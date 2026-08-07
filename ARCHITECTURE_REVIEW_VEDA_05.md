# Architectural Review — VEDA 05 Organizational Architecture v1.0

**Type:** Consistency review. Not a VEDA. Not an amendment. No section of VEDA 05 modified.
**Date:** 2026-08-05
**Reviewed against:** VEDA 01 Experience · VEDA 02 Design Constitution · VEDA 03 Founder Dashboard · VEDA 04 Architecture Requirements — all treated as frozen and correct.
**Standard applied:** would a future engineer, inheriting this in 2036, be able to live with every clause approved today?

**Findings:** 16 weaknesses, 8 blind spots. Seven of the sixteen are direct conflicts with a frozen VEDA clause. The spine of the architecture survives review; specific clauses do not.

---

## Strengths — what should never change

These survived all five tests. Several are load-bearing in ways that are easy to erode later, so they are listed with the reason they matter rather than as praise.

**S1 · Irreversibility is not delegable at any tier.** §4.1's final row denies irreversible authority to the Objective Engine itself, not merely to departments. This is VEDA 01 §10 Ethics 3 converted from a promise into a structural property. Under pressure, the natural erosion is a "trusted department" exception. There must never be one.

**S2 · The Objective Engine counts the completion poll but cannot cast a vote, and absence is never assent.** A coordinator that can manufacture a GO is a coordinator that will, on a deadline. The rule is cheap now and irreplaceable later.

**S3 · Craft disputes escalate rather than being arbitrated (§9.4 A4).** A non-craft authority settling a craft dispute is the mechanism by which quality dies in every organization that has tried it. The Engine computing impact and handing over a decision rather than a dispute is the correct division, and it is rare.

**S4 · L1 and L2 improve competence; only L3 touches authority, and L3 cannot enact.** This is the single property that makes a decade of compounding capability safe, and it aligns exactly with VEDA 03's refusal of "silent rule creation from inferred consent." If any future change lets a department widen its own scope by getting good at its job, the architecture has failed regardless of what else survives.

**S5 · The four tool prohibitions (§8.1).** No department selects a Provider, introduces a tool, holds a grant, or touches an Environment. These are what keep seven departments from becoming seven execution paths — the failure VEDA 04 R1 rates critical.

**S6 · An objective whose "done" is not checkable is refused at admission.** This prevents the completion poll from becoming a formality and is the cheapest quality mechanism in the document.

**S7 · The andon cord is free, unpenalized, and explicitly excluded from any metric.** A cord anyone hesitates to pull does not exist. The exclusion from metrics is the part that will be argued about; it is the part that makes it work.

**S8 · No Strategy department.** The correct omission, and the one most likely to be proposed as an addition.

