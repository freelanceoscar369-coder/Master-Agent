"""Deciding you need more evidence, and being able to go and get it.

Fixture D2 in the diversified battery reads ONE page and asks a question
that page cannot answer. The answer is on a second page, linked from the
first, and never named in the objective -- so reaching it has to be the
system's own decision.

What it actually did, three missions in a row: read the directory page,
conclude "nobody has established the Sunday hours", replan, and read the
directory page again. Two separate defects, both here:

1.  The Planner was handed `still unresolved: crit_2` -- an internal
    identifier -- and asked to go and settle it.
2.  The page's TEXT keeps the words "Sunday opening hours" and loses the
    address behind them, so a mission holding the answer's location could
    not act on its own decision.

Deciding more research is needed, and having nothing to do about it, is
not intelligence. It is a system that knows it is stuck.
"""
from __future__ import annotations

import types

from master_agent.brain.deliberation import (
    DISCOVERY,
    MET,
    UNVERIFIED,
    Candidate,
    Criterion,
    DecisionFrame,
    Observation,
    deliberate,
)


class TestWhatIsMissingIsSaidInWords:
    def _frame(self):
        return DecisionFrame(
            objective="which reading rooms are step-free and open on Sunday",
            requirement_ids=("req_1", "req_2"),
            decision_type="research_shortlist",
            mandatory=(
                Criterion("crit_1", "the reading room is step-free",
                          requirement_id="req_1"),
                Criterion("crit_2", "the reading room is open on Sunday",
                          requirement_id="req_2"),
            ),
        )

    def test_a_result_carries_what_its_criteria_ask(self):
        """A result that only knows `crit_2` cannot say what is missing
        to anything except the frame it came from."""
        result = deliberate(self._frame(), (), reasoner=None)

        assert result.criteria == {
            "crit_1": "the reading room is step-free",
            "crit_2": "the reading room is open on Sunday",
        }
        assert "criteria" in result.as_dict()

    def test_the_question_names_the_criterion_not_its_id(self):
        import kalpavriksha_desktop as kd

        from master_agent.brain.deliberation import DeliberationResult, RejectedCandidate

        result = DeliberationResult(
            state="insufficient_evidence",
            rejected=(RejectedCandidate("c1", "Halden Reading Room", "unverified",
                                        unverified=("crit_2",)),),
            criteria={"crit_2": "the reading room is open on Sunday"},
            more_research=True,
        )

        question = kd._evidence_question(result)

        assert question["unresolved_criteria"] == ["the reading room is open on Sunday"]
        assert question["candidates"]["the reading room is open on Sunday"] == [
            "Halden Reading Room"]

    def test_nothing_extracted_is_the_widest_question_not_no_question(self):
        """The first source established none of the criteria, so all of
        them are open. Returning None here is why a mission that read one
        page, learned nothing usable, and KNEW it stopped after a single
        cycle."""
        import kalpavriksha_desktop as kd

        from master_agent.brain.deliberation import DeliberationResult

        result = DeliberationResult(
            state="insufficient_evidence",
            criteria={"crit_1": "the reading room is step-free",
                      "crit_2": "the reading room is open on Sunday"},
            more_research=True,
        )

        question = kd._evidence_question(result)

        assert question is not None
        assert sorted(question["unresolved_criteria"]) == [
            "the reading room is open on Sunday",
            "the reading room is step-free",
        ]

    def test_a_settled_decision_asks_for_nothing(self):
        import kalpavriksha_desktop as kd

        from master_agent.brain.deliberation import DeliberationResult

        assert kd._evidence_question(
            DeliberationResult(state="decided", more_research=False)) is None
        assert kd._evidence_question(None) is None


