# Reasoning-Layer Milestone — Freeze, Audit & Handoff

**Status: Milestone frozen and committed.** This report is the closing
audit for the Kalpavriksha reasoning-layer work spanning discovery,
Desktop Executive foundation, the reasoning-provider architecture,
persistent named-session identity, and the App Knowledge layer.

## Part 1 — Capability confirmation

| # | Requirement | Confirmed by |
|---|---|---|
| 1 | ChatGPT/Kimi/Perplexity represented as reasoning providers | `PROVIDER_CATALOG` entries in `ai_infrastructure/catalog.py` (`chatgpt-desktop`, `kimi-desktop`, `perplexity-desktop`), one `DesktopAppReasoningProvider` per entry via `build_desktop_providers()` |
| 2 | Coding-agent conversations never used as reasoning sessions | `is_coding_agent()` (role + closed identity set `KNOWN_CODING_AGENT_IDENTITIES`) checked at provider construction (`build_desktop_providers()`), at `complete()`'s own step -1, and in `availability()` — three independent layers |
| 3 | Reasoning sessions isolated from coding-agent sessions | `ReasoningSessionManager._navigate_to_chat_section()` switches to the exact-name `"Chat"` section before any session search, best-effort/no-op where none exists (Perplexity) |
| 4 | Persistent session name `"Kalpavriksha Reasoning"` | `DEDICATED_SESSION_NAME` in `reasoning_session.py` |
| 5 | Search → reuse / create → rename → never anonymous | `ReasoningSessionManager.establish()`: `find_named_session()` → `open_named_session()` on a hit, `create_named_session()` (which itself attempts `_rename_current_session()`) on a miss |
| 6 | Exact-name matching, no substring collision | `find_named_session()` uses `find(name_exact=...)`; the exact substring-collision risk (a prior mission's own live-found bug) has a dedicated regression test (`test_substring_collision_the_exact_one_is_selected`) |
| 7 | ChatGPT uses real Chat, never Codex/Work | `CHAT_SECTION_LABEL = "Chat"` exact-match navigation; live-confirmed twice (`REASONING_SESSION_E2E_ACCEPTANCE_3/4.md`) |
| 8 | Kimi uses real Chat, never coding/agent/Work | Same generic mechanism; live-confirmed (`REASONING_SESSION_E2E_ACCEPTANCE_3/4.md`) |
| 9 | Perplexity uses its real conversational surface, no assumed Chat tab | `_navigate_to_chat_section()` is a no-op when no exact `"Chat"` tab exists — confirmed live, Perplexity has none (`APP_KNOWLEDGE_ACQUISITION_1.md`) |
| 10 | Fails safely rather than typing into an uncertain window | `_launch_or_focus()`'s foreground-confirmation gate (never proceeds without a positively-confirmed active window); `find_named_session()`/`_find_new_session_control()` return `None`/fail closed rather than guess |
| 11 | Clear/write/submit verified, not assumed | `write_text()`'s `_verify_cleared()`/`_verify_readback()`; `_submit()`'s `_verify_submission()` |
| 12 | Response discovery based on the current request, not the largest region | `find_new_content()` — baseline-diff, content-set comparison, prompt-anchored positional floor (`EXPERT_DESKTOP_EXECUTIVE_RESPONSE_DISCOVERY_1.md`, `PERSISTENT_REASONING_SESSION_RELIABILITY_1.md`) |
| 13 | Multi-turn discovery never returns a stale earlier-turn response | Content-set + prompt-anchored floor, both added specifically for this; live-proven twice against ChatGPT's own growing `"Kalpavriksha Reasoning"` conversation |
| 14 | Current-call response associated with the newly submitted prompt | The prompt-anchor mechanism locates *this call's own* submitted text and only accepts a response positioned below it |
| 15 | Hidden/offscreen elements never mistaken for composer/response | `IsOffscreen` filtering in `find_composer()`, `find_main_content()`, and `_text_region_candidates()` (used by both `snapshot_text_regions()`/`find_new_content()`) |
| 16 | Window maximization before geometry-dependent interaction | `_launch_or_focus()` maximizes the confirmed-foreground window before returning it |

All 16 confirmed present, with a cited implementation and (where
applicable) live evidence — not asserted from memory.

## Part 2 — Regression validation

```
pytest tests/test_app_knowledge_profile.py tests/test_app_knowledge_acquisition.py \
       tests/test_desktop_uia.py tests/test_desktop_execution.py \
       tests/test_desktop_operator.py tests/test_reasoning_role_separation.py \
       tests/test_reasoning_session_manager.py tests/test_desktop_app_provider.py \
       tests/test_reasoning_fallback_ladder.py tests/test_kalpavriksha_desktop_mission_bridge.py \
       tests/test_win32_clipboard_backend.py tests/test_broker_integration.py \
       tests/test_broker_wiring.py tests/test_desktop_perception.py
```

**Result: 919 passed, 4 failed. Zero new regressions.**

The 4 failures are the same, by-name-identical, pre-existing failures
documented in every prior mission report in this codebase's history (the
`gemini.api`-default-enabled config decision and the
`tiered_runner.py`/broker-wiring naming-guard assertions) — untouched by
any reasoning-layer change:

- `test_broker_integration.py::test_only_the_catalogue_names_a_provider[gemini]`
- `test_broker_wiring.py::test_the_broker_reads_the_estate_from_the_desktop_executive`
- `test_broker_wiring.py::test_no_provider_is_available_before_the_machine_has_been_scanned`
- `test_broker_wiring.py::test_cloud_providers_stay_off_until_the_founder_enables_them`

**A separate, pre-existing inconsistency was found and *not* fixed, by
design**: `tests/test_desktop_executive.py` (a file modified by an
earlier, separate "Desktop Interaction"/`actions_interaction.py` mission,
not part of this session's own reasoning-layer regression suite at any
point) contains 5 tests that fail when run — 4 assert an older "Deliverable
7: no automation capability" boundary that `actions_interaction.py`'s own
registration in `plugin.py` intentionally supersedes (the Desktop
Executive now legitimately exposes 18 capabilities including real click/
type/keyboard actions, not 12 read-only ones); the 5th
(`test_launching_starts_the_resolved_path`) exercises the new,
verified-launch behavior against a fake process probe that was never
updated to simulate a process actually becoming "running" after
`start()`. This file was never part of this session's own established
regression suite (confirmed: it was not included in any of the ~15+
regression runs across every reasoning-layer mission this session), so
it is **excluded from this milestone's commit** — left as an
uncommitted, pre-existing local modification for a future, separate
Desktop Executive test-hygiene pass, per the mission's own instruction
not to reopen unrelated debugging. `plugin.py`/`actions_interaction.py`
themselves — real, working, intentional architecture — are still
included in this milestone.

## Live validation status

### ChatGPT Desktop — strongest proof

Proven live, screen-observed, this session:

- Correct Chat interface (never Codex/Work).
- Isolated, named `"Kalpavriksha Reasoning"` session.
- Persistent reuse across independent calls — confirmed *twice*, most
  recently on a conversation already holding many prior exchanges.
- Prompt entry, submission, real response — all verified, not assumed.
- Correct response discovery, including the harder case: a fresh
  response correctly distinguished from several older ones already
  present in the same, growing, reused conversation.

### Kimi Desktop — not claimed beyond what was observed

Kimi's write/submit/response mechanics were proven live in earlier
sessions (see `REASONING_SESSION_E2E_ACCEPTANCE_3/4.md`) — that evidence
stands, unchanged. The *persistent-session* architecture built this
mission chain (`find_named_session`/rename-for-reuse) was **not**
re-validated live against Kimi: the instance available this session
showed the same pre-existing orphaned-process contamination documented
in two prior reports (`APP_KNOWLEDGE_ACQUISITION_1.md`,
`PERSISTENT_REASONING_SESSION_1.md`). Not claimed as a full live E2E
PASS for the persistent-session feature specifically; not re-debugged,
per every prior mission's own explicit instruction and this one's.

### Perplexity Desktop — valuable, honestly bounded

- Installed, confirmed.
- Its interface genuinely differs from ChatGPT/Kimi — no separate Chat
  tab; a single, unified `"Ask anything…"` surface.
- Session creation, prompt writing, submission, and real response
  generation have each been directly, visually confirmed working at
  least once.
- `"New"` (not `"new chat"`/`"new task"`) is its own new-conversation
  control — a real, generic vocabulary gap found and closed.
- `"Session actions"` / `"More actions"` are its real per-item menu
  vocabulary — found and added to the generic rename-trigger vocabulary.
- **Persistent rename/reuse remains unverified.** A direct, read-only
  inspection of its currently-active, freshly-created conversation found
  no matching rename control even after the vocabulary expansion. Not
  claimed working. Not forced through with additional live probing,
  per the explicit "do not invent success" instruction.

## Part 3 — Milestone commit

See the handoff report (end of this response) for the commit hash, tag,
and exact file list. Scope, decided by inspecting each file's actual
diff content and correlating modification timestamps against this
session's own active working period — not by a blanket `git add -A`:
every file genuinely part of the reasoning-provider architecture, the
Desktop Executive foundation it depends on, and this milestone's own
audit trail is included; unrelated pre-existing working-tree state
(Founder Edition voice/browser/gemini-provider work, VEDRA_PROJECT
assets, obsidian notes, root-level status/completion text files, `.bak`/
`.backup` files, ad-hoc diagnostic scripts from earlier, unrelated
missions) is left untouched — neither committed nor deleted, since none
of it was created by this milestone's own work and its disposition is
not this mission's call to make.

## Part 4 — Groq/Gemini

Not added. `ai_infrastructure/catalog.py`'s `ProviderSpec`/
`PROVIDER_CATALOG` and the `DesktopAppReasoningProvider`/
`TieredPromptRunner` architecture are already provider-extensible by
construction (one new catalogue entry + one new provider class, the same
pattern ChatGPT/Kimi/Perplexity already followed) — no redesign would be
needed to add either later.

Not committed to remote. No push performed.
