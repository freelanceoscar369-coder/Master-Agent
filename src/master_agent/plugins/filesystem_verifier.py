"""FilesystemVerifier -- a concrete Verifier for filesystem capabilities.
See VERIFICATION_SYSTEM.md and FILESYSTEM_CAPABILITIES.md. Implements exactly
one method; everything else (building Evidence, computing the Verdict) is
inherited, unchanged, from the generic base.
"""
from __future__ import annotations

from typing import Any

from master_agent.plugins.filesystem_observation import normalize_observation
from master_agent.verification.verifier import Verifier


class FilesystemVerifier(Verifier):
    worker_name = "filesystem"
    environment_name = "filesystem_environment"

    def __init__(
        self,
        target_path: str,
        base_path: str,
        include_content_preview: bool = False,
        include_directory_listing: bool = False,
    ) -> None:
        self._target_path = target_path
        self._base_path = base_path
        self._include_content_preview = include_content_preview
        self._include_directory_listing = include_directory_listing

    def capture_observation_dict(self) -> dict[str, Any]:
        """Re-observe current real-world filesystem state fresh at the moment
        verify() is called -- never a cached Observation from whenever the
        Action ran. This is what keeps Verification structurally independent
        of Execution (ADR-0011)."""
        from pathlib import Path

        target = Path(self._target_path)
        base = Path(self._base_path)

        observation = normalize_observation(
            target,
            base,
            include_content_preview=self._include_content_preview,
            include_directory_listing=self._include_directory_listing,
        )
        return observation.as_dict()