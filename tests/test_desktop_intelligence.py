"""Desktop Intelligence — deterministic (Level 1) tests for
`desktop/intelligence/` (`DesktopObservation`, `capture_evidence()`,
semantic classification, App Knowledge consultation, and the read-only
`desktop_observe` action).

No real UIA/COM traversal happens here — `capture_evidence()` is
exercised against a duck-typed `FakeBridge` exposing exactly the
read-only surface `UiaAutomationBridge` provides, the same pattern
`test_desktop_uia.py`/`test_app_knowledge_acquisition.py` already
establish. Two independent guards prove this layer cannot mutate
anything: (1) `FakeBridge.write_text()`/`.click()` raise `AssertionError`
the instant either is called, and (2) a structural AST scan of every
module under `desktop/intelligence/` confirms no mutating identifier is
even referenced in source.
"""
from __future__ import annotations

import ast
from datetime import UTC, datetime
from pathlib import Path

import pytest

from master_agent.app_knowledge.catalog import CHATGPT_DESKTOP
from master_agent.app_knowledge.profile import KnowledgeType
from master_agent.desktop.execution.backends import WindowInfo
from master_agent.desktop.execution.uia_control import (
    CONTROL_TYPE_BUTTON,
    CONTROL_TYPE_TAB_ITEM,
    UiaElementSnapshot,
    UiaTargetNotFound,
    UiaUnavailable,
)
from master_agent.desktop.intelligence.app_knowledge_bridge import resolve_app_knowledge
from master_agent.desktop.intelligence.evidence import capture_evidence
from master_agent.desktop.intelligence.models import SemanticRole, WindowState
from master_agent.desktop.intelligence.screenshot import (
    ScreenshotUnavailable,
    capture_screenshot,
)

PACKAGE = (
    Path(__file__).resolve().parent.parent
    / "src" / "master_agent" / "desktop" / "intelligence"
)

T0 = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)


# ═══════════════════════ fakes — no real backend anywhere ═══════════════


class _FakeRect:
    def __init__(self, bounds):
        self.left, self.top, self.right, self.bottom = bounds


class _FakeRawElement:
    """Stands in for a raw `IUIAutomationElement` COM object — the only
    attribute `capture_evidence()` ever reads off one of these directly
    is its own bounding rectangle (see `evidence._bounds_of()`)."""

    def __init__(self, bounds):
        self.CurrentBoundingRectangle = _FakeRect(bounds)


class FakeBridge:
    """Duck-typed stand-in for `UiaAutomationBridge`'s read-only surface.
    `write_text`/`click` raise `AssertionError` the instant either is
    called — the structural regression guard mirroring
    `app_knowledge/acquisition.py`'s own `ReadOnlyFakeBridge`."""

    def __init__(
        self, *,
        window_bounds=(0, 0, 1000, 800),
        elements=(),
        composer_bounds=None,
        main_content_bounds=None,
        new_content_bounds=None,
        focused_bounds=None,
        raise_on_window_bounds=False,
        raise_on_snapshot=False,
    ):
        self._window_bounds = window_bounds
        self._elements = elements
        self._composer_bounds = composer_bounds
        self._main_content_bounds = main_content_bounds
        self._new_content_bounds = new_content_bounds
        self._focused_bounds = focused_bounds
        self._raise_on_window_bounds = raise_on_window_bounds
        self._raise_on_snapshot = raise_on_snapshot

    def window_bounds(self, handle):
        if self._raise_on_window_bounds:
            raise UiaTargetNotFound("window has no bounding rectangle")
        return self._window_bounds

    def snapshot_elements(self, handle):
        if self._raise_on_snapshot:
            raise UiaUnavailable("UIA is unreachable")
        return self._elements

    def find_composer(self, handle):
        if self._composer_bounds is None:
            raise UiaTargetNotFound("no composer-shaped element found")
        return _FakeRawElement(self._composer_bounds)

    def find_main_content(self, handle):
        if self._main_content_bounds is None:
            raise UiaTargetNotFound("no text-bearing content region found")
        return _FakeRawElement(self._main_content_bounds)

    def find_new_content(self, handle, baseline, exclude_text="", min_height=8):
        if self._new_content_bounds is None:
            return None
        return _FakeRawElement(self._new_content_bounds)

    def get_focused_element_in_window(self, handle):
        if self._focused_bounds is None:
            raise UiaTargetNotFound("no element currently has focus in this window")
        return _FakeRawElement(self._focused_bounds)

    # ---- mutating methods -- must NEVER be called by this layer ----------

    def write_text(self, *args, **kwargs):
        raise AssertionError("Desktop Intelligence must never call write_text()")

    def click(self, *args, **kwargs):
        raise AssertionError("Desktop Intelligence must never call click()")


