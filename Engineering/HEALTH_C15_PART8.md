# Health Report — Sprint 1 Component 15, Part 8: `invalidate()`

**Type:** Implementation health report. Working-directory evidence only.
**Date:** 2026-08-06
**Status:** Complete. **Not committed, not tagged, no Rule 001.**
**Preceded by:** Hermes — Part 5 PASS · Part 6 PASS · Part 7 PASS.
**Ground:** Kernel Specification · ADR-0022 · ADR-0023 · Roadmap v2 (+ Amendments 001–003) · VEDA 01–04 · Objective Engine Specification §10.

**Scope honoured:** only `Kernel.invalidate()` built · C8 untouched · no new
`RefusalReason` · R39/R40 not revisited · no GREEN component modified · no
Part 9 · no speculative API.

**All four operations of §3.5 are now built.** `raise NotImplementedError`
appears **zero** times in `kernel.py`, asserted by test.

---

## 1 · What was built

| File | | |
|---|---|---|
| `src/master_agent/kernel/kernel.py` | extended | 1,257 lines, **163 AST statements** (was 158) |
| `tests/test_kernel_invalidate.py` | new | **57 tests** |
| six superseded "unbuilt operation" guards | converted — §6 | — |

`invalidate()` is **five statements of logic**. Everything else about it is
an absence the specification requires.

---

## 2 · §11.8's four steps, and where each one lives

```
   1. Set suspension. K2 now refuses every mint.     → one assignment, FIRST
   2. Invalidate every MINTED intent not yet
      attempted.                                     → the sweep
   3. Intents already ATTEMPTING run to settlement.  → an absence
   4. Engine keeps admitting, Mission Control keeps
      assigning, work queues at the boundary.        → an absence
```

**Step 1 must precede step 2, and that is the only ordering decision in the
part.** A mint completing between them would produce a warrant the sweep
has already passed, surviving an Override meant to reach everything. K2
refusing first closes the window — which is what §11.8's *"milliseconds"*
is about. Asserted structurally (the `suspend()` call's line number
precedes every `del`), because the window it closes is too small to observe
from outside.

**Steps 3 and 4 are proven as absences**, by AST guard rather than by
prose: `invalidate()` touches no attempted warrant, no admission provider,
no clock, no ledger, and nothing named admit/assign/queue/notify/publish.

---

## 3 · Only `SCOPE_ALL` suspends — the one interpretive call, and its ground

`invalidate()` serves two callers: the founder's global Override (§11.8)
and objective termination (Objective Engine Specification §10.5). **Only
the global form sets suspension.**

| Ground | |
|---|---|
| §11.8 | Names step 1 under `invalidate(scope=all, …)`, and attributes suspension to *"the founder's global Override"* |
| OE §10.5 | Termination is *"the same operation the founder's global Override uses, **at a narrower scope**. Nothing new is built."* A narrower scope reaches fewer intents; it does not stop the machine |
| OE §10.2 | A terminated objective gets *"no new mints"* from **K1** — the Engine publishes the terminal state and `OBJECTIVE_TERMINAL` does the rest. Suspension is not needed for it, and would be wrong |

The alternative reading — that any invalidation suspends — would stop all
autonomy because one objective was cancelled. Two tests pin the boundary in
both directions.

---

## 4 · New findings

### R46 — invalidation cannot record itself · **High**

§4.5 lists six terminal states and states plainly: *"All six terminal
states are recorded. **None is a deletion.**"* §4.4 is more specific —
cancellation *"writes a terminal outcome record of kind `cancelled`."*

**There is no such record available, and none can be constructed.**
Measured against the vocabulary rather than argued:

| | |
|---|---|
| C13's `RecordKind` | closed to `intent · attempt · outcome` |
| The outcome record | **is** C5's `Receipt` (C13: *"there is no second outcome type"*) |
| `Receipt.attempt` | 1-based; an invalidated warrant was never attempted |
| `ExecutionOutcome` | closed to §6.3's four **execution** outcomes; no `cancelled`, no `invalidated` |

So invalidation writes nothing. **The ledger deletes nothing** — the intent
record survives untouched and across a restart, asserted — but **no record
says the warrant was invalidated**, and for an objective-scoped call the
`reason` has no destination at all.

**Consequence, stated plainly.** After invalidation the Kernel retains no
memory of the warrant and the ledger holds only its intent. §12.2's
nineteenth guarantee — *"have an action invisible to audit"* — holds for
actions, but an **invalidation** is now invisible. It is not an orphan
either: §9.5's orphan is *"every expired intent **with attempts** and no
outcome"*, and this has none, so nothing surfaces it.

**Not closed here.** Closing it requires either a fourth `RecordKind` or a
widened outcome vocabulary — C13 and C5 respectively, both GREEN, both
outside this brief. A test asserts the gap against both enums so it cannot
close by accident and pass unnoticed.

### R47 — a suspended Kernel cannot be resumed · **Medium**

§3.5's surface is four operations and none of them resumes. C14 ships
`OverrideSwitch.resume()` and **the Kernel reaches it from nowhere**, so
once suspended the Kernel stays suspended for the life of the process.

The absence is deliberate on both sides: a shipped Part-2 guard forbids any
Kernel name containing `suspend` or `resume`, and adding a fifth operation
would be the speculative API this brief forbids. VEDA 01 §10 makes the
Override a founder gesture and never describes its inverse.

Recorded so the asymmetry is a known limit rather than an assumed one. It
needs a decision about §3.5's surface, not an engineering fix.

### R48 — an objective named `all` cannot be scoped · **Low**

