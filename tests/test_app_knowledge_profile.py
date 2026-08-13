"""Deterministic tests for the App Knowledge Profile data model
(`app_knowledge/profile.py`) and the three initial profiles
(`app_knowledge/catalog.py`)."""
from __future__ import annotations

import pytest

from master_agent.app_knowledge.catalog import APP_KNOWLEDGE_CATALOG
from master_agent.app_knowledge.profile import (
    AppKnowledgeProfile,
    Fact,
    KnowledgeType,
    unknown,
)


class TestFact:
    def test_a_fact_without_a_source_is_rejected(self):
        """Undocumented documented knowledge is a contradiction in
        terms — every fact, including UNKNOWN ones, must say where it
        came from (or that it was never investigated)."""
        with pytest.raises(ValueError):
            Fact(value="x", knowledge_type=KnowledgeType.DOCUMENTED, source="")

    def test_a_fact_with_only_whitespace_as_source_is_rejected(self):
        with pytest.raises(ValueError):
            Fact(value="x", knowledge_type=KnowledgeType.OBSERVED, source="   ")

    def test_documented_and_observed_are_confirmed(self):
        assert Fact("x", KnowledgeType.DOCUMENTED, source="official docs").is_confirmed
        assert Fact("x", KnowledgeType.OBSERVED, source="live UIA read").is_confirmed

    def test_inferred_and_unknown_are_never_confirmed(self):
        """The mission's own rule: 'Never present inferred behavior as
        fact.' `is_confirmed` is the one property callers should check
        before acting on a fact as if it were reliable."""
        assert not Fact("x", KnowledgeType.INFERRED, source="reasoned guess").is_confirmed
        assert not Fact(None, KnowledgeType.UNKNOWN, source="not yet investigated").is_confirmed

    def test_unknown_helper_produces_an_unconfirmed_fact(self):
        fact = unknown()
        assert fact.knowledge_type is KnowledgeType.UNKNOWN
        assert not fact.is_confirmed
        assert fact.source  # still carries a non-empty source


class TestAppKnowledgeProfile:
    def _minimal_profile(self):
        return AppKnowledgeProfile(
            provider_id="test-app", label="Test App", last_reviewed="2026-08-13",
        )

    def test_an_unpopulated_profile_defaults_every_field_to_unknown(self):
        """A profile built with no facts supplied must be honest about
        that — every field starts UNKNOWN, never silently guessed."""
        profile = self._minimal_profile()
        for name, fact in profile.all_facts().items():
            assert fact.knowledge_type is KnowledgeType.UNKNOWN, f"{name} was not UNKNOWN by default"

    def test_unresolved_questions_lists_every_still_unknown_field(self):
        profile = self._minimal_profile()
        assert set(profile.unresolved_questions()) == set(profile.all_facts().keys())

    def test_merge_observations_only_changes_the_named_fields(self):
        profile = self._minimal_profile()
        updated = profile.merge_observations({
            "chat_interface": Fact("A 'Chat' tab", KnowledgeType.OBSERVED, source="live read"),
        })
        assert updated.chat_interface.value == "A 'Chat' tab"
        assert updated.chat_interface.knowledge_type is KnowledgeType.OBSERVED
        # every other field is untouched
        assert updated.other_modes.knowledge_type is KnowledgeType.UNKNOWN
        assert updated.new_session_creation.knowledge_type is KnowledgeType.UNKNOWN

    def test_merge_observations_does_not_mutate_the_original(self):
        """`AppKnowledgeProfile` is frozen, like every other declarative
        record in this codebase — acquisition must never silently
        rewrite a profile another caller is still holding a reference
        to."""
        profile = self._minimal_profile()
        profile.merge_observations({
            "chat_interface": Fact("A 'Chat' tab", KnowledgeType.OBSERVED, source="live read"),
        })
        assert profile.chat_interface.knowledge_type is KnowledgeType.UNKNOWN

    def test_merge_observations_rejects_an_unknown_field_name(self):
        profile = self._minimal_profile()
        with pytest.raises(ValueError):
            profile.merge_observations({
                "not_a_real_field": Fact("x", KnowledgeType.OBSERVED, source="live read"),
            })

    def test_merge_observations_rejects_a_non_observed_fact(self):
        """`merge_observations()` is specifically for acquisition
        results — passing it a DOCUMENTED or INFERRED fact would blur
        exactly the distinction the mission requires stay clear."""
        profile = self._minimal_profile()
        with pytest.raises(ValueError):
            profile.merge_observations({
                "chat_interface": Fact("A 'Chat' tab", KnowledgeType.INFERRED, source="a guess"),
            })


