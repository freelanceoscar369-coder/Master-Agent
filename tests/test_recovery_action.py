"""A failed route becomes a different route, not the same one again.

## What made this necessary

The founder's research run produced four facts that were all true at
once:

    OpenBrowserSession   matched
    Navigate             matched
    ReadPageText         matched
    page text            "Error 500 - Server Internal Error"

Every step was independently verified. No founder requirement was
satisfied. **A verified step is not a satisfied requirement**, and a
recovery that confuses the two either throws away real evidence or
believes the objective is progressing when it is not.

## The rule a second attempt has to obey

    same strategy + same environment + same known failure
    + no changed condition
    = not a recovery

An earlier version re-submitted the identical intent and made things
worse: the new plan opened a browser session the failed attempt still
held, and the mission died on `session already open`. What differs now is
KNOWLEDGE, not identity -- same Intent, same requirement ids, same
founder evidence, plus what the first attempt learned.
"""
from __future__ import annotations

import pytest

from master_agent.brain.deliberation import (
    MissionProgress,
    no_useful_progress,
    progress_of,
)
from master_agent.planner.plan import CONSTRAINT, SemanticRequirement

REQUIREMENTS = (
    SemanticRequirement("req_1", CONSTRAINT, "find the games",
                        founder_evidence="search for action rpg games"),
    SemanticRequirement("req_2", CONSTRAINT, "give demo links",
                        founder_evidence="search for action rpg games"),
)


class Task:
    def __init__(self, task_id, capability, covers, verdict, payload=None, observation=None):
        self.task_id = task_id
        self.capability = capability
        self.covers = covers
        self.payload = payload or {}
        self.errors = []
        self.evidence = (
            {"verdict": verdict, "evidence_id": f"ev-{task_id}",
             "observation": observation or {}}
            if verdict else None
        )


# =====================================================================
# A verified step is not a satisfied requirement
# =====================================================================


class TestTheDistinctionThatMattered:
    def the_dead_source_run(self):
        """The founder's own trace: everything verified, nothing
        satisfied, because the page was an HTTP 500."""
        return [
            Task("t1", "Browser.OpenBrowserSession", ("req_1",), "matched"),
            Task("t2", "Browser.Navigate", ("req_1",), "matched",
                 {"url": "https://dead.example/reviews"}),
            Task("t3", "Browser.ReadPageText", ("req_1", "req_2"), "matched"),
            Task("t4", "Reasoning.Transform", ("req_2",), "not_matched",
                 {"instruction": "which of these qualify?"}),
        ]

    def test_verified_steps_are_recorded_even_when_nothing_is_satisfied(self):
        progress = progress_of("research", REQUIREMENTS, self.the_dead_source_run())
        assert progress.verified_steps, "verified execution facts were discarded"
        assert "req_2" in progress.unresolved

    def test_evidence_survives_a_failed_mission(self):
        """It was independently observed. It does not stop being true
        because a later step failed."""
        progress = progress_of("research", REQUIREMENTS, self.the_dead_source_run())
        assert len(progress.evidence_ids) >= 3

    def test_the_failed_route_is_named_so_it_can_be_avoided(self):
        progress = progress_of("research", REQUIREMENTS, self.the_dead_source_run())
        assert any("Reasoning.Transform" in route
                   for route in progress.failed_routes)

    def test_a_route_is_capability_plus_target_not_capability_alone(self):
        """Two Navigates are the same capability and entirely different
        attempts. A recovery that could not tell them apart would rule
        out navigation itself."""
        progress = progress_of("research", REQUIREMENTS, self.the_dead_source_run())
        assert any("dead.example" in route
                   for route in progress.successful_routes)

    def test_a_failed_source_still_counts_as_useful_progress(self):
        """Knowing a source is unusable is knowledge, and it is what
        stops the next attempt repeating it."""
        progress = progress_of("research", REQUIREMENTS, self.the_dead_source_run())
        assert progress.useful_progress is True


# =====================================================================
# Zero satisfaction, and partial success
# =====================================================================


