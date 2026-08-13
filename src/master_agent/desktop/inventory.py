"""Machine inventory — what is installed, what is running (MB030).

Pure logic over whatever a `SystemProbe` reports. No subprocess calls, no
filesystem access, no platform branching beyond asking the probe what
platform it is.

**Facts only** (Deliverable 10). An application is installed or it is not;
a version is what the tool reported. Nothing here says a version is too
old, that one application is better than another, or that anything should
be installed — those are judgements, and the Desktop Executive does not
make them.
"""
from __future__ import annotations

import dataclasses
import os
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, List, Optional, Tuple

from master_agent.desktop.catalog import CATALOG, ApplicationSpec
from master_agent.desktop.probe import ProcessInfo, SystemProbe

INSTALLED = "installed"
MISSING = "missing"
UNAVAILABLE = "unavailable"

#: How much of a tool's error output is worth keeping as a hint.
DETAIL_LIMIT = 70

_VERSION_PATTERN = re.compile(r"\d+\.\d+(?:\.\d+)?(?:[-+][\w.]+)?")

#: Characters a UTF-16 payload leaves behind when a single-byte codepage
#: decodes it — see `repair_wide_text`.
_WIDE_FILLERS = (chr(0), " ", chr(255))


#: Windows evidence, strongest first (Universal Windows Environment
#: Discovery). `discover()` picks the first source that actually matched
#: an application to decide its `install_source`/`launch_target`/
#: `confidence` — a later, weaker source can still add itself to
#: `discovery_sources` and set `running=True`, but never override a
#: stronger source's launch target. "Running, no resolvable path" ranks
#: above catalog/registry guesses deliberately: a real, currently-running
#: process is stronger evidence an application exists than any static
#: metadata about where it was expected to be — this is the exact
#: Claude Desktop case (`RUNNING_PROCESS` when nothing else matches).
RUNNING_PROCESS = "running_process"
START_MENU = "start_menu"
MSIX = "msix"
REGISTRY = "registry"
CATALOG_PATH = "catalog_path"
PATH_GUESS = "path"
NONE_SOURCE = "none"

_SOURCE_CONFIDENCE = {
    RUNNING_PROCESS: "high",
    START_MENU: "high",
    MSIX: "high",
    REGISTRY: "medium",
    CATALOG_PATH: "medium",
    PATH_GUESS: "low",
    NONE_SOURCE: "none",
}


@dataclass(frozen=True)
class InstalledApplication:
    """Deliverable 2's shape, extended (Universal Windows Environment
    Discovery) with the normalized fields real multi-source discovery
    needs. Every new field defaults to something a catalog-only,
    pre-discovery caller already produces, so nothing that reads `.status`
    /`.version`/`.path`/`.launchable`/`.healthy`/`.detail`/`.version_args`
    needs to change.
    """

    key: str
    name: str
    category: str
    status: str = MISSING
    version: str | None = None
    path: str | None = None
    launchable: bool = False
    healthy: bool = False
    detail: str = ""
    version_args: Tuple[str, ...] = field(default_factory=tuple)
    # ---- Universal Windows Environment Discovery -----------------------
    aliases: Tuple[str, ...] = field(default_factory=tuple)
    executable_name: str | None = None
    package_name: str | None = None
    package_family: str | None = None
    app_user_model_id: str | None = None
    publisher: str | None = None
    #: What actually resolved this record: `RUNNING_PROCESS`, `START_MENU`,
    #: `MSIX`, `REGISTRY`, `CATALOG_PATH`, `PATH_GUESS`, or `NONE_SOURCE`.
    install_source: str = NONE_SOURCE
    #: What `execute()` should hand to the launcher — either
    #: `explorer.exe shell:AppsFolder\\<AppID>` or a verified executable
    #: path. `None` when nothing discoverable can actually launch this.
    launch_target: str | None = None
    #: Every source that corroborated this record, not just the one that
    #: won `install_source` — e.g. `(RUNNING_PROCESS, START_MENU)` when a
    #: founder already has the app open.
    discovery_sources: Tuple[str, ...] = field(default_factory=tuple)
    confidence: str = "none"
    #: Whether `catalog.py` has a hand-written `ApplicationSpec` for this
    #: key. `False` for an application Windows discovered that no
    #: developer anticipated — Section 6's "unknown applications must
    #: also be discoverable" is what this flags.
    catalog_metadata_present: bool = False
    running: bool = False

    @property
    def installed(self) -> bool:
        return self.status == INSTALLED

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "category": self.category,
            "status": self.status,
            "installed": self.installed,
            "version": self.version,
            "path": self.path,
            "launchable": self.launchable,
            "healthy": self.healthy,
            "detail": self.detail,
            "version_args": self.version_args,
            "aliases": self.aliases,
            "executable_name": self.executable_name,
            "package_name": self.package_name,
            "package_family": self.package_family,
            "app_user_model_id": self.app_user_model_id,
            "publisher": self.publisher,
            "install_source": self.install_source,
            "launch_target": self.launch_target,
            "discovery_sources": self.discovery_sources,
            "confidence": self.confidence,
            "catalog_metadata_present": self.catalog_metadata_present,
            "running": self.running,
        }


