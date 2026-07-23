"""Mission Brief 005 — the three MODIFY-category primitives:
RenameFileAction, CopyFileAction, MoveFileAction. Direct unit tests
against each Action, covering the brief's explicit "overwrite protection"
and "path traversal" requirements plus the into-folder-vs-literal-path
destination resolution shared via resolve_into_or_as().
"""
from __future__ import annotations

from master_agent.executor.actions.copy_file import CopyFileAction
from master_agent.executor.actions.move_file import MoveFileAction
from master_agent.executor.actions.rename_file import RenameFileAction
from master_agent.plugins.base import PermissionCategory, RiskTier


def test_all_three_are_reversible_write_and_categorized_modify():
    for action_cls in (RenameFileAction, CopyFileAction, MoveFileAction):
        action = action_cls({})
        assert action.risk_tier == RiskTier.REVERSIBLE_WRITE
        assert action.permission_category == PermissionCategory.MODIFY


# ---- RenameFileAction ---------------------------------------------------------

def test_rename_file_renames_within_same_directory(tmp_path):
    (tmp_path / "notes.txt").write_text("hi")
    action = RenameFileAction({"desktop": tmp_path})

    result = action.run({"path": "notes.txt", "new_name": "notes_old.txt"})

    assert result.success
    assert not (tmp_path / "notes.txt").exists()
    assert (tmp_path / "notes_old.txt").read_text() == "hi"
    assert result.output == str(tmp_path / "notes_old.txt")


def test_rename_file_missing_source_fails(tmp_path):
    action = RenameFileAction({"desktop": tmp_path})
    result = action.run({"path": "ghost.txt", "new_name": "x.txt"})
    assert not result.success
    assert "not found" in result.errors[0]


def test_rename_file_rejects_a_directory_source(tmp_path):
    (tmp_path / "sub").mkdir()
    action = RenameFileAction({"desktop": tmp_path})
    result = action.run({"path": "sub", "new_name": "sub2"})
    assert not result.success
    assert "not a file" in result.errors[0]


def test_rename_file_refuses_to_overwrite_by_default(tmp_path):
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.txt").write_text("b")
    action = RenameFileAction({"desktop": tmp_path})

    result = action.run({"path": "a.txt", "new_name": "b.txt"})

    assert not result.success
    assert "already exists" in result.errors[0]
    assert (tmp_path / "b.txt").read_text() == "b"


def test_rename_file_overwrites_when_explicitly_requested(tmp_path):
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.txt").write_text("b")
    action = RenameFileAction({"desktop": tmp_path})

    result = action.run({"path": "a.txt", "new_name": "b.txt", "overwrite": True})

    assert result.success
    assert (tmp_path / "b.txt").read_text() == "a"


def test_rename_file_validate_rejects_new_name_with_path_separator(tmp_path):
    action = RenameFileAction({"desktop": tmp_path})
    errors = action.validate({"path": "a.txt", "new_name": "sub/b.txt"})
    assert any("must be a bare filename" in e for e in errors)


def test_rename_file_validate_rejects_path_traversal(tmp_path):
    action = RenameFileAction({"desktop": tmp_path})
    errors = action.validate({"path": "../secret.txt", "new_name": "b.txt"})
    assert any("unsafe path" in e for e in errors)


def test_rename_file_validate_rejects_missing_new_name(tmp_path):
    action = RenameFileAction({"desktop": tmp_path})
    errors = action.validate({"path": "a.txt"})
    assert any("missing required parameter: new_name" in e for e in errors)


# ---- CopyFileAction -------------------------------------------------------------

def test_copy_file_into_an_existing_folder_keeps_filename(tmp_path):
    (tmp_path / "config.json").write_text("{}")
    (tmp_path / "backup").mkdir()
    action = CopyFileAction({"desktop": tmp_path})

    result = action.run({"path": "config.json", "destination": "backup"})

    assert result.success
    assert (tmp_path / "config.json").exists()  # source untouched
    assert (tmp_path / "backup" / "config.json").read_text() == "{}"
    assert result.output["destination"] == str(tmp_path / "backup" / "config.json")


