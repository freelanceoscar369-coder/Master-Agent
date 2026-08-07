# Universal Executive Operator

## Purpose
Documents the execution layer: Orchestrator, Verification Subsystem, Worker/Plugin Runtime, Environment Session Management — per `KALPAVRIKSHA_VISION_V2.md` §4 (FROZEN).

## Constitutional Definition

### Role (§4)
The **Universal Executive Operator** is the execution layer. It carries out what the Brain decided, with full accountability. It **never decides, never plans, and never holds an opinion about *why* a Step exists — only *how* to run it safely and *whether it actually worked*.**

### Three-Layer Position (§6)
```
Executive Brain (decides what, how to structure, how to explain)
        │
Shared Infrastructure (one consistent source of truth both sides depend on)
        │
Universal Executive Operator (carries out what was decided, with accountability)
```

**Dependency direction only** — Brain and Operator never depend on each other's internals; both depend downward on Shared Infrastructure.

### Constitutional Responsibilities (§4)
1. **Orchestrator** — walks `MissionPlan`, resolves Capability → Worker, checks Permission System, invokes Worker, triggers Verification, applies retry/failure-branching policy
2. **Worker Runtime** — Operator-owned implementation detail (not distinct architectural layer)
3. **Verification Subsystem** — runs alongside Operator (needs Environment access) but through its own contract, never through Worker's `invoke()`

### Constitutional Non-Responsibilities (§4.4)
- Does not decide what a Mission should accomplish
- Does not maintain private copy of Permission grants, Mission state, or Memory — all three are Shared Infrastructure (§5)
- Does not nominate or promote Knowledge (§9) — produces Evidence; Brain and Promotion Review decide what becomes durable

---

## Architecture Components

### 1. Orchestrator (`src/master_agent/orchestrator/orchestrator.py`)

**Purpose** (from `ARCHITECTURE.md` §4.5): Walks a `MissionPlan`, resolves each Step's capability to a plugin via the registry, checks the Permission System, invokes the plugin. Retry/failure-branching policy lives here, not in individual plugins.

**Implementation Status:** **IMPLEMENTED** — `Orchestrator` class with `execute_capability`, `execute_step`, `execute_plan` methods.

**Key Behaviors:**
- Resolves capability via `PluginRegistry.find_for_capability()` — takes first candidate (Founder Edition: no selection policy for multiple providers)
- Checks Permission System before invocation (`PermissionSystem.check()`)
- Returns `StepResult(step_id, result, blocked_on_approval)`
- `execute_plan()` walks steps in list order, stops at first approval block or failure
- **Explicitly NOT the mission path** since MB037 — dependency-graph scheduling belongs to Mission Control's Dispatcher; Orchestrator's sequential walk is for `master-agent-demo` entry point only

**Constitution Alignment:**
- ✅ Resolves Capability → Worker via Capability Registry
- ✅ Checks Permission System via Shared Infrastructure
- ✅ Invokes Worker, captures result
- ✅ Retry/failure-branching policy lives here (sequential, stops on first problem)
- ⚠️ Does NOT trigger Verification — that is Runtime's responsibility (MB024)
- ⚠️ Does NOT walk dependency graph — Mission Control's Dispatcher owns execution order

### 2. Worker Runtime / Plugin Model

#### Plugin Contract (`src/master_agent/plugins/base.py`)
**Status:** **IMPLEMENTED** — `Plugin` ABC, `ModelProvider` specialization

**Core Interface:**
```python
class Plugin(ABC):
    @property
    @abstractmethod
    def manifest(self) -> PluginManifest: ...
    
    @abstractmethod
    def invoke(self, capability: str, payload: dict) -> InvocationResult: ...
```

**Manifest Structure:**
- `PluginManifest(name, version, capabilities: list[CapabilityManifest])`
- `CapabilityManifest(name, description, risk_tier, input_schema, output_schema, permission_category)`

