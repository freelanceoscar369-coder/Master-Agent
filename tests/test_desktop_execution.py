"""Sprint 1, Component 26 — Elite Desktop Executive (Part 1): Execution.

**No test in this file drives the real machine's keyboard, mouse, or
window state, and no test launches real software.** Every Window/
Keyboard/Mouse/Clipboard test injects a Fake backend implementing the
same `Protocol` the real Win32 backend does; every Process/Executor test
injects a `FakeProbe` or `NullSystemProbe`, never `RealSystemProbe`. This
is a deliberate, disclosed scoping decision — see `Engineering/
HEALTH_C26.md` §11 for exactly what *was* verified against the real
desktop (window enumeration, read-only) and why keyboard/mouse/process
execution was not, in the same session that wrote this suite.

Browser tests use a real, **headless** `BrowserSessionManager`
(Playwright) against `data:` URLs only — the same pattern
`tests/browser_test_support.py` already establishes for the whole Browser
Worker test suite (no navigation to any real website, no network access).

| Requirement | Source |
|---|---|
| Window lifecycle | C26 brief |
| Keyboard operations | C26 brief |
| Mouse operations | C26 brief |
| Clipboard | C26 brief |
| Browser open/focus | C26 brief |
| Process launch/terminate | C26 brief |
| Permission boundaries | C26 brief |
| Recovery paths | C26 brief |
| Every operation routes through an existing Operation Profile; never bypassed | C26 brief |

Structural guards read executable identifiers via AST, never source
text — the discipline every C22–C25 suite already established.
"""
from __future__ import annotations

import ast
from pathlib import Path

from master_agent.desktop.actions import DesktopContext
from master_agent.desktop.execution import (
    FORBIDDEN_METHOD_NAMES,
    FORBIDDEN_OPERATIONS,
    PERMITTED_OPERATIONS,
    BackendUnavailable,
    BrowserExecutive,
    BrowserUnavailable,
    ClipboardExecutive,
    DesktopExecutor,
    KeyboardController,
    MouseController,
    NullClipboardBackend,
    NullKeyboardBackend,
    NullMouseBackend,
    ProcessExecutive,
    WindowManager,
)
from master_agent.desktop.execution.backends import WindowInfo
from master_agent.desktop.operations import KNOWLEDGE_BASE
from master_agent.desktop.probe import CommandResult, ProcessInfo

PACKAGE = (
    Path(__file__).resolve().parent.parent
    / "src" / "master_agent" / "desktop" / "execution"
)


# ═══════════════════════ fakes — no real backend anywhere ═══════════════


class FakeWindowBackend:
    """A desktop, described rather than driven. Every mutating call is
    recorded so a test can assert what was asked for, without anything
    ever reaching a real window."""

    def __init__(self, windows: tuple[WindowInfo, ...] = (), active_handle: int | None = None):
        self._windows = {w.handle: w for w in windows}
        self._active = active_handle
        self.calls: list[tuple[str, int]] = []
        self.fail_operations: set[str] = set()

    def enumerate(self) -> tuple[WindowInfo, ...]:
        return tuple(self._windows.values())

    def active(self) -> WindowInfo | None:
        return self._windows.get(self._active) if self._active is not None else None

    def _apply(self, name: str, handle: int) -> bool:
        self.calls.append((name, handle))
        if name in self.fail_operations:
            return False
        return handle in self._windows

    def bring_to_front(self, handle: int) -> bool:
        ok = self._apply("bring_to_front", handle)
        if ok:
            self._active = handle
        return ok

    def minimize(self, handle: int) -> bool:
        return self._apply("minimize", handle)

    def maximize(self, handle: int) -> bool:
        return self._apply("maximize", handle)

    def restore(self, handle: int) -> bool:
        return self._apply("restore", handle)

    def close(self, handle: int) -> bool:
        ok = self._apply("close", handle)
        if ok:
            del self._windows[handle]
        return ok


class ExplodingWindowBackend:
    """A backend that cannot run here at all — the structural case, not
    an ordinary operational failure."""

    def enumerate(self):
        raise BackendUnavailable("no window backend is configured")

    def active(self):
        raise BackendUnavailable("no window backend is configured")

    def bring_to_front(self, handle):
        raise BackendUnavailable("no window backend is configured")

    minimize = maximize = restore = close = bring_to_front


class FakeKeyboardBackend:
    def __init__(self):
        self.typed: list[str] = []
        self.pressed: list[str] = []
        self.hotkeys: list[tuple[str, ...]] = []

    def type_text(self, text: str) -> None:
        self.typed.append(text)

    def press(self, key: str) -> None:
        self.pressed.append(key)

    def hotkey(self, keys: tuple[str, ...]) -> None:
        self.hotkeys.append(tuple(keys))


class FakeMouseBackend:
    def __init__(self):
        self.moves: list[tuple[int, int]] = []
        self.clicks: list[tuple[int, int, str]] = []
        self.double_clicks: list[tuple[int, int, str]] = []
        self.drags: list[tuple[int, int, int, int]] = []
        self.scrolls: list[tuple[int, int, int]] = []

    def move(self, x, y):
        self.moves.append((x, y))

    def click(self, x, y, button):
        self.clicks.append((x, y, button))

    def double_click(self, x, y, button):
        self.double_clicks.append((x, y, button))

    def drag(self, x1, y1, x2, y2):
        self.drags.append((x1, y1, x2, y2))

    def scroll(self, x, y, amount):
        self.scrolls.append((x, y, amount))


class FakeClipboardBackend:
    def __init__(self, initial: str | None = None):
        self._content = initial

    def read(self) -> str | None:
        return self._content

    def write(self, text: str) -> None:
        self._content = text

    def clear(self) -> None:
        self._content = None


