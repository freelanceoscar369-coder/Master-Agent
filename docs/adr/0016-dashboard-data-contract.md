# ADR-0016: The Dashboard Data Contract — a read model over published surfaces

Status: Accepted (2026-07-26) — Mission Brief 026

## Context

The Founder Dashboard is the first *consumer* component in Kalpavriksha:
every prior Mission Brief added something that decides, executes,
coordinates, or persists. This one only looks.

That makes its dependency direction the whole design problem. A dashboard
that reaches into live objects becomes a second, undocumented client of
every internal detail it touches — and the next change to Mission Control
or the Runtime breaks it, or worse, is *prevented* by it. MB026's rules
anticipate this: read-only, published contracts only, no private access,
no business logic, and tolerate missing data.

MB026 also required that a missing contract stop implementation and raise
an ADR. A full survey was done first
(`FOUNDER_DASHBOARD_ARCHITECTURE.md` §2): **every panel's data is
reachable through existing published surfaces.** No gap was found, so this
ADR records the contract rather than proposing a change to one.

## Decision 1 — A frozen read model sits between contracts and rendering

`sources.py` reads live systems once per refresh and produces a
`DashboardSnapshot`: frozen dataclasses of plain data. `panels.py` renders
*only* from that snapshot.

### Options considered

1. **Panels read live objects directly.** Rejected. It scatters contract
   knowledge across every panel, makes each one require a whole running
   system to test, and leaves nothing preventing a panel from calling a
   mutating method it happens to have access to.
2. **One flat dict of everything.** Rejected: no types, no place to record
   *why* a value is missing, and every consumer re-derives the shape.
3. **A typed, frozen snapshot produced by a single collector layer.**
   Chosen.

The decisive consequence: a panel holds nothing mutable, so "read-only"
becomes a property of the data flow rather than a rule someone has to
remember. And a panel test needs no Runtime, no Mission Control, and no
browser — which is what makes 100+ tests cheap rather than heroic.

## Decision 2 — Absence is a first-class value, distinct from zero

Every read-model field is optional, and the snapshot records *why*
something is missing alongside the fact that it is.

`0` and "unknown" are different facts. A queue length of `0` means nothing
is waiting; an unreadable queue means we do not know. Rendering the second
as `0` would be fabrication — precisely what MB026 Rule 3 forbids, and the
same discipline that makes ETA `None` rather than a guess
(`RUNTIME_ENGINE_ARCHITECTURE.md` §10) and stops execution success
implying verification success (ADR-0011).

Every read in `sources.py` is therefore wrapped so a failure becomes
absent data with a reason, never an exception that blanks the view. A
Dashboard attached to a half-wired system still renders a complete, honest
frame.

## Decision 3 — Health classification is presentation, and is quarantined to prove it

Deliverable 8 asks for Runtime / Queue / Audit / Persistence *health*,
which sits closest to MB026 Rule 4 ("no business logic"). The boundary
this ADR draws:

> The Dashboard **classifies published numbers for display**. It **never
> decides anything.** No classification is read by Mission Control, the
> Runtime, or any Executive; nothing branches on it. Deleting every health
> label would change what a founder sees and nothing about what the system
> does.

Enforced structurally, not by intention:

- All classification lives in `health.py` as **pure functions of plain
  numbers** — no live objects, no I/O.
- Each rule is documented at its function.
- Every panel renders the **raw counts beside the label**, so a founder can
  always check the judgement against the numbers that produced it.

### Rejected alternative

Deriving health inside Mission Control or the Runtime and publishing it.
That would be genuinely cleaner for the Dashboard — but it puts a
*presentation* concern into frozen components, and MB026 explicitly
forbids redesigning them. It would also mean the system computes a
judgement nothing in the system consumes.

## Decision 4 — Live updates are event-driven, with a clock tick

The Dashboard subscribes to `MissionControl.bus` (all event types, not an
enumerated list, so a future Executive's new events still refresh the
view) and additionally re-renders on an interval, because uptime advances
with no event to announce it.

Polling alone was rejected: it would show a task starting up to one
interval late, on a system whose whole point is that it moves without a
human. Events alone were rejected: time-based fields would freeze between
events.

MB023's bus already isolates a failing subscriber, so **a broken dashboard
cannot take down execution** — the property that makes attaching one to a
live system safe.

## Decision 5 — Recovery status is handed in, never discovered

The Dashboard does not call `recover()`. That is the launcher's job;
calling it would be both a mutation and orchestration, violating Rules 1
and 4 at once. The launcher passes the `RecoveryReport` it already holds,
and a Dashboard given none reports recovery status as unavailable rather
than inventing one.

## Consequences

- The Dashboard depends on exactly the surfaces listed in
  `FOUNDER_DASHBOARD_ARCHITECTURE.md` §2. That table is the contract; if a
  frozen component ever changes one of those surfaces, this is the list to
  check.
- No frozen component was modified by MB026. Not one line.
- A future web or desktop front-end consumes the same `DashboardSnapshot`
  and discards `panels.py` — the read model, not the renderer, is the
  reusable asset.
- **Known cost, named rather than hidden:** "Event Log Size" is computed
  from `read_events()`, which returns the entire persisted log. That is
  O(log) per persistence refresh. The right fix is a `count_events()` on
  the `StateStore` contract — a *persistence* change, deliberately not
  made here because MB025's architecture is frozen. Mitigated by
  refreshing persistence data on a slower cadence than runtime data, and
  recorded in `ROADMAP.md`.
