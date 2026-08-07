# Independent Engineering Audit — Component C9: ExecutionRequest

**Type:** Audit only. **No source modified, no fixes applied, no formatting changed, no commit, no tag.**
**Date:** 2026-08-05
**Auditor:** Claude (temporary — Hermes unavailable)
**Subject:** `execution_request.py` · `test_foundation_execution_request.py` · `HEALTH_C9.md`
**Baseline:** working tree at `ac5e399` + untracked C9

---

## 0 · A disclosure that belongs at the top

**I am auditing my own implementation.** I wrote C9, wrote its tests, and wrote `HEALTH_C9.md`. An author auditing their own work cannot supply the independence this gate is meant to provide — the failure mode is not dishonesty, it is that the blind spots which produced a defect are the same ones that miss it.

To compensate I re-derived every claim from the frozen documents and **executed adversarial probes against the built object rather than reading the code for agreement**. Where the health report made a number claim, I re-measured it rather than citing it. That found one factual error in my own report (§3, I2) and two design weaknesses (I1, I3) that reading alone did not surface.

**This audit should still be re-run by Hermes when it is available.** Treat this as a defect-finding pass, not as the independent verification Rule 001 will eventually want.

---

## 1 · Executive Summary

> ### Verdict: **PASS WITH OBSERVATIONS**

C9 implements what Kernel Specification §4.3, §7, §14.1 and Roadmap Amendment 001 require. Both founder decisions — `principal_id: str` (M8) and the `PENDING_CONSEQUENCE_ENGINE` sentinel — are implemented exactly as frozen. The value object is immutable, pure, dependency-clean, and introduces zero Ruff violations. **No constitutional conflict was found**, so no `CONFLICT_C9.md` was produced.

**Six issues found. None blocks Rule 001. One is worth deciding before C13.**

| # | Issue | Class | Severity |
|---|---|---|---|
| **I1** | `as_dict()["consequence"]` is polymorphic (`str` \| `dict`); `PendingConsequenceEngine.as_dict()` is the only `as_dict()` in `foundation/` returning a non-dict | Engineering | **Medium** |
| **I2** | `HEALTH_C9.md` states `+14` lines to `__init__.py`; measured **+12** | Documentation | Low |
| **I3** | `test_the_action_classes_match_the_attestation_split` contains **zero references to `ActionClass`** — it re-tests C7 and would pass if C9's enum were deleted | Engineering | Low |
| **I4** | No test hashes a request carrying a real `Consequence` | Engineering | Low |
| **I5** | Field order deviates from Roadmap §2 C9's stated API order | Roadmap/Doc | Low |
| **I6** | The marker singleton is not enforced — `PendingConsequenceEngine()` yields a distinct but equal object | Engineering | Low |

**And one forward risk that is not a C9 defect but is the most consequential thing in this audit:**

> **R-A · `expected_effect` and `task_ref` have no carrier into `authorize()`.** Both are §4.3 Intent fields. Neither is in the frozen `Warrant` (C4), neither is in `ExecutionRequest` (C9), neither is Kernel-computed — and the **Planner is not one of §7.3's eight attestors**, so `expected_effect` has no attestation to ride in either. C15 needs it and nothing supplies it. **Architecture defect, High.**

---

## 2 · Verified Items

### 2.1 Constitutional correctness

| Requirement | Source | Verified | Method |
|---|---|---|---|
| Is the input half of `authorize(ExecutionRequest)` | §3.5 | ✅ | Field set maps to `Warrant`'s |
| `objective_id` present and non-empty | §7.2 K1 | ✅ | 5 parametrized rejections |
| The digest, **never** the payload | §4.3 | ✅ | `test_it_never_carries_the_payload` — asserts no `payload`, no `*_payload` |
| `action_class` selects the §7.4 set | §7.4 | ✅ | Closed enum, 2 members |
| Attestations carried as **objects** | §7.3 | ✅ | Type-checked at construction |
| Consequence **never null, never omitted, never partial** | **§14.1** | ✅ | Required field; `None` rejected; probe confirmed |
| Marker is the literal §14.1 names | §14.1 | ✅ | `as_dict() == "pending_consequence_engine"` |
| Carries no field §4.3 sources to the Kernel/attestor | §4.3 | ✅ | `test_it_holds_no_field_the_kernel_owns`, 15 names |
| `principal_id: str`, no `Principal` object | **M8, frozen** | ✅ | Import absent *and* field name asserted |
| No dependency on C2 | M8 | ✅ | Measured import set |
| No queue/judgment shape (VEDA 03 §7.5 posture) | VEDA 03 | ✅ | No id, no timestamp, no priority |
| Never speaks to the founder (C20 owns utterances) | VEDA 04 D2 | ✅ | No prose composed |

