"""C26 · The real backend — Win32, `ctypes` only, nothing else.

**This is the one file in `desktop/execution/` allowed to call
`ctypes.windll`.** Every other file in this package is platform-agnostic;
isolating the platform-specific mechanism here means a missing DLL or the
wrong operating system fails one import, never the package's.

`ctypes` is the standard library — this file adds **no third-party
dependency**. `pywin32` is not installed in this environment and nothing
here requires it.

## What each backend actually calls

| Backend | Win32 API |
|---|---|
| Window | `EnumWindows`, `GetForegroundWindow`, `SetForegroundWindow`, `AttachThreadInput`, `GetCurrentThreadId`, `ShowWindow`, `PostMessageW(WM_CLOSE)`, `GetWindowThreadProcessId` |
| Keyboard | `SendInput` with `KEYBDINPUT` — `KEYEVENTF_UNICODE` for `type_text` (full Unicode, not layout-dependent), virtual-key codes for `press`/`hotkey` |
| Mouse | `SetCursorPos`, `SendInput` with `MOUSEINPUT` for button state and the wheel |
| Clipboard | `OpenClipboard`/`EmptyClipboard`/`SetClipboardData`/`GetClipboardData`/`CloseClipboard` against `CF_UNICODETEXT`, with `GlobalAlloc`/`GlobalLock` for the buffer |

**`close()` posts `WM_CLOSE`, never `TerminateProcess` or a kill signal.**
A window that owns unsaved work gets the chance to prompt, the same
distinction `desktop/actions.py`'s own `CloseApplicationAction` already
draws between an application's own shutdown and a forced kill — that
forced kill is `ProcessExecutive.terminate()`'s job (`process.py`), reusing
the existing `CloseApplicationAction`, and this file does not duplicate it.

## What this file does not do

No screenshot, no pixel read, no `BitBlt`, no `GetPixel` — Window Manager
is forbidden OCR and vision, and there is no code path here that could
produce either. No registry (`RegOpenKeyEx` and family are never called),
no privilege API (`AdjustTokenPrivileges`, `ShellExecute` with
`runas` — neither appears), no install/uninstall surface. `tests/
test_desktop_execution.py`'s guards check this by AST across the whole
package, including this file.

## Verification status — read before trusting this file blindly

**This file was not exercised against a live desktop in the session that
wrote it.** Enumerating windows is read-only and was smoke-tested; moving
the mouse, sending keystrokes, and posting `WM_CLOSE` were not — doing so
from an autonomous coding session would hijack whatever the operator was
doing on their own screen, which is a materially different risk than
reading a machine inventory (C24's own safe live check). `Engineering/
HEALTH_C26.md` §11 records exactly what was and was not verified live, and
names this as the one component of C26 that most needs a human's first
real run.
"""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

from master_agent.desktop.execution.backends import BackendUnavailable, WindowInfo

if sys.platform != "win32":  # pragma: no cover — this repository targets win32
    raise BackendUnavailable(
        "the Win32 execution backend is only available on Windows"
    )

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# ---- window constants ----------------------------------------------------

SW_HIDE = 0
SW_MAXIMIZE = 3
SW_MINIMIZE = 6
SW_RESTORE = 9
WM_CLOSE = 0x0010

# ---- keyboard constants ---------------------------------------------------

INPUT_KEYBOARD = 1
INPUT_MOUSE = 0
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_SCANCODE = 0x0008

#: Names a founder or a workflow (C25) would actually use, mapped to
#: virtual-key codes. Closed — an unmapped name is refused rather than
#: guessed at.
VIRTUAL_KEYS: dict[str, int] = {
    "enter": 0x0D, "return": 0x0D,
    "escape": 0x1B, "esc": 0x1B,
    "delete": 0x2E, "del": 0x2E,
    "backspace": 0x08,
    "tab": 0x09,
    "space": 0x20,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "home": 0x24, "end": 0x23,
    "pageup": 0x21, "pagedown": 0x22,
    "ctrl": 0x11, "control": 0x11,
    "alt": 0x12,
    "shift": 0x10,
    "win": 0x5B, "windows": 0x5B, "meta": 0x5B, "cmd": 0x5B,
    **{chr(c): c for c in range(0x30, 0x3A)},  # '0'-'9'
    **{chr(c).lower(): c for c in range(0x41, 0x5B)},  # 'a'-'z' -> VK_A..VK_Z
    **{f"f{n}": 0x70 + n - 1 for n in range(1, 13)},  # f1-f12
}


