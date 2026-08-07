# Health Report — Sprint 1, Component 27: Desktop Perception Layer

**Type:** Implementation health report. Working-directory evidence only.
**Date:** 2026-08-06
**Status:** Complete. **Not committed, not tagged, no Rule 001.**
**Built on:** `kalpavriksha-s1-c18.0` — commit `01497c3`, treated as frozen. Every file below is new; nothing at or below that tag was touched.
**Ground:** C1–C26 · Desktop Executive (Mission Brief 030) · Desktop Operations (C25) · Founder Runtime (C23) · Founder Boot (C24) · Environment Intelligence (C22) · Browser Worker (Mission Brief 022) · existing Desktop assets.

**Constraints honoured:** no Kernel/Runtime/Constitution/Mission Control/
Desktop Executive/Environment Intelligence redesign · no Sprint 2 · no
Mission OS · perception only — never executes, clicks, types, launches,
terminates, restarts, moves the mouse, presses a key, or modifies a
window.

---

## 1 · What was built

| File | | |
|---|---|---|
| `src/master_agent/desktop/perception/evidence.py` | new | 120 lines, **40 AST statements** |
| `src/master_agent/desktop/perception/win32_probe.py` | new | 76 lines, **27 AST statements** |
| `src/master_agent/desktop/perception/windows.py` | new | 163 lines, **59 AST statements** |
| `src/master_agent/desktop/perception/readiness.py` | new | 201 lines, **53 AST statements** |
| `src/master_agent/desktop/perception/browser.py` | new | 209 lines, **68 AST statements** |
| `src/master_agent/desktop/perception/clipboard.py` | new | 74 lines, **30 AST statements** |
| `src/master_agent/desktop/perception/state.py` | new | 95 lines, **41 AST statements** |
| `src/master_agent/desktop/perception/history.py` | new | 110 lines, **55 AST statements** |
| `src/master_agent/desktop/perception/failures.py` | new | 169 lines, **62 AST statements** |
| `src/master_agent/desktop/perception/engine.py` | new | 212 lines, **74 AST statements** |
| `src/master_agent/desktop/perception/__init__.py` | new | 24 exported names |
| `tests/test_desktop_perception.py` | new | 1088 lines, **98 tests** |

**522 statements of implementation.**

```
   Desktop Executive (C26)     ↓ acts
   Desktop Perception (C27)    ↓ observes
   Desktop Operator (future)   ↓ decides

   WindowObserver · BrowserObserver · ClipboardObserver · UIReadyDetector
              │
              ▼
   ObservationEngine.observe(now, applications, inventory) -> DesktopState
              │
              ▼
   DesktopObserver  ─┬─ DesktopObservationHistory (latest/changes_since/stable)
                      └─ FailureDetector (compares the last two observations)
```

---

## 2 · Read this first — a real bug the tests caught, not just exercised

`Observation.as_dict()`'s first draft projected a single as_dict-capable
value (a `WindowInfo`) but not a **tuple** of them — `WindowObserver`'s
own `windows` observation, whose `.value` is `tuple[WindowInfo, ...]`.
With zero windows this bug was invisible (`json.dumps(())` silently
serializes to `[]`, so a naive equality check on an empty case would have
passed); `test_desktop_state_as_dict_round_trips_through_json`, written
with at least one real window present, caught the mismatch immediately —
the original assertion compared a `tuple` of live objects against its own
`json.loads(json.dumps(...))`, which cannot round-trip a tuple of
dataclass instances at all. Fixed by projecting tuples/lists element-wise
in `evidence.py`. Recorded here because it is exactly the class of defect
a coverage number does not surface on its own — the line was executed
either way; only a test that checked the *value*, not just that the code
ran, found it.

---

## 3 · Component-by-component, each mapped to what it reuses

