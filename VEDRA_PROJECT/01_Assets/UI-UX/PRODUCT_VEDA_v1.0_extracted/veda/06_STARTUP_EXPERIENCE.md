# Product Veda · Deliverable 6 — Startup Experience

**Authoritative.** The startup experience is the first impression of the
product. Every detail is intentional. An engineer implementing this must
produce exactly the sequence described, down to the millisecond offsets.

The flow is fixed and non-negotiable:

> **Launch → Splash → Tree slowly grows → Ambient light → Somesh wakes →
> Greeting → Ready**

---

## 6.0 · Governing constraints

1. **The animation timeline and the initialization timeline are independent.**
   Initialization happens behind the animation. The animation never waits on
   initialization; initialization never hurries the animation.
2. **There is never a spinner, a progress bar, a loading state, or a version
   number visible at any point.** The tree growing IS the loading experience.
3. **The window opens already dark.** The exact background colour is painted
   before the first frame. There is no white flash.
4. **The founder never waits on a flourish.** Input is accepted before the
   animation completes.
5. **The UI never invents a greeting.** If no greeting has arrived, the
   greeting slot is empty and the stack closes the gap.
6. **Interruption is honoured.** A keypress or click during startup
   fast-forwards to Ready.
7. **`prefers-reduced-motion` collapses the entire sequence** to a specified
   static composition at a specified time.

---

## 6.1 · Launcher

### 6.1.1 What the founder clicks

The Kalpavriksha application launcher: a desktop app icon (electron shell or
similar native wrapper). Nothing in this document specifies the icon's visual
design; that is a separate deliverable. This document covers what happens after
the process starts.

### 6.1.2 Window creation

| Property | Value |
|---|---|
| Default size | 1440 × 900 px |
| Minimum size | 1180 × 760 px (enforced by the shell; the window cannot be resized below this) |
| Position | Centred on the active display at process start. If the active display is narrower than 1440 or shorter than 900, the window opens at the display's usable area minus 40px on each axis, still centred. |
| Background colour painted before first frame | `#05070A` (the exact hex value of `--c-void` in Founder Dark) |

**Why `#05070A` by literal hex and not a CSS variable:** The background colour
must be written into the native window's background property at the shell/OS
level before the first web frame renders. CSS variables are not available at
that point. Hardcode `#05070A`. If the theme is Founder Light (a future
feature), this value must be updated to `#F4F2EE`.

**The result:** the founder clicks the icon, the window appears, and it is
already `#05070A`. There is no white flash, no grey flash, no OS default
background. The first thing the founder sees is darkness.

### 6.1.3 Shell-level settings

```
titleBarStyle: hidden (or equivalent for the target shell)
backgroundColor: '#05070A'
minWidth: 1180
minHeight: 760
width: 1440
height: 900
center: true
show: false   // window is NOT shown until first paint is ready
```

The `show: false` / `ready-to-show` pattern: the window is created hidden,
the renderer paints one frame (the dark background + the splash composition
described in §6.2), and only then is the window shown. This eliminates the
window-creation flash at the OS level.

---

## 6.2 · Splash

### 6.2.1 What the splash is

The splash is the dark background plus the wordmark, nothing else. It is the
starting composition before the tree begins growing.

**Splash composition (visible at t = 0 ms):**

| Element | Position | Style |
|---|---|---|
| Background | Full window fill | `--c-void` (`#05070A`) |
| Wordmark `KALPAVRIKSHA` | Top-left, `--frame-margin` (64px) from top and left edges | `--t-label`, `--c-ink-3`, opacity `0.0` at t = 0, transitions to `1.0` — see timeline |
| All other UI elements | Not rendered, not in DOM | — |

### 6.2.2 What the splash is NOT

- No product logo animation.
- No spinner or activity indicator of any kind.
- No progress bar, no percentage, no "Loading…" text.
- No version number.
- No tagline.
- No founder's name.
- No fade-in of the application chrome.

The wordmark is the only element because the wordmark is a word, and words do
not require animation to be meaningful. Its opacity transition is gentle, not
theatrical.

---

