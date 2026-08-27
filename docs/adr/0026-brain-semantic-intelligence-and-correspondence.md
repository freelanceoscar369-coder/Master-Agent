# ADR-0026: Brain Semantic Intelligence and Correspondence

Status: Accepted — Founder-ratified 2026-08-27

Refines the inside of Constitution §3. **Does not amend the
Constitution**, and deliberately adds no box to `KALPAVRIKSHA_VISION_V2
.md`: the Constitution already gives the Brain understanding, reasoning,
planning and reporting. What was missing was not a responsibility — it
was a guarantee that the *same meaning* survives the journey between
responsibilities the Brain already had.

## The problem

Three defects found in three days, all the same shape.

A founder asked *"whats required to achieve state kalpavriksha builds
kalpavriksha?"* and was told "Nothing has run yet" in three milliseconds.
A founder answered *"where?"* with *"on desktop"* and the words reached a
capability argument verbatim. A founder said *"search for new 2026 action
rpg games and give me demo version download links"* and the **filesystem**
search parser claimed it on a substring, then asked forever for something
they had already said.

Each was repaired at its own boundary. None of the repairs would have
prevented the next one, because the thing they have in common is not a
parser or a role or a regex. It is that **the founder's meaning was never
a first-class object.** It existed as prose at the front, as arguments in
the middle, and as verdicts at the end, and nothing carried it across.

The end of the chain says so out loud. `brain/reporter.py` reports
`founder_outcome_conformance: "not_evaluated"` — an honest admission that
the system could tell a founder every step was verified without being
able to say whether the thing they asked for happened.

## Decision

Semantic intelligence is an **internal Brain faculty**, not a fourth
layer. The architecture is unchanged:

```
EXECUTIVE BRAIN            Intent Layer · Planner · Model Router · Reporter
                           + Brain Semantic Intelligence (internal)
SHARED INFRASTRUCTURE
UNIVERSAL EXECUTIVE OPERATOR
```

It owns semantic interpretation, semantic requirement preservation,
plan-to-intent correspondence, capability-choice rationale, grounded
system-question context, and mission-level founder-outcome conformance.

It owns **none** of: environment access, execution, permission, provider
selection, capability registration, Verification, Evidence, Mission State,
persistence, tool execution.

### The invariant

> Founder meaning must remain traceable from input to verified outcome.

Answerable at any point: what did they mean; which requirements were
extracted; which steps cover each; why each capability was a valid fit;
which reasoning outputs correspond to which requirement; which required
outcomes were verified; does verified reality satisfy the original
meaning; what remains unknown.

No component may answer these by reconstructing meaning from a raw prompt
after the fact when canonical semantic data exists.

### Semantic requirements

The existing canonical `Intent` carries `SemanticRequirement` — id, kind,
description, required, provenance — with a **closed** kind vocabulary:
`effect`, `information`, `deliverable`, `constraint`. Requirements
describe WHAT. The Planner decides HOW, and a requirement never names a
capability.

Derived deterministically for typed intents. For compound natural
objectives the existing Brain reasoning door performs a narrow structured
extraction — *what does the founder require* — never *which tool should
we use*. Malformed extraction is not admitted; material uncertainty is
clarified rather than guessed.

### Two artefacts, never one

A requirement carries **both** sides of the correspondence question:

| field | what it holds | example |
|---|---|---|
| `founder_evidence` | Founder Semantic Evidence — what was said | `"d drive in Onkar folder"` |
| `description` | Canonical Execution Interpretation — the system's reading | `location = d_drive` |
| `interpretation` | whether that reading is settled | `known` / `uncertain` |

**Conformance may not derive both sides from the interpretation.** This
is the decision the two failed acceptances forced, and it is not a
refinement of the previous design — it corrects a hole in it.

Requirements were being derived from what the Brain RESOLVED. That makes
this representable, and it happened twice:

    founder utterance
      -> incorrect interpretation
        -> requirement derived from the incorrect interpretation
          -> execution matches the incorrect interpretation
            -> Verification MATCHED
              -> OutcomeConformance SATISFIED
                -> "This did what you asked for."

Every link is sound. The chain is internally consistent end to end and
the conclusion is false, because the requirement and the execution came
from the same misreading, so the comparison at the end could only ever
discover that the system agreed with itself. **Consistency with an
interpretation is not correspondence with meaning**, and a system that
spells them the same way will keep certifying its own mistakes.

Two rules follow, and both fail toward asking rather than acting:

