"""Reading a plan out of what a provider said (Mission Brief 036).

Everything here is deterministic and structural. Nothing in this module
judges whether a plan is a *good* plan -- it decides whether what came
back is a plan at all, which is a question with a right answer.

## There is no parser here

`validate()` takes an already-parsed document, and the Planner gets that
document from `Evidence.observation["json"]` -- the value MB035's
`observe()` produced while judging the reply. That is deliberate. If this
module parsed the text a second time, the artefact that was *verified*
and the artefact that gets *executed* would be two objects that merely
usually agree, and the day they disagreed nothing would notice. Reading
the verifier's own observation makes that class of bug unrepresentable,
and it is a published field: `Evidence.observation` is documented as a
plain JSON-shaped dict precisely so consumers other than the Verifier can
read it. Fence unwrapping, likewise, already happens once, in MB035's
`_as_json`, and once is the right number of times.
"""
from __future__ import annotations

from typing import Any

from master_agent.planner import outcomes
from master_agent.planner.catalogue import CapabilityOption, names
from master_agent.capabilities.input_bindings import (
    MalformedBinding,
    bindings_from_dict,
)
from master_agent.planner.plan import (
    BAD_DEPENDENCY,
    BAD_PAYLOAD,
    COMPLEXITIES,
    CYCLIC,
    DEFAULT_COMPLEXITY,
    DEFAULT_PRIORITY,
    MALFORMED,
    MISSING_EXPECTATION,
    NO_STEPS,
    PRIORITIES,
    UNKNOWN_CAPABILITY,
    MissionPlan,
    PlanRefusal,
    Step,
)


def _malformed(detail: str) -> PlanRefusal:
    return PlanRefusal(
        code=MALFORMED,
        reason="the provider's plan was not shaped like a plan",
        detail=detail,
    )


def _vocabulary(
    value: Any,
    allowed: tuple[str, ...],
    default: str,
    key: str,
    step_id: str,
) -> tuple[str, PlanRefusal | None]:
    """One of a closed set, or the default when the provider said nothing.

    Absence is not a failure -- MB036's plan shape did not have these two
    keys, and a plan written against it is still a valid plan. A *wrong*
    value is a failure, because silently substituting the default would
    tell a founder the step is `normal` priority when the provider said
    `urgent`, and that is a lie about what was planned.
    """
    if value is None:
        return default, None
    if isinstance(value, str) and value.strip().lower() in allowed:
        return value.strip().lower(), None
    return default, _malformed(
        f"step `{step_id}`: `{key}` must be one of {', '.join(allowed)}"
    )


def _option_named(capability: str, options: Any) -> Any:
    """The catalogue entry for this capability, or a stand-in with no
    required arguments.

    A stand-in rather than a raise: a capability the catalogue does not
    describe has published no requirements, and inventing some would be
    the fabrication this brief exists to remove.
    """
    for option in options or ():
        if option.name == capability:
            return option
    return CapabilityOption(name=capability)


