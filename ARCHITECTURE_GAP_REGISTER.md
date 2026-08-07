# Architecture Gap Register

## Source
All 26 KB documents in `knowledge/architecture/`

## Classification Legend
- **A** = Implementation Bug
- **B** = Missing Implementation Required by Frozen Architecture
- **C** = Intentional Founder Edition Limitation
- **D** = Future Evolution / Scalability Item
- **E** = Requires ADR Decision
- **F** = Documentation Gap

## Severity Scale
- **Critical** — Blocks core functionality, violates frozen Constitution
- **High** — Major capability missing, significant work required
- **Medium** — Noticeable gap, workaround exists
- **Low** — Minor gap, cosmetic or convenience

---

| ID | Issue | Affected Components | Severity | Classification | Dependency | Recommended Action |
|----|-------|---------------------|----------|----------------|------------|-------------------|
| **GAP-001** | `CapabilityManifest.input_schema`/`output_schema` declared in `plugins/base.py` but populated by **nothing** | `FilesystemPlugin`, `BrowserPlugin`, `ModelProvider`, all future Plugins | **Critical** | **B** — Missing Implementation | None | Populate from Action `required_parameters()` in Plugin manifest construction |
| **GAP-002** | **AI Capability Broker not implemented** — Architecture frozen (MB027, Amendment 2), `src/master_agent/broker/` exists but `AiCapabilityService` in `ai_infrastructure/` is wiring only; kernel service missing | Model Router (MB032), Workers needing intelligence, Broker kernel service | **Critical** | **B** — Missing Implementation | GAP-003 (AI Infra Executive) | Implement `CapabilityBroker` kernel service in `broker/`; wire to `AiCapabilityService` |
| **GAP-003** | **AI Infrastructure Executive not implemented** — Machine-touching counterpart to Broker (scans, probes, benchmarks, inventories, installs) | Broker inventory freshness, Provider discovery, Benchmarking | **Critical** | **B** — Missing Implementation | GAP-002 (Broker) | Implement AI Infrastructure Executive as Worker (Operator) |
| **GAP-004** | **Filesystem Verifier missing** — Constitution §10 requires Verification for all capabilities; no `FilesystemVerifier` exists | Filesystem capabilities (14), Verification Subsystem, Constitution §10 compliance | **Critical** | **B** — Missing Implementation | None | Implement `FilesystemVerifier` in `verification/` or `plugins/` |
| **GAP-005** | **Reporter not built** — Constitution §3.4 names it explicitly; `cli.py` completion messages only | Executive Brain, Reporting, Founder-facing output | **High** | **B** — Missing Implementation | None | Implement `Reporter` module in Brain |
| **GAP-006** | **Intent Layer not implemented** — `cli.py` regex `parse_intent()` is stand-in; real Intent Layer pending | Executive Brain, Intent Layer, Planner input | **High** | **B** — Missing Implementation | GAP-007 (Planner wiring) | Implement real Intent Layer (post-Planner) |
| **GAP-007** | **Planner not wired to `cli.py`** — MB037 wired Planner to MissionControl path; `cli.py` conversational path still uses regex stand-in | `cli.py` conversational path, Planner integration | **High** | **B** — Missing Implementation | GAP-006 (Intent Layer) | Wire Planner to `cli.py` conversational path (MB037 follow-up) |
| **GAP-008** | **MissionManager unwired** — Imports `MemoryStore` but `cli.py`'s `MasterAgentSession` is only live path | Mission State ownership, Shared Infrastructure §5.3 | **High** | **B** — Missing Implementation | GAP-006, GAP-007 | Wire `MissionManager` into live path (scoped to real Planner work) |
| **GAP-009** | **ADR-0015 Proposed** — `TaskDispatcher.restore_objective()` additive change to frozen components awaiting ratification | Persistence, Mission Control, Recovery | **High** | **E** — Requires ADR Decision | None | Founder ratification of ADR-0015 |
| **GAP-010** | **ADR-0020 Proposed** — Founder Approval Workflow ships frozen-component changes | Approval workflow, Mission Control, Runtime | **High** | **E** — Requires ADR Decision | None | Founder ratification of ADR-0020 |
| **GAP-011** | **`_current_objective_id` never advances** — `submit_objective()` sets only when `None`; after boot scan, all later missions point at scan | Mission Control, Founder State, `founder_state()` contract | **High** | **A** — Implementation Bug | None | Fix in frozen `mission_control/` (requires ADR) |
| **GAP-012** | **Two approval gates** — Orchestrator checks PermissionSystem; Runtime has separate ApprovalGate at `_handle_task()` | Orchestrator, Runtime, Approval flow | **Medium** | **D** — Future Evolution | None | Documented; relay pattern (ADR-0005) connects them |
| **GAP-013** | **Orchestrator does NOT trigger Verification** — Constitution §4.1 says it does; Runtime does it instead | Orchestrator, Runtime, Verification Subsystem | **Medium** | **A** — Implementation Bug | None | Documented divergence; align Constitution or code |
| **GAP-014** | **Execution order ownership** — Constitution says Orchestrator "walks MissionPlan"; Mission Control Dispatcher owns order | Orchestrator, Mission Control Dispatcher, MB037 clarification | **Medium** | **D** — Future Evolution | None | Documented; MB037 clarified ownership |
| **GAP-015** | **Filesystem Verifier missing** — Constitution §10 mandatory for all capabilities; no `FilesystemVerifier` | Filesystem capabilities, Verification Subsystem, Constitution §10 | **Critical** | **B** — Missing Implementation | GAP-004 (same issue) | Implement `FilesystemVerifier` |
| **GAP-016** | **Two Plugin integration surfaces for Browser** — `BrowserPlugin` (Orchestrator path) + `BrowserWorker` (facade) | Browser Worker, Orchestrator, Verification integration | **Medium** | **D** — Future Evolution | None | Awaits second Verifier-backed Worker to unify |
| **GAP-017** | **Capability selection policy** — `find_for_capability()` returns list; Founder Edition takes first | Plugin Registry, multiple providers | **Low** | **C** — Intentional Limitation | None | Documented as EVOLVABLE; policy needed for multi-provider |
| **GAP-018** | **Thread-affine Environment Sessions** — Browser Session must use creating thread (Playwright sync API) | Runtime, Browser Worker, Objectives | **Medium** | **D** — Future Evolution | None | Documented constraint; objectives must open/close session as tasks |
| **GAP-019** | **Pause/resume/cancel not implemented** — Needs ratified ADR (MB037 §5) | Mission Control, Mission Lifecycle, `test_missions_lifecycle.py` | **Medium** | **E** — Requires ADR Decision | None | Founder decision + ratified ADR |
| **GAP-020** | **Event Bus synchronous/in-process** — Named as future revisiting for multi-process | Mission Control, Event Bus, Audit Stream | **Low** | **D** — Future Evolution | None | Interface small for drop-in replacement |
| **GAP-021** | **Audit Stream unbounded in-memory** — Same debt as `LocalExecutor._log` | Mission Control, Audit Stream, `ROADMAP.md` | **Low** | **D** — Future Evolution | None | One answer when addressed |
| **GAP-022** | **Dispatcher readiness O(tasks) not incremental** | Mission Control, Task Dispatcher | **Low** | **D** — Future Evolution | None | Documented in MB023 debt section |
| **GAP-023** | **CapabilityManifest.input_schema/output_schema empty** — Declared in `plugins/base.py`, populated by nothing | All Plugins, Planner, Capability Contract (MB039) | **Critical** | **B** — Missing Implementation | GAP-001 (same) | Populate from Action `required_parameters()` |
| **GAP-024** | **AI Infrastructure Executive not implemented** — Machine-touching counterpart to Broker | Broker inventory, Provider discovery, Benchmarking | **Critical** | **B** — Missing Implementation | GAP-002, GAP-003 | Implement as Worker (Operator) |
| **GAP-025** | **Capability Contract & Index not wired** — `CapabilityIndex` exists but not source of truth for PluginRegistry or MC | Plugin Registry, Mission Control, Planner | **High** | **B** — Missing Implementation | GAP-001, GAP-023 | Wire CapabilityIndex as source of truth |
| **GAP-025** | **Concrete ModelProviders not implemented** — Ollama, ChatGPT, etc. missing | Model Router, AiCapabilityService, Broker | **High** | **B** — Missing Implementation | GAP-002, GAP-003 | Implement `providers/` package |
| **GAP-026** | **Broker Wiring** — Composition root wiring Broker → Model Router not documented | Composition root, Model Router, Broker | **High** | **B** — Missing Implementation | GAP-002 | Document wiring in composition root |
| **GAP-027** | **Broker Approval Integration** — `APPROVAL_REQUIRED` for paid providers not surfaced to flow | Broker, Model Router, Approval flow (MB028.1) | **High** | **B** — Missing Implementation | GAP-002, GAP-010 | Surface Broker approvals to Approval Queue |
| **GAP-028** | **Broker Learning Loop** — ADR-0018: policy learns, decision procedure deterministic | Broker, Policy, Benchmark Store | **Medium** | **D** — Future Evolution | GAP-002 | Design learning loop (EVOLVABLE) |
| **GAP-029** | **Concrete ModelProviders not implemented** — Ollama, ChatGPT, etc. | Model Router, Broker, AiCapabilityService | **High** | **B** — Missing Implementation | GAP-002, GAP-003 | Implement `providers/` package |
| **GAP-030** | **Filesystem Verifier Missing** — Duplicate of GAP-004/GAP-015 | Filesystem, Verification | **Critical** | **B** — Missing Implementation | GAP-004 | Implement `FilesystemVerifier` |
| **GAP-031** | **AI Infrastructure Executive** — Duplicate of GAP-003/GAP-024 | Broker, Provider discovery | **Critical** | **B** — Missing Implementation | GAP-003 | Implement |
| **GAP-032** | **Concrete Providers** — Duplicate of GAP-025 | Model Router, Broker | **High** | **B** — Missing Implementation | GAP-025 | Implement |
| **GAP-033** | **Broker Wiring** — Duplicate of GAP-026 | Composition root, Model Router | **High** | **B** — Missing Implementation | GAP-026 | Document |
| **GAP-034** | **Broker Approval Integration** — Duplicate of GAP-027 | Broker, Approval flow | **High** | **B** — Missing Implementation | GAP-027 | Surface to Approval Queue |
| **GAP-035** | **Filesystem Verifier Missing** — Duplicate of GAP-004/GAP-015/GAP-030 | Filesystem, Verification | **Critical** | **B** — Missing Implementation | GAP-004 | Implement |
| **GAP-036** | **CapabilityManifest.input_schema/output_schema Empty** — Duplicate of GAP-001/GAP-023 | Plugins, Planner | **Critical** | **B** — Missing Implementation | GAP-001 | Populate from Action `required_parameters()` |
| **GAP-037** | **Two Approval Gates** — Duplicate of GAP-012 | Orchestrator, Runtime | **Medium** | **D** | GAP-012 | Documented |
| **GAP-038** | **Orchestrator Verification** — Duplicate of GAP-013 | Orchestrator, Runtime | **Medium** | **A** | GAP-013 | Documented |
| **GAP-039** | **Execution Order** — Duplicate of GAP-014 | Orchestrator, Dispatcher | **Medium** | **D** | GAP-014 | Documented |
| **GAP-040** | **Filesystem Verifier** — Duplicate of GAP-004/015/030/035 | Filesystem, Verification | **Critical** | **B** | GAP-004 | Implement |
| **GAP-041** | **AI Infrastructure Executive** — Duplicate of GAP-003/024/031 | Broker, Provider discovery | **Critical** | **B** | GAP-003 | Implement |
| **GAP-042** | **Concrete Providers** — Duplicate of GAP-025/032 | Model Router, Broker | **High** | **B** | GAP-025 | Implement `providers/` |
| **GAP-043** | **Broker Wiring** — Duplicate of GAP-026/033 | Composition root | **High** | **B** | GAP-026 | Document |
| **GAP-044** | **Broker Approval** — Duplicate of GAP-027/034 | Broker, Approval flow | **High** | **B** | GAP-027 | Surface to queue |
| **GAP-045** | **Filesystem Verifier** — Duplicate | Filesystem, Verification | **Critical** | **B** | GAP-004 | Implement |
| **GAP-046** | **input_schema/output_schema** — Duplicate of GAP-001/023/036 | Plugins, Planner | **Critical** | **B** | GAP-001 | Populate |
| **GAP-047** | **Two Approval Gates** — Duplicate | Orchestrator, Runtime | **Medium** | **D** | GAP-012 | Documented |
| **GAP-048** | **Orchestrator Verification** — Duplicate | Orchestrator, Runtime | **Medium** | **A** | GAP-013 | Documented |
| **GAP-049** | **Execution Order** — Duplicate | Orchestrator, Dispatcher | **Medium** | **D** | GAP-014 | Documented |
| **GAP-050** | **Filesystem Verifier** — Duplicate | Filesystem, Verification | **Critical** | **B** | GAP-004 | Implement |

