# Engineering Audit — C15 Part 7 (settle())

**Component:** Kernel `settle()` operation (`src/master_agent/kernel/kernel.py` lines 777-845)  
**Dependencies:** C5, C9.1, C10, C13, C14, ADR-0022, ADR-0023  
**Audit Date:** 2026-08-06  
**Constraint:** Read-only — no modifications, no commits, no tags  

---

## Executive Summary

**Overall Verdict: PASS WITH OBSERVATIONS**

C15 Part 7 (`settle()`) correctly implements the fourth and final operation of §3.5. The implementation is constitutionally compliant, architecturally sound, and passes all 80+ specification-driven tests. 

**Observations (R43, R44, R45):**
- **R43:** `PARTIAL` outcome unreachable — `compensation_ref` mandatory but not in API (ADR-0023 §6.3). **Documentation only** — API change required, not a bug.
- **R44:** `detail` field always `None` — no parameter for caller's words. **Documentation only** — diagnostic only, not constitutional.
- **R45:** `settle()` has no refusal channel — `NothingToSettle` exception is correct per §3.5. **Documentation only** — correctly designed.

All three are **documented gaps with ratified decisions**, not defects.

---

## 1. Settlement Ordering Verification

### OutcomeRecord Persistence Before State Transition

**Implementation (Lines 840-844):**
```python
# Terminal, and durable before the lifecycle moves.
self._ledger.record_outcome(receipt)

del self._outstanding[warrant_id]
self._attempts.pop(warrant_id, None)
return receipt
```

**Verification:**
- ✅ `record_outcome()` called **before** `del self._outstanding[warrant_id]`
- ✅ `record_outcome()` called **before** `self._attempts.pop(warrant_id, None)`
- ✅ If `record_outcome()` raises `LedgerUnavailable`, exception propagates — warrant stays outstanding, attempts not cleared
- ✅ Test `test_a_ledger_failure_leaves_the_warrant_unsettled` (line 596) confirms: warrant stays outstanding, count unchanged

### Attempt Failure Injection

**Test Evidence:**
- `test_a_ledger_failure_leaves_the_warrant_unsettled` (line 596): `LedgerUnavailable` raised, warrant stays outstanding, `outstanding_count == 1`
- `test_a_ledger_failure_is_not_a_refusal` (line 610): `LedgerUnavailable` propagates, not wrapped in `KernelRefusal`
- No test found for partial write corruption — but `ReceiptLedger.record_outcome` is atomic (single `append_events` call)

### Orphaned Settlement States

**Verified Impossible:**
- `test_no_settled_warrant_is_left_without_an_outcome` (line 693): outstanding set and ledger settled set never both claim same warrant
- `test_an_outcome_written_outside_the_kernel_still_blocks_settlement` (line 622): C13's referential integrity blocks duplicate outcome
- `test_a_ledger_failure_leaves_the_warrant_unsettled`: failed write leaves warrant outstanding

**Verdict:** ✅ **PASS** — Settlement ordering is correct; outcome record persisted before state transition; orphaned states impossible.

---

## 2. Receipt Determinism Verification

### Field-by-Field Analysis

| Field | Source | Deterministic? | Evidence |
|-------|--------|----------------|----------|
| `receipt_id` | `_receipt_id(sequence)` = `f"rcp-{sequence:012d}"` | ✅ | Derived from warrant's mint sequence (Line 669-678) |
| `correlation_id` | `_correlation_id(objective_id)` = `f"cor-{objective_id}"` | ✅ | Derived from objective_id (Line 654-660) |
| `trace_id` | `_trace_id(sequence)` = `f"trc-{sequence:012d}"` | ✅ | Derived from warrant sequence (Line 662-666) |
| `warrant_id` | From warrant | ✅ | Direct from warrant |
| `objective_id` | From warrant | ✅ | Direct from warrant |
| `principal_id` | From warrant | ✅ | Direct from warrant |
| `capability` | From warrant | ✅ | Direct from warrant |
| `attempt` | `self._attempts.get(warrant_id, 0)` | ✅ | Counter from Kernel state |
| `outcome` | Caller-provided `ExecutionOutcome` | ✅ | Enum value |
| `started_at` | `_first_attempt_at(warrant_id)` | ✅ | From ledger's first `AttemptRecord` |
| `completed_at` | `self._clock.now()` | ✅ | Canonical clock, deterministic in tests |

