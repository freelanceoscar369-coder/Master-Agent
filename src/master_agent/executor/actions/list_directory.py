"""ListDirectoryAction — lists the immediate (non-recursive) contents of a
known location, or a subfolder under it. READ_ONLY. See
FILESYSTEM_CAPABILITIES.md.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from master_agent.executor.action import (
    Action,
    ExecutionResult,
    default_locations,
    is_unsafe_relative_path,
)
from master_agent.plugins.base import PermissionCategory, RiskTier

LIST_DIRECTORY = "list_directory"


class ListDirectoryAction(Action):
    name = LIST_DIRECTORY
    description = "List the immediate contents of a folder in a known location."
    risk_tier = RiskTier.READ_ONLY
    permission_category = PermissionCategory.READ
    expected_result = "The folder's entries are returned, split into folders and files; nothing changes."

    def __init__(self, locations: dict[str, Path] | None = None) -> None:
        self._locations = locations or default_locations()

    def required_parameters(self) -> list[str]:
        return []  # `path` is optional -- "." (the location root) if omitted

    def validate(self, parameters: dict[str, Any]) -> list[str]:
        errors: list[str] = []

        path = (parameters.get("path") or ".").strip()
        if is_unsafe_relative_path(path) and path != ".":
            errors.append(f"unsafe path '{path}': must be relative, no '..' segments")

        location_key = (parameters.get("location") or "desktop").strip().lower()
        if location_key not in self._locations:
            known = ", ".join(sorted(self._locations)) or "none configured"
            errors.append(f"unknown location '{location_key}' (known: {known})")

        return errors

    def run(self, parameters: dict[str, Any]) -> ExecutionResult:
        path = (parameters.get("path") or ".").strip()
        location_key = (parameters.get("location") or "desktop").strip().lower()
        base = self._locations[location_key]
        target = base if path == "." else base / path

        if not target.exists():
            return ExecutionResult(success=False, errors=[f"directory not found: {target}"])
        if not target.is_dir():
            return ExecutionResult(success=False, errors=[f"{target} is not a directory"])

        try:
            entries = sorted(target.iterdir(), key=lambda p: p.name.lower())
        except OSError as exc:
            return ExecutionResult(success=False, errors=[str(exc)])

        folders = [e.name for e in entries if e.is_dir()]
        files = [e.name for e in entries if e.is_file()]
        return ExecutionResult(
            success=True,
            output={"path": str(target), "folders": folders, "files": files},
        )