**On VEDA 01 and VEDA 04 specifically:** C9 is infrastructure beneath the founder-facing surface. VEDA 01's requirements (one gesture, no persuasion, honest uncertainty) and VEDA 04's (A1's receipt contract, D2's voice) place **no direct constraint** on this value object; they constrain the ledger, the Kernel and the dashboard. The one place VEDA 04 reaches C9 is **A1's quartet requirement**, which arrives via §14.1 and is satisfied. **No VEDA conflict found.**

### 2.2 Structural correctness — probed, not assumed

| Property | Result | Probe |
|---|---|---|
| Frozen dataclass | ✅ | `setattr` → `FrozenInstanceError` |
| Immutable collection | ✅ | `attestations.__setitem__` → `AttributeError` (tuple) |
| Hashable | ✅ | Verified **with** a real `Consequence` and with attestations — works, though untested (I4) |
| Deterministic construction | ✅ | No mutable defaults; `()` and `None` only |
| Deterministic serialisation | ✅ | Two equal requests → byte-identical JSON, with quartet and with marker |
| No execution behaviour | ✅ | Forbidden-verb scan over public surface |
| No authorization behaviour | ✅ | same; no method returns a decision |
| Value-object purity | ✅ | No runtime state, no I/O, no ambient time, no clock |
| Type confusion rejected | ✅ | `True` as `objective_id` → refused; `"local"` as `action_class` → refused; `list` as attestations → refused |

**One nuance worth recording:** `ActionClass` is a `str`-Enum, so `ActionClass.LOCAL == "local"` is `True`. The validator uses `isinstance`, not `==`, so a raw string is still refused. **Correct, and it is the kind of thing that is wrong in most codebases.**

### 2.3 Dependency correctness

```
execution_request  →  foundation.attestation   (Attestation, AttestationQuestion)
                   →  foundation.consequence   (Consequence)
```

**Exactly two internal imports. Nothing else.** Verified by AST, not by reading.

| Check | Result |
|---|---|
| No dependency drift | ✅ `test_it_depends_only_on_components_seven_and_six` asserts the exact set |
| No unnecessary imports | ✅ Every import is used: `Attestation`/`Consequence` for `isinstance` + annotation, `AttestationQuestion` for the dedup set, `Any`/`Enum`/`dataclass` structural |
| No circular dependencies | ✅ All nine foundation modules import standalone in a fresh interpreter; package imports cleanly, 34 exports |
| No `Principal` (M8) | ✅ Import absent, field is `principal_id` |
| No `Clock` | ✅ Import absent; no ambient-time call |
| No `Warrant` | ✅ Import absent — `ReversibilityClass` correctly left to A2's attestor |

**`AttestationQuestion` is imported but never annotated** — used only as the dedup set's element type. Legitimate, not dead.

### 2.4 Integration correctness — no previous component modified

`git diff` against tag `kalpavriksha-s1-c8.0`, limited to the eight prior foundation modules: **empty**. `clock.py` · `principal.py` · `execution_context.py` · `warrant.py` · `receipt.py` · `consequence.py` · `attestation.py` · `refusal.py` — **byte-identical**.

| Integrates with | How | Verified |
|---|---|---|
| **Warrant** (C4) | By *shape*, not by import. `objective_id`, `principal_id`, `capability`, `payload_digest` match `Warrant`'s names, types and non-empty invariants exactly | ✅ Compared field by field |
| **Consequence** (C6) | Typed field; `isinstance` accepted; `as_dict()` delegated | ✅ Probe: real quartet round-trips |
| **Attestation** (C7) | Tuple of objects; `question` used for dedup; `as_dict()` delegated | ✅ All 8 questions parametrized |
| **Receipt** (C5) | **No coupling, correctly.** A receipt is written after the fact; a request precedes authorization | ✅ No import, no reference |

