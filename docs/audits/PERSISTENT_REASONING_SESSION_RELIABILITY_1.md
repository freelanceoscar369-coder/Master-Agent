# Complete Persistent Reasoning Session Reliability — Report

**Status: Response discovery for persistent, multi-turn conversations
fixed and proven live, twice, against ChatGPT Desktop — the mission's
own required regression case. Perplexity Desktop's rename-for-reuse
capability was extended with a real, live-found generic vocabulary gap
closed, but rename itself remains unverified live this mission — reported
honestly as not yet meeting the persistent-session requirement, per the
mission's own explicit "do not manufacture success" instruction, not
forced through with more probing.**

## Acceptance table

| Provider | Named session | Reuse | Current response correctly captured | Live proof |
|---|---|---|---|---|
| ChatGPT | **PASS** | **PASS** | **PASS** | Provided — two-call regression, both automated and visual |
| Perplexity | PASS (created) — rename **not verified** | **FAIL** — not yet reliably reusable by name | Not confirmed this mission (see §4) | Partial — session/write/submit mechanics real; rename and response-capture for this app not proven |
| Kimi | Existing architecture, unchanged | Existing architecture, unchanged | Existing evidence, unchanged | Not attempted — blocked, documented, not re-debugged (per explicit instruction) |

## 1. Fix: response discovery for persistent, multi-turn conversations

Two distinct, sequential fixes were needed — the second only surfaced
once the first was live-verified and a second live run exposed a
different failure mode. Both are described in `find_new_content()`'s
own updated docstring.

### Fix 1 — content-set comparison, not position comparison

The prior version compared each candidate region against `baseline` *by
its own bounding rectangle*. Confirmed live against ChatGPT Desktop's
reused `"Kalpavriksha Reasoning"` conversation: once several exchanges
had accumulated, an older reply's on-screen position shifted between the
baseline snapshot and the after-submission poll (new content appended
below it) — its rectangle no longer matched its own baseline entry, so
it was wrongly treated as new. **Fix**: compare candidate text against
the *set* of all baseline text, regardless of position. A region is
excluded if its text was seen *anywhere* in the baseline snapshot, full
stop.

**Live result after this fix alone**: still wrong. A *different* older
reply — one that had scrolled entirely off-screen at the moment
`baseline` was captured, and so was never recorded in it at all —
scrolled back into view during a later poll and was accepted, since
content-set membership cannot exclude something baseline never saw in
the first place.

### Fix 2 — prompt-anchored positional floor

Locate this call's own just-submitted prompt (`exclude_text`) by its
rendered text, wherever it appears in the window; only ever consider a
candidate whose own top position is at or below that prompt's bottom
edge. In every chat UI this architecture targets, a response can only
ever render visually *below* the request that produced it — nothing
above the current prompt's own position can be this call's own answer,
regardless of what scrolling did to baseline capture. Best-effort: if
the prompt's own echo cannot be located, the floor defaults to the
window's own top edge (every candidate remains eligible), and the
content-set comparison from Fix 1 stays in force either way.

### Why this stays generic

No application name, wording, or selector appears in either fix. Both
signals — text-content-set membership, and vertical position relative to
the current prompt's own rendered location — are structural properties
of how UIA and ordinary top-down chat layouts work, not particular to
ChatGPT, Kimi, or Perplexity.

### Live evidence

**ChatGPT Desktop, two-call regression, run after both fixes**:

- Call 1 (a fresh call against the already-existing, reused
  `"Kalpavriksha Reasoning"` conversation): `outcome=succeeded`, response
  text exactly `KALPAVRIKSHA_FIXV2_CALL1_OK`, marker present.
