# Model Router

## Purpose
Documents the Brain's single door to reasoning — the component that routes generation requests to whichever Provider the AI Capability Broker selects, without making provider decisions itself.

---

## Frozen Constitution

### Constitution §3.3 (Model Router — FROZEN)

**Role:** Single Reasoning Provider interface (`generate(prompt, context, **opts) -> ModelResponse`). Picks a provider per call based on:
1. **Connectivity** — offline ⇒ Local Reasoning Provider only
2. **Privacy sensitivity** — sensitive tags stay local unless human explicitly overrides
3. **Task profile** — routine → local; strong reasoning needed → cloud
4. **Explicit user preference** — always wins

**Amendment 2 (MB027):** The Model Router **consults the AI Capability Broker (§5.7) to resolve *which* Reasoning Provider**, rather than implementing its own ranking. Its interface, its role as the Brain's single door to reasoning, and all four criteria are unchanged — each one maps onto a phase of the Broker's decision engine (`AI_CAPABILITY_BROKER_ARCHITECTURE.md` §6.5), with one stated narrowing: criterion 4's "always wins" is honoured among candidates that survive the Broker's hard-constraint filter, so a preference can never select a Provider that is unavailable, licence-barred, privacy-barred, or paid-without-approval.

**The Model Router resolves *which registered Reasoning Provider* to invoke by querying Shared Infrastructure's Capability Registry (§5.1) — the same registry the Operator's Orchestrator queries to resolve execution capabilities. This is not a boundary violation: both the Brain and the Operator depend downward on Shared Infrastructure; neither depends on the other (§6).**

### Constitution §5.1 (Capability Registry — FROZEN)
> Queried by the Brain's Model Router (to resolve a Reasoning Provider) and the Operator's Orchestrator (to resolve an execution capability) — the same lookup mechanism serving two different callers. One registry, one answer, regardless of who's asking.

### Constitution §5.7 (AI Capability Broker — RESEARCH-BACKED, Amendment 2)
> The single intelligence-selection service. Every component that needs AI — the Brain's Model Router and Planner, and every Worker that needs reasoning, vision, OCR, speech, or embeddings mid-task — asks the Broker *which* Provider should serve the request. **No other component may decide.**

> **Belongs in Shared Infrastructure because:** both the Brain and the Operator need the same answer to the same question (ADR-0010). One copy per side would drift; assigning it to either side recreates the crossed-boundary contradiction. Its state (spend, approvals, benchmarks) must be singular across Operator Instances.

> **Boundary that keeps it here:** Broker **decides and never touches the machine**. Executes nothing, opens no connection, imports no provider SDK, spends nothing, retries nothing, grants no permission — it *requires* permission through §5.2. Output names already-registered Capability + parameters; caller runs through Operator like any other Capability. **Broker creates no new execution path.**

### Constitution Rule 4 (FROZEN)
> **Environment Access Has One Door.** No Brain module, no CLI code, touches an Environment directly. Everything goes through a Worker, via the Operator's Worker Runtime, via an Environment Session the Operator Instance owns.

---

## Model Router Philosophy

### From `model_router.py` Module Docstring

**Before MB032:** Four hardcoded branches, two product names, unauditable ladder:
```python
if not ctx.is_online:            return self._provider("hermes")
if ctx.is_sensitive:             return self._provider("hermes")
if ctx.requires_strong_reasoning: return self._provider("chatgpt")
return self._provider(self._default_provider)  # "hermes"
```

**ADR-0017 Consequences:** Called this *"a documented contradiction"* — Constitution §14/§21 forbid product names in Brain logic.

**After MB032 (Amendment 2 §3.3):** Four branches become **four facts about the request** — `offline`, `sensitive`, `requires_strong_reasoning`, `preferred_provider` — which the Broker turns into a decision with a record behind it. **No provider name left in this file.**

### The Port Pattern (Outbound Port)
`ProviderSelector` Protocol declared in Model Router, satisfied by `ai_infrastructure.AiCapabilityService`. Dependency points **inward**: the Brain declares what it needs and is handed an implementation, so `plugins/` acquires no dependency on Mission Control, Permission System, or Broker.

### Fail-Closed
A router with no selector **refuses everything** (Deliverable 10). Not "falls back to the local one": a fallback is a provider decision, and a component that makes one when its decision-maker is missing is the exact hardcoding MB032 deleted. Forgetting to wire the Broker yields a system that does nothing and says why, never one that quietly does something else.

---

## Routing Responsibilities