def test_copy_file_as_a_literal_new_path(tmp_path):
    (tmp_path / "config.json").write_text("{}")
    action = CopyFileAction({"desktop": tmp_path})

    result = action.run({"path": "config.json", "destination": "config.bak.json"})

    assert result.success
    assert (tmp_path / "config.bak.json").read_text() == "{}"


def test_copy_file_missing_source_fails(tmp_path):
    action = CopyFileAction({"desktop": tmp_path})
    result = action.run({"path": "ghost.json", "destination": "x.json"})
    assert not result.success
    assert "not found" in result.errors[0]


def test_copy_file_refuses_to_overwrite_by_default(tmp_path):
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.txt").write_text("b")
    action = CopyFileAction({"desktop": tmp_path})

    result = action.run({"path": "a.txt", "destination": "b.txt"})

    assert not result.success
    assert "already exists" in result.errors[0]


def test_copy_file_overwrites_when_explicitly_requested(tmp_path):
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.txt").write_text("b")
    action = CopyFileAction({"desktop": tmp_path})

    result = action.run({"path": "a.txt", "destination": "b.txt", "overwrite": True})

    assert result.success
    assert (tmp_path / "b.txt").read_text() == "a"


def test_copy_file_validate_rejects_path_traversal_on_source_and_destination(tmp_path):
    action = CopyFileAction({"desktop": tmp_path})
    assert any("unsafe path" in e for e in action.validate({"path": "../a.txt", "destination": "b.txt"}))
    assert any(
        "unsafe destination" in e
        for e in action.validate({"path": "a.txt", "destination": "../b.txt"})
    )


# ---- MoveFileAction -------------------------------------------------------------

def test_move_file_into_an_existing_folder_keeps_filename(tmp_path):
    (tmp_path / "temp.txt").write_text("x")
    (tmp_path / "archive").mkdir()
    action = MoveFileAction({"desktop": tmp_path})

    result = action.run({"path": "temp.txt", "destination": "archive"})

    assert result.success
    assert not (tmp_path / "temp.txt").exists()
    assert (tmp_path / "archive" / "temp.txt").read_text() == "x"


def test_move_file_as_a_literal_new_path(tmp_path):
    (tmp_path / "temp.txt").write_text("x")
    action = MoveFileAction({"desktop": tmp_path})

    result = action.run({"path": "temp.txt", "destination": "final.txt"})

    assert result.success
    assert not (tmp_path / "temp.txt").exists()
    assert (tmp_path / "final.txt").read_text() == "x"


def test_move_file_missing_source_fails(tmp_path):
    action = MoveFileAction({"desktop": tmp_path})
    result = action.run({"path": "ghost.txt", "destination": "x.txt"})
    assert not result.success
    assert "not found" in result.errors[0]


def test_move_file_refuses_to_overwrite_by_default(tmp_path):
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.txt").write_text("b")
    action = MoveFileAction({"desktop": tmp_path})

    result = action.run({"path": "a.txt", "destination": "b.txt"})

    assert not result.success
    assert "already exists" in result.errors[0]
    assert (tmp_path / "a.txt").exists()  # nothing moved on refusal


def test_move_file_overwrites_when_explicitly_requested(tmp_path):
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.txt").write_text("b")
    action = MoveFileAction({"desktop": tmp_path})

    result = action.run({"path": "a.txt", "destination": "b.txt", "overwrite": True})

    assert result.success
    assert not (tmp_path / "a.txt").exists()
    assert (tmp_path / "b.txt").read_text() == "a"


def test_move_file_validate_rejects_path_traversal_on_source_and_destination(tmp_path):
    action = MoveFileAction({"desktop": tmp_path})
    assert any("unsafe path" in e for e in action.validate({"path": "../a.txt", "destination": "b.txt"}))
    assert any(
        "unsafe destination" in e
        for e in action.validate({"path": "a.txt", "destination": "../b.txt"})
    )
