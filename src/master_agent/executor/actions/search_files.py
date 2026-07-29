"""SearchFilesAction — recursive glob search for files under a known
location. READ_ONLY. See FILESYSTEM_CAPABILITIES.md.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from master_agent.executor.action import (
    Action,
    ExecutionResult,
    default_locations,
    is_unsafe_relative_path,
    to_portable_relative_str,
)
from master_agent.plugins.base import PermissionCategory, RiskTier

SEARCH_FILES = "search_files"

# A broad pattern ("*") over a large tree could otherwise return an
# unbounded number of matches. Capped, and the cap is reported in the
# output rather than silently applied -- FILESYSTEM_CAPABILITIES.md §7.
MAX_RESULTS = 200


class SearchFilesAction(Action):
    name = SEARCH_FILES
    description = "Search for files matching a glob pattern, recursively, under a known location."
    risk_tier = RiskTier.READ_ONLY
    permission_category = PermissionCategory.READ
    expected_result = "Matching file paths (relative to the search root) are returned; nothing changes."

    def __init__(self, locations: dict[str, Path] | None = None) -> None:
        self._locations = locations or default_locations()

    def required_parameters(self) -> list[str]:
        return ["pattern"]

    def validate(self, parameters: dict[str, Any]) -> list[str]:
        errors: list[str] = []

        pattern = (parameters.get("pattern") or "").strip()
        if not pattern:
            errors.append("missing required parameter: pattern")
        elif ".." in pattern or pattern.startswith("/"):
            errors.append(f"unsafe pattern '{pattern}': must not traverse outside the search root")

        path = (parameters.get("path") or ".").strip()
        if is_unsafe_relative_path(path) and path != ".":
            errors.append(f"unsafe path '{path}': must be relative, no '..' segments")

        location_key = (parameters.get("location") or "desktop").strip().lower()
        if location_key not in self._locations:
            known = ", ".join(sorted(self._locations)) or "none configured"
            errors.append(f"unknown location '{location_key}' (known: {known})")

        return errors

    def run(self, parameters: dict[str, Any]) -> ExecutionResult:
        pattern = parameters["pattern"].strip()
        path = (parameters.get("path") or ".").strip()
        location_key = (parameters.get("location") or "desktop").strip().lower()
        base = self._locations[location_key]
        root = base if path == "." else base / path

        if not root.exists() or not root.is_dir():
            return ExecutionResult(success=False, errors=[f"search root not found: {root}"])

        try:
            matches = sorted(p for p in root.rglob(pattern) if p.is_file())
        except OSError as exc:
            return ExecutionResult(success=False, errors=[str(exc)])

        truncated = len(matches) > MAX_RESULTS
        matches = matches[:MAX_RESULTS]
        # Forward slashes on every platform -- these strings get persisted
        # into mission history, so they must not depend on which OS ran
        # the search (Mission Brief 023.1).
        relative = [to_portable_relative_str(p, root) for p in matches]

        return ExecutionResult(
            success=True,
            output={"root": str(root), "matches": relative, "truncated": truncated},
        )
