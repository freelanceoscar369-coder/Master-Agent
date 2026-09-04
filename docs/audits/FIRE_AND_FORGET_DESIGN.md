# Fire-and-Forget — Architecture & Feasibility Review

Read-only. No code was changed to produce this document. Every claim below
is either a direct reading of the current source or a live, empirical
observation made earlier in this engagement (the pywebview per-call
threading model was independently proven by a real test: an unrelated
`send_message` call answered promptly while an earlier `_submit_objective`
call was hung — see the Threading Model section for why that is
architecturally guaranteed, not a fluke).

## Current lifecycle

```
Founder Surface (JS)
  -> Bridge.call('send_message', text)                [HTTP POST /js_api/{uid}]
  -> DesktopShellApi.send_message()                    [desktop_shell.py]
  -> CommunicationEngine.handle()  -- returns None (not conversation)
  -> DesktopShellApi._submit_objective(text)            [injected callable]
  -> kalpavriksha_desktop._submit_objective()
       -> mission_service.start(text)                   [BLOCKS ~6-7s: Intent parse + real Gemini call]
       -> while not (objective.is_complete or objective.has_failure) and time < deadline:
              runtime.run_once()                         [BLOCKS: one dispatch cycle]
              time.sleep(0.2)
       -> mission_control.founder_state(objective_id)
       -> return {"reply": <final sentence>}
  -> JS receives the HTTP response, clears "thinking"
```

Everything from `mission_service.start()` to the final `return` executes on
**one HTTP request thread**, and the JS side's `await Bridge.call(...)`
does not resolve until that whole chain returns. This is Task 2's own
design, described honestly in its own docstring: *"Drives the existing
`RuntimeEngine.run_once()` in a bounded loop... so one synchronous
pywebview bridge call can return a real result instead of a background
daemon."* It was built this way on purpose, not by accident.

## Current blocking point

Exactly one loop, in `kalpavriksha_desktop._submit_objective()`:

```python
while _time.monotonic() < deadline and not (objective.is_complete or objective.has_failure):
    runtime.run_once()
    objective = mission_control.dispatcher.objective(objective_id)
    if not (objective.is_complete or objective.has_failure):
        _time.sleep(0.2)
```

Nothing in `MissionService`, `MissionControl`, or `RuntimeEngine` requires
this loop to exist. It is a **caller-side wrapper**, not a property of the
components it drives. Planning (`mission_service.start()`) is a separate,
smaller block (~6-7s, dominated by the real Gemini round-trip) that
happens *before* this loop and is unavoidable regardless of what happens
next — an objective_id cannot exist before a plan does.

## Proposed fire-and-forget lifecycle

```
Founder: "Open Chrome and check example.com."
  -> mission_service.start(text)          [still synchronous, ~6-7s — a plan must exist first]
  -> accepted?
       no  -> return {"reply": "I couldn't plan that: ..."}      (unchanged, today's behavior)
       yes -> return {"reply": "Started — I'm working on it.",   (NEW: acknowledgement, not a result)
                       "objective_id": ..., "status": status.as_dict()}
              -- the bridge call ends here --

Independently, on the runtime's own background thread (already running,
started once at boot, not per-objective):
  RuntimeEngine.run_forever()
    -> polls Mission Control for ready work across every objective it knows
    -> executes, verifies, retries -- exactly today's RuntimeEngine, unchanged
    -> publishes events -> ExecutionStatus updates live
    -> reaches AWAITING_FOUNDER_COMPLETION, exactly as today

Founder Surface polls get_execution_status() (already exists, Task 2.5)
whenever Hyper Agent's Work Region wants a fresh read. No new push
channel, no new bridge method beyond what already ships.
```

The founder's conversational turn now covers only *planning* latency
(~6-7s, itself a candidate for a "thinking" indicator Hyper Agent already
owns), not *planning + execution* (which was the 15-80s the earlier
latency investigation measured).

## Threading model

Verified by reading `desktop_shell.py`'s `FixedBottleServer`, not
inferred:

```python
class ThreadedAdapter(bottle.ServerAdapter):
    def run(self, handler) -> None:
        class ThreadAdapter(ThreadingMixIn, WSGIServer):
            pass
        server = make_server(self.host, self.port, handler, server_class=ThreadAdapter, ...)
        server.serve_forever()
```

Every `window.pywebview.api.*` call from JS is an HTTP POST to
`/js_api/{uid}`, served by a `ThreadingMixIn` WSGI server — **a new OS
thread per bridge call, always, today, unmodified.** This is *why* the
earlier "Hello, are you there?" test answered instantly while a hung
`_submit_objective` call sat blocked on a different thread: they were
never on the same thread to begin with. Fire-and-forget does not change
this model; it exploits a property that already exists.

