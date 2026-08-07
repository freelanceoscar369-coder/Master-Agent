"""The mission pipeline (Mission Brief 037).

```
Founder objective -> Planner -> MissionPlan -> Execution -> Verifier -> Memory
```

MB036 built a Planner and wired it to nothing. This package is the wiring,
and it is **only** wiring: it decomposes nothing, selects no provider,
computes no verdict and stores no memory. Each of those already has
exactly one owner, and MB037's whole job is to put them in a line.

## Why there is so little code here

Almost every guarantee this brief asks for already existed, unconnected:

- **Dependency order** — Mission Control's Task Dispatcher (MB023) has
  dispatched in dependency order since it shipped.
- **Verification per step** — the Runtime already verifies whenever
  `task.expected_outcome` is present, records the `evidence_id` on the
  task, and fails the task when the verdict is not `matched` (MB024/MB035).
- **Lessons from failure** — `MemoryService.attach_to()` already
  subscribes to `OBJECTIVE_FAILED` and writes to the Failure Library
  (MB034).
- **`Task.expected_outcome`** — MB023 added the field, with a comment
  citing Constitution §3.2 and the Planner that did not exist yet.

So `translation.py` is a 1:1 field mapping and the pipeline is a sequence
of published calls. That is the strongest evidence yet that the
Constitution's decomposition was right: the brief that connects six
subsystems needed no new architecture from any of them.
"""
from master_agent.missions.history import (
    PlanHistory,
    PlanRecord,
    Replay,
    ReplayStep,
    StepRecord,
)
from master_agent.missions.service import MissionOutcome, MissionService
from master_agent.missions.translation import (
    REQUIRED_STEP_FIELDS,
    PlanIncomplete,
    incomplete_steps,
    objective_from_plan,
)

__all__ = [
    "REQUIRED_STEP_FIELDS",
    "MissionOutcome",
    "MissionService",
    "PlanHistory",
    "PlanIncomplete",
    "PlanRecord",
    "Replay",
    "ReplayStep",
    "StepRecord",
    "incomplete_steps",
    "objective_from_plan",
]