**RiskTier Enum:** `READ_ONLY`, `REVERSIBLE_WRITE`, `IRREVERSIBLE`
**PermissionCategory Enum:** `READ`, `WRITE`, `MODIFY`, `DELETE`, `SYSTEM`

**ModelProvider Specialization:**
- `CAPABILITY_NAME = "generate_text"`
- `generate(prompt, context, **opts) -> str`
- `invoke()` delegates to `generate()`

**Registry:** `PluginRegistry` indexes by capability, not plugin name. Orchestrator resolves "who can do X" without caring which plugin.

#### Filesystem Plugin (`src/master_agent/plugins/filesystem_plugin.py`)
**Status:** **IMPLEMENTED** — 14 capabilities via declarative registration (MB005)

**Capabilities (from `FILESYSTEM_CAPABILITIES.md`):**
| Category | Risk Tier | Capabilities |
|----------|-----------|--------------|
| Read | `READ_ONLY` | `read_file`, `list_directory`, `search_files`, `file_exists`, `directory_exists` |
| Write | `REVERSIBLE_WRITE` | `write_file`, `append_file` |
| Modify | `REVERSIBLE_WRITE` | `rename_file`, `copy_file`, `move_file` |
| Delete | `IRREVERSIBLE` | `delete_file`, `delete_folder` |
| Composite | — | `create_folder`, `workspace_bootstrap` |

**Registration:** Loop over declared Action classes — adding capability #N = one new class in tuple, never edit to `FilesystemPlugin`.

#### Browser Worker (`BROWSER_WORKER_ARCHITECTURE.md`, MB022)
**Status:** **IMPLEMENTED** — Reference Worker against frozen Constitution

**9 Atomic Actions:**
| Action | Capability | Risk Tier | Category | Wraps |
|--------|------------|-----------|----------|-------|
| `OpenBrowserSessionAction` | `open_browser_session` | `REVERSIBLE_WRITE` | `SYSTEM` | Playwright launch + context + page |
| `CloseBrowserSessionAction` | `close_browser_session` | `REVERSIBLE_WRITE` | `SYSTEM` | Playwright teardown |
| `NavigateAction` | `navigate` | `REVERSIBLE_WRITE` | `MODIFY` | `page.goto()` |
| `ClickAction` | `click` | `REVERSIBLE_WRITE` | `MODIFY` | `page.locator().click()` |
| `TypeTextAction` | `type_text` | `REVERSIBLE_WRITE` | `WRITE` | `page.locator().fill()` |
| `PressKeyAction` | `press_key` | `REVERSIBLE_WRITE` | `MODIFY` | `page.keyboard.press()` |
| `ScrollAction` | `scroll` | `REVERSIBLE_WRITE` | `MODIFY` | `page.mouse.wheel()` |
| `WaitForSelectorAction` | `wait_for_selector` | `READ_ONLY` | `READ` | `page.locator().wait_for()` |
| `ObserveBrowserAction` | `observe_browser` | `READ_ONLY` | `READ` | `normalize_observation()` |

**Environment Session Manager:** `BrowserSessionManager` (one per Operator Instance) owns `BrowserSession` (Playwright instance, Browser, BrowserContext, Page). Deliberately **NOT Shared Infrastructure** (Constitution §5.8).

**Generic Verification Package:** `verification/` — `Verifier` ABC, `Evidence`, `ExpectedOutcome`, `ObservationCheck`, `Verdict`, `AuditRecord`, `AuditLog` — zero Playwright imports, reusable by Desktop/Terminal/REST Workers.

### 3. Verification Subsystem (`src/master_agent/verification/`)

**Constitutional Mandate (§10, RESEARCH-BACKED):** Structurally independent from Execution.

**Three-Part Boundary (§10.2):**
1. **Execution produces effects** — Worker's Action runs, returns Execution Result. Says nothing about real-world outcome.
2. **Verification produces Evidence** — Verification Subsystem re-observes Environment Instance, compares Observation against Expected Outcome (from Planner). Output: Verdict + Observation + Expected Outcome = **Evidence**.
3. **Evidence flows back to Brain** — routed via Shared Infrastructure as input to "is Mission complete?"

