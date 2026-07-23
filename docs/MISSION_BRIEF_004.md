# Mission Brief 004 — The Memory System

Status: Implemented (2026-07-23)

## Objective

Give Master Agent a memory that survives a restart, designed so it can
grow for years without a rewrite — not "add SQLite," a real layered
architecture with only the layers needed today actually built. Per the
brief's explicit gate, design came before code: `MEMORY_ARCHITECTURE.md`
was written and is the authoritative design document; this file is the
delivery record.

## Design summary

Six layers, three implemented:

1. **Conversation Memory** (`memory/conversation.py`) — current session's
   turns, in-process, never persisted.
2. **Mission Memory** — the mission currently executing. Not a new class:
   this is the pre-existing `Mission` object
   (`mission_manager/mission.py`, Mission Brief 001) plus
   `MasterAgentSession.last_mission`, formalized rather than duplicated.
3. **Persistent Memory** (`memory/store.py`) — `SQLiteMemoryStore`, the
   first real implementation of the `MemoryStore` interface ADR-0004
   sketched (previously `NotImplementedError` everywhere).
4. **Knowledge Memory** (Reserved), 5. **Vector Memory** (Future), 6.
   **Cloud Sync** (Optional future) — `memory/future.py`, abstract
   interfaces only, nothing instantiated or wired anywhere.

`memory/memory.py`'s `Memory` facade composes Layers 1 and 3 behind one
surface — `MasterAgentSession` (and any future consumer) depends on
`Memory`, never on `SQLiteMemoryStore` directly, injected through the
constructor, never a singleton. Full reasoning, the SQLite schema, the
conversational query design, privacy posture, and known tradeoffs are
all in `MEMORY_ARCHITECTURE.md` — not duplicated here.

## Schema summary

One `missions` table (readable-first, JSON columns for structured fields
nothing queries into yet — see `docs/adr/0007-sqlite-memory-backend.md`
for why), one `preferences` table for the key/value preferences
ADR-0004's original interface already specified. Covers every field the
brief asked for: Mission ID, Timestamp, Intent, Execution Plan, Approval
Status, Execution Result, Execution Time, Files Created, Folders Created,
Status, Errors — plus `title` (a clean display string for the
conversational queries) and `outcome` (mirrors `Mission.outcome`
verbatim). Full DDL: `MEMORY_ARCHITECTURE.md` §5.

## Mission flow — how persistence became automatic

`MasterAgentSession._remember()` builds a `MissionRecord` and calls
`self.memory.persist_mission(...)` at every point a mission reaches a
terminal state — `_finish()`'s `COMPLETED`/`FAILED` branches, and
`_handle_approval_response()`'s `CANCELLED` branch. `main()` and the CLI
loop never call anything memory-related; persistence happens inside
`MasterAgentSession` itself, automatically, exactly as the brief
required ("No manual save calls from the CLI").

`approval_status` (`"not_required"` / `"approved"` / `"denied"`) is
derived from how `_run()` was reached — every implemented capability is
currently `REVERSIBLE_WRITE` and always requires approval, so
`"not_required"` doesn't occur in practice yet; it's there for the day a
`READ_ONLY` capability skips the approval gate entirely.

## Conversational surface

Two new phrasings, recognized in `cli.py` after the wake/pending checks
and before ordinary intent parsing (so a memory question never starts a
Mission and never gets mistaken for a pending Yes/No answer):

- `"What was my last mission?"` → title, a status sentence, a relative
  timestamp (`"Today at 3:05 PM."` / `"Yesterday at 8:14 PM."` / a full
  date further back).
- `"Show my recent missions."` → a numbered list (up to the last 10),
  each entry a title and a short status word.

See `MEMORY_ARCHITECTURE.md` §9 for an honest note on why this doesn't
literally reproduce the brief's two example transcripts byte-for-byte —
they use two different, mutually inconsistent title formats for the same
kind of mission, and the second references a "Delete Temp" capability
that doesn't exist in this codebase. This implementation picked one
consistent title format and used it everywhere, which is what a real user
would actually want.

## Files changed

**New:**
- `src/master_agent/memory/conversation.py` — `ConversationTurn`,
  `ConversationMemory` (Layer 1).
- `src/master_agent/memory/memory.py` — `Memory` facade.
- `src/master_agent/memory/future.py` — `KnowledgeMemory`,
  `VectorMemory`, `CloudSyncMemory` (Layers 4-6, interfaces only).
- `MEMORY_ARCHITECTURE.md` — the design document.
- `docs/adr/0007-sqlite-memory-backend.md` — stdlib `sqlite3` over an
  ORM, JSON columns over normalization.
- `tests/test_memory.py` — 24 new tests.
- `docs/MISSION_BRIEF_004.md` — this file.

**Modified:**
- `src/master_agent/memory/store.py` — `MissionRecord` extended with
  `title`, `approval_status`, `completed_at`, `execution_plan`,
  `execution_result`, `execution_time_seconds`, `folders_created`,
  `files_created`, `errors`; `MemoryStore` gained `missions_by_status`;
  `SQLiteMemoryStore` fully implemented (was `NotImplementedError`
  everywhere).
