"""Corrected Fallback Ladder — deterministic tests (Section 12's matrix,
Section 13's two failure-proof isolation tests).

Every test here drives the **real** `CapabilityBroker`, `AiCapabilityService`,
`ProviderSource`, `PromptExecutor`, and `TieredPromptRunner` — only the
leaf-level `ModelProvider.complete()` calls are faked, via `FakeProvider`
below. This is deliberate: a hand-rolled fake executor would only prove
this test file's own idea of the tiering logic, not that the real Broker
ranking/exclusion machinery actually enforces it. No real application is
launched, no real network call is made, and no real Gemini quota is
touched — fully deterministic, per Section 6's own "dependency injection/
mocks for deterministic tests" allowance.

Live, real-machine evidence (a genuine installed desktop AI application,
a real Gemini-success isolation run, real Chrome if reached) lives in
`docs/audits/REASONING_FALLBACK_LADDER_1.md`, not here.
"""
from __future__ import annotations

import pytest

from master_agent.ai_infrastructure.catalog import CLOUD, DESKTOP, REASONING, ProviderSpec
from master_agent.ai_infrastructure.execution import PromptExecutor
from master_agent.ai_infrastructure.ledger import DecisionLedger
from master_agent.ai_infrastructure.profiles import ProviderSource
from master_agent.ai_infrastructure.service import AiCapabilityService
from master_agent.ai_infrastructure.tiered_runner import TieredPromptRunner
from master_agent.broker.broker import CapabilityBroker
from master_agent.broker.policy import get_policy
from master_agent.plugins.base import CapabilityManifest, ModelProvider, PluginManifest, RiskTier
from master_agent.plugins.model_router import SelectionRequest
from master_agent.plugins.registry import PluginRegistry
from master_agent.providers.response import SUCCEEDED, UNAVAILABLE, Availability, ProviderResponse, ProviderResult, failure


class FakeProvider(ModelProvider):
    """A `ModelProvider` whose `complete()` returns whatever the test
    tells it to, recording every call — the seam that lets these tests
    drive the real Broker/PromptExecutor/TieredPromptRunner without a
    real application or network call anywhere."""

    CAPABILITY_NAME = "generate_text"

    def __init__(self, provider_id: str, outcomes: list) -> None:
        self._provider_id = provider_id
        self._outcomes = list(outcomes)  # popped left-to-right, one per complete() call
        self.complete_calls = 0

    @property
    def provider_id(self) -> str:
        return self._provider_id

    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            name=self._provider_id, version="1.0.0",
            capabilities=[CapabilityManifest(name=self.CAPABILITY_NAME, description="fake", risk_tier=RiskTier.READ_ONLY)],
        )

    def availability(self) -> Availability:
        return Availability(self._provider_id, True)

    def generate(self, prompt, context=None, **opts):
        result = self.complete(prompt, context=context)
        if not result.ok:
            raise RuntimeError(result.error)
        return result.text

    def complete(self, prompt, context=None, options=None, budget=None, cancellation=None) -> ProviderResult:
        self.complete_calls += 1
        if self._outcomes:
            return self._outcomes.pop(0)
        return failure(self._provider_id, UNAVAILABLE, "no more scripted outcomes")


def _success(provider_id: str, text: str = "a real answer") -> ProviderResult:
    return ProviderResult(
        provider_id=provider_id, outcome=SUCCEEDED,
        response=ProviderResponse(text=text, model=provider_id),
    )


def _failure(provider_id: str, reason: str = "scripted failure") -> ProviderResult:
    return failure(provider_id, UNAVAILABLE, reason)


def _spec(provider_id: str, locality: str) -> ProviderSpec:
    return ProviderSpec(
        provider_id=provider_id, label=provider_id, capabilities=frozenset({REASONING}),
        locality=locality, privacy="private" if locality != CLOUD else "third_party",
        declared_quality=0.8, cost_per_call=0.0,
    )


