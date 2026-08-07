"""Verification regression tests for filesystem verification.

These tests verify the core verification invariants:
1. Failed execution does not create false evidence
2. Verification reads fresh filesystem state
3. ExecutionResult is never trusted by verifier
4. AuditRecord contains evidence_id
5. Permission denial prevents execution
"""
from __future__ import annotations

from pathlib import Path

from master_agent.executor.executor import LocalExecutor
from master_agent.permissions.permission_system import GrantScope, PermissionSystem
from master_agent.plugins.filesystem_plugin import FilesystemPlugin
from master_agent.plugins.filesystem_verifier import FilesystemVerifier
from master_agent.plugins.filesystem_worker import FilesystemWorker
from master_agent.verification.audit import AuditRecord
from master_agent.verification.evidence import ExpectedOutcome, ObservationCheck, Verdict


def test_failed_execution_no_false_evidence(tmp_path: Path):
    """Failed execution should not create MATCHED evidence."""
    permissions = PermissionSystem()
    executor = LocalExecutor(permissions)
    FilesystemPlugin(executor, locations={"desktop": tmp_path})
    worker = FilesystemWorker(executor, locations={"desktop": tmp_path})

    def approve(capability: str) -> None:
        permissions.grant(executor.name, capability, GrantScope.ONCE)

    # Try to create folder in a location that doesn't exist
    payload = {"name": "test", "location": "nonexistent_location"}

    expected = ExpectedOutcome(
        description="folder created",
        checks=[ObservationCheck(field="target_exists", operator="equals", value=True)],
    )

    # Execution fails but we still verify
    report = worker.run_step("create_folder", payload, requested_by="test", expected_outcome=expected)

    # Execution failed
    assert report.execution.success is False
    # Evidence should reflect the actual state (folder doesn't exist)
    assert report.evidence is not None
    assert report.evidence.verdict == Verdict.NOT_MATCHED
    # Audit should record both execution failure and verification verdict
    assert report.audit.execution_success is False
    assert report.audit.verification_verdict == Verdict.NOT_MATCHED


def test_verification_reads_fresh_state(tmp_path: Path):
    """Verifier must read fresh filesystem state, not cached from execution."""
    permissions = PermissionSystem()
    executor = LocalExecutor(permissions)
    FilesystemPlugin(executor, locations={"desktop": tmp_path})
    worker = FilesystemWorker(executor, locations={"desktop": tmp_path})

    def approve(capability: str) -> None:
        permissions.grant(executor.name, capability, GrantScope.ONCE)

    # Create a file
    approve("write_file")
    payload_write = {"path": "test.txt", "content": "original", "location": "desktop"}
    worker.run_step("write_file", payload_write, requested_by="test")

    # Modify file externally (simulating external change after execution)
    (tmp_path / "test.txt").write_text("modified_externally")

    # Verify with expected outcome matching original (should fail)
    payload_verify = {"path": "test.txt", "location": "desktop"}
    expected = ExpectedOutcome(
        description="file has original content",
        checks=[ObservationCheck(field="content_preview", operator="equals", value="original")],
    )

    report = worker.run_step("read_file", payload_verify, requested_by="test", expected_outcome=expected, include_content_preview=True)

    # Verification should see the external modification and fail
    assert report.execution.success is True  # read_file succeeds
    assert report.evidence is not None
    assert report.evidence.verdict == Verdict.NOT_MATCHED
    assert report.evidence.observation["content_preview"] == "modified_externally"


