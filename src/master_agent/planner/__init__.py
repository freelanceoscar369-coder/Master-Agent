"""Planning — an objective becomes steps, and every step says what it
expects (Mission Brief 036).

See `planner.py` for the argument. The short version: MB035 shipped a
verifier that judges an answer against an expectation *stated before the
answer arrived*, and `ExpectedOutcome` names the Planner as the thing
that states one. This is that thing.
"""
from master_agent.planner.catalogue import (
    CapabilityOption,
    catalogue_from,
    catalogue_from_index,
    names,
    render,
)
from master_agent.planner.outcomes import (
    SUCCESS_KEYS,
    MalformedSuccess,
    SuccessSpec,
)
from master_agent.planner.parsing import validate
from master_agent.planner.plan import (
    BAD_DEPENDENCY,
    BAD_PAYLOAD,
    BROKER_REFUSED,
    CYCLIC,
    MALFORMED,
    MISSING_EXPECTATION,
    NO_CAPABILITIES,
    NO_STEPS,
    NOT_JSON,
    PROVIDER_FAILED,
    UNKNOWN_CAPABILITY,
    UNVERIFIED,
    Intent,
    MissionPlan,
    PlanOutcome,
    PlanRefusal,
    Step,
)
from master_agent.planner.planner import PLANNING_CAPABILITY, Planner
from master_agent.planner.prompting import PLAN_SHAPE, build_prompt, plan_expectation

__all__ = [
    "BAD_DEPENDENCY",
    "BAD_PAYLOAD",
    "BROKER_REFUSED",
    "CYCLIC",
    "MALFORMED",
    "MISSING_EXPECTATION",
    "NOT_JSON",
    "NO_CAPABILITIES",
    "NO_STEPS",
    "PLANNING_CAPABILITY",
    "PLAN_SHAPE",
    "PROVIDER_FAILED",
    "SUCCESS_KEYS",
    "UNKNOWN_CAPABILITY",
    "UNVERIFIED",
    "CapabilityOption",
    "Intent",
    "MalformedSuccess",
    "MissionPlan",
    "PlanOutcome",
    "PlanRefusal",
    "Planner",
    "Step",
    "SuccessSpec",
    "build_prompt",
    "catalogue_from",
    "catalogue_from_index",
    "names",
    "plan_expectation",
    "render",
    "validate",
]
