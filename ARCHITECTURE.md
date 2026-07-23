# Master Agent — System Architecture

Status: Draft v0.1 (Founder Edition kickoff)
Owner: Senior Software Engineer / System Architect
Last updated: 2026-07-23

## 1. Purpose

Master Agent is the orchestration layer between human intention and software
execution — the Kalpavriksha Principle: **Intent → Plan → Delegate → Execute
→ Verify → Learn → Report.**

This document describes the module boundaries, data flow, and the plugin
contract that everything else in the system builds on. It is a living
document — update it whenever a module boundary or contract changes.

## 2. Guiding constraints (from the founding brief)

These aren't slogans, they're design constraints this architecture is
answerable to:

- **Intent over prompts.** The system captures a structured `Intent`
  object (goal, constraints, context, success criteria), not a raw prompt
  string that gets passed straight to a model.
- **Outcome over output.** A Mission isn't "done" because a model produced
  text; it's done because the Verifier confirmed the real-world state
  matches the intent's success criteria.
- **Everything is a plugin.** Model providers, capabilities (calendar,
  filesystem, browser, etc.), voice adapters, even the UI transport, are
  all plugins behind the same registry and contract. The core engine
  should be small; almost all capability lives in plugins.
- **Human approval before important actions.** No plugin may execute a
  step classified above `read-only` risk without a Permission System grant.
- **Local-first, cloud-enhanced.** The system must be fully functional
  offline against a local model and local memory. Cloud providers
  (ChatGPT) are an enhancement the Model Router opts into, never a hard
  dependency.
- **Replaceable modules.** Every module in §4 is swappable behind its
  interface without touching the others. This is what makes "build for
  one founder first, scale for millions later" possible — you don't
  rewrite the engine to swap SQLite for Postgres or Piper for a cloud TTS.

## 3. High-level data flow

```
 Voice / Text Input
        │
        ▼
   Intent Layer  ──────────────► structured Intent (goal, constraints, context)
        │
        ▼
     Planner  ─────────────────► Mission Plan (DAG of Steps, each bound to a Capability)
        │
        ▼
  Mission Manager  ◄──────────► Local Memory (mission state, history)
        │  (state machine: draft → planned → awaiting_approval →
        │   executing → verifying → completed | failed | cancelled)
        ▼
  Permission System  ───────────► blocks on any step above read-only risk
        │  until human approves (voice / UI)
        ▼
   Orchestrator  ───────────────► resolves each Step to a Plugin via the
        │                          Plugin Registry, invokes it, collects results
        ▼
   Plugin Runtime
    ├─ Model Providers (ChatGPT, Hermes-local, ...)
    ├─ Capability Plugins (fs, calendar, browser, ...)
    │     │  local-action plugins delegate here:
    │     ▼
    │  Local Executor ──► Action (validate → permission check → run)
    │     │                  ├─► e.g. CreateFolderAction/WriteFileAction → filesystem
    │     │                  └─► e.g. WorkspaceBootstrapAction → relays a grant to,
    │     │                          then calls, Local Executor again per sub-step
    │     ▼
    │  ExecutionResult + log entry (action, times, duration, status)
    │     — one entry per sub-step too, for a composite action
    │
    └─ Voice I/O Adapters (STT, TTS)
        │
        ▼
     Verifier  ────────────────► checks outcome against Intent's success criteria
        │
        ▼
    Reporter  ─────────────────► voice + UI report back to the human
        │
        ▼
   Local Memory  ───────────────► mission + outcome recorded for future planning (Learn)
```

## 4. Module boundaries

Each module is a separate Python package under `src/master_agent/`, talks to
its neighbors only through the interfaces below, and can be replaced
independently.

### 4.1 Intent Layer
Turns raw input (voice transcript or typed text) into a structured `Intent`.
This is deliberately *not* "send the raw string to an LLM" — it's a real
parsing/clarification step so the Planner never has to guess what the human
meant. Owns follow-up clarification questions when intent is ambiguous.

