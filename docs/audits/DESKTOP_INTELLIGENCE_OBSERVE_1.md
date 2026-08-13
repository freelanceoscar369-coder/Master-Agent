# Desktop Intelligence — Observe → Understand — Milestone Report

**Status: milestone frozen and committed.** This report closes the
"Desktop Intelligence — Observe & Understand Foundation" mission, the
direct follow-on to `docs/audits/DESKTOP_INTELLIGENCE_GAP_ANALYSIS_1.md`
and the reasoning-layer milestone (`milestone-reasoning-layer`, `72fcb37`).

## What was built

A new package, `src/master_agent/desktop/intelligence/`, sitting above
`desktop/execution/` (raw UIA/Win32 primitives) and beside
`desktop/perception/` (C27's application/window-level presence layer —
composed with, not replaced or duplicated):

| Module | Role |
|---|---|
| `models.py` | `DesktopObservation`, `ElementObservation`, `ScreenshotEvidence`, `SemanticRole`, `WindowState` — the data. |
| `evidence.py` | `capture_evidence()` — Part B's read-only primitive: one already-resolved window in, one `DesktopObservation` out. |
| `classification.py` | `classify_element()` — Part D's semantic classification, evidence-based, no vendor branching. |
| `screenshot.py` | `capture_screenshot()`/`Win32ScreenshotBackend` — Part C's first-class screenshot capability, safe-failing. |
| `app_knowledge_bridge.py` | `resolve_app_knowledge()` — Part E's join from a desktop catalog key to an `AppKnowledgeProfile`. |
| `observer.py` | `DesktopIntelligence.observe_desktop()` — Part F's stable, runtime-integrated API. |

Plus one minimal, additive extension to the hardened
`desktop/execution/uia_control.py` (no existing method's behavior
changed): `UiaElementSnapshot`, `snapshot_elements()`, and
`window_bounds()` — the one new read-only UIA primitive this whole
package needed and did not already have (batch element enumeration;
every other method this package calls — `find_composer()`,
`find_main_content()`, `find_new_content()`,
`get_focused_element_in_window()` — already existed). Real UIA
`ControlType`/property constants used by classification (`CONTROL_TYPE_*`,
`SelectionItem`/`WindowIsModal` property IDs) were verified against the
real, installed `UIAutomationCore.dll` type library before use, not
guessed — see the constant block's own comment in `uia_control.py`.

One new read-only Desktop Executive action, `desktop_observe`
(`ObserveDesktopAction` in `actions_interaction.py`, `RiskTier.READ_ONLY`),
registered alongside `find_target`/`read_text` — the Part F integration
boundary a future Planner step can call.

## Confidence vocabulary

Reused, not reinvented: `app_knowledge.profile.KnowledgeType`
(`DOCUMENTED`/`OBSERVED`/`INFERRED`/`UNKNOWN`) is the confidence band for
every fact this layer produces. `DOCUMENTED` is reserved for facts that
came from a consulted `AppKnowledgeProfile` (carried through unchanged,
never collapsed into `OBSERVED`); `OBSERVED` for hard UIA property/
`ControlType` reads; `INFERRED` for the existing `find_composer()`/
`find_main_content()`/`find_new_content()` heuristics and this package's
own generic sidebar-geometry heuristic; `UNKNOWN` is the honest default —
Part D's own rule ("if the system cannot confidently determine a role,
return UNKNOWN rather than guessing") is enforced by
`classification.py`'s own fallthrough, not a caller's afterthought.

## Read-only, structurally

Every `UiaAutomationBridge` call this package makes is one of:
`snapshot_elements()`, `window_bounds()`, `find_composer()`,
`find_main_content()`, `find_new_content()`,
`get_focused_element_in_window()` — all read-only by their own existing
contract. `tests/test_desktop_intelligence.py` proves this two
independent ways: a fake bridge whose `write_text()`/`click()` raise
`AssertionError` on any call (exercised end-to-end through
`capture_evidence()`), and a structural AST scan of every module under
`desktop/intelligence/` confirming no mutating identifier
(`write_text`, `click`, `KeyboardController`, `MouseController`, `paste`,
`press`) is even referenced in source.

