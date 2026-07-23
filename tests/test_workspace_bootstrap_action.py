"""WorkspaceBootstrapAction tests -- the composite action. Unlike
test_create_folder_action.py / test_write_file_action.py, this can't test
run() against the action in isolation, because the whole point of a
composite action is that it invokes its sub-actions through the real
LocalExecutor (docs/adr/0006-composite-action-relay.md) -- so these tests
wire up a real LocalExecutor + PermissionSystem, register all three
actions on it (the same shape FilesystemPlugin uses), and exercise
workspace_bootstrap through executor.execute(), asserting on both the
filesystem outcome and the Executor's own log to prove no sub-step
bypassed it.
"""
from __future__ import annotations

import pytest

from master_agent.executor.actions.create_folder import CREATE_FOLDER, CreateFolderAction
from master_agent.executor.actions.workspace_bootstrap import WORKSPACE_BOOTSTRAP, WorkspaceBootstrapAction
from master_agent.executor.actions.write_file import WRITE_FILE, WriteFileAction
from master_agent.executor.executor import LocalExecutor
from master_agent.permissions.permission_system import ApprovalRequired, GrantScope, PermissionSystem
from master_agent.plugins.base import RiskTier


def make_executor(tmp_path):
    permissions = PermissionSystem()
    executor = LocalExecutor(permissions)
    locations = {"desktop": tmp_path}
    executor.register(CreateFolderAction(locations))
    executor.register(WriteFileAction(locations))
    executor.register(WorkspaceBootstrapAction(executor, locations))
    return executor, permissions


# ---- contract -------------------------------------------------------------

def test_declares_reversible_write_risk_and_required_parameters():
    action = WorkspaceBootstrapAction(executor=LocalExecutor(PermissionSystem()), locations={})
    assert action.risk_tier == RiskTier.REVERSIBLE_WRITE
    assert action.required_parameters() == ["name"]
    assert action.expected_result


# ---- validate ---------------------------------------------------------------

def test_validate_passes_for_a_well_formed_request(tmp_path):
    executor, _ = make_executor(tmp_path)
    action = WorkspaceBootstrapAction(executor, locations={"desktop": tmp_path})
    errors = action.validate(
        {
            "name": "MyProject",
            "folders": ["src", "docs"],
            "files": [{"path": "README.md", "content": "# MyProject"}],
        }
    )
    assert errors == []


def test_validate_catches_missing_name(tmp_path):
    executor, _ = make_executor(tmp_path)
    action = WorkspaceBootstrapAction(executor, locations={"desktop": tmp_path})
    assert any("name" in e for e in action.validate({}))


def test_validate_catches_unknown_location(tmp_path):
    executor, _ = make_executor(tmp_path)
    action = WorkspaceBootstrapAction(executor, locations={"desktop": tmp_path})
    errors = action.validate({"name": "MyProject", "location": "downloads"})
    assert any("unknown location" in e for e in errors)


def test_validate_rejects_traversal_in_name(tmp_path):
    executor, _ = make_executor(tmp_path)
    action = WorkspaceBootstrapAction(executor, locations={"desktop": tmp_path})
    errors = action.validate({"name": "../escape"})
    assert any("unsafe name" in e for e in errors)


def test_validate_rejects_non_list_folders(tmp_path):
    executor, _ = make_executor(tmp_path)
    action = WorkspaceBootstrapAction(executor, locations={"desktop": tmp_path})
    errors = action.validate({"name": "MyProject", "folders": "src"})
    assert any("folders must be a list" in e for e in errors)


def test_validate_rejects_traversal_in_folder_entry(tmp_path):
    executor, _ = make_executor(tmp_path)
    action = WorkspaceBootstrapAction(executor, locations={"desktop": tmp_path})
    errors = action.validate({"name": "MyProject", "folders": ["../escape"]})
    assert any("unsafe folder path" in e for e in errors)


def test_validate_rejects_malformed_file_entry(tmp_path):
    executor, _ = make_executor(tmp_path)
    action = WorkspaceBootstrapAction(executor, locations={"desktop": tmp_path})
    errors = action.validate({"name": "MyProject", "files": [{"content": "no path key"}]})
    assert any("invalid file entry" in e for e in errors)


def test_validate_rejects_traversal_in_file_path(tmp_path):
    executor, _ = make_executor(tmp_path)
    action = WorkspaceBootstrapAction(executor, locations={"desktop": tmp_path})
    errors = action.validate({"name": "MyProject", "files": [{"path": "../escape.txt", "content": ""}]})
    assert any("unsafe file path" in e for e in errors)


def test_validate_never_touches_the_filesystem(tmp_path):
    """validate() is a pure check -- calling it with a well-formed-looking
    request must not create anything, even though run() would."""
    executor, _ = make_executor(tmp_path)
    action = WorkspaceBootstrapAction(executor, locations={"desktop": tmp_path})
    action.validate({"name": "MyProject", "folders": ["src"], "files": [{"path": "README.md", "content": "x"}]})
    assert list(tmp_path.iterdir()) == []


# ---- full composition through the real Executor ----------------------------

