# Component: Desktop Executive

## Purpose
Discovers installed software, versions, running processes; launches, opens, closes applications. Twelve capabilities, zero architecture change.

## Scope
src/master_agent/desktop/

## Dependencies
- Mission Control (mission_control/) — registers via manifest-reading adapter
- LocalExecutor (executor/) for IRREVERSIBLE actions (CloseApplication, ExecuteCommand)
- MISSION_BRIEF_030.md

## Last Updated
2026-07-31

## References
- MISSION_BRIEF_030.md

## Status
Template