**Implementation:** **IMPLEMENTED** — `Verifier` ABC + `evaluate_checks()` + `Evidence` dataclasses

**Core Types (`evidence.py`):**
```python
class Verdict(str, Enum): MATCHED, NOT_MATCHED, PARTIALLY_MATCHED, ERROR
@dataclass class ObservationCheck: field, operator, value, description
@dataclass class ExpectedOutcome: description, checks: list[ObservationCheck]
@dataclass class Evidence: evidence_id, worker, environment, captured_at, expected, observation, verdict, check_results, errors
```

**Verifier Contract (`verifier.py`):**
```python
class Verifier(ABC):
    worker_name: str
    environment_name: str
    
    @abstractmethod
    def capture_observation_dict(self) -> dict[str, Any]: ...
    
    def verify(self, expected: ExpectedOutcome) -> Evidence:
        # Re-observes fresh, never trusts ExecutionResult
        # Builds Evidence record with verdict
```

**BrowserVerifier** (`plugins/browser_verifier.py`): Implements `capture_observation_dict()` using `normalize_observation()` — the only other function touching Playwright `Page` besides Actions.

**Runtime Integration:** `RuntimeEngine._verify()` calls `gateway.verify()` against task's `expected_outcome`. **Execution success ≠ verification success** — `NOT_MATCHED` verdict = failed task (ADR-0011).

### 4. Action Execution (`src/master_agent/executor/`)

#### LocalExecutor (`executor/executor.py` — MB002)
**Status:** **IMPLEMENTED** — Single execution path for all local capabilities

**Flow:** `LocalExecutor.execute(action_name, parameters)` →
1. Look up registered Action
2. `action.validate(parameters)` — must never touch filesystem or perform side effects
3. Check Permission System (Executor's own grant key, distinct from Orchestrator's)
4. `action.run(parameters)` → `ExecutionResult`
5. Catch exceptions (never raw traceback)
6. Log execution (action, start/end time, duration, status)

#### Action Contract (`executor/action.py`)
**Status:** **IMPLEMENTED** — Foundation every local capability plugs into

**Class Attributes (declared, not instantiated):**
```python
name: str
description: str
risk_tier: RiskTier
permission_category: PermissionCategory
expected_result: str
```

**Abstract Methods:**
- `required_parameters() -> list[str]` — documentation + contract
- `validate(parameters) -> list[str]` — pure check, no side effects
- `run(parameters) -> ExecutionResult` — structured failures, no exceptions for ordinary failures

**ExecutionResult:** `success`, `output`, `errors[]`, `warnings[]`, `execution_time_seconds` (set by Executor)

**Security (from `FILESYSTEM_CAPABILITIES.md` §6):**
- Path traversal: `is_unsafe_relative_path()` — checks both PurePosixPath and PureWindowsPath (MB023.1)
- Invalid paths: empty/whitespace rejected in `validate()`
- Overwrite protection: refuse to clobber unless `overwrite: true`
- Sandboxing: all paths resolved against configured location roots (`default_locations()`)

**Composite Actions:** `WorkspaceBootstrapAction` orchestrates primitives through same `LocalExecutor.execute()` — every sub-step independently validated, permission-gated, logged. No rollback on partial failure (deliberate, ADR-0006).

### 5. Permission Boundaries

#### Permission System (Shared Infrastructure §5.2)
**Status:** **IMPLEMENTED** — Single grant ledger across all Operator Instances

**Risk Tiers:** `READ_ONLY` (short-circuits unconditionally), `REVERSIBLE_WRITE`, `IRREVERSIBLE`

**Grant Scopes:** `ONCE`, `THIS_SESSION`, `ALWAYS_FOR_CAPABILITY`

**Critical Rule (ADR-0009):** `ALWAYS_FOR_CAPABILITY` grant **never satisfies** an `IRREVERSIBLE` check — destructive actions require fresh decision every time.

