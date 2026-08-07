# MasterAgent — Architectural Requirements Derived from the Experience Bible

Capability requirements, event flows, contracts, memory and runtime implications, migration risks and implementation order. Derived from the Bible v1.0. No code, no redesign.

## 0 · Reading note and assumptions

**What this is.** Every clause in the Experience Bible that imposes a capability on the system, extracted and stated as an architectural requirement. Each requirement carries its Bible citation so the trace runs both ways: no requirement here is invented, and no Bible clause is unimplemented.

**An honest declaration.** I have not seen MasterAgent's codebase. The *required modules* below are derived purely from the Bible and are therefore complete and correct as requirements. The *affected modules* section names components by their conventional function — orchestrator, tool layer, model gateway — because I cannot name yours. **Treat that section as a checklist to reconcile against your actual module map, not as a description of your system.** Where I have guessed at your architecture I have said so explicitly rather than writing confidently around the gap.

**The single most important finding.** The Bible does not describe an assistant with governance features bolted on. It describes a system whose **primary object is not a task but a decision**, and whose primary output is not an action but **a receipt plus a request for judgment**.

If MasterAgent's core loop is currently *goal → plan → tool calls → result*, then implementing this Bible is not a feature programme. It is the insertion of a **decision and consequence layer between planning and execution**, through which every action must pass. Almost everything below follows from that one structural change, and the migration risks in Section 8 are almost entirely about how invasive it is.

**Terminology used throughout.**
- **Action** — anything that changes state outside the system.
- **Judgment request** — a decision surfaced to the founder.
- **Rule** — a standing grant of authority to act without asking.
- **Receipt** — the immutable record of an action, written before it.
- **The line** — the current boundary between delegated and escalated judgment (Bible §3).

## 1 · Required modules

Twenty-two capabilities, grouped into five layers. Each states its Bible source and its hard invariant.

---

## Layer A · The Trust Spine
*Foundational. Nothing above this layer is safe without it.*

**A1 · Receipt Ledger**
*Source: Eng. Law I — every autonomous action writes its receipt before it writes its change.*
Append-only, immutable, monotonic. Two-phase against every action: **intent record → execute → outcome record**. Intent carries actor, rule (if any), reversibility class, expected effect, and the consequence quartet.
**Invariant:** if the intent write fails, the action does not occur. No exceptions, no buffering, no fire-and-forget.
**Note:** this places a durable write on the critical path of every action. See §7.

**A2 · Reversibility Registry**
*Source: Eng. Law II — every action is reversible or explicitly marked irreversible at design time.*
A declared classification for every action type in the system: reversible / reversible-until-T / irreversible. Each reversible class names its **compensating action** and its window. Unclassified action types are **non-executable by default** — the registry fails closed.
**Invariant:** "probably reversible" cannot be represented. The type system must not permit an unclassified action to reach execution.

**A3 · Override / Global Suspend**
*Source: §10 Human override.*
One gesture suspends all rule firing atomically, including in-flight evaluations. No confirmation, no friction, no persuasion copy. Work and queueing continue; **only deciding stops**. Must be reachable when the rest of the system is degraded — architecturally, this argues for it living outside the main orchestration path.
**Invariant:** suspension latency measured in milliseconds, not in a job cycle.

**A4 · Scope Introspection**
*Source: §10 Ethics 5 — it can always say what it is not allowed to do, in one sentence.*
A queryable, human-legible statement of current authority and its complement. Derived from the rule set, never hand-maintained.
**Invariant:** answerable at any moment without computation the founder waits on.

---

## Layer B · The Judgment Layer
*Where the product's actual object lives.*

**B1 · Consequence Engine**
*Source: §5 Approvals; Principle VI.*
Computes, for every judgment request, the four mandatory fields: **what changes · what it costs · what happens if you do nothing · whether it can be undone.**
**Invariant:** a judgment request missing any field cannot be emitted. This is a schema-level gate, not a UI concern — enforce it where requests are constructed, or it will be worked around.

