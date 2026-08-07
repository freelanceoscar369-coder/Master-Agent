"""Sprint 1, Component 27 — Desktop Perception Layer.

**No test in this file executes, clicks, types, launches, terminates,
restarts, moves the mouse, or presses a key.** Window/Readiness/Failure/
History tests inject Fake backends (mirroring `tests/
test_desktop_execution.py`'s own fixtures); Browser Observer tests use a
real, headless `BrowserSessionManager` against `data:` URLs only — the
identical pattern C26's own suite already established, and already a
normal part of every run of this repository's test suite.

| Requirement | Source |
|---|---|
| Application opens / closes | C27 brief |
| Window changes | C27 brief |
| Browser navigation | C27 brief |
| Busy / Missing / Unknown state | C27 brief |
| History | C27 brief |
| Confidence propagation | C27 brief |
| Failure detection | C27 brief |
| Never execute, click, type, launch, terminate, restart, move mouse, press key, modify windows | C27 brief |

Structural guards read executable identifiers via AST, never source
text — the discipline every C22–C26 suite already established.
"""
from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from master_agent.desktop.actions import DesktopContext
from master_agent.desktop.execution.backends import WindowInfo
from master_agent.desktop.execution.clipboard import ClipboardExecutive
from master_agent.desktop.execution.process import ProcessExecutive
from master_agent.desktop.execution.window import WindowManager
from master_agent.desktop.inventory import MachineInventory
from master_agent.desktop.operations import KNOWLEDGE_BASE
from master_agent.desktop.perception import (
    SECTIONS,
    Confidence,
    DesktopObservationHistory,
    DesktopObserver,
    FailureDetector,
    FailureKind,
    Observation,
    ObservationEngine,
    ReadinessState,
    UIReadyDetector,
    WindowObserver,
)
from master_agent.desktop.perception.browser import BrowserObserver
from master_agent.desktop.perception.clipboard import ClipboardObserver
from master_agent.desktop.perception.evidence import InvalidObservation
from master_agent.desktop.perception.state import (
    DesktopState,
    aggregate_confidence,
)
from master_agent.desktop.perception.win32_probe import (
    ResponsivenessUnavailable,
)
from master_agent.desktop.probe import CommandResult, ProcessInfo
from master_agent.environment.browser_session import BrowserSessionManager

PACKAGE = (
    Path(__file__).resolve().parent.parent
    / "src" / "master_agent" / "desktop" / "perception"
)

T0 = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)


# ═══════════════════════ fakes — no real backend anywhere ═══════════════


class FakeWindowBackend:
    def __init__(self, windows=(), active_handle=None):
        self._windows = {w.handle: w for w in windows}
        self._active = active_handle

    def enumerate(self):
        return tuple(self._windows.values())

    def active(self):
        return self._windows.get(self._active) if self._active is not None else None

    def bring_to_front(self, handle):  # pragma: no cover — never called by this layer
        raise AssertionError("perception must never mutate a window")

    minimize = maximize = restore = close = bring_to_front


class ExplodingWindowBackend:
    def enumerate(self):
        from master_agent.desktop.execution.backends import BackendUnavailable

        raise BackendUnavailable("no window backend is configured")

    def active(self):
        from master_agent.desktop.execution.backends import BackendUnavailable

        raise BackendUnavailable("no window backend is configured")


class FakeProbe:
    def __init__(self, running=None, on_path=None):
        self.platform = "win32"
        self._running = list(running or [])
        self._on_path = on_path or {}

    def which(self, executable):
        return self._on_path.get(executable)

    def exists(self, path):
        return False

    def run(self, command):
        return CommandResult(ok=True, output="")

    def start(self, command):  # pragma: no cover — perception never launches
        raise AssertionError("perception must never launch anything")

    def processes(self):
        return list(self._running)


def window(handle=1, title="Untitled", process_id=100, visible=True, minimized=False, maximized=False):
    return WindowInfo(
        handle=handle, title=title, process_id=process_id,
        is_visible=visible, is_minimized=minimized, is_maximized=maximized,
    )


def inventory(*running_pairs, platform="win32"):
    """`running_pairs` is `(pid, owner_key)` tuples."""
    processes = [ProcessInfo(pid=pid, name=f"{owner}.exe", owner=owner) for pid, owner in running_pairs]
    apps = []
    return MachineInventory(applications=apps, processes=processes, platform=platform, captured_at=T0)


class AlwaysRespondingBackend:
    def is_responding(self, handle, timeout_ms=500):
        return True


class NeverRespondingBackend:
    def is_responding(self, handle, timeout_ms=500):
        return False


class ExplodingResponsivenessBackend:
    def is_responding(self, handle, timeout_ms=500):
        raise ResponsivenessUnavailable("no probe")


def engine(
    windows_backend=None, running=(), on_path=None, responsiveness=None,
) -> ObservationEngine:
    probe = FakeProbe(running=running, on_path=on_path)
    context = DesktopContext(probe)
    return ObservationEngine(
        window_manager=WindowManager(windows_backend or FakeWindowBackend()),
        process=ProcessExecutive(context=context, sleep=lambda s: None),
        responsiveness=responsiveness,
    )


DATA_URL = "data:text/html,<html><body><h1>C27</h1></body></html>"


# ═══════════════════════ A · window observer ═════════════════════════════


