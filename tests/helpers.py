"""Construtores de livros e narrações sintéticos para os testes."""
from __future__ import annotations

from scribe.epub import normalize

WORD_DUR = 0.3   # duração de cada palavra falada
WORD_GAP = 0.1   # pausa entre palavras


def make_book(*paragraphs: str, lang: str = "en", kinds: list[str] | None = None) -> dict:
    """Livro com uma seção; cada string vira um bloco (ou imagem, se começar com 'img:')."""
    blocks = []
    wid = 0
    for i, text in enumerate(paragraphs):
        if text.startswith("img:"):
            blocks.append({"id": i, "kind": "img", "src": text[4:], "alt": "", "words": []})
            continue
        words = []
        for tok in text.split():
            words.append({"t": tok, "n": normalize(tok, lang), "id": wid})
            wid += 1
        kind = kinds[i] if kinds else "p"
        blocks.append({"id": i, "kind": kind, "text": text, "words": words})
    return {"title": "Teste", "language": lang,
            "chapters": [{"index": 0, "href": "c.xhtml", "title": "C", "blocks": blocks}]}


def speak(text: str, t0: float = 0.0) -> tuple[list[dict], float]:
    """Narração sintética: palavras com tempo, a partir de t0. Devolve (palavras, fim)."""
    out = []
    t = t0
    for tok in text.split():
        out.append({"w": tok, "s": round(t, 3), "e": round(t + WORD_DUR, 3), "p": 1.0})
        t += WORD_DUR + WORD_GAP
    return out, t


def narrate(*parts) -> list[dict]:
    """Junta trechos falados; um número entre trechos é uma pausa (segundos)."""
    words: list[dict] = []
    t = 0.0
    for p in parts:
        if isinstance(p, (int, float)):
            t += p
        else:
            ws, t = speak(p, t)
            words += ws
    return words


def all_words(book: dict) -> list[dict]:
    return [w for c in book["chapters"] for b in c["blocks"] for w in b["words"]]


def orphan_probe(parent_pid: int, flag: str):
    """W9: filho que só sai quando o laço de comandos pede parada (pai morto)."""
    import time
    from scribe.worker import watch_parent
    cmds = watch_parent(lambda: [], parent_pid)
    for _ in range(600):
        if {"stop": True} in cmds():
            with open(flag, "w") as f:
                f.write("parada")
            return
        time.sleep(0.1)
