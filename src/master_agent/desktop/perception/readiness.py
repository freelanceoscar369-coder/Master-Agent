"""C27 · UI Ready Detector — six states, evidence only.

```
   ApplicationReady   ApplicationBusy   ApplicationHung
   WindowMissing      Loading           Unknown
```

**"Must never assume. Evidence only."** Every state below is reached by
naming the specific fact that produced it — never inferred from elapsed
time alone, which is the one shortcut this module is built to refuse.
`Unknown` is not a failure of this detector; it is the correct answer
whenever the available evidence does not clear the bar for any of the
other five, and is returned far more often than a caller might expect
from a naive implementation, on purpose.

## What produces each state, and why

| State | Requires | Confidence |
|---|---|---|
| `WINDOW_MISSING` | not running, no window found | `OBSERVED` |
| `WINDOW_MISSING` | running, no window found, past its own C25 startup estimate | `STRONG` — two independent facts (running, and past the profile's own declared window) |
| `LOADING` | running, no window found, still within its C25 startup estimate | `STRONG` when the estimate is known, `WEAK` when it is not |
| `HUNG` | a window is found, and `win32_probe.ResponsivenessBackend` reports it is not responding | `OBSERVED` — the same technique Task Manager itself uses |
| `BUSY` | a window is found, responding, and its title changed since the previous observation | `WEAK` — one indirect fact; a title change is real activity, not proof of *why* |
| `READY` | a window is found and responding, with no evidence of recent change | `OBSERVED` when responsiveness was checked, `STRONG` when a window is present and was already stable across two observations |
| `UNKNOWN` | anything else — responsiveness could not be checked, or the evidence is contradictory | `UNKNOWN` |

`known_failure_modes`/`startup_time` are read from C25's
`ApplicationOperationProfile` — consulted, never re-derived; a second
guess at "how long should this take" would be exactly the duplication the
Architecture Rules forbid.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from master_agent.desktop.execution.backends import WindowInfo
from master_agent.desktop.operations import ApplicationOperationProfile
from master_agent.desktop.perception.evidence import (
    Confidence,
    Observation,
    unknown_observation,
)
from master_agent.desktop.perception.win32_probe import (
    ResponsivenessBackend,
    ResponsivenessUnavailable,
)

SOURCE = "UIReadyDetector"


class ReadinessState(str, Enum):
    """The brief's own six. Closed."""

    READY = "application_ready"
    BUSY = "application_busy"
    HUNG = "application_hung"
    WINDOW_MISSING = "window_missing"
    LOADING = "loading"
    UNKNOWN = "unknown"


class UIReadyDetector:
    __slots__ = ("_responsiveness",)

    def __init__(self, responsiveness: ResponsivenessBackend | None = None) -> None:
        from master_agent.desktop.perception.win32_probe import NullResponsivenessBackend

        self._responsiveness = responsiveness or NullResponsivenessBackend()

    def detect(
        self,
        *,
        application: str,
        is_running: bool | None,
        window: WindowInfo | None,
        launched_at: datetime | None,
        previous_title: str | None,
        now: datetime,
        profile: ApplicationOperationProfile | None = None,
    ) -> Observation:
        """One `Observation` whose `.value` is a `ReadinessState`.

        `is_running`/`window` are facts the caller already observed
        (`ProcessExecutive.is_running`, `WindowObserver`) — this method
        derives no process or window fact of its own. `previous_title`
        is the same application's window title from the *last*
        observation, if any (`ObservationHistory`, reused rather than
        re-queried).
        """
        if window is None:
            return self._window_missing(application, is_running, launched_at, profile, now)

        responding = self._check_responding(window)
        if responding is False:
            return Observation(
                value=ReadinessState.HUNG, confidence=Confidence.OBSERVED,
                reason=f"{application}'s window did not respond to a WM_NULL probe",
                source="Win32ResponsivenessBackend.is_responding()", timestamp=now,
            )

        if responding is None:
            # Responsiveness could not be checked at all — fall back to
            # the weaker signals below rather than claiming HUNG or READY
            # from nothing.
            if previous_title is not None and previous_title != window.title:
                return Observation(
                    value=ReadinessState.BUSY, confidence=Confidence.WEAK,
                    reason=(
                        f"{application}'s window title changed from "
                        f"{previous_title!r} to {window.title!r}"
                    ),
                    source="ObservationHistory (title comparison)", timestamp=now,
                )
            return unknown_observation(
                reason=(
                    f"a window exists for {application} but responsiveness "
                    "could not be checked"
                ),
                source=SOURCE, timestamp=now,
            )

        # responding is True.
        if previous_title is not None and previous_title != window.title:
            return Observation(
                value=ReadinessState.BUSY, confidence=Confidence.WEAK,
                reason=(
                    f"{application}'s window title changed from "
                    f"{previous_title!r} to {window.title!r}"
                ),
                source="ObservationHistory (title comparison)", timestamp=now,
            )

        confidence = Confidence.STRONG if previous_title == window.title else Confidence.OBSERVED
        return Observation(
            value=ReadinessState.READY, confidence=confidence,
            reason=f"{application}'s window is present and responded to a probe",
            source="Win32ResponsivenessBackend.is_responding()", timestamp=now,
        )

    def _check_responding(self, window: WindowInfo) -> bool | None:
        try:
            return self._responsiveness.is_responding(window.handle)
        except ResponsivenessUnavailable:
            return None

    def _window_missing(
        self,
        application: str,
        is_running: bool | None,
        launched_at: datetime | None,
        profile: ApplicationOperationProfile | None,
        now: datetime,
    ) -> Observation:
        if is_running is False:
            return Observation(
                value=ReadinessState.WINDOW_MISSING, confidence=Confidence.OBSERVED,
                reason=f"{application} is not running and no window was found",
                source=SOURCE, timestamp=now,
            )

        if is_running is None:
            return unknown_observation(
                reason=f"whether {application} is running could not be determined",
                source=SOURCE, timestamp=now,
            )

        # is_running is True, no window found: loading, or overdue.
        if launched_at is None or profile is None:
            return Observation(
                value=ReadinessState.LOADING, confidence=Confidence.WEAK,
                reason=(
                    f"{application} is running with no window yet; no launch "
                    "time or operation profile was supplied to judge whether "
                    "this is expected"
                ),
                source=SOURCE, timestamp=now,
            )

        elapsed = (now - launched_at).total_seconds()
        expected = profile.startup_time.typical_seconds[1]
        if elapsed <= expected:
            return Observation(
                value=ReadinessState.LOADING, confidence=Confidence.STRONG,
                reason=(
                    f"{application} is running with no window yet, "
                    f"{elapsed:.0f}s since launch, within its own C25 "
                    f"startup estimate of {expected}s"
                ),
                source="ApplicationOperationProfile.startup_time", timestamp=now,
            )
        return Observation(
            value=ReadinessState.WINDOW_MISSING, confidence=Confidence.STRONG,
            reason=(
                f"{application} is running with no window, "
                f"{elapsed:.0f}s since launch — past its own C25 startup "
                f"estimate of {expected}s"
            ),
            source="ApplicationOperationProfile.startup_time", timestamp=now,
        )
