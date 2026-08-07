# Sprint 1 Implementation Roadmap v2

**Type:** Reconciliation. No architecture designed, no component changed, no code written.
**Date:** 2026-08-05
**Supersedes:** `SPRING_1_IMPLEMENTATION_PLAN.md` §2–§3 (component list, numbering, build order) **for sequencing only.** That document's architecture, interfaces, acceptance criteria, testing strategy and demonstration path remain authoritative and are not restated here.
**Does not modify:** the original plan, or any shipped component.

---

## 0 · Why this document exists

Components 3–5 surfaced three architectural findings that changed what could be built and in what order:

| Finding | Effect on sequence |
|---|---|
| **C2** — `Principal` in the brief meant Kalpavriksha's identity; VEDA 04 means a human authority | Split into `Principal` + a new `ExecutionContext`. One tag, two components. |
| **C3** — `execution_context_id` on a Warrant would be circular and temporally impossible | Established that the dependency runs Context → Warrant, fixing the order of everything downstream |
| **C5** — the brief's "quartet" was Evidence, already shipped; the real quartet is four different fields | Built the value model of B1's quartet, not a second Evidence |

None was a mistake in the plan. Each was a discovery only reachable by building. The result is that **the shipped track built immutable value objects while the plan scheduled stateful services**, and the numbering diverged at C3.

This document restates the numbering against what exists, and orders what remains.

### 0.1 The numbering reconciliation

Shipped components are numbered **by artifact**, not by tag — `Principal` and `ExecutionContext` shipped together under `kalpavriksha-s1-c2.0` but are two components with different dependencies and different consumers. Counting them as one is what made "Component 6" ambiguous in the first place.

**From here, one component means one artifact, one brief, one commit, one tag.**

---

## 1 · Current shipped components

All six are immutable value objects in `foundation/`. All verified under Quality Gate Rule 001. Measured, not estimated.

| # | Component | Tag | Source | Tests | Public surface |
|---|---|---|---|---|---|
| **C1** | **Canonical Clock** | `c1.1` | 295 | 28 | `Clock` · `Instant` · `SystemClock` · `ManualClock` |
| **C2** | **Principal** | `c2.0` | 169 | 21 | `Principal` · `PrincipalKind` · `PrincipalRegistry` · `UnknownPrincipal` · `InvalidPrincipalRegistry` |
| **C3** | **Execution Context** | `c2.0` | 119 | 33 | `ExecutionContext` |
| **C4** | **Constitutional Warrant** | `c3.0` | 303 | 55 | `Warrant` · `ReversibilityClass` · `InvalidWarrant` |
| **C5** | **Constitutional Receipt** | `c4.0` | 251 | 59 | `Receipt` · `ExecutionOutcome` · `InvalidReceipt` |
| **C6** | **Consequence Quartet** | `c5.0` | 240 | 49 | `Consequence` · `Cost` · `CostBasis` · `InvalidConsequence` |
| | **Total** | | **1,377** | **245** | 20 exported symbols |

**Calibration for every estimate below:** a foundation value object has run **119–303 source lines and 21–59 tests**, median ≈ 245 / 49.

### 1.1 What is *not* built, despite similar names

| Exists | Does not exist |
|---|---|
| `ReversibilityClass` — the vocabulary, inside `warrant.py` | The **Reversibility Registry** that classifies capabilities and fails closed |
| `Receipt` — the value object | The **Receipt Ledger** — the append-only store A1 requires |
| `Consequence` — the value model | The **Consequence Engine** (B1) that computes it — Sprint 2 |

Conflating these three pairs is the single most likely way this roadmap is misread.

---

## 2 · Remaining components

Fifteen. Each entry answers the ten questions the brief specifies.

---

### C7 · Attestation

