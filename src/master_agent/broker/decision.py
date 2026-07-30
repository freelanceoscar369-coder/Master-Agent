"""What a decision *is*, and the record it leaves (MB031 Deliverables 5, 10).

Two shapes. `BrokerDecision` is the answer handed back to a caller;
`DecisionRecord` is the immutable evidence that the answer was given, and
the input needed to reproduce it.

Both carry the **full candidate list with reasons**, not just the winner.
MB031 Deliverable 9 asks for ranked candidates and Deliverable 10 for
structured refusal, but the deeper reason is auditability: the question a
founder asks six weeks later is *"why didn't it use the local one?"*, and
a record containing only the winner cannot answer it (ADR-0017 §3.5).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from master_agent.broker.policy import SelectionPolicy
from master_agent.broker.profiles import ProviderProfile, TaskProfile

# ---- outcomes -----------------------------------------------------------

SELECTED = "selected"
NO_PROVIDER_AVAILABLE = "no_provider_available"

# ---- why a candidate was rejected ---------------------------------------
#
# Every rejection names one of these. A refusal that says only "none
# suitable" is a refusal a founder cannot act on.

NO_CAPABILITY = "does not offer this capability"
UNAVAILABLE = "not available"
EXCLUDED = "excluded by the request"
NEEDS_NETWORK = "requires the network, and this task is offline-only"
CLOUD_FORBIDDEN = "cloud providers are not permitted by policy"
PAID_FORBIDDEN = "paid providers are not permitted by policy"
NOT_PRIVATE = "sensitive work may not go to a third party"
OVER_COST = "costs more than the request allows"
OVER_LATENCY = "slower than the request allows"
CONTEXT_TOO_SMALL = "context window is too small for this task"
NEEDS_APPROVAL = "needs founder approval, which has not been given"
BELOW_FLOOR = "below the quality floor"


@dataclass(frozen=True)
class Candidate:
    """One provider considered, and what became of it."""

    provider_id: str
    eligible: bool
    reason: str = ""
    quality: float = 0.0
    cost: float = 0.0
    latency_ms: float | None = None
    locality: str = ""
    rank: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "eligible": self.eligible,
            "reason": self.reason,
            "quality": self.quality,
            "cost": self.cost,
            "latency_ms": self.latency_ms,
            "locality": self.locality,
            "rank": self.rank,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Candidate:
        return cls(
            provider_id=data["provider_id"],
            eligible=data["eligible"],
            reason=data.get("reason", ""),
            quality=data.get("quality", 0.0),
            cost=data.get("cost", 0.0),
            latency_ms=data.get("latency_ms"),
            locality=data.get("locality", ""),
            rank=data.get("rank"),
        )


@dataclass(frozen=True)
class BrokerDecision:
    """The answer. `winner` is None exactly when `outcome` is
    `NO_PROVIDER_AVAILABLE` — there is no third state, and no "best
    effort" fallback (Deliverable 10: never invent a provider)."""

    outcome: str
    task: TaskProfile
    policy_version: str
    quality_floor: float
    candidates: tuple[Candidate, ...] = ()
    winner: str | None = None
    reason: str = ""
    inputs_digest: str = ""
    decided_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def selected(self) -> bool:
        return self.outcome == SELECTED

    @property
    def ranked(self) -> tuple[Candidate, ...]:
        """Eligible candidates, best first. Deliverable 9: the caller gets
        the runners-up, so re-asking after a failure costs nothing."""
        return tuple(
            candidate
            for candidate in self.candidates
            if candidate.eligible and candidate.rank is not None
        )

    @property
    def rejected(self) -> tuple[Candidate, ...]:
        return tuple(c for c in self.candidates if not c.eligible)

    def as_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome,
            "task": self.task.as_dict(),
            "policy_version": self.policy_version,
            "quality_floor": self.quality_floor,
            "candidates": [c.as_dict() for c in self.candidates],
            "winner": self.winner,
            "reason": self.reason,
            "inputs_digest": self.inputs_digest,
            "decided_at": self.decided_at.isoformat(),
        }


@dataclass(frozen=True)
class DecisionRecord:
    """Immutable evidence, and everything needed to reproduce the answer.

    Carries the **provider profiles as they were**, not a reference to
    whatever they are now. A replay that re-read today's providers would
    not be reproducing a historical decision; it would be making a new one
    and calling it history (Deliverable 6).
    """

    decision: BrokerDecision
    policy: SelectionPolicy
    providers: tuple[ProviderProfile, ...]

    @property
    def policy_version(self) -> str:
        return self.decision.policy_version

    @property
    def winner(self) -> str | None:
        return self.decision.winner

    def as_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.as_dict(),
            "policy": self.policy.as_dict(),
            "providers": [p.as_dict() for p in self.providers],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DecisionRecord:
        decision = data["decision"]
        return cls(
            decision=BrokerDecision(
                outcome=decision["outcome"],
                task=TaskProfile.from_dict(decision["task"]),
                policy_version=decision["policy_version"],
                quality_floor=decision["quality_floor"],
                candidates=tuple(
                    Candidate.from_dict(c) for c in decision.get("candidates", ())
                ),
                winner=decision.get("winner"),
                reason=decision.get("reason", ""),
                inputs_digest=decision.get("inputs_digest", ""),
                decided_at=datetime.fromisoformat(decision["decided_at"]),
            ),
            policy=SelectionPolicy.from_dict(data["policy"]),
            providers=tuple(
                ProviderProfile.from_dict(p) for p in data.get("providers", ())
            ),
        )


def compute_digest(
    task: TaskProfile,
    providers: tuple[ProviderProfile, ...],
    policy: SelectionPolicy,
) -> str:
    """A stable fingerprint of everything that determined a decision.

    This is what makes "every decision is auditable" a property rather
    than a claim: two decisions with the same digest must have the same
    outcome, and a digest that changed means an input changed. Providers
    are sorted by id first, so the same set in a different order
    fingerprints identically — otherwise the digest would record the
    caller's list order, which is not an input to anything.
    """
    payload = {
        "task": task.as_dict(),
        "policy": policy.as_dict(),
        "providers": sorted(
            (p.as_dict() for p in providers), key=lambda p: p["provider_id"]
        ),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]
