# 30 August 2026 — Founder Edition demo readiness

The durable state of the demo-readiness sprint. Facts and their sources;
no metric here is estimated.

---

## 1 · Git truth at the start

```
branch                claude/founder-browser-identity
local HEAD            97087cc2048baef832b7923d80605c779d301832
origin branch HEAD    b4a9cfeef0c5746e2770e1e257f0a1882eea07a9   (one behind local)
origin/main           60dbaa0147b81bc8fae10e684d0fd7e2b4fe84dc
status                clean
ahead / behind main   24 ahead, 0 behind
merge-base            60dbaa0  (= origin/main, still fast-forwardable)
preserved branches    backup/pre-lfs-ORIGINAL, claude/pensive-lichterman-f38f6c,
                      postmigration/main-rewritten
```

Local work had not reached the remote. Pushed, no rewriting:
`b4a9cfe..97087cc`.

---

## 2 · What this sprint inherited

The Desktop/Browser closure is not reopened. Confirmed from final source
and its ledger, not from the previous report:

- deterministic dictated-Browser workflow planning
- `Browser.ObserveBrowser` publishing `selectors` and `elements`
- Evidence-backed founder result projection (`Step.answers_founder`)
- no provider defect proven in the failed acceptance of 26 Aug
- strict equality-on-normalised-URL navigation verification
- desktop operating knowledge, mouse capability reachability
- the Trusted Web lane and its separation from ordinary Browser work
- no-Ollama Founder Edition

One boundary was reopened, and only because new live evidence
contradicted it — see §3.

---

## 3 · P0 defect: question routing

**Live evidence.** A founder opened a fresh session and typed
*"whats required to achieve state kalpavriksha builds kalpavriksha?"*.

```
08:54:43.955Z   founder        the question
08:54:43.958Z   chief_of_staff "Nothing has run yet, so there's nothing to report on."
                events: none · missions: none · broker entries: none
```

Three milliseconds. It reached no Planner, no Broker and no reasoning.

**Boundary.** `brain/utterance.py::structural_role()` — with no question
open, `_is_question(text)` returned `FOLLOW_UP` with `confident=True`.
`confident=True` is the load-bearing half: it meant `decide_role()` never
consulted the Brain's reasoning door, so nothing downstream could notice
the question was about the future.

Reproduced read-only before any change. The discriminator was the
question mark alone:

```
"whats required to achieve state kalpavriksha builds kalpavriksha?" → follow_up
"what is required to make this self-hosting"        (no "?")        → new_objective
"how should we sequence the next three milestones?"                 → follow_up
```

**Fix, at the owner.** A follow-up needs something to follow. Whether one
exists is a fact about the *conversation*; `utterance.py` sees one
sentence. So `structural_role()` takes `has_referent`, supplied by the
surface from `previous_objective_id`, and:

| | referent | no referent |
|---|---|---|
| `"why did that fail?"` | `FOLLOW_UP` | `INFORMATIONAL_QUESTION` |

Same words, two roles, decided by the referent rather than by punctuation.

**Where an informational question goes.** To the Reasoning Executive —
which is what it always was. `Reasoning.Transform(instruction) -> text`
was registered the whole time, so `IntentLayer.answer_question()` names
that capability, the Planner's ordinary one-step path plans it **without
a model**, the Broker chooses a provider, `TextVerifier` verifies, and
`answers_founder="text"` carries the answer back. No advisory layer, no
second brain, no new subsystem, no new refusal code.

**One supporting change.** `opens_an_instruction()` now strips a modal
request prefix — *"could you create…"*, *"can you open…"*. The same
grammatical job `_LEAD` already did, for a shape spanning two words.
Without it, making questions answerable would have turned every
courteous instruction into something to think about instead of something
to do.

**Not implemented**, per the brief: question mark = new objective; any
further punctuation or phrase heuristic.

---

## 4 · The routing test family was dead, not merely red

Fifteen tests in `tests/test_brain_non_execution_routing.py` failed with
`TypeError: _submit_objective() got an unexpected keyword argument
'reasoning_runner'`.

