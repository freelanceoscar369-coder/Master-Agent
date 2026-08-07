"""What the Planner is allowed to plan with (Mission Brief 036).

A plan naming a capability that does not exist is not a plan -- it is a
sentence about one. The catalogue is how the Planner learns what really
exists, and it is the list a hallucinated capability is checked against.

**It is a port, not a dependency.** `catalogue_from()` needs one method,
`all()`, so Mission Control's `CapabilityRegistry` satisfies it and
nothing here imports that frozen package -- the same "needs one method"
shape MB033 used for `PromptExecutor(providers=...)`. A test can hand in a
list of two options; the launcher hands in the real registry; neither
knows about the other.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CapabilityOption:
    """One thing the Planner may put in a Step.

    A narrow projection of whatever the registry holds, on purpose: the
    Planner needs a name, a sentence and a risk tier to write a plan, and
    giving it the full descriptor would let it start reasoning about
    permission categories, which the Permission System owns and nothing
    else does.
    """

    name: str
    description: str = ""
    risk_tier: str | None = None
    #: MB039. The arguments a call **must** carry, read from the
    #: capability's contract rather than from its description. This is the
    #: field that closes MB036 Finding 4: the Planner used to learn an
    #: argument's name by reading English, and got it wrong.
    required_args: tuple[str, ...] = ()
    #: False when optional arguments exist that nobody has published, so
    #: the list above is a floor rather than the whole story.
    args_complete: bool = False


def catalogue_from(registry: Any) -> tuple[CapabilityOption, ...]:
    """Project a capability registry into the Planner's vocabulary.

    Sorted by name, always: the catalogue goes into a prompt, and a prompt
    whose text depends on registration order would make the same objective
    produce a different plan on a different boot. Determinism starts here,
    not at the parser.
    """
    options = [
        CapabilityOption(
            name=descriptor.qualified_name,
            description=(descriptor.description or "").strip(),
            risk_tier=descriptor.risk_tier,
        )
        for descriptor in registry.all()
    ]
    return tuple(sorted(options, key=lambda option: option.name))


def catalogue_from_index(index: Any) -> tuple[CapabilityOption, ...]:
    """Project MB039's capability index into the Planner's vocabulary.

    Preferred over `catalogue_from()` wherever an index exists: the
    registry publishes a *sentence* about a capability, and the index
    publishes its *arguments*. Same "needs one attribute" shape -- an
    index is anything with `.entries`.
    """
    return tuple(
        CapabilityOption(
            name=entry.canonical_id,
            description=entry.summary,
            risk_tier=entry.risk_tier,
            required_args=tuple(entry.required_args),
            args_complete=entry.args_complete,
        )
        for entry in sorted(index.entries, key=lambda e: e.canonical_id)
    )


def render(options: tuple[CapabilityOption, ...] | list[CapabilityOption]) -> str:
    """The catalogue as the provider sees it.

    One line per capability, and the risk tier is shown because a plan
    that reaches for `Filesystem.DeleteFolder` when `Filesystem.ListFolder`
    would answer the question should be visibly the more expensive choice.
    It is stated, never enforced: enforcement is the Permission System's,
    and MB028.0 made that the only gate.
    """
    lines = []
    for option in options:
        # The name stands alone on the left of the separator.
        #
        # The first version of this rendered `- Name(arg1, arg2)`, and a
        # live run produced a plan whose capability was the literal string
        # `Filesystem.WriteFile(path, ...)` -- the model read the
        # signature as part of the name. It happened on one objective out
        # of four, which is worse than always: an ambiguity that usually
        # resolves correctly is one nobody notices until it does not.
        line = f"- {option.name} | {signature(option)}"
        if option.description:
            line += f" | {option.description}"
        if option.risk_tier:
            line += f" [risk: {option.risk_tier}]"
        lines.append(line)
    return "\n".join(lines)


def signature(option: CapabilityOption) -> str:
    """The required arguments, as a labelled field.

    Labelled rather than parenthesised so it cannot be mistaken for part
    of the capability name -- see `render`. "no arguments" and "arguments
    exist but were never published" are said differently, because they
    are different facts.
    """
    if not option.required_args:
        return "args: none declared" if not option.args_complete else "args: none"
    args = ", ".join(option.required_args)
    if option.args_complete:
        return f"args: {args}"
    return f"args: {args} (others may exist)"


def names(options: tuple[CapabilityOption, ...] | list[CapabilityOption]) -> tuple[str, ...]:
    return tuple(option.name for option in options)
