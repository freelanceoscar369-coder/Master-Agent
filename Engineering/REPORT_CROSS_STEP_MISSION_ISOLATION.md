# KALPAVRIKSHA — CROSS-STEP MISSION ISOLATION & LIVE ACCEPTANCE REPORT

**Date:** 2026-08-20 · **Base:** `5eeb6f7` · **Isolation fix:** `3eaae9d` (pushed)

The isolation defect is fixed and proven. **Packaged acceptance is BLOCKED** — Gemini
returns HTTP 429 for planning-sized requests, and my pre-flight was not good enough to
detect that before launching.

---

## 1. Git Truth

`HEAD == origin/main == 5eeb6f7` at start, ahead 0, behind 0. Protected worktree
(5 modified, 111 untracked) untouched. No reset, no clean.

---

## 2–6. The defect and the correction

`_dependency_tasks()` searched **every** Objective for a matching `task_id`. So Mission
B's `depends_on: ["step_3"]` could be satisfied by Mission A's `step_3` — and Mission A's
verified browser observation could be written into Mission B's file.

Every check the resolver makes would have passed: completed, has Evidence, verdict
`matched`, result agrees with observation. **All true, about the wrong mission.**

The lookup key is now `(objective_id, task_id)`, resolved through Mission Control's own
`Objective` rather than a Runtime-side index. No cache, no second map.

### The same family of bug, one layer up

`_objective_of()` returned the first Objective containing a matching `task_id` — a coin
toss when two missions share step ids. It matches by **identity** now. `_handle_task()`
establishes ownership **once** and uses that single answer for binding sources, approval,
`task_started`, verification, failure and completion, so no two call sites can disagree.

A task whose owning mission cannot be established fails **before** approval or invocation
rather than scanning hopefully for something with the right id.

---

## 7–8. Two-mission collision test

Two live Objectives, both containing `step_3`, in one Mission Control. Mission B's
`step_5` binds `content` to `step_3.url`.

| | |
|---|---|
| Mission A `step_3` | `https://mission-a.test/`, Evidence `ev-mission-a`, MATCHED |
| Mission B `step_3` | `https://mission-b.test/`, Evidence `ev-mission-b`, MATCHED |
| **Written by Mission B** | **`https://mission-b.test/`** |

Asserted in **both** registration orders. Step ids stay contextual — the fix is scoping,
not forcing the Planner to mint globally unique ids, and a test asserts both missions may
legitimately contain `step_3`.

---

## 9. Provenance

`input_provenance` for Mission B names `ev-mission-b` and asserts `ev-mission-a` is absent.
`objective_id` was **not** added to each provenance record: the `TASK_STARTED` event
already carries it, and a test asserts the event's `objective_id` is the consumer's. Scope
is unambiguous by containment, so the schema stays smaller.

---

## 10. Mutation proof — and a detail that matters

Restoring the global cross-objective scan fails the collision test.

**Only the reversed-registration-order case fails.** With the bug restored, the
forward-order test still passes, because dict iteration happens to land on the right
task. §7's requirement to reverse the order is what makes this test real — the obvious
single-direction test would have been green over a live bug.

---

## 11–12. Preserved

The result ≡ Evidence trust rule is untouched. All isolation tests use the **production
JSON wire form** for `input_bindings`, never pre-parsed `Binding` objects — the shape that
caused the previous round's live failure.

---

## 13. Regression

**0 failures at `5eeb6f7`, 0 after, 0 introduced** — 377 tests across cross-step binding,
runtime, Mission Control, dispatcher, tasks, translation, history, persistence and the
architecture rules. File list verified to exist before the run was treated as a baseline.

---

## 14. Commit ordering

The isolation correction was committed and pushed (`3eaae9d`) **before** any live run, as
required. Validated code is not sitting unpushed.

---

## 15. Pre-flight — my design was inadequate, and it cost something

Before launching, I probed `gemini.api`:

```
reachable : True | configured
call      : OK -> ok
```

I treated that as a pass and launched. The planning call then failed, the ladder fell
through **every** tier — `chatgpt-desktop`, `perplexity-desktop`, `kimi-desktop`,
`no_provider_available`, `browser.free-ai` — and launched **23 desktop application
processes** on the founder's machine.

