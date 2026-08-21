"""Elite Desktop Executive — the authored knowledge itself.

One entry per catalogued application, in `catalog.py`'s own key
vocabulary and its own order. **This is where the module earns the word
"elite":** not a new scanner, not a new capability — the trained-operator
knowledge the current Desktop Executive never had to write down because
Mission Brief 030 stopped at *"discover, launch, close, inspect."*

## Scope: the nineteen applications the Desktop Executive already knows

The brief's own worked examples name fifteen applications, four of which —
Brave, Office, Explorer, Terminal — have no entry in `desktop/catalog.py`.
**No profile is authored for them.** Inventing one would mean this module
claims operational knowledge about software the Desktop Executive cannot
even detect, which is a second catalogue in the costume of a knowledge
base — exactly what `environment_intelligence`'s own `uncatalogued` tuple
(C22) already refuses to do for the same reason. `UNPROFILED_EXAMPLES`
records the four names so the gap is stated, not silently absent, and
`test_completeness_and_gaps.py`'s tests assert every one of the fifteen
named examples is either profiled or listed there — nothing falls through
uncounted.

## Why some data is generated rather than hand-written per application

Eight of the nineteen — `git`, `python`, `node`, `docker`, `wsl`,
`powershell`, `java`, `playwright` — are pure command-line tools with no
window of their own. Writing eight near-identical hand-authored recovery
plans would not be eight pieces of knowledge; it would be one piece of
knowledge, copy-pasted eight times, which is the duplication this whole
project has refused everywhere else. `_cli_recovery_plan()` is that one
piece of knowledge, parameterised, and every one of the eight calls it
with the facts that actually differ (the label, and the one or two things
that genuinely vary — Docker's daemon, WSL's virtual machine). The eleven
GUI or service applications are each authored individually, because their
failure surfaces genuinely differ from each other and from the CLI eight.
"""
from __future__ import annotations

from master_agent.desktop.operations.types import (
    ApplicationOperationProfile,
    ApplicationRecoveryPlan,
    AutomationStrategy,
    Capability,
    DesktopCapabilityMatrix,
    FailureMode,
    LaunchMethod,
    OperationNote,
    RecoveryApproach,
    RecoveryGuidance,
    StartupEstimate,
    StartupSpeed,
    WindowStrategy,
    Workflow,
    WorkflowStep,
    WorkflowVerb,
)

#: The brief's own worked examples that the Desktop Executive's catalog
#: does not know. See the module docstring — no profile is invented for
#: these; they are named so the gap is a fact, not an omission.
UNPROFILED_EXAMPLES: tuple[str, ...] = ("brave", "office", "explorer", "terminal")


# ═══════════════════════ shared recovery knowledge ════════════════════════


def _na(reason: str) -> RecoveryGuidance:
    """A failure mode that does not plausibly apply to this class of
    application. Documented, not omitted — see `types.py`'s
    `RecoveryGuidance.applicable`."""
    return RecoveryGuidance(diagnosis=reason, guidance=("no action: this failure mode does not apply here",), applicable=False)


def _cli_recovery_plan(
    key: str,
    label: str,
    *,
    network_note: str = (
        "the command depends on network access it does not have; check "
        "connectivity and retry"
    ),
    hung_note: str | None = None,
) -> ApplicationRecoveryPlan:
    """The one CLI recovery shape, parameterised. See the module docstring
    for why this is generated rather than hand-duplicated eight times."""
    return ApplicationRecoveryPlan(
        key=key,
        guidance=(
            (
                FailureMode.NOT_RUNNING,
                RecoveryGuidance(
                    diagnosis=f"{label} is not a background process; 'not running' means the "
                    "command has not been invoked in this session, not a fault.",
                    guidance=(f"invoke {label} in a terminal when it is needed",),
                ),
            ),
            (FailureMode.WINDOW_HIDDEN, _na(f"{label} has no window of its own; it runs inside whichever terminal invoked it.")),
            (
                FailureMode.LOADING,
                RecoveryGuidance(
                    diagnosis=f"{label} is still executing the requested command.",
                    guidance=("wait for the command to return; long-running commands are normal for this class of tool",),
                ),
            ),
            (
                FailureMode.HUNG,
                RecoveryGuidance(
                    diagnosis=hung_note or f"{label} has stopped producing output and has not returned.",
                    guidance=(
                        "check whether the command is waiting on stdin (some CLIs block for input)",
                        "if genuinely stuck, interrupt the process (Ctrl-C) and re-run",
                    ),
                ),
            ),
            (
                FailureMode.MULTIPLE_INSTANCES,
                RecoveryGuidance(
                    diagnosis=f"more than one {label} invocation is running concurrently.",
                    guidance=("this is ordinary for a CLI tool; identify the specific process by its arguments or working directory before acting on any one of them",),
                ),
            ),
            (FailureMode.LOGIN_REQUIRED, _na(f"{label} itself does not gate on an interactive login (any credential a specific subcommand needs is that subcommand's own concern, not this tool's).")),
            (FailureMode.UNEXPECTED_POPUP, _na(f"{label} is a command-line tool; it has no window to raise a popup in.")),
            (
                FailureMode.NETWORK_FAILURE,
                RecoveryGuidance(diagnosis=network_note, guidance=("check network connectivity", "retry the command")),
            ),
        ),
    )


# ═══════════════════════ 1 · profiles ════════════════════════════════════