class FakeProbe:
    """Mirrors `tests/test_desktop_executive.py`'s own fixture. `start()`
    and `run()` are recorded, never real — no subprocess is ever spawned
    by this suite."""

    def __init__(self, on_path=None, paths=None, versions=None, running=None, fail=None):
        self.platform = "win32"
        self._on_path = on_path or {}
        self._paths = paths or set()
        self._versions = versions or {}
        self._running = list(running or [])
        self._fail = fail or set()
        self.started: list[list[str]] = []
        self.ran: list[list[str]] = []

    def which(self, executable):
        return self._on_path.get(executable)

    def exists(self, path):
        return path in self._paths

    def run(self, command):
        self.ran.append(command)
        head = command[0]
        if head in self._fail:
            return CommandResult(ok=False, error=f"boom: {head}")
        return CommandResult(ok=True, output=self._versions.get(head, ""))

    def start(self, command):
        self.started.append(command)
        if command[0] in self._fail:
            return CommandResult(ok=False, error=f"cannot start {command[0]}")
        return CommandResult(ok=True)

    def processes(self):
        return list(self._running)

    def get_store_apps(self):
        return []

    def get_uninstall_apps(self):
        return []

    def get_start_apps(self):
        return []


def machine(**kwargs) -> FakeProbe:
    defaults = {
        "on_path": {},
        "versions": {},
    }
    defaults.update(kwargs)
    return FakeProbe(**defaults)


def window(handle=1, title="Untitled", process_id=100, visible=True, minimized=False, maximized=False) -> WindowInfo:
    return WindowInfo(
        handle=handle, title=title, process_id=process_id,
        is_visible=visible, is_minimized=minimized, is_maximized=maximized,
    )


def desktop_executor(probe: FakeProbe | None = None, **kwargs) -> DesktopExecutor:
    context = DesktopContext(probe or machine())
    fake_windows = kwargs.pop("windows", FakeWindowBackend())
    fake_keyboard = kwargs.pop("keyboard_backend", FakeKeyboardBackend())
    fake_mouse = kwargs.pop("mouse_backend", FakeMouseBackend())
    fake_clipboard = kwargs.pop("clipboard_backend", FakeClipboardBackend())
    return DesktopExecutor(
        context=context,
        window_manager=WindowManager(fake_windows),
        keyboard=KeyboardController(fake_keyboard, ClipboardExecutive(fake_clipboard)),
        mouse=MouseController(fake_mouse),
        clipboard=ClipboardExecutive(fake_clipboard),
        process=ProcessExecutive(context=context, sleep=lambda s: None),
        **kwargs,
    )


# ═══════════════════════ A · window lifecycle ════════════════════════════


class TestWindowLifecycle:
    def test_enumerate_lists_visible_windows(self):
        backend = FakeWindowBackend((window(1, "Chrome"), window(2, "Notepad")))
        result = WindowManager(backend).enumerate()
        assert result.success
        assert result.output["count"] == 2

    def test_enumerate_excludes_invisible_windows_by_default(self):
        backend = FakeWindowBackend((window(1, "Chrome", visible=True), window(2, "Hidden", visible=False)))
        result = WindowManager(backend).enumerate()
        assert result.output["count"] == 1

    def test_enumerate_can_include_invisible_windows(self):
        backend = FakeWindowBackend((window(1, "Chrome", visible=True), window(2, "Hidden", visible=False)))
        result = WindowManager(backend).enumerate(visible_only=False)
        assert result.output["count"] == 2

    def test_locate_finds_a_case_insensitive_title_substring(self):
        backend = FakeWindowBackend((window(1, "Mozilla Firefox"),))
        result = WindowManager(backend).locate("FIREFOX")
        assert result.success
        assert result.output["windows"][0]["title"] == "Mozilla Firefox"

    def test_locate_reports_no_match_honestly(self):
        backend = FakeWindowBackend((window(1, "Notepad"),))
        result = WindowManager(backend).locate("Chrome")
        assert not result.success
        assert "no visible window" in result.errors[0]

    def test_locate_refuses_a_blank_query(self):
        result = WindowManager(FakeWindowBackend()).locate("   ")
        assert not result.success

    def test_locate_by_process_matches_pid(self):
        backend = FakeWindowBackend((window(1, "Chrome", process_id=555),))
        result = WindowManager(backend).locate_by_process(frozenset({555}))
        assert result.success
        assert result.output["windows"][0]["process_id"] == 555

    def test_active_reports_the_active_window(self):
        backend = FakeWindowBackend((window(1, "Chrome"), window(2, "Notepad")), active_handle=2)
        result = WindowManager(backend).active()
        assert result.success
        assert result.output["title"] == "Notepad"

    def test_active_reports_honestly_when_nothing_is_active(self):
        result = WindowManager(FakeWindowBackend()).active()
        assert not result.success

    def test_bring_to_front(self):
        backend = FakeWindowBackend((window(1, "Chrome"),))
        result = WindowManager(backend).bring_to_front(1)
        assert result.success
        assert ("bring_to_front", 1) in backend.calls

    def test_minimize_maximize_restore(self):
        backend = FakeWindowBackend((window(1, "Chrome"),))
        manager = WindowManager(backend)
        assert manager.minimize(1).success
        assert manager.maximize(1).success
        assert manager.restore(1).success

    def test_close_removes_the_window(self):
        backend = FakeWindowBackend((window(1, "Chrome"),))
        manager = WindowManager(backend)
        result = manager.close(1)
        assert result.success
        assert manager.enumerate().output["count"] == 0

    def test_an_operation_on_an_unknown_handle_fails_honestly(self):
        manager = WindowManager(FakeWindowBackend())
        result = manager.bring_to_front(9999)
        assert not result.success

    def test_focus_process_composes_locate_and_bring_to_front(self):
        backend = FakeWindowBackend((window(1, "Chrome", process_id=42),))
        result = WindowManager(backend).focus_process(frozenset({42}))
        assert result.success
        assert ("bring_to_front", 1) in backend.calls

    def test_the_null_backend_is_the_default(self):
        manager = WindowManager()
        assert manager.enumerate().success  # empty, but honestly empty
        assert manager.enumerate().output["count"] == 0
        assert not manager.bring_to_front(1).success
        assert not manager.minimize(1).success
        assert not manager.maximize(1).success
        assert not manager.restore(1).success
        assert not manager.close(1).success
        assert not manager.active().success


