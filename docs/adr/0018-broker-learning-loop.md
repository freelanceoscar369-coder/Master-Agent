# ADR-0018: The Broker Learning Loop — the policy learns, the decision procedure does not

Status: **Accepted (2026-07-29)** — founder directive issued at MB027
ratification

Extends ADR-0017. Design: `AI_CAPABILITY_BROKER_ARCHITECTURE.md` §19,
§11.1.

## Context

At ratification of MB027, the founder added one architectural objective:

> *"The Broker must become self-improving through long-term usage
> analytics, benchmark history, cost optimization, privacy awareness, and
> Founder-approved AI ecosystem evolution. This learning loop should
> become a first-class architectural objective for the AI Infrastructure
> Executive."*

This collides head-on with ADR-0017 Decision 4, which freezes the Broker
as deterministic and replayable — the property that makes MB027's Rule 15
("every provider decision must be auditable") a fact about the system
rather than an aspiration. A component that silently changes how it
decides is a component whose past decisions can no longer be explained,
and losing that would cost more than the learning gains.

The same directive also expands the AI Infrastructure Executive's scope to
include **installation**, which MB027 had explicitly excluded from its
frozen contract.

Both are founder decisions. This ADR records how they are absorbed
without giving up what ADR-0017 was built to protect.

## Decision 1 — The policy learns; the decision procedure does not

> The Decision Engine stays deterministic, replayable, and free of model
> calls. What evolves is the **versioned policy** it reads.

Every decision already carries `policy_version` and an `inputs_digest`
(ADR-0017 Decision 4). A decision made under policy v7 replays against
policy v7 forever. Learning produces policy v8 as a discrete, reviewable,
reversible artifact.

### Options considered

1. **The Broker self-tunes its own weights continuously.** Rejected. It
   destroys replay: the same request produces different answers at
   different times with nothing in the record explaining the difference,
   which makes the audit trail decorative. It also makes the kernel
   service that every mission depends on the component least able to be
   reasoned about.
2. **An AI decides the policy.** Rejected, for the reason ADR-0017 already
   gave for not letting an AI make selections: something has to break the
   recursion, and starting it buys nothing here — the inputs are counts,
   rates, and costs, and the analysis over them is arithmetic plus
   judgement, with the judgement reserved for the founder anyway.
3. **Versioned policy, evolved by proposal and promotion.** Chosen.
   Learning becomes a sequence of named artifacts a human can read,
   accept, reject, and revert — and every past decision stays explainable
   against the exact policy that produced it.

## Decision 2 — Analysis belongs to the AI Infrastructure Executive, not the Broker

Three distinct owners:

| Stage | Owner |
|---|---|
| Data (decisions, outcomes, costs, benchmark aggregates) | The Broker |
| Analysis (data → proposals) | The AI Infrastructure Executive |
| Promotion (proposal → policy) | The Founder, via Promotion Review |

The founder's directive places analysis with the Executive, and the
architecture independently arrives at the same place for two reasons worth
recording:

- **Analysis is work, and work happens in an Executive.** Letting the
  Broker analyse itself would give a kernel service a periodic, expensive
  workload and make the component that must be replayable the one
  rewriting its own rules. As an Executive capability
  (`AiInfrastructure.AnalyseUsage`), it is an ordinary mission dispatched
  by the Runtime — bounded, observable, interruptible, and free to be
  expensive.
- **Only this Executive can check a proposal for feasibility.** It is the
  component that observes the machine — what is installed, what the
  hardware can do, what a Provider actually returns when probed. Usage
  analytics without that context produces proposals that are right about
  the data and wrong about the machine ("switch to the 70B local model" on
  a host that cannot load it). Holding both the measurements and the
  machine is what lets a proposal be filtered before a founder ever sees
  it.

## Decision 3 — The loop is the Knowledge Lifecycle, not new machinery

```
BrokerDecision → OutcomeReport (Verification-backed)
   → BenchmarkSample + CostLedgerEntry      [Evidence]
   → UsageAnalytics + PolicyProposal        [Knowledge Candidate]
   → Founder Promotion Review               [ADR-0012, human-gated]
   → policy vN+1                            [Permanent Knowledge]
   → every subsequent decision              [Future Reasoning]
```

ADR-0012 already defines this lifecycle, and MB023 already ships the
**Knowledge Acquisition Queue** with the gate enforced *in code* —
advancing past verification requires `human_approved=True`, and the
refusal is published as an auditable event. A policy proposal is a
Knowledge Candidate and rides that machinery unchanged. Ecosystem
proposals ride the **Self-Development Queue** the same way.

Two existing queues, two existing gates, **zero new approval paths**. The
alternative — a bespoke proposal-approval mechanism inside the Broker —
was rejected for the same reason ADR-0017 rejected a bespoke payment
approval: a second human-gating mechanism is a second thing that can be
wrong about what the founder already said.

