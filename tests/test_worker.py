"""Transcrição em streaming — specs/worker.md (W1–W7).

As decisões do worker são funções puras e o laço recebe o "Whisper" injetado,
então nada aqui roda modelo de verdade.
"""
from __future__ import annotations

import pytest

from scribe.store import TranscriptStore
from scribe.worker import cut_words, plan_chunk, transcribe_loop, watch_parent

DURATION = 300.0


def w(text, s, e):
    return {"w": text, "s": s, "e": e, "p": 1.0}


# ---------------------------------------------------------------- W1

@pytest.mark.parametrize("start,playhead", [(10.0, 10.0), (10.0, 11.0), (12.9, 10.0)])
def test_W1_perto_do_playhead_o_pedaco_e_urgente_e_curto(start, playhead):
    c = plan_chunk(start, playhead, DURATION, intervals=[])
    assert c.urgent
    assert c.end == pytest.approx(start + 7.0)


@pytest.mark.parametrize("start,playhead", [(40.0, 10.0), (13.1, 10.0), (5.0, 10.0)])
def test_W1_longe_do_playhead_o_pedaco_e_normal(start, playhead):
    c = plan_chunk(start, playhead, DURATION, intervals=[])
    assert not c.urgent
    assert c.end == pytest.approx(start + 24.0)


# ---------------------------------------------------------------- W2

def test_W2_pedaco_para_antes_de_trecho_ja_transcrito():
    c = plan_chunk(40.0, 0.0, DURATION, intervals=[[0.0, 40.0], [50.0, 80.0]])
    assert c.end == 50.0


def test_W2_pedaco_nao_passa_do_fim_do_audio():
    c = plan_chunk(290.0, 0.0, DURATION, intervals=[])
    assert c.end == DURATION


# ---------------------------------------------------------------- W3

def test_W3_folga_de_2s_alem_do_fim_planejado():
    c = plan_chunk(100.0, 0.0, DURATION, intervals=[])
    assert c.clip_end == pytest.approx(c.end + 2.0)


def test_W3_sem_folga_quando_encosta_em_trecho_transcrito():
    c = plan_chunk(40.0, 0.0, DURATION, intervals=[[50.0, 80.0]])
    assert c.clip_end == c.end == 50.0


def test_W3_sem_folga_no_fim_do_audio():
    c = plan_chunk(290.0, 0.0, DURATION, intervals=[])
    assert c.clip_end == c.end == DURATION


# ---------------------------------------------------------------- W4

def test_W4_palavras_ate_a_borda_ficam_com_tolerancia():
    words = [w("a", 10.0, 10.5), w("b", 19.0, 20.1), w("c", 20.3, 20.8)]
    kept, end = cut_words(words, 20.0, hard=False)
    assert [x["w"] for x in kept] == ["a", "b"]   # "b" termina 0,1 s depois: tolerado
    assert end == 20.0


def test_W4_palavra_atravessando_a_borda_encurta_o_pedaco():
    words = [w("a", 10.0, 10.5), w("longa", 19.6, 20.6), w("c", 20.7, 21.0)]
    kept, end = cut_words(words, 20.0, hard=False)
    assert [x["w"] for x in kept] == ["a"]
    assert end == 19.6                             # o próximo pedaço começa em "longa"


def test_W4_com_borda_firme_fica_tudo_que_comeca_antes_dela():
    words = [w("a", 10.0, 10.5), w("b", 19.8, 20.2)]
    kept, end = cut_words(words, 20.0, hard=True)
    assert [x["w"] for x in kept] == ["a", "b"]
    assert end == 20.0


def test_W4_pedaco_sempre_avanca_mesmo_com_palavra_na_borda_inicial():
    # uma palavra enorme que começa no início do pedaço e passa da borda
    words = [w("aaaa", 10.0, 21.0)]
    kept, end = cut_words(words, 20.0, hard=False, start=10.0)
    assert end >= 10.3


# ---------------------------------------------------------------- W5

def test_W5_sobra_minuscula_so_e_marcada_como_coberta():
    c = plan_chunk(49.8, 0.0, DURATION, intervals=[[0.0, 49.8], [50.0, 80.0]])
    assert c.fill_only


def test_W5_sobra_normal_nao_e_fill_only():
    c = plan_chunk(40.0, 0.0, DURATION, intervals=[[50.0, 80.0]])
    assert not c.fill_only


# ---------------------------------------------------------------- laço (W6, W7)

class FakeWhisper:
    """Devolve uma palavra por segundo; registra o que foi pedido."""

    def __init__(self, on_segment=None):
        self.calls = []
        self.on_segment = on_segment

    def __call__(self, start, clip_end, urgent):
        self.calls.append((start, clip_end, urgent))
        t = start
        while t + 0.5 <= clip_end:
            if self.on_segment:
                self.on_segment(t)
            yield [w(f"w{t:.0f}", t, t + 0.5)]
            t += 1.0