Three thread populations exist or would exist:

| Thread | Owns | Lifetime |
|---|---|---|
| GUI/message-pump thread | `webview.start()`, WebView2 host | process lifetime |
| Per-bridge-call thread (`ThreadingMixIn`) | one `send_message`/`submit_objective`/`get_execution_status` call | one HTTP request |
| Runtime background thread (`RuntimeEngine.start_background()`) | `run_forever()` — dispatch/execute/verify loop | started once at boot, `daemon=True`, until `stop()` or process exit |

`RuntimeEngine.start_background()` **already exists**, unmodified, today:

```python
def start_background(self) -> None:
    """Run the loop on a background thread. `stop()` joins it."""
    if self._thread is not None:
        raise RuntimeError("runtime is already running")
    self._thread = threading.Thread(target=self.run_forever, daemon=True)
    self._thread.start()
```

It is already used exactly this way elsewhere in this codebase
(`test_browser_live2.py`: `system.runtime.start_background()`, called once
at boot, independent of any single objective). `kalpavriksha_desktop.py`
is the only place that does *not* use it — it drives `run_once()` inline
instead, which is precisely the wrapper this review is asked to remove.

**Concurrency risk, stated plainly.** Nothing in `MissionControl`,
`TaskDispatcher`, `ApprovalQueue`, `CompletionQueue`, or `EventBus` takes a
lock. `EventBus`'s own docstring calls it *"Synchronous, in-process
publish/subscribe... the wrong answer for a single-process, local-first
Founder Edition"* — describing single-threaded *access*, not merely
single-threaded *delivery*. Under fire-and-forget, the background thread
continuously mutates `MissionControl`'s registries while bridge-call
threads read (`get_execution_status`, `founder_state`) and occasionally
write (`confirm_completion`, and — see the one-current-mission section
below — a *new* `submit_objective` once the prior one is terminal).
CPython's GIL makes individual dict/list/attribute operations atomic
enough that this does not corrupt memory or crash, but no compound
operation here is guaranteed atomic across the two threads, and nothing in
this codebase has ever been exercised under real concurrent access to
prove it safe by test. The exposure is bounded, not eliminated, by the
one-current-mission gate below.

## MissionControl responsibilities

Unchanged. It remains the single orchestration authority: it does not
know or care which thread calls `submit_objective()`, `dispatch_ready()`,
or `confirm_completion()`. Nothing proposed here adds a second registry,
a second event bus, or a second decision-maker.

## Runtime responsibilities

Unchanged in code, changed in *invocation*: instead of the founder-surface
driving `run_once()` once per bridge call, `RuntimeEngine.run_forever()`
drives itself continuously on its own background thread, exactly as its
own `start_background()`/`run_forever()` methods already promise. `_dispatch()`
already iterates *every* objective Mission Control knows
(`self._mc.dispatcher.objectives()`) — it was never scoped to a single
in-flight objective; the founder-surface's own "one current mission"
policy is what has made that invisible until now.

## Founder acknowledgement contract

Reusing what already exists rather than inventing a new shape:

```json
{
  "reply": "Started — I'm working on it.",
  "objective_id": "<the real objective_id MissionService.start() returned>",
  "status": { ...ExecutionStatus.as_dict(), "status": "planning" or "executing" ... }
}
```

No new identifier, no new status vocabulary — `objective_id` is
`MissionOutcome.objective_id` (already returned today, just discarded
after the loop), and `status` is `ExecutionStatus.as_dict()` (Task 2.5,
unmodified). The acknowledgement claims exactly one fact: *the objective
was accepted and is now running.* It does not set `status.result`,
`status.message` beyond "started," or anything that could be read as
completion — `ExecutionStatus.terminal_state` stays `False` until the
runtime, then the founder, say otherwise.

## ExecutionStatus relationship

`ExecutionStatus` already updates from live events regardless of who is
polling it — this was true the moment it was built and needs no change to
*keep working* under fire-and-forget. One real gap exists, found by
tracing exactly what happens after the bridge call returns early:

**`status.result` / `status.message` are currently populated only by
`_submit_objective()`'s own post-loop code**, reading `founder_state().result`
*after* the bounded while-loop exits. Under fire-and-forget, that code
never runs — the bridge call returns before the loop would have started.
`ExecutionStatus.record()` itself never sets `result`/`message` from an
`Event` today, because `OBJECTIVE_COMPLETED`'s payload only carries
`{"task_count": ...}` (`dispatcher.py::_publish_objective_terminal_state`)
— the actual result lives on `Task.result`, which no event currently
carries.

