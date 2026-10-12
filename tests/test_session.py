"""Sessão e linha do tempo — specs/session.md (S1–S5)."""
from __future__ import annotations

import pytest

from scribe.align import NARRATED
from scribe.session import Session
from tests.helpers import all_words, make_book, narrate

P1 = ("when you look at a very messy space it is easy to feel overwhelmed "
      "take a few minutes to speak some compassionate words to yourself")
P2 = ("there are actually only five things in any room trash dishes laundry "
      "things that have a place and things that do not have a place")


def segment(words, s=None, e=None):
    return {"s": words[0]["s"] if s is None else s,
            "e": words[-1]["e"] if e is None else e, "words": words}


def new_session(tmp_path, book, duration=600.0):
    return Session(book, tmp_path, duration=duration, audio_chapters=[])


# ---------------------------------------------------------------- S1

def test_S1_palavra_atual_e_a_ultima_que_comecou(tmp_path):
    book = make_book(P1)
    tr = narrate(P1)
    s = new_session(tmp_path, book)
    s.handle({"type": "segment", "seg": segment(tr, s=0.0)})
    words = all_words(book)
    assert s.word_at(tr[3]["s"]) == words[3]["id"]
    assert s.word_at(tr[3]["s"] + 0.35) == words[3]["id"]   # na pausa depois dela
    assert s.word_at(tr[4]["s"]) == words[4]["id"]


def test_S1_antes_da_primeira_palavra_nao_ha_palavra_atual(tmp_path):
    book = make_book(P1)
    tr = narrate(5.0, P1)
    s = new_session(tmp_path, book)
    s.handle({"type": "segment", "seg": segment(tr, s=0.0)})
    assert s.word_at(2.0) is None


# ---------------------------------------------------------------- S2

def test_S2_depois_do_trecho_transcrito_a_palavra_atual_fica_incerta(tmp_path):
    book = make_book(P1, P2)
    tr = narrate(P1)
    s = new_session(tmp_path, book)
    s.handle({"type": "segment", "seg": segment(tr, s=0.0)})
    end = tr[-1]["e"]
    assert s.word_at(end + 3.0) is not None    # até 4 s: ainda é a última palavra
    assert s.word_at(end + 10.0) is None       # além disso, sem transcrição: incerto


def test_S2_silencio_transcrito_nao_e_incerteza(tmp_path):
    book = make_book(P1, P2)
    tr1 = narrate(P1)
    tr2 = narrate(30.0, P2)
    s = new_session(tmp_path, book)
    s.handle({"type": "segment", "seg": segment(tr1 + tr2, s=0.0)})
    # entre P1 e P2 há uma pausa longa, mas o áudio foi transcrito: segue a última palavra
    assert s.word_at(25.0) == all_words(book)[len(P1.split()) - 1]["id"]


# ---------------------------------------------------------------- S3

def test_S3_pedaco_novo_atualiza_tempos_e_versao(tmp_path):
    book = make_book(P1, P2)
    s = new_session(tmp_path, book)
    v0 = s.version
    assert s.word_at(1.0) is None
    s.handle({"type": "segment", "seg": segment(narrate(P1), s=0.0)})
    assert s.version > v0
    assert s.word_at(1.0) is not None
    assert s.store.covers(0.0, 5.0)


def test_S3_sessao_reaberta_ja_tem_os_tempos_do_que_foi_salvo(tmp_path):
    book = make_book(P1)
    first = new_session(tmp_path, book)
    first.store.add(segment(narrate(P1), s=0.0))      # o worker grava em disco
    again = new_session(tmp_path, make_book(P1))
    assert again.word_at(1.0) is not None


# ---------------------------------------------------------------- S4

def test_S4_imagem_aparece_no_fim_do_texto_narrado_anterior(tmp_path):
    book = make_book(P1, "img:fig.png", P2)
    tr = narrate(P1, 2.0, P2)
    s = new_session(tmp_path, book)
    s.handle({"type": "segment", "seg": segment(tr, s=0.0)})
    end_p1 = tr[len(P1.split()) - 1]["e"]
    assert s.image_time(1) == pytest.approx(end_p1)


def test_S4_imagem_sem_texto_narrado_antes_nao_tem_hora(tmp_path):
    book = make_book("img:capa.png", P1)
    s = new_session(tmp_path, book)
    s.handle({"type": "segment", "seg": segment(narrate(P1), s=0.0)})
    assert s.image_time(0) is None


# ---------------------------------------------------------------- S5

def test_S5_fim_da_transcricao_refaz_o_alinhamento_global(tmp_path, monkeypatch):
    book = make_book(P1, P2)
    s = new_session(tmp_path, book)
    s.handle({"type": "segment", "seg": segment(narrate(P1, P2), s=0.0)})
    calls = []
    original = s.aligner.align_all
    monkeypatch.setattr(s.aligner, "align_all", lambda words: (calls.append(len(words)), original(words)))
    s.handle({"type": "done"})
    assert len(calls) == 1
    assert {s.aligner.state[w["id"]] for w in all_words(book)} == {NARRATED}


def test_S5_sem_pedacos_novos_nao_refaz(tmp_path, monkeypatch):
    book = make_book(P1)
    s = new_session(tmp_path, book)
    calls = []
    monkeypatch.setattr(s.aligner, "align_all", lambda words: calls.append(1))
    s.handle({"type": "done"})
    assert calls == []


# ---------------------------------------------------------------- S6

class DeadProcess:
    def is_alive(self):
        return False


class EmptyQueue:
    def get_nowait(self):
        import queue
        raise queue.Empty


def test_S6_worker_que_morre_sem_avisar_vira_erro(tmp_path):
    s = new_session(tmp_path, make_book(P1))
    s.worker_state = "loading"
    s._proc, s._out_q = DeadProcess(), EmptyQueue()
    s.poll()
    assert s.worker_state == "error"


def test_S6_worker_que_terminou_normalmente_nao_e_erro(tmp_path):
    s = new_session(tmp_path, make_book(P1))
    s.worker_state = "done"
    s._proc, s._out_q = DeadProcess(), EmptyQueue()
    s.poll()
    assert s.worker_state == "done"


# ---------------------------------------------------------------- S7

COMMENT = "a woman wrote that she was proud of her messy house and then I got this comment:"
AFTER = "there it was the word that had haunted me for so much of my life as a messy woman"


def test_S7_momento_dentro_do_texto_do_audio(tmp_path):
    book = make_book(COMMENT, "img:c.png", AFTER)
    tr = narrate(COMMENT, "very lazy.", AFTER)
    s = new_session(tmp_path, book)
    s.handle({"type": "segment", "seg": segment(tr, s=0.0)})
    very = next(w for w in tr if w["w"] == "very")
    lazy = next(w for w in tr if w["w"] == "lazy.")
    assert s.extra_at(very["s"] + 0.01) == (0, 0)
    assert s.extra_at(lazy["s"] + 0.01) == (0, 1)
    assert s.extra_at(very["s"] - 0.5) is None          # antes do trecho
    assert s.extra_at(lazy["e"] + 0.5) is None          # depois do trecho
