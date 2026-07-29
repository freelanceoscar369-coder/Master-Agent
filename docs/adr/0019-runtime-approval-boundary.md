# ADR-0019: The Runtime Approval Boundary — one gate, at the only funnel, failing closed

Status: **ACCEPTED — ratified by the founder 2026-07-29, implemented in
Mission Brief 028.0**

Proposed first, per MB028.0's own rules (*stop, produce ADR, explain why,
wait for ratification*), with no frozen file modified. Ratified, then
implemented exactly as specified below.

Extends ADR-0005 (executor/plugin permission relay) and ADR-0009
(IRREVERSIBLE grant rule). Full trace and diagrams:
`docs/MISSION_BRIEF_028_0.md`.

## Context — the defect, stated exactly

Kalpavriksha has **two** permission checks and **two** execution paths.
The checks are on one path. The Runtime is on the other.

| Gate | Location | Key checked | Purpose |
|---|---|---|---|
| **A — the Founder boundary** | `orchestrator/orchestrator.py:42` | `(plugin_name, capability, risk_tier)` | The real approval decision. Raises `ApprovalRequired`. |
| **B — the relay target** | `executor/executor.py:104` | `(executor_name, action_name, risk_tier)` | Not an independent boundary. It exists so gate A's decision can be carried down (ADR-0005). |

`plugins/filesystem_plugin.py:170` grants gate B's key **unconditionally**,
immediately before calling it:

```python
self._executor.permissions.grant(self._executor.name, capability, GrantScope.ONCE)
result = self._executor.execute(capability, payload)
```

On the Orchestrator path that is correct and is exactly what ADR-0005
describes: gate A already ran, so the plugin relays an approval it really
holds.

On the Runtime path, `runtime/engine.py:320` calls
`gateway.invoke(...)` → `PluginGateway.invoke` → `plugin.invoke(...)`
**directly**. The Orchestrator is never involved. So gate A never runs,
and gate B is pre-satisfied by a relay carrying a decision that was never
made.

**Net gates on the Runtime path: zero.** Verified by running it, not by
reading: an `IRREVERSIBLE` `delete_folder` completes and the directory is
gone, with no approval anywhere
(`tests/test_launcher.py::test_the_runtime_path_is_ungated`).

This contradicts **Constitution Rule 5**: *"The Permission System is
consulted before any step above `READ_ONLY`, regardless of which Operator
Instance executes it."*

**No single component is at fault, and that matters for the fix.** ADR-0005's
relay is correct given an outer approval. MB024's `ExecutiveGateway` is
correct given something gates it. MB023's dispatcher never claimed to
gate. The defect is that MB024 introduced a *second* execution path and
did not carry the boundary onto it — and nothing in the architecture
forced it to, because the boundary lived in a component (the Orchestrator)
that the new path simply does not use.

## Decision 1 — The boundary is an `ApprovalGate` the Runtime consults at its single funnel

`runtime/approval.py` defines a protocol **inside `runtime/`**:

```
class ApprovalGate(Protocol):
    def check(self, request: ApprovalRequest) -> None: ...   # raises ApprovalDenied

ApprovalRequest(executive_id, qualified_capability, local_capability,
                task_id, objective_id)
```

`RuntimeEngine._handle_task()` calls it once, before any gateway is
touched. That method is the **only** funnel: both gateway call sites
(`_execute_with_retry` → `invoke`, and `_verify`) descend from it, and
every task of every objective for every Executive passes through it.

This is the same move MB025 made for `CheckpointSink`: the protocol is
defined inside `runtime/`, so the Runtime acquires **no dependency on the
Permission System module** and stays Executive-agnostic and
infrastructure-agnostic. The composition root supplies a real
implementation that delegates to Shared Infrastructure's Permission System
(§5.2) — the single grant ledger, unchanged and un-duplicated.

### Options considered

1. **Check inside `PluginGateway`.** Rejected. It is *one* implementation
   of `ExecutiveGateway`; a Browser gateway, a Terminal gateway, and every
   future one would each need their own copy, and a new gateway that
   omitted it would silently reopen the hole. That is duplicated truth,
   which MB028.0 Deliverable 2 forbids outright.
2. **Route Runtime execution through the `Orchestrator`.** Rejected. The
   Orchestrator walks a `MissionPlan` of `Step`s; the Runtime holds Mission
   Control `Task`s. Adapting one to the other creates a translation layer
   that can drift, and it would undo MB024's deliberate decision to give
   the Runtime its own `ExecutiveGateway` abstraction (which is what keeps
   Mission Control mechanically incapable of executing). Fixing a boundary
   by merging two execution models is a bigger change with a larger blast
   radius than the defect.
