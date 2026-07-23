"""Filesystem capability plugin — the first real (non-model) plugin in the
system, and the one Mission Brief 001 exercises end to end. Implements the
same Plugin contract as everything else (ADR-0003): a manifest and
invoke(). Nothing about the Orchestrator or Permission System needed to
change to accommodate it.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from master_agent.plugins.base import (
    CapabilityManifest,
    InvocationResult,
    Plugin,
    PluginManifest,
    RiskTier,
)

CREATE_FOLDER = "create_folder"


class FilesystemPlugin(Plugin):
    """Creates folders under a small, named set of locations.

    `locations` maps a lowercase location name (e.g. "desktop") to a real
    base directory, and is injected rather than hardcoded — this is the
    dependency-injection seam that lets tests point "desktop" at a tmp_path
    instead of the real user Desktop, without touching this class. Defaults
    to the real Desktop for interactive/production use.
    """

    def __init__(self, locations: dict[str, Path] | None = None) -> None:
        self._locations = locations or {"desktop": Path.home() / "Desktop"}

    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            name="filesystem",
            version="0.1.0",
            capabilities=[
                CapabilityManifest(
                    name=CREATE_FOLDER,
                    description="Create a new folder in a known location.",
                    risk_tier=RiskTier.REVERSIBLE_WRITE,
                    input_schema={"name": "str", "location": "str (optional, default 'desktop')"},
                    output_schema={"path": "str — absolute path of the created (or existing) folder"},
                ),
            ],
        )

    def invoke(self, capability: str, payload: dict[str, Any]) -> InvocationResult:
        if capability != CREATE_FOLDER:
            return InvocationResult(success=False, error=f"unsupported capability: {capability}")

        name = (payload.get("name") or "").strip()
        if not name:
            return InvocationResult(success=False, error="missing folder name")

        location_key = (payload.get("location") or "desktop").strip().lower()
        base = self._locations.get(location_key)
        if base is None:
            known = ", ".join(sorted(self._locations)) or "none configured"
            return InvocationResult(
                success=False,
                error=f"unknown location '{location_key}' (known: {known})",
            )

        target = base / name

        if target.exists():
            if target.is_dir():
                # Idempotent: asking to create a folder that's already
                # there is a success, not an error — matches how a human
                # would read "create a folder called Demo" a second time.
                return InvocationResult(success=True, output=str(target))
            return InvocationResult(
                success=False,
                error=f"{target} already exists and is not a folder",
            )

        try:
            target.mkdir(parents=True, exist_ok=False)
        except OSError as exc:
            return InvocationResult(success=False, error=str(exc))

        return InvocationResult(success=True, output=str(target))
