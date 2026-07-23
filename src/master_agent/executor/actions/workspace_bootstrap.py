"""WorkspaceBootstrapAction — the first composite Action: it doesn't touch
the filesystem itself, it orchestrates CreateFolderAction and
WriteFileAction through the same LocalExecutor everything else runs
through. See docs/MISSION_BRIEF_003.md and
docs/adr/0006-composite-action-relay.md for why composition happens this
way instead of the composite calling other actions' run() directly.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from master_agent.executor.action import Action, ExecutionResult, is_unsafe_relative_path
from master_agent.executor.actions.create_folder import CREATE_FOLDER
from master_agent.executor.actions.write_file import WRITE_FILE
from master_agent.executor.executor import LocalExecutor
from master_agent.permissions.permission_system import GrantScope
from master_agent.plugins.base import RiskTier

WORKSPACE_BOOTSTRAP = "workspace_bootstrap"


class WorkspaceBootstrapAction(Action):
    """Creates a root folder, then any requested subfolders and seed
    files under it — a reusable "stand up a new project workspace"
    primitive, not a hardcoded "create THE Master Agent project" script.
    Every future mission that needs a folder-plus-files layout (a new
    plugin's scaffold, a new Obsidian sub-vault, whatever) supplies its
    own `folders`/`files` spec instead of this action growing a special
    case for each one.
    """

    name = WORKSPACE_BOOTSTRAP
    description = (
        "Create a workspace root folder plus any requested subfolders and "
        "seed files under it, composed from create_folder and write_file."
    )
    # Composed entirely of REVERSIBLE_WRITE sub-actions today. If a future
    # sub-step ever needs a higher risk tier, this MUST be raised to match —
    # a composite can never be gated more loosely than the riskiest thing it
    # might actually do.
    risk_tier = RiskTier.REVERSIBLE_WRITE
    expected_result = (
        "The workspace root folder exists, along with every requested "
        "subfolder and file, each created through the same permission-"
        "gated, logged Executor path as if invoked individually. On "
        "partial failure, whatever completed before the failing step stays "
        "done — there is no transactional rollback (see ADR-0006)."
    )

    def __init__(self, executor: LocalExecutor, locations: dict[str, Path] | None = None) -> None:
        """`executor` is the SAME LocalExecutor this action will be
        registered on — injected, not looked up globally, so this action
        can relay grants to and invoke its own sub-actions through the
        real Executor path instead of bypassing it. `locations` is passed
        straight through to validate() for the same fail-fast-without-
        side-effects reasoning CreateFolderAction/WriteFileAction use."""
        self._executor = executor
        self._locations = locations or {"desktop": Path.home() / "Desktop"}

    def required_parameters(self) -> list[str]:
        return ["name"]

    def validate(self, parameters: dict[str, Any]) -> list[str]:
        errors: list[str] = []

        name = (parameters.get("name") or "").strip()
        if not name:
            errors.append("missing required parameter: name")
        elif is_unsafe_relative_path(name):
            errors.append(f"unsafe name '{name}': must be relative, no '..' segments")

        location_key = (parameters.get("location") or "desktop").strip().lower()
        if location_key not in self._locations:
            known = ", ".join(sorted(self._locations)) or "none configured"
            errors.append(f"unknown location '{location_key}' (known: {known})")

        folders = parameters.get("folders", [])
        if not isinstance(folders, list):
            errors.append("folders must be a list of relative subfolder paths")
        else:
            for folder in folders:
                if not isinstance(folder, str) or not folder.strip():
                    errors.append(f"invalid folder entry: {folder!r} (must be a non-empty string)")
                elif is_unsafe_relative_path(folder):
                    errors.append(f"unsafe folder path '{folder}': must be relative, no '..' segments")

        files = parameters.get("files", [])
        if not isinstance(files, list):
            errors.append("files must be a list of {path, content} objects")
        else:
            for file_spec in files:
                if not isinstance(file_spec, dict) or not (file_spec.get("path") or "").strip():
                    errors.append(f"invalid file entry: {file_spec!r} (must be a dict with a non-empty 'path')")
                elif is_unsafe_relative_path(file_spec["path"]):
                    errors.append(f"unsafe file path '{file_spec['path']}': must be relative, no '..' segments")
                elif not isinstance(file_spec.get("content", ""), str):
                    errors.append(f"file entry '{file_spec['path']}' has non-string content")

        return errors

    def run(self, parameters: dict[str, Any]) -> ExecutionResult:
        name = parameters["name"].strip()
        location = (parameters.get("location") or "desktop").strip().lower()
        folders = parameters.get("folders", [])
        files = parameters.get("files", [])

        completed: list[dict[str, str]] = []

        root_result = self._run_substep(CREATE_FOLDER, {"name": name, "location": location})
        if not root_result.success:
            return ExecutionResult(
                success=False,
                errors=[f"failed to create workspace root '{name}': {'; '.join(root_result.errors)}"],
                output={"completed_before_failure": completed},
            )
        completed.append({"step": CREATE_FOLDER, "target": root_result.output})

        for folder in folders:
            combined = str(Path(name) / folder)
            result = self._run_substep(CREATE_FOLDER, {"name": combined, "location": location})
            if not result.success:
                return ExecutionResult(
                    success=False,
                    errors=[f"failed to create subfolder '{folder}': {'; '.join(result.errors)}"],
                    output={"completed_before_failure": completed},
                )
            completed.append({"step": CREATE_FOLDER, "target": result.output})

        for file_spec in files:
            combined = str(Path(name) / file_spec["path"])
            result = self._run_substep(
                WRITE_FILE,
                {"path": combined, "content": file_spec.get("content", ""), "location": location},
            )
            if not result.success:
                return ExecutionResult(
                    success=False,
                    errors=[f"failed to write file '{file_spec['path']}': {'; '.join(result.errors)}"],
                    output={"completed_before_failure": completed},
                )
            completed.append({"step": WRITE_FILE, "target": result.output})

        root_path = self._locations[location] / name
        return ExecutionResult(
            success=True,
            output={
                "root": str(root_path),
                "created_folders": [c["target"] for c in completed if c["step"] == CREATE_FOLDER],
                "written_files": [c["target"] for c in completed if c["step"] == WRITE_FILE],
            },
        )

    def _run_substep(self, action_name: str, payload: dict[str, Any]) -> ExecutionResult:
        """Relays this action's own already-granted approval down to the
        sub-action's grant key, then runs it through the real Executor —
        never by calling the sub-action's run() directly. See
        docs/adr/0006-composite-action-relay.md: this is ADR-0005's
        Plugin-layer relay pattern, one layer deeper, because here the
        Action itself is the thing orchestrating other Actions.
        """
        self._executor.permissions.grant(self._executor.name, action_name, GrantScope.ONCE)
        return self._executor.execute(action_name, payload)
