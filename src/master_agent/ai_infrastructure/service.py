"""The one place a Kalpavriksha component asks "which intelligence?"
(Mission Brief 032).

```
    request -> profiles -> Broker -> DecisionRecord -> approval? -> Selection
                (supplied)  (decides)   (stored)       (founder)     (executable)
```

Every arrow is an existing component used through its published contract.
This class owns no ranking, no provider list, no cost opinion and no
approval machinery — it is the wiring MB031 deliberately left undone, and
the reason MB031 could ship a kernel service that depends on nothing.

**What it guarantees, and what each guarantee costs if it is missing:**

- *Every* decision reaches the ledger before anything acts on it. A
  decision nobody recorded cannot be replayed, and an unreplayable
  decision makes "auditable" a claim rather than a property (Deliverable 7).
- A refusal is returned as data, never discovered at call time
  (Deliverable 4).
- A paid selection reaches the founder's inbox *before* execution, never
  after the money is gone (Deliverable 5).
- A free selection under a permitting policy is executable immediately,
  with no question asked (Deliverable 6).

`decide()` never raises for a refusal; `select()` raises, because
`ModelRouter.select_provider()` must return a provider or not return.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from master_agent.ai_infrastructure.approval import approval_needed
from master_agent.ai_infrastructure.budgets import derive, size_of
from master_agent.ai_infrastructure.economy import TokenEconomy, summarise
from master_agent.ai_infrastructure.ledger import (
    DENIED,
    GRANTED,
    NOT_REQUIRED,
    PENDING,
    DecisionEntry,
    DecisionLedger,
)
from master_agent.ai_infrastructure.profiles import ProviderSource
from master_agent.ai_infrastructure.refusal import (
    APPROVAL_DENIED,
    APPROVAL_PENDING,
    NO_PROVIDER,
    BrokerRefusal,
    BrokerRefused,
    NoProviderAvailable,
    ProviderApprovalDenied,
    ProviderApprovalPending,
    refusal_from_decision,
)
from master_agent.ai_infrastructure.workload import (
    profile_for as workload_profile_for,
)
from master_agent.broker.broker import CapabilityBroker
from master_agent.broker.decision import BrokerDecision, DecisionRecord
from master_agent.broker.profiles import (
    SENSITIVE,
    UNRESTRICTED,
    ProviderProfile,
    TaskProfile,
)

#: What a request that names no capability is asking for. Reasoning is the
#: Brain's door (Constitution §3.3), so it is the only sensible default.
DEFAULT_CAPABILITY = "reasoning"

NO_APPROVAL_QUEUE = (
    "no approval queue is wired, so a provider that needs your permission "
    "cannot be authorised; refusing rather than spending"
)


@dataclass(frozen=True)
class Selection:
    """A provider, chosen, recorded, and cleared to run."""

    provider_id: str
    profile: ProviderProfile
    decision: BrokerDecision
    entry: DecisionEntry
    approval_state: str = NOT_REQUIRED
    approval_id: str | None = None
    #: MB038. The three deadlines this call must honour, derived here and
    #: enforced by the adapter. `None` when the caller did not ask for a
    #: budgeted selection -- the adapter then refuses rather than
    #: inventing one, so absence is safe and visible.
    budget: Any = None

    @property
    def why(self) -> str:
        """The Broker's own sentence, never a paraphrase."""
        return self.decision.reason

    @property
    def task_id(self) -> str:
        return self.decision.task.task_id

    @property
    def cost_tier(self) -> str:
        return self.entry.cost_tier

    @property
    def quality_tier(self) -> str:
        return self.entry.quality_tier

    @property
    def record(self) -> DecisionRecord | None:
        return self.entry.record

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "why": self.why,
            "cost_tier": self.cost_tier,
            "quality_tier": self.quality_tier,
            "policy_version": self.decision.policy_version,
            "task_id": self.task_id,
            "approval_state": self.approval_state,
            "approval_id": self.approval_id,
            "entry_id": self.entry.entry_id,
        }


