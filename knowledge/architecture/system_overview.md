# System Overview

## Purpose
Provides a high-level architectural overview of the Kalpavriksha project — the orchestration layer between human intention and software execution, implementing the Kalpavriksha Principle: **Intent → Plan → Delegate → Execute → Verify → Learn → Report**.

## Scope
Covers the complete system architecture per the Frozen Constitution (`docs/architecture/KALPAVRIKSHA_VISION_V2.md` Revision 3), including the three-layer separation (Executive Brain, Shared Infrastructure, Universal Executive Operator), module boundaries, data flow, plugin/Worker contracts, and the Runtime Engine heartbeat.

## Dependencies
- `ARCHITECTURE.md` (implementation map — module file layout, present data flow)
- `docs/architecture/KALPAVRIKSHA_VISION_V2.md` (the Frozen Constitution — authoritative for architectural decisions)
- `docs/architecture/FOUNDER_CONSTITUTION_FREEZE.md` (freeze declaration and audit trail)
- `MEMORY_ARCHITECTURE.md` (six-layer memory design)
- `FILESYSTEM_CAPABILITIES.md` (Action Contract pattern for local capabilities)
- `BROWSER_WORKER_ARCHITECTURE.md` (reference Worker implementation)
- `MISSION_CONTROL_ARCHITECTURE.md` (runtime coordination layer)
- `RUNTIME_ENGINE_ARCHITECTURE.md` (autonomous execution loop)
- `PERSISTENCE_ARCHITECTURE.md` (event log + snapshot recovery)
- `AI_CAPABILITY_BROKER_ARCHITECTURE.md` (intelligence selection kernel service)

## Last Updated
2026-08-02

## References
- `ARCHITECTURE.md` — current implementation detail (module boundaries §4, Model Router §5, open questions §6)
- `KALPAVRIKSHA_VISION_V2.md` — constitutional authority (all §1–§22, Status tags in §18)
- `FOUNDER_CONSTITUTION_FREEZE.md` — freeze record and Section Status Registry (§4)
- `MEMORY_ARCHITECTURE.md` — Layers 1–3 implemented, Layers 4–6 interfaces
- `FILESYSTEM_CAPABILITIES.md` — 14 filesystem capabilities via Action Contract
- `BROWSER_WORKER_ARCHITECTURE.md` — 9 atomic Browser Actions, generic verification package
- `MISSION_CONTROL_ARCHITECTURE.md` — Event Bus, Executive/Capability Registries, Task Dispatcher, queues, Audit Stream
- `RUNTIME_ENGINE_ARCHITECTURE.md` — 8-state loop, ExecutiveGateway, mechanical retry, ApprovalGate
- `PERSISTENCE_ARCHITECTURE.md` — append-only event log + versioned snapshots, recovery
- `AI_CAPABILITY_BROKER_ARCHITECTURE.md` — Provider Registry, Capability Matrix, Decision Engine, cost/benchmark ledgers

## Status
**POPULATED FROM VERIFIED SOURCES** — not a template.

---

## 1. High-Level Architecture (Constitution §1–§6)

### 1.1 The Kalpavriksha Loop (Constitution §1)
```
Intent → Plan → Delegate → Execute → Verify → Learn → Report
```
Every interaction follows this loop. No step is optional. No step is bypassed.

### 1.2 Three-Layer Separation (Constitution §3, §4, §5, §6)
```
Executive Brain (decides what, how to structure, how to explain)
        │
Shared Infrastructure (one consistent source of truth both sides depend on)
        │
Universal Executive Operator (carries out what was decided, with accountability)
```
**Dependency direction only** — not sequential data flow. Brain and Operator never depend on each other's internals; both depend downward on Shared Infrastructure.

