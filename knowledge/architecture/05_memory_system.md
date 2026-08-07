# Memory System

## Purpose
Documents the six-layer memory architecture that serves as the durable anchor for Kalpavriksha — enabling missions to survive process restarts, feeding future planning, and providing one seam for all subsystems to depend on instead of inventing their own persistence. Per `MEMORY_ARCHITECTURE.md` and Constitution §5.4 (Shared Infrastructure).

## Constitutional Role

### Constitution §5.4 (FROZEN)
> **Memory** belongs in Shared Infrastructure because: every Operator Instance's Evidence must aggregate into one durable history, not fragment into per-Operator silos — otherwise a future Planner call asking "have I done something like this before" only ever sees what one Operator Instance happened to do. All six Memory layers live here, including the durable, queryable form of execution history.

### Constitution §9 (Mixed Status)
- **§9.1 Permanent Knowledge and Temporary Observations** — FROZEN
  - Permanent Knowledge (persisted, queryable): Mission History + User Preferences
  - Temporary Observations (in-process only): Conversation Memory + Mission Memory
- **§9.2 Evidence Hierarchy** — FROZEN (strongest to weakest):
  1. Observed Reality
  2. Evidence (structured Observation vs Expected Outcome)
  3. Mission Record (persisted, survives restart)
  4. Conversation Transcript (debugging only)
  5. Reasoning Provider Output (never treated as evidence of reality)
- **§9.3–9.5 Knowledge Lifecycle** — RESEARCH-BACKED

### Constitution Rule 7 (FROZEN)
> **Memory Persists Automatically.** Persistence happens at every terminal Mission state, with no manual save call anywhere in the calling code.

### Constitution Rule 8 (FROZEN)
> **Evidence Hierarchy Is Law.** When documentation and observed reality conflict, observed reality wins — for Mission history and now explicitly for Permanent Knowledge too.

---

## Memory Philosophy (from `MEMORY_ARCHITECTURE.md` §1–§3)

### Why Memory Exists
Every Miracle through 003.5 proved Master Agent can *act* — but none of that survived process exit. `MasterAgentSession.last_mission` was a single Python attribute that forgets the moment the interpreter does.

Memory exists to:
1. Let missions survive the process that ran them
2. Give every future subsystem one seam to depend on instead of five different ones each inventing its own persistence

### What Should Be Remembered
- **Mission outcomes** — what was asked, planned, approved, what happened, duration, artifacts created, errors
- **Mission identity and timing** — stable ID, timestamps for lookup and chronological ordering
- **User preferences** — small durable key/value facts distinct from mission history

### What Should NEVER Be Remembered
- **Raw conversation text, persisted indefinitely** — Layer 1 is in-process only, discarded on session end
- **Anything that leaves the machine** — no telemetry, analytics, network calls, cloud storage (Layer 6 is placeholder interface)
- **Secrets or credentials** — nothing currently handles these; named so future Miracle must consciously decide
- **Anything a mission's own action didn't actually produce** — records Executor-reported `ExecutionResult.output`, not reconstruction

---

## Six Layer Memory Architecture

### Layer 1: Conversation Memory
**Status:** IMPLEMENTED (`memory/conversation.py`)

| Aspect | Detail |
|--------|--------|
| **Purpose** | Current session's turns, bounded in-memory |
| **Ownership** | Shared Infrastructure (in-process only) |
| **Data Type** | `ConversationTurn(speaker, text, at)` in bounded list (`max_turns`, default 200) |
| **Lifecycle** | Created per session; old turns fall off; discarded on process exit |
| **Implementation** | `ConversationMemory` class; `MasterAgentSession.handle()` records user text and system reply automatically on every call |

**Key Properties:**
- Never touches disk
- Bounded (`max_turns=200`) — old turns fall off rather than growing unboundedly
- When process exits, this layer is gone — by design, not a gap

### Layer 2: Mission Memory
**Status:** IMPLEMENTED (pre-existing, formalized in MB004)

| Aspect | Detail |
|--------|--------|
| **Purpose** | Current execution state — the Mission currently executing |
| **Ownership** | Shared Infrastructure (but represented by pre-existing objects) |
| **Data Type** | `Mission` object (`mission_manager/mission.py`) + `MasterAgentSession.last_mission` + `StepResult`/`ExecutionResult` |
| **Lifecycle** | Exists during mission execution; converted to `MissionRecord` at terminal state |
| **Implementation** | **Deliberately not a new class** — wraps existing `Mission` object. Translation step at boundary: `MasterAgentSession._remember()` converts in-flight state to `MissionRecord` at terminal status (`COMPLETED`, `FAILED`, `CANCELLED`) |

