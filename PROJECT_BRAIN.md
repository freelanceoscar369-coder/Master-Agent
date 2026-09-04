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

## Where things stand right now (2026-09-04)

Read this section for current truth. Everything below it is the record of
how the system got here, and is kept unedited on purpose.

Each claim below carries the kind of proof it actually has. A source-level
test is not a live proof, and a live proof is not a packaged proof. Where
those differ, the weaker one is the truth.

### Architecture truth

The Constitution is frozen (`docs/architecture/FOUNDER_CONSTITUTION_FREEZE.md`)
and ADRs are ratified through **ADR-0027**. The three that govern current
work:

- **ADR-0024** — intent resolution, clarification and Planner admission.
  Understanding and capability are separate axes.
- **ADR-0026** — founder semantic meaning stays traceable to a verified
  outcome.
- **ADR-0027** — Brain Deliberative Intelligence and Decision Utility.
  This lives *inside* the existing System Brain; it is not another layer
  and not another agent. Its invariant: every material Brain decision must
  be useful for satisfying Founder intent, or for truthfully determining
  that it cannot yet be satisfied. It separates **source failure**,
  **method failure** and **objective failure** — a method failure must not
  become an objective failure by default.

No second Brain, Planner, Broker, Browser Executive, computer-use engine,
verification subsystem, persistence layer, capability registry or provider
registry is to be built. The ones that exist are the ones.

### The founder-intent pipeline, by stage

| Stage | What it covers | Status | Evidence |
|---|---|---|---|
| **1** | Founder → Intent | **FROZEN** | live-proven at `0e4eb95` |
| **2** | Intent → Brain's next decision | **FROZEN** | live-proven at `73584a3` |
| **3** | Brain decision → Planner fidelity | **FROZEN** | closed at `1748c5e`; the contract was already right — the correction prompt was truncating the plan it asked the model to fix |
| **4** | Persistent continuation / Planner reliability | **OPEN** | see below |

Stages 1–3 are not reopened because an older document describes them
differently. Reopening one needs evidence tracing a live failure back to it.

### Stage 4 — the open frontier

Measured on free providers: **~51–53% Planner admission at 100% target
fidelity**. The objective is **≥90% admission without weakening target
fidelity or the validators**. Buying the number by loosening a validator is
not progress; it is a louder way of being wrong.

### Implementation and wiring truth

- The Brain→action loop lives in the repository-root composition root, not
  under `src/` — grep the repository, not the package.
- A capability now publishes what it produces rather than leaving the
  Planner to infer it (`bcd5913f`).
- A founder judgement **pauses** a mission rather than ending it
  (`ad169fe0`), and the Brain's action decides who acts next rather than
  the loop deciding (`5873d9d8`).

### Live-proven truth

- **Trusted-web route reached.** The Gemini web surface was driven, and the
  **Onkar** profile was selected autonomously without asking the Founder.
- **GLM-5.3-Flash via the Cline native TUI** (Cline Usage-Billing provider)
  answered live at an observed **$0.00**. Classified
  **FREE_PROMOTIONAL / FREE_LIMITED** — never `FREE_FOREVER`, because the
  client itself carries daily-limit and promotion-ended states. Route
  detail: `Engineering/INTELLIGENCE_ROUTE_RECORD_GLM53.md`.
- Two sibling routes are **not** available: GLM-5.3-Flash via Ollama Cloud
  is `PAID_NOT_ENTITLED`, and the Cline **headless** free route 404s. Both
  are recorded so they are not retested by accident.

### Trusted-web current-turn ownership — LIVE-PROVEN (4 Sep 2026)

Both invariants were proven against the real page, in the hardest shape
available: a 26,438-character prompt submitted into a conversation already
carrying an entire previous run, with the reply being a token quoted
verbatim in the prompt. The extractor returned that 33-character token and
nothing else — no decoy line, no run of the prompt, no sentinel from the
earlier turn.

  submitted prompt ≠ current provider reply          ✓
  the extractor owns only the current provider turn  ✓

Two defects had to be closed to get there, and the second was found only
because the first live run was actually run:

1. **Echo.** A 40-character anchor identifies only the *first* fragment of
   a turn, so later fragments of a long prompt carried no anchor and read
   as new text. A ~26K prompt came back as though Gemini had written it —
   size was deciding ownership.
