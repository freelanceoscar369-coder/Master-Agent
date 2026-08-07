# Health Report — Sprint 1 Component 15, Part 4: K2 and the ordered precondition set

**Type:** Implementation health report. Working-directory evidence only.
**Date:** 2026-08-06
**Status:** Complete for the work that is unblocked. **K3 and the mint are deferred — see §3.**
**Not committed, not tagged, no Rule 001.**

---

## 1 · What was built

| File | | Lines |
|---|---|---|
| `src/master_agent/kernel/kernel.py` | extended | 638 (**99 AST statements**, was 84) |
| `tests/test_kernel_preconditions.py` | new | 423 |

**New internal surface**

```
Kernel._check_override_state()          -> KernelRefusal | None      §7.2 K2
Kernel._check_preconditions(request)    -> AdmissionRecord | KernelRefusal   §7.4
```

**The public surface is unchanged** — still §3.5's four operations plus the two readers. All four still raise `NotImplementedError`, asserted by test.

---

## 2 · What this part completes

### 2.1 K2 · Override state

§7.2: *"Global suspension is not active. **Why the Kernel:** the Override's meaning **is** 'the Kernel stops minting.' No other component can express that."*

| Property | Implementation |
|---|---|
| Refusal | `OVERRIDE_ACTIVE`, `failed_check = K2_OVERRIDE_STATE`, **`attestor = None`** (Amendment M5 — a K-check has no attestor) |
| Detail | The founder's own words, **carried verbatim**. The Kernel relays; C20 owns composition |
| Remediable | **True.** VEDA 01 §10 — the override is *"never discouraged"*, and resuming is one gesture. A suspension reading as irremediable would be a revocation of trust the founder cannot undo |
| Reads | **Only its own switch** — signature takes no argument. No request, no admission, no ledger |
| Writes | **Nothing.** §11.8's mechanism belongs to `invalidate()`, which is not implemented |

**§7.5's collapse property is tested directly:** a thousand refusals under one suspension produce a set of size **one** — *"a thousand refusals are one state… not a thousand queue items."*

### 2.2 §7.4's ordered precondition set

```
  local        K1 · K2 · A1 A2 A3 A4 A5 A6 · [K3 — not in this part]
  intelligence K1 · K2 · A1 … A8            · [K3 — not in this part]
```

§7.1 is why the order is load-bearing: *"a refusal costs as little as possible and the reason returned is the most fundamental one. An action with no objective is refused for having no objective, never for a budget problem it also had."*

Proved two ways. **Behaviourally** — a suspended Kernel asked about an unknown objective refuses for the *unknown objective*; three simultaneous failures report K1; a suspended Kernel with no attestations refuses at K2 rather than A1. And **structurally** — an AST walk of `_check_preconditions` asserts the call sequence is exactly `_check_objective_binding → _check_override_state → _verify_attestations`, so a reordering that happened to pass the behavioural tests still fails.

On success it returns the `AdmissionRecord`, because the envelope §10.3 names is what the mint will bound the warrant against, and reading it twice would invite the two reads to disagree.

### 2.3 ADR-0022 forward references, as instructed

Two `TODO(ADR-0022)` markers, placed where the binding will go rather than only in a report — one in the module docstring's subject-match section, one at the subject comparison in `_verify_attestations`. Both name **R34** and the recommended close. A test asserts both are present, so they cannot be silently dropped.

Per the brief, **the carried `reversibility_class` is treated as trusted for now.**

---

## 3 · What is deferred, and why

### 3.1 K3 is blocked — R35, and it is not R34

`_check_receipt_intent_write` does not exist. K3 writes an `IntentRecord` (C13), and its fields were mapped by introspection against everything the Kernel can reach:

| `IntentRecord` field | Source |
|---|---|
| `warrant_id` · `recorded_at` | Kernel · Clock |
| `objective_id` · `principal_id` · `capability` · `consequence` | request |
| `reversibility_class` | **request, once C9.1 ships** — ADR-0022 |
| **`expected_effect`** | **⛔ none** |

**`expected_effect` has no source, and ADR-0022 does not address it.** ADR-0022 added exactly one field. §4.3 sources `expected_effect` to the **Planner**, and the Planner is not one of §7.3's eight attestors — so it can arrive neither in the request nor inside an attestation.