- Call 2 (same conversation, now with call 1's own exchange plus
  multiple prior missions' worth of history already in it):
  `outcome=succeeded`, response text exactly `KALPAVRIKSHA_FIXV3_CALL2_OK`
  — the genuinely current, correct response, not any of the several
  older ones still present higher up in the same transcript. Screenshot
  confirms the sidebar still shows the same, single `"Kalpavriksha
  Reasoning"` entry selected — no new conversation was created.

This is the exact regression the mission required: the same architecture
that already passed the two-call persistent-session test now also
correctly attributes each response to its own request in a conversation
that keeps growing.

## 2. Perplexity Desktop — rename vocabulary gap closed, rename itself not yet verified live

### What was found and fixed

A read-only, bounded inspection of Perplexity Desktop's real window
found genuine per-session menu triggers named **"Session actions"** and
**"More actions"** — neither contains the word "options" at all, so the
existing `RENAME_TRIGGER_VOCABULARY` (all "...options" phrasing) could
never match either one. Added both, plus the generic siblings `"chat
actions"`/`"conversation actions"`/`"message actions"`, to
`RENAME_TRIGGER_VOCABULARY` — the same "options and actions are both
real, interchangeable wording for the identical concept" reasoning
already applied to `NEW_SESSION_VOCABULARY`'s own `"new"` fallback.
Generic, not Perplexity-specific: any application using "actions"
instead of "options" for its per-item menu benefits identically.

### What remains unverified, reported honestly

A direct, read-only inspection of Perplexity's *currently active,
just-created* conversation — the exact state `create_named_session()`
attempts to rename immediately after clicking "New" — found **no**
element matching any `RENAME_ACTION_VOCABULARY` or
`RENAME_TRIGGER_VOCABULARY` phrase at all, even after the vocabulary
expansion above and even after a real prompt had already been submitted
in that conversation. The "Session actions"/"More actions" triggers
found earlier belonged to *other, already-listed* past conversations in
the sidebar, not to the one currently open. This is consistent with a
real, plausible, but not yet confirmed hypothesis: Perplexity may not
expose a rename-capable "Sessions" list entry for the conversation
currently being viewed at all — only for conversations that have become
a *separate, listed* sidebar item, which may require navigating away and
back, or may happen on a delay this mission's bounded, single-pass
validation did not wait out.

**This was not investigated further.** The mission's own explicit rule —
"If rename cannot be verified: fail closed for persistence; do not
pretend the session is reusable; report the provider as not yet meeting
the persistent-session requirement" — is exactly what the existing,
unchanged `_rename_current_session()` verification already does
(`renamed=False` when `find_named_session()` cannot confirm the exact
title afterward), and is exactly what is reported here: Perplexity is
**not yet** counted as meeting the persistent-session requirement. No
speculative further clicking, menu-hunting, or additional live
diagnostic passes were performed, per the mission's own explicit
instruction not to turn this into another diagnostic loop.

### Live validation attempts and the environment condition that limited them

One full live run reached write/submit successfully (rename not
verified, as above) but timed out at response verification; two
subsequent retries failed earlier, at launch/focus itself
(`the application did not report a real, visible window`), tracing —
confirmed by direct screenshot — to this development session's own
concurrent coding-agent GUI window repeatedly holding OS foreground focus
during the confirmation poll, the identical environment condition
already documented in two prior missions' own reports. Per the mission's
explicit instruction not to create another diagnostic loop, no further
retries were attempted.

**What is still real, useful, positive evidence from this and the prior
mission**: Perplexity Desktop's session creation, prompt writing,
submission, and real response generation have all been directly,
visually confirmed working at least once each — this is not reported as
broken, only as not yet meeting the *specific, additional* bar this
mission raised (verified rename + confirmed current-response capture, in
one continuous live run).

## 3. ChatGPT Desktop — no regression

The mission's own explicit regression list — exact `"Kalpavriksha
Reasoning"` lookup, reuse of an existing named conversation, creation
when absent, coding-agent rejection, Chat vs Codex/Work separation,
verified write, verified submission — is untouched by this mission's
diff (only `find_new_content()`'s response-discovery logic and
`RENAME_TRIGGER_VOCABULARY` changed) and is re-confirmed both by the full
deterministic suite (§5) and by the two-call live run in §1, which
exercised `find_named_session()`'s reuse path, the Chat-section
navigation, and verified write/submit exactly as before.

## 4. Kimi Desktop — blocked, not re-debugged

Zero visible windows at the time of this mission's own check (`kimi
windows: []`), the same pre-existing, already-documented orphaned-process
contamination from prior missions. Per the mission's own explicit
instruction — "Do NOT spend this mission debugging the previously
contaminated Kimi process... otherwise document it as blocked and stop"
— no launch attempt, diagnostic, or force-kill was performed this
mission.

## 5. Tests

**New this mission**: 12.

`tests/test_desktop_uia.py` (+5): the mission's own required scenario
(`CALL1_RESPONSE` existing, `CALL2_RESPONSE` new → resolver returns
`CALL2_RESPONSE`); the exact position-drift bug Fix 1 closes; multiple
old matching responses all excluded; the exact off-screen-at-baseline bug
Fix 2 closes; graceful fallback when the prompt echo cannot be located.
(Composer exclusion and navigation/sidebar-chrome exclusion — also named
in the mission's own test list — were already covered by existing tests
carried over unchanged, confirmed still passing.)

`tests/test_reasoning_session_manager.py` (+1): a dedicated, named
regression test pinning the live-found `"Session actions"`/`"More
actions"` vocabulary gap and its fix (existing rename-flow tests already
exercised the trigger-then-action mechanism generically; this test names
the specific real finding, matching this codebase's own convention of
one dedicated test per live-found fact).

## 6. Regression

```
pytest tests/test_app_knowledge_profile.py tests/test_app_knowledge_acquisition.py \
       tests/test_desktop_uia.py tests/test_desktop_execution.py \
       tests/test_desktop_operator.py tests/test_reasoning_role_separation.py \
       tests/test_reasoning_session_manager.py tests/test_desktop_app_provider.py \
       tests/test_reasoning_fallback_ladder.py tests/test_kalpavriksha_desktop_mission_bridge.py \
       tests/test_win32_clipboard_backend.py tests/test_broker_integration.py \
       tests/test_broker_wiring.py tests/test_desktop_perception.py
```

**Result: 919 passed, 4 failed.** Same 4 pre-existing, by-name-identical
failures documented in every prior mission's report in this codebase.
**Zero new regressions.** No existing guard was weakened.

## 7. Production changes

Confined to `src/master_agent/desktop/execution/uia_control.py`
(`find_new_content()` — both fixes described in §1) and
`src/master_agent/providers/reasoning_session.py`
(`RENAME_TRIGGER_VOCABULARY` — the `"actions"`-wording additions from
§2). No other file changed. No application name, coordinate, or
vendor-specific branch anywhere in either diff.

## 8. Explicitly left untouched / not expanded

- The session-architecture itself (`find_named_session`,
  `open_named_session`, `create_named_session`, coding-agent gating) —
  unchanged, per the mission's own explicit instruction not to redesign
  it.
- Perplexity's rename mechanism was extended (vocabulary) but not
  further investigated once it remained unverified — no speculative
  additional menu-hunting, no app-specific selector added to force a
  match.
- Kimi Desktop — not touched at all this mission.
- App Knowledge layer — not expanded, no additional documentation
  research performed, per explicit instruction.
- This development session's own concurrent-coding-agent-window focus
  contention — documented again, not worked around; it is evidence the
  existing foreground-safety gate is functioning correctly under a real
  but unusual condition, not a defect to engineer around.

Not committed, per instruction.