**Key Properties:**
- No new class created — would duplicate state and risk sync issues
- Behaves exactly as in MB001–003.5 until terminal state
- Translation happens at Layer 2 → Layer 3 boundary

### Layer 3: Persistent Memory (Operational Memory)
**Status:** IMPLEMENTED (`memory/store.py` — `SQLiteMemoryStore`)

| Aspect | Detail |
|--------|--------|
| **Purpose** | Durable, queryable mission history on this machine |
| **Ownership** | Shared Infrastructure |
| **Data Type** | `MissionRecord` persisted to SQLite |
| **Lifecycle** | Written at every terminal mission state; survives process restart |
| **Implementation** | `SQLiteMemoryStore` implements `MemoryStore` ABC using stdlib `sqlite3` (no ORM — ADR-0007) |

**Schema (from `MEMORY_ARCHITECTURE.md` §5):**
```sql
CREATE TABLE missions (
    mission_id             TEXT PRIMARY KEY,
    title                   TEXT NOT NULL,
    intent_summary          TEXT NOT NULL,
    status                  TEXT NOT NULL,          -- "completed" | "failed" | "cancelled"
    approval_status         TEXT NOT NULL,          -- "not_required" | "approved" | "denied"
    created_at              TEXT NOT NULL,          -- ISO 8601 UTC
    completed_at            TEXT NOT NULL,          -- ISO 8601 UTC
    execution_plan          TEXT NOT NULL,          -- JSON: [{step_id, capability, payload}, ...]
    execution_result        TEXT,                   -- JSON: raw result output or NULL
    execution_time_seconds  REAL NOT NULL DEFAULT 0.0,
    artifacts                TEXT NOT NULL,          -- JSON: [{"type": ..., "path"/"id"/...: ...}, ...]
    errors                    TEXT NOT NULL,          -- JSON list of error strings
    outcome                   TEXT                  -- JSON: Mission.outcome mirrored
);
CREATE INDEX idx_missions_completed_at ON missions(completed_at);
CREATE INDEX idx_missions_status_completed ON missions(status, completed_at);

CREATE TABLE preferences (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL   -- JSON
);
```

**Design Decisions (§6b):**
- `artifacts` generic list (not `folders_created`/`files_created` columns) — future capabilities (git, shell, browser) contribute own shape without schema change
- JSON columns for `execution_plan`, `execution_result`, `artifacts`, `errors` — nothing queries into them today; only `status` and `completed_at` filtered/sorted
- `title` and `outcome` columns beyond brief's list — `title` for display, `outcome` for self-describing record

### Layer 4: Knowledge Memory
**Status:** RESERVED — interface only (`memory/future.py`)

| Aspect | Detail |
|--------|--------|
| **Purpose** | Durable facts distinct from mission history (founder preferences learned in conversation, ingested documents) |
| **Ownership** | Shared Infrastructure |
| **Data Type** | `KnowledgeMemory` interface (ABC) |
| **Lifecycle** | Not implemented — reserved for future Miracle |
| **Implementation** | Interface only; no wiring into `MasterAgentSession` or live code |

**Constitution §9.3–9.5 (RESEARCH-BACKED):** Knowledge Lifecycle — Execution → Evidence → Knowledge Candidate → Promotion Review → Permanent Knowledge → Future Reasoning. Promotion Review requires human confirmation for Founder Edition.

**Future Evolution (§12):** `KnowledgeMemory` in `memory/future.py` is the interface to implement against; does not require Layer 3's schema to change.

### Layer 5: Vector Memory
**Status:** FUTURE — interface only (`memory/future.py`)

| Aspect | Detail |
|--------|--------|
| **Purpose** | Semantic recall over mission history |
| **Ownership** | Shared Infrastructure |
| **Data Type** | `VectorMemory` interface (ABC) |
| **Lifecycle** | Not implemented — future Miracle |
| **Implementation** | Interface only; no wiring |

