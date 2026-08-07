# Product Veda · Deliverable 5 — Dashboard Behaviour

**SCOPE CONSTRAINT — READ BEFORE TOUCHING ANYTHING.**
This document specifies ONLY the appearance, disappearance, geometry, timing,
focus, and voice behaviour of the dashboard overlay. The dashboard's content —
its sections, data, controls, actions — is out of scope here entirely. Nothing
below redesigns, adds, removes, or reorders any dashboard feature.

Two engineers who read only this file must independently produce overlay
behaviour that is pixel-identical. Every dimension is a token or a concrete
pixel value. No approximations.

---

## 5.1 · Trigger — how the dashboard opens

Two and only two triggers open the dashboard. No other gesture, click, or swipe
may open it.

### 5.1.1 · Chevron (pointer)

The `chevron-down` icon in the top-right corner of the Founder Surface
(01_FOUNDER_SURFACE §1.7) is the canonical pointer trigger. A single click or
tap opens the overlay. The chevron rotates 180° on open (it now points up) and
returns on close.

```css
.chevron-control {
  transition:
    transform var(--d-4) var(--e-settle),
    color     var(--d-1) var(--e-settle);
}
.chevron-control[aria-expanded="true"] {
  transform: rotate(180deg);
}
```

### 5.1.2 · Keyboard shortcut

`Cmd+D` (macOS) / `Ctrl+D` (Windows/Linux) toggles the dashboard.

- The shortcut fires only when the overlay is not actively animating
  (i.e., only in `closed` or `open` states — see §5.7).
- The shortcut does not fire if a modal-equivalent sheet from a different
  system layer is focused. Because this product has no modals (00_TOKENS §10.6),
  this case is restricted to OS-level focus shifts.
- Binding is registered on the app shell and never consumes the keystroke in a
  text input that currently has focus. If the text composer is focused and the
  founder presses `Cmd+D` / `Ctrl+D`, the default browser behaviour is
  suppressed and the dashboard opens; the text input is blurred first.

No other keyboard shortcut opens or closes the dashboard. `?` or help menus
must not list an alternative shortcut.

---

## 5.2 · Overlay geometry — the sheet rises from the bottom

**Choice: the dashboard is a bottom sheet.**

Justification: the tree rises from the bottom edge; language emerges from the
trunk. A bottom sheet honours that directionality — content arrives from where
the tree lives. A right-side panel would compete with the tree's canopy as a
second focal point. A centre-expand animation has no directional logic in this
composition. One direction: up from the bottom.

### 5.2.1 · Sheet anatomy

```
┌────────────────────────────────────────┐
│  Founder Surface (tree visible behind) │
│                                        │
│  ──────────────────────────────────── ← drag handle / header
│  Dashboard content (scrollable)        │
│  ……                                    │
└────────────────────────────────────────┘
```

- The sheet sits at `z-index: var(--z-transient)` (value `30`).
- It does NOT cover the entire viewport. The tree must remain visible above it.
- The sheet has `border-radius: var(--r-3) var(--r-3) 0 0` (14px top corners,
  flush bottom).
- Background: `var(--glass-dark)` (dark theme) / `var(--glass-light)` (light
  theme), both `rgba` at `0.88` opacity. `backdrop-filter: blur(var(--blur-transient))`.

### 5.2.2 · Dimensions at each breakpoint

Heights are the sheet's rendered height when fully open. The sheet slides
**up** from `y = 100vh` to its open position.

#### Desktop — ≥ 1440 × 900

```
sheet height:  560px
sheet width:   100vw
bottom:        0
top offset:    calc(100vh − 560px)   /* = ~340px of tree visible above */
```

The tree is visible in the top `calc(100vh − 560px)` of the window — at the
reference 900px height, that is **340px**, which includes the canopy top,
mid-canopy, and a portion of the veil zone. The tree is never fully obscured.

