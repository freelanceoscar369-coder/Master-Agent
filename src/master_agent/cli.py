"""Mission Brief 001 — The First Conversation. Extended in Mission Brief
003.1 to reach the Workspace Bootstrap capability from Mission Brief 003,
and in Mission Brief 005 to reach the eleven new filesystem primitives
(read/list/search/exists-checks, append, rename/copy/move,
delete-file/delete-folder) from FILESYSTEM_CAPABILITIES.md.

The smallest possible end-to-end slice through the real architecture:
text in, one real mission out. Deliberately does NOT touch the Mission
Manager (persistence), Model Router, Memory, or either model provider —
those stay out of scope. What's real here: rule-based intent parsing, the
actual PermissionSystem gate, the actual Orchestrator + PluginRegistry,
and real filesystem writes via FilesystemPlugin — which, as of Mission
Brief 002, is a thin adapter over the LocalExecutor + Action Contract
(see executor/executor.py and docs/MISSION_BRIEF_002.md).

The Step/MissionPlan shapes used below are the same ones the real Planner
(planner/planner.py) will eventually produce — this module hand-builds a
plan instead of calling a model, but nothing downstream (Orchestrator,
plugins, Permission System) needs to change when a real Planner replaces
`build_plan`. Mission Brief 003.1 added a second recognized intent
shape — "create a project" — that hand-builds a plan targeting the
`workspace_bootstrap` composite capability (see
executor/actions/workspace_bootstrap.py and
docs/MISSION_BRIEF_003.md) instead of `create_folder`. Nothing about how
that plan is executed differs from the folder-creation path: same
Orchestrator, same Permission System, same relay mechanism — this module
never had to know a composite action was involved, which is exactly the
point of Mission Brief 003's design.

Mission Brief 005 generalizes this further: rather than one dataclass per
new capability (which would mean eight more ParsedXIntent shapes and eight
more branches in every downstream method), every new capability is
represented by a single generic `ParsedActionIntent` — capability name +
payload + a few display strings — and intent parsing itself moved to a
table (`_INTENT_PATTERNS`) of (regex, builder) pairs instead of a growing
if/elif chain, matching the same "avoid long if/else chains, design for
many" principle FilesystemPlugin's own registration follows
(FILESYSTEM_CAPABILITIES.md §4). Read/List/Search never trigger the
approval flow at all — they're READ_ONLY, and PermissionSystem.check()
already short-circuits for that tier (see permission_system.py) — so
those three intents simply execute and return a result in one turn, the
same as every other READ_ONLY capability would.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from master_agent.executor.action import is_unsafe_relative_path
from master_agent.executor.executor import LocalExecutor
from master_agent.memory.memory import Memory
from master_agent.memory.store import MissionRecord, SQLiteMemoryStore
from master_agent.mission_manager.mission import Mission, MissionStatus
from master_agent.orchestrator.orchestrator import Orchestrator, StepResult
from master_agent.permissions.permission_system import GrantScope, PermissionSystem
from master_agent.planner.planner import MissionPlan, Step
from master_agent.plugins.base import InvocationResult
from master_agent.plugins.filesystem_plugin import (
    COPY_FILE,
    CREATE_FOLDER,
    DELETE_FILE,
    DELETE_FOLDER,
    LIST_DIRECTORY,
    MOVE_FILE,
    READ_FILE,
    RENAME_FILE,
    SEARCH_FILES,
    WORKSPACE_BOOTSTRAP,
    FilesystemPlugin,
)
from master_agent.plugins.registry import PluginRegistry

WAKE_PHRASES = {"master agent"}

# Intentionally narrow — recognizes exactly "create a folder called X
# [on <location>]". Real NLP / the Intent Layer is out of scope for this
# brief; this stays a rule-based parser on purpose, not a hidden model call.
_CREATE_FOLDER_RE = re.compile(
    r"""^create\s+(?:a\s+)?folder\s+(?:called|named)\s+
        ["'“]?(?P<name>[^"'”.]+?)["'”]?
        (?:\s+(?:on|in)\s+(?:my\s+|the\s+)?(?P<location>[\w\s]+?))?
        \.?\s*$""",
    re.IGNORECASE | re.VERBOSE,
)

# Recognizes "create [a|an|a new|new] [<type>] project|application
# called|named X". The optional <type> group only captures when it's
# immediately followed by the literal "project"/"application" — e.g. in
# "create a project called X" there's no separate type word, so the
# regex engine backtracks past the optional group and "project" itself
# satisfies the mandatory noun, leaving type unset. Same rule-based-not-
# a-model-call philosophy as _CREATE_FOLDER_RE above.
_CREATE_PROJECT_RE = re.compile(
    r"""^create\s+(?:a\s+new\s+|a\s+|an\s+|new\s+)?
        (?:(?P<type>[A-Za-z][\w.+#-]*)\s+)?
        (?:project|application)\s+
        (?:called|named)\s+
        ["'“]?(?P<name>[^"'”.]+?)["'”]?
        \.?\s*$""",
    re.IGNORECASE | re.VERBOSE,
)


# Mission Brief 005: the eight new conversational shapes, one regex each.
# Every one of these anchors on a distinct leading verb (read/rename/
# copy/move/delete/list/search), so match order among them doesn't
# matter — unlike _CREATE_FOLDER_RE/_CREATE_PROJECT_RE above, which both
# start with "create" and must stay ordered accordingly. Non-greedy
# `\S+?`/`.+?` capture groups followed by an optional trailing `\.?\s*$`
# are what let "Read README.md" and "Read README.md." both resolve to the
# same path (verified by manual regex trace — see FILESYSTEM_CAPABILITIES.md
# §6, "why individual Actions" doesn't answer this, but the mechanism is
# the same non-greedy trick DELETE/COPY/MOVE below all reuse). Only the
# six phrasings the brief's conversation examples require are wired here
# (plus "move", added for symmetry with "copy") — file_exists/
# directory_exists/append_file are real, tested capabilities
# (test_read_actions.py / test_write_actions.py) with no conversational
# phrasing yet, which is fine: the toolbox is bigger than any one
# conversation needs to reach on day one (FILESYSTEM_CAPABILITIES.md §4).
_READ_FILE_RE = re.compile(r"^read\s+(?:the\s+file\s+)?(?P<path>\S+?)\.?\s*$", re.IGNORECASE)
_RENAME_FILE_RE = re.compile(r"^rename\s+(?P<path>\S+?)\s+to\s+(?P<new_name>\S+?)\.?\s*$", re.IGNORECASE)
_COPY_FILE_RE = re.compile(r"^copy\s+(?P<path>\S+?)\s+to\s+(?P<destination>.+?)\.?\s*$", re.IGNORECASE)
_MOVE_FILE_RE = re.compile(r"^move\s+(?P<path>\S+?)\s+to\s+(?P<destination>.+?)\.?\s*$", re.IGNORECASE)
# Deliberately no separate "delete a folder" wording: whether this is a
# file-delete or folder-delete is disambiguated after matching, by
# checking for a trailing " folder" keyword (_build_delete_intent below) —
# plain Python string logic, not a second regex, per "prefer simplicity
# over cleverness."
_DELETE_RE = re.compile(r"^delete\s+(?P<path>.+?)\.?\s*$", re.IGNORECASE)
_LIST_DIRECTORY_RE = re.compile(
    r"^list\s+(?:the\s+)?files\s+(?:inside|in|on)\s+(?:my\s+|the\s+)?(?P<location>[\w\s]+?)\.?\s*$",
    re.IGNORECASE,
)
_SEARCH_FILES_RE = re.compile(r"^search\s+for\s+(?P<pattern>\S+?)\.?\s*$", re.IGNORECASE)

# Mission Brief 004: recognizes the two memory-query phrasings from the
# brief's example conversations. Checked before ordinary intent parsing
# (see MasterAgentSession._handle_inner) so a memory question never
# starts a Mission and never gets mistaken for a pending approval answer.
_LAST_MISSION_RE = re.compile(r"^what\s+was\s+my\s+last\s+mission\??$", re.IGNORECASE)
_RECENT_MISSIONS_RE = re.compile(r"^show\s+(?:me\s+)?(?:my\s+)?recent\s+missions\.?$", re.IGNORECASE)


def _parse_memory_query(text: str) -> str | None:
    if _LAST_MISSION_RE.match(text):
        return "last"
    if _RECENT_MISSIONS_RE.match(text):
        return "recent"
    return None


class UnrecognizedInput(Exception):
    """Raised when the input doesn't match any command this brief supports."""


class InvalidProjectRequest(Exception):
    """Raised when text structurally matches a project-creation request
    (_CREATE_PROJECT_RE matched) but the extracted project name isn't
    usable — empty, or unsafe per
    executor/action.py's is_unsafe_relative_path(). Deliberately distinct
    from UnrecognizedInput: the human clearly asked to create a project,
    so the reply should explain what's wrong with the name they gave,
    not claim the whole request wasn't understood."""

    def __init__(self, reasons: list[str]) -> None:
        self.reasons = reasons
        super().__init__("; ".join(reasons))


@dataclass
class ParsedIntent:
    action: str
    folder_name: str
    location: str


@dataclass
class ParsedProjectIntent:
    action: str
    project_name: str
    project_type: str  # normalized template key, e.g. "python" or "generic"
    project_type_label: str  # display label, e.g. "Python", or "" for generic


@dataclass
class ParsedActionIntent:
    """Generic stand-in for every Mission Brief 005 capability — one
    dataclass instead of eight (ParsedReadIntent, ParsedRenameIntent, ...),
    because the only things that actually differ between "read a file" and
    "delete a folder" are the capability name, the payload shape, and a
    couple of display strings; the control flow around them (build a plan,
    maybe ask for approval, run it, record it) is identical. See the
    module docstring.

    `capability` is one of the filesystem_plugin capability-name constants
    (READ_FILE, RENAME_FILE, ...) — it becomes the plan's Step.capability
    directly. `warning` is "" for READ_ONLY capabilities (Read/List/Search
    never reach _approval_message, so it's never read for those, but
    leaving it empty rather than omitting the field keeps the dataclass
    uniform across all nine capabilities this represents).
    """

    capability: str
    payload: dict[str, Any]
    title: str  # e.g. 'Rename "notes.txt" to "notes_old.txt"' — used as the mission title and the approval header
    location: str  # display label, e.g. "Desktop" or "Downloads"
    warning: str  # approval-message consequence sentence; "" for read-only capabilities


# ---- project templates -----------------------------------------------------
# Each template function takes the project name and returns
# {"folders": [...], "files": [{"path": ..., "content": ...}]} — the exact
# shape WorkspaceBootstrapAction's payload expects (ARCHITECTURE.md §4.7).
# Deliberately simple, per the brief: no venv, no git init, no package
# installation — those are future missions, not this one.

def _python_project_template(name: str) -> dict[str, Any]:
    return {
        "folders": ["src", "tests", "docs", "config"],
        "files": [
            {"path": "README.md", "content": f"# {name}\n"},
            {"path": ".gitignore", "content": "__pycache__/\n*.pyc\n.venv/\n"},
            {"path": "requirements.txt", "content": ""},
            {
                "path": "main.py",
                "content": 'def main():\n    pass\n\n\nif __name__ == "__main__":\n    main()\n',
            },
        ],
    }


def _generic_project_template(name: str) -> dict[str, Any]:
    """The sensible default for an omitted or unrecognized project type —
    "unknown project type -> fall back to default template" from Mission
    Brief 003.1's Error Handling section."""
    return {
        "folders": ["src", "docs"],
        "files": [{"path": "README.md", "content": f"# {name}\n"}],
    }


# type key -> (display label, template function). Extending this dict is
# the whole cost of teaching Master Agent a new project type.
_PROJECT_TEMPLATES: dict[str, tuple[str, Callable[[str], dict[str, Any]]]] = {
    "python": ("Python", _python_project_template),
}


def _resolve_project_type(raw_type: str | None) -> tuple[str, str]:
    """Returns (type_key, display_label). Unknown or omitted types
    resolve to ("generic", "") — the generic template's key and an empty
    label, so callers building a mission title get "Create Project"
    rather than "Create  Project"."""
    key = (raw_type or "").strip().lower()
    if key in _PROJECT_TEMPLATES:
        return key, _PROJECT_TEMPLATES[key][0]
    return "generic", ""


def _template_for(project_type: str) -> Callable[[str], dict[str, Any]]:
    entry = _PROJECT_TEMPLATES.get(project_type)
    return entry[1] if entry else _generic_project_template


def _validate_project_name(name: str) -> list[str]:
    errors: list[str] = []
    if not name:
        errors.append("missing a project name")
    elif is_unsafe_relative_path(name):
        errors.append(f"unsafe project name '{name}': must be relative, no '..' segments or slashes")
    return errors


def _build_folder_intent(match: re.Match[str]) -> ParsedIntent:
    location = (match.group("location") or "Desktop").strip()
    return ParsedIntent(action=CREATE_FOLDER, folder_name=match.group("name").strip(), location=location)


def _build_project_intent(match: re.Match[str]) -> ParsedProjectIntent:
    name = match.group("name").strip()
    errors = _validate_project_name(name)
    if errors:
        raise InvalidProjectRequest(errors)
    project_type, project_type_label = _resolve_project_type(match.group("type"))
    return ParsedProjectIntent(
        action=WORKSPACE_BOOTSTRAP,
        project_name=name,
        project_type=project_type,
        project_type_label=project_type_label,
    )


def _strip_trailing_folder_word(text: str) -> str:
    """"backup folder" -> "backup"; "backup" -> "backup" (unchanged).
    Plain string post-processing rather than a second regex — used to
    disambiguate delete-file-vs-delete-folder and to resolve copy/move
    destinations and list locations phrased with a trailing "folder"
    word. See FILESYSTEM_CAPABILITIES.md's "prefer simplicity over
    cleverness."."""
    if text.lower().endswith(" folder"):
        return text[: -len(" folder")].strip()
    return text


def _build_read_intent(match: re.Match[str]) -> ParsedActionIntent:
    path = match.group("path").strip()
    return ParsedActionIntent(
        capability=READ_FILE,
        payload={"path": path, "location": "desktop"},
        title=f'Read "{path}"',
        location="Desktop",
        warning="",
    )


def _build_rename_intent(match: re.Match[str]) -> ParsedActionIntent:
    path = match.group("path").strip()
    new_name = match.group("new_name").strip()
    return ParsedActionIntent(
        capability=RENAME_FILE,
        payload={"path": path, "new_name": new_name, "location": "desktop"},
        title=f'Rename "{path}" to "{new_name}"',
        location="Desktop",
        warning="This action will modify your filesystem.",
    )


def _build_copy_intent(match: re.Match[str]) -> ParsedActionIntent:
    path = match.group("path").strip()
    destination = _strip_trailing_folder_word(match.group("destination").strip())
    return ParsedActionIntent(
        capability=COPY_FILE,
        payload={"path": path, "destination": destination, "location": "desktop"},
        title=f'Copy "{path}" to "{destination}"',
        location="Desktop",
        warning="This action will modify your filesystem.",
    )


def _build_move_intent(match: re.Match[str]) -> ParsedActionIntent:
    path = match.group("path").strip()
    destination = _strip_trailing_folder_word(match.group("destination").strip())
    return ParsedActionIntent(
        capability=MOVE_FILE,
        payload={"path": path, "destination": destination, "location": "desktop"},
        title=f'Move "{path}" to "{destination}"',
        location="Desktop",
        warning="This action will modify your filesystem.",
    )


def _build_delete_intent(match: re.Match[str]) -> ParsedActionIntent:
    raw = match.group("path").strip()
    if raw.lower().endswith(" folder"):
        path = _strip_trailing_folder_word(raw)
        return ParsedActionIntent(
            capability=DELETE_FOLDER,
            payload={"path": path, "location": "desktop"},
            title=f'Delete Folder "{path}"',
            location="Desktop",
            warning="This will permanently delete this folder and everything inside it. This cannot be undone.",
        )
    return ParsedActionIntent(
        capability=DELETE_FILE,
        payload={"path": raw, "location": "desktop"},
        title=f'Delete File "{raw}"',
        location="Desktop",
        warning="This will permanently delete this file. This cannot be undone.",
    )


# Free-text location word -> (location key, display label). Anything not
# in this map still gets a location key (lower-cased, "folder" stripped) —
# an unrecognized location fails validate()'s "unknown location" check at
# execution time with a clear error, rather than failing to parse at all.
_KNOWN_LOCATIONS = {"desktop": "Desktop", "downloads": "Downloads", "documents": "Documents"}


def _build_list_intent(match: re.Match[str]) -> ParsedActionIntent:
    raw_location = _strip_trailing_folder_word(match.group("location").strip())
    location_key = raw_location.lower()
    label = _KNOWN_LOCATIONS.get(location_key, raw_location.title())
    return ParsedActionIntent(
        capability=LIST_DIRECTORY,
        payload={"path": ".", "location": location_key},
        title=f'List "{label}"',
        location=label,
        warning="",
    )


def _build_search_intent(match: re.Match[str]) -> ParsedActionIntent:
    pattern = match.group("pattern").strip()
    return ParsedActionIntent(
        capability=SEARCH_FILES,
        payload={"pattern": pattern, "location": "desktop"},
        title=f'Search for "{pattern}"',
        location="Desktop",
        warning="",
    )


# Table-driven dispatch: intent parsing is "try each pattern in order,
# build from the first match" rather than a growing if/elif chain — the
# same "avoid long if/else chains, design for many" principle
# FilesystemPlugin's own registration follows (FILESYSTEM_CAPABILITIES.md
# §4). _CREATE_FOLDER_RE/_CREATE_PROJECT_RE stay first and in their
# existing relative order (both start with "create", so order between
# just those two matters for backtracking reasons that predate this
# table); every entry after them anchors on a distinct leading verb, so
# their relative order doesn't matter.
_INTENT_PATTERNS: list[
    tuple[re.Pattern[str], Callable[[re.Match[str]], ParsedIntent | ParsedProjectIntent | ParsedActionIntent]]
] = [
    (_CREATE_FOLDER_RE, _build_folder_intent),
    (_CREATE_PROJECT_RE, _build_project_intent),
    (_READ_FILE_RE, _build_read_intent),
    (_RENAME_FILE_RE, _build_rename_intent),
    (_COPY_FILE_RE, _build_copy_intent),
    (_MOVE_FILE_RE, _build_move_intent),
    (_DELETE_RE, _build_delete_intent),
    (_LIST_DIRECTORY_RE, _build_list_intent),
    (_SEARCH_FILES_RE, _build_search_intent),
]


def parse_intent(text: str) -> ParsedIntent | ParsedProjectIntent | ParsedActionIntent:
    text = text.strip()

    for regex, build in _INTENT_PATTERNS:
        match = regex.match(text)
        if match:
            return build(match)

    raise UnrecognizedInput(text)


def build_plan(intent: ParsedIntent | ParsedProjectIntent | ParsedActionIntent) -> MissionPlan:
    """Stand-in for the real Planner (out of scope) — see module docstring."""
    if isinstance(intent, ParsedProjectIntent):
        template = _template_for(intent.project_type)(intent.project_name)
        step = Step(
            step_id="workspace-bootstrap-1",
            capability=WORKSPACE_BOOTSTRAP,
            payload={
                "name": intent.project_name,
                "location": "desktop",
                "folders": template["folders"],
                "files": template["files"],
            },
        )
        return MissionPlan(steps=[step])

    if isinstance(intent, ParsedActionIntent):
        # One step, whatever the capability — the plan shape never has to
        # know which of the nine ParsedActionIntent-backed capabilities
        # this is, same as it never had to know workspace_bootstrap was a
        # composite above.
        step = Step(step_id=f"{intent.capability}-1", capability=intent.capability, payload=intent.payload)
        return MissionPlan(steps=[step])

    step = Step(
        step_id="create-folder-1",
        capability=CREATE_FOLDER,
        payload={"name": intent.folder_name, "location": intent.location},
    )
    return MissionPlan(steps=[step])


def _mission_title(intent: ParsedProjectIntent) -> str:
    return f"Create {intent.project_type_label} Project" if intent.project_type_label else "Create Project"


# ---- Mission Brief 004: Memory --------------------------------------------
# Everything below builds the MissionRecord persisted at every terminal
# mission state, and renders the two conversational memory queries. See
# MEMORY_ARCHITECTURE.md §7 and §9.

def _record_title(intent: ParsedIntent | ParsedProjectIntent | ParsedActionIntent) -> str:
    """One consistent title format, used for both the single-mission and
    the list query — see MEMORY_ARCHITECTURE.md §9 for why this doesn't
    literally reproduce the brief's two (mutually inconsistent) example
    title strings."""
    if isinstance(intent, ParsedProjectIntent):
        return f'{_mission_title(intent)} "{intent.project_name}"'
    if isinstance(intent, ParsedActionIntent):
        return intent.title
    return f'Create Folder "{intent.folder_name}"'


# capability name -> artifact type for the single-string-output
# capabilities (rename/delete produce a bare path string, same output
# shape create_folder already had — see _extract_artifacts below for why
# a bare string can no longer default to "folder" now that rename/delete
# also return one).
_STRING_OUTPUT_ARTIFACT_TYPES = {
    RENAME_FILE: "file",
    DELETE_FILE: "deleted_file",
    DELETE_FOLDER: "deleted_folder",
}
# Capabilities that read or inspect but never create, modify, or remove
# anything — nothing to record as an artifact.
_NO_ARTIFACT_CAPABILITIES = {READ_FILE, LIST_DIRECTORY, SEARCH_FILES}


def _extract_artifacts(
    intent: ParsedIntent | ParsedProjectIntent | ParsedActionIntent,
    result: InvocationResult | None,
) -> list[dict[str, str]]:
    """Generic `{"type": ..., "path": ...}` artifact list from a step's
    result — MissionRecord.artifacts, not a folders/files-specific shape,
    so a future capability whose output doesn't look like "folders and
    files" (a git commit, a shell command's stdout, ...) can contribute
    its own artifact shape without a Memory schema change (see
    MEMORY_ARCHITECTURE.md §6b). This function still has to know each
    capability's output shape to interpret it — that part is unavoidable
    while cli.py stands in for the real Planner/Reporter.

    Mission Brief 005 note: a bare string output used to mean "a folder
    was created" unconditionally (only create_folder returned one). Now
    rename_file/delete_file/delete_folder also return a bare path string,
    so the string case is only safe to interpret once `intent` says which
    capability produced it — hence the two lookup tables above, and why
    this now takes `intent` as well as `result`."""
    if result is None or not result.success:
        return []
    output = result.output

    if isinstance(intent, ParsedActionIntent):
        if intent.capability in _NO_ARTIFACT_CAPABILITIES:
            return []
        if intent.capability in _STRING_OUTPUT_ARTIFACT_TYPES and isinstance(output, str):
            return [{"type": _STRING_OUTPUT_ARTIFACT_TYPES[intent.capability], "path": output}]
        if intent.capability in {COPY_FILE, MOVE_FILE} and isinstance(output, dict):
            destination = output.get("destination")
            return [{"type": "file", "path": destination}] if destination else []
        return []

    if isinstance(output, dict):
        artifacts = [{"type": "folder", "path": p} for p in output.get("created_folders", [])]
        artifacts += [{"type": "file", "path": p} for p in output.get("written_files", [])]
        return artifacts
    if isinstance(output, str):
        return [{"type": "folder", "path": output}]
    return []


def _build_mission_record(
    mission: Mission,
    intent: ParsedIntent | ParsedProjectIntent | ParsedActionIntent,
    plan: MissionPlan,
    step_result: StepResult | None,
    approval_status: str,
) -> MissionRecord:
    result = step_result.result if step_result else None
    errors = [result.error] if (result is not None and not result.success and result.error) else []
    execution_plan = [
        {"step_id": step.step_id, "capability": step.capability, "payload": step.payload}
        for step in plan.steps
    ]
    return MissionRecord(
        mission_id=mission.mission_id,
        title=_record_title(intent),
        intent_summary=mission.intent_summary,
        status=mission.status.value,
        approval_status=approval_status,
        created_at=mission.created_at,
        completed_at=mission.updated_at,
        execution_plan=execution_plan,
        execution_result=result.output if result is not None else None,
        execution_time_seconds=result.execution_time_seconds if result is not None else 0.0,
        artifacts=_extract_artifacts(intent, result),
        errors=errors,
        outcome=mission.outcome,
    )


_STATUS_SENTENCES = {
    "completed": "Completed successfully.",
    "failed": "Failed.",
    "cancelled": "Cancelled.",
}
_STATUS_WORDS = {
    "completed": "Success",
    "failed": "Failed",
    "cancelled": "Cancelled",
}


def _status_sentence(status: str) -> str:
    return _STATUS_SENTENCES.get(status, f"{status.capitalize()}.")


def _status_word(status: str) -> str:
    return _STATUS_WORDS.get(status, status.capitalize())


def _format_relative_timestamp(at: datetime, *, now: datetime | None = None) -> str:
    """"Today at 3:05 PM" / "Yesterday at 8:14 PM" / a full date further
    back. Both `at` and `now` are UTC (every datetime Mission produces is
    UTC) — this is UTC-relative, not local-time-relative; see
    MEMORY_ARCHITECTURE.md §9 and §11 for why that's a known
    simplification rather than a hidden one."""
    now = now or datetime.now(timezone.utc)
    delta_days = (now.date() - at.date()).days
    time_part = at.strftime("%I:%M %p").lstrip("0") or "12:00 AM"
    if delta_days == 0:
        day_part = "Today"
    elif delta_days == 1:
        day_part = "Yesterday"
    else:
        day_part = at.strftime("%B %d, %Y")
    return f"{day_part} at {time_part}"


def _default_memory_db_path() -> Path:
    """Local-first, per-machine default — same Path.home()-based
    convention FilesystemPlugin already uses for its Desktop location.
    See MEMORY_ARCHITECTURE.md §10 (Privacy)."""
    return Path.home() / ".master_agent" / "memory.db"


# ---- Mission Brief 005: completion messages for ParsedActionIntent --------
# One small builder per capability whose output shape needs its own
# sentence, keyed by capability name — table-driven for the same reason
# _INTENT_PATTERNS is, rather than an if/elif chain in _finish(). A
# capability with no entry here (currently none of the nine reachable
# from conversation, but file_exists/directory_exists/append_file would
# fall through to this if a future intent reached them) gets
# `_default_action_complete`'s generic sentence — never a KeyError.

def _read_file_complete(intent: ParsedActionIntent, result: InvocationResult) -> str:
    content = (result.output or {}).get("content", "")
    return f'Done.\nRead "{intent.payload["path"]}".\n\n{content}'


def _list_directory_complete(intent: ParsedActionIntent, result: InvocationResult) -> str:
    output = result.output or {}
    folders = output.get("folders", [])
    files = output.get("files", [])
    folders_block = "Folders:\n" + ("\n".join(folders) if folders else "(none)")
    files_block = "Files:\n" + ("\n".join(files) if files else "(none)")
    return f"Done.\n{intent.title}.\n\n{folders_block}\n\n{files_block}"


def _search_files_complete(intent: ParsedActionIntent, result: InvocationResult) -> str:
    output = result.output or {}
    matches = output.get("matches", [])
    header = f'Done.\nFound {len(matches)} file(s) matching "{intent.payload["pattern"]}"'
    if output.get("truncated"):
        header += " (showing the first 200)"
    body = "\n".join(matches) if matches else "(no matches)"
    return f"{header}.\n\n{body}"


def _rename_file_complete(intent: ParsedActionIntent, result: InvocationResult) -> str:
    return f"Done.\n{intent.title}.\n(New path: {result.output})"


def _copy_file_complete(intent: ParsedActionIntent, result: InvocationResult) -> str:
    destination = (result.output or {}).get("destination", "")
    return f"Done.\n{intent.title}.\n(Copied to: {destination})"


def _move_file_complete(intent: ParsedActionIntent, result: InvocationResult) -> str:
    destination = (result.output or {}).get("destination", "")
    return f"Done.\n{intent.title}.\n(Moved to: {destination})"


def _delete_complete(intent: ParsedActionIntent, result: InvocationResult) -> str:
    return f"Done.\n{intent.title}."


def _default_action_complete(intent: ParsedActionIntent, result: InvocationResult) -> str:
    return f"Done.\n{intent.title}.\nMission completed successfully."


_ACTION_COMPLETION_BUILDERS: dict[str, Callable[[ParsedActionIntent, InvocationResult], str]] = {
    READ_FILE: _read_file_complete,
    LIST_DIRECTORY: _list_directory_complete,
    SEARCH_FILES: _search_files_complete,
    RENAME_FILE: _rename_file_complete,
    COPY_FILE: _copy_file_complete,
    MOVE_FILE: _move_file_complete,
    DELETE_FILE: _delete_complete,
    DELETE_FOLDER: _delete_complete,
}


class MasterAgentSession:
    """Wires the real modules together for one conversation.

    Everything this class depends on is passed in (registry, permissions,
    orchestrator) rather than constructed internally — the dependency-
    injection seam that lets tests swap a sandboxed FilesystemPlugin in
    without this class, or the real filesystem, ever knowing the
    difference.
    """

    def __init__(
        self,
        registry: PluginRegistry,
        permissions: PermissionSystem,
        orchestrator: Orchestrator,
        memory: Memory,
    ) -> None:
        self._registry = registry
        self._permissions = permissions
        self._orchestrator = orchestrator
        self.memory = memory
        self._awake = False
        self._pending: (
            tuple[Mission, MissionPlan, ParsedIntent | ParsedProjectIntent | ParsedActionIntent] | None
        ) = None
        self.last_mission: Mission | None = None

    def handle(self, text: str) -> str:
        # Layer 1 (Conversation Memory): every turn is recorded here,
        # automatically — no caller of handle() needs to know Memory
        # exists for this to happen. See MEMORY_ARCHITECTURE.md §4a.
        text = text.strip()
        self.memory.record_turn("user", text)
        reply = self._handle_inner(text)
        self.memory.record_turn("system", reply)
        return reply

    def _handle_inner(self, text: str) -> str:
        if not self._awake:
            self._awake = True
            return "Hello! I'm awake.\nWhat would you like me to do?"

        if self._pending is not None:
            return self._handle_approval_response(text)

        memory_query = _parse_memory_query(text)
        if memory_query is not None:
            return self._answer_memory_query(memory_query)

        try:
            intent = parse_intent(text)
        except InvalidProjectRequest as exc:
            # Structurally recognized as a project-creation request, but
            # the name itself can't be used — explain why rather than
            # claiming the whole request wasn't understood. No Mission is
            # created, same invariant UnrecognizedInput already keeps.
            return (
                f"I can't create that project: {'; '.join(exc.reasons)}.\n"
                'Try something like: "Create a Python project called Demo."'
            )
        except UnrecognizedInput:
            return (
                "I don't understand that yet. Try:\n"
                '"Create a folder called <name> on my Desktop."\n'
                '"Create a Python project called <name>."\n'
                '"Read <file>." / "List files inside Downloads." / "Search for *.pdf."\n'
                '"Rename <file> to <name>." / "Copy <file> to <folder>." / "Delete <file or folder>."\n'
                '"What was my last mission?"'
            )

        mission = Mission(intent_summary=text)
        self.last_mission = mission
        plan = build_plan(intent)
        mission.plan = plan
        mission.transition(MissionStatus.PLANNED)

        return self._run(mission, plan, intent, approval_status="not_required")

    def _answer_memory_query(self, query: str) -> str:
        """Mission Brief 004's two conversational queries — reads Memory,
        never Mission/Executor/Orchestrator. See MEMORY_ARCHITECTURE.md
        §9."""
        if query == "last":
            record = self.memory.last_mission()
            if record is None:
                return "You haven't run any missions yet."
            return (
                "Your last mission was:\n"
                f"{record.title}\n"
                f"{_status_sentence(record.status)}\n"
                f"{_format_relative_timestamp(record.completed_at)}."
            )

        records = self.memory.recent_missions(limit=10)
        if not records:
            return "You haven't run any missions yet."
        lines = [f"{i}.\n{r.title}\n{_status_word(r.status)}" for i, r in enumerate(records, start=1)]
        return "\n".join(lines)

    def _run(
        self,
        mission: Mission,
        plan: MissionPlan,
        intent: ParsedIntent | ParsedProjectIntent | ParsedActionIntent,
        approval_status: str,
    ) -> str:
        # Entering execution is itself a state, whether or not the
        # Permission System ends up blocking it — "attempting to execute
        # surfaced a need for approval" is a truer read of what happened
        # than "we never started." Guarded so a second _run() call (after
        # approval) doesn't try to re-enter EXECUTING from EXECUTING.
        if mission.status == MissionStatus.PLANNED:
            mission.transition(MissionStatus.EXECUTING)

        results = self._orchestrator.execute_plan(plan)
        step_result = results[0] if results else None

        if step_result is not None and step_result.blocked_on_approval:
            mission.transition(MissionStatus.AWAITING_APPROVAL)
            self._pending = (mission, plan, intent)
            return self._approval_message(intent)

        return self._finish(mission, plan, step_result, intent, approval_status)

    def _approval_message(self, intent: ParsedIntent | ParsedProjectIntent | ParsedActionIntent) -> str:
        if isinstance(intent, ParsedProjectIntent):
            return (
                "I understood your request.\n\n"
                f"Mission:\n{_mission_title(intent)}\n\n"
                f"Project:\n{intent.project_name}\n\n"
                "Plan:\n"
                "• Create workspace\n"
                "• Create folders\n"
                "• Create starter files\n\n"
                "This will modify your filesystem.\n"
                "Approve? (Yes/No)"
            )
        if isinstance(intent, ParsedActionIntent):
            # One format for every write/modify/delete capability —
            # Read/List/Search are READ_ONLY and never reach this method
            # at all (PermissionSystem.check() short-circuits for that
            # tier, so the Orchestrator never sets blocked_on_approval for
            # them; see the module docstring). `intent.warning` is what
            # varies: a plain "this will modify your filesystem" for
            # rename/copy/move, versus the sharper "cannot be undone" for
            # delete_file/delete_folder (FILESYSTEM_CAPABILITIES.md §5).
            return (
                "I understood your request.\n\n"
                f"Action:\n{intent.title}\n\n"
                f"Location:\n{intent.location}\n\n"
                f"{intent.warning}\n"
                "Approve? (Yes/No)"
            )
        return (
            "I understood your request.\n\n"
            f'Action:\nCreate folder "{intent.folder_name}"\n\n'
            f"Location:\n{intent.location}\n\n"
            "This action will modify your filesystem.\n"
            "Approve? (Yes/No)"
        )

    def _handle_approval_response(self, text: str) -> str:
        mission, plan, intent = self._pending
        answer = text.strip().lower()

        if answer not in {"yes", "y", "no", "n"}:
            return "Please answer Yes or No."

        self._pending = None

        if answer in {"no", "n"}:
            mission.transition(MissionStatus.CANCELLED)
            self._remember(mission, intent, plan, None, approval_status="denied")
            return "Okay, cancelled. Nothing was changed."

        # Fully generic — resolves whichever capability this mission's
        # single step names (create_folder or workspace_bootstrap) via
        # the same registry lookup, then grants exactly the ONE approval
        # the Orchestrator's own gate needs. Everything downstream of that
        # single grant — including a composite action relaying its OWN
        # grants to its sub-actions (docs/adr/0006-composite-action-relay.md)
        # — happens without this method knowing or caring. That's the
        # point of Mission Brief 003's design: this code didn't change at
        # all to support project creation.
        step = plan.steps[0]
        plugin = self._registry.find_for_capability(step.capability)[0]
        self._permissions.grant(plugin.manifest.name, step.capability, GrantScope.ONCE)
        mission.transition(MissionStatus.EXECUTING)
        return self._run(mission, plan, intent, approval_status="approved")

    def _remember(
        self,
        mission: Mission,
        intent: ParsedIntent | ParsedProjectIntent | ParsedActionIntent,
        plan: MissionPlan,
        step_result: StepResult | None,
        approval_status: str,
    ) -> None:
        """The only place a mission's terminal state turns into a
        MissionRecord and reaches Memory — called from every terminal
        transition (_finish's COMPLETED/FAILED branches, and the
        CANCELLED branch above). No manual save call exists anywhere in
        main() or the CLI loop; this is what makes persistence automatic.
        See MEMORY_ARCHITECTURE.md §7."""
        record = _build_mission_record(mission, intent, plan, step_result, approval_status)
        self.memory.persist_mission(record)

    def _finish(
        self,
        mission: Mission,
        plan: MissionPlan,
        step_result: StepResult | None,
        intent: ParsedIntent | ParsedProjectIntent | ParsedActionIntent,
        approval_status: str,
    ) -> str:
        result = step_result.result if step_result else None
        if result is None or not result.success:
            mission.transition(MissionStatus.FAILED)
            error = result.error if result else "no plugin available for that action"
            mission.outcome = {"error": error}
            self._remember(mission, intent, plan, step_result, approval_status)
            return f"Something went wrong: {error}"

        mission.transition(MissionStatus.VERIFYING)
        mission.transition(MissionStatus.COMPLETED)

        if isinstance(intent, ParsedProjectIntent):
            mission.outcome = {"created_workspace": result.output}
            self._remember(mission, intent, plan, step_result, approval_status)
            return self._project_completion_message(intent, result)

        if isinstance(intent, ParsedActionIntent):
            # Uniform outcome shape across all nine capabilities — same
            # reasoning as the rest of Mission Brief 005's cli.py changes:
            # the *meaning* of "output" is capability-specific, but the
            # control flow storing it isn't, so it doesn't need a branch
            # per capability here (only the completion message, which
            # genuinely differs, gets one — via _ACTION_COMPLETION_BUILDERS).
            mission.outcome = {"capability": intent.capability, "output": result.output}
            self._remember(mission, intent, plan, step_result, approval_status)
            builder = _ACTION_COMPLETION_BUILDERS.get(intent.capability, _default_action_complete)
            return builder(intent, result)

        mission.outcome = {"created_path": result.output}
        self._remember(mission, intent, plan, step_result, approval_status)
        return f"Done.\nMission completed successfully.\n(Created: {result.output})"

    def _project_completion_message(self, intent: ParsedProjectIntent, result) -> str:
        output = result.output or {}
        folders_created = len(output.get("created_folders", []))
        files_created = len(output.get("written_files", []))
        type_prefix = f"{intent.project_type_label} " if intent.project_type_label else ""
        return (
            "Done.\n"
            f'{type_prefix}project "{intent.project_name}" created successfully.\n\n'
            f"Execution time: {result.execution_time_seconds:.3f} seconds\n"
            f"Folders created: {folders_created}\n"
            f"Files created: {files_created}\n\n"
            "Mission completed successfully."
        )


def build_default_session() -> MasterAgentSession:
    """Production wiring: real Desktop, real permission system, one plugin
    registered, real (local, file-backed) Memory. This is the only
    function in the module that touches the real filesystem's Desktop
    path and the real memory database path — everything else takes them
    as parameters, which is what keeps this testable.
    """
    permissions = PermissionSystem()
    executor = LocalExecutor(permissions)
    registry = PluginRegistry()
    registry.register(FilesystemPlugin(executor))
    orchestrator = Orchestrator(registry, permissions)
    memory = Memory(SQLiteMemoryStore(str(_default_memory_db_path())))
    return MasterAgentSession(registry, permissions, orchestrator, memory)


def main() -> None:
    session = build_default_session()
    print("Master Agent — try: \"Create a folder called Demo on my Desktop.\" or")
    print('"Create a Python project called Demo." or "Read README.md" or "List files')
    print('inside Downloads" or "Search for *.pdf" or "Rename notes.txt to notes_old.txt"')
    print('or "Copy config.json to backup folder" or "Delete temp folder" or')
    print("\"What was my last mission?\" Type 'exit' to quit.\n")
    try:
        while True:
            text = input("> ")
            if text.strip().lower() in {"exit", "quit"}:
                print("Goodbye.")
                break
            print(session.handle(text))
            print()
    except (EOFError, KeyboardInterrupt):
        print("\nGoodbye.")


if __name__ == "__main__":
    main()
