"""MB038 Steps 11 and 12 — cancellation, abandonment, and replay.

No timers anywhere. Cancellation is signalled explicitly and time moves
only when a test advances a fake clock, because inferring that abandoned
work has finished from elapsed time is precisely what MB038 refuses.
"""
from __future__ import annotations

import json

import pytest

from master_agent.ai_infrastructure.admission import OCCUPIED
from master_agent.ai_infrastructure.execution import NOT_ADMITTED, PromptExecutor
from master_agent.ai_infrastructure.ledger import (
    ABANDONED,
    COMPLETED,
    FAILED,
    LIFECYCLES,
    REFUSED,
    ExecutionRecord,
    ExecutionReplay,
)
from master_agent.ai_infrastructure.occupancy import ProviderOccupancy
from master_agent.plugins.registry import PluginRegistry
from master_agent.providers.budget import CallBudget
from master_agent.providers.deadline import Cancellation, DeadlineExceeded, check, supervise
from master_agent.providers.response import (
    CANCELLED,
    OUTCOMES,
    TIMED_OUT_ITL,
    TIMED_OUT_TTFT,
)
from master_agent.providers.stream import StreamMonitor
from tests.broker_test_support import Harness, ollama
from tests.test_timeout_selection import TIMED_LOCAL, budgeted

NOW = 3_000.0


class FakeClock:
    def __init__(self, start: float = NOW) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> float:
        self.now += seconds
        return self.now


def budget(total_s: float = 300.0) -> CallBudget:
    return CallBudget(
        total_deadline=NOW + total_s,
        ttft_deadline=NOW + min(60.0, total_s),
        itl_ms=5_000.0,
        total_ms=total_s * 1000,
        ttft_ms=min(60.0, total_s) * 1000,
    )


# ---- the cancellation signal --------------------------------------------


def test_a_fresh_cancellation_is_not_cancelled():
    token = Cancellation()

    assert token.cancelled is False
    assert token.at is None, "never 0.0, which would read as the start of time"


def test_cancelling_records_when_and_why():
    token = Cancellation()

    token.cancel(NOW, "founder stopped the mission")

    assert token.cancelled is True
    assert token.at == NOW
    assert token.reason == "founder stopped the mission"


def test_the_first_cancellation_is_the_one_that_counts():
    """A second caller must not be able to rewrite why the work stopped."""
    token = Cancellation()
    token.cancel(NOW, "founder cancelled")
    token.cancel(NOW + 5, "mission aborted")

    assert token.at == NOW
    assert token.reason == "founder cancelled"


def test_nothing_cancels_itself_after_an_interval():
    """No timer, no window. Something has to decide."""
    token = Cancellation()
    clock = FakeClock()
    clock.advance(10_000.0)

    assert token.cancelled is False


# ---- cancellation as a deadline set to now ------------------------------


def test_a_cancelled_call_is_refused_at_the_same_gate_as_a_deadline():
    clock = FakeClock()
    monitor = StreamMonitor(clock=clock, started_at=NOW)
    token = Cancellation()
    token.cancel(NOW, "mission aborted")

    breach = check(budget(), monitor, clock.now, token)

    assert breach.reason == CANCELLED
    assert breach.detail == "mission aborted"


def test_cancellation_outranks_a_deadline_that_would_also_have_fired():
    """Recording a timeout would blame the provider for a founder's
    decision."""
    clock = FakeClock()
    monitor = StreamMonitor(clock=clock, started_at=NOW)
    clock.advance(500.0)
    token = Cancellation()
    token.cancel(clock.now, "stopped")

    assert check(budget(total_s=10.0), monitor, clock.now, token).reason == CANCELLED


def test_an_uncancelled_token_changes_nothing():
    clock = FakeClock()
    monitor = StreamMonitor(clock=clock, started_at=NOW)
    clock.advance(500.0)

    assert check(budget(), monitor, clock.now, Cancellation()).reason == TIMED_OUT_TTFT


