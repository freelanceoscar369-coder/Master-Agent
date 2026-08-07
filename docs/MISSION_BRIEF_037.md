# Mission Brief 037 — Planner Integration

**Status:** Implemented
**Date:** 2026-07-31
**Depends on:** MB023 (Mission Control), MB024 (Runtime), MB032 (Broker
wiring), MB034 (Memory), MB035 (Verifier), MB036 (Planner)
**Frozen files modified:** none. No ADR. No Constitution change.

---

## 1. What this brief is

MB036 built a Planner and wired it to nothing. MB037 puts it in the line:

```
Founder -> Planner -> MissionPlan -> Mission Control -> Executives
        -> Broker -> Providers -> Verifier -> Evidence -> Memory
```

The hierarchy is unchanged. Nothing here decomposes, selects, verifies or
remembers — each of those already has exactly one owner, and this brief's
whole job was to put them in a row.

## 2. The finding that shaped it

**Almost every guarantee the brief asks for already existed, unconnected.**

| Asked for | Where it already lived |
|---|---|
| Dependency-ordered execution | Mission Control's Task Dispatcher (MB023) |
| Verify each step before it completes | `RuntimeEngine._verify()` (MB024/MB035) |
| Never unlock a dependent step before verification | The Runtime calls `task_completed()` *after* a matched verdict |
| Evidence recorded per step | `Task.evidence_id` (MB023) |
| Lessons from failure | `MemoryService.attach_to()` on `OBJECTIVE_FAILED` (MB034) |
| Somewhere to put an ExpectedOutcome | **`Task.expected_outcome`, added by MB023** |

That last row is the one worth pausing on. MB023 gave `Task` a field it
had no producer for, with a comment naming Constitution §3.2 and the
Planner that did not exist yet. MB036 built the producer. MB037 is the
arrow between them — and it is a **1:1 field copy**, because the seam was
cut for exactly this three briefs ago.

So `missions/` is small, and that is the result, not a shortcut.

## 3. What shipped

| Module | What it owns |
|---|---|
| `missions/translation.py` | `MissionPlan` -> `Objective`. 1:1, lossless, and the gate that rejects an incomplete plan. |
| `missions/service.py` | `MissionService.start()` — the one path from a founder objective to submitted work. |
| `missions/history.py` | The durable record: what was planned, what happened, and replay. |

Plus: `Step` gained `priority` and `estimated_complexity`; the Dashboard
gained a CURRENT MISSION panel; the console turns any unrecognised line
into an objective; `cli.py` stopped producing `MissionPlan`s.

## 4. The decisions worth arguing with

### 4.1 Translation, not a second work vocabulary

The Runtime, Mission Control and the Dispatcher have been frozen since
MB025 and this brief allows zero frozen files. Teaching them to read a
`MissionPlan` would need a ratified exception and would buy nothing —
`Task` already has `capability`, `payload`, `depends_on` and
`expected_outcome`. Translation is not a workaround; it is the seam being
used.

