# Runtime Engine Architecture — The Heartbeat

Status: Added 2026-07-26 — Mission Brief 024, Autonomous Runtime Engine

Design document required before any of this Miracle's code, per
Constitution Rule 1. Sibling documents: `MISSION_CONTROL_ARCHITECTURE.md`
(the nervous system this drives) and `BROWSER_WORKER_ARCHITECTURE.md` (the
first organ it drives work into).

## 1. What the Runtime Engine is

Mission Control knows *what should happen next*. Executives know *how to
do* one kind of thing. Until now, a human sat between them: MIT-001's own
certification transcript shows a founder pulling `dispatch_ready()`,
invoking the Worker, and reporting back, cycle by cycle.

The Runtime Engine is that human, replaced by a loop. It observes, it
dispatches, it waits, it verifies, it reports, it repeats — and it does
none of the work itself.

## 2. The two tensions this design had to resolve

Both were real, and neither had an obvious answer. Getting them wrong
would have quietly broken guarantees earlier Mission Briefs paid for.

### 2.1 If nothing may perform work, who invokes the Executive?

Three rules collide:

- Mission Control never performs work (MB023, enforced by an
  import-parsing test).
- The Runtime Engine never performs work (MB024 Rule 1).
- The Runtime Engine never directly calls Browser Executive APIs
  (MB024 Rule 2).

Taken as "no component may ever call an Executive," nothing can ever
execute, and the system is a very well-audited paperweight. So the rules
have to mean something more precise, and this design commits to that
reading explicitly:

> **"Never performs work" means: contains no work logic, holds no
> Environment access, and has no Executive-specific knowledge.** It does
> not mean "never causes work to happen" — causing work to happen, in the
> right order, with the right accountability, *is* orchestration.

The seam is an **`ExecutiveGateway`**: a small protocol
(`invoke(capability, payload)`, `verify(...)`) with zero Executive
knowledge. The Runtime holds gateways keyed by Executive ID, and resolves
which one to use *from the assignment Mission Control made* — never by
asking an Executive anything, never by importing one, never by knowing a
browser exists.

**Why the gateway registry lives on the Runtime, not on Mission Control.**
Putting it on Mission Control was the other candidate and was rejected:
Mission Control is *mechanically* incapable of performing work today (no
plugin imports, registries hold descriptors not objects, no
execute/invoke surface — all enforced by tests). Handing it a callable
that invokes plugins would weaken that guarantee and force those tests to
be loosened, which is a strong signal it is the wrong place. The Runtime
is allowed to be the thing that touches both sides, because that is
precisely its job; Mission Control stays pure.

**What Rule 2 therefore forbids, concretely:** the `runtime/` package
must never import `browser_plugin`, `browser_worker`, `browser_session`,
Playwright, the `LocalExecutor`, or any concrete plugin — and
`tests/test_runtime_architecture.py` parses its imports and fails if that
ever changes. The Runtime learns what to run and who runs it exclusively
from Mission Control.

### 2.2 Retry, versus "strategic recovery belongs to the Brain"

MB023's dispatcher deliberately never auto-retries, and says so:
auto-retry would be a strategic recovery decision, which Constitution §11
assigns to the Brain. MB024 Deliverable 5 asks for exactly retry.

