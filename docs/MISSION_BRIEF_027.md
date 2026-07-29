# Mission Brief 027 — AI Capability Broker Architecture

Status: **Frozen (architecture only) — Accepted and ratified by the
founder, 2026-07-29**

Design: `AI_CAPABILITY_BROKER_ARCHITECTURE.md`
Decision records: `docs/adr/0017-ai-capability-broker.md` (the Broker),
`docs/adr/0018-broker-learning-loop.md` (the learning loop, added at
ratification)

## Objective

Design and freeze the intelligence-selection layer: the single service
every Executive asks *"which AI should do this?"*, so that no Executive
ever decides for itself. Architecture only — no implementation, no
provider integration, no Desktop automation, no provider-specific code.

## The Required Analysis, answered

MB027 required a decision, not a deferral: **Kernel Service or
Executive?**

> **Kernel Service** — a Shared Infrastructure component (Constitution
> §5).

Four independent reasons, any one sufficient (full argument:
`AI_CAPABILITY_BROKER_ARCHITECTURE.md` §2, ADR-0017 Decision 1):

1. Both the Brain and the Operator need the same answer. A component both
   columns depend on is the definition of Shared Infrastructure —
   ADR-0010 created that layer to fix precisely this contradiction after
   an independent audit found the Brain reaching into an Operator-owned
   registry. Making the Broker an Executive recreates that bug.
2. It arrives too late in the sequence. Executives are dispatched; the
   Broker must be consulted *before* dispatch, to decide what the dispatch
   contains.
3. Its state must be singular. Monthly spend, standing approvals, and
   benchmark aggregates are ledgers — the same argument that put the
   Permission System in Shared Infrastructure (§5.2).
4. Every Executive would otherwise reach it by Executive-to-Executive
   invocation, which Rule 6 requires be a permission-relaying composite
   call. The most-called component in the system should not be reachable
   only through the heaviest calling convention in the system.

**What the losing option was right about is preserved, not discarded.**
Discovery, scanning, and benchmarking do touch the real machine, and Rule
4 gives Environment access exactly one door. So the concern splits:

> The Broker decides and never touches the machine.
> The **AI Infrastructure Executive** touches the machine and never decides.

## What was frozen

| Deliverable | Where |
|---|---|
| 1. Broker architecture — responsibilities, dependencies, inputs, outputs, extension points, failure handling, verification flow | Architecture §3 |
| 2. Provider Registry | §4 |
| 3. Capability Matrix | §5 |
| 4. Decision Engine | §6 |
| 5. AI Asset Inventory | §7 |
| 6. Recommendation Engine | §8 |
| 7. Cost Model | §9 |
| 8. Benchmark Engine | §10 |
| 9. Founder Approval Policy | §12 |
| 10. AI Infrastructure Executive contract | §11 |
| 11. Desktop Executive interface | §13.1 |
| 12. Capability Packages integration | §13.2 |
| ADR-0017 | `docs/adr/0017-ai-capability-broker.md` |

## The five decisions worth reading

**1. Cheapest tier that clears a quality floor — and refuse rather than
guess.** MB027 asks for "highest probability of success while minimizing
cost" and freezes a six-rung cost ladder. Those pull against each other,
and the brief does not say how they resolve. Pure cost-minimisation hands
every mission to a 1B local model, most fail cheaply and repeatedly, then
get retried somewhere expensive anyway. Pure success-maximisation routes
everything to the frontier API and makes local-first decorative. The
resolution: walk the ladder from the cheapest rung, stop at the first tier
with a candidate clearing the request's quality floor, and if no tier
clears it, return `NO_CAPABLE_PROVIDER` instead of selecting the best of a
bad set. The floor is configuration per task class, not a constant.

**2. The Broker creates no new execution path.** Its output is the name of
an *already-registered* Constitution Capability plus parameters; the
caller runs it through the Operator like anything else. Without this rule
the Broker becomes a second, unaudited route to the outside world, and
every other guarantee in the design turns cosmetic. It is also what keeps
retry with the Runtime and Brain (MB024), approval with the Permission
System (§5.2), Environment access behind Rule 4, and verification with the
Verification Subsystem (ADR-0011) — instead of quietly duplicating four
existing ownership decisions.

