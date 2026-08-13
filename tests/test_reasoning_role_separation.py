"""Role separation — coding agents (Claude Code, Codex, Cursor, Kimi coding
agents, or any future coding agent) must never become a Kalpavriksha
reasoning provider. Represented architecturally: a spec's own `role` field,
plus a closed identity set checked independently of it
(`ai_infrastructure/catalog.py::is_coding_agent()`), enforced at every
layer that could otherwise let one through — spec-level availability
(`profiles.py`), provider construction (`build_desktop_providers()`), and
`complete()`'s own entry point (defense in depth).
"""
from __future__ import annotations

import dataclasses

from master_agent.ai_infrastructure.catalog import (
    CODING_AGENT_ROLE,
    DESKTOP,
    KNOWN_CODING_AGENT_IDENTITIES,
    PROVIDER_CATALOG,
    REASONING,
    REASONING_ROLE,
    ProviderSpec,
    is_coding_agent,
)
from master_agent.ai_infrastructure.profiles import availability
from master_agent.desktop.actions import DesktopContext
from master_agent.providers import desktop_app as mod


def _spec(**overrides) -> ProviderSpec:
    base = dict(
        provider_id="some-desktop-app",
        label="Some Desktop App",
        capabilities=frozenset({REASONING}),
        locality=DESKTOP,
        privacy="third_party",
        declared_quality=0.8,
        cost_per_call=0.0,
    )
    base.update(overrides)
    return ProviderSpec(**base)


class TestIsCodingAgent:
    def test_a_spec_with_the_reasoning_role_is_not_a_coding_agent(self):
        spec = _spec(role=REASONING_ROLE)
        assert is_coding_agent(spec) is False

    def test_a_spec_declaring_the_coding_agent_role_is_caught(self):
        spec = _spec(provider_id="totally-unremarkable-id", role=CODING_AGENT_ROLE)
        assert is_coding_agent(spec) is True

    def test_a_known_identity_is_caught_even_without_the_role_declared(self):
        """The exact scenario the mission calls out by name: 'Claude Code...
        cannot accidentally become a reasoning provider' — even a spec that
        forgets to set `role=CODING_AGENT_ROLE` is still caught, because
        the identity-set check is independent of it."""
        spec = _spec(provider_id="claude-code", role=REASONING_ROLE)
        assert is_coding_agent(spec) is True

    def test_the_identity_check_also_matches_via_inventory_key(self):
        spec = _spec(provider_id="my-app", inventory_key="claude_code", role=REASONING_ROLE)
        assert is_coding_agent(spec) is True

    def test_generic_across_vendors_not_just_claude(self):
        """The mission names several by name: Claude Code, Codex, Cursor
        agents, Kimi coding agents."""
        for identity in ("codex", "cursor", "kimi-code"):
            spec = _spec(provider_id=identity, role=REASONING_ROLE)
            assert is_coding_agent(spec) is True, identity

    def test_a_partial_word_match_inside_a_real_reasoning_app_id_is_not_flagged(self):
        """Substring matching is real but must not be so loose it flags an
        unrelated application whose id happens to contain a coding-agent
        word as a fragment."""
        spec = _spec(provider_id="chatgpt-desktop", inventory_key="chatgpt_desktop")
        assert is_coding_agent(spec) is False

    def test_every_real_catalog_entry_that_is_not_declared_a_coding_agent_is_not_flagged(self):
        """Regression guard: adding a new real desktop reasoning app to the
        catalog must never accidentally trip the coding-agent identity
        set."""
        for spec in PROVIDER_CATALOG:
            if spec.role == CODING_AGENT_ROLE:
                continue
            assert is_coding_agent(spec) is False, spec.provider_id


class TestAvailabilityRejectsCodingAgents:
    def test_a_coding_agent_spec_is_unavailable_even_when_installed_and_healthy(self):
        spec = _spec(provider_id="claude-code", inventory_key="claude_code_app")

        class _InstalledHealthyApp:
            installed = True
            healthy = True
            version = "1.0"

        class _FakeInventory:
            def get(self, key):
                return _InstalledHealthyApp() if key == spec.inventory_key else None

        available, detail = availability(spec, _FakeInventory(), enabled=frozenset())

        assert available is False
        assert "CODING_AGENT_NOT_A_REASONING_PROVIDER" in detail

    def test_checked_before_the_static_unsafe_reason_so_both_can_coexist(self):
        spec = _spec(
            provider_id="claude-code",
            autonomous_reasoning_unsafe_reason="some other reason entirely",
        )
        available, detail = availability(spec, None, enabled=frozenset())
        assert available is False
        assert "CODING_AGENT_NOT_A_REASONING_PROVIDER" in detail


class TestBuildDesktopProvidersExcludesCodingAgents:
    def test_a_coding_agent_entry_never_becomes_a_constructed_provider(self, monkeypatch):
        coding_agent_spec = _spec(provider_id="claude-code", role=CODING_AGENT_ROLE)
        reasoning_spec = _spec(provider_id="a-real-reasoning-app")
        monkeypatch.setattr(mod, "PROVIDER_CATALOG", (coding_agent_spec, reasoning_spec))

        providers = mod.build_desktop_providers(DesktopContext(probe=None))

        provider_ids = {p.provider_id for p in providers}
        assert "claude-code" not in provider_ids
        assert "a-real-reasoning-app" in provider_ids

    def test_an_identity_matched_coding_agent_is_also_excluded_without_the_role_set(self, monkeypatch):
        """The current development environment's own identity, if it were
        ever added to the catalog without remembering to set the role,
        still can't slip through — the identity-set check is independent
        of the role field."""
        forgotten_role_spec = _spec(provider_id="claude-code")  # role defaults to REASONING_ROLE
        monkeypatch.setattr(mod, "PROVIDER_CATALOG", (forgotten_role_spec,))

        providers = mod.build_desktop_providers(DesktopContext(probe=None))

        assert providers == []


class TestCompleteRefusesCodingAgentsBeforeTouchingTheMachine:
    def test_complete_refuses_immediately_for_a_coding_agent_spec(self):
        """Includes the mission's own explicit test requirement for the
        persistent-session feature: a coding-agent session can never
        satisfy the 'Kalpavriksha Reasoning' session requirement, because
        `ReasoningSessionManager.establish()` — find-or-create-named-session
        included — is never even reached for one."""
        spec = _spec(provider_id="claude-code", role=CODING_AGENT_ROLE)
        provider = mod.DesktopAppReasoningProvider(spec, context=DesktopContext(probe=None))

        def _boom(*args, **kwargs):
            raise AssertionError("must not touch the machine for a coding-agent spec")

        provider._context.inventory = _boom
        provider._launch_or_focus = _boom
        provider._sessions.establish = _boom

        result = provider.complete("some reasoning prompt")

        assert result.ok is False
        assert "CODING_AGENT_NOT_A_REASONING_PROVIDER" in result.error

    def test_availability_reports_the_coding_agent_exclusion(self):
        spec = _spec(provider_id="codex", role=CODING_AGENT_ROLE)
        provider = mod.DesktopAppReasoningProvider(spec, context=DesktopContext(probe=None))

        availability_result = provider.availability()

        assert availability_result.reachable is False
        assert "CODING_AGENT_NOT_A_REASONING_PROVIDER" in availability_result.detail
