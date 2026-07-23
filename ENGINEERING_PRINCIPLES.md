# Engineering Principles

Status: Frozen (2026-07-23) — Miracle 003.5, Foundation Freeze

These are the permanent rules of how Master Agent gets built — not
aspirations, constraints that have already been load-bearing across
Miracles 001 through 003.1. Every principle below is stated with the
real evidence that produced it: a bug it would have prevented, a design
decision it forced, or a piece of code that already depends on it. A
future contributor — human or AI — should be able to check any change
against this list before writing it, not after.

This document is about **how** we build. `PRODUCT_PRINCIPLES.md` is
about **what** we build and why it should feel a certain way to a user.
`ARCHITECTURE_PRINCIPLES.md` is about **why the system is shaped the way
it is**. All three are permanent; none of them restate the others.

## 1. Never bypass the Executor

`LocalExecutor` (`executor/executor.py`) is the only component allowed
to touch the local machine. Every local capability — filesystem today;
shell, git, VS Code, Obsidian eventually — is an `Action` that runs
through `LocalExecutor.execute()`, never called directly.

This is not a style preference. When `WorkspaceBootstrapAction` needed
to call `CreateFolderAction` and `WriteFileAction` (Miracle 003), the
brief that authorized it was explicit: *do not bypass the Executor*. The
alternative — a composite action calling `run()` on its sub-actions
directly — would have worked, and would have quietly turned off
validation, permission-gating, and logging for every action reachable
only through a composite. `docs/adr/0006-composite-action-relay.md`
exists because the correct-but-harder path was taken instead.

**In practice:** if you're writing code that creates a file, runs a
shell command, or touches git — and it isn't inside an `Action.run()`
called by `LocalExecutor.execute()` — stop. That code belongs in a new
`Action`, not next to the feature that needs it.

## 2. Never bypass the Permission System

