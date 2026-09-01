"""Mission Brief 036 — an objective becomes steps, and every step says
what it expects.

The Definition of Done, as a property of the running system:

```
Intent -> catalogue -> Broker -> provider -> Evidence -> MissionPlan
```

with every Step carrying an `ExpectedOutcome` stated before it runs,
nothing in the plan naming a capability that does not exist, and no
fallback plan on any of the five ways it can fail.
"""
from __future__ import annotations

import pytest

from master_agent.mission_control.capabilities import (
    CapabilityDescriptor,
    CapabilityRegistry,
)
from master_agent.planner import plan as vocabulary
from master_agent.planner.planner import PLANNING_CAPABILITY, Planner
from master_agent.planner.prompting import plan_expectation
from tests.planner_test_support import (
    CATALOGUE,
    CREATE,
    DELETE,
    WRITE,
    StubRunner,
    fenced,
    plan_text,
    refused,
    step,
    success,
)


def intent(goal: str = "Set up a project folder", **kwargs) -> vocabulary.Intent:
    return vocabulary.Intent(goal=goal, **kwargs)


def planner(*replies, catalogue=CATALOGUE, **kwargs) -> tuple[Planner, StubRunner]:
    runner = StubRunner(*replies)
    return Planner(runner, catalogue, **kwargs), runner


# =========================================================================
# The whole path, working
# =========================================================================


def test_an_objective_becomes_a_plan_whose_every_step_states_what_it_expects():
    """The Definition of Done in one test. Constitution §3.2 says every
    Step names an Expected Outcome; before MB036 nothing produced one."""
    subject, _runner = planner(
        plan_text(
            step("make_folder", CREATE.name, {"path": "/tmp/demo"}),
            step(
                "write_readme",
                WRITE.name,
                {"path": "/tmp/demo/README.md"},
                depends_on=["make_folder"],
                success_doc=success("a README is written", must_contain=["README"]),
            ),
        )
    )

    outcome = subject.plan(intent())

    assert outcome.planned
    assert outcome.refusal is None
    assert [s.step_id for s in outcome.plan.steps] == ["make_folder", "write_readme"]
    assert [s.capability for s in outcome.plan.steps] == [CREATE.name, WRITE.name]
    assert outcome.plan.objective == "Set up a project folder"
    assert all(s.expected_outcome is not None for s in outcome.plan.steps)
    assert outcome.provider_id == "alpha-local"
    assert outcome.entry_id == 7


def test_no_step_can_carry_an_expectation_that_cannot_be_evaluated():
    """MB035 documents that an `ExpectedOutcome` with no checks evaluates
    to ERROR under the frozen evaluator. A Planner that emitted one would
    be producing steps that can never be verified, which is worse than
    producing none."""
    subject, _ = planner(
        plan_text(step("one"), step("two", WRITE.name, {"path": "/tmp/x"}))
    )

    outcome = subject.plan(intent())

    for planned_step in outcome.plan.steps:
        assert planned_step.expected_outcome.checks, planned_step.step_id
        assert planned_step.expected_outcome.description


def test_a_stated_expectation_becomes_real_checks_not_a_description():
    subject, _ = planner(
        plan_text(
            step(
                "one",
                success_doc=success(
                    "a JSON report",
                    must_contain=["created"],
                    must_exclude=["error"],
                    must_be_json=True,
                    must_have_fields=["path"],
                    min_words=3,
                ),
            )
        )
    )

    expected = subject.plan(intent()).plan.steps[0].expected_outcome

    assert expected.description == "a JSON report"
    fields = [check.field for check in expected.checks]
    # not_empty, contains, excludes, is_json, json_has, at_least_words
    assert len(expected.checks) == 6
    assert "empty" in fields and "normalised" in fields and "is_json" in fields


def test_the_expectation_on_the_plan_itself_is_stated_before_the_request():
    """MB035's argument is that a check is only falsifiable if it existed
    before the answer did. The plan is generated text like any other, so
    it is checked the same way -- and the expectation travels *with* the
    request rather than being applied to whatever came back."""
    subject, runner = planner()

    subject.plan(intent())

    assert runner.calls[0]["expected"] == plan_expectation()


