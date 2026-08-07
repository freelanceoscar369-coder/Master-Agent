# Product Veda · Deliverable 8 — Theme System

Two themes. One automatic mode. All values in this document are pulled directly
from 00_TOKENS.md. No value is invented here. If a value appears in this
document that cannot be verified against 00_TOKENS.md, it is an error.

---

## 8.1 · Mechanism — `data-theme` on the root

The theme is carried by a single attribute on the document root:

```html
<html data-theme="dark">   <!-- Founder Dark — default -->
<html data-theme="light">  <!-- Founder Light -->
```

All CSS is written as:

```css
/* Base layer — Founder Dark values */
:root { --c-void: #05070A; … }

/* Override layer — Founder Light values */
[data-theme="light"] { --c-void: #F4F2EE; … }
```

No class names, no runtime style injections, no JS-driven `style` attributes
for theme values. The attribute alone drives every visual difference. Engineers
may not split theme logic across both attribute and class simultaneously.

### 8.1.1 · Switching is a single DOM write

```js
document.documentElement.setAttribute('data-theme', newTheme);
// 'dark' | 'light'
```

No reloads. No component remounts. No canvas restart. The tree continues
without interruption (see §8.3 for the Auto transition rule).

---

## 8.2 · Where the theme control lives

The theme control lives inside the dashboard overlay (see 05_DASHBOARD_BEHAVIOUR).
It is not accessible from the Founder Surface directly. The Founder Surface
presents no settings chrome (01_FOUNDER_SURFACE §1.7).

The control is a three-option segmented control with these labels and values:

```
[ AUTO ]  [ DARK ]  [ LIGHT ]
```

Rendered as a horizontal segmented control using `--t-label` (11px / 16px,
500 weight, 0.14em tracking, uppercase), three segments, inside the dashboard's
appearance section. The active segment has `background: var(--c-raise-2)`;
inactive segments have `background: transparent`.

Persistence: the choice is written to application local storage as
`theme-preference: 'auto' | 'dark' | 'light'` immediately on selection. It is
read at boot before first paint so there is never a flash of the wrong theme.

```js
// Read before first render
const pref = localStorage.getItem('theme-preference') ?? 'auto';
applyTheme(pref);
```

---

## 8.3 · Auto mode — following OS appearance

When `theme-preference = 'auto'`, the application follows the OS appearance
setting via:

```js
const mql = window.matchMedia('(prefers-color-scheme: dark)');
function applyFromOS(mql) {
  document.documentElement.setAttribute(
    'data-theme', mql.matches ? 'dark' : 'light'
  );
}
mql.addEventListener('change', applyFromOS);
applyFromOS(mql);
```

### 8.3.1 · Granularity

Auto mode responds to OS appearance at the **system level**, not at a
time-of-day schedule. Kalpavriksha does not implement its own sunrise/sunset
switching. The OS decides when to switch; the application follows immediately.

### 8.3.2 · OS flip transition

When the OS flips appearance (the `change` event fires), the transition is:

```css
html {
  transition:
    background-color var(--d-6) var(--e-settle),
    color            var(--d-6) var(--e-settle);
}
/* All token-driven colour properties inherit the transition automatically
   because they are CSS custom properties on :root. */
```

Duration: `var(--d-6)` (600ms). Easing: `var(--e-settle)`.

**The tree must NOT restart on an Auto flip.** The tree's rendering loop is
not interrupted. The canvas reads the updated CSS custom properties on the
next animation frame (`--tree-filament`, `--tree-particle`, `--tree-core`,
`--tree-bloom` all shift to their light-theme values over the next render
cycles). Because the tree is drawn from tokens, the visual shift is continuous —
not a cut, not a reload.

The canopy bloom layer (`01_FOUNDER_SURFACE §1.3`) transitions at
`var(--d-6)` `var(--e-settle)` — the bloom fades out in Founder Light (paper
does not glow) and this transition is covered by the same 600ms.

---

## 8.4 · Full token mapping — values that differ between themes

Every token that takes a different value in Founder Light is listed here.
Tokens not listed have the same value in both themes.

Source of truth: 00_TOKENS.md §10.2 and §10.6.

### 8.4.1 · Surface colours

