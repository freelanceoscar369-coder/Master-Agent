# Mission Brief 038 — Adaptive Provider Deadlines (Implementation)

**Status:** Implementation brief. Architecture is finalized; this document
does not revisit it.
**Date:** 2026-07-31
**Architecture of record:** the finalized MB038 timeout architecture.
**Depends on:** ADR-0002, ADR-0011, ADR-0016, ADR-0017, ADR-0018, MB033,
MB035, MB036, MB037.

---

## 1. Executive summary

Kalpavriksha applies **one** timeout to every provider call.
`OllamaProvider` holds a single `self._timeout` from
`OllamaConfig.timeout_seconds` and uses it for `/api/tags` health probes
and `/api/generate` planning prompts alike. `Task` and `Objective` carry
no deadline concept at all.

The consequence reached production twice. MB036 and MB037 both reported a
**healthy** `gemma4:latest` as failed, because a large planning prompt
legitimately needs a long prefill window and the system had no way to
tell a provider that is *thinking* from one that is *hung*.

This brief implements the finalized architecture:

- **Mission Control** owns the mission SLA only.
- **Runtime** owns the task deadline.
- **Broker** computes adaptive execution budgets from workload class and
  provider profile.
- **Provider** enforces deadlines and **never retries**.
- **Three deadlines** — Total, TTFT, ITL — replace the single timeout.
- **Deadlines propagate top-down as absolute instants.**
- **Retry belongs to the Runtime**, exclusively.
- **Cancellation propagates through the existing execution context.**
- **Structured timeout evidence** is recorded for every call.

The work splits at the freeze boundary. **Stage A is the entire
provider-call path and requires no frozen edit and no ADR** — it resolves
both observed production failures. **Stage B** puts the deadline on the
Task and enforces it in the Runtime, and requires ADR-0021 and ADR-0022.

Stage A is the deliverable that matters. Stage B should not be started
until its ADRs are ratified.

---

## 2. Scope

### 2.1 In scope

| # | Item | Stage |
|---|---|---|
| 1 | Workload classification on the Broker request | A |
| 2 | `CallBudget` value object — Total, TTFT, ITL, plus derivation | A |
| 3 | Adaptive budget derivation in the Broker | A |
| 4 | Provider profile latency fields and `supports_streaming` | A |
| 5 | Streaming transport and progress observation | A |
| 6 | Three-deadline enforcement in the provider adapter | A |
| 7 | **Removal of provider-side retry** | A |
| 8 | Four distinct timeout outcomes | A |
| 9 | Structured timeout evidence on the execution record | A |
| 10 | Configuration precedence — bounds, not scalars | A |
| 11 | Admission refusal when the remaining budget is below the class floor | A |
| 12 | Cancellation via the execution context | A |
| 13 | Replay reuse of recorded budgets | A |
| 14 | Dashboard rendering of budgets and timeout causes | A |
| 15 | `Objective` SLA and `Task` deadline | B — ADR-0021 |
| 16 | Runtime enforcement at the task boundary | B — ADR-0022 |

### 2.2 Freeze posture

Stage A touches **no frozen package**. `mission_control/`, `runtime/`,
`persistence/`, `verification/`, `plugins/` and `executor/` are unchanged,
and `RATIFIED_EXCEPTIONS` gains no row. The frozen-file guard must stay
green throughout Stage A without amendment — that is an acceptance
criterion, not an aspiration.

---

## 3. Architecture as implemented

### 3.1 Ownership, as built

```
Mission Control   mission SLA (absolute)                    Stage B
       ↓
Runtime           T_task = min(T_mission, now + ceiling)    Stage B
       ↓          task-level retry (MB024, unchanged)
Broker            CallBudget{total, ttft, itl} + derivation Stage A
       ↓
Provider Adapter  enforces all three. Never retries.        Stage A
       ↓
Transport         socket deadline                           Stage A
```

### 3.2 The three deadlines

