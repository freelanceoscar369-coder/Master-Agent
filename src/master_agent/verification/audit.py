"""Audit records — see KALPAVRIKSHA_VISION_V2.md §5.6 (Telemetry and
Audit) and BROWSER_WORKER_ARCHITECTURE.md §10.

Deliberately separate from LocalExecutor's own ExecutionLogEntry
(executor/executor.py) rather than an edit to it: ExecutionLogEntry is
shared, existing infrastructure every Action in the codebase already
depends on, and changing its shape risks every existing caller and test.
AuditRecord is a strictly additive, richer record a Worker Lifecycle
facade (BrowserWorker is the first) builds on top of a LocalExecutor
call, carrying fields (requested_by, Verification Verdict, Evidence id)
ExecutionLogEntry was never asked to carry and was not designed to.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from master_agent.verification.evidence import Verdict


@dataclass
class AuditRecord:
    audit_id: str
    requested_by: str
    worker: str
    environment: str
    action_name: str
    started_at: datetime
    ended_at: datetime
    execution_success: bool
    verification_verdict: Verdict | None
    evidence_id: str | None
    errors: list[str] = field(default_factory=list)
    payload_summary: dict[str, Any] = field(default_factory=dict)


class AuditLog:
    """Append-only, in-process. Never truncated, never overwritten — see
    KALPAVRIKSHA_VISION_V2.md §15.4 ("Transparency Over Trust") and this
    Mission Brief's "never lose execution history" requirement. Bounding
    or persisting this for a long-running daemon is the same, already-named
    ROADMAP.md item LocalExecutor._log has (MEMORY_ARCHITECTURE.md §11) —
    not solved differently here."""

    def __init__(self) -> None:
        self._records: list[AuditRecord] = []

    def append(self, record: AuditRecord) -> None:
        self._records.append(record)

    @property
    def records(self) -> list[AuditRecord]:
        return list(self._records)

    def for_evidence(self, evidence_id: str) -> AuditRecord | None:
        return next((r for r in self._records if r.evidence_id == evidence_id), None)
