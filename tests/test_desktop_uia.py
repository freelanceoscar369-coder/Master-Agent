"""Universal Autonomous Desktop Executive — deterministic (Level 1) tests
for `desktop/execution/uia_control.py` and `text_control.classify_window`.

No real UIA/COM traversal happens here — `UiaAutomationBridge._root`/
`_descendants` are monkeypatched to return fake, duck-typed elements, so
every test in this file is fast and exercises the real matching/
filtering/verification *logic* (Section 15's own testing standard: "Level
1 — deterministic unit tests... interface selection... verification
logic"). The one real thing this file's import chain touches is
`comtypes.client.GetModule("UIAutomationCore.dll")` — a Windows system
component, not something these tests need a live application for; this
matches every other test in this suite already assuming `sys.platform ==
"win32"`.

Live, real-machine evidence (a genuine Electron application, real window,
real composer, real submitted prompt, real read-back response) lives in
`docs/audits/UNIVERSAL_AUTONOMOUS_DESKTOP_EXECUTIVE_1.md`, not here —
Section 11's own Level 3 is deliberately not a unit test.
"""
from __future__ import annotations

import pytest

from master_agent.desktop.execution.uia_control import (
    UiaAutomationBridge,
    UiaTargetNotFound,
    UiaUnavailable,
)
from master_agent.desktop.execution.text_control import (
    Win32ChildEnumBackend,
    classify_window,
)


class _Rect:
    def __init__(self, left, top, right, bottom):
        self.left, self.top, self.right, self.bottom = left, top, right, bottom


class FakeUiaElement:
    """A duck-typed stand-in for `IUIAutomationElement` — every attribute
    this module actually reads, nothing more."""

    def __init__(
        self, name="", automation_id="", control_type=50026, is_enabled=True,
        is_focusable=False, rect=(0, 0, 100, 20), has_value=False, has_text=False,
        value="", text="", read_only=False, invokable=False, is_offscreen=False,
    ):
        self.CurrentName = name
        self.CurrentAutomationId = automation_id
        self.CurrentControlType = control_type
        self.CurrentIsKeyboardFocusable = is_focusable
        self.CurrentBoundingRectangle = _Rect(*rect)
        self._has_value = has_value
        self._has_text = has_text
        self._value = value
        self._text = text
        self._read_only = read_only
        self._invokable = invokable
        self._is_offscreen = is_offscreen
        self.focused = False

    def set_text(self, text):
        """Mutate this element's own text in place — for tests that need
        to simulate a region's content changing between two reads (e.g. a
        `snapshot_text_regions()` baseline vs. a later `find_new_content()`
        poll) without swapping in a whole new fake element."""
        self._text = text

    def GetCurrentPropertyValue(self, prop_id):
        from master_agent.desktop.execution.uia_control import (
            _IS_VALUE_PATTERN_AVAILABLE_PROPERTY_ID,
            _IS_TEXT_PATTERN_AVAILABLE_PROPERTY_ID,
            _IS_ENABLED_PROPERTY_ID,
            _IS_OFFSCREEN_PROPERTY_ID,
        )
        if prop_id == _IS_VALUE_PATTERN_AVAILABLE_PROPERTY_ID:
            return self._has_value
        if prop_id == _IS_TEXT_PATTERN_AVAILABLE_PROPERTY_ID:
            return self._has_text
        if prop_id == _IS_ENABLED_PROPERTY_ID:
            return True
        if prop_id == _IS_OFFSCREEN_PROPERTY_ID:
            return self._is_offscreen
        return False

    def SetFocus(self):
        self.focused = True

    def GetCurrentPattern(self, pattern_id):
        from master_agent.desktop.execution.uia_control import (
            _VALUE_PATTERN_ID, _TEXT_PATTERN_ID, _INVOKE_PATTERN_ID,
        )
        element = self
        if pattern_id == _VALUE_PATTERN_ID and self._has_value:
            return _FakeValuePatternHolder(element)
        if pattern_id == _TEXT_PATTERN_ID and self._has_text:
            return _FakeTextPatternHolder(element)
        if pattern_id == _INVOKE_PATTERN_ID and self._invokable:
            return _FakeInvokePatternHolder(element)
        raise RuntimeError("pattern not supported")


class _FakeValuePatternHolder:
    def __init__(self, element):
        self._element = element

    def QueryInterface(self, _iface):
        return _FakeValuePattern(self._element)


class _FakeValuePattern:
    def __init__(self, element):
        self._element = element

    @property
    def CurrentIsReadOnly(self):
        return self._element._read_only

    def SetValue(self, value):
        self._element._value = value
        self._element._text = value

    @property
    def CurrentValue(self):
        return self._element._value


class _FakeTextPatternHolder:
    def __init__(self, element):
        self._element = element

    def QueryInterface(self, _iface):
        return _FakeTextPattern(self._element)


class _FakeTextPattern:
    def __init__(self, element):
        self._element = element

    @property
    def DocumentRange(self):
        return _FakeDocumentRange(self._element)


class _FakeDocumentRange:
    def __init__(self, element):
        self._element = element

    def GetText(self, _max_length):
        return self._element._text


class _FakeInvokePatternHolder:
    def __init__(self, element):
        self._element = element
        self.invoked = False

    def QueryInterface(self, _iface):
        return _FakeInvokePattern(self._element)


class _FakeInvokePattern:
    def __init__(self, element):
        self._element = element

    def Invoke(self):
        self._element._invoked = True


class FakeKeyboard:
    def __init__(self):
        self.typed: list[str] = []
        self.pasted: list[str] = []
        self.hotkeys: list[tuple] = []
        self.pressed: list[str] = []

    def type(self, text):
        self.typed.append(text)

    def paste(self, text=None):
        self.pasted.append(text)

    def hotkey(self, *keys):
        self.hotkeys.append(keys)

    def press(self, key):
        self.pressed.append(key)


class FakeMouse:
    def __init__(self):
        self.clicks: list[tuple[int, int]] = []

    def click(self, x, y):
        self.clicks.append((x, y))
        return True


def _bridge_with_elements(elements, window_rect=(0, 0, 400, 800)):
    bridge = UiaAutomationBridge()
    root = FakeUiaElement(rect=window_rect)
    bridge._root = lambda handle: root
    bridge._descendants = lambda r: elements
    return bridge


# ═══════════════════════ classify_window ═══════════════════════


class FakeChildEnumBackend:
    def __init__(self, children):
        self._children = children

    def children_of(self, parent_handle):
        return self._children


