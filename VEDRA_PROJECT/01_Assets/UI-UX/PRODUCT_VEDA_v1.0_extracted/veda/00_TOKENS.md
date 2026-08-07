# Product Veda · Deliverable 10 — Design Tokens

**Authoritative. Every other deliverable consumes these names.** No section may
introduce a value that is not defined here. If a value is needed and absent,
it is added here first.

Format: CSS custom properties. Ship as `tokens.css`, imported before all else.

---

## 10.1 · Typography

Two families. Loaded from Google Fonts; both have variable versions.

```css
--font-display: 'Inter Tight', 'Inter', -apple-system, system-ui, sans-serif;
--font-text:    'Inter', -apple-system, system-ui, sans-serif;
--font-mono:    'IBM Plex Mono', ui-monospace, monospace;
```

**Semantic rule (inherited, unchanged):** mono states machine facts (IDs,
timestamps, amounts, counts, state words). Text/display state language. Never
mixed inside one sentence.

### Scale

Every `line-height` is a whole multiple of 4px. Sizes in px, not rem, because
the desktop shell has a fixed root.

| Token | Size / Line | Weight | Tracking | Use |
|---|---|---|---|---|
| `--t-greeting` | 40 / 52 | 300 | −0.02em | Somesh's greeting, home screen |
| `--t-speech` | 28 / 40 | 300 | −0.015em | Somesh's spoken lines in conversation |
| `--t-display` | 34 / 44 | 500 | −0.02em | Section titles in overlays |
| `--t-title` | 22 / 32 | 500 | −0.015em | Panel titles |
| `--t-subtitle` | 17 / 28 | 400 | −0.01em | Secondary headings |
| `--t-body` | 15 / 24 | 400 | 0 | Founder messages, prose |
| `--t-body-sm` | 13 / 20 | 400 | 0 | Captions, metadata |
| `--t-mono` | 12 / 20 | 400 | 0.01em | Telemetry, transcript timestamps |
| `--t-label` | 11 / 16 | 500 | 0.14em, uppercase | Field labels, state words |
| `--t-numeral` | 48 / 56 | 500 | −0.03em | Large figures; `tabular-nums` always |

```css
--t-greeting-size: 40px;  --t-greeting-lh: 52px;  --t-greeting-weight: 300;
--t-speech-size: 28px;    --t-speech-lh: 40px;    --t-speech-weight: 300;
--t-display-size: 34px;   --t-display-lh: 44px;   --t-display-weight: 500;
--t-title-size: 22px;     --t-title-lh: 32px;     --t-title-weight: 500;
--t-subtitle-size: 17px;  --t-subtitle-lh: 28px;  --t-subtitle-weight: 400;
--t-body-size: 15px;      --t-body-lh: 24px;      --t-body-weight: 400;
--t-body-sm-size: 13px;   --t-body-sm-lh: 20px;
--t-mono-size: 12px;      --t-mono-lh: 20px;
--t-label-size: 11px;     --t-label-lh: 16px;     --t-label-track: 0.14em;
--t-label-weight: 500;
--t-numeral-size: 48px;   --t-numeral-lh: 56px;
```

**Rules.** Flush left everywhere except the greeting and the home-screen
composer, which are centred on the tree's optical axis (see D1). Optical
alignment (ink, not glyph box) applies to `--t-greeting`, `--t-display` and
`--t-numeral`. Max measure for prose: **68ch**. `font-variant-numeric:
tabular-nums` on every numeral and every mono run.

---

## 10.2 · Colour

### Founder Dark (default)

```css
--c-void:        #05070A;   /* deepest field, behind the tree */
--c-ground:      #080B10;   /* base surface */
--c-raise-1:     rgba(255,255,255,0.028);
--c-raise-2:     rgba(255,255,255,0.05);
--c-raise-3:     rgba(255,255,255,0.075);
--c-hair:        rgba(150,190,220,0.16);
--c-hair-soft:   rgba(150,190,220,0.09);
--c-ink:         #E9EFF5;
--c-ink-2:       #9FB0BF;
--c-ink-3:       #63727F;
--c-ink-4:       #3E4A55;   /* disabled only */
```

### Founder Light

**Not an inversion.** Warm paper, not white; the tree reads as ink-on-paper
rather than light-in-void. Ratios verified ≥ 4.5:1 for body, ≥ 3:1 for large.

```css
--c-void:        #F4F2EE;   /* warm paper */
--c-ground:      #FAF9F6;
--c-raise-1:     rgba(20,26,32,0.026);
--c-raise-2:     rgba(20,26,32,0.048);
--c-raise-3:     rgba(20,26,32,0.07);
--c-hair:        rgba(40,56,70,0.16);
--c-hair-soft:   rgba(40,56,70,0.08);
--c-ink:         #14191E;
--c-ink-2:       #4A555F;
--c-ink-3:       #77828C;
--c-ink-4:       #A8B0B7;
```

### Signals — identical in both themes

Four states, plus one ceremonial accent.

