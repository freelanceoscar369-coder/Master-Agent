# Shared Infrastructure

## Purpose
Documents the foundational layer both Brain and Operator depend on: Capability Registry, Permission System, Mission State, Memory, Configuration, Telemetry/Audit, AI Capability Broker — per `KALPAVRIKSHA_VISION_V2.md` §5 (FROZEN).

## Constitutional Definition (§5, FROZEN)

### Role in Three-Layer Architecture
```
Executive Brain (decides what, how to structure, how to explain)
        │
Shared Infrastructure (one consistent source of truth both sides depend on)
        │
Universal Executive Operator (carries out what was decided, with accountability)
```

**Dependency direction only** — not sequential data flow. Both Brain and Operator depend downward on Shared Infrastructure; Shared Infrastructure depends on neither. Multiple Brain-side components and multiple Operator Instances (§8) may read and write Shared Infrastructure concurrently — it is not a pipe one message flows through once.

### Why This Layer Exists (Constitution §5)
The prior revision claimed "the boundary is absolute" between Brain and Operator while assigning Plugin Registry and Memory exclusively to the Operator's column. Verified against source (`plugins/registry.py`, `plugins/model_router.py`), the Model Router — a Brain component — constructs directly against the Plugin Registry, and the registry's docstring states it is "the only thing the Orchestrator **and** Model Router talk to." A two-column model cannot represent a component both columns genuinely depend on without either duplicating it (causing drift) or misassigning it (causing contradiction). A third, foundational layer resolves this: Brain and Operator are still forbidden from depending on each other's internals; both are permitted — required — to depend on Shared Infrastructure's public contracts.

---

## Infrastructure Components

Extract only supported components from Constitution §5.

### 5.1 Capability Registry (formerly "Plugin Registry")
**Status:** FROZEN  
**Purpose:** Single registry queried by Brain's Model Router (Reasoning Provider resolution) and Operator's Orchestrator (execution capability resolution) — same lookup mechanism, two different callers. One registry, one answer, regardless of who asks.

**Ownership:** Shared Infrastructure (single component, two indices: plugin identity, capability → plugin)

**Dependencies:** None (foundational)

**Current Implementation Status:** **IMPLEMENTED** — `src/master_agent/plugins/registry.py`
- `PluginRegistry.register(plugin)` — populates from Plugin manifests
- `find_for_capability(capability)` — returns candidate plugins
- `risk_tier_for(plugin_name, capability)` — used by Orchestrator
- Mission Control maintains separate **coordination catalogue** (descriptors: names, versions, owners, health) — populated by adapter reading Plugin manifests (`MISSION_CONTROL_ARCHITECTURE.md` §4)

**Constitution Note:** Future capability-resolution policy (choosing between multiple Workers for same Capability) is EVOLVABLE — evolution of lookup logic, not new component.

### 5.2 Permission System
**Status:** FROZEN  
**Purpose:** Single, consistent grant ledger across every Operator Instance a Mission might touch. Makes "one approval per mission" (§15.3) a Mission-wide guarantee.

**Ownership:** Shared Infrastructure (elevated this revision — prior revision assigned to Operator)

**Dependencies:** None (foundational)

**Current Implementation Status:** **IMPLEMENTED** — `src/master_agent/permissions/permission_system.py`

**Risk Tiers (gating mechanism):**
- `READ_ONLY` — short-circuits unconditionally, never prompts
- `REVERSIBLE_WRITE` — grants: `ONCE`, `THIS_SESSION`, `ALWAYS_FOR_CAPABILITY`
- `IRREVERSIBLE` — **`ALWAYS_FOR_CAPABILITY` never satisfies** (ADR-0009)

**Permission Categories (descriptive, orthogonal):**
- `READ`, `WRITE`, `MODIFY`, `DELETE`, `SYSTEM`

**Relay Pattern (ADR-0005, ADR-0006):** Outer approval explicitly carried down to inner grant key. Plugin adapter relays already-obtained approval to Executor's key without asking human twice.

**Runtime ApprovalGate (MB028.0, ADR-0019):** Protocol defined inside `runtime/approval.py` — Runtime consults before any gateway invocation. Fail-closed: no gate ⇒ nothing runs.

