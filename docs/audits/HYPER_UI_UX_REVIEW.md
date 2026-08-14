# HYPER AGENT — Kalpavriksha UI/UX Review
### Founder Surface · Dashboard · Tree Experience
**Review and proposal only. No files were modified.**
**7–12 August 2026**

---

## 0 · Evidence boundary — read before the verdict

I inspected the workspace before writing. What I can and cannot see:

| Source | Available | Used for |
|---|---|---|
| Earlier approved UI direction (prototypes, Design Constitution, Experience Bible) | ✅ | The "earlier" side of the comparison |
| **Product Veda v1.0** — the spec that produced the current UI | ✅ | The "current" side of the comparison |
| C20 Presence · C21 Conversation · C24 integration source | ✅ | Component inventory, layout, density |
| Founder's verbatim feedback | ✅ | The primary signal |
| Backend execution-state field list (from this brief) | ✅ | §6 Task-State, §8 Timing |
| **Implemented HTML/CSS/JS, tree renderer, WebView bridge, dashboard code** | ❌ **not in this workspace** | — |
| **Screenshots of the running app** | ❌ none provided | — |

**Consequence, stated plainly.** I am reviewing **the specified design and the
decisions that produced it**, not the shipped pixels. That is a weaker position
for measuring density (I cannot count the rendered cards) and a *stronger* one
for diagnosing cause — because the cause of both complaints is a decision
recorded in writing, and I can point at the line.

Findings that would change if the implementation drifted from spec are marked
**[verify against build]**.

---

## Executive Verdict

**The founder is right, and the cause is a decision I specified.**

Product Veda v1.0 §Supersessions **S2** reversed the earlier approved direction:

> *Prior:* "The tree recedes — sigil everywhere but arrival."
> *Product Veda:* "**The tree is primary and permanently full-bleed.**"

That reversal was ordered as FINAL by the Founder Edition brief and I
implemented it as instructed. But the earlier Design Constitution had contained
an explicit warning against exactly this, in these words:

> *"A particle organism that never gets out of the way becomes a screensaver
> the founder resents by day four."*

The founder's message — *"the tree is getting highlighted more than the actual
work"* — is that prediction arriving on schedule. This is not a rendering bug
or a colour problem. **It is a hierarchy inversion, specified on purpose, that
has now been tested against reality and failed.**

The second complaint, *"bulky rather than clean,"* is largely a **consequence of
the first**, plus two accumulations. Diagnosed in §Current UX Problems.

**Neither complaint calls for new design.** Both call for a prominence rule the
product does not currently have.

---

## Current UX Strengths

Preserve all of these. They are not the problem and the fix must not damage them.

1. **The identity works.** "The tree that talks" is memorable and unlike any
   competitor. The founder's complaint is about *proportion*, never about the
   tree's existence — worth reading carefully, because the instinct to cut is
   the wrong response.
2. **The honesty discipline holds.** No fabricated greeting, no fake activity,
   no invented ETA, no spinner. `--d-gate: 400ms` means short operations show
   nothing at all. This is genuinely rare and it is the product's deepest moat.
3. **State carried by colour *and* word** — everything survives greyscale.
4. **Four signals, one ceremonial accent.** The palette has not sprawled.
5. **The conversation surface is correct.** Somesh as flush-left prose with a
   hairline rather than a bubble-with-avatar was the right call and should not
   be revisited.
6. **The calm state is designed, not an afterthought.** "Nothing needs you" is
   a first-class screen. Most products in this category have no such state.
7. **Voice/text simultaneity** — neither is a mode you switch into.
8. **The token system is complete and internally consistent.** 121 tokens, zero
   undefined references. Whatever changes, the vocabulary holds.

---

## Current UX Problems

Ranked by contribution to the founder's two complaints.

### P1 — Hierarchy inversion: the least informative element has the most visual weight

The tree carries **6 states**. The work carries **11 semantic fields**
(`status`, `current_step`, `total_steps`, `elapsed_ms`, `timeout_ms`, `attempt`,
`max_attempts`, `message`, `result`, `requires_founder_completion`,
`terminal_state`).

Product Veda gives the tree a **full-bleed canvas, a 62%-width canopy, a canopy
bloom, and permanent breathing**, and gives the work a text stack in the lower
third behind a darkening veil.

**The element with the lowest information density owns the most pixels and all
of the motion.** That is the inversion, stated numerically. Everything else in
this review follows from it.

