# ADR-0004: Local-first memory, no cloud sync in Founder Edition

Status: Accepted (2026-07-23)

## Context
"Local memory" is a mandatory Founder Edition feature, and "local-first
architecture, cloud enhancement when beneficial" is a core principle.

## Decision
Mission history, learned preferences, and the plugin capability index live
in a local SQLite database under the user's app data directory, plus a
local embedding index for semantic recall (embeddings generated locally,
not via a cloud API, so memory search works fully offline). No cloud sync
or multi-device memory replication is in scope for Founder Edition.

## Consequences
- Memory doesn't follow the founder across machines yet — acceptable for
  "build for one founder first."
- When multi-device / cloud sync becomes a requirement, this should arrive
  as an optional plugin (a sync provider) rather than a rewrite of the
  Memory module's interface — the interface should already be storage-
  backend-agnostic (see `memory/store.py` stub).
