"""The serialization boundary — and the resolution of R53.

## What R53 was

C17's health report recorded it:

> *"The transport is in-process. Outbound is fully JSON-ready. Inbound is
> not: `authorize()` takes an `ExecutionRequest` and `settle()` takes an
> `ExecutionOutcome`, both Foundation values. A surface in a separate
> process therefore cannot yet call this API. It would need a deserialiser
> for `ExecutionRequest`, `Attestation` and `Consequence`, none of which
> exists — and building one **there** would make that boundary the author
> of `reversibility_class`, which ADR-0022 D2 forbids."*

## Why this module resolves it, and the Kernel API could not

ADR-0022 D2 names the roles:

> ```
>    caller ──► ReversibilityRegistry.classify(capability) ──► Classification
>           ──► ExecutionRequest(reversibility_class=classification.cls, …)
>           ──► Kernel.authorize(request)
> ```
> *"Both the value and the attestation come from **C12, the owner §4.3
> names**. **The caller is a courier, not an author.**"*

**The Runtime is the caller.** It is the component that stands between a
surface and the Kernel API, and assembling a request from what a surface
sent is exactly what a courier does: it carries a value it did not decide.

The Kernel API is **not** the caller — it is the Kernel's own projection,
one layer below. A decoder there would put request construction inside the
authority's own boundary, which is the thing D2's discipline exists to
keep apart. So the decoder lives here, one layer up, and the Kernel API is
unchanged.

**Neither this module nor the Runtime originates a `reversibility_class`.**
It arrives on the wire, from a surface that obtained it from C12 per D2.
Carrying a value across a boundary is not authoring it — the same
relationship a courier has to a sealed envelope. What this module adds is
zero: no default, no inference, no fallback. A payload without the field
fails to decode.

## The division this module keeps

C9 states it, and the two halves must not merge:

> *"The Kernel refuses requests on constitutional grounds and records
> those refusals; a request that is merely **malformed** is not a
> constitutional refusal and must not become one, or the ledger fills with
> records of callers getting the shape wrong."*

| Failure | Raises |
|---|---|
| **Transport** — a key is missing, or a value is not a member of a closed vocabulary | `InvalidEnvelope` |
| **Constitutional** — a blank capability, a stale attestation, a null consequence | the value's own error, **untouched** |

The dict lookups and enum conversions happen inside one guarded step; the
Foundation value is constructed **outside** it. So no constitutional error
is ever wrapped, renamed or hidden behind a transport one.

## What it validates

**Nothing.** Every Foundation value in this system validates at
construction — C4, C5, C6, C7, C9 each refuse to exist in a state they
should not be in. A decoder that checked the same things would be the
duplicated validation §1.2 forbids one layer up, and it would drift.

This module's whole job is **shape to value**. The values decide whether
they are legal.

## Precedent

`ledger/receipt_ledger.py` already decodes `Consequence`, `IntentRecord`,
`AttemptRecord` and `Receipt` from dictionaries, in the component that
consumes them rather than in `foundation/`. This follows that shape
exactly: **Foundation writes projections; consumers read them.** No
`from_dict` is added to any frozen value.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from typing import Any

from master_agent.foundation.attestation import (
    Attestation,
    AttestationQuestion,
    AttestationVerdict,
)
from master_agent.foundation.consequence import Consequence, Cost, CostBasis
from master_agent.foundation.execution_request import (
    PENDING_CONSEQUENCE_ENGINE,
    ActionClass,
    ExecutionRequest,
    PendingConsequenceEngine,
)
from master_agent.foundation.receipt import ExecutionOutcome
from master_agent.foundation.warrant import ReversibilityClass


class InvalidEnvelope(ValueError):
    """The transport payload could not be read as the value it claims.

    A **shape** failure, never a constitutional one. §7.5's refusals and
    C9's `InvalidExecutionRequest` both describe requests the system
    understood; this describes one it could not read.

    Deliberately raised only from the guarded lookup step, so an
    `InvalidExecutionRequest` — a real constitutional answer — is never
    caught and re-labelled as a wire problem.
    """


# ---- encoding · the value's own projection, never a new one -----------


def encode_request(request: ExecutionRequest) -> dict[str, Any]:
    """C9's own `as_dict()`, unaltered.

    Nothing is added, renamed or reordered. The encoder exists so that the
    boundary has a named pair — and so a round-trip test means something —
    not because there is a second shape to produce.
    """
    return request.as_dict()


def encode_outcome(outcome: ExecutionOutcome) -> str:
    """§6.3's four kinds, as C5 already writes them."""
    return outcome.value


# ---- decoding · shape to value ----------------------------------------


def decode_request(payload: Mapping[str, Any]) -> ExecutionRequest:
    """Assemble the Foundation value a surface sent.

    The lookups and enum conversions are guarded; **the construction is
    not**. `ExecutionRequest.__post_init__` is what decides whether the
    request is legal, and its verdict crosses this boundary untouched.
    """
    fields = _request_fields(payload)
    return ExecutionRequest(**fields)