**This is the same finding recorded as R-A (High) in `AUDIT_C9_CLAUDE.md` §4**, which predicted it would surface at C15. It has.

### 3.2 The mint is blocked on three things

| # | Blocker | Status |
|---|---|---|
| **C9.1** | `ExecutionRequest.reversibility_class` | Ratified in ADR-0022; **this session was instructed not to implement it** |
| **O1** | `attempt_budget` for `read_only` and `reversible_until` | §8.5 quantifies only `irreversible` (1) and `reversible` (3). *"Liberal"* and *"bounded"* are not numbers. **Open** |
| **O2** | `expires_at` ruling | §4.4's `min()` has two unreachable terms; using `AdmissionRecord.deadline` alone drops terms, which can only **lengthen** the window. **Open** |

§7.4 places K3 and the mint last, so everything before them is complete.

---

## 4 · Quality gates

| Gate | Result |
|---|---|
| Part 4 tests | **32 passed, 0 failed** |
| Parts 1–4 together | **188 passed, 0 failed** |
| Ruff — all C15 source and tests | **All checks passed** |
| Line length | 88 / 81 (limit 100) |
| Architecture guards (Rule 001 set) | **215 passed, 1 skipped, 0 failed** |
| §14 R9 ceiling | **99 of 600 statements — 17% consumed** (was 14%) |
| C1–C14 untouched | **0 modified files** in `foundation/` or `ledger/` |

---

## 5 · Engineering decisions

**ED-044 · K2 takes no argument.**

§7.2 gives K2 one question about the Kernel's own state. A signature taking the request would invite a future suspension scoped per-objective or per-capability, and §11.8 is explicit that suspension is **global** — *"one gesture stops everything."*

**ED-045 · `_check_preconditions` returns the record, not a boolean.**

The same reasoning as ED-041: the envelope and the admission decision come from one read.

**ED-046 · The order is asserted structurally, not only behaviourally.**

§7.1's ordering is a constitutional guarantee, and behavioural tests can pass by coincidence when several checks would refuse. Reading the call sequence out of the AST makes a silent reordering fail.

**ED-047 · Test suspension forces the Kernel's own slot.**

There is no public writer — suspension arrives through `invalidate()`, which is not implemented — so the test helper sets `_override` directly. Inventing a `_suspend` would be override *behaviour*, which this part does not own.

---

## 6 · Risks

| # | Risk | Severity | Note |
|---|---|---|---|
| **R35** | **`IntentRecord.expected_effect` has no source.** K3 cannot construct one. §4.3 sources it to the Planner, which is not an attestor, so it can arrive neither in the request nor in an attestation | **High** | **New here, though predicted.** `AUDIT_C9_CLAUDE.md` §4 recorded it as R-A and said it would surface at C15. **A founder decision is needed** — the same shape ADR-0022 just settled for `reversibility_class`, and worth settling together with O1 and O2 so the mint unblocks in one pass |
| **R34** | The A2 attestation does not bind to the carried `reversibility_class` | High | Carried from ADR-0022. **Marked in source** with two `TODO(ADR-0022)` references. Trusted for now, per this brief |
| **O1 · O2** | `attempt_budget` values; `expires_at` ruling | Medium | Carried from ADR-0022 §5.3. Both block the mint |
| **R32** | Subject match uses `payload_digest` alone | Medium | Carried. R34's recommended close resolves both |
| **R31** | Attestation freshness window unratified | Medium | Carried |
| **R30** | No `RefusalReason` for an unreachable admission provider | Medium | Carried |
| **R6** | §14 R9's 600-statement ceiling | High | **17% consumed.** K2 and the ordering cost 15 statements |

---

## 7 · Blockers

**None for the work delivered.**

**Four for the mint**, and settling them together would unblock it in one pass: **C9.1** (ratified, not implemented), **R35** (`expected_effect`, needs a decision), **O1** (two budget numbers), **O2** (the `expires_at` ruling).

---

## 8 · Preservation

C1–C14 untouched — zero modified files in `foundation/` or `ledger/`. **C9 was not reopened**, per the brief. Parts 1–3 unchanged; their 156 tests still pass unmodified.

Nothing outside `src/master_agent/kernel/kernel.py` and `tests/test_kernel_preconditions.py` was changed. No specification, roadmap, amendment or ADR modified. No commit, no tag.

**STOP.**