**Future Evolution (§12):** Component reads Layer 3's `missions` table via `MissionQuery.offset` (paging whole table) and indexes `title`/`intent_summary`/`execution_result` locally — additive, not a migration. Deep `OFFSET` pagination O(offset) in SQLite; fine for one-time/periodic background index build.

### Layer 6: Cloud Sync
**Status:** OPTIONAL FUTURE — interface only (`memory/future.py`)

| Aspect | Detail |
|--------|--------|
| **Purpose** | Multi-device synchronization (opt-in) |
| **Ownership** | Shared Infrastructure |
| **Data Type** | `CloudSyncMemory` interface (ABC) |
| **Lifecycle** | Not implemented — optional future |
| **Implementation** | Interface only; off by default forever unless founder decision says otherwise |

**Future Evolution (§12):** Arrives as optional plugin per ADR-0004, reading/writing through same `MemoryStore` interface — e.g., `push(since=...)`/`pull()` implementation syncing `missions` rows to remote store founder explicitly opts into.

---

## Memory Storage Architecture

### Two-Layer Interface Contract (`MEMORY_ARCHITECTURE.md` §6)

#### 1. `MemoryStore` ABC (`memory/store.py`) — Storage Contract
```python
save_mission(mission: MissionRecord) -> None
get_mission(mission_id: str) -> MissionRecord | None
query_missions(query: MissionQuery) -> list[MissionRecord]
remember_preference(key: str, value: Any) -> None
recall_preference(key: str) -> Any | None
```
- `SQLiteMemoryStore` only implementation today
- `JSONMemoryStore` or Postgres-backed store would implement same five methods
- Nothing above changes when backend changes

#### 2. `Memory` Facade (`memory/memory.py`) — Single System Seam
```python
record_turn(speaker: str, text: str) -> None
conversation_turns() -> list[ConversationTurn]
persist_mission(record: MissionRecord) -> None
mission_by_id(mission_id: str) -> MissionRecord | None
last_mission() -> MissionRecord | None
recent_missions(limit: int = 10) -> list[MissionRecord]
successful_missions() -> list[MissionRecord]
failed_missions() -> list[MissionRecord]
remember_preference(key: str, value: Any) -> None
recall_preference(key: str) -> Any | None
```
- Composes Layer 1 (`ConversationMemory`) and `MemoryStore` (Layer 3)
- `MasterAgentSession` depends on `Memory`, injected via constructor
- Never on `SQLiteMemoryStore` directly, never as singleton
- Tests construct own `SQLiteMemoryStore(":memory:")` or `tmp_path`-scoped file

### Query Contract Redesign (MB004.1, ADR-0008)
**Before:** `recent_missions(limit)` + `missions_by_status(status, limit)` — two methods
**After:** Single `query_missions(query: MissionQuery) -> list[MissionRecord]`
- `MissionQuery` dataclass: `status`, `limit`, `offset` (today)
- New filters = new fields on dataclass, never new methods on `MemoryStore`
- `Memory`'s public methods unchanged — build `MissionQuery` internally
- `offset` exists for Layer 5's future indexer (paging entire history)

### Artifacts Generic Storage (MB004.1, ADR-0008)
- `artifacts: list[dict]` with `{"type": ..., "path"/"id"/...: ...}`
- `MissionRecord.folders_created`/`.files_created` remain as `@property` views
- Future capabilities (git commit, shell output, browser download) contribute own shape without schema change

---

## Memory Retrieval

### Supported Queries (Exactly 5, from `MEMORY_ARCHITECTURE.md` §8)

| Query | `Memory` Method | Backing `MissionStore.query_missions(...)` |
|-------|-----------------|--------------------------------------------|
| Last mission | `last_mission()` | `MissionQuery(limit=1)`, first row |
| Mission by ID | `mission_by_id(id)` | `get_mission` (point lookup by PK) |
| Last 10 missions | `recent_missions(limit=10)` | `MissionQuery(limit=10)` |
| Successful missions | `successful_missions()` | `MissionQuery(status="completed")` |
| Failed missions | `failed_missions()` | `MissionQuery(status="failed")` |

### Conversational Surface (`MEMORY_ARCHITECTURE.md` §9)
`cli.py` recognizes two phrasings (checked after wake/pending, before intent parsing):
- `"What was my last mission?"` → single-mission summary: title, status sentence, relative timestamp
- `"Show my recent missions."` → numbered list (up to 10), each: title + short status word

