"""`ReasoningSessionManager` — finding or creating the one persistent,
named `"Kalpavriksha Reasoning"` reasoning conversation before any prompt
is written into a desktop AI application.

Architectural history (see `reasoning_session.py`'s own module docstring
for the full account): the original model asked whether whatever was
currently focused looked empty (missed a real incident — the focused
conversation was an active Claude Code session); the first correction
actively requested a new session every call and treated the verified
click as the isolation guarantee; **this correction** replaces "a new,
anonymous session every call" with "find-or-create the one persistent,
exact-named session, and reuse it" — the founder's own explicit
requirement.
"""
from __future__ import annotations

from master_agent.desktop.execution.uia_control import UiaTargetNotFound, UiaUnavailable
from master_agent.providers.reasoning_session import (
    CHAT_SECTION_LABEL,
    DEDICATED_SESSION_NAME,
    ISOLATION_UNVERIFIED,
    NEW_SESSION_VOCABULARY,
    RENAME_ACTION_VOCABULARY,
    RENAME_TRIGGER_VOCABULARY,
    ReasoningSessionManager,
    build_session_marker,
)


class FakeUiaBridge:
    """A fake `UiaAutomationBridge` covering every method
    `ReasoningSessionManager` calls: `find()`, `click()`,
    `get_focused_element_in_window()`, `write_text()`.

    `existing_sessions` simulates the set of real conversations already
    present in the application, keyed by their own *exact* visible name
    — `find(name_exact=...)` only ever matches a key that equals the
    request case-insensitively, never a substring, mirroring the real
    `UiaAutomationBridge.find()`'s own exact-match semantics exactly (that
    matching logic itself is tested in `test_desktop_uia.py`; this fake
    exists to prove `ReasoningSessionManager` *uses* `name_exact`, not to
    re-test `find()` itself).
    """

    def __init__(
        self,
        existing_sessions: dict[str, object] | None = None,
        new_session_control: bool = True,
        new_session_control_phrase: str | None = None,
        new_session_click_result: bool = True,
        has_chat_section: bool = False,
        chat_section_click_result: bool = True,
        rename_action_available: bool = False,
        rename_trigger_available: bool = False,
        rename_click_result: bool = True,
        get_focused_raises: bool = False,
        write_text_result: bool = True,
        find_raises: Exception | None = None,
    ):
        self.sessions: dict[str, object] = dict(existing_sessions or {})
        self._new_session_control = new_session_control
        self._new_session_control_phrase = new_session_control_phrase
        self._new_session_click_result = new_session_click_result
        self._has_chat_section = has_chat_section
        self._chat_section_click_result = chat_section_click_result
        self._rename_action_available = rename_action_available
        self._rename_trigger_available = rename_trigger_available
        self._rename_click_result = rename_click_result
        self._get_focused_raises = get_focused_raises
        self._write_text_result = write_text_result
        self._find_raises = find_raises

        self.chat_section_element = object()
        self.new_session_element = object()
        self.rename_action_element = object()
        self.rename_trigger_element = object()
        self.focused_element = object()

        self.clicked_elements: list[object] = []
        self.find_calls: list[str] = []
        self.written: list[tuple[object, str]] = []
        self.enter_pressed = False

    def find(self, handle, *, name_contains=None, name_exact=None, visible_only=False, retries=0):
        self.find_calls.append(name_exact or name_contains)
        if self._find_raises is not None:
            raise self._find_raises

        if name_exact == CHAT_SECTION_LABEL:
            if self._has_chat_section:
                return self.chat_section_element
            raise UiaTargetNotFound("no chat section tab found")

        if name_exact is not None:
            for session_name, element in self.sessions.items():
                if session_name.lower() == name_exact.lower():
                    return element
            raise UiaTargetNotFound(f"no element with exact name {name_exact!r}")

        if name_contains is not None:
            phrase = name_contains.lower()
            if self._new_session_control and phrase in NEW_SESSION_VOCABULARY:
                if self._new_session_control_phrase is None or phrase == self._new_session_control_phrase:
                    return self.new_session_element
            if self._rename_action_available and phrase in RENAME_ACTION_VOCABULARY:
                return self.rename_action_element
            if self._rename_trigger_available and phrase in RENAME_TRIGGER_VOCABULARY:
                return self.rename_trigger_element
            raise UiaTargetNotFound(f"no element matched {name_contains!r}")

        raise UiaTargetNotFound("no search criteria given")

    def click(self, element, mouse):
        self.clicked_elements.append(element)
        if element is self.chat_section_element:
            return self._chat_section_click_result
        if element is self.new_session_element:
            return self._new_session_click_result
        if element in (self.rename_action_element, self.rename_trigger_element):
            return self._rename_click_result
        # opening an already-existing named session
        return True

    def get_focused_element_in_window(self, handle):
        if self._get_focused_raises:
            raise UiaTargetNotFound("nothing focused in this window")
        return self.focused_element

    def write_text(self, element, text, keyboard, append=False, mouse=None):
        self.written.append((element, text))
        keyboard.press("enter")
        if self._write_text_result:
            # Simulate a successful rename: the conversation now carries
            # this exact name and becomes findable by it, same as a real
            # renamed conversation would.
            self.sessions[text] = self.new_session_element
        return self._write_text_result


