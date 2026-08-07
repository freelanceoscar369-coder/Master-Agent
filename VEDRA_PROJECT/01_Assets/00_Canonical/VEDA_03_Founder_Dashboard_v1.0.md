# Kalpavriksha — Founder Dashboard UX & Interaction Spec v1

Experience design milestone 1: flow, screen states, presence model, voice model, motion spec, and open decisions.

## Product position

Kalpavriksha is a **personal AI executive**, not a chatbot and not a dashboard. The design consequence of that sentence is specific and it is the spine of this spec:

- A chatbot **waits for a prompt**. Kalpavriksha **opens with a report** — it has already been working.
- A dashboard **shows you data**. Kalpavriksha **shows you decisions** — data is the evidence, not the product.
- A productivity app **asks you to do things**. Kalpavriksha **asks permission to do things**.

Every screen is judged against four feelings: *the AI was working while I was away*, *the AI understands my company*, *the AI waits for my decisions*, *the AI is my executive partner*.

**Proportions.** 70% NASA mission control (trust through precision, alignment, telemetry), 20% Jarvis (living presence, elegant motion, personality in language), 10% Bloomberg (consequence, cost, decision framing). The Bloomberg 10% is deliberately the smallest and the most load-bearing — it is what turns awe into retention.

## Where the brief was challenged

Six positions taken against the original brief. Each is a product argument, not a taste preference.

**1. Swiss Grid discipline, inverted surface.** The pinned skill's canon is white paper, near-black ink, Swiss red — the exact opposite of a cinematic dark environment. Following it literally would have produced a Müller-Brockmann report. What transfers is the *structure*: a 12-column modular grid, 8px baseline, subgrid bands so every card snaps to a column line, a toggleable overlay, and optical ink alignment on display type. NASA mission control is itself rigorously gridded — telemetry earns trust by being visibly aligned. Press **G** anywhere in the concept to see the grid the whole thing is built on.

**2. The tree is state, not scenery.** The neural tree earns roughly eight seconds of awe on arrival. It does not earn a permanent half-screen. After the greeting it demotes to a 56px sigil in the left rail, running the same particle engine, reporting system state: *idle / thinking / speaking / awaiting you*. A particle organism that never gets out of the way becomes a screensaver the founder resents by day four. Demoting it also converts decoration into information — the founder learns to read the sigil the way a pilot reads an attitude indicator.

**3. Voice must be unlocked by a gesture.** Every browser blocks unprompted audio. A greeting that silently fails to speak makes the AI feel broken on the very first turn — the worst possible first impression for a product selling *aliveness*. The arrival screen therefore opens with the tree assembling and a single gesture ("Wake Kalpavriksha", or any keypress) that unlocks audio and starts the synced typed + spoken greeting. The permission grant is disguised as ceremony. Typing remains the source of truth; speech is a layer, always skippable.

**4. The idle prompt should be ambient, not needy.** "What's on your mind today?" spoken at a founder mid-thought reads as an assistant interrupting a CEO. Instead, at 18 seconds the three choices fade up silently in the lower right with the label *Kalpavriksha is listening* — presence without interrogation. Voice only re-engages if the founder has been idle and then moves the cursor: attention returned.

**5. The quiet day is a required state.** The brief specifies a rich "while you were away" summary. It does not specify what happens on the day nothing happened — which is where most AI-partner products die, because a wall of zeros reads as *the product is broken*. Kalpavriksha reports calm with the same conviction it reports activity: "Nothing needed you. That's the report." Six checks clean, zero awaiting you, burn on plan. Confident calm is a stronger trust signal than a wall of achievements.

**6. Approve / Discuss / Reject is not enough.** A founder cannot decide without knowing what changes, what it costs, what happens if they do nothing, and whether it is reversible. Every approval card answers those four before asking for a verdict. This is the Bloomberg 10% doing real work — and it is the single highest-leverage design decision in the product, because approval throughput is the metric the whole system is optimising.

## Core experience flow

```
ARRIVE
  └ dark field · tree particles converge from below (2.4s)
  └ "Wake Kalpavriksha" · gesture unlocks audio
     └ typed + spoken greeting, synced   "Good evening, Onkar."
     └ subline lands                      "I've been working. Four things need you."
     └ rail materialises · tree demotes to sigil
        └ [18s idle] three choices fade up, silent
           ├ Executive Brief    → screen 02
           ├ Continue Conversation → screen 05
           └ Live Dashboard     → screen 03
```

