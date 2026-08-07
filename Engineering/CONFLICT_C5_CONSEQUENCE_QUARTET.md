# Architectural Conflict — Sprint 1 Component 5 (Consequence Quartet)

**Status:** **BLOCKING.** Implementation halted before any code was written.
**Date:** 2026-08-05
**Nothing implemented. Nothing modified. `foundation/` unchanged since `kalpavriksha-s1-c4.0`.**

---

## 1 · Summary

The Component 5 brief specifies the quartet as:

> *Observation · Expected Outcome · Actual Outcome · Verdict*

**That is not the consequence quartet.** It is Constitution §17's **Evidence**, which is already frozen and already shipped.

Two independent conflicts follow, and the second is the more serious one.

---

## 2 · Conflict A — the consequence quartet is four different fields

Three frozen documents define it identically. There is no ambiguity to resolve.

| Source | Text |
|---|---|
| **VEDA 01 §5 Approvals** | *"Every request for judgment answers four questions before asking for a verdict: **what changes, what it costs, what happens if you do nothing, and whether it can be undone.** A request missing any of the four is not a request; it is a guess dressed as one, and it does not ship."* |
| **VEDA 04 · B1** | *"Computes, for every judgment request, the four mandatory fields: **what changes · what it costs · what happens if you do nothing · whether it can be undone.**"* |
| **VEDA 04 · contract** | `build(decisionContext) → {whatChanges, cost, ifNothing, reversibility}` |
| **VEDA 03 · Screen 04** | *"a 2×2 consequence matrix — **what changes / cost / if you do nothing / reversible**"* |

### The decisive property

**The consequence quartet is computed *before* a decision, not after an execution.** It is what the founder is shown when judgment is requested. VEDA 04 B1's invariant is explicit: *"a judgment request missing any field cannot be emitted."*

The brief's four fields describe what happened *after* execution. They are the opposite end of the lifecycle, and no arrangement of them answers *"what happens if you do nothing?"* — a question that only has meaning while the action is still hypothetical.

---

## 3 · Conflict B — the brief's four fields are already implemented

### They are Constitution §17's Evidence

| Term | Constitution §17, frozen |
|---|---|
| **Observation** | *"Freshly captured fact about real-world state, gathered by Verification Subsystem re-checking an Environment Instance. Distinct from Execution Result."* |
| **Evidence** | *"**Observation + Expected Outcome + Verdict**, packaged as durable record."* |
| **Verification** | *"Act of comparing Observation against Expected Outcome to produce Verdict."* |

### And they ship today

`src/master_agent/verification/evidence.py`, protected by ADR-0011:

```
Evidence         evidence_id · worker · environment · captured_at ·
                 expected · observation · verdict · check_results · errors
ExpectedOutcome  description · checks
ObservationCheck field · operator · value · description
Verdict          matched · not_matched · partially_matched · error
```

**Implementing the brief literally would produce a second Evidence, under a third name.**

That matters beyond ordinary duplication. `OBJECTIVE_ENGINE_SPECIFICATION_v1.0.md` §13.1 already records that **"Evidence" carries two meanings** — Constitution §17's (Observation + Expected Outcome + Verdict) and VEDA 04 B5's Evidence Graph (claim → sources) — and that resolving it needs an ADR. Adding a third structure of the same shape, called something else again, makes an open terminology problem materially worse.

### A tell in the brief itself

The brief lists **Observation** and **Actual Outcome** as separate fields. Constitution §17 defines an Observation *as* the freshly captured fact about real-world state — which is the actual outcome. The two are the same thing named twice.

That internal redundancy is the strongest evidence that the field list was assembled from recollection rather than from the frozen documents, which is precisely the failure mode the brief's own grounding instruction exists to prevent.

---

## 4 · What is actually missing

**The real consequence quartet is not implemented anywhere.** Verified: no `what_changes`, `whatChanges`, `if_nothing`, `ifNothing`, `ConsequenceQuartet` or equivalent exists in `src/` or `tests/`.

It is also **already known to be missing**. `CONSTITUTIONAL_KERNEL_SPECIFICATION.md` §14.1 documents that VEDA 04 A1 requires the intent record to carry the quartet while B1 — the engine that produces it — arrives a phase later, and recommends the field carry an explicit `pending_consequence_engine` marker until then.

So there is a genuine, grounded, foundational component to build here. It is simply not the one the brief describes.

---

## 5 · The two readings

### Reading A — build the consequence quartet as VEDA defines it — **recommended**

An immutable `Consequence` value: `what_changes`, `cost`, `if_nothing`, `reversibility`.

| Requirement from the brief | Reading A |
|---|---|
| immutable · deterministic · serializable · hashable · independently testable | ✅ all five, exactly as Components 3 and 4 |
| must not depend on Objective Engine, Learning, Rule Engine, Broker, AI Providers | ✅ depends on **nothing** |
| *"the canonical data model that describes the consequence"* | ✅ that is its literal definition in three frozen documents |
| "one of the foundations of trust" per VEDA | ✅ VEDA 01 §5 — a request missing any field *"does not ship"* |

**No amendment required.** The smallest constitutional change is none: use the frozen definition.

**It also unblocks something.** `Warrant.consequence` is the field Kernel Spec §14.1 left pending. Building the data model now means the marker can be replaced by a real optional value when B1 lands, with no change to the Warrant's shape.

