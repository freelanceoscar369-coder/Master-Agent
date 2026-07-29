# Mission Brief 021, Revision 3 — Founder Constitution Freeze

Status: Shipped (design-only) — 2026-07-26

## Objective

Perform the final Founder Constitution Freeze before implementation
resumes: resolve every gap the independent architecture audit found in
`KALPAVRIKSHA_VISION_V2.md` (Revision 2), consolidate duplicated rules,
freeze architectural terminology, and issue a Final Founder Review
declaring whether Founder Edition can now be implemented without further
Constitution changes.

**Scope constraint, honored throughout:** design-only. No file under
`src/` or `tests/` was read for the purpose of changing it, no code was
written, no package was created, no test was added or modified. Every
change in this Mission Brief is to a Markdown document.

## Input documents consulted

`KALPAVRIKSHA_VISION_V2.md` (Revision 2, primary constitution), `ARCHITECTURE.md`,
`ROADMAP.md`, `PROJECT_BRAIN.md`, `DECISIONS.md`, `MIRACLE_LEDGER.md`,
`docs/adr/0001`–`0009`, `docs/MISSION_BRIEF_001.md`–`005.md`, and the
independent architecture audit produced in this session immediately prior
to this Mission Brief. **MB006–MB020 were checked and confirmed absent**
from this repository, its git history, and every known backup — treated
as non-existent rather than assumed, consistent with how the original
Mission Brief 021 (paused, not completed) was handled.

## What changed, item by item

1. **Shared Infrastructure layer introduced** (`KALPAVRIKSHA_VISION_V2.md`
   §5, ADR-0010). Capability Registry, Permission System, Mission State,
   Memory, Configuration, and aggregated Telemetry/Evidence moved to a
   third layer both Brain and Operator depend on, each with an individual
   justification rather than a blanket move. Environment Session
   Management and Mission Session were evaluated and deliberately kept out
   (§5.7, renumbered §5.8 by Amendment 2, MB027) — not moving is as much
   a design decision as moving.
2. **Verification made structurally independent** (§10, ADR-0011). Defined
   the Execution / Verification / Evidence-to-Brain boundary: Execution
   produces effects, a distinct Verification Subsystem produces Evidence
   by comparing a fresh Observation against an Expected Outcome the
   Planner now must attach to every `Step`, and Evidence — not just a
   status flag — flows back to the Brain.
3. **Knowledge Lifecycle formalized** (§9.3–9.5, ADR-0012). `Execution →
   Evidence → Knowledge Candidate → Promotion Review → Permanent Knowledge
   → Future Reasoning`, with the founder-proposed lifecycle's fourth stage
   renamed from "Verification" to **Promotion Review** to avoid colliding
   with item 2's reserved meaning. Brain nominates Candidates; a
   human-gated Promotion Review approves or rejects; Permanent Knowledge
   is itself revocable if later Evidence contradicts it.
4. **Product-specific terminology scrubbed** (§14, §21). "Hermes,"
   "ChatGPT," "Ollama," "VS Code," and "Obsidian" removed from every
   architecture-defining section and replaced with role-based terms
   (Local/Cloud Reasoning Provider, Desktop/Browser Environment). A single
   "Illustrative Implementations" appendix (§21) holds non-binding
   examples, explicitly marked as not architecture.
5. **Multi-Operator architecture defined** (§8, ADR-0013). Operator
   Instance, Environment Instance, Environment Session, and an Operator
   Registry (folded into the Capability Registry) introduced. Concurrency
   across Operator Instances explicitly scoped out per this brief's
   instruction not to design a distributed system, marked EVOLVABLE.
