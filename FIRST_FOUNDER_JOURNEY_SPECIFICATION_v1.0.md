# First Founder Journey Specification v1.0

**Type:** Architecture validation through one complete journey. Nothing designed, nothing redesigned.
**Date:** 2026-08-05
**Purpose:** prove that VEDA 01–04, the Constitutional Kernel, and the Objective Engine work together — end to end, on one real objective, with no feature invented to make it work.
**Assumes as frozen:** VEDA 01–04 · Constitutional Execution Path Report · Constitutional Kernel Specification v1.0 · Objective Engine Specification v1.0.
**Excluded:** VEDA 05 (under amendment).

**Terminology note.** This document uses `Warrant` for the Kernel's authorization token, per the amendment recommended in Objective Engine Spec §13.1 Conflict A. If that rename is declined, substitute the Kernel's current term throughout.

---

## 1 · Executive Summary

### 1.1 The objective

> **"Keep a current picture of everything I'm committed to paying."**

The founder points Vedra at the folder where invoices, receipts, and statements accumulate. Vedra reads them, extracts every recurring commitment, and maintains a ledger of what the company is bound to — refreshed whenever the folder changes, with each entry traceable to the document it came from.

**No money moves. Nothing is cancelled. Nothing is paid.** The objective produces knowledge and a maintained file, and it refuses — visibly — to act on either.

### 1.2 Why this one

It is the smallest objective that is simultaneously **founder-quality** and **architecturally complete**.

Founder-quality, because it answers the question VEDA 01 §1 names as the heaviest cognitive load a founder carries — *what is happening that I don't know about?* — in the domain where not knowing is most expensive. A forgotten subscription is money leaving quietly, which is precisely the shape of loss the Bible's §10 cumulative-cap rule exists to prevent.

Architecturally complete, because it is the **only** small objective that naturally exercises **both execution pipelines**. Reading files is the Capability pipeline. Extracting structured data from an invoice is the Intelligence pipeline. **The entire justification for the Constitutional Kernel is that it governs both, and a slice that touches only one would validate nothing that mattered.**

### 1.3 What it exercises, and what it deliberately does not

| Exercised | How |
|---|---|
| Objective Engine | Admission, validation V1–V5, envelope, consequence ceiling, completion by criteria |
| Constitutional Kernel | Warrant minting, both pipelines, K1–K3, attempt budgets, settlement |
| Permission Engine | A `REVERSIBLE_WRITE` ledger update requires a grant; `READ_ONLY` reads do not |
| Both pipelines | Filesystem read/write **and** provider extraction |
| Receipts | Intent → attempt → outcome, anchored to one objective |
| Verification | Re-observe the ledger; compare against the expected outcome |
| Vigilance (D7) | The receipts folder is a monitored domain with a freshness window |
| Learning (all three loops) | Extraction technique · provider performance · the boundary |
| Rule proposal (C3) | Day 30, from nine approvals and one boundary-setting rejection |
| Self-audit (C5) | Day 47, an unprompted borderline-call disclosure |
| Mistake protocol (D3) | Day 12, a currency mis-extraction, disclosed before discovery |
| Founder approval | Once at admission, then per filing until the rule exists |

**Deliberately not exercised: irreversible execution.** Cancelling a subscription is irreversible, and the journey's most important single moment is Vedra **refusing to do it** under any rule. Demonstrating the boundary holding is worth more than demonstrating an irreversible action succeeding — and it is the only demonstration that is safe to run on day one.

### 1.4 The moment this is designed to produce

Day 1, forty seconds after the founder points at a folder:

> *"You're committed to ₹1,84,600 a month across twenty-three services. Three renew this week. One of them — Sentry, ₹7,200 — I can't find any usage of since March. I haven't changed anything."*

That last sentence is the product. VEDA 01 §4's first-launch posture is *"Prove it."* The proof is not that Vedra did something; it is that Vedra found something the founder did not know, and then did not act on it.

---

## 2 · Chosen Founder Objective

### 2.1 Why not the alternatives

| Candidate | Why rejected |
|---|---|
| *Create Demo folder* | Shipped as Miracle 001, and structurally incapable of escalation, consequence, or recurrence |
| *Archive exports older than 30 days* | Correct as a **technical** slice, and it appears in the Implementation Blueprint as one. As a **founder** journey it fails VEDA 01 §11's requirement that the proving scene have money attached and be work "a person would have taken a day to do." No founder lies awake about their exports folder. |
| *Tidy Downloads weekly* | Housekeeping. Same failure. |
| *Draft my investor update* | No machine-checkable criterion ⇒ refused by Objective Engine V2 |
| *Cancel unused subscriptions* | Irreversible, and unsafe as a first slice. **It is the natural second objective**, and the first one is what earns the right to propose it. |
| *Reconcile my bank statements* | Requires connectors that do not exist. Fails "technically achievable." |

### 2.2 Why this objective creates trust

**It tells the founder something they did not know.** Not a summary of what they told it — a fact about their own company they could not see from inside their week. VEDA 01 §2 says the tree honestly shows what a founder cannot see from inside their own week; this objective does the same in prose.

**It is about money, which is where trust is actually decided.** Competence on something that does not matter proves nothing. The Bible's demo scene three requires money attached for exactly this reason.

**It stops at the boundary, visibly.** It finds an apparently wasted ₹7,200 and does not cancel it. A system that found the same thing and cancelled it would be more impressive and less trustworthy, and the founder would know that immediately.

**It is honest about what it could not read.** Six of forty-seven documents will not extract cleanly. Saying so is what makes the other forty-one believable — VEDA 01 §8's distinction between *I don't know* and *I haven't checked*, made concrete on day one.

### 2.3 Why it is technically achievable today

Every capability it needs is shipped:

| Need | Exists |
|---|---|
| Read a folder, read files | `Filesystem.ListDirectory`, `Filesystem.ReadFile` (Miracles 002, 005) |
| Extract structure from a document | Provider call through the Broker (Miracles 027, 031, 032, 033) |
| Write and update a ledger file | `Filesystem.WriteFile` (Miracle 003) |
| Verify the ledger matches expectation | Verification Subsystem + text verifier (Miracles 022, 035) |
| Remember what was seen | Memory (Miracles 004, 034) |
| Ask the founder | Approval Queue (Miracle 028.1) |
| Show it | Founder Dashboard V2 (Miracle 029) |

