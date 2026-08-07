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

| **028.0** — Runtime Permission Boundary (Safety Fix) | Restored **Constitution Rule 5** as a hard architectural guarantee: nothing irreversible executes without founder approval, on any path. The defect: two permission gates, two execution paths, and both gates on one path — the Orchestrator's check never ran on the Runtime path, and the Executor's was pre-satisfied by ADR-0005's relay carrying a decision nobody made. Fix: one `ApprovalGate` protocol defined inside `runtime/` (the MB025 `CheckpointSink` precedent, so the Runtime gains no Permission System dependency), consulted at `_handle_task()` — the only funnel — and **failing closed**: no gate wired means nothing runs at all. Ran in two halves as the brief required: designed, stopped at ADR-0019, ratified, then implemented. Evidence outlives the process, authority does not — a replayed approval restores the record, never a usable grant. Verified live: unapproved delete refused with the folder intact, approved delete completes with who/what/when in the audit, and after a restart the same task is refused again. MB027.5's `--enable-execution` flag removed, its hazard gone. 22 new tests, 1015 passing. Key design decision: ADR-0019. Full detail: `docs/MISSION_BRIEF_028_0.md`. |

| **028.1** — Founder Approval Workflow | Turned approval from architecture into a workflow: `kalpavriksha` now shows an Approval panel with everything a decision needs (capability, executive, risk tier, reason, impact, timestamp), and `approve 1` / `reject 1` / `defer 1` / `approve all` decide it — no flags, no harnesses. The change under it: **an unanswered request is no longer a refusal**; the task waits, and the Runtime re-offers it the moment the founder answers. New Approval Queue in Mission Control beside its two existing human-gated queues; immutable ledger of every decision; deferred requests survive restart; rejected work fails gracefully and is never retried; optional timeout, disabled by default. **ADR-0016 is untouched** — the Dashboard still renders from a frozen snapshot and the Console (composition root) does the acting. Verified live across all eight steps of the brief. 33 new tests, 1051 passing. Key design decision: ADR-0020 (**Proposed** — ships frozen-component changes). Full detail: `docs/MISSION_BRIEF_028_1.md`. |

| **029** — Founder Dashboard V2 | Pure UX, **zero architecture change** (proved by a `git diff` over Runtime/Mission Control/Persistence: empty). The dashboard now opens on a **Founder page** answering the only three questions a founder has — what is it doing, does it need me, what next — with the nine engineering panels moved one keystroke away behind `[V]`. New **view model** layer (`dashboard/founder.py`) between the read model and rendering: a web, desktop, or phone front-end consumes `FounderView` and writes its own renderer, touching nothing else — Deliverable 10, done by layering rather than by promise. Status is one human sentence with a reason, and *waiting-on-you outranks needs-attention* because being blocked on the founder is not the same as being broken. Where MB029 asked for numbers that do not exist, they are honest: **Confidence** is a stated reading of the verification record (or absent), self-development bars are **transcribed from the roadmap** with each one naming what it is a reading of, and **Time saved is reported as not measured**. Recommendations come from the roadmap, filtered by live state. 76 new tests (40 asked), 1138 passing. No ADR — none was needed. Full detail: `docs/MISSION_BRIEF_029.md`. |

| **030** — Desktop Executive (Foundation Layer) | Kalpavriksha's eyes and hands over the local machine: twelve capabilities discovering installed software, versions, and running processes, and launching, opening, or closing applications. **Zero architecture change** — a `git diff` over Runtime, Mission Control, Persistence, Executor, and Plugins is empty, so no ADR was needed. Adding a twelve-capability Executive for free is the strongest evidence yet that MB002's Action contract generalises. It **executes and never decides**: a test parses the whole package for provider vocabulary and fails on any hit, and `category="ai"` is a Dashboard grouping that nothing reads to make a choice. `CloseApplication` and `ExecuteCommand` are `IRREVERSIBLE`, so ADR-0009 makes each a fresh founder decision; `ExecuteCommand` is argv-only. Found three real defects by scanning the founder's actual machine — error text sitting in the version column, UTF-16 output from `wsl`, and a multi-line error filling an inventory row. The Dashboard gains Machine Readiness, and never scans: the launcher submits a scan objective through Mission Control (Rule 4) and hands the result in (ADR-0016 Decision 5). No click, type, mouse, OCR, or vision — Deliverable 7 keeps those for a later brief. 228 new tests (100 asked), 1367 passing. Full detail: `docs/MISSION_BRIEF_030.md`. |

