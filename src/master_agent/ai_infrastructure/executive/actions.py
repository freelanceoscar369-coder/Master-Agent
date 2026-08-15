"""AI Infrastructure Executive — Discovery Actions.

Deterministic discovery of AI providers on the local machine. No AI decisions,
just filesystem scans, registry queries, process lists, and subprocess probes.
"""
from __future__ import annotations

import json
import os
import subprocess

from master_agent.foundation.windowless import NO_WINDOW
import sys
import winreg
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from master_agent.ai_infrastructure.executive.models import (
    ProviderCapabilities,
    ProviderHealth,
    ProviderIdentity,
    ProviderInventory,
    ProviderInventoryEntry,
    ProviderClass,
    DiscoverySource,
)
from master_agent.executor.action import Action, ExecutionResult
from master_agent.plugins.base import RiskTier, PermissionCategory


# ---- Known provider signatures ---------------------------------------------

PROVIDER_SIGNATURES: dict[str, dict[str, Any]] = {
    "ollama": {
        "display_name": "Ollama",
        "provider_class": ProviderClass.LOCAL_RUNTIME,
        "executables": ["ollama.exe", "ollama"],
        "common_paths": [
            r"C:\Users\{user}\AppData\Local\Programs\Ollama",
            r"C:\Program Files\Ollama",
            "/usr/local/bin/ollama",
            "/opt/ollama",
        ],
        "ai_capabilities": {"reasoning", "coding"},
        "execution_capability": "GenerateText",
        "probe_command": ["ollama", "list"],
    },
    "lm-studio": {
        "display_name": "LM Studio",
        "provider_class": ProviderClass.LOCAL_RUNTIME,
        "executables": ["LM Studio.exe", "lms.exe"],
        "common_paths": [
            r"C:\Users\{user}\AppData\Local\LM Studio",
            r"C:\Program Files\LM Studio",
            "/Applications/LM Studio.app",
        ],
        "ai_capabilities": {"reasoning", "coding"},
        "execution_capability": "GenerateText",
        "probe_command": ["lms", "ps"],
    },
    "claude-desktop": {
        "display_name": "Claude Desktop",
        "provider_class": ProviderClass.DESKTOP_APPLICATION,
        "executables": ["Claude.exe", "Claude"],
        "common_paths": [
            r"C:\Users\{user}\AppData\Local\AnthropicClaude",
            r"C:\Program Files\Anthropic\Claude",
            "/Applications/Claude.app",
        ],
        "ai_capabilities": {"reasoning", "reasoning.planning", "coding"},
        "execution_capability": "GenerateText",
        "probe_command": None,  # Desktop app, no CLI
    },
}


def expand_user(path: str) -> str:
    """Expand {user} placeholder to actual username."""
    return path.replace("{user}", os.getenv("USERNAME") or os.getenv("USER") or "")


def find_executable(name: str) -> Path | None:
    """Find an executable in PATH."""
    for path_dir in os.environ.get("PATH", "").split(os.pathsep):
        candidate = Path(path_dir) / name
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


# ---- Discovery Actions -----------------------------------------------------