### 5.3 Mission State
**Status:** FROZEN  
**Purpose:** Owns `Mission` state machine because a single Mission's Steps may be serviced by different Operator Instances (§8). Correct permanent home for `MissionManager` and `Mission` state machine.

**Ownership:** Shared Infrastructure

**Dependencies:** Memory (persistence), Permission System (approval status)

**Current Implementation Status:** **PARTIAL**
- `Mission` state machine: `draft → planned → awaiting_approval → executing → verifying → completed | failed | cancelled` — **IMPLEMENTED** (`src/master_agent/mission_manager/mission.py`)
- `MissionManager` — **NOT WIRED INTO LIVE PATH** (`MEMORY_ARCHITECTURE.md` §11). `cli.py`'s `MasterAgentSession` is the only working conversational path; `MissionManager` imports `MemoryStore` but is unused.

**State Machine Transitions:** Owned by Shared Infrastructure; Operator transitions through Shared Infrastructure's contract, never private copy.

### 5.4 Memory (Six Layers)
**Status:** FROZEN (Layers 1-3), RESEARCH-BACKED (Layer 4), Future (Layers 5-6)  
**Purpose:** Every Operator Instance's Evidence must aggregate into one durable history, not fragment into per-Operator silos.

**Ownership:** Shared Infrastructure (all six layers)

**Dependencies:** Configuration (paths), Permission System (approval_status)

**Current Implementation Status:**

| Layer | Name | Scope | Status |
|-------|------|-------|--------|
| 1 | Conversation Memory | Current session | **IMPLEMENTED** (`memory/conversation.py`) |
| 2 | Mission Memory | Current execution | **IMPLEMENTED** (pre-existing `Mission` + `MasterAgentSession.last_mission`) |
| 3 | Persistent Memory | Durable, this machine | **IMPLEMENTED** (`SQLiteMemoryStore` in `memory/store.py`) |
| 4 | Knowledge Memory | Durable facts/documents | **RESERVED** — interface only (`KnowledgeMemory` in `memory/future.py`) |
| 5 | Vector Memory | Semantic recall | **FUTURE** — interface only (`VectorMemory`) |
| 6 | Cloud Sync | Multi-device | **OPTIONAL FUTURE** — interface only (`CloudSyncMemory`) |

**Schema (Layer 3 — SQLite):**
```sql
missions: mission_id (PK), title, intent_summary, status, approval_status,
          created_at, completed_at, execution_plan (JSON), execution_result (JSON),
          execution_time_seconds, artifacts (JSON), errors (JSON), outcome (JSON)
preferences: key (PK), value (JSON)
```
Indexes: `completed_at`, `(status, completed_at)`

**API Contract:**
- `MemoryStore` ABC — `save_mission`, `get_mission`, `query_missions(MissionQuery)`, `remember_preference`, `recall_preference`
- `Memory` facade — single seam: `record_turn`, `conversation_turns`, `persist_mission`, `mission_by_id`, `last_mission`, `recent_missions`, `successful_missions`, `failed_missions`, `remember_preference`, `recall_preference`

**Auto-Persistence (Rule 7):** `MasterAgentSession._remember()` called at every terminal state (`_finish()`, `_handle_approval_response()` "no" branch). No manual save calls from CLI.

**Query Support:** 5 literal queries (`last_mission`, `mission_by_id`, `recent_missions`, `successful_missions`, `failed_missions`)

### 5.5 Configuration
**Status:** FROZEN  
**Purpose:** Environment roots, Reasoning Provider defaults, policy configuration — single source to prevent drift between Brain/Operator readers.

**Ownership:** Shared Infrastructure

**Dependencies:** None (foundational)

**Current Implementation Status:** **PARTIAL** — Configuration injected via constructor parameters (e.g., `default_locations()` in `executor/action.py`, `RuntimeConfig` in `runtime/config.py`, `OllamaConfig` in `providers/`). No centralized configuration module documented in sources.

**Constitution Requirement:** Configuration drift between two readers of "what's the allowed filesystem root" is a safety bug, not a style question.

### 5.6 Telemetry and Audit (Aggregated Form)
**Status:** FROZEN  
**Purpose:** Durable, queryable, cross-Operator-Instance aggregation of telemetry. Evidence *is* the audited, verified subset of telemetry that made it into Memory.

**Ownership:** Shared Infrastructure (aggregated form only)

