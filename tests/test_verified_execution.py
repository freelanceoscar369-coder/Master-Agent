"""Mission Brief 035 — what a verdict changes.

MB033 shipped a Prompt Cache that never hit and MB034 shipped a Prompt
Library with no automatic writer. Both were waiting for the same sentence
to become true: *Kalpavriksha can tell whether an answer was any good.*

So this file is about the consequences rather than the verifier — that
the cache now stores on evidence instead of on a caller's promise, that a
checked prompt writes itself into memory, and that an unchecked answer
still gets neither.
"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from master_agent.ai_infrastructure.cache import HIT, MISS, ExactPromptCache
from master_agent.ai_infrastructure.economy import NO_CACHE
from master_agent.ai_infrastructure.execution import PromptExecutor
from master_agent.ai_infrastructure.ledger import DecisionLedger, ExecutionRecord
from master_agent.ai_infrastructure.text_verifier import expect
from master_agent.dashboard.charset import ASCII
from master_agent.dashboard.founder import as_dict as founder_as_dict
from master_agent.dashboard.founder import build_founder_view
from master_agent.dashboard.founder_panels import render_intelligence
from master_agent.dashboard.sources import DashboardSources
from master_agent.launcher.boot import build_system
from master_agent.memory.knowledge_store import InMemoryKnowledgeStore
from master_agent.memory.memory_models import (
    FAILURE_LIBRARY,
    HIGH,
    NORMAL,
    PROMPT_LIBRARY,
    VERIFICATION,
)
from master_agent.memory.memory_service import MemoryService
from master_agent.plugins.model_router import RoutingContext, SelectionRequest
from master_agent.plugins.registry import PluginRegistry
from master_agent.providers.ollama import OLLAMA_PROVIDER_ID
from master_agent.providers.transport import HttpResponse, TransportUnavailable
from master_agent.runtime.config import RuntimeConfig
from master_agent.verification.evidence import Verdict
from tests.broker_test_support import (
    FakeTransport,
    Harness,
    ollama,
    ollama_body,
    stated_config,
)

WHEN = datetime(2026, 7, 30, 16, 0, tzinfo=UTC)


def ok(**kwargs) -> HttpResponse:
    return HttpResponse(200, ollama_body(**kwargs))


def memory() -> MemoryService:
    service = MemoryService(store=InMemoryKnowledgeStore())
    service.load()
    return service


def wired(*responses, cache=None, remember=None, **harness_kwargs):
    """The MB033 harness plus MB035's memory sink."""
    harness = Harness("alpha_runtime", **harness_kwargs)
    registry = PluginRegistry()
    provider = ollama(
        *responses,
        provider_id="alpha-local",
        model="test-model",
    )
    registry.register(provider)
    executor = PromptExecutor(
        service=harness.service,
        providers=registry,
        ledger=harness.ledger,
        cache=cache,
        clock=lambda: WHEN,
        memory_sink=remember,
    )
    return harness, executor, provider


def request(**kwargs) -> SelectionRequest:
    kwargs.setdefault("task_id", "t1")
    return SelectionRequest(**kwargs)


# =========================================================================
# The verdict reaches the record
# =========================================================================


def test_an_unchecked_answer_has_no_verdict():
    """"Not checked" and "checked and failed" are different facts."""
    harness, executor, _provider = wired(ok(text="anything"))

    outcome = executor.run("q", request())

    assert outcome.verdict == ""
    assert outcome.verified is False
    assert harness.ledger.get(1).execution.verdict == ""


def test_a_checked_answer_records_its_verdict():
    harness, executor, _provider = wired(ok(text="blue"))

    outcome = executor.run("q", request(), expected=expect(contains_all=["blue"]))

    assert outcome.verdict == "matched"
    assert outcome.verified is True
    assert harness.ledger.get(1).execution.verdict == "matched"
    assert harness.ledger.get(1).execution.verified is True


def test_a_failing_answer_records_that_too():
    harness, executor, _provider = wired(ok(text="red"))

    outcome = executor.run("q", request(), expected=expect(contains_all=["blue"]))

    assert outcome.verdict == "partially_matched"
    assert outcome.verified is False
    assert harness.ledger.get(1).execution.verified is False


