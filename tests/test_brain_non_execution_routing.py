"""The Brain's semantic matrix: understood, executable, and the third
thing that had no home.

Three questions were being answered with two answers:

  1. what does the founder want?          -- `brain/intent.py`
  2. is that clear enough to act on?      -- clarification, or not
  3. can it be done directly, right now?  -- the Planner, and only it

Class D and E below are the rows where 2 is *yes* and 3 is *no*. Before
`brain/advisory.py` they were spoken as though 2 were *no* -- "I can't do
that with what I'm currently able to do" -- which tells a founder their
instruction was rejected when in fact it was understood perfectly.

Nothing here calls a real provider, a real browser or a real machine.
The reasoning ladder is a recording stub, which is also what makes the
architecture invariants in the second half checkable: a test can prove
*which* runner instance was used and *what capability* was asked for.
"""
from __future__ import annotations

import inspect
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import kalpavriksha_desktop as kd  # noqa: E402

from master_agent.brain import advisory  # noqa: E402
from master_agent.brain.advisory import UNREACHABLE, advise  # noqa: E402
from master_agent.conversation_engine.pipeline import Disposition  # noqa: E402
from master_agent.missions.execution_status import COMPLETED, FAILED, ExecutionStatus  # noqa: E402
from master_agent.planner.plan import (  # noqa: E402
    MALFORMED,
    NO_CAPABILITIES,
    NO_STEPS,
    PlanRefusal,
    UNKNOWN_CAPABILITY,
)
from tests.test_conversation_engine import T0, engine  # noqa: E402
from tests.test_kalpavriksha_desktop_mission_bridge import (  # noqa: E402
    _FakeFounderState,
    _FakeMissionControl,
    _FakeMissionService,
    _FakeObjective,
    _FakeOutcome,
    _FakeRuntime,
)

#: The sentence a founder must never hear about a goal that was
#: understood. Quoted from `_founder_refusal_sentence()`'s own output so
#: this test fails if that wording is reintroduced under a new spelling.
REFUSAL_SENTENCE = "I can't do that with what I'm currently able to do."


#: What a correct answer sounds like: Kalpavriksha is the subject of every
#: verb. It goes and reads, tracks, practises. The founder is not told to
#: do anything, because the founder did not ask to learn anything -- they
#: told this system to learn.
CORRECT_ANSWER = (
    "Understood -- you want me able to read a market myself and act on it "
    "with judgement rather than guesswork. That's not one move; it's "
    "something I build up to. I'd start by picking one liquid instrument "
    "and following it daily until I know its rhythm, pull the last few "
    "years of its price history so I have something real to test against, "
    "and paper-trade it until my calls hold up without money at risk. "
    "Shall I start on the first one now?"
)


#: The answer this module shipped with before the founder's correction.
#: Kept verbatim as a fixture: it is fluent, well-meaning and WRONG,
#: because it makes the founder the actor. If it ever reaches a founder
#: again, these tests fail.
COACHING_ANSWER = (
    "I hear you -- you want to be able to read a market and act on it "
    "with your own judgement. That's not one move, it's something we'd "
    "build up together. You should start by settling which market you "
    "actually care about, then get reading a single instrument daily "
    "until its rhythm is familiar, then paper-trade it before a rupee "
    "is at risk. Want me to start on the first one now?"
)


# =========================================================================
# Stubs
# =========================================================================


class Answer:
    """A reasoning outcome the ladder reports as usable."""

    ok = True
    refused = False

    def __init__(self, text: str) -> None:
        self.text = text


class NoAnswer:
    ok = False
    refused = True
    text = ""
    reason = "every tier was exhausted"


class Ladder:
    """Stands in for `TieredPromptRunner` and records exactly what it was
    asked -- the prompt, the routing request, and how many times."""

    def __init__(self, outcome=None) -> None:
        self._outcome = outcome if outcome is not None else Answer(CORRECT_ANSWER)
        self.calls: list[tuple[str, object, dict]] = []

    def run(self, prompt, request, **kwargs):
        self.calls.append((prompt, request, kwargs))
        return self._outcome


class DeadLadder:
    def __init__(self) -> None:
        self.calls = []

    def run(self, prompt, request, **kwargs):
        self.calls.append((prompt, request, kwargs))
        raise RuntimeError("no API key configured")


