# AI Capability Broker Architecture

## Purpose
Documents the intelligence-selection kernel service that every component needing AI consults to determine *which* Provider should serve a request. Per `AI_CAPABILITY_BROKER_ARCHITECTURE.md` (Mission Brief 027) and Constitution Amendment 2 (§5.7, §16, §17).

---

## Frozen Constitution

### Constitution §5.7 (RESEARCH-BACKED — Amendment 2)
> **AI Capability Broker** — The single intelligence-selection service. Every component that needs AI — the Brain's Model Router and Planner, and every Worker that needs reasoning, vision, OCR, speech, or embeddings mid-task — asks the Broker *which* Provider should serve the request. **No other component may decide.**

**Owns exclusively:** Provider Registry, Capability Matrix, Decision Engine, Cost Model, Benchmark Store, Approval Policy, AI Asset Inventory, Recommendation Engine.

**Belongs in Shared Infrastructure because:**
- Both Brain and Operator need same answer to same question (ADR-0010)
- State (spend, approvals, benchmarks) must be singular across Operator Instances
- Must be consulted *before* dispatch, so cannot be a thing that is dispatched

**Boundary that keeps it here:** Broker **decides and never touches the machine**. Executes nothing, opens no connection, imports no provider SDK, spends nothing, retries nothing, grants no permission — it *requires* permission through §5.2. Output names already-registered Capability + parameters; caller runs through Operator like any other Capability. **Broker creates no new execution path.**

**Machine-touching counterpart:** **AI Infrastructure Executive** (Worker, §12, §16) — discovers, probes, benchmarks, inventories, installs (with Founder approval). Produces inputs Broker decides on; never decides itself.

### Constitution §16 Ownership Registry (FROZEN — Amendment 2)
| Component | Home | Rationale |
|-----------|------|-----------|
| **AI Capability Broker** | **Shared Infrastructure** (§5.7) | Both Brain's Model Router and Workers needing intelligence consult it; cost, approval, benchmark ledgers must be singular across Operator Instances. Decides; never executes, never touches Environment. |
| **AI Infrastructure Executive** | **Operator** (Worker, §12) | Machine-touching counterpart to Broker: discovers, probes, benchmarks, inventories, installs (with explicit Founder approval). Produces inputs Broker decides on; never decides itself. |

### Constitution §17 Terminology Freeze (FROZEN — Amendment 2)
| Term | Definition |
|------|------------|
| **AI Capability** | A *kind of intelligence* a Provider can supply — `reasoning`, `vision.ocr`, `speech.transcribe` (§5.7). **Distinct from Capability, never dispatchable on its own**: AI Capability is input to Provider selection; Capability is unit of execution. Written `lowercase.dotted`, Capabilities are `PascalCase.PascalCase` — mechanically distinguishable. |
| **Provider** | Any registered source of AI capability — local runtime, desktop application, cloud API, aggregator (§5.7). **Generalizes, does not replace, Reasoning Provider**: Reasoning Provider (§3.3) is a Provider offering `reasoning` AI Capability. Neither term may get third synonym. |

---

## Architecture Design (from `AI_CAPABILITY_BROKER_ARCHITECTURE.md`)

### 1. Kernel Service vs Executive Decision (Deliverable 1 — §2)
**Decision: AI Capability Broker = Kernel Service (Shared Infrastructure)**

**Why it fails as Executive:**
1. **Both sides need same answer** — Brain's Model Router + Operator's Workers → Shared Infrastructure condition (ADR-0010)
2. **Arrives too late** — Executive dispatched *by* Mission Control/Runtime; Broker needed *before* dispatch
3. **State must be singular** — spend, approvals, benchmarks = ledgers; two Operator Instances disagreeing = safety bug
4. **Executive-to-Executive calling = norm** — heaviest calling convention for most-called component = backwards

**Preserved from Executive argument:** Machine-touching work (scanning, probing, benchmarking, inventory) → **AI Infrastructure Executive** (Worker). Split is exact mirror of Mission Control ↔ Executives.

### 2. Position in System (§3.1)
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
(Orchestrator, Verification, Worker Runtime)
        │
        ▼
