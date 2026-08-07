# Component: Orchestrator

## Purpose
Walks the MissionPlan, resolves Capability → Worker via Capability Registry, checks Permission System, invokes Worker, captures result, triggers Verification, applies retry/failure-branching policy.

## Scope
src/master_agent/orchestrator/

## Dependencies
- KALPAVRIKSHA_VISION_V2.md §4.1
- Mission Control (mission_control/)
- Capability Registry (plugins/registry.py)
- Permission System (permissions/)
- Verification Subsystem (verification/)

## Last Updated
2026-07-31

## References
- KALPAVRIKSHA_VISION_V2.md §4.1
- MISSION_BRIEF_023.md
- MISSION_BRIEF_024.md

## Status
Template