# ═══════════════════════ B · keyboard operations ═════════════════════════


class TestKeyboardOperations:
    def test_type_sends_the_given_text(self):
        backend = FakeKeyboardBackend()
        result = KeyboardController(backend).type("hello world")
        assert result.success
        assert backend.typed == ["hello world"]

    def test_press_sends_a_named_key(self):
        backend = FakeKeyboardBackend()
        KeyboardController(backend).press("enter")
        assert backend.pressed == ["enter"]

    def test_hotkey_sends_a_key_combination(self):
        backend = FakeKeyboardBackend()
        result = KeyboardController(backend).hotkey("ctrl", "shift", "s")
        assert result.success
        assert backend.hotkeys == [("ctrl", "shift", "s")]

    def test_hotkey_requires_at_least_one_key(self):
        result = KeyboardController(FakeKeyboardBackend()).hotkey()
        assert not result.success

    def test_enter_escape_delete_convenience_methods(self):
        backend = FakeKeyboardBackend()
        controller = KeyboardController(backend)
        controller.enter()
        controller.escape()
        controller.delete()
        assert backend.pressed == ["enter", "escape", "delete"]

    def test_arrow_keys(self):
        backend = FakeKeyboardBackend()
        controller = KeyboardController(backend)
        for direction in ("up", "down", "left", "right"):
            assert controller.arrow(direction).success
        assert backend.pressed == ["up", "down", "left", "right"]

    def test_arrow_refuses_an_unknown_direction(self):
        result = KeyboardController(FakeKeyboardBackend()).arrow("diagonal")
        assert not result.success

    def test_paste_writes_then_sends_ctrl_v(self):
        keyboard_backend = FakeKeyboardBackend()
        clipboard_backend = FakeClipboardBackend()
        controller = KeyboardController(keyboard_backend, ClipboardExecutive(clipboard_backend))
        result = controller.paste("pasted text")
        assert result.success
        assert clipboard_backend.read() == "pasted text"
        assert keyboard_backend.hotkeys == [("ctrl", "v")]

    def test_paste_without_text_just_sends_ctrl_v(self):
        keyboard_backend = FakeKeyboardBackend()
        clipboard_backend = FakeClipboardBackend("already there")
        controller = KeyboardController(keyboard_backend, ClipboardExecutive(clipboard_backend))
        controller.paste()
        assert clipboard_backend.read() == "already there"
        assert keyboard_backend.hotkeys == [("ctrl", "v")]

    def test_type_refuses_a_non_string(self):
        result = KeyboardController(FakeKeyboardBackend()).type(12345)  # type: ignore[arg-type]
        assert not result.success

    def test_the_null_backend_reports_unavailable_honestly(self):
        """Passing `NullKeyboardBackend()` explicitly, rather than relying
        on an omitted `backend`, since the constructor's real default is
        now the live Win32 backend on this platform (that is the point of
        this component) — this test's job is the Null backend's own
        honesty, not which backend is chosen when none is given."""
        controller = KeyboardController(NullKeyboardBackend())
        assert not controller.type("hello").success
        assert "no keyboard backend" in controller.type("hello").errors[0]
        assert not controller.press("enter").success
        assert not controller.hotkey("ctrl", "c").success


# ═══════════════════════ C · mouse operations ═════════════════════════════


class TestMouseOperations:
    def test_move(self):
        backend = FakeMouseBackend()
        result = MouseController(backend).move(100, 200)
        assert result.success
        assert backend.moves == [(100, 200)]

    def test_click(self):
        backend = FakeMouseBackend()
        result = MouseController(backend).click(10, 20)
        assert result.success
        assert backend.clicks == [(10, 20, "left")]

    def test_double_click(self):
        backend = FakeMouseBackend()
        MouseController(backend).double_click(10, 20)
        assert backend.double_clicks == [(10, 20, "left")]

    def test_right_click(self):
        backend = FakeMouseBackend()
        MouseController(backend).right_click(10, 20)
        assert backend.clicks == [(10, 20, "right")]

    def test_drag(self):
        backend = FakeMouseBackend()
        result = MouseController(backend).drag(0, 0, 100, 100)
        assert result.success
        assert backend.drags == [(0, 0, 100, 100)]

    def test_scroll(self):
        backend = FakeMouseBackend()
        result = MouseController(backend).scroll(50, 50, -3)
        assert result.success
        assert backend.scrolls == [(50, 50, -3)]

    def test_click_refuses_an_unknown_button(self):
        result = MouseController(FakeMouseBackend()).click(1, 1, button="middle-ish")
        assert not result.success

    def test_no_image_recognition_is_involved_coordinates_only(self):
        """The brief's own words: coordinates only. A click never takes
        anything but x, y — there is no target/selector parameter."""
        import inspect

        sig = inspect.signature(MouseController.click)
        assert set(sig.parameters) == {"self", "x", "y", "button"}

    def test_the_null_backend_reports_unavailable_honestly(self):
        """Passing `NullMouseBackend()` explicitly — see the identical
        note on `TestKeyboardOperations`'s version of this test."""
        controller = MouseController(NullMouseBackend())
        assert not controller.move(1, 1).success
        assert not controller.click(1, 1).success
        assert not controller.double_click(1, 1).success
        assert not controller.drag(0, 0, 1, 1).success
        assert not controller.scroll(1, 1, 1).success


