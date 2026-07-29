# Mission Brief 024 — Autonomous Runtime Engine (The Heartbeat)

Status: Shipped — 2026-07-26

## Objective

Transform Kalpavriksha from a founder-driven system into a continuously
running autonomous one. Mission Control is the nervous system; the
Executives are the organs; this is the heartbeat.

This closes the gap MIT-001's certification named in its own closing
caveat: *"Nothing yet drives the loop end to end... a dashboard built now
would be visualizing a system a human is still hand-cranking."*

## Design-first, per Rule 1

`RUNTIME_ENGINE_ARCHITECTURE.md` was written before any code, including
the Scalability Question and the two architectural tensions that had to be
settled before a line was worth writing.

## The two tensions, and how they were resolved

### 1. If nothing may perform work, who invokes the Executive?

Three rules collide: Mission Control never performs work (MB023, enforced
by a test); the Runtime never performs work (Rule 1); the Runtime never
calls Executive APIs directly (Rule 2). Read absolutely, nothing can ever
execute.

Resolved by making the rule precise rather than bending it:

> **"Never performs work" means: contains no work logic, holds no
> Environment access, and has no Executive-specific knowledge.** It does
> not mean "never causes work to happen" — causing work to happen, in the
> right order, with the right accountability, *is* orchestration.

The seam is an `ExecutiveGateway` protocol (`invoke`, `verify`) with zero
Executive knowledge. The Runtime holds gateways keyed by Executive ID and
resolves which to use *from the assignment Mission Control already made*.

The gateway registry lives on the **Runtime**, not Mission Control —
deliberately. Mission Control is mechanically incapable of performing work
today (no plugin imports, descriptors not objects, no execute surface);
handing it an invoking callable would have forced those tests to be
loosened, which is a reliable signal it was the wrong place.

### 2. Retry, versus "strategic recovery belongs to the Brain"

MB023's dispatcher deliberately never auto-retries, citing Constitution
§11. MB024 Deliverable 5 asks for retry. Resolved by a distinction the
Constitution already draws: §4.1 puts *bounded, mechanical* retry with the
Operator; §11 keeps *strategic* recovery — re-planning, substituting a
capability — with the Brain.

So the Runtime retries the same task, same capability, same payload, a
bounded number of times, then **escalates** and stops deciding.
Critically, **Mission Control never sees a retry**: retries happen inside
one cycle, and Mission Control is told `task_failed()` exactly once, after
the final attempt. MB023's guarantee stays literally true, and a test
asserts exactly that.

## What was built

| Deliverable | Implementation |
|---|---|
| 1. Runtime Loop | `runtime/engine.py` — `run_once()`, `run_forever()`, `start_background()` |
| 2. Runtime States | `runtime/states.py` — the eight states + legal-transition table |
| 3. Dispatch Scheduler | `engine._dispatch()` — asks Mission Control across every objective |
| 4. Verification Integration | `engine._verify()` — invokes the Verification subsystem automatically |
| 5. Failure Recovery | `engine._execute_with_retry()` + `_escalate()` |
| 6. Runtime Health | `runtime/health.py` — exactly the brief's seven fields |
| 7. Graceful Shutdown | `engine.stop()` / `_shutdown()` — finishes work, publishes a final snapshot |
| 8. Configuration | `runtime/config.py` — all five named settings, validated at construction |

Plus nine new event types so every cycle is observable (Rule 3).

## Three real bugs the tests caught

None found by inspection; all three by running the thing.

1. **`recovering -> waiting is not allowed`.** My own transition table
   omitted the retry-resume edge, so *every retry crashed its own cycle*.
   Added, with a regression test named after the bug.
2. **`unsupported capability: Filesystem.CreateFolder`.** Mission Control
   speaks qualified names; Executives speak local ones. Nothing was
   translating. Fixed by resolving the local name *through Mission
   Control* (which stores both on the capability descriptor) — never by
   un-mangling the string, which would be lossy, and never by asking the
   Executive, which Rule 2 forbids.
3. **`expected_outcome` was being smuggled through `payload`**, which
   would have leaked a non-JSON object into audit records. Constitution
   §3.2 says a Step should *carry* its Expected Outcome, so it became a
   real `Task` field.

## A real constraint the heartbeat surfaced

**Playwright's sync API is thread-affine**: a browser session must be used
from the thread that created it. Single-threaded MIT-001 could never hit
this; the autonomous Runtime hit it immediately, because it drives work
from its own thread.

The consequence shapes how objectives are written: *every* interaction
with an Environment Session — opening, loading, closing — must happen
inside a task, on whichever thread the Runtime is using. A well-formed
browsing objective therefore opens its session, works, and closes it as
tasks. That is also simply the better way to express it, so the constraint
pushes toward better objectives rather than around a defect.

