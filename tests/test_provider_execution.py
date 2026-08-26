"""Mission Brief 033 — carrying a Broker decision out, end to end.

The Definition of Done, as a property of the running system:

```
Task -> Broker -> Ollama Provider Plugin -> Ollama -> Structured Response
                                                   -> Decision Ledger
```

with nothing choosing a provider except the Broker, nothing falling back
when one fails, and every execution — including the failures — on the
record.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from master_agent.ai_infrastructure.cache import (
    HIT,
    MISS,
    NOT_CONSULTED,
    CachedResponse,
    ExactPromptCache,
    NullPromptCache,
    cache_key,
)
from master_agent.ai_infrastructure.economy import CLOUD
from master_agent.ai_infrastructure.execution import (
    NO_PLUGIN,
    NOT_EXECUTABLE,
    PromptExecutor,
    PromptOutcome,
)
from master_agent.ai_infrastructure.ledger import CACHE_HIT
from master_agent.config import (
    BrokerConfig,
    GeminiConfig,
    MasterAgentConfig,
    OllamaConfig,
    PromptCacheConfig,
)
from master_agent.dashboard.charset import ASCII
from master_agent.dashboard.founder import as_dict as founder_as_dict
from master_agent.dashboard.founder import build_founder_view
from master_agent.dashboard.founder_panels import render_intelligence
from master_agent.dashboard.sources import DashboardSources
from master_agent.launcher.boot import build_system
from master_agent.permissions.permission_system import GrantScope
from master_agent.plugins.model_router import RoutingContext, SelectionRequest
from master_agent.plugins.registry import PluginRegistry
from master_agent.providers.ollama import OLLAMA_PROVIDER_ID
from master_agent.providers.response import MALFORMED, REJECTED, TIMED_OUT, UNAVAILABLE
from master_agent.providers.transport import (
    HttpResponse,
    TransportTimeout,
    TransportUnavailable,
)
from master_agent.runtime.config import RuntimeConfig
from tests.broker_test_support import (
    Harness,
    RecordingProvider,
    ollama,
    ollama_body,
    stated_config,
    tags_body,
)

WHEN = datetime(2026, 7, 30, 13, 0, tzinfo=UTC)
BOTH_CLOUDS = ("delta-cloud", "epsilon-cloud")


def ok(**kwargs) -> HttpResponse:
    return HttpResponse(200, ollama_body(**kwargs))


def wired(
    *responses,
    installed: tuple[str, ...] = ("alpha_runtime",),
    provider_id: str = "alpha-local",
    cache=None,
    register: bool = True,
    provider=None,
    step_seconds: float = 0.25,
    tags=None,
    **harness_kwargs,
):
    """A Harness plus a real provider, wired the way the launcher wires
    them.

    The provider is the shipped `OllamaProvider` over a scripted
    transport, registered under one of the invented estate's ids — so the
    code under test is the code that ships, and only the machine
    underneath is invented.
    """
    harness = Harness(*installed, **harness_kwargs)
    registry = PluginRegistry()
    if provider is None:
        provider = ollama(
            *responses,
            provider_id=provider_id,
            model="test-model",
            step_seconds=step_seconds,
            tags=tags,
        )
    if register:
        registry.register(provider)
    executor = PromptExecutor(
        service=harness.service,
        providers=registry,
        ledger=harness.ledger,
        cache=cache,
        clock=lambda: WHEN,
    )
    return harness, executor, provider


def request(**kwargs) -> SelectionRequest:
    kwargs.setdefault("task_id", "t1")
    return SelectionRequest(**kwargs)


# =========================================================================
# The whole path, working
# =========================================================================


def test_a_prompt_reaches_a_provider_and_comes_back_as_text():
    _harness, executor, _provider = wired(ok(text="42"))

    outcome = executor.run("what is 6 times 7", request())

    assert outcome.ok is True
    assert outcome.text == "42"


def test_the_provider_that_ran_is_the_one_the_broker_chose():
    harness, executor, _provider = wired(ok())

    outcome = executor.run("q", request())

    assert outcome.provider_id == "alpha-local"
    assert harness.ledger.get(1).provider_id == "alpha-local"


def test_the_prompt_is_what_reaches_the_daemon():
    _harness, executor, provider = wired(ok())

    executor.run("the actual question", request())

    assert provider._transport.posts[0][1]["prompt"] == "the actual question"


def test_context_is_forwarded_to_the_provider():
    _harness, executor, provider = wired(ok())

    executor.run("q", request(), context={"file": "notes.md"})

    assert "file: notes.md" in provider._transport.posts[0][1]["prompt"]


def test_the_decision_and_the_execution_are_one_ledger_entry():
    harness, executor, _provider = wired(ok())

    executor.run("q", request())

    assert len(harness.ledger) == 1
    assert harness.ledger.get(1).executed is True


def test_the_outcome_points_at_the_entry_that_records_it():
    harness, executor, _provider = wired(ok())

    outcome = executor.run("q", request())

    assert outcome.entry_id == harness.ledger.get(1).entry_id


def test_a_free_local_provider_runs_with_nobody_interrupted():
    """MB033's first token-economy criterion: local providers execute
    without cloud escalation and without an approval."""
    harness, executor, _provider = wired(ok())

    outcome = executor.run("q", request())

    assert outcome.ok is True
    assert harness.mission_control.approvals.open() == []
    assert harness.ledger.get(1).execution.locality == "local"


def test_two_prompts_are_two_decisions_and_two_executions():
    harness, executor, _provider = wired(ok())

    executor.run("q", request(task_id="a"))
    executor.run("q", request(task_id="b"))

    assert len(harness.ledger) == 2
    assert len(harness.ledger.executions()) == 2


# ---- what gets recorded (Rule 3) ----------------------------------------


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("provider_id", "alpha-local"),
        ("outcome", "succeeded"),
        ("cost", 0.0),
        ("quality_declared", 0.75),
        ("quality_basis", "declared"),
        ("locality", "local"),
        ("retries", 0),
        ("cache", MISS),
    ],
)
def test_every_execution_records_what_rule_three_asks_for(field, expected):
    harness, executor, _provider = wired(ok())

    executor.run("q", request())

    assert getattr(harness.ledger.get(1).execution, field) == expected


def test_latency_is_recorded_from_the_provider_that_measured_it():
    harness, executor, _provider = wired(ok())

    executor.run("q", request())

    assert harness.ledger.get(1).execution.latency_ms == 250.0


def test_tokens_are_recorded_when_the_daemon_reports_them():
    harness, executor, _provider = wired(ok(prompt_tokens=23, completion_tokens=2))

    executor.run("q", request())
    execution = harness.ledger.get(1).execution

    assert execution.prompt_tokens == 23
    assert execution.total_tokens == 25


def test_the_model_that_answered_is_recorded():
    harness, executor, _provider = wired(ok(model="gemma-ish:latest"))

    executor.run("q", request())

    assert harness.ledger.get(1).execution.model == "gemma-ish:latest"


def test_an_adapter_level_retry_is_no_longer_possible_so_none_is_recorded():
    """MB038 removed the adapter's retry. A refused connection is now
    reported on the first attempt, and the ledger records zero retries
    rather than a retry that did not happen.

    `retries` stays on the record: the Runtime's mechanical retry (MB024)
    is unchanged and is the only retry left in the system."""
    harness, executor, provider = wired(TransportUnavailable("refused"), ok())

    outcome = executor.run("q", request())

    assert outcome.ok is False
    assert harness.ledger.get(1).execution.retries == 0
    assert len(provider._transport.posts) == 1, "the adapter tried again"


def test_the_execution_is_stamped_with_when_it_happened():
    harness, executor, _provider = wired(ok())

    executor.run("q", request())

    assert harness.ledger.get(1).execution.executed_at == WHEN


def test_recording_an_execution_leaves_the_decision_replayable():
    harness, executor, _provider = wired(ok())

    executor.run("q", request())

    assert harness.ledger.replay_matches(1) is True


# =========================================================================
# Failures — and the fallback that never happens (Rule 5)
# =========================================================================


@pytest.mark.parametrize(
    ("script", "outcome"),
    [
        (TransportUnavailable("refused"), UNAVAILABLE),
        (TransportTimeout("slow"), TIMED_OUT),
        (HttpResponse(200, "junk"), MALFORMED),
        (HttpResponse(404, json.dumps({"error": "no model"})), REJECTED),
    ],
)
def test_a_provider_failure_is_reported_not_worked_around(script, outcome):
    harness, executor, _provider = wired(script)

    result = executor.run("q", request())

    assert result.ok is False
    assert harness.ledger.get(1).execution.outcome == outcome


def test_a_failure_never_reaches_a_second_provider():
    """MB033 Rule 5, and the reason it matters: a system that quietly
    substitutes providers cannot learn anything true about either one."""
    harness = Harness("alpha_runtime", "gamma_app")
    registry = PluginRegistry()
    chosen = ollama(TransportUnavailable("down"), provider_id="gamma-desktop")
    other = ollama(ok(text="I was not asked"), provider_id="alpha-local")
    registry.register(chosen)
    registry.register(other)
    executor = PromptExecutor(harness.service, registry, harness.ledger, clock=lambda: WHEN)

    outcome = executor.run("q", request())

    assert outcome.ok is False
    assert outcome.provider_id == "gamma-desktop"
    assert other._transport.posts == [], "a second provider was contacted"


def test_a_failed_execution_is_recorded_as_carefully_as_a_successful_one():
    """A provider's failures are the more interesting half of what a
    future benchmark needs."""
    harness, executor, _provider = wired(TransportTimeout("slow"))

    executor.run("q", request())
    execution = harness.ledger.get(1).execution

    assert execution is not None
    assert execution.error
    assert execution.quality_declared == 0.75


def test_a_failure_reason_reaches_the_caller():
    _harness, executor, _provider = wired(TransportUnavailable("refused"))

    outcome = executor.run("q", request())

    assert "refused" in outcome.reason


def test_a_rejection_carries_its_diagnosis_to_the_caller():
    _harness, executor, _provider = wired(
        HttpResponse(404, json.dumps({"error": "model not found"})),
        tags=HttpResponse(200, tags_body("something-else")),
    )

    outcome = executor.run("q", request())

    assert outcome.detail["installed"] == ["something-else"]


def test_a_broker_refusal_never_touches_a_provider():
    """Nothing is executed, because nothing was chosen."""
    harness, executor, provider = wired(ok(), installed=(), scanned=False)

    outcome = executor.run("q", request())

    assert outcome.refused is True
    assert outcome.ok is False
    assert provider._transport.posts == []
    assert harness.ledger.get(1).execution is None


def test_a_refusal_explains_itself():
    _harness, executor, _provider = wired(ok(), installed=(), scanned=False)

    outcome = executor.run("q", request())

    assert "none eligible" in outcome.reason or "quality floor" in outcome.reason


def test_a_task_waiting_on_approval_is_not_executed():
    """A paid provider reaches the founder's inbox before anything is
    spent -- MB032's gate, still holding with a real provider behind
    it."""
    harness, executor, provider = wired(
        ok(), installed=(), enabled=BOTH_CLOUDS, provider_id="delta-cloud"
    )

    outcome = executor.run("q", request())

    assert outcome.refused is True
    assert provider._transport.posts == []
    assert len(harness.mission_control.approvals.open()) == 1


def test_the_same_task_runs_once_the_founder_approves():
    harness, executor, provider = wired(
        ok(text="paid answer"), installed=(), enabled=BOTH_CLOUDS,
        provider_id="delta-cloud",
    )
    executor.run("q", request())
    harness.approve_everything()

    outcome = executor.run("q", request())

    assert outcome.ok is True
    assert outcome.text == "paid answer"
    assert len(provider._transport.posts) == 1


def test_an_expensive_provider_is_never_contacted_unless_the_broker_picks_it():
    """MB033's third token-economy criterion, asserted with the expensive
    provider *present and registered* -- so the only thing keeping it idle
    is the decision."""
    harness = Harness("alpha_runtime", enabled=BOTH_CLOUDS)
    registry = PluginRegistry()
    local = ollama(ok(text="local answer"), provider_id="alpha-local")
    expensive = ollama(ok(text="expensive answer"), provider_id="epsilon-cloud")
    registry.register(local)
    registry.register(expensive)
    executor = PromptExecutor(harness.service, registry, harness.ledger, clock=lambda: WHEN)

    outcome = executor.run("q", request())

    assert outcome.text == "local answer"
    assert expensive._transport.posts == []


# ---- the wiring gap -----------------------------------------------------


def test_a_chosen_provider_with_no_plugin_is_reported_not_replaced():
    harness, executor, _provider = wired(ok(), register=False)

    outcome = executor.run("q", request())

    assert outcome.ok is False
    assert outcome.reason == NO_PLUGIN
    assert harness.ledger.get(1).execution.outcome == UNAVAILABLE


def test_a_plugin_that_cannot_execute_is_reported_not_replaced():
    """The two `plugins/providers/` stubs are exactly this: a
    `ModelProvider` with no way to run a prompt."""
    _harness, executor, _provider = wired(
        register=True, provider=RecordingProvider("alpha-local")
    )

    outcome = executor.run("q", request())

    assert outcome.reason == NOT_EXECUTABLE


def test_a_missing_plugin_still_leaves_a_record():
    """"We could not run what was chosen" is exactly the kind of thing
    that is invisible until someone asks why nothing works."""
    harness, executor, _provider = wired(ok(), register=False)

    executor.run("q", request())

    assert harness.ledger.get(1).execution is not None
    assert harness.ledger.get(1).execution.cache == NOT_CONSULTED


def test_a_registry_that_raises_is_a_missing_plugin_not_a_crash():
    class Exploding:
        def get(self, name):
            raise RuntimeError("registry is broken")

    harness = Harness("alpha_runtime")
    executor = PromptExecutor(harness.service, Exploding(), harness.ledger, clock=lambda: WHEN)

    outcome = executor.run("q", request())

    assert outcome.ok is False
    assert outcome.reason == NO_PLUGIN


def test_a_registry_that_returns_nothing_is_a_missing_plugin():
    class Empty:
        def get(self, name):
            return None

    harness = Harness("alpha_runtime")
    executor = PromptExecutor(harness.service, Empty(), harness.ledger, clock=lambda: WHEN)

    assert executor.run("q", request()).reason == NO_PLUGIN


# =========================================================================
# The Prompt Cache, in the path
# =========================================================================


def test_the_default_cache_misses_and_the_provider_runs():
    harness, executor, provider = wired(ok())

    outcome = executor.run("q", request())

    assert outcome.cache == MISS
    assert outcome.from_cache is False
    assert len(provider._transport.posts) == 1
    assert harness.ledger.get(1).execution.cache == MISS


def test_the_default_cache_is_the_shipped_one():
    _harness, executor, _provider = wired(ok())

    assert isinstance(executor.cache, NullPromptCache)


def test_nothing_is_stored_without_a_verifier_saying_so():
    """Rule 2: the cache reuses *verified* work, and nothing verifies
    prose yet."""
    _harness, executor, _provider = wired(ok(), cache=ExactPromptCache())

    executor.run("q", request())

    assert len(executor.cache) == 0


def test_a_verified_answer_is_remembered():
    _harness, executor, _provider = wired(ok(text="checked"), cache=ExactPromptCache())

    executor.run("q", request(), verified=True)

    assert len(executor.cache) == 1


def test_a_remembered_answer_is_reused_without_contacting_the_provider():
    """MB033's first efficiency criterion: repeated identical prompts do
    not consume provider executions."""
    _harness, executor, provider = wired(
        ok(text="remembered"), cache=ExactPromptCache()
    )
    executor.run("same question", request(task_id="a"), verified=True)

    outcome = executor.run("same question", request(task_id="b"))

    assert outcome.ok is True
    assert outcome.text == "remembered"
    assert outcome.cache == HIT
    assert len(provider._transport.posts) == 1, "the provider was asked twice"


def test_a_reused_answer_is_recorded_as_reuse_not_as_an_execution():
    harness, executor, _provider = wired(ok(), cache=ExactPromptCache())
    executor.run("q", request(task_id="a"), verified=True)

    executor.run("q", request(task_id="b"))
    execution = harness.ledger.get(2).execution

    assert execution.outcome == CACHE_HIT
    assert execution.cache == HIT
    assert execution.latency_ms == 0.0


def test_a_different_prompt_is_not_a_hit():
    _harness, executor, provider = wired(ok(), cache=ExactPromptCache())
    executor.run("first question", request(task_id="a"), verified=True)

    outcome = executor.run("second question", request(task_id="b"))

    assert outcome.cache == MISS
    assert len(provider._transport.posts) == 2


def test_the_cache_can_be_skipped_for_one_call():
    _harness, executor, provider = wired(ok(), cache=ExactPromptCache())
    executor.run("q", request(task_id="a"), verified=True)

    outcome = executor.run("q", request(task_id="b"), use_cache=False)

    assert outcome.cache == NOT_CONSULTED
    assert len(provider._transport.posts) == 2


def test_a_skipped_lookup_is_recorded_as_never_looked():
    harness, executor, _provider = wired(ok(), cache=ExactPromptCache())

    executor.run("q", request(), use_cache=False)

    assert harness.ledger.get(1).execution.cache == NOT_CONSULTED


def test_an_executor_can_be_told_to_store_unverified_work():
    """Explicitly, and never by default -- which is the whole of Rule 2's
    protection."""
    harness = Harness("alpha_runtime")
    registry = PluginRegistry()
    registry.register(ollama(ok(), provider_id="alpha-local"))
    executor = PromptExecutor(
        harness.service,
        registry,
        harness.ledger,
        cache=ExactPromptCache(allow_unverified=True),
        clock=lambda: WHEN,
        store_unverified=True,
    )

    executor.run("q", request())

    assert len(executor.cache) == 1


def test_a_failed_execution_is_never_cached():
    _harness, executor, _provider = wired(
        TransportUnavailable("down"), cache=ExactPromptCache()
    )

    executor.run("q", request(), verified=True)

    assert len(executor.cache) == 0


def test_the_cache_key_covers_the_provider_and_the_model():
    """So the same prompt answered by a different model is a different
    entry, not a wrong hit."""
    _harness, executor, _provider = wired(ok(), cache=ExactPromptCache())
    executor.run("q", request(task_id="a"), verified=True)

    stored = next(iter(executor.cache._entries))

    assert stored == cache_key("reasoning", "alpha-local", "test-model", "q")


def test_a_reused_cloud_answer_is_counted_as_an_avoided_cloud_call():
    """The only honest saving in the system: an execution that happened
    once and was not repeated."""
    harness = Harness(enabled=BOTH_CLOUDS)
    cache = ExactPromptCache()
    cache.store(
        cache_key("reasoning", "delta-cloud", "test-model", "q"),
        CachedResponse(
            text="reused", provider_id="delta-cloud", model="test-model",
            cost=0.005, locality=CLOUD, verified=True,
        ),
    )
    registry = PluginRegistry()
    provider = ollama(ok(), provider_id="delta-cloud")
    registry.register(provider)
    executor = PromptExecutor(
        harness.service, registry, harness.ledger, cache=cache, clock=lambda: WHEN
    )
    harness.permissions.grant("delta-cloud", "use_paid_provider", GrantScope.ONCE)

    outcome = executor.run("q", request())

    assert outcome.cache == HIT
    assert provider._transport.posts == []
    economy = harness.service.report().economy
    assert economy.avoided_cloud_executions == 1
    assert economy.money_saved == 0.005


# ---- the outcome shape ---------------------------------------------------


def test_an_outcome_serialises_for_a_front_end():
    _harness, executor, _provider = wired(ok())

    payload = executor.run("q", request()).as_dict()

    assert payload["ok"] is True
    assert payload["provider_id"] == "alpha-local"
    assert payload["execution"]["outcome"] == "succeeded"


def test_a_refused_outcome_serialises_its_refusal():
    _harness, executor, _provider = wired(ok(), installed=(), scanned=False)

    payload = executor.run("q", request()).as_dict()

    assert payload["refused"] is True
    assert payload["refusal"]["kind"] == "no_provider"


def test_an_empty_outcome_has_no_reason_to_give():
    assert PromptOutcome().reason == ""


def test_a_successful_outcome_has_no_failure_reason():
    _harness, executor, _provider = wired(ok())

    assert executor.run("q", request()).reason == ""


def test_an_outcome_reports_the_latency_it_measured():
    _harness, executor, _provider = wired(ok())

    assert executor.run("q", request()).latency_ms == 250.0


# =========================================================================
# What the founder sees
# =========================================================================


def view_after(*responses, **kwargs):
    harness, executor, _provider = wired(*responses, **kwargs)
    executor.run("q", request())
    sources = DashboardSources(broker_provider=lambda: harness.service.report())
    return build_founder_view(sources.collect())


def test_before_anything_runs_there_is_nothing_to_show():
    """A founder page that said "Thinking with: none" before anything had
    been asked would be answering a question nobody asked."""
    harness = Harness("alpha_runtime")
    sources = DashboardSources(broker_provider=lambda: harness.service.report())

    view = build_founder_view(sources.collect())

    assert view.intelligence.thinking is None


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("provider", "alpha-local"),
        ("cost", "Free"),
        ("latency", "250 ms"),
        ("cache", "MISS"),
        ("succeeded", True),
        ("model", "test-model"),
    ],
)
def test_the_founder_sees_the_four_lines_mb033_specifies(field, expected):
    view = view_after(ok())

    assert getattr(view.intelligence.thinking, field) == expected


def test_latency_is_shown_in_seconds_once_it_is_seconds():
    """A founder waiting for a local model is counting in seconds."""
    view = view_after(ok(), step_seconds=1.7)

    assert view.intelligence.thinking.latency == "1.7 s"


def test_a_paid_execution_shows_what_it_cost():
    harness, executor, _provider = wired(
        ok(), installed=(), enabled=BOTH_CLOUDS, provider_id="delta-cloud"
    )
    executor.run("q", request())
    harness.approve_everything()
    executor.run("q", request())

    sources = DashboardSources(broker_provider=lambda: harness.service.report())
    view = build_founder_view(sources.collect())

    assert view.intelligence.thinking.cost == "0.0050"


def test_a_failed_execution_is_shown_as_failed():
    view = view_after(TransportUnavailable("refused"))

    assert view.intelligence.thinking.succeeded is False
    assert "refused" in view.intelligence.thinking.error


def test_a_cache_hit_is_shown_as_a_hit():
    harness, executor, _provider = wired(ok(), cache=ExactPromptCache())
    executor.run("q", request(task_id="a"), verified=True)
    executor.run("q", request(task_id="b"))

    sources = DashboardSources(broker_provider=lambda: harness.service.report())
    view = build_founder_view(sources.collect())

    assert view.intelligence.thinking.cache == HIT.upper()


def test_an_unmeasured_latency_or_cost_renders_rather_than_crashing():
    """Found by the linter, not by a test: the marker for "not measured"
    was used in `sources.py` without being imported, so the first
    execution with an unrecorded latency would have raised `NameError`
    while rendering the founder page. Every other execution in this suite
    happened to have both, which is exactly how a hole like this stays
    open."""
    from master_agent.ai_infrastructure.ledger import ExecutionRecord

    harness = Harness("alpha_runtime")
    harness.decide()
    harness.ledger.record_execution(
        1,
        ExecutionRecord(
            provider_id="alpha-local", outcome="succeeded", latency_ms=None, cost=None
        ),
    )
    sources = DashboardSources(broker_provider=lambda: harness.service.report())

    view = build_founder_view(sources.collect())

    assert view.intelligence.thinking.latency == "—"
    assert view.intelligence.thinking.cost == "—"


def test_the_economy_counts_reach_the_founder_view():
    view = view_after(ok())

    assert view.intelligence.economy.local_executions == 1
    assert view.intelligence.economy.cloud_executions == 0
    assert view.intelligence.economy.basis


def test_the_panel_shows_what_is_thinking():
    view = view_after(ok())
    text = "\n".join(render_intelligence(view, ASCII))

    assert "Thinking with  alpha-local" in text
    assert "Cost           Free" in text
    assert "Latency        250 ms" in text
    assert "Prompt Cache   MISS" in text


def test_the_panel_names_the_model_that_ran():
    text = "\n".join(render_intelligence(view_after(ok(model="m:tag")), ASCII))

    assert "(m:tag)" in text


def test_the_economy_totals_are_headed_so_they_do_not_read_as_one_decision():
    """Without a header these sit at the same indent as the last
    decision's fields and look like a property of it."""
    lines = render_intelligence(view_after(ok()), ASCII)
    header = lines.index("  TOKEN ECONOMY")

    assert lines[header + 1].strip().startswith("Ran locally")