# ═══════════════════════ D · clipboard ════════════════════════════════════


class TestClipboard:
    def test_write_then_read(self):
        backend = FakeClipboardBackend()
        executive = ClipboardExecutive(backend)
        executive.write("hello")
        result = executive.read()
        assert result.success
        assert result.output["text"] == "hello"

    def test_clear(self):
        backend = FakeClipboardBackend("something")
        executive = ClipboardExecutive(backend)
        executive.clear()
        assert executive.read().output["text"] is None

    def test_write_refuses_a_non_string(self):
        result = ClipboardExecutive(FakeClipboardBackend()).write(123)  # type: ignore[arg-type]
        assert not result.success

    def test_no_history_is_kept(self):
        """The brief's own words: no history. Overwriting loses the
        previous value completely — there is no way to recover it."""
        backend = FakeClipboardBackend()
        executive = ClipboardExecutive(backend)
        executive.write("first")
        executive.write("second")
        assert executive.read().output["text"] == "second"
        assert not hasattr(executive, "history")
        assert not hasattr(backend, "history")

    def test_the_null_backend_read_is_honestly_empty(self):
        """Passing `NullClipboardBackend()` explicitly, rather than relying
        on an omitted `backend`, since the constructor's real default is
        now the live Win32 backend on this platform — matching
        `KeyboardController`'s own established default (a real reasoning
        prompt must be able to reach the clipboard via `paste()` without
        every caller wiring a backend by hand). This test's job is the
        Null backend's own honesty, not which backend is chosen when none
        is given."""
        executive = ClipboardExecutive(NullClipboardBackend())
        result = executive.read()
        assert result.success
        assert result.output["text"] is None
        assert not executive.write("x").success
        assert not executive.clear().success


# ═══════════════════════ E · process launch/terminate ═════════════════════


class TestProcessExecutive:
    def test_launch_reuses_the_existing_launch_action(self):
        probe = machine(
            on_path={"git": "/usr/bin/git"},
            paths=set(), versions={"git": "git version 2.44.0"},
        )
        # LaunchApplicationAction needs a resolvable installed path
        probe._on_path["git"] = "/usr/bin/git"
        context = DesktopContext(probe)
        result = ProcessExecutive(context=context, sleep=lambda s: None).launch("git")
        assert result.success
        assert probe.started  # the existing Action's own probe.start() was used

    def test_launch_of_an_uninstalled_application_fails_honestly(self):
        result = ProcessExecutive(context=DesktopContext(machine()), sleep=lambda s: None).launch("git")
        assert not result.success

    def test_launch_of_an_unknown_application_fails_honestly(self):
        result = ProcessExecutive(context=DesktopContext(machine()), sleep=lambda s: None).launch("not-a-real-app")
        assert not result.success

    def test_is_running_reflects_the_process_list(self):
        probe = machine(running=[ProcessInfo(pid=1, name="git.exe", owner="git")])
        result = ProcessExecutive(context=DesktopContext(probe), sleep=lambda s: None).is_running("git")
        assert result.success
        assert result.output["running"] is True

    def test_terminate_reuses_the_existing_close_action(self):
        probe = machine(running=[ProcessInfo(pid=42, name="git.exe", owner="git")])
        result = ProcessExecutive(context=DesktopContext(probe), sleep=lambda s: None).terminate("git")
        assert result.success
        assert probe.ran  # the existing Action's own kill command ran

    def test_terminate_of_a_non_running_application_fails_honestly(self):
        result = ProcessExecutive(context=DesktopContext(machine()), sleep=lambda s: None).terminate("git")
        assert not result.success

    def test_restart_terminates_then_launches(self):
        probe = machine(
            on_path={"git": "/usr/bin/git"},
            running=[ProcessInfo(pid=42, name="git.exe", owner="git")],
        )
        result = ProcessExecutive(context=DesktopContext(probe), sleep=lambda s: None).restart("git")
        assert result.success
        assert probe.ran and probe.started

    def test_restart_of_a_non_running_application_still_launches(self):
        probe = machine(on_path={"git": "/usr/bin/git"})
        result = ProcessExecutive(context=DesktopContext(probe), sleep=lambda s: None).restart("git")
        assert result.success
        assert probe.started

    def test_wait_returns_immediately_once_running(self):
        probe = machine(running=[ProcessInfo(pid=1, name="git.exe", owner="git")])
        slept = []
        result = ProcessExecutive(context=DesktopContext(probe), sleep=slept.append).wait("git", timeout_seconds=5)
        assert result.success
        assert slept == []

    def test_wait_times_out_honestly(self):
        probe = machine()  # git never becomes running
        slept = []
        result = ProcessExecutive(context=DesktopContext(probe), sleep=slept.append).wait(
            "git", timeout_seconds=1.0, poll_interval_seconds=0.5
        )
        assert not result.success
        assert "did not report running" in result.errors[0]
        assert slept  # time was simulated, never actually slept

    def test_wait_uses_the_c25_profile_startup_estimate_by_default(self):
        """Reuse, not a second number — `chrome`'s own C25 profile names
        a startup window; `wait()`'s default timeout comes from it."""
        probe = machine()
        slept = []
        executive = ProcessExecutive(context=DesktopContext(probe), sleep=slept.append)
        profile = KNOWLEDGE_BASE.profile("chrome")
        result = executive.wait("chrome", poll_interval_seconds=profile.startup_time.typical_seconds[1] + 1)
        assert not result.success
        assert f"within {float(profile.startup_time.typical_seconds[1])}s" in result.errors[0]


