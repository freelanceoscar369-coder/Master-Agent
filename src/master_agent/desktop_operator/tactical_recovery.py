"""C28 · Tactical Recovery — local recovery only, at most three retries.

*"Implement local recovery only. Examples: retry click, refocus
application, reopen lost window, wait for loading, refresh page."* —
five recovery kinds, and this module names exactly those five plus one
the Tactical Decision Boundary names separately (*"click A or B"*, when a
step supplies an alternate target).

**This module decides; it never acts.** `TacticalRecovery.plan()` reads
the current observation (already produced by Desktop Perception,
supplied by the caller) and returns a `RecoveryPlan` naming which local
recovery to try next — it holds no `DesktopExecutor`, imports nothing
execution-capable, and calls nothing. `state_machine.py` is the one place
a plan is turned into an `Act`. This split is the same Decide/Act
separation the Core Execution Loop already draws one level up, applied
again here so recovery logic is testable without a single mocked
executor call.

## The retry ceiling is data, not a loop bound guessed at runtime

`MAX_RETRIES = 3` is the brief's own number. `outcome_for()` is a pure
function of one integer — the number of retries already spent on *this
step* — and returns exactly `RETRY` or `ESCALATE`. There is no fourth
answer and no loop inside this module that could exceed it.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from master_agent.desktop.perception import ReadinessState
from master_agent.desktop_operator.mission_context import ActionKind, MissionContext, MissionStep

#: The brief's own number. A step that has already retried this many
#: times escalates instead of trying a fourth time.
MAX_RETRIES = 3


class RecoveryKind(str, Enum):
    """The brief's own five tactical recovery examples, plus the
    Tactical Decision Boundary's *"click A or B"*. Closed — a sixth kind
    would be a new tactical capability, which is a decision this module
    does not get to make on its own."""

    RETRY_CLICK = "retry_click"
    USE_ALTERNATE_TARGET = "use_alternate_target"
    REFOCUS_APPLICATION = "refocus_application"
    REOPEN_WINDOW = "reopen_window"
    WAIT_FOR_LOADING = "wait_for_loading"
    REFRESH_PAGE = "refresh_page"


class RecoveryOutcome(str, Enum):
    RETRY = "retry"
    ESCALATE = "escalate"


@dataclass(frozen=True)
class RecoveryPlan:
    """One local recovery to attempt next, and why. Never a
    recommendation about strategy — every kind here is one of the
    Tactical Decision Boundary's own permitted decisions."""

    kind: RecoveryKind
    reason: str


class TacticalRecovery:
    """Stateless. Every call is a pure function of the step and the
    context it is given."""

    def plan(self, step: MissionStep, context: MissionContext) -> RecoveryPlan:
        """Which local recovery to try next, given the most recent
        observation. Evidence-driven — the same discipline C27's UI
        Ready Detector already applies: this never assumes a cause it
        has no observation for."""
        if (
            step.action.kind is ActionKind.CLICK
            and step.action.has_alternate
            and context.step_retries == 1
        ):
            return RecoveryPlan(
                RecoveryKind.USE_ALTERNATE_TARGET,
                "the primary target did not verify; the step names an "
                "alternate target to try next",
            )

        app_state = (
            context.current_observation.application(step.application)
            if context.current_observation is not None
            else None
        )

        if app_state is not None and app_state.window.value is None:
            # `LOADING` is itself a "no window yet" reading (C27's own
            # `_window_missing` only returns it while still within the
            # application's C25 startup estimate) — checked *before* the
            # generic "no window" branches below, or `WAIT_FOR_LOADING`
            # could never be reached: every LOADING app also has no
            # window, so a window-first check would always intercept it.
            if app_state.readiness.value is ReadinessState.LOADING:
                return RecoveryPlan(
                    RecoveryKind.WAIT_FOR_LOADING,
                    f"{step.application} is still loading",
                )
            if app_state.is_running.value is True:
                return RecoveryPlan(
                    RecoveryKind.REOPEN_WINDOW,
                    f"{step.application} is running but no window is present",
                )
            return RecoveryPlan(
                RecoveryKind.REFOCUS_APPLICATION,
                f"{step.application}'s window state is not observable; attempting to focus it",
            )

        if (
            context.current_observation is not None
            and context.current_observation.browser.browser_active.value is True
            and context.current_observation.browser.page_loaded.value is False
        ):
            return RecoveryPlan(
                RecoveryKind.REFRESH_PAGE,
                "the browser is active but the page has not finished loading",
            )

        if step.action.kind is ActionKind.CLICK:
            return RecoveryPlan(
                RecoveryKind.RETRY_CLICK,
                "the click did not verify; no more specific evidence was found",
            )

        return RecoveryPlan(
            RecoveryKind.REFOCUS_APPLICATION,
            f"verification failed for {step.application}; refocusing before retrying",
        )

    def outcome_for(self, step_retries: int) -> RecoveryOutcome:
        """Whether another attempt is permitted. Pure function of one
        number — no loop, no clock, no state held between calls."""
        return RecoveryOutcome.RETRY if step_retries < MAX_RETRIES else RecoveryOutcome.ESCALATE