Two ways to close this, neither implemented here:

- **(a)** Give `ExecutionStatus` a back-reference to `mission_control` so
  it can call `founder_state()` when a terminal/completion event arrives
  — the smaller diff, but breaks its current "reads only `Event`s"
  purity.
- **(b)** Teach `dispatcher.py::_publish_objective_terminal_state()` to
  include the completed objective's result in `OBJECTIVE_COMPLETED`'s
  payload — additive, backward-compatible (existing subscribers ignore
  the new key), keeps `ExecutionStatus` event-only, but is a genuine
  (small) touch to Mission Control's dispatcher.

This is the one piece of "smallest architectural exception" this review
found — see Decision.

## Approval behavior

Unaffected in shape, changed only in *when the founder learns about it*.
Today: the founder-surface's inline loop calls `run_once()`, which raises
`ApprovalPending` internally and returns control to the loop — the
founder never sees this mid-call, they just wait longer (up to
`timeout_seconds`) and eventually get "taking longer than expected."
Under fire-and-forget: the same `ApprovalPending`/`FounderApprovalGate`
path runs on the background thread; `APPROVAL_REQUIRED`/`APPROVAL_REQUESTED`
(already wired into `ExecutionStatus` as `AWAITING_APPROVAL`) surface
*immediately* and asynchronously instead of being invisible until a
timeout. This is a strict improvement, using zero new permission
infrastructure — the existing `mission_control.approve()`/`reject()` calls
work unchanged; the next `run_once()` cycle on the background thread picks
the decision up exactly as it does today.

## Failure behavior

| Failure | Where it happens today | Founder-facing signal under fire-and-forget |
|---|---|---|
| Planning refused (`no plan: ...`) | `mission_service.start()`, before acceptance | **Immediate synchronous refusal** — unchanged, still inside the one still-blocking call |
| Plan structurally rejected (`PlanIncomplete`) | same | **Immediate synchronous refusal** — unchanged |
| Permission/approval required | `RuntimeEngine._require_approval` | **Asynchronous** — `ExecutionStatus.status == AWAITING_APPROVAL`, existing approval action resumes it |
| Execution failure (attempts exhausted) | `RuntimeEngine._escalate` / task `FAILED` | **Asynchronous** — `OBJECTIVE_FAILED` -> `ExecutionStatus.status == FAILED` |
| Mission blocked | dependency/`TASK_BLOCKED` | **Asynchronous** — `ExecutionStatus.status == BLOCKED` |
| Verification fails | `RuntimeEngine._verify` | **Asynchronous** — surfaces as the task's own `FAILED`, same as execution failure (existing semantics: "a verification failure fails the task, and nothing repairs it") |
| Founder completion required | all tasks complete, no failure | **Asynchronous** — existing Task 2.5 flow, `AWAITING_FOUNDER_COMPLETION`, unchanged |

Nothing here is a new decision; every row reuses an existing event/state
this session already wired.

## Conversation-during-mission behavior

Already true today, proven live in this engagement, not a fire-and-forget
side effect: `desktop_shell.send_message()` routes through
`CommunicationEngine.handle()` **first**, and only falls through to
`_submit_objective` when that returns `None`. Plain conversation never
touches `MissionControl`/`RuntimeEngine` at all, and — per the Threading
Model section — runs on its own per-call thread regardless of what any
other bridge call or the background runtime thread is doing. Fire-and-forget
does not newly enable this; it removes the one place (a single very long
bridge call) where the *founder's own turn* felt blocked even though the
rest of the app never was.

## Restart/crash behavior

