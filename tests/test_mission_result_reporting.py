"""A step's output is not a mission result.

The first AI-planned mission Onkar ever ran researched the printing
press, wrote the file, verified, and told him:

    [object Object]

Underneath that was `{'session_id': 'research_session', 'closed': True}`
-- the output of `Browser.CloseBrowserSession`, the fifth and final step
of a five-step plan. The research succeeded; the sentence describing it
came from the cleanup.

`FounderState.result` is `_last_result()`: the LAST task's output. For a
one-step mission that is genuinely the mission's answer -- a folder
mission's last output is the path, exactly what Onkar wanted -- and every
packaged mission until this one was single-step, so the conflation never
showed.

These tests hold the distinction: the founder is told about the mission,
never handed an implementation step's internals.
"""
from __future__ import annotations

import pytest

import kalpavriksha_desktop as kd

OBJECTIVE = "Research the history of the printing press"
CLEANUP = {"session_id": "research_session", "closed": True}


class TestNoRawStructureReachesTheFounder:

    @pytest.mark.parametrize("leaked", [
        CLEANUP,
        {"ok": True},
        [1, 2, 3],
        ("a", "b"),
        b"bytes",
        {"nested": {"deep": True}},
    ])
    def test_implementation_detail_is_never_stringified(self, leaked):
        spoken = kd._describe_result(leaked, OBJECTIVE)
        for marker in ("{", "}", "[", "]", "session_id", "closed", "b'"):
            assert marker not in spoken, f"{marker!r} leaked to the founder: {spoken!r}"

    def test_the_founder_is_told_what_the_mission_was(self):
        assert kd._describe_result(CLEANUP, OBJECTIVE) == f"Done — {OBJECTIVE}."

    def test_the_exact_observed_defect_cannot_recur(self):
        """The literal value Onkar was shown."""
        spoken = kd._describe_result(CLEANUP, OBJECTIVE)
        assert spoken != str(CLEANUP)
        assert "research_session" not in spoken


class TestSingleStepBehaviourIsPreserved:
    """Test A -- no regression on the path that always worked."""

    def test_a_folder_path_is_still_spoken_as_itself(self):
        path = r"C:\Users\DELL\Desktop\KVX"
        assert kd._describe_result(path, "Create folder KVX") == path

    def test_a_browser_observation_keeps_its_sentence(self):
        spoken = kd._describe_result(
            {"url": "https://example.com", "title": "Example"}, "open example"
        )
        assert "https://example.com" in spoken and "Example" in spoken


class TestItInventsNothing:
    """Part 5 -- the report may state only what evidence supports."""

    @pytest.mark.parametrize("claim", [
        "saved", "wrote", "file", "verified", "researched", "successfully",
    ])
    def test_no_unevidenced_claim_is_added(self, claim):
        spoken = kd._describe_result(CLEANUP, OBJECTIVE).lower()
        assert claim not in spoken.replace(OBJECTIVE.lower(), "")

    def test_an_absent_result_does_not_become_a_success_story(self):
        assert kd._describe_result(None, OBJECTIVE) == f"Done — {OBJECTIVE}."
        assert kd._describe_result(None, "") == "Done."

    def test_it_does_not_summarise_what_it_cannot_see(self):
        """This helper has no authority to summarise and does not acquire
        it here -- it only stops repeating something meaningless."""
        import inspect

        source = inspect.getsource(kd._describe_result)
        for forbidden in ("runner", "advise(", "provider", "llm", "model"):
            assert forbidden not in source.lower().split('"""')[-1]


class TestFailureIsNotReportedAsSuccess:
    """Test D -- the failure path is a different function and must stay
    that way; a failed mission never reaches `_describe_result`."""

    def test_a_failed_mission_uses_the_failure_sentence(self):
        spoken = kd._founder_failure_sentence("playwright timed out")
        assert "playwright" not in spoken.lower()
        assert "done" not in spoken.lower()
