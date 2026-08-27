"""A dictated browser interaction sequence is local work.

## The defect

A founder typed, in one sentence:

    Open a browser session and navigate to
    http://127.0.0.1:8731/acceptance.html. Type the text acceptance into
    the element matching #acceptance-box, click the element matching
    #apply, observe the page and tell me the current text shown by
    #state, then close the browser session.

Every material fact is there: the URL, both selectors, the literal text,
which element to read, the ordering, and the close. Nothing needs
judgement.

It reached the AI Planner. Four providers were walked -- one returned a
plan the text verifier only partially matched, one could not confirm its
own prompt had landed, one could not establish conversation isolation --
before a cloud model produced a seven-step plan that read the page with
`ReadPageText`, piped it into `Reasoning.Transform`, and failed on
`binding on step 'step_5' field 'text': source has no canonical Evidence`.
The closing step never ran, so a browser window was left open.

Two separate defects made that possible, and both are tested here:

1. **The deterministic lane could not claim it.** `_read_explicit_workflow`
   refuses anything matching `_FOREIGN_OPERATION`, and "Open a browser"
   matches that at offset 0. Correct for a filesystem compiler; it just
   meant nothing else claimed browser work.
2. **`Browser.ObserveBrowser` did not publish the argument that answers
   the question.** It has read `selectors` since it was written and never
   said so, so `args_complete` was False and a planner that refuses to
   guess at contracts could not use it -- while the model, which does
   guess, reached for `ReadPageText` instead.

## How these tests are built

Provider contact fails **structurally**. The Planner is given a runner
whose `run()` raises, so an objective that touches a provider cannot pass
by accident -- asserting on a call counter afterwards would let a passing
test coexist with a real provider call.
"""
from __future__ import annotations

import pytest

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

#: Verbatim. Every assertion below is about THIS sentence, because a test
#: written against a tidied-up paraphrase proves the paraphrase plans.
FOUNDER_OBJECTIVE = (
    "Open a browser session and navigate to http://127.0.0.1:8731/acceptance.html. "
    "Type the text acceptance into the element matching #acceptance-box, "
    "click the element matching #apply, observe the page and tell me the "
    "current text shown by #state, then close the browser session."
)

EXPECTED = [
    "Browser.OpenBrowserSession",
    "Browser.Navigate",
    "Browser.TypeText",
    "Browser.Click",
    "Browser.ObserveBrowser",
    "Browser.CloseBrowserSession",
]


class ForbiddenRunner:
    """A reasoning runner that must never be reached."""

    def run(self, prompt, request, **kwargs):
        raise AssertionError(
            "PROVIDER MUST NOT BE CONTACTED -- this objective is fully "
            f"determined by the founder's own words. Prompt was {len(prompt)} chars."
        )


@pytest.fixture
def options():
    """The catalogue the packaged application actually builds."""
    executor = LocalExecutor(PermissionSystem())
    contracts = []
    for plugin in (
        BrowserPlugin(executor, BrowserSessionManager(default_headless=False)),
        FilesystemPlugin(executor),
    ):
        actions = getattr(plugin, "_actions", None)
        if isinstance(actions, dict):
            contracts.extend(
                contracts_from_actions(actions, plugin.manifest.name, qualified_name)
            )
    index = build_index(contracts, loader={c.canonical_id: c for c in contracts}.get)
    return catalogue_from_index(index)


def plan_for(objective: str, options):
    return direct_plan(Intent(goal=objective), options)


def capabilities_of(plan):
    return [step.capability for step in plan.steps]


def step_named(plan, capability):
    for step in plan.steps:
        if step.capability == capability:
            return step
    raise AssertionError(f"{capability} not in plan: {capabilities_of(plan)}")


# =====================================================================
# The counterfactual: the exact failure must disappear, for the right
# reason
# =====================================================================


