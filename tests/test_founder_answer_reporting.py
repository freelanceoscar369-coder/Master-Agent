"""A founder who asks a question is told the answer.

## The defect

`FounderState.result` is the LAST COMPLETED task's result. That is right
for a single-step mission -- a folder mission's last output is the path,
which is what was asked -- and wrong for any mission that tidies up after
itself. The dictated browser workflow ends in `CloseBrowserSession`, so
the objective

    ... observe the page and tell me the current text shown by #state,
    then close the browser session.

would have reported the close. `_describe_result` does not stringify a
raw structure at the founder any more, so what they would actually read
is "Done -- <their own objective repeated back>". The question goes
unanswered while every step succeeds.

## The fix, and its two guard rails

A Step may name the field of its own observation that answers the
question (`Step.answers_founder`, a dot-path). Two properties keep that
reporting rather than judging:

* the value comes from **Evidence** -- an independent fresh observation --
  not from the task's own `result`, so the founder is told what was
  verified rather than what the Executive claimed;
* a designated task with **no** Evidence yields nothing, so absence falls
  back to ordinary behaviour instead of quietly promoting an unverified
  claim to "the answer".

Nothing composes prose. Selecting a named field is projection, and
projection is deterministic -- the moment this held a sentence, something
would have to write it, which is authority the reporting path does not
have.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from master_agent.mission_control.mission_control import MissionControl
from master_agent.mission_control.tasks import Objective, Task, TaskState

NOW = datetime(2026, 8, 27, 9, 0, tzinfo=UTC)


def completed(task_id: str, capability: str, result, *, at, evidence=None,
              answers: str = "") -> Task:
    return Task(
        capability=capability,
        task_id=task_id,
        state=TaskState.COMPLETED,
        result=result,
        evidence=evidence,
        answers_founder=answers,
        ended_at=at,
    )


def observation_evidence(**observation) -> dict:
    """Evidence shaped as Verification actually stores it -- the whole
    record, with the fresh observation under `observation`."""
    return {"evidence_id": "e-1", "verdict": "matched", "observation": observation}


def state_for(*tasks) -> object:
    control = MissionControl()
    control.submit_objective(
        Objective(description="tell me the text shown by #state", tasks=list(tasks))
    )
    return control.founder_state()


class TestTheDesignatedAnswerIsReported:
    def test_the_observed_value_is_reported_not_the_cleanup_step(self):
        answer = completed(
            "observe", "Browser.ObserveBrowser", {"claimed": "ignore me"},
            at=NOW,
            evidence=observation_evidence(
                url="http://127.0.0.1:8731/acceptance.html",
                title="Kalpavriksha Acceptance",
                elements=[{"selector": "#state", "is_visible": True,
                           "text": "accepted", "tag_name": "SPAN"}],
            ),
            answers="elements.0.text",
        )
        close = completed(
            "close", "Browser.CloseBrowserSession", {"closed": True},
            at=NOW + timedelta(seconds=1),
        )
        assert state_for(answer, close).answer == "accepted"

    def test_the_value_comes_from_evidence_not_from_the_executives_claim(self):
        """The Action reported one thing and an independent observation
        saw another. The founder is told what was observed -- that
        difference is the entire reason Evidence exists."""
        task = completed(
            "observe", "Browser.ObserveBrowser",
            {"elements": [{"selector": "#state", "text": "the action's own claim"}]},
            at=NOW,
            evidence=observation_evidence(
                elements=[{"selector": "#state", "text": "what was actually there"}]
            ),
            answers="elements.0.text",
        )
        assert state_for(task).answer == "what was actually there"

    def test_a_designated_task_with_no_evidence_answers_nothing(self):
        """Nothing independently observed the value, so there is no
        verified answer -- and an unverified claim is not promoted to one
        merely because a step designated it."""
        answer = completed(
            "observe", "Browser.ObserveBrowser",
            {"elements": [{"selector": "#state", "text": "unverified"}]},
            at=NOW, evidence=None, answers="elements.0.text",
        )
        close = completed(
            "close", "Browser.CloseBrowserSession", {"closed": True},
            at=NOW + timedelta(seconds=1),
        )
        state = state_for(answer, close)
        assert state.answer is None
        assert state.result == {"closed": True}

    def test_a_designated_path_that_is_not_there_answers_nothing(self):
        """A selector matching nothing still produces an entry, so this is
        the rarer case of a path that does not resolve at all. Falling back
        beats reporting `None` as though it were the page's text."""
        answer = completed(
            "observe", "Browser.ObserveBrowser", "step result",
            at=NOW,
            evidence=observation_evidence(url="http://x.test", title="x", elements=[]),
            answers="elements.0.text",
        )
        state = state_for(answer)
        assert state.answer is None
        assert state.result == "step result"

    def test_a_plan_that_designates_nothing_behaves_exactly_as_before(self):
        first = completed("a", "Filesystem.CreateFolder", "/Desktop/KV", at=NOW)
        second = completed(
            "b", "Filesystem.WriteFile", "/Desktop/KV/notes.txt",
            at=NOW + timedelta(seconds=1),
        )
        state = state_for(first, second)
        assert state.answer is None
        assert state.result == "/Desktop/KV/notes.txt"

    def test_an_unfinished_mission_still_reports_nothing(self):
        state = state_for(
            Task(capability="Browser.Navigate", task_id="a", state=TaskState.RUNNING)
        )
        assert state.result is None and state.answer is None


class TestTheFounderReadsIt:
    """The projection has to survive the sentence-building step too, or it
    is a value nobody sees."""

    def test_the_answer_is_spoken_as_it_was_observed(self):
        from kalpavriksha_desktop import _describe_result

        assert _describe_result("accepted", "tell me the text shown by #state") == (
            "accepted"
        )

    def test_without_the_projection_the_founder_reads_a_restatement(self):
        """What the failing run would have said. Kept as a test rather
        than a comment so the improvement cannot quietly regress into
        this."""
        from kalpavriksha_desktop import _describe_result

        assert _describe_result({"closed": True}, "tell me the text shown by #state") == (
            "Done — tell me the text shown by #state."
        )


class TestTheDesignationTravels:
    def test_a_step_carries_it_onto_its_task(self):
        from master_agent.missions.translation import task_from_step
        from master_agent.planner.plan import Step

        task = task_from_step(Step(
            step_id="observe", capability="Browser.ObserveBrowser",
            payload={"session_id": "kv-1", "selectors": ["#state"]},
            answers_founder="elements.0.text",
        ))
        assert task.answers_founder == "elements.0.text"
        assert task.as_dict()["answers_founder"] == "elements.0.text"

    def test_almost_every_step_designates_nothing(self):
        from master_agent.missions.translation import task_from_step
        from master_agent.planner.plan import Step

        task = task_from_step(Step(
            step_id="close", capability="Browser.CloseBrowserSession",
            payload={"session_id": "kv-1"},
        ))
        assert task.answers_founder == ""

    def test_a_model_cannot_designate_an_answer(self):
        """The deterministic lane knows what the founder dictated. A
        planning prompt does not mention this field and the plan parser
        does not read it, so a model cannot claim a step answers a
        question it merely guessed the shape of."""
        from master_agent.planner import parsing, prompting

        source = "".join(
            open(module.__file__, encoding="utf-8").read()
            for module in (parsing, prompting)
        )
        assert "answers_founder" not in source
