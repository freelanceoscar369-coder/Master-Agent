# Founder Dashboard Architecture

Status: Added 2026-07-26 — Mission Brief 026, Founder Dashboard (Founder Edition v1)

Design document required before any code, per Constitution Rule 1.
Siblings: `MISSION_CONTROL_ARCHITECTURE.md`, `RUNTIME_ENGINE_ARCHITECTURE.md`,
`PERSISTENCE_ARCHITECTURE.md` — the three systems this one observes and
never touches.

## 1. What the Dashboard is

The first operational window into a living autonomous system. It reads
published contracts and renders them. That is the whole of it.

**It is read-only.** It never dispatches, never executes a capability,
never mutates Runtime or Mission Control state, and never writes a file.
`tests/test_dashboard_architecture.py` enforces this mechanically — the
same posture MB023, MB024, and MB025 each took for their own boundaries,
because prose drifts and a failing test does not.

## 2. Contract survey — every panel, before any code

MB026 says: *"If any required data is unavailable through existing
contracts, stop implementation and raise an ADR rather than bypassing
architectural boundaries."* So the first thing built was the survey, not
the UI. **Every panel is reachable. No contract gap was found, and no
blocking ADR is required.**

| Panel | Field | Published source |
|---|---|---|
| Runtime Status | State, Uptime, Active Cycle, Queue Length, Last Dispatch, Last Verification | `RuntimeEngine.health()` → `RuntimeHealth` (all six are existing fields) |
| Current Mission | Objective, Progress, Active Executive, Active Capability, ETA | `MissionControl.founder_state()` → `FounderState` |
| Current Mission | Mission Status | `Objective.is_complete` / `.has_failure` — public properties, via `MissionControl.dispatcher.objectives()` |
| Executive | Name, Health, Version, Status, Capability Count | `MissionControl.executives.all()` → `ExecutiveRecord.as_dict()` |
| Capability | Registered | `MissionControl.capabilities.all()` |
| Capability | Pending / Active / Completed | `Task.state` across `dispatcher.objectives()` |
| Audit | Recent events | `MissionControl.audit.entries` (returns copies) |
| Persistence | Snapshot Version | `PersistenceService.load()` → `SnapshotEnvelope.schema_version` |
| Persistence | Last Checkpoint | `PersistenceService.load_checkpoint()` → `RuntimeCheckpoint.captured_at` |
| Persistence | Event Log Size | `PersistenceService.store.read_events()` |
| Persistence | Recovery Status | `RecoveryReport` handed in by the launcher that ran `recover()` |
| System Health | Executives Online | `RuntimeHealth.executives_online` |
| Founder State | everything | `FounderState.as_dict()`, rendered verbatim |
| Live updates | — | `MissionControl.bus.subscribe()` |

`executives`, `capabilities`, `dispatcher`, `audit`, and `bus` are public
attributes of `MissionControl` (no leading underscore, set in `__init__`),
so reading them is contract use, not private access.

**Recovery Status is passed in, not discovered.** The Dashboard does not
call `recover()` — that is the launcher's job, and calling it would be
both a mutation and orchestration. The launcher hands over the
`RecoveryReport` it already has. A Dashboard given none simply reports
recovery status as unavailable, per §4.

## 3. Read model, then render — why there are two layers

```
published contracts ──▶ sources.py ──▶ DashboardSnapshot ──▶ panels.py ──▶ frame
   (live objects)        (tolerant     (plain, frozen        (pure         (string)
                          reads)        dataclasses)          functions)
```

Panels never touch a live object. They receive a `DashboardSnapshot` of
plain data and return strings. Two consequences that matter:

- **Rendering is trivially testable.** A panel test builds a snapshot and
  asserts on text — no Runtime, no Mission Control, no browser.
- **A panel physically cannot mutate anything**, because it has nothing
  mutable to reach. Read-only stops being a discipline and becomes a
  property of the data flow.

`sources.py` is the only layer that touches live systems, and every read
there is wrapped so that a failure becomes *absent data*, never an
exception that takes down the view (§4).

## 4. Missing data (Rule 3): show status, never fabricate

Every field in the read model is optional. When something cannot be read,
the snapshot records `None` **plus a reason**, and the panel renders an
explicit marker rather than a plausible-looking zero.

