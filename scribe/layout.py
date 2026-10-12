"""Imagem ao lado do texto — specs/layout.md.

Decide quanto a janela cresce para a direita, quanto o texto cede e o tamanho do
painel da imagem. Não depende de Qt: recebe geometrias e devolve números.
"""
from __future__ import annotations

from dataclasses import dataclass

CHROME = 66      # largura da janela que não é texto (margens e a fita), sem imagem
GAP = 20         # espaço entre o texto e a imagem
VPAD = 14        # margem vertical do painel da imagem
MIN_TEXT = 280   # G3


@dataclass
class Layout:
    window_w: float   # largura nova da janela
    text_w: float     # largura do texto
    panel_w: float    # largura do painel da imagem
    panel_h: float    # altura da imagem dentro do painel


class ImageLayout:
    def __init__(self):
        self._base: float | None = None   # largura da janela antes de crescer

    def show(self, win_x: float, win_w: float, win_h: float, screen_right: float,
             img_w: float, img_h: float) -> Layout:
        base = self._base if self._base is not None else win_w           # G6
        self._base = base
        text = base - CHROME
        ratio = img_w / img_h
        panel_h = win_h - 2 * VPAD
        panel_w = min(panel_h * ratio, text)                               # G1
        panel_h = panel_w / ratio
        need = panel_w + GAP
        space = max(0.0, screen_right - (win_x + base))
        if space >= need:                                                  # G2
            return Layout(base + need, text, panel_w, panel_h)
        grow = space                                                       # G3
        text_w = max(min(text, MIN_TEXT), text - (need - grow))
        panel_w = max(0.0, base + grow - CHROME - text_w - GAP)
        return Layout(base + grow, text_w, panel_w, panel_w / ratio)

    def hide(self) -> float | None:                                        # G4
        base, self._base = self._base, None
        return base

    def saved_width(self, current_w: float) -> float:                      # G5
        return self._base if self._base is not None else current_w
