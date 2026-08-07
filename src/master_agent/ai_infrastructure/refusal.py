"""Structured refusal (Mission Brief 032 Deliverable 4).

> If a required provider is unavailable, return a structured Broker
> refusal instead of failing later.

"Failing later" is the failure mode this exists to stop: selecting
something optimistically, handing it to a caller, and discovering at call
time that it is not installed, not paid for, or not approved — by which
point the founder is reading a stack trace from a provider SDK instead of
a sentence about their own machine.

So a refusal is **data first**: `BrokerRefusal` carries the reason, the
policy that produced it, and every provider that was considered with why
it was rejected. `AiCapabilityService.decide()` returns one and raises
nothing. The exception types below wrap the same object for callers whose
signature has no room for a refusal — `ModelRouter.select_provider()` has
to return a provider or not return at all.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from master_agent.broker.decision import BrokerDecision

#: Why a request could not be served. Each one has a different answer for
#: the founder, which is the whole reason they are separate values:
#: install something, say yes, or ask for something else.
NO_PROVIDER = "no_provider"
APPROVAL_PENDING = "approval_pending"
APPROVAL_DENIED = "approval_denied"
REFUSAL_KINDS = (NO_PROVIDER, APPROVAL_PENDING, APPROVAL_DENIED)


@dataclass(frozen=True)
class BrokerRefusal:
    """Why nothing ran, in a shape a caller can act on or display."""

    kind: str
    reason: str
    capability: str = ""
    task_id: str = ""
    provider_id: str | None = None
    approval_id: str | None = None
    policy_version: str = ""
    #: (provider_id, why it was rejected), for every provider considered.
    #: The Broker's own candidate list, carried through unchanged: "why
    #: didn't it use the local one?" has to be answerable from here.
    rejected: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    entry_id: int | None = None
    decision: BrokerDecision | None = None

    @property
    def waiting(self) -> bool:
        """Pending is not a failure. The founder has been asked and the
        work is still live — the same distinction MB028.1 drew between
        `ApprovalPending` and `ApprovalDenied`."""
        return self.kind == APPROVAL_PENDING

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "reason": self.reason,
            "capability": self.capability,
            "task_id": self.task_id,
            "provider_id": self.provider_id,
            "approval_id": self.approval_id,
            "policy_version": self.policy_version,
            "rejected": [
                {"provider_id": provider_id, "reason": why}
                for provider_id, why in self.rejected
            ],
            "entry_id": self.entry_id,
        }


def refusal_from_decision(
    decision: BrokerDecision, entry_id: int | None = None
) -> BrokerRefusal:
    """A `NO_PROVIDER_AVAILABLE` decision, read as a refusal.

    The Broker already writes a founder-readable reason and the full
    rejection list; this reshapes them rather than composing a second
    explanation, because two explanations of one event eventually
    disagree.
    """
    return BrokerRefusal(
        kind=NO_PROVIDER,
        reason=decision.reason,
        capability=decision.task.capability,
        task_id=decision.task.task_id,
        policy_version=decision.policy_version,
        rejected=tuple(
            (candidate.provider_id, candidate.reason) for candidate in decision.rejected
        ),
        entry_id=entry_id,
        decision=decision,
    )


class BrokerRefused(Exception):
    """Base for every "this did not run, and here is why".

    Carries the `BrokerRefusal` rather than only a message, so a caller
    that catches it can still show the founder the candidate list without
    re-deriving anything.
    """

    def __init__(self, refusal: BrokerRefusal) -> None:
        super().__init__(refusal.reason)
        self.refusal = refusal

    @property
    def kind(self) -> str:
        return self.refusal.kind


class NoProviderAvailable(BrokerRefused):
    """Nothing on this machine can serve the request under this policy.
    Actionable: install something, lower the bar, or change the policy."""


class ProviderApprovalPending(BrokerRefused):
    """The founder has been asked and has not answered.

    Deliberately **not** a subclass of a denial, for the reason MB028.1
    gives: pending is an open question and the work waits; denied is a
    decision and the work stops. Conflating them turns "the founder was
    asleep" into "the mission failed".
    """

    @property
    def approval_id(self) -> str | None:
        return self.refusal.approval_id


class ProviderApprovalDenied(BrokerRefused):
    """The founder said no, or the question expired unanswered. Never
    retried — asking again and hoping for a different answer is not a
    recovery strategy."""
