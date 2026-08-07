# Health Report — Sprint 1 Component 8: Kernel Refusal

**Type:** Milestone health report.
**Date:** 2026-08-05
**Status:** **GREEN** — committed `ac5e399`, tagged `kalpavriksha-s1-c8.0`, verified under Quality Gate Rule 001.
**Verification evidence:** `Engineering/VERIFICATION_kalpavriksha-s1-c8.0.md`

> Every figure in this document is measured in a **clean isolated worktree at the tag**, not in the working directory. Where a working-directory figure appears it is labelled as such and is not evidence.

---

## 0 · Rule 002 assessment — asked before implementing

> *Does this increase the probability that Founder Edition succeeds before 12 Aug?*

**Yes.** Two of the Kernel's four operations return this type. Kernel Specification §3.5:

```
  authorize(ExecutionRequest) → Intent | Refusal
  attempt(intent_id)          → AttemptToken | Refusal
```

C15 cannot be written without it, and C15 is the sprint. There is no version of the Founder Edition proof in which the Kernel refuses and has nothing to refuse **with**.

Scope was not expanded. One component, one commit, one tag.

---

## 1 · Size

| Metric | Value |
|---|---|
| **Source LOC** — `refusal.py`, total | **379** |
| **Executable LOC** — statements only | **107** |
| — docstring lines | 126 |
| — comment lines | 67 |
| — blank lines | 79 |
| **Test LOC** — `test_foundation_refusal.py` | **799** |
| **Tests added** | **108** |
| Exports added to `foundation/__init__.py` | +12 lines, 5 symbols |
| **Total commit** | **1,190 insertions, 0 deletions, 3 files** |

### 1.1 Against the roadmap estimate

| | Roadmap §2 C8 | Actual | |
|---|---|---|---|
| Source | ~130 lines | **107 executable** | under |
| Tests | ~35 | **108** | 3.1× over |

**The overrun is Amendment 001 M5's, and it is accounted for rather than absorbed.** The roadmap sized C8 against a one-family reason set. M5 widened it to three families and eleven reasons, and each widening is exhaustively tested: 8 questions × 2 attestor guards = 16 tests on attestor identity alone, plus per-reason check-placement tests for §11.1, §11.5 and §11.6, plus the closed-vocabulary tests for two new enums. Same shape as C7's overrun (280 vs 180 lines), same cause — enforcing at construction what the roadmap assumed would be checked downstream.

The **executable** source came in under estimate. The 379 total is the documentation density C1–C7 established, where each invariant cites the specification line requiring it.

### 1.2 Public surface — 5 symbols

```
KernelCheck            closed enum, 3  — §7.2's checks the Kernel performs itself
RefusalFamily          closed enum, 3  — kernel_check · attestation · infrastructure
RefusalReason          closed enum, 11 — spanning all three families
KernelRefusal          frozen dataclass — reason, failed_check, attestor, remediable, detail
InvalidKernelRefusal   ValueError, raised at construction
```

---

## 2 · Reconciliation against the previous milestone

### 2.1 Full suite, clean checkout

| | `c7.0` | C8 | `c8.0` |
|---|---|---|---|
| **Passed** | 1,858 | **+108** | **1,966** |
| **Failed** | 0 | +0 | **0** |
| Skipped | 1 | +0 | 1 |

**Exact.** Measured twice — at commit `ac5e399` before the tag existed, and at the tag afterwards. Both runs: `1966 passed, 1 skipped`.

### 2.2 Foundation suite, cumulative

Measured at the tag: **419 passed.**

| # | Component | Tag | Tests | Running total |
|---|---|---|---|---|
| C1 | Canonical Clock | `c1.1` | 28 | 28 |
| C2 | Principal | `c2.0` | 21 | 49 |
| C3 | Execution Context | `c2.0` | 33 | 82 |
| C4 | Constitutional Warrant | `c3.0` | 55 | 137 |
| C5 | Constitutional Receipt | `c4.0` | 59 | 196 |
| C6 | Consequence Quartet | `c5.0` | 49 | 245 |
| C7 | Attestation | `c7.0` | 66 | 311 |
| **C8** | **Kernel Refusal** | **`c8.0`** | **108** | **419** |

311 + 108 = 419. Exact.

### 2.3 Working directory — information only, not evidence

```
4045 passed, 49 failed, 1 skipped
```

