# Verification Report — `kalpavriksha-s1-c7.0`

**Gate applied:** Quality Gate Rule 001
**Verdict:** **GREEN**
**Date:** 2026-08-05

---

## 1 · Subject

| | |
|---|---|
| Tag | `kalpavriksha-s1-c7.0` (annotated) |
| Commit | `14b0e3a` |
| Milestone | Sprint 1, Component 7 — Attestation |
| Previous milestone | `kalpavriksha-s1-c5.0` → `5d065c2`, unchanged |

> **Tag numbering note.** Tags follow the *artifact* numbering reconciled in `SPRING_1_IMPLEMENTATION_ROADMAP_v2.md` §0.1, so this is `c7.0` even though the previous tag was `c5.0`. `Principal` and `ExecutionContext` shipped together under `c2.0` and count as Components 2 and 3. No tag was skipped and none is missing.

---

## 2 · Rule 001 criteria

| Criterion | Method | Result |
|---|---|---|
| Clean checkout | `git worktree add` into a temp path, isolated from the project directory | ✅ |
| Tag checkout | Worktree created at `kalpavriksha-s1-c7.0` | ✅ |
| Tests executed there | `PYTHONPATH=<worktree>/src python -m pytest tests/ -q`; source isolation confirmed | ✅ |
| Architecture guards executed there | 12 guard modules; C7's constitutional guards named in §4.1 | ✅ |
| Verification report generated | This document | ✅ |

---

## 3 · Test reconciliation

### Clean checkout at the tag

```
1858 passed, 1 skipped in 114.11s
```

| | |
|---|---|
| Passed | **1,858** |
| Failed | **0** |
| Skipped | 1 |

**Reconciliation:** 1,792 at `kalpavriksha-s1-c5.0` + 66 added by Component 7 = **1,858**. Exact.

Run twice — at commit `14b0e3a` before the tag existed, and at the tag after. Identical.

### Cumulative, by component

| # | Component | Tag | Tests | Running total |
|---|---|---|---|---|
| C1 | Canonical Clock | `c1.1` | 28 | 28 |
| C2 | Principal | `c2.0` | 21 | 49 |
| C3 | Execution Context | `c2.0` | 33 | 82 |
| C4 | Constitutional Warrant | `c3.0` | 55 | 137 |
| C5 | Constitutional Receipt | `c4.0` | 59 | 196 |
| C6 | Consequence Quartet | `c5.0` | 49 | 245 |
| **C7** | **Attestation** | **`c7.0`** | **66** | **311** |

Foundation total: **311 tests across seven components.** The remaining 1,547 are the pre-existing suite, unchanged.

### Working directory — information only, not evidence

```
3937 passed, 49 failed, 1 skipped
```

Reconciliation: 3,871 before Component 7 + 66 = **3,937**. The 49 are the 48 pre-existing failures from uncommitted MB032–039 work plus the `launcher/boot.py` guard true positive. **Component 7 introduced no new failure in either context.**

---

## 4 · Architecture guards

**12 modules · 507 passed, 1 skipped.**

### 4.1 Component 7 constitutional guards, named

| Guard | Protects | |
|---|---|---|
| `test_there_are_exactly_eight_questions` | §7.3's precondition set is closed | **PASSED** |
| `test_every_question_maps_to_the_attestor_veda_assigns_it` | §7.3's table, verbatim | **PASSED** |
| `test_exactly_two_questions_are_intelligence_only` | §7.4 — the two-attestation difference between pipelines | **PASSED** |
| `test_there_are_exactly_two_verdicts` | Absence is not a value one can carry | **PASSED** |
| `test_there_is_no_unknown_verdict` | No uncertainty where the Kernel expects an answer | **PASSED** |
| `test_an_attestation_attributed_to_the_wrong_component_is_refused` | §7.3 attestor identity | **PASSED** |
| `test_no_question_accepts_a_foreign_attestor` (×8) | Every question, exhaustively | **PASSED** |
| `test_a_principal_is_never_an_attestor` | ED-018 | **PASSED** |
| `test_it_has_no_dependency_on_the_warrant` | Frozen integration decision | **PASSED** |
| `test_it_has_no_dependency_on_the_principal` | ED-018 | **PASSED** |
| `test_it_imports_nothing_from_master_agent_at_all` | Flat, self-contained record | **PASSED** |
| `test_it_cannot_execute_or_authorize_work` | Acceptance criterion | **PASSED** |
| `test_it_reads_no_ambient_time` | Clock discipline | **PASSED** |
| `test_an_attestation_cannot_be_mutated` (×5) | Immutability | **PASSED** |

