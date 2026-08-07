# Product Veda · Deliverable 1 — Founder Surface Specification

The Founder Home Screen. The first and default screen. Everything else in the
product is reached from here and returns here.

---

## 1.0 · The composition idea, stated once

**The tree rises from the bottom edge of the window. Somesh's words emerge from
the trunk.**

That single sentence determines the whole layout. The tree is not a picture
placed on a screen — it is the ground the language grows out of. The text stack
sits on the tree's vertical axis, low, where the trunk is; the canopy is above
and behind, uninterrupted.

This is why the composition is **centred**, and it is the only centred layout in
the product. Everywhere else — dashboard, conversation history, panels — is
flush left. Centring the home screen is a deliberate exception: a tree is
symmetrical about its trunk, and the founder is meeting it head-on.

---

## 1.1 · The vertical stack (reference: 1440 × 900)

One axis, `x = 50%` of the window's inner width. Every element below is centred
on it. Positions are given as a percentage of window inner height **and** as px
at the reference size, so there is no ambiguity.

| # | Element | Top edge | px @900h | Height |
|---|---|---|---|---|
| — | Tree canopy top | 16% | 144 | — |
| — | *(tree occupies 16% → 100%, trunk exits the bottom edge)* | | | |
| 1 | Greeting | 56% | 504 | 52 (one line) |
| 2 | Presence line | 63.5% | 572 | 24 |
| 3 | Microphone | 71% | 639 | 72 |
| 4 | Composer capsule | 82% | 738 | 56 |
| 5 | Footer hint | 92% | 828 | 16 |

Gaps between stack items are `--sp-5` (24px), `--sp-5`, `--sp-6` (32px),
`--sp-5`. The stack is vertically anchored to the **window bottom**, not
centred: as the window grows taller the canopy gains room, the stack does not
drift. Implement with `position: absolute; bottom: 8%` on the stack container
and `align-items: center`.

**Stack container width:** `min(640px, 100% − 2 × frame-margin)`.

---

## 1.2 · Tree placement

```
canvas#tree {
  position: absolute; inset: 0;
  z-index: var(--z-field);
}
```

Full-bleed canvas, never a bounded box, never a card. The tree is drawn in
normalised coordinates and mapped:

- **Trunk base:** `x = 0.5 · W`, `y = 1.06 · H` — deliberately **below the
  bottom edge**, so the trunk is cut off rather than resting on a floor. A tree
  with a visible base becomes an illustration; a tree that continues past the
  frame becomes a presence.
- **Canopy ceiling:** `y = 0.16 · H`.
- **Canopy width:** `0.62 · W`, clamped to a maximum of 900px so it does not
  become a horizon on ultra-wide displays.
- **Devicepixelratio:** capped at 2.

### The veil — how type always wins

A single radial gradient between the tree and the text stack:

```css
.veil {
  position: absolute; inset: 0; z-index: 5; pointer-events: none;
  background: radial-gradient(
    ellipse 70% 40% at 50% 78%,
    rgba(5,7,10,0.82) 0%,
    rgba(5,7,10,0.55) 45%,
    rgba(5,7,10,0.00) 100%);
}
[data-theme="light"] .veil {
  background: radial-gradient(ellipse 70% 40% at 50% 78%,
    rgba(244,242,238,0.88) 0%, rgba(244,242,238,0.60) 45%,
    rgba(244,242,238,0.00) 100%);
}
```

Non-negotiable: **text is never rendered directly over undimmed particles.**

---

## 1.3 · Ambient lighting

One light source, and it is the tree. Nothing else in the product glows.

Two layers behind the tree, both `z-index: 1`:

**Layer A — base field.**
```css
background: radial-gradient(ellipse 120% 90% at 50% 62%,
            #0A1018 0%, var(--c-void) 66%);
```

**Layer B — canopy bloom.** A soft light where canopy density is greatest,
whose opacity is bound to the tree's state (see D2), never to a timer.

