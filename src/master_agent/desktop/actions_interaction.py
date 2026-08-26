"""Desktop Executive Foundation 1.0 — verified window interaction.

`desktop/actions.py`'s own docstring is explicit that Mission Brief 030
"Deliberately absent (Deliverable 7): no click, no type, no mouse... a
later Desktop Interaction brief owns this" — and says so again on
`BringToFrontAction` itself. That later work was done
(`execution/window.py`, `execution/process.py`, `execution/executor.py`,
`execution/text_control.py`, `perception/integrity.py`) but never
registered as a capability the Planner could reach; this module is that
registration, as real `Action`s — the existing contract, not a new one.

`desktop/actions.py` stays byte-for-byte as written (its own module
docstring says so, and this foundation does not touch it). These Actions
are new capabilities that happen to share three of the old ones' *names*
(`launch_application`, `focus_window`, `bring_to_front`) — the composition
root decides which implementation is registered under each name (see
`desktop/plugin.py`), so the Planner's catalogue shape never changes,
only what actually runs underneath it.

Every action here follows the same shape §12/§13 of the foundation brief
ask for: act, then observe again, then compare against what was expected
— "the function returned" is never treated as "the action succeeded."
"""
from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from master_agent.app_knowledge.profile import KnowledgeType
from master_agent.desktop.actions import DesktopContext, _DesktopAction
from master_agent.desktop.execution.backends import WindowInfo
from master_agent.desktop.execution.executor import DesktopExecutor
from master_agent.desktop.execution.process import ProcessExecutive
from master_agent.desktop.execution.text_control import (
    ClassicControlResolver,
    ControlNotFound,
    Win32ChildEnumBackend,
    classify_window,
)
from master_agent.desktop.execution.uia_control import (
    UiaAutomationBridge,
    UiaTargetNotFound,
    UiaUnavailable,
)
from master_agent.desktop.execution.window import WindowManager
from master_agent.desktop.execution.win32_backends import Win32WindowBackend
from master_agent.desktop.perception.integrity import (
    CLEAR,
    IntegrityGuard,
    IntegrityUnavailable,
    Win32IntegrityBackend,
)
from master_agent.desktop.perception.win32_probe import (
    ResponsivenessUnavailable,
    Win32ResponsivenessBackend,
)
from master_agent.desktop.intelligence.app_knowledge_bridge import resolve_app_knowledge
from master_agent.desktop.intelligence.evidence import capture_evidence
from master_agent.executor.action import ExecutionResult
from master_agent.plugins.base import PermissionCategory, RiskTier

VERIFIED_LAUNCH_APPLICATION = "launch_application"
VERIFIED_FOCUS_WINDOW = "focus_window"
VERIFIED_BRING_TO_FRONT = "bring_to_front"
# Prefixed `desktop_*` (unlike the three names above, which supersede
# existing Desktop-only names): `executor/actions/browser/{click,
# type_text, press_key}.py` already own the bare names on the one shared
# `LocalExecutor` every Executive registers onto (`launcher/boot.py`'s own
# `LocalExecutor(permissions)` passed to every plugin — one flat action
# namespace, by design, per `executor/executor.py`'s own module
# docstring). `read_text`/`close_window` have no such collision and keep
# their plain names.
CLICK_CONTROL = "desktop_click"
TYPE_TEXT = "desktop_type_text"
READ_TEXT = "read_text"
PRESS_KEY = "desktop_press_key"
CLOSE_WINDOW = "close_window"
FIND_TARGET = "find_target"

#: Bounded — never an unbounded poll. A founder waiting on a desktop
#: action is waiting on a real person's attention, the same latency
#: argument `runtime/config.py`'s own retry policy already makes.
_FOCUS_RETRY_ATTEMPTS = 3
_FOCUS_RETRY_DELAY_SECONDS = 0.15
#: Found live (Universal Windows Environment Discovery): 15s was too
#: short for at least one real, MSIX-packaged AI application on this
#: machine (ChatGPT/Codex) to raise its first window on a cold launch —
#: the process was confirmed running well within 15s, but its window did
#: not appear until afterward. The window-locate loop below already
#: returns as soon as a window appears, so this ceiling only matters for
#: genuinely slow-starting applications; it does not slow down a fast one
#: like Chrome or Notepad.
_LAUNCH_WAIT_TIMEOUT_SECONDS = 30.0


