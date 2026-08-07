# Health Report — Sprint 1, Component 26: Elite Desktop Executive (Part 1) — Execution Substrate

**Type:** Implementation health report. Working-directory evidence only.
**Date:** 2026-08-06
**Status:** Complete. **Not committed, not tagged, no Rule 001.**
**Built on:** `kalpavriksha-s1-c18.0` — commit `01497c3`, treated as frozen. Every file below is new; nothing at or below that tag was touched.
**Ground:** C1–C25 · Desktop subsystem (`desktop/catalog.py`, `desktop/inventory.py`, `desktop/actions.py`, `desktop/probe.py`) · Environment Intelligence (C22) · Founder Runtime (C23/C24) · existing Desktop Executive (Mission Brief 030) · existing Browser Automation (`environment/browser_session.py`, `executor/actions/browser/`, Mission Brief 022) · existing AI Infrastructure (read, not touched) · Elite Desktop Executive knowledge layer (C25, `desktop/operations/`).

**Constraints honoured:** no Kernel/Runtime redesign · no Constitution
changes · no Sprint 2 · no Mission OS · no planning/orchestration/
autonomy/reasoning/routing/OCR/vision/AI conversation · every operation
routes through an existing C25 Operation Profile · no frozen component
modified.

---

## 1 · Read this first — an incident, disclosed

**While smoke-testing this package, a real instance of Chrome was
launched on this machine.** `DesktopExecutor()`'s default constructor
resolves to `RealSystemProbe()` — the same default `desktop.plugin
.DesktopPlugin` already uses — and an early exploratory call to
`executor.execute("chrome")` reached `LaunchApplicationAction.run()`,
which calls `probe.start([...])`, which calls `subprocess.Popen(...)` for
real. This was a mistake in how the package was exercised, not a defect
in the package's own design: reading a machine inventory (C24's own
verification method) is safe because it is read-only, and this was
wrongly treated the same way when it is not.

**What was verified afterward, independently, twice:** `Get-Process -Name
chrome` and `Get-CimInstance Win32_Process -Filter "Name='chrome.exe'"`
both report no such process anywhere on the machine, before this report
was written. The launch did not leave a persisting process — most likely
because the shell this session runs in is not attached to the interactive
desktop session Chrome would need. **This is not a guarantee that a
future call under different conditions would be equally harmless**, and
it is recorded as a real near-miss, not a non-event.

**The corrective action taken:** every test in `tests/
test_desktop_execution.py`, and every other exploratory command run after
this incident, uses a `FakeProbe` or `NullSystemProbe` — never
`RealSystemProbe` — for any operation heavier than read-only window
enumeration (§11). Nothing in this session subsequently launched,
clicked, typed into, or closed a real application.

**What is asked of whoever reviews this next:** treat `DesktopExecutor()`'s
real default as a live capability, not a documentation exercise — the
same way MB030's own `LaunchApplicationAction` always was, before this
brief gave it five siblings that can now type and click as well as
launch. If Founder Edition wiring (a future brief) constructs this class
without an explicit backend, it will reach the real machine.

---

## 2 · What was built

| File | | |
|---|---|---|
| `src/master_agent/desktop/execution/backends.py` | new | 171 lines, **101 AST statements** |
| `src/master_agent/desktop/execution/win32_backends.py` | new | 347 lines, **164 AST statements** |
| `src/master_agent/desktop/execution/window.py` | new | 151 lines, **77 AST statements** |
| `src/master_agent/desktop/execution/keyboard.py` | new | 87 lines, **48 AST statements** |
| `src/master_agent/desktop/execution/mouse.py` | new | 69 lines, **40 AST statements** |
| `src/master_agent/desktop/execution/clipboard.py` | new | 43 lines, **25 AST statements** |
| `src/master_agent/desktop/execution/process.py` | new | 142 lines, **51 AST statements** |
| `src/master_agent/desktop/execution/browser.py` | new | 202 lines, **96 AST statements** |
| `src/master_agent/desktop/execution/executor.py` | new | 178 lines, **77 AST statements** |
| `src/master_agent/desktop/execution/permissions.py` | new | 66 lines, **5 AST statements** |
| `src/master_agent/desktop/execution/__init__.py` | new | 22 exported names |
| `tests/test_desktop_execution.py` | new | 1248 lines, **128 tests** |

**696 statements of implementation.**

