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
| **021 Rev. 3** — Founder Constitution Freeze | Design-only (no code, no tests). Resolved every gap an independent audit found in `docs/architecture/KALPAVRIKSHA_VISION_V2.md`: Shared Infrastructure layer (ADR-0010), structurally independent Verification (ADR-0011), the Knowledge Lifecycle (ADR-0012), product-name-free architecture, multi-Operator design (ADR-0013), exactly-once ownership for every component, consolidated rules, frozen terminology, per-section status labels. Declared the Constitution frozen for everything currently on this roadmap. Full detail: `docs/MISSION_BRIEF_021_REVISION_3.md`, `docs/architecture/FOUNDER_CONSTITUTION_FREEZE.md`. |
| **022** — Browser Worker | First implementation Mission Brief against the frozen Constitution: a Playwright-wrapped Browser Worker (nine atomic Actions) proving the Universal Executive Operator architecture in a real Environment. Introduced the generic, Playwright-free `verification/` package (Verifier ABC, Evidence, Audit) any future Worker can reuse unchanged, and the Environment Session Manager pattern (`BrowserSessionManager`) resolving the one stateful-session gap `FOUNDER_CONSTITUTION_FREEZE.md` had left open. Mechanically verifies its own product-independence claim (`test_browser_constitution_compliance.py`). Observes five facets, including the accessibility tree and the page's available actions. 125 new tests, 354 passing overall, zero regressions. Full detail: `docs/MISSION_BRIEF_022.md`, `BROWSER_WORKER_ARCHITECTURE.md`. |

| **023** — Mission Control & Self-Development Infrastructure | The runtime coordination layer everything else plugs into: Universal Event Bus (one schema, no custom logging), Capability Registry, Executive Registry, nine-state Worker Lifecycle, Task Dispatcher (dependency-ordered), Self-Development Queue, Knowledge Acquisition Queue with a code-enforced human promotion gate, immutable Audit Stream, and a Founder State backend contract (no UI). Existing Executives register unmodified via a manifest-reading adapter. "Mission Control never performs work" is enforced by an import-parsing test. First amendment under the Constitution freeze process (ADR-0014). 107 new tests, 461 passing, zero regressions. Full detail: `docs/MISSION_BRIEF_023.md`, `MISSION_CONTROL_ARCHITECTURE.md`. |

Full detail on each: `docs/MISSION_BRIEF_001.md` through
`docs/MISSION_BRIEF_005.md`, `docs/MISSION_BRIEF_021_REVISION_3.md` for the
Constitution Freeze, `docs/MISSION_BRIEF_022.md` for the Browser Worker,
and `docs/MISSION_BRIEF_023.md` for Mission Control; `MIRACLE_LEDGER.md`
for the tag/commit/test-count record of the code-bearing Miracles.

## In progress

Nothing is currently in progress. Mission Brief 023 made Mission Control
the permanent coordination layer; every future Mission Brief plugs into it
rather than inventing new coordination logic. The next Miracle to start is
the first item under Planned, below.

| **MIT-001** — Mission Control Integration, Browser Executive | Certification, not a new capability: proved Mission Control can orchestrate the Browser Executive with **zero modification** to it. All seven tests pass (19 automated + a live run to a real URL). Added auto-discovery (`discover_executives`), renamed `TASK_DISPATCHED` → `TASK_ASSIGNED` per the spec, added `FounderState.result`, and stamped the capability onto verification events for audit traceability. Full detail: `docs/MIT_001_CERTIFICATION.md`. |

| **024** — Autonomous Runtime Engine (The Heartbeat) | The loop that replaces the founder in the cycle: observe → dispatch → execute → verify → report → idle → repeat. Kalpavriksha now runs unattended, proven live against the real internet (four-task browser mission, `progress: 1.0`, zero founder involvement after start). Executive-agnostic by construction — an import-parsing test forbids `runtime/` from naming any specific Executive. Mechanical retry with escalation, honouring Constitution §11's reservation of strategic recovery for the Brain. 82 new tests, 582 passing. Full detail: `docs/MISSION_BRIEF_024.md`, `RUNTIME_ENGINE_ARCHITECTURE.md`. |