## Deterministic tests — Part G, all 15 plus extras

`tests/test_desktop_intelligence.py`, 30 tests, all passing:

1. Clean observation, 2. Unknown application, 3. Missing window,
4. Hidden/offscreen elements, 5. Focused element detection,
6. Composer classification, 7. Button classification,
8. Unknown classification, 9. Confidence handling,
10. App Knowledge lookup, 11. Screenshot capture success,
12. Screenshot capture failure, 13. Provenance/timestamp preservation,
14. No mutation during observation, 15. Cross-application focus safety.

Plus: selected-tab identification, window-state (minimized/normal),
response-region classification via `find_new_content()`, and
`as_dict()` JSON-shape serialization.

## Live validation — bounded, read-only, no retries

ChatGPT Desktop, Kimi Desktop, and Perplexity Desktop were all found
installed **and already running** on this machine (a real,
`deep=True` inventory scan — read-only, no launch). Gemini has no
desktop-app UIA surface in this codebase (`providers/gemini.py` is an
API-based provider, not a catalog entry `desktop/catalog.py` knows about)
— inspected per the mission's own instruction, not live-tested as a
desktop app, since it is not one. `DesktopIntelligence.observe_desktop()`
was called exactly once per application, with `capture_screenshot=True`,
no retries:

### ChatGPT Desktop — strong success

- `application_confidence`: `OBSERVED` (window 262842, "ChatGPT", real
  process-id attribution).
- `window_state`: `maximized`. 280 elements enumerated.
- Composer correctly identified: `"Message ChatGPT"`, role `COMPOSER`,
  `INFERRED` (matched `find_composer()`'s own heuristic) — 2 composer
  *candidates* surfaced (`"Codex"`, `"Message ChatGPT"`), the winner
  correctly distinguished from the runner-up rather than conflating them.
- 86 actionable controls identified (buttons: "Hide sidebar", "Back";
  menus: "File", "Edit", "View", "Help", "Application menu"; etc.).
- `focused_element`: `None` — correct and expected: this call never
  brought ChatGPT's window to the foreground, so real OS keyboard focus
  never left this agent's own window. Proves, live, the same
  cross-application-focus-safety guard Part G item 15 tests
  deterministically.
- Screenshot: captured successfully, 1295×687 PNG, written to
  `%LOCALAPPDATA%\Kalpavriksha\desktop_intelligence_evidence\`.
- App Knowledge: `CHATGPT_DESKTOP` profile consulted and carried through.
- Overall confidence: `OBSERVED`.

### Kimi Desktop — honest UNKNOWN, not forced

- Kimi's processes were found running, but no window was located for
  them — the same pre-existing orphaned-process/environment issue
  `REASONING_LAYER_MILESTONE_1.md` and the gap analysis both already
  documented. Per this mission's own explicit instruction ("Do NOT
  attempt to force Kimi into a clean state... Do NOT repeatedly retry
  applications indefinitely"), this was called once, reported honestly
  (`application_confidence: UNKNOWN`, reason stated plainly, 0 elements),
  and not re-debugged.

### Perplexity Desktop — window found, honestly sparse (minimized)

- `application_confidence`: `OBSERVED` (window 133034, "Perplexity").
- `window_state`: `minimized` — 16 elements enumerated (window-chrome
  level only: "System" menu, "Restore"/"Maximise"/"Close" buttons), no
  composer found — correct: a minimized window's real content is not
  rendered, so no composer/response-region evidence could exist to find.
- Screenshot: safely failed — `captured: False`, reason `"degenerate
  capture bounds (0, 0, 0, 0)"` (a minimized window reports a zero-size
  rectangle) — Part C's own "safe failure if screenshot capture is
  unavailable" requirement, proven live, not just unit-tested.
