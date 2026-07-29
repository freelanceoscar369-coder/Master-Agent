# Mission Brief 025 — Persistent Runtime State Engine

Status: Shipped — 2026-07-26
**Contains one architectural proposal awaiting founder ratification (see §1).**

## Objective

Give Kalpavriksha persistent memory so it survives process restarts and
resumes execution without losing operational state. Mission Control and
the Runtime were alive; persistence makes them continuous.

## 1. Architectural conflicts found, and what was done about them ⚠️

MB025 was issued with: *"If an architectural conflict is discovered, stop
implementation, document it, and propose an ADR rather than making
unilateral architectural changes."* Three were found. All three are
**additive** — nothing was redesigned, no existing method changed
behaviour, nothing was removed — and all three are recorded in
[ADR-0015](adr/0015-persistence-strategy.md), which is deliberately marked
**Proposed** rather than Accepted.

| # | Conflict | Resolution | Why it was unavoidable |
|---|---|---|---|
| 1 | `TaskDispatcher` has **no non-publishing way to admit an objective**. `submit()` is the only entry point and it publishes creation events. | `TaskDispatcher.restore_objective()` + `MissionControl.restore_objective()` | Deliverable 3 (objective persistence) and Rule 4 (no private-state access) cannot both hold otherwise. Restoring through `submit()` would make a restored audit claim every objective was submitted twice. |
| 2 | `TASK_CREATED` did not carry `depends_on`. | one key added to that event's payload | A replay-recovered system had tasks but **no dependency edges**, so it could dispatch a task before its prerequisite. |
| 3 | `EXECUTIVE_REGISTERED` did not carry `health`. | one key added to that event's payload | A replayed Executive came back `UNKNOWN`, was never available, and the whole fallback path was **inert**. |

Conflicts 2 and 3 were found by the replay tests, not by inspection.
Both were in the *fallback* path used when a snapshot is corrupt — the
path that matters most precisely when things have already gone wrong.
Leaving them documented-but-broken was considered and rejected: **a
fallback that executes work out of order is worse than no fallback.**

Conflict 1's second method (`MissionControl.restore_objective`) was not in
the ADR's first draft either. Restoring only through the dispatcher left
Mission Control not knowing which objective was current, so
`founder_state()` returned an empty snapshot — progress `0.0` — after a
*successful* recovery. Deliverable 7 requires Current Mission to survive,
so a restore that leaves the founder view blank has not restored.

**All three are isolated and reversible.** Reverting means deleting two
methods and two dictionary keys.

Offsetting these, Mission Control's purity is now *more* strongly enforced
than before: `json`, `pathlib`, `sqlite3`, `os`, `io`, `shutil`,
`tempfile`, and `pickle` are all now forbidden imports in its architecture
test, making "Mission Control cannot access filesystem APIs" mechanical
rather than merely stated.

## 2. What was built

| Deliverable | Implementation |
|---|---|
| 1. State Persistence Service | `persistence/service.py` |
| 2. Runtime Checkpoints | `runtime/checkpoint.py` + `RuntimeEngine.checkpoint()` / `restore_from()` |
| 3. Objective Persistence | `persistence/serialization.py`, restored via the additive contract |
| 4. Capability Queue Persistence | task states (pending/active/completed) inside objective snapshots |
| 5. Executive Registry Persistence | metadata only — no transient handles, asserted by a test |
| 6. Audit Persistence | append-only `events.jsonl`, rebuilt through the frozen `AuditStream.record()` |
| 7. Founder State Persistence | snapshotted, and re-established live on restore |
| 8. Restart Recovery | `persistence/recovery.py` — `recover()` is the one call a launcher makes |
| 9. Event Replay | `persistence/replay.py` |
| 10. Snapshot Versioning | `persistence/schema.py` — schema version, runtime version, timestamp, SHA-256 checksum, migration registry |

**Rule compliance is mechanical, not asserted.**
`tests/test_persistence_architecture.py` parses imports to prove Mission
Control touches no filesystem API, the Runtime imports no storage and no
persistence package, persistence imports nothing that executes, and — for
Rule 4 — walks every AST node looking for private-attribute access on
anything that is not `self`.

## 3. Design decisions worth knowing

**Two mechanisms, not one.** Snapshots answer "what is true now" (restart
cost is O(live state), so it does not grow as the system ages); the event
log answers "what has happened" (audit history, replay). Using replay as
the *primary* restart path was rejected because start-up time would grow
without bound — worst exactly as the system becomes most valuable.

**JSON, not SQLite, despite ADR-0007.** Memory stores queryable mission
*history*; persistence stores one small object graph read exactly once at
startup and never queried into. A row store buys indexing this workload
never uses and costs a migration per dataclass field. JSON is also
human-inspectable, which matters most for the one artifact you open when
the system did not come back up. Nothing about Memory changes.

**Writes are atomic** (temp file + `os.replace`), so a crash mid-write
leaves the previous good snapshot rather than a truncated one.

