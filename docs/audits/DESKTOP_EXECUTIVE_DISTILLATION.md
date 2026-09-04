# Desktop Executive Distillation

## 1. Executive Conclusion

The Kalpavriksha Desktop Executive architecture exists as a layered, profile‑gated system that separates knowledge (what can be done) from execution (how to do it). The current implementation provides a solid foundation for Windows automation but suffers from fragmented perception, missing UI Automation integration, and duplicated low‑level input handling. The distillation effort should unify perception around a semantic observation hierarchy (UI Automation → browser DOM → screenshot/OCR → low‑level input), consolidate action routing through DesktopExecutor, and ensure verification re‑uses the existing Evidence/Verdict pipeline. No new execution paths are needed; the focus is on wiring proven components and removing stale duplication.

## 2. Current Kalpavriksha Desktop Executive Map

| Component | Status | Evidence |
|-----------|--------|----------|
| DesktopLayer | NOT FOUND | No file or symbol named `DesktopLayer` found in repository. |
| DesktopExecutor | EXISTS + WORKING | `/d/MasterAgent/src/master_agent/desktop/execution/executor.py` – unified API with profile gating, routes to WindowManager, KeyboardController, MouseController, ProcessExecutive, BrowserExecutive, ClipboardExecutive. |
| DesktopExecutive / DesktopExecutiveV2 | EXISTS + WORKING | `/d/MasterAgent/src/master_agent/desktop/operations/executive.py` – read‑only facade holding OperationKnowledgeBase (profiles, recovery plans, workflows, matrix). Exposes `recommend()` and `profile()`. |
| ProcessExecutive | EXISTS + WORKING | `/d/MasterAgent/src/master_agent/desktop/execution/process.py` – wraps `LaunchApplicationAction`, `CloseApplicationAction`, `IsRunningAction`, adds `wait()` based on process‑level readiness. |
| BrowserExecutive | EXISTS + WORKING | `/d/MasterAgent/src/master_agent/desktop/execution/browser.py` – delegates to BrowserSessionManager (Playwright), provides `open_url`, `new_tab`, `focus_browser`, etc. |
| LaunchApplicationAction | EXISTS + PARTIAL | `/d/MasterAgent/src/master_agent/desktop/actions.py` – launches catalogued, installed applications via `desktop.inventory`. |
| MouseController | EXISTS + WORKING | `/d/MasterAgent/src/master_agent/desktop/execution/mouse.py` – low‑level mouse movement/click via `cua‑driver` (Windows) or platform fallbacks. |
| KeyboardController | EXISTS + WORKING | `/d/MasterAgent/src/master_agent/desktop/execution/keyboard.py` – low‑level typing via `cua‑driver`, clipboard integration. |
| Desktop inventory/probe | EXISTS + WORKING | `/d/MasterAgent/src/master_agent/desktop/inventory.py` – machine scan (installed apps, processes), version extraction, store/appx discovery. |
| Knowledge Executive / knowledge base | EXISTS + WORKING | `/d/MasterAgent/src/master_agent/desktop/operations/knowledge.py` – defines PROFILES, RECOVERY_PLANS, WORKFLOWS, MATRIX (DesktopCapabilityMatrix). |
| Permission system | EXISTS + WORKING | Integrated via `PermissionSystemGate` in `DesktopExecutor.__init__` (see `/d/MasterAgent/src/master_agent/desktop/execution/executor.py` lines 76‑78). |
| Observation/verifier mechanisms | EXISTS + PARTIAL | Perception layer under `/d/MasterAgent/src/master_agent/desktop/perception/` includes `win32_probe.py`, `windows.py`, `state.py`, `readiness.py`, `engine.py`, `browser.py`, etc. Uses `ObservationCheck`, `ExpectedOutcome`, `Evidence`, `Verdict` from verification package. |
| Mission/plugin registration | EXISTS + WORKING | Desktop plugin registers via `master_agent/desktop/plugin.py` – exposes desktop capabilities to Mission Control (see `discover_executives` in `kalpavriksha_desktop.py`). |

