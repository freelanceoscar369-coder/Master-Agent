# Kalpavriksha P0 Browser Executive Expert Operator Gap Audit

## 1. Browser Executive Location
The Browser Executive is implemented as the Browser Worker within the Universal Executive Operator architecture.
Key files:
- `src/master_agent/plugins/browser_worker.py` (Worker Lifecycle facade)
- `src/master_agent/plugins/browser_plugin.py` (Plugin adapter)
- `src/master_agent/executor/actions/browser/` (9 atomic Actions)
- `src/master_agent/environment/browser_session.py` (Environment Session Manager)
- `src/master_agent/plugins/browser_observation.py` (Observation normalization)
- `src/master_agent/plugins/browser_verifier.py` (Verification implementation)
- `src/master_agent/verification/` (generic Verification subsystem)

## 2. Existing Capabilities
The Browser Executive currently provides:
- **Environment Session Management**: Single Playwright driver per Operator Instance, multiplexed browser contexts per session_id.
- **Nine atomic Actions**: 
  - `open_browser_session` (REVERSIBLE_WRITE/SYSTEM)
  - `close_browser_session` (REVERSIBLE_WRITE/SYSTEM)
  - `navigate` (REVERSIBLE_WRITE/MODIFY) - page.goto()
  - `click` (REVERSIBLE_WRITE/MODIFY) - page.locator(selector).click()
  - `type_text` (REVERSIBLE_WRITE/WRITE) - page.locator(selector).fill()
  - `press_key` (REVERSIBLE_WRITE/MODIFY) - page.keyboard.press() or locator.press()
  - `scroll` (REVERSIBLE_WRITE/MODIFY) - page.locator(selector).scroll_into_view_if_needed() / mouse.wheel()
  - `wait_for_selector` (READ_ONLY/READ) - page.locator(selector).wait_for()
  - `observe_browser` (READ_ONLY/READ) - normalize_observation()
- **Observation Facets** (via normalize_observation):
  - Current page (URL, title)
  - Viewport size
  - DOM state (via selector-based BrowserElement: visibility, text, tag name)
  - Optional: Accessibility tree (ARIA snapshot)
  - Optional: Available actions (interactive affordances)
- **Verification**: Structurally independent Verifier that re-observes and compares against ExpectedOutcome.
- **Audit**: Automatic audit trail via AuditLog recording execution and verification results.
- **Permission System Integration**: Actions declare risk tiers and categories; permission checked via Orchestrator.
- **Multi-session support**: BrowserSessionManager keyed by session_id allows multiple concurrent sessions per Operator Instance.
- **Engine agnosticism**: Browser engine choice confined to `_launch()` function (currently Chromium).

## 3. Expert-Level Capabilities Already Present
| Capability | Requirement | Existing Implementation | Status | Evidence |
|------------|-------------|-------------------------|--------|----------|
| **Environment Session Management** | Live handle to browser instance | BrowserSessionManager with lazy Playwright driver, context/page per session | IMPLEMENTED | browser_session.py lines 104-194 |
| **Atomic Navigation** | open URL, back, forward, reload | `navigate` Action supports `goto`; back/forward/reload not implemented as separate Actions | PARTIAL | navigate.py uses page.goto(); no back/forward/reload Actions |
| **Element Interaction** | click, double click, right click, drag | `click` Action supports left click via locator.click(); no double/right click/drag | PARTIAL | click.py uses page.locator(selector).click() |
| **Input** | keyboard typing, key presses, hotkeys, clipboard | `type_text` for filling; `press_key` for keyboard events; no clipboard | PARTIAL | type_text.py (fill), press_key.py (keyboard.press/locator.press) |
| **Viewport Control** | scroll | `scroll` Action supports scroll_into_view_if_needed and mouse.wheel | IMPLEMENTED | scroll.py |
| **Waiting** | wait for selector, network, timeout | `wait_for_selector` Action; no explicit network/waitForTimeout | PARTIAL | wait_for_selector.py uses locator.wait_for() |
| **Observation** | screenshot, viewport, DOM, accessibility tree, visible text, title, URL, active tab, tab list, active element, element roles/names/states, loading state, dialogs, popups, permission prompts, downloads, upload state | `observe_browser` provides: URL, title, viewport, selector-based element info (visibility, text, tag); optional accessibility tree and available actions; no tab list, active tab, dialog/popup/download/upload state | PARTIAL | browser_observation.py lines 156-188 (facets) |
| **Verification** | verify expected result vs actual | `BrowserVerifier.verify()` re-observes and compares via ExpectedOutcome checks | IMPLEMENTED | browser_verifier.py + verification/ |
| **Error Handling** | detect action failure, retry, alternative strategy | Actions return ExecutionResult with success/errors; no automatic retry or strategy switching in Worker | PARTIAL | Actions catch BrowserSessionError and general exceptions; retry is Orchestrator's responsibility |
| **Human-like Operation** | semantic location, choose DOM/visual, interact via coordinates, adapt to layout changes, recognize failure, recover | Semantic location via selectors; no visual fallback (OCR/coordinates); no layout change adaptation; failure detected via verification but no automatic recovery | PARTIAL | Observation uses selectors only; no visual computer use layer |

