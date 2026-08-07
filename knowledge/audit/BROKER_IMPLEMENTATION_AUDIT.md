# AI Capability Broker Implementation Audit

## Source
- Architecture: `AI_CAPABILITY_BROKER_ARCHITECTURE.md`, `KALPAVRIKSHA_VISION_V2.md` §5.7
- Implementation: `src/master_agent/broker/broker.py`, `decision.py`, `policy.py`, `profiles.py`
- Freeze: `FOUNDER_CONSTITUTION_FREEZE.md` Amendment 2

## Classification Legend
- **A** = Implementation Bug
- **B** = Missing Implementation Required by Frozen Architecture
- **C** = Intentional Founder Edition Limitation
- **D** = Future Evolution / Scalability Item
- **E** = Requires ADR Decision
- **F** = Documentation Gap

---

## Component Audit

### 1. Provider Registry

**Architecture Design** (`AI_CAPABILITY_BROKER_ARCHITECTURE.md` §4)
> The Broker owns the Provider Registry — what intelligence exists. Descriptors only, never live objects. No provider known to Broker's code. Registration idempotent by `provider_id`.

**Current Implementation**
- **Location**: `src/master_agent/broker/profiles.py` — `ProviderProfile` dataclass
- **Source**: `src/master_agent/ai_infrastructure/profiles.py` — `ProviderSource.profiles()` builds profiles from Desktop Executive inventory
- **Registry Storage**: No persistent registry in Broker package. Profiles are passed into `CapabilityBroker.select()` as `list[ProviderProfile]` argument
- **Registration**: No registration API in Broker. `ProviderSource` constructs profiles from `ProviderSpec` catalog + Desktop Executive inventory

**Missing Pieces**
- No persistent Provider Registry in Broker package (profiles passed in per-call)
- No registration API (`register_provider()`, `update_provider()`)
- No provider health monitoring in Broker
- `ProviderSource` rebuilds profiles on every call (no caching)

**Dependencies**
- Desktop Executive machine scan (MB030)
- `ProviderSpec` catalog (`src/master_agent/ai_infrastructure/catalog.py`)
- Founder-declared credentials for cloud providers

**Classification**: **B** — Missing Implementation Required by Frozen Architecture
> Architecture specifies Provider Registry as Broker-owned component. Current implementation passes profiles as transient argument, no persistent registry.

---

### 2. Decision Engine

**Architecture Design** (`AI_CAPABILITY_BROKER_ARCHITECTURE.md` §6)
> Two-phase algorithm: Phase 1 (Filter — hard constraints), Phase 2 (Rank — cheapest tier clearing quality floor). Refusal over silent fallback.

**Current Implementation** (`src/master_agent/broker/broker.py`)
- **Filter Phase** (`_reject()` method): 13 hard constraints checked in order:
  1. `NO_CAPABILITY` — provider doesn't offer capability
  2. `EXCLUDED` — provider in exclude list
  3. `UNAVAILABLE` — provider not available
  4. `NEEDS_NETWORK` — offline task but provider needs network
  5. `CLOUD_FORBIDDEN` — policy forbids cloud, provider is cloud
  6. `PAID_FORBIDDEN` — policy forbids paid, provider not free
  7. `NOT_PRIVATE` — sensitive task, provider not private
  8. `NEEDS_APPROVAL` — provider requires approval
  9. `OVER_COST` — exceeds max_cost
  10. `OVER_LATENCY` — exceeds max_latency_ms
  11. `CONTEXT_TOO_SMALL` — context window too small
  12. `BELOW_FLOOR` — effective_quality < quality floor
- **Rank Phase** (`ranking_key()` in `policy.py`): Multi-key sort by policy's `ranking` tuple (e.g., `BY_COST`, `BY_QUALITY`, `BY_LATENCY`, `BY_LOCALITY`, `BY_PRIVACY`), ties broken by `provider_id`
- **Selection**: First ranked provider after floor
- **Refusal**: Full rejection list with reasons (`NO_PROVIDER_AVAILABLE`)