3,937 + 108 = **4,045**, failures **unchanged at 49**. All 49 are MB032–039 uncommitted work (R3) plus `launcher/boot.py` ambient time (R7); all 49 are **absent at the tag**.

---

## 3 · Exact pass counts

| Gate | At commit `ac5e399` | At tag `c8.0` |
|---|---|---|
| Full suite | **1,966 passed · 0 failed · 1 skipped** | **1,966 passed · 0 failed · 1 skipped** |
| Architecture guards (6 modules) | **215 passed · 0 failed · 1 skipped** | **215 passed · 0 failed · 1 skipped** |
| C8 constitutional guards | **22 passed · 0 failed** | **22 passed · 0 failed** |
| C8 component tests | **108 passed · 0 failed** | **108 passed · 0 failed** |
| Foundation suite | — | **419 passed · 0 failed** |

Identical at commit and tag.

---

## 4 · Ruff

| Scope | At `c7.0` | At `c8.0` | |
|---|---|---|---|
| **C8's three files** | — | **All checks passed** | ✅ |
| Repo-wide `src/` + `tests/` | **21 findings** | **21 findings** | unchanged |

**C8 introduced zero Ruff findings.** The 21 pre-existing findings sit in `test_memory.py` (5), `mission_manager/mission.py` (3), `permissions/permission_system.py` (2), `executor/executor.py` (2), `cli.py` (2) and seven other files — none touched by C8, all left alone per the prohibition on opportunistic fixes.

Config: `line-length = 100`, `target-version = "py311"`. C8's longest line: **84** characters.

### 4.1 Two deliberate non-fixes

Run speculatively against a **wider** rule set than the project configures, two patterns appear in C8: `UP042` (`str, Enum` rather than `StrEnum`) and `N818` (`Invalid*` without an `Error` suffix). **Neither was changed.** `InvalidWarrant`, `InvalidReceipt`, `InvalidConsequence` and `InvalidAttestation` all use exactly these patterns and all four sit inside frozen green components. C8 matching them is correct; changing C8 alone would make it the odd one out, and changing the others would modify frozen components without authorization.

---

## 5 · Architecture guards

**6 modules · 215 passed · 1 skipped · 0 failed**, identical at commit and tag.

```
test_browser_constitution_compliance.py   test_persistence_architecture.py
test_dashboard_architecture.py            test_runtime_approval_boundary.py
test_mission_control_architecture.py      test_runtime_architecture.py
```

> **On the module count.** The C7 report cited 12 modules run against the *working directory*. Six of those — including `test_missions_architecture.py` and `test_planner_architecture.py` — are files of the uncommitted MB032–039 work and **do not exist at any green tag**. Six is the correct count at `c8.0` and was also correct at `c7.0`. The four `test_missions_architecture.py` failures seen in the working directory have no counterpart at the tag.

---

## 6 · Constitutional guards — 22, all passing

| Guard | Protects |
|---|---|
| `test_there_are_exactly_three_kernel_checks` | §7.2 — *"exactly three"* |
| `test_the_kernel_check_vocabulary_is_closed` | A fourth Kernel-owned check is constitutional, not code |
| `test_a_kernel_check_is_not_an_attestation_question` | §7.2 and §7.3 vocabularies never overlap |
| `test_every_reason_belongs_to_exactly_one_family` | Amendment M5's three families |
| `test_each_of_the_three_kernel_checks_is_representable` | §7.5 — an unrepresentable refusal is unrecordable |
| `test_a_degraded_network_is_not_a_refusal_reason` | §11.7 — *"the Kernel decides nothing here"* |
| `test_learning_unavailable_is_not_a_refusal_reason` | §11.4 — the only "proceed" |
| `test_an_attestation_refusal_requires_the_canonical_attestor` ×8 | §7.3 attestor identity, exhaustively |
| `test_an_attestation_refusal_may_not_omit_the_attestor` ×8 | §7.5 — a refusal names the attestor |
| `test_a_kernel_check_refusal_has_no_attestor` | M5 — *"no attestor was involved"* |
| `test_a_principal_is_never_the_attestor_of_a_refusal` | ED-018, carried forward |
| `test_only_the_unavailable_kernel_may_name_no_check` | §11.9 is the sole checkless refusal |
| `test_an_unavailable_permission_system_is_refused_at_a3` | §11.1 |
| `test_an_unavailable_provider_is_refused_at_a7` | §11.6 |
| `test_a_missing_worker_is_refused_at_a1_or_a6` ×2 | §11.5 |
| `test_a_refusal_is_not_a_judgment_request` | §7.5 — *"not a thousand queue items"* |
| `test_a_thousand_identical_refusals_collapse_to_one` | §7.5 — *"a thousand refusals are one state"* |
| `test_it_depends_on_component_seven_and_nothing_else` | Amendment M5 |
| `test_it_imports_the_question_and_not_the_attestation` | M5 — the enum only, never the type |
| `test_it_is_named_kernel_refusal_and_not_refusal` | Roadmap §2 C8 terminology |
| `test_it_composes_no_founder_facing_sentence` | C20 owns every utterance |
| `test_it_cannot_execute_or_authorize_work` · `test_it_reads_no_ambient_time` | Acceptance criteria |
| `test_a_refusal_cannot_be_mutated` ×5 | Immutability |
| `test_components_one_to_seven_are_untouched` | Milestone integrity |

