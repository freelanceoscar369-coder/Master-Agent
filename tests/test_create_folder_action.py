"""CreateFolderAction unit tests -- exercises validate()/run() directly,
with no Executor, Plugin, Orchestrator, or Permission System involved.
This is the business logic that used to live inline in FilesystemPlugin
(Mission Brief 001); Mission Brief 002 moved it here unchanged, so these
tests are the direct descendants of test_filesystem_plugin.py's old
create/idempotency/error-handling coverage.
"""
from __future__ import annotations

from master_agent.executor.actions.create_folder import CreateFolderAction
from master_agent.plugins.base import RiskTier


def make_action(tmp_path):
    return CreateFolderAction(locations={"desktop": tmp_path})


def test_declares_reversible_write_risk_and_required_parameters():
    action = CreateFolderAction(locations={})
    assert action.risk_tier == RiskTier.REVERSIBLE_WRITE
    assert action.required_parameters() == ["name"]
    assert action.expected_result  # non-empty, documents what success means


def test_validate_passes_for_a_well_formed_request(tmp_path):
    action = make_action(tmp_path)
    assert action.validate({"name": "Demo", "location": "desktop"}) == []


def test_validate_catches_missing_name(tmp_path):
    action = make_action(tmp_path)
    errors = action.validate({"location": "desktop"})
    assert any("name" in e for e in errors)


def test_validate_catches_unknown_location(tmp_path):
    action = make_action(tmp_path)
    errors = action.validate({"name": "Demo", "location": "downloads"})
    assert any("unknown location" in e for e in errors)


def test_validate_defaults_location_to_desktop(tmp_path):
    action = make_action(tmp_path)
    assert action.validate({"name": "Demo"}) == []


def test_run_creates_folder_under_configured_location(tmp_path):
    action = make_action(tmp_path)
    result = action.run({"name": "Demo", "location": "desktop"})

    assert result.success
    created = tmp_path / "Demo"
    assert created.is_dir()
    assert result.output == str(created)
    assert result.errors == []


def test_run_is_idempotent_when_folder_already_exists(tmp_path):
    action = make_action(tmp_path)
    (tmp_path / "Demo").mkdir()

    result = action.run({"name": "Demo", "location": "desktop"})

    assert result.success
    assert result.output == str(tmp_path / "Demo")
    assert "already existed" in result.warnings[0]


def test_run_fails_if_path_exists_and_is_a_file(tmp_path):
    action = make_action(tmp_path)
    (tmp_path / "Demo").write_text("not a folder")

    result = action.run({"name": "Demo", "location": "desktop"})

    assert not result.success
    assert "not a folder" in result.errors[0]
