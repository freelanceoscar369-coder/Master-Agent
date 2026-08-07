# Component: Local Executor

## Purpose
The only component allowed to perform local actions. Validates parameters, checks Permission System, runs Action, catches exceptions, logs execution.

## Scope
src/master_agent/executor/

## Dependencies
- KALPAVRIKSHA_VISION_V2.md §4.7 (via ARCHITECTURE.md)
- ADR-0005, ADR-0006
- Action Contract (executor/action.py)
- Permission System (permissions/)

## Last Updated
2026-07-31

## References
- MISSION_BRIEF_002.md, 003.md, 005.md
- FILESYSTEM_CAPABILITIES.md
- ADR-0005, ADR-0006

## Status
Template