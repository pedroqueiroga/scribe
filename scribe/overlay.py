"""Janela (specs/janela.md): ponte fina entre o Reader e a interface QML."""
from __future__ import annotations

import locale
import sys
from pathlib import Path

from PySide6.QtCore import (QAbstractListModel, QModelIndex, QObject, Qt, QTimer, QUrl,
                            Property, Signal, Slot)
from PySide6.QtGui import QFontDatabase, QGuiApplication, QSurfaceFormat
from PySide6.QtQml import QQmlApplicationEngine

from .align import NARRATED, SKIPPED
from .layout import GAP, ImageLayout, inline_size, is_vertical
from . import oneline as one
from .reader import Reader

HERE = Path(__file__).parent
TICK_MS = 33
SAVE_EVERY_MS = 5000


class MpvPlayer:
    """Adaptador do mpv para a interface de tocador do Reader."""

    def __init__(self, path: str):
        import mpv
        locale.setlocale(locale.LC_NUMERIC, "C")  # exigência da libmpv
        self.mpv = mpv.MPV(video=False, ytdl=False, input_default_bindings=False,
                           keep_open="yes")
        self.mpv.play(path)
        try:
            self.mpv.wait_until_playing(timeout=5)
        except TypeError:
            self.mpv.wait_until_playing()

    @property
    def time_pos(self):
        return self.mpv.time_pos

    @property
    def pause(self):
        return bool(self.mpv.pause)

    @pause.setter
    def pause(self, v):
        self.mpv.pause = v

    @property
    def speed(self):
        return float(self.mpv.speed)

    @speed.setter
    def speed(self, v):
        self.mpv.speed = v

    def seek(self, t):
        self.mpv.seek(t, reference="absolute", precision="exact")

    def close(self):
        try:
            self.mpv.terminate()
        except Exception:
            pass


class BlockModel(QAbstractListModel):
    KIND, HTML, VISIBLE, SRC = range(Qt.UserRole + 1, Qt.UserRole + 5)

    def __init__(self, reader: Reader, cache: Path):
        super().__init__()
        self.r = reader
        self.cache = cache
        self._visible = self._compute_visible()

    def roleNames(self):
        return {self.KIND: b"kind", self.HTML: b"html", self.VISIBLE: b"shown", self.SRC: b"src"}

    def rowCount(self, parent=QModelIndex()):
        return len(self.r.session.blocks)

    def data(self, index, role):
        row = index.row()
        b = self.r.session.blocks[row]
        if role == self.KIND:
            return b["kind"]
        if role == self.HTML:
            return "" if b["kind"] == "img" else self.r.block_html(row)
        if role == self.VISIBLE:
            return self._visible[row]
        if role == self.SRC:
            return image_url(self.cache, b["src"]) if b["kind"] == "img" else ""
        return None

    def _compute_visible(self):
        # J9: blocos inteiramente pulados somem; imagens ficam no painel (J6), e só entram
        # na lista as que têm hora (G8), que o QML mostra no modo vertical
        inline = self.r.inline_images()
        return [inline[i] if b["kind"] == "img" else self.r.session.block_state(b) != SKIPPED
                for i, b in enumerate(self.r.session.blocks)]

    def refresh_all(self):
        self._visible = self._compute_visible()
        n = self.rowCount()
        if n:
            self.dataChanged.emit(self.index(0), self.index(n - 1), [self.HTML, self.VISIBLE])

    def refresh_rows(self, *rows):
        for r in {r for r in rows if r is not None and r >= 0}:
            self.dataChanged.emit(self.index(r), self.index(r), [self.HTML])


def image_url(cache: Path, src: str) -> str:
    return QUrl.fromLocalFile(str(cache / "images" / src)).toString()