#### Small laptop — 1180 → 1439 wide, or height < 800

```
sheet height:  480px
sheet width:   100vw
bottom:        0
top offset:    calc(100vh − 480px)
```

At 720px height, 240px of tree is visible above the sheet — the canopy remains
in frame.

#### Tablet — 834 → 1179 wide

```
sheet height:  72vh    /* capped at 600px */
sheet width:   100vw
bottom:        0
```

`72vh` ensures the sheet never exceeds 600px and the tree is always ≥ 28vh
tall above the sheet.

### 5.2.3 · Maximum fraction rule

**The dashboard may never occupy more than 65% of the viewport height.**

```css
.dashboard-sheet {
  max-height: 65vh;
}
```

This is a hard constraint, not a guideline. If content inside the dashboard
grows beyond this, the sheet scrolls internally (§5.5). The sheet height must
never grow to push the tree out of view.

At the reference 900px, 65vh = 585px. The desktop spec of 560px satisfies this.
The small-laptop spec of 480px satisfies this. The tablet spec of `72vh capped
at 600px` — at viewport heights ≥ 924px the cap applies; below that `72vh` is
≤ 65vh only at 903px and below. **Correction: tablet cap is `min(72vh, 65vh)`
= `65vh`.** Implement as:

```css
@media (min-width: 834px) and (max-width: 1179px) {
  .dashboard-sheet { height: 65vh; max-height: 600px; }
}
```

---

## 5.3 · Backdrop — tree remains present

The backdrop sits between the tree canvas and the sheet:

```css
.dashboard-backdrop {
  position: fixed; inset: 0;
  z-index: calc(var(--z-transient) − 1);   /* = 29 */
  background: rgba(5, 7, 10, 0.28);         /* Founder Dark */
  backdrop-filter: blur(var(--blur-transient));
  pointer-events: auto;                     /* click-outside to close */
}
[data-theme="light"] .dashboard-backdrop {
  background: rgba(244, 242, 238, 0.20);
}
```

**Tree dimming: 28% dark overlay at dark theme; 20% light wash at light theme.**

The tree canvas `opacity` is NOT changed. The overlay achieves dimming via the
backdrop fill colour only. This preserves the tree's animation state and means
it never needs to be restored.

The tree must remain clearly visible through the backdrop — the founder must
always be aware the tree is there. The 28% dim is the maximum; engineers must
not increase this value.

**Blur applies to what is behind the backdrop.** The tree becomes softly blurred
(`--blur-transient` = 14px) AND slightly darkened. The sheet itself is not
blurred relative to the backdrop — it sits above it.

---

## 5.4 · Transition timing — enter and exit are different

This is intentional. Entries are deliberate; exits are immediate. An exit that
matches the entry speed makes the product feel sluggish when the founder
dismisses the dashboard.

### 5.4.1 · Opening (closed → open)

```css
/* Sheet: slides up from below the viewport */
.dashboard-sheet {
  transform: translateY(100%);
  transition:
    transform var(--d-7) var(--e-settle);   /* 900ms, settle */
}
.dashboard-sheet.is-open {
  transform: translateY(0);
}

/* Backdrop: fades in */
.dashboard-backdrop {
  opacity: 0;
  transition: opacity var(--d-6) var(--e-settle);   /* 600ms, settle */
}
.dashboard-backdrop.is-open {
  opacity: 1;
}
```

Total enter duration: `--d-7` (900ms). The backdrop begins simultaneously and
resolves first (600ms), so the tree is already dimmed before the sheet finishes
arriving.

### 5.4.2 · Closing (open → closed)

```css
.dashboard-sheet.is-closing {
  transform: translateY(100%);
  transition:
    transform var(--d-5) var(--e-exit);   /* 420ms, exit easing */
}

.dashboard-backdrop.is-closing {
  opacity: 0;
  transition: opacity var(--d-4) var(--e-exit);   /* 320ms, exit easing */
}
```