No plugin, action, or composite executes anything above `read_only` risk
without a grant from `PermissionSystem`. This has held from Miracle 001
(`create_folder` gated by the Orchestrator's check) through Miracle
003.1 (`workspace_bootstrap`, gated the same way, its internal sub-steps
gated a second time by the Executor).

Two things had to be solved to keep this rule true as the system grew,
and both are permanent techniques now, not one-off fixes:

- **`GrantScope.ONCE` must be consumed atomically.** Miracle 001 found
  and fixed a bug where a `ONCE` grant wasn't consumed on use — one
  approval silently authorized every future call. `PermissionSystem.check()`
  finds and discards the matching grant in the same operation now; this
  is not optional behavior to "simplify later."
- **Two independent checks in one call chain need different grant keys.**
  The Orchestrator gates a Plugin's `invoke()`; the Executor gates an
  Action's `run()`; a composite Action gates its own sub-actions. Each of
  these is a *real* gate, not theater, which means each needs its own key
  — and whichever layer already holds an approval must explicitly relay
  it downward before calling the next layer. This is ADR-0005 (Plugin →
  Executor) and ADR-0006 (Action → its sub-actions), and it will be ADR-N
  again the next time a new layer needs to call through an already-gated
  one. **Do not solve this by removing a check or making a check
  non-consuming** — both were considered and rejected for good reasons
  documented in those ADRs.

**In practice:** if a human approved something once, they should not be
asked again for the same mission — but every layer that could plausibly
be called on its own, bypassing the layers above it, must still refuse
to run unapproved. "Convenient for the common path" and "safe when
bypassed" are both required, not a tradeoff to pick one side of.

## 3. Prefer composition over inheritance

There is no `Action` base class hierarchy beyond the one small ABC
(`executor/action.py`) — six things to implement (`name`, `description`,
`risk_tier`, `expected_result`, `required_parameters()`, `validate()`,
`run()`), no shared mutable state, no template-method framework.
`WorkspaceBootstrapAction` is not a subclass of `CreateFolderAction` — it
holds a reference to the `LocalExecutor` and calls other actions'
`run()`-equivalent (`execute()`) the same way any external caller would.

This kept Miracle 003's design honest: a composite action has to go
through the same gates as everyone else specifically *because* it isn't
a privileged subclass with special access. Inheritance would have made
it easy to skip validation or permission-checking "just this once, since
it's a sibling class." Composition made that impossible to do by
accident.

**In practice:** when a new capability needs to reuse another
capability's behavior, give it a reference to call that behavior through
its public, gated interface — don't extend a class to reach into its
internals.

## 4. Local-first whenever practical

The system must be fully functional offline against a local model and
local storage; cloud providers are an enhancement the Model Router opts
into, never a hard dependency (`docs/adr/0002-hermes-local-llm.md`,
`docs/adr/0004-local-first-memory.md`). Every filesystem action built so
far (`create_folder`, `write_file`, `workspace_bootstrap`) operates on
the local disk with zero network calls, by construction — there was
never a version of these that needed a remote service just to create a
folder.

**In practice:** a new capability that could work against local state or
a cloud API defaults to local unless there's a concrete, named reason
the cloud version is meaningfully better — not "cloud is more modern."

## 5. One approval per mission

A human should never have to say "yes" more than once for a single
thing they asked for — no matter how many primitive operations that
thing decomposes into underneath. `workspace_bootstrap` can run five,
ten, or fifty `create_folder`/`write_file` calls; Miracle 003's tests
assert explicitly that only one `ONCE` grant is ever issued by the
caller for the whole composite (`test_only_one_approval_is_asked_for_the_whole_composite`
and its Miracle 003.1 conversation-level equivalent).

This is in tension with Principle 2 by design, not by accident — every
sub-step is still individually gated, it's just gated by a grant the
outer approval *relayed*, not by a fresh question to the human. Solving
"stay safe" and "stay simple" separately, rather than trading one for
the other, is the actual engineering work here.

**In practice:** if a new composite mission would need to ask the human
more than once, that's a sign the relay pattern (ADR-0005/0006) hasn't
been applied correctly — not a sign the human needs to answer more
questions.

## 6. Every feature requires automated tests

No Miracle has shipped without them, and the practice has already paid
for itself: Miracle 001's two real bugs were found by end-to-end tests,
not by code review of code that "looked done." Miracle 003.1's
`execution_time_seconds` bug was caught by five failing tests on the
very first run, before any user ever saw it.

The standard, observed consistently: new business logic gets direct unit
tests (`test_create_folder_action.py`, `test_write_file_action.py`);
new integration points get end-to-end tests through the real stack, not
mocks (`test_cli_session.py`); and every Miracle's full suite is run and
reported (pass count, not just "tests pass") before the Miracle is
considered done. A regression suite from an earlier Miracle failing is
not an acceptable cost of a new one — see Principle 9.

**In practice:** "I'll add tests later" does not ship. A Miracle isn't
finished until `pytest` and `ruff check .` both come back clean, and
that result is reported, not asserted.

## 7. No duplicated business logic

When `FilesystemPlugin` was refactored from owning `create_folder`'s
logic directly (Miracle 001) to delegating to `CreateFolderAction`
(Miracle 002), the goal explicitly stated in that brief was "no
functionality lost" — meaning the logic moved, it didn't get
re-implemented a second time next to the original. The same discipline
held when `is_unsafe_relative_path()` was needed by three different
actions (Miracle 003): it became one shared function in `action.py`,
not three copies that could drift.

**In practice:** if you're about to write logic that already exists
somewhere else in the codebase — even approximately — stop and either
call the existing implementation or extract a shared one. Two versions
of "how do we decide a path is safe" is a bug waiting for one of them to
fall out of sync with the other.

## 8. Modules communicate only through contracts

The Orchestrator only ever knows a `Step` names a `capability` — it
never knows or cares which `Plugin` will resolve it, and it has not
changed once across four Miracles that added real new behavior
underneath it. A `Plugin` never knows whether the `LocalExecutor` it
calls is running a primitive `Action` or a composite one. `cli.py`'s
`_handle_approval_response()` never knows whether `step.capability` is
`create_folder` or `workspace_bootstrap` — it grants against whatever
capability name is there and moves on.

This is what "everything is a plugin" (ADR-0003) actually buys: modules
stay replaceable because nothing outside a module's own contract can
develop a dependency on its internals. Every ADR in this project's
history exists specifically to protect this property when two
independently-gated layers needed to cooperate (ADR-0005, ADR-0006) —
the fix was never "let the caller reach into the callee," it was always
"add an explicit, narrow interaction at the contract boundary."

**In practice:** if fixing something requires a module to inspect or
depend on another module's internal state (not its public
`invoke()`/`execute()`/`run()` surface), the contract is missing
something — extend the contract, don't route around it.

## 9. User experience is more important than clever architecture

Miracle 003.1 exists because a working capability that's only reachable
through a test file isn't done — "a capability is not complete until a
user can discover and use it naturally" was that brief's closing
principle, and it's permanent, not specific to that one Miracle. The
Permission System's approval prompt is deliberately a single, clear,
voice-summarizable question with an obvious default (`MANIFESTO.md`),
not a technically-correct generic "allow this action?" dialog — the
harder, more specific UX was chosen over the easier, more generic one.

**In practice:** an architecturally elegant capability nobody can reach
from a real conversation is unfinished work, not finished work with a
missing feature. Ship the path from intent to outcome, not just the
mechanism underneath it.

## 10. Simplicity beats complexity

The `Action` contract has six things to implement, on purpose — "keep
this interface small on purpose... the more we put here, the harder it
is to write a new plugin" (`plugins/base.py`'s own docstring, true of
`executor/action.py` too). Real, working technical debt gets flagged in
every Mission Brief's writeup rather than "solved" preemptively: the
relay pattern stayed hand-written in two places (ADR-0005, ADR-0006)
rather than being extracted into a shared base class after only one or
two examples — "one working example doesn't justify the abstraction
yet" is a recurring, deliberate judgment call, not an oversight.

**In practice:** don't build the general version of something until at
least two concrete examples exist to generalize from, and say so
explicitly in the ADR or brief when you're choosing not to generalize
yet — that's a decision worth being able to find later, not a gap to
hide.

## How to use this document

Before writing code for a new Miracle: read this list. If a design
choice conflicts with one of these principles, that's not automatically
disqualifying — but it needs its own ADR explaining why, the same way
ADR-0005 and ADR-0006 explain why the obvious-but-wrong path was
rejected. Silence is not an acceptable way to deviate from a frozen
principle.
