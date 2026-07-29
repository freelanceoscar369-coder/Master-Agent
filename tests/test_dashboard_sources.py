"""Contract tests — the Dashboard reading real, published surfaces, and
degrading honestly when it cannot (MB026 Rules 2 and 3).

These use real systems rather than fakes: the claim under test is that the
Dashboard works against published contracts, and a fake shaped for the
Dashboard would not test that.
"""
from __future__ import annotations

import pytest

from master_agent.dashboard.sources import DashboardSources
from master_agent.mission_control.mission_control import MissionControl
from master_agent.persistence.recovery import RecoveryReport
from tests.dashboard_test_support import System


@pytest.fixture
def dirs(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    return tmp_path / "state", work


@pytest.fixture
def system(dirs):
    state, work = dirs
    return System(state, work)


# ---- fully wired --------------------------------------------------------


def test_collect_produces_a_complete_snapshot(system):
    system.submit()
    system.run()
    snapshot = DashboardSources(
        mission_control=system.mission_control,
        runtime=system.engine,
        persistence=system.service,
    ).collect()

    assert snapshot.runtime.status.available
    assert snapshot.mission.status.available
    assert snapshot.executives.status.available
    assert snapshot.capabilities.status.available
    assert snapshot.audit.status.available
    assert snapshot.persistence.status.available
    assert snapshot.founder_state.status.available


def test_runtime_panel_reads_every_field_from_runtime_health(system):
    system.submit()
    system.run()
    runtime = DashboardSources(runtime=system.engine).collect().runtime

    assert runtime.state is not None
    assert runtime.active_cycle is not None
    assert runtime.queue_length is not None
    assert runtime.uptime_seconds is not None


def test_mission_panel_reads_from_published_founder_state(system):
    system.submit("Increase Founder Net Worth")
    system.run()
    mission = DashboardSources(mission_control=system.mission_control).collect().mission

    assert mission.objective == "Increase Founder Net Worth"
    assert mission.progress is not None
    assert mission.objective_id is not None


def test_mission_status_comes_from_the_objectives_own_properties(system):
    system.submit()
    system.run()
    mission = DashboardSources(mission_control=system.mission_control).collect().mission
    assert mission.mission_status in {"in progress", "completed", "attention required"}


def test_mission_status_reports_completion(dirs):
    state, work = dirs
    system = System(state, work, max_cycles=6)
    system.submit()
    system.run()
    mission = DashboardSources(mission_control=system.mission_control).collect().mission
    assert mission.mission_status == "completed"


def test_executive_panel_reads_the_real_registry(system):
    executives = DashboardSources(mission_control=system.mission_control).collect().executives
    assert len(executives.executives) == 1
    row = executives.executives[0]
    assert row.executive_id == "filesystem"
    assert row.capability_count == 14
    assert row.health == "healthy"
    assert row.state == "ready"


def test_capability_panel_counts_task_states_across_objectives(system):
    system.submit()
    system.run()
    capabilities = (
        DashboardSources(mission_control=system.mission_control).collect().capabilities
    )
    assert len(capabilities.registered) == 14
    assert capabilities.completed is not None
    assert capabilities.pending is not None


def test_audit_panel_reads_real_audit_entries(system):
    system.submit()
    system.run()
    audit = DashboardSources(mission_control=system.mission_control).collect().audit

    assert audit.total_entries and audit.total_entries > 0
    assert audit.recent
    assert audit.recent[-1].sequence == audit.total_entries - 1


def test_audit_window_bounds_what_is_carried_into_the_snapshot(system):
    system.submit()
    system.run()
    audit = (
        DashboardSources(mission_control=system.mission_control, audit_window=5)
        .collect()
        .audit
    )
    assert len(audit.recent) == 5
    assert audit.total_entries > 5


def test_persistence_panel_reads_snapshot_and_log(system):
    system.submit()
    system.run()
    system.save()
    persistence = DashboardSources(persistence=system.service).collect().persistence

    assert persistence.snapshot_schema_version == 1
    assert persistence.event_log_size and persistence.event_log_size > 0
    assert persistence.last_checkpoint_at is not None


def test_recovery_status_is_taken_from_the_handed_in_report(system):
    """ADR-0016 Decision 5: the Dashboard never calls recover()."""
    report = RecoveryReport(recovered=True, source="snapshot", quarantined_tasks=2)
    persistence = (
        DashboardSources(persistence=system.service, recovery_report=report)
        .collect()
        .persistence
    )
    assert persistence.recovery_status == "recovered"
    assert persistence.recovery_source == "snapshot"
    assert persistence.quarantined_tasks == 2


def test_no_recovery_report_means_unknown_recovery_not_a_fabricated_one(system):
    persistence = DashboardSources(persistence=system.service).collect().persistence
    assert persistence.recovery_status is None


def test_founder_state_panel_carries_the_published_dict_verbatim(system):
    system.submit()
    published = system.mission_control.founder_state().as_dict()
    panel = DashboardSources(mission_control=system.mission_control).collect().founder_state
    assert panel.state == published


# ---- missing data (Rule 3) ---------------------------------------------


def test_nothing_wired_still_produces_a_complete_frame_worth_of_data():
    snapshot = DashboardSources().collect()
    assert snapshot.captured_at is not None
    for panel in (
        snapshot.runtime,
        snapshot.mission,
        snapshot.executives,
        snapshot.capabilities,
        snapshot.audit,
        snapshot.persistence,
        snapshot.founder_state,
    ):
        assert panel.status.available is False
        assert panel.status.reason


def test_a_missing_runtime_never_fabricates_runtime_numbers():
    runtime = DashboardSources(mission_control=MissionControl()).collect().runtime
    assert runtime.state is None
    assert runtime.active_cycle is None
    assert runtime.queue_length is None


def test_a_runtime_that_raises_becomes_absent_data_not_a_crash():
    class Broken:
        def health(self):
            raise RuntimeError("sensors offline")

    runtime = DashboardSources(runtime=Broken()).collect().runtime
    assert runtime.status.available is False
    assert "sensors offline" in runtime.status.reason


def test_a_mission_control_that_raises_becomes_absent_data():
    class Broken:
        def founder_state(self):
            raise RuntimeError("nope")

        @property
        def executives(self):
            raise RuntimeError("nope")

        @property
        def capabilities(self):
            raise RuntimeError("nope")

        @property
        def audit(self):
            raise RuntimeError("nope")

    snapshot = DashboardSources(mission_control=Broken()).collect()
    assert snapshot.mission.status.available is False
    assert snapshot.executives.status.available is False
    assert snapshot.capabilities.status.available is False
    assert snapshot.audit.status.available is False


def test_a_corrupt_snapshot_does_not_blank_the_persistence_panel(system, dirs):
    """A corrupt snapshot is reported; the event log is still counted."""
    from master_agent.persistence.schema import SnapshotEnvelope

    system.submit()
    system.run()
    system.save()
    system.service.store.save_snapshot(
        SnapshotEnvelope(payload={"tampered": True}, checksum="wrong")
    )

    persistence = DashboardSources(persistence=system.service).collect().persistence
    assert persistence.snapshot_schema_version is None
    assert persistence.event_log_size and persistence.event_log_size > 0


def test_a_persistence_layer_that_raises_everywhere_degrades_cleanly():
    class Broken:
        def load(self):
            raise RuntimeError("x")

        def load_checkpoint(self):
            raise RuntimeError("x")

        @property
        def store(self):
            raise RuntimeError("x")

    persistence = DashboardSources(persistence=Broken()).collect().persistence
    assert persistence.snapshot_schema_version is None
    assert persistence.event_log_size is None
    assert persistence.last_checkpoint_at is None


# ---- system health composition -----------------------------------------


def test_system_health_is_composed_from_already_collected_data(system):
    """One read, so the health line can never disagree with the panels
    above it."""
    system.submit()
    system.run()
    snapshot = DashboardSources(
        mission_control=system.mission_control,
        runtime=system.engine,
        persistence=system.service,
    ).collect()

    assert snapshot.system_health.executives_online == snapshot.runtime.executives_online
    assert snapshot.system_health.runtime_health is not None


def test_system_health_reports_unknown_when_nothing_is_wired():
    health = DashboardSources().collect().system_health
    assert health.runtime_health == "unknown"
    assert health.audit_health == "unknown"
    assert health.persistence_health == "unknown"


def test_the_snapshot_timestamp_uses_the_injected_clock():
    from tests.dashboard_test_support import FIXED_NOW

    snapshot = DashboardSources(clock=lambda: FIXED_NOW).collect()
    assert snapshot.captured_at == FIXED_NOW