def test_the_panel_shows_the_economy_once_something_has_run():
    text = "\n".join(render_intelligence(view_after(ok()), ASCII))

    assert "Ran locally    1" in text
    assert "Cache          0 hit / 1 miss" in text
    assert "Avoided        0 cloud call(s)" in text


def test_the_panel_says_why_the_savings_are_zero():
    """A row of zeroes with no reason is indistinguishable from a broken
    counter."""
    # Normalised, because the panel wraps the basis across lines and the
    # phrase under test straddles a break.
    text = " ".join(" ".join(render_intelligence(view_after(ok()), ASCII)).split())

    assert "only an answer verified against an expected outcome" in text


def test_the_panel_shows_nothing_economic_before_anything_runs():
    harness = Harness("alpha_runtime")
    sources = DashboardSources(broker_provider=lambda: harness.service.report())
    view = build_founder_view(sources.collect())

    text = "\n".join(render_intelligence(view, ASCII))

    assert "Ran locally" not in text
    assert "Thinking with" not in text


def test_the_panel_flags_a_failed_execution():
    text = "\n".join(
        render_intelligence(view_after(TransportTimeout("slow")), ASCII)
    )

    assert "execution(s) failed" in text
    assert "Failed" in text


def test_no_rendered_line_runs_past_the_frame():
    view = view_after(ok(model="a-fairly-long-model-name:with-a-tag"))
    lines = render_intelligence(view, ASCII)

    assert all(len(line) <= 74 for line in lines), [
        line for line in lines if len(line) > 74
    ]