def refusal(code: str, reason: str = "because") -> PlanRefusal:
    return PlanRefusal(code=code, reason=reason, detail="")


def submit(text: str, *, refusal_code: str | None = None, ladder=None,
           accepted: bool = False, reason: str = "because",
           previous_objective_id: str | None = None):
    """One founder utterance through the real `_submit_objective()`.

    `ladder` is accepted and ignored. It used to be passed as
    `reasoning_runner=`, and that parameter no longer exists: the
    advisory route was removed from production deliberately, with the
    reason recorded in `_submit_objective` itself -- an unconstrained
    reasoner asked "what should I say about this request?" proposes a next
    action, and a founder was told their CV files were being catalogued by
    a mission that had no plan and no tasks. The signature change is what
    made every test in this module that called it die at once, which is
    why the family had been structurally dead rather than merely red.

    Kept as a parameter so the call sites that document "no provider was
    reached" still read that way; what proves it now is that there is
    nowhere to reach one from.
    """
    outcome = _FakeOutcome(
        accepted=accepted,
        objective_id="obj-1" if accepted else None,
        refusal=refusal(refusal_code, reason) if refusal_code else None,
    )
    status = ExecutionStatus()
    # A referent, when the caller states one: the surface reads it off the
    # status, and it is what separates a follow-up from a question.
    status.objective_id = previous_objective_id
    reply = kd._submit_objective(
        _FakeMissionService(outcome),
        _FakeRuntime(),
        _FakeMissionControl([_FakeObjective(complete=True)], _FakeFounderState()),
        status,
        text,
        timeout_seconds=1.0,
    )
    return reply["reply"], status


# =========================================================================
# The semantic matrix -- classes A through G
# =========================================================================


class TestClassA_Conversational:
    """*"Good morning."* Understood, and not work at all. Never reaches
    planning, so it can never be refused for lack of a capability."""

    def test_a_greeting_is_handled_and_never_escalated(self):
        turn = engine().reply("Good morning", moment=T0)
        assert turn.disposition is Disposition.HANDLED
        assert turn.reply
        assert REFUSAL_SENTENCE not in turn.reply


class TestClassB_CapabilityQuestion:
    """*"What can you do?"* A question ABOUT capability -- answered by the
    Brain, not attempted as work."""

    def test_b_capability_question_is_handled_not_planned(self):
        turn = engine().reply("What can you do?", moment=T0)
        assert turn.disposition is Disposition.HANDLED
        assert turn.reply
        assert REFUSAL_SENTENCE not in turn.reply


class TestClassC_ClearAndDirectlyExecutable:
    """*"Open github.com."* Understood, and a registered capability does
    it. Nothing in this mission may divert that to reasoning."""

    def test_c_accepted_objective_never_reaches_the_advisor(self):
        reply, status = submit("Open github.com", accepted=True)
        assert status.status != FAILED

    def test_c_the_surface_has_no_advisory_door_to_reach(self):
        """Stronger than counting calls on a stub. `_submit_objective`
        takes no reasoning runner at all, so an executable objective
        cannot be diverted to reasoning by any code path -- the guarantee
        is structural rather than observed."""
        parameters = set(inspect.signature(kd._submit_objective).parameters)
        assert "reasoning_runner" not in parameters
        assert not (parameters & {"advisor", "runner", "ladder"})


