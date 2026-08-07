"""MB038 Step 3 — throughput on the provider profile.

The governing rule for this stage: **an unmeasured rate stays unmeasured.**
A `None` here is never a synonym for slow, fast, or a default. It means
nobody has timed this provider on this machine, and the Broker must say so
rather than derive a budget from a number it invented.
"""
from __future__ import annotations

from master_agent.ai_infrastructure.catalog import PROVIDER_CATALOG, ProviderSpec
from master_agent.ai_infrastructure.profiles import profile_for
from master_agent.broker.profiles import ProviderProfile


def spec_named(provider_id: str) -> ProviderSpec:
    return next(s for s in PROVIDER_CATALOG if s.provider_id == provider_id)


# ---- unknown stays unknown ----------------------------------------------


def test_throughput_defaults_to_unmeasured_on_both_types():
    assert ProviderSpec(
        provider_id="x",
        label="X",
        capabilities=frozenset(),
        locality="local",
        privacy="private",
        declared_quality=0.5,
        cost_per_call=0.0,
    ).prefill_tokens_per_second is None
    assert ProviderProfile(provider_id="x").decode_tokens_per_second is None
    assert ProviderProfile(provider_id="x").expected_itl_ms is None


def test_a_provider_nobody_has_timed_reports_throughput_as_unknown():
    """Only one provider in this catalogue has been measured on this
    machine. Every other one must stay honest about that."""
    for spec in PROVIDER_CATALOG:
        if spec.provider_id == "ollama.local":
            continue
        assert spec.prefill_tokens_per_second is None, spec.provider_id
        assert spec.decode_tokens_per_second is None, spec.provider_id
        assert spec.expected_itl_ms is None, spec.provider_id


def test_throughput_known_is_false_unless_both_rates_exist():
    assert ProviderProfile(provider_id="x").throughput_known is False
    assert (
        ProviderProfile(provider_id="x", prefill_tokens_per_second=20.0).throughput_known
        is False
    ), "a half-measured provider is not a measured one"
    assert (
        ProviderProfile(
            provider_id="x",
            prefill_tokens_per_second=20.0,
            decode_tokens_per_second=12.0,
        ).throughput_known
        is True
    )


def test_streaming_is_off_until_a_provider_declares_it():
    """False degrades safely to `ttft == total` with no heartbeat --
    exactly today's behaviour, now named rather than assumed."""
    assert ProviderProfile(provider_id="x").supports_streaming is False
    for spec in PROVIDER_CATALOG:
        if spec.provider_id != "ollama.local":
            assert spec.supports_streaming is False, spec.provider_id


# ---- the one measured provider ------------------------------------------


def test_the_measured_provider_carries_its_rates():
    spec = spec_named("ollama.local")

    # MB038A re-measured these in the planning regime after acceptance
    # failed. The Step 0 figures came from 24-token completions.
    assert spec.prefill_tokens_per_second == 10.0
    assert spec.decode_tokens_per_second == 4.0
    assert spec.expected_itl_ms == 200.0
    assert spec.model_load_ms == 35_000.0
    assert spec.supports_streaming is True


def test_measured_rates_are_not_optimistic():
    """A budget derived from an optimistic rate is too small, and too
    small is the failure that reports a healthy provider as broken."""
    spec = spec_named("ollama.local")

    assert spec.prefill_tokens_per_second <= 10.6, "faster than measured"
    assert spec.decode_tokens_per_second <= 4.7, "faster than measured"


def test_rates_are_never_shared_between_providers():
    """A rate is a fact about one model on one machine. Two providers
    sharing a number would mean somebody copied rather than measured."""
    measured = [
        s.prefill_tokens_per_second
        for s in PROVIDER_CATALOG
        if s.prefill_tokens_per_second is not None
    ]

    assert len(measured) == len(set(measured))


# ---- spec -> profile -----------------------------------------------------


def test_throughput_survives_the_journey_to_a_broker_profile():
    profile = profile_for(spec_named("ollama.local"))

    assert profile.prefill_tokens_per_second == 10.0
    assert profile.decode_tokens_per_second == 4.0
    assert profile.expected_itl_ms == 200.0
    assert profile.model_load_ms == 35_000.0
    assert profile.supports_streaming is True
    assert profile.throughput_known is True


def test_an_unmeasured_spec_produces_an_unmeasured_profile():
    profile = profile_for(spec_named("openai.api"))

    assert profile.throughput_known is False
    assert profile.expected_itl_ms is None


# ---- replay round-trip (MB032) ------------------------------------------


def test_throughput_round_trips_so_a_replayed_decision_sees_it():
    """MB032 stores the profiles a decision was made against and replays
    against *those*. A budget derived from a rate the replay cannot see
    would not be reproducible."""
    original = profile_for(spec_named("ollama.local"))

    restored = ProviderProfile.from_dict(original.as_dict())

    assert restored == original


def test_a_record_written_before_mb038_reads_as_unmeasured():
    """Absence in an old record is 'nobody measured', never a
    substituted number."""
    legacy = {"provider_id": "ollama.local", "quality": 0.72, "cost": 0.0}

    restored = ProviderProfile.from_dict(legacy)

    assert restored.prefill_tokens_per_second is None
    assert restored.decode_tokens_per_second is None
    assert restored.expected_itl_ms is None
    assert restored.supports_streaming is False
    assert restored.throughput_known is False