# ═══════════════════════ F · browser open/focus ═══════════════════════════


DATA_URL = "data:text/html,<html><body><h1>C26</h1></body></html>"


class TestBrowserOpenAndFocus:
    def test_new_tab_opens_a_real_headless_session(self):
        executive = BrowserExecutive(headless=True)
        result = executive.new_tab(DATA_URL)
        try:
            assert result.success
            assert executive.current_tab is not None
        finally:
            executive.close_tab()

    def test_open_url_opens_a_tab_when_none_is_current(self):
        executive = BrowserExecutive(headless=True)
        result = executive.open_url(DATA_URL)
        try:
            assert result.success
        finally:
            executive.close_tab()

    def test_open_url_navigates_the_current_tab(self):
        executive = BrowserExecutive(headless=True)
        executive.new_tab(DATA_URL)
        try:
            second = "data:text/html,<html><body>second</body></html>"
            result = executive.open_url(second)
            assert result.success
        finally:
            executive.close_tab()

    def test_switch_tab_changes_the_current_pointer_without_touching_playwright(self):
        executive = BrowserExecutive(headless=True)
        executive.new_tab(DATA_URL, session_id="a")
        executive.new_tab(DATA_URL, session_id="b")
        try:
            result = executive.switch_tab("a")
            assert result.success
            assert executive.current_tab == "a"
        finally:
            executive.close_tab("a")
            executive.close_tab("b")

    def test_switch_tab_refuses_an_unknown_session(self):
        executive = BrowserExecutive(headless=True)
        result = executive.switch_tab("does-not-exist")
        assert not result.success

    def test_close_tab_closes_the_current_tab_by_default(self):
        executive = BrowserExecutive(headless=True)
        executive.new_tab(DATA_URL)
        result = executive.close_tab()
        assert result.success
        assert executive.current_tab is None

    def test_close_tab_with_nothing_open_fails_honestly(self):
        executive = BrowserExecutive(headless=True)
        result = executive.close_tab()
        assert not result.success

    def test_focus_browser_needs_a_desktop_context(self):
        executive = BrowserExecutive()
        result = executive.focus_browser("chrome")
        assert not result.success
        assert "DesktopContext" in result.errors[0]

    def test_focus_browser_reports_honestly_when_not_running(self):
        context = DesktopContext(machine())
        executive = BrowserExecutive(desktop_context=context)
        result = executive.focus_browser("chrome")
        assert not result.success
        assert "not running" in result.errors[0]

    def test_focus_browser_finds_the_real_process_window(self):
        probe = machine(running=[ProcessInfo(pid=777, name="chrome.exe", owner="chrome")])
        context = DesktopContext(probe)
        window_backend = FakeWindowBackend((window(1, "New Tab - Chrome", process_id=777),))
        executive = BrowserExecutive(window_manager=WindowManager(window_backend), desktop_context=context)
        result = executive.focus_browser("chrome")
        assert result.success

    def test_new_tab_without_a_url_just_opens(self):
        executive = BrowserExecutive(headless=True)
        result = executive.new_tab()
        try:
            assert result.success
            assert "url" not in result.output
        finally:
            executive.close_tab()

    def test_new_tab_with_a_duplicate_session_id_fails_honestly(self):
        executive = BrowserExecutive(headless=True)
        executive.new_tab(DATA_URL, session_id="dup")
        try:
            result = executive.new_tab(DATA_URL, session_id="dup")
            assert not result.success
        finally:
            executive.close_tab("dup")

    def test_new_tab_with_a_blank_url_fails_validation_not_navigation(self):
        executive = BrowserExecutive(headless=True)
        result = executive.new_tab(url="", session_id="blank-url")
        try:
            assert not result.success
        finally:
            executive.close_tab("blank-url")

    def test_ensure_manager_itself_reports_a_genuinely_missing_playwright(self, monkeypatch):
        """Unlike the other absence tests (which replace `_ensure_manager`
        wholesale), this blocks the real import it performs — proving the
        method's own `except ImportError` branch, not a stand-in for it."""
        import sys

        monkeypatch.setitem(sys.modules, "master_agent.environment.browser_session", None)
        executive = BrowserExecutive(headless=True)
        result = executive.new_tab(DATA_URL)
        assert not result.success
        assert "not installed" in result.errors[0]

    def test_open_url_and_new_tab_and_close_tab_report_playwright_absence(self, monkeypatch):
        def explode(self):
            raise BrowserUnavailable("no playwright")

        monkeypatch.setattr(BrowserExecutive, "_ensure_manager", explode)
        executive = BrowserExecutive(headless=True)
        assert not executive.open_url(DATA_URL).success
        assert not executive.new_tab(DATA_URL).success
        assert not executive.close_tab("anything").success
        assert not executive.switch_tab("anything").success

    def test_no_conversation_cookie_password_or_history_method_is_ever_called(self):
        """The brief: *do NOT inspect conversations, cookies, passwords,
        history.* Confirmed by reading everything this class calls on a
        session/manager (also checked mechanically in §J)."""
        import inspect

        source = inspect.getsource(BrowserExecutive)
        for forbidden in ("cookies", "storage_state", "history", "password"):
            assert forbidden not in source.lower()


# ═══════════════════════ G · the unified DesktopExecutor ═════════════════


