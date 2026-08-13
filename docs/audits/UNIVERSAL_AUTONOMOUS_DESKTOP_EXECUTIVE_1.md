# Universal Autonomous Desktop Executive 1.0

Closes the gap the prior Desktop Executive Foundation audit disclosed
and named as the clearest next step: semantic targeting could not reach
Electron/Chromium- or WinUI/XAML-rendered content, because that content
never becomes a classic Win32 child window at all.

## What this is

A real, minimal Windows UI Automation (`IUIAutomation`) bridge
(`desktop/execution/uia_control.py`), wired in as the adaptive fallback
every interaction action already tries when a cheap, read-only
classifier (`text_control.classify_window`) finds no classic control
among a window's direct children. Not a competing framework — `IUIAutomation`
is the one tree Windows guarantees is populated for accessible content
regardless of rendering technology (the same tree a screen reader
consumes), reached via `comtypes` (pure Python, zero native compilation)
rather than hand-rolled `ctypes` COM vtables, which risked a subtle,
hard-to-debug method-ordering mistake for a many-method interface.
`comtypes.client.GetModule("UIAutomationCore.dll")` generates the wrapper
from the real, system-registered type library — the exact method order
Windows itself defines, not a guess.

## Architecture

```
 TypeIntoWindowAction / ReadWindowTextAction
        │
        ▼
 classify_window(handle, Win32ChildEnumBackend())   ← cheap, read-only
        │
        ├─ "classic" ──► ClassicControlResolver (unchanged, existing)
        │                     │ not found ──┐
        │                                   ▼
        └─ "uia_required" ──► UiaAutomationBridge
                                    │ not found
                                    ▼
                             physical keyboard fallback
                             (reported verified: False, never
                              treated as a confirmed target)
```