```css
--s-live:     #7FD3FF;   /* system alive, listening, thinking */
--s-attend:   #FFB454;   /* a human is required */
--s-settled:  #63E6A8;   /* complete, safe */
--s-risk:     #FF6B6B;   /* irreversible or wrong */
--s-bloom:    #E8C57A;   /* CEREMONIAL ONLY — celebration. See D2.7 */
```

In Founder Light, signals darken for contrast while keeping hue identity:

```css
[data-theme="light"] {
  --s-live:    #1C7FB8;
  --s-attend:  #B87309;
  --s-settled: #128A5A;
  --s-risk:    #C4342F;
  --s-bloom:   #A67C25;
}
```

**Rules.** Colour is a semantic, never decoration. State is always carried by
**colour AND word** — every state readable in greyscale. `--s-bloom` may appear
only during a celebration sequence and only on tree particles; it is never a UI
colour. No other colour exists in the product.

### Tree palette

```css
--tree-filament:   rgba(127,211,255,0.10);  /* branch lines, dark theme */
--tree-particle:   rgba(160,215,245,0.85);
--tree-core:       rgba(214,240,255,0.95);  /* pulse crest */
--tree-bloom:      rgba(232,197,122,0.90);
[data-theme="light"] {
  --tree-filament: rgba(28,127,184,0.14);
  --tree-particle: rgba(32,90,130,0.70);
  --tree-core:     rgba(12,60,95,0.90);
  --tree-bloom:    rgba(166,124,37,0.85);
}
```

---

## 10.3 · Spacing

Base unit **4px**. Vertical rhythm **8px**. Nothing off-scale.

```css
--sp-1: 4px;    --sp-2: 8px;    --sp-3: 12px;   --sp-4: 16px;
--sp-5: 24px;   --sp-6: 32px;   --sp-7: 48px;   --sp-8: 64px;
--sp-9: 96px;   --sp-10: 128px; --sp-11: 160px;
```

Layout frame:

```css
--frame-margin-desktop: 64px;
--frame-margin-laptop:  48px;
--frame-margin-tablet:  32px;

/* --frame-margin is the RESOLVED active value. Components reference only this;
   they never branch on breakpoint themselves. */
--frame-margin: var(--frame-margin-desktop);
--measure-prose: 68ch;
--measure-conversation: 720px;
```

```css
@media (max-width: 1439px), (max-height: 799px) {
  :root { --frame-margin: var(--frame-margin-laptop); }
}
@media (max-width: 1179px) {
  :root { --frame-margin: var(--frame-margin-tablet); }
}
```

---

## 10.4 · Corner radius

Premium reads as *nearly* square. Nothing is round except a true circle.

```css
--r-0: 0px;      /* rules, dividers, tree canvas */
--r-1: 4px;      /* inputs, chips, small controls */
--r-2: 8px;      /* panels, message bubbles */
--r-3: 14px;     /* overlays, sheets */
--r-4: 20px;     /* composer capsule */
--r-full: 999px; /* mic button, status dots only */
```

---

## 10.5 · Animation durations and easing

```css
--d-1:  120ms;   /* hover, focus ring */
--d-2:  180ms;   /* colour change, small state */
--d-3:  240ms;   /* fade in/out, opacity */
--d-4:  320ms;   /* control morph, mic state */
--d-5:  420ms;   /* element enter, settle */
--d-6:  600ms;   /* panel transition */
--d-7:  900ms;   /* overlay reveal */
--d-8:  1400ms;  /* tree state change */
--d-9:  2400ms;  /* tree assembly */
--d-10: 4000ms;  /* startup growth */
```

### Latency gates — thresholds, not transitions

```css
--d-gate: 400ms;   /* APPROVED ADDITION v1.0 */
```

**This is not a transition duration.** It feeds `setTimeout` thresholds that
decide whether an indicator is shown at all. An operation that completes inside
`--d-gate` shows nothing — no thinking indicator, no loading state, no spinner.
Manufactured deliberation is forbidden, and this token is how that is enforced
numerically.

Used in exactly three places: the thinking indicator gate
(`04_CONVERSATION_DESIGN §4.6`), the history-loading gate (`04 §4.10`), and the
voice silent-window gate (`03_VOICE_EXPERIENCE §3.6`).

### Computed layout variables — a JS contract, not tokens

Three values are written to `:root` by JavaScript on mount and on every resize.
They are **not design tokens** and must never be hand-authored in CSS:

```
--mic-top          top edge of the microphone, px from viewport top
--mic-bottom       bottom edge of the microphone ring, px
--composer-height  current composer height incl. auto-grow, px
--composer-top     top edge of the composer capsule, px from viewport top
```

Contract: set on `document.documentElement`, updated in a single
`ResizeObserver` callback, batched to one write per frame. Consumers position
against them rather than duplicating layout maths — see
`03_VOICE_EXPERIENCE §3.2–3.3` and `04_CONVERSATION_DESIGN §4.8–4.10`.

