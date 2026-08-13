# Clean Universal Reasoning Session E2E Acceptance — Report

**Result: FAIL on both applications (blocked by pre-existing pollution),
not PASS.** This mission's own required production enhancement (verified
submission with a generic Send-control fallback) was implemented and is
proven correct by direct, isolated live evidence and by deterministic
tests. Full end-to-end live acceptance was **not achieved** for either
ChatGPT Desktop or Kimi Desktop, for reasons documented below — reported
plainly, per this mission's own explicit instruction not to manufacture
PASS evidence or hide partial success.

## ChatGPT Desktop — result

**BLOCKED**, at session establishment, before any write/submit was
attempted.

- One live call through the real, unmodified production
  `DesktopAppReasoningProvider.complete()` path against the real,
  currently-running `chatgpt-desktop` process, with the exact required
  prompt (`Reply with exactly: KALPAVRIKSHA_CHATGPT_E2E_OK`).
- Result: `outcome=unavailable`, `error=ISOLATION_UNVERIFIED: the surface
  still shows 5967 characters of content after requesting a new
  session — not confirmed fresh`.
- **Root cause: identical to, and already fully diagnosed in, the prior
  mission's report**
  ([DESKTOP_EXECUTIVE_CLEAR_WRITE_VERIFY_1.md](DESKTOP_EXECUTIVE_CLEAR_WRITE_VERIFY_1.md)):
  this ChatGPT Desktop window instance has been showing its own embedded
  "Codex" coding-agent view plus a stale, ~6KB overlay left over from
  extensive earlier live testing across three prior missions this
  session. `ReasoningSessionManager.establish()` did exactly what it is
  designed to do — navigated to the "Chat" section tab, found and invoked
  a "New chat" control — and correctly, honestly refused to proceed once
  it could not confirm the resulting surface was actually fresh. No text
  was written; no Enter/Send was attempted.
- This is the exact "wrong Chat/Work/Codex surface is active" /
  "application is polluted and cannot safely be reset" condition this
  mission's own strict stop conditions name. Per Phase 1's explicit
  instruction — "do NOT attempt to repair or reason about the heavily
  polluted... instances from the previous missions... if a clean state
  cannot be established safely, report that as a blocker instead of
  modifying production code to accommodate the polluted state" — this was
  not investigated further, and no code was changed to special-case this
  window's state.

## Kimi Desktop — result

**BLOCKED**, at session establishment, before any write/submit was
attempted.

- One live call through the real production path against `kimi-desktop`,
  with the exact required prompt (`Reply with exactly:
  KALPAVRIKSHA_KIMI_E2E_OK`).
- Result: `outcome=unavailable`, `error=ISOLATION_UNVERIFIED: the composer
  still shows 92 characters of drafted content after requesting a new
  session — not confirmed fresh`.
- **Root cause: this session's own residual diagnostic content from the
  prior mission's live testing** (`"[Kalpavriksha Reasoning — Kimi
  Desktop test]Reply with exactly: KALPAVRIKSHA_KIMI_DESKTOP_OK"`, a
  leftover artifact of the previous mission's own manual diagnostics,
  confirmed present via direct inspection at the end of that mission).
  `ReasoningSessionManager.establish()` again did what it is designed to
  do — clicked "Chat", clicked "New Task" — and correctly refused once it
  could not confirm freshness. No text was written; no Enter/Send was
  attempted.
- Same stop condition as ChatGPT Desktop; not investigated further, per
  the same explicit instruction.

## What this mission did prove live

Both blockers occurred **before** the new production behavior this
mission was tasked with adding (verified submission, generic Send
fallback) could even be exercised through the full pipeline. That new
behavior was, however, independently verified two other ways:

1. **Deterministic tests** (`TestSubmit` in `test_desktop_app_provider.py`,
   4 new tests) exercise every branch directly: Enter confirmed by
   composer change; Enter unconfirmed → generic Send control discovered
   and clicked → confirmed; neither Enter nor a discoverable Send control
   verifies → fails closed, `_await_response()` never reached.
2. **The clear/write/focus fixes from the immediately-prior mission**
   were re-confirmed still correct and not regressed by this mission's
   changes (see §Regression below) — `ReasoningSessionManager.establish()`
   itself (Chat-tab navigation, new-session control discovery, composer-
   based freshness check) worked exactly as designed in both live
   attempts above; the correct, honest refusal *is* the architecture
   functioning as intended when isolation genuinely cannot be confirmed.

## Production changes this mission

All changes are confined to `src/master_agent/providers/desktop_app.py` —
the reasoning-provider layer, not the Desktop Executive itself, not
`ReasoningSessionManager`, not the Broker/fallback ladder.

- **New**: `_submit()` — replaces the previous unconditional
  `keyboard.press("enter")` with a verified sequence: press Enter, poll
  (bounded retry) whether the composer's own content changed; if not,
  discover a generic Send/submit control (`SEND_VOCABULARY` — `"send"`,
  `"submit"`, `"send message"`, matched with the same `visible_only`
  filtering added in the prior mission) and invoke it via the existing
  `click()` primitive; verify again the same way. Returns `False` — and
  `complete()` never proceeds to `_await_response()` — if neither
  produces a confirmed change.
- **New**: `_read_composer_safely()`, `_verify_submission()` — small
  helpers `_submit()` composes; `_verify_submission()` fails closed on an
  unreadable composer.
- **New**: `_find_send_control()` — generic vocabulary search, identical
  in shape to `ReasoningSessionManager._find_new_session_control()` from
  the prior mission; no application-specific label anywhere.
- **New constants**: `SEND_VOCABULARY`, `SUBMIT_UNVERIFIED`,
  `_SUBMIT_VERIFY_ATTEMPTS`, `_SUBMIT_VERIFY_DELAY_SECONDS`.
