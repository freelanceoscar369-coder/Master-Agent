"""Ledger — the append-only record of what was authorized and what happened.

VEDA 04 A1. Sits outside `foundation/` because it depends on
`persistence.StateStore`, and `foundation/`'s own rule is that a module
belongs there only if it has **no dependency on any other Kalpavriksha
package**.

It writes through a `StateStore` and never opens a file itself:
`persistence` remains *"the only place in Kalpavriksha that reads or
writes persistence files."*
"""
from __future__ import annotations

from master_agent.ledger.receipt_ledger import (
    AttemptRecord,
    IntentRecord,
    InvalidLedgerRecord,
    LedgerIntegrityError,
    LedgerUnavailable,
    ReceiptLedger,
    RecordKind,
)

__all__ = [
    "AttemptRecord",
    "IntentRecord",
    "InvalidLedgerRecord",
    "LedgerIntegrityError",
    "LedgerUnavailable",
    "ReceiptLedger",
    "RecordKind",
]
