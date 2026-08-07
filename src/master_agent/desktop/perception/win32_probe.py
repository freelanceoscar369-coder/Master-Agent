"""C27 · The one new machine-touching primitive this layer needs:
*"is this window actually responding?"*

Every other fact C27 reports is read from something C24–C26 already
expose. This one is not, because nothing before this brief needed to ask
it: **`ApplicationHung` cannot be honestly reported without it.** Without
this signal, "hung" would have to be guessed from elapsed time alone —
exactly the assumption the brief forbids (*"Must never assume. Evidence
only."*).

## What it calls, and why it is read-only

`SendMessageTimeoutW(hwnd, WM_NULL, 0, 0, SMTO_ABORTIFHUNG, timeout_ms,
&result)` — the identical technique Windows' own Task Manager uses to
mark a process *"Not Responding."* `WM_NULL` is a message every window
procedure is required to handle as a no-op; sending it changes nothing
about the window's state. `SMTO_ABORTIFHUNG` makes the call itself
time-bound rather than blocking indefinitely on a genuinely wedged
window. Nothing here draws a pixel, clicks, focuses, or posts a message
that does anything — the same `ctypes`-only, no-`pywin32` approach
`desktop/execution/win32_backends.py` already established, isolated in
its own file for the identical reason that one is: a platform-detection
failure here fails one import, never the package's.

## Why this lives in `perception/`, not `execution/`

`desktop/execution/win32_backends.py` is C26's own deliverable and this
brief does not modify it (*"Do NOT redesign… Desktop Executive"*).
Probing responsiveness is a new read, not a new way to act — it belongs
beside the layer that reads, not the layer that acts.
"""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from typing import Protocol


class ResponsivenessUnavailable(RuntimeError):
    """This probe cannot run here — wrong platform, or the mechanism is
    absent. Never raised for an ordinary "the window is hung" result,
    which is a normal, valid answer, not a failure of this probe."""


class ResponsivenessBackend(Protocol):
    def is_responding(self, handle: int, timeout_ms: int = 500) -> bool: ...


class NullResponsivenessBackend:
    """Reports honestly that it cannot say — never guesses `True`."""

    def is_responding(self, handle: int, timeout_ms: int = 500) -> bool:
        raise ResponsivenessUnavailable("no responsiveness backend is configured")


class Win32ResponsivenessBackend:
    """`SendMessageTimeoutW` against `WM_NULL`. See the module docstring."""

    _SMTO_ABORTIFHUNG = 0x0002
    _WM_NULL = 0x0000

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise ResponsivenessUnavailable(
                "the Win32 responsiveness probe is only available on Windows"
            )
        self._user32 = ctypes.windll.user32

    def is_responding(self, handle: int, timeout_ms: int = 500) -> bool:
        result = wintypes.DWORD(0)
        sent = self._user32.SendMessageTimeoutW(
            handle, self._WM_NULL, 0, 0,
            self._SMTO_ABORTIFHUNG, timeout_ms, ctypes.byref(result),
        )
        return bool(sent)
