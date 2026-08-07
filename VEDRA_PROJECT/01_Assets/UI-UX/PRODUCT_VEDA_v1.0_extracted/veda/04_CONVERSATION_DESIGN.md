# Product Veda · Deliverable 4 — Conversation Design

**Authoritative.** All tokens from `00_TOKENS.md`. All layout references from
`01_FOUNDER_SURFACE §1.x`. Two independent engineers reading this document must
build the same thing.

---

## 4.0 · Design intent, stated once

The conversation is a living record of the founder's relationship with Somesh.
It is not a chat log, not a support ticket thread, not a dashboard. The visual
language must reflect that Somesh is present and considered — his responses are
not bubbles in a feed, they are statements. The founder's messages are
confirmations that the founder was heard.

Prose legibility governs every decision. Measure, weight, and rhythm are
calibrated for extended reading, not scanning.

---

## 4.1 · Layout and measure

### Conversation column

```css
.conversation {
  width: var(--measure-conversation);   /* 720px */
  max-width: calc(100% - 2 * var(--frame-margin-desktop));
  margin: 0 auto;
  padding-top: var(--sp-8);             /* 64px — space below the window chrome */
  padding-bottom: 160px;                /* 160px — keeps last message above composer */
}
```

On small laptop (`--frame-margin-laptop: 48px`): `max-width: calc(100% - 96px)`.
On tablet (`--frame-margin-tablet: 32px`): `max-width: calc(100% - 64px)`.

The column is **horizontally centred** in the window. This is the only layout
in the product that shares the home screen's centred axis; the reason is that
the conversation column replaces the home screen, it does not sit alongside it
(see transition below). Once in conversation view, the tree is visible behind
and above the column, so the centred axis is still the tree's trunk.

**Vertical rhythm:** `--sp-2` (8px) base grid. Message blocks stack with
`--sp-5` (24px) between them. Within a Somesh reply block, paragraph spacing
is `--sp-3` (12px). All numbers are multiples of the 8px rhythm.

**Scroll region:** the conversation column is the scroll container.

```css
.conversation-scroll {
  position: absolute;
  inset: 0;
  bottom: 0;
  overflow-y: scroll;
  overflow-x: hidden;
  scroll-behavior: smooth;
  overscroll-behavior-y: contain;
  -webkit-overflow-scrolling: touch;
}
```

The scroll region occupies the full window height. The top padding of
`--sp-8` (64px) plus the `z-index: var(--z-content)` stacking ensures the
fixed chrome (wordmark, chevron) sits above the scrollable content without
clipping it.

### Tree visibility during conversation

The tree is always visible behind the conversation column. It is not obscured.
The conversation column has no opaque background — it renders over the tree
canvas.

Each Somesh message block has its own background treatment (specified in §4.3)
that provides contrast for type without covering the tree broadly. The veil
layer from `01_FOUNDER_SURFACE §1.2` remains in place at its specified
opacity — it provides the continuous low-contrast ground.

**No additional dimming on the tree during conversation.** The tree's state
machine drives its own visual intensity; the conversation UI does not dial it
down. The tree dims naturally as Somesh completes speaking (from the speaking
state back toward idle or armed), which creates a natural "settling" rhythm that
accompanies the appearance of the final response text.

### Transition from home screen to conversation view

When the first message is submitted (voice or text), the home screen transforms
into the conversation view. This transition is a single coordinated animation,
not a page navigation. There is no route change, no loading spinner.

**Duration:** `--d-6` (600ms). **Easing:** `--e-settle`.

Elements and their motion:

| Element | Motion |
|---|---|
| Greeting (`--t-greeting`) | Opacity `1 → 0` over `--d-3` `--e-exit`. Does not translate — it fades in place. |
| Presence line | Opacity `1 → 0` over `--d-3` `--e-exit`. |
| Footer hint (if visible) | Opacity `1 → 0` over `--d-2` `--e-exit`. |
| Composer capsule | Translates from its home-screen position (`bottom: 18%`) to its conversation-view position (`bottom: 0`, pinned) over `--d-6` `--e-settle`. Width stays `min(720px, 100% - 2 × frame-margin)`. |
| Mic button | Translates with the composer (they are siblings in the stack) from `bottom: 29%` to conversation-view position (above the composer) over `--d-6` `--e-settle`. |
| First founder message | Fades in at its position in the conversation column at opacity `0 → 1` over `--d-5` `--e-settle`, beginning after the greeting has fully faded (at `--d-3`). |
| Conversation column scroll area | Fades in at opacity `0 → 1` over `--d-5` `--e-settle`, simultaneous with first founder message. |