def test_the_evidence_travels_with_the_outcome():
    _harness, executor, _provider = wired(ok(text="blue"))

    outcome = executor.run("q", request(), expected=expect(contains_all=["blue"]))

    assert outcome.evidence is not None
    assert outcome.evidence.verdict is Verdict.MATCHED
    assert outcome.evidence.observation["text"] == "blue"


def test_the_evidence_id_is_recorded_so_a_claim_can_be_traced():
    harness, executor, _provider = wired(ok(text="blue"))

    outcome = executor.run("q", request(), expected=expect(contains_all=["blue"]))

    assert harness.ledger.get(1).execution.evidence_id == outcome.evidence.evidence_id


def test_a_failed_call_is_never_verified():
    """A timeout has no text, and running checks against "" would produce
    a confident NOT_MATCHED that says nothing the outcome did not already
    say."""
    harness, executor, _provider = wired(
        TransportUnavailable("down")
    )

    outcome = executor.run("q", request(), expected=expect(contains_all=["blue"]))

    assert outcome.ok is False
    assert outcome.evidence is None
    assert harness.ledger.get(1).execution.verdict == ""


def test_recording_a_verdict_leaves_the_decision_replayable():
    harness, executor, _provider = wired(ok(text="blue"))

    executor.run("q", request(), expected=expect(contains_all=["blue"]))

    assert harness.ledger.replay_matches(1) is True


def test_a_verdict_survives_a_round_trip_through_storage():
    harness, executor, _provider = wired(ok(text="blue"))
    executor.run("q", request(), expected=expect(contains_all=["blue"]))

    rebuilt = DecisionLedger()
    rebuilt.restore(harness.ledger.as_dicts())

    assert rebuilt.get(1).execution.verdict == "matched"
    assert rebuilt.get(1).execution.evidence_id


def test_a_ledger_written_before_this_brief_still_loads():
    """Every entry MB033 and MB034 wrote has no verdict. Missing means
    "nothing was asked of the answer", which is what those were."""
    harness, executor, _provider = wired(ok())
    executor.run("q", request())
    rows = harness.ledger.as_dicts()
    del rows[0]["execution"]["verdict"]
    del rows[0]["execution"]["evidence_id"]

    rebuilt = DecisionLedger()
    rebuilt.restore(rows)

    assert rebuilt.get(1).execution.verdict == ""
    assert rebuilt.get(1).execution.verified is False


@pytest.mark.parametrize(
    ("verdict", "verified"),
    [
        ("matched", True),
        ("partially_matched", False),
        ("not_matched", False),
        ("error", False),
        ("", False),
    ],
)
def test_only_matched_counts_as_verified_on_the_record(verdict, verified):
    record = ExecutionRecord(provider_id="p", outcome="succeeded", verdict=verdict)

    assert record.verified is verified


# =========================================================================
# The cache now stores on evidence, not on a promise
# =========================================================================


def test_a_verified_answer_is_cached():
    cache = ExactPromptCache()
    _harness, executor, _provider = wired(ok(text="blue"), cache=cache)

    executor.run("q", request(), expected=expect(contains_all=["blue"]))

    assert len(cache) == 1


def test_an_answer_that_failed_its_checks_is_not_cached():
    """The load-bearing change: what gets remembered is decided by
    evidence, not by whoever called."""
    cache = ExactPromptCache()
    _harness, executor, _provider = wired(ok(text="red"), cache=cache)

    executor.run("q", request(), expected=expect(contains_all=["blue"]))

    assert len(cache) == 0


def test_a_partially_matching_answer_is_not_cached():
    """Half of what was asked for is not what was asked for, and a cache
    that remembered it would serve the same half answer forever."""
    cache = ExactPromptCache()
    _harness, executor, _provider = wired(ok(text="blue"), cache=cache)

    executor.run("q", request(), expected=expect(contains_all=["blue", "sky"]))

    assert len(cache) == 0


