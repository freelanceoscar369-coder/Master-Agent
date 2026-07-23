"""Unit tests for FilesystemPlugin as a thin Plugin-contract adapter over
LocalExecutor + CreateFolderAction/WriteFileAction/WorkspaceBootstrapAction
(Mission Brief 002, extended in Mission Brief 003). Detailed business
logic for each action lives in its own test_*_action.py, testing the
action directly — this file only covers what the adapter itself is
responsible for: manifest shape, delegation, error-shape translation, and
the permission-grant relay to the Executor's own gate (see
docs/adr/0005-executor-permission-relay.md and, for the composite
capability, docs/adr/0006-composite-action-relay.md).
"""
from __future__ import annotations

import pytest

from master_agent.executor.executor import LocalExecutor
from master_agent.permissions.permission_system import PermissionSystem
from master_agent.plugins.base import RiskTier
from master_agent.plugins.filesystem_plugin import (
    CREATE_FOLDER,
    WORKSPACE_BOOTSTRAP,
    WRITE_FILE,
    FilesystemPlugin,
)


def make_plugin(tmp_path):
    executor = LocalExecutor(PermissionSystem())
    return FilesystemPlugin(executor, locations={"desktop": tmp_path}), executor


def test_manifest_declares_reversible_write_risk():
    executor = LocalExecutor(PermissionSystem())
    plugin = FilesystemPlugin(executor, locations={})
    cap = plugin.manifest.capabilities[0]
    assert cap.name == CREATE_FOLDER
    assert cap.risk_tier == RiskTier.REVERSIBLE_WRITE


def test_manifest_declares_all_three_capabilities():
    executor = LocalExecutor(PermissionSystem())
    plugin = FilesystemPlugin(executor, locations={})
    names = {cap.name for cap in plugin.manifest.capabilities}
    assert names == {CREATE_FOLDER, WRITE_FILE, WORKSPACE_BOOTSTRAP}
    assert all(cap.risk_tier == RiskTier.REVERSIBLE_WRITE for cap in plugin.manifest.capabilities)


def test_registers_create_folder_action_on_the_given_executor():
    executor = LocalExecutor(PermissionSystem())
    FilesystemPlugin(executor, locations={})
    # No public "is registered" query on LocalExecutor by design (keep its
    # surface small) -- registering the SAME action name twice raises,
    # which is the observable proof registration happened.
    with pytest.raises(ValueError):
        FilesystemPlugin(executor, locations={})


def test_invoke_delegates_to_executor_and_creates_folder(tmp_path):
    plugin, executor = make_plugin(tmp_path)
    result = plugin.invoke(CREATE_FOLDER, {"name": "Demo", "location": "desktop"})

    assert result.success
    assert (tmp_path / "Demo").is_dir()
    assert result.output == str(tmp_path / "Demo")
    # The Executor's own log proves execution actually went through it,
    # not some shortcut back to direct filesystem code in the plugin.
    assert len(executor.log) == 1
    assert executor.log[0].action_name == CREATE_FOLDER
    assert executor.log[0].status == "success"


def test_invoke_translates_action_failure_into_invocation_error(tmp_path):
    plugin, _executor = make_plugin(tmp_path)
    result = plugin.invoke(CREATE_FOLDER, {"name": "Demo", "location": "downloads"})

    assert not result.success
    assert "unknown location" in result.error


def test_invoke_rejects_unsupported_capability(tmp_path):
    plugin, executor = make_plugin(tmp_path)
    result = plugin.invoke("delete_folder", {"name": "Demo"})

    assert not result.success
    assert "unsupported capability" in result.error
    # Never even reached the executor for a capability this plugin
    # doesn't expose.
    assert executor.log == []


def test_second_invocation_does_not_require_a_fresh_human_approval(tmp_path):
    """The relay grant is scoped ONCE and consumed per invoke() call --
    confirms invoke() can be called repeatedly (e.g. the CLI's idempotent
    re-create-same-folder case from Mission Brief 001) without ever
    raising ApprovalRequired back out to a caller that isn't expecting it
    outside the Orchestrator's own approval flow."""
    plugin, executor = make_plugin(tmp_path)

    first = plugin.invoke(CREATE_FOLDER, {"name": "Demo", "location": "desktop"})
    second = plugin.invoke(CREATE_FOLDER, {"name": "Demo", "location": "desktop"})

    assert first.success
    assert second.success
    assert len(executor.log) == 2


# ---- write_file capability --------------------------------------------------

def test_invoke_write_file_delegates_to_executor_and_writes_content(tmp_path):
    plugin, executor = make_plugin(tmp_path)
    result = plugin.invoke(WRITE_FILE, {"path": "README.md", "content": "hello"})

    assert result.success
    assert (tmp_path / "README.md").read_text() == "hello"
    assert executor.log[-1].action_name == WRITE_FILE
    assert executor.log[-1].status == "success"


def test_invoke_write_file_translates_action_failure(tmp_path):
    plugin, _executor = make_plugin(tmp_path)
    result = plugin.invoke(WRITE_FILE, {"path": "../escape.txt", "content": "x"})

    assert not result.success
    assert "unsafe path" in result.error


# ---- workspace_bootstrap capability -----------------------------------------

def test_invoke_workspace_bootstrap_composes_create_folder_and_write_file(tmp_path):
    plugin, executor = make_plugin(tmp_path)
    result = plugin.invoke(
        WORKSPACE_BOOTSTRAP,
        {
            "name": "MyProject",
            "folders": ["src"],
            "files": [{"path": "README.md", "content": "# MyProject"}],
        },
    )

    assert result.success
    root = tmp_path / "MyProject"
    assert root.is_dir()
    assert (root / "src").is_dir()
    assert (root / "README.md").read_text() == "# MyProject"
    # Only ONE grant was relayed by this invoke() call (for
    # workspace_bootstrap itself), yet the sub-steps also ran through the
    # real Executor and got logged -- proof the composite relays its own
    # grants internally rather than this adapter needing to know about them.
    # (Sub-steps log first, the composite's own entry last -- nesting
    # order: see test_workspace_bootstrap_action.py for why.)
    action_names = [entry.action_name for entry in executor.log]
    assert action_names == [CREATE_FOLDER, CREATE_FOLDER, WRITE_FILE, WORKSPACE_BOOTSTRAP]


def test_invoke_workspace_bootstrap_does_not_ask_twice_on_repeat_invocation(tmp_path):
    plugin, executor = make_plugin(tmp_path)
    payload = {"name": "MyProject", "folders": ["src"]}

    first = plugin.invoke(WORKSPACE_BOOTSTRAP, payload)
    second = plugin.invoke(WORKSPACE_BOOTSTRAP, payload)

    assert first.success
    assert second.success
