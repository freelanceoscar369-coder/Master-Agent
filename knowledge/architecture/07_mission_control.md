# Mission Control

## Purpose
Documents the runtime coordination layer that registers capabilities, orders task execution, receives all events, preserves an immutable audit stream, tracks learning needs, and exposes an honest system state snapshot to the founder. Per `MISSION_CONTROL_ARCHITECTURE.md` (Mission Brief 023) and Constitution §4, §5, §6, §8, §9, §10, §15, §16.

## Constitutional Role

### Constitution §4 (Operator) & §5 (Shared Infrastructure)
Mission Control sits at the coordination layer between the **Executive Brain** (what to do) and the **Universal Executive Operator** (how to execute). It performs **no work** — no Environment access, no model calls, no filesystem operations. It decides *what should happen next and in what order*, and records *what actually happened*.

### Constitution §5.1 (Capability Registry)
Shared Infrastructure owns the **execution-time** Capability Registry (Plugin object → capability). Mission Control owns a separate **coordination catalogue** (descriptors: names, versions, owners, health, dependencies) — populated by adapter reading Plugin manifests.

### Constitution §5.2 (Permission System)
Single grant ledger in Shared Infrastructure. Mission Control's Dispatcher checks readiness; Runtime consults ApprovalGate at execution funnel.

### Constitution §5.3 (Mission State)
Owned by Shared Infrastructure (`MissionManager` / `Mission` state machine). Mission Control transitions state through Shared Infrastructure contract.

### Constitution §5.4 (Memory)
Shared Infrastructure owns Memory. Mission Control emits events; Memory persists MissionRecord automatically at terminal states (Rule 7).

### Constitution §8 (Multi-Operator)
Mission Control's Operator Registry tracks live Operator Instances. Capability Registry resolves which Operator Instance services a Step.

### Constitution §9 (Knowledge)
Mission Control's Knowledge Acquisition Queue implements 7-stage pipeline. Promotion gate (`VERIFICATION → KNOWLEDGE_STORAGE`) requires explicit `human_approved=True` (ADR-0012).

### Constitution §10 (Verification)
Verification Subsystem is Operator-adjacent but structurally independent. Mission Control receives Evidence references, never re-derives judgments.

### Constitution §15 (Human Oversight)
One approval per mission via relay pattern (Rule 6). Mission Control's Approval Queue surfaces pending decisions.

---

## Responsibilities

From `MISSION_CONTROL_ARCHITECTURE.md` §1:

1. **Registers who can do what** — Executive Registry, Capability Registry (coordination catalogue)
2. **Turns objectives into ordered capability calls** — Task Dispatcher with dependency resolution
3. **Receives every event** — Universal Event Bus (single `Event` schema)
4. **Preserves immutable audit stream** — Audit Stream (append-only, system-wide)
5. **Tracks what the system still needs to learn** — Self-Development Queue + Knowledge Acquisition Queue
6. **Exposes one honest snapshot of system state to the founder** — Founder State backend contract

**What Mission Control MUST NEVER Do (§1):**
- Perform work (no Environment access, no Playwright, no filesystem, no model calls)
- Call a plugin directly — `TaskDispatcher` marks tasks ready, assigns Executive; outside caller (Runtime) invokes
- Maintain private copy of Permission grants, Mission State, or Memory
- Define a second Evidence type — reuses Verification's `Evidence`

---

## Mission Lifecycle Management

### Objective → Task Decomposition
- **Objective**: What the founder wants (submitted via `MissionControl.submit_objective()`)
- **Task**: Decomposed unit naming a **qualified capability** + optional `depends_on` list
- **Qualified capability**: Deterministic mapping `qualified_name("filesystem", "read_file") == "Filesystem.ReadFile"` (not hand-maintained table)

### Task States (from Dispatcher)
- `CREATED` → `DISPATCHED` → `RUNNING` → `COMPLETED` | `FAILED` | `BLOCKED`
- Failed dependency → `BLOCKED` (never silently skipped, never auto-retried)
- Dependency cycles rejected at submission time