class TestClassD_And_E_UnderstoodButUnplannable:
    """*"Buy a house for me."* *"Learn trading."* Understood: yes.
    Directly executable: no.

    ## What changed, and why these assertions inverted

    This pair used to be answered by `brain/advisory.py` -- a provider
    asked what to say about a goal it could not plan. Production removed
    that call, and `_submit_objective` records the reason where the call
    used to be: the live CV mission told a founder *"I am taking full
    responsibility for evaluating all your resume files... Shall I start
    cataloging those files now?"* about a mission with no plan, no tasks
    and nothing waiting on an answer. Nothing was cataloguing anything.

    The diagnosis in that comment is the load-bearing part: *an
    unconstrained reasoner asked "what should I say about this request?"
    will propose a next action, because that is what the question
    invites. It cannot promise otherwise, so it is not asked.*

    So the honest outcome for this class is now a sentence composed from
    what the Planner actually reported, and a terminal `FAILED` -- this
    attempt did not succeed and nothing is pending. These tests hold that
    in place, including the part that is uncomfortable: the founder is
    told plainly that no plan could be built, rather than being
    encouraged by a model that cannot do the thing either.

    `brain/advisory.py` still exists and its own unit tests below still
    pass. Nothing in production calls it. That is recorded rather than
    quietly tidied away -- see the sprint ledger.
    """

    GOALS = ("Buy a house for me", "Learn trading")

    @pytest.mark.parametrize("goal", GOALS)
    def test_no_provider_is_asked_what_to_say(self, goal):
        """The property the removal was for. There is no runner parameter
        to hand a provider through, so this cannot regress by someone
        re-adding a call -- they would have to re-add the door first."""
        assert "reasoning_runner" not in inspect.signature(
            kd._submit_objective
        ).parameters
        reply, _ = submit(goal, refusal_code=NO_STEPS)
        assert reply

    @pytest.mark.parametrize("goal", GOALS)
    def test_the_founder_is_told_what_the_planner_actually_reported(self, goal):
        reply, status = submit(goal, refusal_code=NO_STEPS)
        assert status.status == FAILED, (
            "an attempt that produced no plan is not a completed turn"
        )
        assert reply.strip()

    @pytest.mark.parametrize("goal", GOALS)
    def test_the_founder_is_never_coached(self, goal):
        """The founder's own correction, which outlived the module it was
        written for: *"Learn trading" means Kalpavriksha must learn
        trading.* Whatever this path says, it must not tell the founder
        what THEY should go and do."""
        reply, _ = submit(goal, refusal_code=NO_STEPS)
        lowered = reply.lower()
        for coaching in ("you should", "you could start", "why don't you",
                         "i'd suggest you", "you might want to"):
            assert coaching not in lowered, reply


class TestClassF_GenuinelyAmbiguous:
    """*"Create a folder."* A missing parameter -- and a missing parameter
    is not permission to invent one. This is the ONLY class that produces
    a question, and the advisory route must not swallow it."""

    def test_f_clarification_still_reaches_the_founder_verbatim(self):
        """The question comes from the REAL `IntentLayer` now, not from a
        fabricated `CLARIFICATION_REQUIRED` refusal.

        That refusal used to be how the question travelled: the request
        became a mission, the mission was refused, and this function
        unwrapped a question out of a planning failure. ADR-0024 Decision
        1 moved the boundary earlier, so the fabricated refusal is
        unreachable and the question is asked before a mission exists.
        """
        status = ExecutionStatus()
        service = _FakeMissionService(_FakeOutcome(accepted=True, objective_id="never"))
        reply = kd._submit_objective(
            service, _FakeRuntime(),
            _FakeMissionControl([_FakeObjective(complete=True)], _FakeFounderState()),
            status, "Create a folder", timeout_seconds=1.0,
        )["reply"]

        assert reply == "What should the folder be called?"
        assert service.started_with is None, (
            "an under-specified request became a mission -- ADR-0024 §10 "
            "requires MissionService = 0 and Planner = 0 when clarification "
            "is required"
        )


class TestClassG_GenuineFailure:
    """Something actually broke. A malformed plan, a hallucinated
    capability, an empty catalogue. These are NOT 'understood but large',
    and dressing them up as advice would hide a real fault."""

    @pytest.mark.parametrize("code", [MALFORMED, UNKNOWN_CAPABILITY, NO_CAPABILITIES])
    def test_g_real_faults_are_reported_as_faults(self, code):
        """A fault is not a goal that is merely too large. Dressing one up
        as advice would hide a broken system behind encouragement -- which
        is now structurally impossible, since there is no advice path, but
        the terminal state still has to be honest."""
        _, status = submit("Do the thing", refusal_code=code)
        assert status.status == FAILED


# =========================================================================
# Architecture invariants
# =========================================================================