| Deadline | Bounds | Derived from |
|---|---|---|
| **TTFT** | prefill | workload class + prompt size + `profile.prefill_rate` |
| **ITL** | decode cadence | `profile.expected_itl` — independent of prompt size |
| **Total** | whole call | class + prefill estimate + expected output + `profile.decode_rate` |

All three clamp to the remaining task deadline in Stage B; to the class
ceiling in Stage A.

### 3.3 Extending the Broker request without touching a frozen file

`SelectionRequest` lives in `plugins/model_router.py`, which is frozen
and whose `RATIFIED_EXCEPTIONS` row names ADR-0017 — a different purpose.

**Approach: subclass, do not modify.** Define in `ai_infrastructure/`:

```
BudgetedSelectionRequest(SelectionRequest)
    request_class: str = EXECUTION
    deadline: float | None = None        # absolute, monotonic
```

`AiCapabilityService.decide()` already accepts `request: Any`, every
`isinstance` check against `SelectionRequest` still passes, and
`SelectionRequest.from_context()` is untouched. This follows MB035's
precedent exactly: `TextVerifier` lives outside frozen `verification/`
and implements the published contract rather than editing it.

**No ADR is required for Stage A because of this choice.** Adding the
fields directly to `SelectionRequest` would need one.

### 3.4 Cancellation through the existing execution context

Cancellation is **a deadline set to now**, carried by the `CallBudget`
already flowing down §3.1. No new mechanism, no new channel, no thread
interruption.

A call that cannot be interrupted mid-flight is **abandoned**: the caller
stops waiting, the result is discarded, and the abandonment is recorded
as an outcome distinct from a timeout — including whether the provider is
believed still occupied.

---

## 4. Components affected

### 4.1 New modules

| Module | Contents |
|---|---|
| `providers/budget.py` | `CallBudget` — pure dataclass, no I/O. Placed in `providers/` so both the adapter and the wiring layer import it without a cycle, matching MB033's pure-dataclass precedent. |
| `ai_infrastructure/workload.py` | Closed workload-class vocabulary and per-class bounds. |
| `ai_infrastructure/budgets.py` | Deterministic budget derivation. |

### 4.2 Modified — none frozen

| Module | Change |
|---|---|
| `providers/transport.py` | Streaming method alongside `post_json`; per-call deadline instead of a stored timeout. |
| `providers/ollama.py` | Consume `CallBudget`; enforce three deadlines; **delete `max_attempts` and all retry**; emit four outcomes; report observed TTFT and ITL. |
| `providers/response.py` | `TIMED_OUT_PREFILL`, `STALLED_DECODE`, `TIMED_OUT_TOTAL`, `ABANDONED`. Existing `TIMED_OUT` retained only if a migration path needs it. |
| `ai_infrastructure/service.py` | Attach the derived `CallBudget` to the `Selection`. |
| `ai_infrastructure/execution.py` | Pass the budget through unchanged; record timeout evidence. |
| `ai_infrastructure/ledger.py` | Timeout fields on `ExecutionRecord`. |
| `ai_infrastructure/catalog.py`, `profiles.py` | `prefill_rate`, `decode_rate`, `expected_itl`, `supports_streaming`. |
| `config.py` | Per-class bounds; `OllamaConfig.timeout_seconds` demoted to a provider ceiling. |
| `planner/planner.py` | Emit `request_class="planning"`. Sets no timeout. |
| `dashboard/readmodel.py`, `sources.py`, `founder.py`, `founder_panels.py` | Render budget, cause, and observed-versus-derived. |
| `launcher/boot.py` | Wire derivation; report class bounds in the boot report. |

### 4.3 Explicitly unchanged

`mission_control/`, `runtime/`, `persistence/`, `verification/`,
`plugins/`, `executor/`. Stage A must not produce a diff in any of them.

---

## 5. Sequence of implementation

Ordered so each step is independently testable and nothing is built on an
unmeasured assumption.

