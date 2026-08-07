"""MB038 Step 2 — the CallBudget value object."""
from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from master_agent.providers.budget import (
    BINDING_CONSTRAINTS,
    FROM_CEILING,
    FROM_ESTIMATE,
    FROM_FLOOR,
    FROM_MISSION,
    FROM_OVERRIDE,
    CallBudget,
    Derivation,
)


def budget(**overrides) -> CallBudget:
    fields = {
        "total_deadline": 1000.0,
        "ttft_deadline": 600.0,
        "itl_ms": 5000.0,
        "total_ms": 300_000.0,
        "ttft_ms": 200_000.0,
    }
    fields.update(overrides)
    return CallBudget(**fields)


# ---- the deadlines are instants -----------------------------------------


def test_remaining_time_is_measured_against_an_absolute_instant():
    subject = budget()

    assert subject.total_remaining_ms(now=900.0) == 100_000.0
    assert subject.ttft_remaining_ms(now=500.0) == 100_000.0


def test_remaining_time_goes_negative_rather_than_clamping_to_zero():
    """A caller deciding whether to refuse needs to know *how far* past
    the deadline it is, not merely that it is past."""
    assert budget().total_remaining_ms(now=1100.0) == -100_000.0


@pytest.mark.parametrize(
    "now,total_gone,ttft_gone",
    [(500.0, False, False), (600.0, False, True), (1000.0, True, True)],
)
def test_expiry_is_inclusive_of_the_deadline_instant(now, total_gone, ttft_gone):
    subject = budget()

    assert subject.total_expired(now) is total_gone
    assert subject.ttft_expired(now) is ttft_gone


# ---- ITL is the one legitimately relative quantity ----------------------


def test_a_stall_is_measured_from_the_last_token_not_from_the_start():
    subject = budget(itl_ms=5000.0)

    assert subject.stalled(last_token_at=900.0, now=904.0) is False
    assert subject.stalled(last_token_at=900.0, now=906.0) is True


def test_a_non_streaming_budget_never_reports_a_stall():
    """An embedding has no tokens to pace. A heartbeat that can never be
    fed would fail every single-shot call."""
    subject = budget(enforce_itl=False, itl_ms=1.0)

    assert subject.stalled(last_token_at=0.0, now=10_000.0) is False


# ---- guards --------------------------------------------------------------


def test_a_ttft_deadline_after_the_total_deadline_is_refused():
    """It would make TIMED_OUT_TOTAL unreachable, hiding the very
    distinction the three deadlines exist to draw."""
    with pytest.raises(ValueError) as caught:
        budget(ttft_deadline=1200.0)

    assert "ttft_deadline must not exceed total_deadline" in str(caught.value)


def test_a_ttft_deadline_equal_to_the_total_deadline_is_allowed():
    """This is exactly how a non-streaming provider degrades."""
    assert budget(ttft_deadline=1000.0).ttft_deadline == 1000.0


@pytest.mark.parametrize("itl", [0.0, -1.0])
def test_a_non_positive_stall_budget_is_refused(itl):
    with pytest.raises(ValueError):
        budget(itl_ms=itl)


def test_a_budget_is_frozen_so_no_layer_can_extend_it_in_flight():
    subject = budget()

    with pytest.raises(FrozenInstanceError):
        subject.total_deadline = 99_999.0  # type: ignore[misc]


# ---- derivation ----------------------------------------------------------


def test_the_binding_constraint_vocabulary_is_closed():
    assert BINDING_CONSTRAINTS == (
        FROM_ESTIMATE,
        FROM_FLOOR,
        FROM_CEILING,
        FROM_MISSION,
        FROM_OVERRIDE,
    )


def test_a_budget_reports_itself_as_plain_json_shaped_data():
    """It travels into the execution record and must survive being read
    by a process that imports none of this."""
    subject = budget(
        derivation=Derivation(
            request_class="planning",
            prompt_tokens=2400,
            expected_output_tokens=300,
            provider_id="ollama.local",
            prefill_rate=120.0,
            decode_rate=18.0,
            ttft_bound_by=FROM_CEILING,
        )
    )

    reported = subject.as_dict()

    assert reported["total_ms"] == 300_000.0
    assert reported["ttft_ms"] == 200_000.0
    assert reported["itl_ms"] == 5000.0
    assert reported["enforce_itl"] is True
    assert reported["derivation"]["request_class"] == "planning"
    assert reported["derivation"]["prompt_tokens"] == 2400
    assert reported["derivation"]["ttft_bound_by"] == FROM_CEILING
    assert reported["derivation"]["total_bound_by"] == FROM_ESTIMATE


def test_the_derivation_defaults_to_estimate_on_every_deadline():
    derivation = Derivation()

    assert derivation.total_bound_by == FROM_ESTIMATE
    assert derivation.ttft_bound_by == FROM_ESTIMATE
    assert derivation.itl_bound_by == FROM_ESTIMATE


def test_a_budget_carries_a_derivation_even_when_nobody_supplied_one():
    """Absent evidence must be an empty record, never a missing
    attribute -- the panel and the ledger both read it unconditionally."""
    assert budget().derivation.as_dict()["request_class"] == ""


def test_mission_and_override_constraints_are_expressible():
    subject = budget(
        derivation=Derivation(total_bound_by=FROM_MISSION, itl_bound_by=FROM_FLOOR)
    )

    reported = subject.as_dict()["derivation"]
    assert reported["total_bound_by"] == FROM_MISSION
    assert reported["itl_bound_by"] == FROM_FLOOR
    assert FROM_OVERRIDE in BINDING_CONSTRAINTS
