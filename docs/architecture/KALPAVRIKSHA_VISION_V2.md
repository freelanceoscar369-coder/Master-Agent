# Kalpavriksha Architecture Constitution — Version 2 (Revision 3: Founder Constitution Freeze)

**Status:** Canonical Architecture Reference — Frozen
**Effective Date:** 2026-07-26
**Scope:** All Mission Briefs from MB021 forward
**Authority:** This document supersedes all prior Mission Briefs, ADRs, and design notes for architectural *decisions*. `ARCHITECTURE.md` remains authoritative for current *implementation* detail (module file layout, present-day data flow) and is read through this Constitution's terminology, not instead of it. Every section below carries a **Status** tag — see §18 for what each tag permits and forbids. See `FOUNDER_CONSTITUTION_FREEZE.md` for the freeze declaration and the audit trail that produced this revision.

---

## Revision history

- **v2 (2026-07-24):** First consolidation of MB001–005 + ARCHITECTURE.md + MEMORY_ARCHITECTURE.md + FILESYSTEM_CAPABILITIES.md into a single constitution.
- **v2, independent audit (2026-07-25):** Audited against internal consistency, completeness, separation of concerns, scalability, product independence, and vision alignment. Findings: a claimed "absolute boundary" between Brain and Operator was contradicted by shared infrastructure (Plugin Registry, Memory) neither column accounted for; product names (Hermes, Ollama, ChatGPT, VS Code, Obsidian) were load-bearing in principle-level prose, contradicting this document's own Product Agnosticism claim; Verification was nominally but not structurally independent from Execution; several real, working classes (`MasterAgentSession`, `MissionManager`, `Reporter`) were unplaced by the Brain/Operator model; several rules were duplicated across sections; multi-worker/multi-environment/multi-operator scaling was either explicitly disclaimed or unaddressed.
- **Revision 3 (this document, 2026-07-26):** Resolves every item above. See `docs/MISSION_BRIEF_021_REVISION_3.md` for the full record of what changed and why.
- **Amendment 1 (2026-07-26, MB023):** §17 gains one row recording **Executive** as a synonym for **Worker** — the term MB023's Mission Control registration API uses for the same role. This is the first amendment made under the freeze process, and it follows that process exactly: Constitution and `FOUNDER_CONSTITUTION_FREEZE.md` updated together, backed by `docs/adr/0014-executive-and-worker-terminology.md` with rejected alternatives recorded. No section's status changed; no shipped code was renamed.
- **Amendment 2 (2026-07-29, MB027):** The **AI Capability Broker** is placed in Shared Infrastructure as §5.7 (prior §5.7 renumbered to §5.8), added to §6's module table and §16's Ownership Registry alongside the **AI Infrastructure Executive**, and §17 gains **AI Capability** and **Provider**. §3.3 gains one clarifying sentence: the Model Router consults the Broker to resolve *which* Reasoning Provider, rather than implementing its own ranking — its interface, its role, and all four of its criteria are unchanged. Backed by `docs/adr/0017-ai-capability-broker.md` (ratified by the founder, 2026-07-29) and `AI_CAPABILITY_BROKER_ARCHITECTURE.md`. No section's status changed; no shipped code was renamed or modified.

---

## Table of Contents