def test_classify_window_finds_a_classic_control():
    backend = FakeChildEnumBackend([(1, "Edit", "")])
    assert classify_window(999, backend) == "classic"


def test_classify_window_reports_uia_required_for_render_host_children():
    backend = FakeChildEnumBackend([
        (1, "Chrome_RenderWidgetHostHWND", "Chrome Legacy Window"),
        (2, "Intermediate D3D Window", ""),
    ])
    assert classify_window(999, backend) == "uia_required"


def test_classify_window_reports_uia_required_for_unrecognized_children():
    backend = FakeChildEnumBackend([(1, "SomeUnknownClass", "")])
    assert classify_window(999, backend) == "uia_required"


def test_classify_window_survives_an_unreadable_window():
    class ExplodingBackend:
        def children_of(self, parent_handle):
            raise RuntimeError("window gone")

    assert classify_window(999, ExplodingBackend()) == "uia_required"


# ═══════════════════════ find() ═══════════════════════


def test_find_matches_by_name_contains_case_insensitively():
    target = FakeUiaElement(name="Send Message")
    other = FakeUiaElement(name="Sidebar")
    bridge = _bridge_with_elements([other, target])

    found = bridge.find(1, name_contains="send")
    assert found is target


def test_find_matches_by_automation_id_exactly():
    target = FakeUiaElement(automation_id="composer-input")
    other = FakeUiaElement(automation_id="composer-input-2")
    bridge = _bridge_with_elements([other, target])

    found = bridge.find(1, automation_id="composer-input")
    assert found is target


def test_find_raises_not_found_when_nothing_matches():
    bridge = _bridge_with_elements([FakeUiaElement(name="Sidebar")])
    with pytest.raises(UiaTargetNotFound):
        bridge.find(1, name_contains="nope", retries=0)


def test_find_retries_before_giving_up():
    """Section 7: "target not found / target changed" — a target that
    only appears on a later attempt (the tree still settling) must still
    resolve, not fail on the first empty read."""
    calls = {"count": 0}
    target = FakeUiaElement(name="Prompt")
    bridge = UiaAutomationBridge()
    bridge._root = lambda handle: FakeUiaElement()

    def flaky_descendants(root):
        calls["count"] += 1
        return [target] if calls["count"] >= 2 else []

    bridge._descendants = flaky_descendants
    found = bridge.find(1, name_contains="prompt", retries=2, retry_delay_seconds=0)
    assert found is target


def test_find_name_exact_matches_the_whole_name_case_insensitively():
    target = FakeUiaElement(name="Chat")
    bridge = _bridge_with_elements([target])

    found = bridge.find(1, name_exact="chat", retries=0)
    assert found is target


def test_find_name_exact_does_not_match_a_substring():
    """Found live, this session: 'Chat' as a substring also matches
    'New chat', 'Chats', 'Pin chat' — real sibling names in a real
    application's own UIA tree. `name_exact` must not."""
    decoy = FakeUiaElement(name="New chat")
    bridge = _bridge_with_elements([decoy])

    with pytest.raises(UiaTargetNotFound):
        bridge.find(1, name_exact="chat", retries=0)


def test_find_visible_only_skips_an_offscreen_match():
    """Found live, this session: an inactive tab's own elements can stay
    mounted in the accessibility tree, merely hidden — a plain name match
    cannot tell an off-screen decoy from the one actually on screen."""
    offscreen_decoy = FakeUiaElement(name="New chat", is_offscreen=True)
    onscreen_target = FakeUiaElement(name="New chat", is_offscreen=False)
    bridge = _bridge_with_elements([offscreen_decoy, onscreen_target])

    found = bridge.find(1, name_contains="new chat", visible_only=True, retries=0)
    assert found is onscreen_target


def test_find_visible_only_raises_when_every_match_is_offscreen():
    bridge = _bridge_with_elements([FakeUiaElement(name="New chat", is_offscreen=True)])

    with pytest.raises(UiaTargetNotFound):
        bridge.find(1, name_contains="new chat", visible_only=True, retries=0)


def test_find_without_visible_only_still_returns_an_offscreen_match():
    """Default behavior (`visible_only=False`) is unchanged for every
    existing caller — this is opt-in, not a new default."""
    offscreen_only = FakeUiaElement(name="New chat", is_offscreen=True)
    bridge = _bridge_with_elements([offscreen_only])

    found = bridge.find(1, name_contains="new chat", retries=0)
    assert found is offscreen_only


# ═══════════════════════ find_composer / find_main_content ═══════════════════════


def test_find_composer_picks_the_smallest_bottom_anchored_focusable_text_element():
    """The exact heuristic confirmed live against Claude Desktop's own
    "Prompt" element (44px tall, anchored near the bottom of a ~680px
    window)."""
    history = FakeUiaElement(
        name="History", is_focusable=True, has_text=True, rect=(0, 0, 400, 500),
    )
    composer = FakeUiaElement(
        name="Prompt", is_focusable=True, has_text=True, rect=(0, 636, 400, 680),
    )
    sidebar_button = FakeUiaElement(
        name="Menu", is_focusable=True, has_text=False, rect=(0, 700, 40, 730),
    )
    bridge = _bridge_with_elements([history, sidebar_button, composer], window_rect=(0, 0, 400, 800))

    found = bridge.find_composer(1)
    assert found is composer


def test_find_composer_clips_a_scrollable_composers_content_extent_to_the_window():
    """Real, live-found measurement bug: reproduced against ChatGPT
    Desktop's real composer, genuinely maximized (confirmed via real
    Win32 `is_maximized` state). Its raw `CurrentBoundingRectangle`
    reported the *full scrollable content* extent of an accumulated long
    draft (1280px), extending far past the window's own bottom edge
    (687px tall window) — nearly double the window's own height. Clipped
    to the window's bounds, its true on-screen height was 335px (48.8% of
    the window) — a real, ordinary composer, wrongly rejected before this
    fix because the unclipped rect always exceeded any realistic height
    fraction."""
    composer = FakeUiaElement(
        name="Message ChatGPT", is_focusable=True, has_text=True,
        rect=(0, 345, 400, 1625),  # bottom (1625) far past the window's own 687
    )
    bridge = _bridge_with_elements([composer], window_rect=(0, 0, 400, 687))

    found = bridge.find_composer(1)

    assert found is composer


def test_find_composer_raises_when_nothing_matches():
    bridge = _bridge_with_elements([FakeUiaElement(name="Sidebar", is_focusable=False)])
    with pytest.raises(UiaTargetNotFound):
        bridge.find_composer(1)


