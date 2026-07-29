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

## ADR-0009: PermissionCategory + the IRREVERSIBLE grant rule (Mission Brief 005)
Added `PermissionCategory` (`read`/`write`/`modify`/`delete`/`system`) to
`plugins/base.py` as a purely descriptive axis alongside `RiskTier` —
never consulted by `PermissionSystem.check()`'s actual gating logic. Also
added one real mechanism change to `check()`: an `always_for_capability`
grant can never satisfy a check for an `irreversible`-tier capability, no
matter how it was created — destructive actions (`delete_file`,
`delete_folder`) require a fresh decision every time, with zero changes
to `grant()`'s signature or any existing call site. See
`docs/adr/0009-permission-category-and-irreversible-grant-rule.md`.

## ADR-0010: Shared Infrastructure layer (Mission Brief 021 Revision 3)
Introduced a third layer beneath both the Executive Brain and the
Universal Executive Operator: Capability Registry, Permission System,
Mission State, Memory, Configuration, and aggregated Telemetry/Evidence.
Fixes a verified contradiction — `ModelRouter` (Brain) depends directly on
`PluginRegistry`, which the prior Constitution assigned exclusively to the
Operator. See `docs/adr/0010-shared-infrastructure-layer.md`.

## ADR-0011: Verification as an independent subsystem (Mission Brief 021 Revision 3)
Execution produces effects; a distinct Verification Subsystem produces
Evidence by comparing a fresh Observation against an Expected Outcome the
Planner attaches to each `Step`; Evidence flows back to the Brain. Fixes
Verification being nominally but not structurally separate from Execution
in the prior Constitution. See
`docs/adr/0011-verification-as-independent-subsystem.md`.

## ADR-0012: The Knowledge Lifecycle (Mission Brief 021 Revision 3)
`Execution → Evidence → Knowledge Candidate → Promotion Review → Permanent
Knowledge → Future Reasoning`. Brain nominates Candidates; Promotion
Review (human-gated for Founder Edition, deliberately not named
"Verification" to avoid colliding with ADR-0011) approves or rejects;
Permanent Knowledge is revocable if later Evidence contradicts it. See
`docs/adr/0012-knowledge-lifecycle.md`.

## ADR-0013: Multi-Operator / Environment Instance architecture (Mission Brief 021 Revision 3)
Defined Operator Instance, Environment Instance, and Environment Session as
first-class concepts so the architecture scales to multiple desktops,
browsers, and VPS instances without redesign — explicitly not a
distributed-systems design, and today's single-Operator-Instance,
sequential implementation is unchanged. See
`docs/adr/0013-multi-operator-environment-instance-architecture.md`.

## Mission Brief 021, Revision 3 (2026-07-26): Founder Constitution Freeze
Design-only — no code, no tests, no packages. Resolved every gap the
independent architecture audit found in `KALPAVRIKSHA_VISION_V2.md`
(Revision 2): introduced Shared Infrastructure (ADR-0010), made
Verification structurally independent (ADR-0011), formalized the Knowledge
Lifecycle (ADR-0012), scrubbed product-specific terminology (Hermes,
ChatGPT, Ollama, VS Code, Obsidian) from every architecture-defining
section in favor of role-based terms, designed for multiple Operators
(ADR-0013), placed every previously-unowned component (`MasterAgentSession`,
`MissionManager`, `Reporter`) exactly once, consolidated three sets of
duplicated rules to one canonical statement each, froze sixteen
architectural terms to exactly one meaning each (retiring "Task" as an
alias for `Step`), and labeled every section FROZEN / RESEARCH-BACKED /
EVOLVABLE / IMPLEMENTATION DETAIL. Final Founder Review: **the Constitution
is frozen** — `ROADMAP.md`'s next five planned items can be implemented
without further Constitution changes; three named architectural items
(in-mission recovery decision procedure, stateful Environment Sessions,
concurrent multi-Operator dispatch) remain open but block only the
specific future capabilities that need them, not current roadmap work.
Full detail: `docs/MISSION_BRIEF_021_REVISION_3.md`,
`docs/architecture/FOUNDER_CONSTITUTION_FREEZE.md`.

