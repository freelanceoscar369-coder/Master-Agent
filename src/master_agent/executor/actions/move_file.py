"""MoveFileAction — moves a file to a destination within the same
location, either into an existing folder (keeping its filename) or as a
new literal path. REVERSIBLE_WRITE (moving it back undoes it). See
FILESYSTEM_CAPABILITIES.md.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from master_agent.executor.action import (
    Action,
    ExecutionResult,
    default_locations,
    is_unsafe_relative_path,
    resolve_into_or_as,
    resolve_overwrite_error,
)
from master_agent.plugins.base import PermissionCategory, RiskTier

MOVE_FILE = "move_file"


class MoveFileAction(Action):
    name = MOVE_FILE
    description = "Move a file to another path or folder within a known location."
    risk_tier = RiskTier.REVERSIBLE_WRITE
    permission_category = PermissionCategory.MODIFY
    expected_result = "The file no longer exists at its old path; it exists at the resolved destination."

    def __init__(self, locations: dict[str, Path] | None = None) -> None:
        self._locations = locations or default_locations()

    def required_parameters(self) -> list[str]:
        return ["path", "destination"]

    def validate(self, parameters: dict[str, Any]) -> list[str]:
        errors: list[str] = []

        path = (parameters.get("path") or "").strip()
        if not path:
            errors.append("missing required parameter: path")
        elif is_unsafe_relative_path(path):
            errors.append(f"unsafe path '{path}': must be relative, no '..' segments")

        destination = (parameters.get("destination") or "").strip()
        if not destination:
            errors.append("missing required parameter: destination")
        elif is_unsafe_relative_path(destination):
            errors.append(f"unsafe destination '{destination}': must be relative, no '..' segments")

        location_key = (parameters.get("location") or "desktop").strip().lower()
        if location_key not in self._locations:
            known = ", ".join(sorted(self._locations)) or "none configured"
            errors.append(f"unknown location '{location_key}' (known: {known})")

        return errors

    def run(self, parameters: dict[str, Any]) -> ExecutionResult:
        path = parameters["path"].strip()
        destination = parameters["destination"].strip()
        overwrite = bool(parameters.get("overwrite", False))
        location_key = (parameters.get("location") or "desktop").strip().lower()
        base = self._locations[location_key]
        source = base / path
        final_destination = resolve_into_or_as(source, base / destination)

        if not source.exists():
            return ExecutionResult(success=False, errors=[f"file not found: {source}"])
        if not source.is_file():
            return ExecutionResult(success=False, errors=[f"{source} is not a file"])

        overwrite_error = resolve_overwrite_error(final_destination, overwrite)
        if overwrite_error:
            return ExecutionResult(success=False, errors=[overwrite_error])

        try:
            final_destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(final_destination))
        except OSError as exc:
            return ExecutionResult(success=False, errors=[str(exc)])

        return ExecutionResult(
            success=True,
            output={"source": str(source), "destination": str(final_destination)},
        )