**Missing Pieces**
- No pluggable ranking strategies (hardcoded ranking keys)
- No support for multi-objective optimization (single linear ranking)

**Classification**: **3** — Implemented
> Full two-phase filter→rank engine implemented per architecture.

---

### 3. CapabilityRequest / SelectionRequest

**Architecture Design** (`AI_CAPABILITY_BROKER_ARCHITECTURE.md` §3.4)
> `CapabilityRequest(ai_capability, task_class, requester, objective_id, task_id, constraints, hints)`

**Current Implementation**
- **Broker side** (`broker.py`): `TaskProfile` dataclass with fields:
  - `capability`, `task_id`, `sensitivity`, `min_quality`, `max_cost`, `max_latency_ms`, `required_context_tokens`, `offline`, `exclude_providers`, `requester`
- **Model Router side** (`model_router.py`): `RoutingContext` → `SelectionRequest` conversion
- **AiCapabilityService** (`service.py`): Translates caller request → `TaskProfile`

**Classification**: **3** — Implemented
> Full request/response types implemented.

---

### 4. BrokerDecision / ProviderSelection

**Architecture Design** (`AI_CAPABILITY_BROKER_ARCHITECTURE.md` §3.5)
> `BrokerDecision(outcome, selection, alternatives, rejected, cost_estimate, approval, inventory_age_seconds, policy_version, inputs_digest)`

**Current Implementation** (`decision.py`)
- **BrokerDecision**: `outcome` (`SELECTED`/`NO_PROVIDER_AVAILABLE`), `task`, `policy_version`, `quality_floor`, `candidates`, `winner`, `reason`, `inputs_digest`, `decided_at`
- **Candidate**: `provider_id`, `eligible`, `reason`, `quality`, `cost`, `latency_ms`, `locality`, `rank`
- **DecisionRecord**: Immutable record with `decision`, `policy`, `providers` (full profiles at decision time)
- **Replay**: `replay()` reproduces decision from record; `replay_matches()` verifies byte-identical replay

**Classification**: **3** — Implemented
> Full decision types with audit trail and replay implemented.

---

### 5. Cost Model

**Architecture Design** (`AI_CAPABILITY_BROKER_ARCHITECTURE.md` §9)
> `CostProfile(tier, per_request_usd, monthly_cap_usd, currency)`. Cost Model tracks spend, enforces budget caps.

**Current Implementation**
- **ProviderProfile** (`profiles.py`): `cost` (per call), `is_free` property
- **TaskProfile**: `max_cost` constraint
- **Budget System** (MB038): `budgets.py` derives three deadlines (total, TTFT, stall) from provider throughput
- **Budget Derivation**: `budgets.derive()` uses provider throughput (prefill/decode tokens/sec) to compute deadlines
- **Token Economy**: `economy.py` tracks spend, `money_saved` from cache hits

**Missing Pieces**
- No monthly spend tracking/enforcement in Broker
- No budget cap enforcement (TaskProfile has `max_cost` but no periodic budget)
- Cost Model is per-request, not cumulative

**Classification**: **2** — Partial Implementation
> Per-request cost model implemented; cumulative spend tracking and budget caps missing.

---

### 6. Benchmark Store

**Architecture Design** (`AI_CAPABILITY_BROKER_ARCHITECTURE.md` §10)
> Aggregates `BenchmarkSample(provider_id, ai_capability, task_class, success_count, total_count, latency_ms_p50/p95, tokens_per_second)` by `(provider, ai_capability, task_class)`. **Observed beats declared** — Verification Verdict determines success.

**Current Implementation**
- **ProviderProfile** has: `benchmark: float | None`, `benchmark_confidence: float`
- `effective_quality` property returns `benchmark` if not None, else `quality`
- **No aggregation logic** in Broker — no `BenchmarkStore` class, no `record_outcome()` method
- **No Verification integration** — `verification/` package exists but no `Broker.record_outcome()`

