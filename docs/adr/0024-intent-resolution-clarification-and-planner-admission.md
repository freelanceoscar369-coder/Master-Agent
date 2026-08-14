# ADR-0024: Intent Resolution, Clarification, and Planner Admission

Status: Proposed (2026-08-14) — codifies the Intent Layer contract that commits `8c47621`, `fea7ee2` and `bb36c9f` implemented against without a written contract to implement against.

Refines ADR-0010 (Brain / Shared Infrastructure / Operator layering) by specifying the **internal** boundary between two Brain components ADR-0010 places in the same column. Relates to ADR-0012 (Knowledge Lifecycle) for the acquisition gap named in §12. Changes no frozen Constitution text: `KALPAVRIKSHA_VISION_V2.md` §2.1, §3.1, §3.2 and §3.5 are **FROZEN** and this ADR is written to be read *through* them, the same way ADR-0010 refined the two-column model without rewriting it.

---

## Context

Three defects were fixed in three consecutive commits. Each was found at runtime by the Founder, and each was a different symptom of the same missing contract:

| Commit | Founder-visible symptom | What was actually missing |
|---|---|---|
| `8c47621` | An ambiguous request was silently completed with an invented parameter | Nothing said the Intent Layer is a **gate**, so nothing said the Planner may not receive an under-specified Intent |
| `fea7ee2` | *"Learn trading"* was answered *"I can't do that with what I'm currently able to do"* | Nothing said **understanding** and **capability** are independent axes, so the code collapsed them |
| `bb36c9f` | *"Learn trading"* was answered by coaching the Founder on how to learn trading | Nothing said an Intent must **preserve who acts and who benefits** |

Every one of these was defensible against the code as written and indefensible against the Founder's vision. That is the signature of an unwritten contract: three engineers (or three sessions) reading the same source reached three different conclusions about what an `Intent` *is*, because the source described a data structure and never described its meaning.

The Constitution already states the direction — §2.1 *"Intent Over Prompts"*, §3.1 *"a real parsing/clarification step so the Planner never has to guess"* — but it states it in two sentences, and both were satisfiable by code that produced all three defects. `Intent(goal="Learn trading", context={"raw_input": "Learn trading"})` is a structured Intent by the letter of §2.1 and is a raw prompt string by its intent.

**No existing ADR owns Intent semantics.** ADRs 0001–0023 were surveyed; the only occurrences of "intent" outside prose are `IntentRecord` in ADR-0023, which is the Kernel's minting record and unrelated. So this is a new ADR rather than an extension, and it refines ADR-0010 because the boundary it specifies — Intent Layer → Planner — lives *inside* ADR-0010's Brain column and is invisible in ADR-0010's own diagram.

---

## Decision 1 · Intent precedes Planning, and the Intent Layer is a gate

```
Founder input
    ↓
Intent Layer          ← understands; asks, if it must
    ↓
structured Intent     ← sufficiently understood, or it does not pass
    ↓
Planner
```

**Normative:**

1. **Planner admission requires a sufficiently understood Intent.** The Planner's job is to decide whether an understood objective can become a valid `MissionPlan`. It is not the Planner's job to work out what the Founder meant.
2. **An Intent requiring clarification must not enter the Planner.** Not as a best-effort guess, not with a placeholder, not with an invented default.
3. **Capability availability is not a prerequisite for admission.** An Intent is admissible because it is *understood*, never because a capability to execute it happens to be registered.

The Planner already behaves correctly when given a goal it cannot plan: it refuses with a reason. The defect that produced `8c47621` was never in the Planner — it was that under-specified Intents reached it at all, and the Planner did the only thing it can do with a hole in its input, which is guess.

**A missing parameter is not permission to invent one.** This is the standing Founder constraint, and it is a consequence of this decision rather than a separate rule.

---

## Decision 2 · Understanding and capability are independent axes

Kalpavriksha must answer two questions **separately**:

> Do I understand what the Founder wants?
> Can my current capabilities directly achieve it?

The cross-product is four states, and all four are reachable:

| Semantic state | Meaning | Correct response |
|---|---|---|
| `UNDERSTOOD + COMPLETE` | Clear, and nothing is missing | Proceed to planning |
| `UNDERSTOOD + NEEDS_INFORMATION` | Clear in shape, missing a required fact | **Ask** — a specific question about the missing fact |
| `UNDERSTOOD + NOT_DIRECTLY_EXECUTABLE` | Clear, and no registered capability completes it in one plan | Engage with the goal; never refuse it as unclear |
| `NOT_SUFFICIENTLY_UNDERSTOOD` | The system cannot represent what was meant | Ask, or say honestly that it did not understand |

**These are semantic states the architecture must be able to distinguish. They are deliberately not mandated as an enum today** — see §9. What is mandated is that no implementation may collapse two of them into one response.

**The third row is the one that had no home**, and it is the whole of `fea7ee2`. *"Buy a house for me"* is understood perfectly and is not executable in one action. Both facts are true simultaneously. Answering it with a sentence about capability limits tells the Founder their instruction was rejected, when it was in fact understood.

**Capability absence is not evidence of ambiguity, and not evidence of failure.**

---

## Decision 3 · Clarification has a precise and narrow meaning

**Clarification means:** *Kalpavriksha does not yet have enough information to correctly represent or complete the Founder's intended goal.*

Clarification is about **missing information**. It is not about missing ability.

Clarification must **not** be triggered merely because:

- no capability exists for the goal;
- no pattern or regex matched the input;
- the request is unfamiliar or has never been seen before;
- answering it requires reasoning;
- the objective is large, long-running, or spans months;
- the objective concerns the real world rather than this machine.

Each of those is a fact about **Kalpavriksha**. Clarification is a statement about the **Founder's message**. Confusing the two produces a system that interrogates the Founder about its own limitations.

### The generic-fallback rule

Neither extreme may be codified:

- ~~all unmatched text = resolved~~ — this is what let an under-specified request through to the Planner.
- ~~all unmatched text = clarification~~ — this is the opposite error, and would make every unfamiliar goal an interrogation.

**Codified instead:**

> **Lexical unfamiliarity is not equivalent to semantic ambiguity.**

That the Intent Layer holds no pattern for a sentence says something about the Intent Layer's vocabulary. It says nothing about whether the Founder was clear. A fallback that carries unmatched-but-clear input forward is therefore **correct**, and the defect it was blamed for belonged elsewhere.

---

## Decision 4 · The capability catalogue does not define Founder meaning

The Founder expresses goals in natural human language. The capability catalogue describes **what Kalpavriksha can presently execute**. It does not describe **what Kalpavriksha can understand**, and it must never become the vocabulary the Founder is required to speak.

> The Founder must not need to phrase requests as available machine actions.

This is one of the reasons the Intent Layer exists at all. A system whose comprehension is bounded by its current capability set can never be told to acquire a new one — the instruction would be unintelligible by construction, which is precisely the failure `fea7ee2` fixed.

**Corollary (Founder-first):** the Brain converts human goals into system-understandable form. The burden of translation sits with the system, never with the Founder.

---

## Decision 5 · Intent must preserve agency and beneficiary

An Intent must preserve **who is expected to act, learn, change, receive, or benefit**. Dropping that is a loss of meaning, not a paraphrase.

The Founder's own semantic probes:

| Founder says | Actor | Beneficiary / who changes |
|---|---|---|
| *"Learn trading"* | **Kalpavriksha** | Kalpavriksha — it is commanded to acquire the skill |
| *"Teach me trading"* | **Kalpavriksha** | **The Founder** — Kalpavriksha teaches, the Founder learns |
| *"Help me learn trading"* | **Both** — collaborative | The Founder |
| *"Buy a house for me"* | **Kalpavriksha** | The Founder — pursued on their behalf |
| *"Tell me how to buy a house"* | **Kalpavriksha** | The Founder — an explanation is the deliverable |

These four sentences share a subject domain and differ in agency. A system that treats them alike has not understood any of them.

**What is NOT codified:**

