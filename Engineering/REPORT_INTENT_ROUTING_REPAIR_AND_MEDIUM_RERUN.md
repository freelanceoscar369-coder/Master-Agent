# KALPAVRIKSHA — INTENT ROUTING REPAIR & MEDIUM FMEA RE-RUN REPORT

**Date:** 2026-08-19 · **Repair commit:** see §22 · **Artifact:** 2026-08-19 16:13:11, 34,255,880 bytes

**The routing repair worked.** The Medium objective now reaches the Planner intact and
produces a correct 6-step multi-capability plan. Execution then stalled at a **new**
boundary — and it is *not* the one source inspection predicted.

---

## 1. Git Truth

| | |
|---|---|
| Root / branch | `D:/MasterAgent` / `main` |
| HEAD at start | `9c243f6` — verified, matches checkpoint |
| origin/main | `9c243f6`, ahead 0, behind 0 |
| Staged | none |
| Protected | 5 modified tracked, 111 untracked — untouched |

---

## 2. Previous Live Failure

`"create a folder called"` appearing anywhere in a sentence handed the whole objective to
`CreateFolderIntent`, which asked *"What should the folder be called?"* while browser,
observation, file and shutdown requirements were discarded before a mission existed.

---

## 3. Intent Routing RCA

Verified in current source, not taken from the prior report:

```python
for pattern, handler in self._patterns:
    if pattern in text.lower():
        return self._with_roles(handler().parse(text, supplied), text)
```

A **substring test** selects the parser and hands it the entire utterance.

---

## 4. Specialised Parser Ownership — answered from evidence

**They are complete-command recognisers, not phrase extractors.** Measured: **15
end-of-string anchors** across this module's regexes, several with `^` start anchors
(`^read`, `^rename`). Every one was written to recognise a sentence that *is* its command.
None was written to pull a phrase out of a larger objective.

So the parsers were never the problem. The *selection rule* disagreed with what they are.

### A parser-level fix would have been insufficient

Measured before implementing: with `CreateFolderIntent` fixed, the pattern `"create"` still
matches `CreateProjectIntent`, which answers the Medium objective with
*"What should the project be called?"* **The hijack would have moved, not gone.** The repair
therefore had to be at the dispatcher.

---

## 5. Generic Fallback Role

Confirmed sufficient. The fallback produces `Intent(goal=<complete objective>,
context={"raw_input": <same>}, capability="")` — the whole request preserved, with
decomposition left to the Planner, which is where the Constitution puts it.

---

## 6. Whether Intent Schema Change Was Required — **NO**

The generic Intent already carries the complete objective. No new field, no per-subtask
capability record, no schema change. Confirmed by the rerun: the Planner decomposed it into
six steps unaided.

---

## 7. Repair Implemented

One helper and one guard in `src/master_agent/brain/intent.py`:

- `enumerates_multiple_requirements(text)` — does this message ask for more than one thing?
  Two structural signals, both the founder's own punctuation and connectives: more than one
  content-bearing sentence, or an explicit sequencing connective (`then`, `and then`,
  `after that`, `followed by`).
- `parse()` consults the specialised parsers **only** for a single-requirement message.

No `CompoundIntentEngine`, no `MultiIntentRouter`, no decomposer. Nothing is refused and
nothing is decomposed in the Brain — a compound objective simply travels the generic route
that already preserved it.

**Stated limit, documented in code:** a genuine single command whose own words contain a
connective (`create a folder called then on Desktop`) takes the generic route. It is still
planned and executed, just not fast-pathed. That is the safe direction to err — the generic
route loses no requirement; the fast path lost four.

---

## 8. Simple Folder Regression — **READY**

| Case | Result |
|---|---|
| `Create a folder.` | ASK[folder_name] |
| `Create a folder called Research.` | ASK[location] |
| `Create a folder on Desktop.` | ASK[folder_name] |
| `Create a folder called Research on Desktop.` | resolves `{name, location}` |
| `Please create a folder called Research on Desktop.` | resolves |

The Simple FMEA baseline is untouched.

---

## 9. Compound Objective Regression — **READY**

All four required compound cases now yield a generic Intent (`capability == ""`) with the
founder's full text preserved and **no clarification**. Wording-accident test included:
"create a folder called …" and "make a directory named …" phrasings now both preserve every
requirement.

`tests/test_multi_step_intent_routing.py` — **33 tests, all pass.**
Regression: 15 affected suites, **0 failures before, 0 after, 0 introduced** (set-differenced
against a stashed HEAD baseline).

---

## 10–11. Packaged Isolated Rerun