### P2 — Bulk is mostly *compression*, not card count

"Bulky" is usually read as "too many cards." I think that is the wrong
diagnosis here, and fixing card count alone will not satisfy the founder.

When the tree occupies the upper two-thirds, every readable thing is forced
into the remaining third. **Identical content in one-third of the canvas reads
as dense even when the component count has not changed.** Bulk here is a
symptom of crowding, not of accumulation.

Evidence for reading it this way: the founder said "becoming" — a trajectory.
The card count did not jump. The tree's prominence did (S2).

### P3 — Permanent zero-information panels

The C24 right rail carries two panels that read `Awaiting runtime` and will
continue to until C22/C23 land. They are *honest* — that was the point — but
they are **weight that says nothing, permanently on screen**. Two panels'
worth of border, padding, title and body to communicate an absence.

This is real, avoidable bulk. **[verify against build]**

### P4 — Band stacking

The specified home screen stacks, vertically: presence header · mission strip ·
conversation · founder actions · composer — plus a right rail. **Six horizontal
regions before any content.** Each is individually restrained; together they
read as a stack of trays.

The **founder actions row** is the worst offender: four buttons, all disabled,
all saying "Not connected in C21." Four controls that do nothing, permanently
occupying a band. **[verify against build]**

### P5 — Motion competes with reading

The tree breathes continuously, the bloom transitions on state, and the live
indicator flashes on sequence change. All three are individually restrained and
all three are in the founder's peripheral vision **while they are trying to
read what the system is doing.** Peripheral motion wins against static text —
that is not a preference, it is how vision works.

### P6 — The work has no dedicated home

There is a *presence header* and a *mission strip*, and both are ambient
summaries. There is no single, prominent, unambiguous answer to **"What is
Kalpavriksha doing right now?"** — the founder must assemble it from a strip of
five `label: value` pairs. The new backend contract makes a proper answer
possible for the first time; the UI has nowhere to put it.

### P7 — Redundant state surfaces

Presence header shows activity. Mission strip shows mission + execution + calm +
vigilance. The live indicator shows connection. The conversation shows thinking.
**Four surfaces describe system state**, and they overlap. Repetition reads as
noise even when each instance is clean.

---

## Earlier vs Current UI Comparison

| Dimension | Earlier approved | Current (Product Veda v1.0) | Direction |
|---|---|---|---|
| Tree role | Full-bleed on arrival only; 56px sigil thereafter | Permanently full-bleed, primary focal point | ⬇️ **Regressed** — hierarchy inverted |
| Primary question answered | "What needs me?" — one decision, in full | "Is Kalpavriksha here?" — presence | ⬇️ Regressed for a working founder |
| First-screen element count | 3 (voice · one decision · receipt) | 6 bands + right rail | ⬇️ Heavier |
| Motion at rest | Sigil breathing only, 56px | Full-canvas breathing + bloom + indicator | ⬇️ Heavier |
| Visual identity strength | Moderate | **Strong** | ⬆️ **Improved** — keep |
| First-run emotional impact | Good | **Excellent** | ⬆️ Improved — keep |
| Voice as a first-class input | Secondary | **Primary, unmistakable** | ⬆️ Improved — keep |
| Theme coverage | Dark only | Dark · Light · Auto | ⬆️ Improved |
| Token rigour | Good | **Complete (121, verified)** | ⬆️ Improved |
| Honesty guarantees | Strong | **Stronger** (`--d-gate`) | ⬆️ Improved |
| Work/step visibility | Implicit | Still implicit | ➡️ Unchanged — now the gap |
| Calm state | Designed | Designed | ➡️ Preserved |

**Restore:** the earlier hierarchy law — *the thing needing attention outranks
the thing expressing identity.*
**Keep:** the tree's visual quality, voice primacy, theming, tokens, honesty.
**Remove:** permanent tree dominance during work; the disabled actions row; the
permanent empty panels.

**Older is not simply better.** The earlier UI had a weaker identity and buried
voice. The correct outcome is the current visual language governed by the
earlier hierarchy law.

---

## Tree Role Assessment

Answering the brief's questions directly.