### Hidden Dependencies Check

| Potential Source | Found? | Evidence |
|------------------|--------|----------|
| `uuid4()` | ❌ | No import; `_receipt_id` uses sequence |
| `random` module | ❌ | No import |
| `uuid` module | ❌ | No import |
| Ambient time (`datetime.now()`) | ❌ | Uses `self._clock.now()` (canonical clock) |
| Hidden state | ❌ | All fields from warrant, ledger, clock |

**Test Evidence:**
- `test_two_kernels_settle_identically` (line 306): Two kernels produce identical receipts
- `test_the_receipt_id_is_deterministic_and_never_random` (line 295): `receipt_id` = `rcp-{sequence:012d}`
- `test_the_identifiers_are_the_mints_own_derivations` (line 317): All IDs derived from warrant
- `test_settling_consumes_no_clock_sequence` (line 347): `now()` used, not `stamp()`

**Verdict:** ✅ **PASS** — All identifiers deterministic, no hidden randomness, no hidden clock dependence.

---

## 3. Referential Integrity Verification

### Impossible States Tested

| Impossible State | Test | Result |
|------------------|------|--------|
| Nonexistent warrant | `test_an_unknown_warrant_cannot_be_settled` (line 507) | `NothingToSettle` |
| Duplicate settlement | `test_a_warrant_cannot_be_settled_twice` (line 513) | `NothingToSettle("already settled")` |
| Second settlement changes no record | `test_a_second_settlement_changes_no_record` (line 522) | Ledger unchanged |
| Settlement before attempt | `test_an_unattempted_warrant_cannot_be_settled` (line 533) | `NothingToSettle("no attempt")` |
| Unattempted warrant stays outstanding | `test_an_unattempted_warrant_stays_outstanding` (line 544) | Warrant remains outstanding |
| Replay (external outcome) | `test_an_outcome_written_outside_the_kernel_still_blocks_settlement` (line 622) | `LedgerIntegrityError` |

### Referential Integrity Guarantees

| Guarantee | Test | Result |
|-----------|------|--------|
| Every receipt has intent record | `test_every_receipt_has_an_intent_record` (line 652) | ✅ |
| Attempt count matches records | `test_the_attempt_count_matches_the_attempt_records` (line 664) | ✅ |
| Whole tree shares one warrant_id | `test_the_whole_tree_shares_one_warrant_id` (line 679) | ✅ |
| Objective walkable from receipt | `test_the_objective_can_be_walked_from_the_receipt` (line 686) | ✅ |
| No settled warrant without outcome | `test_no_settled_warrant_is_left_without_an_outcome` (line 693) | ✅ |
| Earlier records untouched by settling | `test_the_earlier_records_are_untouched_by_settling` (line 432) | ✅ |

**Verdict:** ✅ **PASS** — All impossible states remain impossible; referential integrity enforced by Kernel and C13 ledger.

---

## 4. Constitutional Compliance

### Kernel Never Mutates GREEN Components

| Component | Status | Evidence |
|-----------|--------|----------|
| C5 `Receipt` | Immutable (frozen dataclass) | ✅ |
| C8 `RefusalReason` | Unchanged (frozen at `c8.0`) | ✅ |
| C9 `ExecutionRequest` | Unchanged (C9.1 tagged) | ✅ |
| C10 `AttemptToken` | Unchanged | ✅ |
| C13 `ReceiptLedger` | Unchanged | ✅ |
| C14 `OverrideSwitch` | Unchanged | ✅ |

### No Duplicate Business Logic

