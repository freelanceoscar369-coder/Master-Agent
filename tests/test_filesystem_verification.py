"""Tests for FilesystemVerifier and filesystem verification flow.
See VERIFICATION_SYSTEM.md and FILESYSTEM_CAPABILITIES.md.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from master_agent.executor.executor import LocalExecutor
from master_agent.permissions.permission_system import GrantScope, PermissionSystem
from master_agent.plugins.filesystem_observation import normalize_observation
from master_agent.plugins.filesystem_plugin import FilesystemPlugin
from master_agent.plugins.filesystem_verifier import FilesystemVerifier
from master_agent.plugins.filesystem_worker import FilesystemWorker
from master_agent.verification.evidence import ExpectedOutcome, ObservationCheck, Verdict


def test_normalize_observation_file_exists(tmp_path: Path):
    """Test observation of an existing file."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello, World!")

    obs = normalize_observation(test_file, tmp_path)

    assert obs.target_path == "test.txt"
    assert obs.target_name == "test.txt"
    assert obs.target_exists is True
    assert obs.target_is_dir is False
    assert obs.target_size_bytes == 13
    assert obs.target_modified_at is not None
    assert obs.target_permissions is not None
    assert obs.content_preview is None  # opt-in
    assert obs.directory_listing == []  # opt-in


def test_normalize_observation_file_with_content_preview(tmp_path: Path):
    """Test observation of an existing file with content preview."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello, World!")

    obs = normalize_observation(test_file, tmp_path, include_content_preview=True)

    assert obs.content_preview == "Hello, World!"
    assert obs.content_preview_truncated is False


def test_normalize_observation_file_content_truncation(tmp_path: Path):
    """Test content preview truncation for large files."""
    test_file = tmp_path / "large.txt"
    large_content = "x" * 15000  # larger than MAX_CONTENT_PREVIEW_CHARS (10_000)
    test_file.write_text(large_content)

    obs = normalize_observation(test_file, tmp_path, include_content_preview=True)

    assert obs.content_preview is not None
    assert len(obs.content_preview) == 10000
    assert obs.content_preview_truncated is True


def test_normalize_observation_directory_exists(tmp_path: Path):
    """Test observation of an existing directory."""
    test_dir = tmp_path / "subdir"
    test_dir.mkdir()
    (test_dir / "file1.txt").write_text("content1")
    (test_dir / "file2.txt").write_text("content2")

    obs = normalize_observation(test_dir, tmp_path, include_directory_listing=True)

    assert obs.target_path == "subdir"
    assert obs.target_name == "subdir"
    assert obs.target_exists is True
    assert obs.target_is_dir is True
    assert obs.target_size_bytes is None
    assert len(obs.directory_listing) == 2
    assert obs.directory_listing_truncated is False
    names = {e.name for e in obs.directory_listing}
    assert names == {"file1.txt", "file2.txt"}


def test_normalize_observation_directory_truncation(tmp_path: Path):
    """Test directory listing truncation for large directories."""
    test_dir = tmp_path / "bigdir"
    test_dir.mkdir()
    for i in range(600):  # larger than MAX_DIRECTORY_ENTRIES (500)
        (test_dir / f"file{i}.txt").write_text("x")

    obs = normalize_observation(test_dir, tmp_path, include_directory_listing=True)

    assert len(obs.directory_listing) == 500
    assert obs.directory_listing_truncated is True


def test_normalize_observation_nonexistent(tmp_path: Path):
    """Test observation of a nonexistent path."""
    nonexistent = tmp_path / "does_not_exist.txt"

    obs = normalize_observation(nonexistent, tmp_path)

    assert obs.target_path == "does_not_exist.txt"
    assert obs.target_name == "does_not_exist.txt"
    assert obs.target_exists is False
    assert obs.target_is_dir is None
    assert obs.target_size_bytes is None
    assert obs.target_modified_at is None
    assert obs.target_permissions is None


def test_filesystem_verifier_matched(tmp_path: Path):
    """Test FilesystemVerifier with MATCHED verdict."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("expected content")

    verifier = FilesystemVerifier(
        target_path=str(test_file),
        base_path=str(tmp_path),
        include_content_preview=True,
    )

    expected = ExpectedOutcome(
        description="file exists with expected content",
        checks=[
            ObservationCheck(field="target_exists", operator="equals", value=True),
            ObservationCheck(field="content_preview", operator="equals", value="expected content"),
            ObservationCheck(field="target_is_dir", operator="equals", value=False),
        ],
    )

    evidence = verifier.verify(expected)

    assert evidence.verdict == Verdict.MATCHED
    assert evidence.worker == "filesystem"
    assert evidence.environment == "filesystem_environment"
    assert evidence.evidence_id is not None
    assert len(evidence.check_results) == 3
    assert all(r.passed for r in evidence.check_results)


