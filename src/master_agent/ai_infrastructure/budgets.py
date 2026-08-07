"""Deriving a CallBudget (Mission Brief 038).

One pure function. Facts about the work and the provider go in; three
deadlines and the reasoning behind them come out.

## Deterministic by construction

Nothing here reads a clock, generates an id, or consults the machine.
`now` is passed in, every other input is a value, and the same inputs
always produce the same budget. That is what keeps MB032's
byte-identical replay guarantee true once budgets are recorded on a
decision: a replayed decision must derive the same numbers it derived the
first time, or the record stops describing what happened.

## Unknown throughput is not slow throughput

A provider nobody has timed has `None` rates, and `None` never becomes a
number here. When throughput is unknown the deriver **cannot make a
size-based estimate at all**, so it falls back to the workload class
ceiling and records `FROM_CEILING` as the binding constraint. That is
visibly a fallback. Substituting a plausible rate would produce a budget
that *looks* derived and is actually invented, which is worse than an
obvious ceiling because nobody would ever question it.

## Every deadline records what bound it

Without the binding constraint, "it timed out" does not say whether to
raise the class floor, measure the provider, or extend the mission. With
it, the answer is in the record.
"""
from __future__ import annotations

from master_agent.ai_infrastructure.workload import Bounds, ClassProfile
from master_agent.broker.profiles import ProviderProfile
from master_agent.providers.budget import (
    FROM_CEILING,
    FROM_ESTIMATE,
    FROM_FLOOR,
    FROM_MISSION,
    FROM_OVERRIDE,
    CallBudget,
    Derivation,
)

#: Milliseconds per second, named so the arithmetic below reads as
#: arithmetic rather than as a magic number.
_MS = 1000.0


def size_of(text: str, profile: ProviderProfile) -> int | None:
    """How many tokens this prompt is, for this provider's tokenizer.

    `None` when the tokenizer has not been characterised. That is not a
    detail: a rate in tokens per second is meaningless without a token
    count, so an unsized prompt is exactly as underivable as an unmeasured
    rate, and `derive()` treats it the same way.

    Characters rather than words, because a character count does not vary
    with language or with how much of the prompt is punctuation, JSON or
    code -- and a planning prompt is mostly the last two.
    """
    if profile.chars_per_token is None:
        return None
    return max(1, round(len(text) / profile.chars_per_token))


def _bounded(value: float, bounds: Bounds) -> tuple[float, str]:
    """Clamp, and say which end did it.

    `FROM_ESTIMATE` means the derived value survived untouched -- the only
    case in which the number reflects the provider rather than policy.
    """
    if value < bounds.floor_ms:
        return bounds.floor_ms, FROM_FLOOR
    if value > bounds.ceiling_ms:
        return bounds.ceiling_ms, FROM_CEILING
    return value, FROM_ESTIMATE


