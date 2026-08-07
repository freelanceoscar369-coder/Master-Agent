# Objective Engine Specification v1.0

**Type:** Implementation architecture. Not a VEDA. Nothing frozen is modified.
**Date:** 2026-08-05
**Designs:** the Objective Engine only. Its responsibility ends at admission into the Constitutional Kernel.
**Assumes as existing and correct:** Constitutional Kernel Specification v1.0 · Constitutional Execution Path Report · VEDA 01–04 · Constitution §§2.2, 3.1, 5.3, 10, 15, 17 · ADR-0011, 0019.
**Excluded:** VEDA 05 (under amendment). Nothing here depends on it.
**Redesigns nothing:** Kernel, Broker, Permission System, Learning, Receipts, Planner, Mission Control.

**Two genuine conflicts were found during design. Neither is resolved here.** §13.1 documents both and recommends the smallest possible amendment for each. One of them is an error in the Kernel Specification, which is mine.

---

## 1 · Executive Summary

### 1.1 The one sentence

> **The Objective Engine is the constitutional owner of *why*. It admits outcomes, holds their envelopes, decides when they are genuinely complete, and hands the Kernel the anchor without which nothing may be minted.**

It plans nothing, schedules nothing, and executes nothing. Those belong to the Planner, Mission Control, and the Kernel respectively — all of which already exist.

### 1.2 The four decisions this specification rests on

**One · Completion is binary, verified, and never a percentage.** Constitution §2.2 already settles it: a Mission is done only when Verification confirms real-world state matches the success criteria — never when a model produces text, and never when a task counter reaches its total. Progress may be *described* ("three of five criteria met"); it is never *scored*. VEDA 03 says of the tree what applies equally here: a single number summarising something complicated is always wrong and always believed.

**Two · An objective whose completion is not checkable is refused at validation.** This is the entire defence against objectives silently becoming tasks. It will be the most-argued rule in the document, and it is the load-bearing one.

**Three · Composition is capped at one level, by type, not by guideline.** An `Objective` is completable. An `Objective Set` groups. **A Set cannot contain a Set.** Arbitrary nesting is how every outcome system becomes a work-breakdown structure, and a founder looking at a tree is a founder looking at a task manager — which VEDA 03 refuses.

**Four · The system may propose objectives; only the founder admits them.** If the system could mint its own objectives, *"no execution without an Objective"* would be satisfiable by minting one, and the Kernel's first guarantee would be decorative. **Objective admission is an authority event, subject to the same discipline as any other grant.**

### 1.3 What the Objective Engine gives the Kernel

Not per-action calls — the Runtime makes those. The Objective Engine publishes an **Admission Record** the Kernel's K1 check reads, containing the objective's identity, state, and **envelope**: budget, deadline, and **consequence ceiling**. A warrant that would exceed any of the three is refused by the Kernel, not by the Objective Engine.

Termination is symmetrical and reuses machinery that already exists: **cancelling an objective is `kernel.invalidate(scope=objective_id)`** — the same operation as the Override, at a narrower scope. That is why the Kernel's `invalidate()` took a scope parameter.

### 1.4 The thing this specification is trying to prevent

A founder ending the day reading a list of what got done.

Every structural choice below — binary completion, no percentages, one level of composition, no objective counts on the first screen, waiting as a first-class state rather than a stalled one — exists so the honest answer to *"what moved forward?"* is a sentence about outcomes and not a report about activity.

---

## 2 · Philosophy

### 2.1 Why the Objective is the anchor and not the request

A request is what a person said. An objective is what they wanted. These are different, and systems that conflate them end up executing sentences.

The Constitution already draws this line at §3.1: the Intent Layer produces *structured* intent — goal, constraints, context, success criteria — precisely so the Planner never guesses. The Objective Engine extends the same discipline one level up: **structured intent becomes an admitted objective only when its outcome is stated in a form that can be checked without asking anyone's opinion.**

That single gate is what makes *"what objective is being advanced?"* answerable rather than rhetorical.

### 2.2 Why activity is the enemy

Every metric a system can easily produce measures activity: tasks completed, capabilities invoked, objectives created, actions per hour. All of them go up when the system is doing more, which is not the same as the founder needing it less.

VEDA 01 §12's warning applies directly: a product whose success is measured in being needed less will look, by conventional instrumentation, like a product that is failing.

**The Objective Engine therefore emits no activity metric of any kind.** Not to the dashboard, not to logs consumed by the dashboard, not as a derived field. §9.4 states what it does emit, and the list is short.

### 2.3 Why an objective must be able to be refused

An engine that admits everything is a queue. The Objective Engine's most valuable single behaviour is refusing at validation — *"I can't tell when this would be done; here's what I'd need to know"* — because an objective admitted with a vague completion criterion produces a mission nobody can end.

This is not friction. It is the moment the system does the thinking the founder would otherwise have to do at the end, when it is expensive, instead of at the start, when it is free.

---

## 3 · Objective Definition

### 3.1 What an Objective is

> **A change in the world the founder wants, stated so that its completion can be checked without asking anyone's opinion, bounded by an envelope the founder approved, and owned by the founder from admission to termination.**

Four clauses, each doing work:

- **a change in the world** — not a change in the system's internal state, not a conversation
- **the founder wants** — proposed by anyone, wanted by exactly one authority
- **completion can be checked** — Constitution §2.2's verification requirement, pulled forward to admission time
- **bounded by an envelope** — budget, deadline, consequence ceiling; approved once, relayed downward per §15.3

### 3.2 What an Objective is not

Each of these is a real thing that must exist somewhere. Naming where prevents it becoming an objective by default.

