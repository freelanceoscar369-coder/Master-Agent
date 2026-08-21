"""Mission Brief 030 — the Desktop Executive.

Kalpavriksha's eyes and hands over the local machine. The claim these
tests hold is narrow and load-bearing: **it executes, it never decides.**
It reports what is installed and does what it is dispatched, and it has
no idea what a model is.

Every test runs against a `FakeProbe`. Nothing here launches Chrome,
kills a process, or shells out — which is what makes a hundred tests
cheap rather than dangerous.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from master_agent.desktop import catalog
from master_agent.desktop.actions import (
    DESKTOP_ACTION_CLASSES,
    DesktopContext,
    ExecuteCommandAction,
)
from master_agent.desktop.inventory import (
    INSTALLED,
    MISSING,
    attribute_processes,
    discover,
    discover_application,
    extract_version,
    observations,
    one_line,
    repair_wide_text,
)
from master_agent.desktop.plugin import DESKTOP_EXECUTIVE_ID, DesktopPlugin
from master_agent.desktop.probe import (
    CommandResult,
    NullSystemProbe,
    ProcessInfo,
    RealSystemProbe,
)
from master_agent.executor.executor import LocalExecutor
from master_agent.mission_control.adapters import discover_executives
from master_agent.mission_control.mission_control import MissionControl
from master_agent.mission_control.tasks import Objective, Task, TaskState
from master_agent.permissions.permission_system import GrantScope, PermissionSystem
from master_agent.plugins.base import RiskTier
from master_agent.plugins.registry import PluginRegistry
from master_agent.runtime.approval import FounderApprovalGate, PermissionSystemGate
from master_agent.runtime.config import RuntimeConfig
from master_agent.runtime.engine import RuntimeEngine
from master_agent.runtime.gateway import PluginGateway

DESKTOP_DIR = Path(__file__).resolve().parents[1] / "src" / "master_agent" / "desktop"


class FakeProbe:
    """A machine, described rather than discovered."""

    def __init__(
        self,
        platform: str = "win32",
        on_path: dict[str, str] | None = None,
        paths: set[str] | None = None,
        versions: dict[str, str] | None = None,
        running: list[ProcessInfo] | None = None,
        fail: set[str] | None = None,
        start_apps: list[dict] | None = None,
        store_apps: list[dict] | None = None,
        uninstall_apps: list[dict] | None = None,
    ) -> None:
        self.platform = platform
        self._on_path = on_path or {}
        self._paths = paths or set()
        self._versions = versions or {}
        self._running = running or []
        self._fail = fail or set()
        self._start_apps = start_apps or []
        self._store_apps = store_apps or []
        self._uninstall_apps = uninstall_apps or []
        self.started: list[list[str]] = []
        self.ran: list[list[str]] = []

    def which(self, executable: str) -> str | None:
        return self._on_path.get(executable)

    def exists(self, path: str) -> bool:
        return path in self._paths

    def run(self, command: list[str]) -> CommandResult:
        self.ran.append(command)
        head = command[0]
        if head in self._fail:
            return CommandResult(ok=False, error=f"boom: {head}")
        if head in self._versions:
            return CommandResult(ok=True, output=self._versions[head])
        return CommandResult(ok=True, output="")

    def start(self, command: list[str]) -> CommandResult:
        self.started.append(command)
        if command[0] in self._fail:
            return CommandResult(ok=False, error=f"cannot start {command[0]}")
        return CommandResult(ok=True)

    def processes(self) -> list[ProcessInfo]:
        return list(self._running)

    def get_store_apps(self) -> list[dict]:
        return list(self._store_apps)

    def get_uninstall_apps(self) -> list[dict]:
        return list(self._uninstall_apps)

    def get_start_apps(self) -> list[dict]:
        return list(self._start_apps)


def machine(**kwargs) -> FakeProbe:
    defaults = {
        "on_path": {"git": "/usr/bin/git", "python": "/usr/bin/python"},
        "versions": {"git": "git version 2.43.0", "python": "Python 3.14.0"},
    }
    defaults.update(kwargs)
    return FakeProbe(**defaults)


def plugin_for(probe: FakeProbe) -> tuple[DesktopPlugin, PermissionSystem]:
    permissions = PermissionSystem()
    executor = LocalExecutor(permissions)
    return DesktopPlugin(executor, probe=probe), permissions


def invoke(plugin: DesktopPlugin, capability: str, payload: dict | None = None):
    return plugin.invoke(capability, payload or {})


# ---- the catalogue -------------------------------------------------------


def test_the_catalogue_is_not_empty():
    assert len(catalog.CATALOG) >= 15


@pytest.mark.parametrize("spec", catalog.CATALOG, ids=lambda s: s.key)
def test_every_catalogue_entry_is_findable_somehow(spec):
    """An entry with no `label`, no executable, and no known path could
    never be found, which would make it a permanent 'missing' the founder
    cannot act on.

    `executables`/`windows_paths`/`posix_paths` are no longer the only
    way — Universal Windows Environment Discovery's `discover()` also
    matches every spec's `label` against live Start Menu/MSIX/registry
    entries (`inventory.py::_claim_match`), confirmed live for real,
    genuinely path-less catalogue entries (Perplexity, Kimi) this
    session. `label` is therefore the one thing every entry actually
    needs; declared paths/executables are enrichment for apps whose
    location is already known, not a requirement."""
    assert spec.label or spec.executables or spec.windows_paths or spec.posix_paths


@pytest.mark.parametrize("spec", catalog.CATALOG, ids=lambda s: s.key)
def test_every_catalogue_entry_has_a_label_and_category(spec):
    assert spec.label
    assert spec.category


@pytest.mark.parametrize("spec", catalog.CATALOG, ids=lambda s: s.key)
def test_catalogue_keys_are_lowercase_identifiers(spec):
    assert spec.key == spec.key.lower()
    assert " " not in spec.key


def test_catalogue_keys_are_unique():
    keys = [spec.key for spec in catalog.CATALOG]
    assert len(keys) == len(set(keys))


def test_resolve_finds_by_key():
    assert catalog.resolve("vscode").label == "VS Code"


def test_resolve_finds_by_label_case_insensitively():
    assert catalog.resolve("vs code").key == "vscode"
    assert catalog.resolve("VS Code").key == "vscode"


def test_resolve_finds_by_executable():
    assert catalog.resolve("code").key == "vscode"


def test_resolve_returns_none_for_unknown():
    assert catalog.resolve("definitely-not-real") is None
    assert catalog.resolve("") is None
    assert catalog.resolve(None) is None


def test_the_ai_grouping_contains_the_named_applications():
    keys = {spec.key for spec in catalog.ai_applications()}

    for expected in ("claude_desktop", "ollama", "lm_studio", "cursor"):
        assert expected in keys


def test_recommended_applications_are_marked():
    assert {spec.key for spec in catalog.recommended()}


def test_readiness_keys_all_exist_in_the_catalogue():
    for key in catalog.READINESS_KEYS:
        assert key in catalog.BY_KEY


def test_paths_for_switches_on_platform():
    spec = catalog.BY_KEY["vscode"]

    assert spec.paths_for("win32") == spec.windows_paths
    assert spec.paths_for("linux") == spec.posix_paths


# ---- version parsing -----------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("git version 2.43.0", "2.43.0"),
        ("Python 3.14.0", "3.14.0"),
        ("v24.15.0", "24.15.0"),
        ("Docker version 29.4.3, build abc", "29.4.3"),
        ("1.60.0", "1.60.0"),
        ("openjdk version \"21.0.1\"", "21.0.1"),
        ("ollama version is 0.32.5", "0.32.5"),
    ],
)
def test_versions_are_extracted(raw, expected):
    assert extract_version(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "not found: code",
        "At line:1 char:3",
        "some banner with no numbers",
    ],
)
def test_unparseable_output_is_not_a_version(raw):
    """The important half. A real machine scan once filled the version
    column with error text presented as fact."""
    assert extract_version(raw) is None


def test_utf16_output_is_repaired():
    """`wsl --version` emits UTF-16LE, which text-mode subprocess decodes
    as cp1252 -- found on a real Windows machine."""
    wide = "W S L   v e r s i o n :   2 . 7 . 3 . 0"

    assert extract_version(wide) == "2.7.3"


def test_normal_text_is_left_alone_by_the_repair():
    assert repair_wide_text("git version 2.43.0") == "git version 2.43.0"


def test_short_text_is_left_alone_by_the_repair():
    assert repair_wide_text("2.1") == "2.1"


def test_one_line_truncates_multiline_errors():
    blob = "At line:1 char:3\n+ --version\n+   ~\nMissing expression"

    assert one_line(blob) == "At line:1 char:3"


def test_one_line_bounds_length():
    assert len(one_line("x" * 500)) <= 70


def test_one_line_of_nothing_is_empty():
    assert one_line("") == ""


# ---- discovery -----------------------------------------------------------


def test_an_application_on_the_path_is_installed():
    found = discover_application(catalog.BY_KEY["git"], machine())

    assert found.status == INSTALLED
    assert found.installed is True
    assert found.launchable is True
    assert found.version == "2.43.0"
    assert found.path == "/usr/bin/git"


def test_an_application_nowhere_is_missing():
    found = discover_application(catalog.BY_KEY["docker"], machine())

    assert found.status == MISSING
    assert found.installed is False
    assert found.launchable is False
    assert found.detail


def test_a_known_install_path_counts_as_installed():
    probe = FakeProbe(paths={r"%PROGRAMFILES%\Mozilla Firefox\firefox.exe"})

    found = discover_application(catalog.BY_KEY["firefox"], probe)

    assert found.installed is True
    assert "known install path" in found.detail


def test_the_path_is_preferred_over_a_known_location():
    probe = FakeProbe(
        on_path={"firefox": "/usr/bin/firefox"},
        paths={r"%PROGRAMFILES%\Mozilla Firefox\firefox.exe"},
    )

    assert discover_application(catalog.BY_KEY["firefox"], probe).path == "/usr/bin/firefox"


def test_a_tool_that_cannot_report_a_version_is_still_installed():
    probe = FakeProbe(on_path={"git": "/usr/bin/git"}, fail={"git"})

    found = discover_application(catalog.BY_KEY["git"], probe)

    assert found.installed is True
    assert found.version is None
    assert found.healthy is False
    assert found.detail


def test_a_tool_that_answers_but_unparseably_stays_healthy():
    """"We could not parse the version" is a different fact from "this is
    broken", and a founder who sees red beside a working tool learns to
    ignore red."""
    probe = FakeProbe(on_path={"git": "/usr/bin/git"}, versions={"git": "no numbers"})

    found = discover_application(catalog.BY_KEY["git"], probe)

    assert found.installed is True
    assert found.version is None
    assert found.healthy is True


def test_skipping_version_reads_avoids_running_anything():
    probe = machine()

    discover_application(catalog.BY_KEY["git"], probe, read_version=False)

    assert probe.ran == []


def test_a_full_scan_covers_the_whole_catalogue():
    inventory = discover(machine())

    assert len(inventory.applications) == len(catalog.CATALOG)


def test_a_scan_records_the_platform():
    assert discover(FakeProbe(platform="linux")).platform == "linux"


def test_installed_and_missing_partition_the_scan():
    inventory = discover(machine())

    assert len(inventory.installed()) + len(inventory.missing()) == len(
        inventory.applications
    )


def test_a_scan_finds_the_installed_ones():
    inventory = discover(machine())

    assert {a.key for a in inventory.installed()} == {"git", "python"}


def test_get_returns_none_for_an_unknown_key():
    assert discover(machine()).get("nope") is None


def test_missing_recommended_only_lists_recommended_ones():
    inventory = discover(machine())
    names = {a.key for a in inventory.missing_recommended()}

    assert "node" in names
    assert "lm_studio" not in names, "LM Studio is not a recommended application"


def test_the_inventory_serialises():
    data = discover(machine()).as_dict()

    assert data["platform"] == "win32"
    assert len(data["applications"]) == len(catalog.CATALOG)
    assert "captured_at" in data


# ---- processes -----------------------------------------------------------


def test_processes_are_attributed_to_applications():
    attributed = attribute_processes(
        [ProcessInfo(pid=1, name="chrome.exe"), ProcessInfo(pid=2, name="ollama.exe")]
    )

    assert {p.owner for p in attributed} == {"chrome", "ollama"}


def test_an_unclaimed_process_has_no_owner():
    """Unowned, not misattributed."""
    attributed = attribute_processes([ProcessInfo(pid=9, name="mystery.exe")])

    assert attributed[0].owner is None


def test_attribution_ignores_the_exe_suffix():
    attributed = attribute_processes([ProcessInfo(pid=1, name="chrome")])

    assert attributed[0].owner == "chrome"


def test_attribution_is_case_insensitive():
    attributed = attribute_processes([ProcessInfo(pid=1, name="CHROME.EXE")])

    assert attributed[0].owner == "chrome"


def test_running_filters_by_owner():
    inventory = discover(
        machine(running=[ProcessInfo(pid=1, name="chrome.exe"), ProcessInfo(pid=2, name="x")])
    )

    assert [p.pid for p in inventory.running("chrome")] == [1]


def test_a_process_survives_serialisation():
    assert ProcessInfo(pid=7, name="a", owner="b").as_dict()["pid"] == 7


# ---- observations, not recommendations -----------------------------------


def test_observations_state_facts():
    lines = observations(discover(machine()))

    assert "Git 2.43.0 installed." in lines
    assert "Docker not installed." in lines


@pytest.mark.parametrize(
    "advice_word", ["should", "recommend", "suggest", "consider", "better", "install "]
)
def test_observations_never_give_advice(advice_word):
    """Deliverable 10: facts only. "Ollama not installed." is a fact;
    "Install Ollama." is advice, and advice belongs to the Broker."""
    lines = " ".join(observations(discover(machine()))).lower()

    assert advice_word not in lines


# ---- the Executive contract ----------------------------------------------


def test_the_executive_registers_twelve_capabilities():
    plugin, _ = plugin_for(machine())

    assert len(plugin.manifest.capabilities) == 12


def test_the_executive_is_named_desktop():
    plugin, _ = plugin_for(machine())

    assert plugin.manifest.name == DESKTOP_EXECUTIVE_ID


@pytest.mark.parametrize(
    "capability",
    [
        "launch_application",
        "close_application",
        "is_installed",
        "get_version",
        "list_installed_software",
        "list_running_processes",
        "is_running",
        "bring_to_front",
        "focus_window",
        "open_file",
        "open_folder",
        "execute_command",
    ],
)
def test_every_briefed_capability_exists(capability):
    plugin, _ = plugin_for(machine())

    assert capability in {c.name for c in plugin.manifest.capabilities}


@pytest.mark.parametrize(
    "capability",
    [
        "is_installed",
        "get_version",
        "list_installed_software",
        "list_running_processes",
        "is_running",
    ],
)
def test_asking_is_read_only(capability):
    plugin, _ = plugin_for(machine())
    tier = {c.name: c.risk_tier for c in plugin.manifest.capabilities}[capability]

    assert tier is RiskTier.READ_ONLY


@pytest.mark.parametrize("capability", ["close_application", "execute_command"])
def test_destructive_capabilities_are_irreversible(capability):
    """Closing loses unsaved work; running a command does anything at all.
    ADR-0009 then guarantees no standing grant can ever satisfy them."""
    plugin, _ = plugin_for(machine())
    tier = {c.name: c.risk_tier for c in plugin.manifest.capabilities}[capability]

    assert tier is RiskTier.IRREVERSIBLE


@pytest.mark.parametrize(
    "capability", ["launch_application", "open_file", "open_folder", "bring_to_front"]
)
def test_acting_capabilities_are_reversible_writes(capability):
    plugin, _ = plugin_for(machine())
    tier = {c.name: c.risk_tier for c in plugin.manifest.capabilities}[capability]

    assert tier is RiskTier.REVERSIBLE_WRITE


@pytest.mark.parametrize("action_cls", DESKTOP_ACTION_CLASSES, ids=lambda c: c.name)
def test_every_action_declares_the_contract(action_cls):
    action = action_cls(DesktopContext(machine()))

    assert action.name
    assert action.description
    assert action.risk_tier
    assert action.expected_result


def test_an_unknown_capability_is_refused():
    plugin, _ = plugin_for(machine())

    result = invoke(plugin, "teleport")

    assert result.success is False
    assert "unsupported capability" in result.error


# ---- asking --------------------------------------------------------------


def test_is_installed_reports_true_for_something_present():
    plugin, _ = plugin_for(machine())

    result = invoke(plugin, "is_installed", {"application": "git"})

    assert result.success is True
    assert result.output["installed"] is True


def test_is_installed_reports_false_for_something_absent():
    plugin, _ = plugin_for(machine())

    result = invoke(plugin, "is_installed", {"application": "docker"})

    assert result.output["installed"] is False


def test_is_installed_needs_an_application():
    plugin, _ = plugin_for(machine())

    result = invoke(plugin, "is_installed", {})

    assert result.success is False
    assert "application" in result.error


def test_an_unknown_application_is_refused_with_the_known_list():
    plugin, _ = plugin_for(machine())

    result = invoke(plugin, "is_installed", {"application": "nonsense"})

    assert result.success is False
    assert "unknown application" in result.error
    assert "git" in result.error


def test_get_version_returns_the_version():
    plugin, _ = plugin_for(machine())

    result = invoke(plugin, "get_version", {"application": "python"})

    assert result.output["version"] == "3.14.0"


def test_get_version_of_something_absent_is_none():
    plugin, _ = plugin_for(machine())

    result = invoke(plugin, "get_version", {"application": "docker"})

    assert result.output["version"] is None
    assert result.output["installed"] is False


def test_list_installed_software_returns_the_inventory():
    plugin, _ = plugin_for(machine())

    result = invoke(plugin, "list_installed_software")

    assert result.output["installed_count"] == 2
    assert len(result.output["applications"]) == len(catalog.CATALOG)
    assert result.output["observations"]


def test_list_installed_software_filters_by_category():
    plugin, _ = plugin_for(machine())

    result = invoke(plugin, "list_installed_software", {"category": "ai"})

    assert {a["category"] for a in result.output["applications"]} == {"ai"}


def test_an_unknown_category_is_refused():
    plugin, _ = plugin_for(machine())

    result = invoke(plugin, "list_installed_software", {"category": "nope"})

    assert result.success is False
    assert "unknown category" in result.error


def test_list_running_processes_returns_them():
    plugin, _ = plugin_for(
        machine(running=[ProcessInfo(pid=1, name="chrome.exe"), ProcessInfo(pid=2, name="x")])
    )

    result = invoke(plugin, "list_running_processes")

    assert result.output["count"] == 2


def test_list_running_processes_can_filter_to_owned_ones():
    plugin, _ = plugin_for(
        machine(running=[ProcessInfo(pid=1, name="chrome.exe"), ProcessInfo(pid=2, name="x")])
    )

    result = invoke(plugin, "list_running_processes", {"owned_only": True})

    assert result.output["count"] == 1


def test_is_running_is_true_when_a_process_belongs_to_it():
    plugin, _ = plugin_for(machine(running=[ProcessInfo(pid=42, name="chrome.exe")]))

    result = invoke(plugin, "is_running", {"application": "chrome"})

    assert result.output["running"] is True
    assert result.output["processes"][0]["pid"] == 42


def test_is_running_is_false_when_nothing_matches():
    plugin, _ = plugin_for(machine())

    assert invoke(plugin, "is_running", {"application": "chrome"}).output["running"] is False


# ---- launching -----------------------------------------------------------


def test_launching_starts_the_resolved_path():
    probe = machine()
    plugin, _ = plugin_for(probe)

    result = invoke(plugin, "launch_application", {"application": "git"})

    assert result.success is True
    assert probe.started == [["/usr/bin/git"]]


def test_launching_something_absent_fails_cleanly():
    plugin, _ = plugin_for(machine())

    result = invoke(plugin, "launch_application", {"application": "docker"})

    assert result.success is False
    assert "not installed" in result.error


def test_a_failed_start_is_reported():
    probe = FakeProbe(on_path={"git": "/usr/bin/git"}, fail={"/usr/bin/git"})
    plugin, _ = plugin_for(probe)

    assert invoke(plugin, "launch_application", {"application": "git"}).success is False


def test_open_file_uses_the_platform_opener():
    probe = FakeProbe(platform="win32", paths={"C:/notes.txt"})
    plugin, _ = plugin_for(probe)

    result = invoke(plugin, "open_file", {"path": "C:/notes.txt"})

    assert result.success is True
    assert probe.started[0][0] == "cmd"


def test_open_file_on_posix_uses_xdg_open():
    probe = FakeProbe(platform="linux", paths={"/tmp/notes.txt"})
    plugin, _ = plugin_for(probe)

    invoke(plugin, "open_file", {"path": "/tmp/notes.txt"})

    assert probe.started[0][0] == "xdg-open"


def test_open_file_on_macos_uses_open():
    probe = FakeProbe(platform="darwin", paths={"/tmp/n.txt"})
    plugin, _ = plugin_for(probe)

    invoke(plugin, "open_file", {"path": "/tmp/n.txt"})

    assert probe.started[0][0] == "open"


def test_opening_something_that_does_not_exist_is_refused():
    plugin, _ = plugin_for(FakeProbe())

    result = invoke(plugin, "open_file", {"path": "/nope"})

    assert result.success is False
    assert "no such path" in result.error


def test_open_folder_shares_the_open_file_behaviour():
    probe = FakeProbe(platform="linux", paths={"/tmp/dir"})
    plugin, _ = plugin_for(probe)

    assert invoke(plugin, "open_folder", {"path": "/tmp/dir"}).success is True


# ---- focus, which is deliberately not built ------------------------------


def test_bringing_to_front_reports_that_it_is_not_built():
    """Deliverable 7 excludes window automation. Saying so beats silently
    doing nothing."""
    plugin, _ = plugin_for(machine(running=[ProcessInfo(pid=3, name="chrome.exe")]))

    result = invoke(plugin, "bring_to_front", {"application": "chrome"})

    assert result.success is False
    assert "Deliverable 7" in result.error


def test_focusing_something_not_running_says_so_first():
    plugin, _ = plugin_for(machine())

    result = invoke(plugin, "focus_window", {"application": "chrome"})

    assert result.success is False
    assert "not running" in result.error


# ---- closing -------------------------------------------------------------


def test_closing_kills_every_owned_process():
    probe = machine(
        running=[ProcessInfo(pid=1, name="chrome.exe"), ProcessInfo(pid=2, name="chrome.exe")]
    )
    plugin, _ = plugin_for(probe)

    result = invoke(plugin, "close_application", {"application": "chrome"})

    assert result.success is True
    assert result.output["closed"] == [1, 2]


def test_closing_something_not_running_fails():
    plugin, _ = plugin_for(machine())

    result = invoke(plugin, "close_application", {"application": "chrome"})

    assert result.success is False
    assert "not running" in result.error


def test_closing_uses_taskkill_on_windows():
    probe = FakeProbe(platform="win32", running=[ProcessInfo(pid=5, name="chrome.exe")])
    plugin, _ = plugin_for(probe)

    invoke(plugin, "close_application", {"application": "chrome"})

    assert probe.ran[-1][0] == "taskkill"


def test_closing_uses_kill_on_posix():
    probe = FakeProbe(platform="linux", running=[ProcessInfo(pid=5, name="chrome")])
    plugin, _ = plugin_for(probe)

    invoke(plugin, "close_application", {"application": "chrome"})

    assert probe.ran[-1] == ["kill", "5"]


# ---- execute command -----------------------------------------------------


def test_a_command_runs_and_returns_output():
    probe = FakeProbe(versions={"echo": "hello"})
    plugin, _ = plugin_for(probe)

    result = invoke(plugin, "execute_command", {"command": ["echo", "hi"]})

    assert result.success is True
    assert result.output["output"] == "hello"


def test_a_shell_string_is_refused():
    """argv only. A shell string would let a payload smuggle a pipeline."""
    plugin, _ = plugin_for(machine())

    result = invoke(plugin, "execute_command", {"command": "rm -rf / | tee x"})

    assert result.success is False
    assert "not a string" in result.error


def test_an_empty_command_is_refused():
    plugin, _ = plugin_for(machine())

    assert invoke(plugin, "execute_command", {"command": []}).success is False


def test_a_command_with_a_blank_argument_is_refused():
    plugin, _ = plugin_for(machine())

    assert invoke(plugin, "execute_command", {"command": ["ls", "  "]}).success is False


def test_a_command_with_a_non_string_argument_is_refused():
    plugin, _ = plugin_for(machine())

    assert invoke(plugin, "execute_command", {"command": ["ls", 7]}).success is False


def test_a_failing_command_reports_the_failure():
    probe = FakeProbe(fail={"broken"})
    plugin, _ = plugin_for(probe)

    result = invoke(plugin, "execute_command", {"command": ["broken"]})

    assert result.success is False


def test_execute_command_validation_is_pure():
    action = ExecuteCommandAction(DesktopContext(machine()))

    assert action.validate({"command": ["ls"]}) == []
    assert action.validate({}) != []


# ---- Mission Control registration (Deliverable 1) ------------------------


def registered_world(probe: FakeProbe | None = None):
    permissions = PermissionSystem()
    executor = LocalExecutor(permissions)
    plugin = DesktopPlugin(executor, probe=probe or machine())
    registry = PluginRegistry()
    registry.register(plugin)
    mc = MissionControl()
    discover_executives(mc, registry)
    return mc, plugin, permissions, registry


def test_the_executive_is_discovered_by_mission_control():
    mc, _, _, _ = registered_world()

    assert DESKTOP_EXECUTIVE_ID in mc.executives.ids()


def test_its_capabilities_reach_mission_control_qualified():
    mc, _, _, _ = registered_world()

    assert "Desktop.IsInstalled" in mc.capabilities.names()
    assert "Desktop.ListInstalledSoftware" in mc.capabilities.names()


def test_all_twelve_capabilities_are_registered():
    mc, _, _, _ = registered_world()

    assert len(mc.capabilities.for_executive(DESKTOP_EXECUTIVE_ID)) == 12


def test_discovery_needs_no_special_casing():
    """Registered by the same manifest-reading adapter every other
    Executive uses -- nothing in Mission Control knows a desktop exists."""
    mc, _, _, _ = registered_world()

    assert mc.executives.get(DESKTOP_EXECUTIVE_ID).version == "1.0.0"


# ---- through the Runtime (Rule 4) ----------------------------------------


def run_task(capability: str, payload: dict, probe: FakeProbe | None = None, approve=()):
    mc, plugin, permissions, registry = registered_world(probe)
    for granted in approve:
        permissions.grant(DESKTOP_EXECUTIVE_ID, granted, GrantScope.ONCE)
    inner = PermissionSystemGate(permissions, registry)
    gate = FounderApprovalGate(
        inner, mc, lambda r: permissions.grant(r.executive_id, r.local_capability, GrantScope.ONCE)
    )
    engine = RuntimeEngine(
        mc,
        RuntimeConfig(poll_interval_seconds=0, max_cycles=3),
        sleep=lambda _s: None,
        approval_gate=gate,
    )
    engine.register_gateway(DESKTOP_EXECUTIVE_ID, PluginGateway(plugin))
    mc.submit_objective(
        Objective(
            description="desktop",
            tasks=[Task(capability=capability, payload=payload, task_id="t1")],
        )
    )
    engine.run_forever()
    return mc, mc.dispatcher.objectives()[0].task("t1"), plugin


def test_a_read_only_capability_runs_through_the_runtime_without_approval():
    _, task, _ = run_task("Desktop.ListInstalledSoftware", {})

    assert task.state is TaskState.COMPLETED


def test_an_irreversible_capability_waits_for_the_founder():
    mc, task, _ = run_task("Desktop.ExecuteCommand", {"command": ["echo", "x"]})

    assert task.state is not TaskState.COMPLETED
    assert len(mc.approvals.open()) == 1


def test_an_approved_irreversible_capability_then_runs():
    _, task, _ = run_task(
        "Desktop.ExecuteCommand", {"command": ["echo", "x"]}, approve=("execute_command",)
    )

    assert task.state is TaskState.COMPLETED


def test_launching_through_the_runtime_needs_approval_too():
    mc, _, _ = run_task("Desktop.LaunchApplication", {"application": "git"})

    assert len(mc.approvals.open()) == 1
    assert mc.approvals.open()[0].capability == "Desktop.LaunchApplication"


# ---- the read-only surface the Dashboard uses ----------------------------


def test_the_plugin_exposes_a_cached_inventory():
    plugin, _ = plugin_for(machine())

    assert plugin.cached_inventory is None

    invoke(plugin, "list_installed_software")

    assert plugin.cached_inventory is not None


def test_reading_the_inventory_never_triggers_a_scan():
    """The Dashboard calls this on every render. A render that scanned the
    machine would mean looking at the screen changes what it reports."""
    probe = machine()
    plugin, _ = plugin_for(probe)
    invoke(plugin, "list_installed_software")
    before = len(probe.ran)

    for _ in range(5):
        assert plugin.cached_inventory is not None

    assert len(probe.ran) == before


def test_inventory_can_be_refreshed_explicitly():
    probe = machine()
    plugin, _ = plugin_for(probe)
    plugin.inventory()
    before = len(probe.ran)

    plugin.inventory(refresh=True)

    assert len(probe.ran) > before


# ---- the Dashboard (Deliverables 4 and 9) --------------------------------


def dashboard_for(probe: FakeProbe):
    from master_agent.dashboard.app import build_dashboard

    mc, plugin, _, _ = registered_world(probe)
    invoke(plugin, "list_installed_software")
    return build_dashboard(
        mission_control=mc,
        inventory_provider=lambda: plugin.cached_inventory,
        writer=lambda _t: None,
    )


def test_machine_readiness_appears_on_the_founder_page():
    frame = dashboard_for(machine()).render()

    assert "MACHINE READINESS" in frame


def test_readiness_shows_installed_applications_as_ready():
    frame = dashboard_for(machine()).render()

    assert "Python" in frame
    assert "Git" in frame


def test_readiness_without_a_desktop_executive_says_so():
    from master_agent.dashboard.app import build_dashboard

    frame = build_dashboard(
        mission_control=MissionControl(), writer=lambda _t: None
    ).render()

    assert "no machine scan yet" in frame


def test_running_applications_are_listed():
    frame = dashboard_for(machine(running=[ProcessInfo(pid=1, name="chrome.exe")])).render()

    assert "Running" in frame
    assert "Chrome" in frame


def test_installed_ai_software_is_listed():
    probe = machine(on_path={"ollama": "/usr/bin/ollama"}, versions={"ollama": "0.1.2"})
    frame = dashboard_for(probe).render()

    assert "AI software" in frame
    assert "Ollama" in frame


def test_the_machine_view_is_in_the_serialised_view_model():
    from master_agent.dashboard.founder import build_founder_view

    view = build_founder_view(dashboard_for(machine()).snapshot())

    assert view.machine.available is True
    assert view.machine.installed_count == 2


def test_a_failing_inventory_provider_becomes_absent_data():
    from master_agent.dashboard.app import build_dashboard

    def explode():
        raise RuntimeError("probe died")

    dashboard = build_dashboard(
        mission_control=MissionControl(),
        inventory_provider=explode,
        writer=lambda _t: None,
    )

    assert "MACHINE READINESS" in dashboard.render()


# ---- the launcher --------------------------------------------------------


def test_the_launcher_registers_the_desktop_executive(tmp_path):
    from master_agent.launcher.boot import build_system

    system = build_system(
        state_dir=tmp_path / "state", dashboard_kwargs={"writer": lambda _t: None}
    )

    assert DESKTOP_EXECUTIVE_ID in system.mission_control.executives.ids()


def test_the_launcher_reports_desktop_capabilities(tmp_path):
    from master_agent.launcher.boot import build_system

    system = build_system(
        state_dir=tmp_path / "state", dashboard_kwargs={"writer": lambda _t: None}
    )

    assert "Desktop.ListInstalledSoftware" in system.mission_control.capabilities.names()


def test_the_launcher_submits_a_machine_scan():
    from master_agent.launcher.main import machine_scan_objective

    objective = machine_scan_objective()

    assert [t.capability for t in objective.tasks] == [
        "Desktop.ListInstalledSoftware",
        "Desktop.ListRunningProcesses",
    ]


def test_the_scan_can_be_skipped():
    from master_agent.launcher.main import build_parser

    assert build_parser().parse_args(["--no-scan"]).no_scan is True


def test_the_scan_needs_no_approval():
    """Both scan capabilities are READ_ONLY, so a founder is never asked
    just to let the system look at their machine."""
    plugin, _ = plugin_for(machine())
    tiers = {c.name: c.risk_tier for c in plugin.manifest.capabilities}

    assert tiers["list_installed_software"] is RiskTier.READ_ONLY
    assert tiers["list_running_processes"] is RiskTier.READ_ONLY


# ---- architecture purity (Rules 2 and 11) --------------------------------

#: Vocabulary that would mean this Executive had started *choosing*.
#: Deliberately excludes two near-misses that are legitimate:
#:   - "Anthropic" appears in `catalog.py` only as a Windows install path
#:     (`%LOCALAPPDATA%\AnthropicClaude\...`) -- a fact about where a
#:     file lives, not knowledge of an API. Pinned by its own test below.
#:   - "recommended" marks developer tooling for Deliverable 4's "Missing
#:     Recommended Applications". It never applies to an AI application,
#:     which `test_no_ai_application_is_ever_marked_recommended` enforces.
FORBIDDEN_VOCABULARY = (
    "openrouter",
    "gemini",
    "gpt-",
    "benchmark",
    "provider ranking",
    "model cost",
    "token cost",
    "quality score",
    "api key",
    "ranked",
)


@pytest.mark.parametrize("word", FORBIDDEN_VOCABULARY)
def test_the_desktop_executive_knows_nothing_about_ai_selection(word):
    """MB030 Rules 2 and 11. The Desktop Executive reports that Ollama is
    installed; it has no idea whether that is a good idea."""
    offenders = []
    for path in DESKTOP_DIR.rglob("*.py"):
        text = path.read_text(encoding="utf-8").lower()
        # Docstrings say what this must NOT do; strip comment lines so the
        # prohibition itself does not trip its own test.
        code = "\n".join(
            line for line in text.splitlines() if not line.strip().startswith("#")
        )
        if word in code:
            offenders.append(path.name)
    assert offenders == [], f"'{word}' appears in {offenders}"


def test_no_ai_application_is_ever_marked_recommended():
    """`recommended` exists for Deliverable 4's developer tooling. The
    moment it were applied to an AI application, the Desktop Executive
    would be recommending intelligence -- which is the Broker's job."""
    for spec in catalog.CATALOG:
        if spec.category == catalog.AI:
            assert not spec.recommended, f"{spec.key} recommends AI software"


