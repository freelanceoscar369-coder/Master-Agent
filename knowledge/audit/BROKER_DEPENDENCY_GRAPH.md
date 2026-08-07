# AI Capability Stack Dependency Graph

## Source
- Implementation: `src/master_agent/broker/`, `src/master_agent/ai_infrastructure/`, `src/master_agent/plugins/model_router.py`, `src/master_agent/plugins/`, `src/master_agent/providers/`
- Architecture: `AI_CAPABILITY_BROKER_ARCHITECTURE.md`, `KALPAVRIKSHA_VISION_V2.md` §5.7

---

## Complete Dependency Graph

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        AI CAPABILITY STACK DEPENDENCY GRAPH                 │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                            FOUNDATION LAYER                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────────┐ │
│  │ ProviderSpec    │    │ Desktop         │    │ CapabilityBroker        │ │
│  │ Catalog         │    │ Executive       │    │ (Kernel Service)        │ │
│  │ (Static)        │    │ (Scanner)       │    │                         │ │
│  │                 │    │                 │    │ ┌─────────────────────┐ │ │
│  │ PROVIDER_       │    │ • Scan          │    │ │ Decision Engine     │ │ │
│  │ CATALOG         │    │ • Inventory     │    │ │ • Filter Phase      │ │ │
│  │ (ai_infra/      │    │ • Health        │    │ │ • Rank Phase        │ │ │
│  │  catalog.py)    │    │                 │    │ │                     │ │ │
│  └────────┬────────┘    └────────┬────────┘    │ └─────────────────────┘ │ │
│           │                      │            └──────────────┬───────────┘ │
│           │                      │                         │             │
│           ▼                      ▼                         ▼             │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                    PROVIDER SOURCE                                  │  │
│  │  (ai_infrastructure/profiles.py)                                    │  │
│  │  • Reads Desktop Executive inventory                                │  │
│  │  • Reads ProviderSpec Catalog                                       │  │
│  │  • Reads Founder cloud credentials                                  │  │
│  │  • Builds ProviderProfile tuple per-request                         │  │
│  │  • Availability = f(spec, inventory, credentials)                   │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                    │                                      │
└────────────────────────────────────┼──────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          AI CAPABILITY SERVICE                              │
│  (ai_infrastructure/service.py)                                            │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  CapabilityBroker (Kernel Service)                                     │ │
│  │  ┌─────────────────────────────────────────────────────────────────┐   │ │
│  │  │ CapabilityBroker.select(TaskProfile, ProviderProfile[])          │   │ │
│  │  │   → Filter (13 hard constraints)                                 │   │ │
│  │  │   → Quality Floor                                                │   │ │
│  │  │   → Rank (Policy ranking keys)                                   │   │ │
│  │  │   → Select first                                                 │   │ │
│  │  │   → DecisionRecord (sink)                                        │   │ │
│  │  └─────────────────────────────────────────────────────────────────┘   │ │
│  │                            │                                           │ │
│  │                            ▼                                           │ │
│  │  AiCapabilityService.wiring:                                          │ │
│  │  ├── CapabilityBroker (decides)                                       │ │
│  │  ├── ProviderSource (supplies profiles)                               │ │
│  │  ├── DecisionLedger (records)                                         │ │
│  │  ├── Approvals (optional, for gating)                                 │ │
│  │  └── Strong reasoning floor                                           │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                     ┌───────────────┼───────────────┐
                     ▼               ▼               ▼
         ┌──────────────────┐ ┌──────────────┐ ┌────────────────┐
         │  ModelRouter     │ │  Workers     │ │  Planner       │
         │  (Brain)         │ │  (Operator)  │ │  (Brain)       │
         │                  │ │              │ │                │
         │ ProviderSelector │ │ AiCapability │ │ AiCapability   │
         │ Protocol         │ │ Service      │ │ Service        │
         └────────┬─────────┘ └──────┬───────┘ └───────┬────────┘
                  │                │                  │
                  ▼                ▼                  ▼
         ┌──────────────────────────────────────────────────────┐
         │                   PROVIDER LAYER                     │
         │  ┌─────────────┐ ┌─────────────┐ ┌────────────────┐ │
         │  │ Ollama      │ │ Local       │ │ Cloud APIs     │ │
         │  │ Provider    │ │ Model       │ │ (Anthropic,    │ │
         │  │ (providers/ │ │ Provider    │ │  OpenAI, etc)  │ │
         │  │  ollama.py) │ │ (future)    │ │               │ │
         │  └─────────────┘ └─────────────┘ └────────────────┘ │
         └──────────────────────────────────────────────────────┘
                    │                    │              │
                    ▼                    ▼              ▼
         ┌──────────────────────────────────────────────────────────────────┐
         │                    EXECUTION LAYER                               │
         │  ┌─────────────┐ ┌─────────────┐ ┌────────────────────────────┐ │
         │  │ AiCapability│ │ ModelProvider │ │ Verification             │ │
         │  │ Service.    │ │ .generate()   │ │ (TextVerifier,           │ │
         │  │ select()    │ │               │ │  BrowserVerifier)        │ │
         │  │ → select()  │ │               │ │                          │ │
         │  │ → decide()  │ │               │ │                          │ │
         │  │ → execute() │ │               │ │                          │ │
         │  └─────────────┘ └─────────────┘ └────────────────────────────┘ │
         └──────────────────────────────────────────────────────────────────┘
                    │                    │              │
                    ▼                    ▼              ▼
         ┌──────────────────────────────────────────────────────────────────┐
         │                    VERIFICATION & LEARNING                       │
         │  ┌─────────────┐ ┌─────────────┐ ┌────────────────────────────┐ │
         │  │ TextVerifier│ │ Browser     │ │ BenchmarkStore (MISSING)   │ │
         │  │ (implemented)│ │ Verifier    │ │ • record_outcome()        │ │
         │  │             │ │ (implemented)│ │ • BenchmarkSample agg     │ │
         │  │             │ │             │ │ • effective_quality        │ │
         │  │             │ │             │ │   = measured if exists      │ │
         │  │             │ │             │ │   else declared             │ │
         │  └─────────────┘ └─────────────┘ └────────────────────────────┘ │
         └──────────────────────────────────────────────────────────────────┘
                    │
                    ▼
         ┌──────────────────────────────────────────────────────────────────┐
         │                    AI INFRASTRUCTURE EXECUTIVE (MISSING)         │
         │  ┌─────────────┐ ┌─────────────┐ ┌────────────────────────────┐ │
         │  │ Discovery   │ │ Probing     │ │ Benchmarking               │ │
         │  │ Actions     │ │ Actions     │ │ Actions                    │ │
         │  │ (subprocess,│ │ (health,    │ │ (run test prompts,         │ │
         │  │  fs, reg,   │ │  version,   │ │  measure quality/         │ │
         │  │  http)      │ │  caps)      │ │  latency/throughput)      │ │
         │  └─────────────┘ └─────────────┘ └────────────────────────────┘ │
         │                          │                                      │
         │                          ▼                                      │
         │  ┌─────────────────────────────────────────────────────────────┐│
         │  │                    INSTALLATION ACTIONS                      ││
         │  │  (with Founder approval via Permission System)              ││
         │  └─────────────────────────────────────────────────────────────┘│
         │                          │                                      │
         │                          ▼                                      │
         │  ┌─────────────────────────────────────────────────────────────┐│
         │  │  FEEDS:  Inventory → ProviderSource → Broker               ││
         │  │          Benchmarks → BenchmarkStore → Broker              ││
         │  │          Recommendations → Executive Task Queue            ││
         │  └─────────────────────────────────────────────────────────────┘│
         └──────────────────────────────────────────────────────────────────┘
