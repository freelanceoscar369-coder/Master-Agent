# Sprint 1 Roadmap v2 — Amendment 001

**Type:** Dependency hardening pass. No code, no commits, no tags, no architecture designed.
**Date:** 2026-08-05
**Amends:** `SPRING_1_IMPLEMENTATION_ROADMAP_v2.md` §2 (component dependencies) and §4 (implementation order), for components **C8–C21**.
**Authority:** This amendment is authoritative where it differs from the roadmap. The roadmap is **not modified**.
**Trigger:** Risk R11, raised during Component 7 — *"the roadmap contains at least one incorrect dependency, found on the first component built from it."*

---

## 1 · Method and result

Every remaining component's declared dependencies, public API, terminology and ownership were re-derived from the frozen documents rather than read from the roadmap. That is the discipline whose absence produced the C7 error.

**Nine findings. Six are corrections; one is a blocker the roadmap misjudged; two are decisions that must be made at brief time rather than discovered mid-implementation.**

| # | Component | Finding | Severity |
|---|---|---|---|
| **M1** | C13 Receipt Ledger | Depends on C6, not C7. Wrong in both directions. | High |
| **M2** | C18 Learning Subscriber | Does not depend on C13. | Medium |
| **M3** | C15 Kernel | Omits C6 Consequence. | High |
| **M4** | C10 Attempt Token | Over-declares C4 Warrant. Depends on nothing. | Medium |
| **M5** | C8 Kernel Refusal | `attestor` must be optional; the reason set is larger than implied. | High |
| **M6** | **C11 Admission Record** | **Blocked on the same ADR it was extracted to avoid.** | **Critical** |
| **M7** | C12 Reversibility Registry | Attestation coupling is a choice, not a given. | Decision |
| **M8** | C9 Execution Request | `Principal` object or `principal_id`? Undecided. | Decision |
| **M9** | C19 Vigilance | Has no domain to attest over until a connector reports health. | Low |

**Terminology: clean.** All 14 proposed API names checked against Constitution §17's frozen terms and the shipped codebase. Zero collisions. One caution at §6.

**Ownership: consistent.** No remaining component claims anything Kernel Specification §3.4 assigns elsewhere.

---

## 2 · The corrections

---

### M1 · C13 Receipt Ledger — wrong in both directions

**Location.** Roadmap §2 C13: *"Depends on. C1 Clock, C5 Receipt, **C7 Attestation**, `persistence.StateStore`."*

**Why the roadmap is wrong.** VEDA 04 A1's contract is explicit:

```
recordIntent(actor, actionType, reversibilityClass, expectedEffect, consequence, ruleRef?) → intentId
recordOutcome(intentId, result, actualEffect)
```

And A1's module text: *"Intent carries actor, rule (if any), reversibility class, expected effect, and **the consequence quartet**."*

**There is no attestation anywhere in A1.** There *is* a consequence quartet, which the roadmap omits.

**Correct dependency.** C1 Clock · C5 Receipt · **C6 Consequence** · `persistence.StateStore` *(shipped)*. **Remove C7.**

**Why the correction is safe.** It removes one dependency and adds one that shipped at `c5.0`. The ledger's public API is unchanged.

**Order impact.** None. C6 precedes C13 under either reading.

> **Note on the quartet's availability.** Kernel Spec §14.1 records that B1 (the Consequence Engine) is Sprint 2, so an intent record written in Sprint 1 carries the explicit marker `pending_consequence_engine`, never null. C13's brief must state this or it will be discovered at implementation time.

---

### M2 · C18 Learning Subscriber — does not depend on the Ledger

**Location.** Roadmap §2 C18: *"Depends on. **C13 Receipt Ledger**, C15 Kernel, `mission_control.events.EventBus`."*

**Why the roadmap is wrong.** Kernel Spec §10.2: *"Use the Event Bus that already exists."* §10.3: *"Publication is after the durable write, never before."*

