# Roadmap

Status: Updated 2026-07-23 — Miracle 003.5, Foundation Freeze

Living document — update it as Miracles complete or plans change. This
is the founder-facing view; `docs/TIMELINE_RISK.md` has the detailed
reasoning behind the Founder Edition pacing below;
`MIRACLE_LEDGER.md` has the verifiable, dated history of everything
marked Completed here.

## Completed

| Miracle | What shipped |
|---|---|
| **001** — First end-to-end mission | Real conversation → real filesystem write ("create a folder") through the actual Orchestrator, Permission System, Mission state machine. Two real bugs found and fixed. |
| **001.5** — Health check + Founder Workspace Bootstrap | Founder-workspace scaffolding (runtime folders, docs, Obsidian vault, git history) around the working code. No functional change. |
| **002** — Generic Local Executor | `LocalExecutor` + the `Action` Contract — every future local capability plugs into one validated, permission-gated, logged execution path. `create_folder` refactored onto it, zero regression. |
| **003** — Workspace Bootstrap Action | `write_file` (second primitive) + `WorkspaceBootstrapAction` (composite, built entirely through the real Executor — no bypass). Reachable only via direct `invoke()` at this point. |
| **003.1** — First Real Mission | Real conversation ("Create a Python project called Demo.") reaches `workspace_bootstrap`, through the full stack, with zero changes to the Orchestrator/PermissionSystem/composite-relay logic. |
| **003.5** — Foundation Freeze | This document set: `ENGINEERING_PRINCIPLES.md`, `MIRACLE_LEDGER.md`, `VISION.md`, `PRODUCT_PRINCIPLES.md` (updated), `ARCHITECTURE_PRINCIPLES.md`, this file, `FOUNDER_PLAYBOOK.md`. Zero code changes. |
| **004** — The Memory System | `memory/` gets a real six-layer design (`MEMORY_ARCHITECTURE.md`), Layers 1-3 implemented: Conversation Memory, Mission Memory (existing `Mission`, formalized), Persistent Memory (`SQLiteMemoryStore`, first real `MemoryStore` implementation). `MasterAgentSession` persists every mission automatically at every terminal state; two conversational queries ("What was my last mission?", "Show my recent missions.") work end to end, verified across a real process restart. Layers 4-6 are interfaces only. |
| **004.1** — Memory Scale Review | Reviewed Memory (and the modules around it) against a millions-of-missions/thousands-of-plugins/years-of-history test. Replaced `MemoryStore`'s two-method query surface with one `query_missions(MissionQuery)` (new filters = new dataclass fields, never new methods); replaced `folders_created`/`files_created` columns with a generic `artifacts` list (a future git/shell/browser capability can contribute its own shape without a schema change). `Memory`'s public API unchanged throughout. Key design decision: ADR-0008. |
| **005** — Local Execution Expansion | `FilesystemPlugin` grew from 3 to 14 capabilities: eleven new primitive Actions (read/list/search/exists-checks, append, rename/copy/move, delete-file/delete-folder), registered declaratively (`FILESYSTEM_CAPABILITIES.md`, written before any code). New `PermissionCategory` axis alongside `RiskTier`, plus a real mechanism change — `always_for_capability` grants can never satisfy an `irreversible` check (ADR-0009). `cli.py`'s intent parser generalized to a single `ParsedActionIntent` + table-driven `_INTENT_PATTERNS`, reaching all six of the brief's conversation examples plus Move. 234 tests passing, zero regressions. |

Full detail on each: `docs/MISSION_BRIEF_001.md` through
`docs/MISSION_BRIEF_005.md`, and `MIRACLE_LEDGER.md` for the
tag/commit/test-count record.

## In progress

Nothing is currently in progress — Miracle 005 is a completed, shipped
increment. The next Miracle to start is the first item under Planned,
below.

## Planned — next up

In the order the accumulated recommendations across Mission Briefs
002/003/003.1/004/004.1/005 converge on:

1. **The real Planner**, replacing `cli.py`'s regex-based
   `parse_intent()`/`build_plan()` stand-in with an actual model call
   through the Model Router (Hermes first — no API key needed, keeps
   testing fast). This is the point at which `planner/planner.py` stops
   raising `NotImplementedError`, and the natural point to finally wire
   `MissionManager` into the live path, calling `Memory.persist_mission()`
   the way `MasterAgentSession._remember()` does today (see
   `MEMORY_ARCHITECTURE.md` §11-§12). Now has real proving ground to
   generalize against: fourteen capabilities and nine distinct
   conversational shapes as of Mission Brief 005, not three and two.
   Verify against the full existing `test_cli_session.py` suite (100+
   assertions deep now) before intent recognition changes shape again —
   that suite is the regression contract this change must not break.
