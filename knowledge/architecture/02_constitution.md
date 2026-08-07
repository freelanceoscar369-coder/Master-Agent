# Constitution Summary

**Document:** `docs/architecture/KALPAVRIKSHA_VISION_V2.md`  
**Version:** v2, Revision 3 (Founder Constitution Freeze)  
**Status:** Canonical Architecture Reference — **FROZEN**  
**Effective Date:** 2026-07-26  
**Scope:** All Mission Briefs from MB021 forward  
**Authority:** This document supersedes all prior Mission Briefs, ADRs, and design notes for architectural *decisions*. `ARCHITECTURE.md` remains authoritative for current *implementation* detail (module file layout, present-day data flow) and is read through this Constitution's terminology, not instead of it.

---

## Frozen Principles (Status: FROZEN)

### 1. Project Vision (§1)
**Kalpavriksha** (the wish-fulfilling tree) is an AI orchestration platform that turns a stated human intention into a completed, verified outcome — not a chat response, not a suggestion, but a real-world result the human can see, touch, and trust.

**The Kalpavriksha Loop** (no step optional, no step bypassed):
```
Intent → Plan → Delegate → Execute → Verify → Learn → Report
```

**What Kalpavriksha Is:**
- An orchestration layer between human intent and software execution
- A plugin architecture where every capability is a Worker behind a single contract
- A local-first, cloud-enhanced system: fully functional with purely local Reasoning Provider and local Memory; cloud Reasoning Providers are opt-in enhancements
- A permission-gated execution engine: nothing above read-only risk executes without explicit human approval
- A memory system that survives process restarts and feeds future planning

**What Kalpavriksha Is Not:**
- A chatbot or LLM wrapper
- A replacement for the human's judgment
- A cloud-dependent service
- A monolith that must be rewritten to add capabilities
- A single, unscalable Operator (§8)

### 2. Core Principles (§2)

| Principle | Definition |
|-----------|------------|
| **2.1 Intent Over Prompts** | System captures structured `Intent` (goal, constraints, context, success criteria), never a raw string handed straight to a model |
| **2.2 Outcome Over Output** | Mission "done" only when Verification (§10) confirms real-world state matches Intent's success criteria — never when a model produces text |
| **2.3 Everything Is a Worker Behind a Capability** | Reasoning Providers, capabilities, transport adapters — all are Workers behind the same Capability Registry and contract (§5, §12). Core engine small; almost all capability lives in Workers |
| **2.4 Human Approval Before Important Actions** | No Worker executes a step classified above `READ_ONLY` risk without a grant from Permission System (§5). Permission System has veto power over Operator — not optional middleware, a gate |
| **2.5 Local-First, Cloud-Enhanced** | System fully functional offline against Local Reasoning Provider and local Memory. Cloud Reasoning Providers are enhancement the Model Router opts into, never a hard dependency. Defined architecturally, not by naming specific models (§14) |
| **2.6 Replaceable Modules** | Every module swappable behind its interface without touching others. Enables "build for one founder first, scale for millions later" |
| **2.7 Minimum Manual Work, Maximum Agent Work** | Agent does execution, human approves and directs. Single canonical statement — see §15.3 for mechanism; do not restate elsewhere, cross-reference it |

---

## Layer Separation Rules (Status: FROZEN)

### Three-Layer Architecture (§6)
```
Executive Brain (decides what, how to structure, how to explain)
        │
Shared Infrastructure (one consistent source of truth both sides depend on)
        │
Universal Executive Operator (carries out what was decided, with accountability)
```

**Dependency direction only** — not sequential data flow. Brain and Operator never depend on each other's internals; both depend downward on Shared Infrastructure.

### Separation Matrix (§6)