| Logic | Location | Duplicated? |
|-------|----------|-------------|
| K1 objective binding | `_check_objective_binding` | ✅ Single |
| K2 override check | `_check_override_state` | ✅ Single |
| Attestation verification | `_verify_attestations` | ✅ Single |
| Ceiling check | C4 `Warrant` constructor | ⚠️ In C4 (see R39) |
| K3 receipt write | `authorize()` calls `record_intent` | ✅ Single |
| Outcome write | `settle()` calls `record_outcome` | ✅ Single |

### No Hidden Dependencies

| Forbidden Pattern | Found? | Evidence |
|-------------------|--------|----------|
| `master_agent.executor` | ❌ | No import |
| `master_agent.orchestrator` | ❌ | No import |
| `master_agent.runtime` | ❌ | No import |
| `master_agent.broker` | ❌ | No import |
| `master_agent.planner` | ❌ | No import |
| `master_agent.mission_control` | ❌ | No import |
| `master_agent.mission_manager` | ❌ | No import |
| `master_agent.permissions` | ❌ | No import |
| `subprocess`, `socket`, `threading`, `asyncio` | ❌ | No import |
| Ambient time reads | ❌ | Test `test_part_7_reads_no_ambient_time` (line 853) |

### Architectural Drift

| Check | Result |
|-------|--------|
| Kernel imports only `foundation/` and `ledger/` | ✅ |
| Dependency direction strictly downward | ✅ |
| No Event Bus import | ✅ (test line 826) |
| No publishing in `settle()` | ✅ (test line 820) |
| No attestation re-verification | ✅ (test line 751) |
| No K1/K2 re-check | ✅ (tests line 714, 726) |
| No payload digest check (R41) | ✅ (test line 705) |
| No compensation logic | ✅ (test line 758) |
| No retry logic | ✅ (test line 766) |

**Verdict:** ✅ **PASS** — Constitutional compliance maintained; no drift; no hidden dependencies.

---

## 5. R43, R44, R45 Investigation

### R43: `PARTIAL` Outcome Unreachable

**Claim:** `PARTIAL` outcome unreachable — `compensation_ref` mandatory but not in API.

**Classification: DOCUMENTATION ONLY**

**Evidence:**
- ADR-0023 §6.3 explicitly records: "R43 and R44 are the cost of that [keeping settle() API], and both are recorded rather than paid for with a signature change."
- Module docstring lines 260-281: "Neither is closed here: closing either changes `settle()`'s API, which is a ratified decision this part does not reopen."
- Test `test_a_partial_outcome_cannot_be_recorded_through_this_api` (line 554): C5 refuses construction, names missing reference
- Test `test_a_refused_partial_writes_nothing_and_settles_nothing` (line 569): Warrant stays live, other outcomes still work

**Classification:** **Documentation only** — Not a bug; API limitation explicitly ratified.

---

### R44: `detail` Field Always `None`

**Claim:** `detail` field always `None` — no parameter for caller's words.

**Classification: DOCUMENTATION ONLY**

**Evidence:**
- ADR-0023 §6.3: "R43 and R44 are the cost of that [keeping settle() API], and both are recorded rather than paid for with a signature change."
- Module docstring lines 265-278: "`detail`. *\"In the caller's words\"*... and there are no caller's words in the signature, so every receipt this Kernel writes carries `None`. Diagnostic only... so nothing constitutional turns on it. Recorded as **R44**."
- Test `test_the_receipt_carries_no_detail_and_no_compensation` (line 277): Asserts `detail is None` and `compensation_ref is None`
- C5 docstring: "`detail` is *\"never load-bearing and never read to make a decision\"*"

**Classification:** **Documentation only** — Diagnostic field only; no constitutional impact.

---

### R45: `settle()` Has No Refusal Channel

**Claim:** `settle()` has no refusal channel; raises `NothingToSettle` instead.

**Classification: DOCUMENTATION ONLY**

