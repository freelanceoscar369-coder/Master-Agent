# Rule 001 — Clarification Proposal

**Type:** Governance review and recommendation. **The existing rule is NOT modified.** No code, no commits, no tags.
**Date:** 2026-08-05
**Scope reviewed:** every completed milestone, C1 through C8
**Question asked:** does Rule 001 currently certify **component cleanliness** or **repository cleanliness**?

---

## 0 · Answer, in one line

**Rule 001 today certifies repository cleanliness *of tests*, component cleanliness of nothing, and it is silent on Ruff, on which guard modules count, and on what a "clean checkout" excludes.**

The gap has not yet caused a wrong GREEN. It has already caused **two inconsistent claims across the eight reports**, both documented in §2, and one of them is in the C8 report I produced this session.

---

## 1 · What Rule 001 says, verbatim

> A milestone is GREEN only if ALL are true:
>
> - Clean checkout
> - Commit verified
> - Tag verified
> - Tests executed against the tag
> - Architecture guards executed against the tag
> - Verification report generated
>
> Working directory success is NOT evidence.

Six criteria. **The last line is the load-bearing one**, and it is the one every report has honoured without exception.

---

## 2 · What the eight milestones actually certified

Reviewed: `VERIFICATION_kalpavriksha-s1-c1.1.md`, `-c2.0`, `-c3.0`, `-c4.0`, `-c5.0`, `-c7.0`, `-c8.0`. (C2 and C3 share tag `c2.0`; C6 shipped under `c5.0`.)

| Criterion | C1.1 | C2.0 | C3.0 | C4.0 | C5.0 | C7.0 | C8.0 | Consistent? |
|---|---|---|---|---|---|---|---|---|
| Clean checkout in a worktree | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | **Yes** |
| Working directory excluded from evidence | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | **Yes** |
| Full test suite at the tag | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | **Yes** |
| Test-count reconciliation to the prior tag | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | **Yes** |
| Prior components byte-identical | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | **Yes** |
| **Commit verified *before the tag existed*** | ? | ? | ? | ? | ? | ✅ | ✅ | **No** — only C7/C8 state the ordering |
| **PYTHONPATH pinned / isolation asserted** | ? | ? | ? | ? | ? | ✅ | ✅ | **No** — first stated at C7 |
| **Guard modules — which set?** | 6 | 8 | 9 | 10 | 11 | 12 | 6 | **No** — see §2.1 |
| **Ruff** | — | — | — | — | noted | — | ✅ | **No** — reported ad hoc, never required |

**Five criteria are honoured identically across all eight. Four are not, and all four are things Rule 001 does not mention.**

### 2.1 The guard-module count — measured, and a correction to my own C8 report

The reports cite 6, 8, 9, 10, 11, 12, then 6. That looked like drift. It is not, and my C8 report's explanation of it was **wrong**.

**Measured fact.** The set of architecture-guard modules present in committed history is **exactly six at every tag from `c1.1` to `c8.0`**:

```
test_browser_constitution_compliance.py   test_persistence_architecture.py
test_dashboard_architecture.py            test_runtime_approval_boundary.py
test_mission_control_architecture.py      test_runtime_architecture.py
```

The counts in reports C2.0–C7.0 fit `6 + (prior foundation modules)` exactly — 6+2=8 at C2.0, 6+3=9 at C3.0, 6+4=10, 6+5=11, 6+6=12 at C7.0 — with the component's *own* constitutional guards named separately in each report's §4.1. **That is a coherent and defensible definition**: "guard modules" meant architecture guards plus every prior component's constitutional suite.

C8's report used the narrower definition — architecture guards only — reported 6, and then asserted the earlier figure was inflated by uncommitted files.

> **Correction.** `VERIFICATION_kalpavriksha-s1-c8.0.md` §4 states: *"The C7 report cited 12 guard modules run against the working directory. Six of those… are files of the uncommitted MB032–039 work and do not exist at any green tag."* **That explanation is incorrect.** The 12 is `6 architecture + 6 prior foundation` modules, all of which do exist at `c7.0`. It was a different definition, not a contaminated one.
>
> One sub-claim survives: `test_missions_architecture.py` and `test_planner_architecture.py` are indeed untracked and exist at no tag — but they were not part of C7's twelve.
>
> **Also unresolved:** the C7 report's `507 passed` figure is not reproducible at `c7.0`. Measured there: 6 architecture modules = **215 passed, 1 skipped**; 6 architecture + 6 foundation = **460 passed, 1 skipped**; adding C7's own suite gives 526. None is 507. **Cause undetermined, and not guessed at here.** The C8 figures (215 / 22) were measured twice and reconcile exactly.

**This is precisely the failure mode a clarification prevents.** Two engineers applied two reasonable readings of "architecture guards," got different numbers, and the second one mis-diagnosed the first. Neither milestone is invalid — the underlying runs were real and passed — but the reports are not comparable, and one now contains a wrong sentence.

---

## 3 · The three ambiguities, stated precisely

### 3.1 Component cleanliness vs repository cleanliness

Rule 001 says *"Tests executed against the tag"* without saying **which** tests. Every report has run the **full suite**, which is repository-level. No report has ever certified the component in isolation.

**In practice this has been the stronger choice**, and it caught something real: C7 and C8 both confirmed that the ambient-time guard's failure came from `launcher/boot.py` and **not** from the component under construction. A component-only run could not have distinguished those.

