# KALPAVRIKSHA — DESKTOP VERIFICATION CORRECTNESS REPORT

**Date:** 2026-08-19 · **Base:** `0661de8` == `origin/main`, ahead 0, behind 0

Three semantic defects in the `DesktopGateway` I shipped at `0661de8`, plus one false
capability claim. All four found by CTO inspection, all four real, all four confirmed
against source before repair.

---

## 1. What was wrong

### Defect 1 — a non-empty dict is always truthy

```python
process_running = bool(probe.output)          # shipped at 0661de8
```

`IsRunningAction.run()` returns:

```python
output={"application": spec.key, "running": bool(running), "processes": [...]}
```

That dict is **never empty**, so `bool(output)` was `True` whether the application was
running or not. `launch_application` would have verified **MATCHED unconditionally** — a
fabricated pass, which is exactly the failure this entire line of work exists to remove.
`close_application` would have reported "still running" for every successful close.

Now the published field is read, and an observation that could not be taken is `None`,
never `False`. *"Not running"* and *"could not find out"* are different facts, and only
the first is evidence of a successful close.

### Defect 2 — the null backend

```python
windows = WindowManager()                     # shipped at 0661de8
```

`WindowManager.__init__` falls back to `NullWindowBackend()`. The verifier observed
nothing on a real desktop and would have reported no window under every condition. It now
passes `Win32WindowBackend()` explicitly — the same backend `actions_interaction` uses.

### Defect 3 — a title guess is not ownership

```python
foreground_matches = needle in str(active.output).lower()   # shipped at 0661de8
```

Wrong in both directions: a document window need not name its application
(`Quarterly Report.docx`), and an unrelated window may mention it
(`notepad - Google Search`). Foreground is now verified by comparing the active window's
`process_id` against the freshly observed process ids of the requested application.

`WindowManager.locate_by_process` already existed for precisely this, and its own
docstring says so: *"an exact match instead of a title guess."*

### False claim — `close_window`

The Step payload names an **application**; execution resolves a window handle internally.
Afterwards — without reading the Action's own report, the one thing Verification may not
do — *"the intended window closed and a sibling of the same application remains"* is
indistinguishable from *"the intended window is still open"*. Both look like "this
application still has windows".

Claiming support would have been right by accident for single-window applications and
silently wrong otherwise. `close_window` is now **not generically verifiable**, which is
the truthful answer. Making it verifiable is an observation-subject question for the Step
contract, not something to paper over in the adapter.

---

## 2. Why the previous tests missed all of it

They proved **wiring shape**: that a gateway existed, subclassed the right base, and
returned `None` for unsupported capabilities. Every one of them passed against the
defective implementation, because none of them ever asked what the verifier *observed*.

This is the same class of mistake as the earlier `microphone_enabled` episode — checking
that code exists rather than that a value flows correctly.

`tests/test_desktop_verification_semantics.py` — **26 behaviour tests**, driven through
injected read-only observers that return the real `ExecutionResult` / `WindowInfo` shapes,
so they run deterministically without a desktop.

---

## 3. Mandatory mutation proof (§9)

Each defect was reintroduced and the suite re-run:

| Mutation | Tests that failed |
|---|---|
| `return bool(output), ...` | `test_running_false_is_observed_as_false`, `test_launch_does_not_match_when_nothing_is_running`, `test_close_matches_when_no_process_remains` — **3** |
| `WindowManager()` (null backend) | `test_the_verifier_builds_a_win32_backed_window_manager` — **1** |
| title substring instead of PID ownership | `test_a_title_that_names_the_app_but_belongs_elsewhere_does_not_match`, `test_a_window_that_does_not_name_the_app_still_matches_when_it_owns_it` — **2** |

All restored; 26/26 pass. The tests would have caught `0661de8`.

Independently confirmed the baseline was genuine: `git show 0661de8:.../gateway.py`
contains `bool(probe.output)`.

---

## 4. Coverage correction

**Desktop canonical verification: 4/19**, not the 5/19 previously reported.

| capability | verifiable | postcondition |
|---|---|---|
| `launch_application` | **YES** | application has ≥1 running process |
| `close_application` | **YES** | application has 0 running processes |
| `focus_window` | **YES** | active window's pid ∈ application's pids |
| `bring_to_front` | **YES** | same |
| `close_window` | **NO** | see §1 |
| the other 14 | **NO** | no generic read-only postcondition |

`REPORT_PRODUCTION_WIRING_TRUTH.md` has been corrected in place (5/19 → 4/19,
`close_window` row rewritten) with a note pointing here.

### Adapter wired ≠ capability verified

These are separate facts and the report now keeps them apart:

* **`DesktopGateway` is wired** — the Founder Edition registers it, and it produces
  canonical `Evidence`. That is a wiring fact.
* **4 of 19 capabilities are semantically supported** — the other 15 return `None`. That
  is a coverage fact.

A wired adapter does not mean a verified Executive.

---

## 5. Classification correction (§12)

| Item | Category |
|---|---|
| `DesktopGateway` | **A. BUILT AND WIRED** — partial capability support |
| Filesystem / Browser gateways | **A. BUILT AND WIRED** — partial capability support |
| Evidence → Reporter | **B. BUILT BUT UNWIRED** |
| Fail-closed lifecycle | **B. BUILT BUT UNWIRED** (deliberately deferred) |
| Verification for the unsupported capability sets | **C. PARTIALLY IMPLEMENTED** — the observation primitives exist; the expectation contract for these subjects does not |
| Cross-step output references / resolution | **D. ACTUALLY NOT BUILT** |
| Semantic Founder-outcome conformance | **D. ACTUALLY NOT BUILT** |

The previous report over-used "BUILT BUT UNWIRED". An unsupported capability is not a
wiring gap when the semantic verification contract for that subject does not exist — a
click has no generic observable postcondition, so there is nothing waiting to be
connected.

---

## 6. Execution untouched

`"invoke" not in DesktopGateway.__dict__` — asserted, still true. The gateway gained a
constructor only to accept injected read-only observers for tests; production leaves both
unset and builds the real ones. Execution still runs:

    MissionControl -> DesktopGateway.invoke (inherited) -> DesktopPlugin
                   -> registered Action -> DesktopExecutor / DesktopExecutiveV2
                   -> Process / Window / Keyboard / Mouse / UIA -> Windows

---

## 7. Regression

Named failure sets against `0661de8`:

| | |
|---|---|
| Baseline failures | 20 |
| After this change | 20 |
| **Introduced** | **0** |

One earlier test asserted `supports("close_window")` and was corrected along with the
claim it encoded.

---

## Verdicts

| | |
|---|---|
| CURRENT DESKTOP EXECUTION PRESERVED | **YES** |
| PROCESS FALSE OBSERVED AS FALSE | **YES** |
| REAL WIN32 WINDOW BACKEND USED | **YES** |
| FOREGROUND VERIFIED BY PROCESS OWNERSHIP | **YES** |
| LAUNCH PROCESS PRESENCE VERIFIED | **YES** |
| CLOSE PROCESS ABSENCE VERIFIED | **YES** |
| CLOSE_WINDOW FALSE CLAIM REMOVED | **YES** |
| DESKTOP CANONICAL VERIFICATION COVERAGE | **4/19** |
| NO FABRICATED EVIDENCE | **YES** |
| GLOBAL FAIL-CLOSED ENABLED | **NO** |
| REPORTER WIRING TOUCHED | **NO** |
| INTRODUCED TEST FAILURES | **0** |
