# KALPAVRIKSHA — REPORTER PRODUCTION WIRING REPORT

**Date:** 2026-08-19 · **Base:** `4a57821` == `origin/main`, ahead 0, behind 0

**Yes — Somesh can now explain a completed or failed mission from authoritative Mission
history plus the exact Evidence Verification produced, without using the last Task output
and without fabricating missing facts.**

---

## 1. Git Truth

`HEAD == origin/main == 4a57821`, ahead 0, behind 0, nothing staged. Protected worktree
(5 modified, 111 untracked) untouched. No reset, no clean.

---

## 2. The reporting bypass that was removed

Terminal Founder messages were composed from `FounderState.result` — explicitly *the most
recently completed Task's output*:

```python
status.message = _describe_result(state.result, status.objective or "")
```

Truthful as "the last task result". Untruthful as "the mission outcome": a three-step
browser mission ending in cleanup reported `{"closed": true}` as the thing Onkar had asked
for, and an earlier build rendered the same value as `[object Object]`.

The comment above the completion branch also asserted *"Verification has already compared
it against the Step's expected outcome by the time this event fires."* It had not — every
gateway returned no Evidence — and that belief is how Onkar was told "Done" for an empty
folder. Both the code and the false comment are gone.

`FounderState.result` itself is **kept**; other consumers legitimately want the last Task
result. Only its misuse as the mission-level report was removed.

---

## 3. Legacy Mission interface — not revived

`Reporter.report_mission_outcome()` is typed against `mission_manager.Mission`.
Constructing synthetic `Mission(...)` objects from `PlanRecord` just to call it would give
two Mission representations that can drift — the same shape of mistake as the launcher
rebuilding `Evidence` from an id. **No synthetic Mission is built anywhere.** The legacy
API is preserved untouched and additively.

---

## 4–5. Authoritative record and the production entry point

`Reporter.report_plan_record_outcome(record, context) -> Report` consumes the existing
`PlanRecord`. No `MissionReportState`, no `MissionOutcomeV2`, no new mission type.

---

## 6. Canonical Evidence consumption

Exact Evidence is recovered **only** from `Evidence.from_dict(step.evidence)`. Never from
`evidence_id`, a verdict string, a capability name or a timestamp. A step whose `evidence`
is `None` — or whose projection this build cannot parse — is **unverified**, reported as
such and never filled in.

---

## 7. Last-task bypass removed

Both terminal branches (operational completion, awaiting-Founder-completion) now call the
Reporter. A mechanical test parses `_submit_objective` and asserts
`_describe_result(state.result` no longer appears in it.

---

## 8. Verification coverage semantics

| situation | what Somesh says |
|---|---|
| all steps verified | *"Work finished. All 3 executed step(s) were independently verified."* |
| 2 of 3 verified | *"Work finished. 2 of 3 steps were independently verified; 1 could not be independently verified."* |
| no Evidence at all | *"Work finished. I don't have independent verification for the executed steps."* |
| failed | *"That didn't finish. {objective}. 1 step(s) did not match what was expected."* |

The words **"checked"** and **"confirmed"** are asserted absent when there is no Evidence —
the old sentence was *"That's done and checked."* with nothing checked at all.

---

## 9. Founder-outcome conformance boundary — the important restraint

Three claims are kept apart: **execution**, **step verification**, **founder-outcome
conformance**. There is Evidence for the second and no generic authority for the third.

So the §18 scenario is tested directly: a Browser step observing `"Example Domain"` and a
Filesystem step whose content independently contains `"Example Domain"`, both MATCHED,
with **no provenance connecting them**. Reporter says both steps were independently
verified. It is asserted never to say *transferred*, *your objective*, *fully verified* or
*semantically*. `Report.metadata["founder_outcome_conformance"] == "not_evaluated"` states
it explicitly so no consumer can read coverage as a claim about the objective.

A lucky equality is not provenance.

---

## 10. Founder Surface wiring

Reporter owns **what happened**; the Surface owns **what the founder is asked to do next**.
So the completion branch appends *"Ready for your review."* to the Reporter's sentence
rather than moving completion controls into the Brain. Clarification, approval-waiting and
reasoning-unavailable messages remain the Surface's, untouched.

**Truthful degradation:** with no Reporter, no PlanHistory or no PlanRecord, the message is
*"The work finished, but I can't reconstruct a verified mission summary."* — never a task
output substituted for a mission summary. The already-wired `mission_service.reporter` and
`mission_service.history` are used; no second Reporter is constructed.

---

## 11. Restart reporting