**Classification**: **1** — Architecture Only
> Fields exist but no store, no aggregation, no Verification feedback loop.

---

### 7. Recommendation Engine

**Architecture Design** (`AI_CAPABILITY_BROKER_ARCHITECTURE.md` §8)
> Recommends what would improve ecosystem. Inert data — never installs/downloads.

**Current Implementation**
- **Not implemented**. No `RecommendationEngine` class, no recommendation logic.

**Classification**: **0** — Absent

---

### 7. Approval Policy

**Architecture Design** (`AI_CAPABILITY_BROKER_ARCHITECTURE.md` §12)
> 8 founder policies. Broker *requires* permission through §5.2, implements no parallel mechanism.

**Current Implementation**
- **Policy flags** (`policy.py`): `allow_cloud`, `allow_paid`, `require_private_for_sensitive`
- **ProviderProfile**: `requires_approval: bool`
- **Broker filter** (`_reject()`): Returns `NEEDS_APPROVAL` if `provider.requires_approval`
- **AiCapabilityService** (`service.py`): `_gated()` handles approval flow via `approvals` queue
- **Approval outcomes**: `NOT_REQUIRED`, `PENDING`, `GRANTED`, `DENIED`
- **FounderApprovalGate** (MB028.1): Wraps `PermissionSystemGate`, adds "ask founder; task waits" outcome

**Classification**: **3** — Implemented
> Full approval flow with Broker filter, service gating, and founder workflow.

---

### 8. Verification Learning Loop

**Architecture Design** (`AI_CAPABILITY_BROKER_ARCHITECTURE.md` §19)
> `Broker.record_outcome(decision_id, OutcomeReport)` → `BenchmarkSample` aggregates by `(provider, ai_capability, task_class)` → feeds next decision. **Outcome successful when Verification says so**.

**Current Implementation**
- **Not implemented**. No `record_outcome()` method in `CapabilityBroker`.
- No `BenchmarkStore` class.
- No integration with `verification/` package (`TextVerifier`, `BrowserVerifier` exist but not connected to Broker).

**Classification**: **0** — Absent

---

### 9. Provider Registry (Persistent)

**Architecture Design**
> Single source of truth for what intelligence exists. Descriptors only, idempotent registration.

**Current Implementation**
- **No persistent registry**. `ProviderSource.profiles()` rebuilds on every call from `ProviderSpec` catalog + Desktop Executive inventory.
- No `register_provider()`, `update_provider()`, `remove_provider()` APIs.
- Desktop Executive scan feeds inventory (`catalog.py` → `ProviderSpec`).

**Classification**: **1** — Architecture Only

---

## Summary Table

| Component | Architecture | Implementation | Classification |
|-----------|--------------|----------------|----------------|
| Provider Registry (persistent) | §4 | Transient profiles per-call | **B** — Missing Frozen Architecture |
| Decision Engine | §6 | Filter→Rank implemented | **3** — Implemented |
| CapabilityRequest/SelectionRequest | §3.4 | `TaskProfile`/`SelectionRequest` | **3** — Implemented |
| BrokerDecision/ProviderSelection | §3.5 | Full types + replay | **3** — Implemented |
| Cost Model | §9 | Per-request only | **2** — Partial |
| Benchmark Store | §10 | Fields only, no store | **1** — Architecture Only |
| Recommendation Engine | §8 | Not implemented | **0** — Absent |
| Approval Policy | §12 | Full flow implemented | **3** — Implemented |
| Verification Learning Loop | §19 | Not implemented | **0** — Absent |
| Provider Registry (persistent) | §4 | Transient per-call | **B** — Missing Frozen Architecture |

---

*Generated from verified implementation only. No redesigns proposed.*