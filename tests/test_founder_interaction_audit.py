"""What Onkar said, and what Somesh showed him, must survive the process.

A founder used Kalpavriksha for a real session and asked afterwards what
went wrong. Nothing could be answered. `cbf5b2a` made missions durable,
but two of the three things the founder did that day -- saying good
morning, and asking what Kalpavriksha could do -- created no mission and
left no trace at all.

ADR-0025 authorises recording both sides of the conversation, and is
equally explicit about what the resulting data may never become. The
tests below cover both halves: that it persists, and that it stays out of
Memory, Knowledge, and the Brain.
"""
from __future__ import annotations

import json
import os

import pytest

from master_agent.audit import (
    CHIEF_OF_STAFF,
    FILENAME,
    FOUNDER,
    InteractionLog,
    JsonlInteractionStore,
)


@pytest.fixture
def log(tmp_path):
    return InteractionLog(JsonlInteractionStore(tmp_path / FILENAME))


class TestItSurvivesTheProcess:

    def test_a_conversation_that_creates_no_mission_is_still_recorded(self, tmp_path, log):
        """The exact gap that made the founder's session unauditable."""
        log.founder_said("Good afternoon", interaction_type="conversation")
        log.founder_was_shown("Good afternoon, Onkar. Somesh here.",
                              interaction_type="conversation")

        reread = JsonlInteractionStore(tmp_path / FILENAME).read()
        assert [r.direction for r in reread] == [FOUNDER, CHIEF_OF_STAFF]
        assert "Good afternoon" in reread[0].text

    def test_a_capability_query_is_recorded(self, tmp_path, log):
        log.founder_said("Tell me what capabilities you currently have.",
                         interaction_type="capability_query")
        assert JsonlInteractionStore(tmp_path / FILENAME).read()[0].interaction_type == "capability_query"

    def test_what_the_founder_was_shown_is_recorded_with_the_status(self, tmp_path, log):
        """The defect class this exists to prove or disprove: backend
        verified success, founder saw "still working"."""
        log.founder_was_shown("That's taking longer than expected; still working on it.",
                              interaction_type="mission_result",
                              status="awaiting_founder_completion",
                              mission_id="obj-1")
        record = JsonlInteractionStore(tmp_path / FILENAME).read()[0]
        assert record.status == "awaiting_founder_completion"
        assert record.mission_id == "obj-1"

    def test_records_carry_correlation_not_just_order(self, tmp_path, log):
        log.founder_said("Create a folder", interaction_type="mission_request",
                         clarification_id="c-1")
        record = JsonlInteractionStore(tmp_path / FILENAME).read()[0]
        assert record.clarification_id == "c-1"
        assert record.interaction_id and record.session_id and record.at

    def test_one_session_id_spans_many_turns(self, tmp_path, log):
        for i in range(4):
            log.founder_said(f"turn {i}")
        sessions = {r.session_id for r in JsonlInteractionStore(tmp_path / FILENAME).read()}
        assert len(sessions) == 1

    def test_a_new_log_is_a_new_session_but_old_records_remain(self, tmp_path):
        first = InteractionLog(JsonlInteractionStore(tmp_path / FILENAME))
        first.founder_said("session one")
        second = InteractionLog(JsonlInteractionStore(tmp_path / FILENAME))
        second.founder_said("session two")

        records = JsonlInteractionStore(tmp_path / FILENAME).read()
        assert len(records) == 2
        assert first.session_id != second.session_id


class TestItIsAppendOnlyAndSafe:

    def test_a_correction_is_a_new_record_never_an_overwrite(self, tmp_path, log):
        log.founder_was_shown("still working")
        log.founder_was_shown("actually, done")
        assert len(JsonlInteractionStore(tmp_path / FILENAME).read()) == 2

    def test_one_corrupt_line_does_not_hide_the_session(self, tmp_path, log):
        log.founder_said("real turn")
        with (tmp_path / FILENAME).open("a", encoding="utf-8") as fh:
            fh.write("{not json\n")
        log.founder_said("later turn")
        assert len(JsonlInteractionStore(tmp_path / FILENAME).read()) == 2

    def test_a_failing_store_never_breaks_the_founders_request(self, tmp_path):
        class Broken:
            def append(self, record):
                raise OSError("disk full")

        assert InteractionLog(Broken()).founder_said("hello") is None

    def test_two_people_not_two_roles(self):
        assert FOUNDER == "founder" and CHIEF_OF_STAFF == "chief_of_staff"
        assert "user" not in (FOUNDER, CHIEF_OF_STAFF)
        assert "assistant" not in (FOUNDER, CHIEF_OF_STAFF)


class TestAdr0025Separation:
    """The load-bearing half of ADR-0025: the trail must not become a
    memory system, and the rule is structural rather than promised."""

    def test_the_brain_planner_and_runtime_never_read_it(self):
        import pathlib

        src = pathlib.Path(__file__).resolve().parent.parent / "src" / "master_agent"
        offenders = []
        for area in ("brain", "planner", "runtime", "missions", "memory", "conversation_engine"):
            for path in (src / area).rglob("*.py"):
                if "master_agent.audit" in path.read_text(encoding="utf-8"):
                    offenders.append(str(path.relative_to(src)))
        assert not offenders, (
            f"{offenders} reads the interaction audit -- a transcript the "
            "Brain can consult during reasoning is Memory by another name "
            "(ADR-0025)"
        )

    def test_it_is_not_inside_the_memory_package(self):
        import master_agent.audit as audit

        assert not audit.__name__.startswith("master_agent.memory")

    def test_it_writes_no_infrastructure_secret(self, tmp_path, log):
        log.founder_said("my key is irrelevant here")
        written = (tmp_path / FILENAME).read_text(encoding="utf-8")
        for marker in ("api_key", "GEMINI_API_KEY", "Authorization", "password", "token"):
            assert marker not in written
        key = os.environ.get("GEMINI_API_KEY", "")
        if key:
            assert key not in written

    def test_records_are_plain_json_an_investigator_can_read(self, tmp_path, log):
        log.founder_said("hello")
        line = (tmp_path / FILENAME).read_text(encoding="utf-8").splitlines()[0]
        assert set(json.loads(line)) >= {"direction", "text", "at", "session_id"}