- ~~"Never tell the Founder what to do."~~ Too broad, and wrong: *"Teach me trading"* and *"Tell me how to buy a house"* are instructions whose correct fulfilment **is** telling the Founder something. The rule that forbids it would break them.
- ~~`COACHING_MARKERS`~~ (`brain/advisory.py`) is an **implementation guardrail**, not architecture. It is a blunt phrase filter that today protects one route — the non-directly-executable one, where the Founder demonstrably did not ask to be taught. It has no standing here, may be replaced or deleted by a future mission, and must not be generalised to routes where the Founder *did* ask to be taught.

**The architectural rule is the one above it:** *preserve the agency and beneficiary expressed by the Founder's intent.* Guardrails are how a given route enforces it today; they are not the rule.

---

## Decision 6 · `NO_STEPS` is an executability result, not a semantic classification

`NO_STEPS` means exactly one thing:

> The available execution capabilities cannot form a valid `MissionPlan` for this objective.

**Not codified:** ~~`NO_STEPS` = advisory intent.~~ That is too strong, and false. These are all non-executable today and are semantically different from one another:

| Objective | Why not executable today | What it actually is |
|---|---|---|
| *"Learn trading"* | No capability acquires a skill | A knowledge-acquisition command (ADR-0012 territory) |
| *"Buy a house for me"* | No capability transacts property | A long-horizon real-world goal |
| *"Send an email to John"* | No email capability is registered | An ordinary action, missing one plugin — and *"John"* is under-specified besides |

The third row matters most: *"Send an email to John"* would become executable the moment an email capability is registered, and would **still** need clarification about which John. `NO_STEPS` cannot distinguish it from *"Learn trading"*, and must not be asked to.

**Normative:** `NO_STEPS` is a valid, honest signal that a goal is not directly executable *right now*. It is a legitimate input to deciding how to respond. It is **not** a classification of what the goal means, and no component may treat it as one. Any component that routes on `NO_STEPS` must document that it is routing on executability alone.

`NO_STEPS` must also remain distinguishable from genuine faults. `MALFORMED`, `UNKNOWN_CAPABILITY`, `PROVIDER_FAILED`, `NO_CAPABILITIES`, `CYCLIC`, `BAD_PAYLOAD`, `BAD_DEPENDENCY` and `MISSING_EXPECTATION` all describe something that went **wrong**. `NO_STEPS` describes something that is merely **larger than one plan**. Presenting a fault as though it were the latter hides a broken system behind reassurance.

---

## Decision 7 · Reasoning stays inside the Brain, behind the Model Router

The Constitution's Brain (§3) is unchanged:

```
Executive Brain
├── Intent Layer     understand, clarify
├── Planner          plan
├── Model Router     the Brain's single door to reasoning
└── Reporter         explain
```

**Normative:** every reasoning call the Brain makes goes through the Model Router (§3.3), whatever the Brain is reasoning *about*. Planning is one such thing, not the only one — §3.3 names the Model Router *"the Brain's single door to reasoning"*, not the Planner's.

Forbidden, and each of these was explicitly considered and rejected:

- a second provider path or client that bypasses the Broker;
- a second semantic router;
- a second Planner;
- reasoning inside the Operator.

Where a Brain component other than the Planner needs reasoning, it reuses the **same** provider ladder and the same AI Capability. A different *workload class* is permitted — that is a fact about the work (size, latency, who is waiting), which is what workload classes exist to express — but a different *provider door* is not.

---

## Decision 8 · Brain ≠ Hands

```
BRAIN                      OPERATOR
Understand                 Observe
Reason                     Act
Plan                       Re-observe
Report                     Verify
                           Recover
```

**Intent interpretation and clarification are Brain responsibilities.** Execution is the Operator's. The Operator never decides what the Founder meant, and never asks the Founder anything. This restates ADR-0010 and §3.5/§4.4 at the one point where the new contract touches them: a clarification question is Brain output, and it reaches the Founder through the Brain's own surface, never as an execution result.

---

## Decision 9 · Response is not fulfilment

**This is explicit architecture, not a quality concern.**

