"""What intelligence Kalpavriksha can actually reach, and how it behaved.

`catalog.py` states what a provider *claims*. This states what was
*observed* — and `broker/profiles.py` has been waiting for it since
MB032: `ProviderProfile.benchmark` is documented as "what was measured
here", `effective_quality()` already prefers it over the declared
`quality`, and `catalog.py`'s own docstring says **"No benchmark store
exists yet"** and names per-model profiles in the debt list. This is that
store. It is not a second registry, a second Broker, or a second Brain:
it holds observations and derives a snapshot, and the existing selection
machinery reads it.

## Why a percentage is never stored on its own

"MiniMax is 53%" is how a fifteen-attempt sample becomes a fact about a
model. Every rate here is stored as its parts — `attempts`, `admitted` —
and `rate` is derived, never persisted alone. `sample_strength` says out
loud how much the number is worth.

## Three things that look alike and are not

- **free status** is a commercial fact: is this zero-cost right now?
- **availability** is an operational fact: does it answer right now?
- **suitability** is a measured fact: does its output satisfy the
  contract we hold it to?

A model can be free, unavailable, and excellent, all at once. Gemini was
exactly that: `standing free quota`, `quota_exhausted`, and admitted on
the one attempt it did serve. Collapsing those three into "is it good"
is how a quota failure gets recorded as a bad model.

## Task-specific, never one score

A model that cannot hold the Planner's JSON contract may be an excellent
researcher. `suitability` is keyed by task, and there is deliberately no
overall number to rank models by.

## History is append-only

`observe()` appends. `snapshot()` derives. Nothing overwrites an earlier
observation, because the question "was this always like that, or did it
change?" cannot be answered from a mutated record.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# ---- access lanes (seed §2) -----------------------------------------
API = "api"
TRUSTED_WEB = "trusted_web"
DESKTOP_APP = "desktop_app"
PUBLIC_WEB = "public_web"
LOCAL_MODEL = "local_model"
SUBSCRIPTION = "existing_subscription_zero_incremental"

# ---- free status (a commercial fact) --------------------------------
STANDING_FREE = "standing_free"
FREE_QUOTA = "free_quota"
MONTHLY_FREE_CREDIT = "monthly_free_credit"
WEB_FREE = "web_free"
TRIAL_ONLY = "trial_only"
SUBSCRIPTION_INCLUDED = "subscription_included"
FREE_UNKNOWN = "unknown"
NOT_FREE = "not_free"

# ---- availability (an operational fact) -----------------------------
AVAILABLE = "available"
RATE_LIMITED = "rate_limited"
QUOTA_EXHAUSTED = "quota_exhausted"
LOGIN_REQUIRED = "login_required"
TRANSPORT_ERROR = "transport_error"
NOT_ELIGIBLE_ON_FREE_PLAN = "not_eligible_on_current_free_plan"
UNSCANNED = "unscanned"
AVAILABILITY_UNKNOWN = "unknown"

# ---- tasks (seed §6) -------------------------------------------------
PLANNER = "planner"
DEEP_REASONING = "deep_reasoning"
WEB_RESEARCH = "public_web_research"
SOURCE_VERIFICATION = "source_verification"
CODING = "coding"
SYNTHESIS = "document_synthesis"
COMPUTER_USE = "computer_use"
BROWSER_USE = "browser_use"
MULTIMODAL = "vision_multimodal"
FAST_TRANSFORM = "fast_low_cost_transformation"

# ---- why an attempt failed, kept apart on purpose -------------------
MODEL_FAILURE = "model_failure"
TRANSPORT_FAILURE = "transport_failure"
QUOTA_FAILURE = "quota_failure"
AUTH_FAILURE = "auth_failure"

#: A rate below this many attempts is not a rate.
_WEAK_SAMPLE = 10
_MODERATE_SAMPLE = 30


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass(frozen=True)
class Observation:
    """One real use of one intelligence, recorded when it happened.

    Written by runtime use as much as by a benchmark campaign: the stack
    is supposed to get truer every time Kalpavriksha asks anything of an
    external model, not only when someone runs a battery.
    """

    tool_id: str
    task: str
    at: str = field(default_factory=_now)
    #: Did the model's output satisfy the contract it was held to?
    #: `None` when nothing was measured (a research call with no
    #: deterministic acceptance test, say).
    accepted: bool | None = None
    #: Only meaningful for tasks with a scope contract, like the Planner.
    outside_target: bool = False
    corrected: bool = False
    latency_seconds: float | None = None
    #: `None` on success. One of the *_FAILURE constants otherwise --
    #: a 429 is not a bad model and must never be recorded as one.
    failure_class: str | None = None
    failure_detail: str = ""
    #: What the transport reported, verbatim where short.
    availability: str = AVAILABLE
    model_id: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "tool_id": self.tool_id, "task": self.task, "at": self.at,
            "accepted": self.accepted, "outside_target": self.outside_target,
            "corrected": self.corrected, "latency_seconds": self.latency_seconds,
            "failure_class": self.failure_class,
            "failure_detail": self.failure_detail,
            "availability": self.availability, "model_id": self.model_id,
        }

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> Observation:
        return cls(
            tool_id=str(row.get("tool_id") or ""),
            task=str(row.get("task") or ""),
            at=str(row.get("at") or _now()),
            accepted=row.get("accepted"),
            outside_target=bool(row.get("outside_target", False)),
            corrected=bool(row.get("corrected", False)),
            latency_seconds=row.get("latency_seconds"),
            failure_class=row.get("failure_class"),
            failure_detail=str(row.get("failure_detail") or ""),
            availability=str(row.get("availability") or AVAILABILITY_UNKNOWN),
            model_id=str(row.get("model_id") or ""),
        )


@dataclass
class Suitability:
    """How one intelligence performed at ONE task.

    Every field here is a count. The rate is a method, so a percentage
    cannot be stored, copied or quoted without the denominator that makes
    it meaningful.
    """

    task: str
    attempts: int = 0
    accepted: int = 0
    first_pass: int = 0
    correction_rescued: int = 0
    outside_target_admitted: int = 0
    #: Attempts that never reached the model. Excluded from `attempts`,
    #: because a browser that would not open is not a plan the model got
    #: wrong.
    transport_lost: int = 0
    latencies: list[float] = field(default_factory=list)
    failure_distribution: dict[str, int] = field(default_factory=dict)
    benchmark_date: str = ""

    @property
    def rate(self) -> float | None:
        """`None` rather than 0.0 when nothing has been measured: "no
        evidence" and "measured, and it fails" are different claims."""
        if not self.attempts:
            return None
        return self.accepted / self.attempts

    @property
    def sample_strength(self) -> str:
        if self.attempts < _WEAK_SAMPLE:
            return "very small sample"
        if self.attempts < _MODERATE_SAMPLE:
            return "small sample"
        return "moderate sample"

    @property
    def median_latency_seconds(self) -> float | None:
        if not self.latencies:
            return None
        ordered = sorted(self.latencies)
        return ordered[len(ordered) // 2]

    def stated(self) -> str:
        """The rate as it must always be quoted -- with its denominator.

        The seed asks for `8/15 = 53%, low-confidence sample`, never a
        bare `53%`.
        """
        if self.rate is None:
            return "not measured"
        return "%d/%d = %.0f%%, %s" % (
            self.accepted, self.attempts, self.rate * 100, self.sample_strength)

    def as_dict(self) -> dict[str, Any]:
        return {
            "task": self.task, "attempts": self.attempts,
            "accepted": self.accepted, "admission_rate": self.rate,
            "stated": self.stated(), "sample_strength": self.sample_strength,
            "first_pass": self.first_pass,
            "correction_rescued": self.correction_rescued,
            "outside_target_admitted": self.outside_target_admitted,
            "transport_lost": self.transport_lost,
            "median_latency_seconds": self.median_latency_seconds,
            # The samples themselves, not only the derived median: a
            # median that cannot be recomputed after a restart is a
            # number nothing can check, and the next observation would
            # have nothing to fold into.
            "latencies": list(self.latencies),
            "failure_distribution": dict(self.failure_distribution),
            "benchmark_date": self.benchmark_date,
        }


@dataclass
class Intelligence:
    """One reachable intelligence: a model on a lane, with its terms."""

    tool_id: str
    provider_id: str
    model_id: str = ""
    model_family: str = ""
    access_lane: str = API
    endpoint_or_surface: str = ""

    free_status: str = FREE_UNKNOWN
    free_limit: str = ""
    quota_remaining_observed: str = ""
    quota_reset_observed: str = ""

    auth_state: str = ""
    availability: str = UNSCANNED
    availability_detail: str = ""

    context_window: int | None = None
    structured_output: bool | None = None
    reasoning: bool | None = None
    tool_use: bool | None = None
    web_search: bool | None = None
    computer_use: bool | None = None
    file_support: bool | None = None
    multimodal: bool | None = None

    privacy_training_note: str = ""
    source_evidence: str = ""
    verified_at: str = ""
    stale_after: str = ""
    notes: str = ""

    #: Task -> measured performance. Deliberately no overall score.
    suitability: dict[str, Suitability] = field(default_factory=dict)

    calls: int = 0
    successes: int = 0
    last_success: str = ""
    last_failure: str = ""
    last_failure_class: str = ""

    def for_task(self, task: str) -> Suitability:
        return self.suitability.setdefault(task, Suitability(task=task))

    def as_dict(self) -> dict[str, Any]:
        return {
            "tool_id": self.tool_id, "provider_id": self.provider_id,
            "model_id": self.model_id, "model_family": self.model_family,
            "access_lane": self.access_lane,
            "endpoint_or_surface": self.endpoint_or_surface,
            "free_status": self.free_status, "free_limit": self.free_limit,
            "quota_remaining_observed": self.quota_remaining_observed,
            "quota_reset_observed": self.quota_reset_observed,
            "auth_state": self.auth_state,
            "availability": self.availability,
            "availability_detail": self.availability_detail,
            "context_window": self.context_window,
            "structured_output": self.structured_output,
            "reasoning": self.reasoning, "tool_use": self.tool_use,
            "web_search": self.web_search, "computer_use": self.computer_use,
            "file_support": self.file_support, "multimodal": self.multimodal,
            "privacy_training_note": self.privacy_training_note,
            "source_evidence": self.source_evidence,
            "verified_at": self.verified_at, "stale_after": self.stale_after,
            "notes": self.notes,
            "suitability": {k: v.as_dict() for k, v in self.suitability.items()},
            "calls": self.calls, "successes": self.successes,
            "last_success": self.last_success, "last_failure": self.last_failure,
            "last_failure_class": self.last_failure_class,
        }

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> Intelligence:
        item = cls(
            tool_id=str(row.get("tool_id") or ""),
            provider_id=str(row.get("provider_id") or ""),
        )
        for key, value in row.items():
            if key == "suitability":
                for task, s in (value or {}).items():
                    item.suitability[task] = Suitability(
                        task=task,
                        attempts=int(s.get("attempts", 0)),
                        accepted=int(s.get("accepted", 0)),
                        first_pass=int(s.get("first_pass", 0)),
                        correction_rescued=int(s.get("correction_rescued", 0)),
                        outside_target_admitted=int(
                            s.get("outside_target_admitted", 0)),
                        transport_lost=int(s.get("transport_lost", 0)),
                        failure_distribution=dict(
                            s.get("failure_distribution") or {}),
                        latencies=[float(x) for x in (s.get("latencies") or [])],
                        benchmark_date=str(s.get("benchmark_date") or ""),
                    )
            elif hasattr(item, key):
                setattr(item, key, value)
        return item


class JsonFileIntelligenceStore:
    """The same shape `JsonFilePlanStore` uses: load, save, nothing else."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"resources": {}, "observations": []}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return {"resources": {}, "observations": []}

    def save(self, document: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(document, indent=2, ensure_ascii=False), encoding="utf-8")


class FreeIntelligenceStack:
    """The living view of what Kalpavriksha can reach and how it behaved.

    It decides nothing. `register()` records what a resource IS,
    `observe()` records what happened, and `snapshot()` derives the
    current picture. Selection stays with the Broker, which already
    prefers a measured `benchmark` over a declared `quality`.
    """

    def __init__(self, store: Any = None) -> None:
        self._store = store
        self._resources: dict[str, Intelligence] = {}
        self._observations: list[Observation] = []
        if store is not None:
            document = store.load()
            for row in (document.get("resources") or {}).values():
                item = Intelligence.from_dict(row)
                if item.tool_id:
                    self._resources[item.tool_id] = item
            for row in document.get("observations") or []:
                self._observations.append(Observation.from_dict(row))

    # -- what exists ---------------------------------------------------
    def register(self, resource: Intelligence) -> Intelligence:
        """Record a resource, preserving any experience already held.

        Re-registering must not erase measurements: a catalogue refresh
        answers "what is it and is it free", never "how did it do".
        """
        existing = self._resources.get(resource.tool_id)
        if existing is not None:
            resource = replace(
                resource,
                suitability=existing.suitability,
                calls=existing.calls, successes=existing.successes,
                last_success=existing.last_success,
                last_failure=existing.last_failure,
                last_failure_class=existing.last_failure_class,
            )
        self._resources[resource.tool_id] = resource
        self._flush()
        return resource

    def get(self, tool_id: str) -> Intelligence | None:
        return self._resources.get(tool_id)

    def all(self) -> tuple[Intelligence, ...]:
        return tuple(self._resources.values())

    # -- what happened -------------------------------------------------
    def observe(self, observation: Observation) -> Intelligence | None:
        """Fold one real use into the record. Append-only."""
        self._observations.append(observation)
        item = self._resources.get(observation.tool_id)
        if item is None:
            return None

        item.calls += 1
        if observation.availability and observation.availability != AVAILABLE:
            item.availability = observation.availability
            item.availability_detail = observation.failure_detail
        elif observation.failure_class is None:
            item.availability = AVAILABLE
            item.availability_detail = ""

        # A call that never reached the model says nothing about the
        # model. It is counted, and it is kept out of the rate.
        if observation.failure_class in (TRANSPORT_FAILURE, QUOTA_FAILURE,
                                         AUTH_FAILURE):
            suit = item.for_task(observation.task)
            suit.transport_lost += 1
            item.last_failure = observation.at
            item.last_failure_class = observation.failure_class
            self._flush()
            return item

        if observation.accepted is None:
            self._flush()
            return item

        suit = item.for_task(observation.task)
        suit.attempts += 1
        suit.benchmark_date = observation.at
        if observation.latency_seconds is not None:
            suit.latencies.append(float(observation.latency_seconds))
        if observation.accepted:
            suit.accepted += 1
            item.successes += 1
            item.last_success = observation.at
            if observation.corrected:
                suit.correction_rescued += 1
            else:
                suit.first_pass += 1
            if observation.outside_target:
                suit.outside_target_admitted += 1
        else:
            reason = observation.failure_detail or MODEL_FAILURE
            suit.failure_distribution[reason] = (
                suit.failure_distribution.get(reason, 0) + 1)
            item.last_failure = observation.at
            item.last_failure_class = observation.failure_class or MODEL_FAILURE
        self._flush()
        return item

    def observations(self, tool_id: str = "") -> tuple[Observation, ...]:
        if not tool_id:
            return tuple(self._observations)
        return tuple(o for o in self._observations if o.tool_id == tool_id)

    # -- the derived picture -------------------------------------------
    def benchmark_for(self, tool_id: str, task: str
                      ) -> tuple[float | None, float]:
        """What this resource measured at one task, for the Broker.

        Returns `(benchmark, confidence)` in exactly the shape
        `ProviderProfile` already declares -- it has carried
        `benchmark: float | None` and `benchmark_confidence: float` since
        MB032, `effective_quality()` already prefers the measurement over
        the declared `quality`, and `catalog.py` says in as many words
        that no store existed to fill them.

        **This module does not rank.** ADR-0018 names a ranking function
        growing outside the Broker as the failure mode that would
        invalidate the design, and an earlier draft of this file did
        exactly that -- `tests/test_broker_integration.py` caught it.
        Ordering providers is the Broker's job; supplying the evidence it
        orders them by is this one's.

        Confidence scales with the sample, so four attempts cannot
        outrank a declared value with the authority of forty. A resource
        that has ever been admitted while claiming work outside its
        target reports confidence 0: that measurement is not evidence of
        quality.
        """
        item = self._resources.get(tool_id)
        if item is None:
            return (None, 0.0)
        suit = item.suitability.get(task)
        if suit is None or suit.rate is None:
            return (None, 0.0)
        if suit.outside_target_admitted:
            return (suit.rate, 0.0)
        confidence = min(1.0, suit.attempts / _MODERATE_SAMPLE)
        return (suit.rate, round(confidence, 3))

    def snapshot(self) -> dict[str, Any]:
        by_availability: dict[str, list[str]] = {}
        for item in self._resources.values():
            by_availability.setdefault(item.availability, []).append(item.tool_id)
        return {
            "generated_at": _now(),
            "resources": len(self._resources),
            "observations": len(self._observations),
            "by_availability": by_availability,
            "by_lane": {
                lane: [i.tool_id for i in self._resources.values()
                       if i.access_lane == lane]
                for lane in {i.access_lane for i in self._resources.values()}
            },
        }

    def _flush(self) -> None:
        if self._store is None:
            return
        self._store.save({
            "resources": {k: v.as_dict() for k, v in self._resources.items()},
            "observations": [o.as_dict() for o in self._observations],
        })
