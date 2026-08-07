# Verification System

## Purpose
Documents the structurally independent Verification Subsystem that produces Evidence by re-observing reality and comparing against Expected Outcomes — never by trusting Execution Results.

---

## Frozen Constitution

### Constitution §10 (Verification Philosophy — RESEARCH-BACKED)

**10.1 Problem Resolved:** Prior revision claimed Verification was "distinct step" but only mechanism was Verifier invoked as "final Step in every plan" through same `Plugin.invoke()` path as execution. Made *state* distinct (`verifying` status) but not *mechanism*. This revision fixes the mechanism.

**10.2 Three-Part Boundary:**
1. **Execution produces effects** — Worker's Action runs, does work, returns Execution Result (did it run without error, what it output). Says nothing about real-world outcome.
2. **Verification produces Evidence** — After (or during) execution, Verification Subsystem (distinct component, own contract, not Worker invoked through Capability path) re-observes Environment Instance, compares Observation against Expected Outcome (Planner attached to Step §3.2). Output: Verdict (matched / did not match / partially matched) + Observation + Expected Outcome = **Evidence** (§9.2).
3. **Evidence flows back to Brain** — routed via Shared Infrastructure as input to "is Mission actually complete, or does it need another Step." Closes loop: Brain plans → Operator executes → Verification observes → Evidence reaches Brain → Brain decides `completed` vs re-plan vs escalate (§11).

**10.3 Why Physically Near Operator but Architecturally Separate:**
Only Operator has Environment access (Brain has none §3.5). Verification must run where Environment access exists. But does so through **own contract** — "observe, then compare against Expected Outcome" — never reuses Worker's `validate()`/`run()`, never folds result into plain Execution Result. Same location, different mechanism = "structurally independent."

**10.4 What Is Deliberately Not Designed Here:**
Exact schema of "Expected Outcome"/"Observation", how comparisons computed, what counts as "partial" match — implementation questions, correctly out of scope. Fixed: three-part boundary and Verification never reuses Execution path.

### Constitution §9.2 (Evidence Hierarchy — FROZEN)
**Strongest to Weakest:**
1. **Observed Reality** — what Environment actually shows, what Verification actually measured
2. **Evidence** (§10.3) — structured, timestamped record of Observation compared against Expected Outcome
3. **Mission Record** — persisted record (intent, plan, approval, outcome, artifacts), survives restart
4. **Conversation Transcript** — useful for debugging human intent, not for determining what happened
5. **Reasoning Provider Output** — what model *said* it would do or *said* happened — **never treated as evidence of reality**

> **When documentation and observed reality conflict, observed reality wins** (Rule 8). Extends to Permanent Knowledge (§9.4).

### Constitution §5.6 (Telemetry and Audit — FROZEN)
**Split responsibility, on purpose:**
- Raw log emission happens locally at Operator Instance/Worker Instance
- Shared Infrastructure owns durable, queryable, cross-Operator-Instance aggregation
- "Audit" and "Evidence" are not two separate components — Evidence **is** the audited, verified subset of telemetry that made it into Memory.

### Constitution §15.4 (Transparency Over Trust — FROZEN)
Every execution is logged. Every Mission is recorded. Evidence (§10) is available, not hidden. No Reasoning Provider call happens without a named Capability behind it.

---

## Architecture Design

### 1. Generic Verification Package (`verification/`)
**From `BROWSER_WORKER_ARCHITECTURE.md` §3, §8:**
- **Zero Environment imports** — written to be Desktop/Terminal/REST Worker's verification layer too
- **Factored out** so answer to "can this Worker serve as canonical implementation for every future Worker" is "yes" by construction

**Core Components:**
| File | Purpose |
|------|---------|
| `verifier.py` | `Verifier` ABC with `capture_observation_dict()` (abstract) + `verify(expected)` (concrete) |
| `evidence.py` | `ObservationCheck`, `ExpectedOutcome`, `Verdict`, `Evidence`, `CheckResult` |
| `evaluator.py` | Pure function `evaluate_checks(observation, checks)` → `(Verdict, list[CheckResult])` |
| `audit.py` | `AuditRecord`, `AuditLog` (append-only, in-process) |

