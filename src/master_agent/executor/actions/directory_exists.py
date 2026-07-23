"""DirectoryExistsAction — checks whether a directory exists at a known
location. READ_ONLY. Symmetric to FileExistsAction. See
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

DIRECTORY_EXISTS = "directory_exists"


class DirectoryExistsAction(Action):
    name = DIRECTORY_EXISTS
    description = "Check whether a directory exists at a known location."
    risk_tier = RiskTier.READ_ONLY
    permission_category = PermissionCategory.READ
    expected_result = "Whether the path exists, and whether it's a directory, is returned; nothing changes."

    def __init__(self, locations: dict[str, Path] | None = None) -> None:
        self._locations = locations or default_locations()

    def required_parameters(self) -> list[str]:
        return ["path"]

    def validate(self, parameters: dict[str, Any]) -> list[str]:
        errors: list[str] = []

        path = (parameters.get("path") or "").strip()
        if not path:
            errors.append("missing required parameter: path")
        elif is_unsafe_relative_path(path):
            errors.append(f"unsafe path '{path}': must be relative, no '..' segments")

        location_key = (parameters.get("location") or "desktop").strip().lower()
        if location_key not in self._locations:
            known = ", ".join(sorted(self._locations)) or "none configured"
            errors.append(f"unknown location '{location_key}' (known: {known})")

        return errors

    def run(self, parameters: dict[str, Any]) -> ExecutionResult:
        path = parameters["path"].strip()
        location_key = (parameters.get("location") or "desktop").strip().lower()
        target = self._locations[location_key] / path

        return ExecutionResult(
            success=True,
            output={"path": str(target), "exists": target.exists(), "is_directory": target.is_dir()},
        )
