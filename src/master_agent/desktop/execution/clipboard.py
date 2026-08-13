"""C26 · Clipboard Executive — read, write, clear. **No history** — the
brief's own words. There is no fourth method, no log, and nothing here
remembers what was written after the next `write()` or `clear()`
overwrites it — the system clipboard has always worked this way, and this
class adds nothing on top of it."""
from __future__ import annotations

from master_agent.desktop.execution.backends import (
    BackendUnavailable,
    ClipboardBackend,
    NullClipboardBackend,
)
from master_agent.executor.action import ExecutionResult


class ClipboardExecutive:
    __slots__ = ("_backend",)

    def __init__(self, backend: ClipboardBackend | None = None) -> None:
        if backend is None:
            try:
                from .win32_backends import Win32ClipboardBackend
                backend = Win32ClipboardBackend()
            except (ImportError, BackendUnavailable):
                backend = NullClipboardBackend()
        self._backend = backend

    def read(self) -> ExecutionResult:
        try:
            text = self._backend.read()
        except BackendUnavailable as exc:
            return ExecutionResult(success=False, errors=[str(exc)])
        return ExecutionResult(success=True, output={"text": text})

    def write(self, text: str) -> ExecutionResult:
        if not isinstance(text, str):
            return ExecutionResult(success=False, errors=["text must be a string"])
        try:
            self._backend.write(text)
        except BackendUnavailable as exc:
            return ExecutionResult(success=False, errors=[str(exc)])
        return ExecutionResult(success=True, output={"written_characters": len(text)})

    def clear(self) -> ExecutionResult:
        try:
            self._backend.clear()
        except BackendUnavailable as exc:
            return ExecutionResult(success=False, errors=[str(exc)])
        return ExecutionResult(success=True, output=None)