**S9 · Five internal escalation tiers, only two of which the founder experiences.** Passes the simplicity test cleanly: internal tier count is not founder-facing complexity. (The mapping to VEDA 03's surface does not pass — see W4.)

**S10 · Departments own no state.** The single decision that keeps them from becoming silos and keeps them device-agnostic. (Contradicted twice inside VEDA 05 — see W11.)

---

## Weaknesses — genuine issues only

Ordered by severity. Each names the frozen clause it conflicts with and the concrete consequence. Directions are indicated where they exist, but this review does not redesign.

### Critical — direct conflicts with frozen clauses

**W1 · Department charters are unbounded, unexpiring grants of authority.**
*Conflicts with:* VEDA 01 §10 Rules (five mandatory parts) · VEDA 04 C1 (a rule without a cumulative cap is malformed and rejected at definition time) · VEDA 04 C2 (a permission with no end date cannot be persisted) · VEDA 03 (rule anatomy is non-negotiable, five parts).

Every charter in §4.2 contains a "Decision authority" clause. Each is a delegation of judgment. None carries a cumulative limit or an expiry. The clearest instance is Operations: *"Rollback — immediate, unilateral, no approval required, at any hour."* That is a permanent, uncapped, non-expiring standing grant, authored preemptively, created outside the Standing Rule Engine.

*Consequence:* seven permanent authorities that the expiry daemon cannot reach, that never appear in the autonomy ratio, and that the founder never granted through the mechanism VEDA 01 §10 says is *the* mechanism by which judgment is delegated. The tree cannot show them. The dependency audit cannot enumerate them, because C7 enumerates rules.

*Direction:* charters should define what a department is competent to **judge**; every authority to **act without asking** should still flow through the Standing Rule Engine with a cap and an expiry. VEDA 05 conflates competence with permission.

---

**W2 · The Mistake Protocol has no channel.**
*Conflicts with:* VEDA 04 D3 — error disclosure "may not be gated by any suppression, batching or quality-scoring mechanism," and error detection must have a direct path to narration that cannot suppress it.

§3.4's CAPCOM rule gives departments no reference to any surfacing interface; everything routes through the Judgment service and consequence ranking. **Ranking is a quality-scoring mechanism.** A department that detects its own error therefore cannot disclose it on the path D3 requires. VEDA 05 defines no mistake channel at all — errors are implicitly E3 judgment requests, which is precisely the gating D3 forbids.

*Consequence:* this damages the mechanism VEDA 03 identifies as doing more for trust than anything else in the product — the unprompted borderline-call disclosure inside the receipt. The CAPCOM rule is correct; its blast radius was not checked against D3.

---

**W3 · The Vigilance Attestation now depends on a department.**
*Conflicts with:* VEDA 04 D7 · VEDA 04 §2 (data connectors report freshness and health per domain to feed D7).

In VEDA 04, connectors report freshness directly to the attestation. §4.2.5 inserts Operations as the reporter of per-domain freshness. That places a fallible intermediary in the path of the product's most trust-critical sentence.

*Consequence:* a degraded Operations makes the attestation unable to distinguish *"no gaps"* from *"no report."* D7's entire value is that it is provably complete; an intermediary that can fail silently converts a proof into an assumption. VEDA 04 R6 rates silent connector failure as the failure most likely to end a customer relationship permanently — this adds a second place it can happen.

---

**W4 · Five escalation tiers emit into a founder surface that has three, and the mapping is absent.**
*Conflicts with:* VEDA 03 (three tiers — Needs you / Sweep / Auto-handled; one decision at a time, never a list; the receipt collapsed to two numbers).

| VEDA 05 tier | Surface in VEDA 03 |
|---|---|
| E0 Auto | Auto-handled receipt. **Consistent.** |
| E1 Peer | "One line in the brief" — **no such category exists.** Not auto-handled (no rule fired), not a request. |
| E2 Contract | Same. **No home.** |
| E3 Judgment | Splits across Needs-you and Sweep by reversibility — **VEDA 05 never makes the mapping.** |
| E4 Halt | Surfaces "immediately, outside ranking" — **no slot.** Screen 01 holds one decision at a time, supplied by the ranking. |

*Consequence:* either the frozen first screen grows a fourth category, or E1/E2/E4 output is undeliverable. At a hundred concurrent objectives, E1 and E2 are the highest-volume events in the system, and VEDA 05 authorized a line in the brief for each without a budget. VEDA 04 D6 requires completed work to collapse to *one line and a receipt* per objective — not one line per internal decision within it.

---

**W5 · Two ranking bypasses are invented.**
*Conflicts with:* VEDA 03 (ranking function frozen as `irreversibility × log(exposure) × deadline_proximity × novelty`, inspectable, with no bypass term) · VEDA 04 B2 (every ordering defensible in one sentence; ranking failure is an incident, not a degradation).

§6.3 creates an unranked channel for a Vigilance gap and one for a fraud signal.

*Consequence:* bypass channels proliferate — the second is always easier to justify than the first, and each one makes the queue's order less explainable. Worth noting: **both cases already score at the top of the frozen function.** Fraud is maximal on irreversibility and exposure; a vigilance gap is maximal on novelty and blocks the greeting through D7's own mechanism regardless of queue position. The bypasses are non-conforming *and* unnecessary.

---

**W6 · A second autonomy metric is introduced.**
*Conflicts with:* VEDA 03 (the headline metric is the autonomy ratio) · VEDA 04 C4 ("every other autonomy-related surface derives from this service. Four independently computed autonomy numbers is a guaranteed future inconsistency").

§12.5 and R12 propose "judgments required per objective, trending down" as the departmental metric.

*Consequence:* exactly the second number C4 forbids. It is also derivable from the existing one, so it buys nothing in exchange for the inconsistency it guarantees. This is the C4 failure mode occurring in the very document that cites C4.

---

**W7 · Department branches in the tree.**
*Conflicts with:* VEDA 01 §9 — "Each primary branch is a domain of delegated judgment. A branch comes into being when the founder grants their first standing rule in that domain. **The founder therefore grows the tree.**" And: "This mapping is fixed. Nothing may be added to it without amending this Bible." And: "The tree cannot be grown by the AI's effort, only by the founder's permission — which means it can never be gamed, inflated, or optimised for. It is the one measure in the product that the product itself cannot move."

§12.5 claims department branches appear in the tree topology, as the mitigation for hierarchy-induced distance.

*Consequence:* this would let the AI's own structure grow the tree, destroying the single property that makes it trustworthy. It is the most direct conflict in the review and the mitigation it was serving must be found elsewhere.

---

### High

**W8 · Contracting has no silence default.**
*Conflicts with:* VEDA 04 B4 — no open request may exist without a scheduled default; an item that can sit indefinitely is a defect.

R9 correctly gave the completion poll a deadline and a no-go default. Contracting (§5.2 phase 3) received neither. A department that never answers a contract offer stalls an objective the founder has already approved, between admission and execution, with nothing firing and nothing surfacing.

**W9 · A4 craft disputes have no derivable default.**
*Conflicts with:* VEDA 04 B4.

Every open request must carry a default. A craft tie-break between two Heads has no safe one — firing either way makes a craft decision the founder did not make, which is the precise thing §9.4 A4 exists to prevent. The only honest default is halting the objective, and VEDA 05 does not say so. If the founder is offline for a week, this class of request currently either fires wrongly or violates B4.

**W10 · Internal decisions leave no record.**
*Gap against:* VEDA 04 A1, whose Action is defined as state change *outside* the system.

A Head's sign-off, a craft rejection, a contract refusal, and an amendment ruling are not Actions under A1 and are therefore not receipted. §12.5 nevertheless claims "every actor writes intent before acting."

*Consequence:* the decisions that most shape an objective's outcome are the ones the ledger does not hold. The andon halt is the only internal decision VEDA 05 explicitly receipts. The transparency claim is stronger than the mechanism supporting it, and an over-claim on the Trust Spine is worse than a stated gap.

**W11 · Two internal contradictions on state ownership.**
R2 states departments own no state. §4.2.7 says Correspondence "owns the relationship record"; §4.2.6 gives Finance ledger reconciliation. Both records must live in Memory (§5.4). The intended meaning is presumably *owns the standard over* — but as written, S10, the strongest simplicity property in the document, is contradicted twice by its own charters.

**W12 · Learning is fed by execution, not by outcome.**
*Gap against:* VEDA 04 M2, which requires provenance to include rejected recommendations and the stated reason.

L1 updates a skill's estimator and technique from what happened. Nothing invalidates that learning when the objective was halted, its output rejected, or its artifact discarded. There is no unlearning path.

*Consequence:* skills become confidently better at producing work that was thrown away, and the confidence is indistinguishable from the useful kind.

**W13 · Provider substitution is invisible to the Commitment graph.**
Hashes bind *upstream artifacts*. Nothing binds the *Provider* that produced a deliverable. If a voice-synthesis Provider fails mid-objective and the Broker substitutes another, Production re-runs and the artifact changes materially — different voice — while the brief hash remains current, nothing goes stale, and the poll passes.

*Consequence:* the staleness mechanism, which is VEDA 05's best idea, has a blind axis. Provider identity is part of an artifact's provenance and is not recorded as a dependency.

**W14 · "Hash-addressed" is unspecified.**
VEDA 05 never states what is hashed. If it hashes content, the mechanism works and corruption is detectable. If it hashes a pointer, an identifier, or metadata, staleness detection is theatre and a corrupted Commitment is undetectable. A ten-year document cannot leave this to the implementer; the two readings produce entirely different guarantees.

**W15 · The AI Capability Broker is the new hot path, and VEDA 05 claims bottleneck-freedom without naming it.**
§3.5 correctly removes the Objective Engine from the per-task path. It simultaneously places **every skill invocation, system-wide, on the Broker** — which is singular by constitutional requirement (§5.7) and must be atomic on cumulative spend accounting (VEDA 04 R3, rated high severity precisely here).

At 500 skills × 100 concurrent objectives × dozens of Providers, the Broker is consulted more often than any other component in the system and cannot be sharded without fragmenting the ledger the Constitution requires to be singular. **The bottleneck moved; it did not leave.** VEDA 05 §3.5 asserts the opposite.

**W16 · The Department Head is singular by design and a throughput point by consequence.**
Apple's inheritance — one taste authority per craft — requires the Head to be singular for consistency. §4.3 makes the same Head the sign-off authority for every objective touching its craft. At a hundred concurrent objectives, that is roughly 700 sign-off decisions across seven serialized authorities.

VEDA 05 states that Mission Leads are horizontally instantiable and does not address the Head. The tension between the Apple inheritance and the scale requirement is real and unresolved.

---

### Medium — simplicity findings

**W17 · Assurance is largely redundant with mechanisms that already fail closed.**
Its checks: receipt-before-action (A1 already aborts if the intent write fails), Capability classification (A2 already fails closed), staleness (§9.2 already fails closed), Expected Outcome present (already required by Constitution §3.2), Evidence attached (already B5's invariant).

Genuinely unique to Assurance: **sign-off came from a Head and not the producing Lead**, and **delivered scope matches contracted scope**. Two checks.

This is not an argument for deletion — an independent monitor that verifies fail-closed mechanisms actually failed closed is proportionate defense-in-depth on the Trust Spine. It is an argument that the charter overstates what Assurance independently contributes, and that a function described as doing seven things when two are its own will accrete the other five as real responsibilities over a decade.

**W18 · The Mission Lead's decisions are mechanical.**
Its authority is sequencing (already determined by the dependency graph) and retry-within-budget (a bounded policy). Its genuinely valuable property — being the accountable name on every receipt its work produced — is a *data* property, not a decision-making one.

The role may be a per-department contribution **record** rather than a reasoning agent. VEDA 05's laziness rule was the right instinct; the review question is whether the remaining 20% of cases need an agent or a struct. Worth resolving before implementation, because an agent that exists will find things to decide.

---

## Blind spots — not yet considered

**B1 · Partition turns fail-closed into fail-open.**
Multi-device synchronization is named as a requirement and appears nowhere in VEDA 05. Staleness fails closed only if the Commitment graph is globally consistent. Under partition, a device holding a stale view sees no supersession, marks nothing stale, and delivers an artifact it believes current. **The strongest safety property in the document degrades to its opposite under exactly the condition that most needs it.** Nothing specifies whether a staleness check requires a fresh read or may trust a local view.

**B2 · Partial objectives have no defined outcome.**
An objective halted at 80% has produced real artifacts, real spend, and real Commitments. The Constitution's Mission state machine offers `failed | cancelled`; neither describes this. VEDA 05 specifies how to halt and says nothing about what happens next: what is salvaged, what the founder is told, whether the spend is recorded against anything, whether the artifacts remain consumable by a future objective. This is trust-critical — the founder paid for something and the architecture is silent on what they get.

**B3 · Nothing runs the admission test.**
§2.1 is the document's most load-bearing artifact and it is written for a human to apply, with no cadence and no owner. R4 mentions in passing that the roster is reviewable at the annual dependency audit, but §2.1 does not make it a required audit output and C7 enumerates rules, not departments. **A test nobody is scheduled to run is a comment.** Over ten years this is the single most likely path to roster sprawl.

**B4 · The Commitment graph is a new durable store with no declared lifetime.**
VEDA 04 §5 requires every store to declare what it keeps, for how long, and how it forgets — forgetting as designed behaviour, not eviction. VEDA 05 introduces a permanent, monotonically growing, content-addressed store of every version of every artifact and brief, and declares nothing.

**B5 · The relayed admission grant is bounded by criteria, not by enumeration.**
Constitution §15.3's "never asked twice for the same thing" assumes the thing decomposes into known steps. In VEDA 05 the founder approves at admission, *before* decomposition and contracting exist. The grant therefore covers a step set that does not yet exist. Above-envelope and irreversible actions re-escalate, which bounds the damage — but nothing specifies how a grant's scope is defined when what it authorizes is unknown at the moment of granting.

**B6 · Department actions have no undo-window grading.**
VEDA 03 grades undo by who was in the room: batch sweep 60s, single approval 30s, **rule firing 24h — longest, precisely because the founder wasn't present** — irreversible none. E0 department actions happen with nobody in the room and are arguably the 24h case. VEDA 05 does not mention undo windows anywhere.

**B7 · Recurring inter-department disputes have no convergence path.**
Each A4 escalates independently. In principle L3 would notice the pattern, but VEDA 05 scopes L3 to *"which decisions the founder makes consistently enough to delegate"* — founder decision patterns. It is not stated that inter-department disputes are in scope. Without it, the same Creative/Production argument reaches the founder on every objective, which is the treadmill rebuilt one dispute class at a time.

**B8 · The narration burden grew and the explanation budget did not.**
VEDA 01 §4 requires every claim to be reachable to its evidence in one step. Claims still are — Evidence binds at generation. But a *decision* now has Engine → Head → Lead → Skill → Capability behind it, and VEDA 04 E1 requires provenance surfaced at the moment of relevance. Nothing specifies how a five-level decision chain collapses into one legible sentence in the fixed voice. Depth was added to the system; nothing was added to the thing that has to explain it.

---

## Future considerations — intentionally postponed

Correctly deferred. Listed so they are not mistaken for oversights, and so the conditions that end the deferral are on the record.

| Item | Why postponed | What ends the deferral |
|---|---|---|
| Peer Objective Engine federation | Constitution §8 standing instruction not to design a distributed system | A second principal or a second instance actually existing |
| Department capacity and WIP calibration | Requires production data; guessing numbers into a permanent document is worse than omitting them | First month of concurrent-objective telemetry |
| Fast path predicate boundary | Shape is fixed (single department, single skill, read-only, no commitment); the exact edge is not | Implementation of step 5 in the adoption sequence |
| Consequence-level reversibility (A2 extension) | Correctly raised in VEDA 05 R8 as an amendment request against a Layer A component | Founder ratification of the A2 extension |
| Objective / Mission terminology | Correctly raised in VEDA 05 R7 with a recommendation; §17 is frozen and cannot be resolved unilaterally | ADR plus ratification |
| Head instance multiplication (W16) | A resolution direction exists — separating standard-*setting* from standard-*applying* — but should not be designed before sign-off latency is measured | Observed sign-off queue depth |
| Legal and People department promotion | Triggers stated precisely, departments correctly not built | First legal-question blocker; first non-founder approval principal |

---

## The Human Trust Test

The founder-facing surface is unchanged by VEDA 05: two touches per objective, one voice, one decision at a time, receipts collapsed. **Felt complexity is flat**, which is the correct outcome for a change of this size and is a genuine achievement of the CAPCOM rule and the lazy Mission Lead.

Structural trustworthiness improves in four specific ways: irreversibility is undelegable at every tier, sign-off is separated from production, staleness is mechanical rather than remembered, and competence cannot convert itself into authority.

But trust in this product is not generated by structure. VEDA 01 and VEDA 03 are explicit about where it is actually generated, and they name four mechanisms. **VEDA 05 damages three of them:**

| Where trust is generated | Named in | VEDA 05's effect |
|---|---|---|
| The unprompted borderline-call disclosure — *"nothing else in this product does more for trust"* | VEDA 03, Screen 01 | **Damaged.** No mistake channel; CAPCOM routes it through ranking (W2) |
| *"Nothing needs you"* being provably complete | VEDA 01 §1, VEDA 04 D7 | **Damaged.** A fallible department inserted into the attestation path (W3) |
| The tree as the one measure the product cannot move | VEDA 01 §9 | **Damaged.** Department branches would let the AI grow it (W7) |
| The rule proposal from observed evidence — the emotional peak | VEDA 03 | **Intact and strengthened.** L3 proposes, cannot enact (S4) |

That is the finding that determines the verdict. VEDA 05 makes Kalpavriksha more trustworthy in its skeleton and less trustworthy at the three points where a founder actually decides whether to trust it. The damage is not intrinsic to the architecture — each case is a specific clause that reached past its own scope — but none of the three can ship as written.

Where trust and elegance conflict here, elegance won three times: the CAPCOM rule was too absolute, the Operations charter was too tidy, and the tree was borrowed to solve a problem it does not belong to.

---

## Final Verdict

**Requires Amendment** — the spine, the department model, and the trust properties of VEDA 05 are sound and should be preserved intact, but seven clauses conflict directly with frozen VEDA 01, 03, and 04 provisions (W1–W7), and three of them sit on the mechanisms that generate founder trust rather than merely describe it.
