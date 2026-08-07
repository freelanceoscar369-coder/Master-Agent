# Domain Index

## Overview

This index groups all Knowledge Base documents into logical domains based on the Kalpavriksha Architecture's layered structure. Each document appears exactly once.

---

## Domain 1: Executive Layer

### Executive Brain
- [Executive Brain](architecture/01_executive_brain.md) — Cognitive layer: Intent Layer, Planner, Model Router, Reporter

### Constitutional Foundation
- [Constitution Summary](architecture/02_constitution.md) — Frozen Constitution v2 Revision 3 summary
- [Terminology Freeze](architecture/14_terminology_freeze.md) — Frozen terminology definitions
- [Immutable Architecture Rules](architecture/02_constitution.md#immutable-architecture-rules) — 15 frozen rules

---

## Domain 2: Shared Infrastructure Layer

### Core Infrastructure
- [Shared Infrastructure](architecture/04_shared_infrastructure.md) — Capability Registry, Permission System, Mission State, Memory, Configuration, Telemetry, AI Capability Broker
- [Separation Model](architecture/04_separation_model.md) — Brain / Shared Infrastructure / Operator three-layer separation

### Memory System
- [Memory System](architecture/05_memory_system.md) — Six-layer memory (L1 Conversation → L6 Cloud Sync)
- [Knowledge Memory (Layer 4)](architecture/21_knowledge_memory.md) — Persistent Founder Memory & Knowledge Repository
- [Knowledge Philosophy](architecture/06_knowledge_philosophy.md) — Evidence Hierarchy, Knowledge Lifecycle

### Persistence & Recovery
- [Persistence Architecture](architecture/08_persistence_architecture.md) — Event log + snapshot recovery
- [Recovery Philosophy](architecture/08_recovery_philosophy.md) — Mission/System recovery, named gaps

### Configuration
- [Environment Independence](architecture/10_environment_independence.md) — No hardcoded assumptions
- [Product Agnosticism](architecture/11_product_agnosticism.md) — Core knows no product

---

## Domain 3: Execution Layer

### Orchestration
- [Orchestrator](architecture/17_orchestrator.md) — Capability resolution, permission gating, plugin invocation
- [Mission Control](architecture/07_mission_control.md) — Event Bus, Registries, Dispatcher, Queues, Founder State, Audit Stream

### Runtime Engine
- [Runtime Engine](architecture/06_runtime_engine.md) — 8-state heartbeat loop, ExecutiveGateway, ApprovalGate, checkpointing

### Action Contract
- [Action Contract](architecture/15_action_contract.md) — Foundation for all local capabilities

---

## Domain 4: Capability Layer

### Filesystem
- [Filesystem Capabilities](architecture/16_filesystem_capabilities.md) — 14 capabilities via Action Contract

### Browser
- [Browser Worker](architecture/18_browser_worker.md) — 9 capabilities, Environment Session Manager, generic Verification

### Plugin System
- [Plugin System](architecture/13_plugin_system.md) — Plugin contract, registration, ModelProvider specialization

### Capability Contracts
- [Capability Contract](architecture/22_capability_contract.md) — Two-tier index + full contracts

---

## Domain 5: AI Layer

### AI Capability Broker
- [AI Capability Broker](architecture/09_ai_capability_broker.md) — Kernel service: Provider Registry, Decision Engine, Cost Model, Benchmark Store, Approval Policy

### Model Router
- [Model Router](architecture/14_model_router.md) — Brain's single door to reasoning, asks Broker

### AI Capability Service
- [AI Capability Service](architecture/19_ai_capability_service.md) — Wiring layer: Broker + ProviderSource + Ledger + Approvals

### Providers
- [Ollama Provider](knowledge/components/14_ai_capability_broker.md) — Implementation pending

---

## Domain 6: Knowledge Layer

### Knowledge Memory
- [Knowledge Memory](architecture/21_knowledge_memory.md) — Layer 4: Persistent Founder Memory & Knowledge Repository

### Knowledge Philosophy
- [Knowledge Philosophy](architecture/06_knowledge_philosophy.md) — Evidence Hierarchy, Knowledge Lifecycle, Promotion Review

---

## Domain 7: Verification & Security

### Verification System
- [Verification System](architecture/11_verification_system.md) — Structurally independent Verification Subsystem
- [Text Verifier](architecture/20_text_verifier.md) — Generated text verification

### Security & Permissions
- [Permission & Security](architecture/12_permission_security.md) — Risk tiers, categories, approval boundaries, relay pattern
- [Human Oversight](architecture/12_human_oversight.md) — One approval per mission, transparency

### Environment Execution
- [Environment Execution](architecture/10_environment_execution.md) — Worker Contract, Environment Session, Thread affinity

---

## Domain 8: Governance

### Constitution & Governance
- [Constitution Summary](architecture/02_constitution.md) — Frozen Constitution v2 Revision 3
- [Founder Constitution Freeze](../docs/architecture/FOUNDER_CONSTITUTION_FREEZE.md) — Freeze declaration, amendments
- [Terminology Freeze](architecture/14_terminology_freeze.md) — Frozen terminology
- [Immutable Architecture Rules](architecture/02_constitution.md#immutable-architecture-rules) — 15 frozen rules

### Product Principles
- [Product Agnosticism](architecture/11_product_agnosticism.md) — Core knows no product
- [Environment Philosophy](architecture/05_environment_philosophy.md) — Local-first, abstract Environment

---

## Domain 9: Audit Documents

### Phase 1: Architecture Integrity Audit
- [Constitution Compliance Matrix](CONSTITUTION_COMPLIANCE_MATRIX.md) — 14 rules audited
- [Architecture Boundary Audit](ARCHITECTURE_BOUNDARY_AUDIT.md) — 7 layers, 20 findings
- [Architecture Gap Register](ARCHITECTURE_GAP_REGISTER.md) — 22 unique gaps
- [Architecture Maturity Report](ARCHITECTURE_MATURITY_REPORT.md) — 14 areas scored 0-4
- [Architecture Risk Register](ARCHITECTURE_RISK_REGISTER.md) — 25 risks ranked

### Phase 2.1: AI Capability Stack Audit
- [Broker Implementation Audit](knowledge/audit/BROKER_IMPLEMENTATION_AUDIT.md) — 10 components
- [Broker Bootstrap Analysis](knowledge/audit/BROKER_BOOTSTRAP_ANALYSIS.md) — Chicken-and-egg analysis
- [Broker Dependency Graph](knowledge/audit/BROKER_DEPENDENCY_GRAPH.md) — 4 dependency chains
- [Broker Maturity Score](knowledge/audit/BROKER_MATURITY_SCORE.md) — 11 components scored

---

## Domain 10: Component References

### Component Cards
- [Planner](knowledge/components/01_planner.md)
- [Model Router](knowledge/components/02_model_router.md)
- [Orchestrator](knowledge/components/03_orchestrator.md)
- [Mission Control](knowledge/components/04_mission_control.md)
- [Runtime Engine](knowledge/components/05_runtime_engine.md)
- [Local Executor](knowledge/components/06_local_executor.md)
- [Filesystem Plugin](knowledge/components/07_filesystem_plugin.md)
- [Browser Plugin](knowledge/components/08_browser_plugin.md)
- [Desktop Executive](knowledge/components/09_desktop_executive.md)
- [Memory System](knowledge/components/10_memory_system.md)
- [Verification Subsystem](knowledge/components/11_verification_subsystem.md)
- [Persistence](knowledge/components/12_persistence.md)
- [Permission System](knowledge/components/13_permission_system.md)
- [AI Capability Broker](knowledge/components/14_ai_capability_broker.md)

### Mission Briefs
- [Mission Brief Index](knowledge/briefs/00_index.md)
- [001 First E2E Mission](knowledge/briefs/001_first_e2e_mission.md)
- [002 Generic Local Executor](knowledge/briefs/002_generic_local_executor.md)
- [003 Workspace Bootstrap Action](knowledge/briefs/003_workspace_bootstrap_action.md)
- [003.1 First Real Mission](knowledge/briefs/003_1_first_real_mission.md)
- [004 Memory System](knowledge/briefs/004_memory_system.md)

---

## Domain 11: ADR Reference

### ADR Index
- [ADR Index](knowledge/adr/00_index.md)

### Core ADRs
- [ADR-0001](knowledge/adr/0001_core_language_python.md) — Core language: Python
- [ADR-0002](knowledge/adr/0002_hermes_local_llm.md) — Hermes local LLM
- [ADR-0003](knowledge/adr/0003_plugin_first_boundary.md) — Plugin-first boundary
- [ADR-0004](knowledge/adr/0004_local_first_memory.md) — Local-first memory
- [ADR-0005](knowledge/adr/0005_executor_permission_relay.md) — Executor permission relay
- [ADR-0006](knowledge/adr/0006_composite_action_relay.md) — Composite action relay
- [ADR-0007](knowledge/adr/0007_sqlite_memory_backend.md) — SQLite memory backend
- [ADR-0008](knowledge/adr/0008_memory_scale_review.md) — Memory scale review
- [ADR-0009](knowledge/adr/0009_permission_category_irreversible_grant.md) — PermissionCategory + IRREVERSIBLE grant rule
- [ADR-0010](knowledge/adr/0010_shared_infrastructure_layer.md) — Shared Infrastructure layer

### Advanced ADRs
- [ADR-0011](knowledge/adr/0011_verification_independent_subsystem.md) — Verification independent subsystem
- [ADR-0012](knowledge/adr/0012_knowledge_lifecycle.md) — Knowledge Lifecycle
- [ADR-0013](knowledge/adr/0013_multi_operator_architecture.md) — Multi-Operator architecture
- [ADR-0014](knowledge/adr/0014_executive_worker_terminology.md) — Executive/Worker terminology
- [ADR-0015](knowledge/adr/0015_persistence_strategy.md) — Persistence strategy (Proposed)
- [ADR-0016](knowledge/adr/0016_dashboard_data_contract.md) — Dashboard data contract
- [ADR-0017](knowledge/adr/0017_ai_capability_broker.md) — AI Capability Broker (ratified)
- [ADR-0018](knowledge/adr/0018_broker_learning_loop.md) — Broker learning loop
- [ADR-0019](knowledge/adr/0019_runtime_approval_boundary.md) — Runtime approval boundary
- [ADR-0020](knowledge/adr/0020_founder_approval_workflow.md) — Founder approval workflow (Proposed)

---

*Each document appears exactly once in this index. Use the Master Index (README.md) for reading order and high-level navigation.*