| Not an objective | What it actually is | Where it lives |
|---|---|---|
| *"Create a folder"* | A **means**. A step toward an outcome. | The Planner's DAG |
| *"What's my runway?"* | A **Query Objective** — a distinct, read-only class (§3.6) | Admitted, but with a `read_only` consequence ceiling |
| *"I like things tidy"* | A **constraint** or a standing-rule input | Rule Engine, Memory |
| *"You can do OCR"* | A **capability** | Capability Registry |
| *"You should archive exports"* | A **proposal** for an objective | Requires founder admission (§3.5) |
| *"Keep exports tidy, always"* | A **Standing Intention** — a template that mints objectives on a schedule | §3.7 |
| *"Launch the product"* | An **Objective Set** if its parts complete independently; an objective only if it has its own checkable criteria | §6 |
| *"Be more efficient"* | Nothing yet. No checkable outcome ⇒ refused at validation, with a question. | Returned to the founder |

### 3.3 Ownership

> **The founder owns every objective, unconditionally, from admission to termination. Ownership is never delegated, transferred, or inferred.**

The system may propose. The Planner may decompose. Departments (when VEDA 05 settles) may execute. **None of them owns the outcome.** VEDA 01 §3 is explicit that humans provide judgment, and *"is this still what I want?"* is judgment.

Practical consequence: no objective may be completed, cancelled, superseded, or have its criteria changed by any component. Those are founder acts, or they are escalations.

### 3.4 Lifetime

**The objective record is permanent.** VEDA 04 M1 makes receipt retention a trust obligation rather than a cost decision, and every receipt anchors to an objective. An objective whose record expired would orphan its receipts.

**The objective's *active* life is bounded.** Every objective carries either a `due_date` or a `review_date`. **Neither may be absent.** An objective with no end is an obligation with no end, and VEDA 04 C2's principle — no permission without an expiry — applies with equal force to a commitment.

At the review date, an objective that has not progressed surfaces once, in the founder's own words, asking whether it is still wanted. It is not auto-cancelled: an objective quietly dropped is worse than one that asks.

### 3.5 Creation and admission — the loophole that must not exist

| Creator | Admission requires |
|---|---|
| Founder, directly | Validation only. The founder stating an outcome is the authority. |
| System, from an observed pattern | **Founder admission**, or an active standing rule with a cumulative cap and an expiry that explicitly covers objective creation |
| Another objective (a dependency it discovered) | **Founder admission** if it widens the parent's envelope; automatic if it fits inside it |
| External trigger (schedule, connector) | Admission under the Standing Intention that created it (§3.7), which the founder admitted once |

**Why this matters more than it looks.** The Kernel guarantees no execution without an objective. If the system could create objectives freely, that guarantee reduces to *"no execution without the system first writing down a reason,"* which is not a guarantee at all.

**Objective creation is therefore an authority event, governed exactly like any other grant.** A system that wants to do something it was not asked to do must ask — which is VEDA 01 §10's entire architecture, applied one level up from actions.

### 3.6 Query Objectives

Questions need answering, and answering may require a provider call — which is an action, which requires an objective. Rather than exempting queries from the Kernel, they become a class of objective.

| Property | Value |
|---|---|
| Consequence ceiling | **`read_only`, mechanically. It cannot mint a write warrant.** |
| Success criterion | The question was answered with sourced evidence, or honestly declared unanswerable |
| Lifecycle | Admitted and terminated within one interaction; no waiting state |
| Founder visibility | None as an objective. The founder sees an answer. |

**Why this is not a bypass:** the `read_only` ceiling is enforced by the Kernel, not by convention. A Query Objective that tried to authorize a file write would be refused at K1's envelope check. Everything expensive or consequential remains a real objective.

### 3.7 Standing Intentions

*"Keep the exports folder tidy"* is not an objective — it never completes. It is a **template that mints objectives**.

| Property | Value |
|---|---|
| What it is | A named intention plus a trigger, an envelope, and a criteria template |
| Admission | Founder admits the intention once. **It carries a cumulative cap and an expiry**, exactly like a standing rule, and for the same reason. |
| What it produces | One ordinary objective per firing, inheriting the template's envelope |
| Review | At expiry, surfaced with its firing history, renewed or not |

This is what makes the vertical slice work: *"archive exports older than 30 days,"* stated once, minting a monthly objective, is the shape the Rule Proposal Miner can learn from inside the thirty-day window VEDA 04 R8 calls a product-survival metric.

### 3.8 Termination — four ways, all terminal, none reversible

| Outcome | Means | Who decides |
|---|---|---|
| **Completed** | Every criterion verified. Machine criteria produced matching Evidence; founder criteria received a verdict. | Verification + founder, never the Objective Engine alone |
| **Failed** | A criterion cannot be met, and this is established rather than assumed | Escalated to the founder; the Engine proposes, the founder confirms |
| **Cancelled** | The founder no longer wants it, or its premise evaporated | **Founder only** |
| **Superseded** | Replaced by a revised version. **The original is retained.** | Founder |

**No objective self-completes on a timer, a task count, or a model's opinion.** Constitution §2.2 forbids the last; the other two are how completion becomes a lie.

**Partial outcomes are recorded, never averaged.** An objective failing at 80% is `failed` with an explicit record of which criteria were met, what artifacts exist, what was spent, and what is salvageable. It is never `completed` at 0.8.

---

## 4 · Lifecycle

### 4.1 The constraint

Constitution §5.3 freezes the Mission state machine as `draft → planned → awaiting_approval → executing → verifying → completed | failed | cancelled` and names Shared Infrastructure its permanent home.