**The only change outside C9's own files is `foundation/__init__.py`: 12 insertions, 0 deletions, exports only.**

### 2.5 Ruff — zero new violations, confirmed

| Scope | Result |
|---|---|
| `execution_request.py` | **All checks passed** |
| `test_foundation_execution_request.py` | **All checks passed** |
| `foundation/__init__.py` | **All checks passed** |
| Repo-wide `src/` + `tests/` | **150 findings — identical to the pre-C9 measurement** |
| Any repo-wide finding inside a C9 file | **None** (grep over the full concise output) |

**Confirmed: C9 introduces zero new Ruff violations.** Existing debt untouched, per instruction.

### 2.6 Test execution — re-run independently

| Scope | Result |
|---|---|
| C9 component tests | **102 passed, 0 failed** |
| Foundation suite | **520 passed, 1 failed** — the pre-existing `boot.py` ambient-time guard (R7) |
| Full suite | **4,147 passed · 49 failed · 1 skipped** |

Reconciliation: 419 (C1–C8) + 102 = **521** foundation tests. 4,045 + 102 = **4,147**. Failures unchanged at 49, none in a C9 file. **`HEALTH_C9.md`'s headline numbers are accurate.**

---

## 3 · Issues Found

### I1 · `as_dict()` is polymorphic on `consequence` — **Medium · Engineering defect**

**Measured:**

```
type(request.as_dict()["consequence"])  with marker   →  str
type(request.as_dict()["consequence"])  with quartet  →  dict
PendingConsequenceEngine.as_dict()                    →  str
```

Every other `as_dict()` in `foundation/` — `Warrant`, `Receipt`, `Consequence`, `Cost`, `Attestation`, `KernelRefusal` — returns `dict[str, Any]`. `PendingConsequenceEngine.as_dict() -> str` is the sole exception, and it makes one key of `ExecutionRequest.as_dict()` union-typed.

**Why it matters, and why it is Medium rather than Low.** C13 Receipt Ledger is an **append-only permanent store**. A field whose type varies by state is harder to query, index and migrate years later — and §14.1's whole purpose is that the gap be legible in the permanent record. It is legible; it is just not uniformly shaped.

**In C9's defence:** §14.1 names the literal string `pending_consequence_engine`, so the *value* is exactly right. The issue is the *shape*, and it is a genuine design trade-off rather than an error. The alternative — `{"pending": "pending_consequence_engine"}` or `{"state": "pending_consequence_engine"}` — keeps the shape uniform at the cost of one level of nesting.

**Not fixed.** This is an audit, and it is a design decision that belongs to the founder or to C13's brief.

### I2 · `HEALTH_C9.md` overstates the `__init__.py` insertion count — **Low · Documentation defect**

`HEALTH_C9.md` §1 states `foundation/__init__.py | modified — exports only | +14`.

**Measured:** `git diff --numstat kalpavriksha-s1-c8.0` reports **12 insertions, 0 deletions**. The correct breakdown is 7 import lines + 5 `__all__` entries = 12.

The adjacent claim — *"five names added"* — is correct.

**Why a Low-severity number matters here:** C8's verification report cited exact insertion counts as evidence, and the commit brief will do the same. A report that is right about 102 tests and wrong about 12 lines invites a reader to check nothing. Every other figure in `HEALTH_C9.md` was re-measured in this audit and is accurate.

### I3 · A C9 test that tests no C9 code — **Low · Engineering defect (test quality)**

```python
def test_the_action_classes_match_the_attestation_split() -> None:
    intelligence_only = {q for q in AttestationQuestion if q.is_intelligence_only}
    assert intelligence_only == {AttestationQuestion.PROVIDER,
                                 AttestationQuestion.ADMISSION}
```

**Measured: zero references to `ActionClass` in its body**, despite the name. It asserts a property of C7's enum and would pass unchanged if `ActionClass` were deleted from the codebase.

Its intent — documenting that C9 deliberately does *not* restate §7.4's mapping — is legitimate and is recorded as R15. But a test named for C9 that cannot fail on a C9 change is **coverage that reads as protection and is not**. Either rename it to state that it guards C7's ownership, or make it assert the relationship (e.g. that `ActionClass` has no member naming a question).