class TestTheExactObjectiveNeedsNoModel:
    def test_it_compiles_to_the_six_dictated_steps(self, options):
        plan = plan_for(FOUNDER_OBJECTIVE, options)
        assert plan is not None, "the fully dictated objective did not plan locally"
        assert capabilities_of(plan) == EXPECTED

    def test_no_provider_is_contacted(self, options):
        """The regression being prevented is not "six steps". It is
        *explicit local work silently falling back to AI planning* -- and
        a six-step plan produced by a model would satisfy a step count
        while being exactly the failure.

        So this goes through the real `Planner`, whose runner raises.
        """
        planner = Planner(runner=ForbiddenRunner(), catalogue=options)
        outcome = planner.plan(Intent(goal=FOUNDER_OBJECTIVE))

        assert outcome.planned, outcome.reason
        assert capabilities_of(outcome.plan) == EXPECTED
        # A deterministic plan asked nobody, so the ladder recorded no
        # attempt and no provider is named.
        assert outcome.attempts == ()
        assert outcome.provider_id is None

    def test_every_dictated_value_is_the_founders_own(self, options):
        plan = plan_for(FOUNDER_OBJECTIVE, options)

        assert step_named(plan, "Browser.Navigate").payload["url"] == (
            "http://127.0.0.1:8731/acceptance.html"
        )
        typing = step_named(plan, "Browser.TypeText").payload
        assert typing["selector"] == "#acceptance-box"
        assert typing["text"] == "acceptance"
        assert step_named(plan, "Browser.Click").payload["selector"] == "#apply"
        assert step_named(plan, "Browser.ObserveBrowser").payload["selectors"] == [
            "#state"
        ]

    def test_one_session_identity_runs_through_the_whole_workflow(self, options):
        plan = plan_for(FOUNDER_OBJECTIVE, options)
        sessions = {step.payload["session_id"] for step in plan.steps}
        assert len(sessions) == 1
        # Environment identity, not a founder fact -- nobody types a
        # session id, so one is generated exactly as the existing dictated
        # browser workflow has always generated one.
        assert next(iter(sessions)).startswith("kv-")

    def test_ordering_is_carried_by_depends_on_alone(self, options):
        plan = plan_for(FOUNDER_OBJECTIVE, options)
        assert plan.steps[0].depends_on == []
        for earlier, later in zip(plan.steps, plan.steps[1:]):
            assert later.depends_on == [earlier.step_id]

    def test_the_browser_opens_where_the_founder_can_see_it(self, options):
        plan = plan_for(FOUNDER_OBJECTIVE, options)
        assert step_named(plan, "Browser.OpenBrowserSession").payload["headless"] is False

    def test_nothing_reasons_and_nothing_reads_the_whole_page(self, options):
        """The model's plan reached for `ReadPageText` -> `Reasoning
        .Transform` to extract one element's text. Both are absent here:
        the capability that answers the question directly was registered
        the whole time."""
        capabilities = capabilities_of(plan_for(FOUNDER_OBJECTIVE, options))
        assert "Browser.ReadPageText" not in capabilities
        assert not any(c.startswith("Reasoning.") for c in capabilities)


# =====================================================================
# Generic by operation, not by site
# =====================================================================


class TestNoFixtureOrSiteIsBakedIn:
    @pytest.mark.parametrize(
        "url,box,button,readout,text",
        [
            ("http://127.0.0.1:9001/other.html", "#name", "#go", "#result", "hello"),
            ("https://example.test/form", ".field", ".submit", ".outcome", "yes"),
            ("http://localhost:3000/a", "[data-id=in]", "[data-id=ok]", "[data-id=out]", "x"),
        ],
    )
    def test_the_same_shape_plans_for_any_page(
        self, options, url, box, button, readout, text
    ):
        objective = (
            f"Open a browser session and navigate to {url}. "
            f"Type the text {text} into the element matching {box}, "
            f"click the element matching {button}, observe the page and tell me "
            f"the current text shown by {readout}, then close the browser session."
        )
        plan = plan_for(objective, options)
        assert plan is not None
        assert capabilities_of(plan) == EXPECTED
        assert step_named(plan, "Browser.Navigate").payload["url"] == url
        assert step_named(plan, "Browser.TypeText").payload["selector"] == box
        assert step_named(plan, "Browser.TypeText").payload["text"] == text
        assert step_named(plan, "Browser.Click").payload["selector"] == button
        assert step_named(plan, "Browser.ObserveBrowser").payload["selectors"] == [readout]

    def test_a_shorter_dictated_sequence_also_plans(self, options):
        """Nothing requires all six operations. What is required is that
        every clause be understood."""
        plan = plan_for(
            "Open a browser session, go to https://example.test/status and tell me "
            "the text shown by #health, then close the browser session.",
            options,
        )
        assert capabilities_of(plan) == [
            "Browser.OpenBrowserSession",
            "Browser.Navigate",
            "Browser.ObserveBrowser",
            "Browser.CloseBrowserSession",
        ]

    def test_a_workflow_that_never_closes_is_still_planned(self, options):
        plan = plan_for(
            "Open a browser session and navigate to https://example.test/a, "
            "then click the element matching #next.",
            options,
        )
        assert capabilities_of(plan) == [
            "Browser.OpenBrowserSession",
            "Browser.Navigate",
            "Browser.Click",
        ]