def test_an_unchecked_answer_is_still_not_cached():
    """MB033's rule, unchanged: nothing verified, nothing stored."""
    cache = ExactPromptCache()
    _harness, executor, _provider = wired(ok(), cache=cache)

    executor.run("q", request())

    assert len(cache) == 0


def test_evidence_overrules_a_caller_claiming_the_answer_was_verified():
    """The whole point of ADR-0011 keeping Verification independent of
    Execution: a promise loses to a check."""
    cache = ExactPromptCache()
    _harness, executor, _provider = wired(ok(text="red"), cache=cache)

    outcome = executor.run(
        "q", request(), verified=True, expected=expect(contains_all=["blue"])
    )

    assert outcome.verified is False
    assert len(cache) == 0


def test_a_caller_with_nothing_to_check_against_can_still_promise():
    """MB033's door survives for callers that have no expectation to
    state — it is still a promise, and still never the default."""
    cache = ExactPromptCache()
    _harness, executor, _provider = wired(ok(), cache=cache)

    executor.run("q", request(), verified=True)

    assert len(cache) == 1


def test_a_verified_answer_is_reused_without_contacting_the_provider():
    """MB033's efficiency criterion, finally reachable."""
    cache = ExactPromptCache()
    _harness, executor, provider = wired(ok(text="blue"), cache=cache)
    expectation = expect(contains_all=["blue"])
    executor.run("same question", request(task_id="a"), expected=expectation)

    outcome = executor.run("same question", request(task_id="b"), expected=expectation)

    assert outcome.cache == HIT
    assert outcome.text == "blue"
    assert len(provider._transport.posts) == 1


def test_a_reused_answer_is_checked_against_what_this_caller_asked_for():
    """A stored answer was verified against *the expectation it was stored
    under*. Serving it to a caller asking for something else without
    checking is how "everything reused was verified" quietly stops being
    true — found by a live run that asked one prompt with two different
    expectations."""
    cache = ExactPromptCache()
    _harness, executor, _provider = wired(ok(text="blue"), cache=cache)
    expectation = expect(contains_all=["blue"])
    executor.run("q", request(task_id="a"), expected=expectation)

    outcome = executor.run("q", request(task_id="b"), expected=expectation)

    assert outcome.cache == HIT
    assert outcome.verdict == "matched", "a hit carries a verdict for this caller"


def test_a_cached_answer_that_fails_a_new_expectation_is_not_served():
    cache = ExactPromptCache()
    _harness, executor, provider = wired(
        ok(text="blue"), ok(text="blue"), cache=cache
    )
    executor.run("q", request(task_id="a"), expected=expect(contains_all=["blue"]))

    outcome = executor.run(
        "q", request(task_id="b"), expected=expect(contains_all=["kalpavriksha"])
    )

    assert outcome.cache == MISS
    assert len(provider._transport.posts) == 2, "the provider was asked again"


def test_a_caller_asking_for_nothing_gets_the_cached_answer_unchecked():
    """Anything satisfies an expectation nobody stated."""
    cache = ExactPromptCache()
    _harness, executor, provider = wired(ok(text="blue"), cache=cache)
    executor.run("q", request(task_id="a"), expected=expect(contains_all=["blue"]))

    outcome = executor.run("q", request(task_id="b"))

    assert outcome.cache == HIT
    assert outcome.verdict == ""
    assert len(provider._transport.posts) == 1


def test_re_checking_a_hit_costs_no_provider_call():
    """Re-checking is arithmetic; calling the provider again is seconds.
    That is the whole reason a hit is re-verified rather than discarded."""
    cache = ExactPromptCache()
    _harness, executor, provider = wired(ok(text="blue"), cache=cache)
    expectation = expect(contains_all=["blue"])
    executor.run("q", request(task_id="a"), expected=expectation)

    executor.run("q", request(task_id="b"), expected=expectation)

    assert len(provider._transport.posts) == 1


def test_the_economy_counts_a_reuse_once_verification_makes_one_possible():
    cache = ExactPromptCache()
    harness, executor, _provider = wired(ok(text="blue"), cache=cache)
    expectation = expect(contains_all=["blue"])
    executor.run("q", request(task_id="a"), expected=expectation)
    executor.run("q", request(task_id="b"), expected=expectation)

    economy = harness.service.report().economy

    assert economy.cache_hits == 1
    assert economy.cache_misses == 1


