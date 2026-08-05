"""Kernel Refusal — why the Kernel did not mint, in a shape a caller can act on.

Constitutional Kernel Specification §7.5:

> *"A refusal names the check that failed, the attestor, and whether it is
> remediable. **Refusals are data, not exceptions** — the shape the Broker's
> `refusal.py` already established, and for the same stated reason: 'the
> founder is reading a stack trace from a provider SDK instead of a sentence
> about their own machine.'"*

Two of the Kernel's four operations return one. §3.5:

```
  authorize(ExecutionRequest) → Intent | Refusal
  attempt(intent_id)          → AttemptToken | Refusal
```

## Why it is `KernelRefusal` and not `Refusal`

`BrokerRefusal` (`ai_infrastructure/refusal.py`) and `PlanRefusal`
(`planner/plan.py`) already exist. A bare third `Refusal` would repeat the
`Intent` collision Objective Engine Specification §13.1 documents. The
qualifier is not decoration — three unqualified refusals in one codebase is
how a reader stops being able to tell which authority spoke.

## Three families, not one

§11.10 enumerates nine failure conditions and most are not attestation
failures. Roadmap Amendment 001 M5 sorts them:

| Family | Members |
|---|---|
| Kernel checks | K1 objective · K2 override · K3 ledger write (§7.2) |
| Attestation failures | any of the eight questions (§7.3) |
| Infrastructure | permission system · tool/worker · provider · kernel (§11) |

A `RefusalReason` covering only attestations would leave *"the ledger is
down"* and *"autonomy is suspended"* unrepresentable — and §7.5 requires
that refusals are **recorded**, so an unrepresentable refusal is an
unrecordable one.

Two of §11.10's nine conditions are deliberately absent. **Network
unavailable** is `DEGRADED`, not refused (§11.7 — the Kernel decides
nothing there), and **learning unavailable** proceeds (§11.4). Neither is a
refusal, so neither has a reason here.

## The attestor is optional, and the reason is that K-checks have none

§7.2's three checks are *"checks the Kernel performs itself… Each is a
question about the Kernel's own domain. No other component owns it."* A
refusal from K1 has no attestor because no attestor was involved. Making
`attestor` required would force the Kernel to invent one, and an invented
attestor is a false attribution in a record kept forever. See ED-024.

## What this deliberately is not

**A refusal is not a judgment request.** §7.5: *"Under an active Override, a
thousand refusals are one state — 'autonomy is suspended; 1,000 actions are
waiting' — not a thousand queue items."* So there is no id, no assignee, no
priority, no count and no timestamp on this value. Every one of those would
be the beginning of a queue, and VEDA 03 abolishes the inbox.

**A refusal is not an utterance.** It carries `detail`, which the caller
supplies. It composes no founder-facing sentence, because C20's Voice
Charter Validator owns every outbound utterance and nothing may reach the
founder un-validated.

## Dependencies

`AttestationQuestion` from Component 7, and nothing else — not `Attestation`
itself. A refusal names *which question* failed, never the attestation
object, which is why this stays a flat record with no nested value to
serialise. Roadmap Amendment 001 M5.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from master_agent.foundation.attestation import AttestationQuestion


class KernelCheck(str, Enum):
    """The three checks the Kernel performs itself. Kernel Spec §7.2.

    *"Exactly three… Each is a question about the Kernel's own domain. No
    other component owns it."* The vocabulary is closed for the same reason
    `AttestationQuestion` is: a fourth Kernel-owned check is a change to what
    the Kernel is, which is a constitutional decision rather than a code
    change.

    Declaration order is §7.1's ordering — *"cheapest-and-most-fundamental
    first"* — but this enum only names the checks. Running them in order is
    the Kernel's business (C15).
    """

    #: K1 — `objective_id` present, resolves to an admitted objective in a
    #: non-terminal state. The constitutional anchor: delegating it to an
    #: attestation would make "no execution without an objective"
    #: attestable-away.
    K1_OBJECTIVE_BINDING = "k1_objective_binding"

    #: K2 — global suspension is not active. The Override's meaning *is*
    #: "the Kernel stops minting"; no other component can express that.
    K2_OVERRIDE_STATE = "k2_override_state"

    #: K3 — the receipt intent write. Runs last, after every other check has
    #: passed. VEDA 04 A1: *"if the intent write fails, the action does not
    #: occur. No exceptions, no buffering, no fire-and-forget."*
    K3_RECEIPT_INTENT_WRITE = "k3_receipt_intent_write"


class RefusalFamily(str, Enum):
    """Which kind of thing failed. Roadmap Amendment 001 M5.

    The Dashboard needs this to honour §7.5's *"a thousand refusals are one
    state"*: refusals collapse by family and reason, never by instance.
    """

    KERNEL_CHECK = "kernel_check"
    ATTESTATION = "attestation"
    INFRASTRUCTURE = "infrastructure"


class RefusalReason(str, Enum):
    """Why the Kernel refused. Closed, and spanning all three families.

    Each member is one condition from §7.2 or §11.10, kept separate when the
    remedy differs — *"each one has a different answer for the founder, which
    is the whole reason they are separate values"* (`BrokerRefusal`'s own
    reasoning, and the precedent this follows).
    """

    # ---- Family 1 · the Kernel's own checks (§7.2) --------------------

    #: K1, first condition: no `objective_id` was supplied. §11.2 — *"an
    #: action with no objective is not a delayed action, it is an
    #: unauthorized one."*
    OBJECTIVE_MISSING = "objective_missing"

    #: K1, second condition: the `objective_id` does not resolve.
    OBJECTIVE_UNKNOWN = "objective_unknown"

    #: K1, third condition: the objective is already completed, failed, or
    #: cancelled. §7.2 requires a **non-terminal** state.
    OBJECTIVE_TERMINAL = "objective_terminal"

    #: K2: global suspension is active. §11.8 — work and queueing continue;
    #: only deciding stops.
    OVERRIDE_ACTIVE = "override_active"

    #: K3: the intent write did not succeed. §11.3 — fail closed, no
    #: buffering.
    LEDGER_UNAVAILABLE = "ledger_unavailable"

    # ---- Family 2 · attestation failures (§7.3) -----------------------

    #: The attestation the Kernel required was not there to verify. §7.3:
    #: one that is *"missing, stale, or subject-mismatched"* is **treated as
    #: absent**, so all three arrive here and `detail` says which. See
    #: ED-025.
    ATTESTATION_ABSENT = "attestation_absent"

    #: The attestor answered, and the answer was no. §7.3: the Kernel
    #: *"never re-derives the verdict"* — it carries this one through.
    ATTESTATION_REFUSED = "attestation_refused"

    # ---- Family 3 · infrastructure (§11) ------------------------------

    #: §11.1 — cannot verify authority ⇒ no authority. No cache, no grace
    #: period, no "it was granted a minute ago."
    PERMISSION_SYSTEM_UNAVAILABLE = "permission_system_unavailable"

    #: §11.5 — refused **before** minting. An intent for an action nothing
    #: can perform is a real authorization for an impossible action.
    TOOL_OR_WORKER_UNAVAILABLE = "tool_or_worker_unavailable"

    #: §11.6 — no `DecisionRecord` ⇒ A7 absent ⇒ refuse. The Kernel does not
    #: override the Broker and does not add a second opinion.
    PROVIDER_UNAVAILABLE = "provider_unavailable"

    #: §11.9 — nothing executes. Stated rather than mitigated. No check was
    #: reached, so this is the one reason with no `failed_check`.
    KERNEL_UNAVAILABLE = "kernel_unavailable"

    @property
    def family(self) -> RefusalFamily:
        return _FAMILY[self]


_FAMILY: dict[RefusalReason, RefusalFamily] = {
    RefusalReason.OBJECTIVE_MISSING: RefusalFamily.KERNEL_CHECK,
    RefusalReason.OBJECTIVE_UNKNOWN: RefusalFamily.KERNEL_CHECK,
    RefusalReason.OBJECTIVE_TERMINAL: RefusalFamily.KERNEL_CHECK,
    RefusalReason.OVERRIDE_ACTIVE: RefusalFamily.KERNEL_CHECK,
    RefusalReason.LEDGER_UNAVAILABLE: RefusalFamily.KERNEL_CHECK,
    RefusalReason.ATTESTATION_ABSENT: RefusalFamily.ATTESTATION,
    RefusalReason.ATTESTATION_REFUSED: RefusalFamily.ATTESTATION,
    RefusalReason.PERMISSION_SYSTEM_UNAVAILABLE: RefusalFamily.INFRASTRUCTURE,
    RefusalReason.TOOL_OR_WORKER_UNAVAILABLE: RefusalFamily.INFRASTRUCTURE,
    RefusalReason.PROVIDER_UNAVAILABLE: RefusalFamily.INFRASTRUCTURE,
    RefusalReason.KERNEL_UNAVAILABLE: RefusalFamily.INFRASTRUCTURE,
}

#: Which check each reason may name. Every entry is a specification line,
#: not a convention:
#:
#: * the three K-reasons pair one-to-one with §7.2's three checks;
#: * an attestation failure may name any of §7.3's eight questions;
#: * §11.1 places the Permission System's answer at A3, §11.6 places the
#:   Provider's at A7, and §11.5 refuses *"at A1/A6 attestation"*;
#: * §11.9 is refused before any check runs, so it names none.
#:
#: `None` inside a set means "this reason may carry no check"; it appears
#: for exactly one reason.
_PERMITTED_CHECKS: dict[
    RefusalReason, frozenset[KernelCheck | AttestationQuestion | None]
] = {
    RefusalReason.OBJECTIVE_MISSING: frozenset({KernelCheck.K1_OBJECTIVE_BINDING}),
    RefusalReason.OBJECTIVE_UNKNOWN: frozenset({KernelCheck.K1_OBJECTIVE_BINDING}),
    RefusalReason.OBJECTIVE_TERMINAL: frozenset({KernelCheck.K1_OBJECTIVE_BINDING}),
    RefusalReason.OVERRIDE_ACTIVE: frozenset({KernelCheck.K2_OVERRIDE_STATE}),
    RefusalReason.LEDGER_UNAVAILABLE: frozenset(
        {KernelCheck.K3_RECEIPT_INTENT_WRITE}
    ),
    RefusalReason.ATTESTATION_ABSENT: frozenset(AttestationQuestion),
    RefusalReason.ATTESTATION_REFUSED: frozenset(AttestationQuestion),
    RefusalReason.PERMISSION_SYSTEM_UNAVAILABLE: frozenset(
        {AttestationQuestion.PERMISSION}
    ),
    RefusalReason.TOOL_OR_WORKER_UNAVAILABLE: frozenset(
        {AttestationQuestion.TASK_READY, AttestationQuestion.PAYLOAD_SCHEMA}
    ),
    RefusalReason.PROVIDER_UNAVAILABLE: frozenset({AttestationQuestion.PROVIDER}),
    RefusalReason.KERNEL_UNAVAILABLE: frozenset({None}),
}


class InvalidKernelRefusal(ValueError):
    """Raised at construction for a refusal that could not account for itself.

    At construction, never at read time. A refusal is recorded (§7.5) and
    read years later by an audit; one that names the wrong check, or names no
    check at all, is worse than no record because it looks like evidence.
    """


@dataclass(frozen=True)
class KernelRefusal:
    """Why nothing was minted, in the three parts §7.5 requires.

    Immutable and hashable. Two refusals with identical fields are the same
    refusal — which is what lets a thousand of them collapse into one state.
    """

    #: Which condition occurred.
    reason: RefusalReason

    #: Which check failed. A K-check when the Kernel refused on its own
    #: ground, one of the eight questions when an attestation did, and
    #: `None` only when the Kernel itself was unavailable and no check ran.
    failed_check: KernelCheck | AttestationQuestion | None

    #: The component that answered, or should have. `None` for a K-check:
    #: §7.2's three are the Kernel's own domain and no attestor is involved.
    attestor: str | None

    #: Whether something can be done that would let the same request
    #: succeed. Required and explicit — never defaulted, because the most
    #: consequential bit in a refusal must not be set by omission. Not
    #: derived from `reason` either; see ED-026.
    remediable: bool

    #: What happened, in the caller's words. Required: a refusal that cannot
    #: say what happened is the stack trace §7.5 exists to replace. Supplied,
    #: never composed here — C20 owns founder-facing utterances.
    detail: str

    def __post_init__(self) -> None:
        if not isinstance(self.reason, RefusalReason):
            raise InvalidKernelRefusal("reason must be a RefusalReason")

        if not isinstance(self.remediable, bool):
            raise InvalidKernelRefusal(
                "remediable must be True or False; a refusal that is 'sort of' "
                "remediable is not answerable"
            )

        if not isinstance(self.detail, str) or not self.detail.strip():
            raise InvalidKernelRefusal(
                "detail must say what happened; a refusal that cannot explain "
                "itself is the stack trace the refusal contract replaces "
                "(Kernel Specification §7.5)"
            )

        self._validate_failed_check()
        self._validate_attestor()

    # ---- invariants ---------------------------------------------------

    def _validate_failed_check(self) -> None:
        check = self.failed_check
        if check is not None and not isinstance(
            check, (KernelCheck, AttestationQuestion)
        ):
            raise InvalidKernelRefusal(
                "failed_check must be a KernelCheck, an AttestationQuestion, "
                "or None"
            )

        permitted = _PERMITTED_CHECKS[self.reason]
        if check not in permitted:
            named = sorted(
                "none" if item is None else item.value for item in permitted
            )
            raise InvalidKernelRefusal(
                f"{self.reason.value!r} is refused at {' or '.join(named)}, "
                f"not at {'none' if check is None else check.value!r}"
            )

    def _validate_attestor(self) -> None:
        check = self.failed_check

        if isinstance(check, AttestationQuestion):
            expected = check.canonical_attestor
            if self.attestor != expected:
                raise InvalidKernelRefusal(
                    f"{check.value!r} is attested by {expected!r}; a refusal "
                    f"naming {self.attestor!r} attributes the failure to the "
                    "wrong component (Kernel Specification §7.3)"
                )
            return

        if self.attestor is not None:
            where = "no check" if check is None else check.value
            raise InvalidKernelRefusal(
                f"a refusal at {where} has no attestor: the three checks of "
                "§7.2 are the Kernel's own domain and no other component "
                "answers them"
            )

    # ---- reading ------------------------------------------------------

    @property
    def family(self) -> RefusalFamily:
        """Which of §11.10's three kinds of thing failed."""
        return self.reason.family

    @property
    def is_attestation_failure(self) -> bool:
        return self.family is RefusalFamily.ATTESTATION

    def as_dict(self) -> dict[str, Any]:
        """A deterministic, JSON-ready projection.

        Fixed key order, enum values as strings. `family` and
        `failed_check_kind` are derived rather than stored: a refusal is
        recorded and read back by an audit that will not have these enum
        classes, and `k2_override_state` should not have to be told apart
        from `permission` by whoever is reading in fifteen years.
        """
        check = self.failed_check
        if check is None:
            kind = None
        elif isinstance(check, KernelCheck):
            kind = "kernel_check"
        else:
            kind = "attestation"

        return {
            "reason": self.reason.value,
            "family": self.family.value,
            "failed_check": None if check is None else check.value,
            "failed_check_kind": kind,
            "attestor": self.attestor,
            "remediable": self.remediable,
            "detail": self.detail,
        }