**Adjudication: the tests were stale.** Production removed the advisory
route deliberately, and records why where the call used to be — the live
CV mission told a founder *"I am taking full responsibility for
evaluating all your resume files… Shall I start cataloging those files
now?"* about a mission with no plan and no tasks. The diagnosis in that
comment is the load-bearing part: *an unconstrained reasoner asked "what
should I say about this request?" will propose a next action, because
that is what the question invites.*

A signature change killed every test in the family at once, so the family
that describes non-execution routing had been guarding nothing.

Repaired: harness signature fixed; the assertions that described the
removed behaviour now describe what production does, quoting production's
own recorded reason. **46 pass** (was 31 pass / 15 fail).

`brain/advisory.py` still exists and its own unit tests still pass.
Nothing in production calls it. Recorded here rather than tidied away —
post-demo cleanup, not a sprint change.

Two rows in `tests/test_utterance_role.py` asserted the old rule
(`"what is ready?"` → `FOLLOW_UP` unconditionally). Updated to the
referent distinction with the reason recorded, not deleted.

---

## 5 · Demo gap matrix

| Path | Classification | Evidence |
|---|---|---|
| **A · Local** | WIRED AND PROVEN | battery GP1, 0.3s, both steps `matched` |
| **B · Ordinary Browser** | WIRED AND PROVEN | battery GP2, 2.5s, six steps, fresh `#state` observation |
| **C · Reasoning + action** | WIRED AND PROVEN | battery GP3, 9.3s, `gemini.api`, file == verified text |
| **D · Trusted Web** | PROVEN IN THE PREVIOUS CLOSURE; source unchanged this sprint | see `DESKTOP_BROWSER_FINAL_CLOSURE.md` |
| Founder result delivery | **WAS BROKEN, NOW WIRED** | §6 below |
| Question routing | **WAS BROKEN, NOW WIRED** | §3 above |

---

## 6 · Founder result delivery

The battery caught this: GP2 executed perfectly and the founder was told

> Work finished. 4 of 6 steps were independently verified; 2 could not be
> independently verified.

True, and not what they asked. They asked what `#state` said.

`FounderState.result` means *the last completed task's outcome*, and a
browser workflow's last task is closing the browser. Rather than
overload it, `FounderState.answer` is now its own fact: present only when
a Step designated a field **and** Verification independently observed it.
The surface leads with the answer and follows with the verification
summary — neither replaces the other.

```
accepted

Work finished. 4 of 6 steps were independently verified; 2 could not be
independently verified.
```

---

## 7 · Architecture guards added

`tests/test_browser_lane_separation.py`, 59 tests, all passing on first
run — the architecture already held; now it is enforced.

- ordinary Browser Worker and every ordinary Browser action are
  Playwright-driven
- the trusted provider, the port and the desktop adapter name **no**
  automation driver (playwright, `BrowserSessionManager`, selenium,
  webdriver, puppeteer, remote-debugging, CDP)
- the trusted provider imports nothing from `environment/`
- trusted execution reaches `DesktopTrustedBrowser`, injected as a port
- neither the provider nor the Broker names a browser product
- no ordinary Browser module can reach the trusted lane, and vice versa
- a blocked page produces Evidence rather than a lane change, asserted on
  the `equals`-on-normalised-URL check itself

---

## 8 · The real-browser question for ORDINARY web work (§9 of the brief)

Audited rather than assumed. Classification, in two halves:

**The mechanism: BUILT BUT UNWIRED.** `TrustedBrowserPort` is already
general — `resolve / use / ensure_available / open_task_tab / navigate /
observe / find / type_into / press / click / close_task_tab`. It carries
no website knowledge and nothing about it is web-AI-specific.

**The governance: GENUINELY MISSING.** `BrowserWorker` is hard-wired to
`BrowserSessionManager`, and nothing decides *under what authority*
ordinary Browser work should run in the founder's signed-in browser.
That decision is the missing part, and it is a Brain decision, not a
Worker one.

**Not built this sprint**, deliberately. Recorded as the post-demo
capability **TRUSTED AUTHENTICATED GENERAL WEB ENVIRONMENT**. The Google
incident is a reason to record it, not a reason to build it in five
hours.

