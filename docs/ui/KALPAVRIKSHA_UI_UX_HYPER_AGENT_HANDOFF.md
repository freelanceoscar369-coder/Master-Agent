# Kalpavriksha — UI/UX handoff for Hyper Agent

**Branch:** `claude/brain-wisdom` · **Audited at:** `6806c90`
**Audience:** Hyper Agent, receiving this cold. You should not need the
founder to explain the system again.
**Status of this document:** production-grounded specification. Every
backend claim below was read out of the source at that commit, not
remembered.

> **Scope.** This is a design brief, not an implementation ticket. No
> production UI was modified to make anything here true. Where the
> backend cannot currently supply something the design wants, it is
> marked and the gap is named rather than filled with invented data.

---

## 1 · What Kalpavriksha is

Kalpavriksha is an **Executive Brain that operates a real machine**. A
founder states an objective in their own words; it works out what was
meant, plans, acts on the actual desktop and the actual web, watches what
happened, checks reality independently, and reports what is true.

It is deliberately **not** a chatbot with tool-call logs. The
architecture separates three things and the interface must not blur them:

| Layer | Owns |
|---|---|
| **Executive Brain** | intent, requirements, decisions, recovery, what "done" means |
| **Shared Infrastructure** | provider selection, budgets, verification, evidence, persistence |
| **Universal Executive Operator** | the hands — browser, desktop, filesystem, document, reasoning |

The single sentence that should govern every screen you draw:

> **The founder should see what was achieved and what is true about it —
> never how the machine is organised.**

### The feeling to design for

> I told Kalpavriksha what I wanted.
> It understood what was obvious.
> It thought only where thinking was required.
> It did the work.
> It kept going when something failed.
> It checked reality.
> It told me what actually happened.

Closer to **a calm executive operating system** than an AI playground.

---

## 2 · The one contract the UI actually consumes

This is the whole surface. There is no other data path into the founder
UI today.

**Bridge** — `kalpavriksha_desktop.py` → `founder_edition/desktop_shell.py::create_window`,
reached from JS as `window.pywebview.api.<name>()`:

| Call | Returns | Notes |
|---|---|---|
| `submit_objective(text)` | dict | the founder's words, verbatim, unparsed |
| `get_execution_status()` | `ExecutionStatus.as_dict()` | **the read model — polled** |
| `confirm_completion(completion_id)` | dict | the founder accepting a finished mission |
| `decide_approval(...)` | dict | answering an approval or a checkpoint |
| `capability_domains()` | domains | what this machine can act on, founder-level |
| `set_mode(mode)` | — | `local` / `ai_mode` / `both` |

**Read model** — `src/master_agent/missions/execution_status.py`.
Its own docstring is the mandate you are working under:

> *"Hyper Agent owns every visual decision about how a founder sees an
> objective run — this module owns none of them… No color, animation,
> icon, or visual metaphor is ever produced here."*

Fields available today via `as_dict()`:

```
status  objective_id  objective  current_step  total_steps
current_task_id  current_capability  attempt  max_attempts
elapsed_ms  timeout_ms  message  result
requires_founder_completion  completion_id
approval_id  approval_kind  approval_preview  approval_context
pending_clarification  selected_mode  effective_mode  mode_reason
errors  terminal_state
```

**The twelve real statuses** (do not invent enums — these are the
spellings):

```
understanding   planning        awaiting_approval   awaiting_clarification
executing       observing       verifying           recovering
awaiting_founder_completion     completed           failed      blocked
```

Plus `idle`, which the front end supplies when nothing is running.

### The existing translation layer — read it before redesigning

`desktop_app/web/js/workState.js` already ports your own earlier
reference implementation and states the governing rule:

> *"Show what is being DONE, not what state the machine is IN. `message`
> describes reality; `status` describes the machine. …the status name is
> NEVER shown to the founder anywhere in this module."*

It already maps every status to founder language (`understanding` →
"Reading your request", `verifying` → "Checking the result", and so on).
**Keep this rule.** You may restyle everything around it.