1. [Project Vision](#1-project-vision) — FROZEN
2. [Core Principles](#2-core-principles) — FROZEN
3. [Executive Brain Responsibilities](#3-executive-brain-responsibilities) — FROZEN
4. [Universal Executive Operator Responsibilities](#4-universal-executive-operator-responsibilities) — FROZEN
5. [Shared Infrastructure Layer](#5-shared-infrastructure-layer) — FROZEN (§5.7 RESEARCH-BACKED, see subsection)
6. [Brain / Shared Infrastructure / Operator Separation](#6-brain--shared-infrastructure--operator-separation) — FROZEN
7. [Universal Environment Philosophy](#7-universal-environment-philosophy) — EVOLVABLE
8. [Multi-Operator Architecture](#8-multi-operator-architecture) — RESEARCH-BACKED
9. [Knowledge Philosophy and Lifecycle](#9-knowledge-philosophy-and-lifecycle) — mixed, see subsections
10. [Verification Philosophy](#10-verification-philosophy) — RESEARCH-BACKED
11. [Recovery Philosophy](#11-recovery-philosophy) — EVOLVABLE
12. [Worker and Plugin Runtime](#12-worker-and-plugin-runtime) — IMPLEMENTATION DETAIL
13. [Environment Independence](#13-environment-independence) — FROZEN
14. [Product Agnosticism](#14-product-agnosticism) — FROZEN
15. [Human Oversight Philosophy](#15-human-oversight-philosophy) — FROZEN
16. [Ownership Registry](#16-ownership-registry) — FROZEN
17. [Terminology Freeze](#17-terminology-freeze) — FROZEN
18. [Section Status Legend](#18-section-status-legend) — FROZEN
19. [Long-term Founder Edition Vision](#19-long-term-founder-edition-vision) — EVOLVABLE
20. [Immutable Architecture Rules](#20-immutable-architecture-rules) — FROZEN
21. [Illustrative Implementations](#21-illustrative-implementations) — IMPLEMENTATION DETAIL
22. [Appendix: Source Document Traceability](#22-appendix-source-document-traceability)

---

## 1. Project Vision
**Status: FROZEN**

**Kalpavriksha** (the wish-fulfilling tree) is an AI orchestration platform that turns a stated human intention into a completed, verified outcome — not a chat response, not a suggestion, but a real-world result the human can see, touch, and trust.

### The Kalpavriksha Loop

```
Intent → Plan → Delegate → Execute → Verify → Learn → Report
```

Every interaction follows this loop. No step is optional. No step is bypassed.

### What Kalpavriksha Is

- An **orchestration layer** between human intent and software execution
- A **plugin architecture** where every capability is a Worker behind a single contract
- A **local-first, cloud-enhanced** system: fully functional with a purely local Reasoning Provider and local Memory; cloud Reasoning Providers are opt-in enhancements
- A **permission-gated execution engine**: nothing above read-only risk executes without explicit human approval
- A **memory system** that survives process restarts and feeds future planning

### What Kalpavriksha Is Not

- A chatbot or LLM wrapper
- A replacement for the human's judgment
- A cloud-dependent service
- A monolith that must be rewritten to add capabilities
- A single, unscalable Operator — see §8

---

## 2. Core Principles
**Status: FROZEN**

Design constraints the architecture is answerable to.

### 2.1 Intent Over Prompts
The system captures a structured `Intent` (goal, constraints, context, success criteria), never a raw string handed straight to a model.

### 2.2 Outcome Over Output
A Mission is "done" only when Verification (§10) confirms real-world state matches the Intent's success criteria — never when a model produces text.

### 2.3 Everything Is a Worker Behind a Capability
Reasoning Providers, capabilities, transport adapters — all are Workers behind the same Capability Registry and contract (§5, §12). The core engine is small; almost all capability lives in Workers.

### 2.4 Human Approval Before Important Actions
No Worker executes a step classified above `READ_ONLY` risk without a grant from the Permission System (§5). The Permission System has veto power over the Operator — it is not optional middleware, it is a gate.

### 2.5 Local-First, Cloud-Enhanced
The system must be fully functional offline against a Local Reasoning Provider and local Memory. Cloud Reasoning Providers are an enhancement the Model Router opts into, never a hard dependency. This principle is defined architecturally, not by naming any specific model or runtime — see §14.

### 2.6 Replaceable Modules
Every module is swappable behind its interface without touching the others. This is what makes "build for one founder first, scale for millions later" possible.

### 2.7 Minimum Manual Work, Maximum Agent Work
The agent does the execution, the human approves and directs. (Single canonical statement — see §15.3 for the mechanism this requires; do not restate this principle's content elsewhere, cross-reference it.)

---

## 3. Executive Brain Responsibilities
**Status: FROZEN**

The **Executive Brain** is the cognitive layer. It decides *what* to do, *how* to structure it, and *how to explain it back*. It owns Intent, Planning, Reasoning-Provider selection, and Reporting. It never executes, never touches an Environment, and never holds a Permission grant.

### 3.1 Intent Layer
Turns raw input into a structured `Intent` (goal, constraints, context, success criteria). Owns follow-up clarification when intent is ambiguous. Deliberately **not** "send the raw string to a model" — a real parsing/clarification step so the Planner never has to guess.

**Current stand-in:** `cli.py`'s regex-based `parse_intent()` plays this role today (Mission Briefs 001, 003.1, 005). The real Intent Layer is a stub pending the real Planner (`ROADMAP.md` item 1).

### 3.2 Planner
Takes an `Intent`, produces a `MissionPlan`: a DAG of `Step` objects, each naming a required **Capability** — never a specific Worker (Shared Infrastructure resolves Capability → Worker at execution time, per §5, so plans stay portable). Every `Step` a Planner emits also names an **Expected Outcome** — a machine-checkable description of what "done" looks like for that Step — so that Verification (§10) has something concrete to compare Observation against. This is the interface the previous revision was missing: without it, Verification has no way to know what to check, because the Operator (by design) has no concept of "intent," only "capability."

Calls a Reasoning Provider through the Model Router — planning is a capability like any other. Reads recent Mission history and Permanent Knowledge (§9) as context for "have I done something like this before."

### 3.3 Model Router
Single Reasoning Provider interface (`generate(prompt, context, **opts) -> ModelResponse`). Picks a provider per call based on:

1. **Connectivity** — offline ⇒ Local Reasoning Provider only
2. **Privacy sensitivity** — anything tagged sensitive by the Intent Layer stays on the Local Reasoning Provider unless the human explicitly overrides
3. **Task profile** — routine steps default to the Local Reasoning Provider (cheap, fast, private); steps declaring a need for stronger reasoning escalate to a Cloud Reasoning Provider
4. **Explicit user preference** — always wins

**Amendment 2 (MB027):** the Model Router **consults the AI Capability Broker (§5.7) to resolve *which* Reasoning Provider**, rather than implementing its own ranking. Its interface, its role as the Brain's single door to reasoning, and all four criteria above are unchanged — each one maps onto a phase of the Broker's decision engine (`AI_CAPABILITY_BROKER_ARCHITECTURE.md` §6.5), with one stated narrowing: criterion 4's "always wins" is honoured among candidates that survive the Broker's hard-constraint filter, so a preference can never select a Provider that is unavailable, licence-barred, privacy-barred, or paid-without-approval.

The Model Router resolves *which registered Reasoning Provider* to invoke by querying Shared Infrastructure's Capability Registry (§5.1) — the same registry the Operator's Orchestrator queries to resolve execution capabilities. This is not a boundary violation: both the Brain and the Operator depend downward on Shared Infrastructure; neither depends on the other (§6). Adding a new Reasoning Provider means registering one new Worker, never touching Model Router or Orchestrator logic.

### 3.4 Reporter
Takes a Mission's outcome plus its Evidence (§10) once Verification has produced a Verdict, and composes the human-facing report (text today; voice, later). Decides *how to explain what happened* — a Brain-shaped judgment (what to say, how much detail, what tone), not an execution fact. Never touches an Environment; only reads Evidence and Mission state through Shared Infrastructure.

**Current status:** not yet built as a distinct module — `cli.py`'s completion messages play this role today. Named here explicitly because it was missing from the previous revision's model entirely (see `FOUNDER_CONSTITUTION_FREEZE.md` §"Ownership gaps closed").

### 3.5 What the Brain Does NOT Do
- Does not execute capabilities
- Does not hold or check Permission grants
- Does not own Mission State (Shared Infrastructure does, §5)
- Does not persist Memory itself (Shared Infrastructure does; the Brain reads it and nominates Knowledge Candidates, §9)
- Does not verify outcomes (it consumes Evidence; it does not produce it, §10)
- Does not know what an Environment Instance is (§8) — only that a Step requires a Capability

---

## 4. Universal Executive Operator Responsibilities
**Status: FROZEN**

The **Universal Executive Operator** is the execution layer. It carries out what the Brain decided, with full accountability. It never decides, never plans, and never holds an opinion about *why* a Step exists — only *how* to run it safely and *whether it actually worked*.

### 4.1 Orchestrator
Walks a `MissionPlan`, and for each `Step`:
1. Resolves Capability → Worker via Shared Infrastructure's Capability Registry (§5.1)
2. Checks the Permission System (§5.2) via Shared Infrastructure
3. Invokes the Worker, captures the result
4. Triggers Verification (§10) against the Step's Expected Outcome
5. Applies retry/failure-branching policy (§11.1) — bounded, deterministic, and scoped to this Operator Instance; it never re-plans

### 4.2 Worker Runtime
See §12 — Worker Runtime (formerly "Worker Architecture") is Operator-owned implementation detail, not a distinct architectural layer.

### 4.3 Verification Subsystem
See §10. Runs alongside the Operator (it needs Environment access, which only the Operator has) but through its own contract, never through a Worker's `invoke()`.

### 4.4 What the Operator Does NOT Do
- Does not decide what a Mission should accomplish
- Does not maintain its own private copy of Permission grants, Mission state, or Memory — all three are Shared Infrastructure (§5), specifically so that multiple Operator Instances (§8) never disagree about what's already been approved, what state a Mission is in, or what happened before
- Does not nominate or promote Knowledge (§9) — it produces Evidence; the Brain and Promotion Review decide what becomes durable

---

## 5. Shared Infrastructure Layer
**Status: FROZEN**

```
        Executive Brain
              │
     Shared Infrastructure
              │
   Universal Executive Operator
```

This diagram describes **dependency direction**, not sequential data flow (consistent with `ARCHITECTURE_PRINCIPLES.md`'s existing "dependencies point inward" rule — this is one more foundation tier under it, not a new philosophy). Both the Brain and the Operator depend downward on Shared Infrastructure; Shared Infrastructure depends on neither. Multiple Brain-side components and multiple Operator Instances (§8) may read and write Shared Infrastructure concurrently — it is not a pipe one message flows through once.

**Why this layer exists.** The prior revision claimed "the boundary is absolute" between Brain and Operator while assigning Plugin Registry and Memory exclusively to the Operator's column. Verified against the actual source (`plugins/registry.py`, `plugins/model_router.py`), the Model Router — a Brain component — constructs directly against the Plugin Registry, and the registry's own docstring states it is "the only thing the Orchestrator **and** Model Router talk to." A two-column model cannot represent a component both columns genuinely depend on without either duplicating it (causing drift) or misassigning it (causing the exact contradiction the audit found). A third, foundational layer resolves this without weakening either boundary: Brain and Operator are still forbidden from depending on *each other's* internals; they are both permitted — required — to depend on Shared Infrastructure's public contracts.

### 5.1 Capability Registry (formerly "Plugin Registry")
**Belongs here because:** it is queried by the Brain's Model Router (to resolve a Reasoning Provider) and the Operator's Orchestrator (to resolve an execution capability) — the same lookup mechanism serving two different callers. If duplicated per-side, or per-Operator-Instance (§8), capability resolution could diverge — one Operator Instance believing a capability exists that another doesn't. One registry, one answer, regardless of who's asking.

Today this is one component with two indices (plugin identity, capability → plugin), not two separate registries — "Capability Registry" and "Plugin Registry" name the same thing. A future capability-resolution *policy* (e.g., choosing between two Workers that both expose the same Capability) is an evolution of this registry's lookup logic, not a new component — marked EVOLVABLE.

### 5.2 Permission System
**Belongs here because:** it must remain a single, consistent grant ledger across every Operator Instance a Mission might touch. If each Operator Instance held its own grant table, a human approving a destructive capability once, for one Operator, could be silently re-satisfied — or silently re-asked — by a different Operator executing a different Step of the *same* Mission. Elevating Permission System to Shared Infrastructure is what makes "one approval per mission" (§15.3) a Mission-wide guarantee instead of an accidental, per-Operator-Instance one. This does not weaken its veto power — it strengthens it: it becomes the one gate every Operator Instance must pass through, not each Operator's private opinion of what's allowed.

The relay pattern (an outer approval explicitly carried down to an inner grant key, ADR-0005/0006) is unchanged by this move — see §20, Rule 6.

### 5.3 Mission State
**Belongs here because:** a single Mission's Steps may be serviced by different Operator Instances (§8) — e.g., one Step needs a Desktop Environment, the next needs a Browser Environment. If Mission State were owned by "the Operator" as a single entity, it's unclear *which* Operator Instance owns it. This is also the correct, permanent home for what the codebase calls `MissionManager` and the `Mission` state machine (`draft → planned → awaiting_approval → executing → verifying → completed | failed | cancelled`) — resolving the ownership gap named in the prior audit (§16).

### 5.4 Memory
**Belongs here because:** every Operator Instance's Evidence must aggregate into one durable history, not fragment into per-Operator silos — otherwise a future Planner call asking "have I done something like this before" only ever sees what one Operator Instance happened to do. All six Memory layers (`MEMORY_ARCHITECTURE.md`) live here, including the durable, queryable form of execution history (see 5.6, Telemetry/Audit).

### 5.5 Configuration
**Belongs here because:** Environment roots, Reasoning Provider defaults, and policy configuration must be identical regardless of which Brain-side or Operator-side component reads them — configuration drift between two readers of "what's the allowed filesystem root" is a safety bug waiting to happen, not a style question.

### 5.6 Telemetry and Audit (aggregated form)
**Split responsibility, on purpose:** raw log emission (one Worker ran, took *n* seconds, succeeded or failed) happens locally, at the Operator Instance or Worker Instance that did the work — that part is *not* Shared Infrastructure, because it doesn't need to be (see §8, §12). What *is* Shared Infrastructure is the durable, queryable, cross-Operator-Instance aggregation of that telemetry — the same mechanism Memory already provides (an Executor-style log folding into a Mission Record, `MEMORY_ARCHITECTURE.md` §4). "Audit" and "Evidence" (§10) are not two separate components — Evidence *is* the audited, verified subset of telemetry that made it into Memory.

### 5.7 AI Capability Broker
*(Added by Amendment 2, MB027. Full design: `AI_CAPABILITY_BROKER_ARCHITECTURE.md`; decision: `docs/adr/0017-ai-capability-broker.md`.)*

The single intelligence-selection service. Every component that needs AI — the Brain's Model Router and Planner, and every Worker that needs reasoning, vision, OCR, speech, or embeddings mid-task — asks the Broker *which* Provider should serve the request. **No other component may decide.** It owns the Provider Registry, the Capability Matrix, the Decision Engine, the Cost Model, the Benchmark Store, the Approval Policy, the AI Asset Inventory, and the Recommendation Engine.

**Belongs here because:** both the Brain and the Operator need the same answer to the same question, which is precisely the condition this layer exists to satisfy (ADR-0010). One copy per side would drift; assigning it to either side recreates the crossed-boundary contradiction the independent audit found in the prior revision. Its state is also a set of ledgers — spend, standing approvals, benchmark aggregates — which must be singular across every Operator Instance for the same reason the Permission System must be (§5.2): two Operator Instances disagreeing about what has already been approved or already been spent is a safety bug, not an inconsistency. And it must be consulted *before* dispatch, so it cannot be a thing that is dispatched.

**The boundary that keeps it here:** the Broker **decides and never touches the machine.** It executes nothing, opens no connection, imports no provider SDK, spends nothing, retries nothing, and grants no permission — it *requires* permission, through §5.2. Its output names an already-registered Capability plus parameters, which the caller runs through the Operator like any other Capability, so **the Broker creates no new execution path**. Everything that requires touching the machine — scanning, probing, benchmarking, inventory, and Founder-approved installation — belongs to the **AI Infrastructure Executive**, an ordinary Worker (§12, §16).

**Status: RESEARCH-BACKED** — the design is reasoned through and frozen (MB027), but not yet implemented. Expect refinement once real usage exists, the same way ADR-0008 refined Memory. Its learning loop (`AI_CAPABILITY_BROKER_ARCHITECTURE.md` §19) is EVOLVABLE by construction: the Broker's *decision procedure* stays deterministic and replayable; what evolves is the versioned policy it reads, and only through Promotion Review (§9.3, §15.5).

### 5.8 What Is Deliberately NOT Shared Infrastructure
- **Environment Session Management** — a live handle to one specific Environment Instance (an open browser tab, a live SSH connection) belongs to whichever Operator Instance opened it. Sharing it centrally would mean one Operator Instance could reach into another's live connection — a safety and isolation violation, not a convenience. See §8.3.
- **Mission Session** (the Brain-side conversational entry point, today's `MasterAgentSession`) — see §16. It is Brain-adjacent glue on a path to dissolving into the Brain proper; it is not infrastructure multiple Operator Instances depend on.
- **Machine scanning, provider probing, benchmarking, inventory capture, and installation** *(added by Amendment 2, MB027)* — these are Environment access, and Rule 4 gives Environment access exactly one door. They belong to the AI Infrastructure Executive, not to the Broker they feed. A kernel service that scanned hosts would be a kernel service with an Environment dependency.

---

## 6. Brain / Shared Infrastructure / Operator Separation
**Status: FROZEN**

| Aspect | Executive Brain | Shared Infrastructure | Universal Executive Operator |
|---|---|---|---|
| **Role** | Decides *what* and *how to structure it*, and *how to explain it* | Provides the one consistent source of truth both sides depend on | Carries out *what* was decided, with accountability |
| **Modules** | Intent Layer, Planner, Model Router, Reporter | Capability Registry, Permission System, Mission State, Memory, Configuration, Telemetry/Evidence aggregation, AI Capability Broker | Orchestrator, Verification Subsystem, Worker/Plugin Runtime, Environment Session Management |
| **Reasoning-Provider calls** | Yes | No | No |
| **Which Provider serves a request** | Asks; never decides | **Decides — the AI Capability Broker (§5.7), and nothing else may** | Asks; never decides |
| **Environment access** | Never | Never | Only through a Worker, via an Environment Session it owns |
| **Permission checks** | Never issues, never checks | Holds and adjudicates every grant | Every step above READ_ONLY is checked here, against Shared Infrastructure |
| **Mission State** | Reads (context) | Owns | Transitions it, through Shared Infrastructure's contract, never a private copy |
| **Memory** | Reads; nominates Knowledge Candidates | Owns; stores and serves | Writes Evidence into it, through Shared Infrastructure's contract |
| **Replaceability** | Swap Planner, swap Reasoning Providers | Swap the storage/backing implementation behind any of §5's components | Swap Orchestrator policy, swap Worker Runtime, add Operator Instances |

**The boundary is precise, not "absolute" in the sense the prior revision claimed.** Brain and Operator never depend on each other's internals — that boundary is real and unchanged. What was inaccurate was implying there is *nothing* both sides legitimately share; there is, and §5 names it, gives it a contract, and explains why each piece lives there. A dependency on Shared Infrastructure is not a boundary violation; a dependency from the Brain straight into the Operator's Orchestrator, or vice versa, would be.

---

## 7. Universal Environment Philosophy
**Status: EVOLVABLE** — the philosophy below is stable; the roster of supported Environments is expected to keep growing, by design, without changing this section.

### 7.1 Local-First Is Not Optional
The system must boot, plan, and execute a meaningful Mission with a purely local Reasoning Provider and local Memory. Cloud Reasoning Providers are Workers the Model Router may select when beneficial — never a prerequisite.

### 7.2 Environment as an Abstract Category
An **Environment** is an abstract category of place execution happens — Desktop Environment, Browser Environment, Terminal Environment, VPS Environment, and (future) Robotics/IoT Environments — never a specific product. The core engine does not care which Environment category a Mission touches; that is a Worker/Environment Session concern (§12, §16).

### 7.3 No Environment Assumptions in Core
No hardcoded paths (locations injected via configuration, §5.5). No product-specific logic in core modules. No assumption about process lifetime.

### 7.4 Environment vs. Environment Instance
"Environment" names a *category*. "Environment Instance" (§17) names one concrete, live, addressable target within that category — this specific desktop, this specific browser tab, this specific VPS. Conflating the two is exactly what made the prior revision's Environment section read as "which host process the engine happens to run inside" rather than "what the Operator can act upon," which is why §8 exists as its own section.

---

## 8. Multi-Operator Architecture
**Status: RESEARCH-BACKED** — this section defines the shape the architecture must not block; it does not design a distributed system, per this revision's explicit constraint.

### 8.1 The problem this section resolves
The prior revision's Operator was implicitly singular — "the Operator" — with no identity, no registry, and an explicit disclaimer that there is "no worker pool or agent swarm." That's a correct description of today's single-process CLI, but it left no answer for what happens when Founder Edition needs multiple desktops, multiple browser sessions, multiple VPS instances, or future robots active at once. This section defines the shape without building it.

### 8.2 Operator Instance
One running instance of the Universal Executive Operator, bound to one (or a small, tightly-coupled set of) Environment Instance(s) — e.g., "the Operator Instance running on Desktop A," "the Operator Instance managing Browser Session B." Tracked by an **Operator Registry**, itself part of Shared Infrastructure's Capability Registry (§5.1) — an Operator Instance advertises which Capabilities it can currently service, the same way a Worker does.

### 8.3 Environment Instance and Environment Session
An **Environment Instance** is one concrete, addressable target (§7.4). An **Environment Session** is the live handle an Operator Instance holds to one Environment Instance — an open browser tab, a live SSH connection, a running desktop process. Environment Sessions are owned by exactly one Operator Instance and are never Shared Infrastructure (§5.8) — sharing a live connection across Operator Instances would violate the isolation that makes Permission grants and safety boundaries meaningful per Environment.

### 8.4 How a Mission spans multiple Operator Instances
A `Step` may name, alongside its Capability, a required Environment category (e.g., "this Step needs a Browser Environment"). Shared Infrastructure's Capability Registry resolves *which* live Operator Instance can service that Step at execution time — exactly the same resolution philosophy already established for Capability → Worker (§3.2, §5.1), extended one level, not reinvented. Because Permission System, Mission State, and Memory are Shared Infrastructure (§5), a Mission spanning three Operator Instances still has exactly one grant ledger, one state machine, and one Memory record — this is *why* §5's resolution is a prerequisite for this section, not a coincidence.

### 8.5 Concurrency — scoped explicitly, not designed
A `MissionPlan`'s DAG already permits independent, parallel branches in principle — nothing in the `Step`/Capability/Worker contract requires strictly serial execution, and nothing about adding Operator Instances requires redesigning that contract. Whether a future Orchestrator actually dispatches independent DAG branches to different Operator Instances concurrently, and what failure-isolation that requires, is deliberately **not designed here** — it is a natural extension point flagged EVOLVABLE, consistent with this revision's instruction not to design a distributed system. Today's implementation remains single-Operator-Instance, sequential, exactly as `ARCHITECTURE.md` describes it.

### 8.6 What this section does not claim
No cross-machine consensus protocol, no distributed transaction model, no operator-to-operator negotiation. Multi-Operator support means the *contracts* (Capability resolution, Permission grants, Mission State, Memory) already generalize to more than one Operator Instance without changing shape — not that a distributed runtime exists today.

---

## 9. Knowledge Philosophy and Lifecycle

### 9.1 Permanent Knowledge and Temporary Observations
**Status: FROZEN** (unchanged from v2 — this held up under audit)

**Permanent Knowledge (persisted, queryable):** Mission History (every Mission's intent, plan, approval, execution result, artifacts, errors) and User Preferences.

**Temporary Observations (in-process only):** Conversation Memory (current session's turns) and Mission Memory (the Mission currently executing).

### 9.2 Evidence Hierarchy (Strongest to Weakest)
**Status: FROZEN** (unchanged — the audit specifically flagged this as the document's best, most load-bearing quality)

1. **Observed Reality** — what the Environment actually shows, what Verification actually measured
2. **Evidence** (§10.3) — the structured, timestamped record of an Observation compared against an Expected Outcome
3. **Mission Record** — the persisted record (intent, plan, approval, outcome, artifacts), derived from execution, survives restart
4. **Conversation Transcript** — useful for debugging human intent, not for determining what happened
5. **Reasoning Provider Output** — what a model *said* it would do or *said* happened — never treated as evidence of reality

**When documentation and observed reality conflict, observed reality wins** (§20, Rule 8). This rule now explicitly extends to Permanent Knowledge (§9.4) — a rule that was previously implicit for Mission-level facts and is now stated for durable knowledge too, closing a real gap rather than introducing a new principle.

### 9.3 The Knowledge Lifecycle
**Status: RESEARCH-BACKED** — newly designed this revision; sound in principle, not yet implemented or battle-tested.

```
Execution → Evidence → Knowledge Candidate → Promotion Review → Permanent Knowledge → Future Reasoning
```

Note the deliberate rename of the lifecycle's fourth stage from "Verification" (as originally proposed) to **Promotion Review** — see §17 for why: "Verification" is reserved for exactly one meaning (§10, Mission-level real-world-state checking). Reusing it here for a different process — deciding whether an accumulated pattern deserves to become durable knowledge — would violate this revision's own terminology-freeze requirement. Promotion Review is a distinct gate that *reuses* the same evidentiary discipline as Verification, but checks a different question ("is this pattern trustworthy enough to shape future reasoning," not "did this Step's execution match its Expected Outcome").

**Stage ownership:**

| Stage | Owner | What happens |
|---|---|---|
| Execution | Operator (a Worker, within an Operator Instance) | Produces effects in an Environment Instance |
| Evidence | Verification Subsystem (§10), stored via Shared Infrastructure | Observation + Expected Outcome + Verdict, packaged as a durable record |
| Knowledge Candidate | Brain (Planner) | The Brain — not the Operator — recognizes a recurring, generalizable pattern in accumulated Evidence and nominates it. This is a reasoning judgment ("is this worth remembering as reusable"), not an execution fact, so it belongs to the Brain. |
| Promotion Review | A dedicated gate, human-confirmed for Founder Edition | Checks the Candidate against a promotion bar: observed enough times, not contradicted by other Evidence, not already superseded by existing Permanent Knowledge. See 9.4 for why this stays human-gated for now. |
| Permanent Knowledge | Shared Infrastructure (Memory, Layer 4 — "Knowledge Memory," `memory/future.py`) | Durable, queryable, actively consulted |
| Future Reasoning | Brain (Planner) | Consumes Permanent Knowledge the same way it already consumes recent Mission history |

### 9.4 Who can promote knowledge, who can reject it
Promoting a Knowledge Candidate changes the Brain's future reasoning *permanently and silently* for every subsequent Mission — this is exactly the class of high-leverage, hard-to-reverse action §15 ("Human Approval Before Important Actions") already exists to gate. For Founder Edition, **Promotion Review requires human confirmation**, the same "one clear decision point" pattern already used for destructive capabilities (§15, §20 Rule 5). This is not a new mechanism — it is the existing Human Oversight principle applied to a new class of consequential action. Automating Promotion Review later is a legitimate evolution (EVOLVABLE), not a change to this principle: the human gate can be relaxed once there is a track record to justify it, the same judgment call this project already applies elsewhere ("don't build the general version until concrete examples exist to generalize from," `ENGINEERING_PRINCIPLES.md` #10).

**Rejection** happens two ways: Promotion Review can reject a Candidate outright (it never becomes Permanent). Separately, Permanent Knowledge itself must be revocable — if new, higher-tier Evidence (§9.2) later contradicts an existing entry, that entry is flagged for re-review and the Brain must not treat it as reliable until reconfirmed or retired. This is §9.2's Evidence Hierarchy applied continuously, not just at promotion time.

### 9.5 How temporary observations differ from permanent knowledge
The dividing line is exactly the Promotion Review gate (9.4) — nothing crosses from "recorded" to "actively shapes future reasoning" without passing through it. A Mission's raw Evidence is history the moment it's recorded; it only becomes Knowledge — something the Planner actively consults, not just could look up — once promoted.

---

## 10. Verification Philosophy
**Status: RESEARCH-BACKED** — redesigned this revision to be structurally, not just nominally, independent from Execution.

### 10.1 The problem this section resolves
The prior revision claimed Verification was "a distinct step... not merged into execution," but its only described mechanism was a Verifier invoked as "a final Step in every plan" — through the exact same `Plugin.invoke()` path as any execution capability. That made the *state* distinct (a `verifying` Mission status exists) but not the *mechanism*. This revision fixes the mechanism.

### 10.2 The three-part boundary

**Execution produces effects.** A Worker's Action runs, does the work, and returns an Execution Result — did it run without raising an error, what did it output. This says nothing about whether the *real-world* outcome is what was actually wanted; it only says the attempt didn't crash.

**Verification produces Evidence.** After (or during) execution, the Verification Subsystem — a distinct component with its own contract, not a Worker invoked through the Capability path — re-observes the relevant Environment Instance and compares what it finds (an **Observation**) against the **Expected Outcome** the Planner attached to the Step (§3.2). The output is a **Verdict** (matched / did not match / partially matched) plus the Observation and Expected Outcome it was compared against — together, this bundle is **Evidence** (§9.2).

**Evidence flows back to the Brain.** Evidence is not merely filed into Memory for later audit — it is specifically routed to the Brain (via Shared Infrastructure) as the input to "is this Mission actually complete, or does it need another Step." This closes the loop the prior revision left open: Brain plans → Operator executes → Verification Subsystem observes and produces Evidence → Evidence reaches the Brain → the Brain decides `completed` versus re-plan versus escalate (§11).

### 10.3 Why Verification stays physically near the Operator but architecturally separate from it
Only the Operator has Environment access (the Brain, by design, has none — §3.5). So the Verification Subsystem must run where Environment access exists. But it does so through its **own** contract — "observe, then compare against an Expected Outcome" — never by reusing a Worker's `validate()`/`run()` path, and never by folding its result into a plain Execution Result. Same location, different mechanism: that is what "structurally independent" means here, and it's a stricter bar than the prior revision met.

### 10.4 What is deliberately not designed here
The exact schema of an "Expected Outcome" or "Observation" object, how comparisons are computed, and what counts as "partial" match are implementation questions, correctly out of scope for a design-only revision. What is fixed: the three-part boundary (Execution / Verification / Evidence-to-Brain) and that Verification never reuses the Execution path.

---

## 11. Recovery Philosophy
**Status: EVOLVABLE** — this revision connects Recovery to Verification's new design; it does not close every gap the prior audit found, and says so explicitly below.

### 11.1 Mission-Level Recovery
The `Mission` state machine (owned by Shared Infrastructure, §5.3) enables precise recovery: if a process dies mid-execution, Mission State says what was attempted, and Evidence (§10) says what was actually confirmed to have happened. Idempotent Actions make re-running safe.

**New this revision:** a failed Verdict (§10.2) is the trigger for recovery, not a silent dead end. When Verification produces a Verdict of "did not match," that Evidence flows to the Brain (§10.2) exactly like a successful Verdict does — the difference is what the Brain does with it: retry the Step (if the Orchestrator's bounded retry policy, §4.1, hasn't already exhausted it), re-plan a replacement Step, or surface the Mission as failed for human attention. This connects §10 and the pre-existing Orchestrator retry/failure-branching responsibility (§4.1) explicitly, which the prior revision's Recovery section never referenced at all.

### 11.2 System-Level Recovery
Memory (Shared Infrastructure, §5.4) is the durable anchor and survives restart. Persistence is automatic, not manually triggered. The repository (or its equivalent durable store) is the source of truth for architecture history; any packaging/delivery mechanism is transport only.

### 11.3 No Silent Corruption
Zero tolerance for silent data loss, drift, or gaps. Live verification against a real process is mandatory, not optional, for every Miracle.

### 11.4 Named, open gap (not resolved by this revision)
The precise **in-mission recovery decision procedure** — exactly which failure classes the Orchestrator's own retry/branching policy (§4.1) can absorb without involving the Brain, versus which must escalate to a full re-plan, versus which must surface to a human — is still not fully specified. §11.1's new connective sentence states *that* a failed Verdict reaches the Brain; it does not yet specify the decision rule for what the Brain (or the Orchestrator, before escalating) does with it. This is named honestly here, per Rule 10 (§20), as a real, scoped, future design item — not a blocker for freezing the rest of this Constitution, since no work currently on `ROADMAP.md` (the real Planner, item 1) depends on it being resolved first. See `FOUNDER_CONSTITUTION_FREEZE.md` for the Final Review's treatment of this gap.

---

## 12. Worker and Plugin Runtime
**Status: IMPLEMENTATION DETAIL** — demoted from a peer architectural section in the prior revision; it is Operator-owned mechanism, not a fourth layer.

### 12.1 Why this is not a separate layer
The prior revision's "Worker Architecture" section stated, in its own first line, that "there is no worker pool or agent swarm in the core" — i.e., it described Plugin Runtime (§4) under a different name. Keeping it as a peer section next to Brain/Operator/Shared Infrastructure implied a fourth architectural concern that doesn't structurally exist, and risked the same content drifting apart under two headings. It is consolidated here as Operator-owned implementation detail.

### 12.2 Workers are Capabilities' implementations
Every Capability is implemented by a Worker (Action or Plugin, in current terminology) registered on the Operator's Worker Runtime. Adding Worker #201 costs one new file; it never means editing the Capability Registry, the Permission System, or the Orchestrator (§20, Rule 3).

### 12.3 Composite Workers
A Worker may orchestrate other Workers (e.g. a project-bootstrap capability composed from folder-creation and file-write capabilities) — but only through the same Shared Infrastructure Capability Registry and Permission System every other caller uses, relaying its own already-obtained grant down to each sub-step (§20, Rule 6). This is the **single** statement of that rule in this document — see §20 for why it no longer appears three times.

### 12.4 Worker Instance
One live, invocable registration of a Worker inside a specific Operator Instance's Worker Runtime — distinguishing "the concept of a capability" from "the specific registered copy of it running inside Operator Instance #3" (§17).

---

## 13. Environment Independence
**Status: FROZEN**

- No hardcoded Environment assumptions: all locations injected via configuration (§5.5)
- No product-specific logic in core modules
- No assumption about process lifetime baked into the core

---

## 14. Product Agnosticism
**Status: FROZEN** — now actually enforced (§21), correcting the prior revision's self-contradiction.

### 14.1 The Core Knows No Product
The architecture does not assume a specific Reasoning Provider, Environment product, or transport. It assumes: a human states intent; the system produces a plan of Capabilities; Capabilities execute with permission; outcomes are verified and remembered. **No section of this Constitution names a specific branded product as part of defining core behavior.** Where a concrete example is useful, it appears only in §21 (Illustrative Implementations), explicitly marked as non-binding.

### 14.2 Capabilities Define the Product
Filesystem capabilities → a file manager. Shell capabilities → a terminal agent. Browser capabilities → a web agent. All simultaneously → Kalpavriksha.

### 14.3 Adding a Product = Adding Capabilities
New product verticals require new Workers, never architecture changes.

---

## 15. Human Oversight Philosophy
**Status: FROZEN**

### 15.1 Approval Is Not Optional
Every capability above `READ_ONLY` requires a Permission System grant (Shared Infrastructure, §5.2). Declining → `Mission.CANCELLED`, nothing executed, nothing persisted as a side effect.

### 15.2 Approval UX Must Stay Simple
One clear decision point, regardless of how many Operator Instances (§8) or sub-steps a Mission touches.

### 15.3 One Approval Per Mission (canonical statement — see §2.7, §20 Rule 5, Rule 14 for cross-references only)
A human is never asked twice for the same thing they already approved, no matter how many primitive Steps, Workers, or Operator Instances that thing decomposes into underneath. This is achieved by relaying an already-obtained grant down through Shared Infrastructure's Permission System (§5.2, §20 Rule 6) — never by weakening what gets checked.

### 15.4 Transparency Over Trust
Every execution is logged. Every Mission is recorded. Evidence (§10) is available, not hidden. No Reasoning Provider call happens without a named Capability behind it.

### 15.5 Promotion Review is Human Oversight applied to Knowledge
See §9.4. Promoting Knowledge is treated as an important action under this same principle, not a separate mechanism.

---

## 16. Ownership Registry
**Status: FROZEN**

Every component named across MB001–005, `ARCHITECTURE.md`, and the prior audit appears here **exactly once**.

| Component | Home | Rationale |
|---|---|---|
| `MasterAgentSession` | **Brain-adjacent, transitional** ("Mission Session" role) | Today's stand-in for Intent Layer + Planner + Mission-initiation, plus a manual call into Memory. Not a fourth layer — as the real Intent Layer/Planner/Reporter become real (`ROADMAP.md` item 1), its responsibilities dissolve into the Brain (§3) and Shared Infrastructure (§5), not into a persisted architectural component. |
| `MissionManager` / `Mission` state machine | **Shared Infrastructure** (§5.3) | A Mission may span multiple Operator Instances (§8); its state cannot belong to any one of them. |
| `Reporter` | **Brain** (§3.4) | Deciding how to explain an outcome is a reasoning/communication judgment, not an execution fact. Not yet built — same honest status as the Verifier was before this revision. |
| `Orchestrator` | **Operator** (§4.1) | Unchanged — carries out what was decided. |
| `ModelRouter` | **Brain** (§3.3) | Decides which Reasoning Provider handles a call. Depends on Shared Infrastructure's Capability Registry (§5.1) — a legitimate downward dependency, not a boundary breach (§6). |
| `CapabilityIndex` / Plugin Registry | **Shared Infrastructure** (§5.1) | One shared answer to "what can be done and by what," queried by both sides. |
| `Memory` | **Shared Infrastructure** (§5.4) | Must aggregate across every Operator Instance, not fragment. |
| Worker Runtime | **Operator** (§12) | Implementation detail of how the Operator invokes Workers; not a distinct layer. |
| Plugin Runtime | **Operator** (§12) | Same as Worker Runtime — the two names refer to the same mechanism. |
| Verification Subsystem | **Operator-adjacent, own contract** (§10) | Needs Environment access (Operator-side) but is structurally distinct from Execution. |
| Permission System | **Shared Infrastructure** (§5.2) | Elevated this revision — see §5.2 for why. |
| Operator Registry | **Shared Infrastructure** (§8.2, part of §5.1) | Tracks live Operator Instances the same way the Capability Registry tracks Workers. |
| Environment Session Manager | **Operator (per-instance)** (§8.3) | Deliberately *not* shared — see §5.8. |
| AI Capability Broker | **Shared Infrastructure** (§5.7) | Added by Amendment 2 (MB027). Both the Brain's Model Router and any Worker needing intelligence consult it; its cost, approval, and benchmark ledgers must be singular across Operator Instances. Decides; never executes, never touches an Environment. |
| AI Infrastructure Executive | **Operator** (Worker, §12) | Added by Amendment 2 (MB027). The machine-touching counterpart to the Broker: discovers, probes, benchmarks, inventories, and — with explicit Founder approval — installs. Produces the inputs the Broker decides on; never decides itself. |

---

## 17. Terminology Freeze
**Status: FROZEN** — every term below has exactly one meaning in this Constitution and all documents it governs.

| Term | Definition |
|---|---|
| **Brain** | The cognitive layer: Intent Layer, Planner, Model Router, Reporter (§3). Decides; never executes. |
| **Operator** | The execution layer: Orchestrator, Verification Subsystem, Worker/Plugin Runtime, Environment Session Management (§4). Executes; never decides. |
| **Worker** | A single registered unit of execution capability inside an Operator's Worker Runtime (today: an Action/Plugin). Not a layer — a component of §12. |
| **Executive** | Synonym for **Worker**, introduced by MB023 as the term Mission Control's registration API uses (`ExecutiveRegistry`, `executive_id`). The same role, described from the coordination layer rather than the execution layer. `Worker` stays canonical here and in Worker-side code; neither term may be given a third synonym. See `docs/adr/0014-executive-and-worker-terminology.md`. |
| **AI Capability** | A *kind of intelligence* a Provider can supply — `reasoning`, `vision.ocr`, `speech.transcribe` (§5.7). Added by Amendment 2 (MB027). **Distinct from Capability, and never dispatchable on its own**: an AI Capability is an input to Provider selection; a Capability is a unit of execution. Written `lowercase.dotted`, where Capabilities are `PascalCase.PascalCase`, so the two are distinguishable mechanically rather than by convention. |
| **Provider** | Any registered source of AI capability — local runtime, desktop application, cloud API, aggregator (§5.7). Added by Amendment 2 (MB027). **Generalizes, and does not replace, Reasoning Provider**: a Reasoning Provider (§3.3) is a Provider offering the `reasoning` AI Capability. Neither term may be given a third synonym. |
| **Environment** | An abstract category of place execution happens (Desktop, Browser, Terminal, VPS, future Robotics/IoT). Never a specific product (§7.2, §21). |
| **Environment Instance** | One concrete, addressable, live target within an Environment category (§7.4, §8.3). |
| **Environment Session** | The live handle an Operator Instance holds to one Environment Instance (§8.3). Owned by exactly one Operator Instance; never Shared Infrastructure. |
| **Capability** | A named unit of "what can be done" that a `Step` references; resolved to a Worker (or an Operator Instance, §8.4) at execution time via the Capability Registry (§5.1). |
| **Action** | The concrete, atomic implementation of one Capability inside a Worker: validates parameters, then runs, producing an Execution Result. |
| **Observation** | A freshly captured fact about real-world state, gathered by the Verification Subsystem re-checking an Environment Instance (§10.2). Distinct from an Execution Result. |
| **Evidence** | An Observation, the Expected Outcome it was compared against, and the resulting Verdict, packaged as a durable record (§9.2, §10.2). |
| **Verification** | The act of comparing an Observation against an Expected Outcome to produce a Verdict (§10). Reserved exclusively for this Mission-level meaning — never used for the Knowledge Lifecycle's Promotion Review (§9.3). |
| **Knowledge** | Durable, *promoted* understanding the Brain actively consults during planning (§9). Distinct from a raw Mission Record, which is history until promoted. |
| **Mission** | One complete Intent-to-Outcome unit of work; owns a single Mission State instance (§5.3); may span multiple Steps, Capabilities, and Operator Instances (§8). |
| **Session** | Reserved for **Mission Session** — the Brain-side conversational context in which a human states Intent and the system carries one or more Missions to completion. Never used for an Environment-level connection — that is always the explicitly-qualified **Environment Session**. |
| **Task** | **Deprecated alias for Step.** Nothing in this Constitution or the codebase distinguishes "Task" from `Step` (a MissionPlan DAG node); rather than invent a false distinction, this Constitution retires "Task" in favor of `Step`. |
| **Step** | One DAG node of a `MissionPlan`, naming a Capability and an Expected Outcome (§3.2). |
| **Worker Instance** | One live, invocable registration of a Worker inside a specific Operator Instance (§12.4). |
| **Operator Instance** | One running instance of the Operator, bound to one (or a small tightly-coupled set of) Environment Instance(s), tracked by the Operator Registry (§8.2). |

---

## 18. Section Status Legend
**Status: FROZEN**

- **FROZEN** — Will not change without a new Constitution revision. Implementation may rely on this shape indefinitely.
- **RESEARCH-BACKED** — Reasoned through carefully (including this revision's audit-and-resolve process), but not yet implemented or proven at real scale. Implementation may proceed against it; expect refinement once real usage exists, the same way `MEMORY_ARCHITECTURE.md`'s design was refined by ADR-0008 after real usage revealed gaps.
- **EVOLVABLE** — Stable philosophy, deliberately open roster or mechanism (e.g., which Environments exist, how concurrency is scheduled). Expected to grow without requiring a Constitution revision, as long as growth stays inside the stated shape.
- **IMPLEMENTATION DETAIL** — Real and correct, but not architecture-constitution material; lives here for continuity, authoritative version may move to `ARCHITECTURE.md` as it evolves.

A section's status is a promise about *how it may change*, not a judgment of its importance — §11 (Recovery) is EVOLVABLE precisely because it is important enough to keep improving deliberately rather than freezing prematurely.

---

## 19. Long-term Founder Edition Vision
**Status: EVOLVABLE**

### 19.1 What "Founder Edition" Means
Built for one founder first; designed so scaling doesn't require rewriting.

### 19.2 Historical Context
Nine Miracles recorded in `MIRACLE_LEDGER.md` (001, 001.5, 002, 003, 003.1, 003.5, 004, 004.1, 005) delivered against the original runway. Each: design doc first, implementation, tests, live verification, documentation.

### 19.3 Post-Founder Edition Evolution
Real Planner (unblocked by this revision — see `FOUNDER_CONSTITUTION_FREEZE.md`), Mission Manager wired into Shared Infrastructure as designed in §5.3, Knowledge/Vector Memory per §9, Cloud Sync (opt-in, never default), Desktop UI, multi-Operator-Instance execution per §8, Reasoning-Provider diversity per §3.3.

---

## 20. Immutable Architecture Rules
**Status: FROZEN**

Every rule below exists in exactly one place in this Constitution. Other sections cross-reference by rule number; they do not restate rule content (§7 of `docs/MISSION_BRIEF_021_REVISION_3.md` lists what was consolidated and from where).

**Rule 1 — Design Before Code, Answering the Scalability Question.** Every Miracle begins with a design document written before implementation, and that document must explicitly answer: "would this still be right at a million Missions, thousands of Workers, hundreds of Capabilities, years of history, many Operator Instances?" (`FILESYSTEM_CAPABILITIES.md` §8 is the template.) This subsumes what the prior revision split into two rules (former Rule 1 and Rule 9) — one rule, one place.

**Rule 2 — No Rewrites Without Approval.** Never refactor architecture without being asked. Reuse existing scaffolding.

**Rule 3 — Capability Contract Is Sacred.** Every capability is a Worker behind the Capability Registry. Adding capability #N costs one new file, never an edit to the Registry, Orchestrator, Permission System, or Worker Runtime.

**Rule 4 — Environment Access Has One Door.** No Brain module, no CLI code, touches an Environment directly. Everything goes through a Worker, via the Operator's Worker Runtime, via an Environment Session (§8.3) the Operator Instance owns.

**Rule 5 — Permission System Has Veto Power, Now Mission-Wide.** Every capability declares a risk tier. The Permission System (Shared Infrastructure, §5.2) is consulted before any step above `READ_ONLY`, regardless of which Operator Instance executes it. An `ALWAYS_FOR_CAPABILITY` grant never satisfies an `IRREVERSIBLE` check.

**Rule 6 — Composites and Nested Calls Relay, Never Bypass.** A Worker that orchestrates other Workers does so only through the Capability Registry and Permission System, relaying its own already-obtained grant down to each sub-step. No transactional rollback on partial failure — completed steps stay completed, and the result reports exactly what completed before failure. (This is the single canonical statement of this rule — §4.5-equivalent content in §12.3 and the former §10.3/§13 references now point here instead of restating it.)

**Rule 7 — Memory Persists Automatically.** Persistence happens at every terminal Mission state, with no manual save call anywhere in the calling code.

**Rule 8 — Evidence Hierarchy Is Law.** When documentation and observed reality conflict, observed reality wins — for Mission history (unchanged) and now explicitly for Permanent Knowledge too (§9.2, §9.4).

**Rule 9 — [merged into Rule 1].**

**Rule 10 — Technical Debt Is Named Honestly.** Every deliverable includes a Technical Debt / Known Limitations section. This Constitution applies this rule to itself: §11.4 names the one gap this revision did not close.

**Rule 11 — Test the Complete Flow.** (Implementation-phase rule — restated here for completeness; governs Mission Briefs that write code, not this design-only one.)

**Rule 12 — Ruff Clean, Pytest Green.** (Implementation-phase rule, as above.)

**Rule 13 — Git History Is Canonical.** One commit per Miracle; never force-push, squash, or rewrite history.

**Rule 14 — [merged into Rule 5 / §15.3].**

**Rule 15 — The Founder Playbook Is Process.** `FOUNDER_PLAYBOOK.md` codifies how Miracles are built. Deviations require explicit founder approval.

---

## 21. Illustrative Implementations
**Status: IMPLEMENTATION DETAIL** — non-binding examples only. Nothing in §1–§20 depends on any row below; this table exists so a reader can picture a concrete instantiation without the architecture depending on one.

| Architectural Role | Illustrative example (not binding) |
|---|---|
| Local Reasoning Provider | e.g. a locally-run, open-weight model served by a local inference runtime |
| Cloud Reasoning Provider | e.g. a hosted commercial reasoning API |
| Desktop Environment | e.g. the host operating system's filesystem, shell, and installed applications |
| Browser Environment | e.g. a web browser instance and its tabs |
| Terminal Environment | e.g. a shell process |
| VPS Environment | e.g. a remote virtual machine reachable over SSH |
| IDE integration Capability | e.g. a code editor's project/file operations |
| Note-taking integration Capability | e.g. a local notes application's vault |

Implementation Mission Briefs may choose specific products for any row above. This Constitution's architecture sections must never be edited to name one.

---

## 22. Appendix: Source Document Traceability

| Document | Role |
|---|---|
| `MISSION_BRIEF_001.md`–`MISSION_BRIEF_005.md` | Implementation records with honest accounting |
| `docs/MISSION_BRIEF_021_REVISION_3.md` | This revision's own record: what changed, why, and what remains open |
| `FOUNDER_CONSTITUTION_FREEZE.md` | Freeze declaration, section-status registry, Final Founder Review |
| `ARCHITECTURE.md` | Current-implementation module map and data flow — read through this Constitution's terminology |
| `MEMORY_ARCHITECTURE.md` | Six-layer memory design (Shared Infrastructure §5.4, Knowledge Lifecycle §9) |
| `FILESYSTEM_CAPABILITIES.md` | Capability design template; source of the Scalability Question (Rule 1) |
| `PROJECT_BRAIN.md` | Current-state index |
| `MIRACLE_LEDGER.md` | Chronological shipment record |
| `docs/adr/0005`–`0006` | Permission relay pattern (Rule 6) |
| `docs/adr/0007`–`0008` | Memory backend and scale review |
| `docs/adr/0009` | PermissionCategory + IRREVERSIBLE grant rule |
| `docs/adr/0010` | Shared Infrastructure layer (this revision) |
| `docs/adr/0011` | Verification as an independent subsystem (this revision) |
| `docs/adr/0012` | Knowledge Lifecycle (this revision) |
| `docs/adr/0013` | Multi-Operator / Environment Instance architecture (this revision) |
| `ROADMAP.md` | Prioritized future work |
| `FOUNDER_PLAYBOOK.md` | Miracle build/review/test/ship process |
| `ENGINEERING_PRINCIPLES.md` / `PRODUCT_PRINCIPLES.md` / `ARCHITECTURE_PRINCIPLES.md` | Value-to-practice mappings |
| `DECISIONS.md` | Quick-reference index to every ADR above |

**Note on MB006–MB020:** confirmed absent from this repository, its git history, and all known backups as of the independent audit preceding this revision. This Constitution does not depend on their content — every claim above traces to a document that verifiably exists.

---

**End of Kalpavriksha Architecture Constitution v2, Revision 3.**

*Frozen per `FOUNDER_CONSTITUTION_FREEZE.md`. Amend only through a new Mission Brief that updates both this document and that freeze record together — never one without the other.*
