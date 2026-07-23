# Mission Brief 002 — Generic Local Executor

Status: Implemented (2026-07-23)

## Objective

Mission Brief 001 proved the architecture works by making one mission
real: create a folder. This brief generalizes *how* that mission
executes, so every future local capability — create/read/rename/delete/
copy/move file, run PowerShell/CMD, git operations, VS Code operations,
Obsidian operations — plugs into the same execution path instead of each
being a special case. No new user-facing features; no voice, model
routing, memory persistence, or cloud integration.

## Architecture summary

```
Orchestrator → PluginRegistry → Plugin.invoke() → LocalExecutor.execute()
                                  (thin adapter)      → Action.validate()
                                                       → PermissionSystem.check()
                                                       → Action.run() → filesystem
```

Two new concepts, both under `src/master_agent/executor/`:

- **`Action`** (`action.py`) — the contract every local capability
  implements: `name`, `description`, `risk_tier`, `expected_result`,
  `required_parameters()`, `validate(parameters)`, `run(parameters)`.
  Deliberately small — six things to implement, not a framework.
- **`LocalExecutor`** (`executor.py`) — the only component allowed to
  perform local actions. `execute(action_name, parameters)` looks up the
  registered `Action`, validates parameters (fails fast, no permission
  check for a malformed request), checks the Permission System, runs the
  action, catches anything that escapes (never a raw traceback), and logs
  every execution (action, start time, end time, duration, status) to an
  in-memory list.

`FilesystemPlugin` (`plugins/filesystem_plugin.py`) is now a thin adapter:
it registers a `CreateFolderAction` on whatever `LocalExecutor` it's
given and forwards `invoke()` calls to `execute()`, translating the
result shape. All the actual create-folder logic — idempotency, error
handling, the `mkdir` call — moved to
`executor/actions/create_folder.py`'s `CreateFolderAction`, unchanged in
behavior from Mission Brief 001.

**The Orchestrator did not change.** It still resolves capability → plugin
via the registry, checks the Permission System, and calls `invoke()` —
exactly as in Mission Brief 001. The generalization happened entirely
inside what a Plugin can do internally, which is the point: this is
additive architecture, not a rewrite.

### The permission design problem, and how it was resolved

The brief required the Executor to check the Permission System itself,
reusing the existing implementation without duplicating logic. But the
Orchestrator already checks permission before calling `invoke()` — and
`GrantScope.ONCE` grants are consumed on use (a bug fixed in Mission
Brief 001). A second check on the *same* grant, inside the Executor,
would always fail: the Orchestrator's check already consumed it.

The fix: the Executor checks a *different* grant key —
`(executor.name, action.name)` instead of `(plugin.name, capability)` —
and `FilesystemPlugin.invoke()` relays the approval it already received
from the Orchestrator down to that key, scoped `ONCE`, immediately before
calling `execute()`. The human is asked exactly once. The Executor's
check stays real for anything that calls it directly, bypassing a
Plugin/Orchestrator entirely — which will matter the moment a second
local-action plugin exists. Full reasoning:
`docs/adr/0005-executor-permission-relay.md`.

## Files changed

**New:**
- `src/master_agent/executor/__init__.py`
- `src/master_agent/executor/action.py` — `Action` ABC, `ExecutionResult`
- `src/master_agent/executor/executor.py` — `LocalExecutor`, `ExecutionLogEntry`
- `src/master_agent/executor/actions/__init__.py`
- `src/master_agent/executor/actions/create_folder.py` — `CreateFolderAction`
- `docs/adr/0005-executor-permission-relay.md`
- `docs/MISSION_BRIEF_002.md` (this file)
- `tests/test_executor.py`
- `tests/test_create_folder_action.py`

**Modified:**
- `src/master_agent/plugins/filesystem_plugin.py` — rewritten as a thin
  adapter (manifest and capability name unchanged; constructor now takes
  a `LocalExecutor`)
- `src/master_agent/cli.py` — `build_default_session()` now constructs a
  `LocalExecutor` and injects it into `FilesystemPlugin`; module docstring
  updated
- `tests/test_cli_session.py` — `build_session()` helper updated for the
  new constructor shape; every assertion in the file is unchanged
- `tests/test_filesystem_plugin.py` — rewritten to test the adapter
  (delegation, error-shape translation, manifest) rather than business
  logic, which moved to `test_create_folder_action.py`
- `ARCHITECTURE.md` — new §4.7 Local Executor, data-flow diagram updated,
  §4.6 cross-referenced, §6 open questions updated
