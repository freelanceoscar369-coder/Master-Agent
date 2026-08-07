"""Explainability primitives — the reason nothing here is a black box.

The C22 brief is explicit: *"Every inference carries confidence, reason,
source. No black box."*

This module is those three words as types, and every derived value in this
package is built from them. There is no path in `environment_intelligence`
that produces a conclusion without carrying the evidence for it.

## Why confidence is a band and not a number

A float would let this layer emit `0.73` for a judgement it made by
counting two facts. A number that precise, derived that loosely, is a
black box wearing a lab coat — the reader cannot tell whether it was
measured or guessed, and nothing in the machine inventory supports
measurement.

So confidence is an **ordered band**, and each band states what kind of
evidence produces it:

| Band | Means |
|---|---|
| `OBSERVED` | The inventory says so directly. No inference occurred. |
| `STRONG` | Two or more independent facts agree. |
| `WEAK` | One indirect fact. Could be coincidence. |
| `UNKNOWN` | No evidence. **The conclusion is `None`, never a guess.** |

`UNKNOWN` is the important one. VEDA 04 §5's distinction between *"I don't
know"* and *"I haven't checked"* is a data property here too: an inference
with `UNKNOWN` confidence carries a `reason` saying which of the two it
is, and `value` is `None` rather than a plausible default.

## Propagation

A conclusion is never more certain than the weakest fact it rests on.
`Confidence.weakest()` is that rule, and it is the only combination
operator this package has — there is no averaging, no boosting, and no way
for two weak facts to become a strong one by arithmetic.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class Confidence(str, Enum):
    """How much the evidence supports a conclusion. Ordered, closed."""

    #: The inventory states it. Nothing was inferred.
    OBSERVED = "observed"

    #: Two or more independent facts agree.
    STRONG = "strong"

    #: One indirect fact. Could be coincidence.
    WEAK = "weak"

    #: No evidence supports any conclusion. The value is `None`.
    UNKNOWN = "unknown"

    @property
    def rank(self) -> int:
        """Position in the ordering. Lower is more certain."""
        return _RANK[self]

    @classmethod
    def weakest(cls, *bands: Confidence) -> Confidence:
        """A conclusion is never stronger than its weakest input.

        The only combination operator in this package. There is
        deliberately no averaging and no way to promote two weak facts
        into a strong one — that arithmetic is how a guess acquires
        authority it did not earn.
        """
        if not bands:
            return cls.UNKNOWN
        return max(bands, key=lambda band: band.rank)


_RANK: dict[Confidence, int] = {
    Confidence.OBSERVED: 0,
    Confidence.STRONG: 1,
    Confidence.WEAK: 2,
    Confidence.UNKNOWN: 3,
}


class Availability(str, Enum):
    """The only vocabulary permitted for a service this layer cannot see.

    The brief fixes it exactly: *"Represent cloud AI only as available /
    unknown / unavailable."* Three values, closed, and `UNKNOWN` is not a
    failure state — it is the honest answer whenever determining the truth
    would require inspecting something this layer must not touch.
    """

    AVAILABLE = "available"
    UNKNOWN = "unknown"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class Evidence:
    """One fact, and where in the inventory it was read.

    `source` is a path into the data this layer consumed, not a filesystem
    path and not a probe. It exists so a reader can go and check the claim
    against the same inventory the derivation saw.
    """

    #: Where the fact came from, e.g. `machine_inventory.applications[git]`.
    source: str

    #: What was observed, stated as a fact rather than a judgement.
    fact: str

    def __post_init__(self) -> None:
        if not isinstance(self.source, str) or not self.source.strip():
            raise InvalidEvidence("evidence must name its source")
        if not isinstance(self.fact, str) or not self.fact.strip():
            raise InvalidEvidence("evidence must state a fact")

    def as_dict(self) -> dict[str, Any]:
        return {"source": self.source, "fact": self.fact}


class InvalidEvidence(ValueError):
    """Raised at construction for evidence that could not be checked.

    At construction, never at read time. Evidence with no source is an
    assertion, and this package exists so that no conclusion rests on one.
    """


@dataclass(frozen=True)
class Inference:
    """A conclusion, its confidence, its reason, and the facts behind it.

    Immutable. The four fields are the brief's requirement made
    structural: a caller cannot obtain the value without also receiving
    what produced it.
    """

    #: The conclusion. **`None` whenever confidence is `UNKNOWN`** — this
    #: layer does not fill silence with a plausible default.
    value: str | None

    confidence: Confidence

    #: Why, in one sentence a founder could read. Always present, and
    #: required most when the answer is `UNKNOWN`: the reason then says
    #: whether nothing was found, or whether finding out would have meant
    #: doing something forbidden.
    reason: str

    #: The facts this rests on. Empty only when confidence is `UNKNOWN`.
    evidence: tuple[Evidence, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.confidence, Confidence):
            raise InvalidEvidence("confidence must be a Confidence band")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise InvalidEvidence(
                "an inference must say why; a conclusion without a reason "
                "is the black box this package exists to prevent"
            )
        if self.confidence is Confidence.UNKNOWN and self.value is not None:
            raise InvalidEvidence(
                "an UNKNOWN inference carries no value; naming one would be "
                "a guess presented as a finding"
            )
        if self.confidence is not Confidence.UNKNOWN and not self.evidence:
            raise InvalidEvidence(
                "a conclusion above UNKNOWN must carry the evidence for it"
            )

    @property
    def known(self) -> bool:
        return self.confidence is not Confidence.UNKNOWN

    def as_dict(self) -> dict[str, Any]:
        """Deterministic, JSON-ready. Fixed key order."""
        return {
            "value": self.value,
            "confidence": self.confidence.value,
            "reason": self.reason,
            "evidence": [item.as_dict() for item in self.evidence],
        }


def unknown(reason: str) -> Inference:
    """The honest answer when nothing supports a conclusion.

    Used everywhere this layer could have guessed and chose not to. The
    reason is mandatory and is the whole value of the call.
    """
    return Inference(value=None, confidence=Confidence.UNKNOWN, reason=reason)