## Decision 4 — Privacy is a one-way ratchet

> The loop may propose **tightening** a privacy constraint. It may
> **never** propose loosening one.

Loosening is a founder-initiated act, never a system-initiated proposal.

This is asymmetric on purpose. Every other guard in §19.4 is a threshold —
a number that can be argued about. This one is a direction, because the
loop's optimisation pressure runs exactly the wrong way: sending sensitive
work to a cloud Provider will *usually* look better on success rate,
latency, and often cost. A loop free to propose it would propose it
correctly and repeatedly, and each proposal would arrive with real
evidence attached, which is precisely what makes it dangerous. A founder
approving the fifteenth well-evidenced privacy relaxation is not making
the same decision they made the first time.

## Decision 5 — Every promoted change carries a rollback condition

A `PolicyProposal` without a `rollback_condition` is refused at
generation, alongside the existing refusal for a proposal without
`evidence`. Each promoted change has a review window; if the observed
verified success rate for the affected capabilities degrades past the
threshold during it, the policy reverts to the prior version and the
reversion is published as an event.

This costs almost nothing to build — `policy_version` is already
first-class, so reverting is selecting a previous version — and it is what
stops the loop being the sole judge of its own changes.

**The limit, stated rather than implied:** rollback reverts *policy*,
never *effects*. An install, a removal, or a month of spend made under a
policy cannot be undone by reverting it. That is why ecosystem mutation is
separately gated at `IRREVERSIBLE` (Decision 6) instead of relying on this
guarantee.

## Decision 6 — Installation joins the Executive's contract, at IRREVERSIBLE

MB027 froze the AI Infrastructure Executive with **no install, download,
or removal capability**, deferring ecosystem mutation to a separate future
Executive. The founder's ratification assigns discovery, installation,
benchmarking, and inventory to this Executive. That is a real expansion of
the frozen contract, recorded here rather than absorbed silently, with
four conditions:

1. **`InstallProvider` / `RemoveProvider` / `UpgradeProvider` are
   `IRREVERSIBLE`.** Per ADR-0009, an `ALWAYS_FOR_CAPABILITY` grant can
   never satisfy an `IRREVERSIBLE` check — so no standing approval can
   ever authorise one. Every install, removal, and upgrade is a fresh
   founder decision, guaranteed mechanically by already-shipped code.
2. **MB027's "no automatic downloads" rule survives, and becomes
   structural rather than declared.** Nothing in the system can *trigger*
   these capabilities: the Broker executes nothing, and recommendations
   are inert data (ADR-0016's discipline, ADR-0017 Decision 6). The only
   path runs through a founder accepting a recommendation into the
   Self-Development Queue. The capability exists; nothing but a founder
   starts it.
3. **Removal requires an impact statement** naming every AI Capability
   that would become unserved or drop a tier. "Reclaim 40 GB" without "and
   lose your only offline OCR" is not a decision a founder can make.
4. **Every mutation re-runs discovery**, so the inventory can never
   silently disagree with the machine — the state the availability filter
   depends on.

## Decision 7 — Exploration is budgeted, because otherwise the loop cannot learn

A Provider ranked low is never selected, so it generates no samples, so it
stays low permanently — including after an upgrade that fixed it. Pure
exploitation converges on whatever was tried first and calls it optimal.

So a configured fraction of **low-stakes** requests deliberately go to a
viable non-winner, and the resulting samples are what allow a Provider to
climb back. Active benchmarking (ADR-0017, §10.2) covers the same gap
deliberately; exploration covers it continuously and for free.

Bounded to low-stakes requests on purpose: an exploration budget spent on
critical work is not learning, it is gambling with the mission.

## Consequences

- **The Broker gains a feedback loop without losing replay.** Every
  decision remains explainable against the policy that produced it, and
  the policy's own history becomes a reviewable artifact — arguably a
  stronger audit position than before, since "why does it decide this way
  now?" now has a document rather than an answer buried in a diff.
- **The AI Infrastructure Executive becomes the most privileged Executive
  in the system.** It reads every ledger, observes the machine, and can
  mutate the ecosystem. Mitigated by tier (`IRREVERSIBLE` for every
  mutation), by structure (it proposes; it cannot apply), and by the fact
  that it holds no ranking logic of its own — but it is worth naming that
  this is now the Executive whose compromise would matter most.
- **The single failure mode that would invalidate the design:** this
  Executive growing a ranking function. It emits `PolicyProposal`s and has
  no path to apply one, the same way the Broker has no path to execute.
  When it is implemented, that boundary should be enforced by the same
  import-parsing test pattern MB023/MB024/MB025 use, not by intention.
- **Every number in the loop is a first guess.** Exploration fraction,
  minimum sample counts, review windows, rollback thresholds, floor
  minimums — all configuration, none calibrated, and none knowable before
  real usage. The shape is frozen; the values should be expected to move.
