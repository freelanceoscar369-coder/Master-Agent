# Persistent Kalpavriksha Reasoning Sessions — Implementation & Live Validation

**Status: Core objective proven live for ChatGPT Desktop (find, reuse,
and re-reuse the exact-named "Kalpavriksha Reasoning" conversation across
independent calls, confirmed both by the automated result and by direct
screenshot evidence). Perplexity Desktop's session mechanics (create,
write, submit, real response generation) proven live for the first time
ever, with two remaining gaps honestly documented, not hidden. Kimi
Desktop blocked by the same pre-existing, already-documented environment
contamination the mission explicitly said not to re-debug.**

## 1. What changed

### Architecture (`src/master_agent/providers/reasoning_session.py`)

Replaced "create a new, anonymous session every call" with "find-or-
create the one persistent, exact-named `Kalpavriksha Reasoning`
conversation, and reuse it":

- **`find_named_session(handle)`** — exact-name search
  (`find(name_exact=DEDICATED_SESSION_NAME, visible_only=True)`), never a
  substring match. This is the direct fix for the mission's own named
  problem: a substring search for `"Kalpavriksha Reasoning"` matched an
  unrelated historical conversation during the App Knowledge Acquisition
  mission's own live pass.
- **`open_named_session(handle, element)`** — click the already-resolved
  element via the existing generic `click()` primitive.
- **`create_named_session(handle, keyboard, marker)`** — unchanged
  isolation guarantee from the prior architecture (a verified click on a
  generic "start a new conversation" control), plus a new, best-effort
  rename step.
- **`_rename_current_session(handle, keyboard, new_name)`** — new
  capability: tries a direct rename control
  (`RENAME_ACTION_VOCABULARY`), falling back to a "more options"-style
  trigger (`RENAME_TRIGGER_VOCABULARY`) if none is directly visible;
  writes the new name into whatever element real OS keyboard focus lands
  on afterward (`UiaAutomationBridge.get_focused_element_in_window()` —
  new primitive, safety-checked to belong to the target window, guarding
  against the same cross-application-focus risk `_launch_or_focus()`
  already guards against); confirms with Enter; verifies by re-running
  `find_named_session()`. **Never fatal** — a genuinely created,
  isolated conversation is a valid reasoning surface for *this* call
  whether or not the rename succeeds; failure only means a *future*
  call's `find_named_session()` will not find it and will create another
  new one instead — a graceful degrade to the prior architecture's own
  behavior, never a regression below it.
