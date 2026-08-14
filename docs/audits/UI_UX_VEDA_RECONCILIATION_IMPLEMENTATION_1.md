# Kalpavriksha UI From Latest HyperAgent Reference — Implementation Report

**14 August 2026 · Kalpavriksha Founder Edition UI**

Continues from `milestone-founder-edition-ui-integration`. Implements the
three priorities in the founder's mission brief against today's newly
generated VEDRA_PROJECT/01_Assets/UI-UX/ reconciliation artifacts, in the
real shipped UI (`desktop_app/web/`) — not HyperAgent's own reference
port (`kv-ui-core`), which remains a separate, unshipped artifact.

## 1 · Reference files used

All read in full from `VEDRA_PROJECT/01_Assets/UI-UX/`, confirmed newer
than the prior mission's own inventory baseline:

- `KALPAVRIKSHA_UI_CLAUDE_IMPLEMENTATION_HANDOFF.md` — gate structure,
  the eight-state parameter table, prominence contract, live-validation
  matrix.
- `KALPAVRIKSHA_UI_FOUNDER_DECISION_GATE.md` — the five sign-off items
  (state model, bloom/colour rulings, dashboard architecture, view
  metrics placement, celebration trigger policy) with reasoning and
  VEDA-amendment verdicts.
- `KALPAVRIKSHA_UI_V1_V2_RECONCILIATION.md` §D–H — the two-axis
  (STATE × PROMINENCE) finding, the 8-state table, the four-view
  dashboard architecture and its ruling on each of the old 9 proposed
  pages, reduced-motion requirements.
- `thread-context.md` — HyperAgent's own working hypotheses for the
  "feels dead" symptom.
- `PRODUCT_VEDA_v1.0_extracted/veda/02_ANIMATION_SYSTEM.md` §2.2–2.3.2 —
  the authoritative six-state parameter values and the state-priority
  rule (Celebration > Speaking > Listening > Thinking > Waiting > Idle),
  read directly from source rather than taken from the reconciliation's
  restatement of it.

## 2 · Priority 1 — tree / animation

**Root cause, not "insufficient breathing":** `tree.js`'s `frame()` loop
had no per-state character at all — every state (idle through
celebration) rendered with the same breathe amplitude, drift, and
particle-chase stiffness. The tree looked the same whether idle or
executing, because it *was* the same. Fixed by porting VEDA
§2.2's own nine-parameter table (`STATE_PARAMS`, `tree.js:39-49`) —
`breatheAmp`/`breathePeriod` (the resting heartbeat, kept subtle),
`pulseDir`/`pulsePeriod`/`pulseCrest` (the larger expand/contract
envelope VEDA's own H4 finding identifies as the channel that actually
reads as "alive"), `driftMul`/`seekStiffness` (how loosely particles
wander vs. how taut their chase is), and `bloomOpacity`/`bloomToken`.
Two additive states approved by the Decision Gate (Item 2) —
`executing` (shares Thinking's basin: steady rhythm, tighter drift) and
`recovering`/`failed` (pulseDir reversed to DOWN, loose stiffness,
dimmed bloom) — use the same table, not invented separately.

The renderer's own established architecture (`TreeField`'s
edges/nodes/parts/branch-recursion model, canvas particle rendering) is
untouched — this is parameterization of the existing renderer, not a
replacement, per the explicit instruction not to copy HyperAgent's
generated geometry.

**A real bug found and fixed, not just the state table:** verifying
reduced-motion live (§4 below) surfaced that the canvas went
permanently blank after any `resize` event when
`prefers-reduced-motion: reduce` was active. `resize()` reassigns
`canvas.width`/`canvas.height`, which always clears the bitmap; with no
animation loop running in reduced motion, nothing ever repainted it —
in full motion the very next `requestAnimationFrame` tick silently
healed this, which is why it was never observed there. Fixed
(`tree.js`, the `resize` listener) by re-issuing the one static frame
after every resize when `reduced` is true. Confirmed by direct canvas
pixel sampling: 18,830 non-transparent pixels before a synthetic
`resize` dispatch, 0 without the fix, 18,830 with it.

Also fixed in this same area, both pre-existing gaps this mission's own
"verify reduced-motion" and "verify all 8 states" requirements exposed:
`frame()` previously called `requestAnimationFrame(frame)`
unconditionally regardless of `reduced`, so the one static frame drawn
on init was overwritten by resumed full animation on the next tick —
reduced motion was non-functional before this session, not merely
suboptimal. And `app.js`'s `applyBloom(tree.state)` referenced a
property `KalpavrikshaTree` never set; replaced with a proper
`currentTreeState` tracked by the new state arbiter (§3 below).

## 3 · State arbiter (`app.js`)

