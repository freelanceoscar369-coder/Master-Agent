"""Runtime Integration Layer — the bridge, and nothing but the bridge.

```
   Desktop UI · CLI · future services
        │
        ▼
   Runtime          ← serialization · transport · wiring
        │
        ▼
   Kernel API       ← projection (C17)
        │
        ▼
   Kernel           ← the authority (C15)
```

## What it is

> **A courier with no opinions.** It carries a request down and an answer
> back. Every decision on the way is made below it.

ADR-0022 D2 names the role and this component fills it: *"the caller is a
courier, not an author."* The Runtime assembles an `ExecutionRequest` from
what a surface sent — carrying a `reversibility_class` a surface obtained
from C12, never originating one — and hands the Foundation value to the
Kernel API unchanged.

## What it is forbidden to do, and how each is prevented

| Never | Prevented by |
|---|---|
| Make a business decision | No branch the operation name did not put here |
| Create Kernel state | It constructs no `Warrant`, `AttemptToken`, `Receipt` or ledger record |
| Duplicate authorization | §7.2's checks are never read here; `authorize` is one delegation |
| Duplicate settlement | `settle` is one delegation, and no outcome is inferred |
| Duplicate execution logic | The §6.1 sequence is C16's; `execute()` delegates to it |

## Two doors, because a callable cannot cross a wire

**`handle(envelope)` — the transport door.** Dictionaries in, dictionaries
out. This is what a surface in any process uses, and it is the only door
that serializes.

**`execute(request, work)` — the in-process door.** §6.1's third line is
*"the caller's own execution, entirely its own business"*, and C16 takes
it as a callable. A callable has no wire representation, so the composed
sequence is reachable in-process and not over a transport. **Stated rather
than worked around:** a remote surface obtains a warrant and a token
through `handle()` and executes on its own side, which is exactly the
arrangement §6.1 describes.

## The wire shape

One envelope in, one envelope out, and the outbound shape is C17's own:

```
   in    {"operation": "authorize", "arguments": {"request": {…}}}
   out   {"operation": "authorize", "kind": "ok", "payload": {…}}
```

`kind` is `ResultKind` and `operation` is `Operation`, both C17's and
neither extended. **No status code, no envelope version, no request id, no
timestamp** — §14 R2's determinism survives a boundary only if the
boundary adds nothing that varies, and a wire field nobody reads is a
field somebody will eventually depend on.

The arguments map uses the Kernel API's **own parameter names** —
`request`, `warrant_id`, `outcome`, `scope`, `reason` — so there is no
translation table to drift.

## Where the two kinds of failure go

A malformed envelope and a malformed request are different things, and C9
insists they stay different:

> *"A request that is merely malformed is not a constitutional refusal and
> must not become one, or the ledger fills with records of callers getting
> the shape wrong."*

Both arrive as `kind: "error"` carrying their **own class name** —
`InvalidEnvelope` for the wire, `InvalidExecutionRequest` for the value —
so a caller can tell them apart without a traceback. Nothing is grouped
into a transport taxonomy; that is C17's convention, followed here.

`BaseException` is not caught. A `KeyboardInterrupt` is not a response.

## Determinism

**No clock, no `uuid4()`, no request id, no retry, no queue, no thread, no
background worker, no buffering.** The transport is a function call, and
§11.3's *"no buffering"* is a Kernel rule a bridge must not defeat from
above.

## Lifecycle

The Runtime owns **composition and nothing else**: given one Kernel, it
constructs the Kernel API and the Execution Coordinator over it and holds
them for its own life. It creates no Kernel, opens no resource, starts
nothing and stops nothing — so there is no `start()`, no `close()` and no
state to leak. The lifecycle that matters is §4.5's, and that one belongs
to the Kernel.

## Placement

`master_agent/runtime_bridge/`, deliberately **not** inside
`master_agent/runtime/`. That package is the shipped Runtime Engine
(MB024) and importing through its `__init__` would give this module a
dependency the brief forbids. Nothing here imports it, and a test asserts
so.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from master_agent.api import ApiResponse, KernelApi, Operation, ResultKind
from master_agent.coordinator import Execution, ExecutionCoordinator, Work
from master_agent.foundation.execution_request import ExecutionRequest
from master_agent.kernel import Kernel
from master_agent.runtime_bridge.codec import (
    InvalidEnvelope,
    decode_outcome,
    decode_request,
)

#: The envelope key naming which of §3.5's operations is asked for.
OPERATION = "operation"

#: The envelope key carrying the operation's arguments, by the Kernel
#: API's own parameter names.
ARGUMENTS = "arguments"


class InvalidRuntime(ValueError):
    """Raised at construction for a Runtime with nothing to bridge.

    At construction, never at call time — the discipline `InvalidKernel`,
    `InvalidCoordinator` and `InvalidKernelApi` all follow.
    """


class Runtime:
    """The bridge. One Kernel in, two doors out.

    Holds the Kernel API and the Coordinator it wired, and no state of its
    own. Two Runtimes over one Kernel are indistinguishable.
    """

    __slots__ = ("_api", "_coordinator")

    def __init__(self, kernel: Kernel) -> None:
        if not isinstance(kernel, Kernel):
            raise InvalidRuntime(
                "kernel must be the Kernel; a bridge with nothing on the "
                "far side is a surface pretending to have authority"
            )
        self._api: KernelApi = KernelApi(kernel)
        self._coordinator: ExecutionCoordinator = ExecutionCoordinator(kernel)

    # ---- the transport door -------------------------------------------

    def handle(self, envelope: Mapping[str, Any]) -> dict[str, Any]:
        """Read one envelope, answer with one envelope.

        The only method that serializes. Every branch below is selected by
        the operation name and by nothing else — there is no decision here
        that a caller did not already make.
        """
        raw = _raw_operation(envelope)
        try:
            operation = _operation_of(envelope)
            response = self._invoke(operation, _arguments_of(envelope))
        except Exception as exc:  # noqa: BLE001 — see the module docstring
            return _error_envelope(raw, exc)
        return response.as_dict()

    def _invoke(
        self, operation: Operation, arguments: Mapping[str, Any]
    ) -> ApiResponse:
        """Delegate. One line per operation, and no line between them.

        `decode_request` and `decode_outcome` are the whole of what this
        adds, and both are shape-to-value with no validation of their own.
        """
        if operation is Operation.AUTHORIZE:
            return self._api.authorize(
                decode_request(_argument(arguments, "request"))
            )
        if operation is Operation.ATTEMPT:
            return self._api.attempt(_argument(arguments, "warrant_id"))
        if operation is Operation.SETTLE:
            return self._api.settle(
                _argument(arguments, "warrant_id"),
                decode_outcome(_argument(arguments, "outcome")),
            )
        if operation is Operation.INVALIDATE:
            return self._api.invalidate(
                _argument(arguments, "scope"), _argument(arguments, "reason")
            )
        return self._api.status()

    # ---- the in-process door ------------------------------------------

    def execute(self, request: ExecutionRequest, work: Work) -> Execution:
        """§6.1's sequence, run by C16.

        A pure delegation. The order, the retry bound and the mandatory
        settlement are the Coordinator's, and duplicating any of them here
        would give the system two answers about §6.3.

        Not reachable through `handle()`: `work` is a callable and a
        callable has no wire representation. A remote surface obtains a
        warrant and a token through the transport door and executes on its
        own side, which is the arrangement §6.1 already describes.
        """
        return self._coordinator.run(request, work)


# ---- envelope reading --------------------------------------------------


def _raw_operation(envelope: Any) -> Any:
    """Whatever the envelope called its operation, before it is trusted.

    Read separately so an error envelope can echo it back even when it
    names nothing this system has.
    """
    if isinstance(envelope, Mapping):
        return envelope.get(OPERATION)
    return None


def _operation_of(envelope: Any) -> Operation:
    if not isinstance(envelope, Mapping):
        raise InvalidEnvelope(
            f"an envelope is a mapping with {OPERATION!r} and "
            f"{ARGUMENTS!r}; got {type(envelope).__name__}"
        )
    if OPERATION not in envelope:
        raise InvalidEnvelope(f"the envelope names no {OPERATION!r}")

    value = envelope[OPERATION]
    try:
        return Operation(value)
    except (ValueError, KeyError) as exc:
        allowed = ", ".join(sorted(member.value for member in Operation))
        raise InvalidEnvelope(
            f"operation must be one of: {allowed}; got {value!r}"
        ) from exc


def _arguments_of(envelope: Mapping[str, Any]) -> Mapping[str, Any]:
    """The arguments map. Absent is empty — `status()` takes none."""
    arguments = envelope.get(ARGUMENTS) or {}
    if not isinstance(arguments, Mapping):
        raise InvalidEnvelope(
            f"{ARGUMENTS!r} must be a mapping of the operation's own "
            "parameter names"
        )
    return arguments


def _argument(arguments: Mapping[str, Any], name: str) -> Any:
    if name not in arguments:
        raise InvalidEnvelope(f"the envelope carries no {name!r} argument")
    return arguments[name]


def _error_envelope(operation: Any, exc: Exception) -> dict[str, Any]:
    """A failure, in the shape every other answer uses.

    C17's convention, followed rather than restated: the exception keeps
    its **own class name**, because a boundary that renamed it would
    invent a vocabulary parallel to the one C8 already closed.

    `operation` echoes what the envelope said. It is `None` when the
    envelope named nothing, and it is **not** coerced into an `Operation`
    — that enum is closed, and a word this system does not have must not
    be given one of its names.
    """
    return {
        OPERATION: operation,
        "kind": ResultKind.ERROR.value,
        "payload": {"type": type(exc).__name__, "message": str(exc)},
    }