**Step 0 — Measurement spike.** Measure `gemma4:latest` prefill rate,
decode rate and inter-token latency on the founder's hardware, and
determine whether Ollama halts generation on client disconnect. Produces
numbers and a short findings note. **No production code.** Every
coefficient below depends on this; guessing them reproduces the current
defect with more machinery.

**Step 1 — Workload vocabulary.** `ai_infrastructure/workload.py`, closed
set, per-class bounds as `(floor, ceiling)` triples for Total, TTFT, ITL.
Pure data. A test asserts producer-less classes are never emitted.

**Step 2 — `CallBudget`.** `providers/budget.py`. Absolute instants on a
monotonic clock. Carries its derivation and which constraint bound it.
Pure dataclass, frozen, no I/O.

**Step 3 — Provider profile fields.** `prefill_rate`, `decode_rate`,
`expected_itl`, `supports_streaming` on `ProviderSpec`/`ProviderProfile`,
populated from Step 0. Declared values, labelled as declared.

**Step 4 — Budget derivation.** `ai_infrastructure/budgets.py`.
Deterministic: identical inputs yield an identical budget. Records the
derivation and the binding constraint. No clock reads inside the
computation beyond the single `now` passed in.

**Step 5 — `BudgetedSelectionRequest`** and Broker attachment. The
`Selection` now carries a `CallBudget`. Recorded on the `DecisionRecord`
**before the call is made**.

**Step 6 — Streaming transport.** A streaming method on the transport
protocol. The scripted `FakeTransport` in `tests/broker_test_support.py`
gains a scripted-stream mode so every deadline path is testable without a
daemon.

**Step 7 — Three-deadline enforcement** in `OllamaProvider`, with the
four outcomes. The heartbeat monitor consumes **token count and
timestamp only** — never token text.

**Step 8 — Delete provider retry.** Remove `max_attempts`,
`retry_delay_seconds` and the retry loop. Transport faults now surface
immediately as `UNAVAILABLE`; the Runtime's mechanical retry is the only
retry in the system.

**Step 9 — Admission refusal.** Refuse before calling when the remaining
budget is below the class floor. Refusal carries the binding constraint.

**Step 10 — Evidence.** Timeout fields on `ExecutionRecord`: budget
granted, derivation, binding constraint, observed TTFT, observed ITL,
outcome, orphan state, clock basis.

**Step 11 — Cancellation and orphan accounting.** Deadline-set-to-now
through the existing context; abandonment recorded; per-provider
occupancy tracked so a serialising local provider is never selected on
the false premise that it is idle.

**Step 12 — Replay.** Assert budgets are reused, never recomputed. Mostly
a constraint plus a test that fails if recomputation is introduced.

**Step 13 — Dashboard.** A timeout renders as *budget exceeded, derived
thus*, never as a bare failure. Never renders token text.

**Step 14 — Wiring and boot report.** `launcher/boot.py` constructs the
derivation and reports the active class bounds.

**Stage B — Steps 15–16.** Only after ADR-0021 and ADR-0022 are ratified.

---

## 6. Tests

Target **250+ new tests**, following the MB033–MB037 pattern: one module
per concern, 100% statement coverage of new modules, and architecture
tests that parse rather than trust.

| Module | Covers |
|---|---|
| `test_timeout_workload.py` | Class vocabulary, bounds, producer-less classes never emitted |
| `test_timeout_budget.py` | `CallBudget` shape; absolute-instant invariants; clamping |
| `test_timeout_derivation.py` | Determinism; class/size/profile inputs; binding constraint recorded; identical inputs → identical budget |
| `test_provider_deadlines.py` | TTFT expiry, ITL stall, Total expiry, completion — each producing its own distinct outcome |
| `test_provider_no_retry.py` | **A provider never retries anything**, asserted by AST over `providers/` and by a transport that would record a second attempt |
| `test_timeout_admission.py` | Refusal below class floor; no call issued; binding constraint reported |
| `test_timeout_cancellation.py` | Deadline-set-to-now; abandonment recorded; occupancy tracked; no thread interruption |
| `test_timeout_evidence.py` | Every §4 field present; observed vs derived distinguishable; budget recorded before the call |
| `test_timeout_replay.py` | Recorded budgets reused; recomputation absent; no provider contacted |
| `test_timeout_dashboard.py` | Budget and cause rendered; **no token text ever rendered** |
| `test_timeout_architecture.py` | Frozen guard green; no new `RATIFIED_EXCEPTIONS` row; no vendor names; adapter holds no default timeout |

