# Mission Control Architecture

Status: Added 2026-07-26 — Mission Brief 023, Mission Control & Self-Development
Infrastructure

Design document required before any of this Miracle's code was written, per
`docs/architecture/KALPAVRIKSHA_VISION_V2.md` Rule 1 ("Design Before Code,
Answering the Scalability Question"). `BROWSER_WORKER_ARCHITECTURE.md` is the
sibling document for Mission Brief 022's Worker; this one covers the
coordination layer that Worker — and every future one — plugs into.

## 1. What Mission Control is, and what it must never become

Mission Control is the **runtime coordination layer**: it registers who can do
what, turns objectives into ordered capability calls, receives every event,
preserves an immutable audit stream, tracks what the system still needs to
learn, and exposes one honest snapshot of system state to the founder.

**Mission Control never performs work.** It holds no Environment access, no
Playwright, no filesystem calls, no model calls. It decides *what should happen
next and in what order*, and records *what actually happened*. Executives
perform work; Capabilities perform actions; Verification confirms reality;
Audit preserves history. This is a hard boundary, mechanically enforced by
`tests/test_mission_control_architecture.py`, not just asserted here.

The practical consequence: `TaskDispatcher` never calls a plugin. It marks
tasks ready and assigns them to an Executive; an *outside* caller (today: a
test or a demo; eventually: the Operator) pulls ready tasks, invokes them
through the Worker machinery Mission Brief 022 already built, and reports the
outcome back. Mission Control is the switchboard, never the hands.

## 2. Terminology: "Executive" and the Constitution's "Worker"

Mission Brief 023 introduces the term **Executive** (Executive Registry,
Executive ID, "Desktop Executive", "Filesystem Executive"). The frozen
Constitution's §17 Terminology Freeze already defines **Worker** for exactly
this role — one registered unit of execution capability — and Mission Brief
022 shipped `BrowserWorker` under that name.

Two live names for one concept is precisely the drift §17 exists to prevent,
so this is resolved rather than left ambiguous: **Executive and Worker name the
same architectural role.** `Worker` remains canonical in the Constitution and
in Worker-side code (`BrowserWorker` is unchanged); `Executive` is the term
Mission Control's registration API uses, because that is the vocabulary this
Mission Brief specified and the founder's brief is the spec. The Constitution's
§17 gains one line recording the alias, and the freeze record is amended in the
same commit, as the Constitution requires of any amendment. Full reasoning and
rejected alternatives: `docs/adr/0014-executive-and-worker-terminology.md`.

An **Executive Instance** registered with Mission Control is therefore the same
thing an Operator Instance would dispatch to — the two registries describe the
same population from different angles, which is why the Executive Registry is
Mission Control's, not a second copy of Shared Infrastructure's Capability
Registry (§4 below).

## 3. Layer map

```
Founder objective
      │
      ▼
 Mission Control ────────────────────────────────────────────┐
   Executive Registry   (who exists, health, current task)    │
   Capability Registry  (what can be done, by whom)           │  emits every
   Task Dispatcher      (order, dependencies, readiness)      │  state change
   Self-Development Q   (what the system still lacks)         │  as an Event
   Knowledge Acq. Q     (how a lack becomes a capability)     │
   Founder State        (one honest snapshot)                 │
      │                                                      ▼
      │                                              Universal Event Bus
      │                                                      │
      ▼                                                      ▼
 ready tasks ──▶ (an outside caller invokes)            Audit Stream
                          │                          (immutable, append-only)
                          ▼
                  Worker / Executive  ──▶ Capability ──▶ Environment
                          │
                          ▼
                    Verification ──▶ Evidence ──▶ back into Mission Control
```

Everything on the Mission Control side of that diagram is new in this Mission
Brief. Everything below "Worker / Executive" already existed as of Mission
Brief 022 and is **not modified** — that is this brief's central acceptance
criterion.

## 4. Why Mission Control's registries do not duplicate Shared Infrastructure

The Constitution (§5.1) places a Capability Registry in Shared Infrastructure —
the lookup both the Brain's Model Router and the Operator's Orchestrator use to
resolve "capability → who provides it." Mission Control has a Capability
Registry too. These are deliberately different things, and conflating them
would be a real architectural error:

| | Shared Infrastructure's registry | Mission Control's registry |
|---|---|---|
| Answers | "which Plugin object services this capability, right now, in this process" | "what capabilities does this system possess, at what version, provided by which Executive, and what is their health" |
| Consumer | Orchestrator / Model Router, at execution time | Dispatcher and Founder State, at coordination time |
| Contains | live plugin object references | descriptors: names, versions, owners, health, dependencies |
| Populated by | `PluginRegistry.register(plugin)` | `register_plugin_as_executive(...)`, which *reads* a plugin's manifest |

Mission Control's registry is a **coordination catalogue**, not an execution
lookup — it holds descriptions, not live objects it could invoke (which it must
not, per §1). The adapter (§9) populates one from the other, which is exactly
why no existing Executive needs modifying.

## 5. The Universal Event Bus — the single communication contract

One `Event` dataclass is the *only* schema any Executive uses to report
anything. No custom logging, no per-Executive event formats. Deliverable #10 is
therefore not a separate component — it is the constraint that `Event` is the
sole reporting shape, enforced by `ExecutiveReporter` (the one helper
Executives use) and by a compliance test asserting no alternative reporting
surface exists.

```
Event(event_id, event_type, occurred_at, source, objective_id, task_id,
      capability, payload, error)
```

`source` is an Executive ID or the literal `"mission_control"`. `payload` is a
plain JSON-shaped dict — never a live object — for the same reason
`Evidence.observation` is (Constitution §9.2): an event must survive being
logged, persisted, or replayed without its consumer needing to know what
produced it.

The ten event types the brief names are implemented exactly, plus the small
number of additional ones the lifecycle genuinely requires (`TASK_DISPATCHED`,
`TASK_BLOCKED`, `EXECUTIVE_REGISTERED`, `EXECUTIVE_HEALTH_CHANGED`,
`WORKER_STATE_CHANGED`, `OBJECTIVE_*`, `KNOWLEDGE_*` pipeline stages) — each
one added because a state transition that isn't observable can't be audited,
which would break "every failure is auditable."

**Delivery is synchronous and in-process.** A message broker would be the wrong
answer for Founder Edition (local-first, single process, no infrastructure to
run) and would make event ordering — which the Audit Stream depends on — harder
to reason about, not easier. The `EventBus` interface is small enough that an
asynchronous or cross-process implementation is a drop-in replacement when a
concrete need exists, not a redesign. A subscriber that raises is isolated:
its failure is captured and re-emitted, never allowed to break the publisher or
starve other subscribers, because a broken dashboard must never take down
execution.

## 6. Worker Lifecycle (deliverable #4)

The brief's nine states, with an explicit legal-transition table in the same
style as `Mission`'s existing state machine (`mission_manager/mission.py`):

```
CREATED → INITIALIZED → READY → RUNNING → {WAITING, COMPLETED, FAILED}
WAITING → {RUNNING, FAILED, STOPPED}
COMPLETED → {READY, STOPPED}          ← see note
FAILED → {RECOVERING, STOPPED}
RECOVERING → {READY, FAILED, STOPPED}
STOPPED → {}                           (terminal)
```

**Why `COMPLETED → READY` exists** even though the brief draws the lifecycle as
a straight line: this is a *Worker* lifecycle, and a Worker that finishes a
task is available for the next one — a browser session that completed a
navigation has not ended its life. Reading the brief's arrow list as literal
one-way transitions would mean one Worker per task forever, which contradicts
Mission Brief 022's own `BrowserSessionManager` (many tasks, one live session).
The brief's list is read as an enumeration of the states, with the transition
table stating the legal edges between them.

Transitions are **mechanical**: `RECOVERING` records that recovery is in
progress, it does not decide a recovery strategy. Strategic recovery is a Brain
responsibility (Constitution §11), and Mission Control must not grow one.

## 7. Task Dispatcher (deliverable #5)

An `Objective` (what the founder wants) decomposes into `Task`s, each naming a
**qualified capability** and an optional `depends_on` list. The dispatcher:

1. Computes which tasks are *ready* (every dependency `COMPLETED`).
2. Resolves each ready task's capability to a registered Executive that
   provides it and is healthy.
3. Marks it `DISPATCHED`, assigns the Executive, emits `TASK_DISPATCHED`.
4. Accepts `task_started` / `task_completed` / `task_failed` reports back, and
   re-computes readiness.

A task whose dependency **failed** becomes `BLOCKED`, never silently skipped
and never auto-retried — auto-retry would be a strategic recovery decision,
which §6 forbids Mission Control from making. Blocked tasks are surfaced in
Founder State so the failure is visible rather than absorbed.

Dependency cycles are rejected at submission time with a clear error, not
discovered as a hang at dispatch time.

**Qualified capability names.** The brief writes capabilities as
`Browser.Navigate`, `Filesystem.Read`. Existing capability names are snake_case
(`navigate`, `read_file`) and plugin names lowercase (`browser`, `filesystem`).
The mapping is one deterministic, tested function — `qualified_name("filesystem",
"read_file") == "Filesystem.ReadFile"` — rather than a hand-maintained lookup
table that would need an entry per capability forever (the same "design for
many, not for three" principle `FILESYSTEM_CAPABILITIES.md` §1 applies to
Actions). The brief's `Filesystem.Read` is illustrative; the deterministic rule
yields `Filesystem.ReadFile` for the capability that actually exists.

## 8. The two queues (deliverables #6, #7)

**Self-Development Queue** holds what the system knows it lacks, typed by the
brief's five categories (`PENDING_CAPABILITY`, `LEARNING_TASK`,
`ARCHITECTURE_IMPROVEMENT`, `RESEARCH_REQUEST`, `IMPLEMENTATION`) with a small
state machine (`PROPOSED → ACCEPTED → IN_PROGRESS → DONE`, plus `REJECTED`).
Mission Control queues and orders these; it never implements them.