After the transition completes, the greeting, presence line, and footer hint
DOM elements are `display: none` for the session's duration. They do not return
until a new session initialises.

**Reduced-motion endpoint:** greeting and presence line opacity `1 → 0` at
`--d-1`. All other transitions collapse to `--d-1` opacity only. No translate
animates.

---

## 4.2 · Founder messages

Founder messages are right-aligned. They represent the founder's voice, their
intent, their words — they come from the founder's side of the relationship.

```css
.founder-message {
  display: flex;
  justify-content: flex-end;
  margin-bottom: var(--sp-5);          /* 24px between messages */
}

.founder-message__bubble {
  max-width: 480px;                     /* 480px = 2/3 of 720px column */
  background: var(--c-raise-2);
  border-radius: var(--r-2);            /* 8px */
  border: 1px solid var(--c-hair-soft);
  padding: var(--sp-4) var(--sp-5);    /* 16px 24px */
  font-size: var(--t-body-size);        /* 15px */
  line-height: var(--t-body-lh);        /* 24px */
  font-weight: var(--t-body-weight);    /* 400 */
  font-family: var(--font-text);
  color: var(--c-ink);
  text-align: left;                     /* left-aligned text inside right-aligned bubble */
}
```

**Why `--c-raise-2` background:** the founder's bubble needs to read against
both the tree and Somesh's flush-left prose. `--c-raise-2` provides enough
surface differentiation without creating a heavy contrast block that fragments
the page. It is understated — the bubble is a container, not a highlight.

**Why `--r-2` (8px):** premium reads as nearly square (`00_TOKENS §10.4`). A
rounder bubble would feel like a consumer messaging app. `8px` gives enough
softening to read as a bubble without the bubble form dominating.

**Timestamp:**

```css
.founder-message__time {
  font: var(--t-mono);                  /* 12px / 20px */
  color: var(--c-ink-4);
  margin-top: var(--sp-2);             /* 8px */
  text-align: right;
  font-variant-numeric: tabular-nums;
}
```

Timestamps use `HH:MM` format (24-hour, no seconds). They appear below the
bubble, right-aligned, always present. They are not hover-revealed — a founder
reviewing history should not need to hover to know when something was said.

**Long founder messages:** a message that would exceed `6 × 24px = 144px`
height (6 body lines) renders fully without truncation. There is no
"show more" on the founder's own messages. The founder knows what they said.
Long messages scroll with the page.

---

## 4.3 · Somesh messages

Somesh is not a bubble with an avatar. He has no visual container in the way
the founder's messages have a container. His responses are **flush-left prose**
with a left-edge hairline as the sole spatial marker.

**Rationale:** a bubble implies an exchange between two entities of equal
visual weight competing in a feed. Somesh is not competing — he is responding
to the founder's world. The hairline reads as a stage mark, not a box. It is
present enough to anchor the text's left edge and indicate "this is Somesh
speaking" without asserting visual dominance. The tree is already Somesh's
mark; his conversation contributions need not also be boxed.

```css
.somesh-message {
  display: flex;
  flex-direction: row;
  align-items: flex-start;
  gap: var(--sp-5);                     /* 24px between hairline and text */
  margin-bottom: var(--sp-5);           /* 24px between message groups */
  padding-left: 0;
}

.somesh-message__hairline {
  flex-shrink: 0;
  width: 1.5px;
  min-height: 100%;                     /* stretches to match text block height */
  background: var(--s-live);
  border-radius: var(--r-0);            /* square cap */
  opacity: 0.6;
}

.somesh-message__body {
  flex: 1;
  max-width: 100%;
}
```

**Typography scale decision:**

Somesh's responses fall into two scales based on character count of the final
delivered text:

