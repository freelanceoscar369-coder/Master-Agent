# Desktop Executive Foundation 1.0

Status as of this session's work. This is a foundation report, not a
completion certificate — see §11 for what remains before the full 29-section
brief this work responds to can be called done.

## 1. What this is

The Desktop Executive (MB030) has real, working Win32 code for window
enumeration, process launch, keyboard/mouse input, and clipboard access —
built in an earlier, unlogged session (referenced in-repo as "C25"/"C26"/
"C27"). None of it was reachable from a founder's objective: `desktop/
actions.py`'s own docstring says so explicitly ("no click, no type, no
mouse... a later Desktop Interaction brief owns this"), and `kalpavriksha_
desktop.py`'s mission pipeline registered only `BrowserPlugin`, never
`DesktopPlugin`.

This work is that missing layer: verified window interaction Actions,
registered as real capabilities, wired into the one Founder Edition
composition root, with genuine OS-level bugs found and fixed along the way
by testing against the real desktop rather than trusting source review.

## 2. Architecture

```
 founder objective
        │
        ▼
 kalpavriksha_desktop.py::_build_mission_pipeline()
        │  registers DesktopPlugin alongside BrowserPlugin,
        │  same registry, same discover_executives(), same
        │  permission-grant loop, same PluginGateway wiring
        ▼
 DesktopPlugin (desktop/plugin.py)
        │  DESKTOP_ACTION_CLASSES (existing: launch/focus/close/inventory/
        │  process actions) with 3 names superseded by the verified layer,
        │  + DESKTOP_INTERACTION_ACTION_CLASSES (new, this session)
        ▼
 actions_interaction.py — VerifiedLaunchApplicationAction, VerifiedFocusWindowAction,
 VerifiedBringToFrontAction, ClickControlAction, TypeIntoWindowAction,
 ReadWindowTextAction, PressKeyAction, CloseWindowAction
        │  every action: resolve window (scoped to the one named app) →
        │  confirm responsiveness → check integrity boundary → act →
        │  observe again → compare against what was expected
        ▼
 execution/executor.py (DesktopExecutor) — the existing C26 unified API,
 gated on operations/knowledge.py's ApplicationOperationProfile per app
        │
        ├─ execution/window.py + win32_backends.py (WindowManager) — real
        │    EnumWindows/SetForegroundWindow/ShowWindow/PostMessageW
        ├─ execution/text_control.py (NEW) — classic-message text control
        │    resolution: EnumChildWindows + WM_GETTEXT/WM_SETTEXT/BM_CLICK
        ├─ perception/integrity.py (NEW) — UIPI/elevation boundary check:
        │    OpenProcessToken + GetTokenInformation
        ├─ perception/win32_probe.py (existing) — SendMessageTimeoutW-based
        │    responsiveness probe, reused unchanged
        └─ execution/keyboard.py, mouse.py, process.py (existing, reused)
