# MB039B — Dispatch Failure Root Cause

**Status:** Diagnosis complete. **No code changed. No frozen file touched.**
**Date:** 2026-07-31
**Confidence: HIGH** — reproduced deterministically without an LLM, and
confirmed by a single-variable control.

---

## 1. Root cause

**Task identity is not unique across missions.**

`missions/translation.py::task_from_step()` sets:

```python
task_id=step.step_id
```

Step ids are unique **within** one plan — MB036's `validate()` refuses a
plan containing two steps with the same id. They are **not** unique
across plans, and the Planner names the first step of nearly every plan
`step_1`.

So the second mission in a process submits a `Task` whose `task_id` is
`step_1`, which the first mission already used. Two Runtime structures
are keyed by `task_id` **alone**, with no objective in the key:

| Structure | Key | Module |
|---|---|---|
| `RuntimeEngine._awaiting_approval` | `task_id` | `runtime/engine.py` |
| `ApprovalQueue.find_open(task_id, capability)` | `task_id` + capability | `mission_control/approvals.py` |

When mission 3's `step_1` reaches the approval boundary, the lookup
resolves against mission 1's **already-decided** `step_1`. The boundary
returns a decision that belongs to a different mission, `_handle_task()`
exits without starting, failing or re-holding the task, and the task is
left in `dispatched` forever.

---

## 2. Evidence

### 2.1 The control that proves it

Same four plans, same submission path, same cycle budget, no LLM. The
**only** variable changed is the step ids.

| Step ids | Result |
|---|---|
| `step_1`, `step_1`/`step_2`, `step_1`, `step_1` (colliding) | **1 of 4** missions complete |
| `a_step_1`, `b_step_1`/`b_step_2`, `c_step_1`, `d_step_1` (unique) | **4 of 4** missions complete |

```
--- colliding ---
MISSION 1  complete=True    history: completed  [('step_1','completed')]
MISSION 2  complete=False   history: running    [('step_1','pending'), ('step_2','completed')]
MISSION 3  complete=False   history: planned    [('step_1','pending')]
MISSION 4  complete=False   history: planned    [('step_1','pending')]

--- unique ---
MISSION 1  complete=True    [('a_step_1','completed')]
MISSION 2  complete=True    [('b_step_1','completed'), ('b_step_2','completed')]
MISSION 3  complete=True    [('c_step_1','completed')]
MISSION 4  complete=True    [('d_step_1','completed')]
```

Mission 2 is the decisive row. It has two steps: `step_1` **collides**
with mission 1's and strands; `step_2` is unique in the process and
**completes**. One mission, two tasks, two different outcomes, separated
only by whether the id had been seen before.

### 2.2 Hand-built objectives never reproduce it

Three missions submitted directly as `Objective`s with ids `probe1_1`,
`probe2_1`, `probe3_1` — all complete, gate `PENDING` then `PASSED` each
time. The dispatcher, the approval boundary and the executive are all
healthy. Only ids produced by `task_from_step()` collide.

### 2.3 State transition audit — mission 3, colliding

| Cycle | Component | Event | Task state |
|---|---|---|---|
| — | `MissionService.start` | objective submitted | `created` |
| 0 | `TaskDispatcher.dispatch_ready` | assigned to `filesystem` | **`dispatched`** |
| 0 | `RuntimeEngine._handle_task` | boundary → `ApprovalPending` | `dispatched` |
| 0 | `_await_approval` | held in `_awaiting_approval["step_1"]` | `dispatched` |
| 0 | harness | founder approves | `dispatched` |
| 1 | `_resume_awaiting` | re-offered | `dispatched` |
| 1 | `_handle_task` | boundary consulted, resolves against **mission 1's** `step_1` | `dispatched` |
| 1 | — | returns without `task_started`, without `_refuse`, without re-hold | **`dispatched`** |
| 2–11 | `_dispatch` | not returned — state is `dispatched`, not ready | **`dispatched`** |

**State stops changing at cycle 1**, inside the approval boundary of
`_handle_task`. `TASK_STARTED` is never published, which is why
`PlanHistory` still reads `planned`/`pending`.

### 2.4 Dispatcher decision path

The Dispatcher **receives the mission and dispatches it correctly.**
`_dispatch()` iterates *every* objective:

```python
for objective in self._mc.dispatcher.objectives():
    assigned.extend(self._mc.dispatch_ready(objective.objective_id))
```

