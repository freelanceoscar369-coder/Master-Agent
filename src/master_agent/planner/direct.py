"""A plan the Planner can write without asking a model.

## The defect this exists to remove

A founder typed *"create a folder called KalpavrikshaLiveTest3 in
Documents"*. `Filesystem.CreateFolder(name, location?)` was registered and
sufficient. The Planner nevertheless sent a planning prompt to its
reasoning ladder, which — Gemini being out of quota — fell through every
tier: Gemini, then each installed desktop AI application, then a browser
search. Windows opened. Nothing about the objective needed reasoning.

**Capability availability and reasoning necessity are different
questions.** A model that is asked *"which of these capabilities creates
a folder?"* is being paid to rediscover a mapping the Intent Layer has
already performed.

## What makes it deterministic rather than a guess

Two independent facts have to agree, and both are already published:

1. The Intent names a capability. Not inferred from prose here — the
   typed parser that recognised the sentence recorded it, the same
   `capability` + `payload` pair `cli.py`'s `ParsedActionIntent` has
   carried since MB005.
2. The registered catalogue confirms that capability exists, publishes
   `required_args`, and declares those arguments **complete**
   (`args_complete`) — MB039's index, not the thin registry.

If either is missing, this returns `None` and the Planner asks a provider
exactly as before. Nothing is downgraded on a maybe.

## Why matching on argument shape alone was rejected

The obvious alternative — find the capability whose `required_args` the
Intent's context happens to satisfy — is unsafe here, measured rather
than assumed: in the filesystem plugin alone `('path',)` is the required
signature of **six** capabilities, among them `Filesystem.ReadFile` and
`Filesystem.DeleteFile`. A shape match cannot tell reading from deleting,
and one of those is irreversible. So the capability is never inferred
from the arguments; it is only ever confirmed.

## What this module does not do

It does not decide whether to use a model — `Planner` owns that. It does
not execute anything. It does not reorder, retry, or approve. It produces
one `Step`, inside `planner/`, which is the only package permitted to
construct a `MissionPlan` at all (asserted by an AST test over `src/`).
"""
from __future__ import annotations

from typing import Any

from master_agent.planner.outcomes import SuccessSpec
from master_agent.planner.plan import Intent, MissionPlan, Step


def _normalised(name: str) -> str:
    """`create_folder`, `CreateFolder` and `Filesystem.CreateFolder` are
    the same capability written three ways -- the plugin constant, the
    contract class, and the qualified catalogue name. Comparing them
    without knowing plugin namespacing keeps the Brain from having to."""
    return name.rsplit(".", 1)[-1].replace("_", "").replace("-", "").lower()


def find_option(capability: str, options) -> Any | None:
    """The registered capability this intent names, or `None`.

    Exact match on the normalised name only. A near-miss is not a match:
    an intent naming something unregistered is a question for the Planner,
    not an invitation to pick the closest thing.
    """
    if not capability:
        return None
    wanted = _normalised(capability)
    for option in options:
        if _normalised(option.name) == wanted:
            return option
    return None


def direct_plan(intent: Intent, options) -> MissionPlan | None:
    """One step, or `None` when this objective genuinely needs planning.

    `None` is the safe answer and is returned for every uncertainty: no
    capability named, capability not registered, arguments the contract
    does not publish, a required argument missing, or an argument roster
    the catalogue itself flags as incomplete.
    """
    option = find_option(getattr(intent, "capability", ""), options)
    if option is None:
        return None

    payload = dict(getattr(intent, "payload", None) or {})
    if not payload:
        return None

    required = tuple(getattr(option, "required_args", ()) or ())
    optional = tuple(getattr(option, "optional_args", ()) or ())

    # MB039's own honesty flag. An index that does not know the full
    # argument roster cannot be used to certify a payload is complete --
    # that is exactly the "the Planner guesses argument names" failure
    # `args_complete` was added to expose, and guessing is what this
    # module exists to stop.
    if not getattr(option, "args_complete", False):
        return None

    known = set(required) | set(optional)
    if not known or not set(payload) <= known:
        # An argument the contract never published cannot be passed on. The
        # Planner will ask a provider, which at least gets to see the
        # capability description.
        return None
    if not set(required) <= set(payload):
        return None

    # Stated before the step runs, from what the Intent Layer already said
    # success looks like -- never composed here, and never left empty:
    # `objective_from_plan()` rejects a step with no expectation, and
    # Verification would have nothing to check against.
    description = next(
        (c for c in (intent.success_criteria or []) if c and c.strip()),
        f"{option.name} completes for {intent.goal}".strip(),
    )
    step = Step(
        step_id=f"{option.name}-1",
        capability=option.name,
        payload=payload,
        expected_outcome=SuccessSpec(description=description).to_expected_outcome(),
    )
    return MissionPlan(steps=[step], objective=intent.goal)
