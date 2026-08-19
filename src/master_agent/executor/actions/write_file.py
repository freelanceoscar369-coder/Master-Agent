"""WriteFileAction — the second primitive Action, and the one
WorkspaceBootstrapAction composes alongside CreateFolderAction. Writes
text content to a file under a known location, creating any missing
parent directories along the way. See docs/MISSION_BRIEF_003.md.
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

WRITE_FILE = "write_file"


class WriteFileAction(Action):
    name = WRITE_FILE
    # The Planner reads this line to decide both *whether* to use this
    # capability and *how to fill its arguments*, and only argument NAMES
    # are rendered alongside it (`planner/catalogue.py::signature`) -- the
    # per-argument descriptions below are not. So the relationship between
    # the two path arguments has to be stated here, or it is not stated to
    # the model at all.
    #
    # Without it, a plan asked to put a file on the Desktop produced
    # `location="Desktop"` AND `path="Desktop/KV_.../page_info.txt"`, and
    # the two were applied one after the other: the file landed in a
    # `Desktop` folder inside the Desktop while the folder the founder
    # asked for stayed empty. Both steps reported success.
    description = (
        "Write text content to a file. 'location' names a known base "
        "directory (Desktop, Documents, Downloads) and 'path' is relative "
        "to it -- so with location 'Desktop', path is 'Notes/summary.txt', "
        "never 'Desktop/Notes/summary.txt'. 'content' is the text to write."
    )
    risk_tier = RiskTier.REVERSIBLE_WRITE
    permission_category = PermissionCategory.WRITE
    expected_result = (
        "The target file exists on disk with the given content after this "
        "action succeeds (idempotent if it already existed with identical "
        "content; overwritten with a warning if it existed with different "
        "content)."
    )

    def __init__(self, locations: dict[str, Path] | None = None) -> None:
        """Same injection pattern as CreateFolderAction — see that class
        for why. Defaults to the real Desktop for interactive use."""
        self._locations = locations or default_locations()

    def required_parameters(self) -> list[str]:
        return ["path"]

    def optional_parameters(self) -> list[dict[str, Any]]:
        """Publishes `location` and `content`, which this action has always
        accepted and never advertised.

        Without this the extracted capability contract carried
        `inputs.closed = False` -- "optional arguments exist and are not
        listed" -- so the Planner was never told either argument existed.
        It still filled them, from the shape of the objective rather than
        from a published contract, and it got the `path`/`location`
        relationship wrong in exactly the way the class description above
        now spells out.

        `content` is optional rather than required because the action
        genuinely accepts its absence: `parameters.get("content", "")`
        writes an empty file, and an empty file is a legitimate thing to
        ask for. Nothing new is introduced here -- this states what the
        action already does.
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
            {
                "name": "content",
                "type": "string",
                "description": (
                    "The exact text to write. Omit it to create an empty file."
                ),
                "default": "",
            },
        ]

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
