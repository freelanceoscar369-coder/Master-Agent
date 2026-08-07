# Health Report — Sprint 1 Component 10: AttemptToken

**Type:** Implementation health report. Working-directory evidence only.
**Date:** 2026-08-05
**Status:** Implementation complete. **Not committed, not tagged, no Rule 001 verification** — those follow under the commit brief.

> Figures below are working-directory evidence and are **not** a milestone claim. C10 is **not green**.

---

## 0 · Grounding

| Source | Bearing on C10 |
|---|---|
| **Kernel Spec §3.5** | `attempt(intent_id) → AttemptToken \| Refusal` — refuses when *"expired, cancelled, settled, or out of attempt budget"* |
| **Kernel Spec §8.5** | Attempt budgets set at mint from the capability's class, *"never by the retry loop"*. `irreversible` = 1 |
| **Kernel Spec §8.6** | *"The Kernel provides the key — `(intent_id, attempt_seq)`."* This is the token's purpose |
| **Kernel Spec §8.4** | An `irreversible` action is never automatically retried — a rule that belongs to the Kernel, not to this value |
| **Roadmap v2 §2 C10** | Public API: `AttemptToken (frozen: warrant_id, attempt_seq, opened_at)` · `InvalidAttemptToken` |
| **Amendment 001 M4** | **Corrects the roadmap: C10 depends on nothing.** Not the Warrant, *"not even the Clock"* |
| **Objective Engine Spec §13.1** | The `Warrant` / `intent_id` naming record — §5 below |

**No conflict found. No `CONFLICT_C10.md` produced.**

Amendment M4 supersedes Roadmap §2 C10's declared `C4 Warrant` dependency. C10 was built to the amendment: §3.5's operation takes an **id**, and the roadmap's own public API is a string, an int and a timestamp. The module imports nothing from `master_agent` at all.

---

## 1 · What was built

| File | | Lines |
|---|---|---|
| `src/master_agent/foundation/attempt_token.py` | new | 173 |
| `tests/test_foundation_attempt_token.py` | new | 394 |
| `src/master_agent/foundation/__init__.py` | modified — **exports only** | +9 |

### 1.1 Public surface — 3 exported symbols

```
AttemptToken          frozen dataclass — warrant_id, attempt_seq, opened_at
InvalidAttemptToken   ValueError, raised at construction
FIRST_ATTEMPT         the constant 1 — there is no attempt zero (§8.5)
```

### 1.2 Size against estimate

| | Roadmap §2 C10 | Actual |
|---|---|---|
| Source | ~120 lines | **173 total · 28 AST statements** |
| Tests | ~35 | **65** |

The implementation is genuinely small — 28 statements. The 173 total is documentation: §8's rules about what a token must *not* carry need recording next to the type, because every one of them is a field someone will eventually propose adding.

Test count is ~1.9× estimate, consistent with the calibration in `ROADMAP_CONSISTENCY_STATUS.md` §6. Driver is parametrization: 4 bad `warrant_id` types + 3 blanks, 4 non-integer sequences, 2 booleans, 3 negatives, 5 valid sequences, 3 bad datetimes.

---

## 2 · Invariants — all enforced structurally

Every one raises `InvalidAttemptToken` at construction. None is a documented convention.

| # | Invariant | Grounding | Test |
|---|---|---|---|
| 1 | `warrant_id` is a non-empty string | Identifier discipline, C3–C9 | `test_a_blank_warrant_id_is_refused` ×3 · `test_a_non_string_warrant_id_is_refused` ×4 |
| 2 | `attempt_seq` is an integer | Roadmap API | `test_a_non_integer_sequence_is_refused` ×4 |
| 3 | **`attempt_seq` rejects `bool`** | `bool` subclasses `int`; `True` would otherwise pass as attempt 1 | `test_a_boolean_sequence_is_refused` ×2 |
| 4 | `attempt_seq ≥ 1` — there is no attempt zero | §8.5 — a budget of 1 means one attempt and no second | `test_attempt_zero_is_refused` · `test_a_negative_sequence_is_refused` ×3 |
| 5 | `opened_at` is a datetime | Clock discipline | `test_a_non_datetime_is_refused` ×3 |
| 6 | `opened_at` is timezone-aware, normalised to UTC | Clock discipline, C1–C9 | `test_a_naive_timestamp_is_refused` · `test_timestamps_are_normalised_to_utc` |
| 7 | Frozen, hashable, deterministic `as_dict()` | Every component since C3 | 4 immutability + 4 value-semantics + 5 serialisation tests |