6. **Ownership clarified, exactly once each** (§16). `MasterAgentSession`
   (Brain-adjacent, transitional), `MissionManager` (Shared
   Infrastructure), `Reporter` (Brain, newly added to §3 as §3.4 — it did
   not exist in Revision 2's Brain component list at all), `Orchestrator`
   (Operator, unchanged), `ModelRouter` (Brain, depends on Shared
   Infrastructure), `CapabilityIndex` (Shared Infrastructure, same
   component as the Capability Registry), `Memory` (Shared Infrastructure),
   Worker Runtime and Plugin Runtime (Operator, same mechanism, one name).
7. **Duplication reduced.** Former Rule 1 and Rule 9 (both gating on "the
   Scalability Question") merged into one Rule 1. Former Rule 5 and Rule
   14 (both stating "one approval per mission") merged, with §15.3 as the
   single canonical prose statement. The composite-relay rule, previously
   stated near-verbatim in three places (§4.5, §10.3, Rule 6 of Revision
   2), now appears once, in Rule 6, with every other reference pointing to
   it rather than restating it.
8. **Terminology frozen** (§17). Sixteen terms given exactly one meaning
   each, including resolving a real collision the founder's own brief
   introduced: "Task" and "Step" were both in use for the same concept:
   "Task" is retired as a deprecated alias for `Step` rather than forcing
   a false distinction between them.
9. **Future-proofing reviewed** (`FOUNDER_CONSTITUTION_FREEZE.md` §2, Item
   9 table). New Reasoning Providers, new Environments, new interfaces,
   and unknown future technologies are already covered by the extension
   model; stateful multi-Step Environment Sessions (needed for Browser/
   Terminal/Robotics) and concurrent multi-Operator dispatch are named,
   scoped-open items, not silently assumed solved.
10. **Section status labels applied** (§18, plus every section heading in
    `KALPAVRIKSHA_VISION_V2.md`). FROZEN / RESEARCH-BACKED / EVOLVABLE /
    IMPLEMENTATION DETAIL assigned per section, with an explicit legend
    stating what each label permits.

## Files touched

- Updated: `docs/architecture/KALPAVRIKSHA_VISION_V2.md` (full revision)
- Created: `docs/architecture/FOUNDER_CONSTITUTION_FREEZE.md`
- Created: `docs/adr/0010-shared-infrastructure-layer.md`
- Created: `docs/adr/0011-verification-as-independent-subsystem.md`
- Created: `docs/adr/0012-knowledge-lifecycle.md`
- Created: `docs/adr/0013-multi-operator-environment-instance-architecture.md`
- Created: `docs/MISSION_BRIEF_021_REVISION_3.md` (this document)
- Updated: `ROADMAP.md`, `PROJECT_BRAIN.md`, `DECISIONS.md`, `ARCHITECTURE.md`
  (cross-references and status notes only — see each file's own diff;
  none of their existing implementation-record content was rewritten)

## Technical debt / remaining stubs

Unchanged from before this Mission Brief — this brief touched no code, so
it introduces no new code-level debt. Three architectural items are named
as deliberately open (not blockers) in `FOUNDER_CONSTITUTION_FREEZE.md`
§3: the in-mission recovery decision procedure, stateful Environment
Sessions in the Worker/Action contract, and concurrent dispatch across
Operator Instances. Each is scoped to a *future* capability that isn't yet
on `ROADMAP.md`, not to the next Mission Brief.

## Live verification

Not applicable in the usual sense — this is a design-only Mission Brief
with no running system to exercise. "Verification" here means: every
factual claim about the existing codebase made in `KALPAVRIKSHA_VISION_V2.md`
and its ADRs was checked directly against source (`plugins/registry.py`,
`plugins/model_router.py`, `permissions/permission_system.py`,
`plugins/base.py`, `cli.py`) during the preceding audit, not asserted from
memory of the prior document.

## Final Founder Review

See `FOUNDER_CONSTITUTION_FREEZE.md` §5 for the full reasoning.
**Declaration: the Constitution is frozen.** Founder Edition's current
`ROADMAP.md` (the real Planner, item 1, and the four items after it) can
be implemented without further Constitution changes.

## Recommendation for the next Mission Brief

Resume implementation. The next Mission Brief should be `ROADMAP.md` item
1 — the real Planner, replacing `cli.py`'s regex-based `parse_intent()`/
`build_plan()` with a live Model Router call — and should be an
implementation brief (code, tests, live verification against the real
stack), not another design brief.
