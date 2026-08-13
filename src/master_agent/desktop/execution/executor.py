"""C26 · `DesktopExecutor` — the unified API, and the one place every
operation is checked against an existing Operation Profile before it runs.

```
   DesktopExecutor.execute() / .focus() / .type() / .click() / .wait() / .close()
              │
              ▼
   DesktopExecutiveV2.profile(application)   ← C25, never bypassed
              │
              ▼
   WindowManager · KeyboardController · MouseController · ProcessExecutive
```

**"Every operation routes through existing Desktop Executive profiles.
Never bypass them"** is this class's one governing rule, and it is
mechanical: every method that names an `application` looks it up through
`DesktopExecutiveV2.profile()` (C25) first, and refuses — with a
structured `ExecutionResult`, never an exception — if the Desktop
Executive has no profile for it. C25's own brief made this the point of
building profiles at all: *"No future module may encode
application-specific behavior outside the Desktop Executive."* This class
is the first module that could have violated that, by clicking and typing
into an application it knows nothing about, and it is built specifically
so that it cannot.

## What this class is not

It is not a planner. It does not decide *what* to type, *where* to click,
or *which* application to use — `DesktopExecutiveV2.recommend()` (C25)
already answers the third question and this class does not repeat that
logic. It executes exactly what it is told, per the brief's own
philosophy: *"It should execute exactly what Kalpavriksha requests.
Nothing more. Nothing less."* Kalpavriksha — the orchestrator that
decides — does not exist yet in this repository; this is the substrate a
future brief wires it to.
"""
from __future__ import annotations

from master_agent.desktop.actions import DesktopContext
from master_agent.desktop.execution.browser import BrowserExecutive
from master_agent.desktop.execution.clipboard import ClipboardExecutive
from master_agent.desktop.execution.keyboard import KeyboardController
from master_agent.desktop.execution.mouse import MouseController
from master_agent.desktop.execution.process import ProcessExecutive
from master_agent.desktop.execution.window import WindowManager
from master_agent.desktop.operations import AutomationStrategy, DesktopExecutiveV2
from master_agent.desktop.probe import RealSystemProbe
from master_agent.executor.action import ExecutionResult


