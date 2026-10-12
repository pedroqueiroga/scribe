"""Leitor — specs/reader.md.

Liga o tocador de áudio, a sessão e a interface, sem depender de Qt nem do mpv:
o tocador é qualquer objeto com `time_pos`, `pause`, `speed` e `seek(t)`.
"""
from __future__ import annotations

import bisect
import html
import re

from .align import NARRATED, SKIPPED

IMAGE_SECONDS = 7.0                                        # R5
SPEEDS = [0.75, 0.9, 1.0, 1.1, 1.25, 1.4, 1.5, 1.75, 2.0]  # R4
JUMP_THRESHOLD = 2.0       # salto maior que isso entre ticks é um pulo (R5, R7)
NOTIFY_EVERY = 5.0         # R7
BLOCK_RESTART = 2.0        # R2
SEEK_LEAD = 0.05           # R1: começa um tiquinho antes da palavra

DEFAULT_PREFS = {"font_size": 22, "bg_opacity": 0.55, "locked": False,
                 "click_through": False, "geometry": [],
                 "text_color": "#f3eee4", "text_opacity": 1.0,
                 "bg_color": "#15131f", "bg_image": ""}
PREF_LIMITS = {"font_size": (12, 64), "bg_opacity": (0.0, 1.0),
               "text_opacity": (0.2, 1.0)}                         # R8
COLOR_RE = re.compile(r"#[0-9a-fA-F]{6}")

# R6: transparência de cada estilo do karaokê (multiplica a opacidade do texto, R8)
EXTRA_MARK = "♪ "       # R13: marca do texto que vem só do áudio
MARK_COLOR = "d9b25f"   # dourado da fita
STYLE_ALPHA = {"past": 1.0, "now": 1.0, "future": 0.5, "other": 0.42, "skipped": 0.22}