| **031** — AI Capability Broker (Core Decision Engine) | The engine ADR-0017 froze: given provider profiles and a task, which provider should be used — deterministically, auditably, and **without ever contacting a model**. Eight founder policies, a configurable quality floor, ranked candidates, structured refusal, policy versioning, and byte-identical replay. **Zero changes to anything existing** (a `git diff` over eight packages is empty) and **100% statement coverage** of the new `broker/` package. The forbidden list is enforced by tests rather than trusted: no network or subprocess imports, no vendor name anywhere, no execution surface, and no `master_agent` import outside `broker` itself — a kernel service consulted from everywhere must depend on nothing. **Found a real bug by running it:** the first draft's blended quality-per-cost score picked a paid cloud provider over a free local one that also cleared the floor, silently overriding Deliverable 8 — exactly the failure ADR-0017 Decision 3 predicted when it rejected blended scores. The key was deleted; policies now differ by their *floor*, not a hidden weighting. 180 new tests, 1543 passing. Not yet wired to anything — that is the next brief. Full detail: `docs/MISSION_BRIEF_031.md`. |

| **032** — Wiring the AI Capability Broker | The Broker stops being a component and becomes the system's only answer to "which AI?". `Task -> Broker -> DecisionRecord -> Approval -> Execution`, with nothing reaching a provider before the first four have happened. The four hardcoded branches in `ModelRouter.select_provider()` are gone, and with them the last product names in Brain logic — *"I need this done well"* is now a **quality floor**, not a route to a named cloud model. **Exactly one frozen file changed**, named in advance by a ratified ADR (ADR-0017's Consequences and Constitution Amendment 2 §3.3), and recorded in the same `RATIFIED_EXCEPTIONS` list every previous amendment used. **Zero new event types, zero new approval paths, zero new snapshot keys**: paid selections ride MB028.1's Approval Queue through its published contract, so `approve 1` in the existing console decides a provider question exactly as it decides a filesystem one. Provider profiles are read from the Desktop Executive's machine scan rather than a hardcoded list, and *"nothing has scanned yet"* is reported as absence rather than assumed present — the discipline that stops a selection succeeding and the call failing later. Every decision, including every refusal, is stored with its policy and provider profiles and **replays against those** rather than today's: proven across a restart with the founder's policy changed in between. New founder panel shows the selected provider, the Broker's own sentence explaining why, the cost tier, and the quality tier — labelled `declared`, because no benchmark store exists and a guess presented as a measurement is a lie. A Broker that cannot be built **fails closed**: no fallback, because a fallback is itself a provider decision. **Two real defects found by running it**, both in the new panel: a refusal rendered with a green tick and "Approval not required" underneath, and the Broker's reason truncated mid-number at *"quality 0.72 clears the qual"*. 397 new tests, 1945 passing, **100% statement coverage** of the new package and the rewritten router. Full detail: `docs/MISSION_BRIEF_032.md`. |