def snap(
    *, name="", automation_id="", control_type=50026, is_enabled=True, is_focusable=False,
    is_offscreen=False, is_selected=None, is_modal=None, has_value=False, has_text=False,
    bounds=(0, 0, 10, 10), text=None,
) -> UiaElementSnapshot:
    return UiaElementSnapshot(
        name=name, automation_id=automation_id, control_type=control_type,
        is_enabled=is_enabled, is_focusable=is_focusable, is_offscreen=is_offscreen,
        is_selected=is_selected, is_modal=is_modal,
        has_value_pattern=has_value, has_text_pattern=has_text,
        bounds=bounds, text=text,
    )


def window(handle=1, title="Kalpavriksha Reasoning", process_id=100, maximized=True, minimized=False):
    return WindowInfo(
        handle=handle, title=title, process_id=process_id,
        is_visible=True, is_minimized=minimized, is_maximized=maximized,
    )


# ═══════════════════════════════ Part G tests ═══════════════════════════


class TestCleanObservation:
    """1. Clean observation — a normal window with a mix of element
    kinds produces a fully-populated, correctly-shaped DesktopObservation."""

    def test_observes_window_identity_and_elements(self):
        elements = (
            snap(name="Message ChatGPT", is_focusable=True, has_text=True, bounds=(100, 500, 900, 560)),
            snap(name="Send", control_type=CONTROL_TYPE_BUTTON, bounds=(910, 520, 950, 550)),
        )
        bridge = FakeBridge(
            window_bounds=(0, 0, 1000, 800), elements=elements,
            composer_bounds=(100, 500, 900, 560),
        )
        obs = capture_evidence(
            uia=bridge, window=window(), application="chatgpt_desktop",
            application_confidence=KnowledgeType.OBSERVED,
            application_reason="test setup", now=T0,
        )
        assert obs.window_handle == 1
        assert obs.window_title == "Kalpavriksha Reasoning"
        assert obs.window_state is WindowState.MAXIMIZED
        assert len(obs.elements) == 2
        assert obs.elements[0].role is SemanticRole.COMPOSER
        assert obs.elements[1].role is SemanticRole.BUTTON
        assert obs.confidence is KnowledgeType.OBSERVED


class TestUnknownApplication:
    """2. Unknown application — `DesktopIntelligence.observe_desktop()`
    for a name not in `desktop/catalog.py` returns an honest UNKNOWN
    observation, never an exception."""

    def test_unknown_application_key_returns_unknown_observation(self):
        from master_agent.desktop.actions import DesktopContext
        from master_agent.desktop.intelligence.observer import DesktopIntelligence
        from master_agent.desktop.probe import CommandResult

        class FakeProbe:
            platform = "win32"

            def which(self, executable):
                return None

            def exists(self, path):
                return False

            def run(self, command):
                return CommandResult(ok=True, output="")

            def processes(self):
                return []

        intel = DesktopIntelligence(DesktopContext(FakeProbe()))
        obs = intel.observe_desktop("not-a-real-application", now=T0)
        assert obs.confidence is KnowledgeType.UNKNOWN
        assert obs.application_confidence is KnowledgeType.UNKNOWN
        assert "not a known application" in obs.reason
        assert obs.elements == ()
        assert obs.window_handle == 0


