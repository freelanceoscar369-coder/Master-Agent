"""Founder meaning, traceable from input to verified outcome.

## The gap

Three defects in three days shared one shape: the founder's meaning was
never a first-class object. It was prose at the front, arguments in the
middle, verdicts at the end, and nothing carried it across. The end of the
chain admitted it — `reporter.py` reported
`founder_outcome_conformance: "not_evaluated"`, so the system could say
every step was independently verified without being able to say whether
the thing that was asked for had happened.

## What these tests hold

The invariant from ADR-0026, at each joint:

    what did they mean → which requirements → which steps cover each →
    why that capability → what did reality show → did it satisfy them

and the boundary that keeps it honest: a semantic assessment is a Brain
judgement about correspondence, never a `Verdict` and never `Evidence`.
"""
from __future__ import annotations

import pytest

from master_agent.brain.conformance import (
    NOT_SATISFIED,
    SATISFIED,
    UNKNOWN,
    assess,
)
from master_agent.brain.intent import IntentLayer
from master_agent.capabilities.extraction import contracts_from_actions
from master_agent.capabilities.index import build_index
from master_agent.environment.browser_session import BrowserSessionManager
from master_agent.executor.executor import LocalExecutor
from master_agent.mission_control.capabilities import qualified_name
from master_agent.permissions.permission_system import PermissionSystem
from master_agent.planner.catalogue import catalogue_from_index
from master_agent.planner.direct import direct_plan
from master_agent.planner.plan import (
    CONSTRAINT,
    EFFECT,
    INFORMATION,
    REQUIREMENT_KINDS,
    SemanticRequirement,
)

PLACES = ("d_drive", "desktop", "documents", "downloads")

BROWSER_OBJECTIVE = (
    "Open a browser session and navigate to http://127.0.0.1:8742/a.html. "
    "Type the text acceptance into the element matching #acceptance-box, "
    "click the element matching #apply, observe the page and tell me the "
    "current text shown by #state, then close the browser session."
)


@pytest.fixture
def options():
    from master_agent.plugins.browser_plugin import BrowserPlugin
    from master_agent.plugins.filesystem_plugin import FilesystemPlugin
    from master_agent.plugins.reasoning_plugin import ReasoningPlugin

    executor = LocalExecutor(PermissionSystem())
    contracts = []
    for plugin in (
        BrowserPlugin(executor, BrowserSessionManager(default_headless=False)),
        FilesystemPlugin(executor),
        ReasoningPlugin(executor),
    ):
        actions = getattr(plugin, "_actions", None)
        if isinstance(actions, dict):
            contracts.extend(
                contracts_from_actions(actions, plugin.manifest.name, qualified_name)
            )
    index = build_index(contracts, loader={c.canonical_id: c for c in contracts}.get)
    return catalogue_from_index(index)


def layer(reasoner=None) -> IntentLayer:
    return IntentLayer(reasoner=reasoner, vocabularies={"location": PLACES})


class Task:
    """Mission Control's task, as conformance reads it."""

    def __init__(self, task_id: str, covers: tuple[str, ...], verdict: str | None = None):
        self.task_id = task_id
        self.covers = covers
        self.evidence = {"verdict": verdict} if verdict else None


# =====================================================================
# A · B · what the founder meant, as facts
# =====================================================================


class TestRequirementsAreExtracted:
    def test_a_typed_request_yields_an_effect_and_its_constraints(self):
        intent = layer().parse(
            "create a folder called Research on the Desktop"
        ).intent
        kinds = [r.kind for r in intent.requirements]
        assert kinds[0] == EFFECT
        assert set(kinds[1:]) == {CONSTRAINT}
        described = {r.description for r in intent.requirements}
        assert "name = Research" in described
        assert any("location" in d for d in described)

    def test_a_question_requires_information_not_an_effect(self):
        intent = layer().answer_question("what can you do right now?").intent
        assert [r.kind for r in intent.requirements] == [INFORMATION]

    def test_requirement_ids_are_deterministic_and_ordered(self):
        intent = layer().parse(
            "create a folder called Research on the Desktop"
        ).intent
        ids = [r.requirement_id for r in intent.requirements]
        assert ids == [f"req_{i}" for i in range(1, len(ids) + 1)]

    def test_every_requirement_keeps_its_provenance(self):
        sentence = "create a folder called Research on the Desktop"
        for requirement in layer().parse(sentence).intent.requirements:
            assert requirement.provenance == sentence

    def test_a_requirement_never_names_a_capability(self):
        """Requirements describe WHAT. Naming a capability here would
        make the semantic layer a second tool selector, which ADR-0026
        rejects by name."""
        intent = layer().parse(
            "create a folder called Research on the Desktop"
        ).intent
        for requirement in intent.requirements:
            assert "Filesystem." not in requirement.description
            assert "CreateFolder" not in requirement.description

    def test_the_kind_vocabulary_is_closed(self):
        assert set(REQUIREMENT_KINDS) == {
            "effect", "information", "deliverable", "constraint"
        }

    def test_the_meaning_survives_a_multi_turn_conversation(self):
        """Different roads, same meaning — the requirements must not
        depend on whether the founder said it in one breath."""
        from master_agent.brain.intent import ClarificationQuestion

        brain = layer()
        result = brain.parse("create a folder")
        known: dict[str, str] = {}
        for reply in ("Research", "on my desktop"):
            result = brain.clarify(
                "create a folder", reply, result.clarification, supplied=known
            )
            known = dict(result.resolved or known)
        staged = {r.description for r in result.intent.requirements}
        assert "name = Research" in staged
        assert "location = desktop" in staged


