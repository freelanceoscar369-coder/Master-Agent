"""C28 · `DesktopOperator` — the whole Founder Runtime boundary in one
method.

```
   Founder Runtime
        │  DesktopTask
        ▼
   DesktopOperator.execute()
        │  runs DesktopStateMachine.run_step() once per step, in order
        ▼
   ExecutionResult
        │
        ▼
   Founder Runtime
```

*"Desktop Operator executes exactly one desktop mission... Desktop
Operator NEVER decides strategy. Desktop Operator NEVER plans missions.
Desktop Operator NEVER replaces Founder Runtime."* `execute()` is the
entire public surface a caller needs: it takes the `DesktopTask` Founder
Runtime already planned, runs the Core Execution Loop
(`state_machine.py`) over each of its steps in the order given, and
returns one `ExecutionResult`. It adds no step, reorders none, and
invents no application choice.

## `MissionContext` is created here, and only here

`execute()` constructs exactly one `MissionContext`, as a **local
variable** — never assigned to `self`. When `execute()` returns, nothing
in this object still references it; `test_mission_context_does_not_
survive_execute` confirms `DesktopOperator` carries no such attribute
after a call completes. This is the brief's *"lives only during one
execution... destroyed immediately after mission... never persisted...
never enters Memory"* made structural rather than promised.

## Everything reachable through exactly one `DesktopExecutor` and one
`DesktopObserver`

Constructed once, in `__init__`, and never re-constructed per mission or
per step. `DesktopOperator` never imports `desktop.execution.window`,
`.keyboard`, `.mouse`, `.clipboard`, `.process`, `.browser`, or
`desktop.perception.windows`/`.browser`/`.clipboard`/`.readiness`
directly — only through the two composed objects, both defaulting to
their own real implementations the same way `DesktopExecutor()` and
`DesktopObserver()` already do on their own.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, datetime

from master_agent.desktop.execution.executor import DesktopExecutor
from master_agent.desktop.perception import DesktopObserver
from master_agent.desktop.probe import SystemProbe
from master_agent.desktop_operator.execution_result import ExecutionResult, MissionOutcome
from master_agent.desktop_operator.mission_context import DesktopTask, MissionContext
from master_agent.desktop_operator.state_machine import DesktopStateMachine, StepStatus
from master_agent.desktop_operator.tactical_recovery import TacticalRecovery
from master_agent.desktop_operator.timeouts import StepTimeoutFailure, TimeoutGovernor

#: Re-exported so a caller building a `DesktopTask` needs only this
#: module — the boundary the brief names is `DesktopTask` in,
#: `ExecutionResult` out.
__all__ = ["DesktopOperator", "DesktopTask", "ExecutionResult"]


def _default_clock() -> datetime:
    return datetime.now(UTC)


class DesktopOperator:
    """One `DesktopExecutor`, one `DesktopObserver`, one state machine.
    Holds no mission state between calls — every `execute()` call is
    independent, and nothing about one mission survives into the next."""

    def __init__(
        self,
        executor: DesktopExecutor | None = None,
        observer: DesktopObserver | None = None,
        *,
        probe: SystemProbe | None = None,
        recovery: TacticalRecovery | None = None,
        timeouts: TimeoutGovernor | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], datetime] = _default_clock,
    ) -> None:
        self._executor = executor or DesktopExecutor()
        self._observer = observer or DesktopObserver()
        self._clock = clock
        self._state_machine = DesktopStateMachine(
            self._executor, self._observer, probe=probe,
            recovery=recovery, timeouts=timeouts, sleep=sleep, clock=clock,
        )

    def execute(self, task: DesktopTask) -> ExecutionResult:
        """Run every step of `task`, in order, stopping at the first
        escalation or timeout. Returns exactly one `ExecutionResult` —
        nothing more, per the brief's own boundary."""
        started_at = self._clock()
        context = MissionContext(task=task, started_at=started_at)
        step_results: list[str] = []

        for index, step in enumerate(task.steps):
            try:
                outcome = self._state_machine.run_step(index, step, context)
            except StepTimeoutFailure as exc:
                return ExecutionResult(
                    mission_id=task.mission_id, outcome=MissionOutcome.TIMED_OUT,
                    steps_completed=index, steps_total=len(task.steps),
                    reason=str(exc), started_at=started_at, finished_at=self._clock(),
                    step_results=tuple(step_results),
                )

            step_results.append(outcome.log_line)

            if outcome.status is StepStatus.ESCALATED:
                return ExecutionResult(
                    mission_id=task.mission_id, outcome=MissionOutcome.ESCALATED,
                    steps_completed=index, steps_total=len(task.steps),
                    reason=f"step {index} escalated: {outcome.escalation.reason}",
                    started_at=started_at, finished_at=self._clock(),
                    escalation=outcome.escalation, step_results=tuple(step_results),
                )

        return ExecutionResult(
            mission_id=task.mission_id, outcome=MissionOutcome.SUCCESS,
            steps_completed=len(task.steps), steps_total=len(task.steps),
            reason="every step verified", started_at=started_at, finished_at=self._clock(),
            step_results=tuple(step_results),
        )
        # `context` falls out of scope here. Nothing above assigned it to
        # `self`, returned it, or passed it anywhere that outlives this
        # call — it is destroyed the moment this frame is.
