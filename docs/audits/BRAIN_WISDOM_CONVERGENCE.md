# Brain / Wisdom intelligence convergence

The single ledger for the `claude/brain-wisdom` mission. ADR-0027 holds
the decision; this holds the evidence.

---

## CURRENT_GIT_TRUTH

```
branch          claude/brain-wisdom
starting HEAD   c1d1760   (verified, not assumed)
origin/main     6349eb1   untouched
merge-base      6349eb1
worktree        clean
stashes         none
```

The reported starting point was treated as a lead and confirmed from Git
before anything was built on it. The preserved acceptance evidence was
re-read and is intact: four plan records, the failing step's error string
verbatim, and `requirements: 0` on the failed record.

## INHERITED_WORK — verified from source, not from the report

| Claimed | Verified |
|---|---|
| `deliberation.py` contracts exist | yes — `DecisionFrame`, `EvidenceAssessment`, `Candidate`, `RecoveryDecision`, `shortlist`, `adjudicate`, `sufficient`, `serves`, `depth_for` |
| research objectives derive requirements | yes |
| requirements carry founder evidence | yes, both lanes |
| **deliberation live-wired** | **no** — a repo-wide grep returned only the module itself. The reported P0.7 gap was real. |
| thread-affinity failure open | yes, and now reproduced deliberately |

---

## ARCHITECTURE_OWNERSHIP

| Concern | Owner | Changed here |
|---|---|---|
| Founder meaning | `IntentLayer` / `MissionService` | requirements now derived for compound objectives |
| Requirements + provenance | `SemanticRequirement` | founder evidence on both lanes |
| Planning | `Planner` (`direct` + AI) | AI lane now carries requirements onto the plan |
| Deliberation | `brain/deliberation.py` | framed at admission |
| Mission lifecycle | Mission Control | **unchanged** |
| Execution | Workers / Executives | **unchanged** |
| Verification | independent | **unchanged** |
| Recovery decision | Brain | added; relayed by the surface |
| Provider selection | Broker | **unchanged** |
| Execution thread | desktop composition root | pinned to one thread |

No second scheduler, dispatcher, mission-state authority, Verification
authority, memory store or orchestrator was created.

---

## INTELLIGENCE_GAP_MATRIX — external mechanisms reconciled

Mature systems used to pressure-test what exists, never to be rebuilt
inside Kalpavriksha.

| Source | Mechanism | Classification | Consequence |
|---|---|---|---|
| **NASA Remote Agent / Livingstone** | goal-directed planning, executive control, model-based diagnosis, replanning | PARTIAL — extend existing owner | Planner + Mission Control + Verification already express the separation. What was missing was the *diagnosis* step between failure and terminal state. Added as a Brain decision, not a new executive. |
| **Soar** | working / semantic / episodic / procedural knowledge, impasse-driven reasoning | ALREADY EXISTS, PROOF INCOMPLETE | Used as a lens, not a design. It exposed that Kalpavriksha does distinguish mission state from memory from capability — but that *episodic* experience is not yet consulted at decision time. Recorded, not built. |
| **Magentic-One** | persistent task/progress state, stall detection, replanning | PARTIAL | Kalpavriksha is deliberately stronger: progress is derived from Verification, never from a model's belief that it finished. Stall detection is the genuine gap (below). |
| **LongHorizon-Harness** | task state outside the executor; only verified environmental facts advance it | ALREADY EXISTS + WIRED | Evidence/Verdict/conformance already do exactly this. No Task Manager added. |
| **Recuris** | working vs experiential memory, localized failure, validation-gated updates | PARTIAL / DEFER | Existing Memory + Knowledge own this. No duplicate store. |
| **AgentRewind** | aligned checkpoints, recovery to an earlier state | REJECT as a generic primitive | External side effects are not reversible. A folder created on the founder's disk cannot be un-created by rewinding agent state. Logical mission recovery is what was built; whole-world rollback was not. |
| **Voyager** | retrieve → execute → critic → verify → promote a reusable skill | EXISTING DECISION, IMPLEMENTATION MISSING | ADR-0012's Knowledge Lifecycle already specifies a *stricter* gate. Seam preserved; not built in this mission. |
| **Reflexion** | failure → structured lesson → improved future decision | GENUINELY MISSING | `RecoveryDecision` records a classification and reason; nothing yet persists it as a reusable lesson. No chain-of-thought would be stored if it did. |
| **PAST-Bench** | prove save → retrieve → reuse → measurable improvement | NOT CLAIMED | Kalpavriksha has memory. This mission does **not** claim learning works, because no paired with/without proof has been run. |
| **Agent-as-a-Judge** | independent requirement-by-requirement evaluation | ALREADY EXISTS + WIRED | `conformance.assess()`, and deliberately without a model. |
| **OSWorld-Verified / V2** | bad evaluators create bad conclusions | ALREADY STRONGER | ADR-0011 keeps Verification independent of the executor; ADR-0026 stops conformance grading its own interpretation. |
| **Anthropic eval practice** | test when behaviour should NOT happen | ADOPTED | The asymmetry tests: a folder must not deliberate. |

