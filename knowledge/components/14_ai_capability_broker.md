# Component: AI Capability Broker

## Purpose
Single intelligence-selection service: Provider Registry, Capability Matrix, Decision Engine, Cost Model, Benchmark Store, Approval Policy, AI Asset Inventory, Recommendation Engine. Decides which Provider serves a request; never executes, never touches Environment.

## Scope
src/master_agent/broker/

## Dependencies
- KALPAVRIKSHA_VISION_V2.md §5.7
- ADR-0017, ADR-0018
- MISSION_BRIEF_027.md
- AI_CAPABILITY_BROKER_ARCHITECTURE.md
- Model Router (plugins/model_router.py) — consults Broker
- AI Infrastructure Executive (ai_infrastructure/) — feeds Broker

## Last Updated
2026-07-31

## References
- KALPAVRIKSHA_VISION_V2.md §5.7
- MISSION_BRIEF_027.md
- AI_CAPABILITY_BROKER_ARCHITECTURE.md
- ADR-0017, ADR-0018

## Status
Template