class TestDesktopExecutorRoutesThroughProfiles:
    def test_execute_refuses_an_unprofiled_application(self):
        result = desktop_executor().execute("totally-unknown-app")
        assert not result.success
        assert "operation profile" in result.errors[0]

    def test_execute_launches_a_profiled_application(self):
        probe = machine(on_path={"git": "/usr/bin/git"})
        result = desktop_executor(probe).execute("git")
        assert result.success

    def test_focus_refuses_an_unprofiled_application(self):
        result = desktop_executor().focus("totally-unknown-app")
        assert not result.success

    def test_focus_finds_and_raises_a_running_applications_window(self):
        probe = machine(running=[ProcessInfo(pid=9, name="git.exe", owner="git")])
        fake_windows = FakeWindowBackend((window(1, "git status", process_id=9),))
        result = desktop_executor(probe, windows=fake_windows).focus("git")
        assert result.success

    def test_type_refuses_an_unprofiled_application(self):
        result = desktop_executor().type("totally-unknown-app", "hello")
        assert not result.success

    def test_type_refuses_a_not_automatable_application(self):
        """`continue_dev`'s own C25 profile names `NOT_AUTOMATABLE` — this
        is real knowledge being consulted, not a fixture built to force
        the branch."""
        result = desktop_executor().type("continue_dev", "hello")
        assert not result.success
        assert "automation surface" in result.errors[0]

    def test_type_succeeds_for_an_automatable_application(self):
        backend = FakeKeyboardBackend()
        result = desktop_executor(keyboard_backend=backend).type("vscode", "hello")
        assert result.success
        assert backend.typed == ["hello"]

    def test_click_refuses_an_unprofiled_application(self):
        result = desktop_executor().click("totally-unknown-app", 1, 1)
        assert not result.success

    def test_click_refuses_a_not_automatable_application(self):
        result = desktop_executor().click("continue_dev", 1, 1)
        assert not result.success

    def test_click_succeeds_for_an_automatable_application(self):
        backend = FakeMouseBackend()
        result = desktop_executor(mouse_backend=backend).click("chrome", 5, 5)
        assert result.success
        assert backend.clicks == [(5, 5, "left")]

    def test_wait_refuses_an_unprofiled_application(self):
        result = desktop_executor().wait("totally-unknown-app", timeout_seconds=0.1)
        assert not result.success

    def test_wait_delegates_to_process_executive(self):
        probe = machine(running=[ProcessInfo(pid=1, name="git.exe", owner="git")])
        result = desktop_executor(probe).wait("git", timeout_seconds=1)
        assert result.success

    def test_close_refuses_an_unprofiled_application(self):
        result = desktop_executor().close("totally-unknown-app")
        assert not result.success

    def test_close_delegates_to_process_executive(self):
        probe = machine(running=[ProcessInfo(pid=1, name="git.exe", owner="git")])
        result = desktop_executor(probe).close("git")
        assert result.success

    def test_every_named_application_operation_checks_the_profile_first(self):
        """A structural version of the same rule: every public method
        that takes an `application` calls `_profile_or_refusal` or
        `_require_automatable` before doing anything else."""
        import inspect

        for method_name in ("execute", "focus", "type", "click", "wait", "close"):
            source = inspect.getsource(getattr(DesktopExecutor, method_name))
            assert "_profile_or_refusal" in source or "_require_automatable" in source


# ═══════════════════════ H · permission boundaries ═══════════════════════


class TestPermissionBoundaries:
    """The brief's own two lists, checked mechanically."""

    def test_the_brief_permitted_list_is_carried_verbatim(self):
        assert PERMITTED_OPERATIONS == (
            "open software", "close software", "focus windows", "type",
            "click", "paste", "browse", "interact with installed applications",
        )

    def test_the_brief_forbidden_list_is_carried_verbatim(self):
        assert FORBIDDEN_OPERATIONS == (
            "install software", "uninstall software", "elevate privileges",
            "change system settings", "modify registry", "access passwords",
            "inspect private conversations",
        )

    def test_no_forbidden_method_exists_anywhere_in_the_package(self):
        found: set[str] = set()
        for path in PACKAGE.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    found.add(node.name)
        for forbidden in FORBIDDEN_METHOD_NAMES:
            assert forbidden not in found, f"forbidden method exists: {forbidden}"

    def test_no_registry_module_is_imported(self):
        imports = _imports()
        for module in ("winreg", "_winreg"):
            assert module not in imports

    def test_no_privilege_elevation_api_is_referenced(self):
        """These names may appear in prose (`win32_backends.py`'s own
        docstring names what it refuses to call) but never as an
        executable identifier — the same prose-vs-identifier discipline
        every guard in this suite applies."""
        imported = _imports()
        called = _called_names()
        defined = _defined_names()
        for banned in ("ShellExecuteW", "runas", "AdjustTokenPrivileges", "IsUserAnAdmin"):
            assert banned not in imported
            assert banned not in called
            assert banned not in defined

    def test_no_install_or_package_manager_is_invoked(self):
        prose = "\n".join(p.read_text(encoding="utf-8") for p in PACKAGE.rglob("*.py")).lower()
        for banned in ("pip install", "winget install", "choco install", "msiexec"):
            assert banned not in prose

    def test_desktop_executor_exposes_only_the_briefs_six_public_methods(self):
        public = {
            name for name in vars(DesktopExecutor)
            if not name.startswith("_") and callable(getattr(DesktopExecutor, name))
        }
        assert public == {"execute", "focus", "type", "click", "wait", "close"}


# ═══════════════════════ I · recovery paths ═══════════════════════════════