**Mission state is lost.** `kalpavriksha_desktop._build_mission_pipeline()`
wires `RuntimeEngine(mission_control, approval_gate=...)` with no
`checkpoint_sink`/persistence of any kind — Founder Edition's composition
root deliberately excludes `master_agent.launcher`'s Persistence layer
(*"Dashboard, Persistence, Recovery and Filesystem, none of which this
surface needs"* — the module's own docstring). Every `Task`, `Objective`,
`PendingApproval`, `PendingCompletion`, and `ExecutionStatus` field lives
in process memory only. If Kalpavriksha.exe closes or crashes — whether a
mission is mid-execution in the foreground (today) or on a background
thread (proposed) — everything in flight is gone; there is nothing to
resume into. This is true **today**, before any change proposed here;
fire-and-forget does not make it worse, but it also does not make it
better, and must not be presented as durable background execution.

## One-current-mission constraint

Preserved, and enforced at exactly the layer this review scopes changes
to: the founder-surface composition root, not Mission Control or Runtime.
`RuntimeEngine._dispatch()` is not itself single-objective — nothing stops
it from servicing two objectives Mission Control happens to hold. The
constraint is a **founder-surface policy**: `_submit_objective()` should
check `status.terminal_state` (or equivalent) before calling
`mission_service.start()` again, and refuse a second objective with a
plain sentence ("a mission is already running") while one is in flight —
the same shape as every other refusal path already in this function. This
is what keeps the concurrency risk in the Threading Model section bounded:
under this gate, `mission_control.submit_objective()` never races against
a *different* objective's own execution, only against read-only status
polls of the *same* one.

## Security implications

None new. No new permission infrastructure, no new grant authority, no
change to `PermissionSystemGate`/`FounderApprovalGate`. The approval
boundary continues to be the only place execution stops for a decision —
fire-and-forget changes when the founder is *told* about that stop, never
whether it happens.

## Smallest implementation surface

1. `kalpavriksha_desktop.py`
   - `_build_mission_pipeline()`: call `runtime.start_background()` once, after construction.
   - `_submit_objective()`: remove the bounded `while`/`run_once()`/`sleep` loop; after `outcome.accepted`, return an acknowledgement (objective_id + `status.as_dict()`) instead of waiting.
   - `_submit_objective()`: add the one-current-mission gate (check `status.terminal_state` before accepting a new objective).
   - Optional: wire `runtime.stop()` into `window.events.closing` for a clean shutdown (not required for correctness — the thread is a daemon and dies with the process; only affects whether the *last* in-progress cycle finishes cleanly).
2. `src/master_agent/missions/execution_status.py` and/or `src/master_agent/mission_control/dispatcher.py`
   - Close the `result`/`message` gap described above — pick option (a) or (b).
3. `src/master_agent/founder_edition/desktop_shell.py`
   - None required — `submit_objective`'s injected-callable shape and `get_execution_status`/`confirm_completion` already exist from Task 2.5 and need no change to their signatures.

No other file needs to change. Hyper Agent's Work Region already consumes
`ExecutionStatus`; nothing about its contract's *shape* changes, only how
soon `status.status` starts moving relative to when the bridge call
returns.

## Frozen components that must remain untouched

`Planner`, `GeminiProvider`, `AI Capability Broker`, `RuntimeEngine`'s own
internals (`_run_cycle`, `_dispatch`, `_handle_task`, retry/approval
logic), `PermissionSystemGate`/`FounderApprovalGate`, `ApprovalQueue`,
`CompletionQueue`'s decision semantics, Hyper Agent, tree.js/app.js/CSS.
All confirmed above to need zero changes — the entire proposal lives in
one composition-root file plus a small, additive extension to how a
result reaches `ExecutionStatus`.

## Risks

- **Unlocked concurrent access to MissionControl's registries** (see
  Threading Model) — bounded but not proven safe by any existing test;
  the one-current-mission gate reduces this to "many readers, one
  writer-at-a-time on shared mutable state with no lock," which is a real
  residual risk, not a theoretical one.
- **`ExecutionStatus.result` gap** — without closing it, fire-and-forget
  ships a status contract that can reach `COMPLETED` with `result: null`,
  silently regressing what Hyper Agent can show today.
- **No durability** — a crash or close mid-mission loses everything,
  identically to today; the UX must not imply otherwise once missions can
  outlive a single visible "turn."
- **Founder-surface-only enforcement of one-current-mission** — if that
  gate is ever bypassed or forgotten in a future change, nothing in
  Mission Control itself would stop a second concurrent objective; the
  safety property lives in one `if` statement in one file, not in the
  architecture.
- **Daemon thread + no `stop()` wiring** — acceptable given no durability
  exists anyway, but worth a conscious decision rather than an omission.

---

# DECISION

**B — READY WITH SMALL ARCHITECTURAL EXCEPTION**

The blocking-wrapper removal itself (`start_background()` + returning
early from `_submit_objective()`) is fully supported by existing,
unmodified architecture — that part alone would be **A**. What pushes
this to **B** is the `ExecutionStatus.result` gap: delivering a real
"verified result" to Hyper Agent asynchronously requires either a new
back-reference from `ExecutionStatus` into `MissionControl`, or a small,
additive extension to `dispatcher.py`'s `OBJECTIVE_COMPLETED` payload —
one explicitly-scoped, small touch to a piece of Mission Control that this
review was otherwise told to treat as untouched. Everything else in the
requested lifecycle (acceptance, execution, retries, approval,
verification, `AWAITING_FOUNDER_COMPLETION`, `COMPLETED` only after
confirmation, ordinary conversation staying responsive, the
one-current-mission constraint) is achievable with the composition-root
change alone.
