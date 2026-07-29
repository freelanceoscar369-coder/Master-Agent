"""MissionControl — the facade that ties the coordination layer together.

Mission Brief 023's seven acceptance criteria are the seven things this
class can do: register Executives, register Capabilities, dispatch Tasks,
receive Events, maintain the Audit Stream, maintain the Self-Development
Queue, and expose Founder State — all without requiring modifications to
existing Executives (see adapters.py).

It performs no work. There is no Environment access, no model call, no
filesystem call, and no live plugin reference anywhere in this package;
`tests/test_mission_control_architecture.py` enforces that mechanically
rather than trusting this docstring.
"""
from __future__ import annotations

from typing import Any

from master_agent.mission_control.audit import AuditStream
from master_agent.mission_control.capabilities import CapabilityDescriptor, CapabilityRegistry
from master_agent.mission_control.dispatcher import TaskDispatcher
from master_agent.mission_control.events import (
    MISSION_CONTROL_SOURCE,
    Event,
    EventBus,
    EventType,
)
from master_agent.mission_control.executives import (
    ExecutiveHealth,
    ExecutiveRecord,
    ExecutiveRegistry,
)
from master_agent.mission_control.founder_state import FounderState, estimate_eta_seconds
from master_agent.mission_control.knowledge_queue import (
    KnowledgeAcquisitionQueue,
    KnowledgeRequest,
)
from master_agent.mission_control.lifecycle import WorkerState
from master_agent.mission_control.reporting import ExecutiveReporter
from master_agent.mission_control.self_development import (
    SelfDevelopmentItem,
    SelfDevelopmentQueue,
    SelfDevelopmentState,
    SelfDevelopmentType,
)
from master_agent.mission_control.tasks import Objective, Task, TaskState