def _vk_of(key: str) -> int:
    lowered = key.strip().lower()
    if lowered not in VIRTUAL_KEYS:
        raise ValueError(
            f"{key!r} is not a known key name; known names: "
            + ", ".join(sorted(VIRTUAL_KEYS))
        )
    return VIRTUAL_KEYS[lowered]


# ---- mouse constants -------------------------------------------------------

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
WHEEL_DELTA = 120

_BUTTON_DOWN = {
    "left": MOUSEEVENTF_LEFTDOWN,
    "right": MOUSEEVENTF_RIGHTDOWN,
    "middle": MOUSEEVENTF_MIDDLEDOWN,
}
_BUTTON_UP = {
    "left": MOUSEEVENTF_LEFTUP,
    "right": MOUSEEVENTF_RIGHTUP,
    "middle": MOUSEEVENTF_MIDDLEUP,
}

# ---- clipboard constants ---------------------------------------------------

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002

# ctypes' default calling convention marshals a WinDLL function's return
# value as a 32-bit `c_int` unless `restype` says otherwise. Every one of
# these four returns/accepts a real 64-bit pointer on x64 Windows (a
# `HANDLE`/`HGLOBAL`/`LPVOID`) — without this, the pointer silently
# truncates to 32 bits, and the next call that dereferences it (`GlobalLock`,
# `wstring_at`) reads garbage memory. Found live, this session: the very
# first real exercise of this backend against the actual system clipboard
# crashed with an access-violation `OSError` from a truncated pointer —
# exactly the risk this file's own module docstring already flagged as
# unverified live.
kernel32.GlobalAlloc.restype = ctypes.c_void_p
kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
kernel32.GlobalSize.restype = ctypes.c_size_t
kernel32.GlobalSize.argtypes = [ctypes.c_void_p]
user32.GetClipboardData.restype = ctypes.c_void_p
user32.GetClipboardData.argtypes = [wintypes.UINT]
user32.SetClipboardData.restype = ctypes.c_void_p
user32.SetClipboardData.argtypes = [wintypes.UINT, ctypes.c_void_p]
user32.RegisterClipboardFormatW.restype = wintypes.UINT
user32.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]

#: The standard, documented Windows opt-out password managers already use
#: (1Password, Bitwarden, Windows' own Credential Manager UI) to keep a
#: clipboard write out of Clipboard History (Win+V) and Cloud Clipboard
#: sync: register this format name and place *any* data — even zero bytes
#: — under it alongside the real `CF_UNICODETEXT` payload in the same
#: `SetClipboardData` sequence. Windows' own clipboard-history listener
#: checks for this format's presence and skips recording the clipboard
#: contents when it's there. Found live, this session: a real reasoning
#: prompt written to the shared clipboard was captured by something
#: outside this process — surviving even an immediate `EmptyClipboard()`
#: right after the paste, which rules out a listener that reads the
#: *live* clipboard at some later moment and points at a write-time
#: capture instead. Clipboard History is exactly that: a write-time
#: listener, present by default on Windows 11, and the single most likely
#: real-world source of this exact risk on any founder's own machine —
#: not specific to any development tooling.
CFSTR_EXCLUDE_FROM_MONITOR = "ExcludeClipboardContentFromMonitorProcessing"


# ---- SendInput structures --------------------------------------------------
# The documented layout (winuser.h). Defined once, used by both the
# keyboard and mouse backends below.


class _MOUSEINPUT(ctypes.Structure):
    # `_fields_` is `ctypes`' own required class-attribute API for
    # declaring a Structure's layout — not a mutable-default footgun.
    _fields_ = [
        ("dx", wintypes.LONG), ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
    ]


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", _MOUSEINPUT), ("ki", _KEYBDINPUT)]  # noqa: RUF012


class _INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", _INPUT_UNION)]


def _send_key_input(vk: int, key_up: bool) -> None:
    inp = _INPUT(type=INPUT_KEYBOARD)
    inp.union.ki = _KEYBDINPUT(
        wVk=vk, wScan=0,
        dwFlags=KEYEVENTF_KEYUP if key_up else 0,
        time=0, dwExtraInfo=None,
    )
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))


