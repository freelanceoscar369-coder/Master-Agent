# Runtime Engine

## Purpose
Documents the autonomous execution heartbeat that replaces the human in the Kalpavriksha loop — observing what is ready, dispatching it, executing through a gateway, invoking Verification, reporting back, and repeating. Per `RUNTIME_ENGINE_ARCHITECTURE.md` (Mission Brief 024) and Constitution §4, §11.

## Constitutional Role

### Constitution §4.1 (Operator Responsibilities)
> **Orchestrator** walks a `MissionPlan`, and for each `Step`:
> 1. Resolves Capability → Worker via Shared Infrastructure's Capability Registry
> 2. Checks Permission System via Shared Infrastructure
> 3. Invokes Worker, captures result
> 4. Triggers Verification (§10) against Step's Expected Outcome
> 5. Applies retry/failure-branching policy — bounded, deterministic, scoped to this Operator Instance; **never re-plans**

### Constitution §11 (Recovery Philosophy)
> **Mission-Level Recovery:** The `Mission` state machine (Shared Infrastructure, §5.3) enables precise recovery. A failed Verdict (§10.2) is the trigger for recovery — Evidence flows to the Brain; the Brain decides retry, re-plan, or surface to human.
> **System-Level Recovery:** Memory (Shared Infrastructure, §5.4) is the durable anchor and survives restart. Persistence is automatic.
> **No Silent Corruption:** Zero tolerance for silent data loss, drift, or gaps.

### Constitution Rule 4 (FROZEN)
> **Environment Access Has One Door.** No Brain module, no CLI code, touches an Environment directly. Everything goes through a Worker, via the Operator's Worker Runtime, via an Environment Session (§8.3) the Operator Instance owns.

### Constitution Rule 5 (FROZEN)
> **Permission System Has Veto Power, Now Mission-Wide.** Every capability declares a risk tier. The Permission System (Shared Infrastructure, §5.2) is consulted before any step above `READ_ONLY`, regardless of which Operator Instance executes it. An `ALWAYS_FOR_CAPABILITY` grant never satisfies an `IRREVERSIBLE` check.

---

## Runtime Responsibilities

From `RUNTIME_ENGINE_ARCHITECTURE.md`:

### What the Runtime Engine IS
- The loop that replaces the human in the cycle: **observe → dispatch → execute → verify → report → idle → repeat**
- Observes Mission Control for ready work
- Dispatches tasks to Executives via gateways
- Executes with mechanical retry only
- Invokes Verification through gateway
- Reports outcomes to Mission Control
- Handles approval boundary (MB028.0)
- Checkpoints state for recovery (MB025)

### What the Runtime Engine Does NOT Do (Deliberate)
- **Performs no work** — contains no work logic, holds no Environment access, has no Executive-specific knowledge
- **Knows no Executive** — routes by Executive ID Mission Control assigned; never imports, names, or queries a concrete Executive
- **Never re-plans, reorders, substitutes a capability, or edits a payload** — retry is mechanical only
- **Never computes a verdict** — asks gateway to verify and forwards result
- **Execution success ≠ verification success** — `NOT_MATCHED` verdict = failed task (ADR-0011)

---

## Execution Lifecycle: Runtime State Machine

From `RUNTIME_ENGINE_ARCHITECTURE.md` §3 and `src/master_agent/runtime/states.py`:

### 8 States
```text
INITIALIZING → IDLE | STOPPING | STOPPED
IDLE         → DISPATCHING | STOPPING          ← the resting state
DISPATCHING  → WAITING | VERIFYING | IDLE | RECOVERING | STOPPING
WAITING      → VERIFYING | RECOVERING | IDLE | STOPPING
VERIFYING    → IDLE | RECOVERING | STOPPING
RECOVERING   → DISPATCHING | IDLE | STOPPING
STOPPING     → STOPPED
STOPPED      → (terminal)
```