| Length threshold | Scale | Token | Rationale |
|---|---|---|---|
| ≤ 240 characters | Speech scale | `--t-speech` (28px / 40px, weight 300) | Short replies are more like a voice — large, airy, present. They are the conversational mode and should feel spoken. |
| > 240 characters | Body scale | `--t-body` (15px / 24px, weight 400) | Longer replies are more like writing — analytical, structured, dense. They require a reading scale, not a speech scale. |

**Why 240 characters:** at `--t-speech`, a 240-character passage fills roughly
4 lines at 720px column width (approximately 60ch per line). Past that, reading
long text at 28px becomes fatiguing and takes up disproportionate screen
height. At `--t-body`, 240 characters fills 3 compact lines.

The scale decision is made once when the **final** text is delivered. It does
not change mid-render.

```css
.somesh-message__body[data-length="short"] {
  font-size: var(--t-speech-size);
  line-height: var(--t-speech-lh);
  font-weight: var(--t-speech-weight);
  font-family: var(--font-display);    /* Inter Tight for speech scale */
  color: var(--c-ink);
  letter-spacing: var(--t-speech-lh);  /* −0.015em tracking */
}

.somesh-message__body[data-length="long"] {
  font-size: var(--t-body-size);
  line-height: var(--t-body-lh);
  font-weight: var(--t-body-weight);
  font-family: var(--font-text);       /* Inter for body scale */
  color: var(--c-ink);
}
```

The `data-length` attribute is `"short"` when character count ≤ 240 and
`"long"` when > 240. Set when the final text is committed.

**Hairline in light theme:** same `--s-live` at 0.6 opacity; the light-theme
value of `--s-live` is `#1C7FB8`, which provides sufficient contrast on the
warm paper ground.

---

## 4.4 · Long replies

A long reply is any Somesh response whose rendered block height exceeds
`480px` (approximately 20 lines of `--t-body`).

### Progressive disclosure

Long replies do **not** collapse behind a "show more" toggle by default. The
product's feel is of a considered response deserving full reading, not a
summary to be expanded. However, if the rendered height exceeds `480px`:

The reply renders in full. The scroll view auto-scrolls to the **top** of the
Somesh message block (not the bottom), so the founder reads from the beginning.
This is the "long reply anchor" behaviour.

**Scroll anchoring for long replies:**

```js
// When a Somesh message is delivered and its height > 480px:
someshBlock.scrollIntoView({ behavior: 'smooth', block: 'start' });
```

Use `block: 'start'` so the top of the reply aligns with the top of the scroll
viewport (offset by `--sp-8` top padding). The founder reads from the
beginning.

### Reading-position preservation

Once the founder scrolls manually during a long reply (any scroll event whose
`deltaY > 0` is user-originated), auto-scroll for subsequent streaming tokens
is paused. The reading-guard threshold is **80px from the bottom of the scroll
container**. If the founder scrolls to within 80px of the bottom, auto-scroll
resumes.

This is the same guard as specified in §4.8 (scrollable history). For long
in-progress replies, the same guard applies during streaming.

---

## 4.5 · Rich content

### Tables

Tables appear in Somesh messages when the runtime delivers structured data.
They are not founder-created.

```css
.somesh-table {
  width: 100%;
  border-collapse: collapse;
  margin: var(--sp-4) 0;               /* 16px above and below */
  font-size: var(--t-body-sm-size);    /* 13px */
  line-height: var(--t-body-sm-lh);    /* 20px */
  font-family: var(--font-text);
}

.somesh-table thead th {
  border-bottom: 1px solid var(--c-hair);
  padding: var(--sp-2) var(--sp-3);    /* 8px 12px */
  text-align: left;
  font-size: var(--t-label-size);      /* 11px */
  font-weight: var(--t-label-weight);  /* 500 */
  letter-spacing: var(--t-label-track);/* 0.14em */
  text-transform: uppercase;
  color: var(--c-ink-3);
}

.somesh-table td {
  padding: var(--sp-2) var(--sp-3);
  border-bottom: 1px solid var(--c-hair-soft);
  color: var(--c-ink);
  vertical-align: top;
}

.somesh-table tbody tr:last-child td {
  border-bottom: none;
}
```

