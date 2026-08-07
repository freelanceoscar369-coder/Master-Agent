# ADR-0021: `ObjectiveState` is a distinct constitutional vocabulary; `Mission State` is untouched

Status: Accepted (2026-08-05) — Founder Decision, ratified. Resolves
`Engineering/CONFLICT_C11.md` and Roadmap Amendment 001 finding **M6**.

Amended (2026-08-06) — Founder Decision: **D5 superseded**, and its
citation of "Kernel Specification §10.3" corrected to Objective Engine
Specification §10.3. K1 is structural admission only and does not enforce
`EXECUTING`. See D5 and `Engineering/CONFLICT_C15_PART2.md`. No other
clause changes; C8 is untouched.

## Context

Sprint 1 Component 11 (Admission Record) was blocked. The block had two
parts, both recorded before this ADR:

**The collision.** Objective Engine Specification §13.1 Conflict A and
Roadmap Amendment 001 §6 both record that `ObjectiveState` sits directly
beside **`Mission State`**, a frozen Constitution §17 term. Amendment
001's terminology audit carried an unconditional instruction: *"Do not
introduce it before that is settled."*

**The missing states.** Objective Engine Specification §4.1 states that the
specification *"does not design a parallel lifecycle"* and instead uses
Constitution §5.3's frozen Mission state machine, *"identif[ying] exactly
two states it genuinely lacks"* — `WAITING` (§4.3) and `SUPERSEDED` (§4.4)
— held as an unratified amendment request in §13.1.

Because the Admission Record's `state` field is what K1 reads on every
mint (§10.2, §10.3), C11 could not be built. C15 depends on C11 and C17
depends on both, so three components were blocked, including the Kernel.

`CONFLICT_C11.md` established that every available path was closed:
implementing the frozen eight alone produces a *false* `EXECUTING` for a
waiting objective — and since K1 gates on `EXECUTING`, a false one **mints
warrants for an objective that is not running**. §4.3's *"a false state is
worse than a missing one"* has direct constitutional consequence here.

This was a founder decision about a frozen document, not an engineering
question. It has now been made.

## Decision

**A distinct constitutional vocabulary is introduced. `Mission State` is
not modified, not extended, and not reused.**

```
ObjectiveState
    WAITING
    READY
    EXECUTING
    COMPLETED
    FAILED
    SUPERSEDED
```

### D1 · The two vocabularies are permanently separate

`Mission State` (Constitution §5.3, §17) and `ObjectiveState` name
different things and neither is defined in terms of the other. A Mission
is *"one complete Intent-to-Outcome unit of work"* (§17). An Objective is
the constitutional anchor a Warrant is minted against (Kernel
Specification §7.2 K1).

**Constitution §5.3 and §17 are unchanged by this ADR.** `MissionStatus`
in `src/master_agent/mission_manager/mission.py` is unchanged, and its
eight members and transition table stand exactly as shipped.

This follows ADR-0014's precedent, which resolved the Executive/Worker
collision by recording the relationship rather than renaming shipped code
— with one difference that matters: ADR-0014 recorded a **synonym**,
because the two names meant the same role. This ADR records a
**distinction**, because they do not.

### D2 · Terminal and non-terminal