## 6.3 · Initialization (behind the animation)

Initialization covers everything the application must do before it can enter
the Ready state: loading the founder's session, connecting to the runtime,
hydrating local state, building the tree geometry.

**The animation timeline does not wait for initialization.** The tree begins
growing at its scheduled time regardless of whether initialization is complete.

### 6.3.1 Hold-point

The one point at which initialization may affect the animation is the
**greeting hold-point**: the moment in the startup timeline when the greeting
and presence line are due to appear (t = 3600 ms). If initialization has not
yet delivered a greeting by t = 3600 ms:

- The tree continues in its post-growth Idle breathe.
- The greeting slot is empty; the stack closes the gap.
- No spinner, no placeholder text, no "—" dash, no ellipsis.
- When the greeting arrives (any time after t = 3600 ms), it enters via the
  greeting entrance animation specified in `02_ANIMATION_SYSTEM §2.5.2`
  (`translateY(8px)` → `translateY(0)`, opacity 0 → 1, over `--d-7`,
  `--e-settle`).

The tree never stalls. There is no "waiting for greeting" state. The
post-growth Idle breathe is the entire experience if the greeting is slow.

### 6.3.2 Early completion

If initialization completes before the animation timeline reaches its end
(Ready at t ≈ 4200 ms), **the sequence does not skip ahead**. The animation
plays at its defined pace. Initialization completing early means the greeting
will be available when t = 3600 ms arrives; it does not accelerate the
timeline.

### 6.3.3 Late completion (beyond t = 4200 ms)

If initialization has not completed by t = 4200 ms (the nominal Ready time):
- The UI enters the Ready state as defined in §6.7 — the founder can type or
  speak.
- The founder's input is buffered.
- When initialization completes, the buffered input is processed.
- The tree stays at Idle throughout. There is no visual indication that
  initialization is still running.

This is the correct behaviour because the founder's time is more valuable than
correct sequencing. The buffering must be invisible.

---

## 6.4 · Master startup timeline

All times are milliseconds from process start (t = 0 when the process
launches).

The target total time to Ready is **4200 ms**. This is a target, not a
guarantee. The animation plays at its defined pace regardless.

### 6.4.1 Cold start timeline

| t (ms) | Phase | On screen | What is animating | Token governing transition |
|---|---|---|---|---|
| 0 | Window appears | `#05070A` background only | Nothing | — |
| 0 – 80 | First paint | Background `--c-void`; wordmark at opacity 0 | Wordmark opacity 0 → 1 | `--d-3` `--e-settle` |
| 80 – 400 | Wordmark settles | Wordmark at opacity 1 | Nothing | — |
| 400 | Tree canvas mounted | Canvas added to DOM; tree geometry pre-built off-screen | Nothing visible yet | — |
| 400 – 600 | Background layer enters | Layer A (base field radial gradient) fades in | Layer A opacity 0 → 1 | `--d-3` `--e-settle` |
| 600 | Particle seeding begins | First particles appear at trunk base at opacity 0 | Particle alpha 0 → base | `--d-4` `--e-settle` |
| 600 – 4600 | Tree growth (§6.5) | Particles rise generation by generation; filaments emerge | Full growth sequence | `--d-10` (4000 ms) total budget |
| 1200 | Canopy bloom layer enters | `.bloom` fades in at `opacity 0` → `0.25` | Bloom opacity | `--d-6` `--e-settle` |
| 2400 | Bloom reaches Idle opacity | Bloom transitions from `0.25` → `0.60` (Idle value) | Bloom opacity | `--d-8` `--e-settle` |
| 3400 | Input affordances appear | Microphone button + composer capsule fade in | Both: `opacity 0 → 1, translateY(12px) → translateY(0)` | `--d-5` `--e-settle` |
| 3600 | Greeting hold-point | If greeting available: greeting + presence line fade in | Greeting: `--d-7` `--e-settle`; `translateY(8px) → 0` | `--d-7` `--e-settle` |
| 3600 | Footer hint appears | Footer hint text | `opacity 0 → 1` | `--d-3` `--e-settle` |
| 4200 | **Ready** | Full composition visible; all UI interactive | Tree in Idle breathe | — |