def _build_system(gemini=None, desktops=(), browser=None, unrelated_spec_ids=()):
    """One real Broker/AiCapabilityService/PromptExecutor/TieredPromptRunner,
    wired with whichever fake providers a test supplies — mirrors
    `kalpavriksha_desktop.py::_build_mission_pipeline()`'s own shape,
    minus everything not relevant to reasoning-provider selection.

    `unrelated_spec_ids` mirrors the real composition root's own
    `specs=PROVIDER_CATALOG + (BROWSER_FREE_AI_SPEC,)`: extra provider
    specs the Broker can see (Ollama, LM Studio, ...) that this ladder
    never registers a real plugin for and never puts in any of its three
    tiers — the exact shape of the real, live bug this file's own
    `test_unrelated_catalog_providers_never_leak_into_any_tier` guards.
    """
    specs = []
    registry = PluginRegistry()
    gemini_ids = frozenset()
    desktop_ids = frozenset()
    browser_ids = frozenset()

    if gemini is not None:
        specs.append(_spec(gemini.provider_id, CLOUD))
        registry.register(gemini)
        gemini_ids = frozenset({gemini.provider_id})

    if desktops:
        specs.extend(_spec(d.provider_id, DESKTOP) for d in desktops)
        for d in desktops:
            registry.register(d)
        desktop_ids = frozenset(d.provider_id for d in desktops)

    if browser is not None:
        specs.append(_spec(browser.provider_id, CLOUD))
        registry.register(browser)
        browser_ids = frozenset({browser.provider_id})

    for unrelated_id in unrelated_spec_ids:
        # LOCAL locality + zero cost: the exact shape that let
        # "ollama.local" outrank every tier's own candidates under the
        # real `prefer_free` policy in the live bug this guards against.
        specs.append(_spec(unrelated_id, "local"))

    providers_source = ProviderSource(inventory_provider=None, specs=tuple(specs),
                                       enabled_cloud_providers=tuple(s.provider_id for s in specs))
    ledger = DecisionLedger(store=None)
    broker = CapabilityBroker(policy=get_policy("prefer_free"), sink=ledger.record)
    intelligence = AiCapabilityService(broker=broker, providers=providers_source, ledger=ledger, approvals=None)
    executor = PromptExecutor(service=intelligence, providers=registry, ledger=ledger)
    all_known = frozenset(s.provider_id for s in specs)
    runner = TieredPromptRunner(executor, gemini_ids, desktop_ids, browser_ids, all_known_provider_ids=all_known)
    return runner


def _request() -> SelectionRequest:
    return SelectionRequest(capability=REASONING)


# ═══════════════════════ Section 12 test matrix ═══════════════════════


def test_a_desktop_succeeds_and_the_cloud_is_never_asked():
    """ADR-0017 Decision 3 walks six rungs cheapest-first: local, desktop
    app, free cloud, free aggregator, existing subscription, paid API. A
    desktop application already running on the founder's machine is
    cheaper than a cloud call, so it is tried first and the cloud is never
    reached.

    This test previously asserted the opposite -- Gemini first, desktop
    untouched -- from when the runner read `gemini, desktop, browser,
    local`. Commit 1743a53 reconciled that to the ADR and said so: *"A
    frozen decision is not mine to re-derive because a local model takes
    fifteen minutes."* The invariant being protected is unchanged and is
    the whole point: **a tier that succeeds must never cause a lower one
    to be touched.** Only which tier is higher has moved.
    """
    gemini = FakeProvider("gemini.api", [_success("gemini.api")])
    desktop = FakeProvider("claude-desktop", [_success("claude-desktop")])
    browser = FakeProvider("browser.free-ai", [_success("browser.free-ai")])
    runner = _build_system(gemini=gemini, desktops=[desktop], browser=browser)

    outcome = runner.run("hello", _request())

    assert outcome.ok and outcome.provider_id == "claude-desktop"
    assert gemini.complete_calls == 0, "the cloud must not be paid for when a desktop app answers"
    assert browser.complete_calls == 0, "browser tier must never be touched when desktop succeeds"


