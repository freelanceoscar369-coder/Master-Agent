"""An invalid proposal is a candidate to repair, not a mission to end.

## The failure

Eight runs of the identical founder objective produced: a valid plan, a
duplicate-argument plan, a plan binding to a step it did not depend on,
an empty plan, and plans that chained independent sources so one block
stalled the rest. Roughly half were refused before execution, and the
founder was told *"I couldn't plan that just now. Please try again."*

Every one of those was already DETECTED precisely -- `validate()` names
the step and the mistake. Throwing that diagnosis away spends a provider
call, teaches the model nothing, and makes the founder the retry button
for a defect the system had already understood.

## The boundary

Correction repairs the PLAN REPRESENTATION. It may not touch the
objective, the requirements or the constraints -- those are repeated
verbatim and are not the model's to revise. A "try again" prompt would
have let a model quietly reinterpret the request; a correction prompt
carrying the exact error cannot.

Bounded at one attempt. A model that cannot produce a valid plan given
the precise error twice will not on the third try, and every attempt is
time a founder waits.
"""
from __future__ import annotations

import json

import pytest

from master_agent.planner.catalogue import CapabilityOption
from master_agent.planner.parsing import validate
from master_agent.planner.plan import CONSTRAINT, SemanticRequirement

REQUIREMENTS = (
    SemanticRequirement("req_1", CONSTRAINT, "find the games",
                        founder_evidence="search for action rpg games"),
    SemanticRequirement("req_2", CONSTRAINT, "give demo links",
                        founder_evidence="search for action rpg games"),
)

# Outputs declared, because a binding may only read a field the source
# capability actually publishes -- and a bare option publishes none, so a
# stand-in without them tests the wrong rule.
OPTIONS = (
    CapabilityOption(name="Browser.Navigate", output_fields=("url", "title")),
    CapabilityOption(name="Browser.ReadPageText", output_fields=("url", "title", "text")),
    CapabilityOption(name="Reasoning.Transform", output_fields=("text",)),
)

#: One that publishes nothing, for the "unknown output field" shape.
SILENT = (CapabilityOption(name="Browser.Navigate"),)


def step(step_id, capability="Browser.Navigate", **extra):
    row = {
        "id": step_id,
        "capability": capability,
        "covers": ["req_1"],
        "success": {"description": "it worked"},
    }
    row.update(extra)
    return row


def plan_of(*steps):
    return {"steps": list(steps)}


# =====================================================================
# The invalid shapes, frozen exactly as they were observed
# =====================================================================


class TestTheObservedInvalidShapesAreRejected:
    """Each of these was produced by the real Planner on the founder's
    real objective. Deterministic rejection is the precondition for
    correcting them -- something has to say precisely what is wrong."""

    def test_the_same_argument_set_twice_is_rejected(self):
        """`payload.url` and `input_bindings.url` both deciding one
        argument. Refused rather than resolved by precedence: a
        precedence rule is how a predicted literal quietly wins over an
        observed value."""
        document = plan_of(step(
            "s1", payload={"url": "https://example.invalid/"},
            input_bindings={"url": {"from_step": {"step_id": "s0", "field": "url"}}},
        ))
        plan, refusal = validate(document, OPTIONS, requirements=REQUIREMENTS)
        assert plan is None
        assert refusal is not None
        assert "same argument twice" in refusal.reason

    def test_an_empty_plan_is_reported_as_its_own_thing(self):
        """"No capability can satisfy this" and "the model produced
        nothing usable" are different system truths and must not be
        collapsed."""
        plan, refusal = validate(plan_of(), OPTIONS, requirements=REQUIREMENTS)
        assert plan is None
        assert refusal is not None
        assert refusal.code == "no_steps"

    def test_a_step_with_no_success_statement_is_rejected(self):
        document = {"steps": [{"id": "s1", "capability": "Browser.Navigate"}]}
        plan, refusal = validate(document, OPTIONS, requirements=REQUIREMENTS)
        assert plan is None
        assert refusal is not None

    def test_a_capability_outside_the_catalogue_is_rejected(self):
        document = plan_of(step("s1", capability="Browser.SolveCaptcha"))
        plan, refusal = validate(document, OPTIONS, requirements=REQUIREMENTS)
        assert plan is None
        assert refusal is not None


class TestAValidPlanStillPassesUntouched:
    def test_a_well_formed_plan_is_accepted(self):
        document = plan_of(
            step("s1", payload={"url": "https://example.invalid/"}),
            step("s2", capability="Browser.ReadPageText",
                 covers=["req_1", "req_2"], depends_on=["s1"]),
        )
        plan, refusal = validate(document, OPTIONS, requirements=REQUIREMENTS)
        assert refusal is None
        assert plan is not None
        assert len(plan.steps) == 2

    def test_coverage_survives_onto_the_plan(self):
        document = plan_of(step("s1", covers=["req_1", "req_2"]))
        plan, _refusal = validate(document, OPTIONS, requirements=REQUIREMENTS)
        assert plan.steps[0].covers == ("req_1", "req_2")
        assert len(plan.requirements) == 2


# =====================================================================
# The correction pass
# =====================================================================


class Outcome:
    def __init__(self, document):
        self.ok = True
        self.refused = False
        self.refusal = None
        self.text = json.dumps(document)
        self.entry_id = 1
        self.provider_id = "p"
        # The Planner checks the plan TEXT against an expectation before
        # parsing it, so a stand-in has to carry a verdict like the real
        # Evidence does.
        from master_agent.verification.evidence import Verdict

        self.evidence = type(
            "E", (), {"observation": {"json": document},
                      "verdict": Verdict.MATCHED},
        )()