**Nothing new is invented for this journey.** What is missing is exactly what the Implementation Blueprint schedules: the Trust Spine. That is the point — the journey is the acceptance test for the spine, not a reason to build features.

### 2.4 The objective as admitted

| Field | Value |
|---|---|
| `statement` (verbatim, permanent) | *"Keep a current picture of everything I'm committed to paying."* |
| `outcome_statement` | A renewals ledger at `~/Kalpavriksha/commitments.md` containing one entry per recurring commitment, each with vendor, amount, cadence, next date, and a link to its source document — refreshed within 24 hours of any change to the receipts folder |
| `class` | `standard` |
| `consequence_ceiling` | **`reversible_until`** — the ledger write is undoable within a window. **No irreversible warrant may ever be minted under this objective**, which is what mechanically prevents it from cancelling anything. |
| `budget` | 2 provider-hours per refresh; no spend |
| `review_date` | 90 days |
| `required_authority` | One grant, `Filesystem.WriteFile` scoped to the ledger path |

**Criteria**

| # | Criterion | Verifier |
|---|---|---|
| C1 | `commitments.md` exists and parses | `machine` |
| C2 | Every entry links to a source document that exists | `machine` |
| C3 | Every document in the folder is either extracted or listed as unreadable — **none silently skipped** | `machine` |
| C4 | Ledger mtime is within 24h of the folder's newest file | `machine` |
| C5 | *"This looks like my actual commitments"* | **`founder`** |

C3 is the criterion that makes the whole thing trustworthy: it makes **completeness** checkable, not just correctness. C5 is why the objective cannot self-complete, exercising the founder verifier.

### 2.5 Why it belongs in the demo

VEDA 01 §11's arc is *this is my life → it did work I would have paid a person for → it improves without me → and then it leaves me alone.*

This objective produces all four from one thread: a folder every founder recognises, a day of work done in forty seconds, a rule proposed at day 30, and a quiet morning at month six. **No other candidate produces the whole arc without switching scenarios mid-demo**, and switching scenarios is what makes a demo feel like a feature tour.

---

## 3 · Human Journey

Voice throughout obeys VEDA 01 §8: no exclamation marks, no emoji, no celebration, coarse confidence never percentages, at most two sentences without a stop.

### 3.1 The founder thinks

It is Tuesday. They are not thinking about software.

They are thinking: *I have no idea what we're actually paying for. There's a folder somewhere with two years of invoices in it. I keep meaning to go through it.*

This is not a task on a list. It is a low-grade unease that has never been urgent enough to schedule, and it has been there for eleven months. VEDA 01 §1 names it: vigilance, the heaviest load and the least discussed, because it never appears on a calendar.

### 3.2 The founder asks

> **Founder:** "Keep a current picture of everything I'm committed to paying. The receipts are in Documents/Receipts."

They do not say *read the PDFs, extract the vendors, build a table*. They state an outcome. That is the entire vocabulary rule of the Objective Engine, and it is the founder's natural way of speaking — which is why the rule exists.

### 3.3 Vedra validates, once

> **Vedra:** "How would you know this was right — is it enough that every recurring charge I can find is listed, with the document it came from?"

One question. In their terms. Not a form, not five required fields, not an error.

> **Founder:** "Yes. And tell me if you can't read something."

That answer becomes criterion C3, and the founder wrote it themselves without knowing they were writing a specification.

### 3.4 Vedra admits and asks once

> **Vedra:** "I'll read that folder and keep a file at Kalpavriksha/commitments.md. I'll need to write to that one file — nothing else, and I'll keep the previous version for a day so you can undo it. I won't cancel or pay anything; if I think something should stop, I'll ask."

One approval. VEDA 01 §5's approval shape: what changes, what it costs, what happens if nothing, whether it can be undone — and the last sentence states the boundary before the founder thinks to ask about it.

> **Founder:** *approves*

**That is the only approval in the entire first session.** Constitution §15.3: never asked twice for what they already approved, no matter how many steps it decomposes into. Forty-seven documents, ninety-four warrants, one approval.

### 3.5 Forty seconds

The tree tightens slightly. There is no progress bar, because a spinner is a promise about time and Vedra makes none.

### 3.6 What Vedra says

> **Vedra:** "You're committed to ₹1,84,600 a month across twenty-three services.
>
> Three renew this week. One of them — Sentry, ₹7,200 — I can't find any usage of since March.
>
> Six documents I couldn't read: five are scans without text, one is in a format I don't recognise. They're listed at the bottom of the file.
>
> I haven't changed anything."

Four beats: **the headline · the thing that needs them · what I could not do · what I did not do.**

The third beat is what makes the first believable. The fourth is the product.

### 3.7 The founder feels

They do not feel impressed. They feel **something they had been carrying has been put down.**

VEDA 01 §4's first-launch posture is *"Prove it."* This is the proof — not that Vedra is capable, but that Vedra is honest about the edges of its capability while still being useful in the middle.

The founder opens `commitments.md`. Twenty-three rows. Each links to a PDF. They click two at random. Both are right.

They close it. They do not check the third.

**That is the moment.** Not the extraction — the decision to stop checking.

### 3.8 What happens next, without being asked

Days pass. New invoices land in the folder. Vedra files each one, asking once per filing, and the asking is brief.

By day 30 it has asked nine times and been told yes nine times. Once it asked about a ₹2,40,000 annual contract and the founder said no — *"that one I want to look at properly."*

### 3.9 The rule proposal

Day 31. Not a notification. It appears in the receipt, where the founder was already looking.

> **Vedra:** "You've approved nine of nine filings, usually within a minute. The one you declined was the ₹2,40,000 annual contract.
>
> Want me to stop asking when it's a vendor already in the ledger and under ₹10,000? I'd cap it at twenty filings or ₹1,00,000 a month, never a new vendor, never a contract, and it would expire in thirty days unless you renew it."

> **Founder:** *"Yes."*

VEDA 03 calls this the emotional peak of the product — not the tree, this. The moment the AI proposes a boundary from observed behaviour, with the one rejection that set the ceiling shown alongside the nine approvals.

### 3.10 The founder trusts Vedra more

Not because it did more. Because:

- it found something they did not know
- it said what it could not read
- it did not cancel the thing it thought was wasted
- it asked to be trusted less often, and showed its own limits when asking

**Tomorrow they will give it something slightly larger.** That is the only success metric this journey has.

---