**Relay Pattern (ADR-0005, ADR-0006):** Outer approval explicitly carried down to inner grant key. Plugin adapter relays already-obtained approval to Executor's key without asking human twice.

#### Runtime ApprovalGate (MB028.0, ADR-0019)
**Status:** **IMPLEMENTED** — `src/master_agent/runtime/approval.py`

**Protocol (defined inside `runtime/`):** `ApprovalGate.check(request) -> None | raises ApprovalPending | ApprovalDenied`

**Properties:**
1. **One funnel** — `_handle_task()` only place reaching gateway; AST test fails if second `gateway.invoke()` site appears
2. **No Runtime dependency** — `ApprovalGate` protocol inside `runtime/`; `PermissionSystemGate` adapter typed against protocols
3. **Fail closed** — No gate ⇒ nothing runs (not even `READ_ONLY`)

**Three Outcomes:**
- `Authorised` → execute
- `ApprovalPending` → hold task, re-offer next cycle (task invisible to `_dispatch()`)
- `ApprovalDenied` → fail, never retry

**Evidence outlives process; authority does not** — decisions published to Audit Stream; grant ledger stays in memory (restart re-asks).

### 6. Environment Interaction

#### Environment Philosophy (Constitution §7, EVOLVABLE)
- **Local-First Is Not Optional** — system boots, plans, executes with purely local Reasoning Provider and Memory
- **Environment as Abstract Category** — Desktop, Browser, Terminal, VPS, Robotics/IoT — never a specific product
- **No Environment Assumptions in Core** — locations injected via configuration (§5.5), no product-specific logic, no process lifetime assumptions
- **Environment vs. Environment Instance** — "Environment" = category; "Environment Instance" = concrete live target (§7.4, §8.3)

#### Environment Session (Constitution §8.3)
- **Environment Instance** — concrete, addressable target (this specific desktop, browser tab, VPS)
- **Environment Session** — live handle Operator Instance holds to one Environment Instance
- **Owned by exactly one Operator Instance** — never Shared Infrastructure (§5.8)
- **Browser Implementation:** `BrowserSessionManager` (one per Operator Instance) → `BrowserSession` (Playwright instance, Browser, BrowserContext, Page)

#### Thread Affinity (Runtime §5.1)
**Critical Constraint:** Browser Environment Session must be used from thread that created it (Playwright sync API binds to per-thread event loop). Every interaction (open, load, close) must happen **inside a task**, on Runtime's thread. Objective must open session, do work, close session as tasks. Not solved by thread-marshalling layer — deliberate (no current need, would put Environment knowledge in Runtime).

### 7. Mission Coordination

#### Mission Control (MB023, `MISSION_CONTROL_ARCHITECTURE.md`)
**Status:** **IMPLEMENTED** — Runtime coordination layer, **performs no work**

**Components:**
- **Universal Event Bus** — single `Event` schema (event_id, type, occurred_at, source, objective_id, task_id, capability, payload, error). Synchronous, in-process.
- **Executive Registry** — tracks live Executives (capabilities, health, current task). Coordination catalogue (descriptors), not execution lookup.
- **Capability Registry** — descriptors (names, versions, owners, health, dependencies). Populated by adapter reading Plugin manifests.
- **Task Dispatcher** — `Objective` → `Task`s (qualified capability + optional `depends_on`). Computes ready tasks, resolves to healthy Executive, marks `DISPATCHED`. Failed dependency → `BLOCKED` (never silently skipped, never auto-retried).
- **Worker Lifecycle** — 9 states: `CREATED → INITIALIZED → READY → RUNNING → {WAITING, COMPLETED, FAILED} → ... → STOPPED`
- **Self-Development Queue** — 5 categories, state machine `PROPOSED → ACCEPTED → IN_PROGRESS → DONE | REJECTED`
- **Knowledge Acquisition Queue** — 7-stage pipeline `NEED → RESEARCH → SOURCE_COLLECTION → COMPARISON → VERIFICATION → KNOWLEDGE_STORAGE → CAPABILITY_CREATION`. Promotion gate (`VERIFICATION → KNOWLEDGE_STORAGE`) requires explicit `human_approved=True`.
- **Founder State** — `MissionControl.founder_state()` → snapshot (objective, mission, executive, capability, progress, evidence, errors, ETA, waiting approval, learning progress). ETA honest or absent.
- **Audit Stream** — subscribes to Event Bus, records every event as immutable `AuditEntry`. Append-only. Distinct from per-Worker `verification/audit.py`.