AI Infrastructure Executive
```

**Key property:** Broker has **no upward dependency** — not on Brain, Operator, Mission Control, Runtime. Safe to be called from everywhere.

### 3. Responsibilities (§3.2)
Broker owns exclusively:
1. **Provider Registry** — what intelligence exists
2. **Capability Matrix** — what each Provider can do (declared + observed)
3. **Decision Engine** — which Provider serves a given request
4. **AI Asset Inventory** — machine's AI ecosystem as last observed
5. **Recommendation Engine** — what would improve the ecosystem
6. **Cost Model** — what has been spent, what will be
7. **Benchmark Store** — how well each Provider actually performs
8. **Approval Policy** — what the founder must sign off
9. **Audit trail of every decision** — emitted, never kept private

### 4. Eight Prohibitions (§3.3 — Mechanically Testable)
1. **Never executes** — no Environment access, no network, no provider SDK imports
2. **Never decides *what* to do** — Brain's job
3. **Never discovers** — scanning = Environment access → AI Infrastructure Executive
4. **Never grants permission** — requires permission through §5.2
5. **Never spends** — estimates/records only
6. **Never retries** — Runtime = mechanical, Brain = strategic
7. **Never names a product in its own logic** — product names only in registry data/illustrative tables
8. **Never installs/downloads/removes** — recommendations are inert data

### 5. Input: `CapabilityRequest` (§3.4)
```python
CapabilityRequest(
    request_id,                 # caller-generated, for correlation
    ai_capability,              # "vision.ocr" — lowercase.dotted
    task_class,                 # coarse bucket for benchmarking, e.g. "plan"
    requester,                  # executive_id | "brain.planner" | "brain.model_router"
    objective_id, task_id,      # Mission Control correlation, optional
    constraints: RequestConstraints,
    hints: RequestHints,
)

RequestConstraints (hard — Provider failing any filtered out):
    privacy: unrestricted | local_only | no_third_party
    connectivity: online_permitted | offline_only
    max_latency_ms: None = unconstrained
    min_quality: floor on expected success probability
    required_context_tokens:
    required_modalities: e.g. ["image"] for vision
    licensing_use: personal | commercial — matched against Provider licence
    exclude_providers: re-ask after failure, never Broker-side loop
    max_cost: per-request ceiling; None = policy default

RequestHints (soft — influences ranking, never filters):
    prefer_provider: explicit founder preference
    prefer_speed_over_quality:
    expected_output_tokens: improves cost estimate
```
**Constraint/hint split load-bearing:** Stops preference silently overriding privacy rule; enables two clean algorithm phases.

### 6. Output: `BrokerDecision` (§3.5)
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
    tier,                       # rung of ladder (§6.2)
    execution_capability,       # PascalCase.PascalCase — what Operator dispatches
    execution_parameters,       # plain dict: model name, endpoint id, etc.
    expected_success,           # 0..1, with `confidence`
    confidence,                 # low when benchmark samples scarce
    rationale,                  # human-readable, founder-facing
)
```

**Three critical properties:**
- `execution_capability` = bridge — Broker output names existing Capability + parameters; caller resolves via Capability Registry, runs through Operator. **Broker creates no new execution path.**
- `rejected` = not debug output — MB027 Rule 15: every decision auditable; "why didn't it use the local one?" answer must be in record
- `alternatives` = what makes re-asking cheap — caller holds ranked runners-up

### 7. Failure Handling (§3.6)
| Situation | Behaviour | Why |
|-----------|-----------|-----|
| No Provider offers AI Capability | `NO_CAPABLE_PROVIDER`, full `rejected` list | Explicit auditable refusal; silent fallback = OCR served by text model hallucinating |
| Candidates exist, all below `min_quality` | `NO_CAPABLE_PROVIDER`, reason `quality_floor` | Confident wrong answer worse than refusal; Evidence discipline (Rule 8) |
| Only paid candidates remain | `APPROVAL_REQUIRED` — never `SELECTED` | Names cost, best free alternative, what founder permits |
| Selected Provider fails at execution | Caller reports outcome, re-asks with `exclude_providers` | Broker does not retry; failure degrades observed reliability |
| Inventory stale beyond bound | Decision returned; local/desktop marked `unverified`; `inventory_age_seconds` on record | Absence ≠ unknown (ADR-0016); stale inventory ≠ "you have no GPU" |
| Budget exhausted for period | Paid tiers filtered out entirely; free tiers selectable | Budget cap that merely warns is not a cap |
| Broker itself unavailable | Caller **fails the step**; does not choose Provider | Fallback = architecture this document prevents; undetectable in audit |

