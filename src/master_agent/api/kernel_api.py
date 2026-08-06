"""Kernel API — the four operations, projected across one boundary.

Kernel Specification §3.5 fixes the surface at four operations. This
module exposes those four and nothing else, in a shape a surface can
consume without importing the Kernel.

```
  authorize(request)              -> ApiResponse
  attempt(warrant_id)             -> ApiResponse
  settle(warrant_id, outcome)     -> ApiResponse
  invalidate(scope, reason)       -> ApiResponse
  status()                        -> ApiResponse
```

## What it is

> **A projection. Every call delegates, and nothing else happens.**

There is no branch in this module that a `KernelRefusal` or an exception
did not put there. It performs no check §7.2 assigns to the Kernel, holds
no state, and decides nothing — which is why the same request through this
boundary and through the Kernel directly cannot produce two answers.

## Why it exists

§3.6's dependency direction is *"strictly downward"*, and a surface that
imports the Kernel to read one number has reached past every boundary
between them to do it. One door means the reach is auditable: a test can
assert that no surface imports the Kernel, and the assertion means
something.

§7.5 states the second reason, about what a surface must never receive:

> *"Refusals are data, not exceptions… the founder is reading a stack
> trace from a provider SDK instead of a sentence about their own
> machine."*

A refusal already arrives as data. **An exception does not**, and every
one of the Kernel's — `AttemptNotAuthorized`, `NothingToSettle`,
`LedgerUnavailable`, `InvalidWarrant`, `InvalidReceipt` — would otherwise
cross the boundary as a traceback. §4 of this docstring is how they cross
instead.

## The vocabulary is the Kernel's, unaltered

Every payload here is a value object's **own** `as_dict()`. Nothing is
renamed, reordered, flattened, enriched or summarised:

| Operation | On success | Source |
|---|---|---|
| `authorize` | `Warrant.as_dict()` | C4 |
| `attempt` | `AttemptToken.as_dict()` | C10 |
| `settle` | `Receipt.as_dict()` | C5 |
| `invalidate` | `{"count": n}` | §3.5's `→ count` |
| `status` | the override switch and the outstanding count | §3.3's two owned facts |

A refusal is `KernelRefusal.as_dict()`, exactly as C8 wrote it — the same
`reason`, `family`, `failed_check`, `failed_check_kind`, `attestor`,
`remediable` and `detail`. **This module adds no reason and renames
none.**

## Exceptions become responses, and keep their names

Every Kernel exception is mapped to a `ResultKind.ERROR` response carrying
the exception's **own class name** and message. Nothing is grouped into a
transport error taxonomy: `NothingToSettle` arrives as
`"NothingToSettle"`, because a boundary that renamed it would be inventing
a vocabulary parallel to the one C8 already closed.

`BaseException` is deliberately not caught. A `KeyboardInterrupt` is not a
response.

**The cost, stated plainly:** a defect inside the Kernel reaches the
caller as an `ERROR` response rather than as a crash. That is the trade a
boundary makes, and it is mitigated by carrying the type name verbatim —
nothing is anonymised, and a caller can tell `InvalidReceipt` from
`LedgerUnavailable` without a stack trace. Recorded as **R52**.

## Determinism

**No `uuid4()`, no clock, no request id, no correlation of its own.** A
response is a pure function of the operation and what the Kernel returned,
so two APIs over two identically-seeded Kernels produce **equal
responses** — the same property §14 R2 requires of the Kernel, extended
across the boundary rather than broken by it.

There is no retry here (§3.4 gives retry mechanics to the Runtime, and
C16 is where they live), no queue, no thread, no background worker and no
buffering. §11.3's *"no buffering"* is a Kernel rule, and a transport that
buffered on its behalf would defeat it from one layer up.

## What it deliberately does not expose

**`ExecutionCoordinator.run()`.** C16 is available and is not wired here:
§3.5 fixes the surface at four operations, and the brief for this
component permits *"no additional public behaviour."* A fifth operation on
this boundary would be a second way to execute, which is the thing one
door exists to prevent. A caller that wants the composed sequence
constructs a Coordinator over the same Kernel.

**Deserialisation.** `authorize()` takes an `ExecutionRequest` and
`settle()` takes an `ExecutionOutcome` — the Foundation values themselves,
never a dictionary to be assembled here. ADR-0022 D2 makes the caller *"a
courier, not an author"* for the reversibility class, and a boundary that
built the request from wire fields would become that author. Foundation is
shared vocabulary; the Kernel is not, and it is the Kernel this door
closes.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

from master_agent.foundation.attempt_token import AttemptToken
from master_agent.foundation.execution_request import ExecutionRequest
from master_agent.foundation.receipt import ExecutionOutcome, Receipt
from master_agent.foundation.refusal import KernelRefusal
from master_agent.foundation.warrant import Warrant
from master_agent.kernel import Kernel


class Operation(str, Enum):
    """What was called. Closed, and closed for the same reason §3.5's
    surface is: a fifth operation is a change to what the Kernel is."""

    AUTHORIZE = "authorize"
    ATTEMPT = "attempt"
    SETTLE = "settle"
    INVALIDATE = "invalidate"

    #: §3.3's two owned facts, read. Not a fifth Kernel operation — the
    #: Kernel already exposes both as properties, and this projects them.
    STATUS = "status"


class ResultKind(str, Enum):
    """Which of the three things happened.

    Three, not seven. The operation says what was asked; this says only
    whether the Kernel answered, refused, or raised — and a caller that
    knows which operation it called knows how to read the payload.
    """

    #: The Kernel answered. The payload is the value's own projection.
    OK = "ok"

    #: The Kernel refused. §7.5 — a decision it made and must record.
    REFUSED = "refused"

    #: The Kernel raised. Carried across as data rather than as a
    #: traceback, with its own class name intact.
    ERROR = "error"


class InvalidKernelApi(ValueError):
    """Raised at construction for an API with nothing to project.

    At construction, never at call time — the discipline `InvalidKernel`
    and `InvalidCoordinator` both follow.
    """


@dataclass(frozen=True)
class ApiResponse:
    """One answer, in the only shape this boundary produces. Immutable.

    Carries no id, no timestamp and no sequence: §14 R2's determinism
    property survives a boundary only if the boundary adds nothing that
    varies between two identical runs.
    """

    #: Which of §3.5's operations was called.
    operation: Operation

    #: Whether the Kernel answered, refused, or raised.
    kind: ResultKind

    #: The value's own `as_dict()`, unaltered. Never composed here.
    payload: dict[str, Any]

    @property
    def ok(self) -> bool:
        """Whether the Kernel answered.

        A refusal is not an error and an error is not a refusal — §7.5
        keeps them apart, and so does this.
        """
        return self.kind is ResultKind.OK

    @property
    def refused(self) -> bool:
        return self.kind is ResultKind.REFUSED

    def as_dict(self) -> dict[str, Any]:
        """A deterministic, JSON-ready projection. Fixed key order."""
        return {
            "operation": self.operation.value,
            "kind": self.kind.value,
            "payload": self.payload,
        }


class KernelApi:
    """The four operations, and the two facts §3.3 says the Kernel owns.

    One collaborator, no state. Two APIs over one Kernel are
    indistinguishable, because nothing that outlives a call lives here.
    """

    __slots__ = ("_kernel",)

    def __init__(self, kernel: Kernel) -> None:
        if not isinstance(kernel, Kernel):
            raise InvalidKernelApi(
                "kernel must be the Kernel; this boundary projects §3.5's "
                "four operations and there is no other source for any of "
                "them"
            )
        self._kernel: Kernel = kernel

    # ---- §3.5 · the four operations -----------------------------------

    def authorize(self, request: ExecutionRequest) -> ApiResponse:
        """Project `Kernel.authorize()`.

        The request crosses as the Foundation value it already is —
        ADR-0022 D2's courier discipline stops at the caller, and a
        boundary that assembled one would be the author it forbids.
        """
        return self._dispatch(
            Operation.AUTHORIZE, lambda: self._kernel.authorize(request)
        )

    def attempt(self, warrant_id: str) -> ApiResponse:
        """Project `Kernel.attempt()`.

        Refuses through §11.3's ledger path and raises through
        `AttemptNotAuthorized`; both cross as data, in different kinds.
        """
        return self._dispatch(
            Operation.ATTEMPT, lambda: self._kernel.attempt(warrant_id)
        )

    def settle(self, warrant_id: str, outcome: ExecutionOutcome) -> ApiResponse:
        """Project `Kernel.settle()`.

        §3.5 gives settlement no refusal channel, so this operation
        produces `OK` or `ERROR` and never `REFUSED`.
        """
        return self._dispatch(
            Operation.SETTLE, lambda: self._kernel.settle(warrant_id, outcome)
        )

    def invalidate(self, scope: str, reason: str) -> ApiResponse:
        """Project `Kernel.invalidate()`.

        **No confirmation parameter, and there will never be one** —
        §11.8 and VEDA 04 A3 forbid it, and a boundary is exactly where
        one would be added for the surface's convenience.
        """
        return self._dispatch(
            Operation.INVALIDATE,
            lambda: self._kernel.invalidate(scope, reason),
        )

    # ---- §3.3 · the two facts the Kernel owns -------------------------

    def status(self) -> ApiResponse:
        """The override switch and the outstanding count.

        §3.3 gives the Kernel two pieces of state and it already exposes
        both as read-only properties. This projects them and derives
        nothing.

        §7.5 is why these two and no others: *"Under an active Override, a
        thousand refusals are one state — 'autonomy is suspended; 1,000
        actions are waiting' — not a thousand queue items."* That sentence
        needs exactly a switch and a count.

        **It is not a badge.** Roadmap §2 C21 refuses *"no objective
        count, no progress bar, no badge"*, and what a surface may say
        about these numbers is C20's and C21's question, not this one's.
        """
        return self._dispatch(
            Operation.STATUS,
            lambda: {
                "override": self._kernel.override.as_dict(),
                "outstanding": self._kernel.outstanding_count,
            },
        )

    # ---- the whole of the transport -----------------------------------

    def _dispatch(
        self, operation: Operation, call: Callable[[], Any]
    ) -> ApiResponse:
        """Call the Kernel, and turn what came back into a response.

        The only logic in this module, and it is mapping rather than
        deciding: which branch is taken is determined entirely by the type
        of what the Kernel returned or raised.
        """
        try:
            answer = call()
        except Exception as exc:  # noqa: BLE001 — see the module docstring
            return ApiResponse(
                operation=operation,
                kind=ResultKind.ERROR,
                payload={"type": type(exc).__name__, "message": str(exc)},
            )

        if isinstance(answer, KernelRefusal):
            return ApiResponse(
                operation=operation,
                kind=ResultKind.REFUSED,
                payload=answer.as_dict(),
            )

        return ApiResponse(
            operation=operation, kind=ResultKind.OK, payload=_project(answer)
        )


def _project(answer: Any) -> dict[str, Any]:
    """The value's own projection, never a new one.

    Each branch names the component that owns the shape. `int` is
    `invalidate()`'s count, which §3.5 returns bare and which needs a key
    to be a payload — that key is the only name this module contributes to
    the wire, and it is the specification's own word.
    """
    if isinstance(answer, (Warrant, AttemptToken, Receipt)):
        return answer.as_dict()
    if isinstance(answer, int):
        return {"count": answer}
    return answer