## ADR-0014: "Executive" and "Worker" name the same role (Mission Brief 023)
MB023 introduced "Executive" for the role the frozen Constitution §17
already calls "Worker" (and MB022 shipped as `BrowserWorker`). Rather than
renaming the founder's deliverables or renaming shipped tagged code, the
two are declared synonymous with `Worker` canonical; §17 records the alias
and `FOUNDER_CONSTITUTION_FREEZE.md` was amended in the same commit, as
the freeze process requires. First amendment made under that process. See
`docs/adr/0014-executive-and-worker-terminology.md`.

## Mission Brief 023 (2026-07-26): Mission Control & Self-Development Infrastructure
Built the runtime coordination layer — Universal Event Bus, Capability
Registry, Executive Registry, Worker Lifecycle, Task Dispatcher,
Self-Development Queue, Knowledge Acquisition Queue, Audit Stream, Founder
State (backend only), and the Communication Contract — as a new
`mission_control/` package. Design-first
(`MISSION_CONTROL_ARCHITECTURE.md`). Three decisions worth remembering:
(1) the Executive/Worker terminology reconciliation above; (2) the
knowledge-promotion gate is enforced in code — advancing past
VERIFICATION requires `human_approved=True`, and the refusal is published
as an auditable event, making ADR-0012 mechanical rather than a
convention; (3) "Mission Control never performs work" is a test that
parses every module's imports, not a claim in a docstring. Registration
uses an adapter that reads a plugin's existing manifest, so the real,
untouched `FilesystemPlugin` and `BrowserPlugin` register with zero
modification — the brief's central acceptance criterion. One real bug
found by the tests: the dispatcher assigned a second task to an already-busy
Executive because availability ignored `current_task_id`. 107 new tests,
461 passing, zero regressions. Full detail: `docs/MISSION_BRIEF_023.md`.

## ADR-0015: Persistence strategy (Mission Brief 025) — **PROPOSED, needs ratification**
Snapshots for state + an append-only event log for history; JSON files
rather than SQLite (Memory's row store answers a different question and
stays unchanged); atomic writes; interrupted tasks quarantined rather than
re-run. Contains **three additive changes to frozen components**, each
required by an MB025 deliverable and each isolated/reversible: a
non-publishing `restore_objective()` on `TaskDispatcher` + `MissionControl`
(Rule 4 forbids reaching into `_objectives`, and `submit()` would
republish creation events), plus `depends_on` on `TASK_CREATED` and
`health` on `EXECUTIVE_REGISTERED` payloads (without them a
replay-recovered system executes out of dependency order, or is inert).
Deliberately marked *Proposed* per MB025's "propose an ADR rather than
making unilateral architectural changes". See
`docs/adr/0015-persistence-strategy.md`.

## Mission Brief 025 (2026-07-26): Persistent Runtime State Engine
Kalpavriksha now survives process restarts. New `persistence/` package:
a service that subscribes to the Event Bus, versioned+checksummed
snapshots, event replay, and one-call restart recovery. Rules enforced
mechanically — an AST-walking test proves no component reaches into
another's private state (Rule 4), Mission Control now forbids every
filesystem/storage import, and the Runtime's `CheckpointSink` protocol is
defined *inside* `runtime/` so it acquires no storage dependency (Rule 3).
Also fixed a real MB024 bug this work exposed: `max_cycles` was absolute,
so a restored runtime broke out of its loop immediately and did nothing.
205 new tests, 789 passing, zero regressions. Full detail:
`docs/MISSION_BRIEF_025.md`.

## ADR-0016: The Dashboard Data Contract (Mission Brief 026)
The Dashboard is the first pure *consumer* component, so its dependency
direction is the whole design problem. A frozen read model
(`DashboardSnapshot`) sits between published contracts and rendering:
panels receive plain data, never live objects, which makes read-only a
property of the data flow rather than a rule to remember, and makes
rendering testable without a Runtime. Absence is a first-class value —
`0` and "unknown" are different facts, and a failed read becomes absent
data with a reason rather than a fabricated zero. Health classification is
presentation, quarantined to `health.py` as pure functions whose results
nothing in Kalpavriksha consumes. See
`docs/adr/0016-dashboard-data-contract.md`.