def test_the_verification_record_for_the_plan_travels_with_the_outcome():
    subject, _ = planner(plan_text(step("one")))

    outcome = subject.plan(intent())

    assert outcome.evidence is not None
    assert outcome.evidence.verdict.value == "matched"
    assert outcome.as_dict()["verdict"] == "matched"


def test_a_fenced_reply_is_still_a_plan():
    """Small local models wrap JSON in a ``` fence. MB035's `_as_json`
    already unwraps one, and the Planner reads the document the verifier
    parsed -- so there is exactly one unwrapping in the system and this
    works without a second one."""
    subject, _ = planner(fenced(plan_text(step("one"))))

    outcome = subject.plan(intent())

    assert outcome.planned
    assert outcome.plan.steps[0].step_id == "one"


# =========================================================================
# The prompt
# =========================================================================


def test_the_provider_is_shown_the_real_catalogue_and_told_it_is_exhaustive():
    subject, runner = planner()

    subject.plan(intent())

    prompt = runner.prompt
    for option in CATALOGUE:
        assert option.name in prompt
        assert option.description in prompt
    assert "exhaustive" in prompt
    assert "[risk: irreversible]" in prompt, "an irreversible capability is not flagged"


def test_the_objective_constraints_and_criteria_all_reach_the_provider():
    subject, runner = planner()

    subject.plan(
        intent(
            "Tidy the workspace",
            constraints=["never delete anything"],
            success_criteria=["the folder still exists"],
            context={"root": "/tmp/demo"},
        )
    )

    prompt = runner.prompt
    assert "Tidy the workspace" in prompt
    assert "never delete anything" in prompt
    assert "the folder still exists" in prompt
    assert "root: /tmp/demo" in prompt


def test_the_same_intent_produces_a_byte_identical_prompt():
    """A prompt whose text depends on dict or registration order would
    make the same objective produce a different plan on a different boot,
    and would stop the prompt cache from ever hitting."""
    first, runner_one = planner()
    second, runner_two = planner()
    context = {"b": 2, "a": 1, "c": 3}

    first.plan(intent(context=dict(context)))
    second.plan(intent(context={"c": 3, "a": 1, "b": 2}))

    assert runner_one.prompt == runner_two.prompt


# =========================================================================
# The five ways it stops, all closed
# =========================================================================


def test_nothing_registered_means_nothing_is_even_asked():
    """Asking a provider to plan against an empty list would produce steps
    naming capabilities that do not exist. The tokens are not spent."""
    subject, runner = planner(catalogue=())

    outcome = subject.plan(intent())

    assert outcome.plan is None
    assert outcome.refusal.code == vocabulary.NO_CAPABILITIES
    assert runner.calls == [], "a provider was contacted with nothing to plan with"


def test_a_broker_refusal_is_passed_through_in_the_brokers_own_words():
    subject, _ = planner(refused("no provider clears the 0.90 quality floor"))

    outcome = subject.plan(intent())

    assert outcome.plan is None
    assert outcome.refusal.code == vocabulary.BROKER_REFUSED
    assert "no provider clears the 0.90 quality floor" in outcome.refusal.reason
    assert outcome.entry_id == 7, "the decision is still on the ledger"


def test_a_provider_that_could_not_answer_is_reported_as_that():
    from master_agent.ai_infrastructure.execution import PromptOutcome

    subject, _ = planner(PromptOutcome(ok=False, provider_id="alpha-local"))

    outcome = subject.plan(intent())

    assert outcome.plan is None
    assert outcome.refusal.code == vocabulary.PROVIDER_FAILED


