# AI Capability Broker Bootstrap Analysis

## Source
- Architecture: `AI_CAPABILITY_BROKER_ARCHITECTURE.md` §2 (Kernel Service vs Executive)
- Implementation: `src/master_agent/broker/`, `src/master_agent/ai_infrastructure/`, `src/master_agent/ai_infrastructure/profiles.py`
- Constitution: `KALPAVRIKSHA_VISION_V2.md` §5.7, §16

---

## The Chicken-and-Egg Problem

### Architecture Definition (MB027, Amendment 2)

> **The split is exact:**
> 
> | | AI Capability Broker (kernel service) | AI Infrastructure Executive (Worker) |
> |---|---|---|
> | Touches the machine | **Never** | Always — that is its whole job |
> | Decides which Provider | Always — nothing else may | Never |
> | Holds registry, matrix, ledger, benchmarks | Yes | No — it *produces inputs* to them |
> | Invoked by | Direct call, as Shared Infrastructure | Dispatch, as any Executive |
> | Import of a provider SDK | Forbidden, mechanically | Permitted, in its own adapter |

### The Circular Dependency

```
AI Infrastructure Executive (Worker)
        ↓ discovers, probes, benchmarks, inventories
Capability Inventory (Provider Profiles)
        ↓ feeds
AI Capability Broker (Kernel Service)
        ↓ decides
Model Router / Workers
        ↓ execute
Provider
        ↓ (generates outcomes)
Verification
        ↓ feeds back
Benchmark Store (Broker)
        ↓ improves
Broker Decisions
        ↓
AI Infrastructure Executive
        ↓ (needs Broker for intelligence mid-task?)
```

### The Core Problem

**The Broker needs an inventory to make decisions.**
**The Executive produces the inventory.**
**But the Executive is a Worker that may need intelligence (Broker) to do its job.**

From `AI_CAPABILITY_BROKER_ARCHITECTURE.md` §11:
> **AI Infrastructure Executive** — The machine-touching counterpart to the Broker: discovers, probes, benchmarks, inventories, and — with explicit Founder approval — installs. **Produces the inputs the Broker decides on; never decides itself.**

But the Executive is a **Worker** (§12, §16). Workers are invoked through the Operator. The Operator uses the Broker for intelligence. So:

```
Executive (Worker) needs intelligence → asks Broker
Broker needs inventory → asks Executive
Executive needs intelligence → asks Broker
```

---

## Current Implementation State

### What Exists

| Component | Status | Notes |
|-----------|--------|-------|
| **CapabilityBroker** (kernel) | ✅ Implemented | `src/master_agent/broker/broker.py` — pure decision engine |
| **CapabilityBroker.select()** | ✅ Implemented | Takes `TaskProfile` + `list[ProviderProfile]` → `BrokerDecision` |
| **ProviderSource** | ✅ Implemented | `ai_infrastructure/profiles.py` — builds profiles from Desktop Executive inventory |
| **ProviderSpec Catalog** | ✅ Implemented | `ai_infrastructure/catalog.py` — `PROVIDER_CATALOG` tuple of `ProviderSpec` |
| **Desktop Executive** | ✅ Implemented | MB030 — 12 capabilities for machine scan |
| **AiCapabilityService** | ✅ Implemented | `ai_infrastructure/service.py` — wiring layer (Broker + ProviderSource + Ledger + Approvals) |
| **ModelRouter** | ✅ Implemented | `plugins/model_router.py` — uses `ProviderSelector` protocol → `AiCapabilityService` |
| **CapabilityBroker Replay** | ✅ Implemented | `replay()` reproduces decisions from records |

### What Does NOT Exist

| Component | Status | Impact |
|-----------|--------|--------|
| **AI Infrastructure Executive** | ❌ Not implemented | No machine scanning, probing, benchmarking, inventory capture |
| **Benchmark Store** | ❌ Not implemented | No `record_outcome()`, no `BenchmarkStore` |
| **Verification Learning Loop** | ❌ Not implemented | No `Broker.record_outcome()`, no Verification integration |
| **Recommendation Engine** | ❌ Not implemented | No `RecommendationEngine` |
| **Cost Model (cumulative)** | ❌ Not implemented | Only per-request budgets (MB038) |
| **Provider Registry (persistent)** | ❌ Not implemented | Profiles rebuilt per-call from inventory |
| **Executive Capabilities** | ❌ Not implemented | No `ExecutivePlugin`, no Executive Actions |

---

## The Bootstrap Gap

### Current Flow (What Works)

