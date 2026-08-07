# Roadmap Consistency Status — C9 to C21

**Type:** Consistency audit. **The roadmap is NOT changed. No code, no commits, no tags.**
**Date:** 2026-08-05
**Sources audited:** `SPRING_1_IMPLEMENTATION_ROADMAP_v2.md` · `SPRING_1_IMPLEMENTATION_ROADMAP_v2_AMENDMENT_001.md`
**Verified against:** Constitutional Kernel Specification · Objective Engine Specification v1.0 · VEDA 01–04 · Constitution §17 · the shipped source at `kalpavriksha-s1-c8.0`
**Baseline:** C1–C8 GREEN. Thirteen components remain.

---

## 0 · Summary

| Status | Components |
|---|---|
| **Confirmed — buildable, dependencies verified** | **C10 · C12 · C13 · C14 · C19 · C20** (6) |
| **Confirmed, awaiting a founder decision on one field** | **C9** (1) |
| **Blocked — founder decision required** | **C11 · C15 · C17** (3) |
| **Confirmed, gated on a predecessor** | **C16 · C18 · C21** (3) |

**Two new findings this pass**, neither previously recorded:

| # | Finding | Severity |
|---|---|---|
| **N1** | **`Warrant.warrant_id` deviates from Objective Engine Spec §13.1's ratified amendment**, which requires the field to stay `intent_id`. VEDA 04 A1's `intentId` is no longer preserved verbatim anywhere in code. **Lands on C13.** | **High** |
| **N2** | **Amendment 001 contradicts itself on C9's C7 dependency** — §5's table says the `Attestation` type, §3 M8's prose says the enum only | Low |

N2 was raised in `C9_IMPLEMENTATION_PRECHECK.md` §5.2 and is repeated here for completeness. **N1 is new.**

---

## 1 · Dependency audit — every remaining component

Bold marks a correction the amendment made to the roadmap. **Verified** means re-derived from a frozen document or measured in the shipped source, not read from the roadmap.

| # | Component | Amendment's corrected dependencies | Verified | Status |
|---|---|---|---|---|
| **C9** | Execution Request | C6, C7, **~~C2~~** *(pending M8)* | ⚠ N2 — type vs enum | **Founder decision** |
| **C10** | Attempt Token | **nothing** | ✅ Kernel Spec §3.5 takes an id | **Confirmed** |
| **C11** | Admission Record | C4 `ReversibilityClass` | ✅ | **BLOCKED — M6** |
| **C12** | Reversibility Registry | C4, C7 *(pending M7)* | ✅ | **Confirmed + decision** |
| **C13** | Receipt Ledger | C1, C5, **C6**, StateStore — **~~C7~~** | ✅ `persistence/store.py:28` committed | **Confirmed + N1** |
| **C14** | Override | nothing | ✅ | **Confirmed** |
| **C15** | Constitutional Kernel | C1, C2, C4, C5, **C6**, C7, C8, C9, C10, C11, C12, C13, C14 | ✅ | **BLOCKED via C11** |
| **C16** | Execution Path Unification | C15 | ✅ | Gated on C15 · **R3** |
| **C17** | Objective Engine | C11, C15, C8 | ✅ | **BLOCKED — ADR** |
| **C18** | Learning Subscriber | C15, EventBus — **~~C13~~** | ✅ `mission_control/events.py:125` committed | Gated on C15 |
| **C19** | Vigilance Attestation | C1 Clock | ✅ | **Confirmed** *(M9)* |
| **C20** | Voice Charter Validator | nothing | ✅ | **Confirmed** |
| **C21** | Dashboard State | C13, C15, C17, C19, C20 | ✅ ADR-0016 exists | Gated, last |

### 1.1 Shipped dependencies — verified present *and committed*

Three components depend on things the roadmap marks *"exists, shipped."* All three verified in committed history at `c8.0`, not merely in the working directory:

| Claimed by | Dependency | Verified |
|---|---|---|
| C13 | `persistence.StateStore` | ✅ `src/master_agent/persistence/store.py:28` — `class StateStore(Protocol)`, committed |
| C18 | `mission_control.events.EventBus` | ✅ `src/master_agent/mission_control/events.py:125` — committed |
| C21 | `dashboard/readmodel.py` (ADR-0016) | ✅ committed; `docs/adr/0016-dashboard-data-contract.md` present |

**No remaining component depends on anything that does not exist.**

### 1.2 Amendment corrections — all six re-verified

| # | Correction | Re-verified this pass |
|---|---|---|
| **M1** | C13 depends on C6, not C7 | ✅ VEDA 04 A1's contract carries the quartet; no attestation appears in A1 |
| **M2** | C18 does not depend on C13 | ✅ Kernel Spec §10.3 — the Kernel writes then publishes; subscribers hold no ledger reference |
| **M3** | C15 must include C6 | ✅ §4.3 lists `consequence`; A1's `recordIntent` takes one |
| **M4** | C10 depends on nothing | ✅ §3.5 `attempt(intent_id)` takes an id, not a warrant |
| **M5** | C8 — attestor optional, three families | ✅ **Implemented and GREEN at `c8.0`.** M5 was correct in full |
| **M6** | C11 is blocked | ✅ Objective Engine Spec §13.1 Conflict B — unchanged, still open |

**All six corrections hold.** M5 is now proven by construction rather than by argument.

---

## 2 · Terminology audit

### 2.1 Confirmed clean

All fourteen names from Amendment §6, plus the two C8 introduced, re-checked against Constitution §17 and the shipped source:

```
RefusalReason ✅   KernelRefusal ✅   KernelCheck ✅      RefusalFamily ✅
ActionClass ✅     ExecutionRequest ✅ AttemptToken ✅     Classification ✅
ReversibilityRegistry ✅  ReceiptLedger ✅  LedgerUnavailable ✅
OverrideSwitch ✅  DomainRegistry ✅  ValidationResult ✅
ObjectiveState ⚠   AdmissionRecord ✅
```

**Zero collisions**, except `ObjectiveState` — flagged by Amendment §6 and blocked by the same ADR as M6.

### 2.2 N1 — the `Warrant` / `Intent` / `intentId` chain, and where it broke

**This is the new finding, and it is the one that matters.**

Objective Engine Spec §13.1 Conflict A recorded that `Intent` meant three things, and ratified a rename:

> *"Rename the Kernel's token type from `Intent` to **`Warrant`**. **The field it carries stays `intent_id`**, preserving VEDA 04 A1's `intentId` verbatim."*

**The type rename was applied. The field instruction was not.** Shipped C4:

```python
#: This warrant's identity. The same value VEDA 04 A1's
#: `recordIntent()` returns as `intentId` — one event, one identifier.
#: Named `warrant_id` to match `ExecutionContext.warrant_id`, shipped in
#: Component 2.
warrant_id: str
```

C4 named it `warrant_id`, gave a reason — consistency with `ExecutionContext.warrant_id` from C2 — and documented the equivalence. That is honest, and the milestone is GREEN and frozen.

**But the consequence is real.** VEDA 04 A1's contract is:

```
recordIntent(actor, actionType, reversibilityClass, expectedEffect, consequence, ruleRef?) → intentId
recordOutcome(intentId, result, actualEffect)
```

**`intentId` now exists in no field name anywhere in the codebase.** The equivalence lives in one docstring in `warrant.py`.

**Where it lands: C13 Receipt Ledger.** C13 implements `recordIntent` / `recordOutcome`. Its brief must state explicitly which name the API uses and record the bridge, or the ledger will either contradict VEDA 04 A1's contract or reintroduce `intent_id` beside `warrant_id` and create the third synonym Constitution §17's Worker/Executive and Provider/Reasoning Provider rows both forbid.

**Precedent exists and should be followed:** ADR-0014 resolved the Executive/Worker collision by recording a synonym rather than renaming shipped code. The same treatment fits here.

**Severity: High.** Not a blocker for any component before C13, and **not grounds to modify C4** — C4 is frozen, documented, and GREEN. It needs an ADR, not a rename.

### 2.3 The `Intent` collision — status

