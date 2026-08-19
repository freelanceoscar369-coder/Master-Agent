"""DesktopGateway -- canonical Evidence for the Desktop Executive.

## What this is, and is not

It is **not** a second Desktop implementation. It subclasses
`PluginGateway` and overrides exactly one method, `verify()`. Execution is
inherited untouched, so every capability still runs the way it runs today:

    MissionControl -> DesktopPlugin -> the registered Action
                   -> DesktopExecutor / DesktopExecutiveV2
                   -> Process / Window / Keyboard / Mouse / UIA

Nothing here launches, clicks, types, focuses or closes anything. The one
thing missing was the adapter between the Desktop Executive and the
canonical `verification.Evidence` contract, and that is all this adds.

## Why only some capabilities

`ExecutionResult.success` is the Action's claim about its own work, and
ADR-0011 exists so completion never rests on a claim like that. So a
capability is verifiable here only where the Desktop package already
offers a **read-only** way to re-observe the fact afterwards:

* `ProcessExecutive.is_running` -- which processes an application has
* `WindowManager.active` -- which window is frontmost, and whose it is

Where no such generic postcondition exists -- a click, a keypress, an
arbitrary shell command -- this returns `None`, which says "not
established" rather than inventing a verdict.

## Three corrections that this file exists in its current form because of

1. **`bool(probe.output)` is always True.** `IsRunningAction` returns
   `{"application": ..., "running": bool, "processes": [...]}` -- a dict
   that is never empty, so truthiness of the container said "running"
   even when `running` was `False`. `launch_application` would have
   verified MATCHED unconditionally: a fabricated pass, which is the
   exact failure this whole line of work removes. The published `running`
   field is read now, and an observation that could not be taken is
   `None` (unknown), never `False`.

2. **`WindowManager()` defaults to `NullWindowBackend`.** A verifier built
   that way observes nothing on a real desktop. The production
   `Win32WindowBackend` -- the same one `actions_interaction` uses -- is
   passed explicitly.

3. **A window title need not contain its application's name.** Matching
   `"notepad" in str(active_window)` is a guess, and it is wrong in both
   directions: a document window may not name its app, and an unrelated
   window may mention it. Ownership is the authoritative relationship, and
   `WindowManager.locate_by_process` already exists for exactly this --
   "an exact match instead of a title guess", in its own words. Foreground
   is verified by comparing the active window's `process_id` against the
   freshly observed process ids of the requested application.
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
#: Capabilities whose effect is that the requested application owns the
#: frontmost window.
_WINDOW_FOREGROUND = frozenset({"focus_window", "bring_to_front"})

#: `close_window` is deliberately NOT here.
#:
#: The Step payload names an *application*; execution resolves an actual
#: window handle internally. Afterwards -- without reading the Action's
#: own report, which is the one thing Verification may not do -- there is
#: no way to tell "the intended window was closed while another window of
#: the same application remains" from "the intended window is still open".
#: Both look like "this application still has windows".
#:
#: Claiming support anyway would mean a verdict that is right by accident
#: for single-window applications and silently wrong otherwise. Saying the
#: capability is not generically verifiable is the truthful answer; making
#: it verifiable is an observation-subject question for the Step contract,
#: not something to paper over here.


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
    )


def _application_of(payload: dict[str, Any]) -> str:
    for key in ("application", "app", "name", "target"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _running_from(probe: Any) -> tuple[bool | None, frozenset[int]]:
    """`(is_running, process_ids)` from an `is_running` observation.

    `None` means *could not be observed* and is never collapsed into
    `False`: "the application is not running" and "I could not find out"
    are different facts, and only the first is evidence of a successful
    close.
    """
    if probe is None or not getattr(probe, "success", False):
        return None, frozenset()

    output = getattr(probe, "output", None)
    if not isinstance(output, dict) or "running" not in output:
        # A shape this code does not understand is an unreadable
        # observation, not a negative one.
        return None, frozenset()

    pids = {
        entry["pid"]
        for entry in (output.get("processes") or [])
        if isinstance(entry, dict) and isinstance(entry.get("pid"), int)
    }
    return bool(output["running"]), frozenset(pids)


class _DesktopStateVerifier(Verifier):
    """Re-observes process and window state through the Desktop package's
    own read-only APIs. Never touches the Action's report.

    `processes` and `windows` are injectable so this can be driven
    deterministically in tests without a real desktop; left unset it uses
    the production implementations.
    """

    worker_name = "desktop"
    environment_name = "windows_desktop"

    def __init__(
        self,
        application: str,
        processes: Any = None,
        windows: Any = None,
    ) -> None:
        self._application = application
        self._processes = processes
        self._windows = windows

    def _process_executive(self) -> Any:
        if self._processes is not None:
            return self._processes
        from master_agent.desktop.execution.process import ProcessExecutive

        return ProcessExecutive()

    def _window_manager(self) -> Any:
        if self._windows is not None:
            return self._windows
        from master_agent.desktop.execution.win32_backends import Win32WindowBackend
        from master_agent.desktop.execution.window import WindowManager

        # Explicit backend. `WindowManager()` alone falls back to
        # `NullWindowBackend`, which observes nothing on a real desktop --
        # a verifier that would have reported no window under every
        # condition.
        return WindowManager(Win32WindowBackend())

    def capture_observation_dict(self) -> dict[str, Any]:
        process_running: bool | None = None
        application_pids: frozenset[int] = frozenset()
        if self._application:
            process_running, application_pids = _running_from(
                self._process_executive().is_running(self._application)
            )

        active_process_id: int | None = None
        foreground_owned_by_application: bool | None = None
        active = self._window_manager().active()
        if getattr(active, "success", False) and isinstance(active.output, dict):
            candidate = active.output.get("process_id")
            if isinstance(candidate, int):
                active_process_id = candidate

        # Ownership, not a title guess. Unknown when either half of the
        # comparison could not be observed.
        if active_process_id is not None and process_running is not None:
            foreground_owned_by_application = active_process_id in application_pids

        return {
            "application": self._application,
            "process_running": process_running,
            "application_process_ids": sorted(application_pids),
            "active_process_id": active_process_id,
            "foreground_owned_by_application": foreground_owned_by_application,
        }


def bind_for_environment(
    capability: str,
    payload: dict[str, Any],
    description: str,
) -> ExpectedOutcome | None:
    """The Planner's claim, expressed as checks the desktop can answer."""
    if not supports(capability):
        return None

    application = _application_of(payload)

    if _in(capability, _PROCESS_PRESENT):
        return ExpectedOutcome(description=description, checks=[ObservationCheck(
            field="process_running", operator="equals", value=True,
            description=f"'{application}' has at least one running process",
        )])

    if _in(capability, _PROCESS_ABSENT):
        return ExpectedOutcome(description=description, checks=[ObservationCheck(
            field="process_running", operator="equals", value=False,
            description=f"'{application}' has no running process",
        )])

    return ExpectedOutcome(description=description, checks=[ObservationCheck(
        field="foreground_owned_by_application", operator="equals", value=True,
        description=(
            f"the frontmost window belongs to a process of '{application}'"
        ),
    )])


class DesktopGateway(PluginGateway):
    """`PluginGateway` plus canonical verification. `invoke()` is inherited
    verbatim, so the Desktop execution path is provably unchanged."""

    def __init__(
        self,
        plugin: Any,
        grant_permission: Any = None,
        processes: Any = None,
        windows: Any = None,
    ) -> None:
        super().__init__(plugin, grant_permission)
        # Injection points for deterministic tests. Production leaves both
        # unset and the verifier builds the real read-only observers.
        self._processes = processes
        self._windows = windows

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
            # (clicks, keypresses, arbitrary commands, close_window, and
            # the query capabilities). Saying so is the truthful answer;
            # inventing a verdict is the failure being removed.
            return None

        return _DesktopStateVerifier(
            application=_application_of(payload),
            processes=self._processes,
            windows=self._windows,
        ).verify(effective)
