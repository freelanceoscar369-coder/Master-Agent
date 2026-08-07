# Persistence Architecture

## Purpose
Documents the operational memory system that makes Mission Control and Runtime state survive process exit and resume exactly where stopped. Per `PERSISTENCE_ARCHITECTURE.md` (Mission Brief 025) and Constitution §11, Rule 1, Rule 4.

---

## Frozen Constitution

### Constitution §11 (Recovery Philosophy — EVOLVABLE)
> **Mission-Level Recovery:** The `Mission` state machine (Shared Infrastructure, §5.3) enables precise recovery. A failed Verdict (§10.2) triggers recovery — Evidence flows to the Brain; Brain decides retry, re-plan, or surface to human.
> **System-Level Recovery:** Memory (Shared Infrastructure, §5.4) is the durable anchor and survives restart. Persistence is automatic.
> **No Silent Corruption:** Zero tolerance for silent data loss, drift, or gaps.

### Constitution Rule 1 (FROZEN)
> **Design Before Code, Answering the Scalability Question.** Every design document must explicitly answer: "would this still be right at a million Missions, thousands of Workers, hundreds of Capabilities, years of history, many Operator Instances?"

### Constitution Rule 4 (FROZEN)
> **Environment Access Has One Door.** No Brain module, no CLI code, touches an Environment directly. Everything goes through a Worker, via the Operator's Worker Runtime, via an Environment Session the Operator Instance owns.

### Constitution Rule 3 (FROZEN)
> **Capability Contract Is Sacred.** Adding capability #N costs one new file, never an edit to the Registry, Orchestrator, Permission System, or Worker Runtime.

---

## Architecture Design (from `PERSISTENCE_ARCHITECTURE.md`)

### 1. The Core Conflict and Proposed Resolution (ADR-0015)
**Problem:** Deliverable 3 requires objectives persisted/restored. Rule 4 forbids reaching into private state.
- `ExecutiveRegistry.register()` ✅ public
- `CapabilityRegistry.register()` ✅ public
- `AuditStream.record()` ✅ public, append-only
- `TaskDispatcher` objectives ❌ **none** — `submit()` only entry point, publishes events

**Proposed Resolution (ADR-0015):** One additive, public, non-publishing method `TaskDispatcher.restore_objective(objective)`. Not a redesign — no existing method changes, no behaviour changes, dispatcher guarantees untouched. Isolated: reverting = delete one method + one call site.

**Status:** **PROPOSED** — documented, not settled. Awaiting founder ratification (`FOUNDER_CONSTITUTION_FREEZE.md` §4a).

### 2. What Persistence Is (and Is Not)
**Rule 1:** Persistence is a service. It **never executes missions**.
- Holds no gateway, no Executive reference, no dispatch surface
- Subscribes, serialises, restores
- Purity enforced by `tests/test_persistence_architecture.py`

**Three Purity Constraints (Mechanically Checked):**
1. **Mission Control cannot access filesystem APIs** — forbidden-import test includes `json`, `pathlib`, `sqlite3`, `os`, `io`
2. **Runtime cannot write persistence directly** — calls `CheckpointSink` protocol defined inside `runtime/`
3. **Persistence cannot dispatch Executives** — no `runtime` import, no gateway, no plugin

### 3. Two Mechanisms: Snapshots + Event Log

| Aspect | Snapshot | Event Log |
|--------|----------|-----------|
| **Answers** | "what is the state right now" | "what has ever happened" |
| **Written** | On checkpoint (cycle end, shutdown) | On every event, as it happens |
| **Used for** | Fast restart (O(state)) | Audit history, replay |
| **Shape** | One versioned envelope | Append-only JSONL |

**Snapshot-based restore = primary path** — O(state), not O(history). Restart time flat as system ages.

**Event replay (Deliverable 9)** — `replay_events_into()` rebuilds Mission Control from log alone. Used for audit reconstruction and repair when snapshot missing/corrupt.

**Why audit rebuilt from log not snapshot:** Log preserves original `event_id`, `occurred_at`, payload → `AuditStream.record()` reconstructs identically. Snapshotting audit separately would duplicate data in two formats that could drift.

### 4. Storage Format
**JSON on local filesystem:**
- `snapshot.json` — versioned envelope
- `events.jsonl` — append-only, one event per line

**Why not SQLite (ADR-0007 chose it for Memory):**
- Memory = mission history (queryable, indexed, long-lived, Planner reads)
- Persistence = operational state (small whole-object snapshot, read once at startup, never queried into)
- Row store buys indexing/persistence never uses; costs schema migration per dataclass field
- JSON human-inspectable — critical for debugging "why did it not come back up"

**Writes are atomic:** Serialise to temp file in same directory, `os.replace()` onto target. Crash mid-write leaves previous good snapshot intact.

### 5. Runtime Seam: `CheckpointSink` Protocol
**Defined in `runtime/checkpoint.py` (not `persistence/`) — on purpose:**
- If Runtime imported persistence, MB024 architecture test fails (asserts `runtime/` imports only `mission_control` and itself)
- Runtime would acquire storage dependency Rule 3 forbids
- **Dependency inversion:** Runtime declares what it needs; persistence satisfies it. Runtime never learns a file exists.

