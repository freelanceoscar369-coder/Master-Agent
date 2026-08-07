# Ruff Debt Register

**Type:** Inventory only. **Nothing fixed, no source modified, no commit, no tag.**
**Date:** 2026-08-05
**Baseline:** tag `kalpavriksha-s1-c8.0` (commit `ac5e399`) and the working directory as of this date
**Tool:** `ruff 0.16.0`, invoked as `python -m ruff check src/ tests/`

---

## 0 · Method, and one finding about the method itself

Findings were measured twice: in a clean isolated worktree at `kalpavriksha-s1-c8.0`, and in the working directory. Every finding is classified by whether it exists in **committed history** or only in uncommitted work, because those are different kinds of debt with different owners.

### 0.1 The rule set is not pinned — record this before reading any count below

`pyproject.toml` declares:

```toml
dev = ["pytest>=8.2", "ruff>=0.5"]

[tool.ruff]
line-length = 100
target-version = "py311"
```

**There is no `select`.** The enforced rule set is therefore whatever the *installed* Ruff version defaults to. Under `ruff 0.16.0` that resolves to a wide set including `I`, `UP`, `SIM`, `S`, `BLE`, `PLW`, `PLR`, `RUF`, `C4`, `B`, `YTT`, `ASYNC` — far more than the `E4/E7/E9/F` a reader of this file would assume.

**Consequence:** a Ruff upgrade can change the gate with no code change. Findings can appear or vanish between two runs of the same commit on two machines. Every count in this register is therefore true *for ruff 0.16.0* and is not reproducible across versions.

**This is the most important entry in this document**, because it is the only one that affects whether any other entry can be trusted. Recorded as **RUFF-GOV-01** in §8. Not fixed here — pinning the rule set is a change, and this brief is an inventory.

### 0.2 Severity taxonomy

| Severity | Meaning in this project |
|---|---|
| **Cosmetic** | Style or modernisation. No behavioural difference under any input |
| **Maintainability** | Dead or duplicated code. Misleads a reader; cannot itself misbehave |
| **Potential Bug** | Can produce wrong behaviour under some reachable condition, including introspection and tooling |
| **Safety Critical** | Can cause a failure to be swallowed, or an action to appear to succeed when it did not. In a system whose first guarantee is *fail closed*, these are constitutional, not stylistic |

### 0.3 Counts

| Tier | Where | Findings |
|---|---|---|
| **A** | Committed history, present at tag `c8.0` | **21** |
| **B** | Uncommitted modifications to tracked files | **36** |
| **C** | Untracked files (MB032–039) | **107** |
| | **Working directory total** | **150** |
| | **Distinct debt across both states** | **164** |

Working directory total (150) is less than A+B+C (164) because a Tier A finding in a file that has since been modified reappears in the working directory at a *shifted line number* and is counted once in each state. Exactly one such shift exists: `permissions/permission_system.py` `SIM103` at line 85 (tag) and line 86 (working directory) — the same finding, not two.

**Findings introduced by Sprint 1 Components C1–C8: zero.** Every Tier A finding was blamed to its introducing commit; all 21 predate Sprint 1 (§1.2).

---

## 1 · Tier A — the 21 findings in committed history

These are the only findings a clean checkout sees, and therefore the only ones Rule 001 could plausibly gate on.