---

## IMPLEMENTED_SLICES

**1 — Playwright thread ownership repaired.** `sync_playwright()` binds to
its creating thread; the manager caches the driver for the process; the
founder surface answers each message on a different short-lived HTTP
worker thread. Reproduced against the real manager first, and the
reproduction is kept as a test so "fixed" cannot quietly become "no
longer reproduces by accident". Repaired by giving mission execution one
stable thread — **not** by marshalling inside the browser code, which
would not work, because the actions hold `Page` objects and call
`page.goto(...)` themselves.

**2 — The semantic spine reaches every lane.** `requirements_for()` was
gated on the intent carrying a capability, making `_reasoned_requirements`
unreachable for the objectives it was written for; and the AI plan path
never carried requirements onto the plan.

**3 — Founder evidence on both paths.** Reasoned requirements carried
none, and `description` there is a model's paraphrase — so conformance
would have compared a reading against itself on every compound objective.
The one-sentence path had the same hole.

**4 — Deliberation live-wired**, framed at `MissionService._admit`.

**5 — Brain-owned recovery** at the failure point.

---

## TEST_EVIDENCE

```
brain deliberation            55 passed
execution thread affinity     10 passed  (incl. the real defect reproduction)
focused spine regression     393 passed
GP1 / GP2 / GP3              PASS
intent conformance           16/16 PASS
```

## FULL_REGRESSION

```
75 failed  8511 passed  2 skipped   (25m09s, frozen tree)
baseline   75 failed  8440 passed
NEW FAILURE IDS: ZERO  -- the failure-ID sets are identical
                 8440 + 71 new tests = 8511
```

## LIVE_EVIDENCE

```
'search for action rpg games released in 2026 ...'  -> frame, 4 criteria
'create a folder called FrameProbe on my desktop'   -> NO FRAME
```

Stable across repeated runs — after a fragility was found and removed
(framing had keyed off requirement KIND, and the extractor labelled the
same objective differently on two runs).

---

## OPEN_BLOCKERS

1. **Replan does not preserve verified work.** Recovery therefore runs
   only when nothing has been verified. Needs the Planner to plan around
   satisfied requirements. Deliberately not half-built: a half-build
   could write a file twice.
2. **No stall / no-progress detection.** Predicted-vs-verified delta is
   not yet derived per step.
3. **Deliberation frames but does not yet assess.** No live mission
   produces `Candidate`s or a `DeliberationResult`.
4. **No bounded critique.**
5. **Environment resolution precedence** unproven.
6. **Learning not claimed** — no paired proof.
7. **Live research rehearsal not run.**

---

## PACKAGE

```
built from   937636f  (branch claude/brain-wisdom; main NOT converged)
artifact     dist/Kalpavriksha/Kalpavriksha.exe
sha256       adb74c8923cc946c9c765a3fcbc88b38473a59672c3c45875fec8bd4e32d988a
size         37,039,737 bytes
built        2026-08-28 13:36
self-check   RESULT: OK · 48 capabilities · all five executives reachable
             approval wired · no-ollama constructed=no candidate=no
             deterministic planning: CreateFolder -> WriteFile · FMEA unset
```

`build/` and `dist/` were removed first, so no stale artefact could
survive a locked-file failure.

### Source/package identity — PROVEN

