# KALPAVRIKSHA — CREATE FOLDER INTENT REPAIR & SIMPLE FMEA REPORT

**Date:** 2026-08-19 · **Commit:** `0dcf462` (parent `8a8861c`)
**Artifact:** `dist/Kalpavriksha/Kalpavriksha.exe` — 2026-08-19 14:35:56, 34,254,021 bytes

---

## 1. Git Truth

| | |
|---|---|
| Toplevel | `D:/MasterAgent` |
| Branch | `main` |
| HEAD at start | `8a8861c` — matches the reported checkpoint, verified not assumed |
| Staged work | none |
| Protected local work | 5 tracked files modified before this session (`providers/gemini.py`, `test_desktop_executive.py`, `test_desktop_shell.py`, `test_founder_edition_assembly.py`, `test_founder_edition_boot.py`) — **untouched** |

No reset, clean, discard, force-checkout, rebase or amend was performed.

---

## 2. Historical Folder Semantics

`CreateFolderIntent` once wrote `location = match.group(2) or "Desktop"` — product
policy inside the Brain. That was correctly removed: the default belongs to the
action that owns it. The Intent Layer then left an unstated location unstated,
and `CreateFolderAction` applied `"desktop"` downstream.

---

## 3. Current RCA

| Question | Answer |
|---|---|
| Is `name` required? | Yes — `CreateFolderIntent`, and `required_parameters() == ["name"]` |
| Is `location` optional? | Yes, at every layer |
| Where is completeness decided? | `CreateFolderIntent.parse()` (`brain/intent.py`) — returned an Intent as soon as `name` was non-empty |
| Where does Desktop enter? | `CreateFolderAction.run()` / `validate()`: `(parameters.get("location") or "desktop")` |
| Which layer introduced it? | **The capability/action.** Not the Intent Layer, not the Planner, not `direct_plan` — which passes `payload` verbatim |
| Why admitted after only the name? | Because completeness *was* "name present" |
| Did the action fill an unresolved field? | **Yes.** Exactly that |

---

## 4. Authoritative Intent Owner

`CreateFolderIntent.parse()`, reached through the single `IntentLayer.parse()`
entry point. Unchanged — no second owner was introduced.

---

## 5. Why Desktop Was Previously Chosen

Not by a decision about Onkar. `CreateFolderAction` publishes `location` as
optional with `"default": "desktop"` and falls back to it in `run()`. With the
Intent already "complete", nothing remained to ask, so the API-level default
became the founder's answer.

---

## 6. Founder Requirement

For **Create Folder**, `name` and `location` are both founder-owned and both
**REQUIRED**. This is an Intent completeness rule and is deliberately **not**
derived from the capability schema.

---

## 7. Changes Implemented

Four, all on existing seams. No new service, engine or validator.

| File | Change |
|---|---|
| `brain/intent.py` | `location` is founder-required; asks `"Where should I create the {name} folder?"` when unstated; payload always carries both fields |
| `brain/intent.py` | `clarify()` accepts prior answers and merges them under the question's key; `context["clarified"]` records every answer |
| `missions/execution_status.py` | `PendingClarification.supplied` — answers resolved so far, carried in `as_dict()` |
| `kalpavriksha_desktop.py` | Threads resolved fields forward across rounds |

### Why the third change was load-bearing

One round resolves fine from the original sentence plus one answer. Two do not:
re-parsing `"Create a folder"` carrying only `{"location": "Desktop"}` has no name
in it, so Onkar would be asked for the name he gave a turn earlier. Answers
therefore accumulate.

---

## 8. Clarification Contract

The existing contract is single-field (`IntentResult` carries at most one
`ClarificationQuestion`), so the empty case takes two rounds — permitted by the
brief. No parallel clarification identity was minted; `clarification_id` remains
canonical.

---

## 9. Multi-Round Intent Preservation

Same logical Intent throughout: objective stays `"Create a folder"`,
`context["raw_input"]` stays the founder's original sentence, and neither
`"Research"` nor `"Desktop"` is ever admitted as an objective of its own —
asserted in tests and confirmed live.

---

## 10. Planner Admission Proof

An incomplete request yields `result.intent is None`, so `MissionService` — which
only ever accepts an `Intent` — is never entered and the Planner is never reached.
Proven by counting through the real production entry point: after the *first*
answer, `planner.calls == 0` and `admissions == []`; both become 1 only after the
last required field.

---

## 11. Capability Default Boundary

