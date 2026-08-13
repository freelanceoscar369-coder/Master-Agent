"""Desktop Executive Foundation 1.0 — semantic targeting and text
interaction for classic Win32 controls.

**Scoped honestly.** This is not Windows UI Automation (`IUIAutomation`);
nothing in this repository speaks that COM interface today, and standing
one up correctly (element caching, tree navigation, pattern invocation,
apartment threading) is real, separate work this foundation names as a
remaining gap rather than rushes. What this module *does* do is real and
useful now: every classic Win32 control (`Edit`, `Static`, `Button`) has
carried a documented, stable messaging contract since Windows 3.x —
`WM_GETTEXT`/`WM_SETTEXT`/`WM_GETTEXTLENGTH`/`BM_CLICK` — and reading or
writing a control's value through it is exactly as "semantic" as a UIA
`ValuePattern`/`InvokePattern` call: it targets the control by identity
(its child HWND and class name), never a screen coordinate, and Notepad's
own edit area is one.

Everything here is `ctypes`-only, the same isolation
`execution/win32_backends.py` and `perception/integrity.py` already
established: a platform-detection failure fails this one import, never
the package's.
"""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from dataclasses import dataclass
from typing import Protocol

if sys.platform != "win32":  # pragma: no cover — this repository targets win32
    raise ImportError("text_control is only available on Windows")

user32 = ctypes.windll.user32

WM_GETTEXT = 0x000D
WM_GETTEXTLENGTH = 0x000E
WM_SETTEXT = 0x000C
BM_CLICK = 0x00F5

_SMTO_ABORTIFHUNG = 0x0002
#: Bounded, the same reasoning `perception/win32_probe.py`'s own
#: `Win32ResponsivenessBackend` already states: a plain, blocking
#: `SendMessageW` waits forever if the target's message loop never
#: services it. A modern (WinUI3/XAML-hosted) window's non-classic child
#: windows — `Microsoft.UI.Content.DesktopChildSiteBridge`,
#: `InputSiteWindowClass`, and similar composition/input-bridge windows
#: `EnumChildWindows` also returns — are exactly this risk: they are real
#: HWNDs, but nothing guarantees they answer `WM_GETTEXT` at all, and one
#: that does not would otherwise hang every enumeration that touches it,
#: not just the one call.
_TIMEOUT_MS = 500

# `ctypes.windll.user32` is one shared, process-wide object — every module
# that does `ctypes.windll.user32` gets the *same* underlying function
# objects. Setting `.argtypes`/`.restype` directly on
# `user32.SendMessageTimeoutW` would silently change what
# `perception/win32_probe.py`'s own, independently-typed call to the same
# API sees, in either direction — exactly the kind of cross-module
# action-at-a-distance this package's whole `ctypes`-isolation discipline
# exists to prevent. `ctypes.WINFUNCTYPE(...)(("Name", dll))` binds a
# *second*, independent function object to the same DLL export — the
# correct types apply only to calls made through this module's own bound
# reference.
_SendMessageTimeoutW = ctypes.WINFUNCTYPE(
    ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
    wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_size_t),
)(("SendMessageTimeoutW", user32))
_EnumChildWindows = ctypes.WINFUNCTYPE(
    wintypes.BOOL, wintypes.HWND, ctypes.c_void_p, wintypes.LPARAM,
)(("EnumChildWindows", user32))
_GetClassNameW = ctypes.WINFUNCTYPE(
    ctypes.c_int, wintypes.HWND, wintypes.LPWSTR, ctypes.c_int,
)(("GetClassNameW", user32))


def _send_message_bounded(handle: int, msg: int, wparam: int, lparam: int) -> int | None:
    """`SendMessageTimeoutW` with `SMTO_ABORTIFHUNG` — returns `None`
    (never raises, never blocks past `_TIMEOUT_MS`) when the target does
    not answer, exactly the "an unresponsive window is an honest result,
    not a hang" discipline `win32_probe.py` already established for
    responsiveness probing generally; this is that same discipline
    applied to every message this module sends."""
    result = ctypes.c_size_t(0)
    sent = _SendMessageTimeoutW(
        handle, msg, wparam, lparam,
        _SMTO_ABORTIFHUNG, _TIMEOUT_MS, ctypes.byref(result),
    )
    if not sent:
        return None
    return result.value