### What Model Router DOES
1. **Accepts `RoutingContext`** — facts about the work (never provider preference)
2. **Builds `SelectionRequest`** — frozen dataclass forwarded to Broker
3. **Calls Broker via `ProviderSelector` Protocol** — `select(request) -> decision`
4. **Resolves decision to runnable Plugin** — via `PluginRegistry`
5. **Executes generation** — `provider.generate(prompt, context)`

### What Model Router Does NOT Do
- **Decide which Provider** — Broker's job exclusively
- **Rank providers** — Broker's Decision Engine does this
- **Implement fallback logic** — Broker refuses rather than guesses
- **Know provider names** — zero vendor names in code
- **Execute generation directly** — delegates to `ModelProvider` Plugin
- **Retry on failure** — Runtime = mechanical retry, Brain = strategic retry

---

## Provider Selection

### Input: `RoutingContext` (Facts About the Work)
```python
@dataclass
class RoutingContext:
    is_online: bool = True                    # connectivity fact
    is_sensitive: bool = False                # privacy fact
    requires_strong_reasoning: bool = False   # task profile fact
    preferred_provider: str | None = None     # explicit founder override
    capability: str = REASONING               # AI Capability (lowercase.dotted)
    max_cost: float | None = None
    max_latency_ms: float | None = None
    required_context_tokens: int | None = None
    task_id: str = ""
    objective_id: str | None = None
    requester: str = "model_router"
```

**Key Principle:** Every field is a fact about the *work*, never a preference about the provider. Turning "this matters" into a product name was the bug MB032 fixed.

### Output: `SelectionRequest` (Frozen — Broker Must Not Edit)
```python
@dataclass(frozen=True)
class SelectionRequest:
    capability: str = REASONING
    offline: bool = False                     # is_online inverted
    sensitive: bool = False
    requires_strong_reasoning: bool = False
    min_quality: float | None = None
    max_cost: float | None = None
    max_latency_ms: float | None = None
    required_context_tokens: int | None = None
    preferred_provider: str | None = None
    exclude_providers: frozenset[str] = field(default_factory=frozenset)
    task_id: str = ""
    objective_id: str | None = None
    requester: str = "model_router"
```

**Constraint/Hint Split Load-Bearing:** Stops preference silently overriding privacy rule; enables two clean algorithm phases in Broker.

### Broker Selection Protocol
```python
@runtime_checkable
class ProviderSelector(Protocol):
    def select(self, request: SelectionRequest) -> Any: ...
    # Returns decision with provider_id, raises rather than returning guess
```

---

## ModelProvider Plugin Relationship

### ModelProvider Specialization (`src/master_agent/plugins/base.py`)
```python
class ModelProvider(Plugin):
    CAPABILITY_NAME = "generate_text"

    @abstractmethod
    def generate(self, prompt: str, context: dict | None, **opts) -> str: ...

    def invoke(self, capability: str, payload: dict) -> InvocationResult:
        if capability != self.CAPABILITY_NAME:
            return InvocationResult(success=False, error=f"unknown capability: {capability}")
        text = self.generate(payload.get("prompt", ""), payload.get("context"))
        return InvocationResult(success=True, output=text)
```

### ModelRouter Resolution
```python
def select_provider(self, ctx: RoutingContext) -> ModelProvider:
    decision = self.select(ctx)  # BrokerDecision with provider_id
    return self._provider(decision.provider_id)

def _provider(self, name: str) -> ModelProvider:
    plugin = self._registry.get(name)  # PluginRegistry lookup
    if not isinstance(plugin, ModelProvider):
        raise ProviderNotWired(name, "registered plugin is not a ModelProvider")
    return plugin
```

### ProviderNotWired Exception
> The Broker chose a provider this process has no plugin for. A wiring gap, not a decision problem — the decision was sound and is on the record, but nothing here can execute it. **Silently picking a different provider would make the record a lie.**

---

## AI Capability Broker Relationship

### From `AI_CAPABILITY_BROKER_ARCHITECTURE.md` §3.1 Position
```
Executive Brain (Intent, Planner, Model Router, Reporter)
        │  asks
        ▼
┌─────────────────── Shared Infrastructure ───────────────────┐
│  Capability Registry  Permission System  Mission State     │
│  Memory  Configuration  Telemetry/Evidence                 │
│                                                             │
│  ┌──────────────  AI Capability Broker  ────────────────┐  │
│  │  Provider Registry ─ Capability Matrix ─ Cost Model  │  │
│  │  Decision Engine ─ Benchmark Store ─ Approval Policy │  │
│  │  AI Asset Inventory ─ Recommendation Engine          │  │
│  └──────────────────────────────────────────────────────┘  │
└──────────────────────────────▲──────────────────────────────┘
        │ asks │ feeds inventory,
        ▼      │ benchmarks, outcomes
Universal Executive Operator
```

