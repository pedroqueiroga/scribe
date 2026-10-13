"""Modo completo — specs/completo.md.

Gera, a partir do arquivo do livro, uma página HTML única com cada palavra marcada com o
`id` dela (`data-w`) e cada bloco com o seu (`data-b`). A página não sabe nada do áudio: a
interface só diz a ela qual é a palavra atual (scribe.js).
"""
from __future__ import annotations

import difflib
import html
import posixpath
import re
import shutil
from pathlib import Path
from urllib.parse import quote, unquote

import ebooklib
from bs4 import BeautifulSoup, NavigableString, Tag

from . import epub as ep
from . import txt

VERSION = 2                       # C10: muda quando o formato da página muda
HERE = Path(__file__).parent
ASSETS = ("scribe.css", "scribe.js")   # copiados a cada abertura: não exigem refazer a página
EXTERNAL = re.compile(r"^(#|data:|[a-z][a-z0-9+.-]*:)", re.I)
CSS_URL = re.compile(r"""url\(\s*(['"]?)([^'")]+)\1\s*\)""")


def page(book_path: str, book: dict, cache: Path) -> Path:
    """C10: a página do livro, gerada só na primeira vez (ou numa versão nova)."""
    out = cache / "full"
    html_path = out / "book.html"
    stamp = out / "version"
    if not (html_path.exists() and stamp.exists() and stamp.read_text() == str(VERSION)):
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)
        build = build_txt if book_path.lower().endswith(".txt") else build_epub
        build(book_path, book, out)
        stamp.write_text(str(VERSION))
    for name in ASSETS:
        shutil.copyfile(HERE / name, out / name)
    return html_path


# ---------------------------------------------------------------- todo formato (C8, C9)

def _document(title: str, lang: str, head: list[str], body: list[str], kind: str) -> str:
    return ("<!DOCTYPE html>\n"
            f'<html lang="{lang}"><head><meta charset="utf-8"><title>{html.escape(title)}</title>'
            '<style id="scribe-base">html{background:#fbf8f1;color:#1d1b16}'
            'body{margin:0}img,svg{max-width:100%;height:auto}</style>'
            + "".join(head) +
            '<link rel="stylesheet" href="scribe.css"></head>'
            f'<body><main class="scribe-page scribe-{kind}">' + "".join(body) +
            '</main><script src="scribe.js"></script></body></html>')


def _map_ids(blocks: list[dict], book: dict) -> tuple[list[int | None], list[list[int | None]]]:
    """C7: id do bloco e de cada palavra no `book.json`, casando pela sequência de textos."""
    old_blocks = [b for c in book["chapters"] for b in c["blocks"]]
    old_words = [w for b in old_blocks for w in b["words"]]
    new_t = [w["t"] for b in blocks for w in b["words"]]
    old_t = [w["t"] for w in old_words]
    flat: list[int | None] = [None] * len(new_t)
    if new_t == old_t:
        flat = [w["id"] for w in old_words]
    else:
        sm = difflib.SequenceMatcher(None, new_t, old_t, autojunk=False)
        for a, b, n in sm.get_matching_blocks():
            for i in range(n):
                flat[a + i] = old_words[b + i]["id"]
    word_ids, i = [], 0
    for b in blocks:
        word_ids.append(flat[i:i + len(b["words"])])
        i += len(b["words"])

    same_shape = [b["kind"] for b in blocks] == [b["kind"] for b in old_blocks]
    if same_shape and new_t == old_t:
        return [b["id"] for b in old_blocks], word_ids
    block_of = {w["id"]: b["id"] for b in old_blocks for w in b["words"]}
    old_imgs = [b for b in old_blocks if b["kind"] == "img"]
    block_ids: list[int | None] = []
    for b, wids in zip(blocks, word_ids):
        if b["kind"] == "img":
            k = next((k for k, o in enumerate(old_imgs) if o["src"] == b["src"]), None)
            block_ids.append(old_imgs.pop(k)["id"] if k is not None else None)
        else:
            block_ids.append(next((block_of[w] for w in wids if w is not None), None))
    return block_ids, word_ids


def _word_ranges(el: Tag) -> list[tuple[int, int]]:
    """C8: trecho (início, fim) de cada palavra no texto do elemento, como o navegador o
    conta (todos os textos, na ordem). Divide como o extrator (`_clean_text` + split): só
    os textos que ele lê (sem as chamadas de nota, E4), com <br> separando palavras."""
    bad = {id(t) for t in el.select(ep.NOTEREF_SEL)}
    ranges: list[list[int]] = []
    pos, in_word = 0, False
    for node in el.descendants:
        if isinstance(node, Tag):
            if node.name == "br":
                in_word = False
            continue
        if type(node) is not NavigableString:
            continue
        text = str(node)
        if any(id(p) in bad for p in node.parents):
            pos += len(text)
            continue
        for ch in text:
            if ch in ep.SPACES:
                in_word = False
            elif ch != ep.SOFT_HYPHEN or in_word:
                if not in_word:
                    ranges.append([pos, pos])
                    in_word = True
                ranges[-1][1] = pos + 1
            pos += 1
    return [tuple(r) for r in ranges]


