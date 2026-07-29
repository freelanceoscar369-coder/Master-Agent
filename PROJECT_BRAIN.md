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
- **Mission Brief 028.0 closed the hole.** *(Designed first, stopped at
  the ADR, ratified, then implemented — the sequence the brief required.)*
  The trace names the exact gap: there are **two permission gates and two
  execution paths, and both gates are on one path.** Gate A
  (`orchestrator.py:42`) is the real boundary; Gate B (`executor.py:104`)
  only receives ADR-0005's relayed decision and is self-satisfied by the
  grant on the line before it. The Runtime calls gateways directly and
  never touches the Orchestrator, so neither gate fires. The design is one
  `ApprovalGate` defined inside `runtime/`, consulted at `_handle_task()`
  — the only funnel — and **failing closed**. It needs **ADR-0019
  ratified** because it changes `runtime/` and `mission_control/events.py`,
  and MB028.0's own rules say stop at that point. Ratified 2026-07-29 and
  implemented: **Constitution Rule 5 is now mechanically true on both
  execution paths.** No gate wired means *nothing* runs — fail-closed is
  total, because the Runtime cannot resolve a risk tier and so cannot
  evaluate an exception. Evidence outlives the process, authority does
  not: a replayed approval restores the record, never a usable grant, so
  after a restart the audit remembers you approved and the system still
  asks again. Verified live. 22 new tests, 1015 passing. Full detail:
  `docs/MISSION_BRIEF_028_0.md`.
- **Mission Brief 024 built the Runtime Engine — the heartbeat.**
  Kalpavriksha now runs **unattended**: a founder submits an objective,
  calls `start_background()`, and the loop observes Mission Control,
  dispatches, executes through an Executive-agnostic gateway, invokes
  Verification, reports back, and idles — repeating until stopped. Proven
  live against the real internet: a four-task browser mission (open →
  navigate → observe+verify → close) completed with `progress: 1.0` and
  the founder doing nothing after start. Two tensions had to be resolved
  first, both recorded in `RUNTIME_ENGINE_ARCHITECTURE.md`: *who invokes*
  when nothing may perform work (answer: a gateway protocol the Runtime
  holds, so Mission Control stays mechanically pure), and *retry* versus
  Constitution §11 (answer: mechanical retry only, and Mission Control
  never sees a retry — only the final outcome). Rules 1 and 2 are enforced
  by an import-parsing test; no `runtime/` file may even name a specific
  Executive. 82 new tests, 582 passing, zero regressions. Full detail:
  `docs/MISSION_BRIEF_024.md`.
- **MIT-001 certified the integration** — the test that decided whether
  the architecture actually holds: *can Mission Control orchestrate the
  Browser Executive without modifying it?* **Yes.** All seven MIT-001
  tests pass (19 automated tests plus one live run against the real
  internet, reaching `https://example.com` and returning a `matched`
  verdict). Zero Modification is proven three ways, including a test that
  runs `git diff` against the MB022 tag and fails if a Browser Executive
  file ever changes. Two deliberate differences from the brief's expected
  output are documented rather than papered over: `Browser.Fill` is named
  `Browser.TypeText` (deterministic naming rule), and there is
  **no `Browser.Verify` capability on purpose** — ADR-0011 makes
  Verification structurally independent, so it must never be dispatchable
  as ordinary work. Certification and full transcript:
  `docs/MIT_001_CERTIFICATION.md`.
- **Mission Brief 023 built Mission Control** — the runtime coordination
  layer everything else now plugs into: a Universal Event Bus (one `Event`
  schema for every Executive, no custom logging anywhere), a Capability
  Registry keyed by deterministic qualified names (`Filesystem.ReadFile`),
  an Executive Registry, the nine-state Worker Lifecycle, a Task
  Dispatcher that turns objectives into dependency-ordered capability
  calls, a Self-Development Queue, a Knowledge Acquisition Queue, an
  immutable Audit Stream, and a Founder State backend contract (no UI).
  Two things worth knowing: **Mission Control never performs work** — a
  test parses every module's imports and fails if any of them could —
  and the **knowledge-promotion gate is enforced in code**, so ADR-0012's
  human-gated Promotion Review cannot quietly become a convention.
  Existing Executives register **unmodified** via an adapter that reads
  their manifest; the integration tests use the real `FilesystemPlugin`
  and `BrowserPlugin`, not fakes. Also made the first amendment under the
  Constitution freeze process (ADR-0014, reconciling "Executive" with
  "Worker"). 107 new tests, 461 passing, zero regressions. Full detail:
  `docs/MISSION_BRIEF_023.md`, `MISSION_CONTROL_ARCHITECTURE.md`.
