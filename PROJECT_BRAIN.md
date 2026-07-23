# Project Brain

**If you only read one file in this repo, read this one.** It's the
orientation index — where things stand, and where to go for detail. Meant
to be read cold by a new session, a new machine, or a future you who's
forgotten the details.

## What this is

Master Agent: an AI orchestration platform that turns a stated intention
into a completed, verified outcome, instead of the human manually
managing multiple AI tools. See `VISION.md` for mission/vision/values/
long-term goals stated formally, `WHY.md` for the origin-story version,
`MANIFESTO.md` for the values as a statement, and
`ENGINEERING_PRINCIPLES.md`/`PRODUCT_PRINCIPLES.md`/
`ARCHITECTURE_PRINCIPLES.md` for what those values require in practice —
how we build, how it should feel, and why it's shaped the way it is,
respectively.

## Where things stand right now (2026-07-23)

- **The architecture is designed and documented**, not just implemented
  ad hoc: `ARCHITECTURE.md` is the system design; `docs/adr/` explains
  *why* each major choice was made.
- **Mission Brief 001 is real and working**: one full mission
  ("create a folder called Demo") runs end to end through the actual
  Orchestrator, Permission System, and Mission state machine — not a
  mock. Full detail and an honest "what's production-ready vs. still a
  stub" accounting: `docs/MISSION_BRIEF_001.md`.
- **Mission Brief 001.5** added the founder-workspace scaffolding — top-
  level runtime folders, this documentation set, the Obsidian vault, git —
  around the working code, without touching the code itself.
- **Mission Brief 002 generalized execution**: a `LocalExecutor` +
  `Action` contract now sits between the Orchestrator and the filesystem,
  so every future local capability (read/rename/delete/copy/move file,
  run PowerShell/CMD, git, VS Code, Obsidian, ...) plugs into the same
  validated, permission-gated, logged execution path instead of being a
  one-off special case. `create_folder` was refactored onto it with zero
  functional regression (same transcript, same tests passing). Full
  detail: `docs/MISSION_BRIEF_002.md`.
- **Mission Brief 003 proved composition**: added `write_file` (a second
  filesystem primitive) and `WorkspaceBootstrapAction` (a composite —
  root folder + subfolders + seed files, generically parameterized, not
  a hardcoded script) that composes `create_folder`/`write_file` calls
  *through* the real `LocalExecutor.execute()` path, never by calling
  their `run()` methods directly — every sub-step stays validated,
  permission-gated (via a relayed grant, extending ADR-0005's pattern —
  see ADR-0006), and logged. No transactional rollback on partial
  failure, flagged as known debt rather than silently accepted. Full
  detail: `docs/MISSION_BRIEF_003.md`.