This machine has an editable install pointing `master_agent` at
`D:\MasterAgent\src`, the primary worktree, which does not carry this
branch. Bare imports resolve there, so identity is proved rather than
assumed. The frozen entry script and PYZ were extracted from the
artifact:

```
kalpavriksha_desktop   _ExecutionThread     YES
                       _EXECUTION           YES
                       _recovery_decision   YES
master_agent.brain.deliberation   'no primary source resolves it'  FOUND
master_agent.missions.service     'decision_frame'                 FOUND
```

None of these exist on `origin/main`. The package carries this branch.

### What the package does NOT yet prove

The executable exposes no objective-run flag, so the thread repair is
proved by three things and not by a packaged mission: the kept
reproduction test against the real `BrowserSessionManager`, GP2 through
the real composition, and the repair's presence in the frozen entry
script above. A packaged live research run is the remaining proof and is
listed as an open blocker, not glossed.


---

# CONTINUATION FROM b71aa9a — 28 AUG 2026

Git truth confirmed the lead exactly: branch `claude/brain-wisdom`, HEAD
`b71aa9a`, `origin/main` still `6349eb1`, worktree clean, evidence
intact.

## The founder's objective, run end to end

Run repeatedly through the real production composition. The trace is
what found every defect below — none of them came from reading code.

**The original blocker is gone.** `Browser.OpenBrowserSession` now
verifies `matched`. The mission reaches the web.

## Four defects found by running it

**1. AI plans declared no coverage at all.** The planner prompt never
mentioned `covers`; `parsing.py` never read it. ADR-0026's rule that AI
plans must state coverage was never implemented, so every research step
came back `covers=[]` and conformance answered "no step took
responsibility" — a research mission could only ever be UNKNOWN however
well it ran. Fixed: requirements are now named by id in the prompt and
each step declares what it is for.

**2. One failed step abandoned steps that could still run.** The drive
loop stopped at `has_failure`. On the founder's objective that ended a
mission with `step_5` and `step_6` — two different sources for the same
requirement — sitting READY, never dispatched. `MissionDispatcher`
always knew better; the fact lived inside one method. Now
`Objective.has_runnable_work`, one owner, used by both. **Measured after
the fix: step_2 failed and step_4 was tried.**

**3. A false completion — the worst kind.** Conformance treated "any
covering step matched" as satisfied. Right for ALTERNATIVES, wrong for
STAGES, and an AI plan is stages. Measured: step 1 opened a browser and
verified, step 2 failed, steps 4–6 never ran, and *"give me free demo
download links"* was reported **SATISFIED** on the strength of a browser
having opened. A requirement whose covering steps did not all report is
now UNKNOWN.

**4. `decision_frame` was being pasted into the planning prompt** as a
raw dict, along with `field_evidence`. Brain bookkeeping the Planner
cannot act on.

## Deliberation

`Observation -> Candidate -> adjudicate -> shortlist -> sufficiency ->
DeliberationResult` is complete and tested (70 cases). The model reads
prose into structure and decides nothing; every `met` must cite an
evidence id that was actually supplied, and one that was not is
**downgraded to unverified**.

**It is not yet called by the product.** `MissionService` invokes
`frame_for`; nothing invokes `deliberate`. The end-to-end runs above
called it from the probe, not from the mission path. Stated plainly
because "the faculty exists" is exactly the claim this mission was told
not to make.

## Regression

```
77 failed  8525 passed  2 skipped   (35m46s, frozen tree)
baseline   75 failed  8440 passed

NEW FAILURE IDS ATTRIBUTABLE TO THIS WORK: ZERO
```

The two extra IDs are the live Windows-clipboard pair. They **pass in
isolation** on this same tree, and the whole branch diff contains zero
clipboard references; an earlier session proved they fail identically at
the baseline commit in a clean worktree when another process holds the
clipboard lock.

One genuinely new failure did appear mid-session and was the guard doing
its job: `_FakeObjective` had not grown `has_runnable_work`, so the
double had drifted from the contract it stands in for. Fixed on the test
side, and the behaviour is now pinned.

## Still open

- `deliberate()` is not invoked by the mission path.
- Coverage is model-dependent: measured across runs, the Planner emitted
  `covers` twice and omitted it once. Conformance then reports UNKNOWN,
  which is honest but useless. ADR-0026's *rejection* rule is still
  unimplemented — refusing such a plan would turn a reporting gap into
  an inability to act, so it was not done unilaterally.