### 6.1 Tests that must fail before they pass

Three regressions from production, written first:

1. A 26-capability planning prompt under a 120 s global timeout **must
   not** be reported as a provider failure.
2. A dead daemon **must still** fail in about a second — the fast failure
   MB033 built must survive the change.
3. A provider that emits tokens and then stops **must** fail at ITL, not
   at Total.

### 6.2 Determinism

A test asserting the same inputs produce a byte-identical budget across
two processes. This is what protects MB032's replay guarantee.

---

## 7. Risks

**R-1 — Ollama serialises per model.** An abandoned call keeps the model
busy; the next call queues behind it with a budget derived assuming an
idle provider, so it times out too, orphaning again. Self-sustaining.
Mitigated by Step 11's occupancy tracking, and by Step 0 measuring the
real behaviour before any coefficient is fixed. **Highest severity.**

**R-2 — Coefficients from Step 0 are hardware-specific.** They are
correct for the founder's laptop and nowhere else. Ship generous ceilings
and tighten on recorded evidence; never hardcode a rate as a constant
without labelling it declared.

**R-3 — Removing provider retry changes failure timing.** Transport
faults that previously recovered silently on the second attempt now
surface immediately. This is the intended architecture, but it will look
like a regression in any test that depended on the retry. Audit
`test_ollama_provider.py` and `test_provider_execution.py` at Step 8
rather than at the end.

**R-4 — Class floors become a dumping ground.** Without the binding
constraint in evidence, every timeout gets "fixed" by raising the
planning floor. Step 10 is what prevents this, which is why it is not
optional and not last.

**R-5 — `providers/` grows.** MB033 kept it deliberately small and
re-exporting nothing. Keep the heartbeat monitor out of the transport,
and keep `budget.py` a pure dataclass module.

**R-6 — Streaming could leak reasoning.** The monitor must consume count
and timestamp only. Enforced by `test_timeout_dashboard.py` and by giving
the view model nowhere to put token text.

---

## 7a. ADR notes — as built (Step 14)

**No ADR was required, and none was created.** Stage A shipped complete
with `RATIFIED_EXCEPTIONS` unchanged at 7 rows and an empty `git diff`
over every frozen package.

The one place an ADR looked unavoidable was extending the Broker's
request vocabulary. `SelectionRequest` lives in frozen
`plugins/model_router.py`, whose exception row names ADR-0017 — a
different purpose, so reusing it would have been drift.
`BudgetedSelectionRequest` **subclasses** it instead: every
`isinstance` check still passes, `from_context()` is untouched, and
`AiCapabilityService.decide()` already accepted `Any`. MB035 set the
precedent when `TextVerifier` implemented the frozen `Verifier` contract
from outside `verification/`.

Three ADRs remain **recommended and unratified**, all for Stage B:

| ADR | Subject | Frozen files |
|---|---|---|
| ADR-0021 | `Objective` mission SLA; `Task` deadline | `mission_control/tasks.py` |
| ADR-0022 | Runtime enforcement at the task boundary | `runtime/engine.py` |
| ADR-0023 | Founder-initiated mission cancellation | `mission_control/`, `dispatcher.py` |

Stage A already built the *mechanism* ADR-0023 would expose:
`Cancellation` propagates through the execution context and is honoured
at the same gate as a deadline. What is missing is only the Mission
Control verb that lets a founder trigger it — which is the same
amendment MB037's pause/resume gap needs, and should be one decision.

## 8. ADR impact