### State Descriptions
| State | Purpose |
|-------|---------|
| `INITIALIZING` | Startup, registering gateways, restoring checkpoint |
| `IDLE` | Healthy resting state — no work ready (not an error) |
| `DISPATCHING` | Asking Mission Control for ready tasks |
| `WAITING` | Task executing or held at approval boundary |
| `VERIFYING` | Gateway verifying task outcome |
| `RECOVERING` | Mechanical retry in progress (between attempts) |
| `STOPPING` | Graceful shutdown requested |
| `STOPPED` | Terminal — loop exited |

### Key Transitions
- `DISPATCHING → IDLE` exists for common case of poll finding nothing
- `IDLE` is where healthy Runtime spends most of its life
- `RECOVERING` only during mechanical retry between attempts

---

## Runtime Components

### 1. Runtime Loop (`RuntimeEngine._run_cycle()`)
**File:** `src/master_agent/runtime/engine.py`

**One Cycle:**
```text
observe    → ask Mission Control what is ready (never ask an Executive)
dispatch   → mission_control.dispatch_ready(); MC assigns an Executive
APPROVE    → consult the ApprovalGate. Refusal ends the task here
execute    → route each assigned task to its Executive's gateway
             (retry mechanically on failure, up to policy)
verify     → gateway.verify() against the task's ExpectedOutcome,
             producing Evidence
report     → task_started / verification_* / task_completed|failed
idle       → sleep for the poll interval
```

**Concurrency:** `max_concurrent_tasks` caps tasks per cycle (default 1). Within cycle: **sequential** execution (honest, not oversight — Constitution §8.5 leaves concurrent dispatch EVOLVABLE).

### 2. ExecutiveGateway Protocol
**File:** `src/master_agent/runtime/gateway.py`

```python
@runtime_checkable
class ExecutiveGateway(Protocol):
    def invoke(self, capability: str, payload: dict[str, Any]) -> GatewayResult: ...
    def verify(self, capability: str, payload: dict[str, Any], expected: ExpectedOutcome) -> Evidence | None: ...
```

**Properties:**
- Two methods, both Executive-agnostic
- Gateway implementation = where product knowledge lives; protocol has none
- `invoke()`: must not raise for ordinary failure → `GatewayResult(success=False, errors=[...])`
- `verify()`: produces Evidence by re-observing reality, or `None` if no Verifier. **Never derived from `invoke()` result** — maintains Execution/Verification distinction (ADR-0011)

**Runtime holds gateways** keyed by Executive ID, resolves from Mission Control assignment. Zero Executive knowledge.

### 3. PluginGateway
**File:** `src/master_agent/runtime/gateway.py`

```python
class PluginGateway:
    def __init__(self, plugin: Any, grant_permission: Any = None):
        # grant_permission: optional callable invoked with capability name
        # before each invocation — relays already-obtained approval down
        # to Executor's grant key (ADR-0005 pattern)
    
    def invoke(self, capability: str, payload: dict) -> GatewayResult:
        if self._grant_permission: self._grant_permission(capability)
        result = self._plugin.invoke(capability, payload)
        # maps Plugin.InvocationResult → GatewayResult
    
    def verify(self, ...) -> None:
        # Plugin contract has no verification surface
        # Returns None honestly — Runtime records no Evidence produced
```

**Generic:** serves Browser Executive, Filesystem Executive, and every future Executive implementing `Plugin` contract. No per-Executive gateway to write.

### 4. ApprovalGate (MB028.0, ADR-0019)
**File:** `src/master_agent/runtime/approval.py`

**Protocol (defined inside `runtime/` — no Permission System dependency):**
```python
@runtime_checkable
class ApprovalGate(Protocol):
    def check(self, request: ApprovalRequest) -> None: ...
```

**Three Outcomes:**
1. **Authorised** → execute
2. **ApprovalPending** → hold task, re-offer next cycle (task invisible to `_dispatch()`)
3. **ApprovalDenied** → fail, never retry