**Dependencies:** Memory (aggregation mechanism), Verification Subsystem (Evidence production)

**Current Implementation Status:** **PARTIAL**
- Raw log emission: Local at Operator Instance/Worker Instance (e.g., `LocalExecutor._log` — unbounded in-memory list, `MEMORY_ARCHITECTURE.md` §11)
- Aggregated form: Mission Record in Memory (`missions` table) — **IMPLEMENTED**
- Audit Stream: Mission Control subscribes to Event Bus, records every event as immutable `AuditEntry` — **IMPLEMENTED** (`MISSION_CONTROL_ARCHITECTURE.md` §11)
- Per-Worker audit: `verification/audit.py` — **IMPLEMENTED** (distinct from system-wide Audit Stream)

**Split Responsibility (on purpose):** Raw emission happens locally; Shared Infrastructure owns cross-Instance aggregation.

### 5.7 AI Capability Broker
**Status:** RESEARCH-BACKED (Amendment 2, MB027)  
**Purpose:** Single intelligence-selection service. Every component needing AI asks the Broker *which* Provider. **No other component may decide.**

**Ownership:** Shared Infrastructure (Kernel Service — not an Executive)

**Dependencies:** Permission System (requires permission), Capability Registry (execution_binding), Provider Registry (input)

**Current Implementation Status:** **NOT IMPLEMENTED** — Architecture only (MB027). `src/master_agent/broker/` does not exist.

**Broker Owns Exclusively (9 components):**
1. Provider Registry — what intelligence exists
2. Capability Matrix — what each Provider can do (declared + observed)
3. Decision Engine — which Provider serves a given request
4. AI Asset Inventory — machine's AI ecosystem as last observed
5. Recommendation Engine — what would improve the ecosystem
6. Cost Model — spend tracking
7. Benchmark Store — observed performance per (provider, ai_capability, task_class)
8. Approval Policy — what founder must sign off
9. Audit trail of every decision