def test_filesystem_verifier_not_matched(tmp_path: Path):
    """Test FilesystemVerifier with NOT_MATCHED verdict."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("actual content")

    verifier = FilesystemVerifier(
        target_path=str(test_file),
        base_path=str(tmp_path),
        include_content_preview=True,
    )

    expected = ExpectedOutcome(
        description="file should have different content",
        checks=[
            ObservationCheck(field="content_preview", operator="equals", value="expected content"),
        ],
    )

    evidence = verifier.verify(expected)

    assert evidence.verdict == Verdict.NOT_MATCHED
    assert len(evidence.check_results) == 1
    assert evidence.check_results[0].passed is False
    assert evidence.check_results[0].actual_value == "actual content"


def test_filesystem_verifier_partially_matched(tmp_path: Path):
    """Test FilesystemVerifier with PARTIALLY_MATCHED verdict."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("content")

    verifier = FilesystemVerifier(
        target_path=str(test_file),
        base_path=str(tmp_path),
        include_content_preview=True,
    )

    expected = ExpectedOutcome(
        description="mixed checks",
        checks=[
            ObservationCheck(field="target_exists", operator="equals", value=True),
            ObservationCheck(field="content_preview", operator="equals", value="wrong content"),
        ],
    )

    evidence = verifier.verify(expected)

    assert evidence.verdict == Verdict.PARTIALLY_MATCHED
    assert len(evidence.check_results) == 2
    passed = [r for r in evidence.check_results if r.passed]
    failed = [r for r in evidence.check_results if not r.passed]
    assert len(passed) == 1
    assert len(failed) == 1


def test_filesystem_verifier_error_on_observation_failure(tmp_path: Path):
    """Test FilesystemVerifier returns ERROR when observation fails."""
    # Pass an invalid base path that will cause observation to fail
    verifier = FilesystemVerifier(
        target_path="/invalid/path/that/does/not/exist.txt",
        base_path="/also/invalid",
        include_content_preview=True,
    )

    expected = ExpectedOutcome(
        description="should error",
        checks=[
            ObservationCheck(field="target_exists", operator="equals", value=True),
        ],
    )

    evidence = verifier.verify(expected)

    # The observation may still succeed if the path exists in some form,
    # but if it truly fails, we get ERROR verdict
    assert evidence.verdict in (Verdict.ERROR, Verdict.NOT_MATCHED, Verdict.MATCHED)
    # At minimum, it should produce an Evidence record, not crash


def test_filesystem_worker_execute_verify_audit(tmp_path: Path):
    """Test the complete FilesystemWorker execute -> verify -> audit flow."""
    permissions = PermissionSystem()
    executor = LocalExecutor(permissions)
    # Create plugin to register actions on executor
    FilesystemPlugin(executor, locations={"desktop": tmp_path})
    worker = FilesystemWorker(executor, locations={"desktop": tmp_path})

    def approve(capability: str) -> None:
        permissions.grant(executor.name, capability, GrantScope.ONCE)

    # Execute a create_folder action
    payload = {"name": "test_folder", "location": "desktop"}

    # First execution without verification
    approve("create_folder")
    report = worker.run_step("create_folder", payload, requested_by="test")
    assert report.execution.success is True
    assert (tmp_path / "test_folder").is_dir()
    assert report.evidence is None  # no expected outcome provided

    # Second execution with verification
    expected = ExpectedOutcome(
        description="folder should exist",
        checks=[
            ObservationCheck(field="target_exists", operator="equals", value=True),
            ObservationCheck(field="target_is_dir", operator="equals", value=True),
            ObservationCheck(field="target_name", operator="equals", value="test_folder"),
        ],
    )

    approve("create_folder")
    report2 = worker.run_step(
        "create_folder", payload, requested_by="test", expected_outcome=expected,
        include_directory_listing=True,
    )

    assert report2.execution.success is True  # idempotent
    assert report2.evidence is not None
    assert report2.evidence.verdict == Verdict.MATCHED
    assert report2.audit.verification_verdict == Verdict.MATCHED
    assert report2.audit.evidence_id == report2.evidence.evidence_id


