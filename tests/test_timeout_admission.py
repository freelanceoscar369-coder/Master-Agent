"""MB038 Steps 9 and 10 — admission control, occupancy, and evidence."""
from __future__ import annotations

import json

import pytest

from master_agent.ai_infrastructure.admission import (
    ADMITTED,
    DECISIONS,
    OCCUPIED,
    STARVED,
    Admission,
    admit,
)
from master_agent.ai_infrastructure.execution import NOT_ADMITTED, PromptExecutor
from master_agent.ai_infrastructure.ledger import ExecutionRecord
from master_agent.ai_infrastructure.occupancy import ProviderOccupancy
from master_agent.ai_infrastructure.workload import EXECUTION, PLANNING, profile_for
from master_agent.plugins.registry import PluginRegistry
from master_agent.providers.budget import CallBudget
from master_agent.providers.transport import HttpResponse
from tests.broker_test_support import Harness, ollama, ollama_body
from tests.test_timeout_selection import TIMED_LOCAL, budgeted

NOW = 2_000.0


class FakeClock:
    def __init__(self, start: float = NOW) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now


def budget(total_s: float = 300.0) -> CallBudget:
    return CallBudget(
        total_deadline=NOW + total_s,
        ttft_deadline=NOW + min(60.0, total_s),
        itl_ms=5_000.0,
        total_ms=total_s * 1000,
        ttft_ms=min(60.0, total_s) * 1000,
    )


# ---- occupancy -----------------------------------------------------------


def test_a_provider_with_nothing_running_is_not_busy():
    occupancy = ProviderOccupancy(clock=FakeClock())

    assert occupancy.busy("p") is False
    assert occupancy.in_flight("p") == 0
    assert occupancy.as_dict() == {}


def test_a_call_in_flight_makes_a_provider_busy():
    occupancy = ProviderOccupancy(clock=FakeClock())
    occupancy.begin("p")

    assert occupancy.busy("p") is True
    assert occupancy.in_flight("p") == 1


def test_finishing_a_call_frees_the_provider():
    occupancy = ProviderOccupancy(clock=FakeClock())
    occupant = occupancy.begin("p")

    occupancy.end(occupant)

    assert occupancy.busy("p") is False


def test_abandoning_a_call_does_not_free_the_provider():
    """The daemon keeps generating for a caller that stopped listening.
    Counting it as free is how a second orphan gets created."""
    occupancy = ProviderOccupancy(clock=FakeClock())
    occupant = occupancy.begin("p")

    occupancy.abandon(occupant)

    assert occupancy.busy("p") is True
    assert occupancy.abandoned("p") == 1
    assert occupancy.as_dict()["p"] == {"in_flight": 1, "abandoned": 1}


def test_orphans_are_released_only_when_something_establishes_the_provider_is_idle():
    """Not after a guessed interval -- guessing when an orphan finished is
    exactly the invented coefficient MB038 refuses."""
    occupancy = ProviderOccupancy(clock=FakeClock())
    occupancy.abandon(occupancy.begin("p"))

    assert occupancy.release_abandoned("p") == 1
    assert occupancy.busy("p") is False


def test_releasing_orphans_leaves_live_calls_alone():
    occupancy = ProviderOccupancy(clock=FakeClock())
    occupancy.abandon(occupancy.begin("p"))
    occupancy.begin("p")

    occupancy.release_abandoned("p")

    assert occupancy.in_flight("p") == 1
    assert occupancy.abandoned("p") == 0


def test_providers_are_counted_separately():
    occupancy = ProviderOccupancy(clock=FakeClock())
    occupancy.begin("a")

    assert occupancy.busy("a") is True
    assert occupancy.busy("b") is False


def test_ending_a_call_that_was_never_begun_is_harmless():
    from master_agent.ai_infrastructure.occupancy import Occupant

    occupancy = ProviderOccupancy(clock=FakeClock())
    occupancy.end(Occupant(provider_id="p", started_at=0.0))

    assert occupancy.in_flight("p") == 0


