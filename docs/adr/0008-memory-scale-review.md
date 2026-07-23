# ADR-0008: Memory scale review — generic query contract, generic artifact schema

Status: Accepted (2026-07-23) — Miracle 004.1, Memory System Scale Review

## Context

Immediately after Mission Brief 004 shipped, the founder asked a standing
question to be applied before finalizing any architecture/data
model/API/schema: "if this grows to millions of missions, thousands of
plugins, hundreds of capabilities, and years of accumulated knowledge,
would I still keep this design?" — and named three tests every new
component must pass: can it be extended without modification, can it be
replaced without affecting the rest of the system, will another engineer
understand it six months from now.

Running Mission Brief 004's design through that test surfaced two real
problems, and confirmed the rest of the design already holds up.

## What already holds up (no change)

- **SQLite as the Layer 3 backend.** Handles millions of rows fine with
  the right indexes; the file grows but that's normal for a local-first
  history store (the same shape as a browser history DB or a git log).
- **JSON columns for `execution_plan`/`execution_result`/`errors`/
  `outcome`.** Still correct — nothing queries into them, and adding a
  query that needs to is the trigger to normalize, not a reason to do it
  preemptively (ADR-0007, unchanged).
- **One SQLite connection per store instance, no connection pooling.**
  Correct for a single-user desktop process; explicitly flagged in
  `MEMORY_ARCHITECTURE.md` §11 as the thing to reconsider only if Master
  Agent becomes multi-process — not before there's a demonstrated need.
- **`PermissionSystem`'s linear scan over grants.** Bounded by the number
  of distinct (plugin, capability) pairs in use, not by mission volume —
  stays small (tens to low hundreds of entries) even at "hundreds of
  capabilities" scale. No change needed.
- **`PluginRegistry`'s hardcoded registration in `build_default_session()`.**
  Already an accepted, documented Founder Edition tradeoff (ADR-0004);
  `PluginRegistry.register()` itself doesn't care how a plugin was
  discovered, so swapping hardcoded calls for directory-scanned discovery
  later is additive, not a rewrite.

## What did not hold up, and the fix

### 1. `MemoryStore`'s query surface (`recent_missions`, `missions_by_status`)

**Problem:** two query shapes exist today; a Planner with real mission
history, a future UI history view, and Layer 5's eventual indexer will
each want their own filter (by date range, by capability, by plugin, by
free text once Layer 5 exists). If every new filter becomes a new
`MemoryStore` method, the interface grows one method per query need
forever — at "hundreds of capabilities" scale, that's not extension,
that's modification on every future need, which fails question 1
outright, and makes writing a second `MemoryStore` implementation
(question 2 — can Memory be replaced without affecting the rest of the
system) progressively more expensive as the method count grows.

**Fix:** replaced both methods with one `query_missions(query:
MissionQuery) -> list[MissionRecord]`, where `MissionQuery` is a small
dataclass (`status`, `limit`, `offset` today). Future filters are new
`MissionQuery` fields, not new `MemoryStore` methods — `MemoryStore`
stays at five methods indefinitely. `Memory`'s public API
(`last_mission`, `recent_missions`, `successful_missions`,
`failed_missions`) is unchanged — this is purely an internal contract
improvement; nothing in `cli.py` or any existing caller needed to change.

Added `offset` specifically because Layer 5's future indexer
(`MEMORY_ARCHITECTURE.md` §12) will need to walk the *entire* mission
history to build an index, not just the last N — a paginated read, not a
recency query. This is a one-field addition with zero new complexity, not
new infrastructure — deliberately not building cursor-based keyset
pagination, since SQLite's `OFFSET` is adequate for a one-time background
scan and nothing today demonstrates a need for anything more.

Also added a composite index (`status`, `completed_at`) so the
status-filtered path doesn't need a separate sort step at large
per-status row counts — cheap for a single-writer local database, and
directly serves the "millions of missions" case named in the review.

### 2. `MissionRecord`'s `folders_created`/`files_created` columns

**Problem:** these two fields hardcode an assumption specific to
filesystem capabilities. A future git-operations plugin (a commit), a
shell-command plugin (stdout/exit code), a browser-automation plugin (a
downloaded file, a screenshot) — none of these naturally fit "folders
created" or "files created." At "hundreds of capabilities" scale, either
every new capability category gets awkwardly stuffed into
folders/files, or the schema grows a new pair of columns per category —
neither extends without modification.

**Fix:** replaced both columns with one generic `artifacts: list[dict]`
field, each entry shaped `{"type": ..., "path"/"id"/...: ...}`. Today's
two capabilities produce `{"type": "folder", "path": ...}` and `{"type":
"file", "path": ...}`; a future git plugin can contribute `{"type":
"commit", "sha": ...}` to the same list without a schema change.
`folders_created`/`files_created` remain available as `@property` methods
computed from `artifacts` — Mission Brief 004's brief asked for those
fields by name, and every existing caller (`cli.py`, tests) keeps working
unchanged; `artifacts` is now the actual source of truth underneath them.

## Options considered and rejected

- **Do nothing — the current design "works today."** True, but the
  question asked wasn't "does this work today," it was "would this design
  survive the growth this project has already stated as its goal." Both
  problems above are cheap to fix now (an afternoon) and expensive to fix
  later (a migration touching every existing row, plus every caller of
  the methods being removed).
- **Add a real query language / filter DSL.** Rejected as over-engineering
  for what's actually needed — a plain dataclass with optional fields
  covers every query shape named in this review and in
  `MEMORY_ARCHITECTURE.md` §12 without introducing a parser, a new
  dependency, or a new concept to learn.
- **Normalize `artifacts` into its own table now.** Rejected for the same
  reason ADR-0007 rejected normalizing `execution_plan`/`execution_result`
  originally — nothing queries *into* artifacts yet ("find every mission
  that created file X" isn't a requirement today). The generic-list shape
  is what makes that normalization possible later without a rewrite, not
  a reason to do it now.

## Consequences

- `MemoryStore` implementers (today: `SQLiteMemoryStore`; tomorrow:
  whatever Layer 6 or a test double needs) implement five methods, not a
  growing list.
- Every future capability can report what it produced without a Memory
  schema change, as long as it fits the `{"type": ..., ...}` shape —
  which is deliberately unconstrained beyond having a `type` key.
- `MissionQuery`/`artifacts` are both additive-only from here — this ADR
  is the pattern to repeat, not a one-time fix: the next time a query or
  output-shape need doesn't fit, add a field, don't add a method or a
  column.
- Deep `OFFSET`-based pagination is O(offset) in SQLite — acceptable for
  a one-time background scan (Layer 5's eventual indexer), named as a
  known limitation rather than solved, since nothing today needs it
  solved.
