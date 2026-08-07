# AI Capability Service (AiCapabilityService)

## Purpose
Documents the wiring layer that connects the AI Capability Broker (kernel service) to the execution layer — turning Broker decisions into executable Provider selections with approval flow, cost tracking, and audit trail.

---

## Frozen Constitution

### Constitution §5.7 (AI Capability Broker — RESEARCH-BACKED, Amendment 2)
> **The AI Capability Broker is a Kernel Service — a Shared Infrastructure component.** It is not an Executive, and it is not Brain-side or Operator-side.
>
> **Owns exclusively:** Provider Registry, Capability Matrix, Decision Engine, Cost Model, Benchmark Store, Approval Policy, AI Asset Inventory, Recommendation Engine.
>
> **Belongs here because:** both the Brain and the Operator need the same answer to the same question (ADR-0010). Its state (spend, approvals, benchmarks) must be singular across Operator Instances.
>
> **Boundary that keeps it here:** Broker **decides and never touches the machine**. Executes nothing, opens no connection, imports no provider SDK, spends nothing, retries nothing, grants no permission — it *requires* permission through §5.2.

### Constitution §16 Ownership Registry (FROZEN, Amendment 2)
| Component | Home | Rationale |
|-----------|------|-----------|
| **AI Capability Broker** | **Shared Infrastructure** (§5.7) | Both Brain's Model Router and Workers needing intelligence consult it; cost, approval, benchmark ledgers must be singular across Operator Instances. Decides; never executes, never touches Environment. |
| **AI Infrastructure Executive** | **Operator** (Worker, §12) | Machine-touching counterpart to Broker: discovers, probes, benchmarks, inventories, installs (with explicit Founder approval). Produces inputs Broker decides on; never decides itself. |

### Constitution §3.3 (Model Router — FROZEN, Amendment 2)
> The Model Router **consults the AI Capability Broker (§5.7) to resolve *which* Reasoning Provider**, rather than implementing its own ranking. Its interface, its role, and all four criteria are unchanged.

### Constitution Rule 4 (FROZEN)
> **Environment Access Has One Door.** No Brain module, no CLI code, touches an Environment directly. Everything goes through a Worker, via the Operator's Worker Runtime, via an Environment Session the Operator Instance owns.

---

## Architecture Design

### From `AI_CAPABILITY_BROKER_ARCHITECTURE.md` §2 (Kernel Service vs Executive)
> **Decision:** The AI Capability Broker is a **Kernel Service — a Shared Infrastructure component (§5).** It is not an Executive, and it is not Brain-side or Operator-side.
>
> **Split is exact:**
> | | AI Capability Broker (kernel service) | AI Infrastructure Executive (Worker) |
> |---|---|---|
> | Touches the machine | **Never** | Always — that is its whole job |
> | Decides which Provider | Always — nothing else may | Never |
> | Holds registry, matrix, ledger, benchmarks | Yes | No — it *produces inputs* to them |
> | Invoked by | Direct call, as Shared Infrastructure | Dispatch, as any Executive |
> | Import of provider SDK | Forbidden, mechanically | Permitted, in its own adapter |

### From `ai_infrastructure/service.py` Module Docstring
> **The one place a Kalpavriksha component asks "which intelligence?"** (Mission Brief 032).
> ```
>     request -> profiles -> Broker -> DecisionRecord -> approval? -> Selection
>               (supplied)  (decides)   (stored)       (founder)     (executable)
> ```
> Every arrow is an existing component used through its published contract.
> This class owns no ranking, no provider list, no cost opinion and no approval machinery — it is the wiring MB031 deliberately left undone.

### Guarantees (What It Guarantees, Cost If Missing)
1. **Every decision reaches the ledger before anything acts on it** — unreplayable decision makes "auditable" a claim rather than property (Deliverable 7)
2. **A refusal is returned as data, never discovered at call time** (Deliverable 4)
3. **A paid selection reaches founder's inbox BEFORE execution, never after money is gone** (Deliverable 5)
4. **A free selection under a permitting policy is executable immediately, with no question asked** (Deliverable 6)

---

## Core Types

