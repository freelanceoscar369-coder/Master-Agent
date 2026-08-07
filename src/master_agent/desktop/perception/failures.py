"""C27 · Failure Detection — structured observations, never recovery.

The brief's own six: window disappeared, application crashed, navigation
failed, window hidden, browser closed, application never appeared.
**Every one is detected by comparing two already-produced `DesktopState`
values — nothing here re-observes the machine, and nothing here acts on
what it finds.** `FailureDetector.detect()` returns a tuple of
`FailureObservation`s, each carrying the same confidence/reason/source/
timestamp evidence every other observation in this layer does; an empty
tuple is not a lesser answer, it is *"no failure was detected,"* stated
the same way `Coverage.complete` (C19) states a clean result rather than
omitting a field.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from master_agent.desktop.perception.evidence import Confidence
from master_agent.desktop.perception.readiness import ReadinessState
from master_agent.desktop.perception.state import DesktopState

SOURCE = "FailureDetector"


class FailureKind(str, Enum):
    """The brief's own six. Closed."""

    WINDOW_DISAPPEARED = "window_disappeared"
    APPLICATION_CRASHED = "application_crashed"
    NAVIGATION_FAILED = "navigation_failed"
    WINDOW_HIDDEN = "window_hidden"
    BROWSER_CLOSED = "browser_closed"
    APPLICATION_NEVER_APPEARED = "application_never_appeared"


@dataclass(frozen=True)
class FailureObservation:
    """One detected failure, with the same evidence discipline as every
    other observation in this layer."""

    application: str | None
    kind: FailureKind
    confidence: Confidence
    reason: str
    source: str
    timestamp: datetime

    def as_dict(self) -> dict[str, Any]:
        return {
            "application": self.application,
            "kind": self.kind.value,
            "confidence": self.confidence.value,
            "reason": self.reason,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
        }


class FailureDetector:
    """Stateless — every call compares exactly the two states it is
    given. `ObservationHistory` (which states to compare) is the caller's
    decision, not this class's."""

    def detect(
        self, previous: DesktopState | None, current: DesktopState
    ) -> tuple[FailureObservation, ...]:
        if previous is None:
            return ()

        failures: list[FailureObservation] = []
        failures.extend(self._application_failures(previous, current))
        failures.extend(self._browser_failures(previous, current))
        return tuple(failures)

    def _application_failures(
        self, previous: DesktopState, current: DesktopState
    ) -> list[FailureObservation]:
        found: list[FailureObservation] = []
        for prior in previous.applications:
            now_state = current.application(prior.application)
            if now_state is None:
                continue

            had_window = prior.window.value is not None
            has_window = now_state.window.value is not None

            if had_window and not has_window:
                if now_state.is_running.value is False:
                    found.append(FailureObservation(
                        application=prior.application, kind=FailureKind.APPLICATION_CRASHED,
                        confidence=Confidence.STRONG,
                        reason=(
                            f"{prior.application} had a window at the previous "
                            "observation; it now has neither a window nor a "
                            "running process"
                        ),
                        source=SOURCE, timestamp=current.timestamp,
                    ))
                elif now_state.is_running.value is True:
                    found.append(FailureObservation(
                        application=prior.application, kind=FailureKind.WINDOW_DISAPPEARED,
                        confidence=Confidence.STRONG,
                        reason=(
                            f"{prior.application} had a window at the previous "
                            "observation; the process is still running but no "
                            "window is found now"
                        ),
                        source=SOURCE, timestamp=current.timestamp,
                    ))

            if (
                had_window and has_window
                and prior.window.value.is_visible
                and not now_state.window.value.is_visible
            ):
                found.append(FailureObservation(
                    application=prior.application, kind=FailureKind.WINDOW_HIDDEN,
                    confidence=Confidence.OBSERVED,
                    reason=f"{prior.application}'s window was visible and is no longer visible",
                    source=SOURCE, timestamp=current.timestamp,
                ))

            if (
                prior.readiness.value == ReadinessState.LOADING
                and now_state.readiness.value == ReadinessState.WINDOW_MISSING
                and now_state.is_running.value is True
            ):
                found.append(FailureObservation(
                    application=prior.application, kind=FailureKind.APPLICATION_NEVER_APPEARED,
                    confidence=now_state.readiness.confidence,
                    reason=(
                        f"{prior.application} was loading and is now past its "
                        "own operation profile's startup estimate with still "
                        "no window"
                    ),
                    source=SOURCE, timestamp=current.timestamp,
                ))
        return found

    def _browser_failures(
        self, previous: DesktopState, current: DesktopState
    ) -> list[FailureObservation]:
        found: list[FailureObservation] = []
        if previous.browser.browser_active.value is True and current.browser.browser_active.value is False:
            found.append(FailureObservation(
                application=None, kind=FailureKind.BROWSER_CLOSED,
                confidence=Confidence.OBSERVED,
                reason="a browser session was open at the previous observation and none is open now",
                source=SOURCE, timestamp=current.timestamp,
            ))

        if (
            current.browser.browser_active.value is True
            and previous.browser.current_url.known
            and not current.browser.current_url.known
        ):
            found.append(FailureObservation(
                application=None, kind=FailureKind.NAVIGATION_FAILED,
                confidence=Confidence.WEAK,
                reason=(
                    "a browser session is open but its current page could not "
                    "be observed, having been observable a moment before"
                ),
                source=SOURCE, timestamp=current.timestamp,
            ))
        return found
