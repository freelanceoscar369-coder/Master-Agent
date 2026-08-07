# Product Veda · Deliverable 9 — Notification System

The tree is the notification surface. A notification is not an interruption —
it is a change in the tree's condition that the founder may notice, attend to,
or let pass. The tree speaks first with its body; the language follows only
when the founder chooses to look.

**No Windows-style popups. No badges. No counts. No red dots. No notification
centre panel. No persistent banners.**

---

## 9.1 · Taxonomy — three tiers

Two engineers, given the same event, must independently classify it into the
same tier. The classification criteria are exhaustive and mutually exclusive.

### Tier 1 — Ambient

**Definition:** Information the founder may benefit from knowing, but which
requires no action and has no deadline. Missing it has no consequence.

Examples: a goal was logged, a weekly pattern emerged, a streak continued, a
reflection was added to memory.

**Key test:** "If the founder never sees this notification, does anything go
wrong?" If no: Tier 1.

### Tier 2 — Attention

**Definition:** Something has changed that the founder will likely want to know
about, but action is not immediately required. There is a natural window of
relevance (hours, not seconds).

Examples: a planned item moved to today's horizon, a recurring commitment
arrived, a context shift was detected that affects the current focus area.

**Key test:** "Does the founder benefit from knowing this in the next few hours,
but the world does not end if they don't?" If yes: Tier 2.

### Tier 3 — Consequential

**Definition:** An item requires founder attention and has a meaningful
deadline or irreversibility. Not acting has a defined cost.

Examples: a calendar-anchored hard commitment is now (within 60 seconds), a
decision window is closing, an irreversible action awaits founder confirmation.

**Key test:** "Is there a real cost to missing this?" If yes: Tier 3.

**Important:** Tier 3 is rare by design. If more than three Tier 3 notifications
arrive in a single day, the classification is wrong — the source events are
being over-weighted, not under-notified. The threshold for Tier 3 is hard.

---

## 9.2 · Tree behaviour per tier

All animation state names are from **02_ANIMATION_SYSTEM**. This document
references those states by name and does not restate their internals.

### 9.2.1 · Tier 1 — Ambient

**Tree behaviour:** localised leaf glow in the relevant branch region (§9.3).

| Property | Value |
|---|---|
| Animation state invoked | `leaf-glow-ambient` (02_ANIMATION_SYSTEM) |
| Colour token | `--tree-particle` at its base alpha in the active theme |
| Duration | `var(--d-8)` (1400ms) total: 400ms fade-in, 600ms hold, 400ms fade-out |
| Repeats | No. Single pulse, then returns to the tree's current base state |
| Concurrent with tree state | Yes — the tree's current animation state (idle, listening, etc.) continues underneath; the leaf glow is additive |

The Tier 1 pulse is subtle. At conversational distance from a monitor, it may
be perceived as a slight brightening in one region of the tree. That is
intentional — it is ambient, not demanding.

### 9.2.2 · Tier 2 — Attention

**Tree behaviour:** a specific branch region brightens and holds, then slowly
fades. More persistent than Tier 1 — it waits.

| Property | Value |
|---|---|
| Animation state invoked | `branch-attend` (02_ANIMATION_SYSTEM) |
| Colour token | `--s-live` |
| Duration | `var(--d-8)` (1400ms) fade-in, then **holds** at 60% of peak opacity indefinitely until dismissed (§9.5). Fades out over `var(--d-6)` (600ms) on dismiss. |
| Repeats | No pulsing repeat. Holds at steady 60% opacity. One gentle re-pulse (`var(--d-5)`, 420ms) after 90 seconds if not yet attended to — then holds again. Max one re-pulse. |
| Concurrent with tree state | Yes — additive overlay on the current tree state |