The distinction that matters: **`0` and "unknown" are different facts.** A
queue length of `0` means nothing is waiting; an unreadable queue means we
do not know. Rendering the second as `0` would be fabrication — the same
discipline that makes ETA `None` rather than a guess
(`RUNTIME_ENGINE_ARCHITECTURE.md`) and makes Verification refuse to let
execution success imply mission success (ADR-0011).

Concretely: a Dashboard wired to no Runtime, no persistence, and a Mission
Control with nothing in it still renders a complete, honest frame.

## 5. "Health" indicators are presentation, not business logic (Rule 4)

Deliverable 8 asks for Runtime / Queue / Audit / Persistence *health*.
This is the one place the brief's Rule 4 ("the Dashboard contains no
business logic") needs a precise reading, so it is stated rather than
assumed:

- The Dashboard **classifies published numbers for display** — e.g. "queue
  has 2 blocked tasks" → show a warning colour/label.
- The Dashboard **never decides anything**. No classification feeds back
  into Mission Control, the Runtime, or an Executive. Nothing branches on
  it. Removing every health label would change what a founder *sees* and
  nothing about what the system *does*.

To keep that boundary visible rather than trusted, health classification
lives in one module (`health.py`) as **pure functions over plain
numbers**, each with an explicitly documented rule, and every panel shows
the underlying raw counts next to the label. A founder can always check
the label against the numbers that produced it.

## 6. Live updates (Deliverable 10) — event-driven, with a clock tick

Two triggers, because there are two kinds of change:

1. **Event-driven.** The Dashboard subscribes to `MissionControl.bus` and
   marks itself dirty on every event. This is why a task starting appears
   immediately rather than up to a poll-interval later.
2. **Clock tick.** Uptime advances with no event to announce it, so the
   loop also re-renders on an interval.

Subscribing to *all* events (rather than an enumerated list) is deliberate:
a future Executive emitting event types this build has never heard of
still refreshes the view. And per MB023's bus contract, a subscriber that
raises is isolated — **a broken dashboard cannot take down execution**,
which is exactly the property that makes it safe to attach one to a
running system.

## 7. Rendering: stdlib only, no new dependency

Plain ANSI text, composed with the standard library. Rejected
alternatives and why:

- **A web UI (FastAPI + browser).** Rejected for v1: it introduces a
  server, a port, a second process, and a build step, for a founder who is
  already looking at a terminal. `ARCHITECTURE.md` §4.10 keeps this open
  as the eventual path; nothing here forecloses it, because everything
  above `panels.py` is data, not pixels.
- **A TUI library (`rich`, `textual`).** Rejected for v1: a new runtime
  dependency for box-drawing this can do in fifty lines, on a project
  that has kept its dependency list deliberately short.

`render_frame(snapshot) -> str` is the whole rendering contract. A future
web or desktop front-end consumes the same `DashboardSnapshot` and ignores
`panels.py` entirely.

## 8. The Scalability Question (Rule 1)

- **Adding a panel** costs one render function plus one read-model
  dataclass. No existing panel changes.
- **A new Executive or capability** needs no Dashboard change at all — the
  Executive and Capability panels iterate whatever is registered.
- **A new event type** needs no change: the audit panel renders
  `event_type` as published, and the live subscription is type-agnostic.
- **Where this will need revisiting, named now:** `read_events()` returns
  the *entire* persisted log to compute "Event Log Size", so that read is
  O(log) on every persistence refresh. At a million events this is the
  first thing that will hurt. Mitigated for now by refreshing persistence
  data on a slower cadence than runtime data, and named in
  `docs/MISSION_BRIEF_026.md` — the real fix is a `count_events()` on the
  `StateStore` contract, which is a persistence change and therefore
  **deliberately not made here** (MB025's architecture is frozen).
- **Also named:** the audit panel holds only the last N entries in the
  snapshot, so scrollback is bounded by that window rather than the full
  history. Full history remains available through the audit contract for
  anything that needs it.
- **Deliberately not built:** no filtering, no search, no time-travel, no
  export, no mission submission (explicitly out of scope — this dashboard
  is observational only).