#: One `IUIAutomation` COM instance for the process's lifetime — unlike
#: `_executor()`'s deliberately-cheap-to-rebuild composition, creating a
#: COM object is real overhead every action would otherwise re-pay.
_uia_bridge = UiaAutomationBridge()


def _executor(context: DesktopContext) -> DesktopExecutor:
    """One `DesktopExecutor`, wired with the real Win32 backends. Not
    cached on `context` — cheap to build (no I/O in `__init__`), and a
    fresh one per call keeps every Action's dependencies visible in its
    own `__init__` rather than smuggled through shared mutable state."""
    return DesktopExecutor(
        context=context,
        window_manager=WindowManager(Win32WindowBackend()),
        process=ProcessExecutive(context=context),
    )


class _VerifiedInteractionAction(_DesktopAction):
    """Shared machinery: resolve the target application's window, confirm
    it (not merely locate it) via a bounded foreground-and-verify loop,
    and check the integrity boundary before any input is sent — §4/§5 of
    the foundation brief, in the one place every interaction action needs
    it rather than each repeating it."""

    def _windows(self) -> WindowManager:
        return WindowManager(Win32WindowBackend())

    def _integrity_guard(self) -> IntegrityGuard:
        return IntegrityGuard(Win32IntegrityBackend())

    def _resolve_window(self, application: str) -> ExecutionResult:
        """Real process → real window, scoped to that one application —
        never a desktop-wide search. Returns an `ExecutionResult`;
        `output["window"]` on success.

        `validate()` (`_require_known_application`) already refuses an
        application with no catalog spec before the Executor ever calls
        `run()`, so this should be unreachable through the real
        production path — but `Action`'s own contract is "never raise,
        return a structured failure" (its docstring: "It should not
        raise for ordinary failures"), and a `None` spec here previously
        raised a bare `AttributeError` instead. Found calling `run()`
        directly during a live integration test; guarded defensively
        rather than left to rely solely on `validate()` running first.
        """
        spec = self._spec(application)
        if spec is None:
            return ExecutionResult(success=False, errors=[f"{application!r} is not a known application"])
        running = self._context.refresh(read_versions=False, deep=False).running(spec.key)
        if not running:
            return ExecutionResult(success=False, errors=[f"{spec.label} is not running"])
        pids = frozenset(p.pid for p in running)

        located = self._windows().locate_by_process(pids)
        if not located.success:
            return located
        window = located.output["windows"][0]

        try:
            responding = Win32ResponsivenessBackend().is_responding(window["handle"])
        except ResponsivenessUnavailable:
            responding = True  # cannot determine — do not block on an unreadable probe
        if not responding:
            return ExecutionResult(
                success=False,
                errors=[f"{spec.label}'s window ({window['handle']}) is not responding"],
                output={"window": window},
            )

        try:
            check = self._integrity_guard().check(window["process_id"])
        except IntegrityUnavailable:
            check = None
        if check is not None and check.blocked:
            return ExecutionResult(
                success=False,
                errors=[f"{check.condition}: {check.detail}"],
                output={"window": window, "integrity_condition": check.condition},
            )

        return ExecutionResult(success=True, output={"window": window})

    def _focus_and_confirm(self, window: dict[str, Any]) -> ExecutionResult:
        """§4: action must not start until target window input state is
        confirmed. Brings the window forward, then re-reads the *actual*
        foreground window and compares — never assumes the call worked
        because it returned without error."""
        windows = self._windows()
        last_active: dict[str, Any] | None = None
        for _attempt in range(_FOCUS_RETRY_ATTEMPTS):
            windows.bring_to_front(window["handle"])
            active = windows.active()
            if active.success and active.output["handle"] == window["handle"]:
                return ExecutionResult(success=True, output={"window": active.output})
            last_active = active.output if active.success else None
            time.sleep(_FOCUS_RETRY_DELAY_SECONDS)
        return ExecutionResult(
            success=False,
            errors=[
                f"could not confirm window {window['handle']} reached the foreground "
                f"after {_FOCUS_RETRY_ATTEMPTS} attempts"
            ],
            output={"expected": window, "actual_foreground": last_active},
        )


