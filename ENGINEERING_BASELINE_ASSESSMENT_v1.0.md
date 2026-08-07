# Engineering Baseline Assessment v1.0

**Type:** Engineering stabilization assessment. No architecture designed, no component implemented, **nothing fixed.**
**Date:** 2026-08-05
**Milestone under assessment:** commit `2085ceb`, tag `kalpavriksha-s1-c1`
**Method:** every claim reproduced. The committed state was run in an isolated `git worktree` at the tag with `PYTHONPATH` pinned to that tree, so the numbers below describe the *commit*, not the working directory.

---

## 0 · Correction to my previous report

I previously stated that **all 48 failures share one root cause** (`FounderConsole.__init__()` unexpected keyword `memory`).

**That was wrong.** There are **three** distinct root causes, and one of them is a defect I introduced in Component 1. The corrected census is §2.

I also reported the full-suite result as the health of the repository. That conflated the *working directory* with the *commit*. They are very different, and the difference turns out to be the most important finding in this document.

---

## 1 · The headline finding

> **The committed repository is already green. Every one of the 48 failures lives in uncommitted work — except one, which is mine.**

Reproduced in an isolated worktree at tag `kalpavriksha-s1-c1`:

| | Committed tree (`2085ceb`) | Working directory |
|---|---|---|
| Tests collected | **1,575** | **3,703** |
| Passed | **1,574** | 3,655 |
| Failed | **1** | 48 |
| Skipped | 1 | 1 |

The single failure at the commit is `test_the_legacy_allowlist_only_shrinks` — **a test I wrote, failing on a defect I introduced.**

**Excluding my own defect, the committed repository passes 1,574 of 1,574 tests.**

### 1.1 The finding behind the finding

The working directory holds **2,128 more tests than the commit** — spread across **47 untracked test files** and **59 untracked source files**.

> **There is an entire unshipped release sitting in the working tree, and it is larger than the committed repository.**

Mission Briefs 032–039 — the Broker wiring, Ollama provider, token economy, timeout/deadline architecture, text verification, founder memory, the `missions/` package — are all present as working files and **none of it is committed.**

This reframes the mission. The question is not *"should we fix 48 tests?"* It is *"what is the relationship between the committed repository and the two-thirds of the project that has never been committed?"*

---

## 2 · Complete failure census

### 2.1 By root cause — all 48 accounted for

| Cause | Count | Error | Files |
|---|---|---|---|
| **A** | **43** | `TypeError: FounderConsole.__init__() got an unexpected keyword argument 'memory'` | `test_missions_console.py` (27), `test_memory_integration.py` (16) |
| **B** | **4** | `AssertionError: ['cli.py', 'cli.py', 'cli.py', 'planner/parsing.py']` and boundary assertions on `master_agent.planner.planner` | `test_missions_architecture.py` |
| **C** | **1** | `AssertionError: assert 'no planner is wired' in "unknown command 'aprove' - type help"` | `test_founder_approval_workflow.py` |
| | **48** | | |

Plus, at the commit only:

| Cause | Count | Error | File |
|---|---|---|---|
| **D** | **1** | `AssertionError: LEGACY_AMBIENT_TIME names modules that no longer exist: [15 files]` | `test_foundation_clock.py` |

### 2.2 By category, as requested

#### Category 1 — Issues in committed code: **ZERO**

Reproduced at tag `kalpavriksha-s1-c1` in an isolated worktree. Every test that exists in the commit passes, with the sole exception of my own (Category 3).

**There is no defect in committed source code.** None of causes A, B, or C is reachable from the commit, because the test files that produce them are untracked.

#### Category 2 — Issues in untracked work: **47 of 48**

**Cause A — 43 failures.** Untracked tests call `FounderConsole(memory=…, missions=…)`. `src/master_agent/launcher/console.py` is **tracked and unmodified** — byte-identical to HEAD — and its constructor accepts `dashboard, mission_control, founder, refresh_seconds, reader, writer, sleep`. No `memory`. No `missions`.

The tests were written against a console that has not been written yet.

