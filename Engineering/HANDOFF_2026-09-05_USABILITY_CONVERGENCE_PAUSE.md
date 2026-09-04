# HANDOFF — Self-hosted usability convergence, paused 2026-09-05

**Mission status: INCOMPLETE. Do not close it, do not restart the campaign,
do not start a different development stream.**

The campaign: make the actual Kalpavriksha application independently complete
SIMPLE → MODERATE → EXPERT → COMPLEX objectives. Claude observes, diagnoses,
repairs and re-runs. Claude never performs the mission.

---

## 1. Where the campaign stands

```
SIMPLE          anchor-1   FAIL   (2 product runs, 2 failures)
                anchor-2   not reached
                generalisation  not reached
MODERATE / EXPERT / COMPLEX      not started
```

No level gate has been met. There is **no valid Kalpavriksha pass yet** at any
level in this campaign.

## 2. The exact original prompt — DO NOT SIMPLIFY IT

Submit this verbatim to the running application after the next repair:

```
Ensure a folder Kalpavriksha_Usability_Simple exists on my Desktop. Inside it ensure result.txt contains exactly: Kalpavriksha simple usability test passed. Verify folder/file/content, then report.
```

Do not supply URLs, answers, focus assistance, provider choice, or any part of
the outcome. Do not shorten it because it failed.

## 3. The two product runs

Both went through the real app: `python kalpavriksha_desktop.py`, prompt typed
into the real UI via `scripts/live_acceptance/_founder_submit.py`, real Send.

| | run 1 | run 2 |
|---|---|---|
| submitted | 17:17:05Z | 17:36:32Z |
| failed | 17:24:53Z (7m48s) | 17:41:12Z (4m40s) |
| founder saw | "I couldn't plan that just now. Please try again." | same |
| mission_id | none created | none created |
| reasoning thread | **not created** | **not created** |
| artifact | none | none |

```
EXECUTED_BY_KALPAVRIKSHA        TRUE
REASONING_THREAD_CREATED        FALSE
FOUNDER_INTERVENTION_COUNT      0
CLAUDE_MISSION_INTERVENTION     0
WRONG_WINDOW_INPUT_COUNT        0
FALSE_COMPLETION                FALSE   (it failed honestly, twice)
ARTIFACT_OR_EFFECT_VERIFIED     FALSE
FINAL_RESULT                    FAIL
```

## 4. Boundary closed in run 1 — REPAIRED, LIVE-PROVEN

**PROVIDER.** Every reasoning lane was reported unusable while all four AI
desktop applications were running:

```
chatgpt-desktop      timed_out    77.1s
perplexity-desktop   unavailable  31.2s
kimi-desktop         rejected      0.0s
trusted-founder-web  rejected      9.1s
-> no_provider_available
```

Probed alone, ChatGPT Desktop answered the same Stage 1 obligation prompt in
95.1s. The lane worked. It was cut off by `_RESPONSE_POLL_TIMEOUT_SECONDS =
45.0`, a constant tuned against the three-name acceptance prompt. MB038 already
derives a per-request deadline and `complete()` has taken a `budget` since Step
14 — the provider **accepted the parameter and never read it** (`budget`
appeared once in the file, in the signature). A source failure was therefore
reported as an objective failure, which ADR-0027 exists to prevent.

Repair `e1836020`: the budget decides the reply window; the old constant stays
as a **floor** so a small derived deadline cannot reintroduce truncation;
callers passing no budget are unchanged. Three regression tests, each
mutation-checked in both directions.

Proven live in run 2 — all four reasoning calls now succeed, three of them
beyond the old cutoff:

```
brain_founder_obligations            succeeded  90.8s
brain_founder_obligation_audit       succeeded  65.4s
brain_founder_obligation_correction  succeeded  54.8s
brain_founder_obligation_audit       succeeded  72.9s
```

## 5. The CURRENT first incorrect causal boundary — NOT YET REPAIRED

**INTENT / BRAIN — Stage 1 obligation admission.**

With reasoning working, `_trusted_founder_obligations()`
(`src/master_agent/brain/intent.py`) runs its full bounded sequence —
propose → audit → untrusted → correct → audit → untrusted — and returns
`UNSETTLED_INTERPRETATION`. `missions/service.py` then refuses, so no mission
and no plan are ever created.

Stage 1 cannot settle the meaning of *"make a folder, put a file in it with
this text, verify it."* Stage 1 is FROZEN and live-proven at `0e4eb95`, so this
needs new causal evidence before any change — which is exactly what is missing:

**Observability blocker.** `src/master_agent/brain/intent.py` contains **no
logging at all**, and the refusal emits no event carrying its reasons. The
`issues` list that explains the rejection is computed and discarded, so the
cause is currently invisible.

## 6. NEXT EXACT ACTION

1. Make the Stage 1 obligation refusal legible — persist the decision record
   (`verdict`, `issues`, `omissions`, `collapses`, `invented`,
   `unexplained_regions`) as a **product-safe** record, structured evidence
   only, never a reasoning transcript. This is the same record §3 of the
   campaign requires as the **Kalpavriksha Reasoning thread**, so do it once,
   in the existing Brain/ADR-0027 architecture — do not invent another
   Brain/Wisdom layer and do not substitute Claude's notes.
2. Restart the app, submit the same prompt, read the recorded reasons.
3. Only then decide whether the defect is in Stage 1 admission or upstream.
4. Focused regression → changed-surface tests → restart app → same prompt again.

## 7. Open product issues, still open

- **Reasoning thread** — not created for any material mission so far.
  `ACCEPTANCE = FAIL` until it is.
- **Trusted-web page reach** — separate from turn ownership, which IS
  live-proven (`a3f9a9d6`). Three of six submission attempts never submitted:
  `could not confirm window … reached the foreground`, and
  `sign-in did not complete in time` on an authenticated page. Owner is the
  desktop foreground/page-state layer. Caveat held open: those runs were driven
  from a background process on a busy desktop, so harness and product are not
  yet separated.
- **Computer-Use target ownership** — the general invariant (uncertain target ⇒
  zero input) must not be solved only inside a Gemini-specific harness. No
  wrong-window input occurred in this campaign; `_founder_submit.py` refuses to
  type unless the window is confirmed Kalpavriksha and foreground.
- **Untruthful failure message** — the founder is told "I couldn't plan that"
  when the truth may be "I could not reach any reasoning". Not repaired; not
  the current boundary.

## 8. Repository

Everything from this session is committed and pushed. The worktree is dirty
only with work that is **not mine and was left exactly as found**:
`Engineering/bluetooth_switch_test.log` (regenerated by an unrelated mic run)
and `src/master_agent/planner/plan.py` (EOL-only churn, zero content diff),
plus ~90 untracked paths including Hyper Agent's UI/UX assets, the founder's
obsidian notes, and agent detritus. Do not sweep them.