@dataclass(frozen=True)
class SelectionOutcome:
    """Exactly one of the two is set. There is no third state and no
    best-effort partial answer — the same discipline the Broker applies to
    `winner` being None exactly when the outcome is a refusal."""

    selection: Selection | None = None
    refusal: BrokerRefusal | None = None

    @property
    def ok(self) -> bool:
        return self.selection is not None

    def as_dict(self) -> dict[str, Any]:
        if self.selection is not None:
            return {"ok": True, "selection": self.selection.as_dict()}
        return {
            "ok": False,
            "refusal": self.refusal.as_dict() if self.refusal else None,
        }


@dataclass(frozen=True)
class BrokerReport:
    """What the Dashboard is handed (Deliverable 9).

    Plain, precomputed data — tiers already resolved, counts already
    counted — because a renderer that classifies is a renderer with an
    opinion (ADR-0016).
    """

    policy_version: str = ""
    policy_name: str = ""
    providers_available: int = 0
    providers_total: int = 0
    scanned: bool = False
    total_decisions: int = 0
    awaiting_approval: int = 0
    decisions: tuple[DecisionEntry, ...] = field(default_factory=tuple)
    recording_failures: tuple[str, ...] = field(default_factory=tuple)
    #: MB033: the last decision that was actually carried out, and the
    #: running totals over every one that was. `None` until something has
    #: run -- absence rather than a row of zeroes that reads as "it ran and
    #: achieved nothing".
    last_execution: DecisionEntry | None = None
    economy: TokenEconomy = field(default_factory=TokenEconomy)