**Cause B — 4 failures.** `test_missions_architecture.py` (untracked) asserts that mission-planning logic has moved out of `cli.py` and `planner/parsing.py` into the new `missions/` package, and that `missions/` does not import `master_agent.planner.planner`. Neither has happened. This is an architecture test **written for a target state, running against the current one.**

Evidence of tracking status:

| File | Git state |
|---|---|
| `src/master_agent/launcher/console.py` | tracked, **unmodified** |
| `tests/test_missions_console.py` | **untracked** |
| `tests/test_memory_integration.py` | **untracked** |
| `tests/test_missions_architecture.py` | **untracked** |
| `tests/missions_test_support.py` | **untracked** |
| `src/master_agent/missions/` | **untracked** |

#### Category 3 — Issues introduced during this session: **1, and it is mine**

`LEGACY_AMBIENT_TIME` in `tests/test_foundation_clock.py` contains **40 entries. 15 of them name files that are not tracked by git:**

```
ai_infrastructure/cache.py            broker/cost.py
ai_infrastructure/execution.py        broker/learning.py
ai_infrastructure/executive/actions.py  broker/recommendation.py
ai_infrastructure/executive/models.py   broker/registry.py
ai_infrastructure/executive/probes.py   memory/memory_models.py
broker/benchmark.py                   memory/memory_service.py
                                      missions/history.py
                                      plugins/filesystem_observation.py
                                      plugins/filesystem_worker.py
```

**Root cause:** I built the allowlist by scanning the working directory, which contains uncommitted work. The committed tree has no such files, so `test_the_legacy_allowlist_only_shrinks` correctly reports 15 phantom entries.

**Why this matters more than its size suggests:**

| Where | Result |
|---|---|
| Working directory | **28/28 pass** — the defect is invisible |
| Committed tag | **27/28 pass** — the defect is the only failure |

**The bug is invisible in exactly the place I verified it and visible in exactly the place that matters.** I reported Component 1 as green having only measured the working directory. That was an incomplete verification, and the test I wrote to guard against decay is the thing that caught it.

**The defect is in behaviour of a guard, not in the Clock.** `clock.py` is untouched by this and passes 27/28 everywhere. No production code is affected.

#### Category 4 — Issues caused by test assumptions: **1**

`tests/test_founder_approval_workflow.py` is the **only tracked file among the failures**, modified uncommitted by +6/−1:

```diff
-    assert "unknown command" in console.execute("aprove 1")
+    # MB037 changed what an unrecognised line means: it is now an
+    # objective, not an error. [...] With no Planner wired the console
+    # says so instead of crashing [...]
+    assert "no planner is wired" in console.execute("aprove 1")
```

This is distinct from Category 2 and the distinction matters: **a previously-green, committed test was edited to expect behaviour that does not exist.** It passes at HEAD. It fails only because of an uncommitted edit to its own expectation.

The edit is well-reasoned and honestly commented — it belongs to the MB037 console change. But its effect is that **the working directory can no longer tell the difference between "we broke something" and "we are ahead of ourselves."**

### 2.3 Answers to the specific questions asked

| Question | Answer |
|---|---|
| Root cause | Three, plus mine. §2.1. |
| When introduced | Causes A/B: whenever the untracked `missions/` work was written — **never committed**, so no commit introduced them. Cause C: an uncommitted edit to a tracked test. Cause D: this session, commit `2085ceb`. |
| Which milestone introduced it | **None.** Causes A–C are not in any commit. Cause D is in `2085ceb`. |
| Do the failures belong to unfinished work | **Yes — 47 of 48, unambiguously.** Untracked tests for untracked source, asserting a target state. |
| Is fixing them low- or high-risk | **High risk.** Cause A requires writing the console's `memory`/`missions` integration. Cause B requires completing the `cli.py` → `missions/` extraction. Both are feature work, and Cause B is an architecture boundary change — forbidden by this mission's constraints. **Cause D is low risk**: a test-fixture correction touching no production code. |

---

## 3 · Dependency Analysis

Do these failures block the remaining Sprint 1 components?

