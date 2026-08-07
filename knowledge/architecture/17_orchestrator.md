# Orchestrator Architecture

## Purpose
Documents the Orchestrator — the component that walks a MissionPlan, resolves each Step's capability to a Plugin via the Registry, checks the Permission System, invokes the Plugin, and captures the result. Retry/failure-branching policy lives here, not in individual Plugins.

---

## Frozen Constitution

### Constitution §4.1 (Orchestrator — FROZEN)
> **Orchestrator** walks a `MissionPlan`, and for each `Step`:
> 1. Resolves Capability → Worker via Shared Infrastructure's Capability Registry
> 2. Checks Permission System via Shared Infrastructure
> 3. Invokes the Worker, captures the result
> 4. Triggers Verification (§10) against Step's Expected Outcome
> 5. Applies retry/failure-branching policy — bounded, deterministic, scoped to this Operator Instance; never re-plans

### Constitution §4.4 (What the Operator Does NOT Do — FROZEN)
> Does not decide what a Mission should accomplish
> Does not maintain its own private copy of Permission grants, Mission state, or Memory — all three are Shared Infrastructure (§5), specifically so multiple Operator Instances (§8) never disagree about approvals, Mission state, or history
> Does not nominate or promote Knowledge (§9) — produces Evidence; Brain and Promotion Review decide what becomes durable

### Constitution §5.1 (Capability Registry — FROZEN)
> Queried by the Orchestrator (to resolve an execution capability) and the Brain's Model Router (to resolve a Reasoning Provider) — same lookup mechanism, two different callers. One registry, one answer.

### Constitution §5.2 (Permission System — FROZEN)
> Single, consistent grant ledger across every Operator Instance. The Orchestrator checks the Permission System via Shared Infrastructure.

---

## Architecture Design

### From `ARCHITECTURE.md` §4.5
> **Orchestrator** — walks a `MissionPlan`, resolves each Step's capability to a plugin via the registry, checks the Permission System, invokes the plugin. Retry/failure-branching policy lives here, not in individual plugins.

### From `orchestrator/orchestrator.py` Module Docstring
> **Orchestrator — walks a MissionPlan, resolves each Step's capability to a plugin via the registry, checks the Permission System, invokes the plugin.**
> See ARCHITECTURE.md §4.5. Retry/failure-branching policy lives here, not in individual plugins.

### Key Design Decisions

**1. Capability Resolution via Registry**
- `PluginRegistry.find_for_capability(capability)` returns list of candidate Plugins
- Founder Edition: takes first candidate (no selection policy for multiple providers)
- `PluginRegistry.risk_tier_for(plugin_name, capability)` used for permission check

**2. Permission Check Before Invocation**
- `PermissionSystem.check(plugin_name, capability, risk_tier)` called before `plugin.invoke()`
- Raises `ApprovalRequired` if grant not present
- Returns `StepResult(blocked_on_approval=True)` for caller to handle

**3. Single Capability Execution**
- `execute_capability(capability, payload, step_id)` — split out by MB037 so single capability callers don't manufacture a `Step`
- This is not a convenience: `Step` belongs to a `MissionPlan`, Planner is the only thing permitted to produce one

**4. Sequential Plan Execution (Legacy Path)**
- `execute_plan(plan)` walks steps in list order, stops at first approval block or failure
- **Explicitly NOT the mission path since MB037** — Mission Control's Dispatcher orders by dependency; Runtime executes and verifies
- Dependency-graph scheduling is deliberately NOT built here: Mission Control owns execution order

---

## Responsibilities

| Responsibility | Description |
|----------------|-------------|
| **Capability Resolution** | Resolve capability name → Plugin via PluginRegistry |
| **Permission Gating** | Check Permission System before invocation |
| **Plugin Invocation** | Call `plugin.invoke(capability, payload)` |
| **Result Capture** | Return `StepResult(step_id, InvocationResult, blocked_on_approval)` |
| **Retry Policy** | Bounded, deterministic, scoped to this Operator Instance |
| **Failure Branching** | Stop on first failure/approval block (legacy sequential path) |

