"""Extração do texto do EPUB em blocos (parágrafos, títulos, itens, imagens) e palavras.

Cada palavra tem duas formas:
  - `t`: o texto como aparece no livro (vai para a tela)
  - `n`: lista de tokens normalizados (minúsculas, sem pontuação, números por
    extenso) usada só no alinhamento com a transcrição.
"""
from __future__ import annotations

import json
import posixpath
import re
import unicodedata
import warnings
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag, XMLParsedAsHTMLWarning
import ebooklib
from ebooklib import epub

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
warnings.filterwarnings("ignore", category=UserWarning, module="ebooklib")
warnings.filterwarnings("ignore", category=FutureWarning, module="ebooklib")

BLOCK_TAGS = {"p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote",
              "figcaption", "td", "th", "dt", "dd", "pre", "caption"}
CONTAINER_TAGS = {"div", "section", "article", "aside", "body", "ol", "ul",
                  "figure", "table", "thead", "tbody", "tr", "dl", "header",
                  "footer", "nav", "main", "blockquote"}

_num2words_cache: dict[str, callable] = {}


def _num_to_words(num: str, lang: str) -> str:
    from num2words import num2words
    try:
        if re.fullmatch(r"\d+(st|nd|rd|th|º|ª|o|a)", num):
            return num2words(int(re.match(r"\d+", num).group()), lang=lang, to="ordinal")
        if re.fullmatch(r"\d+[.,]\d+", num):
            return num2words(float(num.replace(",", ".")), lang=lang)
        n = int(num)
        if lang == "en" and 1100 <= n <= 2099 and n % 100 != 0 and n // 100 not in (20,):
            # anos: 1990 -> nineteen ninety
            return num2words(n, lang=lang, to="year")
        return num2words(n, lang=lang)
    except Exception:
        return num


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def normalize(token: str, lang: str = "en") -> list[str]:
    """Token de exibição -> tokens normalizados para alinhamento."""
    s = token.lower().replace("’", "'").replace("‘", "'")
    s = s.replace("&", " and " if lang == "en" else " e ")
    s = s.replace("%", " percent" if lang == "en" else " por cento")
    out: list[str] = []
    for part in re.split(r"[—–\-/…]+|\.\.\.", s):
        part = part.strip()
        # números (com ordinal/decimal)
        for piece in re.findall(r"\d+(?:[.,]\d+)?(?:st|nd|rd|th|º|ª)?|[^\d\s]+", part):
            if piece[0].isdigit():
                out.extend(re.findall(r"[a-z]+", strip_accents(_num_to_words(piece, lang).lower())))
            else:
                w = strip_accents(piece)
                w = re.sub(r"[^a-z0-9']", "", w).strip("'")
                if w:
                    out.append(w.replace("'", ""))
    return out


SOFT_HYPHEN = "­"
SPACES = " \t\r\n    "   # separam palavras
NOTEREF_SEL = ('[role="doc-noteref"], a[epub\\:type="noteref"], sup a, '
               'a[href*="footnote"], a[href*="endnote"], [role="doc-pagebreak"], '
               'script, style')                                # E4: fora do texto


def _clean_text(s: str) -> str:
    s = s.replace(SOFT_HYPHEN, "")  # hifenização suave
    s = re.sub(f"[{SPACES}]+", " ", s)
    return s.strip()


def _text_of(el: Tag) -> str:
    """Texto de um bloco, sem quebrar palavras com spans (capitular) e sem chamadas de nota."""
    el = BeautifulSoup(str(el), "lxml").find(el.name)
    for bad in el.select(NOTEREF_SEL):
        bad.decompose()
    for br in el.find_all("br"):
        br.replace_with(" ")
    return _clean_text(el.get_text(""))


def _is_decorative(img: Tag) -> bool:
    cls = " ".join(img.get("class", []))
    return img.get("role") == "presentation" or "inlineimg" in cls or not img.get("src")