@dataclass(frozen=True)
class MachineInventory:
    """One snapshot of the machine. Frozen for the same reason
    `DashboardSnapshot` is: it describes a moment that has passed.
    """

    applications: List[InstalledApplication] = field(default_factory=list)
    #: Section 6: real, Windows-discovered software with no
    #: `catalog.py` entry — kept separate from `applications` rather than
    #: merged in, so every existing caller that iterates `.applications`
    #: expecting catalog-known software (Dashboard, `ai_applications()`,
    #: `missing_recommended()`) is unaffected by however many unrelated
    #: Start-Menu tiles (MMC snap-ins, control panel items, help files)
    #: a real machine happens to expose. Still real, still queryable —
    #: just not silently widening what "the inventory" already meant.
    unknown_applications: List[InstalledApplication] = field(default_factory=list)
    processes: List[ProcessInfo] = field(default_factory=list)
    platform: str = "unknown"
    captured_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def get(self, key: str) -> InstalledApplication | None:
        for application in self.applications:
            if application.key == key:
                return application
        for application in self.unknown_applications:
            if application.key == key:
                return application
        return None

    def get_unknown(self, name: str) -> List[InstalledApplication]:
        """Case-insensitive substring lookup by display name — an unknown
        application has no catalog key a caller could already know."""
        needle = name.strip().lower()
        return [
            a for a in self.unknown_applications
            if needle in a.name.lower() or a.name.lower() in needle
        ]

    def installed(self) -> List[InstalledApplication]:
        return [a for a in self.applications if a.installed]

    def missing(self) -> List[InstalledApplication]:
        return [a for a in self.applications if a.status == MISSING]

    def unavailable(self) -> List[InstalledApplication]:
        """Found but not usable. Distinct from missing: one is absent, the
        other is broken, and a founder should be told which."""
        return [a for a in self.applications if a.status == UNAVAILABLE]

    def missing_recommended(self) -> List[InstalledApplication]:
        from master_agent.desktop.catalog import BY_KEY

        return [
            a
            for a in self.missing()
            if (spec := BY_KEY.get(a.key)) is not None and spec.recommended
        ]

    def ai_applications(self) -> List[InstalledApplication]:
        """Deliverable 8: which AI software is present. A grouping, never
        a shortlist — nothing here decides what should be used."""
        return [a for a in self.applications if a.category == "ai"]

    def running(self, key: str) -> List[ProcessInfo]:
        return [p for p in self.processes if p.owner == key]

    def as_dict(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "captured_at": self.captured_at.isoformat(),
            "applications": [a.as_dict() for a in self.applications],
            "unknown_applications": [a.as_dict() for a in self.unknown_applications],
            "processes": [p.as_dict() for p in self.processes],
        }


