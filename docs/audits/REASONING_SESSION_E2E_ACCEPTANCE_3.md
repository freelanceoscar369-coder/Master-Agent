# Final Reasoning Desktop Acceptance & Closure — Report

**Result: the session-establishment fix and a genuine `write_text()` defect
are both fixed and live-proven. Kimi Desktop's full interaction chain
(session establish → stale draft cleared → prompt written → submitted →
real, correct response received) is directly confirmed live, by UIA
inspection. `complete()`'s own automated response-capture did not detect
that response — a distinct, pre-existing, already-documented limitation of
`find_main_content()`'s heuristic, not something this mission introduces or
is scoped to fix. ChatGPT Desktop remains blocked at composer location by
machine-accumulated stale-draft geometry, unchanged and correctly not
"fixed" via threshold-widening, per explicit instruction.**

## 1. The corrected session-establishment behavior

`ReasoningSessionManager.establish()` previously required the resulting
surface's *content* to look empty after a "new chat" click, conflating an
unsent composer draft (safe — never submitted, no conversation history)
with an existing conversation's real message history (must never be
hijacked). Both real target applications had accumulated stale, unsent
draft text from earlier testing, surviving even a full machine restart —
this incorrectly rejected both with `ISOLATION_UNVERIFIED`.

**Fix**: the two content-freshness checks (`_verify_fresh_surface()`,
`_verify_fresh_main_content()`) were removed entirely. `establish()` now
treats the verified click on a generic "start a new conversation" control
as the whole isolation guarantee — the same mission-provided distinction:
unsubmitted composer draft = safe to clear; existing submitted
conversation = must not be hijacked. Cleanup of any leftover draft is left
entirely to the already-existing, already-verified clear step inside
`UiaAutomationBridge.write_text()`, which is exactly its job.

Confirmed immediately in live testing: both ChatGPT Desktop and Kimi
Desktop's `complete()` calls advanced past session establishment for the
first time in several missions — the failure moved from
`ISOLATION_UNVERIFIED` to a write-stage failure, proving the fix itself
correct.

**Tests**: `tests/test_reasoning_session_manager.py` rewritten — the fake
UIA bridge used throughout no longer even offers
`find_composer`/`find_main_content`/`read_text`, so any regression back
toward inspecting post-click content would break every test in the file,
not just a targeted one. A dedicated regression guard
(`test_establish_never_inspects_composer_or_conversation_content`) makes
this explicit.

## 2. A second, distinct, real defect found and fixed: `write_text()`

With the isolation fix in place, both applications advanced to the write
stage and both failed there — `"typed into the composer but could not
verify the text landed"`. Root-caused live, not guessed, through a single
continuous, narrowly-scoped diagnostic:

- Kimi Desktop's composer was genuinely locatable and genuinely clearable
  (`_verify_cleared()` correctly confirmed empty).
- A **manual** reproduction of the clear-then-paste sequence, called
  directly, worked every time — proving the underlying keystroke/paste
  mechanism is sound.
- Calling the real, unmodified `UiaAutomationBridge.write_text()` on the
  exact same composer, in the exact same state, reliably failed.
- Instrumenting `write_text()` step-by-step isolated the exact divergence:
  its first branch, `ValuePattern.SetValue()`, is tried before ever
  reaching the (proven-reliable) keystroke/paste path. Direct inspection
  confirmed Kimi's composer exposes a genuinely writable `ValuePattern`
  (`CurrentIsReadOnly` reports `False`) — but calling `SetValue()` on it
  raises **no exception** and **silently does not change the composer's
  content**. `write_text()` trusted "no exception" as "it worked," and
  returned the correctly-negative verification as final failure — it
  never attempted the keystroke path that was independently proven to
  work on this exact composer.