---

## 9 · Known debt, carried forward and not hidden

**Retrying a rejected argument.** `Filesystem.CreateFolder` rejected
`unknown location 'on desktop'` and the Runtime retried it three times
before escalating. A deterministic validation failure cannot succeed on
a second attempt; retrying it wastes work and delays the founder's
answer. Recorded **post-demo**: retry policy should distinguish a
transient failure from a rejected argument. Not touched during the
sprint — retry policy is not a demo blocker and is not a place to make
an unscoped change.

**Failed-mission browser session cleanup.** When a Browser mission fails
before `CloseBrowserSession`, the close step never runs and the
Playwright session survives until the process exits. Observed twice —
26 Aug (step_7 never ran) and 27 Aug (step_5 never ran, Chrome pid 7212
left behind).

*Demo blocker: **NO.*** Each mission generates its own `kv-<hex>` session
id, so a leaked session cannot collide with a later one; the battery runs
three missions in one process without interference. Classified
**POST-DEMO P0 · runtime environment-lifecycle debt**. No compensation
system built during the sprint.

**Global absent-Evidence fall-open.** `runtime/engine.py` completes a
task when `verify()` returns `None`, recording
`{"verdict": null, "evidence_id": null, "verifier": "none"}` honestly and
proceeding. Its own comment states the intended end state and why it is
not switched on yet: the Desktop Executive has no canonical verification
path, so enabling the strict gate today would stop working Desktop
capabilities from completing.

*Demo impact: none, and stated rather than papered over.* Every
consequential outcome on the demo paths terminates in canonical
Verification — filesystem writes, browser navigation, the final
observation, generated text. `Browser.TypeText` and `Browser.Click`
remain **delivery-only** by design; the observation that follows owns the
page effect, and no verifier was invented for them to make the battery
look greener.

---

## 10 · North Star audit — *Kalpavriksha builds Kalpavriksha*

Source-traced, not claimed. **This sprint does not advance it.**

| Element | Classification | Note |
|---|---|---|
| Missing-capability detection | **GENUINELY MISSING** | nothing in production notices a gap |
| Self-development queue | **BUILT BUT UNWIRED** | `SelfDevelopmentQueue` + `propose_self_development()`; only tests call it |
| Knowledge acquisition | **BUILT BUT UNWIRED** | `KnowledgeAcquisitionQueue` + Promotion Review; only tests call it |
| Coding Executive / tool | **GENUINELY MISSING** | no coding action exists |
| Repo modification | **GENUINELY MISSING** | filesystem writes exist; no governed repo-edit capability |
| Testing capability | **GENUINELY MISSING** | nothing can run a test suite as a capability |
| Verification | **BUILT AND PROVEN** | with the fall-open debt in §9 |
| Capability registration | **BUILT, STATIC** | registration happens at composition; nothing registers at runtime |
| Restart / persistence | **BUILT** | events, plan history, snapshot, `runtime/checkpoint.py` |
| Resume original objective after restart | **GENUINELY MISSING** | `scripts/live_acceptance/e_persistence_recovery.py` already reports this as unwired rather than claiming it |

**POST_DEMO_NEXT_SEQUENCE**

1. Runtime fail-closed Verification completion (§9), which every later
   item depends on for truthfulness.
2. Failed-mission environment lifecycle (§9).
3. Missing-capability detection → the two queues that already exist.
4. Resume-original-objective after restart.
5. A coding Executive, a testing capability, and governed repo
   modification — in that order, because none of them is safe before 1.
6. `TRUSTED AUTHENTICATED GENERAL WEB ENVIRONMENT` (§8).
7. Founder Surface WebView2 accessibility (the packaged GUI exposes six
   UIA elements, so it cannot be self-driven).

---

## 11 · Not in scope, and deliberately untouched

UI/UX belongs to Hyper Agent. No presentation change was made. The
functional data contracts the surface depends on — founder input, mission
state, approval state, failure state, completion state, verified output —
are unchanged except for the **addition** of `FounderState.answer`, which
adds a field and removes none.