### 4.2 The one guard failure, unchanged

`test_only_the_clock_module_reads_the_machines_wall_clock` fails **in the working directory only**, on `launcher/boot.py`'s two uncommitted `datetime.now()` calls. Confirmed again that the sole offender is `boot.py` and **not** `attestation.py`. Absent at the tag, because `boot.py`'s committed version is clean.

Previously documented; **not addressed here**, per the brief's prohibition on unrelated edits.

---

## 5 · Components 1–6 unchanged

Verified by diff against `kalpavriksha-s1-c5.0`:

```
clock.py · principal.py · execution_context.py · warrant.py ·
receipt.py · consequence.py   →   byte-identical, zero changes
```

`Warrant` in particular remains byte-compatible with `kalpavriksha-s1-c3.0`, per the frozen integration decision. Milestone integrity preserved across all seven tags.

---

## 6 · What changed

| File | |
|---|---|
| `src/master_agent/foundation/attestation.py` | new, 280 lines |
| `src/master_agent/foundation/__init__.py` | modified — exports only |
| `tests/test_foundation_attestation.py` | new, 469 lines |

**759 insertions, 0 deletions, three files.**

Against the roadmap's estimate of ~180 source lines and ~50 tests: **280 lines and 66 tests**. The overrun is the attestor-identity mapping and its exhaustive per-question test (§7 ED-019), which the roadmap did not anticipate.

---

## 7 · Engineering decisions

**ED-018 · The attestor is a component, never a `Principal`. The roadmap was wrong.**

`SPRING_1_IMPLEMENTATION_ROADMAP_v2.md` §2 C7 declares: *"Depends on. C1 Clock (freshness), **C2 Principal (attestor identity)**."*

That is incorrect, and it is my error in a document the founder approved as canonical. All eight attestors in Kernel Specification §7.3 are **components**:

```
A1 Mission Control      A5 Principal model
A2 Reversibility Reg.   A6 Capability contract
A3 Permission System    A7 Broker
A4 Standing Rule Engine A8 Broker
```

A `Principal` is frozen as a human authority — founder or delegate. Note A5 in particular: the question *"who is acting?"* is attested by the **registry that resolves principals**, not by a principal.

Building it as the roadmap declared would have placed a human authority where a component belongs — **precisely the conflation Component 2's conflict report was written about.**

*Resolution:* `attestor: str`, a component identifier. Attestation depends on **C1 Clock only**. This *removes* a dependency and leaves the public API shape unchanged.

*Reported before writing code*, per the standing instruction added to this brief. Proceeded rather than blocking because the frozen Kernel Specification is unambiguous and the correction is strictly narrowing.

> **Roadmap amendment required:** §2 C7's "Depends on" line should read *"C1 Clock (freshness)"* only. **Not applied here** — amending the roadmap is not part of an implementation brief.

**ED-019 · Attestor identity is enforced at construction, not merely checked by the Kernel.**

§7.3 assigns each question exactly one attestor, one-to-one. That mapping lives with the question as `AttestationQuestion.canonical_attestor`, and an attestation whose attestor does not own its question raises.

*Why:* §7.3 says such an attestation *"is treated as absent."* Making it unconstructable means it can never be verified incorrectly, because it can never exist — the same posture that makes an over-ceiling `Warrant` and a compensation-less `PARTIAL` `Receipt` unconstructable.

