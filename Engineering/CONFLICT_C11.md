# Conflict Report — Sprint 1 Component 11: Admission Record

**Type:** Constitutional conflict. **STOP. No code, no tests, no exports, no commit, no tag.**
**Date:** 2026-08-05
**Verdict:** **BLOCKED.** C11 cannot be implemented completely without the `Objective` / `Mission` ADR.

---

## 1 · The question the brief asked, and the answer

> *Determine whether Admission Record can be implemented completely without requiring the unresolved Objective/Mission ADR.*

**No.**

The Admission Record's purpose is to answer K1. K1's answer is read from its `state` field. That field's vocabulary is the Objective lifecycle — and the Objective Engine Specification states in terms that **its lifecycle cannot ship until the ADR is ratified.**

There is no subset of C11 that both (a) satisfies §10.2 and (b) avoids the blocked vocabulary, because the blocked vocabulary *is* the field that makes the record useful.

---

## 2 · Evidence

All quotations are verbatim from the four grounding documents. Nothing below is recalled.

### 2.1 The record's field set requires `state`

**Objective Engine Specification §10.2**, the published record:

```
  admit(objective)
      │
      └──► ADMISSION RECORD ──────────────────► read by K1 on every mint
             objective_id                          "does this resolve to an
             state                                  admitted, non-terminal
             consequence_ceiling                    objective?"
             budget · deadline
             required_authority                  envelope bounds every warrant
             approval_ref                        minted under this objective

  state change (waiting, resumed) ────────────► K1 keeps refusing while the
                                                objective is not EXECUTING
```

**§10.3** — *"`state` | K1's liveness gate | Non-`EXECUTING` ⇒ no mints."*

**Roadmap v2 §2 C11** — *"Public API. `ObjectiveState` (closed enum) · `AdmissionRecord` (frozen: objective_id, **state**, consequence_ceiling, budget, deadline, required_authority, approval_ref)."*

**Removing `state` is not available.** It is the field K1 reads, and a record that cannot answer K1 is not an admission record.

### 2.2 That vocabulary is explicitly unshippable

**Objective Engine Specification §13.1**, closing:

> *"**Pre-existing blocker, unchanged:** the `Objective` / `Mission` terminology ADR is still open. **This specification's lifecycle cannot ship until it is ratified**, because it would otherwise become a third model of the same concept. That ADR is now the critical path for this component."*

### 2.3 The lifecycle needs two states the frozen Constitution does not have

**Objective Engine Specification §4.1:**

> *"Constitution §5.3 freezes the Mission state machine as `draft → planned → awaiting_approval → executing → verifying → completed | failed | cancelled`… This specification does not design a parallel lifecycle. It uses the frozen one, and identifies exactly **two** states it genuinely lacks. Both are additive… **§13.1 states them as an amendment request.**"*

**§4.2** renders the lifecycle with `WAITING ★ new` and `SUPERSEDED ★ new`.

**Constitution §5.3 (FROZEN)**, verified directly:

> *"the `Mission` state machine (`draft → planned → awaiting_approval → executing → verifying → completed | failed | cancelled`)"*

**Shipped code agrees with the frozen Constitution, not with the specification.** `src/master_agent/mission_manager/mission.py:11` — `MissionStatus` has exactly those eight members. **No `WAITING`. No `SUPERSEDED`.**

**The amendment request is unratified.** Both states are therefore unavailable.

### 2.4 The name is blocked by name, in the authoritative amendment

**Roadmap Amendment 001 §6**, terminology audit:

> | `ObjectiveState` | Sits directly beside frozen §17 **`Mission State`**. Same ADR as M6. **Do not introduce it before that is settled.** |

**Constitution §17 (FROZEN)** defines **Mission** as *"One complete Intent-to-Outcome unit of work; **owns a single Mission State instance** (§5.3)."*

Amendment 001 is authoritative and its instruction is unconditional. Introducing `ObjectiveState` now would violate it directly.

### 2.5 Amendment M6 already reached this conclusion

> *"So C11 carries the blocked vocabulary, and C15 depends on C11. **The Kernel is blocked after all**, by a longer route than the roadmap avoided."*
>
> *"**This is a decision, not something a hardening pass resolves.**"*

M6 rates this **Critical** and records it as *"the finding that most affects the order."*

---

## 3 · Every available path, and why each is closed

