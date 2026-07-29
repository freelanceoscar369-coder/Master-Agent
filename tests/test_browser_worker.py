"""BrowserWorker integration tests -- proves the Worker Lifecycle facade
sequences Execute -> Verify -> Audit correctly, that Verification is
independent of Execution's own success flag, and that permission is
genuinely required (BrowserWorker does not self-grant). See
BROWSER_WORKER_ARCHITECTURE.md §10 and §11.
"""
from __future__ import annotations

import pytest

from master_agent.permissions.permission_system import ApprovalRequired
from master_agent.plugins.browser_plugin import BrowserPlugin
from master_agent.plugins.browser_worker import BrowserWorker
from master_agent.verification.evidence import ExpectedOutcome, ObservationCheck, Verdict
from tests.browser_test_support import SAMPLE_HTML, grant_once, make_executor_and_sessions


def make_worker():
    executor, sessions = make_executor_and_sessions()
    BrowserPlugin(executor, sessions)  # registers the nine Actions on the executor
    return BrowserWorker(executor, sessions), executor, sessions


def test_run_step_without_expected_outcome_produces_no_evidence():
    worker, executor, sessions = make_worker()
    grant_once(executor, "open_browser_session")
    try:
        report = worker.run_step("open_browser_session", {"session_id": "s1"}, requested_by="test")
        assert report.execution.success
        assert report.evidence is None
        assert report.audit.execution_success is True
        assert report.audit.verification_verdict is None
        assert report.audit.evidence_id is None
    finally:
        sessions.close_all()


def test_run_step_with_expected_outcome_produces_matched_evidence():
    worker, executor, sessions = make_worker()
    grant_once(executor, "open_browser_session")
    grant_once(executor, "observe_browser")
    try:
        worker.run_step("open_browser_session", {"session_id": "s1"}, requested_by="test")
        sessions.get("s1").page.set_content(SAMPLE_HTML)

        report = worker.run_step(
            "observe_browser",
            {"session_id": "s1", "selectors": ["#heading"]},
            requested_by="test",
            expected_outcome=ExpectedOutcome(
                description="heading says Hello",
                checks=[ObservationCheck(field="elements.0.text", operator="equals", value="Hello")],
            ),
            verify_selectors=["#heading"],
        )
        assert report.execution.success
        assert report.evidence.verdict == Verdict.MATCHED
        assert report.audit.verification_verdict == Verdict.MATCHED
        assert report.audit.evidence_id == report.evidence.evidence_id
    finally:
        sessions.close_all()


def test_execution_success_does_not_imply_verification_success():
    """The core claim of ADR-0011: an Action can succeed while Verification
    independently reports NOT_MATCHED."""
    worker, executor, sessions = make_worker()
    grant_once(executor, "open_browser_session")
    grant_once(executor, "click")
    try:
        worker.run_step("open_browser_session", {"session_id": "s1"}, requested_by="test")
        sessions.get("s1").page.set_content(SAMPLE_HTML)

        report = worker.run_step(
            "click",
            {"session_id": "s1", "selector": "#btn"},
            requested_by="test",
            expected_outcome=ExpectedOutcome(
                description="heading changed to something it never will",
                checks=[ObservationCheck(field="elements.0.text", operator="equals", value="Never")],
            ),
            verify_session_id="s1",
            verify_selectors=["#heading"],
        )
        assert report.execution.success is True  # the click itself worked
        assert report.evidence.verdict == Verdict.NOT_MATCHED  # but it didn't produce the expected state
    finally:
        sessions.close_all()


def test_verification_can_check_against_the_accessibility_tree():
    """Proves the accessibility-tree facet is not merely captured but
    actually usable as Evidence a Verdict is computed from."""
    worker, executor, sessions = make_worker()
    grant_once(executor, "open_browser_session")
    grant_once(executor, "observe_browser")
    try:
        worker.run_step("open_browser_session", {"session_id": "s1"}, requested_by="test")
        sessions.get("s1").page.set_content(SAMPLE_HTML)

        report = worker.run_step(
            "observe_browser",
            {"session_id": "s1"},
            requested_by="test",
            expected_outcome=ExpectedOutcome(
                description="the page exposes a button to assistive technology",
                checks=[
                    ObservationCheck(field="accessibility_tree", operator="contains", value="button")
                ],
            ),
            verify_accessibility_tree=True,
        )
        assert report.evidence.verdict == Verdict.MATCHED
    finally:
        sessions.close_all()


def test_verification_can_check_against_available_actions():
    worker, executor, sessions = make_worker()
    grant_once(executor, "open_browser_session")
    grant_once(executor, "observe_browser")
    try:
        worker.run_step("open_browser_session", {"session_id": "s1"}, requested_by="test")
        sessions.get("s1").page.set_content(SAMPLE_HTML)

        report = worker.run_step(
            "observe_browser",
            {"session_id": "s1"},
            requested_by="test",
            expected_outcome=ExpectedOutcome(
                description="the page affords at least one enabled interaction",
                checks=[
                    ObservationCheck(field="available_actions.0.is_enabled", operator="equals", value=True)
                ],
            ),
            verify_available_actions=True,
        )
        assert report.evidence.verdict == Verdict.MATCHED
    finally:
        sessions.close_all()


def test_run_step_requires_a_real_grant_and_does_not_self_approve():
    """BrowserWorker must never bypass the Permission System -- see
    BROWSER_WORKER_ARCHITECTURE.md §11's explicit design note."""
    worker, _executor, _sessions = make_worker()
    with pytest.raises(ApprovalRequired):
        worker.run_step("open_browser_session", {"session_id": "s1"}, requested_by="test")


def test_audit_log_never_loses_history_across_multiple_steps():
    worker, executor, sessions = make_worker()
    grant_once(executor, "open_browser_session")
    grant_once(executor, "close_browser_session")
    try:
        worker.run_step("open_browser_session", {"session_id": "s1"}, requested_by="test")
        worker.run_step("close_browser_session", {"session_id": "s1"}, requested_by="test")
        assert len(worker.audit_log.records) == 2
        assert [r.action_name for r in worker.audit_log.records] == [
            "open_browser_session",
            "close_browser_session",
        ]
    finally:
        sessions.close_all()


def test_audit_record_carries_requester_worker_environment_and_time():
    worker, executor, sessions = make_worker()
    grant_once(executor, "open_browser_session")
    try:
        report = worker.run_step("open_browser_session", {"session_id": "s1"}, requested_by="founder")
        record = report.audit
        assert record.requested_by == "founder"
        assert record.worker == "browser"
        assert record.environment == "browser_environment"
        assert record.started_at <= record.ended_at
    finally:
        sessions.close_all()
