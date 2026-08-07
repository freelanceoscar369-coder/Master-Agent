# Component: Permission System

## Purpose
Single, consistent grant ledger across all Operator Instances. Adjudicates every grant; veto power over Orchestrator. RiskTier: READ_ONLY | REVERSIBLE_WRITE | IRREVERSIBLE. Grants: ONCE | THIS_SESSION | ALWAYS_FOR_CAPABILITY (never satisfies IRREVERSIBLE).

## Scope
src/master_agent/permissions/

## Dependencies
- KALPAVRIKSHA_VISION_V2.md §5.2
- ADR-0005, ADR-0009
- LocalExecutor (executor/)
- Orchestrator (orchestrator/)

## Last Updated
2026-07-31

## References
- KALPAVRIKSHA_VISION_V2.md §5.2
- ADR-0005, ADR-0009
- MISSION_BRIEF_005.md, 028_0.md, 028_1.md

## Status
Template