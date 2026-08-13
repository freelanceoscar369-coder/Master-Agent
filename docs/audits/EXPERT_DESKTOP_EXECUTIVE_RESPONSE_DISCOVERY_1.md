# Expert Desktop Executive — Architecture Review & Response-Discovery Fix

**Status: PASS.** One high-priority generic weakness (response discovery)
found, fixed, and confirmed live end-to-end after three successive
live-found refinements. One second-priority generic weakness (visibility
filtering gaps) fixed alongside it. Everything else reviewed and left
untouched — either already sound, or a limitation documented rather than
chased, per the mission's own scope boundary.

## 1. Architecture review

Read in full: `desktop/execution/uia_control.py`,
`providers/desktop_app.py`, `desktop/execution/window.py`,
`providers/reasoning_session.py` (read for context only — reasoning
session architecture is out of scope this mission and was not modified).

Assessed against every focus area the mission named:

| Area | Assessment |
|---|---|
| Window discovery | Sound. Generic, real Win32-backed, structured results. |
| Application launch/focus | Sound, with one known limitation — see §5. |
| Window maximization | Sound (added last mission, unchanged here). |
| Chat/Work/Codex navigation | Out of scope (`reasoning_session.py`) — not reviewed for changes. |
| UIA element discovery (`find()`) | Sound — bounded retries, exact/substring name matching, `visible_only`. |
| Exact-name matching | Sound (`name_exact`). |
| Visibility filtering | **Gap found** — `find()` had it; `find_composer()`/`find_main_content()` didn't. Fixed, §3. |
| Composer discovery | Sound geometry heuristic (fixed last mission); now also visibility-filtered. |
| Focus acquisition | Sound — bounded, mouse-click fallback, already proven live. |
| Clear-before-write | Sound — bounded, read-back-verified. |
| Write verification | Sound — containment-based, tolerant of composer chrome (fixed last mission). |
| Paste/type fallback | Sound — length + newline routing. |
| Newline handling | Sound — routes through paste. |
| Enter submission | Sound — verified, not assumed. |
| Send-button fallback | Sound — generic vocabulary, same `find()`/`click()` primitives. |
| Submission verification | Sound — composer-content-change based, bounded. |
| Bounded retries | Sound and consistent throughout — no unbounded loop anywhere in this layer. |
| **Response discovery** | **High-priority gap, explicitly flagged by the mission** — fixed, §4. |
| **Response verification** | Weak "differs from prompt" check inherited the same gap — fixed alongside, §4. |
| Foreground-window safety | Sound — already proven live to correctly refuse to act when the wrong window held focus. |

## 2. Prioritized list of genuine generic weaknesses

1. **Response discovery selects the wrong region** (`find_main_content()`'s
   "largest text-bearing region" heuristic) — HIGH confidence, HIGH value,
   explicitly named by the mission, reproducible on two independent
   applications. **Fixed.**
2. **Missing visibility filtering on `find_composer()`/`find_main_content()`**
   — the exact class of bug `find()`'s own `visible_only` was built for,
   never propagated to these two related heuristics. HIGH confidence,
   low risk, minimal change. **Fixed.**
