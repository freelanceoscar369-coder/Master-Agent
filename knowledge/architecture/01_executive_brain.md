# Executive Brain

## Purpose
Documents the cognitive layer: Intent Layer, Planner, Model Router, Reporter — per `KALPAVRIKSHA_VISION_V2.md` §3 (FROZEN).

## Scope
Covers all Brain responsibilities per Constitution §3. Implementation status drawn from Mission Briefs 036 (Planner), 037 (Planner Integration), and source code in `src/master_agent/planner/`, `src/master_agent/plugins/model_router.py`.

## Dependencies
- `KALPAVRIKSHA_VISION_V2.md` §3 (FROZEN)
- `docs/MISSION_BRIEF_036.md` (Planner implementation)
- `docs/MISSION_BRIEF_037.md` (Planner Integration)
- `src/master_agent/planner/` (7 modules: plan.py, catalogue.py, outcomes.py, prompting.py, parsing.py, planner.py, __init__.py)
- `src/master_agent/plugins/model_router.py` (Model Router, MB032-wired)

## Last Updated
2026-08-02

## References
- `KALPAVRIKSHA_VISION_V2.md` §3 (FROZEN) — constitutional authority
- `MISSION_BRIEF_036.md` — Planner implementation, decisions, findings
- `MISSION_BRIEF_037.md` — Planner Integration, wiring, live findings
- `src/master_agent/planner/plan.py` — vocabulary: Intent, Step, MissionPlan, PlanRefusal, PlanOutcome
- `src/master_agent/planner/catalogue.py` — CapabilityOption, catalogue_from, render
- `src/master_agent/planner/outcomes.py` — SuccessSpec, SUCCESS_KEYS, from_document
- `src/master_agent/planner/prompting.py` — build_prompt, plan_expectation, PLAN_SHAPE
- `src/master_agent/planner/parsing.py` — validate, Kahn's algorithm, payload validation
- `src/master_agent/planner/planner.py` — Planner class, five refusal paths
- `src/master_agent/plugins/model_router.py` — ModelRouter, RoutingContext, SelectionRequest, ProviderSelector protocol

## Status
**POPULATED FROM VERIFIED SOURCES** — not a template.

---

## 1. Constitutional Mandate (KALPAVRIKSHA_VISION_V2.md §3, FROZEN)

### 1.1 Role
The **Executive Brain** is the cognitive layer. It decides *what* to do, *how* to structure it, and *how to explain it back*. It owns Intent, Planning, Reasoning-Provider selection, and Reporting. It **never executes, never touches an Environment, and never holds a Permission grant.**

### 1.2 Components
| Component | Status | Notes |
|-----------|--------|-------|
| **Intent Layer** | Stub / stand-in | `cli.py`'s regex `parse_intent()` plays this role (MB001, 003.1, 005). Real Intent Layer pending real Planner (`ROADMAP.md` item 1). |
| **Planner** | **Implemented** (MB036) | 7 modules in `src/master_agent/planner/`. Produces `MissionPlan` with `ExpectedOutcome` per Step. Not yet wired to `cli.py` (wiring = MB037). |
| **Model Router** | **Implemented** (MB032-wired) | `src/master_agent/plugins/model_router.py`. Asks AI Capability Broker (§5.7) which Provider serves a request. Four hardcoded branches removed. Fail-closed if no Broker wired. |
| **Reporter** | Not built | `cli.py`'s completion messages play this role. Named explicitly in Constitution §3.4 because missing from prior revision. |

### 1.3 What the Brain Does NOT Do (Constitution §3.5)
- Does not execute capabilities
- Does not hold or check Permission grants
- Does not own Mission State (Shared Infrastructure §5.3 does)
- Does not persist Memory itself (Shared Infrastructure does; Brain reads it and nominates Knowledge Candidates §9)
- Does not verify outcomes (consumes Evidence; does not produce it §10)
- Does not know what an Environment Instance is — only that a Step requires a Capability

---

## 2. Planner (Mission Brief 036, 037)

### 2.1 Architecture (MB036 §2)
```
Intent ─> catalogue ─> prompt ─┐
                                v
             ExpectedOutcome ─> PromptExecutor ─> Broker ─> provider
                                │
                         Evidence ──┴── observation["json"]
                                │
                           validate() ─> MissionPlan
```

