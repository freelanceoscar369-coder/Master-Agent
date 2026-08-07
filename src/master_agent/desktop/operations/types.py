"""Elite Desktop Executive — the shape of operational knowledge.

C25's own distinction, stated once so every type below can be read against
it: *"Current Executive answers **What exists?** Elite Executive answers
**How do I operate it?**"* Every dataclass here is the second answer, never
the first — nothing in this file reads a machine, and nothing in it is
executable.

## Every field is authored knowledge, not a measurement

`catalog.py` already draws this line for *"how do I find it"* — *"This
file contains facts about software, and nothing else… Adding an
application is one entry."* This module draws the same line one step
further out, for *"how do I operate it, once found."* A `LaunchMethod` of
`EXECUTABLE_ON_PATH` is a statement about how Chrome starts, in the same
register as `catalog.py`'s own `executables=("chrome",)` — declarative,
hand-authored, and never derived from a probe.

Where a number appears — `StartupEstimate.typical_seconds` — it is a
**declared estimate**, the same discipline MB033's provider catalogue
already established: *"every quality number in the catalogue is a declared
guess, labelled as such."* Nothing here was measured against a stopwatch.

## Why a workflow step can name `paste`, `click` or `submit` and still not
be automation

A `WorkflowStep`'s `verb` is a label from a closed vocabulary — a noun
describing what a human operator does, the same way a recipe's step says
*"fold in the eggs"* without the recipe itself being able to fold
anything. There is no `run()` method anywhere in this file, no callable
attached to a step, and nothing that hands a step to an executor. `tests/
test_desktop_operations.py` proves this by AST: no `subprocess`, no
`pyautogui`, no `click`/`type_text`/`press_key` **call** appears anywhere
in `desktop/operations/`, only the string label.

## No frozen or execution-capable surface is touched

This package imports `master_agent.desktop.inventory` (for
`MachineInventory`, to read what a founder's machine already reports) and
`master_agent.environment_intelligence` (to reuse `Inference`, `Confidence`
and `Evidence` for the one place this module produces a graded
conclusion — `recommend()`, in `executive.py`). It imports **nothing**
from `desktop.actions`, `desktop.plugin` or `desktop.probe` — the
execution-capable half of the Desktop Executive — and nothing from any
frozen package. A test enforces both boundaries by AST.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

# ═══════════════════════ 1 · operation profile ══════════════════════════


class LaunchMethod(str, Enum):
    """How a founder — or whatever the Desktop Executive's own launch
    Action already does — starts this application. Closed, because a
    seventh way to start something is a new fact about the catalogue,
    not a free-text guess."""

    #: Resolved on PATH, exactly the way `catalog.py`'s `executables`
    #: tuple already finds it.
    EXECUTABLE_ON_PATH = "executable_on_path"

    #: Found at a known install location, `catalog.py`'s `windows_paths`/
    #: `posix_paths` fallback.
    KNOWN_INSTALL_PATH = "known_install_path"

    #: Started as a subcommand of a shell already open — `git`, `python`,
    #: `node`, `docker`, `java`; there is no separate "window" to launch.
    SHELL_INVOCATION = "shell_invocation"

    #: A background service or daemon, started once and then addressed
    #: rather than relaunched — `ollama`, `dockerd`.
    BACKGROUND_SERVICE = "background_service"

    #: Not launched on its own — hosted inside another running
    #: application (an editor extension).
    HOSTED_EXTENSION = "hosted_extension"


class WindowStrategy(str, Enum):
    """How this application's window(s) behave, once running. Closed."""

    #: One process, one window. Launching again focuses the existing one.
    SINGLE_INSTANCE_SINGLE_WINDOW = "single_instance_single_window"

    #: One process, multiple windows are normal (one per open workspace
    #: or project).
    SINGLE_INSTANCE_MULTI_WINDOW = "single_instance_multi_window"

    #: A new window per open tab is not how this behaves; tabs live
    #: inside one window, which is itself the common case.
    TABBED_SINGLE_WINDOW = "tabbed_single_window"

    #: No window of its own — runs attached to whatever terminal invoked
    #: it (`git`, `python`, `powershell`).
    TERMINAL_HOSTED = "terminal_hosted"

    #: No window at all in the ordinary case — a background service
    #: reached through something else (a CLI, an API, a browser tab).
    BACKGROUND_SERVICE = "background_service"

    #: No window of its own — lives inside the window of the application
    #: that hosts it.
    HOSTED_IN_OTHER_APPLICATION = "hosted_in_other_application"


