# Verification Report — `kalpavriksha-s1-c18.0`

**Gate applied:** Quality Gate Rule 001 · **Verdict: GREEN** · **Date:** 2026-08-06

| | |
|---|---|
| Tag | `kalpavriksha-s1-c18.0` (annotated) |
| Commit verified | `01497c3` — `01497c36b001fefb13516557fbb61fff87ef1d0c` |
| Milestone | Sprint 1, Components 16, 17 and 18 |
| Previous milestone | `kalpavriksha-s1-c15.0` → `c565244` |
| Commits since | `cb18e9d` C16 · `cecd972` C17 · `01497c3` C18 — linear, nothing rewritten |
| Independent audit | Hermes — **C17 PASS** · **C18 PASS WITH OBSERVATIONS**, recommending *"Proceed to Rule 001"* |

---

## 1 · Rule 001 gate checklist

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | **Clean checkout** — `git worktree` outside the project directory | ✅ | Two worktrees under `…/Temp/claude/`; `git status --porcelain` **empty** in both |
| 2 | **Source isolation confirmed** | ✅ | Probe asserts `master_agent.__file__` is under the worktree with no `MasterAgent` path segment. All four packages — `kernel`, `coordinator`, `api`, `runtime_bridge` — confirmed importing from the worktree |
| 3 | **Commit verified *before the tag existed*** | ✅ | Full suite, guards and Ruff run at `01497c3` with no tag pointing at it |
| 4 | **Tag verified afterwards, second independent worktree** | ✅ | Re-run at `kalpavriksha-s1-c18.0`. Identical numbers |
| 5 | **Full suite against the tag, zero failures, reconciled by count** | ✅ | **3,085 passed · 0 failed · 1 skipped.** Reconciliation exact — §3 |
| 6 | **Architecture guards against the tag**, six committed modules, named | ✅ | **215 passed · 1 skipped · 0 failed** — §4 |
| 7 | **Lint against the tag** — components clean, repo-wide not increased | ✅ | All three clean; repo-wide **21**, identical to `c15.0` — §5 |
| 8 | **Prior components byte-identical**, proven by blob SHA-1 | ✅ | Every change since `c15.0` is an **addition** — §6 |
| 9 | **Verification report generated** | ✅ | This document |

| | |
|---|---|
| `PYTHONPATH` pinned to each worktree's `src/` | ✅ both runs |
| Working directory used as evidence | **No.** Every number below comes from a clean checkout |

### 1.1 Failure categorisation

Rule 001 requires every failure to be categorised as *committed code ·
untracked work · introduced by this change · test assumption*.

> **There were no failures at the commit or at the tag.** The table is
> empty, and that is the finding.

The working directory's 49 failures — five files, unchanged since before
C16 — are all *untracked work* and are absent from this tag, exactly as
they were absent from `c15.0`. §8 records the measurement.

---

## 2 · The two runs

| | Commit `01497c3` (before the tag existed) | Tag `kalpavriksha-s1-c18.0` |
|---|---|---|
| Full suite | **3,085 passed · 0 failed · 1 skipped** | **3,085 passed · 0 failed · 1 skipped** |
| Architecture guards (6 modules) | 215 passed · 1 skipped · 0 failed | 215 passed · 1 skipped · 0 failed |
| Ruff — the three components | All checks passed | All checks passed |
| Ruff — repo-wide | 21 findings | 21 findings |
| Wall clock | 148.22 s | 160.39 s |

**Identical.** Order of operations honoured: commit → verify the commit →
tag → re-verify. The tag was created only after the commit run was green.

---

## 3 · Test reconciliation against the previous milestone

```
   2,896   at kalpavriksha-s1-c15.0
   +   56   C16  Execution Coordinator
   +   52   C17  Kernel API
   +   81   C18  Runtime Integration Layer
   ───────
   3,085   at kalpavriksha-s1-c18.0        ← measured: 3,085
```

**Exact. Zero unexplained delta.**

Measured at the tag, per suite: `test_coordinator.py` **56**,
`test_kernel_api.py` **52**, `test_runtime_bridge.py` **81**. C15's own
suites are unchanged at **469** (`test_kernel_*.py`, which includes the
C17 API suite by filename — the 417 Kernel tests plus 52). The 1 skipped
test is the same one skipped at every milestone since `c1.1`.

---

## 4 · Architecture guards

The six modules committed at this tag, named individually and executed
against it:

| Module | Result |
|---|---|
| `test_browser_constitution_compliance.py` | ✅ |
| `test_dashboard_architecture.py` | ✅ |
| `test_mission_control_architecture.py` | ✅ |
| `test_persistence_architecture.py` | ✅ |
| `test_runtime_approval_boundary.py` | ✅ |
| `test_runtime_architecture.py` | ✅ |
| **Combined** | **215 passed · 1 skipped · 0 failed** |

**Identical to `c15.0`, `c9.1`, and every milestone since `c8.0`.** Three
new packages disturbed no guard, and none was added or changed.

Each component's own constitutional guards are counted separately, inside
its suite, and include the dependency-direction assertions §3.6 requires:

| Component | Dependency set, asserted by test |
|---|---|
| **C16** | `master_agent.foundation.*` and `master_agent.kernel` only |
| **C17** | `master_agent.foundation.*` and `master_agent.kernel` only |
| **C18** | those plus `master_agent.coordinator`, `master_agent.api`, `master_agent.runtime_bridge` — **C1–C17 only**, and `master_agent.runtime` (MB024's engine) explicitly not reached |

---

## 5 · Ruff

| | |
|---|---|
| `src/master_agent/coordinator/`, `api/`, `runtime_bridge/` and their three suites | **All checks passed** |
| Repository-wide | **21 findings** |
| Repository-wide at `c15.0` | 21 findings |
| **Introduced by this milestone** | **0** |

The 21 are the pre-Sprint-1 Tier A baseline in `RUFF_DEBT_REGISTER.md`.
The non-increasing condition holds.

---

## 6 · C1–C15 unchanged

### 6.1 The whole tracked tree

`git diff --name-status kalpavriksha-s1-c15.0 kalpavriksha-s1-c18.0`, over
the entire repository:

```
A  src/master_agent/api/__init__.py
A  src/master_agent/api/kernel_api.py
A  src/master_agent/coordinator/__init__.py
A  src/master_agent/coordinator/coordinator.py
A  src/master_agent/runtime_bridge/__init__.py
A  src/master_agent/runtime_bridge/codec.py
A  src/master_agent/runtime_bridge/runtime.py
A  tests/test_coordinator.py
A  tests/test_kernel_api.py
A  tests/test_runtime_bridge.py
```

**Ten files, all `A`. No `M`, no `D`, anywhere in the repository.**

### 6.2 Blob SHA-1 proof

`git ls-tree -r` over `src/master_agent/foundation/`,
`src/master_agent/ledger/` and `src/master_agent/kernel/` at both tags,
compared by blob hash:

> **18 files. Every blob SHA-1 identical.**

Byte-identity is therefore proven rather than inspected, for **C1 Clock ·
C2 Principal · C4 Warrant · C5 Receipt · C7 Attestation · C8 Refusal ·
C9.1 Execution Request · C10 Attempt Token · C11 Admission Record ·
C12 Reversibility Registry · C13 Receipt Ledger · C14 Override ·
C15 Constitutional Kernel**.

**C17 was not modified by C18.** R53 was resolved by placing the decoder
in the Runtime — the caller, per ADR-0022 D2 — and `api/kernel_api.py`
carries the same content it was committed with in `cecd972`.

`master_agent/runtime/` (MB024's Runtime Engine) is likewise untouched and
is never imported, which is why C18's package is named `runtime_bridge`.

---

## 7 · Three commits under one tag, and why

**C18 imports C16 and C17.** `runtime_bridge/runtime.py` imports
`master_agent.api` and `master_agent.coordinator`; a tag naming C18 alone
could not be checked out, and Rule 001 would have failed at the first
worktree run with an `ImportError`.

So the three land as one milestone: three commits, linear, one tag on the
last. Each commit names its own component and its own recorded risks.

**Consequence, stated plainly:** `cb18e9d` (C16) and `cecd972` (C17) carry
no tag and no verification report of their own. They are verified here, as
part of the tree this tag certifies — the full suite at the tag executes
all 56 C16 tests and all 52 C17 tests, and §3 reconciles them individually.

---

## 8 · Working directory versus the tag

`pytest tests/` in the project working directory reports **49 failures**
across five files. The same suite at this tag reports **zero**.

Unchanged from the measurement recorded at `c15.0`: three of the five
files exist at no tag, and the other two fail only against locally
modified copies (`test_founder_approval_workflow.py`, and the ambient-time
guard reacting to a modified `launcher/boot.py`). **All five are
*untracked work*.** None is committed code, none was introduced by this
change, and none is a test assumption.

Per Rule 001, *"the working directory is never considered evidence."* No
number in §2 through §6 comes from it.

---

## 9 · What this milestone contains

```
   Desktop UI · CLI · future services
        │
        ▼
   C18  Runtime Integration Layer     124 AST statements
        │      transport · serialization · wiring
        ▼
   C17  Kernel API                     64 AST statements
        │      the single integration boundary
        ▼
   C16  Execution Coordinator          73 AST statements
        │      §6.1's sequence, composed once
        ▼
   C15  Constitutional Kernel         163 AST statements
```

**261 statements across the three new components.** Each holds one
collaborator and no state; each asserts its own dependency set by test.

| Guarantee | Held by |
|---|---|
| §6.3's mandatory settlement is structural, not remembered | C16 |
| §8.4 — an irreversible action is never automatically retried | C16, at the layer §3.4 assigns the loop to |
| A surface never imports the Kernel | C17, and a repo-wide guard that fails the build if one does |
| §7.5 — a refusal and an error stay apart on the wire | C17, three response kinds |
| ADR-0022 D2 — the caller is a courier, never an author | C18 owns deserialization; the Kernel API stays a projection |
| C9's line — a malformed request is not a constitutional refusal | C18, visible on the wire as two distinct type names |

---

## 10 · Audit findings, and why none required a code change

Hermes, `Engineering/AUDIT_C18.md`: **PASS WITH OBSERVATIONS**,
recommending *"Proceed to Rule 001"*.

| Finding | Severity | Disposition |
|---|---|---|
| **R55** — the composed sequence is in-process only | Medium | Architectural scope limit, already recorded in `HEALTH_C18.md` §9. No mitigation assigned to C18 |
| **R56** — an unknown operation echoes an unvalidated string | Low | Audit: *"Document as expected behaviour; C20/C21 surfaces must handle untrusted `operation` field"* |
| **R57** — no inbound timeout or envelope size limit | Medium | Audit: *"Add… in Sprint 2 when HTTP transport added."* The C18 brief forbade an HTTP server, and the Roadmap requires none in Sprint 1 |
| **R58** — no metrics or observability hooks | Low | Operational, Sprint 2 |

**No finding required a code change, and none was made.** The tree at this
tag is the tree Hermes audited.

**One factual correction to the audit, recorded rather than argued.**
§8 credits a *"SpyStore double verified against `StateStore` protocol"* as
a false-confidence indicator. **No such double exists in
`tests/test_runtime_bridge.py`.** The suite's doubles are the
`StubAdmissions` provider the Kernel's own suite ships, two `ReceiptLedger`
subclasses that fail a single write, and a `Recorder` work callable. The
verdict does not rest on that row.

---

## 11 · One process observation

**`Engineering/AUDIT_C16.md` is absent.** `AUDIT_C17.md` and
`AUDIT_C18.md` are on file; no independent audit of C16 was recorded.

An audit is **not** a Rule 001 gate, so this does not affect the verdict.
Recorded because it is a gap in the evidence trail rather than in the
code: C16's 56 tests pass at this tag, and Hermes's C18 audit independently
verified C16 as unmodified (§4) and exercised it through `Runtime.execute()`
(§2, §6). Whether a retrospective C16 audit is wanted is a founder
decision.

---

## 12 · Open items carried past this tag

Recorded in `Engineering/HEALTH_C15_PART*.md`, `HEALTH_C16.md`,
`HEALTH_C17.md`, `HEALTH_C18.md` and `AUDIT_C18.md`, and **not solved
here**:

**R34 · R37 · R38 · R39 · R40 · R41 · R43 · R44 · R45 · R46 · R47 ·
R48 · R49 · R50 · R51 · R52 · R54 · R55 · R56 · R57 · R58**

**R53 is CLOSED** by C18 — the deserialiser lives in the Runtime, the
Kernel API is unchanged, and the courier discipline holds.

**R51 remains the largest open item:** the fifteen inventoried entry points
in `orchestrator/`, `executor/`, `runtime/` and `cli.py` still reach tools
without a `warrant_id`. C16, C17 and C18 build the path they will be
migrated *to*; the migration itself is not in any of them.

None of the twenty-one is a Rule 001 gate. Each is documented, fail-closed,
and covered by a test that asserts the gap so it cannot close unnoticed.

---

## 13 · Cleanup

Both verification worktrees were removed after the runs recorded above.
`git worktree list` shows only the project directory.

---

*Generated in clean, isolated checkouts of commit `01497c3` and tag
`kalpavriksha-s1-c18.0`, per Quality Gate Rule 001. `PYTHONPATH` pinned to
each worktree's `src/` and source isolation asserted before either suite
ran. No implementation was modified, no component reopened, and no gate
lowered.*
