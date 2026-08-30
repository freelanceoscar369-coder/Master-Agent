# ADR-0027: Brain Deliberative Intelligence and Decision Utility

**Status:** Accepted — Founder-ratified 2026-08-28

This does not amend the Constitution. It refines Constitution §3 in the
same way ADR-0026 did, and it does not disturb ADR-0011 (independent
Verification), ADR-0017 (Broker sole provider authority), ADR-0024
(intent resolution and Planner admission) or ADR-0026 (semantic
correspondence).

---

## The problem

Founder acceptance failed on a live web research objective:

> search for action rpg games released in 2026 and give me free demo
> download links

The founder was told **"That didn't complete."** The audit is in
`docs/audits/DEMO_30AUG_EVIDENCE.md`. Three things were wrong, and only
the first is a bug:

1. `Browser.OpenBrowserSession` failed on thread affinity, 1.3 seconds
   in. The mission never reached the web.
2. **One step failed and the objective failed.** No recovery, no
   re-plan, no alternative source. A *method* failure was reported as an
   *objective* failure.
3. The plan carried **no requirements** and every step `covers=[]`. The
   semantic guarantees of ADR-0026 reach the deterministic lanes, not
   AI-planned research. Even with a working browser, this mission could
   only ever have reported UNKNOWN.

Fixing (1) alone would have made the mission run and would not have made
the answer good. The founder's decision is that Kalpavriksha must be
**brain-heavy**: strong Workers with a weak Brain produce fast mistakes.

## The invariant

> **Every material Brain decision must be useful for satisfying Founder
> intent, or for determining truthfully that it cannot yet be
> satisfied.**

## Decision

Add **Brain Deliberative Intelligence** as an internal faculty of the
existing Executive Brain. Not a layer, not an agent, not an orchestrator.

It is responsible for: problem and decision framing; identifying
necessary evidence; evidence sufficiency and relevance; contradiction
detection; uncertainty representation; alternative generation; candidate
evaluation; shortlisting; trade-off reasoning; bounded critique; decision
adjudication; whether more research is worth doing; whether a method
failure warrants re-planning; and producing an evidence-grounded
rationale.

It is **not** responsible for: execution; environment access; capability
registration; Permission; provider selection; Verification; creating
Evidence; or storing Permanent Knowledge without Promotion Review.

### Wisdom is a property of the process, not of the model

Wisdom here is the quality of the process that turns *intent + context +
evidence + constraints* into the most useful justified next decision. It
requires keeping six things apart that prose collapses into one:

| | meaning |
|---|---|
| FACT | supported by authoritative Evidence |
| INFERENCE | reasoned from facts, not directly observed |
| ASSUMPTION | used temporarily and explicitly |
| UNKNOWN | unresolved |
| CONFLICT | evidence disagrees |
| RECOMMENDATION | proposed action given evidence and founder criteria |

### Decision utility — the anti-drift gate

A step, research question or reasoning operation is useful only if it
directly satisfies a requirement, obtains Evidence needed to assess one,
reduces a material uncertainty blocking one, resolves a material
contradiction, reduces a material risk to one, or unblocks another
requirement-covered step. **If none apply, it is not done.**

This reuses `SemanticRequirement` and `Step.covers`. It does not invent
parallel runtime semantics.

### Deliberation depth — intelligence only when material

`DIRECT` (deterministic, no model) · `REASONED` (one bounded operation) ·
`DELIBERATIVE` (multiple evidence items, ranking, conflict, alternatives)
· `CRITICAL` (high-impact or hard to reverse, materially uncertain).

**"More intelligence" must not mean "AI everywhere."** Creating a folder
must not deliberate. That is a test, not an aspiration.

The Brain states required reasoning *characteristics*. The Broker remains
sole provider authority. Source confirms the existing request vocabulary
already carries `min_quality` and `exclude_providers`, so a quality floor
and an independent second opinion need **no new ranking system** — the
Brain may say "independent critique required", never "use Gemini".

### Method failure is not objective failure

Three distinct things: a **source** failure (one site cannot supply
evidence), a **method** failure (this plan cannot continue), an
**objective** failure (no safe executable route remains within policy and
budget). Source confirms `MissionDispatcher._publish_objective_terminal_state`
already declares an objective failed only when nothing runnable remains,
and its own comment records that auto-retry "would be a strategic
recovery decision, which belongs to the Brain". **The seam exists and the
Brain side of it was never built.**

Recovery is bounded. A re-plan must differ materially in source, method,
capability, environment, evidence question or strategy — unless fresh
Evidence justifies retrying a transient failure.

### Browser choice is environment resolution

Ordinary live-web research should not default blindly to an isolated
Playwright browser when the ordinary real browser does the work more
reliably. Playwright stays — it is correct for localhost acceptance,
fixtures, and isolated repeatable automation. Neither lane is deleted and
no second real-browser Worker is built.

