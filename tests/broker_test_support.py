"""Shared fixtures for the MB032 Broker integration suite.

Real components wherever one exists: a real `MissionControl`, a real
`PermissionSystem`, a real `CapabilityBroker`, a real `MachineInventory`.
The only invented things are the *provider estate* and a model provider
plugin that records what it was asked — because there is no real provider
in this build to call, and a fake shaped like the shipped catalogue would
be testing the catalogue's numbers rather than the wiring.

The estate is deliberately invented rather than imported from
`ai_infrastructure.catalog`: a test that asserts against the shipped
catalogue turns every future edit of a declared quality number into a test
failure, which teaches people to edit tests instead of thinking.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from master_agent.ai_infrastructure.approval import ProviderApprovalGate
from master_agent.ai_infrastructure.catalog import ProviderSpec
from master_agent.ai_infrastructure.ledger import DecisionLedger, InMemoryDecisionStore
from master_agent.ai_infrastructure.profiles import ProviderSource
from master_agent.ai_infrastructure.service import AiCapabilityService
from master_agent.broker.broker import CapabilityBroker
from master_agent.broker.policy import BALANCED, SelectionPolicy
from master_agent.desktop.inventory import (
    INSTALLED,
    MISSING,
    InstalledApplication,
    MachineInventory,
)
from master_agent.mission_control.mission_control import MissionControl
from master_agent.permissions.permission_system import PermissionSystem
from master_agent.plugins.base import (
    CapabilityManifest,
    ModelProvider,
    PluginManifest,
    RiskTier,
)
from master_agent.providers.ollama import OllamaProvider
from master_agent.providers.transport import HttpResponse

FIXED = datetime(2026, 7, 30, 11, 30, tzinfo=UTC)

# ---- an invented estate -------------------------------------------------
#
# Five providers spanning every axis the Broker filters on: local/desktop/
# cloud, private/third-party, free/paid, present/absent, credentialled or
# not. Ids are lexicographic-tie-break-friendly and name no real product.

LOCAL_FREE = ProviderSpec(
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
)
LOCAL_WEAK = ProviderSpec(
    provider_id="beta-local-weak",
    label="Beta Local",
    capabilities=frozenset({"reasoning"}),
    locality="local",
    privacy="private",
    declared_quality=0.55,
    cost_per_call=0.0,
    latency_ms=9000.0,
    requires_network=False,
    max_context_tokens=8_192,
    inventory_key="beta_runtime",
)
DESKTOP_SUB = ProviderSpec(
    provider_id="gamma-desktop",
    label="Gamma Desktop",
    capabilities=frozenset({"reasoning", "reasoning.planning"}),
    locality="desktop",
    privacy="third_party",
    declared_quality=0.88,
    cost_per_call=0.0,
    latency_ms=3000.0,
    max_context_tokens=200_000,
    inventory_key="gamma_app",
)
CLOUD_CHEAP = ProviderSpec(
    provider_id="delta-cloud",
    label="Delta Cloud",
    capabilities=frozenset({"reasoning", "coding"}),
    locality="cloud",
    privacy="third_party",
    declared_quality=0.86,
    cost_per_call=0.005,
    latency_ms=1500.0,
    max_context_tokens=128_000,
    needs_credentials=True,
)
CLOUD_BEST = ProviderSpec(
    provider_id="epsilon-cloud",
    label="Epsilon Cloud",
    capabilities=frozenset({"reasoning", "reasoning.planning", "coding"}),
    locality="cloud",
    privacy="third_party",
    declared_quality=0.95,
    cost_per_call=0.05,
    latency_ms=1200.0,
    max_context_tokens=128_000,
    needs_credentials=True,
)

ESTATE: tuple[ProviderSpec, ...] = (
    LOCAL_FREE,
    LOCAL_WEAK,
    DESKTOP_SUB,
    CLOUD_CHEAP,
    CLOUD_BEST,
)


def application(
    key: str, installed: bool = True, healthy: bool = True, version: str | None = "1.0"
) -> InstalledApplication:
    return InstalledApplication(
        key=key,
        name=key.replace("_", " ").title(),
        category="ai",
        status=INSTALLED if installed else MISSING,
        version=version if installed else None,
        launchable=installed,
        healthy=healthy,
    )


def inventory(*keys: str, **states: bool) -> MachineInventory:
    """A machine with `keys` installed and healthy.

    `states` overrides health: `inventory("a", "b", b=False)` installs both
    and marks `b` present-but-not-answering.
    """
    applications = [
        application(key, installed=True, healthy=states.get(key, True)) for key in keys
    ]
    return MachineInventory(
        applications=applications, processes=[], platform="test", captured_at=FIXED
    )


def source(
    *installed: str,
    enabled: tuple[str, ...] = (),
    specs: tuple[ProviderSpec, ...] = ESTATE,
    scanned: bool = True,
) -> ProviderSource:
    """A `ProviderSource` over the invented estate. `scanned=False` models
    a system that has not run a machine scan yet."""
    machine = inventory(*installed) if scanned else None
    return ProviderSource(
        inventory_provider=(lambda: machine),
        specs=specs,
        enabled_cloud_providers=enabled,
    )


class Harness:
    """Everything one MB032 scenario needs, wired the way the launcher
    wires it — same components, same order, same contracts."""

    def __init__(
        self,
        *installed: str,
        enabled: tuple[str, ...] = (),
        policy: SelectionPolicy = BALANCED,
        specs: tuple[ProviderSpec, ...] = ESTATE,
        scanned: bool = True,
        with_approvals: bool = True,
        strong_floor: float | None = 0.90,
        store: Any = None,
    ) -> None:
        self.mission_control = MissionControl()
        self.permissions = PermissionSystem()
        self.store = store if store is not None else InMemoryDecisionStore()
        self.ledger = DecisionLedger(store=self.store)
        self.broker = CapabilityBroker(
            policy=policy, sink=self.ledger.record, clock=lambda: FIXED
        )
        self.providers = source(
            *installed, enabled=enabled, specs=specs, scanned=scanned
        )
        self.gate = (
            ProviderApprovalGate(self.mission_control, self.permissions)
            if with_approvals
            else None
        )
        self.service = AiCapabilityService(
            broker=self.broker,
            providers=self.providers,
            ledger=self.ledger,
            approvals=self.gate,
            strong_reasoning_min_quality=strong_floor,
            task_ids=lambda: "generated-task",
        )

    # ---- convenience ---------------------------------------------------

    def decide(self, **kwargs: Any):
        from master_agent.plugins.model_router import SelectionRequest

        kwargs.setdefault("task_id", "t1")
        return self.service.decide(SelectionRequest(**kwargs))

    def select(self, **kwargs: Any):
        from master_agent.plugins.model_router import SelectionRequest

        kwargs.setdefault("task_id", "t1")
        return self.service.select(SelectionRequest(**kwargs))

    def approve_everything(self, founder: str = "founder") -> int:
        pending = list(self.mission_control.approvals.open())
        for approval in pending:
            self.mission_control.approve(approval.approval_id, founder)
        return len(pending)

    def reject_everything(self, founder: str = "founder") -> int:
        pending = list(self.mission_control.approvals.open())
        for approval in pending:
            self.mission_control.reject(approval.approval_id, founder)
        return len(pending)


class StepClock:
    """A monotonic clock that advances a fixed amount every time it is
    read, so a measured latency is a fact about the test rather than about
    the machine it ran on."""

    def __init__(self, step_seconds: float = 0.25) -> None:
        self.step = step_seconds
        self.now = 0.0

    def __call__(self) -> float:
        value = self.now
        self.now += self.step
        return value


class Sleeps:
    """Records what was slept for instead of sleeping. A retry test that
    actually waits is a retry test nobody runs."""

    def __init__(self) -> None:
        self.calls: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


def ollama_body(
    text: str = "hello",
    model: str = "test-model",
    prompt_tokens: int | None = 11,
    completion_tokens: int | None = 3,
    done_reason: str = "stop",
    **extra: Any,
) -> str:
    """One `/api/generate` body, shaped exactly as a real daemon sends it
    (checked against Ollama 0.32 on the founder's machine)."""
    payload: dict[str, Any] = {
        "model": model,
        "created_at": "2026-07-30T09:00:00Z",
        "response": text,
        "done": True,
        "done_reason": done_reason,
    }
    if prompt_tokens is not None:
        payload["prompt_eval_count"] = prompt_tokens
    if completion_tokens is not None:
        payload["eval_count"] = completion_tokens
    payload.update(extra)
    return json.dumps(payload)


def tags_body(*models: str) -> str:
    return json.dumps({"models": [{"name": name} for name in models]})


class FakeTransport:
    """Scripted HTTP, and a record of what was asked of it.

    A single scripted response repeats forever; a list is consumed one per
    call, which is what makes a retry observable. An `Exception` in the
    script is raised rather than returned, so transport failures are
    exercised through the same door the real one uses.
    """

    def __init__(
        self,
        *responses: Any,
        tags: Any = None,
        stream: Any = None,
        on_chunk: Any = None,
    ) -> None:
        self._responses = list(responses) or [HttpResponse(200, ollama_body())]
        self._tags = tags if tags is not None else HttpResponse(200, tags_body())
        self.posts: list[tuple[str, dict[str, Any], float]] = []
        self.gets: list[tuple[str, float]] = []
        # MB038. A scripted stream: a list of NDJSON lines, or an
        # Exception to raise instead. `on_chunk(index)` runs *before* each
        # line is yielded, which is how a test advances a fake clock
        # between tokens and so exercises a stall without waiting for one.
        self._stream = stream
        self._on_chunk = on_chunk
        self.streamed: list[tuple[str, dict[str, Any], float]] = []

    def post_json(self, url: str, payload: dict[str, Any], timeout: float) -> HttpResponse:
        self.posts.append((url, payload, timeout))
        return self._next()

    def get(self, url: str, timeout: float) -> HttpResponse:
        self.gets.append((url, timeout))
        if isinstance(self._tags, Exception):
            raise self._tags
        return self._tags

    def stream_json(self, url: str, payload: dict[str, Any], timeout: float):
        """Scripted NDJSON. Falls back to replaying the next non-streaming
        response as a single line, so a fake built for MB033 still works
        against a caller that streams."""
        self.streamed.append((url, payload, timeout))
        script = self._stream
        if script is None:
            script = [self._next().body]
        if isinstance(script, Exception):
            raise script
        for index, line in enumerate(script):
            if self._on_chunk is not None:
                self._on_chunk(index)
            if isinstance(line, Exception):
                raise line
            yield line

    def _next(self) -> HttpResponse:
        item = self._responses.pop(0) if len(self._responses) > 1 else self._responses[0]
        if isinstance(item, Exception):
            raise item
        return item


def ollama(
    *responses: Any,
    model: str = "test-model",
    tags: Any = None,
    timeout_seconds: float = 30.0,
    step_seconds: float = 0.25,
    stream: Any = None,
    on_chunk: Any = None,
    **kwargs: Any,
) -> OllamaProvider:
    """An `OllamaProvider` over a scripted transport with a deterministic
    clock.

    MB038 removed `max_attempts` and `sleep`: this adapter no longer
    retries anything, so there is nothing to configure and nothing to
    sleep between.
    """
    return OllamaProvider(
        model=model,
        transport=FakeTransport(*responses, tags=tags, stream=stream, on_chunk=on_chunk),
        clock=StepClock(step_seconds),
        timeout_seconds=timeout_seconds,
        **kwargs,
    )


class RecordingProvider(ModelProvider):
    """A model provider that records rather than generates.

    Exists because no shipped provider actually generates text — both are
    documented stubs — and the property under test is *that nothing reaches
    a provider before the Broker and the founder have both answered*, which
    needs a provider that can prove it was not called.
    """

    def __init__(self, provider_id: str, reply: str = "generated") -> None:
        self._id = provider_id
        self._reply = reply
        self.calls: list[tuple[str, dict[str, Any] | None]] = []

    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            name=self._id,
            version="1.0.0",
            capabilities=[
                CapabilityManifest(
                    name=self.CAPABILITY_NAME,
                    description="test provider",
                    risk_tier=RiskTier.READ_ONLY,
                )
            ],
        )

    def generate(
        self, prompt: str, context: dict[str, Any] | None = None, **opts: Any
    ) -> str:
        self.calls.append((prompt, context))
        return self._reply