Voice state (`speaking`/`listening`) and execution status
(`thinking`/`executing`/`waiting`/`completed`/`recovering`/`failed`/
`idle`) are two independent signal sources that previously called
`tree.setState()` directly and could race. Added
`recomputeTreeState()`/`setTreeState()` (`app.js:201-247`) as the single
place either signal now flows through, applying VEDA §2.3.2's own
priority order directly (Speaking/Listening outrank execution status;
within execution status, need-founder > failed > recovering > completed
> executing/thinking > idle). Executing and Error/Recovery slot in
alongside Thinking and Waiting because they're mutually exclusive by
construction (derived from one `status` field) — this doesn't alter
VEDA's ordering, it fills the two slots the two additive states occupy.

## 4 · Priority 2 — the two rulings

**Ruling 1 (Waiting/Attention bloom conflict).** `prominence.js` zeroes
bloom at both `reduced` and `minimum` for a stated reason: bloom
competes with Work Region text, which co-occurs with `reduced`. VEDA's
own Waiting bloom (0.70) and this mission's Error/Recovery bloom (0.55)
both only ever occur at `minimum` (execution-status states that need
the founder or have failed unacknowledged map to `minimum`, not
`reduced` — confirmed directly in `prominence.js`'s own
`deriveProminence()`). Ruling: prominence's zero-bloom rule applies only
at `reduced`, unchanged from already-shipped behavior; each state's own
`bloomOpacity` governs at `minimum`. Implemented entirely in
`app.js`'s `applyBloom()` (`currentProminenceLevel === 'reduced' ? 0 :
1`) — `prominence.js` itself is untouched. **This is not a VEDA
amendment**: VEDA's own 0.70 value ships exactly as specified; nothing
in VEDA required bloom to be zero at `minimum`, that was `kv-ui-core`'s
own contract for a different situation (`reduced`) than the one where
Waiting/Error actually occur.

**Ruling 2 (Error/Recovery colour).** No fifth colour was created.
`failed` uses `--s-risk` (`rgba(255,107,107,…)`); `recovering` uses
`--s-live` (`rgba(127,211,255,…)`), matching the Work Region's own
already-shipped `workState.js` `toneFor()` precedent (`failed`/`blocked`
→ risk tone, everything else including `recovering` → live tone) —
confirmed by reading that file directly. This diverges from
HyperAgent's own specific recommendation (uniform `--s-live` for both)
on one point, `failed`'s colour, because HyperAgent's own handoff states
it had never seen `desktop_app/web/`; the founder's own instruction
("failed should use the existing risk semantic if consistent with
VEDA") and the pre-existing shipped precedent both point the same
direction.

Both rulings verified **live**, through the real
`get_execution_status()` → `applyExecutionStatus()` →
`recomputeTreeState()` → `applyBloom()` pipeline (not by calling
`setTreeState()` directly) — see §6.

## 5 · Priority 3 — dashboard architecture

`index.html`'s single dashboard panel is now a four-view segmented
control (`Missions · Record · Rules & Learning · System`,
`app.js:731-889`, `dashboard.css`'s new `.dashboard-views`/
`.dashboard-view-btn` rules). The old panel's entire content (Session,
Environment & Presence, Desktop, Runtime sources, Appearance/theme
control) moved unchanged into `renderSystemView()` — nothing in it was
rewritten, only relocated under its own named view. `AUTONOMY %`
confirmed absent from the shipped app before this mission (`grep`
returned zero matches) — Priority 3's "keep it removed" constraint was
already satisfied, not new work.

`Missions` shows live data from the same `executionStatus`/
`presentWork()` source already driving the Work Region — "Nothing
running." when idle, not a fabricated summary. `Record` and
`Rules & Learning` show an honest "not yet available" placeholder
(`.dash-empty`): reading `founder_edition/boot.py`'s `dashboard()`
method directly confirmed no backend data source exists for either
today (mission-queue/held-state reporting and rule objects are both
absent — Gate 0's own D3/D5 findings, non-blocking). Nothing here
invents backend data or capabilities.

The dashboard sheet is now bounded to `max-height: 65vh` with its own
internal scroll (`dashboard.css`'s `.dashboard-sheet`), per the
reconciliation's own hard constraint that it never obscure the tree
canvas.

## 6 · Live validation

Performed against the actual shipped files
(`desktop_app/web/index.html`/`js/app.js`/`js/tree.js`/`css/*`) served
statically and driven through a temporary bridge shim standing in for
`window.pywebview.api` (deleted before commit — not part of the
repository). All checks below ran through the real polling pipeline,
not by calling internal setters directly, except where noted.

**All 8 states + celebration**, read via computed `.bloom` style after
`setTreeState()`:

| State | bloomOpacity | bloomToken (RGB sampled) |
|---|---|---|
| idle | 0.60 | `--s-live` (127,211,255) |
| listening | 1.00 | `--s-live` |
| thinking | 0.85 | `--s-live` |
| executing | 0.80 | `--s-live` |
| speaking | 1.00 | `--s-live` |
| waiting | 0.70 | `--s-attend` (255,180,84) |
| completed | 0.85 | `--s-settled` (99,230,168) |
| recovering | 0.55 | `--s-live` |
| failed | 0.55 | `--s-risk` (255,107,107) |
| celebration | 1.00 | `--s-bloom` (232,197,122) |

Every value matches `STATE_PARAMS`/`CELEBRATION_PARAMS` exactly; a
118-assertion Node structural test (scratchpad, not committed) confirms
the table itself matches VEDA's six source values and both rulings'
colour tokens.

**End-to-end ruling verification**, driven via synthetic
`get_execution_status()` responses through the real poll loop (not
direct state injection):

- `status: 'executing'` → `currentProminenceLevel: 'reduced'`,
  bloomOpacity forced to `0` — the pre-existing `reduced` gate,
  unchanged, confirmed still working.
- `status: 'awaiting_approval', requires_founder_completion: true` →
  `currentProminenceLevel: 'minimum'`, tree state `waiting`,
  bloomOpacity `0.7`, amber — Ruling 1 confirmed live at the one
  prominence level where it actually matters.
- `status: 'failed'` (unacknowledged) → `minimum`, tree state `failed`,
  bloomOpacity `0.55`, `rgba(255,107,107,…)` — Ruling 2 confirmed live.

**Celebration trigger**, via the real "Mark complete" button click (not
a direct `tree.celebrate()` call): clicking with
`requires_founder_completion: true` and a `completion_id` fired the
burst (bloomOpacity 1.0, `rgba(232,197,122,…)`), then reverted to the
ongoing state's own bloom after the burst window elapsed;
`celebratedCompletionIds` recorded the id, confirming the idempotency
the Decision Gate's Item 5 requires (never re-fires for the same
completion).

**Reduced motion**: with `prefers-reduced-motion: reduce` active,
initial paint showed a legible branch/skeleton structure (canvas pixel
sample: 18,830 non-transparent pixels of 171,205 total); confirmed it
survives a `resize` event only after the fix in §2 (0 pixels without
it, 18,830 with it). Screenshot evidence taken at both idle and a
mid-branch view — reads clearly as a tree, not a loading indicator.

**Motion is visible in full-motion mode**: sampled two canvas frames
1 second apart in the `thinking` state — 20,145 of 171,205 pixels
(~12%) changed alpha by more than 2 levels, confirming the pulse/drift
envelope is visibly live, not imperceptible.

**Dashboard four-view switching**: `Missions` is the default view on
open, shows "Nothing running." when idle; clicking `Record`, `Rules &
Learning`, and `System` each updated `currentDashboardView`,
`aria-selected`, and rendered the expected content (`System` reproduced
every row the old single-panel view had — Session/Environment &
Presence/Desktop/Runtime sources/Appearance, theme buttons functional).

## 7 · Regression results

**JS side** (the only code this mission touched): `node --check` passed
on `tree.js` and `app.js` after every edit. No JS test framework exists
in this repository (no `package.json`); the live browser validation in
§6 plus the 118-assertion structural test are the available regression
coverage.

**Python side**: zero `.py` files touched by this mission. Ran the
mission-relevant suite in a clean worktree at HEAD (`47bda47`) with
`PYTHONPATH` pointed at the worktree's own `src/` (Engineering Rule
001) — **96 failed, 396 passed**, spanning `test_desktop_executive.py`,
`test_founder_edition_assembly.py`, `test_founder_edition_boot.py`.
Sampled failures are real and pre-existing, not this mission's doing:
an architecture guard fails because `desktop_shell.py` imports `socket`;
a capability-count assertion expects 12 but the registry now has 19;
`FounderEditionApp.boot()` reports `ready is False` in this
environment. This is unrelated to the UI work above (confirmed: the
worktree excludes all uncommitted changes by construction, and this
mission never touched a `.py` file) but is a genuine, currently-broken
backend regression at the last committed tag, worth flagging rather
than silently absorbing into "not my problem." Per Founder Edition
Finalization Mode (backend frozen post-C34.1), this mission does not
attempt to fix it — recorded as an unresolved finding below and in
project memory for Founder/Hermes triage.

## 8 · Unresolved backend/design conflicts

- **Backend test suite regression** (§7) — 96 failing tests at HEAD,
  unrelated to this mission's changes, needs separate triage.
- **Gate 0's D3/D5/D8 findings** (non-blocking, already known): no
  mission-queue/held-state, rule-object, or audit-record data source
  exists yet, which is why `Record` and `Rules & Learning` are honest
  placeholders rather than populated views. Not a conflict to resolve —
  a scope boundary this mission respected rather than invented past.
- **Gate 3 (breatheAmp base-amplitude reconsideration) was not
  entered.** Its own ordering only opens it "if Gate 2 passes and the
  tree still fails perception" — a live Founder judgment call on the
  shipped app, not something to decide unilaterally inside this
  session. The state-table + resize fix in §2 is Gate 1/2 work; no VEDA
  amendment was made or required.

## 9 · Files changed

`desktop_app/web/js/tree.js`, `desktop_app/web/js/app.js`,
`desktop_app/web/index.html`, `desktop_app/web/css/dashboard.css`. No
other working-tree changes (pre-existing, from earlier missions this
session) were modified or included in this mission's commit.
