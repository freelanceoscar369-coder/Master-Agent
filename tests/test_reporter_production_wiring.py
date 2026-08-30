"""Somesh explains the mission, not the last thing that happened to run.

Terminal Founder messages were composed from `FounderState.result` -- the
most recently completed Task's output. Truthful as "the last task
result"; untruthful as "the mission outcome". A three-step browser
mission ending in cleanup reported `{"closed": true}` as though closing
the browser were what Onkar asked for, and an earlier build rendered the
same value as `[object Object]`.

The authoritative record is the `PlanRecord` the Runtime wrote, now
carrying the exact Evidence Verification produced. These tests hold the
Reporter to it, and hold it back from the one claim it cannot make:
that the founder's objective was semantically fulfilled.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from master_agent.brain.reporter import Reporter, ReportContext
from master_agent.missions.history import COMPLETED, FAILED, PlanRecord, StepRecord
from master_agent.verification.evidence import (
    CheckResult,
    Evidence,
    ExpectedOutcome,
    ObservationCheck,
    Verdict,
)

CAPTURED = datetime(2026, 8, 19, 10, 30, tzinfo=UTC)


def evidence(worker: str, verdict: Verdict = Verdict.MATCHED,
             observation: dict | None = None) -> dict:
    check = ObservationCheck(field="target_exists", operator="equals", value=True)
    return Evidence(
        evidence_id=f"ev-{worker}-{verdict.value}",
        worker=worker,
        environment=f"{worker}_environment",
        captured_at=CAPTURED,
        expected=ExpectedOutcome(description="step effect", checks=[check]),
        observation=observation if observation is not None else {"target_exists": True},
        verdict=verdict,
        check_results=[CheckResult(
            check=check, passed=verdict is Verdict.MATCHED, actual_value=True,
        )],
    ).as_dict()


def step(capability: str, ev: dict | None = None, state: str = COMPLETED,
         output=None) -> StepRecord:
    record = StepRecord(step_id=capability, capability=capability, payload={})
    record.state = state
    if ev is not None:
        record.evidence = ev
        record.verdict = ev["verdict"]
        record.evidence_id = ev["evidence_id"]
    return record


def record(objective: str, steps: list[StepRecord], state: str = COMPLETED) -> PlanRecord:
    return PlanRecord(plan_id="plan-1", objective=objective, steps=steps, state=state)


def body(rec: PlanRecord, ctx: ReportContext | None = None) -> str:
    return Reporter().report_plan_record_outcome(rec, ctx).body


class TestVerificationCoverageIsStatedHonestly:
    """Case A-D of the required matrix."""

    def test_every_step_verified(self):
        rec = record("Create a folder", [
            step("Browser.Open", evidence("browser")),
            step("Browser.Navigate", evidence("browser")),
            step("Filesystem.CreateFolder", evidence("filesystem")),
        ])
        text = body(rec)
        assert "3" in text and "verified" in text.lower()

    def test_partial_coverage_says_so(self):
        rec = record("x", [
            step("A", evidence("browser")),
            step("B", evidence("browser")),
            step("C"),  # executed, no Evidence
        ])
        text = body(rec).lower()
        assert "2 of 3" in text
        assert "could not be independently verified" in text

    def test_a_failed_mission_never_claims_verified_success(self):
        rec = record("Open a browser", [
            step("A", evidence("browser", Verdict.NOT_MATCHED)),
        ], state=FAILED)
        text = body(rec).lower()
        assert "did not match" in text
        assert "all" not in text.split("did not match")[0] or "verified" not in text.split("did not match")[0]

    def test_no_evidence_at_all_is_not_described_as_checked(self):
        """The old sentence was "That's done and checked." with nothing
        checked at all."""
        rec = record("x", [step("A"), step("B")])
        text = body(rec).lower()

        assert "don't have independent verification" in text
        for forbidden in ("checked", "confirmed"):
            assert forbidden not in text, f"claimed {forbidden!r} with no Evidence"


class TestTheLastTaskOutputIsNotTheMissionSummary:
    """The defect this wiring exists to remove."""

    def test_a_cleanup_step_does_not_become_the_mission_result(self):
        rec = record(
            "Open a browser, navigate to example.com, then close the browser",
            [
                step("Browser.OpenBrowserSession", evidence("browser")),
                step("Browser.Navigate", evidence("browser")),
                step("Browser.CloseBrowserSession", evidence("browser"),
                     output={"closed": True}),
            ],
        )
        text = body(rec)

        assert "closed" not in text.lower(), (
            "the mission is described by its last step's output"
        )
        assert "{" not in text and "object Object" not in text
        assert "3" in text


class TestEvidenceIsNeverFabricated:

    def test_a_step_with_only_an_id_and_verdict_counts_as_unverified(self):
        """`evidence_id` correlates a record. It does not describe an
        observation, and Reporter may not treat it as one."""
        bare = StepRecord(step_id="A", capability="Filesystem.CreateFolder", payload={})
        bare.state = COMPLETED
        bare.verdict = "matched"
        bare.evidence_id = "ev-abc"          # id present...
        bare.evidence = None                  # ...record absent

        text = body(record("x", [bare])).lower()
        assert "don't have independent verification" in text

    def test_an_unreadable_projection_is_treated_as_missing(self):
        broken = StepRecord(step_id="A", capability="X", payload={})
        broken.state = COMPLETED
        broken.evidence = {"not": "an evidence record"}

        text = body(record("x", [broken])).lower()
        assert "don't have independent verification" in text


class TestCrossDomainIdentity:
    """Guards the old fabricated-filesystem Reporter path."""

    def test_each_worker_identity_is_read_not_rewritten(self):
        rec = record("x", [
            step("Browser.Navigate", evidence("browser")),
            step("Filesystem.WriteFile", evidence("filesystem")),
            step("Desktop.LaunchApplication", evidence("desktop")),
        ])
        from master_agent.brain.reporter import ReportTone

        detailed = body(rec, ReportContext(
            include_evidence_details=True, tone=ReportTone.DETAILED,
        )).lower()

        assert "browser" in detailed
        assert "filesystem" in detailed
        assert "desktop" in detailed


class TestFounderOutcomeConformanceBoundary:
    """§18. The most important restraint in this file.

    Two steps can each be independently verified while nothing establishes
    that the value observed in the first reached the second. Reporter may
    report the first fact and must not imply the second.
    """

    def _record_with_matching_values(self) -> PlanRecord:
        observed = evidence("browser", observation={
            "url": "https://example.com/", "title": "Example Domain",
        })
        written = evidence("filesystem", observation={
            "target_exists": True,
            "content_preview": "Title: Example Domain",
        })
        return record(
            "Observe the page title and write it into a file",
            [step("Browser.ObserveBrowser", observed),
             step("Filesystem.WriteFile", written)],
        )

    def test_both_steps_are_reported_as_independently_verified(self):
        text = body(self._record_with_matching_values()).lower()
        assert "verified" in text

    @pytest.mark.parametrize("overclaim", [
        "transferred", "objective was verified", "fully verified",
        "semantically", "your objective",
    ])
    def test_no_claim_about_the_founders_objective_is_made(self, overclaim):
        """Step verification is not founder-outcome conformance. The values
        matching is a coincidence until provenance exists to prove it."""
        assert overclaim not in body(self._record_with_matching_values()).lower()

    def test_the_metadata_states_conformance_was_not_evaluated(self):
        report = Reporter().report_plan_record_outcome(self._record_with_matching_values())
        assert report.metadata["founder_outcome_conformance"] == "unknown"


class TestRestartReporting:
    """Evidence is durable, so the Brain can explain a mission from disk."""

    def test_a_report_survives_a_serialisation_round_trip(self):
        rec = record("Create a folder", [
            step("Filesystem.CreateFolder", evidence("filesystem")),
            step("Filesystem.WriteFile"),
        ])
        before = body(rec)

        # The route a restart takes: history to disk and back.
        rebuilt = PlanRecord.from_dict(json.loads(json.dumps(rec.as_dict())))
        after = body(rebuilt)

        assert after == before
        assert "1 of 2" in after


class TestReporterStaysPure:
    """Reporter reads records and speaks. Nothing else."""

    @pytest.mark.parametrize("forbidden", [
        "playwright", "subprocess", "BrowserSessionManager", "WindowManager",
        "DesktopExecutor", "ExecutiveGateway",
    ])
    def test_it_reaches_no_environment(self, forbidden):
        import inspect

        from master_agent.brain import reporter as module

        assert forbidden.lower() not in inspect.getsource(module).lower()


class TestLegacyApiPreserved:

    def test_the_mission_manager_entry_point_still_exists(self):
        assert hasattr(Reporter, "report_mission_outcome")
        assert hasattr(Reporter, "report_plan_record_outcome")


class TestTheSurfaceUsesTheReporter:

    def test_the_terminal_branches_no_longer_describe_the_task_result(self):
        """Mechanical: the mission-level branches must not be composed from
        `state.result`."""
        import ast
        import pathlib

        source = (
            pathlib.Path(__file__).resolve().parent.parent / "kalpavriksha_desktop.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(source)

        submit = next(
            node for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "_submit_objective"
        )
        rendered = ast.unparse(submit)

        assert "_mission_report(" in rendered, "the Reporter path is not wired"
        assert "_describe_result(state.result" not in rendered, (
            "a terminal branch still describes the last Task output as the "
            "mission outcome"
        )
