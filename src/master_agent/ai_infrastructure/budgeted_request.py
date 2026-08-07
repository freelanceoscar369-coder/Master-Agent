"""Asking the Broker for a provider *and* a deadline (Mission Brief 038).

`SelectionRequest` lives in `plugins/model_router.py`, which is frozen.
Its `RATIFIED_EXCEPTIONS` row names ADR-0017, which is a different
purpose, so reusing that exception to add fields would be drift.

**So this subclasses rather than modifies.** `AiCapabilityService.decide()`
already accepts `request: Any`, every `isinstance(x, SelectionRequest)`
check still passes, and `SelectionRequest.from_context()` is untouched.
MB035 set the precedent: `TextVerifier` lives outside frozen
`verification/` and implements the published contract instead of editing
it. No ADR is required for this, which is the point.

Both new fields are **facts about the work**, never preferences about the
provider -- the rule MB032 established for everything on a routing
request. A caller says *what kind of interaction this is* and *when it
must be over*; it never says how long the provider may take. That number
is derived, by the Broker, from these facts plus the provider's measured
throughput.
"""
from __future__ import annotations

from dataclasses import dataclass

from master_agent.ai_infrastructure.workload import DEFAULT_CLASS
from master_agent.plugins.model_router import SelectionRequest

#: What a caller assumes about output size when it has nothing better to
#: say. Deliberately **not** a tuned constant: it is only ever used to
#: size the decode half of a budget, the class ceiling bounds the result,
#: and a caller that knows better passes the real number.
UNSTATED_OUTPUT_TOKENS = 0


@dataclass(frozen=True)
class BudgetedSelectionRequest(SelectionRequest):
    """A selection request that also carries what a budget needs.

    Frozen for the same reason its parent is: a request describes what was
    asked, and a selector must not be able to edit the question on its way
    to answering it.
    """

    #: One of `workload.REQUEST_CLASSES`. Answers "what shape is this
    #: interaction?", which is a different question from `capability`
    #: ("what kind of intelligence?"). Planning is `capability="reasoning"`
    #: **and** `request_class="planning"`.
    request_class: str = DEFAULT_CLASS

    #: The prompt this request will carry, so the Broker can size it with
    #: the chosen provider's tokenizer. Held rather than pre-counted
    #: because the count depends on *which* provider wins, and that is not
    #: known until after the decision.
    prompt: str = ""

    #: How much output the caller expects, in tokens. Zero means unstated.
    expected_output_tokens: int = UNSTATED_OUTPUT_TOKENS

    #: Absolute monotonic instant by which the whole call must be over,
    #: from the task above. `None` means no ceiling has been imposed yet --
    #: Stage B supplies one; until then the class envelope is the only
    #: bound.
    deadline: float | None = None
