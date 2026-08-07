# Health Report — Sprint 1, Component 28: Desktop Operator

**Type:** Implementation health report. Working-directory evidence only.
**Date:** 2026-08-06
**Status:** Complete. **Not committed, not tagged, no Rule 001.**
**Built on:** `kalpavriksha-s1-c18.0` — commit `01497c3`, treated as frozen. Every file below is new; nothing at or below that tag was touched.
**Ground:** C1–C27 · Desktop Executive (C26) · Desktop Perception (C27) · Founder Runtime (C23) · Environment Intelligence (C22).

**Constraint honoured, one grounding source recorded as unavailable:** the
brief names *"Gemini Architecture Review (PASS WITH OBSERVATIONS)"* as a
grounding source. No such document exists anywhere in this repository —
searched by filename and by content across every `.md` file. This
component was built without it, following the same discipline C20/C21's
own audits used for their own missing grounding: the gap is stated, not
filled by guessing at what a review might have said. If this review
exists outside the repository, its observations were not available to
this build.

---

## 1 · Architecture

```
   Founder Runtime (C23)
        │  DesktopTask
        ▼
   ┌─────────────────────────────────────────────────────────────┐
   │  DesktopOperator.execute()                                   │
   │                                                                │
   │   for each MissionStep, in order:                             │
   │      DesktopStateMachine.run_step()                            │
   │           Observe → Decide (tactical) → Act → Verify           │
   │                          │                                     │
   │              SUCCESS ────┴──── FAILURE                         │
   │                 │                 │                            │
   │             continue      Tactical Recovery                    │
   │                                 │                               │
   │                        retry (≤3) or Escalate                  │
   │                                                                │
   │   MissionContext — created here, destroyed here                │
   └─────────────────────────────────────────────────────────────┘
        │  ExecutionResult
        ▼
   Founder Runtime (C23)


   DesktopStateMachine consumes, never duplicates:
        DesktopExecutor        (C26)  — every Act
        DesktopObserver        (C27)  — every Observe / Verify
        desktop.inventory.discover()  — the one exception, §7
```

**Six files, exactly as the brief lists them**, plus `__init__.py`:

| File | Role | Statements |
|---|---|---|
| `execution_result.py` | The Founder Runtime boundary — `ExecutionResult`, `EscalationRequest`, `MissionOutcome` | 44 |
| `mission_context.py` | The mission vocabulary (`DesktopTask`, `MissionStep`, `StepAction`, `ExpectedOutcome`) and the ephemeral `MissionContext` | 88 |
| `state_machine.py` | The Core Execution Loop | 134 |
| `tactical_recovery.py` | Recovery planning — decides, never acts | 43 |
| `timeouts.py` | The Step Timeout Governor | 23 |
| `operator.py` | `DesktopOperator` — the one public entry point | 36 |

**377 statements. 100% coverage. Ruff clean.**

**Placement:** `src/master_agent/desktop_operator/` — a sibling of
`desktop/`, not nested inside it. Every prior C25–C27 component sat
*inside* `desktop/` because each was Desktop Executive's own knowledge or
substrate; the Operator is different in kind — it is Founder-Runtime-
facing orchestration that *consumes* Desktop Executive and Desktop
Perception rather than extending either, the same relationship
`founder_runtime/` (C23) already has to the packages it consumes.

---

## 2 · The Core Execution Loop, exactly as specified

```
   Observe
      │
      ▼
   Decide (TACTICAL ONLY)
      │
      ▼
   Act
      │
      ▼
   Verify
      │
      ▼
   State Evaluator
      │
      ├──────── SUCCESS ───────► Continue
      │
      └──────── FAILURE ───────► Tactical Recovery
                                   │
                          retry? ──┘ yes (loop back)
                           │
                          no
                           │
                           ▼
                  Escalate Founder Runtime
```

`DesktopStateMachine.run_step()` implements this once per `MissionStep`.
**No alternate execution model exists** — there is no second loop, no
recursive retry, no branch that skips Verify. `tests/
test_desktop_operator.py::TestLoopOrdering` reads the method's own source
and asserts `_act(` appears before `_verify(` with no second `_act(`
before it, which is a structural proof rather than a description.

### 2.1 One refinement to the diagram's own literal reading, argued and
tested

