"""C26 · Keyboard Controller — `type()`, `press()`, `hotkey()`, `paste()`.

Four methods, exactly the shape the brief names. `paste()` is the one
that composes: it is not a fifth keyboard primitive, it is
`ClipboardExecutive.write()` (when text is given) followed by
`hotkey(("ctrl", "v"))` — reusing both rather than teaching the keyboard
backend a second way to move text onto the screen.
"""
from __future__ import annotations

from master_agent.desktop.execution.backends import (
    BackendUnavailable,
    KeyboardBackend,
    NullKeyboardBackend,
)
from master_agent.desktop.execution.clipboard import ClipboardExecutive
from master_agent.executor.action import ExecutionResult


class KeyboardController:
    __slots__ = ("_backend", "_clipboard")

    def __init__(
        self,
        backend: KeyboardBackend | None = None,
        clipboard: ClipboardExecutive | None = None,
    ) -> None:
        self._backend = backend or NullKeyboardBackend()
        self._clipboard = clipboard or ClipboardExecutive()

    def type(self, text: str) -> ExecutionResult:
        if not isinstance(text, str):
            return ExecutionResult(success=False, errors=["text must be a string"])
        try:
            self._backend.type_text(text)
        except BackendUnavailable as exc:
            return ExecutionResult(success=False, errors=[str(exc)])
        return ExecutionResult(success=True, output={"typed_characters": len(text)})

    def press(self, key: str) -> ExecutionResult:
        try:
            self._backend.press(key)
        except BackendUnavailable as exc:
            return ExecutionResult(success=False, errors=[str(exc)])
        except ValueError as exc:
            return ExecutionResult(success=False, errors=[str(exc)])
        return ExecutionResult(success=True, output={"key": key})

    def hotkey(self, *keys: str) -> ExecutionResult:
        if not keys:
            return ExecutionResult(success=False, errors=["hotkey requires at least one key"])
        try:
            self._backend.hotkey(keys)
        except BackendUnavailable as exc:
            return ExecutionResult(success=False, errors=[str(exc)])
        except ValueError as exc:
            return ExecutionResult(success=False, errors=[str(exc)])
        return ExecutionResult(success=True, output={"keys": list(keys)})

    def paste(self, text: str | None = None) -> ExecutionResult:
        """Paste whatever is on the clipboard, or `text` if given (write
        it, then paste it — the clipboard's prior contents are replaced,
        the same way a founder's own Ctrl-C/Ctrl-V would)."""
        if text is not None:
            written = self._clipboard.write(text)
            if not written.success:
                return written
        return self.hotkey("ctrl", "v")

    # ---- press() convenience names, per the brief's own list -----------

    def enter(self) -> ExecutionResult:
        return self.press("enter")

    def escape(self) -> ExecutionResult:
        return self.press("escape")

    def delete(self) -> ExecutionResult:
        return self.press("delete")

    def arrow(self, direction: str) -> ExecutionResult:
        if direction not in ("up", "down", "left", "right"):
            return ExecutionResult(
                success=False,
                errors=[f"unknown arrow direction: {direction!r} (up, down, left, right)"],
            )
        return self.press(direction)