```

---

## Critical Dependency Chains

### Chain 1: Request → Decision → Execution (Working)
```
Request → ModelRouter → AiCapabilityService.decide()
         → CapabilityBroker.select(TaskProfile, ProviderProfile[])
         → BrokerDecision
         → AiCapabilityService.select() → ModelProvider
         → ModelProvider.generate()
         → Verification → Evidence
         → Memory
```

### Chain 2: Bootstrap Inventory (Partial)
```
Launcher Startup
    ↓
Desktop Executive Scan (MB030) → Inventory
         ↓
ProviderSource.profiles() → ProviderProfile[]
         ↓
AiCapabilityService(CapabilityBroker, ProviderSource, Ledger, Approvals)
         ↓
ModelRouter → AiCapabilityService (ProviderSelector protocol)
         ↓
System ready for "reasoning" capability
```

### Chain 3: Missing Feedback Loop (BROKEN)
```
Execution → Verification → Evidence
    ↓
BenchmarkStore.record_outcome()  ← MISSING
         ↓
BenchmarkStore aggregates by (provider, ai_capability, task_class)
         ↓
ProviderProfile.effective_quality = benchmark (measured) or declared
         ↓
Broker decisions improve over time
```

### Chain 4: AI Infrastructure Executive (MISSING)
```
Executive (Worker) → Discovery Actions → Inventory
                                    ↓
                        ProviderSource → Broker
                                    ↓
                        Benchmark Actions → BenchmarkStore
                                    ↓
                              Verification → Broker.record_outcome()
                                    ↓
                              BenchmarkStore → effective_quality
                                    ↓
                              Broker decisions improve
