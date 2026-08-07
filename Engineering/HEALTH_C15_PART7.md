# Health Report — Sprint 1 Component 15, Part 7: `settle()`

**Type:** Implementation health report. Working-directory evidence only.
**Date:** 2026-08-06
**Status:** Complete. **Not committed, not tagged, no Rule 001.**
**Preceded by:** `HEALTH_C15_PART6.md` — Hermes *PASS WITH OBSERVATIONS*.
**Ground:** Kernel Specification · ADR-0022 · ADR-0023 · Roadmap v2 (+ Amendments 001–003) · VEDA 01–04.

**Founder constraints honoured, in full:** R39 not solved · R40 not solved ·
C8 not modified · no new `RefusalReason` · no GREEN component reopened ·
Part 7 only · Part 8 not begun · no speculative architecture.

---

## 1 · What was built

| File | | |
|---|---|---|
| `src/master_agent/kernel/kernel.py` | extended | 1,162 lines, **158 AST statements** (was 136) |
| `src/master_agent/kernel/__init__.py` | extended | exports `NothingToSettle` |
| `tests/test_kernel_settle.py` | new | **64 tests** |
| `tests/test_kernel_{skeleton,admission,authorization,preconditions,mint,attempt}.py` | 6 superseded guards updated — §8 | — |

**`settle()` is complete.** `invalidate()` is the only operation still
raising `NotImplementedError`, asserted by test. `authorize()` and
`attempt()` are untouched.

```
settle(warrant_id, outcome) -> Receipt
NothingToSettle                     the three impossible states
_receipt_id(sequence)               rcp-{sequence:012d}
_sequence_of(warrant_id)            R29's re-derivation
_first_attempt_at(warrant_id)       started_at, read from A1's records
```

---

## 2 · The operation, in order

```
   1. resolve the warrant from the outstanding set → not there: NothingToSettle
                                                     (distinguishing
                                                      "already settled")
   2. attempts == 0 or no AttemptRecord            → NothingToSettle
   3. build the Receipt from warrant · ledger · clock
   4. ledger.record_outcome(receipt)               → LedgerUnavailable propagates
   5. remove from the outstanding set; drop the attempt count
   6. return the Receipt
```

**The write precedes the transition, and that ordering is the whole
point.** If step 4 raises, the warrant is still outstanding — the state
stays honestly *unsettled* rather than becoming a settlement the ledger
never heard of, which is §9.5's reconciliation gap. §11.3: fail closed, no
buffering.

**The transition is a removal, never a mutation.** §4.4 — *"Nothing mutates
an Intent, ever, at any privilege level. State changes are separate
append-only records referencing it."* The outcome record is that separate
record; the outstanding set is where §13.3 keeps the Kernel's memory
bounded.

**Nothing is taken from the caller but the outcome.** Identity comes from
the `Warrant`, `started_at` from A1's first `AttemptRecord`, `completed_at`
from the `Clock`, and the three identifiers from the mint's own
derivations. A settlement therefore cannot describe an execution other than
the one that was authorized.

---

## 3 · `settle()` has no refusal channel, and that is the specification

§3.5 gives three operations an escape and gives settlement none:

```
  authorize(ExecutionRequest) → Intent | Refusal
  attempt(intent_id)          → AttemptToken | Refusal
  settle(intent_id, Outcome)  → Receipt              ← no refusal
```

**R40 does not extend to this part.** Where `attempt()` raises because C8
cannot name a refusal it is *required* to make, settlement raises because
§3.5 gives it nothing else to return. `NothingToSettle` is the specified
shape, not a workaround, and it stays the right shape after R39 and R40 are
closed. A test asserts a ledger failure is not a `KernelRefusal` for
exactly this reason.

`NothingToSettle` is a `RuntimeError` rather than a `ValueError`, following
`LedgerUnavailable` and Part 6's `AttemptNotAuthorized`: a caller wrapping
`Receipt(...)` construction in `except ValueError` to catch
`InvalidReceipt` must never absorb *"this warrant was already settled"* by
accident.

---

## 4 · Deterministic receipt generation — R29 closed as Part 5 predicted

