"""MB038A — the three acceptance findings, as regression tests.

Each test here corresponds to something that actually failed against the
real daemon on 2026-07-31. See `docs/MISSION_BRIEF_038_ACCEPTANCE.md`.
"""
from __future__ import annotations

import pytest

from master_agent.ai_infrastructure.budgets import derive
from master_agent.ai_infrastructure.catalog import PROVIDER_CATALOG
from master_agent.ai_infrastructure.profiles import profile_for as spec_profile
from master_agent.ai_infrastructure.workload import (
    PLANNING,
    REQUEST_CLASSES,
    all_profiles,
)
from master_agent.ai_infrastructure.workload import profile_for as workload_for
from master_agent.broker.profiles import ProviderProfile

NOW = 1_000.0


def ollama_profile() -> ProviderProfile:
    spec = next(s for s in PROVIDER_CATALOG if s.provider_id == "ollama.local")
    return spec_profile(spec)


def budget(profile=None, workload=PLANNING, prompt=1095, completion=0, **kwargs):
    return derive(
        profile=profile if profile is not None else ollama_profile(),
        workload=workload_for(workload),
        prompt_tokens=prompt,
        completion_tokens=completion,
        now=NOW,
        **kwargs,
    )


# ---- Finding 1: the decode window was zero -------------------------------


def test_a_planning_call_is_budgeted_time_to_actually_write_the_plan():
    """The acceptance failure. With no stated output size the decode
    estimate was zero, `total_ms` collapsed onto `ttft_ms`, and every
    planning call was budgeted to think but never to write."""
    result = budget()

    assert result.total_ms > result.ttft_ms, "the decode window is zero again"


def test_the_decode_window_covers_a_real_plan():
    """The measured call produced 911 tokens."""
    result = budget()

    decode_window_s = (result.total_ms - result.ttft_ms) / 1000
    assert decode_window_s > 60, f"only {decode_window_s:.0f}s to generate a plan"


def test_a_caller_that_states_an_output_size_gets_that_size():
    stated = budget(completion=4000)
    default = budget()

    assert stated.total_ms > default.total_ms
    assert stated.derivation.expected_output_tokens == 4000


def test_the_effective_output_size_is_what_gets_recorded():
    """Evidence must say what was budgeted for, not what the caller
    happened to omit."""
    result = budget(completion=0)

    assert result.derivation.expected_output_tokens > 0
    assert (
        result.derivation.expected_output_tokens
        == workload_for(PLANNING).typical_output_tokens
    )


def test_the_planning_class_output_size_comes_from_measurement():
    """911 tokens observed; the stored figure must not be below it."""
    assert workload_for(PLANNING).typical_output_tokens >= 911


@pytest.mark.parametrize("name", REQUEST_CLASSES)
def test_no_class_budgets_zero_time_to_produce_output(name):
    """The zero that caused the acceptance failure must not survive
    anywhere in the table."""
    assert workload_for(name).typical_output_tokens > 0


def test_every_class_leaves_a_decode_window():
    for profile in all_profiles():
        result = budget(workload=profile.name, prompt=100)
        if profile.name == "embedding":
            continue  # single-shot: ttft and total are the same instant
        assert result.total_ms > result.ttft_ms, profile.name


# ---- Finding 2: the rates were optimistic --------------------------------


def test_the_measured_rates_match_what_the_daemon_actually_did():
    """Measured in the planning regime on 2026-07-31: 1095 prompt tokens
    and 911 output tokens through `gemma4:latest`. The Step 0 figures
    (20 / 12) came from 24-token completions and did not extrapolate."""
    profile = ollama_profile()

    assert profile.prefill_tokens_per_second <= 14.0
    assert profile.decode_tokens_per_second <= 8.0


def test_the_budget_now_covers_the_call_that_failed():
    """1095 prompt tokens, 911 output tokens, cold. The observed call took
    191.9s warm; the acceptance run never finished cold under 161.85s."""
    result = budget(prompt=1095, completion=911)

    assert result.total_ms / 1000 > 250, (
        f"budget {result.total_ms / 1000:.0f}s still under the observed cold call"
    )


# ---- Finding 3: model load was unmodelled --------------------------------


def test_getting_the_model_into_memory_is_budgeted_for():
    """Neither prefill nor decode. The cold acceptance run spent longer
    loading than the entire budget allowed."""
    profile = ollama_profile()

    assert profile.model_load_ms is not None
    assert profile.model_load_ms > 0


def test_model_load_lengthens_the_prefill_window():
    with_load = budget()
    without = budget(profile=_replace_load(ollama_profile(), None))

    assert with_load.ttft_ms > without.ttft_ms


def test_model_load_is_added_once_and_never_multiplied():
    """The safety factor covers *estimate error* in prefill. Applying it
    to a measured constant would inflate a number that is already known."""
    load_ms = 60_000.0
    with_load = budget(profile=_replace_load(ollama_profile(), load_ms))
    without = budget(profile=_replace_load(ollama_profile(), None))

    assert with_load.ttft_ms - without.ttft_ms == pytest.approx(load_ms)


def test_an_unmeasured_load_adds_nothing():
    """`None` stays `None`. It is not a synonym for fast."""
    profile = _replace_load(ollama_profile(), None)

    assert profile.model_load_ms is None
    assert budget(profile=profile).ttft_ms > 0


def test_model_load_round_trips_for_replay():
    original = ollama_profile()

    restored = ProviderProfile.from_dict(original.as_dict())

    assert restored.model_load_ms == original.model_load_ms
    assert restored == original


def _replace_load(profile: ProviderProfile, load: float | None) -> ProviderProfile:
    from dataclasses import replace

    return replace(profile, model_load_ms=load)


# ---- determinism survives the patch --------------------------------------


def test_derivation_is_still_deterministic():
    assert budget() == budget()
    assert budget().as_dict() == budget().as_dict()
