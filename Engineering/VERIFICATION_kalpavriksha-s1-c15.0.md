# Verification Report — `kalpavriksha-s1-c15.0`

**Gate applied:** Quality Gate Rule 001 · **Verdict: GREEN** · **Date:** 2026-08-06

| | |
|---|---|
| Tag | `kalpavriksha-s1-c15.0` (annotated) |
| Commit | `c565244` — `c56524400ff671521fdd69076d85eeeb52ac7f5d` |
| Milestone | Sprint 1, Component 15 — The Constitutional Kernel, Parts 1–8 |
| Previous milestone | `kalpavriksha-s1-c9.1` → `e224fd8` |
| Parent commit | `e224fd8` — history is linear, nothing rewritten |
| Independent audit | Hermes, per part. Parts 5, 6, 7, 8 — **PASS** |

**This is a release-engineering verification, not an architectural review.**
Each part was independently audited before this gate was run.

---

## 1 · Rule 001 gate checklist

Against the governing rule in `Engineering/QUALITY_GATE_RULES.md`, and the
four criteria it requires of a verification report.

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | **Clean checkout** — `git worktree` outside the project directory | ✅ | Two worktrees under `…/Temp/claude/`; `git status --porcelain` **empty** in both |
| 2 | **Source isolation confirmed** — imports resolve inside the worktree | ✅ | Probe asserts `master_agent.__file__` is under the worktree and contains no `MasterAgent` path segment. Run in both |
| 3 | **Commit verified *before the tag existed*** | ✅ | Full suite, guards and Ruff run at `c565244` with no tag pointing at it. §2 |
| 4 | **Tag verified afterwards, in a second independent worktree** | ✅ | Re-run at `kalpavriksha-s1-c15.0`. Identical numbers. §2 |
| 5 | **Full test suite against the tag, zero failures, reconciled by count** | ✅ | **2,896 passed · 0 failed · 1 skipped.** Reconciliation exact — §3 |
| 6 | **Architecture guards against the tag**, six committed modules, named | ✅ | **215 passed · 1 skipped · 0 failed.** §4 |
| 7 | **Lint against the tag** — component clean, repo-wide not increased | ✅ | C15 clean; repo-wide **21**, identical to `c9.1`. §5 |
| 8 | **Prior components byte-identical**, proven by blob SHA-1 | ✅ | Every change since `c9.1` is an **addition**. §6 |
| 9 | **Verification report generated** | ✅ | This document |

| | |
|---|---|
| `PYTHONPATH` pinned to the worktree's `src/` | ✅ both runs |
| Working directory used as evidence | **No.** Every number below comes from a clean checkout |

### 1.1 Failure categorisation

Rule 001 requires every failure to be categorised as *committed code ·
untracked work · introduced by this change · test assumption*.

> **There were no failures at the commit or at the tag.** The category
> table is empty, and that is the finding.

See §7 for why the working directory shows failures that the tag does not
— it is the exact condition Rule 001 was written to expose, and it is
resolved in the correct direction.

---

## 2 · The two runs

| | Commit `c565244` (before the tag existed) | Tag `kalpavriksha-s1-c15.0` |
|---|---|---|
| Full suite | **2,896 passed · 0 failed · 1 skipped** | **2,896 passed · 0 failed · 1 skipped** |
| Architecture guards (6 modules) | 215 passed · 1 skipped · 0 failed | 215 passed · 1 skipped · 0 failed |
| C15's own suite | — | **417 passed · 0 failed** |
| C9.1's own suite | — | **119 passed · 0 failed** |
| Ruff — C15 files | All checks passed | All checks passed |
| Ruff — repo-wide | 21 findings | 21 findings |
| Wall clock | 134.91 s | 125.42 s |

**Identical.** Order of operations honoured: commit → verify commit → tag
→ re-verify. The tag was created only after the commit run was green.

---

## 3 · Test reconciliation against the previous milestone

```
   2,479   at kalpavriksha-s1-c9.1
   +  417   C15's own suite (Parts 1-8)
   ───────
   2,896   at kalpavriksha-s1-c15.0        ← measured: 2,896
```

**Exact. Zero unexplained delta.**

C15's 417 tests, by part:

| Part | Suite | Tests |
|---|---|---|
| 1 | `test_kernel_skeleton.py` | structure, the four operations, §3.4/§3.6 guards |
| 2 | `test_kernel_admission.py` | K1 objective binding, the `AdmissionProvider` port |
| 3 | `test_kernel_authorization.py` | §7.3's eight attestations |
| 4 | `test_kernel_preconditions.py` | K2, and §7.4's precondition set in order |
| 5 | `test_kernel_mint.py` | K3's receipt-intent write, and the mint |
| 6 | `test_kernel_attempt.py` | 54 — liveness, budget, `AttemptRecord`, idempotency key |
| 7 | `test_kernel_settle.py` | 64 — the terminal outcome record, deterministic receipts |
| 8 | `test_kernel_invalidate.py` | 57 — the Override's mechanism, at both scopes |
| | **Total, measured at the tag** | **417** |

C9.1's suite is unchanged at **119**, the figure recorded in
`VERIFICATION_kalpavriksha-s1-c9.1.md`. The 1 skipped test is the same one
skipped at every milestone since `c1.1`.

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

**Identical to `c9.1` and to every milestone since `c8.0`.** C15 adds no
architecture-guard module and changes none.

C15's own constitutional guards are counted separately, inside its 417,
and include the dependency-direction assertions §3.6 requires: the Kernel
imports only `master_agent.foundation.*` and `master_agent.ledger.*`,
imports no attestor, no Worker, no Provider and no Objective Engine, reads
no ambient time, opens no file, and touches no store.