| State | Kind | Meaning |
|---|---|---|
| `WAITING` | non-terminal | Admitted; nothing is running, and that is correct (§8.2's four kinds) |
| `READY` | non-terminal | Admitted, envelope set, authority resolved; not yet executing |
| `EXECUTING` | non-terminal | Work is happening |
| `COMPLETED` | **terminal** | Every criterion verified (§3.8) |
| `FAILED` | **terminal** | A criterion cannot be met, established rather than assumed (§3.8) |
| `SUPERSEDED` | **terminal** | Replaced by a revised version; the original is retained (§3.8, §4.4) |

### D3 · `SUPERSEDED` is terminal and absolute

An objective never transitions out of `SUPERSEDED`. Replacing an objective
**creates a new objective and never mutates the old one.**

This is the same discipline the Kernel applies to warrants and for the
same stated reason (§4.4): *"the record of what was authorized must not be
editable after the fact."* Supersession preserves both sides — the
original terminates honestly, the revision carries the lineage, and the
receipts of both remain reachable.

### D4 · It is a constitutional vocabulary, not business logic

`ObjectiveState` is the **published** state carried in the Admission
Record and read by the Kernel. It is not the Objective Engine's internal
bookkeeping.

This is faithful to §10.1 — *"The Objective Engine's responsibility ends at
admission"* — and to §10.2, which shows the Admission Record as what
crosses the boundary. The Engine may track richer detail internally; what
it **publishes** is one of these six values.

**Consequence:** an objective that has not been admitted publishes no
Admission Record at all. There is no `DRAFT` in this vocabulary because a
draft has nothing to publish, and K1 refuses an unknown objective already
(Kernel Specification §7.2).

### D5 · K1 refuses on terminal only — **superseded and restated**

> **Superseded by Founder Decision, 2026-08-06.** The original D5 read
> that `READY` and `WAITING` refuse mints at K1, citing *"Kernel
> Specification §10.3."* **Both halves were wrong**, and both are
> corrected below. See `Engineering/CONFLICT_C15_PART2.md` for the
> analysis that produced the correction.
>
> **Citation.** The liveness gate — *"`state` | K1's liveness gate |
> Non-`EXECUTING` ⇒ no mints"* and *"K1 keeps refusing while the objective
> is not `EXECUTING`"* — is **Objective Engine Specification §10.2 and
> §10.3**, not the Kernel Specification. Kernel Specification §10.3 is
> *"The four invariants that make learning safe"*, a different subject.

**K1 is structural admission only.** Kernel Specification §7.2 K1 governs
the Kernel's own check and it refuses on exactly three conditions:

```
    objective missing · objective unknown · objective terminal
```

**K1 does not enforce `EXECUTING`.** `READY` and `WAITING` are
non-terminal and **pass K1**.

**The `EXECUTING` requirement is a minting prerequisite, not an admission
prerequisite**, and belongs to the mint decision path:

| Check | Question | Where |
|---|---|---|
| **K1** | Is this objective admitted and not finished? | **Structural admission** |
| **Mint** | Is this objective running right now? | **Lifecycle admission** |

Objective Engine Specification §10.2 and §10.3 are satisfied by the mint
path rather than by K1, so no clause in either document is contradicted.

**C8's `RefusalReason` is unchanged and requires no new member** — its
three objective reasons map one-to-one onto K1's three refusals, which is
what made this the resolution with no cost. C8 remains frozen at
`kalpavriksha-s1-c8.0`.

## Amendments this ADR carries

Both are recorded here rather than by editing the specification files, so
the change has one authoritative location and the specifications remain
diffable against their released versions.

### A1 · Objective Engine Specification — amends §4.1, §4.2 and §13.1

**§13.1 Conflict A is resolved.** The `Objective`/`Mission` collision is
closed by D1: two distinct vocabularies, neither defined in terms of the
other, `Mission State` untouched.

**§13.1 Conflict B is superseded, not ratified as written.** Conflict B
requested two additive states on the frozen Mission machine. **That
request is withdrawn.** Constitution §5.3 is not amended. `WAITING` and
`SUPERSEDED` exist instead in `ObjectiveState`, where they need no
amendment to a frozen document.

**§4.1's premise is amended.** The specification's statement that it *"uses
the frozen one"* — Constitution §5.3's machine — no longer holds for the
published state. It holds for Missions, which continue to use it.

**§4.2's lifecycle is retained as the Engine's internal description**, and
its published projection is D2's six values. The mapping of the internal
lifecycle onto the published vocabulary is **C17's to specify**; the two
mappings this ADR does not determine are named in O2 below.

**§13.1's blocking sentence is discharged.** *"This specification's
lifecycle cannot ship until it is ratified"* — it is now ratified.

### A2 · Kernel Specification — amends §7.2 K1

**§7.2 K1's refusal list is restated against the ratified vocabulary.**
K1 currently reads: *"Refuses: no objective · unknown objective · objective
already completed, failed, or cancelled."*

It becomes: **no objective · unknown objective · objective in a terminal
state**, where terminal is D2's `COMPLETED | FAILED | SUPERSEDED`.

**This changes no behaviour and no shipped code.** K1's requirement is
unchanged — *"resolves to an admitted objective in a non-terminal state."*
The enumeration is replaced by the partition, which is what the Kernel
actually tests. C8's shipped `RefusalReason.OBJECTIVE_TERMINAL` already
expresses exactly this and needs no change.

**Objective Engine Specification §10.2 and §10.3 are unchanged.** The
Admission Record's field set stands as written, and so does the liveness
gate — **satisfied by the mint path rather than by K1**, per D5 as
superseded. Kernel Specification §10.3 is a different subject entirely and
is not touched by this ADR.

### A3 · Constitution — **no amendment**

§5.3 and §17 are untouched. This is the point of the decision: a new,
separate vocabulary rather than an extension of a frozen one.

## Consequences

### Unblocked

| Component | Status | Why |
|---|---|---|
| **C11 Admission Record** | **UNBLOCKED** | `ObjectiveState` now exists as ratified vocabulary. The `state` field has six defined values and a determined terminal partition |
| **C15 Constitutional Kernel** | **UNBLOCKED** | Depended on C11 only. K1 needs *admitted?* and *non-terminal?*; D2 answers both |
| **C17 Objective Engine** | **UNBLOCKED** on the collision | §13.1's blocking sentence is discharged. One open item remains at O1, and it is narrower than the block it replaces |

### Preserved

- Constitution §5.3 and §17 unchanged.
- `MissionStatus` unchanged — eight members, same transition table.
- C1–C10 unchanged. No foundation component is modified by this ADR.
- C8's `RefusalReason` unchanged; `OBJECTIVE_TERMINAL` already matches A2.

### Terminology audit

Checked against Constitution §17's frozen terms and against `src/`:

| Name | In §17? | In `src/`? | |
|---|---|---|---|
| `ObjectiveState` | No | No | ✅ clean — and now explicitly distinguished from `Mission State` by D1 |
| `WAITING` · `READY` · `EXECUTING` · `COMPLETED` · `FAILED` · `SUPERSEDED` | No | Members of `MissionStatus` share four spellings | ✅ **Not a collision.** They are members of a different enum in a different module. `MissionStatus.EXECUTING` and `ObjectiveState.EXECUTING` are distinct values of distinct types, exactly as `AttestationVerdict.REFUSED` and a `RefusalReason` coexist today |

**`READY` is new to the project's vocabulary** — zero occurrences as a
state name in `src/`. It has no counterpart in `MissionStatus`, which
reduces rather than raises collision risk.

## Open items — recorded, not decided

Neither blocks C11, C15 or C17's vocabulary. Both are named here so they
are settled deliberately rather than discovered.

### O1 · §3.8 names four terminations; the ratified vocabulary has three terminal states

Objective Engine Specification §3.8 defines termination *"four ways, all
terminal, none reversible"*: **Completed · Failed · Cancelled ·
Superseded**. The ratified `ObjectiveState` has `COMPLETED`, `FAILED` and
`SUPERSEDED`. **There is no `CANCELLED`.**

§3.8 assigns cancellation to the founder alone — *"The founder no longer
wants it, or its premise evaporated"* — and it is distinct from the other
three: `FAILED` would be untrue (nothing failed), and `SUPERSEDED` implies
a replacement that does not exist.

**Why this does not block anything now.** K1 needs only the terminal /
non-terminal partition, and every state in D2 is classified. C11's record
and C15's check are complete without resolving it. C8's `OBJECTIVE_TERMINAL`
abstracts over which terminal state applies.

**Where it lands.** C17, which implements `terminate()` against §3.8. The
founder should decide before C17's brief whether cancellation is a seventh
state, or whether §3.8's four ways collapse to three in the published
vocabulary. **Stated as evidence, not as a recommendation** — this is the
same class of decision as the one this ADR records, and it is the
founder's.

### O2 · Two internal-to-published mappings are undetermined

D4 makes the published vocabulary a projection of §4.2's internal
lifecycle. Four mappings follow directly — `PLANNED/ADMITTED → READY`,
`EXECUTING → EXECUTING`, `WAITING → WAITING`, and the terminal states to
themselves. Two do not:

- **`AWAITING_APPROVAL`** — plausibly `WAITING`, matching §8.2's
  `awaiting_judgment` kind, but the decision is C17's.
- **`VERIFYING`** — whether an objective under verification publishes
  `EXECUTING` (permitting mints, which verification itself may need) or a
  non-executing state. Under D5 as superseded this no longer affects K1,
  which passes any non-terminal state; it now bears only on the mint
  path's lifecycle check.

**C17's brief must state both.** Neither affects C11: the Admission Record
carries whichever value the Engine publishes.

## Alternatives considered and rejected

| Alternative | Rejected because |
|---|---|
| Amend Constitution §5.3 to add `WAITING` and `SUPERSEDED` | Amends a frozen document to serve a component. The founder chose separation over extension |
| Reuse `MissionStatus` for objectives | Conflates two concepts and produces §13.1's *"third model of the same concept"* |
| Roadmap Amendment 001 M6 option (b) — a narrowed mintability indicator | Answers K1 but publishes less than §10.2 requires, and M6 itself rated it *"a design decision beyond the roadmap"* needing its own validation |
| Accept the block (M6 option c) | Sprint 1 stops after C12, C13, C14, C19, C20 and the Kernel never ships |

## References

- `Engineering/CONFLICT_C11.md` — the block this resolves
- `SPRING_1_IMPLEMENTATION_ROADMAP_v2_AMENDMENT_001.md` §2 M6, §6
- `SPRING_1_IMPLEMENTATION_ROADMAP_v2_AMENDMENT_002.md` — roadmap effect
- Objective Engine Specification §3.8, §4.1–§4.4, §8.2, §10.1–§10.3, §13.1
- Constitutional Kernel Specification §7.2 K1
- `Engineering/CONFLICT_C15_PART2.md` — the analysis that superseded D5
- Constitution §5.3, §17 — **unchanged**
- ADR-0014 — precedent for resolving a vocabulary collision without renaming shipped code