```css
.bloom {
  position: absolute; left: 50%; top: 34%;
  width: 56%; aspect-ratio: 1; transform: translate(-50%,-50%);
  background: radial-gradient(circle,
              rgba(127,211,255,0.055) 0%, transparent 70%);
  transition: opacity var(--d-8) var(--e-settle),
              background var(--d-8) var(--e-settle);
}
```

Bloom opacity by state: idle `0.6` · listening `1.0` · thinking `0.85` ·
speaking `1.0` · attention `0.7` (hue shifts to `--s-attend` at 0.045 alpha) ·
celebration `1.0` (hue `--s-bloom` at 0.075 alpha).

Founder Light replaces both layers with a flat `--c-void` and **no bloom** —
paper does not glow. Tree state is carried by particle density and ink weight
instead.

---

## 1.4 · Greeting placement and behaviour

```
font: var(--t-greeting)            /* 40 / 52, weight 300 */
color: var(--c-ink)
text-align: center
max-width: 640px
```

- **One line preferred**, two maximum. If the string would wrap to three lines,
  the runtime supplied too much text — render two lines and truncate at a word
  boundary with no ellipsis. Never shrink the type to fit.
- **Optical alignment:** the greeting is centred on the *ink* bounding box, not
  the glyph box. Measure the first and last glyph's side bearings on the canvas
  and offset by half their difference.
- Entrance is specified in D6 (startup) and D2.8 (return visit).
- **The greeting is supplied by the runtime.** The UI never composes it and
  never substitutes a default. If no greeting has arrived, the slot renders
  nothing and the stack closes the gap — see §1.9.

**Presence line** directly beneath: `var(--t-body)`, `--c-ink-2`, one line, no
wrap. Also runtime-supplied.

---

## 1.5 · Microphone placement — the primary affordance

Voice is primary. The microphone is therefore the largest interactive element on
the screen and sits on the axis.

```
size: 72 × 72
radius: --r-full
border: 1px solid var(--c-hair)
background: var(--c-raise-1)
icon: microphone, 24 × 24, --c-ink-2
```

Concentric ring, drawn as a pseudo-element, is the state carrier:

```css
.mic::after {
  content: ''; position: absolute; inset: -8px;
  border-radius: var(--r-full);
  border: 1px solid transparent;
  transition: border-color var(--d-4) var(--e-settle),
              transform var(--d-4) var(--e-settle);
}
```

| State | Ring | Icon | Size |
|---|---|---|---|
| idle | transparent | `--c-ink-2` | 72 |
| hover | `--c-hair` | `--c-ink` | 72 |
| armed (voice on, not speaking) | `--s-live` @ 35% | `--s-live` | 72 |
| listening | `--s-live` @ 70%, ring scale 1.06 | `--s-live` | 76 |
| muted | `--c-ink-3`, 1px dashed | `microphone-muted`, `--c-ink-3` | 72 |
| denied (no permission) | `--s-attend` @ 50% | `microphone-muted`, `--s-attend` | 72 |

A **label** sits 12px below in `--t-label`, `--c-ink-3`, stating the state in
words: `LISTENING` · `MUTED` · `TAP TO SPEAK` · `MICROPHONE BLOCKED`. Colour is
never the only carrier.

Full behaviour in D3.

---

## 1.6 · Text input placement — always available, never competing

Text is always available. It is not primary, so it is **collapsed by default**
and one gesture from full size.

**Collapsed (default):** a capsule on the axis.
```
width: 320   height: 56   radius: --r-4
border: 1px solid var(--c-hair-soft)
background: var(--glass-dark); backdrop-filter: blur(var(--blur-transient))
content: keyboard icon (20) + "Type instead" in --t-body, --c-ink-3
```

**Expanded:** triggered by click, `Tab` onto it, or **any printable keypress
anywhere on the screen** (the keystroke is captured and becomes the first
character — this is what makes text feel always-available without occupying the
screen).

```
width: min(720px, 100% − 2 × frame-margin)
min-height: 56   max-height: 184 (auto-grow, ~6 rows)
border: 1px solid var(--c-hair)
background: var(--glass-dark)
padding: 16px 20px
```