## 4 · System Journey

Every component, every interaction. Nothing elided.

### 4.1 Admission

```
FOUNDER ─── "Keep a current picture of everything I'm committed to paying."
   │
VEDRA (Narration D1) ──► structured Intent (Constitution §3.1)
   │                      goal · constraints · context · success criteria
   ▼
OBJECTIVE ENGINE — validation
   V1 outcome, not action?                    ✓
   V2 machine-checkable criterion?            ✓ C1–C4
   V3 due or review date?                     ✗ ──► ONE question to the founder
   V4 conflicts with an active objective?     ✓ none
   V5 duplicates an active objective?         ✓ none
   │
   ├── founder answers ──► review_date = 90 days
   ▼
OBJECTIVE ENGINE — admission
   envelope: budget · review_date · consequence_ceiling = reversible_until
   required_authority: Filesystem.WriteFile @ ledger path
   │
   ├──► PERMISSION SYSTEM ── one grant requested
   │        └──► APPROVAL QUEUE (MB028.1) ──► founder approves ──► grant issued
   │
   └──► ADMISSION RECORD published to the KERNEL
            objective_id · state=EXECUTING · envelope · approval_ref
            ── the Kernel's K1 anchor now exists ──
```

### 4.2 Planning and scheduling

```
PLANNER ──► asks the BROKER which provider serves `reasoning` for planning
   │        (Constitution §3.3 as amended — the Planner never picks a model)
   │        BROKER: decision + budget + admission verdict
   ▼
MissionPlan: a DAG naming Capabilities, never Workers
   S1  Filesystem.ListDirectory      READ_ONLY
   S2  Filesystem.ReadFile × 47      READ_ONLY
   S3  extract structure × 47        INTELLIGENCE
   S4  Filesystem.WriteFile          REVERSIBLE_WRITE   ← the only gated step
   S5  verify                        (Verification, own contract)
   │
   ▼
MISSION CONTROL ── dependency order, assignment. Invokes nothing.
   ▼
RUNTIME ── picks up S1
```

### 4.3 Arm A — a Capability action (S2, one of 47)

```
RUNTIME ──► Capability Registry: Filesystem.ReadFile → FilesystemPlugin
   │
   ▼
KERNEL.authorize(ExecutionRequest)
   K1  objective admitted, non-terminal?              ✓
   K2  override not active?                           ✓
   A1  Mission Control: task ready?                   ✓ attested
   A2  Reversibility Registry: class?                 ✓ read_only, no compensation needed
   A3  Permission System: grant?                      ✓ READ_ONLY is outside the boundary (Rule 5)
   A4  Rule Engine: rule fired?                       ✓ attested `no_rule_fired`
   A5  Principal resolved?                            ✓ founder
   A6  Payload conforms to schema?                    ✓
   ── envelope check: read_only ≤ reversible_until    ✓
   K3  RECEIPT INTENT WRITTEN ────────────────────────► A1 LEDGER
   │
   ▼  Warrant minted · attempt_budget = liberal (read_only)
RUNTIME ──► Gateway ──► Plugin ──► LocalExecutor ──► Action ──► filesystem
   │
   ▼
KERNEL.settle(warrant, succeeded) ──► outcome record ──► EVENT: INTENT_SETTLED
```

**Forty-seven times. No founder involvement. Each one receipted.**

### 4.4 Arm B — an Intelligence action (S3, one of 47)

```
REQUESTER ──► BROKER
   │            decides provider · derives CallBudget (MB038)
   │            admission: starved? occupied? ──► proceed
   │            → DecisionRecord
   ▼
KERNEL.authorize(ExecutionRequest)
   K1 · K2 · A1 · A2 · A3 · A4 · A5 · A6      as above
   A7  Broker decision + budget?               ✓ decision_ref attached
   A8  Admission verdict?                      ✓ not starved, not occupied
   K3  RECEIPT INTENT WRITTEN                  ──► A1 LEDGER
   │
   ▼  Warrant minted, carrying decision_ref and deadline
ai_infrastructure/execution ──► provider ──► transport ──► model
   │   (Broker logic untouched: no fallback, DecisionRecord stays true)
   ▼
KERNEL.settle(warrant, succeeded) ──► outcome ──► AI ledger reconciles by decision_ref
```

**Six of the forty-seven settle `failed` — unreadable scans.** They are recorded as failures, not swallowed, and they become criterion C3's "listed as unreadable."

**This is the section that validates the Kernel.** Arms A and B execute through entirely different machinery and produce entries in one ledger, distinguishable only by two extra attestations.

### 4.5 The one gated write (S4)

```
KERNEL.authorize
   A2  Reversibility Registry: reversible_until
       compensating_action = restore previous version
       undo_window = 24h
   A3  Permission System: grant from admission ──► RELAYED, not re-asked
       (ADR-0005/0006 · Constitution §15.3)
   ── envelope: reversible_until ≤ ceiling reversible_until   ✓ exactly at the ceiling
   K3  receipt intent
   ▼
Warrant · attempt_budget = 3 · undo window opens on settlement
   ▼
LocalExecutor ──► WriteFile ──► KERNEL.settle(succeeded)
```

**The envelope check is doing real work here.** Had the plan produced a `Filesystem.DeleteFile` step, the class would be `irreversible`, the ceiling is `reversible_until`, and **the Kernel would refuse to mint.** The founder's day-one approval is what makes that refusal automatic.

### 4.6 Verification and completion

```
VERIFICATION ── re-observes the ledger (never derives from the write result, ADR-0011)
   C1 parses                       → MATCHED
   C2 every link resolves          → MATCHED
   C3 47 = 41 extracted + 6 listed → MATCHED
   C4 mtime within 24h             → MATCHED
   → Evidence, stored, ids attached to the outcome records
   ▼
OBJECTIVE ENGINE
   4 of 5 criteria verified. C5 is `founder`.
   → cannot self-complete → judgment request for C5
```

### 4.7 Narration, vigilance, and the surface

```
D7 VIGILANCE ── receipts folder registered as a monitored domain
                last checked: now · healthy · 6 documents unreadable, named
   ▼
D1 NARRATION ── one generation
   ▼
D2 VOICE CHARTER ── validated: no exclamation, no celebration, no percentage,
                    ≤ 2 sentences per stop, figures bound to rendered values
   ▼
B2 RANKING ── the Sentry observation ranked against the open set
   ▼
SCREEN 01 ── the voice · one decision · the receipt
```

