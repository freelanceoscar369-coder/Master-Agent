# KALPAVRIKSHA — FIRST MEDIUM E2E FMEA REPORT

**Date:** 2026-08-19 · **Tested at:** `68b03fc` (synced with GitHub)
**Artifact:** `dist/Kalpavriksha/Kalpavriksha.exe` — 2026-08-19 15:44:05, 34,254,021 bytes

**Outcome: material failure at the FIRST boundary — Founder → Intent.**
Execution stopped there, per the mission's stop rule. No repair was attempted.

---

## 1. Git Truth

| | |
|---|---|
| Root / branch | `D:/MasterAgent` / `main` |
| LOCAL HEAD | `68b03fc` — matches expectation |
| REMOTE origin/main | `68b03fc` |
| AHEAD / BEHIND | 0 / 0 |
| Staged | none |
| Protected | 5 modified tracked, 111 untracked — untouched |

---

## 2. Isolated FMEA Environment

| | |
|---|---|
| State root | `%TEMP%\kv_medium_fmea` (disposable) |
| FMEA PID | 12404, marker-bound |
| Microphone | **absent** — app reported `✗ Voice pipeline`, label static `TAP TO SPEAK` |
| Normal Founder root | untouched — 11 records, last write 13:55:50, unchanged after the run |

Seams verified in source before launch: `KALPAVRIKSHA_STATE_DIR` (`kalpavriksha_desktop.py:148`),
`KALPAVRIKSHA_DISABLE_MIC` (`:1040`).

---

## 3. Exact Founder Objective

> Open a browser and navigate to https://example.com. Observe the page's actual title and final URL. Create a folder called `KV_MEDIUM_155505` on Desktop. Inside that folder create a text file called `page_info.txt` containing the title and URL you actually observed. Then close the browser.

Submitted as ONE objective through the packaged Founder Surface. No internal API was called.

Pre-verified absent: the folder and `page_info.txt`.

---

## 4. Canonical Intent — **FAILED**

**No Intent was produced.** `parse()` returned `intent=None` with a clarification.

All ten material requirements were discarded before Planning: open browser, navigate
to the URL, observe title, observe final URL, create folder, location Desktop, create
`page_info.txt` inside it, file contains observed title, file contains observed URL,
close browser.

**MEDIUM INTENT PRESERVATION = FAILED.**

---

## 5. Clarification Behaviour — **FAILED**

Expected 0. Observed 1:

> **Somesh: "What should the folder be called?"**

The objective states the folder name explicitly (`KV_MEDIUM_155505`). The question was
**not** genuinely needed and was **not** answered — answering it would have masked the
defect and tested nothing.

**NO UNNECESSARY CLARIFICATION = FAILED.**

---

## 6–7. Planner / Provider / MissionPlan — NOT REACHED

`plan_history.json`, `broker_decisions.json` and `events.jsonl` were **never created**
in the isolated root. No mission was admitted, no mode selected, no provider consulted,
no plan produced.

**MEDIUM PLAN COMPLETENESS = NOT ASSESSED** (nothing to assess).

---

## 8–12. Browser / Cross-Step Flow / Filesystem / Close — NOT REACHED

No browser process started (verified: no chrome/msedge/firefox began in the run window).
No folder, no file. The world is unchanged.

**BROWSER EXECUTION / BROWSER OBSERVATION / FILESYSTEM EXECUTION = NOT ASSESSED.**

---

## 13. Independent Verification

Verified independently that **nothing happened**: folder absent, no browser launched,
normal Founder root byte-identical to baseline.

---

## 14. Founder Report

The surface behaved **correctly** while reporting a wrong upstream decision. It showed
`Needs your answer`, the question, and Onkar's complete original objective. No
`[object Object]`, no raw session dictionaries, no cleanup metadata, no internal step
output.

**FOUNDER REPORT = READY** — for what it was given. The defect is upstream.

---

## 15. Completion-Surface Observation