| **025** — Persistent Runtime State Engine | Operational memory: Kalpavriksha survives a kill and resumes exactly where it stopped, demonstrated live (each task executed exactly once across both processes, audit history intact). New `persistence/` package — bus-subscribed event log, versioned+checksummed snapshots, event replay, one-call `recover()`. Interrupted tasks are quarantined rather than re-run. **⚠️ Ships three additive changes to frozen components, recorded in ADR-0015 as *Proposed* and awaiting ratification.** 205 new tests, 789 passing. Full detail: `docs/MISSION_BRIEF_025.md`, `PERSISTENCE_ARCHITECTURE.md`. |

| **026** — Founder Dashboard (Founder Edition v1) | The first operational window into the running system: nine read-only panels updating live off the Event Bus, no manual refresh. Read-only by construction (a frozen read model between contracts and rendering), and **zero frozen components modified**, enforced by a `git diff` test. Demonstrated live across a real kill-and-restart: reconnected, showed restored state, and watched the mission resume to 100%. 182 new tests, 971 passing. Full detail: `docs/MISSION_BRIEF_026.md`, `FOUNDER_DASHBOARD_ARCHITECTURE.md`. |

| **027** — AI Capability Broker Architecture | Architecture-only (no code): froze the intelligence-selection layer every future Executive is blocked behind. The Broker is a **kernel service** (Shared Infrastructure), not an Executive — both the Brain and the Operator need the same answer, and it must be consulted *before* dispatch. Provider registry, capability matrix, decision engine (cheapest tier clearing a configurable quality floor; refuse rather than guess), AI asset inventory, recommendation engine, cost model, benchmark engine (Verification-backed, observed beats declared), founder approval policy, and the AI Infrastructure Executive / Desktop Executive / Capability Package contracts. Proposed a Constitution amendment rather than making one; **the founder ratified it 2026-07-29 and it was applied as Amendment 2**. The same ratification added the **learning loop** as a first-class objective for the AI Infrastructure Executive — the policy learns, the decision procedure does not (ADR-0018) — and added `IRREVERSIBLE` install/remove/upgrade to that Executive's contract. Key design decisions: ADR-0017, ADR-0018. Full detail: `docs/MISSION_BRIEF_027.md`, `AI_CAPABILITY_BROKER_ARCHITECTURE.md`. |

| **027.5** — The Kalpavriksha Launcher | The founder entry point: `kalpavriksha` recovers state, wires every shipped subsystem, starts the Runtime, and hands the terminal to the Founder Dashboard — closing the "wiring lives in tests" gap MB026 left open. No new architecture: the launcher is a **composition root** that constructs and wires, and is depended on by nothing (both enforced by AST-walking tests). Every boot step reports its real status with a reason, so the absent AI Capability Broker is visible at every launch rather than silently skipped. **Found a real defect by running it: the Runtime path does not consult the Permission System**, so an `IRREVERSIBLE` delete completes unapproved — pre-existing, contradicts Constitution Rule 5, and now the top backlog item. Execution is opt-in (`--enable-execution`) until it is fixed. 22 new tests, 993 passing. Full detail: `docs/MISSION_BRIEF_027_5.md`. |

## Backlog — tracked, not blocking

- **MB023.1 — Cross-Platform Path Safety.** Harden
  `is_unsafe_relative_path()` for Windows/POSIX differences (a
  POSIX-absolute path like `/etc/passwd` is not `is_absolute()` on
  Windows, so the sandbox check under-rejects), normalize path separators
  in action output, add regression tests, and verify sandbox boundary
  behavior on both platforms. Raised alongside Mission Brief 023 and
  deliberately kept out of it — the nervous system was the mission.
  **Status: completed** (`v0.7.1-miracle-023-1`) — fixed three real
  cross-platform defects and took the suite fully green (500 passed, 0
  failed) for the first time. See `docs/MISSION_BRIEF_023_1.md`.