**Note:** Timestamps UTC-relative (no user timezone configured). `mission_by_id`, `successful_missions`, `failed_missions` are real tested methods without conversational phrasing — flagged honestly as gap.

---

## Memory Consolidation

### Knowledge Lifecycle (Constitution §9.3, RESEARCH-BACKED)
```
Execution → Evidence → Knowledge Candidate → Promotion Review → Permanent Knowledge → Future Reasoning
```

**Stage Ownership:**
| Stage | Owner | What Happens |
|-------|-------|--------------|
| Execution | Operator (Worker) | Produces effects in Environment Instance |
| Evidence | Verification Subsystem (§10), stored via Shared Infrastructure | Observation + Expected Outcome + Verdict = durable record |
| Knowledge Candidate | Brain (Planner) | Recognizes recurring pattern in Evidence, nominates it (reasoning judgment) |
| Promotion Review | Dedicated gate, human-confirmed (Founder Edition) | Checks Candidate: observed enough times, not contradicted, not superseded |
| Permanent Knowledge | Shared Infrastructure (Memory Layer 4) | Durable, queryable, actively consulted |
| Future Reasoning | Brain (Planner) | Consumes Permanent Knowledge like recent Mission history |

**Promotion Review Gate (Constitution §9.4):**
- Changing Brain's future reasoning permanently and silently = high-leverage, hard-to-reverse action
- **Requires human confirmation** for Founder Edition (same "one clear decision point" as destructive capabilities)
- Automating later = legitimate evolution (EVOLVABLE), not principle change
- Rejection: Promotion Review can reject outright; Permanent Knowledge revocable if higher-tier Evidence contradicts

### Temporary vs Permanent (Constitution §9.5)
Dividing line = Promotion Review gate. Nothing crosses from "recorded" to "actively shapes future reasoning" without passing through it. Mission's raw Evidence = history; only becomes Knowledge once promoted.

---

## Memory Lifecycle

### Mission Flow (`MEMORY_ARCHITECTURE.md` §7)
```
MasterAgentSession.handle()
    |
    v
Mission (Layer 2)
    |
    v
Executor / Orchestrator
    |
    v
Result (ExecutionResult -> InvocationResult -> StepResult)
    |
    v
MissionRecord (built at terminal state)
    |
    v
Memory facade -> MemoryStore -> SQLite (Layer 3)
```

### Auto-Persistence Triggers (Rule 7)
`MasterAgentSession._remember()` called at every terminal state:
- `_finish()` → after `COMPLETED` or `FAILED`
- `_handle_approval_response()` "no" branch → after `CANCELLED`

**No manual save calls from CLI.** `approval_status` derived from how `_run()` reached:
- `"not_required"` — never needed human decision
- `"approved"` — resumed after "Yes"
- `"denied"` — human said "No"

### Privacy (`MEMORY_ARCHITECTURE.md` §10)
- No telemetry, analytics, hidden network calls in `memory/`
- Every import = Python stdlib (`sqlite3`, `json`, `pathlib`, `datetime`, `dataclasses`, `abc`, `typing`)
- No cloud storage — Layer 6 unimplemented interface
- SQLite at `~/.master_agent/memory.db` (created on first use, `Path.home()`-based)
- Tests never touch real path — use `:memory:` or `tmp_path`

---

## Persistence Relationship

### Memory (Mission History) vs Persistence (Operational State)
| Aspect | Memory (Layer 3) | Persistence (MB025) |
|--------|------------------|---------------------|
| **Concern** | Mission history — queryable, indexed, long-lived | Operational state — small whole-object snapshot |
| **Storage** | SQLite (`~/.master_agent/memory.db`) | JSON (`snapshot.json` + `events.jsonl`) |
| **Read Pattern** | Planner reads for "have I done this before" | Read once at startup, never queried into |
| **Schema** | Migrations when needed | JSON human-inspectable; versioned envelope + checksum |
| **Write** | Auto at terminal mission state | Cycle end + shutdown (Runtime `CheckpointSink`) |

**Why Not Conflate (MB025 §4):**
- Memory = mission history (Planner consumer)
- Persistence = operational state (Runtime/Mission Control consumer)
- Conflating would be a mistake — different concerns, different access patterns
- Row store buys indexing Memory needs; Persistence never uses partial reads
- JSON is human-inspectable for debugging "why did it not come back up"