But the rule does not say so, and "component cleanliness" is the reading a new engineer would more naturally take from the phrase *"a milestone is GREEN."*

### 3.2 Ruff has no status

Ruff is not a Rule 001 criterion. Every Sprint 1 report has nonetheless reported it, and C8's compared the repo-wide count against `c7.0` to prove the component introduced nothing.

That practice is **stronger than the rule**, applied **inconsistently across milestones**, and **unwritten**. Any of those three alone is tolerable; together they mean a future milestone could skip Ruff entirely and still be GREEN by the letter.

Recorded as **RUFF-GOV-03** in `RUFF_DEBT_REGISTER.md`.

### 3.3 "Clean checkout" does not say what it excludes

Every report has used `git worktree` outside the project directory, and C7/C8 additionally asserted **source isolation** — a probe that raises if `master_agent` resolves anywhere but the worktree. C1–C5 did not state that assertion.

Without it, a clean checkout that silently imports an installed distribution or the project directory's `src/` would pass Rule 001 while testing the wrong code. **No evidence suggests this happened.** The point is that the rule does not currently forbid it.

---

## 4 · Recommendation — one explicit interpretation

> ### **Rule 001 certifies REPOSITORY cleanliness at the tag, plus COMPONENT attribution.**

Both halves, stated as one rule:

**Repository cleanliness** — the whole test suite passes in a clean, isolated checkout of the tag. Not the component's tests; all of them. A component that passes its own suite while breaking another's has not earned a milestone.

**Component attribution** — the report must show what the component itself changed: test-count reconciliation against the prior tag, byte-identity of prior components, and the component's own constitutional guards named individually.

**Why this interpretation and not component-only:** it is what all eight milestones already did. Adopting it ratifies existing practice and invalidates nothing. Component-only would be a weakening, and it would have hidden the `boot.py` finding that C7 and C8 both surfaced.

### 4.1 Proposed clarified wording

Offered for founder ratification. **Not applied. The existing rule stands unchanged until it is.**

> **Rule 001 (clarified).** A milestone is GREEN only if ALL are true:
>
> 1. **Clean checkout** — a `git worktree` outside the project directory, with `git status` empty.
> 2. **Source isolation confirmed** — imports are asserted to resolve inside the worktree. A run that could import the project directory or an installed distribution is void.
> 3. **Commit verified before the tag exists** — the full suite passes at the commit, and only then is the tag created.
> 4. **Tag verified afterwards** — the same evidence is reproduced in a second, independent worktree at the tag.
> 5. **Full test suite executed against the tag**, with **zero failures**, reconciled by count against the previous milestone.
> 6. **Architecture guards executed against the tag** — meaning the six modules committed at that tag, named individually in the report. The component's own constitutional guards are additionally named and counted separately.
> 7. **Lint executed against the tag** — the component's files clean, and the repository-wide count compared to the previous milestone. A milestone may not increase it.
> 8. **Prior components byte-identical**, proven by blob SHA-1 rather than inspection.
> 9. **Verification report generated**, recording every number above.
>
> Working directory success is NOT evidence.

**What changes in practice: nothing.** C8 satisfies all nine as written. C7 satisfies eight of nine (its guard-module figure is not reproducible, §2.1). C1–C5 satisfy the substance of all nine; items 2, 3 and 7 are simply not stated in their reports.

### 4.2 What this deliberately does not do

- **It does not retroactively invalidate any milestone.** C1–C8 remain GREEN. The underlying runs were real, isolated, and reconciled; what is missing is documentation of criteria that were not written down yet.
- **It does not make Ruff a blocker for existing debt.** Item 7 gates on *not increasing* the count, which the 21 pre-existing Tier A findings already satisfy. It would have failed nothing in Sprint 1.
- **It does not require re-verification of C1–C7.** Recommended only if the founder wants the record uniform; there is no engineering reason, and it costs seven worktree runs at roughly 2.5 minutes each.

---

## 5 · Founder decisions required

| # | Decision | Recommendation |
|---|---|---|
| **D1** | Adopt §4's interpretation — repository cleanliness plus component attribution? | **Yes.** It ratifies what all eight milestones already did |
| **D2** | Adopt §4.1's nine-item wording, replacing the six-item rule? | **Yes**, but it is a rule change and therefore founder-only |
| **D3** | Make lint a Rule 001 criterion (item 7)? | **Yes**, in the *non-increasing* form. Requires RUFF-GOV-01 first — an unpinned rule set cannot gate anything reproducibly |
| **D4** | Re-verify C1–C7 under the clarified wording? | **No.** No engineering benefit; the substance was already met |
| **D5** | Correct the C8 verification report's §4 note? | **Yes** — §2.1 above establishes it is wrong. The file is untracked, so this changes no history |

---

## 6 · What was not done

`Engineering/QUALITY_GATE_RULES.md` was **not modified** — it is the only tracked file in `Engineering/`, and amending a rule is not an engineering act. No verification report was rewritten; the C8 correction in §2.1 is recorded here and awaits D5. No milestone was re-verified. No commit, no tag.

---

*Governance review conducted against all seven verification reports and against measured facts from tags `kalpavriksha-s1-c1.1` through `kalpavriksha-s1-c8.0` on 2026-08-05. Guard-module membership and counts measured with `git ls-tree` and `pytest`, not read from the reports.*