def test_the_reason_a_provider_failed_is_in_the_sentence_not_only_the_detail():
    """Found by running MB037 live. A founder read "the provider could not
    answer" and had nowhere to go, while `no answer within 540s` -- the
    one fact that tells them what to change -- sat in a field the console
    does not render."""
    from master_agent.ai_infrastructure.execution import ExecutionRecord, PromptOutcome

    failed = PromptOutcome(
        ok=False,
        provider_id="alpha-local",
        execution=ExecutionRecord(
            provider_id="alpha-local",
            outcome="timed_out",
            error="no answer within 540s",
        ),
    )
    subject, _ = planner(failed)

    outcome = subject.plan(intent())

    assert "no answer within 540s" in outcome.refusal.reason
    assert outcome.refusal.detail == "no answer within 540s"


def test_an_answer_with_no_verification_record_is_refused_rather_than_trusted():
    """Fail closed. The Planner states an expectation on every request, so
    a reply arriving with no `Evidence` means the execution path did not
    apply it -- and accepting it would quietly reintroduce the gap MB035
    exists to close."""
    runner = StubRunner(plan_text(step("one")), with_evidence=False)
    subject = Planner(runner, CATALOGUE)

    outcome = subject.plan(intent())

    assert outcome.plan is None
    assert outcome.refusal.code == vocabulary.UNVERIFIED


def test_prose_is_not_a_plan_and_the_founder_can_read_what_was_actually_said():
    subject, _ = planner("Sure! I'd start by creating a folder, then...")

    outcome = subject.plan(intent())

    assert outcome.plan is None
    assert outcome.refusal.code == vocabulary.NOT_JSON
    # `partially_matched`, not `not_matched`: prose is not blank, so the
    # weakest check passed. MB035's `passed()` requires MATCHED and
    # deliberately does not accept half -- which is exactly what stops
    # "it said *something*" from counting as a plan.
    assert "partially_matched" in outcome.refusal.detail
    assert outcome.raw.startswith("Sure!"), "the reply was described but not kept"


def test_no_failure_produces_a_plan_of_its_own():
    """MB032 refused a fallback provider because a fallback is itself a
    provider decision. A fallback plan is worse: it is a plan nobody
    verified, produced at the moment the system has just shown it cannot
    plan."""
    from master_agent.ai_infrastructure.execution import PromptOutcome

    for reply in (
        refused(),
        PromptOutcome(ok=False),
        "not json at all",
        plan_text(step("x", "Filesystem.Invented")),
        '{"steps": []}',
    ):
        subject, _ = planner(reply)
        outcome = subject.plan(intent())
        assert outcome.plan is None, reply
        assert outcome.refusal is not None, reply


# =========================================================================
# A plan that is not a usable plan
# =========================================================================


def test_a_hallucinated_capability_is_refused_with_the_list_of_real_ones():
    """The MB033 discipline: a missing model is reported *with the models
    that are installed*. A founder should not have to go and look."""
    subject, _ = planner(plan_text(step("one", "Filesystem.Summarise")))

    outcome = subject.plan(intent())

    assert outcome.refusal.code == vocabulary.UNKNOWN_CAPABILITY
    assert "Filesystem.Summarise" in outcome.refusal.reason
    # The list the provider was actually shown, in the order it was shown
    # -- not a re-sorted one. "Here is what you were given" is a more
    # useful answer to "why did it invent that?" than an alphabet.
    assert outcome.refusal.known_capabilities == (CREATE.name, WRITE.name, DELETE.name)


def test_a_step_with_no_stated_expectation_fails_the_whole_plan():
    """§3.2, mechanically. Not "the step is unverified" -- the plan is
    refused, because the alternative is a plan that is 80% checkable and
    reports as checked."""
    subject, _ = planner(plan_text(step("one"), step("two", success_doc=None)))

    outcome = subject.plan(intent())

    assert outcome.plan is None
    assert outcome.refusal.code == vocabulary.MISSING_EXPECTATION
    assert "two" in outcome.refusal.detail


def test_no_steps_is_an_honest_refusal_rather_than_an_empty_plan():
    """Rule 6 of the prompt gives the provider a way to say "the catalogue
    cannot do this". An empty plan submitted to the Runtime would complete
    instantly and report success."""
    subject, _ = planner('{"steps": []}')

    outcome = subject.plan(intent())

    assert outcome.refusal.code == vocabulary.NO_STEPS
    assert outcome.refusal.known_capabilities


