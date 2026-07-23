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
change from Mission Brief 001 — same transcript, same behavior. See
`docs/MISSION_BRIEF_001.md` and `docs/MISSION_BRIEF_002.md` for what's
genuinely production-ready versus still stubbed, and try it yourself:

```
pip install -e ".[dev]"
python -m master_agent.cli
```

Everything beyond that one execution path — Planner, Mission Manager,
Model Router, Memory, ChatGPT/Hermes providers, Voice, Desktop UI, and
every local action besides `create_folder` — is still the scaffold-stage
interface described below, not wired to anything real yet.

## Layout

```
src/master_agent/
  cli.py               # Mission Brief 001: the one working end-to-end conversation
  orchestrator/      # walks a MissionPlan, invokes plugins via the registry
  planner/            # Intent -> MissionPlan
  mission_manager/    # Mission entity + state machine
  memory/             # local-first storage (SQLite + local embeddings)
  permissions/        # approval gate for non-read-only plugin actions
  executor/            # Mission Brief 002: LocalExecutor + Action contract + actions/
  plugins/            # Plugin contract, registry, filesystem_plugin.py, providers/ (ChatGPT, Hermes)
  voice/              # STT (input) / TTS (output) adapters
  ui/                 # notes on the desktop UI boundary (separate process)
docs/adr/              # architecture decision records
docs/MISSION_BRIEF_001.md  # what Mission Brief 001 proved
docs/MISSION_BRIEF_002.md  # what the Local Executor is and why, and what's next
tests/                 # unit tests (41 passing — executor, actions, plugin adapter, intent parsing, full session flow)
```

## Getting started

```
pip install -e ".[dev,voice,ui]"
pytest
python -m master_agent.cli   # try the real create-folder conversation
```

## Principles this scaffold is built to honor

Intent over prompts. Outcome over output. Everything is a plugin. Human
approval before important actions. Local-first, cloud-enhanced. Replaceable
modules. Maintainable code over clever code. Build for one founder first,
scale for millions later.