Deliberately **not** solved with a thread-marshalling layer: that is real
complexity for a capability nothing needs (execution is sequential), and
it would put Environment knowledge inside the Runtime, which Rule 2
forbids. Named in `RUNTIME_ENGINE_ARCHITECTURE.md` §5.1.

## Live verification — unattended, against the real internet

The founder submits an objective, calls `start_background()`, and does
nothing else:

```
FOUNDER: submitting objective, then starting the runtime and walking away
FOUNDER: did nothing else.

--- outcome ---
  open   completed
  nav    completed
  check  completed
  close  completed

runtime state: stopped | cycles: 4 | completed: 4 | failed: 0 | retries: 0
progress: 1.0 | result: {'session_id': 'live', 'closed': True} | evidence: 1

--- event trail ---
   18 runtime_started
   20 dispatch_started      21 task_assigned    23 task_started   24 task_completed
   26 runtime_idle
   28 dispatch_started      29 task_assigned    31 task_started   32 task_completed
   34 runtime_idle
   36 dispatch_started      37 task_assigned    39 task_started
   41 verification_started  42 verification_completed             43 task_completed
   45 runtime_idle
   47 dispatch_started      48 task_assigned    50 task_started   51 task_completed
   52 objective_completed
   54 runtime_idle          56 runtime_stopping 58 runtime_stopped
```

That is the Definition of Done, literally: Start Runtime → Runtime Running
→ Mission Control Dispatching → Browser Executive Working → Verification →
Audit Updated → Waiting For Next Task, with no founder in the cycle.

## Acceptance criteria

| Criterion | Covering test |
|---|---|
| Start successfully | `test_a_cycle_with_no_work_goes_idle_rather_than_erroring` |
| Continuously poll Mission Control | `test_dependency_order_is_honoured_across_cycles_automatically` |
| Dispatch tasks | `test_a_ready_task_is_dispatched_executed_and_reported_without_a_human` |
| Verify results | `test_verification_runs_automatically_inside_the_autonomous_loop` |
| Recover from failures | `test_a_failing_task_is_retried_up_to_the_policy_limit`, `test_exhausted_retries_escalate_exactly_once` |
| Shut down gracefully | `test_stop_transitions_cleanly_and_publishes_a_final_snapshot` |
| No founder interaction once started | `test_definition_of_done_a_founder_starts_the_runtime_and_walks_away` |

## Testing

**82 new tests; 582 passing overall**, zero failures. `ruff check` clean on
every new file.

`tests/test_runtime_architecture.py` enforces Rules 1 and 2 mechanically:
it parses every `runtime/` module's imports and fails on Playwright,
`subprocess`, network libraries, the `LocalExecutor`, or any concrete
plugin — and separately asserts no runtime source file so much as *names*
a specific Executive, so a `if executive_id == "browser"` branch could
never sneak in.

## Out of scope, honored

No Founder Dashboard UI, no Desktop Executive, no Filesystem Executive
enhancements, no Self-Development Engine.

## Technical debt / known limitations

- **Sequential execution.** `max_concurrent_tasks` bounds work-in-flight;
  it does not parallelise. Correct for Founder Edition (Constitution §8.5
  leaves concurrency EVOLVABLE, and the Browser Executive is thread-affine
  anyway), wrong eventually.
- **Fixed-interval polling**, not event-driven. A long interval adds
  latency; a short one wastes cycles. The `EventBus` is already the right
  seam for a wake-up-on-event upgrade.
- **No persistence of its own.** Shutdown publishes a final snapshot into
  the Audit Stream — the durable *shape* this architecture has, but still
  an in-memory list (MB023's named debt). The Runtime deliberately does
  not invent a second mechanism to route around that.
- **Retry has no jitter**, which would matter only if many Executives
  failed in lockstep.
- **`BrowserGateway` lives in `tests/runtime_test_support.py`**, not in
  shipped source. That is correct for Rule 2 — assembling a specific
  Executive into a gateway is founder-wiring — but it means there is no
  shipped, reusable browser gateway yet. Whoever builds the first real
  launcher will want one, and it belongs beside the Browser Executive, not
  inside `runtime/`.

## Recommendation for the next Mission Brief

MB024 was the last thing standing between the backend and a dashboard
worth building. **MB025 — Founder Dashboard** is now genuinely unblocked:
`MissionControl.founder_state().as_dict()` and
`RuntimeEngine.health().as_dict()` are both JSON today, and the Event Bus
gives a UI a live feed to subscribe to rather than a polling loop to
invent.

The one thing worth doing first, if the founder wants the system to
survive a restart rather than merely run unattended, is **persistence for
Mission Control** — currently every objective, audit entry, and runtime
snapshot lives only in memory. A dashboard makes that gap much more
visible, because the first thing anyone does with a dashboard is close it
and come back.