| Aspect | Executive Brain | Shared Infrastructure | Universal Executive Operator |
|--------|-----------------|----------------------|------------------------------|
| Role | Decides what and how to structure it, and how to explain it | Provides the one consistent source of truth both sides depend on | Carries out what was decided, with accountability |
| Modules | Intent Layer, Planner, Model Router, Reporter | Capability Registry, Permission System, Mission State, Memory, Configuration, Telemetry/Evidence aggregation, AI Capability Broker | Orchestrator, Verification Subsystem, Worker/Plugin Runtime, Environment Session Management |
| Reasoning-Provider calls | Yes | No | No |
| Which Provider serves a request | Asks; never decides | **Decides — AI Capability Broker (§5.7)** | Asks; never decides |
| Environment access | Never | Never | Only through a Worker, via an Environment Session it owns |
| Permission checks | Never issues, never checks | Holds and adjudicates every grant | Every step above READ_ONLY checked here, against Shared Infrastructure |
| Mission State | Reads (context) | Owns | Transitions it, through Shared Infrastructure's contract |
| Memory | Reads; nominates Knowledge Candidates | Owns; stores and serves | Writes Evidence into it, through Shared Infrastructure's contract |

---

## 2. Executive Brain (Constitution §3)

### 2.1 Intent Layer
Turns raw input into structured `Intent` (goal, constraints, context, success criteria). Owns follow-up clarification when ambiguous. **Not** "send raw string to a model."

**Current stand-in:** `cli.py`'s regex-based `parse_intent()` (Mission Briefs 001, 003.1, 005). The real Intent Layer is a stub pending the real Planner (`ROADMAP.md` item 1).

### 2.2 Planner
Takes an `Intent`, produces a `MissionPlan`: a DAG of `Step` objects, each naming a required **Capability** (never a specific Worker). Every `Step` also names an **Expected Outcome** (machine-checkable description of "done") so Verification has a concrete target.

Calls a Reasoning Provider through the Model Router. Reads recent Mission history and Permanent Knowledge (§9) as context.

### 2.3 Model Router
Single Reasoning Provider interface: `generate(prompt, context, **opts) -> ModelResponse`. Picks provider per call based on:
1. **Connectivity** — offline ⇒ Local Reasoning Provider only
2. **Privacy sensitivity** — sensitive tags stay local unless human overrides
3. **Task profile** — routine → local; strong reasoning needed → cloud
4. **Explicit user preference** — always wins

**Amendment 2 (MB027):** The Model Router **consults the AI Capability Broker (§5.7) to resolve which Reasoning Provider**, rather than implementing its own ranking. Its interface, role, and four criteria are unchanged.

### 2.4 Reporter
Takes Mission outcome + Evidence once Verification produces a Verdict, composes human-facing report (text today; voice later). Decides *how to explain* — a Brain-shaped judgment. Never touches Environment; only reads Evidence and Mission state through Shared Infrastructure.

**Current status:** Not yet built as distinct module — `cli.py`'s completion messages play this role today.

### 2.5 What the Brain Does NOT Do (Constitution §3.5)
- Does not execute capabilities
- Does not hold or check Permission grants
- Does not own Mission State (Shared Infrastructure does, §5.3)
- Does not persist Memory itself (Shared Infrastructure does)
- Does not verify outcomes (consumes Evidence; does not produce it)
- Does not know what an Environment Instance is — only that a Step requires a Capability

---

## 3. Shared Infrastructure (Constitution §5)

### 3.1 Capability Registry (formerly "Plugin Registry")
Single registry queried by both Brain's Model Router and Operator's Orchestrator. One lookup mechanism, one answer, regardless of who asks. Today: one component with two indices (plugin identity, capability → plugin). Future capability-resolution policy is EVOLVABLE.

### 3.2 Permission System
Single, consistent grant ledger across every Operator Instance. Risk tiers: `READ_ONLY | REVERSIBLE_WRITE | IRREVERSIBLE`. Permission Categories (orthogonal, descriptive): `READ | WRITE | MODIFY | DELETE | SYSTEM`.

**Mechanism:** `ALWAYS_FOR_CAPABILITY` grant **never** satisfies an `IRREVERSIBLE` check — destructive actions require fresh decision every time (ADR-0009). Relay pattern (outer approval carried down to inner grant key) unchanged (ADR-0005, ADR-0006).

### 3.3 Mission State
Owned here because a single Mission's Steps may be serviced by different Operator Instances (§8). State machine: `draft → planned → awaiting_approval → executing → verifying → completed | failed | cancelled`. Resolves ownership gap for `MissionManager`/`Mission` from prior audit.

### 3.4 Memory (Constitution §5.4, `MEMORY_ARCHITECTURE.md`)
Six layers, Layers 1–3 implemented, Layers 4–6 interfaces:

| Layer | Name | Scope | Status |
|-------|------|-------|--------|
| 1 | Conversation Memory | Current session | Implemented (`memory/conversation.py`) |
| 2 | Mission Memory | Current execution | Implemented (pre-existing `Mission` object + `MasterAgentSession.last_mission`) |
| 3 | Persistent Memory | Durable, this machine | Implemented (`SQLiteMemoryStore`) |
| 4 | Knowledge Memory | Durable facts/documents | Reserved — interface only (`KnowledgeMemory` in `memory/future.py`) |
| 5 | Vector Memory | Semantic recall | Future — interface only (`VectorMemory`) |
| 6 | Cloud Sync | Multi-device | Optional future — interface only (`CloudSyncMemory`) |

**Schema (Layer 3):** `missions` table (mission_id, title, intent_summary, status, approval_status, created_at, completed_at, execution_plan JSON, execution_result JSON, execution_time_seconds, artifacts JSON, errors JSON, outcome JSON) + `preferences` table (key, value JSON). Indexes on `completed_at` and `(status, completed_at)`.

**API:** `MemoryStore` ABC (storage contract) + `Memory` facade (single seam for rest of system). `MasterAgentSession` persists automatically at every terminal mission state.

### 3.5 Configuration
Environment roots, Reasoning Provider defaults, policy configuration — single source to prevent drift.

### 3.6 Telemetry and Audit (aggregated form)
Raw log emission happens locally at Worker/Operator Instance. Shared Infrastructure owns the durable, queryable, cross-Operator-Instance aggregation (same mechanism Memory provides). Evidence *is* the audited, verified subset of telemetry that made it into Memory.

### 3.7 AI Capability Broker (Constitution §5.7, Amendment 2, `AI_CAPABILITY_BROKER_ARCHITECTURE.md`)
**Kernel Service** (Shared Infrastructure) — not an Executive. Both Brain and Operator need the same answer to the same question.

**Owns exclusively:**
1. Provider Registry — what intelligence exists
2. Capability Matrix — what each Provider can do (declared + observed)
3. Decision Engine — which Provider serves a given request
4. AI Asset Inventory — machine's AI ecosystem as last observed
5. Recommendation Engine — what would improve the ecosystem
6. Cost Model — spend tracking
7. Benchmark Store — observed performance per (provider, ai_capability, task_class)
8. Approval Policy — what founder must sign off
9. Audit trail of every decision