**B2 · Consequence Ranking Service**
*Source: §5; Eng. Law VII — ranking is explainable.*
Orders open judgment requests by irreversibility, exposure, deadline proximity and novelty. **Emits its own justification** alongside the order.
**Invariant:** every ordering is defensible in one sentence, on demand. Chronological ordering is never a fallback — if ranking fails, that is an incident, not a degradation.

**B3 · Escalation Router**
*Source: §5 Escalations.*
Classifies every decision into **auto-handled / sweep / needs-you**, and where it escalates, names which of the three triggers fired: novel, irreversible, or excluded by rule.
**Invariant:** irreversible items can never be routed to a batchable tier, regardless of value or volume.

**B4 · Silence Default Scheduler**
*Source: §5 Escalations; Principle VII — silence has a stated default.*
Every open request carries a declared default action and a firing time. A durable timer executes the default, writes a receipt, and narrates it.
**Invariant:** no open request may exist without a scheduled default. An item that can sit indefinitely is a defect. This module is the most commonly omitted requirement in the entire Bible and the most damaging to skip — without it, "silence is a decision" is a claim the product cannot honour.

**B5 · Evidence Graph**
*Source: §4 First week — every claim reachable to its evidence in one step.*
Every assertion the AI makes is bound to its sources at generation time, not reconstructed afterwards. Provenance travels with the claim through summarisation.
**Invariant:** an unsourced claim is not renderable. If provenance is lost in a summarisation step, the summary is invalid.

**B6 · Confidence Model**
*Source: §10 Confidence.*
Three discrete external levels, mapped to three fixed phrasings, plus a **"what would raise it"** derivation. Internal continuous scores may exist; they are never exposed and never rendered numerically.
**Invariant:** no percentage crosses the boundary to the founder, in any surface, ever.

---

## Layer C · The Autonomy Layer
*The mechanism that moves the line.*

**C1 · Standing Rule Engine**
*Source: §10 Rules.*
Rule lifecycle and evaluation. Each rule carries five mandatory parts: trigger, **cumulative limit**, explicit exclusions, expiry, receipt binding.
**Invariant:** cumulative accounting is windowed and atomic. A per-instance cap without a cumulative cap is a malformed rule and must be rejected at definition time — this is the clause that prevents a large sum leaving in many small pieces.

**C2 · Rule Expiry Daemon**
*Source: §10; Eng. Law VI — every grant of authority carries an expiry.*
Rules die unless renewed. Renewal is a founder act, surfaced with the rule's firing history.
**Invariant:** a permission with no end date cannot be persisted.

**C3 · Rule Proposal Miner**
*Source: §4 First month; §10 Learning.*
Observes decision history, detects stable patterns, and generates proposals **with evidence attached** — including the counter-examples that set the boundary.
**Invariant:** proposals never self-enact (Eng. Law V). Inference generates proposals; only permission generates actions. Enforce in the system, not the interface.
**Product-critical:** §4 states the first accepted proposal must occur inside thirty days. This module's time-to-first-viable-proposal is a **product survival metric**, not an engineering nicety.

**C4 · Judgment Boundary Service ("the line")**
*Source: §3 — the boundary is the product.*
The canonical, queryable state of what is delegated versus escalated. Single source of truth for the autonomy measure, the tree's topology, the dependency audit, and scope introspection.
**Invariant:** every other autonomy-related surface derives from this service. Four independently computed autonomy numbers is a guaranteed future inconsistency.

**C5 · Self-Audit / Borderline Flagger**
*Source: Principle IX — the AI reports its own borderline calls before anyone finds them.*
Post-hoc review of rule firings against near-boundary heuristics: close to a cap, repeated within an unusual interval, unusual for the vendor or category. Surfaces unprompted and proposes a narrowing.
**Invariant:** cannot be disabled, rate-limited to invisibility, or suppressed by a quality metric. This module exists specifically to produce output that looks bad.

**C6 · Delegation Router (human)**
*Source: §10 Delegation.*
Routes classes of decision to named humans other than the founder, with their own receipts and defaults.
**Invariant:** delegation to a human is a first-class outcome with equal support to approval and rejection — not a special case grafted onto the approval path.

