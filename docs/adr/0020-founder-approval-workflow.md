# ADR-0020: The Founder Approval Workflow — the Dashboard shows, the Console decides

Status: **Accepted, shipped — the frozen-component changes it requires are
PROPOSED and await ratification** (2026-07-29) — Mission Brief 028.1

Extends ADR-0019 (the approval boundary). Preserves ADR-0016 (the
Dashboard read model) intact. Design: `docs/MISSION_BRIEF_028_1.md`.

## Context

MB028.0 made Kalpavriksha safe: the Runtime consults an `ApprovalGate`
before any gateway, and refuses to execute what the founder has not
approved. It did not make it *usable*. There was no way to say yes. An
irreversible task failed, the founder saw a failed task, and the only
route to approval was a command-line flag granting a capability *before*
the system ever asked for it — which is approval in the wrong direction:
authorising a class of action in advance rather than deciding a specific
one on its merits.

Three things had to change, and each one touches something already
decided.

## Decision 1 — Pending is a third outcome, not a kind of refusal

MB028.0 had two answers: authorised, or denied-and-the-task-fails.
MB028.1 adds a third:

| Permission System says | MB028.0 | MB028.1 |
|---|---|---|
| granted | execute | execute |
| not granted | **fail the task** | **ask the founder; the task waits** |
| founder rejected / expired | — | fail the task, never retried |

`ApprovalPending` is deliberately **not** a subclass of `ApprovalDenied`.
Conflating them is how "the founder was asleep" becomes "the mission
failed" — and MB028.1's Deliverables 6 and 7 are precisely the demand
that those two be distinguishable.

The consequence that had to be built: a held task is *dispatched* as far
as Mission Control is concerned, so it never comes back through
`_dispatch()`. Without somewhere to remember it, answering an approval
would resolve the question and the work would still never run. The
Runtime keeps `_awaiting_approval` and re-offers those tasks first each
cycle. That state is loop state, not coordination state — Mission Control
already knows the task is assigned — so it stays in the Runtime.

**Found by a failing test, not by inspection.** The first implementation
approved correctly, published correctly, and left the task at
`DISPATCHED` forever.

## Decision 2 — The Approval Queue lives in Mission Control

### Options considered

1. **In the Permission System.** Rejected. That component is the ledger of
   *granted authority*; a queue of unanswered questions is a different
   thing with a different lifetime, and merging them would mean a pending
   request looked like a partial grant.
2. **In `runtime/`, beside the gate.** Rejected. The queue is read by the
   Dashboard and written by the founder; putting it in the Runtime gives
   two more components a reason to depend on the Runtime, and the Runtime
   is not a place other things should read from.
3. **A new Shared Infrastructure component.** Rejected as premature: it
   would be a fourth §5 entry for something that fits an existing shape.
4. **A third queue in Mission Control.** Chosen. Mission Control already
   owns two human-gated queues (Self-Development, Knowledge Acquisition),
   already publishes `APPROVAL_REQUIRED`, and `FounderState` already has
   a `waiting_approval` field that was, until now, only ever populated by
   knowledge promotions. This is the shape the coordination layer was
   already built around.

**It is not a second permission system.** The queue holds questions; the
Permission System holds authority. Approving here issues a `ONCE` grant
there, and the boundary stays singular — ADR-0019 unweakened, which
MB028.1's Architecture Rules require explicitly.

## Decision 3 — The Dashboard shows the queue; the Console decides. ADR-0016 is untouched.

This is the decision that mattered most, because MB028.1 reads like a
demand to make the Dashboard interactive, and ADR-0016 makes read-only a
*structural* property: panels receive a frozen snapshot and return
strings, so a panel physically cannot mutate what it observes.

> **The Approval panel renders `[A]pprove N` and has no way to act on
> it.** `FounderConsole`, in the launcher, reads the keystroke and calls
> Mission Control's published contract.

So the split is:

```
dashboard/    renders the queue from a frozen snapshot   (pure, unchanged)
launcher/console.py   reads keys, calls MissionControl.approve()   (composition root)
```

Every ADR-0016 guarantee survives: no panel holds a live object, panels
remain testable without a Runtime, and a broken renderer still cannot
affect execution. What changed is that something *else* in the same
terminal can act — which was always allowed, because the launcher is the
composition root and is permitted to know every layer.

### Rejected alternative

Giving `FounderDashboard` a Mission Control reference and command
methods. It is the obvious implementation and it would quietly undo the
one property ADR-0016 spent its whole length establishing. A Dashboard
that can approve is a Dashboard that can do anything.