```
   DesktopExecutor.execute() / .focus() / .type() / .click() / .wait() / .close()
              │  every call checked against a C25 profile first
              ▼
   WindowManager · KeyboardController · MouseController · ClipboardExecutive
   ProcessExecutive (extends desktop/actions.py)  ·  BrowserExecutive (extends the Browser Worker)
              │
              ▼
   Win32*Backend (ctypes)  ·  BrowserSessionManager (Playwright)  ·  existing SystemProbe
```

**Placement:** `desktop/execution/`, a sibling of C25's `desktop/
operations/`, both inside `desktop/` per the same governing rule C25
established — *"No future module may encode application-specific behavior
outside the Desktop Executive"* — extended here to *how* it is operated,
never *whether* it may be.

---

## 3 · The seven components, each mapped to what it reuses

| Component | Brief's capabilities | Reuses |
|---|---|---|
| Window Manager | enumerate, locate, active, front, minimize, maximize, restore, close | Nothing existing to reuse — fills the gap `desktop/actions.py`'s own `BringToFrontAction` names by its own docstring: *"window focus needs desktop interaction, which MB030 deliberately excludes… a later Desktop Interaction brief owns this."* This is that brief. `desktop/actions.py` is untouched. |
| Keyboard Controller | type, press, hotkey, paste | `paste()` composes `ClipboardExecutive.write()` + `hotkey(("ctrl","v"))` — no third way to move text onto a screen |
| Mouse Controller | move, click, double-click, right-click, drag, scroll | Coordinates only, no new concept |
| Clipboard Executive | read, write, clear | No history — no fourth method |
| Process Executive | launch, wait, terminate, restart, is_running | `launch()`/`terminate()`/`is_running()` call `LaunchApplicationAction`/`CloseApplicationAction`/`IsRunningAction` (MB030) directly — `wait()` reuses C25's `startup_time` estimate for its default timeout; `restart()` composes the other two |
| Browser Executive | open_url, new_tab, close_tab, switch_tab, focus_browser | `OpenBrowserSessionAction`/`NavigateAction`/`CloseBrowserSessionAction` (MB022) for every session operation; `focus_browser()` reuses `desktop.inventory`'s process attribution + the new `WindowManager` — no second Playwright driver |
| Application Executive (`DesktopExecutor`) | execute, focus, type, click, wait, close | Every named-application method calls `DesktopExecutiveV2.profile()` (C25) first — see §5 |

---

## 4 · Window Manager fills a documented gap, without touching what named it

`BringToFrontAction`'s own docstring, read before writing a line of this
component:

> *"Focus is a window operation, and this Executive deliberately has no
> window automation (Deliverable 7). So it reports honestly that it
> cannot, rather than pretending."*

`window.py` is the independent, new implementation of exactly that
capability — `WindowManager.bring_to_front()`, `minimize()`, `maximize()`,
`restore()`, `close()` — and `desktop/actions.py` is not modified. The two
coexist: `BringToFrontAction` still reports its own honest refusal if
called directly; `WindowManager` is where the refusal's promised future
brief actually lands.

`WindowManager.close()` **posts `WM_CLOSE`**, never a forced kill — the
window gets the chance to prompt for unsaved work, the same distinction
`CloseApplicationAction`'s own docstring draws (*"Closing an editor with
unsaved work destroys it… `IRREVERSIBLE` on purpose"*) between an
application's own shutdown and `ProcessExecutive.terminate()`'s forced
kill, which reuses that existing Action rather than duplicating it.

`locate_by_process()` is the one new idea in this file: given a set of
process ids, find the window(s) they own. It exists so `focus_browser()`
and `DesktopExecutor.focus()` never guess at a window by matching a
title fragment — they resolve the exact window from `desktop.inventory`'s
own, already-audited process attribution.

---

## 5 · "Every operation routes through existing Desktop Executive
profiles. Never bypass them." — how this is actually true

`DesktopExecutor._profile_or_refusal()` is called first by every one of
`execute`/`focus`/`type`/`click`/`wait`/`close`. An application with no
C25 `ApplicationOperationProfile` is refused — as a structured
`ExecutionResult`, never an exception — before any window, keyboard, mouse
or process call happens:

```python
def execute(self, application: str) -> ExecutionResult:
    outcome = self._profile_or_refusal(application)
    if isinstance(outcome, ExecutionResult):
        return outcome
    return self.process.launch(application)
