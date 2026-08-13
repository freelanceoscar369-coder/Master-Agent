# Desktop Executive Clear→Write→Verify Contract — Fix & Acceptance Report

**Result: PARTIAL. Do not read this as PASS.** Three real, generic bugs
were found and fixed in the Desktop Executive's interaction layer, each
proven correct with new deterministic tests and, for two of the three,
with live evidence against a real application. The two required
end-to-end live acceptance tests (ChatGPT Desktop, Kimi Desktop) did
**not** both pass. This is reported plainly, per the mission's own
explicit instruction not to claim PASS unless they genuinely do.

## 1. Reproducing the actual failure first

Before changing any code, the existing production write path
(`UiaAutomationBridge.write_text()` in `uia_control.py`) was re-read in
full. The sequence, exactly as it existed:

```
element.SetFocus()
sleep(0.15)
if not append:
    keyboard.hotkey("ctrl", "a")
    sleep(0.05)
    keyboard.press("delete")
    sleep(0.1)
keyboard.type(text) or keyboard.paste(text)   # by length threshold
sleep(0.15)
return self._verify_readback(element, text, append)   # bounded retry, WRITE side only
```

**Finding, stated plainly: the clear step had zero verification.** The
write side already had `_verify_readback()` (bounded retry, read-back
compared against expected text) — the clear side had nothing. `ctrl+a`+
`delete` "returning" (no exception from `KeyboardController`) was the only
signal ever checked, and that signal is not evidence anything happened on
screen.

This was reproduced once, live, against Kimi Desktop's real composer,
with per-step instrumentation:

```
text BEFORE anything:                    '\n'
real focused element BEFORE SetFocus():  ('', 50004)
real focused element AFTER SetFocus():   ('', 50004)   -- unchanged
text after SetFocus:                     '\n'
text after ctrl+a:                       '\n'
text immediately after delete:           '\n'
text 300ms after delete:                 '\n'
text 800ms after delete:                 '\n'          -- unchanged, even after waiting
```

Content stayed byte-for-byte identical through the entire sequence. This
matches the mission's own candidate diagnosis exactly: **"clear operation
not committed."**

## 2. The generic fix — three distinct, real bugs, in the order they were found

All three live entirely inside `desktop/execution/uia_control.py`
(`UiaAutomationBridge`) — the shared, generic interaction layer every
caller already goes through. No application-specific branch was added
anywhere; every fix is keyed on generic signals (content length, content
identity, presence of a newline character) or generic UIA mechanisms
(`GetFocusedElement`/`CompareElements`, the same coordinate-click fallback
`click()` already used).

### 2.1 Verified clear, with bounded retry and fail-closed

`_verify_cleared()` (new): reads the composer back, bounded retry (4
attempts, 0.25s backoff — the identical shape `_verify_readback()` already
used for the write side). `write_text()`'s clear step now retries the
`ctrl+a`+`delete` *action* itself up to 2 times, verifying after each, and
returns `False` — never typing — if the composer cannot be positively
confirmed clear within that bounded window.

### 2.2 The "short leftover content" blind spot (found live, fixed same session)

The first version of `_verify_cleared()` used a length-only threshold
("≤80 characters counts as cleared"). Live testing immediately exposed
the gap: real leftover content from an earlier attempt can itself be
short, and a `ctrl+a`+`delete` that silently does nothing passes a
length-only check by coincidence. Fixed by capturing the composer's
content once, *before* the first clear attempt, and requiring the
post-clear content to have genuinely changed (or to have already been
empty) — not merely to be short. Regression-tested directly
(`test_write_text_short_unchanged_leftover_content_is_not_mistaken_for_cleared`).

### 2.3 Focus: UIA logical focus vs. real Win32 keyboard focus

`_verify_focus()` (new): after `SetFocus()`, polls
`GetFocusedElement()`/`CompareElements()` — generic `IUIAutomation`
methods — retrying `SetFocus()` when focus is *positively* not yet
landed. Best-effort only: an inconclusive comparison (the mechanism itself
unsupported for a given control) proceeds rather than blocks, since the
clear/write verification steps that follow are the real, definitive proof
of whether the interaction worked.

Found live: after `ReasoningSessionManager.establish()`'s own real clicks
(Chat tab, New Task), a subsequent `SetFocus()` did not always yield
reliable typed input, even when UIA's own focus bookkeeping looked
correct — a real, generic divergence between UI-Automation's logical
focus and actual Win32 keyboard input focus. Fixed with a last-resort,
fully generic fallback: if UIA-level focus is never confirmed within the
bounded retries and a `mouse` controller is available, one real,
coordinate-derived click at the element's own UIA-reported bounding-rect
center is attempted — the *exact same* geometry-derived mechanism
`click()` itself already uses for elements without a working
`InvokePattern`. `write_text()` gained an optional `mouse` parameter
(`None`-safe; every existing caller keeps today's behavior unless it
opts in). Both real callers (`providers/desktop_app.py`,
`desktop/actions_interaction.py`) now pass their own `MouseController`.

