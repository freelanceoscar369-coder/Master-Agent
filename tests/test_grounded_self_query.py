"""Questions about Kalpavriksha, answered from Kalpavriksha's records.

## The defect this closes

Asked *"What can you do right now?"*, the surface built a
`Reasoning.Transform` mission with the last mission's contents attached
as grounding. That action defaults to `sensitive=True` — correctly,
because its context is normally private founder material — so the Broker
looked for a PRIVATE-locality provider, found none running, and the
question failed outright:

    11 provider(s) considered, none eligible: excluded by the request;
    not available; sensitive work may not go to a third party

Every layer behaved correctly. The mistake was upstream of all of them:
**none of these questions needed a provider.** What this machine can do,
which providers are usable, why a capability was chosen, whether the last
mission satisfied the request — all four are already recorded, and
reading a record is not reasoning.

Found by rehearsing the founder's own questions before asking them, which
is the only reason it is fixed rather than discovered live.
"""
from __future__ import annotations

import pytest

from master_agent.brain import self_query
from master_agent.brain.conformance import assess
from master_agent.planner.plan import (
    DELIVERABLE,
    EFFECT,
    INFORMATION,
    SemanticRequirement,
)


class Entry:
    def __init__(self, canonical_id: str, domain: str) -> None:
        self.canonical_id = canonical_id
        self.domain = domain


class Profile:
    def __init__(self, provider_id: str, available: bool) -> None:
        self.provider_id = provider_id
        self.available = available


class Step:
    def __init__(self, capability, verdict="", covers=(), reason=""):
        self.capability = capability
        self.verdict = verdict
        self.covers = covers
        self.selection_reason = reason
        self.task_id = capability
        self.evidence = {"verdict": verdict} if verdict else None


class Record:
    def __init__(self, objective, steps=(), requirements=()):
        self.objective = objective
        self.steps = list(steps)
        self.requirements = list(requirements)


# =====================================================================
# What can you do right now
# =====================================================================


class TestCapabilityAnswer:
    ENTRIES = [
        Entry("Filesystem.CreateFolder", "filesystem"),
        Entry("Filesystem.WriteFile", "filesystem"),
        Entry("Browser.Navigate", "browser"),
    ]

    def test_it_counts_what_is_actually_registered(self):
        answer = self_query.answer(self_query.CAPABILITIES, capabilities=self.ENTRIES)
        assert "3 registered capabilities" in answer
        assert "2 areas" in answer

    def test_it_answers_by_area_not_by_primitive_name(self):
        """A founder asking what it can do wants the shape of its reach.
        Forty-eight identifiers answer a different question."""
        answer = self_query.answer(self_query.CAPABILITIES, capabilities=self.ENTRIES)
        assert "filesystem" in answer and "browser" in answer
        assert "Filesystem.CreateFolder" not in answer

    def test_an_empty_registry_answers_nothing_rather_than_guessing(self):
        assert self_query.answer(self_query.CAPABILITIES, capabilities=[]) == ""


# =====================================================================
# Which providers are usable
# =====================================================================


class TestProviderAnswer:
    PROFILES = [
        Profile("gemini.api", True),
        Profile("openrouter.api", True),
        Profile("chatgpt-desktop", False),
    ]

    def test_known_is_distinguished_from_usable(self):
        """A provider can be registered, configured and completely unable
        to run. Naming it as available would be a promise this machine
        cannot keep."""
        answer = self_query.answer(self_query.PROVIDERS, providers=self.PROFILES)
        assert "3 reasoning providers" in answer
        assert "2 can actually be used" in answer
        assert "gemini.api" in answer
        assert "chatgpt-desktop" in answer
        assert "known but not usable" in answer

    def test_it_does_not_claim_to_choose_between_them(self):
        answer = self_query.answer(self_query.PROVIDERS, providers=self.PROFILES)
        assert "Broker" in answer


# =====================================================================
# Why that capability
# =====================================================================


class TestRationaleAnswer:
    def test_it_reads_the_reason_recorded_at_planning_time(self):
        record = Record(
            "create a folder called Research on the Desktop",
            [Step("Filesystem.CreateFolder", "matched", ("req_1",),
                  "Filesystem.CreateFolder was selected for req_1 because …")],
        )
        answer = self_query.answer(self_query.PLAN_RATIONALE, record=record)
        assert "Filesystem.CreateFolder" in answer
        assert "req_1" in answer
        assert "recorded when the plan was made" in answer

    def test_a_record_with_no_recorded_reason_answers_nothing(self):
        """Rather than inventing one after the fact — a plausible reason
        is indistinguishable from the real one exactly when it is
        wrong."""
        record = Record("something old", [Step("Filesystem.CreateFolder", "matched")])
        assert self_query.answer(self_query.PLAN_RATIONALE, record=record) == ""


