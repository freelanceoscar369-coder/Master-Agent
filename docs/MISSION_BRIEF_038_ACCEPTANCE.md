# MB038 Acceptance Validation — failed, then fixed

> **Superseded by `MISSION_BRIEF_038A.md`.** The three findings below
> were fixed and the workload now passes: planned and verified in
> 325.6 s against a 658.7 s derived budget. This document is kept as the
> record of the failure and its diagnosis.

# Original report — NOT ACCEPTED

**Date:** 2026-07-31
**Workload:** the original MB036/MB037 planning objective, live, against
`gemma4:latest` on the founder's machine.
**Result:** **the workload still fails.** `timed_out_ttft` at 163.96 s.
**Stopped at diagnosis, as the brief requires. Nothing was changed.**

---

## 1. What happened

```
objective : Create a folder called employee_api and write a README.md
            inside it describing a REST API for employee management.
provider  : ollama.local (gemma4:latest), free, local, chosen by the Broker
planned   : False
outcome   : timed_out_ttft        admission: admitted     lifecycle: failed
latency   : 163 963 ms
```

**Budget derived** (recorded on the ledger, verbatim):

| Field | Value |
|---|---|
| `total_ms` | 161 850 |
| `ttft_ms` | 161 850 |
| `itl_ms` | 5 000 |
| `prompt_tokens` | 1 079 |
| `expected_output_tokens` | **0** |
| `prefill_rate` | 20.0 tok/s |
| `decode_rate` | 12.0 tok/s |
| `total_bound_by` | `estimate` |
| `ttft_bound_by` | `estimate` |
| `itl_bound_by` | `class_floor` |

**Observed:** `ttft_ms: null`, `token_count: 0`, `elapsed_ms: 163 964`.
Nothing arrived at all.

---

## 2. Root cause

A second run of the **identical prompt**, raw and unbudgeted, against the
now-warm daemon:

```
prompt            4 317 chars -> estimated 1 079 tokens
actual            prompt_eval = 1 095 tokens        (estimate off by 1.5%)
first frame       78.30 s   <- and it is the first ANSWER token
frames            521
done              191.88 s, eval = 911 tokens
```

Three distinct causes, each independently sufficient to fail the call.

### Cause 1 — the budget allowed **zero time to generate**

The Planner passes no `expected_output_tokens`, so `derive()` computed
`decode_ms = 0` and `total_ms` collapsed onto `ttft_ms`. Both are
161 850 ms. **The decode window is 0.0 s at every prompt size** —
confirmed by arithmetic across 1 000 / 2 000 / 3 000-token prompts before
the daemon was even asked.

The real call spent **113.58 s** generating 911 tokens. No budget shaped
like this can accommodate that.

This is a **wiring omission in MB038 Step 14**, not a bad number.

### Cause 2 — both declared rates are optimistic by roughly half

| Rate | Declared (Step 0) | Actual, this workload | Error |
|---|---|---|---|
| prefill | 20.0 tok/s | **13.99** tok/s (1 095 ÷ 78.30 s) | 43% optimistic |
| decode | 12.0 tok/s | **8.02** tok/s (911 ÷ 113.58 s) | 50% optimistic |

The Step 0 spike measured short prompts with `num_predict: 24`. That is
the wrong regime: prefill does not extrapolate linearly to a 1 095-token
prompt, and a decode rate averaged over 2–3 tokens says nothing about 911.
The measurement was taken honestly and is simply not representative.

This is a **calibration issue** — exactly the class of error §5.4 of the
architecture predicted ("estimates will be wrong, by design") and that
recorded observation exists to correct.

### Cause 3 — cold-start model load is not modelled anywhere

| Run | State | Time to first token |
|---|---|---|
| Acceptance | cold (first generate after boot) | **> 163.96 s — never arrived** |
| Diagnostic | warm | **78.30 s** |