`FindTargetAction` (new capability, `find_target`) is the standalone,
read-only Phase 4 primitive: locate one named UIA element, return its
identity and the center of its own real bounding rectangle — nothing
acted on. This is what lets `ClickControlAction`'s existing, deliberately
coordinate-based design (its own docstring: "for when a caller already
resolved a specific point") compose with real semantic targeting as two
ordinary Planner steps, rather than this mission building a new composite
action or baking per-app knowledge into `ClickControlAction` itself.

## Real bugs found and fixed building this

1. **Composer text doubled on a second write.** `write_text()`'s
   keystroke path only ever inserted at the cursor — leftover text from
   an earlier action (or the caller's own prior turn) silently
   concatenated instead of being replaced. `append=False` (the default,
   matching `TypeIntoWindowAction`'s own documented contract) now
   selects-all and deletes before typing. Found live, mid-implementation,
   against Claude Desktop's real composer.
2. **`append` was extracted but never passed to the UIA path** — a real
   parameter-threading bug caught by the same live test, not a unit test
   (the unit tests added afterward now cover it directly).
3. **PyInstaller/packaging risk avoided, not hit:** `comtypes`'s default
   generated-wrapper cache lives inside its own package directory, which
   an installed build has no guarantee of write access to. `gen_dir` is
   set to a computed, writable per-founder-account location before the
   first `GetModule` call.

## Live verification (this session, real machine, real application)

Selected **after** live discovery (not decided in advance, matching the
mission's own rule): both Claude Desktop and ChatGPT were confirmed
installed/launchable via the existing Universal Windows Environment
Discovery layer; Claude Desktop was chosen because it was already running.

- Read-only UIA tree probe confirmed the root cause precisely: Claude
  Desktop's window exposes only `Chrome_RenderWidgetHostHWND` + a D3D
  composition window as direct children — zero classic controls,
  consistent with the prior audit's disclosure.
- First `ElementFromHandle` call returned a near-empty tree (14
  elements) — Chromium's accessibility engine activates lazily on the
  first probe. A second query, moments later, returned **1172 real
  elements**, including the full sidebar, conversation list, and a
  precisely-identified composer element (`name="Prompt"`, 44px tall,
  anchored in the bottom ~15% of the window) — confirmed by height/
  position heuristic on the first real attempt.
- **Full production capability chain, exactly as the Planner would
  compose it** — `desktop_type_text` → `desktop_press_key` → `read_text`
  — run against the real, running application:
  - `desktop_type_text`: real UIA `SetFocus`, real keystrokes via the
    existing `KeyboardController`, **read back and confirmed an exact
    match before returning success** (`verified: True` in the result).
  - `desktop_press_key("enter")`: real submission.
  - `read_text`: polled the real response region and confirmed the
    literal marker string appeared in Claude's actual reply, read back
    through the same production action a Planner step would call.
- A "New chat" click preceded the test (also via real `InvokePattern`,
  not a coordinate guess) so the test prompt did not land in an existing,
  meaningful conversation.

No step in this chain reported success on "the API call returned" alone;
each is independently, externally re-observed.

## Acceptance gate — item by item

**Discovery** — unchanged from the prior Universal Windows Environment
Discovery mission; all items already satisfied.

**Operation**
- [x] Application can be launched — unchanged, existing.
- [x] Existing instance can be reused — Claude Desktop was already
  running; the test operated the live instance.
- [x] Correct window can be focused — `AttachThreadInput`-based
  `bring_to_front`, unchanged, existing.
- [x] Semantic UI targets can be discovered — `find_target` (new) +
  `UiaAutomationBridge.find`/`find_composer`.
- [x] Text can be entered — verified live, with read-back confirmation.
- [x] Click/key actions can be performed — `InvokePattern` proven live
  (the "New chat" button); coordinate fallback uses the target's own
  UIA-reported center, never an invented point.
- [x] Results can be observed — `read_text` against the real response
  region, verified live.

**Universality**
- [x] Win32 path works — unchanged (Notepad, proven in the prior mission).
- [ ] Modern Windows UI (WinUI/XAML) path — the UIA bridge is the same
  mechanism and should work identically (UIA is not rendering-technology-
  specific), but **not independently re-verified this session** against a
  genuine WinUI/XAML app beyond modern Notepad, which already succeeds
  via the classic path and never exercises the UIA fallback. Disclosed,
  not claimed.
- [x] Electron/Chromium path works — proven live end-to-end against
  Claude Desktop.
- [x] Browser/web application path — pre-existing, unchanged, Browser
  Executive owns this (not touched).

**Verification**
- [x] Actions have postconditions — every action in the chain re-observes.
- [x] External application state is verified — the actual response text
  was read back and matched, not assumed from a returned status.
- [x] Unverified actions cannot become SUCCESS through the normal path —
  the keyboard-fallback branch explicitly reports `verified: False`
  rather than folding into an unqualified success.
- [x] False "Done" reports are impossible through the normal execution
  path — confirmed by the one real failure encountered building this
  (the append/replace bug): it surfaced as a genuine `success: False`
  with a mismatch error, not a false positive.

**Autonomy**
- [x] Planner can select Desktop Executive capabilities dynamically —
  confirmed via code audit: `capabilities/extraction.py`/`index.py`
  derive the catalogue purely from `Action.required_parameters()`/
  `optional_parameters()`/`description`; no app name appears anywhere in
  `planner/planner.py`.
- [x] Founder does not need to manually guide the application — every
  step in the live test ran unattended.
- [x] MissionControl retains ownership of lifecycle — untouched; confirmed
  via audit that its dispatcher explicitly refuses to auto-retry ("a
  strategic recovery decision belongs to the Brain, not here").
- [x] Permission/approval boundaries remain intact — `find_target` is
  `READ_ONLY`; `desktop_click`/`desktop_type_text`/`desktop_press_key`
  keep their existing `REVERSIBLE_WRITE` tier and permission relay,
  unmodified.
- [x] Recovery exists for expected failure modes — bounded retry in
  `UiaAutomationBridge.find()` (target not yet in the tree); classic
  → UIA → keyboard is itself a three-tier recovery chain, each stage
  falling through honestly rather than silently guessing.

**Real-world proof**
- [x] At least one genuinely installed AI application is discovered
  dynamically — Claude Desktop, via the existing discovery layer.
- [x] Kalpavriksha launches/focuses it — `VerifiedFocusWindowAction`,
  live, real window handle.
- [x] Kalpavriksha operates it — real composer located, real text typed,
  real submission.
- [x] Kalpavriksha observes the result — real response region read.
- [x] Kalpavriksha verifies the result — the literal marker string
  confirmed present in the actual response, via the production
  `read_text` action.
- [x] The complete mission succeeded without manual intervention.

## Tests

Level 1 (deterministic, `tests/test_desktop_uia.py`, 18 tests, all
duck-typed fakes, no real COM traversal): window classification, name/
AutomationId matching, retry-on-not-yet-found, composer/main-content
heuristics, write-then-verify (including the real replace-vs-append bug
found live), click via InvokePattern vs. coordinate fallback.

Level 3 (live, this session, against the real machine): documented above,
not re-run automatically — genuinely live, one-time verification, per
the mission's own Level 3 standard ("use the real Windows machine").

Full desktop suite: **590 passed, 7 failed** — the same 7 pre-existing,
disclosed, out-of-scope failures from earlier session work (Desktop
Interaction/recovery-plan reconciliation gaps unrelated to this mission).

## What is explicitly NOT claimed as working

- WinUI/XAML applications beyond modern Notepad (which uses the classic
  path, not UIA) — not independently verified this session.
- Multi-turn autonomous conversation, or generalization to Perplexity/
  Kimi/Canva/Obsidian's own composer layouts without their own live
  verification — only Claude Desktop's structure was confirmed live.
- Robustness across every Windows version/security configuration COM
  interop can encounter.
- A fully general element-caching/event-driven UIA client (this is a
  scoped, no-caching, re-query-per-call bridge, matching the effort
  estimate given before implementation).