class DiscoverOllamaAction(Action):
    """Discover Ollama local runtime."""

    name = "ai_infrastructure.discover_ollama"
    description = "Discover Ollama installation and running models"
    risk_tier = RiskTier.READ_ONLY
    permission_category = PermissionCategory.READ
    expected_result = "Ollama installation details or not found"

    def required_parameters(self) -> list[str]:
        return []

    def validate(self, parameters: dict[str, Any]) -> list[str]:
        return []

    def run(self, parameters: dict[str, Any]) -> ExecutionResult:
        signature = PROVIDER_SIGNATURES["ollama"]
        identity = None
        health = ProviderHealth(is_available=False)

        # Check PATH
        exe_path = find_executable("ollama.exe") or find_executable("ollama")
        if exe_path:
            # Probe version
            try:
                result = subprocess.run(
                    ["ollama", "--version"],
                    capture_output=True,
                creationflags=NO_WINDOW,
                    text=True,
                    timeout=10,
                )
                version = result.stdout.strip() if result.returncode == 0 else None
            except Exception:
                version = None

            # Probe models
            models = []
            try:
                result = subprocess.run(
                    ["ollama", "list"],
                    capture_output=True,
                creationflags=NO_WINDOW,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    lines = result.stdout.strip().split("\n")[1:]  # Skip header
                    for line in lines:
                        parts = line.split()
                        if parts:
                            models.append(parts[0])
            except Exception:
                pass

            identity = ProviderIdentity(
                provider_id="ollama.local",
                display_name=signature["display_name"],
                provider_class=signature["provider_class"],
                version=version,
                install_path=str(exe_path.parent.parent),
                executable_path=str(exe_path),
                discovery_source=DiscoverySource.PROCESS_LIST,
            )
            health = ProviderHealth(
                is_available=True,
                is_healthy=True,
                last_probe_at=datetime.now(UTC),
                details={"models": models},
            )
        else:
            # Check common install paths
            for path_template in signature["common_paths"]:
                path = Path(expand_user(path_template))
                if path.exists():
                    health = ProviderHealth(
                        is_available=True,
                        is_healthy=False,
                        last_probe_at=datetime.now(UTC),
                        error_message="Installed but ollama not in PATH",
                        details={"install_path": str(path)},
                    )
                    identity = ProviderIdentity(
                        provider_id="ollama.local",
                        display_name=signature["display_name"],
                        provider_class=signature["provider_class"],
                        install_path=str(path),
                        discovery_source=DiscoverySource.FILESYSTEM_SCAN,
                    )
                    break

        return ExecutionResult(
            success=True,
            output={"identity": identity.as_dict() if identity else None, "health": health.as_dict()},
        )


class DiscoverLMStudioAction(Action):
    """Discover LM Studio local runtime."""

    name = "ai_infrastructure.discover_lm_studio"
    description = "Discover LM Studio installation and loaded models"
    risk_tier = RiskTier.READ_ONLY
    permission_category = PermissionCategory.READ
    expected_result = "LM Studio installation details or not found"

    def required_parameters(self) -> list[str]:
        return []

    def validate(self, parameters: dict[str, Any]) -> list[str]:
        return []

    def run(self, parameters: dict[str, Any]) -> ExecutionResult:
        signature = PROVIDER_SIGNATURES["lm-studio"]
        identity = None
        health = ProviderHealth(is_available=False)

        # Check PATH for lms CLI
        exe_path = find_executable("lms.exe") or find_executable("lms")
        if exe_path:
            try:
                result = subprocess.run(
                    ["lms", "--version"],
                    capture_output=True,
                creationflags=NO_WINDOW,
                    text=True,
                    timeout=10,
                )
                version = result.stdout.strip() if result.returncode == 0 else None
            except Exception:
                version = None

            try:
                result = subprocess.run(
                    ["lms", "ps"],
                    capture_output=True,
                creationflags=NO_WINDOW,
                    text=True,
                    timeout=10,
                )
                models = []
                if result.returncode == 0:
                    lines = result.stdout.strip().split("\n")[1:]
                    for line in lines:
                        parts = line.split()
                        if parts:
                            models.append(parts[0])
            except Exception:
                models = []

            identity = ProviderIdentity(
                provider_id="lm-studio.local",
                display_name=signature["display_name"],
                provider_class=signature["provider_class"],
                version=version,
                install_path=str(exe_path.parent.parent),
                executable_path=str(exe_path),
                discovery_source=DiscoverySource.PROCESS_LIST,
            )
            health = ProviderHealth(
                is_available=True,
                is_healthy=True,
                last_probe_at=datetime.now(UTC),
                details={"models": models},
            )
        else:
            # Check common paths
            for path_template in signature["common_paths"]:
                path = Path(expand_user(path_template))
                if path.exists():
                    health = ProviderHealth(
                        is_available=True,
                        is_healthy=False,
                        last_probe_at=datetime.now(UTC),
                        error_message="Installed but lms CLI not in PATH",
                        details={"install_path": str(path)},
                    )
                    identity = ProviderIdentity(
                        provider_id="lm-studio.local",
                        display_name=signature["display_name"],
                        provider_class=signature["provider_class"],
                        install_path=str(path),
                        discovery_source=DiscoverySource.FILESYSTEM_SCAN,
                    )
                    break

        return ExecutionResult(
            success=True,
            output={"identity": identity.as_dict() if identity else None, "health": health.as_dict()},
        )


class DiscoverClaudeDesktopAction(Action):
    """Discover Claude Desktop application."""

    name = "ai_infrastructure.discover_claude_desktop"
    description = "Discover Claude Desktop installation"
    risk_tier = RiskTier.READ_ONLY
    permission_category = PermissionCategory.READ
    expected_result = "Claude Desktop installation details or not found"

    def required_parameters(self) -> list[str]:
        return []

    def validate(self, parameters: dict[str, Any]) -> list[str]:
        return []

    def run(self, parameters: dict[str, Any]) -> ExecutionResult:
        signature = PROVIDER_SIGNATURES["claude-desktop"]
        identity = None
        health = ProviderHealth(is_available=False)

        for path_template in signature["common_paths"]:
            path = Path(expand_user(path_template))
            if path.exists():
                # Try to get version from app
                version = None
                try:
                    # On Windows, check for version in executable
                    if sys.platform == "win32":
                        exe = path / "Claude.exe"
                        if exe.exists():
                            # Could use win32api to get file version
                            pass
                except Exception:
                    pass

                identity = ProviderIdentity(
                    provider_id="claude-desktop",
                    display_name=signature["display_name"],
                    provider_class=signature["provider_class"],
                    version=version,
                    install_path=str(path),
                    discovery_source=DiscoverySource.FILESYSTEM_SCAN,
                )
                health = ProviderHealth(
                    is_available=True,
                    is_healthy=True,
                    last_probe_at=datetime.now(UTC),
                    details={"install_path": str(path)},
                )
                break

        return ExecutionResult(
            success=True,
            output={"identity": identity.as_dict() if identity else None, "health": health.as_dict()},
        )


class DiscoverCloudProvidersAction(Action):
    """Discover configured cloud providers from Broker catalog/registry."""

    name = "ai_infrastructure.discover_cloud_providers"
    description = "Discover cloud providers enabled in configuration"
    risk_tier = RiskTier.READ_ONLY
    permission_category = PermissionCategory.READ
    expected_result = "List of configured cloud providers"

    def required_parameters(self) -> list[str]:
        return ["enabled_providers"]

    def validate(self, parameters: dict[str, Any]) -> list[str]:
        if "enabled_providers" not in parameters:
            return ["missing required parameter: enabled_providers"]
        return []

    def run(self, parameters: dict[str, Any]) -> ExecutionResult:
        enabled = parameters.get("enabled_providers", [])
        entries = []

        for provider_id in enabled:
            if provider_id == "openai.api":
                identity = ProviderIdentity(
                    provider_id="openai.api",
                    display_name="OpenAI API",
                    provider_class=ProviderClass.CLOUD_API,
                    discovery_source=DiscoverySource.CONFIG_DECLARED,
                )
                health = ProviderHealth(
                    is_available=True,
                    is_healthy=True,
                    last_probe_at=datetime.now(UTC),
                    details={"needs_credentials": True},
                )
                entries.append({"identity": identity.as_dict(), "health": health.as_dict()})
            elif provider_id == "openrouter.api":
                identity = ProviderIdentity(
                    provider_id="openrouter.api",
                    display_name="OpenRouter",
                    provider_class=ProviderClass.CLOUD_AGGREGATOR,
                    discovery_source=DiscoverySource.CONFIG_DECLARED,
                )
                health = ProviderHealth(
                    is_available=True,
                    is_healthy=True,
                    last_probe_at=datetime.now(UTC),
                    details={"needs_credentials": True},
                )
                entries.append({"identity": identity.as_dict(), "health": health.as_dict()})

        return ExecutionResult(success=True, output={"entries": entries})


# ---- Registry of all discovery actions ------------------------------------

DISCOVERY_ACTIONS = [
    DiscoverOllamaAction,
    DiscoverLMStudioAction,
    DiscoverClaudeDesktopAction,
    DiscoverCloudProvidersAction,
]

DISCOVERY_ACTION_CLASSES = DISCOVERY_ACTIONS


def get_all_discovery_actions() -> list[type[Action]]:
    """Get all discovery action classes."""
    return DISCOVERY_ACTION_CLASSES