| Aspect | Executive Brain | Shared Infrastructure | Universal Executive Operator |
|--------|-----------------|----------------------|------------------------------|
| **Role** | Decides what and how to structure it, and how to explain it | Provides the one consistent source of truth both sides depend on | Carries out what was decided, with accountability |
| **Modules** | Intent Layer, Planner, Model Router, Reporter | Capability Registry, Permission System, Mission State, Memory, Configuration, Telemetry/Evidence aggregation, AI Capability Broker | Orchestrator, Verification Subsystem, Worker/Plugin Runtime, Environment Session Management |
| **Reasoning-Provider calls** | Yes | No | No |
| **Which Provider serves a request** | Asks; never decides | **Decides — AI Capability Broker (§5.7)** | Asks; never decides |
| **Environment access** | Never | Never | Only through a Worker, via an Environment Session it owns |
| **Permission checks** | Never issues, never checks | Holds and adjudicates every grant | Every step above READ_ONLY checked here, against Shared Infrastructure |
| **Mission State** | Reads (context) | Owns | Transitions it, through Shared Infrastructure's contract, never a private copy |
| **Memory** | Reads; nominates Knowledge Candidates | Owns; stores and serves | Writes Evidence into it, through Shared Infrastructure's contract |
| **Replaceability** | Swap Planner, swap Reasoning Providers | Swap storage/backing behind any §5 component | Swap Orchestrator policy, swap Worker Runtime, add Operator Instances |

**Boundary precision:** Brain and Operator never depend on each other's internals — that boundary is real. What was inaccurate was implying there is *nothing* both sides legitimately share; there is, and §5 names it, gives it a contract, and explains why each piece lives there.

---

## Shared Infrastructure Layer (§5, Status: FROZEN)

### 5.1 Capability Registry
**Belongs here because:** queried by Brain's Model Router (Reasoning Provider resolution) and Operator's Orchestrator (execution capability resolution) — same lookup mechanism, two different callers. One registry, one answer, regardless of who asks. Today: one component with two indices (plugin identity, capability → plugin). Future capability-resolution policy is EVOLVABLE.

### 5.2 Permission System
**Belongs here because:** single, consistent grant ledger across every Operator Instance a Mission might touch. If each Operator Instance held its own grant table, human approving once for one Operator could be silently re-satisfied or re-asked by different Operator executing different Step of same Mission. Elevated to Shared Infrastructure makes "one approval per mission" (§15.3) a Mission-wide guarantee.

**Relay pattern** (ADR-0005/0006): outer approval explicitly carried down to inner grant key — unchanged by this move.

### 5.3 Mission State
**Belongs here because:** single Mission's Steps may be serviced by different Operator Instances (§8). If owned by "the Operator" as single entity, unclear *which* Operator Instance owns it. Correct permanent home for `MissionManager` and `Mission` state machine: `draft → planned → awaiting_approval → executing → verifying → completed | failed | cancelled`.

### 5.4 Memory
**Belongs here because:** every Operator Instance's Evidence must aggregate into one durable history, not fragment into per-Operator silos. All six Memory layers live here (`MEMORY_ARCHITECTURE.md`), including durable, queryable execution history (see 5.6).

### 5.5 Configuration
**Belongs here because:** Environment roots, Reasoning Provider defaults, policy configuration must be identical regardless of which Brain-side or Operator-side component reads them. Configuration drift = safety bug.

### 5.6 Telemetry and Audit (aggregated form)
**Split responsibility, on purpose:** raw log emission happens locally at Operator Instance/Worker Instance. Shared Infrastructure owns durable, queryable, cross-Operator-Instance aggregation — same mechanism Memory provides (Executor-style log folding into Mission Record). "Audit" and "Evidence" (§10) are not separate components — Evidence *is* the audited, verified subset of telemetry that made it into Memory.