**Time-of-day greeting** is computed locally: <12:00 morning, <17:00 afternoon, else evening. The greeting is the only sentence the founder hears before information — it must be short enough that voice and typing finish together (~1.8s).

**Return-visit variation matters.** Same-day return should not replay the full assembly; the tree is already grown, greeting shortens to "Back, Onkar. One thing moved." Full ceremony is for the first session of a day. (Not built in v1 concept — flagged as a v1.1 state.)

## Screen specifications

**01 · Founder Arrival.** Full-bleed near-black with a radial lift at the centre. Living neural tree in canvas particles. Top-left wordmark, top-right system line (session ID, IST clock, uptime, ALL SYSTEMS NOMINAL). Centre: greeting with a cyan cursor. Bottom-left: voice toggle with a live level meter that animates only while speaking. Bottom-right: the ambient choice tray. No navigation chrome until the greeting completes — the first eight seconds have exactly one affordance.

**02 · Executive Brief.** Headline row of four large numerals on the 12-column grid: 12 completed / 3 improved / 2 recommendations / 1 approval — colour-coded green, cyan, neutral, amber. Below, mission cards on columns 1–9 and an intelligence stack on 9–13 (productivity score 87/100, one open risk with an inline "Draft it" action). The **quiet-day variant** is shown as a second state on the same screen. Rule: the founder must be able to answer "is today calm?" in under two seconds, before reading a single sentence.

**03 · Mission Control.** Operational telemetry. Active missions with live progress bars and ETAs, a held mission showing how long it has been blocked, then completed missions. Right column: a system-state readout (autonomy level, active/queued/held counts) above a vertical timeline with state-coloured nodes. This is the screen that must read like an instrument panel — mono type is doing more work here than the palette.

**04 · Approval Center.** The revenue screen. Three approval types are specified: permission (Voice Executive Mode), financial (Datastack renewal, ₹18.4L/yr, 22% above market), strategic (unblock the infra decision). Each carries the AI's recommendation in a bordered rationale block plus a 2×2 consequence matrix — *what changes / cost / if you do nothing / reversible*. Actions: Approve, Discuss, Reject. Approve resolves the card in place and pulses the sigil to *Acting*; Reject records a graceful decline ("noted, I won't raise it again this quarter"); Discuss jumps to Conversation Mode with the item in context. Right column tracks decision velocity — median 26m, down from 3h 10m.

**05 · Conversation Mode.** Conversation is a *state*, not a page. The dashboard dims to ~55% and holds the right four columns; the exchange takes columns 1–9. Context cards for the held approval and the running mission stay visible throughout. Composer with a pulsing mic ring, placeholder "Speak, or type to Kalpavriksha…", ⌘K. Full-screen chat is what makes an AI feel like a chatbot; keeping telemetry alive in the periphery is what keeps it mission control.

## Design system

**Palette — colour carries meaning, never mood.**

| Token | Value | Meaning |
|---|---|---|
| void | `#05070A` | primary field |
| deep | `#080B10` | alternating spread |
| ink / ink-2 / ink-3 | `#E9EFF5` / `#9FB0BF` / `#63727F` | text hierarchy |
| live | `#7FD3FF` | system is alive / AI presence |
| needs you | `#FFB454` | blocked on a human |
| done | `#63E6A8` | completed |
| risk | `#FF6B6B` | open risk |

Nothing else is coloured. No gradients as decoration, no neon, no glow for its own sake. Glass panels are `rgba(255,255,255,.028)` with a hairline `rgba(150,190,220,.16)` and a 3.5% top-edge highlight — never blurred to mush.

**Type.** Inter for display and body; IBM Plex Mono for mission IDs, timestamps, labels, folios and telemetry. The mono is the single strongest "instrument, not app" signal in the system — stronger than the dark palette. Scale: 76/80 masthead · 44/48 h1 · 27/32 h2 · 19/24 h3 · 15/24 body · 11/16 kicker. Every line-height is a px multiple of 8. Flush-left, ragged-right, always. Key data is set as large numerals.