**3. Observed beats declared, and Verification defines "success."** Every
matrix attribute is stored twice — `declared` (vendor documentation) and
`observed` (this system's own history) — and observed wins. That is
Constitution Rule 8, the Evidence Hierarchy, applied to provider
selection: a Provider cannot market its way up the ranking. And a
benchmark sample records the **Verification Verdict**, not an API status
code, because a model returning a fluent, confident, wrong answer must
score as a failure. Otherwise the store systematically comes to prefer
providers that fail *articulately*.

**4. Determinism is what makes auditability real.** Same request + same
registry + same inventory + same benchmark aggregates + same policy
version ⇒ the same decision, always; ties break on `provider_id`
lexicographically, never on dict ordering or wall-clock. Every decision
carries an `inputs_digest` and the **full list of rejected providers with
reasons** — because the question a founder asks six weeks later is "why
didn't it use the local one?", and a record containing only the winner
cannot answer it. A corollary stated out loud: **no model call is made to
make a decision.** A Broker that asked an AI which AI to use would need an
AI to make that choice; this design never starts the recursion.

**5. Recommendations are inert, and approval reuses what exists.** Nothing
in Kalpavriksha consumes a recommendation to act — the same structural
boundary ADR-0016 drew around Dashboard health. An accepted recommendation
becomes a **Self-Development Queue** item, the component MB023 already
built for "the system lacks something." Likewise the Broker implements no
approval machinery: paid selection checks the existing Permission System,
which means ADR-0009's guarantee is inherited free — an
`ALWAYS_FOR_CAPABILITY` grant can never satisfy an `IRREVERSIBLE` check,
so a standing "yes, use paid AI" can never auto-authorise buying a
subscription.

## Two collisions found during design, resolved rather than glossed

Both follow ADR-0014's precedent — a collision surfaced during design is
resolved explicitly, in writing, in the same commit.

1. **"Capability" was already taken.** Constitution §17 freezes it as a
   dispatchable unit of execution (`Browser.Navigate`); MB027 uses the
   same word for a kind of intelligence (`vision.ocr`). Resolved by naming
   the second **AI Capability** and making the two distinguishable
   *mechanically*: Capabilities are `PascalCase.PascalCase` (Mission
   Control's existing qualified-name rule), AI Capabilities are
   `lowercase.dotted`. A test can tell them apart.
2. **Constitution §3.3 already gives the Model Router a selection role.**
   Not superseded — generalised. All four of its criteria map onto the
   Decision Engine (Architecture §6.5), which is the evidence that the
   Broker extends a frozen design rather than competing with it. One
   narrowing is stated plainly rather than smuggled: §3.3's "explicit user
   preference always wins" is honoured *among candidates that survived the
   hard-constraint filter* — a preference cannot select something
   unavailable, licence-barred, privacy-barred, or paid-without-approval.

## One addition to MB027's own policy

MB027's approval policy is organised entirely around money. Added:
**sending data tagged sensitive to any third-party Provider requires
approval, including a free one.** A free cloud model is still a third
party receiving the founder's data, and §3.3 criterion 2 already treats
privacy as first-class routing. Gating a £0.002 paid call while waving
through a free upload of the same content protects the wrong thing.

## One restructuring of what the brief asked for

Deliverable 3 lists "Reasoning, Coding, Vision, OCR … Latency, Quality,
Cost, Availability, Licensing, Rate Limits" as a single capability list.
Frozen as two axes instead: **AI Capabilities** (what a Provider can do —
it either offers one or does not) and **attributes** (how well, at what
price, under what terms — these qualify every offer and change over time).
Merged, "cost" becomes something a Provider "can do" and the Decision
Engine's filter phase cannot be written cleanly. Split, each axis has one
job. Architecture §5.1 states this and why.

## Acceptance criteria

| Criterion | Status |
|---|---|
| Architecture frozen | ✅ §3 |
| Provider Registry frozen | ✅ §4 |
| Capability Matrix frozen | ✅ §5 |
| Decision Engine frozen | ✅ §6 |
| Cost Model frozen | ✅ §9 |
| Recommendation Engine frozen | ✅ §8 |
| Benchmark architecture frozen | ✅ §10 |
| Founder Approval Policy frozen | ✅ §12 |
| Desktop interface frozen | ✅ §13.1 |
| Capability Package interface frozen | ✅ §13.2 |
| ADR-0017 completed | ✅ |
| Roadmap updated | ✅ `ROADMAP.md` |
| Living Founder Memory updated | ✅ `PROJECT_BRAIN.md`, `DECISIONS.md`, `MIRACLE_LEDGER.md` |
| No existing architecture modified | ✅ by the brief — the one Constitution amendment it requires was *proposed*, not made. Applied afterwards, on founder ratification (see below) |
| No Constitution violations | ✅ |
| No implementation performed | ✅ `src/` and `tests/` byte-identical to the MB026 tag |

## Founder ratification — 2026-07-29

Placing a new component in Shared Infrastructure touches four **FROZEN**
Constitution sections (§5, §6, §16, §17). The freeze process permits this
through an ADR (`FOUNDER_CONSTITUTION_FREEZE.md` §4a; precedent
ADR-0014) — but MB027's acceptance criteria say "no existing architecture
modified," and MB025 set the precedent for exactly this situation:
propose, do not decide unilaterally. So the brief wrote the amendment out
in full and left `KALPAVRIKSHA_VISION_V2.md` untouched.

**The founder accepted MB027, ratified ADR-0017, and approved both the
Kernel Service placement and the Broker / AI Infrastructure Executive
split.** The amendment was then applied in one pass as **Constitution
Amendment 2**: §3.3 gains one clarifying sentence, §5.7 is the Broker
(prior §5.7 renumbered §5.8 and now names machine scanning, probing,
benchmarking, inventory, and installation as deliberately *not* Shared
Infrastructure), §6's module table plus a new "which Provider serves a
request" row, two rows in §16, two rows in §17. §5.7 carries status
**RESEARCH-BACKED** — frozen in shape, not yet proven by implementation.

This is the **first structural amendment** made under the freeze process
(Amendment 1 was a terminology reconciliation), and the freeze record now
states the precedent it set: *a structural amendment is proposed by a
Mission Brief and applied only after founder ratification; a terminology
reconciliation forced by shipping code may move in the same commit.*

## The learning loop — added by founder directive at ratification

> *"The Broker must become self-improving through long-term usage
> analytics, benchmark history, cost optimization, privacy awareness, and
> Founder-approved AI ecosystem evolution. This learning loop should
> become a first-class architectural objective for the AI Infrastructure
> Executive."*

Frozen as `AI_CAPABILITY_BROKER_ARCHITECTURE.md` §19, decided in ADR-0018.
The design problem is that self-improvement collides head-on with the
determinism-and-replay guarantee that makes every provider decision
auditable in the first place. The resolution is a separation, not a
compromise:

> **The decision *procedure* never learns. The versioned *policy* it reads
> does — evidence-backed, Founder-promoted, and revertible.**

Every decision already carries `policy_version`, so a decision made under
v7 replays against v7 forever, and learning produces v8 as a discrete
artifact a human can read, accept, reject, and roll back.

Five things worth carrying forward:

1. **Three owners.** The Broker holds the data; the **AI Infrastructure
   Executive** does the analysis; the Founder promotes. The Executive gets
   the analysis not only because the directive says so but because it is
   the only component that can also check a proposal for *feasibility*
   against the real machine — analytics without that context proposes
   "switch to the 70B local model" on a host that cannot load it.
2. **It is ADR-0012's Knowledge Lifecycle**, applied to provider
   selection, so it rides MB023's existing human-gated queues. **Zero new
   approval paths.**
3. **Privacy is a one-way ratchet.** The loop may propose *tightening* a
   privacy constraint and may never propose loosening one. Every other
   guard is a threshold; this one is a direction, because the optimisation
   pressure runs exactly the wrong way — cloud providers usually *do* look
   better on success rate and latency, so a loop free to propose
   relaxation would propose it correctly, repeatedly, and with real
   evidence attached, which is what makes it dangerous.
4. **Every promoted change needs a `rollback_condition`** or it is refused
   at generation, with a review window and automatic reversion if verified
   success degrades. Rollback is nearly free because `policy_version` is
   already first-class.
5. **Exploration is budgeted.** Without it a low-ranked Provider never
   gets sampled, so it stays low permanently — including after an upgrade
   that fixed it. Bounded to low-stakes requests: exploration spent on
   critical work is gambling, not learning.

**Scheduled at the same time, deliberately not designed:** a **Policy
Simulator** (§19.8) validating a proposed policy version against
historical missions before it reaches the founder for approval. It is
nearly free to build because §6.6's determinism-and-replay guarantee
already makes past decisions re-derivable — the simulator is that
mechanism pointed at a different policy version, which is a good sign that
determinism was the right thing to freeze. One constraint has to be built
in from the start: replay reports what would have been *selected* as fact,
and success effects only as a labelled estimate, because no outcome exists
for a Provider that was never called.

**One change to what MB027 froze, recorded rather than absorbed
silently.** The directive assigns *installation* to the AI Infrastructure
Executive; MB027's frozen contract explicitly excluded it. `InstallProvider`,
`RemoveProvider`, and `UpgradeProvider` are now in that contract at
**`IRREVERSIBLE`** tier — which means ADR-0009 guarantees, mechanically,
that no standing grant can ever authorise one. MB027's "no automatic
downloads" rule survives and is now structural rather than declared:
nothing in the system can *trigger* these capabilities, because the Broker
executes nothing and recommendations are inert data. The only path runs
through a founder accepting a recommendation into the Self-Development
Queue.

## Technical Debt and Known Limitations (Rule 10)

Full list: `AI_CAPABILITY_BROKER_ARCHITECTURE.md` §16. The three that
matter most:

1. **The learning loop's guards are reasoned, not calibrated.**
   Exploration fraction, minimum sample counts, review windows, rollback
   thresholds, floor minimums — all configuration, none with an empirical
   basis yet, and none knowable before real usage. The shape is frozen;
   every number in it is a first guess. Related: **rollback reverts
   policy, never effects** — an install or a month of spend made under a
   policy cannot be undone by reverting it, which is why ecosystem
   mutation is separately gated at `IRREVERSIBLE`.
2. **`plugins/model_router.py` is a live contradiction.**
   `select_provider()` hardcodes the strings `"hermes"` and `"chatgpt"` —
   product names in Brain logic, which Constitution §14/§21 forbid. The
   Broker supersedes that method; the Model Router keeps its `generate()`
   interface and asks the Broker instead of ranking providers itself.
   **No code was changed by this Mission Brief** — the migration is a
   future implementation brief, now on `ROADMAP.md`.
3. **Success-probability estimation for a novel task class is the weakest
   part of the design.** Cold start is defined and reasonable but
   genuinely unproven; the first real workload will likely force a
   revision of the penalty and floor defaults. They are configuration, not
   constants, which is the hedge.

## The Final Architectural Question

> *"Does this architecture increase Kalpavriksha's ability to build
> Kalpavriksha?"*

**Yes — unambiguously.** The decisive one of four reasons (all four:
Architecture §17): every future Executive would otherwise each pick its
own provider, hold its own key, and encode its own fallback — N copies of
one policy, drifting. With the Broker, an Executive that needs
intelligence writes one `CapabilityRequest` and is done. **The cost of
building the next Executive goes down because this exists**, which is the
only reason to build it before the Executives that need it.

The honest counter-argument, stated rather than avoided: this makes one
component a dependency of everything, and a bug in it degrades every
mission at once. Mitigated by its shape — deterministic policy over plain
data, no I/O, no network, the most testable thing in this codebase — and
by refusal-over-guessing, which makes its worst realistic failure "the
system stops and says why" rather than "the system quietly used the wrong
thing."
