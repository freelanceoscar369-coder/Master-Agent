"""Mission Brief 037 — the whole hierarchy, in one process.

```
Founder -> MissionService -> Planner -> Broker -> Provider
        -> Mission Control -> Executive -> Verifier -> Evidence -> Memory
```

Every layer here is the shipped one: the real `AiCapabilityService` and
`CapabilityBroker` choosing a provider, the real `OllamaProvider` over a
scripted socket, the real `PromptExecutor` recording the call, the real
Dispatcher ordering the work, the real `RuntimeEngine` running and
verifying it, and the real `MemoryService` learning from the outcome.

Only two things are invented: the bytes the daemon would have returned,
and the Executive's own result. Everything between them is production
code, which is what makes this the file that would catch an integration
regression the unit tests cannot.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from master_agent.ai_infrastructure.execution import PromptExecutor
from master_agent.dashboard.founder import build_founder_view
from master_agent.dashboard.sources import DashboardSources
from master_agent.memory.knowledge_store import JsonKnowledgeStore
from master_agent.memory.memory_service import MemoryService
from master_agent.mission_control.executives import ExecutiveHealth
from master_agent.mission_control.mission_control import MissionControl
from master_agent.missions.history import COMPLETED, PlanHistory
from master_agent.brain import IntentLayer
from master_agent.missions.service import MissionService
from master_agent.planner.planner import Planner
from master_agent.plugins.registry import PluginRegistry
from master_agent.providers.transport import HttpResponse
from master_agent.runtime.config import RuntimeConfig
from master_agent.runtime.engine import RuntimeEngine
from master_agent.runtime.gateway import GatewayResult
from tests.broker_test_support import Harness, ollama, ollama_body
from tests.missions_test_support import descriptors
from tests.planner_test_support import CREATE, WRITE, plan_text, step, success

WHEN = datetime(2026, 7, 31, 10, 0, tzinfo=UTC)

PLAN = plan_text(
    step("make_folder", CREATE.name, {"name": "demo"},
         success_doc=success("the folder is created", must_contain=["created"])),
    step("write_readme", WRITE.name, {"path": "demo/README.md"},
         depends_on=["make_folder"],
         success_doc=success("the file is written", must_contain=["written"])),
)


class FilesystemGateway:
    """Stands in for the Filesystem Executive, with a real Verifier
    behind `verify()` -- the same pairing `PluginGateway` documents."""

    def __init__(self, results: dict[str, str]) -> None:
        self.results = results
        self.invoked: list[tuple[str, dict]] = []

    def capabilities(self) -> list[str]:
        return ["create_folder", "write_file"]

    def invoke(self, capability: str, payload: dict) -> GatewayResult:
        self.invoked.append((capability, dict(payload)))
        return GatewayResult(success=True, output=self.results[capability])

    def verify(self, capability: str, payload: dict, expected: Any) -> Any:
        from master_agent.ai_infrastructure.text_verifier import verify_text

        return verify_text(self.results[capability], expected)


class AlwaysApprove:
    def check(self, _request: Any) -> None:
        return None


def whole_system(tmp_path, reply: str = PLAN):
    """Wired the way `launcher/boot.py` wires it."""
    mission_control = MissionControl()
    for executive_id in sorted({d.executive_id for d in descriptors()}):
        mission_control.register_executive(
            executive_id,
            version="test",
            capabilities=[d for d in descriptors() if d.executive_id == executive_id],
            health=ExecutiveHealth.HEALTHY,
        )
        mission_control.mark_executive_ready(executive_id)

    harness = Harness("alpha_runtime")
    providers = PluginRegistry()
    provider = ollama(
        HttpResponse(200, ollama_body(text=reply)),
        provider_id="alpha-local",
        model="test-model",
        # MB038: the Planner asks for a budget, so planning calls stream.
        stream=[json.dumps({"response": reply, "done": True, "eval_count": 9})],
    )
    providers.register(provider)
    executor = PromptExecutor(
        service=harness.service,
        providers=providers,
        ledger=harness.ledger,
        clock=lambda: WHEN,
    )

    memory = MemoryService(store=JsonKnowledgeStore(tmp_path / "knowledge"))
    memory.load()
    memory.attach_to(mission_control)

    history = PlanHistory()
    history.attach_to(mission_control)

    intent_layer = IntentLayer()

    missions = MissionService(
        planner=Planner(executor, mission_control.capabilities),
        mission_control=mission_control,
        intent_layer=intent_layer,
        history=history,
        memory=memory,
    )

    gateway = FilesystemGateway({"create_folder": "created demo", "write_file": "written"})
    runtime = RuntimeEngine(
        mission_control=mission_control,
        config=RuntimeConfig(max_cycles=12),
        approval_gate=AlwaysApprove(),
    )
    runtime.register_gateway("filesystem", gateway)

    return {
        "mission_control": mission_control,
        "harness": harness,
        "provider": provider,
        "memory": memory,
        "history": history,
        "missions": missions,
        "gateway": gateway,
        "runtime": runtime,
    }


# =========================================================================
# The whole path
# =========================================================================


def test_one_objective_travels_the_entire_hierarchy(tmp_path):
    """The Definition of Done, in one assertion block."""
    system = whole_system(tmp_path)

    outcome = system["missions"].start("Set up a demo project")
    for _ in range(4):
        system["runtime"].run_once()

    # Planner produced a plan through the Broker.
    assert outcome.accepted
    assert outcome.provider_id == "alpha-local"
    assert system["provider"]._transport.streamed, "no provider was contacted"

    # Mission Control executed it in dependency order.
    assert [name for name, _ in system["gateway"].invoked] == ["create_folder", "write_file"]

    # The Verifier produced Evidence for every step.
    record = system["history"].get(outcome.objective_id)
    assert record.state == COMPLETED
    assert [s.verdict for s in record.steps] == ["matched", "matched"]
    assert all(s.evidence_id for s in record.steps)

    # Memory learned from it.
    assert any(
        r.title == "Mission completed: Set up a demo project" for r in system["memory"].all()
    )


def test_the_broker_chose_the_provider_and_recorded_the_decision(tmp_path):
    """Planning is a Broker decision on the same ledger as every other AI
    call. It does not get a private path to a model."""
    system = whole_system(tmp_path)

    system["missions"].start("Set up a demo project")

    entries = system["harness"].ledger.recent()
    assert entries
    assert entries[-1].provider_id == "alpha-local"


def test_the_planner_asked_for_a_capability_not_for_a_product(tmp_path):
    system = whole_system(tmp_path)

    system["missions"].start("Set up a demo project")

    _url, payload, _timeout = system["provider"]._transport.streamed[0]
    for vendor in ("gemma", "claude", "gpt", "qwen", "deepseek"):
        assert vendor not in payload["prompt"].lower()


def test_the_prompt_carries_the_real_capability_registry(tmp_path):
    """No hardcoded capability names: what the model is shown is what
    Mission Control actually has."""
    system = whole_system(tmp_path)

    system["missions"].start("Set up a demo project")

    _url, payload, _timeout = system["provider"]._transport.streamed[0]
    for name in system["mission_control"].capabilities.names():
        assert name in payload["prompt"]


def test_the_dashboard_reflects_progress_as_the_mission_runs(tmp_path):
    system = whole_system(tmp_path)
    sources = DashboardSources(
        mission_control=system["mission_control"],
        plan_provider=lambda: system["history"],
        clock=lambda: WHEN,
    )

    system["missions"].start("Set up a demo project")
    before = build_founder_view(sources.collect())
    assert before.plan.completed == 0
    assert before.plan.current_step == "make_folder"

    for _ in range(4):
        system["runtime"].run_once()

    after = build_founder_view(sources.collect())
    assert after.plan.completed == 2
    assert after.plan.progress == 1.0
    assert after.plan.failed == 0
    assert after.plan.unverified == 0


def test_the_finished_mission_replays_without_touching_the_provider(tmp_path):
    system = whole_system(tmp_path)
    outcome = system["missions"].start("Set up a demo project")
    for _ in range(4):
        system["runtime"].run_once()
    streamed_calls = len(system["provider"]._transport.streamed)

    replay = system["history"].replay(outcome.objective_id)

    assert replay.complete
    assert [s.capability for s in replay.steps] == [CREATE.name, WRITE.name]
    assert len(system["provider"]._transport.streamed) == streamed_calls


def test_a_provider_that_returns_prose_starts_no_mission(tmp_path):
    system = whole_system(tmp_path, reply="Sure! Here's how I'd do that.")

    outcome = system["missions"].start("Set up a demo project")

    assert not outcome.accepted
    assert system["mission_control"].dispatcher.objectives() == []
    assert system["gateway"].invoked == []


def test_a_plan_naming_an_unregistered_capability_starts_no_mission(tmp_path):
    system = whole_system(tmp_path, reply=plan_text(step("one", "Filesystem.Teleport", {})))

    outcome = system["missions"].start("Teleport the folder")

    assert not outcome.accepted
    assert "does not exist" in outcome.reason
    assert system["mission_control"].dispatcher.objectives() == []


def test_the_refusal_is_remembered_so_the_next_session_knows(tmp_path):
    system = whole_system(tmp_path, reply="Sure! Here's how I'd do that.")

    system["missions"].start("Set up a demo project")

    assert any("Could not plan" in r.title for r in system["memory"].all())


def test_nothing_ran_before_the_plan_was_verified(tmp_path):
    """The plan document itself is checked by MB035 before it is parsed,
    so a provider that answers with something unusable never reaches the
    Dispatcher at all."""
    system = whole_system(tmp_path, reply='{"not_steps": []}')

    system["missions"].start("Set up a demo project")

    assert system["gateway"].invoked == []
    assert system["mission_control"].dispatcher.objectives() == []