def test_the_panel_encodes_on_a_cp1252_console():
    text = "\n".join(render_intelligence(view_after(ok()), ASCII))

    text.encode("cp1252")


def test_the_view_serialises_for_a_web_front_end():
    payload = founder_as_dict(view_after(ok()))["intelligence"]

    assert payload["thinking"]["provider"] == "alpha-local"
    assert payload["thinking"]["cache"] == "MISS"
    assert payload["economy"]["local_executions"] == 1


def test_the_serialised_view_has_no_thinking_before_anything_runs():
    harness = Harness("alpha_runtime")
    sources = DashboardSources(broker_provider=lambda: harness.service.report())

    payload = founder_as_dict(build_founder_view(sources.collect()))["intelligence"]

    assert payload["thinking"] is None


def test_the_panel_never_causes_an_execution():
    """ADR-0016, extended to the new panel: looking at the screen cannot
    make Kalpavriksha think."""
    harness, executor, provider = wired(ok())
    executor.run("q", request())
    sources = DashboardSources(broker_provider=lambda: harness.service.report())

    for _ in range(5):
        build_founder_view(sources.collect())

    assert len(provider._transport.posts) == 1


# =========================================================================
# The launcher wires it (Definition of Done)
# =========================================================================


def quiet_system(state_dir, **kwargs):
    """A launcher-built system that says nothing and states its own config.

    `config` is a `setdefault`, so the tests below that hand in their own
    `MasterAgentConfig` -- the ones asserting what `OllamaConfig` and
    `PromptCacheConfig` do to the wiring -- keep it. See `stated_config`
    for what arrives when this is left to `load_config()`: the founder's
    real `~/.master_agent`, and a live `GEMINI_API_KEY` that made this
    file's "only the transport is invented" tests contact a real endpoint.
    """
    state_dir = Path(state_dir)
    kwargs.setdefault("config", stated_config(state_dir.parent))
    kwargs.setdefault("runtime_config", RuntimeConfig(poll_interval_seconds=0))
    kwargs.setdefault("dashboard_kwargs", {"writer": lambda _text: None})
    return build_system(state_dir=state_dir, **kwargs)


