# Product Veda · Deliverable 3 — Voice Experience

**Authoritative.** Extends `01_FOUNDER_SURFACE §1.5`. All tokens from
`00_TOKENS.md`. Every state in every matrix is a designed state — none is a
fallback or a placeholder. Two independent engineers reading this document must
build the same thing.

---

## 3.0 · Design intent, stated once

The microphone is not a record button. It is a presence indicator — it shows
whether Somesh can hear the founder right now. States map to what the system
*is doing*, not to what the founder should do next. Copy is accordingly calm and
declarative, never instructional.

Voice and text are simultaneously live at all times the runtime permits. No
state may disable text input.

---

## 3.1 · Microphone state matrix

The mic button is `72 × 72` on desktop, `64 × 64` on small laptop, `80 × 80`
on tablet. `border-radius: var(--r-full)`. All sizes below are at the desktop
reference; adjust proportionally per `01_FOUNDER_SURFACE §1.8`.

The concentric ring is a `::after` pseudo-element: `inset: −8px` from the
button edge, `border-radius: var(--r-full)`, `border: 1.5px solid`. The button
background is always `var(--c-raise-1)` unless specified otherwise. The button
border is always `1px solid var(--c-hair)` unless specified otherwise.

The **label** is 12px below the button, `--t-label` (11px / 16px, weight 500,
tracking 0.14em, uppercase), colour specified per state. Colour is never the
only carrier — the label text must be present and distinct even in greyscale.

Transition between any two states: `--d-4` (320ms) `--e-settle` for ring
colour, ring scale, icon swap, and button background; `--d-2` (180ms)
`--e-settle` for label text and label colour.

Icon is always `20 × 20`, `currentColor`, `stroke-width: 1.5`.

### Full state matrix

| State | Ring border-color | Ring scale | Button background | Icon | Icon colour | Label text | Label colour |
|---|---|---|---|---|---|---|---|
| `idle` | `transparent` | 1.0 | `var(--c-raise-1)` | `microphone` | `var(--c-ink-2)` | `TAP TO SPEAK` | `var(--c-ink-3)` |
| `armed` | `color-mix(in srgb, var(--s-live) 35%, transparent)` | 1.0 | `var(--c-raise-1)` | `microphone` | `var(--s-live)` | `LISTENING` | `var(--c-ink-2)` |
| `listening` | `color-mix(in srgb, var(--s-live) 70%, transparent)` | 1.06 | `var(--c-raise-2)` | `microphone` | `var(--s-live)` | `LISTENING` | `var(--s-live)` |
| `capturing-speech` | `color-mix(in srgb, var(--s-live) 90%, transparent)` | 1.10 | `var(--c-raise-2)` | `microphone` | `var(--s-live)` | `CAPTURING` | `var(--s-live)` |
| `processing` | `color-mix(in srgb, var(--s-live) 50%, transparent)` | 1.0 | `var(--c-raise-1)` | `microphone` | `var(--s-live)` | `PROCESSING` | `var(--c-ink-2)` |
| `muted` | `var(--c-ink-3)` (1px dashed, not solid) | 1.0 | `var(--c-raise-1)` | `microphone-muted` | `var(--c-ink-3)` | `MUTED` | `var(--c-ink-3)` |
| `denied` | `color-mix(in srgb, var(--s-attend) 50%, transparent)` | 1.0 | `var(--c-raise-1)` | `microphone-muted` | `var(--s-attend)` | `MICROPHONE BLOCKED` | `var(--s-attend)` |
| `unavailable` | `var(--c-hair-soft)` | 1.0 | `var(--c-raise-1)` | `microphone-muted` | `var(--c-ink-4)` | `NO MICROPHONE` | `var(--c-ink-4)` |
| `error` | `color-mix(in srgb, var(--s-risk) 45%, transparent)` | 1.0 | `var(--c-raise-1)` | `microphone-muted` | `var(--s-risk)` | `VOICE UNAVAILABLE` | `var(--s-risk)` |

