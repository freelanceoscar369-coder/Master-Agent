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

from copy import deepcopy
from typing import Any

from master_agent.capabilities.input_bindings import (
    MalformedBinding,
    bindings_from_dict,
)
from master_agent.planner import outcomes
from master_agent.planner.catalogue import CapabilityOption, names
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


def normalise_plan_document(document: Any) -> Any:
    """Canonicalise only representation variants with one meaning.

    Provider JSON is not authoritative until semantic validation accepts
    it.  This function therefore repairs punctuation-level shape drift and
    nothing else: it never chooses a capability, requirement, dependency,
    argument, output field, or success condition.

    Accepted equivalences are deliberately closed:

    * a bare list is the value of ``steps``;
    * a single step object is a one-element ``steps`` list;
    * a sole ``plan``/``mission_plan``/``result`` wrapper is transparent;
    * one ``steps`` object is a one-element list; and
    * one ``covers`` id is a one-element list.

    Ambiguous wrappers and every semantic error remain untouched for the
    existing validator to reject precisely.
    """
    copied = deepcopy(document)

    if isinstance(copied, list):
        copied = {"steps": copied}
    elif isinstance(copied, dict) and "steps" not in copied:
        wrapper_keys = tuple(
            key for key in ("plan", "mission_plan", "result")
            if key in copied
        )
        if len(copied) == 1 and len(wrapper_keys) == 1:
            nested = copied[wrapper_keys[0]]
            if isinstance(nested, (dict, list)):
                return normalise_plan_document(nested)
        elif (
            isinstance(copied.get("id"), str)
            and isinstance(copied.get("capability"), str)
        ):
            copied = {"steps": [copied]}

    if not isinstance(copied, dict):
        return copied

    raw_steps = copied.get("steps")
    if isinstance(raw_steps, dict):
        raw_steps = [raw_steps]
        copied["steps"] = raw_steps
    if not isinstance(raw_steps, list):
        return copied

    for entry in raw_steps:
        if not isinstance(entry, dict):
            continue
        covers = entry.get("covers")
        if isinstance(covers, (str, int)):
            entry["covers"] = [covers]
    return copied


def materialise_binding_dependencies(document: Any) -> Any:
    """Copy a provider plan and make its already-declared dataflow explicit.

    A ``from_step`` binding says unambiguously that its consumer cannot run
    before the named producer.  Providers repeatedly emitted that dataflow
    correctly while omitting the same id from ``depends_on``; asking more
    providers to restate the graph cost twelve calls in a live Founder
    Research mission and still produced no mission.

    This is representation normalisation, not planning: it never chooses a
    source, field, capability or order that the binding did not already
    state.  The returned document is a deep copy so the verified Evidence
    observation remains immutable.  Malformed bindings are left for
    :func:`validate` to refuse through its existing precise path.
    """
    copied = normalise_plan_document(document)
    if not isinstance(copied, dict) or not isinstance(copied.get("steps"), list):
        return copied
    for entry in copied["steps"]:
        if not isinstance(entry, dict):
            continue
        raw_depends = entry.get("depends_on", [])
        if raw_depends is None:
            raw_depends = []
        if isinstance(raw_depends, str):
            raw_depends = [raw_depends]
        if not isinstance(raw_depends, list):
            continue
        try:
            bindings = bindings_from_dict(entry.get("input_bindings"))
        except MalformedBinding:
            continue
        depends = list(raw_depends)
        for binding in bindings.values():
            for reference in binding.references:
                if reference.step_id not in depends:
                    depends.append(reference.step_id)
        entry["depends_on"] = depends
    return copied


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

    # The field the Founder asked to receive, when this step produces it.
    # This is a designation, not proof: Mission Control reads the value only
    # from matched Evidence after execution.  The capability contract still
    # bounds what may be named, so a provider cannot invent a result field.
    raw_answer = entry.get("answers_founder")
    if raw_answer is None:
        answers_founder = ""
    elif not isinstance(raw_answer, str):
        return None, _malformed(
            f"step `{step_id}`: `answers_founder` must be a dot-path string"
        )
    else:
        answers_founder = raw_answer.strip()
    if answers_founder:
        published = tuple(getattr(option, "output_fields", ()) or ())
        root = answers_founder.split(".", 1)[0]
        if root not in published:
            return None, PlanRefusal(
                code=BAD_PAYLOAD,
                reason="a step designates an answer field that is not published",
                detail=(
                    f"step `{step_id}` designates `{answers_founder}`, but "
                    f"`{capability}` publishes: "
                    f"{', '.join(published) or 'no output fields'}."
                ),
            )

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
            answers_founder=answers_founder,
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