Deliverable 5 ("execution consumes the plan without modification, and
never infers missing information") is a property of that module: it
copies, it never fills in, and an incomplete plan is **rejected before an
`Objective` exists** — so there is no path on which execution could have
inferred the missing part.

### 4.2 The gate judges fields, not producers

`incomplete_steps()` refuses a plan whose step lacks a capability,
inputs, an expected outcome, or dependency information. MB036's Planner
can never fail those checks — its own validator is stricter. That is not
a reason to skip them: this is the gate for *any* producer, and the day a
second one appears the guarantee has to already be here rather than in
the first one's docstring. A hand-built plan is held to the same rules,
asserted by a test that hands in a `Step`-shaped object from elsewhere.

"Inputs" means **the field is present and is a mapping** — not that it is
non-empty. `Desktop.ScanMachine` takes no arguments, and a rule that
forced a payload would make the Planner invent one, which is exactly the
guessing Deliverable 9 forbids.

### 4.3 Priority and complexity are descriptive, never directive

The brief adds both to what a Planner produces. Both are closed
vocabularies (`low|normal|high|critical`, `trivial|small|moderate|large`),
both default to the middle of their scale, and **neither reaches `Task`**.

A Planner that could reorder execution by labelling a step `critical`
would own lifecycle, which the Constitution gives to Mission Control
alone. `depends_on` decides order and nothing else does — told to the
model in the prompt, enforced in the parser, and asserted by a test that
puts a `critical` step behind a `low` one and checks the `low` one runs
first.

Both are **optional in the plan document**: a plan written against
MB036's shape is still a valid plan. A *wrong* value is a refusal,
because silently substituting the default would tell a founder a step is
`normal` when the provider said `urgent` — a lie about what was planned.

### 4.4 The history observes; it never drives

Every field in a `PlanRecord` is filled by a **subscriber**, per event
type, on the bus MB034 already uses. Nothing in `missions/history.py`
dispatches, unlocks, orders or retries — a history that could influence
execution would be a second orchestration authority wearing a notebook.
An architecture test parses the module and fails on any call to
`dispatch_ready`, `task_started`, `task_completed`, `task_failed` or
`run_once`.

### 4.5 Replay re-reads; it cannot re-run

`replay()` reconstructs a mission from recorded evidence alone. The
strongest form of that claim is not a docstring but the import list:
`missions/history.py` imports nothing from `providers/`,
`ai_infrastructure/`, `plugins/`, `broker/`, `httpx`, `urllib`, `socket`
or `subprocess`. There is nothing in reach that *could* contact a
provider. A test asserts it.

Everything stored is JSON-plain, so an `ExpectedOutcome` is recorded as
its description and its checks' descriptions rather than as the live
object — a record has to survive being read by a process that does not
import `verification/`.

### 4.6 The one thing the pipeline writes to Memory

A **refused** plan publishes no Mission Control event at all, because no
objective was ever submitted. So the failure MB034's subscriptions can
never learn about is the one `MissionService` records itself: the plan
that did not happen. Every other lesson still comes from the
subscriptions that already existed, and a test asserts a completed
mission is remembered exactly once — not once per subscriber, now that
two of them watch the same events.

### 4.7 `cli.py` stopped pretending to plan

Until now `master-agent-demo` built a one-step `MissionPlan` for every
recognised sentence, which made it a second producer of plan vocabulary.
It was never planning — a regex cannot decompose a goal, state a
dependency, or name an Expected Outcome — so what it produces is now
called what it is: a `CapabilityCall`.

**All 66 of `test_cli_session.py`'s assertions pass unchanged**, which is
the evidence that this was a rename of a misdescribed thing rather than a
behaviour change. An AST test over the whole `src/` tree now asserts that
`planner/parsing.py` is the only module that constructs a `MissionPlan`
or a `Step`.

### 4.8 One CURRENT MISSION slot, not two

The new plan panel and MB029's mission panel answer the same founder
question. Showing both said it twice and pushed the founder page to 64
lines against its 60-line budget. So they share one slot: the step-level
answer when a plan exists, MB029's summary when it does not (the
launcher's own machine scan is an objective nobody planned, and it must
not become invisible).

The step list is capped at five rows and **says what it is not showing** —
a list that quietly stops reads as a shorter plan.

**Never internal LLM reasoning.** `PlanView` and `PlanPanelData` have no
field for a prompt, a reply, or a provider's reasoning. A test asserts
the absence of those field names, because a view model with nowhere to
put it cannot leak it by accident when the panel grows.

## 5. What was NOT built, and why

**Pause, resume and cancel do not exist — on any layer.**

The brief assigns them to Mission Control. Mission Control publishes
`submit_objective`, `restore_objective`, `dispatch_ready`, `ready_tasks`,
`task_started/completed/failed`, the approval verbs and `founder_state`.
There is no pause, no resume, no cancel, and no `TaskState` for a paused
task.

Building them needs one of two things, and this brief forbids both:

1. **Add them to Mission Control** — edits frozen `mission_control/` and
   `dispatcher.py`. The brief says *zero frozen files, no ADR*.
2. **Build them outside** — a controller that gates dispatch is a second
   scheduler. The brief says *Mission Control remains the single
   orchestration authority*.

