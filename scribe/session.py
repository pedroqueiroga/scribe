"""Sessão de leitura: junta livro, transcrição em streaming e alinhamento.

A interface chama `poll()` periodicamente; quando chega um pedaço novo da
transcrição, ele é alinhado localmente e os tempos das palavras são recalculados.
"""
from __future__ import annotations

import bisect
import json
import multiprocessing as mp
import queue
import sys
from pathlib import Path

from . import audio
from .align import NARRATED, SKIPPED, Aligner
from .store import TranscriptStore


def load_book(epub_path: str, cache: Path) -> dict:
    path = cache / "book.json"
    if path.exists():
        return json.loads(path.read_text())
    from . import epub
    print("[epub] extraindo texto…", file=sys.stderr)
    data = epub.extract(epub_path, cache)
    epub.cover_font_files(epub_path, cache / "fonts")
    return data


class Session:
    def __init__(self, book: dict, cache: Path, duration: float, audio_chapters: list[dict],
                 audio_path: str | None = None, model_size: str = "small"):
        self.cache = cache
        self.audio_path = audio_path
        self.book = book
        self.duration = duration
        self.audio_chapters = audio_chapters
        self.store = TranscriptStore(cache)
        self.aligner = Aligner(book)
        self.blocks = self.aligner.blocks
        self.words = self.aligner.words
        self.model_size = model_size
        self.worker_state = "idle"   # idle | loading | running | done | error
        self.version = 0             # incrementa a cada recálculo de tempos (S3)
        self._dirty_global = False
        if self.store.segments:
            self.aligner.align_all(self.store.words())
        self._recompute()

    @classmethod
    def open(cls, epub_path: str, audio_path: str, cache: Path, model_size: str = "small"):
        book = load_book(epub_path, cache)
        duration = float(audio.probe(audio_path)["format"]["duration"])
        chs_path = cache / "audio_chapters.json"
        if chs_path.exists():
            chapters = json.loads(chs_path.read_text())
        else:
            chapters = [c.__dict__ for c in audio.chapters(audio_path)]
            chs_path.write_text(json.dumps(chapters, ensure_ascii=False))
        return cls(book, cache, duration, chapters, audio_path, model_size)

    # -- transcrição em segundo plano

    def start_worker(self, playhead: float):
        if self.store.complete(self.duration):
            self.worker_state = "done"
            return
        from . import worker
        ctx = mp.get_context("spawn")
        self._cmd_q = ctx.Queue()
        self._out_q = ctx.Queue()
        self._cmd_q.put({"playhead": playhead})
        self._proc = ctx.Process(
            target=worker.run, daemon=True,
            args=(self.audio_path, str(self.cache), self.book["language"],
                  self.model_size, self._cmd_q, self._out_q))
        self._proc.start()
        self.worker_state = "loading"

    def stop_worker(self):
        proc = getattr(self, "_proc", None)
        if proc is None:
            return
        if proc.is_alive():
            self._cmd_q.put({"stop": True})
            proc.join(timeout=2)
            if proc.is_alive():
                proc.terminate()
                proc.join(timeout=1)
        for q in (self._cmd_q, self._out_q):          # J11: sem semáforos vazados
            q.close()
            q.join_thread()
        # o semáforo de cada fila só é liberado quando a fila deixa de existir
        self._proc = self._cmd_q = self._out_q = None

    def update_playhead(self, t: float):
        q = getattr(self, "_cmd_q", None)
        if q is not None and self.worker_state in ("loading", "running"):
            q.put({"playhead": t})

    def poll(self) -> bool:
        """Processa as mensagens pendentes do worker; True se os tempos mudaram."""
        q = getattr(self, "_out_q", None)
        if q is None:
            return False
        changed = False
        while True:
            try:
                msg = q.get_nowait()
            except queue.Empty:
                break
            changed |= self.handle(msg)
        proc = getattr(self, "_proc", None)
        if proc is not None and not proc.is_alive() and self.worker_state in ("loading", "running"):
            self.worker_state = "error"                                    # S6
            print("[worker] o processo de transcrição terminou inesperadamente", file=sys.stderr)
        return changed

    def handle(self, msg: dict) -> bool:
        """Trata uma mensagem do worker; True se os tempos mudaram."""
        kind = msg["type"]
        if kind == "ready":
            self.worker_state = "running"
        elif kind == "segment":
            seg = msg["seg"]
            self.store.add(seg, write=False)   # o worker já gravou em disco
            if seg["words"]:
                self.aligner.add_segment(seg["words"])
                self._dirty_global = True
            self._recompute()
            return True
        elif kind == "done":
            self.worker_state = "done"
            if self._dirty_global:            # S5
                self.aligner.align_all(self.store.words())
                self._dirty_global = False
                self._recompute()
                return True
        elif kind == "error":
            self.worker_state = "error"
            print(msg["msg"], file=sys.stderr)
        return False

    # -- tempos

    def _recompute(self):
        self.aligner.compute(self.store.covers)
        al = self.aligner
        idx = [k for k in range(len(self.words)) if al.state[k] == NARRATED]
        self.word_starts = [al.ws[k] for k in idx]
        self.word_ids = idx
        self.extras = al.extras                                    # A12
        self.version += 1

    def extra_at(self, t: float):
        """S7: (trecho, palavra) do texto só do áudio sendo dito em t, ou None."""
        for ei, ex in enumerate(self.extras):
            ws = ex["words"]
            if not ws[0]["s"] <= t:
                continue
            if t > ws[-1]["e"]:
                # depois do trecho: a última palavra dele continua até o livro retomar
                k = bisect.bisect_right(self.word_starts, ws[-1]["s"])
                if k < len(self.word_starts) and self.word_starts[k] <= t:
                    continue
            wi = max(i for i, w in enumerate(ws) if w["s"] <= t)
            return ei, wi
        return None

    def word_at(self, t: float) -> int | None:
        """Palavra sendo narrada (ou a última antes de t), ou None se não houver."""
        k = bisect.bisect_right(self.word_starts, t) - 1
        if k < 0:
            return None
        wid = self.word_ids[k]
        # se t cai depois do fim e não há transcrição ali, é incerto
        if t > self.aligner.we[wid] + 4.0 and not self.store.covers(self.aligner.we[wid], t):
            return None
        return wid

    def is_covered(self, t: float) -> bool:
        return self.store.covered_until(t) is not None

    def block_state(self, b: dict) -> int:
        st = self.aligner.state
        if b["kind"] == "img":
            return NARRATED
        ids = [w["id"] for w in b["words"]]
        if any(st[k] == NARRATED for k in ids):
            return NARRATED
        if ids and all(st[k] == SKIPPED for k in ids):
            return SKIPPED
        return 0

    def block_start(self, b: dict) -> float | None:
        al = self.aligner
        for w in b["words"]:
            if al.state[w["id"]] == NARRATED:
                return al.ws[w["id"]]
        return None

    def image_time(self, block_index: int) -> float | None:
        """Instante em que a imagem aparece: fim do último texto narrado antes dela."""
        al = self.aligner
        for b in reversed(self.blocks[:block_index]):
            for w in reversed(b["words"]):
                if al.state[w["id"]] == NARRATED:
                    return al.we[w["id"]]
        return None

    def chapter_title(self, t: float) -> str:
        title = ""
        for c in self.audio_chapters:
            if c["start"] <= t:
                title = c["title"]
        return title
