# ADR-0022: `ExecutionRequest` carries `reversibility_class`; the Kernel performs no lookup for it

Status: Accepted (2026-08-06) — Founder Decision. Unblocks C15 Part 4.
Supersedes three engineering guards shipped in C9 at `kalpavriksha-s1-c9.0` (§5.2).

## Context

C15 Part 4 — the mint decision — is blocked. `Engineering/CONFLICT_C15_PART4.md` records the finding: constructing a `Warrant` needs ten fields, and **three have no source the Kernel can reach.**

| Field | Source | |
|---|---|---|
| **`reversibility_class`** | none | ⛔ root cause |
| `attempt_budget` | §8.5's table, **keyed by** `reversibility_class` | ⛔ dependent |
| `expires_at` | §4.4's formula, partially unreachable | ⛔ dependent |

Measured by introspection: `ExecutionRequest`, `AdmissionRecord` and `Attestation` carry no reversibility class between them. `AdmissionRecord.consequence_ceiling` is an **upper bound** (§10.4 — *"the highest consequence class any warrant under this objective may carry"*), not the action's class, and substituting it would record a false class and make C4's own ceiling check compare a value against itself.

Three options were put to the founder: a classification provider port on the Kernel; the request carrying the value; or widening the `Attestation` type.

## Decision

**`ExecutionRequest` carries `reversibility_class`.**

Founder rationale, recorded verbatim:

> *"The architectural intent is that the Kernel performs no additional lookups beyond the already approved `AdmissionProvider`."*

The Kernel therefore derives `attempt_budget` and `expires_at` from the carried class **without introducing any additional runtime dependency**. The port option was declined on that ground; widening `Attestation` was not taken.

### D1 · The field

`ExecutionRequest` gains one required field:

```python
reversibility_class: ReversibilityClass
```

**Required, with no default.** A default would be a guessed class, and §7.3 A2 exists precisely so that no component guesses one. `read_only` as a default would be the most dangerous possible choice, since it is the least-constrained cell of §8.5's budget table.

### D2 · The caller obtains it from the Reversibility Registry, never invents it

The intended flow, unchanged from what A2 already requires:

```
   caller ──► ReversibilityRegistry.classify(capability) ──► Classification
          ──► ReversibilityRegistry.attest(...)          ──► Attestation (A2)
          ──► ExecutionRequest(reversibility_class=classification.cls,
                               attestations=(…, a2, …))
          ──► Kernel.authorize(request)
```

Both the value and the attestation come from **C12, the owner §4.3 names**. The caller is a courier, not an author. This is the same shape the eight attestations already use: evidence is gathered from owners and carried, and the Kernel verifies rather than re-asks.

### D3 · The Kernel derives, and still does not look up

| Derived | From | Basis |
|---|---|---|
| `attempt_budget` | the carried class | §8.5 — *"Set at mint from the capability's class, never by the retry loop"* |
| `expires_at` | the carried class and `AdmissionRecord.deadline` | §4.4's `min()` |

Neither derivation consults anything outside the request and the already-approved `AdmissionProvider`, which is the whole point of the decision.

### D4 · The ceiling check becomes meaningful

With the action's own class present, C4's `consequence_ceiling` finally has something to bound. §10.4:

> *"An objective admitted with `consequence_ceiling: reversible` **cannot mint an irreversible warrant**, no matter what the plan later decides."*

The Kernel refuses when `reversibility_class` exceeds `consequence_ceiling`. Under the previous shape this comparison was unimplementable.

## Consequences

### 5.1 The integrity gap this decision creates — recorded, not argued

**The A2 attestation does not bind to the carried value.**

`Attestation` carries `question · attestor · subject · verdict · attested_at · reason`. Its `subject` is the request's `payload_digest` (C15 Part 3, per C7's ED-022). **Nothing structurally ties the attestation to the `reversibility_class` the caller carried alongside it.**

So a caller can present a genuine, fresh, correctly-attributed A2 attestation and a **different** class than the registry gave it. The Kernel cannot detect the substitution, because it cannot read the registry's answer.

**The dangerous direction is understatement.** Claiming `reversible` for an action the registry classified `irreversible` yields `attempt_budget` 3 instead of 1 and evades §8.4 — *"an action classified `irreversible` is never automatically retried. Ever."*

**Partial mitigation, available today:** D4's ceiling check bounds the class **upward**. A caller cannot claim more consequence than the objective's envelope permits. It does not bound understatement.

**Recommended follow-on, costing no frozen component:** bind the class into the A2 attestation's subject. `ReversibilityRegistry.attest(capability, subject, attested_at)` takes `subject` from its caller, so the subject can be a digest of `(payload_digest, reversibility_class)`. The Kernel's subject convention is C15's own — set in Part 3, not frozen — so changing it reopens nothing. **This is a decision for the part that implements the mint**, and it closes the gap completely.

Recorded as **R34**.

### 5.2 Three shipped C9 guards are reversed

C9 at `kalpavriksha-s1-c9.0` asserted the opposite of this decision, deliberately and with stated reasoning. All three must change, and the reasoning they carried is now superseded rather than merely edited.

| Guard | What it asserts today | Effect |
|---|---|---|
| `test_it_has_no_dependency_on_the_warrant_type` | *"The only import from `warrant` would be `ReversibilityClass`, **which the Reversibility Registry attests (A2) rather than the caller asserting**."* | **Removed.** Its premise is exactly what this ADR reverses |
| `test_it_depends_only_on_components_seven_and_six` | C9 imports only `attestation` and `consequence` | **Widened** to include `foundation.warrant` for `ReversibilityClass` |
| `test_it_holds_no_field_the_kernel_owns` | Lists `reversibility_class` among fields a request must not carry, *"§4.3 sources these to the Kernel or an attestor at mint. A request carrying one would be the caller authorizing itself."* | **`reversibility_class` removed from the list.** The other fourteen names stay |

