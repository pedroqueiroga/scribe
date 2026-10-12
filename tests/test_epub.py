"""Extração do EPUB — specs/epub.md (E1–E9, N1–N5)."""
from __future__ import annotations

import pytest

from scribe import epub
from tests.conftest import PNG


def extract(epub_factory, tmp_path, chapters, **kw):
    path = epub_factory(chapters, **kw)
    return epub.extract(str(path), tmp_path / "cache")


def blocks_of(data):
    return [b for ch in data["chapters"] for b in ch["blocks"]]


def texts(data):
    return [b.get("text") for b in blocks_of(data)]


# ---------------------------------------------------------------- E1 ordem

def test_E1_secoes_seguem_o_spine_e_blocos_a_ordem_do_documento(epub_factory, tmp_path):
    data = extract(epub_factory, tmp_path, [
        ("b.xhtml", "B", "<p>primeiro da b</p><p>segundo da b</p>"),
        ("a.xhtml", "A", "<p>único da a</p>"),
    ])
    assert [c["href"] for c in data["chapters"]] == ["b.xhtml", "a.xhtml"]
    assert texts(data) == ["primeiro da b", "segundo da b", "único da a"]


# ---------------------------------------------------------------- E2 tipos

def test_E2_tipos_de_bloco(epub_factory, tmp_path):
    data = extract(epub_factory, tmp_path, [("c.xhtml", "C", """
        <h1>Título</h1>
        <p>Parágrafo.</p>
        <ol><li>Item um.</li><li>Item dois.</li></ol>
        <div>Texto solto num div.</div>
    """)])
    kinds = [(b["kind"], b["text"]) for b in blocks_of(data)]
    assert kinds == [
        ("h", "Título"),
        ("p", "Parágrafo."),
        ("li", "Item um."),
        ("li", "Item dois."),
        ("p", "Texto solto num div."),
    ]


# ---------------------------------------------------------------- E3 inline

def test_E3_capitular_nao_quebra_a_palavra(epub_factory, tmp_path):
    data = extract(epub_factory, tmp_path, [("c.xhtml", "C",
        '<p><span class="stickup">w</span>hen you look at <b>very</b> messy space</p>')])
    assert texts(data) == ["when you look at very messy space"]


def test_E3_espacos_e_quebras_de_linha_sao_normalizados(epub_factory, tmp_path):
    data = extract(epub_factory, tmp_path, [("c.xhtml", "C",
        "<p>uma\n   linha<br/>outra linha</p>")])
    assert texts(data) == ["uma linha outra linha"]


# ---------------------------------------------------------------- E4 notas/páginas

def test_E4_chamada_de_nota_e_marca_de_pagina_somem_do_texto(epub_factory, tmp_path):
    data = extract(epub_factory, tmp_path, [("c.xhtml", "C",
        '<p>Executive<a href="#footnote-001" id="footnote-001-backlink"><sup>1</sup></a> '
        'functioning <span role="doc-pagebreak" aria-label="page 3" id="page_3"></span>skills</p>')])
    assert texts(data) == ["Executive functioning skills"]


# ---------------------------------------------------------------- E5 rodapé

def test_E5_nota_de_rodape_vira_bloco_note(epub_factory, tmp_path):
    data = extract(epub_factory, tmp_path, [("c.xhtml", "C", """
        <p>Texto principal.</p>
        <ol class="fnlist"><li class="footnote1"><a href="#x" id="footnote-001">1</a> Veja o apêndice.</li></ol>
    """)])
    b = blocks_of(data)
    assert [x["kind"] for x in b] == ["p", "note"]
    assert "Veja o apêndice." in b[1]["text"]


# ---------------------------------------------------------------- E6 imagens

def test_E6_imagem_de_conteudo_vira_bloco_e_e_copiada(epub_factory, tmp_path):
    data = extract(epub_factory, tmp_path, [("c.xhtml", "C",
        '<p>antes</p><div><img alt="Figura" src="images/fig.png"/></div><p>depois</p>')],
        images={"fig.png": PNG})
    b = blocks_of(data)
    assert [x["kind"] for x in b] == ["p", "img", "p"]
    assert b[1]["src"] == "fig.png"
    assert (tmp_path / "cache" / "images" / "fig.png").read_bytes() == PNG


