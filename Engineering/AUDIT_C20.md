# Engineering Audit — C20 Founder Presence Layer

**Component:** C20 — Founder Presence Layer
**Role:** Independent Architecture Auditor. The auditor did not implement C20.
**Audit Date:** 2026-08-06
**Repository state:** `HEAD` = `01497c3`, tag `kalpavriksha-s1-c18.0`. One branch (`main`), no stash, one worktree.
**Constraint:** Read-only — no modifications, no commits, no tags.

---

## Executive Verdict

> ## **NO VERDICT ISSUED — the audit could not be performed.**
>
> **The artefact under audit is not present in this repository.** No
> implementation, no tests, and no `Engineering/HEALTH_C20.md` exist.

**Why none of the three permitted verdicts was chosen.**

The brief requires exactly one of `PASS` · `PASS WITH OBSERVATIONS` ·
`FAIL`. Each of the three is a statement about an implementation the
auditor has examined:

| Verdict | What issuing it would assert |
|---|---|
| `PASS` | Code was inspected and found compliant. **Would be false.** |
| `PASS WITH OBSERVATIONS` | Code was inspected, found compliant, with named residuals. **Would be false.** |
| `FAIL` | Code was inspected and found non-compliant. **Also false** — nothing was inspected, and "absent" is not "incorrect." |

The brief's own first two constraints govern this: *"Do NOT use
assumptions"* and *"Do NOT repair missing information."* An auditor who
issues a verdict on code they have not seen has done the opposite of
auditing, and a `PASS` produced that way is the single most damaging
artefact this process can generate.

**This report is therefore evidence of absence, not a judgment of
quality.** The verdict slot stays empty until the artefact is available.

---

## 1 · Evidence — what was searched, and what was found

Every search below was run against the working tree at `01497c3`.

| # | Search | Result |
|---|---|---|
| 1 | `find . -iname "*C20*"` (repository-wide, excluding `.git`) | **No match.** `Engineering/HEALTH_C20.md` does not exist |
| 2 | `grep -rln "PresenceSnapshot"` over all `.py` and `.md` | **No match** |
| 3 | `grep -rn "Presence\|presence"` over `src/`, `Engineering/`, root `*.md` | Six matches, **all incidental English** in unrelated modules — `ai_infrastructure/catalog.py:65`, `capabilities/contract.py:231`, `foundation/attestation.py:5,49`, `foundation/execution_request.py:54,55`. None is a type, module, or identifier |
| 4 | `grep -rl "Presence Layer"` | **No match** |
| 5 | `ls src/master_agent/` | 33 packages. **No `presence/` package** |
| 6 | `git log kalpavriksha-s1-c18.0..HEAD` | **No commits since the tag** |
| 7 | `git branch -a` | `main` and `remotes/origin/main` only. **No C20 branch** |
| 8 | `git stash list` | **Empty** |
| 9 | `git worktree list` | One worktree, the project directory |
| 10 | `git status --porcelain --untracked-files=all -- src/ tests/` | 64 untracked files, all of them **pre-existing MB032–039 work** (`ai_infrastructure/`, `brain/`, `broker/`, `capabilities/`, `memory/`, `missions/`, `planner/`, `plugins/`, `providers/`) plus **C19** (`vigilance/`, `tests/test_vigilance.py`). **No presence module, no C20 test file** |

### 1.1 Two near-misses, examined and excluded

Both are named here so that nobody reading this report concludes they were
overlooked.

**`src/master_agent/voice/`** — three files, `__init__.py`, `input.py`,
`output.py`. **Present and tracked at `kalpavriksha-s1-c18.0`**, modified
2026-07-24, and unmodified in the working tree. `output.py` contains
`Speaker` and `LocalPiperSpeaker` — text-to-speech transport. It is
neither a Presence Layer nor the Roadmap's Voice Charter Validator, and it
predates this milestone entirely.

**`VEDRA_PROJECT/02_Desktop/kd/src/app/shell/PresenceSigil.tsx`** and its
CSS module — TypeScript/React inside the Electron desktop tree. It is not
Python, not in `src/master_agent/`, not in Sprint 1's component track, and
carries no `PresenceSnapshot`. The founder's standing instruction excludes
UI, Electron and dashboard work from this scope, so it was **not
audited** and is recorded only as a name collision.

---

## 2 · Ground that was available, and ground that was not

The brief names eight sources. Their availability:

| Source | Available |
|---|---|
| Kernel Specification | ✅ `CONSTITUTIONAL_KERNEL_SPECIFICATION.md` |
| ADR-0022 · ADR-0023 | ✅ `docs/adr/` |
| VEDA 01–05 | ✅ |
| `ROADMAP.md` | ✅ |
| C1–C19 | ✅ committed through `c18.0`; C19 present and untracked |
| **C20** | ❌ **absent** |
| **`HEALTH_C20.md`** | ❌ **absent** |

**Two of the eight grounded sources are missing, and they are the two the
audit is about.** Under *"if documentation does not support a claim,
explicitly state it"*, no claim about C20 can be supported by anything in
this repository.

---

## 3 · Constitutional Compliance

**Cannot be verified. No artefact.**

The brief asks whether the Presence Layer owns only `PresenceSnapshot`
production, runtime observation and founder-facing state projection, and
none of authorization, orchestration, execution, mutation, business logic,
planning, plugin invocation, tool execution or mission management.

**No file exists against which any of those eleven questions can be
asked.** Nothing is asserted in either direction.

---

## 4 · Boundary Verification

**Cannot be verified for C20. No artefact.**

One adjacent fact *is* measurable and is recorded because it is true
independently of C20: the five packages the founder froze are unmodified
in the working tree.

```
git status --porcelain -- src/master_agent/foundation \
                          src/master_agent/kernel \
                          src/master_agent/ledger \
                          src/master_agent/coordinator \
                          src/master_agent/runtime_bridge
→ (empty)
```

**This proves the freeze holds today. It does not prove C20 respects it**,
because C20 is not present to respect or violate it.

---

## 5 · Green Component Protection

**Cannot be verified for C20.**

`git log kalpavriksha-s1-c18.0..HEAD` is empty and `git diff` against the
tag shows no modification to any tracked source. Every GREEN component
from C1 through C18 is byte-identical to its state at the frozen tag.

Again: this is a property of the repository as it stands, **not evidence
about C20**.

---

## 6 · Hidden Dependency Audit

**Cannot be performed. No import graph exists to analyse.**

---

## 7 · Snapshot Contract Review

**Cannot be performed.**

The brief specifies eight fields — active mission, execution state, calm
state, vigilance state, pending approvals, last action, reasoning summary,
current activity — and requires that every one be *derived, not invented*.

**No `PresenceSnapshot` type exists anywhere in the repository**, so no
field can be traced to a source, and the derived-versus-invented question
cannot be asked of anything.

One documentation observation, recorded rather than resolved: **the
eight-field contract appears in the Mission Brief and in no frozen
document available here.** Searches 2 and 4 found no specification of
`PresenceSnapshot` in the Kernel Specification, the VEDAs, the ADRs or the
Roadmap. Were the artefact present, this auditor would have no ratified
source against which to check its shape.

---

## 8 · Calm Review

**Cannot be performed for C20's implementation.** One finding *is*
available and is the most substantive result of this audit.

The brief asks whether **"running missions do not block calm"** is
supported by the Kernel Specification or by VEDA.

**Measured answer: no frozen document available here states it, in either
direction.**

What the frozen documents do say about calm:

> **VEDA 04 D7** — *"'Nothing needs you' … is only safe if it is provably
> complete — backed by a coverage check across **every monitored domain**
> confirming each was actually checked, within its freshness window,
> without error."*
>
> **Invariant:** *"if any domain is **stale, unreachable or errored**, the
> system may not say 'nothing needs you.'"*
>
> **VEDA 04 F7** — *"any gap → the greeting MUST name it. 'Nothing needs
> you' is unavailable while coverage is incomplete."*

**Every stated condition on calm is about coverage — whether each watched
domain was checked, freshly, without error.** Nothing in D7, F7, VEDA 04
§4's `attest()` contract, or the Kernel Specification mentions running
work, in-flight missions, or outstanding warrants as a condition on the
calm state, either to block it or to exempt it.

So the proposition *"running missions do not block calm"*:

| | |
|---|---|
| **Contradicted by a frozen document?** | **No.** No frozen text makes running work a blocker |
| **Supported by a frozen document?** | **No.** No frozen text exempts it either |
| **Status** | **Unsupported and uncontradicted — an undocumented design decision** |

Recorded as **R62**. Per the brief, no implementation change is
recommended and none could be: there is no implementation.

**A related measurable fact.** C19's shipped `CalmState`
(`src/master_agent/vigilance/vigilance.py`) gates solely on
`Coverage.complete`, which is computed from registered domains and their
freshness and health. It reads no mission, no warrant and no outstanding
count — consistent with the frozen documents, and consistent with the
proposition, without either citing it.