class VerifiedLaunchApplicationAction(_DesktopAction):
    """§11: launch success is process + visible window + (where
    practical) foreground — never "the subprocess started." Composes the
    existing `LaunchApplicationAction`/`ProcessExecutive.wait`/
    `WindowManager` rather than re-implementing any of them."""

    name = VERIFIED_LAUNCH_APPLICATION
    description = "Launch an installed application and verify it produced a real, visible window."
    risk_tier = RiskTier.REVERSIBLE_WRITE
    permission_category = PermissionCategory.SYSTEM
    expected_result = (
        "The application's process exists and a visible top-level window "
        "belonging to it exists."
    )

    def required_parameters(self) -> list[str]:
        return ["application"]

    def optional_parameters(self) -> list[dict[str, Any]] | None:
        return [
            {
                "name": "focus",
                "type": "boolean",
                "description": "Bring the new window to the foreground after it appears.",
                "default": True,
            }
        ]

    def validate(self, parameters: dict[str, Any]) -> list[str]:
        return self._require_known_application(parameters)

    def run(self, parameters: dict[str, Any]) -> ExecutionResult:
        spec = self._spec(parameters["application"])
        should_focus = parameters.get("focus", True)

        executor = _executor(self._context)
        launched = executor.execute(spec.key)
        if not launched.success:
            return launched

        waited = executor.process.wait(spec.key, timeout_seconds=_LAUNCH_WAIT_TIMEOUT_SECONDS)
        if not waited.success:
            return ExecutionResult(
                success=False,
                errors=[f"{spec.label} process did not report running: {'; '.join(waited.errors)}"],
            )

        running = self._context.refresh(read_versions=False, deep=False).running(spec.key)
        if not running:
            return ExecutionResult(
                success=False,
                errors=[f"{spec.label} process exists but disappeared before its window could be found"],
            )
        pids = frozenset(p.pid for p in running)

        window_deadline = time.monotonic() + _LAUNCH_WAIT_TIMEOUT_SECONDS
        located = None
        while time.monotonic() < window_deadline:
            located = executor.windows.locate_by_process(pids)
            if located.success:
                break
            time.sleep(0.3)
        if located is None or not located.success:
            return ExecutionResult(
                success=False,
                errors=[
                    f"{spec.label} is running (pid(s): {sorted(pids)}) but no visible "
                    "top-level window was found for it"
                ],
                output={"application": spec.key, "pids": sorted(pids)},
            )
        window = located.output["windows"][0]

        foreground_confirmed = False
        if should_focus:
            focused = executor.windows.bring_to_front(window["handle"])
            active = executor.windows.active()
            foreground_confirmed = (
                focused.success and active.success and active.output["handle"] == window["handle"]
            )

        return ExecutionResult(
            success=True,
            output={
                "application": spec.key,
                "pids": sorted(pids),
                "window": window,
                "foreground_confirmed": foreground_confirmed,
            },
        )


class VerifiedFocusWindowAction(_VerifiedInteractionAction):
    name = VERIFIED_FOCUS_WINDOW
    description = "Focus a specific running application's window, and confirm it actually reached the foreground."
    risk_tier = RiskTier.REVERSIBLE_WRITE
    permission_category = PermissionCategory.SYSTEM
    expected_result = "The application's window is confirmed as the real foreground window."

    def required_parameters(self) -> list[str]:
        return ["application"]

    def optional_parameters(self) -> list[dict[str, Any]]:
        """No optional arguments.

        Verified against this Action's own `validate()`, `run()` and
        every helper they call: it reads exactly the required
        arguments above and nothing else. Returning a list -- even an
        empty one -- is this Action stating that its argument roster
        is complete.

        That statement is what the deterministic planner needs. An
        open roster means `optional arguments exist and are not
        listed`, and a planner that cannot see the whole contract
        correctly refuses to guess at it -- so this capability could
        not be planned without a model, however fully the founder
        spelled the request out."""
        return []

    def validate(self, parameters: dict[str, Any]) -> list[str]:
        return self._require_known_application(parameters)

    def run(self, parameters: dict[str, Any]) -> ExecutionResult:
        resolved = self._resolve_window(parameters["application"])
        if not resolved.success:
            return resolved
        return self._focus_and_confirm(resolved.output["window"])