| # | Rule | File | Line | Exact Ruff message | Severity | Tracked | Introduced by | Blocks Demo? | Blocks Rule 001? | Cleanup milestone |
|---|---|---|---|---|---|---|---|---|---|---|
| A01 | `UP035` | `src/master_agent/cli.py` | 50 | Import from `collections.abc` instead: `Callable` | Cosmetic | Tracked | `307c8b8` Miracle 003.1 (2026-07-23) | No | No | Post-demo |
| A02 | `UP017` | `src/master_agent/cli.py` | 607 | Use `datetime.UTC` alias | Cosmetic | Tracked | `965628b` Miracle 004 (2026-07-23) | No | No | Post-demo |
| A03 | `UP017` | `src/master_agent/executor/executor.py` | 81 | Use `datetime.UTC` alias | Cosmetic | Tracked | `f07ca41` Miracle 002 (2026-07-23) | No | No | **C16** |
| A04 | `UP017` | `src/master_agent/executor/executor.py` | 129 | Use `datetime.UTC` alias | Cosmetic | Tracked | `f07ca41` Miracle 002 (2026-07-23) | No | No | **C16** |
| A05 | `UP017` | `src/master_agent/memory/conversation.py` | 18 | Use `datetime.UTC` alias | Cosmetic | Tracked | `965628b` Miracle 004 (2026-07-23) | No | No | Post-demo |
| A06 | `F401` | `src/master_agent/mission_control/mission_control.py` | 20 | `master_agent.mission_control.approvals.ApprovalState` imported but unused | Maintainability | Tracked | `6e12bd8` Miracle 028.1 (2026-07-29) | No | No | Post-demo |
| A07 | `UP017` | `src/master_agent/mission_manager/mission.py` | 48 | Use `datetime.UTC` alias | Cosmetic | Tracked | `ee815fe` Miracle 001 (2026-07-23) | No | No | Post-demo |
| A08 | `UP017` | `src/master_agent/mission_manager/mission.py` | 49 | Use `datetime.UTC` alias | Cosmetic | Tracked | `ee815fe` Miracle 001 (2026-07-23) | No | No | Post-demo |
| A09 | `UP017` | `src/master_agent/mission_manager/mission.py` | 56 | Use `datetime.UTC` alias | Cosmetic | Tracked | `ee815fe` Miracle 001 (2026-07-23) | No | No | Post-demo |
| A10 | `I001` | `src/master_agent/permissions/permission_system.py` | 7 | Import block is un-sorted or un-formatted | Cosmetic | Tracked | `ee815fe` Miracle 001 (2026-07-23) | No | No | Post-demo |
| A11 | `SIM103` | `src/master_agent/permissions/permission_system.py` | 85 | Return the negated condition directly | Cosmetic | Tracked | `905845b` Miracle 005 (2026-07-23) | No | No | Post-demo |
| A12 | `I001` | `src/master_agent/plugins/filesystem_plugin.py` | 42 | Import block is un-sorted or un-formatted | Cosmetic | Tracked | `ee815fe` Miracle 001 (2026-07-23) | No | No | Post-demo |
| A13 | `I001` | `tests/test_cli_session.py` | 18 | Import block is un-sorted or un-formatted | Cosmetic | Tracked | `ee815fe` Miracle 001 (2026-07-23) | No | No | Post-demo |
| A14 | `RUF059` | `tests/test_filesystem_plugin.py` | 200 | Unpacked variable `executor` is never used | Maintainability | Tracked | `746a26d` Miracle 003 (2026-07-23) | No | No | Post-demo |
| A15 | `UP017` | `tests/test_memory.py` | 22 | Use `datetime.UTC` alias | Cosmetic | Tracked | `965628b` Miracle 004 (2026-07-23) | No | No | Post-demo |
| A16 | `C408` | `tests/test_memory.py` | 23 | Unnecessary `dict()` call (rewrite as a literal) | Cosmetic | Tracked | `965628b` Miracle 004 (2026-07-23) | No | No | Post-demo |
| A17 | `UP017` | `tests/test_memory.py` | 85 | Use `datetime.UTC` alias | Cosmetic | Tracked | `965628b` Miracle 004 (2026-07-23) | No | No | Post-demo |
| A18 | `UP017` | `tests/test_memory.py` | 128 | Use `datetime.UTC` alias | Cosmetic | Tracked | `1eff1f3` Miracle 004.1 (2026-07-23) | No | No | Post-demo |
| A19 | `UP017` | `tests/test_memory.py` | 195 | Use `datetime.UTC` alias | Cosmetic | Tracked | `965628b` Miracle 004 (2026-07-23) | No | No | Post-demo |
| A20 | `I001` | `tests/test_permission_system.py` | 10 | Import block is un-sorted or un-formatted | Cosmetic | Tracked | `905845b` Miracle 005 (2026-07-23) | No | No | Post-demo |
| A21 | `I001` | `tests/test_workspace_bootstrap_action.py` | 12 | Import block is un-sorted or un-formatted | Cosmetic | Tracked | `746a26d` Miracle 003 (2026-07-23) | No | No | Post-demo |

### 1.1 Tier A by rule and severity

| Rule | Count | Severity |
|---|---|---|
| `UP017` Use `datetime.UTC` alias | 11 | Cosmetic |
| `I001` Import block un-sorted | 5 | Cosmetic |
| `UP035` Import from `collections.abc` | 1 | Cosmetic |
| `SIM103` Return negated condition | 1 | Cosmetic |
| `C408` Unnecessary `dict()` | 1 | Cosmetic |
| `F401` Unused import | 1 | Maintainability |
| `RUF059` Unused unpacked variable | 1 | Maintainability |