| Meaning | Source | Status |
|---|---|---|
| Structured goal + constraints + criteria | Constitution §3.1, shipped `planner/plan.Intent` | **Frozen.** Untouched |
| Receipt ledger's first-phase identifier `intentId` | VEDA 04 A1 | **Frozen**, but see N1 — no longer in code |
| The Kernel's authorization token | Kernel Spec §4 | **Resolved** — renamed `Warrant`, shipped at `c3.0` |

**Two of three resolved. The third is N1.**

---

## 3 · Blocked items

### 3.1 The single root blocker

| | |
|---|---|
| **What** | The `Objective` / `Mission` terminology ADR |
| **Recorded** | Implementation Blueprint §10 R7 · Objective Engine Spec §13.1 Conflict B · Roadmap §5 R1 · Amendment M6 |
| **Blocks** | **C11 · C15 · C17** — three components including the Kernel |
| **Why C11** | It carries `ObjectiveState`, and `Mission State` is a frozen §17 term sitting directly beside it |
| **Why C15** | C15 depends on C11. Amendment M6: *"The Kernel is blocked after all, by a longer route than the roadmap avoided"* |
| **Why C17** | Its lifecycle would become a third model of the same concept |
| **Age** | Longest-standing open item in the project |
| **Precedent available** | ADR-0014 — Executive/Worker, resolved with a synonym rather than a rename |

**Conflict B additionally requires two states — `WAITING` and `SUPERSEDED` — that the frozen Constitution §5.3 machine lacks.** Both are additive; nothing is removed and no existing transition is deleted.

### 3.2 Amendment M6's three options, unchanged

| Option | Effect | Cost |
|---|---|---|
| **(a) Ratify the ADR** | Unblocks C11, C15 **and** C17 together | One ADR. **Recommended by M6 §10** |
| **(b) Narrow the record** | C11 carries a mintability indicator answering only K1's two questions | Unblocks C11 and C15 without the ADR, but is a **design decision beyond the roadmap** needing its own validation |
| **(c) Accept the block** | C11 and C15 wait for C17 | Sprint 1 stalls once C9, C10, C12, C13, C14, C19, C20 are exhausted |

### 3.3 What remains buildable under option (c)

```
C9 → C10 → C12 → C13 → C14 → C19 → C20        ← seven components, no blocker
    ────────── hard stop ──────────
C11 → C15 → C16 → C17 → C18 → C21             ← six, all wait on ratification
```

**Seven of thirteen. C8 is now green, so the count is one lower than Amendment §8.2's eight.** Every component after the stop is the half that produces the Founder Edition proof.

---

## 4 · Founder decisions

| # | Decision | Blocks | Recommendation | Source |
|---|---|---|---|---|
| **M6** | Ratify the `Objective`/`Mission` ADR — option (a), (b) or (c)? | **C11, C15, C17** | **(a) Ratify.** Removes the longest-standing blocker and unblocks three components at once | Amendment §2 M6, §10 |
| **M8** | C9: `principal: Principal` or `principal_id: str`? | **C9** | **`principal_id: str`** — an `ExecutionRequest` becomes a `Warrant`, and shipped `Warrant.principal_id` is typed `str` | Amendment §3 M8; evidence in `C9_IMPLEMENTATION_PRECHECK.md` §5.1 |
| **M7** | C12: does the Reversibility Registry construct `Attestation`s, or answer `classify()` with an adapter? | **C12** | **Registry constructs it.** Eight attestors each needing an adapter is seven more components than the sprint has room for, and `Attestation` imports nothing | Amendment §3 M7 |
| **N1** | C13: which name does `recordIntent` return — `warrant_id`, `intent_id`, or both via an ADR? | **C13** | **An ADR recording the synonym**, following ADR-0014's precedent. **Do not rename C4** | §2.2 above — **new** |
| **N2** | C9: does `attestations` carry `Attestation` objects or questions? | C9 | **Objects.** Determinable from §7.3; needs a sentence in C9's brief, not a decision | `C9_IMPLEMENTATION_PRECHECK.md` §5.2 |
| **E3** | Commit the frozen specifications? | Rule 002 auditability | **Yes, first** | `ENGINEERING_DOCUMENT_POLICY.md` §5 |