class Bridge(QObject):
    positionChanged = Signal()
    currentChanged = Signal()
    imageChanged = Signal()
    prefsChanged = Signal()
    statusChanged = Signal()
    visibilityToggleRequested = Signal()
    jumped = Signal()                 # J4: um pulo no áudio ressincroniza o texto
    hotkey = Signal(str)

    def __init__(self, app, reader: Reader, model: BlockModel, cache: Path, oneline: bool = False):
        super().__init__()
        self.app = app
        self.start_oneline = oneline
        self._line = one.estimated_line(reader.prefs["font_size"])   # O1: até a medida chegar
        self.r = reader
        self.model = model
        self.cache = cache
        self._row = reader.current_row
        self._status = ""
        self.layout = ImageLayout()
        self._panel = (0.0, 0.0)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(TICK_MS)
        self.save_timer = QTimer(self)
        self.save_timer.timeout.connect(reader.save)
        self.save_timer.start(SAVE_EVERY_MS)
        self.hotkey.connect(self._on_hotkey)

    def _tick(self):
        changed = self.r.tick()
        if "timings" in changed:
            self.model.refresh_all()
            self.statusChanged.emit()
        if "current" in changed:
            self.model.refresh_rows(self._row, self.r.current_row)
            self._row = self.r.current_row
            self.currentChanged.emit()
        if "image" in changed:
            self.imageChanged.emit()
        if "position" in changed:
            self.positionChanged.emit()
        status = self._compute_status()
        if status != self._status:
            self._status = status
            self.statusChanged.emit()

    def _compute_status(self):                          # J10
        s = self.r.session
        if self.r.current_word is not None and s.is_covered(self.r.position):
            return ""
        return {"idle": "", "loading": "carregando o modelo…", "running": "transcrevendo…",
                "error": "erro na transcrição", "done": ""}.get(s.worker_state, "")

    def _after_nav(self):
        self.jumped.emit()
        self.imageChanged.emit()          # um pulo pode ter mudado a imagem (R5)
        self.model.refresh_rows(self._row, self.r.current_row)
        self._row = self.r.current_row
        self.currentChanged.emit()
        self.positionChanged.emit()

    # ---------------------------------------------------------------- propriedades

    @Property(float, notify=positionChanged)
    def position(self):
        return self.r.position

    @Property(float, constant=True)
    def duration(self):
        return self.r.session.duration

    @Property(bool, notify=positionChanged)
    def playing(self):
        return not self.r.player.pause

    @Property(int, notify=currentChanged)
    def currentRow(self):
        return self.r.current_row

    @Property(int, notify=currentChanged)
    def currentCharOffset(self):
        return self.r.current_char_offset()

    @Property(bool, notify=currentChanged)
    def synced(self):
        return self.r.current_word is not None

    @Property(str, notify=positionChanged)
    def chapterTitle(self):
        return self.r.session.chapter_title(self.r.position)

    @Property(str, constant=True)
    def bookTitle(self):
        return self.r.session.book["title"]

    @Property(int, notify=imageChanged)
    def focusRow(self):
        return self.r.focus_row                           # G10

    @Property(str, notify=imageChanged)
    def image(self):
        return image_url(self.cache, self.r.image) if self.r.image else ""

    @Property(str, notify=statusChanged)
    def status(self):
        return self._status

    @Property(float, notify=statusChanged)
    def transcribedFraction(self):
        s = self.r.session
        return sum(b - a for a, b in s.store.intervals) / max(1.0, s.duration)

    @Property(int, notify=prefsChanged)
    def fontSize(self):
        return self.r.prefs["font_size"]

    @Property(float, notify=prefsChanged)
    def bgOpacity(self):
        return self.r.prefs["bg_opacity"]

    @Property(bool, notify=prefsChanged)
    def locked(self):
        return self.r.prefs["locked"]

    @Property(bool, notify=prefsChanged)
    def clickThrough(self):
        return self.r.prefs["click_through"]

    @Property(bool, notify=prefsChanged)
    def onTop(self):
        return self.r.window_mode()["on_top"]

    @Property(bool, notify=prefsChanged)
    def passClicks(self):
        return self.r.window_mode()["click_through"]

    @Property(float, notify=prefsChanged)
    def speed(self):
        return self.r.player.speed

    @Property("QVariantList", constant=True)
    def geometry(self):
        """Geometria inicial; com --oneline, na altura de uma linha (O5)."""
        g = list(self.r.prefs["geometry"])
        saved_h = g[3] if len(g) == 4 else None
        h = one.initial_height(saved_h, self._line, self.start_oneline)
        if h is not None:
            if len(g) == 4:
                g[3] = h
            else:
                g = [-1, -1, -1, h]       # sem geometria salva: só a altura
        return g

    lineChanged = Signal()

    @Slot(float)
    def setLinePitch(self, px):
        """Altura de uma linha medida na tela (O1–O6)."""
        if px > 0 and abs(px - self._line) > 0.01:
            self._line = px
            self.lineChanged.emit()

    @Property(float, notify=lineChanged)
    def linePitch(self):
        return self._line

    @Property(float, notify=lineChanged)
    def onelineThreshold(self):                       # O2
        return one.threshold(self._line)

    @Property(float, notify=lineChanged)
    def onelineHeight(self):                          # O1
        return one.oneline_height(self._line)

    @Slot(float, result="QVariantList")
    def stripMargins(self, h):                        # O6
        return list(one.strip_margins(h, self._line))

    @Slot(float, float, float, result=float)
    def heightAfterLineChange(self, h, old, new):     # O4
        return one.height_after_line_change(h, old, new)


    # ---------------------------------------------------------------- ações

    @Slot()
    def togglePlay(self):
        self.r.toggle_play()
        self.positionChanged.emit()

    @Slot(float)
    def skip(self, dt):
        self.r.skip(dt)
        self._after_nav()

    @Slot(float)
    def seekFraction(self, f):
        self.r.seek(f * self.r.session.duration)
        self._after_nav()

    @Slot(str)
    def seekLink(self, link):
        self.r.seek_link(link)
        self._after_nav()

    @Slot(int)
    def jumpBlock(self, d):
        self.r.jump_block(d)
        self._after_nav()

    @Slot(int)
    def adjustSpeed(self, step):
        self.r.adjust_speed(step)
        self.prefsChanged.emit()

    @Slot(int)
    def adjustFont(self, d):
        self.r.set_pref("font_size", self.r.prefs["font_size"] + d)
        self.prefsChanged.emit()

    @Property(str, notify=prefsChanged)
    def textColor(self):
        return self.r.prefs["text_color"]

    @Property(float, notify=prefsChanged)
    def textOpacity(self):
        return self.r.prefs["text_opacity"]

    @Slot(str)
    def setTextColor(self, color):                    # R8
        self.r.set_pref("text_color", color)
        self.model.refresh_all()
        self.prefsChanged.emit()

    @Slot(float)
    def setTextOpacity(self, v):                      # R8
        self.r.set_pref("text_opacity", round(v, 2))
        self.model.refresh_all()
        self.prefsChanged.emit()

    @Property(str, notify=prefsChanged)
    def bgColor(self):
        return self.r.prefs["bg_color"]

    @Property(str, notify=prefsChanged)
    def bgImage(self):
        img = self.r.prefs["bg_image"]
        return QUrl.fromLocalFile(img).toString() if img and Path(img).exists() else ""

    @Slot(str)
    def setBgColor(self, color):                      # R8
        self.r.set_pref("bg_color", color)
        self.prefsChanged.emit()

    @Slot(str, result=bool)
    def setBgImage(self, url):                        # R12 ("" remove)
        path = QUrl(url).toLocalFile() if url.startswith("file:") else url
        ok = self.r.set_background_image(path)
        self.prefsChanged.emit()
        return ok

    @Slot(float)
    def setBgOpacity(self, v):
        self.r.set_pref("bg_opacity", round(v, 2))
        self.prefsChanged.emit()

    @Slot()
    def toggleLock(self):
        self.r.toggle_lock()
        self.prefsChanged.emit()

    @Slot()
    def toggleClickThrough(self):
        self.r.set_pref("click_through", not self.r.prefs["click_through"])
        self.prefsChanged.emit()

    @Slot(int, int, int, int)
    def saveGeometry(self, x, y, w, h):
        self.r.set_pref("geometry", [x, y, int(self.layout.saved_width(w)), h])   # G5

    @Slot(float, float, float, float, result=float)
    def layoutImage(self, x, w, h, screen_right):
        """G1–G3, G6: abre espaço para a imagem atual; devolve a nova largura da janela."""
        from PySide6.QtGui import QImageReader
        size = QImageReader(str(self.cache / "images" / self.r.image)).size()
        if size.width() <= 0 or size.height() <= 0:
            return w
        lay = self.layout.show(x, w, h, screen_right, size.width(), size.height())
        self._panel = (lay.panel_w, lay.panel_h)
        self.imageChanged.emit()
        return lay.window_w

    @Slot(result=float)
    def restoreWidth(self):
        """G4: largura da janela antes da imagem (0 se ela não cresceu)."""
        self._panel = (0.0, 0.0)
        base = self.layout.hide()
        self.imageChanged.emit()          # G4: o QML relê o painel e o texto volta a se esticar
        return base if base is not None else 0.0

    @Property(float, notify=imageChanged)
    def imagePanelWidth(self):
        return self._panel[0]

    @Property(float, notify=imageChanged)
    def imagePanelHeight(self):
        return self._panel[1]

    @Slot(float, float, bool, bool, result=bool)
    def isVertical(self, w, h, oneline, now):
        return is_vertical(self.layout.saved_width(w), h, oneline, now)   # G7, G5

    @Slot(float, float, float, float, result="QVariantList")
    def inlineSize(self, text_w, win_h, img_w, img_h):
        return list(inline_size(text_w, win_h, img_w, img_h))   # G9

    @Property(float, constant=True)
    def imageGap(self):
        return GAP

    @Slot(float, float, float, float)
    def setInputRegion(self, x, y, w, h):
        """J3: só o retângulo (em pixels lógicos da janela) recebe o mouse."""
        from .x11 import set_input_region
        if getattr(self, "window", None) is None:
            return                        # janela ainda não criada
        dpr = self.window.devicePixelRatio()
        set_input_region(int(self.window.winId()),
                         [(int(x * dpr), int(y * dpr), int(w * dpr) + 1, int(h * dpr) + 1)])

    @Slot()
    def clearInputRegion(self):
        from .x11 import set_input_region
        if getattr(self, "window", None) is not None:
            set_input_region(int(self.window.winId()), None)

    @Slot()
    def quit(self):
        self.r.player.pause = True        # R11: silêncio já no clique
        self.app.quit()

    def _on_hotkey(self, action):                       # J8
        {"toggle_play": self.togglePlay,
         "back": lambda: self.skip(-10),
         "forward": lambda: self.skip(10),
         "prev_block": lambda: self.jumpBlock(-1),
         "next_block": lambda: self.jumpBlock(1),
         "slower": lambda: self.adjustSpeed(-1),
         "faster": lambda: self.adjustSpeed(1),
         "toggle_lock": self.toggleLock,
         "toggle_visible": self.visibilityToggleRequested.emit,
         }[action]()


