# Health Report — Sprint 1 Component 15, Part 6: `attempt()`

**Type:** Implementation health report. Working-directory evidence only.
**Date:** 2026-08-06
**Status:** Complete. **Not committed, not tagged, no Rule 001.**
**Preceded by:** `HEALTH_C15_PART5.md` and `AUDIT_C15_PART5.md` — *PASS WITH OBSERVATIONS*.
**Ground:** Kernel Specification · ADR-0022 · ADR-0023 · Roadmap v2 (+ Amendments 001–003) · VEDA 01–04.

**Founder constraints honoured, in full:** R39 not solved · C8 not modified ·
no new `RefusalReason` · no GREEN component reopened · Part 6 only · Part 7
not begun · no speculative architecture.

---

## 1 · What was built

| File | | |
|---|---|---|
| `src/master_agent/kernel/kernel.py` | extended | 958 lines, **136 AST statements** (was 120) |
| `src/master_agent/kernel/__init__.py` | extended | exports `AttemptNotAuthorized` |
| `tests/test_kernel_attempt.py` | new | **54 tests** |
| `tests/test_kernel_{skeleton,admission,authorization,preconditions,mint}.py` | 6 superseded guards updated — §7 | — |

**`attempt()` is complete.** `settle()` and `invalidate()` still raise
`NotImplementedError`, asserted by test. `authorize()` is untouched.

```
attempt(warrant_id) -> AttemptToken | KernelRefusal
AttemptNotAuthorized          §3.5's four conditions — see §3
Kernel._attempts              the attempt count, §3.3's Intent lifecycle
```

---

## 2 · The operation, in order

```
   1. resolve the warrant from the outstanding set   → not there:  raise
   2. now = clock.now()                                (never stamp() — §4)
   3. warrant.is_expired(now)                        → expired:    raise
   4. used >= warrant.attempt_budget                 → spent:      raise
   5. record AttemptRecord(warrant_id, used+1, now)  → write fails: KernelRefusal
   6. used = used + 1
   7. return AttemptToken(warrant_id, used, now)
```

**The record is durable before the token exists.** §8.6 makes the token an
idempotency key and C10 states that a Worker holding one *"treats it as
settled fact."* A token issued before the write would authorize an attempt
the ledger has never heard of — §9.5's reconciliation gap arriving one
layer earlier than the orphan it is named for. Asserted by ordering test,
and again by the failure path: a write that fails yields no token and
consumes no budget.

**Expiry is checked before the budget** (§7.1's ordering principle applied
here). A warrant that is both lapsed and spent is reported as lapsed,
because the authorization ending is the more fundamental fact.

**§8.4 has no branch, deliberately.** *"An action classified `irreversible`
is never automatically retried. Ever."* C4 refuses to construct an
irreversible warrant whose `attempt_budget` is anything but 1, so the rule
holds **structurally** through step 4. A second check here would be a rule
that a future edit could remove; an invariant at construction is not. Two
tests prove it end to end rather than by reading the table.

---

## 3 · R40 — the one thing Part 6 could not do constitutionally

**§3.5 requires `attempt()` to *refuse* when a warrant is expired,
cancelled, settled, or out of attempt budget. C8's `RefusalReason` can name
none of the four.**

Its eleven members cover K1's three objective conditions, K2, K3's ledger
write, §7.3's two attestation failures, and §11's four infrastructure
conditions. A lapsed warrant, a spent budget and a settled warrant are none
of those. Measured directly — a test asserts that no member's value
contains `expire`, `budget`, `settled`, `cancel` or `attempt`, so the gap
cannot close by accident and pass unnoticed.

**This is the same gap as the shipped R39, reached from the other
operation.** R39: the envelope breach at the mint has no reason either. One
decision about C8 closes both.

### What was done instead

The four conditions **raise `AttemptNotAuthorized`** — a Kernel-owned
`RuntimeError`, deliberately not a `ValueError`, following
`LedgerUnavailable`'s stated reasoning.

The alternative was a `KernelRefusal` wearing a reason that is not true of
it. C8's own `InvalidKernelRefusal` rules that out:

> *"one that names the wrong check, or names no check at all, is worse than
> no record because it looks like evidence."*