---

## Components

### Orchestrator Class (`src/master_agent/orchestrator/orchestrator.py`)

```python
class Orchestrator:
    def __init__(self, registry: PluginRegistry, permissions: PermissionSystem):
        self._registry = registry
        self._permissions = permissions

    def execute_capability(self, capability: str, payload: dict, step_id: str = "") -> StepResult:
        # 1. Resolve capability → Plugin
        candidates = self._registry.find_for_capability(capability)
        if not candidates:
            return StepResult(step_id, InvocationResult(success=False, error=f"no plugin for capability {capability}"))
        plugin = candidates[0]  # Founder Edition: first candidate
        risk_tier = self._registry.risk_tier_for(plugin.manifest.name, capability)

        # 2. Permission check
        try:
            self._permissions.check(plugin.manifest.name, capability, risk_tier)
        except ApprovalRequired:
            return StepResult(step_id=step_id or capability, result=None, blocked_on_approval=True)

        # 3. Invoke plugin
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

### StepResult
```python
@dataclass
class StepResult:
    step_id: str
    result: InvocationResult | None
    blocked_on_approval: bool = False
```

---

## Data/State Flow

```
MissionPlan (list of Steps)
         │
         ▼
Orchestrator.execute_plan()
         │
         ├─► For each Step:
         │      │
         │      ├─► Registry.find_for_capability(step.capability)
         │      │
         │      ├─► Registry.risk_tier_for(plugin, capability)
         │      │
         │      ├─► PermissionSystem.check(plugin, capability, risk_tier)
         │      │       └─► raises ApprovalRequired → StepResult(blocked_on_approval=True)
         │      │
         │      ├─► plugin.invoke(capability, step.payload)
         │      │
         │      └─► StepResult(step_id, InvocationResult, blocked_on_approval)
         │
         └─► list[StepResult] (stops on first block/failure)
