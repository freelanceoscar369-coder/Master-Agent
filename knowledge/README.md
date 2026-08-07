# Kalpavriksha Knowledge Base

## Purpose

This Knowledge Base is the authoritative documentation for the Kalpavriksha Architecture — a local-first, cloud-enhanced AI orchestration platform that turns human intention into verified outcomes.

It serves as the single source of truth for:

- **Architecture Decisions** — frozen by Constitution, audited by Phase 1/2 audits
- **Implementation Reality** — traced to source code, Mission Briefs, ADRs
- **System Understanding** — for contributors, auditors, and future maintainers

> **This is not a design document.** It is a record of what exists, verified against source code and frozen Constitution.

---

## Reading Order for New Contributors

### 1. Constitutional Foundation (Start Here)
| Order | Document | Purpose |
|-------|----------|---------|
| 1 | [Constitution Summary](architecture/02_constitution.md) | Frozen architecture principles, rules, terminology |
| 2 | [System Overview](architecture/00_system_overview.md) | High-level architecture map, three-layer separation |
| 3 | [Founder Constitution Freeze](architecture/FOUNDER_CONSTITUTION_FREEZE.md) | Freeze declaration, amendment history |

### 2. Layer Architecture (Core Understanding)
| Order | Document | Layer |
|-------|----------|-------|
| 4 | [Executive Brain](architecture/01_executive_brain.md) | Executive Brain |
| 5 | [Shared Infrastructure](architecture/04_shared_infrastructure.md) | Shared Infrastructure |
| 6 | [Universal Executive Operator](architecture/03_universal_executive_operator.md) | Universal Executive Operator |
| 7 | [Mission Control](architecture/07_mission_control.md) | Coordination |
| 8 | [Runtime Engine](architecture/06_runtime_engine.md) | Runtime |
| 9 | [Memory System](architecture/05_memory_system.md) | Memory (Layers 1-6) |
| 10 | [Persistence Architecture](architecture/08_persistence_architecture.md) | Persistence |

### 10. Capability Layer
| Order | Document | Domain |
|-------|----------|--------|
| 11 | [Action Contract](architecture/15_action_contract.md) | Action Contract |
| 12 | [Filesystem Capabilities](architecture/16_filesystem_capabilities.md) | Filesystem |
| 13 | [Browser Worker](architecture/18_browser_worker.md) | Browser |
| 14 | [Orchestrator](architecture/17_orchestrator.md) | Orchestration |
| 15 | [Plugin System](architecture/13_plugin_system.md) | Plugins |
| 16 | [Capability Contract](architecture/22_capability_contract.md) | Contracts |

### 11. AI Layer
| Order | Document | Domain |
|-------|----------|--------|
| 17 | [AI Capability Broker](architecture/09_ai_capability_broker.md) | Broker Architecture |
| 18 | [Model Router](architecture/14_model_router.md) | Model Routing |
| 19 | [AI Capability Service](architecture/19_ai_capability_service.md) | Service Wiring |
| 20 | [Text Verifier](architecture/20_text_verifier.md) | Verification |

### 12. Knowledge & Verification
| Order | Document | Domain |
|-------|----------|--------|
| 21 | [Knowledge Memory](architecture/21_knowledge_memory.md) | Knowledge Memory (L4) |
| 22 | [Verification System](architecture/11_verification_system.md) | Verification |
| 23 | [Permission & Security](architecture/12_permission_security.md) | Security |
| 24 | [Environment Execution](architecture/10_environment_execution.md) | Environments |

### 13. Audit Documents (Phase 1 & 2)
| Order | Document | Phase |
|-------|----------|-------|
| 25 | [Constitution Compliance Matrix](CONSTITUTION_COMPLIANCE_MATRIX.md) | Phase 1 |
| 26 | [Architecture Boundary Audit](ARCHITECTURE_BOUNDARY_AUDIT.md) | Phase 1 |
| 27 | [Architecture Gap Register](ARCHITECTURE_GAP_REGISTER.md) | Phase 1 |
| 28 | [Maturity Report](ARCHITECTURE_MATURITY_REPORT.md) | Phase 1 |
| 29 | [Risk Register](ARCHITECTURE_RISK_REGISTER.md) | Phase 1 |
| 30 | [Broker Implementation Audit](knowledge/audit/BROKER_IMPLEMENTATION_AUDIT.md) | Phase 2.1 |
| 31 | [Broker Bootstrap Analysis](knowledge/audit/BROKER_BOOTSTRAP_ANALYSIS.md) | Phase 2.1 |
| 32 | [Broker Dependency Graph](knowledge/audit/BROKER_DEPENDENCY_GRAPH.md) | Phase 2.1 |
| 33 | [Broker Maturity Score](knowledge/audit/BROKER_MATURITY_SCORE.md) | Phase 2.1 |

---