class DesktopExecutor:
    """Composes every C26 component over one `DesktopContext` and one
    `DesktopExecutiveV2`, so a caller never has to wire six objects
    together to ask for one operation.
    """

    def __init__(
        self,
        *,
        context: DesktopContext | None = None,
        desktop_executive: DesktopExecutiveV2 | None = None,
        window_manager: WindowManager | None = None,
        keyboard: KeyboardController | None = None,
        mouse: MouseController | None = None,
        clipboard: ClipboardExecutive | None = None,
        process: ProcessExecutive | None = None,
        browser: BrowserExecutive | None = None,
    ) -> None:
        self._context = context or DesktopContext(RealSystemProbe())
        self._executive = desktop_executive or DesktopExecutiveV2()
        self.windows = window_manager or WindowManager()
        self.clipboard = clipboard or ClipboardExecutive()
        self.keyboard = keyboard or KeyboardController(clipboard=self.clipboard)
        self.mouse = mouse or MouseController()
        self.process = process or ProcessExecutive(
            context=self._context, knowledge_base=self._executive.knowledge_base
        )
        self.browser = browser or BrowserExecutive(
            window_manager=self.windows, desktop_context=self._context
        )

    # ---- the profile gate ------------------------------------------------

    def _profile_or_refusal(self, application: str):
        """The one check every named-application method runs first.
        Returns the profile, or an `ExecutionResult` refusal a caller
        returns verbatim — never raises, matching every other failure in
        this package.
        """
        profile = self._executive.profile(application)
        if profile is None:
            return ExecutionResult(
                success=False,
                errors=[
                    f"{application!r} has no Desktop Executive operation profile; an application the Desktop Executive does not know cannot be operated through this door"
                ],
            )
        return profile

    def _require_automatable(self, application: str):
        """Like `_profile_or_refusal`, and additionally refuses an
        application whose profile names no automation surface at all
        (`AutomationStrategy.NOT_AUTOMATABLE`) — C25's own knowledge,
        consulted rather than re-derived."""
        outcome = self._profile_or_refusal(application)
        if isinstance(outcome, ExecutionResult):
            return outcome
        if outcome.automation_strategy is AutomationStrategy.NOT_AUTOMATABLE:
            return ExecutionResult(
                success=False,
                errors=[
                    f"{application!r}'s operation profile names no automation surface (automation_strategy: {outcome.automation_strategy.value})"
                ],
            )
        return outcome

    # ---- the unified API, per the brief's own six names -------------------

    def execute(self, application: str) -> ExecutionResult:
        """Launch `application`, per its own profile."""
        outcome = self._profile_or_refusal(application)
        if isinstance(outcome, ExecutionResult):
            return outcome
        # `outcome` (the profile) already ties 1:1 to
        # `catalog.ApplicationSpec.key` (`operations/types.py`'s own
        # docstring on `ApplicationOperationProfile`) — `outcome.key` is
        # the resolved catalog key without this module needing its own
        # import of `desktop.catalog` (Architecture Rules: no second
        # catalog scanner/resolver — `_profile_or_refusal` already did
        # this resolution).
        #
        # Universal Windows Environment Discovery (Section 7): launch
        # resolution comes from the normalized inventory record's own
        # `launch_target`, already ranked by evidence strength in
        # `inventory.py::_resolve_one` (Start Menu/AppUserModel > MSIX >
        # a verified catalog path). `inventory()` is cache-first, so
        # `deep=True` (its default) only pays the multi-source scan's
        # real cost once per process lifetime, not on every launch — the
        # same reasoning `read_versions=False` already applies to the
        # per-app version probe specifically.
        inventory = self._context.inventory(read_versions=False)
        installed_app = inventory.get(outcome.key) or inventory.get(application)
        launch_target = installed_app.launch_target if installed_app else None
        if launch_target and launch_target.lower().startswith("shell:appsfolder"):
            # The one case the existing, frozen `LaunchApplicationAction`
            # (`desktop/actions.py`) cannot express on its own: it starts
            # `[installed_app.path]` as a single command, and
            # `explorer.exe shell:AppsFolder\<id>` is two arguments.
            # Every other case (a verified exe path, or a raw path Start
            # Menu itself reported for a legacy shortcut) already *is*
            # `installed_app.path`, so the fallback below already
            # launches it correctly without this method repeating that
            # logic.
            result = self._context.probe.start(["explorer.exe", launch_target])
            if result.ok:
                return ExecutionResult(success=True, output=f"Launched {application}")
            return ExecutionResult(success=False, errors=[result.error])
        # Fall back to the existing profile-based launch
        return self.process.launch(application)

    def focus(self, application: str) -> ExecutionResult:
        """Bring `application`'s window to the front. Reuses
        `desktop.inventory`'s own process attribution and `WindowManager
        .focus_process` — the same composition `BrowserExecutive
        .focus_browser` uses, since bringing a window forward is the same
        operation whether the application is a browser or not."""
        outcome = self._profile_or_refusal(application)
        if isinstance(outcome, ExecutionResult):
            return outcome
        running = self._context.refresh(read_versions=False, deep=False).running(application)
        if not running:
            return ExecutionResult(success=False, errors=[f"{application} is not running"])
        pids = frozenset(p.pid for p in running)
        return self.windows.focus_process(pids)

    def type(self, application: str, text: str) -> ExecutionResult:
        """Type `text`, after confirming `application` can be automated."""
        outcome = self._require_automatable(application)
        if isinstance(outcome, ExecutionResult):
            return outcome
        return self.keyboard.type(text)

    def click(self, application: str, x: int, y: int, button: str = "left") -> ExecutionResult:
        """Click at `(x, y)`, after confirming `application` can be
        automated. The coordinate is the caller's decision — this method
        performs no image recognition and locates nothing on its own."""
        outcome = self._require_automatable(application)
        if isinstance(outcome, ExecutionResult):
            return outcome
        return self.mouse.click(x, y, button)

    def wait(self, application: str, timeout_seconds: float | None = None) -> ExecutionResult:
        """Wait for `application` to report running. See `process.py` for
        why this is a process-level, not a window-level, readiness
        signal."""
        outcome = self._profile_or_refusal(application)
        if isinstance(outcome, ExecutionResult):
            return outcome
        return self.process.wait(application, timeout_seconds=timeout_seconds)

    def close(self, application: str) -> ExecutionResult:
        """Terminate `application`, via the existing
        `CloseApplicationAction` (`IRREVERSIBLE`, per ADR-0009)."""
        outcome = self._profile_or_refusal(application)
        if isinstance(outcome, ExecutionResult):
            return outcome
        return self.process.terminate(application)