2. **Over-correction.** Containment against our own outgoing text fixes (1)
   and alone overshoots: asked for a token quoted in the prompt, Gemini
   answered perfectly and containment disowned it, so the provider timed
   out with the answer on screen. Order settles what content cannot — we
   send the prompt once, so the page echoes it once.

`GEMINI PLANNER SUITABILITY` is still **UNMEASURED**. Ownership no longer
voids a benchmark, but none has been run yet.

### Open: the trusted-web lane reaches the page unreliably

Newly measured, and separate from ownership. Across three live runs (six
submission attempts), **three attempts never submitted at all**:

- `could not confirm window … reached the foreground after 3 attempts` —
  the provider correctly refuses to type into a window it cannot confirm is
  in front, rather than typing blind. It then has no second route.
- `sign-in did not complete in time` — the page-state classifier never read
  READY and waited out 300 seconds on an authenticated page.

These cost 28s–317s and return nothing, which under Rule U2 is
founder-rescue-shaped. The causal owner is the desktop foreground/page-state
layer, **not** the extractor. One caveat held open honestly: these runs were
driven from a background process on a busy desktop, so how much of the
foreground contention is the product and how much is the harness is not yet
separated.

### Packaged-proven truth

The Founder Edition desktop app has been built and demonstrated, but one
**heap-corruption crash after a spoken reply remains unreproduced and its
root cause OPEN**. Packaging a rebuild requires the app to be closed; a
locked-file build failure leaves the *old* executable in place, so verify
the artefact rather than the exit code.

### Open / unproven

- Stage 4 reliability (the ≥90% objective above).
- Trusted-web page reach: the foreground and sign-in-state failures above.
- The Founder Edition crash root cause.
- The backend suite carries a known baseline of failures that are
  **environment-dependent**, not regressions — e.g. `test_fmea_web_scope.py`
  fails wherever no Gemini API key is configured, because the tier is then
  legitimately empty. Compare failure IDs against that baseline before
  calling anything a regression.

### Who owns what

**Hyper Agent owns UI and UX** — visual design, UX redesign, page
composition, the visual system, interaction design, and its own design
documents. Core engineering owns backend correctness, architecture,
contracts, state models, the interfaces UI consumes, evidence, tests and
packaging, and fixes UI-blocking backend defects when the cause is proven.
A UI requirement discovered here becomes a written interface/state handoff
to Hyper Agent, never a silent redesign.

### Standing safety rule

No paid inference is authorised. Before any Cline inference: verify the
provider, verify the model, verify its free/cost status, and leave
auto-approve **off** unless tools are genuinely required. A previous
accidental paid call happened because a default paid model and auto-approve
were both live.

## How it got here (state as of 2026-07-31)

**The loop is closed.** As of Mission Brief 037 a founder types a
sentence into `kalpavriksha` and it becomes a plan, runs, is verified
step by step, and is remembered:

```
Founder -> Planner -> MissionPlan -> Mission Control -> Executives
        -> Broker -> Providers -> Verifier -> Evidence -> Memory
```

Nothing in that line is a stub. The Planner is the only producer of a
plan (MB036), the Broker is the only chooser of a provider (MB031/032),
the Verifier is the only judge of an answer (MB035), Memory is the only
keeper of what was learned (MB034), and Mission Control is the only
orchestrator (MB023). Each of those is asserted by a test rather than by
this paragraph.

Two things are known-missing and named rather than hidden: **pause /
resume / cancel** (needs a ratified ADR — MB037 §5), and **nothing
publishes what arguments a capability takes**, so the Planner guesses
them (MB036 Findings 4 and 5; top of the backlog).

The rest of this section is the historical record of how it got here.

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
- **Mission Brief 031 built the AI Capability Broker's decision engine.**
  The thing MB027 designed and you ratified, now real: hand it provider
  profiles and a task, and it answers which provider to use — filter,
  quality floor, rank by policy, take the first, or **refuse rather than
  guess**. Eight founder policies, byte-identical replay, and a
  `policy_version` on every decision so history stays readable under the
  rules it was made under (ADR-0018). **100% coverage, zero changes to
  anything existing**, and the forbidden list enforced by AST tests — no
  network imports, no vendor names, no execution surface, and no
  dependency on any other subsystem. **The finding worth remembering:** a
  blended quality-per-cost score picked a paid provider over a free one
  that also cleared the floor, which is exactly what ADR-0017 warned would
  happen; the blend was deleted and policies now differ by their *floor*.
  **It is not wired to anything yet** — that is the next brief, and it is
  where the integration risk lives. 180 new tests, 1543 passing. Full
  detail: `docs/MISSION_BRIEF_031.md`.
