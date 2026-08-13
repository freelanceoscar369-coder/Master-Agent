# App Knowledge Acquisition Layer — Initial Build & Live Validation

**Status: Capability built, tested, and exercised live (read-only) against
all three initial targets.** ChatGPT Desktop and ~~Kimi Desktop~~
(contaminated this pass — see §4) have deep observed knowledge from this
session's own extensive prior history plus one fresh confirmation this
mission. Perplexity Desktop went from zero live contact to a first
genuine, safe, read-only observation pass. No application is claimed
"configured" or "ready for reasoning integration" by this mission —
that determination is explicitly out of scope here (see §6).

## 1. What was built

`src/master_agent/app_knowledge/` — a new, standalone package, three
files:

- **`profile.py`** — the data model. `KnowledgeType` (`DOCUMENTED` /
  `OBSERVED` / `INFERRED` / `UNKNOWN`), `Fact` (a value + type + a
  *mandatory* source — a `Fact` cannot be constructed without saying
  where it came from), `AppKnowledgeProfile` (one frozen dataclass per
  application, fields named after the mission's own question list
  verbatim: `chat_interface`, `other_modes`, `new_session_creation`,
  `can_rename_chat`, `dedicated_session_strategy`, `composer_exposure`,
  `send_representation`, `enter_submits`, `response_exposure`,
  `persists_unsent_drafts`, `inactive_tabs_in_uia_tree`,
  `visibility_distinguishing_properties`, `loading_reconnection_states`,
  `safe_active_session_indicator`). `merge_observations()` returns a new,
  updated profile — never mutates in place — and refuses anything that
  isn't a real field name or a genuinely `OBSERVED` fact.
- **`catalog.py`** — `APP_KNOWLEDGE_CATALOG`, keyed by `provider_id` (the
  same join key `PROVIDER_CATALOG` already uses), holding the three
  initial profiles.
- **`acquisition.py`** — `acquire_knowledge(spec, bridge, handle)`, the
  read-only capability. Refuses immediately for any `is_coding_agent()`
  spec, before touching the machine at all. Every individual check
  (`check_chat_tab`, `check_dedicated_session_present`,
  `check_composer_current_text`, `check_offscreen_duplicates`,
  `check_loading_state`) calls only read-only `UiaAutomationBridge`
  methods — `find()`, `find_composer()`, `read_text()`,
  `snapshot_text_regions()`. None of them accept a `KeyboardController`
  or `MouseController`, and none of them can reach `write_text()` or
  `click()` — there is no parameter through which a mutating call could
  even be attempted, not merely a convention against making one.

Nothing here is wired into production automation. `complete()`/
`ReasoningSessionManager` are unmodified — this mission's own deliverable
list asked for the acquisition capability, the profiles, tests, and a
report, not a runtime integration, and the mission text itself says a
profile must "inform, but not replace, generic UI discovery." Wiring
this in is a natural next step, not attempted here.

## 2. Why this is generic, not per-vendor automation

No `if app_id == "..."` branch exists anywhere in `profile.py` or
`acquisition.py`. The three profiles in `catalog.py` are *data* — the
same way `PROVIDER_CATALOG` itself is data, not code, per-application.
`acquisition.py`'s checks operate on structural, vendor-independent UIA
signals (exact-name matching, `IsOffscreen`, generic loading-keyword
scanning across common English wording, not one application's specific
copy) — the same primitives every other part of the Desktop Executive
already uses.

## 3. The three initial profiles

### ChatGPT Desktop

Deep `OBSERVED` coverage carried forward from three prior missions this
session (`REASONING_SESSION_E2E_ACCEPTANCE_2/3/4.md`,
`EXPERT_DESKTOP_EXECUTIVE_RESPONSE_DISCOVERY_1.md`), refined by this
mission's own fresh read-only pass with two new findings:

1. **The exact-name 'Chat' tab is not always present.** Confirmed live
   this mission: with an *existing* conversation open, the Chat/Codex
   tab selector is not shown at all — the header instead shows the open
   conversation's own title. Every prior confirmation of the tab was on
   a fresh landing page. A caller must not treat the tab's absence, by
   itself, as evidence of being in Codex/Work mode.
2. **A substring match on "Kalpavriksha Reasoning" already succeeds** —
   but not because of a genuinely dedicated, reused session. It matches
   one specific prior mission's own conversation, which ChatGPT itself
   auto-titled starting with that phrase (other runs were auto-titled
   differently). Current production automation does not rename or reuse
   a session at all — every call creates a new one and embeds its
   identity in the prompt text instead (see `dedicated_session_strategy`).

`DOCUMENTED` facts (new-chat shortcut Ctrl+Shift+O, rename procedure)
came from third-party blogs, not first-party OpenAI help — labeled as
such in each `source` string.

### Kimi Desktop

Same depth of prior `OBSERVED` knowledge (Chat/Work tab split, the
"Ask me. Task me." composer-label concatenation bug, restart-surviving
draft persistence, "Reconnecting…"/"getting ready" loading states, the
sidebar-vs-response response-discovery finding) — all already documented
with citations to the specific prior audit report each came from.

**This mission's own live pass did not add to it.** Kimi Desktop showed
*zero* visible windows at the moment of inspection (`WindowManager.
enumerate()` returned nothing titled "Kimi"), despite the process
inventory suggesting it was still "running" — almost certainly orphaned
background processes accumulated across this session's own extensive
prior testing (documented across four prior missions as the same class
of accumulated-instability finding already seen with ChatGPT's
stale-draft composer). Two bounded attempts (20s, then 35s) to
launch/focus it were made; neither found a real window. Per the
mission's own explicit instruction — "Do not repeatedly test a heavily
polluted application instance. If the environment is demonstrably
contaminated, document it and stop" — no third attempt was made, and no
process was force-killed to manufacture a clean state.

### Perplexity Desktop

Went from **zero prior live contact of any kind** to a first, clean,
safe, read-only observation pass this mission. Real findings:

- **No separate 'Chat' tab exists at all** — confirmed by exact-name
  search finding nothing. The application presents one unified surface:
  an "Ask anything…" composer with a "Search" mode dropdown and a
  "Computer" toggle beside it. No multi-tab Chat/Work/Codex-style split
  was observed anywhere.
- **A "Computer" toggle was found, unexplored.** Its exact behavior was
  not investigated (clicking it would be exactly the kind of action
  knowledge acquisition must never perform) — flagged in the profile as
  worth the same caution as ChatGPT's Codex or Kimi's Work, not itself
  confirmed safe or unsafe.
- **No "Kalpavriksha Reasoning" session exists** — expected, since no
  automation has ever targeted this application.
- **The composer was located and read as empty** (whitespace-only,
  consistent with its visible placeholder) — `find_composer()`'s generic
  heuristic worked on a third, previously-untested application without
  any change.
- **No loading/reconnection text was visible** at the moment of
  inspection.

Everything about actually *writing to or submitting* this application —
send-control identity, whether Enter submits, response exposure, draft
persistence, a safe "session is active" signal — remains genuinely
`UNKNOWN` or, where a third-party source existed, `DOCUMENTED` but
unconfirmed. This is intentional and enforced by a dedicated regression
test (`test_perplexity_write_and_response_path_remains_unconfirmed`):
none of those fields may read as `OBSERVED` until a mission actually
performs (and is authorized to perform) a real write/submit against this
application.

## 4. Live validation — what was actually done

For each target: launch/focus using the same read-only-safe polling
`_launch_or_focus()` already uses (reimplemented narrowly in a
standalone script, deliberately *not* importing
`DesktopAppReasoningProvider` — no write-capable machinery was ever in
scope, even unused), bring to front, screenshot for visual confirmation
of the correct interface, then run `acquire_knowledge()` — pure reads,
zero clicks, zero keystrokes, zero submissions.

