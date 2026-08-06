"""Kernel — the single point at which the constitution is enforced.

Kernel Specification §3.6 places it in **Shared Infrastructure**: both the
Brain and the Operator depend on it, and neither depends on the other.

Outside `foundation/` because it depends on two other packages —
`foundation` and `ledger` — and `foundation/` admits a module only if it
has no dependency on any other Kalpavriksha package.
"""
from __future__ import annotations

from master_agent.kernel.kernel import (
    SCOPE_ALL,
    AdmissionProvider,
    AttemptNotAuthorized,
    InvalidKernel,
    Kernel,
    NothingToSettle,
)

__all__ = [
    "SCOPE_ALL",
    "AdmissionProvider",
    "AttemptNotAuthorized",
    "InvalidKernel",
    "Kernel",
    "NothingToSettle",
]
