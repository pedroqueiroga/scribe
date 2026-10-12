"""Modo de uma linha — specs/oneline.md.

O modo é consequência da altura da janela. As funções recebem a altura de uma linha
medida na tela (`line`, em px); enquanto a medida não chega, vale `estimated_line`.
"""
from __future__ import annotations

import math

ESTIMATE = 1.7   # altura de linha ≈ 1,7 × tamanho da fonte (Roboto, line-height 128%)
EXTRA = 22       # O1: margens e a linha de progresso
DOCK = 48        # O2: faixa da barra no modo normal (J5)
MIN_LINES = 2.5  # O2: linhas de texto que o modo normal precisa
PROGRESS = 4     # O6: espaço da linha de progresso, embaixo


def estimated_line(font: int) -> float:
    return font * ESTIMATE


def oneline_height(line: float) -> int:                                   # O1
    return math.ceil(line + EXTRA)


def threshold(line: float) -> float:                                      # O2
    return DOCK + MIN_LINES * line


def is_oneline(height: float, line: float) -> bool:                       # O2
    return height < threshold(line)


def height_after_line_change(height: float, old_line: float, new_line: float) -> float:  # O4
    return oneline_height(new_line) if is_oneline(height, old_line) else height


def initial_height(saved: float | None, line: float, oneline: bool) -> float | None:   # O5
    return oneline_height(line) if oneline else saved


def strip_margins(height: float, line: float) -> tuple[float, float]:     # O6
    """Margens de cima e de baixo para a faixa ter exatamente uma linha."""
    free = max(0.0, height - line - PROGRESS)
    return free / 2, free / 2 + PROGRESS
