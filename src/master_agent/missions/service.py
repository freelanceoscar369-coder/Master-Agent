"""The one path from a founder objective to running work (MB037).

```
objective text -> Planner -> MissionPlan -> Objective -> Mission Control
```

and then nothing, because from that point the system already worked: the
Dispatcher orders by dependency, the Runtime executes and verifies, the
Verifier produces Evidence, Memory subscribes to the outcome. This class
is the first four arrows and not one step further.

## What it deliberately does not do

- **It does not execute.** It submits. The Runtime pulls.
- **It does not choose a provider.** The Planner asks the Broker for
  `reasoning`; the Broker answers. This module names no provider.
- **It does not verify.** It never sees a verdict.
- **It does not re-plan.** A failed mission stays failed until a founder
  says otherwise. Adaptive re-planning is a later brief with its own
  safety argument, and quietly adding it here -- at the exact moment the
  system has demonstrated it got something wrong -- is how a planner
  starts making decisions nobody approved.

## The one thing it does write to Memory

A *refused* plan produces **no Mission Control event at all**, because no
objective was ever submitted. So the failure that memory would otherwise
never learn about is the one this module records: the plan that did not
happen. Every other lesson still comes from MB034's existing
subscriptions, which is why this class has no other memory call.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from master_agent.memory.memory_models import FAILURE_LIBRARY, HIGH, MISSION
from master_agent.mission_control.events import EventType
from master_agent.missions.history import PlanHistory
from master_agent.missions.translation import PlanIncomplete, objective_from_plan
from master_agent.planner.plan import (
    BROKER_REFUSED,
    NO_CAPABILITIES,
    NOT_JSON,
    PROVIDER_FAILED,
    UNVERIFIED,
    Intent,
    MissionPlan,
    PlanOutcome,
    PlanRefusal,
    Step,
)
from master_agent.brain import IntentLayer, Reporter

#: Why a mission did not start. `refused` is the Planner's (or the
#: Broker's) answer; `rejected` is this layer refusing a plan that came
#: back structurally unusable.
REFUSED = "refused"
REJECTED = "rejected"
ACCEPTED = "accepted"


@dataclass(frozen=True)
class MissionOutcome:
    """What happened when the founder asked for something."""

    status: str = REFUSED
    objective_id: str | None = None
    plan: Any = None
    objective: Any = None
    record: Any = None
    #: The Planner's `PlanRefusal`, when there was one.
    refusal: Any = None
    #: Deliverable 4's rejection reasons, when the plan was incomplete.
    reasons: tuple[str, ...] = ()
    provider_id: str | None = None
    entry_id: int | None = None

    @property
    def accepted(self) -> bool:
        return self.status == ACCEPTED

    @property
    def steps(self) -> int:
        return len(self.plan.steps) if self.plan is not None else 0

    @property
    def reason(self) -> str:
        """One sentence for a founder, whichever way this went."""
        if self.status == ACCEPTED:
            return ""
        if self.refusal is not None:
            return self.refusal.reason
        if self.reasons:
            return "the plan was not executable: " + "; ".join(self.reasons)
        return "no plan"

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "objective_id": self.objective_id,
            "steps": self.steps,
            "provider_id": self.provider_id,
            "entry_id": self.entry_id,
            "reason": self.reason,
            "reasons": list(self.reasons),
        }


@dataclass
class MissionService:
    """Founder objective in, submitted mission out.

    Every collaborator is handed in and used through its published
    surface. `history` and `memory` are optional -- a system with neither
    still plans and still runs, and reports honestly that it is not
    keeping a record.
    """

    planner: Any
    mission_control: Any
    intent_layer: IntentLayer
    reporter: Reporter | None = None
    history: PlanHistory | None = None
    memory: Any = None
    _counter: int = field(default=0, repr=False)

    def start(self, objective: str, *, objective_id: str | None = None) -> MissionOutcome:
        """Plan it, check it, submit it.

        Returns rather than raises for every expected failure: a founder
        typing an impossible objective at 22:13 must get a sentence, not a
        traceback.
        """
        text = objective.strip()
        self._counter += 1
        task_id = f"plan-{self._counter}"

        # Task 2.5: the two phases that happen before an Objective (and
        # therefore any Task) exists to attach evidence to. Published
        # through the same bus everything downstream already reports
        # through, not a second observability path.
        self._publish_phase(EventType.MISSION_UNDERSTANDING_STARTED, task_id, objective_id, text)

        # Parse raw input through Intent Layer
        intent_result = self.intent_layer.parse(text)
        if intent_result.needs_clarification:
            # Report clarification needed and return refused outcome
            if self.reporter:
                report = self.reporter.report_clarification_needed(
                    intent_result.clarification.question,
                    intent_result.clarification.options,
                )
                # For now, return a refused outcome with the clarification detail
                return MissionOutcome(
                    status=REFUSED,
                    refusal=PlanRefusal(
                        code="CLARIFICATION_REQUIRED",
                        reason=report.body,
                        detail=intent_result.clarification.question,
                    ),
                )
            return MissionOutcome(
                status=REFUSED,
                refusal=PlanRefusal(
                    code="CLARIFICATION_REQUIRED",
                    reason="Clarification required but no reporter available",
                    detail=intent_result.clarification.question,
                ),
            )

        # Use the parsed Intent from Intent Layer
        intent = intent_result.intent
        if intent is None:
            return MissionOutcome(
                status=REFUSED,
                refusal=PlanRefusal(
                    code="NO_INTENT",
                    reason="Intent Layer produced no intent",
                    detail="",
                ),
            )

        self._publish_phase(EventType.MISSION_PLANNING_STARTED, task_id, objective_id, text)
        outcome = self.planner.plan(
            intent, task_id=task_id, objective_id=objective_id
        )

        if not outcome.planned:
            self._remember_refusal(text, outcome)
            if self.reporter:
                report = self.reporter.report_plan_result(
                    objective=text,
                    planned=False,
                    refusal_reason=outcome.refusal.reason if outcome.refusal else "Unknown",
                    provider_id=outcome.provider_id,
                )
                # Could log or return the report
            return MissionOutcome(
                status=REFUSED,
                refusal=outcome.refusal,
                provider_id=outcome.provider_id,
                entry_id=outcome.entry_id,
            )

        try:
            mission = objective_from_plan(outcome.plan, description=text)
        except PlanIncomplete as incomplete:
            self._remember_rejection(text, incomplete.reasons)
            if self.reporter:
                report = self.reporter.report_plan_result(
                    objective=text,
                    planned=False,
                    rejection_reasons=incomplete.reasons,
                    provider_id=outcome.provider_id,
                )
            return MissionOutcome(
                status=REJECTED,
                plan=outcome.plan,
                reasons=incomplete.reasons,
                provider_id=outcome.provider_id,
                entry_id=outcome.entry_id,
            )

        # Mission Control validates again on submission (duplicate ids,
        # unknown dependencies, cycles). Letting it is the point: it owns
        # the work, so it gets the last word on whether the work is
        # admissible, and this layer does not pre-empt a check it does not
        # own.
        submitted = self.mission_control.submit_objective(mission)

        record = None
        if self.history is not None:
            record = self.history.record_plan(
                plan_id=submitted.objective_id,
                objective=text,
                plan=outcome.plan,
                planned_by=outcome.provider_id,
                entry_id=outcome.entry_id,
            )

        if self.reporter:
            report = self.reporter.report_plan_result(
                objective=text,
                planned=True,
                provider_id=outcome.provider_id,
            )

        # Return accepted outcome; mission outcome will be reported via events
        return MissionOutcome(
            status=ACCEPTED,
            objective_id=submitted.objective_id,
            plan=outcome.plan,
            objective=submitted,
            record=record,
            provider_id=outcome.provider_id,
            entry_id=outcome.entry_id,
        )

    # ---- Task 2.5 phase reporting ------------------------------------

    def _publish_phase(
        self, event_type: Any, task_id: str, objective_id: str | None, objective_text: str
    ) -> None:
        """Report a phase that has no Task/Objective yet to attach evidence
        to. `mission_control` is the same collaborator every other write in
        this class already has; a caller that hands in one without a `bus`
        (a test double, typically) is not reporting phases, honestly."""
        bus = getattr(self.mission_control, "bus", None)
        if bus is None:
            return
        from master_agent.mission_control.events import Event

        bus.publish(
            Event(
                event_type=event_type,
                source="mission_service",
                task_id=task_id,
                objective_id=objective_id,
                payload={"objective": objective_text},
            )
        )

    # ---- the lesson nobody else can record -------------------------------

    def _remember_refusal(self, objective: str, outcome: Any) -> None:
        refusal = outcome.refusal
        if refusal is None:
            return
        self._write(
            title=f"Could not plan: {objective}",
            body=(
                f"{refusal.reason}\n\n{refusal.detail}".strip()
                + f"\n\nRefusal code: {refusal.code}."
            ),
            tags=("planning", "refused", refusal.code),
        )

    def _remember_rejection(self, objective: str, reasons: tuple[str, ...]) -> None:
        self._write(
            title=f"Rejected an unusable plan: {objective}",
            body=(
                "A plan was produced but could not be executed as written:\n"
                + "\n".join(f"- {reason}" for reason in reasons)
                + "\n\nNothing was submitted and nothing was repaired."
            ),
            tags=("planning", "rejected"),
        )

    def _write(self, title: str, body: str, tags: tuple[str, ...]) -> None:
        if self.memory is None:
            return
        try:
            self.memory.write(
                category=FAILURE_LIBRARY,
                title=title,
                full_text=body,
                tags=tags,
                importance=HIGH,
                source=MISSION,
            )
        except Exception:  # noqa: BLE001 - a memory that fails must not stop a founder
            # MB034's posture: memory is a record of the work, never a
            # precondition for it. A history that cannot be written is a
            # degraded system, not a stopped one.
            return
