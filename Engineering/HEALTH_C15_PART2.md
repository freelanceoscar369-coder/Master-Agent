# Health Report — Sprint 1 Component 15, Part 2: K1 Admission Gate

**Type:** Implementation health report. Working-directory evidence only.
**Date:** 2026-08-06
**Status:** Part 2 complete. **Not committed, not tagged, no Rule 001.**
**Unblocked by:** Founder Decision, 2026-08-06, resolving `CONFLICT_C15_PART2.md`.

---

## 1 · The founder decision, implemented

> K1 is admission validation only. It refuses on **objective missing · objective unknown · objective terminal**, and **shall not enforce `EXECUTING`**.
>
> `ObjectiveState == EXECUTING` is a **minting** prerequisite, not an admission prerequisite.

| Check | Question | Where |
|---|---|---|
| **K1** | Is this objective admitted and not finished? | **structural** — here |
| **Mint** | Is this objective running right now? | **lifecycle** — a later part |

**C8 was not modified. No `RefusalReason` was added.** Its three objective reasons map one-to-one onto K1's three refusals, which is what made this the resolution with no cost. A test asserts the enum is still exactly eleven members.

### 1.1 ADR-0021 updated, as instructed

| Change | |
|---|---|
| **D5 superseded** and restated: K1 is structural admission; `READY` and `WAITING` pass; the `EXECUTING` requirement moves to the mint path | ✅ |
| **Citation corrected** — the liveness gate is **Objective Engine Specification** §10.2/§10.3, not Kernel Spec §10.3 (which is *"The four invariants that make learning safe"*) | ✅ |
| A2's heading narrowed to *"amends §7.2 K1"*; its §10.2/§10.3 paragraph re-attributed | ✅ |
| O2's `VERIFYING` note re-scoped — it no longer bears on K1, only on the mint path | ✅ |
| Status header records the amendment and its date | ✅ |

**No other clause changed.** D1–D4, A1, A3 and the terminology audit stand as ratified.

---

## 2 · What was built

| File | | Lines |
|---|---|---|
| `src/master_agent/kernel/kernel.py` | extended | 394 (**59 AST statements**, was 34) |
| `src/master_agent/kernel/__init__.py` | exports — `AdmissionProvider` added | 24 |
| `tests/test_kernel_admission.py` | new | 538 |
| `tests/kernel_test_support.py` | new — shared doubles | 64 |
| `tests/test_kernel_skeleton.py` | updated — constructor fixtures only | 419 |

**New surface**

```
AdmissionProvider        Protocol — admission_for(objective_id) -> AdmissionRecord | None
Kernel(clock, ledger, admission)
Kernel._check_objective_binding(request) -> AdmissionRecord | KernelRefusal
Kernel._admission_for(objective_id)
Kernel._register(warrant) · Kernel._is_outstanding(warrant_id)
```

**The public surface is unchanged** — still §3.5's four operations plus Part 1's two readers, asserted as a set equality. K1, the lookup and registration are **internal**: they are steps of `authorize`, not operations a caller invokes.

---

## 3 · R28's boundary, implemented as decided

> *"Do NOT inject AdmissionRecord into ExecutionRequest. Admission remains outside the ExecutionRequest boundary. Kernel obtains admission information through its admission provider."*

`AdmissionProvider` is a `runtime_checkable` Protocol validated at construction. `ExecutionRequest` gains **no** admission field — asserted by test, because a request carrying its own admission would let a caller assert the very thing K1 exists to check.

The Kernel **never imports the Objective Engine** — §10.1: *"The Objective Engine's responsibility ends at admission."* It publishes; the Kernel reads. This is why C15 ships before C17, and a test enforces it.

**No caching.** Every check reads afresh. A cached admission is an authority that outlives its source — the defect §11.1 names for permissions — and §10.2's own diagram has the state changing under the Kernel's feet. Two tests prove it: a record that changes between checks changes the outcome, and a withdrawn objective stops passing.

---

## 4 · Test count and coverage

**94 tests: 47 new (Part 2) + 45 (Part 1, still passing) + 2 shared-double helpers exercised throughout.** Both suites: **92 passed, 0 failed.**

| Area | Proves |
|---|---|
| **The founder decision** | Every non-terminal state passes — `READY` and `WAITING` explicitly; `READY` and `EXECUTING` are indistinguishable at K1; the module contains no `is_executing` reference at all |
| **The three refusals** | Unknown → `OBJECTIVE_UNKNOWN`, remediable; terminal → `OBJECTIVE_TERMINAL`, **not** remediable; the partition is exactly terminal-versus-not with no state falling between |
| **Refusal shape** | `failed_check` is `K1_OBJECTIVE_BINDING`; **attestor is `None`** (Amendment M5 — a K1 refusal has no attestor); family is `KERNEL_CHECK` |
| **`OBJECTIVE_MISSING`** | Unreachable from K1 and deliberately so — `ExecutionRequest` refuses a blank `objective_id` at construction, so the condition is **prevented** rather than detected. C8 keeps the reason for callers C9 does not guard |
| **C8 untouched** | The enum is still eleven members; the three objective reasons are exactly as shipped |
| **The record is returned** | Not discarded — the mint path needs the envelope, and reading twice would invite the two reads to disagree |
| **Failure** | A provider that raises **propagates**; nothing is registered; nothing is written |
| **Registration** | One warrant, one registration (§4.4); a duplicate is refused rather than silently replacing; a non-`Warrant` is refused; nothing reaches the ledger |
| **Override** | Readable, never written in Part 2; **K1 does not consult it** — a suspended Kernel still refuses an unknown objective *for being unknown*, per §7.1's ordering principle |
| **Nothing arrived early** | All four operations still raise `NotImplementedError`; no public method added; no attestor held |

