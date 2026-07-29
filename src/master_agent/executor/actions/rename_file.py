"""RenameFileAction — renames a file within the same directory.
REVERSIBLE_WRITE. Deliberately same-directory-only, to stay atomic — a
rename that also changes directory is a move, which is MoveFileAction's
job (FILESYSTEM_CAPABILITIES.md §2). See FILESYSTEM_CAPABILITIES.md.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from master_agent.executor.action import (
    Action,
    ExecutionResult,
    default_locations,
    is_unsafe_relative_path,
    resolve_overwrite_error,
)
from master_agent.plugins.base import PermissionCategory, RiskTier

RENAME_FILE = "rename_file"


class RenameFileAction(Action):
    name = RENAME_FILE
    description = "Rename a file within the same directory in a known location."
    risk_tier = RiskTier.REVERSIBLE_WRITE
    permission_category = PermissionCategory.MODIFY
    expected_result = "The file exists under its new name; the old name no longer exists."

    def __init__(self, locations: dict[str, Path] | None = None) -> None:
        self._locations = locations or default_locations()

    def required_parameters(self) -> list[str]:
        return ["path", "new_name"]

    def validate(self, parameters: dict[str, Any]) -> list[str]:
        errors: list[str] = []

        path = (parameters.get("path") or "").strip()
        if not path:
            errors.append("missing required parameter: path")
        elif is_unsafe_relative_path(path):
            errors.append(f"unsafe path '{path}': must be relative, no '..' segments")

        new_name = (parameters.get("new_name") or "").strip()
        if not new_name:
            errors.append("missing required parameter: new_name")
        elif "/" in new_name or "\\" in new_name or is_unsafe_relative_path(new_name):
            errors.append(f"invalid new_name '{new_name}': must be a bare filename, no path separators")

        location_key = (parameters.get("location") or "desktop").strip().lower()
        if location_key not in self._locations:
            known = ", ".join(sorted(self._locations)) or "none configured"
            errors.append(f"unknown location '{location_key}' (known: {known})")

        return errors

    def run(self, parameters: dict[str, Any]) -> ExecutionResult:
        path = parameters["path"].strip()
        new_name = parameters["new_name"].strip()
        overwrite = bool(parameters.get("overwrite", False))
        location_key = (parameters.get("location") or "desktop").strip().lower()
        source = self._locations[location_key] / path
        destination = source.parent / new_name

        if not source.exists():
            return ExecutionResult(success=False, errors=[f"file not found: {source}"])
        if not source.is_file():
            return ExecutionResult(success=False, errors=[f"{source} is not a file"])

        overwrite_error = resolve_overwrite_error(destination, overwrite)
        if overwrite_error:
            return ExecutionResult(success=False, errors=[overwrite_error])

        try:
            # `replace`, not `rename`: on Windows `Path.rename()` raises
            # if the destination exists, while on POSIX it silently
            # replaces -- so `rename` would make `overwrite: true` mean
            # two different things on two platforms. `Path.replace()` is
            # the atomic overwrite on both (Mission Brief 023.1). The
            # overwrite guard above still decides *whether* replacing is
            # allowed; this only makes the allowed case behave the same
            # everywhere.
            source.replace(destination)
        except OSError as exc:
            return ExecutionResult(success=False, errors=[str(exc)])

        return ExecutionResult(success=True, output=str(destination))