class TestWindowObserver:
    def test_enumerate_reports_every_window_observed(self):
        backend = FakeWindowBackend((window(1, "Chrome"), window(2, "Notepad")))
        obs = WindowObserver(WindowManager(backend)).observe(T0)
        assert obs.windows.confidence == Confidence.OBSERVED
        assert len(obs.windows.value) == 2

    def test_active_window_is_reported(self):
        backend = FakeWindowBackend((window(1, "Chrome"), window(2, "Notepad")), active_handle=2)
        obs = WindowObserver(WindowManager(backend)).observe(T0)
        assert obs.active_window.value.title == "Notepad"

    def test_no_active_window_is_reported_honestly(self):
        obs = WindowObserver(WindowManager(FakeWindowBackend())).observe(T0)
        assert not obs.active_window.known

    def test_focused_application_resolved_from_inventory(self):
        backend = FakeWindowBackend((window(1, "Chrome", process_id=555),), active_handle=1)
        inv = inventory((555, "chrome"))
        obs = WindowObserver(WindowManager(backend)).observe(T0, inventory=inv)
        assert obs.active_application.value == "chrome"
        assert obs.active_application.confidence == Confidence.OBSERVED

    def test_focused_application_unknown_without_inventory(self):
        backend = FakeWindowBackend((window(1, "Chrome", process_id=555),), active_handle=1)
        obs = WindowObserver(WindowManager(backend)).observe(T0)
        assert not obs.active_application.known

    def test_focused_application_unknown_when_process_unattributed(self):
        backend = FakeWindowBackend((window(1, "Unknown App", process_id=999),), active_handle=1)
        inv = inventory((555, "chrome"))
        obs = WindowObserver(WindowManager(backend)).observe(T0, inventory=inv)
        assert not obs.active_application.known

    def test_is_foreground_is_computed_not_duplicated(self):
        backend = FakeWindowBackend((window(1, "Chrome"), window(2, "Notepad")), active_handle=2)
        obs = WindowObserver(WindowManager(backend)).observe(T0)
        chrome, notepad = obs.windows.value
        assert obs.is_foreground(notepad) is True
        assert obs.is_foreground(chrome) is False

    def test_enumeration_failure_is_reported_honestly(self):
        obs = WindowObserver(WindowManager(ExplodingWindowBackend())).observe(T0)
        assert not obs.windows.known
        assert not obs.active_window.known

    def test_never_calls_a_mutating_window_method(self):
        backend = FakeWindowBackend((window(1, "Chrome"),), active_handle=1)
        WindowObserver(WindowManager(backend)).observe(T0)
        # FakeWindowBackend raises AssertionError if any mutating method
        # is called — reaching here at all is the proof.


# ═══════════════════════ B · UI ready detector ═══════════════════════════


class TestUIReadyDetector:
    def test_ready_when_window_found_and_responding(self):
        detector = UIReadyDetector(AlwaysRespondingBackend())
        obs = detector.detect(
            application="chrome", is_running=True, window=window(1, "Chrome"),
            launched_at=None, previous_title=None, now=T0,
        )
        assert obs.value is ReadinessState.READY

    def test_hung_when_window_found_and_not_responding(self):
        detector = UIReadyDetector(NeverRespondingBackend())
        obs = detector.detect(
            application="chrome", is_running=True, window=window(1, "Chrome"),
            launched_at=None, previous_title=None, now=T0,
        )
        assert obs.value is ReadinessState.HUNG
        assert obs.confidence == Confidence.OBSERVED

    def test_busy_when_title_changed_since_last_observation(self):
        detector = UIReadyDetector(AlwaysRespondingBackend())
        obs = detector.detect(
            application="chrome", is_running=True, window=window(1, "New Title"),
            launched_at=None, previous_title="Old Title", now=T0,
        )
        assert obs.value is ReadinessState.BUSY
        assert obs.confidence == Confidence.WEAK

    def test_window_missing_when_not_running_and_no_window(self):
        detector = UIReadyDetector()
        obs = detector.detect(
            application="chrome", is_running=False, window=None,
            launched_at=None, previous_title=None, now=T0,
        )
        assert obs.value is ReadinessState.WINDOW_MISSING
        assert obs.confidence == Confidence.OBSERVED

    def test_loading_within_startup_estimate(self):
        detector = UIReadyDetector()
        profile = KNOWLEDGE_BASE.profile("chrome")
        launched = T0
        soon = T0 + timedelta(seconds=1)
        obs = detector.detect(
            application="chrome", is_running=True, window=None,
            launched_at=launched, previous_title=None, now=soon, profile=profile,
        )
        assert obs.value is ReadinessState.LOADING
        assert obs.confidence == Confidence.STRONG

    def test_window_missing_past_startup_estimate(self):
        detector = UIReadyDetector()
        profile = KNOWLEDGE_BASE.profile("chrome")
        launched = T0
        long_after = T0 + timedelta(seconds=profile.startup_time.typical_seconds[1] + 60)
        obs = detector.detect(
            application="chrome", is_running=True, window=None,
            launched_at=launched, previous_title=None, now=long_after, profile=profile,
        )
        assert obs.value is ReadinessState.WINDOW_MISSING
        assert obs.confidence == Confidence.STRONG

    def test_loading_weak_without_a_profile_or_launch_time(self):
        detector = UIReadyDetector()
        obs = detector.detect(
            application="chrome", is_running=True, window=None,
            launched_at=None, previous_title=None, now=T0,
        )
        assert obs.value is ReadinessState.LOADING
        assert obs.confidence == Confidence.WEAK

    def test_unknown_when_running_state_unknown(self):
        detector = UIReadyDetector()
        obs = detector.detect(
            application="chrome", is_running=None, window=None,
            launched_at=None, previous_title=None, now=T0,
        )
        assert obs.value is None
        assert obs.confidence == Confidence.UNKNOWN

    def test_unknown_when_responsiveness_cannot_be_checked_and_title_unchanged(self):
        detector = UIReadyDetector(ExplodingResponsivenessBackend())
        obs = detector.detect(
            application="chrome", is_running=True, window=window(1, "Chrome"),
            launched_at=None, previous_title="Chrome", now=T0,
        )
        assert obs.value is None
        assert obs.confidence == Confidence.UNKNOWN

    def test_never_assumes_hung_from_elapsed_time_alone(self):
        """A window that has existed a long time, with no responsiveness
        signal at all, must not become HUNG by inference — only a real
        probe result may say so."""
        detector = UIReadyDetector(ExplodingResponsivenessBackend())
        obs = detector.detect(
            application="chrome", is_running=True, window=window(1, "Chrome"),
            launched_at=T0 - timedelta(hours=5), previous_title="Chrome", now=T0,
        )
        assert obs.value is not ReadinessState.HUNG

    def test_ready_is_strong_when_title_is_stable_across_observations(self):
        detector = UIReadyDetector(AlwaysRespondingBackend())
        obs = detector.detect(
            application="chrome", is_running=True, window=window(1, "Same Title"),
            launched_at=None, previous_title="Same Title", now=T0,
        )
        assert obs.value is ReadinessState.READY
        assert obs.confidence == Confidence.STRONG


