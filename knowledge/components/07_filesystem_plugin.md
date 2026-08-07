# Component: Filesystem Plugin

## Purpose
Thin adapter registering filesystem Actions on LocalExecutor; forwards invoke() calls to LocalExecutor.execute().

## Scope
src/master_agent/plugins/filesystem_plugin.py
src/master_agent/executor/actions/filesystem/

## Dependencies
- LocalExecutor (executor/)
- ADR-0003, ADR-0005, ADR-0006
- Permission System (permissions/)
- MISSION_BRIEF_005.md

## Last Updated
2026-07-31

## References
- MISSION_BRIEF_005.md
- FILESYSTEM_CAPABILITIES.md
- MISSION_BRIEF_022.md (Browser Plugin pattern)

## Status
Template