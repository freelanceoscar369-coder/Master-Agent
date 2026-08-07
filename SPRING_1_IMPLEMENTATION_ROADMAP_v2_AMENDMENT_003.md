# Sprint 1 Roadmap v2 — Amendment 003

**Type:** Component reopening and blocker removal. No code, no commits, no tags, no architecture designed.
**Date:** 2026-08-06
**Amends:** `SPRING_1_IMPLEMENTATION_ROADMAP_v2.md` §2 C9 and §2 C15, and §1's shipped-component table.
**Authority:** Authoritative where it differs from the roadmap or from Amendments 001 and 002. None of those is modified.
**Trigger:** Founder Decision recorded in **ADR-0022**, resolving `Engineering/CONFLICT_C15_PART4.md`.

---

## 1 · What changed

C15 Part 4 was blocked: three required `Warrant` fields had no source the Kernel could reach, rooted in a single one — **`reversibility_class`**.

**ADR-0022 makes `ExecutionRequest` the carrier**, on the founder's stated architectural intent that *"the Kernel performs no additional lookups beyond the already approved `AdmissionProvider`."*

The Kernel then derives `attempt_budget` (§8.5) and `expires_at` (§4.4) from the carried class with **no new runtime dependency**.

---

## 2 · Roadmap §2 C9 — corrected

**Location.** Roadmap §2 C9: *"Public API. `ActionClass` … · `ExecutionRequest` (frozen: objective_id, principal, capability, payload_digest, action_class, target_ref, attestations, consequence) · `InvalidExecutionRequest`."*

**Corrected public API** — one field added, and `principal` already reads `principal_id` per Amendment 001 M8:

```
ExecutionRequest (frozen: objective_id, principal_id, capability,
                  payload_digest, action_class, reversibility_class,
                  consequence, target_ref, attestations)
```

**Corrected dependencies.** Amendment 001 §5 lists C9 as *"C6 Consequence, C7 Attestation, ~~C2~~"*. It becomes **C4 `ReversibilityClass`, C6 Consequence, C7 Attestation**.

**Why the correction is not free, and the roadmap should say so.** C9 shipped with three guards asserting the opposite — most explicitly `test_it_has_no_dependency_on_the_warrant_type`, whose stated reason was that `ReversibilityClass` is *"attest[ed] (A2) rather than the caller asserting."* ADR-0022 §5.2 records all three and why each is superseded. **This is a reversal, not a clarification.**

---

## 3 · Roadmap §1 — C9 is reopened

Roadmap §1 lists shipped components as final. C9 is no longer final.

| # | Component | Was | Becomes |
|---|---|---|---|
| **C9** | Execution Request | `kalpavriksha-s1-c9.0` | **`kalpavriksha-s1-c9.1`** |

Following the `c1` → `c1.1` precedent for a correction to a shipped component.

**Tags `c10.0` through `c14.0` are not re-cut and remain valid.** They contain the earlier `ExecutionRequest` and were verified against it. History is linear; nothing is rewritten.

**Rule 001 applies to `c9.1` in full** — clean-checkout verification at the commit, then again at the tag.

---

## 4 · Roadmap §2 C15 — status

| | |
|---|---|
| **Was** | Part 4 blocked: `reversibility_class` unsourceable |
| **Becomes** | **Unblocked for that field.** Two values still required before the mint can be built |

### 4.1 The two values still open

| # | Needed | Why it is not an engineering choice |
|---|---|---|
| **O1** | `attempt_budget` for `read_only` and `reversible_until` | §8.5 quantifies only `irreversible` (**1**) and `reversible` (**3**). *"Liberal"* and *"bounded"* are not numbers, and the budget governs how many times an action may be attempted |
| **O2** | A ruling on `expires_at` | §4.4's `min(grant validity, budget deadline, class-specific default)` has two unreachable terms. Adopting `AdmissionRecord.deadline` alone **drops terms from a `min()`**, which can only lengthen the validity window — the unsafe direction, so it needs saying rather than assuming |

**Neither blocks C9's re-tag.** Both block the mint.

---

## 5 · Order effect

```
   C9.1  ExecutionRequest  (reopened, re-tagged)
     │
     ▼
   C15 Part 4  Mint decision   ← also needs O1 and O2
     │
     ▼
   C15 Part 5+ · C16 · C17 · C18 · C21
```

**C15 Parts 1–3 are unaffected** — 156 tests, no change to the Kernel's dependency set, which stays at `Clock`, `ReceiptLedger`, `AdmissionProvider`.

**C16 gains a requirement.** Every caller unified onto the Kernel's path must now supply `reversibility_class`, obtained from the Reversibility Registry alongside the A2 attestation (ADR-0022 D2). Fifteen entry points across two pipelines are in scope. **C16's brief must state it.**

**No other component's order changes.** C10, C11, C12, C13, C14 are untouched; C17, C19, C20, C21 are unaffected.

---

## 6 · Risk register effect

| # | Risk | Status |
|---|---|---|
| **R34** | **The A2 attestation does not bind to the carried `reversibility_class`.** A caller can present a genuine attestation and a different class; the Kernel cannot detect it. The dangerous direction is **understatement** — claiming `reversible` for an `irreversible` action yields `attempt_budget` 3 instead of 1 and evades §8.4's no-auto-retry rule | **New, High.** Partially mitigated by ADR-0022 D4's ceiling check, which bounds the class **upward only**. **Recommended close:** bind the class into the A2 attestation's subject — the subject convention is C15's own, set in Part 3, so it reopens no frozen component. **A decision for the mint's brief** |
| **R32** | Subject match uses `payload_digest` alone | Carried from C15 Part 3. **R34's recommended close would resolve both** |
| **R31** | The attestation freshness window is unratified | Carried. Unaffected |
| **R6** | §14 R9's 600-statement ceiling | Carried. 14% consumed; the mint is the largest remaining piece |

---

## 7 · What this amendment does not do

`SPRING_1_IMPLEMENTATION_ROADMAP_v2.md`, `AMENDMENT_001.md` and `AMENDMENT_002.md` are **left untouched**. Constitution, VEDAs and both specifications are **unchanged** — no frozen constitutional document is amended, and ADR-0022 carries no specification amendment because none is needed: §4.3 already sources `reversibility_class` to the Reversibility Registry, and D2 keeps it there.

**No code was written. C9 was not modified. No commit, no tag.**

---

*Component reopening. Produced against ADR-0022, `Engineering/CONFLICT_C15_PART4.md`, Roadmap v2, Amendments 001 and 002, and the Constitutional Kernel Specification on 2026-08-06. All field and guard claims measured against the shipped source at `kalpavriksha-s1-c13.0`.*