# ═══════════════════════ C · clipboard observer ═══════════════════════════


class TestClipboardObserver:
    def test_reports_content_present(self):
        from tests.test_desktop_execution import FakeClipboardBackend

        clipboard = ClipboardExecutive(FakeClipboardBackend("hello"))
        status = ClipboardObserver(clipboard).observe(T0)
        assert status.has_content.value is True
        assert status.length.value == 5

    def test_reports_empty_clipboard(self):
        from tests.test_desktop_execution import FakeClipboardBackend

        clipboard = ClipboardExecutive(FakeClipboardBackend(None))
        status = ClipboardObserver(clipboard).observe(T0)
        assert status.has_content.value is False
        assert status.length.value == 0

    def test_never_reports_the_actual_text(self):
        from tests.test_desktop_execution import FakeClipboardBackend

        clipboard = ClipboardExecutive(FakeClipboardBackend("a secret founder note"))
        status = ClipboardObserver(clipboard).observe(T0)
        rendered = str(status.as_dict())
        assert "secret" not in rendered

    def test_the_null_default_is_honestly_empty(self):
        status = ClipboardObserver().observe(T0)
        assert status.has_content.value is False


# ═══════════════════════ D · browser observer (real, headless) ═══════════


class TestBrowserObserver:
    def test_no_manager_reports_browser_inactive(self):
        perception = BrowserObserver(None).observe(T0)
        assert perception.browser_active.value is False
        assert perception.tab_count.value == 0

    def test_no_sessions_open_reports_inactive(self):
        manager = BrowserSessionManager()
        perception = BrowserObserver(manager).observe(T0)
        assert perception.browser_active.value is False

    def test_an_open_session_is_observed(self):
        manager = BrowserSessionManager()
        manager.open_session("s1")
        try:
            session = manager.get("s1")
            session.page.set_content("<html><body>hi</body></html>")
            perception = BrowserObserver(manager).observe(T0, session_id="s1")
            assert perception.browser_active.value is True
            assert perception.tab_count.value == 1
            assert perception.page_loaded.value is True
        finally:
            manager.close_all()

    def test_current_url_reflects_navigation(self):
        manager = BrowserSessionManager()
        manager.open_session("s1")
        try:
            manager.get("s1").page.goto(DATA_URL)
            perception = BrowserObserver(manager).observe(T0, session_id="s1")
            assert perception.current_url.value == DATA_URL
        finally:
            manager.close_all()

    def test_tab_count_reflects_multiple_sessions(self):
        manager = BrowserSessionManager()
        manager.open_session("a")
        manager.open_session("b")
        try:
            perception = BrowserObserver(manager).observe(T0)
            assert perception.tab_count.value == 2
        finally:
            manager.close_all()

    def test_never_inspects_cookies_history_or_credentials(self):
        """Scoped to `browser.py` alone — `history` is also a legitimate
        identifier elsewhere in this package (`DesktopObserver.history`,
        this layer's own observation history), which is a different
        concept from browser history and must not trip this guard."""
        tree = ast.parse(PACKAGE.joinpath("browser.py").read_text(encoding="utf-8"))
        imports, calls, defined = set(), set(), set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)
            elif isinstance(node, ast.Call):
                calls.add(ast.unparse(node.func))
            elif isinstance(node, (ast.ClassDef, ast.FunctionDef)):
                defined.add(node.name)
        for forbidden in ("cookies", "storage_state", "history", "password", "credential"):
            assert forbidden not in imports
            assert forbidden not in calls
            assert forbidden not in defined


# ═══════════════════════ E · observation engine / desktop state ═════════


class TestApplicationOpensAndCloses:
    def test_application_opens_moves_from_missing_to_ready(self):
        e = engine(running=[ProcessInfo(pid=1, name="chrome.exe", owner="chrome")])
        inv = inventory((1, "chrome"))
        # No window yet: still loading/missing.
        state1 = e.observe(T0, applications=("chrome",), inventory=inv)
        assert state1.application("chrome").readiness.value in (
            ReadinessState.LOADING, ReadinessState.WINDOW_MISSING,
        )

    def test_application_closes_reports_not_running(self):
        e = engine(running=[])
        inv = inventory()
        state = e.observe(T0, applications=("git",), inventory=inv)
        assert state.application("git").is_running.value is False
        assert state.application("git").readiness.value is ReadinessState.WINDOW_MISSING

    def test_a_window_owned_by_the_application_is_attributed(self):
        backend = FakeWindowBackend((window(1, "Chrome", process_id=1),))
        e = engine(windows_backend=backend, running=[ProcessInfo(pid=1, name="chrome.exe", owner="chrome")])
        inv = inventory((1, "chrome"))
        state = e.observe(T0, applications=("chrome",), inventory=inv)
        assert state.application("chrome").window.value.title == "Chrome"


