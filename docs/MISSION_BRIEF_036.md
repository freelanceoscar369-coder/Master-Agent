# Mission Brief 036 — The Planner

**Status:** Implemented
**Date:** 2026-07-30
**Depends on:** MB031/MB032 (the Broker), MB033 (execution), MB035 (the
Generated Text Verifier)
**Frozen files modified:** none. No ADR was needed.

---

## 1. Why this, now

MB035 shipped a Verifier that judges an answer against an
`ExpectedOutcome` **stated before the answer arrived**. That contract has
always named the thing that is supposed to state one — from
`verification/evidence.py`, frozen since ADR-0011:

> `ExpectedOutcome` — *"What a Planner (or, until the real Planner exists,
> whatever hand-builds a Step) attaches to a Step so Verification has
> something concrete to compare against."*

Nothing did. The consequences were spread across three briefs and all
looked like separate gaps:

- MB033's **Prompt Cache** fills only for callers that state an
  expectation.
- MB035's **Prompt Library** writer, the same.
- Constitution **§3.2** — every Step names an Expected Outcome — was a
  promise with no mechanism behind it.

They are one gap. And for the north star specifically: Kalpavriksha can
decide *which* AI (MB032), *run* it (MB033) and *check* it (MB035), but
every objective it executes was decomposed by a human. **Decomposition is
the faculty between "runs work" and "improves itself."** A system that
cannot turn a goal into steps cannot be handed a goal about itself.

## 2. What shipped

```
    Intent ─> catalogue ─> prompt ─┐
                                   v
             ExpectedOutcome ─> PromptExecutor ─> Broker ─> provider
                                   │
                        Evidence ──┴── observation["json"]
                                   │
                              validate() ─> MissionPlan
```

Seven modules in `planner/`, a package that until now held one
`NotImplementedError`:

| Module | What it owns |
|---|---|
| `plan.py` | The vocabulary: `Intent`, `Step`, `MissionPlan`, plus `PlanRefusal`/`PlanOutcome` and eleven refusal codes. `Step` gains `expected_outcome`. |
| `catalogue.py` | What may appear in a plan. A port needing one method, `all()`. |
| `prompting.py` | The request and the expectation, written in the same breath. |
| `outcomes.py` | A step's stated `success` → an `ExpectedOutcome`, over a closed vocabulary. |
| `parsing.py` | Structural validation. No parser — see §4.2. |
| `planner.py` | The `Planner`. |
| `__init__.py` | Exports. |

`Intent`, `Step` and `MissionPlan` moved from `planner.py` to `plan.py`
and are re-exported, so the Orchestrator, `cli.py` and two test modules
import them from exactly where they always did. Nothing that consumed
them changed.

## 3. What it is *not*

**It is not wired into `cli.py`.** The regex `parse_intent()` /
`build_plan()` stand-in still runs the conversational path. This is the
MB031→MB032 rhythm on purpose: build the engine, prove it, wire it in a
brief that can weigh `test_cli_session.py`'s hundred-assertion regression
contract properly. Wiring is MB037.

**It does not solve semantic correctness.** The expectations it emits are
structural and they are over text. They catch a blank result, a refusal,
a truncation, a wrong shape. They cannot catch a step that reports
success and did the wrong thing. ADR-0017 Decision 5 named that gap;
MB035 inherited it; MB036 does not close it either. A step whose
expectation passes is **checked**, not **correct**.

## 4. The decisions worth arguing with

### 4.1 §3.2 is enforced at the door it is about, not in the type

`Step.expected_outcome` is `ExpectedOutcome | None` on the dataclass and
**mandatory in the Planner**. Making the field required would have turned
a vocabulary change into a rewrite of five earlier briefs — MB022's
browser Steps and `cli.py`'s stand-in both hand-build Steps and have
nothing to attach. §3.2 is a rule about *planning*, so it is enforced
where planning happens: `parsing.validate()` refuses a plan whose step has
no expectation, and an architecture test asserts the Planner cannot emit
one. A rule enforced at the door it is about beats a type signature that
forces unrelated code to lie.

### 4.2 There is no second parser

`validate()` takes an already-parsed document, and the Planner reads that
document out of `Evidence.observation["json"]` — the value MB035's
`observe()` produced *while judging the reply*.

If `parsing.py` had parsed the text again, the artefact that was
**verified** and the artefact that gets **executed** would be two objects
that merely usually agree, and the day they disagreed nothing would
notice. Reading the verifier's own observation makes that class of bug
unrepresentable. It is also a published field — `Evidence.observation` is
documented as a plain JSON-shaped dict precisely so consumers other than
the Verifier can read it.

The same argument retired a fence-unwrapper this brief originally had:
MB035's `_as_json` already unwraps one, and once is the right number of
times.