class Commands:
    """Fila de comandos controlada pelo teste."""

    def __init__(self, playhead=0.0):
        self.playhead = playhead
        self.pending: list[dict] = [{"playhead": playhead}]

    def send(self, **msg):
        self.pending.append(msg)

    def __call__(self):
        out, self.pending = self.pending, []
        return out


def test_W7_transcreve_tudo_e_avisa_o_fim(tmp_path):
    store = TranscriptStore(tmp_path)
    events = []
    transcribe_loop(store, 60.0, Commands(0.0), FakeWhisper(), events.append)
    assert store.complete(60.0)
    assert events[-1] == {"type": "done"}
    assert all(e["type"] == "segment" for e in events[:-1])


def test_W7_retoma_so_o_que_falta_ao_reabrir(tmp_path):
    TranscriptStore(tmp_path).add({"s": 0.0, "e": 40.0, "words": []})
    fake = FakeWhisper()
    transcribe_loop(TranscriptStore(tmp_path), 60.0, Commands(0.0), fake, lambda e: None)
    assert fake.calls and all(start >= 40.0 for start, _, _ in fake.calls)


def test_W7_nada_a_fazer_avisa_o_fim_sem_transcrever(tmp_path):
    TranscriptStore(tmp_path).add({"s": 0.0, "e": 60.0, "words": []})
    fake = FakeWhisper()
    events = []
    transcribe_loop(TranscriptStore(tmp_path), 60.0, Commands(0.0), fake, events.append)
    assert fake.calls == [] and events == [{"type": "done"}]


def test_W1_primeiro_pedaco_comeca_no_playhead_e_e_urgente(tmp_path):
    fake = FakeWhisper()
    transcribe_loop(TranscriptStore(tmp_path), 300.0, Commands(120.0), fake, lambda e: None)
    start, _, urgent = fake.calls[0]
    assert start == 120.0 and urgent


def test_W6_pulo_para_longe_salva_o_parcial_e_muda_o_foco(tmp_path):
    store = TranscriptStore(tmp_path)
    cmds = Commands(0.0)
    jumped = []

    def on_segment(t):
        # durante o 2º pedaço (normal, 7–31 s), a pessoa pula para 200 s
        if 10.0 <= t and not jumped:
            jumped.append(t)
            cmds.send(playhead=200.0)

    fake = FakeWhisper(on_segment)
    events = []
    transcribe_loop(store, 300.0, cmds, fake, events.append, max_chunks=3)
    starts = [c[0] for c in fake.calls]
    assert starts[2] == 200.0                     # o 3º pedaço já é na nova posição
    partial = events[1]["seg"]
    assert partial["s"] == 7.0 and partial["e"] < 31.0   # parcial salvo
    assert store.covers(7.0, partial["e"])


def test_W6_pulo_dentro_do_pedaco_atual_nao_interrompe(tmp_path):
    cmds = Commands(0.0)

    def on_segment(t):
        if t == 10.0:
            cmds.send(playhead=12.0)

    fake = FakeWhisper(on_segment)
    events = []
    transcribe_loop(TranscriptStore(tmp_path), 300.0, cmds, fake, events.append, max_chunks=2)
    assert events[1]["seg"]["e"] == pytest.approx(31.0)


def test_W6_reproducao_normal_atras_do_pedaco_nao_interrompe(tmp_path):
    # pedaços: [0,7] urgente, [7,31], [31,55]; durante o 3º, a escuta avança de 20 para 25 s
    cmds = Commands(0.0)

    def on_segment(t):
        if t == 35.0:
            cmds.send(playhead=20.0)
        if t == 40.0:
            cmds.send(playhead=25.0)

    events = []
    transcribe_loop(TranscriptStore(tmp_path), 300.0, cmds, FakeWhisper(on_segment),
                    events.append, max_chunks=3)
    assert events[2]["seg"]["s"] == 31.0
    assert events[2]["seg"]["e"] == pytest.approx(55.0)


def test_W6_pulo_para_tras_num_trecho_ja_transcrito_nao_interrompe(tmp_path):
    store = TranscriptStore(tmp_path)
    store.add({"s": 0.0, "e": 100.0, "words": []})
    cmds = Commands(90.0)

    def on_segment(t):
        if t == 105.0:
            cmds.send(playhead=10.0)       # volta para um trecho pronto e contíguo ao pedaço

    events = []
    transcribe_loop(store, 300.0, cmds, FakeWhisper(on_segment), events.append, max_chunks=1)
    assert events[0]["seg"]["e"] == pytest.approx(124.0)