The resolution is a distinction the Constitution already makes.
Constitution §4.1 puts *bounded retry and failure-branching policy* in the
Operator ("Retries and failure-branching policy lives here, not in
individual plugins"); §11 keeps *strategic* recovery — deciding to
re-plan, change approach, substitute a different capability — with the
Brain.

So the Runtime does **mechanical** retry only:

- Same task, same capability, same payload, bounded attempt count,
  fixed delay.
- It never alters a payload, never substitutes a capability, never
  re-plans, never reorders an objective.
- When attempts are exhausted it **escalates**: reports the failure to
  Mission Control and emits `TASK_ESCALATED`. It does not decide what
  happens next; that is the Brain's, and no Brain exists yet, so an
  escalated task simply stops and becomes visible in Founder State.

**Mission Control never sees a retry.** Retries happen inside one Runtime
cycle, before anything is reported; Mission Control is told
`task_failed()` only once, after the final attempt. MB023's "the
dispatcher never auto-retries" therefore stays literally true — verified
by a test asserting Mission Control records exactly one `TASK_FAILED` for
a task that was attempted three times.

## 3. Runtime states

The eight states the brief names, with an explicit legal-transition table
in the same style as `Mission` and `WorkerState`:

```
INITIALIZING → IDLE | STOPPING | STOPPED
IDLE         → DISPATCHING | STOPPING          ← the resting state
DISPATCHING  → WAITING | VERIFYING | IDLE | RECOVERING | STOPPING
WAITING      → VERIFYING | RECOVERING | IDLE | STOPPING
VERIFYING    → IDLE | RECOVERING | STOPPING
RECOVERING   → DISPATCHING | IDLE | STOPPING
STOPPING     → STOPPED
STOPPED      → (terminal)
```

`IDLE` is where a healthy Runtime spends most of its life — there is
usually no work ready, and that is not an error condition. `DISPATCHING →
IDLE` exists for the common case of a poll that found nothing.

## 4. One cycle

```
observe    → ask Mission Control what is ready (never ask an Executive)
dispatch   → mission_control.dispatch_ready(); MC assigns an Executive
APPROVE    → consult the ApprovalGate (§4a). Refusal ends the task here
execute    → route each assigned task to its Executive's gateway
             (retry mechanically on failure, up to policy)
verify     → gateway.verify() against the task's ExpectedOutcome,
             producing Evidence
report     → task_started / verification_* / task_completed|failed
idle       → sleep for the poll interval
```

Every step publishes an event, so a cycle that did nothing is as
observable as one that did everything (Rule 3).

**Verification is invoked, never performed, by the Runtime.** The Runtime
asks the gateway to verify and forwards the resulting Verdict and
Evidence ID to Mission Control. It never computes a verdict, never
inspects an Environment, and never lets execution success imply
verification success — a task whose execution succeeded but whose Verdict
is `NOT_MATCHED` is reported to Mission Control as **failed**, because
ADR-0011's whole point is that those are different claims.

## 4a. The approval boundary (MB028.0, ADR-0019)

Added 2026-07-29. This is the only change to `runtime/` since MB024, and
it exists because MB024's design had a hole this document did not name:
**the Runtime reaches Executives directly, so the Orchestrator's
permission check — the Founder approval boundary — was not on this path.**
An `IRREVERSIBLE` `delete_folder` completed with no approval anywhere.

The fix, in one sentence:

> `RuntimeEngine._handle_task()` consults an `ApprovalGate` before it
> touches any gateway, and **refuses to execute anything at all if no gate
> is wired.**

Three properties, each load-bearing:

1. **One funnel.** `_handle_task()` is the only place in `runtime/` that
   reaches a gateway, so it is the only place a boundary is needed — and
   the only place one could be bypassed. A test AST-walks the package and
   fails if a second `gateway.invoke(...)` site ever appears, because a
   second site is an alternate execution path.
2. **The Runtime gains no dependency.** `ApprovalGate` is a protocol
   defined *inside* `runtime/approval.py`, the same move MB025 made with
   `CheckpointSink`. The Runtime knows only "there is a gate, and it may
   refuse." `PermissionSystemGate` — the real adapter — also lives there,
   typed against protocols and importing nothing concrete, exactly as
   `PluginGateway` does.
3. **Fail closed, totally.** No gate ⇒ nothing runs, not even
   `READ_ONLY`. The Runtime cannot know a capability's risk tier (that is
   the gate's job, precisely so the Runtime stays Executive-agnostic), so
   with no gate it cannot evaluate the exception it would be making.
   Forgetting to wire the boundary yields a system that does nothing,
   never one that does everything.

**Three outcomes, not two** (MB028.1). The boundary distinguishes
*authorised*, *pending*, and *refused*:

- **Authorised** — execute.
- **Pending** (`ApprovalPending`) — the founder has been asked and has not
  answered. The task is **held, not failed**: it keeps its state, the
  Runtime remembers it in `_awaiting_approval`, and `_resume_awaiting()`
  re-offers it first on the next cycle, so answering resumes work with no
  restart and no resubmission. Held tasks are invisible to `_dispatch()`
  (Mission Control considers them dispatched), which is exactly why the
  Runtime has to remember them itself.
- **Refused** (`ApprovalDenied`) — rejected or expired. The task fails and
  is **never retried**: retrying a refusal is asking the same question
  repeatedly and hoping for a different answer.

`ApprovalPending` is deliberately not a subclass of `ApprovalDenied`.
Conflating them is how "the founder was asleep" becomes "the mission
failed".

**Evidence outlives the process; authority does not.** Every decision
publishes `APPROVAL_GRANTED` / `APPROVAL_DENIED` carrying capability,
task, `decided_by`, and time — durable in the event log and Audit Stream.
The grant ledger itself stays in memory on purpose: if replay rehydrated
grants, every restart would silently re-arm every approval ever given.
After a restart the audit remembers you approved, and the system still
asks again.

## 5. Concurrency — bounded, and honestly sequential

`max_concurrent_tasks` caps how many tasks the Runtime takes on in one
cycle. Within a cycle they execute **sequentially**.

This is deliberate, not an oversight. Constitution §8.5 leaves concurrent
dispatch across Operator Instances explicitly EVOLVABLE and undesigned,
and the first real Executive (Browser, MB022) is built on Playwright's
sync API, which supports one driver per thread — genuine parallelism would
break it. A cap that bounds work-in-flight without pretending to
parallelise is the honest shape for Founder Edition, and it is the same
knob a future threaded or multi-Operator implementation would keep.

### 5.1 Environment Sessions are thread-affine — a real constraint

Building the autonomous loop surfaced something the single-threaded
MIT-001 certification could not: **a browser Environment Session must be
used from the thread that created it.** Playwright's sync API binds to a
per-thread event loop, so opening a session on one thread and acting on it
from the Runtime's thread raises *"Sync API inside the asyncio loop"*.

Consequences, stated plainly because they shape how objectives are
written:

- Every interaction with an Environment Session — including opening,
  loading content, and closing it — must happen **inside a task**, on
  whichever thread the Runtime is driving. An objective that expects a
  human to reach in and manipulate a live session mid-run is not
  something this architecture supports.
- A well-formed browsing objective therefore opens its session, does its
  work, and closes its session as tasks. That is also simply the right
  way to express it, so the constraint pushes toward better objectives
  rather than around a defect.
- This is a property of the *Executive's* underlying library, not of the
  Runtime. A future Executive with a thread-safe environment has no such
  restriction, and nothing in `runtime/` assumes one way or the other —
  which is exactly why the Runtime holds no session state itself.

Not solved by adding a thread-marshalling layer, deliberately: that would
be real complexity in service of a capability nothing currently needs
(§5's sequential execution means there is one Runtime thread), and it
would put Environment knowledge inside the Runtime, which Rule 2 forbids.
Named here rather than discovered later.

## 6. Configuration

| Setting | Default | Why |
|---|---|---|
| `poll_interval_seconds` | 1.0 | Responsive without spinning a CPU |
| `max_concurrent_tasks` | 1 | Matches §5's honest sequential execution |
| `max_attempts` | 3 | One retry is often luck; three bounds a flapping Executive |
| `retry_delay_seconds` | 0.5 | Fixed, not exponential — a fixed delay is predictable and this is mechanical retry, not congestion control |
| `verify_when_expected_outcome_present` | True | Verification policy: verify whenever the Planner supplied something to check |
| `shutdown_timeout_seconds` | 10.0 | Bounds "finish current work where possible" |
| `max_cycles` | None | Test/one-shot affordance; None means run forever |

## 7. Health

`RuntimeHealth` exposes exactly the brief's seven fields — uptime, active
cycle, queue length, executives online, executives busy, last dispatch,
last verification — all derived by *reading* Mission Control, never by
maintaining a shadow copy that could disagree with it.

## 8. Graceful shutdown

`stop()` requests shutdown; the loop finishes the task it is on (bounded
by `shutdown_timeout_seconds`), transitions `STOPPING → STOPPED`, and
publishes `RUNTIME_STOPPED` carrying the final health snapshot.

**On "persist state," honestly:** that snapshot goes into Mission
Control's immutable Audit Stream, which is the durable *shape* this
architecture has. It is not yet durable *storage* — the Audit Stream is an
in-memory list, already named as debt in MB023 alongside
`LocalExecutor._log`. The Runtime deliberately does not invent a second,
different persistence mechanism to work around that; when Mission Control
gets persistence, the Runtime's shutdown snapshot becomes durable with no
change here. Named rather than quietly satisfied.

## 9. The Scalability Question (Rule 1)

- **Adding Executive #50** costs one gateway registration. The Runtime
  has no per-Executive branching to grow.
- **Adding a new capability** costs nothing here — the Runtime never
  enumerates capabilities; it routes whatever Mission Control assigns.
- **Where this will need revisiting, named now:** the loop is
  single-threaded and sequential (§5); polling is a fixed interval rather
  than event-driven, so a long poll interval adds latency and a short one
  wastes cycles (an event-driven wake-up is the obvious future upgrade,
  and the `EventBus` is already the seam for it); and retry is a fixed
  delay with no jitter, which would matter if many Executives ever failed
  in lockstep.
- **Deliberately not built ahead of need:** no priority scheduling, no
  work stealing, no distributed runtime, no persistence layer of its own,
  no adaptive poll interval.