| **033** — Ollama Provider & the Token Economy | Kalpavriksha thinks for the first time. MB032 made the Broker the single authority on *which* AI and nobody answered; this is the execution path — `Task -> Broker -> Ollama -> structured response -> ledger` — proved live against the founder's own daemon (`gemma4:latest`, 22.8 s, 30 tokens, free, recorded and replayable). **Zero frozen files modified**: MB032 needed one ratified exception, this needed none. The network went into a package of its own (`providers/`) rather than weakening MB032's purity tests — the wiring layer imports one pure-dataclass module from it and so can *record* an execution without acquiring the ability to *perform* one, and `providers/__init__.py` re-exports nothing so importing the package cannot pull in an HTTP client. A provider is registered in a **second registry**, never as an Executive: ADR-0017 Decision 8 says an AI Capability is not a Constitution Capability, so a provider must not appear in Mission Control, the Runtime's gateway map, or the Executive list. **Rule 5 is the load-bearing one** — five named failure outcomes, every one returned as data, and never a silent substitution, because a system that quietly swaps providers cannot learn anything true about either. Live: a missing model answers `HTTP 404: model 'x' not found` *with the list of models that are installed*; a dead daemon answers `is Ollama running at ...?`. A timeout is deliberately never retried. The **Token Economy** begins accumulating, and refuses to invent: `money_saved` is not "what the frontier model would have cost" — that number is unfalsifiable, always flattering, and grows fastest on the days the system does least — it is the recorded cost of work that happened once and was reused instead of repeated. Which makes every saving zero in this build, with the panel saying *why* rather than leaving a founder to infer it. `PromptCache` ships as the interface plus an always-miss default, because nothing verifies generated text yet and a cache that stored unverified output would make Kalpavriksha repeat a wrong answer faster. **Three defects found:** a latent `NameError` in the Dashboard caught by the linter (every test happened to have both a latency and a cost), economy totals that read as part of the last decision, and an MB032 test passing on a substring (`def execute` matching `def executed`). 350 new tests (the brief asked for 250), 2295 passing, **100% statement coverage** of both new packages. Full detail: `docs/MISSION_BRIEF_033.md`. |

| **034** — Persistent Founder Memory | Kalpavriksha stops being a stateless executor. It now remembers what the founder told it — preferences, decisions, what worked, what failed — **across restarts, with no LLM anywhere near the answer**. Proved live: four facts typed into one process, recalled by a fresh one, a repeat folded into the original, and a word nobody wrote honestly returning nothing. **Zero frozen files modified** and no ADR needed. `memory/` was not new — MB004 shipped Layers 1–3 there — so the five modules compose *beside* them and `cli.py`'s existing path is untouched; this is Layer 4 arriving, which `memory/future.py` had reserved. Ten categories, four importance levels, six sources, all closed vocabularies enforced at write time. **Retrieval is deterministic and the ranking is stated rather than tuned** — tag 8, title 4, summary 2, body 1, ties broken by importance then recency then id — so the same query returns the same list forever and the order never depends on insertion order. Matching is exact: `fail` does not find `failure`, which is a surprise a founder can see rather than a stemmer matching the wrong thing invisibly. Automatic memory rides the **existing** Event Bus, subscribed per event type rather than to everything, because the Runtime publishes a heartbeat every cycle. Saying the same thing twice is one memory, and repeating it can raise its importance but never lower it. Memory lives **beside** the state directory, not inside it: a recovery may legitimately discard operational state and must never discard what the founder said. A corrupt knowledge file is **moved aside, never overwritten** — a founder can open a `.corrupt` file and copy their notes out; they cannot recover a file the program replaced. The index is derived, so a bad one is rebuilt in silence, checked by equality rather than size because an index with the right number of wrong entries is the failure hardest to notice. **Three defects found by running it:** a full stop the founder did not type ("exceeds 0.9."), missions remembered by UUID because the completion event carries no description, and every restart writing "Recovered 0 objective(s)" until that line owned the whole panel. 315 new tests (the brief asked for 250), **100% statement coverage** of all five modules. Full detail: `docs/MISSION_BRIEF_034.md`. |

