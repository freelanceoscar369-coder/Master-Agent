"""BrowserWorker — the Worker Lifecycle facade. See
BROWSER_WORKER_ARCHITECTURE.md §10.

Sequences exactly three mechanical steps — Execute, Verify, Audit — and
returns everything it did to the caller. It decides nothing: which
capability to run, what payload to send, and what an Expected Outcome
should be are all supplied by the caller (standing in for the Executive
Brain until a real Planner exists — see docs/MISSION_BRIEF_022.md). This
class must never grow a retry loop, a re-planning branch, or a call into
Memory/Knowledge — those are Brain/Recovery responsibilities
(KALPAVRIKSHA_VISION_V2.md §3, §11), explicitly out of scope for a Worker.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from master_agent.environment.browser_session import BrowserSessionManager
from master_agent.executor.action import ExecutionResult
from master_agent.executor.executor import LocalExecutor
from master_agent.plugins.browser_verifier import BrowserVerifier
from master_agent.verification.audit import AuditLog, AuditRecord
from master_agent.verification.evidence import Evidence, ExpectedOutcome


@dataclass
class BrowserStepReport:
    """Everything one call to run_step() produced — the artifact Founder
    Review questions 6/7 ("is Verification structurally independent, is
    Evidence produced independently of execution") are checked against."""

    execution: ExecutionResult
    evidence: Evidence | None
    audit: AuditRecord


class BrowserWorker:
    def __init__(
        self,
        executor: LocalExecutor,
        sessions: BrowserSessionManager,
        audit_log: AuditLog | None = None,
    ) -> None:
        self._executor = executor
        self._sessions = sessions
        self._audit_log = audit_log if audit_log is not None else AuditLog()

    @property
    def audit_log(self) -> AuditLog:
        return self._audit_log

    def run_step(
        self,
        capability: str,
        payload: dict[str, Any],
        requested_by: str,
        expected_outcome: ExpectedOutcome | None = None,
        verify_session_id: str | None = None,
        verify_selectors: list[str] | None = None,
        verify_accessibility_tree: bool = False,
        verify_available_actions: bool = False,
    ) -> BrowserStepReport:
        started_at = datetime.now(UTC)

        # 1. Execute -- the existing, unmodified LocalExecutor. Browser
        # Actions are registered on it exactly the way Filesystem Actions
        # are; no new Executor variant exists or was needed.
        execution = self._executor.execute(capability, payload)

        # 2. Verify -- only if the caller supplied something to check
        # against. Execution succeeding never implies this step is skipped
        # or assumed to have passed; if no ExpectedOutcome was given, this
        # step honestly produces no Evidence rather than fabricating a
        # verdict.
        evidence: Evidence | None = None
        if expected_outcome is not None:
            session_id = verify_session_id or payload.get("session_id")
            verifier = BrowserVerifier(
                self._sessions,
                session_id,
                verify_selectors,
                include_accessibility_tree=verify_accessibility_tree,
                include_available_actions=verify_available_actions,
            )
            evidence = verifier.verify(expected_outcome)

        # 3. Audit -- never lose execution history (this Mission Brief's
        # explicit requirement); appended, never overwritten.
        ended_at = datetime.now(UTC)
        record = AuditRecord(
            audit_id=str(uuid4()),
            requested_by=requested_by,
            worker="browser",
            environment="browser_environment",
            action_name=capability,
            started_at=started_at,
            ended_at=ended_at,
            execution_success=execution.success,
            verification_verdict=evidence.verdict if evidence else None,
            evidence_id=evidence.evidence_id if evidence else None,
            errors=list(execution.errors) + (list(evidence.errors) if evidence else []),
            payload_summary=dict(payload),
        )
        self._audit_log.append(record)

        return BrowserStepReport(execution=execution, evidence=evidence, audit=record)
