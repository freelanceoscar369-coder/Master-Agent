# PRODUCT VEDA — Kalpavriksha Founder Edition Visual Language

**Version 1.0 · 7 August 2026**

The complete visual specification. This document and the ten it indexes are the
implementation source of truth. **Claude should never guess. Everything is here.**

---

## How to read this

| # | Document | Covers |
|---|---|---|
| 10 | `00_TOKENS.md` | **Read first.** Typography, colour, spacing, radius, duration, easing, elevation, blur, icons, interaction states, motion accessibility |
| 1 | `01_FOUNDER_SURFACE.md` | Founder Home Screen: tree placement, the vertical stack, ambient lighting, greeting, microphone, text input, responsive behaviour at three breakpoints |
| 2 | `02_ANIMATION_SYSTEM.md` | Tree geometry, the six states, the state machine, performance budget, micro-animations |
| 3 | `03_VOICE_EXPERIENCE.md` | Microphone matrix, listening indicator, waveform, interrupt, mute, noise, voice+text, transcript |
| 4 | `04_CONVERSATION_DESIGN.md` | Founder and Somesh messages, long replies, tables, charts, code, thinking, scroll, persistence |
| 5 | `05_DASHBOARD_BEHAVIOUR.md` | Appearance, hiding, overlay, transitions. **Content unchanged.** |
| 6 | `06_STARTUP_EXPERIENCE.md` | Launch → Splash → Growth → Light → Wake → Greeting → Ready |
| 7 | `07_DESKTOP_PRESENCE.md` | Taskbar, tray, minimize, restore, focus, application states |
| 8 | `08_THEME_SYSTEM.md` | Founder Dark, Founder Light, Auto |
| 9 | `09_NOTIFICATION_SYSTEM.md` | Notifications that originate from the tree |

**Build order.** `00_TOKENS` → `01_FOUNDER_SURFACE` + `02_ANIMATION_SYSTEM` →
`03` + `04` → `06` → `08` → `05` + `07` + `09`.

The tree and the tokens come first. Everything else assumes they exist.

---

## The five sentences that govern everything

If a decision is not covered by any document, decide it from these.

1. **The tree is the identity.** It is not decoration, not a loader, not a
   mascot. It is the product's body. People must remember *the tree that talks.*
2. **Somesh is heard and read, never depicted.** No avatar, no face, no icon, no
   character. The tree is the only mark.
3. **Voice is primary. Text is always available.** Both are simultaneously live;
   neither is a mode you switch into.
4. **The tree is primary; the dashboard is secondary.** The dashboard is a place
   you visit and leave. It may never dominate the Founder Surface.
5. **Never fake liveness.** Motion reflects real state. The idle breathe and
   pulse are a resting heartbeat, not activity. On a dead feed the interface is
   still, and that stillness is honest.

---

## Recorded supersessions — six reversals of previously-approved decisions

This brief overrides six decisions in the accepted *Design Constitution* and
*Experience Bible*. All six are implemented as instructed. They are recorded
here so the two bodies of work do not silently contradict each other, and so a
future reader knows which document won and why.

**Where Product Veda and the Design Constitution disagree, Product Veda governs
for the Founder Edition.** The Constitution remains authoritative for the
Founder Dashboard's interior surfaces, which this brief explicitly did not
change.

