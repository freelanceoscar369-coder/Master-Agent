"""The Founder Execution Status contract (Task 2.5).

Hyper Agent owns every visual decision about how a founder sees an
objective run — this module owns none of them. What it produces is a
plain, UI-agnostic snapshot of *semantic* fact, built by watching the same
event bus every other observer in this codebase already watches
(`mission_control.bus`), plus the two phase events `missions/service.py`
now publishes for the two stretches of work that happen before any Task
exists.

Nothing here decides anything. It is a read model: a real event happened,
this records what it honestly implies about where the objective is right
now, and nothing is reported that the event stream did not actually say.
An unknown stays `None`, never guessed at — the same discipline
`capabilities/contract.py`'s `UNKNOWN` already holds elsewhere.

No color, animation, icon, or visual metaphor is ever produced here — that
is Hyper Agent's decision entirely, made from the semantic fields below.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from master_agent.mission_control.events import Event, EventType

# ---- the eleven states Task 2.5 names, and nothing else -------------------

UNDERSTANDING = "understanding"
#: The founder has been asked a question and the objective is waiting on
#: their answer. Deliberately NOT `COMPLETED`: the surface used to mark a
#: clarified objective completed the moment the question was successfully
#: displayed, which told the founder their request had finished when in
#: fact it had not started. ADR-0024 Decision 10 -- a clarification is not
#: an outcome. Sits beside `AWAITING_APPROVAL` and
#: `AWAITING_FOUNDER_COMPLETION` because it is the same shape of fact:
#: work is paused, and a specific founder response resumes it.
AWAITING_CLARIFICATION = "awaiting_clarification"
PLANNING = "planning"
AWAITING_APPROVAL = "awaiting_approval"
EXECUTING = "executing"
OBSERVING = "observing"
VERIFYING = "verifying"
RECOVERING = "recovering"
AWAITING_FOUNDER_COMPLETION = "awaiting_founder_completion"
COMPLETED = "completed"
FAILED = "failed"
BLOCKED = "blocked"

TERMINAL_STATUSES = frozenset({COMPLETED, FAILED})

#: The event types that move `status`, in the order that reflects why: an
#: event later in this mapping overrides one earlier only because it was
#: published later in real time, never because of a priority assigned here.
_STATUS_BY_EVENT = {
    EventType.MISSION_UNDERSTANDING_STARTED: UNDERSTANDING,
    EventType.MISSION_PLANNING_STARTED: PLANNING,
    EventType.APPROVAL_REQUESTED: AWAITING_APPROVAL,
    EventType.APPROVAL_REQUIRED: AWAITING_APPROVAL,
    EventType.VERIFICATION_STARTED: VERIFYING,
    EventType.TASK_RETRY_SCHEDULED: RECOVERING,
    EventType.TASK_BLOCKED: BLOCKED,
    EventType.OBJECTIVE_FAILED: FAILED,
    EventType.FOUNDER_COMPLETION_REQUESTED: AWAITING_FOUNDER_COMPLETION,
    EventType.FOUNDER_COMPLETION_CONFIRMED: COMPLETED,
}


@dataclass
class PendingClarification:
    """A question the founder has been asked, and everything needed to
    resume the objective from their answer.

    ## Why the semantic key travels as data

    `ClarificationQuestion.key` already existed and was dropped before
    reaching the founder: only `question` was transmitted, as the `detail`
    string of a `PlanRefusal`. That left the answer un-attachable —
    `"Research"` arrived with nothing saying *what it was the answer to*,
    so resolving it meant re-reading the question text and inferring the
    field. `key` is carried here so that never has to happen.

    ## Why `objective` is stored rather than recovered

    `ExecutionStatus.objective` holds the same sentence, but `begin()`
    overwrites it the moment the next founder message arrives — including
    the message that *is* the answer. Holding the founder's original
    request here makes resumption independent of call ordering, and it is
    the string re-parsed on resolution, so everything they already said
    (a location, a project type) is re-derived from their own words.

    `options` is carried even though today's surface renders a plain text
    prompt: the field exists on `ClarificationQuestion`, a founder may be
    offered choices later, and dropping it here would recreate exactly the
    transport gap `key` is here to close.
    """

    question: str
    key: str
    objective: str
    options: tuple[str, ...] = ()
    required: bool = True
    #: Correlates the founder's answer with this question. A dedicated id
    #: rather than a reused one: `approval_id` names a permission decision
    #: on an objective that already exists, and `completion_id` names
    #: founder confirmation of one that has finished. A clarification
    #: happens *before* an objective exists at all, so neither identifier
    #: is in scope for it, and borrowing one would make two different
    #: founder interactions indistinguishable to the surface. Minted the
    #: same way both of those are (`uuid4().hex[:8]`, see
    #: `mission_control/approvals.py`), so nothing new is introduced but
    #: the name.
    clarification_id: str = field(default_factory=lambda: uuid4().hex[:8])

    def as_dict(self) -> dict[str, Any]:
        return {
            "clarification_id": self.clarification_id,
            "question": self.question,
            "key": self.key,
            "options": list(self.options),
            "required": self.required,
        }


@dataclass
class ExecutionStatus:
    """One founder objective's live status, as a plain, JSON-shaped
    contract. Mutated only by `record()`, which does nothing but read an
    `Event` that already happened — the same "an event describes something
    that already happened" discipline `Event` itself documents.
    """

    status: str | None = None
    objective_id: str | None = None
    objective: str | None = None
    current_step: int = 0
    total_steps: int = 0
    current_task_id: str | None = None
    current_capability: str | None = None
    attempt: int = 1
    max_attempts: int | None = None
    timeout_ms: int | None = None
    started_at: datetime | None = None
    message: str | None = None
    result: Any = None
    requires_founder_completion: bool = False
    completion_id: str | None = None
    #: The open founder approval, when one is waiting. Carried so the
    #: Founder Surface can offer the decision rather than only report
    #: that a decision is needed.
    approval_id: str | None = None
    #: The open founder question, when one is waiting. Same shape of fact
    #: as `approval_id` above: the objective is paused and a specific
    #: founder response resumes it. `None` whenever nothing is pending.
    pending_clarification: PendingClarification | None = None
    errors: list[str] = field(default_factory=list)

    # ---- lifecycle ---------------------------------------------------

    def begin(
        self, objective_text: str, *, timeout_seconds: float | None = None
    ) -> None:
        """Reset for a new objective. Called by the composition root at
        the one real moment a founder's request starts being processed —
        immediately before `MissionService.start()` — so `started_at` is
        truthful rather than backdated to the first event this object
        happens to observe."""
        self.status = None
        self.objective_id = None
        self.objective = objective_text
        self.current_step = 0
        self.total_steps = 0
        self.current_task_id = None
        self.current_capability = None
        self.attempt = 1
        self.max_attempts = None
        self.timeout_ms = int(timeout_seconds * 1000) if timeout_seconds else None
        self.started_at = datetime.now(UTC)
        self.message = None
        self.result = None
        self.requires_founder_completion = False
        self.completion_id = None
        self.approval_id = None
        # A new objective inherits no question. The founder surface reads
        # any pending clarification BEFORE calling this, precisely because
        # the message that answers one arrives as the next objective.
        self.pending_clarification = None
        self.errors = []

    def record(self, event: Event) -> None:
        """The one place an `Event` becomes a status fact. Never raises —
        an observer that could break the pipeline it is only watching
        would be worse than an observer that occasionally reports nothing
        new."""
        if event.objective_id is not None and self.objective_id is None:
            self.objective_id = event.objective_id

        if event.event_type is EventType.RUNTIME_STARTED:
            attempts = (event.payload or {}).get("max_attempts")
            if isinstance(attempts, int):
                self.max_attempts = attempts
            return

        if event.event_type is EventType.TASK_CREATED:
            self.total_steps += 1
            return

        if event.event_type is EventType.TASK_STARTED:
            self.current_step += 1
            self.current_task_id = event.task_id
            self.current_capability = event.capability
            self.attempt = 1
            self.status = _observing_or_executing(event.capability)
            return

        if event.event_type is EventType.TASK_RETRY_SCHEDULED:
            payload = event.payload or {}
            attempt = payload.get("attempt")
            of = payload.get("of")
            if isinstance(attempt, int):
                self.attempt = attempt
            if isinstance(of, int):
                self.max_attempts = of
            self.status = RECOVERING
            return

        if event.event_type is EventType.OBJECTIVE_COMPLETED:
            # Verified, not yet founder-completed — MissionControl opens
            # the completion question off this same event
            # (mission_control/completion.py); this object just reports
            # that the question is now open, once FOUNDER_COMPLETION_
            # REQUESTED itself arrives below. Nothing here claims COMPLETED.
            return

        if event.event_type in (
            EventType.APPROVAL_REQUESTED, EventType.APPROVAL_REQUIRED,
        ):
            self.approval_id = (event.payload or {}).get("approval_id")
        elif event.event_type in (
            EventType.APPROVAL_GRANTED, EventType.APPROVAL_DENIED,
        ):
            # Answered -- the question is no longer open.
            self.approval_id = None

        if event.event_type is EventType.FOUNDER_COMPLETION_REQUESTED:
            self.requires_founder_completion = True
            self.completion_id = (event.payload or {}).get("completion_id")
            self.status = AWAITING_FOUNDER_COMPLETION
            return

        if event.event_type is EventType.FOUNDER_COMPLETION_CONFIRMED:
            self.requires_founder_completion = False
            self.status = COMPLETED
            return

        if event.event_type is EventType.OBJECTIVE_FAILED:
            self.errors.append(event.error or "objective failed")
            self.status = FAILED
            return

        mapped = _STATUS_BY_EVENT.get(event.event_type)
        if mapped is not None:
            self.status = mapped

    # ---- reading -------------------------------------------------------

    @property
    def elapsed_ms(self) -> int | None:
        if self.started_at is None:
            return None
        return int((datetime.now(UTC) - self.started_at).total_seconds() * 1000)

    @property
    def terminal_state(self) -> bool:
        return self.status in TERMINAL_STATUSES

    def as_dict(self) -> dict[str, Any]:
        """The Hyper Agent contract (Task 2.5 §8). Every field here is a
        fact this object actually observed — `None` where nothing has
        determined a value yet, never a guess."""
        return {
            "status": self.status,
            "objective_id": self.objective_id,
            "objective": self.objective,
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "current_task_id": self.current_task_id,
            "current_capability": self.current_capability,
            "attempt": self.attempt,
            "max_attempts": self.max_attempts,
            "elapsed_ms": self.elapsed_ms,
            "timeout_ms": self.timeout_ms,
            "message": self.message,
            "result": self.result,
            "requires_founder_completion": self.requires_founder_completion,
            "completion_id": self.completion_id,
            "approval_id": self.approval_id,
            "pending_clarification": (
                self.pending_clarification.as_dict()
                if self.pending_clarification is not None else None
            ),
            "errors": list(self.errors),
            "terminal_state": self.terminal_state,
        }


def _observing_or_executing(capability: str | None) -> str:
    """`Browser.ObserveBrowser` is a real, already-published capability
    name — reading "observe" out of it is reading a fact the Planner/
    Executive already stated, not inventing a second classification of
    what a task does."""
    if capability and "observe" in capability.lower():
        return OBSERVING
    return EXECUTING