**Registration Adapter:** `register_plugin_as_executive()` reads Plugin manifest — `BrowserPlugin` and `FilesystemPlugin` register unchanged.

#### Runtime Engine (MB024, `RUNTIME_ENGINE_ARCHITECTURE.md`)
**Status:** **IMPLEMENTED** — Heartbeat loop: observe → dispatch → execute → verify → report → idle → repeat

**ExecutiveGateway Protocol:** `invoke(capability, payload)`, `verify(...)` — zero Executive knowledge. Runtime holds gateways keyed by Executive ID, resolves from Mission Control assignment.

**Mechanical Retry Only (Constitution §4.1 vs §11):**
- Same task, same capability, same payload, bounded attempts, fixed delay
- Never alters payload, substitutes capability, re-plans, reorders
- Exhausted → escalate (`TASK_ESCALATED`) to Mission Control
- Mission Control never sees retry (told `task_failed` once after final attempt)

**8-State Machine:** `INITIALIZING → IDLE | STOPPING | STOPPED`, `IDLE → DISPATCHING | STOPPING`, `DISPATCHING → WAITING | VERIFYING | IDLE | RECOVERING | STOPPING`, `WAITING → VERIFYING | RECOVERING | IDLE | STOPPING`, `VERIFYING → IDLE | RECOVERING | STOPPING`, `RECOVERING → DISPATCHING | IDLE | STOPPING`, `STOPPING → STOPPED`, `STOPPED` (terminal)

**Concurrency:** `max_concurrent_tasks` (default 1) caps work-in-flight. Sequential within cycle (honest, not oversight). Thread-affine Environment Sessions.

#### Persistence (MB025, `PERSISTENCE_ARCHITECTURE.md`)
**Status:** **IMPLEMENTED** — Operational memory, survives kill, resumes where stopped

**Two Mechanisms:**
- Append-only event log (`events.jsonl`) — written as events happen
- Versioned, checksummed snapshot (`snapshot.json`) — written on checkpoint

**Recovery:** `recovery.recover()` — single call launcher makes.

**Four Boundaries (enforced by tests):**
1. Persistence never executes
2. Mission Control never writes files
3. Runtime never performs storage (calls `CheckpointSink` protocol)
4. Contracts only (AST test rejects private-attribute access on non-`self`)

**Interrupted tasks quarantined, never re-run** — unknown side effects → `FAILED`, dependents `BLOCKED`, visible in Founder State.

---

## Execution Flow

Supported by sources (Constitution §1 Loop + Runtime Engine + Mission Control):

```
Intent (Brain §3.1)
    ↓
Plan (Planner §3.2 → MissionPlan with Steps + ExpectedOutcomes)
    ↓
Dispatch (Mission Control Dispatcher → Task with capability, payload, expected_outcome, assigned_executive)
    ↓
Execute (Runtime Engine → ExecutiveGateway.invoke() → Plugin.invoke() / LocalExecutor.execute())
    ↓
Verify (Runtime Engine → ExecutiveGateway.verify() → Verifier.verify() → Evidence)
    ↓
Report (Runtime Engine → Mission Control task_completed/failed + Event Bus → Founder State / Audit Stream)
    ↓
Learn (Memory persists MissionRecord automatically at terminal states — Rule 7)
```