**Why `capturing-speech` and `listening` are distinct:** `listening` means the
mic window is open and Somesh is waiting. `capturing-speech` means the VAD has
confirmed speech onset — this is when the waveform animates and the ring scales
up further. The transition between them must happen within 200ms of speech
onset.

**Why `processing` ring scale returns to 1.0:** the founder has finished
speaking; the ring returning to still signals "received". Lingering at 1.10
would imply ongoing capture.

**Why `idle` and `armed` both have transparent rings but differ in icon
colour:** on a cold start before session initialisation, the mic is truly idle
and no voice session is active. Once the session is live but no utterance is in
flight, the state is `armed`. The icon shifting to `--s-live` is the signal.
Label text differs: `TAP TO SPEAK` vs `LISTENING`. The label ensures greyscale
readers see the distinction.

### State transition table

| From | Event | To | Notes |
|---|---|---|---|
| `idle` | Session initialises | `armed` | `--d-4` `--e-settle` |
| `armed` | VAD: activity detected | `listening` | `--d-2` `--e-settle` — fast |
| `listening` | VAD: speech confirmed | `capturing-speech` | `--d-2` `--e-settle` |
| `capturing-speech` | VAD: speech ended | `processing` | `--d-4` `--e-settle` |
| `processing` | Runtime: result delivered | `armed` | `--d-4` `--e-settle` |
| `armed` | Founder clicks mic | `muted` | `--d-4` `--e-settle` |
| `muted` | Founder clicks mic | `armed` | `--d-4` `--e-settle` |
| `armed` | OS permission revoked | `denied` | Immediate, `--d-2` colour only |
| any | No audio device | `unavailable` | Immediate, `--d-2` colour only |
| any | Runtime reports error | `error` | `--d-4` `--e-settle`; auto-recovers after 8s |

`error` auto-recovers: after 8000ms, if the runtime has not reported
resolution, return to `unavailable`. If the runtime reports recovery, transition
to `armed` at `--d-4` `--e-settle`.

### Permission request — exact behaviour

Permission request is browser-native. The UI prepares for it before calling
`getUserMedia`:

1. The button transitions to `armed` ring (35% live) at `--d-4` `--e-settle`.
2. The native OS/browser permission prompt appears. **Do not overlay any custom
   UI on top of it** — competing chrome confuses the founder.
3. **If granted:** transition to `armed` normally.
4. **If denied:** transition to `denied`. Below the mic label, at `--sp-3`
   (12px) below, a secondary line in `--t-body-sm`, `--c-ink-2` reads:
   `"Microphone access was blocked. Enable it in your browser settings to speak
   with Somesh."` This line is `max-width: 360px`, `text-align: center`. It
   persists until the founder manually restores permission or the session ends.
5. **If dismissed without choice:** treat as `denied` with secondary copy:
   `"Somesh needs microphone access to hear you. Type below or click the
   microphone to try again."`

The composer auto-expands immediately in all `denied`/`unavailable`/`error`
states. Text carries the full interaction.

### Reduced-motion endpoints

All ring scale animations collapse to instant opacity changes only. `--d-2`
opacity transition replaces all transform transitions. Icon and label still
change on state.

---

## 3.2 · Listening indicator

The listening indicator is distinct from the mic button. It answers the
founder's question: "Is Somesh hearing me right now?"

### Placement and geometry

Horizontally centred on the tree/text axis. Vertically: centred between the
bottom edge of the mic button and the top edge of the composer capsule. At the
reference layout, this is approximately `top: 75.5%` (approximately `y = 679px`
at 900h), `height: 2px`.

```css
.listening-bar {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  top: calc(var(--mic-bottom) + 16px);   /* 16px = --sp-4 below the ring edge */
  width: 40px;
  height: 2px;
  border-radius: var(--r-1);             /* 4px */
  background: var(--s-live);
  opacity: 0;
  transform-origin: center center;
  transition:
    opacity var(--d-3) var(--e-settle),
    width var(--d-4) var(--e-settle);
}
```