**C7 · Dependency Audit Generator**
*Source: §10 Annual Dependency Audit.*
Annual, unprompted, **non-disableable**. Produces: current unasked authority in plain language; rules unexamined since grant; what would be lost on departure; self-assessed overreach.
**Invariant:** no configuration flag suppresses it. If one exists, it will be set.

---

## Layer D · The Expression Layer
*The Bible states the AI is the interface. That makes this layer product-critical, not presentational.*

**D1 · Narration Service**
*Source: §3; Eng. Law III — the system can render its complete state as prose at any moment.*
Renders any system state into first-person prose in the fixed voice. Deterministic templates for facts and figures; a generative layer only for connective reasoning.
**Invariant:** figures in prose are bound to the same values rendered on screen — rendered from one source, never independently generated.

**D2 · Voice Charter Validator**
*Source: §8 in full.*
A lint pass on **every outbound utterance**: banned phrase list, exclamation and emoji ban, single-apology rule, stacked-hedge detection, confidence phrasing whitelist, celebration detection.
**Invariant:** an utterance that fails validation is regenerated or falls back to a deterministic template — never emitted with a warning. **This is the only defence against the language model's baseline personality reasserting itself**, and it will try to on every model upgrade.

**D3 · Mistake Protocol Handler**
*Source: §8 Mistakes.*
On detected error: emit **impact → cause → fix → prevention**, one sentence each, in that order, before founder discovery. Automatically generates the rule-tightening proposal.
**Invariant:** disclosure is triggered by detection, not by founder query. Structurally, this means error detection must have a direct path to the narration layer that does not route through anything capable of suppressing it.

**D4 · Presence State Broadcaster**
*Source: §7 Motion; §9 Tree.*
Emits idle / thinking / speaking / awaiting.
**Invariant:** "thinking" reflects genuine computation above a threshold. Manufactured deliberation is explicitly forbidden (§7, Eng. Law VIII) — the state machine must be driven by real work signals, not by a UI timer.

**D5 · Tree Topology Service**
*Source: §9.*
Derives branch structure from rule domains, depth from accumulated trust, regional density from activity, regional warmth from pending judgment. Revoked rules **thin their branch but never delete it**.
**Invariant:** deterministic and reproducible from the boundary service — the same state always produces the same tree. Topology history is retained permanently; §9 makes preservation a product requirement, not a storage preference.

**D6 · Brief Composer**
*Source: §4; §5 Mission summaries.*
Headline-first assembly, collapse of completed work to a single line and a receipt, and a **designed quiet-day variant**.
**Invariant:** the zero-activity brief is a first-class output with its own composition path, not an empty-list render.

**D7 · Vigilance Attestation Service**
*Source: §1 — vigilance is the primary load; §4 Day 200.*
**This is a requirement the Bible implies but never names, and it is the one I would most want on the record.**
The sentence *"Nothing needs you"* is the product's highest-value claim and its greatest liability. It is only safe if it is **provably complete** — backed by a coverage check across every monitored domain confirming each was actually checked, within its freshness window, without error.
**Invariant:** if any domain is stale, unreachable or errored, the system may not say "nothing needs you." It must say what it could not check. A silent gap converts the product's core promise into a lie by omission, and it is the single failure most likely to end a customer relationship permanently.

---

## Layer E · Governance and Presentation

**E1 · Decision Provenance Store** — *§1 Continuity; Eng. Law IX.* Why decisions were made, surfaced **at the moment of relevance** rather than on search. Stated retention lifetime.

**E2 · Deterministic Demo Tenant** — *§11.* Fixed outcomes over real data shape, labelled as such. A first-class runtime mode, not a fixtures file.

**E3 · Export** — *Eng. Law X.* Complete founder-readable export of data, receipts, rules and provenance.

## 2 · Affected modules

**Reconcile against your real module map.** Named here by conventional function because I have not seen the codebase.