### Current front-end inventory

```
desktop_app/web/index.html          124 lines — the shell
desktop_app/web/css/tokens.css      163 — design tokens, from Product Veda v1.0
desktop_app/web/css/base.css        110
desktop_app/web/css/surface.css     342
desktop_app/web/css/conversation.css 96
desktop_app/web/css/dashboard.css   126
desktop_app/web/css/prominence.css   98
desktop_app/web/css/work-region.css 312
desktop_app/web/js/app.js          1685 — polling, routing, rendering
desktop_app/web/js/messageRender.js 272 — your renderer, an ES module
desktop_app/web/js/workState.js     172 — status → founder language
desktop_app/web/js/tree.js          440 — the canvas tree
desktop_app/web/js/prominence.js    130
desktop_app/web/js/timing.js        105
```

Tokens already exist and trace to Product Veda v1.0 (typography, a
Founder-Dark palette, spacing scale, four state colours: `--s-live`,
`--s-attend`, `--s-settled`, `--s-risk`, plus `--s-bloom`). Extend that
system; do not start a second one.

---

## 3 · Information hierarchy

Five layers. The discipline is that each layer is **opt-in downward** —
the founder never has to descend to understand the outcome.

### Level 1 — Founder conversation *(primary, always visible)*

Founder input and Kalpavriksha's replies. Calm. Not every system event
becomes a chat message; a mission that changes route four times should
not produce four bubbles.

### Level 2 — Live mission state *(compact, persistent while working)*

Objective · what is happening now · what is already verified · what is
unresolved · whether the founder is needed. No invented percentages.

Prefer **`2 of 3 requirements verified`** over **`67%`**.

### Level 3 — Reasoning / progress trace *(expandable, not default)*

What was established, what is still missing, why the route changed.
Structured state transitions only — **never chain-of-thought.**

```
Confirmed
  ✓ step-free access
Still needed
  ○ Sunday opening hours
Doing now
  → checking another source
```

### Level 4 — Verification / evidence *(inspection, on demand)*

What was verified, from what observation, when. Use the production
vocabulary, which already distinguishes:

```
matched            an independent observation agreed
partially_matched  some of what was expected was observed
unmatched          the observation contradicted the expectation
(no evidence)      nothing independent was recorded
```

**Model prose is never evidence.** A `Reasoning.Transform` result is
measured deterministically (length, line count, whether it parses as
JSON) and *that measurement* is the evidence — see
`plugins/reasoning_gateway.py`, which explains why at length.

### Level 5 — Advanced / diagnostics *(hidden by default)*

Provider names, capability names, mission id, task id, evidence id,
timings, fallback routes. Engineering and audit only.

---

## 4 · The primary UX principle

The founder must never need to know these words:

```
Planner · Mission Control · provider adapter · UUID · step id
crit_1 · evidence id · capability name · retry count · JSON
provider ladder · Reasoning.Transform · input_bindings
```

**Bad**

```
Reasoning.Transform: MATCHED
Evidence: 7928c...
crit_2 unresolved
Browser.Navigate retry=2
```

**Good**

```
I confirmed the first requirement.
I still need reliable evidence for Sunday availability,
so I'm checking another source.
```

The backend already refuses to leak most of this: the founder-facing
sentence builders (`_founder_failure_sentence`, `_decision_sentence`) are
written to hand over a sentence, never a stack trace, and the live
acceptance fixtures assert that no UUIDs, no `crit_`/`req_` ids and no
raw JSON reach the founder's reply. **Do not reintroduce them in the
presentation layer.**

---

## 5 · Mission states — what to design

The left column is the **UX concept** the brief asked for. The right is
what the backend actually reports. Where they do not line up, that is
stated rather than papered over.