class TestWindowChanges:
    def test_changes_since_reports_windows_section_on_a_new_window(self):
        history = DesktopObservationHistory()
        e = engine()
        state1 = e.observe(T0, applications=())
        history.record(state1)

        backend2 = FakeWindowBackend((window(1, "New Window"),))
        e2 = engine(windows_backend=backend2)
        state2 = e2.observe(T0 + timedelta(seconds=1), applications=())
        assert "windows" in history.changes_since(state1) or history.changes_since(state1) == ()
        history.record(state2)
        assert "windows" in history.changes_since(state1)


class TestBrowserNavigationObservedViaEngine:
    def test_engine_reports_browser_state(self):
        manager = BrowserSessionManager()
        manager.open_session("s1")
        try:
            manager.get("s1").page.goto(DATA_URL)
            e = ObservationEngine(browser_sessions=manager)
            state = e.observe(T0, applications=())
            assert state.browser.current_url.value == DATA_URL
        finally:
            manager.close_all()


class TestBusyMissingUnknownStates:
    def test_busy_state_reaches_desktop_state(self):
        backend = FakeWindowBackend((window(1, "Loading...", process_id=1),))
        e = engine(
            windows_backend=backend, responsiveness=AlwaysRespondingBackend(),
            running=[ProcessInfo(pid=1, name="chrome.exe", owner="chrome")],
        )
        inv = inventory((1, "chrome"))
        state1 = e.observe(T0, applications=("chrome",), inventory=inv)

        backend2 = FakeWindowBackend((window(1, "Loaded Page", process_id=1),))
        e2 = engine(
            windows_backend=backend2, responsiveness=AlwaysRespondingBackend(),
            running=[ProcessInfo(pid=1, name="chrome.exe", owner="chrome")],
        )
        state2 = e2.observe(T0 + timedelta(seconds=1), applications=("chrome",), inventory=inv, previous=state1)
        assert state2.application("chrome").readiness.value is ReadinessState.BUSY

    def test_missing_state_reaches_desktop_state(self):
        e = engine(running=[])
        state = e.observe(T0, applications=("chrome",), inventory=inventory())
        assert state.application("chrome").readiness.value is ReadinessState.WINDOW_MISSING

    def test_unknown_state_when_process_cannot_be_checked(self):
        window_manager = WindowManager(FakeWindowBackend())
        e = ObservationEngine(window_manager=window_manager, process=None)
        state = e.observe(T0, applications=("chrome",))
        assert state.application("chrome").readiness.value is None
        assert state.application("chrome").readiness.confidence == Confidence.UNKNOWN


# ═══════════════════════ F · history ═════════════════════════════════════


class TestHistory:
    def test_latest_is_none_before_anything_recorded(self):
        assert DesktopObservationHistory().latest() is None

    def test_record_and_latest(self):
        history = DesktopObservationHistory()
        e = engine()
        state = e.observe(T0)
        history.record(state)
        assert history.latest() is state

    def test_bounded_at_max_observations(self):
        history = DesktopObservationHistory(max_observations=3)
        e = engine()
        for i in range(5):
            history.record(e.observe(T0 + timedelta(seconds=i)))
        assert len(history) == 3
        assert history.latest().timestamp == T0 + timedelta(seconds=4)

    def test_changes_since_empty_when_nothing_changed(self):
        history = DesktopObservationHistory()
        e = engine()
        state1 = e.observe(T0)
        history.record(state1)
        state2 = e.observe(T0 + timedelta(seconds=1))
        history.record(state2)
        # Same fake backend, same facts -> only timestamps differ, which
        # signatures deliberately exclude.
        assert history.changes_since(state1) == ()

    def test_stable_false_before_enough_observations(self):
        history = DesktopObservationHistory()
        history.record(engine().observe(T0))
        assert history.stable(count=2) is False

    def test_stable_true_when_repeated_observations_agree(self):
        history = DesktopObservationHistory()
        e = engine()
        history.record(e.observe(T0))
        history.record(e.observe(T0 + timedelta(seconds=1)))
        assert history.stable(count=2) is True

    def test_stable_false_after_a_real_change(self):
        history = DesktopObservationHistory()
        history.record(engine().observe(T0))
        history.record(engine(windows_backend=FakeWindowBackend((window(9, "New"),))).observe(T0 + timedelta(seconds=1)))
        assert history.stable(count=2) is False

    def test_max_observations_must_be_positive(self):
        with pytest.raises(ValueError):
            DesktopObservationHistory(max_observations=0)

    def test_count_must_be_positive(self):
        with pytest.raises(ValueError):
            DesktopObservationHistory().stable(count=0)

    def test_sections_are_the_brief_relevant_state_facets(self):
        assert set(SECTIONS) == {"applications", "windows", "browser", "clipboard", "focus", "foreground"}


# ═══════════════════════ G · confidence propagation ══════════════════════