def test_execution_result_never_trusted_by_verifier(tmp_path: Path):
    """Verification verdict must be independent of ExecutionResult.success."""
    permissions = PermissionSystem()
    executor = LocalExecutor(permissions)
    FilesystemPlugin(executor, locations={"desktop": tmp_path})
    worker = FilesystemWorker(executor, locations={"desktop": tmp_path})

    def approve(capability: str) -> None:
        permissions.grant(executor.name, capability, GrantScope.ONCE)

    # Write file successfully
    approve("write_file")
    payload = {"path": "test.txt", "content": "content", "location": "desktop"}
    report = worker.run_step("write_file", payload, requested_by="test")

    assert report.execution.success is True
    assert report.evidence is None  # no expected outcome

    # Now verify with an expected outcome that will NOT match
    expected = ExpectedOutcome(
        description="wrong expectation",
        checks=[ObservationCheck(field="content_preview", operator="equals", value="different")],
    )

    report2 = worker.run_step("read_file", {"path": "test.txt", "location": "desktop"}, requested_by="test", expected_outcome=expected, include_content_preview=True)

    # Execution succeeded but verification failed
    assert report2.execution.success is True
    assert report2.evidence is not None
    assert report2.evidence.verdict == Verdict.NOT_MATCHED
    # Audit records both: execution success, verification failure
    assert report2.audit.execution_success is True
    assert report2.audit.verification_verdict == Verdict.NOT_MATCHED


def test_audit_record_contains_evidence_id(tmp_path: Path):
    """AuditRecord must contain evidence_id when verification runs."""
    permissions = PermissionSystem()
    executor = LocalExecutor(permissions)
    FilesystemPlugin(executor, locations={"desktop": tmp_path})
    worker = FilesystemWorker(executor, locations={"desktop": tmp_path})

    def approve(capability: str) -> None:
        permissions.grant(executor.name, capability, GrantScope.ONCE)

    approve("create_folder")
    payload = {"name": "test_folder", "location": "desktop"}
    expected = ExpectedOutcome(
        description="folder exists",
        checks=[ObservationCheck(field="target_exists", operator="equals", value=True)],
    )

    report = worker.run_step("create_folder", payload, requested_by="test", expected_outcome=expected)

    # Evidence should have evidence_id
    assert report.evidence is not None
    assert report.evidence.evidence_id is not None

    # Audit should link to the same evidence_id
    assert report.audit.evidence_id == report.evidence.evidence_id
    assert report.audit.evidence_id is not None

    # Verify audit record structure
    assert isinstance(report.audit, AuditRecord)
    assert report.audit.audit_id is not None
    assert report.audit.requested_by == "test"
    assert report.audit.worker == "filesystem"
    assert report.audit.environment == "filesystem_environment"
    assert report.audit.action_name == "create_folder"


def test_permission_denial_prevents_execution(tmp_path: Path):
    """Without permission grant, execution should fail with ApprovalRequired."""
    permissions = PermissionSystem()
    executor = LocalExecutor(permissions)
    FilesystemPlugin(executor, locations={"desktop": tmp_path})
    worker = FilesystemWorker(executor, locations={"desktop": tmp_path})

    # No approve() call - permission not granted
    payload = {"name": "test_folder", "location": "desktop"}
    expected = ExpectedOutcome(
        description="folder should exist",
        checks=[ObservationCheck(field="target_exists", operator="equals", value=True)],
    )

    # This should raise ApprovalRequired (not caught by worker - Runtime handles it)
    from master_agent.permissions.permission_system import ApprovalRequired
    import pytest

    with pytest.raises(ApprovalRequired):
        worker.run_step("create_folder", payload, requested_by="test", expected_outcome=expected)

    # The folder was NOT created
    assert not (tmp_path / "test_folder").exists()


def test_verification_error_on_observation_failure(tmp_path: Path):
    """Verifier returns ERROR verdict when observation itself fails."""
    # Use invalid base path that will cause observation to fail
    verifier = FilesystemVerifier(
        target_path="/invalid/path/does/not/exist.txt",
        base_path="/also/invalid",
        include_content_preview=True,
    )

    expected = ExpectedOutcome(
        description="should error on observation",
        checks=[ObservationCheck(field="target_exists", operator="equals", value=True)],
    )

    evidence = verifier.verify(expected)

    # Should produce evidence with ERROR verdict, not crash
    assert evidence.verdict == Verdict.ERROR
    assert evidence.worker == "filesystem"
    assert evidence.environment == "filesystem_environment"
    assert len(evidence.errors) > 0
    assert "observation failed" in evidence.errors[0].lower()


