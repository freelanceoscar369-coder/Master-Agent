"""Resolving declared input bindings against verified dependency output.

## What this refuses to do

A binding says *"take `url` from step_3"*. The tempting implementation is
`source_task.result["url"]` — and that would quietly undo the Evidence
architecture, because an `ExecutionResult` is a Worker's claim about its
own work. ADR-0011 exists so completion never rests on one; a value that
flows automatically into the next step deserves the same standard.

So a value resolves only when **eight** things hold:

1. the source Task exists;
2. it is COMPLETED;
3. it is a declared dependency of the consuming Task;
4. its `result` contains the field;
5. it carries canonical Evidence;
6. that Evidence's verdict is `matched`;
7. the Evidence's *observation* contains the field;
8. the reported value and the observed value **agree**.

Rule 8 is the one that matters. If the Action says one thing and the
independent Observation says another, this does not pick a winner — it
fails. Choosing silently is how a system starts trusting itself.

## What it does not know

Nothing about browsers, filesystems, desktops, `title`, `url`, or
`page_info.txt`. It sees Tasks, ids, two JSON dicts, dot-paths, and the
binding structure. That ignorance is load-bearing and asserted by an
architecture test: the Runtime must stay domain-agnostic.

## Failure is before side effect

Resolution runs before the approval boundary and before `gateway.invoke`,
so a binding that cannot be trusted fails the Task without approving
anything, writing anything, or asking a provider to guess a replacement.
There is no fallback to a planner literal and none to the founder's raw
words — a missing value is not permission to invent one.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from master_agent.capabilities.input_bindings import (
    Binding,
    LiteralSegment,
    MalformedBinding,
    StepFieldRef,
    binding_from_dict,
)


class BindingResolutionError(Exception):
    """A declared input could not be trustworthily resolved. The message is
    the diagnostic a Task failure carries."""


@dataclass
class ResolvedInputs:
    """The payload to execute, and where its bound values came from."""

    payload: dict[str, Any]
    #: JSON-plain provenance: which step and field supplied each target,
    #: and under which Evidence. Only ids and paths -- the values
    #: themselves already live in the source Evidence, and copying dynamic
    #: content again would enlarge what we store for no new fact.
    provenance: list[dict[str, Any]] = field(default_factory=list)

    @property
    def has_bindings(self) -> bool:
        return bool(self.provenance)


def _walk(document: Any, path: str) -> tuple[bool, Any]:
    """The same dot-path vocabulary Verification's evaluator uses:
    `url`, `title`, `elements.0.text`. Deliberately not JSONPath.

    Reimplemented rather than imported because `runtime/` may not depend on
    the verification package (asserted by an architecture test); parity is
    asserted by test instead of by coupling.
    """
    current = document
    for part in path.split("."):
        if isinstance(current, dict):
            if part not in current:
                return False, None
            current = current[part]
        elif isinstance(current, list):
            try:
                index = int(part)
            except ValueError:
                return False, None
            if not 0 <= index < len(current):
                return False, None
            current = current[index]
        else:
            return False, None
    return True, current


def _verified_value(task: Any, source: Any, ref: StepFieldRef) -> Any:
    """One field of one dependency, corroborated by its own Evidence."""
    consumer = getattr(task, "task_id", "?")
    where = f"{consumer}: binding on step '{ref.step_id}' field '{ref.field}'"

    if source is None:
        raise BindingResolutionError(f"{where}: no such step in this mission")

    if ref.step_id not in list(getattr(task, "depends_on", ()) or ()):
        # `depends_on` is the single execution-order authority. A binding
        # may read a dependency; it may not create one, because that would
        # let data flow decide scheduling behind the DAG's back.
        raise BindingResolutionError(
            f"{where}: not a declared dependency of this step"
        )

    state = getattr(getattr(source, "state", None), "value", getattr(source, "state", None))
    if str(state) != "completed":
        raise BindingResolutionError(f"{where}: source step is '{state}', not completed")

    result = getattr(source, "result", None)
    if not isinstance(result, dict):
        raise BindingResolutionError(f"{where}: source produced no readable result")
    found, reported = _walk(result, ref.field)
    if not found:
        raise BindingResolutionError(f"{where}: field absent from the source result")

    evidence = getattr(source, "evidence", None)
    if not isinstance(evidence, dict):
        # The local fail-closed rule for data dependencies. A step may
        # still COMPLETE elsewhere without Evidence while global
        # fail-closed remains deferred -- but a value may not FLOW on that
        # basis. Those are different policies and this is the strict one.
        raise BindingResolutionError(
            f"{where}: source has no canonical Evidence, so its output "
            f"cannot be trusted as an input"
        )
    if evidence.get("verdict") != "matched":
        raise BindingResolutionError(
            f"{where}: source Evidence verdict is "
            f"'{evidence.get('verdict')}', not matched"
        )

    observed_found, observed = _walk(evidence.get("observation") or {}, ref.field)
    if not observed_found:
        raise BindingResolutionError(
            f"{where}: field absent from the source Evidence observation"
        )

    if reported != observed:
        # Never pick a winner. The Action and the independent Observation
        # disagreeing is exactly the condition Verification exists to
        # surface, and silently preferring either one would make the
        # Evidence decorative.
        raise BindingResolutionError(
            f"{where}: the step reported {reported!r} but the independent "
            f"observation recorded {observed!r}; refusing to choose"
        )

    return observed


def resolve_inputs(task: Any, sources: dict[str, Any]) -> ResolvedInputs:
    """The payload to execute, built from literals plus verified values.

    `task.payload` is never mutated: the persisted plan stays what the
    Planner decided, and the resolved payload is execution material rather
    than a rewritten plan.
    """
    payload = dict(getattr(task, "payload", None) or {})
    declared = getattr(task, "input_bindings", None) or {}
    if not declared:
        return ResolvedInputs(payload=payload)

    # A Task carries bindings as plain JSON -- that is the wire form, and
    # it is what survives the event bus, translation and a restart. Parsed
    # here rather than assumed to be objects: an earlier version took
    # `Binding` instances, which is what the tests happened to build and
    # what production never sends, so the first live mission died on
    # `'dict' object has no attribute 'ref'`.
    try:
        bindings: dict[str, Binding] = {
            target: value if isinstance(value, Binding) else binding_from_dict(
                value, where=f"input_bindings.{target}"
            )
            for target, value in declared.items()
        }
    except MalformedBinding as exc:
        raise BindingResolutionError(
            f"{getattr(task, 'task_id', '?')}: {exc}"
        ) from None

    provenance: list[dict[str, Any]] = []

    for target, binding in bindings.items():
        if target in payload:
            # Two authorities for one argument. Rejected at plan time too;
            # asserted again here because a plan can reach a Runtime that
            # did not validate it.
            raise BindingResolutionError(
                f"{getattr(task, 'task_id', '?')}: '{target}' is set both by a "
                f"literal payload and by a binding"
            )

        used: list[dict[str, Any]] = []

        if binding.ref is not None:
            source = sources.get(binding.ref.step_id)
            value = _verified_value(task, source, binding.ref)
            payload[target] = value
            used.append({
                "step_id": binding.ref.step_id,
                "field": binding.ref.field,
                "evidence_id": (getattr(source, "evidence", None) or {}).get("evidence_id"),
            })
        else:
            parts: list[str] = []
            for segment in binding.segments:
                if isinstance(segment, LiteralSegment):
                    parts.append(segment.text)
                    continue
                source = sources.get(segment.step_id)
                value = _verified_value(task, source, segment)
                if not isinstance(value, str):
                    raise BindingResolutionError(
                        f"{getattr(task, 'task_id', '?')}: '{target}' joins "
                        f"'{segment.step_id}.{segment.field}', which is "
                        f"{type(value).__name__}, not text"
                    )
                parts.append(value)
                used.append({
                    "step_id": segment.step_id,
                    "field": segment.field,
                    "evidence_id": (getattr(source, "evidence", None) or {}).get("evidence_id"),
                })
            payload[target] = "".join(parts)

        provenance.append({"target": target, "sources": used})

    return ResolvedInputs(payload=payload, provenance=provenance)