- Both Navigate steps failed on the live web: one verified `not_matched`,
  the other hit the 5s timeout on Steam. That timeout is the
  browser-policy finding the founder ring-fenced, and it is now the
  blocker for a live research answer.
- No-progress/loop detection, replan preserving verified work,
  environment precedence, material-support boundary, capability-gap
  recognition: unbuilt.


---

# CONTINUATION FROM 2ec717c — RESEARCH REACHES REASONING

Git truth confirmed the lead. Everything below was found by running the
founder's exact objective through `_submit_objective` -- the real product
entry point -- not by reading code.

## The chain, repaired end to end

**Navigation had an element-interaction budget.** All six browser Actions
shared `DEFAULT_TIMEOUT_MS = 5_000`. Clicking asks an in-memory document
a question; `page.goto()` asks an arbitrary public host for a document.
Navigation now has its own 30s budget -- Playwright's own default,
borrowed rather than invented -- and nothing else waits longer.
**Measured: the storefront that timed out twice now verifies `matched`.**

**The Planner was sending us where this lane cannot go.** Its first two
sources were general-web-search query URLs; we landed on an
automation-refusal page and Verification correctly reported
`not_matched`. Nothing malfunctioned. `NavigateAction.description` now
states the destination CLASS that is unreachable -- and a constitution
guard caught an earlier draft of that very comment for naming a product,
which is the rule working.

**`Browser.ReadPageText` produced no Evidence at all.** It was in no
expectation group, so no Verifier ran. It returned text as an Action
RESULT, and an Action result is not Evidence: `input_bindings` refused it
("source has no canonical Evidence"), and the Brain, which may read only
Evidence, saw nothing. A mission could visit three sites, verify all
three, and have nothing to think about. Now page-observable, with a
bounded opt-in `text` facet. **Measured: `ReadPageText verdict=matched
text_len=3929`.**

**The product performs the decision.** `_decide` reads canonical Evidence
into Observations, runs `deliberate()`, records the structured result on
the status contract, and does so BEFORE the success/failure branch --
because a mission that reached three sources and then failed a fourth
step still learned something the founder is owed. **Measured live:
`state: insufficient_evidence, requirement_ids: ['req_1','req_2']`
recorded by the product, not by a probe.**

## A feature of mine that made things worse, and was removed

The bounded recovery loop re-submitted the same intent. Measured, it
produced a fresh plan that opened a browser session the failed attempt
had already opened, and the mission died on `session already open:
'main'` -- a second failure caused by the first attempt's leftovers, and
a worse outcome than the honest failure it was improving on.

`recovery_for` already says a new attempt must differ materially in
source, method, capability, environment, evidence question or strategy.
An identical intent differs in none of them, so the surface was violating
the rule it was relaying. The decision is still made and recorded; acting
on it needs the Planner to plan around satisfied requirements and around
environment the last attempt left behind. That is the next P0.

## Regression

```
75 failed  8541 passed  2 skipped   (23m47s, frozen tree)
baseline   75 failed  8440 passed
NEW FAILURE IDS: ZERO -- the sets are identical
```

## Still blocking the research answer

**AI Planner variance.** Across eight runs of the same objective the
Planner produced: a valid executing plan, a duplicate-argument plan, a
plan binding to a step it did not depend on, an empty plan, and plans
whose alternative sources were chained sequentially so one block stalled
the rest. Roughly half were refused before execution. Coverage shows the
same variance -- `covers` was emitted on some runs and omitted on others.

**Reasoning.Transform sensitivity.** One run reached the synthesis step
and was refused: *"11 provider(s) considered, none eligible: excluded by
the request; sensitive work may not go to a third party."* Public page
text is not private founder material, but the action defaults to
sensitive.

Neither is a founder decision. Both are recorded here rather than
guessed at.


---

# CONTINUATION FROM 5d24b6d — THE THREE BLOCKERS

## P0.1 — Planner self-correction