**This specification does not design a parallel lifecycle.** It uses the frozen one, and identifies exactly **two** states it genuinely lacks. Both are additive; no existing state changes meaning and no existing transition is removed. §13.1 states them as an amendment request.

### 4.2 The lifecycle

```
                         ┌─────────┐
    founder states  ────►│  DRAFT  │  the outcome exists as words
    or system proposes   └────┬────┘
                              │  VALIDATION — is completion checkable?
                              │  ├─ no  ──► returned with a question (not a failure)
                              │  └─ yes ──┐
                              ▼           │
                    ┌──────────────────┐  │  ADMISSION — envelope set,
                    │     PLANNED      │◄─┘  authority resolved, contract held
                    │  = ADMITTED      │
                    └─────────┬────────┘     ── the Kernel's K1 anchor now exists ──
                              │
                    ┌─────────▼─────────┐
                    │ AWAITING_APPROVAL │  the one founder approval (§15.3)
                    └─────────┬─────────┘   envelope + criteria, relayed downward
                              │
                    ┌─────────▼─────────┐          ┌──────────────────────┐
                    │    EXECUTING      │◄────────►│   WAITING  ★ new     │
                    │  work is happening│          │  nothing is running, │
                    └─────────┬─────────┘          │  and that is correct │
                              │                    └──────────────────────┘
                    ┌─────────▼─────────┐
                    │     VERIFYING     │  Evidence against every criterion
                    └─────────┬─────────┘
                              │
         ┌────────────────────┼────────────────────┬─────────────────────┐
         ▼                    ▼                    ▼                     ▼
   ┌───────────┐        ┌──────────┐        ┌───────────┐      ┌──────────────┐
   │ COMPLETED │        │  FAILED  │        │ CANCELLED │      │ SUPERSEDED ★ │
   └───────────┘        └──────────┘        └───────────┘      │     new      │
                                                                └──────┬───────┘
        all four are terminal · all four are permanent                 │
        none is a deletion · none is reversible              supersedes ──► a new
                                                             objective, original kept
```

### 4.3 Why WAITING must exist

Without it, an objective waiting on a founder decision, a scheduled time, an external dependency, or an unavailable provider must sit in `EXECUTING` — which is false, nothing is executing — or in `AWAITING_APPROVAL`, which is false unless it is specifically a founder decision.

**A false state is worse than a missing one**, because every downstream consumer — the brief, the dashboard, the learning loops, the founder's own reading of "what is happening" — inherits the lie. Constitution §5.3's own rationale for the state machine is that it "keeps *what is happening right now* trustworthy for every other module reading it."

`WAITING` is that clause honoured, not extended.

### 4.4 Why SUPERSEDED must exist

Objectives change. Today the only available moves are mutation — which destroys the record of what was originally wanted — or cancel-and-recreate, which severs the link between them and makes the founder look like they abandoned something.

**Supersession preserves both**: the original terminates honestly, the revision carries the lineage, and the receipts of both remain reachable. This is the same discipline the Kernel applies to warrants and for the same reason: **the record of what was authorized must not be editable after the fact.**

### 4.5 Validation — the gate that does the real work

Between `DRAFT` and `PLANNED`, five questions. **All must pass.**

| # | Question | Refusal is returned as |
|---|---|---|
| V1 | Is there a stated outcome, distinct from a stated action? | *"That's a step — what's it for?"* |
| V2 | Is completion checkable? Does at least one criterion have a machine verifier? | *"How would I know when this is done?"* |
| V3 | Is there a due date or a review date? | *"When should I come back to this?"* |
| V4 | Does it conflict with an active objective? | The conflict, stated in the founder's terms (§11.3) |
| V5 | Does it duplicate an active objective? | An offer to merge, not a second objective (§11.4) |

**A validation refusal is not a failure and is never recorded as one.** It is a clarifying question, in the founder's own words, at the only moment when answering it is cheap. The objective remains in `DRAFT` and is completed by the answer.

**V2 is the rule that keeps objectives from becoming tasks.** An objective with no machine-checkable criterion means "done" is whatever someone says it is, which is a to-do list wearing a constitution.

---

## 5 · Data Model

### 5.1 Fields

Immutable fields are marked **†**. Everything else is append-versioned — updated by writing a new version, never by editing in place.

#### Identity and provenance

| Field | Type | Notes |
|---|---|---|
| `objective_id` **†** | id | The Kernel's K1 anchor |
| `statement` **†** | text | **The founder's own words, verbatim, forever.** Never normalised, never rewritten by a model. This is what lets narration honestly say *"you asked for…"* fourteen months later. |
| `outcome_statement` | text | The checkable restatement. Versioned; the founder approves each version. |
| `created_at` **†** · `admitted_at` · `terminated_at` | timestamp | Canonical clock only — never ambient local time |
| `creator` **†** | `founder` \| `system_proposal` \| `standing_intention` \| `parent_objective` | §3.5 |
| `proposal_evidence` **†** | ref | Required when `creator ≠ founder`. **A system-proposed objective without evidence is refused.** |
| `standing_intention_id` **†** | id? | Set when minted by a template |

#### Outcome and success

| Field | Type | Notes |
|---|---|---|
| `criteria[]` | list | Each: `statement`, `verifier` (`machine` \| `founder`), `expected_outcome`, `evidence_id?`, `verdict?`, `due?` |
| `class` **†** | `standard` \| `query` \| `maintenance` | Query carries a hard `read_only` ceiling (§3.6) |

#### Envelope — what the founder approved