def test_the_launcher_registers_a_provider_that_can_execute(tmp_path):
    system = quiet_system(tmp_path / "state")

    provider = system.providers.get(OLLAMA_PROVIDER_ID)

    assert callable(provider.complete)


def test_the_launcher_builds_a_prompt_executor(tmp_path):
    system = quiet_system(tmp_path / "state")

    assert system.prompt_executor is not None


def test_the_provider_registry_is_not_the_executive_registry(tmp_path):
    """ADR-0017 Decision 8: an AI Capability is not a Constitution
    Capability, so a provider is not a dispatchable Executive. Putting one
    in the Executive registry would add it to Mission Control, the
    Runtime's gateway map and the Dashboard -- three subsystems MB033 must
    not touch."""
    system = quiet_system(tmp_path / "state")

    assert system.providers is not system.registry
    assert OLLAMA_PROVIDER_ID not in [
        p.manifest.name for p in system.registry.all_plugins()
    ]


def test_a_provider_never_becomes_an_executive(tmp_path):
    system = quiet_system(tmp_path / "state")

    assert not system.mission_control.executives.has(OLLAMA_PROVIDER_ID)


def test_a_provider_never_gets_a_runtime_gateway(tmp_path):
    system = quiet_system(tmp_path / "state")

    assert OLLAMA_PROVIDER_ID not in system.runtime._gateways


