# Health Report — Sprint 1 Component 15, Part 5: K3 and the Mint

**Type:** Implementation health report. Working-directory evidence only.
**Date:** 2026-08-06
**Status:** Complete. **Not committed, not tagged, no Rule 001.**
**Preceded by:** `KERNEL_PRE_PART5_AUDIT.md` — *READY FOR PART 5*.

---

## 1 · What was built

| File | | Lines |
|---|---|---|
| `src/master_agent/kernel/kernel.py` | extended | 774 (**120 AST statements**, was 99) |
| `tests/test_kernel_mint.py` | new | 54 tests |
| `tests/test_kernel_{skeleton,admission,authorization,preconditions}.py` | 4 superseded guards updated — §6 | — |

**`authorize()` is complete.** The other three operations still raise `NotImplementedError`, asserted by test.

```
authorize(request) -> Warrant | KernelRefusal
_expires_at(issued_at, action_class, deadline)      §4.4  · ADR-0023 D4
_warrant_id(sequence) · _correlation_id(objective_id) · _trace_id(sequence)
ATTEMPT_BUDGET   §8.5 · ADR-0023 D3
VALIDITY_DEFAULT §4.4 · ADR-0023 D4
```

---

## 2 · The mint, and the one ordering decision that matters

§7.4's order runs K1 · K2 · attestations · **K3**, then the mint.

**The `Warrant` is built before the ledger write and returned only after it succeeds.** §7.2 K3's guarantee is that *nothing executes without a durable intent*; constructing a frozen value is not executing, and this is **the only order that cannot orphan a record.** If construction failed after the write, the ledger would hold an intent with no warrant — the reconciliation gap §9.5 exists to make impossible.

Two ways a `Warrant` can refuse construction, both proven to write nothing:

| Condition | C4's invariant | Test |
|---|---|---|
| Class exceeds the objective's ceiling | §10.4, via `ReversibilityClass.exceeds()` | `test_a_class_exceeding_the_ceiling_cannot_mint` |
| `expires_at <= issued_at` | *"expired at birth authorizes nothing"* | `test_a_past_deadline_fails_closed_rather_than_minting` |

Both propagate `InvalidWarrant` rather than becoming a `KernelRefusal` — a caller or Engine defect is not a decision the Kernel made, and §7.5 records decisions. Same posture as R30 and ADR-0023 D4.

**C4 already owns the ceiling check** (`Warrant.__post_init__` calls `exceeds()`), so the Kernel does not restate it. That would have been reimplementation.

---

## 3 · Derivations, all deterministic

| Derived | Rule | Source |
|---|---|---|
| `attempt_budget` | `ATTEMPT_BUDGET[reversibility_class]` | §8.5 + ADR-0023 D3 |
| `expires_at` | `min(issued_at + VALIDITY_DEFAULT[action_class], admission.deadline)` | §4.4 + D4 |
| `warrant_id` | `wrt-{sequence:012d}` from `Clock.stamp()` | §4.3 |
| `correlation_id` | `cor-{objective_id}` | C5 |
| `trace_id` | `trc-{sequence:012d}` | C5 |

**No `uuid4()`, no ambient randomness.** Two Kernels with the same clock and inputs mint **equal warrants** — asserted directly, and it is what makes the Kernel verifiable at all.

**§8.5's budgets:** `irreversible` 1 and `reversible` 3 are verbatim. `reversible_until` **2 is forced** — a test asserts `1 < budget < 3`, which is the derivation itself rather than the number. `read_only` 5 is asserted bounded and above `reversible`, not pinned to 5, because ADR-0023 D3 records it as the one value not forced by the specification.

### 3.1 R29 resolves without stored state

ADR-0023 §6.3 said Part 5 must store `correlation_id` and `trace_id` for settlement. **It does not need to.** Both are pure functions of data already on the `Warrant` — the objective id, and the sequence embedded in `warrant_id` — so Part 7 re-derives them. A test proves the round trip.

That removes the Part 5 / Part 7 coupling ADR-0023 flagged, and adds no state to the Kernel.

---

## 4 · Test coverage — 54 tests

