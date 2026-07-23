# Mission Brief 003.1 — First Real Mission

Status: Implemented (2026-07-23)

## Objective

Mission Brief 003 proved `WorkspaceBootstrapAction` could compose two
primitives safely through the Executor and Permission System — but it
was reachable only through direct `invoke()` calls in a test file. This
brief connects it to real conversation. Typing "Create a Python project
called Demo." or "Create a project called Expense Tracker." at
`python -m master_agent.cli` now completes a real mission, through the
full stack: Conversation → Intent Parser → Mission → Planner →
Permission System → Executor → `WorkspaceBootstrapAction` →
`CreateFolderAction` / `WriteFileAction`. No layer was bypassed, and no
new architecture was introduced — this brief is entirely about wiring
layers that already existed.

## Architecture summary

Two functions in `src/master_agent/cli.py` — `parse_intent()` and
`build_plan()` — have played the role of the Intent Layer and Planner
for the CLI demo since Mission Brief 001 (both are documented stand-ins;
the real `Planner` class in `planner/planner.py` is still a stub that
raises `NotImplementedError` until a live Model Router provider exists —
see `ARCHITECTURE.md` §4.1-4.2). This brief extended both, without
touching anything below them:

- **`parse_intent()`** gained a second regex, `_CREATE_PROJECT_RE`,
  recognizing "create [a/an/a new] [\<type\>] project/application
  called/named X". It extracts a project name and an optional type; the
  type is looked up in a small `_PROJECT_TEMPLATES` dict, and an
  omitted or unrecognized type resolves to a `"generic"` fallback rather
  than failing the request. A name that fails the same
  `is_unsafe_relative_path()` check `WriteFileAction`/
  `WorkspaceBootstrapAction` already use (Mission Brief 003) raises a new
  `InvalidProjectRequest`, distinct from `UnrecognizedInput` — the human
  clearly asked for a project, so the reply explains what's wrong with
  the name instead of claiming the request wasn't understood at all.
- **`build_plan()`** gained a branch: given a `ParsedProjectIntent`, it
  looks up the project's template function (`_python_project_template`
  or `_generic_project_template`), calls it with the project name to get
  a `{folders, files}` shape, and builds a **single** `Step` naming the
  `workspace_bootstrap` capability with that shape as its payload.

```
Conversation ("Create a Python project called Demo.")
  → parse_intent() → ParsedProjectIntent(name="Demo", type="python")
  → build_plan()   → MissionPlan([Step(capability="workspace_bootstrap",
                                        payload={name, folders, files})])
  → Mission(intent_summary=text), same Mission class, no special case
  → Orchestrator.execute_plan()  ← UNCHANGED since Mission Brief 001
      → PluginRegistry resolves "workspace_bootstrap" → FilesystemPlugin
      → PermissionSystem.check() → ApprovalRequired (first pass)
  → CLI shows the plan, asks Yes/No
  → human answers "Yes" → ONE grant issued, ONE relay mechanism reused
      (`_handle_approval_response()` — UNCHANGED, capability-agnostic
      since it was written)
  → Orchestrator.execute_plan() again → FilesystemPlugin.invoke()
      → relays its grant to the Executor (ADR-0005)
      → LocalExecutor.execute("workspace_bootstrap", payload)
      → WorkspaceBootstrapAction.run()
          → relays a grant + executes "create_folder"  [× N]  (ADR-0006)
          → relays a grant + executes "write_file"      [× N]  (ADR-0006)
  → Mission COMPLETED, outcome recorded, completion message shown
```

**What did NOT change**, and why that matters: `Mission`,
`Orchestrator`, `PermissionSystem`, `LocalExecutor`,
`WorkspaceBootstrapAction`, `CreateFolderAction`, `WriteFileAction`, and
`FilesystemPlugin` are all byte-identical to how Mission Brief 003 left
them. `_handle_approval_response()` in `cli.py` was already fully
capability-agnostic (it reads `step.capability` and grants against
whatever that is) — it required zero changes to support project
creation. This is the payoff of Mission Brief 003's design: a brand new
kind of mission reached production through the conversation layer by
extending exactly two functions, not by touching the execution stack.

