# Sprint 1 Implementation Plan

**Filename as specified in the brief.** (`SPRING_1` — preserved verbatim rather than corrected to `SPRINT_1`, so the brief and the artifact match.)

**Type:** Engineering execution plan. No architecture designed or redesigned.
**Date:** 2026-08-05
**Goal:** one real founder objective, start to finish, with a constitutional receipt.
**Governed by (frozen):** VEDA 01–04 · Constitutional Execution Path Report · Constitutional Kernel Specification v1.0 · Objective Engine Specification v1.0 · First Founder Journey Specification v1.0.

**Terminology:** `Warrant` is used for the Kernel token per Objective Engine Spec §13.1 Conflict A. If that amendment is declined, substitute the Kernel's current term.

---

## 1 · Current State

Measured directly from the tree on 2026-08-05. No assumptions.

### 1.1 What exists

| Area | State | Files |
|---|---|---|
| Execution path | **Working.** `Orchestrator.execute_capability()` resolves → gates → invokes. `LocalExecutor` + Action Contract is the single validated inner door. | `orchestrator/`, `executor/` (29 files) |
| Capabilities | ~30 across 7 plugins. 32 Action implementations. | `plugins/`, `executor/actions/`, `desktop/`, `ai_infrastructure/executive/` |
| Permission System | **Working, in-memory.** `check()` gates above `READ_ONLY`; `ONCE` consumed atomically; `ALWAYS_FOR_CAPABILITY` never satisfies `IRREVERSIBLE`. | `permissions/permission_system.py` (101 lines) |
| Approval queue | **Working.** Delegates grants to the Permission System — not a second ledger. | `mission_control/approvals.py` |
| Runtime | **Working and gated.** `_require_approval()` fails closed with no gate wired. | `runtime/engine.py`, `runtime/approval.py` |
| Broker | **Working.** Decision, budget, admission, occupancy, refusal, ledger, learning. | `broker/` (10 files), `ai_infrastructure/` (22 files) |
| Verification | **Working.** Independent of execution per ADR-0011. | `verification/` (5 files) |
| Persistence | **Working.** `StateStore` protocol, atomic write via `os.replace`, event log. | `persistence/` (7 files) |
| Memory | **Working.** One door in/out, digest dedup, nothing inferred. | `memory/` (10 files) |
| Event Bus | **Working.** The only reporting shape in the system. | `mission_control/events.py` |
| Dashboard | **Working.** Frozen read-model dataclasses; panels render only from these. | `dashboard/` (11 files) |
| Tests | 60+ modules, including AST-based architecture-boundary tests. | `tests/` |

### 1.2 What does not exist

Of VEDA 04's 22 modules: **0 complete, 3 partial, 19 absent.**

| Needed for Sprint 1 | State |
|---|---|
| A1 Receipt Ledger | **Absent** |
| A2 Reversibility Registry | **Partial** — `RiskTier` (3 tiers, 48 declarations) and `PermissionCategory` exist. No compensating actions. No fail-closed on unclassified. |
| A3 Override | **Absent** |
| Constitutional Kernel | **Absent** |
| Objective Engine | **Absent** as specified. `mission_control/Objective` is a task container, not an outcome owner. |
| Canonical Clock | **Absent** — see 1.3 |
| Principal model | **Absent** — `decided_by="founder"` is a string literal |
| D2 Voice Charter | **Absent** |
| D7 Vigilance | **Absent** |

### 1.3 The three live defects Sprint 1 must not inherit

**D-1 · Ambient time. 106 call sites across 40 files.** `datetime.now(UTC)` read directly. VEDA 04 §7 requires one canonical timezone source with no ambient local time in the decision path.

**Important nuance:** the *injection pattern* already exists and is well established — `ai_infrastructure/execution.py:178`, `occupancy.py:50`, `runtime/engine.py:78` all take an injected clock, and MB038 states the discipline explicitly. **What is missing is a canonical implementation to inject.** Component 1 is therefore not introducing a discipline; it is giving an existing one a home.

**D-2 · Multiple execution entry points.** `execute_plan()` documents itself as "not the mission path" and `cli.py:807` calls it. `PluginGateway.invoke()` has no internal permission check.