### 5.7 AI Capability Broker (Amendment 2, MB027, Status: RESEARCH-BACKED)
**The single intelligence-selection service.** Every component needing AI (Brain's Model Router/Planner, Workers needing reasoning/vision/OCR/speech/embeddings mid-task) asks the Broker *which* Provider. **No other component may decide.**

Owns: Provider Registry, Capability Matrix, Decision Engine, Cost Model, Benchmark Store, Approval Policy, AI Asset Inventory, Recommendation Engine.

**Belongs here because:** both Brain and Operator need same answer to same question (ADR-0010). Its state (spend, approvals, benchmarks) must be singular across Operator Instances (same reason as Permission System §5.2). Must be consulted *before* dispatch, so cannot be a thing that is dispatched.

**Boundary that keeps it here:** Broker **decides and never touches the machine**. Executes nothing, opens no connection, imports no provider SDK, spends nothing, retries nothing, grants no permission — it *requires* permission through §5.2. Output names already-registered Capability + parameters, which caller runs through Operator like any other Capability. **Broker creates no new execution path.**

Machine-touching counterpart: **AI Infrastructure Executive** (ordinary Worker, §12, §16) — discovers, probes, benchmarks, inventories, installs (with Founder approval).

### 5.8 What Is Deliberately NOT Shared Infrastructure
- **Environment Session Management** — live handle to one Environment Instance belongs to Operator Instance that opened it. Sharing centrally = one Operator reaching into another's live connection (safety/isolation violation)
- **Mission Session** (`MasterAgentSession`) — Brain-adjacent glue, transitional, not infrastructure multiple Operator Instances depend on
- **Machine scanning, provider probing, benchmarking, inventory, installation** — Environment access, Rule 4 gives exactly one door. Belong to AI Infrastructure Executive, not Broker they feed

---

## Executive Brain Responsibilities (§3, Status: FROZEN)

The **Executive Brain** is the cognitive layer. Decides *what* to do, *how* to structure it, *how to explain it back*. Owns Intent, Planning, Reasoning-Provider selection, Reporting. **Never executes, never touches Environment, never holds Permission grant.**

### 3.1 Intent Layer
Turns raw input into structured `Intent` (goal, constraints, context, success criteria). Owns follow-up clarification when ambiguous. **Deliberately not** "send raw string to a model" — real parsing/clarification step so Planner never guesses.

**Current stand-in:** `cli.py`'s regex `parse_intent()` (MB001, 003.1, 005). Real Intent Layer stub pending real Planner (`ROADMAP.md` item 1).

### 3.2 Planner
Takes `Intent`, produces `MissionPlan`: DAG of `Step` objects, each naming a required **Capability** (never specific Worker — Shared Infrastructure resolves at execution time, so plans stay portable). Every `Step` also names an **Expected Outcome** — machine-checkable description of "done" for that Step — so Verification (§10) has concrete target.

Calls Reasoning Provider through Model Router. Reads recent Mission history and Permanent Knowledge (§9) as context.

### 3.3 Model Router
Single Reasoning Provider interface: `generate(prompt, context, **opts) -> ModelResponse`. Picks provider per call based on:
1. **Connectivity** — offline ⇒ Local Reasoning Provider only
2. **Privacy sensitivity** — sensitive tags stay local unless human explicitly overrides
3. **Task profile** — routine → local; strong reasoning needed → cloud
4. **Explicit user preference** — always wins

**Amendment 2 (MB027):** Model Router **consults AI Capability Broker (§5.7) to resolve *which* Reasoning Provider**, rather than implementing own ranking. Interface, role, and four criteria unchanged — each maps onto a phase of Broker's decision engine. Criterion 4's "always wins" honoured among candidates surviving Broker's hard-constraint filter.

Resolves *which registered Reasoning Provider* by querying Shared Infrastructure's Capability Registry (§5.1) — same registry Operator's Orchestrator queries. Not a boundary violation: both Brain and Operator depend downward on Shared Infrastructure; neither depends on the other (§6).

### 3.4 Reporter
Takes Mission outcome + Evidence once Verification produces Verdict, composes human-facing report (text today; voice later). Decides *how to explain* — Brain-shaped judgment (what to say, detail, tone), not execution fact. Never touches Environment; only reads Evidence and Mission state through Shared Infrastructure.

**Current status:** not yet built as distinct module — `cli.py`'s completion messages play this role.

### 3.5 What the Brain Does NOT Do
- Does not execute capabilities
- Does not hold or check Permission grants
- Does not own Mission State (Shared Infrastructure §5.3 does)
- Does not persist Memory itself (Shared Infrastructure does; Brain reads it and nominates Knowledge Candidates §9)
- Does not verify outcomes (consumes Evidence; does not produce it §10)
- Does not know what an Environment Instance is — only that a Step requires a Capability

---

## Universal Executive Operator Responsibilities (§4, Status: FROZEN)

The **Universal Executive Operator** is the execution layer. Carries out what Brain decided, with full accountability. **Never decides, never plans, never holds opinion about *why* a Step exists — only *how* to run it safely and *whether it actually worked*.**

### 4.1 Orchestrator
Walks `MissionPlan`, for each `Step`:
1. Resolves Capability → Worker via Shared Infrastructure's Capability Registry (§5.1)
2. Checks Permission System (§5.2) via Shared Infrastructure
3. Invokes Worker, captures result
4. Triggers Verification (§10) against Step's Expected Outcome
5. Applies retry/failure-branching policy (§11.1) — bounded, deterministic, scoped to this Operator Instance; never re-plans

### 4.2 Worker Runtime
See §12 — Worker Runtime (formerly "Worker Architecture") is Operator-owned implementation detail, not distinct architectural layer.

### 4.3 Verification Subsystem
See §10. Runs alongside Operator (needs Environment access, which only Operator has) but through its own contract, never through Worker's `invoke()`.

### 4.4 What the Operator Does NOT Do
- Does not decide what a Mission should accomplish
- Does not maintain private copy of Permission grants, Mission state, or Memory — all three are Shared Infrastructure (§5), specifically so multiple Operator Instances (§8) never disagree about approvals, Mission state, or history
- Does not nominate or promote Knowledge (§9) — produces Evidence; Brain and Promotion Review decide what becomes durable

---

## Evolvable Areas

| Section | Status | Reason |
|---------|--------|--------|
| §7 Universal Environment Philosophy | EVOLVABLE | Philosophy stable; roster of supported Environments expected to grow without changing section |
| §8 Multi-Operator Architecture | RESEARCH-BACKED | Defines shape architecture must not block; does not design distributed system per explicit constraint |
| §9.3–9.5 Knowledge Lifecycle | RESEARCH-BACKED | Newly designed; sound in principle, not yet implemented/battle-tested |
| §10 Verification Philosophy | RESEARCH-BACKED | Redesigned this revision to be structurally independent from Execution |
| §11 Recovery Philosophy | EVOLVABLE | Connects Recovery to Verification's new design; does not close every gap from prior audit |
| §19 Long-term Founder Edition Vision | EVOLVABLE | Expected to evolve as product matures |

### Key Named Gaps (Not Blockers)
1. **In-mission recovery decision procedure** (§11.4): Exact rule for when Orchestrator's retry absorbs failure vs escalates to re-plan vs surfaces to human. Not a blocker — nothing on `ROADMAP.md` depends on it.
2. **Stateful Environment Sessions inside Worker/Action contract** (§8.3, §12): Today's Action contract is one-shot; Browser/Terminal/Robotics need live handle across multiple Steps. Not a blocker — no current Worker needs this.
3. **Concurrent dispatch across Operator Instances** (§8.5): Deliberately left EVOLVABLE per instruction not to design distributed system.
4. **MB006–MB020 absent** from repository and all known backups. Constitution does not depend on their content.

---

## Ownership Boundaries (§16, Status: FROZEN)

Every component named across MB001–005, `ARCHITECTURE.md`, and prior audit appears here **exactly once**.

| Component | Home | Rationale |
|-----------|------|-----------|
| `MasterAgentSession` | **Brain-adjacent, transitional** ("Mission Session" role) | Today's stand-in for Intent Layer + Planner + Mission-initiation + manual Memory call. Dissolves into Brain (§3) and Shared Infrastructure (§5) as real components emerge |
| `MissionManager` / `Mission` state machine | **Shared Infrastructure** (§5.3) | Mission may span multiple Operator Instances (§8); state cannot belong to any one |
| `Reporter` | **Brain** (§3.4) | Deciding how to explain outcome is reasoning/communication judgment, not execution fact. Not yet built |
| `Orchestrator` | **Operator** (§4.1) | Unchanged — carries out what was decided |
| `ModelRouter` | **Brain** (§3.3) | Decides which Reasoning Provider handles a call. Depends on Shared Infrastructure's Capability Registry — legitimate downward dependency, not boundary breach (§6) |
| `CapabilityIndex` / Plugin Registry | **Shared Infrastructure** (§5.1) | One shared answer to "what can be done and by what," queried by both sides |
| `Memory` | **Shared Infrastructure** (§5.4) | Must aggregate across every Operator Instance, not fragment |
| Worker Runtime | **Operator** (§12) | Implementation detail of how Operator invokes Workers; not a distinct layer |
| Plugin Runtime | **Operator** (§12) | Same as Worker Runtime — two names refer to same mechanism |
| Verification Subsystem | **Operator-adjacent, own contract** (§10) | Needs Environment access (Operator-side) but structurally distinct from Execution |
| Permission System | **Shared Infrastructure** (§5.2) | Elevated this revision — see §5.2 for why |
| Operator Registry | **Shared Infrastructure** (§8.2, part of §5.1) | Tracks live Operator Instances same way Capability Registry tracks Workers |
| Environment Session Manager | **Operator (per-instance)** (§8.3) | Deliberately *not* shared — see §5.8 |
| AI Capability Broker | **Shared Infrastructure** (§5.7) | Added by Amendment 2 (MB027). Both Brain's Model Router and Workers needing intelligence consult it; ledgers must be singular across Operator Instances. Decides; never executes, never touches Environment |
| AI Infrastructure Executive | **Operator** (Worker, §12) | Added by Amendment 2 (MB027). Machine-touching counterpart to Broker: discovers, probes, benchmarks, inventories, installs (with Founder approval). Produces inputs Broker decides on; never decides itself |

---

## Human Oversight Requirements (§15, Status: FROZEN)

### 15.1 Approval Is Not Optional
Every capability above `READ_ONLY` requires Permission System grant (Shared Infrastructure, §5.2). Declining → `Mission.CANCELLED`, nothing executed, nothing persisted as side effect.

### 15.2 Approval UX Must Stay Simple
One clear decision point, regardless of how many Operator Instances (§8) or sub-steps a Mission touches.

### 15.3 One Approval Per Mission (Canonical Statement)
A human is never asked twice for the same thing they already approved, no matter how many primitive Steps, Workers, or Operator Instances that thing decomposes into underneath. Achieved by relaying already-obtained grant down through Shared Infrastructure's Permission System (§5.2, Rule 6) — **never by weakening what gets checked**.

### 15.4 Transparency Over Trust
Every execution is logged. Every Mission is recorded. Evidence (§10) is available, not hidden. No Reasoning Provider call happens without a named Capability behind it.

### 15.5 Promotion Review Is Human Oversight Applied to Knowledge
See §9.4. Promoting Knowledge treated as important action under same principle, not separate mechanism.

---

## Verification Requirements (§10, Status: RESEARCH-BACKED)

### 10.1 Problem Resolved
Prior revision claimed Verification was "distinct step" but only mechanism was Verifier invoked as "final Step in every plan" — through same `Plugin.invoke()` path as execution capability. Made *state* distinct (`verifying` Mission status) but not *mechanism*. This revision fixes the mechanism.

### 10.2 Three-Part Boundary
1. **Execution produces effects** — Worker's Action runs, does work, returns Execution Result (did it run without error, what it output). Says nothing about real-world outcome.
2. **Verification produces Evidence** — After (or during) execution, Verification Subsystem (distinct component, own contract, not Worker invoked through Capability path) re-observes Environment Instance, compares Observation against Expected Outcome (Planner attached to Step §3.2). Output: Verdict (matched / did not match / partially matched) + Observation + Expected Outcome = **Evidence** (§9.2).
3. **Evidence flows back to Brain** — Evidence routed to Brain (via Shared Infrastructure) as input to "is Mission actually complete, or does it need another Step." Closes loop: Brain plans → Operator executes → Verification observes and produces Evidence → Evidence reaches Brain → Brain decides `completed` vs re-plan vs escalate (§11).

### 10.3 Why Physically Near Operator but Architecturally Separate
Only Operator has Environment access (Brain has none §3.5). Verification Subsystem must run where Environment access exists. But does so through **own contract** — "observe, then compare against Expected Outcome" — never by reusing Worker's `validate()`/`run()`, never by folding result into plain Execution Result. Same location, different mechanism = "structurally independent."

### 10.4 What Is Deliberately Not Designed Here
Exact schema of "Expected Outcome"/"Observation", how comparisons computed, what counts as "partial" match — implementation questions, correctly out of scope. Fixed: three-part boundary and Verification never reuses Execution path.

---

## Amendment Process

**Freeze does not mean "never changes"** — changes go through `FOUNDER_CONSTITUTION_FREEZE.md` record with ADR, not silent edit.

### Amendment Process (per `FOUNDER_CONSTITUTION_FREEZE.md` §4a)
1. **Structural amendment:** Proposed by Mission Brief via ADR marked *Proposed*, applied **only after founder ratification** (precedent: MB025 ADR-0015, MB027 ADR-0017)
2. **Terminology reconciliation forced by shipping code:** May move in same commit (precedent: Amendment 1, ADR-0014)

### Amendments to Date

| # | Date | Mission Brief | What Changed | Backed By |
|---|------|---------------|--------------|-----------|
| 1 | 2026-07-26 | MB023 | §17 Terminology Freeze gains: **Executive** = synonym for **Worker** (Mission Control registration API term). No section status changed; no shipped code renamed | `docs/adr/0014-executive-and-worker-terminology.md` |
| 2 | 2026-07-29 | MB027 | **AI Capability Broker** becomes Shared Infrastructure component: new §5.7 (prior §5.7 → §5.8); §6 module table + "which Provider serves a request" row; §16 two rows (Broker → Shared Infrastructure, AI Infrastructure Executive → Operator); §17 two terms (AI Capability, Provider). §3.3 gains one sentence: Model Router consults Broker rather than ranking Providers itself. No section status changed; no shipped code renamed/modified | `docs/adr/0017-ai-capability-broker.md`, `AI_CAPABILITY_BROKER_ARCHITECTURE.md` |

**Precedent set:** Structural amendment = proposed by Mission Brief, applied only after founder ratification. Terminology reconciliation forced by shipping code = may move in same commit.

---

## Terminology Freeze (§17, Status: FROZEN)

Every term below has exactly one meaning in this Constitution and all documents it governs.

| Term | Definition |
|------|------------|
| **Brain** | Cognitive layer: Intent Layer, Planner, Model Router, Reporter (§3). Decides; never executes. |
| **Operator** | Execution layer: Orchestrator, Verification Subsystem, Worker/Plugin Runtime, Environment Session Management (§4). Executes; never decides. |
| **Worker** | Single registered unit of execution capability inside an Operator's Worker Runtime (today: an Action/Plugin). Not a layer — a component of §12. |
| **Executive** | Synonym for **Worker**, introduced by MB023 as term Mission Control's registration API uses (`ExecutiveRegistry`, `executive_id`). Same role, described from coordination layer. `Worker` stays canonical; neither term may get third synonym. See `docs/adr/0014-executive-and-worker-terminology.md`. |
| **AI Capability** | A *kind of intelligence* a Provider can supply — `reasoning`, `vision.ocr`, `speech.transcribe` (§5.7). Added by Amendment 2. **Distinct from Capability, never dispatchable on its own**: AI Capability is input to Provider selection; Capability is unit of execution. Written `lowercase.dotted`, Capabilities are `PascalCase.PascalCase` — mechanically distinguishable. |
| **Provider** | Any registered source of AI capability — local runtime, desktop application, cloud API, aggregator (§5.7). Added by Amendment 2. **Generalizes, does not replace, Reasoning Provider**: Reasoning Provider (§3.3) is a Provider offering `reasoning` AI Capability. Neither term may get third synonym. |
| **Environment** | Abstract category of place execution happens (Desktop, Browser, Terminal, VPS, future Robotics/IoT). Never a specific product (§7.2, §21). |
| **Environment Instance** | One concrete, addressable, live target within an Environment category (§7.4, §8.3). |
| **Environment Session** | Live handle an Operator Instance holds to one Environment Instance (§8.3). Owned by exactly one Operator Instance; never Shared Infrastructure. |
| **Capability** | Named unit of "what can be done" that a `Step` references; resolved to Worker (or Operator Instance, §8.4) at execution time via Capability Registry (§5.1). |
| **Action** | Concrete, atomic implementation of one Capability inside a Worker: validates parameters, then runs, producing Execution Result. |
| **Observation** | Freshly captured fact about real-world state, gathered by Verification Subsystem re-checking an Environment Instance (§10.2). Distinct from Execution Result. |
| **Evidence** | Observation + Expected Outcome + Verdict, packaged as durable record (§9.2, §10.2). |
| **Verification** | Act of comparing Observation against Expected Outcome to produce Verdict (§10). Reserved exclusively for this Mission-level meaning — never used for Knowledge Lifecycle's Promotion Review (§9.3). |
| **Knowledge** | Durable, *promoted* understanding the Brain actively consults during planning (§9). Distinct from raw Mission Record, which is history until promoted. |
| **Mission** | One complete Intent-to-Outcome unit of work; owns single Mission State instance (§5.3); may span multiple Steps, Capabilities, and Operator Instances (§8). |
| **Session** | Reserved for **Mission Session** — Brain-side conversational context where human states Intent and system carries one or more Missions to completion. Never used for Environment-level connection — that is always **Environment Session**. |
| **Task** | **Deprecated alias for Step.** Nothing distinguishes "Task" from `Step` (MissionPlan DAG node); Constitution retires "Task" in favor of `Step`. |
| **Step** | One DAG node of a `MissionPlan`, naming a Capability and an Expected Outcome (§3.2). |
| **Worker Instance** | One live, invocable registration of a Worker inside a specific Operator Instance (§12.4). |
| **Operator Instance** | One running instance of the Operator, bound to one (or small tightly-coupled set of) Environment Instance(s), tracked by Operator Registry (§8.2). |

---

## Open Questions

1. **In-mission recovery decision procedure** (§11.4, `FOUNDER_CONSTITUTION_FREEZE.md` §3.1): Exact rule for when Orchestrator's retry absorbs failure vs escalates to re-plan vs surfaces to human. Not a blocker for current `ROADMAP.md`.

2. **Stateful Environment Sessions inside Worker/Action contract** (§8.3, §12, `FOUNDER_CONSTITUTION_FREEZE.md` §3.2): Today's Action contract is one-shot (`validate()` → `run()`); Browser/Terminal/Robotics need capability holding live handle across multiple Steps. Not a blocker — no current Worker needs this.

3. **Concurrent dispatch across Operator Instances** (§8.5, `FOUNDER_CONSTITUTION_FREEZE.md` §3.3): Deliberately left EVOLVABLE per instruction not to design distributed system.

4. **MB006–MB020 absent** from repository and all known backups (`FOUNDER_CONSTITUTION_FREEZE.md` §3.4). Constitution does not depend on their content — every claim traces to verified document.

5. **Real Planner not yet implemented** (`ROADMAP.md` item 1) — `cli.py` regex stand-in active. Unblocked by Constitution freeze.

6. **Reporter not yet built** — `cli.py` completion messages stand in. Named in Constitution §3.4 as ownership gap closed.

7. **MissionManager not wired into live path** (`MEMORY_ARCHITECTURE.md` §11) — `cli.py`'s `MasterAgentSession` only working path.

8. **ADR-0015 (Persistence Strategy) Proposed** — three additive changes to frozen components awaiting ratification.

9. **ADR-0020 (Founder Approval Workflow) Proposed** — ships frozen-component changes.

---

## Wiki Links Added

- `[[KALPAVRIKSHA_VISION_V2.md]]` — source document
- `[[FOUNDER_CONSTITUTION_FREEZE.md]]` — freeze record, amendments
- `[[ARCHITECTURE.md]]` — implementation map
- `[[MEMORY_ARCHITECTURE.md]]` — six-layer memory design
- `[[FILESYSTEM_CAPABILITIES.md]]` — capability design template
- `[[ROADMAP.md]]` — prioritized future work
- `[[FOUNDER_PLAYBOOK.md]]` — Miracle build process
- `[[ENGINEERING_PRINCIPLES.md]]` / `[[PRODUCT_PRINCIPLES.md]]` / `[[ARCHITECTURE_PRINCIPLES.md]]` — value-to-practice mappings
- `[[DECISIONS.md]]` — ADR index
- `[[MIRACLE_LEDGER.md]]` — chronological shipment record
- `[[PROJECT_BRAIN.md]]` — current-state index
- `[[docs/adr/0005]]`–`[[docs/adr/0006]]` — permission relay pattern (Rule 6)
- `[[docs/adr/0007]]`–`[[docs/adr/0008]]` — memory backend and scale review
- `[[docs/adr/0009]]` — PermissionCategory + IRREVERSIBLE grant rule
- `[[docs/adr/0010]]` — Shared Infrastructure layer
- `[[docs/adr/0011]]` — Verification as independent subsystem
- `[[docs/adr/0012]]` — Knowledge Lifecycle
- `[[docs/adr/0013]]` — Multi-Operator / Environment Instance architecture
- `[[docs/adr/0014]]` — Executive/Worker terminology
- `[[docs/adr/0015]]` — Persistence strategy (Proposed)
- `[[docs/adr/0017]]` — AI Capability Broker (ratified)
- `[[docs/adr/0018]]` — Broker learning loop

---

## Future Extraction Recommendations

1. **`docs/MISSION_BRIEF_021_REVISION_3.md`** — full record of what changed in Revision 3 and why
2. **`AI_CAPABILITY_BROKER_ARCHITECTURE.md`** — detailed Broker design (Provider Registry, Decision Engine, etc.)
3. **`BROWSER_WORKER_ARCHITECTURE.md`** — reference Worker implementation against frozen Constitution
4. **`MISSION_CONTROL_ARCHITECTURE.md`** — coordination layer design (Event Bus, registries, queues)
5. **`RUNTIME_ENGINE_ARCHITECTURE.md`** — autonomous loop design (heartbeat, retry, ApprovalGate)
6. **`PERSISTENCE_ARCHITECTURE.md`** — event log + snapshot recovery design
7. **`verification/` package** — Verifier ABC, Evidence, Audit types (generic, Worker-reusable)

---

*Document created from verified source: `docs/architecture/KALPAVRIKSHA_VISION_V2.md` (v2, Revision 3, Frozen 2026-07-26). No inferences, no implementation details invented, terminology preserved exactly.*