def test_b_desktop_answers_before_the_cloud_is_reached_at_all():
    """The same rung order from the other side: with the desktop tier
    healthy, a failing cloud provider is never even consulted, because
    the ladder never gets that far down.

    This asserted `gemini.complete_calls == 1` when the cloud sat above
    desktop. Under ADR-0017's order that call does not happen, and not
    making it is the saving the ladder exists for.
    """
    gemini = FakeProvider("gemini.api", [_failure("gemini.api")])
    claude = FakeProvider("claude-desktop", [_success("claude-desktop")])
    browser = FakeProvider("browser.free-ai", [_success("browser.free-ai")])
    runner = _build_system(gemini=gemini, desktops=[claude], browser=browser)

    outcome = runner.run("hello", _request())

    assert outcome.ok and outcome.provider_id == "claude-desktop"
    assert gemini.complete_calls == 0, "the ladder never descended to the cloud"
    assert browser.complete_calls == 0, "browser tier must not be touched once desktop succeeds"


def test_c_gemini_fails_chatgpt_desktop_available_chrome_not_touched():
    gemini = FakeProvider("gemini.api", [_failure("gemini.api")])
    chatgpt = FakeProvider("chatgpt-desktop", [_success("chatgpt-desktop")])
    browser = FakeProvider("browser.free-ai", [_success("browser.free-ai")])
    runner = _build_system(gemini=gemini, desktops=[chatgpt], browser=browser)

    outcome = runner.run("hello", _request())

    assert outcome.ok and outcome.provider_id == "chatgpt-desktop"
    assert browser.complete_calls == 0


def test_d_gemini_fails_multiple_desktop_providers_only_one_touched():
    gemini = FakeProvider("gemini.api", [_failure("gemini.api")])
    claude = FakeProvider("claude-desktop", [_success("claude-desktop")])
    chatgpt = FakeProvider("chatgpt-desktop", [_success("chatgpt-desktop")])
    browser = FakeProvider("browser.free-ai", [_success("browser.free-ai")])
    runner = _build_system(gemini=gemini, desktops=[claude, chatgpt], browser=browser)

    outcome = runner.run("hello", _request())

    assert outcome.ok
    assert outcome.provider_id in {"claude-desktop", "chatgpt-desktop"}
    touched = int(claude.complete_calls > 0) + int(chatgpt.complete_calls > 0)
    assert touched == 1, "exactly one desktop provider should be tried when the first ranked one succeeds"
    assert browser.complete_calls == 0


def test_d_within_tier_fallback_to_next_desktop_provider_on_failure():
    # Equal declared quality/cost/locality ties on `provider_id`
    # lexicographically (`broker/policy.py`'s own documented rule) — so
    # with identical `_spec()` profiles, "chatgpt-desktop" ranks ahead of
    # "claude-desktop" alphabetically and is tried first. Scripted to
    # fail there, so the within-tier fallback to the second-ranked
    # candidate is what this test actually exercises.
    gemini = FakeProvider("gemini.api", [_failure("gemini.api")])
    chatgpt = FakeProvider("chatgpt-desktop", [_failure("chatgpt-desktop")])
    claude = FakeProvider("claude-desktop", [_success("claude-desktop")])
    browser = FakeProvider("browser.free-ai", [_success("browser.free-ai")])
    runner = _build_system(gemini=gemini, desktops=[chatgpt, claude], browser=browser)

    outcome = runner.run("hello", _request())

    assert outcome.ok and outcome.provider_id == "claude-desktop"
    assert chatgpt.complete_calls == 1
    assert claude.complete_calls == 1
    assert browser.complete_calls == 0, "browser must not be touched once the second desktop provider succeeds"


def test_e_gemini_and_all_desktop_fail_browser_reached_and_succeeds():
    gemini = FakeProvider("gemini.api", [_failure("gemini.api")])
    claude = FakeProvider("claude-desktop", [_failure("claude-desktop")])
    chatgpt = FakeProvider("chatgpt-desktop", [_failure("chatgpt-desktop")])
    browser = FakeProvider("browser.free-ai", [_success("browser.free-ai")])
    runner = _build_system(gemini=gemini, desktops=[claude, chatgpt], browser=browser)

    outcome = runner.run("hello", _request())

    assert outcome.ok and outcome.provider_id == "browser.free-ai"
    assert claude.complete_calls == 1 and chatgpt.complete_calls == 1
    assert browser.complete_calls == 1


