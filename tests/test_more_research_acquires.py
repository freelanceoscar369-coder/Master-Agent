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


class TestWhatAnEarlierAttemptEstablishedIsStillTrue:
    """A replan starts a new mission record. The Evidence from the old
    one does not stop being Evidence.

    Found by the demo centrepiece, which is one objective that needs two
    pages. It read the directory on its first pass, lost a route, and
    reached the opening hours on its third -- and then reported

        mandatory criteria remain unestablished for every candidate

    while holding, between the three records, every fact it needed. The
    deliberation was reading only the newest record, so no single record
    ever held both halves of the answer.

    That is the exact opposite of the rule recovery is built on: a second
    attempt must PRESERVE verified work, and Evidence is what verified
    work IS.
    """

    def _control(self, records: dict):
        def objective(objective_id):
            if objective_id not in records:
                raise KeyError(objective_id)
            return records[objective_id]

        return types.SimpleNamespace(
            dispatcher=types.SimpleNamespace(objective=objective))

    def _record(self, evidence_id, url, text):
        return types.SimpleNamespace(tasks=[types.SimpleNamespace(evidence={
            "evidence_id": evidence_id,
            "observation": {"url": url, "text": text},
        })])

    def test_observations_span_every_attempt(self):
        import kalpavriksha_desktop as kd

        control = self._control({
            "obj-1": self._record("ev-1", "http://x.test/directory.html",
                                  "Ashcombe accepts laptops."),
            "obj-2": self._record("ev-2", "http://x.test/weekend.html",
                                  "Ashcombe opens Saturday."),
        })

        seen = kd._observations_from(control, ["obj-1", "obj-2"])

        assert {o.evidence_id for o in seen} == {"ev-1", "ev-2"}

    def test_one_id_still_works_and_is_not_read_as_characters(self):
        """A bare string is a sequence too, and iterating it would ask
        the dispatcher for objectives named 'o', 'b', 'j'."""
        import kalpavriksha_desktop as kd

        control = self._control({
            "obj-1": self._record("ev-1", "http://x.test/a.html", "text"),
        })

        assert {o.evidence_id for o in kd._observations_from(control, "obj-1")} == {"ev-1"}

    def test_an_unreadable_attempt_does_not_lose_the_readable_ones(self):
        import kalpavriksha_desktop as kd

        control = self._control({
            "obj-2": self._record("ev-2", "http://x.test/b.html", "text"),
        })

        seen = kd._observations_from(control, ["obj-missing", "obj-2"])

        assert {o.evidence_id for o in seen} == {"ev-2"}

    def test_a_page_visited_on_an_earlier_attempt_is_not_offered_again(self):
        """Otherwise the third attempt is told to go where the first one
        already went."""
        import kalpavriksha_desktop as kd

        control = self._control({
            "obj-1": types.SimpleNamespace(tasks=[types.SimpleNamespace(evidence={
                "evidence_id": "ev-1",
                "observation": {
                    "url": "http://x.test/directory.html",
                    "text": "...",
                    "links": [{"text": "weekend", "url": "http://x.test/weekend.html"}],
                },
            })]),
            "obj-2": self._record("ev-2", "http://x.test/weekend.html", "..."),
        })

        assert kd._unvisited_links(control, ["obj-1", "obj-2"]) == []
        assert kd._unvisited_links(control, ["obj-1"]) == [
            {"text": "weekend", "url": "http://x.test/weekend.html"}]

    def test_the_loop_carries_every_attempt_into_the_decision(self):
        """A source guard. The chain is only useful if it is the thing
        actually handed to `_decide`, and this is the line that regressed
        silently once already."""
        import inspect

        import kalpavriksha_desktop as kd

        source = inspect.getsource(kd._submit_objective)
        assert "attempts_made = [objective_id]" in source
        assert "attempts_made.append(objective_id)" in source
        assert "objective_id\n        )" not in source.split("attempts_made")[-1], (
            "a decision after the loop must read the chain, not the last id")


class TestAnsweredIsNotFailed:
    """The centrepiece ended with a decided shortlist, every criterion
    cleared against Evidence, two candidates rejected with reasons — and
    then told the founder:

        That didn't complete. I've kept the details for review.

    A route had failed earlier in the mission and been recovered from.
    Both halves are facts; only one of them is the outcome. Saying the
    objective failed when it was answered is as untrue as the reverse,
    and the reverse is what this system is built against.
    """

    def _source(self):
        import inspect

        import kalpavriksha_desktop as kd

        return inspect.getsource(kd._submit_objective)

    def test_a_decided_shortlist_changes_what_the_founder_is_told(self):
        source = self._source()
        assert "answered = decided is not None and bool(decided.shortlist)" in source

    def test_the_failure_is_still_mentioned_never_hidden(self):
        """Softening it into silence would be the other lie."""
        source = self._source()
        assert "Some of what I tried along the way didn't work" in source
        assert "kept the details" in source

    def test_a_mission_with_no_answer_still_says_it_did_not_complete(self):
        """The branch only applies when something was actually
        shortlisted. An empty result must keep the plain failure
        sentence."""
        source = self._source()
        branch = source.split("answered = decided", 1)[1]
        assert "if answered else status.message" in branch