### 2. Verifier Contract (`verifier.py`)
```python
class Verifier(ABC):
    worker_name: str
    environment_name: str

    @abstractmethod
    def capture_observation_dict(self) -> dict[str, Any]:
        """Re-observe current real-world state fresh. Must never return cached value from prior Execution."""

    def verify(self, expected: ExpectedOutcome) -> Evidence:
        # 1. Capture fresh observation
        # 2. Evaluate checks via evaluate_checks()
        # 3. Build Evidence record with verdict
```

**Key Principle:** `verify()` **never reads `ExecutionResult`** — always re-observes reality fresh. Execution success ≠ verification success.

### 3. Evidence Model (`evidence.py`)

**`ObservationCheck`** — one declarative assertion:
- `field` — dot-path into observation dict (e.g., `"url"`, `"elements.0.text"`)
- `operator` — `"equals" | "contains" | "not_contains" | "exists" | "matches_regex"`
- `value` — expected value
- `description` — human-readable

**`ExpectedOutcome`** — what Planner attaches to Step:
- `description` — what success looks like
- `checks` — list of `ObservationCheck`

**`Verdict`** (Enum):
- `MATCHED` — all checks passed
- `NOT_MATCHED` — zero checks passed
- `PARTIALLY_MATCHED` — some passed, some failed
- `ERROR` — observation itself could not be captured

**`Evidence`** — durable record routed back to Brain:
- `evidence_id`, `worker`, `environment`, `captured_at`
- `expected` (`ExpectedOutcome`)
- `observation` (plain JSON-shaped dict — never live object)
- `verdict` (`Verdict`)
- `check_results` (list of `CheckResult`)
- `errors` (list of strings)

### 4. Evaluation Logic (`evaluator.py`)
- **Dot-path lookup** (`get_field()`) into nested dict/list — missing path = normal outcome, not error
- **5 operators:** `exists`, `equals`, `contains`, `not_contains`, `matches_regex`
- **Empty checks list** → `Verdict.ERROR` (design mistake, never silent pass)
- **Aggregation:** all passed → `MATCHED`, none passed → `NOT_MATCHED`, some → `PARTIALLY_MATCHED`

### 5. Audit Records (`audit.py`)
**Separate from `LocalExecutor.ExecutionLogEntry`** — additive, richer record:
- `AuditRecord`: `audit_id`, `requested_by`, `worker`, `environment`, `action_name`, `started_at`, `ended_at`, `execution_success`, `verification_verdict`, `evidence_id`, `errors`, `payload_summary`
- `AuditLog` — append-only, in-process, never truncated/overwritten
- Bounding/persisting = same debt as `LocalExecutor._log` (named, not solved differently)

---

## Verification Lifecycle

### Per-Step Verification (from `BROWSER_WORKER_ARCHITECTURE.md` §10, `RUNTIME_ENGINE_ARCHITECTURE.md`)
```
1. Execute → LocalExecutor.execute(capability, payload) → ExecutionResult
2. Verify  → Verifier.verify(expected_outcome) → Evidence
3. Audit   → AuditRecord(execution_success, verification_verdict, evidence_id)
```

**Runtime Integration (`RUNTIME_ENGINE_ARCHITECTURE.md`):**
- `RuntimeEngine._verify()` calls `gateway.verify()` against task's `expected_outcome`
- **Execution success ≠ verification success** — `NOT_MATCHED` verdict = failed task
- No Verifier → Evidence = None, recorded honestly (not treated as pass)

### Mission Control Integration (`MISSION_CONTROL_ARCHITECTURE.md`)
- `task_completed` / `task_failed` events carry `evidence_id`
- `verification_started` / `verification_completed` events emitted
- Founder State carries Evidence *references* (not re-derived judgments)
- Audit Stream ingests every event (system-wide) — distinct from per-Worker `AuditLog`