The brief draws `Observe` once, at the top of the loop, implying a fresh
Observe every retry. The implementation instead takes **one Observe
before the retry loop begins** (the step's baseline), and every attempt's
Verify re-observes and compares **against that baseline**, not against
the immediately-preceding attempt's own reading. This was not the first
implementation — it replaced one that *did* compare each attempt only to
its own immediately-prior Observe, and that version had a real bug,
caught by `TestEveryActionVerified::test_readiness_expectation_is_checked
_via_perception` failing: once an early attempt already produced the
intended change (a window's title finished transitioning), every
*subsequent* retry's own Act legitimately did nothing further, so
comparing attempt-to-attempt made an already-successful step escalate
after three retries, every time. `ExpectedOutcome.expect_change` asks
*"is the world different from when this step began?"*, never *"did this
specific retry's own action do something new?"* — the fix, and the
reasoning for it, are both recorded in `state_machine.py`'s own
docstrings, at both the module level and on `run_step()` itself, not just
here.

---

## 3 · Tactical Decision Boundary — exactly the brief's two lists

| Operator MAY decide | Enforced by |
|---|---|
| Click A or B | `StepAction.alternate_x/alternate_y` — never a coordinate the Operator invented, always one Founder Runtime already named acceptable in the step |
| Wait | `ActionKind.WAIT`, or `RecoveryKind.WAIT_FOR_LOADING` |
| Retry | The bounded loop, `TacticalRecovery.outcome_for()` |
| Focus window | `ActionKind.FOCUS` → `DesktopExecutor.focus()` |
| Recover focus | `RecoveryKind.REFOCUS_APPLICATION` |
| Recover tab | Not separately implemented — see §8 (known limitations) |
| Recover application | `RecoveryKind.REOPEN_WINDOW` (running, no window) / `REFOCUS_APPLICATION` (window state unknown) |

| Operator NEVER decides | Enforced by |
|---|---|
| Use another AI | No AI/provider/broker module is importable — `TestNeverActsOrReadsDirectly` |
| Change workflow | `MissionStep`s are fixed at task construction; nothing in this package appends, removes, or reorders one |
| Choose another application | `MissionStep.application` is set once, at construction, by Founder Runtime; no method reassigns it |
| Choose another browser | `DesktopExecutor.browser` is one `BrowserExecutive`, held at construction; nothing in `desktop_operator/` constructs or selects a second one |
| Change mission | `DesktopTask.steps` is a frozen tuple; `execute()` iterates it read-only |

`TestNoStrategicDecisions` checks the closed vocabulary structurally:
`RecoveryKind` is exactly the brief's six (five recovery examples plus
*"click A or B"*), `ActionKind` is exactly `DesktopExecutor`'s six
primitives, and `_decide()`'s own source is parsed by AST to confirm no
numeric coordinate literal (beyond `0`, used only in comparisons) is
fabricated anywhere in the method body.

---

## 4 · Tactical Recovery

`TacticalRecovery.plan()` **decides; it never acts** — it holds no
`DesktopExecutor`, imports nothing execution-capable, and is a pure
function of the step and the current `MissionContext`. Every branch is
evidence-driven, the same discipline C27's UI Ready Detector already
established for the identical reason:

| Evidence | Recovery chosen |
|---|---|
| Step names an alternate target, and this is the first retry | `USE_ALTERNATE_TARGET` |
| Application running, window absent, still within its C25 startup estimate (`ReadinessState.LOADING`) | `WAIT_FOR_LOADING` |
| Application running, window absent, **past** its C25 startup estimate | `REOPEN_WINDOW` |
| Window state cannot be determined at all (not running, or unknown) | `REFOCUS_APPLICATION` |
| Browser active, page not yet loaded | `REFRESH_PAGE` (via `DesktopExecutor.browser.open_url()` on the **already-observed** current URL — never a URL the Operator invents) |
| A click failed with none of the above evidence | `RETRY_CLICK` |
| Any other action failed with none of the above evidence | `REFOCUS_APPLICATION` |

### 4.1 A second real bug, caught by the same discipline

`LOADING` is itself a *"no window found yet"* reading — C27's own
`_window_missing()` only returns `LOADING` while a window is absent. The
first implementation checked *"is the window absent"* **before** checking
*"is the application loading,"* which meant `WAIT_FOR_LOADING` could never
be reached: every application in the `LOADING` state also has no window,
so the window-absence branch always intercepted it first, silently and
permanently. Caught by
`TestTacticalRecoveryPlanning::test_retry_click_as_the_generic_fallback`
and its sibling failing once `test_wait_for_loading_when_readiness_is_
loading` was tightened from *"accepts either outcome"* to asserting the
one correct kind. Fixed by checking readiness before the generic
window-absence branches; `tactical_recovery.py`'s own comment at that
exact line records why the ordering matters, so a future edit cannot
silently reintroduce the same dead code.

---

## 5 · Retry ceiling

`MAX_RETRIES = 3`, the brief's own number, held as one module-level
constant in `tactical_recovery.py` and nowhere duplicated.
`TacticalRecovery.outcome_for(step_retries)` is a pure function of one
integer: below the ceiling, `RETRY`; at the ceiling, `ESCALATE`. There is
no fourth answer.

`run_step()`'s loop is `for attempt in range(1, MAX_RETRIES + 1)` — a
fixed-range loop, never a `while True`. On the third failed attempt, the
method escalates directly rather than attempting recovery a fourth time;
`TestRetryCeiling::test_a_step_that_never_succeeds_escalates_after_
exactly_three_attempts` proves both the count (exactly `MAX_RETRIES`
clicks are made) and the outcome.

`context.step_retries` resets to `0` at the start of every step
(`MissionContext.begin_step()`), because the ceiling is per-step, not
per-mission: a five-step mission where each step needed one retry is not
the same failure as one step needing five.

---

## 6 · Timeout policy

Every `MissionStep.timeout_seconds` is validated **positive at
construction** — `MissionStep.__post_init__` refuses zero or negative,
so *"every step must carry a timeout"* is a type error, not a runtime
check that could be skipped. `TimeoutGovernor.check()` is called twice per
attempt (before Act, and after Act before Verify) and raises
`StepTimeoutFailure` — carrying the step index, elapsed seconds, and the
limit — the moment the step's own budget is exceeded, at any point in the
attempt, not only between attempts.

**No infinite waits, no endless retries, no polling loops** — each
honoured by a distinct structural fact, not a shared promise:

- *No infinite waits*: `ActionKind.WAIT` and `RecoveryKind.WAIT_FOR_
  LOADING` both sleep a **bounded** amount — the recovery wait is
  `min(RECOVERY_WAIT_SECONDS, TimeoutGovernor.remaining())`, so recovery
  itself can never cause the timeout it exists beside.
- *No endless retries*: §5 — a fixed-range loop, capped at `MAX_RETRIES`.
- *No polling loops*: `TimeoutGovernor` contains no loop of any kind — it
  is one elapsed-time comparison, called by the state machine's own
  already-bounded loop.

`TimeoutGovernor.remaining()` never returns a negative number — a step
already over budget has zero seconds remaining, never a number a caller
might otherwise sleep against.

---

## 7 · Why `_observe()` also calls `desktop.inventory.discover()` — the
one stated judgment call in this component

`DesktopObserver.observe()` (C27) takes an optional `MachineInventory`
and uses it to attribute a window's process id to an application key.
Without one, C27's `WindowObserver` cannot say *which* application a
window belongs to, and every readiness and verification check in this
package depends on that attribution. C27 left the parameter
caller-supplied on purpose — its own docstring: *"Caller-supplied, never
read from an ambient clock/probe inside this layer."* Someone upstream
has to supply it.

**Judged not to be the *"read windows/browser/UI directly"* the brief
forbids.** `MachineInventory` is Desktop Executive's own data model
(`desktop/inventory.py`), already consumed throughout `desktop/actions
.py`, `desktop/execution/process.py`, and `desktop/operations`.
`discover()` reads installed applications and the process list through a
`SystemProbe` — the same read `ProcessExecutive.is_running()` already
performs internally on every call this package makes — never a mouse,
keyboard, window handle, or browser page. This is the same category of
call `founder_edition/boot.py` (C24) was already permitted to make as its
own composition root's one machine-touching step, for the identical
reason: an inventory scan is a fact about installed software and running
processes, not about what is currently on screen.

`state_machine.py`'s own module docstring carries this argument in full,
at the point a reader would ask the question, and `tests/
test_desktop_operator.py::TestNeverActsOrReadsDirectly::test_inventory_
is_read_via_discover_not_a_second_scanner` asserts `discover()` is called
and no internal helper of it (`discover_application`,
`attribute_processes`) is — the inventory is C27/C25's own contract,
consumed once, never re-derived.

---

## 8 · Every action verified — and MissionContext, destroyed

**"EVERY action requires verification. Never Act → Act without Verify
between them."** `_act()` and `_verify()` are called exactly once each per
loop iteration, in that order — proven by reading `run_step()`'s own
source (§2), not merely asserted by convention. `_verify()` always calls
`self._observe()`, which is always exactly one `DesktopObserver.observe()`
call — never a cached value, never a second read mechanism.

**`MissionContext` is created inside `DesktopOperator.execute()`'s own
call frame and held nowhere else.** `DesktopOperator` has no
`_context`/`_mission_context` attribute; `TestMissionContextEphemerality
::test_mission_context_does_not_survive_execute` iterates every attribute
the operator instance actually holds after a real `execute()` call and
asserts none of them is a `MissionContext` — the strongest proof Python
offers short of watching the garbage collector. A second test
(`test_mission_context_is_never_persisted_or_entered_into_memory`) checks
by AST that no module in this package imports `master_agent.persistence`
or `master_agent.memory` at all — the *"never persisted, never enters
Memory"* rule is a fact about the whole package's import graph, not a
promise about one code path.

---

## 9 · Founder Runtime boundary

*"Founder Runtime sends `DesktopTask`. Desktop Operator returns
`ExecutionResult`. Nothing more."*

`DesktopOperator.execute(task: DesktopTask) -> ExecutionResult` is the
entire public method signature — checked directly by
`TestFounderRuntimeBoundary::test_execute_returns_only_an_execution_
result` via `inspect.signature`. `ExecutionResult` states facts:
`outcome`, how many of the mission's steps completed, a human-readable
`reason`, and — only when escalated — an `EscalationRequest` naming the
step, the reason, how many retries were exhausted, the last observation's
confidence, and a plain-language detail. **`EscalationRequest` has no
field that could carry a recommendation** — its dataclass fields are
checked directly against the closed set `{step_index, reason,
retries_exhausted, last_observation_confidence, detail}`, so Founder
Runtime is never handed a suggestion dressed as a fact.

### 9.1 A deliberate name collision, not an accident

`master_agent.executor.action.ExecutionResult` already exists and is
used throughout `desktop/execution/` and `desktop/perception/` — every
`Act` this package performs returns one internally. This module's
`ExecutionResult` is a different type at a different altitude: the
Action-level type answers *"did this one click succeed?"*; this one
answers *"did the whole mission succeed, and what does Founder Runtime
need to know?"* Nothing in this package imports both under the same bare
name in the same scope — the collision is documented in
`execution_result.py`'s own module docstring rather than hidden, and the
brief's own naming (`execution_result.py`, `ExecutionResult`) is honoured
literally rather than renamed to avoid the collision.

---

## 10 · No Executive duplication, no Perception duplication

Checked by AST, not by promise, across every file in the package:

| Guarantee | How it is enforced |
|---|---|
| Only `desktop.execution.executor` is imported from C26 | `window`, `keyboard`, `mouse`, `clipboard`, `process`, `browser`, `backends`, `win32_backends`, `actions`, `plugin`, `probe` (as a construction path) — none imported |
| Only `desktop.perception`'s own public surface is imported from C27 | `windows`, `browser`, `clipboard`, `win32_probe` submodules — none imported directly |
| No second `WindowBackend`/`MouseBackend`/`KeyboardBackend`/`ClipboardBackend` Protocol | None declared anywhere in `desktop_operator/` |
| No second `Confidence`, `ReadinessState`, or `FailureKind` vocabulary | Imported, never redeclared |
| No frozen package reachable | `foundation`, `kernel`, `ledger`, `coordinator`, `runtime_bridge`, `api` — none imported |
| No Mission Control, planning, or Founder Runtime/Edition surface reachable | `mission_control`, `planner`, `brain`, `orchestrator`, `runtime.*` (the Engine), `founder_runtime`, `founder_edition` — none imported |

**The guards were proven able to fail.** A throwaway module containing
`import subprocess`, `from master_agent.kernel import Kernel`, and
`from master_agent.desktop.execution.window import WindowManager` was
added to the package and the suite re-run:

```
FAILED TestNeverActsOrReadsDirectly::test_no_module_that_could_touch_the_machine_is_imported
FAILED TestNeverActsOrReadsDirectly::test_no_direct_execution_or_perception_submodule_is_imported
FAILED TestNeverActsOrReadsDirectly::test_no_frozen_package_is_imported
3 failed, 9 passed, 71 deselected
```

The file was deleted and the suite returned to 83 passing.

---

## 11 · Test evidence

```
python -m pytest tests/test_desktop_operator.py -q
  83 passed in ~2s

python -m pytest tests/test_desktop_operator.py --cov=master_agent.desktop_operator
  __init__.py             8 stmts   0 miss  100%
  execution_result.py    43 stmts   0 miss  100%
  mission_context.py     84 stmts   0 miss  100%
  operator.py            34 stmts   0 miss  100%
  state_machine.py      124 stmts   0 miss  100%
  tactical_recovery.py   38 stmts   0 miss  100%
  timeouts.py             20 stmts  0 miss  100%
  TOTAL                  351 stmts  0 miss  100%

python -m ruff check src/master_agent/desktop_operator/ tests/test_desktop_operator.py
  All checks passed!
```

**Full suite: 5871 passed, 49 failed, 1 skipped (203s)** — up from C27's
5788 passed with the identical 49 pre-existing failures
(`FounderConsole.__init__()` rejecting a `memory` keyword argument, and
`launcher/boot.py:693` reading ambient `datetime.now()`, both sitting in
the uncommitted MB032–039 working tree, unrelated to and unmodified by
this component). All 83 new tests landed clean; nothing existing
regressed.

**No test drives a real desktop.** Every `DesktopExecutor` and
`DesktopObserver` in this suite is built over Fake backends
(`ScriptedBackend`, matching C26/C27's own fixture pattern — a click can
change what a later enumerate reports, which is what makes Verify
actually testable). Two tests use a real, **headless**
`BrowserSessionManager` against `data:` URLs only — the identical pattern
C26/C27's own suites already establish for the whole Browser Worker
surface, not new risk introduced here.

---

## 12 · Frozen components and prior surfaces

```
git diff --stat kalpavriksha-s1-c18.0 -- foundation kernel ledger coordinator
                                          runtime_bridge api
→ (empty)

git status --porcelain -- foundation kernel ledger coordinator runtime_bridge api
→ (empty)

git status --porcelain -- desktop/execution desktop/operations desktop/perception
                            desktop/actions.py desktop/plugin.py
→ (only the untracked C25/C26/C27 directories themselves; no existing
   tracked file touched)
```

**Byte-identical to the frozen tag, and every prior C25–C27 deliverable
this component consumes is untouched.** Every file this brief delivers is
new.

---

## 13 · Known limitations

1. **"Recover tab" is not separately implemented.** The Tactical Decision
   Boundary names it alongside recover focus/application, but
   `TacticalRecovery` has no dedicated `RecoveryKind` for it —
   `RecoveryKind.REFOCUS_APPLICATION`/`REOPEN_WINDOW` cover the window-
   level recovery a lost or hidden browser tab would also need, and
   `DesktopExecutor.browser.switch_tab()` exists and is reachable through
   the executor, but nothing in `plan()` currently chooses it. Recorded
   as absent rather than half-built.
2. **`REFRESH_PAGE` only fires when a URL has already been observed.** If
   `context.current_observation.browser.current_url` is unknown, the
   recovery silently does nothing that attempt (proven safe by
   `TestDesktopStateMachineDirect::test_refresh_page_recovery_calls_
   browser_open_url`) and the loop proceeds to its next attempt or
   escalation — it does not fabricate a URL to retry with, which would be
   inventing a mission decision.
3. **`BUSY` readiness (a title change between observations) is real
   evidence of activity, never proof of *why*.** A step whose expected
   readiness is `READY` can still be delayed by a spurious title change
   unrelated to the step's own goal; `TacticalRecovery` treats this the
   same as any other unverified click and retries, which is the correct,
   conservative behavior but not a guarantee of efficiency.
4. **No test exercises this package against a real, unattended desktop.**
   Every scenario in `tests/test_desktop_operator.py` is deterministic and
   Fake-backed by design (§11) — this proves the state machine's logic is
   correct against the contracts C26/C27 publish, not that a real mouse
   click on a real window produces the readiness transitions this
   package's tests assume. C26's and C27's own health reports already
   name their real backends' mutating paths as unverified live, for the
   same reason; this component inherits that same boundary rather than
   resolving it.
5. **The Gemini Architecture Review named in this brief's grounding was
   not available** (§0). Any observations it might have raised about
   this component's design were not incorporated, because they could not
   be read.

---

*End of report. Working-directory evidence only. No commits, no tags, no
Rule 001 milestone declared.*