**Properties (each load-bearing):**
1. **One funnel** — `_handle_task()` only place reaching gateway; AST test fails if second `gateway.invoke()` site appears
2. **No Runtime dependency** — `ApprovalGate` protocol inside `runtime/`; `PermissionSystemGate` adapter typed against protocols
3. **Fail closed** — No gate ⇒ nothing runs (not even `READ_ONLY`)

**Evidence outlives process; authority does not** — decisions published to Audit Stream; grant ledger stays in memory (restart re-asks).

#### FounderApprovalGate (MB028.1)
Wraps `PermissionSystemGate`; adds third outcome: **ask the founder; the task waits**.
- `ApprovalPending` deliberately not subclass of `ApprovalDenied`
- Expiry evaluated on each cycle re-check (no separate timer)
- Approval consumed once — never reused (ADR-0009)

### 5. Retry System (Mechanical Only)
**File:** `src/master_agent/runtime/engine.py` → `_execute_with_retry()`

```text
Same task, same capability, same payload, bounded attempts, fixed delay.
Never alters payload, never substitutes capability, never re-plans, never reorders.
When attempts exhausted → escalate (TASK_ESCALATED) to Mission Control.
Mission Control never sees a retry — told task_failed once after final attempt.
```

**Configurable:**
- `max_attempts` (default 3)
- `retry_delay_seconds` (default 0.5, fixed not exponential)

**Constitution Alignment:** §4.1 puts bounded retry in Operator; §11 keeps strategic recovery with Brain. Runtime = mechanical; Brain = strategic.

### 6. Checkpoint System (MB025)
**File:** `src/master_agent/runtime/checkpoint.py` + `engine.py`

**Protocol (defined inside `runtime/` — no persistence dependency):**
```python
class CheckpointSink(Protocol):
    def save_checkpoint(self, snapshot: RuntimeCheckpoint) -> None: ...
    def load_checkpoint(self) -> RuntimeCheckpoint | None: ...
```

**RuntimeCheckpoint** captures: state, cycle, tasks_completed, tasks_failed, retries_performed, escalations, last_dispatch_at, last_verification_at.

**Restored on startup** via `recover()` → restores Mission Control + Runtime counters. Runtime state deliberately NOT restored to mid-cycle — always comes back through `INITIALIZING → IDLE` and re-observes Mission Control.

---

## Execution Flow

Supported by Constitution Loop + Runtime Engine + Mission Control:

```
Intent (Brain §3.1)
    ↓
Plan (Planner §3.2 → MissionPlan with Steps + ExpectedOutcomes)
    ↓
Dispatch (Mission Control Dispatcher → Task with capability, payload, expected_outcome, assigned_executive)
    ↓
APPROVE (Runtime ApprovalGate at single funnel _handle_task())
    ↓
Execute (Runtime → ExecutiveGateway.invoke() → PluginGateway → Plugin.invoke() / LocalExecutor.execute())
    ↓
Verify (Runtime → ExecutiveGateway.verify() → Verifier.verify() → Evidence)
    ↓
Report (Runtime → Mission Control task_completed/failed + Event Bus → Founder State / Audit Stream)
    ↓
Learn (Memory persists MissionRecord automatically at terminal states — Rule 7)
    ↓
Idle → repeat
```

---

## Failure Handling

### Approval Failure (`approval.py`)
- `ApprovalPending` → task held in `_awaiting_approval`, re-offered next cycle
- `ApprovalDenied` → task fails, **never retried** (retrying a refusal = asking same question repeatedly)
- No gate wired → **fail closed** (nothing runs)

### Execution Failure (`_execute_with_retry()`)
- Mechanical retry: identical task, bounded attempts, fixed delay
- Gateway exceptions caught → treated as failed attempt
- All attempts exhausted → `_escalate()` → `TASK_ESCALATED` event → Mission Control