**Knowledge Acquisition Queue** implements the brief's seven-stage pipeline:
`NEED → RESEARCH → SOURCE_COLLECTION → COMPARISON → VERIFICATION →
KNOWLEDGE_STORAGE → CAPABILITY_CREATION`, advanced one stage at a time
(skipping stages is rejected, so the pipeline can't be short-circuited).

**The promotion gate is enforced in code, not documented as a convention.**
Constitution ADR-0012 makes Promotion Review human-gated for Founder Edition:
promoting knowledge silently reshapes all future reasoning, which is exactly
the class of consequential action §15 exists to gate. So advancing a request
from `VERIFICATION` into `KNOWLEDGE_STORAGE` requires an explicit
`human_approved=True` argument; without it the advance is refused with a
structured error naming the ADR. Mission Control can therefore drive the entire
pipeline *up to* the gate autonomously and never past it. This is the one place
Mission Control deliberately refuses to be fully automatic.

## 9. Registering existing Executives without modifying them

The brief's hardest acceptance criterion: Mission Control must work "without
requiring modifications to existing Executives." Satisfied by an **adapter**,
not by an interface every Executive must now implement:

`register_plugin_as_executive(mission_control, plugin, ...)` reads a
`Plugin`'s existing `manifest` (name, version, capability list — a contract
stable since Mission Brief 001) and derives everything the Executive Registry
needs. `BrowserPlugin` and `FilesystemPlugin` register unchanged; neither file
is touched by this Mission Brief. A future Desktop/Git/Research Executive that
implements the same long-standing `Plugin` contract registers the same way,
with no Mission Control change either — which is the "every future Executive
can plug in without architectural changes" criterion, demonstrated rather than
promised (`tests/test_mission_control_integration.py`).