| Presumed module | Change | Severity |
|---|---|---|
| **Core agent loop / orchestrator** | Must gain a mandatory decision-and-consequence checkpoint between plan and execute. Every action routes through classification, rule evaluation and receipt-intent before touching a tool. | **Invasive — this is the migration** |
| **Tool / integration layer** | Every tool surface must be classified in the Reversibility Registry with a named compensating action. Unclassified tools become non-executable. | **High — large one-time audit** |
| **Model gateway** | All outbound language passes the Voice Charter Validator. Needs regeneration-on-failure and a deterministic fallback path. Requires prompt/version pinning so a model upgrade cannot silently alter personality. | High |
| **Scheduler / background work** | Gains durable, long-horizon timers for silence defaults, rule expiry, freshness windows and the annual audit. Horizons of a year make this a persistence problem, not a queue problem. | High |
| **Notification subsystem** | **Deleted, not reconfigured.** §5 abolishes notifications. Any push, badge or count infrastructure is repurposed to undo-window and pending-commitment surfaces only. | Medium — politically hard |
| **Task / mission model** | Missions gain impact class, reversibility class, rule linkage, receipt linkage and a default-on-silence. | Medium |
| **Data connectors** | Must report freshness and health per domain to feed D7. A connector that fails silently breaks the product's core claim. | Medium — **frequently underestimated** |
| **Auth / identity** | Must represent delegates (CFO, Head of Eng) as approval principals, not merely as users. | Medium |
| **Search / retrieval** | Shifts from founder-initiated query to system-initiated recall at relevance. Different trigger model, different ranking. | Medium |
| **Analytics / telemetry** | **Contradiction to resolve deliberately.** Conventional engagement instrumentation measures the inverse of this product's success (§12). Primary metric becomes the position of the line. | Low technically, **high organisationally** |
| **Front-end state** | Consumes a presence stream and a tree topology stream. Needs a designed reduced-motion state and a designed empty state per surface. | Medium |

## 3 · Event flows

Seven canonical flows. Ordering constraints marked **▸** are non-negotiable.

### F1 · Autonomous action under a rule
```
signal observed
  ▸ classify action type  → Reversibility Registry
     └ unclassified? → ABORT, escalate as novel
  ▸ irreversible? → never auto → route to needs-you
  ▸ evaluate rules → match? → check cumulative window
     └ cap breached → escalate, cite the cap
  ▸ write RECEIPT INTENT
     └ write fails → ABORT (Eng. Law I)
  execute
  ▸ write RECEIPT OUTCOME
  update boundary service → tree topology, autonomy measure
  queue for self-audit review
```

### F2 · Escalation to judgment
```
decision cannot be auto-handled
  ▸ name the trigger: novel | irreversible | excluded
  ▸ Consequence Engine builds the quartet
     └ any field underivable → the request CANNOT be emitted;
       raise as an internal gap, do not degrade the request
  bind evidence (Evidence Graph)
  derive confidence level + what-would-raise-it
  ▸ assign default-on-silence + deadline → register durable timer
  rank against open set → emit ordering justification
  Narration Service renders → Voice Charter Validator → surface
```

### F3 · Founder decision
```
verdict received
  ▸ cancel the silence timer
  ▸ write receipt intent → execute → outcome
  open undo window per reversibility class
  record into Decision Provenance (the reasoning, not just the verdict)
  feed Rule Proposal Miner
  update boundary service
```

### F4 · Rule proposal → grant → first firing
```
Miner detects stable pattern (N consistent, M elapsed, counter-example bounded)
  assemble evidence including the boundary-setting rejection
  ▸ derive cumulative cap — REQUIRED, not optional
  ▸ derive exclusions — REQUIRED
  set trial expiry
  surface as proposal (never enacted)
     └ granted → rule active, trial clock starts, tree branch created
     └ adjusted → re-derive, re-propose
     └ declined → record; suppress this pattern class for a period
  first firing → receipt → narrated in the next brief, unprompted
```

### F5 · Silence default fires
```
timer expires, no founder response
  ▸ re-verify the default is still valid (facts may have moved)
     └ changed → re-escalate, do NOT fire a stale default
  ▸ receipt intent → execute default → outcome
  narrate in next brief: what happened, when, why it was the stated default
```
The re-verification step is easy to omit and firing a stale default is a trust-ending event.

