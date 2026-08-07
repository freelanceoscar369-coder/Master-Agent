# Health Report — Sprint 1 Component 13: Receipt Ledger

**Type:** Implementation health report. Working-directory evidence only.
**Date:** 2026-08-05
**Status:** Implementation and dedicated verification complete. **Not committed, not tagged.**
**Rule 001:** **attempted 2026-08-05 and BLOCKED at the commit gate** — see `RULE001_C13_BLOCKED.md`. Every quality gate passes; C13's five predecessors (C9, C10, C11, C12, C14) were never committed, and `receipt_ledger.py` imports C9. A C13-only tag was proven in a clean worktree not to collect its own tests. **No commit and no tag were created.** Awaiting a sequencing decision.

> **Note on this file.** The brief asked for an *updated* `HEALTH_C13.md`. None existed — C13 was implemented but its health report was never produced before the Hermes audit. This is the first issue.

---

## 1 · What was built

| File | | Lines |
|---|---|---|
| `src/master_agent/ledger/receipt_ledger.py` | new | 498 (150 AST statements) |
| `src/master_agent/ledger/__init__.py` | new — exports | 31 |
| `tests/test_foundation_receipt_ledger.py` | **new, this brief** | 811 (381 AST statements) |

**Public surface**

```
ReceiptLedger         record_intent · record_attempt · record_outcome · read
                      has_intent · is_settled · __len__
IntentRecord          frozen — A1's field list
AttemptRecord         frozen — §8.6's idempotency key as two flat identifiers
RecordKind            closed enum, 3 — the wire discriminator
LedgerUnavailable     RuntimeError — the fail-closed signal
LedgerIntegrityError  subclass of the above
InvalidLedgerRecord   ValueError, raised at construction
```

The outcome record **is** the shipped `Receipt` (C5) — which is why Amendment 001 M1 lists C5 among this component's dependencies. There is no second outcome type.

**Placement.** `master_agent/ledger/`, not `foundation/`. C13 depends on `persistence.StateStore` (Amendment 001 M1), and `foundation/`'s own rule is that a module belongs there only if it has *no dependency on any other Kalpavriksha package*. The Hermes audit records this as correct (R6, observation only).

---

## 2 · Work done under this brief

### 2.1 Dedicated verification suite — 83 tests

`tests/test_foundation_receipt_ledger.py`. **Every test names the specification clause it defends.** The file header carries the clause table, and no test exists to raise coverage.

| Required area | Tests | Representative invariant proven |
|---|---|---|
| **Append-only** | 5 | No mutator exists **at any privilege level** — `dir()` is scanned, not just the public surface. History is monotonic and no prior entry ever changes |
| **Ordering** | 5 | Append order is preserved globally, per-warrant, and **across a restart** |
| **Durability assumptions** | 5 | The write reaches the store **before the call returns** (this is what K3 depends on); one write is exactly one `append_events` of exactly one event — no batching; in-memory count and store count are equal at every step — no buffering; a second, independently-constructed ledger over the same `JsonFileStateStore` root sees the record, which is only possible if it hit the filesystem |
| **Failure behaviour** | 8 | A storage failure raises and **leaves no trace in memory**; the caller can retry because no phantom duplicate was recorded; the ledger itself never retries (exactly one `append_events` call); an unreadable log fails closed at construction; `LedgerUnavailable` is **not** a `ValueError`, so `except ValueError` cannot swallow it; `LedgerIntegrityError` subclasses it so one `except` catches every refusal |
| **Referential integrity** | 5 | An attempt or outcome with no intent is refused **before reaching storage** — the orphan §9.5 calls a reconciliation gap is unwritable rather than merely detectable |
| **Impossible states** | 5 | One intent per warrant; at most one outcome; **nothing follows the terminal outcome**; and all three still hold after a restart, because the indexes are rebuilt from the log |
| **Duplicate protection** | 4 | `(warrant_id, attempt_seq)` — §8.6's key — is recorded once, is scoped to the warrant, and survives a restart |
| **Deterministic serialization** | 8 | A1's field list exactly; the consequence is **never** serialised as null (§14.1); every record is tagged with its `RecordKind`; records round-trip through storage **equal** to the originals; `Decimal` precision and timezone normalisation both survive |
| Record construction invariants | 24 | Identifiers, the never-null consequence, blank `rule_ref`, naive timestamps, 1-based sequences |
| Constitutional | 6 | Never decides/evaluates/authorizes/retries; reads no ambient time; imports nothing that could act; depends on `persistence` **only through the `StateStore` Protocol**; the store is injected, never constructed; the write surface is exactly the three the roadmap declares |

