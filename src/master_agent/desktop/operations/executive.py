"""`DesktopExecutiveV2` — the elite layer, assembled.

```
   catalog.py            (what applications exist, C1–C30 territory)
        │
        ▼
   knowledge.py           (how to operate each one — this brief)
        │
        ▼
   OperationKnowledgeBase (the aggregate: profiles + recovery + workflows + matrix)
        │
        ▼
   DesktopExecutiveV2     (read-only facade + the one algorithm: recommend())
        │
        ▼
   Founder Edition / Environment Intelligence — consumers, never callers of execution
```

**Everything below `catalog.py` in this diagram is knowledge, and only
knowledge.** `DesktopExecutiveV2` holds no probe, no executor, no
`Action`, and is never registered as a Mission Control capability —
unlike `desktop.plugin.DesktopPlugin`, which *is* execution-capable and is
untouched by this brief. A founder can ask this facade *"how would you
operate Chrome?"* and get an answer; asking it to *do* anything is not a
method this class has.

## `recommend()` is the one place a graded conclusion is produced

Every other read here is a direct lookup — a profile, a recovery plan, a
capability list — carried, never derived. `recommend()` is the exception,
and it is exactly the question the brief asks Environment Intelligence to
be able to answer: *"Which application should perform this task? Why?
Confidence? Fallback?"* It answers by reusing C22's own
`Inference`/`Confidence`/`Evidence` vocabulary rather than inventing a
parallel one, and it reads facts only from a `MachineInventory` a caller
supplies — never a probe of its own, and never a second scan.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from master_agent.desktop.inventory import MachineInventory
from master_agent.desktop.operations.knowledge import (
    MATRIX,
    PROFILES,
    RECOVERY_PLANS,
    WORKFLOWS,
)
from master_agent.desktop.operations.types import (
    AI_CAPABILITIES,
    ApplicationOperationProfile,
    ApplicationRecoveryPlan,
    Capability,
    DesktopCapabilityMatrix,
    InvalidOperationKnowledge,
    Workflow,
)
from master_agent.environment_intelligence import (
    Confidence,
    EnvironmentIntelligence,
    Evidence,
    Inference,
    unknown,
)


@dataclass(frozen=True)
class OperationKnowledgeBase:
    """Every piece of authored knowledge, in one immutable value. Pure
    data — assembling it performs no lookup against a machine and no
    derivation; it is exactly what `knowledge.py` declared, held together.
    """

    profiles: tuple[ApplicationOperationProfile, ...]
    recovery_plans: tuple[ApplicationRecoveryPlan, ...]
    workflows: tuple[Workflow, ...]
    matrix: DesktopCapabilityMatrix

    def __post_init__(self) -> None:
        profile_keys = [p.key for p in self.profiles]
        if len(set(profile_keys)) != len(profile_keys):
            raise InvalidOperationKnowledge("a profile key must not repeat")
        recovery_keys = [r.key for r in self.recovery_plans]
        if len(set(recovery_keys)) != len(recovery_keys):
            raise InvalidOperationKnowledge("a recovery plan key must not repeat")

    def profile(self, key: str) -> ApplicationOperationProfile | None:
        for candidate in self.profiles:
            if candidate.key == key:
                return candidate
        return None

    def recovery_plan(self, key: str) -> ApplicationRecoveryPlan | None:
        for candidate in self.recovery_plans:
            if candidate.key == key:
                return candidate
        return None

    def workflows_for(self, key: str) -> tuple[Workflow, ...]:
        return tuple(w for w in self.workflows if w.key == key)

    def profiled_keys(self) -> tuple[str, ...]:
        return tuple(p.key for p in self.profiles)

    def as_dict(self) -> dict[str, Any]:
        return {
            "profiles": {p.key: p.as_dict() for p in self.profiles},
            "recovery_plans": {r.key: r.as_dict() for r in self.recovery_plans},
            "workflows": [w.as_dict() for w in self.workflows],
            "matrix": self.matrix.as_dict(),
        }


#: The knowledge base built from this brief's own authored data. A module
#: constant, the same way `desktop.catalog.CATALOG` and `desktop.catalog
#: .BY_KEY` are module constants — one knowledge base, never rebuilt per
#: call, and never a second one instantiated with different data.
KNOWLEDGE_BASE = OperationKnowledgeBase(
    profiles=PROFILES,
    recovery_plans=RECOVERY_PLANS,
    workflows=WORKFLOWS,
    matrix=MATRIX,
)


@dataclass(frozen=True)
class ApplicationRecommendation:
    """*"Which application, why, how confident, and what else could work"*
    — the brief's four questions, structurally. `choice` is an `Inference`
    (C22's own type): its `.value` is the recommended application's key,
    or `None` when nothing here is confident enough to name one, and its
    `.reason`/`.evidence` are never absent, even then."""

    capability: Capability
    choice: Inference
    fallback: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "capability": self.capability.value,
            "choice": self.choice.as_dict(),
            "fallback": list(self.fallback),
        }


class DesktopExecutiveV2:
    """Read-only. Every method either looks up authored knowledge or
    reasons over a `MachineInventory` a caller already holds — never a
    probe, never a scan, never an action."""

    __slots__ = ("_kb",)

    def __init__(self, knowledge_base: OperationKnowledgeBase = KNOWLEDGE_BASE) -> None:
        if not isinstance(knowledge_base, OperationKnowledgeBase):
            raise TypeError(
                "DesktopExecutiveV2 takes an OperationKnowledgeBase; there "
                "is no other way to hold operational knowledge"
            )
        self._kb = knowledge_base

    @property
    def knowledge_base(self) -> OperationKnowledgeBase:
        return self._kb

    def profile(self, key: str) -> ApplicationOperationProfile | None:
        return self._kb.profile(key)

    def recovery_plan(self, key: str) -> ApplicationRecoveryPlan | None:
        return self._kb.recovery_plan(key)

    def workflows(self, key: str) -> tuple[Workflow, ...]:
        return self._kb.workflows_for(key)

    def capability_matrix(self) -> DesktopCapabilityMatrix:
        return self._kb.matrix

    def recommend(
        self,
        capability: Capability,
        inventory: MachineInventory | None = None,
        environment: EnvironmentIntelligence | None = None,
    ) -> ApplicationRecommendation:
        """Which application should perform a task requiring `capability`.

        Reasoning, in order, and every step is auditable:

        1. **No candidate is known** → `UNKNOWN`, naming the capability.
        2. **No inventory supplied** → `UNKNOWN`; nothing here can say
           what is actually installed without one, and this function
           performs no scan of its own.
        3. **Exactly one candidate is installed and healthy** →
           `OBSERVED` — the inventory says so directly.
        4. **Several candidates are installed and healthy** → `STRONG` —
           multiple independent facts agree the capability is available.
           The one named is the first in the matrix's own declared
           order, unless `environment` narrows it (below); every other
           healthy candidate is named in `fallback`, not silently
           dropped.
        5. **Exactly one candidate is installed but reported unhealthy,
           and nothing healthy exists** → `WEAK` — one indirect,
           qualified fact.
        6. **Nothing is installed at all** → `UNKNOWN`, naming how many
           candidates were checked.

        For the AI capabilities (`AI_CAPABILITIES`), when several
        candidates tie at step 4 and `environment` is supplied with a
        known `ai.preferred`, that already-derived C22 preference breaks
        the tie — reusing C22's own conclusion rather than recomputing
        one, per the brief's *"integrate with C22"* instruction.
        """
        if not isinstance(capability, Capability):
            raise TypeError("recommend() takes a Capability")
        if inventory is not None and not isinstance(inventory, MachineInventory):
            raise TypeError("inventory must be a MachineInventory, or omitted")
        if environment is not None and not isinstance(
            environment, EnvironmentIntelligence
        ):
            raise TypeError(
                "environment must be an EnvironmentIntelligence, or omitted"
            )

        candidates = self._kb.matrix.providers_of(capability)
        if not candidates:
            return ApplicationRecommendation(
                capability=capability,
                choice=unknown(
                    f"no application in the operation knowledge base is "
                    f"known to offer {capability.value}"
                ),
            )

        if inventory is None:
            return ApplicationRecommendation(
                capability=capability,
                choice=unknown(
                    "no machine inventory was supplied; nothing here can "
                    "say which candidate is actually installed without one"
                ),
                fallback=candidates,
            )

        healthy: list[str] = []
        installed_unhealthy: list[str] = []
        for key in candidates:
            application = inventory.get(key)
            if application is None or not application.installed:
                continue
            (healthy if application.healthy else installed_unhealthy).append(key)

        if len(healthy) >= 2:
            chosen = _prefer(healthy, capability, environment)
            evidence = tuple(
                Evidence(
                    source=f"machine_inventory.applications[{key}]",
                    fact=f"{key} is installed and healthy",
                )
                for key in healthy
            )
            reason = (
                f"{len(healthy)} candidates for {capability.value} are "
                f"installed and healthy; {chosen} is chosen"
            )
            if chosen != healthy[0]:
                reason += " — the environment's own AI preference (C22) breaks the tie"
            else:
                reason += " by the operation knowledge base's declared priority order"
            choice = Inference(
                value=chosen,
                confidence=Confidence.STRONG,
                reason=reason,
                evidence=evidence,
            )
            fallback = tuple(k for k in candidates if k != chosen)
            return ApplicationRecommendation(capability, choice, fallback)

        if len(healthy) == 1:
            chosen = healthy[0]
            choice = Inference(
                value=chosen,
                confidence=Confidence.OBSERVED,
                reason=(
                    f"{chosen} is the only candidate for {capability.value} "
                    "that is installed and healthy"
                ),
                evidence=(
                    Evidence(
                        source=f"machine_inventory.applications[{chosen}]",
                        fact=f"{chosen} is installed and healthy",
                    ),
                ),
            )
            fallback = tuple(k for k in candidates if k != chosen)
            return ApplicationRecommendation(capability, choice, fallback)

        if installed_unhealthy:
            chosen = installed_unhealthy[0]
            choice = Inference(
                value=chosen,
                confidence=Confidence.WEAK,
                reason=(
                    f"{chosen} is installed but reported unhealthy; it is "
                    f"the only candidate present for {capability.value}"
                ),
                evidence=(
                    Evidence(
                        source=f"machine_inventory.applications[{chosen}]",
                        fact=f"{chosen} is installed but reported unhealthy",
                    ),
                ),
            )
            fallback = tuple(k for k in candidates if k != chosen)
            return ApplicationRecommendation(capability, choice, fallback)

        return ApplicationRecommendation(
            capability=capability,
            choice=unknown(
                f"none of the {len(candidates)} candidate application(s) "
                f"for {capability.value} is installed"
            ),
            fallback=candidates,
        )


def _prefer(
    healthy: list[str],
    capability: Capability,
    environment: EnvironmentIntelligence | None,
) -> str:
    """Break a tie among several healthy candidates. C22's own `ai
    .preferred` is consulted only for AI capabilities and only when it
    names one of the tied candidates — otherwise the matrix's own
    declared order stands, which is `healthy[0]`."""
    if capability not in AI_CAPABILITIES or environment is None:
        return healthy[0]
    preferred = environment.ai.preferred
    if preferred is not None and preferred.known and preferred.value in healthy:
        return preferred.value
    return healthy[0]
