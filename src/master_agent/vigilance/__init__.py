"""Vigilance — the proof that makes *"Nothing needs you"* honest.

VEDA 04 D7. A coverage check across every monitored domain, and a calm
state that cannot be constructed without one.

Outside `foundation/`: that package's door admits a module only if every
layer above it needs it, and it aggregates exports in an `__init__` three
shipped milestones have left byte-identical.
"""
from __future__ import annotations

from master_agent.vigilance.vigilance import (
    CalmState,
    Coverage,
    Domain,
    DomainRegistry,
    DomainReport,
    DomainStatus,
    Gap,
    GapKind,
    InvalidDomain,
    UnknownDomain,
    VigilanceAttestation,
    VigilanceIncomplete,
)

__all__ = [
    "CalmState",
    "Coverage",
    "Domain",
    "DomainRegistry",
    "DomainReport",
    "DomainStatus",
    "Gap",
    "GapKind",
    "InvalidDomain",
    "UnknownDomain",
    "VigilanceAttestation",
    "VigilanceIncomplete",
]
