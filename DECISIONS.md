# Decisions Log

Running log of architecture and process decisions. Full ADR text lives in
`docs/adr/`; this is the quick-reference summary so a new session (or a
new machine) doesn't have to re-derive context by reading every ADR.

## ADR-0001: Core engine in Python
Chosen over TypeScript/Node and C#/.NET for AI/ML ecosystem maturity and
iteration speed. Consequence: the Desktop UI is necessarily a separate
process/language from the engine, talking over local HTTP/WS — already
the right call for replaceability.

## ADR-0002: "Hermes integration" = local LLM via Ollama
Confirmed by the founder: Hermes is the local-model counterpart to the
cloud ChatGPT integration, served locally via Ollama, behind the same
`ModelProvider` interface as ChatGPT. Still open: which specific Hermes
checkpoint/size to default to.

## ADR-0003: Everything is a plugin behind one contract
Single `Plugin` base contract (manifest + `invoke()`) implemented by
every model provider, capability, and voice adapter. Orchestrator and
Model Router only ever talk to plugins through the registry.

## ADR-0004: Local-first memory, no cloud sync in Founder Edition
SQLite + local embeddings. No multi-device sync in v0.1 — acceptable
under "build for one founder first."

## ADR-0005: Executor/Plugin permission-relay (Mission Brief 002)
`LocalExecutor.execute()` checks permission on its own grant key
(`executor.name`, `action.name`), distinct from the Orchestrator's
existing check on (`plugin.name`, `capability`) — a `Plugin` adapter
relays an already-obtained human approval down to the Executor's key
rather than the Executor skipping its own check. See
`docs/adr/0005-executor-permission-relay.md`.

## ADR-0006: Composite-action relay (Mission Brief 003)
Extends ADR-0005 one layer deeper: `WorkspaceBootstrapAction` relays its
own already-obtained grant to each sub-action it invokes
(`create_folder`, `write_file`), then calls them through the real
`LocalExecutor.execute()` — never by calling their `run()` directly. See
`docs/adr/0006-composite-action-relay.md`.

## ADR-0007: SQLite Memory backend (Mission Brief 004)
`SQLiteMemoryStore` uses stdlib `sqlite3` directly (not `sqlmodel`, an
already-declared but unused dependency) and JSON text columns for
structured fields nothing queries into yet, rather than a normalized
multi-table schema — "readable schema first," per the brief. See
`docs/adr/0007-sqlite-memory-backend.md`.

## ADR-0008: Memory scale review (Mission Brief 004.1)
Reviewed Memory against "millions of missions, thousands of plugins,
hundreds of capabilities, years of history." Two things didn't hold up:
`MemoryStore`'s query surface (fixed with one `query_missions(MissionQuery)`
method instead of a method per filter) and `MissionRecord`'s
filesystem-specific `folders_created`/`files_created` columns (fixed with
a generic `artifacts` list). `Memory`'s public API unchanged. See
`docs/adr/0008-memory-scale-review.md`.

## Mission Brief 001 (2026-07-23): First end-to-end mission
Implemented a real vertical slice — text in, real filesystem write out,
real Permission System gate — using only existing scaffold modules
(`Orchestrator`, `PermissionSystem`, `Mission`) plus one new plugin
(`FilesystemPlugin`) and one new entrypoint (`cli.py`). Found and fixed
two real bugs in code that had previously passed its own unit tests:
`PermissionSystem`'s `ONCE` grant was never consumed (one approval
silently authorized every future call), and the Mission state machine
illegally skipped `EXECUTING` when no approval was needed. Full writeup:
`docs/MISSION_BRIEF_001.md`.

## Mission Brief 001.5 (2026-07-23): Health check + workspace bootstrap
Confirmed all Mission Brief 001 assets intact, no drift from documented
structure. Found: no git repository existed despite two prior deliveries
of the codebase, and the project's canonical location (`D:\MasterAgent`)
could not be verified or written to from any session so far, because the
Claude desktop device bridge has not been connected. This bootstrap
initializes git in the cloud staging copy and adds the top-level runtime
folders, founder documentation set, and Obsidian vault requested in the
brief — all still pending a real transfer to `D:\MasterAgent`. See
`START_HERE.md` for the exact steps to complete that transfer, and
`docs/MISSION_BRIEF_001.md` §"What's production-ready vs. still a stub"
for what's real versus scaffolded in the code itself.

## Mission Briefs 002 - 003.5 (2026-07-23): Executor, composition, first
## real mission, foundation freeze
Summarized here for continuity; full detail in each `docs/MISSION_BRIEF_*.md`.
002 generalized execution behind `LocalExecutor` + the `Action` Contract
(`create_folder` refactored onto it, zero regression). 003 added
`write_file` and the first composite Action, `WorkspaceBootstrapAction`
(ADR-0006). 003.1 connected real conversation ("Create a Python project
called Demo.") to that composite through the full stack, with zero
changes below the Planner — found and fixed one real bug
(`InvocationResult` dropping execution time). 003.5 froze the project's
permanent engineering documentation (this file's own staleness between
001.5 and 004 is itself an example of what that freeze was meant to
prevent going forward) before Memory/Voice/Model Routing began.

## Mission Brief 004 (2026-07-23): The Memory System
Designed a six-layer memory model (`MEMORY_ARCHITECTURE.md`) before
writing any code, per the brief's explicit gate. Implemented Layers 1-3:
Conversation Memory (in-process), Mission Memory (the pre-existing
`Mission` object, formalized rather than duplicated), and Persistent
Memory (`SQLiteMemoryStore`, ADR-0007). Layers 4-6 are interfaces only
(`memory/future.py`). `MasterAgentSession` now persists every mission
automatically at every terminal state (no manual save calls anywhere in
the CLI), and answers two real conversational queries ("What was my last
mission?", "Show my recent missions.") — verified across a real process
restart. `MissionManager` remains unwired into the live path; that's
scoped into the real-Planner Miracle next. Full detail:
`docs/MISSION_BRIEF_004.md`.

## Mission Brief 004.1 (2026-07-23): Memory System scale review
A standing review question ("would this design survive millions of
missions, thousands of plugins, hundreds of capabilities, years of
history?") was applied to Memory immediately after it shipped, before
anything else got built on top of it. Two real problems found and fixed
(ADR-0008): the query interface would have grown a method per future
filter need, and the persisted schema hardcoded a filesystem-specific
assumption about mission output. Both fixed additively — `Memory`'s
public API and every existing caller unchanged. One further finding
(`LocalExecutor._log` is unbounded) was named but deliberately not fixed,
since it predates this Miracle and wasn't part of what was asked. Full
detail: `docs/MISSION_BRIEF_004_1.md`.

## Open decisions (not yet locked)
- Desktop UI stack: recommended pywebview + local FastAPI server for
  speed-to-ship; Tauri/Electron not ruled out, just not chosen yet.
- Exact Hermes checkpoint/quantization for the founder's hardware.
- Plugin distribution model beyond Founder Edition (marketplace/installer)
  — explicitly out of scope for v0.1; top-level `plugins/` folder exists
  as a placeholder for when this is designed.
- Commit message / tag naming: this bootstrap used "Miracle 001" verbatim
  as instructed for the initial commit and tag (`v0.1.0-miracle-001`).
  If that was meant to read "Mission 001," it's a one-line `git commit
  --amend` / re-tag away from being fixed — flagging here rather than
  silently changing wording you may have chosen deliberately (it does
  echo the Kalpavriksha "wish-granting" theme).