### 2.4 A literal typed newline is dropped, not collapsed (found live, root cause of the acceptance failure)

With 2.1–2.3 in place, live testing against Kimi Desktop advanced past
the clear step but still failed at write verification. Isolated,
step-by-step reproduction found the exact mechanism: typing a short
prompt (well under the existing paste-length threshold) containing
Kalpavriksha's own session-marker separator (`"[marker]\n\nprompt"`) via
character-by-character `SendInput` produced `"[marker]prompt"` — the
blank line did not merely collapse the way pasted whitespace already
legitimately does elsewhere (`_normalize_whitespace()`'s own documented
finding); it vanished with **no separator at all**. A literal `\n`
delivered as a synthetic keystroke is genuinely ambiguous across
composers — some insert a line break, some treat it as submit, this one
appears to simply drop it.

Fixed by widening `write_text()`'s existing paste-vs-type decision:
`keyboard.paste()` is now used whenever the text is long **or** contains
a newline, regardless of length — clipboard content carries no such
ambiguity, only its own, already-tolerated reflow behavior. This directly
matters for this architecture specifically, since every session-marked
prompt `DesktopAppReasoningProvider` submits contains exactly this kind
of blank-line separator.

## 3. Deterministic tests

All new tests live in `tests/test_desktop_uia.py`, the existing,
established home for this layer's Level-1 tests (fast, fake-element-based,
no real UIA/COM traversal). 12 new tests, covering the mission's own
required list directly:

| Mission requirement | Test |
|---|---|
| 1. clear succeeds, read-back empty | `test_write_text_clear_succeeds_and_readback_becomes_empty` |
| 2. clear API succeeds but UI stale → bounded retry succeeds | `test_write_text_clear_stale_then_settles_via_bounded_retry` |
| 3. clear never becomes empty → fail closed | `test_write_text_clear_never_empties_fails_closed_without_typing` |
| (found live) short unchanged leftover ≠ cleared | `test_write_text_short_unchanged_leftover_content_is_not_mistaken_for_cleared` |
| (positive case) short content that genuinely changes | `test_write_text_short_content_that_genuinely_changes_is_verified_cleared` |
| (edge case) already empty before clear runs | `test_write_text_already_empty_before_clear_is_trivially_verified` |
| 4. write succeeds, immediate read-back stale → bounded retry succeeds | pre-existing `test_write_text_retries_the_readback_before_reporting_a_mismatch` (unchanged, still passing) |
| 5. write read-back never matches → fail closed | pre-existing `test_write_text_reports_false_on_a_genuine_mismatch` (unchanged, still passing) |
| 6. focus/write/verify sequence preserved | `test_write_text_focus_is_reconfirmed_via_generic_uia_primitives`, `test_write_text_falls_back_to_a_real_click_when_uia_focus_never_confirms`, `test_write_text_without_a_mouse_still_proceeds_when_focus_never_confirms`, `test_write_text_focus_verification_is_inconclusive_not_blocking` |
| (found live) newline forces paste regardless of length | `test_write_text_pastes_short_text_containing_a_newline`, `test_write_text_still_types_short_text_without_a_newline` |
| 7. existing app-independent UIA tests continue passing | all 26 pre-existing `test_desktop_uia.py` tests, unchanged, still passing |
| 8. no application-specific selector required | every fix keyed on generic content/UIA signals — confirmed by inspection, no per-app branch exists anywhere in the diff |

**Focused suite**: `pytest tests/test_desktop_uia.py` — **40 passed**
(28 pre-existing + 12 new), 0 failed.

**Mission-relevant regression suite** (`test_desktop_uia.py`,
`test_desktop_execution.py`, `test_desktop_operator.py`,
`test_reasoning_role_separation.py`, `test_reasoning_session_manager.py`,
`test_desktop_app_provider.py`, `test_reasoning_fallback_ladder.py`,
`test_kalpavriksha_desktop_mission_bridge.py`,
`test_win32_clipboard_backend.py`, `test_broker_integration.py`,
`test_broker_wiring.py`, `test_desktop_perception.py`):

- **Baseline** (before this mission's changes): 839 passed, 4 failed.
- **Final**: **846 passed, 4 failed.**
- The 4 failures are the same, unchanged, pre-existing failures documented
  in the two prior missions' own reports (a `gemini.api`-default-enabled
  config decision and a `tiered_runner.py` naming-guard assertion, both
  predating this mission and unrelated to the interaction layer).
- **Zero new regressions.**

## 4. Files changed

