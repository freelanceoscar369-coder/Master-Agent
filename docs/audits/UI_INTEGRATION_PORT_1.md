# UI Integration Port — Completion Report

**14 August 2026 · Kalpavriksha Founder Edition UI**

Closes the handoff gap `docs/audits/UI_INTEGRATION_AUDIT.md` identified:
that audit's own workspace had no shipped application and no git
repository to port into. This mission located both, ported the ordered
manifest into the real shipped UI (`desktop_app/web/`), and validated it
live.

## 1 · Repository recovery

`D:\MasterAgent` confirmed as the one, unique Kalpavriksha repository on
this machine — a systematic search of `C:`, `D:`, and `E:` for
`kalpavriksha_desktop.py` and `REASONING_LAYER_MILESTONE_1.md` (the
project's own entry point and its own milestone doc) found exactly one
match each, both here. `milestone-reasoning-layer` and
`milestone-desktop-intelligence-observe` are both present as real tags;
Engineering Rule 001 is documented (this session's own memory, stated by
the founder 2026-08-05).

`docs/audits/UI_INTEGRATION_AUDIT.md` itself was not in the repository's
tracked or working-tree files — found inside
`VEDRA_PROJECT/01_Assets/UI-UX/kalpavriksha-ui-integration-audit.zip`, an
untracked packaged export of the isolated HyperAgent workspace that audit
document describes. Extracted (read-only) to inspect; the three markdown
audit documents (this one's own direct inputs) are now committed to
`docs/audits/` as part of this mission, matching this repository's own
convention of keeping its full audit trail in that directory rather than
inside an opaque archive.

## 2 · What the shipped app actually is

The reference workspace's own "surface"/"founder-edition" React
components (`ConversationSurface`, `FounderActions`, `MissionStrip`,
`SystemLine`, `EnvironmentPanel`, `FounderRuntimePanel`) describe a
**different UI shape** than what is actually shipping: `desktop_app/web/`
is a vanilla HTML/CSS/JS, canvas-rendered "tree" application (no React,
no build step), driven by `founder_edition/desktop_shell.py`'s
`window.pywebview.api` bridge. Checked directly, not assumed: none of
`FounderActions`, `MissionStrip`, `EnvironmentPanel`,
`FounderRuntimePanel`, or an "Awaiting runtime" panel exist anywhere in
`desktop_app/web/js/app.js`, `tree.js`, or `index.html` (`grep` for their
own vocabulary — "founder.action", "mission.strip", "awaiting.runtime" —
found zero matches).

**Consequence for the port manifest's steps 3, 4, 5** ("delete the four
disabled action buttons" · "delete the mission-strip band" · "collapse
the two Awaiting-runtime panels"): **not applicable, not skipped.** There
was never anything here to delete — those elements are specific to the
reference workspace's own, separate composition, never built in the
shipped tree UI. Confirmed by direct inspection of the actual shipped
source, not inferred from the manifest's own wording.

Steps 1, 2, 6, 7, 8 all apply and are implemented below.

## 3 · The authoritative `status` enum — resolved, not guessed

The audit's own SS7 flagged two coexisting vocabularies and asked for the
real one before step 6. Found directly in the committed backend:
`src/master_agent/missions/execution_status.py::ExecutionStatus` — the
Phase 3 vocabulary (`understanding` / `planning` / `awaiting_approval` /
`executing` / `observing` / `verifying` / `recovering` /
`awaiting_founder_completion` / `completed` / `failed` / `blocked`,
underscored) **is** the authoritative one, spelled identically to what
the reference `workState.ts`/`prominence.ts` already used. `idle` has no
backend spelling — the backend represents "nothing in flight" as
`status: null`, which both reference modules already treat as idle. The
other vocabulary (`ExecutionPhase`, hyphenated, `presence/src/types.ts`)
belongs to a different, C19A/C20-era layer, not this contract.

This same contract is **already fully wired end to end**, found by
inspection, not built here:
`window.pywebview.api.get_execution_status()` →
`founder_edition/desktop_shell.py::DesktopShellApi.get_execution_status()`
→ `lambda: status.as_dict()` (`kalpavriksha_desktop.py`), and
`confirm_completion(completion_id)` the same way, relaying to
`MissionControl.confirm_completion()`. Both are already in the bridge's
`window.expose(...)` list. `tests/test_task_2_5_execution_contract.py`
(15 tests) already covers this contract and was not touched.

## 4 · What was ported

| Manifest step | Ported as | Notes |
|---|---|---|
| 1 · `prominence.ts`+`.css` | `js/prominence.js`, `css/prominence.css` | Logic/values unchanged; TS types removed. |
| 2 · `data-prominence` + 5 vars on the tree | `js/app.js::applyProminence()`, on `documentElement` | Canvas gets `transform:scale()`+`opacity` (additive CSS, no prior rule existed); `.veil` gets `opacity` (previously undeclared, always opaque); bloom composes via a multiplier (see SS5); breathing amplitude via a new `tree.js::setBreatheAmplitude()` hook. |
| 3, 4, 5 | N/A | See SS2 — nothing to delete in this shipped UI. |
| 6 · `workState.ts`+`timing.ts` | `js/workState.js`, `js/timing.js` | Logic/thresholds unchanged. |
| 7 · Work Region | `js/app.js::renderWorkRegion()` + `css/work-region.css` (`.kv-work-region*`) | Polled from `get_execution_status()` every 1.5s (no push channel exists for this contract, unlike voice state). |
| 8 · Founder Completion | `js/app.js::renderCompletionRequest()` + `css/work-region.css` (`.kv-completion*`) | "Mark complete" wired to the real `confirm_completion()`. |

## 5 · Adaptations made composing with existing, richer behaviour

Two places where the reference's own numbers don't transfer literally,
because the shipped tree already has behaviour the isolated reference
workspace's simpler tree did not:

- **Bloom.** The reference's `.bloom` has no other driver, so its own
  `--tree-bloom-opacity` (0.6 ambient / 0 reduced-minimum) is applied as
  an absolute value. The shipped `.bloom` is already driven per
  voice/mic state by `applyBloom()` (six states, hue changes — real,
  tested, Product-Veda-specified behaviour this port must not regress).
  Composed instead of overridden: `--tree-bloom-opacity > 0` becomes a
  multiplier of 1 (ambient — existing behaviour untouched), `= 0`
  becomes a multiplier of 0 (reduced/minimum — bloom extinguished,
  which is the rule's actual intent: *"a light source competing with
  text is the single largest contributor to the reported 'tree over
  work' feeling"*).
- **Breathing amplitude.** The shipped tree already breathes
  (`1 + sin(t)*0.012`, drawn on canvas, not CSS). `--tree-breathe-amp`
  now multiplies that existing `0.012` constant via a new,
  purely-additive `setBreatheAmplitude()` method on both `TreeField` and
  `KalpavrikshaTree` — nothing about the existing animation was
  rewritten.

## 6 · "Send back" — recorded honestly, not fabricated

`CompletionRequest`'s own five-element contract includes a "Send back"
action. Checked directly: `mission_control.py` has `confirm_completion()`
and nothing else for this — `reject()`/`defer()` operate on a different
id namespace (`approval_id`, a separate subsystem) and would be the wrong
call, not a shortcut. "Send back" is rendered (the five-element contract
is honoured) but **disabled**, with an honest `title` explaining why,
rather than wired to an unrelated action or silently doing nothing.

## 7 · Deterministic validation

No JS test framework is wired into `desktop_app/web/` (checked: no
`package.json`, no `*.test.js` anywhere under it, and none was added —
consistent with the manifest's own "smallest clean change set"). Ran a
dependency-free Node smoke test instead, exercising the three ported
modules against scenarios drawn directly from the audit's own SS5 table
and each module's own documented rules — **30/30 pass**: all six
prominence states, `prominenceVars`/transition-token asymmetry, the
message-over-status rule, the idle/unknown-status fail-safe, and every
timing honesty rule (10s elapsed gate, 3-step bar minimum, no ETA,
liveness at 20s, timeout warning at 75%, never a countdown).

## 8 · Live validation

The real, unmodified `desktop_app/web/` files were served statically and
opened in a real browser session — genuinely running the actual shipped
HTML/CSS/JS, not a description of it. `window.pywebview.api` does not
exist outside the real pywebview host, so bridge calls were backed by a
fake `api` object implementing the identical
`get_execution_status()`/`confirm_completion()` contract, letting the
real polling/rendering code run unmodified end to end:

| Verified live | Result |
|---|---|
| Idle | `data-prominence="ambient"`, canvas `scale(1)`/`opacity(1)`, `.work-region-slot` innerHTML `""`, height `0` |
| Executing, in-flight | `data-prominence="reduced"`, canvas `scale(0.55)`/`opacity(0.55)`, veil `0.92`; Work Region headline = the runtime `message` (not the status name), supporting line = `"Step 2 of 4 · Still working"` (liveness assertion correctly appeared after the same message held >20s) |
| Awaiting founder completion | `data-prominence="minimum"`, canvas `scale(0.3)`; Completion Request rendered the real `result` as the summary, correct non-terminal consequence line, "Mark complete" enabled, "Send back" disabled with its honest reason |
| Mark complete clicked | `confirm_completion('completion-abc123')` called exactly once with the right id; undo window rendered, actions removed |
| Undo clicked | Actions restored, `data-completed` reverted |
| Back to idle | Prominence returned to ambient, canvas back to `scale(1)`, slot empty again |

Console was checked after every state transition: zero errors throughout.

**Not validated, recorded honestly:**

- The full native pywebview host (a real OS window, the complete
  Python composition root with a live reasoning provider actually
  executing an objective) was not launched end to end — validated
  instead via the real served files plus a bridge double implementing
  the exact contract `desktop_shell.py` already exposes. The contract
  itself already has its own passing backend test suite
  (`test_task_2_5_execution_contract.py`, untouched).
- The `failed`/`blocked` states and the sidebar-adjacent six-state table
  were covered by the Node smoke test (SS7) but not separately
  screenshotted live — `executing`/`awaiting_founder_completion`/idle
  already exercise the same rendering code path those states share.
- The subtle ~1.2%-amplitude breathing-motion difference
  (`--tree-breathe-amp`) was confirmed wired (`setBreatheAmplitude()`
  receives the correct parsed value) but not distinguished by eye —
  too small a visual delta for a screenshot to usefully judge.

## 9 · Regression

**Per Engineering Rule 001**, numbers below are from
`git worktree add <tmp> milestone-founder-edition-ui-integration` +
`pytest`, not the working directory.

`tests/test_task_2_5_execution_contract.py`,
`test_founder_edition_boot.py`, `test_founder_edition_assembly.py`,
`test_desktop_intelligence.py`, `test_desktop_uia.py`,
`test_voice_pipeline.py`, `test_reasoning_session_manager.py`, clean
checkout:

```
280 passed, 47 failed in 56.0s
```

Working-directory runs of the same files showed only 5 failures — the
other 42 are masked there by *other, unrelated* uncommitted
Founder-Edition/runtime Python fixes this mission never touched
(`founder_runtime/wiring.py`, `providers/gemini.py`,
`founder_edition/voice_pipeline.py`, etc. — all already modified,
uncommitted, before this mission started). **Confirmed pre-existing,
not introduced by this commit**: the identical 47 failures reproduce at
the parent tag (`milestone-desktop-intelligence-observe`), checked the
same way, in its own clean worktree, before any UI-integration change
existed. This mission never read or wrote a backend/runtime/reasoning-
layer/Desktop-Intelligence Python file — every failure above is about
`founder_edition`/`founder_runtime` composition, orthogonal to the
frontend this mission actually changed.

`test_desktop_intelligence.py` (30/30) and `test_desktop_uia.py` both
pass cleanly in the same clean checkout, confirming the prior Desktop
Intelligence milestone's own work is undisturbed.

## 10 · Commit scope — a real judgment call, recorded

`desktop_app/web/{index.html,js/app.js,js/tree.js}` each already carried
substantial **uncommitted, pre-existing Founder Edition work** before this
mission started (dark-theme forcing, a mode-switch control, a startup
diagnostics overlay, and — checked directly, `git show HEAD` — a
near-total prior rewrite of `tree.js`/`app.js` that HEAD's own committed
versions do not contain at all). This mission's own additions are layered
directly on top of that work in the same files, and are not separable
from it: the new `prominence.css` targets `canvas#treeCanvas`, an id only
the pre-existing (uncommitted) rename introduced — HEAD's own `index.html`
still has `id="tree"`. Committing "only this mission's lines" on top of
HEAD is not technically coherent here.

**Decision:** commit these three files in full current state. This
mission is, unlike the prior (backend-only) Desktop Intelligence mission,
explicitly chartered to finish integrating the shipped UI — the
pre-existing changes already sitting in these files are the same
"Founder Edition UI" this mission's own brief describes recovering and
completing, not unrelated work from a different subsystem. `base.css`,
`conversation.css`, and `surface.css` also carry pre-existing uncommitted
changes but this mission never edited or depended on them — left
untouched, as usual.

## 11 · Scope discipline held

Not touched: Hermes, Groq, Gemini, any new provider, video generation,
the reasoning-layer architecture, `ReasoningSessionManager`, Desktop
Intelligence (`desktop/intelligence/`), or the Planner/Mission Control
backend beyond reading the already-committed `execution_status.py`
contract. No new UI was designed — every visual rule ported is the one
the prior review already approved (verdict C).