| Field | Type | Notes |
|---|---|---|
| `budget` | value | Spend and/or provider-time ceiling |
| `due_date` \| `review_date` | timestamp | **At least one is mandatory** (§3.4) |
| `consequence_ceiling` **†** | `read_only` \| `reversible` \| `reversible_until` \| `irreversible` | **The highest consequence class any warrant under this objective may carry.** Raising it requires a new founder approval, never a re-derivation. |
| `required_authority` **†** | grant/rule ref | Resolved once at admission; relayed downward per §15.3 |
| `approval_ref` **†** | id | The single founder approval this objective runs under |

#### State

| Field | Type | Notes |
|---|---|---|
| `state` | enum | §4.2, including the two proposed additions |
| `waiting` | record? | Present only in `WAITING`. §8. |
| `set_id` | id? | Membership in an Objective Set. §6. |
| `depends_on[]` | ids | Other objectives. **Objectives, never steps.** |
| `supersedes` **†** / `superseded_by` | id? | Lineage |
| `plan_ref` | ref | The Planner's DAG. **Held, not owned, and never rendered to the founder by default.** |

#### Termination

| Field | Type | Notes |
|---|---|---|
| `terminal_state` **†** | enum | One of the four |
| `terminal_reason` **†** | text | In the founder's terms, never a stack trace |
| `criteria_outcomes[]` **†** | list | Per-criterion result. **This is what a partial failure records instead of a percentage.** |
| `salvage[]` **†** | refs | Artifacts that survive a failed or cancelled objective (§11) |

### 5.2 Fields deliberately absent

| Absent | Why |
|---|---|
| `progress_percent` | §7.2. A number summarising something complicated will be believed. |
| `priority` | Ranking is B2's, computed from consequence — not a field anyone sets. A settable priority is a field that becomes "high" on everything. |
| `assignee` / `owner` | The founder owns every objective (§3.3). A second owner field would eventually disagree with that. |
| `task_count` / `completed_count` | Activity metrics (§2.2) |
| `estimated_effort` | Not a founder-facing concept; belongs to the Planner's estimator |
| `status_note` | A free-text field that becomes the real state, unvalidated, unverified |

**The absences are as load-bearing as the fields.** Each one, added later for a locally good reason, converts the model into a project tracker.

---

## 6 · Hierarchy

### 6.1 The decision

> **Two node types, one edge, depth capped at one — enforced by type, not by policy.**

- **`Objective`** — completable, has criteria, can be executed against
- **`Objective Set`** — a named grouping, has **no criteria of its own**, cannot be executed against, completes exactly when its members terminate
- **A Set cannot contain a Set.** There is no field for it.

### 6.2 Why not arbitrary nesting

Nesting is the most-requested and most-regretted feature in every outcome system ever built. Three reasons it is refused here:

**It produces a tree, and a founder reading a tree is reading a task manager.** VEDA 03 is explicit: one decision, one objective, never dashboards full of tasks.

**Completion becomes ambiguous.** A parent whose children are 4-of-7 complete invites a percentage, which §7.2 forbids — and the percentage will be invented by whoever renders it if the model permits one.

**Depth is a ratchet.** Nothing about depth 3 is different in kind from depth 2, so the argument that permits the second permits the fifth. Capping by type means the conversation does not start.

### 6.3 Milestones are not entities

A milestone is a **weighted-free success criterion with its own due date**. It is a row in `criteria[]`, not an object.

This is deliberate. The moment a milestone is an entity, it acquires a state, then an owner, then a progress field, and the system is tracking milestones rather than outcomes.

### 6.4 Dependencies

`depends_on` links **objective to objective**, never objective to step. Step-level dependencies belong to the Planner's DAG, which Mission Control already schedules and which the Objective Engine holds by reference and does not interpret.

**A dependency cycle is refused at validation**, exactly as `Objective.validate()` already refuses task cycles at submission time rather than discovering them as a hang.

---

## 7 · Success Measurement

### 7.1 The model

> **Binary completion. Criteria-based. Per-criterion verifier. Progress described, never scored.**

An objective is complete when **every** criterion has a matching verdict. Not most. Not weighted. Not a threshold.

### 7.2 Why not a percentage

Constitution §2.2: done only when Verification confirms real-world state matches the success criteria.

VEDA 03, of the tree, applies verbatim here: *"It does not display a health score, and must never be made to. A single number summarising a company is always wrong and always believed."*

A percentage-complete objective is that same error at a smaller scale. It is arithmetic over things that do not add up — one criterion may be trivial and another may be the entire point — and it will be read as a prediction. **"Three of five criteria met, and the two outstanding are X and Y" is more information in fewer characters and cannot be misread.**

### 7.3 Verifier types

| Verifier | Who decides | Constraint |
|---|---|---|
| `machine` | Verification Subsystem, producing Evidence by re-observing (ADR-0011) | Requires an `expected_outcome` |
| `founder` | A judgment request, ranked by B2, carrying a silence default per B4 | **An objective with any founder criterion cannot self-complete** |

**Every objective must have at least one `machine` criterion** (V2). Even a taste judgment has one: *"is the video good"* is `founder`, but *"a video exists at path X, 4:58 long, 1080p"* is `machine`. If no machine criterion can be stated, the outcome has not been made concrete enough to admit.

### 7.4 What is rejected

| Model | Why |
|---|---|
| Weighted criteria | Weights imply partial credit implies a percentage (§7.2). And nobody sets weights honestly under deadline. |
| Task-count completion | A model can produce five tasks and complete all five without changing the world. Constitution §2.2 exists to forbid exactly this. |
| Time-based completion | An objective is not done because its deadline passed. It is `failed`, or it is `waiting`. |
| Model self-assessment | §2.2, unambiguously |