def test_steps_that_wait_for_each_other_in_a_circle_are_refused():
    subject, _ = planner(
        plan_text(
            step("a", depends_on=["b"]),
            step("b", depends_on=["a"]),
        )
    )

    outcome = subject.plan(intent())

    assert outcome.refusal.code == vocabulary.CYCLIC
    assert "a, b" in outcome.refusal.detail


def test_a_step_that_depends_on_itself_is_refused():
    subject, _ = planner(plan_text(step("a", depends_on=["a"])))

    assert subject.plan(intent()).refusal.code == vocabulary.BAD_DEPENDENCY


def test_a_step_that_waits_for_a_step_that_is_not_in_the_plan_is_refused():
    subject, _ = planner(plan_text(step("a", depends_on=["ghost"])))

    outcome = subject.plan(intent())

    assert outcome.refusal.code == vocabulary.BAD_DEPENDENCY
    assert "ghost" in outcome.refusal.detail


def test_two_steps_sharing_an_id_are_refused():
    subject, _ = planner(plan_text(step("a"), step("a", WRITE.name)))

    outcome = subject.plan(intent())

    assert outcome.refusal.code == vocabulary.MALFORMED
    assert "share the id" in outcome.refusal.detail


def test_the_steps_come_back_in_an_order_that_can_actually_be_executed():
    """The Orchestrator walks `plan.steps` in list order, so declared
    dependencies have to become list order or they are decoration."""
    subject, _ = planner(
        plan_text(
            step("third", depends_on=["second"]),
            step("first"),
            step("second", depends_on=["first"]),
        )
    )

    outcome = subject.plan(intent())

    assert [s.step_id for s in outcome.plan.steps] == ["first", "second", "third"]


def test_independent_steps_keep_the_order_the_provider_declared():
    """Kahn's algorithm with an arbitrary tie-break would reorder
    independent steps differently on different runs."""
    subject, _ = planner(
        plan_text(step("zulu"), step("alpha"), step("mike"))
    )

    outcome = subject.plan(intent())

    assert [s.step_id for s in outcome.plan.steps] == ["zulu", "alpha", "mike"]


# =========================================================================
# What it asks the Broker for
# =========================================================================


def test_the_broker_is_asked_for_reasoning_and_told_who_is_asking():
    subject, runner = planner()

    subject.plan(intent(), task_id="task-9", objective_id="objective-3")

    request = runner.calls[0]["request"]
    assert request.capability == PLANNING_CAPABILITY
    assert request.requester == "planner"
    assert request.task_id == "task-9"
    assert request.objective_id == "objective-3"


def test_a_sensitive_objective_is_declared_sensitive_to_the_broker():
    """The Planner states facts about the work. What that implies for
    provider choice is the Broker's, and only the Broker's."""
    subject, runner = planner()

    subject.plan(intent(is_sensitive=True))

    assert runner.calls[0]["request"].sensitive is True


def test_the_quality_floor_for_planning_is_a_knob_and_not_a_hardcoded_true():
    """Planning benefits from a stronger model, but *how good a plan has
    to be* is a quality floor, and ADR-0017 gives floors to the founder's
    policy rather than to whichever component is asking."""
    default, runner_default = planner()
    raised, runner_raised = planner(requires_strong_reasoning=True)

    default.plan(intent())
    raised.plan(intent())

    assert runner_default.calls[0]["request"].requires_strong_reasoning is False
    assert runner_raised.calls[0]["request"].requires_strong_reasoning is True


def test_an_offline_planner_tells_the_broker_the_work_cannot_touch_the_network():
    subject, runner = planner(offline=True)

    subject.plan(intent())

    assert runner.calls[0]["request"].offline is True


# =========================================================================
# The catalogue is a port, and it is read fresh
# =========================================================================


