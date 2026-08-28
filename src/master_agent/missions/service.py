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
    KNOWN,
    UNSETTLED_INTERPRETATION,
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
    #: The founder's selection and what the mission actually ran under.
    #: Carried from the Planner rather than recomputed -- the component
    #: that made the decision is the one that reports it.
    selected_mode: str = ""
    effective_mode: str = ""
    mode_reason: str = ""

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

    def start(
        self, objective: Intent | str, *, objective_id: str | None = None
    ) -> MissionOutcome:
        """Plan it, check it, submit it.

        Returns rather than raises for every expected failure: a founder
        typing an impossible objective at 22:13 must get a sentence, not a
        traceback.

        ## Why this takes an `Intent` as well as a string

        ADR-0024 Decision 1 makes this the canonical admission boundary:
        the Planner may only be reached through here, and only with an
        Intent that is already sufficiently understood. The production
        path therefore resolves intent *before* calling — the founder
        surface asks `IntentLayer` first, and a clarification-required
        result never reaches this method at all, which is what ADR-0024
        §10 requires ("MissionService = 0, Planner = 0").

        Given an `Intent`, this method **does not reinterpret it**. It
        does not re-parse the founder's language, does not touch `goal`,
        `actor` or `beneficiary`, and invents no constraints. Whatever
        the Intent Layer decided the founder meant survives this boundary
        unchanged (ADR-0024 Decision 12).

        The string form is retained for callers that hand over raw text
        and have no Intent Layer of their own — the console path and a
        large body of existing tests. It parses through the *same*
        `intent_layer` instance, so there is one Intent Layer in the
        system and one place agency is derived, never two.
        """
        # An already-resolved Intent skips understanding entirely: it was
        # understood before it got here, and re-deriving meaning from
        # `goal` would be the "second parser" ADR-0024 Decision 13 forbids.
        if isinstance(objective, Intent):
            self._counter += 1
            task_id = f"plan-{self._counter}"
            # The understanding phase happened immediately upstream, in the
            # Intent Layer. The event is published here anyway so the
            # founder's phase timeline stays complete -- it describes the
            # mission's lifecycle, not which class did the work, and a
            # missing phase would read to the founder as a skipped step.
            description = str(objective.context.get("raw_input") or objective.goal)
            self._publish_phase(
                EventType.MISSION_UNDERSTANDING_STARTED, task_id, objective_id, description
            )
            return self._admit(objective, task_id=task_id, objective_id=objective_id)

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

        return self._admit(intent, task_id=task_id, objective_id=objective_id, description=text)

    # ---- admission ---------------------------------------------------

    def _admit(
        self, intent: Intent, *, task_id: str, objective_id: str | None,
        description: str | None = None,
    ) -> MissionOutcome:
        """Everything downstream of understanding: plan, translate, submit.

        One body, reached by both forms of `start()`, so an Intent handed
        in by the founder surface and an Intent parsed here from raw text
        follow byte-for-byte the same path to the Planner. Two bodies
        would be two admission policies waiting to diverge.

        `description` is the founder's own wording, carried for history,
        reports and Memory -- provenance, not contract. When the caller
        supplies an Intent it is recovered from `context["raw_input"]`,
        falling back to `goal`. Nothing downstream of this line derives
        *meaning* from it (ADR-0024 §7).
        """
        if description is None:
            description = str(intent.context.get("raw_input") or intent.goal)
        text = description

        # Every admitted mission carries the founder's requirements.
        #
        # A compound natural objective -- the AI Planner's whole
        # workload -- derives them through the reasoning door, which
        # `parse()` may never touch: parsing is structural and reaching
        # a provider there would put a model on every keystroke path.
        # So the compound half is derived HERE, once per mission, at the
        # boundary ADR-0024 already makes the only way to the Planner.
        #
        # Without it the failed research acceptance planned ten steps
        # with an empty requirement list and `covers=[]` on every one,
        # and outcome conformance over an empty requirement set can only
        # answer UNKNOWN.
        if not getattr(intent, "requirements", ()) and self.intent_layer is not None:
            try:
                intent.requirements = self.intent_layer.requirements_for(
                    intent, raw=text
                )
            except Exception:  # noqa: BLE001 -- absent semantics, not a crash
                intent.requirements = ()

        # What decision, if any, this mission actually faces.
        #
        # Framed HERE because this is where the founder's requirements
        # are complete and nothing has yet been planned -- a frame
        # written after the evidence arrives is a rationalisation of
        # whatever turned up, and its criteria quietly become the shape
        # of the data instead of the shape of the request.
        #
        # `None` for a typed capability with settled arguments, which is
        # most missions. Deliberation is a cost the founder pays in
        # latency, and a folder is not a decision.
        try:
            from master_agent.brain import deliberation as _deliberation

            frame = _deliberation.frame_for(
                objective=text,
                requirements=getattr(intent, "requirements", ()) or (),
                capability=str(getattr(intent, "capability", "") or ""),
            )
            if frame is not None:
                # Reviewable decision metadata, never a reasoning
                # transcript: what is being decided and what would
                # settle it (ADR-0027).
                intent.context["decision_frame"] = frame.as_dict()
        except Exception:  # noqa: BLE001 -- an unframed mission still runs
            pass

        # An interpretation nobody settled may not become work.
        #
        # This was written as a comment on `SemanticRequirement`
        # -- "UNCERTAIN may never reach execution" -- and enforced
        # nowhere. Conformance refused to REPORT satisfaction for an
        # uncertain requirement, which closes the back door and leaves
        # the front one open: a plan carrying one would still have run,
        # and the founder would have been told about real work done on a
        # reading the system did not stand behind.
        #
        # It belongs here and only here. ADR-0024 Decision 1 already
        # makes this the single admission boundary to the Planner, so
        # the check has one owner rather than becoming a second policy
        # that drifts from the first.
        unsettled = [
            requirement
            for requirement in (getattr(intent, "requirements", None) or ())
            if getattr(requirement, "required", True)
            and str(getattr(requirement, "interpretation", KNOWN)) != KNOWN
        ]
        if unsettled:
            unclear = "; ".join(
                str(getattr(r, "founder_evidence", "") or getattr(r, "description", ""))
                for r in unsettled
            )
            return MissionOutcome(
                status=REFUSED,
                refusal=PlanRefusal(
                    code=UNSETTLED_INTERPRETATION,
                    reason=(
                        "I am not confident I understood part of this, so I "
                        "have not acted on it."
                    ),
                    detail=(
                        f"Unsettled: {unclear}. Asking is the correct outcome "
                        "here -- acting on a reading nobody confirmed is how a "
                        "mission gets verified against its own mistake."
                    ),
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
                selected_mode=getattr(outcome, "selected_mode", ""),
                effective_mode=getattr(outcome, "effective_mode", ""),
                mode_reason=getattr(outcome, "mode_reason", ""),
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
                # The routing decision travels with the plan it explains.
                # The Planner already returns all three on `PlanOutcome`;
                # they simply stopped at the process boundary.
                selected_mode=getattr(outcome, "selected_mode", "") or "",
                effective_mode=getattr(outcome, "effective_mode", "") or "",
                mode_reason=getattr(outcome, "mode_reason", "") or "",
                attempts=getattr(outcome, "attempts", ()) or (),
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
            selected_mode=getattr(outcome, "selected_mode", ""),
            effective_mode=getattr(outcome, "effective_mode", ""),
            mode_reason=getattr(outcome, "mode_reason", ""),
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