The `--mic-bottom` custom property is set by JS as `mic.offsetTop +
mic.offsetHeight + ring-offset` where `ring-offset = 8px` (the inset of the
`::after` pseudo from the button edge).

### State behaviour

| State | Width | Opacity | Additional |
|---|---|---|---|
| `idle` / `armed` / `processing` / `muted` / `denied` / `unavailable` / `error` | `40px` | `0` | — |
| `listening` | `40px` | `0.55` | Static — present but quiet |
| `capturing-speech` | `80px` | `1.0` | Width expands; this is the unmistakable "I hear you" signal |

Transition from `listening` to `capturing-speech` must reach full opacity and
80px width within 200ms of speech onset. Using `--d-3` (240ms) with
`--e-settle` satisfies this as the settle curve front-loads most of the
animation.

**Why a separate element rather than an animation on the mic ring:** the ring
conveys mode (is the system open to hearing?). The bar conveys activity (is the
system hearing right now?). They answer different questions and must be
readable simultaneously without one overriding the other.

**Why 2px, not a dot:** a horizontal line reads as a threshold being crossed —
a mouth being heard — rather than a status light. It is calm and does not
compete with the waveform above it.

### Reduced-motion endpoint

Opacity transitions only. No width animation. `listening`: opacity `0.55`,
width `40px`. `capturing-speech`: opacity `1.0`, width `40px` (width stays
fixed; amplitude is not shown).

---

## 3.3 · Voice waveform

The waveform is not decorative. It is an honest real-time display of the audio
amplitude the runtime is receiving. It appears only during `capturing-speech`
and fades during `processing` and `armed`.

### Placement

Centred on the tree/text axis. Positioned immediately above the mic button:
bottom edge of the waveform is `--sp-4` (16px) above the top edge of the mic
button (above the ring extension, i.e. above `mic.offsetTop − 8px − 16px`).

```css
.waveform {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  bottom: calc(100% - var(--mic-top) + 24px);
  display: flex;
  align-items: flex-end;
  justify-content: center;
  gap: 3px;
  height: 40px;
  opacity: 0;
  transition: opacity var(--d-3) var(--e-settle);
}
```

The waveform container is always `40px` tall. Bars grow upward from a shared
baseline at the container bottom.

### Bar specification

| Property | Value |
|---|---|
| Bar count | 9 |
| Bar width | 3px |
| Gap between bars | 3px |
| Total width | `(9 × 3) + (8 × 3) = 51px` |
| Min bar height | 3px |
| Max bar height | 36px (90% of container) |
| Corner radius | `var(--r-1)` (4px) on top corners only: `border-radius: 4px 4px 2px 2px` |
| Colour (dark theme) | `var(--s-live)` at opacity `0.85` |
| Colour (light theme) | `var(--s-live)` at opacity `0.90` |

**Why 9 bars:** 9 is odd, giving a centre bar on the axis. The centre bar
receives the highest-amplitude frequency bucket. Even bar counts create a gap
on the axis and feel off-centre.

**Why 3px bar / 3px gap:** tighter than the common 4/2 split, which makes bars
feel like a chart. At 3/3 they read as a single unified gesture.

### Amplitude mapping

The runtime delivers a normalised amplitude value `A ∈ [0.0, 1.0]` for the
current frame (this is a presentation-layer assertion — how the runtime derives
it is not specified here).

Each bar `i` (0 = leftmost, 4 = centre, 8 = rightmost) receives its own
amplitude sample `a[i]` from the runtime's frequency-band data. If the runtime
delivers a single scalar rather than per-band values, apply this shaping
function to produce bar heights from a single `A`:

```
shape[i] = 1.0 − abs(i − 4) / 4        /* triangular envelope, peak at centre */
a[i] = A × shape[i]
```

Height formula:

```
H_min = 3
H_max = 36
height[i] = H_min + (H_max − H_min) × a[i]
           = 3 + 33 × a[i]   (px)
```

**Smoothing:** apply exponential smoothing per bar at each frame:

```
smoothed[i] = smoothed_prev[i] × 0.72 + a[i] × 0.28
```

Smoothing coefficient `0.72` (hold weight). This means a bar responds to a
spike within approximately 3 frames but decays slowly enough to avoid
flickering. At 60fps, a peak at frame 0 reaches 50% at frame 4 and 10% at
frame 7.

**Frame rate:** 60fps target. If `requestAnimationFrame` is unavailable or the
tab is backgrounded, the waveform stops updating; the bars hold their last
smoothed value. No timer-based fallback.

### Resting state (amplitude data unavailable)

When the waveform is visible (state `capturing-speech`) but amplitude data has
not yet arrived for the current frame, render this exact static configuration:

```
bar heights: [3, 5, 9, 14, 18, 14, 9, 5, 3]  (px)
```

This is a fixed triangular shape, not a random or looping animation. It reads
as "open and ready" rather than "broken" or "active". Do not interpolate toward
this shape — set it instantly if data is unavailable, and resume normal
animation the moment data arrives.

### Visibility rules

| Mic state | Waveform opacity | Note |
|---|---|---|
| `idle` | `0` | hidden |
| `armed` | `0` | hidden |
| `listening` | `0` | hidden — the bar handles "I hear you" |
| `capturing-speech` | `1.0` | visible, animating |
| `processing` | `0.30` | partially visible, held at last smoothed heights, not animating |
| `muted` | `0` | hidden |
| `denied` | `0` | hidden |
| `unavailable` | `0` | hidden |
| `error` | `0` | hidden |

Transition to/from `0`: `--d-3` (240ms) `--e-settle`. Transition to/from `0.30`:
`--d-4` (320ms) `--e-settle`.

### Reduced-motion endpoint

A static 3-bar stepped level meter replaces the 9-bar animated waveform.

```css
@media (prefers-reduced-motion: reduce) {
  .waveform {
    gap: 4px;
  }
  .waveform .bar:nth-child(1),
  .waveform .bar:nth-child(3),
  .waveform .bar:nth-child(5),
  .waveform .bar:nth-child(6),
  .waveform .bar:nth-child(7),
  .waveform .bar:nth-child(8),
  .waveform .bar:nth-child(9) {
    display: none;
  }
  /* bars 2, 4, 5 (0-indexed: 1, 3, 4) remain */
}
```

In reduced-motion mode, 3 bars remain (leftmost visible, centre, rightmost
visible). Heights step between three fixed levels based on amplitude quantised
to low/medium/high:

```
A < 0.33: heights = [6, 10, 6]
A < 0.66: heights = [12, 20, 12]
A ≥ 0.66: heights = [22, 36, 22]
```

No interpolation between levels. Heights change instantly on level boundary
crossing.

---

## 3.4 · Interrupt animation

The founder may interrupt Somesh at any point during playback. Interruption is
absolute and instant — Somesh never "lets himself finish".

### Definition of interrupt

An interrupt occurs when ANY of the following happens while Somesh is in his
`speaking` state (runtime is delivering audio):

1. The founder clicks the mic button.
2. The VAD detects speech onset from the founder.
3. The founder begins typing (any printable keypress or focus on composer).
4. The founder presses `Escape`.

### What stops

- Audio playback halts immediately — mid-word, mid-phoneme, at the exact
  sample boundary. **No fade-out.** Cut is clean.
- The waveform, if visible, drops to opacity `0` at `--d-2` (180ms)
  `--e-settle`.

### Tree response

The tree transitions from its `speaking` state to `listening` or `thinking`
state (depending on which interrupt trigger fired) using the **state transition
named `speaking → listening`** from the animation system. This transition should
already be specified in the animation document. Duration: `--d-8` (1400ms),
easing `--e-settle`. The canopy bloom opacity drops from `1.0` to `1.0`
(listening) — there is no visual "flinch". The tree does not react dramatically
to being interrupted; it simply shifts state. This communicates that Somesh is
not bothered by the interruption.