### Verification Failure (`_verify()`)
- `Evidence.verdict != "matched"` → `_report_failure()` → task fails
- **Execution success ≠ verification success** — ADR-0011 distinction
- No Verifier → Evidence = None, recorded honestly (not treated as pass)

### Reporting Failure (`_report_failure()`)
- Calls `MissionControl.task_failed()` with error + evidence_id
- Reporting exceptions caught → `RUNTIME_ERROR` event (reporting must never take down loop)

### Recovery (`_recover()`)
- If in `RECOVERING` → go `IDLE` (recovered)
- Else transition to `RECOVERING` → go `IDLE`
- Runtime that dies on one bad cycle is not a heartbeat

---

## Recovery Philosophy

### Runtime Responsibilities (Constitution §11.1 + `RUNTIME_ENGINE_ARCHITECTURE.md`)
- Mechanical retry only (bounded, deterministic)
- Escalate to Mission Control after exhaustion
- **Never decides what happens next** — that is Brain's (Constitution §11)

### Mission Control Responsibilities (`MISSION_CONTROL_ARCHITECTURE.md` §7)
- Failed dependency → task `BLOCKED` (never silently skipped, never auto-retried)
- Blocked tasks surfaced in Founder State
- Auto-retry would be strategic recovery → forbidden

### Persistence Responsibilities (MB025, `PERSISTENCE_ARCHITECTURE.md`)
- Interrupted tasks quarantined, never re-run (unknown side effects)
- Returns as `FAILED`, dependents `BLOCKED`, visible in Founder State
- Re-running = strategic judgement for Brain (Constitution §11)

### Named Gap (Constitution §11.4, `FOUNDER_CONSTITUTION_FREEZE.md` §3.1)
**In-mission recovery decision procedure** — exact rule for when Orchestrator's retry absorbs failure vs escalates to re-plan vs surfaces to human. **Not a blocker** — nothing on `ROADMAP.md` depends on it.

---

## Persistence Relationship

### Two Systems, Separate Concerns (MB025 §4)
| Aspect | Memory (Layer 3) | Persistence (Operational) |
|--------|------------------|---------------------------|
| **Concern** | Mission history — queryable, indexed, long-lived | Operational state — small whole-object snapshot |
| **Storage** | SQLite (`~/.master_agent/memory.db`) | JSON (`snapshot.json` + `events.jsonl`) |
| **Read Pattern** | Planner reads for "have I done this before" | Read once at startup, never queried into |
| **Write** | Auto at terminal mission state (Rule 7) | Cycle end + shutdown (Runtime `CheckpointSink`) |

### Recovery Interaction
1. `recover()` detects existing state
2. Restores Mission Control (executives → capabilities → objectives → audit)
3. Restores Runtime counters
4. Interrupted tasks → quarantined as `FAILED` with error "interrupted by shutdown"
5. Dependents become `BLOCKED` — visible, not silently dropped
6. System ready to resume

### Boundaries (Test-Enforced)
1. Persistence never executes (no gateway, no Executive)
2. Mission Control never writes files (forbidden-import test)
3. Runtime never performs storage (calls `CheckpointSink` protocol)
4. Contracts only (AST test rejects private-attribute access)

---

## Thread Affinity and Environment Sessions

### Critical Constraint (`RUNTIME_ENGINE_ARCHITECTURE.md` §5.1)
> **Environment Sessions are thread-affine.** Every interaction with a live session must happen inside a task, on the Runtime's thread.

**Playwright sync API binds to per-thread event loop** — opening session on one thread and acting from Runtime's thread raises "Sync API inside the asyncio loop."

### Consequences
- Every interaction (open, load, close) must happen **inside a task** on Runtime's thread
- Objective must open session, do work, close session as tasks
- Not solved by thread-marshalling layer — deliberate (no current need, would put Environment knowledge in Runtime)
- Future Executive with thread-safe environment has no such restriction
- Runtime holds no session state itself (Rule 2)