def test_f_everything_fails_clean_founder_facing_failure_no_fabrication():
    gemini = FakeProvider("gemini.api", [_failure("gemini.api")])
    claude = FakeProvider("claude-desktop", [_failure("claude-desktop")])
    browser = FakeProvider("browser.free-ai", [_failure("browser.free-ai")])
    runner = _build_system(gemini=gemini, desktops=[claude], browser=browser)

    outcome = runner.run("hello", _request())

    assert not outcome.ok
    assert outcome.text == "", "a failed outcome must never carry fabricated response text"


def test_no_desktop_providers_registered_falls_through_to_browser():
    """Section 3/7: an empty desktop tier (nothing installed) must not
    block reaching the browser tier."""
    gemini = FakeProvider("gemini.api", [_failure("gemini.api")])
    browser = FakeProvider("browser.free-ai", [_success("browser.free-ai")])
    runner = _build_system(gemini=gemini, desktops=[], browser=browser)

    outcome = runner.run("hello", _request())

    assert outcome.ok and outcome.provider_id == "browser.free-ai"


def test_unrelated_catalog_providers_never_leak_into_any_tier():
    """Real, live bug found running the actual production pipeline: the
    real `PROVIDER_CATALOG` this ladder's `ProviderSource` is built from
    also contains Ollama/LM Studio/OpenAI/OpenRouter — none of them part
    of any of the three named tiers. Without excluding them explicitly
    (not just "the other two tiers"), one of them — Ollama, specifically,
    a real and repeatedly-stated "never enable/query" constraint in this
    codebase — could win a scoped tier's Broker call purely by ranking,
    regardless of which tier was supposedly being attempted. Confirmed
    live: with the bug present, a real Gemini-auth-failure run selected
    `ollama.local` for the "desktop" tier attempt.
    """
    gemini = FakeProvider("gemini.api", [_failure("gemini.api")])
    claude = FakeProvider("claude-desktop", [_success("claude-desktop")])
    browser = FakeProvider("browser.free-ai", [_success("browser.free-ai")])
    runner = _build_system(
        gemini=gemini, desktops=[claude], browser=browser,
        unrelated_spec_ids=("ollama.local", "lm-studio.local"),
    )

    outcome = runner.run("hello", _request())

    assert outcome.ok and outcome.provider_id == "claude-desktop"
    for attempt in runner.last_attempts:
        assert "ollama.local" not in attempt.provider_ids_considered
        assert "lm-studio.local" not in attempt.provider_ids_considered


# ═══════════════════════ Section 13 — the two failure-proof tests ═══════════════════════


def test_CRITICAL_a_successful_tier_must_never_touch_any_lower_tier():
    """The failure mode this file exists to prevent, stated in ADR-0017's
    own rung order: something succeeds, and the system nevertheless calls
    a cheaper-than-it rung anyway. Must fail loudly if that regresses.

    Named for the property rather than for Gemini, because naming a
    provider is what tied the previous version to a rung order the ADR
    does not have. The property survives any reordering; the name now
    does too.
    """
    gemini = FakeProvider("gemini.api", [_success("gemini.api")])
    desktop = FakeProvider("claude-desktop", [_success("claude-desktop")])
    browser = FakeProvider("browser.free-ai", [_success("browser.free-ai")])
    runner = _build_system(gemini=gemini, desktops=[desktop], browser=browser)

    outcome = runner.run("hello", _request())

    # Desktop is the highest configured rung here, so it answers and
    # nothing below it is consulted.
    assert outcome.provider_id == "claude-desktop"
    assert gemini.complete_calls == 0
    assert browser.complete_calls == 0