class TestZeroSatisfactionRecovery:
    def test_nothing_satisfied_means_everything_is_still_to_do(self):
        tasks = [Task("t1", "Browser.Navigate", ("req_1", "req_2"),
                      "not_matched", {"url": "https://dead.example/"})]
        progress = progress_of("research", REQUIREMENTS, tasks)
        assert progress.satisfied == ()
        assert set(progress.unresolved) == {"req_1", "req_2"}
        assert progress.anything_satisfied is False


class TestPartialSuccessRecovery:
    def partial(self):
        return [
            Task("t1", "Browser.Navigate", ("req_1",), "matched",
                 {"url": "https://works.example/"}),
            Task("t2", "Browser.ReadPageText", ("req_1",), "matched"),
            Task("t3", "Browser.Navigate", ("req_2",), "not_matched",
                 {"url": "https://dead.example/"}),
        ]

    def test_a_satisfied_requirement_is_not_listed_as_still_to_do(self):
        """The whole point of preserving verified work: a replan must
        not redo it. For a capability with an external effect, redoing
        is not a wasted step -- it is a second real change."""
        progress = progress_of("research", REQUIREMENTS, self.partial())
        assert progress.satisfied == ("req_1",)
        assert progress.unresolved == ("req_2",)

    def test_the_working_route_is_remembered_alongside_the_broken_one(self):
        progress = progress_of("research", REQUIREMENTS, self.partial())
        assert any("works.example" in r for r in progress.successful_routes)
        assert any("dead.example" in r for r in progress.failed_routes)


# =====================================================================
# No useful progress
# =====================================================================


class TestNoUsefulProgress:
    def base(self):
        return MissionProgress(
            objective="research", satisfied=("req_1",), unresolved=("req_2",),
            evidence_ids=("ev-1",), failed_routes=("Browser.Navigate a",),
        )

    def test_an_identical_outcome_is_no_progress(self):
        progress = self.base()
        assert no_useful_progress(progress, progress) is True

    def test_a_newly_satisfied_requirement_is_progress(self):
        after = MissionProgress(
            objective="research", satisfied=("req_1", "req_2"),
            evidence_ids=("ev-1",), failed_routes=("Browser.Navigate a",),
        )
        assert no_useful_progress(self.base(), after) is False

    def test_new_evidence_is_progress_even_without_satisfaction(self):
        after = MissionProgress(
            objective="research", satisfied=("req_1",), unresolved=("req_2",),
            evidence_ids=("ev-1", "ev-2"), failed_routes=("Browser.Navigate a",),
        )
        assert no_useful_progress(self.base(), after) is False

    def test_eliminating_another_route_is_progress(self):
        """A second dead source is not nothing: it is one fewer place
        left to try, and it is what makes the third attempt different."""
        after = MissionProgress(
            objective="research", satisfied=("req_1",), unresolved=("req_2",),
            evidence_ids=("ev-1",),
            failed_routes=("Browser.Navigate a", "Browser.Navigate b"),
        )
        assert no_useful_progress(self.base(), after) is False

    def test_a_new_evidence_id_for_the_same_observation_is_not_progress(self):
        before = progress_of("research", REQUIREMENTS, [
            Task("first", "Browser.ReadPageText", (), "matched",
                 observation={"url": "https://a.test", "text": "same",
                              "captured_at": "one"}),
        ])
        after = progress_of("research", REQUIREMENTS, [
            Task("second", "Browser.ReadPageText", (), "matched",
                 observation={"url": "https://a.test", "text": "same",
                              "captured_at": "two"}),
        ])
        assert before.evidence_ids != after.evidence_ids
        assert before.observation_signatures == after.observation_signatures
        assert no_useful_progress(before, after) is True

    def test_a_changed_observation_is_new_knowledge(self):
        before = progress_of("research", REQUIREMENTS, [
            Task("first", "Browser.ReadPageText", (), "matched",
                 observation={"url": "https://a.test", "text": "old"}),
        ])
        after = progress_of("research", REQUIREMENTS, [
            Task("second", "Browser.ReadPageText", (), "matched",
                 observation={"url": "https://a.test", "text": "new"}),
        ])
        assert no_useful_progress(before, after) is False


