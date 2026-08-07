# Health Report — Sprint 1 Component 9: Execution Request

**Type:** Implementation health report. Working-directory evidence only.
**Date:** 2026-08-05
**Status:** Implementation complete. **Not committed, not tagged, no Rule 001 verification** — those follow under the commit brief.
**Predecessor:** `kalpavriksha-s1-c8.0`, GREEN

> Every figure below is **working-directory evidence and is not a milestone claim.** Rule 001 is unsatisfied by construction, and C9 is therefore **not green**.

---

## 0 · Grounding, and one documentation discrepancy

### 0.1 Grounded against the three authoritative documents

| Source | Bearing on C9 |
|---|---|
| **Kernel Specification §4.3** | The Intent's field set and, critically, each field's **Source** column |
| **Kernel Specification §3.5** | `authorize(ExecutionRequest) → Intent \| Refusal` — C9 is the input half |
| **Kernel Specification §7.3 / §7.4** | Attestation presence is the Kernel's check; `ActionClass` selects the set |
| **Kernel Specification §14.1** | `pending_consequence_engine` — *"never null, never omitted, never a partial quartet"* |
| **Roadmap v2 §2 C9** | Purpose, public API, the `Execution*` boundary requirement (R9) |
| **Amendment 001 M8** | `principal_id` vs `Principal` — **now frozen by founder decision** |

### 0.2 Amendment 002

**Recorded as instructed:** *Amendment 002 was referenced in the implementation brief but does not exist in the repository; implementation proceeded using the three authoritative documents* — Kernel Specification §4.3, Roadmap v2, and Amendment 001. A repository-wide search returned only `SPRING_1_IMPLEMENTATION_ROADMAP_v2_AMENDMENT_001.md`. Per founder direction, a non-existent document is not an authority and implementation was not blocked.

### 0.3 Conflict check

**No conflict found. No `CONFLICT_C9.md` produced.**

The two open items from `C9_IMPLEMENTATION_PRECHECK.md` were both closed by founder decision before code was written:

| # | Item | Resolution |
|---|---|---|
| **M8** | `principal: Principal` or `principal_id: str`? | **`principal_id: str`. Frozen.** C9 therefore has no dependency on C2 |
| **P3** | Is `consequence` optional, or does it carry §14.1's marker? | **Explicit sentinel `PENDING_CONSEQUENCE_ENGINE`.** Never `None`, never omitted |

Precheck item **N2** — Amendment §5's table says the `Attestation` type, §3 M8's prose says the enum only — was resolved as the precheck determined: **the type**, because §7.3 requires the Kernel to verify `attestor`, `subject` and `attested_at`, which are fields of the object. The roadmap's own C9 API lists `attestations`, corroborating.

Precheck item **P4** — §4.3 sources `payload_digest` and `action_class` to the Kernel, the roadmap to the request — was resolved as the precheck recommended: **the roadmap**, on three pieces of evidence (shipped `Warrant.payload_digest` is passed in; §4.4 says the digest *"is checked at `attempt()`"*; a Kernel that computed it would need the payload, which §4.3 forbids carrying). §4.3's Source column is read as where a value's authority originates, not which component assigns it. **Stated here so the reading is explicit rather than inherited.**

---

## 1 · What was built

| File | | Lines |
|---|---|---|
| `src/master_agent/foundation/execution_request.py` | new | 290 |
| `src/master_agent/foundation/__init__.py` | modified — **exports only** | +14 |
| `tests/test_foundation_execution_request.py` | new | 679 |

### 1.1 Public surface — 5 exported symbols

```
ActionClass                closed enum, 2 — local · intelligence  (§7.4)
PendingConsequenceEngine   frozen sentinel type
PENDING_CONSEQUENCE_ENGINE the module-level instance  (§14.1)
ExecutionRequest           frozen dataclass, 8 fields
InvalidExecutionRequest    ValueError, raised at construction
```

### 1.2 Fields, and where each is grounded

| Field | Type | §4.3 Source | Note |
|---|---|---|---|
| `objective_id` | `str` | **Request** | K1's anchor. Opaque — never resolved here |
| `principal_id` | `str` | Principal model | **Frozen M8.** Matches `Warrant.principal_id` |
| `capability` | `str` | Capability Registry | Qualified name |
| `payload_digest` | `str` | *(see §0.3 P4)* | The digest, **never** the payload |
| `action_class` | `ActionClass` | *(see §0.3 P4)* | Selects the §7.4 set |
| `consequence` | `Consequence \| PendingConsequenceEngine` | Consequence Engine | **Required. Never `None`** (§14.1) |
| `target_ref` | `str \| None` | **Request** | §4.3's *"where meaningful"* |
| `attestations` | `tuple[Attestation, ...]` | Various owners | May be empty; may be incomplete |