**Grid.** 12 columns · 8px baseline · 24px leading · 24px gutter · 48px margin · 1440px max width. All elements placed by column *line* via subgrid bands. Verified: 37 placements, all on valid lines; zero off-baseline vertical spacing.

**Component anatomy.** Panel padding is 23px (+1px border = 24, one leading unit) or 31px (= 32). Buttons resolve to 48px height. Tags are 16px-line mono caps in a hairline box. Progress bars are 2px. Timeline nodes are 7px with a 4px halo when live.

## Motion specification

| Moment | Duration | Easing | Notes |
|---|---|---|---|
| Tree assemble | 2400ms | `cubic-bezier(.16,1,.3,1)` | particles rise from below the fold and converge on branch targets; per-particle delay 0–550ms |
| Breathe idle | 6s loop | sine | ±1.2% scale — must be barely perceptible |
| Pulse travel | 4.5s loop | linear | a brightness wave from root to canopy; the "heartbeat" |
| Thinking | 1.2s | sine | drift amplitude ×3, particles loosen and reorganise |
| Greeting type | 38ms/char | — | speech starts at char 0; both land within ~150ms |
| Cursor blink | 1.05s | steps(1) | cyan, removed 420ms after the line completes |
| Tray fade-up | 900ms | ease | at 18s idle, translateY 10px → 0 |
| Card enter | 420ms | ease-out | 60ms stagger, rise 12px |
| Approval settle | 540ms | slight overshoot | conveys mass — a decision has weight |
| Sigil state change | 600ms | ease | colour + amplitude shift |

**Rules.** Nothing bounces. Nothing spins. Motion communicates state change and mass, never delight for its own sake. A founder must never wait on an animation to read a number. `prefers-reduced-motion` renders the tree fully assembled and static, and disables all transitions.

**Performance budget.** Canvas 2D, ~2400 particles on the arrival field and ~260 on the sigil, scaled by viewport. Canvas 2D beats WebGL here: no library dependency, predictable memory, and it degrades gracefully. Target 60fps on an M1 MacBook Air and ≥30fps on integrated graphics. If the field drops below budget, reduce particle count before reducing motion quality — density is the illusion.

## Interaction model

**Presence states (the sigil).** `idle` — slow breathe, low amplitude. `thinking` — particles loosen and reorganise, amplitude ×3. `speaking` — synced with the voice level meter. `awaiting` — amber tint, a slower and heavier pulse. The founder should be able to read the system's state from peripheral vision alone.

**Voice model.** Text is the source of truth; voice is a layer over it. Whatever is spoken is typed; whatever is typed can be spoken back. Voice is unlocked by the wake gesture, toggleable at all times, and cancels instantly on toggle-off. The concept demo uses the browser speech engine — production would use a real TTS with a deliberately chosen executive voice (calm, mid-low pitch, ~0.94 rate, British or Indian English).

**Attention model.** Kalpavriksha never interrupts. It surfaces. Choices fade up silently at 18s; voice re-engages only on cursor movement after idle. There are no toast notifications and no modal dialogs anywhere in the system — an executive partner does not throw dialogs at you.

**Navigation.** The left rail is 88px, holds the sigil, numbered screen indices, and the founder's initial with the local clock. Clicking the sigil always returns to arrival. `G` toggles the grid overlay. `⌘K` focuses the composer from anywhere.

**Language rules for the AI.** First person, never "the system". Short declaratives. Leads with the conclusion, then the evidence. Quantifies whenever possible. Never apologises for doing its job. Never uses exclamation marks. Says "I'd open at ₹13.8L and settle at ₹14.5L" — an opinion with a number — rather than "here are some considerations." The voice is the product; a hedging AI executive is not an executive.

## Resolved · Decision 1: the approval queue at volume

Open decision 1 is now designed. See **Screen 04b — Approval Queue at Volume**.

### The frame

At five open items the Approval Center is a list. At twenty it is an inbox, and an inbox turns an executive partner back into a to-do app — the founder starts triaging the AI instead of the business. So the design goal is inverted from every inbox ever built: **success is the queue shrinking**, and the headline metric is not throughput but the share of decisions Kalpavriksha stops needing to ask about.

### Three principles

