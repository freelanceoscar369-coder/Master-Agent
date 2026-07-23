# ADR-0006: Composite actions relay grants to their own sub-actions — the same pattern as ADR-0005, one layer deeper

Status: Accepted (2026-07-23) — Mission Brief 003

## Context

Mission Brief 003 asked for a `WorkspaceBootstrapAction` built as a
composition of smaller, reusable actions (`create_folder`, and a new
`write_file`) rather than a hardcoded "create project" script — with two
explicit constraints: do not bypass the Executor, and do not bypass the
Permission System.

Both constraints rule out the obvious naive implementation: a composite
`run()` that imports `CreateFolderAction`/`WriteFileAction` and calls
their `run()` methods directly. That would work, but every sub-step would
skip `LocalExecutor.execute()` entirely — no `validate()`, no permission
check, no log entry, no crash containment. The Executor's whole reason
for existing (ARCHITECTURE.md §4.7: "the only component allowed to
perform local actions") would be a lie the moment a composite action
existed, and the fact-finding value of `executor.log` — the granular,
per-step audit trail every future capability was supposed to get for
free — would silently stop working for anything that ran inside a
composite.

So a composite action's sub-steps have to go through
`self._executor.execute(sub_action_name, payload)`, the same call every
other caller uses. But that call checks permission on the sub-action's
own grant key — `(executor.name, "create_folder")`,
`(executor.name, "write_file")` — which is exactly the same double-check
problem ADR-0005 solved for the Plugin/Orchestrator boundary, now
reproduced one layer deeper: the composite's own entry into `execute()`
already consumed the grant for `(executor.name, "workspace_bootstrap")`;
that grant does nothing for the different keys its sub-steps need.

## Options considered

1. **Sub-actions call `run()` directly, bypassing the Executor.** Rejected
   outright — this is the thing the brief explicitly ruled out, and for
   good reason: see Context above.
2. **Grant `ALWAYS_FOR_CAPABILITY` for `create_folder`/`write_file` up
   front, inside `run()`, before invoking them.** Rejected: `ALWAYS`
   grants don't expire when the composite finishes — they'd silently
   authorize *any* future direct call to `create_folder` or `write_file`
   for the lifetime of the `PermissionSystem` instance, not just the
   sub-steps this composite needed. That's a much bigger, sneakier grant
   than the human ever approved, and it's exactly the kind of scope creep
   `GrantScope.ONCE` exists to prevent.
3. **Relay a fresh `ONCE` grant to each sub-action's key immediately
   before invoking it, mirroring `FilesystemPlugin.invoke()`'s relay from
   ADR-0005.** Chosen — see Decision.

## Decision

`WorkspaceBootstrapAction` is constructed with a reference to the same
`LocalExecutor` it will be registered on (dependency injection, same
pattern as the `locations` dict every action already takes). A private
helper, `_run_substep(action_name, payload)`, does exactly two things
before returning: `self._executor.permissions.grant(self._executor.name,
action_name, GrantScope.ONCE)`, then `self._executor.execute(action_name,
payload)`. Every sub-step — each `create_folder` call, each `write_file`
call — goes through this helper, so every one of them is validated,
permission-checked (via a grant relayed the instant before it's needed
and consumed the instant it's used), executed, and logged by the real
Executor, indistinguishable in the log from a call that arrived from
anywhere else.

This is structurally identical to ADR-0005's Plugin-layer relay. The
difference is *where* the relay happens: ADR-0005 relays at the
Plugin/Executor boundary (a `Plugin.invoke()` implementation relaying to
the Executor); this ADR relays at the Action/Executor boundary (an
`Action.run()` implementation — one that happens to also be a caller of
the Executor — relaying to itself). Both exist for the same reason: an
approval already obtained at an outer layer has to be explicitly,
visibly carried down to whatever inner grant key actually gates the next
call, because two independent permission checks in one call chain can
never safely share a key without breaking `GrantScope.ONCE`.

## Consequences

- Zero changes to `LocalExecutor`, `PermissionSystem`, or `Orchestrator`.
  The relay lives entirely inside `WorkspaceBootstrapAction`, the same
  way ADR-0005's relay lives entirely inside `FilesystemPlugin`.
- `executor.log` now shows the full trace of a composite mission: every
  sub-step logged individually, in the order it actually ran, plus one
  final entry for the composite itself (recorded last, in its own
  `finally` block, after `run()` — which invoked every sub-step — has
  already returned). This is a real debugging and audit win the brief
  didn't explicitly ask for but falls out of not bypassing the Executor.
- **No transactional rollback.** If sub-step 3 of 5 fails,
  `WorkspaceBootstrapAction.run()` returns immediately with
  `success=False` and an `output["completed_before_failure"]` list — but
  sub-steps 1 and 2 stay done on disk. A future mission that needs
  all-or-nothing semantics (e.g. an irreversible multi-file operation)
  will need a different pattern — a compensating-action list, or a
  two-phase commit-style staging step — not built here, since nothing in
  this brief's scope needed it and "do not over-engineer" applies.
- **This relay is convention, not enforcement — the same debt ADR-0005
  already flagged, now with a second instance of the pattern.** A future
  composite-action author who forgets to relay before invoking a
  sub-action gets the exact same confusing failure mode ADR-0005
  describes: `ApprovalRequired` raised on every sub-step, even though the
  composite itself was just approved. Two independent examples of the
  same footgun (`FilesystemPlugin.invoke()` and now
  `WorkspaceBootstrapAction._run_substep()`) make a stronger case than
  ADR-0005's one example did for eventually factoring this into something
  the type system enforces — e.g. a `LocalExecutor.execute_relayed()`
  convenience method that does the grant-then-execute pairing atomically,
  so a caller can't accidentally do one without the other. Still not
  built now: two working examples with identical, well-documented logic
  is a stronger signal than one, but it's not yet three, and duplicating
  four lines of clear code twice is a smaller cost than a wrong
  abstraction. Worth building the moment a third Executor-backed
  composite (or a third Plugin adapter) needs the same relay.
- `WorkspaceBootstrapAction`'s own `risk_tier` must stay `>=` the highest
  risk tier of anything it might invoke internally — currently
  `REVERSIBLE_WRITE`, matching both `create_folder` and `write_file`. If
  a future sub-step (e.g. an eventual `delete_file`) is `IRREVERSIBLE`,
  any composite that can reach it must be raised to `IRREVERSIBLE` too,
  or the top-level gate would under-ask for approval relative to what the
  composite can actually do. Noted here as a rule for whoever writes the
  next composite, not enforced by any check today.
