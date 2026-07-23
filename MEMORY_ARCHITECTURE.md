# Memory Architecture

Status: Updated 2026-07-23 — Miracle 004.1, Memory System Scale Review
(see §6a, §6b — the query contract and the artifact schema were
generalized after a design review against multi-year, high-volume growth;
`docs/adr/0008-memory-scale-review.md` has the full before/after
reasoning). Originally added 2026-07-23 — Miracle 004, The Memory System.

This is the design document required before any Memory code was written
(per the Miracle 004 brief's explicit gate: "Only after the design is
complete should implementation begin"). It explains why Memory exists,
what it does and does not remember, how its layers interact, and where
it grows next. `ARCHITECTURE.md` §4.8 has the short summary; this file is
the detail.

## 1. Why Memory exists

Every Miracle through 003.5 proved Master Agent can *act* — parse an
intent, get approval, execute it, report the outcome. None of that
survives the process exiting. `MasterAgentSession.last_mission` (the only
memory that has existed until now) is a single Python attribute: it
forgets the moment the interpreter does.

That's a ceiling, not a bug in isolation — Mission Briefs 001-003.5
deliberately scoped memory out so the execution path could be proven
first. But "Trust through transparency" (`PRODUCT_PRINCIPLES.md`) requires
a mission history that survives a restart — a track record the founder
(and eventually the Planner) can actually inspect. And every future
capability this project has already named — Voice ("what did I ask you
to do earlier"), the real Planner (using past outcomes as context),
Multi-Agent execution (coordinating around shared history), Vector Memory
(semantic recall over that history), Cloud Sync (syncing that history) —
depends on mission history existing somewhere durable, in a shape those
future consumers can read without knowing how it's stored.

So Memory exists to do two things: let missions survive the process that
ran them, and give every future subsystem one seam to depend on instead
of five different ones each inventing its own persistence.

## 2. What should be remembered

- **Mission outcomes** — what was asked, what was planned, whether it was
  approved, what actually happened, how long it took, what got created,
  what went wrong. This is the substance of "a track record that's
  inspectable."
- **Mission identity and timing** — a stable ID and timestamps, so a
  mission can be looked up individually and ordered chronologically.
- **User preferences** (carried over from ADR-0004's original interface,
  now actually implemented) — small durable key/value facts the founder
  has told the system to remember, distinct from mission history.

## 3. What should never be remembered

- **Raw conversation text, persisted indefinitely.** Layer 1
  (Conversation Memory) exists in-process only and is discarded when the
  session ends. A user's typed text can contain anything — there's no
  reason for it to outlive the process by default, and nothing in this
  Miracle's brief asked for a searchable conversation transcript. If a
  future Miracle wants that, it's a deliberate, separately-scoped
  decision, not a side effect of building mission memory.
- **Anything that leaves the machine.** No telemetry, no analytics, no
  network calls, no cloud storage — Layer 6 (Cloud Sync) is a placeholder
  interface with zero implementation, exactly as the brief requires. Every
  file in `memory/` imports only the Python standard library
  (`sqlite3`, `json`, `pathlib`, `datetime`, `dataclasses`, `abc`,
  `typing`) — there is nothing in this module that could phone home even
  by accident.
- **Secrets or credentials.** Nothing in the current system handles these,
  so there's nothing to exclude yet — named here so a future Miracle that
  adds anything credential-shaped has to consciously decide whether it
  belongs in Memory at all (probably not) rather than defaulting it in.
- **Anything a mission's own action didn't actually produce.** Memory
  records what the Executor reports, not a guess at it — `execution_result`
  is the real `ExecutionResult.output`/`InvocationResult.output`, not a
  reconstruction.

## 4. The six layers, and how they interact

| Layer | Name | Scope | Status this Miracle |
|---|---|---|---|
| 1 | Conversation Memory | Current session | **Implemented** |
| 2 | Mission Memory | Current execution | **Implemented** (pre-existing, formalized here) |
| 3 | Persistent Memory | Durable, this machine | **Implemented** (SQLite) |
| 4 | Knowledge Memory | Durable facts/documents | Reserved — interface only |
| 5 | Vector Memory | Semantic recall | Future — interface only |
| 6 | Cloud Sync | Multi-device | Optional future — interface only |

```
Conversation (L1, in-process)
     |
     v
 MasterAgentSession.handle()
     |
     v
   Mission  (L2 — mission_manager/mission.py's Mission object;
     |        this IS the "current execution" layer — nothing new
     |        was built for it, see §4b below)
     v
 Executor / Orchestrator  (unchanged by this Miracle)
     |
     v
  Result  (ExecutionResult -> InvocationResult -> StepResult)
     |
     v
  MissionRecord  (built once the mission reaches a terminal state)
     |
     v
   Memory facade  ---->  MemoryStore  ---->  SQLite (L3, this machine)
                                        \
                                         `-- (future) L4/L5/L6 read L3's
                                             history; they do not require
                                             L3's schema to change
```

### 4a. Layer 1 — Conversation Memory

`memory/conversation.py`. `ConversationMemory` holds the current session's
turns (`ConversationTurn(speaker, text, at)`) in a bounded in-memory list
(`max_turns`, default 200 — old turns fall off rather than growing
unboundedly). `MasterAgentSession.handle()` records the user's text and
the system's reply on every call, automatically. Nothing here touches
disk. When the process exits, this layer is gone — that's the design, not
a gap (see §3).

### 4b. Layer 2 — Mission Memory

Deliberately **not** a new class. "The current execution" is already
represented by the real `Mission` object (`mission_manager/mission.py`,
built in Mission Brief 001) plus `MasterAgentSession.last_mission` and the
`StepResult`/`ExecutionResult` produced while a mission runs. Wrapping
that in a second object would duplicate state that already exists and
risk the two falling out of sync. This Miracle's actual contribution to
Layer 2 is the translation step at its boundary: once a mission reaches a
terminal status (`COMPLETED`, `FAILED`, or `CANCELLED`),
`MasterAgentSession._remember()` converts that in-flight state into a
`MissionRecord` and hands it to the Memory facade. Before that point nothing
changes; Layer 2 behaves exactly as it did in Mission Briefs 001-003.5.

### 4c. Layer 3 — Persistent Memory (SQLite)

`memory/store.py`. See §5 for the schema. `SQLiteMemoryStore` implements
the `MemoryStore` interface (originally sketched, unimplemented, in
ADR-0004) using the Python standard library's `sqlite3` module directly —
see ADR-0007 for why an ORM (`sqlmodel`, already a project dependency for
possible future use) was not used here.

### 4d. Layers 4-6 — reserved and future

`memory/future.py` defines `KnowledgeMemory` (L4), `VectorMemory` (L5),
and `CloudSyncMemory` (L6) as abstract interfaces with no implementation
and no wiring into `MasterAgentSession` or anywhere else live. They exist
so a future Miracle has an agreed shape to build into, matching the
brief's instruction: "The implementation should only build Layers 1-3.
Layers 4-6 remain interfaces or placeholders." See §7 for what each is
expected to become.

## 5. The SQLite schema (Layer 3)

Readable first, not optimized first — two tables, JSON text columns for
anything that isn't queried yet rather than a normalized multi-table
design nothing currently needs:

```sql
CREATE TABLE IF NOT EXISTS missions (
    mission_id             TEXT PRIMARY KEY,
    title                   TEXT NOT NULL,   -- e.g. Create Python Project "Demo"
    intent_summary          TEXT NOT NULL,   -- the raw text the user typed
    status                  TEXT NOT NULL,   -- "completed" | "failed" | "cancelled"
    approval_status         TEXT NOT NULL,   -- "not_required" | "approved" | "denied"
    created_at              TEXT NOT NULL,   -- ISO 8601 UTC, when the Mission was created
    completed_at            TEXT NOT NULL,   -- ISO 8601 UTC, when it reached a terminal state
    execution_plan          TEXT NOT NULL,   -- JSON: [{step_id, capability, payload}, ...]
    execution_result        TEXT,            -- JSON: the raw result output, or NULL
    execution_time_seconds  REAL NOT NULL DEFAULT 0.0,
    artifacts                TEXT NOT NULL,   -- JSON: [{"type": ..., "path"/"id"/...: ...}, ...]
    errors                    TEXT NOT NULL,   -- JSON list of error strings
    outcome                   TEXT             -- JSON: Mission.outcome, mirrored for transparency
);
-- Unfiltered recency queries (last_mission, recent_missions) hit this one.
CREATE INDEX IF NOT EXISTS idx_missions_completed_at ON missions(completed_at);
-- Status-filtered recency queries (successful_missions, failed_missions)
-- hit this composite index instead of a status-only index + a separate
-- sort step -- matters at large per-status row counts, not today's
-- volumes, but costs nothing to have from day one.
CREATE INDEX IF NOT EXISTS idx_missions_status_completed ON missions(status, completed_at);

CREATE TABLE IF NOT EXISTS preferences (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL   -- JSON
);
```

This covers every field the brief asked for: Mission ID, Timestamp
(`created_at`/`completed_at`), Intent (`intent_summary`), Execution Plan,
Approval Status, Execution Result, Execution Time, Files Created, Folders
Created, Status, Errors. `title` and `outcome` are additions beyond the
brief's list — `title` because the conversational query responses (§9)
need a clean display string, not a re-parse of raw intent text every time;
`outcome` because mirroring `Mission.outcome` verbatim costs one column
and keeps the record fully self-describing without a second query.

**`artifacts`, not `folders_created`/`files_created` columns (§6b).**
"Files created" and "folders created" are what the brief asked for by
name, and `MissionRecord.folders_created`/`.files_created` still exist as
computed properties returning exactly that — but the *column* is a
generic `artifacts` list of `{"type": ..., ...}` entries, not two
filesystem-specific columns. A future capability whose output isn't
folder/file-shaped (a git commit, a shell command's exit code, a
downloaded asset) contributes its own artifact shape without a schema
change. See `docs/adr/0008-memory-scale-review.md` for why this changed
from the original Mission Brief 004 shape.

`execution_plan`, `execution_result`, `artifacts`, and `errors` are JSON
text rather than normalized child tables because nothing today needs to
query *into* them (e.g. "find every mission that created a file named
X") — only the top-level `status` and `completed_at` are actually
filtered/sorted on, hence the two indexes. If a future Miracle needs to
query inside those fields, that's the trigger to normalize them then, not
now.

## 6. The Memory API (the contract)

Two layers of interface, matching the "the rest of the system must never
know whether storage is SQLite / JSON / Postgres / Vector DB / Cloud"
requirement:

- **`MemoryStore`** (`memory/store.py`, ABC) — the storage contract:
  `save_mission`, `get_mission`, `query_missions`, `remember_preference`,
  `recall_preference`. `SQLiteMemoryStore` is the only implementation
  today. A `JSONMemoryStore` or a future Postgres-backed store would
  implement the same five methods and nothing above it would need to
  change.

### 6a. Why `query_missions(MissionQuery)` and not a method per query shape

The original Mission Brief 004 shape had `recent_missions(limit)` and
`missions_by_status(status, limit)` as two separate `MemoryStore`
methods. A scale review (`docs/adr/0008-memory-scale-review.md`) flagged
this as a design that would not survive "hundreds of capabilities": every
future filter (a date range, a specific capability, eventually free-text
search once Layer 5 exists) would otherwise become another `MemoryStore`
method, growing the storage contract forever and making every current and
future backend implementation more expensive to write.

The fix: one `query_missions(query: MissionQuery) -> list[MissionRecord]`
method. `MissionQuery` is a small dataclass (`status`, `limit`, `offset`
today) — new filters are new fields on this dataclass, never new methods
on `MemoryStore`. `Memory`'s public, friendly methods
(`last_mission()`, `recent_missions()`, `successful_missions()`,
`failed_missions()`) are unchanged and build the right `MissionQuery`
internally — nothing above `Memory` (`cli.py`, tests, a future Planner)
needed to change when this was reshaped underneath it. `offset` exists
ahead of any consumer needing it, for Layer 5's future indexer (§12),
which will need to page through the *entire* mission history, not just
the most recent N — a one-field, zero-new-infrastructure addition, not
premature complexity.

### 6b. Why `artifacts`, not `folders_created`/`files_created`, is the stored shape

The same review flagged `folders_created`/`files_created` as columns that
hardcode a filesystem-specific assumption about what a mission produces.
They work for today's two capabilities and nothing else — a future git
plugin's commit, a shell command's output, a browser plugin's downloaded
file none of these are "folders" or "files." The fix: store a generic
`artifacts: list[dict]` (`{"type": ..., "path"/"id"/...: ...}`) instead;
`MissionRecord.folders_created`/`.files_created` remain as `@property`
views computed from `artifacts`, so the brief's literal ask and every
existing caller keep working — `artifacts` is now the source of truth
underneath them. See `docs/adr/0008-memory-scale-review.md`.
- **`Memory`** (`memory/memory.py`, facade) — the single object the rest
  of the system actually depends on. Composes Layer 1
  (`ConversationMemory`) and a `MemoryStore` (Layer 3) behind one surface:
  `record_turn`, `conversation_turns`, `persist_mission`, `mission_by_id`,
  `last_mission`, `recent_missions`, `successful_missions`,
  `failed_missions`, `remember_preference`, `recall_preference`.
  `MasterAgentSession` depends on `Memory`, injected through its
  constructor — never on `SQLiteMemoryStore` directly, never as a
  singleton (`build_default_session()` constructs one real instance per
  session; tests construct their own, usually over `:memory:`).

## 7. Mission flow — how persistence actually happens

`MasterAgentSession` calls `self._remember(...)` (which builds a
`MissionRecord` and calls `self._memory.persist_mission(...)`) at every
point a mission reaches a terminal state:

- `_finish()` — after a mission transitions to `COMPLETED` or `FAILED`.
- `_handle_approval_response()`'s "no" branch — after a mission
  transitions to `CANCELLED`.

`main()` and the CLI loop never call anything memory-related — persistence
is automatic, exactly as the brief requires ("No manual save calls from
the CLI"). `approval_status` is derived from *how* `_run()` was reached:
`"not_required"` if the mission never needed to stop for a human decision,
`"approved"` if it resumed after a "Yes", `"denied"` if the human said
"No". Today every implemented capability is `REVERSIBLE_WRITE`, so
`"not_required"` doesn't occur in practice yet — it exists for the day a
`READ_ONLY` capability (which skips the approval gate entirely, per
`PermissionSystem.check()`) reaches this code path.

## 8. Query support

No semantic search — five simple, literal queries, exactly as scoped:

| Query | `Memory` method | Backing `MissionStore.query_missions(...)` call |
|---|---|---|
| Last mission | `last_mission()` | `MissionQuery(limit=1)`, first row |
| Mission by ID | `mission_by_id(id)` | (`get_mission`, not `query_missions` — a point lookup by primary key) |
| Last 10 missions | `recent_missions(limit=10)` | `MissionQuery(limit=10)` |
| Successful missions | `successful_missions()` | `MissionQuery(status="completed")` |
| Failed missions | `failed_missions()` | `MissionQuery(status="failed")` |

`Memory`'s method names and signatures above are unchanged from the
original Mission Brief 004 shape — the `MissionQuery`/`query_missions`
redesign (§6a) is entirely internal to how `Memory` talks to
`MemoryStore`.

Two of these are reachable from real conversation today (see §9);
`mission_by_id`, `successful_missions`, and `failed_missions` are real,
tested methods on `Memory` without conversational phrasing wired to them
yet — flagged honestly as a gap in the deliverable report, not hidden.

## 9. Conversational surface

`cli.py` recognizes two new phrasings, checked after the wake/pending
checks and before ordinary intent parsing (so they never start a Mission
and never fight with an in-progress approval):

- `"What was my last mission?"` → a single-mission summary: title, a
  status sentence ("Completed successfully." / "Failed." /
  "Cancelled."), and a relative timestamp ("Today at 3:05 PM." /
  "Yesterday at 8:14 PM." / a full date further back).
- `"Show my recent missions."` → a numbered list (up to the last 10),
  each entry a title and a short status word ("Success" / "Failed" /
  "Cancelled").

**A note on matching the brief's example transcripts closely, not
literally:** the brief's two example conversations use two different title
phrasings for the same kind of mission (`Create Python Project "Demo"` in
the first example vs. `Create Demo Project` in the second) and the second
example references a `"Delete Temp"` capability that doesn't exist
anywhere in this codebase. Reading these as exact strings to reproduce
would mean either fabricating a delete capability or presenting
inconsistent title formats for the same kind of mission depending on
which query was asked — both worse than picking one clean, consistent
title format and using it everywhere. This implementation uses
`Create {Type }Project "{name}"` / `Create Folder "{name}"` consistently
for both the single-mission and list views, and applies the "Cancelled"
status the second example shows to real cancelled missions (declined
approvals), which do exist in this codebase. If a real "delete" capability
is added later, it inherits the same title convention automatically.
Timestamps are formatted from the UTC datetimes `Mission` already
produces — there's no user timezone configured anywhere in the system yet,
so "Today"/"Yesterday" are UTC-relative, not local-time-relative. That's a
known simplification, not a hidden one (see §10).

## 10. Privacy

Local-first, exactly as required:

- No telemetry, no analytics, no hidden network calls anywhere in
  `memory/`. Every import is Python standard library.
- No cloud storage — Layer 6 is an unimplemented interface, not a
  disabled feature flag.
- The SQLite file lives at `~/.master_agent/memory.db` by default
  (`cli.py`'s `_default_memory_db_path()`), created on first use, entirely
  on the machine the process runs on. Consistent with the rest of the
  project's `Path.home()`-based defaults (e.g. `FilesystemPlugin`'s
  Desktop location).
- Tests never touch that path — every test constructs its own
  `SQLiteMemoryStore(":memory:")` or a `tmp_path`-scoped file, so running
  the suite never reads or writes a real founder's mission history.

## 11. Tradeoffs and known limitations

- **UTC-relative timestamps, not local-time-relative** (see §9). Fine for
  a founder in one timezone running this locally; would need a real
  timezone concept before it's fully honest for anyone else.
- **`mission_by_id`, `successful_missions`, `failed_missions` have no
  conversational phrasing yet** — real, tested, reachable via `Memory`
  directly, not yet wired to `cli.py`'s parser. Small, deliberate scope
  cut to keep this Miracle's conversational surface exactly matching the
  brief's two given examples rather than inventing three more phrasings
  the brief didn't ask for.
- **`MissionManager` (`mission_manager/mission_manager.py`) still isn't
  wired into the live path.** It already imports `MemoryStore` and has a
  `transition()` method whose comment describes persisting on every
  transition, but `cli.py`'s `MasterAgentSession` — the only working
  conversational path — has never used `MissionManager`, before or after
  this Miracle. This Miracle wires persistence into the path that
  actually runs, not into the currently-dead scaffold; `MissionManager`
  becoming real is naturally scoped into the "real Planner" work already
  on `ROADMAP.md` (item 3), at which point it should call into `Memory`
  the same way `MasterAgentSession._remember()` does now.
- **No transactional guarantees beyond SQLite's own.** A crash between a
  mission's filesystem side effects and its `save_mission()` call would
  leave the filesystem change real but unrecorded. Acceptable for Founder
  Edition; worth naming if Memory becomes load-bearing for anything
  safety-critical later.
- **One process, one grant table, one SQLite connection** — `PermissionSystem`
  was already single-process/in-memory (unchanged by this Miracle);
  `SQLiteMemoryStore` opens one connection for its own lifetime, which is
  fine for a single-user desktop CLI and would need reconsidering for any
  future multi-process or server deployment.
- **`LocalExecutor._log` (`executor/executor.py`, Mission Brief 002) is an
  unbounded in-memory list, not part of Memory at all.** Found during the
  scale review, out of scope to fix here since it predates this Miracle
  and touching it wasn't asked for. Not a problem for a CLI process that
  exits after a session, but would leak memory in a long-running daemon
  processing missions for years. Flagged on `ROADMAP.md` as a future
  one-line item: bound it, or fold it into `Memory` now that a durable
  home for execution history exists.

## 12. Future evolution path

- **Layer 4 (Knowledge Memory)** — durable facts distinct from mission
  history (e.g. founder preferences learned in conversation, not typed as
  a `remember_preference` call; ingested documents). `KnowledgeMemory` in
  `memory/future.py` is the interface to implement against; it does not
  require Layer 3's schema to change.
- **Layer 5 (Vector Memory)** — semantic recall, exactly as ADR-0004
  already anticipated ("a local embedding index for semantic recall").
  The natural shape: a component that reads Layer 3's `missions` table
  (via `MissionQuery`'s `offset` field, walking the whole table page by
  page — already there for exactly this, see §6a) and indexes
  `title`/`intent_summary`/`execution_result` locally — additive, not a
  migration. Deep `OFFSET` pagination is O(offset) in SQLite; fine for a
  one-time or periodic background index build, not something this
  Miracle solved further since nothing today demonstrates a need to.
- **Layer 6 (Cloud Sync)** — arrives as an optional plugin, per ADR-0004,
  reading/writing through the same `MemoryStore` interface rather than
  bypassing it — e.g. a `push(since=...)`/`pull()` implementation of
  `CloudSyncMemory` that syncs `missions` rows to a remote store the
  founder explicitly opts into. Off by default, forever, unless a founder
  decision says otherwise.
- **Planner context** — once the real Planner (`ROADMAP.md` item 3)
  exists, it's a natural consumer of `Memory.recent_missions()`/
  `Memory.successful_missions()` as context for "have I done something
  like this before."
- **`MissionManager` wiring** — see §11's note; becomes real alongside the
  Planner work, calling `Memory.persist_mission()` the same way
  `MasterAgentSession` does today.