**Four easings. No fifth.**

```css
--e-settle: cubic-bezier(0.16, 1, 0.30, 1);   /* enters, settles — default */
--e-exit:   cubic-bezier(0.40, 0.00, 1, 1);   /* leaves */
--e-linear: linear;                            /* progress, waveform, timers */
--e-breathe: cubic-bezier(0.45, 0, 0.55, 1);  /* symmetric loops */
```

**Rules.** Nothing bounces. Nothing spins. Overshoot permitted at ≤3% in
exactly two places (decision settle, celebration bloom). Motion expresses state
change and mass — never delight for its own sake. Content is legible at frame
one; no animation gates a read.

---

## 10.6 · Elevation

No drop shadows in Founder Dark — they make mud. Elevation is **edge luminosity
plus blur**. Founder Light gets true shadows, because paper casts them.

```css
/* dark */
--el-0: none;
--el-1: inset 0 1px 0 rgba(255,255,255,0.035);
--el-2: inset 0 1px 0 rgba(255,255,255,0.05);
--el-3: 0 0 0 1px var(--c-hair), inset 0 1px 0 rgba(255,255,255,0.06);

/* light */
[data-theme="light"] {
  --el-1: 0 1px 2px rgba(20,26,32,0.04);
  --el-2: 0 2px 8px rgba(20,26,32,0.06);
  --el-3: 0 8px 32px rgba(20,26,32,0.10);
}
```

Four planes only: **field** (tree) · **content** · **live** · **transient**.
There is no fifth plane, which means **there are no modals** in the product.

```css
--z-field: 0; --z-content: 10; --z-live: 20; --z-transient: 30;
```

---

## 10.7 · Blur and glass

Glass is **hard and thin**, not soft and thick. One blur value.

```css
--blur-transient: 14px;   /* transient plane only */
--glass-dark:  rgba(8,11,16,0.88);
--glass-light: rgba(250,249,246,0.88);
```

### Notification glow — canvas ratios, not CSS lengths

```css
--notif-glow-radius-t1:  0.06;   /* APPROVED ADDITION v1.0 */
--notif-glow-radius-t2:  0.10;
--notif-glow-radius-t3:  0.16;
--notif-glow-opacity-t1: 0.38;
--notif-glow-opacity-t2: 0.55;
--notif-glow-opacity-t3: 0.70;
```

Dimensionless ratios passed to the tree's canvas renderer, not CSS lengths.
Radius is a fraction of canvas width; opacity is the peak at the glow centre
with radial falloff to zero. Consumed only by
`09_NOTIFICATION_SYSTEM §9.3` for localised leaf glow.

Blur appears in exactly three places: the dashboard overlay backdrop, the
notification bloom card, and the composer when it floats over the tree.
Nowhere else.

---

## 10.8 · Iconography

**14 icons. No icon set is imported.** All are 20×20, 1.5px stroke,
`currentColor`, square cap, square join, drawn on a 20px grid with 2px padding.

`microphone` · `microphone-muted` · `waveform` · `keyboard` · `send` ·
`chevron-down` · `chevron-right` · `close` · `minimize` · `check` ·
`alert-triangle` · `sun` · `moon` · `circle-dot`

No avatars. No mascot. No assistant icon. No generic AI glyph. **The tree is
the only mark**; nothing else may represent Somesh.

---

## 10.9 · Interaction timing and states

Every interactive element defines all five states. No exceptions.

| State | Change | Duration / Easing |
|---|---|---|
| **rest** | baseline | — |
| **hover** | `--c-raise-1` → `--c-raise-2`; border `--c-hair-soft` → `--c-hair`; ink one step brighter | `--d-1` `--e-settle` |
| **focus-visible** | 2px ring `--s-live` at 40% opacity, offset 2px. Never removes the hover treatment | `--d-1` `--e-settle` |
| **pressed** | scale `0.985`, `--c-raise-3` | `--d-1` `--e-settle` |
| **disabled** | ink `--c-ink-4`, border `--c-hair-soft`, `cursor: not-allowed`, opacity 1 (never fade — a faded control reads as broken) | instant |

Cursor: `default` on text, `pointer` on controls, `text` on inputs. No custom
cursors.

Hit target minimum **32×32** (44×44 on tablet). Focus order follows DOM order;
one visible focus ring at a time.

---

## 10.10 · Motion accessibility

`prefers-reduced-motion: reduce` is a **designed state, not a fallback.** Every
animation declares a static endpoint:

- Tree renders fully grown and still; state carried by colour and density only.
- Pulse, breathing, particle drift: off.
- Transitions collapse to `--d-1` opacity only. No transform animates.
- Voice waveform becomes a static 3-bar level meter that steps, not sweeps.
- Celebration becomes a single 240ms colour shift to `--s-bloom`, then rest.

`prefers-contrast: more` switches to the `contrast` variant of the active
theme: hairlines to 0.30 alpha, ink to pure `#FFFFFF` / `#000000`, signals to
full saturation.
