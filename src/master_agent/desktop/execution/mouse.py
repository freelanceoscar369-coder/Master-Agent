"""C26 · Mouse Controller — move, click, double click, right click, drag,
scroll. **Coordinates only** — the brief's own words. No image
recognition anywhere in this file: every method takes an `(x, y)` a
caller already decided on, and nothing here looks for a button, an icon,
or a color to click toward.
"""
from __future__ import annotations

from master_agent.desktop.execution.backends import (
    BackendUnavailable,
    MouseBackend,
    NullMouseBackend,
)
from master_agent.executor.action import ExecutionResult

_KNOWN_BUTTONS = ("left", "right", "middle")


class MouseController:
    __slots__ = ("_backend",)

    def __init__(self, backend: MouseBackend | None = None) -> None:
        if backend is None:
            try:
                from .win32_backends import Win32MouseBackend
                backend = Win32MouseBackend()
            except (ImportError, BackendUnavailable):
                backend = NullMouseBackend()
        self._backend = backend

    def move(self, x: int, y: int) -> ExecutionResult:
        try:
            self._backend.move(x, y)
        except BackendUnavailable as exc:
            return ExecutionResult(success=False, errors=[str(exc)])
        return ExecutionResult(success=True, output={"x": x, "y": y})

    def click(self, x: int, y: int, button: str = "left") -> ExecutionResult:
        if button not in _KNOWN_BUTTONS:
            return ExecutionResult(
                success=False, errors=[f"unknown button: {button!r} (known: {', '.join(_KNOWN_BUTTONS)})"]
            )
        try:
            self._backend.click(x, y, button)
        except BackendUnavailable as exc:
            return ExecutionResult(success=False, errors=[str(exc)])
        return ExecutionResult(success=True, output={"x": x, "y": y, "button": button})

    def double_click(self, x: int, y: int, button: str = "left") -> ExecutionResult:
        if button not in _KNOWN_BUTTONS:
            return ExecutionResult(
                success=False, errors=[f"unknown button: {button!r} (known: {', '.join(_KNOWN_BUTTONS)})"]
            )
        try:
            self._backend.double_click(x, y, button)
        except BackendUnavailable as exc:
            return ExecutionResult(success=False, errors=[str(exc)])
        return ExecutionResult(success=True, output={"x": x, "y": y, "button": button})

    def right_click(self, x: int, y: int) -> ExecutionResult:
        return self.click(x, y, button="right")

    def drag(self, x1: int, y1: int, x2: int, y2: int) -> ExecutionResult:
        try:
            self._backend.drag(x1, y1, x2, y2)
        except BackendUnavailable as exc:
            return ExecutionResult(success=False, errors=[str(exc)])
        return ExecutionResult(success=True, output={"from": [x1, y1], "to": [x2, y2]})

    def scroll(self, x: int, y: int, amount: int) -> ExecutionResult:
        try:
            self._backend.scroll(x, y, amount)
        except BackendUnavailable as exc:
            return ExecutionResult(success=False, errors=[str(exc)])
        return ExecutionResult(success=True, output={"x": x, "y": y, "amount": amount})
