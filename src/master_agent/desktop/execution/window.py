"""C26 · Window Manager — window operations only.

Enumerate, locate, active, bring to front, minimize, maximize, restore,
close. **No OCR. No vision.** — the brief's own words, and there is no
method here that could read a pixel: every value on `WindowInfo` comes
from the platform's own window metadata (title, process id, visibility,
minimized/maximized state), never a screenshot.

This fills the gap `desktop/actions.py`'s own `BringToFrontAction`
deliberately left open: *"window focus needs desktop interaction, which
MB030 deliberately excludes (Deliverable 7); a later Desktop Interaction
brief owns this."* This is that brief. `desktop/actions.py` is not
modified — this is a new, independent implementation, not a patch to the
old one, and the two can coexist (the old action still reports its own
honest refusal if called directly).
"""
from __future__ import annotations

from dataclasses import dataclass

from master_agent.desktop.execution.backends import (
    BackendUnavailable,
    NullWindowBackend,
    WindowBackend,
)
from master_agent.executor.action import ExecutionResult


@dataclass(frozen=True)
class WindowNotFound:
    """Why `locate()` found nothing. Carried rather than returning a bare
    `None` with no explanation — the same discipline every derivation in
    this project already applies to an absent conclusion."""

    query: str
    windows_considered: int


class WindowManager:
    """Every method returns an `ExecutionResult` — this project's own
    universal result envelope (`executor/action.py`), reused rather than
    inventing a second one. A window operation that cannot succeed is a
    structured failure, never a raised exception a caller has to guess
    the shape of."""

    __slots__ = ("_backend",)

    def __init__(self, backend: WindowBackend | None = None) -> None:
        self._backend = backend or NullWindowBackend()

    def enumerate(self, *, visible_only: bool = True) -> ExecutionResult:
        try:
            windows = self._backend.enumerate()
        except BackendUnavailable as exc:
            return ExecutionResult(success=False, errors=[str(exc)])
        if visible_only:
            windows = tuple(w for w in windows if w.is_visible)
        return ExecutionResult(
            success=True,
            output={"count": len(windows), "windows": [w.as_dict() for w in windows]},
        )

    def locate(self, title_contains: str) -> ExecutionResult:
        """The one search this package performs: a case-insensitive
        substring match against a window's own title. No image match, no
        process-name heuristic here — `locate_by_process` (below) is the
        precise version when a process id is already known."""
        needle = title_contains.strip().lower()
        if not needle:
            return ExecutionResult(success=False, errors=["title_contains must not be blank"])
        result = self.enumerate(visible_only=True)
        if not result.success:
            return result
        windows = result.output["windows"]
        matches = [w for w in windows if needle in w["title"].lower()]
        if not matches:
            return ExecutionResult(
                success=False,
                errors=[f"no visible window title contains {title_contains!r}"],
                output=WindowNotFound(title_contains, len(windows)).__dict__,
            )
        return ExecutionResult(success=True, output={"count": len(matches), "windows": matches})

    def locate_by_process(self, process_ids: frozenset[int]) -> ExecutionResult:
        """Every visible window owned by one of the given process ids.
        The precise counterpart to `locate()`: a caller who already knows
        *which process* it wants (from `desktop.inventory`'s own
        `MachineInventory.running()`, reused rather than re-derived) gets
        an exact match instead of a title guess."""
        result = self.enumerate(visible_only=True)
        if not result.success:
            return result
        windows = result.output["windows"]
        matches = [w for w in windows if w["process_id"] in process_ids]
        if not matches:
            return ExecutionResult(
                success=False,
                errors=[f"no visible window belongs to process id(s): {sorted(process_ids)}"],
            )
        return ExecutionResult(success=True, output={"count": len(matches), "windows": matches})

    def active(self) -> ExecutionResult:
        try:
            window = self._backend.active()
        except BackendUnavailable as exc:
            return ExecutionResult(success=False, errors=[str(exc)])
        if window is None:
            return ExecutionResult(success=False, errors=["no window is currently active"])
        return ExecutionResult(success=True, output=window.as_dict())

    def bring_to_front(self, handle: int) -> ExecutionResult:
        return self._apply("bring_to_front", handle)

    def minimize(self, handle: int) -> ExecutionResult:
        return self._apply("minimize", handle)

    def maximize(self, handle: int) -> ExecutionResult:
        return self._apply("maximize", handle)

    def restore(self, handle: int) -> ExecutionResult:
        return self._apply("restore", handle)

    def close(self, handle: int) -> ExecutionResult:
        """Posts a close request — see `win32_backends.py`'s module
        docstring for why this is never a forced kill."""
        return self._apply("close", handle)

    def focus_process(self, process_ids: frozenset[int]) -> ExecutionResult:
        """`locate_by_process` + `bring_to_front`, composed. The one
        convenience method in this class, because *"find the window
        belonging to this process and bring it forward"* is a single
        operation every caller in this package needs — `browser.py`'s
        `focus_browser()` and `executor.py`'s `focus()` both use this
        rather than each repeating the two-step sequence."""
        located = self.locate_by_process(process_ids)
        if not located.success:
            return located
        handle = located.output["windows"][0]["handle"]
        return self.bring_to_front(handle)

    def _apply(self, operation: str, handle: int) -> ExecutionResult:
        method = getattr(self._backend, operation)
        try:
            ok = method(handle)
        except BackendUnavailable as exc:
            return ExecutionResult(success=False, errors=[str(exc)])
        if not ok:
            return ExecutionResult(
                success=False, errors=[f"{operation} did not succeed for window {handle}"]
            )
        return ExecutionResult(success=True, output={"handle": handle, "operation": operation})