| UX concept | Backend truth | Founder sees | Founder can | Never asked to | Continues alone |
|---|---|---|---|---|---|
| IDLE | *(front-end only; no mission)* | greeting, composer, recent missions | start anything | — | n/a |
| UNDERSTANDING | `understanding` | "Reading your request" | wait / cancel | explain again | yes |
| PLANNING | `planning` | "Working out the steps" | wait | approve a plan | yes |
| WORKING | `executing` | what is being done now | wait | pick a tool | yes |
| REASONING | `executing` + `current_capability` is a reasoning capability | "Thinking about what it found" | wait | choose a model | yes |
| WAITING FOR EXTERNAL SYSTEM | `executing` / `observing`, elapsed vs `timeout_ms` | "Waiting for the site to respond" | wait | fix the site | yes |
| VERIFYING | `verifying` | "Checking the result" | wait | confirm it worked | yes |
| MORE RESEARCH NEEDED | **GAP** — real in the Brain, not in `as_dict()` (§8) | "Checking another source" | wait | supply the source | yes |
| RECOVERING | `recovering` | "That route didn't work — trying another" | wait | choose a route | yes |
| REPLANNING | `planning` again, `attempt` > 1 | same as recovering | wait | re-explain | yes |
| WAITING FOR FOUNDER APPROVAL | `awaiting_approval` + `approval_kind = permission` | the specific permission, with context | **Approve / Decline** | — | **no** |
| WAITING FOR FOUNDER INFORMATION | `awaiting_clarification` + `pending_clarification` | the question, in their own terms | answer | guess | **no** |
| CHECKPOINT | `awaiting_approval` + `approval_kind = founder_checkpoint` | what the work produced so far | **Continue / Stop** | — | **no** |
| COMPLETED | `completed` (+ `requires_founder_completion`) | the result and what was verified | accept, open artifacts | — | done |
| PARTIALLY COMPLETED | `completed` with unresolved requirements | what was and was not established | accept, ask for more | — | done |
| TRUTHFULLY BLOCKED | `blocked` | why, in plain words | decide next step | fix internals | **no** |
| FAILED | `failed` + `errors` | what stopped it | retry, rephrase | read a trace | **no** |
| STOPPED / CANCELLED | **GAP** — no cancel path in the bridge (§8) | — | — | — | — |

---

## 6 · Autonomy must be visible — and quiet

This is the differentiator. When Kalpavriksha preserves verified work,
finds missing evidence, changes route, recovers, falls back to another
provider or discovers a source nobody named, the founder should be able
to *see that it did* — without theatre.

Useful progress, not an animation of a brain thinking:

```
First source checked
  ✓ Accessibility confirmed

Sunday hours not established
  → Checking another source

Second source found
  ✓ Sunday hours confirmed

  → Verifying final match
```

Forbidden: pulsing "AI is thinking" states, fake token streams, agent
swarm visualisations, confidence meters that no backend computes.

---

## 7 · Three founder questions that must never look alike

The backend distinguishes these and the UI must not teach the founder
that they are the same thing. `approval_kind` carries which one it is
(`mission_control/approvals.py`).

### CONTINUE / STOP — `approval_kind = "founder_checkpoint"`

The objective itself said *"show me before you continue."* The founder is
reviewing work, not granting anything. Answering Continue **grants no
capability authority and changes no risk tier**.
Buttons: **Continue** · **Stop**. Neutral treatment.

### APPROVE / DECLINE — `approval_kind = "permission"`

Policy. Something destructive, costly, or privacy-affecting is gated.
Answering yes can create real Permission System authority.
Buttons: **Approve** · **Decline**. Weightier treatment; show
`approval_context` (why) and `approval_preview` (what).

### ANSWER REQUESTED — `pending_clarification`

Information only the founder has. Not a decision, not a permission.
An input, with the question in the founder's own terms.

> Visually: three distinct card families. If a founder learns to click
> the same-looking button in all three, the permission boundary has been
> destroyed in the presentation layer.

---

## 8 · Founder interruption policy

Kalpavriksha interrupts **rarely, and only for**:

```
money or a paid action        credentials / login / 2FA
physical intervention          legal, signature, identity authority
irreversible high-impact action
information only the founder holds
a frozen architectural decision
final acceptance
genuinely ambiguous intent
```