def repair_wide_text(raw: str) -> str:
    """Undo a UTF-16 payload decoded as a single-byte codepage.

    Found by running this against a real Windows machine: `wsl --version`
    emits UTF-16LE, which `subprocess` in text mode decodes as cp1252,
    producing ``W S L   v e r s i o n :   2 . 7 . 3 . 0`` — every real
    character followed by its high byte. Detected by looking for that
    exact alternation rather than by guessing encodings, and returned
    untouched when the pattern does not hold.
    """
    if len(raw) < 8:
        return raw
    tail = raw[1::2]
    fillers = sum(1 for char in tail if char in _WIDE_FILLERS)
    if fillers < len(tail) * 0.8:
        return raw
    return raw[::2]


def extract_version(raw: str) -> str | None:
    """Pull a version out of whatever the tool printed, or return None.

    **Returning None is the important half.** An earlier draft fell back
    to "whatever was printed", and a real machine scan filled the founder's
    inventory with ``not found: code`` and ``At line:1 char:3`` sitting in
    the version column — error text presented as fact. A version this
    cannot parse is not a version.
    """
    if not raw:
        return None
    text = repair_wide_text(raw.strip()).strip()
    if not text:
        return None
    first = text.splitlines()[0].strip()
    match = _VERSION_PATTERN.search(first)
    return match.group(0) if match else None


def one_line(text: str, limit: int = DETAIL_LIMIT) -> str:
    """A detail is a hint, not a transcript. PowerShell answers
    `--version` with a multi-line parser error, and pasting all of it into
    an inventory row makes the whole panel unreadable.
    """
    if not text:
        return ""
    repaired = repair_wide_text(text.strip()).strip()
    if not repaired:
        return ""
    return repaired.splitlines()[0].strip()[:limit]


def _version_of(
    spec: ApplicationSpec, executable: str, probe: SystemProbe, read_version: bool
) -> tuple[str | None, bool, str]:
    if not read_version:
        return None, True, ""

    if spec.version_args is None:
        # Desktop Executive Foundation 1.0: some executables (GUI-only,
        # no CLI at all — `notepad.exe`) have no way to be asked for a
        # version that does not also open a real, visible window. `None`
        # is that fact declared honestly; skipping the probe here is what
        # keeps a routine inventory scan from flashing one open.
        return None, True, "no version check available for this application"

    result = probe.run([executable, *spec.version_args])
    # Some tools (java, notably) print their version to stderr and exit
    # non-zero, so a version is looked for wherever it appears rather than
    # only after a clean exit.
    version = extract_version(result.output) or extract_version(result.error)
    if version:
        return version, True, ""

    # Installed and answering, just not in a shape this can read.
    # `healthy` stays True when the command ran at all: "we could not
    # parse the version" is a different fact from "this is broken", and a
    # founder who sees a red mark beside a working tool learns to ignore
    # red marks.
    if result.ok:
        return None, True, "installed; version not reported in a readable form"
    return None, False, one_line(result.error) or "did not report a version"


def discover_application(
    spec: ApplicationSpec, probe: SystemProbe, read_version: bool = True
) -> InstalledApplication:
    """One application, as the machine reports it.

    Order matters: PATH first (an executable that resolves is launchable),
    then known install locations (a GUI application that never joined the
    PATH).
    """
    for executable in spec.executables:
        resolved = probe.which(executable)
        if resolved:
            version, healthy, detail = _version_of(
                spec, executable, probe, read_version
            )
            return InstalledApplication(
                key=spec.key,
                name=spec.label,
                category=spec.category,
                status=INSTALLED,
                version=version,
                path=resolved,
                launchable=True,
                healthy=healthy,
                detail=detail,
                version_args=spec.version_args,
            )

    for candidate in spec.paths_for(probe.platform):
        if probe.exists(candidate):
            return InstalledApplication(
                key=spec.key,
                name=spec.label,
                category=spec.category,
                status=INSTALLED,
                path=os.path.expandvars(candidate),
                launchable=True,
                healthy=True,
                detail="found at a known install path; not on PATH",
                version_args=spec.version_args,
            )

    return InstalledApplication(
        key=spec.key,
        name=spec.label,
        category=spec.category,
        status=MISSING,
        detail=spec.notes or "not found on PATH or at any known install path",
        version_args=spec.version_args,
    )


