"""Imagem ao lado do texto — specs/layout.md (G1–G6)."""
from __future__ import annotations

import pytest

from scribe.layout import CHROME, GAP, ENTER_VERTICAL, INLINE_MAX_H, MIN_TEXT, VPAD, ImageLayout, inline_size, is_vertical
from tests.test_reader import lib  # noqa: F401  (fixture do G8)

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


# ---------------------------------------------------------------- modo vertical

@pytest.mark.parametrize("w, h, oneline, vertical", [
    (400, 930, False, True),      # estreita e alta, encostada na lateral
    (900, 400, False, False),     # barra horizontal
    (500, 500, False, False),     # quadrada não é mais alta que larga
    (300, 60, True, False),       # uma linha nunca é vertical
    (300, 400, True, False),
])
def test_G7_formato_da_janela_decide_o_modo_vertical(w, h, oneline, vertical):
    assert is_vertical(w, h, oneline) is vertical


def test_G7_folga_perto_do_quadrado():
    assert ENTER_VERTICAL == 1.15
    # entrando: só passa para vertical depois de 1,15 × a largura
    assert is_vertical(500, 570, False, now=False) is False
    assert is_vertical(500, 580, False, now=False) is True
    # saindo: continua vertical até a altura ficar menor que a largura
    assert is_vertical(500, 520, False, now=True) is True
    assert is_vertical(500, 500, False, now=True) is True
    assert is_vertical(500, 499, False, now=True) is False
    assert is_vertical(500, 900, True, now=True) is False


def test_G9_imagem_no_texto_ocupa_a_largura_do_texto():
    assert inline_size(300, 900, 1200, 800) == (300, 200)


def test_G9_imagem_alta_limitada_pela_altura_da_janela_sem_distorcer():
    assert INLINE_MAX_H == 0.6
    w, h = inline_size(300, 500, 800, 1600)
    assert h == pytest.approx(300) and w == pytest.approx(150)


def test_G9_imagem_pequena_nao_aumenta():
    assert inline_size(300, 900, 120, 80) == (120, 80)


def test_G9_imagem_sem_tamanho_conhecido_nao_ocupa_espaco():
    assert inline_size(300, 900, 0, 0) == (0, 0)


def test_G8_imagens_com_hora_aparecem_no_texto_e_a_capa_nao(tmp_path, lib):
    from tests.test_reader import P1, P2, build
    reader, *_ = build(tmp_path, lib, "img:capa.png", P1, "img:fig.png", P2)
    assert reader.inline_images() == [False, False, True, False]


def test_G8_imagem_depois_de_texto_ainda_nao_narrado_nao_aparece(tmp_path, lib):
    from tests.test_reader import P1, P2, build
    from tests.helpers import narrate
    reader, *_ = build(tmp_path, lib, P1, "img:fig.png", P2, transcript=narrate(P2))
    assert reader.inline_images()[1] is False


def test_G7_com_o_painel_aberto_vale_a_largura_de_antes_do_crescimento(tmp_path, monkeypatch):
    """No G3 a janela cresce menos que o painel (o texto cede); descontar o painel da
    largura atual daria uma largura menor que a real e faria o modo alternar."""
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

    grown = bridge.layoutImage(900, 600, 540, 1536)         # G3: só 36 px até a borda
    assert grown == 636 and bridge.imagePanelWidth + GAP > grown - 600
    assert bridge.isVertical(grown, 540, False, False) is False
    assert bridge.isVertical(grown, 610, False, True) is True    # julga pelos 600 de antes


# ---------------------------------------------------------------- G10

def _focus_setup(tmp_path, lib):
    from tests.test_reader import P1, P2, build
    reader, player, session, *_ = build(tmp_path, lib, P1, "img:fig.png", P2)
    return reader, player, session.image_time(1), session.block_start(session.blocks[2])


def test_G10_imagem_vira_o_foco_um_segundo_antes_da_hora(tmp_path, lib):
    from scribe.reader import IMAGE_LEAD
    from tests.test_reader import play_to
    reader, player, hour, _ = _focus_setup(tmp_path, lib)
    play_to(reader, player, hour - IMAGE_LEAD - 0.3, step=0.1)
    assert reader.focus_row == -1
    play_to(reader, player, hour - IMAGE_LEAD + 0.2, step=0.1)
    assert reader.focus_row == 1


def test_G10_foco_volta_ao_texto_quando_a_palavra_seguinte_comeca(tmp_path, lib):
    from tests.test_reader import play_to
    reader, player, hour, nxt = _focus_setup(tmp_path, lib)
    assert hour < nxt
    play_to(reader, player, nxt - 0.05, step=0.05)
    assert reader.focus_row == 1
    play_to(reader, player, nxt + 0.1, step=0.05)
    assert reader.focus_row == -1


def test_G10_pulo_para_dentro_do_intervalo_da_o_foco(tmp_path, lib):
    reader, player, hour, _ = _focus_setup(tmp_path, lib)
    reader.seek(hour)
    assert reader.focus_row == 1


def test_G10_sem_fala_depois_o_foco_dura_o_tempo_do_R5(tmp_path, lib):
    from scribe.reader import IMAGE_HOLD
    from tests.test_reader import P1, build
    reader, player, session, *_ = build(tmp_path, lib, P1, "img:fig.png")
    hour = session.image_time(1)
    reader.seek(hour + IMAGE_HOLD - 0.5)
    assert reader.focus_row == 1
    reader.seek(hour + IMAGE_HOLD + 0.5)
    assert reader.focus_row == -1