**Numeric columns:** any `td` containing only numeric content (digits,
decimal points, commas, currency symbols, percent signs — no letters) receives:

```css
td[data-numeric] {
  text-align: right;
  font-family: var(--font-mono);       /* IBM Plex Mono */
  font-size: var(--t-mono-size);       /* 12px */
  font-variant-numeric: tabular-nums;
}
```

The `data-numeric` attribute is set by the rendering layer after inspecting
cell content. Alignment is right; this is not optional — numeric columns that
are left-aligned are unreadable when comparing values.

**Row separators:** `1px solid var(--c-hair-soft)` between body rows. Header
separator: `1px solid var(--c-hair)` (stronger). No alternating row fills —
they create visual noise against the tree background.

**Overflow behaviour:** tables that exceed the column width (`720px`) scroll
horizontally within a scroll container:

```css
.somesh-table-wrap {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  border-radius: var(--r-1);
}
```

The scroll container has no visible scrollbar unless hovered. On hover, a `2px`
thumb in `var(--c-hair)` appears. No horizontal scroll affordance beyond the
natural scroll shadow (a `4px` gradient fade on the right edge using
`--c-ground` to `transparent`).

### Charts

**Allowed chart types: line and bar only.**

**Rationale for this restriction:** the product's conversation column is 720px
wide. Pie charts are unreadable at this width for more than 5 segments. Scatter
plots require hover interaction to be meaningful — a conversation surface is
not an analytics dashboard. Treemaps, heatmaps, and area charts are excluded
for the same reason. Line charts answer "how did this change?" Bar charts answer
"how do these compare?" These are the two questions a founder most frequently
asks in a conversational context.

```css
.somesh-chart {
  width: 100%;
  height: 240px;                        /* fixed height for all charts */
  margin: var(--sp-4) 0;
  border-radius: var(--r-2);
  background: var(--c-raise-1);
  padding: var(--sp-4);
}
```

**Axes and gridlines:**

```css
/* gridlines */
.chart-gridline {
  stroke: var(--c-hair-soft);
  stroke-width: 1px;
}

/* axis labels */
.chart-axis-label {
  font-family: var(--font-mono);
  font-size: var(--t-mono-size);        /* 12px */
  fill: var(--c-ink-3);
}

/* axis line */
.chart-axis-line {
  stroke: var(--c-hair);
  stroke-width: 1px;
}
```

**Colour rules:** charts use signal colours semantically. Data series are
coloured as:

| Series role | Colour | Condition |
|---|---|---|
| Primary / only series | `--s-live` | Always |
| Positive / goal / success | `--s-settled` | When semantic meaning is confirmed |
| Warning / attention | `--s-attend` | When semantic meaning is confirmed |
| Risk / loss | `--s-risk` | When semantic meaning is confirmed |

`--s-bloom` is forbidden in charts. It is ceremonial only.

If a chart has more series than there are signal colours (i.e., 5+ series),
the runtime must aggregate or group. The UI does not invent additional colours.
A chart exceeding four data series is a specification error in the runtime's
response.

**What is forbidden in charts:**

- Drop shadows
- 3D effects
- Gradient fills on bars or lines
- Animation on data point entry (reduced-motion applies globally; on standard
  motion, bars may enter from their baseline over `--d-5` `--e-settle` once
  only — no looping)
- Pie, donut, radar, scatter, heatmap, treemap types
- Legend with more than 4 items
- Tooltips that require hover to see key data (use axis labels to make data
  self-evident)

### Code blocks

Code appears in Somesh messages when the runtime delivers runnable or
illustrative code.

```css
.somesh-code {
  display: block;
  font-family: var(--font-mono);       /* IBM Plex Mono */
  font-size: var(--t-mono-size);       /* 12px */
  line-height: var(--t-mono-lh);       /* 20px */
  background: var(--c-raise-2);
  border: 1px solid var(--c-hair-soft);
  border-radius: var(--r-1);           /* 4px */
  padding: var(--sp-4) var(--sp-5);    /* 16px 24px */
  margin: var(--sp-3) 0;              /* 12px above and below */
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  color: var(--c-ink);
  white-space: pre;
  tab-size: 2;
  position: relative;                   /* anchors the copy affordance */
}
```