## Files changed

**Modified:**
- `src/master_agent/cli.py` — `_CREATE_PROJECT_RE`, `ParsedProjectIntent`,
  `InvalidProjectRequest`, the two project template functions +
  `_PROJECT_TEMPLATES`/`_resolve_project_type`/`_template_for`,
  `_validate_project_name`, `parse_intent()` and `build_plan()` extended
  with a project branch, `MasterAgentSession._approval_message()` /
  `_project_completion_message()` added, `_finish()` now takes `intent`
  and dispatches on its type. The folder-creation code paths inside these
  same functions are untouched — see the regression tests.
- `src/master_agent/plugins/base.py` — `InvocationResult` gained an
  optional `execution_time_seconds: float = 0.0` field (see "A bug found
  while wiring this up" below).
- `src/master_agent/plugins/filesystem_plugin.py` — `invoke()` now
  forwards `result.execution_time_seconds` from the Executor's
  `ExecutionResult` into the `InvocationResult` it returns, on both the
  success and failure path.
- `tests/test_cli_session.py` — new "Mission Brief 003.1: project
  creation" section (see Testing below); the entire Mission Brief 001
  folder-creation section above it is unchanged, both in code and in
  wording, and still passes.
- `ARCHITECTURE.md` §4.1-4.2 — documents `cli.py`'s rule-based
  Intent-Layer/Planner stand-in and how it now produces a
  `workspace_bootstrap` step for project intents.
- `PROJECT_BRAIN.md`, `README.md` — status sections updated.

**New:**
- `docs/MISSION_BRIEF_003_1.md` (this file)

**Unchanged (verified, not assumed):** `Mission`, `Orchestrator`,
`PermissionSystem`, `LocalExecutor`, `WorkspaceBootstrapAction`,
`CreateFolderAction`, `WriteFileAction`, `PluginRegistry`,
`planner/planner.py` (still the `NotImplementedError` stub) — the whole
point of this brief was reaching an existing capability without touching
its execution stack.

## Intent Parser

Examples recognized, with what's extracted:

| Input | Project name | Project type | Template used |
|---|---|---|---|
| "Create a Python project called Demo." | Demo | python | Python |
| "Create a project called Expense Tracker." | Expense Tracker | (omitted) | generic |
| "Create a new application named Budget App." | Budget App | (omitted) | generic |
| "Create a Rust project called Widget." | Widget | (unrecognized) | generic |

The regex's optional type group only captures when a word immediately
precedes the literal "project"/"application" — the engine naturally
backtracks past it when there's no separate type word (see the inline
comment on `_CREATE_PROJECT_RE`), so "create a project called X" and
"create a Python project called X" both parse correctly without two
separate patterns.

## Mission

`Mission(intent_summary=text)` — the exact same constructor call Mission
Brief 001 used, no special-case branch. The Mission entity has no idea
whether its plan targets `create_folder` or `workspace_bootstrap`.

## Planner

`build_plan()`'s project branch (see Architecture summary) produces a
**single** `Step`. The three-line "Plan" the user sees
(`• Create workspace / • Create folders / • Create starter files`) is a
presentational summary built for display, not three separate `Step`
objects in the `MissionPlan` — the actual DAG has one step naming the
composite capability, and the composite's own internal fan-out (into
`create_folder`/`write_file` calls) happens one layer down, inside
`WorkspaceBootstrapAction`, exactly as designed in Mission Brief 003.
This keeps the Orchestrator's contract exactly what it's always been:
one step per plan-level unit of work, regardless of how much a single
capability does internally.

## Permission

Exactly one `GrantScope.ONCE` grant is issued per mission, on
`(plugin.manifest.name, step.capability)` — for a project mission that's
`("filesystem", "workspace_bootstrap")`. The composite's own relay of
that approval down to its sub-actions (ADR-0006) happens entirely inside
`WorkspaceBootstrapAction`, invisibly to `cli.py`. Verified by a
dedicated test that a full Python project mission completes with exactly
one "Yes" answer.

