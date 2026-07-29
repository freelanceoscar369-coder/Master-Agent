# Miracle Ledger

Chronological record of every completed Miracle (Mission Brief). This is
the append-only history — `PROJECT_BRAIN.md` is the current-state index,
`DECISIONS.md`/`docs/adr/` explain *why* each decision was made, this
file is the *when/what shipped/did it stay green* record. Add a row here
the moment a Miracle is committed and tagged; never edit a past row
except to fix a factual error.

| Miracle | Date | Git Tag | Commit | Tests | Status | Summary |
|---|---|---|---|---|---|---|
| **001** — First end-to-end mission | 2026-07-23 | `v0.1.0-miracle-001` | `ee815fe` | 23 passed | ✅ Shipped | First real vertical slice: "create a folder called Demo" through the actual Orchestrator, Permission System, and Mission state machine — not a mock. Found and fixed two real bugs (`ONCE` grant never consumed; Mission state machine illegally skipped `EXECUTING`). Full writeup: `docs/MISSION_BRIEF_001.md`. |
| **001.5** — Health check + Founder Workspace Bootstrap | 2026-07-23 | *(none — see note)* | `d6deef8` | 23 passed (unchanged) | ✅ Shipped | Verified Miracle 001's assets were intact, then added the founder-workspace scaffolding around the working code: top-level runtime folders, documentation set, Obsidian vault, git history (`ee815fe` retroactively became the first commit). No functional code changed — pure scaffolding + docs. Flagged then, still true: `D:\MasterAgent` unverified, no device bridge connected. |
| **002** — Generic Local Executor | 2026-07-23 | `v0.2.0-miracle-002` | `f07ca41` | 41 passed | ✅ Shipped | Generalized *how* a mission executes: added `LocalExecutor` + the `Action` Contract so every future local capability plugs into one validated, permission-gated, logged execution path instead of being a one-off. Refactored `create_folder` onto it with zero functional regression. Key design decision: ADR-0005 (Executor/Plugin permission-relay). Full writeup: `docs/MISSION_BRIEF_002.md`. |
| **003** — Workspace Bootstrap Action | 2026-07-23 | `v0.3.0-miracle-003` | `746a26d` | 76 passed | ✅ Shipped | Proved the Executor + Action layer composes safely: added `write_file` (second primitive) and `WorkspaceBootstrapAction` (composite — root folder + subfolders + seed files, generically parameterized), composed entirely through `LocalExecutor.execute()`, never by calling sub-actions' `run()` directly. Key design decision: ADR-0006 (composite-action relay, one layer deeper than ADR-0005). Reachable only via direct `invoke()` calls at this point — flagged as the top gap. Full writeup: `docs/MISSION_BRIEF_003.md`. |
| **003.1** — First Real Mission | 2026-07-23 | `v0.3.1-miracle-003-1` | `307c8b8` | 93 passed | ✅ Shipped | Closed Miracle 003's gap: connected real conversation ("Create a Python project called Demo.") to `workspace_bootstrap`, through the full stack — Conversation → Intent Parser → Mission → Planner → Permission System → Executor → `WorkspaceBootstrapAction` → primitives. Zero changes to `Orchestrator`, `PermissionSystem`, or the composite's own relay logic — proof the design generalizes. Found and fixed one real bug (`InvocationResult` silently dropping execution time). Full writeup: `docs/MISSION_BRIEF_003_1.md`. |
| **003.5** — Foundation Freeze | 2026-07-23 | `v0.3.5-miracle-003-5` | *(see note below — a file can't contain the hash of the commit that introduces it)* | 93 passed (unchanged) | ✅ Shipped | Zero user-facing features, zero architecture changes, zero runtime behavior changes (`src/`/`tests/` diff empty). Created the project's permanent engineering documentation set (this file included) before Memory, Voice, or Model Routing begin. See `FOUNDER_PLAYBOOK.md` for the process this freeze itself now codifies. |
| **004** — The Memory System | 2026-07-23 | `v0.4.0-miracle-004` | *(see note below — same self-reference problem as 003.5)* | 124 passed | ✅ Shipped | Design-first six-layer memory model (`MEMORY_ARCHITECTURE.md`); Layers 1-3 implemented (Conversation, Mission, Persistent/SQLite), Layers 4-6 reserved as interfaces only. `MasterAgentSession` now persists every mission automatically at every terminal state — no manual save calls in the CLI — and answers "What was my last mission?" / "Show my recent missions." from Memory. Verified across a real process restart. Key design decision: ADR-0007 (stdlib `sqlite3`, JSON columns over normalization). Full writeup: `docs/MISSION_BRIEF_004.md`. |
| **004.1** — Memory Scale Review | 2026-07-23 | `v0.4.1-miracle-004-1` | *(see note below — same self-reference problem, resolved the same way from the start this time)* | 126 passed | ✅ Shipped | Reviewed Memory against long-term scale (millions of missions, thousands of plugins, hundreds of capabilities, years of history) before more got built on top of it. Fixed two real problems: `MemoryStore`'s query surface (one `query_missions(MissionQuery)` instead of a method per filter need) and `MissionRecord`'s filesystem-specific `folders_created`/`files_created` columns (replaced with a generic `artifacts` list). `Memory`'s public API and every existing caller unchanged. Key design decision: ADR-0008. Full writeup: `docs/MISSION_BRIEF_004_1.md`. |
| **005** — Local Execution Expansion | 2026-07-23 | `v0.5.0-miracle-005` | *(see note below — same self-reference problem, same standing resolution)* | 234 passed | ✅ Shipped | Design-first (`FILESYSTEM_CAPABILITIES.md`) expansion of `FilesystemPlugin` from 3 to 14 capabilities: eleven new primitive Actions (read/list/search/exists-checks, append, rename/copy/move, delete-file/delete-folder), registered declaratively — adding capability #15 costs one new file, never an edit to the plugin. New `PermissionCategory` axis plus a real mechanism change (an `always_for_capability` grant can never satisfy an `irreversible` check). `cli.py`'s intent parser generalized to one `ParsedActionIntent` + table-driven `_INTENT_PATTERNS`, reaching all six of the brief's conversation examples plus Move. Key design decision: ADR-0009. Full writeup: `docs/MISSION_BRIEF_005.md`. |

| **021 Rev. 3** — Founder Constitution Freeze | 2026-07-26 | `v0.5.1-miracle-021-3` | `f9aee0e` | 234 passed (unchanged) | ✅ Shipped | Design-only — zero code, zero tests, zero runtime behavior changes. Resolved every gap an independent architecture audit found in `docs/architecture/KALPAVRIKSHA_VISION_V2.md`: introduced a Shared Infrastructure layer between Executive Brain and Universal Executive Operator (ADR-0010), made Verification structurally independent of Execution (ADR-0011), formalized the Knowledge Lifecycle with a human-gated Promotion Review (ADR-0012), designed for multiple Operator Instances (ADR-0013), scrubbed product-specific terminology from the architecture, gave every previously-unowned component exactly one home, consolidated duplicated rules, froze sixteen architectural terms, and labeled every section FROZEN/RESEARCH-BACKED/EVOLVABLE/IMPLEMENTATION DETAIL. Declared the Constitution frozen. Full writeup: `docs/MISSION_BRIEF_021_REVISION_3.md`, `docs/architecture/FOUNDER_CONSTITUTION_FREEZE.md`. |
| **022** — Browser Worker | 2026-07-26 | `v0.6.0-miracle-022` | *(see note below — same self-reference problem, same standing resolution)* | 354 passed | ✅ Shipped | Design-first (`BROWSER_WORKER_ARCHITECTURE.md`) first implementation Miracle against the frozen Constitution: a Playwright-wrapped Browser Worker (nine atomic Actions) proving the Universal Executive Operator architecture in a real Environment. Added the generic, Playwright-free `verification/` package (Verifier ABC, Evidence, Audit) every future Worker reuses unchanged, and the Environment Session Manager (`BrowserSessionManager`) resolving the stateful-session gap the Constitution Freeze had left open. Observation covers five facets including the accessibility tree and the page's available actions. Product-independence is mechanically verified by a standing test, not just asserted in prose. Two real bugs found by running the suite rather than by inspection (see the Mission Brief's own "what changed after the first live run" and "what a completeness recheck caught" sections). 125 new tests, zero regressions. Full writeup: `docs/MISSION_BRIEF_022.md`. |

