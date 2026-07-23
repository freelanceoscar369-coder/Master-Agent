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
    ParsedActionIntent,
    ParsedProjectIntent,
    UnrecognizedInput,
    _validate_project_name,
    parse_intent,
)
from master_agent.executor.executor import LocalExecutor
from master_agent.memory.memory import Memory
from master_agent.memory.store import SQLiteMemoryStore
from master_agent.mission_manager.mission import MissionStatus
from master_agent.orchestrator.orchestrator import Orchestrator
from master_agent.permissions.permission_system import PermissionSystem
from master_agent.plugins.filesystem_plugin import (
    COPY_FILE,
    DELETE_FILE,
    DELETE_FOLDER,
    LIST_DIRECTORY,
    MOVE_FILE,
    READ_FILE,
    RENAME_FILE,
    SEARCH_FILES,
    FilesystemPlugin,
)
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

def build_session(tmp_path, memory: Memory | None = None) -> MasterAgentSession:
    permissions = PermissionSystem()
    executor = LocalExecutor(permissions)
    registry = PluginRegistry()
    registry.register(FilesystemPlugin(executor, locations={"desktop": tmp_path}))
    orchestrator = Orchestrator(registry, permissions)
    memory = memory or Memory(SQLiteMemoryStore(":memory:"))
    return MasterAgentSession(registry, permissions, orchestrator, memory)


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


# ==== Mission Brief 004: Memory ==============================================
#
# Automatic persistence (no manual save calls anywhere in this test file --
# every assertion below reaches Memory only through conversation, exactly
# like a real user would) and the two conversational memory queries from
# the brief. See MEMORY_ARCHITECTURE.md §7 and §9.

def test_successful_mission_is_persisted_automatically(tmp_path):
    session = build_session(tmp_path)
    session.handle("Master Agent")
    session.handle("Create a folder called Demo on my Desktop.")
    session.handle("Yes")

    record = session.memory.last_mission()

    assert record is not None
    assert record.title == 'Create Folder "Demo"'
    assert record.status == "completed"
    assert record.approval_status == "approved"
    assert record.folders_created == [str(tmp_path / "Demo")]
    assert record.files_created == []
    assert record.errors == []


def test_cancelled_mission_is_persisted_automatically(tmp_path):
    session = build_session(tmp_path)
    session.handle("Master Agent")
    session.handle("Create a folder called NoGo on my Desktop.")
    session.handle("No")

    record = session.memory.last_mission()

    assert record is not None
    assert record.status == "cancelled"
    assert record.approval_status == "denied"
    assert record.folders_created == []


def test_project_mission_persists_folders_and_files_created(tmp_path):
    session = build_session(tmp_path)
    session.handle("Master Agent")
    session.handle("Create a Python project called Demo.")
    session.handle("Yes")

    record = session.memory.last_mission()

    assert record.title == 'Create Python Project "Demo"'
    assert record.status == "completed"
    assert len(record.folders_created) == 5  # root + src + tests + docs + config
    assert len(record.files_created) == 4  # README, .gitignore, requirements.txt, main.py
    assert record.execution_time_seconds >= 0.0


def test_what_was_my_last_mission_before_any_mission(tmp_path):
    session = build_session(tmp_path)
    session.handle("Master Agent")

    reply = session.handle("What was my last mission?")

    assert "haven't run any missions" in reply.lower()
    # Asking the question must not itself start a Mission.
    assert session.last_mission is None


def test_what_was_my_last_mission_after_a_completed_mission(tmp_path):
    session = build_session(tmp_path)
    session.handle("Master Agent")
    session.handle("Create a Python project called Demo.")
    session.handle("Yes")

    reply = session.handle("What was my last mission?")

    assert reply.startswith("Your last mission was:\n")
    assert 'Create Python Project "Demo"' in reply
    assert "Completed successfully." in reply
    assert " at " in reply  # relative timestamp line, e.g. "Today at 3:05 PM."


def test_what_was_my_last_mission_reflects_most_recent_not_first(tmp_path):
    session = build_session(tmp_path)
    session.handle("Master Agent")
    session.handle("Create a folder called First on my Desktop.")
    session.handle("Yes")
    session.handle("Create a folder called Second on my Desktop.")
    session.handle("Yes")

    reply = session.handle("What was my last mission?")

    assert 'Create Folder "Second"' in reply
    assert "First" not in reply