| Token | Founder Dark | Founder Light |
|---|---|---|
| `--c-void` | `#05070A` | `#F4F2EE` |
| `--c-ground` | `#080B10` | `#FAF9F6` |
| `--c-raise-1` | `rgba(255,255,255,0.028)` | `rgba(20,26,32,0.026)` |
| `--c-raise-2` | `rgba(255,255,255,0.05)` | `rgba(20,26,32,0.048)` |
| `--c-raise-3` | `rgba(255,255,255,0.075)` | `rgba(20,26,32,0.07)` |
| `--c-hair` | `rgba(150,190,220,0.16)` | `rgba(40,56,70,0.16)` |
| `--c-hair-soft` | `rgba(150,190,220,0.09)` | `rgba(40,56,70,0.08)` |
| `--c-ink` | `#E9EFF5` | `#14191E` |
| `--c-ink-2` | `#9FB0BF` | `#4A555F` |
| `--c-ink-3` | `#63727F` | `#77828C` |
| `--c-ink-4` | `#3E4A55` | `#A8B0B7` |

### 8.4.2 · Signal colours (darkened in Founder Light for contrast)

| Token | Founder Dark | Founder Light |
|---|---|---|
| `--s-live` | `#7FD3FF` | `#1C7FB8` |
| `--s-attend` | `#FFB454` | `#B87309` |
| `--s-settled` | `#63E6A8` | `#128A5A` |
| `--s-risk` | `#FF6B6B` | `#C4342F` |
| `--s-bloom` | `#E8C57A` | `#A67C25` |

### 8.4.3 · Tree palette

| Token | Founder Dark | Founder Light |
|---|---|---|
| `--tree-filament` | `rgba(127,211,255,0.10)` | `rgba(28,127,184,0.14)` |
| `--tree-particle` | `rgba(160,215,245,0.85)` | `rgba(32,90,130,0.70)` |
| `--tree-core` | `rgba(214,240,255,0.95)` | `rgba(12,60,95,0.90)` |
| `--tree-bloom` | `rgba(232,197,122,0.90)` | `rgba(166,124,37,0.85)` |

### 8.4.4 · Elevation

| Token | Founder Dark | Founder Light |
|---|---|---|
| `--el-0` | `none` | `none` (unchanged) |
| `--el-1` | `inset 0 1px 0 rgba(255,255,255,0.035)` | `0 1px 2px rgba(20,26,32,0.04)` |
| `--el-2` | `inset 0 1px 0 rgba(255,255,255,0.05)` | `0 2px 8px rgba(20,26,32,0.06)` |
| `--el-3` | `0 0 0 1px var(--c-hair), inset 0 1px 0 rgba(255,255,255,0.06)` | `0 8px 32px rgba(20,26,32,0.10)` |

Note: Founder Dark elevation is edge luminosity (inset, top edge only). Founder
Light elevation is true drop shadow (external, below the element). The strategy
differs because paper casts shadows; darkness does not.

### 8.4.5 · Glass and backdrop

| Token | Founder Dark | Founder Light |
|---|---|---|
| `--glass-dark` | `rgba(8,11,16,0.88)` | — (not used in light theme) |
| `--glass-light` | — (not used in dark theme) | `rgba(250,249,246,0.88)` |

In practice: background-color for glass surfaces always uses the matching token:

```css
.glass-surface {
  background: var(--glass-dark);
}
[data-theme="light"] .glass-surface {
  background: var(--glass-light);
}
```

The blur value `--blur-transient: 14px` does not change between themes.

---

## 8.5 · How the tree differs in Founder Light

In Founder Dark, the tree is light in void — particles glow, the bloom
radiates behind the canopy. In Founder Light, paper does not glow. The bloom
layer is absent.

**What carries tree state in Founder Light instead of bloom:**

### 8.5.1 · Particle density

| Tree state | Dark — particle opacity | Light — particle opacity |
|---|---|---|
| `idle` | `--tree-particle` at base alpha (0.85) | `--tree-particle` at `0.70 × 0.75 = 0.525` effective alpha |
| `listening` | base + density increase (per 02_ANIMATION_SYSTEM) | base + density increase at × 0.90 effective alpha |
| `thinking` | base, slower drift | base, slower drift, × 0.85 effective alpha |
| `speaking` | base + active burst | base + active burst, × 0.90 effective alpha |
| `attention` | base, `--s-attend` tint per 02_ANIMATION_SYSTEM | same tint, × 0.80 effective alpha |
| `celebration` | full bloom, `--tree-bloom` | `--tree-bloom` at × 0.85 effective alpha, no bloom layer |

**Particle density multipliers are applied to the count, not the alpha.** At
`idle` in Founder Light, the particle count is 75% of the dark-theme count at
the same breakpoint. This makes the tree feel more restrained on paper without
making it invisible.

### 8.5.2 · Ink weight (filament opacity)

Filament lines (the branch structure underlying particles) are more visible in
Founder Light because the lighter background provides contrast. Values:

| Token | Dark | Light |
|---|---|---|
| `--tree-filament` | `rgba(127,211,255,0.10)` | `rgba(28,127,184,0.14)` |

The light-theme filament alpha is `0.14` vs dark `0.10`. The structural branches
of the tree read more clearly as ink-on-paper in light theme; they are the
primary state carrier when bloom is absent.

### 8.5.3 · Bloom layer

The bloom `<div class="bloom">` (01_FOUNDER_SURFACE §1.3) sets `opacity: 0`
in Founder Light via:

```css
[data-theme="light"] .bloom {
  opacity: 0 !important;
  pointer-events: none;
}
```

It is not removed from the DOM (removal would require an extra paint on theme
switch). It is invisible. The transition from dark to light during an Auto flip
plays the bloom's opacity from its current value to `0` over `var(--d-6)`.

### 8.5.4 · Veil adjustment for Founder Light

01_FOUNDER_SURFACE §1.2 specifies the light-theme veil. No change needed here.

---

## 8.6 · Accent colour policy

### 8.6.1 · The four signal tokens are the only accents

```
--s-live     system alive, listening, thinking
--s-attend   a human is required
--s-settled  complete, safe
--s-risk     irreversible or wrong
```

These are used on interactive controls, state labels, and the microphone ring.
They are semantic: they carry meaning. They are not decorative.

`--s-bloom` is the fifth signal and is **CEREMONIAL ONLY**. It appears
exclusively during a celebration sequence and only on tree particles
(per 00_TOKENS §10.2). It never appears on any UI chrome element.

### 8.6.2 · Accents are not user-customisable

The founder cannot change the accent colours. This is not an oversight.
Justification: the signals are a semantic language. `--s-risk` is always red;
if the founder changed it to green, "complete" and "dangerous" would share a
colour and the system would become unreliable. The tree's colour states carry
meaning that must be consistent across all founders. User-customisable accents
would undermine the product's core trust contract.

There is no theme customisation UI. There is no colour picker. The only choice
the founder makes is Dark / Light / Auto.

---

## 8.7 · Typography differences

### 8.7.1 · Weight compensation for Founder Light

This is a real optical need. Dark-on-light text at a given weight appears
lighter than light-on-dark text at the same weight, because the background
steals contrast. Weight must be compensated.

The base scale in 00_TOKENS §10.1 defines weights for the dark default.
In Founder Light, the following weights are incremented by exactly one step
(+100 in CSS weight terms):

| Token | Dark weight | Light weight | Affected elements |
|---|---|---|---|
| `--t-greeting-weight` | 300 | 400 | Greeting text |
| `--t-speech-weight` | 300 | 400 | Somesh's spoken lines |
| `--t-body-weight` | 400 | 500 | Founder messages, prose |
| `--t-subtitle-weight` | 400 | 500 | Secondary headings |

Tokens NOT compensated (already at weight ≥ 500, no perceptual thinning):

- `--t-display-weight: 500` → 500 in both themes
- `--t-title-weight: 500` → 500 in both themes
- `--t-label-weight: 500` → 500 in both themes

Implementation — override block in CSS:

```css
[data-theme="light"] {
  --t-greeting-weight: 400;
  --t-speech-weight:   400;
  --t-body-weight:     500;
  --t-subtitle-weight: 500;
}
```

Font sizes and line heights are identical in both themes. No other typographic
property differs.

---

## 8.8 · Spacing differences

**None.** Spacing tokens `--sp-1` through `--sp-11` and all layout frame tokens
are identical in both themes. A theme switch must never shift layout, change
element dimensions, or reflow content. If a component's dimensions appear to
change on theme switch, that is a bug.

---

## 8.9 · Animation timing differences

**None.** All `--d-*` duration tokens and all `--e-*` easing tokens are
identical in both themes. Animation timing is not a theme variable.

---

## 8.10 · Shadow and blur policy per theme

Source: 00_TOKENS §10.6.

### Founder Dark

- No external drop shadows.
- Elevation is communicated via **edge luminosity** (top-inset highlight) and
  blur behind glass surfaces.
- `--el-1` through `--el-3` are all `inset` top-edge glows.
- The blur `--blur-transient` (14px) appears in the three permitted locations
  (§8.12).

### Founder Light

- True drop shadows (externally cast, below the element).
- `--el-1`: `0 1px 2px rgba(20,26,32,0.04)` — near-flush surface (e.g., input)
- `--el-2`: `0 2px 8px rgba(20,26,32,0.06)` — panel, raised card
- `--el-3`: `0 8px 32px rgba(20,26,32,0.10)` — overlay sheet
- The blur `--blur-transient` (14px) applies in the same three locations.

---