| Component | Brief's requirements | Reuses |
|---|---|---|
| Window Observer | active window, focused application, title, process, minimized, maximized, foreground | Only C26 `WindowManager`'s three non-mutating methods — `enumerate()`, `active()`, `locate_by_process()` (used by the engine, not this file directly). "Focused application" is resolved from `MachineInventory.processes[].owner`, the same attribution `desktop.actions.IsRunningAction` already reads — no new process→application mapping |
| UI Ready Detector | Ready / Busy / Hung / Window Missing / Loading / Unknown, evidence only | C25's `ApplicationOperationProfile.startup_time` for the loading/overdue boundary; one new, narrowly-scoped read (`win32_probe.py`) for Hung, because nothing before this brief could answer it |
| Browser Observer | browser active, current URL, page loaded, navigation complete, tab count | `ObserveBrowserAction` (MB022) for url/title; `BrowserSessionManager.list_sessions()` for tab count; one new read (`document.readyState`) for load state — nothing else on the page is touched |
| Desktop State | applications, windows, browser, clipboard status, focus, foreground, time, confidence | `focus`/`foreground` are `windows.active_application`/`windows.active_window`, aliased — not a second observation of the same fact |
| Observation Engine | `observe()`, immutable, never acts | Composes the five observers; performs no observation of its own beyond attributing a window to an application (matching process ids already computed) |
| Evidence Model | confidence, reason, source, timestamp | `Confidence` is C22's own enum, imported not redeclared; `Observation` adds the one field C22's own `Inference` has no use for — a moment |
| Observation History | last N, `changes_since()`, `latest()`, `stable()` | Bounded the same way `ConversationMemory` (C23) is bounded |
| Failure Detection | the brief's own six kinds, structured, never recovers | Compares two already-produced `DesktopState`s — no new observation |

---

## 4 · Two new reads, both argued, both narrowly scoped

Every fact but two was already observable through C22/C25/C26. The two
genuinely new reads exist because nothing before this brief needed to ask
these questions, and both are justified individually rather than bundled
into a general "perception can read whatever it needs" license:

**`document.readyState` (`browser.py`).** Neither `ObserveBrowserAction`
nor `BrowserSessionManager` exposes whether a page has finished loading.
`page.evaluate("document.readyState")` is a standard, sandboxed DOM query
— it cannot navigate, click, or mutate anything, and the expression is a
fixed string, never caller-supplied. **Both `page_loaded` and
`navigation_complete` are honestly stated as measuring the same
underlying signal**: this layer performs one static read and cannot
distinguish *"idle"* from *"about to navigate"* without the event-listening
the Browser Worker's own architecture deliberately avoids
(`BROWSER_WORKER_ARCHITECTURE.md` §8 — mechanical failures only). Stated
in the `navigation_complete` observation's own `reason` field, not buried
in a docstring only a developer would read.

**`SendMessageTimeoutW(WM_NULL)` (`win32_probe.py`).** The identical
technique Windows' own Task Manager uses to mark a process *"Not
Responding."* `WM_NULL` is a no-op every window procedure must handle;
the call changes nothing about the window. Without it, `ApplicationHung`
would have to be guessed from elapsed time alone — exactly the assumption
the brief forbids (*"Must never assume. Evidence only."*). Isolated in
its own file, `ctypes`-only, no `pywin32`, mirroring `desktop/execution/
win32_backends.py`'s own isolation for the identical reason: a
platform-detection failure here fails one import, never the package's.

---

## 5 · UI Ready Detector — never assumes, and it is tested against the
temptation to assume

The detector's own table (in its module docstring) states exactly what
evidence produces each state, and `test_never_assumes_hung_from_elapsed_
time_alone` is written specifically against the shortcut a naive
implementation would take: a window that has existed five hours, with no
responsiveness signal available at all, is asserted **not** to become
`HUNG` — only a real `SendMessageTimeoutW` result may say so. `Unknown` is
the state this detector reaches more often than a caller might expect
from a system that "tries to be helpful," and that is the design working
as intended, not a gap:

- `test_unknown_when_responsiveness_cannot_be_checked_and_title_unchanged`
  — no responsiveness signal, no title change → `UNKNOWN`, never a guess.
- `test_loading_weak_without_a_profile_or_launch_time` — running with no
  window, but nothing to compare elapsed time against → `LOADING` at
  `WEAK`, not `STRONG` — the confidence band itself states how much the
  conclusion actually rests on.
- `Busy` requires an observed title change between two real observations
  (`ObservationHistory`, reused rather than re-queried) — never inferred
  from "some time has passed."

---

## 6 · Confidence propagation — proven to actually aggregate, not just
report per-field

