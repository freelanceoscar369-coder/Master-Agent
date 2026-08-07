"""MB038 Step 4 — deterministic budget derivation."""
from __future__ import annotations

import pytest

from master_agent.ai_infrastructure.budgets import derive
from master_agent.ai_infrastructure.workload import (
    EMBEDDING,
    EXECUTION,
    PLANNING,
    profile_for,
)
from master_agent.broker.profiles import ProviderProfile
from master_agent.providers.budget import (
    FROM_CEILING,
    FROM_ESTIMATE,
    FROM_FLOOR,
    FROM_MISSION,
    FROM_OVERRIDE,
)

NOW = 1_000.0


def measured(**overrides) -> ProviderProfile:
    fields = {
        "provider_id": "ollama.local",
        "prefill_tokens_per_second": 20.0,
        "decode_tokens_per_second": 12.0,
        "expected_itl_ms": 90.0,
        "supports_streaming": True,
        "chars_per_token": 4.0,
    }
    fields.update(overrides)
    return ProviderProfile(**fields)


def unmeasured(**overrides) -> ProviderProfile:
    fields = {"provider_id": "openai.api", "supports_streaming": True}
    fields.update(overrides)
    return ProviderProfile(**fields)


def budget(profile=None, workload=PLANNING, prompt=2000, completion=400, **kwargs):
    return derive(
        profile=profile if profile is not None else measured(),
        workload=profile_for(workload),
        prompt_tokens=prompt,
        completion_tokens=completion,
        now=NOW,
        **kwargs,
    )


# ---- derivation from measured throughput --------------------------------


def test_ttft_is_derived_from_prompt_size_and_the_measured_prefill_rate():
    """2000 tokens at 20 tok/s = 100 s of prefill; planning's safety
    factor is 3.0, so 300 s."""
    result = budget(prompt=2000)

    assert result.ttft_ms == pytest.approx(300_000.0)
    assert result.derivation.ttft_bound_by == FROM_ESTIMATE


def test_total_covers_prefill_plus_decode():
    """300 s of TTFT plus 400 tokens at 12 tok/s (33.3 s)."""
    result = budget(prompt=2000, completion=400)

    assert result.total_ms == pytest.approx(300_000.0 + 400 / 12 * 1000)


def test_a_bigger_prompt_buys_a_bigger_prefill_window():
    """The MB036/MB037 defect, inverted: prompt size must move TTFT."""
    small = budget(prompt=200)
    large = budget(prompt=4000)

    assert large.ttft_ms > small.ttft_ms * 5


def test_prompt_size_does_not_move_the_stall_budget():
    """ITL is a property of the model and the hardware. A model that has
    begun emitting tokens emits them at its own rate regardless of how
    large the prompt was."""
    assert budget(prompt=200).itl_ms == budget(prompt=8000).itl_ms


def test_deadlines_are_absolute_instants_on_the_clock_supplied():
    result = budget(prompt=200, completion=10)

    assert result.total_deadline == pytest.approx(NOW + result.total_ms / 1000)
    assert result.ttft_deadline == pytest.approx(NOW + result.ttft_ms / 1000)


def test_the_derivation_records_the_rates_it_used():
    result = budget()

    assert result.derivation.prefill_rate == 20.0
    assert result.derivation.decode_rate == 12.0
    assert result.derivation.provider_id == "ollama.local"
    assert result.derivation.request_class == PLANNING
    assert result.derivation.prompt_tokens == 2000
    assert result.derivation.expected_output_tokens == 400


# ---- unknown throughput --------------------------------------------------


def test_unknown_throughput_falls_back_to_the_class_ceiling():
    """`None` never becomes a number. A ceiling is visibly a fallback; an
    invented rate would look derived and never be questioned."""
    planning = profile_for(PLANNING)

    result = budget(profile=unmeasured())

    assert result.ttft_ms == planning.ttft.ceiling_ms
    assert result.total_ms == planning.total.ceiling_ms
    assert result.derivation.ttft_bound_by == FROM_CEILING
    assert result.derivation.total_bound_by == FROM_CEILING


def test_unknown_throughput_records_zero_rates_alongside_the_ceiling_marker():
    """Zero means not measured, and the binding constraint beside it makes
    the pair unambiguous."""
    result = budget(profile=unmeasured())

    assert result.derivation.prefill_rate == 0.0
    assert result.derivation.decode_rate == 0.0
    assert result.derivation.ttft_bound_by == FROM_CEILING


def test_a_half_measured_provider_is_treated_as_unmeasured():
    result = budget(profile=unmeasured(prefill_tokens_per_second=20.0))

    assert result.derivation.total_bound_by == FROM_CEILING


def test_rates_without_a_tokenizer_cannot_derive_anything():
    """Tokens per second is meaningless without a token count. A provider
    that was timed but whose tokenizer was never characterised is exactly
    as underivable as one that was never timed."""
    timed_but_unsized = measured(chars_per_token=None)

    result = budget(profile=timed_but_unsized)

    assert timed_but_unsized.throughput_known is True
    assert timed_but_unsized.can_size_a_prompt is False
    assert result.derivation.total_bound_by == FROM_CEILING
    assert result.derivation.ttft_bound_by == FROM_CEILING


def test_prompt_size_is_ignored_when_there_is_no_rate_to_apply_it_to():
    small = budget(profile=unmeasured(), prompt=10)
    large = budget(profile=unmeasured(), prompt=100_000)

    assert small.ttft_ms == large.ttft_ms


