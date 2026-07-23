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
| **004** — The Memory System | 2026-07-23 | `v0.4.0-miracle-004` | `fc2866b` | 124 passed | ✅ Shipped | Design-first six-layer memory model (`MEMORY_ARCHITECTURE.md`); Layers 1-3 implemented (Conversation, Mission, Persistent/SQLite), Layers 4-6 reserved as interfaces only. `MasterAgentSession` now persists every mission automatically at every terminal state — no manual save calls in the CLI — and answers "What was my last mission?" / "Show my recent missions." from Memory. Verified across a real process restart. Key design decision: ADR-0007 (stdlib `sqlite3`, JSON columns over normalization). Full writeup: `docs/MISSION_BRIEF_004.md`. |

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

## How to add a row

When a Miracle completes: run the full suite, confirm the pass count,
commit, tag (`vMAJOR.MINOR.PATCH-miracle-NNN`, following the pattern
already established — see `FOUNDER_PLAYBOOK.md`'s Git Workflow section),
then add exactly one row here with the real commit hash and real test
count — not an estimate. This table is only useful if every number in it
is independently verifiable by running `git show <commit>` and `pytest`
against it.