### Recovery Interaction
- Memory survives restart — durable anchor (Constitution §11.2)
- Persistence restores Mission Control + Runtime counters
- Interrupted tasks quarantined (Persistence) → `FAILED` in Mission Record (Memory)
- Strategic re-run = Brain's judgement (Constitution §11)

---

## Security and Privacy Boundaries

### Data Never Stored
- Raw conversation text (Layer 1 in-process only)
- Anything leaving machine (Layer 6 placeholder)
- Secrets/credentials (named for future conscious decision)
- Reconstructed results (only Executor-reported `ExecutionResult.output`)

### Access Control
- `MasterAgentSession` depends on `Memory` facade, injected per session
- Tests construct isolated stores (`:memory:` or `tmp_path`)
- No singleton — `build_default_session()` creates one real instance per session

### Configuration
- SQLite path via `cli.py`'s `_default_memory_db_path()` → `Path.home()`-based (consistent with `FilesystemPlugin`)
- No cloud storage — Layer 6 opt-in plugin via `MemoryStore` interface

---

## Current Implementation Status

| Layer | Constitution Status | Implementation Status | Notes |
|-------|---------------------|----------------------|-------|
| **1: Conversation Memory** | FROZEN (§9.1) | ✅ **IMPLEMENTED** | `memory/conversation.py` — bounded, in-process |
| **2: Mission Memory** | FROZEN (§9.1) | ✅ **IMPLEMENTED** | Pre-existing `Mission` + `MasterAgentSession.last_mission` |
| **3: Persistent Memory** | FROZEN (§5.4) | ✅ **IMPLEMENTED** | `SQLiteMemoryStore` + `Memory` facade; auto-persist at terminal states |
| **4: Knowledge Memory** | RESEARCH-BACKED (§9.3) | ⏳ **RESERVED** | `KnowledgeMemory` interface in `memory/future.py` only |
| **5: Vector Memory** | FUTURE | ⏳ **INTERFACE ONLY** | `VectorMemory` interface in `memory/future.py` only |
| **6: Cloud Sync** | OPTIONAL FUTURE | ⏳ **INTERFACE ONLY** | `CloudSyncMemory` interface in `memory/future.py` only |

### API Contract
| Component | Status | Notes |
|-----------|--------|-------|
| `MemoryStore` ABC | ✅ **IMPLEMENTED** | 5 methods; `SQLiteMemoryStore` only impl |
| `Memory` Facade | ✅ **IMPLEMENTED** | Single seam; composes L1 + L3 |
| `MissionQuery` dataclass | ✅ **IMPLEMENTED** | `status`, `limit`, `offset` |
| Conversational queries | ⚠️ **PARTIAL** | 2/5 phrasings wired; 3 methods lack phrasing |

### Tradeoffs and Known Limitations (`MEMORY_ARCHITECTURE.md` §11)
- UTC-relative timestamps (not local-time)
- `mission_by_id`, `successful_missions`, `failed_missions` lack conversational phrasing
- `MissionManager` unwired from live path (scoped to real Planner work)
- No transactional guarantees beyond SQLite's own
- Single process, one grant table, one SQLite connection
- `LocalExecutor._log` unbounded in-memory list (not part of Memory — leak risk in daemon)

---

## Design vs Implementation Differences

| Area | Design (Constitution + MEMORY_ARCHITECTURE.md) | Implementation | Status |
|------|------------------------------------------------|----------------|--------|
| **Layer 2 as separate class** | "Deliberately not a new class" — uses existing `Mission` | ✅ Aligned — no new class created | ✅ MATCH |
| **Layer 3 backend** | Swappable via `MemoryStore` ABC | ✅ `SQLiteMemoryStore` only; `JSONMemoryStore` possible | ✅ MATCH |
| **Query API** | Single `query_missions(MissionQuery)` | ✅ Redesigned in MB004.1 (ADR-0008) | ✅ MATCH |
| **Artifacts column** | Generic `artifacts` JSON (not filesystem-specific) | ✅ Changed from `folders_created`/`files_created` | ✅ MATCH |
| **Auto-persistence** | At every terminal state, no manual save | ✅ `_remember()` in `_finish()` and approval "no" | ✅ MATCH |
| **Layer 4–6** | Interfaces only, no wiring | ✅ `memory/future.py` ABCs only | ✅ MATCH |
| **MissionManager wiring** | Should call `Memory` same as `MasterAgentSession` | ❌ Unwired — imports `MemoryStore` but unused | ⚠️ GAP |
| **Conversational coverage** | All 5 query methods reachable | ❌ Only 2/5 wired to `cli.py` parser | ⚠️ GAP |
| **Timezone** | UTC-relative only | ✅ Known simplification | ✅ MATCH |
| **Transactional guarantees** | Only SQLite's own | ✅ Acceptable for Founder Edition | ✅ MATCH |

