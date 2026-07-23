"""Mission Brief 001 integration tests — the full conversation through the
real Orchestrator, real PermissionSystem, and real PluginRegistry, with
only the filesystem location sandboxed to tmp_path (via FilesystemPlugin's
DI seam) so nothing here ever touches the real Desktop.

As of Mission Brief 002, FilesystemPlugin is a thin adapter over
LocalExecutor + CreateFolderAction (see executor/), but the flow this
file exercises — and every assertion in it — is unchanged: this is the
regression test proving the create-folder mission still works exactly as
before after that refactor.

Mission Brief 003.1 added a second conversation shape ("create a
project") reaching the workspace_bootstrap composite from Mission Brief
003, through the exact same Orchestrator/PermissionSystem/Executor path —
see the "project creation" section below. Nothing in the folder-creation
section changed.
"""
from __future__ import annotations

import pytest

from master_agent.cli import (
    InvalidProjectRequest,
    MasterAgentSession,
    ParsedProjectIntent,
    UnrecognizedInput,
    _validate_project_name,
    parse_intent,
)
from master_agent.executor.executor import LocalExecutor
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
    permissions = PermissionSystem()
    executor = LocalExecutor(permissions)
    registry = PluginRegistry()
    registry.register(FilesystemPlugin(executor, locations={"desktop": tmp_path}))
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


# ==== Mission Brief 003.1: project creation ==================================
#
# Conversation -> Intent Parser -> Mission -> (hand-built) Planner ->
# Permission System -> Executor -> WorkspaceBootstrapAction ->
# CreateFolderAction / WriteFileAction. Every layer below MasterAgentSession
# is exactly what the folder-creation tests above already exercise --
# these tests confirm the NEW intent shape reaches it correctly, not that
# the layers themselves behave differently.

# ---- parse_intent: project shape -------------------------------------------

@pytest.mark.parametrize(
    "text,expected_name,expected_type,expected_label",
    [
        ("Create a Python project called Demo.", "Demo", "python", "Python"),
        ("Create a project called Expense Tracker.", "Expense Tracker", "generic", ""),
        ("Create a new application named Budget App.", "Budget App", "generic", ""),
        ("create a python project called demo", "demo", "python", "Python"),  # case-insensitive
        ("Create a Rust project called Widget.", "Widget", "generic", ""),  # unrecognized type -> fallback
    ],
)
def test_parse_intent_recognizes_project_creation(text, expected_name, expected_type, expected_label):
    intent = parse_intent(text)
    assert isinstance(intent, ParsedProjectIntent)
    assert intent.project_name == expected_name
    assert intent.project_type == expected_type
    assert intent.project_type_label == expected_label


def test_parse_intent_raises_invalid_project_request_for_unsafe_name():
    with pytest.raises(InvalidProjectRequest) as excinfo:
        parse_intent("Create a project called /etc.")
    assert any("unsafe project name" in reason for reason in excinfo.value.reasons)


def test_validate_project_name_catches_empty_name():
    assert any("missing a project name" in e for e in _validate_project_name(""))


def test_validate_project_name_catches_traversal():
    assert any("unsafe project name" in e for e in _validate_project_name("../escape"))


def test_validate_project_name_passes_for_ordinary_names():
    assert _validate_project_name("Expense Tracker") == []


# ---- full session: python project creation ----------------------------------

def test_full_happy_path_creates_python_project_on_approval(tmp_path):
    session = build_session(tmp_path)
    session.handle("Master Agent")

    approval_prompt = session.handle("Create a Python project called Demo.")
    assert "Mission:\nCreate Python Project" in approval_prompt
    assert "Project:\nDemo" in approval_prompt
    assert "Create workspace" in approval_prompt
    assert "Approve? (Yes/No)" in approval_prompt
    # Nothing should exist on disk yet -- approval hasn't happened.
    assert not (tmp_path / "Demo").exists()

    final = session.handle("Yes")

    assert "Done." in final
    assert 'Python project "Demo" created successfully' in final
    assert "Folders created: 5" in final  # root + src + tests + docs + config
    assert "Files created: 4" in final  # README, .gitignore, requirements.txt, main.py
    assert "Mission completed successfully" in final

    root = tmp_path / "Demo"
    assert root.is_dir()
    assert (root / "src").is_dir()
    assert (root / "tests").is_dir()
    assert (root / "docs").is_dir()
    assert (root / "config").is_dir()
    assert (root / "README.md").read_text() == "# Demo\n"
    assert (root / "main.py").exists()
    assert (root / ".gitignore").exists()
    assert (root / "requirements.txt").exists()

    assert session.last_mission.status == MissionStatus.COMPLETED
    assert session.last_mission.outcome["created_workspace"]["root"] == str(root)


