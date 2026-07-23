"""Unit tests for FilesystemPlugin in isolation — no Orchestrator, no
Permission System, just the plugin's own contract with the disk.
"""
from __future__ import annotations

from master_agent.plugins.base import RiskTier
from master_agent.plugins.filesystem_plugin import CREATE_FOLDER, FilesystemPlugin


def make_plugin(tmp_path):
    return FilesystemPlugin(locations={"desktop": tmp_path})


def test_manifest_declares_reversible_write_risk():
    plugin = FilesystemPlugin(locations={})
    cap = plugin.manifest.capabilities[0]
    assert cap.name == CREATE_FOLDER
    assert cap.risk_tier == RiskTier.REVERSIBLE_WRITE


def test_creates_folder_under_configured_location(tmp_path):
    plugin = make_plugin(tmp_path)
    result = plugin.invoke(CREATE_FOLDER, {"name": "Demo", "location": "desktop"})

    assert result.success
    created = tmp_path / "Demo"
    assert created.is_dir()
    assert result.output == str(created)


def test_defaults_to_desktop_when_location_omitted(tmp_path):
    plugin = make_plugin(tmp_path)
    result = plugin.invoke(CREATE_FOLDER, {"name": "Demo"})

    assert result.success
    assert (tmp_path / "Demo").is_dir()


def test_idempotent_when_folder_already_exists(tmp_path):
    plugin = make_plugin(tmp_path)
    (tmp_path / "Demo").mkdir()

    result = plugin.invoke(CREATE_FOLDER, {"name": "Demo", "location": "desktop"})

    assert result.success
    assert result.output == str(tmp_path / "Demo")


def test_fails_if_path_exists_and_is_a_file(tmp_path):
    plugin = make_plugin(tmp_path)
    (tmp_path / "Demo").write_text("not a folder")

    result = plugin.invoke(CREATE_FOLDER, {"name": "Demo", "location": "desktop"})

    assert not result.success
    assert "not a folder" in result.error


def test_fails_on_missing_name(tmp_path):
    plugin = make_plugin(tmp_path)
    result = plugin.invoke(CREATE_FOLDER, {"location": "desktop"})

    assert not result.success
    assert "name" in result.error


def test_fails_on_unknown_location(tmp_path):
    plugin = make_plugin(tmp_path)
    result = plugin.invoke(CREATE_FOLDER, {"name": "Demo", "location": "downloads"})

    assert not result.success
    assert "unknown location" in result.error


def test_rejects_unsupported_capability(tmp_path):
    plugin = make_plugin(tmp_path)
    result = plugin.invoke("delete_folder", {"name": "Demo"})

    assert not result.success
    assert "unsupported capability" in result.error
