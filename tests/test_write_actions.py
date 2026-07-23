"""Mission Brief 005 — AppendFileAction, the write-tier primitive that
joins WriteFileAction (tested separately in test_write_file_action.py).
Direct unit tests against the Action, same pattern as test_read_actions.py.
"""
from __future__ import annotations

from master_agent.executor.actions.append_file import AppendFileAction
from master_agent.plugins.base import PermissionCategory, RiskTier


def make_action(tmp_path):
    return AppendFileAction({"desktop": tmp_path})


def test_declares_reversible_write_risk_and_write_category():
    action = AppendFileAction({})
    assert action.risk_tier == RiskTier.REVERSIBLE_WRITE
    assert action.permission_category == PermissionCategory.WRITE
    assert action.required_parameters() == ["path", "content"]


def test_creates_file_when_missing(tmp_path):
    action = make_action(tmp_path)
    result = action.run({"path": "log.txt", "content": "first line\n"})

    assert result.success
    created = tmp_path / "log.txt"
    assert created.read_text() == "first line\n"
    assert result.output == str(created)
    assert result.warnings == []


def test_appends_to_an_existing_file_without_truncating(tmp_path):
    (tmp_path / "log.txt").write_text("first line\n")
    action = make_action(tmp_path)

    result = action.run({"path": "log.txt", "content": "second line\n"})

    assert result.success
    assert (tmp_path / "log.txt").read_text() == "first line\nsecond line\n"
    assert "extended, not replaced" in result.warnings[0]


def test_creates_missing_parent_directories(tmp_path):
    action = make_action(tmp_path)
    result = action.run({"path": "notes/today.txt", "content": "hi"})

    assert result.success
    assert (tmp_path / "notes" / "today.txt").read_text() == "hi"


def test_fails_when_target_is_a_directory(tmp_path):
    (tmp_path / "log.txt").mkdir()
    action = make_action(tmp_path)

    result = action.run({"path": "log.txt", "content": "x"})

    assert not result.success
    assert "not a file" in result.errors[0]


def test_validate_rejects_missing_path(tmp_path):
    action = make_action(tmp_path)
    errors = action.validate({"content": "x"})
    assert any("missing required parameter: path" in e for e in errors)


def test_validate_rejects_non_string_content(tmp_path):
    action = make_action(tmp_path)
    errors = action.validate({"path": "log.txt", "content": 123})
    assert any("content must be a string" in e for e in errors)


def test_validate_rejects_path_traversal(tmp_path):
    action = make_action(tmp_path)
    errors = action.validate({"path": "../../etc/passwd", "content": "x"})
    assert any("unsafe path" in e for e in errors)


def test_validate_rejects_unknown_location(tmp_path):
    action = make_action(tmp_path)
    errors = action.validate({"path": "log.txt", "content": "x", "location": "nowhere"})
    assert any("unknown location" in e for e in errors)


def test_validate_defaults_location_to_desktop(tmp_path):
    action = make_action(tmp_path)
    assert action.validate({"path": "log.txt", "content": "x"}) == []