| Area | Proves |
|---|---|
| **Deterministic mint** | Two Kernels mint equal warrants; ids are monotonic and unique within one Kernel; the window is identical across instances |
| **Duplicate protection** | Distinct requests mint distinct warrants; five mints yield five ids; `_register` refuses a re-registration; §4.4's *"can two executions share one? No"* |
| **Ledger write** | The intent is durable before the warrant returns; A1's field list is present; `expected_effect` reaches the permanent record; the consequence is never null; a `LedgerUnavailable` refuses with `LEDGER_UNAVAILABLE` at `K3_RECEIPT_INTENT_WRITE` and mints nothing |
| **Warrant invariants** | Identity carried from the request; ceiling from the `AdmissionRecord`, never the caller; budget per class; never expired at birth |
| **Receipt invariants** | The three identifiers, their meanings, and their derivability |
| **Serialization** | Deterministic, JSON-ready, and the intent survives a **ledger restart** |
| **Referential integrity** | Every minted warrant has an intent record; **the ledger never holds an orphan** |
| **Nothing beyond Part 5** | Three operations still unimplemented; surface unchanged; no Event Bus; no attestor |

### 4.1 Two of my own test defects, found and fixed

**An empty `ReceiptLedger` is falsy** — `__len__` returns 0, so `ledger or ReceiptLedger(...)` silently discarded the injected broken ledger and the failure test passed against a working one. Changed to an identity check. **This is a real trap for any future caller**, and it is now commented at the site.

**Attestation subjects were pinned to a constant** while tests varied `payload_digest`, so §7.3's subject match correctly refused — the tests were wrong, not the Kernel. The helper now derives subjects from the request's own digest.

Both are recorded because a test that passes for the wrong reason is worse than one that fails.

---

## 5 · Quality gates

| Gate | Result |
|---|---|
| Part 5 tests | **54 passed, 0 failed** |
| C15 Parts 1–5 + C9 | **360 passed, 0 failed** |
| Ruff — all C15 source and tests | **All checks passed** |
| Line length | 88 (limit 100) |
| Architecture guards | **215 passed, 1 skipped, 0 failed** |
| §14 R9 ceiling | **120 of 600 statements — 20% consumed** (was 17%) |
| C1–C14 untouched | **0 modified files** in `foundation/` or `ledger/` |

---

## 6 · Four superseded guards

Parts 1–4 asserted `authorize()` was unimplemented. Part 5 makes that false, so each is updated rather than deleted:

| File | Change |
|---|---|
| `test_kernel_skeleton.py` | `authorize` removed from the unimplemented parametrization; renamed to `test_every_unbuilt_operation_is_unimplemented` |
| `test_kernel_{admission,authorization,preconditions}.py` | `…_four_operations_are_still_unimplemented` → `test_the_remaining_operations_are_unimplemented`, asserting **3** |

No assertion was weakened — the count still pins exactly how much is unbuilt.

---

## 7 · Risks

| # | Risk | Severity | Note |
|---|---|---|---|
| **R39** | **No `RefusalReason` covers an envelope breach.** A class exceeding the ceiling, or a past deadline, raises `InvalidWarrant` rather than refusing constitutionally — yet §10.4 says *"the Kernel refuses a warrant exceeding any of the three"* | **Medium** | **New.** Behaviour is defined, fail-closed and tested. But §7.5 requires refusals to be recorded, and these cannot be. Same family as R30. **Worth settling together with R30** — one decision covers both |
| **R34** | The A2 attestation does not bind to the carried class | High | Carried. Three `TODO(ADR-0022)` markers; ADR-0023 D5 specifies the close. **Now live**: the mint trusts the class for both the budget and the record |
| **R38** | `read_only = 5` is not forced by the specification | Low | Carried from ADR-0023 D3 |
| **R37** | `expires_at` omits grant validity | Low | Carried. Can only lengthen; tightens when A3 carries an expiry |
| **R31** | Attestation freshness window unratified | Medium | Carried |
| **R6** | §14 R9's 600-statement ceiling | High | **20% consumed.** The mint cost 21 statements. Parts 6–8 have ample room |

---

## 8 · Blockers

**None.** Parts 6, 7 and 8 are unblocked — R29 resolved in §3.1, and every derivation the mint needed is now in place.

---

## 9 · Preservation

C1–C14 untouched — zero modified files in `foundation/` or `ledger/`. C9.1 (`kalpavriksha-s1-c9.1`) is consumed as shipped, not modified.

Changed outside `kernel.py`: only the four superseded guards and the new test file. No specification, roadmap, amendment or ADR modified. **No new ADR, no new concepts, no architecture change.** No commit, no tag.

**STOP.** Awaiting Hermes audit.