**D-3 · Retry multiplies grants.** `_execute_with_retry()` loops after one `_require_approval()`.

### 1.4 What Sprint 1 does not touch

`broker/` · `ai_infrastructure/` (except the one Kernel call site) · `verification/` · `memory/` · `mission_control/` coordination · `plugins/` contracts · all 32 Actions.

**Not one Action changes.** They gain a registry entry, not a code edit.

---

## 2 · Required Components

Twelve. Each states why Sprint 1 cannot run without it.

| # | Component | Why required | Build |
|---|---|---|---|
| **C1** | **Canonical Clock** | Every receipt, expiry, undo window, and freshness check needs one time source. Retrofitting it later re-dates every record written before it. | **New** |
| **C2** | **Principal** | A1 requires an actor on every intent. VEDA 04 R10: model it now while only one exists. | **New** |
| **C3** | **Reversibility Registry** | The Kernel's A2 attestation. Fails closed. The ledger write needs a real compensating action. | **Extend** existing `RiskTier` |
| **C4** | **Receipt Ledger** | K3. Nothing executes without it. | **New** |
| **C5** | **Override** | K2, and the founder's revocation anchor. | **New** |
| **C6** | **Constitutional Kernel** | The whole point of the sprint. | **New** |
| **C7** | **Execution path unification** | Without it, A1 has holes, which VEDA 04 R1 rates worse than no spine. | **Modify** |
| **C8** | **Objective Engine** | Admission, validation V1–V5, envelope, consequence ceiling, criteria. K1's anchor. | **New** |
| **C9** | **Voice Charter Validator** | Zero dependencies. Built now, every utterance is compliant by construction; built later, all are retro-validated. | **New** |
| **C10** | **Learning Subscriber** | Records Kernel events. Proves the one-way contract. | **New** (thin) |
| **C11** | **Vigilance Attestation** (one domain) | *"Current as of this morning"* is unsayable without it. | **New** (minimal) |
| **C12** | **Dashboard state** | Screen 01: the voice, one decision, the receipt. | **Extend** `readmodel.py` |

### 2.1 Deliberately out of Sprint 1

| Excluded | Why | When |
|---|---|---|
| C1 Standing Rule Engine | Needs A1 + timers. The slice's one approval is `ONCE`. | Sprint 2 |
| Durable Timer Service | Day 1 has no long-horizon timer. Silence defaults arrive with B4. | Sprint 2 |
| B1 Consequence Engine | The quartet is `pending_consequence_engine` per Kernel Spec §14.1 | Sprint 2 |
| C3 Proposal Miner | Needs 30 days of decisions | Sprint 3 |
| C5 Self-Audit | Ships **with** C3, never after | Sprint 3 |
| D3 Mistake Protocol | Day 12 of the journey | Sprint 2 |
| Departments | VEDA 05 under amendment | — |

**On the sprint success metric.** The brief requires *"Vedra learns. Vedra proposes one future improvement."* Sprint 1 delivers the **mechanism** — the event stream, the decision provenance, the receipt corpus — and the proposal itself arrives in Sprint 3, because a proposal from one day of data would be inference from too few points and C1 would reject its guessed cap as malformed. **The injectable Clock (C1) is what makes the 30-day proposal testable in seconds rather than in a month**, which is the honest way to demonstrate it early.

---

## 3 · Build Order

