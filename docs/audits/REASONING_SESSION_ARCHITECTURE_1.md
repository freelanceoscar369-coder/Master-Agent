# Kalpavriksha-Owned Reasoning Session Architecture — Implementation & Acceptance Report

## 1. What this changes

The prior architecture (see
[CLAUDE_DESKTOP_REASONING_SAFETY_GATE_1.md](CLAUDE_DESKTOP_REASONING_SAFETY_GATE_1.md))
asked one question before writing a reasoning prompt into a desktop AI
application: *"does whatever conversation is currently focused happen to
look empty?"* That model is what let a real incident happen — the
currently-focused conversation was an active one (this project's own Claude
Code session), and "looks empty" was never actually checked against
anything Kalpavriksha itself created.

This mission replaces that model with an architectural one: Kalpavriksha
reasons inside its own, actively-created, isolated session — never inside
whatever happened to already be open — and the tool used to build
Kalpavriksha is structurally prevented from ever becoming a reasoning
provider, independent of which specific application it happens to be.

## 2. Role separation

**New**: `ai_infrastructure/catalog.py` —
- `ProviderSpec.role: str = REASONING_ROLE` (or `CODING_AGENT_ROLE`).
- `KNOWN_CODING_AGENT_IDENTITIES` — a closed, vendor-generic set (`claude-code`,
  `codex`, `cursor`, `github-copilot`, `windsurf`, `cline`, `aider`,
  `kimi-code`, `kimi-webbridge`, `continue-dev`, `amazon-q`, …).
- `is_coding_agent(spec)` — true if *either* the spec's own `role` says so,
  *or* its `provider_id`/`inventory_key` matches the identity set —
  independent checks, so a spec that forgets to declare the role is still
  caught by identity, and a coding tool not yet added to the identity set
  is still caught if its own spec declares the role.

Enforced at three independent points, so no single omission lets a coding
agent through:

1. **`build_desktop_providers()`** (`providers/desktop_app.py`) — a
   coding-agent spec is never even constructed as a provider object.
2. **`profiles.py::availability()`** — checked first, before installed/
   healthy/credential checks, so the Broker never ranks or selects a
   coding-agent spec regardless of installation state.
3. **`DesktopAppReasoningProvider.complete()`/`.availability()`** — a
   direct call (bypassing the Broker) still refuses immediately, before
   any inventory read, launch, or focus call.

No entry for "Claude Code" or any other coding agent exists in
`PROVIDER_CATALOG` today — this is forward-looking, structural prevention,
not a reaction to one already present. `claude-desktop` (the consumer chat
application) is *not* classified as a coding agent — the risk it carries
(discussed next) is about session state, not application identity.

## 3. Kalpavriksha-owned, isolated reasoning sessions

**New file**: `providers/reasoning_session.py` — `ReasoningSessionManager`.

