"""Build 2 — Gemini through the existing Broker and Planner, end to end,
against a scripted transport (no real network in the automated suite;
the real-API proof is a founder-facing run recorded in
`docs/audits/P0_GEMINI_REASONING_PROVIDER.md`, the same split
`test_ollama_provider.py`'s own docstring already establishes).
"""
from __future__ import annotations

import json

from master_agent.ai_infrastructure.catalog import REASONING
from master_agent.ai_infrastructure.execution import PromptExecutor
from master_agent.ai_infrastructure.ledger import DecisionLedger
from master_agent.ai_infrastructure.profiles import ProviderSource
from master_agent.ai_infrastructure.service import AiCapabilityService
from master_agent.broker.broker import CapabilityBroker
from master_agent.broker.policy import get_policy
from master_agent.broker.profiles import TaskProfile, UNRESTRICTED
from master_agent.planner.catalogue import CapabilityOption
from master_agent.planner.plan import Intent
from master_agent.planner.planner import Planner
from master_agent.plugins.registry import PluginRegistry
from master_agent.providers.gemini import GEMINI_PROVIDER_ID, GeminiProvider
from master_agent.providers.transport import HttpResponse

from tests.test_gemini_provider import FakeTransport, _ok


# ---- Broker: discovery / capability / eligibility -------------------------


def _gemini_source(enabled: bool) -> ProviderSource:
    return ProviderSource(
        inventory_provider=lambda: None,  # gemini.api needs no machine scan
        enabled_cloud_providers=("gemini.api",) if enabled else (),
    )


def test_gemini_is_discovered_in_the_provider_catalog():
    from master_agent.ai_infrastructure.catalog import BY_PROVIDER_ID

    assert "gemini.api" in BY_PROVIDER_ID


def test_gemini_declares_reasoning():
    profiles = _gemini_source(enabled=True).profiles()
    gemini = next(p for p in profiles if p.provider_id == "gemini.api")

    assert gemini.serves(REASONING)


def test_gemini_is_unavailable_until_the_founder_enables_it():
    """Absence from `enabled_cloud_providers` is a fact, not an oversight
    to work around — the same rule `BrokerConfig`'s own docstring states."""
    profiles = _gemini_source(enabled=False).profiles()
    gemini = next(p for p in profiles if p.provider_id == "gemini.api")

    assert gemini.available is False


def test_gemini_is_eligible_once_the_founder_enables_it():
    profiles = _gemini_source(enabled=True).profiles()
    gemini = next(p for p in profiles if p.provider_id == "gemini.api")

    assert gemini.available is True


def test_broker_selects_gemini_when_ollama_is_excluded():
    """Reuses the exact existing mechanism proven for claude-desktop:
    `TaskProfile.exclude_providers`. No new selection path."""
    source = _gemini_source(enabled=True)
    broker = CapabilityBroker(policy=get_policy("prefer_free"))
    task = TaskProfile(
        capability=REASONING,
        task_id="gemini-broker-test",
        sensitivity=UNRESTRICTED,
        exclude_providers=frozenset({"ollama.local"}),
    )

    decision = broker.select(task, list(source.profiles()))

    assert decision.outcome == "selected"
    assert decision.winner == "gemini.api"


def test_ollama_exclusion_is_respected_even_when_gemini_is_not_configured():
    """Excluding Ollama must never silently fall through to Ollama anyway
    — the Broker's own refusal, not a Gemini-specific rule."""
    source = _gemini_source(enabled=False)
    broker = CapabilityBroker(policy=get_policy("prefer_free"))
    task = TaskProfile(
        capability=REASONING,
        task_id="gemini-broker-test-2",
        sensitivity=UNRESTRICTED,
        exclude_providers=frozenset({"ollama.local"}),
    )

    decision = broker.select(task, list(source.profiles()))

    assert decision.winner != "ollama.local"


# ---- Planner: end to end, scripted transport -------------------------------


def _wired_planner(transport) -> Planner:
    source = _gemini_source(enabled=True)
    ledger = DecisionLedger(store=None)  # in-memory only
    broker = CapabilityBroker(policy=get_policy("prefer_free"), sink=ledger.record)
    intelligence = AiCapabilityService(
        broker=broker, providers=source, ledger=ledger, approvals=None
    )

    registry = PluginRegistry()
    registry.register(GeminiProvider(api_key="test-key", transport=transport))

    executor = PromptExecutor(service=intelligence, providers=registry, ledger=ledger)
    catalogue = (
        CapabilityOption(
            name="Browser.Navigate",
            description="Open a URL in the browser and confirm it loaded.",
            risk_tier="REVERSIBLE_WRITE",
            required_args=frozenset({"url"}),
        ),
    )
    return Planner(runner=executor, catalogue=catalogue)


_PLAN_JSON = json.dumps(
    {
        "steps": [
            {
                "id": "step-1",
                "capability": "Browser.Navigate",
                "payload": {"url": "https://example.com/"},
                "depends_on": [],
                "success": {
                    "description": "the page loaded and its title contains 'Example'",
                    "must_contain": [],
                    "must_exclude": [],
                    "must_be_json": False,
                    "must_have_fields": [],
                    "min_words": 0,
                },
            }
        ]
    }
)


def test_planner_produces_a_plan_when_gemini_answers_with_a_valid_plan_document():
    transport = FakeTransport(_ok(text=_PLAN_JSON))
    planner = _wired_planner(transport)
    intent = Intent(
        goal=(
            "Plan the following computer task without executing it: open "
            "Chrome, navigate to https://example.com/, verify the page "
            "loaded, and report the result."
        )
    )

    outcome = planner.plan(intent, task_id="gemini-planner-test")

    assert outcome.provider_id == GEMINI_PROVIDER_ID
    assert outcome.plan is not None, (
        outcome.refusal.reason if outcome.refusal else "no refusal recorded"
    )
    assert outcome.plan.steps[0].capability == "Browser.Navigate"


def test_planner_refuses_cleanly_when_gemini_is_rate_limited():
    transport = FakeTransport(
        HttpResponse(429, json.dumps({"error": {"message": "quota exceeded"}}))
    )
    planner = _wired_planner(transport)
    intent = Intent(goal="Plan something harmless.")

    outcome = planner.plan(intent, task_id="gemini-planner-test-2")

    assert outcome.plan is None
    assert outcome.refusal is not None
    assert "quota exceeded" in outcome.refusal.reason