def _read_step(
    entry: Any, index: int, allowed: tuple[str, ...], options: Any = (),
    source_capabilities: dict[str, str] | None = None,
) -> tuple[Step | None, PlanRefusal | None]:
    if not isinstance(entry, dict):
        return None, _malformed(f"step {index + 1} is not an object")

    step_id = entry.get("id")
    if not isinstance(step_id, str) or not step_id.strip():
        return None, _malformed(f"step {index + 1} has no usable `id`")
    step_id = step_id.strip()

    capability = entry.get("capability")
    if not isinstance(capability, str) or not capability.strip():
        return None, _malformed(f"step `{step_id}` names no capability")
    capability = capability.strip()

    # Which founder requirements this step claims responsibility for.
    #
    # A CLAIM, never proof -- Evidence still decides reality (ADR-0026).
    # Read permissively and never fatal: a plan that omits it is the
    # plan Kalpavriksha built for a year, and refusing it here would turn
    # a reporting gap into an inability to act at all. What it costs
    # instead is honest: conformance reports UNKNOWN for a requirement no
    # step took responsibility for, which is exactly true.
    covers = tuple(
        str(item).strip()
        for item in (entry.get("covers") or ())
        if isinstance(item, (str, int)) and str(item).strip()
    )
    if capability not in allowed:
        return None, PlanRefusal(
            code=UNKNOWN_CAPABILITY,
            reason=f"the plan names a capability that does not exist: {capability}",
            detail=(
                f"step `{step_id}` asks for `{capability}`, which is not "
                "registered. A plan is only executable if every capability "
                "in it is real."
            ),
            known_capabilities=allowed,
        )

    payload = entry.get("payload", {})
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        return None, _malformed(f"step `{step_id}`: `payload` must be an object")

    raw_depends = entry.get("depends_on", [])
    if raw_depends is None:
        raw_depends = []
    if isinstance(raw_depends, str):
        raw_depends = [raw_depends]
    if not isinstance(raw_depends, list) or any(
        not isinstance(item, str) or not item.strip() for item in raw_depends
    ):
        return None, _malformed(f"step `{step_id}`: `depends_on` must be a list of step ids")
    depends_on = [item.strip() for item in raw_depends]

    priority, problem = _vocabulary(
        entry.get("priority"), PRIORITIES, DEFAULT_PRIORITY, "priority", step_id
    )
    if problem is not None:
        return None, problem

    complexity, problem = _vocabulary(
        entry.get("complexity"), COMPLEXITIES, DEFAULT_COMPLEXITY, "complexity", step_id
    )
    if problem is not None:
        return None, problem

    # MB039. The payload is checked against the capability's published
    # required arguments *before* the plan is submitted. Names only --
    # whether the folder already exists is the Action's `validate()`, run
    # against the real world. This catches the class of error that made
    # MB037's plan unrunnable: right capability, wrong argument name.
    option = _option_named(capability, options)

    # ---- declared input bindings ------------------------------------
    #
    # A value produced by an earlier step, named rather than predicted.
    # Validated here so a plan that would guess is refused before a
    # mission exists, not discovered when a file already holds the wrong
    # text.
    try:
        bindings = bindings_from_dict(entry.get("input_bindings"))
    except MalformedBinding as exc:
        return None, _malformed(f"step `{step_id}`: {exc}")

    known_args = set(getattr(option, "required_args", ()) or ()) | set(
        getattr(option, "optional_args", ()) or ()
    )
    for target, binding in bindings.items():
        if target in payload:
            # Two authorities for one argument. Refused rather than
            # resolved by precedence -- a precedence rule is how a
            # predicted literal quietly wins over an observed value.
            return None, PlanRefusal(
                code=BAD_PAYLOAD,
                reason="a step set the same argument twice",
                detail=(
                    f"step `{step_id}` gives `{target}` both a literal value "
                    f"and an input binding. Exactly one may decide it."
                ),
            )
        if getattr(option, "args_complete", False) and target not in known_args:
            return None, PlanRefusal(
                code=BAD_PAYLOAD,
                reason="a step bound an argument its capability does not accept",
                detail=(
                    f"step `{step_id}` binds `{target}`, which `{capability}` "
                    f"does not publish. It accepts: "
                    f"{', '.join(sorted(known_args)) or 'nothing'}."
                ),
            )
        for ref in binding.references:
            source_capability = (source_capabilities or {}).get(ref.step_id)
            if source_capability is not None:
                source_option = _option_named(source_capability, options)
                published = tuple(getattr(source_option, "output_fields", ()) or ())
                if not published:
                    # The capability has published no result shape, so any
                    # field name here would be the Planner guessing a key.
                    # Unknown is refused rather than attempted.
                    return None, PlanRefusal(
                        code=BAD_PAYLOAD,
                        reason="a step binds to a capability that publishes no outputs",
                        detail=(
                            f"step `{step_id}` reads `{ref.field}` from "
                            f"`{ref.step_id}` (`{source_capability}`), which "
                            f"declares no output fields."
                        ),
                    )
                if ref.field.split(".")[0] not in published:
                    return None, PlanRefusal(
                        code=BAD_PAYLOAD,
                        reason="a step binds to an output field that is not published",
                        detail=(
                            f"step `{step_id}` reads `{ref.field}` from "
                            f"`{ref.step_id}`, which publishes: "
                            f"{', '.join(published)}."
                        ),
                    )
            if ref.step_id not in depends_on:
                # `depends_on` is the single execution-order authority, so
                # it is never auto-extended here: a binding may read a
                # dependency, not create one.
                return None, PlanRefusal(
                    code=BAD_DEPENDENCY,
                    reason="a step reads a value from a step it does not depend on",
                    detail=(
                        f"step `{step_id}` binds `{target}` from `{ref.step_id}`, "
                        f"which is not in its `depends_on`."
                    ),
                )

    # A required argument is satisfied by a literal OR by a binding.
    # Checking only the payload would refuse the very plans this contract
    # exists to allow.
    supplied = set(payload) | set(bindings)
    missing = [
        arg for arg in getattr(option, "required_args", ()) if arg not in supplied
    ]
    if missing:
        return None, PlanRefusal(
            code=BAD_PAYLOAD,
            reason=f"a step is missing arguments its capability requires: {capability}",
            detail=(
                f"step `{step_id}` calls `{capability}` without "
                + ", ".join(f"`{name}`" for name in missing)
                + f". It requires: {', '.join(option.required_args)}."
                + (
                    f" It was given: {', '.join(sorted(payload))}."
                    if payload
                    else " It was given nothing."
                )
            ),
        )

    try:
        spec = outcomes.from_document(entry.get("success"), step_id=step_id)
    except outcomes.MalformedSuccess as exc:
        # Constitution §3.2, enforced. A step with no stated expectation
        # is not a cheaper step, it is an unverifiable one -- and MB035
        # exists precisely so that stops being acceptable.
        return None, PlanRefusal(
            code=MISSING_EXPECTATION,
            reason="a step did not state what success looks like",
            detail=str(exc),
        )

    return (
        Step(
            step_id=step_id,
            capability=capability,
            payload=payload,
            depends_on=depends_on,
            expected_outcome=spec.to_expected_outcome(),
            input_bindings={t: b.as_dict() for t, b in bindings.items()},
            # What the founder asked to see before this step runs. Read as
            # plain text and trimmed; absent for almost every step, which
            # is the point -- a checkpoint exists only because an
            # objective asked for one.
            founder_checkpoint=str(entry.get("founder_checkpoint") or "").strip(),
            priority=priority,
            estimated_complexity=complexity,
            covers=covers,
        ),
        None,
    )