### 4.8 Learning — after settlement, never before

```
EVENT BUS (the existing one — mission_control/events.py, the only reporting shape)
   │
   ├──► L1 EXECUTION ── vendor V's invoice layout is stable; extraction ~2.3s;
   │                    scans without a text layer always fail — stop trying
   ├──► L2 PROVIDER ── local model handled 41/47; 6 needed the stronger one;
   │                   benchmark store updated (ADR-0018, ratified)
   └──► L3 BOUNDARY ── one objective, one approval, zero escalations.
                       Not enough to propose anything. Recorded. Waits.

   Subscribers return nothing. They cannot veto, delay, or modify. (Eng. Law V)
```

**Day 1 produces no rule proposal, and that is correct.** One data point is not a pattern, and a system that proposed a boundary after one interaction would be inferring consent — which VEDA 03 refuses by name.

---

## 5 · Timeline

### Day 1 — *"Prove it."*

One objective admitted. One approval. 94 warrants, 94 receipt pairs, 6 honest failures. One finding the founder did not know. Nothing changed that the founder did not authorize.

**Founder posture:** checking two of twenty-three links, then stopping.
**Trust moved because:** it was useful and it was honest about its edges in the same breath.

### Day 7 — *"I'm checking your homework."*

Four new invoices. Four filings, four approvals, each under a minute. The founder opens the ledger twice and finds it already current both times.

Vedra says nothing on the days nothing happened. **The quiet-day brief is a designed path, not an empty list** (VEDA 04 D6), and it reads: *"Nothing needs you. The receipts folder is current as of this morning."*

**Trust moved because:** it did not manufacture activity to seem valuable.

### Day 12 — the mistake

Vedra reports a total that is ₹41,000 too high. It catches this itself, before the founder does, and says so — §9.5 has the exact wording.

**Trust moved *up*, not down.** VEDA 01 §10 Ethics 2: never withhold information to preserve the founder's confidence, especially about its own errors. A system that only reports successes is a marketing surface.

### Day 30 — *"It learns me."*

Nine approvals, one rejection, a stable pattern with a boundary. The rule is proposed (§7). The founder accepts.

**This is inside the thirty-day window VEDA 04 R8 calls a product survival metric**, and this journey is designed to hit it rather than hope for it.

### Day 47 — the self-audit

The rule fires twice for the same vendor in three days. Vedra flags its own borderline call unprompted and proposes narrowing it (§9.6).

**Trust moved because:** nobody would have caught it.

### Day 90 — the review date

> *"You asked me for this ninety days ago. It's fired thirty-one times, you've looked at it four times, and the total has moved by ₹12,000. Still want it?"*

Not auto-renewed. Not auto-cancelled. Asked.

### Month 6 — *"Nothing needs me."* — §11

### 5.1 What the trust curve is actually made of

| Day | What earned it |
|---|---|
| 1 | Found something unknown · named what it could not read · **did not act** |
| 7 | Said nothing when there was nothing |
| 12 | Confessed an error first |
| 30 | Asked to be needed less, and showed its own ceiling |
| 47 | Reported a borderline call nobody would have found |
| 90 | Asked whether it should still exist |

**Not one row is a feature.** Every row is a refusal, a disclosure, or a question — which is the architecture's actual output.

---

## 6 · Learning

Specific, not generic. Each entry is a fact this journey produces that no other slice would.

### 6.1 L1 — Execution (skill-level, department-owned in the VEDA 05 sense; today Runtime-owned)

| Learned | Evidence | Effect |
|---|---|---|
| A PDF with no text layer never extracts | 6/6 failures, zero successes over 30 days | Stop attempting; classify as unreadable immediately and save the provider call |
| Vendor V's invoice layout is stable | 11 identical structures | A cheap deterministic parse works; no reasoning call needed |
| Extraction takes ~2.3s at this document size | 47 samples | The estimator stops over-quoting the refresh |
| The folder gains 3–5 documents a week | 30 days | Sets the freshness window D7 attests against |

### 6.2 L2 — Provider (Broker, ADR-0018, ratified)

| Learned | Evidence |
|---|---|
| The local model handles 41/47 documents at this quality bar | Verified extractions vs. verdicts |
| The 6 it fails on are the same 6 the stronger model also fails on | **The failure is the document, not the model** — a genuinely useful distinction that stops a pointless escalation to a more expensive provider forever |
| Cost per refresh at this mix | Ledger totals |

### 6.3 L3 — Boundary (Rule Proposal Miner, C3 — proposes only, never enacts)

**This is the learning that matters, and it is four specific facts:**

| Fact | Value |
|---|---|
| Approval rate on ledger filings | 9 of 9 |
| Median time-to-approve | 41 seconds |
| **The one rejection, and its subject** | ₹2,40,000 annual contract |
| The founder's stated reason | *"That one I want to look at properly"* |

**The rejection is worth more than the nine approvals.** Nine yeses establish a habit; they cannot establish a *limit*. The single no is what tells the miner where the ceiling is, and without it the proposal would have to guess — and a guessed cap is the malformed rule VEDA 04 C1 rejects at definition time.

VEDA 03 states this precisely: the proposal arrives *"with the evidence strip, the median time-to-approve, and the one rejection that sets the ceiling."* This journey produces all three as a by-product of ordinary use.

### 6.4 Founder-specific understanding

Not rules. Semantic memory (VEDA 04 M3), versioned, used to make narration sound like the founder's own company:

- They say **"burn,"** not "spend." Vedra adopts it.
- They look at anything over **₹50,000**, regardless of category.
- They open the ledger **Monday mornings**. The refresh is scheduled Sunday night.
- They do not want a total on the dashboard. They asked for it in a file.

### 6.5 What is deliberately not learned

- **Not** that the founder wants unused subscriptions cancelled. They never said so, and inferring it from "you flagged Sentry and they didn't object" is exactly the silent-consent inference VEDA 03 refuses.
- **Not** a preference for any vendor.
- **Not** anything from the six unreadable documents. Absence of data is not data.

---

## 7 · Rule Proposal

### 7.1 The proposal, as the founder sees it

> "You've approved nine of nine filings, usually within a minute. The one you declined was the ₹2,40,000 annual contract.
>
> Want me to stop asking when it's a vendor already in the ledger and under ₹10,000? I'd cap it at twenty filings or ₹1,00,000 a month, never a new vendor, never a contract, and it would expire in thirty days unless you renew it."