### 7.5 The measure the Objective Engine actually reports

Not a completion rate. Not throughput.

> **Judgments required per objective, over time.**

It is the only number the Objective Engine produces, and it is a *derived* value read from the receipt ledger, not independently maintained.

**It is explicitly subordinate to VEDA 03's headline metric — the autonomy ratio, owned by C4.** VEDA 04 C4 is unambiguous that every autonomy-related surface derives from the Boundary Service and that independently computed autonomy numbers are a guaranteed inconsistency. This number is objective-scoped and does not attempt to be an autonomy measure; if it ever appears beside the autonomy ratio on the same surface, one of them must go, and it is this one.

---

## 8 · Waiting Model

### 8.1 The requirement

Waiting must not look like failure. In VEDA 01's terms, a system that renders a legitimate wait as a problem manufactures vigilance load — the exact burden the product exists to remove.

### 8.2 Four kinds

| Kind | Waiting on | Ends when | Timeout behaviour |
|---|---|---|---|
| `awaiting_judgment` | A founder decision | Verdict received | **B4's silence default fires, re-verified first** |
| `awaiting_time` | A scheduled moment | The moment arrives | Durable timer; survives deployments |
| `awaiting_dependency` | Another objective's criterion | Dependency terminates | Dependency's own timeout cascades |
| `awaiting_resource` | Provider, device, connector, network | Resource returns | **Declared expected-by; on breach, escalates as a judgment, never a silent stall** |

### 8.3 The waiting record

Every wait carries five fields, all mandatory:

```
   waiting_on      what, specifically, in the founder's terms
   since           when the wait began
   ends_when       the condition that resolves it
   expected_by     when we believe it resolves
   on_timeout      what happens if expected_by passes — never "nothing"
```

**`on_timeout` may not be empty.** VEDA 04 B4's invariant — no open request may exist without a scheduled default, and an item that can sit indefinitely is a defect — applies to waiting objectives with the same force. An objective that can wait forever is a promise the system cannot keep.

### 8.4 How waiting is presented

| Rule | Reason |
|---|---|
| Waiting objectives appear in **no failure count** | It is not a failure |
| Waiting objectives generate **no judgment request by themselves** | Waiting is not a decision. Only `awaiting_judgment` produces one, and that one is the decision itself. |
| Narration says what is being waited for and when it is expected | *"The exports archive runs Friday"* — a statement, not a status |
| A wait that breaches `expected_by` **surfaces once**, and escalates | The breach is news; the wait is not |

### 8.5 Waiting is not a dumping ground

**An objective may not enter `WAITING` without a resolvable `ends_when`.** "Waiting on circumstances" is not a wait; it is an objective that should be reviewed or cancelled. Without this rule, `WAITING` becomes the state where objectives go to be forgotten while appearing healthy — the most likely way this design decays.

---

## 9 · Founder Experience

### 9.1 The vocabulary rule

The founder says **"archive exports."** They never see *create folder · move file · compress · delete*.

| Layer | Founder sees it |
|---|---|
| Objective | **Always.** In their own words. |
| Criteria | On request — *"how will you know it's done?"* |
| Steps / plan DAG | **Never by default.** Available in Mission Control, one level down. |
| Capabilities, warrants, receipts, providers | Never as such. Present in the receipt, expandable, deliberately low-contrast. |

VEDA 03 states the governing principle: you go to Mission Control when you *don't trust the summary*, so its prominence should be inversely proportional to how well the system is doing its job. **The Objective Engine's job is to make that visit unnecessary, not to make it richer.**

### 9.2 Admission is a conversation, not a form

The founder states an outcome. If validation fails, the system asks **one** question in their terms — *"how would I know when the exports are properly archived?"* — never a form, never a required-field error, never a list of everything missing at once.

A refused objective is a `DRAFT` awaiting one answer, and it is never recorded as a failure.

### 9.3 The founder's words survive forever

`statement` is immutable and verbatim. It is never normalised, summarised, or rewritten by a model.

This matters at year two, when the system needs to say *"you asked me to keep exports tidy — that was fourteen months ago, and the folder has changed shape."* That sentence is only possible if the original words still exist. VEDA 01 §4 requires the vocabulary to adapt over time, and adaptation requires knowing what the original was.

### 9.4 What the Objective Engine emits to the founder surface

**Exactly three things.** Everything else is available on request and pushed to no one.

| Emitted | Consumer | Constraint |
|---|---|---|
| At most one judgment request | VEDA 03 Screen 01, the decision slot | Ranked by B2. **One at a time, never a list.** |
| Completed objectives, collapsed | The receipt | *"12 handled without you"* — **objectives, not tasks** |
| An outcome sentence per completion | Narration (D1) | The outcome, not the method |

**Explicitly not emitted:** active objective count · progress bars · a list of what is in flight · anything that would render as a badge or a number on a nav item. VEDA 03 refuses unread badges and counts, and *"a number on a nav item is an obligation."*

### 9.5 Dashboard integration

| Surface | Objective Engine's contribution |
|---|---|
| **Screen 01** — the voice, the decision, the receipt | One decision. The receipt's collapsed objective count. Nothing else. |
| **Approval queue at volume** | Judgment requests only, tiered by B3 into Needs-you / Sweep / Auto-handled — **the frozen three tiers, unchanged** |
| **Mission Control** (interior) | The full active set, enumerable, with steps one level down. The only place objectives are listed. |
| **The tree** | **Nothing.** VEDA 01 §9 fixes the mapping: branches are domains of delegated judgment created by founder rule grants. Objectives are not branches and must never be made into them — the tree is the one measure the product itself cannot move. |