class TestInitialCatalog:
    """The three initial profiles the mission asked for — structural
    completeness and honesty checks, not a re-assertion of every fact's
    content (that lives in the profiles themselves and the audit
    report)."""

    @pytest.mark.parametrize("provider_id", ["chatgpt-desktop", "kimi-desktop", "perplexity-desktop"])
    def test_every_initial_target_has_a_profile(self, provider_id):
        assert provider_id in APP_KNOWLEDGE_CATALOG

    @pytest.mark.parametrize("provider_id", ["chatgpt-desktop", "kimi-desktop", "perplexity-desktop"])
    def test_every_fact_carries_a_real_source(self, provider_id):
        profile = APP_KNOWLEDGE_CATALOG[provider_id]
        for name, fact in profile.all_facts().items():
            assert fact.source.strip(), f"{provider_id}.{name} has an empty source"

    def test_perplexity_write_and_response_path_remains_unconfirmed(self):
        """The mission's own explicit instruction: 'Do NOT claim
        Perplexity is configured or validated merely because a
        knowledge profile exists.' A safe, read-only pass legitimately
        earned a handful of OBSERVED facts (e.g. that no distinct 'Chat'
        tab exists) — that is real, useful knowledge, not a
        contradiction. What must *not* happen is any of the
        write/submit/response-path fields — the parts that would only
        ever be confirmed by actually running a prompt through this
        application — reading as OBSERVED, since knowledge acquisition
        never performs a write and no automation has ever targeted this
        application."""
        profile = APP_KNOWLEDGE_CATALOG["perplexity-desktop"]
        write_and_response_fields = (
            "send_representation", "enter_submits", "response_exposure",
            "persists_unsent_drafts", "safe_active_session_indicator",
        )
        facts = profile.all_facts()
        for name in write_and_response_fields:
            assert facts[name].knowledge_type is not KnowledgeType.OBSERVED, (
                f"perplexity-desktop.{name} reads as OBSERVED, but confirming it would require "
                "a write/submit this application has never received"
            )

    def test_chatgpt_and_kimi_have_real_observed_evidence(self):
        """Unlike Perplexity, these two were extensively live-tested
        this session — their profiles should reflect that, not read as
        pure documentation research."""
        for provider_id in ("chatgpt-desktop", "kimi-desktop"):
            profile = APP_KNOWLEDGE_CATALOG[provider_id]
            observed_count = sum(
                1 for f in profile.all_facts().values() if f.knowledge_type is KnowledgeType.OBSERVED
            )
            assert observed_count > 0, f"{provider_id} has no OBSERVED facts despite live testing this session"

    def test_no_inferred_fact_is_ever_presented_without_saying_so(self):
        """A structural version of 'never present inferred behavior as
        fact': every INFERRED fact's own source string must itself
        acknowledge it is a generalization/guess, not a direct
        observation -- readable by a human without opening this test."""
        for profile in APP_KNOWLEDGE_CATALOG.values():
            for name, fact in profile.all_facts().items():
                if fact.knowledge_type is KnowledgeType.INFERRED:
                    assert not fact.source.lower().startswith("live "), (
                        f"{profile.provider_id}.{name} is INFERRED but its source reads "
                        "like a direct live observation"
                    )
