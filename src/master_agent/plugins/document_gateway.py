"""Execution adapter that independently verifies text document writes.

The Document plugin remains the execution owner.  This gateway only joins
that existing plugin to the existing filesystem observation/verifier seam,
so a successful write is followed by a fresh read of the artifact rather
than being accepted from the Action's return value.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from master_agent.executor.action import default_locations
from master_agent.plugins.filesystem_expectations import (
    bind_for_environment,
    wants_content_digest,
)
from master_agent.plugins.filesystem_verifier import FilesystemVerifier
from master_agent.runtime.gateway import PluginGateway
from master_agent.verification.evidence import Evidence, ExpectedOutcome


class DocumentGateway(PluginGateway):
    """Run Document actions and verify exact Markdown/plain-text output."""

    def __init__(self, plugin: Any, locations: dict[str, Path] | None = None) -> None:
        super().__init__(plugin)
        self._locations = locations or default_locations()

    @staticmethod
    def _format(payload: dict[str, Any]) -> str:
        declared = str(payload.get("format") or "").strip().lower()
        if declared:
            return declared
        return Path(str(payload.get("path") or "")).suffix.lstrip(".").lower()

    def verify(
        self,
        capability: str,
        payload: dict[str, Any],
        expected: ExpectedOutcome,
    ) -> Evidence | None:
        # A Word package needs a document-aware extractor before exact text
        # can be claimed.  V1's Markdown/text artifacts are exact UTF-8 text;
        # those can be re-read and compared today.  Refuse to overclaim the
        # binary format meanwhile.
        local = capability.rsplit(".", 1)[-1].replace("_", "").lower()
        if local != "writedocument" or self._format(payload) not in {"md", "txt"}:
            return None

        effective = bind_for_environment(
            capability=capability,
            payload=payload,
            description=expected.description,
        )
        if effective is None:
            return None

        location = str(payload.get("location") or "desktop").strip().lower()
        base = self._locations.get(location)
        if base is None:
            return None
        relative = str(payload.get("path") or "").strip()
        if not relative:
            return None

        verifier = FilesystemVerifier(
            target_path=str(Path(base) / relative),
            base_path=str(base),
            include_content_digest=wants_content_digest(capability, payload),
        )
        return verifier.verify(effective)
