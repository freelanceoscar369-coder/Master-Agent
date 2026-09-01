"""`Browser.ObserveBrowser` can be asked for an element, and says so.

## The defect

The Action has read `selectors` since it was written. It never published
the argument, so the extracted contract was `known` but not `closed`,
`args_complete` was False, and a planner that refuses to guess at
contracts could not use the one capability that answers "what does this
element say?".

A model, which does guess, reached for `Browser.ReadPageText` and piped
it into `Reasoning.Transform` instead -- and that failed, because
`ReadPageText` publishes no verified output to bind to.

Two things are proven here: that the roster is now published truthfully,
and that a fresh observation asked for a selector actually returns that
element's text through the ordinary Verification path -- no new verifier,
no new capability, no page-specific expectation.
"""
from __future__ import annotations

import pytest

from master_agent.capabilities.extraction import contract_from_action
from master_agent.environment.browser_session import BrowserSessionManager
from master_agent.executor.actions.browser.observe import ObserveBrowserAction
from master_agent.plugins.browser_expectations import bind_for_environment
from master_agent.plugins.browser_verifier import BrowserVerifier
from master_agent.verification.evidence import ObservationCheck, Verdict

#: A page whose state changes only when a button is pressed -- the generic
#: shape of "act, then read the element that shows the result". No fixture
#: file and no site: the point is the mechanism.
PAGE = """
<html><head><title>State Page</title></head><body>
  <input id="box" />
  <button id="apply" onclick="document.getElementById('state').textContent =
      document.getElementById('box').value === 'acceptance' ? 'accepted' : 'rejected'">Apply</button>
  <span id="state">pending</span>
</body></html>
"""


@pytest.fixture
def page_session():
    sessions = BrowserSessionManager()
    sessions.open_session("s1")
    sessions.get("s1").page.set_content(PAGE)
    try:
        yield sessions
    finally:
        sessions.close_all()


# =====================================================================
# The contract
# =====================================================================


class TestTheRosterIsPublished:
    def contract(self):
        return contract_from_action(
            ObserveBrowserAction(BrowserSessionManager()),
            "Browser.ObserveBrowser",
            "browser",
        )

    def test_the_arguments_it_already_reads_are_now_named(self):
        names = {field.name for field in self.contract().inputs.fields}
        assert names == {
            "session_id",
            "selectors",
            "include_accessibility_tree",
            "include_available_actions",
        }

    def test_the_roster_is_closed_so_a_planner_may_rely_on_it(self):
        """`args_complete` is what turns "these are the required names,
        others may exist" into "this is the whole contract". Without it
        the deterministic lane correctly refuses to pass `selectors`."""
        inputs = self.contract().inputs
        assert inputs.known and inputs.closed

    def test_the_published_roster_is_exactly_what_run_reads(self):
        """A published argument nobody reads is a lie in the other
        direction. `validate()` is the Action's own statement of what it
        accepts, so the two must agree."""
        action = ObserveBrowserAction(BrowserSessionManager())
        published = {"session_id"} | {
            item["name"] for item in action.optional_parameters()
        }
        errors = action.validate({
            "session_id": "s",
            "selectors": ["#a"],
            "include_accessibility_tree": True,
            "include_available_actions": True,
        })
        assert errors == []
        assert published == {
            "session_id", "selectors",
            "include_accessibility_tree", "include_available_actions",
        }

    def test_elements_is_published_as_an_output(self):
        outputs = {field.name for field in self.contract().outputs.fields}
        assert outputs == {"url", "title", "elements"}


class TestElementsIsStructurallyGuaranteed:
    """`elements` was withheld on the reading that it "depends on
    selectors the caller passed". That confused the list's CONTENTS with
    its PRESENCE, and it is the presence a plan depends on."""

    def test_the_key_is_there_even_with_no_selectors(self, page_session):
        result = ObserveBrowserAction(page_session).run({"session_id": "s1"})
        assert result.success
        assert result.output["elements"] == []

    def test_one_entry_per_selector_in_the_order_requested(self, page_session):
        result = ObserveBrowserAction(page_session).run(
            {"session_id": "s1", "selectors": ["#state", "#box", "#apply"]}
        )
        assert [e["selector"] for e in result.output["elements"]] == [
            "#state", "#box", "#apply"
        ]

    def test_a_selector_matching_nothing_still_produces_its_entry(self, page_session):
        """Absence is an observation. Skipping the entry would shift every
        later index, which is what makes `elements.0` safe to name."""
        result = ObserveBrowserAction(page_session).run(
            {"session_id": "s1", "selectors": ["#not-here", "#state"]}
        )
        elements = result.output["elements"]
        assert elements[0]["selector"] == "#not-here"
        assert elements[0]["is_visible"] is False
        assert elements[1]["text"] == "pending"