**Stale/Duplicated components:** 
- Multiple low‑level input paths (mouse/keyboard) exist both in `desktop/execution/*` and in perception files (`win32_probe.py` uses `ctypes` for mouse/keyboard). 
- Duplicate window enumeration: `WindowManager` (`window.py`) vs. perception `win32_probe.py` (`get_windows()`). 
- Duplicate process attribution: `inventory.py` (`attribute_processes`) vs. `ProcessExecutive.is_running()`.

## 3. External Windows Automation Evidence

### A. Microsoft UI Automation (UIA)
- UIA provides programmatic access to the UI element tree, control types (Button, Edit, ComboBox, etc.), automation IDs, names, control patterns (Invoke, Value, Selection, ExpandCollapse, etc.), and events (focus changed, property changed, structure changed). 
- It works across Win32, WinForms, WPF, and UWP/Store apps when UIA support is enabled. 
- Evidence from research notes: `day 0 master agent.txt` lines 1419‑1420, 1564, 1578, 1609, 1715, 1920‑1922, 1927, 2044‑2046, 2079, 2083, 2129, 2286, 2290, 2417. 
- UIA is the recommended first semantic observation layer for Windows desktop automation (see research hierarchy: UIA → browser DOM → screenshot/OCR → mouse/keyboard).

### B. pywinauto
- Python library wrapping UIA (and legacy Win32) with higher‑level idioms: element discovery by auto_id, title, control_type; support for patterns; input methods; waiting for conditions. 
- Strengths: mature, cross‑framework, integrated with pytest/allure. 
- Limitations: adds another abstraction layer; may introduce latency; not needed if we wrap UIA directly via `comtypes` or `ctypes`. 
- Research notes indicate pywinauto could be leveraged for browser chrome where DOM insufficient (`P0_BROWSER_EXECUTIVE_EXPERT_OPERATOR_GAP_MATRIX.md` line 68). 
- Recommendation: use UIA directly via existing `UiaAutomationBridge` (see perception files) rather than adding a new dependency.

### C. PyAutoGUI / low‑level input
- Useful when UIA cannot expose a control (custom drawn, inaccessible, or legacy). 
- Provides screenshot, pixel color, mouse movement, keyboard typing. 
- Currently handled by `MouseController`/`KeyboardController` via `cua‑driver` (Windows) and fallback mechanisms. 
- Should remain as the fallback layer in the perception hierarchy.

### D. Browser automation
- Existing Playwright layer via `BrowserSessionManager` (`environment/browser_session.py`) and `BrowserExecutive`. 
- Correct hierarchy: UI Automation (for desktop app chrome, dialogs) → browser DOM/Playwright (for web content) → screenshot/OCR → mouse/keyboard. 
- Do not replace one mechanism with another; layer them by capability.

## 4. Distilled Architecture

**Proposed core abstractions (already justified by existing code):**
- `DesktopObservation` – returns a generic dict of UI state (already embodied by perception engine output, e.g., `Win32Probe.capture_observation_dict()`). 
- `DesktopElement` – a handle to a UIA element (already present in `uia_control.py` via `UiaAutomationBridge`). 
- `DesktopAction` – an action typed by capability (click, type, etc.) that routes through `DesktopExecutor`. 
- `DesktopSession` – not needed; DesktopExecutor is stateless per‑call, using the OperationKnowledgeBase for profiles. 
- `DesktopVerifier` – already exists as `Verifier` subclasses (e.g., `BrowserVerifier` would be added for UIA). 

**Data flow:**
1. Founder request → Intent → Planner → MissionPlan (with Steps referencing capabilities like `desktop.click`, `desktop.type`). 
2. Mission Control dispatches to Desktop Executive capability (already registered via `desktop.plugin.DesktopPlugin`). 
3. Desktop Executive receives the operation, looks up the application profile in `DesktopExecutiveV2.profile()`, validates automatable, then delegates to the appropriate controller (Mouse, Keyboard, Process, Window, Browser, Clipboard). 
4. Perception layer (Win32 probe, browser probe) captures pre‑ and post‑conditions as `Evidence` using `ExpectedOutcome` from the Planner. 
5. Verifier computes `Verdict`; Reporter builds founder‑facing report. 
6. ExecutionStatus updates via event bus (already wired in `kalpavriksha_desktop.py`). 

## 5. Capability Matrix

