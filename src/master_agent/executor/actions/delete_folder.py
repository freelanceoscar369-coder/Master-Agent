"""DeleteFolderAction — permanently deletes a folder and everything under
it. IRREVERSIBLE — same "no standing blanket approval" rule as
DeleteFileAction (FILESYSTEM_CAPABILITIES.md §5). Refuses an empty or "."
path so "delete X" can never resolve to deleting an entire location root,
on top of the traversal check every path-shaped parameter already gets.
See FILESYSTEM_CAPABILITIES.md.
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
)
from master_agent.plugins.base import PermissionCategory, RiskTier

DELETE_FOLDER = "delete_folder"


class DeleteFolderAction(Action):
    name = DELETE_FOLDER
    description = "Permanently delete a folder and everything under it, in a known location."
    risk_tier = RiskTier.IRREVERSIBLE
    permission_category = PermissionCategory.DELETE
    expected_result = "The folder and its entire contents no longer exist. This cannot be undone by this system."

    def __init__(self, locations: dict[str, Path] | None = None) -> None:
        self._locations = locations or default_locations()

    def required_parameters(self) -> list[str]:
        return ["path"]

    def validate(self, parameters: dict[str, Any]) -> list[str]:
        errors: list[str] = []

        path = (parameters.get("path") or "").strip()
        if not path or path == ".":
            errors.append("missing or empty 'path' — refusing to delete a location root")
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
        base = self._locations[location_key]
        target = base / path

        # Defense in depth: validate() already rejects '..'/absolute/empty
        # paths, so `target` structurally cannot equal or be an ancestor
        # of `base` — this check exists anyway, cheaply, in case a future
        # change to path resolution ever loosens that guarantee.
        if target == base or base not in target.parents:
            return ExecutionResult(success=False, errors=[f"refusing to delete outside of {base}"])

        if not target.exists():
            return ExecutionResult(success=False, errors=[f"folder not found: {target}"])
        if not target.is_dir():
            return ExecutionResult(success=False, errors=[f"{target} is a file — use delete_file"])

        try:
            shutil.rmtree(target)
        except OSError as exc:
            return ExecutionResult(success=False, errors=[str(exc)])

        return ExecutionResult(success=True, output=str(target))