### Model Router → Broker Flow
1. **Model Router** builds `SelectionRequest` from `RoutingContext`
2. **Broker** receives request, runs Decision Engine (two-phase: filter → rank)
3. **Broker** returns `BrokerDecision` with `ProviderSelection`
4. **Model Router** resolves `provider_id` to `ModelProvider` Plugin
5. **ModelProvider** executes `generate(prompt, context)`

### Broker Decision Output (What Model Router Receives)
```python
BrokerDecision(
    decision_id,                # join key for cost, benchmark, audit
    request_id,
    outcome,                    # SELECTED | APPROVAL_REQUIRED | NO_CAPABLE_PROVIDER
    selection,                  # ProviderSelection | None
    alternatives,               # ranked, with reasons — never just the winner
    rejected,                   # [(provider_id, filter_reason)] — full audit trail
    cost_estimate,              # CostEstimate | None
    approval,                   # ApprovalRequirement | None
    inventory_age_seconds,      # freshness of facts
    policy_version,             # which policy produced this
    inputs_digest,              # replay key
    decided_at,
)

ProviderSelection(
    provider_id,
    tier,                       # rung of ladder
    execution_capability,       # PascalCase.PascalCase — what Operator dispatches
    execution_parameters,       # plain dict: model name, endpoint id, etc.
    expected_success,           # 0..1, with `confidence`
    confidence,                 # low when benchmark samples scarce
    rationale,                  # human-readable, founder-facing
)
```

### Key Property: `execution_capability` = Bridge
Broker output names **already-registered Capability** + parameters. Caller resolves via Capability Registry, runs through Operator. **Broker creates no new execution path.**

---

## Current Implementation Status

| Component | Constitution/Architecture | Implementation Status | Notes |
|-----------|---------------------------|----------------------|-------|
| **ModelRouter Class** | FROZEN (§3.3) | ✅ **IMPLEMENTED** | `src/master_agent/plugins/model_router.py` |
| **RoutingContext** | FROZEN | ✅ **IMPLEMENTED** | Facts about work, no provider preference |
| **SelectionRequest** | FROZEN | ✅ **IMPLEMENTED** | Frozen dataclass, constraint/hint split |
| **ProviderSelector Protocol** | FROZEN | ✅ **IMPLEMENTED** | Outbound port, satisfied by Broker |
| **Broker Integration** | MB032/Amendment 2 | ✅ **IMPLEMENTED** | `select()` → `select_provider()` → `_provider()` |
| **Fail-Closed** | MB032 Deliverable 10 | ✅ **IMPLEMENTED** | `BrokerUnavailable`, `ProviderNotWired` exceptions |
| **ModelProvider Plugins** | FROZEN (Rule 3) | ✅ **IMPLEMENTED** | `ModelProvider` specialization |
| **PluginRegistry Lookup** | FROZEN (§5.1) | ✅ **IMPLEMENTED** | Capability Registry shared with Orchestrator |
| **Four Hardcoded Branches** | REMOVED (MB032) | ✅ **REMOVED** | No product names in code |
| **`preferred_provider` Override** | FROZEN (criterion 4) | ✅ **IMPLEMENTED** | Passed as hint, honoured among survivors |
| **AI Capability Broker** | RESEARCH-BACKED | ❌ **NOT IMPLEMENTED** | Architecture only (MB027); `broker/` package missing |
| **ProviderSelector Implementation** | RESEARCH-BACKED | ❌ **NOT IMPLEMENTED** | `ai_infrastructure.AiCapabilityService` missing |
| **Broker Decision Types** | RESEARCH-BACKED | ❌ **NOT IMPLEMENTED** | `BrokerDecision`, `ProviderSelection` dataclasses missing |
| **Broker Refusal Handling** | RESEARCH-BACKED | ⚠️ **PARTIAL** | `BrokerUnavailable` raised, but no Broker to refuse |

---

## Open Questions

1. **AI Capability Broker Not Implemented** — Architecture frozen (MB027, Amendment 2), but `src/master_agent/broker/` does not exist. Required for Model Router (MB032) and Workers needing intelligence mid-task.

2. **Broker Decision Types Missing** — `BrokerDecision`, `ProviderSelection`, `SelectionRequest` dataclasses defined in architecture but not implemented in code.

3. **ProviderSelector Implementation Missing** — `ai_infrastructure.AiCapabilityService` missing. Protocol exists in `model_router.py` but no implementation.