PROFILES: tuple[ApplicationOperationProfile, ...] = (
    # ---- developer tooling ----
    ApplicationOperationProfile(
        key="python",
        launch=OperationNote("Invoked as a command in an already-open terminal — `python` or `python3`.", "There is no separate 'Python application' to launch."),
        focus=OperationNote("Not applicable; focus belongs to the hosting terminal window."),
        close=OperationNote("The interpreter exits when its script or REPL session ends, or the hosting terminal closes."),
        wait_until_ready=OperationNote("Ready the moment the process starts; a REPL prints its own prompt as the readiness signal."),
        health_check=OperationNote("The interpreter responds to `--version` with a version string."),
        recover=OperationNote("Re-invoke the command; there is no process to restart independently of the command that started it."),
        known_failure_modes=(FailureMode.NOT_RUNNING, FailureMode.LOADING, FailureMode.HUNG, FailureMode.MULTIPLE_INSTANCES, FailureMode.NETWORK_FAILURE),
        startup_time=StartupEstimate(StartupSpeed.INSTANT, (0, 1), "interpreter start-up; a script's own work is separate"),
        preferred_launch_method=LaunchMethod.SHELL_INVOCATION,
        window_strategy=WindowStrategy.TERMINAL_HOSTED,
        automation_strategy=AutomationStrategy.CLI_INVOCATION,
        recovery_approach=RecoveryApproach.WAIT_AND_RETRY,
    ),
    ApplicationOperationProfile(
        key="git",
        launch=OperationNote("Invoked as a command — `git <subcommand>` — in an already-open terminal."),
        focus=OperationNote("Not applicable; focus belongs to the hosting terminal window."),
        close=OperationNote("Each invocation exits on its own when the subcommand completes."),
        wait_until_ready=OperationNote("Ready immediately; a git subcommand either returns or reports an error."),
        health_check=OperationNote("Responds to `git --version` with a version string."),
        recover=OperationNote("Re-invoke the failed subcommand once the underlying condition (a lock file, a network path) is resolved."),
        known_failure_modes=(FailureMode.NOT_RUNNING, FailureMode.HUNG, FailureMode.MULTIPLE_INSTANCES, FailureMode.NETWORK_FAILURE),
        startup_time=StartupEstimate(StartupSpeed.INSTANT, (0, 1)),
        preferred_launch_method=LaunchMethod.SHELL_INVOCATION,
        window_strategy=WindowStrategy.TERMINAL_HOSTED,
        automation_strategy=AutomationStrategy.CLI_INVOCATION,
        recovery_approach=RecoveryApproach.WAIT_AND_RETRY,
    ),
    ApplicationOperationProfile(
        key="node",
        launch=OperationNote("Invoked as `node <script>` or as a bare REPL in an already-open terminal."),
        focus=OperationNote("Not applicable; focus belongs to the hosting terminal window."),
        close=OperationNote("Exits when the script or REPL session ends, or the hosting terminal closes."),
        wait_until_ready=OperationNote("Ready the moment the process starts."),
        health_check=OperationNote("Responds to `node --version` with a version string."),
        recover=OperationNote("Re-invoke the command; a hung script is interrupted and re-run."),
        known_failure_modes=(FailureMode.NOT_RUNNING, FailureMode.LOADING, FailureMode.HUNG, FailureMode.MULTIPLE_INSTANCES, FailureMode.NETWORK_FAILURE),
        startup_time=StartupEstimate(StartupSpeed.INSTANT, (0, 1)),
        preferred_launch_method=LaunchMethod.SHELL_INVOCATION,
        window_strategy=WindowStrategy.TERMINAL_HOSTED,
        automation_strategy=AutomationStrategy.CLI_INVOCATION,
        recovery_approach=RecoveryApproach.WAIT_AND_RETRY,
    ),
    ApplicationOperationProfile(
        key="vscode",
        launch=OperationNote("Started from the Start Menu / Dock, from a known install path, or via its own `code` CLI (`code .` opens the current folder)."),
        focus=OperationNote("Click its taskbar entry, or bring the existing window to the front; a second launch with the same folder focuses rather than duplicates."),
        close=OperationNote("Close the window; unsaved files prompt to save first."),
        wait_until_ready=OperationNote("The window title shows the open folder/file and the editor pane accepts focus.", "Extension activation can continue briefly after the window itself is usable."),
        health_check=OperationNote("The main window is present and responds to focus; the status bar shows no persistent error banner."),
        recover=OperationNote("Close and relaunch; a genuinely frozen window is ended and relaunched with the same folder."),
        known_failure_modes=(FailureMode.NOT_RUNNING, FailureMode.WINDOW_HIDDEN, FailureMode.LOADING, FailureMode.HUNG, FailureMode.MULTIPLE_INSTANCES, FailureMode.UNEXPECTED_POPUP),
        startup_time=StartupEstimate(StartupSpeed.MODERATE, (2, 6), "slower on first launch after an update, while extensions activate"),
        preferred_launch_method=LaunchMethod.EXECUTABLE_ON_PATH,
        window_strategy=WindowStrategy.SINGLE_INSTANCE_MULTI_WINDOW,
        automation_strategy=AutomationStrategy.DESKTOP_EXECUTIVE_WINDOW_CONTROL,
        recovery_approach=RecoveryApproach.RESTART_APPLICATION,
    ),
    ApplicationOperationProfile(
        key="cursor",
        launch=OperationNote("Started from a known install path, or via its own `cursor` CLI."),
        focus=OperationNote("Bring the existing window to the front; a second launch on the same workspace focuses rather than duplicates, mirroring VS Code (Cursor is a VS Code fork)."),
        close=OperationNote("Close the window; unsaved files prompt to save first."),
        wait_until_ready=OperationNote("The window title shows the open workspace and the editor pane accepts focus."),
        health_check=OperationNote("The main window is present and responds to focus."),
        recover=OperationNote("Close and relaunch."),
        known_failure_modes=(FailureMode.NOT_RUNNING, FailureMode.WINDOW_HIDDEN, FailureMode.LOADING, FailureMode.HUNG, FailureMode.MULTIPLE_INSTANCES, FailureMode.LOGIN_REQUIRED, FailureMode.NETWORK_FAILURE),
        startup_time=StartupEstimate(StartupSpeed.MODERATE, (2, 6)),
        preferred_launch_method=LaunchMethod.KNOWN_INSTALL_PATH,
        window_strategy=WindowStrategy.SINGLE_INSTANCE_MULTI_WINDOW,
        automation_strategy=AutomationStrategy.DESKTOP_EXECUTIVE_WINDOW_CONTROL,
        recovery_approach=RecoveryApproach.RESTART_APPLICATION,
    ),
    ApplicationOperationProfile(
        key="notepad",
        launch=OperationNote("Started from `%WINDIR%\\system32\\notepad.exe`; always available on Windows."),
        focus=OperationNote("Bring the existing window to the front; a second launch opens a new window rather than focusing (modern Notepad is multi-instance)."),
        close=OperationNote("Close the window; unsaved text prompts to save first."),
        wait_until_ready=OperationNote("The window is present and its edit area accepts focus — near-instant, no extension/workspace loading."),
        health_check=OperationNote("The main window is present and responds to focus."),
        recover=OperationNote("Close and relaunch."),
        known_failure_modes=(FailureMode.NOT_RUNNING, FailureMode.WINDOW_HIDDEN, FailureMode.MULTIPLE_INSTANCES),
        startup_time=StartupEstimate(StartupSpeed.FAST, (1, 2)),
        preferred_launch_method=LaunchMethod.KNOWN_INSTALL_PATH,
        window_strategy=WindowStrategy.SINGLE_INSTANCE_MULTI_WINDOW,
        automation_strategy=AutomationStrategy.DESKTOP_EXECUTIVE_WINDOW_CONTROL,
        recovery_approach=RecoveryApproach.RESTART_APPLICATION,
    ),
    ApplicationOperationProfile(
        key="visualstudio",
        launch=OperationNote("Started from the Start Menu or a known install path (`devenv.exe`)."),
        focus=OperationNote("Bring the existing window to the front."),
        close=OperationNote("Close the window; unsaved files and a running debug session prompt first."),
        wait_until_ready=OperationNote("The solution has finished loading and the editor accepts focus.", "Large solutions can take noticeably longer than the window's own appearance suggests."),
        health_check=OperationNote("The main window is present and the status bar shows no persistent 'loading' state."),
        recover=OperationNote("Close and relaunch; reopen the last solution."),
        known_failure_modes=(FailureMode.NOT_RUNNING, FailureMode.WINDOW_HIDDEN, FailureMode.LOADING, FailureMode.HUNG, FailureMode.MULTIPLE_INSTANCES, FailureMode.UNEXPECTED_POPUP),
        startup_time=StartupEstimate(StartupSpeed.SLOW, (5, 20), "large solutions load noticeably slower"),
        preferred_launch_method=LaunchMethod.KNOWN_INSTALL_PATH,
        window_strategy=WindowStrategy.SINGLE_INSTANCE_MULTI_WINDOW,
        automation_strategy=AutomationStrategy.DESKTOP_EXECUTIVE_WINDOW_CONTROL,
        recovery_approach=RecoveryApproach.RESTART_APPLICATION,
    ),
    # ---- browsers ----
    ApplicationOperationProfile(
        key="chrome",
        launch=OperationNote("Started from the Start Menu, a known install path, or the `chrome`/`google-chrome` executable on PATH."),
        focus=OperationNote("Bring the existing window to the front; a new tab is opened in the running instance rather than a second window in the ordinary case."),
        close=OperationNote("Close the window; a founder is prompted only if multiple tabs are open and the setting to warn is on."),
        wait_until_ready=OperationNote("The window is present and the address bar accepts focus.", "A specific page's own readiness is a navigation concern, not a launch concern."),
        health_check=OperationNote("The window is present and responds to focus; no persistent 'Aw, Snap!' error page."),
        recover=OperationNote("Close and relaunch; a genuinely hung renderer is ended via the browser's own task manager or the process is killed and the browser relaunched."),
        known_failure_modes=(FailureMode.NOT_RUNNING, FailureMode.WINDOW_HIDDEN, FailureMode.LOADING, FailureMode.HUNG, FailureMode.MULTIPLE_INSTANCES, FailureMode.LOGIN_REQUIRED, FailureMode.UNEXPECTED_POPUP, FailureMode.NETWORK_FAILURE),
        startup_time=StartupEstimate(StartupSpeed.FAST, (1, 3), "slower with many extensions or a cold profile"),
        preferred_launch_method=LaunchMethod.EXECUTABLE_ON_PATH,
        window_strategy=WindowStrategy.TABBED_SINGLE_WINDOW,
        automation_strategy=AutomationStrategy.BROWSER_WORKER,
        recovery_approach=RecoveryApproach.RESTART_APPLICATION,
    ),
    ApplicationOperationProfile(
        key="edge",
        launch=OperationNote("Started from the Start Menu, a known install path, or the `msedge` executable on PATH."),
        focus=OperationNote("Bring the existing window to the front; a new tab is opened in the running instance."),
        close=OperationNote("Close the window."),
        wait_until_ready=OperationNote("The window is present and the address bar accepts focus."),
        health_check=OperationNote("The window is present and responds to focus."),
        recover=OperationNote("Close and relaunch."),
        known_failure_modes=(FailureMode.NOT_RUNNING, FailureMode.WINDOW_HIDDEN, FailureMode.LOADING, FailureMode.HUNG, FailureMode.MULTIPLE_INSTANCES, FailureMode.LOGIN_REQUIRED, FailureMode.UNEXPECTED_POPUP, FailureMode.NETWORK_FAILURE),
        startup_time=StartupEstimate(StartupSpeed.FAST, (1, 3)),
        preferred_launch_method=LaunchMethod.KNOWN_INSTALL_PATH,
        window_strategy=WindowStrategy.TABBED_SINGLE_WINDOW,
        automation_strategy=AutomationStrategy.BROWSER_WORKER,
        recovery_approach=RecoveryApproach.RESTART_APPLICATION,
    ),
    ApplicationOperationProfile(
        key="firefox",
        launch=OperationNote("Started from the Start Menu, a known install path, or the `firefox` executable on PATH."),
        focus=OperationNote("Bring the existing window to the front; a new tab is opened in the running instance."),
        close=OperationNote("Close the window; a founder is prompted if configured to warn on multiple tabs."),
        wait_until_ready=OperationNote("The window is present and the address bar accepts focus."),
        health_check=OperationNote("The window is present and responds to focus."),
        recover=OperationNote("Close and relaunch."),
        known_failure_modes=(FailureMode.NOT_RUNNING, FailureMode.WINDOW_HIDDEN, FailureMode.LOADING, FailureMode.HUNG, FailureMode.MULTIPLE_INSTANCES, FailureMode.LOGIN_REQUIRED, FailureMode.UNEXPECTED_POPUP, FailureMode.NETWORK_FAILURE),
        startup_time=StartupEstimate(StartupSpeed.FAST, (1, 3)),
        preferred_launch_method=LaunchMethod.EXECUTABLE_ON_PATH,
        window_strategy=WindowStrategy.TABBED_SINGLE_WINDOW,
        automation_strategy=AutomationStrategy.BROWSER_WORKER,
        recovery_approach=RecoveryApproach.RESTART_APPLICATION,
    ),
    # ---- AI software ----
        ApplicationOperationProfile(
            key="claude_desktop",
            launch=OperationNote("Started from a known install path (there is no reliable executable name on PATH)."),
            focus=OperationNote("Bring the existing window to the front; a second launch focuses the running instance rather than opening a second one."),
            close=OperationNote("Close the window; an in-progress response is abandoned."),
            wait_until_ready=OperationNote("The window is present and the message composer accepts focus."),
            health_check=OperationNote("The window is present and responds to focus; no persistent connection-error banner."),
            recover=OperationNote("Close and relaunch."),
            known_failure_modes=(FailureMode.NOT_RUNNING, FailureMode.WINDOW_HIDDEN, FailureMode.LOADING, FailureMode.HUNG, FailureMode.MULTIPLE_INSTANCES, FailureMode.LOGIN_REQUIRED, FailureMode.NETWORK_FAILURE),
            startup_time=StartupEstimate(StartupSpeed.MODERATE, (2, 5)),
            preferred_launch_method=LaunchMethod.KNOWN_INSTALL_PATH,
            window_strategy=WindowStrategy.SINGLE_INSTANCE_SINGLE_WINDOW,
            automation_strategy=AutomationStrategy.MCP_PROTOCOL,
            recovery_approach=RecoveryApproach.RESTART_APPLICATION,
        ),
        ApplicationOperationProfile(
            key="chatgpt_desktop",
            launch=OperationNote("Started from a known install path (there is no reliable executable name on PATH)."),
            focus=OperationNote("Bring the existing window to the front; a second launch focuses the running instance rather than opening a second one."),
            close=OperationNote("Close the window; an in-progress response is abandoned."),
            wait_until_ready=OperationNote("The window is present and the message composer accepts focus."),
            health_check=OperationNote("The window is present and responds to focus; no persistent connection-error banner."),
            recover=OperationNote("Close and relaunch."),
            known_failure_modes=(FailureMode.NOT_RUNNING, FailureMode.WINDOW_HIDDEN, FailureMode.LOADING, FailureMode.HUNG, FailureMode.MULTIPLE_INSTANCES, FailureMode.LOGIN_REQUIRED, FailureMode.NETWORK_FAILURE),
            startup_time=StartupEstimate(StartupSpeed.MODERATE, (2, 5)),
            preferred_launch_method=LaunchMethod.KNOWN_INSTALL_PATH,
            window_strategy=WindowStrategy.SINGLE_INSTANCE_SINGLE_WINDOW,
            automation_strategy=AutomationStrategy.DESKTOP_EXECUTIVE_WINDOW_CONTROL,
            recovery_approach=RecoveryApproach.RESTART_APPLICATION,
        ),
        ApplicationOperationProfile(
            key="perplexity_desktop",
            launch=OperationNote("Started via its Start Menu/AppUserModel registration — a fixed install path is not declared, discovered live instead (Universal Windows Environment Discovery)."),
            focus=OperationNote("Bring the existing window to the front; a second launch focuses the running instance rather than opening a second one."),
            close=OperationNote("Close the window; an in-progress response is abandoned."),
            wait_until_ready=OperationNote("The window is present and the message composer accepts focus."),
            health_check=OperationNote("The window is present and responds to focus; no persistent connection-error banner."),
            recover=OperationNote("Close and relaunch."),
            known_failure_modes=(FailureMode.NOT_RUNNING, FailureMode.WINDOW_HIDDEN, FailureMode.LOADING, FailureMode.HUNG, FailureMode.MULTIPLE_INSTANCES, FailureMode.LOGIN_REQUIRED, FailureMode.NETWORK_FAILURE),
            startup_time=StartupEstimate(StartupSpeed.MODERATE, (2, 5)),
            preferred_launch_method=LaunchMethod.KNOWN_INSTALL_PATH,
            window_strategy=WindowStrategy.SINGLE_INSTANCE_SINGLE_WINDOW,
            automation_strategy=AutomationStrategy.DESKTOP_EXECUTIVE_WINDOW_CONTROL,
            recovery_approach=RecoveryApproach.RESTART_APPLICATION,
        ),
        ApplicationOperationProfile(
            key="kimi_desktop",
            launch=OperationNote("Started via its Start Menu/AppUserModel registration — a fixed install path is not declared, discovered live instead (Universal Windows Environment Discovery)."),
            focus=OperationNote("Bring the existing window to the front; a second launch focuses the running instance rather than opening a second one."),
            close=OperationNote("Close the window; an in-progress response is abandoned."),
            wait_until_ready=OperationNote("The window is present and the message composer accepts focus."),
            health_check=OperationNote("The window is present and responds to focus; no persistent connection-error banner."),
            recover=OperationNote("Close and relaunch."),
            known_failure_modes=(FailureMode.NOT_RUNNING, FailureMode.WINDOW_HIDDEN, FailureMode.LOADING, FailureMode.HUNG, FailureMode.MULTIPLE_INSTANCES, FailureMode.LOGIN_REQUIRED, FailureMode.NETWORK_FAILURE),
            startup_time=StartupEstimate(StartupSpeed.MODERATE, (2, 5)),
            preferred_launch_method=LaunchMethod.KNOWN_INSTALL_PATH,
            window_strategy=WindowStrategy.SINGLE_INSTANCE_SINGLE_WINDOW,
            automation_strategy=AutomationStrategy.DESKTOP_EXECUTIVE_WINDOW_CONTROL,
            recovery_approach=RecoveryApproach.RESTART_APPLICATION,
        ),
        ApplicationOperationProfile(
            key="ollama",
        launch=OperationNote("Started as a background service (`ollama serve`, or auto-started by the installer) rather than opened as a window."),
        focus=OperationNote("Not applicable; there is no window — it is reached through its CLI or local API."),
        close=OperationNote("Stopped as a service/process; there is no window to close."),
        wait_until_ready=OperationNote("The local API responds (conventionally on `localhost:11434`)."),
        health_check=OperationNote("Responds to `ollama --version` and to a local API request."),
        recover=OperationNote("Restart the background service."),
        known_failure_modes=(FailureMode.NOT_RUNNING, FailureMode.LOADING, FailureMode.HUNG, FailureMode.MULTIPLE_INSTANCES, FailureMode.NETWORK_FAILURE),
        startup_time=StartupEstimate(StartupSpeed.FAST, (1, 3), "a large model's first load is separate and much slower"),
        preferred_launch_method=LaunchMethod.BACKGROUND_SERVICE,
        window_strategy=WindowStrategy.BACKGROUND_SERVICE,
        automation_strategy=AutomationStrategy.CLI_INVOCATION,
        recovery_approach=RecoveryApproach.RESTART_APPLICATION,
    ),
    ApplicationOperationProfile(
        key="lm_studio",
        launch=OperationNote("Started from a known install path."),
        focus=OperationNote("Bring the existing window to the front."),
        close=OperationNote("Close the window; a locally-served model stops serving when the application exits."),
        wait_until_ready=OperationNote("The window is present and the chat/server tab accepts focus."),
        health_check=OperationNote("The window is present and responds to focus; the local server tab (if enabled) shows 'running'."),
        recover=OperationNote("Close and relaunch."),
        known_failure_modes=(FailureMode.NOT_RUNNING, FailureMode.WINDOW_HIDDEN, FailureMode.LOADING, FailureMode.HUNG, FailureMode.NETWORK_FAILURE),
        startup_time=StartupEstimate(StartupSpeed.MODERATE, (2, 5)),
        preferred_launch_method=LaunchMethod.KNOWN_INSTALL_PATH,
        window_strategy=WindowStrategy.SINGLE_INSTANCE_SINGLE_WINDOW,
        automation_strategy=AutomationStrategy.DESKTOP_EXECUTIVE_WINDOW_CONTROL,
        recovery_approach=RecoveryApproach.RESTART_APPLICATION,
    ),
    ApplicationOperationProfile(
        key="open_webui",
        launch=OperationNote("Started as a local web service (`open-webui serve` or a container) rather than opened as a desktop window."),
        focus=OperationNote("Not applicable at the process level; once running it is reached as a page in a browser, whose focus is the browser's own concern."),
        close=OperationNote("Stopped as a service/process."),
        wait_until_ready=OperationNote("The local web server responds on its configured port."),
        health_check=OperationNote("The service process is running and its port accepts a connection."),
        recover=OperationNote("Restart the service process."),
        known_failure_modes=(FailureMode.NOT_RUNNING, FailureMode.LOADING, FailureMode.HUNG, FailureMode.LOGIN_REQUIRED, FailureMode.NETWORK_FAILURE),
        startup_time=StartupEstimate(StartupSpeed.MODERATE, (2, 8)),
        preferred_launch_method=LaunchMethod.SHELL_INVOCATION,
        window_strategy=WindowStrategy.BACKGROUND_SERVICE,
        automation_strategy=AutomationStrategy.BROWSER_WORKER,
        recovery_approach=RecoveryApproach.RESTART_APPLICATION,
    ),
    ApplicationOperationProfile(
        key="continue_dev",
        launch=OperationNote("Not launched on its own; it activates when its host editor (VS Code or a compatible fork) starts."),
        focus=OperationNote("Focus its panel inside the host editor; the editor's own window focus is a precondition."),
        close=OperationNote("Deactivates when the host editor closes; it has no independent process to end."),
        wait_until_ready=OperationNote("Its panel is present in the host editor's sidebar and accepts focus."),
        health_check=OperationNote("Its panel renders in the host editor without an extension-host error."),
        recover=OperationNote("Reload the host editor's window; the extension re-activates with it."),
        known_failure_modes=(FailureMode.NOT_RUNNING, FailureMode.LOADING, FailureMode.HUNG, FailureMode.NETWORK_FAILURE),
        startup_time=StartupEstimate(StartupSpeed.FAST, (1, 3), "activation time inside the host editor"),
        preferred_launch_method=LaunchMethod.HOSTED_EXTENSION,
        window_strategy=WindowStrategy.HOSTED_IN_OTHER_APPLICATION,
        automation_strategy=AutomationStrategy.NOT_AUTOMATABLE,
        recovery_approach=RecoveryApproach.RESTART_APPLICATION,
    ),
    # ---- containers and shells ----
    ApplicationOperationProfile(
        key="docker",
        launch=OperationNote("The engine is started as a background service (Docker Desktop, or `dockerd` directly); the `docker` CLI then talks to it."),
        focus=OperationNote("Not applicable to the engine; Docker Desktop's own dashboard window (if installed) can be focused independently."),
        close=OperationNote("Stopping the engine ends every running container; this is a deliberate, disruptive action a founder chooses."),
        wait_until_ready=OperationNote("`docker info` succeeds rather than reporting the daemon unreachable."),
        health_check=OperationNote("`docker info` or `docker version` succeeds against the running daemon."),
        recover=OperationNote("Restart the engine/service; running containers are stopped by this and must be started again afterward."),
        known_failure_modes=(FailureMode.NOT_RUNNING, FailureMode.LOADING, FailureMode.HUNG, FailureMode.NETWORK_FAILURE),
        startup_time=StartupEstimate(StartupSpeed.SLOW, (5, 30), "the engine/VM can take noticeably longer than the CLI's own start"),
        preferred_launch_method=LaunchMethod.BACKGROUND_SERVICE,
        window_strategy=WindowStrategy.BACKGROUND_SERVICE,
        automation_strategy=AutomationStrategy.CLI_INVOCATION,
        recovery_approach=RecoveryApproach.RESTART_APPLICATION,
    ),
    ApplicationOperationProfile(
        key="wsl",
        launch=OperationNote("Started implicitly by invoking `wsl` or a command inside a distribution; there is no separate 'WSL application' window."),
        focus=OperationNote("Not applicable; focus belongs to whichever terminal is hosting the session."),
        close=OperationNote("A distribution instance ends with `wsl --shutdown`, or when its hosting terminal closes."),
        wait_until_ready=OperationNote("The invoked shell prints its own prompt."),
        health_check=OperationNote("Responds to `wsl --version` and `wsl --list` without error."),
        recover=OperationNote("`wsl --shutdown` then re-invoke; this ends every running distribution, which is a deliberate, disruptive action."),
        known_failure_modes=(FailureMode.NOT_RUNNING, FailureMode.LOADING, FailureMode.HUNG, FailureMode.MULTIPLE_INSTANCES, FailureMode.NETWORK_FAILURE),
        startup_time=StartupEstimate(StartupSpeed.MODERATE, (2, 10), "cold VM start is slower than an already-running distribution"),
        preferred_launch_method=LaunchMethod.SHELL_INVOCATION,
        window_strategy=WindowStrategy.TERMINAL_HOSTED,
        automation_strategy=AutomationStrategy.CLI_INVOCATION,
        recovery_approach=RecoveryApproach.RESTART_APPLICATION,
    ),
    ApplicationOperationProfile(
        key="powershell",
        launch=OperationNote("Started from the Start Menu, Windows Terminal, or the `pwsh`/`powershell` executable on PATH."),
        focus=OperationNote("Bring the existing terminal window to the front."),
        close=OperationNote("Close the terminal window, or `exit` the session."),
        wait_until_ready=OperationNote("The prompt is printed and accepts input."),
        health_check=OperationNote("Responds to `pwsh --version` / `powershell -Command $PSVersionTable.PSVersion`."),
        recover=OperationNote("Close the window and open a new session; a hung command inside it is interrupted (Ctrl-C) first."),
        known_failure_modes=(FailureMode.NOT_RUNNING, FailureMode.WINDOW_HIDDEN, FailureMode.HUNG, FailureMode.MULTIPLE_INSTANCES, FailureMode.NETWORK_FAILURE),
        startup_time=StartupEstimate(StartupSpeed.FAST, (0, 2)),
        preferred_launch_method=LaunchMethod.EXECUTABLE_ON_PATH,
        window_strategy=WindowStrategy.TERMINAL_HOSTED,
        automation_strategy=AutomationStrategy.CLI_INVOCATION,
        recovery_approach=RecoveryApproach.RESTART_APPLICATION,
    ),
    ApplicationOperationProfile(
        key="java",
        launch=OperationNote("Invoked as a command — `java -jar ...` or `java <class>` — in an already-open terminal."),
        focus=OperationNote("Not applicable; focus belongs to the hosting terminal window."),
        close=OperationNote("The JVM process exits when the program ends, or is interrupted."),
        wait_until_ready=OperationNote("Ready once the JVM has started; for a long-running service, its own log line signals readiness."),
        health_check=OperationNote("Responds to `java -version`."),
        recover=OperationNote("Re-invoke the command; a hung process is interrupted and re-run."),
        known_failure_modes=(FailureMode.NOT_RUNNING, FailureMode.LOADING, FailureMode.HUNG, FailureMode.MULTIPLE_INSTANCES, FailureMode.NETWORK_FAILURE),
        startup_time=StartupEstimate(StartupSpeed.FAST, (1, 3), "JVM warm-up varies with the program"),
        preferred_launch_method=LaunchMethod.SHELL_INVOCATION,
        window_strategy=WindowStrategy.TERMINAL_HOSTED,
        automation_strategy=AutomationStrategy.CLI_INVOCATION,
        recovery_approach=RecoveryApproach.WAIT_AND_RETRY,
    ),
    ApplicationOperationProfile(
        key="playwright",
        launch=OperationNote("Invoked as a command (`playwright <subcommand>`) or as a Python package with no CLI on PATH at all — `catalog.py` already notes this."),
        focus=OperationNote("Not applicable; focus belongs to the hosting terminal, or to whatever browser window a Playwright script itself opens (a concern of the script, not of this profile)."),
        close=OperationNote("Exits when the invoking command completes."),
        wait_until_ready=OperationNote("Ready once the command starts; a specific script's own readiness is that script's concern."),
        health_check=OperationNote("Responds to `playwright --version` when a CLI is on PATH."),
        recover=OperationNote("Re-invoke the command."),
        known_failure_modes=(FailureMode.NOT_RUNNING, FailureMode.LOADING, FailureMode.HUNG, FailureMode.NETWORK_FAILURE),
        startup_time=StartupEstimate(StartupSpeed.FAST, (0, 2)),
        preferred_launch_method=LaunchMethod.SHELL_INVOCATION,
        window_strategy=WindowStrategy.TERMINAL_HOSTED,
        automation_strategy=AutomationStrategy.CLI_INVOCATION,
        recovery_approach=RecoveryApproach.WAIT_AND_RETRY,
    ),
)