At least ~86 s of the cold run was loading `gemma4:latest` into memory.
Model load is **not prefill and not decode**; no rate on the provider
profile represents it, and `docs/MISSION_BRIEF_038.md` §4.3 does not list
it as a derivation input.

This is an **unmodelled quantity — an architecture gap**, not a wrong
number and not a defect in what was built.

### Arithmetic, corrected

Using measured rates and the real output size:

```
prefill  1 095 / 13.99  =  78.3 s
decode     911 /  8.02  = 113.6 s
raw total               = 191.9 s   (warm)
+ model load            ≈  86   s   (cold)
                        ≈ 278   s   cold, first call
```

Against a granted budget of 161.85 s. The call was over budget warm, and
far over it cold.

---

## 3. Classification

| Cause | Class |
|---|---|
| 1. Zero decode allowance | **MB038 defect** (Step 14 wiring, incomplete) |
| 2. Optimistic prefill/decode rates | **Calibration issue** |
| 3. Cold-start model load unmodelled | **Architecture gap** (not covered by MB038 as specified) |

**MB038 is not accepted.** Cause 1 alone is a defect in what was
delivered.

---

## 4. What MB038 got right

Recorded here because the machinery behaved exactly as designed while
producing a wrong answer — which is the distinction the brief exists to
make possible.

- **The failure is now diagnosable in one read.** MB036 and MB037
  produced `no answer within Ns`. This run produced the granted budget,
  its full derivation, the binding constraint, the observation, the
  admission decision and the lifecycle. Every number in §2 came out of
  the ledger; none required a debugger.
- **`timed_out_ttft`, not `timed_out`.** The call is correctly classified
  as *never started* rather than *too slow* — which is what sent the
  diagnostic at prefill instead of at the total budget.
- **Streaming works.** 521 frames, inter-token gaps ~200 ms against a
  5 000 ms stall budget — an enormous margin, and no false ITL timeout.
- **The tokenizer estimate is sound.** 1 079 predicted against 1 095
  actual, 1.5% error. `chars_per_token = 4.0` needs no change.
- **No retry below the Runtime.** One call, one failure, no repeat.
- **Admission, lifecycle and replay all recorded** and reproduced
  identically on read-back, contacting no provider.
- **The dashboard shows it.** `Budget 162s total / 162s first token / 5s
  stall`, `Bound by estimate`, and the failure line — visible without a
  log file.

The instrumentation is working. The numbers going into it are wrong.

---

## 5. Recommended remediation — not implemented

Ordered. Each is small; none was performed under this brief.

1. **Give the Planner an output estimate.** One argument at the call site
   in `planner/planner.py`. Without it `total_ms == ttft_ms` for every
   planning call, which is Cause 1. A plan is structured JSON with a
   known rough size; ~900 tokens is now a measured figure, not a guess.
2. **Re-measure both rates in the planning regime** — a ~1 000-token
   prompt with an unbounded `num_predict`, not `num_predict=24`. Update
   `ollama.local` in `ai_infrastructure/catalog.py` to ~14 prefill and
   ~8 decode, again rounded down.
3. **Model the cold start.** Options, in preference order: a
   `model_load_ms` field on the provider profile, measured; or warm the
   model at boot so the first real call is never the loading one. This
   needs an architecture note in `MISSION_BRIEF_038.md` §4.3 first — it
   is a new derivation input, not a coefficient change.
4. **Consider whether `ttft_safety = 3.0` still earns its place** once
   rates are honest. It was covering measurement error; with real rates
   and a real decode allowance it may be double-counting.
5. **Re-run this acceptance brief.** With causes 1–3 addressed the
   corrected arithmetic predicts ~280 s cold and ~192 s warm, comfortably
   inside the planning class ceiling of 1 800 s.

---

## 6. Reproduction

- Acceptance harness: `scratchpad/accept_mb038.py`
- Frame diagnostic: `scratchpad/diag_frames.py`
- Both are throwaway validation scripts, not production code.