class TestAPageRecordsWhereItPoints:
    def test_relative_links_are_recorded_absolute(self):
        """`el.href`, not `getAttribute('href')`: the browser has already
        resolved it against the page's own base, so `hours.html` arrives
        as somewhere a later step can actually navigate to."""
        from master_agent.plugins.browser_observation import _observe_links

        page = types.SimpleNamespace(
            eval_on_selector_all=lambda selector, script: [
                {"text": "Sunday opening hours",
                 "url": "http://127.0.0.1:8931/hours.html"},
            ])

        links, truncated = _observe_links(page)

        assert [(link.text, link.url) for link in links] == [
            ("Sunday opening hours", "http://127.0.0.1:8931/hours.html")]
        assert truncated is False

    def test_what_is_not_a_destination_is_not_a_link(self):
        from master_agent.plugins.browser_observation import _observe_links

        page = types.SimpleNamespace(
            eval_on_selector_all=lambda s, script: [
                {"text": "Menu", "url": "javascript:void(0)"},
                {"text": "Email us", "url": "mailto:someone@example.test"},
                {"text": "Hours", "url": "http://127.0.0.1:8931/hours.html"},
            ])

        assert [link.text for link in _observe_links(page)[0]] == ["Hours"]

    def test_the_same_destination_twice_is_one_link(self):
        from master_agent.plugins.browser_observation import _observe_links

        page = types.SimpleNamespace(
            eval_on_selector_all=lambda s, script: [
                {"text": "Hours", "url": "http://x.test/hours.html"},
                {"text": "See hours", "url": "http://x.test/hours.html"},
            ])

        assert len(_observe_links(page)[0]) == 1

    def test_an_unreadable_page_points_nowhere_rather_than_raising(self):
        from master_agent.plugins.browser_observation import _observe_links

        def explode(selector, script):
            raise RuntimeError("the page went away")

        assert _observe_links(types.SimpleNamespace(
            eval_on_selector_all=explode)) == ([], False)

    def test_a_cap_that_bites_is_declared_never_silent(self):
        from master_agent.plugins.browser_observation import MAX_PAGE_LINKS, _observe_links

        page = types.SimpleNamespace(
            eval_on_selector_all=lambda s, script: [
                {"text": f"link {i}", "url": f"http://x.test/{i}"}
                for i in range(MAX_PAGE_LINKS + 20)
            ])

        links, truncated = _observe_links(page)

        assert len(links) == MAX_PAGE_LINKS
        assert truncated is True


class TestWhereToLookComesFromEvidence:
    def _objective(self, tasks):
        return types.SimpleNamespace(tasks=tasks)

    def _task(self, url, links=()):
        return types.SimpleNamespace(evidence={
            "evidence_id": "ev-1",
            "observation": {"url": url, "text": "...",
                            "links": [dict(link) for link in links]},
        })

    def _control(self, objective):
        return types.SimpleNamespace(
            dispatcher=types.SimpleNamespace(objective=lambda _id: objective))

    def test_a_link_seen_but_not_followed_is_offered(self):
        import kalpavriksha_desktop as kd

        control = self._control(self._objective([
            self._task("http://x.test/directory.html",
                       [{"text": "Sunday opening hours", "url": "http://x.test/hours.html"}]),
        ]))

        assert kd._unvisited_links(control, "obj-1") == [
            {"text": "Sunday opening hours", "url": "http://x.test/hours.html"}]

    def test_a_page_already_read_is_not_offered_again(self):
        """Otherwise the suggestion is "go back where you have been",
        which is exactly the loop this exists to break."""
        import kalpavriksha_desktop as kd

        control = self._control(self._objective([
            self._task("http://x.test/directory.html",
                       [{"text": "Hours", "url": "http://x.test/hours.html"},
                        {"text": "Home", "url": "http://x.test/directory.html"}]),
            self._task("http://x.test/hours.html"),
        ]))

        assert kd._unvisited_links(control, "obj-1") == []

    def test_an_unreadable_record_points_nowhere(self):
        import kalpavriksha_desktop as kd

        def explode(_id):
            raise RuntimeError("no such objective")

        assert kd._unvisited_links(
            types.SimpleNamespace(dispatcher=types.SimpleNamespace(objective=explode)),
            "obj-1") == []

    def test_the_question_carries_both_what_and_where(self):
        import kalpavriksha_desktop as kd

        from master_agent.brain.deliberation import DeliberationResult

        question = kd._evidence_question(
            DeliberationResult(
                state="insufficient_evidence",
                criteria={"crit_2": "the reading room is open on Sunday"},
                more_research=True),
            [{"text": "Sunday opening hours", "url": "http://x.test/hours.html"}],
        )

        assert question["unresolved_criteria"] == ["the reading room is open on Sunday"]
        assert question["unvisited"] == [
            {"text": "Sunday opening hours", "url": "http://x.test/hours.html"}]


class TestThePlannerIsToldWhereNotOnlyWhat:
    def _prompt(self, wanted):
        from master_agent.planner.prompting import build_prompt
        from tests.test_medium_planner_guidance import CATALOGUE, Intent

        return build_prompt(
            Intent(goal="which rooms are step-free and open on Sunday",
                   context={"evidence_needed": wanted}),
            CATALOGUE,
        )

    def test_the_address_a_page_actually_carried_reaches_the_plan(self):
        prompt = self._prompt({
            "unresolved_criteria": ["the reading room is open on Sunday"],
            "candidates": {},
            "already_established": [],
            "unvisited": [{"text": "Sunday opening hours",
                           "url": "http://x.test/hours.html"}],
        })

        assert "the reading room is open on Sunday" in prompt
        assert "http://x.test/hours.html" in prompt
        assert "none has been visited yet" in prompt

    def test_no_unvisited_links_means_no_section_about_them(self):
        prompt = self._prompt({
            "unresolved_criteria": ["the reading room is open on Sunday"],
            "candidates": {},
            "already_established": [],
            "unvisited": [],
        })

        assert "none has been visited yet" not in prompt