class AutomationStrategy(str, Enum):
    """Which existing automation surface, if any, could operate this
    application — never that this module operates it. Closed, and every
    non-`NOT_AUTOMATABLE` value names a component that already exists and
    is not built or invoked here."""

    #: The existing Browser Worker (Playwright-backed) is the surface
    #: that could drive this application, because it is a browser or is
    #: reached through one.
    BROWSER_WORKER = "browser_worker"

    #: Model Context Protocol — Claude Desktop's own extension surface.
    #: Nothing here speaks MCP; this only names that the surface exists.
    MCP_PROTOCOL = "mcp_protocol"

    #: Operable by invoking the application's own command-line interface
    #: — a fact about the application, never a command this module runs.
    CLI_INVOCATION = "cli_invocation"

    #: Only the Desktop Executive's existing window Actions apply
    #: (`launch_application`, `focus_window`, `close_application`,
    #: `bring_to_front`) — no deeper automation surface is known.
    DESKTOP_EXECUTIVE_WINDOW_CONTROL = "desktop_executive_window_control"

    #: No automation surface is known for this application at all.
    NOT_AUTOMATABLE = "not_automatable"


class StartupSpeed(str, Enum):
    """A qualitative band for how long this application takes to become
    usable. Closed, and paired with a declared numeric estimate — see
    `StartupEstimate`."""

    INSTANT = "instant"
    FAST = "fast"
    MODERATE = "moderate"
    SLOW = "slow"


@dataclass(frozen=True)
class StartupEstimate:
    """How long this application takes to become usable. A **declared
    estimate**, not a measurement — nothing in this package times
    anything. `typical_seconds` is `(low, high)`, both inclusive."""

    speed: StartupSpeed
    typical_seconds: tuple[int, int]
    note: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.speed, StartupSpeed):
            raise InvalidOperationKnowledge("speed must be a StartupSpeed")
        low, high = self.typical_seconds
        if not (isinstance(low, int) and isinstance(high, int)):
            raise InvalidOperationKnowledge("typical_seconds must be two integers")
        if low < 0 or high < low:
            raise InvalidOperationKnowledge(
                "typical_seconds must be a non-negative, non-decreasing range"
            )

    def as_dict(self) -> dict[str, Any]:
        return {
            "speed": self.speed.value,
            "typical_seconds": list(self.typical_seconds),
            "note": self.note,
        }


class InvalidOperationKnowledge(ValueError):
    """Raised at construction for operational knowledge that could not be
    stated. At construction, never at read time — a profile with a gap
    should fail to exist rather than answer a founder's question with a
    hole."""


class RecoveryApproach(str, Enum):
    """The profile's own one-line recovery philosophy — distinct from the
    detailed, per-failure-mode `ApplicationRecoveryPlan`. Closed."""

    #: Close it (if open) and launch it again.
    RESTART_APPLICATION = "restart_application"

    #: End the process directly, then launch again — for a window that
    #: will not respond to a normal close.
    KILL_PROCESS_AND_RELAUNCH = "kill_process_and_relaunch"

    #: Nothing to do but wait — the condition resolves on its own.
    WAIT_AND_RETRY = "wait_and_retry"

    #: No mechanical recovery exists; a founder has to look at it.
    MANUAL_INTERVENTION_REQUIRED = "manual_intervention_required"


@dataclass(frozen=True)
class OperationNote:
    """One piece of authored knowledge about how to do one thing with one
    application — launching it, focusing it, checking it is healthy.

    **A description, never a command.** `description` is a sentence a
    trained human operator would recognise; nothing here is a selector, a
    coordinate, or a string handed to a shell. Two fields, deliberately
    small: this is prose knowledge, not a script.
    """

    description: str
    note: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.description, str) or not self.description.strip():
            raise InvalidOperationKnowledge(
                "an operation note must describe what a human operator "
                "would do; an empty description documents nothing"
            )

    def as_dict(self) -> dict[str, Any]:
        return {"description": self.description, "note": self.note}


class FailureMode(str, Enum):
    """The eight ways an application can be found not working. Closed —
    the brief's own contract, verbatim."""

    NOT_RUNNING = "not_running"
    WINDOW_HIDDEN = "window_hidden"
    LOADING = "loading"
    HUNG = "hung"
    MULTIPLE_INSTANCES = "multiple_instances"
    LOGIN_REQUIRED = "login_required"
    UNEXPECTED_POPUP = "unexpected_popup"
    NETWORK_FAILURE = "network_failure"