def test_abandoning_an_unknown_occupant_returns_it_unchanged():
    from master_agent.ai_infrastructure.occupancy import Occupant

    occupancy = ProviderOccupancy(clock=FakeClock())
    stray = Occupant(provider_id="p", started_at=0.0)

    assert occupancy.abandon(stray) is stray


# ---- admission -----------------------------------------------------------


def test_the_decision_vocabulary_is_closed():
    assert DECISIONS == (ADMITTED, STARVED, OCCUPIED)


def test_a_healthy_budget_is_admitted():
    decision = admit(budget=budget(), request_class=PLANNING, now=NOW)

    assert decision.ok is True
    assert decision.decision == ADMITTED


def test_a_call_that_cannot_finish_is_refused_before_it_is_made():
    """Issuing it would burn the remaining budget, blame the provider for
    arithmetic, and leave an orphan behind."""
    decision = admit(budget=budget(total_s=5.0), request_class=PLANNING, now=NOW)

    assert decision.decision == STARVED
    assert decision.required == profile_for(PLANNING).total.floor_ms
    assert decision.available == pytest.approx(5_000.0)
    assert "cannot finish" in decision.reason


def test_starvation_is_measured_against_the_class_floor_not_a_constant():
    """The same 15 seconds is fine for execution and not for planning."""
    fifteen = budget(total_s=15.0)

    assert admit(budget=fifteen, request_class=EXECUTION, now=NOW).ok is True
    assert admit(budget=fifteen, request_class=PLANNING, now=NOW).decision == STARVED


def test_a_budget_already_past_its_deadline_is_starved():
    decision = admit(budget=budget(total_s=10.0), request_class=PLANNING, now=NOW + 60)

    assert decision.decision == STARVED
    assert decision.available < 0


def test_a_serialising_provider_that_is_busy_refuses_the_call():
    """The budget assumed the provider starts when asked. Behind a queue
    that assumption is false."""
    occupancy = ProviderOccupancy(clock=FakeClock())
    occupancy.begin("ollama.local")

    decision = admit(
        budget=budget(), request_class=PLANNING, now=NOW,
        occupancy=occupancy, provider_id="ollama.local", serialises=True,
    )

    assert decision.decision == OCCUPIED
    assert "one call at a time" in decision.reason


def test_an_occupied_refusal_names_an_orphan_separately():
    """A founder seeing "abandoned" knows the queue is not their doing."""
    occupancy = ProviderOccupancy(clock=FakeClock())
    occupancy.abandon(occupancy.begin("ollama.local"))

    decision = admit(
        budget=budget(), request_class=PLANNING, now=NOW,
        occupancy=occupancy, provider_id="ollama.local", serialises=True,
    )

    assert "1 of them abandoned" in decision.reason


def test_a_provider_that_does_not_serialise_is_admitted_while_busy():
    occupancy = ProviderOccupancy(clock=FakeClock())
    occupancy.begin("openai.api")

    decision = admit(
        budget=budget(), request_class=PLANNING, now=NOW,
        occupancy=occupancy, provider_id="openai.api", serialises=False,
    )

    assert decision.ok is True


def test_occupancy_is_only_consulted_when_one_was_supplied():
    decision = admit(
        budget=budget(), request_class=PLANNING, now=NOW,
        provider_id="ollama.local", serialises=True,
    )

    assert decision.ok is True


def test_an_unbudgeted_call_is_admitted():
    """The pre-MB038 path has no budget to be starved against."""
    assert admit(budget=None, request_class=PLANNING, now=NOW).ok is True


def test_occupancy_outranks_starvation_because_it_invalidates_the_budget():
    occupancy = ProviderOccupancy(clock=FakeClock())
    occupancy.begin("ollama.local")

    decision = admit(
        budget=budget(total_s=1.0), request_class=PLANNING, now=NOW,
        occupancy=occupancy, provider_id="ollama.local", serialises=True,
    )

    assert decision.decision == OCCUPIED


def test_the_same_inputs_always_produce_the_same_decision():
    """An admission refusal is recorded as evidence; it must mean the same
    thing when it is read back."""
    args = {"budget": budget(total_s=5.0), "request_class": PLANNING, "now": NOW}

    assert admit(**args) == admit(**args)