def test_the_model_router_resolves_through_the_provider_registry(tmp_path):
    system = quiet_system(tmp_path / "state")

    assert system.model_router._registry is system.providers


def test_the_configured_model_is_what_the_provider_will_run(tmp_path):
    config = MasterAgentConfig(ollama=OllamaConfig(model="configured-model"))
    system = quiet_system(tmp_path / "state", config=config)

    assert system.providers.get(OLLAMA_PROVIDER_ID).model == "configured-model"


def test_the_configured_address_is_what_the_provider_will_reach(tmp_path):
    config = MasterAgentConfig(ollama=OllamaConfig(base_url="http://elsewhere:1234"))
    system = quiet_system(tmp_path / "state", config=config)

    assert system.providers.get(OLLAMA_PROVIDER_ID).base_url == "http://elsewhere:1234"


def test_a_disabled_provider_is_simply_not_registered(tmp_path):
    """Every provider is independently switchable — Build 2 added Gemini
    beside Ollama, and disabling one must never register the other by
    accident, so an empty registry now requires disabling both."""
    config = MasterAgentConfig(
        ollama=OllamaConfig(enabled=False), gemini=GeminiConfig(enabled=False)
    )
    system = quiet_system(tmp_path / "state", config=config)

    assert system.providers.all_plugins() == []
    assert "no provider is enabled" in system.report.step("Provider execution").detail


