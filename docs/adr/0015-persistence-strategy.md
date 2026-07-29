# ADR-0015: Persistence strategy — snapshots plus an event log, and one additive restore contract

Status: **Accepted** (ratified 2026-07-26 by Mission Brief 026, which lists
ADR-0015 among the frozen architecture) — proposed by Mission Brief 025

> This ADR shipped as *Proposed* because MB025 was issued with: "If an
> architectural conflict is discovered, stop implementation, document it,
> and propose an ADR rather than making unilateral architectural
> changes." Three conflicts were found, all additive and reversible.
> MB026's frozen-architecture list names ADR-0015 as Accepted, which
> ratifies them; the three changes (a non-publishing `restore_objective()`
> on `TaskDispatcher`/`MissionControl`, plus `depends_on` on
> `TASK_CREATED` and `health` on `EXECUTIVE_REGISTERED` payloads) are now
> part of the frozen architecture and may not be redesigned without a new
> ADR.

## Context

Mission Control (MB023) and the Runtime Engine (MB024) hold every piece of
operational state in memory. The system runs unattended but does not
survive a restart: objectives, audit history, registries, and runtime
counters all vanish when the process exits.

MB025 requires that state to persist and resume, under four rules:
persistence never executes missions; Mission Control never writes files;
the Runtime never performs storage operations; and no component reaches
into another's private state.

## Decision 1 — Two mechanisms: snapshots for state, an event log for history

A snapshot answers "what is true now"; the event log answers "what has
happened". Restart uses the snapshot (O(live state), so restart time does
not grow as the system ages); audit history and Deliverable 9's replay
capability use the log.

### Options considered

1. **Event log only, rebuilding all state by replay.** Rejected as the
   *primary* path: restart cost grows without bound with history, so a
   system that had run for a year would take proportionally longer to
   start than one that had run for a day — a property that gets worse
   exactly as the system becomes more valuable. Replay is still built and
   tested (`replay_events_into()`), as a repair path and to satisfy
   Deliverable 9.
2. **Snapshots only.** Rejected: Deliverable 6 requires audit history —
   including original timestamps and evidence IDs — to survive restart,
   and a periodic snapshot inherently loses whatever happened between
   snapshots.
3. **Both, each for what it is good at.** Chosen.

## Decision 2 — JSON files, not SQLite, despite ADR-0007

ADR-0007 chose stdlib `sqlite3` for Memory. This is a different concern
and unifying them would be the error.

Memory stores **mission history**: queryable, indexed, filtered by status
and recency, read repeatedly by a future Planner. Persistence stores
**operational state**: one small object graph, written on checkpoint,
read exactly once at startup, never queried into. A row store's indexing
and partial reads buy nothing here, and cost a schema migration each time
a dataclass gains a field.

JSON is also human-inspectable, which matters disproportionately for the
one artifact you reach for when the system did not come back up.

Writes are atomic (temp file + `os.replace`), so a crash mid-write leaves
the previous good snapshot rather than a truncated one — the failure mode
that would make persistence worse than none.

Nothing about Memory changes; both remain.

## Decision 3 — An additive restore contract on Mission Control ⚠️

**This is the conflict.** Deliverable 3 requires objective persistence.
Rule 4 forbids reaching into private state. The frozen `TaskDispatcher`
offers no way to satisfy both:

- `submit()` is the only entry point, and it publishes
  `OBJECTIVE_SUBMITTED` + `TASK_CREATED`. Restoring through it would
  republish creation events for work submitted hours earlier, so the
  restored audit would claim every objective was submitted twice.
- Writing `TaskDispatcher._objectives` directly is exactly what Rule 4
  forbids.

Every other component already has a clean path:
`ExecutiveRegistry.register()` and `CapabilityRegistry.register()` are
public and publish nothing; `AuditStream.record()` copies `event_id` and
`occurred_at` off the Event, so audit rebuilds **byte-faithfully with
zero changes**.

### Options considered

1. **Reach into `_objectives`.** Rejected — direct violation of Rule 4,
   and of `ENGINEERING_PRINCIPLES.md` #8 ("extend the contract, don't
   route around it").
2. **Restore via `submit()` and accept duplicate creation events.**
   Rejected — it corrupts the audit's meaning. An audit that says
   something happened twice when it happened once is worse than an audit
   that is merely incomplete.
3. **Add a "replay mode" flag to the EventBus that suppresses
   publication.** Rejected — a global mute is a much larger and more
   dangerous change to a frozen component than a single additive method,
   and a bus that can be silenced is a bus whose audit guarantees are
   conditional.