## High-Level Architecture Map

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        KALPAVRIKSHA ARCHITECTURE                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    EXECUTIVE BRAIN (Decides)                         │   │
│  │  Intent Layer → Planner → Model Router → Reporter                   │   │
│  │  Never executes, never touches Environment, never holds Permission  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                       │
│                                    ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                  SHARED INFRASTRUCTURE (Single Source)              │   │
│  │  Capability Registry │ Permission System │ Mission State │ Memory   │   │
│  │  Configuration       │ Telemetry/Audit   │ AI Capability Broker     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                       │
│                                    ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                  UNIVERSAL EXECUTIVE OPERATOR (Executes)             │   │
│  │  Orchestrator │ Worker Runtime │ Verification │ Environment Sessions │   │
│  │  Never decides, never plans — only executes and verifies            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                       │
│              ┌─────────────────────┼─────────────────────┐               │
│              ▼                     ▼                     ▼               │
│     ┌───────────────┐      ┌───────────────┐      ┌───────────────┐     │
     │  FILESYSTEM     │      │    BROWSER    │      │  AI LAYER     │     │
     │  14 capabilities│      │  9 capabilities│      │  Broker +     │     │
     │  Action Contract│      │  Playwright    │      │  Model Router │     │
     └───────────────┘      └───────────────┘      └───────────────┘     │
                                                                          │
     ┌─────────────────────────────────────────────────────────────────┐  │
     │                    MISSION CONTROL (Coordinates)                 │  │
     │  Event Bus │ Executive Registry │ Task Dispatcher │ Queues      │  │
     │  Founder State │ Audit Stream │ Knowledge Acquisition           │  │
     └─────────────────────────────────────────────────────────────────┘  │
                                                                          │
     ┌─────────────────────────────────────────────────────────────────┐  │
     │                    RUNTIME ENGINE (Heartbeat)                    │  │
     │  Observe → Dispatch → Execute → Verify → Report → Idle → Repeat │  │
     └─────────────────────────────────────────────────────────────────┘  │
                                                                          │
     ┌─────────────────────────────────────────────────────────────────┐  │
     │                    PERSISTENCE (Survives Restart)                │  │
     │  Event Log (JSONL) + Snapshots (JSON) → recover()               │  │
     └─────────────────────────────────────────────────────────────────┘  │
                                                                          │
     ┌─────────────────────────────────────────────────────────────────┐  │
     │                    MEMORY & KNOWLEDGE                            │  │
     │  L1 Conversation │ L2 Mission │ L3 SQLite │ L4 Knowledge       │  │
     │  L5 Vector (future) │ L6 Cloud Sync (optional)                  │  │
     └─────────────────────────────────────────────────────────────────┘  │
                                                                          │
     ┌─────────────────────────────────────────────────────────────────┐  │
     │                    AI CAPABILITY BROKER (Kernel)                 │  │
     │  Provider Registry │ Decision Engine │ Cost Model │ Benchmarks  │  │
     │  Approval Policy   │ Recommendations  │ Verification Loop       │  │
     └─────────────────────────────────────────────────────────────────┘  │
                                                                          │
     ┌─────────────────────────────────────────────────────────────────┐  │
     │                    VERIFICATION & KNOWLEDGE                      │  │
     │  Execute → Verify → Evidence → Memory → Knowledge Lifecycle     │  │
     └─────────────────────────────────────────────────────────────────┘  │
                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Source Document References

### Frozen Constitution
- [KALPAVRIKSHA_VISION_V2.md](../docs/architecture/KALPAVRIKSHA_VISION_V2.md) — Frozen Constitution v2 Revision 3
- [FOUNDER_CONSTITUTION_FREEZE.md](../docs/architecture/FOUNDER_CONSTITUTION_FREEZE.md) — Freeze declaration, amendments

### Implementation Maps
- [ARCHITECTURE.md](../ARCHITECTURE.md) — Current implementation module map, data flow
- [MEMORY_ARCHITECTURE.md](../MEMORY_ARCHITECTURE.md) — Six-layer memory design
- [FILESYSTEM_CAPABILITIES.md](../FILESYSTEM_CAPABILITIES.md) — Action Contract pattern
- [BROWSER_WORKER_ARCHITECTURE.md](../BROWSER_WORKER_ARCHITECTURE.md) — Reference Worker implementation
- [MISSION_CONTROL_ARCHITECTURE.md](../MISSION_CONTROL_ARCHITECTURE.md) — Coordination layer
- [RUNTIME_ENGINE_ARCHITECTURE.md](../RUNTIME_ENGINE_ARCHITECTURE.md) — Heartbeat loop
- [PERSISTENCE_ARCHITECTURE.md](../PERSISTENCE_ARCHITECTURE.md) — Event log + snapshot recovery
- [AI_CAPABILITY_BROKER_ARCHITECTURE.md](../AI_CAPABILITY_BROKER_ARCHITECTURE.md) — Broker design