The **Kernel** writes durably and then publishes. The subscriber receives events. It never reads the ledger, and §10.3's *"no subscriber is required — zero subscribers is a valid, fully functional configuration"* confirms it holds no reference to anything the Kernel owns.

**Correct dependency.** C15 Kernel *(for the nine event types)* · `mission_control.events.EventBus` *(shipped)*. **Remove C13.**

**Why the correction is safe.** Removes a dependency. Also removes a temptation: a subscriber holding the ledger could read it, and §10.3's isolation guarantee is easier to keep when it cannot.

**Order impact.** **Yes.** C18 becomes buildable immediately after C15, in parallel with C16 and C17 rather than behind them.

---

### M3 · C15 Constitutional Kernel — omits C6

**Location.** Roadmap §2 C15: *"Depends on. Everything above — C1, C2, C4, C5, C7, C8, C9, C10, C11, C12, C13, C14."*

**Why the roadmap is wrong.** C6 Consequence is absent from the list, yet the Kernel needs it twice: A1's `recordIntent` takes a `consequence`, and Kernel Spec §4.3 lists `consequence` as a warrant field.

**Correct dependency.** Add **C6**. Full set: C1, C2, C4, C5, **C6**, C7, C8, C9, C10, C11, C12, C13, C14.

**Why the correction is safe.** C6 shipped at `c5.0`.

**Order impact.** None.

---

### M4 · C10 Attempt Token — over-declares the Warrant

**Location.** Roadmap §2 C10: *"Depends on. C4 Warrant."*

**Why the roadmap is wrong.** Kernel Spec §3.5: `attempt(intent_id) → AttemptToken | Refusal` — the operation takes an **id**, not a warrant. The roadmap's own public API for C10 is `AttemptToken(warrant_id, attempt_seq, opened_at)`: a string, an int, and a timestamp.

The Kernel checks the warrant's expiry and attempt budget *before* minting a token. The token itself never touches a `Warrant`.

**This is the same class of error as C7 (ED-018): a dependency declared from the conceptual relationship rather than from the type.**

**Correct dependency.** **Nothing.** Not even the Clock — `opened_at` is passed in, as `Warrant.issued_at` and `Attestation.attested_at` are.

**Why the correction is safe.** Removes a dependency entirely and matches the pattern of the six shipped value objects.

**Order impact.** **Yes.** C10 joins the immediately-buildable set with C14, C19 and C20.

---

### M5 · C8 Kernel Refusal — the reason set is larger, and the attestor is optional

**Location.** Roadmap §2 C8: *"Depends on. C7 Attestation (a refusal names which attestation failed)."* Public API: *"`KernelRefusal` (frozen: reason, failed_check, attestor, remediable, detail)."*

**Why the roadmap is wrong — two ways.**

**First, `attestor` cannot be required.** Kernel Spec §7.2's three checks — K1 objective binding, K2 override state, K3 receipt intent write — are *"checks the Kernel performs itself… Each is a question about the Kernel's own domain. No other component owns it."* A refusal from K1 has no attestor, because no attestor was involved.

**Second, the reason set spans three families, not one.** §11.10 enumerates nine conditions, and most are not attestation failures:

| Family | Members |
|---|---|
| Kernel checks | K1 objective missing · K2 override active · K3 ledger unavailable |
| Attestation failures | A1–A8, each refusable |
| Infrastructure | Permission System unavailable · Tool/Worker unavailable · Provider unavailable · Kernel unavailable |

A `RefusalReason` enum covering only attestations would leave *"the ledger is down"* and *"autonomy is suspended"* unrepresentable — and §7.5 requires that **refusals are recorded**, so an unrepresentable refusal is an unrecordable one.

**Correct dependency.** C7's **`AttestationQuestion` enum only**, not the `Attestation` type. A refusal names *which question* failed, never the attestation object.