| # | Prior decision | Product Veda 1.0 | Consequence |
|---|---|---|---|
| S1 | *"Text is the source of truth; voice is a layer over it."* (Bible §5) | **Voice is primary.** | The microphone is the largest interactive element on the home screen; the composer is collapsed by default. Text remains always available and lossless — the reversal is about primacy, not availability. |
| S2 | *"The tree recedes — sigil everywhere but arrival."* (Constitution §3) | **The tree is primary and permanently full-bleed.** | The 56px presence sigil is retired from the Founder Surface. It survives only inside dashboard interior screens. |
| S3 | *"There is no light theme; adding one is a constitutional amendment."* | **Founder Light ships.** | Designed as warm paper, not inverted dark. The lighting model changes with it: paper does not glow, so the canopy bloom is removed in Light and state is carried by particle density, ink weight and filament opacity instead. |
| S4 | *"The AI does not celebrate. No bursts, no confetti, no bloom on success."* | **Celebration ships: the tree blooms, golden particles.** | Constrained numerically in `02_ANIMATION_SYSTEM` §2.2: fires only on a real founder-facing completion, at most once per event, never on app open. |
| S5 | *Four signal colours only; nothing else may be coloured.* | **A fifth colour, `--s-bloom`, is admitted as ceremonial.** | Scoped hard: permitted only on tree particles during a celebration sequence. It is never a UI colour, never a state colour, never available to a component. |
| S6 | *The assistant is "Kalpavriksha", first person.* | **Kalpavriksha is the product and the tree. Somesh is the personality.** | The wordmark reads KALPAVRIKSHA. Somesh is the name attached to speech. One personality, one mark, no third entity. |

**What did not change**, and must not: the 8px vertical rhythm; the
mono-states-facts / text-states-judgment rule; four depth planes and therefore
no modals; state carried by colour *and* word; no badges, no counts, no OS
toasts; the honesty rules — never fabricate a greeting, never invent activity,
never synthesise state the runtime did not report.

---

## Success criteria, made testable

The brief's success criterion is a feeling: *"I'm meeting Somesh,"* not *"I'm
opening software."* Feelings are not verifiable, so here is what must be true
for that feeling to be possible.

| Test | Pass condition |
|---|---|
| **First frame** | The window is never white. `--c-void` is painted before the first frame. Verified by video capture at 240fps. |
| **Time to presence** | The tree is visible and moving within 600ms of window creation. |
| **Time to interactive** | Input is accepted before the startup animation finishes. The founder never waits on a flourish. |
| **Three-second identity** | A stranger shown any screen for three seconds names the tree first. |
| **No-chrome test** | On the home screen the only non-tree, non-language elements are the wordmark, the microphone, the composer, and one chevron. Count them: four. |
| **Stillness test** | With no runtime data, the interface breathes and does nothing else. No spinner appears. No progress bar appears. No invented greeting appears. |
| **Greyscale test** | Screenshot in greyscale: every state remains readable, because every state carries a word. |
| **Silence test** | Mute voice entirely. Nothing is lost but sound. |
| **Reduced-motion test** | With `prefers-reduced-motion`, every screen is complete and still. No element is missing. |
| **60fps test** | The tree holds 60fps on integrated graphics at the desktop particle budget, and degrades by reducing particle count first. |

---

## The refusal list

Kalpavriksha's identity is as much what it declines to be. None of the following
may enter the product without an explicit reversal recorded in this section.

**Never:** an avatar · a mascot · a face · an assistant icon · a floating chat
bubble · a generic AI glyph · a modal dialog · a notification badge · an unread
count · an OS toast · a spinner · a progress bar for an unknown duration ·
three bouncing dots · a fabricated greeting · simulated typing · invented
activity · a KPI wall on the home screen · a settings gear on the home screen ·
an onboarding tour · an empty-state illustration · a celebration on launch ·
gamification of any kind · a colour outside the five defined · a fifth easing
curve · a duration off the ladder.

---

## Open items for the founder

Two things I did not decide alone, recorded rather than assumed.

1. **Somesh's voice character** is not specified here. Rate, pitch and prosody
   are a casting decision, not a visual one. `03_VOICE_EXPERIENCE` specifies
   every visible state of voice interaction; the voice itself needs an audition.
2. **Celebration triggers.** `02_ANIMATION_SYSTEM` §2.2 specifies exactly how a
   celebration looks and constrains it to *a real founder-facing completion*.
   **Which events qualify is a product decision, not a visual one.** If the list
   grows past a handful, the bloom stops meaning anything — that is the risk to
   manage.

---

## Provenance

Derived from: the approved UI prototype · the accepted Design Constitution and
Experience Bible (with the six supersessions above) · C20 Presence · C21 Founder
Conversation · the C24 integration.

No workflow, architecture, feature, backend, AI behaviour, planning, execution,
dashboard content, or voice pipeline was invented or altered. This is a visual
finalisation of an already-approved experience.
