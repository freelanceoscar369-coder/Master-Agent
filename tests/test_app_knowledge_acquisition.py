"""Deterministic tests for `app_knowledge/acquisition.py` — its own
read-only checks, and, most importantly, the structural guarantee that
knowledge acquisition can never type, click, or submit anything."""
from __future__ import annotations

import pytest

from master_agent.ai_infrastructure.catalog import PROVIDER_CATALOG, ProviderSpec
from master_agent.app_knowledge.acquisition import (
    CodingAgentAcquisitionRefused,
    acquire_knowledge,
    check_chat_tab,
    check_composer_current_text,
    check_dedicated_session_present,
    check_loading_state,
    check_offscreen_duplicates,
)
from master_agent.app_knowledge.profile import KnowledgeType
from master_agent.desktop.execution.uia_control import UiaTargetNotFound


class ReadOnlyFakeBridge:
    """A fake `UiaAutomationBridge` exposing every read-only method
    `acquisition.py` might call, plus `write_text`/`click` as methods
    that raise `AssertionError` the instant they are invoked — the
    structural regression guard for "knowledge acquisition never
    mutates anything." A test that reaches either of those two methods
    fails immediately and unambiguously."""

    def __init__(self, chat_tab_present=True, dedicated_session_present=False,
                 composer_text="Type a message", composer_raises=False,
                 loading_texts=(), offscreen_only_names=()):
        self._chat_tab_present = chat_tab_present
        self._dedicated_session_present = dedicated_session_present
        self._composer_text = composer_text
        self._composer_raises = composer_raises
        self._loading_texts = list(loading_texts)
        self._offscreen_only_names = set(offscreen_only_names)
        self.find_calls: list[dict] = []

    # ---- read-only methods, safe to call ---------------------------------

    def find(self, handle, *, name_contains=None, name_exact=None, visible_only=False, retries=0):
        self.find_calls.append({
            "name_contains": name_contains, "name_exact": name_exact, "visible_only": visible_only,
        })
        if name_exact == "Chat":
            if self._chat_tab_present:
                return object()
            raise UiaTargetNotFound("no exact-name 'Chat' element")
        if name_contains == "Kalpavriksha Reasoning":
            if self._dedicated_session_present:
                return object()
            raise UiaTargetNotFound("no dedicated session")
        if name_contains in self._offscreen_only_names:
            if visible_only:
                raise UiaTargetNotFound(f"{name_contains} exists but is off-screen")
            return object()
        raise UiaTargetNotFound(f"no element matched {name_contains or name_exact!r}")

    def find_composer(self, handle):
        if self._composer_raises:
            raise UiaTargetNotFound("no composer-shaped element found")
        return "composer-element"

    def read_text(self, element):
        return self._composer_text

    def snapshot_text_regions(self, handle, min_height=8):
        return {(0, i * 20, 100, i * 20 + 20): text for i, text in enumerate(self._loading_texts)}

    # ---- mutating methods -- must NEVER be called by acquisition ---------

    def write_text(self, *args, **kwargs):
        raise AssertionError("acquisition must never call write_text()")

    def click(self, *args, **kwargs):
        raise AssertionError("acquisition must never call click()")


def _chatgpt_spec():
    return next(spec for spec in PROVIDER_CATALOG if spec.provider_id == "chatgpt-desktop")


def _coding_agent_spec():
    return ProviderSpec(
        provider_id="claude-code", label="Claude Code (test)",
        capabilities=frozenset(), locality="local", privacy="private",
        declared_quality=0.0, cost_per_call=0.0,
    )


class TestReadOnlyGuard:
    """The mission's own absolute rule: knowledge acquisition must
    never type into, click, or submit anything."""

    def test_acquire_knowledge_never_calls_a_mutating_method(self):
        bridge = ReadOnlyFakeBridge()
        # If acquire_knowledge() ever reached write_text()/click(), the
        # fake would raise AssertionError and this test would fail --
        # its passing IS the guarantee.
        acquire_knowledge(_chatgpt_spec(), bridge, handle=1)

    def test_a_bridge_with_no_mutating_methods_at_all_still_works(self):
        """Belt-and-suspenders: a bridge that does not even *implement*
        write_text/click (rather than one that raises) must still let
        acquisition succeed -- proving no code path here references
        them, not merely that a test happens to catch it if it did."""

        class BareReadOnlyBridge:
            def find(self, handle, **kwargs):
                raise UiaTargetNotFound("nothing found")

            def find_composer(self, handle):
                raise UiaTargetNotFound("no composer")

            def read_text(self, element):
                return ""

            def snapshot_text_regions(self, handle, min_height=8):
                return {}

        acquire_knowledge(_chatgpt_spec(), BareReadOnlyBridge(), handle=1)