The task reaches `dispatched` on cycle 0 in every failing case. The
Dispatcher is not refusing anything.

### 2.5 Executive availability — DISPROVEN

My MB039 hypothesis was wrong, and the trace disproves it:

- executive selected: `filesystem`, on every task including stranded ones
- busy: no — later tasks in the same process dispatch normally
- queue length: `dispatch_ready` returns 4, 3, 2, 1 as work drains
- semaphore: `max_concurrent_tasks = 1`, correctly honoured
- occupancy: not consulted for capability tasks (that is MB038's
  provider-side register)
- admission: MB038 admission control applies to *provider calls*, not to
  capability tasks; it is not on this path

A control trace with three missions and four tasks completed all four in
eight cycles, with the boot scan objective present. Availability is
healthy.

### 2.6 Queue audit

| Queue | Producer | Consumer | Enqueue | Dequeue | Final length |
|---|---|---|---|---|---|
| `TaskDispatcher` objectives | `submit_objective` | `_dispatch` | 5 | n/a (iterated) | 5 |
| ready tasks (derived) | `dispatch_ready` | `_run_cycle` | 4 | 4 | 0 |
| `_awaiting_approval` | `_await_approval` | `_resume_awaiting` | 4 | 4 | 0 |
| `ApprovalQueue` open | boundary | founder | 4 | 4 | 0 |

**No queue retains work.** Nothing is un-consumed. The stranded tasks are
not *in* a queue — they hold a terminal-looking `dispatched` state that
no producer will re-offer.

---

## 3. Classification

**Architectural flaw** — identity namespacing.

Not scheduling (the scheduler dispatches correctly), not a queue bug (no
queue retains work), not a race (fully deterministic, single-threaded,
no LLM), not a deadlock (nothing waits on anything).

Two subsystems assume `task_id` is globally unique. The plan→objective
translation introduced by MB037 makes it unique only per plan. The
observable *symptom* is a missing transition; the *cause* is that two
different tasks share an identity.

---

## 4. Affected modules

| Module | Role | Frozen |
|---|---|---|
| `missions/translation.py` | **origin** — assigns the colliding id | no |
| `runtime/engine.py` | `_awaiting_approval` keyed by `task_id` | **yes** |
| `mission_control/approvals.py` | `find_open(task_id, …)` | **yes** |
| `missions/history.py` | reads `pending` because no event arrives | no |

---

## 5. Minimal fix location

**One function, one non-frozen file:**

`src/master_agent/missions/translation.py::task_from_step()`

Make the `task_id` unique per objective while preserving the founder-
facing step name. The two frozen consumers need no change — they are
correct given a unique id, and were correct before MB037 introduced a
non-unique one.

MB037's stated reason for reusing `step_id` was that *"a founder reading
`write_readme` in the Dashboard and `write_readme` in the plan should be
reading about the same thing"*. That goal survives: the step name is
already carried separately in `PlanRecord.steps[].step_id`, so the
display name does not depend on the task id.

**Not recommended:** changing the frozen keying. It would be a larger
change, in frozen files, to accommodate an id that should not be
ambiguous in the first place.

---

## 6. Scope of impact

Only the **second and subsequent** missions in one process. A single
mission per process — every prior brief's validation, including MB038's
acceptance — never collides, which is why this survived to MB039.

It also silently corrupts `PlanHistory`: a stranded task reads `pending`
forever, so the Dashboard shows a mission as `planned` that was in fact
dispatched and abandoned.

---

## 7. Reproduction

- `scratchpad/mb039b_trace.py` — control: hand-built objectives, unique
  ids, with and without the boot scan. All complete.
- `scratchpad/mb039b_repro.py` — failure: `MissionService`, colliding
  ids. 1 of 4.
- `scratchpad/mb039b_repro_unique.py` — same, unique ids. 4 of 4.
- `scratchpad/mb039b_probe.py` — instrumented boundary showing
  `PENDING` → `PASSED` on the healthy path.

None requires an LLM. All are deterministic.

---

## 8. Confidence

**HIGH.** Single-variable control, deterministic reproduction in both
directions, and a mechanism traced to two named lookups. The one thing I
did **not** do is step inside `FounderApprovalGate._decided_for()` to name
which of the two colliding lookups returns first — the behaviour is
proven and the fix location is unaffected by which, but that detail is
unverified and stated as such.
