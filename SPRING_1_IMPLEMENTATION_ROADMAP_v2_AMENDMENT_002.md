# Sprint 1 Roadmap v2 — Amendment 002

**Type:** Blocker removal. No code, no commits, no tags, no architecture designed.
**Date:** 2026-08-05
**Amends:** `SPRING_1_IMPLEMENTATION_ROADMAP_v2.md` §2 C11, §5 R1, and §4's order — and **Amendment 001 §2 M6, §5, §6 and §8**.
**Authority:** This amendment is authoritative where it differs from the roadmap or from Amendment 001. Neither is modified.
**Trigger:** Founder ratification of `ObjectiveState`, recorded in **ADR-0021**.

---

## 1 · What changed

**One decision closed the project's longest-standing blocker.**

ADR-0021 introduces `ObjectiveState` as a **distinct constitutional
vocabulary** — `WAITING · READY · EXECUTING · COMPLETED · FAILED ·
SUPERSEDED` — permanently separate from Constitution §17's frozen
`Mission State`, which is untouched.

That resolves both halves of the block Amendment 001 §2 M6 recorded:

| M6's half | Resolved by |
|---|---|
| The `Objective`/`Mission` collision — *"`Mission State` is a frozen §17 term, and `ObjectiveState` sits directly beside it"* | ADR-0021 **D1** — two distinct vocabularies, neither defined in terms of the other, §5.3 and §17 unchanged |
| Conflict B — *"the frozen Mission state machine lacks `WAITING` and `SUPERSEDED`; both need ratification"* | ADR-0021 **A1** — the amendment request is **withdrawn**. Both states exist in `ObjectiveState`, so no frozen document is amended |

M6 offered three options. **The founder took option (a) — ratify** — which
M6 §10 recommended and which unblocks C11, C15 and C17 together.

---

## 2 · Amendment 001 §6's terminology caution is discharged

Amendment 001 §6 carried:

> | `ObjectiveState` | Sits directly beside frozen §17 **`Mission State`**. Same ADR as M6. **Do not introduce it before that is settled.** |

**It is now settled.** The instruction is discharged and `ObjectiveState`
may be introduced. ADR-0021's terminology audit confirms zero collisions:
the four state names it shares with `MissionStatus` are members of a
different enum in a different module, which is the same coexistence
`AttestationVerdict.REFUSED` and `RefusalReason` already have in shipped
code. `READY` is new to the project and has no counterpart at all.

---

## 3 · Corrected status — C11, C15, C17

Bold marks a change from Amendment 001 §5.

| # | Component | Dependencies | Buildable |
|---|---|---|---|
| **C11** | Admission Record | C4 `ReversibilityClass` — **⚠ removed** | **now ✅** |
| **C15** | Constitutional Kernel | C1, C2, C4, C5, C6, C7, C8, C9, C10, C11, C12, C13, C14 | **after C11, C13, C14 ✅** |
| **C17** | Objective Engine | C11, C15, C8 — **⚠ blocked on ADR removed** | **after C15 ✅** |

**No component in Sprint 1 is blocked on an unresolved ADR.**

---

## 4 · Corrected implementation order

Amendment 001 §8.1's order now applies unconditionally — its stated
condition was *"if and only if M6 resolves via option (a) or (b)"*, and
option (a) has been taken.

Accounting for what has shipped since Amendment 001:

```
  shipped:   C1 · C2 · C3 · C4 · C5 · C6 · C7 · C8 · C9 · C10 · C12
  remaining: C11 → C13 → C14 → C15 → C16 → C17 → C18 → C19 → C20 → C21
```

**C11 moves to the front of the remaining work**, because C15 depends on
it and C15 is the sprint. C13 and C14 are the Kernel's other two
outstanding prerequisites; C19 and C20 remain independent and may move
freely.

**Amendment 001 §8.2's "hard stop" scenario is void.** It described the
sprint stalling after seven components with *"every component after the
stop [being] the half that matters."* That stop no longer exists.

---

## 5 · Risk register effect

| # | Risk | Status |
|---|---|---|
| **R1** | *"`Objective`/`Mission` ADR still unratified. C17 cannot begin… **the longest-standing blocker in the project**"* — Roadmap §5, Critical | **CLOSED.** Ratified 2026-08-05 as ADR-0021 |
| **M6** | Amendment 001, Critical | **CLOSED** by option (a) |
| **D1** | `DEMO_RISK_REGISTER.md` — *"the ADR is the difference between a Kernel and no Kernel"*, Fatal/High | **CLOSED** |

**The binding constraint on 12 Aug is now D2 — scope and velocity — not
an unresolved decision.** That is a materially better position: D2 is an
engineering and scope question with known levers, where D1 was a decision
nobody but the founder could make.

---

## 6 · One open item, carried forward

**ADR-0021 O1 — §3.8 names four terminations; the ratified vocabulary has
three terminal states.**

Objective Engine Specification §3.8 defines termination *"four ways"* —
Completed · Failed · **Cancelled** · Superseded. `ObjectiveState` has no
`CANCELLED`.

**This blocks nothing now.** K1 needs only the terminal / non-terminal
partition, which ADR-0021 D2 determines completely, and C8's shipped
`RefusalReason.OBJECTIVE_TERMINAL` already abstracts over which terminal
state applies. C11's record and C15's check are complete without it.

**It lands on C17**, which implements `terminate()` against §3.8. **Decide
before C17's brief**, per ADR-0021 O1. ADR-0021 O2 records two further
mappings — `AWAITING_APPROVAL` and `VERIFYING` — that C17's brief must
also state.

**Severity: Medium, and narrower than what it replaces.** A Critical
blocker on three components has become a Medium open item on one.

---

## 7 · What this amendment does not do

`SPRING_1_IMPLEMENTATION_ROADMAP_v2.md` and
`SPRING_1_IMPLEMENTATION_ROADMAP_v2_AMENDMENT_001.md` are **left
untouched**. Constitution §5.3 and §17 are **unchanged**. No specification
file was edited — ADR-0021 carries both specification amendments as
numbered clauses so the change has one authoritative location.

No component was implemented. C11 has **not** been started.

---

*Blocker removal. No code, no commits, no tags. Produced against ADR-0021, `Engineering/CONFLICT_C11.md`, Roadmap v2, Amendment 001, the Constitutional Kernel Specification and the Objective Engine Specification on 2026-08-05.*