### F6 · Mistake disclosure
```
error detected (self-monitoring, reconciliation, or external signal)
  ▸ assess impact FIRST
  ▸ emit impact → cause → fix → prevention, in order, one sentence each
  ▸ this path may not be gated by any suppression, batching
    or quality-scoring mechanism
  generate rule-tightening proposal automatically
  disclose BEFORE founder discovery — latency here is a correctness property
```

### F7 · Session start
```
founder arrives
  ▸ Vigilance Attestation: every domain checked, fresh, healthy?
     └ any gap → the greeting MUST name it.
       "Nothing needs you" is unavailable while coverage is incomplete.
  compose brief (headline-first; quiet-day path if zero)
  select top-ranked judgment request
  presence → thinking → speaking
  narrate → validate → render text and voice from ONE stream
```

## 4 · APIs and contracts

Stated as logical capability contracts — operations, obligations and invariants. Transport and shape are yours.

### Receipt Ledger
`recordIntent(actor, actionType, reversibilityClass, expectedEffect, consequence, ruleRef?) → intentId`
`recordOutcome(intentId, result, actualEffect)`
`readLedger(filter) → receipts` · `renderAsProse(filter) → text`
**Obligations:** append-only; no update or delete operation exists at any privilege level; intent must precede execution; prose rendering is a first-class operation, not a report generator.

### Reversibility Registry
`classify(actionType) → {class, window?, compensatingAction?}`
`register(actionType, classification)` · `compensate(intentId) → result`
**Obligations:** fails closed on unknown types. No default classification exists.

### Consequence Engine
`build(decisionContext) → {whatChanges, cost, ifNothing, reversibility}`
**Obligations:** returns an error, never a partial. Callers cannot construct a judgment request without a complete quartet — enforce structurally.

### Ranking Service
`rank(openRequests) → [{requestId, position, justification}]`
**Obligations:** justification is mandatory and human-legible. No chronological fallback.

### Standing Rule Engine
`define(rule) → ruleId` · `evaluate(decisionContext) → {matched, ruleId?, reason}`
`consume(ruleId, amount) → {allowed, remaining}` · `expire(ruleId)` · `renew(ruleId, period)`
**Obligations:** `define` rejects any rule lacking a cumulative cap, exclusions or expiry. `consume` is atomic against concurrent evaluation.

### Boundary Service
`state() → {delegatedDomains, escalatedClasses, autonomyRatio, activeRules}`
`history(period) → timeSeries` · `topology() → treeStructure`
**Obligations:** sole source of autonomy truth. Every consumer reads here; none computes its own.

### Narration Service
`narrate(stateOrEvent, register) → utterance`
**Obligations:** every numeric in the utterance carries a binding to the rendered value. Output always passes through validation before emission.

### Voice Charter Validator
`validate(utterance) → {pass, violations[]}` · `enforce(utterance) → utterance | template`
**Obligations:** no bypass parameter exists. A failing utterance is never emitted with a warning.

### Vigilance Attestation
`attest() → {complete: bool, domains[{name, lastChecked, healthy}], gaps[]}`
**Obligations:** the "nothing needs you" surface **must** call this and **must** honour a false result. Consider enforcing at the type level — the calm-state message should be unconstructable without a complete attestation.

### Override
`suspend()` · `resume()` · `status()`
**Obligations:** synchronous, unconditional, no confirmation parameter. Available when upstream services are degraded.

### Scope Introspection
`permitted() → sentence` · `forbidden() → sentence`

### Dependency Audit
`generate(year) → audit`
**Obligations:** no suppression parameter exists in the signature.

## 5 · Memory requirements

Five distinct stores. They differ in lifetime, mutability and — most importantly — **retrieval trigger**. Collapsing them into one vector index will produce a system that can search but cannot remember, and the Bible requires remembering.

### M1 · Episodic — the receipt ledger
*Every action, intent and outcome.* Append-only, immutable, **permanent**. This is the evidentiary base for the audit, the self-audit, the tree's history and export. Retention is not a cost decision; §10 makes it a trust obligation.

### M2 · Decisional — provenance
*Every founder verdict, and the reasoning that produced it.* Includes rejected recommendations and the stated reason — §8 forbids relitigating without a changed fact, which requires knowing what was declined and why.
**Retrieval trigger: relevance, not query.** This store must be able to *volunteer*. "You set this band fourteen months ago" is only possible if the memory system is invoked by context, not by search. This is the least conventional requirement in this document and the one that most distinguishes the product at year two.