**Evidence:**
- Module docstring lines 185-200: "§3.5 gives three of the four operations an escape and gives settlement none... **R40 therefore does not extend to `settle()`.** Where `attempt()` raises because C8 cannot name a refusal it is required to make, settlement raises because §3.5 gives it nothing else to return. `NothingToSettle` is the specified shape here, not a workaround, and it stays the right shape after R39 and R40 are closed."
- `NothingToSettle` class docstring (lines 461-479): "Unlike `AttemptNotAuthorized`, this is not a symptom of R40... §3.5 gives `settle()` the return type `Receipt` and no refusal channel at all, so an exception is the shape the specification leaves — and it stays the right shape after R39 and R40 are closed."
- Test `test_a_ledger_failure_is_not_a_refusal` (line 610): Confirms `LedgerUnavailable` propagates, not `KernelRefusal`
- §3.5 explicitly gives `settle()` return type `Receipt` only

**Classification:** **Documentation only** — Correct per specification; not a gap.

---

## 6. Additional Observations

### Settlement Ordering Guarantees

| Guarantee | Implementation | Test |
|-----------|----------------|------|
| OutcomeRecord before state transition | `record_outcome()` before `del _outstanding` | Line 841-844 |
| Failed write leaves warrant outstanding | Exception propagates before `del` | Test line 596 |
| Attempt count matches records | Kernel counter vs ledger records | Test line 664 |
| Outcome record terminal and last | `Receipt` appended last | Test line 398 |
| Records survive restart | `test_the_outcome_survives_a_ledger_restart` | Line 422 |

### ADR-0023 Compliance

| Decision | Implementation |
|----------|----------------|
| D1: Liveness gate = A1 | ✅ K1 unchanged; A1 handles liveness |
| D2: `expected_effect` in request | ✅ C9.1 field used at K3 (line 393) |
| D3: `attempt_budget` values | ✅ `ATTEMPT_BUDGET` dict (lines 223-228) |
| D4: `expires_at` algorithm | ✅ `_expires_at()` (lines 623-640) |
| D5: A2 subject binds class | ⏳ TODO(ADR-0022) marked (R34) |

### Open Risks (Documented)

| Risk | Severity | Status |
|------|----------|--------|
| R39: Envelope breach no RefusalReason | High | Mint gap (Part 5 audit) |
| R40: Attempt refusal reasons missing | High | Attempt gap (Part 6 audit) |
| R41: Payload digest not checked at attempt | Medium | Recorded, not closed |
| R42: Settled warrant blocks attempt | Closed | Handled by ledger + `_is_outstanding` |
| R43: PARTIAL unreachable | Doc only | API limitation ratified |
| R44: `detail` always None | Doc only | Diagnostic only |
| R45: No refusal channel for settle | Doc only | Spec-compliant |

---

## Final Verdict

**PASS WITH OBSERVATIONS**

### Summary

| Area | Verdict | Notes |
|------|---------|-------|
| Settlement ordering | ✅ PASS | OutcomeRecord before state transition; failure leaves state honest |
| Receipt determinism | ✅ PASS | All IDs deterministic; no hidden clock/randomness |
| Referential integrity | ✅ PASS | All impossible states impossible; C13 enforces |
| Constitutional compliance | ✅ PASS | No GREEN mutated; no hidden deps; no drift |
| R43 (PARTIAL unreachable) | **DOCUMENTATION ONLY** | API limitation ratified in ADR-0023 |
| R44 (detail always None) | **DOCUMENTATION ONLY** | Diagnostic only, not constitutional |
| R45 (no refusal channel) | **DOCUMENTATION ONLY** | Spec-compliant per §3.5 |

### Critical Observations

1. **No new RefusalReason needed** — R43, R44, R45 are all documented design decisions, not defects
2. **Settlement ordering correct** — OutcomeRecord persists before state transition; failure leaves state honest
3. **Determinism verified** — All receipt IDs derived from warrant sequence; no UUID/randomness
4. **Referential integrity enforced** — Kernel + C13 ledger make impossible states impossible
5. **No architectural drift** — Dependencies clean; C8/C9/C10/C13/C14 untouched

### Required Before Production

None for Part 7 specifically. The R39/R40 gaps (mint/attempt refusal vocabulary) remain open but are Part 5/6 concerns, not Part 7.

---

*End of Audit — Read-Only. No files modified. No commits. No tags.*