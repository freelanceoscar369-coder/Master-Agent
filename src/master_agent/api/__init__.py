"""Kernel API — the single integration boundary.

Everything above the Kernel reaches it through this package and through no
other route. Kernel Specification §3.6 places the Kernel in Shared
Infrastructure with *"dependency direction strictly downward"*; this is
the one door in that direction, so a surface can consume the constitution
without importing it.
"""
from __future__ import annotations

from master_agent.api.kernel_api import (
    ApiResponse,
    InvalidKernelApi,
    KernelApi,
    Operation,
    ResultKind,
)

__all__ = [
    "ApiResponse",
    "InvalidKernelApi",
    "KernelApi",
    "Operation",
    "ResultKind",
]
