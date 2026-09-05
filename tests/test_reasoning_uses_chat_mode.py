"""Reasoning is a question, not an instruction to start acting.

A coding agent, a cowork workspace, a computer-use surface and an
autonomous task runner are capabilities that ACT. Sending Brain reasoning
into one asks a tool to start doing things on the founder's machine --
which is not what the Brain decided and not what the Broker selected.

`_navigate_to_chat_section()` handles applications that expose modes as a
visible "Chat" TAB. It cannot help with the ones that expose a SELECTOR:
there is no tab to click, so the call is a silent no-op and the window
stays wherever the founder last left it. Measured live 2026-09-05,
ChatGPT Desktop declares its mode in an accessible name --
"Switch mode, current mode: ChatGPT" -- so the answer is readable.
"""
from __future__ import annotations

from master_agent.providers.reasoning_session import (
    NON_CHAT_MODE,
    ReasoningSessionManager,
    declared_mode,
    is_non_chat_mode,
)


class _Snapshot:
    def __init__(self, name):
        self.name = name


class _Uia:
    def __init__(self, names):
        self._names = list(names)
        self.clicked = 0

    def snapshot_elements(self, handle):
        return [_Snapshot(n) for n in self._names]

    def find(self, *a, **k):
        from master_agent.desktop.execution.uia_control import UiaTargetNotFound
        raise UiaTargetNotFound("no chat tab here")

    def click(self, *a, **k):
        self.clicked += 1
        return True


def _manager(names):
    return ReasoningSessionManager(_Uia(names), mouse=object())


class TestADeclaredModeIsRead:

    def test_a_chat_mode_is_recognised(self):
        assert declared_mode(["Switch mode, current mode: ChatGPT"]) == "ChatGPT"
        assert is_non_chat_mode("ChatGPT") is False

    def test_an_execution_mode_is_recognised(self):
        for mode in ("Cowork", "Code", "Computer", "Agent", "Developer"):
            assert is_non_chat_mode(mode) is True, mode

    def test_an_application_that_declares_nothing_is_not_refused(self):
        """The common case. Most applications have one surface, and
        refusing silence would block every provider that has no modes."""
        assert declared_mode(["New chat", "Send", "Kalpavriksha Reasoning"]) == ""
        assert is_non_chat_mode("") is False

    def test_a_mode_containing_a_keyword_as_a_fragment_is_not_refused(self):
        """"Codex" is not "Code". Whole words only, or a perfectly good
        chat surface gets refused for its spelling."""
        assert is_non_chat_mode("Codex") is False

    def test_a_multi_word_execution_mode_is_still_caught(self):
        assert is_non_chat_mode("Agent Mode") is True
        assert is_non_chat_mode("Computer Use") is True


class TestEstablishRefusesAnExecutionSurface:

    def test_a_cowork_surface_receives_zero_input(self):
        """The whole point: refuse BEFORE anything is typed."""
        manager = _manager(["Switch mode, current mode: Cowork", "New chat"])
        result = manager.establish({"handle": 1}, "chatgpt-desktop", keyboard=object())

        assert result.ok is False
        assert NON_CHAT_MODE in result.reason
        assert "Cowork" in result.reason, "the refusal must name what it saw"

    def test_a_chat_surface_is_not_refused_for_its_mode(self):
        """It may still fail later for other reasons -- what must not
        happen is a refusal ON THE MODE when the mode is fine."""
        manager = _manager(["Switch mode, current mode: ChatGPT", "New chat"])
        result = manager.establish({"handle": 1}, "chatgpt-desktop", keyboard=object())

        assert NON_CHAT_MODE not in (result.reason or "")

    def test_an_application_with_no_modes_is_not_refused_for_its_mode(self):
        manager = _manager(["New chat", "Ask anything"])
        result = manager.establish({"handle": 1}, "perplexity-desktop", keyboard=object())

        assert NON_CHAT_MODE not in (result.reason or "")