def main(paths: list[str], model_size: str = "small", oneline: bool = False):
    from .library import Library
    from .session import Session

    lib = Library()
    bid, entry = lib.resolve(paths)
    cache = lib.cache(bid)

    fmt = QSurfaceFormat.defaultFormat()
    fmt.setAlphaBufferSize(8)
    QSurfaceFormat.setDefaultFormat(fmt)
    app = QGuiApplication(sys.argv)
    app.setApplicationName("scribe")

    session = Session.open(entry["epub"], entry["audio"], cache, model_size)
    lib.touch(bid, title=session.book["title"])
    for f in sorted((cache / "fonts").glob("*.[to]tf")):          # J7
        QFontDatabase.addApplicationFont(str(f))

    player = MpvPlayer(entry["audio"])
    reader = Reader(session, player, lib, bid)
    session.start_worker(reader.position)
    model = BlockModel(reader, cache)
    bridge = Bridge(app, reader, model, cache, oneline=oneline)

    try:
        from .hotkeys import DEFAULT, HotkeyListener
        hk = HotkeyListener({**DEFAULT, **lib.data["ui"].get("hotkeys", {})}, bridge.hotkey.emit)
        for combo in hk.failed:                                         # H1
            print(f"[atalhos] {combo} não foi registrado: já está em uso por outro programa "
                  f"(outra janela do scribe aberta?)", file=sys.stderr)
        hk.start()
    except Exception as e:
        print(f"[atalhos] indisponíveis: {e}", file=sys.stderr)

    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("reader", bridge)
    engine.rootContext().setContextProperty("blocks", model)
    engine.load(QUrl.fromLocalFile(str(HERE / "overlay.qml")))
    if not engine.rootObjects():
        sys.exit("Falha ao carregar a interface.")

    bridge.window = engine.rootObjects()[0]

    def shutdown():
        player.pause = True               # R11: antes de qualquer outra coisa
        bridge.timer.stop()               # J11: nada mais consulta o mpv depois daqui
        bridge.save_timer.stop()
        reader.close()
        session.stop_worker()
        player.close()

    app.aboutToQuit.connect(shutdown)
    code = app.exec()
    # J11: destrói a janela antes do motor QML; senão o motor zera `reader` primeiro e
    # todas as ligações da janela reclamam de ler propriedades de null
    from PySide6.QtCore import QCoreApplication, QEvent
    for obj in engine.rootObjects():
        obj.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    del engine
    sys.exit(code)