| Application | Window found | Visually confirmed | Acquisition run |
|---|---|---|---|
| ChatGPT Desktop | Yes (handle 262842) | Yes (screenshot) | Yes |
| Kimi Desktop | **No** — zero visible windows | N/A | Not run — contaminated, documented, stopped |
| Perplexity Desktop | Yes (handle 133034) | Yes (screenshot) | Yes |

No prompt was ever entered or submitted to any application during this
mission. No coding-agent session was touched. No clipboard mechanism was
touched. No application was force-killed.

## 5. Tests

**New this mission**: 34 —

`tests/test_app_knowledge_profile.py` (17): `Fact`'s mandatory-source
guarantee, `is_confirmed` correctly distinguishing
`DOCUMENTED`/`OBSERVED` from `INFERRED`/`UNKNOWN`, an unpopulated
profile defaulting every field to `UNKNOWN`, `merge_observations()`'s
immutability and field/type validation, structural completeness of all
three initial profiles (every fact carries a real source), and — most
directly tied to the mission's own explicit instruction — a dedicated
test that Perplexity's write/submit/response-path fields never read as
`OBSERVED` without an actual write ever having happened.

`tests/test_app_knowledge_acquisition.py` (17): the read-only guard
itself (`acquire_knowledge()` proven, via a fake bridge that raises on
`write_text()`/`click()`, and separately via a bare bridge that does not
even implement them, never to reach either), coding-agent refusal before
any bridge access at all, and each individual check's own logic
(positive/negative results both recorded, never silently dropped;
unresolvable elements recorded as an observation, not raised past the
caller).

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

**Result: 900 passed, 4 failed.** Same 4 pre-existing, by-name-identical
failures documented in every prior mission's report in this codebase.
**Zero new regressions.** Desktop Executive production behavior
(`uia_control.py`, `desktop_app.py`, `reasoning_session.py`) was not
touched this mission.

## 7. Is any application "ready for reasoning integration"?

**Not determined by this mission, deliberately.** This mission's own
deliverable list asks the report to state "whether each application is
ready" — answered honestly:

- **ChatGPT Desktop**: separately, and previously, proven live
  end-to-end (full session-establishment → write → submit → verified
  response chain) in `REASONING_SESSION_E2E_ACCEPTANCE_4.md` and
  `EXPERT_DESKTOP_EXECUTIVE_RESPONSE_DISCOVERY_1.md`. That readiness
  finding is unchanged by this mission; this mission only added two
  refinements to *how well understood* its interface is, not new proof
  of working automation.
- **Kimi Desktop**: previously proven live end-to-end for the core
  write/submit/response mechanics (same reports), with the
  session-establishment architecture separately confirmed correct.
  Unchanged by this mission — no live automation was attempted here at
  all, only a (failed, contaminated) read-only check.
- **Perplexity Desktop**: **not ready, and not claimed to be.** A
  knowledge profile now exists, and one genuine, safe read-only pass
  confirmed real structural facts about its interface — but zero writes,
  zero submissions, and zero response verifications have ever been
  attempted against it. Readiness requires exercising the same generic
  write/submit/response-verification mechanisms already proven against
  ChatGPT and Kimi, which is future work this mission's own scope
  boundary ("do not modify unrelated Desktop Executive behavior... do
  not claim Perplexity is configured or validated merely because a
  knowledge profile exists") explicitly does not authorize here.

## 8. Explicitly left untouched

- `DesktopAppReasoningProvider.complete()` / `ReasoningSessionManager` —
  not modified; this mission built a new, separate knowledge layer, not
  a runtime integration of it.
- Coding-agent separation — untouched; independently re-confirmed intact
  by `acquire_knowledge()`'s own refusal gate and its dedicated test.
- Clipboard mechanics — not investigated, per explicit instruction.
- Kimi Desktop's currently-orphaned background processes — not
  force-killed, per explicit instruction; left for the founder or a
  future mission to clear naturally (e.g. closing them by hand).
- Perplexity Desktop's "Computer" toggle — observed, flagged, not
  explored further.

Not committed, per instruction.