@dataclass(frozen=True)
class ApplicationOperationProfile:
    """How to operate one application. Every field is knowledge; nothing
    here can be executed.

    The eleven fields the brief names, plus `key`, which ties this
    profile back to `catalog.ApplicationSpec.key` — the one identifier
    this package borrows rather than reinvents, so a profile can never
    exist for an application the Desktop Executive does not already know
    about (§ tests: `test_every_profile_key_is_a_real_catalog_key`).
    """

    key: str
    launch: OperationNote
    focus: OperationNote
    close: OperationNote
    wait_until_ready: OperationNote
    health_check: OperationNote
    recover: OperationNote
    known_failure_modes: tuple[FailureMode, ...]
    startup_time: StartupEstimate
    preferred_launch_method: LaunchMethod
    window_strategy: WindowStrategy
    automation_strategy: AutomationStrategy
    recovery_approach: RecoveryApproach

    def __post_init__(self) -> None:
        if not isinstance(self.key, str) or not self.key.strip():
            raise InvalidOperationKnowledge("a profile must name its application key")
        for field_name in (
            "launch",
            "focus",
            "close",
            "wait_until_ready",
            "health_check",
            "recover",
        ):
            if not isinstance(getattr(self, field_name), OperationNote):
                raise InvalidOperationKnowledge(
                    f"{field_name} must be an OperationNote"
                )
        if not all(isinstance(m, FailureMode) for m in self.known_failure_modes):
            raise InvalidOperationKnowledge(
                "known_failure_modes must be FailureMode values"
            )
        if len(set(self.known_failure_modes)) != len(self.known_failure_modes):
            raise InvalidOperationKnowledge(
                "known_failure_modes must not repeat a mode"
            )

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "launch": self.launch.as_dict(),
            "focus": self.focus.as_dict(),
            "close": self.close.as_dict(),
            "wait_until_ready": self.wait_until_ready.as_dict(),
            "health_check": self.health_check.as_dict(),
            "recover": self.recover.as_dict(),
            "known_failure_modes": [m.value for m in self.known_failure_modes],
            "startup_time": self.startup_time.as_dict(),
            "preferred_launch_method": self.preferred_launch_method.value,
            "window_strategy": self.window_strategy.value,
            "automation_strategy": self.automation_strategy.value,
            "recovery_approach": self.recovery_approach.value,
        }


# ═══════════════════════ 2 · recovery intelligence ═══════════════════════


@dataclass(frozen=True)
class RecoveryGuidance:
    """What a trained operator would check and do for one failure mode,
    on one application. `applicable=False` documents a mode that cannot
    plausibly occur here — stated, never omitted."""

    diagnosis: str
    guidance: tuple[str, ...]
    applicable: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.diagnosis, str) or not self.diagnosis.strip():
            raise InvalidOperationKnowledge(
                "recovery guidance must diagnose the symptom"
            )
        if not self.guidance:
            raise InvalidOperationKnowledge(
                "recovery guidance must name at least one step, even when "
                "that step is 'no action: this mode does not apply here'"
            )

    def as_dict(self) -> dict[str, Any]:
        return {
            "diagnosis": self.diagnosis,
            "guidance": list(self.guidance),
            "applicable": self.applicable,
        }


@dataclass(frozen=True)
class ApplicationRecoveryPlan:
    """Guidance for all eight failure modes, for one application.
    Deliberately total — a plan with a mode missing would let a founder
    hit the one gap that was never written down, which is the silent gap
    this project's own vigilance layer (C19) already refuses to allow for
    a different kind of coverage."""

    key: str
    guidance: tuple[tuple[FailureMode, RecoveryGuidance], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.key, str) or not self.key.strip():
            raise InvalidOperationKnowledge("a recovery plan must name its application key")
        modes = [mode for mode, _ in self.guidance]
        if len(set(modes)) != len(modes):
            raise InvalidOperationKnowledge("a recovery plan must not repeat a mode")
        missing = set(FailureMode) - set(modes)
        if missing:
            names = ", ".join(sorted(m.value for m in missing))
            raise InvalidOperationKnowledge(
                f"a recovery plan must cover every failure mode; {self.key} "
                f"is missing: {names}"
            )

    def for_mode(self, mode: FailureMode) -> RecoveryGuidance:
        for candidate_mode, guidance in self.guidance:
            if candidate_mode is mode:
                return guidance
        raise KeyError(mode)  # pragma: no cover — unreachable given __post_init__'s totality check

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "guidance": {
                mode.value: guidance.as_dict() for mode, guidance in self.guidance
            },
        }


# ═══════════════════════ 3 · human workflow knowledge ════════════════════


class WorkflowVerb(str, Enum):
    """The vocabulary a workflow step may use. Closed, and every member
    is a label describing what a human does — never a callable, never
    dispatched. See the module docstring for why this does not become
    automation."""

    LAUNCH = "launch"
    WAIT = "wait"
    FOCUS = "focus"
    PASTE = "paste"
    TYPE = "type"
    SUBMIT = "submit"
    NAVIGATE = "navigate"
    SWITCH_TAB = "switch_tab"
    SEARCH = "search"
    DOWNLOAD = "download"
    UPLOAD = "upload"
    OPEN_DOCUMENT = "open_document"
    SAVE = "save"
    CLOSE = "close"
    ACCEPT = "accept"
    COPY = "copy"
    OBSERVE = "observe"


