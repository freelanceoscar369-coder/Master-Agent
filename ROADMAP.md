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

Full detail on each: `docs/MISSION_BRIEF_001.md` through
`docs/MISSION_BRIEF_003_1.md`, and `MIRACLE_LEDGER.md` for the
tag/commit/test-count record.

## In progress

Nothing is currently in progress — Miracle 003.5 is a deliberate pause
point ("Foundation Freeze") before the next capability work begins. The
next Miracle to start is the first item under Planned, below.

## Planned — next up

In the order the accumulated recommendations across Mission Briefs
002/003/003.1 converge on:

1. **A second real project template** (e.g. `node`) — the first test of
   whether `cli.py`'s `_PROJECT_TEMPLATES` dict-extension pattern
   actually generalizes, the way Miracle 003 tested whether the `Action`
   Contract generalized past one example. Small, cheap, and answers a
   real open question before building more on top of an unproven
   pattern.
2. **A third Executor-relay instance** (a new local-action plugin, e.g.
   git operations, or a third composite action) — settles whether the
   base-class extraction flagged as debt in ADR-0005/ADR-0006 is worth
   building yet. Two examples said "not yet"; a third might say "yes."
3. **The real Planner**, replacing `cli.py`'s regex-based
   `parse_intent()`/`build_plan()` stand-in with an actual model call
   through the Model Router (Hermes first — no API key needed, keeps
   testing fast). This is the point at which `planner/planner.py` stops
   raising `NotImplementedError`. Verify against the full existing
   `test_cli_session.py` suite before intent recognition generalizes
   further — that suite is the regression contract this change must not
   break.
4. **Memory that matters.** Wire `SQLiteMemoryStore` for real; persist
   `Mission.outcome` across restarts; recall the last N missions as
   Planner context. Directly enables "trust through transparency"
   (`PRODUCT_PRINCIPLES.md`) — a mission history that survives a
   restart is what makes a track record inspectable.

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

- **Every remaining local action** from `ARCHITECTURE.md`'s original
  list: read/rename/delete/copy/move file, run PowerShell/CMD, git
  operations, VS Code operations, Obsidian operations — each a candidate
  `Action` or composite, per `ARCHITECTURE_PRINCIPLES.md`'s extension
  strategy.
- **A live third `ModelProvider`** (e.g. Claude via API) — the Model
  Router was designed so this is one new plugin, not a router rewrite;
  Version 1 is a reasonable point to actually prove that claim.
- **Local Memory's semantic recall** (the embedding-index half of
  `ARCHITECTURE.md` §4.8) — SQLite-only memory (Planned, above) is the
  prerequisite; semantic recall over mission history is the natural
  follow-up once there's real history to search.
- **Desktop UI beyond a shell** — richer mission history views, inline
  approval UX refinements informed by real usage, not speculative design.

## Explicitly not on this roadmap yet

Plugin marketplace/installer, multi-device memory sync, non-Windows
support, team/multi-user features — all deliberately deferred per "build
for one founder first" (`PRODUCT_PRINCIPLES.md`). Don't schedule work
against these without a concrete trigger for why they're needed now.