def decode_outcome(value: Any) -> ExecutionOutcome:
    """One of §6.3's four kinds, or nothing.

    C5's vocabulary is closed — *"an outcome that does not fit one of
    these is not a fifth kind, it is a caller who has not finished
    deciding what happened."*
    """
    return _member(ExecutionOutcome, value, "outcome")


def _request_fields(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Every field C9 declares, read from the wire and converted.

    `target_ref` and `attestations` are the two C9 gives defaults, so they
    are the two read as optional. Every other field is required, and a
    payload missing one does not decode — **including
    `reversibility_class`**, which ADR-0022 D1 makes *"required, with no
    default: a default would be a guessed class."*
    """
    if not isinstance(payload, Mapping):
        raise InvalidEnvelope(
            "a request payload must be a mapping of C9's own field names"
        )

    return {
        "objective_id": _required(payload, "objective_id"),
        "principal_id": _required(payload, "principal_id"),
        "capability": _required(payload, "capability"),
        "payload_digest": _required(payload, "payload_digest"),
        "action_class": _member(
            ActionClass, _required(payload, "action_class"), "action_class"
        ),
        "reversibility_class": _member(
            ReversibilityClass,
            _required(payload, "reversibility_class"),
            "reversibility_class",
        ),
        "expected_effect": _required(payload, "expected_effect"),
        "consequence": _decode_consequence(_required(payload, "consequence")),
        "target_ref": payload.get("target_ref"),
        "attestations": tuple(
            _decode_attestation(item)
            for item in payload.get("attestations") or ()
        ),
    }


def _decode_attestation(payload: Any) -> Attestation:
    """One of §7.3's answers, as C7 projects it.

    Constructed outside the guard for the same reason a request is: C7
    refuses a mis-attributed or naive-timestamped attestation, and that
    refusal is evidence rather than a wire problem.
    """
    if not isinstance(payload, Mapping):
        raise InvalidEnvelope("an attestation must be a mapping")

    fields = {
        "question": _member(
            AttestationQuestion, _required(payload, "question"), "question"
        ),
        "attestor": _required(payload, "attestor"),
        "subject": _required(payload, "subject"),
        "verdict": _member(
            AttestationVerdict, _required(payload, "verdict"), "verdict"
        ),
        "attested_at": _moment(_required(payload, "attested_at")),
        "reason": payload.get("reason"),
    }
    return Attestation(**fields)


def _decode_consequence(
    payload: Any,
) -> Consequence | PendingConsequenceEngine:
    """The quartet, or §14.1's marker.

    The marker's wire form is the literal string
    `"pending_consequence_engine"`, which is what C9 writes and what C13
    already reads back. **Never null, never omitted, never a partial
    quartet.**
    """
    if payload == PENDING_CONSEQUENCE_ENGINE.as_dict():
        return PENDING_CONSEQUENCE_ENGINE

    if not isinstance(payload, Mapping):
        raise InvalidEnvelope(
            "consequence must be the quartet or the "
            f"{PENDING_CONSEQUENCE_ENGINE.as_dict()!r} marker; it is never "
            "null, never omitted and never a partial quartet"
        )

    cost = _required(payload, "cost")
    if not isinstance(cost, Mapping):
        raise InvalidEnvelope("cost must be a mapping")
    amount = cost.get("amount")

    return Consequence(
        what_changes=_required(payload, "what_changes"),
        cost=Cost(
            description=_required(cost, "description"),
            basis=_member(CostBasis, _required(cost, "basis"), "basis"),
            amount=None if amount is None else _amount(amount),
            currency=cost.get("currency"),
        ),
        if_nothing=_required(payload, "if_nothing"),
        reversibility=_member(
            ReversibilityClass,
            _required(payload, "reversibility"),
            "reversibility",
        ),
    )


# ---- the guarded lookup step ------------------------------------------


def _required(payload: Mapping[str, Any], key: str) -> Any:
    """A field the wire must carry. Absence is a shape failure."""
    if key not in payload:
        raise InvalidEnvelope(f"the payload carries no {key!r}")
    return payload[key]


def _member(enum: Any, value: Any, field: str) -> Any:
    """A member of a closed vocabulary, or nothing.

    Every enum this decodes is closed by a frozen component, and a value
    outside one is a caller sending a word the constitution does not have.
    """
    try:
        return enum(value)
    except (ValueError, KeyError) as exc:
        allowed = ", ".join(sorted(member.value for member in enum))
        raise InvalidEnvelope(
            f"{field} must be one of: {allowed}; got {value!r}"
        ) from exc


def _moment(value: Any) -> datetime:
    """An ISO-8601 instant. C7 refuses a naive one; this only parses."""
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise InvalidEnvelope(
            f"attested_at must be an ISO-8601 timestamp; got {value!r}"
        ) from exc


def _amount(value: Any) -> Decimal:
    """A cost, carried as a string so no precision is lost crossing JSON.

    C6 renders it that way — *"`amount` renders as a string so no
    precision is lost crossing JSON, where every number is a float"* — and
    reading it back through `Decimal` is what makes the round trip exact.
    """
    try:
        return Decimal(str(value))
    except (ArithmeticError, TypeError, ValueError) as exc:
        raise InvalidEnvelope(
            f"cost amount must be a decimal string; got {value!r}"
        ) from exc
