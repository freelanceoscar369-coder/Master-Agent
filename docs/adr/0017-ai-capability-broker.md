# ADR-0017: The AI Capability Broker — a kernel service for intelligence selection

Status: **Accepted — ratified by the founder 2026-07-29. The Constitution
amendment has been applied.** — Mission Brief 027

Supersedes nothing. Amends `KALPAVRIKSHA_VISION_V2.md` §3.3, §5, §6, §16,
§17 (Amendment 2, recorded in `FOUNDER_CONSTITUTION_FREEZE.md` §4a).
Full design: `AI_CAPABILITY_BROKER_ARCHITECTURE.md`.

## Context

Every Executive still to be built — Desktop, Research, Knowledge,
Filesystem, Terminal, Git — will need AI. The question "which AI?" has to
be answered somewhere, and there are only two places it can go: inside
each Executive, or in one shared component.

Inside each Executive, it is answered N times. N copies of a provider
list, N sets of credentials, N fallback ladders, N cost assumptions, N
opinions about whether a paid API is acceptable. They drift immediately
and there is no single place to audit what was chosen or what was spent.
The system's own growth — which is the point of Kalpavriksha — makes this
worse the faster it works.

Two frozen facts constrain the answer, and both were verified against
source before designing anything:

1. **Constitution §3.3 already gives the Brain's Model Router a provider-
   selection role**, with four named criteria. Any new selector either
   subsumes it or competes with it, and §16 requires every component be
   owned exactly once.
2. **Constitution §17 already freezes "Capability"** to mean a
   dispatchable unit of execution (`Browser.Navigate`). MB027 uses the
   same word for a kind of intelligence (`vision.ocr`). Left implicit,
   this collides the way "Executive"/"Worker" collided in MB023.

## Decision 1 — The Broker is a Kernel Service, not an Executive

MB027 required this be answered, not deferred. **Kernel service —
specifically, a Shared Infrastructure component (§5).**

### Options considered

1. **An Executive.** Rejected, on four independent grounds, any one
   sufficient:
   - Both the Brain (Model Router, Planner) and the Operator (an Executive
     mid-task) need the same answer. A component both columns depend on is
     the *definition* of Shared Infrastructure — ADR-0010 introduced that
     layer to fix exactly this contradiction after an independent audit
     found the Brain reaching into an Operator-owned registry. Placing the
     Broker in the Operator's column recreates the bug ADR-0010 fixed.
   - It arrives too late in the sequence. Executives are dispatched by
     Mission Control and the Runtime; the Broker must be consulted
     *before* dispatch, to decide what the dispatch contains. A thing
     consulted before dispatch cannot be a thing that is dispatched.
   - The state it owns must be singular. Monthly spend, standing
     approvals, and benchmark aggregates are ledgers; two Operator
     Instances holding two copies is the same class of bug that made §5.2
     elevate the Permission System to Shared Infrastructure.
   - Every future Executive would have to reach it by
     Executive-to-Executive invocation, which Rule 6 requires be a
     permission-relaying composite call. Making the most-called component
     in the system reachable only through the heaviest calling convention
     is backwards.
2. **A Brain component (extending the Model Router).** Rejected: an
   Executive needing OCR mid-task would then have to call into the Brain,
   which §6 forbids outright. It also makes cost and approval — Mission-
   wide, cross-Operator facts — Brain-local.
3. **A Shared Infrastructure kernel service.** Chosen.

### What the rejected option was right about, and how it is preserved

The strongest argument for "Executive" is Rule 4: discovery, scanning,
probing, and benchmarking all touch the real machine, and Environment
access has exactly one door. That argument is correct and is honoured by
splitting the concern rather than compromising the placement:

> **The Broker decides and never touches the machine. The AI
> Infrastructure Executive touches the machine and never decides.**

The Broker consumes an inventory; it never produces one. This is the same
shape as Mission Control's coordination catalogue versus a Worker's live
handles, applied one layer down — and it is why the Broker can hold the
frozen rule "zero provider SDK imports," enforceable by the same
import-parsing test pattern MB023/MB024/MB025 already use.

## Decision 2 — The Broker selects; it never executes, spends, retries, or approves

The Broker returns a `BrokerDecision` naming an already-registered
Constitution Capability plus parameters. The caller resolves it through
the Capability Registry (§5.1) and runs it through the Operator, exactly
as it would any other Capability.

**The Broker creates no new execution path.** This is what stops it
becoming a second, unaudited route to the outside world — the one failure
mode that would make every other guarantee in the design cosmetic. It also
keeps four existing ownership decisions intact rather than quietly
duplicating them: retry stays with the Runtime and the Brain (MB024's
resolution), approval stays with the Permission System (§5.2), Environment
access stays behind Rule 4, and verification stays with the Verification
Subsystem (ADR-0011).

## Decision 3 — Cheapest tier that clears a quality floor, and refuse rather than guess