```

## 3. Components reused vs. created

**Reused, unmodified in logic:** `execution/window.py`, `execution/
process.py`, `execution/keyboard.py`, `execution/mouse.py`, `execution/
backends.py`, `perception/win32_probe.py`, `operations/*` (C25 profiles),
`desktop/actions.py` (byte-for-byte, per its own docstring).

**Created this session:**
- `desktop/perception/integrity.py` — integrity-level/elevation detection.
- `desktop/execution/text_control.py` — classic Win32 message-based
  control targeting and text I/O ("UIA-lite" — see §7).
- `desktop/actions_interaction.py` — the 8 verified interaction Actions.

**Modified:**
- `desktop/plugin.py` — registers the interaction layer under 3 existing
  names (`launch_application`, `focus_window`, `bring_to_front`) plus 5 new
  ones, without touching `actions.py`.
- `desktop/execution/executor.py` — `execute()` now also resolves
  Store/AppX launch commands from the inventory (via the already-resolved
  profile key, not a second catalog import); `execute()`/`focus()` use
  `read_versions=False` for their fast path; `type()`/`click()` restored
  to `_require_automatable()` (a pre-existing regression from earlier in
  this session that dropped the `NOT_AUTOMATABLE` refusal — fixed as part
  of getting the test suite green, since a codebase this deep in a "one
  session" development style accumulates this kind of regression fast).
- `desktop/inventory.py` — `discover()` no longer calls the unused
  `get_uninstall_apps()` (its result was never read — three registry-query
  subprocesses for nothing on every scan) and gates `get_store_apps()`
  behind `read_versions` (see §6).
- `desktop/catalog.py` — added a Notepad entry with `version_args=None`
  (no CLI version flag exists; any argument opens a real window).
- `desktop/operations/knowledge.py` — added Notepad's operation profile.
- `desktop/execution/win32_backends.py` — `bring_to_front()` now uses
  `AttachThreadInput` (see §8).
- `kalpavriksha_desktop.py` — registers `DesktopPlugin` in
  `_build_mission_pipeline()`, mirroring `BrowserPlugin`'s exact
  composition (registry, permission grants, gateway, capability contracts).

## 4. Permission model

Unchanged. Every interaction Action declares its own `risk_tier`
(`REVERSIBLE_WRITE` for launch/focus/click/type/press/close,
`READ_ONLY` for read_text) and `permission_category`. The composition
root's pre-grant loop (`GrantScope.ALWAYS_FOR_CAPABILITY`) is extended to
cover Desktop's capabilities the same way it already covers Browser's —
`PermissionSystem.check()` itself still refuses to honor that grant for an
`IRREVERSIBLE` action regardless, so this changes nothing about what an
IRREVERSIBLE Desktop action (there are none in the interaction layer
today) would require.

## 5. Observation, targeting, action, verification, recovery

- **Observation** is scoped: `_resolve_window()` looks up the one named
  application's running processes, then that process's window — never a
  desktop-wide crawl.
- **Targeting** is by identity: window handle + process id for windows;
  child-control class name (falling back to a text substring) for
  controls — never a screen coordinate as the primary path.
- **Action** never starts until the target is confirmed: responsiveness
  (bounded `SendMessageTimeoutW` probe) and integrity boundary
  (`IntegrityGuard`) are both checked before any input is sent, and focus
  is confirmed (`_focus_and_confirm`, §8) before typing or clicking.
- **Post-action verification** is real, not assumed: `TypeIntoWindowAction`
  reads the control back after writing; `VerifiedLaunchApplicationAction`
  re-locates the window and separately confirms foreground; `CloseWindow
  Action` polls (bounded) for the window's disappearance.
- **Recovery** is currently limited to the bounded retry loops already
  built into focus-confirmation (§8) and the launch window-locate poll.
  Retry-on-stale-element and escalate-on-unknown-modal (§9's fuller
  brief) are not built — see §11.

## 6. A real performance bug found and fixed

`inventory.py::discover()` called `probe.get_store_apps()`
(`powershell -Command "Get-AppxPackage | ..."`) and `probe.
get_uninstall_apps()` (three separate registry-query `powershell` calls)
**unconditionally, on every single inventory scan**, regardless of the
existing `read_versions` fast/slow-path flag. `get_uninstall_apps()`'s
result was never even read.

Effect, measured live: launching Notepad went through `execute()` →
`process.wait()` → `context.refresh()`, each independently re-running
`discover()` — **~64 seconds** for a golden-path launch that should be
near-instant. Root-caused with per-stage timing instrumentation, fixed by
gating `get_store_apps()` behind `read_versions` and removing the dead
`get_uninstall_apps()` call. Same golden path afterward: **~7 seconds** to
launch, **~14.5 seconds** total for launch+type+read-back.

## 7. Known, disclosed gap: text control targeting is not UIA

Nothing in this repository speaks `IUIAutomation` (COM) today — no
`pywinauto`, no `comtypes`. Rather than stand up a COM accessibility
wrapper under this session's time pressure (real risk: fragile, undertested
apartment-threading/element-caching code), `text_control.py` targets
classic Win32 controls by identity (child HWND + class name) and reads/
writes through `WM_GETTEXT`/`WM_SETTEXT`/`BM_CLICK` — the same messaging
contract every Win32 `Edit`/`Static`/`Button` control has answered since
Windows 3.x, and confirmed live to still work against Windows 11's
WinUI3-hosted Notepad (`NotepadTextBox` class).

This is a genuine, disclosed deviation from the brief's stated UIA
preference. It works for the golden paths tested here; it will not target
a control that ignores classic window messages (e.g. most modern
WinUI3/UWP apps beyond Notepad's specific control). Building real UIA
support is the clearest concrete next step for this foundation.

## 8. Two real Win32 bugs found only by testing live

1. **Cross-module `ctypes` singleton mutation.** `ctypes.windll.user32` is
   one shared, process-wide object. `text_control.py` originally set
   `.argtypes`/`.restype` directly on `user32.SendMessageTimeoutW` —
   which silently changed what `perception/win32_probe.py`'s own,
   independently-typed call to the *same* function object saw, breaking
   an unrelated, already-working responsiveness probe elsewhere in the
   package (`ctypes.ArgumentError: expected LP_c_ulonglong instance
   instead of pointer to c_ulong`). Fixed by binding independent function
   pointers via `ctypes.WINFUNCTYPE(...)(("Name", user32))` instead of
   mutating the shared function object.

2. **`SetForegroundWindow` refused by Windows' anti-focus-stealing lock.**
   `bring_to_front()`'s bare `SetForegroundWindow(handle)` succeeded
   immediately after this process's own `execute()` launched a window (the
   OS grants the launching process a one-time allowance) but failed
   silently on any later, independent focus call once foreground had moved
   elsewhere — confirmed live via a real "Focus Chrome" golden-path
   failure. Fixed with `AttachThreadInput`, Microsoft's own documented
   workaround: briefly share input state with whichever thread currently
   holds the foreground, call `SetForegroundWindow`, detach immediately.

Both were invisible from source review alone; both were found by running
real actions against the real desktop and treating a wrong result as a
bug, not an acceptable flake.

## 9. A real test-environment contamination found and cleared

Windows 11 Notepad persists session-restore state
(`%LOCALAPPDATA%\Packages\Microsoft.WindowsNotepad_.../LocalState/
{TabState,WindowState}`) across process kills. Dozens of stale tabs from
unrelated earlier testing (this session and prior ones) were silently
reopening on every launch, polluting window resolution — the golden-path
launch action picked an arbitrary restored tab (once, a minimized one)
instead of the freshly-created window. This is an environment artifact,
not a product bug; cleared by removing the stale `TabState`/`WindowState`
files so golden-path testing reflects a clean launch.

## 10. Golden-path evidence (real, against the live desktop)

| Path | Result | Evidence |
|---|---|---|
| A — Open Chrome | **PASS** | Real `chrome.exe` (7 processes), visible window "Google Chrome", `foreground_confirmed: True` |
| C — Open Notepad, type, verify | **PASS** | Real `notepad.exe`, `NotepadTextBox` control resolved by class name, `WM_SETTEXT` + read-back both returned `"Hello Kalpavriksha"` |
| E — What applications are running? | **PASS** | Real process enumeration, 98 processes, `chrome.exe` correctly reported present |
| F — Focus Chrome | **PASS** (after the `AttachThreadInput` fix in §8) | Foreground window confirmed as the real Chrome window after 3 bounded focus attempts |
| B — Chrome navigate + verify title | **NOT RUN** this session | Browser Worker's own navigate/verify path predates this work and was not re-exercised here |
| D — Open Cursor | **BLOCKED** | Cursor is not installed on this machine (`%LOCALAPPDATA%\Programs\cursor\Cursor.exe` absent) — cannot produce real evidence without fabricating it |

## 11. Remaining P0 gaps — honestly, not glossed over

- **Modal/popup monitor** (brief §15) — not built this session.
- **Real UIA-based semantic targeting** — see §7; today's classic-message
  approach is a scoped, working, but non-UIA substitute.
- **Structured local recovery beyond bounded retry** — retry-on-stale-
  element and escalate-on-unknown-modal are not implemented.
- **Golden path B** — not re-verified this session (pre-existing, not
  newly broken).
- **Golden path D** — blocked by this machine not having Cursor installed.
- **Real packaged acceptance** — rebuild + install + golden paths against
  the installed executable was not performed; this requires the founder
  to run the installer (Claude cannot self-elevate/install).
- **Full automated test coverage** of every subsystem named in the brief
  (integrity checks, UIA normalization, modal handling, browser visible
  mode, capability registration end-to-end) is partial: `tests/
  test_desktop_execution.py` (128 tests, all passing) covers window/
  process/keyboard/mouse/clipboard/executor logic against fakes; the new
  interaction layer, integrity guard, and text control resolver have live
  manual verification (§10) but no dedicated automated test file yet.
- **A pre-existing, unrelated circular import** was found
  (`master_agent.communication` ↔ `founder_edition.boot`, via a
  `founder_runtime/wiring.py → founder_edition.desktop_layer` edge added
  earlier in this session's uncommitted history, not by this Desktop
  Executive work). It blocks `tests/test_desktop_shell.py` from
  collecting standalone but does not block `kalpavriksha_desktop.py`
  itself from importing. Left unfixed: `founder_runtime`/`communication`
  internals are outside this mission's scope per its own DO-NOT-CHANGE
  list, and diagnosing/fixing it is real, separate work.
