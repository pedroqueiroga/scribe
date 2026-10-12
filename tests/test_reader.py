"""Leitor — specs/reader.md (R1–R8). Usa um tocador falso no lugar do mpv."""
from __future__ import annotations

import pytest

from scribe.library import Library
from scribe.reader import IMAGE_SECONDS, SPEEDS, Reader
from scribe.session import Session
from tests.helpers import all_words, make_book, narrate

P1 = ("when you look at a very messy space it is easy to feel overwhelmed "
      "take a few minutes to speak some compassionate words to yourself")
P2 = ("there are actually only five things in any room trash dishes laundry "
      "things that have a place and things that do not have a place")
P3 = ("the first step is to take a trash bag and pick up all the trash "
      "throw it away into the bag and do not take the trash out yet")


class FakePlayer:
    def __init__(self, duration):
        self.time_pos = 0.0
        self.pause = False
        self.speed = 1.0
        self.duration = duration
        self.seeks = []

    def seek(self, t):
        self.seeks.append(t)
        self.time_pos = t


@pytest.fixture
def lib(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    (tmp_path / "l.epub").write_bytes(b"epub")
    (tmp_path / "l.m4b").write_bytes(b"audio")
    return Library()


def build(tmp_path, lib, *paragraphs, transcript=None, duration=120.0):
    """Livro + sessão já com a narração inteira transcrita + leitor parado em 0."""
    book = make_book(*paragraphs)
    bid, _ = lib.resolve([str(tmp_path / "l.epub"), str(tmp_path / "l.m4b")])
    session = Session(book, lib.cache(bid), duration=duration, audio_chapters=[])
    tr = transcript if transcript is not None else narrate(*[p for p in paragraphs
                                                             if not p.startswith("img:")])
    session.handle({"type": "segment", "seg": {"s": 0.0, "e": duration, "words": tr}})
    player = FakePlayer(duration)
    reader = Reader(session, player, lib, bid)
    return reader, player, session, book, tr


def play_to(reader, player, t, step=0.25):
    """Simula a reprodução normal até t, com ticks regulares."""
    while player.time_pos < t:
        player.time_pos = min(t, player.time_pos + step)
        reader.tick()


# ---------------------------------------------------------------- R1

def test_R1_clicar_numa_palavra_narrada_vai_ao_inicio_dela(tmp_path, lib):
    reader, player, _, book, tr = build(tmp_path, lib, P1, P2)
    reader.seek_word(1, 2)                   # 3ª palavra do 2º parágrafo
    k = len(P1.split()) + 2
    assert player.time_pos == pytest.approx(tr[k]["s"], abs=0.06)
    assert player.time_pos <= tr[k]["s"]


def test_R1_clicar_em_palavra_sem_tempo_vai_a_proxima_narrada(tmp_path, lib):
    junk = "thank you for downloading this ebook join our mailing list for more offers today"
    reader, player, session, book, tr = build(tmp_path, lib, P1, junk, P2,
                                        transcript=narrate(P1, P2))  # propaganda não lida
    reader.seek_word(1, 0)                   # palavra pulada
    first_p2 = len(P1.split())
    assert player.time_pos == pytest.approx(tr[first_p2]["s"], abs=0.06)


# ---------------------------------------------------------------- R2

def test_R2_proximo_paragrafo(tmp_path, lib):
    reader, player, *_ , tr = build(tmp_path, lib, P1, P2, P3)
    play_to(reader, player, 2.0)
    reader.jump_block(+1)
    assert player.time_pos == pytest.approx(tr[len(P1.split())]["s"], abs=0.06)


def test_R2_anterior_volta_ao_inicio_do_atual_se_ja_passaram_2s(tmp_path, lib):
    reader, player, *_, tr = build(tmp_path, lib, P1, P2, P3)
    start_p2 = tr[len(P1.split())]["s"]
    reader.seek(start_p2 + 3.0)
    reader.tick()
    reader.jump_block(-1)
    assert player.time_pos == pytest.approx(start_p2, abs=0.06)


def test_R2_anterior_no_comeco_do_paragrafo_vai_ao_paragrafo_anterior(tmp_path, lib):
    reader, player, *_, tr = build(tmp_path, lib, P1, P2, P3)
    start_p2 = tr[len(P1.split())]["s"]
    reader.seek(start_p2 + 0.5)
    reader.tick()
    reader.jump_block(-1)
    assert player.time_pos == pytest.approx(tr[0]["s"], abs=0.06)


def test_R2_pula_paragrafos_nao_narrados(tmp_path, lib):
    junk = "thank you for downloading this ebook join our mailing list for more offers today"
    reader, player, *_, tr = build(tmp_path, lib, P1, junk, P2,
                                        transcript=narrate(P1, P2))  # propaganda não lida
    play_to(reader, player, 1.0)
    reader.jump_block(+1)
    assert player.time_pos == pytest.approx(tr[len(P1.split())]["s"], abs=0.06)


# ---------------------------------------------------------------- R3

def test_R3_pulos_de_tempo_ficam_dentro_do_audio(tmp_path, lib):
    reader, player, *_ = build(tmp_path, lib, P1, duration=60.0)
    reader.seek(5.0)
    reader.skip(-10)
    assert player.time_pos == 0.0
    reader.seek(55.0)
    reader.skip(+10)
    assert player.time_pos < 60.0


# ---------------------------------------------------------------- R4

def test_R4_velocidade_em_degraus_com_limites(tmp_path, lib):
    reader, player, *_ = build(tmp_path, lib, P1)
    reader.adjust_speed(+1)
    assert player.speed == SPEEDS[SPEEDS.index(1.0) + 1]
    for _ in range(20):
        reader.adjust_speed(+1)
    assert player.speed == max(SPEEDS) == 2.0
    for _ in range(20):
        reader.adjust_speed(-1)
    assert player.speed == min(SPEEDS) == 0.75


def test_R4_velocidade_lembrada_por_livro(tmp_path, lib):
    reader, player, session, *_ = build(tmp_path, lib, P1)
    reader.adjust_speed(+1)
    bid = reader.bid
    again = Reader(session, FakePlayer(120.0), Library(), bid)
    assert again.player.speed == SPEEDS[SPEEDS.index(1.0) + 1]


# ---------------------------------------------------------------- R5

def test_R5_imagem_aparece_ao_passar_e_some_depois_de_7s(tmp_path, lib):
    reader, player, session, *_ , tr = build(tmp_path, lib, P1, "img:fig.png", P2)
    t_img = session.image_time(1)
    play_to(reader, player, t_img + 0.3)
    assert reader.image == "fig.png"
    play_to(reader, player, t_img + IMAGE_SECONDS + 0.5)
    assert reader.image is None


def test_R5_atravessar_a_imagem_com_um_pulo_nao_mostra(tmp_path, lib):
    reader, player, session, *_ = build(tmp_path, lib, P1, "img:fig.png", P2)
    t_img = session.image_time(1)
    reader.seek(t_img + 5.0)
    play_to(reader, player, t_img + 6.0)
    assert reader.image is None


def test_R5_pulo_externo_por_cima_da_imagem_nao_mostra(tmp_path, lib):
    reader, player, session, *_ = build(tmp_path, lib, P1, "img:fig.png", P2)
    t_img = session.image_time(1)
    play_to(reader, player, t_img - 1.0)
    player.time_pos = t_img + 5.0          # pulo feito pelo próprio tocador
    reader.tick()
    assert reader.image is None


@pytest.mark.parametrize("jump", [-10.0, -300.0, +30.0])
def test_R5_pulo_pelo_leitor_esconde_a_imagem(tmp_path, lib, jump):
    reader, player, session, *_ = build(tmp_path, lib, P1, "img:fig.png", P2)
    play_to(reader, player, session.image_time(1) + 0.3)
    assert reader.image == "fig.png"
    reader.skip(jump)
    assert reader.image is None


def test_R5_pulo_pelo_tocador_esconde_a_imagem(tmp_path, lib):
    reader, player, session, *_ = build(tmp_path, lib, P1, "img:fig.png", P2)
    t_img = session.image_time(1)
    play_to(reader, player, t_img + 0.3)
    player.time_pos = t_img - 20.0
    reader.tick()
    assert reader.image is None


def test_R5_clicar_numa_palavra_esconde_a_imagem(tmp_path, lib):
    reader, player, session, *_ = build(tmp_path, lib, P1, "img:fig.png", P2)
    play_to(reader, player, session.image_time(1) + 0.3)
    reader.seek_word(0, 0)
    assert reader.image is None


def test_R5_pausado_a_imagem_continua(tmp_path, lib):
    reader, player, session, *_ = build(tmp_path, lib, P1, "img:fig.png", P2)
    play_to(reader, player, session.image_time(1) + 0.3)
    player.pause = True
    for _ in range(100):                   # muitos ticks sem o tempo andar
        reader.tick()
    assert reader.image == "fig.png"


def test_R5_fechar_a_imagem(tmp_path, lib):
    reader, player, session, *_ = build(tmp_path, lib, P1, "img:fig.png", P2)
    play_to(reader, player, session.image_time(1) + 0.3)
    reader.dismiss_image()
    assert reader.image is None


# ---------------------------------------------------------------- R6

def test_R6_karaoke_no_paragrafo_atual(tmp_path, lib):
    reader, player, *_, tr = build(tmp_path, lib, P1, P2)
    player.time_pos = tr[3]["s"] + 0.1
    reader.tick()
    assert reader.current_row == 0
    styles = reader.word_styles(0)
    assert styles[:3] == ["past"] * 3
    assert styles[3] == "now"
    assert set(styles[4:]) == {"future"}


def test_R6_outros_paragrafos_esmaecidos_e_pulados_mais_ainda(tmp_path, lib):
    junk = "thank you for downloading this ebook join our mailing list for more offers today"
    reader, player, *_ = build(tmp_path, lib, P1, junk, P2,
                                        transcript=narrate(P1, P2))  # propaganda não lida
    player.time_pos = 1.0
    reader.tick()
    assert set(reader.word_styles(2)) == {"other"}
    assert set(reader.word_styles(1)) == {"skipped"}


def test_R6_html_do_paragrafo_tem_um_link_por_palavra(tmp_path, lib):
    reader, *_ = build(tmp_path, lib, "hello <world> & friends")
    html = reader.block_html(0)
    assert html.count("<a ") == 4
    assert 'href="0:1"' in html and "&lt;world&gt;" in html and "&amp;" in html


def test_R6_posicao_da_palavra_atual_em_caracteres(tmp_path, lib):
    reader, player, *_ = build(tmp_path, lib, "Hello, big world today", transcript=None)
    player.time_pos = 0.85                 # 3ª palavra ("world") começa em 0,8 s
    reader.tick()
    text = "Hello, big world today"
    assert reader.current_char_offset() == text.index("world")


def test_R6_sem_palavra_atual_a_posicao_e_zero(tmp_path, lib):
    reader, *_ = build(tmp_path, lib, P1, transcript=narrate(5.0, P1))
    assert reader.current_word is None
    assert reader.current_char_offset() == 0


# ---------------------------------------------------------------- R7

def test_R7_avisa_o_worker_a_cada_5s_e_logo_apos_um_pulo(tmp_path, lib, monkeypatch):
    reader, player, session, *_ = build(tmp_path, lib, P1, duration=600.0)
    sent = []
    monkeypatch.setattr(session, "update_playhead", sent.append)
    play_to(reader, player, 12.0)
    assert [round(t) for t in sent] == [5, 10]
    reader.seek(300.0)
    assert sent[-1] == 300.0
    player.time_pos = 400.0                # pulo feito fora do leitor (ex.: pelo mpv)
    reader.tick()
    assert sent[-1] == 400.0


# ---------------------------------------------------------------- R8

def test_R8_preferencias_sao_salvas_e_restauradas(tmp_path, lib):
    reader, player, session, *_ = build(tmp_path, lib, P1)
    defaults = dict(reader.prefs)
    assert {"font_size", "bg_opacity", "locked", "click_through", "geometry"} <= set(defaults)
    reader.set_pref("font_size", 30)
    reader.set_pref("bg_opacity", 0.2)
    reader.set_pref("locked", True)
    reader.set_pref("click_through", True)
    reader.set_pref("geometry", [10, 20, 800, 300])
    again = Reader(session, FakePlayer(120.0), Library(), reader.bid)
    assert again.prefs["font_size"] == 30
    assert again.prefs["bg_opacity"] == 0.2
    assert again.prefs["locked"] is True
    assert again.prefs["click_through"] is True
    assert again.prefs["geometry"] == [10, 20, 800, 300]


def test_R9_livro_novo_comeca_do_zero_sem_pular(tmp_path, lib):
    reader, player, *_ = build(tmp_path, lib, P1)
    assert player.seeks == []
    assert reader.position == 0.0


def test_R8_limites_das_preferencias(tmp_path, lib):
    reader, *_ = build(tmp_path, lib, P1)
    reader.set_pref("font_size", 500)
    reader.set_pref("bg_opacity", -1)
    assert reader.prefs["font_size"] == 64
    assert reader.prefs["bg_opacity"] == 0.0


# ---------------------------------------------------------------- R9

def test_R9_leitor_salva_ao_fechar_e_recomeca_dali(tmp_path, lib):
    reader, player, session, *_ = build(tmp_path, lib, P1)
    player.time_pos = 42.0
    reader.tick()
    reader.close()
    again = Reader(session, FakePlayer(120.0), Library(), reader.bid)
    assert again.player.seeks == [42.0]
    assert again.position == 42.0


# ---------------------------------------------------------------- R10

def test_R10_solta_e_janela_comum(tmp_path, lib):
    reader, *_ = build(tmp_path, lib, P1)
    assert reader.window_mode() == {"on_top": False, "click_through": False}


def test_R10_fixa_fica_por_cima(tmp_path, lib):
    reader, *_ = build(tmp_path, lib, P1)
    reader.toggle_lock()
    assert reader.window_mode() == {"on_top": True, "click_through": False}


def test_R10_cliques_so_atravessam_quando_fixa(tmp_path, lib):
    reader, *_ = build(tmp_path, lib, P1)
    reader.set_pref("click_through", True)
    assert reader.window_mode()["click_through"] is False
    reader.toggle_lock()
    assert reader.window_mode() == {"on_top": True, "click_through": True}


def test_R10_soltar_desliga_o_atravessar(tmp_path, lib):
    reader, *_ = build(tmp_path, lib, P1)
    reader.toggle_lock()
    reader.set_pref("click_through", True)
    reader.toggle_lock()
    assert reader.prefs["click_through"] is False
    assert reader.window_mode() == {"on_top": False, "click_through": False}



# ---------------------------------------------------------------- R8 (texto)

def test_R8_cor_e_opacidade_do_texto_sao_salvas_e_restauradas(tmp_path, lib):
    reader, player, session, *_ = build(tmp_path, lib, P1)
    assert {"text_color", "text_opacity"} <= set(reader.prefs)
    reader.set_pref("text_color", "#a0d8ff")
    reader.set_pref("text_opacity", 0.7)
    again = Reader(session, FakePlayer(120.0), Library(), reader.bid)
    assert again.prefs["text_color"] == "#a0d8ff"
    assert again.prefs["text_opacity"] == 0.7


def test_R8_limites_da_opacidade_do_texto(tmp_path, lib):
    reader, *_ = build(tmp_path, lib, P1)
    reader.set_pref("text_opacity", 0.0)
    assert reader.prefs["text_opacity"] == 0.2
    reader.set_pref("text_opacity", 3)
    assert reader.prefs["text_opacity"] == 1.0


@pytest.mark.parametrize("bad", ["vermelho", "#12345", "#gggggg", "", None, "123456"])
def test_R8_cor_invalida_e_ignorada(tmp_path, lib, bad):
    reader, *_ = build(tmp_path, lib, P1)
    reader.set_pref("text_color", "#a0d8ff")
    reader.set_pref("text_color", bad)
    assert reader.prefs["text_color"] == "#a0d8ff"


def test_R8_cor_e_opacidade_aparecem_no_texto(tmp_path, lib):
    reader, player, *_, tr = build(tmp_path, lib, P1)
    reader.set_pref("text_color", "#a0d8ff")
    reader.set_pref("text_opacity", 0.5)
    player.time_pos = tr[3]["s"] + 0.1
    reader.tick()
    html = reader.block_html(0)
    # palavra já dita: opacidade cheia do karaokê × 0,5 escolhida = 0x7f, na cor escolhida
    assert 'style="color:#7fa0d8ff' in html
    # palavra futura: 0,5 do karaokê × 0,5 = 0,25 -> 0x3f
    assert 'color:#3fa0d8ff' in html


# ---------------------------------------------------------------- R11

def test_R11_fechar_pausa_o_audio(tmp_path, lib):
    reader, player, *_ = build(tmp_path, lib, P1)
    assert player.pause is False
    reader.close()
    assert player.pause is True


def test_R11_pausa_vem_antes_de_salvar(tmp_path, lib, monkeypatch):
    reader, player, *_ = build(tmp_path, lib, P1)
    order = []
    monkeypatch.setattr(lib, "set_position", lambda *a: order.append(("salvou", player.pause)))
    reader.close()
    assert order == [("salvou", True)]


def test_R9_salvar_a_posicao_periodicamente_nao_pausa(tmp_path, lib):
    reader, player, *_ = build(tmp_path, lib, P1)
    player.time_pos = 42.0
    reader.save()
    assert player.pause is False
    assert Library().data["books"][reader.bid]["position"] == 42.0


# ---------------------------------------------------------------- R8 (fundo)

def test_R8_cor_do_fundo_salva_e_validada(tmp_path, lib):
    reader, player, session, *_ = build(tmp_path, lib, P1)
    assert reader.prefs["bg_color"] == "#15131f"
    reader.set_pref("bg_color", "#203040")
    reader.set_pref("bg_color", "azul")              # inválida: ignorada
    again = Reader(session, FakePlayer(120.0), Library(), reader.bid)
    assert again.prefs["bg_color"] == "#203040"


# ---------------------------------------------------------------- R12

def make_png(path, w=8, h=6):
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QGuiApplication, QImage
    QGuiApplication.instance() or QGuiApplication([])
    path.parent.mkdir(parents=True, exist_ok=True)
    QImage(w, h, QImage.Format_RGB32).save(str(path))
    return path


def test_R12_imagem_e_copiada_e_sobrevive_ao_original_sumir(tmp_path, lib):
    reader, player, session, *_ = build(tmp_path, lib, P1)
    original = make_png(tmp_path / "fotos" / "praia.png")
    assert reader.set_background_image(str(original)) is True
    saved = reader.prefs["bg_image"]
    assert saved and saved != str(original)
    assert "backgrounds" in saved
    original.unlink()
    again = Reader(session, FakePlayer(120.0), Library(), reader.bid)
    from pathlib import Path
    assert again.prefs["bg_image"] == saved and Path(saved).exists()


@pytest.mark.parametrize("bad", ["nao-existe.png", "texto.txt"])
def test_R12_arquivo_invalido_e_ignorado(tmp_path, lib, bad):
    reader, *_ = build(tmp_path, lib, P1)
    good = make_png(tmp_path / "boa.png")
    reader.set_background_image(str(good))
    before = reader.prefs["bg_image"]
    (tmp_path / "texto.txt").write_text("não sou imagem")
    assert reader.set_background_image(str(tmp_path / bad)) is False
    assert reader.prefs["bg_image"] == before


def test_R12_remover_volta_para_a_cor(tmp_path, lib):
    reader, *_ = build(tmp_path, lib, P1)
    reader.set_background_image(str(make_png(tmp_path / "boa.png")))
    reader.set_background_image("")
    assert reader.prefs["bg_image"] == ""


def test_R12_mesmo_nome_de_arquivos_diferentes_nao_se_sobrescrevem(tmp_path, lib):
    reader, *_ = build(tmp_path, lib, P1)
    a = make_png(tmp_path / "a" / "fundo.png", 8, 6)
    b = make_png(tmp_path / "b" / "fundo.png", 16, 4)
    reader.set_background_image(str(a))
    first = reader.prefs["bg_image"]
    reader.set_background_image(str(b))
    from pathlib import Path
    assert reader.prefs["bg_image"] != first
    assert Path(first).exists()


# ---------------------------------------------------------------- R13

COMMENT = "a woman wrote that she was proud of her messy house and then I got this comment:"
AFTER = "there it was the word that had haunted me for so much of my life as a messy woman"


def lazy_reader(tmp_path, lib):
    tr = narrate(COMMENT, "very lazy.", AFTER)
    reader, player, session, book, _ = build(tmp_path, lib, COMMENT, "img:c.png", AFTER, transcript=tr)
    very = next(w for w in tr if w["w"] == "very")
    lazy = next(w for w in tr if w["w"] == "lazy.")
    return reader, player, very, lazy


def test_R13_texto_do_audio_so_aparece_quando_a_narracao_chega(tmp_path, lib):
    reader, player, very, lazy = lazy_reader(tmp_path, lib)
    play_to(reader, player, very["s"] - 1.0)
    assert "lazy." not in reader.block_html(0)
    play_to(reader, player, very["s"] + 0.05)
    html = reader.block_html(0)
    assert "<i" in html and "lazy." in html and "♪" in html


def test_R13_karaoke_e_paragrafo_atual_durante_o_texto_do_audio(tmp_path, lib):
    reader, player, very, lazy = lazy_reader(tmp_path, lib)
    play_to(reader, player, lazy["s"] + 0.05)
    assert reader.current_row == 0
    assert reader.current_extra == (0, 1)
    html = reader.block_html(0)
    very_html = html[html.index(">very<") - 60:html.index(">very<")]
    lazy_html = html[html.index(">lazy.<") - 60:html.index(">lazy.<")]
    assert "#ff" in very_html and "#ff" in lazy_html      # já dita e atual: opacidade cheia


def test_R13_palavra_futura_do_trecho_fica_esmaecida(tmp_path, lib):
    reader, player, very, lazy = lazy_reader(tmp_path, lib)
    play_to(reader, player, very["s"] + 0.05)
    html = reader.block_html(0)
    lazy_html = html[html.index(">lazy.<") - 60:html.index(">lazy.<")]
    assert "#7f" in lazy_html                              # futura: metade da opacidade


def test_R13_clicar_numa_palavra_do_audio_pula_para_ela(tmp_path, lib):
    reader, player, very, lazy = lazy_reader(tmp_path, lib)
    play_to(reader, player, lazy["e"] + 0.5)
    reader.seek_link("x0:1")
    assert player.time_pos == pytest.approx(lazy["s"], abs=0.06)


def test_R13_posicao_da_palavra_atual_dentro_do_texto_do_audio(tmp_path, lib):
    reader, player, very, lazy = lazy_reader(tmp_path, lib)
    play_to(reader, player, lazy["s"] + 0.05)
    plain = COMMENT + "\n" + "♪ very lazy."
    assert reader.current_char_offset() == plain.index("lazy.")


# ---------------------------------------------------------------- R14

def test_R14_imagem_recente_e_a_ultima_que_a_narracao_passou(tmp_path, lib):
    reader, player, session, *_ = build(tmp_path, lib, P1, "img:a.png", P2, "img:b.png", P3)
    assert reader.recent_image() is None
    play_to(reader, player, session.image_time(1) + 0.5)
    assert reader.recent_image() == "a.png"
    play_to(reader, player, session.image_time(3) - 1.0)
    assert reader.recent_image() == "a.png"            # continua até a próxima
    play_to(reader, player, session.image_time(3) + 0.5)
    assert reader.recent_image() == "b.png"


def test_R14_voltar_para_antes_da_imagem_volta_a_anterior(tmp_path, lib):
    reader, player, session, *_ = build(tmp_path, lib, P1, "img:a.png", P2, "img:b.png", P3)
    play_to(reader, player, session.image_time(3) + 0.5)
    reader.seek(session.image_time(3) - 2.0)
    assert reader.recent_image() == "a.png"
    reader.seek(0.0)
    assert reader.recent_image() is None


def test_R14_outro_capitulo_nao_herda_a_imagem(tmp_path, lib):
    from tests.helpers import make_book as mb
    book = mb(P1, "img:a.png", P2)
    book["chapters"].append({"index": 1, "href": "c2.xhtml", "title": "C2", "blocks": [
        {"id": 3, "kind": "p", "text": P3,
         "words": [{"t": t, "n": [t], "id": 1000 + i} for i, t in enumerate(P3.split())]}]})
    # renumera as palavras do capítulo 2 em sequência
    nxt = sum(len(b["words"]) for b in book["chapters"][0]["blocks"])
    for i, w in enumerate(book["chapters"][1]["blocks"][0]["words"]):
        w["id"] = nxt + i
    bid, _ = lib.resolve([str(tmp_path / "l.epub"), str(tmp_path / "l.m4b")])
    session = Session(book, lib.cache(bid), duration=120.0, audio_chapters=[])
    session.handle({"type": "segment", "seg": {"s": 0.0, "e": 120.0, "words": narrate(P1, P2, 1.0, P3)}})
    player = FakePlayer(120.0)
    reader = Reader(session, player, lib, bid)
    play_to(reader, player, session.image_time(1) + 0.5)
    assert reader.recent_image() == "a.png"
    p3_start = session.block_start(session.blocks[3])
    play_to(reader, player, p3_start + 0.5)
    assert reader.recent_image() is None


def test_R14_imagem_em_secao_propria_pertence_ao_capitulo_anterior(tmp_path, lib):
    """No EPUB real, a ilustração do capítulo 4 fica numa seção só dela (ch04a)."""
    from tests.helpers import make_book as mb
    book = mb(P1, P2)
    nxt_block = len(book["chapters"][0]["blocks"])
    book["chapters"].append({"index": 1, "href": "ch04a.xhtml", "title": "ch04a", "blocks": [
        {"id": nxt_block, "kind": "img", "src": "fig.png", "alt": "", "words": []}]})
    bid, _ = lib.resolve([str(tmp_path / "l.epub"), str(tmp_path / "l.m4b")])
    session = Session(book, lib.cache(bid), duration=120.0, audio_chapters=[])
    session.handle({"type": "segment", "seg": {"s": 0.0, "e": 120.0, "words": narrate(P1, P2)}})
    player = FakePlayer(120.0)
    reader = Reader(session, player, lib, bid)
    play_to(reader, player, session.image_time(nxt_block) + 0.5)
    assert reader.recent_image() == "fig.png"