`DesktopState.confidence` is `Confidence.weakest()` (C22's own
combinator, not a new one) over **every** observation the state carries.
`test_the_whole_state_confidence_is_dragged_down_by_an_unobserved_
browser` is the test that proves this is real: a scenario with a fully
observed window, application and readiness (all `OBSERVED`/`STRONG`) but
no browser session open still reports the *whole* state's confidence as
`UNKNOWN`, because `browser.current_url` is honestly unknown when nothing
is open — proving the aggregate is computed across every section, not
just the one a caller happens to check first.

---

## 7 · Failure Detection — six kinds, each a comparison, never a guess

Every one of the brief's six kinds is detected by comparing exactly two
`DesktopState`s — `FailureDetector` holds no state of its own and
performs no observation:

| Kind | Evidence |
|---|---|
| `WINDOW_DISAPPEARED` | had a window, now has none, process still running |
| `APPLICATION_CRASHED` | had a window, now has neither a window nor a running process |
| `WINDOW_HIDDEN` | had a *visible* window, now has the same window but not visible |
| `APPLICATION_NEVER_APPEARED` | was `LOADING`, is now `WINDOW_MISSING` past its own C25 startup estimate, still running |
| `BROWSER_CLOSED` | a browser session was open, none is open now |
| `NAVIGATION_FAILED` | a browser session is open, its URL was observable a moment ago and is not now |

An application tracked in the previous observation but not requested in
the current one is silently skipped rather than reported missing —
`test_an_application_no_longer_tracked_in_current_is_skipped` — because a
caller choosing not to ask about an application is not evidence anything
happened to it.

---

## 8 · Structural guards, and the guards proven able to fail

