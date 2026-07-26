# ADR-0011: Verification as a structurally independent subsystem, not a Step invoked through the Capability path

Status: Accepted (2026-07-26) — Mission Brief 021 Revision 3 (Founder Constitution Freeze)

## Context

`KALPAVRIKSHA_VISION_V2.md` v2's §8.1 claimed "Verification Is a Distinct
Step... not merged into execution," but its only described mechanism
(§8.3) was: a Verifier, once built, would be "invoked as a final Step in
every plan" — resolved through the same Capability → Worker →
`invoke()` path as any execution capability. The independent audit found
this made Verification *nominally* distinct (there is a real `verifying`
Mission state) but not *structurally* distinct: its invocation mechanism
was identical to Execution's, with no distinguishing contract, no
postcondition schema, and no defined path for the information a Verifier
would need (the Intent's success criteria, owned by the Brain) to reach a
component that, by design, only understands "capability" (the Operator).

This matters because the whole reason Verification exists as a phase in
the Kalpavriksha Loop (`Intent → Plan → Delegate → Execute → Verify →
Learn → Report`) is that "the Action ran without raising an exception" and
"the real world now matches what was actually wanted" are different
claims. Folding Verification into the same mechanism as Execution risks
collapsing exactly that distinction back down to one claim, silently.

## Options considered

1. **Leave Verification as a Step resolved through the Capability path,**
   just build the Verifier plugin when the time comes. Rejected — this is
   what v2 already described, and it's what the audit flagged: the
   mechanism doesn't actually distinguish "did it run" from "did it work,"
   which is the one distinction Verification exists to make.
2. **Make Verification part of every Action's own `run()` return value**
   (e.g., an Action checks its own postcondition before returning).
   Rejected — this makes verification only as independent as the Action
   author chooses to make it, with no structural guarantee, and it
   conflates "the thing that produced the effect" with "the thing that
   checks the effect," which is precisely the coupling a first-class
   Verification subsystem is supposed to prevent (an Action that has a bug
   in its effect is not a trustworthy judge of whether its own effect is
   correct).
3. **A distinct Verification Subsystem, physically able to reach an
   Environment Instance (so it must run Operator-side) but invoked through
   its own contract — never a Worker's `invoke()` — comparing a fresh
   Observation against an Expected Outcome the Planner attaches to each
   `Step`, and returning Evidence to the Brain.** Chosen.

## Decision

`KALPAVRIKSHA_VISION_V2.md` §10 defines a three-part boundary:

- **Execution produces effects.** A Worker's Action runs and returns an
  Execution Result — did it run without error, what did it output. This
  is not evidence of real-world correctness, only of successful attempt.
- **Verification produces Evidence.** A distinct Verification Subsystem
  re-observes the relevant Environment Instance (an **Observation**) and
  compares it against the **Expected Outcome** the Planner attached to the
  `Step` when the Brain produced the `MissionPlan` (§3.2 — a new
  Brain-side responsibility this ADR requires, closing the "how does
  success-criteria information reach the Operator" gap the audit found).
  The result is a **Verdict**; Verdict + Observation + Expected Outcome
  together are **Evidence**.
- **Evidence flows back to the Brain.** Not merely filed into Memory for
  audit — routed to the Brain as the input to "is this Mission actually
  complete."

Verification stays physically adjacent to the Operator (only the Operator
has Environment access — the Brain has none, by design), but is invoked
through its own contract, never a Worker's `validate()`/`run()` path. Same
location, different mechanism — that is the bar "structurally independent"
must clear, and it's a stricter bar than v2's Verifier-as-a-Step design met.

The Knowledge Lifecycle (ADR-0012) introduces a second, later gate —
Promotion Review — that also compares evidence against a bar before
allowing something to proceed. That gate is deliberately **not** named
"Verification": the term is reserved for this ADR's Mission-level,
real-world-state meaning only, per the Constitution's terminology freeze
(`KALPAVRIKSHA_VISION_V2.md` §17).

## Consequences

- Every future `Step` a Planner produces must carry an Expected Outcome,
  not just a human-readable description. This is a new, real requirement
  on the (still-unbuilt) real Planner — named here so it isn't
  rediscovered as a gap once Planner implementation begins.
- The Verifier itself remains unbuilt (unchanged status from v2) — this
  ADR fixes its *architecture*, not its implementation. `cli.py`'s
  completion messages remain the manual verification surface until a real
  Verification Subsystem exists.
- Recovery (`KALPAVRIKSHA_VISION_V2.md` §11.1) now has an explicit trigger
  it didn't have before: a failed Verdict is Evidence like any other, and
  reaches the Brain the same way a successful one does — what differs is
  what the Brain does with it (retry, re-plan, or surface to a human).
  The precise decision rule for that is still open (§11.4) and is not
  resolved by this ADR.
- No code changes result from this ADR — `Verifier` remains a planned
  module. This is a design constraint for whoever builds it next, the
  same relationship ADR-0006 had to `WorkspaceBootstrapAction` before it
  was written.