Executives that are *not* Plugins (a future remote or out-of-process Executive)
register through the same underlying `register_executive()` call the adapter
uses — the adapter is a convenience over the primitive, never the only door.

## 10. Founder State (deliverable #9) — backend contract only

No UI. One method, `MissionControl.founder_state()`, returns a `FounderState`
snapshot with exactly the brief's ten fields (current objective, mission,
executive, capability, progress, evidence, errors, ETA, waiting approval,
learning progress).

**ETA is honest or absent.** It is estimated from the mean duration of tasks
already completed in the current objective, multiplied by tasks remaining, and
is `None` when fewer than one task has completed. A confidently-wrong ETA is
worse than no ETA — this is the same discipline as Verification refusing to let
execution success imply mission success.

`evidence` carries Evidence *references* produced by Verification (Mission
Brief 022's `Evidence`, reused unchanged — Mission Control does not define a
second evidence type), never re-derived judgments of its own.

## 11. Audit Stream (deliverable #8)

Subscribes to the Event Bus and records **every** event as an immutable
`AuditEntry`. Append-only: no update, no delete, no truncation. Reads return
copies, so a caller cannot mutate history by holding a reference to it.

This does not duplicate `verification/audit.py`'s `AuditLog` (Mission Brief
022), and the distinction matters: that one is a *per-Worker, per-step* record
of Execute→Verify→Audit for one capability call. The Audit Stream is
*system-wide and event-level* — objectives, dispatch decisions, health changes,
queue movements, and Worker step records alike. A Worker's `AuditRecord` can be
ingested into the stream as an event; the stream is not a second copy of it.

Bounding or persisting the stream for a long-running daemon is the same
already-named `ROADMAP.md` item `LocalExecutor._log` carries — explicitly not
solved differently here, so there is one answer to "unbounded in-memory
history" when it's addressed, not three.

## 12. The Scalability Question (Rule 1)

Would this design still be right at a million Missions, hundreds of Executives,
thousands of capabilities, years of history, many Operator Instances?

- **Adding Executive #100** costs one `register_executive()` call — no edit to
  the dispatcher, the bus, or the registries. Capability resolution is a dict
  lookup keyed by qualified name, not a scan.
- **Adding event type #40** costs one enum member. Subscribers filter by type;
  a subscriber that doesn't know a new type simply never fires, rather than
  breaking — so an old dashboard survives a new Executive.
- **Where this design will genuinely need revisiting, named honestly:** the
  Event Bus is synchronous and in-process, the Audit Stream is an unbounded
  in-memory list, and the dispatcher's readiness computation is O(tasks) per
  call rather than incremental. All three are correct for one founder on one
  machine and all three are wrong for a multi-process, multi-year deployment.
  Each is isolated behind a small interface specifically so it can be replaced
  without touching the layers above it — and each is listed in
  `docs/MISSION_BRIEF_023.md`'s Technical Debt section rather than discovered
  later.
- **Where this Mission Brief deliberately did not build ahead of need:** no
  persistence (Memory integration is a separate, later decision — Mission
  Control emits events a persistence layer can subscribe to, which is the
  correct seam), no priority scheduling beyond dependency order, no distributed
  dispatch (Constitution §8.5 explicitly leaves concurrency EVOLVABLE), no
  retry policy (strategic recovery is the Brain's, per §6).
