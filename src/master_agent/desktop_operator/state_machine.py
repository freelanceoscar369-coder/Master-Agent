"""C28 · The Core Execution Loop — exactly the state machine the brief
draws, and no alternate execution model.

```
   Observe
      │
      ▼
   Decide (TACTICAL ONLY)
      │
      ▼
   Act
      │
      ▼
   Verify
      │
      ▼
   State Evaluator
      │
      ├──────── SUCCESS ───────► Continue
      │
      └──────── FAILURE ───────► Tactical Recovery
                                   │
                          retry? ──┘ yes (loop back to Observe)
                           │
                          no
                           │
                           ▼
                  Escalate Founder Runtime
```

**Bounded, not polling.** `run_step()`'s loop runs at most
`tactical_recovery.MAX_RETRIES` iterations — a `for` loop over a fixed
range, never a `while True`. Every iteration re-observes through Desktop
Perception rather than assuming the world is still what it was; that is
the *"no polling loop"* rule honoured structurally, not by promise: a
polling loop is unbounded by construction, and this one cannot be.

**Every Act has a Verify immediately after it — never two Acts in a
row.** `_act()` and `_verify()` are called exactly once each per loop
iteration, in that order, and `_verify()` always re-observes through
`DesktopObserver` — never through a cached value, never by reading a
window directly.

**One Observe establishes the step's baseline, before the retry loop
begins; every attempt's Verify re-observes and compares against that
baseline, not against the previous attempt's own reading.** This is
deliberate. An earlier attempt can already have produced the intended
change — the window is already titled correctly, already focused,
already responding — and a later retry's own Act can then legitimately
do nothing further. Comparing each attempt only against its own
immediately-preceding Observe would make a step that already succeeded
look like a fresh failure on every subsequent retry, forever, which is
not what `ExpectedOutcome.expect_change` means: it asks *"is the world
different from when this step began?"*, never *"did this specific retry's
own action do something new?"* `run_step()`'s own docstring restates this
at the point it matters.

## Desktop Executive Usage

Every `_act()` branch calls exactly one `DesktopExecutor` (C26) method —
`.execute()`, `.focus()`, `.type()`, `.click()`, `.wait()` (via a bare
`sleep`, injected — see below), `.close()`, or, for the two recovery
kinds `DesktopExecutor`'s six-method API has no dedicated call for,
`.browser.open_url()` (refresh) — still a `DesktopExecutor` sub-component,
never a second `BrowserExecutive`. No `subprocess`, mouse, keyboard,
browser, window, or clipboard call is ever made directly; `tests/
test_desktop_operator.py`'s guard checks this by AST.

## Desktop Perception Usage

Every `_observe()` call is exactly one `DesktopObserver.observe()` (C27)
call. **No window, browser, or UI fact is read any other way.**

## Why `_observe()` also calls `desktop.inventory.discover()`

`DesktopObserver.observe()` (C27) takes an optional `MachineInventory` and
uses it to attribute a window's process id to an application key — without
one, C27's own `WindowObserver` cannot say *which* application a window
belongs to, and every readiness/verification check in this package
depends on that attribution. C27 left the parameter caller-supplied on
purpose (its own module docstring: *"Caller-supplied, never read from an
ambient clock/probe inside this layer"*), which makes *someone* upstream
responsible for supplying it.

**`MachineInventory` is not a window, a browser, or UI state — it is
Desktop Executive's own data model** (`desktop/inventory.py`, consumed
throughout `desktop/actions.py`, `desktop/execution/process.py`, and
`desktop/operations` already). `discover()` reads installed applications
and the process list through a `SystemProbe` — the same read
`ProcessExecutive.is_running()` already performs internally on every
call — never a mouse, keyboard, window handle, or browser page. This is
judged **not** to be the "read windows/browser/UI directly" the brief
forbids, for the same reason `founder_edition/boot.py` (C24) was already
permitted to call `discover()` as its own composition root's one
machine-touching step: an inventory scan is a fact about installed
software and running processes, not about what is currently on screen.
Recorded as a stated judgment call in `Engineering/HEALTH_C28.md` §7
rather than left implicit.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from master_agent.desktop.execution.executor import DesktopExecutor
from master_agent.desktop.inventory import MachineInventory, discover
from master_agent.desktop.perception import DesktopObserver, DesktopState
from master_agent.desktop.probe import RealSystemProbe, SystemProbe
from master_agent.desktop_operator.execution_result import EscalationRequest
from master_agent.desktop_operator.mission_context import (
    ActionKind,
    MissionContext,
    MissionStep,
    StepAction,
)
from master_agent.desktop_operator.tactical_recovery import (
    MAX_RETRIES,
    RecoveryKind,
    RecoveryPlan,
    TacticalRecovery,
)
from master_agent.desktop_operator.timeouts import TimeoutGovernor

#: The wait a `WAIT_FOR_LOADING` recovery sleeps for, capped by whatever
#: time remains in the step's own timeout — never longer, so recovery
#: itself cannot cause the timeout it exists beside.
RECOVERY_WAIT_SECONDS = 1.0


class StepStatus(str, Enum):
    SUCCESS = "success"
    ESCALATED = "escalated"


@dataclass(frozen=True)
class StepOutcome:
    status: StepStatus
    attempts_used: int
    log_line: str
    escalation: EscalationRequest | None = None


class DesktopStateMachine:
    """One instance runs the Core Execution Loop for one `DesktopTask`'s
    steps, in order, holding exactly one `DesktopExecutor` and one
    `DesktopObserver` — never constructing a second of either."""

    def __init__(
        self,
        executor: DesktopExecutor,
        observer: DesktopObserver,
        *,
        probe: SystemProbe | None = None,
        recovery: TacticalRecovery | None = None,
        timeouts: TimeoutGovernor | None = None,
        sleep: Callable[[float], None],
        clock: Callable[[], datetime],
    ) -> None:
        self._executor = executor
        self._observer = observer
        self._probe = probe or RealSystemProbe()
        self._recovery = recovery or TacticalRecovery()
        self._timeouts = timeouts or TimeoutGovernor()
        self._sleep = sleep
        self._clock = clock

    def run_step(self, step_index: int, step: MissionStep, context: MissionContext) -> StepOutcome:
        """One Observe happens *before* the retry loop, establishing this
        step's own baseline; every attempt's Verify compares against
        *that* baseline, never against the previous attempt's own
        Observe. This is deliberate, not a shortcut: once an earlier
        attempt already produced the intended change, a later retry's
        Act can legitimately do nothing new (the window is already
        titled correctly, already focused, already ready) — comparing
        against the immediately-preceding Observe instead of the step's
        baseline would make a retry that already succeeded look like a
        fresh failure every single time, which is not what *"expect
        change"* means. `expect_change` asks *"is the world different
        from when this step began?"*, not *"did the last click, this
        specific time, do something new?"*
        """
        context.begin_step(self._clock())
        pending_recovery: RecoveryPlan | None = None

        step_baseline = self._observe(step)
        context.record_observation(step_baseline)

        for attempt in range(1, MAX_RETRIES + 1):
            self._timeouts.check(
                step_index=step_index, started_at=context.step_started_at,
                now=self._clock(), timeout_seconds=step.timeout_seconds,
            )

            # ── Decide (tactical only) ──────────────────────────────
            action = self._decide(step, pending_recovery)
            context.previous_action = action

            # ── Act ──────────────────────────────────────────────────
            self._act(step.application, action)

            self._timeouts.check(
                step_index=step_index, started_at=context.step_started_at,
                now=self._clock(), timeout_seconds=step.timeout_seconds,
            )

            # ── Verify (re-Observe through Desktop Perception) ────────
            post_observation = self._observe(step)
            context.record_observation(post_observation)
            context.record_delta(_changed_sections(step_baseline, post_observation))
            verified = self._verify(step, step_baseline, post_observation)

            # ── State Evaluator ──────────────────────────────────────
            if verified:
                context.record_step_result(f"step {step_index}: verified on attempt {attempt}")
                return StepOutcome(StepStatus.SUCCESS, attempt, f"verified on attempt {attempt}")

            context.step_retries = attempt
            if attempt == MAX_RETRIES:
                escalation = EscalationRequest(
                    step_index=step_index,
                    reason=f"verification failed after {attempt} attempt(s)",
                    retries_exhausted=attempt,
                    last_observation_confidence=post_observation.confidence,
                    detail=(
                        f"{step.application}: last action {action.kind.value} did "
                        f"not verify; changed sections: {context.verification_delta}"
                    ),
                )
                context.record_step_result(f"step {step_index}: escalated after {attempt} attempts")
                return StepOutcome(StepStatus.ESCALATED, attempt, "escalated", escalation)

            plan = self._recovery.plan(step, context)
            self._apply_recovery(plan, step, context)
            pending_recovery = plan

        raise AssertionError(  # pragma: no cover — unreachable given the range(1, MAX_RETRIES + 1) bound above
            "unreachable: the loop always returns within MAX_RETRIES iterations"
        )

    # ---- the four phases ---------------------------------------------

    def _observe(self, step: MissionStep) -> DesktopState:
        inventory = self._current_inventory()
        return self._observer.observe(
            self._clock(), applications=(step.application,), inventory=inventory,
        )

    def _current_inventory(self) -> MachineInventory:
        """The one call in this whole package to `desktop.inventory
        .discover()` — never a window, browser, or UI read (see the
        module docstring's "Reading the inventory" note for why this is
        not the same category of thing `DesktopObserver.observe()`'s own
        `inventory` parameter needs supplied by *someone*, and why that
        someone is this class rather than a caller reaching around it)."""
        return discover(self._probe, read_versions=False)

    def _decide(self, step: MissionStep, pending_recovery: RecoveryPlan | None) -> StepAction:
        """Tactical only. The only decision this method can make is
        *which of the step's own pre-approved targets to use* — never a
        new target, never a new application, never a new kind of action."""
        if pending_recovery is not None and pending_recovery.kind is RecoveryKind.USE_ALTERNATE_TARGET:
            return StepAction(
                kind=step.action.kind,
                x=step.action.alternate_x, y=step.action.alternate_y,
                text=step.action.text, wait_seconds=step.action.wait_seconds,
            )
        return step.action

    def _act(self, application: str, action: StepAction) -> None:
        """Exactly one `DesktopExecutor` call. See the module docstring."""
        if action.kind is ActionKind.CLICK:
            self._executor.click(application, action.x, action.y)
        elif action.kind is ActionKind.TYPE:
            self._executor.type(application, action.text)
        elif action.kind is ActionKind.FOCUS:
            self._executor.focus(application)
        elif action.kind is ActionKind.WAIT:
            self._sleep(action.wait_seconds)
        elif action.kind is ActionKind.EXECUTE:
            self._executor.execute(application)
        elif action.kind is ActionKind.CLOSE:
            self._executor.close(application)
        else:  # pragma: no cover — ActionKind is closed and exhausted above
            raise ValueError(f"unknown action kind: {action.kind}")

    def _verify(self, step: MissionStep, pre: DesktopState, post: DesktopState) -> bool:
        """Always through Desktop Perception's own already-produced
        observations — never a second read, never a direct window/UI
        inspection."""
        post_app = post.application(step.application)
        if step.expected.readiness is not None and (
            post_app is None or post_app.readiness.value != step.expected.readiness
        ):
            return False

        if step.expected.expect_change:
            pre_app = pre.application(step.application)
            if not _application_changed(pre_app, post_app):
                return False

        return True

    def _apply_recovery(self, plan: RecoveryPlan, step: MissionStep, context: MissionContext) -> None:
        """The one place a `RecoveryPlan` becomes a real call — every
        branch goes through `DesktopExecutor` (C26), including its
        `.browser` sub-component for the one kind (`REFRESH_PAGE`) the
        six-method unified API has no dedicated call for."""
        if plan.kind in (RecoveryKind.REFOCUS_APPLICATION, RecoveryKind.REOPEN_WINDOW):
            self._executor.focus(step.application)
        elif plan.kind is RecoveryKind.WAIT_FOR_LOADING:
            remaining = self._timeouts.remaining(
                started_at=context.step_started_at, now=self._clock(),
                timeout_seconds=step.timeout_seconds,
            )
            self._sleep(min(RECOVERY_WAIT_SECONDS, remaining))
        elif plan.kind is RecoveryKind.REFRESH_PAGE:
            url = (
                context.current_observation.browser.current_url.value
                if context.current_observation is not None else None
            )
            if url is not None:
                self._executor.browser.open_url(url)
        # RETRY_CLICK and USE_ALTERNATE_TARGET need no separate recovery
        # call — the next loop iteration's Act already retries.


def _application_changed(pre, post) -> bool:
    if pre is None or post is None:
        return pre is not post
    if pre.readiness.value != post.readiness.value:
        return True
    pre_window = pre.window.value
    post_window = post.window.value
    if (pre_window is None) != (post_window is None):
        return True
    if pre_window is not None and post_window is not None:
        return pre_window.title != post_window.title
    return False


def _changed_sections(pre: DesktopState, post: DesktopState) -> tuple[str, ...]:
    """A minimal, honest delta — not `ObservationHistory`'s own
    `changes_since()` (that class belongs to a live session's history,
    not one ephemeral before/after comparison), but the same idea: name
    *which* facts differ rather than making a caller diff the whole
    state by hand."""
    changed = []
    if pre.confidence != post.confidence:
        changed.append("confidence")
    if pre.browser.current_url.value != post.browser.current_url.value:
        changed.append("browser")
    if pre.clipboard.has_content.value != post.clipboard.has_content.value:
        changed.append("clipboard")
    for pre_app in pre.applications:
        post_app = post.application(pre_app.application)
        if post_app is not None and _application_changed(pre_app, post_app):
            changed.append(f"application:{pre_app.application}")
    return tuple(changed)