**The behaviour §12.1's twelfth guarantee requires is unaffected** — *"a
live, unexpired, uninvalidated Intent — `attempt()` refuses otherwise."*
Every one of the four conditions fails closed and opens no attempt, writes
nothing, and consumes no budget. **What is missing is the record, not the
refusal.**

**One condition C8 *can* name is returned as a real refusal:** the
`AttemptRecord` write failing → `LEDGER_UNAVAILABLE` at
`K3_RECEIPT_INTENT_WRITE`, `remediable=True`. Downgrading it to an
exception for a uniform shape would have thrown away a refusal the
constitution can record.

**The mixed shape is the honest one and it is temporary.** When the C8
decision that closes R39 is taken, each `raise` site becomes a `return`
one-for-one. Nothing else about this operation changes.

---

## 4 · Four decisions worth naming

**Time is read with `now()`, never `stamp()`.** C1 documents `stamp()` as
consuming a sequence number, and Part 5 derives `warrant_id` from that
sequence. An attempt that spent one would silently shift the identity of
the next warrant minted. A test asserts that a mint, an attempt and a
second mint leave the two warrant ids consecutive.

**The attempt count is Kernel state, not ledger state.** §3.3 assigns the
Intent's *lifecycle* to the Kernel and §4.4's *"one Intent, N attempts"* is
that lifecycle. It cannot live on the `Warrant` — C4: *"a warrant that knew
how many attempts had been used would be a mutable object wearing a frozen
decorator."* It is a count, never a record: the `AttemptRecord` goes to A1,
and the ledger's own `(warrant_id, attempt_seq)` key is the crosscheck, so
a sequence this counter got wrong is refused at the write rather than
recorded.

**K1 is not re-run and K2 is not consulted.** §3.5 lists four conditions
and the objective's state is not among them; re-reading admission would put
a fifth gate on the path no specification asks for. For K2, §11.8 is
precise: suspension *"fails closed on **minting**"*, and its reach into
work already authorized is `invalidate()` — *"invalidate every MINTED
intent not yet attempted"* — while *"intents already ATTEMPTING run to
settlement."* A K2 check here would contradict the second clause and
duplicate the first. Both absences are asserted against the source, because
the absence is the assertion.

**Nothing is published.** §10.2's `ATTEMPT_STARTED` waits for the Event
Bus, which §10.3 makes optional and which arrives with publication.

---

## 5 · Test coverage — 54 tests

| Area | Proves |
|---|---|
| **The successful attempt** | A token is issued; it names the warrant; attempts number 1, 2, 3…; it carries §8.6's idempotency key; two warrants count independently |
| **§8.5 budgets** | All four classes open exactly their budget and no more; an irreversible warrant gets one attempt and no second; a spent budget is never refreshed by waiting; no caller can supply a budget |
| **§4.4 window** | An expired warrant opens nothing; a warrant expiring mid-sequence stops there; expiry is reported before budget; the last moment inside the window still works |
| **Provenance** | An unknown id, a malformed id, another Kernel's warrant, and a refused authorization all open nothing |
| **§9.1 record** | Every attempt is recorded; record and token agree on key and moment; the write precedes the token; a ledger failure refuses and consumes no attempt; a settled warrant opens nothing; the intent record is untouched; records survive a restart |
| **Determinism & non-interference** | The warrant is never mutated; attempting does not settle; no clock sequence is consumed; no admission read; no override read; nothing minted; no attestation re-verified |
| **R40 · R41** | The vocabulary gap is asserted, not assumed; the exception is not a refusal in disguise and not a `ValueError`; the digest is not checked here |
| **Nothing beyond Part 6** | Two operations still unimplemented; surface unchanged; no publishing; no attestor; dependency set unchanged; no ambient time; R9 ceiling |

---

## 6 · Quality gates

| Gate | Result |
|---|---|
| Part 6 tests | **54 passed, 0 failed** |
| C15 Parts 1–6 | **294 passed, 0 failed** |
| C15 Parts 1–6 + C9.1 | **413 passed, 0 failed** |
| Foundation (C1–C14) + architecture guards | **828 passed, 1 skipped, 0 failed** |
| Ruff — all C15 source and tests | **All checks passed** |
| Line length | 88 source / 84 tests (limit 100) |
| §14 R9 ceiling | **136 of 600 statements — 23% consumed** (was 20%) |
| C1–C14 untouched | **0 modified files** in `foundation/` or `ledger/` |