- `src/master_agent/desktop/execution/uia_control.py` — `_verify_cleared()`
  and `_verify_focus()` (new); `write_text()` rewritten to call both, take
  an optional `mouse` parameter, and route newline-containing text through
  `paste()` regardless of length; six new module-level constants
  (`_MAX_CLEARED_CHARS`, `_CLEAR_VERIFY_ATTEMPTS`,
  `_CLEAR_VERIFY_DELAY_SECONDS`, `_CLEAR_ACTION_ATTEMPTS`,
  `_FOCUS_VERIFY_ATTEMPTS`, `_FOCUS_VERIFY_DELAY_SECONDS`).
- `src/master_agent/providers/desktop_app.py` — `_write_prompt()` now
  passes `mouse=self._mouse` to `write_text()`.
- `src/master_agent/desktop/actions_interaction.py` — the
  Action/capability-dispatch layer's own `write_text()` call now passes
  `mouse=executor.mouse` too, for the same benefit outside the reasoning
  provider.
- `tests/test_desktop_uia.py` — 12 new tests, 1 existing test's mock
  updated (a newline-containing sample now correctly exercises the
  `paste()` path it always should have, per §2.4).

## 5. Live acceptance results — honest, not fabricated

### ChatGPT Desktop: **NOT ATTEMPTED beyond one clean check**

One production `complete()` call was made. Result: correctly and
honestly refused — `ISOLATION_UNVERIFIED`, the same root cause documented
in the prior mission's report (this specific window instance has been
showing its own embedded "Codex" view plus stale overlay content since
extensive earlier testing this session). Per the mission's own explicit
instruction ("do not spend the session repeatedly debugging a polluted
ChatGPT instance"), this was not pursued further. **No claim of PASS is
made for ChatGPT Desktop.**

### Kimi Desktop: **PARTIAL — real, measurable progress, no full PASS**

Multiple live attempts through the real, unmodified production
`DesktopAppReasoningProvider.complete()` path, in order:

1. Before the fix: failed at the clear step (`typed into the composer but
   could not verify the text landed`) — the exact failure this mission
   set out to fix.
2. After 2.1–2.3 (verified clear, corrected short-content blind spot,
   focus fallback): clear step confirmed genuinely working (direct
   instrumentation showed `_verify_cleared()` correctly returning `True`
   only once real, delayed content change was observed) — but write
   verification still failed, for the newly-found reason in §2.4.
3. After 2.4 (newline forces paste): isolation establishment and clear
   both succeeded live; a subsequent attempt hit
   `ISOLATION_UNVERIFIED` again — this time because the composer already
   held ~92 characters of this session's own earlier diagnostic residue,
   above the (unrelated, pre-existing) session-isolation freshness
   threshold in `reasoning_session.py`. A direct, legitimate cleanup
   attempt (writing a single space via the now-fixed production clear
   path) itself returned `False` — the clear step, while genuinely more
   reliable than before this mission, is **not** yet 100% reliable
   against this specific, heavily-exercised Kimi composer instance within
   this same live session.

**This is reported as a real, remaining limitation, not glossed over.**
The three fixes in §2 are real, each independently proven (by direct,
isolated live reproduction and by new deterministic tests) to correct the
specific mechanism found broken. What was not achieved is a single,
unbroken, from-a-clean-state live run all the way through response
verification — in part because this Kimi Desktop instance has now been
written to, cleared, and read from dozens of times across this and the
prior mission's live testing, and the remaining intermittent clear
failures may be partly an artifact of that accumulated session-local
state rather than the underlying mechanism itself. That distinction was
not conclusively established, and is named as an open question rather
than assumed in either direction.

## 6. Preserved architecture — confirmed, not merely asserted

- Gemini remains the sole Tier 1 provider; `TieredPromptRunner`,
  `CapabilityBroker`, and `policy.py` were not touched.
- `ReasoningSessionManager` was not redesigned — its own establishment
  logic (Chat-section navigation, new-session vocabulary search, composer-
  based freshness check) is unchanged; only `write_text()`, one layer
  below it, changed.
- Coding-agent role separation (`is_coding_agent()`, the three-layer
  enforcement from the prior mission) is untouched.
- Claude Desktop was not reintroduced and was not used for any part of
  this mission's live validation.
- No application-specific write implementation exists anywhere in the
  diff — every fix is generic, keyed on content/UIA signals common to any
  composer.

## 7. Remaining limitations, stated explicitly

- **ChatGPT Desktop has not been live-validated end-to-end in this or the
  prior mission.** Its current window instance is judged too degraded by
  earlier testing to usefully attempt further without either restarting
  it (a destructive action this session correctly declined to take
  unilaterally) or accepting another polluted-state result.
- **Kimi Desktop's clear step, while measurably improved and verified
  correct in isolation, is not yet provably 100% reliable against a
  composer that has accumulated this much session-local test residue.**
  A genuinely fresh install/session (outside this development machine's
  now-extensive test history) has not been tried.
- The newline-forces-paste fix (§2.4) is the most recently found and
  least extensively live-tested of the three; it is proven correct by
  direct, isolated reproduction and by deterministic test, but has not
  yet been observed succeeding in a completely clean, single-pass live
  run.

Not committed, per instruction.