**Eight Prohibitions (mechanically testable):**
1. Never executes (no Environment access, no network, no provider SDK imports)
2. Never decides *what* to do (Brain's job)
3. Never discovers (scanning = Environment access → AI Infrastructure Executive)
4. Never grants permission (requires permission through §5.2)
5. Never spends (estimates/records only)
6. Never retries (Runtime = mechanical, Brain = strategic)
7. Never names a product in its own logic (product names only in registry data)
8. Never installs/downloads/removes (recommendations are inert data)

**Input:** `CapabilityRequest(ai_capability: lowercase.dotted, task_class, requester, constraints[privacy, connectivity, max_latency_ms, min_quality, licensing_use, exclude_providers, max_cost], hints[prefer_provider, prefer_speed_over_quality, expected_output_tokens])`

**Output:** `BrokerDecision(outcome: SELECTED | APPROVAL_REQUIRED | NO_CAPABLE_PROVIDER, selection[execution_capability: PascalCase.PascalCase, execution_parameters], alternatives[], rejected[(provider_id, filter_reason)], cost_estimate, approval, inventory_age_seconds, policy_version, inputs_digest)`

**Verification Loop:** Caller executes → Verification produces Evidence → `Broker.record_outcome(decision_id, OutcomeReport)` → `BenchmarkSample` aggregates by (provider, ai_capability, task_class) → feeds next decision. **Outcome successful when Verification says so, not when provider call returned.**

**Machine-Touching Counterpart:** AI Infrastructure Executive (Worker, §12, §16) — discovers, probes, benchmarks, inventories, installs (with Founder approval). Produces inputs Broker decides on; never decides itself.

### 5.8 What Is Deliberately NOT Shared Infrastructure
- **Environment Session Management** — live handle belongs to Operator Instance that opened it (safety/isolation)
- **Mission Session** (`MasterAgentSession`) — Brain-adjacent glue, transitional
- **Machine scanning, provider probing, benchmarking, inventory, installation** — Environment access → AI Infrastructure Executive

---

## Component Responsibilities Summary

| Component | Purpose | Ownership | Depends On | Implementation |
|-----------|---------|-----------|------------|----------------|
| Capability Registry | Single lookup: capability → Worker/Provider | Shared Infrastructure | None | ✅ `plugins/registry.py` |
| Permission System | Single grant ledger, veto power | Shared Infrastructure | None | ✅ `permissions/` |
| Mission State | Mission state machine ownership | Shared Infrastructure | Memory, Permissions | ⚠️ `MissionManager` unwired |
| Memory (6 layers) | Durable history aggregation | Shared Infrastructure | Config, Permissions | ✅ L1-3; ⏳ L4-6 |
| Configuration | Single source for roots/defaults/policy | Shared Infrastructure | None | ⚠️ Scattered injection |
| Telemetry/Audit (aggregated) | Cross-Instance telemetry aggregation | Shared Infrastructure | Memory, Verification | ⚠️ Partial |
| AI Capability Broker | Intelligence selection kernel service | Shared Infrastructure (Kernel) | Permissions, Registry | ❌ Architecture only |
| Persistence | Event log + snapshot recovery | Shared Infrastructure (separate pkg) | Mission Control, Runtime | ✅ `persistence/` |

---

## Data and State Flow

### Constitution Data Flow (Dependency Direction)
```
Brain (reads/writes)     Operator (reads/writes)
       │                        │
       ▼                        ▼
Shared Infrastructure (Capability Registry, Permission System, Mission State, Memory, Config, Telemetry, Broker)
```

### Key Flows
1. **Model Router → Capability Registry** — resolves Reasoning Provider
2. **Orchestrator → Capability Registry** — resolves execution capability
3. **Orchestrator/Runtime → Permission System** — checks grants before invoke
4. **Runtime/Mission Control → Mission State** — transitions through Shared Infrastructure contract
5. **Operator → Memory** — writes Evidence via Shared Infrastructure contract
6. **Brain → Memory** — reads history, nominates Knowledge Candidates
7. **Brain/Operator → AI Capability Broker** — asks which Provider (before dispatch)
8. **AI Infrastructure Executive → Broker** — feeds inventory, benchmarks, outcomes

### Persistence Flow
```
Event Bus (Mission Control) → Persistence (events.jsonl append-only)
Runtime (cycle end/shutdown) → CheckpointSink → Persistence (snapshot.json)
Startup → recover() → restores Mission Control + Runtime counters
Interrupted tasks → quarantined as FAILED, dependents BLOCKED
```

---

## Persistence and Recovery

### Memory Persistence (Layer 3)
- **Mechanism:** `SQLiteMemoryStore` → `~/.master_agent/memory.db`
- **Trigger:** Automatic at every terminal Mission state (Rule 7)
- **Schema:** `missions` + `preferences` tables with JSON columns
- **No transactional guarantees** beyond SQLite's own (`MEMORY_ARCHITECTURE.md` §11)

### Operational Persistence (MB025)
- **Two mechanisms:** append-only event log (`events.jsonl`) + versioned checksummed snapshot (`snapshot.json`)
- **Snapshot:** O(live state) restart, written on checkpoint
- **Event log:** written as events happen, audit history + replay
- **Recovery:** `recovery.recover()` — single call launcher makes
- **Four boundaries (test-enforced):**
  1. Persistence never executes
  2. Mission Control never writes files
  3. Runtime never performs storage (calls `CheckpointSink` protocol)
  4. Contracts only (AST test rejects private-attribute access)

### Recovery Responsibilities
- **Memory:** Survives restart, durable anchor (Constitution §11.2)
- **Mission State:** Enables precise recovery — says what was attempted
- **Evidence:** Says what was actually confirmed (Verification)
- **Interrupted tasks:** Quarantined, never re-run (unknown side effects)
- **Strategic re-run:** Brain's judgement (Constitution §11)

---

## Security Boundaries

### Permission System (Central Gate)
- **Veto power:** Consulted before any step above `READ_ONLY`, regardless of Operator Instance
- **Mission-wide:** Single grant ledger prevents silent re-satisfaction/re-asking across Operator Instances
- **IRREVERSIBLE rule:** `ALWAYS_FOR_CAPABILITY` never satisfies (ADR-0009)

### Relay Pattern (ADR-0005, ADR-0006)
- Outer approval → inner grant key (Plugin → Executor, Composite → sub-steps)
- Never bypasses Permission System, never weakens what gets checked

### Runtime ApprovalGate (MB028.0)
- Single funnel: `_handle_task()` only place reaching gateway
- Fail-closed: no gate ⇒ nothing runs
- Protocol in `runtime/` — Runtime gains no Permission System dependency

### Configuration Integrity
- Single source prevents drift (safety bug if readers disagree)
- Injected, not hardcoded (Constitution §13)

### Broker Isolation
- Zero upward dependencies (not on Brain, Operator, Mission Control, Runtime)
- No Environment access, no provider SDK imports
- Decision output = existing Capability + parameters (no new execution path)

---

## Ownership Registry Alignment (Constitution §16, FROZEN)

| Component | Constitution Home | This Document |
|-----------|-------------------|---------------|
| `CapabilityIndex` / Plugin Registry | Shared Infrastructure (§5.1) | ✅ Capability Registry |
| `Permission System` | Shared Infrastructure (§5.2) | ✅ Permission System |
| `MissionManager` / `Mission` state machine | Shared Infrastructure (§5.3) | ✅ Mission State |
| `Memory` | Shared Infrastructure (§5.4) | ✅ Memory (6 layers) |
| `Configuration` | Shared Infrastructure (§5.5) | ✅ Configuration |
| `Telemetry/Evidence aggregation` | Shared Infrastructure (§5.6) | ✅ Telemetry/Audit |
| `AI Capability Broker` | Shared Infrastructure (§5.7) | ✅ AI Capability Broker |
| `Operator Registry` | Shared Infrastructure (§8.2, part of §5.1) | ✅ Part of Capability Registry |

**Note:** `MasterAgentSession` is **Brain-adjacent, transitional** (not Shared Infrastructure). `Environment Session Manager` is **Operator (per-instance)** (deliberately not shared).

---

## Current Implementation Status

| Component | Constitution Status | Implementation Status | Notes |
|-----------|---------------------|----------------------|-------|
| **Capability Registry** | FROZEN | ✅ **IMPLEMENTED** | `plugins/registry.py`; Mission Control has separate coordination catalogue |
| **Permission System** | FROZEN | ✅ **IMPLEMENTED** | `permissions/`; relay pattern + Runtime ApprovalGate |
| **Mission State** | FROZEN | ⚠️ **PARTIAL** | State machine ✅; `MissionManager` unwired (`MEMORY_ARCHITECTURE.md` §11) |
| **Memory (Layers 1-3)** | FROZEN | ✅ **IMPLEMENTED** | `memory/` — Conversation, Mission, SQLite |
| **Memory (Layer 4)** | RESEARCH-BACKED | ⏳ **RESERVED** | `KnowledgeMemory` interface only |
| **Memory (Layer 5)** | FUTURE | ⏳ **INTERFACE ONLY** | `VectorMemory` interface only |
| **Memory (Layer 6)** | OPTIONAL FUTURE | ⏳ **INTERFACE ONLY** | `CloudSyncMemory` interface only |
| **Configuration** | FROZEN | ⚠️ **PARTIAL** | Scattered injection; no centralized module |
| **Telemetry/Audit (aggregated)** | FROZEN | ⚠️ **PARTIAL** | Mission Record ✅; `LocalExecutor._log` unbounded ❌ |
| **AI Capability Broker** | RESEARCH-BACKED | ❌ **NOT IMPLEMENTED** | Architecture only (MB027); `broker/` package missing |
| **Persistence (Operational)** | FROZEN (MB025) | ✅ **IMPLEMENTED** | `persistence/` — event log + snapshot, recovery |
| **AI Infrastructure Executive** | RESEARCH-BACKED | ❌ **NOT IMPLEMENTED** | Machine-touching counterpart to Broker |

### Proposed Changes (Awaiting Ratification)
- **ADR-0015 (Persistence Strategy):** Three additive changes to frozen components — `TaskDispatcher.restore_objective()` + two others. Recorded as **Proposed** in `FOUNDER_CONSTITUTION_FREEZE.md`.
- **ADR-0020 (Founder Approval Workflow):** Ships frozen-component changes. Recorded as **Proposed**.

---

## Open Questions

1. **MissionManager unwired** — `cli.py`'s `MasterAgentSession` only live path; `MissionManager` imports `MemoryStore` but unused (`MEMORY_ARCHITECTURE.md` §11). Scoped to "real Planner" work (`ROADMAP.md` item 3).

2. **Centralized Configuration** — Constitution requires single source; current implementation uses constructor injection scattered across modules. No centralized configuration module documented.

3. **AI Capability Broker not implemented** — Architecture frozen (MB027, Amendment 2), but `src/master_agent/broker/` does not exist. Required for Model Router (MB032) and Workers needing intelligence.

4. **AI Infrastructure Executive not implemented** — Machine-touching counterpart to Broker (scans, probes, benchmarks, inventories, installs). Required for Broker's inventory freshness.

5. **Telemetry aggregation** — `LocalExecutor._log` is unbounded in-memory list, not part of Memory (`MEMORY_ARCHITECTURE.md` §11). Would leak in long-running daemon. Flagged on `ROADMAP.md`.

6. **CapabilityManifest.input_schema/output_schema empty** — Declared in frozen `plugins/base.py`, populated by nothing. Planner guesses payload names (MB036 Finding 4, MB037 Finding 3). Top backlog item.

7. **In-mission recovery decision procedure** (Constitution §11.4) — Exact escalation rules unspecified. Not a blocker for current `ROADMAP.md`.

8. **Stateful Environment Sessions in Action contract** (Constitution §8.3, §12) — One-shot vs multi-Step needs. Not a blocker.

9. **ADR-0015 / ADR-0020 Proposed** — Awaiting founder ratification before applying to frozen components.

---

## Future Extraction Targets

1. `src/master_agent/plugins/registry.py` — Capability Registry implementation
2. `src/master_agent/permissions/permission_system.py` — Permission System implementation
3. `src/master_agent/mission_manager/` — Mission State (`mission.py`, `mission_manager.py`)
4. `src/master_agent/memory/` — All 6 layers implementation
5. `src/master_agent/runtime/approval.py` — ApprovalGate protocol and types
6. `src/master_agent/persistence/` — Event log, snapshot, recovery implementation
7. `src/master_agent/broker/` — AI Capability Broker (when implemented)
8. `src/master_agent/ai_infrastructure/` — AI Infrastructure Executive (when implemented)
9. `src/master_agent/runtime/checkpoint.py` — CheckpointSink protocol
10. `tests/test_persistence_architecture.py` — Purity enforcement tests

---

## Wiki Links Added

- `[[KALPAVRIKSHA_VISION_V2.md]]` — Constitution source (§5, §16, §17, §20)
- `[[FOUNDER_CONSTITUTION_FREEZE.md]]` — Freeze record, amendments, section status
- `[[ARCHITECTURE.md]]` — Implementation map (§4.8 Memory, §5 Model Router)
- `[[MEMORY_ARCHITECTURE.md]]` — Six-layer memory design
- `[[MISSION_CONTROL_ARCHITECTURE.md]]` — Coordination layer, registries, Audit Stream
- `[[RUNTIME_ENGINE_ARCHITECTURE.md]]` — Heartbeat loop, ApprovalGate, checkpointing
- `[[PERSISTENCE_ARCHITECTURE.md]]` — Event log + snapshot, recovery
- `[[AI_CAPABILITY_BROKER_ARCHITECTURE.md]]` — Broker design (Provider Registry, Decision Engine)
- `[[01_executive_brain.md]]` — Brain layer (Model Router consults Broker)
- `[[02_constitution.md]]` — Constitution summary
- `[[03_universal_executive_operator.md]]` — Operator layer (Permission boundaries, Orchestrator)
- `[[system_overview.md]]` — System overview
- `[[docs/adr/0005]]`–`[[docs/adr/0006]]` — Permission relay pattern
- `[[docs/adr/0007]]`–`[[docs/adr/0008]]` — Memory backend and scale review
- `[[docs/adr/0009]]` — PermissionCategory + IRREVERSIBLE grant rule
- `[[docs/adr/0010]]` — Shared Infrastructure layer
- `[[docs/adr/0011]]` — Verification independent subsystem
- `[[docs/adr/0015]]` — Persistence strategy (Proposed)
- `[[docs/adr/0017]]` — AI Capability Broker (ratified)
- `[[docs/adr/0019]]` — Runtime approval boundary
- `[[docs/adr/0020]]` — Founder approval workflow (Proposed)

---

*Document created from verified sources only. No implementation details invented. Terminology preserved exactly. Design/implementation differences recorded without reconciliation.*