def _stateful_browser_order(steps: list[Step]) -> PlanRefusal | None:
    """Refuse two incomparable operations against one browser session.

    Mission Control is free to run dependency-ready steps in any valid
    topological order.  A browser session is mutable state, so two steps
    that share it but are not ordered by the DAG can observe whichever
    page the other step happened to leave behind.  Declaration order is
    not authority and must not be used to guess which operation came first.
    """
    by_id = {step.step_id: step for step in steps}

    def waits_for(step: Step, target: str) -> bool:
        pending = list(step.depends_on)
        seen: set[str] = set()
        while pending:
            dependency = pending.pop()
            if dependency == target:
                return True
            if dependency in seen:
                continue
            seen.add(dependency)
            source = by_id.get(dependency)
            if source is not None:
                pending.extend(source.depends_on)
        return False

    sessions: dict[str, list[Step]] = {}
    for step in steps:
        if not step.capability.lower().startswith("browser."):
            continue
        session_id = step.payload.get("session_id")
        if isinstance(session_id, str) and session_id.strip():
            sessions.setdefault(session_id.strip(), []).append(step)

    for session_id, operations in sessions.items():
        for index, left in enumerate(operations):
            for right in operations[index + 1:]:
                if waits_for(left, right.step_id) or waits_for(right, left.step_id):
                    continue
                return PlanRefusal(
                    code=BAD_DEPENDENCY,
                    reason="operations sharing a stateful browser session are unordered",
                    detail=(
                        f"steps `{left.step_id}` and `{right.step_id}` both use "
                        f"stateful browser session `{session_id}`, but neither "
                        "depends on the other. Give independent routes separate "
                        "sessions, or declare their real execution order."
                    ),
                )
    return None


def validate(
    document: Any,
    options: tuple[CapabilityOption, ...] | list[CapabilityOption],
    objective: str = "",
    requirements: Any = (),
    is_sensitive: bool | None = None,
    required_coverage: Any = (),
    forbidden_coverage: Any = (),
    exhausted_routes: Any = (),
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
    document = normalise_plan_document(document)

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
    known_requirement_ids = {
        str(getattr(requirement, "requirement_id", "") or "")
        for requirement in (requirements or ())
        if str(getattr(requirement, "requirement_id", "") or "")
    }
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

    covered = {requirement_id for step in steps for requirement_id in step.covers}
    unknown = covered - known_requirement_ids if known_requirement_ids else set()
    if unknown:
        return None, PlanRefusal(
            code=BAD_PAYLOAD,
            reason="a step claims coverage of an unknown Founder requirement",
            detail=f"unknown requirement ids: {', '.join(sorted(unknown))}",
        )

    missing = set(required_coverage or ()) - covered
    if missing:
        return None, PlanRefusal(
            code=BAD_PAYLOAD,
            reason="the plan does not cover every current strategy target",
            detail=f"missing requirement ids: {', '.join(sorted(missing))}",
        )

    repeated = set(forbidden_coverage or ()) & covered
    if repeated:
        return None, PlanRefusal(
            code=BAD_PAYLOAD,
            reason=(
                "the plan claims an untargeted or already-satisfied "
                "Founder requirement"
            ),
            detail=(
                "already satisfied or deliberately untargeted requirement ids: "
                + ", ".join(sorted(repeated))
            ),
        )

    exhausted = {str(route).strip() for route in (exhausted_routes or ()) if str(route).strip()}
    repeated_routes: set[str] = set()
    for step in steps:
        target = ""
        for key in ("url", "path", "query", "instruction"):
            value = step.payload.get(key)
            if isinstance(value, str) and value.strip():
                target = value.strip()
                break
        if target and f"{step.capability} {target}" in exhausted:
            repeated_routes.add(f"{step.capability} {target}")
    if repeated_routes:
        return None, PlanRefusal(
            code=BAD_PAYLOAD,
            reason="the continuation repeats an exhausted strategy unchanged",
            detail="repeated routes: " + "; ".join(sorted(repeated_routes)),
        )

    answer_steps = [step.step_id for step in steps if step.answers_founder]
    if len(answer_steps) > 1:
        return None, PlanRefusal(
            code=BAD_PAYLOAD,
            reason="more than one step designates the Founder's answer",
            detail=(
                "exactly one evidence-producing step may designate the answer; "
                f"found designations on: {', '.join(answer_steps)}"
            ),
        )

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

    session_problem = _stateful_browser_order(steps)
    if session_problem is not None:
        return None, session_problem

    ordered, refusal = _ordered(steps)
    if ordered is None:
        return None, refusal

    return MissionPlan(
        steps=ordered,
        objective=objective,
        requirements=tuple(requirements or ()),
        is_sensitive=is_sensitive,
    ), None