**One test exists to keep the others honest:** `test_the_spy_store_satisfies_the_shipped_protocol` asserts the test double is an instance of the real `StateStore` Protocol. Without it, every durability and failure test above could be proving something about a fiction.

### 2.2 The single Ruff finding — fixed

`RUF023` — `ReceiptLedger.__slots__` not sorted. Verified independently before fixing (one finding, matching the audit's R5). Sorted. **Nothing else in the module was touched.**

A second finding then appeared in the *new test file* (`RUF007`, `zip()` over successive pairs) and was fixed with `itertools.pairwise`. One over-length line (123 chars, in the header table) was also wrapped — Ruff does not flag it because `E501` is absent from the resolved rule set, which is **RUFF-GOV-01** showing up again.

---

## 3 · Write latency — measured

Against the real `JsonFileStateStore`, which `flush()`es and `os.fsync()`s before returning. 300 samples per operation, Windows 11, project working directory on `D:`.

| Operation | Median | Mean | p95 | Max |
|---|---|---|---|---|
| `record_intent` | **2.160 ms** | 2.171 ms | 2.448 ms | 4.234 ms |
| `record_attempt` | **2.269 ms** | 2.304 ms | 2.783 ms | 3.079 ms |
| `record_outcome` | **2.390 ms** | 2.455 ms | 3.043 ms | 9.018 ms |

**Replay cost:** 900 records reconstructed in **27.6 ms** at construction (~31 µs/record).

### 3.1 Reading these numbers

**~2.2 ms is the cost of honesty, and it is on the critical path of every action.** §7.2 K3 runs the intent write last, and nothing executes until it returns — so every action in Kalpavriksha pays this once, plus once per attempt and once at settlement. A three-record action costs ~6.8 ms of durable write.

That is well inside VEDA 04 A3's *"milliseconds, not a job cycle"* framing and is not a demo risk at Founder Edition scale.

**The `fsync` dominates.** The 9 ms outlier on `record_outcome` is the filesystem, not the code — which is the correct place for the cost to be. **Roadmap R4 is the standing warning: never make this write async.** These numbers exist so that a future change proposing to do so has to argue against a measurement.

**Replay grows linearly** and is paid once per process start. At 900 records it is 27.6 ms; at 100,000 it would be roughly 3 s. That is a real number for a long-lived install and is recorded as **R26**.

---

## 4 · Thread-safety assumptions — documented, not implemented

Per the brief: **current guarantees only. No thread safety was implemented and no locking was added.**

### 4.1 What is guaranteed today

| Context | Guarantee |
|---|---|
| **Single thread, single process, one `ReceiptLedger`** | **Fully correct.** Every invariant in §2.1 holds unconditionally. This is the only context the implementation guarantees |
| Concurrent **readers** with no writer | Safe. `read()` copies into a tuple; the records are frozen value objects |

### 4.2 What is *not* guaranteed — two named races

**Race 1 · Check-then-act on every integrity rule.** Each writer follows the shape:

```
    if record.warrant_id in self._intents:   # check
        raise LedgerIntegrityError(...)
    self._append(record)                     # write
    self._intents.add(record.warrant_id)     # act
```

Two threads can both pass the check before either reaches the `add`. **Result: two intent records for one warrant, in the durable log**, which §9.1 forbids and which no later read can disambiguate. The same shape governs duplicate attempts and second outcomes.

**Race 2 · The store write and the in-memory history are not one atomic step.** `_append()` calls `append_events()` and *then* appends to `self._entries`. Two threads interleaving can produce an in-memory order that differs from the durable order — so `read()` and a restart would disagree about sequence.

### 4.3 Below the ledger

`JsonFileStateStore.append_events()` opens in `"a"` mode, writes, flushes, `fsync`s. There is **no file lock**. Two processes writing one root can interleave partial lines; `read_events()` skips a malformed line, so the failure mode is a **silently dropped record** rather than a crash — which is worse for an audit spine.

Each `ReceiptLedger` also holds its **own** in-memory index, so two instances over one store cannot see each other's writes and neither one's duplicate protection is sound.

### 4.4 Why this is acceptable today, and where it must be revisited

Kernel Specification §3.6 requires the Kernel's state to be *"singular across every Operator Instance"*, and the ledger is written **only** by the Kernel at K3. A single-writer Kernel makes the single-threaded guarantee sufficient **by architecture rather than by accident**.

That assumption is currently **unstated and unenforced**. It becomes load-bearing at:

- **C15 Kernel** — its brief must state that `authorize()`, `attempt()` and `settle()` are serialised, or the races in §4.2 are reachable.
- **C16 Execution Path Unification** — 15 entry points converge; if any invokes the Kernel concurrently, Race 1 is live.
- Any future multi-process or multi-Operator deployment — which needs file locking or a different store, not a change here.

Recorded as **R25**. **No mitigation was implemented**, per this brief.

---

## 5 · Quality gates

| Gate | Result |
|---|---|
| C13 component tests | **83 passed, 0 failed** (0.23 s) |
| Ruff — `src/master_agent/ledger/` + new tests | **All checks passed** |
| Line length | 80 / 76 / 96 (limit 100) |
| Architecture guards (boundary check for the new package) | **215 passed, 1 skipped, 0 failed** |
| Write latency | Measured, §3 |

Architecture guards were run because C13 introduces a new package and could have crossed a boundary another component's guard defends. It had not. **No repository-wide test run was performed**, per the brief.

---

## 6 · Risks

| # | Risk | Severity | Status |
|---|---|---|---|
| **R25** | **The ledger is not thread-safe, and the single-writer assumption is unstated.** Two named races, §4.2 | **Medium** | **New.** Not a defect under the architecture's own single-Kernel rule (§3.6) — but that rule is not enforced anywhere. **C15's brief must state that Kernel operations are serialised** |
| **R26** | **Replay is O(n) at every process start** — 27.6 ms per 900 records, ~3 s at 100k | Low | **New.** Acceptable for the Founder Edition. `StateStore` already supports snapshots, so the fix exists when needed and is not a C13 change |
| **R27** | **`CompensationRecord` is not implemented.** §9.1 names four record types; the roadmap's declared surface has three writers | Low | **New, deliberate.** Adding a fourth writer would exceed Roadmap §2 C13. §6.4 — *"Compensation exits through the Kernel too"* — so a compensating action mints its own intent and is recorded as a normal tree; only the explicit `compensates:` link is missing |
| **R4** | *"Never make the ledger write async"* — Roadmap §5 | **Critical** | Unchanged. §3 now supplies the measurement any such proposal must argue against |
| **N1** | `intentId` / `warrant_id` naming | Medium | **Landed here, and resolved by precedent.** `record_intent()` **returns** the identifier (A1's `→ intentId`) while the field is named `warrant_id`, following the shipped `Warrant`, `ExecutionContext`, `Receipt` and `AttemptToken`. No new synonym was introduced. An ADR recording the equivalence is still the clean close |
| **RUFF-GOV-01** | `line-length = 100` configured but not enforced by the resolved rule set | Medium | **Confirmed live again** — a 123-character line passed Ruff and was caught only by measurement |

---

## 7 · Blockers

**None.**

**C15's prerequisites are now complete** — C11, C12, C13 and C14 are all built. C15 remains gated only on this component's Rule 001 verification, which the founder has withheld pending Hermes re-audit.

---

## 8 · Preservation

C1–C12 and C14 untouched. `foundation/__init__.py` **not modified** — C13 is not a foundation component and exports through its own package. No specification, roadmap, amendment or ADR modified. No commit, no tag.

**STOP.** Awaiting Hermes re-audit.
