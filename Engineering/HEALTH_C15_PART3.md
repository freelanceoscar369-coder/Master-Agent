# Health Report — Sprint 1 Component 15, Part 3: Authorization Verification

**Type:** Implementation health report. Working-directory evidence only.
**Date:** 2026-08-06
**Status:** Part 3 complete. **Not committed, not tagged, no Rule 001.**

---

## 1 · What was built

| File | | Lines |
|---|---|---|
| `src/master_agent/kernel/kernel.py` | extended | 546 (**84 AST statements**, was 59) |
| `tests/test_kernel_authorization.py` | new | 655 |

**New internal surface**

```
DEFAULT_ATTESTATION_MAX_AGE       module constant — §7.3's freshness window
_required_questions(action_class) §7.4's set, derived from C7
Kernel._verify_attestations(request) -> KernelRefusal | None
Kernel._attestation_absent(question, why)
```

**The public surface is unchanged** — still §3.5's four operations plus the two readers. Verification is a step of `authorize`, not an operation: a caller that could pre-verify would act on a stale answer, and the Kernel's guarantee is that the check and the mint happen together.

**All four operations still raise `NotImplementedError`** — asserted by test. Mint, execution, retry and settlement are not here.

---

## 2 · §7.3 implemented in full

> *"The Kernel verifies each attestation's **presence, attestor identity, subject match, and freshness**. **It never re-derives the verdict.**"*

| Property | Implementation | Adversarial coverage |
|---|---|---|
| **Presence** | Every question in §7.4's set must be supplied | Each of the 6 local questions removed in turn; both intelligence-only questions removed in turn; a local set offered for an intelligence request |
| **Attestor identity** | `attestation.attestor` must equal `question.canonical_attestor` | **Forged past C7's frozen dataclass** — §3 below |
| **Subject match** | `attestation.subject` must equal `request.payload_digest` | Each of the 6 questions given a foreign subject in turn; a complete valid set replayed against a mutated payload |
| **Freshness** | `attestation.is_stale(clock.now(), MAX_AGE)` | Each of the 6 aged out in turn; boundary case; clock advanced mid-test |
| **Verdict carried, never re-derived** | `REFUSED` → `ATTESTATION_REFUSED`, attestor's reason relayed verbatim | Each of the 6 refused in turn; the reason asserted equal, not merely present |

**No attestor is called.** Verified structurally: an AST walk of `_verify_attestations` collects every call on the Kernel's own collaborators and asserts the set is exactly `{self._clock.now, self._attestation_absent}`. Reaching the admission provider or the ledger from here would be re-deriving; reaching an attestor would be reimplementation.

**§14 R3 is the risk this part exists against** — *"if validation degrades to 'a field is present,' the Kernel becomes ceremony."* Each of the four properties is checked on **every** required question, not just the first, and there is a parametrized test per property proving it.

### 2.1 §7.4's two-attestation difference

`_required_questions` derives the set from C7's own `is_intelligence_only` and never restates it. Local = A1–A6; intelligence = A1–A8; the difference is exactly `PROVIDER` and `ADMISSION`, asserted directly.

### 2.2 §7.1's ordering

Questions are checked in §7.3's table order and the **first** failure is returned — *"a refusal costs as little as possible and the reason returned is the most fundamental one."* Two tests pin it: two simultaneous failures report the earlier question, and a missing A2 outranks a refused A5.

---

## 3 · The forged-attestor test

C7's ED-019 makes a mis-attributed attestation **unconstructable**, so §7.3's attestor-identity check cannot fail through the public constructor. Two ways to respond, and only one is safe:

- Skip the check because C7 covers it — which is exactly the validation-thinning §14 R3 warns about, and it makes the Kernel's compliance depend on a distant invariant in a different component.
- **Implement it anyway, and forge an attestation past the frozen dataclass to prove it works.**

Part 3 does the second. `object.__setattr__` bypasses C7's guard, the Kernel refuses the forgery naming the wrong attestor, and a companion test confirms the public constructor still refuses it. The check is not dead code — it is the only thing standing if C7 ever relaxes.

---

## 4 · Two values the specifications do not give

Both were required by §7.3 and defined nowhere. Recorded rather than buried.

### 4.1 The subject is the request's `payload_digest`

C7's ED-022 deliberately left this to the Kernel: *"What identifies a subject — a payload digest, a capability, a request id — is the Kernel's business, not this value's."*