# =====================================================================
# C · D · a compound request keeps every requirement
# =====================================================================


class TestCompoundRequestsKeepEverything:
    def test_a_dictated_browser_workflow_records_every_operation(self, options):
        plan = direct_plan(layer().parse(BROWSER_OBJECTIVE).intent, options)
        descriptions = " | ".join(r.description for r in plan.requirements)
        for expected in ("browser session is open", "#acceptance-box",
                         "#apply", "#state", "closed"):
            assert expected in descriptions, expected

    def test_the_information_requirement_is_not_an_effect(self, options):
        """"tell me what #state shows" is something the founder must be
        TOLD. Filing it as an effect would lose the only requirement the
        mission exists to answer."""
        plan = direct_plan(layer().parse(BROWSER_OBJECTIVE).intent, options)
        told = [r for r in plan.requirements if r.kind == INFORMATION]
        assert len(told) == 1
        assert "#state" in told[0].description

    def test_a_web_request_is_not_reduced_to_a_file_search(self):
        """The live defect. A filesystem parser claiming this would erase
        the founder's actual requirements."""
        result = layer().parse(
            "search for new 2026 action rpg games and give me demo "
            "version download links"
        )
        assert not result.needs_clarification
        assert result.intent.capability == ""


# =====================================================================
# E · F · plan coverage
# =====================================================================


class TestPlansSayWhatTheyCover:
    def test_every_required_requirement_is_covered(self, options):
        plan = direct_plan(layer().parse(BROWSER_OBJECTIVE).intent, options)
        covered = {rid for step in plan.steps for rid in step.covers}
        required = {r.requirement_id for r in plan.requirements if r.required}
        assert required <= covered, required - covered

    def test_coverage_names_only_requirements_that_exist(self, options):
        plan = direct_plan(layer().parse(BROWSER_OBJECTIVE).intent, options)
        known = {r.requirement_id for r in plan.requirements}
        for step in plan.steps:
            assert set(step.covers) <= known

    def test_the_one_step_path_covers_everything_it_was_asked(self, options):
        intent = layer().parse(
            "create a folder called Research on the Desktop"
        ).intent
        plan = direct_plan(intent, options)
        assert set(plan.steps[0].covers) == {
            r.requirement_id for r in intent.requirements
        }

    def test_the_observation_answers_for_what_it_observes(self, options):
        """Type and click are delivery-only; the step that re-reads the
        page is the evidence they took effect. Coverage says so, which is
        what lets conformance be honest without inventing a verifier for
        them."""
        plan = direct_plan(layer().parse(BROWSER_OBJECTIVE).intent, options)
        observe = next(s for s in plan.steps if "Observe" in s.capability)
        typed = next(s for s in plan.steps if "TypeText" in s.capability)
        clicked = next(s for s in plan.steps if "Click" in s.capability)
        assert set(typed.covers) <= set(observe.covers)
        assert set(clicked.covers) <= set(observe.covers)

    def test_coverage_is_descriptive_and_never_dispatches(self):
        """The same discipline `priority` carries. Asserted structurally
        so a future reader cannot start ordering on it."""
        import inspect

        from master_agent.mission_control import dispatcher

        assert "covers" not in inspect.getsource(dispatcher)


# =====================================================================
# G · why this capability
# =====================================================================


class TestTheReasonSurvives:
    def test_a_step_records_why_it_was_chosen(self, options):
        plan = direct_plan(
            layer().parse("create a folder called Research on the Desktop").intent,
            options,
        )
        reason = plan.steps[0].selection_reason
        assert "Filesystem.CreateFolder" in reason
        assert "req_1" in reason

    def test_the_reason_is_built_only_from_published_facts(self, options):
        """A founder asking "why did you use that tool?" a day later must
        be answered from what was decided, not by a model producing a
        plausible reason — which is indistinguishable from the real one
        exactly when it is wrong."""
        by_name = {o.name: o for o in options}
        plan = direct_plan(
            layer().parse("create a folder called Research on the Desktop").intent,
            options,
        )
        step = plan.steps[0]
        contract = by_name[step.capability]
        assert contract.description.strip().rstrip(".").lower()[:30] in (
            step.selection_reason.lower()
        )
        for argument in contract.required_args:
            assert argument in step.selection_reason