ADR-0023 §6.3 required Part 5 to **store** `receipt_id`, `correlation_id`
and `trace_id` at mint so that Part 7 would have them. The Part 5 health
report's §3.1 argued it did not need to, because all three are pure
functions of data already on the `Warrant`. **Part 7 confirms it.**

| Derived | Rule | Basis |
|---|---|---|
| `receipt_id` | `rcp-{sequence:012d}` | §9.1 makes the outcome record `0..1` per warrant, so the mint sequence is unique by construction |
| `correlation_id` | `cor-{objective_id}` | Part 5, re-derived |
| `trace_id` | `trc-{sequence:012d}` | Part 5, re-derived |
| `attempt` | the warrant's attempt count | §4.4 |
| `started_at` | first `AttemptRecord.recorded_at` | §9.2 — read the record, never hold a second copy |
| `completed_at` | `clock.now()` | — |

**No `uuid4()`, no ambient randomness, and no clock sequence consumed.**
Two Kernels with the same clock and inputs settle to **equal receipts** —
asserted directly. `now()` rather than `stamp()`, because spending a
sequence here would silently shift the identity of the next warrant minted;
a test proves a settle-then-mint leaves the warrant ids consecutive.

**The Kernel gained no state.** `__slots__` is unchanged from Part 6, and
settlement *removes* state rather than adding any.

---

## 5 · One outcome record per warrant — a documented reading, not a change

C5's docstring reads *"one receipt per attempt… several receipts may share
one `warrant_id`."* §9.1 and §4.4 say otherwise and they govern:

> `OutcomeRecord (0..1, terminal)` · *"One Intent, N attempts, N attempt
> records, **one outcome record**."*

C13 already resolved it the same way — `record_outcome` refuses a second
outcome for one warrant. So `Receipt.attempt` carries **how many attempts
the warrant used**, and `started_at` is the first attempt's moment, making
`Receipt.duration` the span of the whole authorized execution.

**Nothing in C5 or C13 was changed to say this.** It is recorded in the
Kernel's docstring because two readings exist and only one is
implementable.

---

## 6 · Impossible states

| State | Made impossible by | Verdict |
|---|---|---|
| Settling a warrant this Kernel never minted | `NothingToSettle` | raises, writes nothing |
| Settling twice | `NothingToSettle`, distinguishing *"already settled"* | raises; a test proves no record changes |
| Settling a warrant with no attempt | `NothingToSettle` — and `Receipt.attempt` is 1-based, so it is unconstructable anyway. §4.5 sends an unattempted warrant to EXPIRED or CANCELLED, never SETTLED | raises, stays outstanding |
| An outcome record with no intent record | C13 `_require_intent` | unwritable |
| A second outcome from outside the Kernel | C13 `LedgerIntegrityError` | unwritable — tested |
| An attempt after settlement | The warrant left the outstanding set — **this closes R42** | `AttemptNotAuthorized` |
| `completed_at` before `started_at` | C5 | unconstructable |
| An outcome that is not one of §6.3's four | C5's closed vocabulary | `InvalidReceipt`; nothing settled |
| `PARTIAL` without a compensating action | C5 | `InvalidReceipt` — **R43**, see §7 |
| Editing a settled receipt | C5 frozen; ledger append-only at every privilege level | no method exists |

**Every failure path was tested for what it leaves behind, not only for
what it raises.** A refused settlement writes nothing, settles nothing, and
leaves the warrant live and settleable under a kind the API can express.

---

## 7 · Two things settlement cannot say

ADR-0023 §6.3 records the founder ruling that `settle()` keeps its API and
that *"the Kernel owns all Receipt metadata; Receipt construction occurs
internally using Kernel state."* Two `Receipt` fields are **not** metadata
and are not Kernel state.

**R43 — `PARTIAL` is unreachable.** §6.3 makes `compensation_ref` mandatory
for the outcome it calls *"the most dangerous… and the one most often
modelled as failure — a half-written file is not a file that was not
written."* `settle(warrant_id, outcome)` has no parameter for a
compensating action and the Kernel cannot invent one, so C5 refuses
construction and names what is missing. **One of §6.3's four settlement
kinds cannot be recorded through this API.** Fails closed and is tested;
closing it changes `settle()`'s ratified signature.