### Visual acknowledgement

The Somesh message that was being spoken acquires a partial-transcript marker:
the text rendered so far (the portion delivered before the cut) remains visible.
Below it, a `--t-mono` line in `--c-ink-3` reads `— interrupted`. This appears
at `--d-3` (240ms) `--e-settle` opacity `0 → 1`. It is the only visual
acknowledgement of the interrupt.

No toast, no banner, no animation beyond the tree state change and this marker.

### Duration

The full interrupt sequence (audio cut → tree state shift begins → acknowledge
marker appears) completes its visible phases within `--d-4` (320ms). The tree's
own state animation continues for its full `--d-8` in the background.

---

## 3.5 · Mute state

Three distinct conditions all suppress microphone input. They are not
synonyms — they require different copy and different recovery paths.

### `muted` — founder chose silence

**How toggled:** single click or tap on the mic button in any active state
(`armed`, `listening`, `capturing-speech`, `processing`). Single click again to
unmute. There is no hold-to-mute. There is no keyboard shortcut beyond the mic
button's accessible role (Enter/Space when focused).

**Persists across sessions:** yes. If the founder mutes and closes the window,
the next session opens in `muted` state. The label reads `MUTED`. This is
intentional — a founder who muted has a reason. The product respects it without
asking why.

**Icon:** `microphone-muted`. Colour: `--c-ink-3`. Ring: `1px dashed
var(--c-ink-3)` — the dashed ring is the exclusive visual vocabulary for
founder-chosen silence. It differs from the solid ring of `denied` and the
faint ring of `unavailable`.

**What the tree does while muted:** tree transitions to and holds the `idle`
state (from animation system). Bloom at `0.6`. The tree is still alive; it is
simply not listening. This communicates presence without surveillance.

**Secondary label:** none. Mute is a normal state and needs no explanation.

### `denied` — OS/browser blocked permission

**How triggered:** OS or browser denied microphone access.

**Cannot be toggled by clicking the mic button.** Clicking in `denied` state
opens the browser's native permission settings page for this origin (via
`window.open(chrome://settings/content/microphone)` on Chromium or equivalent).
If the platform does not support direct settings deep-link, the mic click shows
the copy below without any navigation.

**Icon:** `microphone-muted`. Colour: `--s-attend`. Ring: `1.5px solid
color-mix(in srgb, var(--s-attend) 50%, transparent)`. Solid — this is a
condition, not a choice.

**Copy below mic label (12px below in `--t-body-sm`, `--c-ink-2`,
max-width 360px, centred):**
`"Microphone access was blocked. Click here to open settings."`

The word "here" is styled with `color: var(--s-live)` and `cursor: pointer`.
Clicking it triggers the settings deep-link described above.

**Tree while denied:** tree holds whatever state it was in. The bloom dims to
`0.4` at `--d-8` `--e-settle`. The tree does not go dark; the founder can still
interact via text.

### `unavailable` — no audio device

**How triggered:** the runtime reports no audio input device is present (no
hardware microphone).

**Cannot be toggled.** Mic button is in `disabled` interaction state
(`cursor: not-allowed`) but remains visually present so the founder understands
what is missing.

**Icon:** `microphone-muted`. Colour: `--c-ink-4`. Ring: `1.5px solid
var(--c-hair-soft)`. Very quiet — this condition is permanent for the session
and should not alarm.

**Copy below mic label (12px below in `--t-body-sm`, `--c-ink-3`,
max-width 360px, centred):**
`"No microphone found. Type to continue."`

**Tree while unavailable:** tree holds `idle`. No special treatment.

**Composer behaviour in all three states:**

| State | Composer |
|---|---|
| `muted` | Collapsed (founder can still use text normally) |
| `denied` | Auto-expands and takes focus immediately on entering `denied` |
| `unavailable` | Auto-expands on load; cannot collapse |

---

## 3.6 · Noise handling

Noise handling is entirely a runtime concern. The UI presents the runtime's
assessment without exposing technical detail or blaming the founder.