```

`type()` and `click()` go one step further, through
`_require_automatable()`: an application whose C25 profile names
`AutomationStrategy.NOT_AUTOMATABLE` is refused too. This is not a
fixture built to exercise a branch — `continue_dev`'s real, shipped C25
profile names exactly this strategy (it is a hosted editor extension with
no window of its own), and `test_type_refuses_a_not_automatable_
application` calls the real `DesktopExecutiveV2()` against it.

`test_every_named_application_operation_checks_the_profile_first` reads
each of the six methods' own source and asserts the profile check appears
in it — a structural proof, not a description, that bypassing C25's
knowledge would require deleting the check, not just forgetting to add
one somewhere new.

---

## 6 · No OCR, no vision, no image recognition — checked, not just avoided

The brief repeats this prohibition for both Window Manager and Mouse
Controller. `TestNoOcrOrVision` checks it two ways:

- **No image or OCR library is importable from this package** — `cv2`,
  `PIL`, `pytesseract`, `pyautogui`, `easyocr`, `numpy`, `mss` — eight
  names, none present.
- **No screen-capture or OCR call appears** — `GetPixel`, `BitBlt`,
  `screenshot`, `grab`, `locateOnScreen`, `image_to_string`, `imread` —
  none is called anywhere, including inside `win32_backends.py`, which
  could technically reach `user32.GetDC`/`gdi32.BitBlt` via `ctypes` and
  deliberately does not.

`MouseController.click`'s own signature is asserted to be exactly
`(self, x, y, button)` — no `target`, no `selector`, no `image` parameter
exists for a caller to pass, which is the brief's *"coordinates only"*
made structural rather than a promise.

---

## 7 · Browser Executive — a session is a tab, and nothing more is touched

The Browser Worker's own `BrowserSession` is one `BrowserContext` + one
`Page` — precisely what the brief calls a *"tab."* `new_tab()` opens a
session; `close_tab()` closes one; `switch_tab()` changes which session
subsequent calls act on **without any Playwright call at all** — it is
bookkeeping local to `BrowserExecutive`, verified by
`test_switch_tab_changes_the_current_pointer_without_touching_playwright`.

`focus_browser()` is the one place this file reaches outside the browser
itself, because Playwright has no concept of an OS window in front of
other windows. It resolves the browser's process via `desktop.inventory`
(never a second inventory) and asks `WindowManager.focus_process()` —
never a title guess.

**"Do NOT inspect: conversations, cookies, passwords, history"** is
checked twice: `test_no_conversation_cookie_password_or_history_method_
is_ever_called` reads the class's own source for those four words, and
`TestNoDuplication.test_browser_executive_imports_no_second_playwright_
driver` confirms `browser.py` never calls `sync_playwright()` or
`chromium.launch()` itself — every session is the existing
`BrowserSessionManager`'s.

Tests exercise a real, **headless** browser via the existing
`BrowserSessionManager`, against `data:` URLs only — the identical
pattern `tests/browser_test_support.py` already establishes for the whole
Browser Worker suite (*"No navigation to any real website, network
access… per Mission Brief 022's product-independence rule"*). This is not
new risk; it is the same headless, sandboxed Playwright launch every
existing Browser Worker test already performs on every run of this
repository's suite.

---

## 8 · Permission boundaries — the brief's two lists, enforced by absence

`permissions.py` carries `PERMITTED_OPERATIONS` and `FORBIDDEN_OPERATIONS`
as the brief's own eight and seven strings, verbatim, checked against the
brief text word-for-word by
`test_the_brief_permitted_list_is_carried_verbatim` /
`test_the_brief_forbidden_list_is_carried_verbatim`.

**The enforcement itself is structural, not a runtime gate.** There is no
`install()`, `uninstall()`, `elevate()`, `change_settings()`,
`modify_registry()`, `access_passwords()` or `inspect_conversations()`
method anywhere in `desktop/execution/` —
`test_no_forbidden_method_exists_anywhere_in_the_package` walks every
function definition in the package by AST and asserts none of ten
candidate names (the seven verbs plus three synonyms) exists. A method
that does not exist cannot be called by mistake, called with a gate
bypassed, or called before a gate runs — a stronger guarantee than a
runtime check that could itself have a bug.

Three more checks close the gap between *"no method exists"* and *"no
mechanism exists"*: `winreg`/`_winreg` are never imported (no registry
access at all, not even read-only); `ShellExecuteW`, `runas`,
`AdjustTokenPrivileges`, `IsUserAnAdmin` appear nowhere as an executable
identifier (no elevation path); and `pip install`, `winget install`,
`choco install`, `msiexec` never appear as text anywhere in the package
(no install surface, checked even more strictly than the identifier-only
guards elsewhere, because an install command could plausibly be
constructed as a plain string rather than a named call).

`test_desktop_executor_exposes_only_the_briefs_six_public_methods`
confirms `DesktopExecutor`'s entire public surface is exactly `execute`,
`focus`, `type`, `click`, `wait`, `close` — nothing extra was added to the
unified API beyond what the brief named.

---

## 9 · Recovery paths

Every backend failure is `BackendUnavailable` — a structural fact
(*"this mechanism cannot run at all here"*), never confused with an
ordinary operational failure (a click that lands on nothing, a window
that will not come to front, which are reported as `success=False`
without that exception). `TestRecoveryPaths` and
`TestEveryBackendUnavailableBranch` exercise every one of the sixteen
possible unavailable-backend combinations across all four backend types,
plus:

- **A platform-level operation failure is reported, not raised** — a
  `FakeWindowBackend` configured to fail `bring_to_front` specifically
  returns a structured `ExecutionResult`, distinct from the backend being
  entirely absent.
- **`ProcessExecutive.wait()` recovers from an application that never
  starts by reporting a timeout, never hanging** — the poll loop's
  `sleep` is injected, so the test asserts the correct honest failure
  without any real time passing.
- **`restart()` distinguishes a tolerable terminate failure from a real
  one** — *"the application was not running"* is absorbed and the launch
  proceeds; a genuine kill failure (the process refused to die,
  `taskkill` itself failing) is not swallowed and is returned directly —
  proven with a `FakeProbe` configured to fail the real kill command
  `CloseApplicationAction` issues.
- **A missing Playwright dependency is reported, not raised** — both via
  a full recovery-path test that replaces `_ensure_manager()` wholesale,
  and via `test_ensure_manager_itself_reports_a_genuinely_missing_
  playwright`, which blocks the real `import` (`sys.modules[...] = None`)
  to exercise `_ensure_manager()`'s own `except ImportError` branch
  directly rather than a stand-in for it.

---

## 10 · Structural guards, and the guards proven able to fail

| Guarantee | How it is enforced |
|---|---|
| No image/OCR library or call | §6 |
| No forbidden method exists | §8 |
| No registry access | `winreg`/`_winreg` never imported |
| No privilege elevation | four Win32 elevation identifiers never called/defined |
| No install surface | four install-command strings never appear as text |
| No second catalog/inventory | `desktop.catalog` not imported; `discover`/`discover_application`/`attribute_processes` never called |
| No second Operation Profile type | `ApplicationOperationProfile`, `ApplicationRecoveryPlan`, `DesktopCapabilityMatrix`, `Capability` (C25) declared nowhere here |
| No second Playwright driver | `sync_playwright`/`chromium.launch` absent from `browser.py` |
| No frozen package reachable | `foundation`, `kernel`, `ledger`, `coordinator`, `runtime_bridge`, `api` — none imported |
| No planning/orchestration surface reachable | `mission_control`, `planner`, `brain`, `orchestrator`, `runtime.*` (the Engine) — none imported, per the brief's own *"execution layer only"* |

**The guards were proven able to fail**, the same discipline every C22–C25
suite already applied. A throwaway module containing `import subprocess`,
`from master_agent.kernel import Kernel`, and `import winreg` was added
to the package and the suite re-run:

```
FAILED TestPermissionBoundaries::test_no_registry_module_is_imported
FAILED TestTheGuardsThemselves::test_subprocess_and_winreg_are_absent_even_from_prose
FAILED TestNoDuplication::test_no_frozen_package_is_imported
3 failed, 15 passed, 110 deselected
```

The file was deleted and the suite returned to 128 passing.

---

## 11 · Verification status — read this before trusting the real backend

**Exercised live, on this machine, in this session:**

- `Win32WindowBackend.enumerate()` and `.active()` — read-only. Returned
  278 real windows and correctly identified the active one (this
  session's own window, titled "Claude"). This is the one live check
  performed, and it is read-only in the same sense C24's own machine scan
  was.

**Not exercised live, by deliberate, disclosed decision:**

- `bring_to_front`, `minimize`, `maximize`, `restore`, `close` (window
  mutation)
- `type_text`, `press`, `hotkey` (keyboard input)
- `move`, `click`, `double_click`, `drag`, `scroll` (mouse input)
- `read`, `write`, `clear` (clipboard mutation)
- Every `ProcessExecutive`/`DesktopExecutor` call against a
  `RealSystemProbe`, after §1's incident

**Why:** an autonomous coding session driving the real mouse, keyboard, or
window state would act on whatever the operator is doing on their own
screen at that moment — a materially different risk from reading a
machine inventory or enumerating window titles, both of which observe
without acting. `win32_backends.py`'s own module docstring states this
plainly and names itself *"the one component of C26 that most needs a
human's first real run."*

**Coverage reflects this honestly rather than being inflated to hide
it:**

```
python -m pytest tests/test_desktop_execution.py --cov=master_agent.desktop.execution
  __init__.py             11 stmts   0 miss  100%
  backends.py             58 stmts   0 miss  100%
  browser.py              98 stmts   0 miss  100%
  clipboard.py            27 stmts   0 miss  100%
  executor.py             67 stmts   0 miss  100%
  keyboard.py             51 stmts   0 miss  100%
  mouse.py                44 stmts   0 miss  100%
  permissions.py           4 stmts   0 miss  100%
  process.py               47 stmts   0 miss  100%
  win32_backends.py      159 stmts 159 miss    0%
  window.py                74 stmts   0 miss  100%