class TestMissingWindow:
    """3. Missing window — `capture_evidence()` degrades to an honest
    UNKNOWN observation when the window itself has no readable bounding
    rectangle, rather than raising."""

    def test_missing_window_bounds_yields_unknown_observation(self):
        bridge = FakeBridge(raise_on_window_bounds=True)
        obs = capture_evidence(
            uia=bridge, window=window(), application="chatgpt_desktop",
            application_confidence=KnowledgeType.OBSERVED,
            application_reason="test setup", now=T0,
        )
        assert obs.confidence is KnowledgeType.UNKNOWN
        assert obs.elements == ()
        assert "bounding rectangle" in obs.reason


class TestHiddenOffscreenElements:
    """4. Hidden/offscreen elements — carried through with is_offscreen
    set, never silently dropped, and never counted as actionable."""

    def test_offscreen_element_is_reported_but_not_actionable(self):
        elements = (
            snap(name="Send", control_type=CONTROL_TYPE_BUTTON, is_offscreen=True, bounds=(0, 0, 10, 10)),
        )
        bridge = FakeBridge(elements=elements)
        obs = capture_evidence(
            uia=bridge, window=window(), application="chatgpt_desktop",
            application_confidence=KnowledgeType.OBSERVED,
            application_reason="test setup", now=T0,
        )
        assert len(obs.elements) == 1
        assert obs.elements[0].is_offscreen is True
        assert obs.elements[0].role is SemanticRole.BUTTON
        assert obs.elements[0].is_actionable is False
        assert obs.actionable_controls == ()


class TestFocusedElementDetection:
    """5. Focused element detection — the element whose bounds match
    `get_focused_element_in_window()`'s own result is marked focused;
    nothing else is."""

    def test_focused_element_is_identified_by_bounds_match(self):
        composer_bounds = (100, 500, 900, 560)
        elements = (
            snap(name="Composer", is_focusable=True, has_text=True, bounds=composer_bounds),
            snap(name="Sidebar item", bounds=(0, 0, 50, 700)),
        )
        bridge = FakeBridge(elements=elements, focused_bounds=composer_bounds)
        obs = capture_evidence(
            uia=bridge, window=window(), application="chatgpt_desktop",
            application_confidence=KnowledgeType.OBSERVED,
            application_reason="test setup", now=T0,
        )
        assert obs.focused_element is not None
        assert obs.focused_element.name == "Composer"
        assert obs.focused_element.is_focused is True
        assert obs.elements[1].is_focused is False


class TestComposerClassification:
    """6. Composer classification — the element matching
    `find_composer()`'s own resolved bounds is classified COMPOSER,
    INFERRED, with a reason citing that heuristic."""

    def test_composer_matched_element_is_classified(self):
        composer_bounds = (100, 500, 900, 560)
        elements = (snap(name="Message ChatGPT", is_focusable=True, has_text=True, bounds=composer_bounds),)
        bridge = FakeBridge(elements=elements, composer_bounds=composer_bounds)
        obs = capture_evidence(
            uia=bridge, window=window(), application="chatgpt_desktop",
            application_confidence=KnowledgeType.OBSERVED,
            application_reason="test setup", now=T0,
        )
        composer = obs.elements[0]
        assert composer.role is SemanticRole.COMPOSER
        assert composer.role_confidence is KnowledgeType.INFERRED
        assert "find_composer" in composer.role_reason
        assert composer in obs.composer_candidates
        assert composer in obs.actionable_controls