### 4.2 Planner (`planner/`)
Takes an `Intent`, produces a `MissionPlan`: a DAG of `Step` objects, each
naming a required `Capability` (not a specific plugin — the Orchestrator
resolves capability → plugin at execution time, so plans stay portable
across whichever plugins are installed). Planner itself calls a Model
Provider through the Model Router — planning is a capability like any other.

### 4.3 Mission Manager (`mission_manager/`)
Owns the `Mission` entity and its state machine. This is the single source
of truth for "what is happening right now" — the UI, voice reporter, and
Orchestrator all read mission state from here rather than tracking it
themselves. Persists to Local Memory so missions survive a restart.

States: `draft → planned → awaiting_approval → executing → verifying →
completed | failed | cancelled`.

### 4.4 Permission System (`permissions/`)
Every plugin declares a risk tier per capability it exposes:
`read_only | reversible_write | irreversible`. The Permission System is
consulted before the Orchestrator invokes anything above `read_only`, and
grants can be scoped `once`, `this_session`, or `always_for_capability`.
This module has veto power over the Orchestrator — it is not optional
middleware, it's a gate.

### 4.5 Orchestrator (`orchestrator/`)
Walks the `MissionPlan`, and for each `Step`: resolves capability → plugin
via the Plugin Registry, checks the Permission System, invokes the plugin,
captures the result (or failure) back onto the Mission. Retries and
failure-branching policy lives here, not in individual plugins.

### 4.6 Plugin Runtime (`plugins/`)
`base.py` defines the `Plugin` contract every capability, model provider,
and voice adapter implements: a manifest (name, version, capabilities
provided, risk tier per capability, input/output schema) plus an `invoke()`
method. `registry.py` discovers and indexes installed plugins at startup.
Model providers (`plugins/providers/`) are plugins like any other — ChatGPT
and local Hermes both implement the same `ModelProvider` interface, which is
what makes the Model Router possible (see §5). Plugins that need to touch
the local machine (filesystem, shell, git, ...) don't do that work
themselves — they delegate to the Local Executor (§4.7). `FilesystemPlugin`
is the first example: a thin adapter that registers a `CreateFolderAction`
and forwards `invoke()` calls to it.

### 4.7 Local Executor (`executor/`)
The only component allowed to perform local actions — added in Mission
Brief 002. `action.py` defines the **Action Contract** every local
capability implements: a name, description, risk tier, required
parameters, a `validate()` step, and a `run()` step that does the actual
work and returns a structured `ExecutionResult` (success, output, errors,
warnings, execution time). `executor.py`'s `LocalExecutor` is what
capabilities actually execute through: it looks up the registered Action,
validates parameters, checks the Permission System, runs the action,
catches anything that escapes (never a raw traceback), and logs every
execution (action, start/end time, duration, status) in memory.

This exists so that `create_folder` isn't a one-off special case: every
future local capability in `ARCHITECTURE.md`'s original list — create
file, read file, rename, delete, copy, move, run PowerShell/CMD, git
operations, VS Code operations, Obsidian operations — plugs into the same
Action Contract and runs through the same executor, with the same
validation, permission-gating, structured-failure, and logging behavior
for free. A Plugin adapter (like `FilesystemPlugin`) still exists above
it so the Orchestrator/PluginRegistry resolve capabilities the same way
they always have (ADR-0003 is unchanged) — the Executor is what that
adapter delegates to, not a replacement for the Plugin contract.

The Executor checks permission itself, using its own grant key distinct
from the Orchestrator's — see
`docs/adr/0005-executor-permission-relay.md` for why two independent
permission checks in the same call chain need different keys, and how the
Plugin adapter relays an already-obtained approval down to the Executor's
key without asking the human twice.