```

---

## Component Interface Contracts

### CapabilityBroker (Kernel Service)
```python
class CapabilityBroker:
    def __init__(self, policy: SelectionPolicy, sink: Sink, clock: Clock)
    def select(task: TaskProfile, providers: list[ProviderProfile]) -> BrokerDecision
    def replay(record: DecisionRecord) -> BrokerDecision
    # State: policy, sink, clock, records[]
```

### AiCapabilityService (Wiring Layer)
```python
class AiCapabilityService:
    def __init__(broker, providers: ProviderSource, ledger, approvals, strong_floor, task_ids, clock)
    def decide(request) -> SelectionOutcome
    def select(request) -> Selection  # raises on refusal
    def report(limit) -> BrokerReport
```

### ProviderSource (Inventory Supplier)
```python
class ProviderSource:
    def __init__(inventory_provider, specs, enabled_cloud)
    def profiles() -> tuple[ProviderProfile]
    def available() -> tuple[ProviderProfile]
    def counts() -> (available, total)
    def has_scan() -> bool
```

### ModelRouter (Brain's Door)
```python
class ModelRouter:
    def __init__(registry: PluginRegistry, selector: ProviderSelector)
    def select(ctx: RoutingContext) -> BrokerDecision
    def select_provider(ctx: RoutingContext) -> ModelProvider
    def generate(prompt, ctx, context) -> str
```

### ModelProvider (Plugin Specialization)
```python
class ModelProvider(Plugin):
    CAPABILITY_NAME = "generate_text"
    def generate(prompt, context, **opts) -> str
    def invoke(capability, payload) -> InvocationResult
```

---

## Missing Links (Red = Broken)

| Link | Status | Fix Required |
|------|--------|--------------|
| `Broker.record_outcome()` → `BenchmarkStore` | ❌ Missing | Implement `BenchmarkStore` + `Broker.record_outcome()` |
| `BenchmarkStore` → `ProviderProfile.effective_quality` | ❌ Missing | Implement `BenchmarkStore` + `effective_quality` logic |
| `Verification` → `Broker.record_outcome()` | ❌ Missing | Wire `TextVerifier`/`BrowserVerifier` → `Broker.record_outcome()` |
| `AI Infrastructure Executive` | ❌ Missing | Implement as Worker with Discovery/Probing/Benchmark Actions |
| `BenchmarkStore` → `ProviderProfile.effective_quality` | ❌ Missing | Feed benchmarks into `effective_quality` property |
| `Executive` → `BenchmarkStore` | ❌ Missing | Executive runs benchmarks → feeds `BenchmarkStore` |
| `Executive` → `ProviderSource` | ❌ Missing | Executive feeds inventory → `ProviderSource` |
| `RecommendationEngine` | ❌ Missing | Implement inert recommendation logic |

---

## Execution Order (Runtime)

```
1. Launcher.main()
   ├── DesktopExecutive.scan() → inventory
   ├── ProviderSource(inventory, catalog, credentials)
   ├── DecisionLedger()
   ├── ApprovalQueue()  [optional]
   ├── CapabilityBroker(policy, sink=ledger)
   ├── AiCapabilityService(broker, provider_source, ledger, approvals)
   ├── ModelRouter(registry, selector=AiCapabilityService)
   ├── RuntimeEngine(mission_control, config, clock, sleep, checkpoint_sink, approval_gate)
   ├── MissionControl()
   ├── Launcher.start() → RuntimeEngine.run_forever()
```

---

## Critical Path for Bootstrap

```
1. DesktopExecutive.scan() → inventory
2. ProviderSource(inventory) → ProviderProfile[]
3. CapabilityBroker + AiCapabilityService + ProviderSource
4. ModelRouter(selector=AiCapabilityService)
4. RuntimeEngine + MissionControl
5. Launcher → RuntimeEngine.run_forever()

RESULT: System can route "reasoning" capability

[PARALLEL] Implement AI Infrastructure Executive
    ├── Discovery Actions → inventory → ProviderSource
    ├── Probing Actions → health/version/caps → ProviderSource
    ├── Benchmark Actions → BenchmarkStore → effective_quality
    ├── Verification → record_outcome() → BenchmarkStore
    └── Installation Actions → new providers
```

---

*Generated from verified implementation and architecture documents.*