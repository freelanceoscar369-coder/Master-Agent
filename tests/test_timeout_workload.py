"""MB038 Step 1 — the workload vocabulary and its deadline envelopes."""
from __future__ import annotations

import pytest

from master_agent.ai_infrastructure.workload import (
    CODE_GENERATION,
    DEFAULT_CLASS,
    EMBEDDING,
    EXECUTION,
    INTERACTIVE,
    PLANNING,
    REQUEST_CLASSES,
    VERIFICATION,
    Bounds,
    ClassProfile,
    all_profiles,
    is_known,
    profile_for,
)


def test_the_vocabulary_is_closed_and_complete():
    assert REQUEST_CLASSES == (
        PLANNING,
        EXECUTION,
        CODE_GENERATION,
        INTERACTIVE,
        EMBEDDING,
        VERIFICATION,
    )
    assert len(all_profiles()) == len(REQUEST_CLASSES)


def test_every_class_has_an_envelope_for_all_three_deadlines():
    for profile in all_profiles():
        for bounds in (profile.total, profile.ttft, profile.itl):
            assert bounds.floor_ms > 0, profile.name
            assert bounds.ceiling_ms >= bounds.floor_ms, profile.name


def test_the_default_is_the_tight_envelope_not_the_generous_one():
    """A caller that forgets to classify should get a fast failure and
    notice, rather than a ten-minute one and not."""
    assert DEFAULT_CLASS == EXECUTION
    assert (
        profile_for(DEFAULT_CLASS).ttft.ceiling_ms
        < profile_for(PLANNING).ttft.ceiling_ms
    )


def test_planning_has_the_widest_prefill_envelope():
    """The MB036/MB037 defect: a planning prompt carries the whole
    capability catalogue, so its prefill is both large and variable."""
    planning = profile_for(PLANNING)
    for other in all_profiles():
        if other.name == PLANNING:
            continue
        assert planning.ttft.ceiling_ms >= other.ttft.ceiling_ms, other.name


def test_interactive_is_the_tightest_because_a_human_is_waiting():
    interactive = profile_for(INTERACTIVE)
    assert interactive.ttft.ceiling_ms <= profile_for(EXECUTION).ttft.ceiling_ms
    assert interactive.ttft_safety < profile_for(PLANNING).ttft_safety


def test_embeddings_do_not_stream_so_itl_is_undefined_rather_than_different():
    """A single-shot call has no tokens to pace. An adapter must not start
    a heartbeat it can never feed."""
    assert profile_for(EMBEDDING).streams is False
    assert profile_for(EMBEDDING).enforces_itl is False
    for name in (PLANNING, EXECUTION, CODE_GENERATION, INTERACTIVE, VERIFICATION):
        assert profile_for(name).enforces_itl is True


def test_an_unknown_class_raises_rather_than_falling_back():
    """A silent fallback would give an unknown class the execution
    envelope -- and a planning prompt budgeted as execution is exactly the
    production failure this brief exists to fix."""
    with pytest.raises(ValueError) as caught:
        profile_for("summarisation")

    assert "summarisation" in str(caught.value)
    assert PLANNING in str(caught.value), "the error does not list what is known"


def test_is_known_answers_without_raising():
    assert is_known(PLANNING) is True
    assert is_known("nonsense") is False


# ---- bounds -------------------------------------------------------------


def test_bounds_clamp_in_both_directions():
    bounds = Bounds(100.0, 900.0)

    assert bounds.clamp(50.0) == 100.0
    assert bounds.clamp(500.0) == 500.0
    assert bounds.clamp(5000.0) == 900.0


def test_bounds_at_the_edges_are_kept_unchanged():
    bounds = Bounds(100.0, 900.0)

    assert bounds.clamp(100.0) == 100.0
    assert bounds.clamp(900.0) == 900.0


def test_an_inverted_envelope_is_refused_at_construction():
    """A floor above a ceiling is a configuration error that would
    otherwise surface as an unexplainable timeout."""
    with pytest.raises(ValueError):
        Bounds(900.0, 100.0)


def test_a_class_profile_is_frozen():
    from dataclasses import FrozenInstanceError

    profile = profile_for(EXECUTION)
    with pytest.raises(FrozenInstanceError):
        profile.ttft_safety = 99.0  # type: ignore[misc]


@pytest.mark.parametrize("name", REQUEST_CLASSES)
def test_every_class_names_itself(name):
    """`profile_for(x).name == x` -- a mismatch would make evidence
    attribute a budget to the wrong class."""
    assert profile_for(name).name == name


def test_class_profiles_can_be_constructed_for_a_future_class():
    """The envelope type is not private to the shipped table."""
    profile = ClassProfile(
        name="future",
        total=Bounds(1.0, 2.0),
        ttft=Bounds(1.0, 2.0),
        itl=Bounds(1.0, 2.0),
    )

    assert profile.enforces_itl is True
    assert profile.ttft_safety == 2.0
