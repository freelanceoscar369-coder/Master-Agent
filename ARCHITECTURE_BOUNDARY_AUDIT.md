# Architecture Boundary Audit

## Source
- `docs/architecture/KALPAVRIKSHA_VISION_V2.md` §3–§6, §16
- `docs/architecture/FOUNDER_CONSTITUTION_FREEZE.md` §4 (Section Status Registry)
- All 26 KB documents

## Classification Legend
- **A** = Implementation Bug
- **B** = Missing Implementation Required by Frozen Architecture
- **C** = Intentional Founder Edition Limitation
- **D** = Future Evolution / Scalability Item
- **E** = Requires ADR Decision
- **F** = Documentation Gap

---

## 1. Executive Brain (§3, FROZEN)

### Constitutional Definition
> The **Executive Brain** is the cognitive layer. It decides *what* to do, *how* to structure it, and *how to explain it back*. It owns Intent, Planning, Reasoning-Provider selection, and Reporting. It **never executes, never touches an Environment, and never holds a Permission grant.**

### Boundary Audit

| Component | Constitutional Role | Implementation | Boundary Status |
|-----------|---------------------|----------------|-----------------|
| **Intent Layer** | Turns raw input → structured `Intent`. Owns clarification. | ❌ **STUB** — `cli.py` regex `parse_intent()` only (KB#01) | **B** — Missing Implementation |
| **Planner** | `Intent` → `MissionPlan` (DAG of Steps + ExpectedOutcomes). Calls Reasoning Provider via Model Router. | ✅ **IMPLEMENTED** (MB036/037) — 7 modules in `planner/` (KB#01) | ✅ COMPLIANT |
| **Model Router** | Single `generate()` interface. Picks Provider via AI Capability Broker. | ✅ **IMPLEMENTED** (MB032) — `model_router.py` asks Broker (KB#14) | ✅ COMPLIANT |
| **Reporter** | Composes human-facing report from Evidence + Verdict. Never touches Environment. | ❌ **NOT BUILT** — `cli.py` completion messages only (KB#01) | **B** — Missing Implementation |

### Brain Non-Responsibilities (§3.5) — Audit

| Prohibited | Evidence |
|------------|----------|
| Does not execute capabilities | ✅ No execution imports in `planner/`, `model_router.py` |
| Does not hold/check Permission grants | ✅ No `PermissionSystem` imports in Brain modules |
| Does not own Mission State | ✅ Mission State in Shared Infrastructure (KB#04) |
| Does not persist Memory | ✅ Reads Memory, nominates Knowledge Candidates only |
| Does not verify outcomes | ✅ Consumes Evidence, Verification in Operator |
| Does not know Environment Instance | ✅ Only knows Capability names |

### Boundary Violations Found
| Violation | Location | Classification |
|-----------|----------|----------------|
| `cli.py` regex `parse_intent()` executes filesystem ops indirectly via Orchestrator path | `cli.py` | **C** — Intentional Founder Edition Limitation (stand-in) |
| Model Router had hardcoded provider names (pre-MB032) | `model_router.py` (historical) | **A** — Fixed by MB032 |

---

## 2. Shared Infrastructure (§5, FROZEN)

### Constitutional Definition
> Both Brain and Operator depend downward on Shared Infrastructure; Shared Infrastructure depends on neither. Multiple Brain/Operator components may read/write concurrently.

### Components Audit

| Component | Constitutional Home | Implementation | Boundary Status |
|-----------|---------------------|----------------|-----------------|
| **Capability Registry** | Shared Infra (§5.1) | ✅ `PluginRegistry` — execution-time lookup | ✅ COMPLIANT |
| **Permission System** | Shared Infra (§5.2) | ✅ `PermissionSystem` — single grant ledger | ✅ COMPLIANT |
| **Mission State** | Shared Infra (§5.3) | ⚠️ `MissionManager` unwired (KB#04 §11) | **B** — Partial |
| **Memory** | Shared Infra (§5.4) | ✅ Layers 1-3 implemented; L4 implemented (MB034); L5-6 interfaces | ✅ COMPLIANT |
| **Configuration** | Shared Infra (§5.5) | ⚠️ Scattered injection, no central config module | **F** — Documentation Gap |
| **Telemetry/Audit** | Shared Infra (§5.6) | ⚠️ Aggregated in Memory; raw logs local | ⚠️ PARTIAL |
| **AI Capability Broker** | Shared Infra (§5.7, Amendment 2) | ❌ **NOT IMPLEMENTED** — Architecture only (MB027) | **B** — Missing |
| **What NOT Shared** | | | |
| Environment Session Manager | Operator (per-instance) | ✅ `BrowserSessionManager` per Operator Instance | ✅ COMPLIANT |
| Mission Session (`MasterAgentSession`) | Brain-adjacent, transitional | ✅ Documented as transitional (KB#02) | ✅ COMPLIANT |
| Machine scanning/probing | AI Infrastructure Executive | ❌ Executive not implemented | **B** — Missing |

### Cross-Layer Dependencies — Audit

| Dependency | Direction | Constitutional? | Evidence |
|------------|-----------|-----------------|----------|
| Model Router → Capability Registry | Brain → Shared Infra | ✅ Yes (downward) | `ModelRouter` injects `PluginRegistry` |
| Orchestrator → Capability Registry | Operator → Shared Infra | ✅ Yes (downward) | `Orchestrator` injects `PluginRegistry` |
| Orchestrator → Permission System | Operator → Shared Infra | ✅ Yes (downward) | `Orchestrator` injects `PermissionSystem` |
| Runtime → Mission Control | Runtime → Coordination | ✅ Yes (Runtime uses MC) | `RuntimeEngine` injects `MissionControl` |
| Runtime → Plugin Registry | Runtime → Shared Infra | ✅ Via Mission Control | `Runtime` gets gateways from MC |
| **Brain → Operator** | **Brain → Operator** | **❌ NO** | **None found** |
| **Operator → Brain** | **Operator → Brain** | **❌ NO** | **None found** |

---

## 3. Universal Executive Operator (§4, FROZEN)

### Constitutional Definition
> The **Universal Executive Operator** carries out what the Brain decided, with full accountability. It **never decides, never plans, and never holds an opinion about *why* a Step exists — only *how* to run it safely and *whether it actually worked*.**

### Components Audit

| Component | Constitutional Role | Implementation | Boundary Status |
|-----------|---------------------|----------------|-----------------|
| **Orchestrator** | Walks MissionPlan, resolves Capability→Worker, checks Permission, invokes Worker, triggers Verification, applies retry policy | ✅ `Orchestrator` class (KB#17) | ⚠️ **PARTIAL** — Verification triggered by Runtime, not Orchestrator |
| **Worker Runtime** | Operator-owned implementation detail (not distinct layer) | ✅ `Plugin` ABC, `PluginRegistry` (KB#13) | ✅ COMPLIANT |
| **Verification Subsystem** | Runs alongside Operator, own contract, never through Worker's `invoke()` | ✅ `Verifier` ABC + `TextVerifier` + `BrowserVerifier` (KB#11, KB#20) | ✅ COMPLIANT |

### Operator Non-Responsibilities (§4.4) — Audit

| Prohibited | Evidence |
|------------|----------|
| Does not decide Mission accomplishment | ✅ Planner produces MissionPlan |
| Does not maintain private Permission/Mission State/Memory | ✅ All in Shared Infrastructure |
| Does not nominate/promote Knowledge | ✅ Produces Evidence only |

### Boundary Violations Found

| Violation | Location | Classification |
|-----------|----------|----------------|
| Orchestrator does NOT trigger Verification (Constitution §4.1 says it does) | `orchestrator.py` | **A** — Implementation Bug (Runtime does it instead) |
| Two approval gates exist (Orchestrator + Runtime ApprovalGate) | `orchestrator.py`, `runtime/approval.py` | **D** — Future Evolution (relay pattern connects them) |
| Execution order owned by Mission Control Dispatcher, not Orchestrator | `dispatcher.py` | **D** — Future Evolution (MB037 clarified) |

---

## 4. Mission Control (§16, FROZEN — Coordination Layer)

### Constitutional Definition
> **Mission Control never performs work.** Holds no Environment access, no model calls. Decides *what should happen next and in what order*, records *what actually happened*.

### Components Audit

| Component | Implementation | Boundary Status |
|-----------|----------------|-----------------|
| Universal Event Bus | ✅ `EventBus` — single `Event` schema (KB#07) | ✅ COMPLIANT |
| Executive Registry | ✅ Tracks live Executives (health, current task) | ✅ COMPLIANT |
| Capability Registry (MC) | ✅ Coordination catalogue (descriptors, not live objects) | ✅ COMPLIANT |
| Task Dispatcher | ✅ Dependency-ordered, `BLOCKED` on failed dep, no auto-retry | ✅ COMPLIANT |
| Self-Development Queue | ✅ 5 categories, state machine | ✅ COMPLIANT |
| Knowledge Acquisition Queue | ✅ 7-stage pipeline, promotion gate `human_approved=True` | ✅ COMPLIANT |
| Founder State | ✅ `founder_state()` — 10-field snapshot, honest ETA | ✅ COMPLIANT |
| Audit Stream | ✅ Append-only `AuditEntry`, distinct from Worker audit | ✅ COMPLIANT |

### Boundary Violations Found

| Violation | Location | Classification |
|-----------|----------|----------------|
| Mission Control emits `OBJECTIVE_SUBMITTED` + `TASK_CREATED` on `submit()` — prevents clean restore (ADR-0015) | `dispatcher.py` | **E** — Requires ADR Decision (ADR-0015 Proposed) |
| `_current_objective_id` never advances past first objective | `mission_control.py` | **A** — Implementation Bug |
| `count_events()` not implemented (MB026 posture) | `mission_control.py` | **C** — Intentional Limitation |

---

## 4. Runtime Engine (§11, FROZEN — Heartbeat)

### Constitutional Definition
> The loop that replaces the founder: observe → dispatch → execute → verify → report → idle → repeat.

### Components Audit

| Component | Implementation | Boundary Status |
|-----------|----------------|-----------------|
| 8-State Machine | ✅ `RuntimeState` enum + `assert_transition` (KB#06) | ✅ COMPLIANT |
| ExecutiveGateway Protocol | ✅ `invoke()` + `verify()` (KB#06) | ✅ COMPLIANT |
| PluginGateway | ✅ Generic over any `Plugin` (KB#06) | ✅ COMPLIANT |
| ApprovalGate | ✅ Protocol in `runtime/`, fail-closed (KB#06, KB#12) | ✅ COMPLIANT |
| Mechanical Retry Only | ✅ Same task, bounded attempts, fixed delay (KB#06) | ✅ COMPLIANT |
| CheckpointSink Protocol | ✅ In `runtime/`, no persistence dep (KB#06, KB#08) | ✅ COMPLIANT |

### Boundary Violations Found

| Violation | Location | Classification |
|-----------|----------|----------------|
| Thread-affine Environment Sessions (Browser) — constraint not enforced | `runtime/engine.py` | **D** — Future Evolution (documented constraint) |
| Two approval gates (Orchestrator + Runtime) | `orchestrator.py`, `approval.py` | **D** — Future Evolution |

---

## 5. Verification Subsystem (§10, RESEARCH-BACKED)

### Constitutional Definition
> **Structurally independent from Execution.** Three-part boundary:
> 1. Execution produces effects
> 2. Verification produces Evidence (re-observes, compares against Expected Outcome)
> 3. Evidence flows back to Brain

### Implementation Audit

| Component | Implementation | Boundary Status |
|-----------|----------------|-----------------|
| `Verifier` ABC | ✅ `verification/verifier.py` — `capture_observation_dict()` abstract | ✅ COMPLIANT |
| `evaluate_checks()` | ✅ `verification/evaluator.py` — pure, 5 operators | ✅ COMPLIANT |
| Evidence Model | ✅ `verification/evidence.py` — `Evidence`, `ExpectedOutcome`, `Verdict` | ✅ COMPLIANT |
| `BrowserVerifier` | ✅ `plugins/browser_verifier.py` — ~10 lines | ✅ COMPLIANT |
| `TextVerifier` | ✅ `ai_infrastructure/text_verifier.py` — deterministic measurement | ✅ COMPLIANT |
| Runtime Integration | ✅ `RuntimeEngine._verify()` calls `gateway.verify()` | ✅ COMPLIANT |

### Boundary Violations Found

| Violation | Location | Classification |
|-----------|----------|----------------|
| **Filesystem Verifier Missing** — Constitution §10 mandatory for all capabilities | `verification/` | **B** — Missing Implementation Required |
| Execution success ≠ Verification success (correct) | `runtime/engine.py` | ✅ COMPLIANT (Runtime treats `NOT_MATCHED` as failure) |
| Filesystem capabilities have no Verifier | `executor/actions/` | **B** — Missing Implementation |

---

## 6. Plugin System (§12, IMPLEMENTATION DETAIL)

### Constitutional Definition
> Workers are Capabilities' implementations. Every Capability = Worker registered on Operator's Worker Runtime. Adding #N = one new file.

### Implementation Audit

| Plugin | Implementation | Boundary Status |
|--------|----------------|-----------------|
| `Plugin` ABC | ✅ `plugins/base.py` — `manifest`, `invoke()` | ✅ COMPLIANT |
| `ModelProvider` | ✅ Specialization with `generate()` | ✅ COMPLIANT |
| `PluginRegistry` | ✅ Capability index, risk tier lookup | ✅ COMPLIANT |
| `FilesystemPlugin` | ✅ 14 capabilities, declarative registration | ✅ COMPLIANT |
| `BrowserPlugin` | ✅ 9 capabilities, identical pattern | ✅ COMPLIANT |

### Boundary Violations Found

| Violation | Location | Classification |
|-----------|----------|----------------|
| `CapabilityManifest.input_schema`/`output_schema` declared but empty | `plugins/base.py` | **B** — Missing Implementation |
| Two integration surfaces for Browser (`BrowserPlugin` + `BrowserWorker`) | `plugins/` | **D** — Future Evolution |
| No capability selection policy for multiple providers | `registry.py` | **C** — Intentional Limitation (Founder Edition) |

---

## Summary: Boundary Audit Findings

| Layer | Critical Violations | Partial | Compliant |
|-------|---------------------|---------|-----------|
| **Brain** | 0 | 2 (Intent Layer, Reporter missing) | 4/6 |
| **Shared Infrastructure** | 1 (Broker missing) | 2 (Config, Telemetry) | 5/8 |
| **Operator** | 1 (Orchestrator→Verification) | 2 (Execution order, Retry) | 3/6 |
| **Mission Control** | 1 (`_current_objective_id`) | 1 (ADR-0015) | 7/9 |
| **Runtime** | 0 | 1 (Thread affinity) | 6/7 |
| **Verification** | 1 (Filesystem Verifier missing) | 0 | 5/6 |
| **Plugin System** | 1 (input_schema empty) | 1 (Two surfaces) | 5/7 |

---

## Classification Summary

| Classification | Count | Details |
|----------------|-------|---------|
| **A** — Implementation Bug | 3 | `_current_objective_id`, Orchestrator→Verification, `_current_objective_id` (duplicate) |
| **B** — Missing Implementation Required | 6 | Broker, Filesystem Verifier, Reporter, Intent Layer, MissionManager, input_schema |
| **C** — Intentional Limitation | 3 | Capability selection, count_events, MasterAgentSession stand-in |
| **D** — Future Evolution | 5 | Two approval gates, execution order, two surfaces, thread affinity, selection policy |
| **E** — Requires ADR | 1 | ADR-0015 (restore_objective) |
| **F** — Documentation Gap | 1 | Configuration centralization |

---

*Generated from verified KB documents and Constitution only. No fixes implemented. Classifications based on frozen Constitution only.*