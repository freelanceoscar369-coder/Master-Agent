"""C27 · `DesktopObservationHistory` — the last N observations, and
questions over them.

Bounded the same way `ConversationMemory` (C23, Layer 1) is bounded: the
oldest observation falls off past `max_observations` rather than growing
without limit for a long-running session. In-process only, never
persisted — a desktop's state five minutes ago is not evidence about
right now, and nothing here claims otherwise past its own bound.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from master_agent.desktop.perception.state import DesktopState

#: The sections `changes_since()` reports on, in a fixed order — the same
#: pattern `EnvironmentIntelligence.changes_from()` (C22) already
#: establishes for the identical reason: a caller acts on *what* changed,
#: not on a diff of the whole state by hand.
SECTIONS: tuple[str, ...] = ("applications", "windows", "browser", "clipboard", "focus", "foreground")


def _signature(state: DesktopState, section: str) -> object:
    """A comparable projection of one section — the observed *values*,
    never the `Observation` wrapper (whose `timestamp` would make two
    otherwise-identical readings compare unequal)."""
    if section == "applications":
        return tuple(
            (a.application, a.is_running.value, a.readiness.value)
            for a in state.applications
        )
    if section == "windows":
        active = state.windows.active_window.value
        enumerated = state.windows.windows.value
        return (
            active.handle if active is not None else None,
            len(enumerated) if enumerated is not None else None,
        )
    if section == "browser":
        return (
            state.browser.browser_active.value,
            state.browser.current_url.value,
            state.browser.page_loaded.value,
            state.browser.tab_count.value,
        )
    if section == "clipboard":
        return (state.clipboard.has_content.value, state.clipboard.length.value)
    if section == "focus":
        return state.focus.value
    if section == "foreground":
        foreground = state.foreground.value
        return foreground.handle if foreground is not None else None
    raise ValueError(f"unknown section: {section!r}")  # pragma: no cover — SECTIONS is closed


@dataclass
class DesktopObservationHistory:
    """Newest last. `max_observations` bounds it; `record()` is the only
    mutation, and it is this class's own bookkeeping — not a mutation of
    the desktop, which nothing in `perception/` ever performs."""

    max_observations: int = 50
    _states: list[DesktopState] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        if self.max_observations < 1:
            raise ValueError("max_observations must be at least 1")

    def record(self, state: DesktopState) -> None:
        self._states.append(state)
        if len(self._states) > self.max_observations:
            self._states = self._states[-self.max_observations :]

    def latest(self) -> DesktopState | None:
        return self._states[-1] if self._states else None

    def all(self) -> tuple[DesktopState, ...]:
        return tuple(self._states)

    def __len__(self) -> int:
        return len(self._states)

    def changes_since(self, previous: DesktopState) -> tuple[str, ...]:
        """Which sections differ between `previous` and the latest
        recorded state. Empty if nothing changed, or if nothing has been
        recorded since — never raises for either case."""
        latest = self.latest()
        if latest is None:
            return ()
        return tuple(
            section for section in SECTIONS
            if _signature(latest, section) != _signature(previous, section)
        )

    def stable(self, count: int = 2) -> bool:
        """Whether the last `count` recorded states agree on every
        section. `False` when fewer than `count` observations exist —
        stability is not claimed from insufficient evidence, the same
        discipline every derivation in this project already applies to
        an absent conclusion."""
        if count < 1:
            raise ValueError("count must be at least 1")
        if len(self._states) < count:
            return False
        window = self._states[-count:]
        baseline = window[0]
        return all(
            all(_signature(state, section) == _signature(baseline, section) for section in SECTIONS)
            for state in window[1:]
        )