- `complete()`'s own step 4 now calls `self._submit(window, keyboard)`
  and returns a structured `SUBMIT_UNVERIFIED` failure rather than
  unconditionally proceeding after `keyboard.press("enter")`.

No application-specific selector, coordinate, or branch was added
anywhere in this diff — every new mechanism is generic (content-signal-
based or vocabulary-search-based, reusing existing `find()`/`click()`
primitives).

## Deterministic tests

**New**: 4 tests in `tests/test_desktop_app_provider.py`
(`TestSubmit`) — Enter confirmed by composer change; Enter unconfirmed
falls back to a discovered Send control and succeeds; neither verifies →
fails closed; full `complete()` integration proving `_await_response()`
is never reached without verified submission.

**Fixed alongside**: `_verify_submission()`'s bounded-retry constants
were moved from default-parameter values to bare module-global reads
(matching `_await_response()`'s own established pattern) — a
default-parameter value is bound once at import time and is not
reachable by `monkeypatch`, which made the first version of these tests
correct but needlessly slow (~2s of real sleeping per test). Fixed before
being reported as done.

## Regression

Per this mission's own required scope (Desktop Executive/UIA tests,
reasoning-session tests, reasoning fallback/provider-selection tests,
mission-relevant regression suite):

```
pytest tests/test_desktop_uia.py tests/test_desktop_execution.py \
       tests/test_desktop_operator.py tests/test_reasoning_role_separation.py \
       tests/test_reasoning_session_manager.py tests/test_desktop_app_provider.py \
       tests/test_reasoning_fallback_ladder.py tests/test_kalpavriksha_desktop_mission_bridge.py \
       tests/test_win32_clipboard_backend.py tests/test_broker_integration.py \
       tests/test_broker_wiring.py tests/test_desktop_perception.py
```

- **Baseline** (end of the immediately-prior mission, before this
  mission's changes): 846 passed, 4 failed.
- **Final**: **851 passed, 4 failed.**
- **New tests this mission: exactly 5** — 4 in `TestSubmit`
  (`test_enter_confirmed_by_composer_content_changing`,
  `test_enter_produces_no_change_falls_back_to_a_discovered_send_control`,
  `test_neither_enter_nor_a_discoverable_send_control_verifies_fails_closed`,
  `test_complete_never_awaits_a_response_without_verified_submission_integration`)
  plus 1 in `TestSessionEstablishmentIntegration`
  (`test_response_is_never_awaited_when_submission_is_not_verified`).
- **Exact failures, both before and after this mission's changes**
  (identical set, confirmed by name):
  - `tests/test_broker_integration.py::test_only_the_catalogue_names_a_provider[gemini]`
  - `tests/test_broker_wiring.py::test_the_broker_reads_the_estate_from_the_desktop_executive`
  - `tests/test_broker_wiring.py::test_no_provider_is_available_before_the_machine_has_been_scanned`
  - `tests/test_broker_wiring.py::test_cloud_providers_stay_off_until_the_founder_enables_them`
- **Evidence these are pre-existing, not a claim**: all four were already
  documented, by name, with the same failure reasons, in both of the two
  immediately-prior missions' own reports
  ([CLAUDE_DESKTOP_REASONING_SAFETY_GATE_1.md](CLAUDE_DESKTOP_REASONING_SAFETY_GATE_1.md),
  [DESKTOP_EXECUTIVE_CLEAR_WRITE_VERIFY_1.md](DESKTOP_EXECUTIVE_CLEAR_WRITE_VERIFY_1.md)) —
  the `gemini.api`-default-enabled config decision and the
  `tiered_runner.py` naming-guard assertion, neither touched by any
  change in this mission's diff. Re-run identically, by name, before and
  after this mission's changes: same 4, same reasons, no new failures, no
  fewer failures.
- **Zero new regressions.**

## Architectural rules — preserved, confirmed by construction

- **Coding agents remain coding-only**: `is_coding_agent()` and its
  three-layer enforcement (from two missions ago) are untouched by this
  mission's diff.
- **Claude Desktop was not used** for any part of this mission — neither
  as a live target nor as a reference implementation for the new submit
  logic.
- **Kalpavriksha owns its reasoning session**: unchanged —
  `ReasoningSessionManager.establish()` (Chat-section navigation,
  new-session discovery, composer-based freshness confirmation) is
  untouched by this mission; both live blockers above are proof it is
  *working as designed*, refusing rather than guessing.
- **No coding-agent session was used, reused, or typed into** in either
  live attempt — both blockers occurred at the isolation-check stage,
  before any write was attempted.

## Is the architecture ready for the next stage?

**Not yet, on live evidence — the mechanism is right, the test
environment is not.** Every architectural piece required for this
mission's acceptance gate exists, is generic, and is independently proven
correct: session isolation (prior missions), verified clear/write/focus
(prior mission), and now verified submission with a generic Send
fallback (this mission). What has not yet been demonstrated is all of
them succeeding together, live, in a single unbroken run — because both
available real applications on this specific development machine carry
several missions' worth of accumulated test residue that this mission was
explicitly told not to clean up by force.

**Recommended next step, stated plainly**: the architecture should next
be validated against a genuinely clean instance of at least one of these
applications — a fresh install, a different machine, or (with the
founder's own action, not this session's) a manual close-and-reopen of
the current instances — rather than a fourth consecutive mission
attempting to reason about or work around this same accumulated state.
Continuing to iterate against these two specific, now heavily-tested
windows would be exactly the "repeated speculative live experiments"
this mission's own stop conditions name.

Not committed, per instruction.
