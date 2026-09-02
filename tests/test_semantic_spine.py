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

import json
import re
from types import SimpleNamespace

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

    def test_compound_semantics_separate_candidate_properties_from_mission_outputs(self):
        offered = [
            {
                "kind": "information",
                "description": "compare products",
                "candidate_property": True,
                "source_quote": "compare products",
                "success_meaning": "the products are compared",
            },
            {
                "kind": "information",
                "description": "recommend one",
                "candidate_property": False,
                "source_quote": "recommend one",
                "success_meaning": "one product is recommended",
            },
            {
                "kind": "deliverable",
                "description": "save a report",
                "candidate_property": False,
                "source_quote": "save a report",
                "success_meaning": "the report is saved",
            },
        ]

        class Reasoner:
            def run(self, prompt, _request):
                # Stage 1C settles the Founder obligation set upstream,
                # blind to this decomposition. This case is about the
                # requirement boundary below it, so it supplies a trusted
                # obligation set exactly as production would.
                if "Enumerate the separate" in prompt:
                    return SimpleNamespace(ok=True, text=json.dumps({
                        "anchors": [
                            {"anchor_id": f"anchor_{index}",
                             "source_quote": item["source_quote"],
                             "meaning": item["success_meaning"],
                             "depends_on": []}
                            for index, item in enumerate(offered, start=1)
                        ],
                    }))
                if "Audit whether a proposed set" in prompt:
                    regions = sorted({int(found) for found in re.findall(
                        r'"region_index":\s*(\d+)', prompt)})
                    cand = sorted({int(f) for f in re.findall(
                        r'"candidate_index":\s*(\d+)', prompt)})
                    ids = [f"anchor_{i}"
                           for i, _ in enumerate(offered, start=1)]
                    return SimpleNamespace(ok=True, text=json.dumps({
                        "state_candidates": [
                            {"candidate_index": index,
                             "relationship": "independent_outcome",
                             "anchor_id": ids[position]}
                            if position < len(ids) else
                            {"candidate_index": index,
                             "relationship": "context",
                             "reason": "not exercised by this case"}
                            for position, index in enumerate(cand)
                        ],
                        "regions": [
                            {"region_index": index,
                             "disposition": "represented_by_anchor",
                             "anchor_id": "anchor_1"}
                            for index in regions
                        ],
                        "anchors": [
                            {"anchor_id": f"anchor_{index}", "entailed": True}
                            for index, _item in enumerate(offered, start=1)
                        ],
                        "omissions": [], "collapses": [], "invented": [],
                        "valid": True,
                    }))
                if "semantic admission reviewer" in prompt:
                    document = {
                        "valid": True,
                        "independently_verifiable": True,
                        "anchors": [
                            {
                                "anchor_id": f"anchor_{index}",
                                "source_quote": item["source_quote"],
                                "meaning": item["success_meaning"],
                                "depends_on": [],
                            }
                            for index, item in enumerate(offered, start=1)
                        ],
                        "coverage": [
                            {
                                "anchor_id": f"anchor_{index}",
                                "requirement_indices": [index],
                                "independently_trackable": True,
                            }
                            for index, _item in enumerate(offered, start=1)
                        ],
                        "invented": [],
                    }
                else:
                    document = {"requirements": offered}
                return SimpleNamespace(ok=True, text=json.dumps(document))

        intent = SimpleNamespace(
            goal="compare products, recommend one, and save a report",
            capability="",
            payload={},
            answers_founder="",
        )
        requirements = layer(Reasoner()).requirements_for(intent, raw=intent.goal)

        assert [r.candidate_property for r in requirements] == [True, False, False]
        assert [r.description for r in requirements] == [
            "compare products", "recommend one", "save a report",
        ]


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


# =====================================================================
# The circular validation this spine exists to end
# =====================================================================