### Mission Briefs
- [MISSION_BRIEF_001.md](../docs/MISSION_BRIEF_001.md) through [MISSION_BRIEF_005.md](../docs/MISSION_BRIEF_005.md) — Early implementation
- [MISSION_BRIEF_021_REVISION_3.md](../docs/MISSION_BRIEF_021_REVISION_3.md) — Constitution freeze
- [MISSION_BRIEF_022.md](../docs/MISSION_BRIEF_022.md) — Browser Worker
- [MISSION_BRIEF_023.md](../docs/MISSION_BRIEF_023.md) — Mission Control
- [MISSION_BRIEF_024.md](../docs/MISSION_BRIEF_024.md) — Runtime Engine
- [MISSION_BRIEF_025.md](../docs/MISSION_BRIEF_025.md) — Persistence
- [MISSION_BRIEF_026.md](../docs/MISSION_BRIEF_026.md) — Founder Dashboard
- [MISSION_BRIEF_027.md](../docs/MISSION_BRIEF_027.md) — AI Capability Broker
- [MISSION_BRIEF_028_0.md](../docs/MISSION_BRIEF_028_0.md) — Runtime Permission Boundary
- [MISSION_BRIEF_028_1.md](../docs/MISSION_BRIEF_028_1.md) — Founder Approval Workflow
- [MISSION_BRIEF_029.md](../docs/MISSION_BRIEF_029.md) — Founder Dashboard V2
- [MISSION_BRIEF_030.md](../docs/MISSION_BRIEF_030.md) — Desktop Executive
- [MISSION_BRIEF_031.md](../docs/MISSION_BRIEF_031.md) — AI Capability Broker
- [MISSION_BRIEF_032.md](../docs/MISSION_BRIEF_032.md) — Wiring Broker
- [MISSION_BRIEF_033.md](../docs/MISSION_BRIEF_033.md) — Ollama Provider
- [MISSION_BRIEF_034.md](../docs/MISSION_BRIEF_034.md) — Persistent Founder Memory
- [MISSION_BRIEF_035.md](../docs/MISSION_BRIEF_035.md) — Verifying Generated Text
- [MISSION_BRIEF_036.md](../docs/MISSION_BRIEF_036.md) — The Planner
- [MISSION_BRIEF_037.md](../docs/MISSION_BRIEF_037.md) — Planner Integration
- [MISSION_BRIEF_038.md](../docs/MISSION_BRIEF_038.md) — Timeout Architecture
- [MISSION_BRIEF_038A.md](../docs/MISSION_BRIEF_038A.md) — Timeout Stage A
- [MISSION_BRIEF_038_DELIVERED.md](../docs/MISSION_BRIEF_038_DELIVERED.md) — Timeout Delivered
- [MISSION_BRIEF_038_B.md](../docs/MISSION_BRIEF_038_B.md) — Timeout Stage B
- [MISSION_BRIEF_039.md](../docs/MISSION_BRIEF_039.md) — Capability Contracts

### ADRs
- [ADR-0003](../docs/adr/0003) — Plugin contract
- [ADR-0004](../docs/adr/0004) — Local-first stance
- [ADR-0005](../docs/adr/0005) — Executor permission relay
- [ADR-0006](../docs/adr/0006) — Composite action relay
- [ADR-0007](../docs/adr/0007) — Memory backend (SQLite)
- [ADR-0008](../docs/adr/0008) — Memory scale review
- [ADR-0009](../docs/adr/0009) — PermissionCategory + IRREVERSIBLE rule
- [ADR-0010](../docs/adr/0010) — Shared Infrastructure layer
- [ADR-0011](../docs/adr/0011) — Verification independent subsystem
- [ADR-0012](../docs/adr/0012) — Knowledge Lifecycle
- [ADR-0013](../docs/adr/0013) — Multi-Operator architecture
- [ADR-0014](../docs/adr/0014) — Executive/Worker terminology
- [ADR-0015](../docs/adr/0015) — Persistence strategy (Proposed)
- [ADR-0016](../docs/adr/0016) — Dashboard read model
- [ADR-0017](../docs/adr/0017) — AI Capability Broker (ratified)
- [ADR-0018](../docs/adr/0018) — Broker learning loop
- [ADR-0019](../docs/adr/0019) — Runtime approval boundary
- [ADR-0020](../docs/adr/0020) — Founder approval workflow (Proposed)

---

## ADR References by Domain

| Domain | ADRs |
|--------|------|
| Plugin System | ADR-0003, ADR-0004 |
| Permission System | ADR-0005, ADR-0006, ADR-0009, ADR-0019, ADR-0020 |
| Memory | ADR-0007, ADR-0008, ADR-0012 |
| Shared Infrastructure | ADR-0010 |
| Verification | ADR-0011 |
| Multi-Operator | ADR-0013 |
| Terminology | ADR-0014 |
| Persistence | ADR-0015 (Proposed) |
| AI Capability Broker | ADR-0017, ADR-0018 |
| Runtime Approval | ADR-0019 |
| Founder Approval | ADR-0020 (Proposed) |
| Dashboard | ADR-0016 |

---

*This Knowledge Base is maintained by the Kalpavriksha Architecture Team. All documents are verified against source code and frozen Constitution. No redesigns, no unimplemented features documented as implemented, no gaps concealed.*