**Syntax highlighting colour policy:**

Only four colour roles are used, mapped to signal tokens:

| Token class | Colour | Examples |
|---|---|---|
| Keywords, control flow | `var(--s-live)` | `if`, `for`, `return`, `function` |
| Strings, literals | `var(--s-settled)` | `"hello"`, `'world'`, template literals |
| Comments | `var(--c-ink-3)` | `// comment`, `/* block */` |
| Everything else | `var(--c-ink)` | identifiers, operators, numbers, punctuation |

**Why only four roles:** more colour differentiation in code creates a
Christmas-tree effect that competes visually with the tree and fragments
readability. The four roles cover the reading-critical distinctions (control
flow, data, comment, base text) without adding noise. Numbers, operators, and
type annotations all fall to `--c-ink` because a founder reading code needs to
distinguish structure (keywords) from content (strings) from context (comments)
— the rest is noise at this granularity.

`--s-attend` and `--s-risk` are not used for syntax highlighting. They are
reserved for state communication.

**Copy affordance:**

```css
.somesh-code__copy {
  position: absolute;
  top: var(--sp-2);                    /* 8px */
  right: var(--sp-2);                  /* 8px */
  height: 28px;
  padding: 0 var(--sp-3);             /* 0 12px */
  border-radius: var(--r-1);
  background: var(--c-raise-2);
  border: 1px solid var(--c-hair-soft);
  font: var(--t-label);
  color: var(--c-ink-3);
  cursor: pointer;
  opacity: 0;
  transition: opacity var(--d-1) var(--e-settle);
}

.somesh-code:hover .somesh-code__copy {
  opacity: 1;
}
```

Copy button is visible on hover of the code block. On click, the block's text
content is copied to the clipboard. The button text is `COPY`. After successful
copy, text changes to `COPIED` and colour changes to `var(--s-settled)` for
`--d-5` (420ms), then reverts.

On failed copy: text changes to `FAILED` in `var(--s-risk)` for `--d-5`, then
reverts. No toast, no banner — the feedback is local to the button.

---

## 4.6 · Thinking indication

The thinking indicator appears when the runtime is genuinely working on a
response. It must not appear for fast operations.

**Latency threshold:** the indicator is shown only if the runtime has not
begun delivering a response within **400ms** of message submission. For
responses that arrive within 400ms, nothing appears. This prevents a
flickering indicator on fast round-trips.

```js
let thinkingTimer = setTimeout(() => {
  showThinkingIndicator();
}, 400);  // --d-gate: 400ms (see TOKEN ADDITION REQUEST in 03_VOICE_EXPERIENCE)

// On first token received:
clearTimeout(thinkingTimer);
hideThinkingIndicator();
```

### What it is

The thinking indicator is a single horizontal `--t-label` line in
`--c-ink-3`, placed where the next Somesh message will begin (i.e., at the
left edge of the conversation column, at the same horizontal position as the
Somesh hairline):

```css
.thinking-indicator {
  display: flex;
  align-items: center;
  gap: var(--sp-4);                    /* 16px */
  height: 40px;
  padding-left: 0;
  margin-bottom: var(--sp-5);
  opacity: 0;
  transition: opacity var(--d-3) var(--e-settle);
}

.thinking-indicator__hairline {
  flex-shrink: 0;
  width: 1.5px;
  height: 40px;
  background: var(--s-live);
  opacity: 0.3;                        /* dimmer than active Somesh hairline (0.6) */
  border-radius: var(--r-0);
}

.thinking-indicator__label {
  font-size: var(--t-label-size);      /* 11px */
  font-weight: var(--t-label-weight);  /* 500 */
  letter-spacing: var(--t-label-track);/* 0.14em */
  text-transform: uppercase;
  color: var(--c-ink-3);
}
```

The `__label` text is a single word: `THINKING`. It does not change. It does
not animate. It does not say "working…" or "one moment" or any filler phrase.

**Why this instead of dots:** three bouncing dots are a lie in two ways. They
imply continuous activity (the bouncing) when the system may be waiting on a
network call. And they are borrowed visual language from consumer messaging
apps. The hairline-with-label reads as the same visual language as a Somesh
message — it is a placeholder where the message will be — which is honest. The
dimmer hairline (0.3 opacity vs 0.6) signals incompleteness.

