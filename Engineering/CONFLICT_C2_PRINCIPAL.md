# Architectural Conflict — Sprint 1 Component 2 (Principal)

**Status:** **BLOCKING.** Implementation halted before any code was written.
**Date:** 2026-08-05
**Raised by:** Quality Gate Rule 000 — a change that resolves a contradiction silently does not leave the repository more trustworthy.
**Nothing implemented. Nothing modified. No architecture changed.**

---

## 1 · Summary

The Component 2 mission brief defines the Principal as:

> *"The permanent identity of Kalpavriksha during runtime… the digital identity that carries constitutional responsibility throughout execution."*
>
> *"The Principal is NOT: … the Founder"*
>
> *"The Principal should: own active Objectives … maintain constitutional state … survive runtime lifecycle"*

VEDA 04 defines a principal as **a human decision-maker — the founder, or a delegate.** These are not two descriptions of one thing. They differ on the single question the Principal exists to answer: **on whose authority does an action occur?**

Three distinct conflicts follow. Conflict 1 is constitutional. Conflicts 2 and 3 are structural.

---

## 2 · Conflict 1 — What a Principal *is*

### Evidence, frozen side

| Source | Text |
|---|---|
| VEDA 04 · M5 Relational | *"principals — **The founder, delegates**, their authorities and their own decision histories."* |
| VEDA 04 · R10 | *"The Bible assumes **one founder**. Delegation (C6) introduces a **second principal**"* — the first principal is therefore the founder |
| VEDA 04 · C6 | *"Routes classes of decision to named **humans** other than the founder, with their own receipts and defaults."* |
| VEDA 04 · §2 Auth/identity | *"Must represent delegates (CFO, Head of Eng) as approval **principals**, not merely as users."* |
| Kernel Spec · §4.3 | `actor` — *"Principal **on whose authority** this acts"* |
| Kernel Spec · §7.3 A5 | *"Who is acting, and **on whose authority**?"* → refuses when no principal resolves |
| Sprint 1 Plan · §5 C2 | `Principal: principal_id · display_name · kind: **founder \| delegate \| system**` |

### Evidence, brief side

> *"the permanent identity of **Kalpavriksha**"* · *"The Principal is NOT … the Founder"*

### Why this is constitutional and not cosmetic

VEDA 01 §10, Autonomy Constitution:

> *"The founder's authority is absolute and unconditional. **Every capability Kalpavriksha holds was granted**, is visible, and can be withdrawn instantly. **Autonomy is lent, never earned in a way that makes it permanent.**"*

A **permanent** identity belonging to **Kalpavriksha** that **carries constitutional responsibility** is, by construction, authority that was not granted by the founder and cannot be withdrawn from it. That is the precise thing VEDA 01 §10 forbids.

If Kalpavriksha is the principal, then Kalpavriksha acts on its own authority. Every receipt would record Kalpavriksha as the actor, and the ledger would no longer answer *"who authorized this?"* — it would answer *"which program ran?"*, which the execution log already answers.

**This is not a naming disagreement. The two readings produce receipts that mean different things.**

---

## 3 · Conflict 2 — Ownership of Objectives

The brief: *"The Principal should own active Objectives."*

| Source | Text |
|---|---|
| Objective Engine Spec · §3.3 | *"**The founder owns every objective**, unconditionally, from admission to termination. Ownership is never delegated, transferred, or inferred."* |
| Objective Engine Spec · §10.2 | The Objective Engine publishes the Admission Record; **the Kernel's K1 reads it** to decide whether a warrant may be minted |
| Constitution · §16 | Every component appears exactly once. One home per concern. |

If the Principal holds active Objectives, two components hold objective state, and K1 has two possible sources for *"is this objective admitted and live?"* Two sources of truth for a Kernel precondition is the failure mode §16 exists to prevent, and it is the same class of defect as the two-ledger problem the Execution Path Report already found.

---

## 4 · Conflict 3 — The brief contradicts itself on statefulness

Requested in the same list:

| Stateful | Stateless |
|---|---|
| *"own active Objectives"* | *"expose **immutable** identity"* |
| *"maintain constitutional state"* | *"never own business logic"* |
| *"survive runtime lifecycle"* | *"It is **identity, not intelligence**"* |

An object that owns live Objectives and maintains state across a runtime lifecycle is a stateful service. It cannot simultaneously be an immutable identity value. Additionally, Constitution §5.3 places Mission/Objective state in **Shared Infrastructure**, not in an identity object.

The left column and the right column cannot both be built.

---

## 5 · The two readings

I can see a charitable reading of the brief that mostly reconciles, and I would rather name it than assume it.

### Reading A — *Principal = the party on whose authority an action occurs*

`Principal` is an immutable value (`principal_id`, `display_name`, `kind`), resolved by a `PrincipalRegistry`. The founder is the first and currently only one. Kalpavriksha is never a principal; it acts *for* one.

Under this reading, *"NOT the Founder"* means *"the runtime record of the founder, not the human being"*, and *"owns active Objectives"* means *"is the recorded owner of"* rather than *"holds the collection."*

- Matches VEDA 04 M5, R10, C6, §2 · Kernel §4.3, A5 · Sprint Plan §5 C2 — **all of it, exactly**
- ~60 lines. Immutable dataclass plus a registry. No state, no lifecycle.
- Widens to delegation (C6) by adding rows, which is what R10 asked for

### Reading B — *Principal = Kalpavriksha's own runtime identity*

A stateful service owning active Objectives and constitutional state across the lifecycle.

- Contradicts VEDA 01 §10 (authority is lent, never held permanently by Kalpavriksha)
- Contradicts VEDA 04 M5/R10/C6/§2 (principals are humans)
- Contradicts Objective Engine §3.3 (the founder owns every objective)
- Creates a second holder of objective state, against Constitution §16
- Makes Kernel A5 unable to answer *"on whose authority"*
- Is internally inconsistent (§4)

**Reading B would require amending VEDA 04 and VEDA 01 §10. Neither is in scope, and both are frozen.**

---

## 6 · Recommendation

**Confirm Reading A, and I implement immediately.** The interface is already specified in `SPRING_1_IMPLEMENTATION_PLAN.md` §5 C2 and needs no design work:

```
Principal:          principal_id: str · display_name: str · kind: founder | delegate | system
PrincipalRegistry:  founder() -> Principal · resolve(id) -> Principal | None
```

Against the brief's acceptance criteria, Reading A satisfies every one:

| Criterion | Reading A |
|---|---|
| can be instantiated | ✅ |
| has immutable identity | ✅ frozen dataclass |
| can own Objectives | ✅ **as the recorded owner** — the Objective Engine holds the record, the Principal is what it names |
| cannot execute work | ✅ no method does anything |
| cannot authorize work | ✅ authorization is the Permission System's; the Principal is only *identified* by Kernel A5 |
| cannot mutate identity | ✅ frozen |
| integrates cleanly with Component 1 | ✅ no dependency on the Clock; both are `foundation/` primitives |

**If Reading B is genuinely intended**, this is not a Component 2 task. It is a constitutional amendment to VEDA 01 §10 and VEDA 04 M5/R10/C6, and it should go through the amendment process rather than arrive as an implementation brief.

---

## 7 · What was not done

No file created. No file modified. No test written. `foundation/` still contains only `clock.py` and `__init__.py`.

Component 1 and both its tags are untouched.

---

*Conflict report. Raised before implementation, as the mission brief instructs. Every citation verified against the frozen documents on 2026-08-05.*
