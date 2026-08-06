"""Execution Coordinator — the Kernel's exit protocol, written once.

Kernel Specification §6.1 states what every caller must do, in four
lines:

```
   intent = kernel.authorize(request)      # may refuse
   token  = kernel.attempt(intent.id)      # may refuse: expired, over budget
   result = <<the caller's own execution, entirely its own business>>
   kernel.settle(intent.id, outcome)       # mandatory
```

Four lines is not many, and that is exactly the problem. §6.3 says
*"every minted intent must be settled — settlement is mandatory, and its
absence is a defect rather than a shrug"*, and §4.4 calls an unsettled
intent *"a first-class defect, never a silently discarded record."* Both
sentences describe something a caller can forget.

**This component makes the sequence structural rather than remembered.**
A caller supplies a request and a piece of work; the order, the retry
bound, and the settlement are not its business and cannot be got wrong.

## What it is, in one line

> **An orchestrator with no authority.** It composes the four operations
> §3.5 already gives it and decides nothing the Kernel decides.

## What it must never become

§1.2's warning is about the Kernel, and it applies with equal force one
layer up: a component that reimplements what it coordinates is not a
coordinator, it is a second Kernel with worse tests.

| Never | Owner |
|---|---|
| Deciding whether an action is permitted | Kernel §7.2 · the attestors §7.3 |
| Minting anything | Kernel §3.3 — *"the only minting authority"* |
| Writing to the ledger | Kernel K3, and A1 owns the storage |
| Counting attempts, or bounding them | `Warrant.attempt_budget`, set at mint |
| Classifying reversibility | Reversibility Registry, via ADR-0022 D2 |
| Reading a clock | The Kernel holds the canonical one |
| Constructing an `ExecutionRequest` | **The caller** — ADR-0022 D2 |

That last row is the one most easily lost. ADR-0022 D2 makes the caller a
courier for the reversibility class, *"not an author"*, and a Coordinator
that built the request would be authoring the very field the courier
discipline exists to keep honest.

It holds **one** collaborator — the Kernel — and **no state at all**. Two
Coordinators over one Kernel are indistinguishable, because everything
that persists lives in the Kernel and the ledger behind it.

## Where the retry loop lives, and why it lives here

§3.4 assigns it, by name:

> | Retry *mechanics* | **The Runtime.** The Kernel authorizes an attempt
> | budget; it does not loop. |

§8.1 is why the loop needs a home with a bound:

> *"The root cause is not the loop. It is that there was nothing for the
> loop to be bounded by."*

The bound is `Warrant.attempt_budget`, set at mint from the action's
class. This component **never counts against it** — it asks
`Kernel.attempt()` for another attempt and stops when the Kernel refuses
one. Holding its own counter would be the second opinion §1.2 forbids.

### §8.4 is checked here, and that is not duplication

> *"An action classified `irreversible` is never automatically retried.
> Ever. Regardless of attempt budget, error class, or how transient the
> failure appears."*

C4 already refuses to construct an irreversible warrant whose budget is
anything but 1, so the Kernel would refuse a second attempt anyway. The
check is still made here because §8.4 says *"regardless of attempt
budget"*, and this is the only place in the system that decides whether
to **ask** for another attempt. That is a different question from whether
one would be granted, and the Kernel does not answer it — the Kernel does
not loop.

`unknown` is likewise never retried (§6.3, §8.4), and neither is
`partial`: some effect occurred, and doing it again is not a retry.

## An exception from the work settles `unknown`

If the caller's work raises, this component does **not** decide that the
action failed. §6.3 defines the two words precisely:

| `failed` | *"The effect did not occur, and this is known"* |
| `unknown` | *"The caller cannot determine whether the effect occurred"* |

An unexpected exception establishes the second and not the first. §6.3:
*"`unknown` exists because pretending otherwise is how a system
double-charges a card."* So the intent is settled `unknown`, which never
auto-retries and which escalates — the safe direction in every case, and
the honest one in most.

`BaseException` is deliberately **not** caught. A `KeyboardInterrupt` is
not an execution outcome.

## Escalation is reported, never performed

§8.4: an irreversible action settled `failed` or `unknown` *"escalates as
a judgment request. A human decides whether to try again, and that
decision mints a new Intent under a fresh grant."*

`Execution.requires_escalation` says **that** one is required. It does not
raise one: §3.4 gives narration and the founder surface to D1, B2 and
VEDA 03, and a component that manufactured judgment items would build the
inbox VEDA 03 abolishes. The property is derived from values that already
exist — C5's own `Receipt.requires_escalation` and the warrant's class —
so no vocabulary is added.

## Two recorded gaps this component runs into

Both belong to the shipped Kernel and neither is solved here.

**R43 · `partial` cannot be settled.** §6.3 requires a compensating
action reference for it and `settle(warrant_id, outcome)` has no
parameter for one. Work that returns `PARTIAL` therefore reaches a
settlement that C5 refuses to construct, `InvalidReceipt` propagates, and
the warrant stays outstanding and unsettled. **Recorded as R49**, which
is R43 seen from the caller's side. It is not caught here: swallowing it
would turn a loud gap into a silent one, and the intent would be no more
settled for it.

**R44 · a receipt carries no detail.** When work raises, the exception
text has nowhere to go in the permanent record. It is carried on
`Execution.error` so it is not destroyed, and the ledger holds the
outcome without the sentence. **Recorded as R50.**

## Scope

Roadmap §2 C16 states a second half this component does not perform:
*"`warrant_id` required by `LocalExecutor.run()`, no alternative route to
a tool"* — the migration of the fifteen inventoried entry points. That
work modifies `orchestrator/`, `executor/`, `runtime/` and `cli.py`, and
the brief for this component restricts its dependencies to C1–C15 and
forbids new runtime dependencies. **The unification is therefore not in
this component**, and is recorded in the health report as the outstanding
half. What is built here is the thing those fifteen call sites will each
be migrated *to*.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from master_agent.foundation.attempt_token import AttemptToken
from master_agent.foundation.execution_request import ExecutionRequest
from master_agent.foundation.receipt import ExecutionOutcome, Receipt
from master_agent.foundation.refusal import KernelRefusal
from master_agent.foundation.warrant import Warrant
from master_agent.kernel import AttemptNotAuthorized, Kernel

#: What the caller supplies as the work.
#:
#: §6.1's third line — *"the caller's own execution, entirely its own
#: business"* — and this signature is the whole of what this component
#: knows about it. It receives §8.6's idempotency key and answers with one
#: of §6.3's four kinds.
#:
#: **No file, no socket, no provider, no Worker.** §6.2's fifteen-year
#: property depends on the layers above execution knowing none of those,
#: and a callable is how this one keeps knowing none of them.
Work = Callable[[AttemptToken], ExecutionOutcome]


class InvalidCoordinator(ValueError):
    """Raised at construction for a Coordinator that could not coordinate.

    At construction, never later — the same discipline `InvalidKernel`
    follows, and for the same reason: a misconfiguration discovered on the
    first execution is discovered at the most expensive possible moment.
    """


@dataclass(frozen=True)
class Execution:
    """What happened, end to end. Immutable.

    Every field is either a value the Kernel produced or a fact about how
    far the sequence got. Nothing here is derived from a second opinion,
    and nothing here is authority — it is a report.
    """

    #: The minted authorization, or `None` when authorization refused.
    warrant: Warrant | None = None

    #: The terminal outcome record, or `None` when nothing was settled.
    #: §9.1's `OutcomeRecord (0..1, terminal)`.
    receipt: Receipt | None = None

    #: The Kernel's refusal, from `authorize()` or from `attempt()`.
    #: `None` when neither refused.
    refusal: KernelRefusal | None = None

    #: How many attempts the work actually ran under. Observed, never
    #: enforced — the bound is `Warrant.attempt_budget` and it is the
    #: Kernel's.
    attempts: int = 0

    #: The work's exception text, when it raised. It has no home in the
    #: permanent record while R44 stands, and this keeps it from being
    #: destroyed. Diagnostic only.
    error: str | None = None

    @property
    def authorized(self) -> bool:
        """Whether a warrant was minted."""
        return self.warrant is not None

    @property
    def settled(self) -> bool:
        """Whether the mandatory settlement of §6.3 occurred.

        **`False` is a defect, not a state**, whenever `authorized` is
        true — §4.4 calls an unsettled intent *"a first-class defect,
        never a silently discarded record."* The one benign case is an
        authorization no attempt was ever opened against, which §4.5 sends
        to EXPIRED rather than to SETTLED.
        """
        return self.receipt is not None

    @property
    def requires_escalation(self) -> bool:
        """Whether a human must decide what happens next.

        Two clauses, both quoted rather than invented:

        §6.3 — `unknown` *"escalates"*, which C5 already answers as
        `Receipt.requires_escalation`.

        §8.4 — an irreversible action settled `failed` or `unknown`
        *"escalates as a judgment request. A human decides whether to try
        again, and that decision mints a new Intent under a fresh grant."*

        Reported, never acted on. §3.4 gives narration and the founder
        surface to D1, B2 and VEDA 03.
        """
        if self.receipt is None:
            return False
        if self.receipt.requires_escalation:
            return True
        return (
            self.warrant is not None
            and self.warrant.is_irreversible
            and self.receipt.outcome is ExecutionOutcome.FAILED
        )

    def as_dict(self) -> dict[str, Any]:
        """A deterministic, JSON-ready projection. Fixed key order."""
        return {
            "warrant": None if self.warrant is None else self.warrant.as_dict(),
            "receipt": None if self.receipt is None else self.receipt.as_dict(),
            "refusal": None if self.refusal is None else self.refusal.as_dict(),
            "attempts": self.attempts,
            "error": self.error,
        }


class ExecutionCoordinator:
    """§6.1's sequence, composed once.

    One collaborator, no state. Everything that outlives a call lives in
    the Kernel and in the ledger behind it, which is what makes two
    Coordinators over one Kernel indistinguishable.
    """

    __slots__ = ("_kernel",)

    def __init__(self, kernel: Kernel) -> None:
        if not isinstance(kernel, Kernel):
            raise InvalidCoordinator(
                "kernel must be the Kernel; §6.1's sequence is composed of "
                "its four operations and there is no other source for any "
                "of them (§3.5)"
            )
        self._kernel: Kernel = kernel

    def run(self, request: ExecutionRequest, work: Work) -> Execution:
        """Authorize, attempt, execute, settle. In that order, always.

        §6.1, with the settlement §6.3 makes mandatory guaranteed rather
        than remembered.

        **Nothing runs before a warrant exists.** A refusal returns
        immediately and `work` is never called — §11.5's reason for
        refusing before minting applies with more force to refusing before
        executing.

        **The loop asks; it never counts.** `Kernel.attempt()` refuses
        when the budget is spent or the warrant has expired, and that
        refusal is what ends the loop. This component holds no counter
        against §8.5's budget because holding one would be a second
        opinion about a question the mint already answered.

        Returns an `Execution` describing how far the sequence got. It
        does not raise for a refusal — §7.5: *"refusals are data, not
        exceptions."* It does propagate `InvalidReceipt` for a `partial`
        outcome, which is **R49**; see the module docstring.
        """
        if not callable(work):
            raise InvalidCoordinator(
                "work must be callable; §6.1's third line is the caller's "
                "own execution and this component has no other way to reach "
                "it"
            )

        authorized = self._kernel.authorize(request)
        if isinstance(authorized, KernelRefusal):
            return Execution(refusal=authorized)

        warrant: Warrant = authorized
        outcome: ExecutionOutcome | None = None
        refusal: KernelRefusal | None = None
        error: str | None = None
        attempts = 0

        while True:
            try:
                token = self._kernel.attempt(warrant.warrant_id)
            except AttemptNotAuthorized:
                # Budget spent, or the window closed. Either way no further
                # attempt is authorized, and asking again would be the
                # unbounded loop §8.1 describes.
                break

            if isinstance(token, KernelRefusal):
                # §11.3 — the attempt record could not be written, so no
                # attempt was opened and nothing ran.
                refusal = token
                break

            attempts += 1

            try:
                outcome = work(token)
            except Exception as exc:  # noqa: BLE001 — see the module docstring
                # §6.3: the caller cannot determine whether the effect
                # occurred. That is `unknown`, not `failed`.
                outcome = ExecutionOutcome.UNKNOWN
                error = f"{type(exc).__name__}: {exc}"
                break

            if not _may_retry(outcome, warrant):
                break

        if outcome is None:
            # No attempt ever ran, so there is no outcome to record.
            # §4.5 sends such a warrant to EXPIRED, never to SETTLED, and
            # `settle()` would refuse it.
            return Execution(warrant=warrant, refusal=refusal, attempts=attempts)

        receipt = self._kernel.settle(warrant.warrant_id, outcome)
        return Execution(
            warrant=warrant,
            receipt=receipt,
            refusal=refusal,
            attempts=attempts,
            error=error,
        )


def _may_retry(outcome: ExecutionOutcome, warrant: Warrant) -> bool:
    """Whether another attempt should be **asked for**.

    Not whether one would be granted — that is `attempt()`'s answer,
    against §8.5's budget. This is the Runtime's own obedience to §8.4,
    at the layer §3.4 assigns the loop to.

    | Outcome | Retry | Because |
    |---|---|---|
    | `succeeded` | no | There is nothing to try again |
    | `partial` | no | *"Some effect occurred"* — doing it again is not a retry |
    | `unknown` | no | §6.3 and §8.4 — *"never auto-retried"*; it escalates |
    | `failed` | only if reversible | §8.4 — *"regardless of attempt budget"* |
    """
    if outcome is not ExecutionOutcome.FAILED:
        return False
    return not warrant.is_irreversible