def test_the_economy_explains_an_empty_cache_by_what_is_outstanding_now():
    """MB033's message blamed a missing verifier. MB035 built it, so the
    message names the condition that is actually left."""
    harness, executor, _provider = wired(ok())
    executor.run("q", request())

    assert harness.service.report().economy.basis == NO_CACHE
    assert "verified against an expected outcome" in NO_CACHE


# =========================================================================
# A checked prompt writes itself into memory (MB034's missing writer)
# =========================================================================


def sink_for(service: MemoryService):
    def remember(prompt, outcome):
        return service.remember_prompt(
            prompt=prompt,
            provider_id=outcome.provider_id or "unknown",
            verdict=outcome.verdict,
            expectation=(
                outcome.evidence.expected.description if outcome.evidence else ""
            ),
            evidence_id=outcome.evidence.evidence_id if outcome.evidence else "",
        )

    return remember


def test_a_prompt_that_worked_reaches_the_prompt_library():
    knowledge = memory()
    _harness, executor, _provider = wired(ok(text="blue"), remember=sink_for(knowledge))

    executor.run(
        "What colour is the sky?", request(), expected=expect(contains_all=["blue"])
    )

    written = knowledge.find_by_category(PROMPT_LIBRARY)
    assert len(written) == 1
    assert "What colour is the sky?" in written[0].full_text
    assert written[0].source == VERIFICATION
    assert written[0].importance == NORMAL


def test_a_prompt_that_failed_reaches_the_failure_library():
    knowledge = memory()
    _harness, executor, _provider = wired(ok(text="red"), remember=sink_for(knowledge))

    executor.run("A question", request(), expected=expect(contains_all=["blue"]))

    written = knowledge.find_by_category(FAILURE_LIBRARY)
    assert len(written) == 1
    assert written[0].importance == HIGH


def test_the_memory_names_the_provider_and_the_verdict():
    knowledge = memory()
    _harness, executor, _provider = wired(ok(text="blue"), remember=sink_for(knowledge))

    executor.run("A question", request(), expected=expect(contains_all=["blue"]))
    record = knowledge.recent()[0]

    assert "alpha-local" in record.full_text
    assert "matched" in record.tags
    assert "prompt" in record.tags


def test_the_memory_carries_the_evidence_id():
    """A claim that a prompt worked has to be traceable to the check that
    said so."""
    knowledge = memory()
    _harness, executor, _provider = wired(ok(text="blue"), remember=sink_for(knowledge))

    outcome = executor.run("q", request(), expected=expect(contains_all=["blue"]))

    assert outcome.evidence.evidence_id in knowledge.recent()[0].summary


def test_the_memory_records_what_was_asked_for():
    knowledge = memory()
    _harness, executor, _provider = wired(ok(text="blue"), remember=sink_for(knowledge))

    executor.run(
        "q", request(), expected=expect(description="a colour", contains_all=["blue"])
    )

    assert "a colour" in knowledge.recent()[0].full_text


def test_an_unchecked_answer_teaches_memory_nothing():
    """Writing it down would fill the Prompt Library with prompts nobody
    established worked."""
    knowledge = memory()
    _harness, executor, _provider = wired(ok(), remember=sink_for(knowledge))

    executor.run("q", request())

    assert len(knowledge) == 0


def test_a_failed_call_teaches_memory_nothing_either():
    knowledge = memory()
    _harness, executor, _provider = wired(
        TransportUnavailable("down"), remember=sink_for(knowledge)
    )

    executor.run("q", request(), expected=expect(contains_all=["blue"]))

    assert len(knowledge) == 0


def test_a_refusal_teaches_memory_nothing():
    knowledge = memory()
    harness = Harness(scanned=False)
    executor = PromptExecutor(
        harness.service,
        PluginRegistry(),
        harness.ledger,
        clock=lambda: WHEN,
        memory_sink=sink_for(knowledge),
    )

    outcome = executor.run("q", request(), expected=expect())

    assert outcome.refused is True
    assert len(knowledge) == 0