---

## Current Implementation Status

| Component | Constitution/Architecture | Implementation Status | Notes |
|-----------|---------------------------|----------------------|-------|
| **Runtime Loop** | `RUNTIME_ENGINE_ARCHITECTURE.md` §3–4 | ✅ **IMPLEMENTED** | 8-state machine, `_run_cycle()`, `_dispatch()`, `_handle_task()` |
| **ExecutiveGateway** | Protocol in `gateway.py` | ✅ **IMPLEMENTED** | `invoke()` + `verify()` |
| **PluginGateway** | Generic gateway in `gateway.py` | ✅ **IMPLEMENTED** | Works for any `Plugin`; `grant_permission` relay |
| **BrowserGateway** | Executive with Verifier | ✅ **IMPLEMENTED** | Pairs `PluginGateway` + `BrowserVerifier` (test support) |
| **ApprovalGate** | MB028.0/ADR-0019 | ✅ **IMPLEMENTED** | Protocol in `runtime/`; `PermissionSystemGate` + `FounderApprovalGate` |
| **Retry System** | Mechanical only (§4.1 vs §11) | ✅ **IMPLEMENTED** | `_execute_with_retry()` — bounded, fixed delay |
| **Checkpoint System** | MB025 `CheckpointSink` | ✅ **IMPLEMENTED** | `RuntimeCheckpoint` + `CheckpointSink` protocol |
| **Persistence** | MB025 `recovery.recover()` | ✅ **IMPLEMENTED** | Event log + snapshot; quarantines interrupted tasks |
| **Thread Affinity** | §5.1 documented constraint | ✅ **ACKNOWLEDGED** | Browser sessions must be used on creating thread |
| **Health Monitoring** | `RuntimeHealth` 7 fields | ✅ **IMPLEMENTED** | Derived from Mission Control (no shadow copy) |

### Implementation Files
- `src/master_agent/runtime/engine.py` — `RuntimeEngine` (597 lines)
- `src/master_agent/runtime/approval.py` — `ApprovalGate`, `PermissionSystemGate`, `FounderApprovalGate` (360 lines)
- `src/master_agent/runtime/gateway.py` — `ExecutiveGateway`, `PluginGateway`, `GatewayResult` (116 lines)
- `src/master_agent/runtime/checkpoint.py` — `RuntimeCheckpoint`, `CheckpointSink`
- `src/master_agent/runtime/config.py` — `RuntimeConfig`
- `src/master_agent/runtime/states.py` — `RuntimeState`, `assert_transition`
- `src/master_agent/runtime/health.py` — `RuntimeHealth`

---

## Design vs Implementation Differences

| Area | Design (Architecture/Constitution) | Implementation | Status |
|------|-----------------------------------|----------------|--------|
| **Orchestrator role** | Walks MissionPlan, triggers Verification | Sequential for demo; Verification = Runtime | ✅ Aligned via MB037 |
| **Execution order** | Orchestrator applies retry/branching | Dispatcher orders by dependency; Runtime executes | ✅ Aligned |
| **Approval boundary** | Permission System before invoke | Orchestrator checks; Runtime has separate ApprovalGate | ⚠️ Two gates (ADR-0005 relay + MB028.0) |
| **Verification trigger** | Orchestrator triggers | Runtime calls `gateway.verify()` | ✅ Aligned (independent) |
| **Retry visibility** | Orchestrator owns retry | Runtime mechanical retry; Mission Control never sees retry | ✅ Aligned |
| **Environment Sessions** | Abstract category (Constitution §7) | BrowserSessionManager thread-affine | ⚠️ Constraint documented |
| **Composite execution** | Worker orchestrates via Registry | WorkspaceBootstrapAction uses LocalExecutor directly | ✅ Aligned (relay pattern) |

---

## Open Questions