## Mission Brief 026 (2026-07-26): Founder Dashboard
Built the first operational window into the running system: nine read-only
panels updating live off the Event Bus. A contract survey was done *before*
any code (MB026 required stopping and raising an ADR if data were
unreachable) — every panel proved reachable through published surfaces, so
no blocking ADR was needed, and **no frozen component was modified**, which
a `git diff` test against the MB025 tag now enforces. Two real findings
during the build: box-drawing glyphs crash a cp1252 Windows console (fixed
with a charset chosen by asking the output stream what it can encode, not
by guessing from the platform), and the Capability panel initially counted
capabilities rather than naming them, under-delivering Deliverable 5 —
caught by the Definition-of-Done test. 182 new tests, 971 passing. Full
detail: `docs/MISSION_BRIEF_026.md`.

## ADR-0017: The AI Capability Broker (Mission Brief 027) — **Accepted; ratified 2026-07-29, Constitution Amendment 2 applied**
The intelligence-selection layer is a **kernel service** (Shared
Infrastructure), not an Executive — because both the Brain's Model Router
and any Executive mid-task need the same answer, which is the exact
condition ADR-0010 created Shared Infrastructure to handle; because the
Broker must be consulted *before* dispatch, so it cannot be a thing that
is dispatched; and because spend, approvals, and benchmark aggregates are
ledgers that must be singular (the §5.2 argument). What the rejected
option was right about is preserved by splitting the concern: **the Broker
decides and never touches the machine; the AI Infrastructure Executive
touches the machine and never decides.** Four rulings worth remembering:
selection walks the cost ladder and stops at the first tier clearing a
configurable *quality floor*, refusing rather than guessing when no tier
does; the Broker's output names an already-registered Capability, so it
**creates no new execution path**; `observed` beats `declared` in the
capability matrix (Rule 8 applied to providers) and a benchmark sample
records the Verification Verdict, not an API status, so providers that
fail *articulately* cannot climb; and decisions are deterministic and
replayable, which is what makes "every provider decision is auditable"
a property rather than a claim. Two terminology collisions resolved
ADR-0014-style: **AI Capability** (`lowercase.dotted`) is not
**Capability** (`PascalCase.PascalCase`), and **Provider** generalizes
**Reasoning Provider** without renaming it. **Ratified by the founder on
2026-07-29**, at which point the proposed Constitution amendment was
applied as **Amendment 2** (§3.3, §5.7 new, prior §5.7 → §5.8, §6, §16,
§17; §5.7 carries status RESEARCH-BACKED). See
`docs/adr/0017-ai-capability-broker.md`.

## ADR-0018: The Broker Learning Loop (founder directive at MB027 ratification)
The founder made self-improvement a first-class objective for the AI
Infrastructure Executive — usage analytics, benchmark history, cost
optimization, privacy awareness, and Founder-approved ecosystem evolution.
That collides head-on with ADR-0017's determinism-and-replay guarantee, so
the resolution is a separation rather than a compromise: **the decision
*procedure* never learns; the versioned *policy* it reads does.** Every
decision already carries `policy_version`, so a decision made under v7
replays against v7 forever, and learning produces v8 as a discrete,
reviewable, revertible artifact. Three owners: the Broker holds the data,
the AI Infrastructure Executive does the analysis (it is the only
component that can also check a proposal for *feasibility* against the
real machine), the Founder promotes. The loop is ADR-0012's Knowledge
Lifecycle applied to provider selection, so it rides MB023's existing
human-gated queues — **zero new approval paths**. Four guards worth
remembering: privacy is a **one-way ratchet** (the loop may propose
tightening, never loosening — because the optimisation pressure runs
exactly the wrong way and every such proposal would arrive with real
evidence attached); every promoted change needs a `rollback_condition` or
it is refused at generation; exploration is budgeted on low-stakes
requests, or a low-ranked provider can never climb back; and installation
— newly added to the Executive's contract by this directive — is
`IRREVERSIBLE`, so ADR-0009 guarantees no standing grant can ever
authorise one. See `docs/adr/0018-broker-learning-loop.md`,
`AI_CAPABILITY_BROKER_ARCHITECTURE.md` §19 and §11.1. **Scheduled, not
designed:** a **Policy Simulator** (§19.8) that validates a proposed policy
version against historical missions before it reaches the founder —
nearly free because ADR-0017's determinism guarantee already makes past
decisions re-derivable, and carrying one non-negotiable constraint from
the start: replay can report what would have been *selected* as fact, but
never whether it would have *succeeded*, because no outcome exists for a
Provider that was never called.

