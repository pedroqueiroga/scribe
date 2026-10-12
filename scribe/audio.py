"""Leitura de metadados e trechos de áudio via ffprobe/ffmpeg."""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass

import numpy as np

SAMPLE_RATE = 16000


@dataclass
class AudioChapter:
    index: int
    title: str
    start: float
    end: float


def probe(path: str) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json",
         "-show_format", "-show_chapters", path],
        check=True, capture_output=True, text=True,
    ).stdout
    return json.loads(out)


def chapters(path: str) -> list[AudioChapter]:
    """Capítulos do arquivo; se não houver marcas, divide em blocos de 10 min."""
    info = probe(path)
    duration = float(info["format"]["duration"])
    chs = [
        AudioChapter(i, c.get("tags", {}).get("title", f"Parte {i + 1}"),
                     float(c["start_time"]), float(c["end_time"]))
        for i, c in enumerate(info.get("chapters", []))
    ]
    if chs:
        return chs
    step = 600.0
    n = int(duration // step) + 1
    return [AudioChapter(i, f"Parte {i + 1}", i * step, min((i + 1) * step, duration))
            for i in range(n)]


def load_segment(path: str, start: float, end: float) -> np.ndarray:
    """Áudio mono 16 kHz float32 entre start e end (segundos)."""
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{start:.3f}", "-to", f"{end:.3f}",
         "-i", path, "-map", "0:a:0", "-ac", "1", "-ar", str(SAMPLE_RATE),
         "-f", "f32le", "-"],
        check=True, capture_output=True,
    ).stdout
    return np.frombuffer(raw, dtype=np.float32)