```python
class CheckpointSink(Protocol):
    def save_checkpoint(self, snapshot: RuntimeCheckpoint) -> None: ...
    def load_checkpoint(self) -> RuntimeCheckpoint | None: ...
```

`RuntimeCheckpoint` captures: state, cycle, tasks_completed, tasks_failed, retries_performed, escalations, last_dispatch_at, last_verification_at.

### 6. Restart Recovery: The In-Flight Task Problem
**On startup `recover()`:**
1. Detects existing state
2. Restores Mission Control (executives → capabilities → objectives → audit)
3. Restores Runtime counters
4. Hands back system ready to resume

**Hard case: task `RUNNING` or `DISPATCHED` when process died**
- Side effects UNKNOWN — may have completed navigation, written file, or done nothing
- **Option 1: Re-run** → risks duplicate execution (explicitly forbidden)
- **Option 2: Quarantine** → guarantees no duplicate execution

**Chosen: Quarantine**
- Interrupted tasks restored as `FAILED` with error: *"interrupted by shutdown; outcome unknown — not retried automatically to avoid duplicate execution"*
- Surface in Founder State's `errors`
- Dependents become `BLOCKED` — visible, not silently dropped
- Tasks `READY`/`CREATED`/`BLOCKED` resume normally (had not started)
- Deciding to re-run quarantined task = **strategic judgement** → Brain's (Constitution §11), not Runtime's mechanical retry

### 7. Snapshot Versioning (Deliverable 10)
Every snapshot carries:
- `schema_version`
- `runtime_version`
- `created_at`
- `checksum` (SHA-256 over canonically-serialised payload)

**Failure modes:**
- **Checksum mismatch** → `CorruptSnapshot` → fallback to event log
- **Unknown future schema version** → `UnsupportedSchemaVersion` → refuse rather than guess
- **Older known version** → migration registry (`MIGRATIONS` maps `from_version → callable`; empty today, v1 only)

### 8. Scalability Question (Rule 1)
- **Snapshot cost O(live state)** — objectives, registries, counters — not O(history)
- **Event log grows without bound** — honest limit: at million events, reading slow; should segment/compact (snapshot + events after). **Not built now** — compaction needs real retention policy; inventing one ahead of need = premature infrastructure
- **Deliberately not built:** no remote/cloud store (ADR-0004 local-first), no encryption, no multi-process locking (single-founder, single-process), no partial/incremental snapshots

---

## Current Implementation Status

| Component | Architecture Status | Implementation Status | Notes |
|-----------|---------------------|----------------------|-------|
| **Event Log (`events.jsonl`)** | FROZEN (MB025) | ✅ **IMPLEMENTED** | Append-only, one event per line |
| **Snapshot (`snapshot.json`)** | FROZEN (MB025) | ✅ **IMPLEMENTED** | Versioned envelope + SHA-256 checksum |
| **Atomic Writes** | FROZEN (MB025) | ✅ **IMPLEMENTED** | Temp file + `os.replace()` |
| **Recovery (`recover()`)** | FROZEN (MB025) | ✅ **IMPLEMENTED** | Single call launcher makes |
| **Quarantine Interrupted Tasks** | FROZEN (MB025) | ✅ **IMPLEMENTED** | Restored as `FAILED`, dependents `BLOCKED` |
| **Event Replay (`replay_events_into()`)** | FROZEN (MB025) | ✅ **IMPLEMENTED** | Rebuilds MC from log alone |
| **Snapshot Versioning** | FROZEN (MB025) | ✅ **IMPLEMENTED** | `schema_version`, `runtime_version`, `created_at`, `checksum` |
| **Migration Registry** | FROZEN (MB025) | ✅ **IMPLEMENTED** | `MIGRATIONS` map; empty (v1 only) |
| **CheckpointSink Protocol** | FROZEN (MB025) | ✅ **IMPLEMENTED** | In `runtime/checkpoint.py` |
| **Runtime Checkpointing** | FROZEN (MB025) | ✅ **IMPLEMENTED** | Cycle end + shutdown |
| **Purity Tests** | FROZEN (MB025) | ✅ **IMPLEMENTED** | `test_persistence_architecture.py` |
| **ADR-0015 `restore_objective()`** | PROPOSED | ⏳ **PROPOSED** | Awaiting founder ratification |
| **Event Log Compaction** | EVOLVABLE (debt) | ⏳ **RESERVED** | Named in MB025 debt section |
| **Remote/Cloud Store** | NOT BUILT | ❌ **NOT IMPLEMENTED** | ADR-0004 local-first unchanged |
| **Encryption** | NOT BUILT | ❌ **NOT IMPLEMENTED** | Deliberately not built |
| **Multi-Process Locking** | NOT BUILT | ❌ **NOT IMPLEMENTED** | Single-process stated |

---

## Design vs Implementation Differences

