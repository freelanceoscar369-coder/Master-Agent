"""A payload can agree with itself and still be wrong about the founder.

## The failure this file exists to make impossible

Twice, live, this sequence completed and reported success:

    founder says      "d drive in Onkar folder"
    Brain resolves    location = d_drive          <- half the sentence
    requirement       "location = d_drive"        <- written FROM the resolve
    execution         creates D:\\Rudra
    Verification      MATCHED (the folder is really there)
    conformance       SATISFIED
    founder is told   "This did what you asked for."

Every arrow is sound. The chain is internally consistent from end to end.
It is also wrong, because the requirement and the execution were both
derived from the same misreading, so the comparison at the end could only
ever agree with itself. Consistency with an interpretation is not
correspondence with meaning, and a system that cannot tell those apart
will keep certifying its own mistakes.

The matrix below is therefore not a parser test. Every case has a
RESOLVED PAYLOAD THAT IS INTERNALLY CONSISTENT and a founder meaning it
does not carry, and every case asserts the system declines to certify it.

## Why the assertions look like this

Two properties do the work, and neither is a phrase table:

1.  Nothing may be settled while a word of the founder's reply is
    unexplained -- by a value that was resolved or by pure grammar.
    Whoever resolved it. A model returning a legitimate vocabulary value
    is not evidence that the value is the whole answer.

2.  An unsettled interpretation may not execute and may not be reported
    as satisfied. `UNKNOWN` is the honest state and is never rounded up.
"""
from __future__ import annotations

import json

import pytest

from master_agent.brain.conformance import (
    NOT_SATISFIED,
    SATISFIED,
    UNKNOWN,
    assess,
)
from master_agent.brain.intent import ClarificationQuestion, IntentLayer
from master_agent.planner.plan import (
    CONSTRAINT,
    KNOWN,
    UNCERTAIN,
    SemanticRequirement,
)

PLACES = ("d_drive", "desktop", "documents", "downloads")
FIELDS = ("folder_name", "location", "parent")


class Reasoner:
    """A model that returns exactly what the real one returned."""

    def __init__(self, reply: str = "") -> None:
        self.reply = reply

    def run(self, prompt, request, **kwargs):
        class Outcome:
            ok = True
            text = self.reply

        return Outcome()


def where(name: str = "Rudra") -> ClarificationQuestion:
    return ClarificationQuestion(
        question=f"Where should I create the {name} folder?",
        key="location",
        gathering=FIELDS,
    )


def settle(
    reply: str,
    *,
    returns: dict | None = None,
    ambiguous: bool = False,
    name: str = "Rudra",
):
    """One clarification turn. Returns (payload or None, question or None).

    `returns` is what the model reports for the named fields, in the
    envelope the reasoning door actually validates. Getting that envelope
    wrong is not a harmless test detail: a malformed reply is rejected
    before any semantic check runs, so the assertions below would pass
    without the guard they exist to prove. They did, briefly, until this
    was corrected.
    """
    said = None
    if returns is not None or ambiguous:
        said = json.dumps({"fields": dict(returns or {}), "ambiguous": ambiguous})
    layer = IntentLayer(
        reasoner=Reasoner(said) if said is not None else None,
        vocabularies={"location": PLACES},
    )
    result = layer.clarify(
        "create a folder", reply, where(name),
        supplied={"folder_name": name}, evidence={},
    )
    if result.needs_clarification:
        return None, result.clarification.question
    return dict(result.intent.payload or {}), None


# =====================================================================
# THE MATRIX -- resolved payloads that are consistent and wrong
# =====================================================================