**Key Distinctions from Prior Architecture:**
- Orchestrator no longer walks plan — Mission Control Dispatcher + Runtime own execution order
- Verification is separate step, not folded into execution
- Approval boundary at Runtime funnel, not Orchestrator
- Retry is mechanical (Runtime), strategic recovery is Brain's (Constitution §11)

---

## Worker / Plugin Model

### Capability Resolution
1. **Shared Infrastructure Capability Registry** — execution-time lookup: "which Plugin object services this capability right now" (§5.1)
2. **Mission Control Capability Registry** — coordination catalogue: "what capabilities exist, at what version, provided by which Executive, health" (§4)

### Worker Registration
- `Plugin` implements `manifest` (name, version, capabilities[])
- `register_plugin_as_executive()` reads manifest → populates Mission Control's Executive Registry
- No modification to existing Executives required (MB023 acceptance criterion)

### Capability Contract (Rule 3)
> "Every capability is a Worker behind the Capability Registry. Adding capability #N costs one new file, never an edit to the Registry, Orchestrator, Permission System, or Worker Runtime."

**Implemented via:**
- `FilesystemPlugin`: declarative registration from Action class tuple
- `BrowserWorker`: 9 Action classes + `BrowserPlugin` manifest
- New Executive: implements `Plugin` contract → registers via same adapter

### Composite Workers (Rule 6)
> "A Worker that orchestrates other Workers does so only through the Capability Registry and Permission System, relaying its own already-obtained grant down to each sub-step."

**Implemented:** `WorkspaceBootstrapAction` → `LocalExecutor.execute()` for sub-steps. `BrowserWorker` sequences Execute → Verify → Audit.

---

## Environment Independence (Constitution §13, FROZEN)

- No hardcoded Environment assumptions: all locations injected via configuration (§5.5)
- No product-specific logic in core modules
- No assumption about process lifetime baked into core

**Implemented via:**
- `default_locations()` — configurable roots (desktop, downloads, documents)
- `BrowserSessionManager._launch()` — single private function for engine choice
- `ExecutiveGateway` protocol — zero Executive knowledge in Runtime
- `ProviderSelector` protocol — zero provider knowledge in Model Router

---

## Security and Permission Model

### Layered Defense
1. **Action.validate()** — pure check, no filesystem/permission touch
2. **Orchestrator** — `PermissionSystem.check(plugin, capability, risk_tier)` before invoke
3. **LocalExecutor** — own grant key check (relayed approval from Orchestrator via ADR-0005)
4. **Runtime ApprovalGate** — `check(request)` at single funnel `_handle_task()`, fail closed

### Risk Tier Enforcement
- `READ_ONLY` — never prompts, short-circuits in `PermissionSystem.check()`
- `REVERSIBLE_WRITE` — `ONCE`/`THIS_SESSION`/`ALWAYS_FOR_CAPABILITY` grants apply
- `IRREVERSIBLE` — `ALWAYS_FOR_CAPABILITY` **never satisfies**; fresh decision every time

### Sandboxing
- All paths relative to configured roots (`default_locations()`)
- `is_unsafe_relative_path()` rejects absolute paths and `..` traversal (both POSIX/Windows)
- Overwrite protection unless explicit `overwrite: true`
- `DeleteFolderAction` refuses empty/`"."` path

### Transparency (Constitution §15.4)
- Every execution logged (LocalExecutor._log)
- Every Mission recorded (Memory auto-persist at terminal states)
- Evidence available, not hidden
- No Reasoning Provider call without named Capability

---

## Recovery Responsibilities

### Orchestrator (§4.1, Constitution §4.1)
- Retry/failure-branching policy: bounded, deterministic, scoped to this Operator Instance
- Never re-plans

### Runtime Engine (§11.1, `RUNTIME_ENGINE_ARCHITECTURE.md`)
- Mechanical retry only (same task, same payload, bounded attempts)
- Escalates to Mission Control after exhaustion (`TASK_ESCALATED`)
- Never decides what happens next — that is Brain's (Constitution §11)