class FakeMouse:
    pass


class FakeKeyboard:
    def __init__(self):
        self.pressed: list[str] = []

    def press(self, key):
        self.pressed.append(key)


class TestFindNamedSession:
    """Rule #2's own explicit requirement: exact-name matching, never a
    substring match. Real, live-found risk this guards against: a
    substring search for 'Kalpavriksha Reasoning' matched an unrelated
    historical conversation during this session's own knowledge-
    acquisition work."""

    def test_finds_the_exact_named_session(self):
        target = object()
        bridge = FakeUiaBridge(existing_sessions={DEDICATED_SESSION_NAME: target})
        manager = ReasoningSessionManager(bridge, FakeMouse())

        found = manager.find_named_session(handle=1)

        assert found is target

    def test_substring_collision_the_exact_one_is_selected(self):
        """Given 'Kalpavriksha Reasoning — old test', 'Kalpavriksha
        Reasoning', and 'Kalpavriksha Reasoning backup' all exist, only
        the exact one is ever returned."""
        exact = object()
        bridge = FakeUiaBridge(existing_sessions={
            "Kalpavriksha Reasoning — old test": object(),
            DEDICATED_SESSION_NAME: exact,
            "Kalpavriksha Reasoning backup": object(),
        })
        manager = ReasoningSessionManager(bridge, FakeMouse())

        found = manager.find_named_session(handle=1)

        assert found is exact

    def test_no_exact_match_a_substring_only_lookalike_is_not_used(self):
        """Given only 'My Kalpavriksha Reasoning Notes' exists (the exact
        phrase is only a *substring* of its title), it must not be
        selected — `find_named_session()` returns `None`."""
        bridge = FakeUiaBridge(existing_sessions={
            "My Kalpavriksha Reasoning Notes": object(),
        })
        manager = ReasoningSessionManager(bridge, FakeMouse())

        found = manager.find_named_session(handle=1)

        assert found is None

    def test_no_sessions_at_all_returns_none_not_an_error(self):
        bridge = FakeUiaBridge(existing_sessions={})
        manager = ReasoningSessionManager(bridge, FakeMouse())

        assert manager.find_named_session(handle=1) is None

    def test_a_com_level_failure_is_treated_as_not_found_not_raised(self):
        bridge = FakeUiaBridge(find_raises=UiaUnavailable("COM error"))
        manager = ReasoningSessionManager(bridge, FakeMouse())

        assert manager.find_named_session(handle=1) is None


