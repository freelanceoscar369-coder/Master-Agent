# Architecture Risk Register

## Source
- All 26 KB documents
- Constitution Compliance Matrix
- Architecture Boundary Audit
- Architecture Gap Register
- Architecture Maturity Report

## Risk Ranking Criteria

| Rank | Definition |
|------|------------|
| **Critical** | Violates frozen Constitution, blocks core functionality, no workaround |
| **High** | Major capability missing, significant work required, workaround exists but painful |
| **Medium** | Noticeable gap, workaround exists, documented for future |
| **Low** | Minor gap, cosmetic or convenience, documented for future |

---

## Risk Register

| Risk ID | Risk Description | Affected Areas | Rank | Root Cause | Current Mitigation | Residual Risk |
|---------|------------------|----------------|------|------------|-------------------|---------------|
| **RISK-001** | **AI Capability Broker kernel service not implemented** — Architecture frozen (Amendment 2), but `src/master_agent/broker/` kernel service missing. Model Router and Workers cannot select providers. | Model Router (MB032), Workers needing intelligence, Planner, Brain completeness | **Critical** | Architecture frozen before implementation; MB027 architecture-only | Model Router fails closed (`BrokerUnavailable`); no provider selection possible | **Complete blockage** of intelligence selection; all AI calls fail |
| **RISK-002** | **AI Infrastructure Executive not implemented** — Machine-touching counterpart to Broker (scans, probes, benchmarks, inventories, installs) missing. Broker has no fresh inventory. | Broker inventory freshness, Provider discovery, Benchmarking, Concrete Provider integration | **Critical** | Architecture split (MB027) created Executive role but not implemented | Broker falls back to stale/declared inventory only | **Stale/absent inventory** → Broker makes decisions on unknown data |
| **RISK-003** | **Filesystem Verifier missing** — Constitution §10 mandates Verification for all capabilities. No `FilesystemVerifier` exists. 14 filesystem capabilities have no independent verification. | Verification Subsystem, Filesystem capabilities (14), Constitution §10 compliance | **Critical** | Constitution §10 requires Verification for all; Filesystem was first capability | ExecutionResult trusted without re-observation | **False confidence** — Execution success ≠ real-world outcome verified |
| **RISK-004** | **CapabilityManifest.input_schema/output_schema empty** — Declared in frozen `plugins/base.py`, populated by nothing. Planner guesses payload names (MB036 Finding 4). | Planner (MB036/037), all Plugins (Filesystem, Browser, ModelProvider), Capability Contract (MB039) | **Critical** | Declared in frozen `plugins/base.py` but never populated | Planner guesses payload names from prose | **Plans fail at execution** — MB037 live plan: `CreateFolder` needs `name`, plan sent `path` |
| **RISK-005** | **AI Capability Broker + AI Infrastructure Executive chicken-egg** — Broker needs inventory from Executive; Executive needs Broker for intelligence. Neither implemented. | Broker inventory, Executive discovery, Provider registration, Benchmarking | **Critical** | Architecture split created circular dependency | None | **Deadlock** — Neither can function without the other |
| **RISK-006** | **Reporter not built** — Constitution §3.4 explicitly names it; only `cli.py` completion messages exist. No structured reporting to founder. | Executive Brain, Founder-facing reporting, Transparency (§15.4) | **High** | Constitution §3.4 explicitly names it as missing | `cli.py` completion messages | **No structured reporting** — founder cannot review outcomes systematically |
| **RISK-007** | **Intent Layer not implemented** — `cli.py` regex `parse_intent()` is stand-in. Real Intent Layer pending real Planner. | Executive Brain, Planner input, Conversational path | **High** | Real Intent Layer pending real Planner (ROADMAP item 1) | Regex stand-in handles 9 filesystem shapes + project creation | **Fragile parsing** — cannot handle ambiguous intent, no clarification |
| **RISK-008** | **Planner not wired to `cli.py` conversational path** — MB037 wired Planner to MissionControl path; `cli.py` still uses regex stand-in. | Executive Brain, Planner integration, Conversational UX | **High** | MB037 wired MissionControl path; `cli.py` path separate | Regex stand-in handles current commands | **Inconsistent behavior** — conversational vs programmatic paths differ |
| **RISK-009** | **MissionManager unwired from live path** — Imports `MemoryStore` but `cli.py`'s `MasterAgentSession` is only live path. | Mission State ownership (Shared Infra §5.3), Recovery, Persistence | **High** | Scoped to "real Planner" work (ROADMAP item 3) | `MasterAgentSession` persists at terminal states | **Mission State not in Shared Infra** — violates Constitution §5.3 |
| **RISK-010** | **`_current_objective_id` never advances** — `submit_objective()` sets only when `None`; after boot scan, all later missions point at scan. | Mission Control, Founder State, `founder_state()` contract | **High** | Frozen `mission_control/`; MB037 didn't fix | Founder page reads plan history (unaffected) | **Founder State contract broken** — reports wrong current objective |
| **RISK-011** | **Orchestrator does NOT trigger Verification** — Constitution §4.1 says it does; Runtime does it instead. | Orchestrator, Runtime, Verification Subsystem, Constitution §4.1 | **Medium** | MB037 moved Verification to Runtime; Constitution not updated | Runtime `_verify()` does it | **Constitution/code divergence** — misleading documentation |
| **RISK-012** | **Two approval gates** — Orchestrator checks PermissionSystem; Runtime has separate ApprovalGate at `_handle_task()`. | Orchestrator, Runtime, Approval flow, Relay pattern (ADR-0005) | **Medium** | MB028.0 added Runtime gate; Orchestrator gate pre-existed | Relay pattern (ADR-0005) connects them | **Complexity** — two gates, relay pattern, potential for drift |
| **RISK-013** | **CapabilityManifest.input_schema/output_schema empty** — Declared in `plugins/base.py`, populated by nothing. | Planner, all Plugins, Capability Contract (MB039), CapabilityIndex | **Critical** | Declared in frozen `plugins/base.py`, never populated | Planner guesses from prose | **Duplicate of RISK-004** — same root cause |
| **RISK-014** | **Filesystem Verifier missing** — Constitution §10 mandatory for all; no `FilesystemVerifier` exists. | Verification Subsystem, Filesystem (14 caps), Constitution §10 | **Critical** | Constitution §10 mandatory for all | None | **Duplicate of RISK-003** |
| **RISK-015** | **ADR-0015 Proposed** — `TaskDispatcher.restore_objective()` additive change to frozen components awaiting ratification. | Persistence, Mission Control, Recovery | **High** | MB025 design conflict with Rule 4 | Manual recovery only | **Blocks persistence completeness** |
| **RISK-015** | **ADR-0020 Proposed** — Founder Approval Workflow ships frozen-component changes. | Approval workflow, Mission Control, Runtime | **High** | MB028.1 added workflow; frozen files changed | Current approval flow works | **Blocks approval workflow completeness** |
| **RISK-016** | **`_current_objective_id` never advances** — `submit_objective()` sets only when `None`; after boot scan, all missions point at scan. | Mission Control, Founder State, `founder_state()` contract | **High** | Frozen `mission_control/`; MB037 didn't fix | Founder page uses plan history (unaffected) | **Founder State contract broken** |
| **RISK-017** | **Pause/resume/cancel not implemented** — Needs ratified ADR (MB037 §5). | Mission Control, Mission Lifecycle, `test_missions_lifecycle.py` | **Medium** | Needs ratified ADR; MB037 forbade both options | None | **Cannot pause/resume/cancel missions** |
| **RISK-018** | **Two Plugin integration surfaces for Browser** — `BrowserPlugin` (Orchestrator) + `BrowserWorker` (facade). | Browser Worker, Orchestrator, Verification integration | **Medium** | MB022 built both; awaits second Verifier-backed Worker | Both work; `BrowserWorker` is Constitution-complete | **Dual maintenance** — two surfaces, potential drift |
| **RISK-019** | **Capability selection policy** — `find_for_capability()` returns list; Founder Edition takes first. | Plugin Registry, multiple providers | **Low** | Documented as EVOLVABLE | First candidate taken | **Arbitrary selection** when multiple providers exist |
| **RISK-019** | **Thread-affine Environment Sessions** — Browser Session must use creating thread (Playwright sync API). | Runtime, Browser Worker, Objectives | **Medium** | Playwright constraint documented | Objectives must open/close session as tasks | **Constraint on objective design** — cannot interleave |
| **RISK-020** | **Pause/resume/cancel needs ADR** — Needs ratified ADR (MB037 §5). | Mission Control, Mission Lifecycle | **Medium** | Needs ratified ADR | None | **Cannot pause/resume/cancel** |
| **RISK-020** | **Event Bus synchronous/in-process** — Named as future revisiting for multi-process. | Mission Control, Event Bus, Audit Stream | **Low** | Interface small for drop-in replacement | Works for Founder Edition | **Blocks multi-process scaling** |
| **RISK-021** | **Audit Stream unbounded in-memory** — Same debt as `LocalExecutor._log`. | Mission Control, Audit Stream, `ROADMAP.md` | **Low** | Same debt as `LocalExecutor._log` | Not solved differently | **Memory growth** in long-running daemon |
| **RISK-022** | **Dispatcher readiness O(tasks) not incremental** | Mission Control, Task Dispatcher | **Low** | Documented in MB023 debt | Works for single-founder | **Scaling limit** |
| **RISK-023** | **Capability selection policy** — `find_for_capability()` returns list; no policy for multiple providers. | Plugin Registry | **Low** | Documented as EVOLVABLE | First candidate taken | **Arbitrary selection** |
| **RISK-024** | **CapabilityManifest.input_schema/output_schema empty** — Duplicate of RISK-004. | All Plugins, Planner | **Critical** | Same as RISK-004 | Same | **Duplicate** |
| **RISK-025** | **Filesystem Verifier missing** — Duplicate of RISK-003. | Filesystem, Verification | **Critical** | Same as RISK-003 | Same | **Duplicate** |

