"""Override — one gesture stops the deciding, and nothing stands in its way.

VEDA 01 §10, verbatim:

> *"One gesture stops everything. All rules dormant, all autonomy
> suspended, immediately, with no confirmation dialogue and no persuasion.
> Kalpavriksha continues working and continues queueing — **it simply stops
> deciding.**"*
>
> *"The override is always visible, never buried, and never discouraged. **A
> product that makes it hard to revoke trust has revealed what it thinks
> trust is for.**"*

VEDA 04 A3 states the same requirement as an architecture invariant — *"No
confirmation, no friction, no persuasion copy… Must be reachable when the
rest of the system is degraded"* — and Kernel Specification §7.2 K2 states
what it means inside the Kernel: *"the Override's meaning **is** 'the
Kernel stops minting.' No other component can express that."*

## What this module is

The **immutable record of override state**, and nothing else. Two values:
whether autonomy is suspended, and — when it is — the reason.

`suspend()` and `resume()` return a **new** switch. They change nothing in
place, following `PrincipalRegistry` (C2) and the Reversibility Registry,
which likewise take their state at construction. Holding the current
switch, applying it at K2, and invalidating outstanding warrants under
§11.8 are all the Kernel's, and none of them is here.

## What must never appear here

Three prohibitions, each from a frozen document, each enforced by a test
rather than by review:

**No confirmation.** §11.8: *"`invalidate()` has no confirmation parameter
in its signature, matching VEDA 04's requirement that none exist."* Not a
default-true flag, not an `are_you_sure`, not a two-step. `resume()` takes
no argument at all and `suspend()` takes only its reason.

**No friction.** No delay, cooldown, grace period, expiry or retry budget.
A3's invariant is *"suspension latency measured in milliseconds, not in a
job cycle"*, and every one of those fields is a job cycle wearing a
safety-feature name.

**No persuasion.** This module composes no sentence. `reason` is supplied
by the caller and carried verbatim; nothing here argues, warns, or asks
again. C20's Voice Charter Validator owns every outbound utterance.

## Suspending is never refused

Calling `suspend()` on an already-suspended switch is allowed and returns
a switch carrying the new reason. Refusing it would be friction on the one
gesture VEDA 01 §10 says must never be discouraged — and *"a product that
makes it hard to revoke trust has revealed what it thinks trust is for."*

`resume()` on an already-running switch is likewise allowed. Neither
direction gains anything from an error, and an error is friction.

## Only deciding stops

§11.8's mechanism is precise: suspension stops **minting**. Work already
attempting runs to settlement, the Objective Engine keeps admitting,
Mission Control keeps assigning, and work queues at the Kernel boundary.

So this record carries nothing about work, queues, counts or in-flight
state. §7.5: *"Under an active Override, a thousand refusals are one state
— 'autonomy is suspended; 1,000 actions are waiting' — not a thousand
queue items."* One state is what this value is.

## Dependencies

**None.** A3 requires the Override to be reachable *"when the rest of the
system is degraded"*, and Roadmap §2 C14 puts it *"deliberately outside the
main path so it works when the rest is degraded."* This module imports
nothing from `master_agent` at all — not even the Clock. A record of when
suspension began belongs to the ledger that records it, not to the switch.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class InvalidOverride(ValueError):
    """Raised at construction for an override state that could not be read.

    At construction, never at use. K2 consults this on **every mint** and
    treats it as settled fact, so one that should not exist must not be
    constructible.
    """


@dataclass(frozen=True)
class OverrideSwitch:
    """Whether autonomy is suspended. Immutable and hashable.

    Two switches with identical fields are the same state — which is what
    lets §7.5's *"a thousand refusals are one state"* hold: the state is a
    value, not an accumulation.
    """

    #: Whether the Kernel is suspended from minting. **This is the whole
    #: of the Override's meaning** (§7.2 K2).
    suspended: bool

    #: Why, in the founder's terms, carried verbatim. Required while
    #: suspended and refused while running — a reason on a running switch
    #: would be a stale explanation for a condition that no longer holds.
    #:
    #: Supplied, never composed: this module argues with nobody.
    reason: str | None = None

    def __post_init__(self) -> None:
        # `bool` is the type, not merely the truthiness. A switch built
        # from `1` or `"yes"` would read as suspended without anyone having
        # said so.
        if not isinstance(self.suspended, bool):
            raise InvalidOverride(
                "suspended must be True or False; autonomy is either "
                "suspended or it is not"
            )

        if self.suspended:
            if not isinstance(self.reason, str) or not self.reason.strip():
                raise InvalidOverride(
                    "a suspended override requires a reason; the founder is "
                    "owed a sentence about their own machine, not a silent "
                    "stop"
                )
        elif self.reason is not None:
            raise InvalidOverride(
                "a running override carries no reason; a reason that "
                "outlives its suspension is an explanation for a condition "
                "that no longer holds"
            )

    # ---- transitions, each returning a new switch ----------------------

    def suspend(self, reason: str) -> OverrideSwitch:
        """Stop the deciding. Returns a **new** suspended switch.

        **There is no confirmation parameter, and there will never be
        one** — §11.8 and VEDA 04 A3 both forbid it.

        Calling this on an already-suspended switch is allowed and carries
        the new reason. Refusing would be friction on the one gesture
        VEDA 01 §10 says must never be discouraged.
        """
        return OverrideSwitch(suspended=True, reason=reason)

    def resume(self) -> OverrideSwitch:
        """Start deciding again. Returns a **new** running switch.

        Takes no argument. Nothing gates resumption and nothing records a
        justification for it here — the ledger records that it happened.

        Calling this on an already-running switch is allowed and returns
        the running state.
        """
        return OverrideSwitch(suspended=False)

    # ---- reading ------------------------------------------------------

    @property
    def is_suspended(self) -> bool:
        """Whether K2 must refuse every mint.

        A fact, not a decision. §7.2 K2 performs the check; this value only
        reports the state it was built with.
        """
        return self.suspended

    def as_dict(self) -> dict[str, Any]:
        """A deterministic, JSON-ready projection.

        Fixed key order. Equal switches always produce identical
        dictionaries, so a record of a suspension reads the same years
        later as it did the moment it was written.
        """
        return {
            "suspended": self.suspended,
            "reason": self.reason,
        }