---

## Open Questions

1. **MissionManager unwired** — `cli.py`'s `MasterAgentSession` only live path; `MissionManager` imports `MemoryStore` but unused (`MEMORY_ARCHITECTURE.md` §11). Scoped to "real Planner" work (`ROADMAP.md` item 3).

2. **Conversational phrasing incomplete** — `mission_by_id`, `successful_missions`, `failed_missions` are real tested methods without `cli.py` phrasing. Deliberate scope cut to match brief's two examples.

3. **UTC vs local timestamps** — Known simplification; needs real timezone concept before honest for multi-timezone users.

4. **Transactional guarantees** — Crash between filesystem effects and `save_mission()` leaves filesystem change real but unrecorded. Acceptable for Founder Edition; named for safety-critical future.

5. **Single-process limits** — One grant table, one SQLite connection. Fine for desktop CLI; needs reconsidering for multi-process/server deployment.

6. **`LocalExecutor._log` unbounded** — Not part of Memory; would leak in long-running daemon. Flagged on `ROADMAP.md` as future one-line item.

7. **Knowledge Memory (Layer 4) not implemented** — `KnowledgeMemory` interface reserved; Promotion Review human-gated (Constitution §9.4). Unblocked by Constitution freeze.

8. **Vector Memory (Layer 5) not implemented** — Interface only; natural shape reads Layer 3 via `MissionQuery.offset` for background indexing.

9. **Cloud Sync (Layer 6) optional** — Off by default forever unless founder decision. Arrives as plugin via `MemoryStore` interface.

---

## Future Extraction Targets

1. `src/master_agent/memory/conversation.py` — Layer 1 implementation
2. `src/master_agent/memory/store.py` — `MemoryStore` ABC + `SQLiteMemoryStore`
3. `src/master_agent/memory/memory.py` — `Memory` facade
4. `src/master_agent/memory/future.py` — Layer 4–6 interfaces
5. `src/master_agent/mission_manager/mission.py` — Layer 2 `Mission` object
6. `src/master_agent/mission_manager/mission_manager.py` — Unwired `MissionManager`
7. `src/master_agent/cli.py` — Conversational surface (`_remember`, query phrasings)
8. `tests/test_memory_*.py` — Test coverage for all layers
9. `docs/adr/0007` — Memory backend choice (stdlib sqlite3 over ORM)
10. `docs/adr/0008` — Memory scale review (query contract + artifacts redesign)

---

## Wiki Links Added

- `[[KALPAVRIKSHA_VISION_V2.md]]` — Constitution §5.4, §9, Rule 7, Rule 8
- `[[FOUNDER_CONSTITUTION_FREEZE.md]]` — Freeze record, section status
- `[[MEMORY_ARCHITECTURE.md]]` — Primary source document
- `[[ARCHITECTURE.md]]` — Implementation map §4.8
- `[[PERSISTENCE_ARCHITECTURE.md]]` — Operational persistence (separate concern)
- `[[MISSION_CONTROL_ARCHITECTURE.md]]` — Mission State ownership, Audit Stream
- `[[01_executive_brain.md]]` — Brain reads Memory, nominates Knowledge Candidates
- `[[02_constitution.md]]` — Constitution summary
- `[[03_universal_executive_operator.md]]` — Operator writes Evidence to Memory
- `[[04_shared_infrastructure.md]]` — Memory as Shared Infrastructure component
- `[[system_overview.md]]` — System overview
- `[[docs/adr/0007]]` — Memory backend choice
- `[[docs/adr/0008]]` — Memory scale review
- `[[docs/adr/0010]]` — Shared Infrastructure layer
- `[[docs/adr/0012]]` — Knowledge Lifecycle
- `[[docs/adr/0015]]` — Persistence strategy (Proposed)

---

*Document created from verified sources only. No memory capabilities invented. Terminology preserved exactly. Frozen design separated from implementation status.*