**Fix** (`src/master_agent/desktop/execution/uia_control.py`,
`write_text()`): when `SetValue()` raises nothing but the subsequent
read-back verification shows it did not actually land, execution now
falls through to the keystroke/paste path instead of returning a false
failure. Minimal, generic, no new mechanism — the fallback path already
existed and was already proven correct; the only change is not giving up
before trying it.

This is a genuine, reproducible, machine-independent defect: a UIA
control advertising a writable `ValuePattern` that silently no-ops is a
property of Kimi Desktop's own Electron accessibility implementation, not
of this development machine's accumulated test state. It would recur on
any machine running this exact application version.

**Tests**: `tests/test_desktop_uia.py` —
`test_write_text_falls_back_to_keystrokes_when_value_pattern_silently_no_ops`,
simulating exactly this: a writable (non-read-only) `ValuePattern` whose
`SetValue()` is a real no-op, and asserting the keystroke path is reached
and succeeds.

## 3. Live acceptance — Kimi Desktop

Real, unmodified `DesktopAppReasoningProvider.complete()` call, prompt
`Reply with exactly: KALPAVRIKSHA_KIMI_FINAL_OK`:

- `outcome=succeeded`, `ok=True`, session marker recorded
  (`Kalpavriksha Reasoning — Kimi Desktop · 2026-08-13 19:04:56 ·
  9129ac67`).
- A direct, read-only check immediately after showed the composer was
  genuinely empty (`'\n'`) — confirming the prompt was actually submitted
  and accepted by the application, not merely written and abandoned.
- **However**, the response text `complete()` itself returned was wrong:
  left-sidebar navigation chrome (`"Work / Chat / New Task / Dashboard /
  ... / Reconnecting… / Your workspace is getting ready"`), not the real
  reply, and did not contain the required marker.
- A direct, targeted, read-only search of the window's full UIA
  descendant tree (not `find_main_content()`'s heuristic) found the real
  response: an element named exactly **`KALPAVRIKSHA_KIMI_FINAL_OK`**
  (present twice, plus the full submitted prompt echoed back with its
  session marker) — proving Kimi Desktop **did** receive and correctly
  answer the real, isolated, Kalpavriksha-owned prompt.

**Root cause of the capture miss**: `find_main_content()`'s own heuristic
— "the largest text-bearing region in the window" — is documented in its
own docstring as approximate. Kimi's left navigation sidebar (many nav
items, an empty chat list, connection-status text) is a larger
text-bearing region than a short, one-line correct answer
(`KALPAVRIKSHA_KIMI_FINAL_OK`) sitting in the actual chat transcript pane.
`_await_response()`'s own verification (only "differs from the submitted
prompt") is too weak to catch this: sidebar chrome trivially differs from
the prompt, so it was accepted as "the response."

**This was not fixed in this mission.** It is a distinct failure from the
`write_text()` defect above — it does not block session isolation, draft
clearing, prompt writing, or submission (all four are now confirmed
correct and working for Kimi Desktop, live). It only affects the final,
fully-automated response-capture step, and it is exactly the class of
issue the founder has already named as the next focus area ("we will
return to the Expert Desktop Executive"). Modifying `find_main_content()`
or `_await_response()`'s verification strength was judged out of this
mission's scope — this mission's own instructions bound it to the
session-establishment/draft-clearing correction and to fixing only a
failure discovered at "that exact point," which was `write_text()`, not
response capture.

## 4. Live acceptance — ChatGPT Desktop

Unchanged from the prior mission's finding, re-confirmed this mission:
`outcome=rejected`, `error="typed into the composer but could not verify
the text landed"` — `find_composer()` cannot locate ChatGPT's composer at
all, because accumulated stale draft content (from four prior missions'
testing, ~6,000+ characters, never sent) has grown it to roughly 79% of
the window's height, beyond even the already-widened geometric threshold.

Per this mission's explicit "What NOT to do" list, this was **not**
addressed by widening `find_composer()`'s thresholds — that would tune
the Universal Desktop Executive to this one machine's accumulated test
debris, not fix a generic defect a real founder would encounter on a
normally-used installation. This is honestly documented as
environment-specific, exactly as the immediately-prior mission's report
already established.

## 5. Regression

```
pytest tests/test_desktop_uia.py tests/test_desktop_execution.py \
       tests/test_desktop_operator.py tests/test_reasoning_role_separation.py \
       tests/test_reasoning_session_manager.py tests/test_desktop_app_provider.py \
       tests/test_reasoning_fallback_ladder.py tests/test_kalpavriksha_desktop_mission_bridge.py \
       tests/test_win32_clipboard_backend.py tests/test_broker_integration.py \
       tests/test_broker_wiring.py tests/test_desktop_perception.py
```

**Result: 848 passed, 4 failed.** All 4 failures are the same,
by-name-identical, pre-existing failures documented in both prior
missions' reports (the `gemini.api`-default-enabled config decision and
the `tiered_runner.py` naming-guard assertion) — untouched by any change
in this mission's diff. **Zero new regressions.** One new test added
(`test_write_text_falls_back_to_keystrokes_when_value_pattern_silently_no_ops`).

