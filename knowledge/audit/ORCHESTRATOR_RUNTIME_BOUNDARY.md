# Orchestrator & Runtime Boundary Audit

## Source
- Architecture: `KALPAVRIKSHA_VISION_V2.md` §4.1, §11, `RUNTIME_ENGINE_ARCHITECTURE.md`, `MISSION_CONTROL_ARCHITECTURE.md`
- Implementation: `src/master_agent/orchestrator/orchestrator.py`, `src/master_agent/runtime/engine.py`, `src/master_agent/mission_control/mission_control.py`

## Classification Legend
- **A** = Implementation Bug
- **B** = Missing Implementation Required by Frozen Architecture
- **C** = Founder Edition Limitation
- **D** = Future Evolution / Scalability Item
- **E** = Requires ADR Decision
- **F** = Documentation Gap

---

## 1. Orchestrator Architecture (§4.1, FROZEN)

### Constitutional Definition
> **Orchestrator** walks a `MissionPlan`, and for each `Step`:
> 1. Resolves Capability → Worker via Shared Infrastructure's Capability Registry
> 2. Checks Permission System via Shared Infrastructure
> 3. Invokes the Worker, captures the result
> 4. Triggers Verification (§10) against Step's Expected Outcome
> 5. Applies retry/failure-branching policy — bounded, deterministic, scoped to this Operator Instance; never re-plans

---

## 2. Current Implementation (`src/master_agent/orchestrator/orchestrator.py`)

```python
class Orchestrator:
    def __init__(self, registry: PluginRegistry, permissions: PermissionSystem):
        self._registry = registry
        self._permissions = permissions

    def execute_capability(self, capability: str, payload: dict, step_id: str = "") -> StepResult:
        candidates = self._registry.find_for_capability(capability)
        if not candidates:
            return StepResult(step_id=step_id or capability, result=InvocationResult(success=False, error=f"no plugin for capability {capability}"))
        plugin = candidates[0]  # Founder Edition: take first candidate
        risk_tier = self._registry.risk_tier_for(plugin.manifest.name, capability)
        try:
            self._permissions.check(plugin.manifest.name, capability, risk_tier)
        except ApprovalRequired:
            return StepResult(step_id=step_id or capability, result=None, blocked_on_approval=True)
        result = plugin.invoke(capability, payload)
        return StepResult(step_id=step_id or capability, result=result)

    def execute_step(self, step: Step) -> StepResult:
        return self.execute_capability(step.capability, step.payload, step_id=step.step_id)

    def execute_plan(self, plan: MissionPlan) -> list[StepResult]:
        """Sequential execution in declared order. NOT the mission path since MB037."""
        results = []
        for step in plan.steps:
            step_result = self.execute_step(step)
            results.append(step_result)
            if step_result.blocked_on_approval or (step_result.result and not step_result.result.success):
                break
        return results
```

---

## 3. Orchestrator vs Constitution §4.1 — Gap Analysis

| Constitutional Requirement | Implementation | Status |
|---------------------------|----------------|--------|
| 1. Resolves Capability → Worker via Capability Registry | ✅ `find_for_capability()` | ✅ Compliant |
| 2. Checks Permission System via Shared Infrastructure | ✅ `PermissionSystem.check()` | ✅ Compliant |
| 3. Invokes Worker, captures result | ✅ `plugin.invoke()` | ✅ Compliant |
| 4. **Triggers Verification against Expected Outcome** | ❌ **NOT IMPLEMENTED** | **A** — Implementation Bug |
| 5. Applies retry/failure-branching policy | ⚠️ Partial — sequential, stops on first failure | ⚠️ Partial |

### Critical Gap: Verification Not Triggered
**Constitution §4.1 Step 4**: "Triggers Verification (§10) against Step's Expected Outcome"

**Implementation**: `execute_capability()` and `execute_step()` do **NOT** call any verification. They return `StepResult` with `InvocationResult` only.

**Where Verification Happens**: `RuntimeEngine._verify()` in `runtime/engine.py` (MB024), not in Orchestrator.

