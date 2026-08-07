"""Execution Context — the identity one execution carries with it.

An `ExecutionContext` answers *"what is running, for which objective, on
whose authority, under which warrant, and how do I correlate it with
everything else?"* — and answers nothing else.

## What it is not

It is a value, not a service. It owns nothing.

| It never | Because |
|---|---|
| owns authority | The `Principal` is the authority. This only references one. |
| owns Objectives | The Objective Engine is the single source of truth. This carries an `objective_id`, not an Objective. |
| owns constitutional state | It is frozen and created per execution. There is no state to own. |
| grants permissions | The Permission System decides. Nothing here has a permission API. |
| survives the execution | No registry, no store, no lifecycle methods. Nothing holds one after its execution ends. |

## Boundaries against three names it sits next to

**`ExecutionRequest`** (Constitutional Kernel Specification §3.5) goes *in*
to `authorize()`. **A `Warrant` comes back out.** An `ExecutionContext`
carries the warrant's id *during* the execution the warrant permits. The
three are sequential, not alternatives, and only the middle one is
authority.

**`ExecutionResult`** (`executor/action.py`) is what an Action *produced*.
Context is what it was *given*. Output versus identity.

**`ExecutionLogEntry`** (`executor/executor.py`) is a record written
afterwards. Context exists during.

## Why the principal is the object and the rest are ids

`principal` is a whole `Principal` because the question it answers —
*"which founder or delegate authorized this?"* — must be answerable
without a second lookup, and because a frozen value cannot go stale.

`objective_id` and `warrant_id` are opaque strings deliberately. Both refer
to entities that live elsewhere and are owned elsewhere; holding the id
keeps the single source of truth single. It is also why this module needs
no import from the Objective Engine or the Kernel, neither of which exists
yet — an id is an id regardless of what it eventually points at, so
nothing here is rewritten when they land.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from master_agent.foundation.principal import Principal

def _empty_metadata() -> MappingProxyType[str, str]:
    return MappingProxyType({})


@dataclass(frozen=True)
class ExecutionContext:
    """Immutable identity for exactly one execution.

    Every field is required except `metadata`, and that is deliberate: a
    context missing its objective, its principal, or its warrant is a
    context that cannot answer the question it exists for, and an optional
    field is how it would come to be missing one.
    """

    #: The Objective this execution advances. An id, never the Objective —
    #: the Objective Engine remains the single source of truth.
    objective_id: str

    #: The founder or delegate on whose authority this runs. The whole
    #: value, so a receipt can name them without a lookup.
    principal: Principal

    #: The Kernel-minted Warrant permitting this execution. Present because
    #: execution happens *after* authorization; a context without one
    #: describes work nobody permitted.
    warrant_id: str

    #: Links every execution belonging to one logical unit of work — the
    #: forty-seven document reads of one objective step share one.
    correlation_id: str

    #: Identifies this single execution within that correlation. Distinct
    #: from `correlation_id` because "which run" and "which group of runs"
    #: are different questions and one field cannot answer both.
    trace_id: str

    #: Diagnostic labels only — never load-bearing, never read to make a
    #: decision. Constrained to `str -> str` and frozen on construction so
    #: it cannot become the place real state hides. If something here would
    #: change what the system does, it belongs in a named field or nowhere.
    metadata: Mapping[str, str] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        for name in ("objective_id", "warrant_id", "correlation_id", "trace_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty identifier")

        if not isinstance(self.principal, Principal):
            raise TypeError(
                "principal must be a Principal (a founder or a delegate); "
                "Kalpavriksha is never a principal — see foundation.principal"
            )

        # A dict passed by a caller stays mutable through their reference
        # even inside a frozen dataclass. Copy it, then freeze the copy, so
        # "immutable" is true of the object rather than of the annotation.
        object.__setattr__(
            self, "metadata", MappingProxyType(dict(self.metadata))
        )

    @property
    def principal_id(self) -> str:
        """Convenience for the receipt layer, which records the id."""
        return self.principal.principal_id