def registry_with(*names: str) -> CapabilityRegistry:
    registry = CapabilityRegistry()
    for name in names:
        executive, capability = name.split(".")
        registry.register(
            CapabilityDescriptor(
                qualified_name=name,
                executive_id=executive.lower(),
                capability=capability,
                description=f"Does {capability}.",
                risk_tier="reversible",
            )
        )
    return registry


def test_mission_controls_registry_satisfies_the_catalogue_port_unmodified():
    """`catalogue_from()` needs one method, `all()`. Nothing in `planner/`
    imports the frozen Mission Control package to get it."""
    registry = registry_with("Filesystem.CreateFolder", "Desktop.LaunchApplication")
    subject = Planner(StubRunner(), registry)

    assert subject.catalogue_names() == (
        "Desktop.LaunchApplication",
        "Filesystem.CreateFolder",
    )


def test_the_catalogue_is_read_on_every_call_not_captured_at_construction():
    """An Executive that deregisters takes its capabilities with it. A
    Planner holding a snapshot would keep planning with them."""
    registry = registry_with("Filesystem.CreateFolder", "Browser.OpenPage")
    runner = StubRunner(plan_text(step("one", "Browser.OpenPage")))
    subject = Planner(runner, registry)

    registry.remove_executive("browser")
    outcome = subject.plan(intent())

    assert outcome.refusal.code == vocabulary.UNKNOWN_CAPABILITY
    assert outcome.refusal.known_capabilities == ("Filesystem.CreateFolder",)


def test_the_same_plan_document_always_yields_the_same_plan():
    text = plan_text(
        step("c", depends_on=["a"]), step("a"), step("b", depends_on=["a"])
    )

    first = Planner(StubRunner(text), CATALOGUE).plan(intent())
    second = Planner(StubRunner(text), CATALOGUE).plan(intent())

    assert [s.step_id for s in first.plan.steps] == [s.step_id for s in second.plan.steps]
    assert [s.expected_outcome for s in first.plan.steps] == [
        s.expected_outcome for s in second.plan.steps
    ]


# =========================================================================
# Reporting
# =========================================================================


def test_a_refusal_reports_itself_without_anybody_parsing_a_sentence():
    subject, _ = planner(refused("nothing is installed"))

    reported = subject.plan(intent()).as_dict()

    assert reported["planned"] is False
    assert reported["steps"] == 0
    assert reported["refusal"]["code"] == vocabulary.BROKER_REFUSED
    assert reported["verdict"] == ""


def test_the_one_sentence_a_founder_reads_is_empty_when_there_is_a_plan():
    """`reason` answers "why not?" -- so a plan has none. An empty string
    rather than "success" keeps a caller from rendering a reason box for
    an outcome that has nothing to explain."""
    refused_outcome, _ = planner(refused("nothing is installed"))
    planned_outcome, _ = planner(plan_text(step("a")))

    assert refused_outcome.plan(intent()).reason == "no plan: nothing is installed"
    assert planned_outcome.plan(intent()).reason == ""


def test_a_plan_reports_how_many_steps_it_has():
    subject, _ = planner(plan_text(step("a"), step("b", WRITE.name)))

    reported = subject.plan(intent()).as_dict()

    assert reported == {
        "planned": True,
        "steps": 2,
        "provider_id": "alpha-local",
        "entry_id": 7,
        "verdict": "matched",
        "refusal": None,
    }


@pytest.mark.parametrize(
    "reply,code",
    [
        # `steps` is there, so the plan document verified; it is the shape
        # *inside* it that is wrong, and the parser is the thing that can
        # say so precisely.
        ('{"steps": "one then two"}', vocabulary.MALFORMED),
        # A sole wrapper and a bare list reach the deterministic parser.
        # The former is the provider's honest empty-plan refusal; the
        # latter is a steps list whose entries are malformed.
        ('{"plan": []}', vocabulary.NO_STEPS),
        ("[1, 2, 3]", vocabulary.MALFORMED),
    ],
)
def test_a_document_that_is_not_a_plan_says_which_part_is_wrong(reply, code):
    subject, _ = planner(reply)

    outcome = subject.plan(intent())

    assert outcome.refusal.code == code
    assert outcome.refusal.detail