```
                    ┌───────────────────────────────────┐
   LAYER 0          │  C1 CANONICAL CLOCK               │  ◄── no dependencies
   foundation       │  now · stamp · founder-local ·    │      everything needs it
                    │  monotonic · ambient prohibition  │
                    └───────────────┬───────────────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              ▼                     ▼                     ▼
       ┌─────────────┐      ┌──────────────┐      ┌──────────────┐
       │ C2 PRINCIPAL│      │ C3 REVERSIB- │      │ C9 VOICE     │
       │ (no deps,   │      │ ILITY REG.   │      │ CHARTER      │
       │  ordered    │      │ fails closed │      │ (no deps —   │
       │  here for   │      │              │      │  built early │
       │  A1)        │      │              │      │  on purpose) │
       └──────┬──────┘      └──────┬───────┘      └──────────────┘
              │                    │
              └────────┬───────────┘
                       ▼
              ┌──────────────────┐         ┌──────────────┐
   LAYER 1    │ C4 RECEIPT LEDGER│         │ C5 OVERRIDE  │
   trust      │ append-only ·    │         │ outside the  │
   spine      │ intent→outcome · │         │ main path    │
              │ StateStore-backed│         │ by design    │
              └────────┬─────────┘         └──────┬───────┘
                       └────────────┬─────────────┘
                                    ▼
                    ┌───────────────────────────────────┐
   LAYER 2          │  C6 CONSTITUTIONAL KERNEL         │
   authority        │  authorize · attempt · settle ·   │
                    │  invalidate                        │
                    └───────────────┬───────────────────┘
                                    │
              ┌─────────────────────┼──────────────────┐
              ▼                     ▼                  ▼
       ┌─────────────┐      ┌──────────────┐   ┌──────────────┐
   L3  │ C7 PATH     │      │ C8 OBJECTIVE │   │ C10 LEARNING │
       │ UNIFICATION │      │ ENGINE       │   │ SUBSCRIBER   │
       │ warrant_id  │      │ K1's anchor  │   │ one-way      │
       │ required    │      │              │   │              │
       └──────┬──────┘      └──────┬───────┘   └──────────────┘
              └────────┬───────────┘
                       ▼
              ┌──────────────┐      ┌──────────────┐
   L4         │ C11 VIGILANCE│      │ C12 DASHBOARD│
   surface    │ one domain   │      │ state        │
              └──────┬───────┘      └──────┬───────┘
                     └──────────┬──────────┘
                                ▼
                    ┌───────────────────────┐
                    │  THE SLICE RUNS       │
                    └───────────────────────┘
```

### 3.1 Why C1 is first, and why nothing overlaps it

**Clock has no dependencies and 106 existing call sites.** Every record written before it exists carries a timestamp of unknown provenance. Every component after it takes an injected clock from the start, so no component is ever written against ambient time and later corrected.

**No overlapping work:** C2, C3, and C9 are independent of each other and could proceed in parallel *after* C1 — but each takes a clock, so none can be finished before it. Starting anywhere else means writing code that C1 will later change.

### 3.2 Zero-rework check per component

| Component | *Correct after 300 capabilities?* |
|---|---|
| C1 Clock | Yes. Capability count irrelevant. |
| C3 Registry | Yes — **only because it fails closed.** An unclassified capability is non-executable, so growth cannot outrun governance. |
| C4 Ledger | Yes for append-only local sequential. Retention/compaction is a storage decision, never a correctness one. |
| C6 Kernel | Yes. Holds no capability list; 3 checks + 8 attestation validations, all O(1). |
| C8 Objective Engine | Yes. Never enumerates capabilities. |
| C7 Path unification | Yes — **because `warrant_id` is a required argument, not a convention.** |

---

## 4 · File-Level Plan

### 4.1 Created

| File | Component | Purpose |
|---|---|---|
| `src/master_agent/foundation/__init__.py` | C1 | Package |
| `src/master_agent/foundation/clock.py` | C1 | `Clock` protocol, `Instant`, `SystemClock`, `ManualClock` |
| `src/master_agent/foundation/principal.py` | C2 | `Principal`, `PrincipalRegistry` |
| `src/master_agent/reversibility/__init__.py` · `registry.py` | C3 | `ReversibilityClass`, `Classification`, `ReversibilityRegistry` |
| `src/master_agent/receipts/__init__.py` · `ledger.py` · `records.py` | C4 | `ReceiptLedger`, `IntentRecord`, `AttemptRecord`, `OutcomeRecord` |
| `src/master_agent/override/__init__.py` · `switch.py` | C5 | `OverrideSwitch` |
| `src/master_agent/kernel/__init__.py` · `kernel.py` · `warrant.py` · `attestation.py` · `refusal.py` | C6 | The Kernel |
| `src/master_agent/objectives/__init__.py` · `objective.py` · `engine.py` · `validation.py` | C8 | Objective Engine |
| `src/master_agent/voice/charter.py` | C9 | Utterance validator |
| `src/master_agent/learning/subscriber.py` | C10 | Kernel event recorder |
| `src/master_agent/vigilance/__init__.py` · `attestation.py` | C11 | Domain registry + attestation |

