"""The Kalpavriksha Launcher (Mission Brief 027.5) — the founder's single
entry point.

Public surface is deliberately small: `build_system()` constructs a fully
wired Kalpavriksha and reports honestly on what came up, and
`KalpavrikshaSystem` is the handle that starts and stops it.
"""
from master_agent.launcher.boot import (
    BootReport,
    BootStep,
    KalpavrikshaSystem,
    build_system,
)

__all__ = ["BootReport", "BootStep", "KalpavrikshaSystem", "build_system"]