### `Selection` — A Provider, Chosen, Recorded, Cleared to Run
```python
@dataclass(frozen=True)
class Selection:
    provider_id: str
    profile: ProviderProfile
    decision: BrokerDecision
    entry: DecisionEntry
    approval_state: str = NOT_REQUIRED
    approval_id: str | None = None
    budget: Any = None  # MB038: three deadlines (total, TTFT, stall)

    @property
    def why(self) -> str:
        return self.decision.reason  # Broker's own sentence, never paraphrase
```

### `SelectionOutcome` — Exactly Two States
```python
@dataclass(frozen=True)
class SelectionOutcome:
    selection: Selection | None = None
    refusal: BrokerRefusal | None = None
    # Exactly one is set. No third state, no best-effort partial answer.
```

### `BrokerReport` — What Dashboard Is Handed (Deliverable 9)
```python
@dataclass
class BrokerReport:
    policy_version: str
    policy_name: str
    providers_available: int
    providers_total: int
    scanned: bool
    total_decisions: int
    awaiting_approval: int
    decisions: tuple[DecisionEntry, ...]
    recording_failures: tuple[str, ...]
    last_execution: DecisionEntry | None
    economy: TokenEconomy
```
**Plain, precomputed data** — tiers already resolved, counts already counted — because a renderer that classifies is a renderer with an opinion (ADR-0016).

---

## AiCapabilityService Class

### Constructor
```python
class AiCapabilityService:
    def __init__(
        self,
        broker: CapabilityBroker,           # The kernel service (decides)
        providers: ProviderSource,          # Profile registry (reads)
        ledger: DecisionLedger,             # Audit trail (writes)
        approvals: Any = None,              # Optional: for decision-only service
        strong_reasoning_min_quality: float | None = None,
        task_ids: Any = None,
        monotonic: Any = None,
    )
```

**`approvals` optional** so caller can build decision-only service (report, dry run). Without it, anything needing founder permission is **refused**, never assumed (`NO_APPROVAL_QUEUE`).

### Core Methods

#### `decide()` — Broker Decision Only (No Execution)
```python
def decide(self, request: CapabilityRequest) -> SelectionOutcome:
    # 1. Broker decides
    decision = self._broker.decide(request)
    
    # 2. Record decision in ledger
    entry = self._ledger.record(decision)
    
    # 3. Handle approval if needed
    if decision.outcome == APPROVAL_REQUIRED:
        if self._approvals is None:
            return SelectionOutcome(refusal=BrokerRefusal(...))
        # Submit to approval queue
        approval_id = self._approvals.request(decision)
        return SelectionOutcome(refusal=ProviderApprovalPending(...))
    
    # 4. Build Selection
    profile = self._providers.get(decision.selection.provider_id)
    return SelectionOutcome(selection=Selection(
        provider_id=decision.selection.provider_id,
        profile=profile,
        decision=decision,
        entry=entry,
    ))
```

#### `select()` — Decide + Resolve to Executable Provider
```python
def select(self, request: CapabilityRequest) -> Selection:
    outcome = self.decide(request)
    if outcome.refusal:
        raise BrokerRefused(outcome.refusal)  # ModelRouter.select_provider() must return provider or not return
    return outcome.selection
```

#### `execute()` — Full Execute Path (Wired for ModelRouter)
```python
def execute(self, request: CapabilityRequest, prompt: str, context: dict) -> str:
    selection = self.select(request)  # raises if refused
    provider = self._provider_registry.get(selection.provider_id)
    return provider.generate(prompt, context)
```

---

## Approval Flow

### Three Outcomes (From `approval.py`)
| Broker Says | MB028.0 | MB028.1 |
|-------------|---------|---------|
| Granted | Execute | Execute |
| Not Granted | Fail task | **Ask founder; task waits** |
| Founder Rejected/Expired | — | Fail task, never retried |

### `FounderApprovalGate` (MB028.1)
- Wraps `PermissionSystemGate` rather than replacing it
- Adds third outcome: **ask the founder; the task waits**
- Expiry evaluated on each cycle re-check (no separate timer)
- Approval consumed once — never reused (ADR-0009)

---

## Cost & Budget System (MB038)