**M6 is the only one that blocks more than one component, and it blocks the Kernel.**

---

## 5 · Assumptions that must never be guessed

Each of these has already been guessed wrong once, or is positioned to be. **Every one must be read from a frozen document at brief time, never recalled.**

| # | Assumption | Why it must not be guessed | Evidence |
|---|---|---|---|
| **A1** | **A component's declared dependency in the roadmap** | Amendment 001 found **six wrong** out of fourteen. The error rate on this document is 43% | R11; ED-018 found C7's dependency wrong on the first component built from the roadmap |
| **A2** | **Who attests a question** | C7's roadmap entry named `Principal` as the attestor. All eight §7.3 attestors are **components**. Building it as declared would have placed a human authority where a component belongs | ED-018 |
| **A3** | **Whether a value is optional** | Roadmap says C9's `consequence` is *"optional, pending B1."* Kernel Spec §14.1 says the opposite verbatim: *"never null, never omitted"* | §14.1; Amendment M1's identical note for C13 |
| **A4** | **Which name a frozen contract uses** | N1. `intentId` is VEDA 04 A1's; the code says `warrant_id`; the equivalence lives in one docstring | §2.2 |
| **A5** | **Whether a term is frozen** | `Mission State` is frozen §17; `ObjectiveState` sits beside it. Introducing it before ratification creates a collision no later rename undoes cheaply | Amendment §6; Objective Engine Spec §13.1 |
| **A6** | **Which components exist versus which vocabularies exist** | Roadmap §1.1 names three pairs conflated this way — `ReversibilityClass` vs the Registry, `Receipt` vs the Ledger, `Consequence` vs the Engine. *"The single most likely way this roadmap is misread"* | Roadmap §1.1 |
| **A7** | **Where a §11 failure condition is refused** | §11.1 places the Permission System's answer at A3, §11.5 the Worker's at A1/A6, §11.6 the Provider's at A7. Getting one wrong produces a refusal that names the wrong authority in a permanent record | Kernel Spec §11; enforced structurally in C8's `_PERMITTED_CHECKS` |
| **A8** | **Whether a report's figure is reproducible** | The C7 report's `507 passed` cannot be reproduced at its own tag, and the C8 report mis-diagnosed why | `RULE001_CLARIFICATION.md` §2.1 |

---

## 6 · Roadmap estimates — measured against actuals

Reported because the calibration is drifting in one direction, and a brief written to these numbers will be wrong the same way.

| # | Component | Est. source | Actual | Est. tests | Actual |
|---|---|---|---|---|---|
| C7 | Attestation | ~180 | 280 | ~50 | 66 |
| C8 | Kernel Refusal | ~130 | 379 *(107 executable)* | ~35 | **108** |

**Source estimates are roughly right when measured as executable lines** — C8 came in at 107 against ~130 — and roughly half the total once the project's documentation density is included.

**Test estimates are low, and increasingly so:** C7 ran 1.3×, C8 ran 3.1×. Both overruns have the same cause — enforcing invariants at construction, with exhaustive parametrized coverage, rather than checking them downstream. That is the house pattern, and the roadmap's estimates predate it.

**Not a defect in the roadmap; a calibration note.** Remaining test estimates should be read as lower bounds. On the roadmap's ~730 remaining tests, a 2× factor is ~1,460 — which affects schedule, and therefore the 12 Aug date.

---

## 7 · What was not done

Neither roadmap file was modified. No amendment was written. No component was implemented, no decision was taken on the founder's behalf, and no dependency was changed. N1 was **recorded**, not resolved, and C4 was **not** touched.

---

*Consistency audit conducted against both roadmap documents, the Constitutional Kernel Specification, Objective Engine Specification v1.0, Constitution §17, the ADR index, and the shipped source at `kalpavriksha-s1-c8.0` on 2026-08-05. Every "verified" claim was measured or read from a frozen document; none was recalled.*
