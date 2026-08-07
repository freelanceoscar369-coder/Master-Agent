"""Reporter — converts internal state into founder-facing responses.

Constitution §3.4: Takes Mission outcome + Evidence once Verification produces
Verdict, composes human-facing report (text today; voice later). Decides
*how to explain* — Brain-shaped judgment (what to say, detail, tone), not
execution fact. Never touches Environment; only reads Evidence and Mission
state through Shared Infrastructure.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from master_agent.verification.evidence import Evidence, Verdict
from master_agent.mission_manager.mission import Mission, MissionStatus


class ReportFormat(str, Enum):
    """Output format for reports."""
    TEXT = "text"
    JSON = "json"
    SUMMARY = "summary"


class ReportTone(str, Enum):
    """Tone for the report."""
    CONCISE = "concise"
    DETAILED = "detailed"
    TECHNICAL = "technical"


@dataclass
class ReportContext:
    """Context for generating a report."""
    format: ReportFormat = ReportFormat.TEXT
    tone: ReportTone = ReportTone.CONCISE
    include_evidence_details: bool = False
    include_timing: bool = True
    max_steps_detail: int = 5


@dataclass
class Report:
    """A generated report for the founder."""
    title: str
    body: str
    format: ReportFormat = ReportFormat.TEXT
    generated_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "body": self.body,
            "format": self.format.value,
            "generated_at": self.generated_at.isoformat(),
            "metadata": self.metadata,
        }


class Reporter:
    """Generates founder-facing reports from Mission outcomes and Evidence.

    The Reporter is the Brain's voice — it decides what to say, how much
    detail to include, and what tone to use. It never executes anything
    or touches any Environment. It only reads from Shared Infrastructure
    (Mission state, Evidence, Memory).
    """

    def __init__(self) -> None:
        self._templates = {
            "mission_completed": self._template_mission_completed,
            "mission_failed": self._template_mission_failed,
            "mission_cancelled": self._template_mission_cancelled,
            "plan_refused": self._template_plan_refused,
            "plan_rejected": self._template_plan_rejected,
            "step_completed": self._template_step_completed,
            "step_failed": self._template_step_failed,
            "approval_required": self._template_approval_required,
            "clarification_needed": self._template_clarification_needed,
        }

    def report_mission_outcome(
        self,
        mission: Mission,
        evidence_list: list[Evidence] | None = None,
        context: ReportContext | None = None,
    ) -> Report:
        """Generate a report for a completed/failed/cancelled mission."""
        ctx = context or ReportContext()
        evidence_list = evidence_list or []

        if mission.status == MissionStatus.COMPLETED:
            template = self._templates["mission_completed"]
        elif mission.status == MissionStatus.FAILED:
            template = self._templates["mission_failed"]
        elif mission.status == MissionStatus.CANCELLED:
            template = self._templates["mission_cancelled"]
        else:
            # For in-progress missions
            template = self._templates["mission_completed"]

        return template(mission, evidence_list, ctx)

    def report_plan_result(
        self,
        objective: str,
        planned: bool,
        refusal_reason: str | None = None,
        rejection_reasons: tuple[str, ...] = (),
        provider_id: str | None = None,
        context: ReportContext | None = None,
    ) -> Report:
        """Generate a report for a planning outcome (refused/rejected/accepted)."""
        ctx = context or ReportContext()

        if not planned and refusal_reason:
            return self._templates["plan_refused"](
                objective, refusal_reason, provider_id, ctx
            )
        elif not planned and rejection_reasons:
            return self._templates["plan_rejected"](
                objective, rejection_reasons, provider_id, ctx
            )
        else:
            return Report(
                title="Plan Accepted",
                body=f"Objective accepted for execution: {objective}",
                format=ctx.format,
                metadata={"objective": objective, "provider_id": provider_id},
            )

    def report_step_result(
        self,
        step_id: str,
        capability: str,
        success: bool,
        output: Any = None,
        error: str | None = None,
        evidence: Evidence | None = None,
        context: ReportContext | None = None,
    ) -> Report:
        """Generate a report for a single step outcome."""
        ctx = context or ReportContext()

        if success:
            return self._templates["step_completed"](
                step_id, capability, output, evidence, ctx
            )
        else:
            return self._templates["step_failed"](
                step_id, capability, error, evidence, ctx
            )

    def report_approval_required(
        self,
        mission_title: str,
        capability: str,
        payload: dict[str, Any],
        consequence: str,
        context: ReportContext | None = None,
    ) -> Report:
        """Generate an approval request report."""
        ctx = context or ReportContext()
        return self._templates["approval_required"](
            mission_title, capability, payload, consequence, ctx
        )

    def report_clarification_needed(
        self,
        question: str,
        options: tuple[str, ...] = (),
        context: ReportContext | None = None,
    ) -> Report:
        """Generate a clarification request report."""
        ctx = context or ReportContext()
        return self._templates["clarification_needed"](question, options, ctx)

    # --- Template Methods ---

    def _template_mission_completed(
        self,
        mission: Mission,
        evidence_list: list[Evidence],
        ctx: ReportContext,
    ) -> Report:
        lines = [f"✅ Mission Completed: {mission.intent_summary}"]

        if ctx.include_timing and mission.updated_at and mission.created_at:
            duration = (mission.updated_at - mission.created_at).total_seconds()
            lines.append(f"Duration: {duration:.1f}s")

        if evidence_list:
            matched = sum(1 for e in evidence_list if e.verdict == Verdict.MATCHED)
            not_matched = sum(1 for e in evidence_list if e.verdict == Verdict.NOT_MATCHED)
            partial = sum(1 for e in evidence_list if e.verdict == Verdict.PARTIALLY_MATCHED)
            error = sum(1 for e in evidence_list if e.verdict == Verdict.ERROR)

            lines.append(f"Verification: {matched} matched, {partial} partial, {not_matched} not matched, {error} errors")

            if ctx.include_evidence_details and ctx.tone == ReportTone.DETAILED:
                for ev in evidence_list:
                    lines.append(f"  • {ev.worker}.{ev.environment}: {ev.verdict.value}")
                    if ev.check_results:
                        for cr in ev.check_results:
                            status = "✓" if cr.passed else "✗"
                            lines.append(f"    {status} {cr.check.field} {cr.check.operator} {cr.check.value}")

        if ctx.tone == ReportTone.CONCISE:
            body = lines[0]
            if len(lines) > 1:
                body += f" ({lines[1]})"
        else:
            body = "\n".join(lines)

        return Report(
            title="Mission Completed",
            body=body,
            format=ctx.format,
            metadata={
                "mission_id": mission.mission_id,
                "status": mission.status.value,
                "evidence_count": len(evidence_list),
            },
        )

    def _template_mission_failed(
        self,
        mission: Mission,
        evidence_list: list[Evidence],
        ctx: ReportContext,
    ) -> Report:
        lines = [f"❌ Mission Failed: {mission.intent_summary}"]

        if mission.outcome and isinstance(mission.outcome, dict):
            error = mission.outcome.get("error")
            if error:
                lines.append(f"Error: {error}")

        if evidence_list:
            for ev in evidence_list:
                if ev.verdict in (Verdict.NOT_MATCHED, Verdict.ERROR):
                    lines.append(f"  • {ev.worker}.{ev.environment}: {ev.verdict.value}")
                    if ev.errors:
                        for err in ev.errors:
                            lines.append(f"    {err}")

        body = "\n".join(lines) if ctx.tone != ReportTone.CONCISE else lines[0]

        return Report(
            title="Mission Failed",
            body=body,
            format=ctx.format,
            metadata={
                "mission_id": mission.mission_id,
                "status": mission.status.value,
                "evidence_count": len(evidence_list),
            },
        )

    def _template_mission_cancelled(
        self,
        mission: Mission,
        evidence_list: list[Evidence],
        ctx: ReportContext,
    ) -> Report:
        body = f"🚫 Mission Cancelled: {mission.intent_summary}"
        if ctx.tone != ReportTone.CONCISE:
            body += "\nNo changes were made."

        return Report(
            title="Mission Cancelled",
            body=body,
            format=ctx.format,
            metadata={"mission_id": mission.mission_id, "status": mission.status.value},
        )

    def _template_plan_refused(
        self,
        objective: str,
        refusal_reason: str,
        provider_id: str | None,
        ctx: ReportContext,
    ) -> Report:
        lines = [f"🤔 Could not plan: {objective}", f"Reason: {refusal_reason}"]
        if provider_id:
            lines.append(f"Provider: {provider_id}")

        body = "\n".join(lines) if ctx.tone != ReportTone.CONCISE else lines[0]

        return Report(
            title="Plan Refused",
            body=body,
            format=ctx.format,
            metadata={"objective": objective, "refusal_reason": refusal_reason, "provider_id": provider_id},
        )

    def _template_plan_rejected(
        self,
        objective: str,
        rejection_reasons: tuple[str, ...],
        provider_id: str | None,
        ctx: ReportContext,
    ) -> Report:
        lines = [f"📋 Plan rejected for: {objective}"]
        for reason in rejection_reasons:
            lines.append(f"  • {reason}")
        if provider_id:
            lines.append(f"Provider: {provider_id}")

        body = "\n".join(lines) if ctx.tone != ReportTone.CONCISE else lines[0]

        return Report(
            title="Plan Rejected",
            body=body,
            format=ctx.format,
            metadata={
                "objective": objective,
                "rejection_reasons": list(rejection_reasons),
                "provider_id": provider_id,
            },
        )

    def _template_step_completed(
        self,
        step_id: str,
        capability: str,
        output: Any,
        evidence: Evidence | None,
        ctx: ReportContext,
    ) -> Report:
        lines = [f"✅ Step completed: {step_id} ({capability})"]

        if ctx.tone == ReportTone.DETAILED and output:
            if isinstance(output, dict):
                for k, v in output.items():
                    lines.append(f"  {k}: {v}")
            else:
                lines.append(f"  Output: {output}")

        if evidence and ctx.include_evidence_details:
            lines.append(f"  Verification: {evidence.verdict.value}")

        body = "\n".join(lines) if ctx.tone != ReportTone.CONCISE else lines[0]

        return Report(
            title="Step Completed",
            body=body,
            format=ctx.format,
            metadata={"step_id": step_id, "capability": capability, "evidence_id": evidence.evidence_id if evidence else None},
        )

    def _template_step_failed(
        self,
        step_id: str,
        capability: str,
        error: str | None,
        evidence: Evidence | None,
        ctx: ReportContext,
    ) -> Report:
        lines = [f"❌ Step failed: {step_id} ({capability})"]
        if error:
            lines.append(f"Error: {error}")

        if evidence and evidence.errors:
            for err in evidence.errors:
                lines.append(f"  Verification error: {err}")

        body = "\n".join(lines) if ctx.tone != ReportTone.CONCISE else lines[0]

        return Report(
            title="Step Failed",
            body=body,
            format=ctx.format,
            metadata={"step_id": step_id, "capability": capability, "error": error},
        )

    def _template_approval_required(
        self,
        mission_title: str,
        capability: str,
        payload: dict[str, Any],
        consequence: str,
        ctx: ReportContext,
    ) -> Report:
        lines = [
            "🔐 Approval Required",
            f"Mission: {mission_title}",
            f"Action: {capability}",
        ]

        if payload:
            lines.append("Parameters:")
            for k, v in payload.items():
                lines.append(f"  {k}: {v}")

        lines.append(f"\n{consequence}")
        lines.append("Approve? (Yes/No)")

        body = "\n".join(lines)

        return Report(
            title="Approval Required",
            body=body,
            format=ctx.format,
            metadata={"capability": capability, "payload": payload, "consequence": consequence},
        )

    def _template_clarification_needed(
        self,
        question: str,
        options: tuple[str, ...],
        ctx: ReportContext,
    ) -> Report:
        lines = [f"❓ {question}"]
        if options:
            lines.append("Options:")
            for i, opt in enumerate(options, 1):
                lines.append(f"  {i}. {opt}")

        body = "\n".join(lines)

        return Report(
            title="Clarification Needed",
            body=body,
            format=ctx.format,
            metadata={"question": question, "options": list(options)},
        )