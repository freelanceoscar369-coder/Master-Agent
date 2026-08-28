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

from master_agent.executor.action import (
    Action,
    ExecutionResult,
    default_locations,
    is_unsafe_relative_path,
)
from master_agent.plugins.base import PermissionCategory, RiskTier

CREATE_FOLDER = "create_folder"


class CreateFolderAction(Action):
    name = CREATE_FOLDER
    # The Planner reads this line to decide both *whether* to use this
    # capability and *how to fill its arguments*, and only argument NAMES
    # are rendered alongside it (`planner/catalogue.py::signature`) -- the
    # per-argument descriptions published below are not. So the split
    # between the two arguments has to be stated here, or it is not stated
    # to the model at all. Asked to "create a folder called Research on my
    # Desktop" without it, the Planner had no reason to treat the trailing
    # phrase as anything but part of the name, and passed
    # name="Research on my Desktop" -- producing a folder named after the
    # whole sentence.
    # The second sentence was added later, and it overstated. `name` is
    # contractually a RELATIVE PATH under `location`, not a leaf: the
    # shared guard's own docstring names this argument as "a relative
    # path/name meant to be joined onto a configured location's base
    # directory", `validate()` deliberately admits multi-segment values,
    # and `run()` calls `mkdir(parents=True)` -- which does nothing at
    # all unless the value may have more than one segment.
    #
    # Saying "own name only" here told the Planner the opposite of what
    # the code accepts, so a founder asking for a folder inside another
    # folder would be refused a target this capability can already reach
    # safely. The real rule -- the one the original defect needed -- is
    # about a LOCATION phrase, and that is what it now says.
    description = (
        "Create a new folder. 'name' may be a relative path under "
        "'location' (e.g. 'Onkar/Rudra' to create Rudra inside Onkar); "
        "'..' and absolute paths are rejected. When the objective says "
        "WHERE to put it (Desktop, Documents, Downloads), that is a "
        "location and belongs in 'location', never in 'name'."
    )
    risk_tier = RiskTier.REVERSIBLE_WRITE
    permission_category = PermissionCategory.WRITE
    expected_result = (
        "The target folder exists on disk after this action succeeds "
        "(idempotent if it already existed as a folder)."
    )

    def __init__(self, locations: dict[str, Path] | None = None) -> None:
        """`locations` maps a lowercase location name (e.g. "desktop") to
        a real base directory — injected rather than hardcoded, so tests
        can point "desktop" at a tmp_path instead of the real user
        Desktop. Defaults to the real Desktop for interactive use."""
        self._locations = locations or default_locations()

    def required_parameters(self) -> list[str]:
        return ["name"]

    def optional_parameters(self) -> list[dict[str, Any]]:
        """Publishes `location`, which this action has always accepted but
        never advertised.

        Without this the extracted capability contract carried
        `inputs.closed = False` -- "optional arguments exist and are not
        listed" -- so the Planner was never told a `location` argument
        existed. Asked to "create a folder called Research on my
        Desktop", it had exactly one slot to put everything in and passed
        `name="Research on my Desktop"`, which produced a folder named
        after the whole sentence instead of a folder named Research on
        the Desktop.

        The default is stated here because it is the action's own
        long-standing behaviour (`run()`/`validate()` both fall back to
        "desktop"), not a new product policy invented for the Planner's
        benefit."""
        return [
            {
                "name": "location",
                "type": "string",
                "description": (
                    "Which known base directory to create the folder in: "
                    + ", ".join(sorted(self._locations))
                    + ". Omit it to use the default."
                ),
                "default": "desktop",
            },
        ]

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