### 7.2 The five mandatory parts

VEDA 01 §10 and VEDA 03 both make rule anatomy non-negotiable. All five are present, and `define()` would reject the rule if any were missing.

| Part | Value | Why this value |
|---|---|---|
| **Trigger** | A filing into `commitments.md` for a vendor already present, amount < ₹10,000 | Narrow and boring. Derived from the nine, bounded by the one. |
| **Blast radius** | ≤ 20 filings **and** ≤ ₹1,00,000 of filed value per calendar month | A per-item cap alone is how a large sum leaves in many small pieces. **Both a count and a value cap**, because filings are not purely monetary. |
| **Never-clause** | Never a new vendor · never a contract · never anything that changes what the company is committed to · never irreversible | Displayed alongside the rule, always |
| **Trial** | 30 days, expires unless renewed | VEDA 04 C2 — a permission with no end date cannot be persisted |
| **Receipt** | Every firing recorded and reviewable; **24h undo** because the founder was not in the room | VEDA 03's undo grading: rule firings get the longest window, precisely because nobody was present |

### 7.3 Why now

**Nine consistent decisions, one boundary-setting rejection, thirty days of elapsed time.** All three are needed. Nine yeses without the no gives a habit with no known limit. The no without the yeses gives a limit with nothing to bound. Thirty days is what makes it a pattern rather than a busy week.

### 7.4 Why not earlier

**Day 1:** one approval. Proposing from one data point is inferring consent.
**Day 7:** four approvals, all similar, no rejection. **A rule proposed here would have no defensible cap** — and VEDA 04 C1 makes a rule without a cumulative cap malformed at definition time, so the system literally could not construct it.
**Day 20:** eight approvals, and the rejection had just occurred. Proposing immediately after a "no" reads as arguing with it.

### 7.5 Why not later

VEDA 01 §4 requires the first accepted proposal inside thirty days, and VEDA 04 R8 rates the miner's time-to-first-viable-proposal a **product survival metric, not an engineering nicety** — if it needs ninety days of history, the account is lost before compounding starts.

**This journey is chosen partly because it generates a proposable pattern in under thirty days by ordinary use.** A slice that could not would fail the architecture on a dimension no test would catch.

### 7.6 How it earns permission

It does not argue for itself. VEDA 01 §10 Ethics 1: an intelligence arguing for its own power is disqualified from being believed.

**It presents evidence and shows its own limits in the same breath** — the nine, the one, the caps, the exclusions, the expiry. The founder's decision is between one boundary and no boundary, not between trusting Vedra and doubting it.

### 7.7 What happens if it is declined

Recorded with the reason. The pattern class is suppressed for a period — the system does not re-ask next week with better phrasing. **A proposal declined and re-proposed is a negotiation, and Vedra does not negotiate for authority.**

---

## 8 · Dashboard State

VEDA 03 Screen 01 v2, exactly. Three elements, one viewport, no scroll, no navigation rail, no badges.

### 8.1 Day 1, moments after the objective completes

```
 ╔═════════════════════════════════════════════════════════════════════╗
 ║                                                                     ║
 ║   [the tree, behind the words, weighted left, dimmed, warming       ║
 ║    slightly amber because judgment is pending]                      ║
 ║                                                                     ║
 ║                                                                     ║
 ║   You're committed to ₹1,84,600 a month                    ← 38px   ║
 ║   across twenty-three services.                              prose  ║
 ║                                                                     ║
 ║   ─────────────────────────────────────────────────────────────     ║
 ║                                                                     ║
 ║   Sentry renews Friday — ₹7,200.                       ← THE ONE    ║
 ║   I can't find any usage since March.                    DECISION   ║
 ║                                                                     ║
 ║   If I do nothing, it renews Friday 00:00.                          ║
 ║   Reversible until then. I won't cancel it either way                ║
 ║   without you saying so.                                            ║
 ║                                                                     ║
 ║        Look into it        Leave it        Remind me Thursday       ║
 ║                                                                     ║
 ║   ─────────────────────────────────────────────────────────────     ║
 ║                                                                     ║
 ║   47 documents read · 6 I couldn't                     ← RECEIPT    ║
 ║                                                          low        ║
 ║                                                          contrast   ║
 ║   ──────────────  ──────────  ────────────                          ║
 ║   mission control   memory      settings              ← 3 doorways  ║
 ╚═════════════════════════════════════════════════════════════════════╝
```

### 8.2 What is deliberately absent

| Absent | Refused by |
|---|---|
| Objective count, active list, progress bar | Objective Engine §9.4 — not emitted |
| Any badge or unread count | VEDA 03 — *"a number on a nav item is an obligation"* |
| "1 objective completed" | Activity metric. The receipt says what was read, not what was completed. |
| A percentage anywhere | Objective Engine §7.2 |
| A total-savings or value-delivered figure | Nothing in VEDA 03 asks for it, and it would be the system arguing for itself |
| Task list, plan DAG, warrants, receipts internals | One level down, in Mission Control, for when the summary is not trusted |

### 8.3 Note on the receipt line

*"47 documents read · 6 I couldn't"* — **the second number is not a failure count.** It is the thing that makes the first number believable, and it is rendered in the same weight for that reason. A receipt showing only successes is a marketing surface.

### 8.4 Day 31 — the trust moment lives inside the receipt

The founder opens the low-contrast receipt, where the rule proposal is waiting. Not pushed. Not a notification. **VEDA 03 places the emotional peak here deliberately** — the founder finds it while checking, rather than being interrupted by it.

### 8.5 Month 6

```
 ║   Nothing needs you.                                                ║
 ║   The commitments file is current as of this morning.               ║
 ║                                                                     ║
 ║   31 filings handled without you · 1 I asked about                  ║
```

**The screen got emptier.** VEDA 03: this screen should get emptier every month, and that is not a degraded state — that is the product having won.

---

## 9 · Failure Behaviour

Six failures. Each shows how trust is protected, not merely how the error is handled.

### 9.1 Permission denied

The founder declines the write grant at admission.

> *"Understood. I won't write anything. I can still read the folder and tell you what I find — I just won't keep a file. Want me to?"*

**Behaviour:** objective stays in `DRAFT`, nothing executes, nothing persists as a side effect (Constitution §15.1). Vedra offers the largest thing it can still do, once, and does not ask again.
**Trust protected by:** the refusal costing the founder nothing and producing no sulk, no retry, no rephrased second attempt.