_RAW_PATH_PATTERN = re.compile(r"^[A-Za-z]:\\")


def _is_raw_path(app_id: str) -> bool:
    """`Get-StartApps`' `AppID` is a real AppUserModelID for most
    entries (`shell:AppsFolder\\<AppID>` launches them), but for some
    legacy shortcuts Windows has no AppUserModelID to report and falls
    back to the shortcut's raw target path instead (observed live:
    Ollama's Start Menu entry reports its `AppID` as
    `C:\\Users\\...\\ollama app.exe`, not an AppUserModelID). `shell:
    AppsFolder` cannot resolve a raw path, so this decides which launch
    mechanism a given `AppID` actually needs.
    """
    return bool(_RAW_PATH_PATTERN.match(app_id))


def _start_app_launch_target(app_id: str) -> str:
    if _is_raw_path(app_id):
        return app_id
    return f"shell:AppsFolder\\{app_id}"


def _label_matches(label: str, candidate_name: str) -> bool:
    a, b = label.strip().lower(), (candidate_name or "").strip().lower()
    if not a or not b:
        return False
    return a in b or b in a


def _claim_match(
    label: str, candidates: list[dict], claimed_ids: set[int], name_field: str
) -> dict | None:
    """First unclaimed candidate whose `name_field` matches `label` —
    substring, either direction, the same tolerant match `discover()`
    already used for Store apps, now shared across every source."""
    for candidate in candidates:
        if id(candidate) in claimed_ids:
            continue
        if _label_matches(label, candidate.get(name_field, "")):
            claimed_ids.add(id(candidate))
            return candidate
    return None


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")
    return slug or "unknown"