| Component | Cause A (console kwarg) | Cause B (missions boundary) | Cause C (console message) | Cause D (my allowlist) | Blocked? |
|---|---|---|---|---|---|
| **C2 Principal** | no | no | no | no | **No** |
| **C3 Reversibility Registry** | no | no | no | no | **No** |
| **C4 Receipt Ledger** | no | no | no | no | **No** |
| **C5 Override** | no | no | no | no | **No** |
| **C6 Constitutional Kernel** | no | no | no | no | **No** |
| **C8 Objective Engine** | no | **weak** | no | no | **No** — but see §3.2 |
| **C12 Dashboard state** | **weak** | no | no | no | **No** — different module |
| **C7 Execution path unification** | no | no | no | no | **No — but see §3.3** |
| **Any component's verification** | — | — | — | **yes** | **Yes — §3.1** |

### 3.1 The one thing genuinely blocked

**Nothing is blocked from being *built*. One thing is blocked from being *verified*.**

With 48 known-red tests in the working directory, the question *"did my change break anything?"* is no longer answerable by reading a pass/fail signal. It requires diffing failure lists between runs. That is a manual, error-prone comparison that gets less reliable as the noise floor persists — and it is precisely how a real regression hides inside expected noise.

**Cause D compounds this**, because it means my own verification method was wrong: I measured the working directory and called it green.

### 3.2 C8's weak coupling

Cause B asserts `missions/` must not import `master_agent.planner.planner`. The Objective Engine will sit adjacent to the Planner. If the `cli.py` → `missions/` extraction lands while C8 is being built, the two will contend for the same boundary. **Not a blocker; a sequencing note.**

### 3.3 C7 is the real collision risk

C7 (execution path unification) modifies `orchestrator/`, `executor/`, `runtime/`, and `ai_infrastructure/execution.py`. **Every one of those is also modified or created by the uncommitted MB032–039 work.** Building C7 against the committed tree and merging later is a guaranteed conflict on the most safety-critical code in the system.

This is not a reason to fix the 48. It is a reason to **commit the in-flight work before C7**, which is a different action entirely.

---

## 4 · Path Recommendation

The three offered options, assessed against evidence.

**Option A — Fix now. Rejected.** Fixing causes A and B means writing the console's `memory`/`missions` integration and completing the `cli.py` → `missions/` extraction. That is finishing MB032–039, not stabilization. It is explicitly forbidden by this mission's constraints ("do not modify architecture", "do not redesign components"), and it is a larger body of work than everything Sprint 1 has planned.

**Option C — Ignore until Sprint X. Rejected.** It leaves a defect I introduced sitting in a tagged milestone, and it accepts a permanently unreadable green/red signal. §3.1 shows the cost compounds silently.

**Option B — Quarantine. Selected**, with the precise meaning given in §5.

The evidence that makes B correct is that **the quarantine has already happened by accident**: the 47 failures come from untracked files, so any CI checking out `2085ceb` never sees them. **The commit is already green.** The failures exist only in one developer's working directory.

There is nothing to quarantine. There is something to *recognise* — and one thing of mine to fix.

---

## 5 · Green Baseline Plan

Smallest possible. No refactoring. No redesign.

### Step 1 — Fix Cause D (mine)

`LEGACY_AMBIENT_TIME` must describe **committed** code, because that is what the guard governs. Three candidate approaches, in ascending order of merit:

| Approach | Effect | Assessment |
|---|---|---|
| Delete the 15 untracked entries | Commit goes green | **Rejected.** When MB032–039 lands, 15 files will trip the ambient-time guard and block the commit. |
| Skip files that don't exist | Commit goes green | **Rejected.** Weakens "the list may only shrink" into "the list may contain anything". |
| **Derive the file set from `git ls-files`** | The guard governs exactly what is committed; untracked work is out of scope until it lands, then correctly in scope | **Recommended.** One helper, no weakened invariant. |

**Not implemented in this document, as instructed.** Requires approval before I touch it.

**Blast radius:** `tests/test_foundation_clock.py` only. No production code. `clock.py` unchanged.

### Step 2 — Change what "green" means

**Green is measured at the commit, in a clean checkout, not in the working directory.**

This is the actual lesson of Cause D. Adopt as a standing rule for every remaining component:

```
git worktree add <tmp> <tag>
cd <tmp> && PYTHONPATH=<tmp>/src python -m pytest tests/ -q
```

