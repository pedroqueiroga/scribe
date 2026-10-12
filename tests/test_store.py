"""Armazenamento da transcrição — specs/store.md (T1–T6)."""
from __future__ import annotations

import json

import pytest

from scribe.store import TranscriptStore

DURATION = 100.0


def seg(s, e, words=()):
    """Pedaço de s a e; `words` = [(texto, inicio, fim)]."""
    return {"s": s, "e": e, "words": [{"w": w, "s": a, "e": b, "p": 1.0} for w, a, b in words]}


@pytest.fixture
def store(tmp_path):
    return TranscriptStore(tmp_path)


# ---------------------------------------------------------------- T1

def test_T1_pedaco_adicionado_e_gravado_e_relido_por_outro_store(tmp_path):
    a = TranscriptStore(tmp_path)
    a.add(seg(10, 20, [("olá", 10.5, 11.0)]))
    b = TranscriptStore(tmp_path)
    assert b.segments == a.segments
    assert b.words() == [{"w": "olá", "s": 10.5, "e": 11.0, "p": 1.0}]


def test_T1_gravacao_e_atomica_sem_arquivos_temporarios(tmp_path):
    TranscriptStore(tmp_path).add(seg(0, 5))
    files = list((tmp_path / "transcript").iterdir())
    assert len(files) == 1 and files[0].suffix == ".json"


def test_T1_add_sem_gravar_nao_cria_arquivo(tmp_path):
    s = TranscriptStore(tmp_path)
    s.add(seg(0, 5), write=False)
    assert s.covers(0, 5)
    assert list((tmp_path / "transcript").iterdir()) == []


# ---------------------------------------------------------------- T2

def test_T2_pedacos_encostados_ou_sobrepostos_viram_um_intervalo(store):
    store.add(seg(0, 10))
    store.add(seg(10, 20))     # encostado
    store.add(seg(18, 30))     # sobreposto
    store.add(seg(50, 60))     # separado
    assert store.intervals == [[0, 30], [50, 60]]


def test_T2_cobertura_de_instantes_e_intervalos(store):
    store.add(seg(0, 30))
    store.add(seg(50, 60))
    assert store.covers(5, 25)
    assert not store.covers(25, 55)        # atravessa o buraco 30–50
    assert store.covered_until(12) == 30
    assert store.covered_until(40) is None


def test_T2_ordem_de_adicao_nao_importa(store):
    store.add(seg(50, 60))
    store.add(seg(0, 10))
    store.add(seg(10, 50))
    assert store.intervals == [[0, 60]]


# ---------------------------------------------------------------- T3

def test_T3a_posicao_nao_coberta_e_o_proprio_proximo_trecho(store):
    store.add(seg(0, 10))
    assert store.next_gap(42.0, DURATION) == 42.0


def test_T3b_posicao_coberta_continua_do_fim_do_intervalo(store):
    store.add(seg(30, 45))
    assert store.next_gap(35.0, DURATION) == 45


def test_T3c_tudo_pronto_ate_o_fim_preenche_o_primeiro_buraco(store):
    store.add(seg(0, 10))
    store.add(seg(20, 30))
    store.add(seg(60, DURATION))
    assert store.next_gap(70.0, DURATION) == 10


def test_T3c_buraco_no_comeco_do_audio(store):
    store.add(seg(5, DURATION))
    assert store.next_gap(50.0, DURATION) == 0.0


def test_T3_audio_inteiro_coberto_nao_tem_proximo(store):
    store.add(seg(0, 60))
    store.add(seg(60, DURATION))
    assert store.next_gap(10.0, DURATION) is None
    assert store.complete(DURATION)


# ---------------------------------------------------------------- T4

def test_T4_formato_antigo_de_capitulo_e_aceito(tmp_path):
    d = tmp_path / "transcript"
    d.mkdir()
    (d / "003.json").write_text(json.dumps({
        "chapter": {"index": 3, "title": "Cap", "start": 40.0, "end": 77.0},
        "words": [{"w": "how", "s": 40.4, "e": 40.6, "p": 0.9}],
    }))
    s = TranscriptStore(tmp_path)
    assert s.intervals == [[40.0, 77.0]]
    assert [w["w"] for w in s.words()] == ["how"]


# ---------------------------------------------------------------- T5

def test_T5_palavras_ordenadas_e_sem_duplicatas_de_sobreposicao(store):
    store.add(seg(10, 20, [("c", 12.0, 12.4), ("d", 15.0, 15.3)]))
    store.add(seg(0, 13, [("a", 1.0, 1.4), ("b", 5.0, 5.5), ("c", 12.02, 12.4)]))
    assert [w["w"] for w in store.words()] == ["a", "b", "c", "d"]


# ---------------------------------------------------------------- T6

def test_T6_arquivo_corrompido_e_ignorado(tmp_path):
    TranscriptStore(tmp_path).add(seg(0, 10))
    (tmp_path / "transcript" / "0000099999.json").write_text('{"s": 99.9, "e": ')
    s = TranscriptStore(tmp_path)
    assert s.intervals == [[0, 10]]