A sentence saying *"I will learn trading"* does **not** prove Kalpavriksha learned trading.
A sentence saying *"I will help pursue the house purchase"* does **not** prove that objective completed.

Six distinct things must stay distinct, and fluency in one is evidence for one only:

| Stage | Question it answers | What proves it |
|---|---|---|
| Understanding | What does the Founder mean? | A structured Intent preserving goal, agency, beneficiary |
| Reasoning | What follows from this? | A reasoning outcome, recorded with its provider decision |
| Planning | Can this become a valid `MissionPlan`? | A plan, or a refusal naming why |
| Execution | Did the attempted action run? | Operator evidence |
| Verification | Does observed reality match the expected outcome? | ADR-0011's independent Verdict |
| Knowledge acquisition | Does the system now *know* something it did not? | ADR-0012's promoted Permanent Knowledge |

**Normative: fluent language must never be accepted as evidence of mission success.** This is §2.2 *"Outcome Over Output"* applied to the specific new hazard this contract introduces — a well-composed answer to a non-executable goal reads exactly like progress, and is not.

---

## Decision 10 · Clarification, Planning, Execution and Verification failures are four different things

| Kind | The question it failed | Must never be spoken as |
|---|---|---|
| **Intent clarification** | What does the Founder mean? What required information is missing? | a refusal, a failure, or a capability limit |
| **Planning failure** | Can this understood objective become a valid `MissionPlan`? | a misunderstanding of the request |
| **Execution failure** | Did an attempted action fail? | a planning or comprehension problem |
| **Verification failure** | Did observed reality fail to match the expected outcome? | success, and never as an execution failure |

**These must never collapse into one generic refusal.** A single sentence covering all four — which is what *"I can't do that with what I'm currently able to do"* was — destroys the Founder's ability to act, because the four have four different remedies: answer a question, register a capability, retry, or investigate reality.

---

## Semantic model

Restating Decision 2 as the model an implementation must be able to express:

```
UNDERSTOOD + COMPLETE                    → admissible to Planner
UNDERSTOOD + NEEDS_INFORMATION           → ask; not admissible
UNDERSTOOD + NOT_DIRECTLY_EXECUTABLE     → admissible; the Planner will say so, and that answer is not a refusal of the goal
NOT_SUFFICIENTLY_UNDERSTOOD              → ask, or say so honestly; not admissible
```

Plus, orthogonally, per Decision 5: **actor** and **beneficiary**.

Note that `UNDERSTOOD + NOT_DIRECTLY_EXECUTABLE` is **not** a state the Intent Layer can determine. Only the Planner, holding the capability catalogue, can. The Intent Layer's output is admissible-or-not; executability is discovered downstream. This is by design and is the structural form of Decision 2.

---

## Non-goals

This ADR does **not**:

- mandate new enums, dataclasses or a parallel implementation taxonomy (§9 of the mission brief; see "Implementation status");
- redesign the Brain, the Planner, the Model Router, or the ConversationEngine;
- specify clarification persistence, correlation storage, or any UI for it;
- specify how knowledge is acquired, validated or retrieved — that is ADR-0012's territory and is named here only to mark the boundary;
- elevate any current implementation guardrail (`COACHING_MARKERS`, phrase lists, refusal-code whitelists) to architecture;
- amend any FROZEN Constitution section.

---

## Implementation status — **PARTIAL**

Measured at `bb36c9f`, 2026-08-14. Classification: **INTENT ARCHITECTURE: DEFINED · INTENT IMPLEMENTATION: PARTIAL.**

