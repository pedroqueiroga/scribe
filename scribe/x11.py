"""Forma de entrada da janela no X11 (J3): onde a janela aceita o mouse."""
from __future__ import annotations

from Xlib import X, display
from Xlib.ext import shape

_disp = None


def _window(wid: int):
    global _disp
    if _disp is None:
        _disp = display.Display()
    return _disp, _disp.create_resource_object("window", wid)


def set_input_region(wid: int, rects: list[tuple[int, int, int, int]] | None):
    """Só os retângulos (em pixels físicos) recebem o mouse; o resto atravessa.
    `None` devolve a janela inteira ao mouse."""
    d, w = _window(wid)
    if rects is None:
        w.shape_mask(shape.SO.Set, shape.SK.Input, 0, 0, X.NONE)
    else:
        w.shape_rectangles(shape.SO.Set, shape.SK.Input, X.Unsorted, 0, 0, rects)
    d.flush()