**19 Cosmetic · 2 Maintainability · 0 Potential Bug · 0 Safety Critical.**

**Nothing in committed history is worse than Maintainability.**

### 1.2 Provenance — none of this is Sprint 1's

Every Tier A line was blamed with `git log -L`. All 21 trace to Miracles 001 through 028.1, dated 2026-07-23 to 2026-07-29 — **before Sprint 1 began**.

| Introducing work | Findings |
|---|---|
| Miracle 001 — First end-to-end mission | 6 |
| Miracle 004 / 004.1 — The Memory System | 6 |
| Miracle 002 — Generic Local Executor | 2 |
| Miracle 003 / 003.1 — Workspace Bootstrap | 3 |
| Miracle 005 — Local Executor Expansion | 2 |
| Miracle 028.1 — Founder Approval Workflow | 1 |
| **Sprint 1 (C1–C8)** | **0** |

`UP017` alone is 11 of 21, and it is a single mechanical pattern — `timezone.utc` written before `datetime.UTC` was adopted as the house style in C1.

---

## 2 · Tier B — 36 findings in uncommitted modifications to tracked files

Not in history. They enter history the moment the MB032–039 work is committed (**R3**).

| File | Findings | Rules | Worst severity |
|---|---|---|---|
| `src/master_agent/broker/broker.py` | **24** | `F821`×18, `F401`×3, `I001`×2, `RUF059`×1 | **Potential Bug** |
| `src/master_agent/launcher/boot.py` | 4 | `I001`×2, `F401`×2 | Maintainability |
| `src/master_agent/plugins/filesystem_plugin.py` | 3 | `F401`×3 | Maintainability |
| `src/master_agent/broker/__init__.py` | 2 | `I001`, `RUF022` | Cosmetic |
| `tests/runtime_test_support.py` | 2 | `I001`, `RUF015` | Cosmetic |
| `src/master_agent/permissions/permission_system.py` | 1 | `SIM103` (line 86) | Cosmetic — **this is A11 shifted, not a new finding** |

### 2.1 B-CRITICAL · `broker/broker.py` — 18 × `F821` undefined name

| Rule | File | Lines | Exact message |
|---|---|---|---|
| `F821` | `src/master_agent/broker/broker.py` | 92, 130, 133 (×2), 149, 151, 203, 254, 255, 312 | Undefined name `SelectionPolicy` |
| `F821` | `src/master_agent/broker/broker.py` | 150 (×2), 157, 205, 253, 313, 375 | Undefined name `ProviderProfile` |
| `F821` | `src/master_agent/broker/broker.py` | 149, 202, 254 | Undefined name `TaskProfile` |

**Severity: Potential Bug. Verified, not assumed.**

`broker.py` carries `from __future__ import annotations`, so these annotations are never evaluated at import and the module **imports cleanly today** — confirmed by direct execution. The names are genuinely never imported; they appear only inside annotations.

**What still breaks:** anything that resolves those annotations at runtime — `typing.get_type_hints()`, a dataclass or Pydantic model built from them, or any introspection-based tooling — raises `NameError`. Static type checking and IDE navigation are already broken on this module.

**Why it is not Safety Critical:** it cannot currently cause a wrong action, only a wrong or absent type answer.

Alongside these, the same file reports `F401` for `VerificationLearningLoop`, `OutcomeReport` and `CostModel` — imported but unused. **The shape is a refactor that moved imports out and left the annotations behind.** Worth a look by whoever owns MB032–039, before it is committed.

---

## 3 · Tier C — 107 findings in untracked files

MB032–039 work, invisible to git. **This tier contains the only Safety Critical findings in the repository.**