| Decision | Status | Evidence |
|---|---|---|
| 1 · Intent precedes Planning | **Implemented** | `8c47621`; `tests/test_intent_layer_boundary.py` proves 0 Planner invocations for an unresolved Intent |
| 2 · Understanding ⊥ capability | **Implemented for the response path** | `fea7ee2`; the four states are distinguished behaviourally, not as types |
| 3 · Clarification is narrow | **Partially implemented** | The Intent Layer asks correctly; the round trip does not close — see Gap 1 |
| 4 · Catalogue ≠ meaning | **Implemented** | Founder text reaches the Planner unchanged; no capability vocabulary is required of the Founder |
| 5 · Agency and beneficiary | **Not structurally implemented** | See Gap 3 — this is the most significant gap in this ADR |
| 6 · `NO_STEPS` is executability only | **Implemented** | `fea7ee2` routes exactly one code and leaves faults as faults |
| 7 · Reasoning behind the Model Router | **Implemented** | One `TieredPromptRunner` instance, one `"reasoning"` AI Capability, asserted by test |
| 8 · Brain ≠ Hands | **Held** | No Operator component interprets Intent |
| 9 · Response ≠ fulfilment | **Documented, not enforced** | See Gap 2 |
| 10 · Four distinct failures | **Implemented for three of four** | Clarification, planning and execution are distinct at the surface; verification failure surfacing is unreviewed by this mission |

---

## Open gaps — deliberately not closed by this ADR

### Gap 1 · The clarification round trip does not close

The required lifecycle:

```
Intent → ClarificationQuestion → Founder answer → correlate with pending Intent
       → IntentLayer.clarify() → resolved Intent → Planner
```

What exists today, verified:

- `ClarificationQuestion` carries `question`, `key`, `options`, `required` (`brain/intent.py:19`).
- `MissionService` transmits **only** `question`, as `PlanRefusal.detail` (`missions/service.py:158`). **`key` and `options` are dropped at that boundary** — `PlanRefusal` has no field for either.
- `IntentLayer.clarify()` has **zero production callers**. A test (`tests/test_intent_layer_boundary.py:130`) asserts this absence by `git grep`, so it is a recorded fact rather than an oversight.
- There is no pending-Intent store and no correlation identifier, so a Founder's answer cannot be matched to the question that prompted it.
- `options` is never populated by any producer, so the MCQ shape is specified and unused.

**Consequence:** Kalpavriksha asks a well-formed question and cannot receive the answer. The exchange ends where it should continue.

### Gap 2 · Response-is-not-fulfilment is documented, not enforced

Decision 9 is stated here and is not structurally prevented anywhere. A composed answer to a non-executable goal currently sets a **completed** status on the surface, which is correct in the sense that the *conversational turn* completed and misleading in the sense that the *objective* did not. Nothing distinguishes "answered" from "achieved" in the state vocabulary (ADR-0021). A future mission should decide whether that distinction belongs in ADR-0021's vocabulary or in the surface.

### Gap 3 · `Intent` cannot represent agency or beneficiary

Decision 5 is the contract; the runtime type cannot express it. `Intent` (`planner/plan.py:60`) has `goal`, `constraints`, `context`, `success_criteria`, `is_sensitive` — **no actor, no beneficiary**.

Measured behaviour of `IntentLayer.parse()` at `bb36c9f`:

| Probe | Result |
|---|---|
| *"Learn trading"* | `goal="Learn trading"`, `context={raw_input}` |
| *"Teach me trading"* | `goal="Teach me trading"`, `context={raw_input}` |
| *"Help me learn trading"* | `goal="Help me learn trading"`, `context={raw_input}` |

All three are structurally identical. **Agency survives today only because the raw sentence is carried verbatim into a downstream prompt, where a language model re-derives it.** That is lexical preservation, not structural preservation, and it is exactly the *"send the raw string to a model"* pattern §3.1 says the Intent Layer deliberately is not.

**This ADR records the contradiction rather than resolving it**, per the mission's scope restriction. Closing it means giving `Intent` a way to carry agency — which is a change to a type the Planner consumes, and deserves its own mission.

### Gap 4 · Founder-commanded knowledge acquisition is unbuilt

`bb36c9f` gave *"Learn trading"* the correct semantic subject: Kalpavriksha is the one commanded to learn. Nothing yet performs the learning. Unproven, and none of it should be inferred from a fluent answer: evidence acquisition, research, validation, persistent knowledge, later retrieval, later application, demonstrable competence gain.

**That work belongs to Knowledge architecture (ADR-0012), not to Intent.** Simulating it inside the Intent or response path would be fake completion, and Decision 9 exists to forbid exactly that.