### I4 · Hashing with a real `Consequence` is untested — **Low · Engineering defect (test gap)**

The suite contains two `hash(...)` assertions: one on the marker, one on a request whose consequence is the marker. **No test hashes a request carrying a real `Consequence`** — which is the case that depends on `Consequence` → `Cost` → `Decimal` all being hashable.

**Probed manually: it works.** So this is a coverage gap, not a defect. It is worth closing because it is the one hashability path that depends on a *chain* of other components staying hashable.

### I5 · Field order deviates from the roadmap's stated API — **Low · Roadmap/Documentation defect**

Roadmap §2 C9: `ExecutionRequest (frozen: objective_id, principal, capability, payload_digest, action_class, target_ref, attestations, consequence)` — `consequence` **last**.

Implemented: `objective_id, principal_id, capability, payload_digest, action_class, consequence, target_ref, attestations` — `consequence` **sixth**.

**The deviation is forced, not chosen.** The founder froze `consequence` as required; Python requires non-defaulted fields before defaulted ones; `target_ref` and `attestations` have defaults. The roadmap's order is unimplementable under the frozen decision.

**Mitigating:** positional construction in the roadmap's order fails loudly — `consequence` would receive `target_ref`'s value and raise `InvalidExecutionRequest`. No silent misbinding is possible.

**Neither document was amended** — that is not an auditor's act.

### I6 · The marker singleton is not enforced — **Low · Engineering defect**

```
PendingConsequenceEngine() == PENDING_CONSEQUENCE_ENGINE   →  True
PendingConsequenceEngine() is PENDING_CONSEQUENCE_ENGINE   →  False
```

The class docstring says *"Use the module-level `PENDING_CONSEQUENCE_ENGINE` rather than constructing one"*, and nothing enforces it.

**C9 itself is safe** — `is_consequence_pending` uses `isinstance`, and `_validate_consequence` uses `isinstance`. Equality and hashing behave correctly, so a second instance is functionally interchangeable.

**The risk is downstream:** a future component writing `request.consequence is PENDING_CONSEQUENCE_ENGINE` would be correct for every request built the recommended way and silently wrong for one that was not. A `__new__` returning a cached instance, or `@lru_cache`, would close it.

---

## 4 · Risks

### Critical

**None.**

### High

**R-A · `expected_effect` and `task_ref` have no carrier into `authorize()` — Architecture defect**

Kernel Specification §4.3 lists both as Intent fields:

| Field | §4.3 Source |
|---|---|
| `task_ref` | Mission Control |
| `expected_effect` | **Planner** |

**Measured:**
- Absent from `ExecutionRequest` (C9) — it matches the roadmap's declared API, which omits them.
- Absent from the shipped `Warrant` (C4) — **0 occurrences**, and C4 is frozen at `c3.0`.
- Not Kernel-computed — the Kernel has no planner and no scheduler (§3.4).
- **The Planner is not one of §7.3's eight attestors.** The eight are Mission Control, Reversibility Registry, Permission System, Standing Rule Engine, Principal registry, Capability contract, and the Broker twice. So `expected_effect` cannot even arrive inside an attestation.

`task_ref` *could* ride in the A1 attestation's opaque `subject` — Mission Control is A1's attestor — but that is unspecified, not designed. `expected_effect` has no such route.

**Consequence:** C15 is required to mint an Intent carrying a field that no shipped or planned component supplies. It will be discovered mid-build on the sprint's largest component, under a 600-line ceiling, with C4 frozen.

**This is not a C9 defect.** C9 implements its declared API exactly. It is a gap between §4.3's Intent contents and the union of what C4 and C9 carry, and **C9 was the last moment it could be caught cheaply.**

**Recommendation:** resolve at C15's brief — or earlier, since it may require an amendment naming where these two fields enter. Do **not** modify C4.

### Medium

**R-B · I1's polymorphic serialisation reaches a permanent store at C13.** See §3 I1. Decide the shape before the ledger's write format is fixed, because an append-only store cannot be reshaped retroactively.

### Low