**Purpose.** One attestor's answer to one of the Kernel's eight questions, with enough metadata for the Kernel to verify it without re-deriving the verdict.
**Why it still exists.** Kernel Spec §7.3: *"The Kernel verifies each attestation's presence, attestor identity, subject match, and freshness. It never re-derives the verdict."* That sentence is the Kernel's entire design, and the type it operates on does not exist.
**Depends on.** C1 Clock (freshness), C2 Principal (attestor identity).
**Shipped components depending on it.** None today. C4 `Warrant` has an `attestations[]` field in Kernel Spec §4.3 that was deliberately not implemented — see §5 R2.
**Future components depending on it.** C8, C9, C12, C13, C15 Kernel, and every attestor adapter. **Five consumers — the widest reach of any remaining value object.**
**Public API.** `AttestationQuestion` (closed enum, 8) · `AttestationVerdict` (closed enum, 2 — absence is not a third verdict) · `Attestation` (frozen: question, attestor, subject, verdict, attested_at, reason) · `InvalidAttestation` · `Attestation.is_stale(at, max_age)`.
**Kind.** Immutable value object.
**Size.** ~180 source lines.
**Tests.** ~50.

---

### C8 · Kernel Refusal

**Purpose.** A structured refusal naming the check that failed, the attestor, and whether it is remediable.
**Why it still exists.** Kernel Spec §3.5 — two of four operations return `… | Refusal`. §7.5: *"Refusals are data, not exceptions… the founder is reading a stack trace from a provider SDK instead of a sentence about their own machine."*
**Depends on.** C7 Attestation (a refusal names which attestation failed).
**Shipped components depending on it.** None.
**Future components depending on it.** C15 Kernel (`authorize`, `attempt`), C17 Objective Engine (V1–V5 admission refusals), C21 Dashboard (*"1,000 actions are waiting"*).
**Public API.** `RefusalReason` (closed enum) · `KernelRefusal` (frozen: reason, failed_check, attestor, remediable, detail) · `as_dict()`.
**Kind.** Immutable value object.
**Size.** ~130 source lines.
**Tests.** ~35.

> **Terminology.** Must be `KernelRefusal`, not `Refusal`. `BrokerRefusal` (`ai_infrastructure/refusal.py`) and `PlanRefusal` (`planner/plan.py`) already exist; a bare third would repeat the `Intent` collision documented in Objective Engine Spec §13.1.

---

### C9 · Execution Request

**Purpose.** Everything `Kernel.authorize()` needs, assembled by the caller before the Kernel is asked.
**Why it still exists.** Kernel Spec §3.5: `authorize(ExecutionRequest) → Warrant | Refusal`. It is the input half of the contract; the Warrant is the output half and already ships.
**Depends on.** C2 Principal, C6 Consequence (optional, pending B1), C7 Attestation.
**Shipped components depending on it.** None.
**Future components depending on it.** C15 Kernel, C16 Execution Path.
**Public API.** `ActionClass` (closed enum: `local` · `intelligence` — selects the attestation set, §7.4) · `ExecutionRequest` (frozen: objective_id, principal, capability, payload_digest, action_class, target_ref, attestations, consequence) · `InvalidExecutionRequest`.
**Kind.** Immutable value object.
**Size.** ~220 source lines.
**Tests.** ~50.

> **Boundary.** Five `Execution*` types will coexist: `ExecutionContext` (C3), `ExecutionOutcome` (C5), `ExecutionRequest` (C9), and the shipped `ExecutionResult` / `ExecutionLogEntry`. The module must document the distinction, as C3 and C5 did.

---

### C10 · Attempt Token

**Purpose.** Permission to open one attempt against a live warrant.
**Why it still exists.** Kernel Spec §3.5: `attempt(warrant_id) → AttemptToken | Refusal`, refusing when *"expired, cancelled, settled, or out of attempt budget."* C4's `attempt_budget` is currently authorized but unenforced — nothing consumes it.
**Depends on.** C4 Warrant.
**Shipped components depending on it.** None.
**Future components depending on it.** C15 Kernel, C16 Execution Path, and the Runtime's retry loop.
**Public API.** `AttemptToken` (frozen: warrant_id, attempt_seq, opened_at) · `InvalidAttemptToken`.
**Kind.** Immutable value object.
**Size.** ~120 source lines.
**Tests.** ~35.