3. **Wrap gateways in the launcher.** Rejected, and this is the important
   rejection. It would work, and it requires no frozen change — but any
   caller can register an unwrapped gateway, so the guarantee would rest
   on the launcher remembering. MB028.0's Definition of Done rejects
   exactly this: *"enforced by architecture — not convention, not
   documentation, and not developer discipline."*
4. **Remove the self-grant from every plugin.** Rejected. It restores
   gate B to independence but breaks the Orchestrator path (ADR-0005's
   relay is what makes gate A's decision reach the Executor), and it puts
   the boundary in every plugin — N copies of the truth, drifting as
   plugins are added.
5. **One `ApprovalGate`, consulted by the Runtime at `_handle_task`.**
   Chosen.

## Decision 2 — It fails closed

A `RuntimeEngine` constructed without an `ApprovalGate` **refuses every
capability above `READ_ONLY`.** Not a warning, not a log line — the task
fails with `approval gate not configured`, and the refusal is published.

This is what converts the guarantee from architectural *intent* into an
architectural *fact*. Forgetting to wire the gate produces a system that
does nothing, rather than a system that does everything. MB027.5's
`--enable-execution` opt-in existed only because this property did not,
and was removed on implementation — a safety flag that outlives its
hazard teaches founders to ignore flags.

**Implementation note — stricter than proposed, deliberately.** This ADR
proposed refusing everything *above `READ_ONLY`* when no gate is wired.
That is not implementable as written: the Runtime cannot know a
capability's risk tier (resolving it is the gate's job, precisely so the
Runtime stays ignorant of Executives, MB024 Rule 2), so with no gate it
cannot evaluate the exception it would be making. **A gateless Runtime
therefore refuses everything**, and the `READ_ONLY` exemption lives in the
gate, where the tier is known. Stricter than proposed, never weaker, and
the only version that is actually fail-closed rather than fail-closed-if-
we-can-work-out-what-to-close.

## Decision 3 — Approval evidence is history; a grant is a live capability. Replay restores only the first.

Deliverables 8 and 9 pull in opposite directions, and the resolution is
the whole of both:

- **Deliverable 8** — after a restart, the audit must still prove approval
  existed, who approved, when, and for which capability.
- **Deliverable 9** — replaying history must never re-execute irreversible
  work, and must never re-authorise it either.

> **A replayed `APPROVAL_GRANTED` event restores the *record* that an
> approval happened. It must never restore a usable grant.**

If replay rehydrated grants, then every restart would silently re-arm
every approval a founder had ever given — an approval ledger that grows
monotonically and never expires, reconstructed from history the founder
cannot see. The correct posture after a restart is: *the audit remembers
that you approved; the system still asks again.*

This is ADR-0009's discipline extended. A `ONCE` grant is consumed on use;
an `ALWAYS_FOR_CAPABILITY` grant can never satisfy an `IRREVERSIBLE`
check. Both say the same thing — **destructive authority does not
accumulate.** Replay-restores-evidence-not-grants is the restart-shaped
version of that rule.

Replay does not invoke gateways today (`persistence/replay.py` reconstructs
Mission Control state only), so Deliverable 9's *execution* half is already
true. It is currently true by construction and untested; the ratified work
adds the test that pins it.

## Decision 4 — Approval is recorded as an event, so evidence outlives the process

The Permission System's grant ledger is in-memory and deliberately not
persisted (see Decision 3 — persisting it would be re-arming). So the
evidence has to live where durable history already lives: the event log
and the Audit Stream.

`EventType.APPROVAL_GRANTED` and `EventType.APPROVAL_DENIED` are added
alongside the existing `APPROVAL_REQUIRED`, carrying
`{capability, risk_tier, executive_id, task_id, decided_by, decided_at,
scope}`.

`decided_by` is a required field, not an optional one. "Approval existed"
is a weaker claim than "the founder approved," and Deliverable 8 asks for
the second.

## Frozen components this requires changing