Transition: width and border-color over `--d-4` `--e-settle`; the placeholder
cross-fades over `--d-2`. The mic **stays visible and stays armed** — voice and
text are simultaneously live (D3.7).

`Enter` submits. `Shift+Enter` newlines. `Escape` collapses if empty, clears if
not. Submitting an empty or whitespace-only value does nothing.

**Footer hint:** `--t-label`, `--c-ink-3`, centred: `SPACE TO SPEAK · TYPE TO
WRITE`. Fades to 0 opacity `--d-3` after the founder's first interaction of the
session and does not return.

---

## 1.7 · Background and window frame

The window has no visible chrome beyond the OS frame. There is no title bar
band, no toolbar, no navigation rail on the home screen.

Two persistent controls only, both at `--c-ink-3`, both 20×20, both fading to
`--c-ink-2` on hover:

- **Top-left, at `--frame-margin`:** the wordmark `KALPAVRIKSHA` in
  `--t-label`. Not a logo, not an icon — the word.
- **Top-right, at `--frame-margin`:** a single `chevron-down` that opens the
  dashboard overlay (D5). Nothing else.

That is the entire chrome. No settings gear on this screen; settings live inside
the dashboard overlay.

---

## 1.8 · Responsive behaviour

Three targets. **The composition never reflows into columns** — it scales.

### Desktop — ≥ 1440 × 900

Reference values above. `--frame-margin: 64px`. Canopy width `0.62·W` capped at
900px. Greeting 40/52. Particle budget 2400.

### Small laptop — 1180 → 1439 wide, or height < 800

`--frame-margin: 48px`. Canopy width `0.70·W`. Particle budget 1800.

Vertical compression, because 1280×720 is the tightest common case:
- Canopy ceiling moves to `12%`.
- Greeting → **34 / 44**.
- Stack gaps tighten one step: 24 → 16, 32 → 24.
- Microphone → **64 × 64**, icon 22.
- Footer hint is removed entirely below 760px height.

### Tablet — 834 → 1179 wide (portrait or landscape)

`--frame-margin: 32px`. Canopy width `0.86·W`. Particle budget 1200.

- Greeting → **30 / 40**, max two lines.
- Microphone → **80 × 80** (touch target), icon 26. Hit area 96×96 including
  padding.
- Composer collapsed width → `min(280px, 70%)`; expanded → `100% − 2 ×
  frame-margin`.
- The keypress-to-expand behaviour is dropped (no physical keyboard assumed);
  tapping the capsule is the only expand gesture.
- Hover states are not rendered; `:active` uses the pressed treatment
  immediately.

### Below 834 wide

**Out of scope for v1.0.** The shell renders the tree, the greeting, and the
microphone only, with the composer as a full-width bottom sheet. Specified as a
graceful floor, not a designed experience.

---

## 1.9 · Empty and degraded states

Every one of these is a designed state. None is an error.

| Condition | Screen shows |
|---|---|
| No greeting supplied yet | Tree at idle. Greeting slot empty, stack closes the gap by 76px. Presence line reads `—`. Mic armed. **No substitute greeting is invented.** |
| No presence data at all | Tree at idle, dimmed one step (bloom 0.4). Presence line reads `no signal` in `--c-ink-3`. Mic still functional. |
| Microphone permission denied | Mic in `denied` state, label `MICROPHONE BLOCKED`. Composer auto-expands and takes focus — text carries the whole interaction. |
| Voice unavailable in this build | Mic hidden entirely. Composer expanded by default. Footer hint reads `TYPE TO WRITE`. |
| Reduced motion | Tree fully grown and still. Bloom static at idle value. No entrance animation; the greeting is present at first paint. |

---

## 1.10 · What is forbidden on this screen

No metrics. No cards. No graphs. No KPI row. No navigation rail. No tabs. No
avatar. No mascot. No assistant icon. No floating chat bubble. No modal. No
notification badge. No onboarding tour. No empty-state illustration.

If an element is neither the tree, Somesh's language, the two input affordances,
the wordmark, nor the single dashboard chevron — **it does not belong here.**
