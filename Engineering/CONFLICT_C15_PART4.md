# Conflict Report — C15 Part 4: the mint cannot construct a Warrant

**Type:** Dependency / specification conflict. **STOP. No code, no tests, no commit, no tag.**
**Date:** 2026-08-06
**Verdict:** **BLOCKED.** `Warrant.reversibility_class` has no source the Kernel can reach, and two further fields depend on it.

---

## 1 · The finding

Minting means constructing a `Warrant` (C4, frozen at `c3.0`). It has **ten required fields**. Measured against everything the Kernel can reach:

| Warrant field | Source | |
|---|---|---|
| `warrant_id` | Kernel mints | ✅ |
| `objective_id` | `request.objective_id` | ✅ |
| `principal_id` | `request.principal_id` | ✅ |
| `capability` | `request.capability` | ✅ |
| `payload_digest` | `request.payload_digest` | ✅ |
| `consequence_ceiling` | `AdmissionRecord.consequence_ceiling` | ✅ |
| `issued_at` | `Clock.now()` | ✅ |
| **`reversibility_class`** | — | ⛔ **none** |
| **`attempt_budget`** | §8.5's table, **keyed by `reversibility_class`** | ⛔ blocked by the above |
| **`expires_at`** | §4.4's formula needs grant validity and a class default | ⛔ partial |

**One root cause: the Kernel cannot see the capability's reversibility class.**

Everything it can reach was checked field by field:

```
ExecutionRequest : objective_id · principal_id · capability · payload_digest
                   action_class · consequence · target_ref · attestations
AdmissionRecord  : objective_id · state · consequence_ceiling · budget
                   deadline · required_authority · approval_ref
Attestation      : question · attestor · subject · verdict · attested_at · reason
```

**None carries it.**

---

## 2 · Why the obvious substitutions fail

| Candidate | Why not |
|---|---|
| **`AdmissionRecord.consequence_ceiling`** | §10.4 defines it as *"the **highest** consequence class any warrant under this objective may carry."* An upper bound is not the action's class — a `reversible` ceiling admits a `read_only` action. Substituting would record a false class in a permanent warrant, and would make C4's own ceiling check (`class ≤ ceiling`) compare a value against itself |
| **The A2 attestation** | `Attestation` carries a **verdict**, not a payload. It says the Reversibility Registry was asked and answered; it cannot say *which class*. C7 is frozen at `c7.0` |
| **`ExecutionRequest.consequence.reversibility`** | A real `Consequence` **does** carry a `ReversibilityClass` — a near miss. Two reasons it does not help: in Sprint 1 the field is always `PENDING_CONSEQUENCE_ENGINE`, because B1 is Sprint 2 and §14.1 requires the marker; and even in Sprint 2 the quartet is produced by the **Consequence Engine**, not the Reversibility Registry, so taking the class from it would source a field from a different owner than §4.3 assigns |
| **Hold the `ReversibilityRegistry`** | This brief forbids dependency expansion, and §1.2's *"attestation, not reimplementation"* is the reason the Kernel holds no attestor. **This is nonetheless the crux of the decision** — see §4 |
| **Add a field to `ExecutionRequest`** | C9 is frozen at `c9.0`, and this brief forbids reopening GREEN components |

---

## 3 · The two dependent gaps

Both resolve automatically once the root is fixed, but both need a value.

### 3.1 `attempt_budget` — §8.5's table is keyed by class, and two entries are unquantified

> | `read_only` | **Liberal** |
> | `reversible` | Bounded, small (**default 3**) |
> | `reversible_until` | Bounded, and the undo window is not extended by retrying |
> | `irreversible` | **1** |

`irreversible` and `reversible` are specified. **`read_only` ("liberal") and `reversible_until` ("bounded") are not numbers.** Deriving the budget is specified behaviour — *"set at mint from the capability's class"* — but two of the four cells need a founder value.

### 3.2 `expires_at` — §4.4's formula has two unreachable terms

> `expires_at = min(grant validity, budget deadline, class-specific default)`

| Term | Reachable? |
|---|---|
| grant validity | ⛔ the A3 attestation carries no `grant_ref` or expiry |
| budget deadline | ✅ `AdmissionRecord.deadline` |
| class-specific default | ⛔ *"seconds for a filesystem write"* is illustrative, not a value |

Using `AdmissionRecord.deadline` alone is a **narrowing of a `min()`** — arithmetically safe, since dropping terms can only make the window longer, which is the **unsafe** direction. So it cannot simply be adopted without the founder saying so.

---

## 4 · The decision

**Where does the Kernel get the reversibility class?**

### Option A — a classification provider port, mirroring R28 — **recommended**

The founder resolved R28 by giving the Kernel an `AdmissionProvider`. The same shape works here: a read port the Kernel holds, answered by the Reversibility Registry.

**Changes no frozen component.** C4, C7, C9 and C12 all stand. It is one constructor parameter and one Protocol, exactly like Part 2's.

**Is it reimplementation?** No. §7.3 forbids the Kernel *re-deriving a verdict*; the A2 attestation remains the verdict that the registry was asked and answered. The port supplies the **value** the Intent must record. §4.3 already sources `reversibility_class` to the Reversibility Registry — this is the Kernel reading the owner's answer, not forming its own.

**Cost:** the registry is consulted twice per action — once by whoever gathers the A2 attestation, once by the Kernel. Acceptable, and C12's `classify()` is an in-memory lookup.

### Option B — the caller supplies the `Classification` in the request

Matches how attestations already travel: whoever gathers A2 also carries C12's `Classification` value.

**Requires modifying `ExecutionRequest` (C9, frozen at `c9.0`)** — a new tag and re-verification. It also lets the caller state the class, which A2 exists to prevent; the Kernel would have to check the value against the attestation it cannot read.

### Option C — widen the A2 attestation to carry the classification

Most faithful to *"attestation, not reimplementation"* — the owner's answer travels with the owner's signature.

**Requires modifying `Attestation` (C7, frozen at `c7.0`)**, which is depended on by C9, C12 and the Kernel. The widest blast radius of the three.

---

## 5 · Recommendation

**Option A**, plus two founder values:

| # | Needed | For |
|---|---|---|
| 1 | A classification provider port on the Kernel | `reversibility_class` |
| 2 | `attempt_budget` for `read_only` and `reversible_until` | §8.5's two unquantified cells |
| 3 | Ruling on `expires_at` — adopt `AdmissionRecord.deadline` alone, or supply a class-specific default | §4.4's `min()` |

Option A is the only one that changes no frozen component, and it repeats a pattern the founder has already chosen once. Items 2 and 3 are values, not designs; each is one line.

---

## 6 · What is not blocked

**Parts 1–3 stand.** 156 tests passing, nothing modified. K1, K2's state, attestation verification and registration are all built and correct — **K2 and K3 are implementable today**; only the mint itself is blocked, and it comes last in §7.4's order.

C1–C14 remain GREEN. **No defect was found in any of them**, and no frozen document contradicts another here — this is a gap between what a Warrant requires and what the Kernel is given, not a disagreement between specifications.

---

## 7 · What was not done

No file was created or modified in `src/`. No test was written. No dependency added, no Protocol invented, no frozen component reopened, no `Warrant` constructed with a substituted field. `master_agent/kernel/` contains the same two files it did at the end of Part 3. **Part 5 was not started.**

---

*Conflict report. Every field mapped by introspecting `Warrant`, `ExecutionRequest`, `AdmissionRecord` and `Attestation` directly, and checked against Kernel Specification §4.3, §4.4, §7.3, §8.5 and §10.4 on 2026-08-06.*