def test_CRITICAL_desktop_success_must_never_open_the_browser():
    """The inverse: Gemini fails, a desktop provider succeeds, but the
    browser tier is nevertheless opened anyway. Must also fail loudly if
    that regresses."""
    gemini = FakeProvider("gemini.api", [_failure("gemini.api")])
    desktop = FakeProvider("claude-desktop", [_success("claude-desktop")])
    browser = FakeProvider("browser.free-ai", [_success("browser.free-ai")])
    runner = _build_system(gemini=gemini, desktops=[desktop], browser=browser)

    outcome = runner.run("hello", _request())

    assert outcome.provider_id == "claude-desktop"
    assert browser.complete_calls == 0


# ═══════════════════════ Section 9 — no boot/recursion regressions ═══════════════════════


def test_tiered_runner_construction_touches_nothing():
    """Constructing the runner (mirroring what happens at boot) must not
    call any provider's complete()."""
    gemini = FakeProvider("gemini.api", [_success("gemini.api")])
    desktop = FakeProvider("claude-desktop", [_success("claude-desktop")])
    browser = FakeProvider("browser.free-ai", [_success("browser.free-ai")])
    _build_system(gemini=gemini, desktops=[desktop], browser=browser)

    assert gemini.complete_calls == 0
    assert desktop.complete_calls == 0
    assert browser.complete_calls == 0


def test_worst_case_every_tier_absent_or_failing_does_not_prevent_boot():
    """Boot safety, the mission's own explicit worst case: 'Gemini
    unavailable, desktop app missing, desktop session creation fails,
    browser provider unavailable — cannot prevent Kalpavriksha from
    booting.' Construction must succeed (no exception, no hang) even when
    every single tier is empty or guaranteed to fail, and a subsequent
    `run()` call must return a clean, bounded failure rather than raise or
    block."""
    gemini = FakeProvider("gemini.api", [_failure("gemini.api", "genuinely unavailable")])
    desktop = FakeProvider("claude-desktop", [_unsafe("claude-desktop", "desktop session creation failed")])
    browser = FakeProvider("browser.free-ai", [_failure("browser.free-ai", "browser provider unavailable")])

    # Construction itself must not raise.
    runner = _build_system(gemini=gemini, desktops=[desktop], browser=browser)

    # And a real run(), with every tier guaranteed to fail, must return
    # honestly rather than hang or raise.
    outcome = runner.run("hello", _request())

    assert not outcome.ok
    assert outcome.text == ""
    assert gemini.complete_calls == 1
    assert desktop.complete_calls == 1
    assert browser.complete_calls == 1


def test_construction_with_every_tier_completely_empty_does_not_raise():
    """The absolute minimum boot scenario: no Gemini registered, no
    desktop providers discovered, no browser provider registered — the
    state of a machine before any provider has ever been configured.
    Construction must still succeed, and `run()` must return rather than
    raise or hang (no tier was even attempted, so there is honestly
    nothing to report — `None`, not a fabricated failure object)."""
    runner = _build_system(gemini=None, desktops=[], browser=None)

    outcome = runner.run("hello", _request())  # must not raise

    assert outcome is None
    assert all(not attempt.attempted for attempt in runner.last_attempts)


def test_tiered_runner_does_not_reference_the_planner_or_mission_service():
    """Section 9: 'no provider execution path calls the Planner
    recursively' — asserted structurally, the same AST-guard discipline
    this codebase already uses elsewhere, over the actual source of the
    three new modules."""
    import ast
    import inspect
    from master_agent.ai_infrastructure import tiered_runner
    from master_agent.providers import desktop_app, browser_free_ai

    forbidden = {"Planner", "MissionService", "mission_service"}
    for module in (tiered_runner, desktop_app, browser_free_ai):
        source = inspect.getsource(module)
        tree = ast.parse(source)
        names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        names |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
        overlap = forbidden & names
        assert not overlap, f"{module.__name__} references {overlap} — a reasoning provider must never call back into the Planner"


