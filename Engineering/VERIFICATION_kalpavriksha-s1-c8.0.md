# Verification Report — `kalpavriksha-s1-c8.0`

**Gate applied:** Quality Gate Rule 001
**Verdict:** **GREEN**
**Date:** 2026-08-05

---

## 1 · Subject

| | |
|---|---|
| Tag | `kalpavriksha-s1-c8.0` (annotated) |
| Commit | `ac5e399` |
| Milestone | Sprint 1, Component 8 — Kernel Refusal |
| Previous milestone | `kalpavriksha-s1-c7.0` → `14b0e3a`, unchanged |

---

## 2 · Rule 001 criteria

| Criterion | Method | Result |
|---|---|---|
| Clean checkout | `git worktree add --detach` into the scratchpad, outside the project directory | ✅ |
| **Commit verified before the tag existed** | Worktree created at `ac5e399`; `git tag -l kalpavriksha-s1-c8.0` returned **0** at that moment | ✅ |
| **Tag verified afterwards** | Second, independent worktree created at the tag after it was cut | ✅ |
| PYTHONPATH pinned | `PYTHONPATH=<worktree>/src` on every invocation | ✅ |
| Source isolation confirmed | §2.1 below | ✅ |
| Tests executed there | Full suite, both worktrees | ✅ |
| Architecture guards executed there | 6 modules, both worktrees | ✅ |
| Constitutional guards executed there | 22 C8 guards, both worktrees | ✅ |
| Verification report generated | This document | ✅ |

**Order of operations, stated because Rule 001 turns on it:** the commit was verified in a clean worktree *before* the tag was created, the tag was created only after that run passed, and the tag was then verified in a *separate* worktree. At no point was a tag created ahead of its evidence.

### 2.1 Source isolation

Both worktrees were probed before any test ran:

```
master_agent  -> <worktree>\src\master_agent\__init__.py
refusal.py    -> <worktree>\src\master_agent\foundation\refusal.py
ISOLATION CONFIRMED: no import resolves to D:/MasterAgent/src
```

The probe asserts the worktree path is present in `__file__` and raises otherwise, so a silent fallback to the project directory or to an installed distribution fails the run rather than passing it quietly. Both worktrees reported `git status --porcelain` empty.

---

## 3 · Test reconciliation

### 3.1 At the commit, before the tag existed

```
1966 passed, 1 skipped in 143.78s
```

### 3.2 At the tag

```
1966 passed, 1 skipped in 142.91s
```

**Identical. Zero failures in both.**

| | |
|---|---|
| Passed | **1,966** |
| Failed | **0** |
| Skipped | 1 |

**Reconciliation:** 1,858 at `kalpavriksha-s1-c7.0` + 108 added by Component 8 = **1,966**. Exact.

### 3.3 Cumulative foundation, by component

Measured at the tag: **419 passed** across the eight foundation test modules.

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

Foundation total: **419 tests across eight components.** The remaining 1,547 are the pre-existing suite, unchanged.

### 3.4 Working directory — information only, not evidence

```
4045 passed, 49 failed, 1 skipped
```

Reconciliation: 3,937 before Component 8 + 108 = **4,045**, and the failure count is **unchanged at 49**. All 49 are the MB032–039 uncommitted work (R3) plus the `launcher/boot.py` ambient-time true positive (R7), and every one is **absent at the tag** — which is precisely why Rule 001 refuses working-directory evidence.

---

## 4 · Architecture guards

**6 modules · 215 passed · 1 skipped · 0 failed.** Identical at the commit and at the tag.

```
test_browser_constitution_compliance.py   test_persistence_architecture.py
test_dashboard_architecture.py            test_runtime_approval_boundary.py
test_mission_control_architecture.py      test_runtime_architecture.py
```

> **Note on the module count.** The C7 report cited 12 guard modules run against the *working directory*. Six of those — including `test_missions_architecture.py` and `test_planner_architecture.py` — are files of the uncommitted MB032–039 work and **do not exist at any green tag**. Six is the correct count at `c8.0`, and it was also the correct count at `c7.0`; the difference is what the clean checkout contains, not a reduction in coverage. The four `test_missions_architecture.py` failures reported in the working directory therefore have no counterpart here.

### 4.1 Component 8 constitutional guards, named

**22 passed** at the commit and at the tag.