| Guarantee | How it is enforced |
|---|---|
| No mutating call anywhere | 24 forbidden method names — `click`, `type_text`, `hotkey`, `launch`, `terminate`, `restart`, `bring_to_front`, `minimize`, `maximize`, `restore`, `close`, `write`, `clear`, `new_tab`, `close_tab`, `switch_tab`, `open_url`, `execute`, and more — checked by AST, none present |
| No execution-capable module reachable | `desktop.execution.executor`, `.keyboard`, `.mouse`, `desktop.actions`, `desktop.plugin` — none imported |
| No frozen package reachable | `foundation`, `kernel`, `ledger`, `coordinator`, `runtime_bridge`, `api` — none imported |
| No planning/orchestration surface reachable | `mission_control`, `planner`, `brain`, `orchestrator`, `runtime.*` (the Engine) — none imported |
| No second window reader, catalog, or Playwright driver | `desktop.execution.window` **is** imported (reused); `desktop.catalog`, `sync_playwright`, `chromium.launch` are **not** |
| No second Confidence band or Operation Profile type | `Confidence` imported, never redeclared; `ApplicationOperationProfile`, `DesktopExecutiveV2`, `Capability` (C25) declared nowhere here |
| No cookie/history/credential inspection | Checked against `browser.py` specifically (its own prose legitimately names what it refuses to do; `history` is also this layer's own unrelated `DesktopObserver.history` property elsewhere in the package, which the check is scoped to exclude) |

**The guards were proven able to fail.** A throwaway module containing
`import subprocess` and `from master_agent.kernel import Kernel` was
added to the package and the suite re-run; `test_no_frozen_package_is_
imported` failed for the right reason. The file was deleted and the suite
returned to 98 passing.

---

## 9 · Verification status — what was checked live, and what was not

Following the discipline C26's own report established after its own
incident (§10 there): every mutating capability in this repository is
treated as consequential by default, and any live check is stated
explicitly rather than assumed safe.

**Exercised live, on this machine, in this session — both read-only:**

- `Win32WindowBackend.active()` (C26) to find this session's own active
  window ("Claude").
- `Win32ResponsivenessBackend.is_responding()` (this brief) against that
  same window's real handle — returned `True`. `SendMessageTimeoutW`
  against `WM_NULL` cannot mutate anything; this is the same class of
  check Task Manager performs continuously in the background, and it was
  run against this session's own window, not a founder's.

**Not exercised live:** everything else in this package uses Fake
backends (window/readiness/history/failures) or a real, **headless**
`BrowserSessionManager` against `data:` URLs only — the identical,
already-established pattern C26's own suite uses for the whole Browser
Worker test surface, run on every execution of this repository's test
suite already.

---

## 10 · Test evidence

```
python -m pytest tests/test_desktop_perception.py -q
  98 passed in ~4s

python -m pytest tests/test_desktop_perception.py --cov=master_agent.desktop.perception
  __init__.py       12 stmts   0 miss  100%
  browser.py        67 stmts   0 miss  100%
  clipboard.py      30 stmts   0 miss  100%
  engine.py         71 stmts   0 miss  100%
  evidence.py       37 stmts   0 miss  100%
  failures.py       59 stmts   0 miss  100%
  history.py        50 stmts   0 miss  100%
  readiness.py      53 stmts   0 miss  100%
  state.py          39 stmts   0 miss  100%
  win32_probe.py    21 stmts   6 miss   71%
  windows.py        56 stmts   0 miss  100%

python -m ruff check src/master_agent/desktop/perception/ tests/test_desktop_perception.py
  All checks passed!
```

**Every Fake-backed module is at 100%.** `win32_probe.py`'s real
`Win32ResponsivenessBackend` sits at 71% — its constructor and the
successful path were exercised by the one live check in §9; its own
platform-guard branch (non-Windows) and the timeout-path internals were
not, for the same reason C26's `win32_backends.py` was left at 0% by
disclosed decision rather than mocked into an inflated number.

**Full suite: 5788 passed, 49 failed, 1 skipped (200s)** — up from C26's
5690 passed with the identical 49 pre-existing failures
(`FounderConsole.__init__()` rejecting a `memory` keyword argument, and
`launcher/boot.py:693` reading ambient `datetime.now()`, both sitting in
the uncommitted MB032–039 working tree, unrelated to and unmodified by
this component). All 98 new tests landed clean; nothing existing
regressed.

---

## 11 · Frozen components and existing surfaces

```
git diff --stat kalpavriksha-s1-c18.0 -- foundation kernel ledger coordinator
                                          runtime_bridge api
→ (empty)

git status --porcelain -- foundation kernel ledger coordinator runtime_bridge api
→ (empty)

git status --porcelain -- desktop/actions.py desktop/plugin.py
                            environment/browser_session.py
                            executor/actions/browser plugins/browser_observation.py
→ (empty)
```

**Byte-identical to the frozen tag, and every existing surface this
component reuses — the Desktop Executive, the Browser Worker, C25's and
C26's own deliverables — is untouched.** Every file this brief delivers
is new.

---

## 12 · Success criteria, answered concretely

The brief's own five questions, each traced to the exact call that
answers it:

| Question | Answered by |
|---|---|
| *What is on my screen?* | `DesktopObserver.observe(now, ...).windows.value` — every enumerated window, visible or not |
| *Which application is active?* | `state.focus` — `windows.active_application`, resolved from real process attribution |
| *Is Chrome actually open?* | `state.application("chrome").is_running` and `.window` — both real `ExecutionResult`-derived facts, never assumed |
| *Did Claude launch?* | `state.application("claude_desktop").readiness` — `LOADING` while within its own C25 startup estimate, `WINDOW_MISSING` if it never appears |
| *Is the page finished loading?* | `state.browser.page_loaded` — `document.readyState == "complete"`, stated honestly when it cannot be read |

**No action was executed to answer any of them** — every one of the 98
tests proving these answers work injects a Fake or reads a real, headless
browser page that was never clicked, typed into, or navigated by this
package itself.

---

## 13 · What this does not do, stated so it is not assumed

1. **Nothing here decides anything.** The brief's own diagram —
   *"Desktop Operator (future) ↓ decides"* — names the next layer this is
   not. `DesktopObserver` has no method that acts on what it observes.
2. **No recovery is attempted.** `FailureDetector` reports; nothing in
   this package retries, restarts, or works around a detected failure.
3. **No OCR, no vision, no pixel is ever read.** Every fact in this
   package comes from window metadata, process attribution, or a DOM
   property read through Playwright's own sandboxed `evaluate()` — never
   a screenshot, never `BitBlt`, never `GetPixel`.
4. **`Busy` is a real but limited signal.** A title change is genuine
   observed activity, not proof of *why* — stated as `WEAK` confidence,
   never overclaimed as certainty about what the application is doing.
5. **The real responsiveness probe's failure paths are unverified live.**
   §9, §10 — stated plainly rather than discovered by surprise.

---

*End of report. Working-directory evidence only. No commits, no tags, no
Rule 001 milestone declared.*