def test_find_main_content_picks_the_largest_text_bearing_region():
    small = FakeUiaElement(name="Status", has_text=True, rect=(0, 0, 100, 50))
    large = FakeUiaElement(name="Messages", has_text=True, rect=(0, 0, 400, 600))
    bridge = _bridge_with_elements([small, large])

    found = bridge.find_main_content(1)
    assert found is large


def test_find_composer_skips_an_offscreen_candidate():
    """Same class of bug `find()`'s own `visible_only` guards against,
    now also applied to `find_composer()`: a Chromium/Electron app can
    keep an inactive tab's own composer mounted, merely hidden. An
    offscreen candidate that would otherwise win on geometry must never
    be returned as the on-screen composer."""
    hidden = FakeUiaElement(
        name="Hidden composer", is_focusable=True, has_text=True,
        rect=(0, 636, 400, 660), is_offscreen=True,
    )
    visible = FakeUiaElement(
        name="Prompt", is_focusable=True, has_text=True,
        rect=(0, 636, 400, 680), is_offscreen=False,
    )
    bridge = _bridge_with_elements([hidden, visible], window_rect=(0, 0, 400, 800))

    found = bridge.find_composer(1)

    assert found is visible


def test_find_main_content_skips_an_offscreen_candidate():
    hidden_large = FakeUiaElement(name="Hidden", has_text=True, rect=(0, 0, 400, 900), is_offscreen=True)
    visible = FakeUiaElement(name="Messages", has_text=True, rect=(0, 0, 400, 600), is_offscreen=False)
    bridge = _bridge_with_elements([hidden_large, visible])

    found = bridge.find_main_content(1)

    assert found is visible


# ═══════════════════════ snapshot_text_regions / find_new_content ═══════════════════════


def test_snapshot_text_regions_reads_every_candidates_current_text():
    a = FakeUiaElement(name="A", has_text=True, rect=(0, 0, 400, 300), text="first")
    b = FakeUiaElement(name="B", has_text=True, rect=(0, 300, 400, 600), text="second")
    bridge = _bridge_with_elements([a, b], window_rect=(0, 0, 400, 800))

    snapshot = bridge.snapshot_text_regions(1, min_height=20)

    assert set(snapshot.values()) == {"first", "second"}


def test_find_new_content_ignores_a_region_unchanged_since_the_baseline():
    """The generic fix itself: persistent chrome (a sidebar) that reads
    identically before and after must never be mistaken for a new
    response."""
    sidebar = FakeUiaElement(name="Sidebar", has_text=True, rect=(0, 0, 200, 800), text="Chat 1\nChat 2\nChat 3")
    bridge = _bridge_with_elements([sidebar], window_rect=(0, 0, 400, 800))
    baseline = bridge.snapshot_text_regions(1, min_height=20)

    found = bridge.find_new_content(1, baseline, min_height=20)

    assert found is None


def test_find_new_content_returns_a_region_that_genuinely_changed():
    sidebar = FakeUiaElement(name="Sidebar", has_text=True, rect=(0, 0, 200, 800), text="Chat 1\nChat 2")
    response = FakeUiaElement(name="Response", has_text=True, rect=(200, 0, 400, 100), text="thinking…")
    bridge = _bridge_with_elements([sidebar, response], window_rect=(0, 0, 400, 800))
    baseline = bridge.snapshot_text_regions(1, min_height=20)
    response.set_text("the real, finished answer")

    found = bridge.find_new_content(1, baseline, min_height=20)

    assert found is response


def test_find_new_content_prefers_the_smallest_changed_region():
    """The same "most specific match, not the broadest" preference
    `find_composer()` already applies: a small, precise reply element is
    preferred over a large enclosing pane that also changed because the
    reply was inserted inside it."""
    outer_pane = FakeUiaElement(name="Conversation", has_text=True, rect=(0, 0, 400, 800), text="")
    reply = FakeUiaElement(name="Reply", has_text=True, rect=(0, 700, 400, 750), text="")
    bridge = _bridge_with_elements([outer_pane, reply], window_rect=(0, 0, 400, 800))
    baseline = bridge.snapshot_text_regions(1, min_height=20)
    outer_pane.set_text("prior transcript\n\nthe real answer")
    reply.set_text("the real answer")

    found = bridge.find_new_content(1, baseline, min_height=20)

    assert found is reply


def test_find_new_content_excludes_text_matching_the_prompt():
    """A composer that still visibly holds the just-submitted prompt
    (echoed back, or not yet cleared) must never be mistaken for the
    response."""
    composer = FakeUiaElement(name="Composer", has_text=True, rect=(0, 700, 400, 780), text="")
    bridge = _bridge_with_elements([composer], window_rect=(0, 0, 400, 800))
    baseline = bridge.snapshot_text_regions(1, min_height=20)
    composer.set_text("the submitted prompt")

    found = bridge.find_new_content(1, baseline, exclude_text="the submitted prompt", min_height=20)

    assert found is None


def test_find_new_content_treats_a_brand_new_region_as_changed():
    """A region that did not exist in the baseline at all (a freshly
    inserted message bubble, common when a reply becomes a new DOM node
    rather than mutating an existing one) must still be found."""
    bridge = _bridge_with_elements([], window_rect=(0, 0, 400, 800))
    baseline = bridge.snapshot_text_regions(1, min_height=20)
    assert baseline == {}

    new_reply = FakeUiaElement(name="Reply", has_text=True, rect=(0, 700, 400, 750), text="a brand new answer")
    bridge._descendants = lambda r: [new_reply]

    found = bridge.find_new_content(1, baseline, min_height=20)

    assert found is new_reply


def test_find_new_content_skips_offscreen_regions():
    hidden = FakeUiaElement(name="Hidden", has_text=True, rect=(0, 0, 400, 100), text="", is_offscreen=True)
    bridge = _bridge_with_elements([hidden], window_rect=(0, 0, 400, 800))
    baseline = bridge.snapshot_text_regions(1, min_height=20)
    hidden.set_text("changed but never visible")

    found = bridge.find_new_content(1, baseline, min_height=20)

    assert found is None