Everything else appears as autonomous progress or recovery. Do not design
a UI that invites "what should I do?" cards — the product's own recovery
loop is built to avoid asking.

---

## 9 · Completion UX

A finished mission shows **what was achieved, what was verified, the key
result, where any artifact is, and any real limitation.**

Not `Done.` And never — this shipped and was fixed on 29 Aug —
a correct answer immediately followed by *"That didn't complete."*
Completion must project one canonical truth. The backend now suppresses
the contradiction; do not reintroduce it by stacking a success card and
an error card in the same view.

Real completion text the product produces today:

```
1 of what I found meets everything you asked for:
  - Ashcombe Repair Workshop
I ruled out 2: Brindle Repair Workshop (a mandatory criterion was not
met); Calder Repair Workshop (a mandatory criterion was not met)
```

---

## 10 · Partial and blocked outcomes

Truthful incompleteness is a **first-class, respectable** outcome and must
not be styled like a crash.

```
I confirmed 2 of 3 requirements.
I could not verify the third: the source is currently blocking
automated access.
I did not guess.
```

Distinguish, with different treatments:

| Class | Backend signal today |
|---|---|
| EXTERNAL LIMITATION | error text naming a site/timeout/anti-bot |
| INSUFFICIENT EVIDENCE | deliberation state `insufficient_evidence` — **GAP: not in `as_dict()`** |
| PROVIDER UNAVAILABLE | provider result `UNAVAILABLE` — internal, not surfaced |
| PERMISSION REQUIRED | `awaiting_approval` |
| SYSTEM ERROR | `failed` with `errors` |

---

## 11 · Providers

Providers are implementation detail. The default surface should say:

```
Using another reasoning route…
```

not `Kimi unavailable → OpenRouter`. Provider names belong in Level 5,
or in Level 1 **only** when they affect cost, privacy, or a founder
choice.

**A provider failing is not a mission failing** when Kalpavriksha
recovers — and it does. Live, all of 29 Aug, one desktop provider
answered every request with a capacity banner; it was detected, rejected,
excluded for that attempt, and the ladder moved on. That should read as
composure, not alarm.

---

## 12 · The two browser lanes — do not merge them visually

| Lane | For | Mechanism |
|---|---|---|
| **Ordinary automation** | public pages, forms, scraping | **Playwright**, via `BrowserSessionManager` |
| **Trusted Web AI** | an AI *website* used as a reasoning provider | the founder's **real signed-in Chrome/Comet**, via the Desktop Executive |

Never design an affordance like *"use my logged-in Chrome to get past
this."* When ordinary automation meets bot detection, that is a truthful
external limitation. Architectural guards in
`tests/test_browser_lane_separation.py` fail if code tries to blur this;
the UI must not blur it either.

---

## 13 · Progress UX

No fabricated progress bars. Two honest sources exist:

1. `current_step` / `total_steps` — real, already in `as_dict()`.
2. Requirement-level standing — real in the Brain (`MissionProgress`:
   satisfied / unresolved / failed routes) but **not currently exposed**
   (§8 gap).

Design the requirement checklist against (2) and mark it
**BACKEND CONTRACT REQUIRED** until exposed. Use (1) meanwhile.

---

## 14 · Memory and persistence

A provider's chat history is **transport**, not Kalpavriksha's memory.
Kalpavriksha's own state is Founder Intent, requirements, Evidence and
MissionProgress. Never present a provider conversation as the product's
memory.

Durable audit across a restart is real and proven
(`scripts/live_acceptance/u1_real_restart.py`). Autonomous resumption of
an *interrupted objective* is **not** built — do not design an affordance
that implies it.

Do not surface raw persistence or event logs by default.

---

## 15 · Artifacts

Checked at this HEAD: **there is no artifact contract.** The bridge
returns no artifact list, and a written file's path exists only inside
Filesystem evidence (`target_path`, `target_exists`, `target_size_bytes`,
`content_text_sha256`).

**Do not parse file paths out of model prose.** An artifact card requires
explicit backend data:

```
name · type · path/reference · verification state · available actions
```

Actions (`Open`, `Show in Folder`, `Save As`, `Copy path`) require a
backend contract that does not exist yet. Classification:
**BACKEND CONTRACT MISSING.** Design the card; mark it FUTURE.

---

## 16 · Visual character

```
calm · high-trust · intelligent · minimal · executive
modern · precise · warm but not playful
```

Avoid: gaming/crypto dashboards, cyberpunk neon, terminal-first,
mascots, constant motion, telemetry everywhere.

The existing token set (Founder Dark, `--c-void #05070A` through
`--c-ink #E9EFF5`, four state colours) is a good foundation and traces to
Product Veda v1.0. Extend it into a real system: elevation, radius,
iconography, motion, and semantic state colours for
`verified / unverified / attention / failure / founder-action-required`.

---

## 17 · Home / idle

```
greeting · composer · recent meaningful missions
system readiness (one line) · important alerts only
```

No technical metrics in idle space. The current shell already has the
tree canvas, greeting, mic, mode switch (LOCAL / AI MODE / BOTH) and
composer — a good skeleton to redesign around.

---

## 18 · Window and responsiveness

Desktop Founder Edition. Design for a normal window, maximised, and a
smaller window. Requirements: composer always reachable; long
conversations and long missions scroll without losing the mission
summary; cards never block the conversation. **Text selection and copy
must keep working** — the composer is `contenteditable` and messages are
selectable today. Not mobile-first.

---

## 19 · Accessibility

Keyboard navigation and visible focus · text selection · contrast ·
font sizing · screen-reader semantics where practical · never
colour-alone state · large targets · reduced-motion respected (the tree
canvas and any progress motion must honour `prefers-reduced-motion`).

---

## 20 · Component inventory

For each: purpose · data · interactions · states · backend support.

| Component | Data it needs | Backend today |
|---|---|---|
| `FounderComposer` | — | `submit_objective` ✅ |
| `MissionHeader` | `objective` | ✅ |
| `MissionStateChip` | `status` → `workState.js` language | ✅ |
| `ProgressSummary` | `current_step`/`total_steps` | ✅ steps · ❌ requirements |
| `RequirementChecklist` | satisfied / unresolved | ❌ **contract required** |
| `ActivityLine` | `message` | ✅ |
| `EvidenceCard` | verdict + observation | ⚠ internal only |
| `VerifiedResultCard` | `result`, `message` | ✅ |
| `RecoveryNotice` | `status = recovering`, `attempt` | ✅ shallow · ❌ *why* |
| `ApprovalCard` | `approval_kind = permission` + preview/context | ✅ |
| `CheckpointCard` | `approval_kind = founder_checkpoint` | ✅ |
| `ClarificationCard` | `pending_clarification` | ✅ |
| `ArtifactCard` | name/type/path/state | ❌ **contract missing** |
| `FailureCard` | `errors`, `status = failed` | ✅ |
| `ProviderFallbackNotice` | provider swap | ❌ not surfaced |
| `CompletionCard` | `requires_founder_completion`, `completion_id` | ✅ |
| `AdvancedDiagnosticsDrawer` | ids, capability, timings | ✅ partial |
| `MissionHistoryItem` | past missions | ⚠ dashboard only |
| `DecisionCard` | shortlist / rejected / unresolved | ❌ **exists, not exposed** |

---

## 21 · Screen inventory

```
A · Main founder workspace (idle)
B · Active mission
C · Reasoning / research mission        ← the centrepiece
D · Approval required (three variants: permission, checkpoint, question)
E · Recovery / replan
F · Successful completion
G · Truthfully blocked outcome
H · Mission history
I · Evidence / details drawer
J · System readiness
```

Ten screens. Do not invent more to look thorough.

---

## 22 · Centrepiece storyboard — the demo journey

This is a **real, passing** mission
(`scripts/live_acceptance/demo_centrepiece.py`). The founder names one
page. That page cannot answer the question.

