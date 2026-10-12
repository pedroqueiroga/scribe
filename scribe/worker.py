"""Transcrição em streaming — specs/worker.md.

`plan_chunk` e `cut_words` decidem o que transcrever e onde cortar;
`transcribe_loop` é o laço, com o reconhecedor injetado; `run` liga o laço ao
faster-whisper e às filas de comunicação com a interface.

Mensagens recebidas: {"playhead": t} | {"stop": True}
Mensagens enviadas:  {"type": "ready"} | {"type": "segment", "seg": {...}}
                     | {"type": "done"} | {"type": "error", "msg": str}
"""
from __future__ import annotations

import os
import queue
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

URGENT_CHUNK = 7.0       # W1
NORMAL_CHUNK = 24.0      # W1
URGENT_BEFORE = 1.0      # W1: até 1 s antes do playhead…
URGENT_AFTER = 3.0       # …até 3 s depois
OVERLAP = 2.0            # W3
EDGE_TOLERANCE = 0.15    # W4
MIN_ADVANCE = 0.3        # W4, W5
MOVE_THRESHOLD = 1.5     # W6: mudança de playhead que conta como pulo
INTERRUPT_MARGIN = 2.0   # W6: pulo dentro do pedaço atual (com margem) não interrompe


@dataclass
class Chunk:
    start: float
    end: float          # fim planejado
    clip_end: float     # fim do áudio efetivamente transcrito (com folga)
    urgent: bool
    hard_end: bool      # encosta em trecho transcrito ou no fim do áudio
    fill_only: bool     # sobra minúscula: só marcar como coberta


def plan_chunk(start: float, playhead: float, duration: float,
               intervals: list[list[float]]) -> Chunk:
    urgent = playhead - URGENT_BEFORE <= start < playhead + URGENT_AFTER
    end = start + (URGENT_CHUNK if urgent else NORMAL_CHUNK)
    hard = False
    nxt = next((a for a, _ in intervals if a > start + 0.05), None)
    if nxt is not None and nxt <= end:
        end, hard = nxt, True
    if end >= duration:
        end, hard = duration, True
    clip_end = end if hard else min(end + OVERLAP, duration)
    return Chunk(start, end, clip_end, urgent, hard, end - start < MIN_ADVANCE)


def cut_words(words: list[dict], end: float, hard: bool,
              start: float | None = None) -> tuple[list[dict], float]:
    """Palavras que ficam no pedaço e o fim real do pedaço (W4)."""
    if hard:
        return [w for w in words if w["s"] < end], end
    kept: list[dict] = []
    seg_end = end
    for w in words:
        if w["e"] <= end + EDGE_TOLERANCE:
            kept.append(w)
        else:
            if w["s"] < end:
                seg_end = w["s"]
            break
    if start is not None and seg_end < start + MIN_ADVANCE:
        # não avançaria: aceita o corte duro
        return [w for w in words if w["s"] < end], end
    return kept, seg_end


def _focus_elsewhere(store, duration: float, playhead: float, c: Chunk) -> bool:
    """W6: o trecho mais útil para a nova posição deixou de ser o pedaço em andamento?"""
    if c.start - INTERRUPT_MARGIN <= playhead <= c.clip_end:
        return False
    nxt = store.next_gap(playhead, duration)
    return nxt is None or abs(nxt - c.start) > 0.01


TranscribeFn = Callable[[float, float, bool], Iterable[list[dict]]]


