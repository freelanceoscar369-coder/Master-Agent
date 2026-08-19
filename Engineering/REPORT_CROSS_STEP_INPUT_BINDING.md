# KALPAVRIKSHA — VERIFIED CROSS-STEP INPUT BINDING REPORT

**Date:** 2026-08-20 · **Base:** `650c72f` == `origin/main`, ahead 0, behind 0

The contract is implemented and deterministically proven. **The packaged Medium rerun
could not complete: the Gemini API returned HTTP 429 (quota exceeded), so no plan was
produced.** That is an environmental blocker, not an implementation result, and it is
reported as such rather than dressed up.

---

## 1–3. Git Truth, boundary, architecture preserved

`HEAD == origin/main == 650c72f`, ahead 0, behind 0. Protected worktree (5 modified,
111 untracked) untouched. No Browser, Filesystem or Desktop execution semantics changed;
the only Action modified is `ObserveBrowserAction`, and only to publish output metadata
it already returned.

The proven boundary: `step_3` observed `https://example.com/`, `step_5` wrote
`https://example.com`. `depends_on` said *when*; nothing said *what flows*.

---

## 4. Binding contract — and a placement correction

`capabilities/input_bindings.py`. Two forms only:

```json
{"from_step": {"step_id": "step_3", "field": "url"}}
{"concat": [{"literal": "Title: "}, {"from_step": {"step_id": "step_3", "field": "title"}}]}
```

No arithmetic, conditionals, loops, expression language or evaluation. `concat` does not
nest. A binding is data the Runtime walks, never code it runs.

**Placement corrected.** §3 suggested `mission_control/`, *provided architecture tests
confirm it*. They did not: `test_the_planner_depends_on_no_frozen_runtime_component`
forbids the Planner importing `mission_control`, and it caught the first placement.
`capabilities/` is the published contract package both layers may import — the same
precedent as the Planner consuming `verification.evidence`.

---

## 5–6. Capability output publication

`Action.output_parameters()`, mirroring `optional_parameters()`, defaulting to `None`.
`ObserveBrowserAction` publishes `url` and `title` — **known, deliberately not closed**,
because `run()` also returns viewport, elements and an optional accessibility tree, and
publishing a field is a promise a plan may depend on. Unknown and empty stay different
facts: `CreateFolder` reports `None`, not `()`.

Planner catalogue now renders:

```
Browser.ObserveBrowser | args: session_id (others may exist) | outputs: url, title
```

Names only. Full field descriptions stay behind the lazy-contract seam; MB039's two-tier
design is preserved because prompt size has already cost real latency once.

---

## 7–8. Planner syntax and plan-time validation

Prompt rule 4a: *"do not guess it, copy it, predict it, or take it from the objective's
wording. You do not know it yet."*

Refused at plan time: literal/binding collision, missing source step, source not in
`depends_on` (never auto-added — `depends_on` stays the single execution-order authority),
unpublished output field, source publishing no outputs, malformed binding. A required
argument is satisfied by a literal **or** a binding.

---

## 9–10. Translation and Mission State

`Step.input_bindings → Task.input_bindings`, copied, nothing resolved. `Task.evidence`
now carries the canonical projection Mission Control already transported — stored, not
recomputed, verdict untouched. No second Evidence store.

---

## 11–14. Runtime resolution, and the eight conditions

Resolved inside `_handle_task`, **before** the approval boundary, so the founder and the
Permission System decide on the values that will actually execute. A value resolves only
when: the source exists; is COMPLETED; is a declared dependency; its result has the field;
it has canonical Evidence; the verdict is `matched`; the observation has the field; **and
the reported and observed values agree.**

The last is the one that matters. If the Action and the independent Observation disagree,
resolution **fails** — it does not pick a winner. That is exactly the original defect's
shape (`https://example.com` vs `https://example.com/`), now a hard error.

The same resolved payload reaches approval, `gateway.invoke` and `gateway.verify`, and the
same one on every retry. `task.payload` is never mutated.

---

## 15–17. Failure, persistence, provenance

Any binding failure fails the Task before approval or invocation — no fallback to a
planner literal, none to the founder's raw words, no provider call. This local
fail-closed rule for **data** is separate from the deferred global one for completion: a
step may still complete without Evidence elsewhere, but a value may not *flow* on that
basis.

`StepRecord` persists `input_bindings` (where a value was meant to come from) and
`input_provenance` (where it actually came from: step, field, evidence_id). Ids and paths
only — the values already live in the source Evidence, so nothing dynamic is duplicated
and privacy exposure is not enlarged. Historical records load with `{}` and `[]`.

---

## 18. Mutation proof

| mutation | tests failed |
|---|---|
| A — trust raw result, skip the Evidence comparison | 1 |
| B — let a literal override a binding target | 2 |
| C — unresolved payload to `gateway.invoke` | 2 |
| D — unresolved payload to Verification | 2 |
| E — drop source provenance | 1 |
| **F — assume `Binding` objects instead of the wire form** | **3** |

Mutation F is not from the brief. It is the defect I shipped, described below.

---

## 19. Regression

**0 failures at `650c72f`, 0 after, 0 introduced** (430 tests across planner, parsing,
capability contracts, translation, mission_control, runtime, persistence, history, gateway
wiring, Reporter, Evidence routing). File list verified to exist before the run was
treated as a baseline.

---

## 20. Packaged run — a defect I introduced, and how it was found

The first packaged rerun died in the Runtime:

```
cycle 5 failed: 'dict' object has no attribute 'ref'
```

`Task.input_bindings` carries **plain JSON** — the wire form that survives translation,
the event bus and a restart. My resolver expected `Binding` objects, and **my tests built
tasks with `bindings_from_dict(...)`, a shape production never sends.** 59 tests green
against code that could not run.

This is precisely the failure mode recorded against others in this codebase — checking
that code exists rather than that a value flows — and I reproduced it. The resolver now
parses the wire form, the tests use plain dicts, and reintroducing the object-only
assumption fails 3 tests including the boundary-agreement ones.

The same run exposed a second gap: `input_bindings` were not persisted to `StepRecord`, so
durable history could not answer "where was this input meant to come from?". Fixed.

### What that aborted run did prove

Before the stall, from the real Planner via `gemini.api`:

```
step_5 Filesystem.WriteFile
  payload: {"location": "Desktop", "path": "KV_MEDIUM_004012/page_info.txt"}
```

**No `content` at all** — no `Example Domain`, no predicted URL. The Planner stopped
predicting the value. Steps 1–4 completed and verified MATCHED.

---

## 21–24. The acceptance rerun — BLOCKED

The second packaged rerun never produced a plan. The broker record shows the ladder:

```
1  gemini.api          selected  -> failed
2  chatgpt-desktop     selected
3  perplexity-desktop  selected
```

Direct probe:

```
HTTP 429: You exceeded your current quota, please check your plan and billing details.
```

Gemini is configured and reachable; its quota is exhausted. The tiered runner behaved
correctly and fell through to DESKTOP-locality providers, which drive real applications —
seven Perplexity processes launched on the founder's machine. The run was stopped and
those processes ended.

**Five ChatGPT processes were left running deliberately: they started at 18:55, roughly
six hours before this run, and are the founder's own.** Cleanup was time-filtered, so they
were never in scope.

So §21–24 — actual browser values, binding provenance, file content, WriteFile Evidence —
**were not obtained**. They require one successful planning call.

---

## 25–26. Reporter and conformance boundary

Untouched. `founder_outcome_conformance` remains `not_evaluated`. Nothing in this mission
claims the founder's objective was semantically verified.

---

## 27. Cleanup

FMEA state roots removed (copies preserved in the session scratchpad), test folders
removed, no Kalpavriksha or fallthrough processes running, `Desktop\Desktop` unchanged at
its two pre-existing items, normal Founder profile MD5-verified unchanged.

---

## Verdicts

| | |
|---|---|
| EXISTING BROWSER EXECUTION PRESERVED | **YES** |
| EXISTING FILESYSTEM EXECUTION PRESERVED | **YES** |
| STEP PAYLOAD REMAINS CAPABILITY PAYLOAD | **YES** |
| FIRST-CLASS INPUT BINDING EXISTS | **YES** |
| SOURCE OUTPUT FIELD PUBLISHED | **YES** — `url`, `title` |
| PLANNER NO LONGER PREDICTS MEDIUM VALUES | **YES** — observed live: `step_5.payload` had no `content` |
| BINDING SOURCE MUST BE DEPENDENCY | **YES** |
| SOURCE RESULT MUST HAVE MATCHED EVIDENCE | **YES** |
| RESULT / EVIDENCE VALUE AGREEMENT REQUIRED | **YES** |
| UNVERIFIED SOURCE CANNOT FLOW | **YES** |
| SAME RESOLVED PAYLOAD REACHES APPROVAL | **YES** |
| SAME RESOLVED PAYLOAD REACHES EXECUTION | **YES** |
| SAME RESOLVED PAYLOAD REACHES VERIFICATION | **YES** |
| ORIGINAL PLAN PAYLOAD MUTATED | **NO** |
| BINDING PROVENANCE DURABLE | **YES** (deterministic; not yet observed on a live mission) |
| MEDIUM FILE TITLE FROM OBSERVED VALUE | **NOT OBTAINED** — no plan produced |
| MEDIUM FILE URL FROM OBSERVED VALUE | **NOT OBTAINED** |
| EXACT OBSERVED URL PRESERVED | **NOT OBTAINED** |
| WRITEFILE DYNAMIC CONTENT VERIFIED | **NOT OBTAINED** |
| GLOBAL FAIL-CLOSED ENABLED | **NO** |
| SEMANTIC OUTCOME QC IMPLEMENTED | **NO** |
| INTRODUCED TEST FAILURES | **0** |
| MEDIUM CROSS-STEP DATA FLOW | **NOT PROVEN LIVE** — deterministically proven, packaged acceptance blocked by provider quota |

---

## The question

> *Can Kalpavriksha now prove, from durable provenance rather than equality or model
> prediction, that the values written by a dependent Step came from the verified output of
> the Step it depended on?*

**The mechanism exists and is proven deterministically; it has not yet been proven on a
live mission.**

What is built: a binding names its source step and field; resolution requires the source's
canonical Evidence to corroborate the reported value, and refuses when they disagree; the
resolved payload is what gets approved, executed and verified; and `input_provenance`
records which step, which field and which `evidence_id` supplied each input, durably.

So the answer will be from provenance rather than equality — no coincidence of values can
satisfy it, because the chain is recorded rather than inferred.

What is missing is one successful planning call. Gemini's quota is exhausted, and the
fallback tiers drive desktop applications rather than an API. **Re-run the packaged Medium
objective once quota resets** to obtain §21–24.
