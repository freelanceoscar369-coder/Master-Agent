"""The founder surface must know every status the backend can report.

Found by live testing the packaged app, not by any source test: `162f6ec`
added `AWAITING_CLARIFICATION` to `ExecutionStatus` and left the three
front-end status vocabularies untouched. The consequence in the real
application was silent and wrong --

  * `app.js executionTreeState()` matched no branch and returned `null`,
    so `recomputeTreeState()` fell through to **idle**: the tree showed
    *nothing happening* while Kalpavriksha was in fact waiting on the
    founder to answer a question it had just asked;
  * `prominence.js` never reached its "a human is required" tier;
  * `workState.js` did not list the status as known, so the headline came
    from `UNKNOWN_STATUS_FALLBACK` -- the generic word *"Working"*.

Every one of those is the same mistake the backend fix existed to
prevent: telling the founder something other than what is true about
their request. `awaiting_clarification` belongs exactly where
`awaiting_approval` already is -- the work is stopped until the founder
responds.

These tests read the shipped JavaScript as text. That is deliberate:
there is no JS test runner in this repository, and the failure being
guarded is precisely a vocabulary in one language drifting from a
vocabulary in another. A Python test that asserts the correspondence is
worth more than no test at all, and it fails on the next status added to
either side.
"""
from __future__ import annotations

import pathlib

import pytest

from master_agent.missions import execution_status as status_module

WEB = pathlib.Path(__file__).resolve().parent.parent / "desktop_app" / "web" / "js"

#: Statuses that mean "the work has stopped and only the founder can
#: restart it". Kept here as the single statement of that idea; every
#: surface below is checked against it rather than against each other.
NEEDS_FOUNDER = (
    "awaiting_approval",
    "awaiting_founder_completion",
    "awaiting_clarification",
    "blocked",
)


def read(name: str) -> str:
    path = WEB / name
    assert path.is_file(), f"{name} is not where the packaging spec expects it"
    return path.read_text(encoding="utf-8")


class TestBackendVocabulary:

    def test_the_status_exists_and_is_not_terminal(self):
        """A question is not an outcome. If this ever becomes terminal the
        founder is told their request finished because they were asked
        something."""
        assert status_module.AWAITING_CLARIFICATION == "awaiting_clarification"
        assert status_module.AWAITING_CLARIFICATION not in status_module.TERMINAL_STATUSES

    def test_it_is_reported_through_the_status_contract(self):
        state = status_module.ExecutionStatus()
        state.status = status_module.AWAITING_CLARIFICATION
        state.pending_clarification = status_module.PendingClarification(
            question="What should the folder be called?",
            key="folder_name",
            objective="Create a folder",
        )
        published = state.as_dict()

        assert published["status"] == "awaiting_clarification"
        assert published["terminal_state"] is False
        assert published["pending_clarification"]["key"] == "folder_name"


class TestSurfaceKnowsEveryWaitingStatus:
    """Each surface is checked for the whole `NEEDS_FOUNDER` set, not just
    the new member -- a test that only knew about clarification would let
    the next one drift exactly the same way."""

    @pytest.mark.parametrize("status", NEEDS_FOUNDER)
    def test_the_tree_treats_it_as_waiting_on_the_founder(self, status):
        source = read("app.js")
        head, _, _ = source.partition("if (needsFounder) return 'waiting';")
        _, _, needs_founder_block = head.rpartition("const needsFounder =")
        assert status in needs_founder_block, (
            f"app.js does not count {status!r} as needing the founder, so "
            "executionTreeState() falls through to null and the tree renders "
            "idle while the founder is being waited on"
        )

    @pytest.mark.parametrize("status", NEEDS_FOUNDER)
    def test_prominence_gives_it_the_human_required_tier(self, status):
        source = read("prominence.js")
        head, _, _ = source.partition("// 2 -- Work in flight")
        assert status in head, (
            f"prominence.js resolves {status!r} below the 'a human is "
            "required' tier, so the tree can outrank a founder who is being "
            "waited on"
        )

    @pytest.mark.parametrize("status", NEEDS_FOUNDER)
    def test_work_state_knows_the_status(self, status):
        source = read("workState.js")
        _, _, known = source.partition("var KNOWN_STATUSES = [")
        known, _, _ = known.partition("]")
        assert f"'{status}'" in known, (
            f"workState.js does not list {status!r}, so its headline comes "
            "from UNKNOWN_STATUS_FALLBACK instead of naming what is actually "
            "happening"
        )

    def test_the_clarification_headline_names_what_is_wanted(self):
        """"Working" would be a lie, and "Needs your approval" would be the
        wrong question. The founder is being asked for information."""
        source = read("workState.js")
        assert "awaiting_clarification: 'Needs your answer'" in source

    def test_the_headline_branch_distinguishes_it_from_approval(self):
        source = read("workState.js")
        assert "STATE_LANGUAGE.awaiting_clarification" in source, (
            "the waiting branch resolves clarification to some other "
            "state's wording"
        )


class TestNoStatusIsUnknownToTheSurface:

    def test_every_backend_status_is_known_to_work_state(self):
        """The whole class of defect, guarded once. Any status added to
        `execution_status.py` without teaching the surface about it fails
        here rather than in front of the founder."""
        backend = {
            value for name, value in vars(status_module).items()
            if name.isupper() and isinstance(value, str) and value.islower()
            and name not in {"UTC"}
        }
        known = read("workState.js").partition("var KNOWN_STATUSES = [")[2].partition("]")[0]
        missing = sorted(s for s in backend if f"'{s}'" not in known)
        assert not missing, (
            f"statuses the backend can report but the founder surface does "
            f"not know: {missing}"
        )