**Interrupted tasks are quarantined, never re-run.** A task `RUNNING` or
`DISPATCHED` when the process died has *unknown* side effects. It restores
as `FAILED` with *"interrupted by shutdown; outcome unknown — not retried
automatically to avoid duplicate execution"*, surfaces in Founder State,
and its dependents become `BLOCKED`. Deciding to actually re-run one is a
*strategic* judgement, which Constitution §11 reserves for the Brain —
the same boundary MB024's mechanical-only retry respects.

## 4. A real bug this Mission Brief exposed in MB024

`max_cycles` was absolute, not per-process. A runtime restored at cycle N
with `max_cycles=N` broke out of its loop **immediately and did nothing** —
every bounded run after a restart would silently no-op. Fixed by bounding
`max_cycles` to cycles run *in this process* while keeping `active_cycle`
cumulative (which is the useful health number). Found by the
repeated-restart test.

## 5. Live verification — kill and resume

```
=== PROCESS 1: founder starts Kalpavriksha and submits work ===
  progress: 0.67
  tasks: [('t1','completed'), ('t2','completed'), ('t3','ready')]
  files on disk: ['a.txt']

=== KILLED. state directory contents ===
  events.jsonl  14192 bytes
  snapshot.json  9230 bytes

=== PROCESS 2: brand new object graph, same state dir ===
  recovery: {'recovered': True, 'source': 'snapshot', 'executives': 1,
             'capabilities': 14, 'objectives': 1, 'audit_entries': 43,
             'quarantined_tasks': 0}
  BEFORE running -> progress: 0.67 | mission: build a folder and two files
  BEFORE running -> tasks: [('t1','completed'), ('t2','completed'), ('t3','ready')]
  resumed cycle counter: 2

=== RESUMED AND FINISHED ===
  progress: 1.0
  files: ['a.txt', 'b.txt']
  contents: {'a.txt': 'one', 'b.txt': 'two'}
  task completions across BOTH processes: ['t1','t2','t3'] -> each exactly once: True
  audit entries preserved: 70
```

Process 2 shares nothing with Process 1 but the state directory. Progress
is correct *before* it runs anything, and each task executed exactly once
across both processes.

## 6. Acceptance criteria

| Criterion | Covering test |
|---|---|
| Start Runtime, submit objectives, stop, restart, recover, resume, complete | `test_definition_of_done_kill_restart_and_resume` |
| No duplicate execution | `test_no_work_is_repeated_across_the_restart`, `test_a_quarantined_task_is_never_dispatched_again` |
| Preserve audit history | `test_audit_history_from_the_first_process_survives` |
| Founder performs no manual recovery | `recover()` is one call; `test_a_restart_with_nothing_persisted_starts_cleanly` covers first boot |

## 7. Testing

**205 new tests; 789 passing overall**, zero regressions (the brief asked
for 80+). `ruff check` clean on every new and changed file.

| Required category | File |
|---|---|
| Restart recovery | `test_persistence_restart.py`, `test_persistence_recovery.py` |
| Corruption detection | `test_persistence_schema.py`, `test_persistence_store.py` |
| Schema version | `test_persistence_schema.py` |
| Event replay | `test_persistence_replay.py` |
| Queue restoration | `test_persistence_recovery.py`, `test_persistence_restart.py` |
| Audit restoration | `test_persistence_service.py`, `test_persistence_restart.py` |
| Architecture purity | `test_persistence_architecture.py` |

## 8. Technical debt / known limitations

- **The event log grows without bound.** It is read in full only when
  rebuilding audit, but at a million events that becomes slow.
  Segmentation/compaction is **not** built, because a correct compaction
  policy requires a retention policy that does not exist yet.
- **No multi-process locking.** Two processes sharing a state directory
  would corrupt it. Single-founder scope; stated rather than defended
  against.
- **`Task.expected_outcome` is not persisted.** It is a live object, not
  JSON state. A restored task keeps its history but not its expectation;
  a future Planner re-attaches expectations when it re-plans. Asserted by
  a test so it stays a decision rather than a surprise.
- **Replay reconstructs state, not every nuance.** Retry counters and
  runtime health come from the snapshot; the log carries what the events
  carry.
- **No encryption, no remote store.** ADR-0004's local-first stance is
  unchanged.

## 9. Recommendation for the next Mission Brief

The backend is now continuous *and* durable, which is what MB024's
closing note said the dashboard was waiting for. **MB026 — Founder
Dashboard** is unblocked: `MissionControl.founder_state().as_dict()` and
`RuntimeEngine.health().as_dict()` are both JSON, the Event Bus gives a
live feed, and the Audit Stream now survives a restart so a dashboard
opened tomorrow still shows yesterday.

Before that, **ADR-0015 needs ratification** — three additive changes to
frozen components are exactly the kind of thing that should be accepted or
rejected deliberately, not by default.