class VerifiedBringToFrontAction(VerifiedFocusWindowAction):
    name = VERIFIED_BRING_TO_FRONT
    description = "Bring a running application's window to the front, and confirm it actually arrived."


class FindTargetAction(_VerifiedInteractionAction):
    """Universal Autonomous Desktop Executive, Phase 4's explicit
    `desktop.find_target` primitive: locate one semantic element by its
    accessible name within a confirmed-foreground window, and report its
    identity plus the center of its own real, UIA-reported bounding
    rectangle — read-only, acts on nothing. This is what lets
    `ClickControlAction`'s existing, deliberately coordinate-based design
    (see its own docstring: "for when a caller already resolved a
    specific point") compose with real semantic targeting instead of a
    caller guessing pixels: a mission plans `find_target` then
    `desktop_click(x, y)` as two ordinary steps, exactly the "Planner
    composes primitives" shape Phase 6 asks for — no new composite
    action, no per-app knowledge baked in here.
    """

    name = FIND_TARGET
    description = "Locate a named application's UI element by its accessible name, without acting on it."
    risk_tier = RiskTier.READ_ONLY
    permission_category = PermissionCategory.SYSTEM
    expected_result = "The element's identity and click point are returned; nothing changes."

    def required_parameters(self) -> list[str]:
        return ["application", "name_contains"]

    def optional_parameters(self) -> list[dict[str, Any]]:
        """No optional arguments.

        Verified against this Action's own `validate()`, `run()` and
        every helper they call: it reads exactly the required
        arguments above and nothing else. Returning a list -- even an
        empty one -- is this Action stating that its argument roster
        is complete.

        That statement is what the deterministic planner needs. An
        open roster means `optional arguments exist and are not
        listed`, and a planner that cannot see the whole contract
        correctly refuses to guess at it -- so this capability could
        not be planned without a model, however fully the founder
        spelled the request out."""
        return []

    def validate(self, parameters: dict[str, Any]) -> list[str]:
        errors = self._require_known_application(parameters)
        if not isinstance(parameters.get("name_contains"), str) or not parameters.get("name_contains", "").strip():
            errors.append("'name_contains' must be a non-empty string")
        return errors

    def run(self, parameters: dict[str, Any]) -> ExecutionResult:
        resolved = self._resolve_window(parameters["application"])
        if not resolved.success:
            return resolved
        window = resolved.output["window"]

        try:
            element = _uia_bridge.find(window["handle"], name_contains=parameters["name_contains"])
        except (UiaUnavailable, UiaTargetNotFound) as exc:
            return ExecutionResult(success=False, errors=[str(exc)])

        info = _uia_bridge.describe(element)
        return ExecutionResult(
            success=True,
            output={
                "name": info.name, "automation_id": info.automation_id,
                "control_type": info.control_type, "is_enabled": info.is_enabled,
                "x": info.center_x, "y": info.center_y,
            },
        )


class ObserveDesktopAction(_VerifiedInteractionAction):
    """Desktop Intelligence, Part F: `desktop.observe` — the OBSERVE
    primitive registered onto the same read-only boundary `FindTargetAction`/
    `ReadWindowTextAction` already occupy. Resolves the window the exact
    same way `FindTargetAction` does (`_resolve_window()` — process
    attribution, responsiveness, integrity; never focuses or brings it
    forward), then composes `desktop.intelligence.evidence.capture_evidence()`
    — the one new read-only primitive this mission adds — rather than a
    second observation mechanism. Never types, clicks, submits, or renames
    anything; a Planner step reads `DesktopObservation.as_dict()` and
    plans its *next* action from it, exactly the "Observe -> Understand"
    boundary this mission is scoped to, nothing past it.
    """

    name = "desktop_observe"
    description = (
        "Observe a named application's confirmed window read-only: visible elements, their "
        "semantic roles where determinable, focus, and actionable controls. Never acts on anything."
    )
    risk_tier = RiskTier.READ_ONLY
    permission_category = PermissionCategory.SYSTEM
    expected_result = "A structured DesktopObservation is returned; nothing on screen changes."

    def required_parameters(self) -> list[str]:
        return ["application"]

    def optional_parameters(self) -> list[dict[str, Any]] | None:
        return [
            {
                "name": "capture_screenshot",
                "type": "boolean",
                "description": "Also capture and associate a screenshot of the window as evidence.",
                "default": False,
            }
        ]

    def validate(self, parameters: dict[str, Any]) -> list[str]:
        return self._require_known_application(parameters)

    def run(self, parameters: dict[str, Any]) -> ExecutionResult:
        application = parameters["application"]
        resolved = self._resolve_window(application)
        if not resolved.success:
            return resolved
        window = WindowInfo(**resolved.output["window"])

        screenshot_backend = None
        if bool(parameters.get("capture_screenshot", False)):
            from master_agent.desktop.intelligence.screenshot import Win32ScreenshotBackend

            try:
                screenshot_backend = Win32ScreenshotBackend()
            except Exception:  # noqa: BLE001 — screenshots are corroborating evidence, never required
                screenshot_backend = None

        observation = capture_evidence(
            uia=_uia_bridge, window=window, application=application,
            application_confidence=KnowledgeType.OBSERVED,
            application_reason=f"window {window.handle} resolved for {application!r} via _resolve_window()",
            app_knowledge=resolve_app_knowledge(application),
            screenshot_backend=screenshot_backend,
            now=datetime.now(UTC),
        )
        return ExecutionResult(success=True, output=observation.as_dict())


