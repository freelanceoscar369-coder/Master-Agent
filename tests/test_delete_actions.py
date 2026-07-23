"""Mission Brief 005 — the two IRREVERSIBLE/DELETE-category primitives:
DeleteFileAction, DeleteFolderAction. Direct unit tests against each
Action. The additional "an ALWAYS_FOR_CAPABILITY grant can never satisfy
an IRREVERSIBLE check" rule these actions rely on is tested at the
PermissionSystem level in test_permission_system.py, not here — this file
only covers what each Action itself is responsible for.
"""
from __future__ import annotations

from master_agent.executor.actions.delete_file import DeleteFileAction
from master_agent.executor.actions.delete_folder import DeleteFolderAction
from master_agent.plugins.base import PermissionCategory, RiskTier


def test_both_are_irreversible_and_categorized_delete():
    for action_cls in (DeleteFileAction, DeleteFolderAction):
        action = action_cls({})
        assert action.risk_tier == RiskTier.IRREVERSIBLE
        assert action.permission_category == PermissionCategory.DELETE


# ---- DeleteFileAction -----------------------------------------------------------

def test_delete_file_removes_the_file(tmp_path):
    (tmp_path / "temp.txt").write_text("x")
    action = DeleteFileAction({"desktop": tmp_path})

    result = action.run({"path": "temp.txt"})

    assert result.success
    assert not (tmp_path / "temp.txt").exists()
    assert result.output == str(tmp_path / "temp.txt")


def test_delete_file_missing_file_fails(tmp_path):
    action = DeleteFileAction({"desktop": tmp_path})
    result = action.run({"path": "ghost.txt"})
    assert not result.success
    assert "not found" in result.errors[0]


def test_delete_file_refuses_a_directory(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "keep.txt").write_text("keep me")
    action = DeleteFileAction({"desktop": tmp_path})

    result = action.run({"path": "sub"})

    assert not result.success
    assert "use delete_folder" in result.errors[0]
    assert (tmp_path / "sub" / "keep.txt").exists()  # nothing touched


def test_delete_file_validate_rejects_path_traversal(tmp_path):
    action = DeleteFileAction({"desktop": tmp_path})
    errors = action.validate({"path": "../secret.txt"})
    assert any("unsafe path" in e for e in errors)


def test_delete_file_validate_rejects_missing_path(tmp_path):
    action = DeleteFileAction({"desktop": tmp_path})
    errors = action.validate({})
    assert any("missing required parameter: path" in e for e in errors)


def test_delete_file_validate_rejects_unknown_location(tmp_path):
    action = DeleteFileAction({"desktop": tmp_path})
    errors = action.validate({"path": "x.txt", "location": "nowhere"})
    assert any("unknown location" in e for e in errors)


# ---- DeleteFolderAction ----------------------------------------------------------

def test_delete_folder_removes_folder_and_its_contents(tmp_path):
    (tmp_path / "temp").mkdir()
    (tmp_path / "temp" / "a.txt").write_text("a")
    (tmp_path / "temp" / "sub").mkdir()
    action = DeleteFolderAction({"desktop": tmp_path})

    result = action.run({"path": "temp"})

    assert result.success
    assert not (tmp_path / "temp").exists()
    assert result.output == str(tmp_path / "temp")


def test_delete_folder_missing_folder_fails(tmp_path):
    action = DeleteFolderAction({"desktop": tmp_path})
    result = action.run({"path": "ghost"})
    assert not result.success
    assert "not found" in result.errors[0]


def test_delete_folder_refuses_a_file(tmp_path):
    (tmp_path / "file.txt").write_text("x")
    action = DeleteFolderAction({"desktop": tmp_path})

    result = action.run({"path": "file.txt"})

    assert not result.success
    assert "use delete_file" in result.errors[0]
    assert (tmp_path / "file.txt").exists()


def test_delete_folder_validate_rejects_empty_path(tmp_path):
    action = DeleteFolderAction({"desktop": tmp_path})
    errors = action.validate({"path": ""})
    assert any("refusing to delete a location root" in e for e in errors)


def test_delete_folder_validate_rejects_dot_path(tmp_path):
    action = DeleteFolderAction({"desktop": tmp_path})
    errors = action.validate({"path": "."})
    assert any("refusing to delete a location root" in e for e in errors)


def test_delete_folder_validate_rejects_path_traversal(tmp_path):
    action = DeleteFolderAction({"desktop": tmp_path})
    errors = action.validate({"path": "../other"})
    assert any("unsafe path" in e for e in errors)


def test_delete_folder_validate_rejects_unknown_location(tmp_path):
    action = DeleteFolderAction({"desktop": tmp_path})
    errors = action.validate({"path": "temp", "location": "nowhere"})
    assert any("unknown location" in e for e in errors)
