# Health Report — Sprint 1 Component 11: Admission Record

**Type:** Implementation health report. Working-directory evidence only.
**Date:** 2026-08-05
**Status:** Implementation complete. **Not committed, not tagged, no Rule 001, no self-audit.**
**Unblocked by:** ADR-0021 (ratified) · Amendment 002. `CONFLICT_C11.md` is resolved.

---

## 1 · What was built

| File | | Lines |
|---|---|---|
| `src/master_agent/foundation/admission.py` | new | 295 (56 AST statements) |
| `tests/test_foundation_admission.py` | new | 563 |
| `src/master_agent/foundation/__init__.py` | modified — **exports only** | +5 imports, +3 `__all__` |

**Public surface — 3 symbols**

```
ObjectiveState          closed enum, 6 — ADR-0021's ratified vocabulary
AdmissionRecord         frozen, 7 fields — §10.2's published record
InvalidAdmissionRecord  ValueError, raised at construction
```

**Fields** — §10.2 and Roadmap §2 C11, verbatim and in order:
`objective_id · state · consequence_ceiling · budget · deadline · required_authority · approval_ref`

Against the roadmap's `~200 source lines / ~45 tests`: **295 lines (56 statements) / 115 tests.**

---

## 2 · Test count

**115 passed, 0 failed** (0.16s).

Adversarial coverage as required: invalid `ObjectiveState` (5 bad types, plus a real `MissionStatus` member, plus 3 retired lifecycle spellings) · invalid envelope construction (missing fields, non-`Decimal` budget, `bool` budget, negative budget, naive deadline, non-datetime deadline, non-`ReversibilityClass` ceiling, 15 identifier cases) · serialization (7 tests incl. `Decimal`-through-JSON) · hashing · equality · immutability (7 fields + ceiling-raise + state-advance).

---

## 3 · Ruff

**All checks passed** on all three touched files. Max line 91 (module) / 81 (tests), limit 100. No repo-wide cleanup, no opportunistic fixes.

---

## 4 · Guards

| Gate | Result |
|---|---|
| Architecture guards (Rule 001 set, 6 modules) | **215 passed, 1 skipped, 0 failed** |
| C11 constitutional guards | included in the 115; all passed |

Constitutional guards cover: depends only on C4 · no clock · does not import the Objective Engine or Kernel · imports nothing that could act · cannot execute/admit/terminate · carries none of the Objective's internals · carries none of §5.2's deliberately-absent fields · exactly the seven published fields, in order · holds no runtime state · does not restate C4's vocabulary · reads no ambient time · **does not import the Mission vocabulary**.

---

## 5 · ADR-0021 implemented as ratified

| Decision | Implementation |
|---|---|
| **D1** two permanently separate vocabularies | `admission.py` imports nothing from `mission_manager`; construction **refuses a `MissionStatus` member** with a message naming the separation |
| **D2** terminal partition | `COMPLETED · FAILED · SUPERSEDED` terminal; `WAITING · READY · EXECUTING` not. Partition proven complete and disjoint by test |
| **D3** `SUPERSEDED` terminal and absolute | Terminal by D2; the record is frozen, so a state cannot be advanced in place — a change is a new published record |
| **D4** published vocabulary, no `DRAFT` | Six values only; a parametrized test asserts `draft`, `planned`, `awaiting_approval`, `verifying`, `cancelled` are all absent |
| **D5** §10.3's gate unchanged | Only `EXECUTING` opens it. `READY` and `WAITING` are non-terminal and still open nothing — asserted as a strict subset |

---

## 6 · One naming change the guards forced

The property that answers §10.3's gate was first written as `permits_minting`. The forbidden-verb guard rejected it, and **the guard was right**: a value object exposing `permits_*` reads as granting authority, which is exactly what this record must not do — the Kernel decides.

Renamed to **`is_executing`**, on both `ObjectiveState` and `AdmissionRecord`. It states the fact; §10.3's rule that a non-`EXECUTING` objective mints nothing stays with the Kernel. No behaviour changed.

Also corrected during implementation: one test asserted the separation from `MissionStatus` by scanning raw source text, which failed because the docstring *names* `Mission State` precisely to record the separation. Rewritten to inspect the module's actual imports via AST. And `FURB157` on `Decimal("-1")` → `Decimal(-1)`, matching the C5 ruling and C6's shipped convention.

---

## 7 · New risks

| # | Risk | Severity | Note |
|---|---|---|---|
| **R21** | **`budget` carries no currency.** §5.1 types it only as *"value — Spend and/or provider-time ceiling"*, and Roadmap §2 C11 declares seven fields. An eighth (`budget_currency`) would exceed the declared API, and C6's `Cost` — which does pair amount with currency — is **not** an available dependency: both Roadmap §2 C11 and Amendment 001 §5 declare C4 only | Low | Deliberate. A bare `Decimal` is unambiguous in a single-currency system. If multi-currency is ever real, the field set is a founder/roadmap change, not a C11 fix |
| **R22** | **The envelope's time half is `deadline` alone.** §5.1's objective model carries `due_date \| review_date` with *"at least one mandatory"*; the published record carries one `deadline`. Which of the two an Engine publishes is **C17's** to specify | Low | C11 is complete either way — it carries whichever the Engine publishes |

Both are recorded so C15/C17 settle them deliberately.

---

## 8 · Blockers

**None.**

`ADR-0021 O1` (no `CANCELLED` against §3.8's four terminations) and `O2` (the `AWAITING_APPROVAL` / `VERIFYING` mappings) remain open by design and land on **C17**. Neither affects C11: the terminal partition is complete over the six ratified values, and C8's shipped `RefusalReason.OBJECTIVE_TERMINAL` already abstracts over which terminal state applies.

**C15's remaining prerequisites are now C13 and C14.**

---

## 9 · Preservation

C1–C10 untouched. Only `foundation/__init__.py` changed outside C11's own files, exports only. Constitution §5.3/§17, `MissionStatus`, the specifications, the roadmap and both amendments all unmodified. No commit, no tag.

**STOP.**