MB027 freezes a six-rung priority ladder (local → desktop app → free cloud
→ free aggregator → existing subscription → paid API) and asks for "the
highest probability of success while minimizing cost." Those two goals
pull against each other and the brief does not say how they resolve. This
ADR resolves it:

> Selection walks the ladder from the cheapest rung and stops at the first
> tier containing a candidate whose expected success probability clears
> the request's quality floor. If no tier clears it, the Broker returns
> `NO_CAPABLE_PROVIDER` rather than selecting the best of a bad set.

### Options considered

1. **Pure cost minimisation.** Rejected: a 1B local model gets every
   mission, most fail cheaply and repeatedly, then get retried somewhere
   expensive anyway — the worst of both, and it makes the failure look
   like a mission problem rather than a routing problem.
2. **Weighted score over cost, quality, and latency.** Rejected: a single
   blended number cannot be audited. "Why didn't it use the local one?"
   has no answer beyond "the weights said so," and any weight change
   silently rewrites every past decision's logic.
3. **Cheapest tier clearing an explicit floor.** Chosen. Local-first stays
   a genuine priority rather than a slogan; the escape hatch is a named,
   configurable number per task class rather than a hidden coefficient;
   and each rejection carries a reason.

The floor is configuration, not a constant: the right threshold for
"summarise this file" and "plan a mission" are different numbers and
always will be.

## Decision 4 — Every decision is deterministic and replayable

Same request + same registry + same inventory + same benchmark aggregates
+ same policy version ⇒ the same decision, always. Ties break on
`provider_id` lexicographically — never dict ordering, wall-clock, or
randomness — and each decision carries an `inputs_digest` over those five
things.

This is what turns MB027's Rule 15 ("every provider decision must be
auditable") from a claim into a property: a past decision can be
reconstructed and re-derived. It also settles a question worth stating out
loud: **no model call is made to make a decision.** The Decision Engine is
deterministic policy over data. A Broker that asked an AI which AI to use
would need an AI to make that choice; this design never starts the
recursion.

A corollary the design accepts deliberately: decision *caching* is not
built, because a cached decision must be invalidated by inventory, budget,
benchmark, and policy changes independently, and a stale hit spends money
the budget filter would have refused. Determinism means caching can be
added safely later, with explicit invalidation, when a measured need
exists.

## Decision 5 — Observed beats declared, and Verification defines "success"

The Capability Matrix stores every attribute twice: `declared` (manifest,
config, vendor documentation) and `observed` (this system's own benchmark
history). Where observed exists, it wins.

This is Constitution Rule 8 — the Evidence Hierarchy, observed reality
over documentation — applied to provider selection. A Provider cannot
market its way up the ranking.

And the sample that feeds `observed` records the **Verification Verdict**
(ADR-0011), not an API status code. A model that returns a fluent,
confident, wrong answer scores as a failure. Without this rule the
Benchmark Store would systematically come to prefer providers that fail
*articulately*, which is a worse outcome than having no benchmark data at
all.

`inconclusive` is a distinct third verdict and counts as neither success
nor failure — treating "we could not tell" as success is how a benchmark
store fills with fiction.

## Decision 6 — Recommendations are inert, and route through machinery that exists

The Recommendation Engine produces data. **Nothing in Kalpavriksha
consumes a recommendation to act.** Deleting the entire engine would
change what the founder sees and nothing about what the system does —
deliberately the same boundary, drawn the same structural way, that
ADR-0016 drew around Dashboard health classification.

A recommendation the founder accepts becomes a **Self-Development Queue**
item — the component MB023 already built for "the system lacks something"
— and flows through normal Mission Control planning and approval. No new
action path, no new approval path, and the Broker stays on the correct
side of "never performs work."

Every recommendation must carry falsifiable evidence (decision IDs,
sample IDs, ledger references) or it is refused at generation. "Consider
upgrading your model" is noise; a claim a founder can check and reject is
not.

## Decision 7 — Approval reuses the Permission System, and free is not the same as private

The Broker implements no approval machinery. Paid selection is expressed
as a check against Shared Infrastructure's existing Permission System
(§5.2), which already holds the grant ledger and already has Mission-wide
veto power.

Two properties are inherited rather than rebuilt:

- Acquiring a subscription is `IRREVERSIBLE`, and per ADR-0009 an
  `ALWAYS_FOR_CAPABILITY` grant can never satisfy an `IRREVERSIBLE`
  check. A standing "yes, use paid AI" can therefore never auto-authorise
  buying a new subscription. That guarantee is already shipped and tested.
- "One approval per mission" (§15.3) applies unchanged.

**One addition to MB027's policy, made deliberately:** sending data tagged
sensitive to *any* third-party Provider requires approval, including a
free one. MB027's policy is organised entirely around money, but a free
cloud model is still a third party receiving the founder's data, and §3.3
criterion 2 already treats privacy as first-class routing. Gating a
£0.002 paid call while waving through a free upload of the same content
would be protecting the wrong thing.

