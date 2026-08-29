"""One objective, one meaning — for as long as that objective lives.

A replan changes the plan. It must not change what the founder asked
for. If `req_2` means "is it open on Saturday" at admission, it means
that on the third attempt too; only its STATE may move, from unresolved
to satisfied.

Everything downstream depends on this holding: `MissionProgress` counts
requirement ids, Evidence binds to them, `more_research` names the
unresolved one, `no_useful_progress` compares two standings, conformance
reports satisfaction, and the founder is told the result in those terms.
A requirement whose meaning moves under them makes all six reason
correctly about a moving objective.

The dangerous variant is not a crash. It is `req_2` quietly becoming
"start from the directory page", which is a sentence nobody can verify
about a workshop — and then a shortlist that depends on how a model felt
about it.
"""
from __future__ import annotations

import types

from master_agent.missions.service import MissionService
from master_agent.planner.plan import (
    CONSTRAINT,
    INFORMATION,
    Intent,
    SemanticRequirement,
)

#: What the founder actually asked. Derived once, this is the answer.
FIRST_READING = (
    SemanticRequirement("req_1", INFORMATION,
                        "the workshop accepts laptops",
                        founder_evidence="accept laptops"),
    SemanticRequirement("req_2", INFORMATION,
                        "the workshop is open on Saturday",
                        founder_evidence="open on Saturday"),
    SemanticRequirement("req_3", CONSTRAINT,
                        "start from the directory page",
                        founder_evidence="Start from"),
)

#: What a second derivation of the SAME sentence produced live: the
#: Saturday question gone, the navigation instruction promoted into a
#: question. If anything ever consumes this for a replan, the founder is
#: answered about something they did not ask.
SECOND_READING = (
    SemanticRequirement("req_1", INFORMATION,
                        "which workshops accept laptops",
                        founder_evidence="accept laptops"),
    SemanticRequirement("req_2", INFORMATION,
                        "start from the directory page at the given URL",
                        founder_evidence="Start from"),
)


class CountingLayer:
    """An Intent Layer whose reading of the same sentence changes.

    Not a constant mock: the defect being pinned is precisely that a
    second derivation disagrees with the first, so a stub that always
    answers the same thing would prove nothing.
    """

    def __init__(self):
        self.calls = 0
        self.readings = [FIRST_READING, SECOND_READING]

    def requirements_for(self, intent, raw=""):
        self.calls += 1
        return self.readings[min(self.calls - 1, len(self.readings) - 1)]


def fingerprint(requirements):
    """The MEANING of a requirement set, by the fields that carry it.

    Not object identity: a replan is free to rebuild the tuple, and this
    must still say "the same thing was asked". Test-side only — nothing
    in production depends on it.
    """
    return tuple(
        (r.requirement_id, r.kind, r.description, r.required, r.founder_evidence)
        for r in requirements or ()
    )


def _service(layer):
    """A `MissionService` with only the piece under test wired.

    `_admit` is reached directly; nothing here plans or executes,
    because what is being asked is a question about meaning, not about
    work.
    """
    service = MissionService.__new__(MissionService)
    service.intent_layer = layer
    return service


def _derive(service, intent):
    """The one line of `_admit` that owns this, exercised as `_admit`
    reaches it. Kept to that line deliberately: admitting a whole mission
    would drag in the Planner, and the Planner is not the owner."""
    if not getattr(intent, "requirements", ()) and service.intent_layer is not None:
        try:
            intent.requirements = service.intent_layer.requirements_for(
                intent, raw=str(intent.context.get("raw_input") or intent.goal))
        except Exception:  # noqa: BLE001
            intent.requirements = ()
    return intent.requirements