---

## 10 · Integration with the Constitutional Kernel

### 10.1 The boundary

> **The Objective Engine's responsibility ends at admission. It never calls `authorize()`.** The Runtime does, per action, and the Kernel validates against the admission record the Objective Engine published.

The Objective Engine is therefore not on the execution hot path at all. It touches an objective a handful of times over its life: admit, envelope changes, waiting transitions, terminate.

### 10.2 What is published, and what the Kernel does with it

```
  OBJECTIVE ENGINE                              CONSTITUTIONAL KERNEL
  ────────────────                              ─────────────────────

  admit(objective)
      │
      └──► ADMISSION RECORD ──────────────────► read by K1 on every mint
             objective_id                          "does this resolve to an
             state                                  admitted, non-terminal
             consequence_ceiling                    objective?"
             budget · deadline
             required_authority                  envelope bounds every warrant
             approval_ref                        minted under this objective

  state change (waiting, resumed) ────────────► K1 keeps refusing while the
                                                objective is not EXECUTING

  terminate(objective_id, reason) ─────────────► kernel.invalidate(
                                                    scope = objective_id)
                                                  ── outstanding warrants
                                                     cancelled, no new mints
```

### 10.3 What becomes what

The brief asks which information becomes intent, authority request, and execution contract. Precisely:

| Objective field | Becomes | Where |
|---|---|---|
| `objective_id` | The **warrant's constitutional anchor** | Every warrant carries it; K1 validates it |
| `required_authority` + `approval_ref` | The **authority request**, resolved **once** at admission | Relayed downward per §15.3 — never re-asked per step |
| `budget` · `deadline` · `consequence_ceiling` | The **execution contract** — the envelope | Kernel refuses a warrant exceeding any of the three |
| `criteria[].expected_outcome` | Verification's target | Travels with the step, not the warrant |
| `state` | K1's liveness gate | Non-`EXECUTING` ⇒ no mints |

### 10.4 The consequence ceiling

The single most useful field in this specification.

An objective admitted with `consequence_ceiling: reversible` **cannot mint an irreversible warrant**, no matter what the plan later decides, what a department later concludes, or what a provider later suggests. Raising the ceiling requires a fresh founder approval — it is not re-derivable from circumstances.

This is VEDA 04 A2's classification discipline applied at the objective level, and it closes a gap that per-action classification alone leaves open: **an objective composed entirely of individually-reversible actions can still produce an irreversible outcome.** The ceiling is where the founder says how far this is allowed to go, once, in advance, in calm.

### 10.5 Termination reuses the Override mechanism

`kernel.invalidate(scope=objective_id, reason=…)` — the same operation the founder's global Override uses, at a narrower scope. Nothing new is built.

Consequence, stated because it is a physical limit rather than a design choice: **warrants already executing run to settlement.** A cancelled objective stops *deciding to act*; it cannot un-write a file already being written. This is the same honest limit the Kernel states for the Override, and it must be narrated as such rather than implied away.

---

## 11 · Failure Behaviour

### 11.1 Impossible objective

**Refused at validation if knowable then; halted with a stated reason if discovered later.** Never partially attempted in the hope that it resolves.

On late discovery: the objective enters `FAILED` with per-criterion outcomes, a plain-language reason, and an explicit **salvage list** — what exists, what was spent, what is reusable. The founder paid for something; they are told what they got.

### 11.2 Obsolete objective

The premise evaporated — the customer churned, the deadline passed, the product pivoted.

**This must be detected, not merely accepted.** An objective whose premise changed and which continues executing is the system working hard on something nobody wants, which is the most expensive failure available and the least visible.

Detection sources: a superseding objective, a dependency terminating differently than assumed, the review date arriving with no progress, or a Research finding that contradicts a stated premise. Detection **surfaces as a judgment** — *"this assumed X; X is no longer true"* — and the founder decides. The Engine never cancels on its own.

### 11.3 Conflicting objectives

Two objectives whose criteria cannot both hold.

Detected at **validation** (V4) against the active set, and re-checked when any objective's criteria are superseded. **Escalated, never auto-resolved.** The Engine states the conflict in the founder's terms and offers the options it can see; choosing between two things the founder wants is judgment by definition.

### 11.4 Duplicate objectives

Same or overlapping outcome statement and target.

Detected at validation (V5). **The response is an offer to merge, not a second objective and not a silent rejection.** Two objectives quietly pursuing one outcome will produce two sets of receipts, two envelopes, and eventually two conflicting completions.

### 11.5 Changing objectives

> **Criteria are never mutated. A change produces a new version by supersession.**

The original terminates as `SUPERSEDED`, the revision carries `supersedes`, both records persist, and receipts remain reachable from either.

**Why not mutation.** A mutable objective can be edited after the fact to describe an outcome other than the one approved — which makes every receipt anchored to it unfalsifiable. This is the identical argument that makes warrants immutable in the Kernel, applied one level up, and the two must not disagree.

**Supersession within the envelope** proceeds on founder approval of the new version. **Supersession that widens the envelope** — more budget, later deadline, higher consequence ceiling — is a new approval, and the Engine says which of the three widened.

### 11.6 Failure summary

| Condition | Behaviour | Who decides |
|---|---|---|
| Impossible, known early | Refused at validation, as a question | Engine (mechanical) |
| Impossible, discovered late | Halt · `FAILED` · salvage list | Founder confirms |
| Obsolete | Surfaced as a judgment | **Founder only** |
| Conflicting | Escalated with options | **Founder only** |
| Duplicate | Merge offered | Founder |
| Changing | Supersession, original retained | Founder |
| Envelope exceeded | Kernel refuses the warrant; objective waits | Founder, on the escalation |

