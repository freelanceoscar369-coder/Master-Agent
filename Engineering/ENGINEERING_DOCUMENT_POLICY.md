# Engineering Document Policy

**Type:** Practice investigation and recommendation. **No repository changes, no commits, no tags.**
**Date:** 2026-08-05
**Question:** should HEALTH reports, VERIFICATION reports and other Engineering documents be tracked, untracked, or something else?

---

## 0 · Answer, in one line

**Current practice is: every Engineering document is untracked except one, and that is an accident of history rather than a decision.** The recommendation is to **track verification and health reports, and keep working documents untracked** — a split policy, stated in §4.

---

## 1 · What the practice actually is — measured

### 1.1 `Engineering/` today

| File | Git state |
|---|---|
| `QUALITY_GATE_RULES.md` | **Tracked** |
| `CONFLICT_C2_PRINCIPAL.md` | Untracked |
| `CONFLICT_C5_CONSEQUENCE_QUARTET.md` | Untracked |
| `VALIDATION_C6.md` | Untracked |
| `VERIFICATION_kalpavriksha-s1-c1.1.md` | Untracked |
| `VERIFICATION_kalpavriksha-s1-c2.0.md` | Untracked |
| `VERIFICATION_kalpavriksha-s1-c3.0.md` | Untracked |
| `VERIFICATION_kalpavriksha-s1-c4.0.md` | Untracked |
| `VERIFICATION_kalpavriksha-s1-c5.0.md` | Untracked |
| `VERIFICATION_kalpavriksha-s1-c7.0.md` | Untracked |
| `VERIFICATION_kalpavriksha-s1-c8.0.md` | Untracked |
| `HEALTH_C8.md` | Untracked |
| `C9_IMPLEMENTATION_PRECHECK.md` | Untracked |

**One tracked file out of thirteen.** `Engineering/` is not in `.gitignore`; these files are simply never staged.

### 1.2 Milestone commits — measured

Every Sprint 1 milestone commit contains **exactly three files**:

| Tag | Files committed |
|---|---|
| `c3.0` | `warrant.py` · `test_foundation_warrant.py` · `foundation/__init__.py` |
| `c4.0` | `receipt.py` · `test_foundation_receipt.py` · `foundation/__init__.py` |
| `c5.0` | `consequence.py` · `test_foundation_consequence.py` · `foundation/__init__.py` |
| `c7.0` | `attestation.py` · `test_foundation_attestation.py` · `foundation/__init__.py` |
| `c8.0` | `refusal.py` · `test_foundation_refusal.py` · `foundation/__init__.py` |

**No milestone commit has ever contained a document.** The C8 finalization brief asked for "documentation directly belonging to C8" to be staged; precedent was followed instead, and that choice is what prompted this investigation.

### 1.3 Root-level architecture documents

The frozen specifications this project grounds against are **also untracked**:

```
CONSTITUTIONAL_KERNEL_SPECIFICATION.md    OBJECTIVE_ENGINE_SPECIFICATION_v1.0.md
SPRING_1_IMPLEMENTATION_ROADMAP_v2.md     FIRST_FOUNDER_JOURNEY_SPECIFICATION_v1.0.md
SPRING_1_..._AMENDMENT_001.md             KALPAVRIKSHA_IMPLEMENTATION_BLUEPRINT.md
VEDRA_PROJECT/  (all five VEDAs)          ENGINEERING_BASELINE_ASSESSMENT_v1.0.md
```

**This is the more serious half of the finding.** Rule 002 requires grounding every component against documents that exist in no commit. `ARCHITECTURE.md`, `DECISIONS.md`, `MANIFESTO.md` and `ROADMAP.md` *are* tracked, so the repository already mixes both conventions at its root.

---

## 2 · Is the current practice defensible?

### 2.1 The arguments for leaving reports untracked

| Argument | Weight |
|---|---|
| **A verification report cannot be in the commit it verifies.** It records the test counts produced *by* that commit and the tag cut *after* it. Committing it requires a second commit after every tag | **Strong, and correct** |
| A report is evidence *about* the repository, not part of the product | Moderate |
| Documents in milestone commits inflate the diff and obscure what shipped | Weak — a separate commit solves this |

### 2.2 The arguments against

| Argument | Weight |
|---|---|
| **Rule 001 requires a verification report as a GREEN criterion. An artifact that is a gate criterion but exists in no commit cannot be audited from the repository** | **Decisive** |
| **A clean checkout of `c8.0` contains no evidence that `c8.0` was ever verified.** The proof of GREEN lives only on one machine | **Decisive** |
| Rule 002 requires grounding against frozen documents that are in no commit. A fresh clone cannot execute Rule 002 at all | **Decisive** |
| Untracked files are one `git clean -fdx` from gone. There is no second copy | **Strong** |
| Conflict and precheck reports are cited *by* tracked work — `refusal.py` cites ED-018 from an untracked report | Moderate |

### 2.3 Verdict

**The current practice is not defensible, and the reason is narrow and specific.**

Rule 001 makes "verification report generated" a condition of GREEN. Eight milestones are GREEN. **A clone of this repository contains proof of none of them.** The reports, the conflict reports that redirected two components, and the frozen specifications every component was grounded against are all outside version control.

The three-file commit convention is *correct* and should be kept. The error is not what milestone commits contain — it is that **nothing else is ever committed at all.**

---

## 3 · Options considered

