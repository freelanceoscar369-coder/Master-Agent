"""The Founder Interaction Audit Trail (ADR-0025).

Deliberately a package of its own. This is neither Memory nor Knowledge,
and keeping it out of `memory/` is what stops it drifting into either.
"""
from master_agent.audit.interaction import (
    CHIEF_OF_STAFF,
    FILENAME,
    FOUNDER,
    InteractionLog,
    InteractionRecord,
    JsonlInteractionStore,
)

__all__ = [
    "CHIEF_OF_STAFF",
    "FILENAME",
    "FOUNDER",
    "InteractionLog",
    "InteractionRecord",
    "JsonlInteractionStore",
]
