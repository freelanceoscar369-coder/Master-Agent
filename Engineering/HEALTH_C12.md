# Health Report — Sprint 1 Component 12: Reversibility Registry

**Type:** Implementation health report. Working-directory evidence only.
**Date:** 2026-08-05
**Status:** Implementation complete. **Not committed, not tagged, no Rule 001, no self-audit.**

> C11 skipped per brief — blocked, documented in `CONFLICT_C11.md`, not revisited.

---

## 1 · What was built

| File | | Lines |
|---|---|---|
| `src/master_agent/foundation/reversibility.py` | new | 360 (81 AST statements) |
| `tests/test_foundation_reversibility.py` | new | 560 |
| `src/master_agent/foundation/__init__.py` | modified — **exports only** | +6 imports, +4 `__all__` |

**Public surface — 4 symbols**

```
Classification           frozen: capability, cls, compensating_capability, undo_window
ReversibilityRegistry    register / classify / is_classified / capabilities / attest
Unclassified             LookupError — the fail-closed path
InvalidClassification    ValueError, raised at construction
```

Against the roadmap's `~200 source lines / ~45 tests`: **360 lines (81 statements) / 73 tests.**

---

## 2 · Test count

**73 passed, 0 failed** (0.07s).

Includes the roadmap's required coverage test — `test_every_registered_capability_is_classified`.

---

## 3 · Ruff

**All checks passed** on all three touched files. Max line 89 (module) / 87 (tests), limit 100.

Two findings arose in my own new files and were fixed: `I001` (import block — `refusal` sorts before `reversibility`) and `RUF022` (`__all__` — `Classification` after `AttestationVerdict`). No repo-wide cleanup, no opportunistic fixes.

---

## 4 · Guards

| Gate | Result |
|---|---|
| Architecture guards (existing Rule 001 set, 6 modules) | **215 passed, 1 skipped, 0 failed** |
| C12 constitutional guards | **11 passed** |

Constitutional guards cover: dependency set is exactly C4 + C7 · no clock · imports nothing that could act · cannot execute or authorize · decides nothing about permission · holds no callable · reads no ambient time · does not restate C4's vocabulary · `Unclassified` is not a `ValueError` · registry exposes no mutator · registry has no instance dict.

---

## 5 · Decisions taken (both from authoritative documents, neither invented)

**M7 — the registry constructs the A2 attestation.** Roadmap §2 C12 already declares *"C7 Attestation (it produces the A2 attestation)"*, and Amendment M7's recommendation agrees: *"the registry constructs it… `Attestation` imports nothing, so the coupling is to a leaf."* Two authoritative documents point the same way, so this was not treated as an open decision.

**The registry is immutable.** `register()` returns a new registry; there is no mutator. Follows `PrincipalRegistry` (C2), which takes its entries at construction. Grounded in §8.3 — *"reversibility class changing"* requires a **new Intent**, not a silent substitution.

**Two fail-closed paths, not one.** `classify()` raises `Unclassified`; `attest()` returns a **REFUSED** attestation. §7.5 requires refusals to be recorded, so the Kernel gets an answer it can carry into a receipt rather than an exception to translate. Neither represents "probably reversible".

---

## 6 · Structural invariants

VEDA 04 A2's invariant — *"'probably reversible' cannot be represented"* — is enforced at construction, per class:

| Class | Compensating capability | Undo window |
|---|---|---|
| `READ_ONLY` | refused | refused |
| `REVERSIBLE` | **required** | refused |
| `REVERSIBLE_UNTIL` | **required** | **required, strictly positive** |
| `IRREVERSIBLE` | refused (§8.4) | refused |

Also structural: non-empty capability name · `cls` must be a `ReversibilityClass` · `undo_window` must be a `timedelta` · a capability may not be classified twice, at construction or via `register()`.

---

## 7 · New risks

| # | Risk | Severity | Note |
|---|---|---|---|
| **R19** | **The classification audit is not done.** The roadmap defines C12 as the registry *"plus a one-time classification audit of ~30 shipped capabilities"* and calls it *"the expensive half."* **24 action modules exist in committed code.** The registry ships empty | **High** | **Deliberate.** Each capability needs a class *and a working compensating action*, which is founder/architect judgment. A guessed classification is worse than none: an unclassified capability fails closed safely, a wrongly-classified one mints warrants under a false class. Populating it is a data exercise, not a code change — the registry is ready to receive it |
| **R20** | **`compensating_capability` is an unresolved name.** The registry says *what* undoes an action, never that the named capability exists or is itself classified | Low | Deliberate — resolving it would need a Capability Registry dependency C12 does not have. Cross-checking belongs where both registries meet (C15/C16) |

---

## 8 · Blockers

**None for C12.**

C11 remains blocked (`CONFLICT_C11.md`), which still blocks C15 and C17. C13, C14, C19, C20 remain buildable.

---

## 9 · Preservation

C1–C10 untouched. Only `foundation/__init__.py` changed outside C12's own files, exports only. No roadmap, specification or ADR modified. No commit, no tag.

**STOP.**
