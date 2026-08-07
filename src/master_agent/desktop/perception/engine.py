"""C27 · Observation Engine — `observe()`, and the `DesktopObserver`
facade around it.

```
   ObservationEngine.observe(now, ...) -> DesktopState   (pure composition)
              │
              ▼
   DesktopObserver.observe(now, ...)                      (+ records to history, reads failures)
```

**Never executes. Never clicks. Never types. Never recovers.** Every
value `ObservationEngine.observe()` returns was read from a component
that already exists — `WindowObserver`, `BrowserObserver`,
`ClipboardObserver`, `UIReadyDetector`, C26's `ProcessExecutive.is_running`
(read-only), C25's `DesktopExecutiveV2.profile()`. This file performs no
derivation of its own beyond assembling what those already produced into
one `DesktopState`.

`DesktopObserver` adds exactly two things `ObservationEngine` does not
have on its own: a `DesktopObservationHistory` (so `changes_since()` and
`stable()` have something to compare against) and a `FailureDetector`
(so a caller does not have to thread the last two states through by
hand). Neither performs a new observation — both read what the engine
already produced.
"""
from __future__ import annotations

from datetime import datetime

from master_agent.desktop.execution.clipboard import ClipboardExecutive
from master_agent.desktop.execution.process import ProcessExecutive
from master_agent.desktop.execution.window import WindowManager
from master_agent.desktop.inventory import MachineInventory
from master_agent.desktop.operations import DesktopExecutiveV2
from master_agent.desktop.perception.browser import BrowserObserver
from master_agent.desktop.perception.clipboard import ClipboardObserver
from master_agent.desktop.perception.evidence import (
    Confidence,
    Observation,
    unknown_observation,
)
from master_agent.desktop.perception.failures import FailureDetector, FailureObservation
from master_agent.desktop.perception.history import DesktopObservationHistory
from master_agent.desktop.perception.readiness import UIReadyDetector
from master_agent.desktop.perception.state import (
    ApplicationState,
    DesktopState,
    aggregate_confidence,
)
from master_agent.desktop.perception.windows import WindowObserver

SOURCE_IS_RUNNING = "ProcessExecutive.is_running()"


class ObservationEngine:
    """Composes the five read-only observers into one `DesktopState`.
    Holds no history and detects no failures — that is `DesktopObserver`'s
    job, one layer up."""

    def __init__(
        self,
        *,
        window_manager: WindowManager | None = None,
        browser_sessions: object | None = None,
        clipboard: ClipboardExecutive | None = None,
        process: ProcessExecutive | None = None,
        desktop_executive: DesktopExecutiveV2 | None = None,
        responsiveness=None,
    ) -> None:
        self._window_observer = WindowObserver(window_manager)
        self._browser_observer = BrowserObserver(browser_sessions)
        self._clipboard_observer = ClipboardObserver(clipboard)
        self._readiness = UIReadyDetector(responsiveness)
        self._process = process
        self._executive = desktop_executive or DesktopExecutiveV2()

    def observe(
        self,
        now: datetime,
        *,
        applications: tuple[str, ...] = (),
        inventory: MachineInventory | None = None,
        launched_at: dict[str, datetime] | None = None,
        previous: DesktopState | None = None,
    ) -> DesktopState:
        window_obs = self._window_observer.observe(now, inventory=inventory)
        browser_obs = self._browser_observer.observe(now)
        clipboard_obs = self._clipboard_observer.observe(now)

        launched_at = launched_at or {}
        app_states = tuple(
            self._observe_application(
                application, now, window_obs.windows.value, inventory, launched_at.get(application), previous,
            )
            for application in applications
        )

        all_observations: list[Observation] = [
            window_obs.windows, window_obs.active_window, window_obs.active_application,
            browser_obs.browser_active, browser_obs.current_url, browser_obs.page_loaded,
            browser_obs.navigation_complete, browser_obs.tab_count,
            clipboard_obs.has_content, clipboard_obs.length,
        ]
        for app_state in app_states:
            all_observations.extend([app_state.is_running, app_state.window, app_state.readiness])

        return DesktopState(
            applications=app_states, windows=window_obs, browser=browser_obs,
            clipboard=clipboard_obs, timestamp=now,
            confidence=aggregate_confidence(all_observations),
        )

    def _observe_application(
        self, application, now, windows, inventory, launched_at, previous,
    ) -> ApplicationState:
        is_running_obs = self._observe_is_running(application, now)

        pids = frozenset(p.pid for p in inventory.running(application)) if inventory else frozenset()
        window_value = next((w for w in (windows or ()) if w.process_id in pids), None) if windows is not None else None
        if windows is None:
            window_obs = unknown_observation(
                reason="window enumeration failed; no window can be attributed",
                source="WindowObserver", timestamp=now,
            )
        else:
            window_obs = Observation(
                value=window_value, confidence=Confidence.OBSERVED,
                reason=(
                    f"a window owned by {application} was found" if window_value is not None
                    else f"no window owned by {application} was found among {len(windows)} enumerated"
                ),
                source="WindowObserver", timestamp=now,
            )

        previous_app = previous.application(application) if previous is not None else None
        previous_title = (
            previous_app.window.value.title
            if previous_app is not None and previous_app.window.value is not None
            else None
        )
        profile = self._executive.profile(application)

        readiness_obs = self._readiness.detect(
            application=application, is_running=is_running_obs.value, window=window_value,
            launched_at=launched_at, previous_title=previous_title, now=now, profile=profile,
        )

        return ApplicationState(
            application=application, is_running=is_running_obs,
            window=window_obs, readiness=readiness_obs,
        )

    def _observe_is_running(self, application: str, now: datetime) -> Observation:
        if self._process is None:
            return unknown_observation(
                reason="no ProcessExecutive was supplied", source=SOURCE_IS_RUNNING, timestamp=now,
            )
        result = self._process.is_running(application)
        if not result.success:
            return unknown_observation(
                reason="; ".join(result.errors) or "is_running failed",
                source=SOURCE_IS_RUNNING, timestamp=now,
            )
        return Observation(
            value=result.output["running"], confidence=Confidence.OBSERVED,
            reason=f"{application} running: {result.output['running']}",
            source=SOURCE_IS_RUNNING, timestamp=now,
        )


class DesktopObserver:
    """`ObservationEngine` + `DesktopObservationHistory` +
    `FailureDetector`, composed. The single entry point Founder Runtime
    (C23/C24) or a future Desktop Operator would hold."""

    def __init__(
        self,
        engine: ObservationEngine | None = None,
        history: DesktopObservationHistory | None = None,
        failure_detector: FailureDetector | None = None,
    ) -> None:
        self._engine = engine or ObservationEngine()
        self._history = history or DesktopObservationHistory()
        self._failures = failure_detector or FailureDetector()

    @property
    def history(self) -> DesktopObservationHistory:
        return self._history

    def observe(
        self,
        now: datetime,
        *,
        applications: tuple[str, ...] = (),
        inventory: MachineInventory | None = None,
        launched_at: dict[str, datetime] | None = None,
    ) -> DesktopState:
        previous = self._history.latest()
        state = self._engine.observe(
            now, applications=applications, inventory=inventory,
            launched_at=launched_at, previous=previous,
        )
        self._history.record(state)
        return state

    def failures(self) -> tuple[FailureObservation, ...]:
        """Failures between the two most recent recorded observations.
        Empty when fewer than two exist, or when nothing changed."""
        states = self._history.all()
        if len(states) < 2:
            return ()
        return self._failures.detect(states[-2], states[-1])