def test_asking_the_same_thing_twice_is_one_memory():
    """MB034's duplicate suppression, still holding on the automatic
    path."""
    knowledge = memory()
    _harness, executor, _provider = wired(
        ok(text="blue"), ok(text="blue"), remember=sink_for(knowledge)
    )
    expectation = expect(contains_all=["blue"])

    executor.run("q", request(task_id="a"), expected=expectation)
    executor.run("q", request(task_id="b"), expected=expectation)

    assert len(knowledge) == 1


def test_a_broken_memory_never_takes_down_the_answer():
    """Remembering never gates work — the posture every sink in this
    codebase takes."""

    def explode(prompt, outcome):
        raise OSError("disk full")

    _harness, executor, _provider = wired(ok(text="blue"), remember=explode)

    outcome = executor.run("q", request(), expected=expect(contains_all=["blue"]))

    assert outcome.ok is True
    assert executor.memory_failures


def test_no_sink_is_a_normal_configuration():
    _harness, executor, _provider = wired(ok(text="blue"))

    assert executor.run("q", request(), expected=expect(contains_all=["blue"])).ok


def test_the_prompt_library_writer_is_reachable_directly():
    """`memory/` reaches neither the Broker nor a provider, so the
    executor calls *out* to it rather than importing anything."""
    knowledge = memory()

    write = knowledge.remember_prompt(
        prompt="Summarise this", provider_id="p", verdict="matched"
    )

    assert write.record.category == PROMPT_LIBRARY


def test_memory_still_imports_nothing_from_the_execution_layer():
    import ast
    from pathlib import Path

    path = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "master_agent"
        / "memory"
        / "memory_service.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert not node.module.startswith("master_agent.ai_infrastructure")
            assert not node.module.startswith("master_agent.providers")


# =========================================================================
# What the founder sees
# =========================================================================


def view_after(*responses, expected=None, **kwargs):
    harness, executor, _provider = wired(*responses, **kwargs)
    executor.run("q", request(), expected=expected)
    sources = DashboardSources(broker_provider=lambda: harness.service.report())
    return build_founder_view(sources.collect())


def test_an_unchecked_answer_says_so_rather_than_showing_a_blank():
    view = view_after(ok())

    assert view.intelligence.thinking.verified == "not checked"


def test_a_verified_answer_says_matched():
    view = view_after(ok(text="blue"), expected=expect(contains_all=["blue"]))

    assert view.intelligence.thinking.verified == "matched"


def test_a_failed_check_is_shown_in_words_a_founder_reads():
    view = view_after(ok(text="red"), expected=expect(contains_all=["blue"]))

    assert view.intelligence.thinking.verified == "partially matched"


def test_the_panel_shows_the_verdict():
    view = view_after(ok(text="blue"), expected=expect(contains_all=["blue"]))
    text = "\n".join(render_intelligence(view, ASCII))

    assert "Verified       matched" in text


def test_the_panel_says_not_checked_when_nothing_was_asked():
    text = "\n".join(render_intelligence(view_after(ok()), ASCII))

    assert "Verified       not checked" in text


def test_no_rendered_line_runs_past_the_frame():
    view = view_after(ok(text="blue"), expected=expect(contains_all=["blue"]))
    lines = render_intelligence(view, ASCII)

    assert all(len(line) <= 74 for line in lines), [
        line for line in lines if len(line) > 74
    ]


def test_the_panel_encodes_on_a_cp1252_console():
    view = view_after(ok(text="blue"), expected=expect(contains_all=["blue"]))

    "\n".join(render_intelligence(view, ASCII)).encode("cp1252")


def test_the_view_serialises_for_a_web_front_end():
    view = view_after(ok(text="blue"), expected=expect(contains_all=["blue"]))

    payload = founder_as_dict(view)["intelligence"]["thinking"]

    assert payload["verified"] == "matched"


def test_the_outcome_serialises_its_verdict():
    _harness, executor, _provider = wired(ok(text="blue"))

    payload = executor.run(
        "q", request(), expected=expect(contains_all=["blue"])
    ).as_dict()

    assert payload["verdict"] == "matched"
    assert payload["verified"] is True