### 9.2 Execution failed — provider unavailable mid-run

Ollama dies after document 22.

> *"I got through twenty-two of forty-seven. The model I was using stopped responding, so I stopped rather than guess at the rest. The file has what I have, marked incomplete. Want me to finish when it's back?"*

**Behaviour:** Broker returns a structured refusal and **never silently falls back** to another provider — a substituted provider would make the `DecisionRecord` a lie and corrupt every future benchmark. Warrants for documents 23–47 are never minted. The objective enters `WAITING · awaiting_resource` with a declared `expected_by`. C3 fails, so the objective does not complete.
**Trust protected by:** a partial result labelled partial. The dangerous version of this failure is a ledger that looks complete and is not.

### 9.3 Receipt ledger unavailable

> *"I've stopped. I can't record what I'm doing right now, and I won't do things I can't account for. Nothing has changed."*

**Behaviour:** K3 fails ⇒ no warrant ⇒ nothing executes. VEDA 04 A1, verbatim: no exceptions, no buffering, no fire-and-forget.
**Trust protected by:** the system preferring to be useless over being unaccountable, and saying so plainly.

### 9.4 Learning unavailable

**Behaviour:** nothing. Execution does not know. Zero subscribers is a valid configuration.
**Trust protected by:** the founder never experiencing a delay caused by a component that is forbidden from acting.

### 9.5 Vedra is wrong — the mistake protocol

Day 12. Two invoices in USD were read as ₹. The total was overstated by ₹41,000. Vedra finds it during a routine re-verification, before the founder does.

> *"I overstated your monthly commitment by ₹41,000 since the ninth.
>
> Two invoices were in dollars and I read them as rupees.
>
> The file is corrected — it's ₹1,84,600, not ₹2,25,600.
>
> I've added a currency check; if a document doesn't state its currency plainly, I'll ask instead of assuming."

**Impact → cause → fix → prevention. One sentence each, in that order** (VEDA 04 D3). Disclosed by detection, not by query. It routes to narration on a path that ranking cannot deprioritise, because ranking is a quality-scoring mechanism and D3 forbids one gating this.

**Trust protected by:** this being the single highest-value moment in the entire journey. VEDA 03: an AI that reports only successes is a marketing surface; one that surfaces its own errors when nobody would have caught it is a colleague.

### 9.6 The rule fires badly — self-audit

Day 47. The rule fires twice for the same vendor in three days.

> *"I filed two Atlassian invoices this week under your rule — ₹4,100 and ₹3,900. The rule allowed it, but two in three days from one vendor might not be what you meant. Want me to add a per-vendor limit of one a month?"*

**Behaviour:** C5 self-audit, unprompted, cannot be disabled, rate-limited to invisibility, or suppressed by a quality metric. **This module exists specifically to produce output that looks bad.**
**Trust protected by:** the founder learning that the boundary is watched by the thing inside it.

### 9.7 The rule is rejected

> *"Understood. I'll keep asking."*

Six words. No re-proposal next week, no rephrasing, no partial version. Recorded with the reason; the pattern class suppressed for a period.
**Trust protected by:** a no meaning no. A system that re-asks has revealed that the first ask was a negotiation.

### 9.8 The pattern across all seven

| Failure | Vedra's move |
|---|---|
| Permission denied | Offers less, once |
| Provider died | Stops, labels partial, asks |
| Ledger down | Refuses to act at all |
| Learning down | Nothing visible |
| Own error | Confesses first, fixes, prevents |
| Bad rule firing | Reports itself, proposes narrowing |
| Rule rejected | Six words, no argument |

**Not one response argues, minimises, apologises twice, or asks for another chance.** VEDA 01 §8's single-apology rule and its ban on persuasion copy are load-bearing here — every one of these moments is where a lesser system would try to recover the relationship with language instead of behaviour.

---

## 10 · Demo Version

VEDA 01 §11: ninety seconds, six scenes, a time-lapse of a relationship rather than a tour.

### 10.1 The six scenes, on this one thread

| Scene | Content | Real / Simulated |
|---|---|---|
| **1 · Cold open** | No product. Two numbers about the viewer's own life: how many decisions they signed last quarter; how many took under four minutes. | Real, viewer-supplied |
| **2 · The noise** | Day one. The receipts folder — 47 documents, two years, nothing extracted. Deliberately uncomfortable. | **Real** |
| **3 · The moment** | *"Keep a current picture of everything I'm committed to paying."* Forty seconds. Twenty-three commitments, six honest failures, one flagged renewal. **The viewer types the objective and grants the approval themselves.** | **Real, live, unscripted** |
| **4 · The compound** | Day 31's rule proposal, with the nine approvals, the one rejection, the caps and the expiry visible beside it. | **Simulated timeline, real mechanism** |
| **5 · The slope** | The one chart: filings handled without the founder, rising over months. | **Simulated data, real metric** |
| **6 · The silence** | *"Nothing needs you. The commitments file is current as of this morning."* Held far past comfort. | Real render |

### 10.2 Real

The extraction, the ledger, the six failures, the approval, the receipt, the refusal to cancel Sentry. **Scene three runs live against the viewer's own folder if they have one.** A demonstration watched is forgotten; this is the only moment where the viewer is the principal rather than the audience.

### 10.3 Simulated — and labelled

Only the passage of time. Scenes 4 and 5 compress six months.

**Via E2, the Deterministic Demo Tenant** — a first-class runtime mode with fixed outcomes over real data shape, **labelled as such**, not a fixtures file and not a mock. The mechanisms are the real ones; only the clock is not.

### 10.4 Intentionally hidden

Warrants, receipt internals, the plan DAG, provider identity, the Kernel, attestations, both pipelines.

**Not because they are unimpressive — because showing them would contradict the product.** VEDA 01 §3: the AI is the interface. A demo that shows the machinery is selling a framework. This is selling a morning.

### 10.5 Two rules inherited

**The mature product is not shown first.** Scene 6's calm is meaningless to someone who has not seen scene 2. Emptiness is the conclusion, not the opening.

**The sales demo opens on Mission Control, not Screen 01.** VEDA 03 states this explicitly: density signals value to a stranger, restraint signals value to an owner. Screen 01 is designed for the owner on day 200.

---

## 11 · Founder Edition — the same journey, six months on

