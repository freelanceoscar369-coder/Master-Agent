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

from master_agent.foundation.admission import (
    AdmissionRecord,
    InvalidAdmissionRecord,
    ObjectiveState,
)
from master_agent.foundation.attempt_token import (
    FIRST_ATTEMPT,
    AttemptToken,
    InvalidAttemptToken,
)
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
from master_agent.foundation.execution_request import (
    PENDING_CONSEQUENCE_ENGINE,
    ActionClass,
    ExecutionRequest,
    InvalidExecutionRequest,
    PendingConsequenceEngine,
)
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
from master_agent.foundation.refusal import (
    InvalidKernelRefusal,
    KernelCheck,
    KernelRefusal,
    RefusalFamily,
    RefusalReason,
)
from master_agent.foundation.reversibility import (
    Classification,
    InvalidClassification,
    ReversibilityRegistry,
    Unclassified,
)
from master_agent.foundation.warrant import (
    InvalidWarrant,
    ReversibilityClass,
    Warrant,
)

__all__ = [
    "FIRST_ATTEMPT",
    "PENDING_CONSEQUENCE_ENGINE",
    "ActionClass",
    "AdmissionRecord",
    "AttemptToken",
    "Attestation",
    "AttestationQuestion",
    "AttestationVerdict",
    "Classification",
    "Clock",
    "Consequence",
    "Cost",
    "CostBasis",
    "ExecutionContext",
    "ExecutionOutcome",
    "ExecutionRequest",
    "Instant",
    "InvalidAdmissionRecord",
    "InvalidAttemptToken",
    "InvalidAttestation",
    "InvalidClassification",
    "InvalidConsequence",
    "InvalidExecutionRequest",
    "InvalidKernelRefusal",
    "InvalidPrincipalRegistry",
    "InvalidReceipt",
    "InvalidWarrant",
    "KernelCheck",
    "KernelRefusal",
    "ManualClock",
    "ObjectiveState",
    "PendingConsequenceEngine",
    "Principal",
    "PrincipalKind",
    "PrincipalRegistry",
    "Receipt",
    "RefusalFamily",
    "RefusalReason",
    "ReversibilityClass",
    "ReversibilityRegistry",
    "SystemClock",
    "Unclassified",
    "UnknownPrincipal",
    "Warrant",
]
