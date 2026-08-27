"""A question mark is linguistic form. It is not evidence about history.

## The defect

A founder opened a fresh session and typed:

    whats required to achieve state kalpavriksha builds kalpavriksha?

Three milliseconds later they were told:

    Nothing has run yet, so there's nothing to report on.

No Planner, no Broker, no reasoning, no mission. `structural_role()`
returned `FOLLOW_UP` with `confident=True` because the sentence ended in
a question mark, so the surface answered it from the mission record --
of which there was none.

`confident=True` is the load-bearing half. It meant the Brain's own
reasoning door was never consulted, so nothing downstream ever got the
chance to notice that the question was about the future.

## The distinction, and where it now lives

A follow-up needs something to follow. Whether one exists is a fact about
the CONVERSATION, and `brain/utterance.py` can only see one sentence of
it -- so the referent is passed in by the surface, which holds it, rather
than guessed at by the module that cannot.

The same sentence is therefore a follow-up when a mission stands behind
it and an informational question when nothing does. That is the honest
reading: *"why did that fail?"* means two different things in the two
situations, and no amount of grammar tells them apart.

## What an informational question then becomes

Work for the Reasoning Executive. `Reasoning.Transform(instruction) ->
text` was registered the whole time, so the answer needs no advisory
layer, no second brain and no new subsystem: the Intent Layer names the
capability, the Planner's ordinary one-step path plans it WITHOUT a
model, the Broker chooses a provider, `TextVerifier` verifies the answer,
and `Step.answers_founder` carries it back.

AI planning calls: zero. AI reasoning: yes, in the one place the
architecture puts it.
"""
from __future__ import annotations

import pytest

from master_agent.brain.intent import IntentLayer
from master_agent.brain.utterance import UtteranceRole, structural_role
from master_agent.capabilities.extraction import contracts_from_actions
from master_agent.capabilities.index import build_index
from master_agent.environment.browser_session import BrowserSessionManager
from master_agent.executor.executor import LocalExecutor
from master_agent.mission_control.capabilities import qualified_name
from master_agent.permissions.permission_system import PermissionSystem
from master_agent.planner.catalogue import catalogue_from_index
from master_agent.planner.direct import direct_plan
from master_agent.planner.plan import Intent
from master_agent.planner.planner import Planner
from master_agent.plugins.browser_plugin import BrowserPlugin
from master_agent.plugins.filesystem_plugin import FilesystemPlugin
from master_agent.plugins.reasoning_plugin import ReasoningPlugin

#: Verbatim, from the live session.
THE_QUESTION = "whats required to achieve state kalpavriksha builds kalpavriksha?"


class ForbiddenRunner:
    """A reasoning runner the PLANNER must never reach.

    Note what this does and does not forbid. Planning a question must ask
    no provider; ANSWERING it must ask exactly one, inside
    `Reasoning.Transform`. This stub sits at the planning door only.
    """

    def run(self, prompt, request, **kwargs):
        raise AssertionError(
            "PROVIDER MUST NOT BE CONTACTED TO PLAN -- a question names one "
            f"registered capability. Prompt was {len(prompt)} chars."
        )


@pytest.fixture
def options():
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


def role(text: str, *, has_referent: bool = False, awaiting: bool = False,
         options_offered: tuple[str, ...] = ()) -> UtteranceRole:
    decided, _confident = structural_role(
        text, awaiting_answer=awaiting, options=options_offered,
        has_referent=has_referent,
    )
    return decided


# =====================================================================
# A · a question with nothing behind it is not a report request
# =====================================================================


class TestNoReferent:
    @pytest.mark.parametrize("question", [
        THE_QUESTION,
        "what is required to make Kalpavriksha self-improving?",
        "how should we sequence the next three milestones?",
        "why does the broker prefer free providers?",
        "what would it take to ship this by Friday?",
    ])
    def test_a_question_about_the_future_is_never_a_follow_up(self, question):
        assert role(question, has_referent=False) is UtteranceRole.INFORMATIONAL_QUESTION

    def test_the_exact_live_question_reaches_reasoning(self, options):
        intent = IntentLayer().answer_question(THE_QUESTION).intent
        plan = direct_plan(intent, options)

        assert plan is not None
        assert [step.capability for step in plan.steps] == ["Reasoning.Transform"]
        assert plan.steps[0].payload == {"instruction": THE_QUESTION}

    def test_planning_a_question_asks_no_provider(self, options):
        """The regression this prevents is not "it answers". It is a
        question quietly costing a planning round trip to rediscover that
        thinking is done by the thinking capability."""
        planner = Planner(runner=ForbiddenRunner(), catalogue=options)
        outcome = planner.plan(IntentLayer().answer_question(THE_QUESTION).intent)

        assert outcome.planned, outcome.reason
        assert outcome.attempts == ()
        assert outcome.provider_id is None

    def test_the_answer_is_designated_so_it_reaches_the_founder(self, options):
        plan = direct_plan(IntentLayer().answer_question(THE_QUESTION).intent, options)
        assert plan.steps[0].answers_founder == "text"

    def test_a_designation_the_contract_does_not_publish_is_refused(self, options):
        """The same discipline the argument roster gets. Promising a field
        nobody declared is a guess about outputs."""
        intent = IntentLayer().answer_question(THE_QUESTION).intent
        assert direct_plan(
            Intent(
                goal=intent.goal, capability=intent.capability,
                payload=dict(intent.payload), answers_founder="rationale",
            ),
            options,
        ) is None

    def test_the_question_travels_verbatim(self, options):
        """Nothing rewrites the founder's sentence on the way to the
        provider -- what they asked is what gets answered."""
        plan = direct_plan(IntentLayer().answer_question(THE_QUESTION).intent, options)
        assert plan.steps[0].payload["instruction"] == THE_QUESTION


