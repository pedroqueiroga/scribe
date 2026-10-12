"""Atalhos globais no X11 via XGrabKey (a combinação fica exclusiva do scribe)."""
from __future__ import annotations

import threading
from typing import Callable

from Xlib import X, XK, display, error

DEFAULT = {
    "toggle_play": "ctrl+alt+p",
    "back": "ctrl+alt+comma",
    "forward": "ctrl+alt+period",
    "prev_block": "ctrl+alt+j",
    "next_block": "ctrl+alt+k",
    "toggle_visible": "ctrl+alt+h",
    "toggle_lock": "ctrl+alt+f",
    "slower": "ctrl+alt+bracketleft",
    "faster": "ctrl+alt+bracketright",
}

_MODS = {"ctrl": X.ControlMask, "alt": X.Mod1Mask, "shift": X.ShiftMask, "super": X.Mod4Mask}
# variações com NumLock (Mod2) e CapsLock (Lock) ligados
_IGNORED = [0, X.LockMask, X.Mod2Mask, X.LockMask | X.Mod2Mask]


class HotkeyListener(threading.Thread):
    def __init__(self, bindings: dict[str, str], callback: Callable[[str], None]):
        super().__init__(daemon=True)
        self.callback = callback
        self.disp = display.Display()
        self.root = self.disp.screen().root
        self.keys: dict[tuple[int, int], str] = {}
        self.failed: list[str] = []
        for action, combo in bindings.items():
            parts = combo.split("+")
            mods = 0
            for p in parts[:-1]:
                mods |= _MODS[p.lower()]
            keysym = XK.string_to_keysym(parts[-1])     # nomes de tecla diferenciam maiúsculas
            code = self.disp.keysym_to_keycode(keysym) if keysym else 0
            if not code:
                self.failed.append(combo)
                continue
            catcher = error.CatchError(error.BadAccess)  # H1: uma verificação por combinação
            for extra in _IGNORED:
                self.root.grab_key(code, mods | extra, True, X.GrabModeAsync, X.GrabModeAsync,
                                   onerror=catcher)
            self.disp.sync()
            if catcher.get_error():
                for extra in _IGNORED:
                    self.root.ungrab_key(code, mods | extra)
                self.disp.sync()
                self.failed.append(combo)
                continue
            self.keys[(code, mods)] = action
        self._stop = False

    def run(self):
        mask = X.ControlMask | X.Mod1Mask | X.ShiftMask | X.Mod4Mask
        while not self._stop:
            ev = self.disp.next_event()
            if ev.type == X.KeyPress:
                action = self.keys.get((ev.detail, ev.state & mask))
                if action:
                    self.callback(action)

    def stop(self):
        self._stop = True