# =====================================================================
# The mission loop consumes the decision
# =====================================================================


class TestTheDecisionIsActedOn:
    def test_the_surface_replans_rather_than_recording_and_stopping(self):
        import inspect

        import kalpavriksha_desktop as kd

        source = inspect.getsource(kd._submit_objective)
        assert "mission_service.start(intent_result.intent)" in source
        assert 'context["recovery"]' in source, (
            "the second attempt is not told what the first one learned, so "
            "it is the same attempt again"
        )

    def test_the_environment_is_released_before_the_second_attempt(self):
        """Otherwise the retry inherits a session the failed attempt
        still holds -- which is exactly how the previous version made
        things worse."""
        import inspect

        import kalpavriksha_desktop as kd

        source = inspect.getsource(kd._submit_objective)
        recovery = source.split("attempts += 1")[1]
        release = recovery.index("_release_task_browsers()")
        restart = recovery.index("mission_service.start(intent_result.intent)")
        assert release < restart

    def test_the_loop_stops_when_nothing_changed(self):
        import inspect

        import kalpavriksha_desktop as kd

        source = inspect.getsource(kd._submit_objective)
        assert "no_useful_progress(before, after)" in source

    def test_the_objective_identity_is_never_replaced(self):
        """Recovery is part of the original mission. A disconnected new
        objective wearing the costume of continuity would lose the
        founder's requirements and their provenance."""
        import inspect

        import kalpavriksha_desktop as kd

        source = inspect.getsource(kd._submit_objective)
        recovery = source.split("attempts += 1")[1]
        assert "intent_layer.parse" not in recovery
        assert "requirements_for" not in recovery


class TestThePlannerIsToldWhatWasLearned:
    def build(self, recovery):
        from master_agent.planner.catalogue import CapabilityOption
        from master_agent.planner.plan import Intent
        from master_agent.planner.prompting import build_prompt

        intent = Intent(goal="research something", constraints=[],
                        context={"recovery": recovery}, success_criteria=[])
        intent.requirements = REQUIREMENTS
        return build_prompt(intent, (CapabilityOption(name="Browser.Navigate"),))

    def test_a_failed_route_is_stated(self):
        prompt = self.build({
            "satisfied": [], "unresolved": ["req_1", "req_2"],
            "failed_routes": ["Browser.Navigate https://dead.example/"],
        })
        assert "dead.example" in prompt
        assert "materially DIFFERENT" in prompt

    def test_satisfied_requirements_are_marked_not_to_be_redone(self):
        prompt = self.build({
            "satisfied": ["req_1"], "unresolved": ["req_2"],
            "failed_routes": [],
        })
        assert "NOT to be done again" in prompt
        assert "req_1" in prompt

    def test_no_site_is_named_as_a_rule_only_as_a_fact(self):
        """The instruction is "these did not work", never a forbidden
        list. A hardcoded hostname stops being true the moment the site
        recovers."""
        import inspect

        from master_agent.planner import prompting

        source = inspect.getsource(prompting)
        for hardcoded in ("steampowered", "ign.com", "http://", "https://"):
            assert hardcoded not in source, hardcoded

    def test_an_ordinary_first_attempt_says_nothing_about_recovery(self):
        from master_agent.planner.catalogue import CapabilityOption
        from master_agent.planner.plan import Intent
        from master_agent.planner.prompting import build_prompt

        intent = Intent(goal="research something", constraints=[],
                        context={}, success_criteria=[])
        intent.requirements = REQUIREMENTS
        prompt = build_prompt(intent, (CapabilityOption(name="Browser.Navigate"),))
        assert "second attempt" not in prompt

    def test_independent_sources_are_not_placed_in_one_failure_chain(self):
        """Measured live: one help-page redirect blocked eleven unrelated
        acquisition, synthesis, delivery and verification steps because
        each source had been made to depend on the previous source.
        """
        prompt = self.build({})

        assert "must not block an unrelated source route" in prompt
        assert "stateful session" in prompt
