"""Mission Brief 001 integration tests — the full conversation through the
real Orchestrator, real PermissionSystem, and real PluginRegistry, with
only the filesystem location sandboxed to tmp_path (via FilesystemPlugin's
DI seam) so nothing here ever touches the real Desktop.
"""
from __future__ import annotations

import pytest

from master_agent.cli import MasterAgentSession, UnrecognizedInput, parse_intent
from master_agent.mission_manager.mission import MissionStatus
from master_agent.orchestrator.orchestrator import Orchestrator
from master_agent.permissions.permission_system import PermissionSystem
from master_agent.plugins.filesystem_plugin import FilesystemPlugin
from master_agent.plugins.registry import PluginRegistry


# ---- parse_intent -----------------------------------------------------

@pytest.mark.parametrize(
    "text,expected_name,expected_location",
    [
        ("Create a folder called Demo on my Desktop.", "Demo", "Desktop"),
        ("create a folder called Demo", "Demo", "Desktop"),  # default location
        ('Create a folder named "Project X" on the Desktop', "Project X", "Desktop"),
        ("create folder called Demo", "Demo", "Desktop"),  # "a" is optional
    ],
)
def test_parse_intent_recognizes_create_folder(text, expected_name, expected_location):
    intent = parse_intent(text)
    assert intent.folder_name == expected_name
    assert intent.location == expected_location


def test_parse_intent_rejects_unrelated_text():
    with pytest.raises(UnrecognizedInput):
        parse_intent("What's the weather today?")


# ---- full session -------------------------------------------------------

def build_session(tmp_path) -> MasterAgentSession:
    registry = PluginRegistry()
    registry.register(FilesystemPlugin(locations={"desktop": tmp_path}))
    permissions = PermissionSystem()
    orchestrator = Orchestrator(registry, permissions)
    return MasterAgentSession(registry, permissions, orchestrator)


def test_wake_returns_greeting(tmp_path):
    session = build_session(tmp_path)
    reply = session.handle("Master Agent")
    assert "Hello! I'm awake." in reply


def test_full_happy_path_creates_folder_on_approval(tmp_path):
    session = build_session(tmp_path)
    session.handle("Master Agent")

    approval_prompt = session.handle("Create a folder called Demo on my Desktop.")
    assert 'Create folder "Demo"' in approval_prompt
    assert "Location:\nDesktop" in approval_prompt
    assert "Approve? (Yes/No)" in approval_prompt
    # Nothing should exist on disk yet — approval hasn't happened.
    assert not (tmp_path / "Demo").exists()

    final = session.handle("Yes")

    assert "Done." in final
    assert "Mission completed successfully" in final
    assert (tmp_path / "Demo").is_dir()
    assert session.last_mission.status == MissionStatus.COMPLETED
    assert session.last_mission.outcome["created_path"] == str(tmp_path / "Demo")


def test_declining_approval_does_not_create_folder(tmp_path):
    session = build_session(tmp_path)
    session.handle("Master Agent")
    session.handle("Create a folder called NoGo on my Desktop.")

    reply = session.handle("No")

    assert "cancelled" in reply.lower()
    assert not (tmp_path / "NoGo").exists()
    assert session.last_mission.status == MissionStatus.CANCELLED


def test_unrecognized_command_does_not_start_a_mission(tmp_path):
    session = build_session(tmp_path)
    session.handle("Master Agent")

    reply = session.handle("Sing me a song")

    assert "don't understand" in reply.lower()
    assert session.last_mission is None


def test_invalid_approval_answer_reprompts_without_losing_state(tmp_path):
    session = build_session(tmp_path)
    session.handle("Master Agent")
    session.handle("Create a folder called Demo on my Desktop.")

    reply = session.handle("maybe")
    assert "Yes or No" in reply
    assert not (tmp_path / "Demo").exists()

    final = session.handle("yes")
    assert "Done." in final
    assert (tmp_path / "Demo").is_dir()


def test_running_the_same_command_twice_is_idempotent(tmp_path):
    session = build_session(tmp_path)
    session.handle("Master Agent")

    session.handle("Create a folder called Demo on my Desktop.")
    session.handle("Yes")
    assert (tmp_path / "Demo").is_dir()

    # Second time round: fresh mission, same folder — should still succeed,
    # not error out because the folder already exists.
    session.handle("Create a folder called Demo on my Desktop.")
    second_final = session.handle("Yes")

    assert "Done." in second_final
    assert session.last_mission.status == MissionStatus.COMPLETED