| Guard | Protects | |
|---|---|---|
| `test_there_are_exactly_three_kernel_checks` | §7.2 — *"exactly three"* | **PASSED** |
| `test_the_kernel_check_vocabulary_is_closed` | A fourth Kernel-owned check is constitutional, not code | **PASSED** |
| `test_a_kernel_check_is_not_an_attestation_question` | §7.2 and §7.3 vocabularies never overlap | **PASSED** |
| `test_every_reason_belongs_to_exactly_one_family` | Amendment M5's three families | **PASSED** |
| `test_each_of_the_three_kernel_checks_is_representable` | §7.5 — an unrepresentable refusal is unrecordable | **PASSED** |
| `test_a_degraded_network_is_not_a_refusal_reason` | §11.7 — *"the Kernel decides nothing here"* | **PASSED** |
| `test_learning_unavailable_is_not_a_refusal_reason` | §11.4 — the only "proceed" | **PASSED** |
| `test_an_attestation_refusal_requires_the_canonical_attestor` (×8) | §7.3 attestor identity, every question | **PASSED** |
| `test_an_attestation_refusal_may_not_omit_the_attestor` (×8) | §7.5 — a refusal names the attestor | **PASSED** |
| `test_a_kernel_check_refusal_has_no_attestor` | M5 — *"no attestor was involved"* | **PASSED** |
| `test_a_principal_is_never_the_attestor_of_a_refusal` | ED-018, carried forward | **PASSED** |
| `test_only_the_unavailable_kernel_may_name_no_check` | §11.9 is the sole checkless refusal | **PASSED** |
| `test_an_unavailable_permission_system_is_refused_at_a3` | §11.1 | **PASSED** |
| `test_an_unavailable_provider_is_refused_at_a7` | §11.6 | **PASSED** |
| `test_a_missing_worker_is_refused_at_a1_or_a6` (×2) | §11.5 | **PASSED** |
| `test_a_refusal_is_not_a_judgment_request` | §7.5 — *"not a thousand queue items"* | **PASSED** |
| `test_a_thousand_identical_refusals_collapse_to_one` | §7.5 — *"a thousand refusals are one state"* | **PASSED** |
| `test_it_depends_on_component_seven_and_nothing_else` | Amendment M5 | **PASSED** |
| `test_it_imports_the_question_and_not_the_attestation` | M5 — the enum only, never the type | **PASSED** |
| `test_it_is_named_kernel_refusal_and_not_refusal` | Roadmap §2 C8 terminology | **PASSED** |
| `test_it_composes_no_founder_facing_sentence` | C20 owns every utterance | **PASSED** |
| `test_it_cannot_execute_or_authorize_work` | Acceptance criterion | **PASSED** |
| `test_it_reads_no_ambient_time` · `test_it_has_no_dependency_on_the_clock` | Clock discipline | **PASSED** |
| `test_a_refusal_cannot_be_mutated` (×5) | Immutability | **PASSED** |
| `test_components_one_to_seven_are_untouched` | Milestone integrity | **PASSED** |

---

## 5 · Ruff

| Scope | At `c7.0` | At `c8.0` | |
|---|---|---|---|
| **C8's three files** | — | **All checks passed** | ✅ |
| Repo-wide `src/` + `tests/` | **21 findings** | **21 findings** | unchanged |

**Component 8 introduced zero Ruff findings.** The 21 are pre-existing and distributed across `test_memory.py` (5), `mission_manager/mission.py` (3), `permissions/permission_system.py` (2), `executor/executor.py` (2), `cli.py` (2) and seven other files — none of which C8 touches. Left alone, per the brief's prohibition on opportunistic fixes.

Project configuration: `[tool.ruff]`, `line-length = 100`, `target-version = "py311"`. C8's longest line is 84 characters.

---

## 6 · Components 1–7 unchanged

Verified by SHA-1 of each blob in both trees, not by inspection:

| Module | Blob SHA-1 | |
|---|---|---|
| `clock.py` | `220f9628…` | **IDENTICAL** |
| `principal.py` | `2e8c756c…` | **IDENTICAL** |
| `execution_context.py` | `acafb3f9…` | **IDENTICAL** |
| `warrant.py` | `e1136e95…` | **IDENTICAL** |
| `receipt.py` | `697da25e…` | **IDENTICAL** |
| `consequence.py` | `d496734a…` | **IDENTICAL** |
| `attestation.py` | `7b7e6dcf…` | **IDENTICAL** |

`git diff --stat kalpavriksha-s1-c7.0 ac5e399` limited to those seven paths returns **empty**. `Warrant` in particular remains byte-compatible with `kalpavriksha-s1-c3.0`, per the frozen C7 integration decision. **Milestone integrity preserved across all eight tags.**

---

## 7 · What changed

The entire tree delta from `c7.0` to `c8.0`:

| File | |
|---|---|
| `src/master_agent/foundation/refusal.py` | new, 379 lines |
| `src/master_agent/foundation/__init__.py` | modified — exports only, +12 |
| `tests/test_foundation_refusal.py` | new, 799 lines |

**1,190 insertions, 0 deletions, three files.** Nothing else in the repository differs between the two tags.

Against the roadmap's estimate of ~130 source lines and ~35 tests: **107 executable lines and 108 tests.** Source came in **under** estimate; the test overrun is Amendment 001 M5's widening of the reason set from one family to three, each exhaustively tested across all eight attestation questions. Same shape of overrun as C7, and the same cause — enforcing at construction what the roadmap assumed would be checked downstream.