def derive(
    *,
    profile: ProviderProfile,
    workload: ClassProfile,
    prompt_tokens: int,
    completion_tokens: int,
    now: float,
    mission_deadline: float | None = None,
    override_total_ms: float | None = None,
) -> CallBudget:
    """The budget for one call.

    `now` is a monotonic instant supplied by the caller; the returned
    deadlines are absolute instants on that same clock.

    `mission_deadline` is the hard ceiling from above (Stage B). When
    given, no deadline may exceed it, and a deadline it shortens records
    `FROM_MISSION` -- so a timeout at a duration matching nothing in any
    config file is still explainable.

    `override_total_ms` is configuration precedence level 5. It is
    clamped by the mission ceiling like everything else: an override that
    would outlive the mission is not honoured, it is recorded as
    overridden and then cut down.
    """
    # Both halves are required. Rates without a token count cannot be
    # applied to anything, so a provider whose tokenizer is uncharacterised
    # is as underivable as one that was never timed -- and says so with the
    # same marker rather than quietly using half a derivation.
    known = profile.throughput_known and profile.can_size_a_prompt

    # MB038A. A caller that states nothing gets the class's measured
    # typical output rather than zero. Zero meant "no time to generate",
    # which is what the acceptance run failed on.
    expected_output = completion_tokens or workload.typical_output_tokens

    if known:
        # `throughput_known` guarantees both rates are non-None.
        prefill_ms = (prompt_tokens / profile.prefill_tokens_per_second) * _MS
        decode_ms = (expected_output / profile.decode_tokens_per_second) * _MS
        # MB038A. Getting the model into memory is neither prefill nor
        # decode, scales with nothing, and is added un-multiplied: the
        # safety factor exists to cover *estimate error* in prefill, and
        # applying it to a measured constant would inflate a number that
        # is already known.
        load_ms = profile.model_load_ms or 0.0
        estimate = load_ms + prefill_ms * workload.ttft_safety
        ttft_ms, ttft_bound = _bounded(estimate, workload.ttft)
        total_ms, total_bound = _bounded(estimate + decode_ms, workload.total)
    else:
        # No rate, so no estimate -- and the marker must say *fallback*,
        # not `FROM_ESTIMATE`. Routing the ceiling through `_bounded`
        # would return it unchanged and label it an estimate, which is
        # precisely the "looks derived, actually invented" failure this
        # module exists to avoid.
        ttft_ms, ttft_bound = workload.ttft.ceiling_ms, FROM_CEILING
        total_ms, total_bound = workload.total.ceiling_ms, FROM_CEILING

    if override_total_ms is not None:
        total_ms, total_bound = override_total_ms, FROM_OVERRIDE

    # ITL is the provider's own cadence when measured, and the class
    # envelope otherwise. It is deliberately not multiplied by a safety
    # factor here: the class floor already is the tolerance, and a second
    # invented coefficient on top of it would make a stall budget nobody
    # could explain.
    if profile.expected_itl_ms is not None:
        itl_ms, itl_bound = _bounded(profile.expected_itl_ms, workload.itl)
    else:
        itl_ms, itl_bound = workload.itl.ceiling_ms, FROM_CEILING

    # A stream is only supervised when both ends agree there is one. A
    # class that does not stream has no tokens to pace; a provider that
    # does not stream gives us nothing to pace them with.
    enforce_itl = workload.streams and profile.supports_streaming

    if not profile.supports_streaming:
        # Degrade exactly as the architecture specifies: with no progress
        # signal, "time to first token" and "time to the whole answer"
        # are the same instant. This is today's behaviour, now named.
        ttft_ms, ttft_bound = total_ms, total_bound

    total_deadline = now + total_ms / _MS
    ttft_deadline = now + ttft_ms / _MS

    if mission_deadline is not None:
        if mission_deadline < total_deadline:
            total_deadline, total_bound = mission_deadline, FROM_MISSION
            total_ms = max(0.0, (total_deadline - now) * _MS)
        if mission_deadline < ttft_deadline:
            ttft_deadline, ttft_bound = mission_deadline, FROM_MISSION
            ttft_ms = max(0.0, (ttft_deadline - now) * _MS)

    # The invariant `CallBudget` enforces, established here rather than
    # discovered there: a first token that may arrive after the call is
    # already over would make TIMED_OUT_TOTAL unreachable.
    if ttft_deadline > total_deadline:
        ttft_deadline, ttft_ms, ttft_bound = total_deadline, total_ms, total_bound

    return CallBudget(
        total_deadline=total_deadline,
        ttft_deadline=ttft_deadline,
        itl_ms=itl_ms,
        enforce_itl=enforce_itl,
        total_ms=total_ms,
        ttft_ms=ttft_ms,
        derivation=Derivation(
            request_class=workload.name,
            prompt_tokens=prompt_tokens,
            # The *effective* figure, so evidence says what was actually
            # budgeted for rather than what the caller happened to omit.
            expected_output_tokens=expected_output,
            provider_id=profile.provider_id,
            # Zero here means *not measured*, matching the `None` on the
            # profile. The record says `FROM_CEILING` alongside it, so the
            # two together are unambiguous.
            prefill_rate=profile.prefill_tokens_per_second or 0.0,
            decode_rate=profile.decode_tokens_per_second or 0.0,
            total_bound_by=total_bound,
            ttft_bound_by=ttft_bound,
            itl_bound_by=itl_bound,
        ),
    )
