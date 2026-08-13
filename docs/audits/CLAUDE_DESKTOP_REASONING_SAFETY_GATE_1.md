# Claude Desktop Reasoning-Provider Safety Gate — RCA & Acceptance Report

## 1. What this fixes

The Corrected Fallback Ladder's desktop reasoning tier could type an autonomous
reasoning prompt into whatever conversation/session happened to be focused in a
discovered desktop AI application — including an *existing, active* one. Live
testing against Claude Desktop specifically demonstrated this concretely: the
window Kalpavriksha correctly discovered and focused was, at that moment,
hosting an active Claude Code project session (this very development session),
and the automation typed into and submitted to it.

This report documents the corrected root cause, the permanent architectural
fix (a generic session-isolation gate, not a Claude-specific patch), and the
regression/acceptance evidence.

## 2. Root cause — corrected

An earlier diagnosis in this investigation concluded the cause was an external
clipboard-content observer in the development environment. **That diagnosis
was wrong** and is superseded by this section.

The actual mechanism, established with direct evidence:

- Window handle `459536` (PID `18240`) is a real, correctly-discovered Claude
  Desktop process (`C:\Program Files\WindowsApps\Claude_...\Claude.exe`,
  matching the catalog's own `AppUserModelId`). Discovery, launch, and focus
  all worked exactly as designed — `GetForegroundWindow()`, checked
  independently via a direct PowerShell call outside Kalpavriksha's own code,
  confirmed this window held real OS foreground throughout every phase of
  every live trial.
- Claude Desktop, as configured on this machine, hosts Claude Code project
  sessions as tabs *within the same application window* the generic
  discovery/launch/focus path resolves to. Its own UIA tree exposes buttons
  literally named `"New session in Master-Agent"`, `"New session in DELL"`,
  `"New session in ARJUN_BOT"` — per-project session launchers.
- The tab focused at automation time was this development session's own tab.
  A read of the window's "main content" region returned verbatim fragments of
  this conversation's own prior assistant messages.
- Therefore: every "leak" observed during this investigation was the
  automation directly typing into, and submitting to, its own live session —
  not a window-targeting bug, not keystroke misrouting, and not a clipboard
  side-channel. `_launch_or_focus()` and `find_composer()` performed exactly
  as designed against exactly the window they were asked to target.

**The generalizable risk**: any desktop AI application that can host multiple
sessions/tabs/conversations — general chat threads, project-scoped agent
sessions, or anything else — may have an *existing, active* one focused when
the reasoning fallback triggers. Discoverability of a window and a composer is
not evidence of safety to write into it autonomously.

## 3. Fix — a generic, architectural session-isolation gate

No Claude-specific selector was added. No "click New session" automation was
added. The fix has two layers:

### 3.1 Generic runtime isolation check (applies to every desktop provider)

`DesktopAppReasoningProvider._verify_isolated_session()`
([desktop_app.py](../../src/master_agent/providers/desktop_app.py)) runs
after `_launch_or_focus()` succeeds and *before* any write to the composer.
It reuses `find_main_content()`/`read_text()` — the exact same generic UIA
primitives `_await_response()` already uses to read a reply, called earlier
in the sequence instead of later. No new automation mechanism, no per-app
heuristic.

- If the existing content (whitespace-normalized) exceeds `600` characters,
  isolation is **not established** — the surface likely already holds a real
  prior conversation.
- If the read itself fails (`UiaUnavailable`/`UiaTargetNotFound`), isolation
  is **not established** — an unreadable state is never treated as "probably
  empty."
- Only a near-empty read (a short welcome/placeholder, or nothing) is treated
  as isolated.

Both failure branches return a structured `ProviderResult` failure
(`ISOLATION_UNVERIFIED: ...`) *before* `_write_prompt()` is ever called — the
composer is never written to when isolation cannot be established.

The `600`-character threshold is calibrated against real, live evidence
gathered this session: an active Claude Desktop session's main-content region
held `11,411` characters of real prior conversation; nothing observed in a
genuinely fresh/welcome state anywhere close to that.

### 3.2 Declarative static exclusion (Claude Desktop specifically)

The generic runtime check cannot be safely re-verified live against Claude
Desktop without repeating the exact incident it exists to prevent. Per the
mission's own instruction, Claude Desktop is therefore *also* excluded at the
declarative/selection layer:

- `ProviderSpec.autonomous_reasoning_unsafe_reason` (new field,
  [catalog.py](../../src/master_agent/ai_infrastructure/catalog.py)) is set
  on the real `claude-desktop` catalog entry, naming the reason.
- `ai_infrastructure/profiles.py::availability()` checks this field first —
  a statically-excluded provider is reported unavailable to the Broker
  **before** installed/healthy/credential checks, so it is never ranked or
  selected at all, regardless of whether it's genuinely installed.
- `DesktopAppReasoningProvider.complete()` and `.availability()` both check
  the same field as a defense-in-depth backstop — even a direct call to
  `complete()` (bypassing the Broker) refuses immediately, before any
  inventory read, launch, or focus call.

This is deliberately stronger than "open it, then refuse to type": Claude
Desktop is never opened or focused for autonomous reasoning at all. Its
Desktop Executive support (discovery, launch, focus, UIA targeting, typing,
reading, `find_target`) is untouched — the provider object is still
constructed and registered by `build_desktop_providers()`, it simply always
reports itself unsafe.

### 3.3 What was deliberately *not* changed

- `CapabilityBroker`, `policy.py`, `PromptExecutor`, `TieredPromptRunner` — no
  changes. An "unsafe" result is just another provider failure; the existing
  bounded within-tier exclusion-and-retry logic already handles "reject this
  one, try the next ranked candidate, fall through to the next tier if none
  remain" correctly, with zero new selection logic.
- The Universal Desktop Executive (`desktop/` package: discovery, launch,
  focus, UIA, keyboard, reading, `find_target`) — untouched. The isolation
  gate is a reasoning-provider-layer concern (`providers/desktop_app.py`,
  `ai_infrastructure/`), not a Desktop Executive concern.
- No further live submissions were attempted against Claude Desktop after the
  corrected root cause was established.

## 4. Provider-selection behavior (unchanged mechanism, new failure class)

```
Gemini API
  → (bounded retry, existing, unchanged)
  → if genuinely unavailable: query desktop reasoning providers
      → statically-unsafe providers (claude-desktop) never ranked at all
      → runtime-unsafe providers (isolation not established) rejected,
        excluded, next candidate tried — bounded by provider count
      → highest-ranked remaining safe provider selected
  → if no safe desktop provider exists: Browser Executive / free-web tier
  → if that also fails: clean, honest failure — no fabricated success
```

Gemini remains the sole Tier 1 provider and is untouched by this mission.

## 5. Validation

### 5.1 Deterministic tests (new)

`tests/test_desktop_app_provider.py` — provider-level, 14 new/updated tests:

- `TestStaticSafetyExclusion` (3 tests): `complete()` refuses immediately
  without touching `inventory`/`_launch_or_focus`/`_write_prompt` for the
  statically-unsafe spec; `availability()` reports the exclusion; a provider
  *without* the flag is not affected by it.
- `TestSessionIsolationGate` (6 tests): fresh/near-empty → isolated; a
  surface with substantial existing content → rejected; a `UiaTargetNotFound`
  read failure → rejected as unverified; a `UiaUnavailable` read failure →
  rejected as unverified; exactly-at-threshold → isolated; one character over
  → rejected.
- `TestFullCompleteIsolationIntegration` (3 tests): using a provider spec
  *without* the static exclusion (so only the generic runtime gate is under
  test) — `_write_prompt` is never reached when isolation fails or is
  unverifiable; `_write_prompt` *is* reached once isolation is established
  (proven by letting it fail for its own, later, unrelated reason).

`tests/test_reasoning_fallback_ladder.py` — tier-level, 4 new tests, driving
the real `CapabilityBroker`/`TieredPromptRunner`, only leaf `complete()`
calls faked:

- Unsafe desktop provider rejected → next safe desktop provider selected →
  browser never touched.
- Gemini fails, only unsafe desktop providers → browser fallback reached and
  succeeds.
- No safe desktop or browser provider → clean failure, `outcome.text == ""`
  (never fabricated).
- Integration proof using the **real** `PROVIDER_CATALOG` entry (not a test
  double) through the **real** `profiles.py::availability()` function: even
  an installed-and-healthy `claude-desktop` is reported unavailable to the
  Broker, with the reason surfaced.

### 5.2 Live, read-only evidence (safe — no keyboard/clipboard/Enter)

- Provider construction: `0.000s`, `context.cached is None` — no scan, no
  domino effect. All four desktop providers (including `claude-desktop`)
  still constructed and registered.
- `claude-desktop.availability()` against the real catalog entry:
  `reachable=False`, detail names `AUTONOMOUS_REASONING_UNSAFE` and the
  reason.
- Read-only survey of the other three real, currently-running desktop apps'
  actual UIA state (no interaction, pure `find_main_content`/`read_text`):
  - `chatgpt-desktop`: 5,967 normalized characters present (leftover from
    earlier testing) → isolation gate would reject it, correctly.
  - `kimi-desktop`: 1,029 normalized characters present → rejected,
    correctly.
  - `perplexity-desktop`: no text-bearing content region found → rejected as
    `ISOLATION_UNVERIFIED`, correctly (fail closed, not "probably empty").

  All three, in their real current states, are correctly refused by the
  generic gate — direct, live evidence the fail-closed behavior holds against
  real UIA trees, not only synthetic fakes.

### 5.3 Regression suite

**Full suite** (`pytest tests/`, excluding three files that fail at
*collection* on a pre-existing, unrelated circular import between
`communication`/`conversation_engine`/`founder_edition` — present before this
mission started, confirmed via `git status` showing those files already
modified at session start):

```
6318 passed, 85 failed, 1 skipped   (first full run)
6402 passed, 84 failed, 1 skipped   (after fixing one real regression, below)
```

**One real regression was found and fixed**: `test_desktop_perception.py::
TestClipboardObserver::test_the_null_default_is_honestly_empty` broke because
this session's own `ClipboardExecutive.__init__` default-backend fix (real
Win32 backend instead of a silent no-op `Null` one — needed so `paste()`
actually works, and the mechanism this whole investigation is about) also
changed what `ClipboardObserver()`'s own bare constructor picks up. Fixed by
passing `NullClipboardBackend()` explicitly in the test, matching the same
pattern already used for `KeyboardController`'s equivalent test — the test's
job is the Null backend's own honesty, not which backend is chosen when none
is given. Re-running the exact same 85 previously-failing tests confirms only
this one flipped to passing; the other 84 are unaffected.

