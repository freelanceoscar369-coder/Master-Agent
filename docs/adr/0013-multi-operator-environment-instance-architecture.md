# ADR-0013: Operator Instances and Environment Instances — scaling posture without designing a distributed system

Status: Accepted (2026-07-26) — Mission Brief 021 Revision 3 (Founder Constitution Freeze)

## Context

`KALPAVRIKSHA_VISION_V2.md` v2 described "the Operator" as a singular,
implicit thing, and its Worker Architecture section stated outright:
"there is no 'worker pool' or 'agent swarm' in the core — the Orchestrator
invokes plugins sequentially." That is an accurate description of today's
single-process CLI, but the independent audit flagged it as a direct
mismatch against the scaling scenarios Founder Edition is meant to grow
into: multiple desktops, multiple browser sessions, multiple VPS
instances, and eventually robots, all potentially active at once. Nothing
in v2 defined an identity for "one Operator" as opposed to another, and
"Environment" (§6 in v2) meant "which host process the engine happens to
run inside" — a much narrower concept than "how many external targets the
Operator can act on right now."

This Mission Brief is explicit that a distributed system must not be
designed here — only that the architecture must not *block* this scaling
axis. The task is definitional, not mechanical.

## Options considered

1. **Leave "the Operator" singular and treat multi-environment support as
   a future rewrite.** Rejected — this is exactly the gap the audit named;
   deferring the definition doesn't make the eventual work smaller, and
   the Constitution's own purpose is to keep future Mission Briefs from
   having to invent foundational vocabulary mid-implementation.
2. **Design a full distributed coordination protocol now** (operator
   discovery, health-checking, cross-machine consensus). Rejected —
   explicitly out of scope per this Mission Brief's instruction ("do not
   design distributed systems, only define the architecture so it
   naturally scales"), and would be premature complexity of exactly the
   kind `ENGINEERING_PRINCIPLES.md` #10 warns against building ahead of a
   concrete need.
3. **Define Operator Instance and Environment Instance as first-class,
   named concepts, and show that the existing Capability-resolution
   philosophy already generalizes to them without inventing a new
   mechanism** — leaving concurrency and cross-machine coordination
   explicitly unresolved and marked EVOLVABLE. Chosen.

## Decision

`KALPAVRIKSHA_VISION_V2.md` §8 defines:

- **Operator Instance** — one running instance of the Universal Executive
  Operator, bound to one (or a small, tightly-coupled set of) Environment
  Instance(s). Tracked by an Operator Registry, itself part of Shared
  Infrastructure's Capability Registry (ADR-0010) — an Operator Instance
  advertises which Capabilities it can currently service, the same way a
  Worker does.
- **Environment Instance** — one concrete, addressable target (this
  specific desktop, this specific browser tab, this specific VPS),
  distinct from "Environment" as an abstract category.
- **Environment Session** — the live handle one Operator Instance holds to
  one Environment Instance. Deliberately **not** Shared Infrastructure
  (ADR-0010's §5.7) — sharing a live connection across Operator Instances
  would violate the isolation that makes Permission grants and safety
  boundaries meaningful per Environment.

A `Step` may name, alongside its Capability, a required Environment
category. Shared Infrastructure's Capability Registry resolves which live
Operator Instance can service that Step at execution time — the same
resolution philosophy already established for Capability → Worker
(unchanged from v2), extended one level, not reinvented. Because
Permission System, Mission State, and Memory are already Shared
Infrastructure (ADR-0010), a Mission spanning multiple Operator Instances
still has exactly one grant ledger, one state machine, and one Memory
record — this decision is only safe *because* ADR-0010 already moved those
three components out of the Operator's exclusive ownership.

Concurrency is explicitly scoped out: a `MissionPlan`'s DAG already
permits independent, parallel branches in principle (nothing about "DAG of
Steps" requires strict serial execution), so nothing about adding Operator
Instances requires changing the `Step`/Capability/Worker contract. Whether
a future Orchestrator actually dispatches DAG branches to different
Operator Instances concurrently, and what failure-isolation that would
require, is marked EVOLVABLE and left for a future, dedicated Mission
Brief when a concrete need exists.

## Consequences

- Today's implementation is unaffected: it remains single-Operator-Instance
  and sequential, exactly as `ARCHITECTURE.md` describes. This ADR adds
  vocabulary and a resolution pattern for the future; it does not require
  building an Operator Registry, multiple Operator Instances, or
  concurrent dispatch now.
- Future non-filesystem Workers (shell, git, browser, VPS) can be designed
  against "which Environment Instance does this need" from day one,
  instead of retrofitting that concept once a second Environment category
  actually exists.
- This ADR does not resolve session/handle support inside the Action
  contract itself (a stateful Environment Session spanning multiple
  Steps, as Browser/Terminal/Robotics capabilities will eventually need) —
  named as a related but distinct open item, still EVOLVABLE, not solved
  here since nothing in this Mission Brief's scope required solving it
  and no current `ROADMAP.md` item depends on it yet.
- No code changes result from this ADR.