### 2.1 The invariants expressed as *absences* — guarded by test

§8 is mostly a list of things a retry loop must not decide for itself. Each is enforced here by a guard asserting the field does not exist:

| Absent | Why | Test |
|---|---|---|
| **Attempt budget** | §8.5 — set at mint from the capability's class, *"never by the retry loop."* A token that knew its own budget is a retry loop one field away from enforcing its own policy | `test_it_carries_no_budget` |
| **Retry policy / reversibility** | §8.4 is *"the most important clause in this section"* and belongs to the Kernel and the Reversibility Registry, never to the thing being retried | `test_it_carries_no_retry_policy` |
| **Expiry / deadline** | The validity window is the Warrant's. A token is opened inside one the Kernel has already confirmed live | `test_it_carries_no_expiry` |
| **Payload** | §4.3 — the digest, never the payload | `test_it_carries_no_payload` |
| **Runtime state** | A token records that an attempt opened, never how it went | `test_it_holds_no_runtime_state` |
| **Any `master_agent` import** | M4 | `test_it_imports_nothing_from_master_agent_at_all` |

**`test_it_has_exactly_three_fields`** pins the field list to Roadmap §2 C10 verbatim, so a fourth field cannot be added without the test naming it.

---

## 3 · Quality gates

| Gate | Result |
|---|---|
| Component tests pass | ✅ **65 passed, 0 failed** in 0.09s |
| Ruff clean, touched files | ✅ **All checks passed** — module, tests, `__init__.py` |
| Line length | ✅ module max 82, tests max 91 (limit 100) |
| Health report generated | ✅ this document |

Per the brief's stop point: **no full-repository run, no Rule 001, no byte-identity check, no milestone comparison, no self-audit.**

### 3.1 Two Ruff findings raised and resolved during implementation

Both were in files C10 created; neither is an opportunistic fix elsewhere.

**`I001` — import block un-sorted** in `foundation/__init__.py`. `attempt_token` sorts before `attestation`, and the import was initially placed after it. Reordered.

**`DTZ001` — `datetime()` without `tzinfo`** on the test that *deliberately* builds a naive timestamp to prove it is refused. Resolved with `# noqa: DTZ001`, **matching the existing house convention** — `tests/test_foundation_attestation.py` carries the identical suppression on the identical test, and that file is Ruff-clean.

---

## 4 · Engineering decisions

**ED-035 · `idempotency_key` is exposed, because §8.6 says this value is one.**

> *"The Kernel provides the key — `(intent_id, attempt_seq)` — and requires Workers to honour it where the underlying operation permits."*

The token holds exactly those two values. Exposing the pair as `idempotency_key` states what §8.6 states; it derives nothing and decides nothing. **`opened_at` is deliberately excluded from the key** — two attempts opened at different instants under the same warrant and sequence are one attempt seen twice, which is precisely what a Worker must deduplicate.

**ED-036 · `bool` is rejected for `attempt_seq`.**

`isinstance(True, int)` is `True` in Python, so without an explicit check `attempt_seq=True` would construct a valid-looking first attempt. An attempt numbered `True` is a caller error. This is the one type-confusion this value is actually exposed to, and it is closed at construction rather than left to a reviewer.

**ED-037 · Counting starts at 1, and `FIRST_ATTEMPT` is exported.**

§8.5 sets an `irreversible` budget of **1**, meaning one attempt and no second — the same reasoning `Warrant.attempt_budget` records: unambiguous in a way *"0 retries"* is not. A sequence of 0 is therefore not a sensible input, and it raises. The constant is exported so the Kernel and any Worker share one definition of "first" rather than each writing `== 1`.