# ═══════════════════════ 2 · recovery plans ═══════════════════════════════

#: `docker` and `wsl` are deliberately not generated here even though
#: they are command-line-first: each has a background engine/VM whose
#: failure surface (a daemon that must be started, a cold VM boot) is
#: genuinely different from a stateless CLI's, so each gets a bespoke
#: plan in `_BESPOKE_RECOVERY_PLANS` below instead — see its own comment.
_CLI_RECOVERY_PLANS: tuple[ApplicationRecoveryPlan, ...] = (
    _cli_recovery_plan("python", "Python"),
    _cli_recovery_plan("git", "Git"),
    _cli_recovery_plan("node", "Node.js"),
    _cli_recovery_plan("powershell", "PowerShell"),
    _cli_recovery_plan("java", "the JVM"),
    _cli_recovery_plan("playwright", "the Playwright CLI"),
)

_BESPOKE_RECOVERY_PLANS: tuple[ApplicationRecoveryPlan, ...] = (
    ApplicationRecoveryPlan(
        key="notepad",
        # The catalog gained `notepad` and an ApplicationOperationProfile
        # for it, and no recovery plan followed -- an application the
        # Executive knows about and could not recover.
        # `test_every_catalog_key_has_a_recovery_plan` was reporting a
        # real gap rather than being stale.
        #
        # The guidance follows the profile already written for it: always
        # present on Windows, near-instant, multi-window, and with exactly
        # one thing that can lose the founder's work.
        guidance=(
            (FailureMode.NOT_RUNNING, RecoveryGuidance("No Notepad process is present.", ("launch it; it is always available on Windows",))),
            (FailureMode.WINDOW_HIDDEN, RecoveryGuidance("The process is running but no window is visible (minimized or on another virtual desktop).", ("bring it to the front", "check other virtual desktops/monitors"))),
            (FailureMode.LOADING, _na("it opens near-instantly; there is no workspace or extension load to wait for.")),
            (FailureMode.HUNG, RecoveryGuidance("The window is present but not responding, which for Notepad usually means a very large file is being opened or saved.", ("wait briefly if a large file is genuinely in progress", "otherwise end the process and relaunch -- unsaved text is lost, so prefer waiting"))),
            (FailureMode.MULTIPLE_INSTANCES, RecoveryGuidance("More than one window is open, each with its own document -- ordinary, and a second launch opens a new window rather than focusing an existing one.", ("identify the window needed by its title, which is the file name",))),
            (FailureMode.LOGIN_REQUIRED, _na("Notepad has no account and no sign-in gate.")),
            (FailureMode.UNEXPECTED_POPUP, RecoveryGuidance("A dialog is blocking interaction -- almost always the save prompt raised by closing a document with unsaved text.", ("read it before dismissing: this is the one dialog here that loses the founder's work if answered the wrong way",))),
            (FailureMode.NETWORK_FAILURE, _na("Notepad is entirely local and needs no network.")),
        ),
    ),
    ApplicationRecoveryPlan(
        key="vscode",
        guidance=(
            (FailureMode.NOT_RUNNING, RecoveryGuidance("No VS Code process is present.", ("launch it with the folder that was open, if known",))),
            (FailureMode.WINDOW_HIDDEN, RecoveryGuidance("The process is running but no window is visible (minimized, moved off-screen, or on another virtual desktop).", ("bring it to the front", "check other virtual desktops/monitors"))),
            (FailureMode.LOADING, RecoveryGuidance("The workspace or an extension is still activating.", ("wait; large workspaces and many extensions extend this",))),
            (FailureMode.HUNG, RecoveryGuidance("The window is present but not responding to focus or input.", ("close the window", "if it will not close, end the process and relaunch"))),
            (FailureMode.MULTIPLE_INSTANCES, RecoveryGuidance("More than one window is open, each for a different folder — ordinary, not a fault.", ("identify the window for the folder actually needed by its title",))),
            (FailureMode.LOGIN_REQUIRED, _na("VS Code itself has no login gate; a specific extension's own sign-in is that extension's concern.")),
            (FailureMode.UNEXPECTED_POPUP, RecoveryGuidance("A dialog (an extension prompt, an unsaved-changes warning, an update notice) is blocking interaction.", ("read the dialog before dismissing it — an unsaved-changes prompt loses work if dismissed the wrong way",))),
            (FailureMode.NETWORK_FAILURE, RecoveryGuidance("An extension or Settings Sync could not reach the network.", ("check connectivity", "the editor itself remains usable offline"))),
        ),
    ),
    ApplicationRecoveryPlan(
        key="cursor",
        guidance=(
            (FailureMode.NOT_RUNNING, RecoveryGuidance("No Cursor process is present.", ("launch it with the workspace that was open, if known",))),
            (FailureMode.WINDOW_HIDDEN, RecoveryGuidance("The process is running but no window is visible.", ("bring it to the front", "check other virtual desktops/monitors"))),
            (FailureMode.LOADING, RecoveryGuidance("The workspace is still loading.", ("wait",))),
            (FailureMode.HUNG, RecoveryGuidance("The window is present but not responding.", ("close it", "if it will not close, end the process and relaunch"))),
            (FailureMode.MULTIPLE_INSTANCES, RecoveryGuidance("More than one window is open for different workspaces — ordinary.", ("identify the window needed by its title",))),
            (FailureMode.LOGIN_REQUIRED, RecoveryGuidance("Its AI features require a signed-in account.", ("check the account status in the application before assuming a different fault",))),
            (FailureMode.UNEXPECTED_POPUP, RecoveryGuidance("A dialog is blocking interaction.", ("read it before dismissing — an unsaved-changes prompt loses work if dismissed the wrong way",))),
            (FailureMode.NETWORK_FAILURE, RecoveryGuidance("Its AI features could not reach the network.", ("check connectivity", "local editing remains usable offline"))),
        ),
    ),
    ApplicationRecoveryPlan(
        key="visualstudio",
        guidance=(
            (FailureMode.NOT_RUNNING, RecoveryGuidance("No process is present.", ("launch it with the solution that was open, if known",))),
            (FailureMode.WINDOW_HIDDEN, RecoveryGuidance("The process is running but no window is visible.", ("bring it to the front",))),
            (FailureMode.LOADING, RecoveryGuidance("The solution is still loading — this can take noticeably longer for large solutions.", ("wait",))),
            (FailureMode.HUNG, RecoveryGuidance("The window is present but not responding, often during a long build.", ("wait if a build is genuinely in progress", "otherwise close and relaunch"))),
            (FailureMode.MULTIPLE_INSTANCES, RecoveryGuidance("More than one window is open for different solutions — ordinary.", ("identify the window needed by its title",))),
            (FailureMode.LOGIN_REQUIRED, RecoveryGuidance("Certain features require a signed-in account.", ("check the account status before assuming a different fault",))),
            (FailureMode.UNEXPECTED_POPUP, RecoveryGuidance("A dialog (an update notice, an unsaved-changes prompt) is blocking interaction.", ("read it before dismissing",))),
            (FailureMode.NETWORK_FAILURE, _na("core editing and building do not require network access; NuGet restore is the one exception and reports its own failure.")),
        ),
    ),
    ApplicationRecoveryPlan(
        key="chrome",
        guidance=(
            (FailureMode.NOT_RUNNING, RecoveryGuidance("No process is present.", ("launch it",))),
            (FailureMode.WINDOW_HIDDEN, RecoveryGuidance("The process is running but no window is visible.", ("bring it to the front",))),
            (FailureMode.LOADING, RecoveryGuidance("A page is still loading — a page concern, not a launch concern.", ("wait for the page, not the browser",))),
            (FailureMode.HUNG, RecoveryGuidance("A tab or the whole window is not responding, often one renderer process.", ("end the specific tab via the browser's own task manager if only one tab is affected", "otherwise close and relaunch the browser"))),
            (FailureMode.MULTIPLE_INSTANCES, RecoveryGuidance("More than one window is open — ordinary, tabs are the primary unit, not windows.", ("identify the window needed by its tabs",))),
            (FailureMode.LOGIN_REQUIRED, RecoveryGuidance("A site being viewed requires sign-in — a page concern, not a browser fault.", ("this is expected; sign in on the page",))),
            (FailureMode.UNEXPECTED_POPUP, RecoveryGuidance("A site dialog, a permission prompt, or the browser's own update notice is blocking interaction.", ("read it before dismissing",))),
            (FailureMode.NETWORK_FAILURE, RecoveryGuidance("A page could not load due to connectivity.", ("check connectivity", "retry the navigation"))),
        ),
    ),
    ApplicationRecoveryPlan(
        key="edge",
        guidance=(
            (FailureMode.NOT_RUNNING, RecoveryGuidance("No process is present.", ("launch it",))),
            (FailureMode.WINDOW_HIDDEN, RecoveryGuidance("The process is running but no window is visible.", ("bring it to the front",))),
            (FailureMode.LOADING, RecoveryGuidance("A page is still loading.", ("wait for the page, not the browser",))),
            (FailureMode.HUNG, RecoveryGuidance("A tab or the whole window is not responding.", ("end the specific tab via the browser's own task manager if only one tab is affected", "otherwise close and relaunch"))),
            (FailureMode.MULTIPLE_INSTANCES, RecoveryGuidance("More than one window is open — ordinary.", ("identify the window needed by its tabs",))),
            (FailureMode.LOGIN_REQUIRED, RecoveryGuidance("A site being viewed requires sign-in.", ("this is expected; sign in on the page",))),
            (FailureMode.UNEXPECTED_POPUP, RecoveryGuidance("A site dialog or the browser's own notice is blocking interaction.", ("read it before dismissing",))),
            (FailureMode.NETWORK_FAILURE, RecoveryGuidance("A page could not load due to connectivity.", ("check connectivity", "retry the navigation"))),
        ),
    ),
    ApplicationRecoveryPlan(
        key="firefox",
        guidance=(
            (FailureMode.NOT_RUNNING, RecoveryGuidance("No process is present.", ("launch it",))),
            (FailureMode.WINDOW_HIDDEN, RecoveryGuidance("The process is running but no window is visible.", ("bring it to the front",))),
            (FailureMode.LOADING, RecoveryGuidance("A page is still loading.", ("wait for the page, not the browser",))),
            (FailureMode.HUNG, RecoveryGuidance("A tab or the whole window is not responding.", ("close and relaunch; Firefox offers to restore tabs on restart",))),
            (FailureMode.MULTIPLE_INSTANCES, RecoveryGuidance("More than one window is open — ordinary.", ("identify the window needed by its tabs",))),
            (FailureMode.LOGIN_REQUIRED, RecoveryGuidance("A site being viewed requires sign-in.", ("this is expected; sign in on the page",))),
            (FailureMode.UNEXPECTED_POPUP, RecoveryGuidance("A site dialog or the browser's own notice is blocking interaction.", ("read it before dismissing",))),
            (FailureMode.NETWORK_FAILURE, RecoveryGuidance("A page could not load due to connectivity.", ("check connectivity", "retry the navigation"))),
        ),
    ),
    ApplicationRecoveryPlan(
            key="claude_desktop",
            guidance=(
                (FailureMode.NOT_RUNNING, RecoveryGuidance("No process is present.", ("launch it",))),
                (FailureMode.WINDOW_HIDDEN, RecoveryGuidance("The process is running but no window is visible.", ("bring it to the front",))),
                (FailureMode.LOADING, RecoveryGuidance("The conversation view or an MCP connection is still initializing.", ("wait",))),
                (FailureMode.HUNG, RecoveryGuidance("The window is present but not responding, or a response has stopped streaming.", ("wait briefly for a genuinely long response", "otherwise close and relaunch"))),
                (FailureMode.MULTIPLE_INSTANCES, _na("the application is single-window by design; a second launch focuses the existing window rather than opening another.")),
                (FailureMode.LOGIN_REQUIRED, RecoveryGuidance("The account session has expired.", ("sign in again in the application",))),
                (FailureMode.UNEXPECTED_POPUP, RecoveryGuidance("An update notice or an MCP permission prompt is blocking interaction.", ("read it before dismissing — an MCP permission prompt is a founder decision, not a default to click through",))),
                (FailureMode.NETWORK_FAILURE, RecoveryGuidance("The conversation could not reach the service.", ("check connectivity", "retry the message"))),
            ),
        ),
        ApplicationRecoveryPlan(
            key="chatgpt_desktop",
            guidance=(
                (FailureMode.NOT_RUNNING, RecoveryGuidance("No process is present.", ("launch it",))),
                (FailureMode.WINDOW_HIDDEN, RecoveryGuidance("The process is running but no window is visible.", ("bring it to the front",))),
                (FailureMode.LOADING, RecoveryGuidance("The conversation view is still initializing.", ("wait",))),
                (FailureMode.HUNG, RecoveryGuidance("The window is present but not responding, or a response has stopped streaming.", ("wait briefly for a genuinely long response", "otherwise close and relaunch"))),
                (FailureMode.MULTIPLE_INSTANCES, _na("the application is single-window by design; a second launch focuses the existing window rather than opening another.")),
                (FailureMode.LOGIN_REQUIRED, RecoveryGuidance("The account session has expired.", ("sign in again in the application",))),
                (FailureMode.UNEXPECTED_POPUP, RecoveryGuidance("An update notice or a permission prompt is blocking interaction.", ("read it before dismissing",))),
                (FailureMode.NETWORK_FAILURE, RecoveryGuidance("The conversation could not reach the service.", ("check connectivity", "retry the message"))),
            ),
        ),
        ApplicationRecoveryPlan(
            key="perplexity_desktop",
            guidance=(
                (FailureMode.NOT_RUNNING, RecoveryGuidance("No process is present.", ("launch it",))),
                (FailureMode.WINDOW_HIDDEN, RecoveryGuidance("The process is running but no window is visible.", ("bring it to the front",))),
                (FailureMode.LOADING, RecoveryGuidance("The conversation view is still initializing.", ("wait",))),
                (FailureMode.HUNG, RecoveryGuidance("The window is present but not responding, or a response has stopped streaming.", ("wait briefly for a genuinely long response", "otherwise close and relaunch"))),
                (FailureMode.MULTIPLE_INSTANCES, _na("the application is single-window by design; a second launch focuses the existing window rather than opening another.")),
                (FailureMode.LOGIN_REQUIRED, RecoveryGuidance("The account session has expired.", ("sign in again in the application",))),
                (FailureMode.UNEXPECTED_POPUP, RecoveryGuidance("An update notice or a permission prompt is blocking interaction.", ("read it before dismissing",))),
                (FailureMode.NETWORK_FAILURE, RecoveryGuidance("The conversation could not reach the service.", ("check connectivity", "retry the message"))),
            ),
        ),
        ApplicationRecoveryPlan(
            key="kimi_desktop",
            guidance=(
                (FailureMode.NOT_RUNNING, RecoveryGuidance("No process is present.", ("launch it",))),
                (FailureMode.WINDOW_HIDDEN, RecoveryGuidance("The process is running but no window is visible.", ("bring it to the front",))),
                (FailureMode.LOADING, RecoveryGuidance("The conversation view is still initializing.", ("wait",))),
                (FailureMode.HUNG, RecoveryGuidance("The window is present but not responding, or a response has stopped streaming.", ("wait briefly for a genuinely long response", "otherwise close and relaunch"))),
                (FailureMode.MULTIPLE_INSTANCES, _na("the application is single-window by design; a second launch focuses the existing window rather than opening another.")),
                (FailureMode.LOGIN_REQUIRED, RecoveryGuidance("The account session has expired.", ("sign in again in the application",))),
                (FailureMode.UNEXPECTED_POPUP, RecoveryGuidance("An update notice or a permission prompt is blocking interaction.", ("read it before dismissing",))),
                (FailureMode.NETWORK_FAILURE, RecoveryGuidance("The conversation could not reach the service.", ("check connectivity", "retry the message"))),
            ),
        ),
    ApplicationRecoveryPlan(
        key="ollama",
        guidance=(
            (FailureMode.NOT_RUNNING, RecoveryGuidance("The background service is not running.", ("start the service (`ollama serve`, or via the installer's own auto-start)",))),
            (FailureMode.WINDOW_HIDDEN, _na("the service has no window.")),
            (FailureMode.LOADING, RecoveryGuidance("A model is being loaded into memory for the first request.", ("wait; large models take noticeably longer on first load",))),
            (FailureMode.HUNG, RecoveryGuidance("The API is not responding to requests.", ("restart the service",))),
            (FailureMode.MULTIPLE_INSTANCES, RecoveryGuidance("More than one service instance is bound to the same port — a real conflict, not ordinary.", ("stop the extra instance; only one should hold the port",))),
            (FailureMode.LOGIN_REQUIRED, _na("local inference requires no sign-in.")),
            (FailureMode.UNEXPECTED_POPUP, _na("the service has no window to raise a popup in.")),
            (FailureMode.NETWORK_FAILURE, RecoveryGuidance("A request to pull a model over the network failed; local inference itself needs no network.", ("check connectivity if pulling a model", "already-downloaded models work offline"))),
        ),
    ),
    ApplicationRecoveryPlan(
        key="lm_studio",
        guidance=(
            (FailureMode.NOT_RUNNING, RecoveryGuidance("No process is present.", ("launch it",))),
            (FailureMode.WINDOW_HIDDEN, RecoveryGuidance("The process is running but no window is visible.", ("bring it to the front",))),
            (FailureMode.LOADING, RecoveryGuidance("A model is being loaded into memory.", ("wait; large models take noticeably longer",))),
            (FailureMode.HUNG, RecoveryGuidance("The window is present but not responding.", ("close and relaunch",))),
            (FailureMode.MULTIPLE_INSTANCES, _na("the application is single-window by design.")),
            (FailureMode.LOGIN_REQUIRED, _na("local inference requires no sign-in; the model catalogue browser is the one feature that may.")),
            (FailureMode.UNEXPECTED_POPUP, RecoveryGuidance("An update notice or a model-download prompt is blocking interaction.", ("read it before dismissing",))),
            (FailureMode.NETWORK_FAILURE, RecoveryGuidance("Downloading a model over the network failed; already-downloaded models work offline.", ("check connectivity if downloading",))),
        ),
    ),
    ApplicationRecoveryPlan(
        key="open_webui",
        guidance=(
            (FailureMode.NOT_RUNNING, RecoveryGuidance("The service process is not running.", ("start the service",))),
            (FailureMode.WINDOW_HIDDEN, _na("the service has no window of its own; the page it serves is the browser's concern.")),
            (FailureMode.LOADING, RecoveryGuidance("The service is still starting up.", ("wait",))),
            (FailureMode.HUNG, RecoveryGuidance("The service port stopped responding.", ("restart the service",))),
            (FailureMode.MULTIPLE_INSTANCES, RecoveryGuidance("More than one instance is bound to the same port — a real conflict.", ("stop the extra instance",))),
            (FailureMode.LOGIN_REQUIRED, RecoveryGuidance("The web UI requires sign-in on first use.", ("this is expected; sign in on the page",))),
            (FailureMode.UNEXPECTED_POPUP, _na("popups belong to the page rendering it, which is the browser's own concern, not this service's.")),
            (FailureMode.NETWORK_FAILURE, RecoveryGuidance("The service could not reach a configured backend (a model provider).", ("check the service's own backend configuration and connectivity",))),
        ),
    ),
    ApplicationRecoveryPlan(
        key="continue_dev",
        guidance=(
            (FailureMode.NOT_RUNNING, RecoveryGuidance("The extension has not activated; its host editor is not running.", ("launch the host editor",))),
            (FailureMode.WINDOW_HIDDEN, RecoveryGuidance("Its panel is collapsed or not selected inside the host editor.", ("open its panel in the host editor's sidebar",))),
            (FailureMode.LOADING, RecoveryGuidance("The extension is still activating.", ("wait",))),
            (FailureMode.HUNG, RecoveryGuidance("Its panel is present but not responding.", ("reload the host editor's window",))),
            (FailureMode.MULTIPLE_INSTANCES, _na("it activates once per host editor window; multiple host windows each have their own instance, which is ordinary.")),
            (FailureMode.LOGIN_REQUIRED, RecoveryGuidance("Its configured model provider requires sign-in or a credential.", ("check its configuration in the host editor",))),
            (FailureMode.UNEXPECTED_POPUP, _na("it has no window of its own to raise a popup in; any dialog belongs to the host editor.")),
            (FailureMode.NETWORK_FAILURE, RecoveryGuidance("Its configured model provider could not be reached.", ("check connectivity and the provider's own status",))),
        ),
    ),
    ApplicationRecoveryPlan(
        key="docker",
        guidance=(
            (FailureMode.NOT_RUNNING, RecoveryGuidance("The engine/daemon is not running.", ("start Docker Desktop, or `dockerd`, then retry",))),
            (FailureMode.WINDOW_HIDDEN, RecoveryGuidance("Docker Desktop's dashboard window (if installed) is not visible; the engine itself is unaffected.", ("bring the dashboard window to the front, if present",))),
            (FailureMode.LOADING, RecoveryGuidance("The engine/VM is still starting.", ("wait; this is one of the slower start-ups in the catalogue",))),
            (FailureMode.HUNG, RecoveryGuidance("The daemon is not responding to the CLI.", ("restart the engine/service",))),
            (FailureMode.MULTIPLE_INSTANCES, _na("one engine serves the whole machine; there is no concept of multiple engine instances.")),
            (FailureMode.LOGIN_REQUIRED, RecoveryGuidance("Pulling from a private registry requires `docker login`.", ("sign in to the registry before pulling",))),
            (FailureMode.UNEXPECTED_POPUP, RecoveryGuidance("Docker Desktop's own update or resource-limit notice is blocking its dashboard window.", ("read it before dismissing",))),
            (FailureMode.NETWORK_FAILURE, RecoveryGuidance("Pulling or pushing an image failed due to connectivity.", ("check connectivity", "already-pulled images and local builds work offline"))),
        ),
    ),
    ApplicationRecoveryPlan(
        key="wsl",
        guidance=(
            (FailureMode.NOT_RUNNING, RecoveryGuidance("No distribution instance is currently running.", ("invoke `wsl` or a command inside a distribution to start one",))),
            (FailureMode.WINDOW_HIDDEN, _na("WSL has no window of its own; whatever terminal hosts a session owns its window.")),
            (FailureMode.LOADING, RecoveryGuidance("The virtual machine is still starting (cold start).", ("wait; a cold VM start is slower than an already-running distribution",))),
            (FailureMode.HUNG, RecoveryGuidance("A distribution is not responding.", ("`wsl --shutdown`, then re-invoke — this ends every running distribution, a deliberate and disruptive step",))),
            (FailureMode.MULTIPLE_INSTANCES, RecoveryGuidance("More than one distribution is running concurrently — ordinary.", ("identify the specific distribution with `wsl --list --running`",))),
            (FailureMode.LOGIN_REQUIRED, _na("WSL itself gates on no login; a distribution's own user session is that distribution's concern.")),
            (FailureMode.UNEXPECTED_POPUP, _na("WSL has no window to raise a popup in.")),
            (FailureMode.NETWORK_FAILURE, RecoveryGuidance("A distribution could not reach the network (a known class of WSL networking issue after sleep/resume).", ("`wsl --shutdown` and restart the distribution",))),
        ),
    ),
)

