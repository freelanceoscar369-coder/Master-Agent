# KALPAVRIKSHA P0 — EXPERT HUMAN COMPUTER OPERATOR GAP MATRIX

## 1. Executive conclusion

The current system does NOT satisfy the P0 vision of an EXPERT HUMAN COMPUTER USER. While the Desktop Executive provides basic application discovery, launch, and closure capabilities, it lacks the core computer-use abstraction of mouse and keyboard interaction, screen observation, and closed-loop verify-recover cycles. The system is currently limited to application-level operations (launch/close) without the ability to interact with application UIs via generic input or observe screen state. The foundational architecture for a Universal Executive Operator exists (via the DesktopExecutor and related components), but the specific capabilities for expert-level human-computer interaction (mouse movement, clicking, typing, screen observation, verification, and recovery) are missing or insufficient.

## 2. Existing architecture

The actual current chain for desktop operations is:

Founder Runtime → DesktopTask → DesktopOperator → DesktopStateMachine → DesktopExecutor → 
  ├─ WindowManager
  ├─ KeyboardController
  ├─ MouseController
  ├─ ClipboardExecutive
  ├─ ProcessExecutive
  └─ BrowserExecutive (for browser-specific operations)

The DesktopExecutor composes these components and gates every operation through DesktopExecutiveV2.profile() to ensure the application has a known operation profile. The DesktopExecutor is the unified API for desktop operations, but its current methods (execute, focus, type, click, wait, close) are limited to application-level operations and do not support arbitrary mouse/keyboard coordinates or screen observation.

Underlying the DesktopExecutor are:
- MouseController: provides basic mouse movement and clicking (but only via backend, currently unimplemented)
- KeyboardController: provides typing and key pressing (but only via backend, currently unimplemented)
- WindowManager: provides window focus and enumeration
- ProcessExecutive: provides process launch, termination, and waiting
- ClipboardExecutive: provides clipboard get/set
- BrowserExecutive: provides browser-specific automation (via Playwright)

The perception module exists but is not integrated into the DesktopExecutor for general computer-use observation.

## 3. Human Computer Capability Matrix