---

### C11 · Admission Record

**Purpose.** The Objective Engine's published statement that an objective is admitted, live, and bounded by an envelope.
**Why it still exists.** Kernel Spec §7.2 K1 checks *"objective admitted, non-terminal."* Objective Engine Spec §10.2 defines what it reads. Without this as its own value, the Kernel would import the Objective Engine — and the Objective Engine is blocked on an unratified ADR (§5 R1).
**Depends on.** C4 `ReversibilityClass` (the consequence ceiling).
**Shipped components depending on it.** None.
**Future components depending on it.** C15 Kernel (K1 and the envelope check), C17 Objective Engine (produces it), C21 Dashboard.
**Public API.** `ObjectiveState` (closed enum) · `AdmissionRecord` (frozen: objective_id, state, consequence_ceiling, budget, deadline, required_authority, approval_ref) · `InvalidAdmissionRecord`.
**Kind.** Immutable value object.
**Size.** ~200 source lines.
**Tests.** ~45.

> **This is a sequencing recommendation, not a new design.** Objective Engine Spec §10.2 already specifies the record. Extracting it as its own value object is what lets the Kernel ship while the `Objective`/`Mission` ADR is open. If that ADR resolves first, C11 may be folded into C17 instead.

---

### C12 · Reversibility Registry

**Purpose.** Classify every capability, name its compensating action, and fail closed on anything unclassified.
**Why it still exists.** Kernel Spec §7.3 A2: *"Unclassified. Fails closed — no default classification exists."* VEDA 04 A2: *"'probably reversible' cannot be represented."* Only the vocabulary shipped; the registry did not.
**Depends on.** C4 `ReversibilityClass`, C7 Attestation (it produces the A2 attestation).
**Shipped components depending on it.** None.
**Future components depending on it.** C15 Kernel, C16 Execution Path.
**Public API.** `Classification` (frozen: capability, cls, compensating_capability, undo_window) · `ReversibilityRegistry.register / classify / is_classified` · `Unclassified` (raises — fails closed).
**Kind.** Registry.
**Size.** ~200 source lines, **plus a one-time classification audit of ~30 shipped capabilities.**
**Tests.** ~45, plus one coverage test asserting every registered capability is classified.

> **The audit is the expensive half and it does not shrink.** VEDA 04 R2 rates it high severity and *"easy to underestimate."* At ~30 capabilities it is days; the original plan's §9 risk 2 records why it must not be deferred.

---

### C13 · Receipt Ledger

**Purpose.** The append-only store. The first stateful component in the system.
**Why it still exists.** Kernel Spec §7.2 K3 and VEDA 04 A1: *"if the intent write fails, the action does not occur. No exceptions, no buffering, no fire-and-forget."* Nothing executes without somewhere to write first.
**Depends on.** C1 Clock, C5 Receipt, C7 Attestation, `persistence.StateStore` (**exists, shipped**).
**Shipped components depending on it.** None.
**Future components depending on it.** C15 Kernel, C18 Learning Subscriber, C21 Dashboard, and every future audit.
**Public API.** `ReceiptLedger.record_intent / record_attempt / record_outcome / read` · `LedgerUnavailable`. **No update. No delete. At any privilege level.**
**Kind.** Stateful service.
**Size.** ~320 source lines.
**Tests.** ~65, including crash-safety and restart-ordering tests.

> **The riskiest component in Sprint 1.** It is the first thing that persists, the first that can fail in a way that must abort an action, and the one where "no buffering" forecloses the obvious mitigation. Original plan §9 risk 4 applies: the write is on the critical path of every action and **must never be made async.**

---

### C14 · Override