# =====================================================================
# I · outcome conformance
# =====================================================================


class TestDidItSatisfyTheFounder:
    REQUIREMENTS = (
        SemanticRequirement("req_1", EFFECT, "the folder exists"),
        SemanticRequirement("req_2", INFORMATION, "the state is reported"),
    )

    def test_all_covered_and_matched_is_satisfied(self):
        outcome = assess(self.REQUIREMENTS, [
            Task("a", ("req_1",), "matched"), Task("b", ("req_2",), "matched"),
        ])
        assert outcome.state == SATISFIED

    def test_a_contradicted_requirement_is_not_satisfied(self):
        outcome = assess(self.REQUIREMENTS, [
            Task("a", ("req_1",), "not_matched"), Task("b", ("req_2",), "matched"),
        ])
        assert outcome.state == NOT_SATISFIED
        assert [r.requirement_id for r in outcome.unmet] == ["req_1"]

    def test_absent_evidence_is_unknown_never_done(self):
        outcome = assess(self.REQUIREMENTS, [
            Task("a", ("req_1",), "matched"), Task("b", ("req_2",)),
        ])
        assert outcome.state == UNKNOWN
        assert [r.requirement_id for r in outcome.unproven] == ["req_2"]

    def test_an_uncovered_requirement_is_unknown(self):
        outcome = assess(self.REQUIREMENTS, [Task("a", ("req_1",), "matched")])
        assert outcome.state == UNKNOWN

    def test_a_mission_with_no_semantic_trace_is_unknown(self):
        """A legacy record gets no correspondence invented for it."""
        assert assess((), [Task("a", (), "matched")]).state == UNKNOWN

    def test_an_optional_requirement_does_not_fail_the_mission(self):
        requirements = (
            SemanticRequirement("req_1", EFFECT, "the folder exists"),
            SemanticRequirement("req_2", EFFECT, "nice to have", required=False),
        )
        assert assess(requirements, [Task("a", ("req_1",), "matched")]).state == (
            SATISFIED
        )

    def test_it_asks_no_provider(self):
        """Requirements, coverage and Evidence are all recorded; the
        relationship between them is arithmetic. A model grading this
        would be a model grading a model."""
        import inspect

        from master_agent.brain import conformance

        source = inspect.getsource(conformance)
        for forbidden in ("runner", "reasoner", "prompt", "provider", "Broker"):
            assert forbidden.lower() not in source.lower().replace(
                "no provider", ""
            ).replace("a provider", ""), forbidden


# =====================================================================
# M · the boundary that keeps it honest
# =====================================================================


class TestSemanticStatesAreNotVerdicts:
    def test_the_vocabularies_do_not_overlap(self):
        from master_agent.verification.evidence import Verdict

        semantic = {SATISFIED, NOT_SATISFIED, UNKNOWN}
        verification = {v.value for v in Verdict}
        assert not (semantic & verification), (
            "a conformance state and a Verdict must never be spelled the "
            "same way, or they will eventually be treated the same way"
        )

    def test_conformance_produces_no_evidence(self):
        import inspect

        from master_agent.brain import conformance

        source = inspect.getsource(conformance)
        assert "Evidence(" not in source
        assert "Verdict." not in source

    def test_conformance_reads_verdicts_but_never_writes_one(self):
        outcome = assess(
            (SemanticRequirement("req_1", EFFECT, "x"),),
            [Task("a", ("req_1",), "matched")],
        )
        assert outcome.state == SATISFIED
        assert not hasattr(outcome, "verdict")
        assert not hasattr(outcome, "evidence_id")


# =====================================================================
# N · O · the boundaries the Brain may not cross
# =====================================================================


class TestBrainBoundaries:
    def test_semantic_code_touches_no_environment(self):
        import inspect

        from master_agent.brain import conformance, intent

        for module in (conformance, intent):
            source = inspect.getsource(module)
            for forbidden in ("subprocess", "playwright", "open(", "Path(",
                              "os.remove", "shutil"):
                assert forbidden not in source, f"{module.__name__}: {forbidden}"

    def test_no_provider_is_named_in_brain_semantics(self):
        """The Broker is the sole provider authority. Brain semantics may
        describe a request; it may never choose who answers it."""
        import inspect

        from master_agent.brain import conformance, intent

        for module in (conformance, intent):
            source = inspect.getsource(module).lower()
            for provider in ("gemini", "openrouter", "chatgpt", "ollama",
                             "perplexity", "claude-desktop"):
                assert provider not in source, f"{module.__name__}: {provider}"