| Question | Finding |
|---|---|
| Too large? | **Not inherently — too large *while work is happening*.** At idle the size is right and is the product's best asset. |
| Contrast too strong? | Marginal. The canopy **bloom** is the real offender, not particle contrast. Bloom is a light source competing with text. |
| Animation attracting attention when secondary? | **Yes.** Continuous breathing in peripheral vision during reading. |
| Dominates hierarchy? | **Yes, unconditionally** — that is the defect. It dominates identically whether the system is idle or mid-execution. |
| Communicating useful state, or decoration? | **Genuinely useful — but low-bandwidth.** 6 states. It earns ambient presence; it does not earn 60% of the canvas. |
| Competes with task/status? | **Yes**, for both pixels and motion. |
| Should it become quieter ambient identity? | **Conditionally — not permanently.** See below. |
| When work happens, should attention go to task first? | **Yes. Without exception.** |

### The recommended role — one rule

> **The tree's prominence is inversely proportional to the amount of work in
> flight.**

Not a fixed size. Not a permanent sigil. A **dynamic prominence** bound to real
state.

- **Nothing happening →** the tree is the entire screen. Full-bleed, breathing,
  bloom on. This is the "I'm meeting Somesh" moment and it survives completely
  intact. It is also *honest*: a large tree literally means *nothing needs you*.
- **Work in flight →** the tree recedes — reduced canopy, bloom off, breathing
  amplitude down — and the work takes the centre.
- **Founder action required →** the tree recedes furthest and shifts to the
  attend signal. The decision owns the screen.

This resolves all four constraints at once: the identity is preserved, the
complaint is fixed, no component is deleted, and — the part I would defend
hardest — **tree prominence itself becomes information.** The founder learns to
read the room's proportion before reading a word.

**On animation:** yes, it should exist. It should be **the only continuous
motion in the product**, and its amplitude should scale down with prominence.
When the tree is at work-size, breathing is halved. When a decision is waiting,
breathing is at minimum.

**On visual language:** the current particle language is correct and should not
be replaced. Silver/gold impulses were brainstorming; I do not recommend them —
a second accent family would fracture a palette that is currently disciplined,
and gold is already spoken for as the ceremonial bloom.

---

## Dashboard Assessment

**[verify against build] — assessed from the C24 spec, not from rendered pixels.**

| Dimension | Finding |
|---|---|
| Information density | Acceptable *in isolation*; too high given the tree's crowding |
| Card count | Not the primary problem. Two of them are permanently empty — that *is* a problem |
| Spacing | Correct (8px rhythm, verified in tokens) |
| Borders | Hairlines are right; **the count of bordered regions is too high** — every band has an edge, and edges accumulate into a lattice |
| Typography | Correct and disciplined |
| Hierarchy | **Flat.** Every panel has the same title weight and border treatment, so nothing leads |
| Empty space | Insufficient *around the work*; ample around the tree — exactly backwards |
| Repeated labels | Yes — see P7, four state surfaces |
| Status repetition | Yes |
| Visual noise | Moderate, and mostly from **edges and bands**, not from content |
| Dashboard prominence | Correct (secondary, overlay, chevron-triggered) — do not change |
| Current mission prominence | **Too low.** A `label: value` pair in a strip |
| System-info prominence | **Too high** relative to its value |

**Is it showing too much at once? Yes — but the fix is subtraction of *chrome*,
not of information.** Most of what is shown is worth showing. It is shown with
too many borders, too many titles, and too little contrast between what matters
now and what matters generally.

**Concrete:** flatten the right rail from three bordered panels to one column of
hairline-separated rows with no panel borders at all. Same information, roughly
40% less visual weight, zero content lost.

---

## Information Hierarchy

The brief proposes a fixed 7-level order. **I recommend against a fixed order.**
A static hierarchy is what produced the current defect — the tree is always
first, regardless of what is happening.

### Proposed: a conditional hierarchy

**Rule 1 — Whatever needs a human outranks everything.**
If `requires_founder_completion` or an approval is open, that is position 1.
Nothing may outrank it, including the tree, including an in-flight execution.

**Rule 2 — Absent a human requirement, the current work leads.**
If a task is in flight, the work sentence is position 1.

**Rule 3 — Absent both, identity leads.**
Nothing in flight, nothing waiting → the tree is position 1 and may occupy the
whole screen.

### Resulting order per condition

| Condition | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| **Idle** | Tree (full) | Greeting | Voice input | Conversation | System line |
| **Working** | Work sentence + step | Progress/timing | Conversation | Tree (reduced) | System line |
| **Awaiting founder** | The decision + evidence | Work context | Tree (minimum, attend) | Conversation | System line |
| **Completed** | Result + what changed | Tree (bloom, brief) | Conversation | System line | — |
| **Failed** | What failed + what's at risk + next | Tree (reduced) | Conversation | System line | — |