Because Evidence is durable, the report is reproducible from disk: a `PlanRecord` taken
through `as_dict` → JSON → `from_dict` produces a **byte-identical** report, including the
"1 of 2" coverage. No environment access, no provider, no re-execution.

---

## 12–14. Simple, multi-step, cross-domain

* **Single step** — a folder mission reports *"All 1 executed step(s) were independently
  verified"*, evidence-derived, with no special-case heuristic preserved.
* **Multi-step** — the three-step browser mission's `{"closed": true}` cleanup output is
  asserted absent from the report; `{` and `[object Object]` are asserted absent.
* **Cross-domain** — a record carrying browser, filesystem and desktop Evidence reports all
  three real worker identities. Never rewritten to one domain, which is what the old
  launcher path did.

---

## 15. Mutation proof

| mutation | tests failed |
|---|---|
| A — restore `_describe_result(state.result)` as the terminal message | 1 (`test_the_terminal_branches_no_longer_describe_the_task_result`) |
| B — rebuild Evidence from `evidence_id` + verdict | 2, incl. `test_a_step_with_only_an_id_and_verdict_counts_as_unverified` |
| C — claim *"Your objective was fully verified"* | 2 (`fully verified`, `your objective`) |

All restored; 24/24 pass.

---

## 16. Regression delta

| | |
|---|---|
| Baseline (`4a57821`) | 8 |
| After | 8 |
| **Introduced** | **0** |

Three failures appeared mid-work in `test_kalpavriksha_desktop_mission_bridge.py` and were
**superseded tests, not a regression**: they asserted the founder reply *was* the task
output (`"42"`, `Done — the page at …`). Updated to assert the new mission-level contract
while keeping the property they actually protected — no raw dict or repr reaching the
founder — and the formatting helper is now exercised directly instead of through a path
that no longer uses it.

Per §27, the file list was verified to exist before the run was treated as a baseline.

---

## 17. Wiring truth after repair

| | |
|---|---|
| Verification → Evidence | **WIRED** |
| Evidence → Mission State / History | **WIRED** |
| Evidence → durable Persistence | **WIRED** |
| Evidence → Reporter | **WIRED** |
| Reporter → Founder mission result | **WIRED** |
| Fail-closed absent Evidence | **DEFERRED** |
| Cross-step data provenance | **NOT BUILT** |
| Founder-outcome semantic conformance | **NOT BUILT** |

The last two are not wiring gaps. They are unimplemented architecture.

---

## 18–19. Deferred

**Fail-closed** unchanged — and the newly wired Reporter now *exposes* that truth instead
of concealing it: a mission that completes with no Evidence says so to the founder. That
makes the fail-closed decision safe to take next, with the founder still receiving a
truthful explanation either way.

**Cross-step provenance** untouched. It genuinely does not exist, and §9 of this brief
matters here: Reporter does not guess the important artifact from the last filesystem step.
It reports only what the record and Evidence justify.

---

## Verdicts

| | |
|---|---|
| EXISTING REPORTER PRESERVED | **YES** |
| LEGACY MISSION MANAGER MADE PRODUCTION AUTHORITY | **NO** |
| NEW MISSION STATE TYPE CREATED | **NO** |
| PLANRECORD USED AS AUTHORITATIVE REPORTING RECORD | **YES** |
| CANONICAL EVIDENCE USED DIRECTLY | **YES** |
| EVIDENCE FABRICATED FROM ID | **NO** |
| LAST TASK OUTPUT USED AS MISSION SUMMARY | **NO** |
| REPORTER WIRED TO FOUNDER MISSION RESULT | **YES** |
| UNVERIFIED STEPS REPORTED TRUTHFULLY | **YES** |
| STEP VERIFICATION ≠ FOUNDER CONFORMANCE PRESERVED | **YES** |
| RESTART REPORTING | **READY** |
| GLOBAL FAIL-CLOSED ENABLED | **NO** |
| CROSS-STEP DATA FLOW IMPLEMENTED | **NO** |
| INTRODUCED TEST FAILURES | **0** |

---

## The question

> *Can Somesh now explain a completed or failed mission from authoritative Mission history
> plus the exact Evidence Verification produced, without using the last Task output or
> fabricating missing facts?*

**Yes.** The account comes from the `PlanRecord` and the Evidence on its steps. Where
Evidence is absent, that absence is what the founder is told — including the case where
nothing at all was verified, which the old sentence called *"done and checked"*.

What he still cannot say, and is mechanically prevented from saying, is that the objective
itself was fulfilled. Steps matching is not the same claim, and the bridge that would make
it one does not exist yet.