```

**Every module a `Fake` backend could exercise is at 100%.
`win32_backends.py` — the real Win32 mechanism — is at 0%, and that
number is the honest answer, not a gap to explain away.** It was checked
for correctness by careful reading against the documented Win32 API
(`SendInput`, `EnumWindows`, `OpenClipboard`/`GlobalAlloc`, and their
documented structures and flags), and by the one read-only live check
above, but its mutating methods have not run against a real desktop by
anyone. This is recorded as the component's principal open risk, not
buried in a coverage percentage.

---

## 12 · Test evidence

```
python -m pytest tests/test_desktop_execution.py -q
  128 passed in ~5-10s

python -m ruff check src/master_agent/desktop/execution/ tests/test_desktop_execution.py
  All checks passed!
```

**Full suite: 5690 passed, 49 failed, 1 skipped (166s)** — up from C25's
5562 passed with the identical 49 pre-existing failures
(`FounderConsole.__init__()` rejecting a `memory` keyword argument, and
`launcher/boot.py:693` reading ambient `datetime.now()`, both sitting in
the uncommitted MB032–039 working tree, unrelated to and unmodified by
this component). All 128 new tests landed clean; nothing existing
regressed.

---

## 13 · Frozen components and existing execution surfaces

```
git diff --stat kalpavriksha-s1-c18.0 -- foundation kernel ledger coordinator
                                          runtime_bridge api