| Capability | Current Kalpavriksha | Proven external mechanism | Gap | Recommended owner |
|------------|---------------------|----------------------------|-----|-------------------|
| enumerate windows | EXISTS + PARTIAL (`WindowManager.list_windows()` via Win32 API) | UIA `TreeWalker`, `FindAll` | No UIA‑based enumeration; relies on Win32 GUIINFO | Perception (`win32_probe.py`) |
| inspect active window | EXISTS + PARTIAL (`WindowManager.get_foreground_window()`) | UIA `GetFocusedElement` + container | No UIA‑based focus inspection | Perception |
| inspect controls | EXISTS + PARTIAL (`UiaAutomationBridge` in perception) | UIA `IUIAutomation`, `IUIAutomationElement` | Already present but not fully integrated into action flow | Perception → DesktopExecutor |
| find element | EXISTS + PARTIAL (`UiaAutomationBridge.find()`) | UIA `FindFirst`, `FindAll` | Present; needs to be used by actions | Perception → DesktopExecutor |
| click | EXISTS + WORKING (`MouseController.click`) | UIA `Invoke` pattern | Low‑level click works but lacks semantic targeting | MouseController (fallback), prefer UIA Invoke via new action |
| type text | EXISTS + WORKING (`KeyboardController.type`) | UIA `SetValue` (Value pattern) | Low‑level typing works; lacks semantic field targeting | KeyboardController (fallback), prefer UIA SetValue |
| read text/value | EXISTS + PARTIAL (`UiaAutomationBridge.get_text()`) | UIA `Value` pattern, `LegacyIAccessible.Value` | Present; needs verification integration | Perception |
| invoke control | EXISTS + PARTIAL (via `UiaAutomationBridge.invoke()` for certain patterns) | UIA `Invoke` pattern | Present but not exposed as a first‑class action | Perception → DesktopExecutor |
| focus window | EXISTS + WORKING (`WindowManager.focus_process`) | UIA `SetFocus` | Works at process level; not element level | WindowManager (fallback), prefer UIA SetFocus |
| launch application | EXISTS + WORKING (`ProcessExecutive.launch`) | N/A (same) | None | ProcessExecutive |
| switch window | EXISTS + WORKING (via focus) | UIA `SetFocus` on element’s window | None | WindowManager |
| keyboard input | EXISTS + WORKING | UIA `SendKeys` (via bridge) | Low‑level works; UIA alternative available | KeyboardController |
| mouse input | EXISTS + WORKING | UIA mouse via element click | Low‑level works; UIA alternative available | MouseController |
| screenshot | EXISTS + WORKING (`perception/engine.py`?) | N/A (same) | None | Perception engine |
| browser navigation | EXISTS + WORKING (`BrowserExecutive.open_url`) | N/A (same) | None | BrowserExecutive |
| DOM observation | EXISTS + WORKING (`BrowserExecutive` via Playwright) | N/A (same) | None | BrowserExecutive |
| process observation | EXISTS + WORKING (`ProcessExecutive.is_running`) | N/A (same) | None | ProcessExecutive |
| post‑action observation | EXISTS + PARTIAL (perception captures before/after) | UIA events (focus changed, property changed) | Need to wire UIA events into verification loop | Perception |
| verification | EXISTS + WORKING (`Verification.Verifier`) | UIA property change events for waiting | None | Verification |
| recovery | EXISTS + PARTIAL (recovery plans in knowledge) | UIA‑based retries (stale element) | Need UIA‑specific recovery (e.g., refresh element) | DesktopExecutiveV2 (recovery plans) |
| permission checking | EXISTS + WORKING (`PermissionSystemGate`) | N/A (same) | None | DesktopExecutor |
| sensitive application detection | EXISTS + PARTIAL (catalog marks third_party, privacy) | UIA `IsPassword` property | None | DesktopExecutor (profile) |

## 6. Observation Hierarchy

1. **UI Automation/accessibility structure** – first choice for desktop apps; provides semantic element tree, names, automation IDs, control types, patterns. 
2. **Browser DOM/semantic structure** – for web content; use Playwright to access page frames, iframes, shadow DOM. 
3. **Application/window/process state** – window title, process name, executable path, window rectangle (fallback when UIA unavailable). 
4. **Screenshot/OCR** – when UIA/DOM cannot expose a control (custom drawing, canvas, legacy). Use OCR only if text is required and UIA/DOM fails. 
5. **Mouse/keyboard coordinate interaction** – absolute last resort; only when no semantic target exists. 