### 4.2 Modified

| File | Change | Risk |
|---|---|---|
| `config.py` | `+ ClockConfig`, wired into `MasterAgentConfig` | Low |
| `orchestrator/orchestrator.py` | `execute_capability()` becomes the gate; **delete `execute_plan()`** | **High — the invasive one** |
| `executor/executor.py` | `run()` gains `warrant_id`; optional in Sprint 1, mandatory in Sprint 2 | **Highest blast radius, deliberately** |
| `runtime/gateway.py` | `PluginGateway` routes through the Kernel | Medium |
| `runtime/engine.py` | Retry threads one warrant through N attempts | Low |
| `ai_infrastructure/execution.py` | Calls the Kernel. **Broker logic untouched.** | Medium |
| `cli.py` | Stops calling `execute_plan()` | Low |
| `dashboard/readmodel.py` | `+ ObjectivePanel`, `+ ReceiptPanel` frozen dataclasses | Low |

### 4.3 Untouched

`broker/**` · `ai_infrastructure/**` except one call site · `verification/**` · `memory/**` · `persistence/**` · `mission_control/**` · `plugins/**` · `executor/actions/**` (all 32) · `desktop/**` · `providers/**`

### 4.4 Abstractions deliberately not created

| Not created | Why |
|---|---|
| A Skill Registry | §5.1 of the Constitution: one Capability Registry. Add an index, never a registry. |
| A second event bus | `mission_control/events.py` is the only reporting shape in the system |
| A Kernel middleware/plugin system | The Kernel has four operations. A plugin point is where the constitution becomes negotiable. |
| A generic "Policy" abstraction | Three checks and eight attestations, named. Not configurable. |
| An ORM or migration layer | `StateStore` exists and is sufficient |

---

## 5 · Interfaces

Signatures only. No implementation.

### C1 · Clock

```
Instant:            moment: datetime (aware, UTC) · sequence: int

Clock (Protocol):
    now()        -> datetime          canonical UTC
    stamp()      -> Instant           monotonic, ordered within a process
    to_founder_local(dt) -> datetime  zone from config, never system-ambient

SystemClock(founder_timezone: str, source: Callable[[], datetime] | None)
    .backward_steps -> int            observability: clock regressions seen
    .largest_regression -> timedelta

ManualClock(start: datetime, founder_timezone: str)
    .advance(delta) -> None           tests advance time explicitly
    .set(moment) -> None
```

### C2 · Principal

```
Principal:          principal_id: str · display_name: str · kind: founder|delegate|system
PrincipalRegistry:  founder() -> Principal · resolve(id) -> Principal | None
```

### C3 · Reversibility Registry

```
ReversibilityClass: READ_ONLY | REVERSIBLE | REVERSIBLE_UNTIL | IRREVERSIBLE

Classification:     capability · cls · compensating_capability: str | None
                    · undo_window: timedelta | None

ReversibilityRegistry:
    register(Classification) -> None
    classify(capability) -> Classification        raises Unclassified — fails closed
    is_classified(capability) -> bool
```

### C4 · Receipt Ledger

```
ReceiptLedger:
    record_intent(IntentRecord) -> str            raises LedgerUnavailable
    record_attempt(AttemptRecord) -> None
    record_outcome(OutcomeRecord) -> None
    read(filter) -> list[Record]
    # no update. no delete. at any privilege level.
```

### C5 · Override

```
OverrideSwitch:
    suspend(reason) -> None      # no confirmation parameter exists
    resume() -> None
    is_suspended() -> bool
```

### C6 · Kernel

```
Kernel:
    authorize(ExecutionRequest) -> Warrant | Refusal
    attempt(warrant_id)         -> AttemptToken | Refusal
    settle(warrant_id, Outcome) -> Receipt
    invalidate(scope, reason)   -> int
```

### C8 · Objective Engine

```
ObjectiveEngine:
    draft(statement, creator) -> Objective
    validate(objective)       -> ValidationResult      V1..V5
    admit(objective, envelope, approval_ref) -> AdmissionRecord
    record_criterion(objective_id, criterion_id, verdict, evidence_id) -> None
    complete(objective_id)    -> Objective | CriteriaOutstanding
    terminate(objective_id, reason, kind) -> Objective
```