### Reading B — build the brief's four fields literally — **rejected**

- Duplicates `verification/evidence.py`, which is shipped and frozen by Constitution §17 and ADR-0011
- Attaches a frozen name to a concept that is not it
- Creates a third structure in an already-contested terminology space (Objective Engine Spec §13.1)
- Contains an internal redundancy: Observation and Actual Outcome are the same thing

**This would require amending Constitution §17 and VEDA 04 B1.** Both are frozen, and neither amendment is in scope.

---

## 6 · Grounded answers to the brief's nine design questions

Answered for **Reading A**, so the component is ready to build the moment it is confirmed.

**1 · What fields belong in the Quartet?**
Exactly four, per VEDA 04's contract: `what_changes`, `cost`, `if_nothing`, `reversibility`. VEDA 04 B1 — *"returns an error, never a partial"* — means all four are mandatory and no fifth is permitted.

**2 · Which fields belong in Receipt instead?**
None of the four. The quartet is pre-decision; the Receipt is post-execution. They never overlap. The Receipt already carries what happened (`outcome`, timestamps, `compensation_ref`); the quartet carries what *would* happen.

**3 · What is immutable?**
All of it. A quartet is what the founder was shown when they decided; editing it afterwards would restate the basis of a decision already made — the same argument that makes the Warrant and Receipt immutable.

**4 · What may remain unknown?**
`cost` may legitimately be unknown-but-stated (*"I can't price this"*), because VEDA 01 §8 distinguishes *I don't know* from *I haven't checked*. **`what_changes`, `if_nothing` and `reversibility` may never be unknown** — B1's invariant is that a request missing a field cannot be emitted, and *"whether it can be undone"* is answerable from the Reversibility Registry, which fails closed.

**5 · When can Verdict be UNKNOWN?**
**There is no Verdict in the quartet.** Verdict belongs to Verification (Constitution §17) and already exists as `verification.evidence.Verdict`. The post-execution unknown case is already handled: `Receipt.outcome = UNKNOWN`, shipped in Component 4.

**6 · Can a Quartet exist before execution?**
**It must.** That is its only valid moment. A quartet computed after execution is a description of history, not a request for judgment.

**7 · Can a Receipt exist without a Quartet?**
**Yes**, and this matters. A quartet is built for a **judgment request** — an escalation. An action that fires under a standing rule (E0) is never escalated, so no quartet is ever computed, yet it still writes a receipt. Requiring one would make every auto-handled action escalate, which inverts the product.

**8 · Can multiple Quartets exist for one Receipt?**
At most one, and usually none. One judgment produces one quartet; a re-escalation after facts change is a **new** judgment request with its own quartet, not a second one for the same decision.

**9 · Does a retry create a new Quartet or update the existing one?**
**Neither.** A retry executes under the same Warrant (Kernel Spec §8.3: the grant survives) and writes a new Receipt per attempt (Component 4, ED-005). No new judgment is requested, so no quartet is created and none is ever updated — the quartet is immutable.

### Dependency direction

```
   Consequence  →  (nothing)

   Warrant      →  Consequence?      optional, pending B1 (Kernel Spec §14.1)
   Judgment req →  Consequence       mandatory (VEDA 04 B1) — future component
   Receipt      →  (nothing)         unchanged; the two never touch
```

No circular reference is possible, because `Consequence` depends on nothing at all.

### Future consumers — contract only, none implemented

| Consumer | Uses it for |
|---|---|
| **B1 Consequence Engine** | Produces it. The only writer. |
| **B2 Ranking** | `irreversibility × log(exposure) × deadline × novelty` — reads `reversibility` and `cost` |
| **B3 Escalation Router** | Reads `reversibility` to refuse batching an irreversible item |
| **Founder Dashboard (VEDA 03)** | Renders the 2×2 consequence matrix on Screen 04 |
| **D1 Narration** | *"If I do nothing, it renews Friday 00:00"* comes from `if_nothing` |
| **B4 Silence Defaults** | The declared default is derived alongside `if_nothing` |
| **E1 Provenance** | Stores what the founder was shown at the moment they decided |
| **C7 Annual Dependency Audit** | Reads historical quartets to show what was decided and on what basis |
| **D3 Mistake Protocol** | Compares the quartet's prediction against the Receipt's outcome — **the one consumer that reads both**, and the reason they must stay separate objects |

---

## 7 · Recommendation

**Confirm Reading A.** Build `Consequence` with the four fields VEDA 01 §5, VEDA 04 B1 and VEDA 03 all specify identically. No VEDA is amended, nothing shipped is duplicated, and the component satisfies every structural requirement the brief states.

Scope would be three files as the brief requires: `foundation/consequence.py`, `tests/test_foundation_consequence.py`, and the export line in `foundation/__init__.py`.

**If the brief's four fields are genuinely wanted**, the correct action is not a new component — it is to use `verification.evidence.Evidence`, which already exists and already means exactly that. Any change to it is a redesign of a shipped, frozen component and belongs in a different mission.

---

## 8 · What was not done

No file created. No file modified. No test written.

`foundation/` contains `clock.py`, `principal.py`, `execution_context.py`, `warrant.py`, `receipt.py` — byte-identical to `kalpavriksha-s1-c4.0`. All five tags are untouched.

---

*Conflict report. Raised before implementation, as the mission brief instructs. Every citation verified against the frozen documents and the shipped source on 2026-08-05.*
