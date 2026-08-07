# Mission Brief 038 — Delivered

**Status:** Stage A complete. Stage B ADR-gated and unstarted.
**Date:** 2026-07-31
**Suite:** 3206 → **3457 passing**, 1 skipped, zero regressions.
**Frozen files modified:** none. **ADRs created:** none.
**Architecture of record:** `docs/MISSION_BRIEF_038.md`
**Plan of record:** `docs/MISSION_BRIEF_038_IMPLEMENTATION.md`

---

## 1. Architecture delivered

Kalpavriksha applied **one** timeout to every provider call —
`OllamaProvider.self._timeout`, 120 s by default, used identically for a
`/api/tags` health probe and a twenty-six-capability planning prompt.
`Task` and `Objective` had no deadline concept at all. MB036 and MB037
both reported a **healthy** `gemma4:latest` as failed because of it.

Three changes of kind, not degree:

**One deadline became three.** TTFT bounds prefill and is the only one
that scales with input size. ITL bounds decode cadence and is a property
of the model and the hardware, independent of prompt size. Total bounds
the whole call. They scale with different variables, so no single
variable can represent them — collapsing them was a category error, not a
tuning mistake.

**A duration became an absolute instant.** Deadlines propagate as points
on a monotonic clock. A relative duration is re-based at every hop, so
five layers each honouring "60 seconds left" honour five 60-second
windows — invisible in a one-hop test, compounding under load.

**A constant became a derived, recorded value.** The Broker computes a
budget from the workload class, the prompt size and the provider's
measured throughput, records it *before the call*, and the record is what
replay reads.

### The layering, as built

```
transport.py   mechanism     yields bytes, knows no budget
stream.py      measurement   times them, cannot fail a call
deadline.py    policy        compares the two, decides
budgets.py     derivation    turns facts about work into milliseconds
admission.py   admission     decides whether to call at all
occupancy.py   bookkeeping   counts who is busy; decides nothing
```

Each layer is structurally incapable of the next one's job. `StreamMonitor`
imports no budget and has no way to fail a call, so a stored observation
can be re-examined later against a different policy — which is what makes
the coefficients correctable rather than baked in.

### Ownership

| Layer | Owns | Stage |
|---|---|---|
| Mission Control | the mission SLA, and nothing else about time | B |
| Runtime | task-boundary enforcement; task retry (MB024, untouched) | B |
| Dispatcher | **nothing** time-related | — |
| Broker | budget derivation — the single place facts become milliseconds | **A** |
| Provider adapter | enforcement of the budget it was handed | **A** |
| Transport | the socket deadline. Mechanism only | **A** |

---

## 2. Files introduced

Eight source modules, **367 statements, 100 % statement coverage**.

| Module | Responsibility |
|---|---|
| `ai_infrastructure/workload.py` | Six-class closed vocabulary; `(floor, ceiling)` envelopes per deadline |
| `ai_infrastructure/budgets.py` | `derive()` and `size_of()` — deterministic, reads no clock |
| `ai_infrastructure/budgeted_request.py` | `BudgetedSelectionRequest`, subclassing the frozen request |
| `ai_infrastructure/admission.py` | `admit()` — starved / occupied / admitted |
| `ai_infrastructure/occupancy.py` | In-flight and abandoned counts per provider |
| `providers/budget.py` | `CallBudget`, `Derivation`, binding-constraint vocabulary |
| `providers/stream.py` | `StreamMonitor`, `StreamObservation` — measurement only |
| `providers/deadline.py` | `check()`, `read_timeout_seconds()`, `supervise()`, `Cancellation` |

Eleven test modules, **240 tests**:
`test_timeout_workload`, `_budget`, `_profiles`, `_derivation`,
`_selection`, `_stream`, `_enforcement`, `_adapter`, `_admission`,
`_lifecycle`, `_reporting`.

Modified without breaking their contracts: `broker/profiles.py`,
`ai_infrastructure/{catalog,profiles,service,execution,ledger}.py`,
`providers/{ollama,transport,response}.py`, `planner/planner.py`,
`config.py`, `launcher/boot.py`, four `dashboard/` modules.

---

## 3. Public interfaces added

**Budget**
- `CallBudget(total_deadline, ttft_deadline, itl_ms, enforce_itl, total_ms, ttft_ms, derivation)`
  with `total_expired()`, `ttft_expired()`, `stalled()`, `*_remaining_ms()`