**Why the tree drives the deeper thinking signal:** the tree transitions to its
`thinking` state (bloom at 0.85, see `01_FOUNDER_SURFACE §1.3`) when Somesh
is working. This is the primary signal — a living system visibly concentrating.
The text indicator is the secondary, verbal confirmation for founders who may
not be watching the tree.

**Transition in:** `opacity 0 → 1` at `--d-3` `--e-settle`, triggered after
400ms.

**Transition out:** when the first token arrives, opacity `1 → 0` at `--d-2`
`--e-exit`. The indicator fades as the Somesh message hairline fades in at full
opacity. They do not overlap.

**Reduced-motion endpoint:** opacity change only. No other animation.

---

## 4.7 · Typing indication

**Decision: no visible typing indicator for the founder's own typing.**

**Rationale:** the founder sees their own keystrokes appear in the composer in
real time. An additional typing indicator (e.g., a "you are typing" label)
would be redundant self-narration. It adds noise without adding information.
The composer's text is the typing indicator — it is already visible, immediate,
and accurate.

**What the founder sees while typing:**

The composer's text cursor and the growing text content in the composer are
sufficient. The mic button stays `armed` (or its current state) with its label
unchanged. Nothing in the conversation column changes while the founder types.

**Distinction from Somesh's thinking state:**

| Condition | Where it appears | What is shown |
|---|---|---|
| Founder typing | In the composer (bottom of screen) | Cursor + text content — no label |
| Somesh thinking | In the conversation column (where the reply will be) | Dimmed hairline + `THINKING` label |

The two conditions use different screen regions and different visual languages.
There is no ambiguity about which entity is active.

---

## 4.8 · Scrollable history

### Scroll behaviour

The conversation scroll container uses native scrolling with
`scroll-behavior: smooth`. Scroll snapping is not used — messages are prose,
not cards, and snapping to message boundaries would interrupt natural reading.

```css
.conversation-scroll {
  scroll-behavior: smooth;
  scroll-padding-top: var(--sp-8);     /* 64px — respects top chrome */
}
```

### Auto-scroll and reading guard

When a new message arrives (founder or Somesh), the scroll view auto-scrolls
to show it — **unless the founder has scrolled up into history**.

**Reading guard threshold:** if the scroll position is more than **80px** above
the scroll container's bottom (i.e., `scrollHeight - scrollTop - clientHeight >
80`), auto-scroll is paused. The founder is reading history.

```js
function shouldAutoScroll(container) {
  const distanceFromBottom =
    container.scrollHeight - container.scrollTop - container.clientHeight;
  return distanceFromBottom <= 80;
}
```

When auto-scroll is paused and a new message arrives, the "new below"
affordance appears (see below).

When the founder scrolls to within 80px of the bottom (manually), auto-scroll
resumes. The next arriving message auto-scrolls normally.

### "New below" affordance

When a message arrives while auto-scroll is paused:

```css
.new-below {
  position: fixed;
  left: 50%;
  transform: translateX(-50%);
  bottom: calc(var(--composer-height) + var(--sp-4));  /* above composer */
  height: 32px;
  padding: 0 var(--sp-4);
  border-radius: var(--r-1);
  background: var(--c-raise-3);
  border: 1px solid var(--c-hair);
  font: var(--t-label);
  color: var(--c-ink-2);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  opacity: 0;
  pointer-events: none;
  transition: opacity var(--d-3) var(--e-settle);
  z-index: var(--z-live);
}