**Purpose.** One gesture suspends all minting. Work and queueing continue; only deciding stops.
**Why it still exists.** VEDA 04 A3, Kernel Spec §7.2 K2 and §11.8. VEDA 01 §10: *"One gesture stops everything… no confirmation dialogue and no persuasion."*
**Depends on.** Nothing. Deliberately outside the main path so it works when the rest is degraded.
**Shipped components depending on it.** None.
**Future components depending on it.** C15 Kernel (K2), C21 Dashboard.
**Public API.** `OverrideSwitch.suspend(reason) / resume() / is_suspended()`. **No confirmation parameter exists in any signature.**
**Kind.** Stateful service (minimal).
**Size.** ~90 source lines.
**Tests.** ~25.

---

### C15 · Constitutional Kernel

**Purpose.** The sole minting authority. Three checks performed, eight attestations required, four operations.
**Why it still exists.** The point of the sprint.
**Depends on.** **Everything above** — C1, C2, C4, C5, C7, C8, C9, C10, C11, C12, C13, C14.
**Shipped components depending on it.** None.
**Future components depending on it.** C16, C17, C18, C21 — and every capability ever written.
**Public API.** `Kernel.authorize / attempt / settle / invalidate`. **There is no `execute()`.**
**Kind.** Engine.
**Size.** ~400 source lines. Kernel Spec §14 R9 sets a **600-line ceiling**: *"if the Kernel exceeds roughly 600 lines, something in it belongs somewhere else."*
**Tests.** ~90, including the adversarial bypass suite.

---

### C16 · Execution Path Unification

**Purpose.** One gate. `warrant_id` required by `LocalExecutor.run()`, no alternative route to a tool.
**Why it still exists.** VEDA 04 R1 — holes in an audit spine are worse than no spine. The Execution Path Report inventoried **15 entry points across two pipelines.**
**Depends on.** C15 Kernel.
**Shipped components depending on it.** None in `foundation/`. **Modifies** `orchestrator/`, `executor/`, `runtime/gateway.py`, `runtime/engine.py`, `ai_infrastructure/execution.py`, `cli.py`.
**Future components depending on it.** Every capability, permanently.
**Public API.** No new surface. `LocalExecutor.run()` gains a required `warrant_id`; `Orchestrator.execute_plan()` is deleted.
**Kind.** Modification of existing components.
**Size.** ~150 changed lines across 6 files.
**Tests.** ~40, mostly adversarial refusals.

> **The only component that modifies shipped code**, and the only one that collides with the uncommitted MB032–039 work (§5 R3).

---

### C17 · Objective Engine

**Purpose.** Admission, validation V1–V5, envelope, consequence ceiling, criteria, completion.
**Why it still exists.** K1's anchor. Nothing executes without an objective.
**Depends on.** C11 Admission Record, C15 Kernel, C8 KernelRefusal.
**Shipped components depending on it.** None.
**Future components depending on it.** C21 Dashboard, and the Sprint 1 vertical slice.
**Public API.** `ObjectiveEngine.draft / validate / admit / record_criterion / complete / terminate`.
**Kind.** Engine.
**Size.** ~400 source lines.
**Tests.** ~90.
**Status.** **BLOCKED** on the `Objective`/`Mission` ADR — §5 R1.

---

### C18 · Learning Subscriber

**Purpose.** Records Kernel events. Proves the one-way contract.
**Why it still exists.** Kernel Spec §10.3 — subscribers *"have no return channel"*; Eng. Law V made structural rather than aspirational.
**Depends on.** C13 Receipt Ledger, C15 Kernel, `mission_control.events.EventBus` (**exists — the only reporting shape in the system; a second bus must not be built**).
**Shipped components depending on it.** None.
**Future components depending on it.** Sprint 3's Proposal Miner.
**Public API.** `LearningSubscriber.subscribe(bus)`. **Returns nothing. Cannot veto, delay, or modify.**
**Kind.** Adapter.
**Size.** ~110 source lines.
**Tests.** ~30, including "a raising subscriber does not affect execution" and "zero subscribers is valid."

---

### C19 · Vigilance Attestation

