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

    def multi_click(self, x: int, y: int, count: int, button: str = "left") -> ExecutionResult:
        """`count` rapid clicks at one point — the generic gesture, not a
        named special case.

        Exists because a third click is a real desktop technique and the
        controller could express one and two but not three. Deliberately
        `count` rather than a `triple_click()` method: the gesture is
        generic, and what a third click SELECTS is not — in a single-line
        field it commonly takes the whole value, in document content a
        paragraph or line. That distinction is reference knowledge
        (`operations/reference.py::triple_click`), and a caller must verify
        the resulting selection rather than assume it.

        Nothing in this codebase currently needs three: the rename that
        prompted this was solved by targeting the correct control. The
        primitive exists so the next caller has it without inventing a
        site-specific gesture.
        """
        if button not in _KNOWN_BUTTONS:
            return ExecutionResult(
                success=False, errors=[f"unknown button: {button!r} (known: {', '.join(_KNOWN_BUTTONS)})"]
            )
        if not isinstance(count, int) or count < 1:
            return ExecutionResult(success=False, errors=["'count' must be a positive integer"])
        try:
            for _ in range(count):
                self._backend.click(x, y, button)
        except BackendUnavailable as exc:
            return ExecutionResult(success=False, errors=[str(exc)])
        return ExecutionResult(success=True, output={"x": x, "y": y, "button": button, "count": count})

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
