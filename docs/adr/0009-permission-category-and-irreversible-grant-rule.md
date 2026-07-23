# ADR-0009: PermissionCategory as a second, orthogonal axis; ALWAYS_FOR_CAPABILITY never satisfies an IRREVERSIBLE check

Status: Accepted (2026-07-23) — Mission Brief 005

## Context

Mission Brief 005 grew `FilesystemPlugin` from three capabilities to
fourteen, adding a genuinely new kind of action alongside the existing
read-only-by-convention `create_folder`/`write_file`/`workspace_bootstrap`:
capabilities that permanently, irreversibly destroy something
(`delete_file`, `delete_folder`). The brief's own words: "destructive
actions MUST require higher permission levels" and "review the existing
Permission System — if necessary, introduce permission categories."

Two separate questions were tangled together in that instruction, and
this ADR treats them as two separate decisions:

1. **How should a human (or a future UI) understand what kind of thing a
   capability does?** `RiskTier` (`read_only` / `reversible_write` /
   `irreversible`) already answers "how much oversight does this need,"
   which is a *mechanism* question — it drives `PermissionSystem.check()`
   directly. It does not answer "is this a read, a write, a modification
   of something that already exists, or a deletion" — a *classification*
   question a future approval UI, audit log, or capability browser would
   want to group by, independent of how cautious the system is about it.
2. **Should destructive actions actually be harder to pre-approve, as a
   real mechanism — not just as a label?** Nothing before this Miracle
   distinguished `IRREVERSIBLE` from `REVERSIBLE_WRITE` in
   `PermissionSystem.check()` beyond the tier value itself; both were
   satisfied identically by any grant scope, including a standing
   `ALWAYS_FOR_CAPABILITY` blanket approval.

## Decision — PermissionCategory as a second, orthogonal axis

Added `PermissionCategory` (`READ` / `WRITE` / `MODIFY` / `DELETE` /
`SYSTEM`) to `plugins/base.py`, alongside `RiskTier` — same module, for
the same reason `RiskTier` lives there and not in
`permissions/permission_system.py`: `permission_system.py` already
imports `RiskTier` from `plugins/base.py` (Actions/capabilities declare
these properties about themselves; `plugins/base.py` is where the
contract being described lives), and `CapabilityManifest` also needs to
reference the new enum — defining it in `permission_system.py` instead
would have created a circular import the moment `plugins/base.py` tried
to import it back. `permission_system.py` re-exports it (`from
master_agent.plugins.base import PermissionCategory  # noqa: F401`) so
permission-related code can import it from either module without
ambiguity about which is canonical.

`PermissionCategory` is deliberately *not* consulted by
`PermissionSystem.check()` at all. It is metadata — every `Action` and
every `CapabilityManifest` carries one, for a human-facing UI or a future
policy hook ("always ask me before any DELETE, regardless of tier") to
read — but the actual gating mechanism stays exactly where it was:
`RiskTier`. This mirrors Memory's Layers 4-6
(`MEMORY_ARCHITECTURE.md`): a real, typed, present-in-the-data-model
concept that nothing consumes yet, added because the shape is right and
cheap now, not implemented further than that because nothing today needs
it to do more. `SYSTEM` specifically has zero Actions using it as of this
Miracle — reserved for a future non-file capability (e.g. "run a shell
command") that doesn't fit READ/WRITE/MODIFY/DELETE's file-oriented
framing.

## Decision — IRREVERSIBLE checks reject ALWAYS_FOR_CAPABILITY grants

This is the part that actually changes behavior. `PermissionSystem.check()`
gained one new rule, expressed as an inner filter function:

```python
def _usable(grant: PermissionGrant) -> bool:
    if risk_tier == RiskTier.IRREVERSIBLE and grant.scope == GrantScope.ALWAYS_FOR_CAPABILITY:
        return False
    return True
```

A grant search that used to be `next(g for g in self._grants if
g.plugin_name == plugin_name and g.capability == capability)` now also
filters through `_usable`. Every other rule is unchanged: `READ_ONLY`
still short-circuits before any grant lookup at all; `ONCE` grants are
still found and atomically consumed; `THIS_SESSION` and
(non-IRREVERSIBLE) `ALWAYS_FOR_CAPABILITY` grants are still reusable
until `revoke_session_grants()`.

### Options considered

1. **Change `grant()`'s signature to refuse creating an
   `ALWAYS_FOR_CAPABILITY` grant for an `IRREVERSIBLE` capability in the
   first place.** Rejected: this needs `grant()` to know the capability's
   risk tier at grant time, which it currently doesn't (grants are keyed
   by plugin name + capability string only) — plumbing risk tier into
   every call site (`cli.py`, `WorkspaceBootstrapAction`'s relay, every
   test that calls `grant()`) is a much bigger, noisier change for the
   same outcome `check()`'s filter achieves with zero call-site changes.
2. **A separate `IrreversibleGrant`/`PermissionSystem` subclass or a
   second grant store just for destructive capabilities.** Rejected as
   needless structural complexity — "prefer simplicity over cleverness."
   One `if` inside the existing lookup does the same job.
3. **Filter inside `check()`'s existing grant lookup, as shown above.**
   Chosen. `grant()` stays exactly as permissive as before (nothing
   currently offers a human the option to create an
   `ALWAYS_FOR_CAPABILITY` grant at all — every live approval flow only
   ever grants `ONCE`), and the enforcement lives at the one place that
   already decides "is this allowed to proceed."

### Why now, ahead of any real incident

Nothing in this codebase today lets a human actually create an
`ALWAYS_FOR_CAPABILITY` grant through conversation — this rule has no way
to be exercised by a real user yet. It's defensive enforcement ahead of
that UI existing, not a reaction to something that went wrong. The
Scalability Question test this Miracle re-applied to its own design
(FILESYSTEM_CAPABILITIES.md §8) is exactly why: the moment a future
"always allow write_file for the rest of this session" UI feature exists,
it must not be able to silently double as "always allow delete_folder"
too, and that has to be true from the day such a UI ships, not retrofitted
after someone is surprised by it.

## Consequences

- Zero changes to `grant()`'s signature, and zero changes to any existing
  call site — `cli.py`'s single `GrantScope.ONCE` relay,
  `WorkspaceBootstrapAction`'s sub-step relay (ADR-0006), and every
  existing test all continue to work unmodified.
- `delete_file`/`delete_folder` (and any future `IRREVERSIBLE`
  capability) require a fresh, real decision — `ONCE` or
  `THIS_SESSION` — every single time no such grant is already present.
  There is currently no path in this codebase to acquire a standing
  blanket approval for a destructive action, by design.
- `PermissionCategory` and `RiskTier` can now diverge in ways a future
  reader must not conflate: `rename_file` is `MODIFY` category but only
  `REVERSIBLE_WRITE` tier (its effect is easily undone by renaming back);
  `delete_file` is `DELETE` category and `IRREVERSIBLE` tier (its effect
  cannot be undone by this system). The category never substitutes for
  the tier in any gating decision — see `FILESYSTEM_CAPABILITIES.md` §5's
  table for the full mapping across all fourteen capabilities.
- `PermissionCategory.SYSTEM` remains genuinely unused — worth revisiting
  the moment a non-filesystem local capability (shell, git, ...) is
  designed, per `ROADMAP.md`.