def test_find_new_content_skips_the_composers_own_placeholder_text():
    """Real, live-found false positive: reproduced against ChatGPT
    Desktop. Right after a real submission, the composer's own
    empty-state placeholder ("Message ChatGPT") reads as "changed" (the
    submitted prompt was just cleared out of it), is short enough to win
    as the smallest changed region, and — being static — immediately
    passes `_await_response()`'s stability check too, all before any real
    reply had appeared. A composer is always keyboard-focusable (that is
    what makes it a composer, not content, per `find_composer()`'s own
    heuristic); excluding focusable candidates is what keeps the input
    box itself from ever being mistaken for the response."""
    composer = FakeUiaElement(
        name="Composer", has_text=True, is_focusable=True,
        rect=(0, 700, 400, 780), text="the submitted prompt",
    )
    bridge = _bridge_with_elements([composer], window_rect=(0, 0, 400, 800))
    baseline = bridge.snapshot_text_regions(1, min_height=20)
    assert baseline == {}  # the composer itself was never a candidate to begin with
    composer.set_text("Message ChatGPT")  # cleared back to its own placeholder

    found = bridge.find_new_content(1, baseline, min_height=20)

    assert found is None


def test_find_new_content_default_min_height_catches_a_short_single_line_reply():
    """Real, live-found bug in the fix's own first draft: a genuine,
    short reply — confirmed live against ChatGPT Desktop, the exact text
    "KALPAVRIKSHA_CHATGPT_FINAL_OK" — clipped to 19px tall, narrowly
    missing an untested 20px default `min_height` and silently excluding
    the real response from ever being considered a candidate at all,
    causing a live run to time out despite the response being visibly
    present on screen the whole time. Uses the *default* `min_height`
    deliberately (no override), to pin the real default, not just the
    logic."""
    reply = FakeUiaElement(name="Reply", has_text=True, rect=(0, 244, 400, 263), text="")  # 19px tall
    bridge = _bridge_with_elements([reply], window_rect=(0, 0, 400, 800))
    baseline = bridge.snapshot_text_regions(1)
    reply.set_text("KALPAVRIKSHA_CHATGPT_FINAL_OK")

    found = bridge.find_new_content(1, baseline)

    assert found is reply


# ═══════════════════════ find_new_content: persistent, multi-turn conversations ═══════════════════════


def test_find_new_content_returns_the_current_calls_response_not_an_older_one():
    """The mission's own required scenario: given an existing
    conversation already containing 'CALL1_RESPONSE', and a new request
    that produces 'CALL2_RESPONSE', the resolver must return
    'CALL2_RESPONSE', never 'CALL1_RESPONSE'."""
    old_reply = FakeUiaElement(name="Reply1", has_text=True, rect=(0, 100, 400, 130), text="CALL1_RESPONSE")
    bridge = _bridge_with_elements([old_reply], window_rect=(0, 0, 400, 800))
    baseline = bridge.snapshot_text_regions(1, min_height=20)

    new_reply = FakeUiaElement(name="Reply2", has_text=True, rect=(0, 400, 400, 430), text="CALL2_RESPONSE")
    bridge._descendants = lambda r: [old_reply, new_reply]

    found = bridge.find_new_content(1, baseline, min_height=20)

    assert found is new_reply
    assert bridge.read_text(found) == "CALL2_RESPONSE"


def test_find_new_content_excludes_an_old_response_even_if_its_position_shifted():
    """The exact real bug this fix closes: confirmed live against
    ChatGPT Desktop's own reused, growing 'Kalpavriksha Reasoning'
    conversation — an older reply's on-screen position shifted slightly
    between the baseline snapshot and the after-submission poll (new
    content appended below it), so a *position*-keyed comparison no
    longer matched it against its own baseline entry and wrongly treated
    it as new. Comparing by text content, regardless of position, must
    still exclude it."""
    old_reply = FakeUiaElement(name="Reply1", has_text=True, rect=(0, 100, 400, 130), text="CALL1_RESPONSE")
    bridge = _bridge_with_elements([old_reply], window_rect=(0, 0, 400, 800))
    baseline = bridge.snapshot_text_regions(1, min_height=20)

    # Simulate the live-found drift: the same logical message now
    # resolves to a *different* bounding rectangle (shifted down by new
    # content appended above it), while its text is unchanged.
    old_reply.CurrentBoundingRectangle = _Rect(0, 250, 400, 280)
    new_reply = FakeUiaElement(name="Reply2", has_text=True, rect=(0, 400, 400, 430), text="CALL2_RESPONSE")
    bridge._descendants = lambda r: [old_reply, new_reply]

    found = bridge.find_new_content(1, baseline, min_height=20)

    assert found is new_reply


def test_find_new_content_excludes_multiple_old_matching_responses():
    """Given several old exchanges already in a long-lived, reused
    conversation, all must be excluded — not just the most recent one —
    and the genuinely new reply still found."""
    old1 = FakeUiaElement(name="Reply1", has_text=True, rect=(0, 100, 400, 130), text="CALL1_RESPONSE")
    old2 = FakeUiaElement(name="Reply2", has_text=True, rect=(0, 200, 400, 230), text="CALL2_RESPONSE")
    old3 = FakeUiaElement(name="Reply3", has_text=True, rect=(0, 300, 400, 330), text="CALL3_RESPONSE")
    bridge = _bridge_with_elements([old1, old2, old3], window_rect=(0, 0, 400, 800))
    baseline = bridge.snapshot_text_regions(1, min_height=20)

    new_reply = FakeUiaElement(name="Reply4", has_text=True, rect=(0, 400, 400, 430), text="CALL4_RESPONSE")
    bridge._descendants = lambda r: [old1, old2, old3, new_reply]

    found = bridge.find_new_content(1, baseline, min_height=20)

    assert found is new_reply


def test_find_new_content_excludes_an_old_response_that_was_offscreen_at_baseline_time():
    """A second, separate real bug this fix closes, confirmed live
    against ChatGPT Desktop's own reused, growing 'Kalpavriksha
    Reasoning' conversation: an even older reply had scrolled entirely
    off-screen at the moment `baseline` was captured — never recorded in
    it at all — then scrolled back into view during a *later* poll.
    Content-set comparison alone cannot exclude something baseline never
    saw in the first place; the prompt-anchored floor does, since the
    old reply's position is above the current request's own echoed
    prompt."""
    old_reply_hidden = FakeUiaElement(
        name="OldReply", has_text=True, rect=(0, 50, 400, 80), text="OLD_STALE_RESPONSE", is_offscreen=True,
    )
    bridge = _bridge_with_elements([old_reply_hidden], window_rect=(0, 0, 400, 800))
    baseline = bridge.snapshot_text_regions(1, min_height=20)
    assert baseline == {}  # confirmed: never captured, it was off-screen

    old_reply_visible = FakeUiaElement(
        name="OldReply", has_text=True, rect=(0, 50, 400, 80), text="OLD_STALE_RESPONSE", is_offscreen=False,
    )
    prompt_echo = FakeUiaElement(name="PromptEcho", has_text=True, rect=(0, 300, 400, 330), text="the submitted prompt")
    new_reply = FakeUiaElement(name="NewReply", has_text=True, rect=(0, 400, 400, 430), text="THE_REAL_NEW_RESPONSE")
    bridge._descendants = lambda r: [old_reply_visible, prompt_echo, new_reply]

    found = bridge.find_new_content(1, baseline, exclude_text="the submitted prompt", min_height=20)

    assert found is new_reply