def test_show_my_recent_missions_lists_in_newest_first_order(tmp_path):
    session = build_session(tmp_path)
    session.handle("Master Agent")

    session.handle("Create a folder called Alpha on my Desktop.")
    session.handle("Yes")
    session.handle("Create a folder called Beta on my Desktop.")
    session.handle("No")  # cancelled, still shows up
    session.handle("Create a folder called Gamma on my Desktop.")
    session.handle("Yes")

    reply = session.handle("Show my recent missions.")

    assert reply.startswith("1.\n")
    assert 'Create Folder "Gamma"' in reply
    assert 'Create Folder "Beta"' in reply
    assert 'Create Folder "Alpha"' in reply
    # Newest first.
    assert reply.index("Gamma") < reply.index("Beta") < reply.index("Alpha")
    # Status words per MEMORY_ARCHITECTURE.md §9.
    assert "Success" in reply
    assert "Cancelled" in reply


def test_show_my_recent_missions_before_any_mission(tmp_path):
    session = build_session(tmp_path)
    session.handle("Master Agent")

    reply = session.handle("Show my recent missions.")

    assert "haven't run any missions" in reply.lower()


def test_memory_query_does_not_interrupt_a_pending_approval(tmp_path):
    """If a mission is awaiting Yes/No, any text -- including something
    that looks like a memory query -- is treated as the approval answer,
    matching _handle_approval_response's existing "please answer yes or
    no" behavior. Memory queries are only recognized when nothing is
    pending."""
    session = build_session(tmp_path)
    session.handle("Master Agent")
    session.handle("Create a folder called Demo on my Desktop.")

    reply = session.handle("What was my last mission?")

    assert "Yes or No" in reply
    assert not (tmp_path / "Demo").exists()


def test_conversation_memory_records_every_turn(tmp_path):
    session = build_session(tmp_path)
    session.handle("Master Agent")
    session.handle("Create a folder called Demo on my Desktop.")
    session.handle("Yes")

    turns = session.memory.conversation_turns()
    speakers = [t.speaker for t in turns]

    assert speakers == ["user", "system", "user", "system", "user", "system"]
    assert turns[0].text == "Master Agent"


# ==== Mission Brief 005: filesystem capability expansion ======================
#
# The six conversation examples from the brief, through the exact same
# MasterAgentSession/Orchestrator/PermissionSystem/Executor path the
# folder/project tests above already exercise -- ParsedActionIntent is new,
# but nothing about how a plan built from it gets executed is. Read/List/
# Search are READ_ONLY -- PermissionSystem.check() short-circuits for that
# tier (see permission_system.py) -- so these three execute in a single
# turn with no Yes/No exchange; that itself is asserted below, not
# assumed.

def build_multi_location_session(tmp_path, memory: Memory | None = None):
    """Same as build_session() above, but with a second ("downloads")
    location -- needed for "List files inside Downloads", since the
    default build_session() only wires up "desktop"."""
    permissions = PermissionSystem()
    executor = LocalExecutor(permissions)
    registry = PluginRegistry()
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    registry.register(FilesystemPlugin(executor, locations={"desktop": tmp_path, "downloads": downloads}))
    orchestrator = Orchestrator(registry, permissions)
    memory = memory or Memory(SQLiteMemoryStore(":memory:"))
    return MasterAgentSession(registry, permissions, orchestrator, memory), downloads


# ---- parse_intent: the new shapes --------------------------------------------

@pytest.mark.parametrize(
    "text,expected_capability,expected_payload_subset",
    [
        ("Read README.md", READ_FILE, {"path": "README.md"}),
        ("Read README.md.", READ_FILE, {"path": "README.md"}),
        ("Rename notes.txt to notes_old.txt", RENAME_FILE, {"path": "notes.txt", "new_name": "notes_old.txt"}),
        ("Copy config.json to backup folder", COPY_FILE, {"path": "config.json", "destination": "backup"}),
        ("Copy config.json to config.bak.json", COPY_FILE, {"path": "config.json", "destination": "config.bak.json"}),
        ("Move temp.txt to archive folder", MOVE_FILE, {"path": "temp.txt", "destination": "archive"}),
        ("Delete notes.txt", DELETE_FILE, {"path": "notes.txt"}),
        ("Delete temp folder", DELETE_FOLDER, {"path": "temp"}),
        ("Search for *.pdf", SEARCH_FILES, {"pattern": "*.pdf"}),
    ],
)
def test_parse_intent_recognizes_mission_brief_005_shapes(text, expected_capability, expected_payload_subset):
    intent = parse_intent(text)
    assert isinstance(intent, ParsedActionIntent)
    assert intent.capability == expected_capability
    for key, value in expected_payload_subset.items():
        assert intent.payload[key] == value