### 4.3 A provider gets six keys, not raw `ObservationCheck`s

`ObservationCheck.field` is a dot-path into whatever observation dict a
Worker produces. Letting a provider write those directly would let it
invent `folder.exists_after` against a Verifier that observes no such
thing — **a check that can never fail, which is worse than no check,
because it reports as verified forever.**

So `success` accepts exactly: `description`, `must_contain`,
`must_exclude`, `must_be_json`, `must_have_fields`, `min_words`. Every
one maps onto a check MB035 already builds over a field `observe()`
already produces, so an expectation the Planner emits is always
evaluable — asserted by a test, not assumed. An unsupported key is a
**refusal**, never a silently dropped one: a dropped key is an
expectation the founder believes is being checked and is not.

`require_non_empty` is always on, because MB035 documents that an
`ExpectedOutcome` with no checks evaluates to `ERROR` under the frozen
evaluator — emitting one would mean producing a Step that can never be
verified.

### 4.4 Five ways it stops, and none of them invents a plan

Nothing registered · the Broker refused · the provider failed · no
verification record · the reply was not a plan document. Each returns a
`PlanRefusal` with a code and a sentence.

**No fallback plan.** MB032 refused a fallback provider because a
fallback is itself a provider decision. A fallback plan is worse: it is a
plan nobody verified, produced at exactly the moment the system has just
demonstrated it cannot plan.

A reply with **no `Evidence` at all** is refused rather than trusted. The
Planner states an expectation on every request, so a reply without one
means the execution path did not apply it — accepting it would quietly
reintroduce the gap MB035 exists to close.

### 4.5 The quality floor for planning is a knob, not a hardcoded `True`

Planning benefits from a stronger model. But *how good a plan has to be*
is a **quality floor**, and ADR-0017 gives floors to the founder's policy
rather than to whichever component happens to be asking. Setting
`requires_strong_reasoning=True` inside the Planner would be the Planner
deciding the founder should pay. It defaults to `False` and is a
constructor argument.

### 4.6 An empty step list is a refusal, not an empty plan

Rule 6 of the prompt gives the provider a way to say *"the catalogue
cannot achieve this"*. Without it, the honest answer is unavailable and
the model invents a capability instead. An empty plan submitted to the
Runtime would complete instantly and **report success**, so `{"steps":
[]}` gets its own refusal code.

### 4.7 Declared dependencies become list order

The Orchestrator walks `plan.steps` in list order, so a plan whose
dependencies are only *declared* would execute out of order. Kahn's
algorithm, ties broken by declaration order — deterministic, so the same
plan document always yields the same sequence.

## 5. What the architecture tests assert

`tests/test_planner_architecture.py`, parsing the package rather than
trusting this document:

1. **No product name anywhere** — fourteen vendors, checked against source
   with docstrings stripped, because a vendor name in prose is
   documentation and the same name in a compared string literal is a
   hardcoded provider. (MB033 found a test that passed on a substring for
   want of this distinction.)
2. **No ranking, no fallback, no `score`** — ADR-0018's Consequences name
   a ranking function growing outside the Broker as the single failure
   mode that would invalidate the design.
3. **No `socket`/`urllib`/`httpx`/`subprocess`/`os`/`pathlib`**, no
   `open()` — Constitution Rule 4: Environment access has exactly one
   door, and it is not this one.
4. **No frozen import** except `plugins/model_router`, which is the
   published request vocabulary (`RoutingContext`, `SelectionRequest`),
   and `verification.evidence`, which is the published contract.
5. **`RATIFIED_EXCEPTIONS` gained no row.**

## 6. Running it live

Against the founder's own machine and daemon, through the real launcher
wiring (`build_system`), the real Desktop Executive scan, the real
Broker, and the real `OllamaProvider`.

### Finding 1 — nothing scanned, so nothing available (correct)

First run: `broker_refused — 5 provider(s) considered, none eligible: not
available`. Exactly MB032's discipline: a machine nobody has scanned
reports as absence rather than as a present local runtime. The Planner
failed closed and spent no tokens. Fixed by submitting the scan objective
through Mission Control, as `--ask` does.

### Finding 2 — the configured model was not installed

`HTTP 404: model 'hermes3' not found`. ADR-0002 chose Hermes and
`OllamaConfig.model` still defaults to it; the founder's daemon has
`gemma4:latest`. MB033's structured failure did its job. Not a defect of
this brief — but it is the second time the default has been wrong on the
machine it ships to, and it is now in the backlog.

### Finding 3 — a planning prompt is not a normal prompt