class TestNoParallelBrain:
    """The brief's own prohibitions, checked structurally rather than
    trusted."""

    def test_the_advisor_asks_for_the_same_ai_capability_as_the_planner(self):
        """Not a second provider door. `PLANNING_CAPABILITY` and
        `REASONING_CAPABILITY` must be the identical AI Capability, so no
        provider becomes reachable that planning could not already reach."""
        from master_agent.planner.planner import PLANNING_CAPABILITY

        assert advisory.REASONING_CAPABILITY == PLANNING_CAPABILITY

        ladder = Ladder()
        advise("Learn trading", ladder)
        request = ladder.calls[0][1]
        assert request.capability == PLANNING_CAPABILITY

    def test_the_advisor_is_given_the_planners_own_runner_instance(self):
        """The composition root must hand `brain/advisory.py` the *same*
        `TieredPromptRunner` it hands the Planner -- one ladder, one
        Broker, one decision trail. Read from the source of the one
        function that wires both."""
        source = inspect.getsource(kd._build_mission_pipeline)
        assert "runner=tiered_runner" in source
        # The pipeline returns the same runner it handed the Planner. Checked
        # on the return statement rather than the last token, so adding
        # another element (the founder's mode switch did) does not read as
        # the runner having been dropped.
        returns = [ln for ln in source.splitlines() if ln.strip().startswith("return ")]
        assert any("tiered_runner" in ln for ln in returns), (
            "the pipeline no longer returns the runner it gave the Planner"
        )

    def test_no_second_runner_is_constructed_anywhere_in_the_brain(self):
        source = inspect.getsource(advisory)
        for forbidden in ("TieredPromptRunner(", "PromptExecutor(", "CapabilityBroker(",
                          "requests.", "httpx", "openai", "openrouter"):
            assert forbidden not in source, (
                f"{forbidden!r} in brain/advisory.py -- that is a parallel "
                "provider path, not the Brain's existing door"
            )

    def test_no_goal_phrases_are_hardcoded(self):
        """The acceptance probes are probes, not implementation. A goal
        this codebase has never seen must travel the identical path.

        Every docstring is stripped before the check, because the module
        docstring legitimately *discusses* the probes -- what must not
        exist is executable code, or a prompt, that recognises them.
        """
        import ast

        tree = ast.parse(inspect.getsource(advisory))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.ClassDef)) and ast.get_docstring(node):
                node.body = node.body[1:]
        body = ast.unparse(tree).lower()

        for probe in ("learn trading", "buy a house", "trading", "house",
                      "portuguese", "invest"):
            assert probe not in body, (
                f"{probe!r} appears in executable code or a prompt -- a subject "
                "was special-cased instead of the shape being generalised"
            )

    def test_no_goal_phrases_are_hardcoded_in_the_routing_decision_either(self):
        """Comments naming the probes are fine -- they explain the change.
        `ast.unparse` drops comments, so what is checked is the code that
        actually runs."""
        import ast
        import textwrap

        code = ast.unparse(
            ast.parse(textwrap.dedent(inspect.getsource(kd._submit_objective)))
        ).lower()
        for probe in ("learn trading", "buy a house", "trading", "house"):
            assert probe not in code, (
                f"{probe!r} is branched on in the routing decision -- the "
                "probes were special-cased instead of generalised"
            )

    def test_an_unseen_goal_takes_the_identical_path(self):
        """The acceptance probes are probes, not implementation. A goal
        this codebase has never seen reaches the same outcome as the ones
        it has -- which is the whole point of not special-casing them."""
        reply, status = submit(
            "Get me fluent in Portuguese before the Lisbon trip",
            refusal_code=NO_STEPS,
        )
        assert status.status == FAILED
        assert reply.strip()

    def test_exactly_one_refusal_code_routes_to_reasoning(self):
        """Stated as a whitelist in the source, so widening it is a
        deliberate edit rather than an accident."""
        source = inspect.getsource(kd._submit_objective)
        assert "== NO_STEPS" in source
        assert source.count("advise(") == 1

    def test_the_advisor_never_raises_and_never_returns_empty(self):
        for runner in (Ladder(NoAnswer()), DeadLadder(), Ladder(Answer("")), Ladder(None)):
            assert advise("anything at all", runner)
        assert advise("", Ladder()) == UNREACHABLE

    def test_the_prompt_forbids_the_refusal_wording_before_it_arrives(self):
        """The acceptance condition is stated to the provider AND checked
        on the way back, not hoped for."""
        prompt = advisory._prompt("Learn trading")
        assert "Never say you cannot do it" in prompt
        expectation = advisory._expectation()
        assert expectation is not None