**Implementation:** 
- Extend `Win32Probe` (`/d/MasterAgent/src/master_agent/desktop/perception/win32_probe.py`) to return a unified observation dict that includes UIA element properties when available, otherwise Win32 fallbacks. 
- Ensure `DesktopExecutor` actions consult this observation for pre‑conditions (e.g., `IsEnabled`) and use UIA patterns for execution when the target element supports them. 
- For browser content, reuse `BrowserExecutive` and its session; perception should delegate to browser probe when `environment` is `browser`. 

## 7. Action Hierarchy (ranked by importance for v1)

**P0 (must have for golden path):**
- LaunchApplication (already works) 
- FocusWindow (bring app to front) 
- Click (mouse coordinate – works now; later add UIA Invoke) 
- TypeText (keyboard coordinate – works now; later add UIA SetValue) 
- ReadValue (UIA/get_text) 
- WaitForCondition (poll UIA/DOM/process state) 

**P1 (important gaps):**
- DoubleClick (extend MouseController) 
- PressKey (single key, e.g., Enter) 
- Select (combobox, list) 
- Scroll (wheel or scroll bar) 
- CloseWindow (already via terminate) 
- MoveWindow (via Win32 API) 
- MouseMove (already) 
- Drag (extend MouseController) 

**P2 (future enhancements):**
- WaitForCondition with timeout and polling interval (already in `wait()` but could be generalized) 
- Get/Set clipboard (already via ClipboardExecutive) 
- File dialog handling (specialized) 
- Toast/notification detection 

## 8. Verification Model

- Each Step in a MissionPlan carries an `ExpectedOutcome` (list of `ObservationCheck`). 
- After an Action executes, the Verifier (subclassed per capability) captures a fresh observation dict via `capture_observation_dict()` (currently implemented for browser, needs UIA implementation). 
- `evaluate_checks()` compares observation against expected, returns `Verdict` and `CheckResult`s. 
- Evidence is built (`worker`, `environment`, `observation`, `expected`, `verdict`, `check_results`). 
- Reporter uses `Evidence.verdict` to generate founder‑facing report (see `brain/reporter.py`). 
- No new verifier needed; add a `DesktopVerifier` (`/d/MasterAgent/src/master_agent/verification/desktop_verifier.py`) that subclasses `Verifier` and implements `capture_observation_dict()` using the unified perception engine (UIA first). 
- This integrates with the existing verification architecture; no duplication.

## 9. Recovery Model

Local action recovery (within DesktopExecutor) should:
- **Element not found**: retry with re‑lookup (stale element) – use profile’s `retry_interval` and `max_attempts` from knowledge base (already in `ApplicationOperationProfile`). 
- **Stale UI**: re‑capture observation before retrying. 
- **Focus moved**: refocus target window via `WindowManager.focus_process` before acting. 
- **Window disappeared**: treat as failure; surface via `ExecutionResult` error (application not running). 
- **Action timeout**: already enforced by `DesktopExecutor.wait()` (process‑level) and perception timeouts. 
- **Application launch failure**: `ProcessExecutive.launch` returns failure; DesktopExecutor profiles can mark `launchable=False`. 
- **Accessibility tree unavailable**: fall back to screenshot/OCR or low‑level input (already in perception hierarchy). 
- **Browser DOM unavailable**: fall back to browser screenshot/OCR via `BrowserExecutive` (already handled). 

Recovery should **not** involve strategic re‑planning; that is the Brain’s responsibility. 
All recovery logic lives in `DesktopExecutiveV2.recovery_plans` (see `/d/MasterAgent/src/master_agent/desktop/operations/knowledge.py`).

## 10. Security / Permission Model