- **Mission Brief 032 wired the Broker in, and it is now the only thing
  that answers "which AI?".** A task goes `Broker -> DecisionRecord ->
  approval if needed -> execution`, and nothing reaches a provider before
  the first three have happened. The Model Router's four hardcoded
  branches are gone — including the one that answered *"I need this done
  well"* with a named cloud model, which is now a **quality floor**.
  Provider profiles come from the Desktop Executive's machine scan, so
  what is available is a fact about your machine rather than a list in
  code, and **"nothing has scanned yet" is reported as absence rather than
  assumed present**. Paid providers reach your existing Approval panel
  before anything is spent; free local ones run immediately. Every
  decision is stored and replays against **its own** policy, so changing
  your policy never rewrites history. **The things worth remembering:**
  exactly one frozen file changed and a ratified ADR had named it five
  Miracles earlier; a missing Broker **fails closed** rather than falling
  back, because a fallback is itself a provider decision; and every
  quality number in the catalogue is a *declared* guess, labelled as such
  on screen, until a benchmark store exists. 397 new tests, 1945 passing,
  100% coverage of the new package. Full detail:
  `docs/MISSION_BRIEF_032.md`.
- **Mission Brief 033 made it actually think.** `kalpavriksha --ask "..."`
  now goes Broker → Ollama → answer, on your own machine, for free: a live
  run against `gemma4:latest` took 22.8 s, used 30 tokens, cost nothing,
  and is on the record with all of that attached. **The provider only
  ever executes** — it cannot rank, route, or fall back, and if it fails
  you get a fact you can act on rather than a substitution: a missing
  model answers with *the models you do have*, a stopped daemon answers
  with the address it tried. Only the Broker may choose a different
  provider, and that rule is why the record can be trusted later. The
  **Token Economy** starts counting here, and it will not flatter you:
  "money saved" is never what a frontier model *would* have cost, only
  what was genuinely reused instead of repeated — so it reads zero today,
  and the panel says why. **The thing to know:** the Prompt Cache is
  wired and always misses, because reuse requires *verified* work and
  nothing yet verifies generated text. A verifier is now the highest-value
  next step for cost. 350 new tests, 2295 passing, 100% coverage of the
  new packages, and zero frozen files touched. Full detail:
  `docs/MISSION_BRIEF_033.md`.
- **Mission Brief 034 gave it a memory.** Type `remember "Never delete
  logs automatically"` and it is still there next launch; type `memory
  docker` and you get back exactly what you wrote, ranked and repeatable.
  It also writes things down on its own — missions that finished, missions
  that failed, verifications, your approvals, and recoveries that actually
  recovered something — by listening to the Event Bus that already
  existed. **No LLM is involved anywhere in this**: no embeddings, no
  semantic search, no summarisation. Retrieval is deterministic and the
  ranking is written down, so the same question gives the same answer
  forever. Memory lives **beside** the state directory, never inside it,
  because a recovery may throw operational state away and must never throw
  away what you said — and a corrupt memory file is moved aside rather
  than overwritten, so you can always open it and copy your notes out.
  **The things to know:** saying something twice is one memory (and can
  raise its importance, never lower it); search is whole-word, so `fail`
  will not find `failure`; and there is no `forget()` yet — deleting
  founder memory deserves its own thinking. 315 new tests, 2610 passing,
  100% coverage of the five new modules, zero frozen files touched. Full
  detail: `docs/MISSION_BRIEF_034.md`.