class TestNoNewTaxonomy:
    def test_the_conversation_engines_intent_vocabulary_is_unchanged(self):
        from master_agent.conversation_engine.intent import Intent

        assert {member.value for member in Intent} == {
            "greeting", "continuation", "status_query", "activity_query",
            "priority_query", "capability_query", "build_request", "unknown",
        }

    def test_no_new_planner_refusal_code_was_invented(self):
        from master_agent import planner as planner_pkg

        assert not hasattr(planner_pkg, "NOT_EXECUTABLE")
        assert not hasattr(planner_pkg, "ADVISORY")


# =========================================================================
# Whose goal is it -- the founder's correction
# =========================================================================


class TestKalpavrikshaIsTheOneWhoLearns:
    """*"Learn trading means Kalpavriksha itself must learn trading. It
    does not mean 'teach the Founder trading' or 'give the Founder advice
    about how to learn trading.'"*

    The first version of this module read the instruction as a request
    for advice and answered by coaching the founder. It was fluent and it
    was wrong: the founder did not ask to learn anything, they told this
    system to learn. These tests hold the subject in place.
    """

    def test_a_coaching_answer_cannot_reach_the_founder_at_all(self):
        """The strongest form this can now take. The coaching answer
        cannot be produced by the surface, because the surface asks no
        provider what to say -- the register guard below still protects
        `advise()` itself for any caller that returns."""
        reply, _ = submit("Learn trading", refusal_code=NO_STEPS)
        assert reply != COACHING_ANSWER
        assert "you should" not in reply.lower()

    def test_the_register_guard_still_rejects_coaching(self):
        """`advise()` is no longer wired into the surface, and its guard is
        still the thing that would hold if it were. Tested directly rather
        than through a route that no longer passes through it."""
        assert advise("Learn trading", Ladder(Answer(COACHING_ANSWER))) == UNREACHABLE
        assert advise("Learn trading", Ladder(Answer(CORRECT_ANSWER))) == CORRECT_ANSWER

    @pytest.mark.parametrize("marker", advisory.COACHING_MARKERS)
    def test_every_coaching_marker_is_actually_enforced(self, marker):
        """Each marker is checked individually, so a list entry cannot rot
        into decoration that nothing reads."""
        answer = (
            f"Understood, that matters to you. {marker} settle which market "
            "is worth following, and I'll take it from there once that's "
            "clear enough to act on."
        )
        assert advise("Learn trading", Ladder(Answer(answer))) == UNREACHABLE

    def test_the_prompt_says_the_instruction_is_about_this_system(self):
        prompt = advisory._prompt("Learn trading")
        assert "It is NOT a request for advice" in prompt
        assert "the founder is telling YOU to acquire that skill" in prompt
        assert "Never tell the founder to do anything." in prompt

    def test_the_expectation_states_the_register_before_the_answer_arrives(self):
        """Stated to the provider up front, not only filtered afterwards --
        the same discipline every other expectation in this codebase
        follows."""
        for marker in advisory.COACHING_MARKERS:
            assert marker in advisory.REFUSAL_MARKERS + advisory.COACHING_MARKERS
        assert advisory._expectation() is not None

    def test_the_guard_holds_for_a_runner_that_ignores_the_expectation(self):
        """`expected=` is honoured by the executor. This asserts the
        guarantee does not DEPEND on that: a bare runner handing back
        advice is still stopped."""
        class IgnoresExpectations:
            def run(self, prompt, request, **kwargs):
                return Answer(COACHING_ANSWER)

        assert advise("Learn trading", IgnoresExpectations()) == UNREACHABLE

    def test_the_correction_is_recorded_in_the_source(self):
        """A founder decision that reverses an implementation must be
        readable where the implementation lives, or the next reader
        reintroduces it."""
        # Whitespace-normalised: the correction is prose and wraps, so a
        # contiguous-substring check would pass or fail on line length.
        doc = " ".join((advisory.__doc__ or "").split())
        assert "Kalpavriksha itself must learn trading" in doc
        assert "teach the Founder trading" in doc

    def test_the_unreachable_fallback_is_not_advice_either(self):
        for marker in advisory.COACHING_MARKERS:
            assert marker.lower() not in UNREACHABLE.lower()