Three runtime-reportable conditions:

### Low confidence — runtime unsure what it heard

Triggered when: the runtime delivers a transcript result with confidence below
its threshold.

**Presentation:** the transcript text appears at `--t-body`, `--c-ink-2`
(reduced from `--c-ink`) to indicate uncertainty. A line in `--t-body-sm`,
`--c-ink-3` appears below the transcript: `"Not quite sure — say that again?"`.
This is styled identically to `--t-body-sm` secondary text, not as an error.

Placement: within the transcript region (see §3.8), immediately below the
uncertain transcript line. It occupies one line.

Dismissal: it disappears automatically when the next `capturing-speech` state
begins. It does not require any founder action.

### High ambient noise — runtime reports poor signal

Triggered when: the runtime reports an SNR below its operating threshold during
a `listening` or `capturing-speech` window.

**Presentation:** a single inline notice appears below the listening indicator
(i.e., below the 2px bar, above the composer). The notice is:

```css
.noise-notice {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  /* positioned immediately above composer top */
  bottom: calc(var(--composer-top) + 12px);
  font: var(--t-body-sm);
  color: var(--c-ink-3);
  text-align: center;
  white-space: nowrap;
  opacity: 0;
  transition: opacity var(--d-3) var(--e-settle);
}
```

Copy: `"Background noise is high — you can type instead."`

It appears when the runtime signals the condition and fades out `--d-3`
`--e-exit` when the runtime signals the condition has cleared or the session
moves to `processing`. It never appears for longer than one listening window.

### No speech detected — listening window expired without input

Triggered when: the runtime's listening window closes without detecting speech.

**Presentation:** the mic returns to `armed`. No copy appears. Silence is a
valid choice. Showing "no speech detected" would be patronising.

The tree holds `armed` state (canopy bloom at `1.0`). Nothing else changes.
There is no timeout notice. There is no re-prompt.

**Why this section avoids copy for the no-speech case:** a founder may have
opened their mouth and decided not to speak, or may be thinking. Prompting them
would interrupt their thought. The product's personality is patient.

---

## 3.7 · Voice + text simultaneously

Both inputs are always live when the runtime permits. The hard case is when the
founder switches input mode mid-utterance, or uses both.

### State model

Exactly two input channels are active when voice is available:

1. **Voice channel** — mic state machine (`§3.1`)
2. **Text channel** — composer (`01_FOUNDER_SURFACE §1.6`)

They are independent state machines. Neither disables the other.

### Composer expanded while mic is `armed`

The mic remains in `armed` state — ring at 35% live, icon `--s-live`. The
composer expands to its full width. Both are simultaneously visible. No visual
conflict: they occupy different vertical positions on the axis.

**Focus ring:** the focus ring on the composer input field does not suppress the
mic ring. Both may be visible simultaneously.

### Founder starts typing mid-utterance (voice was `capturing-speech`)

1. The typing keystroke is captured by the composer (the `capturing-speech`
   state is registered as an interrupt — see §3.4).
2. The audio capture stops. The runtime receives an interrupt signal.
3. The mic transitions to `processing` then `armed`.
4. Whatever was captured in the utterance up to the keystroke is discarded by
   the runtime. **The UI does not show a partial transcript from an interrupted
   utterance.**
5. The keystroke appears in the composer as the first character of the new
   typed input.

This is the cleanest possible behaviour: the founder typed, so they want to
type. The interrupted voice input is abandoned cleanly.

### Founder speaks with text already in composer (non-empty composer, mic `armed`)

The mic transitions normally through `listening → capturing-speech → processing`.
The text in the composer is **not submitted** and **not cleared** by the voice
input. The spoken message is handled by the voice channel as a complete,
independent message.

The text remains in the composer after the spoken message completes. The founder
can continue typing and submit it separately. This prevents data loss when the
founder has partially composed a thought in text and then responds to something
verbally.

### Which input wins on `Enter`