**Every row that changes what the founder wants is decided by the founder.** The Engine detects, states, and proposes. It never decides.

---

## 12 · Scalability

### 12.1 Where the Objective Engine sits

Not on the execution hot path (§10.1). Per objective, over days: one admission, one approval relay, a handful of state transitions, one termination. **At 500 active objectives that is a few thousand operations over days, not per second.**

### 12.2 At the stated scale

| Dimension | Effect |
|---|---|
| **10,000 completed** | A store problem, not an architecture one. Compaction after a stated window per §12.3; indexed by `objective_id`, terminal date, and lineage. Completed objectives are in **no** active view. |
| **500 active** | Bounded by admission control (§12.4), never by an unbounded queue. State per objective is small and fixed. |
| **1,000 capabilities** | **Zero effect.** The Objective Engine never enumerates capabilities. It states outcomes. Only the Planner touches the catalogue. |
| **100 departments** | Out of scope (VEDA 05), and the model does not depend on it: an objective names an outcome, never an executor. |

### 12.3 Objective memory over time

| Horizon | What survives | Basis |
|---|---|---|
| **Forever** | `objective_id`, founder's verbatim `statement`, outcome statement, criteria and their verdicts, admission authority, terminal state and reason, lineage, receipt anchors | VEDA 04 M1 — permanent, a trust obligation. C7's annual audit and C5's self-audit both read it. |
| **Bounded window** | Working set — draft artifacts, intermediate context, full plan DAG detail, waiting history | Declared lifetime per VEDA 04 §5. Compacted, never silently evicted. |
| **Historical** | Compacted objectives, queryable, absent from every active view | — |
| **Learning** | Recurrence, time-to-complete, judgments required, refusal reasons, supersession frequency | Feeds L3 rule proposals and the estimator. **Proposes only; never enacts.** |

**Compaction preserves provenance.** VEDA 04 B5's rule is unconditional: when twelve items collapse to one line, the line retains links to all twelve. A compacted objective keeps every receipt anchor. **A summary that loses its sources is invalid**, and there is no exception for age.

### 12.4 The real limit is not compute

500 active objectives generating even one judgment each per week is 500 judgments per week reaching one person. **The scarce resource is the founder's attention, and it does not scale by instantiation.**

Two consequences:

**Admission control, not queueing.** An objective that cannot be resourced — including the founder's judgment capacity — is refused at admission with a stated reason, not admitted and starved. A queue that only grows is a promise the system cannot keep.

**The only real scaling mechanism is needing the founder less.** More objectives per founder-judgment, which is L3's job. Every other system would answer this question with throughput. This one cannot, and §7.5's measure is what makes the answer visible.

### 12.5 The ten-year properties

| Property | Why it holds |
|---|---|
| Vocabulary is outcomes, never technology | No field names a capability, provider, tool, or executor |
| Composition is capped by type | Depth cannot ratchet, because there is no field for depth 2 |
| Completion is binary and verified | Cannot drift into a scoring system, because there is nothing to score |
| The founder's words are immutable | Year-two continuity does not depend on anything being reconstructed |
| Admission is an authority event | The system cannot manufacture its own reasons to act |

---

## 13 · Risks

### 13.1 The two conflicts found — documented, not resolved

#### Conflict A · `Intent` now means three things — and one of them is my error

| Meaning | Source | Status |
|---|---|---|
| Structured goal + constraints + context + success criteria | **Constitution §3.1**, shipped as `planner/plan.Intent`, consumed by `brain/intent.py` | **Frozen** |
| The receipt ledger's first-phase identifier — `recordIntent() → intentId` | **VEDA 04 A1** | **Frozen** |
| The Kernel's authorization token | **Constitutional Kernel Specification v1.0 §4** | **Mine. Wrong.** |

The first two coexist fine — the Kernel's token was designed to *carry* VEDA 04's `intentId`, so they unify. **The collision is with the Constitution's frozen §3.1 term, and I introduced it.**

**Smallest amendment — to the Kernel Specification, which is not frozen. No VEDA changes.**

> Rename the Kernel's token type from `Intent` to **`Warrant`**. The field it carries stays `intent_id`, preserving VEDA 04 A1's `intentId` verbatim. Constitution §3.1's `Intent` is untouched.

`Kernel.authorize() → Warrant` · `warrant.intent_id` · `LocalExecutor.run(warrant_id)`. One class renamed, no logic changed, both frozen terms preserved exactly.

**The rename is also more accurate than the original.** The token is not an intention — it is an instrument issued by an authority permitting a specific act, bounded in time and scope. That is a warrant. This specification uses `Warrant` throughout on that assumption; if the rename is declined, substitute the Kernel's term and the collision stands unresolved.

#### Conflict B · The frozen Mission state machine lacks two states

Constitution §5.3 freezes `draft → planned → awaiting_approval → executing → verifying → completed | failed | cancelled`.

`WAITING` and `SUPERSEDED` have no representation. Today a waiting objective must occupy a state that is false about it (§4.3), and a changing objective must be mutated or cancelled-and-recreated (§4.4).

**Smallest amendment — two additive states. Nothing removed, no existing state's meaning changed, no existing transition deleted.**

> `EXECUTING ⇄ WAITING` · `WAITING → CANCELLED` · `{PLANNED, AWAITING_APPROVAL, EXECUTING, WAITING} → SUPERSEDED` · both new states terminal-safe, `SUPERSEDED` terminal.