class TestEstablishReusesAnExistingSession:
    """Given the exact 'Kalpavriksha Reasoning' conversation already
    exists: it is opened and reused; no new session is created."""

    def test_the_existing_session_is_opened_and_marked_reused(self):
        target = object()
        bridge = FakeUiaBridge(existing_sessions={DEDICATED_SESSION_NAME: target})
        manager = ReasoningSessionManager(bridge, FakeMouse())

        result = manager.establish({"handle": 1}, "Some App", FakeKeyboard())

        assert result.ok is True
        assert result.reused is True
        assert target in bridge.clicked_elements

    def test_no_new_session_control_is_ever_searched_for(self):
        target = object()
        bridge = FakeUiaBridge(
            existing_sessions={DEDICATED_SESSION_NAME: target},
            new_session_control=True,  # would succeed if ever tried
        )
        manager = ReasoningSessionManager(bridge, FakeMouse())

        manager.establish({"handle": 1}, "Some App", FakeKeyboard())

        assert bridge.new_session_element not in bridge.clicked_elements
        assert not any(phrase in bridge.find_calls for phrase in NEW_SESSION_VOCABULARY)

    def test_opening_the_existing_session_but_failing_to_click_fails_closed(self):
        class UnclickableBridge(FakeUiaBridge):
            def click(self, element, mouse):
                self.clicked_elements.append(element)
                return False

        bridge = UnclickableBridge(existing_sessions={DEDICATED_SESSION_NAME: object()})
        manager = ReasoningSessionManager(bridge, FakeMouse())

        result = manager.establish({"handle": 1}, "Some App", FakeKeyboard())

        assert result.ok is False
        assert ISOLATION_UNVERIFIED in result.reason


class TestEstablishCreatesWhenMissing:
    """Given no exact-named session exists: a new one is created via the
    existing generic vocabulary search, then renamed."""

    def test_a_new_session_is_created_and_renamed(self):
        bridge = FakeUiaBridge(existing_sessions={}, rename_action_available=True)
        manager = ReasoningSessionManager(bridge, FakeMouse())

        result = manager.establish({"handle": 1}, "Some App", FakeKeyboard())

        assert result.ok is True
        assert result.reused is False
        assert result.renamed is True
        assert bridge.new_session_element in bridge.clicked_elements
        assert bridge.rename_action_element in bridge.clicked_elements
        assert (bridge.focused_element, DEDICATED_SESSION_NAME) in bridge.written

    def test_the_renamed_session_is_then_findable_by_exact_name(self):
        bridge = FakeUiaBridge(existing_sessions={}, rename_action_available=True)
        manager = ReasoningSessionManager(bridge, FakeMouse())

        manager.establish({"handle": 1}, "Some App", FakeKeyboard())

        assert manager.find_named_session(handle=1) is not None

    def test_rename_via_a_more_options_trigger_when_no_direct_rename_control_exists(self):
        """Some applications require opening a 'more options'-style menu
        before a direct 'Rename' action becomes visible."""
        bridge = FakeUiaBridge(
            existing_sessions={}, rename_action_available=False, rename_trigger_available=False,
        )
        # Simulate: rename action only becomes available *after* the
        # trigger is clicked.
        original_click = bridge.click

        def click_then_reveal(element, mouse):
            result = original_click(element, mouse)
            if element is bridge.rename_trigger_element:
                bridge._rename_action_available = True
            return result

        bridge.click = click_then_reveal
        bridge._rename_trigger_available = True
        manager = ReasoningSessionManager(bridge, FakeMouse())

        result = manager.establish({"handle": 1}, "Some App", FakeKeyboard())

        assert result.ok is True
        assert result.renamed is True
        assert bridge.rename_trigger_element in bridge.clicked_elements

    def test_rename_trigger_matches_actions_wording_not_only_options_wording(self):
        """Real, live-found gap: reproduced against Perplexity Desktop,
        whose per-session menu trigger is named 'Session actions' /
        'More actions' — neither contains the word 'options' at all, so
        an 'options'-only vocabulary would never find it."""
        assert "session actions" in RENAME_TRIGGER_VOCABULARY
        assert "more actions" in RENAME_TRIGGER_VOCABULARY

    def test_no_discoverable_new_session_control_fails_closed(self):
        bridge = FakeUiaBridge(existing_sessions={}, new_session_control=False)
        manager = ReasoningSessionManager(bridge, FakeMouse())

        result = manager.establish({"handle": 1}, "Some App", FakeKeyboard())

        assert result.ok is False
        assert ISOLATION_UNVERIFIED in result.reason

    def test_a_bare_new_control_is_found_only_after_every_more_specific_phrase_fails(self):
        """Real, live-found generic vocabulary gap: reproduced against
        Perplexity Desktop's own sidebar control, whose accessible name
        is exactly 'New' — too terse to contain any of the more specific
        phrases ('new chat', 'new task', ...) as a substring. 'new' is
        tried last, deliberately, so any more specific, lower
        false-positive-risk phrase is always preferred first."""
        bridge = FakeUiaBridge(
            existing_sessions={}, new_session_control=True, new_session_control_phrase="new",
            rename_action_available=True,
        )
        manager = ReasoningSessionManager(bridge, FakeMouse())

        result = manager.establish({"handle": 1}, "Some App", FakeKeyboard())

        assert result.ok is True
        assert "new" in bridge.find_calls
        # every more specific phrase was tried, and failed, before it
        assert bridge.find_calls.index("new chat") < bridge.find_calls.index("new")

    def test_new_session_control_found_but_click_fails_closed(self):
        bridge = FakeUiaBridge(existing_sessions={}, new_session_click_result=False)
        manager = ReasoningSessionManager(bridge, FakeMouse())

        result = manager.establish({"handle": 1}, "Some App", FakeKeyboard())

        assert result.ok is False
        assert ISOLATION_UNVERIFIED in result.reason