# =====================================================================
# The founder's answer
# =====================================================================


class TestTheRequestedValueIsDesignated:
    def test_the_observation_names_the_field_that_answers_the_question(self, options):
        """"tell me the current text shown by #state" is a question. The
        step that can answer it says which of its own observed fields
        does -- a dot-path, because selecting a named field is projection
        and projection is deterministic. Anything that had to compose an
        answer would be reasoning."""
        plan = plan_for(FOUNDER_OBJECTIVE, options)
        assert step_named(plan, "Browser.ObserveBrowser").answers_founder == (
            "elements.0.text"
        )

    def test_no_other_step_claims_to_answer(self, options):
        plan = plan_for(FOUNDER_OBJECTIVE, options)
        designating = [s.capability for s in plan.steps if s.answers_founder]
        assert designating == ["Browser.ObserveBrowser"]

    def test_an_observation_nobody_asked_about_designates_nothing(self, options):
        """"observe the page" with no element named is a general
        observation. There is no requested value, so there is no answer to
        designate."""
        plan = plan_for(
            "Open a browser session, navigate to https://example.test/a and "
            "observe the page, then close the browser session.",
            options,
        )
        assert step_named(plan, "Browser.ObserveBrowser").payload.get("selectors") is None
        assert all(not step.answers_founder for step in plan.steps)

    def test_observe_and_tell_are_one_instruction_not_two_reads(self, options):
        """"observe the page and tell me the text shown by #state" says
        one thing twice. Reading the page twice in a row would be
        obeying the words rather than the instruction."""
        plan = plan_for(FOUNDER_OBJECTIVE, options)
        assert capabilities_of(plan).count("Browser.ObserveBrowser") == 1


# =====================================================================
# Delivery is not outcome
# =====================================================================


class TestTypeAndClickPromiseOnlyDelivery:
    """A page may accept typed input and then reject it; a click may land
    and change nothing. An expectation asserting the page's new state from
    the act of acting would make execution success equal mission success,
    which is the conflation the desktop mouse closure removed. The
    observation that follows owns the page effect."""

    @pytest.mark.parametrize(
        "capability", ["Browser.TypeText", "Browser.Click"]
    )
    def test_the_expectation_claims_delivery_only(self, options, capability):
        step = step_named(plan_for(FOUNDER_OBJECTIVE, options), capability)
        described = step.expected_outcome.description.lower()
        assert "later observation" in described

    def test_the_observation_comes_after_both_of_them(self, options):
        plan = plan_for(FOUNDER_OBJECTIVE, options)
        order = capabilities_of(plan)
        assert order.index("Browser.ObserveBrowser") > order.index("Browser.Click")
        assert order.index("Browser.Click") > order.index("Browser.TypeText")


# =====================================================================
# Refusal: every one of these must fall through to the ladder
# =====================================================================