# ═══════ Desktop reasoning-provider safety gate (session-isolation) ═══════
#
# Real, live-found risk: a desktop AI application's discoverable
# window/composer can belong to an existing, active conversation (found
# live against Claude Desktop specifically, hosting an active Claude
# Code/project session) rather than a fresh surface safe for an
# autonomous one-shot prompt. `DesktopAppReasoningProvider` now refuses
# such a target before ever writing to it (unit-level proof lives in
# `tests/test_desktop_app_provider.py`); these tests prove the *tier*
# correctly treats an "unsafe" result the same as any other provider
# failure — exclude, try the next ranked candidate, and fall through to
# the browser tier if none remain — using the exact same, unmodified
# Broker/TieredPromptRunner exclusion machinery every other failure
# already goes through. No new selection logic was added for this.


def _unsafe(provider_id: str, reason: str = "target session could not be verified as isolated") -> ProviderResult:
    return failure(provider_id, UNAVAILABLE, f"AUTONOMOUS_REASONING_UNSAFE: {reason}")


def test_unsafe_desktop_provider_rejected_falls_through_to_next_safe_desktop_provider():
    gemini = FakeProvider("gemini.api", [_failure("gemini.api")])
    chatgpt = FakeProvider("chatgpt-desktop", [_unsafe("chatgpt-desktop")])
    claude = FakeProvider("claude-desktop", [_success("claude-desktop")])
    browser = FakeProvider("browser.free-ai", [_success("browser.free-ai")])
    runner = _build_system(gemini=gemini, desktops=[chatgpt, claude], browser=browser)

    outcome = runner.run("hello", _request())

    assert outcome.ok and outcome.provider_id == "claude-desktop"
    assert chatgpt.complete_calls == 1, "the unsafe provider must still be attempted once (fail closed, not silently skipped)"
    assert claude.complete_calls == 1
    assert browser.complete_calls == 0, "browser must not be touched once a safe desktop provider succeeds"


def test_gemini_fails_only_unsafe_desktop_providers_falls_through_to_browser():
    gemini = FakeProvider("gemini.api", [_failure("gemini.api")])
    chatgpt = FakeProvider("chatgpt-desktop", [_unsafe("chatgpt-desktop")])
    claude = FakeProvider("claude-desktop", [_unsafe("claude-desktop")])
    browser = FakeProvider("browser.free-ai", [_success("browser.free-ai")])
    runner = _build_system(gemini=gemini, desktops=[chatgpt, claude], browser=browser)

    outcome = runner.run("hello", _request())

    assert outcome.ok and outcome.provider_id == "browser.free-ai"
    assert chatgpt.complete_calls == 1 and claude.complete_calls == 1
    assert browser.complete_calls == 1


def test_no_safe_desktop_or_browser_provider_clean_failure_never_fabricated():
    gemini = FakeProvider("gemini.api", [_failure("gemini.api")])
    claude = FakeProvider("claude-desktop", [_unsafe("claude-desktop")])
    browser = FakeProvider("browser.free-ai", [_failure("browser.free-ai")])
    runner = _build_system(gemini=gemini, desktops=[claude], browser=browser)

    outcome = runner.run("hello", _request())

    assert not outcome.ok
    assert outcome.text == "", "a failed outcome must never carry fabricated response text"


def test_the_real_catalog_never_ranks_the_statically_unsafe_claude_desktop_entry():
    """Integration proof, using the REAL `PROVIDER_CATALOG` entry (not a
    synthetic `_spec()`) and the REAL `profiles.py::availability()`
    function: even a desktop application the machine genuinely reports as
    installed and healthy must never be ranked/selected by the Broker
    once its spec carries `autonomous_reasoning_unsafe_reason` — 'never
    open or interact with an unsafe desktop application merely because it
    is installed' proven at the selection layer, not merely at the
    provider's own `complete()`."""
    from master_agent.ai_infrastructure.catalog import PROVIDER_CATALOG
    from master_agent.ai_infrastructure.profiles import availability

    claude_spec = next(s for s in PROVIDER_CATALOG if s.provider_id == "claude-desktop")
    assert claude_spec.autonomous_reasoning_unsafe_reason is not None  # sanity: the fixture assumption holds

    class _InstalledHealthyApp:
        installed = True
        healthy = True
        version = "1.0"

    class _FakeInventory:
        def get(self, key):
            return _InstalledHealthyApp() if key == claude_spec.inventory_key else None

    available, detail = availability(claude_spec, _FakeInventory(), enabled=frozenset())

    assert available is False
    assert "AUTONOMOUS_REASONING_UNSAFE" in detail