| ADR | Required for | Status |
|---|---|---|
| **None** | **All of Stage A** | Subclassing `SelectionRequest` (§3.3) avoids the only frozen edit Stage A would otherwise need |
| **ADR-0021** | `Objective` mission SLA; `Task` deadline | Recommended, unratified. Frozen: `mission_control/tasks.py` |
| **ADR-0022** | Runtime enforcement at the task boundary | Recommended, unratified. Frozen: `runtime/engine.py` |
| **ADR-0023** | Founder-initiated mission cancellation | Recommended, unratified. Should absorb MB037's pause/resume gap — one lifecycle amendment, not two |

Stage A adds **no row** to `RATIFIED_EXCEPTIONS`. Stage B must not begin
before ADR-0021 and ADR-0022 are ratified.

---

## 9. Acceptance criteria

Stage A is complete when all of the following hold:

1. A planning prompt carrying the full capability catalogue completes
   against the real daemon without a timeout, using a budget derived from
   its workload class and prompt size — not a raised global constant.
2. A dead daemon still fails in about one second.
3. A provider that stops mid-stream fails at ITL, in seconds, under a
   Total budget of ten minutes.
4. Four distinct timeout outcomes are observable and distinguishable in
   the execution record.
5. `grep`-level proof that **no retry exists anywhere in `providers/`**,
   and that the Runtime's mechanical retry is unchanged.
6. Every provider call records: budget granted, its derivation, the
   binding constraint, observed TTFT, observed ITL, outcome, orphan
   state, clock basis.
7. Two identical derivations in two processes produce byte-identical
   budgets.
8. Replay of a recorded mission reuses recorded budgets and contacts no
   provider.
9. The founder page shows a timeout as *budget exceeded, derived thus*,
   and never shows token text.
10. `git diff` over `mission_control/`, `runtime/`, `persistence/`,
    `verification/`, `plugins/` and `executor/` is **empty**, and the
    frozen-file guard passes with no new exception row.
11. 250+ new tests; 100% statement coverage of the three new modules;
    zero regressions against the current 3206-test baseline.
12. Ruff clean across every file the brief touches.

---

## 10. Out of scope

Explicitly excluded. Each is deferred with a reason, not overlooked.

| # | Excluded | Why |
|---|---|---|
| 1 | **`Objective` SLA and `Task` deadline** | Stage B. Frozen; needs ADR-0021. |
| 2 | **Runtime task-deadline enforcement** | Stage B. Frozen; needs ADR-0022. |
| 3 | **Founder-initiated cancellation** | Needs a Mission Control verb; ADR-0023. Stage A implements deadline-driven cancellation only. |
| 4 | **Pause and resume** | Same lifecycle amendment as ADR-0023; MB037's open question. |
| 5 | **Host load as a budget input** | Non-deterministic, therefore non-replayable. Load may be *recorded*; it must never *determine* a deadline. |
| 6 | **Measured provider profiles replacing declared ones** | Needs the benchmark store. Stage A records the data that will feed it; it does not consume it. |
| 7 | **Budget/cost-ledger interaction** | A generous budget on a paid provider is a generous spend. The cost ledger does not exist yet. |
| 8 | **Concurrent provider calls** | The system issues one at a time today. Parallelism makes R-1 sharply worse and needs its own brief. |
| 9 | **Per-model provider profiles** | Still blocked on the benchmark store, as recorded in the roadmap. |
| 10 | **Retry policy changes in the Runtime** | MB024's mechanical retry and escalation are unchanged. This brief removes the *provider's* retry; it does not touch the Runtime's. |
| 11 | **New Mission Control event types** | Timeout facts ride the existing execution record and `TASK_FAILED`, following MB032's deferral of `BROKER_DECISION`. |
| 12 | **Capability input schemas** | The MB036/MB037 payload defect is a separate, higher-priority backlog item. Unrelated to timeouts. |
| 13 | **Streaming to the founder page** | The monitor observes progress; partial output is never displayed and never verified. |
| 14 | **Semantic verification** | Unchanged. ADR-0017 Decision 5 stands. |