- **The closing loop.** ✅ **Done** — shipped as Mission Brief 024, the
  Autonomous Runtime Engine. The Kalpavriksha Loop is continuous.
- **Persistence for Mission Control.** ✅ **Done** — shipped as Mission
  Brief 025.
- **Ratify (or reject) ADR-0017's Constitution amendment.** ✅ **Done** —
  ratified 2026-07-29 and applied as **Constitution Amendment 2** (§3.3,
  new §5.7, prior §5.7 → §5.8, §6, §16, §17). The founder also approved
  the Kernel Service placement and the Broker / AI Infrastructure
  Executive split, and added the learning loop as a first-class objective
  (ADR-0018).
- **Retire `ModelRouter.select_provider()`'s hardcoded provider ladder.**
  `plugins/model_router.py` branches on the literal strings `"hermes"` and
  `"chatgpt"` — product names in Brain logic, which Constitution §14/§21
  forbid. The AI Capability Broker (MB027) supersedes it: the Model Router
  keeps its `generate()` interface and its role as the Brain's single door
  to reasoning, and asks the Broker *which* provider instead of ranking
  them itself. Implementation brief, blocked only on the Broker existing.
- **Ratify (or reject) ADR-0015.** MB025 ships three additive changes to
  frozen components. Each is documented, isolated, and reversible, and the
  ADR is deliberately marked *Proposed* rather than Accepted. This is a
  founder decision, not a default.
- **Event-log compaction.** The persisted log grows without bound.
  Segmentation was deliberately not built, because a correct compaction
  policy needs a retention policy that does not exist yet.
- **A shipped browser gateway.** MB024's `BrowserGateway` lives in test
  support, which is correct for Rule 2 but means the first real launcher
  has nothing reusable to wire. It belongs beside the Browser Executive,
  never inside `runtime/`.
- **`count_events()` on the `StateStore` contract.** The Dashboard's
  "Event Log Size" currently comes from `read_events()`, which returns the
  entire persisted log — O(log) per persistence refresh. The fix belongs
  in persistence, which is frozen, so MB026 deliberately did not make it
  (ADR-0016). First thing that will hurt at high event volumes.
- **A shipped launcher.** ✅ **Done** — shipped as Mission Brief 027.5.
  `kalpavriksha` recovers, discovers, starts the Runtime, and starts the
  Dashboard. See `docs/MISSION_BRIEF_027_5.md`.
- **⚠️ The Runtime path does not consult the Permission System.** Found by
  MB027.5 and verified by running it: an `IRREVERSIBLE` `delete_folder`
  completes with **no approval anywhere**. `FilesystemPlugin.invoke()`
  self-grants a `ONCE` permission on the Executor's key (the ADR-0005
  relay) assuming the Orchestrator already gated the call at the
  plugin/capability key — and the Runtime calls the gateway directly,
  never the Orchestrator. This contradicts **Constitution Rule 5**. It
  predates MB027.5 (MB024 built the path, MIT-001 certified it; MB023.1
  came closest with "`run()` is not a second boundary"), but the launcher
  makes it reachable in one command, so execution is opt-in until it is
  fixed. **The fix touches frozen components and needs its own Mission
  Brief** — most likely a permission check inside `PluginGateway`, or
  routing Runtime execution through the Orchestrator's existing gate.
  This is the highest-priority item on this list.

## Planned — next up

In the order the accumulated recommendations across Mission Briefs
002/003/003.1/004/004.1/005/022 converge on. Read through
`docs/architecture/KALPAVRIKSHA_VISION_V2.md`'s frozen terminology now
(e.g. "Reasoning Provider" for what this list still calls "Hermes"/
"ChatGPT" by their pre-Constitution names) — the Constitution's §21 maps
each role to the concrete product this roadmap already committed to.