- **Mission Brief 035 taught it to check its own answers.** Ask it
  something *and say what a good answer looks like* — "must mention blue",
  "must be JSON with a `name` field", "at least twenty words" — and it
  tells you whether the answer actually met that. Live: `Blue` came back
  from your local model, all three checks passed, verdict **matched**, and
  the answer was cached; asking the same question with a *different*
  requirement correctly re-asked rather than reusing it. **No model judges
  another model** — that recursion is the one thing this system has now
  refused to start three briefs running. A verdict is arithmetic over what
  you asked for *before* the answer arrived, which is the only kind you
  can argue with. **What this unblocks:** MB033's Prompt Cache now
  actually hits (and ships on, because the reason it was off is gone), and
  MB034's Prompt Library finally writes itself — a prompt that worked is
  filed under Prompt Library, one that did not under Failure Library, with
  the evidence id attached. **The thing to know:** somebody has to say
  what a good answer looks like. Nothing infers it, and nothing should — a
  check invented *after* the answer arrived is a rationalisation. Until
  the real Planner attaches one to every step, the cache and the Prompt
  Library fill only for callers that say what they want. And the checks
  are structural: they catch a blank answer, a refusal, a truncation, a
  wrong format — not an answer that is fluent, well-formed and wrong. 153
  new tests, 2763 passing, 100% coverage of both changed modules, zero
  frozen files touched. Full detail: `docs/MISSION_BRIEF_035.md`.

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
| How does it choose which AI to use? | `docs/MISSION_BRIEF_031.md` (the engine), `docs/MISSION_BRIEF_032.md` (how it is wired in), `broker/`, `ai_infrastructure/`, ADR-0017, ADR-0018 |
| Which providers does it know about, and where do their numbers come from? | `ai_infrastructure/catalog.py` — the one file allowed to name a product, and every number in it is a stated guess |
| Why did it pick that provider, and can I see the history? | The AI Decisions panel on the founder page; the durable ledger at `<state-dir>/broker_decisions.json`, replayable with `DecisionLedger.replay()` |
| How do I actually ask it something? | `kalpavriksha --ask "your question"` (add `--model` if yours is not the configured one) — `docs/MISSION_BRIEF_033.md` |
| How does a provider actually run a prompt, and what happens when it fails? | `providers/ollama.py`, `providers/transport.py`, `docs/MISSION_BRIEF_033.md` §3 |
| What has AI actually cost me, and what did it save? | The Token Economy block on the founder page; `ai_infrastructure/economy.py` for exactly what each number counts and refuses to count |
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
| How do I tell it something it should remember forever? | `remember "..."` in the console, or `memory <words>` to ask — `docs/MISSION_BRIEF_034.md` |
| What does it know about me, and where is that stored? | The MEMORY section on the founder page; `<app-dir>/memory/knowledge.json`, readable by hand |
| Why did that search return those results in that order? | `memory/memory_query.py` — the weights and tie-breaks are a table, not a tuned score |
| How does it know whether an answer was any good? | `ai_infrastructure/text_verifier.py`, ADR-0011, `docs/MISSION_BRIEF_035.md` — deterministic checks against what you asked for, never a model's opinion |
| Why did it re-ask instead of reusing a cached answer? | A cached answer is only served if it still satisfies *your* expectation — `docs/MISSION_BRIEF_035.md` §5 |
| How do I just tell it what I want? | Type it into `kalpavriksha`. Anything that is not a console verb becomes an objective: it is planned, submitted to Mission Control, executed, and verified — `docs/MISSION_BRIEF_037.md` |
| What is it doing right now, step by step? | The CURRENT MISSION panel on the founder page — current step, what it expects, what is waiting on a dependency, what failed verification |
| How does an objective become steps? | `planner/`, `docs/MISSION_BRIEF_036.md`. The Planner is the **only** producer of a `MissionPlan`, asserted by an AST test over all of `src/` |
| What does the Brain have to understand before the Planner is allowed to see it? | ADR-0024 — Intent resolution, clarification, and Planner admission. Codifies that understanding and capability are independent (a goal can be understood and not directly executable), that clarification means *missing information* and never *missing ability*, and that Intent must preserve who acts and who benefits. Records what is **not** implemented: the clarification round trip, and agency as a structural field rather than surviving raw text |
| How does a plan become work Mission Control runs? | `missions/translation.py` — a 1:1 copy into `Task`, and the gate that refuses a plan missing a capability, inputs, an expected outcome or dependency information |
| What did it do last time, and can I see it again? | `replay` in the console. Reads recorded evidence only and can reach no provider at all — `missions/history.py`, `docs/MISSION_BRIEF_037.md` §4.5 |
| Why can't I pause or cancel a mission? | Deliberately not built — it needs a ratified ADR. `docs/MISSION_BRIEF_037.md` §5 explains exactly why, and a test enforces the absence |
| Why did my step fail with the right idea but the wrong arguments? | Nothing publishes a capability's argument names yet, so the Planner guesses them. `CapabilityManifest.input_schema` is the empty seam — MB036 Findings 4 and 5, top of the backlog |
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
