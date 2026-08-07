# Planner Wiring Audit

## Source
- Architecture: `KALPAVRIKSHA_VISION_V2.md` §3.2, `MISSION_BRIEF_036.md`, `MISSION_BRIEF_037.md`
- Implementation: `src/master_agent/planner/`, `src/master_agent/missions/`, `src/master_agent/cli.py`

## Classification Legend
- **A** = Implementation Bug
- **B** = Missing Implementation Required by Frozen Architecture
- **C** = Founder Edition Limitation
- **D** = Future Evolution / Scalability Item
- **E** = Requires ADR Decision
- **F** = Documentation Gap

---

## 1. Planner Architecture (MB036)

### Architecture (MB036 §2)
```
Intent ─> catalogue ─> prompt ─┐
                                v
             ExpectedOutcome ─> PromptExecutor ─> Broker ─> provider
                                │
                         Evidence ──┴── observation["json"]
                                │
                           validate() ─> MissionPlan
```

### Implemented Components (MB036)

| Module | Purpose | Status |
|--------|---------|--------|
| `plan.py` | Vocabulary: `Intent`, `Step`, `MissionPlan`, `PlanRefusal`/`PlanOutcome` (11 codes) | ✅ |
| `catalogue.py` | Port: `catalogue_from(registry)` needs `.all()`. `CapabilityOption(name, description, risk_tier, required_args, args_complete)` | ✅ |
| `outcomes.py` | `SuccessSpec` → `ExpectedOutcome` via MB035's `expect()`. Closed `SUCCESS_KEYS` | ✅ |
| `prompting.py` | `build_prompt(Intent, options) -> str`. `PLAN_SHAPE` example. Rules 1-6. `plan_expectation()` | ✅ |
| `parsing.py` | `validate(document, options, objective) -> (MissionPlan, PlanRefusal)`. **No parser** — reads `Evidence.observation["json"]`. Kahn's algorithm. MB039: payload checked against `CapabilityOption.required_args` | ✅ |
| `planner.py` | `Planner(runner, catalogue, requires_strong_reasoning=False, offline=False)`. `options()` reads catalogue fresh. `plan(Intent) -> PlanOutcome`. Five refusal paths. Quality floor = knob. | ✅ |

---

## 2. Planner Integration (MB037)

### What MB037 Shipped

**Pipeline Wired:**
```
Founder -> Planner -> MissionPlan -> Mission Control -> Executives
        -> Broker -> Providers -> Verifier -> Evidence -> Memory
```

**New Modules (`missions/`):**

| Module | Purpose | Status |
|--------|---------|--------|
| `missions/translation.py` | `MissionPlan` → `Objective`. 1:1, lossless. Gate rejects incomplete plan **before `Objective` exists**. | ✅ Implemented |
| `missions/service.py` | `MissionService.start()` — single path from founder objective to submitted work. | ✅ Implemented |
| `missions/history.py` | Durable record: planned, happened, replay. **Observes only** — imports nothing from providers/broker/plugins. | ✅ Implemented |

**Key Decisions (MB037 §4):**
- Translation, not second work vocabulary — `Task` already has `capability`, `payload`, `depends_on`, `expected_outcome`
- Gate judges fields, not producers — `incomplete_steps()` refuses missing capability/inputs/expected_outcome/dependencies
- `priority`/`complexity` descriptive, never directive — closed vocabularies, defaults, **never reach `Task`**
- History observes; never drives — subscribers per event type, no dispatch/unlock/order/retry calls
- Replay re-reads; cannot re-run — import list proves it
- `cli.py` stopped pretending to plan — one-step `MissionPlan` renamed to `CapabilityCall`

---

## 3. Wiring Gap: `cli.py` Still Uses Regex Stand-in

### MB037 §3 Explicit Statement
> "It is not wired into `cli.py`. The regex `parse_intent()`/`build_plan()` stand-in still runs the conversational path."

### Evidence in `cli.py` (Lines 775-801)

```python
# Line 775: intent = parse_intent(text)  # REGEX-BASED
# Line 798: call = build_call(intent)    # builds CapabilityCall, NOT MissionPlan
# Line 799: mission.plan = call           # CapabilityCall assigned to mission.plan
```

**What `cli.py` Does NOT Do:**
- Does NOT call `Planner.plan()`
- Does NOT produce `MissionPlan` with `ExpectedOutcome` per step
- Does NOT use `MissionService.start()`
- Does NOT use `missions/translation.py` or `missions/service.py`
- Does NOT produce `ExpectedOutcome` per step

### What `cli.py` DOES Do (Legacy Path)
- Regex `parse_intent()` → `ParsedIntent`/`ParsedProjectIntent`/`ParsedActionIntent`
- `build_call()` → `CapabilityCall` (single capability + payload)
- `Orchestrator.execute_capability()` → direct execution
- Manual mission state transitions
- Manual `_remember()` at terminal states

---

## 3. Wiring Gap Analysis

### Two Distinct Paths Exist