`no answer within 120s`. `OllamaConfig.timeout_seconds` defaults to 120 s,
sized in MB033 for a short answer. A planning prompt carries the **entire
capability catalogue** — 26 capabilities on this machine — and asks for
structured JSON, so it is several times larger in *and* out than anything
MB033 measured. A timeout is deliberately never retried (MB033), so this
is a clean refusal rather than a hang, but the default is wrong for
planning and the founder would experience it as "planning does not work".

This is a real finding about the Planner in production, not about the
test suite: **the first caller with a genuinely large prompt found that
one global timeout does not fit two very different shapes of work.**

### It planned

With the timeout raised, against `gemma4:latest` on the founder's own
machine, from *"Create a folder called kalpavriksha_demo and write a
README.md inside it saying what the folder is for"*:

```
planned:  True      provider: ollama.local      verdict: matched

  step_1: Filesystem.CreateFolder                    after: -
    expects:  The folder 'kalpavriksha_demo' is successfully created.
      - the answer is not blank
      - mentions "Folder 'kalpavriksha_demo' created."

  step_2: Filesystem.WriteFile                       after: ['step_1']
    expects:  The file 'kalpavriksha_demo/README.md' ... is written.
      - the answer is not blank
      - mentions 'Write successful for kalpavriksha_demo/README.md'
```

Two steps, the right two capabilities out of twenty-six, the dependency
in the right direction, and **an expectation on each one that a
verifier can actually evaluate**. Kalpavriksha decomposed an objective
for the first time.

### Finding 4 — the payloads are wrong, and nothing could have caught it

`Filesystem.CreateFolder` requires `name`. The plan says `path`.
`Filesystem.WriteFile` requires `path`. The plan says `file_path`. Both
steps are **structurally valid and semantically wrong**, and both would
fail at execution.

This is not a model failure — the model was never told. `catalogue.py`
publishes a name, a sentence and a risk tier, because that is all
`CapabilityDescriptor` carries. The seam for fixing it already exists and
is **empty**: `CapabilityManifest.input_schema` is declared in
`plugins/base.py` and populated by nothing in the entire codebase.

Filling it means editing `plugins/`, which is frozen, so MB036
deliberately did not — the same posture MB032 took toward a
`BROKER_DECISION` event type. It is the top item this brief leaves
behind, and it is what makes the difference between a plan that reads
correctly and a plan that runs.

### Finding 5 — an expectation can be falsifiable and still be a guess

`mentions "Folder 'kalpavriksha_demo' created."` is a real, checkable
assertion stated before the step ran — which is exactly what MB035 asks
for. It is also the model's **guess at a result string it has never
seen**, for the same reason as Finding 4.

Worth stating plainly, because it is the failure mode this design makes
*possible* rather than one it removes: a correct step can fail
verification because the expectation described the right outcome in the
wrong words. That is a better failure than the alternative (nothing
checked at all) and it is visible rather than silent — `not_matched` with
the check that failed and what it saw. But "the expectation was
falsifiable" and "the expectation was right" are two different claims,
and only the first is guaranteed. Publishing result shapes alongside
input schemas is the same fix as Finding 4.

## 7. Numbers

- **165 new tests**, 2928 passing overall (from 2763), 1 skipped, zero
  regressions.
- **100% statement coverage** of all seven new modules.
- **Zero frozen files modified**; the guard is green with no new
  exception.
- Ruff clean across everything MB036 touched.

## 8. What this unblocks, and what it leaves

**Unblocked**

- **MB037 — wire the Planner into `cli.py`.** The regex stand-in retires,
  and `test_cli_session.py` is the contract that says it retired safely.
- **The Prompt Cache and Prompt Library actually filling.** Every planned
  Step now carries an expectation, so the caller that verifies is no
  longer the exception.
- **Objectives about Kalpavriksha itself.** A plan is now a thing the
  system produces rather than a thing a human hands it.

**Left open, deliberately**

- **Semantic correctness** (§3). Unchanged, and still the honest limit.
- **A per-call timeout, or a timeout that scales with the prompt.**
  Finding 3. It belongs in `providers/`, not here.
- **The catalogue does not describe payloads or result shapes.**
  Findings 4 and 5, and the most valuable thing this brief leaves behind.
  `CapabilityManifest.input_schema` and `output_schema` are declared in
  the frozen `plugins/base.py` and populated by **nothing**. Filling them
  — and carrying them through `CapabilityDescriptor` into the catalogue —
  turns a plan that reads correctly into a plan that runs. It touches
  frozen files, so it needs its own brief and a ratified exception, or an
  adapter outside `plugins/` that reads `Action.required_parameters()`.
- **Re-planning after a step fails.** Constitution §11 reserves strategic
  recovery for the Brain, and MB024's Runtime does mechanical retry only.
  A Planner that can revise a plan mid-mission is a separate brief with a
  separate safety argument.
- **`OllamaConfig.model` defaults to a model the founder does not have.**
  Finding 2.