| **035** — Verifying Generated Text | Kalpavriksha can finally tell whether an answer was any good — and two features that shipped inert now work. MB033's Prompt Cache never hit and MB034's Prompt Library had no automatic writer, both waiting on the same missing sentence. ADR-0011 froze the Verification Subsystem long ago and `BrowserVerifier` proved the shape generalises, so this is the **second concrete Verifier** and it is a handful of lines. **Zero frozen files modified** and no ADR needed: `verification/` is itself frozen, so the new Verifier lives outside it and implements the published contract, which is what a Worker's Verifier does anyway. **The one interpretation required:** ADR-0011 says re-observe reality fresh, and for generated text *the answer is the artefact* — so the observation is re-derived from the text by deterministic measurement (length, word count, JSON shape, what it contains) and the provider is never asked whether it thinks it did well. **No model judges another model**: that recursion is the one ADR-0017 refused to start, and a verdict here is arithmetic over an expectation stated *before* the answer arrived, which is also the only kind that is falsifiable. Consequences: the cache now stores on **evidence rather than a caller's promise** (and `partially_matched` is deliberately not enough), the cache **ships on** because the reason it was off is gone, a checked prompt writes itself into the Prompt Library through an outbound port, and the founder page shows the verdict with `not checked` distinguished from `not matched`. **Two defects found by running it:** "at least 1 word" passed on a blank answer because the regex ended in `\S*`, and a cache hit ignored what the *new* caller asked for — an answer verified against one expectation was served for another, which is how "everything reused was verified" quietly stops being true. 153 new tests, 2763 passing, **100% statement coverage** of both changed modules. Full detail: `docs/MISSION_BRIEF_035.md`. |

| **036** — The Planner | An objective becomes steps, and **every step says what it expects**. `ExpectedOutcome` has named the Planner as its author since ADR-0011 froze it; nothing was one, which is why MB033's Prompt Cache and MB035's Prompt Library both filled only for callers that happened to state an expectation, and why Constitution §3.2 was a promise rather than a mechanism. Those were one gap. **Zero frozen files modified** and no ADR needed. `Intent`/`Step`/`MissionPlan` moved to `plan.py` and are re-exported, so the Orchestrator and `cli.py` import them from exactly where they always did. **There is no second parser:** the Planner reads its document out of `Evidence.observation["json"]` — the value MB035's `observe()` produced *while judging the reply* — so the artefact that was verified and the artefact that gets executed cannot be two objects that merely usually agree. A provider states success over **six keys, not raw `ObservationCheck`s**, because letting it write dot-paths would let it invent a field no Verifier observes: a check that can never fail, which is worse than no check. An unsupported key is refused, never dropped — a dropped key is an expectation the founder believes is being checked and is not. **Five ways it stops and none invents a plan**, including a reply with no `Evidence` at all: MB032 refused a fallback provider, and a fallback *plan* is worse. `{"steps": []}` is the provider's honest "the catalogue cannot do this" and gets its own refusal code, because an empty plan reaching the Runtime would complete instantly and report success. The quality floor for planning is a **knob, not a hardcoded `True`** — ADR-0017 gives floors to the founder's policy, and setting one here would be the Planner deciding the founder should pay. **Three findings from running it live**: an unscanned machine correctly reported every provider as absent and spent no tokens; `OllamaConfig.model` still defaults to a model the founder does not have; and a planning prompt carrying the whole 26-capability catalogue **timed out at MB033's 120 s default**, which was sized for a short answer — the first caller with a genuinely large prompt found that one global timeout does not fit two shapes of work. Not wired to `cli.py` — that is MB037, the same build-then-wire rhythm the Broker got. 165 new tests, 2928 passing, **100% statement coverage** of all seven new modules. Full detail: `docs/MISSION_BRIEF_036.md`. |