RECOVERY_PLANS: tuple[ApplicationRecoveryPlan, ...] = _CLI_RECOVERY_PLANS + _BESPOKE_RECOVERY_PLANS


# ═══════════════════════ 3 · human workflows ══════════════════════════════

WORKFLOWS: tuple[Workflow, ...] = (
    Workflow(
        key="claude_desktop",
        name="ask_a_question",
        description="The brief's own example, captured as knowledge.",
        steps=(
            WorkflowStep(WorkflowVerb.LAUNCH, "Claude Desktop"),
            WorkflowStep(WorkflowVerb.WAIT, "the window to finish loading"),
            WorkflowStep(WorkflowVerb.FOCUS, "the prompt field"),
            WorkflowStep(WorkflowVerb.PASTE, "the question or context"),
            WorkflowStep(WorkflowVerb.SUBMIT, "the prompt"),
            WorkflowStep(WorkflowVerb.WAIT, "the response to finish streaming"),
            WorkflowStep(WorkflowVerb.COPY, "the response"),
        ),
    ),
    Workflow(
        key="cursor",
        name="request_a_code_change",
        description="The brief's own example, captured as knowledge.",
        steps=(
            WorkflowStep(WorkflowVerb.LAUNCH, "Cursor"),
            WorkflowStep(WorkflowVerb.WAIT, "the workspace to finish loading"),
            WorkflowStep(WorkflowVerb.FOCUS, "the editor or its inline prompt"),
            WorkflowStep(WorkflowVerb.PASTE, "the requested change, as a prompt"),
            WorkflowStep(WorkflowVerb.ACCEPT, "the suggested edit"),
        ),
    ),
    Workflow(
        key="vscode",
        name="open_and_edit_a_file",
        steps=(
            WorkflowStep(WorkflowVerb.LAUNCH, "VS Code", "often with a specific folder"),
            WorkflowStep(WorkflowVerb.WAIT, "the window and extensions to finish loading"),
            WorkflowStep(WorkflowVerb.FOCUS, "the editor pane"),
            WorkflowStep(WorkflowVerb.TYPE, "the edit"),
            WorkflowStep(WorkflowVerb.SAVE, "the file"),
        ),
    ),
    Workflow(
        key="visualstudio",
        name="open_a_solution",
        steps=(
            WorkflowStep(WorkflowVerb.LAUNCH, "Visual Studio"),
            WorkflowStep(WorkflowVerb.WAIT, "the solution to finish loading"),
            WorkflowStep(WorkflowVerb.FOCUS, "the editor or Solution Explorer"),
        ),
    ),
    Workflow(
        key="chrome",
        name="research_a_topic",
        description="The brief's own example, captured as knowledge.",
        steps=(
            WorkflowStep(WorkflowVerb.LAUNCH, "Chrome"),
            WorkflowStep(WorkflowVerb.FOCUS, "the address bar"),
            WorkflowStep(WorkflowVerb.NAVIGATE, "a search engine or a known URL"),
            WorkflowStep(WorkflowVerb.SEARCH, "the topic"),
            WorkflowStep(WorkflowVerb.SWITCH_TAB, "between results opened in new tabs"),
            WorkflowStep(WorkflowVerb.DOWNLOAD, "a file found during research", "when the task calls for it"),
        ),
    ),
    Workflow(
        key="chrome",
        name="upload_a_file_to_a_web_form",
        steps=(
            WorkflowStep(WorkflowVerb.NAVIGATE, "the page with the upload form"),
            WorkflowStep(WorkflowVerb.UPLOAD, "the file, via the page's own file picker"),
            WorkflowStep(WorkflowVerb.SUBMIT, "the form"),
        ),
    ),
    Workflow(
        key="edge",
        name="research_a_topic",
        steps=(
            WorkflowStep(WorkflowVerb.LAUNCH, "Edge"),
            WorkflowStep(WorkflowVerb.FOCUS, "the address bar"),
            WorkflowStep(WorkflowVerb.NAVIGATE, "a search engine or a known URL"),
            WorkflowStep(WorkflowVerb.SEARCH, "the topic"),
        ),
    ),
    Workflow(
        key="firefox",
        name="research_a_topic",
        steps=(
            WorkflowStep(WorkflowVerb.LAUNCH, "Firefox"),
            WorkflowStep(WorkflowVerb.FOCUS, "the address bar"),
            WorkflowStep(WorkflowVerb.NAVIGATE, "a search engine or a known URL"),
            WorkflowStep(WorkflowVerb.SEARCH, "the topic"),
        ),
    ),
    Workflow(
        key="ollama",
        name="run_a_local_model",
        steps=(
            WorkflowStep(WorkflowVerb.LAUNCH, "the Ollama service", "if not already running"),
            WorkflowStep(WorkflowVerb.WAIT, "the local API to accept requests"),
            WorkflowStep(WorkflowVerb.SUBMIT, "a prompt, via its CLI or local API"),
            WorkflowStep(WorkflowVerb.OBSERVE, "the response"),
        ),
    ),
    Workflow(
        key="lm_studio",
        name="chat_with_a_loaded_model",
        steps=(
            WorkflowStep(WorkflowVerb.LAUNCH, "LM Studio"),
            WorkflowStep(WorkflowVerb.WAIT, "a model to finish loading"),
            WorkflowStep(WorkflowVerb.FOCUS, "the chat panel"),
            WorkflowStep(WorkflowVerb.SUBMIT, "a prompt"),
            WorkflowStep(WorkflowVerb.OBSERVE, "the response"),
        ),
    ),
)