*This does not replace the Kernel's check.* The Kernel still verifies presence, subject match and freshness; this makes one of the four impossible to get wrong. It also means the Kernel needs no attestor table of its own.

*Cost:* the mapping and its exhaustive eight-question test are most of the overrun against the roadmap's size estimate. Worth it — the alternative is a table in the Kernel, which §14 R9's 600-line ceiling is already tight against.

**ED-020 · Two verdicts, not three.**

No `UNKNOWN`, no `ABSENT`. §7.3: an attestation that is missing, stale, wrongly attributed or subject-mismatched *"is treated as absent."* Absence is the **lack** of an attestation, never a value one can carry. A third verdict would let a component record uncertainty where the Kernel expects an answer, and the Kernel would then have to decide what that meant — which is re-deriving a verdict, the one thing §7.3 forbids it.

Contrast with `Receipt.ExecutionOutcome`, which *does* carry `UNKNOWN` (ED-008). That is correct and not inconsistent: after execution, *"I cannot determine whether the effect occurred"* is an honest finding. Before execution, *"I cannot determine whether this check passed"* is simply a refusal.

**ED-021 · `reason` is required on `REFUSED` and refused on `SATISFIED`.**

Symmetry carried from `Receipt.compensation_ref` (ED-007). A refusal that cannot say what failed is not answerable, and allowing a reason on a satisfied attestation would let the field drift into a general-purpose note.

**ED-022 · `subject` is opaque.**

§7.3 requires the Kernel to check *subject match*. What identifies a subject — a payload digest, a capability, a request id — is the Kernel's business, not this value's. Holding it opaque is the same discipline `Warrant.rule_ref` uses, and it is why this module needs no knowledge of what it is attesting about.

**ED-023 · No `attestation_id`.**

`Warrant` and `Receipt` carry ids because they are independently referenced. An attestation is only ever carried inside a request or aggregated by the Kernel; nothing looks one up. Adding an id would be inventing a reference nothing uses.

---

## 8 · Risks discovered

| # | Risk | Severity | Status |
|---|---|---|---|
| **R11** | **The roadmap contains at least one incorrect dependency** (ED-018), found on the first component built from it. Others may be wrong in the same way — declared from recollection rather than from the frozen specification. | **High** | **New.** Mitigated by the founder's standing instruction to re-read the roadmap and stop on mismatch; that instruction caught this one. Every remaining component's dependencies should be re-grounded against the Kernel Specification at brief time, not trusted from the roadmap. |
| **R12** | **`AttestationQuestion.canonical_attestor` freezes an architectural assignment in code.** If §7.3's question→attestor mapping ever changes — for instance if the Rule Engine is renamed, or A4 moves — this raises at construction across every caller. | Medium | **New, accepted.** That is the intended behaviour: a silent reassignment of constitutional responsibility should break loudly. The mapping is one dictionary in one module. |
| **R1** | `Objective`/`Mission` ADR unratified — blocks C17 Objective Engine | **Critical** | Unchanged, still open. Longest-standing blocker. |
| **R2** | `Warrant.attestations` field | High | **Resolved** by the frozen integration decision in this brief: `Warrant` is not modified; the Kernel aggregates externally. |
| **R3** | MB032–039 uncommitted; collides with C16 Execution Path | **Critical** | Unchanged. Window closes when C16 begins. |
| **R7** | `launcher/boot.py` ambient time | Medium | Unchanged. Must be resolved before that edit is committed. |

---

## 9 · Rule 000 assessment

> *Every engineering change must leave the repository more trustworthy than it was before the change.*

**Passes.** The Kernel's central design — *"verifies attestor identity… never re-derives the verdict"* — now has a type, and one of its four verification properties is enforced at construction rather than downstream. An attestation attributed to the wrong component cannot exist.

An incorrect dependency in a document approved as canonical was caught before it reached code, by the standing instruction added to this brief.

Nothing unrelated was touched, and all six prior components are byte-identical.

---

*Generated in a clean checkout of `kalpavriksha-s1-c7.0`, per Quality Gate Rule 001. All temporary worktrees removed.*