def test_evidence_is_immutable_and_plain_json(tmp_path: Path):
    """Evidence should be plain JSON-serializable, no live objects."""
    permissions = PermissionSystem()
    executor = LocalExecutor(permissions)
    FilesystemPlugin(executor, locations={"desktop": tmp_path})
    worker = FilesystemWorker(executor, locations={"desktop": tmp_path})

    def approve(capability: str) -> None:
        permissions.grant(executor.name, capability, GrantScope.ONCE)

    approve("write_file")
    payload = {"path": "test.txt", "content": "hello", "location": "desktop"}
    expected = ExpectedOutcome(
        description="file written",
        checks=[ObservationCheck(field="target_exists", operator="equals", value=True)],
    )

    report = worker.run_step("write_file", payload, requested_by="test", expected_outcome=expected)

    # Evidence observation should be plain dict (JSON-serializable)
    assert isinstance(report.evidence.observation, dict)
    # No Path objects should be in observation
    import json
    json_str = json.dumps(report.evidence.observation)  # Should not raise
    assert isinstance(json_str, str)

    # Evidence fields should be immutable-like (dataclass with frozen not required but structure is)
    assert report.evidence.evidence_id is not None
    assert report.evidence.worker == "filesystem"
    assert report.evidence.environment == "filesystem_environment"
    assert report.evidence.captured_at is not None


def test_expected_outcome_with_empty_checks_errors(tmp_path: Path):
    """ExpectedOutcome with no checks should produce ERROR verdict."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("content")

    verifier = FilesystemVerifier(
        target_path=str(test_file),
        base_path=str(tmp_path),
    )

    expected = ExpectedOutcome(
        description="empty checks",
        checks=[],  # Empty checks list
    )

    evidence = verifier.verify(expected)

    assert evidence.verdict == Verdict.ERROR
    assert len(evidence.check_results) == 0


def test_verdict_aggregation_rules(tmp_path: Path):
    """Test verdict aggregation: all pass=MATCHED, none pass=NOT_MATCHED, some=PARTIALLY_MATCHED."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("content")

    verifier = FilesystemVerifier(
        target_path=str(test_file),
        base_path=str(tmp_path),
        include_content_preview=True,
    )

    # All pass
    expected_all = ExpectedOutcome(
        description="all pass",
        checks=[
            ObservationCheck(field="target_exists", operator="equals", value=True),
            ObservationCheck(field="target_is_dir", operator="equals", value=False),
        ],
    )
    evidence_all = verifier.verify(expected_all)
    assert evidence_all.verdict == Verdict.MATCHED

    # None pass
    expected_none = ExpectedOutcome(
        description="none pass",
        checks=[
            ObservationCheck(field="target_exists", operator="equals", value=False),
            ObservationCheck(field="target_is_dir", operator="equals", value=True),
        ],
    )
    evidence_none = verifier.verify(expected_none)
    assert evidence_none.verdict == Verdict.NOT_MATCHED

    # Some pass
    expected_some = ExpectedOutcome(
        description="some pass",
        checks=[
            ObservationCheck(field="target_exists", operator="equals", value=True),
            ObservationCheck(field="target_is_dir", operator="equals", value=True),  # wrong
        ],
    )
    evidence_some = verifier.verify(expected_some)
    assert evidence_some.verdict == Verdict.PARTIALLY_MATCHED


def test_verification_before_execution_order(tmp_path: Path):
    """Verify execution happens before verification in worker."""
    permissions = PermissionSystem()
    executor = LocalExecutor(permissions)
    FilesystemPlugin(executor, locations={"desktop": tmp_path})
    worker = FilesystemWorker(executor, locations={"desktop": tmp_path})

    def approve(capability: str) -> None:
        permissions.grant(executor.name, capability, GrantScope.ONCE)

    approve("create_folder")
    payload = {"name": "test", "location": "desktop"}
    expected = ExpectedOutcome(
        description="folder created",
        checks=[ObservationCheck(field="target_exists", operator="equals", value=True)],
    )

    report = worker.run_step("create_folder", payload, requested_by="test", expected_outcome=expected)

    # Both execution and verification ran
    assert report.execution is not None
    assert report.evidence is not None
    assert report.audit is not None

    # Audit timestamps: started_at <= ended_at
    assert report.audit.started_at <= report.audit.ended_at
    # Verification verdict recorded
    assert report.audit.verification_verdict is not None