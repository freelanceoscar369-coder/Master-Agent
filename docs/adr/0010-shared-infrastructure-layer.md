# ADR-0010: Shared Infrastructure as a third layer between Brain and Operator

Status: Accepted (2026-07-26) — Mission Brief 021 Revision 3 (Founder Constitution Freeze)

## Context

`KALPAVRIKSHA_VISION_V2.md` v2 modeled the system as two columns — Executive
Brain and Universal Executive Operator — and claimed "the boundary is
absolute": the Brain decides, the Operator executes, and neither depends on
the other's internals. An independent architecture audit checked that claim
against the actual source and found it false in at least two places:
`plugins/model_router.py` (a Brain component, per the Constitution's own
§3.3) constructs directly against `PluginRegistry` (assigned exclusively to
the Operator's column, per §4), and `plugins/registry.py`'s own docstring
states the registry is "the only thing the Orchestrator **and** Model
Router talk to." Memory has the same shape: the Planner (Brain) reads it,
but nothing in either column was the actual writer in the live code path —
that was `MasterAgentSession`, a class neither column named at all.

A two-column model cannot represent a component two different callers both
genuinely depend on without one of two failure modes: duplicate it (Brain
gets its own registry, Operator gets its own — now they can silently
diverge on what capabilities exist), or misassign it to one column (which
is what v2 did, producing the audit's core finding).

## Options considered

1. **Keep two columns; assign Plugin Registry and Memory to whichever side
   uses them "more."** Rejected — both sides depend on both components for
   correctness, not convenience. Assigning either to one side doesn't
   remove the other side's real dependency, it just hides it from the
   diagram, which is the exact problem being fixed.
2. **Duplicate the shared components — one copy per side.** Rejected —
   this reintroduces the "two versions of X that can drift" problem
   `ENGINEERING_PRINCIPLES.md` #7 already names as a standing hazard
   elsewhere in this codebase (`is_unsafe_relative_path()`'s single shared
   implementation is the positive example this project already learned
   from). Two Plugin Registries can disagree about what a Worker exposes;
   two Permission ledgers can disagree about what's been approved. Both are
   safety-relevant, not just inconvenient.
3. **Introduce a third, foundational layer — Shared Infrastructure — that
   both Brain and Operator depend downward on, and neither owns.** Chosen.

## Decision

`KALPAVRIKSHA_VISION_V2.md` §5 defines Shared Infrastructure as the layer
beneath both Brain and Operator, containing: the Capability Registry
(formerly "Plugin Registry"), the Permission System (elevated from
Operator-only), Mission State (the correct home for `MissionManager`/
`Mission`, previously unplaced by either column), Memory, Configuration,
and the durable/aggregated form of Telemetry and Evidence. Each component's
inclusion is justified individually in §5.1–§5.6, not by a blanket "shared
stuff goes here" rule — the Constitution's own instruction was "do not
simply move components, explain why each belongs there," and each
subsection does.

Explicitly **not** moved to Shared Infrastructure: Environment Session
Management (a live handle to one Environment Instance belongs to the
Operator Instance that opened it — sharing it centrally would let one
Operator Instance reach into another's live connection) and Mission
Session (`MasterAgentSession`'s conceptual role — Brain-adjacent glue on a
path to dissolving into the Brain proper once the real Planner exists, not
infrastructure multiple Operator Instances depend on).

The diagram (Brain → Shared Infrastructure → Operator) describes
*dependency direction*, consistent with `ARCHITECTURE_PRINCIPLES.md`'s
existing "dependencies point inward" rule, not sequential data flow —
multiple Brain-side components and multiple Operator Instances (ADR-0013)
may read and write Shared Infrastructure concurrently.

## Consequences

- The Brain/Operator boundary claim is now accurate: neither depends on the
  other's internals; both are required to depend on Shared Infrastructure's
  public contracts. This is a narrower, more honest claim than "absolute,"
  and it is checkable against source the way the prior claim wasn't.
- Permission System's move is the one with real teeth: it means a Mission
  spanning multiple Operator Instances (ADR-0013) has exactly one grant
  ledger, so "one approval per mission" is a Mission-wide guarantee, not an
  accidental per-Operator-Instance one. This was not true, even in
  principle, under the v2 model.
- `MissionManager`/`Mission` now has an unambiguous home (Shared
  Infrastructure), closing the ownership gap the audit found. This is a
  Constitution-level clarification only — `MissionManager` remains
  unwired in the live code path (`cli.py`'s `MasterAgentSession` still
  does this work directly), which is unchanged by this ADR and remains
  `ROADMAP.md` item 1's job to fix.
- No code changes result from this ADR. It is a naming and boundary
  clarification for future Mission Briefs to build against, not a
  refactor of `plugins/registry.py`, `plugins/model_router.py`, or
  `memory/memory.py` — those files are already structured consistently
  with this decision; only the Constitution's description of them was
  wrong.
