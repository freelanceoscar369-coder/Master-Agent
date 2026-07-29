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

import os
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

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


@dataclass(frozen=True)
class InstalledApplication:
    """Deliverable 2's shape, exactly."""

    key: str
    name: str
    category: str
    status: str = MISSING
    version: str | None = None
    path: str | None = None
    launchable: bool = False
    healthy: bool = False
    detail: str = ""

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
        }


@dataclass(frozen=True)
class MachineInventory:
    """One snapshot of the machine. Frozen for the same reason
    `DashboardSnapshot` is: it describes a moment that has passed."""

    applications: list[InstalledApplication] = field(default_factory=list)
    processes: list[ProcessInfo] = field(default_factory=list)
    platform: str = "unknown"
    captured_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def get(self, key: str) -> InstalledApplication | None:
        for application in self.applications:
            if application.key == key:
                return application
        return None

    def installed(self) -> list[InstalledApplication]:
        return [a for a in self.applications if a.installed]

    def missing(self) -> list[InstalledApplication]:
        return [a for a in self.applications if a.status == MISSING]

    def unavailable(self) -> list[InstalledApplication]:
        """Found but not usable. Distinct from missing: one is absent, the
        other is broken, and a founder should be told which."""
        return [a for a in self.applications if a.status == UNAVAILABLE]

    def missing_recommended(self) -> list[InstalledApplication]:
        from master_agent.desktop.catalog import BY_KEY

        return [
            a
            for a in self.missing()
            if (spec := BY_KEY.get(a.key)) is not None and spec.recommended
        ]

    def ai_applications(self) -> list[InstalledApplication]:
        """Deliverable 8: which AI software is present. A grouping, never
        a shortlist — nothing here decides what should be used."""
        return [a for a in self.applications if a.category == "ai"]

    def running(self, key: str) -> list[ProcessInfo]:
        return [p for p in self.processes if p.owner == key]

    def as_dict(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "captured_at": self.captured_at.isoformat(),
            "applications": [a.as_dict() for a in self.applications],
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
    an inventory row makes the whole panel unreadable."""
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
            )

    return InstalledApplication(
        key=spec.key,
        name=spec.label,
        category=spec.category,
        status=MISSING,
        detail=spec.notes or "not found on PATH or at any known install path",
    )


def attribute_processes(
    processes: list[ProcessInfo], specs: tuple[ApplicationSpec, ...] = CATALOG
) -> list[ProcessInfo]:
    """Deliverable 5's "application ownership". A process nothing in the
    catalogue claims keeps `owner=None` — unowned, not misattributed."""
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


def discover(
    probe: SystemProbe,
    specs: tuple[ApplicationSpec, ...] = CATALOG,
    read_versions: bool = True,
    clock: Any = None,
) -> MachineInventory:
    """The whole machine, once."""
    now = (clock or (lambda: datetime.now(UTC)))()
    applications = [
        discover_application(spec, probe, read_version=read_versions) for spec in specs
    ]
    processes = attribute_processes(probe.processes(), specs)
    return MachineInventory(
        applications=applications,
        processes=processes,
        platform=probe.platform,
        captured_at=now,
    )


def observations(inventory: MachineInventory) -> list[str]:
    """Deliverable 10: observations, never recommendations.

    "Ollama not installed." is a fact. "Install Ollama." is advice, and
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
