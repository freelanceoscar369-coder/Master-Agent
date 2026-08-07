"""C27 · `DesktopState` — everything the Observation Engine found, in one
immutable value.

`focus` and `foreground` are not a second observation of the active
window — they are `windows.active_application` and `windows.active_window`
themselves, aliased. Two independent readings of *"what is focused right
now"* could disagree with each other in a way that only confuses whoever
reads them; one observation, referenced twice under the names the brief
asks for, cannot.

`confidence` is the state's own weakest link: `Confidence.weakest()` (C22)
over every observation this state carries, so a caller who only checks
the top-level number is never told more than the least-certain fact
actually supports.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from master_agent.desktop.perception.browser import BrowserPerception
from master_agent.desktop.perception.clipboard import ClipboardStatus
from master_agent.desktop.perception.evidence import Confidence, Observation
from master_agent.desktop.perception.windows import WindowObservation


@dataclass(frozen=True)
class ApplicationState:
    """One application's observed state — whether it is running, the
    window found for it (if any — the same `WindowInfo` `readiness` was
    computed from, carried rather than re-derived), and its readiness."""

    application: str
    is_running: Observation
    window: Observation
    readiness: Observation

    def as_dict(self) -> dict[str, Any]:
        return {
            "application": self.application,
            "is_running": self.is_running.as_dict(),
            "window": self.window.as_dict(),
            "readiness": self.readiness.as_dict(),
        }


@dataclass(frozen=True)
class DesktopState:
    """The brief's own eight sections: applications, windows, browser,
    clipboard status, focus, foreground, time, confidence."""

    applications: tuple[ApplicationState, ...]
    windows: WindowObservation
    browser: BrowserPerception
    clipboard: ClipboardStatus
    timestamp: datetime
    confidence: Confidence

    @property
    def focus(self) -> Observation:
        """The focused application — `windows.active_application`,
        aliased under the brief's own name."""
        return self.windows.active_application

    @property
    def foreground(self) -> Observation:
        """The foreground window — `windows.active_window`, aliased."""
        return self.windows.active_window

    def application(self, key: str) -> ApplicationState | None:
        for candidate in self.applications:
            if candidate.application == key:
                return candidate
        return None

    def as_dict(self) -> dict[str, Any]:
        return {
            "applications": {a.application: a.as_dict() for a in self.applications},
            "windows": self.windows.as_dict(),
            "browser": self.browser.as_dict(),
            "clipboard": self.clipboard.as_dict(),
            "focus": self.focus.as_dict(),
            "foreground": self.foreground.as_dict(),
            "timestamp": self.timestamp.isoformat(),
            "confidence": self.confidence.value,
        }


def aggregate_confidence(observations: list[Observation]) -> Confidence:
    """`Confidence.weakest()` (C22) over every observation collected for
    one `DesktopState`. A free function, so `DesktopState` itself stays a
    plain value with no derivation logic of its own — `engine.py` calls
    this once, before constructing the frozen state."""
    return Confidence.weakest(*(o.confidence for o in observations))
