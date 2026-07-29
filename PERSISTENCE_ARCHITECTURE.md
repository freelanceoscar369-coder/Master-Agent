# Persistence Architecture — Operational Memory

Status: Added 2026-07-26 — Mission Brief 025, Persistent Runtime State Engine

Design document required before any code, per Constitution Rule 1. Siblings:
`MISSION_CONTROL_ARCHITECTURE.md` (what is persisted) and
`RUNTIME_ENGINE_ARCHITECTURE.md` (what requests checkpoints).

MB025 implements a **frozen architecture**. This document therefore leads
with the one place where the frozen design and this Mission Brief's own
rules could not both be satisfied unchanged, because that is the decision
most worth a founder's attention.

## 1. The one architectural conflict, and the proposed resolution

**Deliverable 3** requires objectives to be persisted and restored.
**Rule 4** forbids any component from reaching into another's private
state. Surveying the frozen Mission Control:

| Component | Restore path available? |
|---|---|
| `ExecutiveRegistry.register()` | ✅ public, publishes nothing |
| `CapabilityRegistry.register()` | ✅ public, publishes nothing |
| `AuditStream.record()` | ✅ public, append-only, copies `event_id`/`occurred_at` off the Event — a faithful rebuild needs **zero** changes |
| `TaskDispatcher` objectives | ❌ **none** — `submit()` is the only entry point and it publishes `OBJECTIVE_SUBMITTED` + `TASK_CREATED` |

Restoring an objective through `submit()` would republish creation events
for work that was submitted hours ago, so a restored audit would claim
each objective was submitted twice. The alternative — writing to
`TaskDispatcher._objectives` — is precisely what Rule 4 forbids.

**Proposed resolution (ADR-0015):** one additive, public, non-publishing
method, `TaskDispatcher.restore_objective(objective)`. It is not a
redesign: no existing method changes, no behaviour changes, nothing is
removed, and the dispatcher's own guarantees (validation, readiness,
never auto-retrying) are untouched. It exists because Rule 4 requires a
*contract* for something the frozen surface has no contract for.

Per this Mission Brief's opening constraint, this is documented and
proposed rather than treated as settled. It is deliberately the smallest
possible change, and it is isolated: reverting it means deleting one
method and one call site.

## 2. What persistence is, and is not

**Rule 1: persistence is a service. It never executes missions.** The
package holds no gateway, no Executive reference, no dispatch surface. It
subscribes, it serialises, it restores. `tests/test_persistence_architecture.py`
enforces this the same way MB023 and MB024 enforce their boundaries.

Three purity constraints, mechanically checked:

- **Mission Control cannot access filesystem APIs.** It has none today,
  and MB025 adds `json`, `pathlib`, `sqlite3`, `os`, and `io` to Mission
  Control's forbidden-import test so it stays that way.
- **The Runtime cannot write persistence directly.** It calls a
  `CheckpointSink` protocol **defined inside `runtime/`** (§5), so
  `runtime/` still imports nothing but `mission_control` and itself — the
  MB024 architecture test passes unchanged.
- **Persistence cannot dispatch Executives.** No import of `runtime`,
  no gateway, no plugin.

## 3. Two mechanisms, deliberately: snapshots and an event log

| | Snapshot | Event log |
|---|---|---|
| Answers | "what is the state right now" | "what has ever happened" |
| Written | on checkpoint (cycle end, shutdown) | on every event, as it happens |
| Used for | fast restart (Deliverables 2-5, 7) | audit history (6), replay (9) |
| Shape | one versioned envelope | append-only JSONL |

Snapshot-based restore is the **primary** path: it is O(state), not
O(history), so restart time does not grow with how long the system has
been running. Event replay (Deliverable 9) is a genuine, tested
capability — `replay_events_into()` rebuilds Mission Control from the log
alone — used for audit reconstruction and as a repair path when a
snapshot is missing or corrupt, not as the everyday mechanism.

**Why the audit is rebuilt from the log rather than the snapshot:** the
log preserves each event's original `event_id`, `occurred_at`, and
payload, so `AuditStream.record()` reconstructs entries *identically*.
Snapshotting the audit separately would duplicate the same data in two
formats that could drift.

## 4. Storage format

JSON on the local filesystem: one `snapshot.json` (versioned envelope)
and one `events.jsonl` (append-only, one event per line).

