"""Atalhos globais — specs/atalhos.md (H1). Precisa de um servidor X."""
from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="sem servidor X")


def test_H1_combinacao_ocupada_aparece_pelo_nome_e_as_outras_seguem():
    from scribe.hotkeys import HotkeyListener
    # combinações improváveis de estarem em uso por outros programas
    ocupada, livre = "ctrl+alt+shift+F11", "ctrl+alt+shift+F12"
    dono = HotkeyListener({"x": ocupada}, lambda a: None)
    try:
        assert dono.failed == []
        segundo = HotkeyListener({"x": ocupada, "y": livre}, lambda a: None)
        try:
            assert segundo.failed == [ocupada]
            assert "y" in segundo.keys.values()
        finally:
            segundo.disp.close()
    finally:
        dono.disp.close()