**R44 — every receipt carries `detail=None`.** *"In the caller's words"*,
and there are no caller's words in the signature. Diagnostic only — C5
states it is *"never load-bearing and never read to make a decision"* — so
nothing constitutional turns on it.

Both are recorded rather than paid for with a signature change, because the
signature is a ratified decision this part does not reopen.

---

## 8 · §3.5's *"Publishes"* is not built here, and has a home

§3.5's settlement line ends *"Terminal. Publishes."* and §10.2 names
`INTENT_SETTLED`. Nothing is published in Part 7, on four grounds:

- §3.3 gives the Kernel *"what is published, when. **Not the bus**, which
  already exists."*
- The bus is Mission Control's, and §3.6's dependency rule — enforced by a
  **shipped architecture guard** — forbids this module importing it.
- Roadmap §2 puts the subscriber at **C18**, which depends on C13 and C15.
- §10.3 makes zero subscribers *"a valid, fully functional
  configuration"*, and §10.1's guarantee is **complete coverage, never
  veto** — which the durable outcome record already provides.

So §12.1's eleventh guarantee — *"entering the receipt stream learning
consumes"* — is satisfied by the record, and the event arrives with its
component. Asserted by test rather than left to prose.

---

## 9 · Test coverage — 64 tests

| Area | Proves |
|---|---|
| **The settlement** | An attempted warrant settles; the outcome is carried, never re-derived; three of §6.3's four kinds are reachable; `unknown` escalates |
| **Field provenance** | Identity from the warrant; attempt count is the warrant's own; `started_at` is the first attempt's moment, not the mint's; `completed_at` and `duration`; no detail, no compensation |
| **Determinism** | `receipt_id` deterministic and never random; two Kernels settle identically; identifiers are the mint's own derivations; correlation shared per objective, trace and receipt unique; no clock sequence consumed; JSON-ready and stable |
| **§9.1 ordering** | The receipt **is** the outcome record; records read back intent → attempts → outcome; the outcome is last; two objectives interleave without disturbing each other's order; survives a restart; earlier records untouched |
| **§4.5 lifecycle** | A settled warrant leaves the outstanding set, opens no further attempt, leaves no attempt count behind, and is never mutated; other warrants stay outstanding |
| **Impossible states** | All ten of §6, each checked for what it leaves behind |
| **§9.2 integrity** | Every receipt has an intent; the attempt count matches the records; one warrant id across the tree; the objective is walkable; outstanding and settled never both claim one warrant |
| **What settlement does not do** | No admission read; no override read; mints nothing; re-verifies no attestation; compensates nothing; is not a retry |
| **Nothing beyond Part 7** | Signature unchanged; surface unchanged; no new state; only `invalidate()` unimplemented; no publishing; dependencies unchanged; no ambient time; R9 ceiling |

---

## 10 · Quality gates

| Gate | Result |
|---|---|
| Part 7 tests | **64 passed, 0 failed** |
| C15 Parts 1–7 | **357 passed, 0 failed** |
| C15 + C9.1 + foundation + architecture guards | **1,471 passed, 1 skipped, 1 pre-existing failure** |
| Ruff — all C15 source and tests | **All checks passed** |
| Line length | 88 source / 84 tests (limit 100) |
| §14 R9 ceiling | **158 of 600 statements — 26% consumed** (was 23%) |
| C1–C14 untouched | **0 modified files** in `foundation/` or `ledger/` |

### 10.1 The full suite, stated honestly

`pytest tests/` reports **4,915 passed, 49 failed, 1 skipped**.

**All 49 failures are pre-existing and unrelated to C15.** The same five
files failed identically at the Part 6 baseline, measured with the Kernel
changes stashed, and none of them references the Kernel:

| File | Failures |
|---|---|
| `test_missions_console.py` | 27 |
| `test_memory_integration.py` | 16 |
| `test_missions_architecture.py` | 4 |
| `test_foundation_clock.py` | 1 — `launcher/boot.py` reads ambient time |
| `test_founder_approval_workflow.py` | 1 |