| Path | Trigger | Planner Used? | Verification | ExpectedOutcome |
|------|---------|---------------|--------------|-----------------|
| **Founder Path** (`kalpavriksha` launcher) | `MissionService.start()` | ✅ Planner | Runtime `_verify()` | Per-step from Planner |
| **Demo Path** (`master-agent-demo` / `cli.py`) | `MasterAgentSession.handle()` | ❌ Regex | ❌ None | ❌ None |

### Evidence from `cli.py` (Lines 795-801)

```python
# Line 775: intent = parse_intent(text)  # REGEX
# Line 798: call = build_call(intent)    # CapabilityCall
# Line 799: mission.plan = call           # CapabilityCall assigned to mission.plan
```

**What `cli.py` Does NOT Do:**
- ❌ Does NOT call `Planner.plan()`
- ❌ Does NOT produce `MissionPlan` with `ExpectedOutcome` per step
- ❌ Does NOT use `MissionService.start()`
- ❌ Does NOT use `missions/translation.py` or `missions/service.py`
- ❌ Does NOT produce `ExpectedOutcome` per step
- ❌ Does NOT trigger Verification per step (Runtime does it, but no ExpectedOutcome exists)

---

## 4. Mission Lifecycle in `cli.py` vs Architecture

### Architecture (Constitution §4.1, §10)
```
MissionPlan (Steps + ExpectedOutcomes)
    ↓
Orchestrator/Runtime executes Step
    ↓
Runtime._verify() against Step.expected_outcome
    ↓
Evidence → Mission Control → Brain
```

### `cli.py` Reality
```
CapabilityCall (single capability)
    ↓
Orchestrator.execute_capability() → Plugin.invoke()
    ↓
_step_result_ = StepResult(result, blocked_on_approval)
    ↓
If success: _finish() → _remember() → MissionRecord
    ↓
No Verification step (no ExpectedOutcome exists)
    ↓
No Evidence produced
```

---

## 5. Missing Wiring Components

| Component | Architecture | `cli.py` Status | Classification |
|-----------|--------------|-----------------|----------------|
| `Planner.plan()` | Called for every objective | ❌ Never called | **B** — Missing |
| `MissionService.start()` | Single path objective → work | ❌ Never called | **B** — Missing |
| `missions/translation.py` | `MissionPlan` → `Objective` | ❌ Never called | **B** — Missing |
| `missions/service.py` | Single path to submitted work | ❌ Never called | **B** — Missing |
| `ExpectedOutcome` per step | Required by Constitution §3.2 | ❌ Never created | **B** — Missing |
| Verification per step | Runtime `_verify()` | ⚠️ Runtime does it but no ExpectedOutcome | **A** — Bug (verifies nothing) |
| `MissionManager` wiring | Shared Infra §5.3 | ❌ Unwired | **B** — Missing |

---

## 6. Shortcuts Still Present in `cli.py`

| Shortcut | Description | Architecture Violation |
|----------|-------------|------------------------|
| `parse_intent()` regex | Rule-based, not Intent Layer | §3.1: "Not send raw string to model" |
| `build_call()` → `CapabilityCall` | Not a `MissionPlan` | §3.2: Planner produces `MissionPlan` |
| `mission.plan = call` | `CapabilityCall` assigned to `plan` | Type confusion |
| Manual `_remember()` | Auto-persist at terminal states | ✅ Actually compliant (Rule 7) |
| Manual `_finish()` | Manual mission completion | Should be automatic |
| No `ExpectedOutcome` | Constitution §3.2 requires it | §3.2 violation |
| No Verification per step | Constitution §10 requires it | §10 violation |

---

## 7. Two Paths Divergence

### Path 1: Founder Path (`kalpavriksha` launcher)
```
Objective → MissionService.start()
    → Planner.plan(Intent) → MissionPlan
    → missions/translation.py → Objective
    → MissionControl.submit_objective()
    → RuntimeEngine → execute → verify → report
```

### Path 2: Demo Path (`master-agent-demo` / `cli.py`)
```
User text → parse_intent() regex
    → build_call() → CapabilityCall
    → Orchestrator.execute_capability()
    → Manual _finish() / _remember()
    → No Planner, No Verification, No ExpectedOutcome
```

---

## Summary: Planner Wiring Findings

| Finding | Classification | Details |
|---------|----------------|---------|
| Planner core logic implemented | ✅ Compliant | 7 modules, MB036/037 |
| Planner wired to MissionControl path | ✅ Compliant | MB037 `missions/service.py` |
| Planner wired to `cli.py` demo path | **B** Missing | Regex stand-in still used |
| `ExpectedOutcome` per step in `cli.py` | **B** Missing | Constitution §3.2 violation |
| Verification per step in `cli.py` | **A** Bug | Runtime verifies nothing |
| `MissionManager` unwired | **B** Missing | Shared Infra §5.3 |
| `cli.py` shortcuts documented | ✅ Documented | 7 shortcuts identified |

---

*Generated from verified sources only. No implementation gaps resolved. Classifications based on frozen Constitution only.*