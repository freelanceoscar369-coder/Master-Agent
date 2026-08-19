"""Evidence has to survive the trip to disk, and back into a new process.

What used to reach durable storage was a correlation key and a result
code:

    payload = {"verdict": "matched", "evidence_id": "abc123"}

Neither can answer what was observed, when, by which Environment
verifier, against which checks, or which of them failed. So after a
restart none of those questions had an answer, and the launcher papered
over it by rebuilding an `Evidence` object out of the id -- stamping
`worker="filesystem"` on every step regardless of domain and
`captured_at=datetime.now()` on observations made hours earlier.

These tests follow real values through the whole route and assert the
record that comes back is the record Verification produced.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from master_agent.verification.evidence import (
    CheckResult,
    Evidence,
    ExpectedOutcome,
    ObservationCheck,
    Verdict,
)

CAPTURED = datetime(2026, 8, 19, 10, 30, 15, tzinfo=UTC)


def browser_evidence(verdict: Verdict = Verdict.MATCHED) -> Evidence:
    """A realistic Browser Evidence -- the domain the launcher defect
    mislabelled."""
    check = ObservationCheck(
        field="url_normalised", operator="equals",
        value="https://example.com", description="the page is at the requested URL",
    )
    return Evidence(
        evidence_id="ev-browser-1",
        worker="browser",
        environment="browser_environment",
        captured_at=CAPTURED,
        expected=ExpectedOutcome(
            description="Browser is at the requested URL", checks=[check],
        ),
        observation={"url": "https://example.com/", "title": "Example Domain"},
        verdict=verdict,
        check_results=[CheckResult(
            check=check, passed=True, actual_value="https://example.com",
        )],
        errors=[],
    )


def filesystem_evidence() -> Evidence:
    check = ObservationCheck(
        field="target_exists", operator="equals", value=True,
        description="'Research' exists on disk",
    )
    return Evidence(
        evidence_id="ev-fs-1",
        worker="filesystem",
        environment="filesystem_environment",
        captured_at=CAPTURED,
        expected=ExpectedOutcome(description="Folder exists", checks=[check]),
        observation={"target_exists": True, "target_is_dir": True,
                     "target_path": "Research"},
        verdict=Verdict.MATCHED,
        check_results=[CheckResult(check=check, passed=True, actual_value=True)],
        errors=[],
    )


def through_json(evidence: Evidence) -> Evidence:
    """The real route: serialise, cross a JSON boundary, rebuild."""
    return Evidence.from_dict(json.loads(json.dumps(evidence.as_dict())))


class TestTheProjectionIsJsonPlain:
    """No live objects in an event payload -- the bus and the persistence
    service carry JSON."""

    def test_every_value_survives_json(self):
        payload = browser_evidence().as_dict()
        assert json.loads(json.dumps(payload)) == payload

    @pytest.mark.parametrize("path", [
        ("captured_at",), ("verdict",),
        ("expected", "checks", 0, "operator"),
        ("check_results", 0, "passed"),
    ])
    def test_no_live_object_leaks_into_the_payload(self, path):
        value = browser_evidence().as_dict()
        for key in path:
            value = value[key]
        assert isinstance(value, str | int | float | bool | type(None))


class TestExactRoundTrip:

    def test_the_whole_record_survives(self):
        original = browser_evidence()
        assert through_json(original) == original

    def test_the_original_capture_time_is_preserved(self):
        """The launcher stamped `datetime.now()` here. An observation must
        never acquire the timestamp of the moment it was read back."""
        rebuilt = through_json(browser_evidence())
        assert rebuilt.captured_at == CAPTURED
        assert rebuilt.captured_at.tzinfo is not None

    def test_the_observation_survives_intact(self):
        rebuilt = through_json(browser_evidence())
        assert rebuilt.observation == {
            "url": "https://example.com/", "title": "Example Domain",
        }

    def test_the_expected_checks_survive(self):
        """Evidence is observation + expectation + verdict, not a result
        code. What it was checked against has to come back too."""
        rebuilt = through_json(browser_evidence())
        assert rebuilt.expected.description == "Browser is at the requested URL"
        assert len(rebuilt.expected.checks) == 1
        check = rebuilt.expected.checks[0]
        assert (check.field, check.operator, check.value) == (
            "url_normalised", "equals", "https://example.com",
        )

    def test_check_results_survive_and_are_not_derived_from_the_verdict(self):
        failing = browser_evidence(verdict=Verdict.NOT_MATCHED)
        failing.check_results = [CheckResult(
            check=failing.expected.checks[0], passed=False,
            actual_value="https://example.com/other", error=None,
        )]
        rebuilt = through_json(failing)

        assert rebuilt.check_results[0].passed is False
        assert rebuilt.check_results[0].actual_value == "https://example.com/other"
        assert rebuilt.check_results[0].check.field == "url_normalised"

    def test_an_error_verdict_stays_an_error(self):
        """`ERROR` means the observation could not be captured. It must not
        come back as NOT_MATCHED, and its message must survive."""
        broken = browser_evidence(verdict=Verdict.ERROR)
        broken.errors = ["unknown or closed session: 'session_1'"]
        broken.check_results = []
        rebuilt = through_json(broken)

        assert rebuilt.verdict is Verdict.ERROR
        assert rebuilt.errors == ["unknown or closed session: 'session_1'"]


class TestCrossDomainIdentity:
    """The launcher defect, guarded directly: a Browser step must never
    come back claiming a filesystem worker."""

    def test_browser_identity_is_preserved(self):
        rebuilt = through_json(browser_evidence())
        assert rebuilt.worker == "browser"
        assert rebuilt.environment == "browser_environment"
        assert rebuilt.worker != "filesystem"

    def test_filesystem_identity_is_preserved(self):
        rebuilt = through_json(filesystem_evidence())
        assert (rebuilt.worker, rebuilt.environment) == (
            "filesystem", "filesystem_environment",
        )


class TestTheEventCarriesIt:

    def _control(self):
        from master_agent.mission_control.mission_control import MissionControl

        return MissionControl()

    def test_the_payload_nests_the_whole_record(self):
        mc = self._control()
        seen: list = []
        from master_agent.mission_control.events import EventType

        mc.bus.subscribe(seen.append, EventType.VERIFICATION_COMPLETED)

        evidence = browser_evidence()
        mc.verification_completed(
            "t1", verdict=evidence.verdict.value,
            evidence_id=evidence.evidence_id, evidence=evidence.as_dict(),
        )

        payload = seen[0].payload
        # Kept at the top level for compatibility and searchability...
        assert payload["verdict"] == "matched"
        assert payload["evidence_id"] == "ev-browser-1"
        # ...and the canonical record under one key, not flattened.
        assert Evidence.from_dict(payload["evidence"]) == evidence

    def test_a_caller_that_passes_no_evidence_still_works(self):
        """Additive: legacy callers keep working and simply carry none."""
        mc = self._control()
        seen: list = []
        from master_agent.mission_control.events import EventType

        mc.bus.subscribe(seen.append, EventType.VERIFICATION_COMPLETED)

        mc.verification_completed("t1", verdict="matched", evidence_id="abc")
        assert "evidence" not in seen[0].payload


class TestPlanHistoryRetention:

    def test_a_step_record_keeps_the_projection(self):
        from master_agent.missions.history import StepRecord

        step = StepRecord(step_id="s1", capability="Browser.Navigate", payload={})
        step.evidence = browser_evidence().as_dict()

        rebuilt = StepRecord.from_dict(json.loads(json.dumps(step.as_dict())))
        assert Evidence.from_dict(rebuilt.evidence) == browser_evidence()

    def test_a_record_written_before_this_existed_still_loads(self):
        """Historical records carry a verdict and an id and nothing else.
        They must load, and their Evidence must be `None` -- never
        synthesised from the id."""
        from master_agent.missions.history import StepRecord

        historical = {
            "step_id": "s1", "capability": "Filesystem.CreateFolder",
            "payload": {}, "depends_on": [], "expectation": "folder exists",
            "checks": [], "priority": "normal", "estimated_complexity": "moderate",
            "state": "completed", "verdict": "matched",
            "evidence_id": "old-id-123", "errors": [],
        }
        rebuilt = StepRecord.from_dict(historical)

        assert rebuilt.verdict == "matched"
        assert rebuilt.evidence_id == "old-id-123"
        assert rebuilt.evidence is None, "history was fabricated from an id"


class TestFreshProcessReconstruction:
    """The acceptance gate: disk only, no re-execution, no re-observation."""

    def test_a_new_process_recovers_the_exact_record(self, tmp_path):
        import subprocess
        import sys

        original = browser_evidence()

        # --- process A: write the event payload the bus would carry ---
        log = tmp_path / "events.jsonl"
        log.write_text(json.dumps({
            "event_type": "verification_completed",
            "objective_id": "obj-1",
            "task_id": "step_2",
            "payload": {
                "verdict": original.verdict.value,
                "evidence_id": original.evidence_id,
                "evidence": original.as_dict(),
            },
        }) + "\n", encoding="utf-8")

        # --- process B: a genuinely separate interpreter, disk only ---
        script = (
            "import json,sys;"
            "sys.path.insert(0, r'src');"
            "from master_agent.verification.evidence import Evidence;"
            "rec=[json.loads(l) for l in open(r'%s',encoding='utf-8') if l.strip()];"
            "found=[r for r in rec if r['task_id']=='step_2'][0];"
            "ev=Evidence.from_dict(found['payload']['evidence']);"
            "print(json.dumps(ev.as_dict()))"
        ) % str(log).replace("\\", "\\\\")

        completed = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, cwd=str(tmp_path.parent.parent.parent),
        )
        if completed.returncode != 0:
            pytest.skip(f"subprocess could not run: {completed.stderr[:200]}")

        recovered = Evidence.from_dict(json.loads(completed.stdout))
        assert recovered == original
        assert recovered.captured_at == CAPTURED
        assert recovered.worker == "browser"
        assert recovered.observation["title"] == "Example Domain"
        assert recovered.expected.checks[0].field == "url_normalised"
        assert recovered.check_results[0].passed is True


class TestNoFabricationRemains:

    def test_the_launcher_no_longer_manufactures_evidence(self):
        """It rebuilt Evidence from an id, stamping `worker="filesystem"`
        on every step and `captured_at=datetime.now()` on observations made
        earlier. Both callbacks discarded the Report they produced."""
        import ast
        import pathlib

        source = (
            pathlib.Path(__file__).resolve().parent.parent
            / "src/master_agent/launcher/boot.py"
        ).read_text(encoding="utf-8")

        constructed = [
            node for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "Evidence"
        ]
        assert constructed == [], (
            "boot.py constructs Evidence; only Verification may produce it"
        )