### 2.2 Modules (`src/master_agent/planner/`)

| Module | Purpose |
|--------|---------|
| `plan.py` | Vocabulary: `Intent`, `Step`, `MissionPlan`, `PlanRefusal`/`PlanOutcome` (11 refusal codes). `Step.expected_outcome` added. Re-exports for backward compatibility. |
| `catalogue.py` | Port: `catalogue_from(registry)` needs `.all()`. `CapabilityOption(name, description, risk_tier, required_args, args_complete)`. `render()` → prompt lines. Deterministic sort by name. |
| `outcomes.py` | `SuccessSpec` → `ExpectedOutcome` via MB035's `expect()`. Closed `SUCCESS_KEYS`: `description`, `must_contain`, `must_exclude`, `must_be_json`, `must_have_fields`, `min_words`. `require_non_empty=True` always. `MalformedSuccess` raised for unsupported keys. |
| `prompting.py` | `build_prompt(Intent, options) -> str`. `PLAN_SHAPE` example. Rules 1–6 (Rule 6: `{"steps": []}` for impossible objectives). `plan_expectation()` → `ExpectedOutcome` for plan document itself. |
| `parsing.py` | `validate(document, options, objective) -> (MissionPlan, PlanRefusal)`. **No parser** — reads `Evidence.observation["json"]` (MB035's `observe()` output). Kahn's algorithm for dependency ordering (ties = declaration order). MB039: payload checked against `CapabilityOption.required_args` *before* submission. |
| `planner.py` | `Planner(runner, catalogue, requires_strong_reasoning=False, offline=False)`. `options()` reads catalogue fresh each call. `plan(Intent) -> PlanOutcome`. Five refusal paths (none invents a plan). Quality floor = knob (constructor arg), not hardcoded. |
| `__init__.py` | Re-exports `Intent`, `MissionPlan`, `Planner`, `Step`. |

### 2.3 Key Data Structures

**`Intent`** (`plan.py:61`):
```python
goal: str
constraints: list[str]
context: dict[str, Any]
success_criteria: list[str]
is_sensitive: bool
```

**`Step`** (`plan.py:84`):
```python
step_id: str
capability: str          # exact name from catalogue
payload: dict[str, Any]
depends_on: list[str]
expected_outcome: ExpectedOutcome | None  # mandatory in Planner, optional on dataclass
priority: str            # low|normal|high|critical (descriptive, never directive)
estimated_complexity: str  # trivial|small|moderate|large (descriptive, never directive)
```

**`MissionPlan`** (`plan.py:105`):
```python
steps: list[Step]
objective: str
```

**`PlanRefusal`** (`plan.py:112`): 11 codes
- `NO_CAPABILITIES` — empty catalogue
- `BROKER_REFUSED` — Broker declined
- `PROVIDER_FAILED` — provider error (timeout, etc.)
- `UNVERIFIED` — no Evidence record
- `NOT_JSON` — reply not a plan document
- `MALFORMED` — structural failure
- `NO_STEPS` — `{"steps": []}` (Rule 6)
- `UNKNOWN_CAPABILITY` — names unregistered capability
- `MISSING_EXPECTATION` — step lacks `success` object
- `BAD_DEPENDENCY` — self-dep / missing dep / cycle
- `BAD_PAYLOAD` (MB039) — missing required args per `CapabilityOption.required_args`
- `CYCLIC` — dependency cycle

### 2.4 Decisions (MB036 §4)

1. **§3.2 enforced at planning door, not in type** — `Step.expected_outcome` optional on dataclass, mandatory in Planner via `parsing.validate()`. Avoids rewriting MB022 browser tests and `cli.py` stand-in.

2. **No second parser** — `validate()` reads `Evidence.observation["json"]` (MB035's `observe()` output). Verified artefact = executed artefact.

3. **Six `SUCCESS_KEYS`, not raw `ObservationCheck`** — prevents provider inventing uncheckable fields (e.g., `folder.exists_after`). Unsupported key = refusal, never silently dropped.

4. **Five ways to stop, no fallback plan** — MB032 refused fallback provider; fallback plan is worse (unverified, produced at moment of demonstrated planning failure).

5. **Quality floor = knob** — `requires_strong_reasoning` constructor arg, defaults `False`. ADR-0017 gives floors to founder's policy, not component.

6. **Empty step list = refusal** (`NO_STEPS`) — empty plan would complete instantly and report success.

7. **Declared dependencies → list order** — Kahn's algorithm, ties by declaration order. Orchestrator walks `plan.steps` in list order.

### 2.5 Architecture Tests (`tests/test_planner_architecture.py`)
1. No product names (14 vendors checked against stripped source)
2. No ranking, no fallback, no `score` (ADR-0018)
3. No `socket`/`urllib`/`httpx`/`subprocess`/`os`/`pathlib`/`open()` (Constitution Rule 4)
4. No frozen imports except `plugins/model_router` (request vocab) and `verification.evidence` (contract)
5. `RATIFIED_EXCEPTIONS` gained no row

### 2.6 Live Findings (MB036 §6)

| Finding | Description |
|---------|-------------|
| **F1** | Unscanned machine → `broker_refused: 5 providers considered, none eligible: not available`. Correct — absence not assumed. |
| **F2** | `OllamaConfig.model` defaults to `hermes3`; founder has `gemma4:latest`. `HTTP 404`. Backlog item. |
| **F3** | Planning prompt = entire capability catalogue (26 caps) + structured JSON → exceeds 120s default timeout. **One global timeout does not fit two shapes of work.** Highest priority after input-schema gap. |
| **F4** | **Payloads wrong, nothing could catch it.** `CreateFolder` requires `name`; plan sent `path`. `WriteFile` requires `path`; plan sent `file_path`. `CapabilityManifest.input_schema` declared in frozen `plugins/base.py`, populated by **nothing**. Top backlog item. |
| **F5** | Expectation can be falsifiable but still a guess — `must_contain: "Folder 'X' created."` is model's guess at unseen result string. Publishing result shapes alongside input schemas = same fix as F4. |

### 2.7 Planner Integration (MB037)

**Pipeline wired:**
```
Founder -> Planner -> MissionPlan -> Mission Control -> Executives -> Broker -> Providers -> Verifier -> Evidence -> Memory
```

**New modules (`missions/`):**
| Module | Purpose |
|--------|---------|
| `missions/translation.py` | `MissionPlan` → `Objective`. 1:1, lossless. Gate rejects incomplete plan **before `Objective` exists**. |
| `missions/service.py` | `MissionService.start()` — single path from founder objective to submitted work. |
| `missions/history.py` | Durable record: planned, happened, replay. **Observes only** — imports nothing from `providers/`, `ai_infrastructure/`, `plugins/`, `broker/`, `httpx`, `urllib`, `socket`, `subprocess`. |

**Key decisions (MB037 §4):**
- Translation, not second work vocabulary — `Task` already has `capability`, `payload`, `depends_on`, `expected_outcome`.
- Gate judges fields, not producers — `incomplete_steps()` refuses missing capability/inputs/expected_outcome/dependencies. Hand-built plans held to same rules.
- `priority`/`complexity` descriptive, never directive — closed vocabularies, defaults, **never reach `Task`**. `depends_on` decides order.
- History observes; never drives — subscribers per event type, no dispatch/unlock/order/retry calls.
- Replay re-reads; cannot re-run — import list proves it.
- `cli.py` stopped pretending to plan — one-step `MissionPlan` renamed to `CapabilityCall`. All 66 `test_cli_session.py` assertions pass. AST test: `planner/parsing.py` only module constructing `MissionPlan`/`Step`.

**Live findings (MB037 §6):**
- **F1**: Refusal reason didn't reach founder — `detail` field not rendered. Fixed: sentence now carries cause (`no plan: the provider could not answer (no answer within 540s)`).
- **F2**: 540s timeout still insufficient for 26-capability catalogue on CPU. Highest priority after input-schema gap.
- **F3**: **MB036 Finding 4 in production** — `missing required parameter: name`. Planner wrote `{"path": "X"}`; `CreateFolder` requires `name`. All layers correct; mission failed on unpublished fact.
- **F4**: "waiting on step_1" lied after step_1 failed. Fixed: `will not run - make_folder failed` distinct from `waiting on`.
- **Defect 6**: `_current_objective_id` never advances past first objective (frozen `mission_control/` — backlog, same posture as MB026).

---

## 3. Model Router (Mission Brief 032, `src/master_agent/plugins/model_router.py`)

### 3.1 Before MB032 (Docstring)
Four hardcoded branches, two product names, unauditable ladder:
```python
if not ctx.is_online:            return self._provider("hermes")
if ctx.is_sensitive:             return self._provider("hermes")
if ctx.requires_strong_reasoning: return self._provider("chatgpt")
return self._provider(self._default_provider)  # "hermes"
```
ADR-0017: "documented contradiction" — Constitution §14/§21 forbid product names in Brain logic.

### 3.2 After MB032 (Amendment 2 §3.3)
Model Router **keeps interface and role**, **asks AI Capability Broker** which Provider. Four branches become **four facts about the request** forwarded to Broker.

### 3.3 Core Types

**`RoutingContext`** (facts about the work, never provider preference):
```python
is_online: bool = True
is_sensitive: bool = False
requires_strong_reasoning: bool = False
preferred_provider: str | None = None  # explicit founder override → Broker constraint
capability: str = REASONING  # "reasoning" (lowercase.dotted = AI Capability)
max_cost: float | None = None
max_latency_ms: float | None = None
required_context_tokens: int | None = None
task_id: str = ""
objective_id: str | None = None
requester: str = "model_router"
```

**`SelectionRequest`** (frozen — Broker must not edit question):
```python
capability: str = REASONING
offline: bool = False          # is_online inverted: constraint not happy path
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

**`ProviderSelector` Protocol** (outbound port — Brain declares what it needs):
```python
def select(request: SelectionRequest) -> Any: ...  # returns decision with provider_id
```

### 3.4 `ModelRouter` Class

```python
def __init__(self, registry: PluginRegistry, selector: Any = None)
    # selector optional in signature, mandatory in effect

def select(ctx: RoutingContext) -> Any
    # Broker's answer before plugin resolution
    # raises BrokerUnavailable if no selector wired

def select_provider(ctx: RoutingContext) -> ModelProvider
    # Broker's answer resolved to runnable plugin
    # Broker refusals propagate untouched

def generate(prompt: str, ctx: RoutingContext, context: dict | None) -> str
    provider = self.select_provider(ctx)
    return provider.generate(prompt, context)
```

### 3.5 Fail-Closed Guarantees
- **No selector wired** → `BrokerUnavailable` ("refusing rather than guessing")
- **Broker chose unregistered provider** → `ProviderNotWired` (wiring gap, decision was sound)
- **No fallback to local** — a fallback is a provider decision; component making one when decision-maker missing = hardcoding MB032 deleted

### 3.6 Architecture Tests (`tests/test_broker_integration.py`)
- Greps for 7 vendor names to ensure none in `model_router.py`
- Asserts `RATIFIED_EXCEPTIONS` unchanged

---

## 4. Intent Layer (Constitution §3.1)

### 4.1 Constitutional Role
Turns raw input into structured `Intent` (goal, constraints, context, success criteria). Owns follow-up clarification when ambiguous. **Deliberately not** "send raw string to a model" — real parsing/clarification step.

### 4.2 Current Stand-in
`cli.py`'s regex-based `parse_intent()` (Mission Briefs 001, 003.1, 005):
- Recognizes: "create a folder called X [on Y]" → `ParsedIntent`
- "create [a/an/a new] [<type>] project/application called/named X" → `ParsedProjectIntent`
- 9 filesystem shapes (MB005): "Read X", "Rename X to Y", "Copy/Move X to Y", "Delete X [folder]", "List files inside X", "Search for X" → single generic `ParsedActionIntent`
- Table-driven `_INTENT_PATTERNS` (regex, builder) pairs tried in order

### 4.3 Real Intent Layer
Stub pending real Planner (`ROADMAP.md` item 1). Will replace regex stand-in.

---

## 5. Reporter (Constitution §3.4)

### 5.1 Constitutional Role
Takes Mission outcome + Evidence once Verification produces Verdict, composes human-facing report (text today; voice later). Decides *how to explain* — Brain-shaped judgment. Never touches Environment; only reads Evidence and Mission state through Shared Infrastructure.

### 5.2 Current Status
**Not yet built as distinct module** — `cli.py`'s completion messages play this role. Named explicitly in Constitution because missing from prior revision's model entirely (`FOUNDER_CONSTITUTION_FREEZE.md` §"Ownership gaps closed").

---

## 6. Open Questions / Unresolved Items

| Item | Source | Status |
|------|--------|--------|
| **Planner not wired to `cli.py`** | MB036 §3, MB037 | Wiring = MB037 (done for MissionService path; `cli.py` conversational path still uses regex stand-in) |
| **Input schemas unpublished** | MB036 Finding 4, MB037 Finding 3 | `CapabilityManifest.input_schema` declared in frozen `plugins/base.py`, populated by nothing. Top backlog item. |
| **Result shapes unpublished** | MB036 Finding 5 | Same fix as input schemas — `output_schema` also empty. |
| **Timeout for planning** | MB036 Finding 3, MB037 Finding 2 | 540s insufficient for 26-capability catalogue on CPU. Belongs in `providers/`, not Planner. |
| **`OllamaConfig.model` default wrong** | MB036 Finding 2 | Defaults to `hermes3`; founder has `gemma4:latest`. Backlog. |
| **`_current_objective_id` never advances** | MB037 Defect 6 | Frozen `mission_control/` — backlog, same posture as MB026. |
| **Pause/resume/cancel** | MB037 §5 | Needs ratified ADR. `test_missions_lifecycle.py::test_pause_resume_and_cancel_do_not_exist_anywhere` fails if added. |
| **Adaptive re-planning** | MB037 §8 | Deliberately not built — Constitution §11 reserves strategic recovery for Brain. Separate brief with safety argument needed. |
| **Semantic correctness** | MB036 §3 | Unchanged honest limit — expectations are structural over text, cannot catch "reports success but did wrong thing". |

---

## 7. Files Referenced

| File | Role |
|------|------|
| `KALPAVRIKSHA_VISION_V2.md` §3 | Constitutional authority (FROZEN) |
| `FOUNDER_CONSTITUTION_FREEZE.md` | Freeze record, amendments |
| `MISSION_BRIEF_036.md` | Planner implementation, decisions, live findings |
| `MISSION_BRIEF_037.md` | Planner Integration, wiring, live findings |
| `src/master_agent/planner/plan.py` | Vocabulary: Intent, Step, MissionPlan, PlanRefusal, PlanOutcome |
| `src/master_agent/planner/catalogue.py` | CapabilityOption, catalogue_from, render |
| `src/master_agent/planner/outcomes.py` | SuccessSpec, SUCCESS_KEYS, from_document |
| `src/master_agent/planner/prompting.py` | build_prompt, plan_expectation, PLAN_SHAPE |
| `src/master_agent/planner/parsing.py` | validate, Kahn's algorithm, payload validation |
| `src/master_agent/planner/planner.py` | Planner class, five refusal paths |
| `src/master_agent/plugins/model_router.py` | ModelRouter, RoutingContext, SelectionRequest, ProviderSelector |
| `tests/test_planner_architecture.py` | Architecture guards |
| `tests/test_broker_integration.py` | Broker wiring guards |

---

## 8. Wiki Links Added
- `[[KALPAVRIKSHA_VISION_V2.md#3-executive-brain-responsibilities]]`
- `[[MISSION_BRIEF_036.md]]`
- `[[MISSION_BRIEF_037.md]]`
- `[[ARCHITECTURE.md#42-planner]]`
- `[[ARCHITECTURE.md#5-the-model-router]]`
- `[[ADR-0017-ai-capability-broker.md]]`
- `[[ADR-0018]]`

---

## 9. Future Extraction Needs
- `docs/MISSION_BRIEF_038.md` (timeout architecture) when available
- `docs/MISSION_BRIEF_039.md` (capability index / input schemas) when available
- Real Intent Layer implementation (replacing `cli.py` regex stand-in)
- Reporter module implementation
- `src/master_agent/missions/` package (translation, service, history) — not yet read