Cheap, exact, and it would have caught my defect before the tag was cut.

### Step 3 — Do not touch the 47

They are untracked, invisible to CI, and belong to their author's in-flight work. Touching them means either finishing that work or deleting someone's tests. Neither is stabilization.

### Step 4 — Record the situation

The in-flight work is larger than the committed repository. That fact should be written down somewhere durable (`PROJECT_BRAIN.md` or the ledger) so it is not rediscovered by the next person to run the suite.

**Total: one test-fixture change, one verification-procedure change, two documentation lines. No production code.**

---

## 6 · Risk Analysis

> *If we ignore these failures and continue implementing, what is the probability that later work becomes harder?*

Split by what "ignore" means, because the answer differs sharply.

### 6.1 Ignoring the 47 (untracked work) — **low risk: ~10–15%**

Components 2–6 (Principal, Reversibility Registry, Receipt Ledger, Override, Kernel) are **new packages** with no dependency on `console.py`, `missions/`, `cli.py`, or the Planner. They import `foundation/`, `persistence/`, and `plugins/base`. Nothing in causes A–C touches those.

Residual risk is confined to C8 (§3.2) and is a sequencing question, not a correctness one.

### 6.2 Ignoring Cause D (mine) — **high risk: ~80%**

Not because the bug is severe — it is three lines of test data — but because of what it proves: **my verification procedure produced a false green.** Left unchanged, the same procedure will produce false greens for Components 2 through 12.

That is the mechanism by which a defect ships inside a milestone that was reported as verified. It has already happened once, in the first component, on the most carefully reviewed change in the project.

### 6.3 Ignoring the *uncommitted state itself* — **high risk: ~70%, and it grows**

This is the risk the mission did not ask about and the one I would raise loudest.

Fifty-nine untracked source files and 2,128 untracked tests represent MB032–039. Every Sprint 1 component after C6 touches code that this work also touches — C7 most severely (§3.3). Two independent bodies of work modifying `orchestrator/`, `executor/`, `runtime/`, and `ai_infrastructure/execution.py`, one of them uncommitted and therefore invisible to git, is the setup for a merge that cannot be verified by either side's tests.

**Probability that C7 becomes materially harder if the in-flight work is still uncommitted when it starts: high.** The cost is not distributed evenly across the sprint — it is concentrated entirely in C7.

---

## 7 · Recommendation

**Continue Sprint 1. Fix my defect first. Commit the in-flight work before C7.**

One recommendation, three clauses, in order:

**1 · Fix Cause D before starting Component 2.** It is mine, it is small, it touches no production code, and leaving it means every subsequent milestone is verified by a procedure already proven to produce false greens. Approve the `git ls-files` approach in §5 Step 1 and it is a single change.

**2 · Adopt clean-checkout verification as the definition of green.** Working-directory results are not evidence about a commit. This is the standing lesson of Cause D and costs nothing per component.

**3 · Do not touch the 47. Do commit the work they belong to, before C7 begins.** They are unfinished edges of an unshipped release — not defects, not regressions, not in any commit. Fixing them means finishing MB032–039, which is out of scope. But *committing* MB032–039 is a separate, necessary decision, and §6.3 shows the window for making it cheaply closes when C7 starts.

### Why Sprint 1 continues rather than stops

The trigger for stopping would be evidence that committed code is unsound. **The evidence says the opposite: 1,574 of 1,574 committed tests pass.** The architecture is frozen, Component 1's production code is correct, and Components 2–6 are independent of every failing area.

Stopping to fix 47 tests belonging to someone else's unfinished feature would trade a real green baseline for the appearance of one, and would consume the sprint doing work no VEDA asked for.

**The repository can become a green baseline immediately** — it very nearly is one already — and the only thing standing between it and a genuine green tag is a three-line correction to a test fixture I wrote.

---

*Engineering assessment. Nothing implemented, nothing fixed, no architecture modified. Every number reproduced: committed state measured in an isolated `git worktree` at tag `kalpavriksha-s1-c1` with `PYTHONPATH` pinned to that tree; working-directory state measured in place. The temporary worktree has been removed and the repository is exactly as it was before this assessment began.*