- `Derivation` — class, token estimates, provider, rates, and which
  constraint bound each deadline
- `FROM_ESTIMATE | FROM_FLOOR | FROM_CEILING | FROM_MISSION | FROM_OVERRIDE`

**Workload**
- `PLANNING | EXECUTION | CODE_GENERATION | INTERACTIVE | EMBEDDING | VERIFICATION`
- `profile_for(request_class) -> ClassProfile`; `Bounds.clamp()`

**Derivation**
- `derive(profile, workload, prompt_tokens, completion_tokens, now, mission_deadline, override_total_ms)`
- `size_of(text, profile) -> int | None`

**Provider profile** — `prefill_tokens_per_second`, `decode_tokens_per_second`,
`expected_itl_ms`, `chars_per_token`, `supports_streaming`, `serialises`,
plus `throughput_known` and `can_size_a_prompt`. All round-trip through
`as_dict`/`from_dict`.

**Measurement** — `StreamMonitor.token() / complete() / observe() / silence_ms()`;
`StreamObservation` with `ttft_ms`, `max_gap_ms`, `observed_itl_ms`, `decode_ms`.

**Policy** — `check()`, `read_timeout_seconds()`, `supervise()`,
`TimeoutEvent`, `DeadlineExceeded`, `Cancellation`.

**Admission** — `admit()`, `Admission`, `ADMITTED | STARVED | OCCUPIED`.

**Occupancy** — `begin() / end() / abandon() / release_abandoned() / in_flight() / abandoned() / busy()`.

**Outcomes** — `TIMED_OUT_TTFT`, `TIMED_OUT_ITL`, `TIMED_OUT_TOTAL`,
`CANCELLED`, `NOT_ADMITTED`.

**Evidence** — `ExecutionRecord.budget/observation/timeout/admission/admission_reason/lifecycle`;
`LIFECYCLES = (completed, failed, abandoned, refused)`;
`DecisionLedger.replay_execution() -> ExecutionReplay`.

**Call sites** — `PromptExecutor.run(..., cancellation=)`,
`PromptExecutor(occupancy=, monotonic=)`,
`OllamaProvider.complete(..., budget=, cancellation=)`,
`Transport.stream_json()`.

---

## 4. Invariants guaranteed

Each is asserted by test, not by convention.

1. **Unknown stays unknown.** An unmeasured rate is `None` and never
   becomes a number. Derivation falls back to the class ceiling and marks
   it `FROM_CEILING` — never `FROM_ESTIMATE`.
2. **A fallback is never labelled an estimate.** Caught as a real defect
   during Step 4: the ceiling was being routed through the clamp and
   returned marked as derived.
3. **Absence is not zero.** A pre-MB038 record and an unbudgeted call
   both read back with `budget=None`; the founder page renders no budget
   line rather than `0s total`.
4. **Derivation is deterministic.** Same inputs → byte-identical budget,
   across processes. `derive()` reads no clock; `now` is an argument.
5. **The three deadlines stay distinct.** `ttft_deadline > total_deadline`
   is rejected at construction, because it would make `TIMED_OUT_TOTAL`
   unreachable.
6. **Ordering is most-specific-first.** Cancellation outranks every
   deadline; a stall outranks an expired total; occupancy outranks
   starvation. Each has a test and a stated reason.
7. **No retry below the Runtime.** `providers/` contains no retry, no
   sleep, and no retry configuration — asserted by signature check and
   AST walk.
8. **A retry never extends a deadline**, and a timeout is never retried
   under the same budget.
9. **Abandoned ≠ completed.** A cancelled call does not release the
   provider; the daemon may still be working.
10. **No timers, no guessed windows.** Nothing self-cancels;
    `release_abandoned()` is explicit. Elapsed time never implies that
    orphaned work finished.
11. **Replay recomputes nothing** and contacts no provider.
12. **Reporting transcribes.** Every MB038 field on a dashboard row
    appears verbatim in the record it came from.
13. **No frozen file touched.** `git diff` over `mission_control/`,
    `runtime/`, `persistence/`, `verification/`, `executor/` is empty;
    `RATIFIED_EXCEPTIONS` unchanged at 7.

---

## 5. Known limitations

**The unbudgeted path still exists.** `complete(budget=None)` remains
reachable — used by `--ask` and the health probe. Removing it needs those
callers to supply prompts and classes; synthesising a budget for a
prompt-less request would size an empty string, clamp to the 10 s
execution floor, and make a real 22.8 s call fail. That would be a
regression introduced by tidying.