## Execution

`Orchestrator.execute_plan()` → `FilesystemPlugin.invoke("workspace_bootstrap", ...)`
→ `LocalExecutor.execute("workspace_bootstrap", ...)` →
`WorkspaceBootstrapAction.run()`. No filesystem action is ever called
directly by `cli.py` or by the Orchestrator — the composite is the only
thing that talks to `create_folder`/`write_file`, exactly as Mission
Brief 003 designed it.

## Project template

**Python** (`_python_project_template`):
```
<ProjectName>/
  README.md
  .gitignore
  requirements.txt
  src/
  tests/
  docs/
  config/
  main.py
```
5 `create_folder` calls (root + 4 subfolders), 4 `write_file` calls.
No virtual environment, no `git init`, no package installation — exactly
as scoped; those are explicitly future missions.

**Generic** (`_generic_project_template`, the default for an omitted or
unrecognized type):
```
<ProjectName>/
  README.md
  src/
  docs/
```
3 `create_folder` calls, 1 `write_file` call. Minimal on purpose — it's
meant to be a safe, useful default, not a second opinionated template.

## User experience

```
> Master Agent
Hello! I'm awake.
What would you like me to do?

> Create a Python project called Demo.
I understood your request.

Mission:
Create Python Project

Project:
Demo

Plan:
• Create workspace
• Create folders
• Create starter files

This will modify your filesystem.
Approve? (Yes/No)

> Yes
Done.
Python project "Demo" created successfully.

Execution time: 0.001 seconds
Folders created: 5
Files created: 4

Mission completed successfully.
```

(Execution time is genuinely sub-millisecond against a local filesystem —
the illustrative "0.4 seconds" in the brief's example was just that, an
illustration; the actual number reported is always the real measured
`ExecutionResult.execution_time_seconds` from the Executor, never a
hardcoded value.)

## Error handling

- **Unknown project type** → falls back to the generic template
  silently (no error shown — the mission still succeeds, just with the
  default layout). Tested explicitly with "Create a Rust project called
  Widget."
- **Invalid project name** (empty, or fails
  `is_unsafe_relative_path()`) → `InvalidProjectRequest` is raised by
  `parse_intent()` before any `Mission` is created; the reply explains
  the specific problem and suggests a working example. Tested with
  "Create a project called /etc." (an absolute path).
- **Permission denied** (human answers "No") → reuses the exact decline
  path Mission Brief 001 built (`mission.transition(CANCELLED)`,
  "Okay, cancelled. Nothing was changed.") — already capability-agnostic,
  needed no changes.
- **Filesystem failure** → surfaces through the exact same generic
  `_finish()` failure branch folder-creation missions use
  (`"Something went wrong: {error}"`), backed by
  `LocalExecutor`/`WorkspaceBootstrapAction`'s existing guarantee (since
  Mission Brief 002/003) that a raw exception never escapes as a
  traceback — structured errors only.

## Testing

All added to `tests/test_cli_session.py`, in a new section clearly
separated from the Mission Brief 001 folder-creation tests (which are
untouched):

- **`parse_intent` coverage**: recognizes all four example phrasings,
  case-insensitively; unrecognized type falls back to `"generic"`;
  `InvalidProjectRequest` raised for an unsafe name; `_validate_project_name()`
  unit-tested directly for empty/unsafe/ordinary names.
- **Python project creation** — full conversation: plan display, approval,
  completion message, exact folder/file layout on disk, mission outcome.