Eight runs of the identical objective had produced a valid plan, a
duplicate-argument plan, a plan binding to a step it did not depend on,
an empty plan, and plans chaining independent sources. Every one was
already DETECTED precisely; the diagnosis was then thrown away and the
founder was told *"I couldn't plan that just now."*

One bounded correction pass now feeds the exact error back with the
objective, requirements and catalogue repeated verbatim. It repairs the
plan REPRESENTATION and may not reconsider the request.

```
PLANNING STABILITY: 5/5
  run 3: PLAN ok  steps=11  corrected=True
```

Run 3 is the proof: a first proposal that would have refused the mission
was repaired and executed. Fifteen fixtures freeze the observed invalid
shapes, including that invalid-every-time terminates at two provider
calls rather than looping.

## P0.2 — Sensitivity from provenance

`Reasoning.Transform` defaults to `sensitive=True`, correctly. But the
default described the CAPABILITY rather than the MATERIAL, so a mission
that read three public pages was refused for material that was never
private.

The dangerous half is the reverse: `sensitive` arrives in the plan
PAYLOAD, so a model could write `"sensitive": false` over a founder's
private file. Derived now in `resolve_inputs`, which already knows where
every bound value came from and runs after planning, so nothing a model
wrote can reach past it.

```
public  + public   -> public
public  + private  -> private        (a model cannot write past this)
anything unknown   -> unchanged, conservative default stands
```

**Measured live: `Reasoning.Transform` executed on public browser
Evidence instead of being refused.**

## P0.3 — Failed missions release their browser

    attempt 1 opens "main" -> fails before CloseBrowserSession
    -> attempt 2 opens "main" -> "session already open: 'main'"

One attempt's leftovers made the next impossible. `close_anonymous()`
releases task-owned sessions and never identity-backed ones — the
founder's signed-in browser is theirs. Called before the success/failure
branch, because the failing case is the one that caused this.

## The exact objective, end to end

```
step_1 OpenBrowserSession   matched
step_2 Navigate             matched
step_4 Navigate             matched
step_3 ReadPageText         matched   text_len=180
step_5 ReadPageText         matched   text_len=180
step_6 Reasoning.Transform  ran, partially_matched
deliberation: insufficient_evidence, "nothing has been found yet"
```

Every joint now works. The run did not produce a shortlist because the
source returned an **HTTP 500 error page** — the 180 characters are
literally *"Error 500 - Server Internal Error"*. The system behaved
correctly throughout: it reached the page, read what was there, found
nothing that qualified, and said so. A truthful empty answer about a
broken source is the right outcome, and is not a defect in the chain.

## Still open

- A shortlist has not yet been produced from a source that was actually
  serving content. That is a run away, not a repair away.
- `Navigate` verifies `matched` against an error page, because its
  expectation is the destination and the destination was reached. The
  content problem is caught downstream by deliberation. Arguably correct
  layering; recorded rather than changed.


---

# RECOVERY ACTION — 28 AUG 2026

## Verified progress state

`MissionProgress`, derived from records that already exist -- requirement
status from the same `assess()` the founder is shown, so recovery and
reporting can never disagree about what was achieved.

It holds two truths at once, which is the whole reason it exists:

```
OpenBrowserSession   matched
Navigate             matched
ReadPageText         matched
page text            "Error 500 - Server Internal Error"
```

Every step verified. No requirement satisfied. **A verified step is not a
satisfied requirement.**

## Recovery acts

What differs on a second attempt is KNOWLEDGE, not identity: same Intent,
same requirement ids, same founder evidence, plus what the first attempt
learned. The Planner is told which routes failed and which requirements
are already satisfied and must not be redone.

A route is capability PLUS target -- two Navigates are the same
capability and entirely different attempts. Nothing names a site: a test
asserts no hostname appears in the prompting module at all.

The environment is released BEFORE the retry, which is what made the
earlier blind re-submit worse than the failure it improved on.

## Loop rule

```
same requirement standing + no new Evidence + no route eliminated
= NO USEFUL PROGRESS -> stop
```

A failed source still counts as progress: knowing a source is unusable is
knowledge, and it is what makes the next attempt different.

## Live run — Steam, with real content

```
Browser.Navigate      matched   store.steampowered.com/search/...
Browser.ReadPageText  matched   3055 chars of real page text
Reasoning.Transform   FAILED    partially_matched
```

