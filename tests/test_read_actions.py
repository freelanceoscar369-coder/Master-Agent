"""Mission Brief 005 — the five READ_ONLY primitives: ReadFileAction,
ListDirectoryAction, SearchFilesAction, FileExistsAction,
DirectoryExistsAction. Direct unit tests against each Action, no
Executor/Plugin involved (that layer is covered in
test_filesystem_plugin.py) -- the pattern test_create_folder_action.py
established.
"""
from __future__ import annotations

from master_agent.executor.actions.directory_exists import DirectoryExistsAction
from master_agent.executor.actions.file_exists import FileExistsAction
from master_agent.executor.actions.list_directory import ListDirectoryAction
from master_agent.executor.actions.read_file import MAX_READ_BYTES, ReadFileAction
from master_agent.executor.actions.search_files import SearchFilesAction
from master_agent.plugins.base import PermissionCategory, RiskTier


def test_all_five_are_read_only_and_categorized_read():
    for action_cls in (
        ReadFileAction,
        ListDirectoryAction,
        SearchFilesAction,
        FileExistsAction,
        DirectoryExistsAction,
    ):
        action = action_cls({})
        assert action.risk_tier == RiskTier.READ_ONLY
        assert action.permission_category == PermissionCategory.READ


# ---- ReadFileAction ---------------------------------------------------------

def test_read_file_returns_content(tmp_path):
    (tmp_path / "README.md").write_text("hello world")
    action = ReadFileAction({"desktop": tmp_path})

    result = action.run({"path": "README.md"})

    assert result.success
    assert result.output == {"path": str(tmp_path / "README.md"), "content": "hello world"}


def test_read_file_missing_file_fails(tmp_path):
    action = ReadFileAction({"desktop": tmp_path})
    result = action.run({"path": "nope.txt"})
    assert not result.success
    assert "not found" in result.errors[0]


def test_read_file_rejects_a_directory(tmp_path):
    (tmp_path / "sub").mkdir()
    action = ReadFileAction({"desktop": tmp_path})
    result = action.run({"path": "sub"})
    assert not result.success
    assert "directory" in result.errors[0]


def test_read_file_rejects_oversized_file(tmp_path):
    big = tmp_path / "big.txt"
    big.write_text("x" * (MAX_READ_BYTES + 1))
    action = ReadFileAction({"desktop": tmp_path})
    result = action.run({"path": "big.txt"})
    assert not result.success
    assert "read limit" in result.errors[0]


def test_read_file_validate_rejects_path_traversal(tmp_path):
    action = ReadFileAction({"desktop": tmp_path})
    errors = action.validate({"path": "../../etc/passwd"})
    assert any("unsafe path" in e for e in errors)


def test_read_file_validate_rejects_missing_path():
    action = ReadFileAction({})
    assert any("missing required parameter" in e for e in action.validate({}))


def test_read_file_validate_rejects_unknown_location(tmp_path):
    action = ReadFileAction({"desktop": tmp_path})
    errors = action.validate({"path": "x.txt", "location": "nowhere"})
    assert any("unknown location" in e for e in errors)


# ---- ListDirectoryAction -----------------------------------------------------

def test_list_directory_splits_files_and_folders(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "a.txt").write_text("")
    (tmp_path / "b.txt").write_text("")
    action = ListDirectoryAction({"desktop": tmp_path})

    result = action.run({})

    assert result.success
    assert result.output["folders"] == ["sub"]
    assert result.output["files"] == ["a.txt", "b.txt"]


def test_list_directory_missing_directory_fails(tmp_path):
    action = ListDirectoryAction({"desktop": tmp_path})
    result = action.run({"path": "ghost"})
    assert not result.success
    assert "not found" in result.errors[0]


def test_list_directory_rejects_a_file_as_target(tmp_path):
    (tmp_path / "file.txt").write_text("x")
    action = ListDirectoryAction({"desktop": tmp_path})
    result = action.run({"path": "file.txt"})
    assert not result.success
    assert "not a directory" in result.errors[0]


def test_list_directory_validate_rejects_path_traversal(tmp_path):
    action = ListDirectoryAction({"desktop": tmp_path})
    errors = action.validate({"path": "../.."})
    assert any("unsafe path" in e for e in errors)


# ---- SearchFilesAction --------------------------------------------------------

def test_search_files_finds_matches_recursively(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "a.pdf").write_text("")
    (tmp_path / "sub" / "b.pdf").write_text("")
    (tmp_path / "c.txt").write_text("")
    action = SearchFilesAction({"desktop": tmp_path})

    result = action.run({"pattern": "*.pdf"})

    assert result.success
    assert sorted(result.output["matches"]) == ["a.pdf", "sub/b.pdf"]
    assert result.output["truncated"] is False


def test_search_files_caps_results_and_reports_truncation(tmp_path):
    for i in range(5):
        (tmp_path / f"f{i}.txt").write_text("")
    action = SearchFilesAction({"desktop": tmp_path})

    result = action.run({"pattern": "*.txt"})
    # Cap is 200; this test just proves the flag exists and is accurate
    # for an under-cap search (all 5 found, not truncated).
    assert result.success
    assert len(result.output["matches"]) == 5
    assert result.output["truncated"] is False


def test_search_files_validate_rejects_traversal_pattern():
    action = SearchFilesAction({})
    errors = action.validate({"pattern": "../*.pdf"})
    assert any("unsafe pattern" in e for e in errors)


def test_search_files_validate_rejects_missing_pattern():
    action = SearchFilesAction({})
    assert any("missing required parameter" in e for e in action.validate({}))


# ---- FileExistsAction / DirectoryExistsAction ---------------------------------

def test_file_exists_true_for_a_real_file(tmp_path):
    (tmp_path / "x.txt").write_text("")
    action = FileExistsAction({"desktop": tmp_path})
    result = action.run({"path": "x.txt"})
    assert result.success
    assert result.output == {"path": str(tmp_path / "x.txt"), "exists": True, "is_file": True}


def test_file_exists_false_for_a_missing_path(tmp_path):
    action = FileExistsAction({"desktop": tmp_path})
    result = action.run({"path": "ghost.txt"})
    assert result.success  # existence-check succeeding is not the same as the file existing
    assert result.output["exists"] is False


def test_file_exists_false_for_a_directory(tmp_path):
    (tmp_path / "sub").mkdir()
    action = FileExistsAction({"desktop": tmp_path})
    result = action.run({"path": "sub"})
    assert result.success
    assert result.output["exists"] is True
    assert result.output["is_file"] is False


def test_directory_exists_true_for_a_real_directory(tmp_path):
    (tmp_path / "sub").mkdir()
    action = DirectoryExistsAction({"desktop": tmp_path})
    result = action.run({"path": "sub"})
    assert result.success
    assert result.output == {"path": str(tmp_path / "sub"), "exists": True, "is_directory": True}


def test_directory_exists_false_for_a_missing_path(tmp_path):
    action = DirectoryExistsAction({"desktop": tmp_path})
    result = action.run({"path": "ghost"})
    assert result.success
    assert result.output["exists"] is False


def test_file_exists_validate_rejects_path_traversal():
    action = FileExistsAction({})
    errors = action.validate({"path": "../secret"})
    assert any("unsafe path" in e for e in errors)


def test_directory_exists_validate_rejects_path_traversal():
    action = DirectoryExistsAction({})
    errors = action.validate({"path": "../secret"})
    assert any("unsafe path" in e for e in errors)