### 6.4.2 When the runtime is faster than the animation

The animation plays at its defined pace. Nothing skips. The tree does not
grow faster because initialization is done. The timeline is fixed.

### 6.4.3 When the runtime is slower than the animation

The animation plays at its defined pace to the greeting hold-point (t = 3600
ms). If initialization is not complete, the greeting slot is empty (§6.3.1).
The UI enters Ready at t = 4200 ms regardless.

---

## 6.5 · Tree awakening — the growth animation

### 6.5.1 Overview

The tree grows from trunk to canopy, generation by generation. It does not
assemble as a whole — the trunk appears first, then primaries, then
secondaries, and so on, each generation arriving slightly after the previous.
Particles rise from the ground up, converging on their rest positions as they
arrive.

The entire growth is governed by the `--d-10` token (4000 ms). This budget
runs from t = 600 ms to t = 4600 ms, but the nominal Ready state is
reached at t = 4200 ms. The final 400 ms (t = 4200 – 4600 ms) are the
settling phase — the canopy finishes its last small movements while the UI is
already interactive.

### 6.5.2 Particle entry mechanics

Each particle has a defined rest position (baked at tree-build time,
§2.1.3). During growth, each particle starts at a displaced origin position
and travels to its rest position.

**Origin position.** A particle on generation `g` starts at:
- `x = restX + seededJitter(−0.04, +0.04)` normalised units
- `y = −0.15` (below the canvas, invisible at start)

The starting y position is always below the canvas bottom (y < 0 in normalised
space maps to below `1.06 × H` in canvas space, which is already off the
bottom edge). Particles rise into view as they approach their rest positions.

**Travel.** Each particle travels from its origin to its rest position over its
individual entry duration. The travel uses `--e-settle` easing.

**Entry is not instantaneous.** A particle's entry is a motion over
`entryDuration(g)`. Particles in the same generation do not all enter
simultaneously — they stagger within their generation's window (see §6.5.3).

### 6.5.3 Per-generation timing

Times are offsets from the growth start (t = 600 ms in the master timeline).
"Window start" is when the first particle of that generation begins moving.
"Window end" is when the last particle of that generation completes its
travel.

| Generation | Window start (ms from growth start) | Window end (ms from growth start) | Entry duration per particle | Stagger within window |
|---|---|---|---|---|
| 0 (trunk) | 0 | 500 | 480 ms | None — trunk appears as a single entity |
| 1 (primary) | 300 | 900 | 560 ms | Uniform random within window, seeded |
| 2 (secondary) | 700 | 1500 | 620 ms | Uniform random within window, seeded |
| 3 (tertiary) | 1100 | 2100 | 660 ms | Uniform random within window, seeded |
| 4 (quaternary) | 1600 | 2800 | 700 ms | Uniform random within window, seeded |
| 5 (canopy tips) | 2200 | 3800 | 720 ms | Uniform random within window, seeded |

**Stagger.** Within each generation's window, each particle's start offset is
drawn from `seededRandom() × (windowEnd − windowStart − entryDuration)`. This
means every particle starts somewhere in the window such that it completes
within the window end. The seeded random ensures the stagger is identical for
the same founder.

**Filament entry.** Filaments between two particles become visible when
both particles have completed at least 60% of their travel. Before that, a
filament's alpha is 0.

### 6.5.4 Why generation-by-generation, not all-at-once

The tree's identity is established by its structure, not by a flash of light.
Growing from trunk to canopy mirrors how a real tree grows and how the founder
will eventually learn to read the tree's state: trunk first (the ground, the
identity), then branches (the reach), then canopy (the presence). All-at-once
particle materialisation would look like an explosion, not a growth.

### 6.5.5 Growth during `prefers-reduced-motion`

The growth animation does not play. The tree is fully grown and static from
the first frame after the canvas mounts (t = 400 ms). All particles are at
their rest positions, filaments at their computed alphas, bloom at Idle opacity.
No transitions. The greeting and UI affordances appear at t = 800 ms
(a single `--d-3` opacity fade). Ready at t = 800 ms.