### Mission Control (`MISSION_CONTROL_ARCHITECTURE.md` §7)
- Task whose dependency failed → `BLOCKED`, never silently skipped, never auto-retried
- Auto-retry would be strategic recovery → forbidden
- Blocked tasks surfaced in Founder State

### Persistence (MB025, `PERSISTENCE_ARCHITECTURE.md`)
- Interrupted tasks quarantined, never re-run (unknown side effects)
- Returns as `FAILED`, dependents `BLOCKED`
- Re-running = strategic judgement for Brain (Constitution §11)

### Named Gap (Constitution §11.4, `FOUNDER_CONSTITUTION_FREEZE.md` §3.1)
**In-mission recovery decision procedure** — exact rule for when Orchestrator's retry absorbs failure vs escalates to re-plan vs surfaces to human. **Not a blocker** — nothing on `ROADMAP.md` depends on it.

---

## Current Implementation Status

| Component | Constitution Status | Implementation Status | Notes |
|-----------|---------------------|----------------------|-------|
| **Orchestrator** | FROZEN (§4.1) | **IMPLEMENTED** | Sequential walk for demo; mission path = Mission Control + Runtime |
| **Worker Runtime** | FROZEN (§12) | **IMPLEMENTED** | Plugin ABC, PluginRegistry, declarative registration |
| **Filesystem Plugin** | FROZEN (Capability Contract) | **IMPLEMENTED** | 14 capabilities, all Actions, declarative registration |
| **Browser Worker** | FROZEN (Reference impl) | **IMPLEMENTED** | 9 Actions, Environment Session Manager, generic verification |
| **Verification Subsystem** | RESEARCH-BACKED (§10) | **IMPLEMENTED** | Verifier ABC, Evidence, Evaluator, BrowserVerifier |
| **LocalExecutor / Action Contract** | FROZEN (MB002) | **IMPLEMENTED** | Single path, validation, permission relay, logging |
| **Permission System** | FROZEN (§5.2) | **IMPLEMENTED** | Risk tiers, categories, grant scopes, IRREVERSIBLE rule |
| **Runtime ApprovalGate** | FROZEN (MB028.0/ADR-0019) | **IMPLEMENTED** | Protocol in runtime/, fail-closed, three outcomes |
| **Mission Control** | FROZEN (MB023) | **IMPLEMENTED** | Event Bus, Registries, Dispatcher, Queues, Founder State, Audit |
| **Runtime Engine** | FROZEN (MB024) | **IMPLEMENTED** | 8-state loop, ExecutiveGateway, mechanical retry, checkpointing |
| **Persistence** | FROZEN (MB025) | **IMPLEMENTED** | Event log + snapshot, recovery, quarantined tasks |
| **AI Infrastructure Executive** | RESEARCH-BACKED (§5.7) | **NOT IMPLEMENTED** | Machine-touching counterpart to Broker (scans, probes, benchmarks) |
| **Reporter** | FROZEN (§3.4) | **NOT IMPLEMENTED** | cli.py completion messages stand in |

### Design vs Implementation Differences
| Area | Constitution Design | Current Implementation | Status |
|------|---------------------|------------------------|--------|
| **Orchestrator role** | Walks MissionPlan, triggers Verification | Sequential walk for demo; Verification = Runtime | ✅ Aligned (MB037 clarified) |
| **Execution order** | Orchestrator applies retry/branching | Dispatcher orders by dependency; Runtime executes | ✅ Aligned (Mission Control owns order) |
| **Approval boundary** | Permission System consulted before invoke | Orchestrator checks; Runtime has separate ApprovalGate | ⚠️ Two gates (ADR-0005 relay + MB028.0) |
| **Verification trigger** | Orchestrator triggers | Runtime calls `gateway.verify()` | ✅ Aligned (structurally independent) |
| **Composite execution** | Worker orchestrates via Registry | WorkspaceBootstrapAction uses LocalExecutor directly | ✅ Aligned (relay pattern) |