| **023** — Mission Control & Self-Development Infrastructure | 2026-07-26 | `v0.7.0-miracle-023` | `6898776` | 461 passed | ✅ Shipped | Design-first (`MISSION_CONTROL_ARCHITECTURE.md`) build of the runtime coordination layer everything else now plugs into: Universal Event Bus (one `Event` schema system-wide, no custom logging), Capability Registry with deterministic qualified names, Executive Registry, nine-state Worker Lifecycle, Task Dispatcher (dependency-ordered, cycles refused at submission, blocked tasks never auto-retried), Self-Development Queue, Knowledge Acquisition Queue, immutable Audit Stream, Founder State backend contract (no UI), and the Communication Contract. Existing Executives register **unmodified** via a manifest-reading adapter — the integration tests use the real `FilesystemPlugin` and `BrowserPlugin`, not fakes. Two rules made mechanical rather than documentary: "Mission Control never performs work" (an import-parsing test) and ADR-0012's human-gated knowledge promotion (refusal raises *and* publishes an auditable event). First amendment under the Constitution freeze process: ADR-0014, reconciling "Executive" with "Worker". One real bug found by the tests — the dispatcher assigned a second task to an already-busy Executive. Full writeup: `docs/MISSION_BRIEF_023.md`. |
| **023.1** — Cross-Platform Path Safety | 2026-07-26 | `v0.7.1-miracle-023-1` | *(see note below — same self-reference problem, same standing resolution)* | 500 passed | ✅ Shipped | Parallel maintenance brief, shipped as its own commit after 023 was sealed. Fixed three genuine cross-platform defects: `is_unsafe_relative_path()` was weaker on Windows than POSIX (`/etc/passwd` and `D:config` both passed, since `is_absolute()` is False for them there) — now checked against both path flavours and rejecting on `anchor`; `overwrite: true` meant different things per platform (`Path.rename()` raises on Windows, replaces on POSIX) — now `Path.replace()`; and search results leaked native separators into persisted mission history — now portable forward slashes. **First fully green suite of the project's history at this point: 500 passed, 0 failed** — the 5 long-standing failures were fixed at the source, not by relaxing their assertions. Verification also surfaced and pinned a named limit: `run()` is not a second boundary. Full writeup: `docs/MISSION_BRIEF_023_1.md`. |