| Capability | Requirement | Existing component | Status | Evidence | Gap | Recommended next step |
|------------|-------------|-------------------|--------|----------|-----|-----------------------|
| **Input** |
| Mouse movement | Move cursor to (x, y) | MouseController.move() | PARTIALLY BUILT | mouse.py lines 25-30 | Backend not implemented (NullMouseBackend only) | Implement a real mouse backend (e.g., via pyautogui or platform-specific APIs) |
| Left click | Click left button at (x, y) | MouseController.click() | PARTIALLY BUILT | mouse.py lines 32-41 | Backend not implemented | Implement real mouse backend |
| Double click | Double click left button at (x, y) | MouseController.double_click() | PARTIALLY BUILT | mouse.py lines 43-52 | Backend not implemented | Implement real mouse backend |
| Right click | Click right button at (x, y) | MouseController.right_click() | PARTIALLY BUILT | mouse.py lines 54-55 | Backend not implemented | Implement real mouse backend |
| Drag | Drag from (x1, y1) to (x2, y2) | MouseController.drag() | PARTIALLY BUILT | mouse.py lines 57-62 | Backend not implemented | Implement real mouse backend |
| Scroll | Scroll at (x, y) by amount | MouseController.scroll() | PARTIALLY BUILT | mouse.py lines 64-69 | Backend not implemented | Implement real mouse backend |
| Mouse position | Get current cursor position | Not implemented | MISSING | No method to get current position | Add method to query current cursor position |
| Keyboard typing | Type text string | KeyboardController.type() | PARTIALLY BUILT | keyboard.py lines 31-38 | Backend not implemented (NullKeyboardBackend only) | Implement real keyboard backend |
| Individual key presses | Press individual key (e.g., 'enter') | KeyboardController.press() | PARTIALLY BUILT | keyboard.py lines 40-47 | Backend not implemented | Implement real keyboard backend |
| Hotkeys | Press key combinations (e.g., ctrl+c) | KeyboardController.hotkey() | PARTIALLY BUILT | keyboard.py lines 49-58 | Backend not implemented | Implement real keyboard backend |
| Modifier keys | Press modifier keys (shift, ctrl, alt) | KeyboardController.press() (supports any key) | PARTIALLY BUILT | keyboard.py lines 40-47 | Backend not implemented | Implement real keyboard backend |
| Text entry | Compose text via typing/paste | KeyboardController.type() + .paste() | PARTIALLY BUILT | keyboard.py lines 31-38, 60-68 | Backend not implemented for type; paste uses clipboard + hotkey | Implement real keyboard backend |
| Clipboard | Get/set clipboard text | ClipboardExecutive.read()/write() | BUILT | clipboard.py in execution/ | None | None (already implemented) |
| **Observation** |
| Full screenshot | Capture entire screen | Not implemented | MISSING | No screenshot capability | Add screenshot functionality (e.g., via mss or platform APIs) |
| Region screenshot | Capture screen region | Not implemented | MISSING | No region screenshot capability | Add region screenshot functionality |
| Screen change detection | Detect changes between screenshots | Not implemented | MISSING | No screen diff capability | Add screen change detection (e.g., perceptual hash) |
| Window discovery | List top-level windows | WindowManager.list_windows() | BUILT | window.py | None | None (already implemented) |
| Active window | Get foreground window | WindowManager.get_foreground() | BUILT | window.py | None | None (already implemented) |
| Window focus | Check if window is focused | WindowManager.is_focused() | BUILT | window.py | None | None (already implemented) |
| Visible text | Extract visible text via OCR | Not implemented | MISSING | No OCR capability | Add OCR capability (e.g., via Tesseract) |
| UI controls | Enumerate interactive elements | Not implemented | MISSING | No UI control enumeration | Add UI control enumeration via accessibility APIs or UI Automation |
| Accessibility tree | Get accessibility/UI Automation tree | Not implemented | MISSING | No accessibility tree access | Add accessibility tree access via UI Automation (Windows) or AXAPI (macOS) |
| UI Automation | Windows UI Automation support | Not implemented | MISSING | No UI Automation integration | Add UI Automation backend for Windows |
| OCR | Optical character recognition | Not implemented | MISSING | No OCR capability | Add OCR capability |
| Coordinate mapping | Map between logical/physical coordinates | Not implemented | MISSING | No coordinate mapping | Add coordinate mapping for high-DPI displays |
| Current cursor position/state | Get cursor icon/state | Not implemented | MISSING | No cursor state query | Add cursor state query |
| **Closed-loop operation** |
| Observe before action | Capture screen before performing action | Not implemented | MISSING | No observe-before-action hook | Add observe-before-action capability in DesktopExecutor |
| Perform action | Execute mouse/keyboard action | MouseController/KeyboardController | PARTIALLY BUILT | mouse.py, keyboard.py | Backends not implemented | Implement real backends |
| Observe after action | Capture screen after performing action | Not implemented | MISSING | No observe-after-action hook | Add observe-after-action capability |
| Verify expected result | Compare after-state observation to expected | Verification Subsystem (generic) | BUILT | verification/ | None | None (already implemented for Mission-level verification) |
| Detect failure | Determine if verification failed | Verification Subsystem | BUILT | verification/ | None | None |
| Retry | Retry action on failure | Orchestrator retry policy | BUILT | orchestrator/ | None | None (but limited to same action) |
| Recover | Try alternative action on failure | Not implemented | MISSING | No recovery mechanism | Add recovery mechanism that can switch interaction strategies |
| Timeout | Abort action after timeout | TimeoutGovernor in DesktopOperator | BUILT | desktop_operator/timeouts.py | None | None |
| Abort safely | Ensure safe state on abort | Not implemented | MISSING | No safe abort mechanism | Add safe abort (e.g., release modifier keys) |
| **Computer navigation** |
| Desktop | Interact with desktop icons, taskbar | Not implemented | MISSING | No desktop interaction | Add desktop navigation capabilities (via mouse/keyboard at known coordinates) |
| Taskbar | Interact with taskbar (start menu, system tray) | Not implemented | MISSING | No taskbar interaction | Add taskbar interaction |
| Start menu | Open start menu, search | Not implemented | MISSING | No start menu interaction | Add start menu interaction |
| Search | Use system search (Windows Search) | Not implemented | MISSING | No system search interaction | Add system search interaction |
| File Explorer | Navigate file system via Explorer | Not implemented | MISSING | No File Explorer interaction | Add File Explorer interaction |
| Windows dialogs | Interact with standard dialogs (open/save, message boxes) | Not implemented | MISSING | No dialog interaction | Add Windows dialog interaction |
| Open/save dialogs | Handle file open/save dialogs | Not implemented | MISSING | No open/save dialog interaction | Add open/save dialog interaction |
| Context menus | Right-click to open context menu, select item | Not implemented | MISSING | No context menu interaction | Add context menu interaction |
| Application switching | Switch via Alt+Tab, taskbar | Not implemented | MISSING | No application switching | Add application switching |
| Window management | Resize, minimize, maximize, move window | Not implemented | MISSING | No window management | Add window management (via mouse/keyboard or window APIs) |
| **Application understanding** |
| Application discovery | Discover installed applications | Desktop probe/inventory/catalog | BUILT | probe.py, inventory.py, catalog.py | None | None |
| Application identity | Verify running instance matches spec | DesktopExecutor._require_known_application() | BUILT | actions.py | None | None |
| Application launch | Launch application via spec | DesktopExecutor.execute() | BUILT | executor.py | None | None |
| Application UI inspection | Inspect UI of running application | Not implemented | MISSING | No UI inspection | Add UI inspection via observation capabilities |
| Menu discovery | Discover application menus | Not implemented | MISSING | No menu discovery | Add menu discovery via UI Automation or observation |
| Help discovery | Discover help/documentation | Not implemented | MISSING | No help discovery | Add help discovery (F1 menu, online help) |
| README/manual discovery | Discover local documentation | Not implemented | MISSING | No README/manual discovery | Add local file search for documentation |
| Documentation ingestion | Ingest documentation for knowledge | Not implemented | MISSING | No documentation ingestion | Add documentation processing pipeline |
| Application knowledge storage | Store learned workflows per application | Not implemented | MISSING | No application knowledge storage | Add application-specific knowledge base |
| Learned workflows | Store and reuse learned sequences | Not implemented | MISSING | No learned workflows | Add workflow learning and replay |
| Current UI vs stale documentation handling | Prefer current observation over documentation | Not implemented | MISSING | No preference mechanism | Add observation-as-source-of-truth principle |
| **Safety** |
| Permission gates | Require approval for irreversible actions | Permission System via DesktopExecutor | BUILT | executor.py (_profile_or_refusal) | None | None |
| Destructive-action confirmation | Require explicit approval for destructive actions | Permission System (IRREVERSIBLE tier) | BUILT | actions.py (CloseApplicationAction, ExecuteCommandAction) | None | None |
| Founder approval | Founder must approve risky actions | Permission System + Approval Queue | BUILT | mission_control/ | None | None |
| Sensitive-action handling | Handle sensitive actions (e.g., password fields) | Not implemented | MISSING | No special handling for sensitive actions | Add sensitive action detection and handling |
| Recovery/rollback | Rollback where possible (e.g., via snapshots) | Not implemented | MISSING | No recovery/rollback mechanism | Add recovery/rollback (e.g., via system restore points or VM snapshots) |
| Audit trail | Log all actions for review | Audit Stream via Mission Control | BUILT | mission_control/audit.py | None | None |

