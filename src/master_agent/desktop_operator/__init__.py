"""Desktop Operator (C28) — a deterministic human-like execution loop
over the Desktop Executive (C26) and Desktop Perception (C27).

```
   Founder Runtime (C23)
        │  DesktopTask
        ▼
   Desktop Operator          Observe → Decide (tactical only) → Act → Verify
        │  ExecutionResult      │                                        │
        ▼                       └──────────── State Evaluator ───────────┘
   Founder Runtime                    SUCCESS → continue
                                       FAILURE → Tactical Recovery → retry (≤3) or escalate
```

**Never decides strategy. Never plans missions. Never replaces Founder
Runtime.** `DesktopOperator.execute(DesktopTask) -> ExecutionResult` is
the entire public surface — see `operator.py` for the one method, and
`Engineering/HEALTH_C28.md` for the full architecture, retry policy,
timeout policy, and Founder Runtime boundary.
"""
from __future__ import annotations

from master_agent.desktop_operator.execution_result import (
    EscalationRequest,
    ExecutionResult,
    MissionOutcome,
)
from master_agent.desktop_operator.mission_context import (
    ActionKind,
    DesktopTask,
    ExpectedOutcome,
    MissionContext,
    MissionStep,
    StepAction,
)
from master_agent.desktop_operator.operator import DesktopOperator
from master_agent.desktop_operator.state_machine import DesktopStateMachine, StepOutcome, StepStatus
from master_agent.desktop_operator.tactical_recovery import (
    MAX_RETRIES,
    RecoveryKind,
    RecoveryOutcome,
    RecoveryPlan,
    TacticalRecovery,
)
from master_agent.desktop_operator.timeouts import StepTimeoutFailure, TimeoutGovernor

__all__ = [
    "MAX_RETRIES",
    "ActionKind",
    "DesktopOperator",
    "DesktopStateMachine",
    "DesktopTask",
    "EscalationRequest",
    "ExecutionResult",
    "ExpectedOutcome",
    "MissionContext",
    "MissionOutcome",
    "MissionStep",
    "RecoveryKind",
    "RecoveryOutcome",
    "RecoveryPlan",
    "StepAction",
    "StepOutcome",
    "StepStatus",
    "StepTimeoutFailure",
    "TacticalRecovery",
    "TimeoutGovernor",
]
