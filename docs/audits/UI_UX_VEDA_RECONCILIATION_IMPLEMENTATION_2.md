# Approved Kalpavriksha UI/VEDA Reconciliation — Implementation Report

**14 August 2026 · Kalpavriksha Founder Edition UI**

Continues from `milestone-veda-ui-reconciliation`. Reconciles the shipped
UI against the newest HyperAgent artifacts generated later the same day
in `VEDRA_PROJECT/01_Assets/UI-UX/`, which the founder's own brief
identified as superseding the previous mission's interpretation on two
specific points. This report exists because that reconciliation reversed
a prior, explicitly-documented ruling rather than silently amending it.

## 1 · Reference files used (generated after the prior mission's read)

Identified by filesystem timestamp against the prior mission's own read
cutoff (09:16, 14 Aug):

- `kv-probe-approval-html.html`, `kv-tree-reference-html.html`,
  `kv-probe-skeleton-html.html` (09:21–09:23) — three near-identical
  copies of **kv-ui-core's actual reference implementation** (not a
  description of it), each differing only in which state it boots into.
  Read in full. This is the authoritative artifact this mission is
  built on: the exact validated STATE table, PROMINENCE table, and bloom
  composition formula, in runnable code, not prose.
- Two "Corrected reference" screenshots (09:24) — Idle and Approval
  Required, each with a live numeric readout overlay confirming the
  harness's own output.