## 4. Existing systems vs. duplication

What already exists and must be reused:
- DesktopExecutor: the unified API for desktop operations (must be reused)
- WindowManager, KeyboardController, MouseController, ClipboardExecutive, ProcessExecutive: existing controller classes (must be reused)
- DesktopExecutiveV2: operation knowledge base (must be reused for application profiles)
- Permission System: already gates execution (must be reused)
- Verification Subsystem: already provides verify->evidence->brain flow (must be reused)
- Mission Control: already provides orchestration and audit (must be reused)
- Probe/Inventory/Catalog: already provides application discovery (must be reused)
- Persistence: already provides state survival (must be reused)

What exists but is insufficient:
- MouseController/KeyboardController: only have null backends; real backends missing
- WindowManager: lacks advanced window management (resize, move, etc.)
- ProcessExecutive: lacks advanced process control (suspend, etc.)
- ClipboardExecutive: only text; lacks rich clipboard formats
- DesktopExecutor: lacks arbitrary coordinate-based mouse/keyboard and screen observation

What is duplicated or at risk of becoming duplicated:
- No duplicated executives or inventories observed. The architecture avoids duplication by extending the existing DesktopExecutor.

What MUST NOT be built again:
- A second Desktop Executive or Executor
- A second Machine Inventory or Catalog
- A second Permission System
- A second Verification Subsystem
- A second Mission Control