# ---- full session: generic project creation ----------------------------------

def test_full_happy_path_creates_generic_project_when_type_is_omitted(tmp_path):
    session = build_session(tmp_path)
    session.handle("Master Agent")

    approval_prompt = session.handle("Create a project called Expense Tracker.")
    assert "Mission:\nCreate Project" in approval_prompt  # no type label
    assert "Project:\nExpense Tracker" in approval_prompt

    final = session.handle("Yes")

    assert "Done." in final
    assert 'project "Expense Tracker" created successfully' in final
    # No language prefix for the generic template.
    assert 'Python project' not in final

    root = tmp_path / "Expense Tracker"
    assert root.is_dir()
    assert (root / "src").is_dir()
    assert (root / "docs").is_dir()
    assert (root / "README.md").read_text() == "# Expense Tracker\n"
    # The generic template has no tests/config/main.py/.gitignore -- confirms
    # this really is the fallback template, not the Python one by accident.
    assert not (root / "tests").exists()
    assert not (root / "main.py").exists()


def test_unrecognized_project_type_falls_back_to_generic_template(tmp_path):
    """"Unknown project type -> fall back to default template" from the
    Error Handling section -- the user DID specify a type, it's just not
    one Master Agent has a template for."""
    session = build_session(tmp_path)
    session.handle("Master Agent")
    session.handle("Create a Rust project called Widget.")
    final = session.handle("Yes")

    assert "Done." in final
    root = tmp_path / "Widget"
    assert (root / "src").is_dir()
    assert (root / "docs").is_dir()
    assert not (root / "tests").exists()  # proves it's the generic template, not Python's


# ---- permission denied -------------------------------------------------------

def test_declining_project_approval_creates_nothing(tmp_path):
    session = build_session(tmp_path)
    session.handle("Master Agent")
    session.handle("Create a Python project called NoGo.")

    reply = session.handle("No")

    assert "cancelled" in reply.lower()
    assert not (tmp_path / "NoGo").exists()
    assert session.last_mission.status == MissionStatus.CANCELLED


# ---- invalid project name -----------------------------------------------------

def test_invalid_project_name_explains_the_problem_without_starting_a_mission(tmp_path):
    session = build_session(tmp_path)
    session.handle("Master Agent")

    reply = session.handle("Create a project called /etc.")

    assert "can't create that project" in reply
    assert "unsafe project name" in reply
    assert session.last_mission is None
    assert list(tmp_path.iterdir()) == []


# ---- only one approval for the whole composite mission -----------------------

def test_only_one_approval_is_asked_for_the_whole_project_mission(tmp_path):
    """The CLI/Mission layer grants exactly one ONCE approval
    (create_python_project's step.capability). Everything downstream --
    including WorkspaceBootstrapAction relaying its OWN grants to
    create_folder/write_file (docs/adr/0006-composite-action-relay.md) --
    must not need a second answer from the human."""
    session = build_session(tmp_path)
    session.handle("Master Agent")
    session.handle("Create a Python project called Demo.")

    final = session.handle("Yes")  # exactly one approval

    assert "Done." in final
    assert (tmp_path / "Demo" / "src").is_dir()


# ---- full conversation transcript --------------------------------------------

def test_full_conversation_transcript_matches_expected_shape(tmp_path):
    """End-to-end transcript check mirroring Mission Brief 003.1's UX
    example almost verbatim -- wake, request, plan display, approval,
    completion summary."""
    session = build_session(tmp_path)

    greeting = session.handle("Master Agent")
    assert greeting == "Hello! I'm awake.\nWhat would you like me to do?"

    plan_message = session.handle("Create a Python project called Demo.")
    assert "Mission:\nCreate Python Project" in plan_message
    assert "Project:\nDemo" in plan_message
    assert "Plan:" in plan_message
    assert "• Create workspace" in plan_message
    assert "• Create folders" in plan_message
    assert "• Create starter files" in plan_message
    assert "This will modify your filesystem." in plan_message
    assert "Approve? (Yes/No)" in plan_message

    completion_message = session.handle("Yes")
    assert completion_message.startswith("Done.")
    assert 'Python project "Demo" created successfully.' in completion_message
    assert "Execution time:" in completion_message
    assert "Folders created:" in completion_message
    assert "Files created:" in completion_message
    assert "Mission completed successfully." in completion_message


# ---- regression: unrecognized input still behaves as before ------------------

def test_unrecognized_command_still_does_not_start_a_mission_with_project_hint(tmp_path):
    session = build_session(tmp_path)
    session.handle("Master Agent")

    reply = session.handle("Sing me a song")

    assert "don't understand" in reply.lower()
    assert session.last_mission is None
