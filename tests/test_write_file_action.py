"""WriteFileAction unit tests -- exercises validate()/run() directly, the
same pattern test_create_folder_action.py uses for CreateFolderAction.
This is the second filesystem primitive, and the one
WorkspaceBootstrapAction composes alongside create_folder. See
docs/MISSION_BRIEF_003.md.
"""
from __future__ import annotations

from master_agent.executor.actions.write_file import WriteFileAction
from master_agent.plugins.base import RiskTier


def make_action(tmp_path):
    return WriteFileAction(locations={"desktop": tmp_path})


def test_declares_reversible_write_risk_and_required_parameters():
    action = WriteFileAction(locations={})
    assert action.risk_tier == RiskTier.REVERSIBLE_WRITE
    assert action.required_parameters() == ["path"]
    assert action.expected_result


def test_validate_passes_for_a_well_formed_request(tmp_path):
    action = make_action(tmp_path)
    assert action.validate({"path": "README.md", "content": "hello", "location": "desktop"}) == []


def test_validate_catches_missing_path(tmp_path):
    action = make_action(tmp_path)
    errors = action.validate({"content": "hello"})
    assert any("path" in e for e in errors)


def test_validate_catches_unknown_location(tmp_path):
    action = make_action(tmp_path)
    errors = action.validate({"path": "README.md", "location": "downloads"})
    assert any("unknown location" in e for e in errors)


def test_validate_defaults_location_to_desktop(tmp_path):
    action = make_action(tmp_path)
    assert action.validate({"path": "README.md"}) == []


def test_validate_rejects_absolute_path(tmp_path):
    action = make_action(tmp_path)
    errors = action.validate({"path": "/etc/passwd"})
    assert any("unsafe path" in e for e in errors)


def test_validate_rejects_parent_traversal(tmp_path):
    action = make_action(tmp_path)
    errors = action.validate({"path": "../../etc/passwd"})
    assert any("unsafe path" in e for e in errors)


def test_validate_rejects_non_string_content(tmp_path):
    action = make_action(tmp_path)
    errors = action.validate({"path": "README.md", "content": 123})
    assert any("content must be a string" in e for e in errors)


def test_run_writes_file_under_configured_location(tmp_path):
    action = make_action(tmp_path)
    result = action.run({"path": "README.md", "content": "# Hello"})

    assert result.success
    created = tmp_path / "README.md"
    assert created.is_file()
    assert created.read_text() == "# Hello"
    assert result.output == str(created)
    assert result.errors == []


def test_run_creates_missing_parent_directories(tmp_path):
    action = make_action(tmp_path)
    result = action.run({"path": "docs/adr/0001-example.md", "content": "adr body"})

    assert result.success
    created = tmp_path / "docs" / "adr" / "0001-example.md"
    assert created.is_file()
    assert created.read_text() == "adr body"


def test_run_defaults_content_to_empty_string(tmp_path):
    action = make_action(tmp_path)
    result = action.run({"path": "empty.txt"})

    assert result.success
    assert (tmp_path / "empty.txt").read_text() == ""


def test_run_is_idempotent_when_content_is_unchanged(tmp_path):
    action = make_action(tmp_path)
    (tmp_path / "README.md").write_text("# Hello")

    result = action.run({"path": "README.md", "content": "# Hello"})

    assert result.success
    assert "already had this exact content" in result.warnings[0]


def test_run_overwrites_with_warning_when_content_differs(tmp_path):
    action = make_action(tmp_path)
    (tmp_path / "README.md").write_text("old content")

    result = action.run({"path": "README.md", "content": "new content"})

    assert result.success
    assert (tmp_path / "README.md").read_text() == "new content"
    assert "overwritten" in result.warnings[0]


def test_run_fails_if_path_exists_and_is_a_directory(tmp_path):
    action = make_action(tmp_path)
    (tmp_path / "README.md").mkdir()

    result = action.run({"path": "README.md", "content": "hello"})

    assert not result.success
    assert "not a file" in result.errors[0]