## 5. Application knowledge layer

The repository does NOT currently have an application knowledge layer. There is:
- DesktopExecutiveV2.knowledge_base: holds operation profiles, recovery plans, workflows, and a capability matrix
- This is generic operation knowledge, not application-specific learned workflows or documentation.

The knowledge base in operations/executive.py contains:
- PROFILES: ApplicationOperationProfile (defines automation strategy and parameters)
- RECOVERY_PLANS: ApplicationRecoveryPlan (defines recovery steps per failure type)
- WORKFLOWS: Workflow (defines named sequences of capabilities)
- MATRIX: DesktopCapabilityMatrix (defines which applications offer which capabilities)

This is a foundation for application knowledge but does NOT include:
- Learned workflows from observation
- Documentation ingestion (README/help/manual)
- Site-specific knowledge (e.g., web selectors)
- Current UI vs stale documentation handling
- Application-specific OCR/templates

Thus, the Application Knowledge layer as described in the P0 vision is MISSING.

## 6. Actual verification evidence

For each important capability, we distinguish verification levels:

**AUTOMATED TESTED**
- Application discovery (probe/inventory/catalog): tested via unit tests
- Application launch/close: tested via DesktopExecutor tests
- Permission system: tested via unit tests
- Verification subsystem: tested via unit tests
- Mission Control: tested via unit tests

**MANUALLY VERIFIED**
- None observed in the codebase for desktop interaction capabilities

**SOURCE-INSPECTED ONLY**
- MouseController/KeyboardController: only source inspected; no test exercises real backends
- WindowManager: source inspected; limited tests
- ProcessExecutive: source inspected; limited tests
- ClipboardExecutive: source inspected; tested
- DesktopExecutor: source inspected; tested for existing methods

**INFERRED**
- Screen observation capabilities: inferred missing from lack of implementation
- Closed-loop operation: inferred missing from lack of observe-act-verify patterns
- Computer navigation: inferred missing from lack of high-level coordination
- Application understanding: inferred missing from lack of UI inspection and learning

**UNVERIFIED**
- All expert-level computer-use capabilities (mouse/keyboard at coordinates, screen observation, OCR, UI Automation, etc.) are unverified because they are not implemented.

## 7. Research alignment

Review of existing project research documents shows alignment with:
- PyAutoGUI: not mentioned; would be a candidate for mouse/keyboard backend
- Windows UI Automation / accessibility: not mentioned; would be needed for UI control enumeration and accessibility tree
- PyWinAuto: not mentioned; alternative for Windows UI Automation
- Screen observation: not mentioned; would need screenshot and region capture
- OCR: not mentioned; would be needed for visible text extraction
- Visual computer use: not mentioned; would be needed for fallback interaction
- Local/private computer-use approaches: the architecture supports local-first via shared infrastructure
- Application documentation/help as knowledge: not implemented; would be part of application knowledge layer
- Closed-loop observe → act → verify systems: the Verification Subsystem provides the verify->evidence->brain piece, but the act->observe piece is missing for desktop interaction

Research gaps:
- No evidence of research into visual computer use layers for desktop
- No evidence of research into OCR for desktop interaction
- No evidence of research into UI Automation integration
- No evidence of research into learned workflows from observation

## 8. Final P0 Architecture Gap

### A. ALREADY BUILT
- Application discovery (probe, inventory, catalog)
- Application launch and closure (DesktopExecutor.execute/close)
- Basic window management (focus, enumerate)
- Basic process management (launch, terminate, wait)
- Clipboard get/set (text only)
- Permission System gating
- Verification Subsystem (structurally independent)
- Mission Control orchestration and audit
- Persistence (state survival)
- DesktopExecutiveV2 knowledge base (profiles, recovery plans, workflows, matrix)

### B. PARTIALLY BUILT
- Mouse and keyboard controllers (null backends only)
- Window manager (missing advanced operations)
- Process executive (missing advanced operations)
- Clipboard executive (text only, no rich formats)
- DesktopExecutor (missing arbitrary coordinate input and screen observation)