class Reader:
    def __init__(self, session, player, lib, bid: str):
        self.session = session
        self.player = player
        self.lib = lib
        self.bid = bid
        self.entry = lib.data["books"][bid]
        self.prefs = {**DEFAULT_PREFS,
                      **{k: v for k, v in lib.data["ui"].items() if k in DEFAULT_PREFS}}
        self.player.speed = self.entry.get("speed", 1.0)
        self.position = float(self.entry.get("position", 0.0))
        if self.position > 0:                                  # R9
            self.player.seek(self.position)
        self._last_t = self.position
        self.current_row = -1
        self.current_word: int | None = None
        self.current_extra: tuple[int, int] | None = None   # R13
        self.image: str | None = None
        self._image_until = 0.0
        self._images_version = -1
        self._images: list[tuple[float, str]] = []
        self._sync(self.position)

    # ---------------------------------------------------------------- laço

    def tick(self) -> set[str]:
        """Chamado periodicamente pela interface. Devolve o que mudou."""
        changed: set[str] = set()
        if self.session.poll():
            changed.add("timings")
        t = self.player.time_pos
        if t is None:
            return changed
        last = self._last_t
        jumped = abs(t - last) > JUMP_THRESHOLD
        if jumped or int(t // NOTIFY_EVERY) != int(last // NOTIFY_EVERY):   # R7
            self.session.update_playhead(t)
        if jumped and self.image:                                          # R5: pulo esconde
            self.image = None
            changed.add("image")
        if not jumped and t > last:
            src = self._image_between(last, t)                             # R5
            if src:
                self.image = src
                self._image_until = t + IMAGE_SECONDS
                changed.add("image")
        if self.image and t > self._image_until:
            self.image = None
            changed.add("image")
        self._last_t = t
        self.position = t
        changed.add("position")
        if self._sync(t, force="timings" in changed):
            changed.add("current")
        return changed

    def _sync(self, t: float, force: bool = False) -> bool:
        wid = self.session.word_at(t)
        ex = self.session.extra_at(t)
        if wid == self.current_word and ex == self.current_extra and not force:
            return False
        self.current_word = wid
        self.current_extra = ex
        if ex is not None:                                                 # R13
            after = self.session.extras[ex[0]]["after"]
            self.current_row = self.session.words[after]["block"]
        elif wid is not None:
            self.current_row = self.session.words[wid]["block"]
        return True

    def _ensure_images(self):
        """Horário (S4), arquivo e capítulo de cada imagem, ordenados pelo horário."""
        if self._images_version != self.session.version:
            imgs = []
            for row, b in enumerate(self.session.blocks):
                if b["kind"] == "img":
                    ts = self.session.image_time(row)
                    if ts is not None:
                        imgs.append((ts, b["src"], self._anchor_chapter(row)))
            self._images = sorted(imgs)
            self._images_version = self.session.version
        return self._images

    def _anchor_chapter(self, row: int) -> int:
        """R14: capítulo do texto narrado logo antes da imagem."""
        st = self.session.aligner.state
        for b in reversed(self.session.blocks[:row]):
            if any(st[w["id"]] == NARRATED for w in b["words"]):
                return b["chapter"]
        return self.session.blocks[row]["chapter"]

    def _image_between(self, t0: float, t1: float) -> str | None:
        imgs = self._ensure_images()
        times = [ts for ts, _, _ in imgs]
        k = bisect.bisect_right(times, t0)
        if k < len(imgs) and imgs[k][0] <= t1:
            return imgs[k][1]
        return None

    def recent_image(self) -> str | None:                                  # R14
        if self.current_row < 0:
            return None
        chapter = self.session.blocks[self.current_row]["chapter"]
        imgs = self._ensure_images()
        k = bisect.bisect_right([ts for ts, _, _ in imgs], self.position) - 1
        if k >= 0 and imgs[k][2] == chapter:
            return imgs[k][1]
        return None

    # ---------------------------------------------------------------- navegação

    def seek(self, t: float):
        t = max(0.0, min(self.session.duration - 0.5, t))
        self.player.seek(t)
        self.image = None                                                  # R5: pulo esconde
        self.position = t
        self._last_t = t
        self.session.update_playhead(t)                                    # R7
        self._sync(t, force=True)

    def skip(self, dt: float):                                             # R3
        self.seek(self.position + dt)

    def seek_word(self, row: int, k: int):                                 # R1
        al = self.session.aligner
        wid = self.session.blocks[row]["words"][k]["id"]
        for w in self.session.words[wid:]:
            if al.state[w["id"]] == NARRATED:
                self.seek(max(0.0, al.ws[w["id"]] - SEEK_LEAD))
                return

    def seek_link(self, link: str):
        if link.startswith("x"):                                           # R13
            ei, wi = map(int, link[1:].split(":"))
            self.seek(max(0.0, self.session.extras[ei]["words"][wi]["s"] - SEEK_LEAD))
            return
        row, k = map(int, link.split(":"))
        self.seek_word(row, k)

    def jump_block(self, delta: int):                                      # R2
        row = self.current_row
        if row < 0:
            self.skip(10 * delta)
            return
        blocks = self.session.blocks
        cur_start = self.session.block_start(blocks[row])
        if delta < 0 and cur_start is not None and self.position - cur_start > BLOCK_RESTART:
            self.seek(cur_start)
            return
        r = row + delta
        while 0 <= r < len(blocks):
            s = self.session.block_start(blocks[r])
            if s is not None:
                self.seek(s)
                return
            r += delta

    def toggle_play(self):
        self.player.pause = not self.player.pause

    def adjust_speed(self, step: int):                                     # R4
        cur = self.player.speed
        i = min(range(len(SPEEDS)), key=lambda k: abs(SPEEDS[k] - cur))
        self.player.speed = SPEEDS[max(0, min(len(SPEEDS) - 1, i + step))]
        self.entry["speed"] = self.player.speed
        self.lib.save()

    def dismiss_image(self):
        self.image = None

    # ---------------------------------------------------------------- exibição (R6)

    def word_styles(self, row: int) -> list[str]:
        st = self.session.aligner.state
        cur = self.current_word if row == self.current_row else None
        out = []
        for w in self.session.blocks[row]["words"]:
            wid = w["id"]
            if st[wid] == SKIPPED:
                out.append("skipped")
            elif cur is None:
                out.append("other")
            elif wid < cur:
                out.append("past")
            elif wid == cur:
                out.append("now")
            else:
                out.append("future")
        return out

    def _visible_extras(self, row: int) -> list[int]:
        """R13: trechos só do áudio deste parágrafo que a narração já alcançou."""
        out = []
        for ei, ex in enumerate(self.session.extras):
            if (self.session.words[ex["after"]]["block"] == row
                    and ex["words"][0]["s"] <= self.position + 0.01):
                out.append(ei)
        return out

    def current_char_offset(self) -> int:
        """Onde a palavra atual começa no texto do parágrafo (para a janela seguir a linha)."""
        if self.current_extra is not None:                                 # R13
            ei, wi = self.current_extra
            row = self.current_row
            offset = len(" ".join(w["t"] for w in self.session.blocks[row]["words"]))
            for vi in self._visible_extras(row):
                ws = self.session.extras[vi]["words"]
                offset += 1 + len(EXTRA_MARK)           # quebra de linha + marca
                if vi == ei:
                    return offset + sum(len(w["w"]) + 1 for w in ws[:wi])
                offset += len(" ".join(w["w"] for w in ws))
            return 0
        if self.current_word is None:
            return 0
        offset = 0
        for w in self.session.blocks[self.current_row]["words"]:
            if w["id"] == self.current_word:
                return offset
            offset += len(w["t"]) + 1
        return 0

    def block_html(self, row: int) -> str:
        words = self.session.blocks[row]["words"]
        parts = []
        color = self.prefs["text_color"][1:]
        opacity = self.prefs["text_opacity"]
        for k, (w, style) in enumerate(zip(words, self.word_styles(row))):
            alpha = int(STYLE_ALPHA[style] * opacity * 255)
            parts.append(f'<a href="{row}:{k}" style="color:#{alpha:02x}{color};'
                         f'text-decoration:none">{html.escape(w["t"])}</a>')
        html_out = " ".join(parts)
        for ei in self._visible_extras(row):                               # R13
            ws = self.session.extras[ei]["words"]
            cur = self.current_extra[1] if self.current_extra and self.current_extra[0] == ei else None
            items = []
            for wi, w in enumerate(ws):
                style = ("other" if cur is None else
                         "past" if wi < cur else "now" if wi == cur else "future")
                a_ = int(STYLE_ALPHA[style] * opacity * 255)
                items.append(f'<a href="x{ei}:{wi}" style="color:#{a_:02x}{color};'
                             f'text-decoration:none">{html.escape(w["w"])}</a>')
            mark_a = int(0.8 * opacity * 255)
            html_out += (f'<br/><i><span style="color:#{mark_a:02x}{MARK_COLOR}">{EXTRA_MARK.strip()}</span> '
                         + " ".join(items) + "</i>")
        return html_out

    # ---------------------------------------------------------------- preferências (R8)

    def set_pref(self, key: str, value):
        if key in ("text_color", "bg_color") and not (
                isinstance(value, str) and COLOR_RE.fullmatch(value)):
            return                                                         # R8: cor inválida
        if key in PREF_LIMITS:
            lo, hi = PREF_LIMITS[key]
            value = max(lo, min(hi, value))
        self.prefs[key] = value
        self.lib.data["ui"][key] = value
        self.lib.save()

    def toggle_lock(self):                                                 # R10
        locked = not self.prefs["locked"]
        self.set_pref("locked", locked)
        if not locked and self.prefs["click_through"]:
            self.set_pref("click_through", False)

    def window_mode(self) -> dict:                                         # R10
        locked = bool(self.prefs["locked"])
        return {"on_top": locked, "click_through": locked and bool(self.prefs["click_through"])}

    def set_background_image(self, path: str) -> bool:                    # R12
        """Copia a imagem para a pasta de dados e a usa como fundo; "" remove."""
        if not path:
            self.set_pref("bg_image", "")
            return True
        import hashlib
        import shutil
        from pathlib import Path
        from PySide6.QtGui import QImageReader
        from .library import data_dir
        src = Path(path).expanduser()
        if not src.is_file() or not QImageReader(str(src)).canRead():
            return False
        digest = hashlib.sha1(src.read_bytes()).hexdigest()[:16]
        dest_dir = data_dir() / "backgrounds"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"{digest}{src.suffix.lower()}"
        if not dest.exists():
            shutil.copyfile(src, dest)
        self.set_pref("bg_image", str(dest))
        return True

    def save(self):                                                        # R9
        t = self.player.time_pos
        if t is not None:
            self.lib.set_position(self.bid, t)

    def close(self):                                                       # R9, R11
        self.player.pause = True          # R11: silêncio antes de qualquer outra coisa
        self.save()
