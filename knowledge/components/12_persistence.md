# Component: Persistence

## Purpose
Operational memory: append-only event log (events.jsonl) and versioned checksummed snapshots (snapshot.json). Enables system-level recovery.

## Scope
src/master_agent/persistence/

## Dependencies
- KALPAVRIKSHA_VISION_V2.md §11.2
- ADR-0015
- MISSION_BRIEF_025.md
- PERSISTENCE_ARCHITECTURE.md
- Mission Control (mission_control/) - never writes files
- Runtime (runtime/) - calls CheckpointSink protocol

## Last Updated
2026-07-31

## References
- MISSION_BRIEF_025.md
- PERSISTENCE_ARCHITECTURE.md
- ADR-0015

## Status
Template