class TestButtonClassification:
    """7. Button classification — a real UIA Button ControlType is
    classified BUTTON at OBSERVED confidence (a hard property read, not
    an inference)."""

    def test_button_control_type_is_observed_not_inferred(self):
        elements = (snap(name="Send", control_type=CONTROL_TYPE_BUTTON, is_enabled=True, bounds=(1, 1, 20, 20)),)
        bridge = FakeBridge(elements=elements)
        obs = capture_evidence(
            uia=bridge, window=window(), application="chatgpt_desktop",
            application_confidence=KnowledgeType.OBSERVED,
            application_reason="test setup", now=T0,
        )
        button = obs.elements[0]
        assert button.role is SemanticRole.BUTTON
        assert button.role_confidence is KnowledgeType.OBSERVED
        assert button.is_actionable is True


class TestUnknownClassification:
    """8. Unknown classification — an element with no matching signal at
    all is classified UNKNOWN, never guessed at."""

    def test_no_matching_signal_yields_unknown(self):
        elements = (snap(name="Mystery", control_type=99999, bounds=(1, 1, 5, 5)),)
        bridge = FakeBridge(elements=elements)
        obs = capture_evidence(
            uia=bridge, window=window(), application="chatgpt_desktop",
            application_confidence=KnowledgeType.OBSERVED,
            application_reason="test setup", now=T0,
        )
        mystery = obs.elements[0]
        assert mystery.role is SemanticRole.UNKNOWN
        assert mystery.role_confidence is KnowledgeType.UNKNOWN
        assert mystery.is_actionable is False


class TestConfidenceHandling:
    """9. Confidence handling — the top-level `confidence` never reads
    stronger than the weakest input fact that produced it."""

    def test_unknown_application_degrades_overall_confidence(self):
        bridge = FakeBridge(elements=())
        obs = capture_evidence(
            uia=bridge, window=window(), application="",
            application_confidence=KnowledgeType.UNKNOWN,
            application_reason="application identity could not be attributed", now=T0,
        )
        assert obs.confidence is KnowledgeType.UNKNOWN

    def test_observed_application_yields_observed_confidence(self):
        bridge = FakeBridge(elements=())
        obs = capture_evidence(
            uia=bridge, window=window(), application="chatgpt_desktop",
            application_confidence=KnowledgeType.OBSERVED,
            application_reason="window attributed via process id", now=T0,
        )
        assert obs.confidence is KnowledgeType.OBSERVED


class TestAppKnowledgeLookup:
    """10. App Knowledge lookup — `resolve_app_knowledge()` finds the
    right profile by the desktop catalog key, and `capture_evidence()`
    carries the whole profile through unchanged (never collapsing its own
    DOCUMENTED/OBSERVED/INFERRED/UNKNOWN distinction into this layer's own
    vocabulary)."""

    def test_resolve_app_knowledge_joins_via_inventory_key(self):
        profile = resolve_app_knowledge("chatgpt_desktop")
        assert profile is CHATGPT_DESKTOP

    def test_resolve_app_knowledge_returns_none_for_unprofiled_application(self):
        assert resolve_app_knowledge("notepad") is None
        assert resolve_app_knowledge("not-a-real-key") is None

    def test_capture_evidence_carries_app_knowledge_through_unchanged(self):
        bridge = FakeBridge(elements=())
        obs = capture_evidence(
            uia=bridge, window=window(), application="chatgpt_desktop",
            application_confidence=KnowledgeType.OBSERVED,
            application_reason="test setup", app_knowledge=CHATGPT_DESKTOP, now=T0,
        )
        assert obs.app_knowledge is CHATGPT_DESKTOP
        assert obs.app_knowledge.chat_interface.knowledge_type in (
            KnowledgeType.DOCUMENTED, KnowledgeType.OBSERVED, KnowledgeType.INFERRED, KnowledgeType.UNKNOWN,
        )


class TestScreenshotCaptureSuccess:
    """11. Screenshot capture success — a working backend produces
    `captured=True` with a path, width, and height."""

    def test_successful_capture_produces_evidence(self, tmp_path):
        class FakeImage:
            width, height = 800, 600

            def save(self, path):
                Path(path).write_bytes(b"fake-png-bytes")

        class FakeBackend:
            def capture(self, bounds):
                return FakeImage()

        evidence = capture_screenshot(
            FakeBackend(), window_handle=1, application="chatgpt_desktop",
            bounds=(0, 0, 800, 600), dest_dir=tmp_path, now=T0,
        )
        assert evidence.captured is True
        assert evidence.width == 800 and evidence.height == 600
        assert evidence.path is not None
        assert Path(evidence.path).exists()
        assert evidence.window_handle == 1
        assert evidence.timestamp == T0