Re-probed afterwards with a planning-sized prompt (4,072 characters):

```
HTTP 429: You exceeded your current quota...
```

**A one-word probe is not representative of a planning request.** The free tier answers a
trivial call and refuses a real one, so my probe measured the wrong thing and gave false
confidence. The §15 instruction was right; my implementation of it was not.

A correct pre-flight must send a planning-representative prompt. That is itself
quota-consuming, which is the tension §15 tried to avoid by asking for a
"non-side-effecting" probe — but the evidence is that no non-side-effecting probe can
answer this question.

The Broker's fallback policy was **not** modified. It behaved exactly as designed; the
harness simply should not have started.

---

## 16. Process cleanup

23 fallthrough processes stopped, identified by start time within the run window. No
Kalpavriksha, Perplexity, ChatGPT or Kimi processes remain. Earlier in this work a set of
ChatGPT processes started ~6 hours before a run was correctly left alone by the same
time filter.

---

## 17–21. Packaged acceptance — BLOCKED

No plan was produced, so none of the live criteria were obtained: pre-execution plan gate,
live source identity, the value chain, or durable provenance.

---

## 22–23. Untouched

Reporter unchanged; `founder_outcome_conformance` remains `not_evaluated`. Global
fail-closed still deferred.

---

## Cleanup

FMEA state root removed (copy preserved in the session scratchpad), no test folders
remain, `Desktop\Desktop` unchanged at its two pre-existing items, normal Founder profile
MD5-verified unchanged across all four state files.

---

## Verdicts

| | |
|---|---|
| CROSS-STEP CONTRACT PRESERVED | **YES** |
| GLOBAL TASK-ID SOURCE LOOKUP REMOVED | **YES** |
| SOURCE LOOKUP SCOPED TO CONSUMING OBJECTIVE | **YES** |
| TWO MISSIONS MAY BOTH HAVE step_3 | **YES** |
| MISSION B CANNOT CONSUME MISSION A EVIDENCE | **YES** |
| PRODUCTION JSON BINDING SHAPE TESTED | **YES** |
| PROVENANCE IDENTIFIES CORRECT MISSION SOURCE | **YES** |
| MUTATION TO GLOBAL LOOKUP CAUGHT | **YES** — by the reversed-order case |
| GEMINI PREFLIGHT SUCCESS | **NO** — passed a trivial probe, failed the real call |
| PACKAGED MEDIUM RERUN | **BLOCKED** |
| PLANNER PREDICTION REMAINS REMOVED | **NOT RE-OBSERVED** this run (observed previously) |
| OBSERVED TITLE FLOWS TO FILE | **NOT OBTAINED** |
| OBSERVED URL FLOWS TO FILE | **NOT OBTAINED** |
| EXACT OBSERVED URL PRESERVED | **NOT OBTAINED** |
| WRITEFILE DYNAMIC CONTENT VERIFIED | **NOT OBTAINED** |
| DURABLE CROSS-STEP PROVENANCE | **NOT OBTAINED** live; proven deterministically |
| GLOBAL FAIL-CLOSED ENABLED | **NO** |
| SEMANTIC OUTCOME QC IMPLEMENTED | **NO** |
| INTRODUCED TEST FAILURES | **0** |

---

## The question

> *Can a Task now consume verified output only from a dependency in its own Mission, and —
> when the planning provider is available — does the packaged Medium objective prove the
> complete durable value-flow chain?*

**The first half: yes, proven.** A bound value resolves only against a dependency in the
consuming Task's own Objective. Two missions may each contain `step_3`; Mission B reads
Mission B's, in either registration order, and its provenance names Mission B's
`evidence_id`. Restoring the global scan breaks it.

**The second half is unproven, and this run did not get to try.** Gemini's quota refuses
planning-sized requests. The mechanism is complete and deterministically verified end to
end — plan-time refusal, mission-scoped resolution, the result ≡ Evidence rule, one
resolved payload through approval/execution/verification, durable provenance — but no
packaged mission has yet carried an observed value into a file under it.

**Before the next attempt:** pre-flight with a planning-sized prompt, not a one-word one.
Mine was the difference between a clean refusal to start and 23 unwanted desktop
processes.