def test_find_new_content_without_a_locatable_prompt_echo_still_excludes_baseline_text():
    """Best-effort: if the just-submitted prompt cannot be located
    anywhere in the window (an empty `exclude_text`, or the composer has
    not yet visibly cleared into the transcript), the positional floor
    defaults to the window's own top edge rather than blocking
    everything — the content-set comparison alone remains in force."""
    old_reply = FakeUiaElement(name="OldReply", has_text=True, rect=(0, 100, 400, 130), text="OLD_RESPONSE")
    bridge = _bridge_with_elements([old_reply], window_rect=(0, 0, 400, 800))
    baseline = bridge.snapshot_text_regions(1, min_height=20)

    new_reply = FakeUiaElement(name="NewReply", has_text=True, rect=(0, 400, 400, 430), text="NEW_RESPONSE")
    bridge._descendants = lambda r: [old_reply, new_reply]

    found = bridge.find_new_content(1, baseline, exclude_text="", min_height=20)

    assert found is new_reply


# ═══════════════════════ write_text ═══════════════════════


def test_write_text_uses_value_pattern_when_writable():
    element = FakeUiaElement(has_value=True, has_text=True, read_only=False)
    bridge = UiaAutomationBridge()
    keyboard = FakeKeyboard()

    ok = bridge.write_text(element, "hello", keyboard)

    assert ok is True
    assert element._value == "hello"
    assert keyboard.typed == []  # ValuePattern path never touches the keyboard


def test_write_text_falls_back_to_keystrokes_when_value_pattern_silently_no_ops():
    """Real, live-found bug: reproduced against Kimi Desktop's real
    composer. `ValuePattern.CurrentIsReadOnly` reported `False` (a
    genuinely writable pattern — not the read-only case above) and
    `SetValue()` raised no exception at all, yet the composer's content
    was provably unchanged afterward. The prior code trusted "no
    exception" as "it worked" and returned the resulting (correctly
    negative) verification as final failure — never trying the keystroke
    path, which was independently confirmed, live, to work reliably on
    this exact composer. `write_text()` must fall through instead."""
    element = FakeUiaElement(has_value=True, has_text=True, read_only=False)
    element._text = ""
    # Simulate the live-found no-op: SetValue() is called, raises
    # nothing, but never actually updates the element's content.
    original_set_value = _FakeValuePattern.SetValue
    _FakeValuePattern.SetValue = lambda self, value: None
    try:
        bridge = UiaAutomationBridge()
        keyboard = FakeKeyboard()
        keyboard.type = lambda text: setattr(element, "_text", element._text + text)

        ok = bridge.write_text(element, "hello", keyboard)

        assert ok is True
        assert element._text == "hello"
        assert keyboard.hotkeys == [("ctrl", "a")]  # fell through to the keystroke path
    finally:
        _FakeValuePattern.SetValue = original_set_value


def test_write_text_tolerates_a_composers_own_fixed_label_around_the_value():
    """Real, live-found bug: reproduced against Kimi Desktop's real
    composer (its own generic 'New Task' control — the only 'start fresh'
    affordance it exposes at all, confirmed live; there is no separate
    'New Chat' button). That composer's `TextPattern.DocumentRange`
    reports a fixed, non-editable label ('Ask me. Task me.') as part of
    the *same* text range as the real, editable content it wraps. A write
    that genuinely landed correctly then failed exact-match verification
    (the prior `readback == expected_norm` check for a full overwrite)
    because the readback carried this extra chrome the write itself never
    put there and cannot remove. Verification must tolerate fixed
    decoration a composer's own accessibility tree bakes in, the same way
    it already tolerates blank-line reflow below."""
    element = FakeUiaElement(has_value=True, has_text=True, read_only=True)
    element._text = "Ask me. Task me.some old draft"
    bridge = UiaAutomationBridge()
    keyboard = FakeKeyboard()
    # Simulate a real clear: selects and removes only the editable
    # content, leaving the composer's own fixed label behind — exactly
    # what was observed live (clear genuinely worked; only verification
    # was wrong).
    keyboard.press = lambda key: setattr(element, "_text", "Ask me. Task me.") if key == "delete" else None
    keyboard.type = lambda text: setattr(element, "_text", element._text + text)

    ok = bridge.write_text(element, "hello", keyboard, append=False)

    assert ok is True
    assert element._text == "Ask me. Task me.hello"


def test_write_text_falls_back_to_keystrokes_when_value_pattern_is_read_only():
    element = FakeUiaElement(has_value=True, has_text=True, read_only=True)
    element._text = ""
    bridge = UiaAutomationBridge()
    keyboard = FakeKeyboard()
    keyboard.type = lambda text: setattr(element, "_text", element._text + text)  # simulate real typing

    ok = bridge.write_text(element, "hello", keyboard)

    assert ok is True
    assert element.focused is True
    assert keyboard.hotkeys == [("ctrl", "a")]  # cleared before typing (append=False default)


def test_write_text_tolerates_a_rich_text_composers_blank_line_collapse():
    """Found live: pasting the real ~6KB planning prompt into Claude
    Desktop's composer came back with every blank line (`\\n\\n`, a
    paragraph break) collapsed to a single `\\n` — the composer's own
    Ctrl-V paste normalization, not data loss. Verification must accept
    this specific, legitimate difference while still catching a genuine
    mismatch (asserted by the sibling test below)."""
    element = FakeUiaElement(has_value=True, has_text=True, read_only=True)
    element._text = ""
    bridge = UiaAutomationBridge()
    keyboard = FakeKeyboard()
    sent = "first paragraph\n\nsecond paragraph\n\nthird paragraph"
    landed = "first paragraph\nsecond paragraph\nthird paragraph"  # composer's own normalization
    # Text containing a newline now always routes through `paste()`, not
    # `type()` — a literal typed newline is ambiguous across composers
    # (see `write_text()`'s own finding); paste carries no such ambiguity.
    def fake_paste(text=None):
        keyboard.pasted.append(text)
        element._text = landed

    keyboard.paste = fake_paste

    ok = bridge.write_text(element, sent, keyboard)

    assert ok is True
    assert keyboard.typed == []
    assert keyboard.pasted == [sent]