def test_full_bootstrap_creates_root_subfolders_and_files(tmp_path):
    executor, permissions = make_executor(tmp_path)
    permissions.grant(executor.name, WORKSPACE_BOOTSTRAP, GrantScope.ONCE)

    result = executor.execute(
        WORKSPACE_BOOTSTRAP,
        {
            "name": "MyProject",
            "folders": ["src", "docs"],
            "files": [
                {"path": "README.md", "content": "# MyProject"},
                {"path": "docs/NOTES.md", "content": "notes"},
            ],
        },
    )

    assert result.success, result.errors
    root = tmp_path / "MyProject"
    assert root.is_dir()
    assert (root / "src").is_dir()
    assert (root / "docs").is_dir()
    assert (root / "README.md").read_text() == "# MyProject"
    assert (root / "docs" / "NOTES.md").read_text() == "notes"
    assert result.output["root"] == str(root)
    assert len(result.output["created_folders"]) == 3  # root + src + docs
    assert len(result.output["written_files"]) == 2


def test_only_one_human_approval_is_needed_for_the_whole_composite(tmp_path):
    """Only the top-level workspace_bootstrap grant is issued -- create_folder
    and write_file's own grant keys are never pre-populated. If the relay
    (docs/adr/0006-composite-action-relay.md) didn't work, this would raise
    ApprovalRequired on the very first sub-step."""
    executor, permissions = make_executor(tmp_path)
    permissions.grant(executor.name, WORKSPACE_BOOTSTRAP, GrantScope.ONCE)

    result = executor.execute(
        WORKSPACE_BOOTSTRAP,
        {"name": "MyProject", "folders": ["src"], "files": [{"path": "README.md", "content": "hi"}]},
    )

    assert result.success


def test_every_sub_step_is_individually_logged_by_the_real_executor(tmp_path):
    """Proves sub-steps ran THROUGH the Executor (validated, permission-
    checked via relay, logged) rather than the composite calling their
    run() methods directly, which would leave no trace in the log."""
    executor, permissions = make_executor(tmp_path)
    permissions.grant(executor.name, WORKSPACE_BOOTSTRAP, GrantScope.ONCE)

    executor.execute(
        WORKSPACE_BOOTSTRAP,
        {"name": "MyProject", "folders": ["src"], "files": [{"path": "README.md", "content": "hi"}]},
    )

    # Sub-steps log THEIR entries first (each execute() call records in its
    # own `finally` when IT returns); the composite's own entry is recorded
    # last, in ITS `finally`, after run() -- which ran every sub-step -- has
    # already returned. Nesting order, not call order.
    action_names = [entry.action_name for entry in executor.log]
    assert action_names == [CREATE_FOLDER, CREATE_FOLDER, WRITE_FILE, WORKSPACE_BOOTSTRAP]
    assert all(entry.status == "success" for entry in executor.log)


# ---- permission denied -----------------------------------------------------

def test_permission_denied_at_the_top_prevents_every_sub_step(tmp_path):
    executor, _permissions = make_executor(tmp_path)

    with pytest.raises(ApprovalRequired):
        executor.execute(WORKSPACE_BOOTSTRAP, {"name": "MyProject", "folders": ["src"]})

    assert list(tmp_path.iterdir()) == []
    assert executor.log[-1].status == "blocked_on_approval"
    assert executor.log[-1].action_name == WORKSPACE_BOOTSTRAP
    # Nothing beyond the top-level attempt was even reached.
    assert len(executor.log) == 1


# ---- partial failure, no rollback ------------------------------------------

def test_partial_failure_stops_at_the_failing_step_and_reports_what_completed(tmp_path):
    executor, permissions = make_executor(tmp_path)
    # Sabotage the second folder: pre-create it as a *file*, so
    # create_folder's own collision check fails partway through the plan.
    (tmp_path / "MyProject").mkdir()
    (tmp_path / "MyProject" / "docs").write_text("not a folder")

    permissions.grant(executor.name, WORKSPACE_BOOTSTRAP, GrantScope.ONCE)
    result = executor.execute(
        WORKSPACE_BOOTSTRAP,
        {"name": "MyProject", "folders": ["src", "docs"]},
    )

    assert not result.success
    assert "docs" in result.errors[0]
    # No rollback: the root and the first subfolder that DID succeed stay.
    assert (tmp_path / "MyProject").is_dir()
    assert (tmp_path / "MyProject" / "src").is_dir()
    completed = result.output["completed_before_failure"]
    assert len(completed) == 2  # root + src, before docs failed


def test_second_bootstrap_of_the_same_workspace_is_idempotent(tmp_path):
    """Re-running the same bootstrap (e.g. a retried mission) succeeds
    again rather than failing on "already exists" -- create_folder is
    already idempotent and write_file no-ops on identical content, so the
    composite inherits that for free."""
    executor, permissions = make_executor(tmp_path)
    payload = {"name": "MyProject", "folders": ["src"], "files": [{"path": "README.md", "content": "hi"}]}

    permissions.grant(executor.name, WORKSPACE_BOOTSTRAP, GrantScope.ONCE)
    first = executor.execute(WORKSPACE_BOOTSTRAP, payload)

    permissions.grant(executor.name, WORKSPACE_BOOTSTRAP, GrantScope.ONCE)
    second = executor.execute(WORKSPACE_BOOTSTRAP, payload)

    assert first.success
    assert second.success