def test_the_only_vendor_name_is_a_filesystem_path():
    """"Anthropic" appears once, inside a Windows install path. That is a
    fact about where a file lives, not knowledge of a provider."""
    hits = []
    for path in DESKTOP_DIR.rglob("*.py"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if "anthropic" in line.lower():
                hits.append(line.strip())

    assert hits, "the catalogue should still know where Claude Desktop installs"
    for line in hits:
        assert "%LOCALAPPDATA%" in line or "windows_paths" in line


def test_the_catalogue_never_orders_ai_applications_by_preference():
    """A list is not a ranking. Asserted behaviourally rather than by
    grepping for "rank", because the module docstring says "no ranking"
    and a text search would trip over the prohibition itself."""
    ai_order = [spec.key for spec in catalog.ai_applications()]
    catalogue_order = [
        spec.key for spec in catalog.CATALOG if spec.category == catalog.AI
    ]

    assert ai_order == catalogue_order, "AI applications were reordered"


def test_the_desktop_package_imports_no_ai_machinery():
    for path in DESKTOP_DIR.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            module = ""
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
            elif isinstance(node, ast.Import):
                module = node.names[0].name
            assert "model_router" not in module
            assert "providers" not in module


def test_no_automation_capability_exists():
    """Deliverable 7: no click, type, mouse, OCR, vision, or keyboard."""
    plugin, _ = plugin_for(machine())
    names = " ".join(c.name for c in plugin.manifest.capabilities)

    for banned in ("click", "type_", "mouse", "ocr", "vision", "keyboard", "screenshot"):
        assert banned not in names


# ---- the null and real probes --------------------------------------------


def test_a_null_probe_finds_nothing_rather_than_crashing():
    inventory = discover(NullSystemProbe())

    assert inventory.installed() == []
    assert inventory.processes == []


def test_a_plugin_with_no_probe_still_answers():
    permissions = PermissionSystem()
    plugin = DesktopPlugin(LocalExecutor(permissions))
    plugin._context.probe = NullSystemProbe()

    result = invoke(plugin, "is_installed", {"application": "git"})

    assert result.success is True
    assert result.output["installed"] is False


def test_the_real_probe_reports_a_platform():
    assert RealSystemProbe().platform


def test_the_real_probe_survives_a_missing_executable():
    result = RealSystemProbe().run(["definitely-not-a-real-binary-xyz"])

    assert result.ok is False
    assert result.error


def test_the_real_probe_returns_none_for_an_unknown_executable():
    assert RealSystemProbe().which("definitely-not-a-real-binary-xyz") is None


def test_the_real_probe_handles_a_bad_path():
    assert RealSystemProbe().exists("\x00not-a-path") is False


# ═══════════════ Universal Windows Environment Discovery ═══════════════
#
# The catalog is not the source of truth; the Windows machine is
# (Kalpavriksha — Critical Desktop Executive Repair, Section 1). These
# tests exercise `discover()`'s merge across every real evidence source
# `RealSystemProbe` can supply — `Get-StartApps`, `Get-AppxPackage`, the
# registry uninstall keys, and running processes — entirely through
# `FakeProbe`, so nothing here shells out.


def test_running_process_alone_proves_installed():
    """Section 8: a real running process, with nothing else matching it,
    must still resolve the application as installed — the exact Claude
    Desktop case (a catalog path that was simply wrong)."""
    probe = machine(on_path={}, running=[ProcessInfo(pid=1, name="git.exe", owner="git")])

    found = discover(probe).get("git")

    assert found.installed is True
    assert found.running is True
    assert found.install_source == "running_process"
    assert found.launch_target is None  # honestly: nothing to launch it with


def test_msix_discovery_resolves_a_catalog_application():
    """Section 2B/5: an application with no PATH/known-path match is
    still found via `Get-AppxPackage`, with a real launch target."""
    probe = machine(store_apps=[{
        "Name": "Cursor", "PackageFullName": "Cursor_1.0.0_x64__abc",
        "PackageFamilyName": "Cursor_abc", "Publisher": "CN=Cursor",
        "Version": "1.0.0", "InstallLocation": None,
        "AppUserModelID": "Cursor_abc!App",
    }])

    found = discover(probe).get("cursor")

    assert found.installed is True
    assert found.install_source == "msix"
    assert found.launch_target == "shell:AppsFolder\\Cursor_abc!App"
    assert found.package_family == "Cursor_abc"


def test_start_menu_discovery_resolves_a_catalog_application():
    """Section 2B/5: `Get-StartApps` is the strongest static source —
    resolves an application even when neither PATH nor Store/AppX
    enumeration found it."""
    probe = machine(start_apps=[{"Name": "Claude", "AppID": "Claude_pzs8sxrjxfjjc!Claude"}])

    found = discover(probe).get("claude_desktop")

    assert found.installed is True
    assert found.install_source == "start_menu"
    assert found.launch_target == "shell:AppsFolder\\Claude_pzs8sxrjxfjjc!Claude"
    assert found.app_user_model_id == "Claude_pzs8sxrjxfjjc!Claude"


def test_start_menu_raw_path_entry_launches_directly_not_via_appsfolder():
    """Section 7: some legacy shortcuts report a raw file path instead of
    a real AppUserModelID (observed live: Ollama) — `shell:AppsFolder`
    cannot resolve that, so the launch target must be the path itself."""
    probe = machine(start_apps=[{
        "Name": "Ollama", "AppID": r"C:\Users\Founder\AppData\Local\Programs\Ollama\ollama app.exe",
    }])

    found = discover(probe).get("ollama")

    assert found.install_source == "start_menu"
    assert found.launch_target == r"C:\Users\Founder\AppData\Local\Programs\Ollama\ollama app.exe"
    assert found.app_user_model_id is None  # it was never a real AppUserModelID


def test_registry_discovery_resolves_a_catalog_application_hklm_and_hkcu_alike():
    """Sections 2D/15.4/15.5: `discover()` treats every registry hive
    `get_uninstall_apps()` already merges (HKLM, HKLM\\WOW6432Node, HKCU)
    identically — a hive distinction that lives in `RealSystemProbe`'s own
    three separate queries (see `test_registry_probe_queries_both_hives`
    below), not in the merge logic under test here."""
    probe = machine(uninstall_apps=[{
        "DisplayName": "Docker Desktop", "Publisher": "Docker Inc.",
        "DisplayVersion": "4.74.0", "InstallLocation": r"C:\Program Files\Docker\Docker",
        "UninstallString": "...",
    }])

    found = discover(probe).get("docker")

    assert found.installed is True
    assert found.install_source == "registry"
    assert found.version == "4.74.0"
    # Honest: an uninstall entry's `UninstallString` is for removing
    # software, not launching it — no launch target is fabricated.
    assert found.launch_target is None
    assert found.launchable is False


def test_registry_probe_queries_both_hives():
    """Sections 2D/15.4/15.5, at the probe level: `get_uninstall_apps()`
    genuinely queries HKLM (both 64- and 32-bit views) and HKCU, not just
    one hive — regression coverage for the missing-quote/missing-backslash
    bugs found live in this method (fixed this session)."""
    probe = RealSystemProbe.__new__(RealSystemProbe)
    probe._timeout = 5.0  # platform is a read-only property (real sys.platform)
    queried_paths: list[str] = []

    def _fake_run(command, timeout=None):
        queried_paths.append(command[3])
        return CommandResult(ok=True, output="[]")

    probe._run = _fake_run
    probe.get_uninstall_apps()

    assert any("HKLM:\\SOFTWARE\\Microsoft" in p and "WOW6432Node" not in p for p in queried_paths)
    assert any("WOW6432Node" in p for p in queried_paths)
    assert any("HKCU:\\SOFTWARE\\Microsoft" in p for p in queried_paths)
    # The exact bug found live: a missing `\` before the wildcard meant
    # `Uninstall*` (matches nothing) instead of `Uninstall\*` (every
    # child key) — assert the fix, not just that a query happened.
    assert all("Uninstall\\*'" in p for p in queried_paths)


def test_evidence_precedence_start_menu_outranks_registry_and_running_alone():
    """Section 4: when multiple sources agree on the same application,
    the strongest wins the launch target, and every corroborating source
    still appears in `discovery_sources`."""
    probe = machine(
        running=[ProcessInfo(pid=1, name="git.exe", owner="git")],
        start_apps=[{"Name": "Git", "AppID": "Git.Bash"}],
        uninstall_apps=[{
            "DisplayName": "Git", "Publisher": "Git", "DisplayVersion": "2.44.0",
            "InstallLocation": None, "UninstallString": "...",
        }],
    )

    found = discover(probe).get("git")

    assert found.install_source == "start_menu"  # not "registry", not bare "running_process"
    assert found.running is True
    assert "running_process" in found.discovery_sources
    assert "start_menu" in found.discovery_sources


def test_catalog_path_still_wins_when_nothing_else_matches():
    """Section 4: a verified PATH/known-path resolution — the pre-
    existing mechanism — is still honoured when no Windows-wide source
    corroborates it, so this mission adds discovery, it does not remove
    any that already worked."""
    probe = machine(on_path={"git": "/usr/bin/git"}, versions={"git": "git version 2.44.0"})

    found = discover(probe).get("git")

    assert found.install_source == "catalog_path"
    assert found.launch_target == "/usr/bin/git"


def test_a_catalog_path_conflict_is_resolved_in_favour_of_windows_evidence():
    """Section 4's own worked example: a wrong/stale catalog path must
    never override real Start Menu evidence that a matching, different
    install exists."""
    probe = machine(
        on_path={},  # the catalog's own PATH guess finds nothing
        start_apps=[{"Name": "Chrome", "AppID": "Chrome"}],
    )

    found = discover(probe).get("chrome")

    assert found.installed is True
    assert found.install_source == "start_menu"


def test_unknown_application_with_no_catalog_entry_is_still_discovered():
    """Section 6 — the core universality claim: an application no
    developer anticipated must still appear, distinctly flagged as
    catalog-free."""
    probe = machine(start_apps=[{"Name": "MyCoolApp", "AppID": "MyCoolApp.Vendor!App"}])

    inventory = discover(probe)

    assert inventory.get("mycoolapp") is None  # no catalog key claims it
    matches = inventory.get_unknown("MyCoolApp")
    assert len(matches) == 1
    assert matches[0].catalog_metadata_present is False
    assert matches[0].launch_target == "shell:AppsFolder\\MyCoolApp.Vendor!App"
    assert matches[0].installed is True


def test_running_process_with_no_catalog_entry_at_all_does_not_crash():
    """Section 8's principle taken to its edge: `attribute_processes()`
    already leaves a truly unrecognised process `owner=None` rather than
    guessing — `discover()` must not choke on that, only catalog-known
    running processes become `RUNNING_PROCESS`-sourced records."""
    probe = machine(running=[ProcessInfo(pid=99, name="totally_unknown.exe", owner=None)])

    inventory = discover(probe)

    assert all(p.owner is not None or p.name == "totally_unknown.exe" for p in inventory.processes)
    assert inventory.get("git").running is False  # unaffected


def test_launch_target_resolution_prefers_appsfolder_for_true_app_ids():
    """Section 7's launch-order claim, at the unit level: a real
    AppUserModelID resolves to `shell:AppsFolder`, never treated as a
    raw path."""
    from master_agent.desktop.inventory import _start_app_launch_target, _is_raw_path

    assert _is_raw_path("Claude_pzs8sxrjxfjjc!Claude") is False
    assert _start_app_launch_target("Claude_pzs8sxrjxfjjc!Claude") == "shell:AppsFolder\\Claude_pzs8sxrjxfjjc!Claude"
    assert _is_raw_path(r"C:\Program Files\App\app.exe") is True
    assert _start_app_launch_target(r"C:\Program Files\App\app.exe") == r"C:\Program Files\App\app.exe"


def test_deep_scan_is_skipped_on_the_fast_path():
    """Section 9's FAST PATH: `deep=False` must not call any of the
    three Windows-wide sources — asserted by making each one raise if
    called, not merely by asserting on the result."""
    class ExplodingProbe(FakeProbe):
        def get_start_apps(self):
            raise AssertionError("get_start_apps() must not run on the fast path")

        def get_store_apps(self):
            raise AssertionError("get_store_apps() must not run on the fast path")

        def get_uninstall_apps(self):
            raise AssertionError("get_uninstall_apps() must not run on the fast path")

    probe = ExplodingProbe(on_path={"git": "/usr/bin/git"}, versions={"git": "git version 2.44.0"})

    inventory = discover(probe, deep=False)

    assert inventory.get("git").installed is True
    assert inventory.unknown_applications == []


def test_context_cache_upgrades_from_shallow_to_deep_on_demand():
    """Section 9/12's cache-coherence requirement: a fast `refresh()`
    must not silently strand a later `inventory(deep=True)` caller with
    stale, shallow data — the exact bug that would have made `execute()`
    miss Claude Desktop's Start Menu match after any interaction action's
    own fast `refresh()` ran first."""
    probe = machine(start_apps=[{"Name": "Claude", "AppID": "Claude_pzs8sxrjxfjjc!Claude"}])
    context = DesktopContext(probe)

    context.refresh(deep=False)  # e.g. `focus()`'s own fast-path refresh
    assert context.cached.get("claude_desktop").install_source != "start_menu"

    deep = context.inventory(deep=True)  # e.g. `execute()`'s own call

    assert deep.get("claude_desktop").install_source == "start_menu"


def test_context_cache_is_not_rescanned_once_deep():
    """The other half of Section 9: once deep data is cached, a further
    `inventory(deep=True)` call must be free — asserted the same way the
    fast-path test above is, by making the expensive sources explode if
    called again."""
    probe = machine(start_apps=[{"Name": "Claude", "AppID": "Claude_pzs8sxrjxfjjc!Claude"}])
    context = DesktopContext(probe)
    context.inventory(deep=True)

    def _explode():
        raise AssertionError("a cached deep inventory must not be re-scanned")

    probe.get_start_apps = _explode  # type: ignore[method-assign]

    again = context.inventory(deep=True)
    assert again.get("claude_desktop").install_source == "start_menu"


def test_installed_running_visible_are_distinguishable_states():
    """Section 11: NOT_FOUND / INSTALLED / RUNNING must not collapse
    into one `installed=True/False` boolean."""
    not_found = discover(machine()).get("lm_studio")
    installed_not_running = discover(machine(on_path={"git": "/usr/bin/git"})).get("git")
    installed_and_running = discover(machine(
        on_path={"git": "/usr/bin/git"},
        running=[ProcessInfo(pid=1, name="git.exe", owner="git")],
    )).get("git")

    assert not_found.status == MISSING and not_found.running is False
    assert installed_not_running.installed is True and installed_not_running.running is False
    assert installed_and_running.installed is True and installed_and_running.running is True