4. **Keep restored history outside Mission Control**, exposing it only via
   the persistence service. Rejected — `mc.audit` would silently not
   contain history after a restart, which is precisely the surprise
   Deliverable 6 exists to prevent.
5. **An additive, public, non-publishing restore path.** Chosen.

### What was actually added

Two methods forming one coherent contract:

- `TaskDispatcher.restore_objective(objective)` — the mechanism.
  Validates and recomputes readiness exactly as `submit()` does; the only
  difference is silence.
- `MissionControl.restore_objective(objective)` — the facade entry point
  persistence actually calls. Delegates to the dispatcher, and
  additionally re-establishes `_current_objective_id` when unset.

**The second one was not in this ADR's first draft, and the reason it
exists is worth recording.** Restoring only through the dispatcher left
Mission Control not knowing which objective was current, so
`founder_state()` returned an *empty* snapshot — progress `0.0` — after a
successful recovery. Deliverable 7 requires Current Mission to survive a
restart, so a restore that leaves the founder view blank has not actually
restored. Found by running a real kill-and-resume cycle, not by
inspection.

### Why this is an extension, not a redesign

No existing method changes. No behaviour changes for any existing caller.
Nothing is removed. The dispatcher's guarantees — validation, readiness
recomputation, never auto-retrying — are untouched.

Reverting costs deleting two methods and their call sites.

## Decision 3b — Two additive event-payload fields ⚠️

Implementation surfaced two further gaps, both in the **event replay**
fallback path, and both genuinely unsafe to leave alone:

1. **`TASK_CREATED` did not carry `depends_on`.** A system rebuilt by
   replay therefore had the right tasks with *no dependency edges*, so it
   could dispatch a task before its prerequisite. In the exact scenario
   replay exists for — a corrupt snapshot — recovery would have silently
   executed work out of order.
2. **`EXECUTIVE_REGISTERED` did not carry `health`.** A replayed
   Executive came back `UNKNOWN`, was never considered available, and the
   whole fallback path was inert: it would recover state and then refuse
   to run anything.

Both are fixed by adding one key to an existing event payload.

**Why this is not an interface redesign.** `Event.payload` is already
`dict[str, Any]`; the Event schema, the bus, and every consumer are
unchanged, and a consumer that ignores the new key behaves exactly as
before. This is *recording data that was already true* rather than
altering a contract.

**Why not the alternative.** Documenting "replay cannot recover
dependencies or health" and moving on was considered and rejected: it
would leave a recovery path that can execute out of order, which is worse
than not having the path at all. A fallback that is unsafe is not a
fallback.

Found by MB025's replay tests, not by inspection.

## Decision 4 — Interrupted tasks are quarantined, never re-run

A task `RUNNING` or `DISPATCHED` at the moment of death has **unknown**
side effects. Re-running risks duplicate execution, which MB025
explicitly forbids. So such tasks restore as `FAILED` with
*"interrupted by shutdown; outcome unknown — not retried automatically to
avoid duplicate execution"*, surfacing in Founder State with dependents
correctly `BLOCKED`.

Deciding whether to actually re-run one is a *strategic* judgement, which
Constitution §11 reserves for the Brain — the same boundary MB024's
mechanical-only retry respects. Tasks that were `READY`/`CREATED`/
`BLOCKED` had not started and resume normally, satisfying "resume
unfinished work".

## Consequences

- Kalpavriksha survives restarts: objectives, registries, audit,
  runtime counters, and founder state all return.
- **Mission Control gains one method it did not have.** That is the whole
  architectural cost, and it requires ratification.
- Mission Control's purity is now *more* strongly enforced than before:
  MB025 adds `json`, `pathlib`, `sqlite3`, `os`, and `io` to its
  forbidden-import test, making "Mission Control cannot access filesystem
  APIs" mechanical rather than stated.
- The Runtime is unchanged in its dependencies: `CheckpointSink` is a
  Protocol defined **inside `runtime/`**, so MB024's architecture test —
  `runtime/` imports only `mission_control` and itself — passes
  untouched.
- **The event log grows without bound.** Segmentation/compaction is not
  built, because a correct compaction policy requires a retention policy
  that does not exist yet. Named as debt.
- **No multi-process locking.** Two processes sharing a state directory
  would corrupt it. Stated rather than defended against, consistent with
  single-founder Founder Edition scope.