### 1.3 Fields deliberately absent

`warrant_id` · `reversibility_class` · `compensating_action` · `undo_window` · `consequence_ceiling` · `grant_ref` · `rule_ref` · `attempt_budget` · `issued_at` · `expires_at` · `sequence` · `decision_ref` · `expected_effect` · `task_ref`

§4.3 sources every one of these to the Kernel or to an attestor at mint. **A request carrying any of them would be the caller authorizing itself**, and the Kernel would have nothing left to decide. Enforced by `test_it_holds_no_field_the_kernel_owns`.

### 1.4 Size against estimate

| | Roadmap §2 C9 | Actual |
|---|---|---|
| Source | ~220 lines | **290 total / 49 executable** |
| Tests | ~50 | **102** |

**Executable source came in well under estimate at 49 lines**, because the invariants are narrow: four non-empty identifiers, one enum check, one consequence check, one `target_ref` check, and one dedup pass. The 290 total is 145 lines of docstring — heavier than usual, and deliberately so: R9 requires the eight-way `Execution*` boundary table, and §1.3's absence list needs its reasoning recorded where the next reader will find it.

**Test count is 2× estimate**, consistent with the calibration recorded in `ROADMAP_CONSISTENCY_STATUS.md` §6. The driver is the same as C7 and C8 — exhaustive parametrization. Four identifier fields × five bad values = 20 tests before anything else runs.

---

## 2 · Quality gates

| Gate | Result |
|---|---|
| Component tests pass | ✅ **102 passed, 0 failed** in 0.25s |
| Ruff clean | ✅ **All checks passed** on all three files |
| Repo-wide Ruff unchanged | ✅ **150 before C9, 150 after** — zero introduced |
| Architecture guards | ✅ **215 passed, 1 skipped, 0 failed** (6 modules) |
| C9 constitutional guards | ✅ **14 passed** |
| Foundation suite | ✅ **520 passed**, 1 pre-existing failure (R7, `boot.py`) |
| Health report generated | ✅ this document |

### 2.1 Test reconciliation — exact in both directions

| | Before C9 | C9 | After |
|---|---|---|---|
| **Foundation suite** | 419 | +102 | **521** |
| **Full suite, passing** | 4,045 | +102 | **4,147** |
| **Full suite, failing** | 49 | **+0** | **49** |
| Skipped | 1 | +0 | 1 |

**C9 introduced zero new failures.**

| # | Component | Tag | Tests | Running total |
|---|---|---|---|---|
| C1 | Canonical Clock | `c1.1` | 28 | 28 |
| C2 | Principal | `c2.0` | 21 | 49 |
| C3 | Execution Context | `c2.0` | 33 | 82 |
| C4 | Constitutional Warrant | `c3.0` | 55 | 137 |
| C5 | Constitutional Receipt | `c4.0` | 59 | 196 |
| C6 | Consequence Quartet | `c5.0` | 49 | 245 |
| C7 | Attestation | `c7.0` | 66 | 311 |
| C8 | Kernel Refusal | `c8.0` | 108 | 419 |
| **C9** | **Execution Request** | *untagged* | **102** | **521** |

### 2.2 The 49 failures, unchanged

The documented pre-existing set: `boot.py` ambient time (R7, 1) plus MB032–039 uncommitted work (48). **None names `execution_request.py`; none is in `tests/test_foundation_execution_request.py`.** All 49 are absent at every green tag.

### 2.3 Two Ruff findings addressed during implementation, both by precedent

**`FURB157` — `Decimal("1")` in a test fixture.** Rewritten to `Decimal(1)`. This is the exact finding the C5 verification report §7 ruled on: each flagged site is *"checked individually before accepting — all six were integer-valued, where the rewrite is exact."* `Decimal("1")` is integer-valued, so the rewrite is exact. **Verified against the house convention rather than assumed:** `tests/test_foundation_consequence.py` uses `Decimal(1)` for its integer case (line 91) and keeps `Decimal("7200.00")` / `Decimal("0.10")` as strings for fractional values. C9 now matches.

**A 103-character line** in the module docstring's boundary table, over the configured `line-length = 100`. Reworded. **Note:** Ruff did **not** flag it — `E501` is not in the resolved rule set — which is a live instance of **RUFF-GOV-01**: the configured line length is not actually enforced by the configured rule set. Recorded, not fixed here.

Neither was an opportunistic fix; both are in files C9 created.

---

## 3 · Invariants, all enforced structurally

Each raises `InvalidExecutionRequest` at construction.

