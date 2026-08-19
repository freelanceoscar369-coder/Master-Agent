"""Which providers were tried, in what order, and why the first ones did not answer.

The packaged Simple E2E FMEA could prove the *winning* Broker decision was
durable and could not prove the sequence above it. `TieredPromptRunner`
has recorded that sequence on `last_attempts` since it was written --
"report which tier actually handled the request, not just a final yes/no"
-- and a grep across the repository showed nothing ever read it, so it was
overwritten by the next call and never survived the process.

`planned_by` names the provider that ANSWERED. These name the ones tried
before it. Empty attempts is itself an answer: nobody was asked, so the
mission was deterministic.
"""
from __future__ import annotations

import json

import pytest

from master_agent.missions.history import JsonFilePlanStore, PlanHistory, PlanRecord
from master_agent.planner.planner import _attempt_trail


class FakeOutcome:
    def __init__(self, ok, provider_id, reason=""):
        self.ok = ok
        self.provider_id = provider_id
        self.reason = reason


class FakeAttempt:
    def __init__(self, tier, attempted, considered, outcome):
        self.tier = tier
        self.attempted = attempted
        self.provider_ids_considered = tuple(considered)
        self.outcome = outcome


class FakeRunner:
    """Stands in for `TieredPromptRunner` with a deterministic ladder:
    the cloud tier fails, the desktop tier answers. No real provider is
    contacted and no credential is touched."""

    last_attempts = [
        FakeAttempt("cloud", True, ["gemini.api"],
                    FakeOutcome(False, "gemini.api", "HTTP 429 quota exceeded")),
        FakeAttempt("desktop", True, ["chatgpt-desktop", "kimi-desktop"],
                    FakeOutcome(True, "chatgpt-desktop")),
        FakeAttempt("browser", False, [], None),
    ]


class TestTheTrailIsStructuredMetadata:

    def test_it_preserves_order_tier_and_outcome(self):
        trail = _attempt_trail(FakeRunner())
        assert [a["order"] for a in trail] == [1, 2, 3]
        assert [a["tier"] for a in trail] == ["cloud", "desktop", "browser"]
        assert trail[0]["ok"] is False and trail[1]["ok"] is True
        assert trail[2]["attempted"] is False

    def test_it_names_the_failure_and_the_provider_that_answered(self):
        trail = _attempt_trail(FakeRunner())
        assert "429" in trail[0]["reason"]
        assert trail[0]["provider_id"] == "gemini.api"
        assert trail[1]["provider_id"] == "chatgpt-desktop"

    def test_it_records_who_was_considered_not_only_who_won(self):
        trail = _attempt_trail(FakeRunner())
        assert "kimi-desktop" in trail[1]["considered"]

    def test_a_runner_that_kept_no_trail_is_not_an_error(self):
        class Bare:
            pass

        assert _attempt_trail(Bare()) == ()

    def test_no_prompt_or_response_text_is_captured(self):
        """Metadata only. Persisting the content of every reasoning call
        would be a privacy decision nobody has made."""
        for attempt in _attempt_trail(FakeRunner()):
            assert set(attempt) == {
                "order", "tier", "attempted", "considered",
                "provider_id", "ok", "reason",
            }
            assert "prompt" not in attempt and "text" not in attempt


class TestTheTrailSurvivesSerialisation:

    def test_a_fallback_chain_round_trips_through_json(self, tmp_path):
        path = tmp_path / "plan_history.json"
        JsonFilePlanStore(path).save({"p1": PlanRecord(
            plan_id="p1", objective="reason about something",
            planned_by="chatgpt-desktop",
            attempts=list(_attempt_trail(FakeRunner())),
        )})

        record = JsonFilePlanStore(path).load()["p1"]
        assert [a["tier"] for a in record.attempts] == ["cloud", "desktop", "browser"]
        assert record.attempts[0]["ok"] is False
        assert record.attempts[1]["provider_id"] == record.planned_by

    def test_a_deterministic_mission_records_an_empty_trail(self, tmp_path):
        """The absence is the evidence: no provider was asked at all."""
        path = tmp_path / "plan_history.json"
        JsonFilePlanStore(path).save({"p1": PlanRecord(
            plan_id="p1", objective="Create folder 'X'", planned_by=None,
        )})
        record = JsonFilePlanStore(path).load()["p1"]
        assert record.attempts == []
        assert record.planned_by is None

    def test_history_written_before_attempts_existed_still_loads(self, tmp_path):
        path = tmp_path / "plan_history.json"
        path.write_text(
            '{"version": 1, "plans": [{"plan_id": "p1", "objective": "old", '
            '"state": "planned", "planned_at": "", "finished_at": null, '
            '"planned_by": null, "entry_id": null, "steps": []}]}',
            encoding="utf-8",
        )
        assert JsonFilePlanStore(path).load()["p1"].attempts == []

    def test_record_plan_carries_the_trail(self, tmp_path):
        history = PlanHistory(store=JsonFilePlanStore(tmp_path / "h.json"))

        class Plan:
            steps: list = []

        record = history.record_plan(
            plan_id="obj-1", objective="o", plan=Plan(),
            attempts=_attempt_trail(FakeRunner()),
        )
        assert len(record.attempts) == 3

    def test_no_credential_appears_in_the_serialised_trail(self, tmp_path):
        path = tmp_path / "h.json"
        JsonFilePlanStore(path).save({"p": PlanRecord(
            plan_id="p", objective="o", attempts=list(_attempt_trail(FakeRunner())),
        )})
        written = path.read_text(encoding="utf-8").lower()
        for marker in ("api_key", "authorization", "bearer", "password", "cookie"):
            assert marker not in written