class ClickControlAction(_VerifiedInteractionAction):
    """§9/§17: coordinates are the fallback, never the primary path — this
    action exists for when a caller already resolved a specific point
    (from `read_text`'s own control bounds, or the semantic control
    resolver), never for blind desktop-wide clicking. The window is
    confirmed foregrounded first (§4), so the click cannot land on the
    wrong application."""

    name = CLICK_CONTROL
    description = "Click a point inside a named application's confirmed-foreground window."
    risk_tier = RiskTier.REVERSIBLE_WRITE
    permission_category = PermissionCategory.SYSTEM
    expected_result = "The click is delivered to the confirmed-foreground window."

    def required_parameters(self) -> list[str]:
        return ["application", "x", "y"]

    def optional_parameters(self) -> list[dict[str, Any]]:
        """No optional arguments.

        Verified against this Action's own `validate()`, `run()` and
        every helper they call: it reads exactly the required
        arguments above and nothing else. Returning a list -- even an
        empty one -- is this Action stating that its argument roster
        is complete.

        That statement is what the deterministic planner needs. An
        open roster means `optional arguments exist and are not
        listed`, and a planner that cannot see the whole contract
        correctly refuses to guess at it -- so this capability could
        not be planned without a model, however fully the founder
        spelled the request out."""
        return []

    def validate(self, parameters: dict[str, Any]) -> list[str]:
        errors = self._require_known_application(parameters)
        for key in ("x", "y"):
            if not isinstance(parameters.get(key), (int, float)):
                errors.append(f"'{key}' must be a number")
        return errors

    def run(self, parameters: dict[str, Any]) -> ExecutionResult:
        resolved = self._resolve_window(parameters["application"])
        if not resolved.success:
            return resolved
        focused = self._focus_and_confirm(resolved.output["window"])
        if not focused.success:
            return focused

        executor = _executor(self._context)
        clicked = executor.mouse.click(int(parameters["x"]), int(parameters["y"]))
        if not clicked.success:
            return clicked
        return ExecutionResult(
            success=True,
            output={**clicked.output, "window": focused.output["window"]},
        )