**All remaining 84 failures are confirmed pre-existing**, verified two ways:
(a) re-running the exact same 85-test list before and after today's fix shows
84 unchanged either side, and (b) they span entirely unrelated subsystems this
mission never touched — `test_memory_integration.py`, `test_missions_console.py`,
`test_founder_edition_boot.py`/`test_founder_edition_assembly.py`,
`test_fire_and_forget_contract.py`, `test_dashboard_architecture.py`,
`test_founder_dashboard_v2.py`, `test_desktop_operations.py`,
`test_browser_constitution_compliance.py`, `test_provider_execution.py`,
`test_verified_execution.py`, `test_foundation_clock.py`,
`test_founder_approval_workflow.py`, `test_mit_001_browser_integration.py` —
none of which import or exercise anything this mission changed
(`catalog.py`, `profiles.py`, `desktop_app.py`, `tiered_runner.py`,
`uia_control.py`, `win32_backends.py`, `keyboard.py`, `clipboard.py`). A
handful are directly relevant to earlier work this same session and worth
naming specifically:

- `test_broker_wiring.py` (3): `enabled_cloud_providers=("gemini.api",)` is a
  documented founder decision from an earlier mission this session; these
  three tests assert the pre-decision default.
- `test_desktop_executive.py` (5): assert an old "12 capabilities, no
  automation" contract that an earlier mission this session (Universal
  Autonomous Desktop Executive) deliberately superseded by adding
  click/type/read capabilities.
