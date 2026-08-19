# KALPAVRIKSHA — RUNTIME OVER-DISPATCH REPAIR & MEDIUM RE-RUN

**Date:** 2026-08-19 · **Artifact:** 2026-08-19 18:07:04, 34,257,200 bytes

**The scheduler repair worked.** All six steps executed and the mission reached
`completed` — the first time the Medium objective has run end to end.

Three findings follow, and the mission stops at the designated boundary.

---

## 1. Git Truth

`d52b7e7` local == origin/main, ahead 0, behind 0, nothing staged, 5 modified tracked
and 111 untracked preserved.

---

## 2. Repair Implemented

Capacity now travels to the decision instead of a slice being applied after it.

| File | Change |
|---|---|
| `mission_control/dispatcher.py` | `dispatch_ready(objective_id, limit=None)` — the limit is checked **before any state is touched**; surplus tasks stay `READY` |
| `mission_control/mission_control.py` | facade passes `limit` through |
| `runtime/engine.py` | `_cycle()` declares `capacity = max_concurrent_tasks` and asks for exactly that; `_dispatch(limit)` spends the budget **across** objectives |

`limit=None` preserves the previous unbounded behaviour. Every pre-existing caller
omits it, so nothing else changed. `max_concurrent_tasks` was **not** raised, nothing
is dispatched-then-reverted, and no new scheduler type was introduced.

### A second instance of the same bug, found while in there

`_resume_awaiting()` pops held tasks off `_awaiting_approval` and clears it. Any held
task beyond capacity was therefore dropped exactly as `step_4` was. Held tasks that do
not fit are now **put back** rather than lost.

---

## 3. Deterministic Proof

`tests/test_dispatch_capacity.py` — **13 tests, all pass**, covering all five required
shapes including the exact Medium six-step scheduling shape.

Validated by reintroducing the defect: **5 tests fail**, including
`test_step_4_is_not_committed_in_the_first_cycle`; restored, all pass.

Regression across 19 suites: **17 failures at HEAD, 17 with the repair, 0 introduced**
(named set difference, not counts).

---

## 4. Packaged Re-run — scheduler verdicts

Isolated profile, microphone absent (`✗ Voice pipeline`), normal Founder root untouched
(11 records).

| step | capability | before | after |
|---|---|---|---|
| step_1 | `Browser.OpenBrowserSession` | completed | **completed** |
| step_2 | `Browser.Navigate` | completed | **completed** |
| step_3 | `Browser.ObserveBrowser` | completed | **completed** |
| step_4 | `Filesystem.CreateFolder` | **DISPATCHED, never started** | **completed** |
| step_5 | `Filesystem.WriteFile` | never assigned | **completed** |
| step_6 | `Browser.CloseBrowserSession` | completed | **completed** |

Plan state: **`completed`** (previously `running` forever). No dispatch→idle spin. The
folder `KV_MEDIUM_180730` was created on the Desktop.

---

## 5. Finding 1 — NEXT LIVE FAILURE: Observation → later-step input

The written file, read independently:

```
Title: Example Domain
URL: https://example.com/
```

48 bytes — **byte-identical to the content the Planner wrote into `step_5`'s payload at
plan time**, before the browser had been opened. Onkar asked for *"the title and URL you
actually observed"*.

`step_3` (`ObserveBrowser`) completed with **no result retained**: its persisted record
has `evidence_id: null`, `verdict: ""`, and no result or output field of any kind. The
observation is not stored anywhere, so nothing downstream could have consumed it even if
a mechanism existed.

This is the boundary the brief designated as the stop point. **Not repaired.**

---

## 6. Finding 2 — the file was written to a different folder than the one created

Two filesystem capabilities express location in two different vocabularies, and the plan
mixed them:

| step | payload | resolved to |
|---|---|---|
| step_4 `Filesystem.CreateFolder` | `{"name": "KV_MEDIUM_180730", "location": "Desktop"}` | `C:\Users\DELL\Desktop\KV_MEDIUM_180730` |
| step_5 `Filesystem.WriteFile` | `{"path": "Desktop/KV_MEDIUM_180730/page_info.txt"}` | `C:\Users\DELL\Desktop\**Desktop**\KV_MEDIUM_180730\page_info.txt` |

`CreateFolder` takes `location` as a **named base directory**; `WriteFile` takes a
`path` resolved **relative to that same base**. The Planner supplied `Desktop/...` as the
path, which resolved to `Desktop\Desktop\...`.

**Both steps reported success.** The requested folder was left empty and the file landed
in a nested directory nobody asked for.

### This is long-standing, not new

`C:\Users\DELL\Desktop\Desktop\` **already existed, created 2026-07-31**, and already
contained:

- `demo_api` (2026-07-31)
- `Research on my Desktop` (2026-08-14) — an artifact of the earlier name-swallowing bug

So this path-vocabulary mismatch has been quietly depositing misplaced files for weeks.
Only this run's artifact was removed; the pre-existing ones were left untouched for
Onkar to decide about.

---

## 7. Finding 3 — "Done" was reported for work that does not match the objective

The Founder Surface showed:

> **Done — Open a browser and navigate to https://example.com. Observe the page's actual
> title and final URL. Create a folder called KV_MEDIUM_180730 on Desktop. Inside that
> folder create a text file...**

At that moment the requested folder was **empty**, the file was in a phantom directory,
and its contents had never been observed. Every step returned success, so Verification
and the Reporter both concluded the objective was achieved.

This is the **false operational commitment** class, previously listed as a deferred
finding and now demonstrated end to end on a real mission: step-level success was
treated as objective-level success. Recorded, not repaired.

---

## 8. Persistence / Reconstruction

Reconstructable from disk by identifier: objective, plan_id, mode (`both`/`both`),
`planned_by: gemini.api`, tier attempts, all six steps and their states, terminal state
`completed`.

**Not reconstructable:** the browser's actual observed title and URL — never recorded
(see §5).

---

## 9. Cleanup

Removed: this run's Desktop folder, its misplaced nested artifact, and the FMEA state
root (evidence preserved in the session scratchpad, including the written file).
Left untouched: the two pre-existing artifacts in `Desktop\Desktop`, and normal Founder
state (11 records, unchanged). No Kalpavriksha processes running.

---

## 10. Verdicts

| Condition | Verdict |
|---|---|
| DISPATCH LIMITED BEFORE STATE COMMIT | **READY** |
| NO DISPATCHED-BUT-UNSTARTABLE TASK | **READY** |
| REMAINING TASKS STAY READY | **READY** |
| EXECUTIVE BUSY STATE CORRECT | **READY** |
| MEDIUM STEP_4 STARTS | **READY** |
| MEDIUM SCHEDULER PROGRESS | **READY** |
| NEXT LIVE FAILURE | **Observation → later-step input** |

---

## 11. Readiness for the Next Repair

The next mission is the designated one: give the existing architecture a data-flow
contract so a later step can consume an earlier step's observed output. Two facts scope
it, both established live rather than by prediction:

1. `Step.payload` is fixed at plan time — the Planner filled the gap with a prediction
   because it had no way to reference `step_3`.
2. `ObserveBrowser`'s result is **not retained at all**. A reference mechanism alone is
   insufficient; the observation has to be recorded before anything can point at it.

Findings 2 and 3 are recorded and deliberately left for Onkar to sequence. Finding 2 is
independent of data flow and would misplace the file even with a correct observation.