| # | Invariant | Grounding |
|---|---|---|
| 1 | `objective_id`, `principal_id`, `capability`, `payload_digest` non-empty | Matches shipped `Warrant.__post_init__` exactly — the object this becomes |
| 2 | `action_class` is an `ActionClass` | §7.4 selects the attestation set by it |
| 3 | `consequence` is a `Consequence` **or** the marker — **never `None`** | §14.1 verbatim |
| 4 | `attestations` is a `tuple` | A request cannot be edited after it is built |
| 5 | Every element is an `Attestation` | §7.3 operates on the object |
| 6 | **No two attestations answer one question** | §7.3 assigns each question exactly one attestor; the Kernel cannot choose between two answers |
| 7 | `target_ref` is `None` or non-blank | Absent and blank are different; a blank is an unanswered question wearing an answer |
| 8 | No `payload` field exists | §4.3 — *"The digest, never the payload"* |
| 9 | Frozen, hashable, deterministic `as_dict()` | Every component since C3 |

### 3.1 The invariant deliberately **not** enforced

**A request may be incomplete, and may carry no attestations at all.**

§7.3 makes the Kernel verify each attestation's *presence*. Had C9 refused construction without all eight, that presence check would be dead code — and worse, a caller could never build the object whose refusal §7.5 requires to be **recorded**. An unconstructable request produces an unrecordable refusal.

Likewise C9 does **not** check that an `INTELLIGENCE` request carries A7 and A8. That is §7.4's set selection, and it is the Kernel's judgment.

**Completeness is the Kernel's judgment; ambiguity is C9's invariant.** Enforced by `test_a_request_with_no_attestations_is_legal`, `test_a_partially_attested_request_is_legal`, and `test_the_request_does_not_check_the_attestation_set_for_this_class`.

This was flagged in `C9_IMPLEMENTATION_PRECHECK.md` §4.4 as *"the single most likely way C9 is built wrong."*

---

## 4 · Brief requirements, and the test enforcing each

| Requirement | Test |
|---|---|
| Immutable dataclass | `test_a_request_cannot_be_mutated` ×8 |
| Deterministic serialization | `test_serialisation_is_deterministic` · `test_serialisation_carries_every_field` |
| No wall-clock usage | `test_it_reads_no_ambient_time` · `test_it_has_no_dependency_on_the_clock` |
| No ambient state | `test_it_holds_no_runtime_state` |
| No Objective ownership | `test_it_owns_no_objective_and_no_mission` |
| No Mission ownership | same |
| No learning | `test_it_learns_nothing` |
| No execution capability | `test_it_cannot_execute_or_authorize_work` · `test_it_imports_nothing_that_could_act` |
| No authorization capability | same |
| **No `Principal` object** | `test_it_has_no_dependency_on_the_principal` — asserts the import is absent *and* that the field is `principal_id`, not `principal` |
| `principal_id: str` | same |
| Only frozen-spec fields | `test_it_holds_no_field_the_kernel_owns` · `test_it_never_carries_the_payload` |
| Dependencies | `test_it_depends_only_on_components_seven_and_six` |

---

## 5 · Engineering decisions

**ED-030 · `PENDING_CONSEQUENCE_ENGINE` is a frozen singleton type, not a string or `None`.**

Founder decision, implemented per §14.1's stated purpose — the marker *"makes the temporary gap explicit and greppable rather than an absence someone later mistakes for an oversight."*

A bare string `"pending_consequence_engine"` was rejected: `consequence: Consequence | str` would let any string through and the type would stop meaning anything. A frozen dataclass gives immutability, hashability and equality for free, and `isinstance` distinguishes it from a `Consequence` cleanly. It serialises to the literal §14.1 names, so the gap is greppable in a permanent record as well as in code.

`test_the_marker_is_not_falsy` exists because a marker that tested false would be indistinguishable from the absence it replaces.

**ED-031 · Two answers to one question are unconstructable.**

§7.3 assigns each question exactly one attestor. Two attestations for one question leaves the Kernel choosing which to verify — and choosing would be re-deriving a verdict, which §7.3 forbids. Making it unconstructable removes the choice, the same posture C7 used for attestor identity and C8 for check placement.

**Not the same as requiring completeness** (§3.1). Zero answers is legal; two is not.

**ED-032 · `target_ref` distinguishes absent from blank.**

§4.3 carries it *"where meaningful"*, so `None` is legitimate. A blank string is not: it is an unanswered question that looks answered, and it would serialise into a permanent record as an empty target. Same discipline as C7's non-empty `attestor`/`subject`.

**ED-033 · No dependency on `Warrant`, despite becoming one.**