→ (empty)

git status --porcelain -- foundation kernel ledger coordinator runtime_bridge api
→ (empty)

git status --porcelain -- desktop/actions.py desktop/plugin.py desktop/probe.py
                            desktop/catalog.py desktop/inventory.py
                            environment/browser_session.py executor/actions/browser
→ (empty)
```

**Byte-identical to the frozen tag, and every existing execution surface
this component reuses is untouched.** Every file this brief delivers is
new.

---

## 14 · What this does not do, stated so it is not assumed

1. **No planning, orchestration, autonomy, reasoning, routing, OCR,
   vision, or AI conversation is built here.** §6 for OCR/vision
   specifically; §10 for the AST guard that keeps `mission_control`,
   `planner`, `brain`, `orchestrator` and the Runtime Engine unreachable.
2. **Nothing is wired to Mission Control.** `DesktopExecutor` is not an
   `Action`, is not registered on any `LocalExecutor`, and appears in no
   `PluginManifest`. It is a plain Python API a future caller —
   Kalpavriksha, per the brief's own framing, which does not exist in
   this repository — would invoke directly.
3. **No Kernel authorization is consulted.** This is deliberate and
   explicit in the brief (*"No Kernel redesign. No Runtime redesign."*):
   this layer trusts its caller to have already decided an operation is
   authorized, and performs the operation mechanically. Wiring this to
   the approval/authorization system C18's Runtime Bridge already
   established is future work, not attempted here.
4. **The real backend's mutating methods are unverified against a live
   desktop.** §11, stated as plainly as possible so it is not discovered
   by surprise.
5. **`DesktopExecutor()`'s defaults reach the real machine.** §1. This is
   consistent with `desktop.plugin.DesktopPlugin`'s own existing default
   and is not a new architectural decision, but it is now consequential
   in a new way — a launch was always one call away; type/click are now
   one call away too, once a real keyboard/mouse backend is passed.

---

*End of report. Working-directory evidence only. No commits, no tags, no
Rule 001 milestone declared.*