The failing-file set and counts are **unchanged from before Part 6**.
Recorded rather than fixed: they are outside C15 and outside this brief.

---

## 11 · Six superseded guards

Parts 1–6 asserted `settle()` was unimplemented. Part 7 makes that false,
so each is updated rather than deleted, and **no assertion is weakened**.

| File | Change |
|---|---|
| `test_kernel_skeleton.py` | `settle` removed from the unimplemented parametrization; only `invalidate` remains |
| `test_kernel_{admission,authorization,preconditions}.py` | `raise NotImplementedError` count 2 → **1** |
| `test_kernel_mint.py` | `…_other_two_operations_remain_unimplemented` → `…_last_operation_…` |
| `test_kernel_attempt.py` | `…_two_remaining_operations_…` → `…_last_operation_…` |

The count still pins exactly how much is unbuilt.

---

## 12 · Risks

| # | Risk | Severity | Note |
|---|---|---|---|
| **R43** | **`PARTIAL` cannot be recorded through `settle()`.** §6.3 requires a compensating action reference for it and the signature has no parameter for one, so one of four settlement kinds is unreachable | **Medium** | **New.** Fails closed and is tested. Closing it changes `settle()`'s ratified API (ADR-0023 §6.3) |
| **R44** | **Every receipt carries `detail=None`.** The caller has nowhere to say what happened | **Low** | **New.** C5 makes `detail` diagnostic only — *"never load-bearing and never read to make a decision"* |
| **R45** | **§3.5's *"Publishes"* is not built.** No `INTENT_SETTLED` event is emitted | **Low** | **New.** Deliberate — the bus is C18's and §3.6's guard forbids importing it; §10.1's coverage guarantee is met by the durable record |
| **R42** | Settled warrants had no Kernel-side gate | — | **CLOSED.** The warrant leaves the outstanding set; `attempt()` now refuses it as the Kernel's own decision |
| **R29** | `settle()`'s Receipt identity fields | — | **CLOSED.** All three re-derived, no state stored at mint, exactly as the Part 5 health report predicted |
| **R40** | No `RefusalReason` covers `attempt()`'s four conditions | Medium | **Carried, untouched by instruction.** Does **not** extend to `settle()` — §3.5 gives it no refusal channel |
| **R39** | No `RefusalReason` covers an envelope breach | Medium | **Carried, untouched by instruction** |
| **R41** | The payload digest is not checked at `attempt()` | Medium | Carried |
| **R34** | The A2 attestation does not bind to the carried class | High | Carried. Not reached by this part |
| **R38 · R37 · R31** | `read_only = 5` · omitted grant validity · freshness window | Low–Medium | Carried |
| **R6** | §14 R9's 600-statement ceiling | High | **26% consumed.** Settlement cost 22 statements. Part 8 has ample room |

---

## 13 · Blockers

**None for Part 8.** `invalidate()` needs the outstanding set and the
Override switch, both owned since Parts 1 and 4, and Part 7 leaves both
intact. §11.8's step 2 — *"invalidate every MINTED intent not yet
attempted"* — is now distinguishable in Kernel state, because an attempted
warrant has an entry in the attempt count and an unattempted one does not.

**R39 and R40 together remain the one open decision the Kernel needs**, and
it is a founder decision about C8, not an engineering one. R43 is a second,
smaller decision of the same kind — about `settle()`'s signature rather
than about C8.

---

## 14 · Preservation

C1–C14 untouched — zero modified files in `foundation/` or `ledger/`.
C9.1 (`kalpavriksha-s1-c9.1`) consumed as shipped. C8 not opened. No new
`RefusalReason`, no new `KernelCheck`, no new `AttestationQuestion`. C5 and
C13 read, never modified.

Changed outside `kernel/`: only the six superseded guards and the new test
file. No specification, roadmap, amendment or ADR modified. **No new ADR,
no new concepts, no architecture change.** Part 8 not begun. No commit, no
tag, no Rule 001.

**STOP.** Awaiting Hermes audit.