## Mission Brief 027 (2026-07-29): AI Capability Broker Architecture
Architecture-only — zero code, zero tests, zero runtime behavior changes.
Froze the layer every future Executive (Desktop, Research, Knowledge,
Terminal, Git) is blocked behind: provider registry, capability matrix,
decision engine, AI asset inventory, recommendation engine, cost model,
benchmark engine, founder approval policy, the AI Infrastructure Executive
contract, the Desktop Executive contract, and the Capability Packages
integration point. Notable: the approval policy gained one rule MB027 did
not ask for — **sending sensitive data to any third party requires
approval, including a free one**, because a policy organised purely around
money protects the wrong thing; and Deliverable 3's single list was frozen
as *two* axes (what a Provider can do vs. how well/at what price), because
merged, "cost" becomes something a Provider "can do" and the filter phase
cannot be written cleanly. **Ships one Constitution amendment as
*Proposed*, not made** (§5, §6, §16, §17 are FROZEN; MB025's precedent is
propose-don't-decide) — `KALPAVRIKSHA_VISION_V2.md` was not edited. Also
named a live contradiction found in existing code: `ModelRouter.
select_provider()` hardcodes `"hermes"`/`"chatgpt"`, product names in
Brain logic that §14/§21 forbid; the Broker supersedes it, and the
migration is a future brief. Full detail: `docs/MISSION_BRIEF_027.md`,
`AI_CAPABILITY_BROKER_ARCHITECTURE.md`.

## ADR-0019: The Runtime Approval Boundary (Mission Brief 028.0) — **Accepted; ratified and implemented 2026-07-29**
The defect stated exactly: Kalpavriksha has **two permission gates and two
execution paths, and both gates are on one path.** Gate A
(`orchestrator.py:42`, keyed on plugin+capability+tier) is the real
Founder boundary. Gate B (`executor.py:104`, keyed on executor+action) was
never an independent boundary — ADR-0005 designed it to *receive* Gate A's
relayed decision, and `filesystem_plugin.py:170` grants its exact key
unconditionally on the line before it runs. The Runtime path
(`engine.py:320`) calls the gateway directly, never the Orchestrator, so
Gate A never fires and Gate B self-satisfies. **Net gates: zero**, and an
IRREVERSIBLE delete completes unapproved. No single component is at fault
— MB024 introduced a second execution path and the boundary lived in a
component that path does not use. Fix: **one `ApprovalGate` protocol
defined inside `runtime/`** (the MB025 `CheckpointSink` precedent, so the
Runtime gains no Permission System dependency), consulted once at
`_handle_task()` — the only funnel every task passes through — and
**failing closed** when absent, so forgetting to wire it yields a system
that does nothing rather than one that does everything. Rejected:
per-gateway checks (duplicated truth), routing the Runtime through the
Orchestrator (merges two execution models to fix a boundary), and wrapping
gateways in the launcher (works, needs no frozen change, and is exactly
the "convention not architecture" the Definition of Done rejects). Also
resolves the Deliverable 8/9 tension with one rule: **a replayed approval
event restores the *record*, never a usable grant** — otherwise every
restart silently re-arms every approval ever given. That is ADR-0009's
"destructive authority does not accumulate," in restart form. Requires
changing `runtime/` and `mission_control/events.py`, so per MB028.0's own
Architecture Rules the work **stopped at the ADR**; nothing frozen was
touched. See `docs/adr/0019-runtime-approval-boundary.md`,
`docs/MISSION_BRIEF_028_0.md`.

## ADR-0020: The Founder Approval Workflow (Mission Brief 028.1) — Accepted; frozen-component changes **PROPOSED**
MB028.0 made the system safe; it had no way to say yes. The change under
this brief: **an unanswered request is no longer a refusal.** MB028.0
failed the task; now the founder is asked and the task waits.
`ApprovalPending` is deliberately *not* a subclass of `ApprovalDenied` —
conflating them is how "the founder was asleep" becomes "the mission
failed". Three decisions worth remembering: (1) the **Approval Queue
lives in Mission Control**, beside the two human-gated queues MB023 built,
and is emphatically *not* a second permission system — it holds
questions, the Permission System holds authority, and approving issues a
`ONCE` grant there, so ADR-0019's boundary stays singular; (2)
**ADR-0016 is untouched** — the Dashboard still renders from a frozen
snapshot and has no way to act on the `[A]pprove` hints it prints; the
`FounderConsole` in the launcher (the composition root, permitted to know
every layer) does the acting through Mission Control's published
contract. Giving `FounderDashboard` a live Mission Control was the obvious
implementation and would have quietly undone the one property ADR-0016
exists to establish; (3) **a restored approval is evidence, never
authority** — deferred requests come back exactly as they were, but a
restored `APPROVED` entry grants nothing, because the grant lived in the
unpersisted Permission System. Also: defer is not a decision (nothing
reaches the ledger), expiry is one (recorded with `decided_by: "system"`,
because a ledger of only human decisions would leave an unexplained
failure), and timeout defaults to disabled since a request that vanishes
overnight is worse than one still on the screen. One real bug found by a
failing test: a held task is "dispatched" as far as Mission Control is
concerned, so it never returned through `_dispatch()` — approving
resolved the question and the work still never ran. 33 new tests, 1051
passing. See `docs/adr/0020-founder-approval-workflow.md`,
`docs/MISSION_BRIEF_028_1.md`.

## Mission Brief 027.5 (2026-07-29): The Kalpavriksha Launcher
Closed the "wiring lives in tests" gap MB026 named: `kalpavriksha` is now
a real console command that recovers state, wires every shipped subsystem,
starts the Runtime, and hands the terminal to the Founder Dashboard. No
new architecture — the launcher is a **composition root**, the one place
allowed to know every layer at once because its only job is to construct
and wire; two AST-walking tests enforce that nothing in `src/` imports it
and that `boot.py` defines only report/container types. Three decisions
worth remembering: (1) **boot ordering is load-bearing** — recover before
recording (recovery reads history, recording writes it), discover after
recovery (recovery restores what existed, discovery is idempotent and adds
only what is new), and getting it wrong raises
`ExecutiveAlreadyRegistered`, which is why it has its own test; (2) **every
boot step reports its real status with a reason, never `ok`** — ADR-0016's
absence-is-a-value discipline applied to startup, which is why the absent
AI Capability Broker is a visible line at every launch rather than a
silent skip; (3) **execution is opt-in**, because of the finding below.
**Found by running it, not by inspection: the Runtime path does not
consult the Permission System.** `FilesystemPlugin.invoke()` self-grants a
`ONCE` permission on the Executor's key (the ADR-0005 relay) assuming the
Orchestrator already gated the call — and the Runtime calls the gateway
directly, never the Orchestrator. An `IRREVERSIBLE` `delete_folder`
completes with no approval anywhere, contradicting **Constitution Rule 5**.
Pre-existing (MB024 built the path, MIT-001 certified it), but the
launcher makes it reachable in one command. Deliberately **not fixed here**
— it touches frozen components — and deliberately **not papered over**: an
earlier draft's `--approve-session` relay was removed once running it
proved the relay was decorative, because dead safety code reads like
protection. Characterised by a test written to fail when the gap is fixed.
22 new tests, 993 passing. Full detail: `docs/MISSION_BRIEF_027_5.md`.

## Mission Brief 024 (2026-07-26): Autonomous Runtime Engine
Built the heartbeat — the loop that replaces the founder in the execution
cycle. Two architectural tensions resolved and recorded in
`RUNTIME_ENGINE_ARCHITECTURE.md`: (1) *who invokes the Executive* when
Mission Control, the Runtime, and direct Executive calls are all
forbidden — resolved by defining "never performs work" precisely (no work
logic, no Environment access, no Executive knowledge; causing work to
happen in the right order **is** orchestration) and putting an
`ExecutiveGateway` protocol on the Runtime rather than on Mission
Control, so Mission Control stays mechanically incapable of executing;
(2) *retry* versus Constitution §11 — resolved via §4.1's existing
distinction: the Runtime does bounded mechanical retry (same task, same
payload) then escalates, and Mission Control is told exactly once, so
MB023's "the dispatcher never auto-retries" stays literally true. Three
real bugs found by running it (a missing `RECOVERING → WAITING` edge that
crashed every retry; no qualified→local capability translation; an
`ExpectedOutcome` smuggled through `payload` that would have leaked a
non-JSON object into audit records — now a first-class `Task` field per
Constitution §3.2). Also surfaced a genuine constraint single-threaded
testing could not: Playwright sessions are thread-affine, so every
Environment interaction must happen inside a task. 82 new tests, 582
passing. Full detail: `docs/MISSION_BRIEF_024.md`.

## MIT-001 (2026-07-26): Mission Control Integration Certified — Browser Executive
Certification run answering "can Mission Control orchestrate the Browser
Executive without modifying it?" — yes, all seven tests pass. Four gaps
closed on the Mission Control side (auto-discovery via
`discover_executives()`, `TASK_DISPATCHED` renamed to `TASK_ASSIGNED` per
the spec, `FounderState.result`, capability stamped onto verification
events) plus one read-only `PluginRegistry.all_plugins()` accessor so
discovery reads the registry through its contract rather than reaching
into internals. The Browser Executive itself is byte-identical to the
MB022 tag, asserted by a test that runs `git diff`. Two documented,
deliberate differences from the brief's expected capability list:
`Browser.Fill` is `Browser.TypeText` (deterministic naming rule), and
there is **no `Browser.Verify` capability by design** — ADR-0011 makes
Verification structurally independent, so it must never be dispatchable
through the same `invoke()` path as ordinary work. Full detail:
`docs/MIT_001_CERTIFICATION.md`.

## Mission Brief 022 (2026-07-26): Browser Worker
First implementation Mission Brief against the frozen Founder
Constitution. Wrapped Playwright (never reimplemented it) behind nine
atomic Actions registered on the existing, unmodified `LocalExecutor`/
`Plugin` machinery — proving the Universal Executive Operator
architecture generalizes to a second, unrelated capability family at zero
risk to the 229-test filesystem baseline. Introduced a generic,
Playwright-free `verification/` package (`Verifier` ABC, `Evidence`,
`Audit`) any future Worker can reuse unchanged, and an Environment Session
Manager (`BrowserSessionManager`) resolving the Constitution's one
deliberately-open item: stateful sessions inside the one-shot `Action`
contract. Key design catch, found by running the actual test suite, not
by inspection: the first draft gave each session its own independent
Playwright driver, which Playwright's sync API does not support running
concurrently in one thread; fixed by having the manager own one shared
driver/Browser per Operator Instance, multiplexed across sessions as
separate `BrowserContext`s. Mechanically verifies its own
product-independence claim (`test_browser_constitution_compliance.py`)
rather than only asserting it in prose. See `docs/MISSION_BRIEF_022.md`
and `BROWSER_WORKER_ARCHITECTURE.md`.

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

## Mission Brief 005 (2026-07-23): Local execution capability expansion
Designed `FILESYSTEM_CAPABILITIES.md` before writing any code, per the
brief's explicit gate. Grew `FilesystemPlugin` from 3 to 14 capabilities:
eleven new primitive Actions (read/list/search/exists-checks, append,
rename/copy/move, delete-file/delete-folder), registered declaratively
from a tuple of Action classes rather than hand-written per-capability
wiring. Key design decision: ADR-0009 (`PermissionCategory` +
IRREVERSIBLE-never-satisfied-by-ALWAYS_FOR_CAPABILITY). `cli.py`'s intent
parser was generalized to one `ParsedActionIntent` dataclass and a
table-driven `_INTENT_PATTERNS` dispatch, reaching all six of the brief's
conversation examples end to end, plus Move (added for symmetry). 108 new
tests, 234 passing overall, zero regressions. Full detail:
`docs/MISSION_BRIEF_005.md`.

## Open decisions (not yet locked)
- ~~Ratify (or reject) ADR-0017's Constitution amendment.~~ **Ratified
  2026-07-29** and applied as Constitution Amendment 2. The founder also
  approved the Kernel Service placement and the Broker/AI-Infrastructure-
  Executive split, and added the learning loop as a first-class objective
  (ADR-0018).
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