---

## Evidence Model

### Flow: Execution → Evidence → Brain
```
Worker Action (Execute)
       │
       ▼
ExecutionResult (success, output, errors)
       │
       ▼
Verifier (Re-observe fresh)
       │
       ▼
Observation (JSON-shaped dict)
       │
       ▼
ExpectedOutcome (from Planner)
       │
       ▼
evaluate_checks() → Verdict + CheckResults
       │
       ▼
Evidence (observation + expected + verdict + check_results)
       │
       ▼
Shared Infrastructure (Memory) → Brain (Planner)
```

### Evidence Properties
- **Immutable** once created — `evidence_id` ties to `BrokerDecision.decision_id` for cost/benchmark tracking
- **Plain JSON** — survives logging, persistence, replay without consumer needing to know Worker type
- **Never trusts ExecutionResult** — Verification re-observes fresh (ADR-0011)
- **Available, not hidden** (Constitution §15.4)

---

## Current Implementation Status

| Component | Architecture Status | Implementation Status | Notes |
|-----------|---------------------|----------------------|-------|
| **`Verifier` ABC** | RESEARCH-BACKED (§10) | ✅ **IMPLEMENTED** | `verification/verifier.py` — concrete `verify()` + abstract `capture_observation_dict()` |
| **`evaluate_checks()`** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | `verification/evaluator.py` — pure, 5 operators, empty checks = ERROR |
| **Evidence Model** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | `verification/evidence.py` — `ObservationCheck`, `ExpectedOutcome`, `Verdict`, `Evidence`, `CheckResult` |
| **`BrowserVerifier`** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | `plugins/browser_verifier.py` — ~10 lines, implements `capture_observation_dict()` |
| **`normalize_observation()`** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | `plugins/browser_observation.py` — single Playwright touchpoint |
| **Audit System** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | `verification/audit.py` — `AuditRecord`, `AuditLog` (append-only) |
| **Runtime Integration** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | `RuntimeEngine._verify()` calls `gateway.verify()` |
| **Mission Control Events** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | `verification_started`/`completed` events with `evidence_id` |
| **Founder State** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | Carries Evidence references, not re-derived judgments |
| **Generic Package** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | `verification/` zero Environment imports |
| **Filesystem Verifier** | NOT SPECIFIED | ❌ **NOT IMPLEMENTED** | No Verifier for Filesystem capabilities yet |
| **Desktop/Terminal Verifiers** | FUTURE | ⏳ **RESERVED** | Generic package ready; awaits Workers |

---

## Open Questions

1. **Filesystem Verifier Missing** — No Verifier implemented for Filesystem capabilities. Filesystem Actions return `ExecutionResult` but no independent re-observation. Gap between Constitution §10 (mandatory Verification) and current implementation.

2. **ExpectedOutcome Schema Not Finalized** (§10.4) — Exact schema of "Expected Outcome"/"Observation", how comparisons computed, what counts as "partial" match = implementation questions. Not yet designed for non-browser Environments.

3. **Empty Checks = ERROR** — `evaluate_checks()` returns `Verdict.ERROR` for empty checks list. Is this the right default for all Environments? Browser Verifier always provides checks.

3. **Audit Log Unbounded** — `AuditLog` append-only in-memory (same debt as `LocalExecutor._log`). Named in `ROADMAP.md`, not solved differently.

4. **Verification Timing** — Constitution §10.2 says "After (or during) execution". Runtime calls verify after execute. Is "during" needed for long-running Actions?

5. **ObservationCheck Operators Extensibility** — Currently 5 operators. Deliberately flat/small. When does a second Worker need more? Bigger DSL easy to add, hard to remove.

6. **Cross-Worker Evidence Comparison** — Evidence is plain JSON. Can Brain compare Evidence across different Workers (Browser vs Filesystem)? Schema compatibility not yet designed.

---

## Design vs Implementation Differences