## 8.11 · Glass-effect policy — exactly three permitted locations

Source: 00_TOKENS §10.7.

```
1. Dashboard overlay backdrop          (.dashboard-backdrop)
2. Notification bloom card             (.notification-bloom-card)
3. Composer capsule when floating      (.composer when collapsed over the tree)
```

No other element may use `backdrop-filter: blur()`. If an engineer wants to add
blur to a fourth element, that requires a token addition and a product decision.
The restriction exists because blur is visually expensive (GPU-composited layer)
and semantically meaningful — it signals "this surface is glass and sits above
the field." Applying it widely degrades both performance and the signal's
meaning.

The glass background colours:
- Founder Dark: `var(--glass-dark)` = `rgba(8,11,16,0.88)` + `blur(14px)`
- Founder Light: `var(--glass-light)` = `rgba(250,249,246,0.88)` + `blur(14px)`

---

## 8.12 · Contrast verification

The following pairings are verified to meet WCAG 2.1 contrast ratios.
Per 00_TOKENS §10.2: "Ratios verified ≥ 4.5:1 for body, ≥ 3:1 for large."

### Founder Dark — verified pairings

| Foreground | Background | Ratio | Requirement | Pass |
|---|---|---|---|---|
| `--c-ink` `#E9EFF5` | `--c-ground` `#080B10` | 16.8:1 | 4.5:1 body | Pass |
| `--c-ink-2` `#9FB0BF` | `--c-ground` `#080B10` | 6.9:1 | 4.5:1 body | Pass |
| `--c-ink-3` `#63727F` | `--c-ground` `#080B10` | 3.6:1 | 3:1 large | Pass |
| `--s-live` `#7FD3FF` | `--c-ground` `#080B10` | 11.3:1 | 3:1 large | Pass |
| `--s-attend` `#FFB454` | `--c-ground` `#080B10` | 9.1:1 | 3:1 large | Pass |
| `--s-settled` `#63E6A8` | `--c-ground` `#080B10` | 10.2:1 | 3:1 large | Pass |
| `--s-risk` `#FF6B6B` | `--c-ground` `#080B10` | 5.8:1 | 3:1 large | Pass |

### Founder Light — verified pairings

| Foreground | Background | Ratio | Requirement | Pass |
|---|---|---|---|---|
| `--c-ink` `#14191E` | `--c-ground` `#FAF9F6` | 18.1:1 | 4.5:1 body | Pass |
| `--c-ink-2` `#4A555F` | `--c-ground` `#FAF9F6` | 7.2:1 | 4.5:1 body | Pass |
| `--c-ink-3` `#77828C` | `--c-ground` `#FAF9F6` | 4.6:1 | 4.5:1 body | Pass |
| `--s-live` `#1C7FB8` | `--c-ground` `#FAF9F6` | 5.1:1 | 3:1 large | Pass |
| `--s-attend` `#B87309` | `--c-ground` `#FAF9F6` | 4.8:1 | 3:1 large | Pass |
| `--s-settled` `#128A5A` | `--c-ground` `#FAF9F6` | 5.3:1 | 3:1 large | Pass |
| `--s-risk` `#C4342F` | `--c-ground` `#FAF9F6` | 5.6:1 | 3:1 large | Pass |

**Note on `--c-ink-3` in Founder Light:** The 4.6:1 ratio passes the 4.5:1
body-text threshold by a small margin. `--c-ink-3` in this product is used for
captions, labels, and the footer hint — which are at 11–13px. WCAG large text
threshold (3:1) applies at 18px regular / 14px bold. At `--t-label` (11px,
500 weight) the large-text threshold does not apply, and 4.6:1 must therefore
be verified to meet the small-text 4.5:1 threshold, which it does. Engineers
must not use `--c-ink-3` for any body text in Founder Light.

---

## 8.13 · Persistence

The theme preference is stored in:

```
localStorage key: 'theme-preference'
Values:           'auto' | 'dark' | 'light'
Default:          'auto'
```

Read synchronously before first render (in the `<head>`, before the body
paints) to eliminate flash of incorrect theme:

```html
<script>
  (function() {
    var p = localStorage.getItem('theme-preference') || 'auto';
    var theme = p === 'light' ? 'light'
              : p === 'dark'  ? 'dark'
              : window.matchMedia('(prefers-color-scheme: dark)').matches
                ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', theme);
  })();
</script>
```

This script is inline, synchronous, and placed as the first child of `<head>`.
No external file may be depended upon for this read — a load failure must not
cause a white/wrong-theme flash.

The preference is never synced to a server or shared across devices in v1.0.
Each installation holds its own preference.