**ED-038 · No dependency on the Warrant, and none on the Clock.**

Roadmap §2 C10 declared `C4 Warrant`. Amendment M4 corrected it to nothing, on the grounds that §3.5 takes an id and the declared API is a string, an int and a timestamp. Built to the amendment. `opened_at` is passed in, exactly as `Warrant.issued_at` and `Attestation.attested_at` are — which is what keeps this a pure value with no clock to stub.

**ED-039 · `is_first_attempt` is a fact, not a policy.**

It reports whether `attempt_seq == 1`. What follows from it — §8.4's rule that an irreversible action is never automatically retried — is decided by the Kernel against the Reversibility Registry's classification, neither of which this value can see. The property is named for the fact it reports, not for the decision it might tempt a caller into.

---

## 5 · Terminology

| Name | In codebase before C10? | |
|---|---|---|
| `AttemptToken` | 1 docstring mention in `refusal.py`; **0 classes** | ✅ clean |
| `InvalidAttemptToken` | 0 | ✅ clean |
| `attempt_seq` | 0 | ✅ clean |
| `FIRST_ATTEMPT` | 0 | ✅ clean |

### 5.1 `warrant_id`, and why nothing new is decided here

Kernel Specification §3.5 and §8.6 write `intent_id`. Roadmap v2 §2 C10 writes `warrant_id`. The shipped `Warrant` (C4) and `ExecutionContext` (C2) both name the field `warrant_id`.

**C10 follows the roadmap and the shipped precedent: `warrant_id`.** Two of the three grounding documents agree, and every shipped component that names this value already uses it.

This is the naming tension Objective Engine Spec §13.1 recorded when it renamed the Kernel's token type to `Warrant` — one identifier, two names. **Already documented; nothing new arises from C10, and no decision was taken here.** It becomes actionable at C13, which implements VEDA 04 A1's `recordIntent → intentId`.

---

## 6 · Preservation

| | |
|---|---|
| C1–C9 source | **Untouched.** No prior module edited |
| `foundation/__init__.py` | Exports only — three names added, none removed. One existing import line reordered by Ruff's `I001`, no name changed |
| Anything outside `foundation/` | **Untouched** |
| Roadmap / specifications / ADRs | **Untouched** |

---

## 7 · Risks

| # | Risk | Severity | Status |
|---|---|---|---|
| **R17** | **`attempt_seq` monotonicity is unenforceable here.** This value cannot know the previous attempt's number, so nothing prevents constructing attempt 5 before attempt 2, or two tokens with the same sequence. **The Kernel owns sequencing** — §3.5 mints the token — and a token that tried to enforce it would need state, which would stop it being a value | Low | **New, accepted.** C15's brief must state that `attempt()` allocates the sequence. Recorded so it is not discovered there |
| **R18** | **`idempotency_key` returns a tuple, not a string.** A Worker persisting it must choose an encoding, and two Workers could choose differently | Low | **New.** A tuple keeps the two components separable, which a concatenated string would not. If a canonical string form is ever needed it belongs where the persistence format is decided — C13 |
| **N1** | `intentId` / `warrant_id` naming, inherited | Medium | Unchanged. §5.1. Lands on C13 |

---

## 8 · Rule 000 assessment

> *Never compromise architectural integrity for speed.*

**Passes.** The token is 28 statements and carries three fields, which is what §3.5 and §8.6 describe and nothing more. The temptation this component offered was a `may_retry` or `attempts_remaining` field — convenient for a retry loop, and it would have placed §8.4's *"most important clause in this section"* inside the object being retried. Declined, and guarded by test so it cannot be added quietly.

Nothing outside `foundation/` was touched, and no prior component was modified.

---

## 9 · What was not done, deliberately

Per this brief: **no commit, no tag, no Rule 001 verification, no self-audit, no full-repository run, no byte-identity verification, no milestone comparison.** No architecture or roadmap document was modified and no ADR was created. C11 was not started.

**STOP.**

---

*Implementation health report. Working directory at 2026-08-05. Figures measured from the source and the component test suite.*