`Enter` (without Shift) in the composer always submits the composer's text
content, regardless of mic state. If the mic is `capturing-speech` at the
moment `Enter` is pressed, this triggers the interrupt sequence (§3.4) AND
submits the text. The two actions are simultaneous: interrupt fires on the same
frame as the text submit.

**The precedence rule, stated plainly:** the channel whose content is being
actively entered at the moment of submission wins. Text in the composer and
voice being captured simultaneously — whichever the founder acted on (pressed
Enter, or finished speaking and paused) resolves first.

### How both states are visible at once without competing

The mic and the composer occupy different vertical regions of the screen and
different semantic registers. The mic state is carried in the ring and icon
(above). The composer state is carried in its border and focus ring (below).
They do not share visual vocabulary. A founder can see "LISTENING" in the mic
label and cursor-position in the composer simultaneously without confusion.

**What never happens:** the mic does not grey out when the composer is focused.
The composer does not collapse when the mic activates. These two inputs are
equals.

---

## 3.8 · Voice transcript

The transcript is how spoken words appear as text in the conversation. It has
two phases: **interim** (in-flight, subject to change) and **final** (committed
by the runtime).

### Interim transcript

Appears in the composer text area during `capturing-speech` and `processing`.
It is not in the conversation column. It is in the composer.

```css
.composer-interim {
  color: var(--c-ink-2);      /* reduced from --c-ink to signal tentativeness */
  font-style: italic;          /* further visual distinction */
  opacity: 0.8;
}
```

The interim text is non-editable inline text prefixed to any text the founder
has typed, or it occupies the composer alone if no typed text is present. If
the founder has typed text in the composer, the interim transcript is rendered
as a suffix, separated by a single space, in the `--c-ink-2` italic style.

The interim text updates in real time as the runtime refines its hypothesis.
When text changes (correction), the change is applied immediately — no
animation, no deletion-then-retype simulation. The string simply becomes its
new value.

### Final transcript

When the runtime commits a final result, the interim text in the composer is
replaced by the final text. Final text adopts `--c-ink` (not italic, not
reduced opacity). This is the founder's message, now confirmed.

The transition from interim to final:

```css
.composer-text {
  transition: color var(--d-2) var(--e-settle);
}
```

Colour changes from `--c-ink-2` to `--c-ink` over `--d-2`. Italic is removed
instantly (no transition on `font-style` as it is not animatable).

### Where the transcript lands in conversation

On submission (voice or text), the final text becomes a **Founder message** in
the conversation column (see `04_CONVERSATION_DESIGN §4.2`). It appears at the
bottom of the conversation scroll area, right-aligned. The scroll view
auto-scrolls to show it.

### Correction behaviour

When interim text is revised (the runtime changes its hypothesis mid-utterance),
the displayed text in the composer is replaced in place. There is no
strikethrough. There is no delete-then-retype. The string value of the
`contenteditable` region is updated directly. The cursor position is preserved
at the end of the text.

**Why interim is in the composer rather than in the conversation column:** the
interim transcript is not yet a message — it is speech in flight. Placing
it in the conversation column before the founder has committed it would create
ghost messages that disappear or change, which violates "never fake activity".
The composer is already understood as the staging area for a message.

---

## TOKEN ADDITION REQUESTS

The following values are needed by this document and are absent from
`00_TOKENS.md`. They should be added there before implementation.

### ADDITION 1 — `--d-gate`

Used in `04_CONVERSATION_DESIGN §4.6` (thinking indicator latency gate). Value
proposed: `400ms`. This is distinct from any existing duration token.

```css
--d-gate: 400ms;   /* thinking indicator: do not show below this */
```

### ADDITION 2 — JS layout variable protocol

The document references `--mic-top` and `--mic-bottom` as CSS custom properties
set by JavaScript. These are not design tokens (they carry computed layout
values, not design decisions) and should not be listed in `00_TOKENS.md`, but
the engineering team should be aware of the contract: the JS layout layer must
set these on the `:root` element on every resize and on any layout reflow.

---
