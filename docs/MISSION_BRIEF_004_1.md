# Mission Brief 004.1 — Memory System: Scale Review & Extensibility Hardening

Status: Implemented (2026-07-23)

## Objective

Immediately after Mission Brief 004 shipped, a standing review question
was raised: before finalizing any architecture/data model/API/schema,
would this design still be kept if Master Agent grows to millions of
missions, thousands of plugins, hundreds of capabilities, and years of
accumulated history — judged against three tests (extend without
modification, replace without affecting the rest of the system,
understandable six months from now)? This brief is that review, applied
to the Memory System just shipped, plus a pass over the modules around
it, with concrete fixes for what didn't hold up.

## What the review found

**Held up, no change (with reasoning re-affirmed, not just asserted):**
SQLite as the Layer 3 backend; JSON columns for structured-but-unqueried
fields (ADR-0007); the single-connection-per-store design;
`PermissionSystem`'s grant scan (bounded by distinct capabilities in use,
not mission volume); `PluginRegistry`'s hardcoded registration (already
an accepted Founder Edition tradeoff, additive to change later).

**Did not hold up, fixed:**

1. **`MemoryStore`'s query surface** (`recent_missions`,
   `missions_by_status`) would have grown one method per future filter
   need — a real problem at "hundreds of capabilities" scale. Replaced
   with a single `query_missions(query: MissionQuery)`, where new filters
   are new `MissionQuery` fields, never new interface methods. `Memory`'s
   public API is unchanged; this is entirely an internal contract
   improvement.
2. **`MissionRecord`'s `folders_created`/`files_created` columns**
   hardcoded a filesystem-specific assumption that won't generalize to
   git/shell/browser/etc. capabilities. Replaced with a generic
   `artifacts: list[dict]` field (`{"type": ..., ...}`);
   `folders_created`/`files_created` remain as computed `@property`
   views, so Mission Brief 004's literal brief requirement and every
   existing caller keep working unchanged.

Full reasoning, options considered and rejected, and consequences:
`docs/adr/0008-memory-scale-review.md`.

**Found, not fixed (out of scope, named honestly):**
`LocalExecutor._log` (`executor/executor.py`, Mission Brief 002) is an
unbounded in-memory list — fine for a CLI process, would leak memory in a
long-running daemon. Predates this Miracle; flagged on `ROADMAP.md`
rather than fixed here, since touching Executor wasn't part of what was
asked and the fix is small enough to do properly whenever Executor is
next touched deliberately.

## Files changed

- `src/master_agent/memory/store.py` — `MissionQuery` added;
  `MissionRecord.folders_created`/`.files_created` are now `@property`
  views over a new `artifacts` field (was: two stored list fields);
  `MemoryStore.recent_missions`/`.missions_by_status` replaced with
  `.query_missions`; schema's `folders_created`/`files_created` columns
  replaced with one `artifacts` column; `idx_missions_status` replaced
  with a composite `(status, completed_at)` index.
- `src/master_agent/memory/memory.py` — internals now build `MissionQuery`
  and call `query_missions`; public method signatures unchanged.
- `src/master_agent/cli.py` — `_extract_created` renamed
  `_extract_artifacts`, now returns a generic artifact list instead of a
  (folders, files) tuple; `_build_mission_record` updated accordingly.
- `docs/adr/0008-memory-scale-review.md` (new) — full review, options
  considered, decision, consequences.
- `MEMORY_ARCHITECTURE.md` — §6a/§6b added (why `MissionQuery`, why
  `artifacts`); §5 schema updated; §8's query table updated; §11 gained
  the `LocalExecutor._log` finding; §12 updated for `offset`-based
  pagination.
- `tests/test_memory.py` — `_record()` fixture updated; three tests
  renamed/updated to use `MissionQuery`/`query_missions`; two new tests
  (`offset` pagination, `folders_created`/`files_created` deriving
  correctly from `artifacts`).
- `ROADMAP.md` — new Future item for `LocalExecutor._log`.

No changes to `tests/test_cli_session.py` — every assertion there reads
`record.folders_created`/`.files_created`, which still work unchanged as
properties; this is exactly the "replace without affecting the rest of
the system" test passing in practice, not just in principle.

## Tests

2 new tests (offset pagination, artifacts-to-properties derivation), 3
renamed/updated in place (query_missions instead of the two removed
methods). **126 passed** (up from 124; zero regressions across the full
suite, including everything Mission Brief 004 and every prior Miracle
added).

## Test results

```
126 passed in 0.35s
```

## Ruff results

```
All checks passed!
```

## Live verification

Ran a real process creating and completing a Python project mission,
then read `session.memory.last_mission()` directly and confirmed
`.artifacts` contains the generic `{"type": "folder"/"file", "path":
...}` entries, and that `.folders_created`/`.files_created` (still used
by `cli.py`'s existing completion-message code, unrelated to this
Miracle) derive correctly from them — 5 folders, 4 files, matching Mission
Brief 004's original live-verification numbers exactly.

## Recommendation for Miracle 005

Unchanged from Mission Brief 004's recommendation: the real Planner is
next, and now has a query contract (`MissionQuery`) already shaped to
take whatever filters it turns out to need as simple field additions,
rather than becoming the first consumer to trigger another interface
redesign. Also worth a look whenever Executor is next touched: fold
`LocalExecutor._log` into `Memory`, or at minimum bound it, per the
finding in `MEMORY_ARCHITECTURE.md` §11.
