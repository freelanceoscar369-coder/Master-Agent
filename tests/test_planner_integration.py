"""Mission Brief 036 — the Planner on the real execution path.

`tests/test_planner.py` proves the Planner's own logic against a runner
double. This proves the port is real: the same class, driven through the
shipped `PromptExecutor`, the shipped `AiCapabilityService`, the shipped
Broker and the shipped `OllamaProvider`, with only the HTTP transport
scripted. Every claim about "it goes through the Broker" is worth exactly
as much as this file.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime

from master_agent.ai_infrastructure.execution import PromptExecutor
from master_agent.planner.plan import BROKER_REFUSED, Intent
from master_agent.planner.planner import Planner
from master_agent.plugins.registry import PluginRegistry
from master_agent.providers.transport import HttpResponse
from tests.broker_test_support import Harness, ollama, ollama_body
from tests.planner_test_support import CATALOGUE, CREATE, WRITE, plan_text, step, success

WHEN = datetime(2026, 7, 30, 13, 0, tzinfo=UTC)

PLAN = plan_text(
    step("make_folder", CREATE.name, {"path": "/tmp/demo"}),
    step(
        "write_readme",
        WRITE.name,
        {"path": "/tmp/demo/README.md", "content": "# Demo"},
        depends_on=["make_folder"],
        success_doc=success("the file is written", must_contain=["README"]),
    ),
)


def wired(reply: str = PLAN, *, installed=("alpha_runtime",), **harness_kwargs):
    harness = Harness(*installed, **harness_kwargs)
    registry = PluginRegistry()
    provider = ollama(
        HttpResponse(200, ollama_body(text=reply)),
        provider_id="alpha-local",
        model="test-model",
        # MB038: the Planner now asks for a budget, so the call streams.
        # The reply arrives as one NDJSON frame rather than one body.
        stream=[json.dumps({"response": reply, "done": True, "eval_count": 9})],
    )
    registry.register(provider)
    executor = PromptExecutor(
        service=harness.service,
        providers=registry,
        ledger=harness.ledger,
        clock=lambda: WHEN,
    )
    return harness, Planner(executor, CATALOGUE), provider


def test_an_objective_becomes_a_verified_plan_through_the_shipped_path():
    """`Intent -> Broker -> provider -> Evidence -> MissionPlan`, with
    nothing invented but the daemon at the end of the socket."""
    _harness, planner, provider = wired()

    outcome = planner.plan(Intent(goal="Set up a demo project"), task_id="task-1")

    assert outcome.planned, outcome.reason
    assert [s.step_id for s in outcome.plan.steps] == ["make_folder", "write_readme"]
    assert all(s.expected_outcome is not None for s in outcome.plan.steps)
    assert outcome.provider_id == "alpha-local"
    assert outcome.evidence.verdict.value == "matched"
    assert provider._transport.streamed, "the provider was never contacted"


def test_the_planning_call_is_a_broker_decision_on_the_ledger_like_any_other():
    """A plan costs what it costs, on the same record as everything else.
    Planning does not get a private path to a model."""
    harness, planner, _provider = wired()

    planner.plan(Intent(goal="Set up a demo project"), task_id="task-7")

    entries = harness.ledger.recent()
    assert entries, "planning left no decision record"
    latest = entries[-1]
    assert latest.provider_id == "alpha-local"
    assert latest.task_id == "task-7"


def test_the_prompt_the_provider_receives_is_the_one_the_planner_built():
    _harness, planner, provider = wired()

    planner.plan(Intent(goal="Set up a demo project"))

    _url, payload, _timeout = provider._transport.streamed[0]
    assert "Set up a demo project" in payload["prompt"]
    assert CREATE.name in payload["prompt"]


def test_a_plan_waiting_on_founder_approval_is_not_a_plan_yet():
    """A paid provider routes through MB028.1's Approval Queue. Until the
    founder answers, there is no plan -- and the Planner says so with the
    Broker's own sentence rather than planning around it."""
    harness, planner, provider = wired(installed=(), enabled=("delta-cloud",))

    outcome = planner.plan(Intent(goal="Set up a demo project"))

    assert outcome.plan is None
    assert outcome.refusal.code == BROKER_REFUSED
    assert provider._transport.streamed == [], "a provider ran before approval"
    assert harness.mission_control.approvals.open(), "nothing was put to the founder"


def test_a_provider_that_returns_prose_produces_no_plan_and_no_pretending():
    _harness, planner, _ = wired(reply="Sure, I can help you set that up!")

    outcome = planner.plan(Intent(goal="Set up a demo project"))

    assert outcome.plan is None
    assert outcome.raw == "Sure, I can help you set that up!"


def test_a_dead_daemon_is_reported_as_a_provider_failure_not_as_a_bad_plan():
    """The reason a founder reads should be the first thing that went
    wrong, not a downstream symptom of it."""
    from master_agent.providers.transport import TransportUnavailable

    harness = Harness("alpha_runtime")
    registry = PluginRegistry()
    registry.register(
        ollama(
            TransportUnavailable("connection refused"),
            provider_id="alpha-local",
            model="test-model",
        )
    )
    executor = PromptExecutor(
        service=harness.service, providers=registry, ledger=harness.ledger, clock=lambda: WHEN
    )

    outcome = Planner(executor, CATALOGUE).plan(Intent(goal="Set up a demo project"))

    assert outcome.plan is None
    assert outcome.refusal.code == "provider_failed"
    assert outcome.refusal.detail, "a failure with no explanation"