# ---- clamping ------------------------------------------------------------


def test_a_tiny_estimate_is_lifted_to_the_class_floor():
    result = budget(workload=EXECUTION, prompt=1, completion=1)

    assert result.ttft_ms == profile_for(EXECUTION).ttft.floor_ms
    assert result.derivation.ttft_bound_by == FROM_FLOOR


def test_an_enormous_estimate_is_cut_to_the_class_ceiling():
    result = budget(workload=EXECUTION, prompt=10_000_000, completion=1)

    assert result.ttft_ms == profile_for(EXECUTION).ttft.ceiling_ms
    assert result.derivation.ttft_bound_by == FROM_CEILING


def test_the_stall_budget_is_lifted_off_the_raw_cadence_by_the_class_floor():
    """90 ms is the measured gap; the floor exists so a brief hiccup is
    not called a stall."""
    result = budget()

    assert result.itl_ms == profile_for(PLANNING).itl.floor_ms
    assert result.derivation.itl_bound_by == FROM_FLOOR


def test_an_unmeasured_cadence_uses_the_class_ceiling():
    result = budget(profile=unmeasured())

    assert result.itl_ms == profile_for(PLANNING).itl.ceiling_ms
    assert result.derivation.itl_bound_by == FROM_CEILING


# ---- streaming and single-shot ------------------------------------------


def test_a_non_streaming_provider_collapses_ttft_into_total():
    result = budget(profile=measured(supports_streaming=False))

    assert result.ttft_deadline == result.total_deadline
    assert result.enforce_itl is False


def test_a_single_shot_class_never_enforces_a_stall_budget():
    result = budget(workload=EMBEDDING, prompt=100, completion=10)

    assert result.enforce_itl is False


def test_streaming_is_supervised_only_when_both_ends_agree():
    assert budget().enforce_itl is True
    assert budget(profile=measured(supports_streaming=False)).enforce_itl is False
    assert budget(workload=EMBEDDING).enforce_itl is False


# ---- mission clamp -------------------------------------------------------


def test_the_mission_ceiling_cuts_a_budget_that_would_outlive_it():
    result = budget(mission_deadline=NOW + 30.0)

    assert result.total_deadline == NOW + 30.0
    assert result.derivation.total_bound_by == FROM_MISSION
    assert result.total_ms == pytest.approx(30_000.0)


def test_the_mission_ceiling_also_cuts_the_prefill_window():
    result = budget(mission_deadline=NOW + 30.0)

    assert result.ttft_deadline == NOW + 30.0
    assert result.derivation.ttft_bound_by == FROM_MISSION


def test_a_generous_mission_ceiling_changes_nothing():
    unclamped = budget()
    clamped = budget(mission_deadline=NOW + 100_000.0)

    assert clamped.total_ms == unclamped.total_ms
    assert clamped.derivation.total_bound_by == unclamped.derivation.total_bound_by


def test_a_mission_deadline_already_past_yields_no_remaining_time():
    """Refusing is Step 9's job; the deriver's job is to not lie about
    how much time is left."""
    result = budget(mission_deadline=NOW - 5.0)

    assert result.total_ms == 0.0
    assert result.total_remaining_ms(NOW) <= 0


# ---- override ------------------------------------------------------------


def test_an_override_replaces_the_derived_total_and_says_so():
    result = budget(override_total_ms=45_000.0)

    assert result.total_ms == pytest.approx(45_000.0)
    assert result.derivation.total_bound_by == FROM_OVERRIDE


def test_an_override_is_still_cut_by_the_mission_ceiling():
    """Level 5 proposes; level 6 disposes."""
    result = budget(override_total_ms=9_000_000.0, mission_deadline=NOW + 20.0)

    assert result.total_deadline == NOW + 20.0
    assert result.derivation.total_bound_by == FROM_MISSION


# ---- invariants ----------------------------------------------------------


def test_ttft_never_outlives_total_even_when_the_override_is_tiny():
    """Otherwise TIMED_OUT_TOTAL becomes unreachable and the three
    deadlines stop being distinguishable."""
    result = budget(override_total_ms=1_000.0)

    assert result.ttft_deadline <= result.total_deadline
    assert result.ttft_ms <= result.total_ms


@pytest.mark.parametrize("workload", [PLANNING, EXECUTION, EMBEDDING])
@pytest.mark.parametrize("prompt", [1, 500, 50_000])
def test_the_invariant_holds_across_the_whole_input_range(workload, prompt):
    result = budget(workload=workload, prompt=prompt, completion=prompt // 2)

    assert result.ttft_deadline <= result.total_deadline


# ---- determinism ---------------------------------------------------------


def test_the_same_inputs_always_produce_the_same_budget():
    """MB032's byte-identical replay depends on this."""
    first = budget()
    second = budget()

    assert first == second
    assert first.as_dict() == second.as_dict()


def test_derivation_reads_no_clock_of_its_own():
    """Two derivations at different `now` differ only by the offset --
    proof nothing inside consulted a clock."""
    early = derive(
        profile=measured(),
        workload=profile_for(PLANNING),
        prompt_tokens=1000,
        completion_tokens=100,
        now=0.0,
    )
    late = derive(
        profile=measured(),
        workload=profile_for(PLANNING),
        prompt_tokens=1000,
        completion_tokens=100,
        now=5_000.0,
    )

    assert late.total_deadline - early.total_deadline == pytest.approx(5_000.0)
    assert late.total_ms == early.total_ms
    assert late.derivation == early.derivation