.new-below.visible {
  opacity: 1;
  pointer-events: auto;
}
```

Content: a `chevron-down` icon (16×16) followed by `NEW MESSAGE`. On click,
scroll to bottom at `smooth` behaviour and auto-scroll resumes. The affordance
fades out as soon as the founder is within 80px of the bottom.

### Scrollbar styling

```css
.conversation-scroll::-webkit-scrollbar {
  width: 4px;
}
.conversation-scroll::-webkit-scrollbar-track {
  background: transparent;
}
.conversation-scroll::-webkit-scrollbar-thumb {
  background: var(--c-hair-soft);
  border-radius: var(--r-full);
}
.conversation-scroll::-webkit-scrollbar-thumb:hover {
  background: var(--c-hair);
}
```

Firefox:

```css
.conversation-scroll {
  scrollbar-width: thin;
  scrollbar-color: var(--c-hair-soft) transparent;
}
```

The scrollbar is `4px` wide — present but not conspicuous. It appears on hover
of the scroll container and during scroll events. Hidden at rest on webkit;
visible (thin) at rest on Firefox (native behaviour respected).

### Day dividers

When the conversation spans multiple calendar days, a day divider appears
between the last message of one day and the first of the next.

```css
.day-divider {
  display: flex;
  align-items: center;
  gap: var(--sp-4);
  margin: var(--sp-6) 0;              /* 32px above and below */
  color: var(--c-ink-4);
}

.day-divider__line {
  flex: 1;
  height: 1px;
  background: var(--c-hair-soft);
}

.day-divider__label {
  font: var(--t-mono);                /* 12px / 20px */
  color: var(--c-ink-4);
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}
```

Date format: `THURSDAY · 7 AUG 2025`. Day name in uppercase, `·` separator,
date in uppercase. Uses the founder's local timezone (not UTC).

**Today's divider** reads `TODAY ·` followed by the date only when it is not
the current calendar day — if the session spans midnight, "TODAY" refers to the
day the session was opened. If all messages are from the same day, no divider
is shown.

### Jump-to-latest

A `jump-to-latest` control lives at `position: fixed; bottom: composer-height +
sp-4; right: frame-margin`. It is visible only when the founder is more than
400px above the bottom of the scroll container.

```css
.jump-latest {
  position: fixed;
  bottom: calc(var(--composer-height) + var(--sp-4));
  right: var(--frame-margin-desktop);
  width: 36px;
  height: 36px;
  border-radius: var(--r-full);
  background: var(--c-raise-2);
  border: 1px solid var(--c-hair);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  opacity: 0;
  pointer-events: none;
  transition: opacity var(--d-3) var(--e-settle);
  z-index: var(--z-live);
}
```

Contains a `chevron-down` icon (16×16, `--c-ink-2`). On click, smooth-scrolls
to bottom. Distinct from "new below" (which is centred and labelled) because
jump-to-latest is a navigation affordance, not a notification — it is always at
the right margin, not in the content flow.

---

## 4.9 · Persistent conversations

### Session boundaries

Each session is a continuous period of engagement, separated by window close
or a configurable inactivity timeout (timeout value determined by runtime —
not specified here). Session boundaries are marked by a session divider in the
conversation scroll.

```css
.session-divider {
  display: flex;
  align-items: center;
  gap: var(--sp-4);
  margin: var(--sp-7) 0;              /* 48px above and below — more breathing room than day dividers */
}

.session-divider__line {
  flex: 1;
  height: 1px;
  background: var(--c-hair-soft);
}