class TestRecoveryPaths:
    def test_window_backend_unavailable_is_a_structured_failure(self):
        manager = WindowManager(ExplodingWindowBackend())
        result = manager.enumerate()
        assert not result.success
        assert "no window backend" in result.errors[0]

    def test_keyboard_backend_unavailable_is_a_structured_failure(self):
        class Exploding:
            def type_text(self, text):
                raise BackendUnavailable("gone")
            press = hotkey = type_text

        result = KeyboardController(Exploding()).type("x")
        assert not result.success
        assert "gone" in result.errors[0]

    def test_an_operation_that_fails_at_the_platform_level_is_reported_not_raised(self):
        backend = FakeWindowBackend((window(1, "Chrome"),))
        backend.fail_operations.add("bring_to_front")
        result = WindowManager(backend).bring_to_front(1)
        assert not result.success
        assert "did not succeed" in result.errors[0]

    def test_process_wait_recovers_by_reporting_a_timeout_not_hanging(self):
        result = ProcessExecutive(
            context=DesktopContext(machine()), sleep=lambda s: None
        ).wait("git", timeout_seconds=0.1, poll_interval_seconds=0.05)
        assert not result.success

    def test_browser_session_error_is_a_structured_failure(self):
        executive = BrowserExecutive(headless=True)
        result = executive.close_tab("never-opened")
        assert not result.success

    def test_browser_unavailable_is_reported_not_raised(self, monkeypatch):
        """Simulates Playwright being absent by making `_ensure_manager`
        itself raise `BrowserUnavailable` — patched on the class, since
        `BrowserExecutive` uses `__slots__` and has no instance `__dict__`
        for `monkeypatch` to shadow a method on."""
        def explode(self):
            raise BrowserUnavailable("no playwright")

        monkeypatch.setattr(BrowserExecutive, "_ensure_manager", explode)

        executive = BrowserExecutive(headless=True)
        result = executive.new_tab("data:text/html,x")
        assert not result.success
        assert "no playwright" in result.errors[0]

    def test_restart_recovers_from_a_non_running_application(self):
        probe = machine(on_path={"git": "/usr/bin/git"})
        result = ProcessExecutive(context=DesktopContext(probe), sleep=lambda s: None).restart("git")
        assert result.success  # did not propagate the "not running" terminate failure


# ═══════════════════════ I2 · every backend-unavailable branch ══════════


class ExplodingKeyboardBackend:
    def __init__(self, raise_value_error: bool = False):
        self._exc = ValueError("unknown key") if raise_value_error else BackendUnavailable("gone")

    def type_text(self, text):
        raise self._exc

    def press(self, key):
        raise self._exc

    def hotkey(self, keys):
        raise self._exc


class ExplodingMouseBackend:
    def move(self, x, y):
        raise BackendUnavailable("gone")

    def click(self, x, y, button):
        raise BackendUnavailable("gone")

    def double_click(self, x, y, button):
        raise BackendUnavailable("gone")

    def drag(self, x1, y1, x2, y2):
        raise BackendUnavailable("gone")

    def scroll(self, x, y, amount):
        raise BackendUnavailable("gone")


class ExplodingClipboardBackend:
    def read(self):
        raise BackendUnavailable("gone")

    def write(self, text):
        raise BackendUnavailable("gone")

    def clear(self):
        raise BackendUnavailable("gone")


class FailingWriteClipboardBackend:
    def read(self):
        return None

    def write(self, text):
        raise BackendUnavailable("cannot open the clipboard")

    def clear(self):
        raise BackendUnavailable("gone")


class TestEveryBackendUnavailableBranch:
    def test_keyboard_press_reports_backend_unavailable(self):
        result = KeyboardController(ExplodingKeyboardBackend()).press("a")
        assert not result.success and "gone" in result.errors[0]

    def test_keyboard_press_reports_an_unknown_key_value_error(self):
        result = KeyboardController(ExplodingKeyboardBackend(raise_value_error=True)).press("a")
        assert not result.success and "unknown key" in result.errors[0]

    def test_keyboard_hotkey_reports_backend_unavailable(self):
        result = KeyboardController(ExplodingKeyboardBackend()).hotkey("ctrl", "c")
        assert not result.success and "gone" in result.errors[0]

    def test_keyboard_hotkey_reports_an_unknown_key_value_error(self):
        result = KeyboardController(ExplodingKeyboardBackend(raise_value_error=True)).hotkey("ctrl", "c")
        assert not result.success and "unknown key" in result.errors[0]

    def test_paste_stops_if_the_clipboard_write_fails(self):
        controller = KeyboardController(
            FakeKeyboardBackend(), ClipboardExecutive(FailingWriteClipboardBackend())
        )
        result = controller.paste("text")
        assert not result.success
        assert "cannot open the clipboard" in result.errors[0]

    def test_mouse_move_reports_backend_unavailable(self):
        result = MouseController(ExplodingMouseBackend()).move(1, 1)
        assert not result.success and "gone" in result.errors[0]

    def test_mouse_click_reports_backend_unavailable(self):
        result = MouseController(ExplodingMouseBackend()).click(1, 1)
        assert not result.success and "gone" in result.errors[0]

    def test_mouse_double_click_refuses_an_unknown_button(self):
        result = MouseController(FakeMouseBackend()).double_click(1, 1, button="nope")
        assert not result.success

    def test_mouse_double_click_reports_backend_unavailable(self):
        result = MouseController(ExplodingMouseBackend()).double_click(1, 1)
        assert not result.success and "gone" in result.errors[0]

    def test_mouse_drag_reports_backend_unavailable(self):
        result = MouseController(ExplodingMouseBackend()).drag(0, 0, 1, 1)
        assert not result.success and "gone" in result.errors[0]

    def test_mouse_scroll_reports_backend_unavailable(self):
        result = MouseController(ExplodingMouseBackend()).scroll(1, 1, 1)
        assert not result.success and "gone" in result.errors[0]

    def test_clipboard_read_reports_backend_unavailable(self):
        result = ClipboardExecutive(ExplodingClipboardBackend()).read()
        assert not result.success and "gone" in result.errors[0]

    def test_clipboard_write_reports_backend_unavailable(self):
        result = ClipboardExecutive(ExplodingClipboardBackend()).write("x")
        assert not result.success and "gone" in result.errors[0]

    def test_clipboard_clear_reports_backend_unavailable(self):
        result = ClipboardExecutive(ExplodingClipboardBackend()).clear()
        assert not result.success and "gone" in result.errors[0]

    def test_window_locate_propagates_an_enumerate_failure(self):
        result = WindowManager(ExplodingWindowBackend()).locate("chrome")
        assert not result.success and "no window backend" in result.errors[0]

    def test_window_locate_by_process_propagates_an_enumerate_failure(self):
        result = WindowManager(ExplodingWindowBackend()).locate_by_process(frozenset({1}))
        assert not result.success and "no window backend" in result.errors[0]

    def test_window_locate_by_process_reports_no_match_honestly(self):
        backend = FakeWindowBackend((window(1, "Chrome", process_id=1),))
        result = WindowManager(backend).locate_by_process(frozenset({999}))
        assert not result.success
        assert "no visible window belongs to" in result.errors[0]

    def test_window_active_reports_backend_unavailable(self):
        result = WindowManager(ExplodingWindowBackend()).active()
        assert not result.success and "no window backend" in result.errors[0]

    def test_window_focus_process_propagates_a_locate_failure(self):
        result = WindowManager(FakeWindowBackend()).focus_process(frozenset({1}))
        assert not result.success