1. **Rank by consequence, never by time.** A chronological queue makes the founder do the prioritisation the AI should have done. Ranking function: `irreversibility × log(exposure) × deadline_proximity × novelty`, and it is inspectable on request — opaque prioritisation is the fastest way to lose trust in a queue.
2. **Delegating judgment beats delegating tasks.** Batching is a bandage; the cure is a standing rule. The founder teaches a decision boundary once and never sees that class of request again.
3. **Silence must have a stated default.** Every item declares what happens if the founder never responds ("if I don't hear from you by Thursday 18:00, I'll let it renew"). Pre-committed defaults make ignoring the queue a decision rather than a debt.

### Three tiers

| Tier | Contents | Interaction |
|---|---|---|
| **Needs you** | Irreversible, novel, high exposure | Full consequence card, individual verdict. **Never batches** — no checkboxes at any volume. |
| **Sweep** | Routine, reversible, precedent exists | Dense rows, multi-select, running aggregate exposure, 60s undo. |
| **Auto-handled** | Covered by a standing rule | Shown as a **receipt**, not a request. |

Read as a ratio, not a total: 2 / 9 / 14 is a healthy day; 12 / 9 / 4 means the rules aren't working.

### Standing rules — proposed, never authored

A settings page for approval rules is where rules go to die; nobody writes policy preemptively. Kalpavriksha instead watches its own approval history and asks once it has earned the right: *"You've approved 9 of 9 tooling renewals under ₹50,000. Want me to stop asking?"* — with the evidence strip, the median time-to-approve, and the one rejection that sets the ceiling.

**This is the emotional peak of the product** — not the neural tree. The moment the AI proposes a boundary from observed behaviour is when the founder feels accompanied rather than assisted.

Rule anatomy is non-negotiable, five parts: **trigger** (narrow and boring) · **blast radius** (a cumulative cap, not just per-item — a per-item cap alone is how you lose ₹8L in forty ₹20K approvals) · **never-clause** (explicit exclusions, always displayed) · **trial period** (30 days; rules expire unless renewed) · **receipt** (every firing logged and reviewable).

### Mute, snooze, delegate

Snooze defers with a re-surface time. Mute silences a class for a period but never hides the receipt. **Delegate routes to a human** — the most under-designed option in every approval product. A founder at twenty items a day usually shouldn't be the approver at all; invoices over ₹2L go to the CFO, seats to the Head of Eng.

### Trust anchors