def _send_unicode_input(char: str, key_up: bool) -> None:
    inp = _INPUT(type=INPUT_KEYBOARD)
    flags = KEYEVENTF_UNICODE | (KEYEVENTF_KEYUP if key_up else 0)
    inp.union.ki = _KEYBDINPUT(
        wVk=0, wScan=ord(char), dwFlags=flags, time=0, dwExtraInfo=None,
    )
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))


def _send_mouse_input(dx: int, dy: int, data: int, flags: int) -> None:
    inp = _INPUT(type=INPUT_MOUSE)
    inp.union.mi = _MOUSEINPUT(
        dx=dx, dy=dy, mouseData=data, dwFlags=flags, time=0, dwExtraInfo=None,
    )
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))


class Win32WindowBackend:
    """Window operations only. No OCR, no pixel is ever read."""

    def enumerate(self) -> tuple[WindowInfo, ...]:
        found: list[WindowInfo] = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def _callback(hwnd: int, _lparam: int) -> bool:
            length = user32.GetWindowTextLengthW(hwnd)
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            pid = wintypes.DWORD(0)
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            found.append(
                WindowInfo(
                    handle=hwnd,
                    title=buffer.value,
                    process_id=pid.value,
                    is_visible=bool(user32.IsWindowVisible(hwnd)),
                    is_minimized=bool(user32.IsIconic(hwnd)),
                    is_maximized=bool(user32.IsZoomed(hwnd)),
                )
            )
            return True

        user32.EnumWindows(_callback, 0)
        return tuple(found)

    def active(self) -> WindowInfo | None:
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None
        for window in self.enumerate():
            if window.handle == hwnd:
                return window
        return None

    def bring_to_front(self, handle: int) -> bool:
        """A bare `SetForegroundWindow` is refused by Windows' own
        anti-focus-stealing lock whenever the calling process is not
        itself the current foreground process — confirmed live: it
        succeeds immediately after this process's own `execute()` just
        launched `handle`'s process (the OS grants the launching process a
        one-time allowance), then fails silently on a later, independent
        call once focus has moved elsewhere. `AttachThreadInput` is
        Microsoft's own documented workaround for exactly this
        (`SetForegroundWindow`'s MSDN Remarks): briefly sharing input
        state with whichever thread currently holds the foreground lets
        this thread's `SetForegroundWindow` call succeed as that thread's
        own call would, then the threads are detached again immediately —
        never left attached.
        """
        foreground = user32.GetForegroundWindow()
        current_thread = kernel32.GetCurrentThreadId()
        foreground_pid = wintypes.DWORD(0)
        foreground_thread = (
            user32.GetWindowThreadProcessId(foreground, ctypes.byref(foreground_pid))
            if foreground else 0
        )

        attached = False
        if foreground_thread and foreground_thread != current_thread:
            attached = bool(
                user32.AttachThreadInput(current_thread, foreground_thread, 1)
            )

        try:
            # A minimized window ignores SetForegroundWindow outright;
            # restore it first so the call has a normal, visible window.
            if user32.IsIconic(handle):
                user32.ShowWindow(handle, SW_RESTORE)
            result = bool(user32.SetForegroundWindow(handle))
        finally:
            if attached:
                user32.AttachThreadInput(current_thread, foreground_thread, 0)
        return result

    def minimize(self, handle: int) -> bool:
        return bool(user32.ShowWindow(handle, SW_MINIMIZE))

    def maximize(self, handle: int) -> bool:
        return bool(user32.ShowWindow(handle, SW_MAXIMIZE))

    def restore(self, handle: int) -> bool:
        return bool(user32.ShowWindow(handle, SW_RESTORE))

    def close(self, handle: int) -> bool:
        """Posts `WM_CLOSE` — asks the window to close itself, exactly
        the way its own title-bar close button would. Never a forced
        kill; see the module docstring."""
        return bool(user32.PostMessageW(handle, WM_CLOSE, 0, 0))