**Purpose.** Prove coverage before the calm state may be spoken. One monitored domain.
**Why it still exists.** VEDA 04 D7. *"Nothing needs you"* is unsayable without it, and shipping the reassurance before the proof is the sequencing error VEDA 04 §9 names as most tempting.
**Depends on.** C1 Clock (freshness windows).
**Shipped components depending on it.** None.
**Future components depending on it.** C21 Dashboard.
**Public API.** `DomainRegistry.register / report` · `VigilanceAttestation.attest() → {complete, domains[], gaps[]}`. **The calm-state string must be unconstructable without a complete attestation.**
**Kind.** Registry + service.
**Size.** ~200 source lines.
**Tests.** ~45.

---

### C20 · Voice Charter Validator

**Purpose.** Lint every outbound utterance. No exclamation marks, no emoji, no percentages, no celebration, one apology, no stacked hedges.
**Why it still exists.** VEDA 04 D2 and R4 — *"the only defence against the language model's baseline personality reasserting itself, and it will try to on every model upgrade."*
**Depends on.** Nothing.
**Shipped components depending on it.** None.
**Future components depending on it.** C21 Dashboard, and every narration surface thereafter.
**Public API.** `validate(utterance) → ValidationResult` · `enforce(utterance, fallback) → str`. **No bypass parameter exists.**
**Kind.** Adapter / validator.
**Size.** ~220 source lines.
**Tests.** ~50, plus the start of a permanent personality regression corpus.

> **Timing note.** The original plan argued for building this in Phase 0 so nothing needs retro-validation. **That argument is now weaker, not stronger: no utterance exists yet.** The first ones arrive with C21. Placing it immediately before C21 satisfies the invariant — *no utterance ever exists un-validated* — at lower cost than interleaving it now.

---

### C21 · Dashboard State

**Purpose.** Screen 01: the voice, one decision, the receipt.
**Why it still exists.** VEDA 03. The founder-facing end of the slice.
**Depends on.** C13 Receipt Ledger, C15 Kernel, C17 Objective Engine, C19 Vigilance, C20 Voice Charter.
**Shipped components depending on it.** **Extends** `dashboard/readmodel.py` (frozen read-model dataclasses, ADR-0016).
**Future components depending on it.** Sprint 2's narration surfaces.
**Public API.** New frozen read-model dataclasses only. **No objective count, no progress bar, no badge** — VEDA 03 refuses all three.
**Kind.** Extension of an existing component.
**Size.** ~140 source lines.
**Tests.** ~35.

---

## 3 · Dependency graph

```
   ┌──────────────────────── SHIPPED ────────────────────────┐
   │                                                          │
   │   C1 Clock ──────┬──────────────┬───────────┐            │
   │                  │              │           │            │
   │   C2 Principal ──┼──┐           │           │            │
   │        │         │  │           │           │            │
   │        └─► C3 Execution Context │           │            │
   │                     │           │           │            │
   │   C4 Warrant ◄──────┘           │           │            │
   │     │  └─ ReversibilityClass ─┐ │           │            │
   │     │                         │ │           │            │
   │   C5 Receipt ◄────────────────┼─┘           │            │
   │                               │             │            │
   │   C6 Consequence ◄────────────┘             │            │
   └─────────────────────────────────────────────┼────────────┘
                                                 │
   ┌───────────────── VALUE OBJECTS ─────────────┼────────────┐
   │                                             ▼            │
   │   C7 Attestation ◄── C1, C2                              │
   │        │                                                 │
   │        ├──► C8 KernelRefusal                             │
   │        │                                                 │
   │        ├──► C9 ExecutionRequest ◄── C2, C6               │
   │        │                                                 │
   │   C10 AttemptToken ◄── C4                                │
   │                                                          │
   │   C11 AdmissionRecord ◄── ReversibilityClass             │
   └──────────────────────────┬───────────────────────────────┘
                              │
   ┌────────────── SERVICES ──┼───────────────────────────────┐
   │                          ▼                               │
   │   C12 Reversibility Registry ◄── C4, C7                  │
   │   C13 Receipt Ledger ◄── C1, C5, C7, StateStore✓         │
   │   C14 Override ◄── (nothing)                             │
   └──────────────────────────┬───────────────────────────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │   C15 CONSTITUTIONAL KERNEL   │ ◄── C7,C8,C9,C10,C11,
              │   authorize·attempt·settle·   │     C12,C13,C14
              │   invalidate                  │
              └───────────────┬───────────────┘
                              │
        ┌─────────────┬───────┴────────┬──────────────┐
        ▼             ▼                ▼              │
   C16 Execution  C17 Objective   C18 Learning        │
   Path Unified   Engine ⚠BLOCKED  Subscriber         │
        │             │                               │
        └─────────────┴───────────────┬───────────────┘
                                      │
                  C19 Vigilance ──────┤
                  C20 Voice Charter ──┤   (both independent;
                                      ▼    placed by need)
                        ┌─────────────────────────┐
                        │   C21 Dashboard State   │
                        └─────────────────────────┘
                                      │
                                      ▼
                        ┌─────────────────────────┐
                        │  THE VERTICAL SLICE     │
                        │  runs end to end        │
                        └─────────────────────────┘
```

