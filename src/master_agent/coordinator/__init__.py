"""Execution Coordinator — §6.1's four lines, made structural.

Kernel Specification §6.1 states the exit protocol every caller must
follow. This package is that protocol written once, so no caller writes
it again and no caller writes it differently.

Placed outside `foundation/` and outside `kernel/`: it depends on both,
and neither depends on it. §3.6's dependency direction is strictly
downward, and this sits one layer above the Kernel.
"""
from __future__ import annotations

from master_agent.coordinator.coordinator import (
    Execution,
    ExecutionCoordinator,
    InvalidCoordinator,
    Work,
)

__all__ = [
    "Execution",
    "ExecutionCoordinator",
    "InvalidCoordinator",
    "Work",
]