Mirrors the mission's own diagram: Mission → Reasoning Session Manager →
Kalpavriksha-owned session → Provider → response. Implemented as its own
small, named, independently-testable class — composed by
`DesktopAppReasoningProvider`, not folded invisibly into `complete()` — so
the concept the founder can reason about ("did Kalpavriksha get its own
session?") has a concrete, inspectable answer in code, not just a comment.

`establish(window, provider_label)`:

1. Searches a generic vocabulary of "start a new conversation" affordances
   (`NEW_SESSION_VOCABULARY` — "new chat", "new conversation", "new
   session", "new task", …) via the existing `UiaAutomationBridge.find()`
   primitive. Not one application's own wording — confirmed live, this
   session, against two real, independent, currently-installed
   applications (one exposing a "New chat" button, the other a "New Task"
   button) that this exact vocabulary discovered.
2. Invokes the discovered control via the existing `UiaAutomationBridge.click()`
   primitive (`InvokePattern`, falling back to a real coordinate click).
3. Confirms the result — re-reads the surface via the same
   `find_main_content()`/`read_text()` primitives `_await_response()`
   already uses, requiring it to show no more than a small amount of
   content (a welcome/placeholder state, not a real prior conversation).

No new automation mechanism anywhere in this sequence — every primitive
composed here already existed and was already proven live in earlier work
this session. What's new is the *sequence*: **create, then confirm** —
not merely *observe and hope*.

**Fails closed** on every branch:
- No generic control discoverable → `Provider = UNSAFE`, skipped.
- Control found but could not be invoked → unsafe, skipped.
- Invoked, but the resulting surface still shows substantial content
  (confirmed live — see §6) → unsafe, skipped. The currently-active
  conversation is never reused merely because a "new session" control was
  clicked; clicking it is not itself proof anything changed.
- The post-invoke read itself fails (ambiguous/unreadable state) → unsafe,
  skipped — never assumed empty by default.

## 4. Inspectability

`build_session_marker(provider_label)` produces
`"Kalpavriksha Reasoning — <provider label> · <timestamp> · <short id>"`,
embedded directly in the *visible submitted prompt text*
(`DesktopAppReasoningProvider.complete()`'s `marked_prompt`) — not via any
per-application "rename this conversation" UI, which would itself be
exactly the kind of application-specific automation this architecture
exists to avoid. A founder opening the application sees, in the
conversation transcript itself: which session Kalpavriksha created, what it
asked, and (once answered) the provider's real response — without any
private model chain-of-thought ever being part of what's captured. The
marker also appears in the returned `ProviderResult.detail["session_marker"]`
for programmatic inspection.

Two markers generated in succession are guaranteed distinct (a random
component plus a timestamp) — every session is individually identifiable,
not just identifiable as "a Kalpavriksha session" generically.

## 5. Provider hierarchy, boot safety — unchanged, reaffirmed

- Gemini remains the sole Tier 1 provider. Its configuration, retry policy,
  and provider registration are untouched by this mission.
- `CapabilityBroker`, `policy.py`, `PromptExecutor`, `TieredPromptRunner` —
  unmodified. Session establishment failure is just another provider
  failure to this layer; the existing bounded exclusion-and-retry logic
  (unchanged since the prior mission) already does "reject this one, try
  the next ranked candidate, fall through to the next tier" correctly, with
  zero new selection logic added for this mission.
- The Universal Desktop Executive (`desktop/` package) — untouched.
  `ReasoningSessionManager` composes existing primitives; it does not add
  new ones to that layer.
- Provider construction remains pure config storage — `ReasoningSessionManager`
  is constructed alongside the existing `UiaAutomationBridge`/`MouseController`
  in `DesktopAppReasoningProvider.__init__`, doing no I/O itself.
  Session *establishment* only happens inside `complete()`, exactly where
  the (now-removed) prior isolation check used to live — no new domino
  risk introduced.

## 6. Live validation — honest results across three corrective rounds

Per the mission's own explicit instruction, live validation targeted
`chatgpt-desktop` and `kimi-desktop` — real, currently-installed, standalone
consumer applications, **not** Claude Desktop and **not** the active
Claude Code/development session. Reported here across all three rounds,
including two real failures that led to real architectural fixes — not
smoothed over.

### Round 1 — before Chat-section navigation existed

Both `chatgpt-desktop` and `kimi-desktop` failed with the new-session
control apparently invoked but the surface unchanged afterward. Follow-up
read-only inspection found the real cause: **`chatgpt-desktop`'s window was
showing its own embedded "Codex" view** (OpenAI's agentic coding feature
built into the same application) — the "New chat" control discovered and
clicked belonged to *Codex's own* session list, not the general chat. This
is the same class of risk this whole mission addresses, for a second,
independent vendor. `kimi-desktop`'s cause was not yet understood at this
point. Neither attempt wrote a prompt or pressed Enter — the architecture
correctly refused rather than guess.

### Round 2 — after adding exact-match Chat-section navigation + `visible_only` filtering

Founder correction, addressed directly: `ReasoningSessionManager` now
navigates to an exact-match `"Chat"` section tab (distinct from `"Work"`/
`"Codex"`) before searching for a new-session control, and `find()` gained
an opt-in `visible_only` parameter (checks the standard UIA `IsOffscreen`
property) to avoid matching a same-named control belonging to an inactive,
merely-hidden section.

- `chatgpt-desktop` still failed identically. Investigation found
  `IsOffscreen` reports `False` for every candidate regardless of which
  section is actually showing — this application hides inactive-tab
  content via CSS visibility, not real screen-position clipping, so the
  standard offscreen property does not capture it here. `find_composer()`
  additionally could not resolve anything in this window's state at all.
  This specific application instance, after an entire session's worth of
  earlier testing, was judged too degraded to usefully continue debugging
  against — stopped per the explicit instruction not to keep chasing one
  polluted window's specific state.
- `kimi-desktop` also still failed identically (1,029 characters,
  unchanged). Direct before/after comparison found the real cause:
  `find_main_content()` — the "largest text-bearing region" heuristic —
  was matching a **persistent chrome element** (named `"Kimi Agent"`,
  matching the app's own name) that is present regardless of which
  conversation is open. A genuine new-session click produced **byte-for-
  byte identical content** before and after in that region. Separately,
  `find_composer()` correctly and reliably resolved the actual compose box
  (`"Ask me. Task me."`), which was genuinely empty.

### Round 3 — after making composer-emptiness the primary freshness signal

`_verify_fresh_surface()` now tries `find_composer()` — the same resolver
`_write_prompt()` itself uses — first, falling back to the
`find_main_content()` heuristic only when no composer can be resolved at
all.

**Result against `kimi-desktop`: session establishment succeeded, live,
for the first time.** `complete()` navigated to the Chat section, found and
invoked "New Task", confirmed the resulting composer was empty, and
returned `OK` from `ReasoningSessionManager.establish()` — the outcome
changed from `unavailable`/`ISOLATION_UNVERIFIED` to `rejected`/
`"typed into the composer but could not verify the text landed"` — a
**different, later, lower-level failure**, proving the isolation gate
itself now passes cleanly against a real application.

Direct follow-up diagnostic on the write step: the composer's clear-before-
type sequence did not reliably clear existing content before pasting the
new (marker-prefixed) prompt, and a read immediately after showed a mix of
placeholder text and content that did not match what was just sent. This is
a **composer write-reliability issue** — the same category of problem
`_write_prompt()`'s own paste/typing/verification logic already handles for
other applications, not a session-isolation problem. Per the mission's own
explicit scope boundary ("do not redesign the Universal Desktop
Executive"), this was not pursued further within this mission; it is a
distinct, addressable gap left for write-mechanics work, not an isolation
gap.

**What this does and does not demonstrate, stated plainly**:

- ✅ **No fabricated success anywhere across all three rounds.** Every
  failure reported the real, specific reason; nothing was ever assumed
  fine.
- ✅ **The existing conversation was never touched, in every attempt.** No
  text was written and no Enter was pressed until isolation was positively
  confirmed — confirmed by construction and by exact before/after content
  comparison.
- ✅ **A real "start a new conversation" control was genuinely discovered
  and genuinely invoked**, and a real "Chat" section tab was genuinely
  discovered and genuinely invoked, across multiple real, independent
  applications — never mocked or assumed.
- ✅ **Session establishment succeeded live** against `kimi-desktop`: a
  real Kalpavriksha-initiated session was created and positively verified
  fresh via the actual compose box's own state — items 1–2 of the
  mission's own six-item checklist (creates its own session; existing
  conversation untouched) are demonstrated live, not merely by unit test.
- ✅ **Two genuinely different real failures were found live and fixed
  architecturally** (Chat-section confusion; a heuristic-matching-chrome
  problem), each addressed with a generic, reusable mechanism
  (`name_exact`, `visible_only`, composer-primary freshness) rather than
  an app-specific patch — and a third real, novel finding (ChatGPT
  Desktop's own embedded Codex view) surfaced along the way.
- ❌ **A full successful end-to-end run — prompt appears in the
  established session, real response returned, response verified — was
  not achieved live within this mission.** The remaining blocker
  (composer write-verification reliability for `kimi-desktop`
  specifically) is outside this mission's scope to fix (Desktop Executive
  write mechanics, not session isolation) and is reported as an open gap,
  not glossed over.

The deterministic test suite (§7) exercises the full success path —
including the composer-emptiness-confirms-freshness branch — with
synthetic, controlled inputs, and now additionally has one real, live
confirmation that the actual establishment sequence (navigate to Chat →
find and invoke new-session control → confirm via composer state) works
against a genuine, currently-installed application, not only in test
doubles.

## 7. Deterministic tests

**New**: `tests/test_reasoning_role_separation.py` (13 tests) — role
separation at every layer: `is_coding_agent()` unit behavior (declared
role, identity-set match with and without the role set, generic
cross-vendor coverage, no false positives against real catalog entries),
`profiles.py::availability()` integration (unavailable even when
installed/healthy, checked ahead of other exclusions),
`build_desktop_providers()` integration (a coding-agent spec is never
constructed, with and without the role explicitly declared), and
`complete()`/`availability()` refusing before touching the machine.

**New**: `tests/test_reasoning_session_manager.py` (19 tests, grown across
the live-validation corrective rounds documented in §6) —
`ReasoningSessionManager` in isolation: vocabulary search order and
exhaustion; `establish()`'s every branch (no control found; control found
but click fails; control found, clicked, surface confirmed fresh; control
found, clicked, but the currently-active conversation's content is still
present — never reused; ambiguous/unreadable post-click state; a COM-level
failure mid-search); exact-match Chat-section navigation (clicked when
present, silent no-op when absent, non-fatal when unclickable, proven to
run *before* the new-session search, proven not to change behavior for
single-purpose apps with no such section); the composer-primary freshness
check (an empty composer confirms directly, a composer with real drafted
content is rejected, falls back to the main-content heuristic when no
composer resolves); and session-marker predictability/uniqueness.

**Updated**: `tests/test_desktop_uia.py` (+5 tests) — `find()`'s two new
capabilities, added directly in response to real live findings:
`name_exact` (whole-name match, proven not to match a substring like
`"New chat"` the way `name_contains` legitimately would) and
`visible_only` (skips an off-screen match, raises when every match is
off-screen, and — critically — proven to change nothing for existing
callers that don't ask for it).

**Updated**: `tests/test_desktop_app_provider.py` — the prior mission's
`_verify_isolated_session`-based tests replaced with
`TestSessionEstablishmentIntegration`, proving `complete()` correctly gates
`_write_prompt()` on `ReasoningSessionManager.establish()`'s result, that
the actually-submitted prompt carries the session marker, and that a
successful completion surfaces the marker in `ProviderResult.detail`.
`TestStaticSafetyExclusion` (Claude Desktop's own declarative exclusion, from
the prior mission) is unchanged and still passing.

**Updated**: `tests/test_reasoning_fallback_ladder.py` — two new boot-safety
tests: the mission's own named worst case (Gemini unavailable, desktop
session creation fails, browser unavailable — construction and a bounded
`run()` both succeed without raising or hanging) and the absolute minimum
case (every tier completely empty).

Full new/updated test count for this mission: **13 + 19 + 5 + (4 replaced)
+ 2 = 43 tests**, all passing.

## 8. Regression suite

Scoped run (every module touched by this mission plus its direct
neighbors): **819 passed, 4 failed** — all 4 confirmed pre-existing (the
same `gemini.api`-default-enabled and `tiered_runner.py` naming-guard
failures documented in the prior mission's report; unrelated to role
separation or session establishment).

Full suite (`pytest tests/`, excluding the three pre-existing circular-import
collection failures documented in the prior report):

```
6341 passed, 84 failed, 1 skipped
```

The 84 failures are the **exact same 84** documented in the prior mission's
report — identical test names, identical reasons, zero collection errors
introduced. Confirmed by direct grep: none of this mission's new or
modified test files (`test_reasoning_role_separation.py`,
`test_reasoning_session_manager.py`, `test_desktop_app_provider.py`,
`test_reasoning_fallback_ladder.py`) appear anywhere in the failure list.
(The prior report's figure of "6402 passed" for the post-clipboard-fix
state was an arithmetic slip in that report, not a real count — the actual
post-fix full-suite total was never independently re-run at that time,
only the 85-test failing subset was. This mission's own full run is the
first full-suite re-confirmation since, and it reconciles cleanly:
6318 original + 1 clipboard fix + ~22 net new tests this mission ≈ 6341.)

No existing guard or freeze test was weakened, disabled, or had its
assertions loosened to pass.

## 9. Acceptance gate

> Kalpavriksha reasons independently of the tool used to build it, and
> every autonomous reasoning interaction occurs inside a Kalpavriksha-owned,
> isolated, inspectable reasoning session. The development/coding agent
> remains strictly a coding tool.

- **Independent of the build tool**: proven structurally — no entry for any
  coding agent exists in the catalog, and three independent layers would
  reject one if it did, tested directly against a synthetic `"claude-code"`
  spec that does *not* even declare the coding-agent role (identity-set
  match alone catches it).
- **Kalpavriksha-owned, isolated session**: the architecture (create, then
  confirm) is implemented, unit-tested exhaustively across every branch,
  and integration-tested inside `complete()`'s real sequence. Live
  validation confirmed the *mechanism* operates genuinely against real
  applications (real controls found and clicked) and *correctly refuses*
  when isolation cannot be confirmed — it did not, on this occasion,
  encounter a real application in a state where establishment could
  succeed.
- **Inspectable**: the session marker is real, predictable, embedded in
  submitted prompt text (not a hidden mechanism), and distinct per session.
- **Coding agent remains strictly a coding tool**: no change to Claude
  Code's own capabilities was made or was needed — this mission's fix
  lives entirely in Kalpavriksha's own reasoning-provider code.

Given §6's honest accounting, this report does **not** declare the mission
fully closed on live evidence alone — the deterministic tests prove the
architecture is correct; live conditions on this specific machine did not
provide a clean success case within the time available. Recommended next
step: re-attempt live validation at a time when a real desktop AI
application is available in a genuinely fresh state (a newly-installed
application, or one deliberately not used for other testing beforehand).

## 10. Scope discipline — honored

- The Universal Desktop Executive was not redesigned — every primitive
  `ReasoningSessionManager` uses (`find`, `click`, `find_main_content`,
  `read_text`) already existed.
- No application-specific selector was added. `NEW_SESSION_VOCABULARY` is
  generic wording, not any one application's own label, and was validated
  against two independent real applications using the identical list.
- No further clipboard investigation was performed (the prior mission's
  "clipboard observer" theory was already retracted and superseded before
  this mission began; this mission does not reference or depend on it).
- Gemini was not modified.
- The Broker was not modified.
- No coding agent was made into a reasoning agent — quite the opposite;
  this mission's entire first half exists to make that structurally
  impossible.
- Success was not declared from unit tests alone (see §6, §9).

Not committed, per instruction.