```

---

## Security Boundaries

### Permission Check
- Called **before** any Plugin invocation
- Uses Shared Infrastructure's Permission System (single grant ledger)
- Risk tier from Plugin's manifest via Registry
- `READ_ONLY` short-circuits unconditionally

### No Direct Environment Access
- Orchestrator never touches filesystem, shell, browser, etc.
- All Environment access through Plugin → LocalExecutor → Actions
- Rule 4 enforced: Environment access only through Worker via Operator's Worker Runtime

### Approval Boundary
- Orchestrator check is **one approval gate**
- Runtime has separate ApprovalGate at `_handle_task()` (MB028.0)
- Relay pattern (ADR-0005) connects them without asking human twice

---

## Current Implementation Status

| Component | Constitution/Architecture | Implementation Status | Notes |
|-----------|---------------------------|----------------------|-------|
| **Orchestrator Class** | FROZEN (§4.1) | ✅ **IMPLEMENTED** | `src/master_agent/orchestrator/orchestrator.py` |
| **Capability Resolution** | FROZEN (§4.1, §5.1) | ✅ **IMPLEMENTED** | `PluginRegistry.find_for_capability()` |
| **Permission Check** | FROZEN (§4.1, §5.2) | ✅ **IMPLEMENTED** | `PermissionSystem.check()` before invoke |
| **Plugin Invocation** | FROZEN (§4.1) | ✅ **IMPLEMENTED** | `plugin.invoke()` |
| **StepResult** | FROZEN | ✅ **IMPLEMENTED** | `StepResult(step_id, result, blocked_on_approval)` |
| **Retry/Failure Policy** | FROZEN (§4.1) | ⚠️ **PARTIAL** | Sequential walk, stops on first problem (legacy path) |
| **Verification Trigger** | FROZEN (§4.1, §10) | ❌ **NOT IMPLEMENTED** | Orchestrator does NOT trigger Verification (Runtime does) |
| **Dependency-Graph Scheduling** | FROZEN | ❌ **NOT IMPLEMENTED** | Mission Control's Dispatcher owns execution order |
| **Single Capability Execution** | MB037 | ✅ **IMPLEMENTED** | `execute_capability()` split from `execute_step()` |

---

## Design vs Implementation Differences

| Area | Design (Constitution/Architecture) | Implementation | Status |
|------|-----------------------------------|----------------|--------|
| **Capability Resolution** | Registry → Plugin | ✅ `PluginRegistry.find_for_capability()` | ✅ MATCH |
| **Permission Check** | Before invoke, via Shared Infra | ✅ `PermissionSystem.check()` | ✅ MATCH |
| **Retry/Failure Policy** | Bounded, deterministic, no re-plan | ✅ Sequential, stops on first problem | ✅ MATCH (legacy) |
| **Verification Trigger** | Orchestrator triggers Verification | ❌ Runtime triggers Verification | ⚠️ DOCUMENTED |
| **Execution Order** | Orchestrator walks plan | ❌ Mission Control Dispatcher owns order | 📝 DOCUMENTED |
| **Single Capability Execution** | `execute_capability()` | ✅ Split out by MB037 | ✅ MATCH |
| **Multiple Providers** | Selection policy | ⏳ Founder Edition: first candidate | ⏳ RESERVED |

---

## Open Questions

1. **Verification Not Triggered by Orchestrator** — Constitution §4.1 says Orchestrator "triggers Verification against Step's Expected Outcome" but Runtime (`RuntimeEngine._verify()`) does this instead. Documented divergence since MB037.

2. **Execution Order Ownership** — Constitution says Orchestrator "walks a MissionPlan" but MB037 made Mission Control's Dispatcher own execution order (dependency-graph scheduling). Orchestrator's `execute_plan()` is legacy sequential path for `master-agent-demo` only.

3. **Retry Policy Scope** — Constitution says "Retry/failure-branching policy lives here, not in individual plugins" and "never re-plans." Current legacy path stops on first failure. No retry implemented in Orchestrator (Runtime does mechanical retry).

4. **Multiple Provider Selection** — `find_for_capability()` returns list; Founder Edition takes first. Selection policy for multiple providers = EVOLVABLE.

5. **Verification Integration** — How should Orchestrator trigger Verification when a second Verifier-backed Worker exists? Currently two integration surfaces side by side (`BrowserPlugin` + `BrowserWorker`).

---

## Future Extraction Targets

1. `src/master_agent/orchestrator/orchestrator.py` — Full Orchestrator implementation
2. `src/master_agent/orchestrator/__init__.py` — Exports
3. `tests/test_orchestrator.py` — Orchestrator tests
4. `docs/adr/0003` — Plugin contract (Registry contract)
5. `docs/adr/0005` — Executor permission relay (Orchestrator check vs Executor check)

---

## Wiki Links Added

- `[[KALPAVRIKSHA_VISION_V2.md]]` — Constitution §4.1, §5.1, §5.2
- `[[FOUNDER_CONSTITUTION_FREEZE.md]]` — Freeze record
- `[[ARCHITECTURE.md]]` — Implementation map §4.5
- `[[03_universal_executive_operator.md]]` — Operator responsibilities
- `[[04_shared_infrastructure.md]]` — Shared Infrastructure (Registry, Permission)
- `[[06_runtime_engine.md]]` — Runtime Engine (Verification, execution order)
- `[[07_mission_control.md]]` — Mission Control (Dispatcher, execution order)
- `[[12_permission_security.md]]` — Permission check integration
- `[[13_plugin_system.md]]` — Plugin system (Registry, Plugin contract)
- `[[15_action_contract.md]]` — Action Contract (LocalExecutor)
- `[[system_overview.md]]` — System overview

---

*Document created from verified sources only. No Orchestrator architecture redesigned. Terminology preserved exactly. Constitution/Architecture/Implementation/Open Questions separated. Design/implementation differences recorded without reconciliation.*