### 8. Verification Flow (§3.7)
```
CapabilityRequest ──▶ BrokerDecision(decision_id) ──▶ caller executes
                                                          │
                        Verification Subsystem (ADR-0011) ─┤
                                                          ▼
              Broker.record_outcome(decision_id, OutcomeReport)
                                                          │
                          BenchmarkSample ────────────────┘
                                   │
                                   ▼
                     aggregates by (provider, ai_capability, task_class)
                                   │
                                   ▼
                     input to the next decision (§6.3)
```

**Single most important rule:**
> **An outcome is successful when Verification says so, not when the provider call returned.**

`OutcomeReport.verdict` = Verification Verdict (ADR-0011), not HTTP status. Model returning fluent, confident, wrong answer must score as failure, or Benchmark Engine systematically prefers providers that fail articulately.

---

## Provider Registry (Deliverable 2 — §4)

### Descriptor: `ProviderDescriptor`
```python
ProviderDescriptor(
    provider_id,                # stable, unique, founder-readable
    display_name,
    provider_class,             # open vocabulary string
    offers,                     # [CapabilityOffer] — matrix rows
    execution_binding,          # PascalCase.PascalCase Capability + fixed params
    cost_profile,               # §9
    licensing,                  # LicenceTerms
    rate_limits,                # RateLimitPolicy
    requirements,               # HardwareRequirement — GPU/VRAM/RAM/disk/runtime
    availability,               # how presence determined
    version,
    provenance,                 # declared | discovered | self_registered
    registered_at, verified_at,
    health,                     # healthy | degraded | unreachable | unverified
)
```

### Registry Rules (Frozen)
1. **Descriptors only, never live objects** — registry holds descriptions; cannot invoke what it describes
2. **No provider known to Broker's code** — no enum, no `if provider_id == ...`, no vendor-named modules
3. **`provider_class` = open vocabulary string** — not enum; class of AI provider changed 3x in 3 years
4. **`execution_binding` must name already-registered Capability** — registration refused otherwise
5. **Registration idempotent by `provider_id`** — re-registration with changes = update with audit event

### Provider Classes (Illustrative, Non-Binding)
| `provider_class` | Meaning | Examples |
|------------------|---------|----------|
| `local_runtime` | Model served by inference runtime on this host | Ollama, LM Studio, llama.cpp |
| `desktop_application` | Installed AI app driven as application | Claude Desktop, ChatGPT Desktop, ComfyUI, Stable Diffusion, Whisper, VS Code AI |
| `cloud_api` | Hosted API over network | Anthropic, OpenAI, Gemini |
| `cloud_aggregator` | Hosted API routing to many models | OpenRouter |
| `remote_self_hosted` | Runtime founder operates on other hardware | VPS-hosted inference server |
| `embedded` | Intelligence bundled inside another tool | Editor's built-in completion |

### Three Registration Paths
| Provenance | Who Writes | Trust | Example |
|------------|------------|-------|---------|
| `declared` | Founder via Configuration | Highest — explicit intent | "I have OpenRouter key, free tier only" |
| `discovered` | AI Infrastructure Executive | Evidence-backed | "Ollama installed, 4 models" |
| `self_registered` | Executive that provides intelligence | Manifest-backed | Local Model Executive registering what it serves |

All produce `ProviderDescriptor`. Provenance = tie-breaker, never filter. **Observed reality wins** (Rule 8) when declared vs discovered disagree.

### Licensing = First-Class Filter
`LicenceTerms(licence_id, permits_commercial_use, permits_redistribution, requires_attribution, requires_paid_activation, source_url)`
- Provider whose licence doesn't permit request's `licensing_use` → **filtered out in Phase 1**, not warned about

### Availability (Per-Class Determination)
- `local_runtime` — endpoint responds **AND** named model in inventory
- `desktop_application` — app installed at known path, compatible version
- `cloud_api` / `cloud_aggregator` — credential in Config **AND** connectivity **AND** rate-limit headroom
- **Never assumed from descriptor existing** — unverified ≠ unavailable

---

## Decision Engine (Deliverable 3 — §6)

