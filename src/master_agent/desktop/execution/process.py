"""C26 · Process Executive — `launch()`, `wait()`, `terminate()`,
`restart()`, `is_running()`.

**Extends the existing Desktop Executive; never duplicates it.** Four of
these five operations already exist as `Action`s in `desktop/actions.py`
(Mission Brief 030) — `launch()` is `LaunchApplicationAction`,
`terminate()` is `CloseApplicationAction`, `is_running()` is
`IsRunningAction` — and this class calls those Actions' own
`validate()`/`run()` directly rather than re-implementing what launching
or killing a process means. Reusing the Action objects also means every
existing guarantee travels for free: `LaunchApplicationAction` only
launches a catalogued, installed application; `CloseApplicationAction` is
the one that kills by PID, `IRREVERSIBLE` per ADR-0009 for the reason its
own docstring gives.

**`wait()` is the one genuinely new primitive.** C25's own
`ApplicationOperationProfile.wait_until_ready` describes *in prose* what a
trained operator would watch for; nothing before this brief could actually
wait. Lacking OCR or vision (both forbidden), the only reliable,
deterministic signal available here is **process-level readiness** —
`is_running()` becoming true — so that is what `wait()` polls for. It
reuses C25's `startup_time` estimate as a sensible default timeout rather
than inventing a second number, which is the reuse the Architecture Rules
ask for (*"Reuse: Desktop Executive, Operation Profiles… Never
duplicate"*), and is honest about the ceiling: a process that is running
but whose window has not finished loading is a different, unobservable
fact from here.
"""
from __future__ import annotations

import time
from collections.abc import Callable

from master_agent.desktop.actions import (
    CloseApplicationAction,
    DesktopContext,
    IsRunningAction,
    LaunchApplicationAction,
)
from master_agent.desktop.operations import DesktopExecutiveV2, OperationKnowledgeBase
from master_agent.desktop.probe import RealSystemProbe
from master_agent.executor.action import Action, ExecutionResult

#: Used only when no C25 profile is available to estimate from — every
#: profiled application already carries a better number of its own.
DEFAULT_TIMEOUT_SECONDS = 30.0

DEFAULT_POLL_INTERVAL_SECONDS = 0.5


def _run(action_cls: type[Action], context: DesktopContext, **parameters: object) -> ExecutionResult:
    """Validate then run one existing Desktop Executive `Action`,
    unchanged. The one seam every method in this file goes through."""
    action = action_cls(context)
    errors = action.validate(parameters)
    if errors:
        return ExecutionResult(success=False, errors=errors)
    return action.run(parameters)


class ProcessExecutive:
    __slots__ = ("_context", "_executive", "_sleep")

    def __init__(
        self,
        context: DesktopContext | None = None,
        knowledge_base: OperationKnowledgeBase | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._context = context or DesktopContext(RealSystemProbe())
        self._executive = (
            DesktopExecutiveV2(knowledge_base)
            if knowledge_base is not None
            else DesktopExecutiveV2()
        )
        self._sleep = sleep

    def launch(self, application: str) -> ExecutionResult:
        return _run(LaunchApplicationAction, self._context, application=application)

    def is_running(self, application: str) -> ExecutionResult:
        return _run(IsRunningAction, self._context, application=application)

    def terminate(self, application: str) -> ExecutionResult:
        return _run(CloseApplicationAction, self._context, application=application)

    def restart(self, application: str) -> ExecutionResult:
        """Terminate, then launch. An application that was not running is
        not a reason to refuse the launch half — restarting something
        that is already stopped is still a sensible request."""
        terminated = self.terminate(application)
        not_running = terminated.errors == [f"{application} is not running"] or any(
            "is not running" in e for e in terminated.errors
        )
        if not terminated.success and not not_running:
            return terminated

        launched = self.launch(application)
        return ExecutionResult(
            success=launched.success,
            output={"terminated": terminated.success, "launch": launched.output},
            errors=launched.errors,
            warnings=[] if terminated.success or not_running else terminated.errors,
        )

    def wait(
        self,
        application: str,
        timeout_seconds: float | None = None,
        poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
    ) -> ExecutionResult:
        """Poll `is_running()` until it is true or `timeout_seconds`
        elapses. See the module docstring for why process-level readiness
        is the ceiling of what this method can honestly observe."""
        if timeout_seconds is None:
            profile = self._executive.profile(application)
            timeout_seconds = (
                float(profile.startup_time.typical_seconds[1])
                if profile is not None
                else DEFAULT_TIMEOUT_SECONDS
            )

        elapsed = 0.0
        while True:
            check = self.is_running(application)
            if check.success and check.output.get("running"):
                return ExecutionResult(
                    success=True,
                    output={"application": application, "waited_seconds": elapsed},
                )
            if elapsed >= timeout_seconds:
                return ExecutionResult(
                    success=False,
                    errors=[
                        (
                            f"{application} did not report running within "
                            f"{timeout_seconds}s"
                        )
                    ],
                )
            self._sleep(poll_interval_seconds)
            elapsed += poll_interval_seconds