### Gap 5 · `CLARIFICATION_REQUIRED` is not a declared refusal code

Every other refusal code is a constant in `planner/plan.py` (`NO_STEPS`, `MALFORMED`, …) and lower-case. `CLARIFICATION_REQUIRED` is an upper-case string literal constructed in `missions/service.py` and matched by literal comparison at the surface. It also occupies `PlanRefusal`, a type meaning *"why no plan exists"*, to carry something that is not a planning failure at all — which is Decision 10's collapse, surviving in the type system after being fixed in behaviour.

---

## Conformance requirements

An implementation conforms to this ADR when all of the following hold. Tests marked ✅ exist at `bb36c9f`.

| # | Requirement | Enforced by |
|---|---|---|
| C1 | An Intent requiring clarification never reaches the Planner | ✅ `tests/test_intent_layer_boundary.py` (Planner spy: 0 invocations) |
| C2 | A resolved Intent reaches the Planner as a structured `Intent`, never a bare string argument | ✅ `tests/test_intent_layer_boundary.py` |
| C3 | A missing required parameter is asked about, never invented | ✅ `tests/test_intent_layer_boundary.py`, `tests/test_filesystem_founder_path.py` |
| C4 | A clear, non-directly-executable goal is not refused as unclear | ✅ `tests/test_brain_non_execution_routing.py` classes D, E |
| C5 | A clear, directly executable goal is unaffected by the non-executable route | ✅ `tests/test_brain_non_execution_routing.py` class C |
| C6 | Genuine faults are not presented as non-executable goals | ✅ `tests/test_brain_non_execution_routing.py` class G |
| C7 | No Founder phrase or subject is hardcoded in any routing decision | ✅ `tests/test_brain_non_execution_routing.py` (AST-level, comments excluded) |
| C8 | Brain reasoning uses the Model Router's provider ladder and the same AI Capability as planning | ✅ `tests/test_brain_non_execution_routing.py::TestNoParallelBrain` |
| C9 | The Conversation Engine's taxonomy gains no member for this contract | ✅ `tests/test_brain_non_execution_routing.py::TestNoNewTaxonomy` |
| C10 | Agency and beneficiary are preserved through Intent into the response | ⚠️ **Partial** — enforced only for the non-executable route, by phrase guardrail, not by the Intent type. See Gap 3 |
| C11 | A Founder answer to a clarification resolves the pending Intent and proceeds to the Planner | ❌ **Not implemented.** See Gap 1 |
| C12 | A composed answer is never recorded as objective fulfilment | ❌ **Not enforced.** See Gap 2 |

C11 and C12 are stated as requirements deliberately: they are what the next missions are measured against, and listing them as unmet is the point.

---

## Semantic probe audit (2026-08-14, measured at `bb36c9f`)

Not tests, and not strings to match on. Read as: *does the contract above give the right answer for each?*

| Probe | Founder means | Actor | Beneficiary | Clarification? | Planner admission? | Directly executable? | Unimplemented |
|---|---|---|---|---|---|---|---|
| *"Create a folder called Research on my Desktop"* | Make that folder | Kalpavriksha | Founder | No | ✅ Valid | **Yes** | — |
| *"Create a folder"* | Make a folder, name unstated | Kalpavriksha | Founder | **Yes** — name missing | ❌ Refused, correctly | n/a | Round trip (Gap 1) |
| *"Open github.com"* | Open that site | Kalpavriksha | Founder | No | ✅ Valid | **Yes** | — |
| *"Learn trading"* | Kalpavriksha acquires the skill | **Kalpavriksha** | **Kalpavriksha** | No | ✅ Valid | No | Acquisition (Gap 4); agency is lexical only (Gap 3) |
| *"Teach me trading"* | Kalpavriksha teaches | Kalpavriksha | **Founder** | No | ✅ Valid | No | Not distinguished from the row above at the Intent level (Gap 3) |
| *"Help me learn trading"* | Collaborative | **Both** | Founder | No | ✅ Valid | No | Collaboration unrepresentable (Gap 3) |
| *"Buy a house for me"* | Pursue on the Founder's behalf | Kalpavriksha | **Founder** | Arguably — budget, location | ✅ Valid | No | Long-horizon objectives unmodelled |
| *"Tell me how to buy a house"* | Explain | Kalpavriksha | **Founder** | No | ✅ Valid | No | Explanation is a *correct* fulfilment here — and the current guardrail would likely suppress it (Gap 3, and the reason `COACHING_MARKERS` is not architecture) |