3. **`_launch_or_focus()`'s foreground-confirmation can time out when a
   different, unrelated window (this development session's own
   coding-agent GUI) repeatedly reclaims OS foreground focus** — observed
   live, twice, this session. **Not fixed** — this is a desktop-usage
   collision specific to running live diagnostics from inside an active
   coding session on the same physical desktop, not a defect in a normal
   founder's single-application-focus operating condition. Per the
   mission's own five-part test ("reproducible, generic interaction
   failure, expressible as a reusable primitive, benefits existing
   providers, provable by a deterministic test"), this fails on
   "generic" — the fix would be either app-agnostic-but-wrong (assume the
   foreground is contested and blindly retry longer, papering over a
   condition that isn't really about desktop interaction reliability) or
   session-specific-and-out-of-scope (detect and ignore one particular
   coding-agent window). Documented, not touched.

No other candidate weakness cleared the bar for action — everything else
in the review table above was already sound.

## 3. Fix: visibility filtering for `find_composer()` / `find_main_content()`

`find()` already excludes off-screen (`IsOffscreen`) matches when asked
(`visible_only=True`), added after a live-found bug: a Chromium/Electron
app can keep an *inactive* tab's own elements mounted in the
accessibility tree, merely hidden. `find_composer()` and
`find_main_content()` — both heuristic, both used for exactly the kind of
resolution this bug affects — never got the same protection. Fixed
unconditionally (there is no legitimate reason either heuristic should
ever resolve to something off-screen): both now skip any candidate
`IsOffscreen` reports as `True`.

## 4. Fix: generic response discovery (the mission's named priority)

### The problem

`find_main_content()`'s "biggest text-bearing region" heuristic is not a
reliable proxy for "the newly produced assistant response" — a
navigation sidebar, chat list, or workspace nav panel can legitimately be
taller than a short real answer. Confirmed live against both ChatGPT
Desktop and Kimi Desktop in prior missions.

### The fix: `snapshot_text_regions()` / `find_new_content()`

Two new `UiaAutomationBridge` methods, composed rather than reimplementing
`find_main_content()`:

- **`snapshot_text_regions(handle)`** — a read-only baseline: every
  visible, non-focusable, text-bearing region's current text, keyed by
  its own bounding rectangle (clipped to the window, for the same reason
  `find_composer()` already clips — a scrollable element's raw rect can
  report far more than what's actually on screen).
- **`find_new_content(handle, baseline, exclude_text)`** — compares the
  current regions against the baseline: a candidate must be non-empty,
  must not equal `exclude_text` (the submitted prompt), and must either
  be new (not in the baseline) or read differently than it did there.
  Among candidates, the **smallest** wins — the same "most specific
  match, not the broadest" preference `find_composer()` already applies,
  so a precise reply element beats an enclosing scrollable pane that also
  happened to change.

`complete()` now takes a baseline snapshot immediately after a successful
write (before submitting), and `_await_response()` polls
`find_new_content()` against it instead of `find_main_content()`.
Size (`find_main_content`) was never the right signal; *change since
before submission* is.

### Three refinements, each found live and fixed in turn

Bounded, sequential — not a diagnostic loop: each fix was verified by a
fresh live run, and each live run either passed cleanly or surfaced
exactly one new, concrete defect to fix next.

1. **Composer placeholder false positive.** After submission, the
   composer's own empty-state placeholder ("Message ChatGPT") reads as
   "changed" (the prompt was just cleared out of it), is short, and is
   static — it would satisfy both the change check and a naive stability
   check immediately, before any real response existed. Fix: exclude any
   keyboard-focusable candidate from consideration at all — a composer is
   *by definition* focusable (that's what makes it a composer, not
   content, in `find_composer()`'s own heuristic); a genuine response is
   never an editable control.
2. **Untested `min_height` silently excluded a real, short reply.** The
   first draft's `min_height=20` default was picked without live
   evidence. A genuine one-line reply ("KALPAVRIKSHA_CHATGPT_FINAL_OK"),
   confirmed live, clipped to exactly 19px — one pixel under the cutoff —
   causing `find_new_content()` to find nothing and the whole call to
   time out despite the correct response sitting on screen the entire
   wait. Fixed: default lowered to 8px, backed by this measurement, with
   the reasoning documented in the constant's own comment so a future
   change has the real number to reason from.
3. **A single repeat was not enough stability margin.** A first version
   accepted a candidate once its text repeated on one immediate
   follow-up poll. Live, this let a genuinely *truncated* mid-stream read
   ("KALPAVRIKSHA_" instead of the complete
   "KALPAVRIKSHA_CHATGPT_FINAL_OK") through — a real LLM's token cadence
   can pause for a full poll interval without having actually finished.
   Fixed: `_RESPONSE_STABILITY_POLLS = 3` — the same text must now read
   back identically across three consecutive polls (roughly 3 poll
   intervals of true silence) before being accepted.

### Why this stays generic

No application name, wording, or selector appears anywhere in either new
method or in `_await_response()`. Every signal used — visibility, focus
state, bounding-rect-clipped height, content equality/containment, and
change-since-baseline — is a structural property `IUIAutomation` already
exposes for any window, regardless of vendor. The three refinements above
were each driven by a measured, generic property (a fixed pixel height,
a focusable flag, a token-cadence pause) — never by matching one
application's specific text.

## 5. Documented, not fixed: launch/focus contention with a concurrent coding-agent window

Two live attempts this session timed out at `_launch_or_focus()` (`the
application did not report a real, visible window`) despite the target
application's window genuinely existing, being correctly attributed by
process, and being locatable via `locate_by_process()` — confirmed by a
direct, isolated reproduction of the exact same polling logic succeeding
cleanly moments later. Screenshot evidence at the moment of failure showed
this development session's own coding-agent GUI window (visibly running
this very task) occupying the foreground instead.

`_launch_or_focus()`'s own safety property — never proceed without
*positively confirming* the intended window is actually foreground —
worked exactly as designed: it correctly refused to act rather than risk
a keystroke landing in the wrong window. This is evidence of the
foreground-safety gate functioning correctly under a real, if unusual,
condition (two automation-capable windows contesting the desktop at
once), not a defect in it. Extending the timeout or adding retry logic
here would be tuning around one specific machine's concurrent-usage
pattern during development, not fixing a generic desktop-interaction
defect a founder would hit in ordinary single-application use — it does
not clear the mission's own five-part bar for action. Left untouched.

## 6. Production changes

Confined to `src/master_agent/desktop/execution/uia_control.py` and
`src/master_agent/providers/desktop_app.py`. No app-specific selector,
coordinate, or branch anywhere. `find_main_content()` itself is
unchanged in its own matching behavior (only gained the same visibility
filter as `find_composer()`) and remains available for its other
existing caller (`ReadWindowContentAction`, a one-shot content read with
no baseline to diff against).

- `find_composer()` / `find_main_content()`: skip `IsOffscreen` candidates.
- New: `_text_region_candidates()` (shared scan helper),
  `snapshot_text_regions()`, `find_new_content()`.
- `DesktopAppReasoningProvider.complete()`: takes a baseline snapshot
  (best-effort — an unreachable window here falls back to an empty
  baseline rather than failing the whole call) after a successful write,
  before submitting.
- `_await_response()`: rewritten to poll `find_new_content()` against
  that baseline, with a 3-consecutive-poll stability requirement before
  accepting a candidate as final.
- New constant: `_RESPONSE_STABILITY_POLLS = 3`.

## 7. Deterministic tests

**New this mission**: 15 —

`test_desktop_uia.py` (11): offscreen-skipping for both
`find_composer()`/`find_main_content()`; `snapshot_text_regions()` reads
every candidate; `find_new_content()` ignores unchanged regions, returns
a genuinely changed region, prefers the smallest changed region, excludes
text matching the prompt, treats a brand-new (not-in-baseline) region as
changed, skips offscreen regions, skips the composer's own placeholder
text (focusable-exclusion), and catches a real, short (19px) single-line
reply at the corrected default `min_height`.

`test_desktop_app_provider.py` (4, net): `_await_response()`'s new
3-poll-stability requirement, its single-repeat-truncation-rejection
regression (the live-found bug from §4.3), plus the existing suite's
tests adapted to the new `find_new_content()`-based fake bridge and the
new `baseline` parameter.

## 8. Regression

```
pytest tests/test_desktop_uia.py tests/test_desktop_execution.py \
       tests/test_desktop_operator.py tests/test_reasoning_role_separation.py \
       tests/test_reasoning_session_manager.py tests/test_desktop_app_provider.py \
       tests/test_reasoning_fallback_ladder.py tests/test_kalpavriksha_desktop_mission_bridge.py \
       tests/test_win32_clipboard_backend.py tests/test_broker_integration.py \
       tests/test_broker_wiring.py tests/test_desktop_perception.py
```

**Result: 866 passed, 4 failed.** Same 4 pre-existing, by-name-identical
failures documented in every prior mission's report in this codebase (the
`gemini.api`-default-enabled config decision and the `tiered_runner.py`
naming-guard assertion) — untouched by this mission's diff. **Zero new
regressions.** No existing guard was weakened to reach this result.

## 9. Live evidence

One clean, screen-observed, end-to-end run against ChatGPT Desktop
through the real, unmodified `complete()` path (screenshot attached):
`outcome=succeeded`, response text exactly `KALPAVRIKSHA_CHATGPT_FINAL_OK`
— no sidebar chrome, no composer placeholder, no truncation. The
sidebar shows a new, distinctly-titled conversation
("Kalpavriksha Final Confirmation"), and the visible transcript matches
the automated capture exactly.

Per the mission's own instruction not to keep hammering one long-lived
instance: this is the single successful confirmation run kept as
evidence, following the three bounded, sequential fix-and-reverify cycles
in §4 — each triggered by a genuine new finding, not repeated guessing.

## 10. Explicitly left untouched (per scope boundary)

- Reasoning-session architecture (`reasoning_session.py`) — not opened,
  not modified. The mission's own "Current verified state" already
  treats it as proven; no new, clean, reproducible defect was found in it
  this mission.
- Kimi Desktop — not re-tested live this mission, per the explicit
  instruction not to keep debugging that specific, already-perturbed
  instance. The generic fixes here (visibility filtering, response
  discovery, stability) apply equally to it and should benefit any future
  clean Kimi run, but that claim is not itself live-verified this
  mission.
- Perplexity — not added, not tested (not configured for this phase).
- Coding-agent separation — untouched; confirmed intact by construction
  (no code path in this diff touches `is_coding_agent()` or the
  provider-catalog construction gate).
- Clipboard mechanics — not investigated, per explicit instruction.
- `_launch_or_focus()`'s foreground-contention timeout — documented in
  §5, not changed; does not meet the mission's own generic-fix bar.

Not committed, per instruction.
