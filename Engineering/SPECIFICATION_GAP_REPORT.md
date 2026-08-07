# Specification Gap Report — Pre-C15 Mint

**Audit Date:** 2026-08-06  
**Scope:** Specification audit only — no implementation inspection unless required to verify spec already provides the information  

---

## Executive Summary

**Confirmed Blockers: 5**  
**False Blockers: 1**  
**Already Resolved: 1**  
**Founder Decisions Required: 5**

| # | Gap | Severity | Status |
|---|-----|----------|--------|
| 1 | K1 liveness gate: EXECUTING-only vs non-terminal | **Critical** | Confirmed blocker — spec conflict |
| 2 | `expected_effect` has no source for K3/IntentRecord | **Critical** | Confirmed blocker — R35 |
| 3 | `attempt_budget` for `read_only` and `reversible_until` unspecified | **High** | Open — O1 |
| 4 | `expires_at` ruling missing (two unreachable `min()` terms) | **High** | Open — O2 |
| 5 | `reversibility_class` source resolved by ADR-0022 but C9.1 not implemented | **High** | Resolved in spec, blocked on C9.1 |
| 6 | K1 liveness gate spec conflict (Kernel Spec vs Objective Engine Spec) | **Critical** | False blocker — Option A resolves |

---

## 1. Confirmed Blockers

### Blocker 1: K1 Liveness Gate — Spec Conflict
**Severity: Critical**  
**Source Documents:** Kernel Specification §7.2 K1, Objective Engine Specification §10.2/§10.3, ADR-0021 D5, C8 RefusalReason (frozen at c8.0)

**Conflict:**
- **Kernel Specification §7.2 K1:** "resolves to an admitted objective in a **non-terminal** state. Refuses: no objective · unknown objective · objective already completed, failed, or cancelled."
  - READY and WAITING are **non-terminal** → **PASS K1**
- **Objective Engine Specification §10.2/§10.3:** "K1 keeps refusing while the objective is not EXECUTING" / "Non-EXECUTING ⇒ no mints"
  - READY and WAITING are **not EXECUTING** → **REFUSED**
- **ADR-0021 D5 (ratified):** "READY and WAITING therefore refuse mints. That is intended." — follows Objective Engine Spec
- **C8 RefusalReason (frozen at c8.0):** Only three objective-related members: `OBJECTIVE_MISSING`, `OBJECTIVE_UNKNOWN`, `OBJECTIVE_TERMINAL`
  - No member for "objective not executing"
  - Adding member modifies frozen C8 (closed enum by constitutional intent)

**Impact:** K1 cannot be implemented without either:
- Falsifying records (using `OBJECTIVE_TERMINAL` for live objective)
- Modifying frozen C8 (new tag, re-verification downstream)
- Contradicting ratified ADR-0021 D5

**Evidence:** CONFLICT_C15_PART2.md §1-§5; Kernel Spec §7.2 lines 414-416; Objective Engine Spec §10.2-10.3 lines 517-518; ADR-0021 D5 lines 30-32; C8 RefusalReason lines 140-147.

---

### Blocker 2: `expected_effect` Has No Source for K3/IntentRecord
**Severity: Critical**  
**Source Documents:** Kernel Specification §4.3 (line 238), HEALTH_C15_PART4.md §3.1 (R35), AUDIT_C9_CLAUDE.md §4 (R-A)

**Gap:** K3 (Receipt intent write) constructs an `IntentRecord` which requires `expected_effect` field.
- Kernel Spec §4.3 line 238: `expected_effect` — "What the world should look like after" — **Source: Planner**
- Planner is **not** one of §7.3's eight attestors
- Cannot arrive in `ExecutionRequest` (C9) — Planner not a caller
- Cannot arrive in `Attestation` (C7) — Planner not an attestor
- No other component provides it to the Kernel

**Evidence:** HEALTH_C15_PART4.md §3.1 lines 68-80; Kernel Spec §4.3 line 238; AUDIT_C9_CLAUDE.md §4 (predicted as R-A).

**Impact:** K3 cannot construct `IntentRecord` → mint blocked.

---

### Blocker 3: `attempt_budget` for `read_only` and `reversible_until` Unspecified
**Severity: High**  
**Source Documents:** Kernel Specification §8.5 (lines 507-512), ADR-0022 §5.3 O1, Amendment 003 §4.1

**Gap:** §8.5 table quantifies only two of four classes:

| Class | Budget | Status |
|-------|--------|--------|
| `read_only` | **Liberal** | ❌ Not a number |
| `reversible` | Bounded, small (**default 3**) | ✅ Specified |
| `reversible_until` | **Bounded** | ❌ Not a number |
| `irreversible` | **1** | ✅ Specified |