1. **In-mission recovery decision procedure** (Constitution §11.4) — exact escalation rules unspecified. Not a blocker for current `ROADMAP.md`.

2. **Stateful Environment Sessions in Action contract** (Constitution §8.3, §12) — today's Action is one-shot (`validate()` → `run()`); Browser/Terminal/Robotics need live handle across multiple Steps. Not a blocker.

3. **Concurrent dispatch across Operator Instances** (Constitution §8.5) — deliberately left EVOLVABLE per instruction not to design distributed system.

4. **Thread-affine Environment Sessions** — Browser Session must be used from creating thread. Objectives must open/close session as tasks. Not solved by marshalling layer (deliberate).

5. **Pause/resume/cancel** — needs ratified ADR (MB037 §5). `test_missions_lifecycle.py` fails if added without ADR.

6. **Event Bus synchronous/in-process** — named as future revisiting point for multi-process deployment (`MISSION_CONTROL_ARCHITECTURE.md` §12).

7. **Audit Stream unbounded in-memory** — same debt as `LocalExecutor._log` (MB023). Not solved differently here.

---

## Future Extraction Targets

1. `src/master_agent/runtime/engine.py` — Full `RuntimeEngine` implementation
2. `src/master_agent/runtime/approval.py` — `ApprovalGate`, `PermissionSystemGate`, `FounderApprovalGate`
3. `src/master_agent/runtime/gateway.py` — `ExecutiveGateway`, `PluginGateway`
4. `src/master_agent/runtime/checkpoint.py` — `RuntimeCheckpoint`, `CheckpointSink`
5. `src/master_agent/runtime/config.py` — `RuntimeConfig` defaults
6. `src/master_agent/runtime/states.py` — `RuntimeState`, `assert_transition`
7. `src/master_agent/runtime/health.py` — `RuntimeHealth`
8. `tests/test_runtime_architecture.py` — Import-parsing purity test
9. `tests/runtime_test_support.py` — Browser gateway example (pairs PluginGateway + Verifier)
10. `docs/adr/0019` — Runtime approval boundary decision record

---

## Wiki Links Added

- `[[KALPAVRIKSHA_VISION_V2.md]]` — Constitution §4, §11, Rule 4, Rule 5
- `[[FOUNDER_CONSTITUTION_FREEZE.md]]` — Freeze record, named gaps
- `[[RUNTIME_ENGINE_ARCHITECTURE.md]]` — Primary source document
- `[[ARCHITECTURE.md]]` — Implementation map §4.1, §5
- `[[MISSION_CONTROL_ARCHITECTURE.md]]` — Dispatcher, Founder State, Audit Stream
- `[[PERSISTENCE_ARCHITECTURE.md]]` — Event log + snapshot, recovery
- `[[01_executive_brain.md]]` — Brain (strategic recovery owner)
- `[[02_constitution.md]]` — Constitution summary
- `[[03_universal_executive_operator.md]]` — Operator layer (Orchestrator, Verification)
- `[[04_shared_infrastructure.md]]` — Shared Infrastructure (Permission System, Mission State, Memory)
- `[[05_memory_system.md]]` — Memory (durable anchor, auto-persist)
- `[[system_overview.md]]` — System overview
- `[[docs/adr/0005]]`–`[[docs/adr/0006]]` — Permission relay pattern
- `[[docs/adr/0009]]` — PermissionCategory + IRREVERSIBLE rule
- `[[docs/adr/0010]]` — Shared Infrastructure layer
- `[[docs/adr/0011]]` — Verification independent subsystem
- `[[docs/adr/0015]]` — Persistence strategy (Proposed)
- `[[docs/adr/0019]]` — Runtime approval boundary
- `[[docs/adr/0020]]` — Founder approval workflow (Proposed)

---

*Document created from verified sources only. No runtime capabilities invented. Terminology preserved exactly. Constitution/Architecture/Implementation separated. Gaps recorded without reconciliation.*