Not exercised — the mission never completed. Known deferred findings untouched.

---

## 16. Persistence

Three interactions recorded. Onkar's full objective is preserved verbatim as
provenance. The clarification carries `clarification_id=00db061f` and
`in_reply_to=264507db593e`, correlating to his turn.

---

## 17. Fresh-Process Reconstruction — **PARTIAL, and correct**

Process exited; reconstructed from disk by identifier, no timestamp inference:
Onkar's exact objective → the response it produced → the fact that no mission, plan,
provider decision or lifecycle event exists.

Cross-step observed values are **not** reconstructable — because none were ever
produced. That is an accurate record of what happened, not a persistence defect.

---

## 18. Medium FMEA Matrix

| Boundary | Expected | Actual | Evidence | Verdict | Owner |
|---|---|---|---|---|---|
| Founder → Intent | preserve the whole objective | routed to a single-capability folder parser; all other requirements dropped | `parse()` → `intent=None` | **OBSERVED FAILURE** | `IntentLayer` |
| Intent → admission | admit a complete Intent | never reached — no Intent | no mission id | **NOT REACHED** | `MissionService` |
| Intent → Plan | multi-step plan | never reached | `plan_history.json` absent | **NOT REACHED** | `Planner` |
| Planner → Router | mode + tier trail | never reached | `broker_decisions.json` absent | **NOT REACHED** | `CapabilityBroker` |
| Plan → Runtime | dispatch steps | never reached | `events.jsonl` absent | **NOT REACHED** | Mission Control |
| Browser → Observation | real title + URL | never reached | no browser process | **NOT REACHED** | Browser plugin |
| **Observation → later-step input** | observed value becomes a later argument | **no mechanism exists in the contract** | `Step.payload` is a static dict fixed at plan time; `depends_on` orders only; no substitution/reference resolver found; step results not accumulated for later steps | **LATENT SOURCE RISK** (source-proven, *not* live-observed) | `Planner` + Runtime |
| later-step → Filesystem | write observed content | never reached | no file | **NOT REACHED** | Filesystem plugin |
| Execution → Verification | prove world state | never reached | — | **NOT REACHED** | Verification |
| Verification → reporting | truthful report | correct for input given | surface text | **LIVE PASS** | Reporter/Surface |
| reporting → Founder Surface | no internals leaked | clean render | UI tree | **LIVE PASS** | Founder Surface |
| lifecycle → persistence | durable, correlated | objective + question correlated | audit JSONL | **LIVE PASS** | Interaction audit |

---

## 19. First Material Failure Boundary

### **Founder → Intent**

---

## 20. RCA

`IntentLayer.parse()` dispatches by **first-match-wins substring** over an ordered
pattern list, then hands the whole sentence to that one parser:

```python
for pattern, handler in self._patterns:
    if pattern in text.lower():
        return self._with_roles(handler().parse(text, supplied), text)
```

The objective contains the substring `"create a folder called"`, so the entire
multi-step objective was handed to `CreateFolderIntent`.

That parser's regexes are anchored to end-of-string (`...\.?\s*$`), because they were
written for sentences that *are* folder commands. Here the folder phrase sits mid-text,
so no name matched, and it asked for one — while the browser, observation, file and
close requirements had already been discarded by the routing decision.

### The counterfactual, measured

The same semantic objective, with only the folder phrasing changed so no pattern hits:

| Objective | Result |
|---|---|
| `…Create a folder called KV_MEDIUM_155505 on Desktop…` | **CLARIFICATION**, `intent=None`, everything discarded |
| `…Make a directory named KV_MEDIUM_155505 on Desktop…` | **Intent produced**, `goal` = the full objective, `capability=''` → Planner plans it |

The fallback path is the architecturally correct route for a multi-step objective, and
it works. It was simply never reached.

**This is a routing failure, not an understanding failure.** Whether Kalpavriksha
understands a multi-step objective currently depends on whether that objective happens
to contain a single-capability trigger phrase.