---

## 7 · Byte-identical confirmation — Components C1–C7

Verified by blob SHA-1 in both trees, not by inspection. `git diff --stat kalpavriksha-s1-c7.0 ac5e399` limited to these seven paths returns **empty**.

| Module | Component | Blob SHA-1 at `c7.0` and `c8.0` | |
|---|---|---|---|
| `clock.py` | C1 | `220f96284fc12c711952dae10974dd4e231ffe97` | **IDENTICAL** |
| `principal.py` | C2 | `2e8c756ce894d12a2a9a45ddb90fbc6d78557eaa` | **IDENTICAL** |
| `execution_context.py` | C3 | `acafb3f9e3f2bfd13cf3bb020d8109704bdbddb9` | **IDENTICAL** |
| `warrant.py` | C4 | `e1136e95b90a1f0d6033020f974852884e0efe63` | **IDENTICAL** |
| `receipt.py` | C5 | `697da25efc57f742eb4879b6ef90c2c1d86b77fb` | **IDENTICAL** |
| `consequence.py` | C6 | `d496734a0e3c5e1677c6f60e168faf28371a552d` | **IDENTICAL** |
| `attestation.py` | C7 | `7b7e6dcf51a07af622f2356129a75bdf1e259faa` | **IDENTICAL** |

`Warrant` remains byte-compatible with `kalpavriksha-s1-c3.0`, per the frozen C7 integration decision. The **entire** tree delta from `c7.0` to `c8.0` is three files: `refusal.py` (new), `test_foundation_refusal.py` (new), `foundation/__init__.py` (exports only).

---

## 8 · Invariants, all enforced structurally

Each raises `InvalidKernelRefusal` at construction. None is a convention or a docstring promise.

| # | Invariant | Grounding |
|---|---|---|
| 1 | The reason must be a `RefusalReason` | closed vocabulary |
| 2 | Each reason may name **only** the check that produces it | §7.2 pairs each K-reason with one check; §11.1→A3, §11.5→A1/A6, §11.6→A7 |
| 3 | A K-check refusal has **no** attestor | M5 — *"a refusal from K1 has no attestor"* |
| 4 | An attestation refusal names §7.3's **canonical** attestor, exactly | §7.3 attestor identity; ED-018 |
| 5 | Only `KERNEL_UNAVAILABLE` may name no check at all | §11.9 — refused before any check ran |
| 6 | `remediable` must be a real `bool`, and has no default | §7.5's third required part |
| 7 | `detail` is required and non-blank | §7.5 — the sentence that replaces the stack trace |
| 8 | Frozen, hashable, deterministic `as_dict()` | every component since C3 |

---

## 9 · Engineering decisions

**ED-024 · `attestor` is optional, and `None` is *enforced* for K-checks.** M5 established it cannot be required; C8 goes further and refuses a K-check refusal that carries one. §7.2's three are the Kernel's own domain, and a K1 refusal naming `mission_control` is a false attribution in a record kept forever.

**ED-025 · Two attestation reasons, not eight.** M5's *"A1–A8, each refusable"* says which checks can produce a refusal; `failed_check` carries which. Duplicating the eight questions into `RefusalReason` would create a second vocabulary for §7.3 and let the two fields disagree. The family is represented by its two modes — absent and refused — which is what §7.3's *"treated as absent"* collapses the space to.

**ED-026 · `remediable` is explicit, required, and never derived.** `PERMISSION_SYSTEM_UNAVAILABLE` is remediable if the system can be restarted and not if the grant does not exist. Deriving it would be the Kernel deciding something it was told — the shape of re-deriving a verdict §7.3 forbids. No default, so the most consequential bit cannot be set by omission.

