"""MB038 Step 5 — the Broker attaches a budget to its Selection."""
from __future__ import annotations

import pytest

from master_agent.ai_infrastructure.budgeted_request import (
    UNSTATED_OUTPUT_TOKENS,
    BudgetedSelectionRequest,
)
from master_agent.ai_infrastructure.budgets import size_of
from master_agent.ai_infrastructure.catalog import ProviderSpec
from master_agent.ai_infrastructure.workload import (
    DEFAULT_CLASS,
    EXECUTION,
    PLANNING,
    profile_for,
)
from master_agent.broker.profiles import ProviderProfile
from master_agent.plugins.model_router import SelectionRequest
from master_agent.providers.budget import FROM_CEILING, CallBudget
from tests.broker_test_support import Harness

NOW = 5_000.0

#: The invented estate's free local provider, given the throughput the
#: real one was measured at, so a test exercises the derivation path
#: rather than the fallback.
TIMED_LOCAL = ProviderSpec(
    provider_id="alpha-local",
    label="Alpha Local",
    capabilities=frozenset({"reasoning", "coding"}),
    locality="local",
    privacy="private",
    declared_quality=0.75,
    cost_per_call=0.0,
    latency_ms=4000.0,
    requires_network=False,
    max_context_tokens=32_768,
    inventory_key="alpha_runtime",
    prefill_tokens_per_second=20.0,
    decode_tokens_per_second=12.0,
    expected_itl_ms=90.0,
    supports_streaming=True,
    chars_per_token=4.0,
    # A local runtime holds the model for one call at a time, like the
    # real one it stands in for.
    serialises=True,
)


def harness(**kwargs) -> Harness:
    kwargs.setdefault("specs", (TIMED_LOCAL,))
    return Harness("alpha_runtime", **kwargs)


def budgeted(**kwargs) -> BudgetedSelectionRequest:
    kwargs.setdefault("task_id", "t1")
    kwargs.setdefault("request_class", PLANNING)
    return BudgetedSelectionRequest(**kwargs)


def decide(request, **kwargs):
    subject = harness(**kwargs)
    subject.service._monotonic = lambda: NOW
    return subject, subject.service.decide(request)


# ---- the request type ----------------------------------------------------


def test_a_budgeted_request_is_still_a_selection_request():
    """Every `isinstance` check in the frozen router must keep passing --
    that is what makes subclassing legal instead of editing."""
    request = budgeted()

    assert isinstance(request, SelectionRequest)
    assert request.capability == "reasoning"


def test_its_new_fields_default_to_saying_nothing():
    request = BudgetedSelectionRequest()

    assert request.request_class == DEFAULT_CLASS
    assert request.prompt == ""
    assert request.expected_output_tokens == UNSTATED_OUTPUT_TOKENS
    assert request.deadline is None


def test_a_budgeted_request_is_frozen_like_its_parent():
    from dataclasses import FrozenInstanceError

    with pytest.raises(FrozenInstanceError):
        budgeted().request_class = EXECUTION  # type: ignore[misc]


# ---- attachment ----------------------------------------------------------


def test_a_budgeted_request_comes_back_with_three_deadlines():
    _subject, outcome = decide(budgeted(prompt="x" * 8000, expected_output_tokens=400))

    budget = outcome.selection.budget
    assert isinstance(budget, CallBudget)
    assert budget.total_deadline > NOW
    assert budget.ttft_deadline > NOW
    assert budget.itl_ms > 0


def test_the_budget_is_derived_from_the_provider_that_actually_won():
    """A budget computed before the decision would describe a provider
    that might not have been chosen."""
    _subject, outcome = decide(budgeted(prompt="x" * 8000))

    assert outcome.selection.provider_id == "alpha-local"
    assert outcome.selection.budget.derivation.provider_id == "alpha-local"


def test_the_prompt_is_sized_with_the_winning_providers_tokenizer():
    """8000 characters at 4.0 chars/token = 2000 tokens."""
    _subject, outcome = decide(budgeted(prompt="x" * 8000))

    assert outcome.selection.budget.derivation.prompt_tokens == 2000


def test_a_planning_request_gets_a_far_larger_prefill_window_than_execution():
    """The MB036/MB037 defect, resolved at the point of decision."""
    _s1, planning = decide(budgeted(prompt="x" * 8000, request_class=PLANNING))
    _s2, execution = decide(budgeted(prompt="x" * 8000, request_class=EXECUTION))

    assert planning.selection.budget.ttft_ms > execution.selection.budget.ttft_ms