1.  **Nothing is settled while a word of the founder's reply is
    unexplained** — by a value that was resolved or by pure grammar,
    whoever resolved it. This is checked after EVERY interpretation
    source, structural and reasoned alike. A model returning a
    legitimate vocabulary value is not evidence that the value is the
    whole answer: asked *"d drive in onkar folder"*, the production
    model returned `{"location": "d_drive"}` — a legal member of the
    capability's own vocabulary — and validation passed. **An
    instruction to a model is not a constraint.** Prompt compliance
    never becomes one.

2.  **An unsettled interpretation may not execute and may not be
    reported as satisfied.** Those are the same rule seen from either
    end of a mission. `UNKNOWN` is a real answer and is never rounded
    up.

The accounting is over MATERIAL meaning, not literal tokens: grammar is
allowed to disappear, facts are not. The word list that defines grammar
contains no place and no thing, pinned by test — the moment it did, it
would be the phrase table this ADR exists to prevent.

### Plan coverage

`Step.covers` names the requirement ids a step is responsible for.
**Descriptive**: the Runtime ignores it for ordering and permission, as it
already ignores `priority`. Deterministic plans attach coverage by
construction; AI plans must state it and are rejected when a required
requirement is uncovered, when an unknown id is cited, or when coverage
points at a step that does not exist.

Coverage is a claim of responsibility, not proof of reality. Evidence
decides reality.

### Semantic assessment is not Verification

Where deterministic correspondence cannot settle whether a plan or a
generated answer matches the requirement, the Brain may perform **one**
bounded semantic critique through the existing Model Router. Its
vocabulary is deliberately different from Verification's:

| | states |
|---|---|
| `SemanticAssessment` | `ALIGNED` · `NOT_ALIGNED` · `UNCERTAIN` |
| `Verdict` (ADR-0011) | `MATCHED` · `NOT_MATCHED` · `ERROR` |

A semantic assessment never becomes `Evidence`, never becomes a `Verdict`,
never counts as mission success, and is never cached as one. MB035's
guarantee is untouched: `TextVerifier` stays deterministic, Verification
stays independent and observation-based. There is no critique of the
critique.

### Outcome conformance

The missing end of the spine. It consumes semantic requirements, plan
coverage and step Evidence, and returns `SATISFIED` / `NOT_SATISFIED` /
`UNKNOWN`. Machine-checkable, conservative, and no model is needed when
coverage and Evidence make the relationship decidable. `UNKNOWN` is never
rendered as "Done".

### Grounded self-query

A founder question about Kalpavriksha is answered from authoritative
state — the live capability registry, the provider registry, the Broker's
decision ledger, plan history, Evidence — not from a provider's memory of
what Kalpavriksha is. Facts already held by Shared Infrastructure need no
mission to read.

## Rejected alternatives

1. **A separate Semantic Intelligence layer.** Duplicates Brain
   ownership. The Constitution already assigns understanding and
   reporting to the Brain; a fourth box would create two places that
   both believe they own meaning.
2. **A second Intent engine.** Canonical `Intent` already exists, and the
   defects came from meaning *leaving* it, not from its shape.
3. **A semantic tool selector.** The Planner owns which capability
   appears in a Step. Semantics supplies the requirement; the catalogue
   supplies the contract; the Planner joins them.
4. **A semantic provider selector.** The Broker is the sole provider
   authority (MB033 Rule 4). Brain semantics may state request
   properties — workload, sensitivity, an excluded prior candidate — and
   may never name a provider.
5. **A model-produced Verification verdict.** ADR-0011 exists precisely
   so completion does not rest on a claim. A model grading a model is not
   an independent observation of reality.
6. **Unrestricted model-judges-model recursion.** Bounded critique is
   Brain reasoning about admission. Recursion would make the last judge
   the authority, which is the failure mode ADR-0011 removes.
7. **Direct filesystem or browser inspection from the Brain.**
   Environment access is the Operator's alone. A Brain that could look
   would eventually look instead of asking, and its answers would stop
   being traceable to Evidence.

## Consequences

The Reporter can finally distinguish three things a founder cares about
and the system previously conflated: the work ran, the steps were
independently verified, and *what you asked for happened*. `UNKNOWN`
becomes sayable, which is the point — a mission with no semantic trace
stays `UNKNOWN` rather than having correspondence invented for it
retrospectively.

More founder text enters Brain reasoning, so sensitivity may be inherited
or increased on these paths and may never be lowered.
