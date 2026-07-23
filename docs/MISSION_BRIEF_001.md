# Mission Brief 001 — The First Conversation

Status: Implemented (2026-07-23)

## Objective

Prove the vision, not the architecture: text in, one real mission out,
with a real filesystem write and a real approval gate. Smallest possible
slice that still touches genuine modules end to end — no mocks standing
in for the Permission System or the Orchestrator.

## How to run it

```
cd MasterAgent
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m master_agent.cli
```

Then, at the `>` prompt:

```
> Master Agent
Hello! I'm awake.
What would you like me to do?

> Create a folder called Demo on my Desktop.
I understood your request.

Action:
Create folder "Demo"

Location:
Desktop

This action will modify your filesystem.
Approve? (Yes/No)

> Yes
Done.
Mission completed successfully.
(Created: /Users/you/Desktop/Demo)
```

Run the tests with `pytest` from the project root (23 tests, all against a
sandboxed temp directory — nothing in the test suite touches your real
Desktop).

## What was built

- **`plugins/filesystem_plugin.py`** — the first real (non-model)
  capability plugin. Implements the existing `Plugin` contract exactly:
  a manifest declaring `create_folder` at `REVERSIBLE_WRITE` risk, and an
  `invoke()` that actually creates a directory, idempotently, with real
  error handling (missing name, unknown location, path collision with a
  non-directory). Locations are injected (`{"desktop": Path}`), which is
  the seam that let the entire test suite run against `tmp_path` instead
  of a real filesystem.
- **`cli.py`** — a `MasterAgentSession` class that reproduces the exact
  Mission Brief 001 transcript by wiring together modules that already
  existed in the scaffold: a hand-built one-step `MissionPlan` (stands in
  for the real Planner), the real `Mission` state machine, the real
  `Orchestrator`, and the real `PermissionSystem`. A rule-based
  `parse_intent()` recognizes exactly one sentence shape
  ("create a folder called X [on Y]") — deliberately not a model call.
  `main()` provides an interactive REPL; `MasterAgentSession` itself takes
  no global state, so it's testable without stdin/stdout.

## Two real bugs this slice found and fixed

Building the vertical slice exercised code paths the original scaffold's
unit tests never hit, and surfaced two genuine defects in modules marked
"production-ready" before today:

1. **`PermissionSystem.check()` never consumed `GrantScope.ONCE` grants.**
   A single approval silently authorized every future invocation of that
   capability — the opposite of what "once" is supposed to mean. Fixed:
   `check()` now finds and removes the matching `ONCE` grant atomically
   with the check that uses it.
2. **The Mission state machine skipped `EXECUTING` when no approval was
   needed**, going straight from `PLANNED` to `VERIFYING` — which the
   transition table (correctly) rejects. Fixed: `_run()` now always
   transitions into `EXECUTING` before asking the Orchestrator to run the
   plan, whether or not that execution turns out to need approval.

Both were caught by `test_running_the_same_command_twice_is_idempotent`
and `test_declining_approval_does_not_create_folder` — the kind of test
that only exists because this brief insisted on testing the *complete*
flow, not each module in isolation. Worth remembering next time a module
looks "done" after passing its own unit tests.

## What's production-ready vs. still a stub

**Production-ready** (real logic, real error handling, would survive a
code review as-is):
- `FilesystemPlugin` — the `create_folder` capability specifically.
  Other capabilities (delete, move, list) aren't implemented.
- `PermissionSystem` — the grant/check/consume logic is now correct and
  tested. What's still missing: `THIS_SESSION` scope has no expiry
  mechanism yet (it behaves like `ALWAYS_FOR_CAPABILITY` until
  `revoke_session_grants()` is called manually), and there's no
  persistence — grants don't survive a restart.
- `Orchestrator` — sequential execution, permission gating, and failure
  short-circuiting are real and tested. Dependency-graph scheduling
  (`Step.depends_on`) is still unused — fine for a one-step plan, a gap
  for anything with parallel or branching steps.
- `Mission` state machine — the transition table is enforced and now
  exercised by a real multi-step flow, not just unit tests in isolation.

**Still a stub** (unchanged from the architecture scaffold, intentionally
out of scope for this brief):
- Planner (real model-driven planning), Mission Manager (persistence +
  multi-mission lifecycle), Model Router, ChatGPT/Hermes providers,
  Memory (nothing is persisted across process restarts — `last_mission`
  lives only in the running `MasterAgentSession`), Voice I/O, Desktop UI.
- Intent parsing is a single regex for one sentence shape. It will not
  generalize — that's the Planner/Intent Layer's job, not this brief's.

## Suggestions for the next Mission Brief

1. **Mission Brief 002 — Memory that matters.** Wire `SQLiteMemoryStore`
   for real (it's the most-stubbed module that this slice's own
   `Mission.outcome` data is crying out to be persisted into), and add
   "what did I just do?" — recall the last N missions. This is a small,
   contained slice with an obvious visible payoff, and it's the natural
   next dependency for the Mission Manager.
2. **Mission Brief 003 — A second capability.** Add one more
   `FilesystemPlugin` capability (e.g. `list_files`, read-only, no
   approval needed) specifically to prove the Orchestrator's capability
   resolution works with more than one plugin/capability in the registry
   — this slice only ever exercised the single-plugin, single-capability
   path.
3. **Only after those:** a real Planner call through one model provider
   (Hermes first, since it's local — no API key needed to keep testing
   fast), replacing the hand-built `build_plan()` for exactly the
   create-folder case, so the swap can be verified against this brief's
   existing test suite before intent parsing is generalized further.