The Kernel's answer is `payload_digest`, on §4.4's authority — *"An Intent is bound to its `actor`, `capability`, and `payload_digest`. Presenting it for a different capability or a mutated payload is refused"* — and §8.2's, which calls the digest *"the load-bearing term."*

**Residual gap, recorded as R32:** two requests with identical payloads under *different objectives* share a digest, so an attestation could in principle transfer between them. §8.2's "same action" is the five-tuple `(objective_id, actor, capability, payload_digest, target_ref)`, not the digest alone. Closing it would mean the Kernel deriving a composite subject identity that attestors must also compute — a coupling no frozen document describes, so it is **flagged rather than invented**.

### 4.2 The freshness window is unratified

**No frozen document specifies a value.** §7.3 requires freshness to be verified and §14 R3 rates skipping it High, but neither the Kernel Specification nor any VEDA gives a window.

`DEFAULT_ATTESTATION_MAX_AGE = 60 seconds`, chosen short because a request is assembled and authorized in one breath, and §4.3's reasoning for intent expiry applies with more force to the evidence behind it.

**It is a named module constant specifically so that changing it is a visible decision** rather than an edit inside a method. **Awaiting founder ratification — R31.**

---

## 5 · Quality gates

| Gate | Result |
|---|---|
| Part 3 tests | **64 passed, 0 failed** |
| Parts 1–3 together | **156 passed, 0 failed** |
| Ruff — all C15 source and tests | **All checks passed** |
| Line length | 88 / 85 (limit 100) |
| Architecture guards (Rule 001 set) | **215 passed, 1 skipped, 0 failed** |
| §14 R9 ceiling | **84 of 600 statements — 14% consumed** (was 10%) |
| C1–C14 untouched | **0 modified files** in `foundation/` or `ledger/` |

---

## 6 · Frozen vocabulary only

**No new Foundation type. No new `RefusalReason`. No dependency change.**

C8's two attestation reasons carry every failure: `ATTESTATION_ABSENT` for missing, mis-attributed, subject-mismatched and stale — §7.3 says all four *"are treated as absent"* — and `ATTESTATION_REFUSED` when the attestor said no. `detail` distinguishes which of the four it was, which is exactly the division of labour C8's ED-025 chose: the reason says *what kind*, `failed_check` says *which question*, `detail` says *why*.

A test asserts only those two reasons are ever produced and that the enum is still eleven members.

Refusals name `question.canonical_attestor` — C8 refuses any refusal that attributes a failure to the wrong component, so this is enforced at construction as well as asserted.

---

## 7 · Risks

| # | Risk | Severity | Note |
|---|---|---|---|
| **R31** | **The freshness window is unratified.** 60 seconds, chosen by me, specified nowhere | **Medium** | **New.** The check is implemented and tested; only the value is open. Too short refuses legitimate work, too long defeats §7.3. **Founder ratification needed** — it is a constant, so the change is one line |
| **R32** | **Subject match uses `payload_digest` alone.** Two requests with identical payloads under different objectives share a digest, so an attestation could transfer between them | **Medium** | **New.** §8.2's "same action" is a five-tuple. Closing it needs a composite subject identity that attestors also compute — a coupling no frozen document describes. **Flagged, not invented** |
| **R33** | **Over-attestation is permitted.** A local request carrying A7/A8 passes | Low | **New, deliberate.** §7.4 defines what is *required*; an extra answer is not malformed, and C8 has no reason to refuse it. Recorded so it is a decision |
| **R30** | No `RefusalReason` covers an unreachable admission provider | Medium | Carried from Part 2. Unchanged |
| **R29** | `settle()` cannot source `correlation_id` / `trace_id` | Medium | Carried. Lands on the settlement part |
| **R25** | The ledger's single-writer assumption is unstated | Medium | Carried. Part 3 writes nothing; lands on K3 |
| **R6** | §14 R9's 600-statement ceiling | High | **14% consumed.** Verification cost 25 statements for eight questions and four properties |

---

## 8 · Blockers

**None.**

R31 and R32 are open decisions, not blockers: the checks are implemented, tested, and behave correctly under any value the founder chooses for R31. R32 is a narrowing that would strengthen an already-working check.

---

## 9 · Preservation

C1–C14 untouched — `git status` reports zero modified files in `foundation/` or `ledger/`. C7, C8 and C9 in particular are byte-identical; Part 3 reads their vocabularies and restates none of them, asserted by test.

Nothing outside `src/master_agent/kernel/kernel.py` and `tests/test_kernel_authorization.py` was changed. No specification, roadmap, amendment or ADR modified. No commit, no tag.

**STOP.** Awaiting Hermes audit.
