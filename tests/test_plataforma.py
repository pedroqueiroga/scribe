"""Plataforma e dependências — specs/plataforma.md (K1)."""
from __future__ import annotations

import sys


def test_K1_emitir_sinais_nao_consome_referencias_do_true():
    from PySide6.QtCore import QObject, Signal

    class Emissor(QObject):
        sinal = Signal()

    e = Emissor()
    e.sinal.connect(lambda: None)
    antes = sys.getrefcount(True)
    for _ in range(200):
        e.sinal.emit()
    # com o defeito, a contagem cai 200 (uma por emissão); tolera ruído de poucas unidades
    assert abs(sys.getrefcount(True) - antes) < 20