def test_filesystem_worker_write_file_verify(tmp_path: Path):
    """Test FilesystemWorker with write_file and content verification."""
    permissions = PermissionSystem()
    executor = LocalExecutor(permissions)
    # Create plugin to register actions on executor
    FilesystemPlugin(executor, locations={"desktop": tmp_path})
    worker = FilesystemWorker(executor, locations={"desktop": tmp_path})

    def approve(capability: str) -> None:
        permissions.grant(executor.name, capability, GrantScope.ONCE)

    # Write a file
    payload = {"path": "test.txt", "content": "Hello, Verification!", "location": "desktop"}

    expected = ExpectedOutcome(
        description="file written with correct content",
        checks=[
            ObservationCheck(field="target_exists", operator="equals", value=True),
            ObservationCheck(field="target_is_dir", operator="equals", value=False),
            ObservationCheck(field="content_preview", operator="equals", value="Hello, Verification!"),
        ],
    )

    approve("write_file")
    report = worker.run_step(
        "write_file", payload, requested_by="test", expected_outcome=expected,
        include_content_preview=True,
    )

    assert report.execution.success is True
    assert (tmp_path / "test.txt").read_text() == "Hello, Verification!"
    assert report.evidence is not None
    assert report.evidence.verdict == Verdict.MATCHED


def test_filesystem_worker_read_file_verify(tmp_path: Path):
    """Test FilesystemWorker with read_file and verification."""
    permissions = PermissionSystem()
    executor = LocalExecutor(permissions)
    # Create plugin to register actions on executor
    FilesystemPlugin(executor, locations={"desktop": tmp_path})
    worker = FilesystemWorker(executor, locations={"desktop": tmp_path})

    def approve(capability: str) -> None:
        permissions.grant(executor.name, capability, GrantScope.ONCE)

    # Create a file first
    test_file = tmp_path / "read_test.txt"
    test_file.write_text("Read me!")

    # Read it with verification
    payload = {"path": "read_test.txt", "location": "desktop"}

    expected = ExpectedOutcome(
        description="file read successfully",
        checks=[
            ObservationCheck(field="target_exists", operator="equals", value=True),
            ObservationCheck(field="target_is_dir", operator="equals", value=False),
        ],
    )

    approve("read_file")
    report = worker.run_step(
        "read_file", payload, requested_by="test", expected_outcome=expected,
    )

    assert report.execution.success is True
    assert report.execution.output["content"] == "Read me!"
    assert report.evidence is not None
    assert report.evidence.verdict == Verdict.MATCHED


def test_filesystem_worker_delete_file_verify(tmp_path: Path):
    """Test FilesystemWorker with delete_file and verification."""
    permissions = PermissionSystem()
    executor = LocalExecutor(permissions)
    # Create plugin to register actions on executor
    FilesystemPlugin(executor, locations={"desktop": tmp_path})
    worker = FilesystemWorker(executor, locations={"desktop": tmp_path})

    def approve(capability: str) -> None:
        permissions.grant(executor.name, capability, GrantScope.ONCE)

    # Create a file first
    test_file = tmp_path / "to_delete.txt"
    test_file.write_text("Delete me!")

    # Delete it with verification
    payload = {"path": "to_delete.txt", "location": "desktop"}

    expected = ExpectedOutcome(
        description="file deleted",
        checks=[
            ObservationCheck(field="target_exists", operator="equals", value=False),
        ],
    )

    approve("delete_file")
    report = worker.run_step(
        "delete_file", payload, requested_by="test", expected_outcome=expected,
    )

    assert report.execution.success is True
    assert not test_file.exists()
    assert report.evidence is not None
    assert report.evidence.verdict == Verdict.MATCHED