---

## Open Questions

1. **In-mission recovery decision procedure** (Constitution §11.4) — exact escalation rules unspecified. Not a blocker for current `ROADMAP.md`.

2. **Stateful Environment Sessions in Action contract** (Constitution §8.3, §12) — today's Action is one-shot (`validate()` → `run()`); Browser/Terminal/Robotics need live handle across multiple Steps. Not a blocker — no current Worker needs this.

3. **Concurrent dispatch across Operator Instances** (Constitution §8.5) — deliberately left EVOLVABLE per instruction not to design distributed system.

4. **AI Infrastructure Executive not implemented** — machine-touching counterpart to Broker (scans, probes, benchmarks, installs). Required for Broker's inventory freshness.

5. **CapabilityManifest.input_schema/output_schema empty** — declared in frozen `plugins/base.py`, populated by nothing. Planner guesses payload names (MB036 Finding 4, MB037 Finding 3). Top backlog item.

6. **Thread-affine Environment Sessions** — Browser Session must be used from creating thread. Objectives must open/close session as tasks. Not solved by marshalling layer (deliberate).

7. **Pause/resume/cancel** — needs ratified ADR (MB037 §5). `test_missions_lifecycle.py` fails if added without ADR.

---

## Future Extraction Targets

1. `src/master_agent/missions/` — `translation.py`, `service.py`, `history.py` (MB037 wiring)
2. `src/master_agent/runtime/approval.py` — `ApprovalGate`, `ApprovalRequest`, `ApprovalPending`, `ApprovalDenied`
3. `src/master_agent/runtime/gateway.py` — `ExecutiveGateway`, `PluginGateway`, `GatewayResult`
4. `src/master_agent/mission_control/` — full coordination layer implementation
5. `src/master_agent/persistence/` — event log, snapshot, recovery implementation
6. `src/master_agent/ai_infrastructure/` — AI Infrastructure Executive (when implemented)
7. `src/master_agent/plugins/filesystem_plugin.py` — full capability registration
8. `src/master_agent/plugins/browser_*.py` — BrowserPlugin, BrowserWorker, BrowserVerifier
9. `tests/test_runtime_architecture.py` — import-parsing guards
10. `tests/test_mission_control_architecture.py` — purity guards

---

## Wiki Links Added

- `[[KALPAVRIKSHA_VISION_V2.md]]` — Constitution source
- `[[FOUNDER_CONSTITUTION_FREEZE.md]]` — freeze record, amendments
- `[[ARCHITECTURE.md]]` — implementation map
- `[[RUNTIME_ENGINE_ARCHITECTURE.md]]` — heartbeat loop design
- `[[MISSION_CONTROL_ARCHITECTURE.md]]` — coordination layer design
- `[[BROWSER_WORKER_ARCHITECTURE.md]]` — reference Worker implementation
- `[[FILESYSTEM_CAPABILITIES.md]]` — Action Contract pattern
- `[[MEMORY_ARCHITECTURE.md]]` — six-layer memory
- `[[01_executive_brain.md]]` — Brain layer documentation
- `[[02_constitution.md]]` — Constitution summary
- `[[system_overview.md]]` — system overview
- `[[docs/adr/0005]]`–`[[docs/adr/0006]]` — permission relay pattern
- `[[docs/adr/0009]]` — PermissionCategory + IRREVERSIBLE rule
- `[[docs/adr/0010]]` — Shared Infrastructure layer
- `[[docs/adr/0011]]` — Verification independent subsystem
- `[[docs/adr/0013]]` — Multi-Operator architecture
- `[[docs/adr/0015]]` — Persistence strategy (Proposed)
- `[[docs/adr/0019]]` — Runtime approval boundary
- `[[docs/adr/0020]]` — Founder approval workflow (Proposed)

---

*Document created from verified sources only. No implementation details invented. Terminology preserved exactly. Design/implementation differences recorded without reconciliation.*