# =====================================================================
# Did it satisfy what I asked
# =====================================================================


class TestOutcomeAnswer:
    REQUIREMENTS = (
        SemanticRequirement("req_1", INFORMATION, "text is produced"),
        SemanticRequirement("req_2", DELIVERABLE, "the file holds that text"),
    )

    def outcome_for(self, *verdicts):
        steps = [
            Step(f"step_{i}", verdict, (f"req_{i}",))
            for i, verdict in enumerate(verdicts, start=1)
        ]
        record = Record("do the thing", steps, self.REQUIREMENTS)
        return self_query.answer(
            self_query.OUTCOME, record=record,
            conformance=assess(self.REQUIREMENTS, steps),
        )

    def test_all_verified_answers_yes(self):
        answer = self.outcome_for("matched", "matched")
        assert answer.startswith("Yes.")
        assert "verified" in answer

    def test_a_contradicted_requirement_answers_no(self):
        answer = self.outcome_for("not_matched", "matched")
        assert answer.startswith("No.")
        assert "NOT met" in answer

    def test_missing_evidence_is_never_rounded_up_to_yes(self):
        """UNKNOWN is a real answer. A mission the machine cannot vouch
        for is one it says so about."""
        answer = self.outcome_for("matched", "")
        assert "can't say for certain" in answer
        assert "not confirmed" in answer
        assert not answer.startswith("Yes")

    def test_it_says_the_evidence_was_independent(self):
        answer = self.outcome_for("matched", "matched")
        assert "looking at reality again" in answer

    def test_no_conformance_answers_nothing(self):
        assert self_query.answer(self_query.OUTCOME, record=Record("x")) == ""


# =====================================================================
# The boundaries
# =====================================================================


class TestItAnswersOnlyWhatTheRecordsAnswer:
    def test_an_unrecognised_subject_answers_nothing(self):
        assert self_query.answer(self_query.OTHER) == ""
        assert self_query.answer("something_invented") == ""

    def test_the_subject_vocabulary_is_closed(self):
        assert set(self_query.QUESTION_SUBJECTS) == {
            "capabilities", "providers", "plan_rationale", "outcome", "other",
        }

    def test_it_asks_no_provider(self):
        """Reading a record is not reasoning. This module exists so these
        questions never reach a provider at all."""
        import inspect

        source = inspect.getsource(self_query).lower()
        for forbidden in ("runner.run", "budgetedselection", "routingcontext",
                          "prompt ="):
            assert forbidden not in source, forbidden

    def test_it_names_no_provider(self):
        import inspect

        source = inspect.getsource(self_query).lower()
        for provider in ("gemini", "openrouter", "chatgpt", "ollama", "perplexity"):
            assert provider not in source, provider


class TestAQuestionIsNotTheLastMission:
    """Asked *"did the last mission satisfy what I asked for?"*, a founder
    means the last thing they asked FOR — not the last thing they asked
    ABOUT. A question that reasoning had to answer becomes a mission like
    any other and would otherwise become its own referent."""

    def test_a_question_mission_is_recognised_by_its_requirement(self):
        import kalpavriksha_desktop as kd
        from master_agent.brain.intent import QUESTION_REQUIREMENT

        record = Record(
            "what can you do?",
            [Step("Reasoning.Transform", "", ("req_1",))],
            [{"description": f"{QUESTION_REQUIREMENT} what can you do?"}],
        )
        assert kd._answers_a_question(record) is True

    def test_a_legacy_question_mission_is_recognised_by_its_shape(self):
        """Records written before the semantic trace existed carry no
        requirements — and this founder's history holds a hundred of
        them. A mission that is one `Reasoning.Transform` and nothing
        else changed nothing in the world; it produced text, which is
        what answering looks like."""
        import kalpavriksha_desktop as kd

        record = Record("what can you do?", [Step("Reasoning.Transform", "")])
        assert kd._answers_a_question(record) is True

    def test_generate_then_write_is_real_work_not_a_question(self):
        """The second step hands the text over. That is the difference."""
        import kalpavriksha_desktop as kd

        record = Record(
            "think of three names and write them to notes.txt",
            [Step("Reasoning.Transform", "matched"),
             Step("Filesystem.WriteFile", "matched")],
        )
        assert kd._answers_a_question(record) is False

    def test_ordinary_work_is_never_mistaken_for_a_question(self):
        import kalpavriksha_desktop as kd

        record = Record(
            "create a folder",
            [Step("Filesystem.CreateFolder", "matched", ("req_1",))],
            [{"description": "create a folder"}],
        )
        assert kd._answers_a_question(record) is False