- `src/master_agent/cli.py` — `MasterAgentSession` now takes a `memory:
  Memory` constructor parameter (public `self.memory` attribute,
  matching the existing `self.last_mission` convention); `handle()`
  records every turn to Layer 1 automatically; `_run()`/`_finish()`
  thread an `approval_status` through; new `_remember()`,
  `_answer_memory_query()`, `_record_title()`, `_extract_created()`,
  `_build_mission_record()`, `_status_sentence()`, `_status_word()`,
  `_format_relative_timestamp()`, `_default_memory_db_path()`,
  `_parse_memory_query()` helpers; `build_default_session()` constructs a
  real `SQLiteMemoryStore` at `~/.master_agent/memory.db`.
- `tests/test_cli_session.py` — `build_session()` now constructs and
  injects a `Memory` backed by `SQLiteMemoryStore(":memory:")` (every
  existing test picks this up automatically, zero assertion changes); 13
  new tests covering automatic persistence and the two conversational
  queries.
- `ARCHITECTURE.md` — §4.8 rewritten around the six-layer model; §4.3
  (Mission Manager) corrected to honestly reflect that persistence is now
  real but `MissionManager` itself still isn't part of the live path.
- `PROJECT_BRAIN.md`, `ROADMAP.md` — status sections, orientation table,
  and Planned/Future sections updated.

## Tests added

37 new tests: 24 in `tests/test_memory.py` (SQLite persistence/retrieval,
upsert idempotency, status filtering, preferences, restart-survival,
`Memory` facade query methods, `ConversationMemory` bounding, Layers 4-6
being abstract/unimplemented), 13 in `tests/test_cli_session.py`
(automatic persistence on success/cancellation, folders/files-created
extraction, both conversational queries including the empty-history and
most-recent-not-first cases, a pending-approval-takes-priority-over-a-
memory-question case, and full conversation-turn recording).

## Test results

```
124 passed in 0.28s
```

(93 before this Miracle, all still passing unchanged — zero regressions.)

## Ruff results

```
All checks passed!
```

## Live verification

Ran a real process against a temporary `$HOME` (not `:memory:`, not
`tmp_path` — the real `SQLiteMemoryStore` path `build_default_session()`
constructs): created a Python project, approved it, asked "What was my
last mission?" (got the completed summary), created a folder mission and
declined it, asked "Show my recent missions." (got a two-item list,
newest first, with "Cancelled" and "Success"). Then started a **second,
independent process** against the same `$HOME` and asked both questions
again with no setup — it correctly reported the prior process's history,
confirming mission memory survives a restart, which is the entire point
of Layer 3 existing. Full transcript available in this Miracle's
session log; not reproduced here to keep this doc focused.

## Technical debt and remaining stubs (named honestly)

- **`mission_by_id`, `successful_missions`, `failed_missions` have no
  conversational phrasing yet.** Real, tested `Memory` methods; only
  `last_mission`/`recent_missions` are reachable through `cli.py`'s
  parser today, matching exactly the brief's two given examples rather
  than inventing three more phrasings it didn't ask for.
- **`MissionManager` is still not wired into the live path.** It already
  imports `MemoryStore` and its `transition()` method's docstring
  describes persisting on every transition, but `cli.py`'s
  `MasterAgentSession` — the only working conversational path — has never
  used it, before or after this Miracle. Persistence was wired into the
  path that actually runs. `MissionManager` becoming real is scoped into
  the real-Planner work already on `ROADMAP.md`.
- **UTC-relative timestamps** ("Today"/"Yesterday" are UTC-day-relative,
  not local-time-relative) — no timezone concept exists anywhere in the
  system yet.
- **Layers 4-6 are interfaces only**, by design, per the brief.
- **No transactional guarantee** between a mission's filesystem side
  effects and its `save_mission()` call — a crash between the two would
  leave the filesystem change real but unrecorded.
- **`D:\MasterAgent` remains unverified.** No device bridge was connected
  in this session — everything above was built, tested, and verified
  inside this cloud workspace, then delivered as a zip, exactly as every
  prior Miracle has stated. This gap is unchanged by this Miracle and is
  repeated here per the project's standing instruction on this point.

## Recommendation for Miracle 005

`ROADMAP.md`'s Planned section now leads with **the real Planner**,
replacing `cli.py`'s regex stand-in with an actual Model Router call —
this is both the highest-value next step (unblocks every other roadmap
item) and the natural point to finally wire `MissionManager` into the
live path and give the Planner real context via
`Memory.recent_missions()`/`Memory.successful_missions()`, which is the
whole reason Miracle 004 built Memory in the first place. Recommend
Miracle 005 be scoped to: a live Hermes provider behind
`ModelProvider`, `planner/planner.py` generating a real `MissionPlan`
from an `Intent` instead of raising `NotImplementedError`, and — if it
fits in the same brief without widening scope — the Planner reading
`Memory.recent_missions()` as prompt context for its very first call.
