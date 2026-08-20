# KALPAVRIKSHA — SAFE CROSS-STEP LIVE ACCEPTANCE REPORT

**Date:** 2026-08-20 · **Base:** `630956a` · **Safety seam:** `044476f` (pushed before the run)

The safety seam worked. **Live acceptance is BLOCKED** — Gemini's free tier is still
exhausted, and this time the harness refused to fall through instead of launching
twenty-three applications on the Founder's machine.

---

## 1. Git Truth

`HEAD == origin/main == 630956a` at start, ahead 0, behind 0. Protected worktree
(5 modified, 111 untracked) untouched, and 116 entries again afterwards. No reset,
no clean, no force push.

---

## 2–5. The safety seam, and why a pre-flight could not have been it

The last run's damage was not caused by a bug. The ladder did exactly what the product
should do — Gemini refused, so it fell through to the desktop AI applications — and
launched 23 ChatGPT/Kimi/Perplexity processes. Correct product behaviour, unacceptable
test behaviour.

The instruction to pre-flight was the natural fix, and it cannot work:

* a one-word probe succeeds where a planning-sized request gets 429 — that is precisely
  how the last run started;
* a planning-sized probe consumes the quota it is trying to predict.

There is no probe that answers this question. **Scoping the tiers is the only honest
answer:** the harness refuses to fall through rather than guessing whether it would need
to. That is why this run had no pre-flight at all — the Planner call was the first and
only provider call, exactly as §21 required.

`TieredPromptRunner.__init__` already accepted `gemini_provider_ids`,
`desktop_provider_ids` and `browser_provider_ids`. **No new routing type was needed** —
the composition passes empty desktop and browser sets when
`KALPAVRIKSHA_FMEA_REASONING_TIER` is exactly `gemini`.

**No production routing policy changed.** The Broker's fallback behaviour is byte for byte
what it was; only the harness's composition differs, and only under an explicit switch.

---

## 6. Normal launch is provably unchanged

`tests/test_fmea_reasoning_scope.py`, 11 tests. The composition is read through the **AST**
rather than grepped: both later tiers must be conditional on `_gemini_only`, and must
still draw from `PROVIDER_CATALOG` and `BROWSER_FREE_AI_ID` when the switch is off.
Unset, blank, misspelled, `off`, `desktop` — anything but the exact value leaves the full
Gemini → Desktop → Browser ladder, so a typo cannot quietly cost the Founder their
fallback.

The 429 case is simulated directly: a Gemini failure under the scope reaches **no** desktop
or browser provider. A premise test proves an unscoped runner demonstrably would, so the
guard is not protecting against a problem that does not exist.

**Mutation proof:** making the scope fail to empty the desktop tier fails
`test_the_desktop_tier_is_only_emptied_under_the_switch`. Restored, 11/11 pass.

---

## 7. Commit ordering

Committed and pushed as `044476f` **before** the packaged build and before any live call.
`HEAD == origin/main == 044476f`, ahead 0, verified by fetch. No validated code was left
local.

---

## 8–9. Isolation

| | |
|---|---|
| `KALPAVRIKSHA_STATE_DIR` | disposable root; all four state files written there |
| Normal Founder profile | **MD5-verified unchanged**, 4 files, before and after |
| `KALPAVRIKSHA_DISABLE_MIC` | `1` |
| Desktop AI processes before launch | **0** — a clean baseline |

---

## 10. The Planner call — one call, one provider, refused

```
capability : reasoning        task: plan-1        requester: planner
provider   : gemini.api       model: gemini-3.6-flash
outcome    : rejected         retries: 0          latency: 2981 ms
error      : HTTP 429 ... Quota exceeded for metric:
             generate_content_free_tier_requests, limit: 20
```

The Broker record contains **exactly one decision**, `ranked first of 1 eligible`, with the
other nine providers listed under `exclude_providers`:

```
browser.free-ai, chatgpt-desktop, claude-desktop, kimi-desktop,
lm-studio.local, ollama.local, openai.api, openrouter.api, perplexity-desktop
```

Events reached `mission_planning_started` and stopped. No plan was produced.

**The seam did its job.** Same provider refusal as last time; no second tier was asked,
and nothing was launched.

---

## 11–15. Live acceptance criteria — NOT OBTAINED

No plan means no execution, so the pre-execution plan gate, the live cross-step value
chain, mission isolation on a live mission, the physical file, WriteFile Evidence and
durable live provenance were none of them obtained. They require one successful planning
call. Nothing here is inferred from the deterministic tests and presented as a live
result.

---

## 16. Process accounting

| | |
|---|---|
| Kalpavriksha processes after | **0** |
| Perplexity / ChatGPT / Kimi | **0** |
| Started during the run window | **0** |

A count of 12 `claude` processes is present, all started at 07:33 — 52 minutes **before**
the 08:25 launch. They are this engineering session's own CLI processes, not fallthrough,
and were correctly left alone. Recorded here because the raw number would otherwise look
like the exact failure this mission exists to prevent.

---

## 17. Preserved

Objective ownership is identity-safe, and dependency source lookup is scoped to the
consuming Objective. The cross-step binding contract, the result ≡ Evidence trust rule and
the production JSON wire form are untouched by this mission.

---

## 18. Cleanup

FMEA state root removed (copy preserved in the session scratchpad). No `KV_MEDIUM_*`
folder on Desktop. `Desktop\Desktop` unchanged at its two pre-existing items. Founder
profile MD5-verified unchanged.

---

## Verdicts

| | |
|---|---|
| SAFETY SEAM IMPLEMENTED | **YES** |
| NORMAL LAUNCH LADDER UNCHANGED | **YES** — AST-asserted |
| SAFETY SEAM COMMITTED BEFORE RUN | **YES** — `044476f` |
| PRE-FLIGHT PERFORMED | **NO** — by design; the Planner call was the only provider call |
| PROVIDER CALL | **BLOCKED** — HTTP 429, free-tier limit 20 |
| DESKTOP FALLBACK ATTEMPTED | **NO** |
| DESKTOP PROCESSES LAUNCHED | **0** |
| STATE ISOLATION HELD | **YES** |
| FOUNDER STATE UNCHANGED | **YES** — MD5-verified |
| MICROPHONE DISABLED | **YES** |
| PLAN PRODUCED | **NO** |
| LIVE CROSS-STEP VALUE CHAIN | **NOT OBTAINED** |
| OBSERVED TITLE / URL IN FILE | **NOT OBTAINED** |
| WRITEFILE DYNAMIC CONTENT VERIFIED | **NOT OBTAINED** |
| DURABLE LIVE PROVENANCE | **NOT OBTAINED** |
| GLOBAL FAIL-CLOSED ENABLED | **NO** |
| SEMANTIC OUTCOME QC IMPLEMENTED | **NO** |
| INTRODUCED TEST FAILURES | **0** — 11 at `630956a`, 11 after |

---

## The question

> *Can the Medium objective be accepted live without risking the Founder's machine?*

**The second half is now answered: yes.** The identical provider refusal that cost 23
unwanted processes last time cost zero this time. The harness fails fast instead of
falling through, and it does so without weakening the fallback a real Founder launch
depends on.

**The first half is still unanswered, and for the same reason as the previous two
attempts.** Gemini's free tier allows 20 requests per day and it is exhausted. This is an
environmental blocker, not an implementation result.

What remains is genuinely one successful planning call. Every mechanism it would exercise
is built and deterministically proven; none of it has yet been proven on a live mission,
and this report does not claim otherwise.

**Recommended next step: re-run this exact acceptance after the daily quota resets, or
supply a billed Gemini key.** The seam now makes that re-run safe to attempt at any time —
a failed attempt costs one refused API call and nothing else.