### `Selection.budget` — Three Deadlines
```python
budget: Any = None  # MB038: three deadlines (total, TTFT, stall)
```
- **Total deadline** — absolute instant, not duration (durations re-base at every hop)
- **Time-to-first-token (TTFT)** — separate from total
- **Stall deadline** — max inter-token gap
- Derived from measured throughput, not clamped to ceiling
- `bound_by: estimate` — derived from measured throughput

### `TokenEconomy` — Accumulates Without Inventing
- `money_saved` = recorded cost of work that happened once and was reused (NOT "what frontier model would have cost")
- `PromptCache` ships as interface + always-miss default (nothing verifies cache hits yet)

---

## Current Implementation Status

| Component | Architecture Status | Implementation Status | Notes |
|-----------|---------------------|----------------------|-------|
| **CapabilityBroker** (kernel) | RESEARCH-BACKED | ✅ **IMPLEMENTED** | `broker/broker.py` — decision engine, policy, profiles |
| **Decision Types** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | `broker/decision.py` — `BrokerDecision`, `DecisionRecord` |
| **Policy Engine** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | `broker/policy.py` — 8 founder policies, quality floors |
| **Provider Profiles** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | `broker/profiles.py` — `ProviderProfile`, `TaskProfile` |
| **Decision Ledger** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | `ai_infrastructure/ledger.py` — `DecisionLedger`, `DecisionEntry` |
| **Token Economy** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | `ai_infrastructure/economy.py` — `TokenEconomy` |
| **Budgets/Deadlines** | RESEARCH-BACKED (MB038) | ✅ **IMPLEMENTED** | `ai_infrastructure/budgets.py` — three deadlines |
| **Approval System** | RESEARCH-BACKED (MB028.1) | ✅ **IMPLEMENTED** | `ai_infrastructure/approval.py` — `FounderApprovalGate` |
| **AiCapabilityService** | RESEARCH-BACKED (MB032) | ✅ **IMPLEMENTED** | `ai_infrastructure/service.py` — wiring layer |
| **Provider Source** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | `ai_infrastructure/profiles.py` — `ProviderSource` |
| **Workload Profiles** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | `ai_infrastructure/workload.py` — `PLANNING`, `VERIFICATION` |
| **Budgeted Requests** | RESEARCH-BACKED (MB038) | ✅ **IMPLEMENTED** | `ai_infrastructure/budgeted_request.py` |
| **Refusal Types** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | `ai_infrastructure/refusal.py` — 5 named outcomes |
| **Concrete Providers** | RESEARCH-BACKED | ❌ **NOT IMPLEMENTED** | Ollama, ChatGPT, etc. — `providers/` package missing |
| **AI Infrastructure Executive** | RESEARCH-BACKED | ❌ **NOT IMPLEMENTED** | Machine-touching counterpart (scans, probes, benchmarks) |

---

## Design vs Implementation Differences

| Area | Design (Architecture/Constitution) | Implementation | Status |
|------|-----------------------------------|----------------|--------|
| **Broker as Kernel Service** | Shared Infra, never executes | ✅ `CapabilityBroker` in `broker/` | ✅ MATCH |
| **Broker Decides, Never Executes** | Decision engine only | ✅ `CapabilityBroker.decide()` | ✅ MATCH |
| **AiCapabilityService Wiring** | MB032 wiring layer | ✅ `AiCapabilityService` in `service.py` | ✅ MATCH |
| **Approval Integration** | MB028.1 `FounderApprovalGate` | ✅ `FounderApprovalGate` wraps `PermissionSystemGate` | ✅ MATCH |
| **Three Deadlines** | Total, TTFT, Stall (MB038) | ✅ `budgets.py` derives three deadlines | ✅ MATCH |
| **Token Economy** | Records actual reuse savings | ✅ `TokenEconomy` + `PromptCache` (always-miss) | ✅ MATCH |
| **Refusal as Data** | 5 named outcomes, never silent | ✅ `refusal.py` — 5 named outcomes | ✅ MATCH |
| **Concrete Providers** | Ollama, ChatGPT, etc. | ❌ Not implemented | ❌ MISSING |
| **AI Infrastructure Executive** | Machine-touching counterpart | ❌ Not implemented | ❌ MISSING |
| **Provider Registry Source** | Desktop Executive scan | ✅ `ProviderSource` reads from scan | ✅ MATCH |