**Correct API.** `attestor: str | None` · `failed_check` spanning K-checks and A-questions · `RefusalReason` covering all three families above.

**Why the correction is safe.** Widens an enum and makes one field optional. Nothing shipped is affected.

**Order impact.** None.

> **Also relevant, and easy to miss.** §7.5: *"Under an active Override, a thousand refusals are one state — 'autonomy is suspended; 1,000 actions are waiting' — not a thousand queue items."* C8's brief must state that a refusal is **not** a judgment request, or C21 will render a thousand of them and reproduce the inbox VEDA 03 abolishes.

---

### M6 · C11 Admission Record — blocked on the ADR it was meant to route around

**Severity: critical. This is the finding that most affects the order.**

**Location.** Roadmap §4.1: *"**C11 before C15** — extracting the Admission Record as its own value is what lets the Kernel ship while the `Objective`/`Mission` ADR is unresolved. Without it, C15 waits on C17, which waits on ratification."*

**Why the roadmap is wrong.** The extraction does not achieve its stated purpose.

Objective Engine Spec §10.2 defines the record as carrying `state`, read by K1 on every mint, with *"K1 keeps refusing while the objective is not EXECUTING."* The roadmap's own public API for C11 lists `ObjectiveState` as a closed enum.

**But that state vocabulary is precisely what the ADR governs.** Objective Engine Spec §13.1 records two blockers, and both land on it:

- **Conflict B** — the frozen Mission state machine lacks `WAITING` and `SUPERSEDED`; both need ratification
- **The `Objective`/`Mission` collision** — `Mission State` is a **frozen §17 term**, and `ObjectiveState` sits directly beside it

So C11 carries the blocked vocabulary, and C15 depends on C11. **The Kernel is blocked after all**, by a longer route than the roadmap avoided.

**This is a decision, not something a hardening pass resolves.** Three options, with what each costs:

| Option | Effect | Cost |
|---|---|---|
| **(a) Ratify the ADR** | Unblocks C11, C15 **and** C17 together | One ADR. Removes the project's longest-standing blocker. **Recommended.** |
| **(b) Narrow the record** | C11 carries a mintability indicator answering only K1's two questions — *admitted?* and *non-terminal?* — instead of the lifecycle state | Unblocks C11 and C15 without the ADR, but **is a design decision beyond the roadmap** and would need its own validation |
| **(c) Accept the block** | C11 and C15 wait for C17 | Sprint 1 stalls after C10, C12, C13, C14, C19, C20 are exhausted |

**Order impact.** Under (a) or (b), the order in §4 holds. Under (c), **C15 moves behind C17** and the sprint has a hard stop.

> Kernel Spec §7.2 K1 requires only: *"`objective_id` present, resolves to an admitted objective in a non-terminal state. Refuses: no objective · unknown objective · objective already completed, failed, or cancelled."* That is narrower than the full lifecycle — which is what makes (b) possible. **Stated as evidence for the decision, not as the decision.**

---

## 3 · The two decisions to make at brief time

Neither is a roadmap error. Both are choices the roadmap left open, and both would otherwise be discovered mid-implementation — which is exactly what this pass exists to prevent.

### M7 · C12 — does the Reversibility Registry construct Attestations?

Roadmap: *"Depends on C4 `ReversibilityClass`, C7 Attestation (it produces the A2 attestation)."*

Kernel Spec §1.2 establishes *"attestation, not reimplementation"* — owners answer, the Kernel verifies. So an A2 attestation must come from the registry. The open question is whether the registry **constructs** it or merely **answers** it.

| Option | Consequence |
|---|---|
| Registry constructs the `Attestation` | Couples a registry to the attestation type; one fewer moving part |
| Registry answers `classify()`; a thin adapter builds the attestation | Registry stays a pure lookup; adds an adapter per attestor |

**Recommendation: the registry constructs it.** Eight attestors each needing an adapter is seven more components than the sprint has room for, and `Attestation` imports nothing, so the coupling is to a leaf.