| **MIT-001** — Mission Control Integration Certified | 2026-07-26 | `v0.7.2-mit-001` | `ef1f736` | 519 passed | ✅ Certified | Certification, not a new capability: proved Mission Control orchestrates the Browser Executive with **zero modification** to it. All seven MIT-001 tests pass (19 automated + a live run to a real URL returning a `matched` verdict). Zero Modification proven three ways, including a test that runs `git diff` against the MB022 tag. Closed four gaps on the Mission Control side (auto-discovery, `TASK_ASSIGNED` rename, `FounderState.result`, capability stamped onto verification events). Two documented deliberate differences from the brief's expected list: `Browser.Fill` is `Browser.TypeText`, and there is no `Browser.Verify` capability by design (ADR-0011). Full detail: `docs/MIT_001_CERTIFICATION.md`. |
| **024** — Autonomous Runtime Engine (The Heartbeat) | 2026-07-26 | `v0.8.0-miracle-024` | *(see note below — same self-reference problem, same standing resolution)* | 582 passed | ✅ Shipped | Design-first (`RUNTIME_ENGINE_ARCHITECTURE.md`) build of the loop that replaces the founder in the execution cycle: observe → dispatch → execute → verify → report → idle → repeat. **Kalpavriksha now runs unattended**, proven live against the real internet — a four-task browser mission completing at `progress: 1.0` with no founder involvement after `start_background()`. Two architectural tensions resolved rather than fudged: who invokes when nothing may perform work (an `ExecutiveGateway` protocol held by the Runtime, keeping Mission Control mechanically pure), and mechanical retry versus Constitution §11's strategic-recovery-is-the-Brain's rule (Mission Control never sees a retry, only the final outcome). Rules 1 and 2 enforced by an import-parsing test that also forbids any `runtime/` file from naming a specific Executive. Three real bugs found by running it, not by inspection; one genuine constraint surfaced (Playwright sessions are thread-affine). Full writeup: `docs/MISSION_BRIEF_024.md`. |

## Notes on gaps in this table

- **Miracle 001.5 has no dedicated git tag.** It extended Miracle 001's
  commit history (adding `START_HERE.md` on top of the same initial
  commit `ee815fe`) without a version bump, since it shipped zero
  functional changes — pure scaffolding and documentation. If a future
  Miracle wants a tag to point to specifically for 001.5's state, it can
  be added retroactively (`git tag -a v0.1.5-miracle-001-5 d6deef8`)
  without disrupting this table.
- **Test counts are cumulative, not incremental.** Each row's "Tests"
  column is the full suite's pass count *after* that Miracle, not just
  the tests it added — see each Miracle's own Mission Brief doc for the
  breakdown of new vs. carried-over tests.
