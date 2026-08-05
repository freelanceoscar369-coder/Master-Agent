"""Foundation — the things every other layer depends on and nothing depends
back on.

A module belongs here only if it satisfies three conditions: it has no
dependency on any other Kalpavriksha package, every layer above it needs
it, and building it late would force a retrofit across everything written
before it. That is a deliberately narrow door — `foundation/` is not a
utilities drawer, and a helper that only two callers need does not belong
here.

See SPRING_1_IMPLEMENTATION_PLAN.md §3 for the dependency graph this
package sits at the root of.
"""
from __future__ import annotations

from master_agent.foundation.attestation import (
    Attestation,
    AttestationQuestion,
    AttestationVerdict,
    InvalidAttestation,
)
from master_agent.foundation.clock import (
    Clock,
    Instant,
    ManualClock,
    SystemClock,
)
from master_agent.foundation.consequence import (
    Consequence,
    Cost,
    CostBasis,
    InvalidConsequence,
)
from master_agent.foundation.execution_context import ExecutionContext
from master_agent.foundation.principal import (
    InvalidPrincipalRegistry,
    Principal,
    PrincipalKind,
    PrincipalRegistry,
    UnknownPrincipal,
)
from master_agent.foundation.receipt import (
    ExecutionOutcome,
    InvalidReceipt,
    Receipt,
)
from master_agent.foundation.warrant import (
    InvalidWarrant,
    ReversibilityClass,
    Warrant,
)

__all__ = [
    "Attestation",
    "AttestationQuestion",
    "AttestationVerdict",
    "Clock",
    "Consequence",
    "Cost",
    "CostBasis",
    "ExecutionContext",
    "ExecutionOutcome",
    "Instant",
    "InvalidAttestation",
    "InvalidConsequence",
    "InvalidPrincipalRegistry",
    "InvalidReceipt",
    "InvalidWarrant",
    "ManualClock",
    "Principal",
    "PrincipalKind",
    "PrincipalRegistry",
    "Receipt",
    "ReversibilityClass",
    "SystemClock",
    "UnknownPrincipal",
    "Warrant",
]