**Why not SQLite, given ADR-0007 chose it for Memory?** Because they are
different concerns and conflating them would be the mistake. Memory
(`SQLiteMemoryStore`) stores *mission history* — a queryable, indexed,
long-lived record that a future Planner reads for "have I done this
before". Persistence stores *operational state* — a small, whole-object
snapshot read exactly once at startup and never queried into. A row store
buys indexing and partial reads that this workload never uses, and costs a
schema migration every time a dataclass gains a field. JSON is
human-inspectable, which matters a great deal when the thing you are
debugging is "why did it not come back up".

Both remain available; nothing about Memory changes.

**Writes are atomic**: serialise to a temporary file in the same
directory, `os.replace()` onto the target. A crash mid-write leaves the
previous good snapshot intact rather than a truncated one — the failure
mode that would make a persistence layer worse than none.

## 5. The Runtime seam

`runtime/checkpoint.py` defines `RuntimeCheckpoint` (the state) and
`CheckpointSink` (a Protocol: `save_checkpoint`, `load_checkpoint`).
`RuntimeEngine` takes an optional sink and calls it at cycle end and at
shutdown.

The protocol lives **in `runtime/`, not in `persistence/`**, on purpose:
if the Runtime imported the persistence package, MB024's architecture
test — which asserts `runtime/` imports only `mission_control` and itself
— would fail, and the Runtime would have acquired a storage dependency
Rule 3 forbids. Dependency inversion: the Runtime declares what it needs;
persistence satisfies it. The Runtime never learns a file exists.

## 6. Restart recovery, and the in-flight task problem

On startup `recover()` detects existing state, restores Mission Control
(executives → capabilities → objectives → audit) and the Runtime's
counters, and hands back a system ready to resume.

**The hard case: a task that was `RUNNING` or `DISPATCHED` when the
process died.** Its side effects are *unknown* — it may have completed a
browser navigation, written a file, or done nothing. Two options:

- Re-run it. Risks **duplicate execution**, which this Mission Brief
  explicitly forbids.
- Quarantine it. Guarantees no duplicate execution, at the cost of
  needing attention.

**Chosen: quarantine.** Interrupted tasks are restored as `FAILED` with
the error *"interrupted by shutdown; outcome unknown — not retried
automatically to avoid duplicate execution"*. They surface in Founder
State's `errors`, and their dependents become `BLOCKED` — visible, not
silently dropped.

This is deliberately conservative and it is the honest reading of "resume
execution safely. No duplicate task execution." Tasks that were `READY`,
`CREATED`, or `BLOCKED` had not started and resume normally, which is
what satisfies "resume unfinished work". Deciding to re-run a quarantined
task is a *strategic* judgement — exactly what Constitution §11 reserves
for the Brain, and what the Runtime's mechanical retry deliberately
excludes.

## 7. Snapshot versioning (Deliverable 10)

Every snapshot carries `schema_version`, `runtime_version`, `created_at`,
and `checksum` (SHA-256 over the canonically-serialised payload).

- A **checksum mismatch** raises `CorruptSnapshot`. Recovery falls back to
  the event log rather than loading state that has been altered or
  truncated.
- An **unknown future schema version** raises `UnsupportedSchemaVersion`
  rather than guessing. Refusing to read a newer format is safer than
  misinterpreting it.
- An **older known version** is routed through a migration registry —
  empty today (there is only v1), but the seam exists so v2 is a migration
  function rather than a rewrite. `MIGRATIONS` maps `from_version →
  callable`; adding one costs one entry.

## 8. The Scalability Question (Rule 1)

- **Snapshot cost is O(live state)** — objectives, registries, counters —
  not O(history), so restart time is flat as the system ages.
- **The event log grows without bound**, and that is the honest limit
  here: it is written per event and read in full only when rebuilding
  audit. At a million events, reading it becomes slow and it should be
  segmented or compacted (a snapshot plus the events after it). **Not
  built now**, because compaction is only correct once there is a real
  retention policy, and inventing one ahead of a demonstrated need is
  exactly the premature infrastructure this project avoids. Named in
  `docs/MISSION_BRIEF_025.md`'s debt section, not hidden.
- **Deliberately not built:** no remote/cloud store (ADR-0004's
  local-first stance is unchanged), no encryption, no multi-process
  locking (single-founder, single-process today — a second process
  writing the same directory would corrupt state, and that is stated
  rather than defended against), no partial/incremental snapshots.
