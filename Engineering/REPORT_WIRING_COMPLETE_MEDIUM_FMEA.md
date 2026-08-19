# KALPAVRIKSHA — WIRING-COMPLETE MEDIUM E2E FMEA REPORT

**Date:** 2026-08-19 · **HEAD:** `0788653` == `origin/main`, ahead 0, behind 0
**Artifact:** 2026-08-19 23:47:56, 34,307,699 bytes

**First true missing architecture: Observation → dependent Step input.**

And this run did not have to argue it from a coincidence. The observed URL and the written
URL **differ**.

---

## 1–2. Git Truth & frozen architecture

`D:/MasterAgent`, branch `main`, `HEAD == origin/main == 0788653`, ahead 0, behind 0,
nothing staged. Protected worktree: 5 modified tracked, 111 untracked — untouched. No
reset, clean or destructive checkout. **No production source was modified by this mission.**

---

## 3–4. Packaged build & FMEA isolation

Built from HEAD. Isolated profile `%TEMP%\kv_fmea_wired`, `KALPAVRIKSHA_DISABLE_MIC=1`,
PID 14752 marker-bound.

| | |
|---|---|
| Microphone | **absent** — app reported `✗ Voice pipeline` |
| Normal Founder state | **untouched** — MD5 of all four state files verified OK afterwards |
| Test browser | none left open |

---

## 5. Simple sanity gate — PASS

`Create a folder called KV_WIRED_235111 on Desktop`

| | |
|---|---|
| Physical folder | exists |
| Evidence | present, `filesystem/filesystem_environment` |
| Verdict | `matched` |
| Checks | `target_exists=True`, `target_path=KV_WIRED_235111`, `target_is_dir=True` |
| Founder reply | *"Work finished. All 1 executed step(s) were independently verified."* |

Reporter-derived, not raw Task output.

---

## 6–8. Objective, Intent, Plan

Submitted as **one** Founder message. **No clarification.** Planner reached once,
`planned_by: gemini.api`, tier 1, first attempt.

Six steps, every material requirement covered:

| step | capability | depends_on | state |
|---|---|---|---|
| step_1 | `Browser.OpenBrowserSession` | — | completed |
| step_2 | `Browser.Navigate` (`https://example.com`) | step_1 | completed |
| step_3 | `Browser.ObserveBrowser` | step_2 | completed |
| step_4 | `Filesystem.CreateFolder` | — | completed |
| step_5 | `Filesystem.WriteFile` | step_3, step_4 | completed |
| step_6 | `Browser.CloseBrowserSession` | step_3 | completed |

---

## 9. WriteFile path contract — **REPAIRED, confirmed live**

```json
{"path": "KV_MEDIUM_235147/page_info.txt", "location": "Desktop", "content": "..."}
```

Not `Desktop/KV_MEDIUM_.../page_info.txt`. The published contract worked: the Planner now
emits a path relative to its named location. **No `Desktop\Desktop` artifact was created by
this mission** — that directory still holds only the two pre-existing items from earlier
defects.

---

## 10. Scheduler — **REPAIRED, confirmed live**

`step_1` and `step_4` were both initially independent (`depends_on: []`) — the exact shape
that stranded `step_4` forever in the previous run. All six reached `completed`. No
DISPATCHED-but-never-started task, no executive busy leak, no dispatch→idle loop.

---

## 11–15. Canonical Evidence — all six present, all MATCHED

| step | capability | worker | verdict | checks |
|---|---|---|---|---|
| step_1 | OpenBrowserSession | browser | matched | `session_exists=True` |
| step_2 | Navigate | browser | matched | `url_normalised=https://example.com` |
| step_3 | ObserveBrowser | browser | matched | `url exists`, `title exists` |
| step_4 | CreateFolder | filesystem | matched | `target_exists`, `target_path`, `target_is_dir` |
| step_5 | WriteFile | filesystem | matched | + `content_text_sha256` |
| step_6 | CloseBrowserSession | browser | matched | `session_exists=False` |

**Steps with no Evidence: none.** Real domain identities throughout — no filesystem
mislabelling. Close is verified by session **absence**, not by the Action's own claim.

### The authoritative browser observation

```
url   : 'https://example.com/'
title : 'Example Domain'
captured_at : 2026-08-19T18:22:12.541630+00:00
```

---

## 16–17. Physical state and actual file content

`Desktop\KV_MEDIUM_235147\page_info.txt` — 47 bytes, inside the requested folder:

```
Title: Example Domain
URL: https://example.com
```

---

## 18. Value equality — **MISMATCH**

| | Browser actually observed | Written to the file |
|---|---|---|
| title | `Example Domain` | `Example Domain` ✓ |
| **URL** | **`https://example.com/`** | **`https://example.com`** ✗ |

Onkar asked for *"the title and URL you actually observed"*. The URL in the file is not the
URL that was observed. It is the string from his own objective sentence, fixed into
`step_5.content` at planning time — before a browser existed.

---

## 19. Cross-step provenance — **FAILED**

The plan payload captured before execution already contained the concrete literal:

```json
"content": "Title: Example Domain\nURL: https://example.com"
```

`step_5` correctly declares `depends_on: ["step_3", "step_4"]` — the Planner *expressed*
the dependency and then had no mechanism to consume it, so it filled the gap with a
prediction.