def test_parse_intent_recognizes_list_directory():
    intent = parse_intent("List files inside Downloads")
    assert isinstance(intent, ParsedActionIntent)
    assert intent.capability == LIST_DIRECTORY
    assert intent.payload == {"path": ".", "location": "downloads"}


def test_parse_intent_still_recognizes_folder_and_project_shapes_unchanged():
    """Regression: the table-driven _INTENT_PATTERNS dispatch that
    replaced the old if/elif chain must not change behavior for the two
    pre-existing shapes."""
    folder_intent = parse_intent("Create a folder called Demo on my Desktop.")
    assert not isinstance(folder_intent, ParsedActionIntent)
    assert folder_intent.folder_name == "Demo"

    project_intent = parse_intent("Create a Python project called Demo.")
    assert isinstance(project_intent, ParsedProjectIntent)


# ---- full session: read / list / search (no approval) ------------------------

def test_read_file_executes_without_asking_for_approval(tmp_path):
    (tmp_path / "README.md").write_text("# Hello Kalpavriksh")
    session = build_session(tmp_path)
    session.handle("Master Agent")

    reply = session.handle("Read README.md")

    assert "Approve?" not in reply
    assert "Done." in reply
    assert "# Hello Kalpavriksh" in reply
    assert session.last_mission.status == MissionStatus.COMPLETED


def test_read_missing_file_fails_cleanly(tmp_path):
    session = build_session(tmp_path)
    session.handle("Master Agent")

    reply = session.handle("Read ghost.txt")

    assert "Something went wrong" in reply
    assert session.last_mission.status == MissionStatus.FAILED


def test_list_files_inside_downloads(tmp_path):
    session, downloads = build_multi_location_session(tmp_path)
    (downloads / "report.pdf").write_text("x")
    (downloads / "sub").mkdir()
    session.handle("Master Agent")

    reply = session.handle("List files inside Downloads")

    assert "Approve?" not in reply
    assert "report.pdf" in reply
    assert "sub" in reply


def test_search_for_pattern(tmp_path):
    (tmp_path / "a.pdf").write_text("x")
    (tmp_path / "b.txt").write_text("x")
    session = build_session(tmp_path)
    session.handle("Master Agent")

    reply = session.handle("Search for *.pdf")

    assert "Approve?" not in reply
    assert "a.pdf" in reply
    assert "b.txt" not in reply


# ---- full session: rename / copy / move (approval required) ------------------

def test_rename_requires_approval_and_renames_on_yes(tmp_path):
    (tmp_path / "notes.txt").write_text("hi")
    session = build_session(tmp_path)
    session.handle("Master Agent")

    approval = session.handle("Rename notes.txt to notes_old.txt")
    assert "Approve? (Yes/No)" in approval
    assert (tmp_path / "notes.txt").exists()  # not yet renamed -- approval hasn't happened

    final = session.handle("Yes")
    assert "Done." in final
    assert not (tmp_path / "notes.txt").exists()
    assert (tmp_path / "notes_old.txt").read_text() == "hi"


def test_copy_into_a_folder(tmp_path):
    (tmp_path / "config.json").write_text("{}")
    (tmp_path / "backup").mkdir()
    session = build_session(tmp_path)
    session.handle("Master Agent")

    session.handle("Copy config.json to backup folder")
    final = session.handle("Yes")

    assert "Done." in final
    assert (tmp_path / "config.json").exists()  # source untouched
    assert (tmp_path / "backup" / "config.json").read_text() == "{}"


def test_move_added_for_symmetry_with_copy(tmp_path):
    (tmp_path / "temp.txt").write_text("x")
    (tmp_path / "archive").mkdir()
    session = build_session(tmp_path)
    session.handle("Master Agent")

    session.handle("Move temp.txt to archive folder")
    final = session.handle("Yes")

    assert "Done." in final
    assert not (tmp_path / "temp.txt").exists()
    assert (tmp_path / "archive" / "temp.txt").read_text() == "x"


