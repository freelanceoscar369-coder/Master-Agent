"""DeleteFileAction — permanently deletes a single file. IRREVERSIBLE:
PermissionSystem.check() requires a fresh ONCE/THIS_SESSION grant every
time — an ALWAYS_FOR_CAPABILITY grant can never satisfy this action's
check, by design (FILESYSTEM_CAPABILITIES.md §5). Deliberately refuses to
touch a directory — DeleteFolderAction is the one that does that, so
"delete X" can never silently turn a file-delete request into a tree
deletion. See FILESYSTEM_CAPABILITIES.md.
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

DELETE_FILE = "delete_file"


class DeleteFileAction(Action):
    name = DELETE_FILE
    description = "Permanently delete a single file in a known location."
    risk_tier = RiskTier.IRREVERSIBLE
    permission_category = PermissionCategory.DELETE
    expected_result = "The file no longer exists. This cannot be undone by this system."

    def __init__(self, locations: dict[str, Path] | None = None) -> None:
        self._locations = locations or default_locations()

    def required_parameters(self) -> list[str]:
        return ["path"]

    def optional_parameters(self) -> list[dict[str, Any]]:
        """Publishes `location`, which this action has always accepted and
        never advertised.

        `validate()` below reads `parameters.get("location")` and resolves
        it against the known base directories; the contract said nothing
        about it. So the extracted capability carried an unclosed argument
        roster -- "optional arguments exist and are not listed" -- and no
        planner could use `location` from a published contract. An AI
        planner filled it anyway, from the shape of the objective, and the
        deterministic planner correctly refused to, because passing an
        argument a contract does not publish is exactly the guessing that
        module exists to prevent.

        `write_file.py` and `create_folder.py` already carry this same
        declaration for the same reason. This one was missed, and the
        consequence was that a founder saying "delete the file X inside
        folder Y on the Desktop" -- every part of it named -- could not be
        planned without a model.

        Nothing new is introduced: this states what the action already does.
        """
        return [
            {
                "name": "location",
                "type": "string",
                "description": (
                    "Which known base directory the path is relative to: "
                    + ", ".join(sorted(self._locations))
                    + ". Omit it to use the default. Do not repeat this "
                    "name at the start of 'path'."
                ),
                "default": "desktop",
            },
        ]

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

        if not target.exists():
            return ExecutionResult(success=False, errors=[f"file not found: {target}"])
        if not target.is_file():
            return ExecutionResult(success=False, errors=[f"{target} is a directory — use delete_folder"])

        try:
            target.unlink()
        except OSError as exc:
            return ExecutionResult(success=False, errors=[str(exc)])

        return ExecutionResult(success=True, output=str(target))