def _resolve_one(
    spec: ApplicationSpec,
    probe: SystemProbe,
    read_versions: bool,
    running_keys: set[str],
    start_apps: list[dict],
    store_apps: list[dict],
    uninstall_apps: list[dict],
    matched_start_ids: set[int],
    matched_store_ids: set[int],
    matched_uninstall_ids: set[int],
) -> InstalledApplication:
    """One catalog spec, resolved against every Windows evidence source
    with the precedence Universal Windows Environment Discovery requires:
    a matched Start Menu entry outranks bare MSIX/AppX (Get-StartApps is
    Windows' own "how would you actually launch this" answer, a stronger
    claim than `Get-AppxPackage` enumerating every installed *package*
    including ones with no user-facing launch surface at all), which
    outranks a verified catalog path, which outranks a registry
    uninstall entry (real evidence something was installed, but a
    `UninstallString` is for removing software, not launching it — rarely
    a usable launch target). A real running process is folded in as
    corroborating evidence at every tier, and is what alone still proves
    "installed" when nothing else matches at all — the exact Claude
    Desktop case (`RUNNING_PROCESS`) this mission exists to fix.
    """
    is_running = spec.key in running_keys
    running_source = (RUNNING_PROCESS,) if is_running else ()

    start_match = _claim_match(spec.label, start_apps, matched_start_ids, "Name")
    if start_match is not None:
        app_id = start_match["AppID"]
        launch_target = _start_app_launch_target(app_id)
        return InstalledApplication(
            key=spec.key, name=spec.label, category=spec.category,
            status=INSTALLED,
            path=launch_target if _is_raw_path(app_id) else None,
            launchable=True, healthy=True,
            detail="found via Start Menu discovery",
            version_args=spec.version_args,
            app_user_model_id=None if _is_raw_path(app_id) else app_id,
            install_source=START_MENU, launch_target=launch_target,
            discovery_sources=running_source + (START_MENU,),
            confidence=_SOURCE_CONFIDENCE[START_MENU],
            catalog_metadata_present=True, running=is_running,
        )

    store_match = _claim_match(spec.label, store_apps, matched_store_ids, "Name")
    if store_match is not None:
        app_user_model_id = store_match.get("AppUserModelID")
        launch_target = f"shell:AppsFolder\\{app_user_model_id}" if app_user_model_id else None
        return InstalledApplication(
            key=spec.key, name=spec.label, category=spec.category,
            status=INSTALLED,
            path="explorer.exe" if launch_target else None,
            launchable=bool(launch_target), healthy=bool(launch_target),
            detail=(
                "found via Store/AppX discovery" if launch_target
                else "found via Store/AppX discovery but missing AppUserModelID"
            ),
            version=store_match.get("Version"), version_args=spec.version_args,
            package_name=store_match.get("PackageFullName"),
            package_family=store_match.get("PackageFamilyName"),
            app_user_model_id=app_user_model_id, publisher=store_match.get("Publisher"),
            install_source=MSIX, launch_target=launch_target,
            discovery_sources=running_source + (MSIX,),
            confidence=_SOURCE_CONFIDENCE[MSIX],
            catalog_metadata_present=True, running=is_running,
        )

    catalog_app = discover_application(spec, probe, read_version=read_versions)
    if catalog_app.installed:
        return dataclasses.replace(
            catalog_app,
            install_source=CATALOG_PATH, launch_target=catalog_app.path,
            discovery_sources=running_source + (CATALOG_PATH,),
            confidence=_SOURCE_CONFIDENCE[CATALOG_PATH],
            catalog_metadata_present=True, running=is_running,
        )

    registry_match = _claim_match(spec.label, uninstall_apps, matched_uninstall_ids, "DisplayName")
    if registry_match is not None:
        return InstalledApplication(
            key=spec.key, name=spec.label, category=spec.category,
            status=INSTALLED,
            path=registry_match.get("InstallLocation"),
            launchable=False, healthy=True,
            detail="found via registry uninstall entry; no confirmed launch target",
            version=registry_match.get("DisplayVersion"), version_args=spec.version_args,
            publisher=registry_match.get("Publisher"),
            install_source=REGISTRY, launch_target=None,
            discovery_sources=running_source + (REGISTRY,),
            confidence=_SOURCE_CONFIDENCE[REGISTRY],
            catalog_metadata_present=True, running=is_running,
        )

    if is_running:
        # Windows evidence is the source of truth, never the catalog
        # (Section 1): a real process answering to this application's
        # own `process_names` is "installed" regardless of whether any
        # static source could locate where it lives.
        return InstalledApplication(
            key=spec.key, name=spec.label, category=spec.category,
            status=INSTALLED, path=None, launchable=False, healthy=True,
            detail=(
                "a matching process is running, but no Start Menu, MSIX, "
                "catalog path, or registry entry was found for it"
            ),
            version_args=spec.version_args,
            install_source=RUNNING_PROCESS, launch_target=None,
            discovery_sources=(RUNNING_PROCESS,),
            confidence=_SOURCE_CONFIDENCE[RUNNING_PROCESS],
            catalog_metadata_present=True, running=True,
        )

    return InstalledApplication(
        key=spec.key, name=spec.label, category=spec.category,
        status=MISSING,
        detail=spec.notes or "not found on PATH, Start Menu, MSIX, registry, or as a running process",
        version_args=spec.version_args, install_source=NONE_SOURCE,
        catalog_metadata_present=True, running=False,
    )


def _unknown_from_start_apps(start_apps: list[dict], claimed_ids: set[int]) -> list[InstalledApplication]:
    result = []
    for app in start_apps:
        if id(app) in claimed_ids:
            continue
        app_id, name = app["AppID"], app["Name"]
        launch_target = _start_app_launch_target(app_id)
        result.append(InstalledApplication(
            key=f"start_menu:{_slugify(name)}", name=name, category="",
            status=INSTALLED,
            path=launch_target if _is_raw_path(app_id) else None,
            launchable=True, healthy=True,
            detail="discovered via Start Menu; no catalog entry for it",
            app_user_model_id=None if _is_raw_path(app_id) else app_id,
            install_source=START_MENU, launch_target=launch_target,
            discovery_sources=(START_MENU,), confidence=_SOURCE_CONFIDENCE[START_MENU],
            catalog_metadata_present=False, running=False,
        ))
    return result