### Two-Phase Algorithm
**Phase 1 (Filter — hard constraints):** Privacy, connectivity, latency, quality floor, licensing, exclusions, max cost
**Phase 2 (Rank — soft hints):** Cheapest tier clearing quality floor; preferences influence ranking, never filter

**Refusal over silent fallback:** `NO_CAPABLE_PROVIDER` with full `rejected` list

### Tier Ladder (Derived from Cost + Locality, Not Class)
1. **Free Local** — `local_runtime`, `embedded` (no cost, offline)
2. **Free Remote** — `cloud_api` free tier, `cloud_aggregator` free
3. **Paid Local** — `desktop_application` requiring paid activation
4. **Paid Remote** — `cloud_api` paid, `cloud_aggregator` paid

**Quality Floor = Founder's Policy Knob** — not hardcoded. Broker enforces floor; founder sets via policy.

---

## Current Implementation Status

| Component | Architecture Status | Implementation Status | Notes |
|-----------|---------------------|----------------------|-------|
| **Provider Registry** | RESEARCH-BACKED (Amendment 2) | ❌ **NOT IMPLEMENTED** | Architecture only (MB027); `src/master_agent/broker/` does not exist |
| **Capability Matrix** | RESEARCH-BACKED | ❌ **NOT IMPLEMENTED** | Declared + observed matrix |
| **Decision Engine** | RESEARCH-BACKED | ❌ **NOT IMPLEMENTED** | Two-phase filter/rank |
| **AI Asset Inventory** | RESEARCH-BACKED | ❌ **NOT IMPLEMENTED** | Machine's AI ecosystem |
| **Recommendation Engine** | RESEARCH-BACKED | ❌ **NOT IMPLEMENTED** | What would improve ecosystem |
| **Cost Model** | RESEARCH-BACKED | ❌ **NOT IMPLEMENTED** | Spend tracking |
| **Benchmark Store** | RESEARCH-BACKED | ❌ **NOT IMPLEMENTED** | Observed performance aggregates |
| **Approval Policy** | RESEARCH-BACKED | ❌ **NOT IMPLEMENTED** | 8 founder policies |
| **Audit Trail** | RESEARCH-BACKED | ❌ **NOT IMPLEMENTED** | Every decision emitted |
| **AI Infrastructure Executive** | RESEARCH-BACKED | ❌ **NOT IMPLEMENTED** | Machine-touching counterpart |
| **Provider Registration Paths** | RESEARCH-BACKED | ❌ **NOT IMPLEMENTED** | declared/discovered/self_registered |
| **Licensing Filter** | RESEARCH-BACKED | ❌ **NOT IMPLEMENTED** | Phase 1 hard filter |
| **Availability Determination** | RESEARCH-BACKED | ❌ **NOT IMPLEMENTED** | Per-class logic |
| **Verification Feedback Loop** | RESEARCH-BACKED | ❌ **NOT IMPLEMENTED** | `record_outcome()` → `BenchmarkSample` |

**Status:** Architecture only (MB027). No implementation, no provider integration, no provider-specific code. Nothing under `src/` or `tests/` touched.

---

## Design vs Implementation Differences

| Area | Architecture Design | Implementation | Status |
|------|---------------------|----------------|--------|
| **Provider Registry** | Descriptors only, open vocabulary, idempotent registration | ❌ Not implemented | ❌ MISSING |
| **Decision Engine** | Two-phase (filter hard, rank soft); cheapest tier clearing quality floor | ❌ Not implemented | ❌ MISSING |
| **Broker Prohibitions** | 8 mechanically testable rules | ❌ Not implemented | ❌ MISSING |
| **Provider Classes** | Open vocabulary string (6 illustrative) | ❌ Not implemented | ❌ MISSING |
| **Registration Paths** | declared/discovered/self_registered with provenance | ❌ Not implemented | ❌ MISSING |
| **Licensing Filter** | Phase 1 hard filter | ❌ Not implemented | ❌ MISSING |
| **Availability** | Per-class, never assumed | ❌ Not implemented | ❌ MISSING |
| **Verification Loop** | `record_outcome()` → `BenchmarkSample` → next decision | ❌ Not implemented | ❌ MISSING |
| **AI Infrastructure Executive** | Worker that scans/probes/benchmarks/installs | ❌ Not implemented | ❌ MISSING |
| **Cost Model** | Spend tracking, budget caps | ❌ Not implemented | ❌ MISSING |
| **Approval Policy** | 8 founder policies | ❌ Not implemented | ❌ MISSING |
| **Recommendation Engine** | Inert data, never installs | ❌ Not implemented | ❌ MISSING |