**Position 6 in all conditions:** ambient identity, if not already placed.
**Position 7 in all conditions:** dashboard detail — **on demand only.**

The founder's sentence *"the tree is getting highlighted more than the actual
work"* is, precisely, the observation that row 2 and row 3 of this table are
currently rendered identically to row 1.

---

## Task-State Experience

### The governing rule

> **Show what is being done, not what state the machine is in.**
> The state name is the *fallback* when no step message exists — never the
> default.

`message` and `current_step` describe reality. `status` describes the machine.
The founder cares about the first. **`status` should be invisible whenever
`message` is present.**

### Translation table

Technical state → founder-facing language. Chosen for professional register: no
exclamation, no cuteness, no jargon, present continuous for ongoing work.

| Backend state | Founder-facing | Notes |
|---|---|---|
| `idle` | *(nothing shown)* | Silence is the correct rendering. Do not print "Idle." |
| `understanding` | **Reading your request** | |
| `planning` | **Working out the steps** | Not "Planning" — vague to a non-engineer |
| `awaiting_approval` | **Needs your approval** | Position 1. Amber. |
| `executing` | **`message`** — e.g. *Opening Chrome* | State name never shown when a message exists |
| `observing` | **Watching for the result** | |
| `verifying` | **Checking the result** | |
| `recovering` | **Retrying — attempt {n} of {max}** | Only surfaces because attempt > 1 |
| `awaiting_founder_completion` | **Ready for your review** | Position 1. Amber. |
| `completed` | **Done** + one line of what changed | |
| `failed` | **Couldn't finish** + what is at risk + what happens next | Never a stack trace, never an error code as the headline |
| `blocked` | **Stopped — needs you** + the reason | |

### Presentation

One **work line**, `--t-speech` scale (28/40), flush left, at the top of the
work region. One line. Not a card, not a panel, not a bordered box.

Beneath it, at `--t-mono`, at most one supporting line — step position and (only
when warranted) timing. Nothing else.

**Three or four elements total describe the current work.** Compare with the
current mission strip's five `label: value` pairs plus a presence header.

---

## Timing / Progress Experience

Timing is where honest products go wrong most often, so these are rules, not
suggestions.

| Signal | Show when | Never |
|---|---|---|
| `elapsed_ms` | Only once it exceeds **10s**. Below that it is noise | Never as a live millisecond counter |
| `current_step / total_steps` | When `total_steps` is known **and ≥ 3**. Render as **"Step 3 of 7"** | Never as a percentage. Steps are not equal in duration; a percentage is a lie |
| Progress bar | **Only** when `total_steps` is known and ≥ 3. A 2px discrete segmented bar, one segment per step | Never a continuous or indeterminate bar. An indeterminate bar is a spinner with better PR |
| `timeout_ms` | **Only in the final 25%** of the window, as *"Taking longer than usual"* | **Never a countdown.** A countdown tells the founder to watch a clock and implies imminent failure |
| `attempt / max_attempts` | **Only when `attempt` > 1** → *"Retrying — attempt 2 of 3"* | Never show "attempt 1 of 3"; it advertises fragility before any exists |
| Liveness | The **step message changing** is the proof of life. If nothing changes for **20s**, append *"still working · 1m 20s"* | Never a pulsing dot that means nothing |

**Hide timing entirely** when a task completes inside `--d-gate` (400ms), and
when the founder is not looking at the work region.

**Never create a fake ETA.** The product does not know how long it will take.
Elapsed is a fact; remaining is a guess. Only facts are shown.

---

## Founder Completion Experience

`AWAITING_FOUNDER_COMPLETION` is a hard backend state and must be unmistakable
in the UI. The brief's constraint — *deliberate but lightweight, not bulky* — is
the whole design problem.

### Recommendation: takes the band, not the screen

It **owns position 1** in the hierarchy and takes over the work region. It does
**not** become a full-screen takeover, and it is **not** a modal (there are no
modals in this product).

**Anatomy — five elements, no more:**

1. **What was done** — one sentence, `--t-speech`. From `message` / `result`.
2. **Evidence** — *one interaction away, collapsed by default.* This is the
   single most important anti-bulk decision here: expanded evidence is what
   turns an approval into a wall. A `chevron-right` and the word *Evidence*.