### 7.1 Commit scope

Three files, matching the shape of all six prior milestone commits (C3 through C7 each committed exactly module + tests + `__init__.py`). **No Engineering document was committed**, consistent with every prior milestone: `Engineering/QUALITY_GATE_RULES.md` is the only tracked file in that directory, and all six prior verification reports remain untracked. This report and `HEALTH_C8.md` follow that practice. No roadmap file was edited. No unrelated file was staged, and the working directory's 149 dirty entries were left exactly as found.

---

## 8 · Engineering decisions

Recorded in full at `Engineering/HEALTH_C8.md` §5. In summary:

**ED-024 · `attestor` is optional, and `None` is *enforced* for K-checks.** M5 established it cannot be required; C8 goes further and refuses a K-check refusal that carries one. §7.2's three checks are the Kernel's own domain, and a K1 refusal naming `mission_control` is a false attribution in a record kept forever.

**ED-025 · Two attestation reasons, not eight.** M5's *"A1–A8, each refusable"* says which checks can produce a refusal; `failed_check` is the field that carries which. Duplicating the eight questions into `RefusalReason` would create a second vocabulary for §7.3 and let the two fields disagree. The family is represented by its two modes — absent and refused — which is what §7.3's *"treated as absent"* collapses the space to.

**ED-026 · `remediable` is explicit, required, and never derived.** `PERMISSION_SYSTEM_UNAVAILABLE` is remediable if the system can be restarted and not if the grant does not exist. Deriving it would be the Kernel deciding something it was told — the shape of re-deriving a verdict that §7.3 forbids. No default, so the most consequential bit cannot be set by omission.

**ED-027 · No timestamp and no id.** The ledger records when; a second clock reading is a second answer to one question. It also keeps C8 free of a Clock dependency, as M4 reasoned for C10. More importantly, an id is the first field of a queue item, and §7.5 forbids the queue.

**ED-028 · `KernelCheck` is a new closed vocabulary, and `failed_check` is a union.** §7.2's three and §7.3's eight are owned by different authorities; flattening them would either duplicate `AttestationQuestion` or invent a name for the union.

**ED-029 · `as_dict()` emits two derived keys.** `family` and `failed_check_kind` are projected, not stored, so an audit reading the record in fifteen years without these enum classes can still tell `k2_override_state` from `permission`.

---

## 9 · Risks

| # | Risk | Severity | Status |
|---|---|---|---|
| **R13** | **C17's V1–V5 admission refusals have no reason in this enum.** Roadmap §2 C8 names C17 a consumer, but `RefusalReason` covers the *Kernel's* refusals (§7.2, §7.3, §11) — not the Objective Engine's admission validations. C17 needs either a widening of a closed constitutional enum or its own qualified type. | Medium | **New.** Not a blocker for C8 or C15. **Decide at C17's brief** — designing it during C8 would be implementing future roadmap work |
| **R14** | **`_PERMITTED_CHECKS` freezes §11.1 / §11.5 / §11.6's check placements in code.** If the Permission System's answer moves off A3, every caller raises at construction. | Low | **New, accepted** — the same posture as R12. A silent reassignment of where a constitutional check lives should break loudly |
| **R1** | `Objective`/`Mission` ADR unratified — blocks C11, C15, C17 (Amendment M6) | **Critical** | Unchanged. **Now the binding constraint on the Founder Edition date**: every other Kernel prerequisite is unblocked |
| **R3** | MB032–039 uncommitted; collides with C16 | **Critical** | Unchanged. 149 dirty entries; window closes when C16 begins |
| **R7** | `launcher/boot.py` ambient time | Medium | Unchanged. Absent at the tag; must be resolved before that edit is committed |
| **R11** | Roadmap dependency errors (ED-018) | High | **Mitigated for C8** — Amendment 001 M5 caught C8's before code, and C8 was built to the amendment |

---

## 10 · Rule 000 assessment

> *Every engineering change must leave the repository more trustworthy than it was before the change.*

**Passes.** The refusal contract §7.5 states in one sentence — *"a refusal names the check that failed, the attestor, and whether it is remediable"* — now has a type in which all three parts are structurally enforced. A refusal that names the wrong check for its reason, invents an attestor for a check the Kernel owns, or cannot say what happened does not exist rather than being caught in review.

The cheaper design was available and was declined: a single `ATTESTATION_FAILED` reason with a free-text field would have met the roadmap's ~35-test estimate, and would have made *"the ledger is down"* and *"autonomy is suspended"* indistinguishable in a record §7.5 requires to be kept.

Nothing unrelated was touched. All seven prior components are byte-identical by SHA-1, and the tree delta from `c7.0` is exactly three files.

---

*Generated in clean checkouts of commit `ac5e399` and tag `kalpavriksha-s1-c8.0`, per Quality Gate Rule 001. All temporary worktrees removed; `git worktree list` reports only `D:/MasterAgent`.*