The Tier 2 glow is visible but not alarming. It uses `--s-live` (the "system
alive" colour) because attending to a Tier 2 item is a natural act of
collaboration, not an emergency.

### 9.2.3 · Tier 3 — Consequential

**Tree behaviour:** a full-branch brightening with increased particle density,
using the attention signal colour. The tree "reaches" toward the founder.

| Property | Value |
|---|---|
| Animation state invoked | `branch-consequential` (02_ANIMATION_SYSTEM) |
| Colour token | `--s-attend` |
| Duration | `var(--d-6)` (600ms) fade-in. Holds at full opacity. Pulses with period `var(--d-8)` (1400ms in, 1400ms rest) using `--e-breathe` easing. Continues until dismissed. |
| Repeats | Persistent pulse (in/out breathing at `--e-breathe`) until dismissed |
| Concurrent with tree state | Overrides the current tree ambient state for the affected branch only. Global tree state (idle vs. listening vs. thinking) continues for unaffected regions. |

The pulse uses `--e-breathe` (`cubic-bezier(0.45, 0, 0.55, 1)`) — symmetric,
calm, never aggressive. The tree breathes urgency, it does not flash it.

---

## 9.3 · Localised leaf glow — geometry

"A leaf glows in the branch where the thing happened."

### 9.3.1 · Branch regions and domain mapping

The tree is divided into regions corresponding to life domains. The exact
number and boundaries of these regions are defined in **02_ANIMATION_SYSTEM**
(which specifies the tree's structural anatomy). This document specifies the
notification geometry; the branch-to-domain mapping is a rendering concern
owned by 02_ANIMATION_SYSTEM.

For notification purposes, the tree has **four branch quadrants**:

| Quadrant | Position in tree | Example domains |
|---|---|---|
| Upper-left | Upper-left canopy region | Long-horizon, strategic |
| Upper-right | Upper-right canopy region | Immediate, operational |
| Lower-left | Lower-left inner branches | Relationships, context |
| Lower-right | Lower-right inner branches | Current focus, active work |
| Trunk | Central trunk column | Cross-domain, systemic |

When a notification has no specific domain mapping, it defaults to the `Trunk`
region.

The mapping from a notification's source domain to a quadrant is determined by
the application layer and passed to the tree renderer as a parameter. The
renderer does not infer the domain from the notification content.

### 9.3.2 · Glow geometry

A leaf glow is a radial light point centred at a specific normalised coordinate
within the tree's canvas (`0,0` = top-left of canvas, `1,1` = bottom-right):

```
Glow center: [cx, cy] in normalised canvas coordinates
             Provided by the branch-region lookup from 02_ANIMATION_SYSTEM.
             For Tier 1 events: a specific leaf-node coordinate within the
             target quadrant, chosen pseudo-randomly from the set of active
             particle positions in that quadrant at the moment of notification.
             For Tier 2–3: the centroid of the affected branch sub-region.

Glow radius: Tier 1: 0.06 × canvas-width   (approx 56px at 940px canvas)
             Tier 2: 0.10 × canvas-width   (approx 94px at 940px canvas)
             Tier 3: 0.16 × canvas-width   (approx 150px at 940px canvas)

Opacity:     Falloff is radial:
             innerOpacity: Tier 1 = 0.38, Tier 2 = 0.55, Tier 3 = 0.70
             falloff: r^2 (quadratic — gentler than linear, not as sharp as
                      gaussian; this is the "soft bloom" feel)
             outerOpacity: always 0.00 at the glow radius edge

CSS-equivalent (drawn on canvas, not CSS):
  const gradient = ctx.createRadialGradient(cx, cy, 0, cx, cy, glowRadius);
  gradient.addColorStop(0, `rgba(r, g, b, ${innerOpacity})`);
  gradient.addColorStop(1, `rgba(r, g, b, 0.00)`);
```

The glow is drawn to the tree canvas as an additive layer (composite operation
`source-over` at the fill opacity). It does not replace the underlying tree —
it brightens it locally.

### 9.3.3 · Duration and lifecycle

| Phase | Tier 1 | Tier 2 | Tier 3 |
|---|---|---|---|
| Fade in | 400ms (`--e-settle`) | `var(--d-6)` 600ms (`--e-settle`) | `var(--d-6)` 600ms (`--e-settle`) |
| Hold | 600ms at full opacity | Indefinite (until dismissed) | Indefinite (with pulse) |
| Fade out | 400ms (`--e-exit`) | `var(--d-6)` 600ms (`--e-exit`) on dismiss | `var(--d-6)` 600ms (`--e-exit`) on dismiss |

---

## 9.4 · How a notification is read — the reveal surface

**No modals. No notification centre. No slide-out panel.**

When the founder attends to a glowing branch (by any of the gestures below), the
notification detail appears in the **notification bloom card**.

### 9.4.1 · Attend gestures

| Gesture | Effect |
|---|---|
| **Voice** — speaking to Somesh while the tree is in an attention or consequential state | Somesh opens by acknowledging the notification in his response |
| **Click or tap on the glowing region of the tree** | The notification bloom card appears |
| **`Cmd+N` / `Ctrl+N`** | Opens the notification bloom card for the highest-tier pending notification |

The notification bloom card is not in the dashboard — it is not behind the
dashboard chevron. It is a lightweight surface that appears directly over the
tree, on the Founder Surface, without opening the dashboard.

### 9.4.2 · Notification bloom card

The bloom card is a small surface that sits at `z-index: var(--z-transient)`
(30), near the glowing tree region, containing the notification detail.

```css
.notification-bloom-card {
  position: fixed;
  /* Positioned by JS to sit adjacent to the glow centroid,
     clamped to always be fully within the viewport. */
  background: var(--glass-dark);   /* light theme: var(--glass-light) */
  backdrop-filter: blur(var(--blur-transient));
  border-radius: var(--r-3);       /* 14px */
  border: 1px solid var(--c-hair);
  box-shadow: var(--el-3);
  padding: var(--sp-5) var(--sp-6);  /* 24px 32px */
  max-width: 320px;
  min-width: 240px;
}
```

Contents, from top:
1. A `--t-label` line in the appropriate signal colour: the tier label
   (`AMBIENT` / `ATTENTION` / `CONSEQUENTIAL`). Tier 1 cards are never labelled
   with `AMBIENT` — the label is omitted for Tier 1 to reduce interruption.
2. The notification title: `--t-title` (22px / 32px, 500), `--c-ink`. One line,
   no wrap, truncated at 36 characters with no ellipsis (the title is set by
   the system, not user-authored).
3. The notification body: `--t-body` (15px / 24px, 400), `--c-ink-2`. Maximum
   3 lines, no scroll within the card. Content that does not fit is not shown —
   the card is not a document.
4. Tier 3 only: an inline action line at the bottom in `--t-label`, `--s-attend`.
   E.g., `"SPEAK TO RESPOND"`. No button. The intended action is always voice or
   text with Somesh — not a click target.

The bloom card appears with `opacity` from `0` to `1` over `var(--d-5)` (420ms)
`var(--e-settle)`. It does not slide or scale in.

### 9.4.3 · Positioning the bloom card

The card is placed adjacent to the glow centroid: above the centroid if the
centroid is in the lower half of the canvas; below if in the upper half.
Horizontal position follows the centroid, clamped so the card is always
`var(--sp-6)` (32px) from any viewport edge.

The card never overlaps the text stack (the greeting, presence line, mic, and
composer region). If the calculated position would overlap the stack, the card
is repositioned to the nearest non-overlapping position horizontally.

---

## 9.5 · Dismissal and persistence — nothing consequential is lost silently

### 9.5.1 · Dismissal gestures

The bloom card is dismissed by:
- `Escape` key
- Clicking or tapping anywhere outside the card
- The `close` icon (20×20, `--c-ink-3`) in the card's top-right corner
- Speaking to Somesh (Somesh addressing the item counts as dismissal)

### 9.5.2 · Persistence rule

| Tier | What happens after dismissal |
|---|---|
| Tier 1 (Ambient) | The notification is marked read. The tree glow fades. The notification is gone. If the founder never saw the bloom card, it is gone after its natural duration (`var(--d-8)` total). No record persists in the UI. |
| Tier 2 (Attention) | The tree glow fades on dismiss. The notification is recorded in the session transcript visible in conversation history. It does not re-appear. |
| Tier 3 (Consequential) | The tree glow fades on dismiss. The notification is recorded in conversation history AND in a dedicated log accessible from the dashboard (the dashboard's content is out of scope here — the log must exist there). Tier 3 items persist in the log until the founder explicitly marks them resolved through conversation with Somesh. They cannot be silently dropped. |

**A Tier 3 notification cannot be made to disappear from the log by dismissing
the bloom card.** Dismissal only closes the card and stops the tree pulse.
The item remains in the log until resolved. This is the guarantee that nothing
consequential can be lost silently.

---

## 9.6 · Rate limiting — preventing a notification storm

### 9.6.1 · Coalescing window

All incoming notifications pass through a coalescing queue with a **5-second
window**. If two or more notifications arrive within the same 5-second window
and are of the same tier and the same branch quadrant, they are merged into a
single notification. The merged notification's title is the most recent
notification's title; the body indicates multiple items:

```
"[Item title] and N other items"
```

where N is the count of coalesced items (minimum 1 — so "and 1 other item").

### 9.6.2 · Concurrent display limit

At most **one** tree glow is active at a time per quadrant. If a notification
arrives while the same quadrant is already glowing:

- If the new notification is the same tier or lower: it is queued. It activates
  when the current glow is dismissed or expires.
- If the new notification is a higher tier: it immediately supersedes. The
  current glow fades out in `var(--d-3)` (240ms) and the higher-tier glow
  takes over.

At most **two** quadrants may glow simultaneously across the entire tree.
If a third notification arrives for a third quadrant while two are active:

- If it is Tier 1: discard silently (it will reappear in the session transcript).
- If it is Tier 2: queue it. It activates when the first quadrant glow is
  dismissed.
- If it is Tier 3: it supersedes the Tier 1 or Tier 2 glow with the least
  urgency.

### 9.6.3 · Hard rate ceiling

If more than **6 notifications** arrive in any **60-second window**, the system
enters a `coalesced` mode:

1. All pending notifications are merged into a single Tier 2 (or the highest
   tier present) notification for the Trunk region.
2. The Trunk region glows at Tier 2 intensity.
3. The bloom card title reads: `"Several things need your attention"`.
4. The body lists the first three titles, one per line.
5. No further individual glows fire during the coalesced mode window.
6. Coalesced mode ends when the trunk glow is dismissed.

This prevents the tree from becoming a strobing information overload. A founder
who sees the tree turn chaotic with simultaneous glows would correctly interpret
this as a system failure, not a product feature.

---

## 9.7 · Behaviour when window is blurred or minimized

Cross-reference: 07_DESKTOP_PRESENCE §7.4 (minimize) and §7.7 (blur).

### Blurred window

Notifications continue to arrive and the tree continues to animate (the tree
keeps breathing when blurred, per 07_DESKTOP_PRESENCE §7.7.1). Tier 1 and
Tier 2 glows fire normally — the founder may glance at the blurred window and
notice them. The bloom card does NOT auto-open when the window is blurred. It
only opens on an explicit attend gesture (which requires re-focusing the window
first).

Tier 3: the tree glow fires. Additionally, the OS notification exception in
07_DESKTOP_PRESENCE §7.3.2 applies — the OS toast fires if the item is
calendar-anchored and the window has been out of focus.

### Minimized window

Tree rendering is paused (07_DESKTOP_PRESENCE §7.4.1). No glows render during
minimization. When the window is restored:

- All pending Tier 1 notifications are discarded (they are ambient; the moment
  has passed).
- Pending Tier 2 notifications fire their glow immediately on restore.
- Pending Tier 3 notifications fire their glow immediately on restore AND are
  in the session transcript and dashboard log as specified in §9.5.2.

Tier 3 items that arrived while minimized AND qualify for an OS notification
(07_DESKTOP_PRESENCE §7.3.2) will have already fired an OS toast. The
in-app glow on restore is additive — it is not suppressed because an OS toast
was shown.

---

## 9.8 · Quiet hours

If the OS reports `prefers-reduced-motion: reduce`, all notification glows
operate without animation: the affected tree region changes to the target
opacity immediately (no fade-in), holds, and changes back immediately on
dismiss. The `--d-1` (120ms) opacity transition still applies (per
00_TOKENS §10.10 — transitions collapse to `--d-1` opacity only under reduced
motion). The glow is present; it is not animated.

---

## 9.9 · FORBIDDEN list — explicit prohibitions

The following are forbidden in the notification system. No future engineer may
add them without a full product decision revision.

| Forbidden element | Why |
|---|---|
| Badge counts (dot, number) on the dock or tray icon | Turns the mark into a task counter; violates the premium, calm identity |
| Badge counts on any UI element | Same reason |
| Red dot on any surface | Red is `--s-risk` and means irreversible/wrong. Using red for "you have unread items" corrupts the semantic |
| OS toast notifications except the single narrow exception in §9.6 / 07_DESKTOP_PRESENCE §7.3.2 | Intrusive, breaks the product's visual language |
| Notification centre panel or drawer | Not in the product's four z-planes; would require a modal or a fifth plane |
| Notification sounds | Sound is the most intrusive interrupt vector. Kalpavriksha does not control the OS sound environment; a sound would feel like a system alert, not a companion |
| Flashing or blinking animations | Any animation that repeats more than 3 times per second may induce photosensitive response. All tree pulses use `--e-breathe` with period ≥ 2800ms, well below the 3Hz threshold. No faster repeat is ever permitted. |
| Interruption of voice output | If Somesh is mid-utterance, no notification may interrupt the audio. The tree glow fires; the audio continues. |
| Notification stacking (multiple bloom cards open at once) | At most one bloom card is visible at any time (§9.6.2) |
| In-notification action buttons | Actions are taken by speaking to Somesh, not clicking buttons in a notification surface |
| Notification history view / count | There is no notification count. Tier 3 items persist in the dashboard log; that is the history mechanism. |

---

## TOKEN ADDITION REQUEST

The following tokens are needed to implement §9.3.2 (glow geometry) precisely
and are absent from 00_TOKENS.md. They are listed here rather than invented
inline, per the writing standard.

```
--notif-glow-radius-t1: 0.06   /* Tier 1 glow radius as fraction of canvas-width */
--notif-glow-radius-t2: 0.10   /* Tier 2 glow radius as fraction of canvas-width */
--notif-glow-radius-t3: 0.16   /* Tier 3 glow radius as fraction of canvas-width */
--notif-glow-opacity-t1: 0.38  /* Tier 1 inner glow opacity */
--notif-glow-opacity-t2: 0.55  /* Tier 2 inner glow opacity */
--notif-glow-opacity-t3: 0.70  /* Tier 3 inner glow opacity */
```

These are dimensionless ratios, not CSS lengths or colours. They belong in
00_TOKENS §10.7 alongside the blur token, as canvas rendering parameters.
The notification system specifies them here and requests their addition to the
authoritative token file.