| **037** — Planner Integration | The Planner stops being a component and becomes the only way work starts. A founder types a sentence into `kalpavriksha` and it becomes `Objective -> Planner -> MissionPlan -> Mission Control -> Executive -> Broker -> Provider -> Verifier -> Evidence -> Memory`, with nothing bypassed. **Zero frozen files, no ADR.** The finding that shaped the brief: **almost every guarantee it asked for already existed, unconnected** — the Dispatcher has ordered by dependency since MB023, the Runtime has verified before completing since MB024/MB035, and MB034's memory already subscribed to failure. Most of all, **MB023 gave `Task` an `expected_outcome` field it had no producer for**, with a comment naming Constitution §3.2 and the Planner that did not exist yet. MB036 built the producer; this is the arrow between them, and it is a 1:1 field copy because the seam was cut three briefs ago. So `missions/` is three small modules, and that is the result rather than a shortcut. **The gate judges fields, not producers**: a plan missing a capability, inputs, an expected outcome or dependency information is refused *before an `Objective` exists*, so there is no path on which execution could infer the missing part — and a hand-built plan from anywhere is held to the same rules. **Priority and complexity are descriptive, never directive**: closed vocabularies, optional in the document, and they never reach `Task`, because a Planner that could reorder execution by labelling a step `critical` would own lifecycle. **Replay cannot re-run**: `missions/history.py` imports nothing from `providers/`, `ai_infrastructure/`, `plugins/`, `broker/`, `httpx`, `urllib`, `socket` or `subprocess`, so there is nothing in reach that could contact a provider. `cli.py` **stopped pretending to plan** — its one-step `MissionPlan` is now a `CapabilityCall`, and all 66 of `test_cli_session.py`'s assertions pass unchanged, which is the evidence it was a rename rather than a behaviour change; an AST test over all of `src/` now asserts `planner/parsing.py` is the only producer of a `MissionPlan`. The founder page gains one CURRENT MISSION slot showing the current step, what it expects, what is waiting on a dependency and what failed verification — and **no field anywhere for a prompt, a reply, or a provider's reasoning**. **Three defects found**: `PanelStatus()` defaults to available, so an absent plan rendered as `0/0 steps`; the fix for that then hid a real plan; and a Planner given a catalogue that is not Mission Control's own registry produces plans the Dispatcher has never heard of. **What was deliberately not built: pause, resume and cancel.** The brief assigns them to Mission Control, which publishes none of them — adding them edits frozen files (the brief allows none) and building them outside would be a second scheduler (the brief forbids one). The brief's own instruction decides it: the Constitution wins. A test asserts their absence so nobody mistakes it for working. 275 new tests, 3203 passing, **100% statement coverage** of all three new modules. Full detail: `docs/MISSION_BRIEF_037.md`. |

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
- **Wire the Broker into the Runtime.** ✅ **Done** — shipped as Mission
  Brief 032. The Model Router asks the Broker, every decision is recorded
  against its task, paid selections route into MB028.1's Approval Queue,
  and a missing Broker fails closed. See `docs/MISSION_BRIEF_032.md`.
- **Retire `ModelRouter.select_provider()`'s hardcoded provider ladder.**
  ✅ **Done** — shipped as Mission Brief 032. The four branches and
  `ModelRouterConfig.default_provider` are gone; the router keeps its
  `generate()` interface and its role as the Brain's single door to
  reasoning, and holds no provider name at all (asserted by an AST test
  and a vendor grep).
- **Run what the Broker chooses.** ✅ **Done** — shipped as Mission Brief
  033. `OllamaProvider` executes real prompts through the Broker's
  decision, and every execution is recorded with its latency, tokens,
  cost and retry count. See `docs/MISSION_BRIEF_033.md`.
- **A verifier for generated text.** ✅ **Done** — shipped as Mission
  Brief 035. The Prompt Cache stores on evidence, the Prompt Library has
  an automatic writer, and the founder page shows the verdict. See
  `docs/MISSION_BRIEF_035.md`.
- **A Planner that states what each step expects.** ✅ **Done** — shipped
  as Mission Brief 036. `parsing.validate()` refuses a plan whose step has
  no expectation, so §3.2 is a gate rather than a promise. See
  `docs/MISSION_BRIEF_036.md`.
- **Wire the Planner in.** ✅ **Done** — shipped as Mission Brief 037. A
  founder objective now goes `Planner -> Mission Control -> Runtime ->
  Verifier -> Memory`, and `cli.py` no longer produces plan vocabulary.