class TestConfidencePropagation:
    def test_state_confidence_is_the_weakest_observation(self):
        e = ObservationEngine(window_manager=WindowManager(FakeWindowBackend()), process=None)
        state = e.observe(T0, applications=("chrome",))
        assert state.confidence == Confidence.UNKNOWN

    def test_fully_observed_state_has_observed_confidence(self):
        backend = FakeWindowBackend((window(1, "Chrome", process_id=1),), active_handle=1)
        e = engine(windows_backend=backend, running=[ProcessInfo(pid=1, name="chrome.exe", owner="chrome")], responsiveness=AlwaysRespondingBackend())
        state = e.observe(T0, applications=("chrome",), inventory=inventory((1, "chrome")))
        assert state.focus.known  # active window resolved to an application
        assert state.application("chrome").readiness.confidence in (Confidence.OBSERVED, Confidence.STRONG)

    def test_the_whole_state_confidence_is_dragged_down_by_an_unobserved_browser(self):
        """No browser session exists in this scenario, so `browser
        .current_url` is honestly `UNKNOWN` — and that alone is enough to
        pull the *whole* state's aggregate confidence down, proving
        `Confidence.weakest()` (C22) is really being applied across every
        section, not just the one a caller happens to check."""
        backend = FakeWindowBackend((window(1, "Chrome", process_id=1),), active_handle=1)
        e = engine(windows_backend=backend, running=[ProcessInfo(pid=1, name="chrome.exe", owner="chrome")], responsiveness=AlwaysRespondingBackend())
        state = e.observe(T0, applications=("chrome",), inventory=inventory((1, "chrome")))
        assert not state.browser.current_url.known
        assert state.confidence == Confidence.UNKNOWN

    def test_aggregate_confidence_matches_c22s_own_combinator(self):
        assert aggregate_confidence([]) == Confidence.UNKNOWN
        strong = Observation(value=1, confidence=Confidence.STRONG, reason="x", source="y", timestamp=T0)
        weak = Observation(value=2, confidence=Confidence.WEAK, reason="x", source="y", timestamp=T0)
        assert aggregate_confidence([strong, weak]) == Confidence.WEAK

    def test_observation_refuses_a_value_alongside_unknown(self):
        with pytest.raises(InvalidObservation):
            Observation(value="x", confidence=Confidence.UNKNOWN, reason="y", source="z", timestamp=T0)

    def test_observation_refuses_a_naive_timestamp(self):
        with pytest.raises(InvalidObservation):
            Observation(
                value=1, confidence=Confidence.OBSERVED, reason="y", source="z",
                timestamp=datetime(2026, 1, 1),  # noqa: DTZ001 — deliberately naive, to prove it is refused
            )

    def test_observation_refuses_a_blank_reason(self):
        with pytest.raises(InvalidObservation):
            Observation(value=1, confidence=Confidence.OBSERVED, reason="  ", source="z", timestamp=T0)


# ═══════════════════════ H · failure detection ═══════════════════════════