The navigation-timeout repair and the text-as-Evidence repair are both
proven on a live commercial storefront. The mission then failed because
the reasoning provider returned a capacity notice instead of an answer:

> "High demand. Switched to K2.6 Instant for speed. Upgrade to use K2.6
> Thinking."

Verification caught it as `partially_matched` rather than accepting it,
which is the system behaving correctly on a degraded provider. The
research answer is currently blocked by provider capacity, not by the
engineering.

## Two mistakes of mine, recorded

**Cleanup on the wrong thread.** `_release_task_browsers()` looks like
housekeeping and is browser work. Called inline it corrupted the
Playwright driver for every mission afterwards -- "you are using
Playwright Sync API inside the asyncio loop". The execution-thread
invariant was established two sessions ago and this call broke it.

**Editing source during a suite run.** Twelve failures appeared that all
passed on the settled tree: `inspect.getsource` guards reading a file
that changed underneath them. My own recorded rule, broken again.

## Regression

```
75 failed  8615 passed  2 skipped   (31m37s, frozen tree)
NEW FAILURE IDS: ZERO -- sets identical to baseline
```

---

# 29 August — the last two things stopping `more_research`

The P0 that opened this day was provider session health, recorded in
`docs/audits/PROVIDER_SESSION_HEALTH.md`. Once transport health was
established, D/D2/E were re-judged and D2 exposed two defects that had
nothing to do with Kimi.

## D2, before

```
missions run:   1
pages reached:  ['directory.html']
decision:       insufficient_evidence
shortlist:      []
```

One page read, the objective's own question unanswered, and the mission
stopped. Not a wrong answer — a correct decision that nothing could act
on.

## Defect 1 — what is missing was said in identifiers

`_evidence_question` named unresolved criteria by `criterion_id`, so the
Planner was handed

```
- still unresolved: crit_2
```

and asked to go and settle it. A `DeliberationResult` now carries what
its criteria **ask**, not only their ids, and the same line reads

```
- still unresolved: the reading room is open on Sunday
```

Worse, a deliberation that extracted no candidates at all returned
`None` — nothing to ask for. That is not "nothing is missing". A first
source that established none of the criteria leaves **every** criterion
open, which is the widest possible question, and that single `return
None` is why the mission stopped after one cycle.

## Defect 2 — where it might be found was thrown away

The directory page says

```html
<a href="hours.html">Sunday opening hours</a>
```

`read_page_text` kept the words and lost the address. A mission that had
already read the page holding the answer's location could only re-read
the same page — which it did, three missions running, once the first
defect was fixed and it *could* replan:

```
missions run:   3
pages reached:  ['directory.html']
```

A page observation now records where it points: absolute (`el.href`, so
the browser has already resolved it), deduplicated, only anchors that
are somewhere to go, capped at 60 with the cap **declared** when it
bites. `_unvisited_links` subtracts what was already visited, because
"go back where you have been" is the loop this exists to break.

Both halves come out of canonical Evidence. Neither is a model inventing
a destination.

## D2, after

```
missions run:   3
pages reached:  ['directory.html', 'hours.html']
```

`hours.html` is never named in the objective. It was reached because the
system decided it needed evidence it did not have, and knew where that
evidence was.

## A third defect, found by the battery rather than looked for

`SetFocus()` on an inline rename field that had already closed raised
`_ctypes.COMError` out of `_rename_current_session` — a step whose own
docstring says "never raises; a failure at any step simply returns
`False`" — through the reasoning provider, out of
`mission_service.start()`, and ended the mission.

Losing a rename costs reuse on a future call. Losing the mission costs
the founder the work. `write_text` now reports a failed write, and the
methods that promise never to raise no longer merely claim it.

It cost an hour to find because a fixture that raised reported only its
exception type — and the fixture being blamed was not the one that
raised. Fixtures now print the traceback.

## Diversified battery

```
D   two independent sources, neither sufficient alone   PASS
D2  more_research is consumed, and acquires what is missing   PASS
E   a failed source does not end the objective          PASS
F   provider fallback on a service notice               PASS
G   privacy asymmetry                                   PASS
I   unanswerable research stops truthfully              PASS

DIVERSIFIED BATTERY: PASS
```