class TestRenameIsBestEffort:
    """A session genuinely created but not renameable is still a valid,
    isolated conversation for *this* call. Only *reuse* on a future call
    degrades.

    These assertions were briefly inverted, on the strength of a real
    measurement -- rename failed on perplexity-desktop and kimi-desktop --
    and a wrong inference from it. "Not named exactly
    DEDICATED_SESSION_NAME" is not "unidentified", and
    `can_rename_chat: UNKNOWN` for those applications is a question
    nobody has answered, not a settled "unsupported".

    Kimi Desktop's own conversation list shows why: it auto-titles a
    conversation from its first message, so a conversation this manager
    created -- carrying the `[Kalpavriksha Reasoning - ...]` marker as its
    first message -- is neither anonymous nor the founder's. That is the
    strategy `app_knowledge.catalog` already records for ChatGPT and Kimi.

    The fail-closed rule that protects the founder is the one asserted in
    `TestNoNewSessionControl`: no verified-fresh conversation means no
    reasoning, and an already-active chat is never reused.
    """

    def test_no_rename_control_discoverable_still_succeeds_this_call(self):
        bridge = FakeUiaBridge(
            existing_sessions={}, rename_action_available=False, rename_trigger_available=False,
        )
        manager = ReasoningSessionManager(bridge, FakeMouse())

        result = manager.establish({"handle": 1}, "Some App", FakeKeyboard())

        assert result.ok is True
        assert result.reused is False
        assert result.renamed is False

    def test_focus_never_lands_in_this_window_rename_fails_gracefully(self):
        bridge = FakeUiaBridge(
            existing_sessions={}, rename_action_available=True, get_focused_raises=True,
        )
        manager = ReasoningSessionManager(bridge, FakeMouse())

        result = manager.establish({"handle": 1}, "Some App", FakeKeyboard())

        assert result.ok is True
        assert result.renamed is False

    def test_write_text_failing_is_not_fatal_to_the_call(self):
        bridge = FakeUiaBridge(
            existing_sessions={}, rename_action_available=True, write_text_result=False,
        )
        manager = ReasoningSessionManager(bridge, FakeMouse())

        result = manager.establish({"handle": 1}, "Some App", FakeKeyboard())

        assert result.ok is True
        assert result.renamed is False

    def test_an_unrenamed_session_is_not_findable_by_exact_name_next_time(self):
        """The honest degrade: reuse simply will not work on the next
        call — a fresh manager (simulating a wholly separate later call)
        creates another new session instead, exactly like the prior
        architecture always did."""
        bridge = FakeUiaBridge(existing_sessions={}, rename_action_available=False, rename_trigger_available=False)
        manager = ReasoningSessionManager(bridge, FakeMouse())
        manager.establish({"handle": 1}, "Some App", FakeKeyboard())

        assert manager.find_named_session(handle=1) is None