| Area | Design (Architecture) | Implementation | Status |
|------|----------------------|----------------|--------|
| **Two mechanisms** | Snapshots + event log (deliberate) | ✅ Both implemented | ✅ MATCH |
| **Primary restore path** | Snapshot-based (O(state)) | ✅ Snapshot primary | ✅ MATCH |
| **Event replay** | Genuine capability (Deliverable 9) | ✅ `replay_events_into()` tested | ✅ MATCH |
| **Audit from log not snapshot** | Preserves original event_id/occurred_at | ✅ `AuditStream.record()` reconstructs identically | ✅ MATCH |
| **JSON not SQLite** | Different concerns (operational vs mission history) | ✅ JSON on filesystem | ✅ MATCH |
| **Atomic writes** | Temp file + `os.replace()` | ✅ Implemented | ✅ MATCH |
| **CheckpointSink in `runtime/`** | Dependency inversion (no storage dep) | ✅ Protocol in `runtime/checkpoint.py` | ✅ MATCH |
| **Quarantine not re-run** | Conservative, honest reading | ✅ `FAILED` + "interrupted by shutdown" error | ✅ MATCH |
| **Snapshot versioning** | schema_version, checksum, migration registry | ✅ All implemented | ✅ MATCH |
| **ADR-0015 `restore_objective()`** | Proposed additive method | ⏳ Proposed, awaiting ratification | ⚠️ PROPOSED |
| **Event log unbounded growth** | Named honest limit | 📝 Documented debt, not built | 📝 DOCUMENTED |
| **No remote store/encryption** | Deliberately not built | ✅ Not implemented | ✅ MATCH |

---

## Open Questions

1. **ADR-0015 Ratification** — `TaskDispatcher.restore_objective()` proposed as additive change to frozen components. Awaiting founder ratification (`FOUNDER_CONSTITUTION_FREEZE.md` §4a). Smallest possible change; reverting = delete one method + one call site.

2. **Event Log Compaction** — At million events, reading becomes slow. Should segment/compact (snapshot + events after). Not built because compaction needs real retention policy; inventing one ahead of need = premature infrastructure. Named in MB025 debt section.

3. **Quarantine Decision Authority** — Constitution §11 reserves strategic re-run for Brain. Current: quarantined tasks surface in Founder State, human decides. No automated re-run.

4. **Multi-Process Locking** — Single-founder, single-process today. Second process writing same directory would corrupt state. Stated rather than defended against.

5. **Snapshot Version Migration** — Migration registry exists (`MIGRATIONS` map) but empty (v1 only). Future v2 = migration function, not rewrite.

6. **Checkpoint Frequency** — Cycle end + shutdown. Configurable via `RuntimeConfig`. No partial/incremental snapshots.

---

## Future Extraction Targets

1. `src/master_agent/persistence/recovery.py` — `recover()` implementation
2. `src/master_agent/persistence/snapshot.py` — Snapshot serialisation, versioning, checksum
3. `src/master_agent/persistence/event_log.py` — `events.jsonl` append-only, replay
4. `src/master_agent/persistence/migration.py` — `MIGRATIONS` registry
5. `src/master_agent/runtime/checkpoint.py` — `RuntimeCheckpoint`, `CheckpointSink` protocol
6. `tests/test_persistence_architecture.py` — Purity enforcement (forbidden imports, no dispatch)
7. `docs/adr/0015` — Persistence strategy decision record (Proposed)
8. `docs/MISSION_BRIEF_025.md` — Full Mission Brief with Technical Debt section

---

## Wiki Links Added

- `[[KALPAVRIKSHA_VISION_V2.md]]` — Constitution §11, Rule 1, Rule 3, Rule 4
- `[[FOUNDER_CONSTITUTION_FREEZE.md]]` — Freeze record, ADR-0015 Proposed
- `[[PERSISTENCE_ARCHITECTURE.md]]` — Primary source document
- `[[ARCHITECTURE.md]]` — Implementation map
- `[[MISSION_CONTROL_ARCHITECTURE.md]]` — What is persisted, registries
- `[[RUNTIME_ENGINE_ARCHITECTURE.md]]` — Runtime checkpoints, `CheckpointSink`
- `[[MEMORY_ARCHITECTURE.md]]` — Memory vs Persistence distinction
- `[[01_executive_brain.md]]` — Brain (strategic recovery owner)
- `[[02_constitution.md]]` — Constitution summary
- `[[03_universal_executive_operator.md]]` — Operator (Runtime, Orchestrator)
- `[[04_shared_infrastructure.md]]` — Shared Infrastructure (Mission State, Memory)
- `[[05_memory_system.md]]` — Memory (mission history, SQLite)
- `[[06_runtime_engine.md]]` — Runtime (loop, checkpointing, recovery)
- `[[07_mission_control.md]]` — Mission Control (dispatcher, audit, recovery)
- `[[system_overview.md]]` — System overview
- `[[docs/adr/0004]]` — Local-first stance
- `[[docs/adr/0007]]` — Memory backend (SQLite)
- `[[docs/adr/0010]]` — Shared Infrastructure layer
- `[[docs/adr/0015]]` — Persistence strategy (Proposed)

---

*Document created from verified source only. No persistence capabilities redesigned. Terminology preserved exactly. Frozen Constitution/Architecture/Implementation/Proposed separated. Open questions recorded without resolution.*