def test_write_text_still_reports_a_genuine_mismatch():
    element = FakeUiaElement(has_value=True, has_text=True, read_only=True)
    element._text = ""
    bridge = UiaAutomationBridge()
    keyboard = FakeKeyboard()
    keyboard.type = lambda text: setattr(element, "_text", "completely different content")

    ok = bridge.write_text(element, "what was actually sent", keyboard)

    assert ok is False


def test_write_text_pastes_instead_of_typing_when_text_is_long():
    """Found live: a real ~6KB reasoning prompt typed character-by-character
    via `SendInput` failed read-back verification across every desktop
    composer tried. Long text must go through `keyboard.paste()` (clipboard
    write + Ctrl-V, a single event) instead of `keyboard.type()`."""
    from master_agent.desktop.execution.uia_control import _PASTE_THRESHOLD_CHARS

    long_text = "x" * (_PASTE_THRESHOLD_CHARS + 1)
    element = FakeUiaElement(has_value=True, has_text=True, read_only=True)
    element._text = ""
    bridge = UiaAutomationBridge()
    keyboard = FakeKeyboard()
    keyboard.paste = lambda text=None: (setattr(element, "_text", text), keyboard.pasted.append(text))

    ok = bridge.write_text(element, long_text, keyboard)

    assert ok is True
    assert keyboard.typed == []
    assert keyboard.pasted == [long_text]


def test_write_text_pastes_short_text_containing_a_newline():
    """The real, live-found root cause of a Kimi Desktop acceptance
    failure: a short prompt (well under the paste-length threshold) that
    contains a blank-line separator — Kalpavriksha's own session-marker
    prefix always includes one — went through `keyboard.type()` and the
    `\\n\\n` vanished *entirely*, not merely collapsed the way pasted
    whitespace already legitimately does. A literal typed newline is
    ambiguous across composers; paste carries no such ambiguity regardless
    of overall text length."""
    from master_agent.desktop.execution.uia_control import _PASTE_THRESHOLD_CHARS

    short_text_with_newline = "[marker]\n\nactual prompt"
    assert len(short_text_with_newline) < _PASTE_THRESHOLD_CHARS  # sanity: genuinely short
    element = FakeUiaElement(has_value=True, has_text=True, read_only=True)
    element._text = ""
    bridge = UiaAutomationBridge()
    keyboard = FakeKeyboard()
    keyboard.paste = lambda text=None: (setattr(element, "_text", text), keyboard.pasted.append(text))

    ok = bridge.write_text(element, short_text_with_newline, keyboard)

    assert ok is True
    assert keyboard.typed == []
    assert keyboard.pasted == [short_text_with_newline]


def test_write_text_still_types_short_text_without_a_newline():
    """The paste-for-newline fix must not widen beyond its own real
    finding — genuinely short, single-line text keeps typing."""
    element = FakeUiaElement(has_value=True, has_text=True, read_only=True)
    element._text = ""
    bridge = UiaAutomationBridge()
    keyboard = FakeKeyboard()
    keyboard.type = lambda text: (setattr(element, "_text", text), keyboard.typed.append(text))

    ok = bridge.write_text(element, "a short single-line prompt", keyboard)

    assert ok is True
    assert keyboard.pasted == []
    assert keyboard.typed == ["a short single-line prompt"]


def test_write_text_still_types_short_text():
    element = FakeUiaElement(has_value=True, has_text=True, read_only=True)
    element._text = ""
    bridge = UiaAutomationBridge()
    keyboard = FakeKeyboard()

    def fake_type(text):
        keyboard.typed.append(text)
        element._text += text

    keyboard.type = fake_type

    ok = bridge.write_text(element, "short prompt", keyboard)

    assert ok is True
    assert keyboard.pasted == []
    assert keyboard.typed == ["short prompt"]


def test_write_text_replace_clears_existing_content_first():
    """The exact bug found live: typing without clearing first appends
    at the cursor instead of replacing — leftover text from an earlier
    action silently doubled up."""
    element = FakeUiaElement(has_value=False, has_text=True)
    element._text = "leftover from a previous run"
    bridge = UiaAutomationBridge()
    keyboard = FakeKeyboard()

    def fake_type(text):
        element._text += text  # a real keyboard only ever appends at the cursor

    def fake_press(key):
        keyboard.pressed.append(key)
        if key == "delete":  # select-all (ctrl+a) then delete clears the field
            element._text = ""

    keyboard.type = fake_type
    keyboard.press = fake_press

    ok = bridge.write_text(element, "fresh text", keyboard, append=False)

    assert keyboard.hotkeys == [("ctrl", "a")]
    assert keyboard.pressed == ["delete"]
    assert ok is True


def test_write_text_append_does_not_clear_first():
    element = FakeUiaElement(has_value=False, has_text=True)
    element._text = "existing "
    bridge = UiaAutomationBridge()
    keyboard = FakeKeyboard()
    keyboard.type = lambda text: setattr(element, "_text", element._text + text)

    ok = bridge.write_text(element, "appended", keyboard, append=True)

    assert keyboard.hotkeys == []
    assert element._text == "existing appended"
    assert ok is True


def test_write_text_retries_the_readback_before_reporting_a_mismatch():
    """Found live against ChatGPT Desktop (a validation mission, not
    ChatGPT-specific code): a `SetValue()` that demonstrably succeeded
    still failed verification on the *first* immediate read-back —
    Chromium's DOM-to-accessibility-tree sync is asynchronous and settles
    at different speeds per application. This generic retry benefits
    every UIA-backed write, not one application."""
    element = FakeUiaElement(has_value=True, has_text=True, read_only=False)
    bridge = UiaAutomationBridge()
    keyboard = FakeKeyboard()

    # The real SetValue lands correctly, but reads stale for the first
    # two reads (simulating the async settle Chromium exhibited live).
    reads_before_settled = {"count": 0}
    original_read_text = bridge.read_text

    def flaky_read_text(el):
        reads_before_settled["count"] += 1
        if reads_before_settled["count"] <= 2:
            return "stale"
        return original_read_text(el)

    bridge.read_text = flaky_read_text
    ok = bridge.write_text(element, "hello", keyboard)

    assert ok is True
    assert reads_before_settled["count"] == 3  # two stale reads, then the real one


