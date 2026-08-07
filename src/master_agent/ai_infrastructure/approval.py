"""Routing a Broker selection into the founder's Approval Queue (Mission
Brief 032 Deliverable 5).

> The Broker implements no approval machinery. Paid selection is expressed
> as a check against Shared Infrastructure's existing Permission System.
> — ADR-0017 Decision 7

So this module builds nothing. It is an adapter between two components
that already shipped:

    Broker selects a provider
        -> is this one free and unrestricted?   yes -> run it now
        -> no  -> Permission System: is there a grant?   yes -> run it now
        -> no  -> Mission Control's Approval Queue (MB028.1)  -> the task waits

**Zero new approval paths**, exactly as ADR-0018 Decision 3 required of the
learning loop: the founder answers with `approve 1` in the same console,
against the same queue, and the same immutable ledger records it.

## Two things need a founder, and only two

1. **A paid provider.** Money leaves.
2. **Sensitive work reaching a third party.** ADR-0017 Decision 7 adds this
   deliberately: MB027's policy is organised around money, but a *free*
   cloud model is still a third party receiving the founder's data, and
   gating a £0.002 call while waving through a free upload of the same
   content would be protecting the wrong thing. (Every shipped policy
   filters this out before selection; the check exists for a policy that
   does not.)

Everything else runs immediately (Deliverable 6).

## Why IRREVERSIBLE

Spent money cannot be unspent and sent data cannot be unsent. Classifying
both at `IRREVERSIBLE` inherits ADR-0009's already-shipped guarantee: an
`ALWAYS_FOR_CAPABILITY` grant can never satisfy an `IRREVERSIBLE` check, so
no standing "yes, use paid AI" can ever quietly authorise the next call.
Approval is granted `ONCE` and consumed by the check that uses it.
"""
from __future__ import annotations

from typing import Any

from master_agent.ai_infrastructure.refusal import (
    APPROVAL_DENIED,
    APPROVAL_PENDING,
    BrokerRefusal,
    ProviderApprovalDenied,
    ProviderApprovalPending,
)
from master_agent.ai_infrastructure.tiers import describe_cost, is_free
from master_agent.broker.profiles import PRIVATE, SENSITIVE
from master_agent.mission_control.approvals import PendingApproval
from master_agent.permissions.permission_system import GrantScope
from master_agent.plugins.base import RiskTier

# ---- why a founder is being asked ---------------------------------------

PAID = "paid"
SENSITIVE_THIRD_PARTY = "sensitive_third_party"

#: The local capability names the grant ledger is keyed on. Snake_case,
#: because that is what `PermissionSystem.check()` has always taken.
PAID_CAPABILITY = "use_paid_provider"
SENSITIVE_CAPABILITY = "send_sensitive_to_third_party"

#: What the founder sees in the queue. `PascalCase.PascalCase` matches
#: Mission Control's qualified-name convention, and the provider is part of
#: the key so two providers for one task are two separate questions.
QUALIFIED = {
    PAID: "Broker.UsePaidProvider",
    SENSITIVE_THIRD_PARTY: "Broker.SendSensitiveToThirdParty",
}
LOCAL_CAPABILITY = {
    PAID: PAID_CAPABILITY,
    SENSITIVE_THIRD_PARTY: SENSITIVE_CAPABILITY,
}
HUMAN_REASON = {
    PAID: "Use A Paid Provider",
    SENSITIVE_THIRD_PARTY: "Send Sensitive Work To A Third Party",
}

#: Both are irreversible — see the module docstring.
RISK_TIER = RiskTier.IRREVERSIBLE

APPROVAL_REQUESTER = "ai_capability_broker"


def approval_needed(profile: Any, sensitivity: str) -> str | None:
    """Does this selection need a founder, and why? `None` means no.

    Deliberately a free function over two plain facts: it is the rule
    itself, and a rule worth stating once is worth being able to test
    without constructing a queue.
    """
    if not is_free(getattr(profile, "cost", None)):
        return PAID
    if sensitivity == SENSITIVE and getattr(profile, "privacy", None) != PRIVATE:
        return SENSITIVE_THIRD_PARTY
    return None