- **`_current_objective_id` never advances past the first objective.**
  `MissionControl.submit_objective()` sets it only when it is `None`, so
  after the launcher's boot machine-scan every later mission leaves it
  pointing at the scan — and `founder_state()` therefore describes a
  finished scan forever. Found while running MB037. It does **not** affect
  the founder page, because MB037's CURRENT MISSION panel reads the plan
  history rather than `founder_state()`, and it replaces the older mission
  panel whenever a plan exists. But `founder_state()` is a published
  contract other things may consume, and the fix is in frozen
  `mission_control/`, so MB037 deliberately did not make it — the same
  posture MB026 took toward `count_events()`.
- **Pause, resume and cancel a mission.** MB037 could not build them and
  says so out loud rather than half-building them. Mission Control
  publishes no pause/resume/cancel and has no paused `TaskState`; adding
  them edits frozen `mission_control/` and `dispatcher.py`, and building
  them outside would be a second scheduler gating dispatch — which is
  precisely the "single orchestration authority" rule. **This is a
  founder decision and it needs a ratified ADR**, the same posture as
  ADR-0015 and ADR-0020. `test_missions_lifecycle.py` fails the day
  somebody adds one without that conversation.
- **Adaptive re-planning.** MB037's pipeline never re-plans: a failed
  mission stays failed until a founder says otherwise. Revising a plan at
  the exact moment the system has demonstrated it got something wrong
  needs its own safety argument, and Constitution §11 reserves strategic
  recovery for the Brain.