**Impact:** Mint cannot compute `attempt_budget` for two of four reversibility classes. The budget governs how many attempts an action may make (§8.5: "Set at mint from the capability's class, never by the retry loop").

**Evidence:** Kernel Spec §8.5 lines 507-512; ADR-0022 §5.3 O1; Amendment 003 §4.1.

---

### Blocker 4: `expires_at` Ruling Missing (Two Unreachable `min()` Terms)
**Severity: High**  
**Source Documents:** Kernel Specification §4.4 (line 251), ADR-0022 §5.3 O2, Amendment 003 §4.1 O2, CONFLICT_C15_PART4.md §3.2

**Gap:** §4.4 formula: `expires_at = min(grant validity, budget deadline, class-specific default)`

| Term | Reachable? | Evidence |
|------|------------|----------|
| grant validity | ❌ No | A3 attestation carries no `grant_ref` or expiry (CONFLICT_C15_PART4.md §3.2) |
| budget deadline | ✅ Yes | `AdmissionRecord.deadline` |
| class-specific default | ❌ No | "seconds for a filesystem write" is illustrative, not a value (Kernel Spec §4.4 line 251) |

**Critical Issue:** Using `AdmissionRecord.deadline` alone **drops terms from a `min()`** — arithmetically this can only **lengthen** the validity window, which is the **unsafe direction** (longer authorization than intended).

**Evidence:** Kernel Spec §4.4 line 251; ADR-0022 §5.3 O2; Amendment 003 §4.1 O2; CONFLICT_C15_PART4.md §3.2 lines 67-77.

---

### Blocker 5: `reversibility_class` Source Resolved but C9.1 Not Implemented
**Severity: High**  
**Source Documents:** ADR-0022, Amendment 003, Amendment 003 §2-3, HEALTH_C15_PART4.md §3.2

**Status:** 
- ✅ **Resolved in specification:** ADR-0022 ratified founder decision — `ExecutionRequest` carries `reversibility_class` (source: C12 ReversibilityRegistry via caller, per ADR-0022 D2)
- ✅ Resolves root cause for `attempt_budget` and `expires_at` derivation (ADR-0022 D3)
- ❌ **Not implemented:** C9 must be reopened as `c9.1` (Amendment 003 §3); Amendment 003 §2 corrects C9 public API and dependencies
- ❌ C9.1 not yet implemented (HEALTH_C15_PART4.md §3.2 line 86: "C9.1 — ratified, **not implemented**")

**Impact:** Mint cannot proceed until C9.1 ships with `reversibility_class` field.

**Evidence:** ADR-0022 D1-D4; Amendment 003 §2-4; HEALTH_C15_PART4.md §3.2 lines 82-89.

---

## 2. False Blocker

### False Blocker: K1 Liveness Gate — Option A Resolves Without Cost
**Source Documents:** CONFLICT_C15_PART2.md §5-§6

**Analysis:** The conflict between Kernel Spec (lenient: non-terminal passes) and Objective Engine Spec (strict: only EXECUTING passes) **appears** to block K1 implementation. However:

**Option A (Recommended by CONFLICT_C15_PART2.md §6):**
- K1 refuses only on terminal, per Kernel Specification §7.2
- READY and WAITING **pass K1**
- Liveness gate becomes Objective Engine's responsibility: it publishes `EXECUTING` only when it means it
- **Cost: zero** — no code change, no frozen-component change, C8's vocabulary already covers it exactly
- Consistent with §1.2 ("attestation, not reimplementation") and §3.4's test ("does another component already own this question?")
- Requires: amending ADR-0021 D5 to match Kernel Spec, and correcting its citation error (ADR-0021 D5 cites Kernel Spec §10.3 but text is in Objective Engine Spec §10.2/10.3)

**Why not a blocker:** Option A costs nothing, changes no frozen component, matches C8's vocabulary exactly. The conflict is in ADR-0021 D5's ratification of the stricter reading, not in the Kernel Spec itself.

**Evidence:** CONFLICT_C15_PART2.md §5-§6; Kernel Spec §7.2 lines 414-416.

---

## 3. Already Resolved

### Resolved: `reversibility_class` Canonical Source
**Source Documents:** ADR-0022 (ratified), Amendment 003

**Resolution:** ADR-0022 ratified founder decision:
- `ExecutionRequest` carries `reversibility_class: ReversibilityClass` (required, no default)
- Source: C12 ReversibilityRegistry via caller (ADR-0022 D2)
- Kernel derives `attempt_budget` and `expires_at` from carried class (ADR-0022 D3)
- Ceiling check becomes meaningful: Kernel refuses when `reversibility_class` exceeds `consequence_ceiling` (ADR-0022 D4)