Repair verified present in the shipped binary (`enumerates_multiple_requirements` in packaged
bytecode). Isolated profile: state root `%TEMP%\kv_medium2`, PID 16552 marker-bound,
microphone **absent** (`✗ Voice pipeline`), normal Founder root untouched (11 records,
unchanged).

Objective submitted as one message through the packaged Founder Surface.

---

## 12. Intent Preservation — **READY**

**No clarification appeared.** All eight material requirements present in the Intent goal:
browser, example.com, title, URL, `KV_MEDIUM_161341`, Desktop, `page_info.txt`, close.

Before: `plan_history.json` did not exist. After: `plan_history.json`,
`broker_decisions.json` and `events.jsonl` all created.

---

## 13. Planner / Provider Trace — **LIVE PASS**

| | |
|---|---|
| selected / effective mode | both / both (`mode_reason` empty) |
| planned_by | `gemini.api` |
| tier attempts | `[{order:1, tier:"gemini", attempted:true, considered:["gemini.api"], ok:true}]` |
| broker records | 1 |

Tier 1 succeeded first attempt. The durable tier trail is populated.

---

## 14. MissionPlan — **complete, with one serious defect**

Six steps, covering every requirement:

| step | capability | depends_on | state |
|---|---|---|---|
| step_1 | `Browser.OpenBrowserSession` | — | **completed** |
| step_2 | `Browser.Navigate` (`https://example.com`) | step_1 | **completed** |
| step_3 | `Browser.ObserveBrowser` | step_2 | **completed** |
| step_4 | `Filesystem.CreateFolder` `{name: KV_MEDIUM_161341, location: Desktop}` | — | **pending** |
| step_5 | `Filesystem.WriteFile` | step_3, step_4 | **pending** |
| step_6 | `Browser.CloseBrowserSession` | step_3 | **completed** |

**The defect Part 7 asked to be flagged.** `step_5`'s payload, fixed at plan time:

```json
{"path": "Desktop/KV_MEDIUM_161341/page_info.txt",
 "content": "Title: Example Domain\nURL: https://example.com/"}
```

The Planner **hardcoded what it expects example.com to contain**, from prior model knowledge,
with no reference to `step_3`. Onkar asked for *information actually observed*.

Note `step_5` *does* declare `depends_on: ["step_3", "step_4"]` — the Planner expressed the
data dependency correctly and then had no mechanism to consume it, so it filled the gap with
a guess. This is worse than an outright failure: the file would have contained
**plausible-looking values that were never observed**, and would be confidently wrong if the
page ever differed.

---

## 15. First New Failure Boundary

### **Plan → Runtime dispatch — a task is assigned and then stranded**

Not cross-step data flow. Execution never reached `WriteFile`.

Live evidence: 6 tasks created, **5 assigned, 4 started, 4 completed**. `step_4`
(`Filesystem.CreateFolder`) was **assigned to `executive_id: "filesystem"` and never
started**. `step_5` was never assigned (correctly — it depends on step_4). The runtime then
idle-looped **187 dispatch→idle cycles** with nothing to do.

Founder-visible after ~7 minutes: *"That's taking longer than expected; still working on it.
Step 4 of 6 · 6m 43s"* — and it never advances.

---

## 16. RCA of the New Failure

`MissionControl.dispatch_ready()` (`mission_control/dispatcher.py:139`) commits state for
**every** ready task:

```python
task.state = TaskState.DISPATCHED
task.assigned_executive = provider.executive_id
self._executives.set_current_task(provider.executive_id, task.task_id)
```

`RuntimeEngine._cycle()` (`runtime/engine.py:258`) then executes only the first:

```python
for task in tasks[: self._config.max_concurrent_tasks]:   # == 1
    self._handle_task(task)
```

`step_1` and `step_4` were both ready in the same cycle (both `depends_on: []`). Both were
assigned; only `step_1` ran. `step_4` is now `DISPATCHED`, so it no longer appears in
`ready_tasks()` and is never re-offered — **and the filesystem executive is permanently marked
busy with a task that will never start**, so no later filesystem task can be assigned either.

**One layer assigns N, the other runs one, and the difference is neither reverted nor
retried.**

- **Owner:** the seam between `MissionControl.dispatch_ready()` and `RuntimeEngine._cycle()`.
- **Trigger:** two independent ready tasks in one cycle. `max_concurrent_tasks = 1` is the
  trigger, **not the cause** — raising it would mask this case and the bug returns whenever
  ready tasks exceed the cap.
- **Why the Simple FMEA never saw it:** single-step plans never have two ready tasks.

---