**Pre-existing blocker, unchanged:** the `Objective` / `Mission` terminology ADR is still open. **This specification's lifecycle cannot ship until it is ratified**, because it would otherwise become a third model of the same concept. That ADR is now the critical path for this component.

### 13.2 The other risks

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| **R1** | **Objectives inflate into tasks.** *"Create a folder"* gets admitted because refusing feels unhelpful. Within a year the system is a to-do list with a constitution attached. | **Critical** | V2's machine-checkable-criterion gate. It will be argued with constantly, and it is the single rule that must not bend. |
| **R2** | **System-proposed objectives become a minting loophole.** If the system can create objectives freely, *"no execution without an Objective"* becomes *"no execution without the system writing down a reason."* | **Critical** | §3.5 — objective creation is an authority event. `proposal_evidence` mandatory. Cap and expiry on any standing rule permitting it. |
| **R3** | **A percentage returns.** Someone will need "progress" for a chart, and the field is trivially derivable. | **High** | §5.2's absence list. Progress is described in criteria, never in a number. **The absence is the mechanism.** |
| **R4** | **`WAITING` becomes a dumping ground.** Objectives that should be reviewed or cancelled sit there looking healthy. | **High** | §8.5 — no `WAITING` without a resolvable `ends_when` and a non-empty `on_timeout`. |
| **R5** | **Nesting reaches depth 2.** One good reason arrives and the type cap becomes a config option. | **High** | Enforced by type: a Set has no field that could hold a Set. Changing it is a schema change a reviewer must see. |
| **R6** | **Objective counts reach the first screen.** The most natural thing in the world to add, and VEDA 03 deliberately refused it. | **High** | §9.4's emission list is exhaustive. Anything not on it is not emitted. |
| **R7** | **A second autonomy number.** §7.5's measure sits next to VEDA 03's autonomy ratio and the two disagree. | **High** | C4 is the sole source. §7.5's measure is objective-scoped, derived from receipts, and **is the one that goes** if they ever share a surface. |
| **R8** | **Supersession chains become unreadable.** Six versions deep, nobody can say what was originally wanted. | Medium | `statement` is immutable and carries forward unchanged through every version. The founder's original words are always one hop away, regardless of chain depth. |
| **R9** | **Query Objectives become the bypass.** Cheap, self-admitting, and everything starts being one. | Medium | `read_only` ceiling enforced by the Kernel at K1, not by convention. A Query Objective cannot mint a write warrant. |
| **R10** | **Admission becomes a form.** V1–V5 rendered as five required fields, and stating an outcome becomes data entry. | Medium | One question at a time, in the founder's words. §9.2. A form here would undo §9 entirely. |
| **R11** | **The Objective Engine acquires scheduling.** It holds `depends_on` and a plan reference; walking them is one small step away, and Mission Control already owns it. | Medium | It holds `plan_ref` and never interprets it. A second scheduler is a second orchestration authority — the defect the execution-path audit found live in `execute_plan()`. |

---

## 14 · Final Recommendation

### 14.1 Adopt

The Objective Engine as specified: **admission authority, envelope holder, completion judge, and the Kernel's anchor** — owning nothing that plans, schedules, or executes.

### 14.2 The four decisions that must not be revisited

**One · V2 — no objective is admitted whose completion cannot be machine-checked.** Every other rule here is downstream of it. Without V2, objectives become tasks, completion becomes opinion, and the Kernel's first guarantee anchors to nothing.

**Two · Binary completion, never a percentage.** The moment a number exists, it is rendered; the moment it is rendered, it is believed; the moment it is believed, the founder is managing a project instead of receiving an outcome.

**Three · The system proposes, the founder admits.** This is what keeps *"no execution without an Objective"* from being circular. A system that can author its own reasons has no constraint.

**Four · The consequence ceiling.** One field, set once, in calm, that bounds how far an objective is permitted to go regardless of what anything downstream later concludes. It is the cheapest safety mechanism in the entire architecture.

### 14.3 Blocked until ratified

| Blocked | Blocked by |
|---|---|
| The lifecycle (§4) | The `Objective` / `Mission` terminology ADR — **now on the critical path** |
| `WAITING` and `SUPERSEDED` | Conflict B's two-state amendment (§13.1) |
| Every reference to `Warrant` | Conflict A's rename of the Kernel token (§13.1) |

**All three are small and none blocks the others.** Conflict A is a one-class rename. Conflict B is two additive enum members. The ADR has a recommendation already on record.

### 14.4 What is unblocked and should start now

Validation (V1–V5), the data model, criteria with per-criterion verifiers, the envelope including the consequence ceiling, and admission control. **None depends on the ratifications above**, and all of it is required by whatever the state names turn out to be.

### 14.5 The test that matters

At the end of a day, the founder should be able to answer *"what moved forward?"* without opening anything.

Not because a summary was generated, but because the system is structurally incapable of reporting anything else: it holds no task counts, computes no percentages, renders no lists on the first screen, and emits exactly three things — one decision, a collapsed count of **objectives** handled, and a sentence about each outcome.

> **A system that cannot report activity will report outcomes. That is not a discipline anyone has to maintain — it is a consequence of the fields that do not exist.**

---

*Implementation architecture specification. No VEDA created, modified, or reinterpreted. Two genuine conflicts documented in §13.1 with the smallest possible amendments recommended; neither is applied here, and one is a correction to the Constitutional Kernel Specification rather than to any frozen document. All claims about current system behaviour verified against `src/master_agent/` as of 2026-08-05.*
