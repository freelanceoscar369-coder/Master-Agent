"""Workload classes and their deadline bounds (Mission Brief 038).

A workload class answers *"what shape is this interaction?"* -- which is a
different question from `capability`, which answers *"what kind of
intelligence does it need?"*. Planning is `capability="reasoning"` **and**
`request_class="planning"`: two orthogonal facts, two fields, two
consumers. `capability` routes; `request_class` budgets.

The vocabulary is closed. Every class declares bounds for all three
deadlines as `(floor, ceiling)` pairs rather than as single values,
because a scalar at any configuration level re-creates the static timeout
one layer up -- which is the defect MB038 exists to remove.

Bounds are a *safety envelope*, not a prediction. The Broker derives a
value inside them from prompt size and provider profile
(`budgets.py`); these only stop that derivation producing something
absurd in either direction.
"""
from __future__ import annotations

from dataclasses import dataclass

#: The closed vocabulary. Adding a member is a deliberate act -- see the
#: producer test in `tests/test_timeout_workload.py`, which fails if a
#: class exists that nothing is allowed to emit.
PLANNING = "planning"
EXECUTION = "execution"
CODE_GENERATION = "code_generation"
INTERACTIVE = "interactive"
EMBEDDING = "embedding"
VERIFICATION = "verification"

REQUEST_CLASSES = (
    PLANNING,
    EXECUTION,
    CODE_GENERATION,
    INTERACTIVE,
    EMBEDDING,
    VERIFICATION,
)

#: What a caller gets when it says nothing. `execution` rather than
#: `planning`, because the cheap, tight envelope is the safe default: a
#: caller that forgets to classify gets a fast failure and notices,
#: rather than a ten-minute one and does not.
DEFAULT_CLASS = EXECUTION


@dataclass(frozen=True)
class Bounds:
    """A floor and a ceiling, in milliseconds.

    `floor` is also the **admission threshold**: a call whose remaining
    time is below the floor is refused before it is made, because a call
    that cannot finish is a guaranteed timeout and a guaranteed orphan.
    """

    floor_ms: float
    ceiling_ms: float

    def clamp(self, value: float) -> float:
        return max(self.floor_ms, min(self.ceiling_ms, value))

    def __post_init__(self) -> None:
        if self.floor_ms > self.ceiling_ms:
            raise ValueError(
                f"floor {self.floor_ms}ms exceeds ceiling {self.ceiling_ms}ms"
            )


@dataclass(frozen=True)
class ClassProfile:
    """The deadline envelope for one workload class.

    `streams` is False for single-shot work: an embedding has no tokens
    to pace, so ITL is **undefined** rather than merely different, and the
    adapter must not start a heartbeat it can never feed.
    """

    name: str
    total: Bounds
    ttft: Bounds
    itl: Bounds
    streams: bool = True
    #: Multiplier applied to the prefill estimate before clamping. Larger
    #: for classes whose prompt size varies wildly between calls.
    ttft_safety: float = 2.0
    #: MB038A. How much output a call of this class typically produces,
    #: used **only when the caller states nothing**.
    #:
    #: Acceptance found the gap this closes: with no stated output size
    #: the decode estimate was zero, `total_ms` collapsed onto `ttft_ms`,
    #: and every planning call was budgeted to think but never to write.
    #: The real call produced 911 tokens.
    #:
    #: It lives on the class rather than at the call site because output
    #: size is a property of the *kind of work* -- a plan is a plan --
    #: and putting it in the Planner would fix one caller and leave the
    #: next one with the same zero.
    typical_output_tokens: int = 0

    @property
    def enforces_itl(self) -> bool:
        return self.streams


#: **These are envelopes, not measurements.** No throughput figure from
#: any provider is baked in here, and none should be: a rate is a fact
#: about one model on one machine and belongs on that provider's profile
#: (`broker/profiles.py`), never in a table shared by every provider.
#:
#: What these bound is how far a *derived* budget may travel in either
#: direction before it stops being credible for the class. They are
#: deliberately wide, because a narrow envelope built on one laptop's
#: numbers would be the static timeout again, wearing a table.
_PROFILES: dict[str, ClassProfile] = {
    # The class the MB036/MB037 defect lives in. A planning prompt carries
    # the whole capability catalogue, so its prefill is both large and
    # highly variable -- hence the widest TTFT envelope in the table.
    PLANNING: ClassProfile(
        name=PLANNING,
        total=Bounds(60_000, 1_800_000),
        ttft=Bounds(30_000, 1_500_000),
        itl=Bounds(5_000, 60_000),
        ttft_safety=3.0,
        # Measured 2026-07-31: two real planning calls produced 834
        # and 1115 tokens for the same objective. Rounded up.
        typical_output_tokens=1_200,
    ),
    EXECUTION: ClassProfile(
        name=EXECUTION,
        total=Bounds(10_000, 300_000),
        ttft=Bounds(5_000, 120_000),
        itl=Bounds(3_000, 30_000),
        # Unmeasured -- no producer states an output size yet. A
        # conservative assumption, bounded by the class ceiling: too
        # large only wastes patience, too small calls a healthy
        # provider broken.
        typical_output_tokens=512,
    ),
    CODE_GENERATION: ClassProfile(
        name=CODE_GENERATION,
        total=Bounds(20_000, 900_000),
        ttft=Bounds(5_000, 120_000),
        itl=Bounds(3_000, 30_000),
        # Unmeasured; code is long, so assumed larger.
        typical_output_tokens=2_048,
    ),
    # A human is waiting, so a slow start is itself the failure: the value
    # of the answer decays with latency in a way it does not for planning.
    INTERACTIVE: ClassProfile(
        name=INTERACTIVE,
        total=Bounds(5_000, 120_000),
        ttft=Bounds(2_000, 30_000),
        itl=Bounds(2_000, 15_000),
        ttft_safety=1.5,
        # Unmeasured; a conversational turn is short.
        typical_output_tokens=512,
    ),
    # Single-shot. No stream, so no ITL to enforce.
    EMBEDDING: ClassProfile(
        name=EMBEDDING,
        total=Bounds(2_000, 60_000),
        ttft=Bounds(2_000, 60_000),
        itl=Bounds(2_000, 60_000),
        streams=False,
        # A vector, not a stream of tokens. One, so the figure is
        # never zero -- zero is what caused the acceptance failure.
        typical_output_tokens=1,
    ),
    VERIFICATION: ClassProfile(
        name=VERIFICATION,
        total=Bounds(10_000, 300_000),
        ttft=Bounds(5_000, 120_000),
        itl=Bounds(3_000, 30_000),
        # Unmeasured -- no producer exists (MB035's verifier is
        # deterministic and calls no model).
        typical_output_tokens=512,
    ),
}


def is_known(request_class: str) -> bool:
    return request_class in _PROFILES


def profile_for(request_class: str) -> ClassProfile:
    """The envelope for a class.

    Raises rather than falling back to a default. A silent fallback would
    give an unknown class the execution envelope and report nothing -- and
    a planning prompt budgeted as execution is exactly the production
    failure this brief exists to fix.
    """
    try:
        return _PROFILES[request_class]
    except KeyError:
        raise ValueError(
            f"unknown request class {request_class!r}; "
            f"known: {', '.join(REQUEST_CLASSES)}"
        ) from None


def all_profiles() -> tuple[ClassProfile, ...]:
    return tuple(_PROFILES[name] for name in REQUEST_CLASSES)