---

## 6.6 · Greeting arrival and the hard rule

### 6.6.1 The hard rule

> **The UI never invents a greeting.** If the runtime has not delivered a
> greeting string by the time the greeting slot is due (t = 3600 ms), the slot
> renders nothing.

This is not a fallback — it is the designed behaviour. A missing greeting
means the tree is present but silent, which is honest. A invented greeting
(e.g. "Good morning, founder") would be dishonest — the system does not know
what Somesh would say.

### 6.6.2 Greeting arrival before t = 3600 ms

The greeting string is held in memory and applied at t = 3600 ms. It does not
appear early even if it arrives at t = 1000 ms.

### 6.6.3 Greeting arrival after t = 3600 ms

The greeting appears as soon as it arrives, via the greeting entrance animation
(`02_ANIMATION_SYSTEM §2.5.2`): `translateY(8px) → translateY(0)`,
`opacity 0 → 1`, `--d-7` `--e-settle`. The stack gap that existed when the
slot was empty closes simultaneously (the stack container height animates from
`gap-closed` to `gap-open` over `--d-5` `--e-settle`).

### 6.6.4 Ready state with no greeting

If the founder reaches Ready (t = 4200 ms) and no greeting has arrived:
- The greeting slot is empty.
- The vertical stack contracts by the greeting slot height (52 px for one line
  + 24 px gap = 76 px total, per `01_FOUNDER_SURFACE §1.9`).
- The presence line reads `—` in `--c-ink-3`.
- The microphone is armed and functional.
- The composer is collapsed and functional.
- **This is a complete, usable state.** The founder can speak or type. There is
  no visual indication that a greeting was expected.

---

## 6.7 · Ready state — definition and interactivity

### 6.7.1 Definition of Ready

Ready means:
1. The tree canvas is rendering at its Idle breathe parameters.
2. The microphone button is armed and responsive to interaction.
3. The composer capsule is present and responsive to click, Tab, or keypress.
4. The tree's particle system has completed at least generation-3 growth
   (canopy tips may still be settling — this is acceptable).

**Input is accepted before the animation completes.** The founder must never
wait for the canopy to finish settling before they can speak or type. The
Ready state is declared at t = 4200 ms regardless of whether generation-4 or
generation-5 particles have settled.

### 6.7.2 What becomes interactive and when

| Element | Interactive at | Note |
|---|---|---|
| Microphone button | t = 3400 ms | When it first becomes visible. The tree transitions to Listening if activated. |
| Composer capsule | t = 3400 ms | When it first becomes visible. Keypress-to-expand is active. |
| Dashboard chevron | t = 3400 ms | Top-right chevron. The overlay opens over the still-settling tree. |
| Wordmark | t = 80 ms | Visible but has no interactive function at startup. |
| Footer hint | t = 3600 ms | Read-only; not interactive. |

### 6.7.3 Fast-forward on interruption

If the founder presses any printable key or clicks anywhere on the screen
during the startup sequence (before t = 4200 ms):

1. All ongoing animations are immediately driven to their end states.
2. The tree is placed at its full Idle parameters.
3. All UI affordances are made visible instantly (opacity 1, no transform).
4. The greeting appears if it has arrived; the slot is empty if it has not.
5. The entire transition to this end state takes **240 ms** (`--d-3` opacity on
   everything, no transforms).
6. The system enters Ready immediately.
7. If the interrupting input was a printable keypress, it is captured as the
   first character in the composer, which auto-expands.

The 240 ms fast-forward is not a collapse — it is a graceful snap. The founder
sees the tree settle quickly rather than jumping from mid-growth to full.

---

## 6.8 · Cold start vs. warm start vs. return within session

### 6.8.1 Cold start

The full sequence from §6.4.1. All animations play. Tree grows from nothing.
Target Ready: t = 4200 ms.

Cold start is defined as: process is not running, or process was last active
more than 4 hours ago.

### 6.8.2 Warm start

Process is running and was last active between 30 seconds and 4 hours ago
(the window was minimised, hidden, or the display slept).

