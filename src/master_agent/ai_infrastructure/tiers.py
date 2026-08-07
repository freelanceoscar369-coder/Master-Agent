"""Cost and quality tiers — the founder-facing reading of two numbers
(Mission Brief 032 Deliverable 9).

Lives here, not in `dashboard/`, for the reason ADR-0016 gives: the
Dashboard renders what it is handed and classifies nothing. A panel that
decided for itself what counts as "expensive" would be a second opinion
about cost, in the layer least able to defend it.

**The thresholds are configuration-shaped constants, not measurements.**
They are first guesses, stated here in one place so changing them is one
edit and so a reader can see what "moderate" actually means rather than
inferring it from a coloured word.
"""
from __future__ import annotations

# ---- cost ---------------------------------------------------------------

FREE = "free"
LOW = "low"
MODERATE = "moderate"
HIGH = "high"
COST_TIERS = (FREE, LOW, MODERATE, HIGH)

#: Marginal cost of one call. Same unit as `ProviderProfile.cost`, which
#: ADR-0017 leaves to the caller to keep consistent (MB031 debt item 5).
LOW_COST_CEILING = 0.01
MODERATE_COST_CEILING = 0.10

# ---- quality ------------------------------------------------------------

BASIC = "basic"
FAIR = "fair"
GOOD = "good"
STRONG = "strong"
QUALITY_TIERS = (BASIC, FAIR, GOOD, STRONG)

FAIR_FLOOR = 0.60
GOOD_FLOOR = 0.75
STRONG_FLOOR = 0.88

# ---- where a quality number came from -----------------------------------
#
# ADR-0017 Decision 5: measured beats declared. Until a benchmark store
# exists every number is declared, and saying so is the difference between
# a reading and a claim.

MEASURED = "measured"
DECLARED = "declared"

UNKNOWN = "unknown"


def cost_tier(cost: float | None) -> str:
    """`None` is not free. A cost nobody recorded is unknown, and calling
    it free is exactly the fabrication ADR-0016 forbids."""
    if cost is None:
        return UNKNOWN
    if cost <= 0.0:
        return FREE
    if cost <= LOW_COST_CEILING:
        return LOW
    if cost <= MODERATE_COST_CEILING:
        return MODERATE
    return HIGH


def quality_tier(quality: float | None) -> str:
    if quality is None:
        return UNKNOWN
    if quality >= STRONG_FLOOR:
        return STRONG
    if quality >= GOOD_FLOOR:
        return GOOD
    if quality >= FAIR_FLOOR:
        return FAIR
    return BASIC


def quality_basis(benchmark: float | None) -> str:
    """Did this quality come from a measurement or from a claim?"""
    return MEASURED if benchmark is not None else DECLARED


def is_free(cost: float | None) -> bool:
    """A call that costs nothing extra. `None` is not free — see
    `cost_tier`."""
    return cost is not None and cost <= 0.0


def describe_cost(cost: float | None) -> str:
    """`free`, or `low (0.0050 per call)`. The tier alone hides an order of
    magnitude; the number alone means nothing to a founder reading fast."""
    tier = cost_tier(cost)
    if tier in (FREE, UNKNOWN):
        return tier
    return f"{tier} ({cost:.4f} per call)"


def describe_quality(quality: float | None, benchmark: float | None) -> str:
    """`good (0.72, declared)`. The basis is part of the reading, not a
    footnote — see the module docstring."""
    tier = quality_tier(quality)
    if tier == UNKNOWN:
        return tier
    return f"{tier} ({quality:.2f}, {quality_basis(benchmark)})"