| # | Risk | Note |
|---|---|---|
| **R15** | §7.4's split is encoded across C7 (`is_intelligence_only`) and C9 (`ActionClass`) | Accepted. C9 deliberately does not restate it. But the test meant to guard this is I3 |
| **R16** | `PendingConsequenceEngine` must become unconstructable when B1 ships | Carried from `HEALTH_C9.md`. Not actionable in Sprint 1 |
| **R-C** | I6's unenforced singleton | Closes cheaply |
| **RUFF-GOV-01** | The `line-length = 100` setting is not enforced by the resolved rule set — C9 shipped a 103-char line that Ruff never flagged, caught only by manual measurement | Confirmed live during C9. Pre-existing governance gap |

### Defect classification summary

| Class | Count | Items |
|---|---|---|
| **Engineering defects** | 4 | I1, I3, I4, I6 |
| **Architecture defects** | 1 | R-A |
| **Roadmap defects** | 1 | I5 |
| **Documentation defects** | 1 | I2 |

---

## 5 · Rule 001 Readiness

> ### C9 is **READY** for Rule 001 verification.

| Criterion | Status |
|---|---|
| Implementation complete | ✅ |
| Tests pass | ✅ 102/102 |
| Full suite green relative to baseline | ✅ 4,147 passed; failures unchanged at 49, none in C9 |
| Ruff clean, no new debt | ✅ repo-wide 150 → 150 |
| Architecture guards | ✅ 215 passed (verified during implementation) |
| C1–C8 byte-identical | ✅ `git diff` vs `c8.0` empty across all eight |
| No circular imports | ✅ all nine modules import standalone |
| No constitutional conflict | ✅ none found |
| **Not yet committed / tagged / clean-checkout verified** | ⏳ **by design** — the commit brief covers this |

**No issue in §3 blocks Rule 001.** All six are observations; none changes behaviour under test, and I2 is a report correction rather than a code change.

**Two recommended before the commit brief:** correct I2 (a wrong number in the evidence document), and decide I1 (it becomes expensive at C13).

---

## 6 · Recommendations

| # | Recommendation | When | Owner |
|---|---|---|---|
| **1** | **Correct `HEALTH_C9.md` §1: `+14` → `+12`** | Before the commit brief | Engineering |
| **2** | **Decide I1** — keep `as_dict() -> str` for the marker, or wrap it so every `foundation` `as_dict()` returns a dict | Before **C13** | Founder / C13 brief |
| **3** | **Resolve R-A** — name where `expected_effect` and `task_ref` enter `authorize()` | Before **C15**; record now | **Founder** (may need an amendment) |
| **4** | Rename or strengthen I3's test so it can fail on a C9 change | With any C9 follow-up | Engineering |
| **5** | Add a hash test for a request carrying a real `Consequence` (I4) | With any C9 follow-up | Engineering |
| **6** | Enforce the marker singleton via cached `__new__` (I6) | Optional | Engineering |
| **7** | **Re-run this audit under Hermes** when available | Before treating C9 as independently verified | — |

**None of these was applied.** No source file, test file or document was modified by this audit.

---

## 7 · Verdict

> # PASS WITH OBSERVATIONS

C9 correctly and completely implements Kernel Specification §4.3, §7.3, §7.4 and §14.1, together with both frozen founder decisions. It is immutable, pure, dependency-clean and free of execution or authorization behaviour. It modifies no prior component — all eight are byte-identical to `kalpavriksha-s1-c8.0` — and it introduces zero Ruff violations.

**No constitutional conflict exists**, therefore no `CONFLICT_C9.md` was produced.

Six observations were found, four of them by adversarial probing rather than by reading. **None blocks Rule 001.** The most valuable finding is not a C9 defect at all: **`expected_effect` has no path into the Kernel**, and C9 was the last cheap moment to notice.

**The design decision I judged most at risk of being wrong turned out to be right.** C9 permits an *incomplete* request while forbidding an *ambiguous* one. I probed for a way this could let a malformed request through and did not find one: presence remains the Kernel's check per §7.3, and the refusal §7.5 requires to be recorded remains constructible.

**Standing caveat:** the author audited the author. §0.

---

*Audit conducted 2026-08-05 against the working tree at `ac5e399` plus untracked C9. Every numeric claim was re-measured rather than cited; structural claims were verified by executing adversarial probes against constructed objects and by AST inspection of the module's imports. No file was modified.*