## Decision 8 — Two terminology rulings, made now rather than left to collide

Following ADR-0014's precedent (a collision found during design is
resolved explicitly, in writing, in the same commit):

1. **"AI Capability" ≠ "Capability".** A Capability (§17, unchanged) is a
   dispatchable unit of execution. An AI Capability is a kind of
   intelligence and is never dispatchable on its own. They are made
   distinguishable *mechanically*, not by convention: Capabilities are
   `PascalCase.PascalCase` (Mission Control's existing qualified-name
   rule); AI Capabilities are `lowercase.dotted`.
2. **"Provider" generalises "Reasoning Provider"; it does not replace
   it.** A Reasoning Provider (§3.3) is a Provider offering the
   `reasoning` AI Capability. Nothing is renamed, and §17's prohibition on
   third synonyms is respected.

## Constitution amendment — RATIFIED AND APPLIED (2026-07-29)

Placing a new component in Shared Infrastructure touches four FROZEN
sections. The freeze process permits this (`FOUNDER_CONSTITUTION_FREEZE.md`
§4a; precedent ADR-0014), but MB027's acceptance criteria said "no
existing architecture modified," so following MB025's precedent the
amendment was **proposed rather than made**, and
`KALPAVRIKSHA_VISION_V2.md` was left untouched by the Mission Brief
itself.

**The founder ratified this ADR on 2026-07-29**, at which point the
amendment below was applied in one pass and recorded as **Amendment 2** in
`FOUNDER_CONSTITUTION_FREEZE.md` §4a. What was applied:

| § | Change |
|---|---|
| §5 | New subsection **5.7 AI Capability Broker**, with its "belongs here because" rationale (both Brain and Operator consult it; its ledgers must be singular across Operator Instances). Current §5.7 ("What Is Deliberately NOT Shared Infrastructure") renumbers to §5.8 and gains one row: *machine scanning and provider probing are not Shared Infrastructure — they are Environment access, and belong to the AI Infrastructure Executive.* |
| §6 | Shared Infrastructure's "Modules" cell gains "AI Capability Broker". |
| §16 | Two rows: **AI Capability Broker → Shared Infrastructure (§5.7)**, and **AI Infrastructure Executive → Operator (Worker, §12)**. |
| §17 | Two rows: **AI Capability** and **Provider**, as ruled in Decision 8. |
| §3.3 | **No change to the four criteria.** One clarifying sentence: the Model Router resolves *which* Reasoning Provider by consulting the Broker, rather than implementing its own ranking. Its interface, its role, and all four criteria stand (`AI_CAPABILITY_BROKER_ARCHITECTURE.md` §6.5 maps each one). |
| `FOUNDER_CONSTITUTION_FREEZE.md` §4a | One amendment row, as the process requires. |

Applied exactly as specified above, with two additions made while
applying it, both consistent with the ratified intent and recorded here
rather than made silently: §6's comparison table gained a **"which
Provider serves a request"** row (Brain asks, Shared Infrastructure
decides, Operator asks), and `FOUNDER_CONSTITUTION_FREEZE.md`'s §4
registry notes that §5.7 is **RESEARCH-BACKED** while the rest of §5 stays
FROZEN — designed and frozen in shape, not yet proven by implementation.

The freeze record also now states the precedent this set: **a structural
amendment is proposed by a Mission Brief and applied only after founder
ratification; a terminology reconciliation forced by shipping code
(Amendment 1) may move in the same commit.**

## Consequences

- **Every future Executive gets cheaper to build.** It writes one
  `CapabilityRequest` instead of a provider list, a credential, a
  fallback ladder, and a cost opinion. This is the main reason the Broker
  is worth building before the Executives that need it.
- **One component becomes a dependency of everything.** A bug in it
  degrades every mission at once. Mitigated by its shape: deterministic
  policy over plain data, no I/O, no network — the most testable thing in
  this codebase — and by refusal-over-guessing, which makes its worst
  realistic failure "the system stops and says why" rather than "the
  system quietly used the wrong thing."
- **`plugins/model_router.py` is now a documented contradiction.**
  `select_provider()` hardcodes the strings `"hermes"` and `"chatgpt"` —
  product names in Brain logic, which §14/§21 forbid. The Broker
  supersedes that method. **No code was changed by MB027**; the migration
  is named in `ROADMAP.md` as a future implementation brief.
- **Broker state must persist or budgets stop being budgets.** The cost
  ledger, standing approvals, benchmark aggregates, and the inventory all
  have to survive a restart (MB025's shape, no contract change). The
  registry itself does not — it is reconstructible from Configuration and
  a rescan.
- **Named cost, not hidden:** raw benchmark samples grow without bound.
  Selection is insulated (it reads incrementally-maintained aggregates,
  never raw history), but compaction is deliberately not designed here —
  it needs a retention policy that does not exist yet. This is the *same*
  open item already on `ROADMAP.md` for the persisted event log, and it
  should be solved once, for both.