Total exit duration: `--d-5` (420ms). The backdrop fades faster (320ms) so the
tree snaps back to clarity before the sheet fully disappears — the tree
reasserts itself.

**Exit is 420ms vs entry 900ms — more than 2× faster.** This is correct.

### 5.4.3 · Reduced motion

```css
@media (prefers-reduced-motion: reduce) {
  .dashboard-sheet,
  .dashboard-backdrop {
    transition: opacity var(--d-1) var(--e-settle) !important;
    transform: none !important;
  }
}
```

Under reduced motion: the sheet appears/disappears by opacity only in 120ms.
No translateY animates.

---

## 5.5 · Scroll containment

The dashboard sheet is an independent scroll container. Content inside it
scrolls; the rest of the application does not.

```css
.dashboard-sheet {
  overflow-y: auto;
  overscroll-behavior: contain;
  -webkit-overflow-scrolling: touch;
}
```

- The window behind the sheet does NOT scroll when the founder scrolls inside
  the sheet.
- The tree does NOT move.
- Scroll position inside the sheet is reset to `0` each time it opens.

**Does scroll dismiss the sheet?** No. Scrolling the sheet's content does not
close it. The only dismissal gestures are listed in §5.6. This is intentional:
the founder may need to scroll deeply in the dashboard, and an accidental
dismiss-on-scroll would be disruptive.

---

## 5.6 · Dismissal — how the dashboard closes

Four and only four mechanisms close the dashboard:

| Mechanism | Notes |
|---|---|
| Chevron click/tap (now pointing up) | Primary pointer dismiss |
| `Cmd+D` / `Ctrl+D` keyboard shortcut | Same shortcut that opens |
| `Escape` key | Always dismisses, any focused element inside the sheet |
| Click or tap on the backdrop | Pointer hits `.dashboard-backdrop`; a tap that begins and ends on the backdrop dismisses. A tap that begins on the backdrop and ends on the sheet does not dismiss. |

**Scroll does not dismiss.** Stated explicitly because engineers may reach for
scroll-dismiss patterns from mobile sheet libraries. Do not implement it.

**Swipe-down does not dismiss on desktop or laptop.** On tablet, a swipe-down
gesture on the drag handle (a 48×24px touch target at the top of the sheet)
dismisses with the same exit transition as `Escape`. The drag handle is:

```css
.dashboard-sheet__handle {
  width: 36px; height: 4px;
  border-radius: var(--r-full);
  background: var(--c-hair);
  margin: 12px auto 0;
  cursor: pointer;   /* tablet only */
}
```

---

## 5.7 · State table

| State | Dashboard sheet | Backdrop | Tree | Interaction |
|---|---|---|---|---|
| `closed` | `display: none` after exit transition, `transform: translateY(100%)` | `display: none`, `opacity: 0` | Full opacity, animating normally | All Founder Surface interactions active. Dashboard is inert. |
| `opening` | Entering, `translateY` animating toward `0` | `opacity` animating toward `1` | Dimming behind backdrop (no change to canvas opacity) | Founder Surface interactions blocked. Chevron is inert. Keyboard shortcut is inert. Only `Escape` may cancel (fires close immediately). |
| `open` | `transform: translateY(0)`, fully visible | `opacity: 1` | Visible behind backdrop, dimmed `0.28` | All dashboard content is interactive. Backdrop click dismisses. `Escape` dismisses. Chevron dismisses. Founder Surface controls below backdrop are inert (pointer-events blocked by backdrop). |
| `closing` | Exiting, `translateY` animating toward `100%` | `opacity` animating toward `0` | Brightening (backdrop fading) | All interactions inert during exit. Attempting to open during a close: if the exit has passed 50% (≥ 210ms), the open is queued and fires on `transitionend`. Before 50%, the animation reverses. |

---

## 5.8 · Focus management

### 5.8.1 · On open