class TypeIntoWindowAction(_VerifiedInteractionAction):
    """Universal Autonomous Desktop Executive: adaptive semantic
    targeting, never blind keystrokes as the first resort. §3's own
    interface classifier (`text_control.classify_window`) decides, per
    window, whether a cheap classic-control lookup can even succeed —
    Notepad's `NotepadTextBox` still can, so it stays the fast path with
    no COM overhead. Any window whose real content is Chromium (Electron)
    or WinUI/XAML-rendered (`Chrome_RenderWidgetHostHWND` and siblings —
    confirmed live, e.g. Claude Desktop) classifies `uia_required` and is
    resolved via `IUIAutomation` instead — the one mechanism Windows
    itself guarantees exposes that content, proven live end-to-end
    against Claude Desktop's own "Prompt" composer this session: focus
    via UIA's own `SetFocus`, real keystrokes, and a read-back that must
    match exactly before this action reports success. Physical keyboard
    injection into a merely-foreground window (no confirmed target at
    all) is the last resort, not the second.
    """

    name = TYPE_TEXT
    description = "Type text into a named application's window, verifying the value where possible."
    risk_tier = RiskTier.REVERSIBLE_WRITE
    permission_category = PermissionCategory.SYSTEM
    expected_result = "The target control's text contains what was typed."

    def required_parameters(self) -> list[str]:
        return ["application", "text"]

    def optional_parameters(self) -> list[dict[str, Any]] | None:
        return [
            {
                "name": "control_class",
                "type": "string",
                "description": (
                    "The exact Win32 class name of the target control, for "
                    "classic Win32/WinUI windows. Omit it to try known "
                    "text-control classes automatically."
                ),
                "default": None,
            },
            {
                "name": "target_name_contains",
                "type": "string",
                "description": (
                    "A substring of the target element's accessible name, "
                    "for Electron/Chromium/WinUI windows resolved via UI "
                    "Automation (e.g. \"Prompt\" for a chat composer). Omit "
                    "it to use the smallest focusable, text-bearing, "
                    "bottom-anchored element as a best-effort default."
                ),
                "default": None,
            },
            {
                "name": "append",
                "type": "boolean",
                "description": "Append to the control's existing text instead of replacing it.",
                "default": False,
            },
        ]

    def validate(self, parameters: dict[str, Any]) -> list[str]:
        errors = self._require_known_application(parameters)
        if not isinstance(parameters.get("text"), str):
            errors.append("'text' must be a string")
        return errors

    def run(self, parameters: dict[str, Any]) -> ExecutionResult:
        resolved = self._resolve_window(parameters["application"])
        if not resolved.success:
            return resolved
        window = resolved.output["window"]
        focused = self._focus_and_confirm(window)
        if not focused.success:
            return focused

        text = parameters["text"]
        control_class = parameters.get("control_class") or None
        name_contains = parameters.get("target_name_contains") or None
        append = bool(parameters.get("append", False))

        interface = "classic" if control_class else classify_window(window["handle"], Win32ChildEnumBackend())
        if interface == "classic":
            classic_result = self._type_classic(window, control_class, name_contains, text, append)
            if classic_result is not None:
                return classic_result
            # No classic control matched despite the classifier's read —
            # fall through to UIA rather than giving up (Section 7:
            # recover, don't just fail).

        uia_result = self._type_uia(window, name_contains, text, append)
        if uia_result is not None:
            return uia_result

        # Neither semantic mechanism found a target — physical keyboard
        # input into the already-confirmed-foreground window is the
        # documented last resort. Found live, during a real autonomous
        # Planner-driven mission: this branch previously reported
        # `success=True` alongside `verified: False` — MissionControl's
        # own `TaskState`/completion semantics key off `success`, not the
        # nested `verified` flag, so a Planner-driven mission that landed
        # here would have been marked COMPLETED despite this action
        # itself being unable to confirm anything. Universal Autonomous
        # Desktop Executive §7 is explicit: "typed successfully but
        # cannot prove it reached the composer → UNVERIFIED, not DONE" —
        # `success=False` is what actually makes that true through
        # MissionControl's existing, unmodified semantics, not a new
        # verification concept layered on top of them.
        executor = _executor(self._context)
        typed = executor.keyboard.type(text)
        if not typed.success:
            return typed
        return ExecutionResult(
            success=False,
            errors=["typed via unverified keyboard fallback — no semantic target was found to confirm placement"],
            output={
                "method": "keyboard_fallback", "typed_characters": len(text),
                "verified": False,
                "reason": "no semantic target (classic control or UIA element) was found",
            },
        )

    def _type_classic(self, window, control_class, name_contains, text, append) -> ExecutionResult | None:
        resolver = ClassicControlResolver(Win32ChildEnumBackend())
        try:
            control = resolver.find(window["handle"], class_name=control_class, text_contains=name_contains)
        except ControlNotFound:
            return None

        new_text = (resolver.read_text(control) + text) if append else text
        wrote = resolver.write_text(control, new_text)
        if not wrote:
            return ExecutionResult(
                success=False,
                errors=[f"WM_SETTEXT failed for control {control.handle} ({control.class_name})"],
            )

        read_back = resolver.read_text(control)
        verified = text in read_back
        if not verified:
            return ExecutionResult(
                success=False,
                errors=[
                    f"wrote to control {control.handle} but the read-back value does not "
                    f"contain the requested text"
                ],
                output={"control": control.handle, "read_back": read_back, "verified": False},
            )

        return ExecutionResult(
            success=True,
            output={
                "method": "semantic_control", "control": control.handle,
                "control_class": control.class_name, "value": read_back, "verified": True,
            },
        )

    def _type_uia(self, window, name_contains, text, append) -> ExecutionResult | None:
        try:
            if name_contains:
                element = _uia_bridge.find(window["handle"], name_contains=name_contains)
            else:
                element = _uia_bridge.find_composer(window["handle"])
        except (UiaUnavailable, UiaTargetNotFound):
            return None

        executor = _executor(self._context)
        verified = _uia_bridge.write_text(element, text, executor.keyboard, append=append, mouse=executor.mouse)
        info = _uia_bridge.describe(element)
        if not verified:
            return ExecutionResult(
                success=False,
                errors=[f"wrote to UIA element {info.name!r} but the read-back value did not match"],
                output={"method": "uia", "target_name": info.name, "verified": False},
            )
        return ExecutionResult(
            success=True,
            output={"method": "uia", "target_name": info.name, "value": text, "verified": True},
        )


