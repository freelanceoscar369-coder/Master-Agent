"""Founder Edition Boot Sequence — C24.

Assembles the completed Sprint 1 components into one runnable application:
`boot_founder_edition()` runs Boot → Initialize Runtime → Initialize
Presence → Initialize Environment Intelligence → Initialize Conversation →
Connect Founder Runtime → Render Founder Surface → Ready, and returns a
`FounderEditionApp` whose first `snapshot()` already carries live state.

**Orchestration only.** Every value produced was derived by a component
that already existed — `desktop.inventory.discover`, `environment_intelligence
.derive_intelligence`, `vigilance.VigilanceAttestation`, `memory.conversation
.ConversationMemory`, `founder_runtime.FounderRuntime` — and this package
adds no inference of its own. See `boot.py` for why the steps run in this
order and where the boundary with the TypeScript Founder Surface sits.
"""
from __future__ import annotations

from master_agent.founder_edition.boot import (
    DEFAULT_FOUNDER_NAME,
    OK,
    OUT_OF_SCOPE,
    SOMESH,
    STEP_NAMES,
    UNAVAILABLE,
    BootReport,
    BootStep,
    FounderEditionApp,
    boot_founder_edition,
)
from master_agent.founder_edition.dashboard import (
    DASHBOARD_SECTIONS,
    founder_dashboard,
)
from master_agent.founder_edition.desktop_layer import DesktopLayer

__all__ = [
    "DASHBOARD_SECTIONS",
    "DEFAULT_FOUNDER_NAME",
    "OK",
    "OUT_OF_SCOPE",
    "SOMESH",
    "STEP_NAMES",
    "UNAVAILABLE",
    "BootReport",
    "BootStep",
    "DesktopLayer",
    "FounderEditionApp",
    "boot_founder_edition",
    "founder_dashboard",
]