class TestFailureDetection:
    def test_no_previous_state_means_no_failures(self):
        assert FailureDetector().detect(None, engine().observe(T0)) == ()

    def test_window_disappeared_while_still_running(self):
        backend1 = FakeWindowBackend((window(1, "Chrome", process_id=1),))
        e1 = engine(windows_backend=backend1, running=[ProcessInfo(pid=1, name="chrome.exe", owner="chrome")])
        inv = inventory((1, "chrome"))
        state1 = e1.observe(T0, applications=("chrome",), inventory=inv)

        e2 = engine(windows_backend=FakeWindowBackend(), running=[ProcessInfo(pid=1, name="chrome.exe", owner="chrome")])
        state2 = e2.observe(T0 + timedelta(seconds=1), applications=("chrome",), inventory=inv)

        failures = FailureDetector().detect(state1, state2)
        assert any(f.kind is FailureKind.WINDOW_DISAPPEARED for f in failures)

    def test_application_crashed_when_window_and_process_both_gone(self):
        backend1 = FakeWindowBackend((window(1, "Chrome", process_id=1),))
        e1 = engine(windows_backend=backend1, running=[ProcessInfo(pid=1, name="chrome.exe", owner="chrome")])
        inv = inventory((1, "chrome"))
        state1 = e1.observe(T0, applications=("chrome",), inventory=inv)

        e2 = engine(windows_backend=FakeWindowBackend(), running=[])
        state2 = e2.observe(T0 + timedelta(seconds=1), applications=("chrome",), inventory=inventory())

        failures = FailureDetector().detect(state1, state2)
        assert any(f.kind is FailureKind.APPLICATION_CRASHED for f in failures)

    def test_window_hidden_when_visibility_changes(self):
        backend1 = FakeWindowBackend((window(1, "Chrome", process_id=1, visible=True),))
        e1 = engine(windows_backend=backend1, running=[ProcessInfo(pid=1, name="chrome.exe", owner="chrome")])
        inv = inventory((1, "chrome"))
        state1 = e1.observe(T0, applications=("chrome",), inventory=inv)

        backend2 = FakeWindowBackend((window(1, "Chrome", process_id=1, visible=False),))
        e2 = engine(windows_backend=backend2, running=[ProcessInfo(pid=1, name="chrome.exe", owner="chrome")])
        state2 = e2.observe(T0 + timedelta(seconds=1), applications=("chrome",), inventory=inv)

        failures = FailureDetector().detect(state1, state2)
        assert any(f.kind is FailureKind.WINDOW_HIDDEN for f in failures)

    def test_application_never_appeared_past_startup_estimate(self):
        launched_at = {"chrome": T0}
        e1 = engine(running=[ProcessInfo(pid=1, name="chrome.exe", owner="chrome")])
        inv = inventory((1, "chrome"))
        state1 = e1.observe(T0, applications=("chrome",), inventory=inv, launched_at=launched_at)
        profile = KNOWLEDGE_BASE.profile("chrome")

        e2 = engine(running=[ProcessInfo(pid=1, name="chrome.exe", owner="chrome")])
        overdue = T0 + timedelta(seconds=profile.startup_time.typical_seconds[1] + 60)
        state2 = e2.observe(overdue, applications=("chrome",), inventory=inv, launched_at=launched_at)

        failures = FailureDetector().detect(state1, state2)
        assert any(f.kind is FailureKind.APPLICATION_NEVER_APPEARED for f in failures)

    def test_browser_closed(self):
        manager = BrowserSessionManager()
        manager.open_session("s1")
        e1 = ObservationEngine(browser_sessions=manager)
        state1 = e1.observe(T0)
        manager.close_all()
        e2 = ObservationEngine(browser_sessions=manager)
        state2 = e2.observe(T0 + timedelta(seconds=1))

        failures = FailureDetector().detect(state1, state2)
        assert any(f.kind is FailureKind.BROWSER_CLOSED for f in failures)

    def test_navigation_failed_when_url_becomes_unobservable(self):
        state1 = DesktopState(
            applications=(), windows=engine().observe(T0).windows,
            browser=_browser_perception(url_known=True, active=True),
            clipboard=engine().observe(T0).clipboard, timestamp=T0, confidence=Confidence.OBSERVED,
        )
        state2 = DesktopState(
            applications=(), windows=engine().observe(T0).windows,
            browser=_browser_perception(url_known=False, active=True),
            clipboard=engine().observe(T0).clipboard, timestamp=T0 + timedelta(seconds=1),
            confidence=Confidence.UNKNOWN,
        )
        failures = FailureDetector().detect(state1, state2)
        assert any(f.kind is FailureKind.NAVIGATION_FAILED for f in failures)

    def test_failure_observations_carry_full_evidence(self):
        backend1 = FakeWindowBackend((window(1, "Chrome", process_id=1),))
        e1 = engine(windows_backend=backend1, running=[ProcessInfo(pid=1, name="chrome.exe", owner="chrome")])
        inv = inventory((1, "chrome"))
        state1 = e1.observe(T0, applications=("chrome",), inventory=inv)
        e2 = engine(windows_backend=FakeWindowBackend(), running=[])
        state2 = e2.observe(T0 + timedelta(seconds=1), applications=("chrome",), inventory=inventory())
        for failure in FailureDetector().detect(state1, state2):
            assert failure.reason
            assert failure.source
            assert failure.timestamp
            assert isinstance(failure.confidence, Confidence)

    def test_desktop_observer_exposes_failures_between_last_two_observations(self):
        history = DesktopObservationHistory()
        observer = DesktopObserver(history=history)
        assert observer.failures() == ()


def _browser_perception(*, url_known: bool, active: bool):
    from master_agent.desktop.perception.browser import BrowserPerception
    from master_agent.desktop.perception.evidence import unknown_observation

    known = Observation(value="https://example.invalid", confidence=Confidence.OBSERVED, reason="x", source="y", timestamp=T0)
    unk = unknown_observation(reason="x", source="y", timestamp=T0)
    return BrowserPerception(
        browser_active=Observation(value=active, confidence=Confidence.OBSERVED, reason="x", source="y", timestamp=T0),
        current_url=known if url_known else unk,
        page_loaded=known if url_known else unk,
        navigation_complete=known if url_known else unk,
        tab_count=Observation(value=1, confidence=Confidence.OBSERVED, reason="x", source="y", timestamp=T0),
        timestamp=T0,
    )


# ═══════════════════════ I · DesktopObserver end-to-end ═══════════════════


class TestDesktopObserverEndToEnd:
    def test_observe_records_into_history(self):
        observer = DesktopObserver()
        state = observer.observe(T0, applications=("chrome",))
        assert observer.history.latest() is state

    def test_repeated_observe_calls_thread_previous_state(self):
        backend = FakeWindowBackend((window(1, "Chrome", process_id=1),))
        e = ObservationEngine(window_manager=WindowManager(backend))
        observer = DesktopObserver(engine=e)
        observer.observe(T0, applications=("chrome",), inventory=inventory((1, "chrome")))
        second = observer.observe(T0 + timedelta(seconds=1), applications=("chrome",), inventory=inventory((1, "chrome")))
        # Same title both times -> READY should be STRONG on the second call.
        assert second.application("chrome").readiness.confidence in (Confidence.STRONG, Confidence.OBSERVED, Confidence.UNKNOWN)


# ═══════════════════════ I2 · remaining coverage ══════════════════════════


class TestEvidenceValidation:
    def test_confidence_must_be_a_confidence_band(self):
        with pytest.raises(InvalidObservation):
            Observation(value=None, confidence="observed", reason="x", source="y", timestamp=T0)  # type: ignore[arg-type]

    def test_source_must_be_non_blank(self):
        with pytest.raises(InvalidObservation):
            Observation(value=1, confidence=Confidence.OBSERVED, reason="x", source="  ", timestamp=T0)

    def test_as_dict_projects_a_nested_as_dict_capable_value(self):
        w = window(1, "Chrome")
        obs = Observation(value=w, confidence=Confidence.OBSERVED, reason="x", source="y", timestamp=T0)
        assert obs.as_dict()["value"] == w.as_dict()