---

## Open Questions

1. **Broker Implementation** — Architecture frozen (MB027, Amendment 2), but `src/master_agent/broker/` does not exist. Required for Model Router (MB032) and Workers needing intelligence mid-task.

2. **AI Infrastructure Executive Not Implemented** — Machine-touching counterpart (scans, probes, benchmarks, inventories, installs). Required for Broker's inventory freshness.

3. **Provider Discovery** — How does `discovered` provenance work without AI Infrastructure Executive? Chicken-and-egg: Broker needs inventory; Executive produces inventory; Executive needs Broker for intelligence?

4. **Quality Floor Calibration** — Founder sets via policy; how calibrated initially? No benchmark store exists yet.

5. **Cost Model Initialization** — Spend tracking starts at zero; budget caps need founder configuration.

6. **Approval Policy Defaults** — 8 policies need founder configuration; what are safe defaults?

7. **Recommendation Engine Output** — Inert data; how consumed? Future Executive reads recommendations and acts?

8. **Benchmark Store Seeding** — Aggregates by (provider, ai_capability, task_class); needs initial data or cold-start logic.

---

## Future Extraction Targets

1. `src/master_agent/broker/` — When implemented: Provider Registry, Decision Engine, Cost Model, Benchmark Store, Approval Policy
2. `src/master_agent/ai_infrastructure/` — AI Infrastructure Executive (when implemented)
3. `src/master_agent/plugins/model_router.py` — Already reads `ProviderSelector` protocol; will wire to Broker
4. `docs/adr/0017` — AI Capability Broker decision record (ratified)
5. `docs/adr/0018` — Broker learning loop (EVOLVABLE policy, deterministic procedure)
6. `tests/test_broker_architecture.py` — When created: import-parsing purity test (no network/subprocess, no vendor names)
7. `tests/test_broker_integration.py` — Already greps for 7 vendor names in `model_router.py`

---

## Wiki Links Added

- `[[KALPAVRIKSHA_VISION_V2.md]]` — Constitution §5.7, §16, §17 (Amendment 2)
- `[[FOUNDER_CONSTITUTION_FREEZE.md]]` — Freeze record, Amendment 2
- `[[AI_CAPABILITY_BROKER_ARCHITECTURE.md]]` — Primary source document
- `[[ARCHITECTURE.md]]` — Implementation map §5 Model Router
- `[[MISSION_CONTROL_ARCHITECTURE.md]]` — Coordination layer, registries
- `[[RUNTIME_ENGINE_ARCHITECTURE.md]]` — Runtime loop, ApprovalGate
- `[[MEMORY_ARCHITECTURE.md]]` — Memory (cost/benchmark ledgers)
- `[[PERSISTENCE_ARCHITECTURE.md]]` — Operational persistence
- `[[01_executive_brain.md]]` — Brain (Model Router consults Broker)
- `[[02_constitution.md]]` — Constitution summary
- `[[03_universal_executive_operator.md]]` — Operator (Workers needing intelligence)
- `[[04_shared_infrastructure.md]]` — Shared Infrastructure (Broker home)
- `[[05_memory_system.md]]` — Memory (durable ledgers)
- `[[06_runtime_engine.md]]` — Runtime (mechanical retry vs strategic)
- `[[07_mission_control.md]]` — Mission Control (approval queue, audit)
- `[[08_persistence_architecture.md]]` — Persistence (separate concern)
- `[[system_overview.md]]` — System overview
- `[[docs/adr/0010]]` — Shared Infrastructure layer
- `[[docs/adr/0011]]` — Verification independent subsystem
- `[[docs/adr/0012]]` — Knowledge Lifecycle
- `[[docs/adr/0017]]` — AI Capability Broker (ratified)
- `[[docs/adr/0018]]` — Broker learning loop

---

*Document created from verified source only. No Broker capabilities redesigned. Terminology preserved exactly. Frozen Constitution/Architecture/Implementation separated. Open questions recorded without resolution.*