| Option | Effect | Assessment |
|---|---|---|
| **(a) Always untracked** | Status quo | **Rejected.** Rule 001's own criterion becomes unauditable, and Rule 002 is impossible from a clone |
| **(b) Always committed, inside the milestone commit** | Reports ship with their component | **Rejected.** Circular — a verification report cannot describe the commit that contains it, and the tag is cut after |
| **(c) Split by document kind, separate commits** | Evidence tracked; working documents not | **Recommended.** §4 |
| **(d) Separate repository for engineering records** | Full separation | **Rejected.** Adds a second thing to keep in sync, and the link between a tag and its evidence is exactly what must not be breakable |

---

## 4 · Recommended policy

> ### Engineering documents are classified as **Evidence**, **Authority**, or **Working**. Evidence and Authority are tracked. Working documents are not.

### 4.1 The three classes

| Class | What it is | Examples | Policy |
|---|---|---|---|
| **Evidence** | Records that a gate was passed. Cited by Rule 001 | `VERIFICATION_*.md` · `HEALTH_*.md` | **Tracked.** Committed in a **follow-up commit after the tag**, never in the milestone commit |
| **Authority** | Documents that later work is grounded against, and that a conflict report can contradict | `QUALITY_GATE_RULES.md` · the roadmap and its amendment · Kernel/Objective/Journey specifications · the VEDAs · `CONFLICT_*.md` · `*_CLARIFICATION.md` once ratified | **Tracked.** Committed when created or ratified |
| **Working** | Snapshots of a moment, superseded by the next pass | `*_PRECHECK.md` · `*_REGISTER.md` · `*_STATUS.md` · audits and assessments | **Untracked** by default; promoted to Authority if ratified |

### 4.2 Why the split, rather than tracking everything

An audit needs to answer two questions: *"was this tag verified?"* and *"what was it verified against?"* Evidence answers the first, Authority the second. Working documents answer neither — they are how the answers were reached, and they change every pass. Tracking them adds churn without adding auditability.

### 4.3 The commit shape

```
commit N     Sprint 1 Component 8: Introduce the Kernel Refusal   ← 3 files, unchanged
tag          kalpavriksha-s1-c8.0                                 ← after Rule 001 passes
commit N+1   Verification evidence for kalpavriksha-s1-c8.0       ← the reports
```

**The milestone commit's three-file shape is preserved exactly.** Evidence lands in the commit *after* the tag, which resolves §2.1's circularity without weakening anything.

### 4.4 The backlog this creates

| Item | Files | Priority |
|---|---|---|
| **Authority — frozen specifications** | Kernel Spec, Objective Engine Spec, First Founder Journey Spec, Roadmap v2, Amendment 001, Implementation Blueprint, `VEDRA_PROJECT/` (5 VEDAs) | **Highest.** Rule 002 cannot be executed from a clone until these are in |
| **Evidence — seven verification reports** | `c1.1`, `c2.0`, `c3.0`, `c4.0`, `c5.0`, `c7.0`, `c8.0` + `HEALTH_C8.md` | High. One commit, retrospective |
| **Authority — conflict and validation reports** | `CONFLICT_C2`, `CONFLICT_C5`, `VALIDATION_C6` | Medium. Cited by shipped code (ED-018) |
| **Working — leave untracked** | `C9_IMPLEMENTATION_PRECHECK.md`, this document, the three other documents from this brief | — |

**None of this is done here.** This brief forbids commits, and the policy needs founder ratification before a backlog is worked.

---

## 5 · One risk this surfaces

**The frozen specifications are untracked, and Rule 002 mandates grounding against them.**

Consequences, stated plainly:

- A fresh clone cannot ground a component. Rule 002 is unexecutable from the repository alone.
- There is **no version history for a "frozen" document.** If the Kernel Specification changed tomorrow, nothing would record that it had. "Frozen" is currently an assertion, not a property.
- Amendment 001 supersedes the roadmap where they differ. Neither file is in any commit, so **the authority relationship between them exists only in prose**, in a file that is itself untracked.
- `git clean -fdx` in this working directory would destroy the roadmap, the amendment, all five VEDAs, the Kernel Specification, and every verification report for eight GREEN milestones.

**Severity: Critical.** Carried into `DEMO_RISK_REGISTER.md` as **D7**.

---

## 6 · Founder decisions required

| # | Decision | Recommendation |
|---|---|---|
| **E1** | Adopt the Evidence / Authority / Working split? | **Yes** |
| **E2** | Keep milestone commits at three files, with Evidence in a follow-up commit? | **Yes** — preserves precedent and resolves the circularity |
| **E3** | Commit the frozen specifications retrospectively? | **Yes, and first.** This is the Critical item |
| **E4** | Commit the seven prior verification reports retrospectively? | **Yes**, one commit, clearly labelled retrospective |
| **E5** | Should a "frozen" document be protected further — signed tags, or a `frozen/` directory with a guard test? | **Worth deciding, not urgent.** Tracking them first is what makes any further protection possible |

---

## 7 · What was not done

No file was staged, committed, moved or renamed. `.gitignore` was not modified. `Engineering/QUALITY_GATE_RULES.md` was not touched. The backlog in §4.4 is a proposal awaiting E1–E4.

---

*Practice investigation conducted against `git ls-files`, `git status` and the file list of every Sprint 1 milestone commit on 2026-08-05. Every tracking state above was measured, not assumed.*