def _mark(soup: BeautifulSoup, source, block: dict, bid: int | None, wids: list[int | None]):
    """C8/C9: marca o bloco e o trecho de cada palavra dele, no próprio elemento do bloco."""
    if getattr(source, "decomposed", False):
        return                                # um <script> que o extrator leu como texto
    if isinstance(source, NavigableString):  # texto solto num contêiner ganha elemento
        span = soup.new_tag("span")
        source.replace_with(span)
        span.append(source)
        source = span
    if bid is not None:
        source["data-b"] = str(bid)
    if block["kind"] == "img":
        return
    ranges = _word_ranges(source)
    if len(ranges) != len(wids):
        return                                # não bate com o extrator: melhor sem marca
    marks = " ".join(f"{w}:{s}:{e}" for w, (s, e) in zip(wids, ranges) if w is not None)
    if marks:
        source["data-w"] = marks


# ---------------------------------------------------------------- EPUB (C4–C7)

def _resource(url: str, doc: str) -> str:
    """C5: endereço relativo a um documento do EPUB → cópia em `res/`."""
    if not url or EXTERNAL.match(url.strip()):
        return url
    path, _, frag = url.strip().partition("#")
    target = posixpath.normpath(posixpath.join(posixpath.dirname(doc), unquote(path)))
    return "res/" + quote(target) + ("#" + frag if frag else "")


def _rewrite_css(css: str, doc: str) -> str:
    return CSS_URL.sub(lambda m: f'url("{_resource(m.group(2), doc)}")', css)


def build_epub(epub_path: str, book: dict, out: Path):
    b = ep.read(epub_path)
    res = out / "res"
    for item in b.get_items():                                            # C5
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            continue
        dest = res / item.get_name()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(item.get_content())

    docs = list(ep.walk_spine(b, ep._language(b), out.parent / "images"))
    sections = {item.get_name(): f"scribe-ch-{i}" for i, (item, _, _) in enumerate(docs)}
    blocks = [blk for _, _, ex in docs for blk in ex.blocks]
    block_ids, word_ids = _map_ids(blocks, book)

    head: list[str] = []
    seen: set[str] = set()
    body: list[str] = []
    k = 0
    for item, soup, ex in docs:
        doc = item.get_name()
        for el in soup.body.find_all("script"):                            # C4
            el.decompose()
        for blk, src in zip(ex.blocks, ex.sources):                       # C8, C9
            _mark(soup, src, blk, block_ids[k], word_ids[k])
            k += 1
        for el in soup.head.find_all(["link", "style"]) if soup.head else []:   # C4
            if el.name == "link" and "stylesheet" in (el.get("rel") or []):
                el["href"] = _resource(el.get("href", ""), doc)
                key = el["href"]
            elif el.name == "style":
                el.string = _rewrite_css(el.get_text(), doc)
                key = el.string
            else:
                continue
            if key not in seen:
                seen.add(key)
                head.append(str(el))
        bod = soup.body
        for el in bod.find_all(True):
            for attr in ("src", "poster", "xlink:href"):
                if el.has_attr(attr):
                    el[attr] = _resource(el[attr], doc)
            if el.has_attr("href"):
                el["href"] = _link(el["href"], doc, sections) if el.name == "a" \
                    else _resource(el["href"], doc)
            if el.name == "style":
                el.string = _rewrite_css(el.get_text(), doc)
        sec = soup.new_tag("section", attrs={
            "class": " ".join(["scribe-ch", *bod.get("class", [])]),
            "id": sections[doc], "data-href": doc})
        if bod.get("style"):
            sec["style"] = bod["style"]
        for child in list(bod.contents):
            sec.append(child.extract())
        body.append(str(sec))
    _write(out, _document(book["title"], book["language"], head, body, "epub"))


def _link(href: str, doc: str, sections: dict[str, str]) -> str:
    """C6: link para outro documento do livro → ponto dentro da página."""
    if not href or EXTERNAL.match(href.strip()):
        return href
    path, _, frag = href.strip().partition("#")
    target = posixpath.normpath(posixpath.join(posixpath.dirname(doc), unquote(path)))
    if target in sections:
        return "#" + (frag or sections[target])
    return _resource(href, doc)


# ---------------------------------------------------------------- TXT (C3)

def build_txt(path: str, book: dict, out: Path):
    soup = BeautifulSoup("", "lxml")
    blocks, sources = [], []
    for kind, raw in txt.paragraphs(txt.read_text(path)):
        el = soup.new_tag("h2" if kind == "h" else "p")
        el.string = raw
        text = ep._clean_text(raw)
        blocks.append({"kind": kind, "words": [{"t": t} for t in text.split(" ")]})
        sources.append(el)
    block_ids, word_ids = _map_ids(blocks, book)
    body: list[str] = []
    sec = None
    for blk, el, bid, wids in zip(blocks, sources, block_ids, word_ids):
        if blk["kind"] == "h" or sec is None:
            sec = soup.new_tag("section", attrs={"class": "scribe-ch",
                                                 "id": f"scribe-ch-{len(body)}"})
            body.append(sec)
        sec.append(el)
        _mark(soup, el, blk, bid, wids)
    _write(out, _document(book["title"], book["language"], [], [str(s) for s in body], "txt"))


def _write(out: Path, text: str):
    tmp = out / "book.html.tmp"
    tmp.write_text(text)
    tmp.replace(out / "book.html")