### C9 · Voice Charter

```
validate(utterance) -> ValidationResult(passed, violations[])
enforce(utterance, fallback) -> str          # no bypass parameter exists
```

---

## 6 · Acceptance Criteria

Measurable. Each is a test, not a review.

**C1 Clock — DONE means:** one canonical `now()`; `stamp()` strictly increasing across 10,000 calls including within one millisecond; a backward wall-clock step never produces a decreasing instant and increments an observable counter; `ManualClock` advances only when told; `to_founder_local` uses configured zone, never system local; **an AST test fails the build if any new module reads ambient time**, with a legacy allowlist that can only shrink.

**C2 Principal — DONE means:** every intent carries a resolved principal; an unresolvable principal is a refusal, not a default.

**C3 Registry — DONE means:** all ~30 capabilities classified; `classify()` on an unknown capability raises; every `REVERSIBLE_UNTIL` names a compensating capability that exists in the Capability Registry and a non-zero window; **no default classification exists in the code.**

**C4 Ledger — DONE means:** append-only with no update/delete at any privilege level; intent precedes outcome for every record; a simulated write failure prevents execution; kill -9 mid-write leaves the previous good state; records survive restart and reload in issue order.

**C5 Override — DONE means:** `suspend()` blocks all minting within one clock tick; queueing continues; no confirmation parameter exists in the signature; reachable when the Kernel's dependencies are degraded.

**C6 Kernel — DONE means:** K1/K2/K3 performed; 6–8 attestations validated for identity, subject, and freshness; a missing/stale/mismatched attestation refuses; a warrant exceeding the objective's consequence ceiling refuses; one warrant carries N attempts and one outcome; **an irreversible capability is never auto-retried.**

**C7 Path — DONE means:** an AST test asserts no module reaches `plugin.invoke()` or `LocalExecutor.run()` outside the allowlist; `execute_plan()` no longer exists; every Sprint-1 execution produces a receipt pair.

**C8 Objective Engine — DONE means:** V1–V5 enforced; an objective with no machine-checkable criterion is refused; an objective without a due or review date is refused; completion requires every criterion verified; no percentage field exists anywhere in the model.

**C9 Voice Charter — DONE means:** every journey utterance passes; a percentage, an exclamation mark, an emoji, a stacked hedge, and a celebration each fail; no bypass parameter exists.

**C10 Learning — DONE means:** every Kernel event reaches the subscriber; the subscriber returns nothing; a raising subscriber does not affect execution; zero subscribers is a valid configuration.

**C11 Vigilance — DONE means:** the receipts folder is registered with a freshness window; `attest()` returns incomplete when stale; **the calm-state string is unconstructable without a complete attestation.**

**C12 Dashboard — DONE means:** Screen 01 renders the voice, one decision, and the receipt; no objective count, no progress bar, no badge exists in the read model.

---

## 7 · Testing Strategy

Four layers. **Every constitutional guarantee becomes a test** — that is the NASA verification principle applied: verified by test, not by review.

### 7.1 Unit
Per component, against its interface. Deterministic — `ManualClock` everywhere, no test reads a wall clock.

### 7.2 Integration
`tests/test_slice_day_one.py` — the full Day-1 journey against a fixture receipts folder, a stub extraction provider, and a real Kernel over an in-memory ledger. Asserts: 1 approval, N warrants, N receipt pairs, 6 honest failures recorded, ledger written, criteria verified.

### 7.3 Constitutional — one test per guarantee

| Test | Guarantee |
|---|---|
| `no execution without an objective` | K1 |
| `no execution without classification` | A2, fails closed |
| `no execution without a receipt written first` | K3 |
| `no execution when ledger unavailable` | §11.3 — no buffering |
| `no execution when override active` | K2 |
| `warrant cannot exceed the objective's ceiling` | Envelope |
| `warrant is not reusable for a different payload` | Digest binding |
| `irreversible is never auto-retried` | Retry §8.4 |
| `one warrant, N attempts, one outcome` | Retry model |
| `receipts cannot be mutated or deleted` | Append-only |
| `learning cannot block or veto` | Eng. Law V |
| `objective with no checkable criterion is refused` | V2 |
| `no percentage crosses to the founder` | B6 / §7.2 |
| `calm state unconstructable without attestation` | D7 |
| `no ambient time in new modules` | §7 clock |
| `no execution path outside the gate` | R1 |