def test_W6_pulo_para_tras_num_buraco_interrompe(tmp_path):
    store = TranscriptStore(tmp_path)
    store.add({"s": 50.0, "e": 100.0, "words": []})
    cmds = Commands(90.0)

    def on_segment(t):
        if t == 105.0:
            cmds.send(playhead=10.0)       # 0–50 ainda não foi transcrito

    fake = FakeWhisper(on_segment)
    transcribe_loop(store, 300.0, cmds, fake, lambda e: None, max_chunks=2)
    assert fake.calls[1][0] == 10.0


def test_W8_stop_encerra_o_laco(tmp_path):
    cmds = Commands(0.0)
    cmds.send(stop=True)
    fake = FakeWhisper()
    transcribe_loop(TranscriptStore(tmp_path), 300.0, cmds, fake, lambda e: None)
    assert fake.calls == []


# ---------------------------------------------------------------- W9

def test_W9_pai_morto_vira_pedido_de_parada():
    ppid = [100]
    cmds = watch_parent(lambda: [{"playhead": 3.0}], 100, getppid=lambda: ppid[0])
    assert cmds() == [{"playhead": 3.0}]
    ppid[0] = 1                                        # adotado pelo init: o pai morreu
    assert {"stop": True} in cmds()


def test_W9_orfao_para_no_meio_do_pedaco_sem_salvar(tmp_path):
    ppid = [100]

    def die(t):
        if t >= 3.0:
            ppid[0] = 1
    fake = FakeWhisper(on_segment=die)
    store = TranscriptStore(tmp_path)
    cmds = watch_parent(Commands(0.0), 100, getppid=lambda: ppid[0])
    transcribe_loop(store, 300.0, cmds, fake, lambda e: None)
    assert len(fake.calls) == 1                        # não começou outro pedaço
    assert store.intervals == []                       # nada salvo pela metade


def test_W9_sessao_informa_o_proprio_pid_ao_worker(tmp_path, monkeypatch):
    import os
    import scribe.session as session_mod
    from tests.helpers import make_book
    started = {}

    class FakeProcess:
        def __init__(self, target, daemon, args):
            started["args"] = args

        def start(self):
            pass

    class FakeCtx:
        Queue = staticmethod(lambda: __import__("queue").Queue())
        Process = FakeProcess

    monkeypatch.setattr(session_mod.mp, "get_context", lambda kind: FakeCtx)
    s = session_mod.Session(make_book("uma frase"), tmp_path, 60.0, [], "a.m4b", "small")
    s.start_worker(0.0)
    assert started["args"][-1] == os.getpid()


def test_W9_orfao_real_se_encerra_sozinho(tmp_path):
    import os
    """Um pai de verdade inicia o worker e é morto com SIGKILL; o filho tem de sair."""
    import subprocess
    import sys
    import time
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    flag = tmp_path / "saiu"
    parent = subprocess.Popen(
        [sys.executable, "-c",
         "import multiprocessing as mp, os, sys, time\n"
         "from tests.helpers import orphan_probe\n"
         "if __name__ == '__main__':\n"
         "    p = mp.get_context('spawn').Process(target=orphan_probe,"
         f" args=(os.getpid(), {str(flag)!r}), daemon=True)\n"
         "    p.start(); print(p.pid, flush=True); time.sleep(60)\n"],
        cwd=root, stdout=subprocess.PIPE, text=True)
    child = int(parent.stdout.readline())
    time.sleep(0.5)
    parent.kill()                                      # SIGKILL: sem encerramento limpo
    parent.wait()
    deadline = time.time() + 5
    while time.time() < deadline and not flag.exists():
        time.sleep(0.1)
    try:
        assert flag.read_text() == "parada"
    finally:
        try:
            os.kill(child, 9)
        except ProcessLookupError:
            pass


def test_W9_processo_do_worker_vigia_o_pai(tmp_path, monkeypatch):
    import os
    import queue
    import scribe.audio as audio
    import scribe.worker as worker
    fake = FakeWhisper()
    monkeypatch.setattr(worker.os, "nice", lambda n: 0)
    monkeypatch.setattr(audio, "probe", lambda path: {"format": {"duration": "60"}})
    monkeypatch.setattr(worker, "make_whisper", lambda *a, **k: fake)
    cmd_q, out_q = queue.Queue(), queue.Queue()
    cmd_q.put({"playhead": 0.0})
    worker.run("a.m4b", str(tmp_path), "en", "small", cmd_q, out_q, parent_pid=os.getppid())
    assert fake.calls                                  # pai vivo: transcreveu
    fake.calls.clear()
    worker.run("a.m4b", str(tmp_path / "b"), "en", "small", cmd_q, out_q, parent_pid=-1)
    assert fake.calls == []                            # "pai" que não é o nosso: para logo