- `KALPAVRIKSHA_UI_FOUNDER_DECISION_GATE.md`, re-read for §2 ("Where the
  useful V1 metrics land") and §3 (the `AUTONOMY 64%` replacement) —
  confirms `6 rules active` is stated as *interim, until domain
  attribution exists*, not as something to add unconditionally.
- `KALPAVRIKSHA_UI_V1_V2_RECONCILIATION (1).md` — diffed byte-for-byte
  against the copy read last mission; identical, no new content.

## 2 · What changed, and why it's a correction, not an addition

**Reversed: the Waiting/Attention bloom ruling.** The prior mission
resolved VEDA's Waiting bloomOpacity (0.70) vs. `kv-ui-core`'s
bloom-zero-at-minimum rule by letting each state's own bloomOpacity
govern at `minimum`, reasoning that the zero-bloom rule was written for
`reduced` specifically. `kv-probe-approval-html.html` settles this
differently and explicitly, in its own header comment: *"This harness
obeys kv-ui-core (bloom 0) and carries the attend signal in PARTICLE
COLOUR, because kv-ui-core is validated behaviour and must not be
forked."* That is a newer, more authoritative source than the prior
mission's own reasoning — it ships the actual composition formula
rather than a stated intent. This mission reverses the prior ruling
rather than layering a second one on top of it.

**The corrected formula** (`desktop_app/web/js/app.js`, `applyBloom()`),
copied verbatim from `kv-ui-core`:
```
effectiveBloom = stateBloomOpacity × (--tree-bloom-opacity / 0.6)
```
0.6 is prominence's own ambient baseline (`prominence.js`, unedited) —
the gate is exactly 1 at `ambient`, exactly 0 at both `reduced` and
`minimum`. Read live from the CSS custom property every call, never
cached, matching `kv-ui-core`'s own "never cached" rule. The
`currentProminenceLevel` tracking variable the prior mission introduced
for its now-superseded gate logic was removed as dead weight.

**Added: per-state body colour** (`desktop_app/web/js/tree.js`,
`STATE_PARAMS.*.colour`, `resolveColour()`, and the filament/particle
draw calls). This is the load-bearing consequence of the bloom
reversal: with bloom correctly zero at `minimum`, nothing was left to
carry "human required" once amber could no longer appear as a halo.
`kv-ui-core`'s own renderer tints the tree's filaments and particles
themselves, not just the bloom, and this mission ports that — amber
(`--s-attend`) exclusively on the human-required state, settled-green on
Completed, risk-red on Failed, the tree's own neutral token
(`--tree-particle`, already defined in `tokens.css`, unused until now)
everywhere else including `recovering` (deliberately not risk-tinted:
"retrying is the system alive and working, not something wrong" —
`kv-ui-core`'s own stated reasoning, matching the founder's decision 3).
`hasColour` resolution handles both hex (`#rrggbb`, most `--s-*` tokens)
and `rgba(...)` (`--tree-particle`) forms, mirroring `kv-ui-core`'s own
`rgb()` helper.

**Fixed: celebration bloom regression, caught by this mission's own
live testing, not requested.** Applying the corrected gate formula
uniformly would silently suppress the celebration burst whenever it
fires while prominence is still `minimum` — which is exactly when it
fires, since "Mark complete" is clicked from the `waiting` state.
`applyBloom()` now bypasses the gate unconditionally when
`state === 'celebration'`: a bounded, explicit, founder-triggered burst
is not an ambient per-state signal subject to the "bloom competes with
text" rule. Confirmed via a clean single-click test after an earlier
false negative traced to leftover `setTimeout` callbacks from repeated
manual test clicks in the same page session, not a real defect.

**Fixed: a canvas-never-draws race, found during this mission's live
validation, in scope under Priority 1's "verify all states" and
"legible skeleton" requirements.** `tree.js`'s `resize()` — called once
synchronously in `TreeField`'s constructor — could run before the canvas
had ever been laid out (slow first layout pass, fonts still loading, an
ancestor box not yet resolved), getting a 0×0 bounding rect. Nothing
ever corrected it afterward: `canvas.width`/`height` stayed 0, meaning
literally nothing was ever drawn, and in full-motion mode the running
`requestAnimationFrame` loop kept calling `frame()` every tick without
`frame()` itself ever calling `resize()`, so the zero size was
permanent. The window-level `resize` listener (already present, added
last mission for the reduced-motion case) only fires on an actual
window resize, which may never happen if the embedding window's size is
already final at launch — precisely the case in a native pywebview
window, unlike a browser tab. Replaced with a `ResizeObserver` watching
the canvas element's own box directly: it fires once immediately with
whatever size is available and again the moment layout actually
settles, self-healing the race instead of depending on an unrelated
window-level event that might never occur. Falls back to the old
`window.resize` listener if `ResizeObserver` is unavailable (it is not,
in any target environment here, but the fallback costs nothing).

**Confirmed, not changed:** `observing` → Executing (decision 4) was
already correct from the prior mission (`executionTreeState()`,
`app.js`). `recovering` at `reduced` / `failed` (unacknowledged) at
`minimum` (decision-gate doc's own mapping) was already correct —
`prominence.js` was never touched, this mission or last. `breatheAmp`
stays VEDA's canonical `0.006`, untouched (decision 1). No cursor
listeners, no toast/modal/notification architecture exist anywhere in
the shipped files (decision 8, verified by direct grep, zero matches).

**A discrepancy in `kv-ui-core` itself, noted rather than ported.**
`kv-ui-core`'s own filament-opacity formula
(`0.075+((7-e.d)/6)*0.125`) is inverted relative to its own header
comment ("trunk 0.20 -> fine twigs 0.075"): computed out, it actually
gives twigs (`e.d=1`) 0.20 and the trunk (`e.d=6`) ~0.096 — backwards
from its own stated intent, and from the anatomically correct direction
this app's own filament formula already implements (trunk most opaque,
built and documented last mission). "Use kv-ui-core's validated logic"
does not mean porting a formula that contradicts its own author's
stated goal; the existing formula stays, only the colour changed.

## 3 · Explicitly not implemented, and why

**`6 rules active` on the system line (decision-gate §3's interim
replacement for `AUTONOMY 64%`).** Searched
`founder_edition/`, `founder_runtime/` for any rule-count, rule
registry, or rule-object concept — zero matches. The decision-gate doc
itself frames this as interim and conditional ("*until domain
attribution exists*"), not an unconditional instruction, and the
mission brief's own wording ("where the backend currently supports
them") anticipates exactly this case. `AUTONOMY 64%` stays removed (it
was already absent, confirmed again this mission); no replacement
number or count is fabricated in its place.

**Canopy reach / branch-generation depth (decision-gate §3's longer-term
autonomy replacement).** Explicitly stated in the same document as
blocked on "dependency D4" (per-mission domain attribution), which does
not exist in this backend. Not attempted.

## 4 · Live validation

Same technique as the prior mission: the real shipped files served
statically, driven through a temporary bridge shim standing in for
`window.pywebview.api` (deleted before commit). All checks below ran
through the real `get_execution_status()` poll → `applyExecutionStatus()`
→ `deriveProminence()` → `recomputeTreeState()` → `applyBloom()`
pipeline, not by calling internal setters directly.

**The corrected bloom/colour behaviour, end to end:**

| Synthetic status | Tree state | Prominence | Bloom opacity | Body colour |
|---|---|---|---|---|
| (none) | idle | ambient | 0.6 | `--tree-particle` |
| `understanding` | thinking | reduced | **0** | `--tree-particle` |
| `observing` | **executing** | reduced | **0** | `--tree-particle` |
| `blocked` | waiting | minimum | **0** | **`--s-attend`** |
| `recovering` | recovering | **reduced** | **0** | `--tree-particle` |
| `failed` | failed | **minimum** | **0** | **`--s-risk`** |

Confirms: bloom is now correctly zero at both `reduced` and `minimum`
(the reversal); the human-required signal (`blocked`) survives entirely
in body colour with bloom at zero; `observing` maps to `executing`;
`recovering` sits at `reduced` with neutral colour, `failed` at
`minimum` with risk colour — matching the decision-gate doc's own
mapping exactly.

**Celebration**, via the real "Mark complete" click (not a direct
`tree.celebrate()` call): bloom opacity `1` immediately after a clean
click while prominence was still `minimum` — confirms the gate-bypass
fix — then correctly reverts to the ongoing state's own (zero) gated
bloom after the ~2.2s burst window elapses.

**Reduced motion**: `tree.getDebugInfo()` after a fresh load with
`prefers-reduced-motion: reduce` active shows a fully built tree
(219 edges, 2400 particles), correct idle params including the new
`colour` field, and a correctly non-zero canvas size (`1920×1080`
backing, `1280×720` client) with no manual intervention — confirming
the `ResizeObserver` fix self-heals without needing an explicit resize
event.

**Dashboard**: opened cleanly, defaulted to Missions with an honest
"Nothing running." empty state; no `AUTONOMY`/percentage text anywhere
in the page — unaffected by this mission's changes, re-verified rather
than assumed.

**Console**: zero errors logged across every state transition, the
Mark-complete flow, reduced-motion load, and dashboard interaction.

**Pixel-level screenshot evidence**: not obtainable in this session —
the Browser pane reported `document.hidden === true` for the
automation tab (background/non-composited), which Chromium uses to
fully suspend `requestAnimationFrame`, so the canvas never got a chance
to paint a frame for pixel sampling regardless of code correctness.
This is a property of this session's display state, not the
production window (a native, focused pywebview window is never
backgrounded this way). Compensated with direct state/CSS-level
verification (the table above, `tree.getDebugInfo()`, computed-style
reads of `--tree-bloom-opacity` and the bloom element itself) at every
step instead of relying on rendered pixels. The prior mission's own
pixel-sampling evidence (for the resize-in-reduced-motion fix) remains
valid for the parts of the renderer this mission did not touch;
`resolveColour()`'s token-parsing correctness was independently
confirmed by evaluating it directly against live `getComputedStyle`
output for all five colour tokens (`--tree-particle`, `--s-attend`,
`--s-settled`, `--s-risk`, `--s-bloom`), matching `kv-ui-core`'s own
values exactly.

## 5 · Regression results

**JS side**: `node --check` passed on `tree.js` and `app.js` after every
edit. A 138-assertion structural test (scratchpad, not committed)
confirms the corrected `STATE_PARAMS`/`CELEBRATION_PARAMS` tables:
9 states × 10 required fields each (including the new `colour`), amber
appears on exactly one state, `recovering` is confirmed neutral (not
risk), `breatheAmp` confirmed unchanged at VEDA's `0.006`.

**Python side**: zero `.py` files touched by this mission (same as
last). The pre-existing, unrelated backend regression recorded in
project memory (`backend-test-suite-96-failures-at-head.md` — 96/492
failing in the mission-adjacent subset, 203/6729 failing full-suite, at
the prior milestone tag) is out of scope for a UI-only mission per
Founder Edition Finalization Mode and is not re-litigated here; not
re-run in full given no backend code changed since it was last measured.

## 6 · Unresolved backend/design conflicts

- **`6 rules active`** (§3) — no backend rule-count capability exists;
  documented rather than fabricated.
- **Canopy reach / branch depth** (§3) — blocked on domain-attribution
  data (dependency D4) that does not exist yet.
- **The pre-existing backend test-suite regression** (§5) — unrelated,
  not re-verified this mission, already flagged for separate triage.

## 7 · Files changed

`desktop_app/web/js/tree.js`, `desktop_app/web/js/app.js`. No other
working-tree files touched.