The brief's own final instruction resolves it: *"If implementation
pressure ever conflicts with the Constitution, the Constitution wins."*
So they are absent, deliberately, and
`test_missions_lifecycle.py::test_pause_resume_and_cancel_do_not_exist_anywhere`
says so out loud — it fails the day somebody adds one, which is where the
conversation restarts with a ratified ADR.

The console does not advertise a verb that cannot work.

**Checkpoint, resume, state and recovery *do* work**, because MB025 built
them: a plan and every verdict it earned survive a restart, and a mission
killed mid-flight leaves a readable record (the history is written as each
event arrives, not at the end).

## 6. Running it live

Through the real launcher (`build_system`), the real machine scan, the
real Broker, the real `OllamaProvider` against the founder's own daemon,
the real Runtime and the real Memory.

**The wiring is confirmed.** The boot report gains its new step —
`[ok] Planner: 26 capability(ies) to plan with; history watching 6 event
type(s)` — the console accepts a plain sentence as an objective, and the
whole path is exercised.

### Finding 1 — a founder was told *that* it failed, not *why*

First live run: `console replies: no plan: the provider could not answer`.

That is all the founder got. The actual cause — the provider timing out
— was sitting in `PlanRefusal.detail`, a field the console does not
render. A refusal that does not say what to change is barely better than
a silent failure, and it violates the discipline MB033 set when it made a
missing model report itself *with the list of models that are installed*.

Fixed: the reason now carries the cause in the sentence a founder
actually reads (`no plan: the provider could not answer (no answer within
540s)`), with the detail kept alongside for the record. This is a real
defect that only running it could surface — every unit test asserted the
refusal *code*, which was correct throughout.

### Finding 2 — MB036's Finding 3, worse

The 540 s timeout that MB036 flagged is not enough for MB037's prompt
either. The planning prompt now carries the founder's **real
26-capability catalogue**, and `gemma4:latest` on this laptop's CPU does
not finish inside it. MB036 recorded this as "the default is wrong for
planning"; MB037 shows it is wrong by a wider margin than the first
measurement suggested, because the catalogue grew.

A timeout is deliberately never retried (MB033), so this is a clean
refusal rather than a hang — but it is the single thing most likely to
make a founder think the system does not work, and it is now the
highest-priority item after the input-schema gap.

### The run that went all the way through

Objective: *"Create a folder called employee_api and write a README.md
inside it describing a REST API for employee management."*

`gemma4:latest` produced a genuinely good plan:

```
console replies: planned 2 step(s) - running now (mission 2f01a0e2)

  step_1: Filesystem.CreateFolder [high/trivial]
      after:   -
      expects: The folder 'employee_api' is created.
  step_2: Filesystem.WriteFile   [high/small]
      after:   ['step_1']
      expects: The file README.md is written into that folder.
```

— the right two capabilities out of twenty-six, the dependency in the
right direction, priority and complexity on each, an expectation on each,
and a README body with real endpoint documentation in it.

Then execution, through the real Runtime:

```
  cycle 0: approving Filesystem.CreateFolder      <- Rule 5
  cycle 0: handled=step_1  [step_1 dispatched, step_2 created]
  cycle 1: handled=step_1  [step_1 failed,     step_2 blocked]

  step_1: failed   errors=['missing required parameter: name']
  step_2: blocked
  history state: failed
```

**Every guarantee in the brief held, including the ones that only show up
when something goes wrong:**

- The task **waited for founder approval** before touching the disk
  (Rule 5, MB028.1) — nothing ran unapproved.
- `step_1` **failed** rather than half-succeeding.
- `step_2` was **BLOCKED and never dispatched** — the dependent step did
  not unlock on unverified work, which is the property the whole brief
  turns on.
- **Nothing was repaired.** The Planner was not asked again, the payload
  was not adjusted, the expectation was not relaxed.
- The failure reached the history, the Dashboard and Memory.

### Finding 3 — and it failed for the reason MB036 predicted

`missing required parameter: name`. The Planner wrote `{"path":
"employee_api"}`; `CreateFolder` requires `name`. That is **MB036 Finding
4, in production**: nothing publishes what arguments a capability takes,
so the model guesses, and a plan that reads perfectly does not run.