class ControlNotFound(RuntimeError):
    """No child control matched the target — carried as an exception at
    this one boundary (unlike the rest of this package's `ExecutionResult`
    convention) because `TargetResolver` is a pure lookup with nothing to
    execute; the caller turns this into a structured failure."""


@dataclass(frozen=True)
class ControlInfo:
    """One child window, resolved to enough identity to act on and to
    explain the match afterward — the "what was selected, why, with what
    confidence" provenance every target in this foundation is meant to
    carry."""

    handle: int
    class_name: str
    text: str
    matched_by: str


class ChildEnumBackend(Protocol):
    def children_of(self, parent_handle: int) -> tuple[tuple[int, str, str], ...]: ...

    def get_text(self, handle: int) -> str: ...

    def set_text(self, handle: int, text: str) -> bool: ...

    def click(self, handle: int) -> bool: ...


class Win32ChildEnumBackend:
    """`EnumChildWindows` + `GetClassNameW` for identity,
    `WM_GETTEXT`/`WM_SETTEXT`/`BM_CLICK` for value/action. Every
    `SendMessageW` here targets a specific child HWND already resolved by
    identity — never a coordinate, never the desktop-wide window list."""

    def children_of(self, parent_handle: int) -> tuple[tuple[int, str, str], ...]:
        found: list[tuple[int, str, str]] = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def _callback(hwnd: int, _lparam: int) -> bool:
            class_buf = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, class_buf, 256)
            found.append((hwnd, class_buf.value, self.get_text(hwnd)))
            return True

        user32.EnumChildWindows(parent_handle, _callback, 0)
        return tuple(found)

    def get_text(self, handle: int) -> str:
        length = _send_message_bounded(handle, WM_GETTEXTLENGTH, 0, 0)
        if not length or length <= 0:
            return ""
        buffer = ctypes.create_unicode_buffer(length + 1)
        _send_message_bounded(handle, WM_GETTEXT, length + 1, ctypes.addressof(buffer))
        return buffer.value

    def set_text(self, handle: int, text: str) -> bool:
        buffer = ctypes.create_unicode_buffer(text)
        result = _send_message_bounded(handle, WM_SETTEXT, 0, ctypes.addressof(buffer))
        return bool(result)

    def click(self, handle: int) -> bool:
        result = _send_message_bounded(handle, BM_CLICK, 0, 0)
        return result is not None


class NullChildEnumBackend:
    def children_of(self, parent_handle: int) -> tuple[tuple[int, str, str], ...]:
        raise ControlNotFound("no child-control backend is configured")

    def get_text(self, handle: int) -> str:
        raise ControlNotFound("no child-control backend is configured")

    def set_text(self, handle: int, text: str) -> bool:
        raise ControlNotFound("no child-control backend is configured")

    def click(self, handle: int) -> bool:
        raise ControlNotFound("no child-control backend is configured")


#: Tried in order when a caller does not name a specific class. `Edit` is
#: the classic Win32 control (Notepad on Windows ≤10, most native dialogs);
#: `NotepadTextBox` is Windows 11's WinUI3-hosted Notepad — confirmed live
#: on this machine to still answer `WM_GETTEXT`/`WM_SETTEXT` despite being
#: XAML-rendered; `RichEditD2DPT`/`RICHEDIT50W` cover WordPad-family rich
#: text controls. Not exhaustive — a caller that knows its target's real
#: class name should still pass it explicitly.
DEFAULT_TEXT_CONTROL_CLASSES: tuple[str, ...] = (
    "Edit", "NotepadTextBox", "RichEditD2DPT", "RICHEDIT50W", "RichEdit20W",
)