def _ordered(steps: list[Step]) -> tuple[list[Step] | None, PlanRefusal | None]:
    """Kahn's algorithm, ties broken by declaration order.

    The Orchestrator walks `plan.steps` in list order, so a plan whose
    dependencies are only *declared* would execute out of order. Sorting
    here makes the list itself the execution order -- and the tie-break
    keeps it deterministic, so the same plan document always yields the
    same sequence rather than one that depends on dict iteration.
    """
    by_id = {step.step_id: step for step in steps}
    remaining = {step.step_id: set(step.depends_on) for step in steps}
    order: list[Step] = []

    while remaining:
        ready = [
            step.step_id
            for step in steps
            if step.step_id in remaining and not remaining[step.step_id]
        ]
        if not ready:
            stuck = ", ".join(sorted(remaining))
            return None, PlanRefusal(
                code=CYCLIC,
                reason="the plan's steps depend on each other in a circle",
                detail=f"no step can start; involved: {stuck}",
            )
        for step_id in ready:
            order.append(by_id[step_id])
            del remaining[step_id]
        for pending in remaining.values():
            pending.difference_update(ready)

    return order, None


def validate(
    document: Any,
    options: tuple[CapabilityOption, ...] | list[CapabilityOption],
    objective: str = "",
    requirements: Any = (),
) -> tuple[MissionPlan | None, PlanRefusal | None]:
    """Turn a parsed plan document into a `MissionPlan`, or explain why
    it is not one. Never raises, never returns a partial plan.

    `requirements` are the founder's, already derived by the Intent
    Layer. They are carried onto the plan rather than re-derived here:
    the deterministic lanes in `planner/direct.py` published them and
    this path did not, so an AI-planned mission reached execution,
    Verification and the Reporter with nothing to conform against.
    Passing them through is not a second semantic authority -- it is the
    absence of one.
    """
    if not isinstance(document, dict):
        return None, _malformed("the reply was not a JSON object")

    raw_steps = document.get("steps")
    if not isinstance(raw_steps, list):
        return None, _malformed("`steps` is missing or is not a list")

    if not raw_steps:
        # Rule 6 of the prompt: the honest answer to an objective the
        # catalogue cannot reach. Reported as a refusal with its own code
        # rather than as an empty plan, because an empty plan submitted to
        # the Runtime would complete instantly and report success.
        return None, PlanRefusal(
            code=NO_STEPS,
            reason="no plan: the available capabilities cannot achieve this objective",
            detail=(
                "The provider was given the full catalogue and returned no "
                "steps, which is the answer it is asked to give rather than "
                "inventing a capability."
            ),
            known_capabilities=names(options),
        )

    allowed = names(options)
    steps: list[Step] = []
    seen: set[str] = set()

    # Which capability each step id calls, read once up front so a binding
    # can be checked against the SOURCE capability's published outputs.
    # A step may only bind to a field the producing capability declares --
    # otherwise the Planner is guessing a result key, which is the same
    # class of invention this whole contract removes.
    source_capabilities: dict[str, str] = {}
    for entry in raw_steps:
        if isinstance(entry, dict):
            step_id = entry.get("id") or entry.get("step_id")
            capability = entry.get("capability")
            if isinstance(step_id, str) and isinstance(capability, str):
                source_capabilities[step_id.strip()] = capability.strip()

    for index, entry in enumerate(raw_steps):
        step, refusal = _read_step(
            entry, index, allowed, options, source_capabilities=source_capabilities,
        )
        # Narrowed on the step rather than the refusal: the two are always
        # paired, and this way a type checker sees it without an `assert`
        # that would vanish under `python -O`.
        if step is None:
            return None, refusal
        if step.step_id in seen:
            return None, _malformed(f"two steps share the id `{step.step_id}`")
        seen.add(step.step_id)
        steps.append(step)

    for step in steps:
        if step.step_id in step.depends_on:
            return None, PlanRefusal(
                code=BAD_DEPENDENCY,
                reason="a step depends on itself",
                detail=f"step `{step.step_id}` lists its own id in `depends_on`",
            )
        for dependency in step.depends_on:
            if dependency not in seen:
                return None, PlanRefusal(
                    code=BAD_DEPENDENCY,
                    reason="a step depends on one that does not exist",
                    detail=(
                        f"step `{step.step_id}` waits for `{dependency}`, "
                        "which is not in the plan"
                    ),
                )

    ordered, refusal = _ordered(steps)
    if ordered is None:
        return None, refusal

    return MissionPlan(
        steps=ordered, objective=objective, requirements=tuple(requirements or ())
    ), None
