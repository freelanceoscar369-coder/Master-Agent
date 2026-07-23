# ADR-0005: LocalExecutor uses its own grant key, relayed by the Plugin adapter

Status: Accepted (2026-07-23) — Mission Brief 002

## Context

Mission Brief 002 introduced `LocalExecutor` as the single component
allowed to perform local actions (ADR-0003's "everything is a plugin"
principle extended one layer deeper: everything *local* is an Action
executed by the Executor). The brief required: "The Executor MUST call
the existing Permission System before performing irreversible actions.
Do not duplicate permission logic. Reuse the existing implementation."

The Orchestrator already gates plugin invocation on the Permission System
(`orchestrator/orchestrator.py`, unchanged since Mission Brief 001) —
checking and, for `GrantScope.ONCE`, consuming a grant keyed to
`(plugin.manifest.name, capability)` before calling `plugin.invoke()`.

A naive second check inside the Executor, on that *same* grant key, is
broken: the Orchestrator's check already consumed the `ONCE` grant before
`invoke()` (and therefore the Executor) ever runs. The Executor's check
would then always raise `ApprovalRequired`, even immediately after a
human approved the action — the Permission System's `ONCE`-consumption
fix from Mission Brief 001 (see `DECISIONS.md`) would make this refactor
break every mission.

## Options considered

1. **Remove the Orchestrator's own check**, making every Plugin
   responsible for self-gating. Rejected: this changes a documented,
   tested, generic contract (`ARCHITECTURE.md` §4.5) for every plugin,
   not just Executor-backed ones, and would have required updating
   `test_plugin_registry.py`'s generic Plugin test to match — a bigger,
   riskier diff than the brief's "do not over-engineer" called for.
2. **Non-consuming peek in one of the two checkpoints.** Rejected: makes
   `ONCE` grants behave like unlimited grants for whichever caller uses
   the peek, silently reintroducing the exact bug Mission Brief 001 fixed
   — for any plugin that doesn't also route through a consuming check
   downstream.
3. **Different grant key for the Executor's check, relayed by the Plugin
   adapter.** Chosen — see Decision.

## Decision

`LocalExecutor.execute()` checks and consumes a grant keyed to
`(self.name, action.name)` — e.g. `("local_executor", "create_folder")`
— which is a *different* key from the Orchestrator's
`("filesystem", "create_folder")`. Because `PermissionSystem` grants are
keyed by `(plugin_name, capability)` tuples, these two checks don't
collide: the Orchestrator's consumption of its key doesn't affect the
Executor's.

`FilesystemPlugin.invoke()` — having already passed the Orchestrator's
gate by the time it runs at all — relays that approval to the Executor's
key: `self._executor.permissions.grant(self._executor.name, capability,
GrantScope.ONCE)`, immediately before calling `execute()`. The human is
asked exactly once; the relayed grant is consumed the instant it's used.

This keeps the Executor's check *real*, not theater: anything that calls
`LocalExecutor.execute()` directly — bypassing a Plugin/Orchestrator
entirely, which will happen once actions like `RunPowerShell` exist and
some future caller invokes one without going through a properly-gated
adapter — gets no relayed grant and is correctly refused. The Orchestrator
path only works because `FilesystemPlugin` explicitly, visibly relays an
approval it already received; it can't be invoked implicitly by accident.

## Consequences

- Zero changes to `Orchestrator`, `PermissionSystem`, or
  `test_plugin_registry.py` — the existing generic Plugin/Orchestrator
  contract is untouched and still fully tested by the original
  `FakeCalendarPlugin` fixture.
- Every future local-action Plugin adapter (once one exists for, say,
  git operations) must remember to relay its grant the same way
  `FilesystemPlugin` does. This is a real coupling a future engineer
  needs to know about — it isn't enforced by the type system, only by
  convention and this ADR. If a second Executor-backed plugin ships
  without noticing this pattern, its actions will always raise
  `ApprovalRequired` even after Orchestrator-level approval — a
  same-symptom-different-plugin version of the bug this ADR fixes.
  Worth revisiting if/when a third local-action plugin is added: a small
  base class (e.g. `LocalExecutorPlugin`) that does the relay generically
  would remove this footgun. Not built now — one working example doesn't
  justify the abstraction yet ("do not over-engineer").
- `LocalExecutor.name` defaults to `"local_executor"` — a single shared
  executor instance's grant namespace is shared across every action
  registered on it. Not a problem today (one executor, one action), but
  worth knowing before assuming action-level grant isolation that doesn't
  actually exist at the executor level.
