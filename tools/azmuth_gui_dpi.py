"""Window-local DPI setup, logical canvas coordinates, and live display updates."""

from __future__ import annotations

import copy
import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import logging
import os
import tkinter as tk
from tkinter import font as tkfont
import weakref

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DisplayInfo:
    dpi: int = 96
    work_area: tuple[int, int, int, int] = (0, 0, 1920, 1080)
    per_monitor_v2: bool = False
    warning: str = ""

    @property
    def scale(self) -> float:
        return self.dpi / 96.0


class WindowsDpi:
    """All native operations stay on the thread that owns the GUI."""

    def __init__(self):
        self.user = ctypes.WinDLL("user32", use_last_error=True)
        self._declare(self.user, "SetProcessDpiAwarenessContext", wintypes.BOOL, ctypes.c_void_p)
        self._declare(self.user, "SetThreadDpiAwarenessContext", ctypes.c_void_p, ctypes.c_void_p)
        self._declare(self.user, "GetThreadDpiAwarenessContext", ctypes.c_void_p)
        self._declare(self.user, "GetWindowDpiAwarenessContext", ctypes.c_void_p, wintypes.HWND)
        self._declare(self.user, "AreDpiAwarenessContextsEqual", wintypes.BOOL, ctypes.c_void_p, ctypes.c_void_p)
        self._declare(self.user, "GetDpiForWindow", wintypes.UINT, wintypes.HWND)
        self._declare(self.user, "GetAncestor", wintypes.HWND, wintypes.HWND, wintypes.UINT)
        self._declare(self.user, "MonitorFromWindow", wintypes.HANDLE, wintypes.HWND, wintypes.DWORD)
        self._declare(self.user, "GetMonitorInfoW", wintypes.BOOL, wintypes.HANDLE, ctypes.c_void_p)
        self._declare(self.user, "GetWindowRect", wintypes.BOOL, wintypes.HWND, ctypes.POINTER(wintypes.RECT))
        self._declare(self.user, "SetWindowPos", wintypes.BOOL, wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT)

    @staticmethod
    def _declare(library, name, result, *args):
        function = getattr(library, name)
        function.restype, function.argtypes = result, list(args)
        return function

    def is_v2(self, context) -> bool:
        return bool(self.user.AreDpiAwarenessContextsEqual(context, ctypes.c_void_p(-4)))

    def prepare(self) -> str:
        if self.is_v2(self.user.GetThreadDpiAwarenessContext()):
            return ""
        self.user.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        if not self.is_v2(self.user.GetThreadDpiAwarenessContext()):
            # Python may have a manifest or inherited compatibility override.
            previous = self.user.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))
            if not previous:
                return f"Windows compatibility scaling could not be disabled (error {ctypes.get_last_error()})."
        if not self.is_v2(self.user.GetThreadDpiAwarenessContext()):
            return "The GUI thread is not per-monitor DPI aware. Windows may blur this window."
        return ""

    def hwnd(self, root) -> int:
        return self.user.GetAncestor(root.winfo_id(), 2) or root.winfo_id()

    def snapshot(self, hwnd) -> DisplayInfo:
        class MonitorInfo(ctypes.Structure):
            _fields_ = [("size", wintypes.DWORD), ("monitor", wintypes.RECT), ("work", wintypes.RECT), ("flags", wintypes.DWORD)]
        info = MonitorInfo()
        info.size = ctypes.sizeof(info)
        if not self.user.GetMonitorInfoW(self.user.MonitorFromWindow(hwnd, 2), ctypes.byref(info)):
            raise ctypes.WinError(ctypes.get_last_error())
        dpi = self.user.GetDpiForWindow(hwnd)
        if not dpi:
            raise ctypes.WinError(ctypes.get_last_error())
        aware = self.is_v2(self.user.GetWindowDpiAwarenessContext(hwnd))
        return DisplayInfo(dpi, (info.work.left, info.work.top, info.work.right, info.work.bottom), aware,
                           "" if aware else "Windows compatibility scaling is active; text may be blurred.")

    def set_rect(self, hwnd, rect) -> None:
        x0, y0, x1, y1 = rect
        if not self.user.SetWindowPos(hwnd, None, x0, y0, x1 - x0, y1 - y0, 0x14):
            raise ctypes.WinError(ctypes.get_last_error())

    def clamp_window(self, hwnd, work) -> None:
        rect = wintypes.RECT()
        if not self.user.GetWindowRect(hwnd, ctypes.byref(rect)):
            raise ctypes.WinError(ctypes.get_last_error())
        x0, y0, x1, y1 = work
        width, height = min(rect.right - rect.left, x1 - x0), min(rect.bottom - rect.top, y1 - y0)
        left, top = min(max(rect.left, x0), x1 - width), min(max(rect.top, y0), y1 - height)
        target = (left, top, left + width, top + height)
        if target != (rect.left, rect.top, rect.right, rect.bottom):
            self.set_rect(hwnd, target)

    def install_hook(self, hwnd, notify):
        library = ctypes.WinDLL("comctl32", use_last_error=True)
        callback_type = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM, ctypes.c_size_t, ctypes.c_size_t)
        self._declare(library, "DefSubclassProc", ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
        self._declare(library, "SetWindowSubclass", wintypes.BOOL, wintypes.HWND, callback_type, ctypes.c_size_t, ctypes.c_size_t)
        self._declare(library, "RemoveWindowSubclass", wintypes.BOOL, wintypes.HWND, callback_type, ctypes.c_size_t)

        @callback_type
        def callback(window, message, wparam, lparam, identifier, data):
            try:
                if message == 0x02E0:  # WM_DPICHANGED; copy lParam before returning.
                    rect = ctypes.cast(lparam, ctypes.POINTER(wintypes.RECT)).contents
                    self.set_rect(window, (rect.left, rect.top, rect.right, rect.bottom))
                    notify()
                elif message in (0x007E, 0x001A):  # display or settings changed
                    notify()
            except Exception:
                logger.exception("Display notification failed")
            return library.DefSubclassProc(window, message, wparam, lparam)

        if not library.SetWindowSubclass(hwnd, callback, 1, 0):
            raise ctypes.WinError(ctypes.get_last_error())
        return library, callback

    def remove_hook(self, hwnd, hook) -> None:
        library, callback = hook
        if not library.RemoveWindowSubclass(hwnd, callback, 1):
            raise ctypes.WinError(ctypes.get_last_error())


def create_gui_root(*, backend=None) -> tk.Tk:
    """The common direct/tray/batch startup path, before any HWND is created."""
    warning = ""
    if backend is None and os.name == "nt":
        try:
            backend = WindowsDpi()
        except (OSError, AttributeError) as exc:
            warning = f"Native display scaling is unavailable: {exc}"
    if backend is not None:
        try:
            warning = backend.prepare()
        except OSError as exc:
            warning = f"Windows DPI awareness could not be enabled: {exc}"
    root = tk.Tk()
    root.withdraw()
    root._azmuth_dpi_backend = backend
    try:
        info = backend.snapshot(backend.hwnd(root)) if backend else DisplayInfo(work_area=(0, 0, root.winfo_screenwidth(), root.winfo_screenheight()))
    except OSError as exc:
        info = DisplayInfo(warning=f"Cannot verify window DPI: {exc}")
    if warning:
        info = DisplayInfo(info.dpi, info.work_area, info.per_monitor_v2, warning)
    root._azmuth_display_info = info
    root.tk.call("tk", "scaling", info.dpi / 72.0)
    if info.warning:
        logger.warning(info.warning)
    return root


class FontRegistry:
    def __init__(self, root):
        self.root, self.fonts = root, {}

    def get(self, family="Segoe UI", size=9, weight="normal"):
        key = family, max(8, int(size)), weight
        if key not in self.fonts:
            self.fonts[key] = tkfont.Font(root=self.root, family=key[0], size=key[1], weight=key[2])
        return self.fonts[key]

    def refresh(self):
        for (family, size, weight), font in self.fonts.items():
            font.configure(family=family, size=size, weight=weight)


class LogicalCanvas(tk.Canvas):
    """Canvas geometry and hit testing use DIPs; Tk renders fonts at native DPI."""
    def __init__(self, *args, device_scale=1.0, fonts=None, **kwargs):
        self.device_scale, self.fonts = device_scale, fonts
        super().__init__(*args, **kwargs)

    def _create(self, item_type, args, kwargs):
        coordinates = tuple(float(value) * self.device_scale for value in tk._flatten(args))
        options = dict(kwargs)
        for key in ("width",):
            if key in options:
                options[key] = float(options[key]) * self.device_scale
        for key in ("arrowshape", "dash"):
            if options.get(key):
                options[key] = tuple(max(1, round(value * self.device_scale)) for value in options[key])
        if item_type == "text" and isinstance(options.get("font"), tuple) and self.fonts:
            options["font"] = self.fonts.get(*options["font"])
        return super()._create(item_type, coordinates, options)

    def bbox(self, *args):
        bounds = super().bbox(*args)
        return tuple(value / self.device_scale for value in bounds) if bounds else None

    def bind(self, sequence=None, func=None, add=None):
        if func and sequence and any(part in sequence for part in ("Button", "Motion", "Wheel")):
            original = func
            def logical_event(event):
                event = copy.copy(event)
                event.x, event.y = event.x / self.device_scale, event.y / self.device_scale
                return original(event)
            func = logical_event
        return super().bind(sequence, func, add)


class LayoutScaler:
    """Remember authored pixel spacing, so repeated DPI transitions never compound."""
    def __init__(self):
        self.widgets = weakref.WeakKeyDictionary()

    def apply(self, root, scale):
        pending = [root]
        while pending:
            widget = pending.pop()
            pending.extend(widget.winfo_children())
            if widget not in self.widgets:
                options = {key: float(widget.cget(key)) for key in ("padx", "pady", "borderwidth", "highlightthickness", "sashwidth") if key in widget.keys()}
                manager = widget.winfo_manager()
                geometry = widget.pack_info() if manager == "pack" else widget.grid_info() if manager == "grid" else {}
                spacing = {key: tuple(float(value) for value in str(geometry[key]).replace("(", "").replace(")", "").replace(",", "").split()) for key in ("padx", "pady", "ipadx", "ipady") if key in geometry}
                self.widgets[widget] = options, manager, spacing
            options, manager, spacing = self.widgets[widget]
            if options:
                widget.configure(**{key: round(value * scale) for key, value in options.items()})
            if widget.winfo_manager() == manager and spacing:
                scaled = {key: tuple(round(value * scale) for value in values) for key, values in spacing.items()}
                if manager == "pack":
                    widget.pack_configure(**scaled)
                elif manager == "grid":
                    widget.grid_configure(**scaled)


class DpiController:
    """Coalesce native notices and poll as a fallback, only on Tk's owning thread."""
    def __init__(self, root, backend, initial, on_change):
        self.root, self.backend, self.current, self.on_change = root, backend, initial, on_change
        self.closed, self.dirty, self.hook, self.after_id = False, False, None, None
        self.hwnd = backend.hwnd(root)
        try:
            self.hook = backend.install_hook(self.hwnd, self.notify)
        except OSError:
            logger.exception("Native DPI hook unavailable; polling remains active")
        self.after_id = root.after(250, self.poll)

    def notify(self):
        self.dirty = True

    def poll(self):
        if self.closed:
            return
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None
        try:
            info = self.backend.snapshot(self.hwnd)
            if info != self.current or self.dirty:
                changed = info != self.current
                self.dirty = False
                if changed:
                    self.on_change(info)
                self.backend.clamp_window(self.hwnd, info.work_area)
                if changed:
                    self.current = info
        except Exception:
            logger.exception("Display refresh failed; retrying")
        finally:
            if not self.closed:
                self.after_id = self.root.after(250, self.poll)

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None
        if self.hook is not None:
            try:
                self.backend.remove_hook(self.hwnd, self.hook)
                self.hook = None
            except OSError:
                # Keep the callback alive until the root's native destruction.
                logger.exception("DPI hook removal failed during close")