class TestConformanceIsNotCircular:
    r"""The failure that invalidated the guarantee, twice.

        Founder meant   D:\Onkar\Rudra
        Brain resolved  location = d_drive
        Execution made  D:\Rudra
        Verification    MATCHED  (it does exist)
        Conformance     SATISFIED

    Both sides of that comparison came from the same wrong reading. The
    requirement had been written from the RESOLVED value, so it agreed
    with itself — the system proved consistency with its own
    interpretation and called it correspondence with meaning.

    A requirement now carries what the founder SAID beside what it was
    read as, and an interpretation that was never settled can never be
    reported as satisfied.
    """

    def test_a_requirement_keeps_the_founders_own_words(self):
        from master_agent.brain.intent import ClarificationQuestion

        brain = layer()
        fields = ("folder_name", "location", "parent")
        first = brain.clarify(
            "create a folder", "Rudra",
            ClarificationQuestion(question="What?", key="folder_name",
                                  gathering=fields),
            supplied={}, evidence={},
        )
        second = brain.clarify(
            "create a folder", "on my desktop",
            ClarificationQuestion(question="Where?", key="location",
                                  gathering=fields),
            supplied=first.resolved, evidence=first.evidence,
        )
        said = {
            r.description: r.founder_evidence
            for r in second.intent.requirements
        }
        assert said["location = desktop"] == "on my desktop"
        # And a value settled a TURN EARLIER still has its evidence --
        # partial survival is not survival.
        assert said["name = Rudra"] == "Rudra"

    def test_an_uncertain_interpretation_is_never_satisfied(self):
        """Whatever execution proved, it proved it about a reading nobody
        confirmed."""
        from master_agent.planner.plan import UNCERTAIN

        requirement = SemanticRequirement(
            "req_1", EFFECT, "location = d_drive",
            founder_evidence="d drive in onkar folder",
            interpretation=UNCERTAIN,
        )
        outcome = assess((requirement,), [Task("a", ("req_1",), "matched")])
        assert outcome.state == UNKNOWN, (
            "a verified step made an unsettled interpretation look satisfied"
        )
        assert "never settled" in outcome.requirements[0].reason

    def test_a_settled_interpretation_with_evidence_can_be_satisfied(self):
        requirement = SemanticRequirement(
            "req_1", EFFECT, "location = desktop",
            founder_evidence="on my desktop",
        )
        assert assess((requirement,), [Task("a", ("req_1",), "matched")]).state == (
            SATISFIED
        )

    def test_interpretation_defaults_to_known_so_nothing_silently_degrades(self):
        from master_agent.planner.plan import KNOWN

        assert SemanticRequirement("req_1", EFFECT, "x").interpretation == KNOWN


class TestNestedDestinationsAreExpressible:
    r"""Source adjudication, not a guess.

    `executor/action.py::is_unsafe_relative_path` names
    `CreateFolderAction`'s `name` among the arguments that are "a
    relative path/name meant to be joined onto a configured location's
    base directory". `run()` does ``base / name`` then
    ``mkdir(parents=True)``. `validate()`'s own comment contemplates
    multi-segment values like "MyProject/src".

    So "d drive in onkar folder" is expressible through the EXISTING
    contract, and the founder's meaning must reach it rather than being
    refused as unsupported.
    """

    def test_the_capability_contract_permits_a_relative_path(self):
        from master_agent.executor.action import is_unsafe_relative_path

        assert is_unsafe_relative_path("Onkar/Rudra") is False
        # And the guard that makes that safe is still doing its job.
        assert is_unsafe_relative_path("../escape") is True
        assert is_unsafe_relative_path("/etc/passwd") is True
        assert is_unsafe_relative_path("D:config") is True

    def test_a_parent_folder_becomes_a_relative_name(self):
        from master_agent.brain.intent import ClarificationQuestion

        brain = IntentLayer(
            reasoner=_Reasoner('{"fields": {"location": "d_drive", '
                               '"parent": "onkar"}}'),
            vocabularies={"location": PLACES},
        )
        result = brain.clarify(
            "create a folder", "d drive in onkar folder",
            ClarificationQuestion(question="Where?", key="location",
                                  gathering=("folder_name", "location", "parent")),
            supplied={"folder_name": "Rudra"}, evidence={},
        )
        assert result.intent is not None, "the founder's meaning was refused"
        payload = dict(result.intent.payload)
        assert payload["location"] == "d_drive"
        assert payload["name"] == "onkar/Rudra"

    def test_no_second_filesystem_capability_was_built(self):
        """The existing contract expresses this. A new capability would
        be a second way to do one thing."""
        from master_agent.plugins.filesystem_plugin import FilesystemPlugin
        from master_agent.executor.executor import LocalExecutor
        from master_agent.permissions.permission_system import PermissionSystem

        actions = FilesystemPlugin(LocalExecutor(PermissionSystem()))._actions
        assert not any("nested" in name.lower() for name in actions)
        assert not any("subfolder" in name.lower() for name in actions)


class _Reasoner:
    def __init__(self, reply: str) -> None:
        self.reply = reply

    def run(self, prompt, request, **kwargs):
        class Outcome:
            ok = True
            text = self.reply

        return Outcome()
