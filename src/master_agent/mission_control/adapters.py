"""Registering existing Executives without modifying them.

Mission Brief 023's hardest acceptance criterion: Mission Control must
work "without requiring modifications to existing Executives." This module
is how that is satisfied — an adapter that *reads* a plugin's long-standing
`manifest` (name, version, capability list, risk tier, permission
category), rather than an interface every existing plugin would have to
grow.

`BrowserPlugin` (Mission Brief 022) and `FilesystemPlugin` (Mission Brief
005) register through this unchanged; neither file is touched by Mission
Brief 023. A future Desktop/Git/Research Executive that implements the
same `Plugin` contract registers the same way, with no Mission Control
change either.

Executives that are not Plugins (a future out-of-process or remote one)
register through MissionControl.register_executive() directly — this
adapter is a convenience over that primitive, never the only door. See
MISSION_CONTROL_ARCHITECTURE.md §9.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from master_agent.mission_control.capabilities import CapabilityDescriptor, qualified_name
from master_agent.mission_control.executives import ExecutiveHealth
from master_agent.plugins.base import Plugin

if TYPE_CHECKING:  # pragma: no cover - import cycle avoidance only
    from master_agent.mission_control.mission_control import MissionControl


def describe_plugin_capabilities(plugin: Plugin) -> list[CapabilityDescriptor]:
    """Derives Mission Control capability descriptors from a plugin's own
    manifest. Reads only the public `Plugin` contract — nothing here
    depends on a specific plugin's internals, which is what keeps this
    working for plugins that do not exist yet."""
    manifest = plugin.manifest
    descriptors: list[CapabilityDescriptor] = []
    for capability in manifest.capabilities:
        descriptors.append(
            CapabilityDescriptor(
                qualified_name=qualified_name(manifest.name, capability.name),
                executive_id=manifest.name,
                capability=capability.name,
                description=capability.description,
                risk_tier=capability.risk_tier.value if capability.risk_tier else None,
                permission_category=(
                    capability.permission_category.value
                    if capability.permission_category
                    else None
                ),
            )
        )
    return descriptors


def register_plugin_as_executive(
    mission_control: MissionControl,
    plugin: Plugin,
    dependencies: list[str] | None = None,
    health: ExecutiveHealth = ExecutiveHealth.HEALTHY,
    ready: bool = True,
) -> str:
    """Registers `plugin` with Mission Control as an Executive, deriving
    everything from its manifest. Returns the Executive ID.

    `ready=True` walks the new Executive through the real lifecycle
    (CREATED -> INITIALIZED -> READY) rather than constructing it directly
    in READY — the transition table is the source of truth for what states
    are reachable, and skipping it here would make the registry's history
    a lie about how the Executive actually got there.
    """
    manifest = plugin.manifest
    descriptors = describe_plugin_capabilities(plugin)

    executive_id = mission_control.register_executive(
        executive_id=manifest.name,
        version=manifest.version,
        capabilities=descriptors,
        dependencies=dependencies or [],
        health=health,
    )
    if ready:
        mission_control.mark_executive_ready(executive_id)
    return executive_id