| File | Findings | Rules |
|---|---|---|
| `src/master_agent/ai_infrastructure/executive/actions.py` | 19 | `F401`×6, `BLE001`×4, `PLW1510`×4, `S110`×2, `I001` |
| `tests/test_ai_infrastructure_executive.py` | 17 | `F401`×3, `F811`×7, `PLR0402`×6, `I001` |
| `src/master_agent/ai_infrastructure/executive/probes.py` | 15 | `PLW1510`×6, `BLE001`×5, `F401`×2, `F841`×2 (`tps_sum`, `cost_sum`), `I001` |
| `src/master_agent/missions/service.py` | 10 | `F401`×9, `I001` |
| `src/master_agent/broker/recommendation.py` | 5 | `BLE001`, `S110`, `F401`, `I001`, `SIM102` |
| `src/master_agent/broker/benchmark.py` | 4 | `BLE001`, `S110`, `F401`×2 |
| `src/master_agent/plugins/filesystem_gateway.py` | 4 | `F401`×2, `I001`, `RUF015` |
| `src/master_agent/broker/cost.py` | 3 | `BLE001`, `S110`, `F401` |
| `src/master_agent/broker/learning.py` | 3 | `BLE001`, `S110`, `F401` |
| `src/master_agent/broker/registry.py` | 3 | `BLE001`, `S110`, **`RUF009`** |
| `tests/test_provider_registry.py` | 3 | `F401`×2, `I001` |
| `src/master_agent/ai_infrastructure/__init__.py` | 2 | `I001`, `RUF022` |
| `src/master_agent/ai_infrastructure/executive/__init__.py` | 2 | `I001`, `RUF022` |
| `src/master_agent/brain/__init__.py` | 2 | `I001`, `RUF022` |
| `src/master_agent/brain/intent.py` | 2 | `F401`×2 |
| `src/master_agent/plugins/filesystem_worker.py` | 2 | `RUF015`×2 |
| `tests/test_benchmark_store.py` | 2 | `F401`, `I001` |
| `tests/test_filesystem_verification.py` | 2 | `F401`×2 |
| `src/master_agent/brain/reporter.py` · `plugins/filesystem_observation.py` · `tests/missions_test_support.py` · `tests/test_missions_edges.py` · `tests/test_missions_integration.py` · `tests/test_missions_lifecycle.py` · `tests/test_verification_regression.py` | 1 each | `I001` |

### 3.1 The Safety Critical findings — 21 across three rules

| Rule | Count | Files | Why it is safety critical here |
|---|---|---|---|
| **`BLE001`** blind `except Exception` | 14 | `executive/actions.py`×4, `executive/probes.py`×5, `broker/{benchmark,cost,learning,recommendation,registry}.py`×1 each | A blind catch can swallow the very failure a fail-closed check depends on. Kernel Spec §11 requires eight of nine failure conditions to **fail closed**; an exception absorbed before it reaches a check turns fail-closed into proceed-silently |
| **`S110`** `try`/`except`/`pass` | 7 | `executive/actions.py`×2, `broker/{benchmark,cost,learning,recommendation,registry}.py`×1 each | Strictly worse than `BLE001`: the failure is caught **and discarded with no record**. §7.5 requires refusals to be recorded, and *"a silently refused action is indistinguishable from one never attempted"* |
| **`PLW1510`** `subprocess.run` without `check` | 10 | `executive/actions.py`×4, `executive/probes.py`×6 | A failed subprocess returns a non-zero code that is never inspected, so **an action that failed reads as an action that succeeded**. That is a false Receipt, which is the one thing the ledger exists to make impossible |

**All 21 are in untracked files.** None is in committed history and none is in `foundation/`. They are properties of the MB032–039 work, and they become repository debt at the moment R3 is committed.

### 3.2 One constitutional finding worth naming separately

| Rule | File | Line | Message |
|---|---|---|---|
| **`RUF009`** | `src/master_agent/broker/registry.py` | 99 | Do not perform function call `datetime.now` in dataclass defaults |

This is an **ambient-time read**, the same class of violation as **R7** (`launcher/boot.py`). It is caught by Ruff but **not** by `test_only_the_clock_module_reads_the_machines_wall_clock`, because that guard inspects a fixed module list and `registry.py` is untracked.

**Two guards disagree about the same rule, and the constitutional one is the weaker of the two.** Recorded as **RUFF-GOV-02** in §8.

---

## 4 · Blocks Demo?

**No finding in any tier blocks the 12 Aug Founder Demo. Zero exceptions.**

| Tier | Blocks demo | Reason |
|---|---|---|
| A | **No** (21/21) | 19 Cosmetic, 2 Maintainability. None alters behaviour |
| B | **No** (36/36) | `F821` is latent under postponed annotation evaluation; the module imports and runs |
| C | **No** (107/107) | Untracked. The demo path runs through `foundation/` and the Kernel, not through MB032–039 |

**Caveat, stated because it is the honest one:** if the demo path is later routed through MB032–039 code — which **C16 Execution Path Unification will do** — the 21 Safety Critical findings in §3.1 move onto the demo path with it. They do not block the demo today; they would block a *trustworthy* demo the day C16 lands. See DEMO_RISK_REGISTER.md.

---

