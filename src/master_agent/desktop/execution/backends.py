"""C26 · Execution backends — the seam between mechanism and platform.

Four capabilities — windows, keyboard, mouse, clipboard — and each is a
`Protocol` with two implementations, the same shape `desktop/probe.py`
already established for `SystemProbe`/`NullSystemProbe`/`RealSystemProbe`:

| | What it does |
|---|---|
| `Null*Backend` | Never touches the machine. Every call reports an honest failure — `BackendUnavailable` — rather than a silent no-op that looks like success. |
| `Win32*Backend` (`win32_backends.py`) | The real thing, `ctypes`-only, Windows-only. Not imported here — see below. |

**Why the real backend lives in a separate module.** `win32_backends.py`
is the one file in this package allowed to call `ctypes.windll` — every
other file, including this one, is platform-agnostic and imports nothing
that could reach the operating system. Isolating the real implementation
means a platform-detection bug or a missing DLL fails one file's import,
never this package's.

## `BackendUnavailable` is the only failure vocabulary

No backend method raises for an ordinary operational failure — a window
that will not come to front, a click that lands on nothing — that is
reported through `ExecutionResult` at the controller layer, the same
convention every `Action` in this codebase already uses. `Backend
Unavailable` is reserved for a structural fact: *this backend cannot run
at all here* (wrong platform, the mechanism is not present). Confusing the
two would let an ordinary failure look like a missing platform, or a
missing platform look like a fixable one.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class BackendUnavailable(RuntimeError):
    """This backend cannot operate on this machine. Never raised for an
    ordinary operational failure — only for a structural one (wrong
    platform, the underlying mechanism is absent)."""


@dataclass(frozen=True)
class WindowInfo:
    """One window, as the platform reports it. Immutable, and carries no
    more than a window manager could ever need: no screenshot, no pixel
    content, no OCR text — Window Manager is explicitly forbidden both."""

    handle: int
    title: str
    process_id: int
    is_visible: bool
    is_minimized: bool
    is_maximized: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "handle": self.handle,
            "title": self.title,
            "process_id": self.process_id,
            "is_visible": self.is_visible,
            "is_minimized": self.is_minimized,
            "is_maximized": self.is_maximized,
        }


class WindowBackend(Protocol):
    """Window operations only — the brief's own words. No OCR, no vision;
    nothing here reads a pixel."""

    def enumerate(self) -> tuple[WindowInfo, ...]: ...
    def active(self) -> WindowInfo | None: ...
    def bring_to_front(self, handle: int) -> bool: ...
    def minimize(self, handle: int) -> bool: ...
    def maximize(self, handle: int) -> bool: ...
    def restore(self, handle: int) -> bool: ...
    def close(self, handle: int) -> bool: ...


class KeyboardBackend(Protocol):
    """`type_text` sends literal characters; `press`/`hotkey` send named
    keys. Neither reads what is on screen — this is input, not
    verification."""

    def type_text(self, text: str) -> None: ...
    def press(self, key: str) -> None: ...
    def hotkey(self, keys: tuple[str, ...]) -> None: ...


class MouseBackend(Protocol):
    """Coordinates only — the brief's own words. No image recognition;
    nothing here looks for a button, it goes to the pixel it is given."""

    def move(self, x: int, y: int) -> None: ...
    def click(self, x: int, y: int, button: str) -> None: ...
    def double_click(self, x: int, y: int, button: str) -> None: ...
    def drag(self, x1: int, y1: int, x2: int, y2: int) -> None: ...
    def scroll(self, x: int, y: int, amount: int) -> None: ...


class ClipboardBackend(Protocol):
    """Read, write, clear. **No history** — the brief's own words — and
    there is no fourth method that could keep one."""

    def read(self) -> str | None: ...
    def write(self, text: str) -> None: ...
    def clear(self) -> None: ...


class NullWindowBackend:
    """A machine with no windows. Every call is an honest, structural
    refusal — never a silent no-op reported as success."""

    def enumerate(self) -> tuple[WindowInfo, ...]:
        return ()

    def active(self) -> WindowInfo | None:
        return None

    def bring_to_front(self, handle: int) -> bool:
        raise BackendUnavailable("no window backend is configured")

    def minimize(self, handle: int) -> bool:
        raise BackendUnavailable("no window backend is configured")

    def maximize(self, handle: int) -> bool:
        raise BackendUnavailable("no window backend is configured")

    def restore(self, handle: int) -> bool:
        raise BackendUnavailable("no window backend is configured")

    def close(self, handle: int) -> bool:
        raise BackendUnavailable("no window backend is configured")


class NullKeyboardBackend:
    def type_text(self, text: str) -> None:
        raise BackendUnavailable("no keyboard backend is configured")

    def press(self, key: str) -> None:
        raise BackendUnavailable("no keyboard backend is configured")

    def hotkey(self, keys: tuple[str, ...]) -> None:
        raise BackendUnavailable("no keyboard backend is configured")


class NullMouseBackend:
    def move(self, x: int, y: int) -> None:
        raise BackendUnavailable("no mouse backend is configured")

    def click(self, x: int, y: int, button: str) -> None:
        raise BackendUnavailable("no mouse backend is configured")

    def double_click(self, x: int, y: int, button: str) -> None:
        raise BackendUnavailable("no mouse backend is configured")

    def drag(self, x1: int, y1: int, x2: int, y2: int) -> None:
        raise BackendUnavailable("no mouse backend is configured")

    def scroll(self, x: int, y: int, amount: int) -> None:
        raise BackendUnavailable("no mouse backend is configured")


class NullClipboardBackend:
    def read(self) -> str | None:
        return None

    def write(self, text: str) -> None:
        raise BackendUnavailable("no clipboard backend is configured")

    def clear(self) -> None:
        raise BackendUnavailable("no clipboard backend is configured")