- **`establish()`** (public entry point, unchanged name for
  `desktop_app.py`'s own call site) now: navigate to Chat (unchanged,
  best-effort, no-op for Perplexity's own single unified surface) →
  `find_named_session()` → reuse on a hit, `create_named_session()` on a
  miss.
- **`SessionEstablishment`** gained `reused: bool` and `renamed: bool`
  fields, surfaced in `ProviderResult.detail` as `session_reused`/
  `session_renamed` — the acceptance table below is built from these,
  not from assumption.

### One generic vocabulary gap fixed, found live

Perplexity Desktop's own "start a new conversation" control has the
accessible name **exactly `"New"`** — too short to contain any of the
existing, more specific vocabulary phrases (`"new chat"`, `"new task"`,
...) as a substring, so the search failed entirely on first contact.
`"new"` was added to `NEW_SESSION_VOCABULARY`, deliberately **last** (a
bare word is the phrase most likely to false-positive match something
unrelated in a busier window — "Renew subscription", a "News" section —
so every more specific, lower-risk phrase is tried first). This is a
generic vocabulary addition, not a Perplexity-specific branch — any
application whose control is this terse benefits identically.

### `desktop_app.py`

`keyboard = KeyboardController()` moved earlier (session establishment
may itself need to type a rename), passed into `establish()`, and reused
for the write/submit steps rather than recreated. `ProviderResult.detail`
now carries `session_reused`/`session_renamed`.

## 2. Acceptance table

| Provider | Configured | Named session created | Reused | E2E validated |
|---|---|---|---|---|
| ChatGPT Desktop | Yes | Yes (found pre-existing) | **Yes** — confirmed twice, automated + visual | **Yes**, with a caveat — see §3 |
| Kimi Desktop | Yes | No — blocked before session establishment | N/A | No — documented blocker, see §5 |
| Perplexity Desktop | Yes | Yes (created) | No — rename did not succeed this pass | No — see §4 |

## 3. ChatGPT Desktop — live evidence

**Call 1**: `complete()` returned `outcome=succeeded`,
`session_reused=True`, `session_renamed=True`, response text exactly
`KALPAVRIKSHA_PERSISTENT_CALL1_OK` (marker present: `True`). Screenshot
confirms the conversation's own header reads **"Kalpavriksha Reasoning"**
— an exact-name match that already existed (auto-titled by ChatGPT
itself during an earlier mission's own submission) — found and reused,
not created fresh.

**Call 2** (a wholly separate `complete()` invocation, no in-memory state
shared with call 1): `session_reused=True` again — the *same* named
conversation was found and reused, confirmed by the sidebar showing it
selected/highlighted in both screenshots and the header title unchanged.
This is the mission's own required proof: **the second request did not
create another conversation.**

**The caveat**: call 2's automated response capture returned stale text
(`KALPAVRIKSHA_CHATGPT_FINAL_OK` — a reply from a *different, earlier*
mission's exchange, still present higher up in this same, now
multi-turn, reused conversation) instead of the genuinely new
`KALPAVRIKSHA_PERSISTENT_CALL2_OK`. A direct screenshot at the end of
call 2 shows **the real, correct response was on screen the whole
time**, positioned exactly where expected, directly below its own
correctly-marked prompt — the actual reasoning chain (session reuse →
write → submit → real generation) worked completely. Only the automated
`find_new_content()` response-discovery mechanism (built and proven
against always-fresh, single-exchange conversations in the immediately
prior mission) picked the wrong region once the conversation had grown
to three exchanges.

**This is a new, distinct, honestly-reported limitation, not a
session-persistence failure**: `find_new_content()`'s baseline-diff
approach was validated against conversations that go from empty to one
exchange; a long-lived, reused, multi-turn conversation is a genuinely
different shape of problem (which of several *existing* exchanges, not
"is there any new content at all") that this mission's own scope
("persistent session identity... do not expand into another Desktop
Executive rewrite") explicitly does not authorize fixing here. Recorded
as a known gap for the Desktop Executive's own future work, not silently
absorbed into a false "fully validated" claim.

## 4. Perplexity Desktop — live evidence

**First bounded validation, this application's first live contact of
any kind**: after fixing the `"New"`-vocabulary gap (§1), a full
`complete()` call succeeded through launch → session creation → write →
submit, and — confirmed by direct screenshot — **the real, correct
response, `KALPAVRIKSHA_PERPLEXITY_CALL1_OK`, appeared on screen exactly
where expected**, directly below its correctly-marked prompt, in
Perplexity's own genuine "Answer" surface (not the `Computer` toggle,
never engaged).

**Two things did not yet work, both honestly reported rather than
hidden:**

1. **Rename did not succeed** (`session_renamed=False`) — this
   session's `RENAME_ACTION_VOCABULARY`/`RENAME_TRIGGER_VOCABULARY`
   phrases did not match whatever rename affordance Perplexity Desktop
   may or may not expose; that affordance was not investigated this
   pass (out of this mission's bounded-validation scope). Consequence:
   a *future* call will not find this conversation by exact name and
   will create another new one — the honest, designed-for degrade, not
   a crash or a silent wrong answer.
2. **The automated response-verification timed out** (45s, no candidate
   ever accepted) despite the real response being visibly present the
   entire time. Perplexity's own response surface (a distinct "Answer" /
   "Links" / "Images" tab layout, a "Sources" side panel) was never
   exercised by `find_new_content()`/`_await_response()` before this
   mission — its geometry or focus/visibility properties evidently don't
   satisfy that mechanism's current candidate filtering the same way
   ChatGPT's and Kimi's own response surfaces do. Not investigated
   further or fixed this mission, per the same explicit scope boundary
   as §3's finding.

Per the mission's own explicit instruction — "If Perplexity cannot be
safely validated, document the blocker. Do not manufacture success" —
Perplexity is reported as **not** E2E validated, even though real,
positive, generic progress (session creation, write, submit, and actual
response generation all now demonstrably work) was made and is real,
useful evidence for a future mission to build on.

## 5. Kimi Desktop — blocked, documented, not re-debugged

Zero visible windows at the time of this mission's live validation
attempt (`WindowManager.enumerate()` found nothing titled "Kimi") —
the exact same orphaned-background-process contamination already
documented in `docs/audits/APP_KNOWLEDGE_ACQUISITION_1.md`, accumulated
across many prior missions' own extensive testing of this specific
installation. One launch attempt was made (part of the validation
attempt itself, not a diagnostic); it failed identically
(`the application did not report a real, visible window`). Per the
mission's own explicit instruction — "Do not reopen the previous
polluted-window debugging unless a clean reproducible production
failure appears" — no further attempts were made, and no process was
force-killed.

**The persistent-session architecture itself was never exercised
against Kimi this mission** — its correctness for Kimi specifically
remains whatever was already established in prior missions for the
*previous* per-call-creation architecture, not re-validated under the
new find-or-create-named-session logic. A future mission, against a
freshly-restarted Kimi instance, is the natural next step.

## 6. Tests

**New this mission**: 26 total.

`tests/test_reasoning_session_manager.py` (full rewrite, 25 tests) —
`find_named_session()`'s exact-match behavior including the mission's
own explicit substring-collision and no-exact-match scenarios; reuse
(existing session found → opened, no new session created, no new-session
vocabulary ever searched); creation (missing session → new one created
and renamed, via both a direct rename control and a "more options"
trigger fallback); rename-is-best-effort (no rename control, focus never
lands in the window, `write_text()` failing — none of these fail the
current call, only degrade future reuse); a dedicated restart-persistence
test (two wholly separate `ReasoningSessionManager` instances sharing
only the fake bridge — standing in for real, persistent application
state — the second correctly rediscovers and reuses what the first
created); Chat-section navigation ordering; and the new bare-`"new"`
vocabulary fallback ordering.

`tests/test_desktop_uia.py` (+3): `get_focused_element_in_window()` —
returns a focused element confirmed to belong to the window, refuses
focus belonging to a *different* window (the direct regression guard for
the cross-application-focus-leak risk this primitive exists to close),
and raises when nothing is focused.

`tests/test_reasoning_role_separation.py` (extended, not counted as new):
the existing coding-agent-refusal test now also asserts
`_sessions.establish` is never called for a coding-agent spec — the
mission's own explicit "coding-agent rejection" test requirement.

## 7. Regression

```
pytest tests/test_app_knowledge_profile.py tests/test_app_knowledge_acquisition.py \
       tests/test_desktop_uia.py tests/test_desktop_execution.py \
       tests/test_desktop_operator.py tests/test_reasoning_role_separation.py \
       tests/test_reasoning_session_manager.py tests/test_desktop_app_provider.py \
       tests/test_reasoning_fallback_ladder.py tests/test_kalpavriksha_desktop_mission_bridge.py \
       tests/test_win32_clipboard_backend.py tests/test_broker_integration.py \
       tests/test_broker_wiring.py tests/test_desktop_perception.py
```

**Result: 913 passed, 4 failed.** Same 4 pre-existing, by-name-identical
failures documented in every prior mission's report in this codebase.
**Zero new regressions.** No existing safety guard was weakened.

## 8. Architectural rules — confirmed intact

- **Coding agents remain coding-only**: `is_coding_agent()`'s gate sits
  before `establish()` is ever reached (step -1 of `complete()`,
  unchanged); a dedicated test now explicitly asserts
  `_sessions.establish` is never called for a coding-agent spec.
- **No vendor-specific branches**: nothing in `reasoning_session.py` or
  `desktop_app.py` names ChatGPT, Kimi, or Perplexity — every mechanism
  (exact-name search, vocabulary-based control discovery, focus-then-
  write rename) is generic and shared. Perplexity's own navigation gap
  (no "Chat" tab) required zero special-casing: `_navigate_to_chat_section()`
  was already a no-op for applications without one.
- **Inspectability preserved**: every submitted prompt still carries its
  own `[Kalpavriksha Reasoning — <app> · <timestamp> · <id>]` marker,
  visible in the transcript, on top of the conversation itself now being
  persistently titled `"Kalpavriksha Reasoning"`.
- **Composer draft vs. conversation identity kept separate**: no change
  to `write_text()`'s own clear step; a reused or freshly-created named
  session's composer content is never inspected as a reason to reject
  it.

## 9. Explicitly left untouched

- `find_new_content()`/`_await_response()`'s response-discovery
  mechanism itself — the two gaps found live this mission (multi-turn
  conversation ambiguity for ChatGPT, Perplexity's own response-surface
  shape) are documented, not fixed, per this mission's own explicit
  scope boundary.
- Perplexity's rename affordance — not investigated.
- Kimi Desktop's orphaned background processes — not force-killed.
- App Knowledge profiles (`app_knowledge/`) — not touched, per explicit
  instruction not to do more app-knowledge research this mission.

Not committed, per instruction.