### Mission State (Shared Infrastructure §5.3)
Owned by Shared Infrastructure, not Mission Control. State machine:
```
draft → planned → awaiting_approval → executing → verifying → completed | failed | cancelled
```
Mission Control transitions through Shared Infrastructure contract.

---

## Mission State

**Ownership:** Shared Infrastructure (§5.3) — `MissionManager` / `Mission` state machine
**Mission Control Role:** Transitions state via Shared Infrastructure contract; emits events for each transition

### State Transitions Emitted as Events
- `OBJECTIVE_SUBMITTED`, `OBJECTIVE_RESTORED`
- `TASK_DISPATCHED`, `TASK_STARTED`, `TASK_COMPLETED`, `TASK_FAILED`, `TASK_BLOCKED`
- `APPROVAL_REQUESTED`, `APPROVAL_GRANTED`, `APPROVAL_DENIED`
- `VERIFICATION_STARTED`, `VERIFICATION_COMPLETED`

---

## Event Bus

### Universal Event Bus (Deliverable #10)
**Single `Event` schema** — only schema any Executive uses to report anything.

```python
Event(event_id, event_type, occurred_at, source, objective_id, task_id, capability, payload, error)
```

**Properties:**
- `source`: Executive ID or `"mission_control"`
- `payload`: plain JSON-shaped dict (never live object) — survives logging/persistence/replay
- **Delivery:** synchronous, in-process (message broker wrong for Founder Edition)
- **Subscriber isolation:** failure captured and re-emitted; never breaks publisher or starves other subscribers

### Event Types (10 brief-named + lifecycle additions)
- Brief-named: `OBJECTIVE_*`, `TASK_*`, `APPROVAL_*`, `VERIFICATION_*`
- Additions: `TASK_DISPATCHED`, `TASK_BLOCKED`, `EXECUTIVE_REGISTERED`, `EXECUTIVE_HEALTH_CHANGED`, `WORKER_STATE_CHANGED`, `KNOWLEDGE_*` pipeline stages
- **Rule:** state transition not observable → can't be audited → breaks "every failure is auditable"

---

## Task Dispatcher

### Responsibilities (§7)
1. Computes ready tasks (every dependency `COMPLETED`)
2. Resolves ready task's capability to registered Executive (provides it + healthy)
3. Marks `DISPATCHED`, assigns Executive, emits `TASK_DISPATCHED`
4. Accepts `task_started` / `task_completed` / `task_failed` reports, re-computes readiness

