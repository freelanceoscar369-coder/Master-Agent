# Kalpavriksha Implementation Blueprint v1.0

**Type:** Engineering execution blueprint. Not a VEDA. No architecture designed, no philosophy invented, no frozen document reinterpreted.
**Date:** 2026-08-05
**Governs:** implementation order, ownership, and traceability for VEDA 01–04 requirements against the existing codebase.
**Constitutional inputs (frozen, obeyed as written):** VEDA 01 Experience · VEDA 02 Design Constitution · VEDA 03 Founder Dashboard · VEDA 04 Architecture Requirements · KALPAVRIKSHA_VISION_V2 (Constitution).
**Excluded:** VEDA 05, which is under amendment. Nothing here depends on it. Where a VEDA 05 concept would occupy a slot, the slot is named and left empty.

**Every recommendation in this document answers one question: does it reduce future rework while preserving the VEDAs?** Recommendations that only improve elegance are absent by design.

---

## 0 · Ground truth — what exists today

Measured directly from the tree, not from the roadmap.

| | |
|---|---|
| Shipped Miracles | 26 (001 → 035) |
| Source | ~31,000 lines across 23 packages |
| Tests | 60+ test modules, including architecture-boundary tests |
| Constitution compliance | Strong. Layer separation, capability contract, and plugin boundary are enforced by tests, not convention. |

### 0.1 The headline finding

**The codebase implements the Constitution's execution spine to a high standard, and implements almost none of VEDA 04's Trust Spine.**

Of VEDA 04's 22 required modules:

| State | Count | Modules |
|---|---|---|
| Complete | **0** | — |
| Partial | 3 | A2 (risk tiers + `IRREVERSIBLE` category exist; no compensating actions, no fail-closed on unclassified) · B3 (a routing queue exists; no novel/irreversible/excluded classification) · B4 (a defer timer exists; no declared default per request) |
| Absent | 19 | A1, A3, A4, B1, B2, B5, B6, C1–C7, D1–D7, E1–E3 |

This is not a criticism of the work done. Miracles 001–035 built the layer VEDA 04 assumes and does not describe: a validated, permission-gated, logged execution path with real capabilities behind it. VEDA 04's own §2 says the migration is "the insertion of a decision and consequence layer between planning and execution." **That layer is the remaining work, and the existing code is the thing it inserts into.**

### 0.2 The three assets that most reduce future rework

These already exist and change the cost of everything below.

1. **A single validated execution path.** `LocalExecutor` + the Action Contract (Miracle 002) plus `Orchestrator.execute_capability()` — resolve, gate, invoke — is exactly the "single enforcement point" VEDA 04 R1 prescribes as the mitigation for its most severe risk. A1 can be inserted at one place rather than audited across many.
2. **A capability surface still small enough to classify.** Roughly 25–30 registered capabilities. VEDA 04 R2 calls reversibility classification "a large one-time audit that is easy to underestimate." At 30 capabilities it is a week. At 300 it is a quarter, and it will be done badly.
3. **Architecture tests that already enforce boundaries.** `test_dashboard_architecture.py`, `test_mission_control_architecture.py`, `test_capability_contract.py`, `test_browser_constitution_compliance.py`. The mechanism for enforcing every invariant in this blueprint already exists and is trusted.

### 0.3 The one liability that grows daily

**There is more than one way to reach a tool.** `Orchestrator.execute_capability()` is the intended gate, but `TaskDispatcher`'s own docstring says an *outside caller* performs the work; the Runtime, the Browser Worker lifecycle facade, and the Desktop Executive each have their own invocation surface; and `Orchestrator.execute_plan()` is explicitly documented as a demo path, not the mission path.

VEDA 04 R1: *"If actions can currently execute without passing a checkpoint, every such path is a hole, and holes in an audit spine are worse than no spine because they create false confidence."*

**Every capability added before the paths are unified adds to a migration that is currently small.** This is the single most time-sensitive item in this document.

---

## 1 · Executive Summary

### 1.1 What this blueprint concludes

**The architecture does not need to change. The build order does.** Nine specific items are currently scheduled — implicitly or in VEDA 04 §9 — later than their *earliest safe build point*. Each one, built late, forces a retro-audit of everything written before it. Each one, built early, makes everything after it compliant by construction.

VEDA 04 §9's six phases and their gates are preserved exactly as written. This blueprint:

- adds a **Phase −1 (Foundation)** that VEDA 04 assumes and never names — a clock, a principal, a durable timer, and a unified execution path;
- identifies **three modules whose earliest safe build point precedes the phase they are listed in** (building early never violates a gate — every VEDA 04 gate is of the form "cannot proceed until X exists");
- names **four impending duplications** that will occur by default if nothing prevents them.

### 1.2 The five recommendations that matter most

**R-A · Unify the execution path before writing another capability.** One gate, asserted by an architecture test that fails the build if any code reaches `plugin.invoke()` or `LocalExecutor.run()` by another route. *Cost now: days. Cost after 200 capabilities: a quarter, done under pressure, with holes.*

**R-B · Run the reversibility classification audit at 30 capabilities, not at 300.** Fail-closed from the first day it exists: unclassified means non-executable. Every capability written afterwards must declare a class and a compensating action to compile.

**R-C · Do not persist permission grants until the Standing Rule Engine exists.** `PermissionSystem` is an in-memory grant set with a `ALWAYS_FOR_CAPABILITY` scope that has no expiry. VEDA 04 C2: *a permission with no end date cannot be persisted.* It is compliant today only because it is not durable. **Adding persistence to the existing shape converts an accident into a constitutional violation** and creates a migration of live founder grants.

**R-D · Build the Voice Charter Validator (D2) in Phase 0, not Phase 2.** It has zero dependencies — it is a pure function over a string. Every utterance written before it exists must be retro-validated; every one after is compliant by construction. VEDA 04 R4 rates model-personality reassertion as high severity *and recurring forever*. The regression suite it needs is cheapest to start when there are ten utterances, not four hundred.

**R-E · Build one Durable Timer Service in Phase −1.** B4 (silence defaults, days), C2 (rule expiry, months), C7 (dependency audit, a year), undo windows (seconds), and freshness windows (minutes) are five consumers of one capability. VEDA 04 names none of them as a module. **Left unnamed, it will be built three times with three durability guarantees**, and the annual one — the one that must survive every deployment in a year — will be the weakest.

### 1.3 What this blueprint refuses to do