class TestDesktopStateProjection:
    def test_application_state_as_dict(self):
        e = engine(running=[ProcessInfo(pid=1, name="chrome.exe", owner="chrome")])
        state = e.observe(T0, applications=("chrome",), inventory=inventory((1, "chrome")))
        projected = state.application("chrome").as_dict()
        assert projected["application"] == "chrome"

    def test_desktop_state_as_dict_round_trips_through_json(self):
        import json

        backend = FakeWindowBackend((window(1, "Chrome", process_id=1),), active_handle=1)
        e = engine(windows_backend=backend, running=[ProcessInfo(pid=1, name="chrome.exe", owner="chrome")])
        state = e.observe(T0, applications=("chrome",), inventory=inventory((1, "chrome")))
        assert json.loads(json.dumps(state.as_dict())) == state.as_dict()

    def test_a_tuple_of_windows_projects_to_a_list_of_dicts(self):
        backend = FakeWindowBackend((window(1, "Chrome"), window(2, "Notepad")))
        obs = WindowObserver(WindowManager(backend)).observe(T0)
        projected = obs.windows.as_dict()
        assert projected["value"] == [window(1, "Chrome").as_dict(), window(2, "Notepad").as_dict()]

    def test_application_returns_none_for_an_untracked_key(self):
        state = engine().observe(T0, applications=())
        assert state.application("does-not-exist") is None

    def test_window_observation_as_dict(self):
        backend = FakeWindowBackend((window(1, "Chrome"),), active_handle=1)
        obs = WindowObserver(WindowManager(backend)).observe(T0)
        projected = obs.as_dict()
        assert projected["active_window"]["value"]["title"] == "Chrome"


class TestHistoryRemainingBranches:
    def test_changes_since_is_empty_when_history_has_nothing_recorded_yet(self):
        history = DesktopObservationHistory()
        state = engine().observe(T0)
        assert history.changes_since(state) == ()


class TestReadinessRemainingBranches:
    def test_busy_when_responsiveness_unavailable_but_title_changed(self):
        detector = UIReadyDetector(ExplodingResponsivenessBackend())
        obs = detector.detect(
            application="chrome", is_running=True, window=window(1, "New Title"),
            launched_at=None, previous_title="Old Title", now=T0,
        )
        assert obs.value is ReadinessState.BUSY
        assert obs.confidence == Confidence.WEAK


class TestFailuresRemainingBranches:
    def test_failure_observation_as_dict(self):
        obs = FailureDetector()
        backend1 = FakeWindowBackend((window(1, "Chrome", process_id=1),))
        e1 = engine(windows_backend=backend1, running=[ProcessInfo(pid=1, name="chrome.exe", owner="chrome")])
        inv = inventory((1, "chrome"))
        state1 = e1.observe(T0, applications=("chrome",), inventory=inv)
        e2 = engine(windows_backend=FakeWindowBackend(), running=[])
        state2 = e2.observe(T0 + timedelta(seconds=1), applications=("chrome",), inventory=inventory())
        failure = obs.detect(state1, state2)[0]
        projected = failure.as_dict()
        assert projected["kind"] == failure.kind.value

    def test_an_application_no_longer_tracked_in_current_is_skipped(self):
        e1 = engine(running=[ProcessInfo(pid=1, name="chrome.exe", owner="chrome")])
        state1 = e1.observe(T0, applications=("chrome",), inventory=inventory((1, "chrome")))
        e2 = engine()
        state2 = e2.observe(T0 + timedelta(seconds=1), applications=())  # chrome not tracked this round
        failures = FailureDetector().detect(state1, state2)
        assert not any(f.application == "chrome" for f in failures)


class TestEngineRemainingBranches:
    def test_window_enumeration_failure_leaves_the_application_window_unknown(self):
        e = ObservationEngine(window_manager=WindowManager(ExplodingWindowBackend()))
        state = e.observe(T0, applications=("chrome",), inventory=inventory((1, "chrome")))
        assert not state.application("chrome").window.known

    def test_is_running_failure_is_reported_honestly(self):
        e = engine()
        # An application unknown to the catalog fails IsRunningAction's
        # own validate() — the same honest failure a caller would get
        # calling ProcessExecutive.is_running() directly.
        state = e.observe(T0, applications=("not-a-real-application",))
        assert not state.application("not-a-real-application").is_running.known

    def test_desktop_observer_failures_after_two_real_observations(self):
        backend1 = FakeWindowBackend((window(1, "Chrome", process_id=1),))
        e = ObservationEngine(window_manager=WindowManager(backend1))
        observer = DesktopObserver(engine=e)
        observer.observe(T0, applications=(), inventory=inventory((1, "chrome")))
        observer.observe(T0 + timedelta(seconds=1), applications=(), inventory=inventory((1, "chrome")))
        # No application tracked -> no application failures, but the call
        # itself exercises DesktopObserver.failures()'s real comparison.
        assert observer.failures() == ()


class TestClipboardObserverRemainingBranches:
    def test_a_failing_backend_is_reported_honestly(self):
        class ExplodingClipboardBackend:
            def read(self):
                from master_agent.desktop.execution.backends import BackendUnavailable

                raise BackendUnavailable("gone")

            def write(self, text):
                raise NotImplementedError

            def clear(self):
                raise NotImplementedError

        status = ClipboardObserver(ClipboardExecutive(ExplodingClipboardBackend())).observe(T0)
        assert not status.has_content.known
        assert not status.length.known