**Objective:** *"Which community repair workshops accept laptops and are
also open on Saturday? Start from <directory page>"*

| # | System truth | Founder-visible state | Founder-visible copy | Interaction |
|---|---|---|---|---|
| 1 | Mission admitted, requirements derived | UNDERSTANDING | "Reading your request" | none |
| 2 | Browser session, navigate, read page text | WORKING | "Checking the first source" | none |
| 3 | Evidence recorded; one criterion established, one not | REASONING → trace opens | "I confirmed which workshops accept laptops. Saturday opening isn't established yet." | expand trace |
| 4 | `more_research`; a link the founder never named is chosen from Evidence | MORE RESEARCH NEEDED | "Checking another source" | none |
| 5 | That route returns 503 | RECOVERING | "That source wasn't usable — trying another route." | **none — this is the point** |
| 6 | Second source read; earlier Evidence preserved across the replan | WORKING | "Second source found ✓ Saturday hours confirmed" | none |
| 7 | Deliberation: one candidate clears both criteria; two rejected with reasons | VERIFYING | "Verifying the final match" | none |
| 8 | `decided`, shortlist of one | COMPLETED | "Ashcombe Repair Workshop matches both requirements." + the two rejections and why | expand evidence |

**Moment 5 is the whole demo.** A route died and the founder was not
asked anything. Design it as composure — a single quiet line — not an
error.

**Moment 3 is the second most important.** It is the machine saying *I
know what I don't know yet*, which is the thing that makes it feel like
an intelligence rather than a script.

Nothing about repair workshops exists in production. Take away either
page and the mission says so truthfully instead of guessing.

---

## 23 · Current vs future matrix

| UX feature | Backend support | UI support | Gap | Recommendation |
|---|---|---|---|---|
| Conversation | full | yes | — | **READY TO DESIGN** |
| Mission state (12 states) | full | yes | — | **READY TO DESIGN** |
| Activity line | `message` | yes | — | **READY TO DESIGN** |
| Step progress | `current_step`/`total_steps` | yes | — | **READY TO DESIGN** |
| Verified result | `result` + `message` | partial | — | **READY TO IMPLEMENT** |
| Completion acceptance | `confirm_completion` | yes | — | **READY TO DESIGN** |
| Approval (permission) | `approval_kind`, preview, context | yes | — | **READY TO DESIGN** |
| Checkpoint (continue/stop) | `approval_kind` | partial | distinct styling | **READY TO IMPLEMENT** |
| Clarification | `pending_clarification` | yes | — | **READY TO DESIGN** |
| Failure | `errors`, `failed` | yes | classify kinds | **READY TO IMPLEMENT** |
| Mode (local/AI/both) | `selected_mode`, `effective_mode`, `mode_reason` | partial | explain divergence | **READY TO IMPLEMENT** |
| **Requirement checklist** | `MissionProgress` exists | none | not in `as_dict()` | **BACKEND WIRING REQUIRED** |
| **Decision / shortlist card** | `status.deliberation` exists | none | not in `as_dict()` | **BACKEND WIRING REQUIRED** |
| **Recovery reason** | `status.recovery` exists | none | not in `as_dict()` | **BACKEND WIRING REQUIRED** |
| **More-research signal** | real in the loop | none | no event | **BACKEND WIRING REQUIRED** |
| Evidence inspection | Evidence per task | none | no bridge call | **BACKEND CONTRACT REQUIRED** |
| Provider fallback notice | internal only | none | no event | **BACKEND CONTRACT REQUIRED** |
| Artifact cards | none | none | no contract | **BACKEND CONTRACT REQUIRED** |
| Mission history | dashboard read model | partial | — | **READY TO IMPLEMENT** |
| Cancel / stop a running mission | none | none | no bridge call | **BACKEND CONTRACT REQUIRED** |
| Objective resume after restart | audit only | none | not built | **POST-DEMO / FUTURE** |
| Self-development | none | none | — | **POST-DEMO / FUTURE** |

### The four wiring gaps worth naming to engineering first