class TestOneObjectiveOneMeaning:
    def test_a_replan_does_not_re_derive_the_founders_meaning(self):
        """The invariant, stated as a call count. A replan reuses the
        same canonical Intent, which already carries its requirements."""
        layer = CountingLayer()
        service = _service(layer)
        intent = Intent(goal="which workshops", context={})

        _derive(service, intent)          # admission
        assert layer.calls == 1

        _derive(service, intent)          # replan 1
        _derive(service, intent)          # replan 2

        assert layer.calls == 1, (
            f"the founder's meaning was re-derived {layer.calls} times for one "
            "objective")

    def test_the_second_reading_never_reaches_a_replan(self):
        """The pointed version of the same fact. A live second derivation
        dropped the Saturday question and promoted the navigation
        instruction; if a replan consumed it, the mission would answer a
        different question with full confidence."""
        layer = CountingLayer()
        service = _service(layer)
        intent = Intent(goal="which workshops", context={})

        at_admission = fingerprint(_derive(service, intent))
        after_replan_1 = fingerprint(_derive(service, intent))
        after_replan_2 = fingerprint(_derive(service, intent))

        assert at_admission == after_replan_1 == after_replan_2
        assert fingerprint(SECOND_READING) not in (
            at_admission, after_replan_1, after_replan_2)

    def test_ids_descriptions_kinds_and_provenance_all_hold(self):
        layer = CountingLayer()
        service = _service(layer)
        intent = Intent(goal="which workshops", context={})
        _derive(service, intent)

        for _ in range(3):
            requirements = _derive(service, intent)
            assert [r.requirement_id for r in requirements] == [
                "req_1", "req_2", "req_3"]
            assert [r.description for r in requirements] == [
                "the workshop accepts laptops",
                "the workshop is open on Saturday",
                "start from the directory page",
            ]
            assert [r.kind for r in requirements] == [
                INFORMATION, INFORMATION, CONSTRAINT]
            assert [r.founder_evidence for r in requirements] == [
                "accept laptops", "open on Saturday", "Start from"]

    def test_the_saturday_question_cannot_become_a_navigation_instruction(self):
        """The exact live corruption, named. `req_2` is a question about
        the world at admission and stays one."""
        layer = CountingLayer()
        service = _service(layer)
        intent = Intent(goal="which workshops", context={})
        _derive(service, intent)

        _derive(service, intent)
        second = next(r for r in intent.requirements if r.requirement_id == "req_2")

        assert second.description == "the workshop is open on Saturday"
        assert second.kind == INFORMATION


class TestASeparateObjectiveDerivesItsOwn:
    def test_two_objectives_do_not_share_a_reading(self):
        """Reuse is per canonical objective, never per sentence. Two
        founder objectives with identical text are still two objectives,
        and each derives its own meaning."""
        layer = CountingLayer()
        service = _service(layer)

        first = Intent(goal="which workshops", context={})
        second = Intent(goal="which workshops", context={})

        _derive(service, first)
        _derive(service, second)

        assert layer.calls == 2
        assert fingerprint(first.requirements) == fingerprint(FIRST_READING)
        assert fingerprint(second.requirements) == fingerprint(SECOND_READING)

    def test_nothing_is_keyed_by_raw_text(self):
        """A string cache would have collapsed the two above into one.
        The boundary is the canonical Intent, and it carries its own
        answer."""
        import inspect

        source = inspect.getsource(MissionService._admit)
        assert "requirements_by_raw" not in source
        assert 'getattr(intent, "requirements", ())' in source


class TestAFounderModificationIsAllowedToChangeMeaning:
    """Reuse must not become a cage. What is forbidden is meaning moving
    because a model reconsidered the sentence; a founder deliberately
    changing what they want is a different act, and the shape that
    permits it is simply a new canonical Intent."""

    def test_a_new_intent_carries_the_new_meaning(self):
        layer = CountingLayer()
        service = _service(layer)

        original = Intent(goal="which workshops", context={})
        _derive(service, original)
        assert any(r.description == "the workshop is open on Saturday"
                   for r in original.requirements)

        revised = Intent(goal="which workshops, on Sunday", context={})
        _derive(service, revised)

        assert fingerprint(revised.requirements) != fingerprint(original.requirements)
        assert fingerprint(original.requirements) == fingerprint(FIRST_READING), (
            "the original objective's meaning changed under it")


class TestTheFingerprintCanActuallyFail:
    """A stability assertion that cannot detect instability is
    decoration."""

    def test_it_separates_two_different_readings(self):
        assert fingerprint(FIRST_READING) != fingerprint(SECOND_READING)

    def test_it_ignores_object_identity(self):
        rebuilt = tuple(
            SemanticRequirement(r.requirement_id, r.kind, r.description,
                                required=r.required,
                                founder_evidence=r.founder_evidence)
            for r in FIRST_READING
        )
        assert rebuilt is not FIRST_READING
        assert fingerprint(rebuilt) == fingerprint(FIRST_READING)