def test_write_text_reports_false_on_a_genuine_mismatch():
    element = FakeUiaElement(has_value=True, has_text=True, read_only=False)
    bridge = UiaAutomationBridge()
    keyboard = FakeKeyboard()

    # Simulate a write that silently lands wrong (element ignores the value).
    original_set_value = _FakeValuePattern.SetValue
    _FakeValuePattern.SetValue = lambda self, value: None
    try:
        ok = bridge.write_text(element, "hello", keyboard)
    finally:
        _FakeValuePattern.SetValue = original_set_value

    assert ok is False


# ═══════════════════ verified clear (Kimi Desktop live finding) ═══════════
#
# Reproduced live, this session: the clear step's own `ctrl+a`+`delete` API
# calls "succeeding" (no exception) was never evidence the composer was
# actually emptied — content stayed byte-for-byte identical through
# `SetFocus()`, `ctrl+a`, `delete`, and 800ms afterward against a real
# application. These tests cover the generic fix: bounded, read-back-based
# clear verification with a bounded retry of the clear action itself, and a
# fail-closed return (never typing) when the composer cannot be positively
# confirmed empty.


def test_write_text_clear_succeeds_and_readback_becomes_empty():
    """Mission item 1: clear succeeds, read-back confirms empty, write
    proceeds normally."""
    element = FakeUiaElement(has_value=False, has_text=True)
    element._text = "leftover from a previous run"
    bridge = UiaAutomationBridge()
    keyboard = FakeKeyboard()
    keyboard.type = lambda text: setattr(element, "_text", element._text + text)

    def fake_press(key):
        keyboard.pressed.append(key)
        if key == "delete":
            element._text = ""

    keyboard.press = fake_press

    ok = bridge.write_text(element, "fresh text", keyboard, append=False)

    assert ok is True
    assert element._text == "fresh text"


def test_write_text_clear_stale_then_settles_via_bounded_retry():
    """Mission item 2: the clear API call 'succeeds', but the read-back
    stays stale for a couple of reads before genuinely reflecting the
    clear — the same asynchronous-settle behavior already proven for the
    write side, now also tolerated on the clear side."""
    element = FakeUiaElement(has_value=False, has_text=True)
    element._text = "leftover from a previous run"
    bridge = UiaAutomationBridge()
    keyboard = FakeKeyboard()
    keyboard.type = lambda text: setattr(element, "_text", element._text + text)

    reads = {"count": 0}
    original_read_text = bridge.read_text

    def flaky_read_text(el):
        reads["count"] += 1
        # First delete's own read-back stays stale for a couple of polls,
        # then genuinely reflects empty -- no second `ctrl+a`+`delete`
        # attempt should be needed, matching "bounded retry succeeds".
        if reads["count"] <= 2:
            return "leftover from a previous run"
        return original_read_text(el)

    bridge.read_text = flaky_read_text

    def fake_press(key):
        keyboard.pressed.append(key)
        if key == "delete":
            element._text = ""

    keyboard.press = fake_press

    ok = bridge.write_text(element, "fresh text", keyboard, append=False)

    assert ok is True
    # Exactly one `ctrl+a`+`delete` cycle — the bounded *verify* retry
    # absorbed the staleness, not a second clear *action*.
    assert keyboard.pressed.count("delete") == 1


def test_write_text_clear_never_empties_fails_closed_without_typing():
    """Mission item 3: the composer never becomes confirmed-empty within
    the bounded window, even after retrying the clear action itself —
    `write_text` must fail closed and must NEVER call `type`/`paste`,
    since typing into unverified stale content is exactly the real,
    live-found bug this fix exists to prevent."""
    element = FakeUiaElement(has_value=False, has_text=True)
    element._text = "leftover from a previous run" * 5  # well over the threshold
    bridge = UiaAutomationBridge()
    keyboard = FakeKeyboard()
    # `delete` never actually clears anything -- the exact live-found failure.

    ok = bridge.write_text(element, "fresh text", keyboard, append=False)

    assert ok is False
    assert keyboard.typed == []
    assert keyboard.pasted == []
    # The clear action was retried within its own bounded ceiling, not
    # attempted once and given up on, and not retried forever.
    assert keyboard.pressed.count("delete") >= 2


def test_write_text_focus_is_reconfirmed_via_generic_uia_primitives():
    """Mission's own 'Focus' requirement: independently verify the
    composer is still the active target where the existing primitives
    permit it. Exercised via the real `_verify_focus()` path with a fake
    `IUIAutomation` instance — `GetFocusedElement`/`CompareElements` are
    generic UIA methods, not anything application-specific."""
    element = FakeUiaElement(has_value=False, has_text=True)
    element._text = ""
    bridge = UiaAutomationBridge()
    keyboard = FakeKeyboard()
    keyboard.type = lambda text: setattr(element, "_text", element._text + text)

    class FakeAutomation:
        def __init__(self):
            self.compare_calls = 0

        def GetFocusedElement(self):
            return object()

        def CompareElements(self, a, b):
            self.compare_calls += 1
            # Not focused on the first check, focused from the second
            # check onward -- proves SetFocus() is retried, not just
            # called once and trusted.
            return self.compare_calls >= 2

    fake_automation = FakeAutomation()
    bridge._instance = lambda: fake_automation

    ok = bridge.write_text(element, "hello", keyboard, append=False)

    assert ok is True
    assert fake_automation.compare_calls >= 2


def test_write_text_focus_verification_is_inconclusive_not_blocking():
    """When the comparison mechanism itself is unavailable (a real,
    live-found scenario for some applications/controls), `write_text`
    must still proceed rather than treat an inconclusive result as a
    failure -- best-effort, never the only gate."""
    element = FakeUiaElement(has_value=False, has_text=True)
    element._text = ""
    bridge = UiaAutomationBridge()
    keyboard = FakeKeyboard()
    keyboard.type = lambda text: setattr(element, "_text", element._text + text)

    class ExplodingAutomation:
        def GetFocusedElement(self):
            raise RuntimeError("this application does not support it")

    bridge._instance = lambda: ExplodingAutomation()

    ok = bridge.write_text(element, "hello", keyboard, append=False)

    assert ok is True


def test_get_focused_element_in_window_returns_a_focused_element_belonging_to_the_window():
    member = FakeUiaElement(name="Inline rename field")
    bridge = _bridge_with_elements([member], window_rect=(0, 0, 400, 800))

    class FakeAutomation:
        def GetFocusedElement(self):
            return member

        def CompareElements(self, a, b):
            return a is b

    bridge._instance = lambda: FakeAutomation()

    found = bridge.get_focused_element_in_window(1)

    assert found is member