**Classification**: **A** — Implementation Bug (Orchestrator violates §4.1)

---

## 4. Runtime Engine Architecture (MB024, FROZEN)

### Constitutional Definition
> The Runtime Engine is the loop that replaces the founder in the cycle: observe → dispatch → execute → verify → report → idle → repeat.

### Implementation (`src/master_agent/runtime/engine.py`)

**Runtime Responsibilities:**
- Observes Mission Control for ready tasks
- Dispatches via `mission_control.dispatch_ready()`
- Consults `ApprovalGate` at single funnel `_handle_task()`
- Executes via `ExecutiveGateway.invoke()`
- **Verifies via `ExecutiveGateway.verify()`** → produces Evidence
- Reports to Mission Control

**Verification in Runtime** (`_verify()` method):
```python
def _verify(self, gateway, task, local_capability) -> Evidence | None:
    expected = task.expected_outcome
    if expected is None or not self._config.verify_when_expected_outcome_present:
        return None
    self._transition(RuntimeState.VERIFYING)
    evidence = gateway.verify(local_capability, dict(task.payload), expected)
    # ...
    if evidence is not None and evidence.verdict.value != "matched":
        self._report_failure(task, f"verification verdict was '{evidence.verdict.value}'", evidence_id=evidence.evidence_id)
        return evidence
```

---

## 5. Boundary Analysis: Orchestrator vs Runtime

### Constitutional Split

| Layer | Responsibility | Implementation |
|-------|----------------|----------------|
| **Orchestrator** (§4.1) | Walks MissionPlan, resolves Capability→Worker, checks Permission, invokes Worker, **triggers Verification**, applies retry policy | `orchestrator/orchestrator.py` |
| **Runtime Engine** (MB024) | Observe → Dispatch → Execute → **Verify** → Report → Idle → Repeat | `runtime/engine.py` |
| **Mission Control** (MB023) | Dispatches Tasks, manages queues, emits Events, tracks state | `mission_control/` |

### Actual Implementation Split

| Function | Constitution Owner | Actual Implementation |
|----------|-------------------|----------------------|
| Walk MissionPlan | Orchestrator | **Runtime** (via Mission Control dispatch) |
| Capability Resolution | Orchestrator | Orchestrator ✅ |
| Permission Check | Orchestrator | Orchestrator ✅ |
| Worker Invocation | Orchestrator | Runtime (via Gateway) |
| **Verification Trigger** | **Orchestrator** | **Runtime** ❌ |
| Retry Policy | Orchestrator | Runtime (mechanical) |
| Failure Branching | Orchestrator | Runtime (escalation) |
| Execution Order | Orchestrator | Mission Control Dispatcher |

---

## 6. Boundary Violations

### Violation 1: Verification Not in Orchestrator
**Constitution §4.1**: "Triggers Verification (§10) against Step's Expected Outcome"
**Implementation**: Runtime `_verify()` does it
**Classification**: **A** — Implementation Bug

### Violation 2: Orchestrator `execute_plan()` Is Legacy Path
**Code Comment** (`orchestrator.py` line 66-73):
> "**Not the mission path.** Since MB037 a founder objective is planned and submitted to Mission Control, whose Dispatcher orders by dependency and whose Runtime executes and verifies. This walks a plan in list order and stops at the first problem, which is all the `master-agent-demo` entry point ever needed."

**Classification**: **D** — Future Evolution (documented legacy path)

### Violation 3: Execution Order Ownership
**Constitution §4.1**: Orchestrator "walks a MissionPlan"
**Implementation**: Mission Control Dispatcher owns execution order (dependency-graph)
**Runtime** executes sequentially within cycle

**Classification**: **D** — Future Evolution (MB037 clarified ownership)