#: Universal Autonomous Desktop Executive — Section 3's "select the
#: mechanism based on discovered characteristics", implemented as a
#: cheap, read-only classifier: if a window's direct children include
#: one of these composition/render-host markers, its real content is
#: rendered by something other than classic Win32 controls, and no
#: amount of `EnumChildWindows`/`WM_GETTEXT` will ever reach it —
#: confirmed live, Claude Desktop's window has exactly
#: `Chrome_RenderWidgetHostHWND` + a D3D composition window as its only
#: direct children. `Chrome_WidgetWin_1` (the top-level Chromium frame
#: class itself) and the WinUI3/UWP composition-bridge classes are
#: included for the same reason.
_RENDER_HOST_MARKER_CLASSES: tuple[str, ...] = (
    "Chrome_RenderWidgetHostHWND",
    "Chrome_WidgetWin_1",
    "Intermediate D3D Window",
    "Windows.UI.Composition.DesktopWindowContentBridge",
    "Microsoft.UI.Content.DesktopChildSiteBridge",
    "InputSiteWindowClass",
)


def classify_window(window_handle: int, backend: "ChildEnumBackend") -> str:
    """`"classic"` if a known classic text-control class already answers
    on this window (the fast, cheap path — no COM, no UIA tree walk);
    `"uia_required"` otherwise. A window with *neither* a classic control
    nor a recognized render-host marker among its direct children still
    classifies `"uia_required"` — UIA is the correct general fallback
    for anything this heuristic doesn't recognize, not a reason to give
    up early."""
    try:
        children = backend.children_of(window_handle)
    except Exception:  # noqa: BLE001 — an unreadable window is not "classic"
        return "uia_required"
    classes = {class_name for _, class_name, _ in children}
    if classes & set(DEFAULT_TEXT_CONTROL_CLASSES):
        return "classic"
    return "uia_required"


class ClassicControlResolver:
    """Target resolution over one window's *direct* child controls —
    deliberately not a recursive desktop-wide crawl (§6/§8 of the
    foundation brief: scoped, never a desktop-wide search). Matches by
    class name first (`"Edit"`, `"Button"`, `"Static"` — a control's own
    stable identity), falling back to a text/name substring — the same
    two-tier "structural first, then a named fallback" order
    `execution/window.py::locate()` already uses for windows.
    """

    def __init__(self, backend: ChildEnumBackend | None = None) -> None:
        self._backend = backend or NullChildEnumBackend()

    def find(
        self, parent_handle: int, class_name: str | None = None, text_contains: str | None = None
    ) -> ControlInfo:
        children = self._backend.children_of(parent_handle)
        if not children:
            raise ControlNotFound(f"window {parent_handle} has no child controls")

        # An explicit class name is tried alone (the caller knows what it
        # wants); omitted, every known text-control class is tried in
        # turn — still a class-name match, never a coordinate or a
        # desktop-wide search.
        candidates = (class_name,) if class_name else DEFAULT_TEXT_CONTROL_CLASSES
        for candidate in candidates:
            matches = [c for c in children if c[1].lower() == candidate.lower()]
            if matches:
                handle, found_class, text = matches[0]
                return ControlInfo(handle, found_class, text, matched_by="class_name")

        if text_contains:
            needle = text_contains.lower()
            matches = [c for c in children if needle in c[2].lower()]
            if matches:
                handle, found_class, text = matches[0]
                return ControlInfo(handle, found_class, text, matched_by="text")

        raise ControlNotFound(
            f"no child of window {parent_handle} matched "
            f"class_name={class_name!r} text_contains={text_contains!r} "
            f"(considered {len(children)} child control(s))"
        )

    def read_text(self, control: ControlInfo) -> str:
        return self._backend.get_text(control.handle)

    def write_text(self, control: ControlInfo, text: str) -> bool:
        return self._backend.set_text(control.handle, text)

    def click(self, control: ControlInfo) -> bool:
        return self._backend.click(control.handle)