3. **Consequence line** — what marking complete will do, one line, `--t-body`.
4. **Two actions** — `Mark complete` (settled) and `Send back` (secondary).
   Labels state the outcome, not the verb: never "OK", never "Submit".
5. **Undo window** — after completion, a transient line offering reversal for a
   specified period. This is what makes the action feel *lightweight* — the
   weight of a decision comes from its irreversibility, so a reversible one can
   be a single calm click.

**Tree:** minimum prominence, attend signal. **Signal colour:** `--s-attend`
until resolved, then `--s-settled`.

**It cannot be missed:** the work region cannot render anything else while this
state is live, and the tree's reduced prominence is itself a persistent cue. It
does not time out, does not auto-dismiss, and produces no OS notification.

---

## Recommended UX Direction

Five moves, in dependency order.

**1. Introduce a prominence state machine for the tree.** Three prominence
levels — `ambient` (full-bleed), `reduced`, `minimum` — bound to real work
state, transitioning at `--d-8` with `--e-settle`. This is the single change
that resolves the founder's primary complaint.

**2. Create a Work Region.** One area, top of content, that answers *"What is
Kalpavriksha doing right now?"* in one sentence. It is empty and collapsed when
idle. This is where the new backend contract lands.

**3. Collapse the four state surfaces into two.** The **work line** (what is
happening now) and a **system line** (one row, hairline, at the bottom edge:
connection · autonomy · environment · runtime). Retire the mission strip and
fold the presence header into the work region.

**4. Debord the rail.** Replace bordered panels with hairline-separated rows.
Remove the two permanent "Awaiting runtime" panels; state their absence in the
system line instead — one row, not two panels.

**5. Remove the disabled founder-actions row** from the home screen. Four
non-functional controls in a permanent band is the clearest available bulk win.

---

## Proposed Layout Philosophy

> **One question, one answer, one place.**

The screen answers exactly one question at a time, and which question it
answers is determined by real state, not by layout.

- **Idle:** *Is Somesh here?* → the tree answers, and owns the screen.
- **Working:** *What is happening?* → one sentence answers, and owns the screen.
- **Waiting:** *What do you need from me?* → one decision answers, and owns
  the screen.

Everything else is **peripheral by construction**: one system line at the
bottom edge, the dashboard behind a chevron, the conversation scrolling below.

**Bands are the enemy.** The target is **three regions maximum** at any moment:
identity · work · input. Not six.

---

## Proposed Interaction Philosophy

> **The interface should feel like one attention, not several panels.**

- **Attention follows work.** Whatever the system is doing is where the visual
  weight goes. The founder never hunts for it.
- **One thing moves at a time.** When the work region updates, the tree holds
  still. When the tree changes state, the work region does not animate. Two
  simultaneous animations are one too many.
- **Silence is a valid response.** Fast operations show nothing. Idle shows
  nothing but the tree. The product is allowed to be quiet.
- **Every state change is legible in one glance and one sentence.** If it takes
  two elements to understand what is happening, the design has failed.
- **Reversible actions are light; irreversible actions are heavy.** Weight
  comes from consequence, never from decoration.

---

## What to Remove

| # | Item | Reason |
|---|---|---|
| 1 | Permanent tree dominance during work | Root cause of complaint 1 |
| 2 | Canopy bloom while work is in flight | A light source competing with reading |
| 3 | Disabled founder-actions row on the home screen | Four dead controls in a permanent band |
| 4 | The two permanent "Awaiting runtime" panels | Zero-information weight; becomes one system-line row |
| 5 | Mission strip as a separate band | Folds into the work region and the system line |
| 6 | Panel borders in the right rail | Hairline rows carry the same information at ~40% of the weight |
| 7 | Any `status` name shown when a `message` exists | Machine vocabulary in front of a founder |
| 8 | Continuous breathing at full amplitude during reading | Peripheral motion beats static text |

---

## What to Preserve

The tree and its particle language · voice as primary · the calm state · the
honesty guarantees (no fake ETA, no spinner, no fabricated greeting,
`--d-gate`) · four signals plus ceremonial bloom · colour **and** word ·
Somesh as prose, never a bubble with an avatar · dark/light/auto · the full
token system · the dashboard's secondary, overlay, chevron-triggered role ·
the first-run startup sequence, **unchanged** — it is the product's best moment.

---

## What to Simplify