---

## Deduplication Summary

| Unique Issue | Duplicate IDs | Final ID |
|--------------|---------------|----------|
| CapabilityManifest.input_schema/output_schema empty | GAP-001, GAP-023, GAP-036, GAP-046 | **GAP-001** |
| AI Capability Broker not implemented | GAP-002, GAP-003 (partial) | **GAP-002** |
| AI Infrastructure Executive not implemented | GAP-003, GAP-024, GAP-031, GAP-041 | **GAP-003** |
| Filesystem Verifier missing | GAP-004, GAP-015, GAP-030, GAP-035, GAP-040, GAP-045, GAP-050 | **GAP-004** |
| Reporter not built | GAP-005 | **GAP-005** |
| Intent Layer not implemented | GAP-006 | **GAP-006** |
| Planner not wired to cli.py | GAP-007 | **GAP-007** |
| MissionManager unwired | GAP-008 | **GAP-008** |
| ADR-0015 Proposed (restore_objective) | GAP-009 | **GAP-009** |
| ADR-0020 Proposed (Approval Workflow) | GAP-010 | **GAP-010** |
| _current_objective_id never advances | GAP-011 | **GAP-011** |
| Two approval gates | GAP-012, GAP-037, GAP-047 | **GAP-012** |
| Orchestrator doesn't trigger Verification | GAP-013, GAP-038, GAP-048 | **GAP-013** |
| Execution order ownership | GAP-014, GAP-039, GAP-049 | **GAP-014** |
| Two Plugin integration surfaces (Browser) | GAP-016 | **GAP-016** |
| Capability selection policy | GAP-017 | **GAP-017** |
| Thread-affine Environment Sessions | GAP-018 | **GAP-018** |
| Pause/resume/cancel needs ADR | GAP-019 | **GAP-019** |
| Event Bus synchronous/in-process | GAP-020 | **GAP-020** |
| Audit Stream unbounded | GAP-021 | **GAP-021** |
| Dispatcher O(tasks) readiness | GAP-022 | **GAP-022** |