- **No new services.** VEDA 04's 22 modules are capability requirements, not deployment units. §3.4 states the packaging rule explicitly, because a naive 1:1 mapping produces 22 services for a single-founder local-first product, and VEDA 04 §7's latency budgets do not survive network hops.
- **No slice that is already built.** The brief offers "Create Demo folder" as an example. That is Miracle 001, shipped 2026-07-23. §7 explains why it is also the wrong shape for this phase and proposes a superior one.
- **No resolution of frozen-term collisions.** Three are found (§9). Each requires an ADR and ratification. This document names them and states which work must not start until they are settled.

---

## 2 · Dependency Graph

Arrows mean *must exist and be correct before*. Nothing here is stylistic ordering; every edge is a hard dependency where building the dependent first produces rework.

```
╔══════════════════════════════════════════════════════════════════════════════╗
║  PHASE −1 · FOUNDATION — assumed by VEDA 04, named by no VEDA                 ║
╚══════════════════════════════════════════════════════════════════════════════╝

   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌───────────────────┐
   │ CLOCK        │  │ PRINCIPAL    │  │ StateStore   │  │ EXECUTION PATH    │
   │ one canonical│  │ entity model │  │ ✓ EXISTS     │  │ UNIFICATION       │
   │ tz source    │  │ (R10)        │  │ persistence/ │  │ one gate, asserted│
   └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └─────────┬─────────┘
          │                 │                 │                    │
          └────────┬────────┴────────┬────────┘                    │
                   ▼                 ▼                             │
          ┌─────────────────┐  ┌──────────────────┐                │
          │ DURABLE TIMER   │  │ DOMAIN REGISTRY  │                │
          │ SERVICE         │  │ what is watched, │                │
          │ s → years       │  │ freshness window │                │
          └────────┬────────┘  └────────┬─────────┘                │
                   │                    │                          │
╔══════════════════╪════════════════════╪══════════════════════════╪═══════════╗
║  PHASE 0 · TRUST SPINE — VEDA 04 Layer A. Nothing autonomous ships before it. ║
╚══════════════════╪════════════════════╪══════════════════════════╪═══════════╝
                   │                    │                          │
   ┌───────────────┴──────┐             │        ┌─────────────────┴──────────┐
   │ A2 REVERSIBILITY     │             │        │ A1 RECEIPT LEDGER          │
   │ REGISTRY             │─────────────┼───────►│ append-only · intent→exec  │
   │ fails closed         │  classification      │ →outcome · idempotent      │
   └──────────┬───────────┘  is a field on       └─────────┬──────────────────┘
              │              every intent                  │
              │                                            │
   ┌──────────┴───────────┐   ┌──────────────────┐         │
   │ A3 OVERRIDE          │   │ D2 VOICE CHARTER │         │  ← D2 has NO deps.
   │ outside the main path│   │ VALIDATOR        │         │    Listed Phase 2
   │ by design            │   │ pure function    │         │    in VEDA 04;
   └──────────────────────┘   └────────┬─────────┘         │    safe here. R-D.
                                       │                   │
╔══════════════════════════════════════╪═══════════════════╪═══════════════════╗
║  PHASE 1 · JUDGMENT — VEDA 04 Layer B                     │                   ║
╚══════════════════════════════════════╪═══════════════════╪═══════════════════╝
                                       │                   │
   ┌───────────────────┐   ┌───────────┴──────┐   ┌────────┴─────────┐
   │ B1 CONSEQUENCE    │◄──┤ COST MODEL       │   │ B5 EVIDENCE      │
   │ ENGINE            │   │ ✓ EXISTS         │   │ GRAPH            │
   │ quartet or error  │   │ broker/cost.py   │   │ (name collision  │
   └─────────┬─────────┘   └──────────────────┘   │  — see §9.1)     │
             │                                     └────────┬─────────┘
             ├────────────────┬──────────────────┐          │
             ▼                ▼                  ▼          ▼
   ┌──────────────┐  ┌────────────────┐  ┌──────────────────────────┐
   │ B3 ESCALATION│  │ B4 SILENCE     │  │ B2 RANKING               │
   │ ROUTER       │  │ DEFAULTS       │  │ frozen function, VEDA 03 │
   │ 3 triggers   │  │ needs TIMER    │  │ + mandatory justification│
   └──────┬───────┘  └───────┬────────┘  └────────────┬─────────────┘
          │                  │                        │
          └──────────────────┴────────────────────────┘
                             │
                    ┌────────┴─────────┐
                    │ OPEN REQUEST SET │  ← ONE ranked set. Three queues
                    │ single, ranked   │    exist today (§9.2). They collapse
                    └────────┬─────────┘    here or the founder sees three.
                             │
╔════════════════════════════╪═════════════════════════════════════════════════╗
║  PHASE 2 · EXPRESSION — VEDA 04 Layer D                                       ║
╚════════════════════════════╪═════════════════════════════════════════════════╝
                             │
   ┌─────────────┐  ┌────────┴────────┐  ┌──────────────┐  ┌─────────────────┐
   │ D4 PRESENCE │  │ D1 NARRATION    │  │ D7 VIGILANCE │  │ D3 MISTAKE      │
   │ real work   │  │ one generation, │  │ ATTESTATION  │  │ PROTOCOL        │
   │ signals only│  │ two renderings  │  │ needs DOMAIN │  │ ungated path to │
   └─────────────┘  └────────┬────────┘  │ REGISTRY     │  │ D1 — never      │
                             │           └──────┬───────┘  │ through ranking │
                             └──────┬───────────┘          └────────┬────────┘
                                    ▼                               │
                          ┌───────────────────┐                     │
                          │ D6 BRIEF COMPOSER │◄────────────────────┘
                          │ quiet-day variant │
                          │ is a FIRST-CLASS  │
                          │ path, not empty   │
                          └─────────┬─────────┘
                                    │
╔═══════════════════════════════════╪══════════════════════════════════════════╗
║  PHASE 3 · AUTONOMY — VEDA 04 Layer C. The line starts moving.                ║
╚═══════════════════════════════════╪══════════════════════════════════════════╝
                                    │
   ┌────────────────────────────────┴──────────┐
   │ C1 STANDING RULE ENGINE                    │  ← SUBSUMES the existing
   │ 5 mandatory parts · atomic cumulative caps │    PermissionSystem. Do not
   │ needs A1 (receipt binding) + TIMER + PRIN- │    persist grants before this
   │ CIPAL. Depends on A1; A1 never on C1.      │    exists. R-C.
   └──────┬──────────────────────┬──────────────┘
          │                      │
   ┌──────┴───────┐   ┌──────────┴──────────┐   ┌────────────────────────┐
   │ C2 EXPIRY    │   │ C4 BOUNDARY SERVICE │   │ C5 SELF-AUDIT          │
   │ DAEMON       │   │ = A PROJECTION OF A1│   │ ships WITH C3, never   │
   │ needs TIMER  │   │ sole autonomy truth │   │ after                  │
   └──────────────┘   └──────────┬──────────┘   └───────────┬────────────┘
                                 │                          │
                      ┌──────────┴──────────┐    ┌──────────┴───────────┐
                      │ D5 TREE TOPOLOGY    │    │ C3 PROPOSAL MINER    │
                      │ derives from C4     │    │ needs E1 + A1        │
                      │ ONLY (VEDA 01 §9)   │    │ 30-day metric (R8)   │
                      └─────────────────────┘    └──────────────────────┘
                                 ▲
                      ┌──────────┴──────────┐
                      │ VEDA 03 DASHBOARD   │  ← reads C4. Never computes
                      │ autonomy ratio      │    its own number. (C4 invariant)
                      └─────────────────────┘

╔══════════════════════════════════════════════════════════════════════════════╗
║  PHASE 4 · MATURITY   C6 Delegation · E1 Provenance · B6 Confidence · A4      ║
║  PHASE 5 · GOVERNANCE C7 Dependency Audit · E3 Export · E2 Demo Tenant        ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

### 2.1 The one cycle risk, and its resolution

`C1 → A1` (a rule firing writes a receipt) and `A1 → C1` (a receipt names the rule it fired under) reads as circular.

**It is not, and must not be allowed to become so.** A1 carries `ruleRef` as an **opaque identifier field**. It does not resolve it, validate it, or import C1. The dependency is strictly `C1 → A1`. If A1 ever needs to ask C1 anything, the Trust Spine has acquired a dependency on the layer above it and can no longer be the thing everything else is verified against.

**Assert it:** an architecture test forbidding any import of `master_agent.rules` from `master_agent.receipts`.

### 2.2 Three edges that are easy to get backwards

| Looks like | Actually | Why it matters |
|---|---|---|
| Dashboard computes the autonomy ratio | **C4 computes it; dashboard renders it** | VEDA 04 C4: four independently computed autonomy numbers is a guaranteed future inconsistency |
| D5 Tree derives from activity or departments | **D5 derives from C4 only** | VEDA 01 §9: branches come from founder rule grants; the tree is the one measure the product cannot move |
| D7 asks Operations for health | **D7 reads the Domain Registry, which connectors write to** | An intermediary that fails silently converts D7's proof into an assumption |

---

## 3 · Service Ownership Matrix

For each service: what it owns, what it never owns, its API surface, and what must never be copied into it.

### 3.1 Trust Spine

| | **A1 · Receipt Ledger** |
|---|---|
| **Owns** | The immutable record of every action: intent before, outcome after. The only append-only store of what was done. |
| **Never owns** | Rules. Permissions. Decisions. Ranking. Any concept of *why* beyond an opaque `ruleRef`. It never reads anything to decide anything. |
| **API** | `recordIntent(...) → intentId` · `recordOutcome(intentId, ...)` · `readLedger(filter)` · `renderAsProse(filter)` |
| **Never duplicated into** | Nothing recomputes ledger contents. `AuditStream`, `AuditLog`, and `ExecutionLogEntry` become **projections or feeders**, never parallel truths (§9.3). |
| **Invariant** | No update or delete operation exists at any privilege level. Intent write failure aborts the action. |

| | **A2 · Reversibility Registry** |
|---|---|
| **Owns** | The classification of every action type, its compensating action, and its window. |
| **Never owns** | Whether a specific invocation is permitted — that is C1. Whether it happened — that is A1. |
| **API** | `classify(actionType)` · `register(...)` · `compensate(intentId)` |
| **Never duplicated into** | The plugin manifest may *declare* a proposed class; the registry is the only thing that *decides* it. A manifest field read directly by a caller is a second registry. |
| **Invariant** | Fails closed. No default classification exists. "Probably reversible" is unrepresentable. |

| | **A3 · Override** |
|---|---|
| **Owns** | Global suspension of rule firing. |
| **Never owns** | Stopping work or queueing — only deciding. |
| **API** | `suspend()` · `resume()` · `status()` — no confirmation parameter exists in any signature |
| **Architectural note** | Deliberately outside the main orchestration path, so it works when the rest is degraded. It may not import from the Judgment or Autonomy layers. |

### 3.2 Judgment

| | **B1 Consequence · B2 Ranking · B3 Router · B4 Defaults · B5 Evidence Graph** |
|---|---|
| **Collectively own** | The single set of open judgment requests and everything true about them. |
| **Never own** | Execution. Narration wording (B* produce structure; D1 produces prose). Permission grants. |
| **API** | `build(ctx) → quartet` (error, never a partial) · `rank(open) → [{id, position, justification}]` · `classify(decision) → {tier, trigger}` · `scheduleDefault(requestId, action, firingTime)` |
| **Never duplicated** | **One open set.** Three queues exist today (§9.2). Any component holding its own list of things awaiting a human answer is a second open set, and the founder will experience it as a second inbox. |
| **Invariants** | A request missing a quartet field cannot be constructed. A request without a scheduled default cannot exist. Irreversible items can never enter a batchable tier. |

### 3.3 Autonomy

| | **C1 · Standing Rule Engine** |
|---|---|
| **Owns** | Rule definition, evaluation, and cumulative consumption. The single ledger of granted authority. |
| **Never owns** | The record of firings (A1 owns that). Ranking. Narration. The autonomy *number* (C4 derives it). |
| **API** | `define(rule)` — rejects any rule lacking a cumulative cap, exclusions, or expiry · `evaluate(ctx)` · `consume(ruleId, amount)` — atomic · `expire` · `renew` |
| **Never duplicated** | **Subsumes `permissions/PermissionSystem`.** Two grant ledgers is the failure §5.2 of the Constitution exists to prevent. |
| **Invariant** | `define()` rejects malformed rules at definition time, not at firing time. |

| | **C4 · Judgment Boundary Service** |
|---|---|
| **Owns** | The canonical answer to "what is delegated versus escalated," and the autonomy ratio. |
| **Never owns** | Rules themselves. Presentation. |
| **API** | `state()` · `history(period)` · `topology()` |
| **Never duplicated** | **This is the most likely duplication in the entire system.** Four candidate computers of an autonomy number exist or are implied: C4, the dashboard, the tree, and any departmental metric. VEDA 04 C4 names this exact failure. Every consumer reads here; none computes. |
| **Implementation recommendation** | Build it as a **projection of A1 + C1**, per VEDA 04 §7. A derived value cannot disagree with its source. |

### 3.4 The packaging rule — modules are not services

**VEDA 04's 22 modules are capability requirements, not deployment units.** For Founder Edition, the correct packaging is:

| Deployment unit | Contains |
|---|---|
| **One local process** | Everything. All 22 modules as in-process packages. |
| Separate durable stores | Receipt ledger · rule ledger · memory · commitment/artifact store |
| Genuinely out-of-process | Only the Override, and only if it can be reached when the main process is degraded |

Rationale, stated once so it is not relitigated: VEDA 04 §7's latency budgets are 150ms for voice/text synchronisation and sub-second for override. A network hop per judgment request does not fit. **A module boundary enforced by an architecture test is worth as much as a process boundary and costs nothing at runtime** — and the codebase already demonstrates this pattern works.

---

## 4 · Capability Ownership Matrix

Every capability, exactly one owner. **Owner means architectural home per Constitution §16**, not a person. A capability appearing twice is flagged and resolved below the table.

| Capability | Primary Owner | Supporting | Consumers |
|---|---|---|---|
| Record what was done | **A1 Receipt Ledger** | StateStore, Clock, Principal | Everything. C4, C5, C7, E3, D1, Assurance |
| Classify reversibility | **A2 Registry** | Capability contract | A1, B1, B3, C1, execution gate |
| Perform a compensating action | **A2 Registry** | Execution path | Undo windows, B1 |
| Suspend all deciding | **A3 Override** | — | Founder only |
| State current authority in one sentence | **A4 Scope Introspection** | C4 | D1, founder query |
| Compute the consequence quartet | **B1 Consequence Engine** | A2 (reversibility), broker/cost.py (cost) | B2, B3, D1 |
| Order the open set | **B2 Ranking** | B1 | D6, VEDA 03 Screen 01 + 04b |
| Classify a decision's tier and trigger | **B3 Escalation Router** | A2, C1 | B2, B4 |
| Schedule and fire silence defaults | **B4 Silence Defaults** | **Durable Timer Service** | Every open request |
| Bind a claim to its sources | **B5 Evidence Graph** | Memory | D1, D6. **Name collision — §9.1** |
| Express confidence | **B6 Confidence Model** | — | D1 only. No number ever crosses to the founder. |
| Hold granted authority | **C1 Standing Rule Engine** | A1, Timer, Principal | Execution gate, C2, C4, C5 |
| Expire and renew authority | **C2 Expiry Daemon** | C1, Timer | C1 |
| Propose new rules from evidence | **C3 Proposal Miner** | E1 provenance, A1 | Founder, via B2 |
| Answer "where is the line" | **C4 Boundary Service** | A1, C1 | Dashboard, D5, A4, C7. **Sole source.** |
| Confess borderline firings | **C5 Self-Audit** | A1, C1 | D6 receipt. Cannot be disabled. |
| Route decisions to other humans | **C6 Delegation Router** | Principal | B3 |
| Produce the annual audit | **C7 Dependency Audit** | C1 history, Timer | Founder. No suppression parameter exists. |
| Turn state into prose | **D1 Narration** | Everything readable | D6, voice, text |
| Validate every utterance | **D2 Voice Charter** | — (zero deps) | **Every outbound utterance without exception** |
| Disclose the system's own errors | **D3 Mistake Protocol** | A1 | D1 **directly** — never via B2 |
| Broadcast presence | **D4 Presence** | Real work signals from the execution path | UI |
| Derive tree topology | **D5 Tree Topology** | C4 **only** | UI |
| Compose the brief | **D6 Brief Composer** | D1, D7, B2, C5 | Screen 01 |
| Attest vigilance coverage | **D7 Vigilance Attestation** | **Domain Registry** | The calm state. Hard gate. |
| Store decision provenance | **E1 Provenance** | Memory | C3, D1 at relevance |
| Export everything | **E3 Export** | A1, C1, E1, Memory | Founder |
| Deterministic demo | **E2 Demo Tenant** | — | Runtime mode, not fixtures |
| **Foundation** | | | |
| Canonical time | **Clock Service** | — | Every timer, deadline, expiry, greeting |
| Durable timers, seconds→years | **Durable Timer Service** | StateStore, Clock | B4, C2, C7, undo windows, freshness |
| Identity of a decider | **Principal Model** | — | C1, C6, A1, approvals |
| What is watched and how fresh | **Domain Registry** | Connectors | D7 |
| One execution gate | **Execution Path** (exists, needs unifying) | A1, A2, C1 | All capabilities |

### 4.1 Ownership conflicts found — all four flagged

| Capability | Claimed by | Resolution |
|---|---|---|
| **Granted authority** | `permissions/PermissionSystem` (exists) **and** C1 Standing Rule Engine | C1 subsumes. `PermissionSystem` becomes C1's evaluation core or is retired. **Two grant ledgers must never coexist**, even briefly. |
| **Execution history** | `verification/AuditLog`, `mission_control/AuditStream`, `executor/ExecutionLogEntry` (all exist) **and** A1 | A1 is the ledger. The three existing records are per-worker, per-event, and per-execution respectively, and are documented as deliberately distinct. **They must become feeders into or projections of A1, not a fourth store beside three.** §9.3. |
| **Unanswered human questions** | `mission_control/approvals.py`, `knowledge_queue.py`, `self_development.py` (all exist) **and** B2's open set | One ranked open set. The three queues become *sources* of requests, not independent inboxes. §9.2. |
| **The autonomy number** | C4, the dashboard, the tree | C4 only. Assert with an architecture test that no module outside C4 computes a ratio over rules. |

---

## 5 · Module Map

Traceability chain: **VEDA → Requirement → Module → Owner → Dependencies.** Nothing may exist without a row here. `Owner` is the architectural layer per Constitution §16.

### 5.1 Foundation (Phase −1) — assumed by VEDA 04, named by no VEDA

| VEDA | Requirement | Module | Owner | Depends on | State |
|---|---|---|---|---|---|
| 04 §7 Clock | One canonical timezone source; no ambient local time in the decision path | `foundation/clock` | Shared Infra | — | **Build** |
| 04 R10 | Model the principal as an entity now, while only one exists | `foundation/principal` | Shared Infra | — | **Build** |
| 04 §7 Long-horizon timers | Durable timers surviving deployments, migrations, outages | `foundation/timers` | Shared Infra | Clock, StateStore | **Build** |
| 04 D7, §2 connectors | Per-domain freshness and health | `foundation/domains` | Shared Infra | Clock | **Build** |
| 04 R1 | Single enforcement point on the tool path | *(existing)* `orchestrator` + `executor` | Operator | — | **Unify + assert** |
| 04 §5 | Durable storage | `persistence/store.py` | Shared Infra | — | ✓ Exists |

### 5.2 Layer A — Trust Spine (Phase 0)

| VEDA | Requirement | Module | Owner | Depends on | State |
|---|---|---|---|---|---|
| 04 A1 | Receipt before change, two-phase, append-only | `receipts/ledger` | Shared Infra | StateStore, Clock, Principal, A2 | **Build** |
| 04 A2 | Every action classified; fails closed | `reversibility/registry` | Shared Infra | Capability contract | **Extend** — risk tiers and `IRREVERSIBLE` exist; compensating actions and fail-closed do not |
| 04 A3 | One gesture suspends all deciding | `override/` | Outside main path | — | **Build** |
| 04 A4 | Say what it may not do, in one sentence | `boundary/introspection` | Shared Infra | C4 | **Build (Ph 4)** |
| 04 D2 | Lint every outbound utterance | `voice/charter` | Brain | — | **Build early — R-D** |

### 5.3 Layer B — Judgment (Phase 1)

| VEDA | Requirement | Module | Owner | Depends on | State |
|---|---|---|---|---|---|
| 04 B1 · 01 §5 | The four mandatory fields, or no request | `judgment/consequence` | Shared Infra | A2, broker/cost.py | **Build** |
| 04 B2 · **03 frozen fn** | `irreversibility × log(exposure) × deadline × novelty`, justified | `judgment/ranking` | Shared Infra | B1 | **Build** |
| 04 B3 · 03 three tiers | novel / irreversible / excluded → Needs-you / Sweep / Auto | `judgment/router` | Shared Infra | A2, C1 | **Build** — partial in `approvals.py` |
| 04 B4 | Every request has a declared default and firing time; re-verify before firing | `judgment/defaults` | Shared Infra | Timer, B1 | **Build** |
| 04 B5 | Claims bound to sources at generation | `evidence/graph` | Shared Infra | Memory | **Blocked on ADR — §9.1** |
| 04 B6 | Three coarse levels; never a percentage | `judgment/confidence` | Brain | — | **Build (Ph 4)** |

### 5.4 Layer C — Autonomy (Phase 3)

| VEDA | Requirement | Module | Owner | Depends on | State |
|---|---|---|---|---|---|
| 04 C1 · 01 §10 · **03 five parts** | trigger · cumulative cap · exclusions · expiry · receipt | `rules/engine` | Shared Infra | A1, Timer, Principal | **Build — subsumes `permissions/`** |
| 04 C2 | Rules die unless renewed | `rules/expiry` | Shared Infra | C1, Timer | **Build** |
| 04 C3 · **01 §4 30-day** | Proposals with evidence, including the counter-example | `rules/miner` | Brain | E1, A1 | **Build** |
| 04 C4 | Sole source of autonomy truth | `boundary/service` | Shared Infra | A1, C1 (as projection) | **Build** |
| 04 C5 · **03 trust moment** | Reports its own borderline calls, unprompted | `rules/self_audit` | Shared Infra | C1, A1 | **Build — with C3, never after** |
| 04 C6 | Delegation to a named human is first-class | `judgment/delegation` | Shared Infra | Principal | **Build (Ph 4)** |
| 04 C7 | Annual, unprompted, non-disableable | `governance/dependency_audit` | Shared Infra | C1 history, Timer | **Build (Ph 5)** |

### 5.5 Layer D — Expression (Phase 2)

| VEDA | Requirement | Module | Owner | Depends on | State |
|---|---|---|---|---|---|
| 04 D1 · **01 §8** | One generation, two renderings; figures bound to rendered values | `narration/service` | Brain | All readable state | **Build** — `brain/reporter.py` is a stand-in |
| 04 D3 | impact→cause→fix→prevention, before founder discovery, ungated | `narration/mistakes` | Brain | A1 | **Build — direct path to D1** |
| 04 D4 | Presence driven by real work signals, never a UI timer | `presence/` | Brain | Execution signals | **Build** |
| 04 D5 · **01 §9 fixed mapping** | Topology from C4 only; revoked rules thin, never delete | `tree/topology` | Brain | C4 | **Build (Ph 4)** |
| 04 D6 · **03 Screen 01** | Headline-first; quiet-day variant is a first-class path | `narration/brief` | Brain | D1, D7, B2, C5 | **Build** — panels exist |
| 04 D7 | Coverage proof; may not say "nothing needs you" while incomplete | `vigilance/attestation` | Shared Infra | Domain Registry | **Build — same phase as D6** |

### 5.6 Layer E — Governance (Phase 5)

| VEDA | Requirement | Module | Owner | Depends on | State |
|---|---|---|---|---|---|
| 04 E1 | Provenance surfaced at relevance, not on search | `provenance/store` | Shared Infra | Memory | **Build (Ph 4)** |
| 04 E2 | Deterministic demo as a runtime mode | `demo/tenant` | Runtime mode | — | **Build (Ph 5)** |
| 04 E3 | Complete founder-readable export | `governance/export` | Shared Infra | A1, C1, E1, Memory | **Build (Ph 5)** |

### 5.7 Existing modules with no VEDA 01–04 requirement

Traceability runs both ways. These exist and serve the Constitution rather than VEDA 01–04. **None is orphaned; all are named so nothing is unaccounted for.**

`plugins/` · `executor/` · `capabilities/` · `providers/` · `broker/` · `ai_infrastructure/` · `desktop/` · `environment/` · `verification/` · `planner/` · `mission_control/` · `runtime/` · `memory/` · `persistence/` · `launcher/` · `dashboard/`

Two require attention rather than acceptance:

- **`mission_manager/` (86 lines, not wired into the live path)** — duplicates `mission_control/Objective`. §9.4.
- **`orchestrator/execute_plan()`** — documented as a demo path, not the mission path. It is a second walk over work. **Delete it or move it into the demo entry point** before A1 is inserted, so it cannot become an unreceipted route.

---

## 6 · Integration Sequence

**VEDA 04 §9's phases and gates are preserved verbatim.** This section adds Phase −1, which VEDA 04 assumes, and states the earliest safe build point for three items. *Building something earlier than its listed phase never violates a gate — every VEDA 04 gate is of the form "cannot proceed until X exists."*

The two sequencing rules that override everything are inherited unchanged: **never ship autonomy before accountability**, and **never ship the reassurance before the proof.**

---

### Phase −1 · Foundation

**Build:** Clock · Principal · Durable Timer Service · Domain Registry · **execution path unification** · **reversibility classification audit at current scale**

**Why here.** Every one of these is a retrofit if built later, and each retrofit touches everything built in between. The timer alone has five consumers spanning seconds to a year; discovered late, it is built three times.

**Gate:** an architecture test fails the build if any code path reaches `plugin.invoke()` or `LocalExecutor.run()` other than through the single gate. Every registered capability carries a reversibility class and, where reversible, a named compensating action.

> **This phase is the entire zero-rework thesis of this document.** Everything after it is ordinary work.

---

### Phase 0 · The Spine — *VEDA 04 §9 Phase 0, unchanged*

**Build:** A1 Receipt Ledger · A2 completion (fail-closed) · A3 Override · **+ D2 Voice Charter Validator (moved earlier, R-D)**

**Gate (VEDA 04, verbatim):** no execution path can reach a tool without a receipt intent and a reversibility classification. *Verified by test, not by review.*

**Added gate for D2:** no outbound utterance exists that has not passed the validator. Start the personality regression suite now — VEDA 04 R4 says this cost is permanent and recurring; it is cheapest to establish at ten utterances.

---

### Phase 1 · Judgment — *unchanged*

**Build:** B1 · B3 · **B4** · B2 · B5 *(B5 blocked on the §9.1 ADR)*

**Sequencing note inherited from VEDA 04:** B4 belongs in this phase, not later. The moment the system can create an open request it must be able to resolve one by default.

**Added task:** collapse the three existing queues into the single ranked open set (§9.2). Doing this *while* building B2 is one piece of work; doing it afterwards is a migration with a founder-visible surface change.

**Gate:** no judgment request can be constructed without a complete quartet and a scheduled default. Exactly one open set exists, asserted by test.

---

### Phase 2 · Expression — *unchanged*

**Build:** D1 · D6 · D4 · **D7** · **D3**

**D7 ships with D6** — the calm state must never exist before the attestation that makes it honest. **D3 ships here too**, on a path to D1 that does not route through B2. Ranking is a quality-scoring mechanism, and VEDA 04 D3 forbids error disclosure being gated by one.

**Gate:** the entire system state renders as prose; every utterance passes validation; the calm state is unconstructable without complete coverage.

---

### Phase 3 · Autonomy — *unchanged*

**Build:** C1 (subsuming `PermissionSystem`) · C2 · C4 · C3 · **C5 with C3**

**Gate:** a rule cannot be defined without a cumulative cap, exclusions, and an expiry. A firing cannot occur without a receipt. The self-audit cannot be disabled. **Exactly one component computes an autonomy number.**

---

### Phase 4 · Maturity — *unchanged*
C6 · E1 · B6 · A4 · D5

### Phase 5 · Governance — *unchanged*
C7 · E3 · E2. C7 is a **dated commitment**, not a backlog item — it must not be deferred past the first anniversary of the first customer.

---

### 6.1 Where the Vertical Slice sits

**Not a phase. A gate applied at the end of Phase 0, 1, 2, and 3** — the same objective run four times, each run exercising more of the spine. §7.

---

## 7 · Vertical Slice Plan

### 7.1 Why not "Create Demo folder"

Two independent reasons.

**It is already built.** Miracle 001, shipped 2026-07-23: *"create a folder called Demo"* through the real Orchestrator, Permission System, and Mission state machine. Rebuilding it is the rework this document exists to prevent.

**It is the wrong shape.** It is reversible, non-recurring, has no cost, no deadline, no exposure, and no precedent. Therefore:

| It cannot exercise | Because |
|---|---|
| B1 Consequence Engine | The quartet is degenerate — nothing changes, nothing costs, doing nothing is fine, and it undoes trivially |
| B3 Escalation Router | It is never novel, never irreversible, never excluded — it cannot fire any of the three triggers |
| B4 Silence Defaults | There is no meaningful default and no reason to wait |
| C3 Proposal Miner | It never recurs, so no pattern can form |
| A2 compensating actions | Nothing needs compensating |
| D7 Vigilance | It watches no domain |

**A slice that cannot escalate cannot test the layer this whole programme is building.**

### 7.2 The slice: *"Archive exports older than 30 days."*

Stated by the founder monthly. Local, safe, real, and recurring.

**What makes it correct:**

| Property | Exercises |
|---|---|
| Deletes or moves real files | **A2** with a genuine compensating action and a window — the part every team skips |
| Requires approval the first time | **A1** intent→execute→outcome; **C1** on later runs |
| Has a real quartet | *changes:* 14 files, 2.1 GB · *costs:* nothing · *if nothing:* exports keeps growing · *undoable:* yes, 24h |
| Has a sensible silence default | **B4**, including the re-verification step — files may have changed between scheduling and firing |
| **Recurs monthly** | **C3** can form a pattern and propose a rule **inside 30 days** — VEDA 04 R8's product-survival metric, testable rather than hoped for |
| Watches one folder | **D7** with exactly one monitored domain and one freshness window |
| Produces a sentence | **D1 + D2**, with a figure bound to a rendered value |
| Reversible action, irreversible if wrong | **A2 pessimistic classification** — is a move reversible, or reversible-until-T? |
| Touches no money, no third party, no network | Safe as a first exercise of a brand-new Trust Spine |

**What it deliberately does not exercise:** money (C1 cumulative caps over currency, VEDA 04 R3), outbound contact, and multi-step dependency. Those need a second slice at Phase 3; naming that here prevents the first slice from being over-scoped.

### 7.3 The four runs

The same objective, run at the end of each phase. Each run is a **gate**, and each adds exactly one layer.

| Run | After | Must demonstrate | Fails if |
|---|---|---|---|
| **1** | Phase 0 | Intent receipt written before any file moves; reversibility class resolved; killing the process mid-run leaves the ledger honest; Override suspends deciding while queueing continues | Any file moves without a preceding intent record |
| **2** | Phase 1 | A complete quartet; a scheduled default that fires after re-verification; ranked among other open items with a stated justification | A request is constructible without a quartet or a default |
| **3** | Phase 2 | One sentence, passing the Voice Charter, with the figure bound to the rendered value; the calm state refused when the folder's freshness is stale | The system says "nothing needs you" while a domain is unchecked |
| **4** | Phase 3 | Third consecutive month: a rule proposed with evidence *and the counter-example that bounds it*; not enacted; a firing receipted; a borderline firing confessed unprompted | The proposal self-enacts, or the self-audit can be disabled |

**Run 4 is the product.** It is the only run that demonstrates the line moving, and it is testable on a 90-day clock rather than an opinion.

---

## 8 · Zero-Rework Audit

For each phase: *will something built here be rewritten later?* Where yes, **the sequence changes, never the architecture.**

| # | What would be rewritten | Trigger | Sequence change |
|---|---|---|---|
| **1** | Every capability written before A1/A2 needs a receipt-and-classification retro-audit | A1 built after capability growth | **A2 audit in Phase −1, A1 in Phase 0, both before the next capability.** Cost is linear in capability count and the count only grows. |
| **2** | Every utterance written before D2 needs retro-validation, plus a personality regression suite built against an existing corpus | D2 in Phase 2 as listed | **D2 in Phase 0.** Zero dependencies; nothing is lost by building it first. |
| **3** | Live founder grants migrated into C1's five-part shape | Persisting `PermissionSystem` before C1 | **Do not persist grants until Phase 3.** Session-scoped grants remain in memory. This is a deliberate, temporary limitation and should be stated as one. |
| **4** | Timer semantics unified across B4, C2, C7, undo, freshness | Timer discovered per consumer | **One Durable Timer Service in Phase −1.** |
| **5** | Dashboard panels re-pointed at C4 | Panels built against ad-hoc sources before C4 | **Freeze dashboard panel growth until C4 exists.** Existing panels are fine; new ones are rework. |
| **6** | Every consumer of `Objective` or `Mission` migrated | The ADR deferred while consumers accumulate | **Settle the ADR in Phase −1.** Cost grows with each new consumer and with nothing else. |
| **7** | The founder-visible queue surface changes shape | Three queues collapsed after the founder has used them | **Collapse during Phase 1, alongside B2.** One piece of work now, a migration with a visible surface change later. |
| **8** | Receipt writes retrofitted into a fourth audit store | A1 built beside three existing record types | **Decide the projection strategy before A1 is written** (§9.3). |
| **9** | The narration layer rebuilt for voice | Text and speech generated independently | **D1 built as one generation with two renderings from day one.** VEDA 04 §6 makes divergence a severity-one defect; retrofitting a single generation path is a rewrite of D1. |
| **10** | Every autonomy surface re-pointed | A second autonomy number ships | **C4 as a projection of A1+C1, asserted by test, before any surface renders a ratio.** |

### 8.1 Two things that will *not* need rewriting, and should be left alone

**The Action Contract and `LocalExecutor`.** They are exactly the shape VEDA 04 R1's mitigation requires. Inserting A1 into this path is an addition, not a redesign. **Do not refactor them to accommodate the Trust Spine — insert the Trust Spine into them.**

**The architecture-boundary test pattern.** Every invariant in this document is enforceable by the mechanism the codebase already uses and trusts. No new tooling is required, and none should be introduced.

---

## 9 · Duplicate Detection

Separated into three honest categories. **The codebase already documents why several apparent duplicates are not duplicates, and those arguments are correct.** Collapsing them would be its own form of rework.

### 9.1 Terminology collision — blocks work until resolved

**`Evidence` has two meanings.**

| Source | Meaning |
|---|---|
| Constitution §17 (frozen) + `verification/evidence.py` (shipped) | Observation + Expected Outcome + Verdict — *did the world match the plan* |
| VEDA 04 B5 "Evidence Graph" | Claim → sources — *what is this assertion based on* |

These are unrelated concepts sharing a frozen name. **If B5 is built without resolving this, it will be built inside `verification/`, where it does not belong** — B5 serves narration and claim provenance, not mission verification.

**Blocks:** B5, and therefore any narration that makes a sourced claim.
**Requires:** an ADR. §17 is frozen; the precedent for adding a distinguishing term is Amendment 1 (Executive/Worker).
**Recommendation:** rename VEDA 04's concept to **Provenance Graph** in implementation, reserving `Evidence` for its frozen meaning. This changes no VEDA text — VEDA 04 §1 B5's requirement is unchanged; only the module name differs.

Two further collisions were identified in the VEDA 05 review and are already on the amendment path: `Objective`/`Mission`, and `Mission Manager`. **The `Objective`/`Mission` ADR blocks nothing technically but grows more expensive with every new consumer (§8, item 6).**

### 9.2 Real duplication — resolve during the named phase

| Duplication | Instances | Resolution | Phase |
|---|---|---|---|
| **Grant ledger** | `permissions/PermissionSystem` + C1 | C1 subsumes. Never coexist. | 3 |
| **Human-gated queues** | `mission_control/approvals.py` · `knowledge_queue.py` · `self_development.py` + B2's open set | Three become *sources* of requests into one ranked set. The queues keep their domain logic; they stop being inboxes. | 1 |
| **Intent-to-outcome unit** | `mission_manager/Mission` (not wired) + `mission_control/Objective` (live) | Per the pending ADR. Until settled, **write no new consumer of `mission_manager/`**. | −1 |
| **Walk over work** | `Orchestrator.execute_plan()` (demo path, documented as such) + `TaskDispatcher` | Delete `execute_plan()` or relocate it into the demo entry point. It must not survive as an unreceipted route past Phase 0. | −1 |

### 9.3 Documented separations — do **not** collapse, but do not add a fourth

Three execution-record types exist, and the code explains why each is distinct:

- `executor/ExecutionLogEntry` — per-Action, shared by every capability
- `verification/AuditRecord` + `AuditLog` — per-Worker, per-step, carries verdict and evidence id
- `mission_control/AuditStream` — system-wide, event-level, append-only

**These arguments are sound and the separations should stand.** The risk is A1 arriving as a fourth store beside three.

**Decision required before A1 is written:** A1 is the receipt ledger — the only store with the intent-before-execute two-phase property and the only one that is append-only at every privilege level. The other three must become **feeders into it or projections of it**, not peers. Whichever is chosen, **it must be chosen before the first receipt is written**, because the direction of the dependency is not changeable afterwards without rewriting all four.

Similarly documented and correct: **two Capability Registries** (`plugins/registry.py` holds live objects for execution; `mission_control/capabilities.py` holds descriptors for coordination, and deliberately cannot invoke). Keep both. **Add no third** — VEDA 05's skill-ownership index, if it ever ships, is a third *index* on an existing registry, never a new registry.

### 9.4 Impending duplication — prevented only by naming it now

| Would be duplicated | Consumers that would each build one | Prevention |
|---|---|---|
| **Durable timers** | B4 (days), C2 (months), C7 (a year), undo (seconds), freshness (minutes) | One service, Phase −1 |
| **The autonomy number** | C4, dashboard, tree | C4 only, asserted by test |
| **Time** | Every deadline, expiry, greeting, and renewal date | One Clock, Phase −1 |
| **Learning** | broker `learning.py` (provider performance, ratified ADR-0018) · C3 (rule proposals) · any future skill-level loop | **Genuinely three different loops with three different subjects.** Keep separate. The invariant that keeps them from converging: **only C3 touches authority, and C3 cannot enact.** |

---

## 10 · Risks

Ten, ordered by severity. Each names its trigger, its cost if unmitigated, and its mitigation.

**1 · Unreceipted execution paths survive A1.** *Hidden coupling.*
Multiple invocation surfaces exist today. A1 inserted at one of them leaves the others silent, producing an audit spine with holes — which VEDA 04 R1 rates worse than no spine, because it manufactures false confidence.
*Mitigation:* Phase −1 path unification, enforced by a build-breaking architecture test. **Not a lint warning.**

**2 · The reversibility audit is deferred past capability growth.** *Compounding cost.*
Cost is linear in capability count; every misclassification is a potential irreversible action taken automatically.
*Mitigation:* audit at ~30 capabilities. Fail closed from day one. Classify pessimistically; upgrade only on evidence of a working compensating action.

**3 · Persisted grants without expiry.** *Constitutional violation by increment.*
`ALWAYS_FOR_CAPABILITY` has no end date. It is compliant today only because it is in-memory. The natural next feature — "remember my approvals across restarts" — converts an accident into a violation of VEDA 04 C2 and creates a migration of live founder grants.
*Mitigation:* R-C. No grant persistence before C1. State the limitation to the founder rather than quietly fixing it.

**4 · Four autonomy numbers.** *Guaranteed inconsistency.*
VEDA 04 C4 names this failure explicitly, and it is the most-repeated warning across VEDA 03 and 04.
*Mitigation:* C4 as a projection of A1+C1. A derived value cannot disagree with its source. One architecture test.

**5 · The Voice Charter arrives after the utterances.** *Recurring forever.*
VEDA 04 R4 is the only risk in that document marked as returning with every model change. The validator is the sole defence, and it needs a regression corpus that is cheapest to build early.
*Mitigation:* R-D. D2 in Phase 0, regression suite from the first utterance.

**6 · Service explosion.** *Unnecessary abstraction.*
22 VEDA 04 modules + foundation + whatever VEDA 05 eventually adds. A 1:1 module-to-service mapping produces roughly 30 deployment units for a single-founder, local-first product, and blows every latency budget in VEDA 04 §7.
*Mitigation:* §3.4's packaging rule, stated once. Module boundaries enforced by test; one process.

**7 · The Broker becomes the hot path.** *Future bottleneck.*
Every component needing intelligence must ask the Broker, which is singular by constitutional requirement and must be atomic on cumulative spend (VEDA 04 R3, rated high). As capability count and concurrency grow, it is consulted more than anything else in the system and cannot be sharded without fragmenting the ledger.
*Mitigation:* measure Broker call latency from the first vertical-slice run; treat it as a named budget rather than discovering it. **Do not shard the ledger.** If contention appears, cache *decisions* (which are deterministic given inputs), never the *accounting*.

**8 · Annual timers do not survive a year of deployments.** *Silent governance failure.*
C7 is non-disableable and dated. A timer lost to a deployment is a governance failure that surfaces twelve months late, and by then the evidence of when it was lost is gone.
*Mitigation:* persisted schedule with reconciliation on boot, built in Phase −1 and tested by simulated year-crossing rather than by waiting.

**9 · The silence-default re-verification step is omitted.** *Trust-ending, and easy to miss.*
VEDA 04 F5 is explicit: facts move between scheduling and firing. Firing a stale default is a trust-ending event, and the omission is invisible until it happens.
*Mitigation:* re-verification is part of B4's definition of done, exercised by vertical-slice Run 2 with a deliberately mutated fact.

**10 · The calm state ships before the proof.** *The most tempting sequencing error available.*
Building "Nothing needs you" first and D7 later puts a lie into production. VEDA 04 names this as the single failure most likely to end a customer relationship permanently.
*Mitigation:* D7 ships in the same phase as D6, and the gate is structural — **the calm-state message should be unconstructable without a complete attestation**, ideally at the type level, not by a runtime check someone can forget.

---

## 11 · Final Recommendation

### 11.1 Approve and start with Phase −1

Six items, none of which appear in any VEDA, all of which every VEDA assumes: **Clock · Principal · Durable Timers · Domain Registry · execution path unification · reversibility classification audit.**

They share one property: each is nearly free now and a cross-cutting retrofit later. **The single strongest argument in this document is that the codebase is currently at the cheapest moment it will ever be at for all six.** 26 miracles is small. 60 will not be.

### 11.2 Three sequence changes, no architecture changes

| Change | From | To | Reduces |
|---|---|---|---|
| D2 Voice Charter | Phase 2 | **Phase 0** | Retro-validating every utterance; a regression corpus built late |
| Grant persistence | whenever convenient | **Phase 3, with C1** | Migrating live founder grants out of a non-compliant shape |
| Queue collapse | after B2 | **during Phase 1** | A founder-visible surface migration |

Every VEDA 04 §9 gate is preserved. No phase content is removed. No requirement is reinterpreted.

### 11.3 Four items blocked until an ADR is ratified

| Blocked | Blocked by | Cost of delay |
|---|---|---|
| B5 Evidence Graph, and any sourced claim in narration | `Evidence` collision (§9.1) | Grows with every narration surface built |
| New consumers of `mission_manager/` | `Objective`/`Mission` collision | Grows with every consumer |
| A1's relationship to the three existing audit stores | Projection-vs-peer decision (§9.3) | **Unchangeable after the first receipt is written** |
| Grant persistence | C1 not built | None today; violation the moment it ships |

The third is the urgent one. It costs nothing to decide now and cannot be revisited later without rewriting four stores.

### 11.4 The definition of done for this blueprint

Implementation is on track if, at every phase gate, all four hold:

1. **Every capability has a reversibility class and, where reversible, a working compensating action.** Verified by test.
2. **No code path reaches a tool except through the single gate, and that gate writes a receipt intent first.** Verified by test.
3. **Exactly one component computes an autonomy number, one holds granted authority, one holds the open request set, and one records what happened.** Verified by test.
4. **The vertical slice runs, at the depth that phase permits, without a single hand-written fixture.**

### 11.5 The one-sentence justification for every recommendation above

> **Everything scheduled here early is something that becomes a cross-cutting retrofit if scheduled late, and nothing scheduled here early is something the architecture would have to change to accommodate.**

That is the whole thesis. The VEDAs already decided what to build; this document only decides what order makes each thing get built exactly once.

---

*Engineering blueprint. No VEDA created, modified, or reinterpreted. All claims about current system state verified directly against `src/master_agent/`, `MIRACLE_LEDGER.md`, and the shipped test suite as of 2026-08-05. Where a decision requires founder ratification, it is named as blocked rather than assumed.*