**This is the honest cost of the decision and it is stated plainly:** C9 was built to keep the caller from asserting its own reversibility class, and this ADR permits exactly that, with D2 as the discipline and R34 as the residual risk.

### 5.3 Two values remain open

Unchanged by this ADR and still required before the mint can be built:

| # | Needed | Why |
|---|---|---|
| **O1** | `attempt_budget` for `read_only` and `reversible_until` | §8.5 quantifies only `irreversible` (1) and `reversible` (3). *"Liberal"* and *"bounded"* are not numbers |
| **O2** | A ruling on `expires_at` | §4.4's `min(grant validity, budget deadline, class-specific default)` has two unreachable terms. Using `AdmissionRecord.deadline` alone **drops terms from a `min()`**, which can only lengthen the window — the unsafe direction |

## Migration impact

**One component is reopened. Everything else is additive or unaffected.**

### 6.1 C9 — `ExecutionRequest`

| Change | Detail |
|---|---|
| Field added | `reversibility_class: ReversibilityClass`, required |
| Position | **After `action_class`, before `consequence`** — both describe *what kind of action this is*, and the identity fields (`objective_id`, `principal_id`, `capability`, `payload_digest`) stay contiguous at the front |
| Positional callers | Any construction passing more than five positional arguments shifts. **All shipped tests use keyword arguments**, so the measured breakage is zero |
| Invariant added | Must be a `ReversibilityClass`; nothing else. C9 cannot check the ceiling — that is the `AdmissionRecord`'s, and C9 has no access to it |
| Import added | `ReversibilityClass` from `foundation.warrant` — C9's third internal import |
| `as_dict()` | Gains one key, `"reversibility_class"`, between `action_class` and `consequence` |
| Tests | Three guards changed (§5.2); new coverage for the field's presence, type validation, all four class values, and serialisation |

### 6.2 Versioning

C9 is GREEN at `kalpavriksha-s1-c9.0` and this modifies it. Following the `c1` → `c1.1` precedent for a correction to a shipped component:

```
new commit on top of HEAD  →  kalpavriksha-s1-c9.1
```

**Tags `c10.0` through `c14.0` remain valid and are not re-cut.** They contain the earlier `ExecutionRequest` and were verified against it; history is linear and nothing is rewritten. Rule 001 applies to `c9.1` in full — clean-checkout verification at the commit, then at the tag.

**Expected suite delta at `c9.1`:** 2,462 at `c13.0`, plus the new C9 tests, minus none — the three reversed guards are modified, not deleted.

### 6.3 What does not change

| | |
|---|---|
| **C4 `Warrant`** | Untouched. It already has the field; this gives it a source |
| **C7 `Attestation`** | Untouched. Not widened — that was the option not taken |
| **C12 `ReversibilityRegistry`** | Untouched. It still classifies and still produces the A2 attestation. It gains a second reader, which its API already supports via `classify()` |
| **C11, C13, C14** | Untouched |
| **C15 Parts 1–3** | Untouched. 156 tests unaffected; the Kernel's dependency set stays at three |
| **Constitution, VEDAs** | Untouched. No frozen constitutional document is amended |

## Components affected

| Component | Effect | Action |
|---|---|---|
| **C9 ExecutionRequest** | **Modified** — one field, one import, three guards reversed | Re-tag `c9.1` under Rule 001 |
| **C15 Part 4** | **Unblocked** for `reversibility_class`. Still needs O1 and O2 | Proceed once C9 ships and the two values land |
| **C15 Parts 1–3** | Unaffected | None |
| **C4 · C7 · C11 · C12 · C13 · C14** | Unaffected | None |
| **C16 Execution Path Unification** | **Every caller must now supply the class**, obtained per D2. This lands with C16's unification of the 15 entry points | Record in C16's brief |
| **C17 Objective Engine** | Unaffected — it publishes admission, not requests | None |
| **C21 Dashboard** | Unaffected | None |

## Alternatives considered and rejected

| Alternative | Rejected because |
|---|---|
| A classification provider port on the Kernel | **Declined by the founder**: the Kernel performs no lookup beyond the approved `AdmissionProvider` |
| Widen `Attestation` to carry the classification | Most faithful to *"attestation, not reimplementation"*, and it would close R34 outright — but it modifies C7, on which C9, C12 and the Kernel all depend. The widest blast radius of the three |
| Substitute `AdmissionRecord.consequence_ceiling` | §10.4 makes it an upper bound, not the action's class. Would record a false class permanently and make D4's check compare a value against itself |
| Take it from `Consequence.reversibility` | In Sprint 1 the field is always `PENDING_CONSEQUENCE_ENGINE` (§14.1, B1 is Sprint 2); and the quartet's owner is the Consequence Engine, not the Reversibility Registry §4.3 names |

## References

- `Engineering/CONFLICT_C15_PART4.md` — the block this resolves
- `SPRING_1_IMPLEMENTATION_ROADMAP_v2_AMENDMENT_003.md` — roadmap effect
- Constitutional Kernel Specification §4.3, §4.4, §7.3 A2, §8.4, §8.5, §10.4, §1.2
- ADR-0021 — the precedent for a founder decision superseding a shipped engineering guard
