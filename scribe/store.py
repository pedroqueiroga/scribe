"""Armazenamento incremental da transcrição.

Cada pedaço transcrito vira `<cache>/transcript/<inicio_ms>.json` com
{"s": inicio, "e": fim, "words": [{"w","s","e","p"}...]}. A cobertura
(intervalos já transcritos) é reconstruída lendo esses arquivos, então o
trabalho continua de onde parou ao reabrir o livro.
"""
from __future__ import annotations

import bisect
import json
from pathlib import Path

EPS = 0.05


class TranscriptStore:
    def __init__(self, cache: Path):
        self.dir = cache / "transcript"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.segments: list[dict] = []
        for p in sorted(self.dir.glob("*.json")):
            try:
                d = json.loads(p.read_text())
            except (json.JSONDecodeError, OSError):
                continue
            if "chapter" in d:  # formato antigo: um capítulo inteiro
                d = {"s": d["chapter"]["start"], "e": d["chapter"]["end"], "words": d["words"]}
            self.segments.append(d)
        self.segments.sort(key=lambda d: d["s"])
        self._rebuild()

    def _rebuild(self):
        iv: list[list[float]] = []
        for d in self.segments:
            if iv and d["s"] <= iv[-1][1] + EPS:
                iv[-1][1] = max(iv[-1][1], d["e"])
            else:
                iv.append([d["s"], d["e"]])
        self.intervals = iv
        self._starts = [a for a, _ in iv]

    def add(self, seg: dict, write: bool = True):
        if write:
            target = self.dir / f"{int(round(seg['s'] * 1000)):010d}.json"
            tmp = target.with_suffix(".tmp")
            tmp.write_text(json.dumps(seg, ensure_ascii=False))
            tmp.rename(target)
        bisect.insort(self.segments, seg, key=lambda d: d["s"])
        self._rebuild()

    def covered_until(self, t: float) -> float | None:
        """Se t está coberto, devolve o fim do intervalo coberto; senão None."""
        k = bisect.bisect_right(self._starts, t + EPS) - 1
        if k >= 0 and self.intervals[k][1] > t + EPS:
            return self.intervals[k][1]
        return None

    def covers(self, a: float, b: float) -> bool:
        end = self.covered_until(a)
        return end is not None and end >= b - EPS

    def next_gap(self, t: float, duration: float) -> float | None:
        """Primeiro instante não transcrito a partir de t (ou antes, dando a volta)."""
        end = self.covered_until(t)
        if end is None:
            return t if t < duration - EPS else None
        if end < duration - EPS:
            return end
        # do ponto atual até o fim está tudo pronto: preenche buracos anteriores
        prev = 0.0
        for a, b in self.intervals:
            if a > prev + EPS:
                return prev
            prev = b
        return prev if prev < duration - EPS else None

    def complete(self, duration: float) -> bool:
        return self.covers(0.0, duration)

    def words(self) -> list[dict]:
        """Todas as palavras em ordem, sem duplicatas de pedaços sobrepostos."""
        out: list[dict] = []
        last_end = -1.0
        for w in sorted((w for d in self.segments for w in d["words"]), key=lambda w: w["s"]):
            if w["s"] >= last_end - 0.05:
                out.append(w)
                last_end = w["e"]
        return out