## 17. Cross-Step Flow Status — **FAILED, now live-observed at plan level**

Previously source-proven. Now confirmed live in a real plan:

- `step_3` completed; its persisted record has **no result field** — `evidence_id: null`. The
  observed title and URL are **not retained anywhere**.
- The only occurrence of "Example Domain" in durable state is `step_5`'s **plan-time** payload.

So the Medium question — *can information discovered during execution become trustworthy input
to a later action?* — is answered **NO**, and the current behaviour substitutes a prediction
without flagging it.

Not repaired, per Part 8 and Part 14.

---

## 18. Persistence / Restart Reconstruction — **READY**

Process exited; reconstructed from disk by identifier, no timestamp inference: Onkar's
objective → interaction id → plan_id → mode → `planned_by` + tier attempts → all 6 steps and
capabilities → which ran → stall at step_4 → terminal state `running`.

**Not reconstructable:** the browser's observed title and URL — never recorded (see §17).

---

## 19. FMEA Delta — Before vs After

| Boundary | Before | After |
|---|---|---|
| Founder → Intent | **OBSERVED FAILURE** | **LIVE PASS** |
| Intent → admission | never reached | **LIVE PASS** |
| Intent → Plan | never reached | **LIVE PASS** — 6 steps |
| Planner → Router | never reached | **LIVE PASS** — gemini.api, tier 1 |
| Plan → Runtime dispatch | never reached | **OBSERVED FAILURE** — task stranded |
| Browser → Observation | never reached | **LIVE PASS** — open/navigate/observe/close all completed |
| Observation → later-step input | latent | **OBSERVED FAILURE** — plan-time guess, observation not retained |
| Filesystem execution | never reached | **OBSERVED FAILURE** — never ran |
| Verification | never reached | not reached |
| Reporting → Founder | LIVE PASS | **LIVE PASS** — honest "Step 4 of 6, taking longer" |
| Persistence | LIVE PASS | **LIVE PASS** |

---

## 20. Deferred Findings

Untouched: clarification thread-id weakness, Reporter interface drift, Founder action
placement, Send back, completion semantics, TTS "interrupted" label, false operational
commitment, `_current_objective_id`, order-dependent `test_verified_execution.py`, the 11
known failures, QC, Outcome Intelligence, Knowledge Acquisition, multi-mission.

`max_concurrent_tasks = 1` is no longer merely deferred — it is the **trigger** for §16,
though not its cause.

---

## 21. Cleanup

FMEA state root removed (evidence preserved in scratchpad). No Desktop folder to remove —
never created. No test browser left open. Normal Founder root unchanged at 11 records. No
Kalpavriksha processes running.

---

## 22. Verdicts

| Condition | Verdict |
|---|---|
| SPECIALISED INTENT ROUTING | **READY** |
| SIMPLE FOLDER INTENT | **READY** |
| COMPOUND OBJECTIVE PRESERVATION | **READY** |
| UNNECESSARY CLARIFICATION REMOVED | **READY** |
| PLANNER REACHED FOR MEDIUM OBJECTIVE | **READY** |
| MEDIUM INTENT PRESERVATION | **READY** |
| NEXT FAILURE BOUNDARY IDENTIFIED | **YES** |
| MEDIUM E2E BASELINE | **FAILED** |
| READY FOR COMPLEX FMEA | **NO** |

---

## 23. Readiness for Next Repair

Two repairs now indicated, in this order:

1. **Plan → Runtime dispatch stranding** — the blocking defect. `dispatch_ready()` must not
   commit assignment for tasks the engine will not run this cycle (or the engine must run
   what was assigned, or assignment must be reversible/retried).
2. **Cross-step information flow** — a later step must consume an earlier step's observed
   output, and an observation must be retained. Until then the Planner substitutes a
   prediction silently.

Doing #2 first would be untestable: execution cannot reach `WriteFile`.

---

## The question, answered from the packaged rerun only

> *After fixing the single-capability routing hijack, what is now the first live failure
> boundary in the same Medium objective?*

**Plan → Runtime dispatch.**

`Filesystem.CreateFolder` was assigned to the filesystem executive and never started, because
`dispatch_ready()` assigned both initially-ready tasks while the engine ran only one, leaving
the second in a state it can never be re-offered from and its executive permanently marked
busy. The mission stalls at "Step 4 of 6" indefinitely.

This is **not** the cross-step data-flow boundary that source inspection predicted — execution
never got that far. Cross-step flow *did* fail, visibly, in the plan itself: the Planner wrote
the file content from prior knowledge of example.com rather than from the observation it had
correctly sequenced. Both are recorded; neither is repaired here.
