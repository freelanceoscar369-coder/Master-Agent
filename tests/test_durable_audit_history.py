"""What happened must outlive the process it happened in.

The founder's last real session could not be audited after Kalpavriksha
exited: the desktop composition persisted nothing. No event log, no plan
history, no snapshot. Every question worth asking afterwards -- which
mission ran, which capability executed, was it verified, how long did it
take -- was unanswerable, because the only record was in memory and the
memory was gone.

None of that needed new architecture. `PersistenceService` has appended
bus events to a durable log since MB025, and `PlanHistory` has recorded
one row per mission with an entry per step since MB037. `launcher/boot
.py` wires both. The desktop composition simply never constructed them.

These tests assert the wiring, and -- more importantly -- that the data
left behind is actually sufficient to reconstruct a session.
"""
from __future__ import annotations

import inspect
import json
import os
from pathlib import Path

import pytest

import kalpavriksha_desktop as kd


class TestTheStoreLivesOutsideTheRepository:

    def test_state_goes_to_the_application_data_directory(self):
        """Never into the source tree, `build/`, `dist/` or a pytest cache
        -- a history that a rebuild deletes is not a history."""
        state = kd._app_state_dir()
        assert state.is_absolute()
        assert "Kalpavriksha" in str(state)
        repo = Path(kd.__file__).resolve().parent
        assert repo not in state.parents and state != repo

    def test_packaged_and_source_runs_resolve_the_same_store(self):
        """The path is derived from the environment, not from where the
        code happens to live, so a founder's history does not split in two
        when they switch between the exe and a source run."""
        source = inspect.getsource(kd._app_state_dir)
        assert "LOCALAPPDATA" in source
        assert "_MEIPASS" not in source


class TestTheDesktopCompositionRecordsHistory:

    def test_it_wires_the_existing_persistence_service_and_plan_history(self):
        source = inspect.getsource(kd._build_mission_pipeline)
        assert "PersistenceService(" in source
        assert "start_recording()" in source
        assert "PlanHistory(" in source
        assert "attach_to(mission_control)" in source
        assert "history=plan_history" in source

    def test_it_does_not_restore_missions_into_the_runtime(self):
        """Auditability is not crash recovery. Recording what happened
        must not quietly become resuming what was interrupted -- that is a
        separate decision with its own safety argument."""
        import ast
        import textwrap

        # Comments explaining WHY recovery is not wired legitimately name
        # it; `ast.unparse` drops them, so this checks the code that runs.
        code = ast.unparse(
            ast.parse(textwrap.dedent(inspect.getsource(kd._build_mission_pipeline)))
        )
        assert "restore_into(" not in code
        assert "recover(" not in code


class TestPersistedHistoryIsSufficientToReconstructASession:
    """Written by one process, read by another -- the property the founder
    actually needs. `tmp_path` stands in for the app-data directory so the
    test never touches a real founder's history."""

    @pytest.fixture
    def session(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        pipeline = kd._build_mission_pipeline()
        if pipeline is None:
            pytest.skip("no reasoning provider configured; pipeline not built")
        return pipeline, tmp_path / "Kalpavriksha" / "state"

    def test_three_missions_persist_as_three_distinct_records(self, session):
        """Guards `0c34a7c` in the durable data, not only in memory: three
        folder missions of identical shape must not collapse into one."""
        (ms, rt, mc, st, _runner, set_mode, _log, _approve), state = session
        set_mode("local")
        for tag in ("A", "B", "C"):
            kd._submit_objective(
                ms, rt, mc, st, f"Create a folder called KVHist{tag} in Documents",
                timeout_seconds=30.0,
            )

        from master_agent.missions.history import JsonFilePlanStore

        records = JsonFilePlanStore(state / "plan_history.json").load()
        assert len(records) == 3, "missions were attributed to the wrong objective"

        objectives = {r.objective for r in records.values()}
        assert len(objectives) == 3
        step_ids = {s.step_id for r in records.values() for s in r.steps}
        assert len(step_ids) == 3, "two missions share a task identity"

    def test_the_record_answers_what_ran_and_whether_it_finished(self, session):
        (ms, rt, mc, st, _runner, set_mode, _log, _approve), state = session
        set_mode("local")
        kd._submit_objective(
            ms, rt, mc, st, "Create a folder called KVHistOne in Documents",
            timeout_seconds=30.0,
        )

        from master_agent.missions.history import JsonFilePlanStore

        record = next(iter(JsonFilePlanStore(state / "plan_history.json").load().values()))
        assert "KVHistOne" in record.objective
        assert record.state == "completed"
        assert record.planned_at and record.finished_at
        assert record.steps[0].capability == "Filesystem.CreateFolder"

    def test_the_event_log_carries_the_whole_lifecycle_with_correlation(self, session):
        (ms, rt, mc, st, _runner, set_mode, _log, _approve), state = session
        set_mode("local")
        kd._submit_objective(
            ms, rt, mc, st, "Create a folder called KVHistTwo in Documents",
            timeout_seconds=30.0,
        )

        lines = (state / "events.jsonl").read_text(encoding="utf-8").splitlines()
        events = [json.loads(line) for line in lines if line.strip()]
        kinds = {e["event_type"] for e in events}

        # The phases a later investigation has to be able to see.
        for phase in ("objective_submitted", "task_started", "task_completed",
                      "verification_started", "verification_completed",
                      "objective_completed"):
            assert phase in kinds, f"{phase} is absent; the lifecycle cannot be reconstructed"

        # Correlation, not chronological proximity (§5).
        assert any(e.get("objective_id") for e in events)
        assert any(e.get("task_id") for e in events)
        assert all(e.get("occurred_at") for e in events)

    def test_no_secret_is_written_to_history(self, session):
        """§20 -- the store must not become a convenient place for a key
        to end up."""
        (ms, rt, mc, st, _runner, set_mode, _log, _approve), state = session
        set_mode("local")
        kd._submit_objective(
            ms, rt, mc, st, "Create a folder called KVHistSafe in Documents",
            timeout_seconds=30.0,
        )
        written = (state / "events.jsonl").read_text(encoding="utf-8")
        key = os.environ.get("GEMINI_API_KEY", "")
        if key:
            assert key not in written
        for marker in ("api_key", "GEMINI_API_KEY", "Authorization", "password", "token"):
            assert marker not in written