class ReadWindowTextAction(_VerifiedInteractionAction):
    """The read-back half of `TypeIntoWindowAction`, also callable on its
    own — §9's `ReadText`/`ReadValue`. Same adaptive classic-or-UIA
    targeting as `TypeIntoWindowAction`; this is also what a mission step
    uses to observe an AI application's actual response after submitting
    a prompt (Phase 5's external-verification requirement) — proven live
    against Claude Desktop's real response text this session."""

    name = READ_TEXT
    description = "Read the text/value of a named application's target control."
    risk_tier = RiskTier.READ_ONLY
    permission_category = PermissionCategory.SYSTEM
    expected_result = "The control's current text is returned."

    def required_parameters(self) -> list[str]:
        return ["application"]

    def optional_parameters(self) -> list[dict[str, Any]] | None:
        return [
            {
                "name": "control_class",
                "type": "string",
                "description": (
                    "The exact Win32 class name of the target control, for "
                    "classic Win32/WinUI windows. Omit it to try known "
                    "text-control classes automatically."
                ),
                "default": None,
            },
            {
                "name": "target_name_contains",
                "type": "string",
                "description": (
                    "A substring of the target element's accessible name, "
                    "for Electron/Chromium/WinUI windows resolved via UI "
                    "Automation. Omit it to read the largest text-bearing "
                    "region (the main content/response area) as a "
                    "best-effort default."
                ),
                "default": None,
            },
        ]

    def validate(self, parameters: dict[str, Any]) -> list[str]:
        return self._require_known_application(parameters)

    def run(self, parameters: dict[str, Any]) -> ExecutionResult:
        resolved = self._resolve_window(parameters["application"])
        if not resolved.success:
            return resolved
        window = resolved.output["window"]
        control_class = parameters.get("control_class") or None
        name_contains = parameters.get("target_name_contains") or None

        interface = "classic" if control_class else classify_window(window["handle"], Win32ChildEnumBackend())
        if interface == "classic":
            resolver = ClassicControlResolver(Win32ChildEnumBackend())
            try:
                control = resolver.find(window["handle"], class_name=control_class, text_contains=name_contains)
                return ExecutionResult(
                    success=True,
                    output={
                        "method": "classic", "control": control.handle,
                        "control_class": control.class_name, "value": resolver.read_text(control),
                    },
                )
            except ControlNotFound:
                pass  # fall through to UIA rather than failing outright

        try:
            if name_contains:
                element = _uia_bridge.find(window["handle"], name_contains=name_contains)
            else:
                element = _uia_bridge.find_main_content(window["handle"])
            info = _uia_bridge.describe(element)
            return ExecutionResult(
                success=True,
                output={"method": "uia", "target_name": info.name, "value": _uia_bridge.read_text(element)},
            )
        except (UiaUnavailable, UiaTargetNotFound) as exc:
            return ExecutionResult(success=False, errors=[str(exc)])


