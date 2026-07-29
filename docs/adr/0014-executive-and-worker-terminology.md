# ADR-0014: "Executive" and "Worker" name the same role; Worker stays canonical

Status: Accepted (2026-07-26) — Mission Brief 023 (Mission Control &
Self-Development Infrastructure)

## Context

Mission Brief 023 introduces the term **Executive** throughout: "Executive
Registry", "Executive ID", "Every Executive reports into Mission Control",
and an out-of-scope list naming a "Desktop Executive", "Filesystem
Executive", "Git Executive", "Research Executive", and "Knowledge
Executive".

The Founder Constitution's §17 Terminology Freeze already defines
**Worker** for exactly that role — "a single registered unit of execution
capability inside an Operator's Worker Runtime" — and Mission Brief 022
shipped `BrowserWorker` and `BROWSER_WORKER_ARCHITECTURE.md` under that
name.

So the same architectural role now has two names in the project's active
vocabulary. That is precisely the drift §17 exists to prevent: its own
rule is "use exactly one meaning for each" term, and the Constitution
Freeze (`docs/architecture/FOUNDER_CONSTITUTION_FREEZE.md`) records
terminology as FROZEN. Leaving both names live, undefined against each
other, would mean a future Mission Brief author cannot tell whether an
"Executive" is a Worker, a Worker Instance, an Operator Instance, or a
new fourth thing.

The Constitution also states how this must be handled: amendments require
a Mission Brief that updates both the Constitution and the freeze record
together, never one without the other.

## Options considered

1. **Rename Mission Brief 023's deliverables to "Worker Registry",
   "Worker ID", etc., and treat "Executive" as a slip.** Rejected. The
   founder's brief is the specification, and its vocabulary is a
   deliberate framing — "Executive" carries the sense of an accountable
   actor reporting into a command layer, which is exactly what Mission
   Control's registry models. Silently renaming a founder's deliverables
   because a prior document chose a different word is the wrong default,
   and the brief's naming is not ambiguous or wrong, merely different.
2. **Adopt "Executive" everywhere and retire "Worker", updating the
   Constitution, `BROWSER_WORKER_ARCHITECTURE.md`, `BrowserWorker`,
   `browser_worker.py`, and every test that names it.** Rejected. That is
   a wide, purely-cosmetic rename across shipped, tagged, working code
   (Mission Brief 022, `v0.6.0-miracle-022`) with zero functional benefit,
   and it violates Constitution Rule 2 ("No Rewrites Without Approval") —
   refactoring shipped architecture because of a naming preference is
   exactly what that rule forbids.
3. **Declare the two terms synonymous, with one canonical, and record it
   in the frozen terminology table.** Chosen — see Decision.

## Decision

**Executive and Worker name the same architectural role.** Concretely:

- **`Worker` remains canonical** in the Constitution and in Worker-side
  code. `BrowserWorker`, `BROWSER_WORKER_ARCHITECTURE.md`, and every
  Mission Brief 022 artifact are unchanged. Nothing shipped is renamed.
- **`Executive` is the term Mission Control's registration API uses** —
  `ExecutiveRegistry`, `ExecutiveRecord`, `register_executive()`,
  `executive_id` — because that is the vocabulary Mission Brief 023
  specified for these deliverables.
- **An Executive registered with Mission Control is a Worker** viewed from
  the coordination layer: the same population, described for a different
  purpose (who exists and is healthy, rather than how work gets invoked).
- Constitution §17 gains one line recording the alias, and
  `FOUNDER_CONSTITUTION_FREEZE.md` is amended in the same commit, as the
  Constitution requires of any amendment.

The rule for future Mission Briefs: **do not introduce a third name.** If
a document needs to talk about this role, it uses Worker (in
architecture/Constitution context) or Executive (in Mission Control
registration context), and never invents a synonym for either.

## Consequences

- The frozen terminology table stays honest: a reader who encounters
  "Executive" in Mission Control code and "Worker" in the Constitution can
  resolve the relationship in one lookup, instead of guessing.
- Zero code churn in Mission Brief 022's shipped, tagged Worker.
- A mild, accepted cost: `master_agent.mission_control.executives` and
  `master_agent.plugins.browser_worker` use different words for the same
  concept in the same codebase. That is the price of honoring both the
  founder's brief and Rule 2, and it is documented here rather than
  quietly tolerated. If it ever becomes a genuine source of confusion in
  practice (rather than in theory), unifying is a deliberate, separately
  scoped Mission Brief — with the Constitution amended alongside it, the
  same way this ADR does.
- `mission_control/lifecycle.py` names its state enum `WorkerState`, not
  `ExecutiveState`, deliberately: it implements Mission Brief 023's
  deliverable literally titled "Worker Lifecycle" — the brief itself uses
  "Worker" for that one deliverable, which is a small piece of evidence
  that the two terms were already being used interchangeably in the
  founder's own framing.
