# Mission Brief 038A — Acceptance Patch

**Status:** Complete. **MB038 is now ACCEPTED.**
**Date:** 2026-07-31
**Scope:** the three acceptance findings, and nothing else.
**Suite:** 3457 → **3477 passing**, 1 skipped, zero regressions.
**Frozen files modified:** none. **ADRs created:** none.

---

## 1. The result

The workload that failed in MB036 (120 s), MB037 (540 s) and MB038
acceptance (161.85 s) now completes.

```
objective : Create a folder called employee_api and write a README.md
            inside it describing a REST API for employee management.
provider  : ollama.local (gemma4:latest), cold start, model unloaded first

planned   : True          verdict   : matched
outcome   : succeeded     admission : admitted     lifecycle : completed
timeout   : absent
```

| | Budget granted | Observed | Used |
|---|---|---|---|
| **TTFT** | 358.7 s | **168.1 s** | 47% |
| **Total** | 658.7 s | **325.6 s** | 49% |
| **ITL** | 5 000 ms | **363 ms** max gap | 7% |

641 tokens generated, mean inter-token 246 ms, `bound_by: estimate` — the
budget came from measured throughput, not from a ceiling.

The plan itself: two steps, the right two capabilities out of twenty-six,
the dependency in the right direction, an expectation on each, and the
document verified `matched`.

---

## 2. The three fixes

### Finding 1 — the decode window was zero

`ClassProfile.typical_output_tokens`, used **only when the caller states
nothing**. Planning is 1 200, measured (two real calls produced 834 and
1 115 tokens for the same objective).

**Placed on the class, not on the Planner.** The user reported this as a
Planner wiring bug, and it is — but fixing it at the call site would have
fixed one caller and left `--ask` and every future caller with the same
zero. Output size is a property of the *kind of work*: a plan is a plan.
The Planner still states only facts about the work, which is the rule
MB032 established for routing requests.

`derive()` records the **effective** figure, so evidence says what was
budgeted for rather than what the caller happened to omit.

### Finding 2 — the rates were optimistic

Re-measured in the planning regime — ~1 100 tokens in, unbounded
completion — rather than Step 0's 24-token completions on short prompts.

| | Step 0 | MB038A | Basis |
|---|---|---|---|
| prefill | 20 tok/s | **10** | (136.9 − 33.4) s ÷ 1 095 tok = 10.6, rounded down |
| decode | 12 tok/s | **4** | 834 ÷ 165.0 = 5.1 and 1 115 ÷ 238.6 = 4.7, rounded down |
| ITL | 90 ms | **200** | 238.6 s ÷ 1 115 tok = 214 ms |

**Calibrated on observed wall-clock TTFT, not on the daemon's own
`prompt_eval_duration`.** This was the decisive judgement of the patch.
Ollama reported 45.3 s of prefill, but the caller waited 103.5 s after
load for the first token — a 58 s gap this brief did not explain and did
not paper over.

Had the internal counter been trusted (24 tok/s), the derived TTFT budget
would have been ≈170 s against this run's observed 168.1 s: a **1.2%
margin**, which is a coin flip rather than a fix.

Two other measurements were discarded rather than used:

- **Warm prefill of 7 056 tok/s** — prompt-cache reuse of an identical
  prompt, not throughput.
- The earlier wall-clock figure of ~14 tok/s — it conflated model load
  with prefill.

### Finding 3 — cold-start model load was unmodelled

`ProviderProfile.model_load_ms`, measured directly from the daemon's own
`load_duration` on a cold start: **33.4 s**, stored as 35 000 ms rounded
up.

Added to the prefill estimate **un-multiplied**: the safety factor exists
to cover estimate error in prefill, and applying it to a measured
constant would inflate a number that is already known.

Every call is budgeted as though cold, because nothing tracks whether a
model is resident. Over-waiting on a warm call costs patience;
under-waiting calls a healthy provider broken.

---

## 3. Files changed

| File | Change |
|---|---|
| `broker/profiles.py` | `model_load_ms` + serialization |
| `ai_infrastructure/catalog.py` | `model_load_ms` on the spec; `ollama.local` re-measured |
| `ai_infrastructure/profiles.py` | carries it through |
| `ai_infrastructure/workload.py` | `typical_output_tokens` on every class |
| `ai_infrastructure/budgets.py` | class default for output; load added to the estimate |
| `tests/test_timeout_profiles.py` | assertions updated to the re-measured rates |

**The Planner was not changed.** See Finding 1.

**Tests added:** `tests/test_timeout_calibration.py` — 20 tests, one per
acceptance finding plus the regressions that would reintroduce them
(`total_ms > ttft_ms` for planning; no class budgets zero output; load
added once and never multiplied; determinism preserved).

---

## 4. Margin, and whether it is too generous

Roughly 2× on both deadlines. That is deliberate given a 58 s gap nobody
has explained yet, and it costs nothing in the failure cases that matter:

- a **dead daemon** still fails in ~1 s (connection refused)
- a **stall** still fires at 5 s, not at 659 s
- only a provider that is genuinely producing, slowly, gets the full
  window

The generous number is the one that is never reached in a healthy call
and never reached in a broken one either.

---

## 5. What MB038A did not address

- **The 58 s TTFT gap.** Observed TTFT exceeds `load_duration +
  prompt_eval_duration` by 30–60 s in every run measured. Unexplained.
  The budget absorbs it; nothing explains it.
- **Capability payload schemas.** This run's plan still names payload
  keys the actions may not accept — MB036 Finding 4, unrelated to
  timeouts, and still the highest-value item in the backlog.
- **Output size for five of six classes** is a stated conservative
  assumption, not a measurement. Only `planning` is measured. Each is
  bounded by its class ceiling.
- **Rates for every provider except `ollama.local`** remain unmeasured
  and fall back to ceilings.
- **Stage B** — mission SLA, Runtime enforcement, founder cancellation
  verb — remains ADR-gated and unstarted.

---

## 6. Comparison

| | Prompt | Budget | Result |
|---|---|---|---|
| MB036 | 26-capability plan | 120 s flat | `no answer within 120s` |
| MB036 (raised) | same | 540 s flat | planned |
| MB037 | larger objective | 540 s flat | `no answer within 540s` |
| MB038 acceptance | same objective | 161.85 s derived | `timed_out_ttft`, 0 tokens |
| **MB038A** | **same objective** | **658.7 s derived** | **planned, verified, 325.6 s** |

The difference is not that the number got bigger. MB036's raised 540 s
was larger than MB038A's TTFT budget and still failed on the next
objective, because a flat number cannot follow the work. This budget was
derived from the prompt's measured size, the provider's measured
throughput and its measured load time — and it reports which of those
bound it.
