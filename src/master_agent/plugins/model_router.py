"""Model Router — the Brain's single door to reasoning (ARCHITECTURE.md §5).

**Mission Brief 032 removed this module's opinion about providers.** It used
to answer "which one?" itself:

    if not ctx.is_online:            return self._provider("hermes")
    if ctx.is_sensitive:             return self._provider("hermes")
    if ctx.requires_strong_reasoning: return self._provider("chatgpt")
    return self._provider(self._default_provider)   # "hermes"

Four branches, two product names, and a ladder no founder could audit —
ADR-0017's Consequences called it *"a documented contradiction"*, because
Constitution §14/§21 forbid product names in Brain logic. Constitution
Amendment 2 §3.3 resolved it: the Model Router keeps its interface and its
role, and asks the AI Capability Broker *which* provider instead of ranking
them itself.

So the four branches became four **facts about the request** —
`offline`, `sensitive`, `requires_strong_reasoning`, `preferred_provider` —
which the Broker turns into a decision with a record behind it. There is no
provider name left in this file, and `tests/test_broker_integration.py`
greps for seven of them to keep it that way.

## The port, and why it is defined here

`ProviderSelector` is a Protocol declared in this module and satisfied by
`ai_infrastructure.AiCapabilityService`. The dependency points inward:
the Brain declares what it needs and is handed an implementation, so
`plugins/` acquires no dependency on Mission Control, the Permission
System, or the Broker. That is the same outbound-port move MB025 made with
`CheckpointSink` and MB028.0 with `ApprovalGate`, for the same reason —
and it is why importing this module still costs nothing.

## Fail closed

A router with no selector **refuses everything** (Deliverable 10). Not
"falls back to the local one": a fallback is a provider decision, and a
component that makes one when its decision-maker is missing is the exact
hardcoding this brief deleted. Forgetting to wire the Broker yields a
system that does nothing and says why, never one that quietly does
something else.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from master_agent.plugins.base import ModelProvider
from master_agent.plugins.registry import PluginRegistry

#: The AI Capability a generation request asks for. `lowercase.dotted`, so
#: it is mechanically distinguishable from a Constitution Capability like
#: `Filesystem.CreateFolder` (ADR-0017 Decision 8). Not a product, not a
#: model, not an endpoint.
REASONING = "reasoning"

NO_SELECTOR = (
    "no AI Capability Broker is wired, so no provider can be selected; "
    "refusing rather than guessing"
)


@dataclass
class RoutingContext:
    """What the caller knows about the request. Every field is a fact
    about the *work*, never a preference about the provider — turning
    "this matters" into a product name was the bug MB032 fixed.

    `preferred_provider` survives as an explicit founder override, but it
    no longer bypasses anything: it is passed to the Broker as a
    constraint, so an override still produces a real decision with a real
    record, and an override naming something unavailable is refused with a
    reason instead of used.
    """

    is_online: bool = True
    is_sensitive: bool = False
    requires_strong_reasoning: bool = False
    preferred_provider: str | None = None
    #: Which AI Capability, for callers that need something other than
    #: reasoning (`coding`, `vision.ocr`, ...).
    capability: str = REASONING
    #: Optional hard constraints, forwarded verbatim to the Broker.
    max_cost: float | None = None
    max_latency_ms: float | None = None
    required_context_tokens: int | None = None
    #: Ties a selection to the work it was made for, so the stored
    #: `DecisionRecord` can be found again by task.
    task_id: str = ""
    objective_id: str | None = None
    requester: str = "model_router"


@dataclass(frozen=True)
class SelectionRequest:
    """What the router asks the Broker for. Frozen: a request describes
    what was asked, and a selector must not be able to edit the question
    on its way to answering it."""

    capability: str = REASONING
    offline: bool = False
    sensitive: bool = False
    requires_strong_reasoning: bool = False
    min_quality: float | None = None
    max_cost: float | None = None
    max_latency_ms: float | None = None
    required_context_tokens: int | None = None
    preferred_provider: str | None = None
    exclude_providers: frozenset[str] = field(default_factory=frozenset)
    task_id: str = ""
    objective_id: str | None = None
    requester: str = "model_router"

    @classmethod
    def from_context(cls, ctx: RoutingContext) -> SelectionRequest:
        """`is_online` becomes `offline` because the Broker asks about the
        constraint, not the happy path: a task that must not touch the
        network is a property of the task."""
        return cls(
            capability=ctx.capability or REASONING,
            offline=not ctx.is_online,
            sensitive=ctx.is_sensitive,
            requires_strong_reasoning=ctx.requires_strong_reasoning,
            max_cost=ctx.max_cost,
            max_latency_ms=ctx.max_latency_ms,
            required_context_tokens=ctx.required_context_tokens,
            preferred_provider=ctx.preferred_provider,
            task_id=ctx.task_id,
            objective_id=ctx.objective_id,
            requester=ctx.requester,
        )


@runtime_checkable
class ProviderSelector(Protocol):
    """The Broker, as the Brain needs it: one call, one answer.

    Returns something carrying a `provider_id`, and raises rather than
    returning a guess. Deliberately this small — the Brain must not be able
    to reach a policy, a profile list, or a ledger through it.
    """

    def select(self, request: SelectionRequest) -> Any: ...


class BrokerUnavailable(Exception):
    """No selector is wired. Fail closed — see the module docstring."""


class ProviderNotWired(Exception):
    """The Broker chose a provider this process has no plugin for.

    A wiring gap, not a decision problem, and reported as such: the
    decision was sound and is on the record, but nothing here can execute
    it. Silently picking a different provider would make the record a lie.
    """

    def __init__(self, provider_id: str, detail: str = "") -> None:
        self.provider_id = provider_id
        suffix = f" ({detail})" if detail else ""
        super().__init__(
            f"the Broker selected '{provider_id}', which is not registered as a "
            f"model provider in this process{suffix}"
        )


class ModelRouter:
    """Routes a generation call to whichever provider the Broker chose.

    `selector` is optional in the signature and mandatory in effect: a
    router without one refuses every request.
    """

    def __init__(self, registry: PluginRegistry, selector: Any = None) -> None:
        self._registry = registry
        self._selector = selector

    @property
    def selector(self) -> Any:
        return self._selector

    @property
    def has_broker(self) -> bool:
        return self._selector is not None

    def select(self, ctx: RoutingContext) -> Any:
        """The Broker's answer, before any plugin is resolved.

        Exposed separately because the decision is worth having even when
        nothing can execute it: a founder asking "what would you use?"
        should not need a registered provider plugin to find out.
        """
        if self._selector is None:
            raise BrokerUnavailable(NO_SELECTOR)
        return self._selector.select(SelectionRequest.from_context(ctx))

    def select_provider(self, ctx: RoutingContext) -> ModelProvider:
        """The Broker's answer, resolved to something that can run.

        Broker refusals (nothing available, waiting on the founder,
        rejected) propagate untouched: the caller must see *why*, and this
        class has nothing to add to a reason the Broker already wrote.
        """
        return self._provider(self.select(ctx).provider_id)

    def generate(
        self, prompt: str, ctx: RoutingContext, context: dict[str, Any] | None = None
    ) -> str:
        provider = self.select_provider(ctx)
        return provider.generate(prompt, context)

    def _provider(self, name: str) -> ModelProvider:
        """An explicit raise, not an `assert`: assertions vanish under
        `python -O`, and a silently-skipped type check on the object about
        to receive the founder's prompt is not a check."""
        try:
            plugin = self._registry.get(name)
        except KeyError as exc:
            raise ProviderNotWired(name, "no plugin registered under that id") from exc
        if not isinstance(plugin, ModelProvider):
            raise ProviderNotWired(name, "registered plugin is not a ModelProvider")
        return plugin