- `PROJECT_BRAIN.md`, `README.md` — status sections updated

**Unchanged (verified, not assumed):**
- `src/master_agent/orchestrator/orchestrator.py`
- `src/master_agent/permissions/permission_system.py`
- `tests/test_plugin_registry.py`

## Tests added

18 new tests across two files:

- `tests/test_executor.py` (13 tests) — successful execution (read-only
  and reversible-write with grant), permission denied (raises
  `ApprovalRequired`, logged as `blocked_on_approval`), `ONCE` grant
  consumption, invalid parameters (structured failure, permission never
  consulted), unknown action (structured failure, not an exception),
  executor failure propagation (an action that raises internally becomes
  a structured failure with no raw traceback), logging (every execution
  recorded with required fields, log accumulates, log property returns a
  copy), duplicate action registration rejected.
- `tests/test_create_folder_action.py` (8 tests) — the exact business
  logic that used to be inline in `FilesystemPlugin`, now tested against
  `CreateFolderAction` directly: validation (missing name, unknown
  location, default location), run (create, idempotent re-create with a
  warning, collision with a non-directory file).

Plus regression coverage: `tests/test_filesystem_plugin.py` (6 tests,
rewritten) confirms the adapter correctly delegates, translates errors,
and relays permission without asking twice.
`tests/test_cli_session.py` (unchanged assertions) is the end-to-end
regression test — same transcript, same behavior as Mission Brief 001.

## Test results

```
41 passed in 0.24s
```

All passing on the first full run after implementation — no back-and-forth
fixes needed once the permission-key design was worked out up front.

## Ruff results

```
All checks passed!
```

## Live verification

Ran the exact Mission Brief 001 transcript (`Master Agent` →
`Create a folder called Demo on my Desktop.` → `Yes`) against a sandboxed
temp directory through the new code path. Output was byte-for-byte
identical to Mission Brief 001's transcript, the folder was actually
created, and the Executor's log showed one entry:
`action=create_folder status=success duration=0.000392s`.

## Technical debt introduced

1. **The permission-relay pattern is convention, not enforcement.**
   `FilesystemPlugin.invoke()` has to remember to call
   `self._executor.permissions.grant(self._executor.name, capability,
   GrantScope.ONCE)` before calling `execute()`. Nothing in the type
   system requires this — a future local-action plugin author who forgets
   it will get `ApprovalRequired` raised on every call, even after
   Orchestrator-level approval, which is a confusing failure mode to debug
   without knowing this ADR exists. Flagged in ADR-0005 as worth a shared
   base class once a second Executor-backed plugin exists; not built now,
   since one example doesn't justify the abstraction yet.
2. **`LocalExecutor`'s grant namespace is shared across all actions
   registered on one executor instance** (keyed on `executor.name`, not
   per-action). Not a problem with one action registered; would need
   revisiting if per-action grant isolation ever matters.
3. **`ApprovalRequired` is a plain `Exception` subclass**, so a plugin
   with a broad `except Exception` in its own `invoke()` (both
   `ChatGPTProvider` and `HermesProvider` currently have one, inherited
   from `ModelProvider.invoke()`) would silently swallow it rather than
   letting it propagate. Not currently triggered — both providers declare
   `READ_ONLY` risk, which never raises `ApprovalRequired` — but latent,
   and worth a narrower except clause the day either provider's risk tier
   changes.

## Remaining stubs

Unchanged from Mission Brief 001, plus: every local capability other than
`create_folder` (read/rename/delete/copy/move file, PowerShell/CMD, git,
VS Code, Obsidian) — the Executor now makes these cheap to add, but none
are implemented. Planner, Mission Manager persistence, Model Router wiring
to live providers, Memory persistence, Voice I/O, Desktop UI remain
exactly as described in `docs/MISSION_BRIEF_001.md`.

## Recommendation for Mission Brief 003

Add a **second** local action through the Executor — something small and
genuinely different in shape from `create_folder`, e.g. `ReadFileAction`
(read-only, no approval needed at all) or `DeleteFileAction`
(irreversible risk tier, the first action that isn't `reversible_write`).
This is higher-value than it sounds: it's the first real test of whether
the Action Contract and the permission-relay pattern actually generalize,
versus having only ever been exercised by the one action that motivated
their design. It would also surface whether the base-class extraction
flagged in ADR-0005's technical debt is worth doing yet, with real
evidence instead of a guess.