**The last row is the sharpest finding.** *"Tell me how to buy a house"* is an instruction whose correct fulfilment **is** advising the Founder — and `brain/advisory.py`'s `COACHING_MARKERS` guardrail would reject that answer, because it cannot tell this row from *"Learn trading"*. The guardrail is right for the route it currently guards and would be wrong the moment that route widened. This is precisely why Decision 5 codifies *agency preservation* and explicitly refuses to codify the phrase filter, and why Gap 3 is the highest-value gap to close next.

No code was changed to make any of these pass.

---

## Relationship to ADR-0010

ADR-0010 established three layers and proved the Brain/Operator boundary was being violated in practice. It says nothing about the boundaries *within* the Brain column, because at the time the Brain column was one box.

This ADR specifies one internal boundary — Intent Layer → Planner — and one internal reuse rule — all Brain reasoning goes through the Model Router (Decision 7). Both are refinements: nothing here moves a component between layers, and nothing here contradicts ADR-0010's core finding that shared components belong to neither column.

Decision 4 is the Brain-internal analogue of ADR-0010's argument. ADR-0010 rejected letting one column's convenience define where a shared component lives; this ADR rejects letting the Operator's capability catalogue define what the Brain can understand. Same failure shape, one layer up.

## Relationship to ADR-0012 and Knowledge architecture

ADR-0012 defines `Execution → Evidence → Knowledge Candidate → Promotion Review → Permanent Knowledge → Future Reasoning`.

Gap 4 sits squarely in that lifecycle. *"Learn trading"* is a Founder command whose fulfilment is **the acquisition of Permanent Knowledge**, and ADR-0012 already owns every stage of that. What this ADR contributes is only the front of the pipe: the command is now understood correctly, with Kalpavriksha as the subject.

The two ADRs meet at a seam neither yet specifies: **ADR-0012's lifecycle is driven by Evidence produced during Execution, and a Founder-commanded learning goal has no execution to produce Evidence from.** A goal to *learn* must be able to enter the Knowledge lifecycle without first having been an executed Mission. Resolving that is a Knowledge-architecture mission, and this paragraph exists so the next reader finds the seam already named.

---

## Consequences

**Good:**

- Three defects that each looked like separate bugs are now one written contract, so the fourth of that family is preventable rather than discoverable-at-runtime by the Founder.
- Decisions 2, 3 and 6 give four distinct situations four distinct responses, replacing one sentence that covered all of them and helped with none.
- Decision 5 states the agency rule at the right altitude — general enough to cover *"Teach me trading"*, specific enough to have caught `bb36c9f`.
- The gaps are enumerated with evidence, so the next mission starts from a known position rather than rediscovering it.

**Costs and risks accepted:**

- **The contract is ahead of the implementation, and says so.** C10 is partial and C11/C12 are unmet. This is a deliberate choice over a weaker contract that current code fully satisfies — a contract that describes only what already works cannot catch the next defect.
- **Decision 2's four states are not types.** They are enforced behaviourally and by test, which is weaker than the type system and was chosen to avoid inventing a taxonomy during a documentation mission (§9, §16). Gap 3 is where that cost is concentrated.
- **Decision 7 admits a second workload class through the same door.** The distinction between "same provider ladder, different workload class" and "a parallel provider path" is stated but not mechanically enforced; a future component could drift across it while claiming conformance.
- Extra reasoning calls: a non-directly-executable goal now costs a planning call *and* a reasoning call. Accepted — the planning call is what establishes non-executability honestly, and skipping it would mean guessing.