### Owner and cause

- **Owner:** `IntentLayer` (`src/master_agent/brain/intent.py`) — pattern dispatch.
- **Cause:** substring dispatch cannot distinguish *"this sentence is a folder command"*
  from *"this sentence mentions creating a folder among other work"*, and `Intent`
  carries a single `capability` + `payload`, so it has no shape for a multi-step objective.

### The second failure waiting behind it — stated so the repair is not mis-scoped

Fixing routing alone will **not** make this objective succeed. Proven from source, not
observed live:

- `Step.payload` is a static `dict[str, Any]` fixed when the plan is parsed
- `depends_on` expresses ordering only
- no substitution, placeholder, or reference-resolution mechanism exists in Planner or Runtime
- step results are not accumulated anywhere a later step could read

So `Filesystem.WriteFile(content=…)` has no way to receive `Browser.ObserveBrowser`'s
observed title and URL. **The Medium question — "can information discovered during
execution become trustworthy input to a later action?" — is answered NO by the current
contract**, independently of the routing defect.

**CROSS-STEP INFORMATION FLOW = FAILED** (by source contract; not live-observed).

---

## 21. Known Deferred Findings

Untouched and out of scope: clarification-thread identifier weakness, Reporter interface
drift, Founder action placement, Send back semantics, unconditional Founder completion,
TTS "interrupted" label, false operational commitment, `_current_objective_id`,
`max_concurrent_tasks`, order-dependent `test_verified_execution.py`, the 11 known test
failures, QC, Outcome Intelligence, Knowledge Acquisition, multi-mission.

None of them caused or obscured this failure.

---

## 22. Cleanup

FMEA state root removed (copy preserved in the session scratchpad). No Desktop folder to
remove — none was created. No browser session was opened. Normal Founder state untouched.
No Kalpavriksha processes running.

---

## 23. Verdicts

| Condition | Verdict |
|---|---|
| MEDIUM INTENT PRESERVATION | **FAILED** |
| NO UNNECESSARY CLARIFICATION | **FAILED** |
| MEDIUM PLAN COMPLETENESS | NOT ASSESSED — never reached |
| BROWSER EXECUTION | NOT ASSESSED — never reached |
| BROWSER OBSERVATION | NOT ASSESSED — never reached |
| CROSS-STEP INFORMATION FLOW | **FAILED** (source-proven; not live-observed) |
| FILESYSTEM EXECUTION | NOT ASSESSED — never reached |
| INDEPENDENT FINAL VERIFICATION | **PARTIAL** — verified nothing happened |
| FOUNDER REPORT | **READY** — truthful about a wrong upstream decision |
| RESTART RECONSTRUCTION | **PARTIAL** — accurate for what occurred |
| MEDIUM E2E FMEA BASELINE | **FAILED** |
| READY FOR COMPLEX E2E FMEA | **NO** |

---

## 24. Readiness for Repair

Two sequential repair missions are indicated, in this order:

1. **Founder → Intent routing** — a multi-requirement objective must not be captured by a
   single-capability parser. (The blocking defect.)
2. **Cross-step information flow** — a later step must be able to consume an earlier
   step's observed output. (Blocks the Medium objective even after #1.)

Doing #2 first would be untestable; doing #1 alone will not make this objective pass.

---

## The question, answered

> *What is the first real failure boundary when Kalpavriksha moves from the proven Simple
> task to a fully specified multi-step, multi-capability objective requiring observed
> information from one step to become input to another?*

**Founder → Intent.**

Kalpavriksha never got far enough to try. A multi-step objective that merely *mentions*
a single known capability is captured by that capability's parser and reduced to it;
everything else the Founder asked for is discarded before a mission exists. Onkar asked
for a browser, an observation, a folder, a file and a shutdown, and was asked what to
call the folder he had already named.

The second boundary — **Observation → later-step input** — is proven absent from the
contract and would have failed next. It was not reached, and is reported as a latent
source risk rather than a live failure.