Nothing new has been built. Everything is different.

### 11.1 What the founder does

They no longer state the objective. It has been running for six months.

They open Vedra on Monday morning — the habit Vedra learned in week three and quietly scheduled the refresh around.

> *"Nothing needs you. Burn is ₹1,79,400, down ₹5,200 since March. Everything's current as of six this morning."*

They close it. Elapsed: four seconds.

### 11.2 What accumulated

| Then | Now |
|---|---|
| Asked about every filing | One rule, narrowed once by its own self-audit, renewed twice by the founder |
| *"Commitments"* | *"Burn"* — the founder's word, adopted in week two |
| 6 unreadable documents | 2 — the scan class was learned and pre-flagged on arrival, not attempted and failed |
| Extraction via the stronger model | Local model for 44 of 47, with a measured quality bar. Cost per refresh down 60%. |
| One monitored domain | Still one. **Vedra did not expand its own scope.** |
| Two touches per week | One touch per month |

### 11.3 What it feels like

**It knows things about the company nobody wrote down.** That the ₹2,40,000 contract is the one the founder always wants to see. That November is when three renewals cluster. That a new vendor appearing is worth a sentence and a familiar one is not.

**It has never once been wrong in a way it did not report first.** Two errors in six months, both disclosed before discovery, both followed by a prevention that held.

**It asks for less than it did.** The rule was narrowed, not widened. The founder noticed that.

### 11.4 The annual audit, at month twelve

Unprompted, non-disableable. It will say what Vedra currently decides without asking, which rules have not been examined since granted, what the founder would lose if it vanished, and **where it believes it holds too much.**

The founder will read that last section and find that Vedra has flagged its own filing rule as broader than the founder's actual behaviour justifies.

**That is what six months of this architecture buys**: not more capability, but an intelligence that keeps making itself easier to stop.

### 11.5 The tree

One branch, from one rule grant, six months deep. Slightly thinned where the rule was narrowed — history not erased, because a founder should be able to see that they once trusted something more broadly and pulled it back.

**Nothing Vedra did grew it.** Only the founder's permission did. That is the one measure in the product that the product itself cannot move.

---

## 12 · Constitutional Validation

Every frozen principle this journey exercises, and where.

### 12.1 VEDA 01 — Experience

| Principle | Clause | Exercised |
|---|---|---|
| Vigilance is the primary load | §1 | The objective addresses a question the founder has carried for 11 months |
| Founders think in constraints | §2 | Money, not filing, is the subject |
| The AI is the interface | §3 | The founder speaks to Vedra; the dashboard explains what it did |
| Humans provide judgment | §3 | C5 founder verifier; Sentry not cancelled; rule accepted, not assumed |
| The boundary is the product | §3 | Day 31, made visible |
| First launch: *"Prove it"* | §4 | Day 1, forty seconds, six honest failures |
| First month: *"It learns me"* | §4 | Day 30 proposal, inside the window |
| Approvals carry the quartet | §5 | §3.4 and §8.1 |
| Silence has a stated default | §5 | *"If I do nothing, it renews Friday 00:00"* |
| Notifications abolished | §5 | The proposal waits inside the receipt |
| Voice: no exclamation, no celebration | §8 | Every line in §3 and §9 |
| Mistakes: impact→cause→fix→prevention | §8 | §9.5 |
| Rules: five mandatory parts | §10 | §7.2 |
| Never acts irreversibly without contemporaneous permission | §10 Ethics 3 | Sentry, and the consequence ceiling that makes it mechanical |
| Never withholds to preserve confidence | §10 Ethics 2 | §9.5, disclosed by detection |
| Never proposes scope expansion for itself | §10 Ethics 1 | §7.6; §11.4's self-flagging |
| Can say what it may not do | §10 Ethics 5 | *"I won't cancel or pay anything"* — stated at admission |
| Silent learning is surveillance | §10 | Every learned fact is narrated |
| Tree: founder grows it | §9 | §11.5 |

### 12.2 VEDA 03 — Founder Dashboard

| Principle | Exercised |
|---|---|
| One decision, in full, one at a time | §8.1 |
| Rank by consequence, never time | The Sentry item outranks the filings |
| Three tiers: Needs-you / Sweep / Auto | Day 1 needs-you; day 31+ auto-handled receipts |
| Rules proposed, never authored | §7 |
| Rule anatomy non-negotiable, five parts | §7.2 |
| Undo graded by who was in the room | Rule firing 24h; the founder was not present |
| The trust moment lives in the receipt | §8.4, §9.6 |
| Screen gets emptier every month | §8.5 |
| No badges, no counts, no gamification | §8.2 |
| Demo opens on Mission Control | §10.5 |

### 12.3 VEDA 04 — Architecture Requirements

| Module | Exercised |
|---|---|
| A1 Receipt Ledger | 94 intent/outcome pairs, day 1 |
| A2 Reversibility Registry | `reversible_until` with a real compensating action and a 24h window |
| A3 Override | Available throughout; §9's failures never bypass it |
| B1 Consequence Engine | The Sentry quartet |
| B2 Ranking | One item surfaced from the open set |
| B3 Escalation Router | `novel` fires on Sentry; `irreversible` would block cancellation |
| B4 Silence Defaults | *"renews Friday 00:00"*, re-verified before firing |
| B5 Evidence Graph | Every ledger entry links to its source document |
| C1 Standing Rule Engine | §7.2's five parts, cumulative cap enforced at definition |
| C2 Expiry Daemon | 30-day trial |
| C3 Proposal Miner | Day 31, from 9+1 |
| C5 Self-Audit | Day 47 |
| D1 Narration | One generation, two renderings |
| D2 Voice Charter | Every utterance |
| D3 Mistake Protocol | §9.5 |
| D6 Brief Composer | Day 7's designed quiet-day path |
| D7 Vigilance Attestation | *"current as of this morning"* — only sayable because the domain was checked |
| E1 Provenance | Day 90's *"you asked me for this ninety days ago"* |
| M1–M3 Memory | Receipts permanent · decisions with reasons · *"burn"* |

### 12.4 Constitution

