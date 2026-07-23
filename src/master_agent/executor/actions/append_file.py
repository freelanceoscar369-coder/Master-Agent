"""AppendFileAction — appends text content to a file, creating it (and
any missing parent directories) if it doesn't already exist. REVERSIBLE_WRITE.
See FILESYSTEM_CAPABILITIES.md.
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

APPEND_FILE = "append_file"


class AppendFileAction(Action):
    name = APPEND_FILE
    description = "Append text content to a file in a known location, creating it if missing."
    risk_tier = RiskTier.REVERSIBLE_WRITE
    permission_category = PermissionCategory.WRITE
    expected_result = "The target file exists with the given content appended to whatever was there before."

    def __init__(self, locations: dict[str, Path] | None = None) -> None:
        self._locations = locations or default_locations()

    def required_parameters(self) -> list[str]:
        return ["path", "content"]

    def validate(self, parameters: dict[str, Any]) -> list[str]:
        errors: list[str] = []

        path = (parameters.get("path") or "").strip()
        if not path:
            errors.append("missing required parameter: path")
        elif is_unsafe_relative_path(path):
            errors.append(f"unsafe path '{path}': must be relative, no '..' segments")

        if not isinstance(parameters.get("content", ""), str):
            errors.append("content must be a string")

        location_key = (parameters.get("location") or "desktop").strip().lower()
        if location_key not in self._locations:
            known = ", ".join(sorted(self._locations)) or "none configured"
            errors.append(f"unknown location '{location_key}' (known: {known})")

        return errors

    def run(self, parameters: dict[str, Any]) -> ExecutionResult:
        path = parameters["path"].strip()
        content = parameters.get("content", "")
        location_key = (parameters.get("location") or "desktop").strip().lower()
        target = self._locations[location_key] / path

        if target.exists() and target.is_dir():
            return ExecutionResult(success=False, errors=[f"{target} already exists and is not a file"])

        try:
            created = not target.exists()
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("a") as handle:
                handle.write(content)
        except OSError as exc:
            return ExecutionResult(success=False, errors=[str(exc)])

        warnings = [] if created else ["existing file's content extended, not replaced"]
        return ExecutionResult(success=True, output=str(target), warnings=warnings)