class TestAConsistentPayloadIsNotAFaithfulOne:
    """Every reply here names something NARROWER than any one vocabulary
    value. Returning the nearest value produces a payload that validates
    perfectly and discards the part that mattered."""

    @pytest.mark.parametrize("reply, nearest, discarded", [
        # The live regression, verbatim, with the model's real answer.
        ("d drive in Onkar folder", "d_drive", "Onkar"),
        ("Desktop inside Onkar folder", "desktop", "Onkar"),
        ("Documents under Project Alpha", "documents", "Project Alpha"),
        ("downloads, in the archive folder", "downloads", "archive"),
    ])
    def test_a_nearest_value_that_drops_a_folder_is_refused(
        self, reply, nearest, discarded
    ):
        payload, question = settle(reply, returns={"location": nearest})
        assert payload is None, (
            f"settled on {payload} while {discarded!r} went unread -- this is "
            "the shape that created D:\\Rudra and called it success"
        )
        assert question

    def test_the_model_returning_a_legal_value_is_not_a_constraint(self):
        """Pinned exactly. The prompt asks a model not to pick the
        closest value when the reply names something narrower. Asked "d
        drive in onkar folder", the production model returned

            {"location": "d_drive"}

        and because `d_drive` is a legitimate member of the capability's
        own vocabulary, validation passed and a folder was created on the
        wrong path for the second time in one evening.

        Prompt compliance is not a constraint. Accounting for the whole
        reply is."""
        payload, question = settle(
            "d drive in onkar folder", returns={"location": "d_drive"}
        )
        assert payload is None
        assert question

    @pytest.mark.parametrize("reply", [
        "use the second folder",
        "same place as the report from last week",
        "the usual spot",
    ])
    def test_a_referent_with_nothing_to_refer_to_never_executes(self, reply):
        payload, question = settle(reply, ambiguous=True)
        assert payload is None
        assert question

    def test_the_harness_can_produce_a_reply_that_is_accepted(self):
        """The guard must not be a refusal machine -- and a stub whose
        output is rejected before the guard runs proves nothing about the
        guard. This is the control: same envelope, a reply that IS fully
        accounted for, and the founder is not asked twice."""
        payload, question = settle("on my desktop", returns={"location": "desktop"})
        assert question is None
        assert payload["location"] == "desktop"

    def test_a_nested_destination_resolves_once_it_is_actually_read(self):
        """`CreateFolder` already expresses this: `name` is a relative
        path joined onto the location's base directory. Read the whole
        sentence and the payload becomes faithful rather than refused."""
        payload, question = settle(
            "d drive in Onkar folder",
            returns={"location": "d_drive", "parent": "Onkar"},
        )
        assert question is None
        assert payload["location"] == "d_drive"
        assert payload["name"] == "Onkar/Rudra"


# =====================================================================
# The two sides of the comparison must come from different places
# =====================================================================


class TestConformanceMayNotCompareAReadingWithItself:
    class Task:
        def __init__(self, task_id, covers, verdict):
            self.task_id = task_id
            self.covers = covers
            self.evidence = {"verdict": verdict}

    def test_an_unsettled_interpretation_is_never_satisfied(self):
        """Execution proved something. It proved it about a reading
        nobody confirmed, so the mission's outcome is UNKNOWN however
        cleanly the step verified."""
        requirement = SemanticRequirement(
            "req_2", CONSTRAINT, "location = d_drive",
            founder_evidence="d drive in Onkar folder",
            interpretation=UNCERTAIN,
        )
        outcome = assess([requirement], [self.Task("t1", ("req_2",), "matched")])
        assert outcome.state == UNKNOWN
        assert outcome.state != SATISFIED

    def test_a_settled_interpretation_with_evidence_is_satisfied(self):
        requirement = SemanticRequirement(
            "req_2", CONSTRAINT, "location = desktop",
            founder_evidence="on my desktop", interpretation=KNOWN,
        )
        outcome = assess([requirement], [self.Task("t1", ("req_2",), "matched")])
        assert outcome.state == SATISFIED

    def test_a_contradicted_requirement_is_still_not_satisfied(self):
        requirement = SemanticRequirement(
            "req_2", CONSTRAINT, "location = desktop", interpretation=KNOWN,
        )
        outcome = assess([requirement], [self.Task("t1", ("req_2",), "not_matched")])
        assert outcome.state == NOT_SATISFIED

    def test_the_founders_words_survive_beside_the_interpretation(self):
        """Two artefacts, not one. If a requirement carried only
        `description`, an audit asking "does this correspond to what they
        said?" would have nothing to compare against but the answer."""
        requirement = SemanticRequirement(
            "req_2", CONSTRAINT, "location = d_drive",
            founder_evidence="d drive in Onkar folder",
        )
        stored = requirement.as_dict()
        assert stored["description"] == "location = d_drive"
        assert stored["founder_evidence"] == "d drive in Onkar folder"
        assert stored["description"] != stored["founder_evidence"]

    def test_interpretation_defaults_to_known_but_the_state_is_closed(self):
        from master_agent.planner.plan import INTERPRETATION_STATES

        assert SemanticRequirement("r", CONSTRAINT, "x").interpretation == KNOWN
        assert set(INTERPRETATION_STATES) == {KNOWN, UNCERTAIN}
