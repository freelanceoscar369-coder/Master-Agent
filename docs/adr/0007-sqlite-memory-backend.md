# ADR-0007: SQLite Memory backend — stdlib `sqlite3`, JSON columns over normalization

Status: Accepted (2026-07-23) — Miracle 004, The Memory System

## Context

Miracle 004 needed a real implementation behind the `MemoryStore`
interface ADR-0004 sketched (and left as `NotImplementedError`). Two
choices needed making before writing `SQLiteMemoryStore`: which library
talks to SQLite, and how normalized the schema should be. `pyproject.toml`
already lists `sqlmodel>=0.0.21` as a dependency (from the project's
original scaffolding), which made "use sqlmodel" the path of least
resistance — but "path of least resistance" isn't the same as "right
call," so this got decided deliberately rather than defaulted into.

## Decision

**Library:** use the Python standard library's `sqlite3` module directly,
not `sqlmodel`/SQLAlchemy.

**Schema:** one `missions` table with plain columns for the fields that
are actually queried today (`mission_id`, `status`, `completed_at`) and
JSON text columns for structured data nothing queries *into* yet
(`execution_plan`, `execution_result`, `folders_created`, `files_created`,
`errors`, `outcome`) — see `MEMORY_ARCHITECTURE.md` §5 for the full DDL.

## Options considered

1. **sqlmodel/SQLAlchemy ORM.** Rejected for this Miracle: the query
   surface required is five simple, literal lookups (§8 of
   `MEMORY_ARCHITECTURE.md`) — an ORM's value shows up with complex
   joins, migrations, and relationship management, none of which apply
   yet. Pulling in an ORM to write five `SELECT` statements is the kind
   of premature complexity the brief explicitly warned against ("Do not
   optimize prematurely. Readable schema first."). `sqlmodel` stays a
   declared dependency in case a future Miracle's needs genuinely justify
   it — this decision doesn't remove it, just doesn't reach for it here.
2. **Normalized schema** (separate tables for `execution_plan` steps,
   `files_created`, `folders_created`, `errors`). Rejected for the same
   reason: normalization pays off when something needs to query *inside*
   those structures ("find every mission that touched file X"). Nothing
   does yet. `MemoryStore`'s interface hides this choice entirely — if a
   future Miracle's query needs force normalization, that's a
   `SQLiteMemoryStore`-internal migration, not an interface change, and
   not a change anything outside `memory/store.py` needs to know about.
3. **A different storage engine entirely** (JSON file, Postgres). Out of
   scope — ADR-0004 already decided SQLite for Founder Edition; this ADR
   is about how to talk to it, not whether to use it.

## Consequences

- Zero new runtime dependencies for Memory (`sqlite3` ships with Python).
- The schema is trivially readable by anyone who knows SQL, without
  needing to know an ORM's query-building API.
- If normalization becomes necessary later, it's contained inside
  `SQLiteMemoryStore` — `Memory`, `MasterAgentSession`, and every test
  that depends on the `Memory` facade rather than `SQLiteMemoryStore`
  directly are unaffected.
- `sqlmodel` remains an unused-but-declared dependency after this
  Miracle — worth revisiting (removing it, or finally using it) the next
  time `pyproject.toml`'s dependency list gets a deliberate pass, but not
  blocking for this Miracle.