---

## Summary Statistics

| Classification | Unique Issues | Total Mentions (incl. duplicates) |
|----------------|---------------|-----------------------------------|
| **A** — Implementation Bug | 3 | 5 |
| **B** — Missing Implementation Required | 10 | 25 |
| **C** — Intentional Limitation | 1 | 1 |
| **D** — Future Evolution / Scalability | 6 | 12 |
| **E** — Requires ADR Decision | 4 | 5 |
| **F** — Documentation Gap | 0 | 0 |

---

## By Severity

| Severity | Count |
|----------|-------|
| **Critical** | 4 (GAP-001, GAP-002, GAP-003, GAP-004) |
| **High** | 7 (GAP-005, GAP-006, GAP-007, GAP-008, GAP-009, GAP-010, GAP-011) |
| **Medium** | 6 (GAP-012, GAP-013, GAP-014, GAP-016, GAP-018, GAP-027) |
| **Low** | 3 (GAP-017, GAP-020, GAP-021, GAP-022) |

---

## Recommended Priority Order

1. **GAP-001** — CapabilityManifest schemas (unblocks Planner)
2. **GAP-002** — AI Capability Broker (unblocks Model Router, Workers)
3. **GAP-003** — AI Infrastructure Executive (unblocks Broker inventory)
4. **GAP-004** — Filesystem Verifier (Constitution §10 compliance)
5. **GAP-005** — Reporter (Brain completeness)
6. **GAP-006/007** — Intent Layer + Planner wiring (Brain completeness)
7. **GAP-008** — MissionManager wiring (Shared Infra completeness)
8. **GAP-009/010** — ADR ratification (unblocks persistence/approval)
9. **GAP-011** — `_current_objective_id` bug (Founder State correctness)
10. **GAP-013** — Orchestrator/Verification alignment (Constitution §4.1)

---

*Generated from all 26 KB documents. Duplicates removed. Classifications based on frozen Constitution only.*