def test_the_boot_report_names_the_model_and_the_address(tmp_path):
    system = quiet_system(tmp_path / "state")
    detail = system.report.step("Provider execution").detail

    assert "hermes3" in detail
    assert "http://localhost:11434" in detail


def test_the_provider_is_built_even_when_the_daemon_is_not_running(tmp_path):
    """Reachability is a question for the moment of use, not for boot: a
    daemon started five minutes after launch should work, and a provider
    that probed at boot would have decided otherwise."""
    config = MasterAgentConfig(ollama=OllamaConfig(base_url="http://127.0.0.1:9"))
    system = quiet_system(tmp_path / "state", config=config)

    assert system.report.step("Provider execution").ok is True
    assert system.providers.all_plugins()


def test_the_cache_ships_on_since_a_verifier_exists(tmp_path):
    """MB033 shipped this off because nothing could verify generated text,
    so a cache could only ever have stored unchecked output. MB035 built
    the verifier, so the reason is gone — and the cache still stores
    nothing unless an answer was checked against an expected outcome."""
    system = quiet_system(tmp_path / "state")

    assert isinstance(system.prompt_executor.cache, ExactPromptCache)


def test_a_founder_can_turn_the_cache_off(tmp_path):
    config = MasterAgentConfig(prompt_cache=PromptCacheConfig(enabled=False))
    system = quiet_system(tmp_path / "state", config=config)

    assert isinstance(system.prompt_executor.cache, NullPromptCache)