## 4. Missing Capabilities for P0 Expert Operator
| Capability | Requirement | Gap | Recommendation |
|------------|-------------|-----|----------------|
| **Visual Computer Use** | Fallback to screenshot, OCR, mouse/keyboard coordinates when DOM insufficient | No visual observation or interaction layer | Add visual observation (screenshot+OCR) and visual interaction (mouse/keyboard at coordinates) as alternative to DOM-based Actions |
| **Advanced Input** | double click, right click, drag, clipboard, hotkeys | Only left click and basic keyboard press | Add Actions for double click, right click, drag; enhance press_key for hotkeys; add clipboard get/set |
| **Complete Navigation** | back, forward, reload, new tab, close tab, switch tab, window management, deep links, redirects | Only basic navigate (goto) | Add Actions for navigation controls, tab/window management |
| **Complete Observation** | tab list, active tab, element states (checked/selected/disabled), loading state, dialogs, popups, browser permission prompts, downloads, upload state | Observation missing many browser state facets | Enhance normalize_observation to include: tab information, dialog/popup detection, permission prompts, download/upload progress, detailed element states |
| **Automatic Recovery** | recognize failure, retry with alternative strategy, verify recovery | No automatic recovery logic in Worker; Orchestrator handles retry but not strategy switching | Add verification-informed retry logic that can switch interaction strategies (e.g., DOM → visual) |
| **Context Awareness** | understand single-page apps, infinite scroll, dynamic content, SPA applications | Observation is snapshot-based; no built-in waiting for dynamic content beyond wait_for_selector | Add smart waiting mechanisms (e.g., wait for network idle, wait for specific DOM changes) and observation of dynamic content patterns |
| **Knowledge Persistence** | learn workflows, remember site-specific knowledge, distinguish current UI from stale knowledge | No browser-specific knowledge system; relies on general Memory system | Add browser knowledge base (e.g., site selectors, workflow patterns) that updates based on verified successful interactions |
| **Multi-tab/window Handling** | manage multiple tabs/windows, switch context | Sessions are single page; no tab/window management | Extend BrowserSession to manage multiple Pages/contexts; add Actions for tab/window operations |
| **File Upload/Download** | handle uploads and downloads, set/download paths | No upload/download Actions | Add Actions for file upload (setInputFiles) and download (waitForEvent/download) with path configuration |

## 5. Research Gaps
Compared to recommended research tools:
- **Python-UIAutomation-for-Windows / pywinauto**: Not used; could be leveraged for browser chrome (URL bar, dialogs) where DOM insufficient.
- **python-mss / pynput / Tesseract**: Not used; could form visual computer use layer for fallback interaction.
- **OpenRecall**: Not used; could provide local screen context for understanding application state beyond browser.
- **Playwright for browser automation**: Used but only for DOM layer; missing visual fallback and browser chrome interaction.
- **pywin32/wmi**: Not used; could aid in Windows-specific browser process/window management.

## 6. Duplicate Systems Avoided
- No second Browser Executive or Executor created.
- Existing Browser Worker reuses:
  - Generic Verification subsystem (`verification/`)
  - Generic Audit subsystem (`verification/audit.py`)
  - LocalExecutor and Permission System via existing plugin machinery
  - Environment Session pattern (BrowserSessionManager) that could be extended for other Environment types
- All browser-specific code is isolated to browser-plugins and browser-actions.

## 7. Verification Evidence
- **Automated Test Evidence**: 
  - `tests/test_browser_worker_lifecycle.py` demonstrates Execute → Verify → Audit sequence
  - `tests/test_browser_constitution_compliance.py` verifies no Playwright imports in non-browser-files
  - Action-specific tests (e.g., `tests/test_browser_open_session.py`)
- **Manual Evidence**: None provided in audit scope; mission brief 022 includes live demo against real internet (example.com)
- **Source Inspection**: Conducted via reading files listed above
- **Inference**: Based on architectural review and capability enumeration
- **Unverified**: No evidence of expert-level visual fallback or advanced interaction strategies

## 8. Recommended P0 Sequence
To achieve expert human-like browser operator, implement in this order:
1. **Observe**: Enhance observation to capture comprehensive browser state (tabs, dialogs, download/upload, permission prompts, detailed element states)
2. **Understand**: Add visual observation (screenshot+OCR) as fallback for DOM-insufficient situations
3. **Navigate**: Implement complete navigation controls (back, forward, reload, tab/window management)
4. **Act**: Implement advanced input (double/right click, drag, clipboard, hotkeys) and file upload/download
5. **Verify**: Enhance verification to use enriched observation and support visual verification
6. **Recover**: Add verification-informed recovery that can switch interaction strategies (DOM ↔ visual) and retry with alternative selectors
7. **Learn**: Add browser-specific knowledge base for site patterns and workflows that updates with successful verification
8. **Remember**: Ensure knowledge persists across sessions and distinguishes current UI from stale
9. **Improve**: Use knowledge to optimize interaction strategies (e.g., prefer visual for canvas elements)

## 9. Git Status
- Branch: main
- Current commit: 51cdf44 (Installer: clean up app directory on uninstall)
- Relevant Browser Executive commits:
  - da950c9 (C34.5: ship verification — real installer built, run, and verified)
  - b387df0 (C34.4: fix Bluetooth device detection (device-detection layer only))
  - Mission Brief 022: Browser Worker initial implementation (earlier in history)
- Working tree state: 18 modified, 54 untracked (as of session start)

## Conclusion
The Browser Executive provides a solid foundation for browser automation via Playwright but lacks the visual computer use, advanced interaction, and recovery mechanisms required for an expert human-like browser operator. The architecture supports extension without duplication, and the recommended P0 sequence builds upon existing capabilities to achieve the vision.