# ═══════════════════════ 4 · capability matrix ════════════════════════════

MATRIX = DesktopCapabilityMatrix(
    entries=(
        ("python", (Capability.SCRIPTING,)),
        ("git", (Capability.VERSION_CONTROL,)),
        ("node", (Capability.SCRIPTING, Capability.PACKAGE_MANAGEMENT)),
        ("vscode", (Capability.CODE_EDITING,)),
        ("cursor", (Capability.CODE_EDITING, Capability.AI_ASSISTANCE)),
        ("visualstudio", (Capability.CODE_EDITING,)),
        ("chrome", (Capability.NAVIGATION, Capability.UPLOAD, Capability.DOWNLOAD, Capability.AUTHENTICATION, Capability.SEARCH, Capability.CLIPBOARD)),
        ("edge", (Capability.NAVIGATION, Capability.UPLOAD, Capability.DOWNLOAD, Capability.AUTHENTICATION, Capability.SEARCH, Capability.CLIPBOARD)),
        ("firefox", (Capability.NAVIGATION, Capability.UPLOAD, Capability.DOWNLOAD, Capability.AUTHENTICATION, Capability.SEARCH, Capability.CLIPBOARD)),
        ("claude_desktop", (Capability.CONVERSATION, Capability.CLIPBOARD, Capability.MCP, Capability.FILESYSTEM, Capability.REASONING)),
        ("ollama", (Capability.LOCAL_INFERENCE, Capability.REASONING)),
        ("lm_studio", (Capability.LOCAL_INFERENCE, Capability.CHAT_UI)),
        ("open_webui", (Capability.CHAT_UI,)),
        ("continue_dev", (Capability.AI_ASSISTANCE,)),
        ("docker", (Capability.CONTAINERIZATION,)),
        ("wsl", (Capability.LINUX_SUBSYSTEM,)),
        ("powershell", (Capability.SCRIPTING,)),
        ("java", (Capability.JVM_RUNTIME,)),
        ("playwright", (Capability.TEST_AUTOMATION,)),
    )
)
