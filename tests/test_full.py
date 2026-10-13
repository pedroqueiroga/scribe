"""Modo completo — specs/completo.md (C1–C17)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from scribe import epub as ep
from scribe import full, txt
from scribe.library import Library
from scribe.reader import Reader, line_edges, move_line
from scribe.session import Session, load_book
from tests.conftest import PNG
from tests.helpers import make_book, narrate


def page_of(path: Path, book: dict, cache: Path) -> BeautifulSoup:
    out = full.page(str(path), book, cache)
    return BeautifulSoup(out.read_text(), "lxml")


def word_marks(soup) -> dict[int, str]:
    """C8: texto de cada palavra marcada, pelo trecho registrado no elemento do bloco."""
    out = {}
    for el in soup.select("[data-w]"):
        text = el.get_text()
        for item in el["data-w"].split():
            wid, s, e = map(int, item.split(":"))
            out[wid] = text[s:e].replace(ep.SOFT_HYPHEN, "")
    return out


def word_text(soup, wid: int) -> str:
    return word_marks(soup).get(wid, "")


def all_words(book):
    return [w for c in book["chapters"] for b in c["blocks"] for w in b["words"]]


def all_blocks(book):
    return [b for c in book["chapters"] for b in c["blocks"]]


def epub_page(tmp_path, chapters, **kw):
    from tests.conftest import make_epub
    path = make_epub(tmp_path / "livro.epub", chapters, **kw)
    cache = tmp_path / "cache"
    book = ep.extract(str(path), cache)
    return path, book, cache, page_of(path, book, cache)


def xhtml(body: str, head: str = "", body_attrs: str = "") -> str:
    return ('<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
            '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">'
            f'<head><title>T</title>{head}</head><body{body_attrs}>{body}</body></html>')


# ---------------------------------------------------------------- formatos (C1–C3)

@pytest.fixture
def lib(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    return Library()


def test_C1_txt_e_aceito_como_livro(tmp_path, lib):
    (tmp_path / "conto.txt").write_text("Era uma vez.")
    (tmp_path / "conto.m4b").write_bytes(b"audio")
    bid, entry = lib.resolve([str(tmp_path / "conto.m4b"), str(tmp_path / "conto.txt")])
    assert entry["epub"] == str(tmp_path / "conto.txt")
    book = load_book(entry["epub"], lib.cache(bid))
    assert book["chapters"][0]["blocks"][0]["text"] == "Era uma vez."


def test_C1_pasta_com_txt_e_audio(tmp_path, lib):
    (tmp_path / "conto.txt").write_text("Era uma vez.")
    (tmp_path / "conto.mp3").write_bytes(b"audio")
    _, entry = lib.resolve([str(tmp_path)])
    assert entry["epub"].endswith("conto.txt")


def test_C1_pasta_com_epub_e_txt_vale_o_epub(tmp_path, lib):
    (tmp_path / "livro.epub").write_bytes(b"epub")
    (tmp_path / "leia-me.txt").write_text("notas")
    (tmp_path / "livro.mp3").write_bytes(b"audio")
    _, entry = lib.resolve([str(tmp_path)])
    assert entry["epub"].endswith("livro.epub")


def test_C1_pdf_ainda_nao_e_aceito(tmp_path, lib):
    (tmp_path / "livro.pdf").write_bytes(b"%PDF-1.4")
    (tmp_path / "livro.m4b").write_bytes(b"audio")
    with pytest.raises(SystemExit, match="PDF"):
        lib.resolve([str(tmp_path / "livro.pdf"), str(tmp_path / "livro.m4b")])


def txt_book(tmp_path, content, name="conto.txt", encoding="utf-8"):
    path = tmp_path / name
    path.write_bytes(content.encode(encoding) if isinstance(content, str) else content)
    return path, txt.extract(str(path), tmp_path / "cache")


def blocks_of(book):
    return [(b["kind"], b["text"]) for b in all_blocks(book)]


def test_C2_paragrafos_separados_por_linha_em_branco(tmp_path):
    _, book = txt_book(tmp_path, "Era uma vez\num gato.\n\n\nEle dormia muito.\n")
    assert blocks_of(book) == [("p", "Era uma vez um gato."), ("p", "Ele dormia muito.")]


def test_C2_linha_curta_sem_pontuacao_e_titulo_e_abre_secao(tmp_path):
    _, book = txt_book(tmp_path, "Prefácio curto.\n\nCapítulo 1\n\nEra uma vez.\n\n"
                                 "O Fim\n\nAcabou.")
    assert [c["title"] for c in book["chapters"]] == ["conto", "Capítulo 1", "O Fim"]
    assert blocks_of(book)[1] == ("h", "Capítulo 1")
    assert book["title"] == "conto"


def test_C2_nao_e_titulo(tmp_path):
    long_line = "Uma linha sem ponto mas comprida demais para ser um título de capítulo de verdade"
    _, book = txt_book(tmp_path, f"Sim.\n\nEle disse: “Não!”\n\nduas\nlinhas\n\n{long_line}\n\nFim —"
                                 "\n\n* * *")
    assert [k for k, _ in blocks_of(book)] == ["p"] * 6


def test_C2_utf8_com_bom_e_latin1(tmp_path):
    _, book = txt_book(tmp_path, "﻿Ação.", name="a.txt")
    assert blocks_of(book) == [("p", "Ação.")]
    _, book = txt_book(tmp_path, "Ação e coração.", name="b.txt", encoding="latin-1")
    assert blocks_of(book) == [("p", "Ação e coração.")]


def test_C2_idioma_e_normalizacao(tmp_path):
    _, book = txt_book(tmp_path, "Ele não sabia que a casa era de 5 pessoas.", name="pt.txt")
    assert book["language"] == "pt"
    assert all_words(book)[-2]["n"] == ["cinco"]
    _, book = txt_book(tmp_path, "He did not know that the house had 5 rooms.", name="en.txt")
    assert book["language"] == "en"
    assert all_words(book)[-2]["n"] == ["five"]


def test_C2_ids_globais(tmp_path):
    _, book = txt_book(tmp_path, "Um dois.\n\nTítulo\n\nTrês.")
    assert [b["id"] for b in all_blocks(book)] == [0, 1, 2]
    assert [w["id"] for w in all_words(book)] == [0, 1, 2, 3]


def test_C3_pagina_do_txt_guarda_as_quebras_de_linha(tmp_path):
    path, book = txt_book(tmp_path, "Capítulo 1\n\nEra uma vez\num gato.\n\nFim.")
    soup = page_of(path, book, tmp_path / "cache")
    para = soup.select_one('[data-b="1"]')
    assert para.name == "p"
    assert "vez\num" in para.get_text()
    assert soup.select_one('[data-b="0"]').name in ("h1", "h2")
    for w in all_words(book):                                              # C8
        assert word_text(soup, w["id"]) == w["t"]


# ---------------------------------------------------------------- página do EPUB (C4–C7)

def test_C4_documentos_do_spine_em_secoes_com_tags_e_classes(tmp_path):
    raw = {"b.xhtml": xhtml('<p class="first" style="text-indent:0">Segundo <em>cap</em>.</p>'
                            '<script>alert(1)</script>', body_attrs=' class="calibre"')}
    _, _, _, soup = epub_page(tmp_path, [("a.xhtml", "A", "<h1>Um</h1><p>Primeiro.</p>"),
                                         ("b.xhtml", "B", "<p>x</p>")], raw=raw)
    secs = soup.select("section.scribe-ch")
    assert [s["data-href"] for s in secs] == ["a.xhtml", "b.xhtml"]
    p = secs[1].select_one("p.first")
    assert p["style"] == "text-indent:0" and p.em is not None
    assert "calibre" in secs[1]["class"]
    assert "alert(1)" not in str(soup)


def test_C4_estilos_do_livro_valem_para_a_pagina(tmp_path):
    raw = {"a.xhtml": xhtml("<p>Oi.</p>", head='<link href="s.css" rel="stylesheet" type="text/css"/>'
                                                '<style>p{margin:0}</style>')}
    _, _, cache, soup = epub_page(tmp_path, [("a.xhtml", "A", "<p>Oi.</p>")], raw=raw,
                                  files={"s.css": b"p{color:red}"})
    hrefs = [l["href"] for l in soup.select('link[rel="stylesheet"]')]
    assert any(h.endswith("s.css") for h in hrefs)
    assert any("margin:0" in s.get_text() for s in soup.select("head style"))


def test_C5_imagens_estilos_e_fontes_apontam_para_copias(tmp_path):
    raw = {"text/a.xhtml": xhtml(
        '<p>Oi.</p><img src="../images/x.png" alt="x"/><img src="data:image/png;base64,AAA" alt="d"/>'
        '<img src="http://ex.com/y.png" alt="y"/>',
        head='<link href="../style/s.css" rel="stylesheet" type="text/css"/>'
             '<style>h1{background:url("../images/x.png")}</style>')}
    _, _, cache, soup = epub_page(
        tmp_path, [("text/a.xhtml", "A", "<p>Oi.</p>")], raw=raw, images={"x.png": PNG},
        files={"style/s.css": b"@font-face{src:url(../fonts/f.ttf)}", "fonts/f.ttf": b"ttf"})
    base = cache / "full"
    imgs = [i["src"] for i in soup.select("img")]
    assert imgs[0].startswith("res/") and (base / imgs[0]).read_bytes() == PNG
    assert imgs[1].startswith("data:") and imgs[2] == "http://ex.com/y.png"
    css = next(l["href"] for l in soup.select('link[rel="stylesheet"]') if l["href"].endswith("s.css"))
    assert (base / css).exists()
    # a fonte resolve a partir da cópia do css
    assert ((base / css).parent / "../fonts/f.ttf").resolve().read_bytes() == b"ttf"
    style = next(s.get_text() for s in soup.select("head style") if "h1{" in s.get_text())
    url = style.split('url("')[1].split('"')[0]
    assert url.startswith("res/") and (base / url).read_bytes() == PNG


def test_C6_links_internos_viram_ancoras_da_pagina(tmp_path):
    _, _, _, soup = epub_page(tmp_path, [
        ("a.xhtml", "A", '<p><a href="b.xhtml#n1">nota</a> e <a href="b.xhtml">cap</a> '
                         'e <a href="http://ex.com">fora</a>.</p>'),
        ("b.xhtml", "B", '<p id="n1">Nota um.</p>')])
    hrefs = [a["href"] for a in soup.select("section a[href]")]
    sec_b = soup.select("section.scribe-ch")[1]["id"]
    assert hrefs == ["#n1", f"#{sec_b}", "http://ex.com"]


def test_C7_extracao_antiga_casa_pela_sequencia_e_nao_marca_sem_par(tmp_path):
    from tests.conftest import make_epub
    path = make_epub(tmp_path / "livro.epub", [("a.xhtml", "A", "<p>um dois tres quatro cinco</p>")])
    cache = tmp_path / "cache"
    book = ep.extract(str(path), cache)
    # versão antiga: "dois" não existia e "quatro" estava escrito diferente
    words = book["chapters"][0]["blocks"][0]["words"]
    old = [dict(w) for w in words if w["t"] != "dois"]
    old[2]["t"] = "QUATRO"
    for i, w in enumerate(old):
        w["id"] = i
    book["chapters"][0]["blocks"][0]["words"] = old
    soup = page_of(path, book, cache)
    marks = word_marks(soup)
    assert marks == {0: "um", 1: "tres", 3: "cinco"}


# ---------------------------------------------------------------- todo formato (C8–C10)

def test_C8_cada_palavra_marcada_com_o_texto_dela(tmp_path):
    _, book, _, soup = epub_page(tmp_path, [("a.xhtml", "A",
        '<h1>Título <b>bom</b></h1><p>Uma <i>frase</i>, com&#160;pontua­ção — e fim.</p>'
        '<ul><li>item um</li></ul><p>linha<br/>outra \u00ad solta</p>')])
    assert [w["t"] for w in all_words(book)][-3:] == ["linha", "outra", "solta"]
    marks = word_marks(soup)
    for w in all_words(book):
        assert marks[w["id"]] == w["t"]


def test_C8_capitular_e_um_trecho_so(tmp_path):
    _, book, _, soup = epub_page(tmp_path, [("a.xhtml", "A",
        '<p><span class="cap">W</span>hen it rains.</p>')])
    when = all_words(book)[0]
    assert when["t"] == "When"
    p = soup.select_one("p")
    assert p["data-w"].split()[0] == f"{when['id']}:0:4"
    assert p.select_one("span.cap").get_text() == "W"     # a capitular continua lá


def test_C8_sem_um_elemento_por_palavra(tmp_path):
    _, book, _, soup = epub_page(tmp_path, [("a.xhtml", "A", "<p>Uma <i>frase</i> com cinco palavras.</p>")])
    assert len(soup.select("[data-w]")) == 1
    assert soup.select_one("p").get_text() == "Uma frase com cinco palavras."


def test_C8_chamadas_de_nota_aparecem_sem_marca(tmp_path):
    _, book, _, soup = epub_page(tmp_path, [("a.xhtml", "A",
        '<p>Texto<sup><a href="#fn1">1</a></sup> segue.</p>'
        '<p><span role="doc-pagebreak">12</span>Outra.</p>')])
    assert [w["t"] for w in all_words(book)] == ["Texto", "segue.", "Outra."]
    sup = soup.select_one("sup")
    assert sup.get_text() == "1"
    p = soup.select_one("p")
    ranges = [tuple(map(int, x.split(":")[1:])) for x in p["data-w"].split()]
    at = p.get_text().index("1")
    assert not any(s <= at < e for s, e in ranges)          # a chamada fica fora das palavras
    assert soup.find(attrs={"role": "doc-pagebreak"}).get_text() == "12"
    for w in all_words(book):
        assert word_text(soup, w["id"]) == w["t"]


def test_C8_chamada_no_meio_da_palavra_fica_dentro_do_trecho(tmp_path):
    _, book, _, soup = epub_page(tmp_path, [("a.xhtml", "A",
        '<p>Meu Deus!”<sup><a href="#fn6">6</a></sup>). Fim.</p>')])
    assert [w["t"] for w in all_words(book)] == ["Meu", "Deus!”).", "Fim."]
    assert word_marks(soup) == {0: "Meu", 1: "Deus!”6).", 2: "Fim."}


def test_C8_bloco_que_nao_bate_com_o_extrator_fica_sem_marcas():
    soup = BeautifulSoup("<p>tres palavras aqui</p>", "lxml")
    p = soup.p
    full._mark(soup, p, {"kind": "p", "words": [{"t": "tres"}, {"t": "palavras"}]}, 7, [0, 1])
    assert p["data-b"] == "7" and not p.has_attr("data-w")


def test_C9_todo_bloco_tem_elemento_marcado(tmp_path):
    raw = {"a.xhtml": xhtml('<div>texto solto<p>Normal.</p></div><img src="images/x.png" alt="x"/>'
                            '<div><span>inline solto</span></div>')}
    _, book, _, soup = epub_page(tmp_path, [("a.xhtml", "A", "<p>x</p>")], raw=raw,
                                 images={"x.png": PNG})
    kinds = [(b["kind"], b.get("text")) for b in all_blocks(book)]
    assert kinds == [("p", "texto solto"), ("p", "Normal."), ("img", None), ("p", "inline solto")]
    for b in all_blocks(book):
        el = soup.select(f'[data-b="{b["id"]}"]')
        assert len(el) == 1
        if b["kind"] == "img":
            assert el[0].name == "img"
        else:
            assert el[0].get_text() == b["text"]


def test_C10_pagina_reaproveitada_e_refeita_em_versao_nova(tmp_path, monkeypatch):
    from tests.conftest import make_epub
    path = make_epub(tmp_path / "livro.epub", [("a.xhtml", "A", "<p>Oi.</p>")])
    cache = tmp_path / "cache"
    book = ep.extract(str(path), cache)
    calls = []
    real = full.build_epub
    monkeypatch.setattr(full, "build_epub", lambda *a: calls.append(1) or real(*a))
    first = full.page(str(path), book, cache)
    again = full.page(str(path), book, cache)
    assert first == again and len(calls) == 1
    monkeypatch.setattr(full, "VERSION", full.VERSION + 1)
    full.page(str(path), book, cache)
    assert len(calls) == 2


# ---------------------------------------------------------------- leitor (C11–C17)

class FakePlayer:
    def __init__(self):
        self.time_pos = 0.0
        self.pause = False
        self.speed = 1.0

    def seek(self, t):
        self.time_pos = t


def make_reader(tmp_path, lib, *paragraphs, transcript=None, covered=120.0):
    (tmp_path / "l.epub").write_bytes(b"epub")
    (tmp_path / "l.m4b").write_bytes(b"audio")
    bid, _ = lib.resolve([str(tmp_path / "l.epub"), str(tmp_path / "l.m4b")])
    book = make_book(*paragraphs)
    cache = lib.cache(bid)
    session = Session(book, cache, 120.0, [])
    session.handle({"type": "segment",
                    "seg": {"s": 0.0, "e": covered, "words": transcript or narrate(*paragraphs)}})
    return Reader(session, FakePlayer(), lib, bid), bid


def test_C11_modo_completo_e_salvo(tmp_path, lib):
    r, bid = make_reader(tmp_path, lib, "um dois tres")
    assert r.prefs["full"] is False
    r.toggle_full()
    assert r.prefs["full"] is True
    r2 = Reader(r.session, FakePlayer(), Library(), bid)
    assert r2.prefs["full"] is True


def test_C11_alternar_nao_mexe_no_audio(tmp_path, lib):
    r, _ = make_reader(tmp_path, lib, "um dois tres")
    r.player.time_pos = 0.5
    r.player.pause = False
    r.toggle_full()
    assert r.player.time_pos == 0.5 and r.player.pause is False


def test_C11_flag_full(monkeypatch):
    from scribe import cli, overlay
    got = {}
    monkeypatch.setattr(overlay, "main", lambda paths, model, oneline=False, full=False:
                        got.update(full=full))
    cli.main(["play", "x", "--full"])
    assert got == {"full": True}
    cli.main(["play", "x"])
    assert got == {"full": False}


def test_C12_geometria_por_modo(tmp_path, lib):
    r, _ = make_reader(tmp_path, lib, "um dois tres")
    r.save_geometry([10, 20, 700, 200])
    assert r.toggle_full() == []                         # completo sem geometria salva
    r.save_geometry([100, 50, 900, 1000])
    assert r.toggle_full() == [10, 20, 700, 200]
    assert r.toggle_full() == [100, 50, 900, 1000]
    assert r.prefs["geometry"] == [10, 20, 700, 200]


def test_C12_geometria_padrao_do_modo_completo():
    from scribe.reader import full_default_geometry
    assert full_default_geometry(0, 0, 1920, 1080) == [510, 81, 900, 918]
    # tela estreita: a janela não passa da tela
    assert full_default_geometry(0, 0, 800, 600)[2] == 800


def test_C13_destaque_informa_palavra_bloco_e_sincronia(tmp_path, lib):
    r, _ = make_reader(tmp_path, lib, "um dois tres", "quatro cinco")
    r.player.time_pos = 1.3          # "quatro" começa em 1.2
    r.tick()
    assert r.highlight() == {"word": 3, "row": 1, "synced": True}


def test_C13_sem_sincronia(tmp_path, lib):
    r, _ = make_reader(tmp_path, lib, "um dois tres quatro cinco", covered=2.0)
    r.player.time_pos = 60.0          # S2: longe do fim e sem transcrição
    r.tick()
    assert r.highlight() == {"word": None, "row": 0, "synced": False}


def test_C13_trecho_so_do_audio_mantem_a_ultima_palavra_do_livro(tmp_path, lib):
    r, _ = make_reader(tmp_path, lib, "um dois tres quatro cinco")
    r.session.extras = [{"after": 4, "words": [{"w": "extra", "s": 5.0, "e": 5.3, "p": 1.0}]}]
    r.session.extra_at = lambda t: (0, 0) if t >= 5.0 else None
    r.player.time_pos = 5.1
    r.tick()
    assert r.current_extra == (0, 0)
    assert r.highlight() == {"word": 4, "row": 0, "synced": True}


def test_C14_clicar_na_palavra_pelo_id(tmp_path, lib):
    r, _ = make_reader(tmp_path, lib, "um dois tres", "quatro cinco")
    r.seek_word_id(4)
    assert r.player.time_pos == pytest.approx(1.6 - 0.05)


def test_C15_zoom_em_degraus_com_limites_e_salvo(tmp_path, lib):
    r, bid = make_reader(tmp_path, lib, "um dois tres")
    font = r.prefs["font_size"]
    r.zoom(1)
    assert r.prefs["full_zoom"] == pytest.approx(1.1)
    for _ in range(40):
        r.zoom(1)
    assert r.prefs["full_zoom"] == pytest.approx(3.0)
    for _ in range(40):
        r.zoom(-1)
    assert r.prefs["full_zoom"] == pytest.approx(0.5)
    assert r.prefs["font_size"] == font
    assert Library().data["ui"]["full_zoom"] == pytest.approx(0.5)


# ---------------------------------------------------------------- linha da página (C16)

def test_C16_padrao_salvo_e_restaurado(tmp_path, lib):
    r, bid = make_reader(tmp_path, lib, "um dois tres")
    assert (r.prefs["full_measure"], r.prefs["full_offset"]) == (39, 0.5)
    r.set_line(52.345, 0.2567)
    assert (r.prefs["full_measure"], r.prefs["full_offset"]) == (52.3, 0.257)
    ui = Library().data["ui"]
    assert (ui["full_measure"], ui["full_offset"]) == (52.3, 0.257)


@pytest.mark.parametrize("given,expected", [((5, -1), (15, 0)), ((500, 3), (120, 1))])
def test_C16_limites(tmp_path, lib, given, expected):
    r, _ = make_reader(tmp_path, lib, "um dois tres")
    r.set_line(*given)
    assert (r.prefs["full_measure"], r.prefs["full_offset"]) == expected


@pytest.mark.parametrize("offset,left", [(0, 24), (1, 1000 - 24 - 400), (0.5, 300), (0.25, 162)])
def test_C16_posicao_e_a_fracao_do_branco_a_esquerda(offset, left):
    # página de 1000 px, em de 10 px: margem mínima de 24 px, linha de 400 px
    assert line_edges(1000, 10, 40, offset) == pytest.approx((left, left + 400))


def test_C16_pagina_estreita_a_linha_ocupa_o_que_cabe():
    for offset in (0, 0.5, 1):
        assert line_edges(300, 10, 40, offset) == pytest.approx((24, 276))


def test_C16_mover_o_comeco_deixa_o_fim():
    left, right = line_edges(1000, 10, 40, 0.5)
    m, o = move_line(1000, 10, 40, 0.5, "left", 200)
    assert line_edges(1000, 10, m, o) == pytest.approx((200, right), abs=1)
    assert m == 50


def test_C16_mover_o_fim_deixa_o_comeco():
    m, o = move_line(1000, 10, 40, 0.5, "right", 900)
    assert line_edges(1000, 10, m, o) == pytest.approx((300, 900), abs=1)
    assert m == 60


def test_C16_mover_a_linha_mantem_o_comprimento():
    m, o = move_line(1000, 10, 40, 0.5, "both", 100)
    assert m == 40
    assert line_edges(1000, 10, m, o) == pytest.approx((100, 500), abs=1)
    assert move_line(1000, 10, 40, 0.5, "both", -50) == (40, 0)        # margem mínima
    assert move_line(1000, 10, 40, 0.5, "both", 900) == (40, 1)


def test_C16_as_pontas_respeitam_margens_e_limites():
    assert line_edges(1000, 10, *move_line(1000, 10, 40, 0.5, "left", 0)) == pytest.approx((24, 700), abs=1)
    assert line_edges(1000, 10, *move_line(1000, 10, 40, 0.5, "right", 2000)) == pytest.approx((300, 976), abs=1)
    assert move_line(3000, 10, 40, 0.5, "right", 3000)[0] == 120
    assert move_line(1000, 10, 40, 0.5, "left", 690)[0] == 15         # comprimento mínimo
    assert move_line(1000, 10, 40, 0.5, "right", 310)[0] == 15
    assert move_line(3000, 10, 40, 0.5, "left", 0)[0] == 120          # comprimento máximo
    left, right = line_edges(3000, 10, *move_line(3000, 10, 40, 0.5, "left", 0))
    assert right == pytest.approx(line_edges(3000, 10, 40, 0.5)[1], abs=1)   # o fim fica no lugar


def test_C16_pagina_estreita_mover_a_linha_nao_muda_nada():
    # a linha de 40 em não cabe em 300 px: ocupa o que cabe, e o que está salvo fica
    assert move_line(300, 10, 40, 0.7, "both", 0) == (40, 0.7)
    assert move_line(300, 10, 40, 0.7, "both", 200) == (40, 0.7)


def test_C16_arredonda_como_a_preferencia():
    m, o = move_line(1000, 10, 40, 0.5, "left", 233.33)
    assert m == round(m, 1) and o == round(o, 3)


# ---------------------------------------------------------------- maximizada (C17)

def test_C17_maximizada_e_salva(tmp_path, lib):
    r, _ = make_reader(tmp_path, lib, "um dois tres")
    r.toggle_full()
    assert not r.maximized()
    r.set_maximized(True)
    assert r.maximized()
    assert Library().data["ui"]["full_maximized"] is True


def test_C17_maximizada_nao_troca_a_geometria_salva(tmp_path, lib):
    r, _ = make_reader(tmp_path, lib, "um dois tres")
    r.toggle_full()
    r.save_geometry([100, 50, 900, 700])
    r.set_maximized(True)
    r.save_geometry([0, 0, 1920, 1080])               # o tamanho de maximizada
    assert r.prefs["full_geometry"] == [100, 50, 900, 700]
    r.set_maximized(False)
    r.save_geometry([120, 60, 900, 700])
    assert r.prefs["full_geometry"] == [120, 60, 900, 700]


def test_C17_o_overlay_nunca_e_maximizado(tmp_path, lib):
    r, _ = make_reader(tmp_path, lib, "um dois tres")
    r.save_geometry([10, 20, 700, 200])
    r.toggle_full()
    r.set_maximized(True)
    assert r.toggle_full() == [10, 20, 700, 200]      # volta ao overlay
    assert not r.maximized()
    r.save_geometry([30, 40, 700, 200])               # o overlay salva a sua normalmente
    assert r.prefs["geometry"] == [30, 40, 700, 200]


def test_C17_o_completo_volta_maximizado(tmp_path, lib):
    r, _ = make_reader(tmp_path, lib, "um dois tres")
    r.toggle_full()
    r.set_maximized(True)
    r.toggle_full()
    assert r.toggle_full() is not None and r.maximized()


def test_C17_maximizar_so_vale_no_completo(tmp_path, lib):
    r, _ = make_reader(tmp_path, lib, "um dois tres")
    r.set_maximized(True)                             # no overlay: ignorado
    assert not r.maximized() and not r.prefs["full_maximized"]