When the dashboard enters the `open` state (the sheet's `transitionend` fires):

1. Focus moves to the sheet's first focusable element. This is determined by
   DOM order inside `.dashboard-sheet`. The shell does not hard-code a specific
   element — it queries `querySelectorAll` for focusable candidates and takes
   `[0]`.
2. If the sheet has no focusable elements (empty or loading state), focus moves
   to the sheet container itself, which must have `tabindex="-1"`.
3. Focus is **trapped** inside the sheet while it is open. Tab cycles within;
   `Shift+Tab` cycles backward. Focus must not escape to the dimmed Founder
   Surface behind the backdrop.

```js
// Focus trap — schematic (use a proven library such as focus-trap or tabbable)
const focusableSelectors = [
  'a[href]', 'button:not([disabled])',
  'input:not([disabled])', 'select:not([disabled])',
  'textarea:not([disabled])', '[tabindex]:not([tabindex="-1"])'
].join(', ');
```

### 5.8.2 · On close

When the dashboard's exit transition completes (`transitionend` on
`.dashboard-sheet`):

1. Focus returns to the element that was focused **before the dashboard opened**.
   This element reference is captured at the moment the open trigger fires and
   stored in a variable. It is not assumed to be the chevron.
2. If that element no longer exists in the DOM, focus falls back to the chevron
   control.
3. Focus trap is released before the return-focus call.

### 5.8.3 · `Escape` behaviour in nested contexts

If a focusable element inside the sheet has its own `Escape` handler (e.g., a
text input clearing its value), that handler fires first. The sheet's `Escape`
handler fires only if the event is not `.stopPropagation()`-ed by an inner
element. Engineers must ensure inner elements consume `Escape` only when they
have state to clear — an empty input must not consume `Escape`.

---

## 5.9 · Voice during dashboard open

**The microphone stays armed while the dashboard is open.**

Justification: voice is primary (Product Truth §3). The dashboard is a
secondary surface (Product Truth §4). Closing the mic whenever a secondary
surface appears would subordinate voice to the dashboard, which inverts the
product's priority. The founder may ask Somesh a question while reviewing the
dashboard — this must work without any extra step.

Specific rules:

| Condition | Behaviour |
|---|---|
| Dashboard opens while mic is `idle` | Mic remains `idle`. Its ring is visible above the backdrop only if the mic button is in the visible tree zone. It is still armed — a `SPACE` keypress still triggers listening (unless focus is in a text input). |
| Dashboard opens while mic is `listening` | Listening continues uninterrupted. The waveform continues. The sheet animates in over the tree; the tree's waveform state is visible in the portion of tree showing above the sheet. |
| Dashboard opens while mic is `speaking` (Somesh is responding) | Speaking continues. The sheet appears; Somesh's voice does not pause. |
| Founder submits voice input while dashboard is open | The dashboard does not auto-close on voice submission. Closing must be an explicit act. |
| Founder submits text input while dashboard is open | Same rule — the dashboard stays open. |

The mic button itself (on the Founder Surface, below the sheet) is pointer-
inert while the sheet is open because the backdrop covers it. The keyboard
trigger (`SPACE`) remains functional as long as focus is not inside a text
input.

---

## 5.10 · What the dashboard is not permitted to do

These are hard engineering constraints, not style preferences:

- The dashboard must never grow to `height > 65vh`.
- The dashboard must never cause `overflow: scroll` on `<body>` or `<html>`.
- The dashboard must never replace or obscure the tree canvas — the tree canvas
  `display` or `visibility` must not be set by any dashboard state.
- The dashboard must never trigger a network request that delays its visual
  opening. Data loads are independent of the overlay animation.
- The dashboard must never render at `z-index` above `var(--z-transient)` (30).
  There is no higher plane.
- The dashboard must never spawn a child modal, dialog, or alert. Confirmation
  flows inside the dashboard use in-sheet inline states, not overlays.
