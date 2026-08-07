# Health Report — Sprint 1 Component 14: Override

**Type:** Implementation health report. Working-directory evidence only.
**Date:** 2026-08-05
**Status:** Implementation complete. **Not committed, not tagged, no Rule 001, no self-audit.**

---

## 1 · What was built

| File | | Lines |
|---|---|---|
| `src/master_agent/foundation/override.py` | new | 184 (23 AST statements) |
| `tests/test_foundation_override.py` | new | 435 |
| `src/master_agent/foundation/__init__.py` | modified — **exports only** | +4 imports, +2 `__all__` |

**Public surface — 2 symbols**

```
OverrideSwitch    frozen: suspended, reason
                  suspend(reason) · resume() · is_suspended · as_dict()
InvalidOverride   ValueError, raised at construction
```

Against the roadmap's `~90 source lines / ~25 tests`: **184 lines (23 statements) / 58 tests.** The statement count is genuinely small; the line count is documentation, because §11.8's prohibitions are each a field someone will eventually propose adding.

**Immutable formulation, per this brief.** Roadmap §2 C14 declares `suspend(reason) / resume() / is_suspended()`; those names are preserved exactly, with `suspend()` and `resume()` returning a **new** switch rather than mutating — the same treatment the Reversibility Registry received, and following `PrincipalRegistry` (C2).

---

## 2 · Test count

**58 passed, 0 failed** (0.10s).

Adversarial coverage: 7 non-boolean suspension values · 3 blank and 3 non-string reasons · reason-on-running refused · reason-missing-on-suspended refused · signature introspection for confirmation and friction parameters · immutability (2 fields + in-place lift) · equality · hashing · serialization.

---

## 3 · Ruff

**All checks passed** on all three touched files. Max line 77 (module) / 86 (tests), limit 100. No repo-wide cleanup, no opportunistic fixes.

---

## 4 · Guards

| Gate | Result |
|---|---|
| Architecture guards (Rule 001 set, 6 modules) | **215 passed, 1 skipped, 0 failed** |
| C14 constitutional guards | included in the 58; all passed |

The three prohibitions are enforced by **signature introspection**, not by review:

| Prohibition | Source | Guard |
|---|---|---|
| **No confirmation** | §11.8 — *"no confirmation parameter in its signature, matching VEDA 04's requirement that none exist"* | `test_no_signature_carries_a_confirmation_parameter` walks every public method's parameters against 12 confirmation words; `resume()` asserted to take **no** argument; `suspend()` asserted to take **exactly** `reason` |
| **No friction** | VEDA 04 A3 — *"suspension latency measured in milliseconds, not in a job cycle"* | 11 friction words checked against both fields and parameters — delay, cooldown, grace, timeout, expiry, retry, throttle, debounce |
| **No persuasion** | VEDA 01 §10 | 9 words checked across the whole surface; `reason` is carried verbatim, never composed |

Plus: imports **nothing** from `master_agent` at all (A3's *"reachable when the rest of the system is degraded"*) · no clock · carries nothing about work, queues or counts (§11.8, §7.5) · cannot mint, invalidate, execute or revoke.

---

## 5 · Structural invariants

| # | Invariant | Grounding |
|---|---|---|
| 1 | `suspended` must be a real `bool` — not `1`, not `"yes"` | The type, not the truthiness. A switch built from `1` would read as suspended without anyone having said so |
| 2 | Suspended ⇒ non-empty `reason` | The founder is owed a sentence, not a silent stop |
| 3 | Running ⇒ `reason is None` | A reason outliving its suspension explains a condition that no longer holds |
| 4 | `suspend()` never refuses, including when already suspended | VEDA 01 §10 — the gesture *"must never be discouraged"*. Refusing would be friction |
| 5 | `resume()` never refuses and takes no argument | Nothing gates resumption |
| 6 | Frozen, hashable, deterministic `as_dict()` | Foundation convention since C3 |

Invariant 4 is worth naming: the safe direction on this component is always *toward* suspension. VEDA 01 §10 — *"a product that makes it hard to revoke trust has revealed what it thinks trust is for."*

---

## 6 · New risks

| # | Risk | Severity | Note |
|---|---|---|---|
| **R23** | **The switch carries no timestamp.** Nothing records when a suspension began or how long it has held | Low | Deliberate, and consistent with C8's `KernelRefusal` and C10's `AttemptToken`: the ledger records *when*, and a second clock reading is a second answer to one question. Adding one would also give C14 a dependency, which A3 forbids — it must work *"when the rest of the system is degraded."* C13's brief should state that suspension and resumption are ledger events |
| **R24** | **Nothing here enforces §11.8's mechanism.** Setting suspension, invalidating MINTED-not-yet-attempted warrants, and letting ATTEMPTING run to settlement are all absent | Low | Correct and deliberate — §11.8 assigns all three to the Kernel, and this brief forbids Kernel behaviour. **C15's brief must implement §11.8's four numbered steps**; C14 supplies only the state they read |

---

## 7 · Blockers

**None.**

**C15's remaining prerequisite is now C13 alone** — C11, C12 and C14 are all built.

---

## 8 · Preservation

C1–C12 untouched. Only `foundation/__init__.py` changed outside C14's own files, exports only. No specification, roadmap, amendment or ADR modified. No commit, no tag.

**STOP.**