---

## 5 · Quality gates

| Gate | Result |
|---|---|
| Part 2 tests | **47 passed, 0 failed** |
| Part 1 tests (regression) | **45 passed, 0 failed** |
| Ruff — all C15 source and tests | **All checks passed** |
| Line length | 88 / 84 / 77 (limit 100) |
| Architecture guards (Rule 001 set) | **215 passed, 1 skipped, 0 failed** |
| §14 R9 ceiling | **59 of 600 statements — 10% consumed** (was 6%) |
| C1–C14 untouched | **0 modified files** in `foundation/` or `ledger/` |

---

## 6 · Engineering decisions

**ED-040 · A provider failure propagates; it does not become a refusal.**

Fail closed either way — nothing is minted. But a `KernelRefusal` is a constitutional decision the Kernel *made* and §7.5 requires it to be recorded. An unreachable Objective Engine is not a decision, and recording it as one would put a falsehood in a permanent ledger. Same distinction as Part 1's `NotImplementedError` and C13's `LedgerUnavailable` versus `InvalidLedgerRecord`.

**ED-041 · K1 returns the `AdmissionRecord`, not a boolean.**

The mint path needs the envelope §10.3 names — `consequence_ceiling`, `budget`, `deadline`. Returning the record the check already read means the envelope and the liveness decision come from **one** read. A second lookup could see a different state and disagree with the check that just passed.

**ED-042 · Registration refuses a duplicate rather than replacing.**

§4.4: *"Can two executions share one? **No.** One Intent authorizes one logical action."* A silent replacement would drop a warrant from the outstanding set while its execution was still live — invisible to `invalidate()` and to expiry.

**ED-043 · `_check_objective_binding` is private.**

K1 is a step of `authorize`, not an operation. Exposing it would let a caller pre-check admission and then act on a stale answer — the Kernel's guarantee is that the check and the mint happen together.

---

## 7 · Risks

| # | Risk | Severity | Note |
|---|---|---|---|
| **R30** | **No `RefusalReason` covers "the admission provider is unreachable."** C8's infrastructure family has `PERMISSION_SYSTEM_UNAVAILABLE`, `TOOL_OR_WORKER_UNAVAILABLE`, `PROVIDER_UNAVAILABLE` (the Broker's) and `KERNEL_UNAVAILABLE` — none is the Objective Engine | **Medium** | **New.** Behaviour today is defined and fail-closed: the exception propagates and nothing is minted, tested explicitly. But §7.5 requires refusals to be *recorded*, and this failure cannot be. **A founder decision** — either accept propagation as the contract, or widen C8 (which would reopen a frozen component) |
| **R28** | K1 had no admission source | — | **CLOSED** by the founder decision and this part |
| **R29** | `settle()` cannot construct a full `Receipt` from its declared arguments | Medium | **Answered in principle** — the founder ruled the API stays and the Kernel owns Receipt metadata internally. **Still to build**: the part implementing `settle` must show where `correlation_id`, `trace_id` and the timestamps come from. `started_at`/`completed_at` are reachable from the Clock; the two ids are not yet |
| **R25** | The ledger is not thread-safe; the single-writer assumption is unstated | Medium | Carried. Nothing in Part 2 writes to the ledger, so it is not yet reachable — **the part implementing K3 must state that Kernel operations are serialised** |
| **R24** | §11.8's four-step override mechanism unimplemented | Low | Carried. Lands on `invalidate()` |
| **R6** | §14 R9's 600-statement ceiling | High | **10% consumed.** K1 cost 25 statements including its two refusals |

---

## 8 · Blockers

**None for Part 2.**

R30 is recorded and does not block: the behaviour is defined and tested. It becomes a decision when the part implementing K3 needs every failure on the authorize path to be recordable.

---

## 9 · Preservation

C1–C14 untouched — `git status` reports zero modified files in `foundation/` or `ledger/`. C8 in particular is byte-identical, as the founder required.

Changed outside `master_agent/kernel/`: **only `tests/test_kernel_skeleton.py`**, and only its constructor fixtures, to pass the third dependency the founder authorized. No Part 1 assertion was weakened — two were tightened to cover the new parameter.

`docs/adr/0021-objective-state-vocabulary.md` amended as instructed. No specification, roadmap or amendment file modified. No commit, no tag.

**STOP.** Part 3 not started.