2. **Planner context from Memory** — once the real Planner exists, feed it
   `Memory.recent_missions()`/`Memory.successful_missions()` as context
   ("have I done something like this before"). This is Miracle 004's
   whole reason for existing, actually being used by something other than
   a direct conversational query.
3. **Conversational phrasing for `file_exists`/`directory_exists`/
   `append_file`** — real, tested capabilities as of Mission Brief 005
   with no `cli.py` intent shape yet. Small and additive (one more
   `_INTENT_PATTERNS` entry each) whenever there's a concrete need, or
   naturally falls out once the real Planner replaces the regex stand-in
   entirely.
4. **A second real project template** (e.g. `node`) — the first test of
   whether `cli.py`'s `_PROJECT_TEMPLATES` dict-extension pattern
   actually generalizes, the way Miracle 003 tested whether the `Action`
   Contract generalized past one example.
5. **A third Executor-relay instance** (a new *non-filesystem*
   local-action plugin, e.g. git operations, or a third composite
   action) — settles whether the base-class extraction flagged as debt
   in ADR-0005/ADR-0006 is worth building yet. Mission Brief 005 added
   eleven more Actions using the *existing* relay pattern (not a new
   instance of the open question — same Plugin/Executor boundary,
   same `FilesystemPlugin`), so this is still "two examples," not three.

## Founder Edition — reverse-plan checkpoints

From `docs/TIMELINE_RISK.md`, reproduced here so it's visible without
opening a second file. Treat these as a starting point to argue with, not
a locked commitment. Target: 2026-08-05.

1. **Model Router + both providers** answering a basic prompt.
2. **Planner + Mission Manager** state machine, Permission System gate —
   partially proven (Miracles 001-003.1 proved the Permission System +
   Mission state machine + Executor work end to end for hand-built
   plans); the remaining piece is the Planner itself generating a plan
   from a model call instead of `cli.py`'s regex stand-in.
3. **Voice I/O**, wired to the Intent Layer and Reporter.
4. **Desktop UI shell** talking to the engine over HTTP/WS.
5. **Integration pass** on one golden-path mission, no new features in
   the final ~72 hours before the deadline.

## Future — post–Founder Edition, toward Version 1

Not scheduled, not estimated — named here so they're not forgotten, and
so nothing gets built prematurely against them:

- **Non-filesystem local actions** from `ARCHITECTURE.md`'s original
  list: run PowerShell/CMD, git operations, VS Code operations, Obsidian
  operations — each a candidate `Action` or composite, per
  `ARCHITECTURE_PRINCIPLES.md`'s extension strategy. (The filesystem
  actions on that original list — read/rename/delete/copy/move — shipped
  in Mission Brief 005; `PermissionCategory.SYSTEM`, reserved but unused
  as of that Miracle, is likely the right category for the first of
  these non-filesystem ones.)
- **A live third `ModelProvider`** (e.g. Claude via API) — the Model
  Router was designed so this is one new plugin, not a router rewrite;
  Version 1 is a reasonable point to actually prove that claim.
- **Memory Layer 5, Vector Memory** (`memory/future.py`'s `VectorMemory`
  interface, unimplemented) — local-embedding semantic recall over Layer
  3's mission history, now that Mission Brief 004 gives it real history
  to search. Layer 4 (Knowledge Memory) and Layer 6 (Cloud Sync,
  explicitly opt-in) are the same story — interfaces exist
  (`MEMORY_ARCHITECTURE.md` §12), implementations don't yet.
- **Desktop UI beyond a shell** — richer mission history views, inline
  approval UX refinements informed by real usage, not speculative design.
- **Bound or persist `LocalExecutor._log`** (`executor/executor.py`) —
  found during Miracle 004.1's scale review: it's an unbounded in-memory
  list, fine for a CLI process that exits after a session, would leak
  memory in a long-running daemon. Small fix (cap it, or fold it into
  `Memory` now that a durable execution-history home exists) — not urgent
  today, worth doing before Master Agent runs unattended for long
  stretches. See `MEMORY_ARCHITECTURE.md` §11.

## Explicitly not on this roadmap yet

Plugin marketplace/installer, multi-device memory sync, non-Windows
support, team/multi-user features — all deliberately deferred per "build
for one founder first" (`PRODUCT_PRINCIPLES.md`). Don't schedule work
against these without a concrete trigger for why they're needed now.