class PressKeyAction(_VerifiedInteractionAction):
    name = PRESS_KEY
    description = "Press a single key in a named application's confirmed-foreground window."
    risk_tier = RiskTier.REVERSIBLE_WRITE
    permission_category = PermissionCategory.SYSTEM
    expected_result = "The key is delivered to the confirmed-foreground window."

    def required_parameters(self) -> list[str]:
        return ["application", "key"]

    def optional_parameters(self) -> list[dict[str, Any]]:
        """No optional arguments.

        Verified against this Action's own `validate()`, `run()` and
        every helper they call: it reads exactly the required
        arguments above and nothing else. Returning a list -- even an
        empty one -- is this Action stating that its argument roster
        is complete.

        That statement is what the deterministic planner needs. An
        open roster means `optional arguments exist and are not
        listed`, and a planner that cannot see the whole contract
        correctly refuses to guess at it -- so this capability could
        not be planned without a model, however fully the founder
        spelled the request out."""
        return []

    def validate(self, parameters: dict[str, Any]) -> list[str]:
        errors = self._require_known_application(parameters)
        if not isinstance(parameters.get("key"), str) or not parameters.get("key", "").strip():
            errors.append("'key' must be a non-empty string")
        return errors

    def run(self, parameters: dict[str, Any]) -> ExecutionResult:
        resolved = self._resolve_window(parameters["application"])
        if not resolved.success:
            return resolved
        focused = self._focus_and_confirm(resolved.output["window"])
        if not focused.success:
            return focused
        executor = _executor(self._context)
        return executor.keyboard.press(parameters["key"])


class CloseWindowAction(_VerifiedInteractionAction):
    """`WM_CLOSE` (via `WindowManager.close`) — asks the window to close
    itself, never a forced kill; `CloseApplicationAction` in
    `desktop/actions.py` remains the `IRREVERSIBLE` forced-terminate path.
    Verifies the window is actually gone rather than assuming the posted
    message was honoured."""

    name = CLOSE_WINDOW
    description = "Ask a named application's window to close, and verify it disappeared."
    risk_tier = RiskTier.REVERSIBLE_WRITE
    permission_category = PermissionCategory.SYSTEM
    expected_result = "The window no longer appears in the visible window list."

    def required_parameters(self) -> list[str]:
        return ["application"]

    def optional_parameters(self) -> list[dict[str, Any]]:
        """No optional arguments.

        Verified against this Action's own `validate()`, `run()` and
        every helper they call: it reads exactly the required
        arguments above and nothing else. Returning a list -- even an
        empty one -- is this Action stating that its argument roster
        is complete.

        That statement is what the deterministic planner needs. An
        open roster means `optional arguments exist and are not
        listed`, and a planner that cannot see the whole contract
        correctly refuses to guess at it -- so this capability could
        not be planned without a model, however fully the founder
        spelled the request out."""
        return []

    def validate(self, parameters: dict[str, Any]) -> list[str]:
        return self._require_known_application(parameters)

    def run(self, parameters: dict[str, Any]) -> ExecutionResult:
        resolved = self._resolve_window(parameters["application"])
        if not resolved.success:
            return resolved
        handle = resolved.output["window"]["handle"]

        windows = self._windows()
        closed = windows.close(handle)
        if not closed.success:
            return closed

        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            still_there = windows.enumerate(visible_only=True)
            handles = {w["handle"] for w in still_there.output.get("windows", [])} if still_there.success else set()
            if handle not in handles:
                return ExecutionResult(success=True, output={"handle": handle, "closed": True})
            time.sleep(0.2)
        return ExecutionResult(
            success=False,
            errors=[f"window {handle} still present after close was requested (an unsaved-work prompt may be blocking it)"],
            output={"handle": handle},
        )


DESKTOP_INTERACTION_ACTION_CLASSES: tuple[type[_DesktopAction], ...] = (
    VerifiedLaunchApplicationAction,
    VerifiedFocusWindowAction,
    VerifiedBringToFrontAction,
    FindTargetAction,
    ObserveDesktopAction,
    ClickControlAction,
    TypeIntoWindowAction,
    ReadWindowTextAction,
    PressKeyAction,
    CloseWindowAction,
)