---

## 9 · Reasoning Review

**Cannot be performed.**

The brief requires that reasoning summaries be projected and never
generated, hallucinated or synthesised — *"Presence must never become an
LLM."* This is precisely the kind of guarantee that must be verified by
reading imports and call graphs, and there is no module to read.

Recorded so it is not later assumed to have been checked: **this
requirement has not been verified.**

---

## 10 · Purity Review

**Cannot be performed.**

The brief lists seven prohibitions — no network, filesystem, timers,
threads, background execution, randomness, or hidden state. All seven are
verifiable by AST and import analysis. **None was verified**, because
there is nothing to analyse.

---

## 11 · Test Quality Review

**Cannot be performed. No C20 test file exists.**

The brief asks specifically whether the purity guards *"genuinely enforce
the stated guarantees"* — a question that requires reading the assertions.
No assertions are available.

One methodological note, offered because it is the failure mode this
particular review category exists to catch and it has already been seen
once in this project: a guard that matches **source text** rather than
**executable identifiers** will pass against a module whose own docstring
names the thing it forbids, and will fail spuriously for the same reason.
Were C20's guards available, that is the first property this auditor would
check.

---

## 12 · Technical debt

**Cannot be assessed for C20.**

Documentation debt that *is* observable, and is a precondition for any
future C20 audit, is recorded as R63 below.

---

## 13 · New Risks

Both risks below concern the **audit process and the documentation**, not
C20's code, about which this report makes no claim.

| ID | Risk | Severity |
|---|---|---|
| **R62** | *"Running missions do not block calm"* is unsupported and uncontradicted by any frozen document | **Medium** |
| **R63** | An independent audit was commissioned against an artefact that does not exist in the repository | **High** |

### R62 — the calm proposition has no frozen basis

**Severity:** Medium
**Why it matters:** VEDA 04 D7 calls *"Nothing needs you"* the product's
*"highest-value claim and its greatest liability"*, and names a silent gap
as *"the single failure most likely to end a customer relationship
permanently."* A rule governing when that sentence may be spoken is a
constitutional rule. One that lives only in a Mission Brief can be changed
without an ADR, cannot be cited by a future auditor, and cannot be tested
against anything.
**Blocks Rule 001?** **No.** Rule 001's gates are checkout, commit, tag,
tests, guards and report. An undocumented design decision fails none of
them. It should be settled by an ADR before a surface speaks the sentence.

### R63 — the audit had no subject

**Severity:** High
**Why it matters:** The brief instructs the auditor to *"treat the
implementation as potentially incorrect"* and *"prove it wrong if
possible."* Neither is possible against an absent artefact. The danger is
not this report — it is the adjacent outcome, where an auditor under
schedule pressure resolves the ambiguity by issuing `PASS` for work nobody
examined, and that `PASS` then satisfies a gate. **A verdict on absent
code is worse than no verdict**, because it looks like evidence.

Nothing here diagnoses *why* C20 is absent. The measurable facts are only
these: no commits since `01497c3`, one branch, no stash, one worktree, and
no C20 file anywhere in the tree. Whether the work exists elsewhere, was
not started, or was not delivered into this repository **is not
determinable from here and is not guessed at.**

**Blocks Rule 001?** **Yes, for C20 specifically.** Rule 001 requires
tests and architecture guards executed against a tag. C20 has no code, no
tests and no commit, so there is nothing to tag and no milestone to
declare. It blocks nothing else: `kalpavriksha-s1-c18.0` is unaffected and
remains GREEN.

---

## 14 · One documentation observation

`ROADMAP.md` §2 names **C20 · Voice Charter Validator**. This brief names
C20 the **Founder Presence Layer**. They are different components with
different purposes and different public APIs.

This is the fourth such divergence and is already on the register as
**R54** — the roadmap is the architectural source of truth while the
execution sequence is controlled separately. It is restated here only so
that a future reader of this file knows which C20 was audited: **the
Founder Presence Layer, as named by the Mission Brief.**

---

## 15 · What would make this audit possible

Stated as fact, not as a recommendation about design:

1. `Engineering/HEALTH_C20.md` present.
2. The implementation present in the working tree or on a reachable
   branch, with its module path identified.
3. The C20 test suite present.

With those three, every section of this report can be completed as
specified. Without them, no section can.

---

*End of Audit — Read-Only. No files modified. No commits. No tags. No
verdict issued, and none inferred.*