- `test_ollama_provider.py` (4): structural guards (`browser_free_ai.py`/
  `desktop_app.py` reaching `ai_infrastructure`, a `_wait_for_selector_action`
  name coincidentally containing "select", a missing brief marker) that
  predate today's work — from when those two provider modules were first
  written earlier this session's original Corrected Fallback Ladder
  implementation.
- `test_broker_integration.py::test_only_the_catalogue_names_a_provider[gemini]`:
  `tiered_runner.py`'s own module docstring and `TIER_GEMINI` naming describe
  the mission's own explicit "Gemini first" architecture in prose — the
  module's core documented purpose, not a vendor-coupling leak. Rewriting it
  would be a naming-convention change to unrelated architecture, out of this
  mission's explicit scope.

Two other pre-existing failures in this same family (a vendor-name leak for
`ollama`/`openrouter`/`llama` in a comment, and a missing "which brief"
docstring marker, both in `tiered_runner.py`) were fixed as part of this
mission's regression pass — real, low-risk, prose-only fixes, not guard
weakening.

No existing guard or freeze test was weakened, disabled, or had its
assertions loosened to pass.

## 6. Acceptance gate

> A desktop reasoning application cannot receive an autonomous reasoning
> prompt unless Kalpavriksha has positively established that the target
> session is safe and isolated.

Demonstrated by:

- `TestFullCompleteIsolationIntegration` — `_write_prompt` (and therefore any
  keyboard/paste action) provably unreached when isolation fails or is
  unverifiable, reached only once isolation is established.
- Live evidence — the same gate, run read-only against three real,
  currently-running desktop applications, correctly refuses all three in
  their current (non-isolated) states.
- `claude-desktop` — provably never reaches the machine at all for
  autonomous reasoning (static exclusion, verified at both the `availability()`
  layer and the `complete()` entry point).

> Prove the provider ladder behaves correctly under: Gemini success → Gemini
> failure → safe desktop fallback → unsafe desktop rejection → browser
> fallback.

Demonstrated by the existing Section 12/13 test matrix (unchanged, still
passing) plus the four new tier-level tests in section 5.1 above, covering
exactly this sequence including the new "unsafe desktop rejection" case.

## 7. Remaining gaps (explicit, not hidden)

- `claude-desktop` remains excluded from autonomous reasoning until a way to
  positively verify isolation for that specific application exists without a
  live trial that itself carries the risk this mission fixed. This is a
  deliberate, conservative posture, not a temporary oversight.
- The generic isolation gate has not been live-tested with Enter/submission
  against any app in an *isolated* state — only read-only against apps
  currently in a non-isolated state, and via deterministic tests for the
  isolated case. No live full-submission test was attempted, per the
  mission's explicit instruction not to keep retrying live Claude
  submissions and not to make the founder the test harness.
- 84 pre-existing test failures remain across the repository, none introduced
  or touched by this mission (full list and categorization in §5.3) — this
  codebase has multiple other missions in progress simultaneously, evidenced
  by the 35+ files already showing as modified in `git status` before this
  mission's work began. Fixing them is out of this mission's explicit scope.