class TestScreenshotCaptureFailure:
    """12. Screenshot capture failure — an unavailable backend degrades
    to `captured=False` with a reason, never raises."""

    def test_failing_backend_degrades_safely(self, tmp_path):
        class FailingBackend:
            def capture(self, bounds):
                raise ScreenshotUnavailable("Pillow is not installed")

        evidence = capture_screenshot(
            FailingBackend(), window_handle=1, application="chatgpt_desktop",
            bounds=(0, 0, 800, 600), dest_dir=tmp_path, now=T0,
        )
        assert evidence.captured is False
        assert evidence.path is None
        assert "not installed" in evidence.reason

    def test_capture_evidence_never_raises_when_screenshot_backend_fails(self):
        class FailingBackend:
            def capture(self, bounds):
                raise ScreenshotUnavailable("no display available")

        bridge = FakeBridge(elements=())
        obs = capture_evidence(
            uia=bridge, window=window(), application="chatgpt_desktop",
            application_confidence=KnowledgeType.OBSERVED,
            application_reason="test setup", screenshot_backend=FailingBackend(), now=T0,
        )
        assert obs.screenshot is not None
        assert obs.screenshot.captured is False


class TestProvenanceAndTimestamp:
    """13. Provenance/timestamp preservation — every element and the
    observation itself carries the caller-supplied `now`, and a non-empty
    `source` a reader could go verify."""

    def test_every_fact_carries_timestamp_and_source(self):
        elements = (snap(name="Send", control_type=CONTROL_TYPE_BUTTON, bounds=(1, 1, 20, 20)),)
        bridge = FakeBridge(elements=elements)
        obs = capture_evidence(
            uia=bridge, window=window(), application="chatgpt_desktop",
            application_confidence=KnowledgeType.OBSERVED,
            application_reason="test setup", now=T0,
        )
        assert obs.timestamp == T0
        assert obs.source
        for element in obs.elements:
            assert element.timestamp == T0
            assert element.source


class TestNoMutationDuringObservation:
    """14. No mutation during observation — proven two independent ways:
    a fake bridge whose mutating methods raise on any call, and a
    structural AST scan of the package's own source."""

    def test_fake_bridge_mutation_methods_are_never_reached(self):
        elements = (
            snap(name="Composer", is_focusable=True, has_text=True, bounds=(100, 500, 900, 560)),
            snap(name="Send", control_type=CONTROL_TYPE_BUTTON, bounds=(910, 520, 950, 550)),
        )
        bridge = FakeBridge(
            elements=elements, composer_bounds=(100, 500, 900, 560),
            main_content_bounds=(0, 0, 900, 400), focused_bounds=(100, 500, 900, 560),
        )
        # If capture_evidence() ever reached write_text()/click(), the
        # fake would raise AssertionError and this test would fail loudly.
        capture_evidence(
            uia=bridge, window=window(), application="chatgpt_desktop",
            application_confidence=KnowledgeType.OBSERVED,
            application_reason="test setup", baseline={}, now=T0,
        )

    @pytest.mark.parametrize("filename", ["evidence.py", "observer.py", "classification.py", "screenshot.py", "app_knowledge_bridge.py", "models.py"])
    def test_source_never_references_a_mutating_identifier(self, filename):
        forbidden = {"write_text", "click", "KeyboardController", "MouseController", "paste", "press"}
        tree = ast.parse((PACKAGE / filename).read_text(encoding="utf-8"))
        found = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in forbidden:
                found.add(node.id)
            if isinstance(node, ast.Attribute) and node.attr in forbidden:
                found.add(node.attr)
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name in forbidden:
                        found.add(alias.name)
        assert not found, f"{filename} references mutating identifier(s): {found}"