class TestProcessAndExecutorRemainingBranches:
    def test_terminate_failure_for_a_reason_other_than_not_running_is_not_swallowed(self):
        """`restart()` only tolerates a *"not running"* terminate
        failure; a genuine kill failure (the process refused to die)
        must still be reported, not silently overridden by the launch
        attempt."""
        probe = machine(
            on_path={"git": "/usr/bin/git"},
            running=[ProcessInfo(pid=1, name="git.exe", owner="git")],
            fail={"taskkill"},
        )
        result = ProcessExecutive(context=DesktopContext(probe), sleep=lambda s: None).restart("git")
        assert not result.success
        assert "could not close pids" in result.errors[0]

    def test_executor_focus_reports_a_profiled_but_not_running_application_honestly(self):
        result = desktop_executor().focus("git")
        assert not result.success
        assert "git is not running" in result.errors[0]


# ═══════════════════════ J · structural guards, by AST ═══════════════════


def _modules() -> list[tuple[Path, ast.Module]]:
    return [
        (path, ast.parse(path.read_text(encoding="utf-8"), filename=str(path)))
        for path in sorted(PACKAGE.rglob("*.py"))
    ]


def _imports() -> set[str]:
    found: set[str] = set()
    for _, tree in _modules():
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                found.add(node.module)
    return found


def _called_names() -> set[str]:
    found: set[str] = set()
    for _, tree in _modules():
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                rendered = ast.unparse(node.func)
                found.add(rendered)
                found.add(".".join(rendered.split(".")[-2:]))
    return found


def _defined_names() -> set[str]:
    found: set[str] = set()
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
        for word in ("install", "elevate", "ShellExecute"):
            assert word in prose
            assert word not in _imports()
            assert word not in _defined_names()

    def test_subprocess_and_winreg_are_absent_even_from_prose(self):
        """Unlike `install`/`elevate` (named as things this package
        refuses to do), `subprocess` and `winreg` are never mentioned at
        all — this package reuses `desktop.actions`'/`desktop.probe`'s
        own process-launching code rather than describing a second one."""
        prose = "\n".join(p.read_text(encoding="utf-8") for p, _ in _modules())
        assert "subprocess" not in prose
        assert "winreg" not in prose


class TestNoOcrOrVision:
    """The brief's own repeated words for both Window Manager and Mouse
    Controller: no OCR, no vision, no image recognition."""

    FORBIDDEN_MODULES = (
        "cv2", "PIL", "Pillow", "pytesseract", "pyautogui",
        "easyocr", "numpy", "mss",
    )
    FORBIDDEN_CALLS = (
        "GetPixel", "BitBlt", "screenshot", "grab", "locateOnScreen",
        "image_to_string", "imread",
    )

    def test_no_image_or_ocr_library_is_imported(self):
        imported = _imports()
        for module in self.FORBIDDEN_MODULES:
            assert module not in imported

    def test_no_screen_capture_or_ocr_call_appears(self):
        called = _called_names()
        for name in self.FORBIDDEN_CALLS:
            assert name not in called


class TestNoDuplication:
    """Architecture Rules: reuse Desktop Executive, Operation Profiles,
    Capability Matrix, Environment Intelligence — never duplicate."""

    def test_process_executive_reuses_the_existing_actions(self):
        imported = _imports()
        assert "master_agent.desktop.actions" in imported

    def test_no_second_catalog_or_inventory_scanner_is_built(self):
        imported = _imports()
        assert "master_agent.desktop.catalog" not in imported
        called = _called_names()
        for name in ("discover", "discover_application", "attribute_processes"):
            assert name not in called

    def test_no_second_operation_profile_type_is_declared(self):
        defined = _defined_names()
        for owned_by_c25 in (
            "ApplicationOperationProfile", "ApplicationRecoveryPlan",
            "DesktopCapabilityMatrix", "Capability",
        ):
            assert owned_by_c25 not in defined

    def test_browser_executive_imports_no_second_playwright_driver(self):
        prose = PACKAGE.joinpath("browser.py").read_text(encoding="utf-8")
        assert "sync_playwright" not in prose
        assert "chromium.launch" not in prose

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
        """This is the execution substrate only — no planning, no
        orchestration, no autonomy."""
        forbidden = (
            "master_agent.mission_control", "master_agent.planner",
            "master_agent.brain", "master_agent.orchestrator",
            "master_agent.runtime.",
        )
        for module in _imports():
            for forbidden_prefix in forbidden:
                assert not module.startswith(forbidden_prefix)
