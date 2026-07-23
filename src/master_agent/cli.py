"""Mission Brief 001 — The First Conversation.

The smallest possible end-to-end slice through the real architecture:
text in, one real mission out. Deliberately does NOT touch the Planner,
Mission Manager, Model Router, Memory, or either model provider — those
stay out of scope for this brief. What's real here: rule-based intent
parsing for exactly one command, the actual PermissionSystem gate, the
actual Orchestrator + PluginRegistry, and a real filesystem write via
FilesystemPlugin.

The Step/MissionPlan shapes used below are the same ones the real Planner
(planner/planner.py) will eventually produce — this module hand-builds a
one-step plan instead of calling a model, but nothing downstream
(Orchestrator, plugins, Permission System) needs to change when a real
Planner replaces `build_plan`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from master_agent.mission_manager.mission import Mission, MissionStatus
from master_agent.orchestrator.orchestrator import Orchestrator, StepResult
from master_agent.permissions.permission_system import GrantScope, PermissionSystem
from master_agent.planner.planner import MissionPlan, Step
from master_agent.plugins.filesystem_plugin import CREATE_FOLDER, FilesystemPlugin
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


class UnrecognizedInput(Exception):
    """Raised when the input doesn't match any command this brief supports."""


@dataclass
class ParsedIntent:
    action: str
    folder_name: str
    location: str


def parse_intent(text: str) -> ParsedIntent:
    match = _CREATE_FOLDER_RE.match(text.strip())
    if not match:
        raise UnrecognizedInput(text)
    location = (match.group("location") or "Desktop").strip()
    return ParsedIntent(action=CREATE_FOLDER, folder_name=match.group("name").strip(), location=location)


def build_plan(intent: ParsedIntent) -> MissionPlan:
    """Stand-in for the real Planner (out of scope for this brief)."""
    step = Step(
        step_id="create-folder-1",
        capability=CREATE_FOLDER,
        payload={"name": intent.folder_name, "location": intent.location},
    )
    return MissionPlan(steps=[step])


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
        self._pending: tuple[Mission, MissionPlan, ParsedIntent] | None = None
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
        except UnrecognizedInput:
            return 'I don\'t understand that yet. Try: "Create a folder called <name> on my Desktop."'

        mission = Mission(intent_summary=text)
        self.last_mission = mission
        plan = build_plan(intent)
        mission.plan = plan
        mission.transition(MissionStatus.PLANNED)

        return self._run(mission, plan, intent)

    def _run(self, mission: Mission, plan: MissionPlan, intent: ParsedIntent) -> str:
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
            return (
                "I understood your request.\n\n"
                f'Action:\nCreate folder "{intent.folder_name}"\n\n'
                f"Location:\n{intent.location}\n\n"
                "This action will modify your filesystem.\n"
                "Approve? (Yes/No)"
            )

        return self._finish(mission, step_result)

    def _handle_approval_response(self, text: str) -> str:
        mission, plan, intent = self._pending
        answer = text.strip().lower()

        if answer not in {"yes", "y", "no", "n"}:
            return "Please answer Yes or No."

        self._pending = None

        if answer in {"no", "n"}:
            mission.transition(MissionStatus.CANCELLED)
            return "Okay, cancelled. Nothing was changed."

        step = plan.steps[0]
        plugin = self._registry.find_for_capability(step.capability)[0]
        self._permissions.grant(plugin.manifest.name, step.capability, GrantScope.ONCE)
        mission.transition(MissionStatus.EXECUTING)
        return self._run(mission, plan, intent)

    def _finish(self, mission: Mission, step_result: StepResult | None) -> str:
        result = step_result.result if step_result else None
        if result is None or not result.success:
            mission.transition(MissionStatus.FAILED)
            error = result.error if result else "no plugin available for that action"
            mission.outcome = {"error": error}
            return f"Something went wrong: {error}"

        mission.transition(MissionStatus.VERIFYING)
        mission.transition(MissionStatus.COMPLETED)
        mission.outcome = {"created_path": result.output}
        return f"Done.\nMission completed successfully.\n(Created: {result.output})"


def build_default_session() -> MasterAgentSession:
    """Production wiring: real Desktop, real permission system, one plugin
    registered. This is the only function in the module that touches the
    real filesystem's Desktop path — everything else takes it as a
    parameter, which is what keeps this testable.
    """
    registry = PluginRegistry()
    registry.register(FilesystemPlugin())
    permissions = PermissionSystem()
    orchestrator = Orchestrator(registry, permissions)
    return MasterAgentSession(registry, permissions, orchestrator)


def main() -> None:
    session = build_default_session()
    print("Master Agent — Mission Brief 001 demo. Type 'exit' to quit.\n")
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