### Violation 4: Retry Policy Location
**Constitution §4.1**: "Retry/failure-branching policy lives here [Orchestrator]"
**Implementation**: Runtime does mechanical retry (`_execute_with_retry()`)
**Mission Control** never auto-retries (strategic recovery = Brain's)

**Classification**: **D** — Future Evolution (MB024 split mechanical vs strategic)

---

## 6. Runtime vs Orchestrator: Current Flow

### Actual Execution Flow (MB037 Path)
```
1. Founder objective → MissionService.start()
2. Planner → MissionPlan (Steps + ExpectedOutcomes)
3. missions/translation.py → Objective
4. MissionControl.submit_objective() → TaskDispatcher
5. RuntimeEngine._run_cycle()
   ├── _dispatch() → MissionControl.dispatch_ready() → Task[]
   ├── For each Task:
   │   ├── _handle_task()
   │   │   ├── ApprovalGate.check() → Authorised/Pending/Denied
   │   │   ├── ExecutiveGateway.invoke() → Plugin.invoke() / LocalExecutor
   │   │   ├── _execute_with_retry() (mechanical)
   │   │   ├── _verify() → gateway.verify() → Evidence
   │   │   ├── task_completed/failed → MissionControl
   │   │   └── checkpoint()
   └── Idle → sleep → repeat
```

### What Orchestrator Actually Does (Current)
- **Only used by `cli.py` demo path** (`master-agent-demo`)
- `execute_capability()` / `execute_step()` / `execute_plan()` — legacy sequential path
- **Not used by founder mission path** (`kalpavriksha` launcher)

---

## 7. Mission Control vs Runtime Boundary

### Constitutional Split
| Mission Control (Coordination) | Runtime (Execution) |
|--------------------------------|---------------------|
| Registers Executives/Capabilities | Executes via Gateways |
| Dispatches Tasks (dependency-ordered) | Invokes Gateways |
| Manages Queues (Self-Dev, Knowledge) | Mechanical Retry |
| Tracks Mission/Task State | Verifies via Gateway |
| Emits Events / Audit Stream | Reports Results |
| Founder State Snapshot | Mechanical Retry / Escalation |

### Implementation Status: ✅ Compliant
**Mission Control** (`mission_control.py`): Pure coordination, no execution, no verification
**Runtime** (`engine.py`): Pure execution/verification, no coordination decisions

**Classification**: ✅ Compliant

---

## 8. Mission Lifecycle Ownership

### Constitution
- **Mission State** owned by Shared Infrastructure (§5.3)
- **Orchestrator** transitions via Shared Infrastructure contract
- **Mission Control** tracks via Dispatcher

### Implementation
- `Mission` entity + state machine in `mission_manager/mission.py` ✅
- `MissionManager` class exists but **unwired** (KB#04 §11) → **B** Missing
- `cli.py` uses `Mission` directly, transitions manually → **C** Limitation (demo path)
- Mission Control `dispatcher` tracks Task state, not Mission state → **F** Doc Gap

---

## Summary: Boundary Audit Findings

| Boundary | Constitution | Implementation | Classification |
|----------|--------------|----------------|----------------|
| Orchestrator → Verification | Triggers Verification | Runtime does it | **A** Bug |
| Orchestrator → Retry Policy | Owns retry policy | Runtime does mechanical | **D** Evolution |
| Orchestrator → Execution Order | Walks MissionPlan | Dispatcher orders | **D** Evolution |
| Orchestrator → Plan Walking | Walks MissionPlan | Legacy path only | **D** Evolution |
| Runtime → Verification | Verifies via Gateway | ✅ Does it | ✅ Compliant |
| Runtime → Retry | Mechanical only | ✅ Does it | ✅ Compliant |
| Mission Control → Dispatch | Dependency-ordered | ✅ Does it | ✅ Compliant |
| Mission Control → No Work | No execution/verification | ✅ Pure coordination | ✅ Compliant |
| Mission State Ownership | Shared Infrastructure | Manager unwired | **B** Missing |
| Mission State Transitions | Via Shared Infra contract | Manual in `cli.py` | **C** Limitation |

---

*Generated from verified sources only. No fixes implemented. Classifications based on frozen Constitution only.*