**Coefficients are one laptop, one checkpoint, one afternoon.**
`ollama.local` carries 20 prefill tok/s, 12 decode tok/s, 90 ms ITL,
4.0 chars/token — measured on `gemma4:latest`, rounded in the safe
direction. Every other provider is unmeasured and falls back to ceilings.

**`serialises` is declared, not measured.** Whether Ollama halts
generation on client disconnect was **not** established — the Step 0
disconnect test was invalid (it compared a 40-word follow-up against a
400-word baseline). Occupancy accounting is required either way, which is
why this does not block.

**Occupancy protects nothing today.** The system issues one provider call
at a time, so the admission check never fires in practice. It is
protection for when concurrency arrives, and an orphan currently blocks
until `release_abandoned()` is called explicitly.

**No mission SLA.** Nothing supplies `mission_deadline`, so the class
envelope is the only ceiling and `FROM_MISSION` is currently unreachable
in production.

**Four of six workload classes have no producer.** Only `planning` and
`execution` are emitted. `verification` has none *by decision* — MB035's
verifier is deterministic and never calls a model.

**Host state is not recorded.** The architecture permits it as an
observation; Stage A did not implement it.

---

## 6. Stage B prerequisites

| # | Prerequisite | Why it blocks |
|---|---|---|
| 1 | **ADR-0021** — `Objective` SLA, `Task` deadline | Frozen `mission_control/tasks.py`. Without it no mission ceiling exists and `FROM_MISSION` stays theoretical |
| 2 | **ADR-0022** — Runtime enforcement at the task boundary | Frozen `runtime/engine.py`. Deadlines currently bind per call, not per task |
| 3 | **ADR-0023** — mission cancellation verb | Frozen `mission_control/` + `dispatcher.py`. **The mechanism is already built** — only the verb is missing |
| 4 | Measure the disconnect behaviour | Determines whether transport cancellation can be trusted per provider |
| 5 | Decide the mission-SLA default | A ceiling nobody sets is a ceiling that never binds |

**ADR-0023 should absorb MB037's pause/resume gap.** They are one
lifecycle amendment, and splitting them creates two decisions that must
then be kept consistent.

---

## 7. Recommended follow-up work

Ordered by value.

1. **Run MB038 live.** Everything is unit- and integration-proven; the
   original failure (a 26-capability planning prompt against the real
   daemon) has not been re-run under the new budgets. This is the cheapest
   remaining confidence.
2. **Capability input schemas** — *still the highest-value item in the
   backlog, and not a timeout problem.* MB037's first live plan named the
   right two capabilities and got **both payloads wrong**;
   `CapabilityManifest.input_schema` is declared and populated by nothing.
3. **Measure a second provider.** One measured provider proves the shape;
   two prove the abstraction.
4. **Correct the estimates against observation.** Every call now records
   derived-versus-observed TTFT and ITL. Nothing reads it yet — this is
   the loop that makes the coefficients self-correcting.
5. **Feed timeouts to the benchmark store** (ADR-0017 D5, ADR-0018).
   A provider that repeatedly misses a well-derived budget is slower than
   it declares.
6. **Retire the unbudgeted path** by giving `--ask` and the health probe
   classes and prompts.
7. **Budget × cost ceiling.** A generous budget on a paid provider is a
   generous spend; ADR-0017 §9's ledger and these budgets are not
   connected.
8. **Independent architecture audit.** Planner, Broker, Verifier, Memory,
   Mission Control, provider layer and now the execution-economics layer
   are all in place — the milestone the founder already identified as the
   right point for third-party review.

---

## 8. Defects found by building it

| # | Defect | Found by | Status |
|---|---|---|---|
| 1 | Ceiling fallback labelled `FROM_ESTIMATE` | Step 4 tests | Fixed |
| 2 | Rates without a tokenizer silently half-derived | Step 5 | Fixed — both now required |
| 3 | Abandoning occupancy on any exception would wedge a provider on our own bug | Step 9 test surviving into Step 11 | Fixed — only cancellation abandons |
| 4 | `ollama.py` docstring still described the deleted retry | Review | Fixed |
| 5 | Four test files corrupted by a PowerShell UTF-8 round-trip | Full suite | Repaired; bulk edits now go through Python |
| 6 | Removing `max_attempts` broke 192 tests via `**kwargs` | Full suite | Fixed — predicted as R-3, found by running rather than reading |