def transcribe_loop(store, duration: float, get_cmds: Callable[[], list[dict]],
                    transcribe: TranscribeFn, emit: Callable[[dict], None],
                    max_chunks: int | None = None):
    """Transcreve até cobrir o áudio todo (W7) ou receber stop (W8).
    `transcribe(start, clip_end, urgent)` produz listas de palavras com tempos absolutos."""
    st = {"playhead": 0.0, "moved": False, "stop": False}

    def apply_cmds():
        for msg in get_cmds():
            if msg.get("stop"):
                st["stop"] = True
            if "playhead" in msg:
                if abs(msg["playhead"] - st["playhead"]) > MOVE_THRESHOLD:
                    st["moved"] = True
                st["playhead"] = msg["playhead"]

    done_chunks = 0
    while True:
        apply_cmds()
        if st["stop"]:
            return
        start = store.next_gap(st["playhead"], duration)
        if start is None:
            emit({"type": "done"})
            return
        c = plan_chunk(start, st["playhead"], duration, store.intervals)
        if c.fill_only:
            seg = {"s": c.start, "e": c.end, "words": []}
            store.add(seg)
            emit({"type": "segment", "seg": seg})
            continue

        st["moved"] = False
        words: list[dict] = []
        interrupted = False
        for part in transcribe(c.start, c.clip_end, c.urgent):
            words.extend(part)
            apply_cmds()
            if st["stop"]:
                return
            if st["moved"] and _focus_elsewhere(store, duration, st["playhead"], c):   # W6
                interrupted = True
                break

        if interrupted:
            if not words:
                continue
            kept, seg_end = words, words[-1]["e"]
        else:
            kept, seg_end = cut_words(words, c.end, c.hard_end, start=c.start)
        seg = {"s": round(c.start, 3), "e": round(seg_end, 3),
               "words": [w for w in kept if w["s"] < seg_end + 0.01]}
        store.add(seg)
        emit({"type": "segment", "seg": seg})
        done_chunks += 1
        if max_chunks is not None and done_chunks >= max_chunks:
            return


# ---------------------------------------------------------------- processo real

def run(audio_path: str, cache: str, language: str | None, model_size: str, cmd_q, out_q):
    try:
        _run(audio_path, Path(cache), language, model_size, cmd_q, out_q)
    except Exception:
        out_q.put({"type": "error", "msg": traceback.format_exc()})


def make_whisper(audio_path: str, language: str | None, model_size: str,
                 on_ready: Callable[[], None] | None = None) -> TranscribeFn:
    """Reconhecedor real (faster-whisper), carregado na primeira chamada."""
    from . import audio
    model = None

    def whisper(start, clip_end, urgent):
        nonlocal model
        if model is None:
            # J11: o tqdm (usado pelo huggingface_hub ao achar o modelo) criaria uma trava de
            # multiprocessing que vaza quando o worker é encerrado; uma trava de thread basta
            import threading
            from tqdm import tqdm
            tqdm.set_lock(threading.RLock())
            from faster_whisper import WhisperModel
            threads = max(2, (os.cpu_count() or 4) - 2)
            model = WhisperModel(model_size, device="cpu", compute_type="int8",
                                 cpu_threads=threads)
            if on_ready:
                on_ready()
        samples = audio.load_segment(audio_path, start, clip_end)
        segments, _ = model.transcribe(
            samples, language=language, word_timestamps=True, vad_filter=True,
            condition_on_previous_text=False, beam_size=1 if urgent else 5)
        for seg in segments:
            yield [{"w": w.word.strip(), "s": round(start + w.start, 3),
                    "e": round(start + w.end, 3), "p": round(w.probability, 3)}
                   for w in seg.words or []]

    return whisper


def _run(audio_path, cache, language, model_size, cmd_q, out_q):
    from . import audio
    from .store import TranscriptStore

    os.nice(5)  # não disputar CPU com o áudio e a interface
    store = TranscriptStore(cache)
    duration = float(audio.probe(audio_path)["format"]["duration"])

    def get_cmds():
        out = []
        while True:
            try:
                out.append(cmd_q.get_nowait())
            except queue.Empty:
                return out

    whisper = make_whisper(audio_path, language, model_size,
                           on_ready=lambda: out_q.put({"type": "ready"}))
    transcribe_loop(store, duration, get_cmds, whisper, out_q.put)