| File | Change | Why unavoidable |
|---|---|---|
| `runtime/approval.py` | **New file** — `ApprovalGate` protocol, `ApprovalRequest` | New file in a frozen package; the protocol must live inside `runtime/` so the Runtime gains no Permission System dependency (MB025's `CheckpointSink` precedent) |
| `runtime/engine.py` | `__init__` gains `approval_gate=None`; `_handle_task` consults it before dispatching; refusal path publishes and fails the task | This is the only funnel. Anywhere else is either duplicated (per-gateway) or optional (launcher) |
| `mission_control/events.py` | Two additive enum members: `APPROVAL_GRANTED`, `APPROVAL_DENIED` | Evidence must be durable, and the event log is the only durable history. Additive only — no existing member changes |
| `tests/test_dashboard_architecture.py` | The MB026 `git diff` freeze test gains an allowance for these two paths, naming this ADR | **This is the guard working as designed.** It must be amended explicitly, with a reason, rather than deleted or quietly narrowed |

Nothing else. `plugins/`, `executor/`, `persistence/`, `verification/`,
and the Orchestrator path are untouched: ADR-0005's relay keeps working
exactly as it does today, because gate A now genuinely runs on both paths
before the relay happens.

## What ratification unblocks, and what it does not

Ratifying this ADR permits MB028.0 Deliverables 3–9 to be implemented and
tested. It does **not** deliver an approval *interface* — there is still
no way for a founder to say yes to a pending request. That is deliberately
out of scope here, and it lands in **non-frozen** code (the launcher), so
it needs no further ratification:

- With the gate in and no interface, the honest behaviour is that
  irreversible tasks *stop* and are escalated with `APPROVAL_REQUIRED`
  published, which is a strictly safer system than today.
- The minimal interface is a launcher flag (`kalpavriksha --approve
  <capability>`) plus the Dashboard's existing `waiting_approval` panel
  field, which already exists and is already rendered.
- The real interface is a founder decision about UX, and belongs in its
  own brief.

## As implemented (2026-07-29)

Three source changes, exactly the three this ADR named, plus the test
amendment it named:

| File | What landed |
|---|---|
| `runtime/approval.py` | **New.** `ApprovalRequest`, `ApprovalDenied`, the `ApprovalGate` protocol, and `PermissionSystemGate` — the real adapter, typed against `Any` so `runtime/` still imports nothing concrete, exactly as `PluginGateway` is |
| `runtime/engine.py` | `approval_gate=None` on `__init__`; `_require_approval()` and `_refuse()`; the check placed in `_handle_task()` before `_execute_with_retry` |
| `mission_control/events.py` | `APPROVAL_GRANTED`, `APPROVAL_DENIED` — additive |
| `tests/test_dashboard_architecture.py` | The MB026 freeze guard became a **ratified-exceptions list**: each permitted path names the ADR permitting it, so a change without one still fails |

Two things came out differently from the proposal, both recorded rather
than absorbed:

1. **Fail-closed is total, not "above READ_ONLY"** — see Decision 2's
   implementation note. Stricter than proposed.
2. **The evidence reporter ships in `runtime/approval.py`, not the
   launcher.** The first draft duplicated the event-publishing lambda in
   `launcher/boot.py`, which meant the boundary tests exercised a
   different reporter than a founder would. `PermissionSystemGate.
   publishing_reporter()` / `.report_to(bus, decided_by)` is now the one
   implementation, used by both.

**Live verification** (Deliverables 6–9, sandboxed, real filesystem):

```
D6: irreversible task, NO approval
  task state      : failed
  error           : approval denied: founder approval required
  folder survives : True
D7: founder approves, same task repeats
  task state      : completed
  folder deleted  : True
  APPROVAL_GRANTED: who=onkar  what=Filesystem.DeleteFolder  when=2026-07-29T17:13:12Z
D8/D9: restart -- replay history into a fresh Mission Control
  evidence survived : 1 APPROVAL_GRANTED event, who/what/when intact
  replay executed?  : folder still present = True
  authority re-armed? task state = failed, folder = True
```

1015 passing, 1 skipped, zero regressions (993 before).

## Consequences

- **Constitution Rule 5 becomes mechanically true** rather than true on
  one of two paths. This is the point.
- **The Definition of Done becomes provable.** "Nothing irreversible can
  happen unless I approved it" rests on: one gate, at the only funnel,
  failing closed, with a test that no other execution path exists.
- **MB027.5's `--enable-execution` opt-in becomes unnecessary** and should
  be removed in the same brief — a safety flag that outlives the hazard
  teaches founders to ignore flags.
- **Every existing test must still pass.** The Orchestrator path is
  unchanged; the Runtime path gains a gate that tests currently exercising
  it must now satisfy. Expect test-support wiring
  (`tests/dashboard_test_support.py`, MB024/MB025 runtime tests) to need
  an explicit approving gate — that churn is not incidental, it is the
  fix being visible.
- **Named honestly:** a gate the Runtime consults is a component the
  Runtime can be constructed without. Fail-closed is what makes that safe,
  and the test that proves it must construct a Runtime *without* a gate
  and assert refusal — otherwise the default nobody chooses is the one
  nobody checks.