**Open Items from ADR-0022:**
- R34: A2 attestation does not bind to carried `reversibility_class` — caller can present genuine attestation with different class (understatement danger)
- O1: `attempt_budget` for `read_only` and `reversible_until` (Blocker 3)
- O2: `expires_at` ruling (Blocker 4)

**Evidence:** ADR-0022 D1-D4, §5.1-5.3; Amendment 003 §2-4.

---

## 4. Decisions Still Required from Founder

| # | Decision | Severity | Blocks | Where Documented |
|---|----------|----------|--------|------------------|
| 1 | **K1 liveness gate rule**: Option A (Kernel Spec: non-terminal passes) vs Option B (ADR-0021 D5: only EXECUTING passes) | **Critical** | K1 implementation | CONFLICT_C15_PART2.md §5 |
| 2 | **`expected_effect` source for K3/IntentRecord**: Planner is not an attestor; how does Kernel get it? | **Critical** | K3/mint | HEALTH_C15_PART4.md R35 |
| 3 | **`attempt_budget` values**: `read_only` = ? (number), `reversible_until` = ? (number) | **High** | Mint | ADR-0022 O1, Amendment 003 O1 |
| 4 | **`expires_at` ruling**: Adopt `AdmissionRecord.deadline` alone (lengthens window) or supply class-specific default / grant validity? | **High** | Mint | ADR-0022 O2, Amendment 003 O2 |
| 5 | **R34 mitigation**: Bind `reversibility_class` into A2 attestation's subject (recommended close) | **High** | Security | ADR-0022 §5.1 |

---

## 5. Dependency Graph

```
┌─────────────────────────────────────────────────────────────────┐
│                    REMAINING DECISIONS                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ K1 gate     │  │ expected_   │  │ attempt_    │  ┌─────────┐  │
│  │ rule        │  │ effect src  │  │ budget vals │  │ expires │  │
│  │ (Opt A/B)   │  │             │  │ (O1)        │  │ _at (O2)│  │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └────┬────┘  │
└─────────┼────────────────┼────────────────┼─────────────┼────────┘
          │                │                │             │
          ▼                ▼                ▼             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  BLOCKED IMPLEMENTATION                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ K1          │  │ K3 /        │  │ Mint        │              │
│  │ implementation│  │ IntentRecord│  │ (attempt_   │              │
│  │             │  │ (expected_  │  │  budget,    │              │
│  │             │  │  effect)    │  │  expires_at)│              │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │
└─────────┼────────────────┼────────────────┼─────────────────────┘
          │                │                │
          ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      BLOCKED COMPONENT                          │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                    C15 Part 5+ (Kernel)                     │ │
│  │  • K1 cannot be coded without gate decision                │ │
│  │  • K3 cannot construct IntentRecord without expected_effect│ │
│  │  • Mint cannot compute attempt_budget/expires_at           │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────┐
│                        DEMO IMPACT                              │
│  • No Kernel → no minting → no execution → no vertical slice   │
│  • Founder Edition Sprint 1 cannot complete without C15        │
│  • C16 (Execution Path Unification) blocked on C15             │
│  • C17 (Objective Engine) blocked on C15                       │
│  • C21 (Dashboard) blocked on C15                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. Summary: Exactly What Decisions Remain Before C15 Can Be Completed

**Five founder decisions required:**

1. **K1 liveness gate rule** — Adopt Option A (Kernel Spec: non-terminal passes) — **zero cost, matches C8, resolves conflict** ✓ Recommended
2. **`expected_effect` source for K3** — Must identify canonical owner (Planner? ExecutionRequest? AdmissionRecord?) — **Critical blocker**
3. **`attempt_budget` numeric values** for `read_only` and `reversible_until` — **High blocker**
4. **`expires_at` ruling** — Adopt `AdmissionRecord.deadline` alone (lengthens window) or supply missing terms? — **High blocker**
5. **R34 mitigation** — Bind `reversibility_class` into A2 attestation subject — **High, for mint brief**

**Already resolved in spec (awaiting C9.1 implementation):**
- `reversibility_class` source = C12 via caller (ADR-0022 ratified)

**False blocker (resolved by Option A):**
- K1 liveness gate spec conflict — Option A costs nothing, matches C8, requires only ADR-0021 D5 amendment

---

*End of Specification Gap Report — Read-Only. No files modified. No code inspected beyond verifying spec claims.*