```
1. Launcher starts
2. Submits machine scan objective via Mission Control
3. Desktop Executive runs scan → produces inventory
4. Launcher constructs ProviderSource with inventory
5. AiCapabilityService constructed with Broker + ProviderSource
6. ModelRouter wired to AiCapabilityService
7. System ready for requests
```

**This works for the "reasoning" capability** because the Model Router only needs the Broker to select a provider for reasoning. The Broker doesn't need to know about the Executive — it just needs provider profiles.

### The Gap (What Doesn't Work)

| Capability | Status | Reason |
|------------|--------|--------|
| **reasoning** | ✅ Works | Model Router → Broker → ProviderSource → profiles → decision |
| **vision.ocr** | ⚠️ Broken | No provider offers it; no Executive to discover/probe |
| **speech.transcribe** | ⚠️ Broken | Same |
| **embedding** | ⚠️ Broken | Same |
| **Benchmark feedback** | ❌ Missing | No `record_outcome()`, no BenchmarkStore |
| **Executive self-discovery** | ❌ Missing | Executive needs Broker for intelligence mid-task |
| **Executive benchmarking** | ❌ Missing | Executive needs to probe/benchmark providers |
| **Executive installation** | ❌ Missing | Executive needs to install with approval |

---

## The Bootstrap Sequence (What Should Exist)

### Required Bootstrap Sequence

```
PHASE 0: CORE INFRASTRUCTURE (Already exists)
├── CapabilityBroker kernel (decision engine)
├── AiCapabilityService (wiring)
├── ProviderSpec catalog (static declarations)
├── Desktop Executive (machine scan capabilities)
└── AiCapabilityService → ModelRouter wiring

PHASE 1: BOOTSTRAP INVENTORY (Manual/Founder-driven)
├── Founder declares cloud credentials in config
├── Launcher runs Desktop Executive scan at startup
├── AiCapabilityService builds initial ProviderSource from:
│   ├── Static ProviderSpec catalog (declared capabilities)
│   ├── Desktop Executive inventory (local runtimes, desktop apps)
│   └── Founder-declared cloud credentials
└── System can now route "reasoning" requests

PHASE 2: EXECUTIVE BOOTSTRAP (Requires AI Infrastructure Executive)
├── AI Infrastructure Executive implemented as Worker (Operator)
├── Executive registers with Mission Control
├── Executive can:
│   ├── Discover installed providers (subprocess, filesystem, registry)
│   ├── Probe providers (health, version, capabilities)
│   ├── Benchmark providers (run test prompts, measure quality/latency)
│   └── Install providers (with Founder approval)
├── Executive feeds inventory → ProviderSource → Broker
├── Broker decisions improve with fresh inventory + benchmarks
└── Executive can now use Broker for intelligence mid-task

PHASE 3: VERIFICATION LOOP (Requires BenchmarkStore)
├── Broker.record_outcome(decision_id, OutcomeReport)
├── BenchmarkStore aggregates by (provider, ai_capability, task_class)
├── Benchmarks feed Broker's effective_quality
├── Decisions improve over time
└── Executive re-benchmarks periodically
```

---

## The Circular Dependency Resolution

### The Problem

```
Executive (Worker) needs intelligence → asks Broker
Broker needs inventory → asks Executive
Executive needs intelligence → asks Broker
```

### The Resolution (Per Architecture)

**The Executive does NOT need the Broker for its core discovery work.**

From `AI_CAPABILITY_BROKER_ARCHITECTURE.md` §11:
> **AI Infrastructure Executive** — discovers, probes, benchmarks, inventories, and — with explicit Founder approval — installs. **Produces the inputs the Broker decides on; never decides itself.**

The Executive's core job is **machine-touching**: subprocess, filesystem, network probing, registry reading. These are **deterministic operations** that don't require AI intelligence. They are implemented as **Actions** on the `LocalExecutor`.

The Executive only needs the Broker for **judgment calls**:
- "Is this benchmark result good enough?"
- "Should I recommend installing this provider?"
- "What priority should I assign to this discovery?"

These are **rare, high-level decisions** — not the bulk of discovery work.

### The Resolution

```
1. Executive runs DISCOVERY/PROBING actions locally (no Broker needed)
   ├── subprocess.run("ollama list")
   ├── filesystem.scan("/Applications")
   ├── registry.query("HKEY_LOCAL_MACHINE\\...")
   └── http.probe("http://localhost:11434")

2. Executive builds raw inventory → ProviderSource → Broker

3. Broker makes decisions (which provider for reasoning)

4. When Executive needs JUDGMENT:
   Executive → AiCapabilityService → Broker → Decision
   (rare, high-level, not in hot path)

5. Executive runs BENCHMARKS (deterministic Actions)
   ├── run test prompt on provider
   ├── measure latency, quality
   └── feed results → BenchmarkStore → Broker

6. Verification feeds back → Broker.record_outcome() → BenchmarkStore
```