class TestCrossApplicationFocusSafety:
    """15. Cross-application focus safety — when
    `get_focused_element_in_window()` reports that nothing in *this*
    window has focus (the real bridge's own guard against a different
    application's focus leaking in), no element is ever guessed as
    focused."""

    def test_no_focus_in_this_window_yields_no_focused_element(self):
        elements = (
            snap(name="Composer", is_focusable=True, has_text=True, bounds=(100, 500, 900, 560)),
        )
        bridge = FakeBridge(elements=elements, focused_bounds=None)
        obs = capture_evidence(
            uia=bridge, window=window(), application="chatgpt_desktop",
            application_confidence=KnowledgeType.OBSERVED,
            application_reason="test setup", now=T0,
        )
        assert obs.focused_element is None
        assert all(not e.is_focused for e in obs.elements)


# ═══════════════════════════ additional coverage ═════════════════════════


class TestSelectedTab:
    def test_selected_tab_is_identified_from_selection_item_state(self):
        elements = (
            snap(name="Chat", control_type=CONTROL_TYPE_TAB_ITEM, is_selected=True, bounds=(0, 0, 50, 20)),
            snap(name="Codex", control_type=CONTROL_TYPE_TAB_ITEM, is_selected=False, bounds=(50, 0, 100, 20)),
        )
        bridge = FakeBridge(elements=elements)
        obs = capture_evidence(
            uia=bridge, window=window(), application="chatgpt_desktop",
            application_confidence=KnowledgeType.OBSERVED,
            application_reason="test setup", now=T0,
        )
        assert obs.selected_tab is not None
        assert obs.selected_tab.name == "Chat"


class TestWindowState:
    def test_minimized_window_is_reported(self):
        bridge = FakeBridge(elements=())
        obs = capture_evidence(
            uia=bridge, window=window(maximized=False, minimized=True), application="chatgpt_desktop",
            application_confidence=KnowledgeType.OBSERVED,
            application_reason="test setup", now=T0,
        )
        assert obs.window_state is WindowState.MINIMIZED

    def test_normal_window_is_reported(self):
        bridge = FakeBridge(elements=())
        obs = capture_evidence(
            uia=bridge, window=window(maximized=False, minimized=False), application="chatgpt_desktop",
            application_confidence=KnowledgeType.OBSERVED,
            application_reason="test setup", now=T0,
        )
        assert obs.window_state is WindowState.NORMAL


class TestResponseRegionClassification:
    def test_new_content_match_is_classified_response_region(self):
        response_bounds = (0, 400, 900, 460)
        elements = (snap(name="", has_text=True, bounds=response_bounds),)
        bridge = FakeBridge(elements=elements, new_content_bounds=response_bounds)
        obs = capture_evidence(
            uia=bridge, window=window(), application="chatgpt_desktop",
            application_confidence=KnowledgeType.OBSERVED,
            application_reason="test setup", baseline={}, now=T0,
        )
        assert obs.elements[0].role is SemanticRole.RESPONSE_REGION
        assert obs.elements[0].role_confidence is KnowledgeType.INFERRED


class TestAsDictSerialization:
    def test_as_dict_is_json_shaped(self):
        elements = (snap(name="Send", control_type=CONTROL_TYPE_BUTTON, bounds=(1, 1, 20, 20)),)
        bridge = FakeBridge(elements=elements)
        obs = capture_evidence(
            uia=bridge, window=window(), application="chatgpt_desktop",
            application_confidence=KnowledgeType.OBSERVED,
            application_reason="test setup", now=T0,
        )
        payload = obs.as_dict()
        assert payload["application"] == "chatgpt_desktop"
        assert payload["window_state"] == "maximized"
        assert isinstance(payload["elements"], list)
        assert payload["elements"][0]["role"] == "button"