def _unknown_from_store_apps(store_apps: list[dict], claimed_ids: set[int]) -> list[InstalledApplication]:
    result = []
    for app in store_apps:
        if id(app) in claimed_ids:
            continue
        name = app.get("Name") or app.get("PackageFamilyName") or "Unknown"
        app_user_model_id = app.get("AppUserModelID")
        launch_target = f"shell:AppsFolder\\{app_user_model_id}" if app_user_model_id else None
        result.append(InstalledApplication(
            key=f"msix:{_slugify(app.get('PackageFamilyName') or name)}", name=name, category="",
            status=INSTALLED,
            path="explorer.exe" if launch_target else None,
            launchable=bool(launch_target), healthy=bool(launch_target),
            detail="discovered via Store/AppX; no catalog entry for it",
            version=app.get("Version"),
            package_name=app.get("PackageFullName"), package_family=app.get("PackageFamilyName"),
            app_user_model_id=app_user_model_id, publisher=app.get("Publisher"),
            install_source=MSIX, launch_target=launch_target,
            discovery_sources=(MSIX,), confidence=_SOURCE_CONFIDENCE[MSIX],
            catalog_metadata_present=False, running=False,
        ))
    return result


def _unknown_from_uninstall_apps(uninstall_apps: list[dict], claimed_ids: set[int]) -> list[InstalledApplication]:
    result = []
    for app in uninstall_apps:
        if id(app) in claimed_ids:
            continue
        name = app.get("DisplayName")
        if not name:
            continue
        result.append(InstalledApplication(
            key=f"registry:{_slugify(name)}", name=name, category="",
            status=INSTALLED,
            path=app.get("InstallLocation"), launchable=False, healthy=True,
            detail="discovered via registry uninstall entry; no catalog entry, no confirmed launch target",
            version=app.get("DisplayVersion"), publisher=app.get("Publisher"),
            install_source=REGISTRY, launch_target=None,
            discovery_sources=(REGISTRY,), confidence=_SOURCE_CONFIDENCE[REGISTRY],
            catalog_metadata_present=False, running=False,
        ))
    return result


def _dedup_unknown(records: list[InstalledApplication]) -> list[InstalledApplication]:
    """Section 6's unknown-application records come from up to three
    independent sources; the same real application (e.g. a Start Menu
    tile *and* its own registry uninstall entry) must not appear twice.
    Records are built strongest-source-first, so the first record seen
    per display name wins its `install_source`/`launch_target`; later
    duplicates only contribute their source to `discovery_sources`.
    """
    merged: dict[str, InstalledApplication] = {}
    for record in records:
        dedup_key = record.name.strip().lower()
        existing = merged.get(dedup_key)
        if existing is None:
            merged[dedup_key] = record
        else:
            merged[dedup_key] = dataclasses.replace(
                existing,
                discovery_sources=tuple(dict.fromkeys(existing.discovery_sources + record.discovery_sources)),
                running=existing.running or record.running,
            )
    return list(merged.values())