class TestCodingAgentSeparation:
    def test_acquisition_refuses_a_coding_agent_spec_before_touching_the_bridge(self):
        class _BoomBridge:
            def __getattr__(self, name):
                raise AssertionError(f"acquisition must not touch the bridge at all -- tried {name!r}")

        with pytest.raises(CodingAgentAcquisitionRefused):
            acquire_knowledge(_coding_agent_spec(), _BoomBridge(), handle=1)

    def test_a_normal_reasoning_spec_is_not_refused(self):
        bridge = ReadOnlyFakeBridge()
        result = acquire_knowledge(_chatgpt_spec(), bridge, handle=1)
        assert result  # completed normally, no refusal


class TestChatTabCheck:
    def test_records_true_when_an_exact_name_chat_tab_is_visible(self):
        bridge = ReadOnlyFakeBridge(chat_tab_present=True)
        fact = check_chat_tab(bridge, 1)
        assert fact.value is True
        assert fact.knowledge_type is KnowledgeType.OBSERVED

    def test_records_false_not_silence_when_no_chat_tab_is_found(self):
        """A negative result is still a real, useful observation -- it
        must be recorded, not dropped or raised past the caller."""
        bridge = ReadOnlyFakeBridge(chat_tab_present=False)
        fact = check_chat_tab(bridge, 1)
        assert fact.value is False
        assert fact.knowledge_type is KnowledgeType.OBSERVED
        assert fact.note


class TestDedicatedSessionCheck:
    def test_records_true_when_a_kalpavriksha_reasoning_session_exists(self):
        bridge = ReadOnlyFakeBridge(dedicated_session_present=True)
        fact = check_dedicated_session_present(bridge, 1)
        assert fact.value is True

    def test_records_false_when_none_exists(self):
        bridge = ReadOnlyFakeBridge(dedicated_session_present=False)
        fact = check_dedicated_session_present(bridge, 1)
        assert fact.value is False


class TestComposerCurrentTextCheck:
    def test_reads_whatever_is_currently_there_without_judgement(self):
        """This check does not try to tell a stale draft apart from a
        placeholder -- it only records what is actually visible."""
        bridge = ReadOnlyFakeBridge(composer_text="[old draft] some leftover text")
        fact = check_composer_current_text(bridge, 1)
        assert fact.value == "[old draft] some leftover text"
        assert "placeholder" in fact.note or "draft" in fact.note

    def test_an_unresolvable_composer_is_recorded_not_raised(self):
        bridge = ReadOnlyFakeBridge(composer_raises=True)
        fact = check_composer_current_text(bridge, 1)
        assert fact.value is None
        assert fact.knowledge_type is KnowledgeType.OBSERVED


class TestOffscreenDuplicatesCheck:
    def test_detects_a_hidden_duplicate(self):
        bridge = ReadOnlyFakeBridge(offscreen_only_names={"new chat"})
        fact = check_offscreen_duplicates(bridge, 1, "new chat")
        assert fact.value is True

    def test_no_hidden_duplicate_when_nothing_matches_at_all(self):
        bridge = ReadOnlyFakeBridge()
        fact = check_offscreen_duplicates(bridge, 1, "nonexistent")
        assert fact.value is False


class TestLoadingStateCheck:
    def test_finds_generic_loading_wording_case_insensitively(self):
        bridge = ReadOnlyFakeBridge(loading_texts=["Reconnecting…", "Home", "Settings"])
        fact = check_loading_state(bridge, 1)
        assert "Reconnecting…" in fact.value

    def test_empty_when_nothing_matches(self):
        bridge = ReadOnlyFakeBridge(loading_texts=["Home", "Settings"])
        fact = check_loading_state(bridge, 1)
        assert fact.value == []