This run did not need the "equality is not provenance" argument, though it would have
applied: **the values are not even equal.** The browser reported the normalised final URL
with a trailing slash; the file carries the un-normalised form from the objective text. A
prediction that happened to be nearly right, and was wrong in the one character that proves
where it came from.

**Every atomic Step verified MATCHED and the Founder's stated requirement was still not
met.** That is the clearest possible demonstration that step verification is not
founder-outcome conformance.

---

## 20–21. Reporter and Founder Surface

> **Work finished. All 6 executed step(s) were independently verified.**

Reporter-derived, from the authoritative `PlanRecord`. Contains no `[object Object]`, no raw
dict, no `{"closed": true}`, and no last-Step output presented as the mission result.

Critically, it does **not** claim the objective was fulfilled — which would have been false.
`metadata.founder_outcome_conformance == "not_evaluated"`, exactly as required.

The restraint built in the previous mission is what stopped a false claim here.

---

## 22. Durable reconstruction — READY

A fresh process reading only the disposable FMEA state rebuilt: the Founder interaction id,
plan_id, `planned_by` + attempts, all six steps with their capabilities, every Evidence
record with true worker identity and verdict, the observed URL and title with their original
`captured_at`, and **the identical Reporter summary**. No browser, no provider, no
re-execution.

---

## 23–24. First material failure boundary & root cause

### **Observation → dependent Step input**

**Root cause.** `Step.payload` is fixed when the plan is parsed. `depends_on` expresses
ordering, and the Planner used it correctly. But no contract exists for a later Step to
reference an earlier Step's *output*: no reference type, no resolver, no runtime binding,
and until this session the observation was not even retained. It is retained now — the
Evidence carries `url` and `title` — so the missing piece is precisely the **consumption**
seam between a retained observation and a dependent Step's payload at dispatch time.

**Ownership seams** (recorded for the next brief, not modified):

* `planner/plan.py` — `Step.payload: dict[str, Any]`, fixed at parse time
* `planner/parsing.py` — where payloads are built from the provider's plan
* `runtime/engine.py::_handle_task` — the last point before `gateway.invoke`, where a
  payload could be resolved against completed steps
* `missions/history.py::StepRecord.evidence` — where the observed values now durably live

Nothing was repaired. No `StepOutputRef`, `RuntimeVariable`, `PayloadResolver`,
`InterpolationEngine` or special-casing of `example.com` was added.

---

## 25. Global fail-closed

**DEFERRED.** Unchanged. The integrated capability surface still contains operations with
no generic independent verification semantics (filesystem queries, browser interactions,
14 of 19 Desktop capabilities). Converting those into failing production operations to
satisfy this FMEA would be the wrong trade.

Note this run would have passed the strict gate anyway: all six of its steps produced
Evidence.

---

## 26–27. Cleanup & Git

`KV_WIRED_235111`, `KV_MEDIUM_235147` and the FMEA state root removed (evidence preserved in
the session scratchpad, including the written file). `Desktop\Desktop` untouched. Normal
Founder state MD5-verified unchanged. No Kalpavriksha processes running.

**No production code changed** — this mission added only this report, so no regression
comparison against `0788653` is required beyond that statement.

---

## Verdicts

| | |
|---|---|
| INTENT PRESERVATION | **READY** |
| PLANNER REQUIREMENT COVERAGE | **READY** |
| WRITEFILE LOCATION/PATH CONTRACT | **READY** |
| SCHEDULER PROGRESS | **READY** |
| BROWSER OPEN EVIDENCE | **READY** |
| BROWSER NAVIGATE EVIDENCE | **READY** |
| BROWSER OBSERVE EVIDENCE | **READY** |
| BROWSER CLOSE EVIDENCE | **READY** |
| CREATEFOLDER EVIDENCE | **READY** |
| WRITEFILE EVIDENCE | **READY** |
| ALL MEDIUM SUPPORTED STEPS HAVE EVIDENCE | **YES** |
| FILE IN REQUESTED FOLDER | **READY** |
| FILE VALUES MATCH OBSERVED VALUES | **NO** — title matches, URL does not |
| OBSERVED VALUES PROVEN TO FLOW INTO WRITEFILE | **NO** |
| REPORTER USES AUTHORITATIVE HISTORY | **READY** |
| FOUNDER OUTCOME OVERCLAIM | **NO** *(required NO)* |
| RESTART RECONSTRUCTION | **READY** |
| **FIRST TRUE MISSING BOUNDARY** | **Observation → dependent Step input** |
| MEDIUM E2E BASELINE | **FAILED** |
| GLOBAL FAIL-CLOSED ENABLED | **NO** |
| READY FOR COMPLEX FMEA | **NO** |

---

## The question

> *Now that the existing production architecture is wired end-to-end, what is the first
> genuine missing architectural capability exposed by the same Medium Founder objective?*

**A dependent Step cannot consume an earlier Step's observed output.**

Everything around it now works. Intent is preserved, the Planner covers every requirement
and expresses the data dependency in `depends_on`, the scheduler runs all six steps, both
filesystem paths resolve correctly, all six steps produce canonical Evidence that survives a
restart, and the Reporter explains the mission from that Evidence without overclaiming.

What is missing is the one seam between a retained observation and the payload of the Step
that depends on it. Because it is missing, the Planner substituted a prediction — and the
prediction was wrong by one character, which is how we know it was a prediction at all.

That is the next repair, and it is genuinely absent architecture rather than unwired code.