Precedence: explicit founder instruction; an already-open relevant
session; a unique suitable running browser; a persisted founder
preference; evidence-backed Environment Intelligence; otherwise **ask**.
`Chrome wins because tuple[0]` is not intelligence and must not hide in
code. Provider choice stays with the Broker, capability choice with the
Planner, environment instance resolution with environment resolution.

### Reasoning is never Verification

Reasoning says "given this Evidence, option A appears strongest."
Verification says "observed reality matched, or did not match, the
expected outcome." A critique is Brain reasoning and never becomes
Evidence or a Verdict. ADR-0011 is untouched.

### Learning without silent self-corruption

The Brain may nominate a Knowledge Candidate when Evidence supports it.
It may never promote one. Founder Promotion Review remains required per
ADR-0012. Source shows no implemented Knowledge Candidate lifecycle; the
seam is preserved and the gap recorded rather than the lifecycle being
built inside this mission.

---

## Gap classification — source-confirmed before implementation

**ALREADY BUILT.** Canonical `Intent`, `SemanticRequirement` with
`founder_evidence` / `interpretation`, multi-turn clarification,
corrections and provenance, `MissionService._admit` uncertainty gate,
Planner with deterministic and AI lanes, `Step.covers` and capability
rationale, Model Router / Broker / Provider Registry with `min_quality`
and `exclude_providers`, `Reasoning.Transform`, Runtime and
ExecutiveGateway, Permission, independent Verification and Evidence,
Playwright browser environment, `TrustedBrowserPort` /
`DesktopTrustedBrowser`, Environment Intelligence derivation,
OutcomeConformance, grounded self-query, Reporter.

**BUILT BUT NOT WIRED.**
- `IntentLayer._reasoned_requirements` — extracts requirements from a
  compound objective and is **unreachable** for exactly the objectives
  that need it: `intent.py` calls `requirements_for()` only when the
  intent has a `capability` or `answers_founder`.
- `MissionPlan.requirements` — populated only in `planner/direct.py`.
  The AI plan path (`planner/parsing.py::validate`) never sets it.
- The trusted real browser is wired for web-AI providers, not for
  general live-web research.
- Environment Intelligence does not feed browser environment resolution.
- The Runtime's recovery seam exists with no Brain decision behind it.

**WIRED BUT NOT SOURCE-PROVED.** Nothing outstanding in this mission's
scope.

**SOURCE-PROVED BUT NOT LIVE/PACKAGED-PROVED.** The semantic spine on
AI-planned lanes, once wired.

**GENUINELY MISSING.** A reusable deliberation discipline; explicit
evidence-sufficiency reasoning; contradiction adjudication; candidate and
shortlist discipline; the stop/continue research decision;
objective-aware recovery after method failure.

**DELIBERATELY FUTURE-DEFERRED.** Automatic Permanent Knowledge
promotion; unrestricted recursive debate; autonomous Constitution
modification; a generic self-development loop.

---

## Rejected alternatives

1. **A new top-level Wisdom or Intelligence layer.** The architecture
   already has the place where judgement belongs. A new layer would give
   judgement two homes and no owner.
2. **A dedicated Research Agent.** Research is not a special kind of
   work; it is ordinary work whose evidence happens to come from the web.
3. **A research-specific orchestrator.** It would generalise to nothing,
   and the founder's requirement is a faculty that generalises.
4. **Letting Workers make final decisions.** A Worker reports that a page
   says X. Whether X qualifies is the Brain's.
5. **Letting a model choose providers.** ADR-0017. The Brain states
   characteristics; the Broker decides.
6. **LLM-as-Verification.** ADR-0011. A model grading a model is the
   circularity ADR-0026 was written to end.
7. **Unlimited multi-agent debate.** One bounded critique, and only where
   material. Depth is not the same as rigour, and cost is real.
8. **Automatic learning and promotion.** ADR-0012 requires Founder
   Promotion Review; silent belief change is self-corruption.
9. **A hardcoded browser preference presented as intelligence.**
   A constant is not a judgement.
10. **One large prompt asking a model to "be smart".** The failure this
    ADR answers was not caused by an insufficiently flattering prompt,
    and prompt compliance is not a constraint (ADR-0026).

## Consequences

Founder-facing output must answer what was concluded, why that serves the
intent, what Evidence supports it, what was rejected and why when
material, what remains uncertain, and what should happen next. It must
not dump transcripts, chain-of-thought, internal scores or raw HTML.

"Why did you decide that?" must be answerable from canonical records, so
reviewable decision metadata is persisted through the existing history
and PlanRecord mechanisms. No second database, and no stored hidden
chain-of-thought — conclusions, Evidence references and explicit reasons
only.