class Win32KeyboardBackend:
    def type_text(self, text: str) -> None:
        for char in text:
            _send_unicode_input(char, key_up=False)
            _send_unicode_input(char, key_up=True)

    def press(self, key: str) -> None:
        vk = _vk_of(key)
        _send_key_input(vk, key_up=False)
        _send_key_input(vk, key_up=True)

    def hotkey(self, keys: tuple[str, ...]) -> None:
        vks = [_vk_of(k) for k in keys]
        for vk in vks:
            _send_key_input(vk, key_up=False)
        for vk in reversed(vks):
            _send_key_input(vk, key_up=True)


class Win32MouseBackend:
    def move(self, x: int, y: int) -> None:
        user32.SetCursorPos(x, y)

    def click(self, x: int, y: int, button: str) -> None:
        if button not in _BUTTON_DOWN:
            raise ValueError(f"unknown button: {button!r} (known: left, right, middle)")
        self.move(x, y)
        _send_mouse_input(0, 0, 0, _BUTTON_DOWN[button])
        _send_mouse_input(0, 0, 0, _BUTTON_UP[button])

    def double_click(self, x: int, y: int, button: str) -> None:
        self.click(x, y, button)
        self.click(x, y, button)

    def drag(self, x1: int, y1: int, x2: int, y2: int) -> None:
        self.move(x1, y1)
        _send_mouse_input(0, 0, 0, MOUSEEVENTF_LEFTDOWN)
        self.move(x2, y2)
        _send_mouse_input(0, 0, 0, MOUSEEVENTF_LEFTUP)

    def scroll(self, x: int, y: int, amount: int) -> None:
        self.move(x, y)
        _send_mouse_input(0, 0, amount * WHEEL_DELTA, MOUSEEVENTF_WHEEL)


class Win32ClipboardBackend:
    """No history — the brief's own words. Every method acts on the
    single, current system clipboard and nothing else."""

    def read(self) -> str | None:
        if not user32.OpenClipboard(0):
            raise BackendUnavailable("could not open the clipboard")
        try:
            handle = user32.GetClipboardData(CF_UNICODETEXT)
            if not handle:
                return None
            locked = kernel32.GlobalLock(handle)
            if not locked:
                return None
            try:
                # Bounded by the allocation's own reported size rather than
                # trusting a null terminator inside memory this process
                # didn't allocate — the real, live-found crash this guards
                # against (see the restype comment above).
                byte_size = kernel32.GlobalSize(handle)
                max_chars = max(byte_size // ctypes.sizeof(ctypes.c_wchar) - 1, 0)
                return ctypes.wstring_at(locked, max_chars)
            except OSError as exc:
                raise BackendUnavailable(f"could not read clipboard memory: {exc}") from exc
            finally:
                kernel32.GlobalUnlock(handle)
        finally:
            user32.CloseClipboard()

    def write(self, text: str) -> None:
        data = text + "\0"
        size = len(data) * ctypes.sizeof(ctypes.c_wchar)
        handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, size)
        if not handle:
            raise BackendUnavailable("could not allocate clipboard memory")
        locked = kernel32.GlobalLock(handle)
        ctypes.memmove(locked, data, size)
        kernel32.GlobalUnlock(handle)

        if not user32.OpenClipboard(0):
            raise BackendUnavailable("could not open the clipboard")
        try:
            user32.EmptyClipboard()
            user32.SetClipboardData(CF_UNICODETEXT, handle)
            # Opt this write out of Clipboard History / Cloud Clipboard —
            # see the format constant's own docstring above. Only the
            # format's *presence* is checked, not its content, but
            # `GlobalAlloc(..., 0)` returns NULL on this platform (a real,
            # live-found bug: the marker silently never got set, and this
            # exclusion path was a no-op the one time it mattered) — a
            # 1-byte allocation is the smallest one that actually succeeds.
            exclude_format = user32.RegisterClipboardFormatW(CFSTR_EXCLUDE_FROM_MONITOR)
            marker = kernel32.GlobalAlloc(GMEM_MOVEABLE, 1)
            if marker:
                user32.SetClipboardData(exclude_format, marker)
        finally:
            user32.CloseClipboard()

    def clear(self) -> None:
        if not user32.OpenClipboard(0):
            raise BackendUnavailable("could not open the clipboard")
        try:
            user32.EmptyClipboard()
        finally:
            user32.CloseClipboard()