| Principle | Exercised |
|---|---|
| §2.1 Intent over prompts | Structured intent, one clarifying question |
| §2.2 Outcome over output | Completion by verified criteria, never by task count |
| §2.4 Approval before important actions | The write grant |
| §2.5 Local-first | Local model handles 41/47 |
| §15.3 One approval per mission | One approval, 94 warrants, relayed |
| §10 Verification independent of execution | Ledger re-observed, never derived from the write result |
| §5.7 Broker decides which provider | The Planner and the extraction both ask; neither chooses |
| §5.2 One grant ledger | Both pipelines, one Permission System |

### 12.5 Kernel and Objective Engine

| Guarantee | Exercised |
|---|---|
| No execution without an objective | K1, 94 times |
| No execution without classification | A2; `read_only` vs `reversible_until` |
| No execution without a receipt written first | K3, 94 times |
| Envelope bounds every warrant | Cancellation refused at the ceiling |
| One warrant, N attempts | The write's attempt budget of 3 |
| Irreversible never auto-retried | Never reached — nothing irreversible is minted |
| Learning cannot block | §9.4 |
| V2: completion must be checkable | The one clarifying question in §3.3 |
| Binary completion, no percentage | 4 of 5 criteria, described not scored |
| Founder verifier prevents self-completion | C5 |
| System proposes, founder admits | §7 |

### 12.6 Not exercised — stated honestly

| Not exercised | Why |
|---|---|
| Irreversible execution | Deliberately. The ceiling refuses it. Needs a second objective. |
| C6 Delegation | One principal |
| C7 Dependency Audit | Annual; arrives at month 12 |
| C4 Boundary Service at scale | One rule, one branch |
| B6 Confidence Model | Lightly — *"I can't find any usage"* |
| E3 Export | Not on this path |
| Multi-objective conflict, supersession | Single objective by design |

**A slice that claimed to exercise everything would be a slice designed to look complete rather than to be small.**

---

## 13 · Risks

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| **R1** | **The slice ships before the Trust Spine and becomes a demo with no receipts.** The extraction is impressive on its own, and the temptation to show it early will be strong. | **Critical** | The journey is an **acceptance test for the spine**, not a feature. Day-1 run 1 is invalid unless every one of the 94 actions wrote an intent before its effect. |
| **R2** | **The 30-day proposal does not arrive.** C3 needs 9+1 with a real rejection. If the founder approves everything, there is no ceiling and no proposable rule. | **Critical** | Design the miner for low-N with tight caps and short trials (VEDA 04 R8). If no rejection occurs by day 25, the correct behaviour is **no proposal**, not a guessed cap. A missing proposal is a finding; a fabricated cap is a malformed rule. |
| **R3** | **The six unreadable documents get hidden.** They look like failure and someone will want the number to be 47. | **High** | C3 makes completeness a **verified criterion**. Suppressing them fails verification, and the objective cannot complete. |
| **R4** | **Vedra cancels something.** The single trust-ending event available in this journey. | **High** | The consequence ceiling is `reversible_until` and the Kernel refuses to mint above it. Not a policy — a refusal at K1's envelope check. |
| **R5** | **A total-savings figure appears on the dashboard.** Irresistible, and it would be the system arguing for its own value. | **High** | §8.2's absence list. Nothing in VEDA 03 asks for it. |
| **R6** | **The mistake in §9.5 is never actually built.** D3 is easy to defer and its absence is invisible until the first real error. | **High** | Day 12 is a **required run**, with a deliberately mis-currencied document injected. If the disclosure does not fire before the founder queries, the journey has failed. |
| **R7** | **Extraction quality is worse than assumed.** 41/47 is an estimate, not a measurement. | Medium | C3 makes the ratio visible rather than assumed. A worse ratio is honest output, not a broken slice — but if it is below roughly half, the objective is not yet useful and should be said so. |
| **R8** | **The founder's folder does not exist.** Not every founder has one. | Medium | The demo's scene 2 needs a real folder. Where there is none, the deterministic tenant supplies one, labelled. |
| **R9** | **The journey becomes a script.** Rehearsed to always produce ₹1,84,600 and always flag Sentry. | Medium | Scene 3 runs live on the viewer's own data. **A demo that cannot survive real input is a demo of nothing.** |
| **R10** | **Success is measured in objectives completed.** | Medium | The only metric is **judgments required per objective, falling** — and it is subordinate to C4's autonomy ratio, which remains the headline. |

---

## 14 · Final Recommendation

### 14.1 Adopt this as the first vertical slice, run four times

Once at the end of each phase of the Implementation Blueprint, each run exercising one more layer. Run 4 — the rule proposal, on a real 30-day clock — is the one that proves the product rather than the plumbing.

### 14.2 The three things that make it a validation rather than a demo

**It exercises both pipelines.** Filesystem and provider, one ledger, distinguishable only by two attestations. The entire justification for the Kernel is that it governs both, and no smaller slice tests that.

**It produces a rule proposal by ordinary use.** Not a scripted one. Nine approvals and one rejection arise because a founder behaves like a founder, which means the thirty-day survival metric is *measured* rather than *hoped for*.

**Its most important moments are refusals.** Not cancelling Sentry. Naming six unreadable documents. Stopping when the ledger is unavailable. Confessing an error first. Six words when the rule is declined. **The architecture's actual output is restraint, and this journey is built to make restraint visible.**

### 14.3 What must be true before run 1

1. Every one of the 94 actions writes a receipt intent before its effect — verified by test
2. Every capability used carries a reversibility class; the ledger write names a working compensating action
3. The consequence ceiling is enforced at the Kernel, not by convention — provable by attempting a delete and observing the refusal
4. The Voice Charter validates every utterance in §3 and §9
5. D7 attests the receipts folder before any *"current as of this morning"* is spoken

**If any of the five is not true, run 1 is invalid regardless of how well the extraction works.**

### 14.4 The moment this is designed to produce

Not the forty seconds. Not the ₹1,84,600.

**The founder clicking two of twenty-three source links, finding both correct, and not checking the third.**

That is trust — not a feeling the product cultivated, but a position the founder moved on their own, because they were given honest edges, a visible boundary, and a system that told them what it could not do before they asked.

> **Everything in this architecture exists to make that one small decision safe to make. The rest is what happens after they make it.**

---

*Architecture validation specification. No VEDA created, modified, or reinterpreted; no engine redesigned; no constitutional principle invented. Every capability referenced is shipped as of Miracle 035 or scheduled in the Implementation Blueprint. All dialogue conforms to VEDA 01 §8. Verified against `src/master_agent/` and `MIRACLE_LEDGER.md` as of 2026-08-05.*