## Decision 4 — One writer to the terminal

A background render thread plus a blocking `input()` fight over stdout:
the frame redraws over whatever is half-typed. So there is exactly one
writer — the console loop — which polls for keystrokes between frames and
echoes the command line as part of the frame it draws.

That is also why the panel's hints are single letters. `A`/`R`/`D` are
what a poll-driven console can offer without taking on a TUI dependency,
and MB028.1's own mock-up shows exactly that.

The reader is chosen by **asking the stream, not guessing the platform**
(`sys.stdin.isatty()`), so `kalpavriksha | tee log.txt` renders and never
blocks on a keypress that can never arrive — the same discipline MB026
used for charset selection, for the same reason.

## Decision 5 — Defer is not a decision; expiry is

- **Defer** changes only how the request is presented — moved below the
  pending ones, out of the founder's immediate way. The task stays
  blocked, the request stays open, and it survives a restart. Nothing is
  written to the ledger, because nothing was decided.
- **Expire** *is* a decision, made by the system rather than the founder,
  and it fails the task. It writes to the ledger with `decided_by:
  "system"`, because a ledger that recorded only human decisions would
  leave an unexplained failure.

**Timeout defaults to disabled.** A request that vanishes overnight is
worse than one still on the screen in the morning, and "safe" here means
*not executing*, which waiting already achieves. Expiry is evaluated when
the boundary is consulted rather than on a timer — the Runtime already
re-checks every cycle while a task waits, so a separate clock would be a
second thing to keep honest.

## Decision 6 — Restoring a queue restores questions and evidence, never authority

ADR-0019's rule, extended to a component that now persists:

- A restored **deferred** or **pending** entry is an unanswered question
  and comes back exactly as it was (Deliverable 5).
- A restored **approved** entry is a *record* that the founder said yes.
  It grants nothing. The grant it produced lived in the Permission
  System, which is deliberately not persisted, so the same work
  resubmitted after a restart is asked about again.

Demonstrated live, and asserted by
`test_restart_restores_evidence_but_not_authority`.

## Frozen components changed — PROPOSED

| File | Change |
|---|---|
| `mission_control/approvals.py` | **New** — `ApprovalQueue`, `PendingApproval`, `ApprovalRecord` |
| `mission_control/mission_control.py` | `approvals` attribute; `request_approval`/`approve`/`reject`/`defer`/`expire_approvals`; `waiting_approval` now includes capability approvals |
| `mission_control/events.py` | Three additive event types: `APPROVAL_REQUESTED`, `APPROVAL_DEFERRED`, `APPROVAL_EXPIRED` |
| `runtime/approval.py` | `ApprovalPending`; `FounderApprovalGate` wrapping (never replacing) `PermissionSystemGate`; `payload` on `ApprovalRequest` |
| `runtime/engine.py` | Branch on pending vs denied; `_awaiting_approval` and `_resume_awaiting` |
| `persistence/service.py` | One snapshot key (`approvals`) and its restore |
| `dashboard/*` | New `ApprovalPanelData`/`ApprovalRow`, one collector, one pure renderer — additive, no existing panel changed |

Following MB025's precedent, the work **shipped with the ADR marked
Proposed** rather than stopping: MB028.1 lists "updated ADR (if needed)"
as a deliverable rather than a gate, and the brief's Definition of Done
is a working founder workflow. Every change above is additive and
isolated — reverting them removes the workflow and restores MB028.0's
behaviour exactly, touching nothing else.

`tests/test_dashboard_architecture.py`'s ratified-exceptions list names
each path against the ADR permitting it, so an unpermitted change still
fails.

## Consequences

- **`kalpavriksha` is now a system a founder operates**, not a set of
  subsystems that happen to work. That was the Definition of Done.
- **The `--approve` flag is gone.** Approving a capability class in
  advance is the wrong shape: a founder should decide a specific request,
  seeing its impact, at the moment it is asked.
- **One executive still serialises approvals.** A task held at the
  boundary keeps its Executive assigned, so with a single Filesystem
  Executive, pending requests arrive one at a time in practice even
  though the queue supports many. Named, not hidden; it resolves itself
  when a second Executive exists.
- **`estimate_impact` lives in the launcher**, because interpreting a
  payload means knowing what a payload means — Executive knowledge the
  Runtime must not have. It is best-effort and reports `unknown` rather
  than guessing, because a founder approves *against* that number.
