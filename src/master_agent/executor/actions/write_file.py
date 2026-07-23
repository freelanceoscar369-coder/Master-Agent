"""WriteFileAction — the second primitive Action, and the one
WorkspaceBootstrapAction composes alongside CreateFolderAction. Writes
text content to a file under a known location, creating any missing
parent directories along the way. See docs/MISSION_BRIEF_003.md.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from master_agent.executor.action import Action, ExecutionResult, is_unsafe_relative_path
from master_agent.plugins.base import RiskTier

WRITE_FILE = "write_file"


class WriteFileAction(Action):
    name = WRITE_FILE
    description = "Write text content to a file in a known location."
    risk_tier = RiskTier.REVERSIBLE_WRITE
    expected_result = (
        "The target file exists on disk with the given content after this "
        "action succeeds (idempotent if it already existed with identical "
        "content; overwritten with a warning if it existed with different "
        "content)."
    )

    def __init__(self, locations: dict[str, Path] | None = None) -> None:
        """Same injection pattern as CreateFolderAction — see that class
        for why. Defaults to the real Desktop for interactive use."""
        self._locations = locations or {"desktop": Path.home() / "Desktop"}

    def required_parameters(self) -> list[str]:
        return ["path"]

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
        # validate() already confirmed these are present, safe, and known —
        # run() trusts that, same separation of concerns as CreateFolderAction.
        path = parameters["path"].strip()
        content = parameters.get("content", "")
        location_key = (parameters.get("location") or "desktop").strip().lower()
        base = self._locations[location_key]
        target = base / path

        if target.exists() and target.is_dir():
            return ExecutionResult(success=False, errors=[f"{target} already exists and is not a file"])

        try:
            if target.exists() and target.read_text() == content:
                return ExecutionResult(
                    success=True,
                    output=str(target),
                    warnings=["file already had this exact content; no action taken"],
                )

            target.parent.mkdir(parents=True, exist_ok=True)
            overwritten = target.exists()
            target.write_text(content)
        except OSError as exc:
            return ExecutionResult(success=False, errors=[str(exc)])

        warnings = ["existing file overwritten with new content"] if overwritten else []
        return ExecutionResult(success=True, output=str(target), warnings=warnings)