---

## Open Questions

1. **Concrete Providers Not Implemented** — Architecture frozen, but `providers/` package missing. Required for Model Router (MB032) and Workers needing intelligence mid-task.

2. **AI Infrastructure Executive Not Implemented** — Machine-touching counterpart (scans, probes, benchmarks, inventories, installs). Required for Broker's inventory freshness.

3. **Provider Discovery Chicken-Egg** — Broker needs inventory; Executive produces inventory; Executive needs Broker for intelligence?

4. **Quality Floor Calibration** — Founder sets via policy; how calibrated initially? No benchmark store exists yet.

5. **Cost Model Initialization** — Spend tracking starts at zero; budget caps need founder configuration.

6. **Approval Policy Defaults** — 8 policies need founder configuration; safe defaults?

7. **Recommendation Engine Output** — Inert data; how consumed? Future Executive reads recommendations and acts?

8. **Benchmark Store Seeding** — Aggregates by (provider, ai_capability, task_class); needs initial data or cold-start logic.

---

## Future Extraction Targets

1. `src/master_agent/ai_infrastructure/service.py` — `AiCapabilityService` wiring layer
2. `src/master_agent/broker/broker.py` — `CapabilityBroker` kernel service
3. `src/master_agent/broker/decision.py` — `BrokerDecision`, `DecisionRecord`
4. `src/master_agent/broker/policy.py` — 8 founder policies, quality floors
5. `src/master_agent/broker/profiles.py` — `ProviderProfile`, `TaskProfile`
6. `src/master_agent/ai_infrastructure/ledger.py` — `DecisionLedger`, `DecisionEntry`
7. `src/master_agent/ai_infrastructure/approval.py` — `FounderApprovalGate`, `PermissionSystemGate`
8. `src/master_agent/ai_infrastructure/economy.py` — `TokenEconomy`, `summarise`
9. `src/master_agent/ai_infrastructure/budgets.py` — Three deadlines derivation
10. `src/master_agent/ai_infrastructure/budgeted_request.py` — `BudgetedSelectionRequest`
11. `src/master_agent/ai_infrastructure/refusal.py` — 5 named refusal outcomes
12. `src/master_agent/ai_infrastructure/workload.py` — `PLANNING`, `VERIFICATION` workload profiles
13. `src/master_agent/ai_infrastructure/text_verifier.py` — `expect()`, `passed()`
14. `src/master_agent/ai_infrastructure/cache.py` — `PromptCache` interface
15. `docs/adr/0017` — AI Capability Broker decision record (ratified)
16. `docs/adr/0018` — Broker learning loop (EVOLVABLE)

---

## Wiki Links Added

- `[[KALPAVRIKSHA_VISION_V2.md]]` — Constitution §3.3, §5.7, §16, Rule 4
- `[[FOUNDER_CONSTITUTION_FREEZE.md]]` — Freeze record, Amendment 2
- `[[AI_CAPABILITY_BROKER_ARCHITECTURE.md]]` — Broker design, decision engine
- `[[ARCHITECTURE.md]]` — Implementation map
- `[[01_executive_brain.md]]` — Brain (Model Router consults Broker)
- `[[04_shared_infrastructure.md]]` — Shared Infrastructure (Broker home)
- `[[09_ai_capability_broker.md]]` — Broker architecture details
- `[[13_plugin_system.md]]` — Plugin system (ModelProvider)
- `[[14_model_router.md]]` — Model Router (asks Broker)
- `[[system_overview.md]]` — System overview
- `[[docs/adr/0010]]` — Shared Infrastructure layer
- `[[docs/adr/0017]]` — AI Capability Broker (ratified)
- `[[docs/adr/0018]]` — Broker learning loop
- `[[docs/adr/0019]]` — Runtime approval boundary
- `[[docs/adr/0020]]` — Founder approval workflow (Proposed)

---

*Document created from verified sources only. No AI Capability Service architecture redesigned. Terminology preserved exactly. Constitution/Architecture/Implementation/Open Questions separated. Design/implementation differences recorded without reconciliation.*