---

## 4 · Canonical implementation order

**This order supersedes `SPRING_1_IMPLEMENTATION_PLAN.md` §3.**

| # | Component | Kind | Src | Tests | Buildable now? |
|---|---|---|---|---|---|
| **C7** | Attestation | value object | ~180 | ~50 | ✅ |
| **C8** | Kernel Refusal | value object | ~130 | ~35 | after C7 |
| **C9** | Execution Request | value object | ~220 | ~50 | after C7 |
| **C10** | Attempt Token | value object | ~120 | ~35 | ✅ |
| **C11** | Admission Record | value object | ~200 | ~45 | ✅ |
| **C12** | Reversibility Registry | registry | ~200 + audit | ~45 | after C7 |
| **C13** | Receipt Ledger | stateful service | ~320 | ~65 | after C7 |
| **C14** | Override | stateful service | ~90 | ~25 | ✅ |
| **C15** | **Constitutional Kernel** | engine | ~400 | ~90 | after C7–C14 |
| **C16** | Execution Path Unification | modification | ~150 | ~40 | after C15 |
| **C17** | Objective Engine | engine | ~400 | ~90 | ⚠ **blocked on ADR** |
| **C18** | Learning Subscriber | adapter | ~110 | ~30 | after C13, C15 |
| **C19** | Vigilance Attestation | registry + service | ~200 | ~45 | ✅ |
| **C20** | Voice Charter Validator | adapter | ~220 | ~50 | ✅ |
| **C21** | Dashboard State | extension | ~140 | ~35 | last |
| | **Remaining total** | | **~3,080** | **~730** | |

**Sprint 1 complete:** ~4,460 source lines, ~975 tests across 21 components.

### 4.1 Why this order

**C7 first** — five downstream consumers, more than any other remaining value object, and C8, C9, C12, C13 all wait on it.

**Value objects before services** — the pattern that has produced six green milestones. Each is independently testable, has no state to corrupt, and cannot be wrong in a way that hides.

**C11 before C15** — extracting the Admission Record as its own value is what lets the Kernel ship while the Objective/Mission ADR is unresolved. Without it, C15 waits on C17, which waits on ratification.

**C14 Override early despite being a service** — it has zero dependencies and Kernel Spec §3.6 requires it to work *"when the rest is degraded."* Building it before the Kernel keeps that independence honest.

**C16 immediately after C15** — the Kernel with no unified path is a gate with a door beside it.

**C20 immediately before C21** — the invariant is *no utterance ever exists un-validated*, and the first utterance arrives with C21.

### 4.2 Components that may run in parallel

`C10`, `C11`, `C14`, `C19` and `C20` have no dependency on `C7`. If sequencing is ever a constraint, these five are independently buildable at any point.

---