# ═══════════ Founder Edition: the web rung, and quota is not the end ═══════════
#
# The web tier used to be constructed empty in `kalpavriksha_desktop.py`
# (`browser_provider_ids=frozenset()`), so an exhausted Gemini API quota
# could end a founder's request outright once the desktop tier was also
# unavailable. The provider existed and knew how to drive a real visible
# browser; only the wiring was missing.
#
# These prove the *ladder* behaviour deterministically, against fakes, so
# no real quota is spent and no browser opens. The live proof that the web
# provider really drives Chrome is a separate acceptance runner.


def test_a_dead_gemini_api_is_not_the_end_of_reasoning():
    """The whole point of filling the rung. Gemini fails finally, the
    desktop tier has nothing installed, and the request still succeeds —
    through the browser rung rather than through a 429 special case."""
    gemini = FakeProvider("gemini.api", [_failure("gemini.api")])
    browser = FakeProvider("browser.free-ai", [_success("browser.free-ai")])
    runner = _build_system(gemini=gemini, desktops=[], browser=browser)

    outcome = runner.run("hello", _request())

    assert outcome.ok
    assert outcome.provider_id == "browser.free-ai"
    assert gemini.complete_calls == 1, "the cheaper rung was still tried first"


def test_the_web_rung_is_last_not_a_shortcut():
    """Ordering, not opportunism. With a desktop application available the
    browser is never opened, because ADR-0017 walks desktop before the web
    aggregator — and because there is deliberately no `if status == 429`
    anywhere in this path."""
    gemini = FakeProvider("gemini.api", [_failure("gemini.api")])
    desktop = FakeProvider("claude-desktop", [_success("claude-desktop")])
    browser = FakeProvider("browser.free-ai", [_success("browser.free-ai")])
    runner = _build_system(gemini=gemini, desktops=[desktop], browser=browser)

    outcome = runner.run("hello", _request())

    assert outcome.provider_id == "claude-desktop"
    assert browser.complete_calls == 0, "the web rung was opened before it was needed"


def test_a_healthy_upper_rung_never_opens_a_browser():
    """The founder's machine must not sprout a Chrome window because
    something further down the ladder happened to be configured."""
    desktop = FakeProvider("claude-desktop", [_success("claude-desktop")])
    browser = FakeProvider("browser.free-ai", [_success("browser.free-ai")])
    runner = _build_system(gemini=None, desktops=[desktop], browser=browser)

    outcome = runner.run("hello", _request())

    assert outcome.ok and outcome.provider_id == "claude-desktop"
    assert browser.complete_calls == 0


def test_when_every_rung_fails_the_answer_is_a_truthful_failure():
    """No fabricated text, and no endless retry. Provider retry belongs to
    the provider; tier progression belongs to the runner; neither invents
    an answer when the ladder runs out."""
    gemini = FakeProvider("gemini.api", [_failure("gemini.api")])
    desktop = FakeProvider("claude-desktop", [_failure("claude-desktop")])
    browser = FakeProvider("browser.free-ai", [_failure("browser.free-ai")])
    runner = _build_system(gemini=gemini, desktops=[desktop], browser=browser)

    outcome = runner.run("hello", _request())

    assert not outcome.ok
    assert outcome.text == "", "a failed ladder must never carry fabricated text"
    assert gemini.complete_calls == 1
    assert desktop.complete_calls == 1
    assert browser.complete_calls == 1


def test_founder_edition_web_rung_is_gemini_only():
    """Enabling the provider must not quietly re-enable Duck.ai. The site
    list is configuration on the one existing provider, not a second
    provider class."""
    from master_agent.providers.browser_free_ai import (
        CANDIDATE_SITES,
        FOUNDER_EDITION_SITES,
        BrowserFreeAiReasoningProvider,
    )

    labels = [s.label for s in FOUNDER_EDITION_SITES]
    assert labels == ["Gemini (web)"]
    assert not any("duck" in s.label.lower() for s in FOUNDER_EDITION_SITES)

    configured = BrowserFreeAiReasoningProvider(sites=FOUNDER_EDITION_SITES)
    assert [s.label for s in configured._sites] == ["Gemini (web)"]

    # The generic provider is untouched: another deployment still gets both.
    assert any("duck" in s.label.lower() for s in CANDIDATE_SITES)
    assert [s.label for s in BrowserFreeAiReasoningProvider()._sites] == [
        s.label for s in CANDIDATE_SITES
    ]


