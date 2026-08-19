"""Why Kalpavriksha chose local over AI, recoverable after the fact.

`PlanRecord.planned_by` already answered "which provider planned this?".
It could not answer the question underneath: whether a provider was asked
at all, and on what grounds. A deterministic mission and a mission whose
provider was simply unreachable both recorded `planned_by=None`, and an
FMEA pass reading the history afterwards could not tell them apart.

The Planner has returned `selected_mode`, `effective_mode` and
`mode_reason` on every `PlanOutcome` since `0f163fe`. They reached
`MissionOutcome` and `ExecutionStatus` and then stopped at the process
boundary. This is the same record, the same call site and the same source
object as `planned_by` -- so the owner was already proven and only the
field was missing.
"""
from __future__ import annotations

import pytest

from master_agent.missions.history import JsonFilePlanStore, PlanHistory, PlanRecord


class TestTheRecordCarriesTheRoutingDecision:

    def test_a_record_round_trips_its_routing_through_json(self, tmp_path):
        store = JsonFilePlanStore(tmp_path / "plan_history.json")
        store.save({
            "p1": PlanRecord(
                plan_id="p1", objective="Create folder 'X'",
                selected_mode="ai_mode", effective_mode="both",
                mode_reason="local execution required: Filesystem.CreateFolder",
            )
        })
        record = JsonFilePlanStore(tmp_path / "plan_history.json").load()["p1"]

        assert record.selected_mode == "ai_mode"
        assert record.effective_mode == "both"
        assert "Filesystem.CreateFolder" in record.mode_reason

    def test_history_written_before_routing_was_recorded_still_loads(self, tmp_path):
        """An older history must stay readable and report the routing it
        never captured as unknown, rather than failing to load."""
        path = tmp_path / "plan_history.json"
        # The real on-disk envelope as written before this change: a
        # versioned document with a `plans` list, and no routing fields.
        path.write_text(
            '{"version": 1, "plans": [{"plan_id": "p1", "objective": "old", '
            '"state": "planned", "planned_at": "", "finished_at": null, '
            '"planned_by": null, "entry_id": null, "steps": []}]}',
            encoding="utf-8",
        )
        record = JsonFilePlanStore(path).load()["p1"]
        assert record.selected_mode == ""
        assert record.objective == "old"

    def test_record_plan_accepts_the_routing_from_the_plan_outcome(self, tmp_path):
        history = PlanHistory(store=JsonFilePlanStore(tmp_path / "plan_history.json"))

        class Plan:
            steps: list = []

        record = history.record_plan(
            plan_id="obj-1", objective="Create folder 'X'", plan=Plan(),
            planned_by=None, selected_mode="local", effective_mode="local",
        )
        assert record.selected_mode == "local"
        assert record.planned_by is None


class TestTheTwoQuestionsAreDistinguishable:

    @pytest.mark.parametrize("selected,effective,provider,reading", [
        ("local", "local", None, "no provider asked, by founder choice"),
        ("both", "both", None, "local sufficed, so nothing was asked"),
        ("ai_mode", "both", None, "AI preferred, local execution required"),
        ("both", "both", "gemini.api", "reasoning genuinely needed"),
    ])
    def test_each_routing_outcome_is_recoverable(self, tmp_path, selected, effective, provider, reading):
        """`planned_by=None` alone is ambiguous. Paired with the mode it
        becomes a specific, readable fact."""
        store = JsonFilePlanStore(tmp_path / f"h_{selected}_{effective}.json")
        store.save({"p": PlanRecord(
            plan_id="p", objective="o", planned_by=provider,
            selected_mode=selected, effective_mode=effective,
        )})
        record = store.load()["p"]
        assert (record.selected_mode, record.effective_mode, record.planned_by) == (
            selected, effective, provider
        ), reading

    def test_the_founder_preference_is_not_overwritten_by_the_effective_mode(self, tmp_path):
        """The mission escalates; the founder's selection stays where they
        put it -- and the record must show both, not one merged value."""
        store = JsonFilePlanStore(tmp_path / "h.json")
        store.save({"p": PlanRecord(plan_id="p", objective="o",
                                    selected_mode="ai_mode", effective_mode="both")})
        record = store.load()["p"]
        assert record.selected_mode != record.effective_mode
