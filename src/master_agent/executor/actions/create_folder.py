"""CreateFolderAction — the first Action registered with the LocalExecutor.

This is a straight refactor of what used to be FilesystemPlugin's own
invoke() logic (Mission Brief 001) — same behavior, same error messages,
same idempotency, no functionality lost. It now lives here so it executes
through the LocalExecutor like every future local action will, instead of
being a special case inside the Plugin layer. See
docs/MISSION_BRIEF_002.md.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from master_agent.executor.action import Action, ExecutionResult, is_unsafe_relative_path
from master_agent.plugins.base import RiskTier

CREATE_FOLDER = "create_folder"


class CreateFolderAction(Action):
    name = CREATE_FOLDER
    description = "Create a new folder in a known location."
    risk_tier = RiskTier.REVERSIBLE_WRITE
    expected_result = (
        "The target folder exists on disk after this action succeeds "
        "(idempotent if it already existed as a folder)."
    )

    def __init__(self, locations: dict[str, Path] | None = None) -> None:
        """`locations` maps a lowercase location name (e.g. "desktop") to
        a real base directory — injected rather than hardcoded, so tests
        can point "desktop" at a tmp_path instead of the real user
        Desktop. Defaults to the real Desktop for interactive use."""
        self._locations = locations or {"desktop": Path.home() / "Desktop"}

    def required_parameters(self) -> list[str]:
        return ["name"]

    def validate(self, parameters: dict[str, Any]) -> list[str]:
        errors: list[str] = []

        name = (parameters.get("name") or "").strip()
        if not name:
            errors.append("missing required parameter: name")
        elif is_unsafe_relative_path(name):
            # Added in Mission Brief 003: `name` started life as a single
            # user-typed folder name (Mission Brief 001's CLI parser), but
            # WorkspaceBootstrapAction now generates multi-segment values
            # like "MyProject/src" programmatically. Closing this gap here
            # too, not just in the newer actions, so CreateFolderAction is
            # safe against a caller (composite or direct) supplying '..'
            # regardless of which path led to it.
            errors.append(f"unsafe name '{name}': must be relative, no '..' segments")

        location_key = (parameters.get("location") or "desktop").strip().lower()
        if location_key not in self._locations:
            known = ", ".join(sorted(self._locations)) or "none configured"
            errors.append(f"unknown location '{location_key}' (known: {known})")

        return errors

    def run(self, parameters: dict[str, Any]) -> ExecutionResult:
        # validate() already confirmed these are present and known —
        # run() trusts that and doesn't re-check, to keep the two
        # responsibilities (is this request well-formed vs. do the work)
        # cleanly separate.
        name = parameters["name"].strip()
        location_key = (parameters.get("location") or "desktop").strip().lower()
        base = self._locations[location_key]
        target = base / name

        if target.exists():
            if target.is_dir():
                return ExecutionResult(
                    success=True,
                    output=str(target),
                    warnings=["folder already existed; no action taken"],
                )
            return ExecutionResult(
                success=False,
                errors=[f"{target} already exists and is not a folder"],
            )

        try:
            target.mkdir(parents=True, exist_ok=False)
        except OSError as exc:
            return ExecutionResult(success=False, errors=[str(exc)])

        return ExecutionResult(success=True, output=str(target))
