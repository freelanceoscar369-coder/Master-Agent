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

from master_agent.mission_control.approvals import (
    ApprovalQueue,
    ApprovalState,
    PendingApproval,
)
from master_agent.mission_control.audit import AuditStream
from master_agent.mission_control.capabilities import CapabilityDescriptor, CapabilityRegistry
from master_agent.mission_control.completion import CompletionQueue, PendingCompletion
from master_agent.mission_control.dispatcher import TaskDispatcher, UnknownObjective
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
        self.approvals = ApprovalQueue()
        self.self_development = SelfDevelopmentQueue()
        self.knowledge = KnowledgeAcquisitionQueue()
        # Task 2.5: a verified objective is not yet a founder-facing
        # completed one (see completion.py). Every objective that finishes
        # its tasks without failure gets a completion question opened
        # automatically -- a subscriber on the same bus everything else
        # here already reports through, not a special case in the
        # dispatcher that published OBJECTIVE_COMPLETED.
        self.completions = CompletionQueue()
        self.bus.subscribe(self._open_completion_question, EventType.OBJECTIVE_COMPLETED)
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
                # Carried so a system rebuilt by event replay (MB025
                # deliverable #9) knows an Executive was healthy. Without
                # it a replayed Executive comes back UNKNOWN, is never
                # considered available, and the whole fallback path is
                # inert -- found by MB025's replay tests. Additive data in
                # an existing payload; the Event schema is unchanged.
                "health": health.value,
                "dependencies": list(dependencies or []),
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

    def restore_objective(self, objective: Objective) -> Objective:
        """Re-admit an objective persisted by an earlier process, without
        republishing its creation events.

        The facade half of Mission Brief 025's additive restore contract
        (ADR-0015 Decision 3, *Proposed*). It exists because `submit_objective()`
        publishes -- correct for new work, wrong for work being restored --
        and because a restored system must also know which objective is
        current, or `founder_state()` would report an empty snapshot after
        a successful recovery.

        Additive only: no existing method changes, nothing is removed, and
        validation and readiness recomputation are identical to
        `submit_objective()`.
        """
        self.dispatcher.restore_objective(objective)
        if self._current_objective_id is None:
            self._current_objective_id = objective.objective_id
        return objective

    def dispatch_ready(
        self, objective_id: str | None = None, limit: int | None = None
    ) -> list[Task]:
        """`limit` caps how many tasks are actually committed to an
        Executive. Passed straight through: capacity is the Runtime's to
        know and dispatch is the dispatcher's to do."""
        return self.dispatcher.dispatch_ready(
            self._resolve_objective_id(objective_id), limit=limit
        )

    def ready_tasks(self, objective_id: str | None = None) -> list[Task]:
        return self.dispatcher.ready_tasks(self._resolve_objective_id(objective_id))

    def task_started(
        self, task_id: str, objective_id: str | None = None,
        input_provenance: list[dict[str, Any]] | None = None,
    ) -> Task:
        return self.dispatcher.task_started(
            self._resolve_objective_id(objective_id), task_id,
            input_provenance=input_provenance,
        )

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
        resolved = self._resolve_objective_id(objective_id, required=False)
        return self._publish(
            EventType.VERIFICATION_STARTED,
            objective_id=resolved,
            task_id=task_id,
            capability=self._capability_of(resolved, task_id),
        )

    def verification_completed(
        self,
        task_id: str,
        verdict: str,
        evidence_id: str,
        objective_id: str | None = None,
        evidence: dict[str, Any] | None = None,
    ) -> Event:
        """Records a Verification outcome. `verdict` and `evidence_id` come
        from Mission Brief 022's Evidence, reused unchanged — Mission
        Control never defines a second evidence type and never recomputes a
        verdict of its own.

        `evidence` is the canonical JSON projection of that same Evidence
        (`Evidence.as_dict()`), carried whole. It is additive: callers that
        pass only a verdict and an id keep working, and their events simply
        have no `evidence` key.

        Carrying it matters because the pair that used to travel alone is
        a correlation key and a result code. Neither can answer what was
        observed, when, by which Environment verifier, against which
        checks, or which of them failed — so after a restart none of those
        questions had an answer. Mission Control does not read this object,
        does not validate it and does not modify it; it transports exactly
        what Verification produced.
        """
        resolved = self._resolve_objective_id(objective_id, required=False)

        # Mission State is Shared Infrastructure's own responsibility, and a
        # dependent step binding to this task's output needs the record
        # rather than its id -- an id cannot say whether the reported value
        # and the observed value agree. Stored exactly as Verification
        # produced it: not recomputed, not reinterpreted, verdict untouched.
        if evidence is not None and resolved:
            try:
                task = self.dispatcher.objective(resolved).task(task_id)
            except Exception:  # noqa: BLE001 -- an event for work this
                # Mission Control never planned is ignored in silence, the
                # same way the dispatcher already treats one.
                task = None
            if task is not None:
                task.evidence = dict(evidence)

        payload: dict[str, Any] = {"verdict": verdict, "evidence_id": evidence_id}
        if evidence is not None:
            # Nested, not flattened: `verdict` and `evidence_id` stay at the
            # top level for compatibility and searchability, and the whole
            # canonical record lives under one key.
            payload["evidence"] = evidence
        return self._publish(
            EventType.VERIFICATION_COMPLETED,
            objective_id=resolved,
            task_id=task_id,
            capability=self._capability_of(resolved, task_id),
            payload=payload,
        )

    def _capability_of(self, objective_id: str | None, task_id: str) -> str | None:
        """Stamps the capability onto verification events so an audit entry
        answers "which capability was verified" directly, rather than
        requiring a join back through task_id (MIT-001 Test 5 asks the
        audit stream for the Capability used). Returns None rather than
        raising if the task cannot be resolved — an unattributable
        verification event is still worth recording."""
        if objective_id is None:
            return None
        try:
            return self.dispatcher.objective(objective_id).task(task_id).capability
        except (UnknownObjective, KeyError):
            # objective() raises UnknownObjective; task() raises KeyError.
            return None

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

    # ---- Founder approvals (MB028.1) --------------------------------

    def request_approval(self, approval: PendingApproval) -> tuple[PendingApproval, bool]:
        """Open a question for the founder. Idempotent per task+capability
        (the Runtime re-asks every cycle while a task waits), and the
        event is published only when the question is genuinely new."""
        approval, is_new = self.approvals.request(approval)
        if is_new:
            self._publish(
                EventType.APPROVAL_REQUESTED,
                task_id=approval.task_id,
                objective_id=approval.objective_id,
                capability=approval.capability,
                payload=approval.as_dict(),
            )
            # The founder-facing signal MB023 already defined. Published
            # alongside, so anything already watching for "you are being
            # asked" keeps working unchanged.
            self._publish(
                EventType.APPROVAL_REQUIRED,
                task_id=approval.task_id,
                objective_id=approval.objective_id,
                capability=approval.capability,
                payload=approval.as_dict(),
            )
        return approval, is_new

    def approve(self, approval_id: str, founder: str = "founder", note: str = ""):
        return self._decide_approval(
            self.approvals.approve, approval_id, founder, note, EventType.APPROVAL_GRANTED
        )

    def reject(self, approval_id: str, founder: str = "founder", note: str = ""):
        return self._decide_approval(
            self.approvals.reject, approval_id, founder, note, EventType.APPROVAL_DENIED
        )

    def defer(self, approval_id: str, founder: str = "founder", note: str = ""):
        return self._decide_approval(
            self.approvals.defer, approval_id, founder, note, EventType.APPROVAL_DEFERRED
        )

    def expire_approvals(self, timeout_seconds: float | None) -> list[PendingApproval]:
        expired = self.approvals.expire_due(timeout_seconds)
        for approval in expired:
            self._publish(
                EventType.APPROVAL_EXPIRED,
                task_id=approval.task_id,
                objective_id=approval.objective_id,
                capability=approval.capability,
                payload=approval.as_dict(),
            )
        return expired

    def _decide_approval(self, action, approval_id, founder, note, event_type):
        approval = action(approval_id, founder, note)
        self._publish(
            event_type,
            task_id=approval.task_id,
            objective_id=approval.objective_id,
            capability=approval.capability,
            payload={**approval.as_dict(), "decided_by": founder},
        )
        return approval

    # ---- Founder completion (Task 2.5) -------------------------------

    def _open_completion_question(self, event: Event) -> None:
        """Subscriber body for `OBJECTIVE_COMPLETED` — see completion.py's
        module docstring for why this is a separate question from the
        approvals above, asked automatically rather than by request."""
        objective_id = event.objective_id
        if objective_id is None:
            return
        try:
            description = self.dispatcher.objective(objective_id).description
        except UnknownObjective:
            description = ""
        completion, is_new = self.completions.request(
            PendingCompletion(objective_id=objective_id, objective=description)
        )
        if is_new:
            self._publish(
                EventType.FOUNDER_COMPLETION_REQUESTED,
                objective_id=objective_id,
                payload=completion.as_dict(),
            )

    def confirm_completion(
        self, completion_id: str, founder: str = "founder", note: str = ""
    ) -> PendingCompletion:
        """The one action a founder (via Hyper Agent, later) takes to turn
        a verified objective into a founder-facing completed one. Nothing
        here re-runs, re-verifies, or grants anything — the work already
        finished; this only answers "is that acceptable to close out"."""
        completion = self.completions.confirm(completion_id, founder, note)
        self._publish(
            EventType.FOUNDER_COMPLETION_CONFIRMED,
            objective_id=completion.objective_id,
            payload={**completion.as_dict(), "decided_by": founder},
        )
        return completion

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
                result=None,
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
        pending_completion = self.completions.find_open(objective.objective_id)

        return FounderState(
            current_objective=objective.description,
            current_objective_id=objective.objective_id,
            current_mission=objective.description,
            current_executive=active.assigned_executive if active else None,
            current_capability=active.capability if active else None,
            progress=objective.progress,
            result=self._last_result(objective),
            evidence=[task.evidence_id for task in objective.tasks if task.evidence_id],
            errors=[error for task in objective.tasks for error in task.errors],
            eta_seconds=estimate_eta_seconds(durations, remaining),
            waiting_approval=self._waiting_approval(),
            learning_progress=self._learning_progress(),
            requires_founder_completion=pending_completion is not None,
            completion_id=pending_completion.completion_id if pending_completion else None,
        )

    def _last_result(self, objective: Objective) -> Any:
        """What this objective produced — the answer the plan designated
        if it designated one, otherwise the most recently completed task's
        result, reported as the Executive returned it.

        The last completed task is the right answer for a single-step
        mission and the wrong one for any mission that tidies up after
        itself: a browser workflow ending in `CloseBrowserSession`
        reported the close. So a Step may name the field of its own
        observation that answers the founder's question, and that
        designation is honoured here.

        Two properties keep this reporting rather than judging. The value
        comes from **Evidence** — an independent fresh observation — and
        not from the task's own `result`, so what the founder is told is
        what was verified rather than what the Executive claimed. And a
        designated task with no Evidence yields nothing: absence falls
        back to the ordinary behaviour rather than quietly promoting an
        unverified claim to "the answer".
        """
        completed = [
            task
            for task in objective.tasks
            if task.state is TaskState.COMPLETED and task.ended_at is not None
        ]
        if not completed:
            return None

        designated = self._designated_answer(completed)
        if designated is not None:
            return designated
        return max(completed, key=lambda task: task.ended_at).result

    @staticmethod
    def _designated_answer(completed: list[Task]) -> Any:
        """The value a Step named as the founder's answer, or `None`.

        `get_field` is the codebase's one dot-path walker — the same
        function Verification uses to evaluate `elements.0.text` in a
        check. Imported inside the method rather than at module scope so
        the mission_control *models* keep the independence `Task`'s own
        note describes: this borrows one pure projection function, and no
        verification type enters Mission Control's data.
        """
        from master_agent.verification.evaluator import get_field

        for task in sorted(completed, key=lambda t: t.ended_at):
            path = (getattr(task, "answers_founder", "") or "").strip()
            if not path:
                continue
            observation = (task.evidence or {}).get("observation")
            if not isinstance(observation, dict):
                # Designated, but nothing independently observed it. There
                # is no verified answer to give, so none is invented.
                continue
            found, value = get_field(observation, path)
            if found and value is not None:
                return value
        return None

    def _active_task(self, objective: Objective) -> Task | None:
        for state in (TaskState.RUNNING, TaskState.DISPATCHED, TaskState.READY):
            for task in objective.tasks:
                if task.state is state:
                    return task
        return None

    def _waiting_approval(self) -> list[dict[str, Any]]:
        """Everything a founder is currently blocking. Two kinds, one
        list: capability approvals (MB028.1) and knowledge promotions
        (ADR-0012). Both are "the system is waiting on you"."""
        capability_approvals = [
            {"kind": "capability", **approval.as_dict()}
            for approval in self.approvals.open()
        ]
        knowledge = [
            {
                "kind": "knowledge_promotion",
                "request_id": request.request_id,
                "need": request.need,
            }
            for request in self.knowledge.awaiting_promotion()
        ]
        return capability_approvals + knowledge

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