## 5 · Risks

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| **R1** | **`Objective`/`Mission` ADR still unratified.** C17 cannot begin. First recorded in the Implementation Blueprint §10 R7; still open. | **Critical** | C11 removes it from the Kernel's critical path. C17 remains blocked until ratified — **this is now the longest-standing blocker in the project.** |
| **R2** | **`Warrant.attestations` does not exist.** Kernel Spec §4.3 lists it; C4 deferred it as additive. Adding it modifies a component tagged green at `c3.0`. | High | Decide before C7 ships. Either add an optional field to `Warrant` with explicit authorization, or have the Kernel hold attestations alongside the warrant. **A decision, not a defect.** |
| **R3** | **C16 collides with uncommitted MB032–039 work.** Both modify `orchestrator/`, `executor/`, `runtime/`, `ai_infrastructure/execution.py`. 59 untracked source files, invisible to git. | **Critical** | **Commit that work before C16 begins.** The window closes when C16 starts; the Baseline Assessment §6.3 rated this ~70% and concentrated entirely in this one component. |
| **R4** | **C13 Receipt Ledger is the first stateful component.** Crash safety, append-only, and "no buffering" foreclose the obvious mitigation for slow writes. | **Critical** | Measure write latency from the first slice run. **Never make the write async** — that is the one change that would void A1. |
| **R5** | **C12's classification audit is easy to underestimate.** ~30 capabilities, each needing a class and a working compensating action. | High | Do it at 30, not 300. Fail closed from day one, so growth cannot outrun governance. |
| **R6** | **C15 exceeds its 600-line ceiling.** Every §3.4 exclusion will eventually be proposed as an inclusion. | High | The ceiling is a review gate, not a guideline. Attestation, never reimplementation. |
| **R7** | **`launcher/boot.py` reads ambient time** in uncommitted work. Two `datetime.now()` calls. | Medium | Must take an injected `Clock` or join `LEGACY_AMBIENT_TIME` before that edit is committed. Unrelated to any component here. |
| **R8** | **`Evidence` still carries two meanings.** Constitution §17's and VEDA 04 B5's Evidence Graph. | Medium | Deferred by founder direction during C6. `test_it_is_independent_of_evidence` keeps `Consequence` from converging with it meanwhile. **Needs an ADR before B5 is built.** |
| **R9** | **Five `Execution*` types will coexist** after C9. | Medium | Each module documents its boundary, as C3 and C5 already do. |
| **R10** | **Sprint scope is large.** 15 components, ~3,080 lines, ~730 tests remaining. | Medium | The order is dependency-correct, so scope can be cut from the tail (C19–C21) without invalidating anything before it. |

---

## 6 · Recommendation

**Resume implementation at C7.**

Three reasons it is the correct next component:

**It is the Kernel's core loop.** Kernel Spec §7.3 — *"the Kernel verifies each attestation's presence, attestor identity, subject match, and freshness. It never re-derives the verdict."* That is the whole design, and the type it operates on does not exist.

**It has the widest reach.** Five downstream consumers — C8, C9, C12, C13, C15 — more than any other remaining value object. Four components are waiting on it.

**Its terminology is clean.** Zero occurrences in the codebase, absent from Constitution §17's frozen terms. `KernelRefusal` needs qualifying first; `Attestation` does not.

**One decision is needed before it ships, not before it starts** (R2): whether `Warrant` gains an optional `attestations` field, or the Kernel holds them alongside. The work on C7 is identical either way; only its integration differs.

**Two things should happen in parallel with implementation, and neither blocks C7:** ratify the `Objective`/`Mission` ADR (R1), and commit the MB032–039 work before C16 (R3).

---

> **The next implementation component is C7 — Attestation.**

---

*Reconciliation document. No code, no commits, no tags. No architecture designed, no shipped component modified, and `SPRING_1_IMPLEMENTATION_PLAN.md` left untouched. All shipped figures measured directly from the source and test suite on 2026-08-05; all estimates calibrated against the six shipped components.*