# =====================================================================
# Verification
# =====================================================================


class TestTheObservationIsVerifiedFreshly:
    def test_the_expectation_covers_the_selector_that_was_asked_for(self):
        """The verifier re-observes from scratch with the same selectors,
        so position `i` answers request `i`. Asserting that identity is
        what stops a fresh observation of the WRONG element from reading
        as proof about the right one."""
        expected = bind_for_environment(
            capability="Browser.ObserveBrowser",
            payload={"session_id": "s1", "selectors": ["#state"]},
            description="the page was read",
        )
        fields = [(c.field, c.operator, c.value) for c in expected.checks]
        assert ("elements.0.selector", "equals", "#state") in fields

    def test_it_does_not_assert_the_element_was_found(self):
        """A step whose whole purpose may be to confirm something is gone
        must not be failed for succeeding. Whether an element should be
        present, and what it should say, is a claim about a particular
        page -- and this module states what a browser observation means."""
        expected = bind_for_environment(
            capability="Browser.ObserveBrowser",
            payload={"session_id": "s1", "selectors": ["#state"]},
            description="the page was read",
        )
        fields = {c.field for c in expected.checks}
        assert "elements.0.is_visible" not in fields
        assert not any(c.field.endswith(".text") for c in expected.checks)

    def test_read_page_text_requires_a_usable_non_error_page(self):
        expected = bind_for_environment(
            capability="Browser.ReadPageText",
            payload={"session_id": "s1"},
            description="read the source",
        )
        fields = {(check.field, check.operator, check.value) for check in expected.checks}
        assert ("text", "exists", None) in fields
        assert ("page_usable", "equals", True) in fields

    def test_an_observation_with_no_selectors_is_unchanged(self):
        expected = bind_for_environment(
            capability="Browser.ObserveBrowser",
            payload={"session_id": "s1"},
            description="the page was read",
        )
        assert [c.field for c in expected.checks] == ["url", "title"]

    def test_a_fresh_observation_verifies_the_selector(self, page_session):
        expected = bind_for_environment(
            capability="Browser.ObserveBrowser",
            payload={"session_id": "s1", "selectors": ["#state"]},
            description="the page was read",
        )
        evidence = BrowserVerifier(page_session, "s1", ["#state"]).verify(expected)
        assert evidence.verdict is Verdict.MATCHED
        assert evidence.observation["elements"][0]["text"] == "pending"

    def test_the_generic_evaluator_reads_a_nested_element_value(self, page_session):
        """No new verifier and no nested binding syntax. `elements.0.text`
        is a dot-path the shipped evaluator already walks -- the same one
        Verification uses for every other check."""
        page_session.get("s1").page.fill("#box", "acceptance")
        page_session.get("s1").page.click("#apply")

        evidence = BrowserVerifier(page_session, "s1", ["#state"]).verify(
            bind_for_environment(
                capability="Browser.ObserveBrowser",
                payload={"session_id": "s1", "selectors": ["#state"]},
                description="the page was read",
            )
        )
        assert evidence.verdict is Verdict.MATCHED
        assert evidence.observation["elements"][0]["text"] == "accepted"

    def test_a_stated_page_expectation_can_be_checked_the_same_way(self, page_session):
        """What an acceptance harness does with the same machinery: a
        check on `elements.0.text`. Stated HERE, by whoever knows the
        page -- never inside `bind_for_environment`, which would make one
        page's semantics every page's rule."""
        page_session.get("s1").page.fill("#box", "acceptance")
        page_session.get("s1").page.click("#apply")

        from master_agent.verification.evidence import ExpectedOutcome

        evidence = BrowserVerifier(page_session, "s1", ["#state"]).verify(
            ExpectedOutcome(
                description="the page reports the accepted state",
                checks=[ObservationCheck(
                    field="elements.0.text", operator="equals", value="accepted",
                    description="#state reads 'accepted'",
                )],
            )
        )
        assert evidence.verdict is Verdict.MATCHED


class TestDeliveryActionsStillOwnNoOutcome:
    """Click and TypeText remain delivery-only. Inventing outcome
    verification for them here -- so that the acceptance would look
    greener -- is the exact conflation the desktop mouse closure removed,
    and it would make execution success equal mission success."""

    @pytest.mark.parametrize(
        "capability", ["Browser.Click", "Browser.TypeText", "Browser.Scroll",
                       "Browser.PressKey", "Browser.WaitForSelector"],
    )
    def test_no_domain_expectation_is_invented(self, capability):
        assert bind_for_environment(
            capability=capability,
            payload={"session_id": "s1", "selector": "#apply", "text": "x"},
            description="the step ran",
        ) is None