The action keeps its default. Two tests hold the boundary:

- an internal caller passing only `name` still gets a folder (default intact);
- with the action's default swapped to `documents` or `downloads`, Onkar is
  **still asked** — completeness does not consult the schema. Reinforced by an
  AST check that the Intent Layer imports no capability module.

---

## 12. Deterministic Tests

`tests/test_create_folder_intent_completeness.py` — **21 tests**, covering all
ten required matrix items.

Existing suites updated for the new contract, each reviewed individually rather
than bulk-edited: `test_clarification_round_trip.py`, `test_intent_layer_boundary.py`,
`test_local_ai_both_routing.py`, `test_structured_intent_admission.py`,
`test_filesystem_founder_path.py`. **160 pass** across the folder-related suites.

**Full suite: 91 failures with this change, 93 at HEAD, computed as a set
difference — zero introduced.** The two-failure delta is `test_verified_execution.py`
being order/context-dependent, not a fix: run in isolation it fails four tests,
including one that passes in both full-suite runs. Nothing there is attributable
to this work.

---

## 13. Isolated Packaged Build

| | |
|---|---|
| Artifact | 2026-08-19 14:35:56, 34,254,021 bytes |
| New contract in binary | verified in packaged bytecode (`"Where should I create the "`) |
| State root | `%TEMP%\kv_folder_fmea` (disposable) |
| Session | PID 21756, marker-bound |
| Microphone | **absent** — app reported `✗ Voice pipeline`, label at static `TAP TO SPEAK` |
| Normal founder root | untouched — last write 13:55:50, before the 14:38 run |

---

## 14–17. Live Cases

Disk was checked **between** rounds, so "nothing ran yet" is recorded evidence.

### Case A — nothing specified (**LIVE PASS**)

```
Onkar:  Create a folder
Somesh: What should the folder be called?
Onkar:  KV_SIMPLE_143839
Somesh: Where should I create the KV_SIMPLE_143839 folder?     <- disk: ABSENT
Onkar:  Desktop
Somesh: C:\Users\DELL\Desktop\KV_SIMPLE_143839                 <- disk: EXISTS
```

### Case B — name only (**LIVE PASS**)

Asked location; answered `Documents`. Created at `C:\Users\DELL\Documents\KV_DOCS_143926`,
and **confirmed absent from Desktop** — no default substitution.

### Case C — location only (**LIVE PASS**)

`"Create a folder on Desktop"` → `"What should the folder be called?"` → created at
`C:\Users\DELL\Desktop\KV_LOCONLY_143956`. The location from the founder's own
sentence survived the round trip.

### Case D — fully specified (**LIVE PASS**)

No clarification. `C:\Users\DELL\Desktop\KV_FULL_144013`.

**All four missions: `provider_id = None`, `attempts = []`** — deterministic local
planning, zero reasoning.

---

## 18. Verification Evidence

Every folder confirmed on disk independently of the app's own report. Every plan
step recorded `state: completed` with its expectation stated before it ran
(e.g. `"Folder 'KV_SIMPLE_143839' exists at Desktop"`), and every payload carried
the founder-resolved location.

---

## 19. Founder Report

Truthful in all four cases — the actual created path, e.g.
`C:\Users\DELL\Desktop\KV_SIMPLE_143839`. No `[object Object]`, no raw dict, no
cleanup metadata. The previously observed Founder-Surface defect did **not**
reappear.

---

## 20. Simple E2E FMEA Trace (primary multi-round case)

| Boundary | Owner | Result | Verdict |
|---|---|---|---|
| Founder request → Intent parse | `IntentLayer` | name missing, location missing | PASS |
| Missing field → clarification 1 | `CreateFolderIntent` | `"What should the folder be called?"` (`folder_name`) | PASS |
| Pending Intent | `PendingClarification` | objective + key + `clarification_id` + `supplied` | PASS |
| Answer → remaining field | `clarify()` | name resolved, location still missing | PASS |
| → clarification 2 | `CreateFolderIntent` | `"Where should I create the KV_SIMPLE_143839 folder?"` | PASS |
| Completed Intent | `IntentLayer` | `{name, location}` | PASS |
| Mission admission | `MissionService` | admitted once, after the last field | PASS |
| Direct plan | `planner/direct.py` | `Filesystem.CreateFolder`, unique `step_id` | PASS |
| Execution | `CreateFolderAction` | folder created | PASS |
| Verification | disk | folder exists, absent before | PASS |
| Founder report | Founder Surface | real path | PASS |
| Persistence | audit + plan history | `mission_id` == `plan_id`, `completion_id` present | PASS |

