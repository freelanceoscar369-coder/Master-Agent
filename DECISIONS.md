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
