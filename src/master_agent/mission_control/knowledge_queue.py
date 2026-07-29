"""The Knowledge Acquisition Queue (Mission Brief 023 deliverable #7).

The brief's seven-stage pipeline, advanced one stage at a time:

    NEED -> RESEARCH -> SOURCE_COLLECTION -> COMPARISON -> VERIFICATION
         -> KNOWLEDGE_STORAGE -> CAPABILITY_CREATION

Skipping a stage is refused, so the pipeline cannot be short-circuited
into "we needed it, therefore we know it."

## The promotion gate is enforced here, in code

Constitution ADR-0012 makes Promotion Review human-gated for Founder
Edition: promoting knowledge silently reshapes every future planning
decision, which is exactly the class of consequential, hard-to-reverse
action Constitution §15 exists to gate. So the single advance from
VERIFICATION into KNOWLEDGE_STORAGE requires an explicit
`human_approved=True`; without it the advance is refused with a
structured error naming the ADR.

Mission Control can therefore drive this entire pipeline autonomously up
to that gate, and never past it. This is the one place Mission Control
deliberately refuses to be fully automatic — see
MISSION_CONTROL_ARCHITECTURE.md §8.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4


class KnowledgeStage(str, Enum):
    NEED = "need"
    RESEARCH = "research"
    SOURCE_COLLECTION = "source_collection"
    COMPARISON = "comparison"
    VERIFICATION = "verification"
    KNOWLEDGE_STORAGE = "knowledge_storage"
    CAPABILITY_CREATION = "capability_creation"
    REJECTED = "rejected"


# The pipeline in order. Advancing means moving exactly one step along
# this list -- never two, never backwards.
_PIPELINE: list[KnowledgeStage] = [
    KnowledgeStage.NEED,
    KnowledgeStage.RESEARCH,
    KnowledgeStage.SOURCE_COLLECTION,
    KnowledgeStage.COMPARISON,
    KnowledgeStage.VERIFICATION,
    KnowledgeStage.KNOWLEDGE_STORAGE,
    KnowledgeStage.CAPABILITY_CREATION,
]

# Crossing this boundary is Promotion Review (ADR-0012) and requires a
# human decision. Named as a constant so the rule is one fact, not a
# condition duplicated across call sites.
PROMOTION_GATE_FROM = KnowledgeStage.VERIFICATION
PROMOTION_GATE_TO = KnowledgeStage.KNOWLEDGE_STORAGE


class IllegalKnowledgeTransition(Exception):
    pass


class PromotionRequiresHumanApproval(Exception):
    """Raised when something tries to promote a Knowledge Candidate into
    permanent knowledge without an explicit human decision. This is not a
    validation nicety — it is the code-level enforcement of ADR-0012."""


class UnknownKnowledgeRequest(Exception):
    pass


@dataclass
class KnowledgeRequest:
    need: str
    detail: str = ""
    request_id: str = field(default_factory=lambda: str(uuid4()))
    stage: KnowledgeStage = KnowledgeStage.NEED
    sources: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    promoted_by: str | None = None
    rejection_reason: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_promoted(self) -> bool:
        return self.stage in {KnowledgeStage.KNOWLEDGE_STORAGE, KnowledgeStage.CAPABILITY_CREATION}

    def as_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "need": self.need,
            "stage": self.stage.value,
            "sources": list(self.sources),
            "evidence_ids": list(self.evidence_ids),
            "promoted_by": self.promoted_by,
            "rejection_reason": self.rejection_reason,
        }


class KnowledgeAcquisitionQueue:
    def __init__(self) -> None:
        self._requests: dict[str, KnowledgeRequest] = {}
        self._order: list[str] = []

    def add(self, request: KnowledgeRequest) -> KnowledgeRequest:
        self._requests[request.request_id] = request
        self._order.append(request.request_id)
        return request

    def get(self, request_id: str) -> KnowledgeRequest:
        request = self._requests.get(request_id)
        if request is None:
            raise UnknownKnowledgeRequest(f"unknown knowledge request: {request_id}")
        return request

    def next_stage(self, request_id: str) -> KnowledgeStage | None:
        request = self.get(request_id)
        if request.stage is KnowledgeStage.REJECTED:
            return None
        index = _PIPELINE.index(request.stage)
        if index + 1 >= len(_PIPELINE):
            return None
        return _PIPELINE[index + 1]

    def advance(
        self,
        request_id: str,
        human_approved: bool = False,
        approved_by: str | None = None,
    ) -> KnowledgeRequest:
        """Advance exactly one pipeline stage.

        `human_approved` is consulted only at the Promotion Review gate
        (VERIFICATION -> KNOWLEDGE_STORAGE); everywhere else it is
        irrelevant, because no other stage change makes anything durable.
        """
        request = self.get(request_id)

        if request.stage is KnowledgeStage.REJECTED:
            raise IllegalKnowledgeTransition("a rejected knowledge request cannot advance")

        target = self.next_stage(request_id)
        if target is None:
            raise IllegalKnowledgeTransition(
                f"knowledge request is already at the final stage: {request.stage.value}"
            )

        if request.stage is PROMOTION_GATE_FROM and target is PROMOTION_GATE_TO:
            if not human_approved:
                raise PromotionRequiresHumanApproval(
                    "promoting a Knowledge Candidate into permanent knowledge requires an "
                    "explicit human decision (Promotion Review) -- see "
                    "docs/adr/0012-knowledge-lifecycle.md"
                )
            request.promoted_by = approved_by or "human"

        request.stage = target
        request.updated_at = datetime.now(UTC)
        return request

    def reject(self, request_id: str, reason: str) -> KnowledgeRequest:
        """Rejection is available at any stage — Promotion Review can
        refuse a Candidate outright (ADR-0012), and so can any earlier
        stage that finds the need was misconceived."""
        request = self.get(request_id)
        request.stage = KnowledgeStage.REJECTED
        request.rejection_reason = reason
        request.updated_at = datetime.now(UTC)
        return request

    def awaiting_promotion(self) -> list[KnowledgeRequest]:
        """Everything sitting at the human gate — this is what a founder
        dashboard surfaces as "waiting on you"."""
        return [r for r in self.all() if r.stage is PROMOTION_GATE_FROM]

    def all(self) -> list[KnowledgeRequest]:
        return [self._requests[request_id] for request_id in self._order]

    def by_stage(self, stage: KnowledgeStage) -> list[KnowledgeRequest]:
        return [r for r in self.all() if r.stage is stage]

    def __len__(self) -> int:
        return len(self._requests)
