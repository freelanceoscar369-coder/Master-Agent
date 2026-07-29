# Master Agent

> The orchestration layer between human intention and software execution.

Internal codename project. See `ARCHITECTURE.md` for the system design and
`docs/adr/` for the decisions behind it. `docs/TIMELINE_RISK.md` has an
honest read on the Founder Edition deadline (2026-08-05).

## Status

**Mission Brief 001** made one mission real end to end ("create a folder
called Demo") through the actual Orchestrator, Permission System, and
Mission state machine. **Mission Brief 002** generalized how that mission
executes: a `LocalExecutor` + `Action` contract now sits between the
Orchestrator and the filesystem, so every future local capability (file
ops, shell commands, git, VS Code, Obsidian, ...) plugs into the same
validated, permission-gated, logged execution path instead of being a
one-off. `create_folder` runs on this new path today with zero functional
change from Mission Brief 001 — same transcript, same behavior.
**Mission Brief 003** added a second primitive (`write_file`) and proved
the layer composes: `workspace_bootstrap` builds a folder + files layout
entirely by calling the other two actions *through* the Executor — never
bypassing it or the Permission System — with only one human approval for
the whole composite (see `docs/adr/0006-composite-action-relay.md`).
**Mission Brief 003.1** connected that capability to real conversation:
`python -m master_agent.cli` now understands "Create a Python project
called Demo." or "Create a project called Expense Tracker." end to end —
same wake phrase, same one-approval flow, same Orchestrator/Permission
System path the folder-creation demo has used since Mission Brief 001.
**Mission Brief 004** gave the system a real memory: every mission is now
persisted automatically (no manual save calls anywhere in the CLI) to a
local SQLite store, and "What was my last mission?" / "Show my recent
missions." work end to end — verified across a real process restart. See
`docs/MISSION_BRIEF_001.md` through `docs/MISSION_BRIEF_004.md` for what's
genuinely production-ready versus still stubbed, and try it yourself:

```
pip install -e ".[dev]"
python -m master_agent.cli
```

Everything beyond that execution path — the real Planner (a model call;
`cli.py`'s rule-based parser stands in for it today), the `MissionManager`
class specifically (mission persistence itself is now real, just not
through this still-unwired class), Model Router, Memory Layers 4-6
(Knowledge/Vector/Cloud Sync — interfaces only), ChatGPT/Hermes providers,
Voice, Desktop UI, and every local action besides
`create_folder`/`write_file`/`workspace_bootstrap` — is still the
scaffold-stage interface described below, not wired to anything real yet.

## Layout

```
src/master_agent/
  cli.py               # Mission Brief 001: the one working end-to-end conversation
  orchestrator/      # walks a MissionPlan, invokes plugins via the registry
  planner/            # Intent -> MissionPlan
  mission_manager/    # Mission entity + state machine
  memory/             # Mission Brief 004: Memory (conversation, mission, SQLite;
                        #   future.py: reserved Knowledge/Vector/Cloud Sync interfaces)
  permissions/        # approval gate for non-read-only plugin actions
  executor/            # Mission Brief 002: LocalExecutor + Action contract + actions/
                        #   (create_folder, write_file, workspace_bootstrap — Mission Brief 003)
  plugins/            # Plugin contract, registry, filesystem_plugin.py, providers/ (ChatGPT, Hermes)
  voice/              # STT (input) / TTS (output) adapters
  ui/                 # notes on the desktop UI boundary (separate process)
docs/adr/              # architecture decision records
docs/MISSION_BRIEF_001.md  # what Mission Brief 001 proved
docs/MISSION_BRIEF_002.md  # what the Local Executor is and why, and what's next
docs/MISSION_BRIEF_003.md  # composing actions into a workspace_bootstrap mission
docs/MISSION_BRIEF_003_1.md  # connecting conversation to workspace_bootstrap
docs/MISSION_BRIEF_004.md  # the Memory System
MEMORY_ARCHITECTURE.md      # Memory's six-layer design, SQLite schema, tradeoffs
tests/                 # unit tests (124 passing — executor, actions, composite
                        #   action, plugin adapter, intent parsing, full session
                        #   flow for folder/project-creation missions, and Memory:
                        #   persistence, retrieval, conversational queries)
```

## Getting started

```
pip install -e ".[dev,voice,ui]"
pytest
kalpavriksha                 # the founder command: recover, wire, run, watch
python -m master_agent.cli   # try the real create-folder conversation
```

`kalpavriksha` recovers previous state, discovers Executives, starts the
Runtime, and hands the terminal to the Founder Dashboard — which opens on
a page answering three questions: what is it doing, does it need you, what
next. Press `V` for the engineering panels. Useful flags:

```
kalpavriksha --boot-only        # print the boot report and exit
kalpavriksha --demo             # submit one demonstration objective
kalpavriksha --approval-timeout 300   # expire unanswered approvals (default: never)
```

When something irreversible is about to run, it appears in the Approval
panel and **waits for you**:

```
PENDING APPROVALS (1)
  [1] Filesystem.DeleteFolder
      Executive : filesystem
      Reason    : Delete Folder
      Risk      : IRREVERSIBLE
      Impact    : Deletes 14 files
      Requested : 22:13
  [A]pprove N   [R]eject N   [D]efer N   approve all
```

Type `approve 1`, `reject 1`, `defer 1`, or `approve all`. Every decision
is recorded in an immutable ledger with who decided and when; deferred
requests survive a restart; a restored approval is evidence, never fresh
authority.

**Nothing irreversible runs unless you approved it.** Every capability
above `READ_ONLY` is checked against the Permission System before it
executes, on every path, and a Runtime with no approval gate wired refuses
to execute at all. Irreversible capabilities (`delete_file`,
`delete_folder`) can never be covered by a standing grant — they need a
fresh decision every time. Detail: `RUNTIME_ENGINE_ARCHITECTURE.md` §4a
and `docs/MISSION_BRIEF_028_0.md`.

## Principles this scaffold is built to honor

Intent over prompts. Outcome over output. Everything is a plugin. Human
approval before important actions. Local-first, cloud-enhanced. Replaceable
modules. Maintainable code over clever code. Build for one founder first,
scale for millions later.