# =====================================================================
# C · with a referent, a follow-up is still a follow-up
# =====================================================================


class TestWithReferent:
    @pytest.mark.parametrize("question", [
        "why did that fail?",
        "what did it actually do?",
        "how long did that take?",
    ])
    def test_a_question_about_a_real_prior_mission_is_a_follow_up(self, question):
        assert role(question, has_referent=True) is UtteranceRole.FOLLOW_UP

    def test_the_identical_sentence_splits_on_the_referent_alone(self):
        """The whole design in one assertion: same words, two roles,
        decided by whether there is anything to talk about."""
        assert role("why did that fail?", has_referent=True) is UtteranceRole.FOLLOW_UP
        assert role("why did that fail?", has_referent=False) is (
            UtteranceRole.INFORMATIONAL_QUESTION
        )


# =====================================================================
# D · E · F · nothing else moved
# =====================================================================


class TestTheRestOfTheVocabularyIsUnchanged:
    def test_an_offered_option_is_still_an_answer(self):
        assert role("Research", awaiting=True, options_offered=("Research", "Notes")) is (
            UtteranceRole.ANSWER_TO_CLARIFICATION
        )

    def test_a_short_value_while_a_question_is_open_is_still_an_answer(self):
        assert role("Quarterly Report", awaiting=True) is (
            UtteranceRole.ANSWER_TO_CLARIFICATION
        )

    def test_a_question_while_a_question_is_open_is_still_a_follow_up(self):
        """An open question IS a referent -- the founder is asking about
        the thing being asked of them. `has_referent` does not enter into
        it, and this asserts that the new parameter did not disturb the
        branch that already handled this."""
        assert role("what do you mean?", awaiting=True, has_referent=False) is (
            UtteranceRole.FOLLOW_UP
        )

    @pytest.mark.parametrize("instruction", [
        "create a folder called Notes on the Desktop",
        "open a browser session and navigate to http://127.0.0.1:8742/a.html",
        "write the summary into notes.txt",
    ])
    def test_an_explicit_instruction_is_still_a_new_objective(self, instruction):
        assert role(instruction) is UtteranceRole.NEW_OBJECTIVE

    @pytest.mark.parametrize("polite", [
        "could you create a folder called Notes on the Desktop?",
        "can you open a browser session and navigate to http://x.test?",
        "would you please write the summary into notes.txt?",
    ])
    def test_a_polite_request_is_work_not_a_question(self, polite):
        """A modal in front of a verb is politeness, not enquiry. Without
        this, making referent-less questions answerable would have turned
        every courteous instruction into something to think about instead
        of something to do."""
        assert role(polite) is UtteranceRole.NEW_OBJECTIVE

    @pytest.mark.parametrize("stop", ["stop", "never mind", "forget it", "nothing thanks"])
    def test_stopping_is_still_stopping(self, stop):
        assert role(stop, awaiting=True) is UtteranceRole.CANCEL_OR_STOP
        assert role(stop) is UtteranceRole.CANCEL_OR_STOP

    def test_a_statement_is_still_a_new_objective(self):
        assert role("Learn trading") is UtteranceRole.NEW_OBJECTIVE


# =====================================================================
# The surface wires the referent it holds
# =====================================================================


class TestTheSurfaceSuppliesTheReferent:
    def test_it_passes_the_previous_objective_as_the_referent(self):
        """Read from the source of the one function that decides. The
        referent must come from the mission that actually ran, not from a
        constant and not from the presence of a pending question."""
        import inspect

        import kalpavriksha_desktop as kd

        source = inspect.getsource(kd._submit_objective)
        assert "has_referent=previous_objective_id is not None" in source

    def test_an_informational_question_is_routed_to_the_intent_layer(self):
        import inspect

        import kalpavriksha_desktop as kd

        source = inspect.getsource(kd._submit_objective)
        assert "UtteranceRole.INFORMATIONAL_QUESTION" in source
        assert "intent_layer.answer_question(text)" in source