### 7.4 Failure tests — adversarial, one per known bypass

Each attempts the bypass and asserts refusal: gateway with no kernel · plugin invoked directly · fabricated `warrant_id` · expired warrant · reused warrant · execution with no objective · ledger down · override active · irreversible retry · unclassified capability.

**This suite grows by one test per entry point discovered, forever.** It is the institutional memory of the execution-path audit.

### 7.5 Test rules

- No test obtains a warrant except from a real Kernel over an in-memory ledger. **A test-only bypass is a production bypass with a comment on it.**
- No test reads a wall clock.
- Existing 60+ test modules must stay green **untouched** — that is the proof the sprint is integration and not redesign.

---

## 8 · Demonstration Path

At sprint completion, from a cold start.

```
1.  kalpavriksha
        Screen 01. Empty. The tree, dim.

2.  FOUNDER: "Keep a current picture of everything I'm committed to paying.
              The receipts are in Documents/Receipts."

3.  VEDRA:   "How would you know this was right — is it enough that every
              recurring charge I can find is listed, with the document it
              came from?"                              ← V2, one question

4.  FOUNDER: "Yes. And tell me if you can't read something."
                                                        ← becomes criterion C3

5.  VEDRA:   "I'll read that folder and keep a file at commitments.md.
              I need to write to that one file — nothing else. I'll keep
              the previous version for a day. I won't cancel or pay
              anything."                                ← the ONE approval

6.  FOUNDER: approves.

7.  ~40 seconds. No progress bar.

8.  VEDRA:   "You're committed to ₹1,84,600 a month across twenty-three
              services. Three renew this week. One — Sentry, ₹7,200 — I
              can't find any usage of since March. Six documents I
              couldn't read. I haven't changed anything."

9.  FOUNDER opens commitments.md. Twenty-three rows, each linked to a PDF.

10. FOUNDER: "show me the receipt"
        94 intent/outcome pairs. Every one names objective, actor,
        capability, class, and grant. Six settled `failed`, named.

11. FOUNDER: "try to cancel Sentry"
        VEDRA: "I can't. This objective is limited to changes I can undo,
                and cancelling isn't one. If you want that, it's a new
                objective and I'll need you to approve it directly."
                                     ← THE demonstration. The ceiling holds.

12. Operator runs: pytest tests/ -k constitutional
        16 constitutional guarantees, green.
```

**Step 11 is the sprint's actual proof.** Steps 1–10 show competence; step 11 shows the boundary is mechanical rather than promised.

---

## 9 · Architectural Risks Remaining

| # | Risk | Mitigation in this sprint |
|---|---|---|
| **1** | `executor.run()` signature change touches every Action's call site | `warrant_id` **optional** in Sprint 1 with a loud warning; mandatory in Sprint 2 once the warning count is zero |
| **2** | `Objective`/`Mission` ADR unratified — this sprint's Objective Engine could become a third model | **Blocking.** Ratify before C8. C1–C7 are unaffected and proceed. |
| **3** | `Warrant` rename unratified (Kernel Spec §13.1 A) | Blocks C6's public names only. C1–C5 unaffected. |
| **4** | Ledger write latency lands on every action | Measured from the first slice run. **Never solved by making the write async.** |
| **5** | The 106 ambient-time call sites are not all migrated in Sprint 1 | Legacy allowlist that **can only shrink**, enforced by a test that fails when a listed file is cleaned |
| **6** | Extraction quality unknown (41/47 is an estimate) | Criterion C3 makes the ratio visible rather than assumed |

---

## 10 · Component 1 Handoff

Per the brief, implementation stops after component one. **C1 — the Canonical Clock — is delivered in the next section for review.**

Everything else in this plan is scheduled, not started.

---

*Engineering plan. No architecture designed or redesigned. Current state verified directly against `src/master_agent/` and `MIRACLE_LEDGER.md` on 2026-08-05.*
