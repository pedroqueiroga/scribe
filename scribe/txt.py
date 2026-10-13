"""Livro em texto puro — specs/completo.md (C2).

Vira o mesmo formato que o EPUB (seções, blocos e palavras), para o resto do app não
saber de onde o livro veio.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .epub import _clean_text, normalize

TITLE_MAX = 60
END_PUNCT = ".,;:!?…\"'“”‘’«»—–-"
PT_WORDS = {"de", "que", "não", "nao", "uma", "para", "com", "os", "do", "da", "em", "é",
            "um", "se", "ele", "ela", "mas", "como", "por", "isso"}
EN_WORDS = {"the", "and", "of", "to", "is", "that", "it", "was", "he", "she", "you",
            "not", "with", "for", "but", "this", "had", "have"}


def read_text(path: str) -> str:
    raw = Path(path).read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def paragraphs(text: str) -> list[tuple[str, str]]:
    """(tipo, texto como está no arquivo) de cada parágrafo: `h` para título, senão `p`."""
    out = []
    for para in re.split(r"\n[ \t]*\n", text):
        para = para.strip("\n")
        if not _clean_text(para):
            continue
        out.append(("h" if _is_title(para) else "p", para))
    return out


def _is_title(para: str) -> bool:
    line = para.strip()
    return ("\n" not in line and len(line) <= TITLE_MAX and line[-1] not in END_PUNCT
            and any(c.isalnum() for c in line))


def _language(text: str) -> str:
    words = re.findall(r"\w+", text.lower())
    pt = sum(w in PT_WORDS for w in words)
    en = sum(w in EN_WORDS for w in words)
    return "pt" if pt > en else "en"


def extract(path: str, cache: Path) -> dict:
    text = read_text(path)
    lang = _language(text)
    name = Path(path).stem
    href = Path(path).name
    chapters: list[dict] = []

    def section(title: str) -> list:
        chapters.append({"index": len(chapters), "href": href, "title": title, "blocks": []})
        return chapters[-1]["blocks"]

    blocks = None
    for kind, para in paragraphs(text):
        clean = _clean_text(para)
        if kind == "h":
            blocks = section(clean)
        elif blocks is None:
            blocks = section(name)
        blocks.append({"kind": kind, "text": clean,
                       "words": [{"t": t, "n": normalize(t, lang)} for t in clean.split(" ")]})

    bi = wi = 0                                                   # E7: ids globais
    for ch in chapters:
        for b in ch["blocks"]:
            b["id"] = bi
            bi += 1
            for w in b["words"]:
                w["id"] = wi
                wi += 1

    data = {"title": name, "language": lang, "chapters": chapters}
    cache.mkdir(parents=True, exist_ok=True)
    (cache / "book.json").write_text(json.dumps(data, ensure_ascii=False))
    return data
