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
  Sync — interfaces only), Voice I/O, Desktop UI, and non-filesystem local
  actions (PowerShell/CMD, git, VS Code, Obsidian — the Executor supports
  adding them cheaply, per Mission Brief 005 proving the pattern at real
  scale, but none are built yet). See `ROADMAP.md` for what's next and in
  what order.
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
- **Mission Brief 004.1 stress-tested that design against long-term
  scale** (millions of missions, thousands of plugins, hundreds of
  capabilities, years of history) before it went further unreviewed.
  Replaced `MemoryStore`'s two query methods with one
  `query_missions(MissionQuery)` — new filters become dataclass fields,
  never new interface methods — and replaced the filesystem-specific
  `folders_created`/`files_created` columns with a generic `artifacts`
  list, so a future capability that isn't folder/file-shaped (a git
  commit, a shell command's output) doesn't need a schema change.
  `Memory`'s public API and every existing caller are unchanged. Key
  decision: ADR-0008. Full detail: `docs/MISSION_BRIEF_004_1.md`.
- **Mission Brief 025 gave Kalpavriksha persistent memory.** It now
  survives a kill: submit work, run partway, kill the process, restart,
  and it resumes exactly where it stopped — demonstrated live, with each
  task executing exactly once across both processes and audit history
  intact. New `persistence/` package: bus-subscribed event log,
  versioned+checksummed snapshots, event replay, and one-call
  `recover()`. Interrupted tasks are **quarantined, never re-run** (their
  side effects are unknown, and deciding to retry is the Brain's call per
  Constitution §11). **⚠️ Contains three additive changes to frozen
  components** — a non-publishing `restore_objective()`, plus `depends_on`
  and `health` added to two event payloads — each required by a
  deliverable, each isolated and reversible, all recorded in ADR-0015 as
  **Proposed and awaiting ratification**. Also fixed a real MB024 bug it
  exposed (`max_cycles` was absolute, so a restored runtime silently did
  nothing). 205 new tests, 789 passing, zero regressions. Full detail:
  `docs/MISSION_BRIEF_025.md`, `PERSISTENCE_ARCHITECTURE.md`.
- **Mission Brief 026 built the Founder Dashboard** — the first
  operational window into the living system. Read-only by construction: a
  frozen read model sits between published contracts and rendering, so
  panels hold nothing mutable and *cannot* affect what they observe (a
  test renders 25 frames and asserts the system is byte-identical
  afterwards). Nine panels — runtime, mission, executives, capabilities,
  audit, persistence, system health, founder state — updating live off the
  Event Bus with no manual refresh. **No frozen component was modified**,
  asserted by a `git diff` test against the MB025 tag. Two things the
  build caught: a portability defect (box-drawing glyphs crash a cp1252
  Windows console — now an ASCII fallback chosen by asking the stream what
  it can encode), and an under-delivery (the Capability panel counted
  capabilities instead of naming them). 182 new tests, 971 passing. Full
  detail: `docs/MISSION_BRIEF_026.md`, `FOUNDER_DASHBOARD_ARCHITECTURE.md`.
- **Mission Brief 027 froze the AI Capability Broker** — architecture
  only, zero code. This is the layer every remaining Executive (Desktop,
  Research, Knowledge, Terminal, Git) is blocked behind: **no Executive
  ever decides which AI to use.** It requests an *AI Capability*
  (`vision.ocr`, `reasoning.planning`) and the Broker returns a decision —
  which provider, at what cost, with what approval required, and why every
  other candidate was rejected. Placement was the mission's required
  analysis, answered without deferring: it is a **kernel service** (Shared
  Infrastructure), not an Executive, because both the Brain and the
  Operator need the same answer and it must be consulted *before*
  dispatch. The machine-touching half — scanning, probing, benchmarking —
  is a separate **AI Infrastructure Executive**: the Broker decides and
  never touches the machine; the Executive touches the machine and never
  decides. Selection walks the cost ladder (local → desktop app → free
  cloud → aggregator → subscription → paid) and stops at the first tier
  clearing a configurable *quality floor*, refusing rather than guessing
  when none does — and never auto-selects anything paid. **Ratified by the
  founder on 2026-07-29**, at which point the proposed Constitution
  amendment was applied as **Amendment 2** (§3.3, new §5.7, prior §5.7 →
  §5.8, §6, §16, §17) — the first *structural* amendment under the freeze
  process, and the one that established the sequence: proposed by a brief,
  applied only after ratification. The same ratification added a founder
  directive — **the learning loop** (ADR-0018): the Broker becomes
  self-improving through usage analytics, benchmark history, cost
  optimization, privacy awareness, and Founder-approved ecosystem
  evolution, owned by the AI Infrastructure Executive. The way that
  coexists with auditability is the thing to remember: **the versioned
  policy learns; the decision procedure stays deterministic and
  replayable.** Key decisions: ADR-0017, ADR-0018. Full detail:
  `docs/MISSION_BRIEF_027.md`, `AI_CAPABILITY_BROKER_ARCHITECTURE.md`.