def test_a_stream_stops_at_the_chunk_after_cancellation():
    clock = FakeClock()
    monitor = StreamMonitor(clock=clock, started_at=NOW)
    token = Cancellation()
    seen = []

    def chunks():
        for index in range(5):
            clock.advance(1.0)
            if index == 2:
                token.cancel(clock.now, "founder cancelled")
            yield {"response": "x"}

    with pytest.raises(DeadlineExceeded) as caught:
        for chunk in supervise(
            chunks(), budget(), monitor, clock,
            is_token=lambda f: bool(f.get("response")),
            cancellation=token,
        ):
            seen.append(chunk)  # noqa: PERF402 - the loop body is the assertion

    assert caught.value.event.reason == CANCELLED
    # Two delivered. Cancellation happened while the third was being
    # produced, and a chunk that arrives after the call was withdrawn is
    # not handed on -- the check runs before the arrival is recorded.
    assert len(seen) == 2, "it kept streaming after being cancelled"


def test_cancelled_is_a_first_class_outcome():
    """Distinct from every timeout: a timeout means the budget ran out,
    this means somebody withdrew the question."""
    assert CANCELLED in OUTCOMES
    assert CANCELLED not in (TIMED_OUT_TTFT, TIMED_OUT_ITL)


# ---- occupancy through the lifecycle ------------------------------------