- **A timeout that fits the prompt.** MB036 Finding 3, confirmed worse by
  MB037: a planning prompt carries the entire capability catalogue (26 on
  the founder's machine) and asks for structured JSON, and
  `OllamaConfig.timeout_seconds`' 120 s default — sized in MB033 for a
  short answer — is not close. Even 540 s did not finish on CPU. One
  global timeout does not fit two very different shapes of work, and this
  is the single thing most likely to make a founder conclude the system
  does not work. **Highest priority after the input-schema gap.**
  ✅ **ACCEPTED** — the original production failure is resolved. Acceptance
  first failed (`timed_out_ttft`, 0 tokens in 164 s) and exposed three
  causes, all fixed in MB038A (`docs/MISSION_BRIEF_038A.md`): the decode
  window was zero because no caller stated an output size, both rates
  were ~2x optimistic because Step 0 measured 24-token completions, and
  cold-start model load (33 s, measured) was modelled nowhere. Re-run
  from a cold model: **planned, verified `matched`, 325.6 s against a
  658.7 s derived budget**, TTFT 168.1 s against 358.7 s, max inter-token
  gap 363 ms against 5 s. `bound_by: estimate` — derived from measured
  throughput, not clamped to a ceiling. The decisive call was calibrating
  on observed wall-clock TTFT rather than the daemon's own
  `prompt_eval_duration`; trusting the internal counter would have left a
  1.2% margin.
  ✅ **Stage A built** — shipped as MB038. The Planner now states a
  workload class and its prompt; the Broker derives three deadlines from
  measured throughput; the adapter enforces them and no longer retries
  anything. 3457 passing, 240 new tests, **100% coverage of all eight new
  modules**, **zero frozen files touched and no ADR created** — the one
  edit that looked unavoidable (extending the Broker request vocabulary)
  was resolved by subclassing the frozen dataclass instead. Delivery
  record, invariants and limitations:
  `docs/MISSION_BRIEF_038_DELIVERED.md`. Stage B (mission SLA, Runtime
  enforcement, founder cancellation verb) remains ADR-gated.
  📐 **Architecture — `docs/MISSION_BRIEF_038.md` is canonical**
  and is the authoritative specification all timeout work follows. Seven
  residual uncertainties are recorded under Open Reconciliation (§15),
  each with the position taken so implementation is unblocked and what
  would change it. The short version:
  raising the number only moves the failure (a timeout large enough for
  planning makes a *dead* daemon take nine minutes to report), and a
  single wall-clock timeout cannot tell a provider that is **thinking**
  from one that is **hung** — at second 400 they are byte-for-byte
  identical. Three shifts: **one deadline becomes three** (total,
  time-to-first-token, stall), **a duration becomes an absolute instant**
  (a duration is re-based at every hop and silently multiplies), and **a
  constant becomes a derived, recorded value**. Ownership is exclusive —
  the Broker *computes* the budget, the Provider Adapter *enforces* it
  per call, the Runtime enforces per task, Mission Control owns the
  ceiling that clamps all of them, and the Dispatcher owns nothing
  time-related because a deadline must never reorder work. Retry belongs
  to the layer that owns the failure's meaning: transport faults to the
  adapter, task failure to the Runtime, and **a timeout is never retried
  without a new Broker decision**. Cancellation is unified as *a deadline
  set to now*, so four triggers share one propagation path. Replay reuses
  recorded budgets and never recomputes — only the Policy Simulator
  recomputes, and must label the result an estimate.
  **Phase 1 — the whole provider-call path — needs no ADR and no frozen
  edit**, and resolves every failure observed so far. Phase 2 (mission
  deadlines, Runtime enforcement, cancellation) needs ADR-0021/0022/0023,
  and **ADR-0023 is the same decision as MB037's pause/resume gap** — one
  lifecycle amendment, not two. Highest named risk: Ollama serialises per
  model, so an abandoned call can block the next one and budget maths
  that assumes independence is wrong. First backlog item is a
  measurement spike, not code.
- **`OllamaConfig.model` defaults to a model the founder does not have.**
  ADR-0002 chose Hermes; the machine runs `gemma4:latest`. MB033's
  structured 404 reports it correctly every time, which is the system
  working — but it is the second brief to hit it.
- **Nothing publishes a capability's arguments or its result shape.**
  MB036 Findings 4 and 5, and the highest-value thing that brief left
  behind. Its first live plan named the right two capabilities and got
  **both payloads wrong** — `path` where `CreateFolder` requires `name`,
  `file_path` where `WriteFile` requires `path` — because the catalogue
  publishes a name, a sentence and a risk tier, which is all
  `CapabilityDescriptor` carries. The seam exists and is empty:
  `CapabilityManifest.input_schema` and `output_schema` are declared in
  `plugins/base.py` and populated by nothing in the codebase. The same
  gap makes a step's *expectation* a guess at a result string the model
  has never seen — falsifiable, which is the point, but not necessarily
  right. Filling it is the difference between a plan that reads correctly
  and a plan that runs. It touches frozen `plugins/`, so it needs a
  ratified exception or an adapter outside it reading
  `Action.required_parameters()`.
- **Re-planning after a step fails.** Constitution §11 reserves strategic
  recovery for the Brain and MB024's Runtime does mechanical retry only.
  A Planner that revises a plan mid-mission is a separate brief with a
  separate safety argument.
- **Semantic correctness.** MB035's checks are structural: they catch a
  blank answer, a refusal, a truncation, a wrong format. They cannot catch
  an answer that is fluent, well-formed and wrong. ADR-0017 Decision 5
  named that gap for benchmarking and no deterministic check closes it.
- **A Knowledge Executive.** MB034 built the structured memory; the layer
  above it — ingesting the founder's own documents and notes, and keeping
  them in step with what Kalpavriksha learns — is deliberately *not* part
  of it. `memory.search()` is the contract that layer consumes, and MB034
  froze it so this can be built without modifying anything beneath.
- **Inference over the memory.** `Recurring Lessons` and `Open Questions`
  have no automatic writer, and `confidence` is always 1.0, because
  everything stored today is stated or observed. Drawing a lesson from
  several failures is the first thing that would write an *inferred*
  record, and it needs a rule for what confidence means before it needs
  code.
- **Streaming a local answer.** MB033 does one request, one answer, one
  timeout, so a 22-second local generation shows nothing until it
  finishes. Needs `httpx` behind the existing `Transport` protocol and a
  Dashboard that can render a partial.
- **A cost ledger, so budgets can be budgets.** ADR-0017 §9 froze the
  design. MB033 records and totals cost per execution; nothing enforces a
  ceiling yet, which is what turns a total into a budget.
- **A benchmark store, so quality stops being declared.** Every provider
  quality number in `ai_infrastructure/catalog.py` is a stated first
  guess. ADR-0017 Decision 5 says measurement beats declaration where both
  exist — today only declaration exists, and the Dashboard says so on
  every row. MB033 records `quality_declared` on every execution
  specifically so a benchmark can be compared against the claim it
  replaces. This is also what ADR-0018's learning loop needs before it can
  propose anything.
- **Per-model provider profiles.** A provider is currently a *runtime*, so
  the Broker cannot choose between two models on the same Ollama. Telling
  them apart needs the benchmark store above.
- **Broker decisions in the Audit Stream.** They are durable, replayable,
  and on the Dashboard, but a `BROKER_DECISION` event type would mean
  editing a frozen file for reporting rather than for a guarantee — so
  MB032 deferred it to a brief that can weigh that properly.
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
- **The Runtime path did not consult the Permission System.** ✅ **Done**
  — fixed by Mission Brief 028.0 (ADR-0019). Kept as the record of what it
  was: `FilesystemPlugin.invoke()` self-granted a `ONCE` permission on the
  Executor's key (the ADR-0005 relay) assuming the Orchestrator had
  already gated the call — and the Runtime calls the gateway directly,
  never the Orchestrator. So an `IRREVERSIBLE` `delete_folder` completed
  with **no approval anywhere**, contradicting Constitution Rule 5. It
  predated MB027.5 (MB024 built the path, MIT-001 certified it; MB023.1
  came closest with "`run()` is not a second boundary") and was found only
  when the launcher made it reachable in one command. Now closed by one
  `ApprovalGate` at the Runtime's single funnel, failing closed.
- **An approval interface.** ✅ **Done** — shipped as Mission Brief 028.1.
- **Ratify (or reject) ADR-0020's frozen-component changes.** MB028.1
  ships an Approval Queue in `mission_control/`, a third Runtime outcome,
  and one persistence key. Each is additive and isolated — reverting them
  removes the workflow and restores MB028.0 exactly. A founder decision,
  same posture as ADR-0015.
- **An approval history view.** The ledger is durable and queryable, but
  nothing renders it: the founder sees pending work, not past decisions.
- **Desktop interaction** — click, type, mouse, windows, OCR, vision.
  MB030 deliberately excluded all of it (Deliverable 7). `BringToFront`
  and `FocusWindow` are registered and report honestly that focus is not
  built, so the seam is there when the brief comes.
- **Desktop `unavailable` detection.** The state exists and renders, but
  nothing produces it: a Docker daemon that is installed but dead still
  reads as Ready.
- **Undo a rejection.** Rejection is final for that task; a founder who
  rejects by mistake must resubmit the objective.

## Planned — next up

In the order the accumulated recommendations across Mission Briefs
002/003/003.1/004/004.1/005/022 converge on. Read through
`docs/architecture/KALPAVRIKSHA_VISION_V2.md`'s frozen terminology now
(e.g. "Reasoning Provider" for what this list still calls "Hermes"/
"ChatGPT" by their pre-Constitution names) — the Constitution's §21 maps
each role to the concrete product this roadmap already committed to.

1. **The real Planner** — ⏳ **half done.** Mission Brief 036 built it:
   an objective becomes a `MissionPlan` whose every Step carries an
   `ExpectedOutcome`, through the Model Router's Broker path, proved live
   against the founder's own daemon. What remains of this item is the
   *wiring* — replacing `cli.py`'s regex stand-in, and folding
   `MissionManager` into the live path as Shared Infrastructure's Mission
   State — which MB036 deliberately left to its own brief. The rest of
   this entry is the original text, kept because the `test_cli_session.py`
   warning at the end of it is exactly why the split happened.

   Replacing `cli.py`'s regex-based
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