---

## 5 · Ruff

| | |
|---|---|
| C15 source and tests (11 files) | **All checks passed** |
| Repository-wide | **21 findings** |
| Repository-wide at `c9.1` | 21 findings |
| **Introduced by this milestone** | **0** |

The 21 are the pre-Sprint-1 Tier A baseline tracked in
`RUFF_DEBT_REGISTER.md`. The non-increasing condition holds.

---

## 6 · C1–C14 unchanged, except the intentional C9.1 amendment

### 6.1 The whole tracked tree

`git diff --name-status kalpavriksha-s1-c9.1 kalpavriksha-s1-c15.0`, over
the entire repository:

```
A  src/master_agent/kernel/__init__.py
A  src/master_agent/kernel/kernel.py
A  tests/kernel_test_support.py
A  tests/test_kernel_admission.py
A  tests/test_kernel_attempt.py
A  tests/test_kernel_authorization.py
A  tests/test_kernel_invalidate.py
A  tests/test_kernel_mint.py
A  tests/test_kernel_preconditions.py
A  tests/test_kernel_settle.py
A  tests/test_kernel_skeleton.py
```

**Eleven files, all `A`. No `M`, no `D`, anywhere in the repository.**

### 6.2 Blob SHA-1 proof

`git ls-tree -r` over `src/master_agent/foundation/` and
`src/master_agent/ledger/` at both tags, compared by blob hash:

> **16 files. Every blob SHA-1 identical.**

Byte-identity is therefore proven rather than inspected, for **C1 Clock ·
C2 Principal · C4 Warrant · C5 Receipt · C7 Attestation · C8 Refusal ·
C9.1 Execution Request · C10 Attempt Token · C11 Admission Record ·
C12 Reversibility Registry · C13 Receipt Ledger · C14 Override**.

### 6.3 The C9.1 amendment

`kalpavriksha-s1-c9.1` is the **parent commit** of this milestone, not a
change made by it. It shipped `reversibility_class` and `expected_effect`
on `ExecutionRequest` under ADR-0022 and ADR-0023 D2, and was verified
under Rule 001 in its own report. C15 **consumes it as shipped and
modifies nothing**: `execution_request.py` carries the same blob SHA-1 at
both tags.

Tags `c10.0` through `c14.0` are not re-cut and remain valid, per
ADR-0022 §6.2.

---

## 7 · Working directory versus the tag — the Rule 001 finding

`pytest tests/` in the project working directory reports **4,975 passed ·
49 failed · 1 skipped**. The same suite at this tag reports **2,896 passed
· 0 failed · 1 skipped**.

The difference is entirely accounted for, and it is the condition Rule 001
exists to expose:

| Working-directory failure | Category | Present at the tag? |
|---|---|---|
| `test_missions_console.py` — 27 | **untracked work** | No — the file exists at no tag |
| `test_memory_integration.py` — 16 | **untracked work** | No — the file exists at no tag |
| `test_missions_architecture.py` — 4 | **untracked work** | No — the file exists at no tag |
| `test_founder_approval_workflow.py` — 1 | **untracked work** — the file is tracked but locally modified | No — the committed version passes |
| `test_foundation_clock.py` — 1 | **untracked work** — the guard scans the filesystem and sees a locally modified `launcher/boot.py` reading ambient time | No — the committed `boot.py` passes |

**None is committed code. None was introduced by this change. None is a
test assumption.** The last row is the same ambient-time guard that C7 and
C8 both attributed to `boot.py`; the attribution is confirmed again here,
from the opposite direction — the guard passes at the tag, so the cause is
the working copy of `boot.py` and not the guard.

Per Rule 001, *"the working directory is never considered evidence."* No
number in §2 through §6 comes from it.

---

## 8 · What this milestone contains

| | |
|---|---|
| Public surface | `authorize` · `attempt` · `settle` · `invalidate` · `override` · `outstanding_count` |
| `execute()` | **Does not exist** — asserted by test |
| `raise NotImplementedError` in `kernel.py` | **0 occurrences**, measured at the tag |
| §14 R9 ceiling | **163 of 600 AST statements — 27% consumed** |
| Kernel state | five slots; no attestor, no bus, no subsystem |
| Dependencies | `master_agent.foundation.*` and `master_agent.ledger.*` only |

Three checks performed, eight attestations required, four operations, zero
subsystems owned.

---

## 9 · Open items carried past this tag

Recorded in `Engineering/HEALTH_C15_PART*.md` and **not solved here**, per
the founder's standing instruction:

**R34** · **R37** · **R38** · **R39** · **R40** · **R41** · **R43** ·
**R44** · **R45** · **R46** · **R47** · **R48**

Each is a founder decision about a frozen component rather than
engineering work. **R46 — invalidation cannot record itself — remains a
documented Foundation specification gap**, unchanged by this milestone and
explicitly out of its scope. None of the twelve is a Rule 001 gate and
none affects the verdict: every one is documented, fail-closed, and
covered by a test that asserts the gap so it cannot close unnoticed.

---

## 10 · Cleanup

Both verification worktrees were removed after the runs recorded above.
`git worktree list` shows only the project directory.

---

*Generated in clean, isolated checkouts of commit `c565244` and tag
`kalpavriksha-s1-c15.0`, per Quality Gate Rule 001. `PYTHONPATH` pinned to
each worktree's `src/` and source isolation asserted before either suite
ran. No implementation was modified, no component reopened, and no gate
lowered.*