The only plausible import is `ReversibilityClass`, and A2 — the Reversibility Registry — attests that. A caller asserting its own reversibility class would be answering a question §7.3 assigns to another component. `test_it_has_no_dependency_on_the_warrant_type` enforces it.

**ED-034 · `objective_id` is an opaque string.**

C9 carries the id and never the record. This is exactly why C9 is buildable while C11 is blocked: the `Objective`/`Mission` ADR governs the state vocabulary, and C9 touches none of it. `test_it_owns_no_objective_and_no_mission` keeps it that way.

---

## 6 · Terminology

| Name | Constitution §17? | In codebase before C9? | |
|---|---|---|---|
| `ExecutionRequest` | absent | 0 classes (2 docstring mentions) | ✅ clean |
| `ActionClass` | absent | 0 | ✅ clean |
| `InvalidExecutionRequest` | absent | 0 | ✅ clean |
| `PendingConsequenceEngine` | absent | 0 | ✅ **new name, audited here** |
| `PENDING_CONSEQUENCE_ENGINE` | absent | 0 | ✅ **new name.** The literal §14.1 specifies |

**Zero collisions**, all measured.

**`Execution*` boundary (Roadmap R9).** Eight types now share the prefix — the roadmap says five; the measured count was seven before C9 and is eight now, as recorded in `ROADMAP_CONSISTENCY_STATUS.md` §1.4. The module docstring carries the full eight-way table. The distinction that matters: **`ExecutionRequest` exists before anything is authorized; every other `Execution*` type exists because something already was.**

---

## 7 · Preservation

| | |
|---|---|
| C1–C8 source | **Untouched.** All eight modules, zero edits |
| `foundation/__init__.py` | Exports only — five names added, none removed |
| Anything outside `foundation/` | **Untouched** |
| Roadmap / amendment / specifications | **Untouched** |

`test_components_one_to_eight_are_untouched` asserts all eight prior surfaces still resolve. Byte-identity will be proven by blob SHA-1 under the commit brief.

---

## 8 · Risks

| # | Risk | Severity | Status |
|---|---|---|---|
| **R15** | **`ActionClass` and `AttestationQuestion.is_intelligence_only` encode §7.4 in two places.** C7 knows which questions are intelligence-only; C9 knows which classes exist. The Kernel joins them. If §7.4 ever changes, both must move together | Low | **New, accepted.** C9 deliberately does **not** restate the mapping — `test_the_action_classes_match_the_attestation_split` asserts C7 still owns it. Putting the set in C9 would be Kernel behaviour |
| **R16** | **`PendingConsequenceEngine` must disappear when B1 ships.** A Sprint 2 component that accepts the marker forever would make §14.1's *"from the moment B1 exists"* permanently untrue | Low | **New.** Not actionable in Sprint 1. B1's brief must state that the marker becomes unconstructable |
| **R1** | `Objective`/`Mission` ADR unratified — blocks C11, C15, C17 | **Critical** | Unchanged. **C9 is unaffected** (ED-034) |
| **R3** | MB032–039 uncommitted; collides with C16 | **Critical** | Unchanged |
| **R7** | `launcher/boot.py` ambient time | Medium | Unchanged. The one foundation-suite failure |
| **R9** | Eight `Execution*` types | Medium | **Mitigated for C9** — boundary table in the module docstring |
| **RUFF-GOV-01** | Ruff rule set unpinned; `line-length = 100` is configured but not enforced | Medium | **Confirmed live** during this component — §2.3 |

---

## 9 · Rule 000 assessment

> *Never compromise architectural integrity for speed.*

**Passes.** The Kernel's input contract now has a type in which the request cannot be ambiguous — no blank identifier, no null quartet, no two answers to one question — while remaining free to be *incomplete*, which is what keeps §7.3's presence check meaningful and §7.5's refusal recordable.

Two shortcuts were available and declined. Making `consequence` optional would have matched the roadmap's wording and broken §14.1's explicit *"never null"*. Validating the §7.4 attestation set here would have looked thorough and would have been Kernel behaviour in a value object — the exact boundary this brief drew.

Nothing unrelated was touched. All eight prior components are unmodified, and the repo-wide Ruff count is identical before and after.

---

## 10 · What was not done, deliberately

Per this brief: **no commit, no tag, no Rule 001 verification.** No clean-checkout run — every figure here is working-directory evidence and **C9 is not green**. No Kernel behaviour, no execution, no orchestration, no authorization. No roadmap or specification edits. The 49 pre-existing failures and the 150 repo-wide Ruff findings were left exactly as found. C10 was not started.

**STOP.**

---

*Implementation health report. Working directory at 2026-08-05, on `main` at `ac5e399`, uncommitted. All figures measured directly from the source and the test suite.*