| Area | Design (Architecture/Constitution) | Implementation | Status |
|------|-----------------------------------|----------------|--------|
| **Verification Independent** | Own contract, never reuses Execution path | ✅ `Verifier.verify()` calls `capture_observation_dict()` | ✅ MATCH |
| **Re-observes Fresh** | Never reads ExecutionResult | ✅ `verify()` calls `capture_observation_dict()` | ✅ MATCH |
| **Execution ≠ Verification** | `NOT_MATCHED` = failed task | ✅ Runtime treats verdict as source of truth | ✅ MATCH |
| **Generic Package** | Zero Environment imports | ✅ `verification/` zero Playwright/browser imports | ✅ MATCH |
| **Evidence Model** | Plain JSON, immutable, `evidence_id` | ✅ `Evidence` dataclass with `evidence_id` | ✅ MATCH |
| **Evidence to Brain** | Routed via Shared Infrastructure | ✅ Mission Control events carry `evidence_id` | ✅ MATCH |
| **Empty Checks = ERROR** | Design mistake, not silent pass | ✅ `evaluate_checks()` returns `Verdict.ERROR` | ✅ MATCH |
| **Audit Separate from Execution Log** | Additive, richer record | ✅ `AuditRecord` + `AuditLog` distinct from `ExecutionLogEntry` | ✅ MATCH |
| **Filesystem Verifier** | Constitution §10 mandatory for all | ❌ Not implemented | ❌ MISSING |
| **ExpectedOutcome Schema** | Not yet designed for non-browser | ⏳ Not designed | ⏳ RESERVED |
| **Audit Log Persistence** | Named debt, not solved | 📝 Documented debt | 📝 DOCUMENTED |
| **Verification During Execution** | Constitution allows "during" | ⚠️ Runtime only verifies after | 📝 DOCUMENTED |

---

## Future Extraction Targets

1. `src/master_agent/verification/verifier.py` — `Verifier` ABC, `verify()` implementation
2. `src/master_agent/verification/evidence.py` — `ObservationCheck`, `ExpectedOutcome`, `Verdict`, `Evidence`, `CheckResult`
3. `src/master_agent/verification/evaluator.py` — `evaluate_checks()`, `get_field()`, 5 operators
4. `src/master_agent/verification/audit.py` — `AuditRecord`, `AuditLog`
5. `src/master_agent/plugins/browser_verifier.py` — `BrowserVerifier` (~10 lines)
6. `src/master_agent/plugins/browser_observation.py` — `normalize_observation()`, `BrowserObservation`
7. `src/master_agent/plugins/browser_worker.py` — `BrowserWorker.run_step()` (execute→verify→audit)
8. `src/master_agent/runtime/engine.py` — `_verify()` method
9. `src/master_agent/mission_control/` — Events with `evidence_id`, Founder State
10. `docs/adr/0011` — Verification as independent subsystem decision record

---

## Wiki Links Added

- `[[KALPAVRIKSHA_VISION_V2.md]]` — Constitution §5.6, §9.2, §10, §15.4
- `[[FOUNDER_CONSTITUTION_FREEZE.md]]` — Freeze record
- `[[BROWSER_WORKER_ARCHITECTURE.md]]` — Reference Worker implementation
- `[[RUNTIME_ENGINE_ARCHITECTURE.md]]` — Runtime verification integration
- `[[MISSION_CONTROL_ARCHITECTURE.md]]` — Events, Founder State, Audit Stream
- `[[ARCHITECTURE.md]]` — Implementation map
- `[[03_universal_executive_operator.md]]` — Operator responsibilities (§4.3)
- `[[06_runtime_engine.md]]` — Runtime Engine (_verify, gateway)
- `[[10_environment_execution.md]]` — Environment execution patterns
- `[[system_overview.md]]` — System overview
- `[[docs/adr/0011]]` — Verification independent subsystem

---

*Document created from verified sources only. No verification capabilities redesigned. Terminology preserved exactly. Constitution/Architecture/Implementation/Open Questions separated. Design/implementation differences recorded without reconciliation.*