4. **Broker Refusal Handling** — Model Router raises `BrokerUnavailable` if no selector wired. But Broker itself not implemented to refuse.

5. **ModelProvider Plugins** — Only `ModelProvider` specialization exists. No concrete implementations (Ollama, ChatGPT, etc.) yet.

6. **Broker Wiring** — How does the composition root wire Broker → Model Router? Not yet documented.

7. **Broker Approval Integration** — Broker returns `APPROVAL_REQUIRED` for paid providers. Model Router must surface this to approval flow (MB028.1).

8. **Broker Learning Loop** — ADR-0018: Broker's learning loop EVOLVABLE; policy learns, decision procedure deterministic. Not yet designed.

---

## Design vs Implementation Differences

| Area | Design (Architecture/Constitution) | Implementation | Status |
|------|-----------------------------------|----------------|--------|
| **No Hardcoded Branches** | Four branches removed | ✅ No product names in code | ✅ MATCH |
| **Outbound Port** | ProviderSelector Protocol | ✅ Declared in `model_router.py` | ✅ MATCH |
| **Fail-Closed** | No fallback to local | ✅ `BrokerUnavailable` raised | ✅ MATCH |
| **ProviderNotWired** | Wiring gap ≠ decision problem | ✅ Exception with decision preserved | ✅ MATCH |
| **Constraint/Hint Split** | Facts vs preferences | ✅ `SelectionRequest` frozen | ✅ MATCH |
| **Broker as Decision Maker** | Model Router asks, never decides | ✅ `select()` calls Broker | ✅ MATCH |
| **PluginRegistry Shared** | Same registry as Orchestrator | ✅ `PluginRegistry` injected | ✅ MATCH |
| **Four Facts Forwarded** | offline, sensitive, strong_reasoning, preferred | ✅ `SelectionRequest` fields | ✅ MATCH |
| **AI Capability Broker** | Kernel Service in Shared Infra | ❌ Not implemented | ❌ MISSING |
| **Broker Decision Types** | BrokerDecision, ProviderSelection | ❌ Not implemented | ❌ MISSING |
| **ProviderSelector Impl** | ai_infrastructure.AiCapabilityService | ❌ Not implemented | ❌ MISSING |
| **Broker Refusal Flow** | NO_CAPABLE_PROVIDER, APPROVAL_REQUIRED | ⚠️ Model Router raises BrokerUnavailable | ⚠️ PARTIAL |
| **Concrete ModelProviders** | Ollama, ChatGPT, etc. | ❌ None implemented | ❌ MISSING |
| **Broker Wiring** | Composition root wires Broker → Router | ❌ Not documented | ❌ MISSING |

---

## Future Extraction Targets

1. `src/master_agent/plugins/model_router.py` — Full ModelRouter implementation
2. `src/master_agent/ai_infrastructure/` — When implemented: `AiCapabilityService` (ProviderSelector impl)
3. `src/master_agent/broker/` — When implemented: Broker, Decision Engine, Provider Registry
4. `src/master_agent/plugins/providers/` — Concrete ModelProvider implementations (Ollama, etc.)
5. `docs/adr/0017` — AI Capability Broker decision record (ratified)
6. `docs/adr/0018` — Broker learning loop (EVOLVABLE)
7. `tests/test_broker_integration.py` — Greps for 7 vendor names in `model_router.py`
8. `tests/test_model_router.py` — Model Router tests

---

## Wiki Links Added

- `[[KALPAVRIKSHA_VISION_V2.md]]` — Constitution §3.3, §5.1, §5.7, Rule 4
- `[[FOUNDER_CONSTITUTION_FREEZE.md]]` — Freeze record, Amendment 2
- `[[AI_CAPABILITY_BROKER_ARCHITECTURE.md]]` — Broker design, decision engine, output
- `[[ARCHITECTURE.md]]` — Implementation map §5
- `[[01_executive_brain.md]]` — Brain layer (Model Router context)
- `[[04_shared_infrastructure.md]]` — Shared Infrastructure (Capability Registry, Broker)
- `[[09_ai_capability_broker.md]]` — Broker architecture details
- `[[13_plugin_system.md]]` — Plugin system (ModelProvider, Registry)
- `[[system_overview.md]]` — System overview
- `[[docs/adr/0010]]` — Shared Infrastructure layer
- `[[docs/adr/0017]]` — AI Capability Broker (ratified)
- `[[docs/adr/0018]]` — Broker learning loop

---

*Document created from verified sources only. No routing logic redesigned. Terminology preserved exactly. Constitution/Architecture/Implementation/Open Questions separated. Design/implementation differences recorded without reconciliation.*