class _Extractor:
    def __init__(self, book: epub.EpubBook, lang: str, image_dir: Path):
        self.book = book
        self.lang = lang
        self.image_dir = image_dir
        self.blocks: list[dict] = []
        self.sources: list = []   # elemento (ou texto solto) de origem de cada bloco

    def add_text(self, kind: str, text: str, href: str, source=None):
        if not text:
            return
        words = []
        for tok in text.split(" "):
            words.append({"t": tok, "n": normalize(tok, self.lang)})
        self.blocks.append({"kind": kind, "text": text, "words": words})
        self.sources.append(source)

    def add_image(self, img: Tag, href: str):
        src = posixpath.normpath(posixpath.join(posixpath.dirname(href), img["src"]))
        item = self.book.get_item_with_href(src)
        if item is None:
            return
        name = posixpath.basename(src)
        target = self.image_dir / name
        if not target.exists():
            self.image_dir.mkdir(parents=True, exist_ok=True)
            target.write_bytes(item.get_content())
        self.blocks.append({"kind": "img", "src": name, "alt": img.get("alt", ""), "words": []})
        self.sources.append(img)

    def walk(self, el: Tag, href: str):
        for child in el.children:
            if isinstance(child, NavigableString):
                text = _clean_text(str(child))
                if text and el.name in CONTAINER_TAGS and el.name not in ("ol", "ul", "table", "tr"):
                    self.add_text("p", text, href, child)
                continue
            if not isinstance(child, Tag):
                continue
            name = child.name
            if name == "img":
                if not _is_decorative(child):
                    self.add_image(child, href)
                continue
            if name in BLOCK_TAGS and not child.find(list(BLOCK_TAGS - {"blockquote"})):
                for img in child.find_all("img"):
                    if not _is_decorative(img):
                        self.add_image(img, href)
                kind = "h" if re.fullmatch(r"h\d", name) else ("li" if name == "li" else "p")
                if _is_footnote(child):
                    kind = "note"
                self.add_text(kind, _text_of(child), href, child)
            elif name in CONTAINER_TAGS or name in BLOCK_TAGS:
                self.walk(child, href)
            else:
                # inline solto dentro de container (span, a, b...)
                for img in child.find_all("img"):
                    if not _is_decorative(img):
                        self.add_image(img, href)
                text = _text_of(child)
                if text:
                    self.add_text("p", text, href, child)


def _is_footnote(el: Tag) -> bool:
    attrs = " ".join([" ".join(el.get("class", [])), el.get("role", "") or "",
                      el.get("epub:type", "") or ""]).lower()
    parent = el.parent
    if parent is not None:
        attrs += " " + " ".join(parent.get("class", [])).lower()
        attrs += " " + (parent.get("epub:type", "") or "").lower()
    return any(k in attrs for k in ("footnote", "endnote", "fnlist", "doc-note", "rearnote"))


def _toc_titles(book: epub.EpubBook) -> dict[str, str]:
    titles: dict[str, str] = {}

    def visit(entries):
        for e in entries:
            if isinstance(e, tuple):
                sec, children = e
                if getattr(sec, "href", None):
                    titles.setdefault(sec.href.split("#")[0], sec.title)
                visit(children)
            elif isinstance(e, epub.Link):
                titles.setdefault(e.href.split("#")[0], e.title)

    visit(book.toc)
    return titles


def _language(book: epub.EpubBook) -> str:
    lang_meta = book.get_metadata("DC", "language")
    lang = (lang_meta[0][0] if lang_meta else "en").lower().split("-")[0]
    return "pt" if lang.startswith("pt") else ("en" if lang != "pt" else lang)


def walk_spine(book: epub.EpubBook, lang: str, image_dir: Path):
    """Percorre o spine: (item, soup, extrator) de cada documento com corpo."""
    for idref, linear in book.spine:
        item = book.get_item_with_id(idref)
        if item is None or item.get_type() != ebooklib.ITEM_DOCUMENT:
            continue
        soup = BeautifulSoup(item.content, "lxml")  # bruto: get_content() descarta o <title>
        if soup.body is None:
            continue
        ex = _Extractor(book, lang, image_dir)
        ex.walk(soup.body, item.get_name())
        yield item, soup, ex


def read(epub_path: str) -> epub.EpubBook:
    return epub.read_epub(epub_path, options={"ignore_ncx": False})


def extract(epub_path: str, cache: Path) -> dict:
    book = read(epub_path)
    lang = _language(book)
    title_meta = book.get_metadata("DC", "title")
    title = title_meta[0][0] if title_meta else Path(epub_path).stem
    titles = _toc_titles(book)

    chapters = []
    image_dir = cache / "images"
    for item, soup, ex in walk_spine(book, lang, image_dir):
        if not ex.blocks:
            continue
        head = soup.title.get_text(strip=True) if soup.title else ""
        chapters.append({
            "index": len(chapters),
            "href": item.get_name(),
            "title": titles.get(item.get_name()) or head or item.get_id(),
            "blocks": ex.blocks,
        })

    # ids globais de bloco e palavra
    bi = wi = 0
    for ch in chapters:
        for b in ch["blocks"]:
            b["id"] = bi
            bi += 1
            for w in b["words"]:
                w["id"] = wi
                wi += 1

    data = {"title": title, "language": lang, "chapters": chapters}
    cache.mkdir(parents=True, exist_ok=True)
    (cache / "book.json").write_text(json.dumps(data, ensure_ascii=False))
    return data


def cover_font_files(epub_path: str, dest: Path) -> list[Path]:
    """Copia as fontes embutidas no EPUB (usadas pelo overlay)."""
    book = epub.read_epub(epub_path)
    out = []
    for item in book.get_items():
        name = item.get_name().lower()
        if name.endswith((".ttf", ".otf")):
            dest.mkdir(parents=True, exist_ok=True)
            p = dest / posixpath.basename(item.get_name())
            if not p.exists():
                p.write_bytes(item.get_content())
            out.append(p)
    return out