- **Mission Brief 003.1 connected conversation to that capability**:
  `cli.py`'s rule-based Intent Parser now recognizes "create a project"
  phrasing (with an optional type — "Python", or a sensible generic
  default) alongside the original "create a folder" phrasing, and
  `build_plan()` (still `cli.py`'s stand-in for the real Planner) turns a
  recognized project intent into a single `workspace_bootstrap` Step. The
  Orchestrator, Permission System, and approval-relay code are entirely
  unchanged — proof Mission Brief 003's composite-action design really
  does let a new mission reach it without touching anything below the
  Planner. Full detail: `docs/MISSION_BRIEF_003_1.md`.
- **What's still a stub, unchanged:** the *real* Planner (model-driven,
  not `cli.py`'s regex stand-in), the `MissionManager` class specifically
  (multi-mission lifecycle — mission *persistence* itself is real as of
  Mission Brief 004, just not through this class yet), Model Router
  wiring to live providers, Memory Layers 4-6 (Knowledge/Vector/Cloud
  Sync — interfaces only), Voice I/O, Desktop UI, and every local action
  besides `create_folder`/`write_file`/`workspace_bootstrap` (the
  Executor now supports adding them cheaply, but none are built yet). See
  `ROADMAP.md` for what's next and in what order.
- **Mission Brief 003.5 froze the project's permanent engineering
  documentation** before Memory, Voice, or Model Routing begin — zero
  code changes, zero runtime behavior changes. Seven documents, some new
  (`ENGINEERING_PRINCIPLES.md`, `MIRACLE_LEDGER.md`, `VISION.md`,
  `ARCHITECTURE_PRINCIPLES.md`, `FOUNDER_PLAYBOOK.md`), some updated
  (`PRODUCT_PRINCIPLES.md`, `ROADMAP.md`) — see the table below for what
  each one is for.
- **Mission Brief 004 built the Memory System** — a six-layer design
  (`MEMORY_ARCHITECTURE.md`), of which Layers 1-3 are real: Conversation
  Memory (in-process), Mission Memory (the existing `Mission` object,
  formalized), and Persistent Memory (`SQLiteMemoryStore`, the first real
  implementation of the `MemoryStore` interface ADR-0004 sketched).
  Layers 4-6 are interfaces only (`memory/future.py`), not implemented.
  `MasterAgentSession` now persists every mission's outcome automatically
  at every terminal state (completed/failed/cancelled) — no manual save
  call anywhere in the CLI — and answers two real conversational
  questions: "What was my last mission?" and "Show my recent missions."
  Verified across a real process restart (a fresh `python -m
  master_agent.cli` process reads mission history a prior process wrote).
  Full detail: `docs/MISSION_BRIEF_004.md`.

## Where to go for what

| Question | File |
|---|---|
| Why does this exist? | `VISION.md` (formal), `WHY.md` (origin story) |
| What do we value / what tradeoffs does that force? | `MANIFESTO.md` |
| How do those values shape how we build? | `ENGINEERING_PRINCIPLES.md` |
| How do those values shape how the product should feel? | `PRODUCT_PRINCIPLES.md` |
| How is the system designed, and why is it shaped that way? | `ARCHITECTURE.md` (what), `ARCHITECTURE_PRINCIPLES.md` (why) |
| Why was each design choice made? | `docs/adr/*.md`, summarized in `DECISIONS.md` |
| What's actually built and working right now? | `docs/MISSION_BRIEF_001.md`, `docs/MISSION_BRIEF_002.md`, `docs/MISSION_BRIEF_003.md`, `docs/MISSION_BRIEF_003_1.md`, `docs/MISSION_BRIEF_004.md` |
| What shipped when, at what commit/tag, with how many passing tests? | `MIRACLE_LEDGER.md` |
| How does a new local capability plug in? | `ARCHITECTURE.md` §4.7, `docs/MISSION_BRIEF_002.md` |
| How does a *composite* mission (several actions together) plug in? | `docs/MISSION_BRIEF_003.md`, `docs/adr/0006-composite-action-relay.md` |
| How does typed/spoken conversation become a mission? | `ARCHITECTURE.md` §4.1-4.2, `docs/MISSION_BRIEF_003_1.md` |
| How does mission history get remembered, and how do I query it? | `MEMORY_ARCHITECTURE.md`, `docs/MISSION_BRIEF_004.md`, `docs/adr/0007-sqlite-memory-backend.md` |
| What's next, and in what order? | `ROADMAP.md` |
| How should a new Miracle actually be built, reviewed, tested, shipped? | `FOUNDER_PLAYBOOK.md` |
| What's known/unknown about the founder and constraints? | `FOUNDER_CONTEXT.md` |
| How do I set this up on a new machine? | `START_HERE.md` |
| Is the deadline realistic? | `docs/TIMELINE_RISK.md` |
| Raw, unstructured notes / journal / research | `obsidian/` vault |

## Standing constraints worth repeating

- **Local-first architecture, cloud enhancement when beneficial.**
- **Human approval before important actions** — non-negotiable, and the
  approval UX itself has to stay simple (see the tension named in
  `MANIFESTO.md`).
- **Reuse existing scaffolding; don't refactor architecture without being
  asked; don't delete without approval.** Every mission brief so far has
  honored this — check `DECISIONS.md` before assuming a module needs
  rebuilding rather than reusing.
- **"Minimum Manual Work. Maximum Agent Work."** The recurring philosophy
  across every brief — the agent does the execution, the founder
  approves and directs.