## 5 · Blocks Rule 001?

**No finding in any tier blocks Rule 001, as Rule 001 is currently written.**

Rule 001's five criteria are clean checkout, commit verified, tag verified, tests executed against the tag, architecture guards executed against the tag, verification report generated. **Ruff is not among them.**

| Tier | Blocks Rule 001 | Reason |
|---|---|---|
| A | **No** | Rule 001 does not gate on Ruff |
| B | **No** | Not in any checkout |
| C | **No** | Not in any checkout |

**This is a gap, not a clearance.** Every Sprint 1 verification report has reported Ruff voluntarily, and C8's went further and compared the repo-wide count against `c7.0` to prove it had introduced nothing. That practice is stronger than the rule requires and is currently unwritten. See `RULE001_CLARIFICATION.md`.

---

## 6 · Recommended cleanup milestones

Sequenced against the roadmap, not against tidiness. **Every entry is a recommendation; none is scheduled and nothing is fixed here.**

| Milestone | Scope | Rationale |
|---|---|---|
| **Before R3 is committed** | Tier B's 18 `F821` in `broker/broker.py` | These enter history the moment MB032–039 is committed. A missing import is cheaper to fix before it is a commit than after |
| **Before R3 is committed** | Tier C's 21 Safety Critical (§3.1) | Same reason, higher stakes. Committing 7 silent `except: pass` and 10 unchecked `subprocess.run` into a system whose first guarantee is *fail closed* is the single largest trust regression available to this project |
| **Before R3 is committed** | `RUF009` in `broker/registry.py` (§3.2) | R7's requirement, applied consistently: take an injected `Clock` or join `LEGACY_AMBIENT_TIME` |
| **C16 Execution Path Unification** | A03, A04 (`executor/executor.py`) | C16 already modifies this file. Fixing two `UP017` in a file being edited is not opportunistic; touching it for that reason alone would be |
| **Post-demo, one pass** | All remaining Tier A (19 findings) | 18 of 19 are `--fix`-safe. One mechanical commit, no behavioural review needed. **After 12 Aug** — it buys nothing before it and touches ten files the demo depends on |
| **Post-demo** | Tier C non-critical (86 findings) | Mostly `I001` and `F401`. Bulk-fixable once MB032–039 is committed and has an owner |

### 6.1 What must not happen

**Do not run `ruff check --fix` across the repository.** 18 of the 21 Tier A findings are auto-fixable and all 18 are safe, but the same command would rewrite 82 findings in the working directory, including files with no owner and no test coverage at the tag.

The C5 verification report already records the discipline that applies here: Ruff proposed rewriting `Decimal("…")` calls and each site was **checked individually** before acceptance, *"precisely how the defect this decision guards against would have been introduced"* had it been applied blindly.

---

## 7 · Governance findings

| # | Finding | Severity | Recommendation |
|---|---|---|---|
| **RUFF-GOV-01** | **The Ruff rule set is unpinned.** `ruff>=0.5` with no `select` means the gate is defined by whichever version is installed. Two engineers on two machines can get different results from the same commit | **High** | Pin both: an exact Ruff version and an explicit `[tool.ruff.lint] select`. Choose the set that reproduces today's 21 Tier A findings, so pinning changes nothing on the day it lands. **Not a code change to production source** — it is a config decision, and it needs founder sign-off because it defines a gate |
| **RUFF-GOV-02** | **Two guards disagree on ambient time.** `RUF009` catches `datetime.now` in `broker/registry.py`; the constitutional guard `test_only_the_clock_module_reads_the_machines_wall_clock` does not, because it inspects a fixed module list | Medium | Widen the constitutional guard to walk `src/` rather than a list, at whichever milestone next touches it. The constitutional guard should be the stricter of the two, and today it is the weaker |
| **RUFF-GOV-03** | **Ruff is reported by every Sprint 1 verification report but is not a Rule 001 criterion.** Practice exceeds the written rule | Medium | Resolve in `RULE001_CLARIFICATION.md` |

---

## 8 · What was not done

No source file was modified. No `--fix` was run. No commit, no tag. No Ruff configuration was changed — including RUFF-GOV-01, which is a recommendation and not an action taken.

**This document is an inventory. Every count in it is measured, and every provenance claim was produced by `git log -L` against the introducing line.**

---

*Inventory produced at tag `kalpavriksha-s1-c8.0` and in the working directory on 2026-08-05, with `ruff 0.16.0`. All temporary worktrees removed.*