1. **The real Planner**, replacing `cli.py`'s regex-based
   `parse_intent()`/`build_plan()` stand-in with an actual model call
   through the Model Router (Hermes first — no API key needed, keeps
   testing fast). This is the point at which `planner/planner.py` stops
   raising `NotImplementedError`, and the natural point to finally wire
   `MissionManager` into the live path as Shared Infrastructure's Mission
   State (`KALPAVRIKSHA_VISION_V2.md` §5.3), calling `Memory.persist_mission()`
   the way `MasterAgentSession._remember()` does today (see
   `MEMORY_ARCHITECTURE.md` §11-§12). Per the Constitution (§3.2), every
   `Step` the real Planner emits should also name an Expected Outcome —
   worth building in from the start now that Verification's design
   (`KALPAVRIKSHA_VISION_V2.md` §10, ADR-0011) depends on it, even though
   the Verification Subsystem itself isn't being built in this Miracle.
   Now has real proving ground to generalize against: fourteen
   capabilities and nine distinct conversational shapes as of Mission
   Brief 005, not three and two. Verify against the full existing
   `test_cli_session.py` suite (100+ assertions deep now) before intent
   recognition changes shape again — that suite is the regression
   contract this change must not break.
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
   Mission Brief 022's `BrowserPlugin` is a third instance of the relay
   pattern itself (proven, not just theorized), but see item 6 below for
   the *separate*, still-open Environment Session question it raised.
6. **Implement the AI Capability Broker** — MB027 froze the architecture
   (`AI_CAPABILITY_BROKER_ARCHITECTURE.md`) and the founder ratified it,
   so this is now an unblocked implementation brief. Deliberately listed
   here rather than inserted at the top, because sequencing it against the
   real Planner is a founder call, not a default — but note what it
   unblocks: **every Executive still to be built that needs AI** (Desktop,
   Research, Knowledge, Terminal, Git) would otherwise each pick its own
   provider, hold its own credential, and encode its own fallback ladder.
   It also retires `ModelRouter.select_provider()`'s hardcoded provider
   names (see Backlog). Scope it to the decision path first — registry,
   matrix, decision engine, cost ledger, approval gate. The learning loop
   is item 7.
7. **Implement the AI Infrastructure Executive, including the learning
   loop** — the machine-touching counterpart (`AI_CAPABILITY_BROKER_
   ARCHITECTURE.md` §11, §19; ADR-0018). Two phases, and they should stay
   separate briefs: **(a)** discovery, probing, inventory, benchmarking —
   all `READ_ONLY` except `RunBenchmark`, and the thing the Broker needs
   to be useful at all; **(b)** the learning loop and ecosystem mutation —
   `AnalyseUsage` producing `PolicyProposal`s through the existing
   human-gated queues, plus the `IRREVERSIBLE` install/remove/upgrade
   capabilities. Phase (b) has a hard prerequisite that is easy to miss:
   **it needs real decision history to learn from**, so it should not be
   built until the Broker has been running long enough to have produced
   some. Building the analytics before the data exists means calibrating
   guards against nothing.
8. **The Policy Simulator** — scheduled by founder directive 2026-07-29,
   deliberately not designed or implemented yet
   (`AI_CAPABILITY_BROKER_ARCHITECTURE.md` §19.8). Validates a proposed
   policy version against historical missions *before* it reaches the
   founder for approval, so approval happens against "this would have
   changed 34 of 1,206 decisions, here are five" rather than against a
   claim. Nearly free to build, because §6.6's determinism-and-replay
   guarantee already makes past decisions re-derivable — the simulator is
   that mechanism pointed at a different policy version. Sequenced after
   item 7(b) for the same reason: it needs history to replay. **Build the
   fact/estimate distinction in from the start** — replay can say what
   would have been *selected* (fact), never whether it would have
   *succeeded* (estimate), and blurring them manufactures confidence at
   exactly the wrong moment.
9. **A second stateful Worker** (Terminal is the natural next choice) —
   the real test of whether `BrowserSessionManager`'s open/get/close/list
   shape (Mission Brief 022, `BROWSER_WORKER_ARCHITECTURE.md` §4)
   actually generalizes into a shared `EnvironmentSessionManager` base,
   the same way Mission Brief 003 tested whether the `Action` Contract
   generalized past one example. Not urgent — nothing today needs a
   second Environment, and one example doesn't justify the abstraction
   yet.

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