class MissionControl:
    def __init__(self) -> None:
        self.bus = EventBus()
        self.audit = AuditStream(self.bus)
        self.capabilities = CapabilityRegistry()
        self.executives = ExecutiveRegistry()
        self.dispatcher = TaskDispatcher(self.capabilities, self.executives, self.bus)
        self.self_development = SelfDevelopmentQueue()
        self.knowledge = KnowledgeAcquisitionQueue()
        self._current_objective_id: str | None = None

    # ---- Executives and Capabilities --------------------------------

    def register_executive(
        self,
        executive_id: str,
        version: str,
        capabilities: list[CapabilityDescriptor] | None = None,
        dependencies: list[str] | None = None,
        health: ExecutiveHealth = ExecutiveHealth.UNKNOWN,
    ) -> str:
        descriptors = capabilities or []
        record = ExecutiveRecord(
            executive_id=executive_id,
            version=version,
            capabilities=[descriptor.qualified_name for descriptor in descriptors],
            health=health,
            dependencies=dependencies or [],
        )
        self.executives.register(record)

        for descriptor in descriptors:
            self.capabilities.register(descriptor)
            self._publish(
                EventType.CAPABILITY_REGISTERED,
                capability=descriptor.qualified_name,
                payload={"executive_id": executive_id, "risk_tier": descriptor.risk_tier},
            )

        self._publish(
            EventType.EXECUTIVE_REGISTERED,
            payload={
                "executive_id": executive_id,
                "version": version,
                "capability_count": len(descriptors),
            },
        )
        return executive_id

    def mark_executive_ready(self, executive_id: str) -> ExecutiveRecord:
        """Walks the real lifecycle rather than assigning READY directly —
        the transition table is the source of truth for how an Executive
        can reach a state."""
        for state in (WorkerState.INITIALIZED, WorkerState.READY):
            self.transition_executive(executive_id, state)
        return self.executives.get(executive_id)

    def transition_executive(self, executive_id: str, new_state: WorkerState) -> ExecutiveRecord:
        record = self.executives.get(executive_id)
        previous = record.state
        self.executives.transition(executive_id, new_state)
        self._publish(
            EventType.WORKER_STATE_CHANGED,
            payload={
                "executive_id": executive_id,
                "from": previous.value,
                "to": new_state.value,
            },
        )
        return record

    def set_executive_health(
        self, executive_id: str, health: ExecutiveHealth
    ) -> ExecutiveRecord:
        record = self.executives.get(executive_id)
        previous = record.health
        self.executives.set_health(executive_id, health)
        self._publish(
            EventType.EXECUTIVE_HEALTH_CHANGED,
            payload={
                "executive_id": executive_id,
                "from": previous.value,
                "to": health.value,
            },
        )
        return record

    def reporter_for(self, executive_id: str) -> ExecutiveReporter:
        """The one reporting surface an Executive gets — see
        reporting.py. Deliberately does not require the Executive to be
        registered first, so a Worker can report a failure that happened
        during its own registration."""
        return ExecutiveReporter(executive_id, self.bus)

    # ---- Objectives and Tasks ---------------------------------------

    def submit_objective(self, objective: Objective) -> Objective:
        self.dispatcher.submit(objective)
        if self._current_objective_id is None:
            self._current_objective_id = objective.objective_id
        return objective

    def dispatch_ready(self, objective_id: str | None = None) -> list[Task]:
        return self.dispatcher.dispatch_ready(self._resolve_objective_id(objective_id))

    def ready_tasks(self, objective_id: str | None = None) -> list[Task]:
        return self.dispatcher.ready_tasks(self._resolve_objective_id(objective_id))

    def task_started(self, task_id: str, objective_id: str | None = None) -> Task:
        return self.dispatcher.task_started(self._resolve_objective_id(objective_id), task_id)

    def task_completed(
        self,
        task_id: str,
        result: object = None,
        evidence_id: str | None = None,
        objective_id: str | None = None,
    ) -> Task:
        return self.dispatcher.task_completed(
            self._resolve_objective_id(objective_id), task_id, result, evidence_id
        )

    def task_failed(self, task_id: str, error: str, objective_id: str | None = None) -> Task:
        return self.dispatcher.task_failed(self._resolve_objective_id(objective_id), task_id, error)

    # ---- Verification reporting -------------------------------------

    def verification_started(self, task_id: str, objective_id: str | None = None) -> Event:
        return self._publish(
            EventType.VERIFICATION_STARTED,
            objective_id=self._resolve_objective_id(objective_id, required=False),
            task_id=task_id,
        )

    def verification_completed(
        self,
        task_id: str,
        verdict: str,
        evidence_id: str,
        objective_id: str | None = None,
    ) -> Event:
        """Records a Verification outcome. `verdict` and `evidence_id` come
        from Mission Brief 022's Evidence, reused unchanged — Mission
        Control never defines a second evidence type and never recomputes a
        verdict of its own."""
        return self._publish(
            EventType.VERIFICATION_COMPLETED,
            objective_id=self._resolve_objective_id(objective_id, required=False),
            task_id=task_id,
            payload={"verdict": verdict, "evidence_id": evidence_id},
        )

    # ---- Self-Development Queue -------------------------------------

    def propose_self_development(
        self,
        item_type: SelfDevelopmentType,
        title: str,
        detail: str = "",
        priority: int = 100,
    ) -> SelfDevelopmentItem:
        item = self.self_development.add(
            SelfDevelopmentItem(
                item_type=item_type, title=title, detail=detail, priority=priority
            )
        )
        self._publish(
            EventType.SELF_DEVELOPMENT_STARTED,
            payload={"item_id": item.item_id, "type": item_type.value, "title": title},
        )
        return item

    def complete_self_development(self, item_id: str) -> SelfDevelopmentItem:
        item = self.self_development.transition(item_id, SelfDevelopmentState.DONE)
        self._publish(
            EventType.SELF_DEVELOPMENT_COMPLETED,
            payload={"item_id": item.item_id, "title": item.title},
        )
        return item

    # ---- Knowledge Acquisition Queue --------------------------------

    def request_knowledge(self, need: str, detail: str = "") -> KnowledgeRequest:
        request = self.knowledge.add(KnowledgeRequest(need=need, detail=detail))
        self._publish(
            EventType.KNOWLEDGE_REQUESTED,
            payload={"request_id": request.request_id, "need": need},
        )
        return request

    def advance_knowledge(
        self,
        request_id: str,
        human_approved: bool = False,
        approved_by: str | None = None,
    ) -> KnowledgeRequest:
        """Advances one pipeline stage. Crossing the Promotion Review gate
        without `human_approved=True` raises — ADR-0012 enforced in code,
        not convention. The refusal is itself published, so an attempted
        auto-promotion is auditable rather than silent."""
        from master_agent.mission_control.knowledge_queue import (
            PROMOTION_GATE_FROM,
            PromotionRequiresHumanApproval,
        )

        request = self.knowledge.get(request_id)
        at_gate = request.stage is PROMOTION_GATE_FROM

        try:
            updated = self.knowledge.advance(
                request_id, human_approved=human_approved, approved_by=approved_by
            )
        except PromotionRequiresHumanApproval as exc:
            self._publish(
                EventType.APPROVAL_REQUIRED,
                payload={"request_id": request_id, "gate": "promotion_review"},
                error=str(exc),
            )
            raise

        self._publish(
            EventType.KNOWLEDGE_STAGE_ADVANCED,
            payload={"request_id": request_id, "stage": updated.stage.value},
        )
        if at_gate:
            self._publish(
                EventType.KNOWLEDGE_ACQUIRED,
                payload={
                    "request_id": request_id,
                    "need": updated.need,
                    "promoted_by": updated.promoted_by,
                },
            )
        return updated

    def reject_knowledge(self, request_id: str, reason: str) -> KnowledgeRequest:
        request = self.knowledge.reject(request_id, reason)
        self._publish(
            EventType.KNOWLEDGE_REJECTED,
            payload={"request_id": request_id},
            error=reason,
        )
        return request

    # ---- Founder State ----------------------------------------------

    def founder_state(self, objective_id: str | None = None) -> FounderState:
        """One honest snapshot — see founder_state.py. Returns an empty but
        well-formed snapshot when nothing is in flight, rather than None,
        so a consumer never has to special-case "no objective yet"."""
        resolved = self._resolve_objective_id(objective_id, required=False)
        if resolved is None:
            return FounderState(
                current_objective=None,
                current_objective_id=None,
                current_mission=None,
                current_executive=None,
                current_capability=None,
                progress=0.0,
                waiting_approval=self._waiting_approval(),
                learning_progress=self._learning_progress(),
            )

        objective = self.dispatcher.objective(resolved)
        active = self._active_task(objective)
        durations = [
            task.duration_seconds
            for task in objective.tasks
            if task.state is TaskState.COMPLETED and task.duration_seconds is not None
        ]
        remaining = sum(
            1 for task in objective.tasks if task.state not in
            {TaskState.COMPLETED, TaskState.FAILED}
        )

        return FounderState(
            current_objective=objective.description,
            current_objective_id=objective.objective_id,
            current_mission=objective.description,
            current_executive=active.assigned_executive if active else None,
            current_capability=active.capability if active else None,
            progress=objective.progress,
            evidence=[task.evidence_id for task in objective.tasks if task.evidence_id],
            errors=[error for task in objective.tasks for error in task.errors],
            eta_seconds=estimate_eta_seconds(durations, remaining),
            waiting_approval=self._waiting_approval(),
            learning_progress=self._learning_progress(),
        )

    def _active_task(self, objective: Objective) -> Task | None:
        for state in (TaskState.RUNNING, TaskState.DISPATCHED, TaskState.READY):
            for task in objective.tasks:
                if task.state is state:
                    return task
        return None

    def _waiting_approval(self) -> list[dict[str, Any]]:
        return [
            {
                "kind": "knowledge_promotion",
                "request_id": request.request_id,
                "need": request.need,
            }
            for request in self.knowledge.awaiting_promotion()
        ]

    def _learning_progress(self) -> dict[str, Any]:
        return {
            "self_development_open": len(self.self_development.pending()),
            "self_development_total": len(self.self_development),
            "knowledge_requests_total": len(self.knowledge),
            "knowledge_awaiting_promotion": len(self.knowledge.awaiting_promotion()),
        }

    # ---- internals ---------------------------------------------------

    def _resolve_objective_id(
        self, objective_id: str | None, required: bool = True
    ) -> str | None:
        resolved = objective_id or self._current_objective_id
        if resolved is None and required:
            raise ValueError("no objective specified and no current objective is set")
        return resolved

    def _publish(self, event_type: EventType, **kwargs: Any) -> Event:
        event = Event(event_type=event_type, source=MISSION_CONTROL_SOURCE, **kwargs)
        self.bus.publish(event)
        return event