| Path | Closed by |
|---|---|
| **Implement the frozen eight states only** | §4.3 — *"A false state is worse than a missing one."* Without `WAITING`, an objective waiting on a founder decision must sit in `EXECUTING` (false — nothing is executing) or `AWAITING_APPROVAL` (false unless it is specifically a founder decision). K1 gates on `EXECUTING`, so a false `EXECUTING` **mints warrants for an objective that is not running.** This is not an incomplete implementation; it is a wrong one |
| **Implement the eight plus `WAITING` and `SUPERSEDED`** | Ratifies an amendment to **frozen** Constitution §5.3 by writing code. The brief forbids modifying frozen components; this would amend one without an ADR |
| **Reuse the shipped `MissionStatus`** | Conflates `Objective` with `Mission` — precisely the collision the ADR exists to resolve — and still lacks both states. §13.1: it *"would otherwise become a third model of the same concept"* |
| **M6 option (b): a narrowed mintability indicator** | M6 itself: *"is a **design decision beyond the roadmap** and would need its own validation."* The brief: *"**Do not invent placeholder vocabularies.**"* Both close it. It remains available to the founder, not to implementation |
| **Omit `state`** | §10.2 publishes it; §10.3 makes it K1's liveness gate; Roadmap §2 C11 declares it. The record would not answer the question it exists to answer |

**No path satisfies the specifications and the brief's constraints simultaneously.**

---

## 4 · What is *not* blocked

| | |
|---|---|
| **Blocked** | C11 Admission Record. Consequently **C15 Kernel** (depends on C11) and **C17 Objective Engine** |
| **Not blocked** | C1–C10 remain valid. No shipped component is at risk. No VEDA conflict was found and none is proposed |
| **Still buildable now** | **C12** Reversibility Registry · **C13** Receipt Ledger · **C14** Override · **C19** Vigilance · **C20** Voice Charter — none depends on C11 or on the ADR |

Sprint 1 does not stall today. It stalls when those five are exhausted.

---

## 5 · What unblocks C11

One founder decision. Amendment M6 §10's three options, unchanged:

| Option | Effect | Cost |
|---|---|---|
| **(a) Ratify the ADR** | Unblocks **C11, C15 and C17** together | One ADR. **Recommended by M6 §10.** Precedent exists: ADR-0014 resolved the identical Executive/Worker collision with a recorded synonym rather than a rename |
| **(b) Narrow the record** | C11 carries a mintability indicator answering only K1's two questions — *admitted?* and *non-terminal?* — instead of the lifecycle state | Unblocks C11 and C15 without the ADR, but is a design decision requiring its own validation pass |
| **(c) Accept the block** | C11 and C15 wait for C17 | Sprint 1 stops after C12, C13, C14, C19, C20 |

Ratification under (a) must also settle **Conflict B** — the two additive states `WAITING` and `SUPERSEDED`. §4.3 and §4.4 give the reasoning; §13.1 gives the transitions. Both are additive: nothing is removed, no existing state changes meaning, no existing transition is deleted.

> Kernel Specification §7.2 K1 requires only: *"`objective_id` present, resolves to an admitted objective in a non-terminal state."* That is narrower than the full lifecycle — which is what makes (b) possible. **Stated as evidence for the decision, not as the decision.**

---

## 6 · Recommendation

**Ratify the ADR — option (a).**

It is one document, it unblocks three components including the Kernel, and it is the longest-standing open item in the project. Under option (c) the Kernel never ships, and without the Kernel the Founder Edition cannot demonstrate constitutional governance — only an assistant taking actions.

If ratification cannot happen this week, **option (b) with an explicit validation pass** is the fallback that keeps C15 reachable. It should be commissioned as its own brief, not folded into C11's.

---

## 7 · What was not done

No file was created in `src/`. No test was written. No export was added to `foundation/__init__.py`. No placeholder vocabulary was invented, no frozen component was modified, no ADR was created, and no roadmap or architecture document was touched. `foundation/` contains the same ten modules it did before this brief.

**Per the brief's conflict rule, this document is the only deliverable.**

---

*Constitutional conflict report. Every claim verified directly against Kernel Specification §7.2, Objective Engine Specification §4.1–§4.4, §10.2–§10.3 and §13.1, Constitution §5.3 and §17, Roadmap v2 §2 C11, Roadmap Amendment 001 §2 M6 and §6, and `src/master_agent/mission_manager/mission.py` on 2026-08-05.*
