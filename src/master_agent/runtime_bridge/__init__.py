"""Runtime Integration Layer — the bridge between a surface and the Kernel.

Transport, serialization and wiring. No authority, no state, no decision.

Deliberately **not** inside `master_agent/runtime/`, which is the shipped
Runtime Engine (MB024): importing through that package's `__init__` would
give this layer a dependency the C18 brief forbids.
"""
from __future__ import annotations

from master_agent.runtime_bridge.codec import (
    InvalidEnvelope,
    decode_outcome,
    decode_request,
    encode_outcome,
    encode_request,
)
from master_agent.runtime_bridge.runtime import (
    ARGUMENTS,
    OPERATION,
    InvalidRuntime,
    Runtime,
)

__all__ = [
    "ARGUMENTS",
    "OPERATION",
    "InvalidEnvelope",
    "InvalidRuntime",
    "Runtime",
    "decode_outcome",
    "decode_request",
    "encode_outcome",
    "encode_request",
]