def discover(
    probe: SystemProbe,
    specs: tuple[ApplicationSpec, ...] = CATALOG,
    read_versions: bool = True,
    deep: bool = True,
    clock: Any = None,
) -> MachineInventory:
    """The whole machine, once — Universal Windows Environment Discovery:
    the catalog enriches what Windows itself reports, but a catalog
    entry can never declare a real, Windows-evidenced application
    "missing" (Section 1). See `docs/audits/
    DESKTOP_APPLICATION_DISCOVERY_1.md` for the full source/precedence/
    cache design.

    `deep=False` is the FAST PATH (Section 9): running-process
    attribution plus each catalog spec's own PATH/known-path check —
    the same cost this already had before this mission, no PowerShell
    beyond what a catalog path lookup already needed. `deep=True` (the
    default — a caller must opt into the fast path, not the reverse) adds
    the three Windows-wide sources (`Get-StartApps`, `Get-AppxPackage`,
    the registry uninstall keys), each several seconds of real subprocess
    cost, which is exactly why `DesktopContext` caches the result instead
    of re-running this on every action.
    """
    now = (clock or (lambda: datetime.now(UTC)))()
    processes = attribute_processes(probe.processes(), specs)
    running_keys = {p.owner for p in processes if p.owner}

    start_apps = probe.get_start_apps() if deep else []
    store_apps = probe.get_store_apps() if deep else []
    uninstall_apps = probe.get_uninstall_apps() if deep else []

    matched_start_ids: set[int] = set()
    matched_store_ids: set[int] = set()
    matched_uninstall_ids: set[int] = set()

    applications = [
        _resolve_one(
            spec, probe, read_versions, running_keys,
            start_apps, store_apps, uninstall_apps,
            matched_start_ids, matched_store_ids, matched_uninstall_ids,
        )
        for spec in specs
    ]

    unknown_applications = _dedup_unknown(
        _unknown_from_start_apps(start_apps, matched_start_ids)
        + _unknown_from_store_apps(store_apps, matched_store_ids)
        + _unknown_from_uninstall_apps(uninstall_apps, matched_uninstall_ids)
    )

    return MachineInventory(
        applications=applications,
        unknown_applications=unknown_applications,
        processes=processes,
        platform=probe.platform,
        captured_at=now,
    )


def refresh_processes_only(
    probe: SystemProbe,
    previous: MachineInventory,
    specs: tuple[ApplicationSpec, ...] = CATALOG,
    clock: Any = None,
) -> MachineInventory:
    """The FAST PATH's other half (Section 9), for when a deep scan is
    already cached: re-reads only the running-process snapshot — the one
    fact that can genuinely go stale between one call and the next — and
    re-applies it to the *existing* Start Menu/MSIX/registry-derived
    records, instead of discarding several real seconds of subprocess
    work just to confirm which processes are running right now.

    Without this, every `DesktopContext.refresh(deep=False)` call (every
    verified interaction action's own "confirm the window still exists"
    check) would downgrade the shared cache, so the *next*, unrelated
    `execute()` call would silently re-pay the full deep-scan cost —
    live evidence: launching Chrome then Notepad back-to-back each took
    ~25s instead of ~25s-then-instant, traced to exactly this.
    """
    now = (clock or (lambda: datetime.now(UTC)))()
    processes = attribute_processes(probe.processes(), specs)
    running_keys = {p.owner for p in processes if p.owner}
    applications = [
        dataclasses.replace(app, running=(app.key in running_keys))
        for app in previous.applications
    ]
    return dataclasses.replace(
        previous,
        applications=applications,
        processes=processes,
        captured_at=now,
    )


def attribute_processes(
    processes: list[ProcessInfo], specs: tuple[ApplicationSpec, ...] = CATALOG
) -> list[ProcessInfo]:
    """Deliverable 5's \"application ownership\". A process nothing in the
    catalogue claims keeps `owner=None` — unowned, not misattributed.
    """
    lookup: dict[str, str] = {}
    for spec in specs:
        for candidate in spec.process_candidates():
            lowered = candidate.lower()
            lookup[lowered] = spec.key
            lookup[lowered.removesuffix(".exe")] = spec.key

    attributed = []
    for process in processes:
        name = process.name.lower()
        owner = lookup.get(name) or lookup.get(name.removesuffix(".exe"))
        attributed.append(
            ProcessInfo(
                pid=process.pid,
                name=process.name,
                owner=owner,
                window_title=process.window_title,
            )
        )
    return attributed


def observations(inventory: MachineInventory) -> list[str]:
    """Deliverable 10: observations, never recommendations.

    \"Ollama not installed.\" is a fact. \"Install Ollama.\" is advice, and
    advice about AI tooling belongs to the AI Capability Broker, not here
    (Rules 2 and 11). Every string returned is a statement about what is.
    """
    lines = []
    for application in inventory.applications:
        if application.status == INSTALLED:
            version = f" {application.version}" if application.version else ""
            lines.append(f"{application.name}{version} installed.")
        elif application.status == UNAVAILABLE:
            lines.append(f"{application.name} present but not usable.")
        else:
            lines.append(f"{application.name} not installed.")
    return lines