# =========================================================================
# The launcher, end to end
# =========================================================================


def quiet_system(state_dir, **kwargs):
    state_dir = Path(state_dir)
    # `app_dir` is the *parent*: the launcher puts founder memory beside
    # the state directory rather than inside it, so this is the one value
    # that keeps both of them under the test's `tmp_path`.
    kwargs.setdefault("config", stated_config(state_dir.parent))
    kwargs.setdefault("runtime_config", RuntimeConfig(poll_interval_seconds=0))
    kwargs.setdefault("dashboard_kwargs", {"writer": lambda _text: None})
    return build_system(state_dir=state_dir, **kwargs)


def scanned_system(tmp_path):
    from master_agent.desktop.plugin import DesktopPlugin
    from master_agent.executor.executor import LocalExecutor
    from master_agent.permissions.permission_system import PermissionSystem
    from master_agent.plugins.filesystem_plugin import FilesystemPlugin
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
    return system


def test_the_launcher_wires_the_memory_sink(tmp_path):
    system = quiet_system(tmp_path / "state")

    assert system.prompt_executor._memory_sink is not None


def test_a_verified_answer_reaches_the_founders_memory_end_to_end(tmp_path):
    """Task -> Broker -> provider -> verdict -> Prompt Library, through
    the launcher's own wiring, with only the transport invented."""
    system = scanned_system(tmp_path)
    system.providers.get(OLLAMA_PROVIDER_ID)._transport = FakeTransport(
        ok(text="The sky is blue.")
    )

    outcome = system.prompt_executor.run(
        "What colour is the sky?",
        SelectionRequest.from_context(RoutingContext(task_id="live")),
        expected=expect(description="names a colour", contains_all=["blue"]),
    )

    assert outcome.verified is True
    written = system.memory.find_by_category(PROMPT_LIBRARY)
    assert len(written) == 1
    assert "names a colour" in written[0].full_text
    assert system.intelligence.ledger.for_task("live").execution.verdict == "matched"


def test_a_verified_answer_is_reused_on_the_second_ask(tmp_path):
    """The cache ships on now, and the whole path is real."""
    system = scanned_system(tmp_path)
    transport = FakeTransport(ok(text="blue"))
    system.providers.get(OLLAMA_PROVIDER_ID)._transport = transport
    expectation = expect(contains_all=["blue"])

    system.prompt_executor.run(
        "q", SelectionRequest.from_context(RoutingContext(task_id="a")),
        expected=expectation,
    )
    second = system.prompt_executor.run(
        "q", SelectionRequest.from_context(RoutingContext(task_id="b")),
        expected=expectation,
    )

    assert second.cache == HIT
    assert len(transport.posts) == 1
    assert system.intelligence.report().economy.cache_hits == 1


def test_an_unverified_answer_is_asked_again(tmp_path):
    """Nothing was established, so nothing was remembered — and the
    provider is contacted a second time."""
    system = scanned_system(tmp_path)
    transport = FakeTransport(ok(text="blue"))
    system.providers.get(OLLAMA_PROVIDER_ID)._transport = transport

    for task in ("a", "b"):
        system.prompt_executor.run(
            "q", SelectionRequest.from_context(RoutingContext(task_id=task))
        )

    assert len(transport.posts) == 2
    assert system.prompt_executor.run(
        "q", SelectionRequest.from_context(RoutingContext(task_id="c"))
    ).cache == MISS


def test_what_a_prompt_taught_survives_a_restart(tmp_path):
    system = scanned_system(tmp_path)
    system.providers.get(OLLAMA_PROVIDER_ID)._transport = FakeTransport(ok(text="blue"))
    system.prompt_executor.run(
        "What colour is the sky?",
        SelectionRequest.from_context(RoutingContext(task_id="a")),
        expected=expect(contains_all=["blue"]),
    )
    system.stop()

    second = quiet_system(tmp_path / "state")

    assert len(second.memory.find_by_category(PROMPT_LIBRARY)) == 1
    assert second.memory.search("sky")[0].category == PROMPT_LIBRARY