def test_an_admission_serialises_as_plain_data():
    reported = Admission(
        decision=STARVED, reason="too late", required=60.0, available=5.0
    ).as_dict()

    assert json.dumps(reported)
    assert reported["decision"] == STARVED


# ---- evidence ------------------------------------------------------------


def wired(**harness_kwargs):
    harness = Harness("alpha_runtime", specs=(TIMED_LOCAL,), **harness_kwargs)
    harness.service._monotonic = lambda: NOW
    registry = PluginRegistry()
    registry.register(
        ollama(
            HttpResponse(200, ollama_body(text="ok")),
            provider_id="alpha-local",
            stream=[json.dumps({"response": "ok", "done": True, "eval_count": 2})],
        )
    )
    occupancy = ProviderOccupancy(clock=FakeClock())
    executor = PromptExecutor(
        service=harness.service,
        providers=registry,
        ledger=harness.ledger,
        occupancy=occupancy,
        monotonic=lambda: NOW,
    )
    return harness, executor, occupancy


def test_a_successful_budgeted_call_records_its_budget_and_what_happened():
    harness, executor, _occupancy = wired()

    outcome = executor.run("q", budgeted(prompt="x" * 400))

    record = harness.ledger.get(outcome.entry_id).execution
    assert record.budget is not None
    assert record.budget["derivation"]["request_class"] == PLANNING
    assert record.observation is not None
    assert record.observation["token_count"] == 1
    assert record.admission == ADMITTED
    assert record.timeout is None


def test_an_admission_refusal_is_recorded_as_a_call_that_did_not_happen():
    harness, executor, occupancy = wired()
    occupancy.begin("alpha-local")

    outcome = executor.run("q", budgeted(prompt="x" * 400))

    record = harness.ledger.get(outcome.entry_id).execution
    assert outcome.ok is False
    assert record.outcome == NOT_ADMITTED
    assert record.admission == OCCUPIED
    assert "one call at a time" in record.admission_reason
    assert record.budget is not None, "the budget it was refused against"


def test_an_unbudgeted_call_records_absence_rather_than_zero():
    """A pre-MB038 call had no budget and nothing timed it. That is a
    different fact from a budget of zero."""
    from master_agent.plugins.model_router import SelectionRequest

    harness, executor, _occupancy = wired()

    outcome = executor.run("q", SelectionRequest(task_id="t1"))

    record = harness.ledger.get(outcome.entry_id).execution
    assert record.budget is None
    assert record.observation is None
    assert record.admission == ADMITTED


def test_the_provider_is_released_after_the_call():
    _harness, executor, occupancy = wired()

    executor.run("q", budgeted(prompt="x" * 400))

    assert occupancy.busy("alpha-local") is False


def test_the_provider_is_released_even_when_the_call_raises():
    """A provider left permanently occupied after one bad call would
    refuse everything afterwards."""

    class Exploding:
        model = "m"

        def complete(self, *_args, **_kwargs):
            raise RuntimeError("boom")

    harness, _executor, occupancy = wired()
    executor = PromptExecutor(
        service=harness.service,
        providers=type("R", (), {"get": staticmethod(lambda _id: Exploding())})(),
        ledger=harness.ledger,
        occupancy=occupancy,
        monotonic=lambda: NOW,
    )

    with pytest.raises(RuntimeError):
        executor.run("q", budgeted(prompt="x" * 400))

    assert occupancy.busy("alpha-local") is False


# ---- the record round-trips ---------------------------------------------


def test_timeout_evidence_survives_serialisation():
    original = ExecutionRecord(
        provider_id="p",
        outcome="timed_out_ttft",
        budget={"total_ms": 1.0},
        observation={"ttft_ms": None},
        timeout={"reason": "timed_out_ttft"},
        admission=ADMITTED,
        admission_reason="",
    )

    restored = ExecutionRecord.from_dict(original.as_dict())

    assert restored == original
    assert json.dumps(original.as_dict())


def test_a_record_written_before_mb038_reads_as_absent_not_zero():
    restored = ExecutionRecord.from_dict({"provider_id": "p", "outcome": "succeeded"})

    assert restored.budget is None
    assert restored.observation is None
    assert restored.timeout is None
    assert restored.admission == ""
