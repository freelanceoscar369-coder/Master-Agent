"""DesktopGateway -- canonical Evidence for the Desktop Executive.

## What this is, and is not

It is **not** a second Desktop implementation. It subclasses
`PluginGateway` and overrides exactly one method, `verify()`. Execution is
inherited untouched, so every capability still runs the way it runs today:

    MissionControl -> DesktopPlugin -> the registered Action
                   -> DesktopExecutor / DesktopExecutiveV2
                   -> Process / Window / Keyboard / Mouse / UIA

Nothing here launches, clicks, types, focuses or closes anything. The one
thing that was missing was the adapter between the Desktop Executive and
the canonical `verification.Evidence` contract, and that is all this adds.

## Why only some capabilities

`ExecutionResult.success` is the Action's claim about its own work, and
ADR-0011 exists so completion never rests on a claim like that. So a
capability is verifiable here only where the Desktop package already
offers a **read-only** way to re-observe the fact afterwards:

* `WindowManager.enumerate` / `.locate` / `.active` -- windows
* `ProcessExecutive.is_running` -- processes

Where no such generic postcondition exists -- a click, a keypress, an
arbitrary shell command -- this returns `None`, which says "not
established" rather than inventing a verdict. That is deliberate: a
fabricated MATCHED for `desktop_click` would be exactly the failure this
whole line of work exists to remove.
"""
from __future__ import annotations

from typing import Any

from master_agent.runtime.gateway import PluginGateway
from master_agent.verification.evidence import (
    Evidence,
    ExpectedOutcome,
    ObservationCheck,
)
from master_agent.verification.verifier import Verifier

#: Capabilities whose effect is that a process is running.
_PROCESS_PRESENT = frozenset({"launch_application"})
#: Capabilities whose effect is that a process is gone.
_PROCESS_ABSENT = frozenset({"close_application"})
#: Capabilities whose effect is that a matching window is frontmost.
_WINDOW_FOREGROUND = frozenset({"focus_window", "bring_to_front"})
#: Capabilities whose effect is that a matching window is gone.
_WINDOW_ABSENT = frozenset({"close_window"})


def _local(capability: str) -> str:
    return capability.rsplit(".", 1)[-1].replace("_", "").replace("-", "").lower()


def _in(capability: str, names: frozenset[str]) -> bool:
    wanted = _local(capability)
    return any(_local(name) == wanted for name in names)


def supports(capability: str) -> bool:
    """Is there a read-only postcondition this gateway can re-observe?"""
    return (
        _in(capability, _PROCESS_PRESENT)
        or _in(capability, _PROCESS_ABSENT)
        or _in(capability, _WINDOW_FOREGROUND)
        or _in(capability, _WINDOW_ABSENT)
    )


def _application_of(payload: dict[str, Any]) -> str:
    for key in ("application", "app", "name", "target"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _title_of(payload: dict[str, Any]) -> str:
    for key in ("title", "title_contains", "window", "target"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


class _DesktopStateVerifier(Verifier):
    """Re-observes process/window state through the Desktop package's own
    read-only APIs. Never touches the Action's report."""

    worker_name = "desktop"
    environment_name = "windows_desktop"

    def __init__(self, application: str, title: str) -> None:
        self._application = application
        self._title = title

    def capture_observation_dict(self) -> dict[str, Any]:
        from master_agent.desktop.execution.process import ProcessExecutive
        from master_agent.desktop.execution.window import WindowManager

        windows = WindowManager()

        process_running: bool | None = None
        if self._application:
            probe = ProcessExecutive().is_running(self._application)
            if probe.success:
                # `is_running` reports presence in its output; treat an
                # explicit False as False and anything truthy as True.
                process_running = bool(probe.output)

        window_present: bool | None = None
        foreground_matches: bool | None = None
        needle = (self._title or self._application).strip().lower()
        if needle:
            located = windows.locate(needle)
            window_present = bool(located.success and located.output)

            active = windows.active()
            if active.success and active.output:
                foreground_matches = needle in str(active.output).lower()

        return {
            "application": self._application,
            "title": self._title,
            "process_running": process_running,
            "window_present": window_present,
            "foreground_matches": foreground_matches,
        }


def bind_for_environment(
    capability: str,
    payload: dict[str, Any],
    description: str,
) -> ExpectedOutcome | None:
    """The Planner's claim, expressed as checks the desktop can answer."""
    if not supports(capability):
        return None

    if _in(capability, _PROCESS_PRESENT):
        return ExpectedOutcome(description=description, checks=[ObservationCheck(
            field="process_running", operator="equals", value=True,
            description=f"'{_application_of(payload)}' is running",
        )])

    if _in(capability, _PROCESS_ABSENT):
        return ExpectedOutcome(description=description, checks=[ObservationCheck(
            field="process_running", operator="equals", value=False,
            description=f"'{_application_of(payload)}' is no longer running",
        )])

    if _in(capability, _WINDOW_ABSENT):
        return ExpectedOutcome(description=description, checks=[ObservationCheck(
            field="window_present", operator="equals", value=False,
            description="the window is no longer open",
        )])

    return ExpectedOutcome(description=description, checks=[ObservationCheck(
        field="foreground_matches", operator="equals", value=True,
        description="the requested window is frontmost",
    )])


class DesktopGateway(PluginGateway):
    """`PluginGateway` plus canonical verification. `invoke()` is inherited
    verbatim, so the Desktop execution path is provably unchanged."""

    def verify(
        self,
        capability: str,
        payload: dict[str, Any],
        expected: ExpectedOutcome,
    ) -> Evidence | None:
        effective = bind_for_environment(
            capability=capability,
            payload=payload,
            description=expected.description,
        )
        if effective is None:
            # No generic read-only postcondition exists for this capability
            # (clicks, keypresses, arbitrary commands, and the query
            # capabilities). Saying so is the truthful answer; inventing a
            # verdict is the failure being removed.
            return None

        return _DesktopStateVerifier(
            application=_application_of(payload),
            title=_title_of(payload),
        ).verify(effective)
