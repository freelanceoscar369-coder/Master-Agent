"""ReadFileAction — the first Mission Brief 005 primitive. Reads a text
file's content from a known location. READ_ONLY: never touches the
Permission System's approval gate (PermissionSystem.check() already
short-circuits READ_ONLY unconditionally, unchanged by this Miracle).
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

READ_FILE = "read_file"

# A read that would pull an unbounded amount of text into memory (and
# into a Mission's persisted execution_result) isn't a security issue —
# every path is still sandboxed to a known location — but it's a
# resource-usage footgun worth capping cheaply. 2 MB comfortably covers
# any real source file/config/README; a structured error beats a hang or
# an oversized Memory record for anything larger.
MAX_READ_BYTES = 2_000_000


class ReadFileAction(Action):
    name = READ_FILE
    description = "Read a text file's content from a known location."
    risk_tier = RiskTier.READ_ONLY
    permission_category = PermissionCategory.READ
    expected_result = "The file's text content is returned; nothing on disk changes."

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

        if not target.exists():
            return ExecutionResult(success=False, errors=[f"file not found: {target}"])
        if target.is_dir():
            return ExecutionResult(success=False, errors=[f"{target} is a directory, not a file"])

        try:
            size = target.stat().st_size
            if size > MAX_READ_BYTES:
                return ExecutionResult(
                    success=False,
                    errors=[f"{target} is {size} bytes, over the {MAX_READ_BYTES}-byte read limit"],
                )
            content = target.read_text()
        except OSError as exc:
            return ExecutionResult(success=False, errors=[str(exc)])
        except UnicodeDecodeError:
            return ExecutionResult(success=False, errors=[f"{target} is not a text file"])

        return ExecutionResult(success=True, output={"path": str(target), "content": content})