- **LOW RISK**: enumerate windows, inspect titles, read accessible text, browser navigation – gated by default `ALWAYS_FOR_CAPABILITY` grant in `kalpavriksha_desktop.py` (lines 224‑228) for reversible actions. 
- **MEDIUM**: launch applications, type text, file operations – require `IRREVERSIBLE` or explicit founder approval via `PermissionSystemGate` (ADR‑0009). 
- **HIGH**: passwords, banking, trading terminals, credential stores, destructive OS operations – must be marked `requires_approval=True` in provider profile (AI Capability Broker) or `requires_approval=True` in DesktopExecutive operation profile (C25). 
- The existing `PermissionSystemGate` and `FounderApprovalGate` (MB028.1) already enforce this; no new permission system needed. 
- DesktopExecutive must never bypass `profile()` check; every named‑application method calls `_profile_or_refusal()` (executor.py lines 85‑99). 

## 11. Duplicated / Competing Components

| Component | Status | Action |
|-----------|--------|--------|
| Low‑level mouse/keyboard (multiple implementations) | STALE / DUPLICATED | Keep `cua‑driver`‑based `MouseController`/`KeyboardController` as the canonical low‑level path; remove duplicate `ctypes`/`win32api` calls in perception files (e.g., `win32_probe.py` `mouse_event`, `keybd_event`). |
| Window enumeration | STALE / DUPLICATED | Keep `WindowManager` (`window.py`) as the canonical source; deprecate `win32_probe.py.get_windows()` in favor of calling `window_manager.list_windows()`. |
| Process attribution | STALE / DUPLICATED | Keep `inventory.py.attribute_processes` as the source of truth; remove duplicate logic in `ProcessExecutive` (if any). |
| UIA bridge perception | EXISTS + PARTIAL | Keep `UiaAutomationBridge` (`perception/uia_control.py`); ensure it is the single source for UIA interaction; do not duplicate in perception engine. |
| Browser session handling | EXISTS + WORKING | Keep `BrowserSessionManager` and `BrowserExecutive`; no duplication. |
| Clipboard handling | EXISTS + WORKING | Keep `ClipboardExecutive`; no duplication. |

**DO NOT TOUCH** (frozen per founder constraints): 
- `kalpavriksha_desktop.py` (composition root) – only add `runtime.start_background()` and one‑current‑mission gate (see fire‑and‑forget reconciliation). 
- `src/master_agent/missions/execution_status.py` – ExecutionStatus contract must remain unchanged except for the result/message gap (separate concern). 
- `src/master_agent/broker/*` – AI Capability Broker is frozen. 
- `src/master_agent/ai_infrastructure/*` – core AI infrastructure is frozen. 
- `master_agent/desktop/plugin.py` – desktop plugin registration is frozen. 

## 12. P0 Launch Blockers

1. **Missing UIA integration in action execution** – current `MouseController.click` and `KeyboardController.type` use low‑level input; no semantic targeting via UIA/Value/Invoke patterns. 
2. **Perception observation not wired to verification** – no `DesktopVerifier` that uses UIA to produce `Evidence` for desktop actions. 
3. **One‑current‑mission gate absent** – DesktopExecutor accepts new missions while one is running, risking concurrency issues (see fire‑and‑forget reconciliation). 

These three blockers prevent a reliable golden path (e.g., “Open Chrome” → launch → focus → verify title) because verification cannot trust that the action hit the intended semantic target.

## 13. P1 Gaps

1. **UIA‑based action alternatives** – lack of first‑class UIA Invoke/SetValue actions forces reliance on coordinates. 
2. **Stale element recovery** – knowledge base recovery plans exist but are not universally applied to UIA actions. 
3. **Browser‑desktop handoff** – no clear protocol for when UIA fails (e.g., browser chrome) and perception should fall back to browser DOM. 
4. **Screenshot/OCR integration** – perception engine already captures screenshots but OCR is not hooked; needed for controls inaccessible to UIA/DOM. 
5. **Verbose logging for debugging** – missing trace of UIA property values for diagnosis. 

## 14. P2 Future Work

1. **Accessibility events (UIA)** – subscribe to focus changed, property changed to drive smarter waiting. 
2. **Multi‑monitor support** – ensure window coordinates are absolute. 
3. **Internationalization (I18N)** – UIA supports localization; verify that text checks work across languages. 
4. **Custom UIA plugins** – for legacy or custom controls that expose bespoke patterns. 
5. **Performance profiling** – cache UIA lookups per session where safe. 

## 15. Recommended Implementation Order