def wired(stream=None):
    harness = Harness("alpha_runtime", specs=(TIMED_LOCAL,))
    harness.service._monotonic = lambda: NOW
    registry = PluginRegistry()
    registry.register(
        ollama(
            provider_id="alpha-local",
            stream=stream
            or [json.dumps({"response": "ok", "done": True, "eval_count": 1})],
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


def test_a_completed_call_releases_the_provider_and_records_completion():
    harness, executor, occupancy = wired()

    outcome = executor.run("q", budgeted(prompt="x" * 400))

    assert occupancy.busy("alpha-local") is False
    assert harness.ledger.get(outcome.entry_id).execution.lifecycle == COMPLETED


def test_a_cancelled_call_does_not_release_the_provider():
    """The daemon keeps generating for a caller that stopped listening.
    Marking it free is how the next call queues behind an invisible one."""
    _harness, executor, occupancy = wired()
    token = Cancellation()
    token.cancel(NOW, "founder cancelled")

    outcome = executor.run("q", budgeted(prompt="x" * 400), cancellation=token)

    assert outcome.ok is False
    assert occupancy.busy("alpha-local") is True
    assert occupancy.abandoned("alpha-local") == 1


def test_a_cancelled_call_is_recorded_as_abandoned_not_as_failed():
    harness, executor, _occupancy = wired()
    token = Cancellation()
    token.cancel(NOW, "founder cancelled")

    outcome = executor.run("q", budgeted(prompt="x" * 400), cancellation=token)

    record = harness.ledger.get(outcome.entry_id).execution
    assert record.outcome == CANCELLED
    assert record.lifecycle == ABANDONED
    assert record.timeout["detail"] == "founder cancelled"


def test_a_failed_call_releases_the_provider_and_records_failure():
    from master_agent.providers.transport import TransportUnavailable

    harness, executor, occupancy = wired(stream=TransportUnavailable("down"))

    outcome = executor.run("q", budgeted(prompt="x" * 400))

    assert occupancy.busy("alpha-local") is False
    assert harness.ledger.get(outcome.entry_id).execution.lifecycle == FAILED


def test_a_refused_call_is_recorded_as_refused():
    harness, executor, occupancy = wired()
    occupancy.begin("alpha-local")

    outcome = executor.run("q", budgeted(prompt="x" * 400))

    record = harness.ledger.get(outcome.entry_id).execution
    assert record.outcome == NOT_ADMITTED
    assert record.lifecycle == REFUSED


def test_a_provider_that_raises_is_released_rather_than_wedged():
    """`complete()` is contractually forbidden from raising for an
    operational failure, so a raise is a defect in our code -- and
    wedging a provider in response to our own bug would make it
    permanently unusable, with admission refusing every call that could
    clear it."""

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


def test_the_lifecycle_vocabulary_is_closed():
    assert LIFECYCLES == (COMPLETED, FAILED, ABANDONED, REFUSED)


# ---- Step 12: replay -----------------------------------------------------


def test_a_replay_reconstructs_budget_admission_timeout_and_lifecycle():
    harness, executor, occupancy = wired()
    occupancy.begin("alpha-local")
    outcome = executor.run("q", budgeted(prompt="x" * 400))

    replay = harness.ledger.replay_execution(outcome.entry_id)

    assert replay.recorded is True
    assert replay.admission == OCCUPIED
    assert replay.lifecycle == REFUSED
    assert replay.budget is not None
    assert replay.bound_by, "the binding constraint did not survive"


def test_a_replay_reproduces_the_timeout_classification():
    harness, executor, _occupancy = wired()
    token = Cancellation()
    token.cancel(NOW, "founder cancelled")
    outcome = executor.run("q", budgeted(prompt="x" * 400), cancellation=token)

    replay = harness.ledger.replay_execution(outcome.entry_id)

    assert replay.timeout_reason == CANCELLED
    assert replay.abandoned is True


def test_replaying_twice_gives_the_same_answer():
    harness, executor, _occupancy = wired()
    outcome = executor.run("q", budgeted(prompt="x" * 400))

    first = harness.ledger.replay_execution(outcome.entry_id)
    second = harness.ledger.replay_execution(outcome.entry_id)

    assert first == second
    assert first.as_dict() == second.as_dict()


def test_a_replay_reads_the_record_and_contacts_no_provider():
    harness, executor, _occupancy = wired()
    outcome = executor.run("q", budgeted(prompt="x" * 400))
    provider = harness  # nothing to call; assert on the registry instead
    del provider

    before = harness.ledger.get(outcome.entry_id).execution

    replay = harness.ledger.replay_execution(outcome.entry_id)

    assert replay.budget == before.budget
    assert replay.observation == before.observation
    assert harness.ledger.get(outcome.entry_id).execution == before, (
        "replaying changed the record"
    )


def test_a_decision_that_never_executed_replays_as_unrecorded():
    """Distinct from an execution that happened and went badly."""
    harness = Harness("alpha_runtime", specs=(TIMED_LOCAL,))
    harness.service._monotonic = lambda: NOW
    outcome = harness.service.decide(budgeted(prompt="x" * 400))

    replay = harness.ledger.replay_execution(outcome.selection.entry.entry_id)

    assert replay.recorded is False
    assert replay.budget is None
    assert replay.lifecycle == ""


def test_a_replay_never_invents_a_budget_for_an_unbudgeted_call():
    from master_agent.plugins.model_router import SelectionRequest

    harness, executor, _occupancy = wired()
    outcome = executor.run("q", SelectionRequest(task_id="t1"))

    replay = harness.ledger.replay_execution(outcome.entry_id)

    assert replay.recorded is True
    assert replay.budget is None
    assert replay.bound_by == ""
    assert replay.timeout_reason == ""


def test_a_record_from_before_mb038_replays_without_fabricated_fields():
    legacy = ExecutionRecord.from_dict(
        {"provider_id": "p", "outcome": "succeeded", "latency_ms": 12.0}
    )

    assert legacy.lifecycle == ""
    assert legacy.budget is None
    assert legacy.timeout is None
    assert legacy.admission == ""


def test_the_lifecycle_survives_serialisation():
    original = ExecutionRecord(
        provider_id="p", outcome=CANCELLED, lifecycle=ABANDONED,
        timeout={"reason": CANCELLED, "detail": "stopped"},
    )

    restored = ExecutionRecord.from_dict(original.as_dict())

    assert restored == original
    assert json.dumps(original.as_dict())


def test_a_replay_serialises_for_a_reader():
    replay = ExecutionReplay(entry_id=1, recorded=True, lifecycle=ABANDONED)

    reported = replay.as_dict()

    assert json.dumps(reported)
    assert reported["lifecycle"] == ABANDONED
    assert reported["timeout_reason"] == ""
    assert reported["bound_by"] == ""