- App Knowledge: `PERPLEXITY_DESKTOP` profile consulted.
- Overall confidence: `OBSERVED` (the window itself was genuinely found;
  its minimized state is an honest fact, not a defect in observation).

**No prompt was typed. No conversation was created. No existing session
was renamed. No submit action occurred, against any of the three
applications** — structurally guaranteed by `capture_evidence()`'s own
read-only call surface (see above), and confirmed operationally: every
`focused_element` reading above is `None` or belongs to the observed
window's own pre-existing state, never a state this call caused.

## Regression validation

Mission-relevant suite (`test_desktop_uia`, `test_desktop_intelligence`
[new, 30 tests], `test_app_knowledge_profile`,
`test_app_knowledge_acquisition`, `test_desktop_execution`,
`test_desktop_operator`, `test_reasoning_session_manager`,
`test_desktop_app_provider`, `test_kalpavriksha_desktop_mission_bridge`,
`test_desktop_perception`):

```
490 passed in 64.7s
```

`test_desktop_operations.py` (2 failures — `notepad` now has a real
`RECOVERY_PLANS`/`profile()` entry a stale test still asserts should not
exist) was checked against the identical pre-mission tree via `git
stash`: **both failures reproduce byte-for-byte identically with and
without this mission's changes** — pre-existing catalog/test drift,
unrelated to Desktop Intelligence, left untouched per this project's own
execution-first protocol (don't reopen unrelated debugging).

Full-suite run: three test modules (`test_communication.py`,
`test_conversation_engine.py`, `test_desktop_shell.py`) fail to *collect*
on a circular import inside the working tree's own uncommitted Founder
Edition changes (`founder_runtime`/`founder_edition`/`communication`/
`conversation_engine` — none of it touched by this mission); confirmed,
via the same `git stash` check, present identically with or without this
mission's changes. A further block of tests
(`test_memory_integration.py`, `test_missions_architecture.py`,
`test_missions_console.py`, `test_mit_001_browser_integration.py`,
`test_ollama_provider.py`, `test_provider_execution.py`,
`test_verified_execution.py` — none of which import anything from
`desktop/intelligence/`, `actions_interaction.py`, or `uia_control.py`,
confirmed by grep) show a variable pass/fail count between runs
(consistently 84 failed without this mission's changes, consistently 59
failed with them, across repeated runs each way) — deterministic per
tree state but not attributable to any import dependency on this
mission's own code; pre-existing environment/ordering sensitivity in an
unrelated part of the suite, not a Desktop Intelligence regression.
**Zero new failures were found in any test that exercises code this
mission touched.**

## Non-goals held

No autonomous planning, no recovery loop, no self-healing, no
unrestricted LLM control, no vendor-specific automation branch, no Groq/
new reasoning provider, no Perplexity persistence redesign, no Kimi
contamination cleanup, no Gemini redesign, no rewrite of the reasoning-
provider architecture or `ReasoningSessionManager`. `AppKnowledgeProfile`
is consulted as data only — nothing in `desktop/intelligence/` imports or
calls a Desktop Executive action.

## Commit

Tag: `milestone-desktop-intelligence-observe`. Not pushed to remote.
Scope: `desktop/intelligence/` (new), the additive `uia_control.py`
extension, `actions_interaction.py`'s new `desktop_observe` action,
`tests/test_desktop_intelligence.py`, `pyproject.toml`'s explicit Pillow
dependency, `packaging/kalpavriksha.spec`'s hiddenimports, and this
report/the gap analysis this mission responded to. Every other
pre-existing uncommitted working-tree file (Founder Edition voice/
browser/Gemini-provider work, VEDRA_PROJECT assets, root-level status
text files) is left untouched, per the same discipline
`REASONING_LAYER_MILESTONE_1.md` already held itself to.