1. **Four state surfaces → two** (work line, system line).
2. **Six bands → three regions** (identity, work, input).
3. **Three rail panels → one hairline column.**
4. **Twelve technical states → twelve founder sentences**, with `status` hidden
   whenever `message` exists.
5. **Timing → conditional**: hidden by default, appearing only when it carries
   information (see rules above).
6. **Approval → five elements**, evidence collapsed by default.

---

## What to Explore

Not recommendations — hypotheses worth prototyping before committing.

1. **Tree prominence as the only progress indicator.** If tree size already
   encodes "how much is in flight," a separate progress bar may be redundant.
   Worth testing whether the segmented step bar can be deleted entirely.
2. **Localised branch response.** When work happens in a domain, the
   corresponding branch region brightens slightly — the founder learns *where*
   before *what*. Already specified in the notification system; worth extending
   to work state.
3. **A "work density" reading of the canopy** — canopy compactness reflecting
   in-flight count. Risk: it becomes a chart made of leaves. Prototype before
   believing.
4. **Removing the greeting after week one.** The greeting is a first-run
   delight that may become friction for a founder opening the app eight times a
   day. Measure, do not assume.
5. **Light theme as the working default.** Founder Dark is beautiful and the
   tree is stronger in it; Founder Light may be calmer for six-hour days. Worth
   asking the founder directly.

---

## Implementation Phases

Ordered so the founder's complaint is resolved first and cheaply.

### Phase 1 — Prominence *(highest impact, lowest risk)*
Tree prominence state machine (`ambient` / `reduced` / `minimum`); bloom off
during work; breathing amplitude scaled to prominence. **Nothing is deleted.**
Ships alone and should resolve most of complaint 1.

### Phase 2 — Subtraction *(highest bulk win)*
Remove the disabled actions row. Remove the two empty panels. Debord the rail.
Fold the mission strip. **Nothing new is built.** Should resolve most of
complaint 2.

### Phase 3 — The Work Region
Build the single work line, the state translation table, and conditional
timing. This is where the new backend contract is consumed.

### Phase 4 — Founder Completion
The five-element approval, collapsed evidence, undo window.

### Phase 5 — Refinement
Failure and blocked presentation; conversation integration with the work
region; explore items 1–2 above.

**Phases 1 and 2 are independent of the backend contract and can ship
immediately.** Phase 3 depends on the execution-state fields being available to
the UI.

---

## UX VERDICT

### **C — CURRENT UI HAS LOST THE ORIGINAL HIERARCHY; REDESIGN REQUIRED**

**Scoped precisely, because "redesign" reads worse than it is:** what must be
redesigned is the **hierarchy and prominence rules** — not the visual language,
not the components, not the tokens, not the startup sequence.

I estimate **~80% of existing assets survive unchanged.** Nothing needs to be
rebuilt. What is missing is a rule that decides, at every moment, what the
screen is *for*.

Not **B**, because simplification alone will not fix this. You could delete
every surplus card and the tree would still outrank the work — the founder's
first complaint would survive a pure decluttering pass.

Not **D**, because the assets are strong, the identity works, and the honesty
discipline is genuinely rare. Reconstruction would destroy more than it fixed.

---

### TOP 5 CHANGES

**1 · Make tree prominence inversely proportional to work in flight.**
Three levels bound to real state. Resolves the primary complaint, preserves the
identity completely, deletes nothing. *Highest impact by a wide margin.*

**2 · Create one Work Region that answers "What is Kalpavriksha doing?" in one
sentence.** Show `message`, not `status`. The new backend contract has no home
today; this builds it.

**3 · Collapse four state surfaces into two** — a work line and a single system
line at the bottom edge. Retire the mission strip; fold in the presence header.

**4 · Subtract: the disabled actions row, the two empty panels, the rail's
panel borders.** Pure removal, no new work, and the fastest visible answer to
"bulky."

**5 · Make timing conditional and honest.** Elapsed only past 10s; discrete
"Step 3 of 7", never a percentage; **no countdown ever**; attempts only when
retrying.

---

### FUTURE UI PRINCIPLE

> **Attention follows work. Identity fills the silence.**
>
> Kalpavriksha's presence should expand into empty time and retreat from
> occupied time. When there is work, the work is the interface. When there is
> nothing, the tree is the interface — and that emptiness is the product
> succeeding, not idling.

---

**Review complete. No files modified. Stopping here.**