`ExecutionStatus` **already carries** `deliberation` and `recovery` as
declared fields — they are simply **absent from `as_dict()`**, so the UI
cannot see them. Adding them is a small, contained change and it unlocks
Level 3, Level 4, the requirement checklist and the decision card at
once. **This is the highest-value backend request in this document.**

---

## 24 · What you may change freely

Layout · spacing · typography · hierarchy · cards · icons · navigation ·
motion · empty states · evidence presentation · mission timeline ·
completion presentation.

## 25 · What must not change without architectural review

```
Intent ownership          Planner ownership        Mission Control lifecycle
Verification semantics    Evidence semantics       permission authority
financial authority       provider routing         Browser lane ownership
recovery semantics        completion truth         sensitivity / privacy
founder interruption policy
```

The UI **consumes** these contracts. It does not redefine them.

## 26 · No fake intelligence

Forbidden: fake confidence scores, fake learning progress, fake "AI is
thinking", fake requirement completion, fake real-time progress, fake
memory, fake agent swarms, fake self-improvement, fake provider health.

Every visible status must come from production state, or be clearly
labelled a future design concept.

---

## 27 · Reference material in this repository

| What | Path |
|---|---|
| The read model you consume | `src/master_agent/missions/execution_status.py` |
| Existing status→language layer | `desktop_app/web/js/workState.js` |
| Bridge composition | `kalpavriksha_desktop.py` (`create_window(...)`) |
| Approval vs checkpoint | `src/master_agent/mission_control/approvals.py` |
| Why model prose is not evidence | `src/master_agent/plugins/reasoning_gateway.py` |
| Verification independence | `docs/adr/0011-verification-as-independent-subsystem.md` |
| Dashboard read-model discipline | `docs/adr/0016-dashboard-data-contract.md` |
| Approval workflow | `docs/adr/0020-founder-approval-workflow.md` |
| Objective state vocabulary | `docs/adr/0021-objective-state-vocabulary.md` |
| Intent, clarification, admission | `docs/adr/0024-intent-resolution-clarification-and-planner-admission.md` |
| Semantic correspondence | `docs/adr/0026-brain-semantic-intelligence-and-correspondence.md` |
| Deliberation and decisions | `docs/adr/0027-brain-deliberative-intelligence-and-decision-utility.md` |
| Demo journeys and copy | `docs/demo/DEMO_30AUG_RUNBOOK.md` |
| What is proven, with numbers | `docs/audits/DEMO_30AUG_EVIDENCE.md` |
| Earlier UI/UX concepts | `VEDRA_PROJECT/01_Assets/UI-UX/` |

**Screenshots:** none of the *current* Founder Edition build exist in the
repository. `VEDRA_PROJECT/01_Assets/UI-UX/` holds earlier HTML concepts
(`UX_01_First_Screen_v2.html`, `UX_02_Approval_Queue.html`,
`UX_03_Founder_Dashboard.html`, `UX_04_Demo_Path_90sec.html`) — treat
them as history, not as the current build. Current-package screenshots
will be added after founder acceptance. None were manufactured for this
document.

---

## 28 · Hyper Agent's next mission

Return, in this order:

1. UX audit of the current Founder Edition
2. Proposed information architecture
3. Visual direction
4. Component system (tokens → primitives → composites)
5. Key screens (the ten in §21)
6. Centrepiece storyboard (§22), visually
7. State, error and approval designs — including the three distinct
   founder-question families (§7)
8. Interaction specification
9. Accessibility notes
10. Implementation handoff
11. Backend-contract gaps you hit, beyond those in §23
12. Prioritised build sequence

**Suggested priority**

```
P0  founder workspace
P0  mission / progress
P0  verified completion
P0  recovery
P0  approvals (all three families)
P1  history / evidence
P1  artifacts
P2  advanced diagnostics
```

**Do not implement code until the proposed design is reviewed.**

---

## 29 · The one sentence to keep

If a single principle survives the redesign, make it this one, already
written into `workState.js` by your own earlier work:

> **Show what is being done, not what state the machine is in.**