def test_E6_imagens_decorativas_sao_ignoradas(epub_factory, tmp_path):
    data = extract(epub_factory, tmp_path, [("c.xhtml", "C",
        '<p>texto <img class="inlineimg" alt="emoji" src="images/e.png"/></p>'
        '<div><img alt="" role="presentation" src="images/orn.png"/></div>')],
        images={"e.png": PNG, "orn.png": PNG})
    assert [x["kind"] for x in blocks_of(data)] == ["p"]


# ---------------------------------------------------------------- E7 ids

def test_E7_ids_globais_crescentes_a_partir_de_zero(epub_factory, tmp_path):
    data = extract(epub_factory, tmp_path, [
        ("a.xhtml", "A", "<p>um dois</p><p>três</p>"),
        ("b.xhtml", "B", "<p>quatro cinco</p>"),
    ])
    b = blocks_of(data)
    assert [x["id"] for x in b] == [0, 1, 2]
    word_ids = [w["id"] for x in b for w in x["words"]]
    assert word_ids == list(range(5))


# ---------------------------------------------------------------- E8 idioma

@pytest.mark.parametrize("lang,expected", [("pt-BR", "pt"), ("pt", "pt"), ("EN-US", "en"),
                                           ("en", "en"), ("fr", "en")])
def test_E8_idioma(epub_factory, tmp_path, lang, expected):
    data = extract(epub_factory, tmp_path, [("c.xhtml", "C", "<p>x</p>")], lang=lang)
    assert data["language"] == expected


# ---------------------------------------------------------------- E9 títulos

def test_E9_titulo_vem_do_sumario_ou_do_title(epub_factory, tmp_path):
    data = extract(epub_factory, tmp_path, [
        ("a.xhtml", "Capítulo Um", "<p>x</p>"),
        ("b.xhtml", "Título do Documento", "<p>y</p>"),
    ], in_toc={"a.xhtml"})
    assert [c["title"] for c in data["chapters"]] == ["Capítulo Um", "Título do Documento"]


# ---------------------------------------------------------------- N normalização

@pytest.mark.parametrize("token,expected", [
    ("Hello,", ["hello"]),                 # N1
    ("it’s", ["its"]),                     # N1
    ("Coração", ["coracao"]),              # N1 (sem acento)
    ("“Quoted”", ["quoted"]),              # N1
    ("done—all", ["done", "all"]),         # N3
    ("and/or", ["and", "or"]),             # N3
    ("wait…", ["wait"]),                   # N3
    ("&", ["and"]),                        # N4
    ("50%", ["fifty", "percent"]),         # N2 + N4
    ("—", []),                             # N5
    ("...", []),                           # N5
])
def test_N_normalizacao_em_ingles(token, expected):
    assert epub.normalize(token, "en") == expected


@pytest.mark.parametrize("token,lang,expected", [
    ("5", "en", ["five"]),
    ("5", "pt", ["cinco"]),
    ("21st", "en", ["twenty", "first"]),
    ("1990", "en", ["nineteen", "ninety"]),
    ("2000", "en", ["two", "thousand"]),
    ("&", "pt", ["e"]),
])
def test_N2_numeros_por_extenso(token, lang, expected):
    assert epub.normalize(token, lang) == expected


def test_palavras_guardam_original_e_normalizado(epub_factory, tmp_path):
    data = extract(epub_factory, tmp_path, [("c.xhtml", "C", "<p>Chapter 4: Tidy—up!</p>")])
    words = blocks_of(data)[0]["words"]
    assert [w["t"] for w in words] == ["Chapter", "4:", "Tidy—up!"]
    assert [w["n"] for w in words] == [["chapter"], ["four"], ["tidy", "up"]]