class TestItRefusesRatherThanGuesses:
    @pytest.mark.parametrize(
        "objective,why",
        [
            (
                "Open a browser session and navigate to the acceptance page, "
                "then close the browser session.",
                "no URL was stated -- 'the acceptance page' is not an address",
            ),
            (
                "Open a browser session, navigate to https://example.test/a and "
                "type acceptance into the box, then close the browser session.",
                "no selector for the typing target",
            ),
            (
                "Open a browser session, navigate to https://example.test/a and "
                "type it into the element matching #box, then close the browser session.",
                "'it' names no text",
            ),
            (
                "Open a browser session, navigate to https://example.test/a and "
                "type the observed title into the element matching #box.",
                "the text is a value another step would have to produce",
            ),
            (
                "Open a browser session, navigate to https://example.test/a and "
                "click the submit button, then close the browser session.",
                "'the submit button' is an intention, not a selector",
            ),
            (
                "Open a browser session, navigate to https://example.test/a and "
                "tell me what happened, then close the browser session.",
                "a summary was requested, and summarising is reasoning",
            ),
            (
                "Navigate to https://example.test/a and tell me the text shown "
                "by #state, then close the browser session.",
                "no session was opened, and this lane does not invent one",
            ),
            (
                "Open a browser session, navigate to https://example.test/a, "
                "tell me the text shown by #a and tell me the text shown by #b.",
                "two answers requested, one place to report one",
            ),
            (
                "Open a browser session, navigate to https://example.test/a, "
                "search for the cheapest supplier and tell me the text shown by #state.",
                "an operation this lane does not understand -- compiling the "
                "rest would silently drop it",
            ),
            (
                "Open a browser session, close the browser session and navigate "
                "to https://example.test/a.",
                "the close is not last; this lane does not reorder the founder",
            ),
            (
                "Open a browser session and open a browser session, then navigate "
                "to https://example.test/a.",
                "two sessions opened, and nothing said which one to use",
            ),
            (
                "Open a browser session, then close the browser session.",
                "no page operation -- there is no work here to claim",
            ),
        ],
    )
    def test_undictated_work_falls_through(self, options, objective, why):
        assert plan_for(objective, options) is None, why

    def test_a_missing_capability_refuses_the_whole_workflow(self, options):
        """Half a dictated sequence is not a smaller version of it."""
        without_click = tuple(o for o in options if o.name != "Browser.Click")
        assert plan_for(FOUNDER_OBJECTIVE, without_click) is None

    def test_an_incomplete_observe_contract_refuses_rather_than_guesses(self, options):
        """The whole failure began with a contract that did not publish
        the argument it reads. If `selectors` is not published, this lane
        must refuse -- passing it anyway would be guessing at the
        contract, which is exactly what it exists to prevent."""
        import dataclasses

        narrowed = tuple(
            dataclasses.replace(o, optional_args=(), args_complete=False)
            if o.name == "Browser.ObserveBrowser" else o
            for o in options
        )
        assert plan_for(FOUNDER_OBJECTIVE, narrowed) is None

    def test_an_unpublished_elements_output_refuses_rather_than_binds(self, options):
        """The founder's answer is read out of `elements`. A capability
        that does not promise that field is not one to depend on."""
        import dataclasses

        silent = tuple(
            dataclasses.replace(o, output_fields=("url", "title"))
            if o.name == "Browser.ObserveBrowser" else o
            for o in options
        )
        assert plan_for(FOUNDER_OBJECTIVE, silent) is None

    def test_genuinely_ambiguous_browser_work_still_reaches_the_planner(self, options):
        """The lane exists to claim dictated work, not browser work. An
        objective needing judgement must still reach a model."""
        assert plan_for(
            "Open a browser and find out which of our competitors changed "
            "their pricing this month, then summarise what you find.",
            options,
        ) is None


# =====================================================================
# The neighbouring lanes are untouched
# =====================================================================


class TestExistingLanesStillWork:
    def test_the_dictated_capture_workflow_is_unchanged(self, options):
        plan = plan_for(
            "Open a browser, navigate to https://example.test/page, observe it, "
            "create a folder called Research on the Desktop and write the observed "
            "title and url into a file called page_info.txt, then close the browser.",
            options,
        )
        assert plan is not None
        assert capabilities_of(plan) == [
            "Browser.OpenBrowserSession",
            "Browser.Navigate",
            "Browser.ObserveBrowser",
            "Filesystem.CreateFolder",
            "Filesystem.WriteFile",
            "Browser.CloseBrowserSession",
        ]

    def test_the_dictated_filesystem_workflow_is_unchanged(self, options):
        plan = plan_for(
            "Create a folder called KV_Check on the Desktop. Then show me the text "
            "before you write it into notes.txt inside that folder. The text "
            "should be: checkpoint acceptance.",
            options,
        )
        assert plan is not None
        assert capabilities_of(plan) == [
            "Filesystem.CreateFolder",
            "Filesystem.WriteFile",
        ]
        assert step_named(plan, "Filesystem.WriteFile").founder_checkpoint
