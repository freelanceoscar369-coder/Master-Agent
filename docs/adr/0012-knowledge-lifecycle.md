# ADR-0012: The Knowledge Lifecycle — Evidence to Permanent Knowledge, with a human-gated Promotion Review

Status: Accepted (2026-07-26) — Mission Brief 021 Revision 3 (Founder Constitution Freeze)

## Context

`MEMORY_ARCHITECTURE.md` and `KALPAVRIKSHA_VISION_V2.md` v2 already
distinguished Temporary Observations (Conversation Memory, Mission Memory)
from Permanent Knowledge (Mission History, User Preferences), and defined
an Evidence Hierarchy for what to trust when reasoning about what actually
happened. What neither document specified is the missing middle: how does
a raw, one-off Mission's Evidence ever become something the Planner
*actively consults* as trusted, generalizable knowledge, rather than just
another row it could look up? The independent audit flagged this gap
directly — the Knowledge Philosophy covered "what happened" thoroughly but
had no described **promotion** mechanism, despite Memory's own future
evolution path (`MEMORY_ARCHITECTURE.md` §12, Layer 4 "Knowledge Memory")
anticipating exactly this need.

Separately, a founder decision named a candidate lifecycle: `Execution →
Evidence → Knowledge Candidate → Verification → Promotion → Permanent
Knowledge → Future Reasoning`. Using "Verification" as this lifecycle's
gate name collides with ADR-0011's Verification, which the Constitution's
terminology freeze (`KALPAVRIKSHA_VISION_V2.md` §17) reserves exclusively
for Mission-level real-world-state checking. The two processes check
different questions — "did this Step's execution match its Expected
Outcome" versus "does this accumulated pattern deserve to permanently
shape future reasoning" — and conflating their names would make "means
exactly one thing" false the moment both existed.

## Options considered

1. **Reuse "Verification" for both gates**, relying on context to
   disambiguate. Rejected — directly violates this revision's own
   terminology-freeze requirement (`KALPAVRIKSHA_VISION_V2.md` §17: "use
   exactly one meaning for each"), and the two checks have different
   owners, different inputs, and different consequences; a shared name
   invites exactly the kind of accidental conflation ADR-0011 was written
   to prevent one level down.
2. **Auto-promote Knowledge Candidates once they cross an observation-count
   threshold, no human gate.** Rejected for Founder Edition — promoting a
   Candidate changes the Brain's future reasoning permanently and
   silently, for every subsequent Mission. That is precisely the class of
   high-leverage, hard-to-reverse action `KALPAVRIKSHA_VISION_V2.md` §15
   already exists to gate for execution; there's no principled reason
   durable reasoning changes should get a lighter gate than a destructive
   filesystem action does. `ENGINEERING_PRINCIPLES.md` #10's judgment
   ("don't build the general version until concrete examples exist to
   generalize from") also argues against inventing an unsupervised
   auto-promotion policy before any real Candidate has ever been produced.
3. **A distinct, human-gated "Promotion Review" stage**, reusing the
   Evidence Hierarchy's discipline but checking a different question than
   Mission-level Verification. Chosen.

## Decision

`KALPAVRIKSHA_VISION_V2.md` §9.3 defines the lifecycle:

```
Execution → Evidence → Knowledge Candidate → Promotion Review → Permanent Knowledge → Future Reasoning
```

**Stage ownership** (full detail in §9.3's table): Execution is the
Operator's job (unchanged). Evidence is the Verification Subsystem's
output (ADR-0011), stored via Shared Infrastructure (ADR-0010). A
**Knowledge Candidate** is nominated by the **Brain** (the Planner,
reading accumulated Evidence) — recognizing a recurring, generalizable
pattern is a reasoning judgment, not an execution fact, so it does not
belong to the Operator. **Promotion Review** checks the Candidate against
a promotion bar (observed enough times, not contradicted by other
Evidence, not already superseded) and, for Founder Edition, **requires
human confirmation** — the same "one clear decision point" pattern already
used for destructive capabilities. Only after Promotion Review does
something become **Permanent Knowledge**, stored in Shared Infrastructure
(Memory's Layer 4, `memory/future.py`'s `KnowledgeMemory`), and only then
does the Brain treat it as **Future Reasoning** context rather than
inspectable history.

**Rejection** works two ways: Promotion Review can reject a Candidate
outright, and existing Permanent Knowledge is itself revocable — new,
higher-tier Evidence that contradicts it (per the Evidence Hierarchy,
`KALPAVRIKSHA_VISION_V2.md` §9.2) flags it for re-review rather than
letting it silently remain trusted. This extends Rule 8 ("Evidence
Hierarchy Is Law") to Permanent Knowledge explicitly, where it was
previously implicit only for Mission-level facts.

## Consequences

- "Verification" keeps exactly one meaning across the whole Constitution
  (ADR-0011's meaning); the Knowledge Lifecycle's gate is named Promotion
  Review specifically to avoid a naming collision this ADR anticipated
  rather than one the project waited to be surprised by.
- Human-gated Promotion Review is a real, load-bearing scope decision for
  Founder Edition: nothing in this codebase can currently silently
  reshape the Brain's future planning behavior without an explicit human
  "yes," matching the project's standing "no standing blanket approval for
  consequential, hard-to-reverse actions" posture (ADR-0009's
  `IRREVERSIBLE`/`ALWAYS_FOR_CAPABILITY` rule is the precedent this
  mirrors, one layer up, for knowledge rather than execution).
- Automating Promotion Review later, once a track record exists, is an
  explicitly anticipated evolution (marked EVOLVABLE in the Constitution),
  not a violation of this ADR — the same judgment call this project
  already applies to generalizing patterns only after real examples exist.
- No code changes result from this ADR. Layer 4 (`KnowledgeMemory`)
  remains an unimplemented interface, exactly as `MEMORY_ARCHITECTURE.md`
  §4d already scoped it; this ADR specifies the *process* around it that
  will eventually populate it, for whichever future Miracle builds that.