def test_rename_overwrite_is_refused_without_a_silent_replace(tmp_path):
    """The intent parser doesn't expose an "overwrite" phrasing -- this
    confirms that gap surfaces as a clean failure (resolve_overwrite_error's
    refusal is an ordinary ExecutionResult failure, and _finish's failure
    branch already handles any such failure generically), never as a
    silent overwrite or a crash."""
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.txt").write_text("b")
    session = build_session(tmp_path)
    session.handle("Master Agent")
    session.handle("Rename a.txt to b.txt")

    reply = session.handle("Yes")

    assert "Something went wrong" in reply
    assert "already exists" in reply
    assert (tmp_path / "b.txt").read_text() == "b"  # untouched


# ---- full session: delete (approval required, file vs. folder disambiguation) --

def test_delete_folder_requires_approval_and_deletes_on_yes(tmp_path):
    (tmp_path / "temp").mkdir()
    (tmp_path / "temp" / "junk.txt").write_text("junk")
    session = build_session(tmp_path)
    session.handle("Master Agent")

    approval = session.handle("Delete temp folder")
    assert "permanently delete this folder" in approval
    assert (tmp_path / "temp").exists()

    final = session.handle("Yes")
    assert "Done." in final
    assert not (tmp_path / "temp").exists()


def test_delete_file_is_disambiguated_from_delete_folder(tmp_path):
    (tmp_path / "notes.txt").write_text("x")
    session = build_session(tmp_path)
    session.handle("Master Agent")

    approval = session.handle("Delete notes.txt")
    assert "permanently delete this file" in approval

    final = session.handle("Yes")
    assert "Done." in final
    assert not (tmp_path / "notes.txt").exists()


def test_declining_delete_folder_approval_deletes_nothing(tmp_path):
    (tmp_path / "temp").mkdir()
    (tmp_path / "temp" / "keep.txt").write_text("keep")
    session = build_session(tmp_path)
    session.handle("Master Agent")
    session.handle("Delete temp folder")

    reply = session.handle("No")

    assert "cancelled" in reply.lower()
    assert (tmp_path / "temp" / "keep.txt").exists()
    assert session.last_mission.status == MissionStatus.CANCELLED


def test_declining_delete_file_approval_deletes_nothing(tmp_path):
    (tmp_path / "notes.txt").write_text("keep me")
    session = build_session(tmp_path)
    session.handle("Master Agent")
    session.handle("Delete notes.txt")

    reply = session.handle("No")

    assert "cancelled" in reply.lower()
    assert (tmp_path / "notes.txt").exists()


# ---- Memory persistence for the new capabilities ------------------------------

def test_read_mission_persists_with_no_artifacts(tmp_path):
    (tmp_path / "README.md").write_text("hi")
    session = build_session(tmp_path)
    session.handle("Master Agent")
    session.handle("Read README.md")

    record = session.memory.last_mission()

    assert record.title == 'Read "README.md"'
    assert record.status == "completed"
    assert record.artifacts == []


def test_delete_folder_mission_persists_a_deleted_folder_artifact(tmp_path):
    (tmp_path / "temp").mkdir()
    session = build_session(tmp_path)
    session.handle("Master Agent")
    session.handle("Delete temp folder")
    session.handle("Yes")

    record = session.memory.last_mission()

    assert record.title == 'Delete Folder "temp"'
    assert record.artifacts == [{"type": "deleted_folder", "path": str(tmp_path / "temp")}]


def test_rename_mission_persists_a_file_artifact(tmp_path):
    (tmp_path / "notes.txt").write_text("x")
    session = build_session(tmp_path)
    session.handle("Master Agent")
    session.handle("Rename notes.txt to notes_old.txt")
    session.handle("Yes")

    record = session.memory.last_mission()

    assert record.artifacts == [{"type": "file", "path": str(tmp_path / "notes_old.txt")}]


def test_copy_mission_persists_the_destination_as_a_file_artifact(tmp_path):
    (tmp_path / "config.json").write_text("{}")
    session = build_session(tmp_path)
    session.handle("Master Agent")
    session.handle("Copy config.json to config.bak.json")
    session.handle("Yes")

    record = session.memory.last_mission()

    assert record.artifacts == [{"type": "file", "path": str(tmp_path / "config.bak.json")}]


def test_search_and_list_missions_also_persist_with_no_artifacts(tmp_path):
    (tmp_path / "a.pdf").write_text("x")
    session = build_session(tmp_path)
    session.handle("Master Agent")
    session.handle("Search for *.pdf")

    record = session.memory.last_mission()

    assert record.title == 'Search for "*.pdf"'
    assert record.artifacts == []