| Phase | Behaviour |
|---|---|
| Window show | Window appears at `--c-void`; no white flash |
| t = 0 | Tree already at Idle (the tree was paused per `02_ANIMATION_SYSTEM §2.4` pause rule; it resumes |
| t = 0 – 300 | Bloom opacity 0 → Idle value (0.60) over `--d-5` `--e-settle` |
| t = 0 – 300 | UI elements fade in: all at `opacity 0 → 1`, `translateY(8px) → 0` over `--d-5` `--e-settle` |
| t = 300 | **Ready** |

No growth animation. No wordmark re-entrance. The tree is present immediately.
The greeting is the greeting that was already displayed before the window was
hidden — it does not re-animate unless it has changed.

If the greeting has changed since the window was last shown, the new greeting
enters via the greeting entrance animation (`--d-7` `--e-settle`) at t = 0.

### 6.8.3 Return within session

The founder navigated away from the home screen (to the dashboard overlay or a
conversation panel) and has returned. This is not a startup — it is a
navigation return.

| Phase | Behaviour |
|---|---|
| Immediately | The tree is already running (it never stops while the app is focused) |
| The overlay exits | Overlay dismisses per `02_ANIMATION_SYSTEM §2.5.5` (`--d-6` `--e-exit`) |
| Home screen reveals | The home screen content (greeting, mic, composer, footer hint) fades in at `opacity 0 → 1` over `--d-5` `--e-settle` as the overlay departs |
| No animation | No tree growth, no bloom entrance, no wordmark. The tree was there the whole time. |
| **Ready** | Immediate — the screen is already in the Ready state; the navigation just removed the overlay |

The footer hint does not return if the founder has already interacted once this
session (per `01_FOUNDER_SURFACE §1.6`).

---

## 6.9 · Reduced motion — the complete alternate sequence

When `window.matchMedia('(prefers-reduced-motion: reduce)').matches`:

| t (ms) | What happens |
|---|---|
| 0 | Window appears at `--c-void` |
| 0 – 240 | Wordmark `opacity 0 → 1` (only opacity; no transform). Duration `--d-3`. |
| 400 | Tree canvas mounts; tree fully grown and static at first paint. No growth animation. Particles at rest positions, filaments at computed alphas, bloom at Idle opacity 0.60. |
| 400 – 640 | Bloom `opacity 0 → 0.60` over `--d-3`. Bloom does not animate its colour; it is the Idle `--s-live` hue from the start. |
| 640 | UI affordances appear: mic + composer + footer hint, all at `opacity 1` immediately (no transition). |
| 640 | Greeting appears at `opacity 1` immediately if available. No entrance animation. |
| 640 | **Ready** |

Total time to Ready in reduced-motion: **640 ms**.

**Static composition at Ready (reduced-motion):** tree fully grown, particles
static, bloom static at 0.60, all UI affordances present. This is a
first-class designed state — it must look intentional, not broken. The
tree at full particle density and filament visibility is beautiful without
motion.

**State changes in reduced-motion.** After Ready, tree state changes are
carried by bloom colour transitions only (`--d-1` `--e-settle` on bloom opacity
and a direct colour property change — no interpolation, per
`00_TOKENS §10.10`). Particles do not change colour. No breathe.

---

## TOKEN ADDITION REQUEST

No new tokens are required. All durations, easings, colours, and spacing
values in this document are drawn from `00_TOKENS.md`.

The following uses deserve explicit confirmation for the implementing engineer:

- `--d-10` (4000 ms) is explicitly designated for startup growth in
  `00_TOKENS.md`. This is its one and only use.
- `--d-3` (240 ms) is used for the fast-forward snap duration. This is an
  intentional re-use of the fade-in token — the snap is an opacity-only
  transition, which is exactly what `--d-3` is specified for.
- The warm-start Ready time of 300 ms uses `--d-5` (420 ms for the
  individual elements). The 300 ms figure is the point at which the UI is
  functionally ready; the `--d-5` transitions may still be completing
  (they will complete at 420 ms). This is intentional — the affordances
  are interactive from 300 ms even while fading in.
