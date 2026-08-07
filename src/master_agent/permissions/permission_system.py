"""Permission System — the human-approval gate. See ARCHITECTURE.md §4.4.

This module has veto power over the Orchestrator. It does not execute
anything itself; it only answers "is this step allowed to run right now,"
and if not, how to ask the human for a decision.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

# PermissionCategory lives in plugins/base.py, alongside RiskTier — see
# that module for why (the same reason RiskTier does: plugins/Actions
# declare it about themselves, and this module consumes it, so it belongs
# with the contract being described, not with the system enforcing it).
# Re-exported here for convenience so permission-related code can import
# it from either module without ambiguity about which is canonical.
from master_agent.plugins.base import (
    PermissionCategory,  # noqa: F401
    RiskTier,
)


class GrantScope(str, Enum):
    ONCE = "once"
    THIS_SESSION = "this_session"
    ALWAYS_FOR_CAPABILITY = "always_for_capability"


@dataclass(frozen=True)
class PermissionGrant:
    plugin_name: str
    capability: str
    scope: GrantScope


class ApprovalRequired(Exception):
    """Raised by check() when a step needs a human decision before it can
    proceed. The Mission Manager should catch this, transition the mission
    to `awaiting_approval`, and surface the request via voice/UI — it
    should never be silently swallowed.
    """

    def __init__(self, plugin_name: str, capability: str, risk_tier: RiskTier) -> None:
        self.plugin_name = plugin_name
        self.capability = capability
        self.risk_tier = risk_tier
        super().__init__(
            f"approval required: {plugin_name}.{capability} ({risk_tier.value})"
        )


class PermissionSystem:
    def __init__(self) -> None:
        self._grants: set[PermissionGrant] = set()

    def grant(self, plugin_name: str, capability: str, scope: GrantScope) -> None:
        self._grants.add(PermissionGrant(plugin_name, capability, scope))

    def revoke_session_grants(self) -> None:
        self._grants = {g for g in self._grants if g.scope == GrantScope.ALWAYS_FOR_CAPABILITY}

    def check(self, plugin_name: str, capability: str, risk_tier: RiskTier) -> None:
        """Raises ApprovalRequired if this invocation is not covered by an
        existing grant. Callers (the Orchestrator) must not proceed past a
        raised ApprovalRequired without a fresh grant being recorded first.

        A ONCE grant is consumed here — found and removed atomically with
        the check — so it covers exactly the one invocation it was given
        for. Without this, a single approval would silently authorize
        every future call to the same capability, which defeats the point
        of scoping it to "once" in the first place.
        """
        if risk_tier == RiskTier.READ_ONLY:
            return

        # Destructive actions require a real, current decision every
        # time a standing blanket grant isn't present -- an
        # ALWAYS_FOR_CAPABILITY grant never satisfies an IRREVERSIBLE
        # check, no matter how it was created. Nothing in this codebase
        # currently offers a human the option to create one (every live
        # approval flow only ever grants ONCE), so this is defensive
        # enforcement ahead of that UI existing, not a reaction to a real
        # incident -- see FILESYSTEM_CAPABILITIES.md §5.
        def _usable(grant: PermissionGrant) -> bool:
            if risk_tier == RiskTier.IRREVERSIBLE and grant.scope == GrantScope.ALWAYS_FOR_CAPABILITY:
                return False
            return True

        match = next(
            (
                g
                for g in self._grants
                if g.plugin_name == plugin_name and g.capability == capability and _usable(g)
            ),
            None,
        )
        if match is None:
            raise ApprovalRequired(plugin_name, capability, risk_tier)
        if match.scope == GrantScope.ONCE:
            self._grants.discard(match)
