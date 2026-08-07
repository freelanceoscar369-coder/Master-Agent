"""Capability contracts (Mission Brief 039).

What a capability takes, what it returns, and what calling it does to the
world — published as machine-readable data rather than as a sentence of
prose.

MB036's Planner named the right capability and got its arguments wrong.
MB037's first live plan got **both** payloads wrong. Neither was a model
failure: `CapabilityManifest.input_schema` has existed since MB002 and is
populated by nothing, so the only thing published about an argument was
its absence.

**This package is metadata only.** It describes; it never invokes. A test
parses it for the vocabulary of execution and fails on any of it.
"""
from master_agent.capabilities.contract import (
    ARRAY,
    BOOLEAN,
    FIELD_TYPES,
    IDEMPOTENCY,
    IDEMPOTENT,
    INSTANT,
    INTEGER,
    IRREVERSIBLE,
    LATENCY_CLASSES,
    NO_EFFECT,
    NOT_IDEMPOTENT,
    NUMBER,
    OBJECT,
    RETRY_CONDITIONAL,
    RETRY_SAFE,
    RETRY_UNSAFE,
    RETRYABILITY,
    REVERSIBLE,
    SIDE_EFFECT_BY_RISK,
    SIDE_EFFECTS,
    SLOW,
    STRING,
    UNKNOWN,
    VERY_SLOW,
    CapabilityContract,
    FieldSpec,
    Permissions,
    Schema,
    Version,
)
from master_agent.capabilities.extraction import (
    EXTRACTED_VERSION,
    SOURCE_ACTION,
    contract_from_action,
    contracts_from_actions,
)
from master_agent.capabilities.index import (
    CapabilityIndex,
    IndexEntry,
    build_index,
    entry_for,
)

__all__ = [
    "ARRAY",
    "BOOLEAN",
    "EXTRACTED_VERSION",
    "FIELD_TYPES",
    "IDEMPOTENCY",
    "IDEMPOTENT",
    "INSTANT",
    "INTEGER",
    "IRREVERSIBLE",
    "LATENCY_CLASSES",
    "NOT_IDEMPOTENT",
    "NO_EFFECT",
    "NUMBER",
    "OBJECT",
    "RETRYABILITY",
    "RETRY_CONDITIONAL",
    "RETRY_SAFE",
    "RETRY_UNSAFE",
    "REVERSIBLE",
    "SIDE_EFFECTS",
    "SIDE_EFFECT_BY_RISK",
    "SLOW",
    "SOURCE_ACTION",
    "STRING",
    "UNKNOWN",
    "VERY_SLOW",
    "CapabilityContract",
    "CapabilityIndex",
    "FieldSpec",
    "IndexEntry",
    "Permissions",
    "Schema",
    "Version",
    "build_index",
    "contract_from_action",
    "contracts_from_actions",
    "entry_for",
]