**ED-027 · No timestamp and no id.** The ledger records when; a second clock reading is a second answer to one question. It keeps C8 free of a Clock dependency, as M4 reasoned for C10. More importantly, an id is the first field of a queue item, and §7.5 forbids the queue.

**ED-028 · `KernelCheck` is a new closed vocabulary, and `failed_check` is a union.** §7.2's three and §7.3's eight are owned by different authorities; flattening them would either duplicate `AttestationQuestion` or invent a name for the union.

**ED-029 · `as_dict()` emits two derived keys.** `family` and `failed_check_kind` are projected, not stored, so an audit reading the record in fifteen years without these enum classes can still tell `k2_override_state` from `permission`.

---

## 10 · Terminology

| Name | Constitution §17? | In codebase before C8? | |
|---|---|---|---|
| `KernelRefusal` | No | No | ✅ correctly qualified — `BrokerRefusal` and `PlanRefusal` exist; a bare `Refusal` would be the third |
| `RefusalReason` | No | No | ✅ audited by Amendment §6 |
| `KernelCheck` | No | No | ✅ **new name, not in Amendment §6's list of 14.** Audited here: zero occurrences in `src/` or `tests/`, absent from §17. Grounded in the amendment's own family label, *"Kernel checks"* |
| `RefusalFamily` | No | No | ✅ **new name.** Same audit, same result |

`test_it_is_named_kernel_refusal_and_not_refusal` asserts the module exports no bare `Refusal`, so the collision cannot reappear via a later convenience alias.

---

## 11 · Risks

| # | Risk | Severity | Status |
|---|---|---|---|
| **R13** | **C17's V1–V5 admission refusals have no reason in this enum.** Roadmap §2 C8 names C17 a consumer, but `RefusalReason` covers the *Kernel's* refusals — not the Objective Engine's admission validations. | Medium | **New.** Not a blocker for C8 or C15. Decide at C17's brief |
| **R14** | **`_PERMITTED_CHECKS` freezes §11.1 / §11.5 / §11.6's check placements in code.** | Low | **New, accepted** — same posture as R12; a silent reassignment should break loudly |
| **R1** | `Objective`/`Mission` ADR unratified — blocks C11, C15, C17 | **Critical** | Unchanged. **Now the binding constraint on 12 Aug** |
| **R3** | MB032–039 uncommitted; collides with C16 | **Critical** | Unchanged. 149 dirty entries |
| **R7** | `launcher/boot.py` ambient time | Medium | Unchanged. Absent at the tag |
| **R11** | Roadmap dependency errors | High | **Mitigated for C8** — M5 caught it before code |

### 11.1 The risk this report exists to surface

**R1 is now the binding constraint on 12 Aug.** With C8 green, the Kernel's remaining prerequisites are C9, C10, C12, C13, C14 — all unblocked — and **C11, which Amendment M6 rates critical and blocked.** C15 depends on C11. Under M6 option (c), Sprint 1 stalls with the Kernel unbuilt.

That decision is the founder's. M6 §10 already carries the recommendation. **Flagged, not acted on.**

---

## 12 · Rule 000 assessment

> *Never compromise architectural integrity for speed.*

**Passes.** Nothing was traded for the date. The refusal contract §7.5 states in one sentence now has a type in which all three of its parts are structurally enforced.

The cheaper design was available and was declined: a single `ATTESTATION_FAILED` reason with a free-text field would have met the roadmap's ~35-test estimate, and would have made *"the ledger is down"* and *"autonomy is suspended"* indistinguishable in a record §7.5 requires to be kept.

Nothing unrelated was touched. All seven prior components are byte-identical by SHA-1.

---

## 13 · Scope discipline

| Constraint | Observed |
|---|---|
| Only C8 staged | ✅ 3 files; the working directory's 149 dirty entries untouched |
| No roadmap edits | ✅ neither roadmap file modified |
| No opportunistic fixes | ✅ 21 Ruff findings and 49 working-directory failures diagnosed and left alone |
| No refactor of prior components | ✅ C1–C7 byte-identical by SHA-1 |
| No future roadmap work | ✅ C9 not started |
| Tag only after Rule 001 passed | ✅ tag did not exist during the commit-verification run |

---

*Milestone health report. All figures measured in clean isolated worktrees at commit `ac5e399` and tag `kalpavriksha-s1-c8.0`. All temporary worktrees removed.*