---

## Risk Summary by Rank

| Rank | Count | Risk IDs |
|------|-------|----------|
| **Critical** | 6 | RISK-001, RISK-002, RISK-003, RISK-004, RISK-005, RISK-013 (dup) |
| **High** | 7 | RISK-006, RISK-007, RISK-008, RISK-009, RISK-010, RISK-014, RISK-015 |
| **Medium** | 5 | RISK-011, RISK-012, RISK-016, RISK-017, RISK-018, RISK-019 |
| **Low** | 3 | RISK-019, RISK-020, RISK-021, RISK-022, RISK-023 |

---

## Top 5 Risks Requiring Immediate Attention

| Priority | Risk ID | Description | Why Critical |
|----------|---------|-------------|--------------|
| **1** | **RISK-001** | AI Capability Broker kernel service missing | Complete blockage of intelligence selection; all AI calls fail |
| **2** | **RISK-002** | AI Infrastructure Executive missing | Deadlock with Broker; no inventory freshness |
| **3** | **RISK-003** | Filesystem Verifier missing | Constitution §10 violation; false confidence in execution |
| **4** | **RISK-004** | CapabilityManifest schemas empty | Plans fail at execution; Planner guesses payloads |
| **5** | **RISK-005** | Broker ↔ Executive chicken-egg | Neither can function; deadlock |

---

## Recommended Phase 2 Audit

1. **Broker Implementation Deep Dive** — `src/master_agent/broker/`, `src/master_agent/ai_infrastructure/service.py`, `docs/adr/0017`, `docs/adr/0018`
2. **Verification Subsystem Completeness** — `src/master_agent/verification/`, `docs/adr/0011`, Filesystem Verifier design
3. **Capability Contract Integration** — `src/master_agent/capabilities/`, `src/master_agent/plugins/base.py`, MB039 follow-up
4. **Brain Wiring** — `src/master_agent/planner/`, `src/master_agent/plugins/model_router.py`, `src/master_agent/cli.py`
5. **Mission State Wiring** — `src/master_agent/mission_manager/`, `src/master_agent/memory/`, ADR-0015
6. **Approval Flow Unification** — `src/master_agent/runtime/approval.py`, `src/master_agent/orchestrator/orchestrator.py`, ADR-0019, ADR-0020

---

*Generated from Phase 1 audit findings. No fixes recommended. Only risks identified and ranked.*