def test_no_broker_means_nothing_can_be_executed(tmp_path):
    """Fail closed, all the way down: no Broker, no executor, and a boot
    report that says which half is missing."""
    config = MasterAgentConfig(broker=BrokerConfig(policy="nonsense"))
    system = quiet_system(tmp_path / "state", config=config)

    assert system.prompt_executor is None
    assert system.report.step("Provider execution").status == "unavailable"


def test_the_boot_report_places_execution_after_the_broker(tmp_path):
    """It carries out what the Broker decided; it cannot exist first."""
    system = quiet_system(tmp_path / "state")
    names = [step.name for step in system.report.steps]

    assert names.index("AI Capability Broker") < names.index("Provider execution")


def test_the_whole_definition_of_done_holds_end_to_end(tmp_path):
    """Task -> Broker -> Provider -> structured response -> ledger, through
    the launcher's own wiring, with only the transport invented."""
    from master_agent.desktop.plugin import DesktopPlugin
    from master_agent.executor.executor import LocalExecutor
    from master_agent.permissions.permission_system import PermissionSystem
    from master_agent.plugins.filesystem_plugin import FilesystemPlugin
    from tests.broker_test_support import FakeTransport
    from tests.test_broker_wiring import InstalledProbe, scan

    executor = LocalExecutor(PermissionSystem())
    system = quiet_system(
        tmp_path / "state",
        plugins=[
            FilesystemPlugin(executor),
            DesktopPlugin(executor, probe=InstalledProbe("ollama")),
        ],
    )
    scan(system)
    # Only the network is replaced. Everything above it is what ships.
    system.providers.get(OLLAMA_PROVIDER_ID)._transport = FakeTransport(
        ok(text="the real answer", prompt_tokens=9, completion_tokens=4)
    )

    outcome = system.prompt_executor.run(
        "what is the answer",
        SelectionRequest.from_context(RoutingContext(task_id="dod")),
    )

    assert outcome.ok is True
    assert outcome.text == "the real answer"
    assert outcome.provider_id == OLLAMA_PROVIDER_ID

    entry = system.intelligence.ledger.for_task("dod")
    assert entry.record is not None, "the decision is on the record"
    assert entry.execution.outcome == "succeeded"
    assert entry.execution.total_tokens == 13
    assert system.intelligence.ledger.replay_matches(entry.entry_id) is True

    frame = system.dashboard.render()
    assert "Thinking with" in frame
    assert OLLAMA_PROVIDER_ID in frame