### M3 · Semantic — the company model
*Entities, people, vendors, constraints, thresholds, the company's own vocabulary.* Mutable, versioned. §4 requires vocabulary to adapt over time; versioning is what lets the AI say **which** fact changed when it revisits a decision.

### M4 · Procedural — rules and boundaries
*The rule set and its complete history, including revoked rules.* §9 requires that revocation thins a branch without deleting it, which makes rule history permanent, not archival.

### M5 · Relational — principals
*The founder, delegates, their authorities and their own decision histories.* Required by C6.

### Cross-cutting requirements

**Freshness metadata is mandatory.** Every fact carries when it was last verified. D7 cannot function otherwise, and neither can honest uncertainty — §8's distinction between *I don't know* and *I haven't checked* is a data property, not a phrasing choice.

**Stated lifetimes** (Eng. Law IX). Each store declares what it keeps, for how long, and how it forgets. Forgetting is a designed behaviour, not eviction.

**Provenance survives summarisation.** When twelve items collapse to one line, the line retains links to all twelve. A summary that loses its sources is invalid (B5).

**Memory never acts.** Recall may generate a proposal; it never triggers an action (Eng. Law V).

**Contradiction is surfaced, not resolved silently.** When a new fact conflicts with a held one, the AI says so. Silent overwriting of the founder's own recorded reasoning is a violation of §10 Ethics 2.

## 6 · Voice requirements

### The governing constraint

**Text is the source of truth; speech is a layer over it.** Architecturally: one generation, two renderings. Never two generations. Independently produced spoken and written text will diverge, and §5 makes divergence a severity-one defect — it breaks the illusion of a single mind more thoroughly than any visual bug.

### Synthesis
- Neutral-to-warm, mid-low, unhurried. Rate and pitch below default.
- **Prosody control is required, not optional.** §5 specifies pauses of distinct lengths before clauses, before figures, before requests for judgment, and after bad news — and an 8% slowdown when reporting problems, 12% when reporting its own error. A synthesis path without programmable pause and rate cannot implement the Bible.
- **Number pronunciation must be locale-correct and verified.** Currency conventions differ by market; a mispronounced figure destroys authority instantly.
- Voice identity must be stable across provider changes. Treat it as a brand asset with a migration plan, not a runtime configuration.

### Synchronisation
- Text and speech land within **150ms**; beyond 300ms is a severity-one defect.
- Emphasis is a **timing and weight** event, not a volume or pitch event — a brief hold before the word plus visual weight on it.
- Session-scoped audio unlock via a deliberate gesture. Autoplay is never attempted; a silent failure on the first greeting is the worst possible first impression for a product selling presence.

### Interruption
**Barge-in is absolute and unconditional.** Any input stops speech mid-word and completes the text immediately. This must be handled at the audio layer, not by waiting for a sentence boundary. A partner that cannot be interrupted is not a partner — and this is a requirement most synthesis integrations do not satisfy by default.

### Constraints on content
- Never speak a figure not simultaneously rendered on screen. Requires a binding check at emission (D1).
- Maximum two sentences without a stop.
- Voice off must lose **presence only**, never information. Every surface is complete in silence.

### Input
Speech recognition is optional to the Bible; nothing in it requires listening. If added, it is subject to every rule above and to §10's prohibition on inferring authority — a spoken "sure, go ahead" is not a grant of standing authority.

## 7 · Runtime implications

### Latency budgets

| Path | Budget | Consequence of breach |
|---|---|---|
| Voice/text synchronisation | 150ms, hard 300ms | Severity 1 — breaks single-mind illusion |
| Override / suspend | Sub-second, unconditional | Severity 1 — revocability is the trust anchor |
| Receipt intent write | On critical path of every action | Slow ledger = slow product, everywhere |
| Session-start attestation | Under ~1s | Otherwise the greeting stalls or lies |
| Ranking of open set | Under ~300ms | Founder waits to read |
| Scope introspection | Immediate | §10 requires answerability "at any moment" |