class TestTheSystemDoesNotDeliberateOverItsOwnWords:
    """A decision weighs the world. What the system itself said is not
    something it saw.

    A reasoning step's Evidence is a deterministic measurement of the
    text a model produced -- proper Evidence about the ARTEFACT, and not
    an observation of anything outside us.

    Letting it into a deliberation had a measured cost. "Think of exactly
    three short names for a gardening notes app and write them one per
    line into <file>" ran THREE TIMES: the only observation was the
    reasoning step's own output, the deliberation read candidates out of
    it, established none, and asked for more research on an objective
    that had already satisfied every requirement. Each pass generated
    different names and rewrote the file, so the text the founder was
    told had been verified came from the FIRST run and the text on their
    disk came from the THIRD -- the exact boundary golden path 3 exists
    to guard.
    """

    def _control(self, tasks):
        objective = types.SimpleNamespace(tasks=tasks)
        return types.SimpleNamespace(
            dispatcher=types.SimpleNamespace(objective=lambda _id: objective))

    def _task(self, capability, evidence_id, text, url=""):
        return types.SimpleNamespace(capability=capability, evidence={
            "evidence_id": evidence_id,
            "observation": {"text": text, "url": url},
        })

    def test_a_reasoning_step_is_not_an_observation(self):
        import kalpavriksha_desktop as kd

        control = self._control([
            self._task("Reasoning.Transform", "ev-1",
                       "SproutLog\nGrowLog\nPlotPad"),
        ])

        assert kd._observations_from(control, ["obj-1"]) == ()

    def test_a_page_read_still_is_one(self):
        import kalpavriksha_desktop as kd

        control = self._control([
            self._task("Browser.ReadPageText", "ev-2", "Ashcombe accepts laptops.",
                       "http://x.test/directory.html"),
        ])

        seen = kd._observations_from(control, ["obj-1"])

        assert [o.evidence_id for o in seen] == ["ev-2"]

    def test_a_document_on_disk_still_is_one(self):
        """The rule is about OUR OWN WORDS, not about having a url. A
        founder's own file is material about the world."""
        import kalpavriksha_desktop as kd

        control = self._control([
            self._task("Document.ExtractText", "ev-3", "The contract says..."),
        ])

        assert [o.evidence_id for o in kd._observations_from(control, ["obj-1"])] == ["ev-3"]

    def test_a_mixed_mission_keeps_only_what_it_saw(self):
        import kalpavriksha_desktop as kd

        control = self._control([
            self._task("Browser.ReadPageText", "ev-page", "the page said this",
                       "http://x.test/a.html"),
            self._task("Reasoning.Transform", "ev-said", "and I concluded this"),
        ])

        assert [o.evidence_id for o in kd._observations_from(control, ["obj-1"])] == ["ev-page"]

    def test_the_exclusion_is_by_executive_not_by_one_capability_name(self):
        """So a second reasoning capability is excluded on the day it is
        written, not on the day somebody remembers this list."""
        import kalpavriksha_desktop as kd

        control = self._control([
            self._task("Reasoning.Summarise", "ev-4", "a summary I wrote"),
        ])

        assert kd._observations_from(control, ["obj-1"]) == ()

    def test_progress_is_read_defensively_now_that_every_mission_reads_it(self):
        """`_mission_progress` is consulted on every mission now, and the
        surface tests drive the bridge with the smallest record that
        makes their own point -- rightly."""
        import inspect

        import kalpavriksha_desktop as kd

        source = inspect.getsource(kd._mission_progress)
        assert 'getattr(objective, "tasks", ())' in source


class TestOneDecisionPerMission:
    """A mission decides once, and the same answer acts and reports.

    Deliberation involves a model, so asking twice over identical
    Evidence can give two answers -- and did. Measured on fixture D2 with
    production unchanged:

        no further attempt: errors=False decided=decided
                            more_research=False question=False attempts=0/2

    The loop's decision said `decided`, so no further source was sought.
    The second decision, over the same Evidence, said
    `insufficient_evidence`, so the founder was told nothing could be
    confirmed. One mission, one set of Evidence, two verdicts -- and the
    founder shown the one that did not drive the behaviour.

    That is also why the same fixture passed alone and failed after
    another fixture: nothing was contaminating it, the coin was simply
    landing differently.
    """

    def _source(self):
        import inspect

        import kalpavriksha_desktop as kd

        return inspect.getsource(kd._submit_objective)

    def test_the_reporting_decision_reuses_the_one_already_made(self):
        source = self._source()
        after_loop = source.split("_release_task_browsers()")[-1]
        assert "if decided is None:" in after_loop, (
            "the mission deliberates a second time over the same Evidence")

    def test_a_retry_invalidates_the_held_decision(self):
        """New Evidence makes the held answer stale, so it is cleared and
        recomputed rather than reported about a mission that has since
        moved on."""
        source = self._source()
        assert "decided = None" in source
        driven = source.split("_drive_until_settled(runtime, mission_control, status, objective_id,")[-1]
        assert driven.index("decided = None") < driven.index("Did that change anything")

    def test_the_decision_is_still_recorded_for_the_founder(self):
        source = self._source()
        assert "status.deliberation = decided.as_dict()" in source