### C. MISSING
- Real mouse and keyboard backends (platform-specific implementations)
- Screen observation (screenshot, region screenshot, screen change detection)
- OCR for visible text extraction
- UI Automation / accessibility tree access
- Coordinate mapping (high-DPI, multi-monitor)
- Cursor state query
- Observe-before/after-action hooks
- Recovery mechanisms (alternative strategies on failure)
- Advanced window management (resize, move, minimize, maximize)
- Advanced process management (suspend, resume, signal)
- Rich clipboard (formats beyond text)
- Computer navigation primitives (desktop, taskbar, start menu, search, File Explorer, dialogs, context menus, application switching, window management)
- Application understanding (UI inspection, menu discovery, help discovery, README/manual discovery)
- Application knowledge storage (learned workflows, documentation ingestion)
- Learned workflows (storage and replay)
- Current UI vs stale documentation handling (observation as source of truth)
- Sensitive-action handling
- Recovery/rollback mechanisms (system snapshots, etc.)

### D. SHOULD NOT BE BUILT / AVOID DUPLICATION
- Second Desktop Executive or Executor
- Second Machine Inventory or Catalog
- Second Permission System
- Second Verification Subsystem
- Second Mission Control
- Second Probe/Inventory/Catalog system
- Second Persistence system

## P0 Recommended Build Sequence

Starting from the two fundamental inputs (mouse, keyboard), the sequence is:

1. **Implement real mouse and keyboard backends**
   - Platform-specific implementations for Windows (primary target)
   - Replace NullMouseBackend and NullKeyboardBackend with real implementations
   - Ensure they return proper ExecutionResult objects

2. **Add screen observation capabilities**
   - Implement screenshot (full screen) and region screenshot
   - Add screen change detection (e.g., perceptual hash)
   - Integrate with DesktopExecutor to allow observe-before/after-action

3. **Implement coordinate mapping and cursor state**
   - Handle high-DPI displays and multi-monitor setups
   - Add query for current cursor position and state (icon, visibility)

4. **Build basic closed-loop operation**
   - Add observe-before-action and observe-after-action capabilities to DesktopExecutor
   - Wire observation to Verification Subsystem for verify step
   - Add basic retry on verification failure (same action)

5. **Implement computer navigation primitives**
   - Desktop interaction (click desktop icons, taskbar)
   - Taskbar interaction (start menu, system tray)
   - Start menu interaction (open, search)
   - Search interaction (system search)
   - File Explorer interaction (navigate, open file/folder)
   - Windows dialogs interaction (open/save, message boxes)
   - Context menus interaction (right-click, select)
   - Application switching (Alt+Tab, taskbar)
   - Window management (resize, move, minimize, maximize via mouse/keyboard or window APIs)

6. **Enrich application understanding**
   - Add UI inspection via observation (text, control state)
   - Add menu discovery (via UI Automation or observation)
   - Add help discovery (F1, online help)
   - Add README/manual discovery (local file search for common documentation filenames)
   - Add documentation ingestion pipeline (extract text from common formats)

7. **Build application knowledge layer**
   - Extend DesktopExecutiveV2.knowledge_base to store learned workflows per application
   - Add mechanism to learn workflows from successful verification
   - Add storage and replay of learned workflows
   - Implement current UI vs stale documentation handling (prefer observation)

8. **Implement advanced verification and recovery**
   - Enhance verification to use enriched observation (screenshot, OCR, UI Automation)
   - Add recovery mechanism that can switch interaction strategies (e.g., DOM → visual for browser)
   - Add verification-informed retry with alternative selectors or coordinates

9. **Add safety and sensitivity handling**
   - Implement sensitive action detection (e.g., password fields)
   - Add safe abort (release modifier keys, etc.)
   - Consider recovery/rollback via system snapshots where applicable

10. **Achieve expert operator behavior**
    - Combine all above to enable human-like interaction with any Windows application
    - Verify through automated tests that observe → act → verify → recover loop works
    - Validate against real-world applications (beyond the catalog)

## 9. Git / Documentation Safety

- Current branch: main
- Current commit: 51cdf446f70a12b7f6b6a3f18b60e3df353b5e7c
- Uncommitted changes: 18 modified, 54 untracked (as per session start snapshot)
- Relevant commits:
  - da950c9: Installer: clean up app directory on uninstall (most recent)
  - b387df0: Fix Bluetooth device detection (device-detection layer only)
  - Mission Brief 030: Desktop Executive initial implementation
- The audit itself only created the requested gap matrix document; no implementation files were modified.