class TestRestartPersistence:
    """Simulates an application restart: the named conversation was
    created by an earlier call and persists (a real application does not
    forget its own conversation list on restart); a later call, using a
    completely fresh `ReasoningSessionManager` instance (no shared
    in-memory state whatsoever — the same posture a real process restart
    would leave this project in), must still rediscover and reuse it, by
    name alone."""

    def test_a_session_created_in_one_call_is_reused_by_a_wholly_separate_later_call(self):
        # "First call, before restart" -- a fresh manager creates and
        # renames the session, using the same bridge a real, persistent
        # application window would represent.
        bridge = FakeUiaBridge(existing_sessions={}, rename_action_available=True)
        first_manager = ReasoningSessionManager(bridge, FakeMouse())
        first_result = first_manager.establish({"handle": 1}, "Some App", FakeKeyboard())
        assert first_result.ok is True
        assert first_result.reused is False

        # "Restart": a wholly new ReasoningSessionManager instance, no
        # in-memory identifier carried over -- only the bridge (standing
        # in for the real, persistent application state) is the same.
        second_manager = ReasoningSessionManager(bridge, FakeMouse())
        second_result = second_manager.establish({"handle": 1}, "Some App", FakeKeyboard())

        assert second_result.ok is True
        assert second_result.reused is True


class TestChatSectionNavigation:
    """The founder's own explicit correction: navigate to the actual Chat
    section before doing anything else, since a real application's window
    can default to a coding-agent/work section. Exact-match on purpose —
    'chat' as a *substring* also matches unrelated sibling elements like
    'New chat' or 'Pin chat' found live in the same real window. A no-op
    for applications with no such split at all (e.g. Perplexity Desktop's
    own single unified surface, confirmed live — see
    docs/audits/APP_KNOWLEDGE_ACQUISITION_1.md)."""

    def test_a_chat_section_tab_is_clicked_when_present(self):
        bridge = FakeUiaBridge(has_chat_section=True)
        manager = ReasoningSessionManager(bridge, FakeMouse())

        navigated = manager._navigate_to_chat_section(handle=1)

        assert navigated is True
        assert bridge.chat_section_element in bridge.clicked_elements

    def test_absence_of_a_chat_section_is_not_an_error(self):
        bridge = FakeUiaBridge(has_chat_section=False)
        manager = ReasoningSessionManager(bridge, FakeMouse())

        navigated = manager._navigate_to_chat_section(handle=1)

        assert navigated is False
        assert bridge.clicked_elements == []

    def test_establish_navigates_to_chat_before_searching_for_the_named_session(self):
        bridge = FakeUiaBridge(has_chat_section=True, existing_sessions={DEDICATED_SESSION_NAME: object()})
        manager = ReasoningSessionManager(bridge, FakeMouse())

        result = manager.establish({"handle": 1}, "Some App", FakeKeyboard())

        assert result.ok is True
        assert bridge.find_calls[0] == CHAT_SECTION_LABEL

    def test_establish_still_works_normally_when_no_chat_section_exists(self):
        bridge = FakeUiaBridge(has_chat_section=False, existing_sessions={}, rename_action_available=True)
        manager = ReasoningSessionManager(bridge, FakeMouse())

        result = manager.establish({"handle": 1}, "Some App", FakeKeyboard())

        assert result.ok is True


class TestSessionMarker:
    def test_marker_is_predictable_and_inspectable(self):
        marker = build_session_marker("Some App")
        assert marker.startswith("Kalpavriksha Reasoning — Some App")

    def test_two_markers_generated_in_succession_are_distinct(self):
        """Every individual reasoning request must still be identifiable
        even inside the one persistent, reused conversation."""
        a = build_session_marker("Some App")
        b = build_session_marker("Some App")
        assert a != b