### The honest-latency constraint

Eng. Law VIII and §7 forbid **both** simulated deliberation and concealed duration. This has a real architectural consequence: the presence state machine must be driven by genuine work signals from the execution layer, not by interface timers. Fast operations must not display thinking; slow ones must not hide it. Most systems fake one or both by default.

### Durability and event sourcing

The receipt ledger is effectively an event-sourced spine. Consider whether the boundary service, tree topology and autonomy measure should be **projections** of it rather than independently maintained state — this is the cleanest way to guarantee they never disagree, and disagreement here is a trust failure rather than a display bug.

### Idempotency

Every action must be idempotent against its intent record. Retries, timer re-fires and reconnects must not double-execute. With money in scope this is a correctness requirement, not a robustness nicety.

### Long-horizon timers

The Bible requires durable timers spanning minutes (undo), days (silence defaults), months (rule expiry) and **a year** (dependency audit). Annual timers are a persistence-and-recovery problem: they must survive deployments, migrations and outages. An audit missed because of a deployment is a governance failure, not a scheduling one.

### Continuous background work versus cost

"It was working while I was away" requires genuinely continuous operation. Cost control must come from **prioritising by consequence**, not from reducing coverage — because reducing coverage silently breaks D7 and therefore breaks *"Nothing needs you."* If work must be shed, the system says which domain it stopped watching.

### Clock and timezone

Deadlines, defaults, greetings and expiries are all founder-local and legally consequential ("renews Friday 00:00"). One canonical timezone source; no ambient local time anywhere in the decision path.

### Concurrency

Cumulative rule caps must be atomic against parallel evaluation. Two simultaneous decisions must not both pass a cap that only one fits under.

### Model dependency

The Voice Charter Validator is a **runtime dependency of every utterance**, and it must be versioned against model changes. Assume every model upgrade will attempt to restore the model's default personality — exclamation marks, enthusiasm, hedging, "Great question." The validator is the only thing standing between that tendency and the founder. Regression-test the personality on every upgrade with the same seriousness as a security test.

## 8 · Migration risks

Ordered by severity. Each names its mitigation.

**R1 · Retrofitting receipt-before-change onto an existing agent loop** — *Severity: critical.*
If actions can currently execute without passing a checkpoint, every such path is a hole, and holes in an audit spine are worse than no spine because they create false confidence. *Mitigation:* make the tool-invocation path the single enforcement point and remove all others. Treat any direct-execution path as a build-breaking defect, not a lint warning.

**R2 · Classifying the existing tool surface for reversibility** — *Severity: high.*
A large one-time audit that is easy to underestimate and tempting to rush. Every misclassification is a potential irreversible action taken automatically. *Mitigation:* fail closed — unclassified means non-executable. Classify pessimistically; upgrade a classification only with evidence of a working compensating action.

**R3 · Rule cumulative accounting** — *Severity: high.*
Windowed, atomic, concurrent-safe accounting over money is where financial bugs live. *Mitigation:* single-writer accounting per rule; treat as ledger arithmetic; never approximate; reconcile against the receipt ledger continuously.

**R4 · The language model reasserting its own personality** — *Severity: high, recurring forever.*
This is not a one-time migration risk; it returns with every model change. *Mitigation:* the validator, plus a personality regression suite run on every upgrade, plus pinned prompts. Budget for this permanently.

**R5 · Removing notifications** — *Severity: high, organisational.*
Technically trivial, politically the hardest item in this document. Engagement metrics will drop and someone will produce a chart. *Mitigation:* change the instrument before removing the feature (§12). Agree the primary metric — the position of the line — in writing, first.

**R6 · Silent data-connector failure** — *Severity: high, chronically underestimated.*
A connector that fails quietly makes "Nothing needs you" a lie, and that specific lie ends customer relationships permanently. *Mitigation:* D7 as a hard gate on the calm state; per-domain health as a first-class product concept surfaced in the founder's own language.

**R7 · Replacing chronological ordering with consequence ranking** — *Severity: medium.*
Ranking is a behaviour founders must trust, and early ranking will be wrong. *Mitigation:* ship the justification with the order from day one. A wrong-but-explained ranking is recoverable; a wrong-and-opaque one is not.