# ═════════ An unverified answer is not a reason to stop the ladder ═════════
#
# This file's own module docstring states the rule: "stop as soon as a
# VERIFIED reasoning result is obtained." The loop used to stop as soon as
# an `ok` one was, and those are not the same fact.
#
# Found live, not theorised. ChatGPT Desktop returned a mid-stream
# fragment -- once literally `{"steps"`, once a bare `-` -- carrying
# ok=True and verified=False. The Planner then refused the founder's whole
# objective ("the reply was not a plan document") while three untried
# rungs sat below it.


def _expect_contains(text: str):
    from master_agent.ai_infrastructure.text_verifier import expect

    return expect(contains_all=[text])


def test_an_ok_but_unverified_answer_does_not_end_the_ladder():
    """The live defect, as a test. The desktop rung answers, its answer
    fails the expectation it was given, and the ladder keeps walking
    instead of handing the founder something unusable."""
    desktop = FakeProvider("claude-desktop", [_success("claude-desktop", text="{\"steps\"")])
    browser = FakeProvider("browser.free-ai", [_success("browser.free-ai", text="COMPLETE ANSWER")])
    runner = _build_system(gemini=None, desktops=[desktop], browser=browser)

    outcome = runner.run("hello", _request(), expected=_expect_contains("COMPLETE ANSWER"))

    assert outcome.ok
    assert outcome.provider_id == "browser.free-ai", (
        "a truncated answer from an upper rung ended the ladder"
    )
    assert desktop.complete_calls == 1, "the upper rung was still tried first"


def test_a_verified_answer_stops_the_ladder_immediately():
    """The other half: when the answer does satisfy what was asked of it,
    nothing below is touched."""
    desktop = FakeProvider("claude-desktop", [_success("claude-desktop", text="COMPLETE ANSWER")])
    browser = FakeProvider("browser.free-ai", [_success("browser.free-ai", text="COMPLETE ANSWER")])
    runner = _build_system(gemini=None, desktops=[desktop], browser=browser)

    outcome = runner.run("hello", _request(), expected=_expect_contains("COMPLETE ANSWER"))

    assert outcome.provider_id == "claude-desktop"
    assert browser.complete_calls == 0


def test_a_caller_with_nothing_to_check_against_is_unaffected():
    """`PromptOutcome.evidence` is None exactly when no expectation was
    supplied, and `verified` is documented as False in that case. Without
    this discriminator every unchecked call would walk the whole ladder."""
    desktop = FakeProvider("claude-desktop", [_success("claude-desktop", text="anything")])
    browser = FakeProvider("browser.free-ai", [_success("browser.free-ai")])
    runner = _build_system(gemini=None, desktops=[desktop], browser=browser)

    outcome = runner.run("hello", _request())  # no `expected=`

    assert outcome.provider_id == "claude-desktop"
    assert browser.complete_calls == 0, "an unchecked call fell through the ladder"


def test_when_no_rung_verifies_the_last_answer_is_still_returned_honestly():
    """Walking the whole ladder without satisfying the expectation is a
    failure to report, not a reason to fabricate one."""
    desktop = FakeProvider("claude-desktop", [_success("claude-desktop", text="fragment")])
    browser = FakeProvider("browser.free-ai", [_success("browser.free-ai", text="also fragment")])
    runner = _build_system(gemini=None, desktops=[desktop], browser=browser)

    outcome = runner.run("hello", _request(), expected=_expect_contains("NEVER APPEARS"))

    assert desktop.complete_calls == 1 and browser.complete_calls == 1
    assert not getattr(outcome, "verified", False)