§11.8 puts the literal `all` and §10.5 puts an `objective_id` in the same
parameter. An objective whose id is `"all"` therefore cannot be terminated
narrowly — the call is read as a global Override and suspends the machine.

The collision is in the specification's own vocabulary and is not
introduced here. It is tested and documented rather than defended against,
because defending against it would mean inventing a scope type the
specification does not have.

---

## 5 · Test coverage — 57 tests

Every test names the invariant it proves. The nine areas the brief
specified, and what each established:

| Area | Proves |
|---|---|
| **After authorize** | A minted, unattempted warrant is invalidated; the count is what was invalidated; reaching nothing returns 0 and does not object; an invalidated warrant is not settleable |
| **Suspension** | A global call suspends; the founder's words are carried verbatim; no mint survives (K2 refusal with the reason as detail); **suspension precedes the sweep**; a blank reason cannot silently suspend |
| **After attempt** | An attempted warrant is never invalidated; it still settles under an Override; a mixed set separates correctly; an *exhausted* warrant still counts as attempted |
| **After settle** | A settled warrant is not invalidated again; one terminal transition does not consume another's; its receipt survives the Override |
| **Scope** | An objective scope reaches only that objective; it does **not** suspend; it still spares attempted warrants; an unknown scope reaches nothing; the `all` collision (R48) |
| **Duplicate** | A second call reaches nothing, is never refused, carries the newer reason; a scoped call after a global one lifts nothing |
| **Ordering** | The structural proof of step 1 before step 2; sweep order does not change the result |
| **Ledger durability** | No record is deleted; the intent survives a restart; **nothing is written** (R46); no record type can express an invalidation (R46); an invalidated warrant is not an orphan |
| **Outstanding integrity** | Counts match; survivors' attempt budgets untouched and still spendable; the surviving `Warrant` object is unchanged and identical by reference; no attempt count left behind; no new Kernel state |
| **Replay protection** | An invalidated warrant opens no attempt; does not return after a second sweep; no warrant id is ever reissued; the intent record cannot be rewritten |
| **Determinism** | Two Kernels invalidate identically (count and resulting state); no clock read; no admission read |
| **Must not do** | Settles nothing; compensates nothing; neither admits, assigns, queues, notifies nor publishes; never reaches the ledger |
| **Surface** | Two parameters and no third; no friction parameter; no override writer beside the operation; no resume (R47); the override is still handed out immutable; the public surface is unchanged |

---

## 6 · The "unbuilt operation" guard family reaches zero

Parts 1–7 each asserted how much of §3.5 was still unbuilt. Part 8 makes
that zero, so six guards are **converted rather than deleted**, and every
one gets stronger:

| File | Change |
|---|---|
| `test_kernel_skeleton.py` | The unimplemented parametrization becomes `test_every_operation_is_built`, asserting no operation's source contains `NotImplementedError` |
| `test_kernel_skeleton.py` | `…_is_not_a_refusal` becomes `test_no_operation_remains_unimplemented` — the §7.5 reasoning is kept in the docstring, the assertion becomes a count of **0** |
| `test_kernel_{admission,authorization,preconditions}.py` | `raise NotImplementedError` count 1 → **0** |
| `test_kernel_{mint,settle}.py` | The last-operation guards become working `invalidate()` assertions |
| `test_kernel_attempt.py` | Becomes §11.8 step 3 seen from the attempt side |
| `test_kernel_preconditions.py` | `test_no_override_writer_was_added` — **assertion unchanged**, docstring corrected: the mechanism is now built and is still `invalidate()`'s alone |

No assertion was weakened. The count guard is retained rather than removed
because zero is the strongest value it has ever asserted.

---

## 7 · Quality gates

| Gate | Result |
|---|---|
| Part 8 tests | **57 passed, 0 failed** |
| C15 Parts 1–8 | **417 passed, 0 failed** |
| Foundation (C1–C14) + architecture guards | **1,114 passed, 1 skipped, 1 pre-existing failure** |
| Ruff — all C15 source and tests | **All checks passed** |
| Line length | 88 source / 97 tests (limit 100) |
| §14 R9 ceiling | **163 of 600 statements — 27% consumed.** The complete Kernel is well inside the budget set for it |
| C1–C14 untouched | **0 modified files** in `foundation/` or `ledger/` |

### 7.1 The full suite

`pytest tests/` reports **4,975 passed, 49 failed, 1 skipped**. The failing
file set and per-file counts are **identical to the baseline measured
before Part 6** with the Kernel changes stashed, and none of those files
references the Kernel. Unchanged and out of scope.

---

## 8 · Blockers

**None.** C15 is structurally complete: three checks performed, eight
attestations required, four operations built, zero subsystems owned.

The open decisions are carried from earlier parts and are unchanged by this
one — they are founder decisions about frozen components, not engineering
work. R46 joins them and is the largest of the set: it is the only one that
leaves a constitutional requirement (§4.5's *"all six terminal states are
recorded"*) unmet rather than merely unexpressed.

---

## 9 · Preservation

C1–C14 untouched — zero modified files in `foundation/` or `ledger/`. C8
not opened, no new `RefusalReason`. C14 consumed as shipped:
`OverrideSwitch.suspend()` returns a new value and the Kernel holds it, so
no override writer exists on the Kernel at any privilege level — the
shipped guard still passes with its assertion unchanged.

Changed outside `kernel/`: only the six converted guards and the new test
file. No specification, roadmap, amendment or ADR modified. **No new ADR,
no new concepts, no architecture change, no speculative API.** Part 9 not
begun. No commit, no tag, no Rule 001.

**STOP.** Awaiting Hermes audit.