## 6. Architectural rules — preserved

- No coding-agent session was used, reused, or typed into at any point.
- No app-specific selector, coordinate, or branch was added anywhere in
  either diff (`reasoning_session.py`'s prior correction, `uia_control.py`'s
  `write_text()` fallback fix) — both changes are fully generic.
- No clipboard-history investigation, no `find_composer()` threshold
  change, no new diagnostic mechanism, no redesign of the Universal
  Desktop Executive.
- Kalpavriksha's own isolated session was used throughout — every live
  attempt this mission clicked a genuine "new chat"/"new task" control
  before writing anything, and the marked prompt (`[Kalpavriksha
  Reasoning — Kimi Desktop · ...]`) is visible verbatim in the real
  submitted content found in Kimi's UIA tree.

## 7. Closure assessment — stated plainly, against the mission's own criteria

The mission's closure criteria: *"ChatGPT reasoning fallback works
end-to-end, OR Kimi reasoning fallback works end-to-end, with the other
provider either validated or honestly documented as environment-specific."*

**Not met in the strict, fully-automated sense** — no single
`complete()` call returned `ok=True` with the marker present in its own
returned response text for either provider.

**What is proven, concretely, with direct live evidence:**

- The session-establishment defect this mission was created to fix is
  fixed and live-confirmed on both applications.
- A second, independent, genuine defect (`write_text()`'s
  `ValuePattern.SetValue()` silent no-op) was found through one
  continuous, bounded diagnostic and fixed with a minimal, generic,
  tested change.
- Kimi Desktop's full interaction chain — isolated session, stale draft
  cleared, correct prompt written and confirmed submitted (composer
  verified empty afterward), and a **real, correct response from the
  application containing the exact required marker** — is directly,
  concretely proven, by UIA evidence read straight from the live window,
  not inferred or assumed.
- The only remaining gap for Kimi is `complete()`'s own automated
  response-capture step picking the wrong UI region — a pre-existing,
  already-documented "approximate" heuristic limitation of
  `find_main_content()`, unrelated to session isolation, drafting, or
  submission, and explicitly the kind of Desktop Executive hardening work
  the founder has already named as the next, separate engineering focus.
- ChatGPT Desktop remains honestly documented as environment-specific,
  blocked by accumulated stale-draft geometry this mission correctly
  declined to paper over with a threshold change.

Per this mission's own instruction to report plainly rather than
manufacture a PASS: this chapter should be considered **substantively but
not formally closed** — the underlying reasoning-provider mechanics
(isolation, clearing, writing, submission) are now proven correct and
live-working for at least one real application, with a real, verified,
marker-matching response confirmed by direct inspection. The remaining
gap is narrowly scoped to response-capture reliability, which is squarely
inside the "Expert Desktop Executive" work the founder has already
indicated comes next.

Not committed, per instruction.