- **Mission Brief 027.5 shipped the founder entry point.** `kalpavriksha`
  recovers state, wires Shared Infrastructure → Mission Control →
  Persistence → Runtime → Executives → Dashboard, and runs — closing the
  "the wiring lives in tests" gap MB026 had named in its own backlog. The
  launcher is a **composition root**: it constructs and wires, holds no
  policy, and nothing in `src/` imports it (both enforced by AST-walking
  tests). Every boot step reports its real status with a reason, so the
  absent AI Capability Broker is visible at every launch.
  **⚠️ Read this before running it with `--enable-execution`:** building
  the launcher surfaced a real, pre-existing defect — **the Runtime path
  does not consult the Permission System**, so an `IRREVERSIBLE`
  `delete_folder` completes with no approval anywhere, contradicting
  Constitution Rule 5. MB024 built that path and MIT-001 certified it;
  nobody had run it from outside a test. Execution is therefore opt-in,
  and fixing it is the top backlog item. Full detail:
  `docs/MISSION_BRIEF_027_5.md`.

## Where to go for what

| Question | File |
|---|---|
| Why does this exist? | `VISION.md` (formal), `WHY.md` (origin story) |
| What do we value / what tradeoffs does that force? | `MANIFESTO.md` |
| How do those values shape how we build? | `ENGINEERING_PRINCIPLES.md` |
| How do those values shape how the product should feel? | `PRODUCT_PRINCIPLES.md` |
| How is the system designed, and why is it shaped that way? | `ARCHITECTURE.md` (current implementation), `docs/architecture/KALPAVRIKSHA_VISION_V2.md` (authoritative architectural constitution), `ARCHITECTURE_PRINCIPLES.md` (why) |
| What's frozen vs. still open architecturally? | `docs/architecture/FOUNDER_CONSTITUTION_FREEZE.md` (section-status registry, Final Founder Review) |
| How does a Worker (Browser, and eventually Desktop/Terminal/etc.) plug in? | `BROWSER_WORKER_ARCHITECTURE.md`, `docs/MISSION_BRIEF_022.md` |
| How is work coordinated, scheduled, audited, and reported? | `MISSION_CONTROL_ARCHITECTURE.md`, `docs/MISSION_BRIEF_023.md` |
| Is the Mission Control ↔ Executive integration actually proven? | `docs/MIT_001_CERTIFICATION.md` |
| How does the system run without a human driving each cycle? | `RUNTIME_ENGINE_ARCHITECTURE.md`, `docs/MISSION_BRIEF_024.md` |
| How do I actually run it? | `kalpavriksha` — see `README.md` "Getting started" and `docs/MISSION_BRIEF_027_5.md` |
| How do I watch what it is doing? | `FOUNDER_DASHBOARD_ARCHITECTURE.md`, `docs/MISSION_BRIEF_026.md` |
| How does state survive a restart, and what happens to interrupted work? | `PERSISTENCE_ARCHITECTURE.md`, `docs/MISSION_BRIEF_025.md`, ADR-0015 |
| Which AI runs a given task, what does it cost, and who approves paid ones? | `AI_CAPABILITY_BROKER_ARCHITECTURE.md`, `docs/MISSION_BRIEF_027.md`, ADR-0017 |
| Why was each design choice made? | `docs/adr/*.md`, summarized in `DECISIONS.md` |
| What's actually built and working right now? | `docs/MISSION_BRIEF_001.md`, `docs/MISSION_BRIEF_002.md`, `docs/MISSION_BRIEF_003.md`, `docs/MISSION_BRIEF_003_1.md`, `docs/MISSION_BRIEF_004.md`, `docs/MISSION_BRIEF_004_1.md`, `docs/MISSION_BRIEF_005.md` |
| What shipped when, at what commit/tag, with how many passing tests? | `MIRACLE_LEDGER.md` |
| How does a new local capability plug in? | `ARCHITECTURE.md` §4.7, `docs/MISSION_BRIEF_002.md`, `FILESYSTEM_CAPABILITIES.md`, `docs/MISSION_BRIEF_005.md` |
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
