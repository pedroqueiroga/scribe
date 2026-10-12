"""Fixtures compartilhadas: EPUBs e transcrições sintéticas."""
from __future__ import annotations

import base64
from pathlib import Path

import pytest
from ebooklib import epub

# PNG 1x1 válido
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")


def make_epub(path: Path, chapters: list[tuple[str, str, str]], lang: str = "en",
              title: str = "Livro de Teste", images: dict[str, bytes] | None = None,
              in_toc: set[str] | None = None) -> Path:
    """Cria um EPUB. `chapters` = [(nome_arquivo, titulo_html, corpo_html)].
    `in_toc` limita quais arquivos entram no sumário (padrão: todos)."""
    book = epub.EpubBook()
    book.set_identifier("id-teste")
    book.set_title(title)
    book.set_language(lang)
    for name, data in (images or {}).items():
        book.add_item(epub.EpubItem(uid=name, file_name=f"images/{name}",
                                    media_type="image/png", content=data))
    items = []
    for fname, head_title, body in chapters:
        c = epub.EpubHtml(title=head_title, file_name=fname, lang=lang)
        c.content = (f"<html><head><title>{head_title}</title></head>"
                     f"<body>{body}</body></html>")
        book.add_item(c)
        items.append(c)
    toc_items = [c for c in items if in_toc is None or c.file_name in in_toc]
    book.toc = [epub.Link(c.file_name, c.title, c.file_name) for c in toc_items]
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = items
    epub.write_epub(str(path), book)
    return path


@pytest.fixture
def epub_factory(tmp_path):
    def factory(chapters, **kw):
        return make_epub(tmp_path / "livro.epub", chapters, **kw)
    return factory
