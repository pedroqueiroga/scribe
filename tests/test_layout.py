"""Imagem ao lado do texto — specs/layout.md (G1–G6)."""
from __future__ import annotations

import pytest

from scribe.layout import CHROME, GAP, MIN_TEXT, VPAD, ImageLayout

SCREEN = 1920        # borda direita da tela
X, W, H = 100, 760, 300   # janela: x, largura, altura
TEXT = W - CHROME    # largura do texto antes da imagem


def show(lay=None, x=X, w=W, h=H, screen=SCREEN, img=(400, 300)):
    lay = lay or ImageLayout()
    return lay, lay.show(x, w, h, screen, *img)


# ---------------------------------------------------------------- G1

def test_G1_painel_tem_a_altura_util_e_a_proporcao_da_imagem():
    _, r = show(img=(400, 300))
    assert r.panel_h == H - 2 * VPAD
    assert r.panel_w / r.panel_h == pytest.approx(400 / 300)


def test_G1_painel_nunca_mais_largo_que_o_texto():
    _, r = show(img=(4000, 100))
    assert r.panel_w == pytest.approx(TEXT)
    assert r.panel_w / r.panel_h == pytest.approx(4000 / 100)


# ---------------------------------------------------------------- G2

def test_G2_com_espaco_a_janela_cresce_e_o_texto_nao_muda():
    _, r = show()
    assert r.window_w == pytest.approx(W + r.panel_w + GAP)
    assert r.text_w == pytest.approx(TEXT)


# ---------------------------------------------------------------- G3

def test_G3_pouco_espaco_cresce_ate_a_borda_e_o_texto_cede_o_resto():
    space = 100
    _, r = show(x=SCREEN - W - space)
    need = r.panel_w + GAP
    assert r.window_w == pytest.approx(W + space)
    assert r.text_w == pytest.approx(TEXT - (need - space))
    assert r.panel_w / r.panel_h == pytest.approx(400 / 300)


def test_G3_texto_nunca_fica_mais_estreito_que_o_minimo_e_a_imagem_encolhe():
    _, r = show(x=SCREEN - W, w=W, img=(1000, 300))     # nenhum espaço à direita
    assert r.window_w == pytest.approx(W)
    assert r.text_w == pytest.approx(MIN_TEXT)
    assert r.text_w + GAP + r.panel_w == pytest.approx(W - CHROME)
    assert r.panel_w / r.panel_h == pytest.approx(1000 / 300)   # sem distorcer
    assert r.panel_h < H - 2 * VPAD


def test_G3_janela_ja_estreita_nao_aperta_mais_o_texto():
    w = CHROME + 250                                     # texto já abaixo do mínimo
    _, r = show(x=SCREEN - w, w=w)
    assert r.text_w == pytest.approx(250)
    assert r.panel_w == 0


# ---------------------------------------------------------------- G4

def test_G4_ao_esconder_a_janela_volta_a_largura_original():
    lay, r = show()
    assert r.window_w > W
    assert lay.hide() == W


def test_G4_esconder_sem_imagem_nao_muda_nada():
    assert ImageLayout().hide() is None


# ---------------------------------------------------------------- G5

def test_G5_geometria_salva_e_a_de_antes_do_crescimento():
    lay, r = show()
    assert lay.saved_width(r.window_w) == W
    lay.hide()
    assert lay.saved_width(W) == W


# ---------------------------------------------------------------- G6

def test_G6_troca_de_imagem_recalcula_a_partir_do_tamanho_original():
    lay, first = show(img=(400, 300))
    second = lay.show(X, first.window_w, H, SCREEN, 300, 300)
    assert second.window_w == pytest.approx(W + second.panel_w + GAP)
    assert lay.hide() == W


# ---------------------------------------------------------------- G4 na janela

def test_G4_ao_esconder_a_imagem_a_interface_e_avisada_que_o_texto_volta(tmp_path, monkeypatch):
    """O QML só relê `imagePanelWidth` se a ponte avisar; sem o aviso, a janela volta ao
    tamanho mas o texto continua estreito, com o espaço da imagem reservado."""
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QGuiApplication, QImage
    from scribe import overlay
    from scribe.library import Library
    from scribe.reader import Reader
    from scribe.session import Session
    from tests.helpers import make_book, narrate
    from tests.test_reader import FakePlayer

    app = QGuiApplication.instance() or QGuiApplication([])
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    (tmp_path / "l.epub").write_bytes(b"e")
    (tmp_path / "l.m4b").write_bytes(b"a")
    lib = Library()
    bid, _ = lib.resolve([str(tmp_path / "l.epub"), str(tmp_path / "l.m4b")])
    cache = lib.cache(bid)
    (cache / "images").mkdir()
    QImage(400, 300, QImage.Format_RGB32).save(str(cache / "images" / "fig.png"))
    p = "uma frase qualquer do livro com palavras suficientes para o alinhamento casar"
    session = Session(make_book(p, "img:fig.png"), cache, 120.0, [])
    session.handle({"type": "segment", "seg": {"s": 0.0, "e": 120.0, "words": narrate(p)}})
    reader = Reader(session, FakePlayer(120.0), lib, bid)
    reader.image = "fig.png"
    bridge = overlay.Bridge(app, reader, overlay.BlockModel(reader, cache), cache)
    bridge.timer.stop()

    bridge.layoutImage(0, 700, 300, 1920)
    assert bridge.imagePanelWidth > 0
    avisos = []
    bridge.imageChanged.connect(lambda: avisos.append(bridge.imagePanelWidth))
    reader.image = None
    assert bridge.restoreWidth() == 700
    assert avisos and avisos[-1] == 0