### Failure Handling
- Failed dependency → task `BLOCKED` (never silently skipped, never auto-retried)
- Auto-retry = strategic recovery → forbidden (Brain's per Constitution §11)
- Blocked tasks surfaced in Founder State (visible, not absorbed)

### Concurrency
- **No priority scheduling beyond dependency order** (deliberate)
- **No distributed dispatch** (Constitution §8.5 leaves concurrency EVOLVABLE)
- **No retry policy** (strategic recovery = Brain's)

---

## Registries

### 1. Executive Registry (Mission Control's)
**Purpose:** Coordination catalogue — who exists, health, current task
**Contents:** Descriptors (names, versions, owners, health, dependencies)
**Populated by:** `register_plugin_as_executive()` reading Plugin manifest
**Consumer:** Dispatcher and Founder State (coordination time)

### 2. Capability Registry (Mission Control's)
**Purpose:** What capabilities system possesses, at what version, provided by which Executive, health
**Contents:** Descriptors (not live objects)
**Populated by:** Adapter reading Plugin manifests
**Consumer:** Dispatcher and Founder State

### 3. Shared Infrastructure's Capability Registry (Different!)
**Purpose:** Execution-time lookup — "which Plugin object services this capability right now"
**Contents:** Live plugin object references
**Populated by:** `PluginRegistry.register(plugin)`
**Consumer:** Orchestrator / Model Router (execution time)

### 4. Operator Registry (Part of Shared Infrastructure's Capability Registry per §8.2)
**Purpose:** Tracks live Operator Instances (which capabilities they can currently service)
**Relation:** Operator Instance advertises capabilities same way Worker does

---

## Queue Architecture

### Self-Development Queue (Deliverable #6)
**Categories:** `PENDING_CAPABILITY`, `LEARNING_TASK`, `ARCHITECTURE_IMPROVEMENT`, `RESEARCH_REQUEST`, `IMPLEMENTATION`
**State Machine:** `PROPOSED → ACCEPTED → IN_PROGRESS → DONE` (+ `REJECTED`)
**Mission Control Role:** Queues and orders; **never implements**

### Knowledge Acquisition Queue (Deliverable #7)
**Pipeline (7 stages, advance one at a time, skipping rejected):**
```
NEED → RESEARCH → SOURCE_COLLECTION → COMPARISON → VERIFICATION → KNOWLEDGE_STORAGE → CAPABILITY_CREATION
```

**Promotion Gate (Enforced in Code, Not Convention):**
- Advancing `VERIFICATION → KNOWLEDGE_STORAGE` requires explicit `human_approved=True`
- Without it: refused with structured error naming ADR-0012
- Mission Control drives pipeline **up to** gate autonomously, **never past it**
- Constitution ADR-0012: promoting knowledge silently reshapes future reasoning → high-leverage action → gated by §15

---

## Founder State

### Contract (Deliverable #9) — Backend Only, No UI
```python
MissionControl.founder_state() → FounderState snapshot
```

### 10 Fields
| Field | Description |
|-------|-------------|
| `current_objective` | Active objective |
| `current_mission` | Active mission |
| `current_executive` | Assigned Executive |
| `current_capability` | Executing capability |
| `progress` | Progress estimate |
| `evidence` | Evidence *references* from Verification (not re-derived) |
| `errors` | Current errors |
| `eta` | **Honest or absent** — mean duration × tasks remaining; `None` if <1 task completed |
| `waiting_approval` | Pending approvals |
| `learning_progress` | Queue advancement status |

**ETA Discipline:** Confidently-wrong ETA worse than no ETA — same as Verification refusing execution success → mission success.

---

## Audit Stream

### Deliverable #8
**Subscribes to Event Bus** → records **every** event as immutable `AuditEntry`
- Append-only: no update, no delete, no truncation
- Reads return copies (caller cannot mutate history by reference)

### Distinction from Worker Audit (`verification/audit.py`)
| Aspect | Worker Audit (MB022) | Mission Control Audit Stream |
|--------|---------------------|------------------------------|
| Scope | Per-Worker, per-step Execute→Verify→Audit | System-wide, event-level |
| Contains | One capability call's Evidence | Objectives, dispatch decisions, health changes, queue movements, Worker step records |
| Relation | Worker's `AuditRecord` can be ingested as event | Not a second copy |

### Persistence (Named Debt)
- Unbounded in-memory list (same as `LocalExecutor._log`)
- Explicitly not solved differently here — one answer when addressed
- Listed in `MISSION_BRIEF_023.md` Technical Debt section

---

## Recovery Relationship

### Mission Control's Role in Recovery
- Emits events for every state transition (audit trail)
- Maintains Task/Objective state for Dispatcher readiness computation
- **Does not decide recovery strategy** — `RECOVERING` state records progress, does not decide (Brain's per Constitution §11)

### Integration with Persistence (MB025)
- Persistence subscribes to Event Bus → `events.jsonl` append-only
- `TaskDispatcher.restore_objective()` proposed (ADR-0015) — additive public method to restore without republishing creation events
- **Proposed, not settled** — smallest possible change, isolated

### Quarantined Tasks
- Interrupted tasks restored as `FAILED` with error "interrupted by shutdown; outcome unknown — not retried automatically"
- Dependents become `BLOCKED` — visible in Founder State, not silently dropped
- Re-running = strategic judgement for Brain (Constitution §11)

---

## Runtime Relationship

### Runtime Engine (MB024) as Outside Caller
- **Mission Control:** Switchboard (decides order, emits events)
- **Runtime:** Hands (pulls ready tasks, invokes via gateway, reports back)

### Interaction Points
1. `mission_control.dispatch_ready(objective_id)` → returns assigned tasks
2. Runtime calls `task_started()`, `task_completed()`, `task_failed()` with `evidence_id`
3. Runtime consults `ApprovalGate` at `_handle_task()` funnel (MB028.0)
4. Runtime re-offers `_awaiting_approval` tasks first each cycle
5. Runtime publishes `RUNTIME_*` events to Event Bus

### Approval Boundary (MB028.0/ADR-019)
- Mission Control's `request_approval()` publishes `APPROVAL_REQUESTED`/`APPROVAL_REQUIRED` **once** when question new
- Runtime holds pending tasks in `_awaiting_approval` (Mission Control considers them dispatched)
- Runtime re-consults gate each cycle; `FounderApprovalGate` wraps `PermissionSystemGate`

---

## Memory Relationship

### Memory (Shared Infrastructure §5.4) — Durable Anchor
- Mission Control emits events → Memory persists MissionRecord automatically at terminal states (Rule 7)
- Evidence references carried in `FounderState` and `task_completed` events
- Memory aggregates Evidence across all Operator Instances (single history)

### Knowledge Pipeline
- Mission Control's Knowledge Acquisition Queue → Promotion Review (`human_approved=True`) → Permanent Knowledge (Memory Layer 4)
- Brain (Planner) consumes Permanent Knowledge same as recent Mission history

---

## Persistence Relationship

### Mission Control + Persistence (MB025)
**Purity Constraints (Mechanically Enforced):**
1. Mission Control **cannot access filesystem APIs** — forbidden-import test includes `json`, `pathlib`, `sqlite3`, `os`, `io`
2. Mission Control **emits events** a persistence layer can subscribe to (correct seam)
3. Persistence **cannot dispatch Executives** — no `runtime` import, no gateway, no plugin

### Storage Format
- `events.jsonl` — append-only, one event per line (audit history, replay)
- `snapshot.json` — versioned envelope + checksum (fast restart O(live state))
- Recovery: `recover()` restores Mission Control (executives → capabilities → objectives → audit) + Runtime counters

### ADR-0015 Proposed
- `TaskDispatcher.restore_objective(objective)` — additive, public, non-publishing method
- Restoring through `submit()` would republish creation events → audit claims objective submitted twice
- Writing to `_objectives` directly forbidden by Rule 4

---

## Current Implementation Status

| Component | Constitution/Architecture | Implementation Status | Notes |
|-----------|---------------------------|----------------------|-------|
| **Universal Event Bus** | FROZEN (§5) | ✅ **IMPLEMENTED** | Single `Event` schema, synchronous delivery, subscriber isolation |
| **Executive Registry** | FROZEN (§4) | ✅ **IMPLEMENTED** | Coordination catalogue; adapter reads Plugin manifests |
| **Capability Registry (MC)** | FROZEN (§5) | ✅ **IMPLEMENTED** | Descriptors only; deterministic `qualified_name()` |
| **Task Dispatcher** | FROZEN (§7) | ✅ **IMPLEMENTED** | Dependency-ordered; failed dep → `BLOCKED`; no auto-retry |
| **Worker Lifecycle** | FROZEN (Deliverable #4) | ✅ **IMPLEMENTED** | 9 states + legal transition table; `COMPLETED → READY` for reuse |
| **Self-Development Queue** | FROZEN (Deliverable #6) | ✅ **IMPLEMENTED** | 5 categories, `PROPOSED→ACCEPTED→IN_PROGRESS→DONE` |
| **Knowledge Acquisition Queue** | FROZEN (Deliverable #7) | ✅ **IMPLEMENTED** | 7-stage pipeline; promotion gate `human_approved=True` enforced in code |
| **Founder State** | FROZEN (Deliverable #9) | ✅ **IMPLEMENTED** | `founder_state()` → 10-field snapshot; honest ETA |
| **Audit Stream** | FROZEN (Deliverable #8) | ✅ **IMPLEMENTED** | Append-only `AuditEntry`; distinct from Worker audit |
| **Plugin Registration Adapter** | FROZEN (§9) | ✅ **IMPLEMENTED** | `register_plugin_as_executive()` reads manifest; zero Executive changes |
| **Persistence Integration** | MB025 | ✅ **IMPLEMENTED** | Event log + snapshot; `recover()`; ADR-0015 Proposed |
| **Approval Queue Integration** | MB028.1 | ✅ **IMPLEMENTED** | `request_approval()`, `expire_approvals()`, `find_open()` |
| **Mission Manager Wiring** | Constitution §5.3 | ⚠️ **PARTIAL** | `MissionManager` imports `MemoryStore` but unwired from live path (`MEMORY_ARCHITECTURE.md` §11) |
| **Event Bus Async/Cross-Process** | EVOLVABLE (§12) | ⏳ **RESERVED** | Sync in-process only; interface small for drop-in replacement |
| **Audit Stream Persistence** | EVOLVABLE (§12) | ⏳ **RESERVED** | Unbounded in-memory; same debt as `LocalExecutor._log` |
| **Dispatcher Incremental Readiness** | EVOLVABLE (§12) | ⏳ **RESERVED** | O(tasks) per call; not incremental |

---

## Design vs Implementation Differences

| Area | Design (Architecture/Constitution) | Implementation | Status |
|------|-----------------------------------|----------------|--------|
| **Two Capability Registries** | Deliberately separate (execution vs coordination) | ✅ Implemented correctly | ✅ MATCH |
| **Executive = Worker** | Terminology alias (Amendment 1) | ✅ `Worker` canonical in Constitution; `Executive` in MC API | ✅ MATCH |
| **No Work in MC** | Hard boundary, test-enforced | ✅ Import-parsing test forbids plugin/Playwright/filesystem/model imports | ✅ MATCH |
| **Dispatcher No Auto-Retry** | Strategic recovery = Brain's | ✅ Failed dep → `BLOCKED`; never auto-retried | ✅ MATCH |
| **Promotion Gate in Code** | Not convention — enforced | ✅ `human_approved=True` required; structured error on refusal | ✅ MATCH |
| **Founder State ETA** | Honest or absent | ✅ Mean duration × remaining; `None` if <1 task done | ✅ MATCH |
| **Audit Stream vs Worker Audit** | Distinct (system-wide vs per-step) | ✅ Separate implementations; Worker audit ingestible as event | ✅ MATCH |
| **Persistence Separation** | MC emits events; Persistence subscribes | ✅ Forbidden-import test; `recover()` restores MC + Runtime | ✅ MATCH |
| **ADR-0015 Proposed** | `restore_objective()` additive | ⏳ Proposed, awaiting ratification | ⚠️ PROPOSED |
| **Event Bus Sync Only** | Correct for Founder Edition | ⚠️ Named debt for multi-process future | 📝 DOCUMENTED |
| **Dispatcher O(tasks) Readiness** | Correct for single-founder | ⚠️ Named debt for multi-year deployment | 📝 DOCUMENTED |

---

## Open Questions

1. **MissionManager unwired** — `cli.py`'s `MasterAgentSession` only live path; `MissionManager` imports `MemoryStore` but unused (`MEMORY_ARCHITECTURE.md` §11). Scoped to "real Planner" work (`ROADMAP.md` item 3).

2. **ADR-0015 Proposed** — `TaskDispatcher.restore_objective()` + two other additive changes to frozen components. Awaiting founder ratification (`FOUNDER_CONSTITUTION_FREEZE.md` §4a).

3. **Event Bus synchronous/in-process** — Named as future revisiting point for multi-process deployment (§12). Interface small for drop-in replacement.

4. **Audit Stream unbounded in-memory** — Same debt as `LocalExecutor._log` (MB023). Not solved differently — one answer when addressed.

5. **Dispatcher readiness O(tasks) not incremental** — Correct for single-founder; wrong for multi-year deployment (§12).

6. **Pause/resume/cancel** — Needs ratified ADR (MB037 §5). `test_missions_lifecycle.py` fails if added without ADR.

7. **Current objective ID never advances** — `submit_objective()` sets only when `None`; after boot scan, later missions leave it pointing at scan (`MB037` Defect 6). Frozen `mission_control/` — backlog.

8. **Count events not implemented** — MB026 posture: `count_events()` not fixed in frozen `mission_control/`; recorded in backlog.

---

## Future Extraction Targets

1. `src/master_agent/mission_control/mission_control.py` — Core `MissionControl` class
2. `src/master_agent/mission_control/events.py` — `Event`, `EventType`, `EventBus`
3. `src/master_agent/mission_control/dispatcher.py` — `TaskDispatcher`, `Task`, `Objective`
4. `src/master_agent/mission_control/registries.py` — `ExecutiveRegistry`, `CapabilityRegistry`
5. `src/master_agent/mission_control/queues.py` — `SelfDevelopmentQueue`, `KnowledgeAcquisitionQueue`
6. `src/master_agent/mission_control/approvals.py` — `ApprovalQueue`, `PendingApproval`
7. `src/master_agent/mission_control/founder_state.py` — `FounderState` snapshot
8. `src/master_agent/mission_control/audit.py` — `AuditStream`, `AuditEntry`
9. `src/master_agent/mission_control/adapters.py` — `register_plugin_as_executive()`
10. `tests/test_mission_control_architecture.py` — Import-parsing purity test
11. `tests/test_mission_control_integration.py` — Adapter integration test
12. `docs/adr/0014` — Executive/Worker terminology
13. `docs/adr/0015` — Persistence strategy (Proposed)
14. `docs/adr/0020` — Founder approval workflow (Proposed)

---

## Wiki Links Added

- `[[KALPAVRIKSHA_VISION_V2.md]]` — Constitution §4, §5, §6, §8, §9, §10, §15, §16
- `[[FOUNDER_CONSTITUTION_FREEZE.md]]` — Freeze record, amendments, named gaps
- `[[MISSION_CONTROL_ARCHITECTURE.md]]` — Primary source document
- `[[ARCHITECTURE.md]]` — Implementation map
- `[[RUNTIME_ENGINE_ARCHITECTURE.md]]` — Runtime loop, ApprovalGate, checkpointing
- `[[PERSISTENCE_ARCHITECTURE.md]]` — Event log + snapshot, recovery, ADR-0015
- `[[MEMORY_ARCHITECTURE.md]]` — Six-layer memory, auto-persist
- `[[01_executive_brain.md]]` — Brain (strategic recovery, knowledge nomination)
- `[[02_constitution.md]]` — Constitution summary
- `[[03_universal_executive_operator.md]]` — Operator (Orchestrator, Verification)
- `[[04_shared_infrastructure.md]]` — Shared Infrastructure (Permission, Mission State, Memory)
- `[[05_memory_system.md]]` — Memory (durable anchor, Knowledge Lifecycle)
- `[[06_runtime_engine.md]]` — Runtime (loop, gateway, retry, approval)
- `[[system_overview.md]]` — System overview
- `[[docs/adr/0005]]`–`[[docs/adr/0006]]` — Permission relay pattern
- `[[docs/adr/0009]]` — PermissionCategory + IRREVERSIBLE rule
- `[[docs/adr/0010]]` — Shared Infrastructure layer
- `[[docs/adr/0011]]` — Verification independent subsystem
- `[[docs/adr/0012]]` — Knowledge Lifecycle
- `[[docs/adr/0013]]` — Multi-Operator architecture
- `[[docs/adr/0014]]` — Executive/Worker terminology
- `[[docs/adr/0015]]` — Persistence strategy (Proposed)
- `[[docs/adr/0020]]` — Founder approval workflow (Proposed)

---

*Document created from verified sources only. No Mission Control capabilities redesigned. Terminology preserved exactly. Constitutional/Architecture/Implementation/Gaps separated. Design/implementation differences recorded without reconciliation.*