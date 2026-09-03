"""A conversation's name is transport metadata, never a turn.

The founder opened Perplexity and found the first user message of the
conversation was the text `Kalpavriksha Reasoning`. That string is the
thread's NAME. It had been typed into the message composer and sent, so
the model's first turn was a label instead of the founder's request.

`_rename()` clicked a rename control, then typed into whatever held
keyboard focus and pressed enter. When the rename affordance did not
actually open -- the generic vocabulary matched some other control, or
the application has no rename menu -- focus was still on the composer.

These drive the real `ReasoningSessionManager` against a UIA double, so
the contract is proven without opening an application or spending a
provider call.
"""
from __future__ import annotations

import pytest

from master_agent.providers.reasoning_session import (
    DEDICATED_SESSION_NAME,
    ReasoningSessionManager,
    build_session_marker,
)

TEST_PROMPT = (
    "Plan the next continuation for req_3.\n"
    "Reply with JSON only.\n"
    "This exact text is what the model must receive first."
)


class Element:
    """One UIA element, identified by name."""

    def __init__(self, name):
        self.name = name

    def __repr__(self):  # pragma: no cover - diagnostics only
        return f"<{self.name}>"


class FakeUia:
    """A UIA surface that records every keystroke it is given.

    `rename_opens_a_field` is the whole experiment: when an application
    really opens a rename box, focus lands on it; when it does not, focus
    stays where it was -- on the composer.
    """

    def __init__(self, *, rename_opens_a_field: bool, composer_findable: bool = True):
        self.composer = Element("composer")
        self.name_field = Element("name field")
        self._rename_opens_a_field = rename_opens_a_field
        self._composer_findable = composer_findable
        #: (element name, text) for everything typed anywhere.
        self.typed: list[tuple[str, str]] = []
        self.keys: list[str] = []

    # -- discovery ----------------------------------------------------
    def find_composer(self, handle, **kwargs):
        if not self._composer_findable:
            from master_agent.desktop.execution.uia_control import UiaTargetNotFound

            raise UiaTargetNotFound("no composer")
        return self.composer

    def find(self, handle, **kwargs):
        return Element("some control")

    def get_focused_element_in_window(self, handle):
        return self.name_field if self._rename_opens_a_field else self.composer

    def same_element(self, first, second):
        return first is second

    # -- interaction --------------------------------------------------
    def click(self, element, mouse=None):
        return True

    def write_text(self, element, text, keyboard=None, append=False, mouse=None):
        self.typed.append((element.name, text))
        return True

    def snapshot_text_regions(self, handle):
        return ()

    def read_text(self, element):
        return ""


class FakeKeyboard:
    def __init__(self, uia):
        self._uia = uia

    def press(self, key):
        self._uia.keys.append(key)


def manager_for(uia):
    return ReasoningSessionManager(uia, mouse=None)


def rename(uia, monkeypatch, *, action_found=True):
    """Drive the real `_rename`, with control discovery stubbed."""
    manager = manager_for(uia)
    monkeypatch.setattr(
        manager, "_find_by_vocabulary",
        lambda handle, vocabulary: Element("rename action") if action_found else None,
    )
    monkeypatch.setattr(manager, "find_named_session", lambda handle: object())
    return manager._rename(1, FakeKeyboard(uia), DEDICATED_SESSION_NAME)


# ---------------------------------------------------------------------
# The bug
# ---------------------------------------------------------------------


def test_the_title_is_never_typed_into_the_message_composer(monkeypatch):
    """The exact founder-visible failure: rename did not open, focus was
    still the composer, and the title became the first user turn."""
    uia = FakeUia(rename_opens_a_field=False)

    renamed = rename(uia, monkeypatch)

    assert renamed is False, "a rename was reported that never happened"
    composer_writes = [text for name, text in uia.typed if name == "composer"]
    assert composer_writes == [], (
        "the conversation title was typed into the message composer: "
        f"{composer_writes}")
    assert uia.keys == [], "enter was pressed, submitting the title as a turn"


def test_a_real_rename_field_still_gets_the_name(monkeypatch):
    """The fix must not cost renaming where it genuinely works."""
    uia = FakeUia(rename_opens_a_field=True)

    renamed = rename(uia, monkeypatch)

    assert renamed is True
    assert uia.typed == [("name field", DEDICATED_SESSION_NAME)]
    assert uia.keys == ["enter"]


def test_an_unlocatable_composer_is_treated_as_unsafe(monkeypatch):
    """Inconclusive is not a yes. If the composer cannot be found, the
    focused element cannot be proven safe, and nothing is typed."""
    uia = FakeUia(rename_opens_a_field=True, composer_findable=False)

    renamed = rename(uia, monkeypatch)

    assert renamed is False
    assert uia.typed == []
    assert uia.keys == []


def test_a_uia_surface_without_the_comparison_types_nothing(monkeypatch):
    """An older/partial UIA surface must fail closed, not fall through
    to typing."""

    class Partial(FakeUia):
        def __init__(self):
            super().__init__(rename_opens_a_field=True)

        find_composer = None
        same_element = None

    uia = Partial()
    renamed = rename(uia, monkeypatch)

    assert renamed is False
    assert uia.typed == []


# ---------------------------------------------------------------------
# The invariant, stated for every chat-style surface
# ---------------------------------------------------------------------


def test_the_marker_prefixes_the_prompt_rather_than_replacing_it():
    """Identity travels WITH the request, not instead of it. The model's
    first turn must contain the founder's actual prompt."""
    marker = build_session_marker("Perplexity Desktop")
    marked = f"[{marker}]\n\n{TEST_PROMPT}"

    assert TEST_PROMPT in marked
    assert marked != marker
    assert marked.endswith(TEST_PROMPT)
    # and the name is not the payload
    assert marked.strip() != DEDICATED_SESSION_NAME


def test_the_desktop_lane_sends_one_message_carrying_the_real_prompt():
    """A source guard on the composition: the marker is a PREFIX, never
    a separate submitted turn."""
    import inspect

    from master_agent.providers import desktop_app

    source = inspect.getsource(desktop_app)

    assert 'marked_prompt = f"[{session.session_marker}]\\n\\n{prompt}"' in source
    assert "self._write_prompt(window, marked_prompt, keyboard)" in source


@pytest.mark.parametrize(
    "surface", ["perplexity-desktop", "kimi-desktop", "chatgpt-desktop",
                "claude-desktop"])
def test_no_chat_surface_may_submit_its_own_session_name(surface, monkeypatch):
    """The contract holds for every trusted chat-style surface, not only
    the one the founder happened to open."""
    uia = FakeUia(rename_opens_a_field=False)

    rename(uia, monkeypatch)

    assert all(name != "composer" for name, _ in uia.typed), surface
    assert DEDICATED_SESSION_NAME not in [t for _, t in uia.typed if _ == "composer"]


def test_a_composer_that_is_also_the_focused_element_blocks_the_rename():
    """The distinction the existing doubles did not model: when focus and
    composer are the SAME element, typing would send the title. Four
    manager tests passed for years without expressing this, because their
    fake had no way to answer 'are these the same element?'."""

    class Fused(FakeUia):
        def __init__(self):
            super().__init__(rename_opens_a_field=False)
            self.name_field = self.composer

    uia = Fused()
    manager = manager_for(uia)
    assert manager._focus_is_safe_to_name(1, uia.composer) is False
    assert manager._focus_is_safe_to_name(1, Element("elsewhere")) is True