.session-divider__label {
  font: var(--t-mono);
  color: var(--c-ink-3);
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}
```

Session divider label format: the relative time of the gap. Examples:
`3 HOURS AGO` · `YESTERDAY` · `2 WEEKS AGO` · `4 MONTHS AGO`.

For gaps less than 1 hour, no divider is shown — the conversation was
continuous enough that the break is imperceptible.

**Why relative time, not absolute timestamps on session dividers:** the founder
is interested in the flow of the relationship, not the log. "Yesterday" is more
meaningful than "06 AUG 2025 09:14". Absolute dates appear in the day
dividers; session dividers describe time as felt distance.

### How a returning founder re-enters

On window open, if prior history exists:

1. The tree assembles at its normal startup animation.
2. The greeting supplied by the runtime appears at `--t-greeting` (same home
   screen position).
3. The conversation column is loaded but **not scrolled into view** — the home
   screen appears first. The conversation column is already populated in the
   DOM, just below the fold.
4. If the founder speaks or types, the home-screen-to-conversation transition
   fires (§4.1) and the view scrolls to the bottom of the loaded history.

The founder always enters on the home screen, always sees Somesh's greeting,
and then drops into conversation naturally. They are never dropped mid-thread
cold.

### What is shown above the fold on first scroll

The conversation column scrolls into view with the **most recent exchange** at
the bottom and enough history to show the immediately preceding context above
it. The view is pre-scrolled to the bottom so the latest message is visible
within the scroll viewport.

### Initial load depth

The conversation column loads the **most recent 40 message blocks** on session
open. Presentation only — do not specify storage or retrieval. If fewer than 40
blocks exist, all are loaded.

Older history is loaded on scroll-up: when the founder scrolls to within
**160px** of the top of the loaded content, the next batch of 40 blocks is
appended above. A loading placeholder (§4.10, history-loading) appears during
the fetch.

No pagination UI. No "load more" button. History loads transparently on scroll,
anchoring the scroll position so the founder's reading position does not jump.

---

## 4.10 · Empty and degraded states

Each state is calm, clear, and gives the founder one obvious path forward. None
shows a technical error string.

### No history — first ever session

The home screen shows without a conversation column. The tree is in its
startup / `idle` state. The greeting (runtime-supplied) is present. The mic
is `armed`. The footer hint reads `SPACE TO SPEAK · TYPE TO WRITE`.

No empty-state illustration. No "start your journey" call to action. The
product does not prompt — the founder will speak or type when ready.

**After the first message is sent**, the conversation column appears via the
standard home-screen-to-conversation transition (§4.1).

### History failed to load

The conversation column is present but the history batch failed to fetch.

```css
.history-load-error {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 80px;
  font: var(--t-body-sm);
  color: var(--c-ink-3);
}
```

Copy: `"Previous conversations are temporarily unavailable."`

One line, centred in the column, at the top of the conversation area. No icon,
no triangle, no retry button (the batch will be retried automatically). If the
load succeeds on retry, this message is replaced by the loaded history without
animation (instant swap).

**The conversation remains usable.** The founder can send new messages. Only
history is affected.

### A message that failed to send

The founder's message bubble receives an error treatment:

```css
.founder-message__bubble[data-state="failed"] {
  border-color: color-mix(in srgb, var(--s-risk) 40%, transparent);
  background: color-mix(in srgb, var(--s-risk) 8%, var(--c-raise-2));
}
```

Below the bubble, a `--t-body-sm` line in `--s-risk` reads:
`"Not sent — tap to retry"`. On mobile, tap; on desktop, click. The text is
interactive: clicking/tapping retries the send. On retry attempt, the error
treatment is removed and the bubble returns to normal styling.

If retry also fails, the same error treatment reappears. No maximum retry count
is enforced by the UI — the founder may retry as many times as they wish.

The failed message stays in position in the conversation. It is not removed
from the DOM. The founder can see what they tried to send.

### Loading older history (scroll-up batch)

When the founder has scrolled near the top and a batch of older history is
being fetched:

```css
.history-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 48px;
  font: var(--t-mono);
  color: var(--c-ink-4);
}
```

Copy: `LOADING`. One word. No animation, no dots. It appears and disappears. If
the load completes quickly (within 400ms), it never appears — same latency gate
as the thinking indicator (§4.6), using the same `setTimeout` pattern.

---

## TOKEN ADDITION REQUESTS

The following value is needed by this document and is absent from
`00_TOKENS.md`. It is also requested by `03_VOICE_EXPERIENCE.md`. Add once.

### ADDITION 1 — `--d-gate`

```css
--d-gate: 400ms;
/* Used for: thinking indicator delay gate (§4.6), history-loading gate (§4.10),
   voice-processing indicator delay (03_VOICE_EXPERIENCE §3.6).
   Do not use this token for transitions — only for JS timeout thresholds. */
```

Add to `00_TOKENS.md §10.5` with the comment above. It is not an animation
duration; it is a display latency gate. It belongs in the duration section
with this semantic note.

### ADDITION 2 — `--composer-height` JS layout variable

Same pattern as `--mic-top` / `--mic-bottom` in `03_VOICE_EXPERIENCE`. The JS
layout layer must set `--composer-height` on `:root` as the current rendered
height of the composer element, updated on resize and on composer
expand/collapse. Used by `§4.8` and `§4.10` for positioning fixed elements
above the composer.

This is a layout variable, not a design token, and should not be in
`00_TOKENS.md`. Document the contract in the engineering notes.