---

## 21. Restart Reconstruction — PARTIAL

Process exited; reconstruction performed from disk only.

**Reconstructable by identifier:** `mission_id` → `plan_id` → objective (still the
original `"Create a folder"`) → capability → payload → expectation → step state →
founder-visible result → `completion_id`.

**NOT reconstructable by identifier:** the multi-round clarification thread. A
founder's answer carries no `in_reply_to` and no `clarification_id`, and the two
questions of one logical Intent hold **different** clarification ids with no shared
thread id. Linking `"Desktop"` to the question it answered requires timestamp
ordering, which this part forbids.

Pre-existing — founder turns have never carried a back-reference, including in the
pre-repair audit. It was inconsequential while folders needed one round and became
consequential when they need two. Recorded, not fixed: a clarification thread id
is beyond this mission's stated authorization.

---

## 22. Existing Completion-Semantics Observation

Observed, not changed, as instructed. After a verified creation the surface shows
`Mark complete` / `Marking complete will signal that this step is done.` with
status `awaiting_founder_completion`, and `Send back (not available yet)`.

---

## 23. New Findings

| # | Classification | Finding |
|---|---|---|
| F-1 | **OBSERVED WEAKNESS** | Multi-round clarification threads are not reconstructable by identifier alone (§21). |
| F-2 | **OBSERVED WEAKNESS** | The recorded objective differs by path: clarified missions keep the founder's raw words (`"Create a folder"`), a fully-specified one records the Intent goal (`"Create folder 'KV_FULL_144013'"`). Both are defensible; the inconsistency is the finding. |
| F-3 | **LATENT SOURCE RISK** | `test_verified_execution.py` is order/context-dependent — 4 failures in isolation, 2 in the full suite, with a differing member. Unrelated to this work; it corrupts any failure-count-based reasoning. |
| F-4 | **ARCHITECTURE QUESTION** | Location is matched against known base directories (`desktop`, `documents`, …). Explicit paths (Case F, `C:\Temp`) are not supported by the current contract, and per the brief path semantics were **not** broadened. Whether founder-supplied absolute paths should be admissible is a Founder decision. |

---

## 24. Explicitly Deferred

Untouched per Part 18: Send back, founder completion semantics, Reporter interface
drift, interrupted TTS label, false operational commitment, `_current_objective_id`,
`max_concurrent_tasks`, QC, Outcome Intelligence, Knowledge Acquisition,
multi-mission, Router/Broker, voice/privacy architecture. The privacy gate was not
reopened; no regression was observed in this run.

---

## 25. Git End State

`0dcf462` — one commit, 9 files (3 source, 5 updated test suites, 1 new suite).
Pre-existing modified files remain untouched and uncommitted. Disposable folders and
the FMEA state root removed after evidence capture (copy preserved in the session
scratchpad). No Kalpavriksha processes running.

---

## 26. Verdicts

| Condition | Verdict |
|---|---|
| FOLDER NAME REQUIRED | **READY** |
| FOLDER LOCATION REQUIRED | **READY** |
| NAME-ONLY REQUEST CLARIFIES LOCATION | **READY** |
| LOCATION-ONLY REQUEST CLARIFIES NAME | **READY** |
| EMPTY REQUEST OBTAINS BOTH | **READY** |
| MULTI-ROUND INTENT PRESERVATION | **READY** |
| NO PLANNING WHILE INCOMPLETE | **READY** |
| NO EXECUTION WHILE INCOMPLETE | **READY** |
| FULLY SPECIFIED REQUEST | **READY** |
| FILESYSTEM VERIFICATION | **READY** |
| CAPABILITY DEFAULT DOES NOT DEFINE FOUNDER INTENT | **READY** |
| SIMPLE E2E FMEA BASELINE | **READY** |
| READY FOR MEDIUM E2E FMEA | **YES** |

### Pass condition

This sequence is now impossible, verified live in the packaged application with the
disk inspected between rounds:

```
Onkar:  Create a folder
Somesh: What should it be called?
Onkar:  Research
->      creates it on Desktop
```

Kalpavriksha holds `location = UNKNOWN` and continues clarification. Planning and
execution are reached only when `name != UNKNOWN` **and** `location != UNKNOWN`.

**STOP.** The medium task was not started.