**Composite actions (Mission Brief 003).** Not every capability has to be
a filesystem primitive. `WorkspaceBootstrapAction` (`create_folder` +
`write_file`, composed) is the first example of an Action whose `run()`
doesn't touch the filesystem itself at all — it orchestrates other
Actions through the same `LocalExecutor.execute()` path every direct
caller uses, so every sub-step is independently validated, permission-
gated, and logged, with no rollback on partial failure (that limitation
is deliberate, not an oversight — see the ADR). This is the general
pattern for turning a sequence of primitives into a reusable, higher-
level mission (a "bootstrap a new workspace" capability, generically
parameterized by folders/files — not a hardcoded script) instead of
writing one-off orchestration logic outside the Action Contract. See
`docs/adr/0006-composite-action-relay.md` for how a composite relays its
own already-obtained approval down to each sub-action it invokes, the
same pattern ADR-0005 established one layer up.

### 4.8 Local Memory (`memory/`)
Local-first store (SQLite for structured mission/state data, plus a local
embedding index for semantic recall) — no cloud dependency for the system
to function. Holds mission history, learned user preferences, and the
plugin capability index cache. This is the "Learn" step of the
Kalpavriksha loop: outcomes recorded here feed back into future Planner
calls as context.

### 4.9 Voice I/O (`voice/`)
`input.py` wraps a local speech-to-text engine (default: local, e.g.
faster-whisper) behind a `Transcriber` interface; `output.py` wraps a local
text-to-speech engine (default: local, e.g. Piper) behind a `Speaker`
interface. Both are plugins, so a cloud STT/TTS provider can be swapped in
later without touching the Intent Layer or Reporter.

### 4.10 Desktop UI
A thin client, deliberately decoupled from the engine via a local HTTP/WS
API (not imported as a library). This means: the engine can run headless
(useful for testing and for a future server deployment), and the UI
technology choice doesn't leak into core architecture. Recommendation for
Founder Edition, given the 13-day runway: a local FastAPI server + a small
web UI, opened in a native window via `pywebview` — fastest path to a real
desktop app without committing to Electron/Tauri's build complexity yet.
This is a recommendation, not a locked decision — flag if you want to
evaluate Tauri instead before we scaffold it.

## 5. The Model Router — how ChatGPT and Hermes coexist

Both integrations sit behind one `ModelProvider` interface
(`generate(prompt, context, **opts) -> ModelResponse`). The Model Router
picks a provider per-call based on:

1. **Connectivity** — offline ⇒ local Hermes only, no exceptions.
2. **Privacy sensitivity** of the context — anything tagged sensitive by the
   Intent Layer stays on local Hermes unless the human explicitly
   overrides.
3. **Task profile** — planning/routine steps default to local Hermes
   (cheap, fast, private); steps that declare a need for stronger
   reasoning or a ChatGPT-specific capability escalate to ChatGPT.
4. **Explicit user preference**, which always wins.

This router is itself a plugin-registry lookup, not a hardcoded if/else —
adding a third provider later (e.g. Claude via API) means writing one new
`ModelProvider` plugin, not touching the router's core logic.

## 6. Open architecture questions to resolve before Aug 5

- **Hermes runtime**: assumed Ollama serving an OpenAI-compatible local
  endpoint (simplest integration surface, matches the `ModelProvider`
  contract almost 1:1). Confirm which local model you want as the default
  Hermes weight, and that Ollama (vs. LM Studio or raw llama.cpp) is the
  right runtime for you.
- **Desktop UI stack**: pywebview recommendation above needs a yes/no.
- **Plugin distribution**: for Founder Edition, plugins can just be local
  Python packages discovered by the registry at startup — no need to build
  a plugin marketplace/installer yet. Confirm that's acceptable for v0.1.
- **Local-executor-backed plugin/action base class**: the permission-grant
  relay pattern (`docs/adr/0005-executor-permission-relay.md`) is now
  hand-written twice — once in `FilesystemPlugin.invoke()`, once in
  `WorkspaceBootstrapAction._run_substep()`
  (`docs/adr/0006-composite-action-relay.md`). Two working examples make a
  stronger case for extraction than one did, but not yet a strong enough
  one — worth building a shared helper (e.g.
  `LocalExecutor.execute_relayed()`) the moment a third Executor-backed
  plugin or composite action needs the same relay.

See `docs/TIMELINE_RISK.md` for how these choices interact with the Aug 5
deadline.
