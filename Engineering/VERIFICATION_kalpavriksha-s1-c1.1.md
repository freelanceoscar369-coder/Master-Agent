# Verification Report — `kalpavriksha-s1-c1.1`

**Gate applied:** Quality Gate Rule 001
**Verdict:** **GREEN**
**Date:** 2026-08-05

---

## 1 · Subject

| | |
|---|---|
| Tag | `kalpavriksha-s1-c1.1` (annotated) |
| Commit | `9224da6` |
| Milestone | Sprint 1, Component 1.1 — Canonical Clock, corrected |
| Supersedes | Nothing. `kalpavriksha-s1-c1` → `2085ceb` is unchanged and remains in history exactly as tagged. |

---

## 2 · Rule 001 criteria

| Criterion | Method | Result |
|---|---|---|
| Clean checkout | `git worktree add` into a temp path, isolated from the project directory | ✅ |
| Tag checkout | Worktree created at `kalpavriksha-s1-c1.1` | ✅ |
| Tests executed there | `PYTHONPATH=<worktree>/src python -m pytest tests/ -q`, source isolation confirmed by printing `master_agent.__file__` before the run | ✅ |
| Architecture guards executed there | 6 guard modules run explicitly and named in §4 | ✅ |
| Verification report generated | This document | ✅ |

**Working directory results are excluded from this report**, per Rule 001. §5 records them separately as information, not as evidence.

---

## 3 · Test results — clean checkout at the tag

```
1575 passed, 1 skipped in 126.36s
```

| | |
|---|---|
| Passed | **1,575** |
| Failed | **0** |
| Skipped | 1 |

Run twice: once at commit `9224da6` **before** the tag was created (1575 passed / 0 failed), and once at the tag itself after creation. Identical. The tag was not created until the commit was proven green — Rule 001's order of operations.

---

## 4 · Architecture guards

Run as a named set, separately from the full suite, because Rule 001 treats them as a distinct criterion — and because in the incident that produced Rule 001, every unit test passed and only a guard failed.

| Guard module | Result |
|---|---|
| `test_foundation_clock.py` | ✅ |
| `test_mission_control_architecture.py` | ✅ |
| `test_dashboard_architecture.py` | ✅ |
| `test_browser_constitution_compliance.py` | ✅ |
| `test_persistence_architecture.py` | ✅ |
| `test_runtime_architecture.py` | ✅ |
| **Total** | **224 passed, 1 skipped** |

The three guards corrected by this milestone, verified individually:

| Guard | Result |
|---|---|
| `test_only_the_clock_module_reads_the_machines_wall_clock` | **PASSED** |
| `test_the_legacy_allowlist_only_shrinks` | **PASSED** — this is the guard that failed at `kalpavriksha-s1-c1` |
| `test_the_clock_module_reads_the_wall_clock_exactly_once` | **PASSED** |

---

## 5 · Failures, by category

Rule 001 requires every failure to be categorised. At the tag there are none. The categories are reported anyway, because two of them are non-empty in the working directory and both are findings worth carrying forward.

| Category | At the tag | Note |
|---|---|---|
| **Committed code** | **0** | 1,575 of 1,575 pass |
| **Untracked work** | **0 at the tag** | 47 failures exist in the working directory from uncommitted MB032–039 work. Invisible to any checkout. Assessed in `ENGINEERING_BASELINE_ASSESSMENT_v1.0.md`. |
| **Introduced by this change** | **0** | The change is confined to `tests/test_foundation_clock.py`. No production code touched; `clock.py` unchanged. |
| **Test assumption** | **0 at the tag** | 1 in the working directory: an uncommitted edit to `test_founder_approval_workflow.py` expecting an MB037 console message that does not exist. |

### 5.1 The guard's first true positive

In the **working directory** the corrected guard reports one failure:

```
launcher/boot.py
  693: datetime.now()
  721: datetime.now()
```

This is not a defect in this milestone. `launcher/boot.py` is tracked and its **committed** version contains no ambient-time read; the two calls exist only in an uncommitted modification. The guard is correctly refusing to let new ambient time enter the codebase.

**Required before that change is committed:** either take an injected `Clock`, or add `launcher/boot.py` to `LEGACY_AMBIENT_TIME` with the sprint that will remove it.

This is the guard doing on its first day exactly what it was built to do, and it is only visible because the scope is now derived from git.

---

## 6 · What changed, and why

**Defect.** The guard's file set came from `PACKAGE_DIR.rglob("*.py")` — a filesystem scan. The working directory contains ~59 uncommitted source files, so the generated `LEGACY_AMBIENT_TIME` listed 15 modules git has never tracked. The list described a state no checkout could reproduce: **28/28 in the working directory, 27/28 at its own tag.**

**Correction.**

| Change | Effect |
|---|---|
| `_source_files()` derives from `git ls-files` | The guard governs committed and staged code — exactly what a checkout can reproduce |
| `test_the_legacy_allowlist_only_shrinks` shares that same set | One definition of scope. Two definitions is how a guard and its allowlist drift apart. |
| `LEGACY_AMBIENT_TIME` reduced 40 → **24** | The 15 untracked entries removed; `launcher/boot.py` removed because its committed version is clean |
| `Engineering/QUALITY_GATE_RULES.md` added | Rules 000 and 001 recorded permanently |

**Blast radius:** one test module and one new document. `src/master_agent/foundation/clock.py` is byte-identical to `kalpavriksha-s1-c1`. No production behaviour changed.

---

## 7 · Rule 000 assessment

> *Every engineering change must leave the repository more trustworthy than it was before the change.*

**Passes.** Before: a guard that reported green in the one place its own subject could not be reproduced. After: a guard whose scope is defined by git, which caught a real ambient-time introduction within minutes of being corrected, and a written gate that makes the failure mode impossible to repeat silently.

The repository has one fewer way to lie about its own health.

---

*Generated in a clean checkout of `kalpavriksha-s1-c1.1`, per Quality Gate Rule 001. All temporary worktrees removed; the project directory is unchanged apart from this report.*