class ProviderApprovalGate:
    """Turns "this selection needs a yes" into a question in the founder's
    inbox, and a founder's yes into real authority.

    Shaped after `runtime.approval.FounderApprovalGate` on purpose — same
    three outcomes, same consumed-once semantics, same distinction between
    pending and denied — because a founder should not have to learn two
    approval behaviours depending on which part of the system asked.
    """

    def __init__(
        self,
        mission_control: Any,
        permissions: Any,
        timeout_seconds: float | None = None,
    ) -> None:
        self._mc = mission_control
        self._permissions = permissions
        self._timeout_seconds = timeout_seconds

    # ---- the gate ------------------------------------------------------

    def review(
        self,
        provider_id: str,
        reason_code: str,
        capability: str,
        task_id: str,
        cost: float | None = None,
        locality: str = "",
        privacy: str = "",
        objective_id: str | None = None,
        refusal: BrokerRefusal | None = None,
    ) -> str:
        """Return the approval id once authority exists; raise otherwise.

        Raises `ProviderApprovalPending` while the founder has not
        answered, and `ProviderApprovalDenied` once they have said no.
        """
        qualified = self.qualified_capability(reason_code, provider_id)
        local = LOCAL_CAPABILITY[reason_code]

        # Expiry is evaluated here rather than on a timer, for the reason
        # MB028.1 gives: whoever is asking is the system's heartbeat for
        # this question, and a second clock is a second thing to keep
        # honest.
        self._mc.expire_approvals(self._timeout_seconds)

        decided = self._decided_for(task_id, qualified)
        if decided is not None:
            state = decided.state.value
            if state == "approved":
                # The founder's answer becomes real authority, once, in the
                # one place authority lives.
                self._permissions.grant(provider_id, local, GrantScope.ONCE)
            elif state in ("rejected", "expired"):
                raise ProviderApprovalDenied(
                    self._refusal(
                        APPROVAL_DENIED,
                        "you rejected this provider for this task"
                        if state == "rejected"
                        else "the request expired before it was answered",
                        provider_id,
                        capability,
                        task_id,
                        decided.approval_id,
                        refusal,
                    )
                )

        if self._granted(provider_id, local):
            return decided.approval_id if decided is not None else ""

        existing = self._mc.approvals.find_open(task_id, qualified)
        if existing is None:
            existing = self._ask(
                provider_id=provider_id,
                reason_code=reason_code,
                qualified=qualified,
                local=local,
                capability=capability,
                task_id=task_id,
                cost=cost,
                locality=locality,
                privacy=privacy,
                objective_id=objective_id,
            )

        raise ProviderApprovalPending(
            self._refusal(
                APPROVAL_PENDING,
                f"waiting for you to approve {provider_id} for this task",
                provider_id,
                capability,
                task_id,
                existing.approval_id,
                refusal,
            )
        )

    def qualified_capability(self, reason_code: str, provider_id: str) -> str:
        return f"{QUALIFIED[reason_code]}[{provider_id}]"

    # ---- internals -----------------------------------------------------

    def _granted(self, provider_id: str, local: str) -> bool:
        """Ask the one grant ledger. A `ONCE` grant is consumed here, by
        the check that uses it — which is what makes "approved for this
        task" mean this task rather than every task like it."""
        try:
            self._permissions.check(provider_id, local, RISK_TIER)
        except Exception:  # noqa: BLE001 - any refusal is "not granted"
            return False
        return True

    def _decided_for(self, task_id: str, qualified: str) -> Any:
        """The most recent *answered* request for this exact task and
        provider. Newest first, so a fresh question always beats an old
        answer."""
        for approval in reversed(self._mc.approvals.all()):
            if (
                approval.task_id == task_id
                and approval.capability == qualified
                and not approval.is_open
            ):
                return approval
        return None

    def _ask(
        self,
        provider_id: str,
        reason_code: str,
        qualified: str,
        local: str,
        capability: str,
        task_id: str,
        cost: float | None,
        locality: str,
        privacy: str,
        objective_id: str | None,
    ) -> Any:
        approval, _is_new = self._mc.request_approval(
            PendingApproval(
                capability=qualified,
                local_capability=local,
                executive_id=provider_id,
                risk_tier=RISK_TIER.value,
                reason=HUMAN_REASON[reason_code],
                impact=describe_impact(
                    provider_id, reason_code, capability, cost, locality, privacy
                ),
                task_id=task_id,
                objective_id=objective_id,
                objective=self._objective_description(objective_id),
                requested_by=APPROVAL_REQUESTER,
            )
        )
        return approval

    def _objective_description(self, objective_id: str | None) -> str | None:
        if objective_id is None:
            return None
        try:
            for objective in self._mc.dispatcher.objectives():
                if objective.objective_id == objective_id:
                    return objective.description
        except Exception:  # noqa: BLE001 - a missing description is not a refusal
            return None
        return None

    def _refusal(
        self,
        kind: str,
        reason: str,
        provider_id: str,
        capability: str,
        task_id: str,
        approval_id: str | None,
        base: BrokerRefusal | None,
    ) -> BrokerRefusal:
        """Carry the Broker's own candidate list through the approval
        refusal, so "why this provider and not the free one" is still
        answerable while the founder is deciding."""
        return BrokerRefusal(
            kind=kind,
            reason=reason,
            capability=capability,
            task_id=task_id,
            provider_id=provider_id,
            approval_id=approval_id,
            policy_version=base.policy_version if base else "",
            rejected=base.rejected if base else (),
            entry_id=base.entry_id if base else None,
            decision=base.decision if base else None,
        )


def describe_impact(
    provider_id: str,
    reason_code: str,
    capability: str,
    cost: float | None,
    locality: str,
    privacy: str,
) -> str:
    """What saying yes actually does, in one line.

    MB028.1 put impact on every approval because a founder deciding at
    22:13 should not have to work out the consequence from a capability
    name. The same applies here, and the consequence is different for the
    two reasons: one spends money, the other discloses.
    """
    where = f"{locality or 'unknown location'}, {privacy or 'unknown privacy'}"
    if reason_code == PAID:
        return (
            f"Sends this '{capability}' work to {provider_id} ({where}) and "
            f"spends money: {describe_cost(cost)}"
        )
    return (
        f"Sends work you marked sensitive to {provider_id} ({where}). "
        "It leaves this machine and cannot be recalled"
    )