- **Generic project creation** — same, with an omitted type, confirming
  the *generic* template (not Python's) is what actually got built.
- **Unrecognized type falls back to generic** — a specified-but-unknown
  type ("Rust") still succeeds, using the generic template.
- **Permission denied** — declining creates nothing, mission `CANCELLED`.
- **Invalid project name** — explains the problem, creates no Mission,
  touches no filesystem.
- **Only one approval needed** — confirms the composite's internal relay
  (ADR-0006) means a single "Yes" is enough for the whole project mission.
- **Full conversation transcript** — a dedicated test walking wake →
  request → plan → approval → completion, asserting on the shape of every
  message, closest to a literal reproduction of this brief's UX example.
- **Regression** — every Mission Brief 001/002/003 test is unchanged and
  still passes; the only new import into `test_cli_session.py` is the
  handful of new names this brief added.

## Test results

```
93 passed in 0.15s
```

(88 tests carried over from Mission Brief 001/002/003 + 17 new project-
creation tests in `tests/test_cli_session.py`, all in one run, no
regressions. One real bug was found and fixed while writing these tests —
see "A bug found while wiring this up" below.)

## Ruff results

```
All checks passed!
```

## Manual transcript

Two live conversations run against a sandboxed temp directory through
`MasterAgentSession` — the exact class `python -m master_agent.cli` uses,
not a mock:

```
> Master Agent
Hello! I'm awake.
What would you like me to do?

> Create a Python project called Demo.
I understood your request.

Mission:
Create Python Project

Project:
Demo

Plan:
• Create workspace
• Create folders
• Create starter files

This will modify your filesystem.
Approve? (Yes/No)

> Yes
Done.
Python project "Demo" created successfully.

Execution time: 0.001 seconds
Folders created: 5
Files created: 4

Mission completed successfully.
```

Filesystem after that conversation:
```
Demo/
  .gitignore
  README.md
  config/
  docs/
  main.py
  requirements.txt
  src/
  tests/
```

Second conversation, generic template (omitted type):
```
> Master Agent
Hello! I'm awake.
What would you like me to do?

> Create a project called Expense Tracker.
I understood your request.

Mission:
Create Project

Project:
Expense Tracker

Plan:
• Create workspace
• Create folders
• Create starter files

This will modify your filesystem.
Approve? (Yes/No)

> Yes
Done.
project "Expense Tracker" created successfully.

Execution time: 0.000 seconds
Folders created: 3
Files created: 1

Mission completed successfully.
```

## A bug found while wiring this up

Not a design problem like ADR-0005/0006 — a straightforward missing
field, caught immediately by the new tests (5 of them failed on the
first run with `AttributeError: 'InvocationResult' object has no
attribute 'execution_time_seconds'`) rather than shipping silently.

`WorkspaceBootstrapAction`/`LocalExecutor` measure execution time on
their internal `ExecutionResult` (Mission Brief 002), but
`FilesystemPlugin.invoke()` was translating that into the Plugin-layer
`InvocationResult` (`plugins/base.py`) without carrying the timing
across — `InvocationResult` never had a field for it because nothing
before this brief needed to show a human "how long did that take."
Fixed by adding an optional `execution_time_seconds: float = 0.0` field
to `InvocationResult` (default-valued, so every other plugin and every
existing test that constructs one is unaffected) and having
`FilesystemPlugin.invoke()` forward the real measured value on both the
success and failure path. Small, generic, and not scoped to project
creation — any future plugin invocation can now report real timing
through the same field.

## Remaining stubs

Everything Mission Brief 003 already listed, unchanged, plus: the real
Planner (this brief's `build_plan()` extension is still `cli.py`'s
rule-based stand-in, not a model call); no `git init`/venv/package
install in the Python template (explicitly out of scope, per the brief);
only one project type has a real template (`python`) — every other type
word silently uses the generic fallback, which is correct behavior but
means "Create a Node project called X" produces the same generic layout
as "Create a project called X" today.

## Recommendation for Mission Brief 004

Two candidates:

1. **A second real project template** (e.g. `node`/`javascript`, or a
   generic "empty git repo" type) — the first test of whether
   `_PROJECT_TEMPLATES` actually generalizes as a dict-extension pattern,
   the same way Mission Brief 003 tested whether the Action Contract
   generalized past one example.
2. **Wire the decline-and-retry loop**: today, declining a project
   mission ends it outright (`CANCELLED`) — there's no way to say "no,
   call it something else" without starting the whole conversation over.
   A real Planner (or even a slightly smarter rule-based layer) that can
   revise a plan in place, rather than discard it, is the natural next
   step once more than one mission type exists to make that revision
   loop worth building well.