---

## Dependency Ordering (Implementation Sequence)

### Phase 0: Already Done ✅
1. CapabilityBroker kernel (`broker/`)
2. AiCapabilityService wiring (`ai_infrastructure/service.py`)
3. ProviderSpec catalog (`ai_infrastructure/catalog.py`)
4. ProviderSource from Desktop Executive (`profiles.py`)
5. ModelRouter → AiCapabilityService wiring
6. CapabilityBroker replay

### Phase 1: Bootstrap Inventory (Week 1-2)
1. **Desktop Executive scan at launcher startup** — already implemented (MB030)
2. **ProviderSource rebuilt per-request** — already implemented (`profiles.py`)
3. **Launcher constructs AiCapabilityService at startup** — needs wiring in launcher
2. **ModelRouter wired to AiCapabilityService** — needs wiring in launcher
3. **Static ProviderSpec catalog** — already in `catalog.py`

### Phase 2: AI Infrastructure Executive (Week 3-6)
1. **Executive as Worker** — register with Mission Control
2. **Discovery Actions** — subprocess, filesystem, registry, HTTP probe
2. **Probing Actions** — health checks, version detection, capability enumeration
3. **Benchmark Actions** — run test prompts, measure quality/latency/throughput
4. **Installation Actions** — with Founder approval (Permission System)
4. **Executive Registration** — Mission Control registration via adapter
5. **Inventory Feed** → ProviderSource → Broker

### Phase 3: Verification Learning Loop (Week 7-10)
1. **BenchmarkStore** — aggregate by (provider, ai_capability, task_class)
2. **Broker.record_outcome(decision_id, OutcomeReport)** — called by callers
2. **Verification Integration** — `TextVerifier`/`BrowserVerifier` outcomes → Broker
3. **Effective Quality** — `effective_quality` = benchmark if measured else declared
4. **Executive Re-benchmarking** — periodic re-benchmarking Actions

### Phase 4: Recommendation Engine (Week 11+)
1. **RecommendationEngine** — analyzes gaps in inventory/benchmarks
2. **Recommendations** → Executive task queue (with Founder approval for installs)

---

## Critical Path

```
Launcher startup
    ↓
Desktop Executive scan (MB030) → inventory
    ↓
ProviderSource(profiles from inventory + catalog + credentials)
    ↓
AiCapabilityService(CapabilityBroker + ProviderSource + Ledger + Approvals)
    ↓
ModelRouter → AiCapabilityService (ProviderSelector protocol)
    ↓
System ready for "reasoning" requests
    ↓
[PARALLEL] AI Infrastructure Executive development
    ↓
Executive feeds fresh inventory + benchmarks → Broker decisions improve
    ↓
BenchmarkStore + Verification loop → decisions improve over time
```

---

## Blocking Dependencies

| Component | Blocks | Blocked By |
|-----------|--------|------------|
| AI Infrastructure Executive | Benchmark freshness, Executive self-discovery, Installation | None (can start now) |
| BenchmarkStore | Verification learning loop, Effective quality | AI Infrastructure Executive (to run benchmarks) |
| Verification Learning Loop | Continuous improvement, Effective quality | BenchmarkStore + Verification integration |
| Recommendation Engine | Ecosystem improvement | BenchmarkStore + Inventory |
| Provider Registry (persistent) | Stable provider IDs, Health monitoring | AI Infrastructure Executive |

---

## Conclusion

**The bootstrap sequence EXISTS and is PARTIALLY IMPLEMENTED.**

**What works today:** Static catalog + Desktop Executive scan → ProviderSource → Broker → ModelRouter for "reasoning" capability.

**What's missing:** The **AI Infrastructure Executive** — the Worker that discovers, probes, benchmarks, and installs providers. Without it:
- Inventory is static (only what Desktop Executive scans at startup)
- No benchmarks → Broker uses declared quality only
- No verification loop → no learning
- No installation capability

**The circular dependency is RESOLVED by architecture:** Executive does NOT need Broker for discovery/probing/benchmarking (deterministic Actions). Executive only needs Broker for rare high-level judgments.

**Next Step:** Implement **AI Infrastructure Executive** as a Worker (Operator) — this unblocks everything else.

---

*Generated from verified implementation and architecture documents. No redesigns proposed.*