### 6.1 The full suite, stated honestly

`pytest tests/` reports **4,852 passed, 49 failed, 1 skipped**.

**All 49 failures are pre-existing and unrelated to Part 6.** Measured, not
assumed: the same five files fail identically with the Part 6 changes
stashed, and none of them references the Kernel.

| File | Failures |
|---|---|
| `test_missions_console.py` | 27 |
| `test_memory_integration.py` | 16 |
| `test_missions_architecture.py` | 4 |
| `test_foundation_clock.py` | 1 |
| `test_founder_approval_workflow.py` | 1 |

Recorded here rather than fixed: they are outside C15 and outside this
brief.

---

## 7 · Six superseded guards

Parts 1–5 asserted `attempt()` was unimplemented. Part 6 makes that false,
so each is updated rather than deleted, and **no assertion is weakened**.

| File | Change |
|---|---|
| `test_kernel_skeleton.py` | `attempt` removed from the unimplemented parametrization |
| `test_kernel_skeleton.py` | `__slots__` guard now names `_attempts`, with the reasoning for why §3.4 does not assign it elsewhere |
| `test_kernel_{admission,authorization,preconditions}.py` | `raise NotImplementedError` count 3 → **2** |
| `test_kernel_mint.py` | `…_other_three_operations_remain_unimplemented` → `…_other_two_…` |

The counts still pin exactly how much is unbuilt.

---

## 8 · Risks

| # | Risk | Severity | Note |
|---|---|---|---|
| **R40** | **No `RefusalReason` covers any of §3.5's four `attempt()` conditions.** Expired, cancelled, settled and out-of-budget raise instead of refusing, so §7.5's *"refusals are recorded"* is unmet for them | **Medium** | **New.** Behaviour is defined, fail-closed and tested; only the record is missing. **Same family as R39, and one C8 decision closes both** |
| **R41** | **The payload digest is not checked at `attempt()`.** §4.4 says it is — *"the digest is checked at `attempt()`, not merely at mint"* — but §3.5 and Roadmap Amendment 001 M4 give the operation an identifier and nothing else, so there is no capability or payload to compare | **Medium** | **New.** Non-transferability holds at mint; it does not hold at attempt. Closing it requires a signature §3.5 fixes, so it is recorded rather than taken |
| **R42** | **§3.5's *cancelled* and *settled* have no Kernel-side gate in Part 6.** Nothing leaves the outstanding set until Parts 7–8. A settled warrant is stopped today by C13's referential integrity, not by a liveness check | **Low** | **New.** Enforced either way and tested. Part 7 removes settled warrants from the outstanding set and the gate becomes the Kernel's own |
| **R39** | No `RefusalReason` covers an envelope breach | Medium | **Carried, untouched by instruction** |
| **R34** | The A2 attestation does not bind to the carried class | High | Carried. Not reached by this part |
| **R38** | `read_only = 5` is not forced by the specification | Low | Carried. Exercised here — five attempts, then refused |
| **R37** | `expires_at` omits grant validity | Low | Carried. Can only lengthen the window this part enforces |
| **R31** | Attestation freshness window unratified | Medium | Carried |
| **R6** | §14 R9's 600-statement ceiling | High | **23% consumed.** `attempt()` cost 16 statements. Parts 7–8 have ample room |

---

## 9 · Blockers

**None for Parts 7 and 8.** Both were declared unblocked by ADR-0023 §6.2
and nothing here changes that. `settle()` has the attempt count it needs to
write `Receipt.attempt`, and `invalidate()` has the outstanding set.

**R40 and R39 together are the one open decision the Kernel needs**, and it
is a founder decision about C8, not an engineering one.

---

## 10 · Preservation

C1–C14 untouched — zero modified files in `foundation/` or `ledger/`.
C9.1 (`kalpavriksha-s1-c9.1`) consumed as shipped. C8 not opened. No new
`RefusalReason`, no new `KernelCheck`, no new `AttestationQuestion`.

Changed outside `kernel/`: only the six superseded guards and the new test
file. No specification, roadmap, amendment or ADR modified. **No new ADR,
no new concepts, no architecture change.** Part 7 not begun. No commit, no
tag.

**STOP.** Awaiting Hermes audit.