**Decide before C12's brief.**

### M8 · C9 — `Principal` object or `principal_id`?

Roadmap: *"Depends on. C2 Principal, C6 Consequence, C7 Attestation."*

The two shipped precedents disagree, and both are correct for their purpose:

| Shipped | Carries | Why |
|---|---|---|
| `ExecutionContext` (C3) | `principal: Principal` | Runtime identity; *"so a receipt can name them without a lookup"* |
| `Warrant` (C4) | `principal_id: str` | *"a flat, self-contained record… deterministic to serialise"* |

An `ExecutionRequest` becomes a `Warrant`. **Recommendation: `principal_id: str`**, consistent with what it turns into — which also means C9 does **not** depend on C2, only on C6 and C7's enum.

**Decide before C9's brief.**

---

## 4 · M9 · C19 Vigilance — nothing to attest over yet

VEDA 04 D7 requires *"a coverage check across every monitored domain."* VEDA 04 §2: *"Data connectors — **must report freshness and health per domain** to feed D7."*

**No component reports domain health today.** C19 is buildable — the registry and the attestation logic are self-contained — but it will attest over an empty or hand-registered domain set until a connector reports.

**Not a blocker.** The First Founder Journey's slice registers exactly one domain (the receipts folder), and C19's brief should say so rather than implying a connector integration that is not in Sprint 1.

---

## 5 · Corrected dependency table — C8 to C21

Bold marks a change from the roadmap.

| # | Component | Corrected dependencies | Buildable |
|---|---|---|---|
| **C8** | Kernel Refusal | **C7 `AttestationQuestion` enum only** | after C7 ✅ |
| **C9** | Execution Request | C6 Consequence, C7 Attestation, **~~C2~~** *(pending M8)* | after C7 ✅ |
| **C10** | Attempt Token | **nothing** | **now** ✅ |
| **C11** | Admission Record | C4 `ReversibilityClass` — **⚠ blocked, see M6** | ⚠ |
| **C12** | Reversibility Registry | C4 `ReversibilityClass`, C7 Attestation *(pending M7)* | after C7 ✅ |
| **C13** | Receipt Ledger | C1, C5, **C6**, StateStore — **~~C7~~** | after C7 ✅ |
| **C14** | Override | nothing | **now** ✅ |
| **C15** | Constitutional Kernel | C1, C2, C4, C5, **C6**, C7, C8, C9, C10, C11, C12, C13, C14 | after all ⚠ |
| **C16** | Execution Path Unification | C15 | after C15 |
| **C17** | Objective Engine | C11, C15, C8 — **⚠ blocked on ADR** | ⚠ |
| **C18** | Learning Subscriber | C15, EventBus — **~~C13~~** | after C15 ✅ |
| **C19** | Vigilance Attestation | C1 Clock | **now** ✅ *(see M9)* |
| **C20** | Voice Charter Validator | nothing | **now** ✅ |
| **C21** | Dashboard State | C13, C15, C17, C19, C20 | last |

### 5.1 Immediately buildable, in any order

**C10 · C14 · C19 · C20** — none depends on anything unshipped. Four components can proceed regardless of how M6 resolves.

---

## 6 · Terminology audit

All 14 proposed API names checked against Constitution §17's frozen terms and against `src/`:

```
RefusalReason · KernelRefusal · ActionClass · ExecutionRequest · AttemptToken
ObjectiveState · AdmissionRecord · Classification · ReversibilityRegistry
ReceiptLedger · LedgerUnavailable · OverrideSwitch · DomainRegistry · ValidationResult
```

**Zero collisions.** No name appears in §17's frozen vocabulary, and none exists as a class in the shipped codebase. `Kernel` is also unused.

Two cautions:

| Name | Caution |
|---|---|
| **`ObjectiveState`** | Sits directly beside frozen §17 **`Mission State`**. Same ADR as M6. Do not introduce it before that is settled. |
| **`KernelRefusal`** | Correctly qualified. `BrokerRefusal` and `PlanRefusal` already exist; a bare `Refusal` would be the third. |

**`Classification` is generic** and will live inside `reversibility/`. Acceptable, but the module must state that it means *reversibility* classification and nothing else.

---

## 7 · Ownership audit

Checked against Kernel Specification §3.4's *"does NOT own"* table. **No remaining component claims a responsibility the Kernel assigns elsewhere.**

| Component | Owns | Correctly does not own |
|---|---|---|
| C12 Reversibility Registry | Classification, compensating actions | Whether an invocation is permitted (C1 rules / Permission System) |
| C13 Receipt Ledger | Storage | The obligation to write first — that is the Kernel's K3 |
| C14 Override | Suspension state | Stopping work or queueing; only deciding stops |
| C15 Kernel | The Intent/Warrant, the attestation contract, the precondition set | Permission verdicts · provider selection · budgets · objective decomposition · execution · verification · receipt **storage** |
| C17 Objective Engine | Admission, envelope, criteria, completion | Planning · scheduling · execution |
| C19 Vigilance | Coverage attestation | Domain health itself — connectors report it |

---

## 8 · Corrected implementation order

§4 of the roadmap holds **if and only if M6 resolves via option (a) or (b)**.

### 8.1 If the ADR is ratified — recommended

```
C8 → C9 → C10 → C11 → C12 → C13 → C14 → C15 → C16 → C17 → C18 → C19 → C20 → C21
```

Unchanged from the roadmap, with corrected dependencies. C10, C14, C19, C20 may move earlier freely.

### 8.2 If the ADR remains open

```
C8 → C9 → C10 → C12 → C13 → C14 → C19 → C20        ← eight components, no blocker
    ────────── hard stop ──────────
C11 → C15 → C16 → C17 → C18 → C21                   ← all wait on ratification
```

**Eight of fourteen remain buildable.** The sprint does not stall immediately, but it stalls — and every component after the stop is the half that matters.

---

## 9 · Acceptance assessment

> *"Every remaining implementation brief should require ZERO architectural clarification before coding."*

**Achieved for eleven of fourteen:** C8, C9, C10, C12, C13, C14, C16, C18, C19, C20, C21 — dependencies corrected, terminology cleared, ownership verified, open choices reduced to two with recommendations (M7, M8).

**Not achieved for three:** C11, C15, C17. All three wait on one decision — M6 — and no amount of hardening closes it, because it is a founder decision about a frozen document rather than an engineering question.

**That is the honest answer, and it is also the useful one:** the roadmap claimed the Kernel was unblocked, and it is not. Finding that now costs one document. Finding it at C15 would cost the sprint's largest component mid-build.

> *"The roadmap should be stable enough that Components 8–21 proceed continuously."*

**Continuous through C10 unconditionally, and through C21 once M6 is decided.** No other dependency in the remaining fourteen is uncertain.

---

## 10 · Recommendation

**Ratify the `Objective`/`Mission` ADR before C11.**

It is the single decision standing between the sprint and continuous progress. It has been open since the Implementation Blueprint, it blocks three components including the Kernel, and Objective Engine Spec §13.1 already carries a recommendation and precedent — the Executive/Worker treatment in Constitution Amendment 1, which resolved an identical collision with a synonym rather than a rename.

**Meanwhile, implementation may continue without it.** C8 is next per the roadmap and is fully hardened by this amendment. C10, C14, C19 and C20 are unblocked in any order after that.

---

*Hardening pass. No code, no commits, no tags. No architecture designed and no component modified; `SPRING_1_IMPLEMENTATION_ROADMAP_v2.md` left untouched. Every dependency re-derived from VEDA 01/03/04, the Constitutional Kernel Specification, the Objective Engine Specification and the shipped source on 2026-08-05.*