**R8 · The thirty-day proposal threshold** — *Severity: medium, existential to retention.*
If C3 needs ninety days of history to propose confidently, the product loses accounts before it can compound. *Mitigation:* design the miner for low-N confidence with tight caps and short trials. A narrow rule proposed at day twenty beats a perfect one at day ninety.

**R9 · Annual timer survival** — *Severity: medium.*
A year-long timer must outlive every deployment in that year. *Mitigation:* persisted schedule with reconciliation on boot; never in-memory.

**R10 · Multi-principal creep** — *Severity: medium, architectural.*
The Bible assumes one founder. Delegation (C6) introduces a second principal, and if the data model assumes singularity, retrofitting will be expensive. *Mitigation:* model the principal as an entity now, even while only one exists.

**R11 · Feature accretion under conventional metrics** — *Severity: low technically, terminal culturally.*
§12 states it directly: a product whose success is measured in being needed less will look, by conventional instrumentation, like a product that is failing. *Mitigation:* the Section 12 gate in code review, not just in design review.

## 9 · Implementation order

Six phases. The ordering is not preference — each phase makes the next one *safe*, and building out of order produces a system that behaves correctly in the demo and dangerously in production.

---

### Phase 0 · The Spine
**A1 Receipt Ledger · A2 Reversibility Registry · A3 Override**

Nothing autonomous may ship before this exists. The ledger and the registry are what make every later capability auditable and reversible; the override is what makes shipping any of it defensible.

*Gate to proceed:* no execution path in the system can reach a tool without a receipt intent and a reversibility classification. Verified by test, not by review.

---

### Phase 1 · Judgment
**B1 Consequence Engine · B3 Escalation Router · B4 Silence Defaults · B2 Ranking · B5 Evidence Graph**

The product becomes recognisably Kalpavriksha here: it can ask for judgment properly. Note that **B4 belongs in this phase, not later** — the moment the system can create an open request it must also be able to resolve one by default, or it starts accumulating the debt §5 forbids.

*Gate:* no judgment request can be constructed without a complete consequence quartet and a scheduled default.

---

### Phase 2 · Expression
**D1 Narration · D2 Voice Charter · D6 Brief Composer · D4 Presence · D7 Vigilance Attestation**

The AI becomes the interface. **D7 ships in the same phase as the brief** — the calm state must never exist before the attestation that makes it honest. Building the reassuring sentence first and the proof later is the most tempting sequencing error available, and it puts a lie into production.

*Gate:* the entire system state renders as prose; every utterance passes validation; the calm state is unconstructable without complete coverage.

---

### Phase 3 · Autonomy
**C1 Rule Engine · C2 Expiry · C4 Boundary Service · C3 Proposal Miner · C5 Self-Audit**

The line starts moving. C5 ships **with** C3, never after — the ability to act autonomously and the obligation to confess borderline calls are one capability, and separating them creates a window where the product is autonomous but not accountable.

*Gate:* a rule cannot be defined without a cumulative cap, exclusions and an expiry. A firing cannot occur without a receipt. The self-audit cannot be disabled.

---

### Phase 4 · Maturity
**C6 Delegation · E1 Provenance · B6 Confidence · A4 Scope Introspection · D5 Tree Topology**

What makes year two different from month two. The tree's topology service lands here because it derives from the boundary service and the rule history — built earlier, it would encode a structure that does not yet mean anything.

---

### Phase 5 · Governance
**C7 Dependency Audit · E3 Export · E2 Demo Tenant**

The audit can ship last only because it is annual. **It must not be deferred past the first anniversary of the first customer** — which makes it a dated commitment, not a backlog item. Put the date in the plan now.

---

### Two sequencing rules that override the phases

**Never ship autonomy before accountability.** Any capability that lets the system act alone ships in the same release as the mechanism that makes that action visible, reversible and confessable. Not the next release.

**Never ship the reassurance before the proof.** *"Nothing needs you"* is the product's most valuable sentence and its most dangerous. It may only exist once the system can prove it.