@dataclass(frozen=True)
class WorkflowStep:
    """One step in a founder's workflow, described in the founder's own
    terms. `verb` names what happens; `target` names what it happens to,
    in plain language — never a selector."""

    verb: WorkflowVerb
    target: str
    note: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.verb, WorkflowVerb):
            raise InvalidOperationKnowledge("a workflow step's verb must be a WorkflowVerb")
        if not isinstance(self.target, str) or not self.target.strip():
            raise InvalidOperationKnowledge(
                "a workflow step must name what it applies to"
            )

    def as_dict(self) -> dict[str, Any]:
        return {"verb": self.verb.value, "target": self.target, "note": self.note}


@dataclass(frozen=True)
class Workflow:
    """A named sequence of steps a founder actually performs with one
    application. **A description of a pattern, not a script** — nothing
    here can be handed to an executor; see the module docstring."""

    key: str
    name: str
    steps: tuple[WorkflowStep, ...]
    description: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.key, str) or not self.key.strip():
            raise InvalidOperationKnowledge("a workflow must name its application key")
        if not isinstance(self.name, str) or not self.name.strip():
            raise InvalidOperationKnowledge("a workflow must have a name")
        if not self.steps:
            raise InvalidOperationKnowledge(
                "a workflow with no steps documents nothing"
            )

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "description": self.description,
            "steps": [s.as_dict() for s in self.steps],
        }


# ═══════════════════════ 4 · capability matrix ════════════════════════════


class Capability(str, Enum):
    """What an application can be used *for*, in the founder's own
    vocabulary. Closed — the brief's two worked examples (Claude Desktop,
    Chrome) plus enough labels to cover every catalogued application
    honestly. Several are deliberately shared by more than one
    application: that overlap is real, not a defect, and is what
    `DesktopExecutiveV2.recommend()` exists to resolve with a stated
    reason rather than silently."""

    CONVERSATION = "conversation"
    REASONING = "reasoning"
    CLIPBOARD = "clipboard"
    MCP = "mcp"
    FILESYSTEM = "filesystem"
    NAVIGATION = "navigation"
    UPLOAD = "upload"
    DOWNLOAD = "download"
    AUTHENTICATION = "authentication"
    SEARCH = "search"
    CODE_EDITING = "code_editing"
    AI_ASSISTANCE = "ai_assistance"
    LOCAL_INFERENCE = "local_inference"
    CHAT_UI = "chat_ui"
    VERSION_CONTROL = "version_control"
    SCRIPTING = "scripting"
    PACKAGE_MANAGEMENT = "package_management"
    CONTAINERIZATION = "containerization"
    LINUX_SUBSYSTEM = "linux_subsystem"
    JVM_RUNTIME = "jvm_runtime"
    TEST_AUTOMATION = "test_automation"


#: Capabilities for which the environment's AI preference (C22) is
#: consulted to break a tie among installed candidates. See `executive.py`.
AI_CAPABILITIES: tuple[Capability, ...] = (
    Capability.CONVERSATION,
    Capability.REASONING,
    Capability.AI_ASSISTANCE,
    Capability.LOCAL_INFERENCE,
    Capability.CHAT_UI,
)


@dataclass(frozen=True)
class DesktopCapabilityMatrix:
    """Which applications provide which capabilities. Immutable, and
    ordered — `providers_of` returns candidates in the order this matrix
    states them, which is the declared priority order `recommend()` falls
    back to when the machine offers no other evidence."""

    entries: tuple[tuple[str, tuple[Capability, ...]], ...]

    def __post_init__(self) -> None:
        keys = [key for key, _ in self.entries]
        if len(set(keys)) != len(keys):
            raise InvalidOperationKnowledge(
                "a capability matrix must not list the same application key twice"
            )

    def capabilities_of(self, key: str) -> tuple[Capability, ...]:
        for candidate_key, capabilities in self.entries:
            if candidate_key == key:
                return capabilities
        return ()

    def providers_of(self, capability: Capability) -> tuple[str, ...]:
        return tuple(
            key for key, capabilities in self.entries if capability in capabilities
        )

    def all_capabilities(self) -> tuple[Capability, ...]:
        seen: list[Capability] = []
        for _, capabilities in self.entries:
            for capability in capabilities:
                if capability not in seen:
                    seen.append(capability)
        return tuple(seen)

    def as_dict(self) -> dict[str, Any]:
        return {
            key: [c.value for c in capabilities]
            for key, capabilities in self.entries
        }