class AiCapabilityService:
    """The Broker, wired.

    `approvals` is optional only so a caller can build a decision-only
    service (a report, a dry run). Without it, anything needing the
    founder's permission is **refused**, never assumed — see
    `NO_APPROVAL_QUEUE`.
    """

    def __init__(
        self,
        broker: CapabilityBroker,
        providers: ProviderSource,
        ledger: DecisionLedger,
        approvals: Any = None,
        strong_reasoning_min_quality: float | None = None,
        task_ids: Any = None,
        monotonic: Any = None,
    ) -> None:
        self._broker = broker
        self._providers = providers
        self._ledger = ledger
        self._approvals = approvals
        self._strong_floor = strong_reasoning_min_quality
        self._task_ids = task_ids or (lambda: f"ai-{uuid4().hex[:8]}")
        # MB038. The only clock read in budget derivation, and it is
        # injected so a test can pin it and a replay can reproduce the
        # deadlines exactly. `derive()` itself reads no clock at all.
        self._monotonic = monotonic or time.monotonic

    # ---- what it is -----------------------------------------------------

    @property
    def broker(self) -> CapabilityBroker:
        return self._broker

    @property
    def ledger(self) -> DecisionLedger:
        return self._ledger

    @property
    def providers(self) -> ProviderSource:
        return self._providers

    @property
    def policy_version(self) -> str:
        return self._broker.policy.policy_version

    def profiles(self) -> tuple[ProviderProfile, ...]:
        return self._providers.profiles()

    # ---- deciding -------------------------------------------------------

    def decide(self, request: Any) -> SelectionOutcome:
        """Choose a provider, or explain why not. Never raises for a
        refusal — a refusal is an answer."""
        profiles = self._providers.profiles()
        task = self.task_profile(request, profiles)
        # Which policy this class of work is decided under. The mapping is
        # the Broker's own -- `policy_for_request_class()` lives beside the
        # policies it names -- and `select()` has always accepted a
        # per-call policy; nothing here decides anything, it only asks.
        from master_agent.broker.policy import policy_for_request_class

        policy = policy_for_request_class(
            getattr(request, "request_class", None), self._broker.policy
        )
        decision = self._broker.select(task, list(profiles), policy=policy)
        entry = self._recorded(decision, profiles)

        if not decision.selected:
            return SelectionOutcome(
                refusal=refusal_from_decision(decision, entry.entry_id)
            )

        profile = next(p for p in profiles if p.provider_id == decision.winner)
        # MB038. Derived once the provider is known, because the budget
        # depends on *that* provider's measured throughput and tokenizer --
        # a budget computed before the decision would describe a provider
        # that might not have won.
        budget = self._budget_for(request, profile)
        reason_code = approval_needed(profile, task.sensitivity)
        if reason_code is None:
            # Deliverable 6: free, unrestricted, policy permits. Nothing to
            # ask, so nothing is asked.
            return SelectionOutcome(
                selection=Selection(
                    provider_id=profile.provider_id,
                    profile=profile,
                    decision=decision,
                    entry=entry,
                    approval_state=NOT_REQUIRED,
                    budget=budget,
                )
            )

        return self._gated(
            profile, decision, entry, task, reason_code, request, budget
        )

    def _budget_for(self, request: Any, profile: Any) -> Any:
        """The three deadlines for this call, or None.

        Returns None for a caller that did not ask for a budgeted
        selection -- every pre-MB038 caller. The adapter refuses a call
        with no budget rather than inventing one, so absence stays safe
        and visible instead of silently reverting to a static timeout.
        """
        request_class = getattr(request, "request_class", None)
        if request_class is None:
            return None

        workload = workload_profile_for(request_class)
        prompt_tokens = size_of(getattr(request, "prompt", "") or "", profile) or 0
        return derive(
            profile=profile,
            workload=workload,
            prompt_tokens=prompt_tokens,
            completion_tokens=getattr(request, "expected_output_tokens", 0) or 0,
            now=self._monotonic(),
            mission_deadline=getattr(request, "deadline", None),
        )

    def select(self, request: Any) -> Selection:
        """The `ProviderSelector` port `ModelRouter` consumes. Same
        decision as `decide()`, raised rather than returned."""
        outcome = self.decide(request)
        if outcome.selection is not None:
            return outcome.selection
        raise _as_exception(outcome.refusal)

    # ---- the pieces -----------------------------------------------------

    def task_profile(
        self, request: Any, profiles: tuple[ProviderProfile, ...] = ()
    ) -> TaskProfile:
        """Translate a caller's request into what the Broker decides over.

        Two translations are the whole point of MB032:

        - **"I need strong reasoning" becomes a quality floor**, not a
          product. The branch this replaces returned a named cloud provider
          for exactly this request, which is the hardcoding ADR-0017 called
          a documented contradiction.
        - **"Use this provider" becomes an exclusion of every other**, so
          an override still produces a real decision with a real record.
          A preferred provider that is unavailable, unapproved, or below
          the floor is refused with a reason rather than used because
          somebody asked nicely.
        """
        preferred = getattr(request, "preferred_provider", None)
        excluded = set(getattr(request, "exclude_providers", ()) or ())
        if preferred:
            excluded |= {
                profile.provider_id
                for profile in profiles
                if profile.provider_id != preferred
            }

        return TaskProfile(
            capability=getattr(request, "capability", None) or DEFAULT_CAPABILITY,
            task_id=getattr(request, "task_id", "") or self._task_ids(),
            sensitivity=SENSITIVE if getattr(request, "sensitive", False) else UNRESTRICTED,
            min_quality=self._floor(request),
            max_cost=getattr(request, "max_cost", None),
            max_latency_ms=getattr(request, "max_latency_ms", None),
            required_context_tokens=getattr(request, "required_context_tokens", None),
            offline=bool(getattr(request, "offline", False)),
            exclude_providers=frozenset(excluded),
            requester=getattr(request, "requester", "") or "model_router",
        )

    def _floor(self, request: Any) -> float | None:
        """The strictest bar anyone asked for. A request that both names a
        floor and asks for strong reasoning gets the higher of the two —
        taking the later one would let the order of two independent
        statements change the answer."""
        floors = [
            floor
            for floor in (
                getattr(request, "min_quality", None),
                self._strong_floor
                if getattr(request, "requires_strong_reasoning", False)
                else None,
            )
            if floor is not None
        ]
        return max(floors) if floors else None

    def _recorded(
        self, decision: BrokerDecision, profiles: tuple[ProviderProfile, ...]
    ) -> DecisionEntry:
        """The ledger entry for this exact decision.

        The ledger is normally the Broker's `sink`, so the entry already
        exists by the time this runs and the lookup is an identity match.
        Recording it here when it does not is not belt-and-braces
        superstition: Deliverable 7 says *every* AI task has a stored
        record, and a service that quietly skipped one when its sink was
        mis-wired would break replay in the least visible way possible.
        """
        entry = self._ledger.entry_for_decision(decision)
        if entry is not None:
            return entry
        return self._ledger.record(
            DecisionRecord(
                decision=decision,
                policy=self._broker.policy,
                providers=tuple(sorted(profiles, key=lambda p: p.provider_id)),
            )
        )

    def _gated(
        self,
        profile: ProviderProfile,
        decision: BrokerDecision,
        entry: DecisionEntry,
        task: TaskProfile,
        reason_code: str,
        request: Any,
        budget: Any = None,
    ) -> SelectionOutcome:
        base = BrokerRefusal(
            kind=NO_PROVIDER,
            reason=decision.reason,
            capability=task.capability,
            task_id=task.task_id,
            provider_id=profile.provider_id,
            policy_version=decision.policy_version,
            rejected=tuple((c.provider_id, c.reason) for c in decision.rejected),
            entry_id=entry.entry_id,
            decision=decision,
        )

        if self._approvals is None:
            refusal = BrokerRefusal(
                kind=APPROVAL_DENIED,
                reason=NO_APPROVAL_QUEUE,
                capability=task.capability,
                task_id=task.task_id,
                provider_id=profile.provider_id,
                policy_version=decision.policy_version,
                rejected=base.rejected,
                entry_id=entry.entry_id,
                decision=decision,
            )
            self._ledger.set_approval(entry.entry_id, DENIED)
            return SelectionOutcome(refusal=refusal)

        try:
            approval_id = self._approvals.review(
                provider_id=profile.provider_id,
                reason_code=reason_code,
                capability=task.capability,
                task_id=task.task_id,
                cost=profile.cost,
                locality=profile.locality,
                privacy=profile.privacy,
                objective_id=getattr(request, "objective_id", None),
                refusal=base,
            )
        except ProviderApprovalPending as pending:
            self._ledger.set_approval(
                entry.entry_id, PENDING, pending.refusal.approval_id
            )
            # The gate was handed `base` and copies its `entry_id` through,
            # so the refusal already points at the right ledger entry.
            return SelectionOutcome(refusal=pending.refusal)
        except ProviderApprovalDenied as denied:
            self._ledger.set_approval(
                entry.entry_id, DENIED, denied.refusal.approval_id
            )
            return SelectionOutcome(refusal=denied.refusal)

        updated = self._ledger.set_approval(
            entry.entry_id, GRANTED, approval_id or None
        )
        return SelectionOutcome(
            selection=Selection(
                provider_id=profile.provider_id,
                profile=profile,
                decision=decision,
                entry=updated,
                approval_state=GRANTED,
                approval_id=approval_id or None,
                budget=budget,
            )
        )

    # ---- reading --------------------------------------------------------

    def report(self, limit: int = 5) -> BrokerReport:
        """One read-only snapshot for the Dashboard. Collects; decides
        nothing, and cannot: every value here already exists."""
        available, total = self._providers.counts()
        policy = self._broker.policy
        return BrokerReport(
            policy_version=policy.policy_version,
            policy_name=policy.name,
            providers_available=available,
            providers_total=total,
            scanned=self._providers.has_scan(),
            total_decisions=len(self._ledger),
            awaiting_approval=len(self._ledger.awaiting_approval()),
            decisions=self._ledger.recent(limit),
            recording_failures=tuple(self._broker.recording_failures)
            + tuple(self._ledger.write_failures),
            last_execution=self._ledger.last_execution(),
            # Recomputed from the ledger on every read rather than kept as
            # a counter: a counter and a ledger eventually disagree, and
            # the counter is the one on the screen.
            economy=summarise(self._ledger.entries()),
        )


def _as_exception(refusal: BrokerRefusal | None) -> BrokerRefused:
    """One refusal kind, one exception type. A caller catching
    `ProviderApprovalPending` is asking a different question from one
    catching `NoProviderAvailable`, and a single type would force both to
    inspect a string."""
    if refusal is None:  # pragma: no cover - decide() always sets one
        refusal = BrokerRefusal(kind=NO_PROVIDER, reason="no decision was made")
    if refusal.kind == APPROVAL_PENDING:
        return ProviderApprovalPending(refusal)
    if refusal.kind == APPROVAL_DENIED:
        return ProviderApprovalDenied(refusal)
    return NoProviderAvailable(refusal)