Undo windows are graded by who was in the room: batch sweep 60s, single approval 30s, **rule firing 24h** (longest, precisely because the founder wasn't present), irreversible actions none. A single **Pause all autonomy** control makes every rule dormant instantly — Kalpavriksha keeps working and keeps queueing, it just stops deciding. This also makes "AUTONOMY · LEVEL 3" on Mission Control real: level is derived from active rules, and it collapses to zero in one gesture. *(Partially resolves open decision 4.)*

### The headline metric

**Autonomy ratio** — the share of decisions handled by rule versus escalated. This line going up is the product working. If it flattens, Kalpavriksha has stopped learning the founder's judgment, and that is a churn signal months before the founder can articulate it.

### Deliberately refused

No unread badges or counts (a number on a nav item is an obligation — Kalpavriksha says "2 need you," never "23 unread"). No inbox-zero gamification. No bulk-approve on tier 1. No silent rule creation from inferred consent. No settings page called "Approval Rules" — rules live where decisions live.

### It's one screen, not two

Screen 04 doesn't fork. Below ~5 open items it renders as full consequence cards; at 6–15 tiers appear and the sweep list densifies; past 16 rule proposals start surfacing. The founder never learns two interfaces — and the transition is itself information: **the day the tiers appear is the day the founder learns they're becoming the bottleneck.**


## Screen 01 v2 — the first screen, rebuilt on the philosophy

**Governing rule, accepted:** the AI is the interface. The dashboard exists only to explain what the AI has done and where human judgment is still required.

Applied literally, that rule deletes most of Screen 01 v1. The test run against every element: *does this explain what the AI did, or does it ask for human judgment?* If neither — deleted, not moved.

### Four deletions from v1

- **The stat row.** "12 completed / 3 improved / 2 recommendations / 1 approval." Four large numerals. But "12 completed" neither explains what was done nor requires judgment — it is vanity telemetry dressed as mission control. It collapses to one line: *12 handled without you.*
- **The greeting as its own beat.** "Good evening, Onkar." full stop spent the most valuable moment in the product on nothing. The greeting now carries payload in the same breath: *"Two things need you. This one first — it expires Friday."*
- **Scroll.** V1 was ceremony, then you scrolled into a dashboard. If the first screen scrolls, it is a dashboard again. V2 fits one viewport and **empties as you work**.
- **Navigation.** No rail, no menu, no tabs. Three lowercase doorways at the bottom edge. You go to Mission Control when you *don't trust the summary* — so its prominence should be inversely proportional to how well the AI is doing its job.

### Three elements remain

**1 · The voice.** The AI speaks first, in prose, at 38px — a sentence with a subject and a verb, not a card. Prose is the only format that can carry judgment; a metric cannot say "I'd open at ₹13.8L."

**2 · The decision.** One decision, in full, with its recommendation and consequence framing — not a link to an approval centre. Where judgment is required *is* the product, so it gets the largest object on screen. **One at a time, never a list**: a chief of staff says "this one first, here's why." The consequence ranking from Screen 04b supplies the order; resolving an item raises the next into the same slot.

**3 · The receipt.** Everything done, collapsed to two numbers, expandable, deliberately low-contrast. Explaining what it did is an obligation, not a boast — available, not loud.

### The trust moment

Inside the receipt, one item is flagged unprompted: *"I approved the Sentry upgrade (₹7,200) under your tooling rule — three days after a similar one. The rule allowed it, but the pattern might not be what you meant. Want me to narrow it to once a month?"*

Nothing else in this product does more for trust. An AI that reports only successes is a marketing surface. One that surfaces its own borderline calls — when nobody would have caught it — is a colleague. It also closes the loop with the standing-rules system: the AI's self-audit is the primary mechanism by which rules get *tightened* rather than only loosened.

### The tree, reassigned

No longer ceremony that ends. It lives behind the words for the whole session, weighted to the left third, dimmed under the type. It tightens and warms toward amber when judgment is pending, and settles into a slower, cooler breathe when the screen is clear. The founder reads the system's state before reading a word. This also supersedes the v1 sigil for the first screen — the sigil remains correct for the denser interior screens.

### Success condition

Same inversion as the approval queue: **this screen should get emptier every month.** As standing rules accumulate, the left side shrinks and the right side grows, until the founder opens Kalpavriksha and reads *"Nothing needs you. Here's what I'm doing."* That is not a degraded state — that is the product having won.

### Risk accepted, stated openly

A screen this sparse can read as "the product doesn't do much" to someone who hasn't lived with it. Density signals value to a stranger; restraint signals value to an owner. This design optimises for the owner on day 200, which means **the sales demo should open on Mission Control, not this screen.** Worth deciding deliberately rather than discovering it in a pitch.


## The 90-second demo path

**Correction to an earlier note.** I previously flagged that the sales demo should "open on Mission Control, not the first screen." That was wrong. Opening on density is the trap every AI product falls into — *look how much it does!* Strangers don't buy activity. They buy a specific outcome they recognise as their own pain, then the belief that it compounds.

The sparse first screen isn't the problem. **Showing it before it has been earned** is. So don't skip it — end on it. The emptiness is the punchline.

### The structural insight

Kalpavriksha's value is a **derivative** — it lives in the change between day 1 and day 200. You cannot demo a derivative with a screenshot. The demo is therefore not a tour of screens; it is a **time-lapse of a relationship**.

Emotional arc: *this is my life* → *it did something I'd pay a person for* → *it gets better on its own* → *and then it leaves me alone.*

### Six beats, 90 seconds

| # | Time | Beat | On screen | Felt |
|---|---|---|---|---|
| 1 | 0:00 · 12s | **Cold open** | No interface. Two numbers: 340 approvals last quarter, 312 under four minutes. | Recognition |
| 2 | 0:12 · 18s | **The noise** | Day one. 23 open items stacking up. Deliberately uncomfortable. | Earned honesty |
| 3 | 0:30 · 20s | **The moment** | One decision in full — Datastack, ₹4.1L, counter-position written. **They click it.** | Competence |
| 4 | 0:50 · 15s | **The compound** | "You've approved 9 of 9 under ₹50K. Want me to stop asking?" + safety strip. | Surprise |
| 5 | 1:05 · 15s | **The slope** | Autonomy ratio 18% → 91%. The only chart in the demo. | Belief |
| 6 | 1:20 · 10s | **The silence** | "Nothing needs you." Four-second hold. | Desire |

Beat 3 gets the most time because it is the only beat that proves competence. Beat 6 holds silence for ten seconds, which will feel unbearable to the presenter and is exactly right.

### Six rules

1. **Open on their pain, not the product.** No interface for the first twelve seconds. If they don't nod at "312 of them took under four minutes," nothing after it lands.
2. **Hand them the mouse at beat 3.** They click *Send the counter*, not you. A demo watched is forgotten; a decision made with your own hand is a commitment — and it's the only moment they experience being the principal rather than the audience.
3. **Answer "what if it's wrong?" before they ask.** Four words under the rule proposal — *undo 24h · cap ₹2L · expires 30 days · pause one click* — four seconds of screen time. Pre-empt the autonomy objection while they're still excited.
4. **One chart, and it's a slope.** Not usage, not tasks, not hours saved. A rising slope is the only visual that expresses a derivative.
5. **The tree appears last, or not at all.** Every AI startup opens on a glowing particle animation; leading with it files you in that drawer within two seconds. Here it is atmosphere behind the final frame — the reward for having earned the silence.
6. **Never demo live.** A deterministic demo tenant with real data *shape* and fixed outcomes. Say so openly — "this is a scripted tenant" buys more trust than a live run that stumbles.

### Cut from the 90

**Conversation mode** (painful, but every AI product demos a chat box — it's the least differentiated thing you own). **Mission Control** (density reads as complexity to a stranger; right screen for the technical evaluator at minute eight). **The integrations wall** (a grid of logos says "another tool to configure"). **Voice** (delights in person, dies on a shared screen with bad audio — in-room only, never async). **Any sentence beginning "and it can also…"** — the 90 seconds proves exactly one claim, and a second claim halves the first.

### Variants off the same spine

- **90s cold** — all six beats. Booth, cold intro, opening of any call.
- **3 min async** — same beats plus the flagged judgment call from the receipt ("I approved this under your rule but the pattern might not be what you meant"). It needs its own beat to land, and async viewers rewind it. That clip is the one that gets forwarded.
- **15 min qualified** — run the 90 unchanged first, then open the floor. Mission Control, the queue at volume, conversation mode and the rule library all earn their place once the buyer is asking rather than being shown.

### The closing line

*"You're not buying a dashboard. You're buying that."* — said over the silent frame after a four-second hold, then stop talking. The instinct will be to fill the pause with features. **The pause is the product.**


## Open decisions for the founder

Four things deliberately left undecided rather than resolved silently.

**1. Approval queue at volume.** Past roughly five approvals a day the Approval Center becomes a queue, and a queue needs batching, muting, and standing rules ("always approve under ₹50K", "never auto-approve anything touching customer data"). Standing rules are arguably the most valuable feature in the entire product — they are how the founder delegates *judgment*, not just tasks. Design now, or after v1 ships?

**2. Discuss — inline or takeover?** Currently Discuss jumps to Conversation Mode. The alternative is an inline thread that expands within the approval card, keeping the founder in the decision context. Inline is better for quick clarifications; takeover is better for genuine deliberation. Possibly both, keyed to message count.

**3. Does the tree persist on every screen?** The position taken here is no — full-screen at arrival, sigil thereafter. The opposing case is that constant presence is exactly what sells "living intelligence", and that demoting it makes screens 02–05 feel like a conventional SaaS product wearing a dark theme. This is the single biggest reversible bet in the design.

**4. Autonomy level as a founder-facing control.** Mission Control displays "AUTONOMY · LEVEL 3" as a readout. Should that be a dial the founder can turn — trading approval volume against speed? It would be a powerful trust artifact, and it is also the fastest way to make the product feel dangerous. Worth prototyping before committing.

**Explicitly out of scope for this milestone:** backend, data model, real mission execution, authentication, mobile layouts below 1080px (the rail collapses; the full mobile experience is a separate design problem), and the return-visit greeting variation.
