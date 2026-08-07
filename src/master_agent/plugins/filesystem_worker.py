"""FilesystemWorker -- the Worker Lifecycle facade for filesystem capabilities.
See VERIFICATION_SYSTEM.md and BROWSER_WORKER_ARCHITECTURE.md §10.

Sequences exactly three mechanical steps -- Execute, Verify, Audit -- and
returns everything it did to the caller. It decides nothing: which
capability to run, what payload to send, and what an Expected Outcome
should be are all supplied by the caller (standing in for the Executive
Brain until a real Planner exists -- see docs/MISSION_BRIEF_022.md). This
class must never grow a retry loop, a re-planning branch, or a call into
Memory/Knowledge -- those are Brain/Recovery responsibilities
(KALPAVRIKSHA_VISION_V2.md §3, §11), explicitly out of scope for a Worker.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from master_agent.executor.action import default_locations
from master_agent.executor.executor import LocalExecutor
from master_agent.plugins.filesystem_verifier import FilesystemVerifier
from master_agent.verification.audit import AuditLog, AuditRecord
from master_agent.verification.evidence import Evidence, ExpectedOutcome


@dataclass
class FilesystemStepReport:
    """Everything one call to run_step() produced -- the artifact Founder
    Review questions 6/7 ("is Verification structurally independent, is
    Evidence produced independently of execution") are checked against."""

    execution: Any  # ExecutionResult
    evidence: Evidence | None
    audit: AuditRecord


class FilesystemWorker:
    def __init__(
        self,
        executor: LocalExecutor,
        audit_log: AuditLog | None = None,
        locations: dict[str, Path] | None = None,
    ) -> None:
        self._executor = executor
        self._audit_log = audit_log if audit_log is not None else AuditLog()
        self._locations = locations or default_locations()

    @property
    def audit_log(self) -> AuditLog:
        return self._audit_log

    def run_step(
        self,
        capability: str,
        payload: dict[str, Any],
        requested_by: str,
        expected_outcome: ExpectedOutcome | None = None,
        include_content_preview: bool = False,
        include_directory_listing: bool = False,
    ) -> FilesystemStepReport:
        started_at = datetime.now(UTC)

        # 1. Execute -- the existing, unmodified LocalExecutor. Filesystem
        # Actions are registered on it exactly the way Browser Actions are;
        # no new Executor variant exists or was needed.
        execution = self._executor.execute(capability, payload)

        # 2. Verify -- only if the caller supplied something to check
        # against. Execution succeeding never implies this step is skipped
        # or assumed to have passed; if no ExpectedOutcome was given, this
        # step honestly produces no Evidence rather than fabricating a
        # verdict.
        evidence: Evidence | None = None
        if expected_outcome is not None:
            # Resolve the target path from the payload
            target_path = self._resolve_target_path(payload)
            # Use the location's base as the base path
            location_key = (payload.get("location") or "desktop").strip().lower()
            base_path = self._locations.get(location_key)
            if base_path is None:
                base_path = list(self._locations.values())[0]

            verifier = FilesystemVerifier(
                target_path=str(target_path),
                base_path=str(base_path),
                include_content_preview=include_content_preview,
                include_directory_listing=include_directory_listing,
            )
            evidence = verifier.verify(expected_outcome)

        # 3. Audit -- never lose execution history (this Mission Brief's
        # explicit requirement); appended, never overwritten.
        ended_at = datetime.now(UTC)
        record = AuditRecord(
            audit_id=str(uuid4()),
            requested_by=requested_by,
            worker="filesystem",
            environment="filesystem_environment",
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

        return FilesystemStepReport(execution=execution, evidence=evidence, audit=record)

    def _resolve_target_path(self, payload: dict[str, Any]) -> Path:
        """Resolve the target path from payload parameters."""
        location_key = (payload.get("location") or "desktop").strip().lower()
        base = self._locations.get(location_key)
        if base is None:
            base = list(self._locations.values())[0]

        # Different capabilities use different parameter names
        if "path" in payload:
            path = payload["path"].strip()
        elif "name" in payload:
            path = payload["name"].strip()
        elif "source" in payload:
            path = payload["source"].strip()
        elif "destination" in payload:
            path = payload["destination"].strip()
        else:
            path = "."

        return base / path