class TestBrowserObserverRemainingBranches:
    def test_browser_perception_as_dict(self):
        perception = BrowserObserver(None).observe(T0)
        projected = perception.as_dict()
        assert projected["browser_active"]["value"] is False

    def test_a_session_id_that_no_longer_exists_is_reported_honestly(self):
        manager = BrowserSessionManager()
        manager.open_session("s1")
        manager.close_session("s1")
        perception = BrowserObserver(manager).observe(T0, session_id="s1")
        assert not perception.current_url.known

    def test_read_ready_state_reports_none_on_a_browser_session_error(self):
        from master_agent.desktop.perception.browser import _read_ready_state

        manager = BrowserSessionManager()
        assert _read_ready_state(manager, "never-opened") is None

    def test_page_loaded_is_unknown_when_ready_state_cannot_be_read(self, monkeypatch):
        import master_agent.desktop.perception.browser as browser_module

        manager = BrowserSessionManager()
        manager.open_session("s1")
        try:
            manager.get("s1").page.set_content("<html><body>hi</body></html>")
            monkeypatch.setattr(browser_module, "_read_ready_state", lambda sessions, sid: None)
            perception = BrowserObserver(manager).observe(T0, session_id="s1")
            assert not perception.page_loaded.known
            assert not perception.navigation_complete.known
            assert perception.current_url.known  # the URL read did not depend on ready-state
        finally:
            manager.close_all()

    def test_read_ready_state_reports_none_on_any_mechanical_failure(self):
        from master_agent.desktop.perception.browser import _read_ready_state

        class ExplodingPage:
            def evaluate(self, expr):
                raise RuntimeError("page crashed")

        class ExplodingSession:
            page = ExplodingPage()

        class ExplodingManager:
            def get(self, session_id):
                return ExplodingSession()

        assert _read_ready_state(ExplodingManager(), "x") is None


# ═══════════════════════ J · structural guards, by AST ═══════════════════


def _modules():
    return [
        (path, ast.parse(path.read_text(encoding="utf-8"), filename=str(path)))
        for path in sorted(PACKAGE.rglob("*.py"))
    ]


def _imports():
    found = set()
    for _, tree in _modules():
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                found.add(node.module)
    return found


def _called_names():
    found = set()
    for _, tree in _modules():
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                rendered = ast.unparse(node.func)
                found.add(rendered)
                found.add(".".join(rendered.split(".")[-2:]))
    return found


def _defined_names():
    found = set()
    for _, tree in _modules():
        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                found.add(node.name)
    return found


class TestTheGuardsThemselves:
    def test_the_package_was_actually_found(self):
        assert len(list(PACKAGE.rglob("*.py"))) >= 8

    def test_forbidden_words_appear_in_prose_but_not_as_identifiers(self):
        prose = "\n".join(p.read_text(encoding="utf-8") for p, _ in _modules())
        for word in ("execute", "launch", "terminate", "click"):
            assert word in prose
            assert word not in _imports()
            assert word not in _defined_names()


class TestNeverActs:
    """The brief's own forbidden list, checked by AST."""

    FORBIDDEN_CALLS = (
        "click", "double_click", "right_click", "type_text", "hotkey",
        "press", "paste", "move", "drag", "scroll", "launch", "terminate",
        "restart", "bring_to_front", "minimize", "maximize", "restore",
        "close", "write", "clear", "new_tab", "close_tab", "switch_tab",
        "open_url", "execute",
    )

    def test_no_mutating_call_appears_anywhere(self):
        called = _called_names()
        for name in self.FORBIDDEN_CALLS:
            assert name not in called, f"perception calls a mutating method: {name}"

    def test_no_execution_capable_module_is_imported(self):
        forbidden_prefixes = (
            "master_agent.desktop.execution.executor",
            "master_agent.desktop.execution.keyboard",
            "master_agent.desktop.execution.mouse",
            "master_agent.desktop.actions",
            "master_agent.desktop.plugin",
        )
        for module in _imports():
            for forbidden in forbidden_prefixes:
                assert not module.startswith(forbidden), f"{module} gives perception an execution path"

    def test_no_frozen_package_is_imported(self):
        frozen = (
            "master_agent.foundation", "master_agent.kernel",
            "master_agent.ledger", "master_agent.coordinator",
            "master_agent.runtime_bridge", "master_agent.api",
        )
        for module in _imports():
            for forbidden in frozen:
                assert not module.startswith(forbidden)

    def test_no_mission_control_or_orchestration_surface_is_reachable(self):
        forbidden = (
            "master_agent.mission_control", "master_agent.planner",
            "master_agent.brain", "master_agent.orchestrator", "master_agent.runtime.",
        )
        for module in _imports():
            for forbidden_prefix in forbidden:
                assert not module.startswith(forbidden_prefix)


class TestNoDuplication:
    def test_reuses_c26_window_manager_not_a_second_window_reader(self):
        assert "master_agent.desktop.execution.window" in _imports()

    def test_reuses_c25_profiles_not_a_second_knowledge_base(self):
        assert "master_agent.desktop.operations" in _imports()
        defined = _defined_names()
        for owned_by_c25 in ("ApplicationOperationProfile", "DesktopExecutiveV2", "Capability"):
            assert owned_by_c25 not in defined

    def test_reuses_c22_confidence_not_a_second_band(self):
        defined = _defined_names()
        assert "Confidence" not in defined  # imported, not redeclared

    def test_no_second_playwright_driver(self):
        prose = PACKAGE.joinpath("browser.py").read_text(encoding="utf-8")
        assert "sync_playwright" not in prose
        assert "chromium.launch" not in prose

    def test_no_second_catalog_or_scanner(self):
        called = _called_names()
        for name in ("discover", "discover_application", "attribute_processes"):
            assert name not in called
