"""Declaring that one Step's input comes from another Step's verified output.

## The gap this closes

A Medium mission observed a page and wrote what it saw into a file. Every
step verified MATCHED, and the file was still wrong:

    step_3 Browser.ObserveBrowser  observed  https://example.com/
    step_5 Filesystem.WriteFile    wrote     https://example.com

`step_5` declared `depends_on: ["step_3", "step_4"]`, so the Planner had
understood the dependency perfectly. What did not exist was any way to
*express* that `content` comes from `step_3`, so the Planner filled the
argument at planning time from the founder's own sentence -- a prediction,
and wrong by the one character that proves it was one.

`depends_on` says **when**. This says **what flows**.

## What a binding means

    from_step(step_id="step_3", field="url")

reads: *the value this dependency produced for `url`, corroborated by its
own canonical Evidence.* It deliberately does NOT mean "whatever the
Action reported". A binding resolves only when the Action's result and the
independent Observation agree -- see `runtime/input_resolution.py`, which
enforces that. Letting a bound value ride on an unverified
`ExecutionResult` would quietly undo the Evidence architecture: the whole
point is that a Worker's claim about its own work is not proof.

That trust rule is fixed here, not offered as a choice. A Planner writes
`from_step(step_3, url)`; it never selects "result" or "evidence" as a
source, because which to trust is an architectural decision rather than a
reasoning one.

## Deliberately tiny

Two forms, no more:

* `from_step` -- one value from one dependency
* `concat` -- literals and `from_step` segments joined in order

No arithmetic, no conditionals, no loops, no expression language, no
template engine, no evaluation of provider-authored strings. A binding is
data the Runtime walks, never code it runs. `concat` does not nest,
because the moment it does someone will want a conditional inside it.

These shapes are plain dicts on the wire so they cross the event bus and
reach disk with the same JSON-plain discipline everything else uses.

## Why it lives here

Both the Planner (which writes bindings) and Mission Control (whose Tasks
carry them) need this vocabulary, and the Planner may not import
`mission_control` -- an architecture test enforces that, and it caught the
first placement. `capabilities/` is the published contract package for
what a capability accepts and returns, which is exactly what a statement
about how one of its arguments is supplied belongs to. Same precedent as
the Planner consuming `verification.evidence`: a contract, not a runtime.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

#: Keys of the two value forms, and of a concat segment.
FROM_STEP = "from_step"
CONCAT = "concat"
LITERAL = "literal"


class MalformedBinding(ValueError):
    """A binding this contract cannot read. Carries a sentence naming the
    offending target, because a caller rejecting a plan has to be able to
    say which argument was wrong."""


@dataclass(frozen=True)
class StepFieldRef:
    """One value from one dependency's verified output."""

    step_id: str
    field: str

    def as_dict(self) -> dict[str, Any]:
        return {FROM_STEP: {"step_id": self.step_id, "field": self.field}}


@dataclass(frozen=True)
class LiteralSegment:
    """Fixed text the Planner genuinely does know at planning time -- a
    label like `"Title: "`, never an observed value."""

    text: str

    def as_dict(self) -> dict[str, Any]:
        return {LITERAL: self.text}


@dataclass(frozen=True)
class Binding:
    """How one destination argument is produced.

    Exactly one of `ref` or `segments` is set. Both set, or neither, is
    malformed -- two authorities for one argument is the same defect as a
    literal payload competing with a binding.
    """

    ref: StepFieldRef | None = None
    segments: tuple[LiteralSegment | StepFieldRef, ...] = ()

    @property
    def references(self) -> tuple[StepFieldRef, ...]:
        """Every dependency value this binding reads, in order."""
        if self.ref is not None:
            return (self.ref,)
        return tuple(s for s in self.segments if isinstance(s, StepFieldRef))

    def as_dict(self) -> dict[str, Any]:
        if self.ref is not None:
            return self.ref.as_dict()
        return {CONCAT: [segment.as_dict() for segment in self.segments]}


def _ref_from(data: Any, where: str) -> StepFieldRef:
    if not isinstance(data, dict):
        raise MalformedBinding(f"{where}: '{FROM_STEP}' must be an object")
    step_id = data.get("step_id")
    field = data.get("field")
    if not isinstance(step_id, str) or not step_id.strip():
        raise MalformedBinding(f"{where}: '{FROM_STEP}.step_id' must be a step id")
    if not isinstance(field, str) or not field.strip():
        raise MalformedBinding(f"{where}: '{FROM_STEP}.field' must be a field name")
    return StepFieldRef(step_id=step_id.strip(), field=field.strip())


def binding_from_dict(data: Any, where: str = "binding") -> Binding:
    """Read one binding, or raise `MalformedBinding`.

    Strict on purpose. A binding that cannot be read must be rejected at
    plan time, because by execution time the alternative to a value is a
    guess.
    """
    if not isinstance(data, dict):
        raise MalformedBinding(f"{where}: must be an object")

    has_ref = FROM_STEP in data
    has_concat = CONCAT in data
    if has_ref == has_concat:
        raise MalformedBinding(
            f"{where}: exactly one of '{FROM_STEP}' or '{CONCAT}' is required"
        )

    if has_ref:
        return Binding(ref=_ref_from(data[FROM_STEP], where))

    raw = data[CONCAT]
    if not isinstance(raw, list) or not raw:
        raise MalformedBinding(f"{where}: '{CONCAT}' must be a non-empty list")

    segments: list[LiteralSegment | StepFieldRef] = []
    for index, item in enumerate(raw):
        at = f"{where}.{CONCAT}[{index}]"
        if not isinstance(item, dict):
            raise MalformedBinding(f"{at}: must be an object")
        if LITERAL in item and FROM_STEP in item:
            raise MalformedBinding(f"{at}: cannot be both a literal and a reference")
        if LITERAL in item:
            text = item[LITERAL]
            if not isinstance(text, str):
                raise MalformedBinding(f"{at}: '{LITERAL}' must be a string")
            segments.append(LiteralSegment(text=text))
        elif FROM_STEP in item:
            segments.append(_ref_from(item[FROM_STEP], at))
        elif CONCAT in item:
            # Stated rather than silently flattened: nesting is where an
            # expression language starts.
            raise MalformedBinding(f"{at}: '{CONCAT}' cannot nest")
        else:
            raise MalformedBinding(
                f"{at}: must be a '{LITERAL}' or a '{FROM_STEP}'"
            )
    return Binding(segments=tuple(segments))


def bindings_from_dict(data: Any) -> dict[str, Binding]:
    """Read a whole `input_bindings` map, keyed by destination argument."""
    if data in (None, {}):
        return {}
    if not isinstance(data, dict):
        raise MalformedBinding("input_bindings: must be an object")
    return {
        str(target): binding_from_dict(value, where=f"input_bindings.{target}")
        for target, value in data.items()
    }


def bindings_as_dict(bindings: dict[str, Binding]) -> dict[str, Any]:
    return {target: binding.as_dict() for target, binding in bindings.items()}