def test_the_stated_output_size_reaches_the_derivation():
    _subject, outcome = decide(budgeted(prompt="x" * 400, expected_output_tokens=750))

    assert outcome.selection.budget.derivation.expected_output_tokens == 750


def test_a_deadline_on_the_request_clamps_the_budget():
    _subject, outcome = decide(budgeted(prompt="x" * 8000, deadline=NOW + 25.0))

    assert outcome.selection.budget.total_deadline == NOW + 25.0


# ---- backward compatibility ---------------------------------------------


def test_a_plain_request_still_works_and_carries_no_budget():
    """Every pre-MB038 caller. Absence is safe: the adapter refuses a call
    with no budget rather than inventing a static timeout."""
    _subject, outcome = decide(SelectionRequest(task_id="t1"))

    assert outcome.selection is not None
    assert outcome.selection.budget is None


def test_a_refusal_carries_no_budget_because_nothing_will_run():
    subject = harness(scanned=False)
    subject.service._monotonic = lambda: NOW

    outcome = subject.service.decide(budgeted(prompt="x" * 400))

    assert outcome.selection is None
    assert outcome.refusal is not None


# ---- the approval path ---------------------------------------------------


def test_an_approved_paid_selection_still_carries_its_budget():
    """The gated path returns a different `Selection`; it must not drop
    the budget on the way through."""
    paid = ProviderSpec(
        provider_id="delta-cloud",
        label="Delta Cloud",
        capabilities=frozenset({"reasoning"}),
        locality="cloud",
        privacy="third_party",
        declared_quality=0.86,
        cost_per_call=0.005,
        latency_ms=1500.0,
        max_context_tokens=128_000,
        needs_credentials=True,
    )
    subject = Harness(enabled=("delta-cloud",), specs=(paid,))
    subject.service._monotonic = lambda: NOW

    first = subject.service.decide(budgeted(prompt="x" * 400))
    assert first.selection is None, "a paid provider should have been gated"
    subject.approve_everything()

    second = subject.service.decide(budgeted(prompt="x" * 400))

    assert second.selection is not None
    assert second.selection.budget is not None
    assert second.selection.budget.derivation.provider_id == "delta-cloud"


def test_an_unmeasured_paid_provider_falls_back_to_the_class_ceiling():
    """No rates were ever measured for a cloud API on this machine, and
    the budget says so rather than guessing."""
    paid = ProviderSpec(
        provider_id="delta-cloud",
        label="Delta Cloud",
        capabilities=frozenset({"reasoning"}),
        locality="cloud",
        privacy="third_party",
        declared_quality=0.86,
        cost_per_call=0.005,
        max_context_tokens=128_000,
        needs_credentials=True,
    )
    subject = Harness(enabled=("delta-cloud",), specs=(paid,))
    subject.service._monotonic = lambda: NOW
    subject.service.decide(budgeted(prompt="x" * 400))
    subject.approve_everything()

    outcome = subject.service.decide(budgeted(prompt="x" * 400))

    budget = outcome.selection.budget
    assert budget.derivation.total_bound_by == FROM_CEILING
    assert budget.total_ms == profile_for(PLANNING).total.ceiling_ms


# ---- sizing --------------------------------------------------------------


def test_a_prompt_cannot_be_sized_without_a_measured_tokenizer():
    assert size_of("hello world", ProviderProfile(provider_id="x")) is None


def test_sizing_rounds_to_at_least_one_token():
    """An empty or tiny prompt still costs a forward pass."""
    profile = ProviderProfile(provider_id="x", chars_per_token=4.0)

    assert size_of("", profile) == 1
    assert size_of("ab", profile) == 1
    assert size_of("x" * 400, profile) == 100


def test_determinism_two_identical_requests_derive_identical_budgets():
    """MB032's byte-identical replay depends on this holding through the
    Broker, not only inside `derive()`."""
    _s1, first = decide(budgeted(prompt="x" * 8000, expected_output_tokens=300))
    _s2, second = decide(budgeted(prompt="x" * 8000, expected_output_tokens=300))

    assert first.selection.budget.as_dict() == second.selection.budget.as_dict()