def test_an_execution_survives_a_restart(tmp_path):
    """The ledger is the record, and MB033's metadata is part of it."""
    from master_agent.desktop.plugin import DesktopPlugin
    from master_agent.executor.executor import LocalExecutor
    from master_agent.permissions.permission_system import PermissionSystem
    from master_agent.plugins.filesystem_plugin import FilesystemPlugin
    from tests.broker_test_support import FakeTransport
    from tests.test_broker_wiring import InstalledProbe, scan

    state = tmp_path / "state"
    executor = LocalExecutor(PermissionSystem())
    first = quiet_system(
        state,
        plugins=[
            FilesystemPlugin(executor),
            DesktopPlugin(executor, probe=InstalledProbe("ollama")),
        ],
    )
    scan(first)
    first.providers.get(OLLAMA_PROVIDER_ID)._transport = FakeTransport(ok(text="kept"))
    first.prompt_executor.run(
        "q", SelectionRequest.from_context(RoutingContext(task_id="kept"))
    )
    first.stop()

    second = quiet_system(state)
    entry = second.intelligence.ledger.for_task("kept")

    assert entry.execution.outcome == "succeeded"
    assert second.intelligence.ledger.replay_matches(entry.entry_id) is True
    assert second.intelligence.report().economy.local_executions == 1
