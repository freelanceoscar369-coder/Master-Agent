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