1. **Add one‑current‑mission gate** to `kalpavriksha_desktop.py::_submit_objective()` (check `status.terminal_state` before accepting new objective). 
2. **Implement DesktopVerifier** (`verification/desktop_verifier.py`) using unified perception (UIA first). 
3. **Wire UIA Invoke/SetValue actions** into `DesktopExecutor` – add methods `uiaclick(application, element_locator)` and `uitype(application, element_locator, text)` that use `UiaAutomationBridge` when the element supports the pattern, otherwise fall back to mouse/keyboard. 
4. **Update perception engine** to prefer UIA element properties in observation dict; expose a method `get_element_observation(locator)` that returns a dict of UIA properties (name, automationid, controltype, value, enabled, etc.). 
5. **Add recovery plans** for UIA‑specific failures (stale element, invalidated element) in `knowledge.py`. 
6. **Add screenshot/OCR fallback** in perception for when UIA returns no element or is inaccessible. 

## 16. Exact Files/Components to Build or Modify

- `/d/MasterAgent/kalpavriksha_desktop.py` – add `runtime.start_background()` and one‑current‑mission gate. 
- `/d/MasterAgent/src/master_agent/verification/desktop_verifier.py` – new file. 
- `/d/MasterAgent/src/master_agent/desktop/execution/executor.py` – add UIA‑based click/type methods (or extend existing). 
- `/d/MasterAgent/src/master_agent/desktop/perception/engine.py` – enhance to return UIA‑rich observation. 
- `/d/MasterAgent/src/master_agent/desktop/operations/knowledge.py` – ensure recovery plans cover UIA actions. 
- `/d/MasterAgent/src/master_agent/desktop/perception/uia_control.py` – verify `UiaAutomationBridge` provides needed patterns (Invoke, Value, etc.); add if missing. 
- `/d/MasterAgent/src/master_agent/desktop/execution/window.py` – ensure `focus_process` works with UIA‑found window handles (if needed). 
- `/d/MasterAgent/src/master_agent/desktop/execution/process.py` – no change needed. 
- `/d/MasterAgent/src/master_agent/desktop/execution/browser.py` – no change needed. 

## 17. External Sources and Reusable Patterns

- **Microsoft UI Automation documentation** (https://learn.microsoft.com/windows/win32/winauto/entry-uiauto-win32) – authoritative source for control patterns, events, property IDs. 
- **`comtypes` client generation** – already used in perception (`win32_probe.py` line 20: `comtypes.client.GetModule("UIAutomationCore.dll")`). 
- **Python‑UIAutomation‑for‑Windows** – open‑source wrapper referenced in research; can be inspected for patterns but not adopted as dependency. 
- **pywinauto** – reference for high‑level idioms (element finding, waiting) but not to add as dependency. 
- **Existing perception files** – `/d/MasterAgent/src/master_agent/desktop/perception/win32_probe.py`, `/d/MasterAgent/src/master_agent/desktop/perception/windows.py`, `/d/MasterAgent/src/master_agent/desktop/perception/state.py` provide reusable patterns for process/window state extraction. 
- **Verification evidence patterns** – `/d/MasterAgent/src/master_agent/verification/evidence.py` and `evaluator.py` show how to build `ObservationCheck`, `ExpectedOutcome`, `Verdict`. 

## FIRST BUILD

**Single smallest implementation that moves us materially toward a genuinely working Desktop Executive:**

> **Add a one‑current‑mission gate in `kalpavriksha_desktop.py::_submit_objective()`** that calls `status.terminal_state()` (from ExecutionStatus) before accepting a new objective, returning a refusal (`"a mission is already running"`) if true.

**Why this is the first build:**
- It requires zero new dependencies or perception changes. 
- It uses already‑wired components (ExecutionStatus, mission_control). 
- It directly addresses a P0 launch blocker (concurrent mission risk) that would undermine any subsequent action‑level work. 
- It is a minimal, localized change (≈10 lines) that can be verified by attempting to submit two objectives in quick succession and observing the second is refused. 
- Once this gate is in place, further work on UIA actions and verification can proceed safely knowing only one mission will be active at a time.

After this gate is verified, the next step would be to implement `DesktopVerifier` and wire UIA‑based actions, but the one‑current‑mission gate is the foundational blocker that must be resolved first.