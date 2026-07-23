"""Mission Brief 001 — The First Conversation. Extended in Mission Brief
003.1 to reach the Workspace Bootstrap capability from Mission Brief 003.

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
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable

from master_agent.executor.action import is_unsafe_relative_path
from master_agent.executor.executor import LocalExecutor
from master_agent.mission_manager.mission import Mission, MissionStatus
from master_agent.orchestrator.orchestrator import Orchestrator, StepResult
from master_agent.permissions.permission_system import GrantScope, PermissionSystem
from master_agent.planner.planner import MissionPlan, Step
from master_agent.plugins.filesystem_plugin import CREATE_FOLDER, WORKSPACE_BOOTSTRAP, FilesystemPlugin
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


def parse_intent(text: str) -> ParsedIntent | ParsedProjectIntent:
    text = text.strip()

    folder_match = _CREATE_FOLDER_RE.match(text)
    if folder_match:
        location = (folder_match.group("location") or "Desktop").strip()
        return ParsedIntent(
            action=CREATE_FOLDER,
            folder_name=folder_match.group("name").strip(),
            location=location,
        )

    project_match = _CREATE_PROJECT_RE.match(text)
    if project_match:
        name = project_match.group("name").strip()
        errors = _validate_project_name(name)
        if errors:
            raise InvalidProjectRequest(errors)
        project_type, project_type_label = _resolve_project_type(project_match.group("type"))
        return ParsedProjectIntent(
            action=WORKSPACE_BOOTSTRAP,
            project_name=name,
            project_type=project_type,
            project_type_label=project_type_label,
        )

    raise UnrecognizedInput(text)


def build_plan(intent: ParsedIntent | ParsedProjectIntent) -> MissionPlan:
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

    step = Step(
        step_id="create-folder-1",
        capability=CREATE_FOLDER,
        payload={"name": intent.folder_name, "location": intent.location},
    )
    return MissionPlan(steps=[step])


def _mission_title(intent: ParsedProjectIntent) -> str:
    return f"Create {intent.project_type_label} Project" if intent.project_type_label else "Create Project"


class MasterAgentSession:
    """Wires the real modules together for one conversation.

    Everything this class depends on is passed in (registry, permissions,
    orchestrator) rather than constructed internally — the dependency-
    injection seam that lets tests swap a sandboxed FilesystemPlugin in
    without this class, or the real filesystem, ever knowing the
    difference.
    """

    def __init__(self, registry: PluginRegistry, permissions: PermissionSystem, orchestrator: Orchestrator) -> None:
        self._registry = registry
        self._permissions = permissions
        self._orchestrator = orchestrator
        self._awake = False
        self._pending: tuple[Mission, MissionPlan, ParsedIntent | ParsedProjectIntent] | None = None
        self.last_mission: Mission | None = None

    def handle(self, text: str) -> str:
        text = text.strip()

        if not self._awake:
            self._awake = True
            return "Hello! I'm awake.\nWhat would you like me to do?"

        if self._pending is not None:
            return self._handle_approval_response(text)

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
                '"Create a Python project called <name>."'
            )

        mission = Mission(intent_summary=text)
        self.last_mission = mission
        plan = build_plan(intent)
        mission.plan = plan
        mission.transition(MissionStatus.PLANNED)

        return self._run(mission, plan, intent)

    def _run(self, mission: Mission, plan: MissionPlan, intent: ParsedIntent | ParsedProjectIntent) -> str:
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

        return self._finish(mission, step_result, intent)

    def _approval_message(self, intent: ParsedIntent | ParsedProjectIntent) -> str:
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
        return self._run(mission, plan, intent)

    def _finish(
        self, mission: Mission, step_result: StepResult | None, intent: ParsedIntent | ParsedProjectIntent
    ) -> str:
        result = step_result.result if step_result else None
        if result is None or not result.success:
            mission.transition(MissionStatus.FAILED)
            error = result.error if result else "no plugin available for that action"
            mission.outcome = {"error": error}
            return f"Something went wrong: {error}"

        mission.transition(MissionStatus.VERIFYING)
        mission.transition(MissionStatus.COMPLETED)

        if isinstance(intent, ParsedProjectIntent):
            mission.outcome = {"created_workspace": result.output}
            return self._project_completion_message(intent, result)

        mission.outcome = {"created_path": result.output}
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
    registered. This is the only function in the module that touches the
    real filesystem's Desktop path — everything else takes it as a
    parameter, which is what keeps this testable.
    """
    permissions = PermissionSystem()
    executor = LocalExecutor(permissions)
    registry = PluginRegistry()
    registry.register(FilesystemPlugin(executor))
    orchestrator = Orchestrator(registry, permissions)
    return MasterAgentSession(registry, permissions, orchestrator)


def main() -> None:
    session = build_default_session()
    print("Master Agent — try: \"Create a folder called Demo on my Desktop.\" or")
    print('"Create a Python project called Demo." Type \'exit\' to quit.\n')
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