def test_get_focused_element_in_window_refuses_focus_from_another_window():
    """Real, live-found risk this guards against: a different
    application can hold real OS keyboard focus at the exact moment
    this is called (this session's own development environment,
    running a concurrent coding-agent GUI, reproduced exactly this).
    The focused element must be positively confirmed to belong to the
    target window, never assumed."""
    unrelated_element = object()
    member = FakeUiaElement(name="Inline rename field")
    bridge = _bridge_with_elements([member], window_rect=(0, 0, 400, 800))

    class FakeAutomation:
        def GetFocusedElement(self):
            return unrelated_element

        def CompareElements(self, a, b):
            return a is b

    bridge._instance = lambda: FakeAutomation()

    with pytest.raises(UiaTargetNotFound):
        bridge.get_focused_element_in_window(1)


def test_get_focused_element_in_window_raises_when_nothing_is_focused():
    bridge = _bridge_with_elements([], window_rect=(0, 0, 400, 800))

    class FakeAutomation:
        def GetFocusedElement(self):
            return None

        def CompareElements(self, a, b):
            return a is b

    bridge._instance = lambda: FakeAutomation()

    with pytest.raises(UiaTargetNotFound):
        bridge.get_focused_element_in_window(1)


def test_write_text_short_unchanged_leftover_content_is_not_mistaken_for_cleared():
    """The precise real bug found live, this session, immediately after
    fixing the original 'no verification at all' gap: real leftover
    content from an earlier attempt can itself happen to be short — a
    length-only freshness check passes by pure coincidence even though
    `ctrl+a`+`delete` silently did nothing. Comparing against the
    pre-clear baseline catches exactly this: unchanged and non-empty is
    not verified, no matter how short."""
    element = FakeUiaElement(has_value=False, has_text=True)
    element._text = "short leftover"  # short -- would pass a length-only check
    bridge = UiaAutomationBridge()
    keyboard = FakeKeyboard()
    # `delete` never actually changes anything -- the exact live-found bug.

    ok = bridge.write_text(element, "fresh text", keyboard, append=False)

    assert ok is False
    assert keyboard.typed == []
    assert keyboard.pasted == []


def test_write_text_short_content_that_genuinely_changes_is_verified_cleared():
    """The positive case for the same fix: short content that *does*
    change (a real placeholder replacing real leftover text, for example)
    is correctly accepted — the fix only rejects *unchanged* short
    content, not short content generally."""
    element = FakeUiaElement(has_value=False, has_text=True)
    element._text = "short leftover"
    bridge = UiaAutomationBridge()
    keyboard = FakeKeyboard()
    # Real typing into a genuinely-cleared, refocused field replaces, not
    # appends -- matching how a real contenteditable behaves once clear
    # has actually taken effect.
    keyboard.type = lambda text: setattr(element, "_text", text)

    def fake_press(key):
        keyboard.pressed.append(key)
        if key == "delete":
            element._text = "Ask anything"  # a genuine, different placeholder

    keyboard.press = fake_press

    ok = bridge.write_text(element, "fresh text", keyboard, append=False)

    assert ok is True


def test_write_text_already_empty_before_clear_is_trivially_verified():
    """A composer that was already empty before `write_text()` was even
    called needs no real change to be verified — 'unchanged' only matters
    when there was something real to change away from."""
    element = FakeUiaElement(has_value=False, has_text=True)
    element._text = ""
    bridge = UiaAutomationBridge()
    keyboard = FakeKeyboard()
    keyboard.type = lambda text: setattr(element, "_text", element._text + text)
    # `delete` does nothing further -- there was nothing to clear.

    ok = bridge.write_text(element, "fresh text", keyboard, append=False)

    assert ok is True


def test_write_text_falls_back_to_a_real_click_when_uia_focus_never_confirms():
    """Found live, this session: UIA's own notion of focus and real Win32
    keyboard input focus can diverge, immediately after a session-
    establishment sequence that clicked elsewhere in the window. When a
    `mouse` controller is given and UIA-level focus is never positively
    confirmed, one real, geometry-derived click at the element's own
    bounding-rect center is the generic, last-resort fallback -- the same
    mechanism `click()` itself already uses."""
    element = FakeUiaElement(has_value=False, has_text=True, rect=(100, 200, 300, 240))
    element._text = ""
    bridge = UiaAutomationBridge()
    keyboard = FakeKeyboard()
    keyboard.type = lambda text: setattr(element, "_text", element._text + text)

    class NeverFocusedAutomation:
        def GetFocusedElement(self):
            return object()

        def CompareElements(self, a, b):
            return False  # never matches, no matter how many times SetFocus() is retried

    bridge._instance = lambda: NeverFocusedAutomation()

    mouse = FakeMouse()
    ok = bridge.write_text(element, "hello", keyboard, append=False, mouse=mouse)

    assert ok is True
    assert mouse.clicks == [(200, 220)]  # the element's own reported center


def test_write_text_without_a_mouse_still_proceeds_when_focus_never_confirms():
    """`mouse` is optional -- a caller that does not pass one (matching
    every caller before this fix) keeps today's best-effort-only
    behavior, never a new hard requirement."""
    element = FakeUiaElement(has_value=False, has_text=True)
    element._text = ""
    bridge = UiaAutomationBridge()
    keyboard = FakeKeyboard()
    keyboard.type = lambda text: setattr(element, "_text", element._text + text)

    class NeverFocusedAutomation:
        def GetFocusedElement(self):
            return object()

        def CompareElements(self, a, b):
            return False

    bridge._instance = lambda: NeverFocusedAutomation()

    ok = bridge.write_text(element, "hello", keyboard, append=False)

    assert ok is True


# ═══════════════════════ click ═══════════════════════


def test_click_uses_invoke_pattern_when_available():
    element = FakeUiaElement(invokable=True)
    element._invoked = False
    bridge = UiaAutomationBridge()
    mouse = FakeMouse()

    ok = bridge.click(element, mouse)

    assert ok is True
    assert element._invoked is True
    assert mouse.clicks == []  # never falls back to a coordinate click


def test_click_falls_back_to_the_elements_own_bounding_rect_center():
    element = FakeUiaElement(invokable=False, rect=(100, 200, 300, 240))
    bridge = UiaAutomationBridge()
    mouse = FakeMouse()

    ok = bridge.click(element, mouse)

    assert ok is True
    assert mouse.clicks == [(200, 220)]  # the element's own reported center, not a guess
