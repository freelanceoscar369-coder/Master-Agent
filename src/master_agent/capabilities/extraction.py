"""Reading contracts out of the code that already declares them
(Mission Brief 039 Stage A3).

Every `Action` in this codebase already states its name, description,
risk tier, permission category, expected result and required parameters.
None of that reached the Planner, which is why MB037's first live plan
named `path` where `CreateFolder` requires `name`.

**Nothing here is hand-written per capability.** A contract is derived
from the Action object, so adding a capability adds a contract and the
two cannot drift. A hand-maintained table would be a second source of
truth that is wrong the first time somebody renames an argument.

## What extraction can and cannot know

`required_parameters()` publishes **names**. It does not publish types,
optional arguments, or return shapes. So an extracted contract says:

- `inputs.known = True` — the required names are genuinely known
- `inputs.closed = False` — optional arguments exist and are not listed
- every field `type = UNKNOWN` — no type was declared anywhere
- `outputs = Schema.unknown()` — `expected_result` is a sentence, not a
  shape

That is a smaller claim than a hand-written schema and a true one. It is
also enough to fix the defect: the Planner now learns that the argument
is called `name`.
"""
from __future__ import annotations

from typing import Any

from master_agent.capabilities.contract import (
    SIDE_EFFECT_BY_RISK,
    UNKNOWN,
    CapabilityContract,
    FieldSpec,
    Permissions,
    Schema,
    Version,
)

#: The contract version an extracted contract carries. Extraction is
#: mechanical, so every contract it produces is the same generation of
#: the same process -- this is the *extractor's* version, not a claim
#: about the Action's stability.
EXTRACTED_VERSION = Version(1, 0, 0)

#: How a contract says where it came from. Recorded so a later,
#: hand-authored or build-time manifest can be told apart from one
#: derived by reflection.
SOURCE_ACTION = "action"


def _text(value: Any) -> str:
    return str(value).strip() if value else ""


def contract_from_action(
    action: Any, canonical_id: str, domain: str
) -> CapabilityContract:
    """One Action, as a contract.

    `canonical_id` and `domain` are supplied rather than computed: Mission
    Control already owns the qualified-name rule (`Filesystem.CreateFolder`)
    and reproducing it here would create a second naming authority that
    could disagree with the first.
    """
    risk = _enum_value(getattr(action, "risk_tier", None))
    category = _enum_value(getattr(action, "permission_category", None))

    try:
        required = tuple(action.required_parameters() or ())
    except Exception:  # noqa: BLE001 - an Action that cannot describe itself
        # is a capability with an unknown shape, not a crash. Reflection is
        # best-effort by nature and one bad Action must not empty the
        # registry.
        required = ()
        inputs = Schema.unknown()
    else:
        inputs = Schema(
            fields=tuple(
                FieldSpec(name=name, type=UNKNOWN, required=True) for name in required
            ),
            # The required names are genuinely known...
            known=True,
            # ...but optional arguments exist and are not published, so
            # this list is not exhaustive and an unlisted key is not an
            # error. `location` on `CreateFolder` is exactly this case.
            closed=False,
        )

    return CapabilityContract(
        canonical_id=canonical_id,
        version=EXTRACTED_VERSION,
        domain=domain,
        category=category or UNKNOWN,
        inputs=inputs,
        # `expected_result` is a sentence written for a human. It is not a
        # shape, and reading it as one would be exactly the prose-parsing
        # MB039 exists to remove.
        outputs=Schema.unknown(),
        permissions=Permissions(
            risk_tier=risk or UNKNOWN,
            category=category or UNKNOWN,
            # The rule the Permission System applies, restated rather than
            # re-decided: anything above READ_ONLY stops for the founder
            # (MB028.0).
            approval_required=bool(risk) and risk != "read_only",
        ),
        side_effect=SIDE_EFFECT_BY_RISK.get(risk or "", UNKNOWN),
        # Deliberately not derived. Nothing in an Action declares how long
        # it takes, whether it is safe to repeat, or whether calling it
        # twice differs from calling it once.
        latency_class=UNKNOWN,
        retryability=UNKNOWN,
        idempotency=UNKNOWN,
        summary=_text(getattr(action, "description", "")),
        metadata={
            "source": SOURCE_ACTION,
            "local_name": _text(getattr(action, "name", "")),
            # Kept as prose, in metadata, where nothing reads it to make a
            # decision -- the honest home for a sentence.
            "expected_result": _text(getattr(action, "expected_result", "")),
        },
    )


def _enum_value(value: Any) -> str:
    """`RiskTier.READ_ONLY` -> `"read_only"`. Handles a plain string too,
    because a manifest may carry either."""
    if value is None:
        return ""
    return str(getattr(value, "value", value))


def contracts_from_actions(
    actions: dict[str, Any], executive_id: str, qualify: Any
) -> tuple[CapabilityContract, ...]:
    """Every Action a plugin exposes, as contracts.

    `qualify(executive_id, local_name)` is Mission Control's own naming
    function, passed in rather than imported: this package describes
    capabilities and must not acquire a dependency on the frozen registry
    that indexes them.
    """
    return tuple(
        contract_from_action(action, qualify(executive_id, local_name), executive_id)
        for local_name, action in sorted(actions.items())
    )