**Eight prohibitions (mechanically testable):**
1. Never executes (no Environment access, no network, no provider SDK imports)
2. Never decides *what* to do (Brain's job)
3. Never discovers (scanning is Environment access → AI Infrastructure Executive)
4. Never grants permission (requires permission through §5.2)
5. Never spends (estimates/records only)
6. Never retries (Runtime = mechanical, Brain = strategic)
7. Never names a product in its own logic (product names only in registry data / illustrative tables)
8. Never installs/downloads/removes (recommendations are inert data)

**Input:** `CapabilityRequest(ai_capability: lowercase.dotted, task_class, requester, constraints[privacy, connectivity, max_latency_ms, min_quality, licensing_use, exclude_providers, max_cost], hints[prefer_provider, prefer_speed_over_quality, expected_output_tokens])`

**Output:** `BrokerDecision(outcome: SELECTED | APPROVAL_REQUIRED | NO_CAPABLE_PROVIDER, selection[execution_capability: PascalCase.PascalCase, execution_parameters], alternatives[], rejected[(provider_id, filter_reason)], cost_estimate, approval, inventory_age_seconds, policy_version, inputs_digest)`

**Verification loop:** Caller executes → Verification Subsystem produces Evidence → `Broker.record_outcome(decision_id, OutcomeReport)` → `BenchmarkSample` aggregates by (provider, ai_capability, task_class) → feeds next decision. **Outcome is successful when Verification says so, not when provider call returned.**

### 3.8 What Is Deliberately NOT Shared Infrastructure (Constitution §5.8)
- Environment Session Management (live handle belongs to Operator Instance that opened it)
- Mission Session (`MasterAgentSession` — Brain-adjacent glue, transitional)
- Machine scanning, provider probing, benchmarking, inventory, installation (→ AI Infrastructure Executive, an ordinary Worker)

---

## 4. Universal Executive Operator (Constitution §4)

### 4.1 Orchestrator
Walks `MissionPlan`, for each `Step`:
1. Resolves Capability → Worker via Shared Infrastructure's Capability Registry
2. Checks Permission System via Shared Infrastructure
3. Invokes Worker, captures result
4. Triggers Verification against Step's Expected Outcome
5. Applies retry/failure-branching policy (bounded, deterministic, scoped to this Operator Instance; never re-plans)

### 4.2 Worker Runtime (Constitution §12)
Every Capability implemented by a Worker (Action/Plugin) registered on Operator's Worker Runtime. Adding Worker #N costs one new file; never edits Capability Registry, Permission System, or Orchestrator.

**Composite Workers:** May orchestrate other Workers through Shared Infrastructure Capability Registry and Permission System, relaying already-obtained grant down to each sub-step (Rule 6, stated once).

### 4.3 Verification Subsystem (Constitution §10)
**Structurally independent from Execution** — runs alongside Operator (needs Environment access) but through its own contract, never through Worker's `invoke()`.

**Three-part boundary (Constitution §10.2):**
1. **Execution produces effects** — Worker's Action runs, returns Execution Result (did it run without error, what it output). Says nothing about real-world outcome.
2. **Verification produces Evidence** — Verification Subsystem re-observes Environment Instance, compares Observation against Expected Outcome (from Planner). Output: Verdict (matched / did not match / partially matched) + Observation + Expected Outcome = **Evidence**.
3. **Evidence flows back to Brain** — routed to Brain via Shared Infrastructure as input to "is Mission complete, or re-plan?"

**Why physically near Operator but architecturally separate:** Only Operator has Environment access. Verification uses its own "observe → compare against Expected Outcome" contract, never reuses Worker's `validate()`/`run()`, never folds result into plain Execution Result.

### 4.4 What the Operator Does NOT Do (Constitution §4.4)
- Does not decide what a Mission should accomplish
- Does not maintain private copy of Permission grants, Mission state, or Memory
- Does not nominate or promote Knowledge (produces Evidence; Brain + Promotion Review decide)

---

## 5. Implemented Components (from `ARCHITECTURE.md` §4, verified against source)

### 5.1 Local Executor (`executor/`) — Mission Brief 002
**Action Contract** (every local capability implements): name, description, risk tier, required parameters, `validate()`, `run()` → structured `ExecutionResult`.

`LocalExecutor.execute()`: looks up Action, validates parameters, checks Permission System, runs action, catches exceptions (never raw traceback), logs every execution (action, start/end time, duration, status).

**Permission relay:** Executor checks permission using own grant key distinct from Orchestrator's. Plugin adapter relays already-obtained approval down to Executor's key without asking human twice (ADR-0005, ADR-0006).

**Composite Actions:** `WorkspaceBootstrapAction` orchestrates other Actions through same `LocalExecutor.execute()` path — every sub-step independently validated, permission-gated, logged. No rollback on partial failure (deliberate, ADR-0006).

### 5.2 Filesystem Plugin (`plugins/filesystem_plugin.py`) — Mission Briefs 001, 002, 003, 005
14 capabilities registered declaratively from tuple of Action classes:
- **Read** (`READ_ONLY`): `read_file`, `list_directory`, `search_files`, `file_exists`, `directory_exists`
- **Write** (`REVERSIBLE_WRITE`): `write_file`, `append_file`
- **Modify** (`REVERSIBLE_WRITE`): `rename_file`, `copy_file`, `move_file`
- **Delete** (`IRREVERSIBLE`): `delete_file`, `delete_folder`
- **Composite**: `create_folder` (pre-existing), `workspace_bootstrap`

Registration: loop over declared Action classes, `invoke()` resolves registered capability — adding capability #N = one new class in tuple, never edit to `FilesystemPlugin`.

Security: path traversal check via `is_unsafe_relative_path()`, invalid path rejection in `validate()`, overwrite protection (refuse to clobber unless `overwrite: true`), sandboxed to configured location roots.

### 5.3 Browser Worker — Mission Brief 022 (`BROWSER_WORKER_ARCHITECTURE.md`)
**First Worker against frozen Constitution.** 9 atomic Actions:
| Action | Capability | Risk Tier | Category | Wraps |
|--------|------------|-----------|----------|-------|
| `OpenBrowserSessionAction` | `open_browser_session` | `REVERSIBLE_WRITE` | `SYSTEM` | Playwright launch + context + page |
| `CloseBrowserSessionAction` | `close_browser_session` | `REVERSIBLE_WRITE` | `SYSTEM` | Playwright teardown |
| `NavigateAction` | `navigate` | `REVERSIBLE_WRITE` | `MODIFY` | `page.goto()` |
| `ClickAction` | `click` | `REVERSIBLE_WRITE` | `MODIFY` | `page.locator(selector).click()` |
| `TypeTextAction` | `type_text` | `REVERSIBLE_WRITE` | `WRITE` | `page.locator(selector).fill()` |
| `PressKeyAction` | `press_key` | `REVERSIBLE_WRITE` | `MODIFY` | `page.keyboard.press()` |
| `ScrollAction` | `scroll` | `REVERSIBLE_WRITE` | `MODIFY` | `page.mouse.wheel()` / `scroll_into_view_if_needed()` |
| `WaitForSelectorAction` | `wait_for_selector` | `READ_ONLY` | `READ` | `page.locator(selector).wait_for()` |
| `ObserveBrowserAction` | `observe_browser` | `READ_ONLY` | `READ` | `normalize_observation()` |

**Environment Session Manager:** `BrowserSessionManager` (one per Operator Instance) owns `BrowserSession` (Playwright instance, Browser, BrowserContext, Page). `open_session/get/close_session/list_sessions`. Deliberately NOT Shared Infrastructure (Constitution §5.8).

**Generic Verification Package** (`verification/`): `Verifier` ABC, `Evidence`, `ExpectedOutcome`, `ObservationCheck`, `Verdict`, `AuditRecord`, `AuditLog` — zero Playwright imports, reusable by Desktop/Terminal/REST Workers.

**Observation:** `normalize_observation(page, selectors, include_accessibility_tree, include_available_actions) -> BrowserObservation`. Five facets: current page, viewport, DOM state/visible elements, accessibility tree (opt-in), available actions (opt-in). All degrade honestly (yield "absent" not raise). Caps with explicit `*_truncated` flags.

### 5.4 Mission Control — Mission Brief 023 (`MISSION_CONTROL_ARCHITECTURE.md`)
**Runtime coordination layer — performs no work.** No Environment access, no model calls, no live plugin references.

**Components:**
- Universal Event Bus: single `Event` schema (`event_id, event_type, occurred_at, source, objective_id, task_id, capability, payload, error`). Synchronous, in-process delivery.
- Executive Registry: tracks live Executives (capabilities, health, current task). Distinct from Shared Infrastructure's Capability Registry (coordination catalogue vs execution lookup).
- Capability Registry: descriptors (names, versions, owners, health, dependencies) — populated by adapter reading Plugin manifests.
- Task Dispatcher: `Objective` → `Task`s (qualified capability + optional `depends_on`). Computes ready tasks, resolves to healthy Executive, marks `DISPATCHED`, emits `TASK_DISPATCHED`. Failed dependency → `BLOCKED` (never silently skipped, never auto-retried).
- Worker Lifecycle: 9 states (`CREATED → INITIALIZED → READY → RUNNING → {WAITING, COMPLETED, FAILED} → ... → STOPPED`).
- Self-Development Queue: 5 categories, state machine `PROPOSED → ACCEPTED → IN_PROGRESS → DONE | REJECTED`.
- Knowledge Acquisition Queue: 7-stage pipeline `NEED → RESEARCH → SOURCE_COLLECTION → COMPARISON → VERIFICATION → KNOWLEDGE_STORAGE → CAPABILITY_CREATION`. Promotion gate (`VERIFICATION → KNOWLEDGE_STORAGE`) requires explicit `human_approved=True` (Constitution ADR-0012).
- Founder State: `MissionControl.founder_state()` → snapshot (current objective, mission, executive, capability, progress, evidence, errors, ETA, waiting approval, learning progress). ETA honest or absent.
- Audit Stream: subscribes to Event Bus, records every event as immutable `AuditEntry`. Append-only. Distinct from per-Worker `verification/audit.py`.

**Registration adapter:** `register_plugin_as_executive()` reads Plugin manifest — `BrowserPlugin` and `FilesystemPlugin` register unchanged.

### 5.5 Runtime Engine — Mission Brief 024 (`RUNTIME_ENGINE_ARCHITECTURE.md`)
**The heartbeat.** Replaces human in the cycle: observe → dispatch → execute → verify → report → idle → repeat.

**ExecutiveGateway protocol:** `invoke(capability, payload)`, `verify(...)`. Runtime holds gateways keyed by Executive ID, resolves from Mission Control assignment. Zero Executive knowledge. `tests/test_runtime_architecture.py` parses imports — fails if `runtime/` names any concrete Executive.

**Mechanical retry only** (Constitution §4.1 vs §11): same task, same capability, same payload, bounded attempts, fixed delay. Never alters payload, substitutes capability, re-plans, reorders. Exhausted → escalate (`TASK_ESCALATED`) to Mission Control. Mission Control never sees retry (told `task_failed` once after final attempt).

**ApprovalGate (MB028.0, ADR-0019):** `RuntimeEngine._handle_task()` consults `ApprovalGate` before touching any gateway. **Fail closed:** no gate ⇒ nothing runs (not even `READ_ONLY`). Three outcomes: `Authorised` → execute; `ApprovalPending` → hold task, re-offer next cycle; `ApprovalDenied` → fail, never retry. Evidence outlives process; authority does not (restart re-asks).

**8-state machine:** `INITIALIZING → IDLE | STOPPING | STOPPED`, `IDLE → DISPATCHING | STOPPING`, `DISPATCHING → WAITING | VERIFYING | IDLE | RECOVERING | STOPPING`, `WAITING → VERIFYING | RECOVERING | IDLE | STOPPING`, `VERIFYING → IDLE | RECOVERING | STOPPING`, `RECOVERING → DISPATCHING | IDLE | STOPPING`, `STOPPING → STOPPED`, `STOPPED` (terminal).

**Concurrency:** `max_concurrent_tasks` (default 1) caps work-in-flight. Within cycle: sequential execution (honest, not oversight). Environment Sessions are thread-affine (Playwright sync API binds to per-thread event loop) — every interaction must happen inside a task on Runtime's thread.

### 5.6 Persistence — Mission Brief 025 (`PERSISTENCE_ARCHITECTURE.md`)
**Operational memory.** Mission Control and Runtime state survives process exit, resumes where stopped.

Two mechanisms:
- **Append-only event log** (`events.jsonl`) — written as events happen, audit history and replay
- **Versioned, checksummed snapshot** (`snapshot.json`) — written on checkpoint, fast restart O(live state) not O(history)

`recovery.recover()` — single call launcher makes.

**Four boundaries (enforced by `tests/test_persistence_architecture.py`):**
1. Persistence never executes (no gateway, no Executive, no dispatch surface)
2. Mission Control never writes files (no filesystem import; forbidden-import test)
3. Runtime never performs storage (calls `CheckpointSink` protocol defined inside `runtime/checkpoint.py`)
4. Contracts only (AST-walking test rejects private-attribute access on non-`self`)

**Interrupted tasks quarantined, never re-run** — unknown side effects → return as `FAILED`, dependents `BLOCKED`, visible in Founder State. Re-running = strategic judgement for Brain (Constitution §11).

⚠️ Three additive changes to frozen components recorded in ADR-0015 as **Proposed**, awaiting ratification.

---

## 6. AI Capability Broker (Architecture-only, Mission Brief 027, Amendment 2)

**Provider Registry:** `ProviderDescriptor(provider_id, display_name, provider_class[open vocabulary], offers[CapabilityOffer], execution_binding[PascalCase.PascalCase Capability + fixed params], cost_profile, licensing, rate_limits, requirements, availability, version, provenance[declared|discovered|self_registered], registered_at, verified_at, health)`. Descriptors only, never live objects. No provider known to Broker's code. Registration idempotent by `provider_id`.

**Provider Classes (illustrative, non-binding):** `local_runtime` (Ollama, LM Studio), `desktop_application` (Claude Desktop, ChatGPT Desktop), `cloud_api` (Anthropic, OpenAI), `cloud_aggregator` (OpenRouter), `remote_self_hosted`, `embedded`.

**Licensing:** `LicenceTerms` — first-class filter in Phase 1 (providers not permitting request's `licensing_use` filtered out, not warned).

**Availability:** Per-class determination (local_runtime: endpoint responds + model present; desktop_application: installed at known path; cloud_api: credential + connectivity + rate-limit headroom). Never assumed from descriptor existing.

**Decision Engine (§6):**
- Phase 1 (Filter): hard constraints (privacy, connectivity, latency, quality floor, licensing, exclude_providers, max_cost)
- Phase 2 (Rank): cheapest tier clearing quality floor; preferences (hints) influence ranking, never filter
- Refusal over silent fallback: `NO_CAPABLE_PROVIDER` with full `rejected` list

**Cost Model:** `CostProfile(tier[free|freemium|paid_per_request|paid_subscription], per_request_usd, monthly_cap_usd, currency)`. Cost Model tracks spend, enforces budget caps (paid tiers filtered out entirely when exhausted).

**Benchmark Store:** aggregates `BenchmarkSample(provider_id, ai_capability, task_class, success_count, total_count, latency_ms_p50/p95, tokens_per_second, last_updated)` by (provider, ai_capability, task_class). **Observed beats declared** — Verification Verdict determines success, not provider HTTP status.

**Approval Policy:** 8 founder policies (e.g., `always_ask`, `auto_approve_free`, `require_approval_above_cost`). Broker *requires* permission through §5.2, implements no parallel mechanism.

**AI Infrastructure Executive (Worker, §11):** Machine-touching counterpart — discovers, probes, benchmarks, inventories, installs (with explicit Founder approval). Produces inputs Broker decides on; never decides itself.

---

## 7. Terminology Freeze (Constitution §17)

| Term | Definition |
|------|------------|
| **Brain** | Cognitive layer: Intent Layer, Planner, Model Router, Reporter (§3). Decides; never executes. |
| **Operator** | Execution layer: Orchestrator, Verification Subsystem, Worker/Plugin Runtime, Environment Session Management (§4). Executes; never decides. |
| **Worker** | Single registered unit of execution capability inside Operator's Worker Runtime. Not a layer. |
| **Executive** | Synonym for **Worker** (MB023 term for Mission Control registration API). `Worker` stays canonical. |
| **AI Capability** | Kind of intelligence a Provider can supply (`reasoning`, `vision.ocr`, `speech.transcribe`). `lowercase.dotted`. Distinct from Capability. Never dispatchable. |
| **Provider** | Any registered source of AI capability. Generalizes, does not replace, Reasoning Provider. |
| **Environment** | Abstract category (Desktop, Browser, Terminal, VPS, Robotics/IoT). Never a specific product. |
| **Environment Instance** | One concrete, addressable, live target within an Environment category. |
| **Environment Session** | Live handle an Operator Instance holds to one Environment Instance. Owned by exactly one Operator Instance; never Shared Infrastructure. |
| **Capability** | Named unit of "what can be done" a `Step` references; resolved to Worker/Operator Instance at execution time via Capability Registry. |
| **Action** | Concrete, atomic implementation of one Capability inside a Worker: validates, runs, produces Execution Result. |
| **Observation** | Freshly captured fact about real-world state, gathered by Verification Subsystem re-checking an Environment Instance. |
| **Evidence** | Observation + Expected Outcome + Verdict, packaged as durable record. |
| **Verification** | Act of comparing Observation against Expected Outcome to produce Verdict. Reserved exclusively for Mission-level meaning. |
| **Knowledge** | Durable, promoted understanding the Brain actively consults during planning. Distinct from raw Mission Record. |
| **Mission** | One complete Intent-to-Outcome unit of work; owns single Mission State instance; may span multiple Steps, Capabilities, Operator Instances. |
| **Session** | Reserved for **Mission Session** — Brain-side conversational context. Never used for Environment-level connection. |
| **Step** | One DAG node of a `MissionPlan`, naming a Capability and an Expected Outcome. |
| **Worker Instance** | One live, invocable registration of a Worker inside a specific Operator Instance. |
| **Operator Instance** | One running instance of the Operator, bound to one (or small tightly-coupled set of) Environment Instance(s), tracked by Operator Registry. |

---

## 8. Section Status Summary (Constitution §18, `FOUNDER_CONSTITUTION_FREEZE.md` §4)

| Status | Meaning | Sections |
|--------|---------|----------|
| **FROZEN** | Will not change without new Constitution revision. Implementation may rely on this shape indefinitely. | 1, 2, 3, 4, 5 (except §5.7), 6, 9.1–9.2, 13, 14, 15, 16, 17, 18, 20 |
| **RESEARCH-BACKED** | Reasoned through carefully, not yet implemented/proven at real scale. Expect refinement once real usage exists. | 5.7 (AI Capability Broker), 8, 9.3–9.5, 10 |
| **EVOLVABLE** | Stable philosophy, deliberately open roster/mechanism. Expected to grow without Constitution revision. | 7, 11, 19 |
| **IMPLEMENTATION DETAIL** | Real and correct, not architecture-constitution material. | 12, 21 |

---

## 9. Unresolved Questions / Named Gaps (from Constitution §3, §11.4, `FOUNDER_CONSTITUTION_FREEZE.md` §3)

1. **In-mission recovery decision procedure** (§11.4): Exact rule for when Orchestrator's retry absorbs failure vs escalates to re-plan vs surfaces to human. Not a blocker — nothing on `ROADMAP.md` depends on it.

2. **Stateful Environment Sessions inside Worker/Action contract** (§8.3, §12): Today's Action contract is one-shot; Browser/Terminal/Robotics need live handle across multiple Steps. Not a blocker — no current Worker needs this.

3. **Concurrent dispatch across Operator Instances** (§8.5): Deliberately left EVOLVABLE per instruction not to design distributed system. Not a blocker.

4. **MB006–MB020 remain absent** from repository and all known backups. Constitution does not depend on their content.

5. **Planner not yet implemented** (`ROADMAP.md` item 1) — `cli.py`'s regex stand-in plays its role. Real Planner will replace stand-in, wire to Model Router, consume Memory context.

6. **Reporter not yet built** — `cli.py` completion messages play this role.

7. **MissionManager not wired into live path** — `MEMORY_ARCHITECTURE.md` §11: `MissionManager` imports `MemoryStore` but `cli.py`'s `MasterAgentSession` is the only working conversational path.

8. **ADR-0015 (Persistence Strategy) Proposed** — three additive changes to frozen components awaiting ratification.

9. **ADR-0020 (Founder Approval Workflow) Proposed** — ships frozen-component changes.

10. **LocalExecutor._log** unbounded in-memory list, not part of Memory — would leak in long-running daemon (`MEMORY_ARCHITECTURE.md` §11).

11. **UTC-relative timestamps, not local-time-relative** — known simplification (`MEMORY_ARCHITECTURE.md` §11).

12. **No transactional guarantees beyond SQLite's own** — crash between filesystem effects and `save_mission()` leaves filesystem change real but unrecorded.

13. **Cross-platform path safety** (`MB023.1` completed): `is_unsafe_relative_path()` hardened for Windows/POSIX differences.

---

## 10. Scalability Commitments (Constitution Rule 1, applied across all documents)

- Adding Executive/Worker #N: one registration/file, no edits to dispatcher, registries, Orchestrator, Permission System.
- Capability resolution: dict lookup by qualified name, not scan.
- Event Bus: new event type = one enum member; unknown types ignored by old subscribers.
- Broker: adding provider #N = one registration call, zero edits; no provider-specific branches in code.
- Runtime: adding Executive #N = one gateway registration; no per-Executive branching.
- Persistence: event log append-only, snapshot O(live state); recovery single call.
- Where revisiting needed (named honestly): Event Bus synchronous/in-process; Audit Stream unbounded in-memory; Dispatcher readiness O(tasks) not incremental; Runtime single-threaded sequential; fixed poll interval not event-driven; fixed retry delay no jitter.

---

*Document populated from verified sources only. Terminology preserved exactly as used in source documents. Uncertainty marked explicitly.*