class Runner:
    """Answers with a queue of documents, recording every prompt."""

    def __init__(self, *documents):
        self._documents = list(documents)
        self.prompts = []

    def run(self, prompt, request, expected=None):
        self.prompts.append(prompt)
        return Outcome(self._documents.pop(0) if self._documents
                       else {"steps": []})


class TestBoundedSelfCorrection:
    def planner(self, runner):
        from master_agent.planner.planner import Planner

        planner = Planner.__new__(Planner)
        planner._runner = runner
        planner._offline = False
        planner._requires_strong_reasoning = False
        planner._requester = "test"
        planner.options = lambda: OPTIONS
        planner.mode = lambda: "both"
        return planner

    def intent(self):
        from master_agent.planner.plan import Intent

        intent = Intent(goal="research something", constraints=[],
                        context={}, success_criteria=[])
        intent.requirements = REQUIREMENTS
        intent.is_sensitive = False
        return intent

    BAD = None
    GOOD = None

    def documents(self):
        bad = plan_of(step(
            "s1", payload={"url": "https://example.invalid/"},
            input_bindings={"url": {"from_step": {"step_id": "s0", "field": "url"}}},
        ))
        good = plan_of(step("s1", payload={"url": "https://example.invalid/"}))
        return bad, good

    def test_an_invalid_first_proposal_is_repaired(self):
        bad, good = self.documents()
        runner = Runner(bad, good)
        outcome = self.planner(runner).plan(self.intent())
        assert outcome.plan is not None, "the repairable plan was not repaired"
        assert outcome.refusal is None
        assert outcome.corrected is True
        assert len(runner.prompts) == 2

    def test_the_correction_prompt_carries_the_exact_error(self):
        """Not "try again" -- the specific mistake, or the second attempt
        is only another roll of the dice."""
        bad, good = self.documents()
        runner = Runner(bad, good)
        self.planner(runner).plan(self.intent())
        repair = runner.prompts[1]
        assert "same argument twice" in repair
        assert "was not a valid plan" in repair

    def test_the_correction_repeats_the_objective_and_requirements(self):
        """It repairs the plan. It does not get to reconsider the
        request."""
        bad, good = self.documents()
        runner = Runner(bad, good)
        self.planner(runner).plan(self.intent())
        repair = runner.prompts[1]
        assert "research something" in repair
        assert "req_1" in repair and "req_2" in repair
        assert "not yours to revise" in repair

    def test_a_valid_first_proposal_costs_no_second_call(self):
        """Correction is for failure. A founder must not pay for it on
        every mission."""
        _bad, good = self.documents()
        runner = Runner(good)
        outcome = self.planner(runner).plan(self.intent())
        assert outcome.plan is not None
        assert outcome.corrected is False
        assert len(runner.prompts) == 1

    def test_correction_is_bounded_at_one_attempt(self):
        """Invalid every time must terminate, not loop."""
        bad, _good = self.documents()
        runner = Runner(bad, bad, bad, bad)
        outcome = self.planner(runner).plan(self.intent())
        assert outcome.plan is None
        assert outcome.refusal is not None
        assert len(runner.prompts) == 2, (
            f"planning made {len(runner.prompts)} provider calls; the "
            "correction pass is not bounded"
        )

    def test_a_failed_repair_reports_the_original_diagnosis(self):
        """The first diagnosis is the honest one. A second failure's
        wording would only describe a second symptom."""
        bad, _good = self.documents()
        runner = Runner(bad, bad)
        outcome = self.planner(runner).plan(self.intent())
        assert "same argument twice" in outcome.refusal.reason


class TestTheDependencyViolationIsRepairable:
    """The shape that refused a live run: a step reading a value from a
    step it does not depend on. Observed, not invented."""

    def test_binding_to_a_field_nobody_publishes_is_rejected(self):
        """A model may not invent an output field."""
        document = plan_of(
            step("s1", payload={"url": "https://example.invalid/"}),
            step("s2", capability="Browser.Navigate", depends_on=["s1"],
                 payload={},
                 input_bindings={"url": {
                     "from_step": {"step_id": "s1", "field": "invented"}}}),
        )
        plan, refusal = validate(document, SILENT, requirements=REQUIREMENTS)
        assert plan is None
        assert refusal is not None

    def test_it_is_rejected_deterministically(self):
        document = plan_of(
            step("s1", payload={"url": "https://example.invalid/"}),
            step("s2", capability="Reasoning.Transform",
                 payload={"instruction": "summarise"},
                 input_bindings={"context": {
                     "from_step": {"step_id": "s1", "field": "title"}}}),
        )
        plan, refusal = validate(document, OPTIONS, requirements=REQUIREMENTS)
        assert plan is None
        assert refusal is not None
        assert "depend" in refusal.reason

    def test_declaring_the_dependency_makes_it_valid(self):
        """Which is what makes it repairable: the fix is one field, and
        the error names it."""
        document = plan_of(
            step("s1", payload={"url": "https://example.invalid/"}),
            step("s2", capability="Reasoning.Transform",
                 payload={"instruction": "summarise"},
                 depends_on=["s1"],
                 input_bindings={"context": {
                     "from_step": {"step_id": "s1", "field": "title"}}}),
        )
        plan, refusal = validate(document, OPTIONS, requirements=REQUIREMENTS)
        assert refusal is None
        assert plan is not None
