# Verification Report — `kalpavriksha-s1-c13.0`

**Gate applied:** Quality Gate Rule 001 · **Verdict: GREEN** · **Date:** 2026-08-05

| | |
|---|---|
| Tag | `kalpavriksha-s1-c13.0` (annotated) |
| Commit | `9f9f21d` |
| Milestone | Sprint 1, Component 13 — Receipt Ledger |
| Previous | `kalpavriksha-s1-c14.0` → `7b74df7`, unchanged |

> **The first stateful component in Sprint 1**, and the hard dependency of all execution.

---

## 1 · Rule 001 criteria

| Criterion | Result |
|---|---|
| Clean checkout, `git status` empty | ✅ |
| **Commit verified before the tag existed** | ✅ |
| **Tag verified afterwards, second independent worktree** | ✅ |
| PYTHONPATH pinned; source isolation asserted | ✅ |
| Full suite + architecture guards against the tag | ✅ |
| Verification report generated | ✅ this document |

## 2 · Test reconciliation

| | At commit `9f9f21d` | At tag |
|---|---|---|
| Full suite | **2,462 passed · 0 failed · 1 skipped** | **2,462 passed · 0 failed · 1 skipped** |
| Architecture guards | 215 passed · 1 skipped · 0 failed | 215 passed · 1 skipped · 0 failed |

**Identical.** Reconciliation: 2,379 at `c14.0` + **83** = **2,462**. Exact.

**C13's dedicated suite: 83 tests**, every one naming the specification clause it defends. Its constitutional guards are inside that file.

## 3 · Ruff

C13's files clean. Repo-wide **21 findings, identical to `c14.0`**. Zero introduced. The one finding Hermes reported (`RUF023`, `__slots__` unsorted) was fixed before this tag.

## 4 · What changed

```
src/master_agent/ledger/receipt_ledger.py   new, 498 lines (150 statements)
src/master_agent/ledger/__init__.py         new, 32 lines
tests/test_foundation_receipt_ledger.py     new, 811 lines
```

**1,341 insertions, 0 deletions, three files.**

**`foundation/__init__.py` is untouched by this tag** — C13 is not a foundation component and exports through its own package.

## 5 · Components 1–12 and 14 unchanged

Byte-identical, verified by diff against `c14.0`.

## 6 · Placement

`master_agent/ledger/`, not `foundation/`. C13 depends on `persistence.StateStore` (Amendment 001 M1), and `foundation/`'s own rule admits a module only if it has *no dependency on any other Kalpavriksha package*. It writes **through** the store and opens no file itself, so `persistence` remains *"the only place in Kalpavriksha that reads or writes persistence files."*

Hermes recorded this as correct (audit R6, observation only).

## 7 · The invariants this tag makes structural

| Requirement | Source | Enforcement |
|---|---|---|
| **No update, no delete, at any privilege level** | Roadmap §2 C13 | `dir()` is scanned, not just the public surface — a private mutator would fail the test too |
| **No buffering, no batching, no background writer** | VEDA 04 A1 | One write is exactly one `append_events` of exactly one event; in-memory count equals store count at every step |
| **The write reaches storage before the call returns** | §7.2 K3 | Asserted directly — this is what lets the Kernel refuse before anything executes |
| **Fail closed and loudly** | §11.3 | A storage failure raises `LedgerUnavailable` and **leaves no trace in memory**; the caller can retry because no phantom duplicate was recorded; the ledger never retries itself |
| Storage failure cannot be swallowed | — | `LedgerUnavailable` is a `RuntimeError`, so `except ValueError` around record construction cannot absorb it |
| **Referential integrity** | §9.2, §9.5 | An attempt or outcome with no intent is refused **before reaching storage** — the reconciliation gap is unwritable, not merely detectable |
| **§9.1's shapes** | §9.1 | One intent per warrant; at most one outcome; **nothing follows the terminal outcome** — and all three survive a restart, because the indexes are rebuilt from the log |
| **Idempotency key** | §8.6 | `(warrant_id, attempt_seq)` recorded once, scoped to the warrant, surviving restart |
| **The consequence is never null** | §14.1, M1's note | Structural; the marker serialises to the literal the specification names |

One test keeps the rest honest: `test_the_spy_store_satisfies_the_shipped_protocol` asserts the test double is an instance of the real `StateStore` Protocol. Without it, every durability and failure test could be proving something about a fiction.

## 8 · Measured write latency

Against the real `JsonFileStateStore`, which `flush()`es and `os.fsync()`s before returning. 300 samples per operation.

| Operation | Median | p95 | Max |
|---|---|---|---|
| `record_intent` | **2.160 ms** | 2.448 ms | 4.234 ms |
| `record_attempt` | 2.269 ms | 2.783 ms | 3.079 ms |
| `record_outcome` | 2.390 ms | 3.043 ms | 9.018 ms |

Replay: 900 records in **27.6 ms** (~31 µs/record).

**~2.2 ms is on the critical path of every action** — §7.2 K3 runs the intent write last and nothing executes until it returns. A three-record action costs ~6.8 ms of durable write, well inside A3's *"milliseconds, not a job cycle"*.

**Roadmap R4 stands: never make this write async.** These numbers exist so that any such proposal must argue against a measurement.

## 9 · Thread safety — documented, not implemented

**Guaranteed:** single thread, single process, one `ReceiptLedger`. Concurrent readers with no writer.

**Not guaranteed:** two named races — check-then-act on every integrity rule, and the store write not being atomic with the in-memory append. Below the ledger there is no file lock, and a torn line is *silently skipped* on read.

Acceptable today only because §3.6 requires Kernel state to be singular and the ledger is written solely by the Kernel at K3 — **but that assumption is unstated and unenforced.** Recorded as **R25**: C15's brief must state that Kernel operations are serialised.

Full analysis in `HEALTH_C13.md` §4.

## 10 · Audit

Hermes final independent audit: **PASS WITH OBSERVATIONS** (`AUDIT_C13.md`). Observations accepted by founder decision; the missing ledger test file was closed by the 83-test dedicated suite, and the single Ruff finding was fixed. No implementation change was required.

## 11 · Risks carried forward

**R25** thread safety (Medium) · **R26** O(n) replay (Low) · **R27** `CompensationRecord` not implemented (Low, deliberate) · **R4** never make the write async (Critical, unchanged) · **N1** `intentId`/`warrant_id` naming — resolved by precedent here without introducing a third synonym.

---

*Generated in clean checkouts of commit `9f9f21d` and tag `kalpavriksha-s1-c13.0`. All temporary worktrees removed.*