- **Mission Brief 022 built the Browser Worker** — the first
  implementation Mission Brief against the frozen Constitution, proving
  the Universal Executive Operator architecture in a real Environment by
  wrapping Playwright (never reimplementing it): nine atomic Actions
  (`open_browser_session`, `close_browser_session`, `navigate`, `click`,
  `type_text`, `press_key`, `scroll`, `wait_for_selector`,
  `observe_browser`) registered on the existing, unmodified
  `LocalExecutor`/`Plugin` machinery. Introduced two genuinely new,
  reusable pieces: a generic, Playwright-free `verification/` package
  (`Verifier` ABC, `Evidence`, `Audit` — any future Worker's verification
  layer, not just Browser's) and an Environment Session Manager
  (`BrowserSessionManager`) resolving the one stateful-session gap
  `FOUNDER_CONSTITUTION_FREEZE.md` had left open for the Action contract.
  Demonstrated, concretely and with passing tests, that Execution
  succeeding never implies Verification succeeding (an Action can return
  `success=True` while an independently-recomputed Verdict is
  `NOT_MATCHED`). Mechanically verifies its own product-independence claim
  — a test scans every Browser Worker file for forbidden product names and
  fails if one appears. 125 new tests, 354 passing overall, zero
  regressions (5 pre-existing, unrelated Windows path-separator failures
  in the filesystem Actions were confirmed present before this Miracle
  started and are unchanged by it). Full detail: `docs/MISSION_BRIEF_022.md`,
  `BROWSER_WORKER_ARCHITECTURE.md`.
- **Mission Brief 021, Revision 3 froze the Founder Constitution** —
  `docs/architecture/KALPAVRIKSHA_VISION_V2.md` is now the authoritative
  reference for architectural *decisions* (superseding prior Mission
  Briefs/ADRs on architecture, though not their implementation-record
  content), with `ARCHITECTURE.md` remaining the accurate current-
  implementation module map, now read through the Constitution's
  terminology. Design-only — zero code/test changes. Resolved every gap an
  independent audit found: introduced a Shared Infrastructure layer
  beneath the Executive Brain and Universal Executive Operator (ADR-0010),
  made Verification structurally independent of Execution (ADR-0011),
  formalized a Knowledge Lifecycle with a human-gated Promotion Review
  (ADR-0012), removed product-specific terminology (Hermes/ChatGPT/Ollama/
  VS Code/Obsidian) from the architecture in favor of role-based terms,
  designed for multiple Operator Instances across multiple environments
  (ADR-0013), gave every previously-unowned component
  (`MasterAgentSession`, `MissionManager`, `Reporter`) exactly one home,
  consolidated duplicated rules, and froze architectural terminology.
  Final Founder Review: the Constitution is frozen; `ROADMAP.md`'s next
  five planned items can proceed without further Constitution changes.
  Full detail: `docs/MISSION_BRIEF_021_REVISION_3.md`,
  `docs/architecture/FOUNDER_CONSTITUTION_FREEZE.md`.
- **Mission Brief 005 turned the Filesystem Plugin into a real toolbox** —
  eleven new primitive Actions (read/list/search/exists-checks, append,
  rename/copy/move, delete-file/delete-folder), taking `FilesystemPlugin`
  from 3 to 14 capabilities, registered declaratively (adding capability
  #15 costs one new class, never an edit to the plugin itself — see
  `FILESYSTEM_CAPABILITIES.md`, written before any code per the brief's
  design-first gate). Added `PermissionCategory` as a new, purely
  descriptive axis alongside `RiskTier`, plus one real mechanism change:
  a standing `always_for_capability` grant can never satisfy a check for
  an `irreversible` capability — destructive actions require a fresh
  decision every time (ADR-0009). `cli.py`'s intent parser now recognizes
  nine new conversational shapes ("Read X", "Rename X to Y", "Delete X
  [folder]", ...) via one generic `ParsedActionIntent` and a table-driven
  `_INTENT_PATTERNS` dispatch, reaching all six of the brief's
  conversation examples end to end. 108 new tests, 234 passing overall,
  zero regressions. Full detail: `docs/MISSION_BRIEF_005.md`.
- **Mission Brief 028.1 made it usable.** MB028.0 made Kalpavriksha safe
  and left it with no way to say yes. Now `kalpavriksha` shows an Approval
  panel — capability, executive, risk tier, reason, estimated impact
  ("Deletes 14 files"), timestamp — and you type `approve 1`, `reject 1`,
  `defer 1`, or `approve all`. **This is the brief where Kalpavriksha
  stops being a set of working subsystems and becomes a system a founder
  operates.** The change underneath: an unanswered request is no longer a
  refusal — the task *waits*, and the Runtime re-offers it the moment you
  answer. The Approval Queue lives in Mission Control beside its two
  existing human-gated queues and is **not** a second permission system:
  it holds questions, the Permission System holds authority. **ADR-0016
  survives intact** — the Dashboard still renders from a frozen snapshot
  and cannot act on the `[A]pprove` hints it prints; the Console in the
  launcher does. Every decision lands in an immutable ledger; deferred
  requests survive restart; a restored approval is evidence, never fresh
  authority. **⚠️ Ships frozen-component changes with ADR-0020 marked
  *Proposed*.** 33 new tests, 1051 passing. Full detail:
  `docs/MISSION_BRIEF_028_1.md`.
- **Mission Brief 029 rebuilt what the founder actually sees.** Pure UX,
  zero architecture change (proved by `git diff`, which is why it has no
  ADR). `kalpavriksha` opens on a **Founder page** — status in one human
  sentence, decisions second, then mission, work, executive readiness,
  self-development, recommendations. The nine engineering panels are one
  keystroke away behind `[V]`, moved rather than deleted. A **view model**
  (`dashboard/founder.py`) now sits above ADR-0016's read model, so a web
  or mobile front-end consumes `FounderView` and writes its own renderer
  without touching Mission Control. **The thing to remember:** three
  deliverables asked for numbers this system does not measure, and none
  were invented — Confidence is a stated reading of the verification
  record or absent, the self-development bars are transcribed from the
  roadmap with each naming its basis, and "Time saved" is reported as not
  measured. 76 new tests, 1138 passing. Full detail:
  `docs/MISSION_BRIEF_029.md`.
- **Mission Brief 030 gave Kalpavriksha eyes and hands on the machine.**
  The Desktop Executive: twelve capabilities that discover installed
  software, versions and running processes, and launch, open, close, or
  run things. **It executes and never decides** — choosing between what it
  finds is the AI Capability Broker's job, and a test parses the whole
  `desktop/` package for provider vocabulary to keep it that way.
  **Zero architecture change, and therefore no ADR**: everything new lives
  in a new package built on MB002's Action contract and Mission Control's
  existing adapter, which is the strongest evidence yet that those
  contracts generalise. `CloseApplication` and `ExecuteCommand` are
  `IRREVERSIBLE`, so each is a fresh founder decision. Running it against
  the real machine found three defects a fake probe never could — the
  worst being error text presented as a version number. `kalpavriksha`
  now shows Machine Readiness on launch. 228 new tests, 1367 passing.
  Full detail: `docs/MISSION_BRIEF_030.md`.

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
| What stops it doing something irreversible? | `RUNTIME_ENGINE_ARCHITECTURE.md` §4a, `docs/MISSION_BRIEF_028_0.md`, ADR-0019 |
| How do I approve, reject, or defer a pending action? | `docs/MISSION_BRIEF_028_1.md`, ADR-0020 |
| What does the founder actually see, and how do I add a web/mobile UI? | `docs/MISSION_BRIEF_029.md`, `dashboard/founder.py` (the view model) |
| What software does it know about on my machine? | `docs/MISSION_BRIEF_030.md`, `desktop/catalog.py` |
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
