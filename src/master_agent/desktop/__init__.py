"""The Desktop Executive (Mission Brief 030) — eyes and hands over the
local machine. Discovers installed software, reports versions, lists
running processes, and launches, opens, or closes applications.

It executes; it never decides. Choosing between what it finds belongs to
the AI Capability Broker.
"""
from master_agent.desktop.plugin import (
    DESKTOP_EXECUTIVE_ID,
    DESKTOP_VERSION,
    DesktopPlugin,
)

__all__ = ["DESKTOP_EXECUTIVE_ID", "DESKTOP_VERSION", "DesktopPlugin"]