This is the clearest possible argument for the input-schema work. The
Planner, the Broker, the approval boundary, the Dispatcher, the Verifier,
the history and Memory all did their jobs correctly — and the mission
still failed, on the one fact nobody has published.

### Finding 4 — "waiting on step_1" was a lie once step_1 failed

The founder page showed `step_2 - waiting on make_folder` after
`make_folder` had already failed. True, and misleading: a founder reading
it would keep waiting for something that will never happen. Mission
Control already marks the task `BLOCKED`; the founder page had no word
for it.

Fixed: a step whose dependency has failed now reads `will not run -
make_folder failed`. Both states are real and they are now distinct, the
same distinction MB029 insisted on for mission status and MB035 for
`not checked` versus `not matched`.

## 7. Numbers

- **275 new tests** (the brief asked for 250+), **3203 passing**, 1
  skipped, zero regressions.
- **100% statement coverage** of all three new modules.
- **Zero frozen files modified**; `RATIFIED_EXCEPTIONS` unchanged at 7.
- Ruff clean across everything MB037 touched.
- Three tests were updated rather than added: two console tests whose
  asserted contract Deliverable 6 deliberately changes (an unrecognised
  line is now an objective, not an error — the guarantee they existed
  for, *a typo must never decide an approval*, is unchanged and still
  asserted), and one dashboard line-budget test.

## 8. Defects found while building

1. **`PanelStatus()` defaults to available**, so a snapshot with no plan
   data rendered as a live plan showing `0/0 steps` — `0` standing in for
   "unknown", which ADR-0016 exists to prevent. Fixed at the read model:
   `PlanPanelData` defaults to absent, because a plan does not exist until
   somebody asks for something.
2. **The same default then hid a real plan**, because `_collect_plan()`
   built `PlanPanelData` without passing a status when a record *was*
   found. Caught by the dashboard tests immediately.
3. **Two registries silently break dispatch.** A Planner given a
   catalogue that is not Mission Control's own registry produces plans
   naming capabilities the Dispatcher has never heard of. The launcher
   always passed `mission_control.capabilities`; a test fixture did not,
   and nothing ran. The fixture was wrong, but it is a real trap for any
   future wiring, so `test_the_prompt_carries_the_real_capability_registry`
   now asserts the two are the same list.
4. **A refusal that did not say why** — §6 Finding 1, found live.
   Every unit test asserted the refusal *code* and was right to; none
   asserted the *sentence*, so a founder-facing gap survived a fully
   green suite. There is now a test for the sentence.
5. **"Waiting on X" survived X failing** — §6 Finding 4, found live.
   Fixed.
6. **`_current_objective_id` never advances** (not fixed — frozen file).
   `submit_objective()` sets it only when it is `None`, so after the
   launcher's boot machine-scan every later mission leaves it pointing at
   the scan, and `founder_state()` describes a finished scan forever. The
   founder page is unaffected — MB037's panel reads the plan history and
   replaces the older mission panel whenever a plan exists — but
   `founder_state()` is a published contract, and the fix is in frozen
   `mission_control/`. Recorded in the backlog, same posture MB026 took
   toward `count_events()`.

## 9. What this unblocks, and what it leaves

**Unblocked**

- A founder types a sentence and Kalpavriksha plans, runs, verifies and
  remembers it. That is the product.
- Objectives about Kalpavriksha itself now have a path to execution.

**Left open**

- **Pause / resume / cancel** (§5). Needs a ratified ADR.
- **Nothing publishes a capability's arguments or its result shape**
  (MB036 Findings 4 and 5). `CapabilityManifest.input_schema` and
  `output_schema` are declared in frozen `plugins/base.py` and populated
  by nothing. This is the difference between a plan that reads correctly
  and a plan that runs, and it is now the highest-value item in the
  backlog.
- **Adaptive re-planning.** Deliberately not built: a Planner that
  revises a plan at the moment the system has just shown it got something
  wrong needs its own safety argument.
- **A timeout that fits the prompt** (MB036 Finding 3).
