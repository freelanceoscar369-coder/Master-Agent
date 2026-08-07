"""C27 · The Evidence Model — every observation carries confidence,
reason, source, timestamp. Never a black box.

**Reuses C22's `Confidence` band, never redeclares it.** `OBSERVED` /
`STRONG` / `WEAK` / `UNKNOWN` mean exactly what they already mean in
`environment_intelligence.evidence` — *"the inventory says so directly"*
down to *"no evidence supports any conclusion."* `Observation` adds the
one thing C22's own `Inference` does not carry: **a moment.** C22
analyses one static `MachineInventory` snapshot as a whole; C27 observes
a live desktop repeatedly over time, and *when* a fact was true is part
of the fact — two observations with the same value at different moments
are different observations, which is the whole reason `ObservationHistory`
(`history.py`) can ask `changes_since()` a question C22 never needed to.

This is not a second `Inference` wearing a new name: it is `Confidence`'s
existing vocabulary applied to a genuinely new axis (time) that C22's own
type has no field for.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from master_agent.environment_intelligence import Confidence

__all__ = ["Confidence", "InvalidObservation", "Observation", "unknown_observation"]


class InvalidObservation(ValueError):
    """Raised at construction for an observation that could not state
    why it knows what it claims. At construction, never at read time —
    the same discipline `environment_intelligence.evidence.Inference`
    already applies."""


@dataclass(frozen=True)
class Observation:
    """One fact, as it stood at one moment, and why this layer believes
    it. Immutable — a snapshot a consumer could edit is not a snapshot,
    the same reasoning `environment_intelligence.models` already states
    for its own readings."""

    #: The observed fact. `None` whenever `confidence` is `UNKNOWN` —
    #: this layer never fills silence with a plausible default.
    value: Any

    confidence: Confidence

    #: Why, in one sentence a founder could read. Always present.
    reason: str

    #: Where this fact was read from — e.g. `"WindowManager.active()"`,
    #: `"MachineInventory.running('chrome')"`. Never a filesystem path;
    #: a pointer into the call this layer actually made, so a reader can
    #: go verify the claim against the same mechanism that produced it.
    source: str

    #: The instant this was true. Caller-supplied, never read from an
    #: ambient clock inside this layer — the same purity rule C20's
    #: Presence Layer and C22's derivations already hold to.
    timestamp: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.confidence, Confidence):
            raise InvalidObservation("confidence must be a Confidence band")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise InvalidObservation(
                "an observation must say why; a conclusion without a "
                "reason is the black box this model exists to prevent"
            )
        if not isinstance(self.source, str) or not self.source.strip():
            raise InvalidObservation(
                "an observation must name where it was read from"
            )
        if not isinstance(self.timestamp, datetime) or self.timestamp.tzinfo is None:
            raise InvalidObservation(
                "timestamp must be a timezone-aware datetime; every moment "
                "in this layer is caller-supplied and aware"
            )
        if self.confidence is Confidence.UNKNOWN and self.value is not None:
            raise InvalidObservation(
                "an UNKNOWN observation carries no value; naming one would "
                "be a guess presented as a finding"
            )

    @property
    def known(self) -> bool:
        return self.confidence is not Confidence.UNKNOWN

    def as_dict(self) -> dict[str, Any]:
        """Deterministic, JSON-ready. Fixed key order.

        `value` can be a single as_dict-capable object (a `WindowInfo`) or
        a tuple of them (`WindowObserver`'s own `windows` observation) —
        both are projected; anything else (a `str`, `bool`, `int`,
        `None`) passes through unchanged.
        """
        value = self.value
        if isinstance(value, (tuple, list)):
            value = [v.as_dict() if hasattr(v, "as_dict") else v for v in value]
        elif hasattr(value, "as_dict"):
            value = value.as_dict()
        return {
            "value": value,
            "confidence": self.confidence.value,
            "reason": self.reason,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
        }


def unknown_observation(reason: str, source: str, timestamp: datetime) -> Observation:
    """The honest answer when nothing supports a conclusion. Used
    everywhere this layer could have guessed and chose not to — the
    `environment_intelligence.unknown()` helper, with a moment attached."""
    return Observation(
        value=None, confidence=Confidence.UNKNOWN, reason=reason,
        source=source, timestamp=timestamp,
    )