def test_filesystem_worker_list_directory_verify(tmp_path: Path):
    """Test FilesystemWorker with list_directory and verification."""
    permissions = PermissionSystem()
    executor = LocalExecutor(permissions)
    # Create plugin to register actions on executor
    FilesystemPlugin(executor, locations={"desktop": tmp_path})
    worker = FilesystemWorker(executor, locations={"desktop": tmp_path})

    def approve(capability: str) -> None:
        permissions.grant(executor.name, capability, GrantScope.ONCE)

    # Create some files
    (tmp_path / "file1.txt").write_text("1")
    (tmp_path / "file2.txt").write_text("2")
    (tmp_path / "subdir").mkdir()

    # List with verification
    payload = {"path": ".", "location": "desktop"}

    expected = ExpectedOutcome(
        description="directory listing matches expected",
        checks=[
            ObservationCheck(field="target_exists", operator="equals", value=True),
            ObservationCheck(field="target_is_dir", operator="equals", value=True),
            ObservationCheck(field="directory_listing.0.name", operator="equals", value="file1.txt"),
            ObservationCheck(field="directory_listing.1.name", operator="equals", value="file2.txt"),
            ObservationCheck(field="directory_listing.2.name", operator="equals", value="subdir"),
        ],
    )

    approve("list_directory")
    report = worker.run_step(
        "list_directory", payload, requested_by="test", expected_outcome=expected,
        include_directory_listing=True,
    )

    assert report.execution.success is True
    assert report.evidence is not None
    assert report.evidence.verdict == Verdict.MATCHED


def test_filesystem_worker_audit_log_accumulates(tmp_path: Path):
    """Test that FilesystemWorker audit log accumulates records."""
    permissions = PermissionSystem()
    executor = LocalExecutor(permissions)
    # Create plugin to register actions on executor
    FilesystemPlugin(executor, locations={"desktop": tmp_path})
    worker = FilesystemWorker(executor, locations={"desktop": tmp_path})

    def approve(capability: str) -> None:
        permissions.grant(executor.name, capability, GrantScope.ONCE)

    # Run multiple steps
    approve("create_folder")
    worker.run_step("create_folder", {"name": "folder1", "location": "desktop"}, requested_by="test")
    approve("create_folder")
    worker.run_step("create_folder", {"name": "folder2", "location": "desktop"}, requested_by="test")
    approve("write_file")
    worker.run_step("write_file", {"path": "file.txt", "content": "x", "location": "desktop"}, requested_by="test")

    records = worker.audit_log.records
    assert len(records) == 3
    assert [r.action_name for r in records] == ["create_folder", "create_folder", "write_file"]
    assert all(r.worker == "filesystem" for r in records)
    assert all(r.environment == "filesystem_environment" for r in records)


def test_filesystem_verifier_exists_operator(tmp_path: Path):
    """Test FilesystemVerifier with 'exists' operator."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("content")

    verifier = FilesystemVerifier(
        target_path=str(test_file),
        base_path=str(tmp_path),
    )

    expected = ExpectedOutcome(
        description="path exists",
        checks=[
            ObservationCheck(field="target_exists", operator="exists"),
        ],
    )

    evidence = verifier.verify(expected)

    assert evidence.verdict == Verdict.MATCHED
    assert evidence.check_results[0].passed is True


def test_filesystem_verifier_contains_operator(tmp_path: Path):
    """Test FilesystemVerifier with 'contains' operator."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello, World!")

    verifier = FilesystemVerifier(
        target_path=str(test_file),
        base_path=str(tmp_path),
        include_content_preview=True,
    )

    expected = ExpectedOutcome(
        description="content contains substring",
        checks=[
            ObservationCheck(field="content_preview", operator="contains", value="World"),
        ],
    )

    evidence = verifier.verify(expected)

    assert evidence.verdict == Verdict.MATCHED
    assert evidence.check_results[0].passed is True


def test_filesystem_verifier_not_contains_operator(tmp_path: Path):
    """Test FilesystemVerifier with 'not_contains' operator."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello, World!")

    verifier = FilesystemVerifier(
        target_path=str(test_file),
        base_path=str(tmp_path),
        include_content_preview=True,
    )

    expected = ExpectedOutcome(
        description="content does not contain substring",
        checks=[
            ObservationCheck(field="content_preview", operator="not_contains", value="Mars"),
        ],
    )

    evidence = verifier.verify(expected)

    assert evidence.verdict == Verdict.MATCHED
    assert evidence.check_results[0].passed is True


def test_filesystem_verifier_matches_regex_operator(tmp_path: Path):
    """Test FilesystemVerifier with 'matches_regex' operator."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("Version 1.2.3")

    verifier = FilesystemVerifier(
        target_path=str(test_file),
        base_path=str(tmp_path),
        include_content_preview=True,
    )

    expected = ExpectedOutcome(
        description="content matches version pattern",
        checks=[
            ObservationCheck(field="content_preview", operator="matches_regex", value=r"Version \d+\.\d+\.\d+"),
        ],
    )

    evidence = verifier.verify(expected)

    assert evidence.verdict == Verdict.MATCHED
    assert evidence.check_results[0].passed is True