- **Miracle 003.5's own commit hash is genuinely unknowable from inside
  this file.** This table is part of the commit that ships it — writing
  that commit's own hash into it changes its contents, which changes its
  hash, which would make the written value wrong again (the same problem
  a hash-linked structure like git itself is built to route around, not
  something this table can solve by trying harder). The real hash is
  `git tag -n1 v0.3.5-miracle-003-5` away, or `git rev-list -n1
  v0.3.5-miracle-003-5` for just the hash — the tag is the authoritative
  pointer for any Miracle whose commit can't self-reference cleanly. A
  future Miracle's row does not have this problem, since by the time it
  ships, this row's hash is already fixed history it can read and copy.
- **"Status" is always ✅ Shipped or it isn't in this table.** A Miracle
  that was started but not completed doesn't get a row until it ships —
  in-progress work belongs in `ROADMAP.md`'s "In Progress" column, not
  here.
- **Miracle 004 hit the same self-reference problem 003.5 did**, for the
  same reason: this file is part of the commit it documents, so its own
  row can't contain that commit's final hash. Rather than repeat 003.5's
  amend-and-re-tag chase (which only ever produces a new hash that
  invalidates the row again), this row goes straight to the resolution —
  `git tag -n1 v0.4.0-miracle-004` / `git rev-list -n1
  v0.4.0-miracle-004` is the authoritative pointer, same as 003.5's row.
  A future documentation-only or ledger-updating Miracle will hit this
  again; treat "point to the tag" as the standing answer, not a one-off
  workaround.
- **Miracle 004.1 applied that standing answer from the start** — its row
  never tried to embed a commit hash at all, going straight to `git tag
  -n1 v0.4.1-miracle-004-1` / `git rev-list -n1 v0.4.1-miracle-004-1` as
  the pointer. No amend, no chase. This is what "treat it as the standing
  answer" above actually looks like in practice.
- **Miracle 005's row follows the same pattern**: `git tag -n1
  v0.5.0-miracle-005` / `git rev-list -n1 v0.5.0-miracle-005` for the
  authoritative commit hash.
- **Miracle 021 Revision 3 could record its real hash** (`f9aee0e`),
  unlike the rows above it, for a simple reason: it shipped before this
  ledger row was written, so by the time the row existed the hash was
  already fixed history to read and copy — exactly the situation the
  004 note predicted would eventually apply. Its tag was added
  retroactively alongside this row (`v0.5.1-miracle-021-3`, a patch-level
  bump since it changed zero code), the same way the 001.5 note says a
  retroactive tag can be added without disrupting this table.
- **Miracle 023 could record its real hash** (`6898776`) for the same
  reason 021 Revision 3's row could: the ledger row was written after that
  commit already existed, so the hash was fixed history to read and copy.
  Its tag was added alongside this row.
- **Miracle 023.1 hit the self-reference problem** (its ledger row ships
  in the commit it documents) and resolves it the standing way:
  `git tag -n1 v0.7.1-miracle-023-1` / `git rev-list -n1
  v0.7.1-miracle-023-1`. Patch-level bump, since it fixes existing
  behaviour rather than adding a capability.
- **MIT-001 is a certification row, not a Miracle row.** It shipped no new
  capability; it proved an existing pair worked together. Recorded here
  anyway because the ledger is the "what happened when" record, and a
  certification that gates two Mission Briefs being called complete is
  part of that history.
- **Miracle 024 hit the standing self-reference problem** (its ledger row
  ships in the commit it documents) and resolves it the standing way:
  `git tag -n1 v0.8.0-miracle-024` / `git rev-list -n1
  v0.8.0-miracle-024`. Minor version bump — a new runtime capability, not
  a fix to an existing one.
- **Miracle 022 hit the standing self-reference problem again** and
  resolves it the standing way: `git tag -n1 v0.6.0-miracle-022` /
  `git rev-list -n1 v0.6.0-miracle-022` is the authoritative pointer.
  Minor version bump, since it adds a new capability family (the Browser
  Worker) rather than extending an existing one.

## How to add a row

When a Miracle completes: run the full suite, confirm the pass count,
commit, tag (`vMAJOR.MINOR.PATCH-miracle-NNN`, following the pattern
already established — see `FOUNDER_PLAYBOOK.md`'s Git Workflow section),
then add exactly one row here with the real commit hash and real test
count — not an estimate. This table is only useful if every number in it
is independently verifiable by running `git show <commit>` and `pytest`
against it.
