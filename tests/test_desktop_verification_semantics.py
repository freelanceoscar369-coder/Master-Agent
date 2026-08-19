"""What the Desktop verifier actually observes — not what it is wired to.

The previous round's tests proved wiring *shape*: that a gateway existed,
that it subclassed the right thing, that unsupported capabilities returned
None. Every one of them passed against an implementation with three
semantic defects:

* `process_running = bool(probe.output)` -- and `IsRunningAction` returns
  `{"application": ..., "running": bool, "processes": [...]}`, a dict that
  is never empty. So "is it running" was always True, and
  `launch_application` would have verified MATCHED unconditionally. A
  fabricated pass is precisely the failure this work exists to remove.
* `WindowManager()` -- which defaults to `NullWindowBackend` and observes
  nothing at all on a real desktop.
* `"notepad" in str(active_window)` -- a title guess, wrong in both
  directions: a document window need not name its application, and an
  unrelated window may mention it.

Shape tests cannot catch any of those. These are behaviour tests, driven
through injected read-only observers so they run deterministically without
a desktop.
"""
from __future__ import annotations

from typing import Any

import pytest

from master_agent.desktop.gateway import DesktopGateway, supports
from master_agent.verification.evidence import ExpectedOutcome


class Result:
    """Stands in for `ExecutionResult` as the read-only observers return it."""

    def __init__(self, success: bool, output: Any = None) -> None:
        self.success = success
        self.output = output


class Processes:
    """A stub `ProcessExecutive.is_running`, returning the real output shape."""

    def __init__(self, running: bool | None, pids: list[int] | None = None) -> None:
        self._running = running
        self._pids = pids or []

    def is_running(self, application: str) -> Result:
        if self._running is None:
            return Result(False, None)  # the observation itself failed
        return Result(True, {
            "application": application,
            "running": self._running,
            "processes": [{"pid": pid, "name": application} for pid in self._pids],
        })


class Windows:
    """A stub `WindowManager.active`, returning the real `WindowInfo` shape."""

    def __init__(self, active_pid: int | None, title: str = "") -> None:
        self._pid = active_pid
        self._title = title

    def active(self) -> Result:
        if self._pid is None:
            return Result(False, None)
        return Result(True, {
            "handle": 1, "title": self._title, "process_id": self._pid,
            "is_visible": True, "is_minimized": False, "is_maximized": False,
        })


def verdict(capability, payload, processes, windows) -> str | None:
    gateway = DesktopGateway(plugin=object(), processes=processes, windows=windows)
    evidence = gateway.verify(capability, payload, ExpectedOutcome(description="d"))
    return None if evidence is None else evidence.verdict.value


class TestProcessPresenceIsReadFromTheField:
    """Defect 1. The container is always truthy; the `running` field is not."""

    def test_running_true_is_observed_as_true(self):
        assert verdict(
            "launch_application", {"application": "notepad"},
            Processes(running=True, pids=[100]), Windows(active_pid=100),
        ) == "matched"

    def test_running_false_is_observed_as_false(self):
        """The exact case `bool(probe.output)` got wrong: a non-empty dict
        that reports `running: False`."""
        assert verdict(
            "launch_application", {"application": "notepad"},
            Processes(running=False), Windows(active_pid=None),
        ) != "matched"

    def test_an_unreadable_observation_is_not_a_negative_one(self):
        """"Not running" and "could not find out" are different facts, and
        only the first is evidence of a successful close."""
        assert verdict(
            "close_application", {"application": "notepad"},
            Processes(running=None), Windows(active_pid=None),
        ) != "matched"


class TestLaunchAndClose:

    def test_launch_matches_when_the_application_is_running(self):
        assert verdict(
            "launch_application", {"application": "chrome"},
            Processes(running=True, pids=[42]), Windows(active_pid=42),
        ) == "matched"

    def test_launch_does_not_match_when_nothing_is_running(self):
        assert verdict(
            "launch_application", {"application": "chrome"},
            Processes(running=False), Windows(active_pid=None),
        ) != "matched"

    def test_close_matches_when_no_process_remains(self):
        assert verdict(
            "close_application", {"application": "chrome"},
            Processes(running=False), Windows(active_pid=None),
        ) == "matched"

    def test_close_does_not_match_while_the_application_still_runs(self):
        """The test that most directly catches the truthiness defect: with
        `bool(probe.output)` this reported "still running" for every close
        AND "running" for every launch."""
        assert verdict(
            "close_application", {"application": "chrome"},
            Processes(running=True, pids=[7]), Windows(active_pid=7),
        ) != "matched"


class TestForegroundIsVerifiedByOwnership:
    """Defect 3. Ownership is the authoritative relationship; a title is a
    guess that is wrong in both directions."""

    @pytest.mark.parametrize("capability", ["focus_window", "bring_to_front"])
    def test_matches_when_the_active_window_belongs_to_the_application(self, capability):
        assert verdict(
            capability, {"application": "notepad"},
            Processes(running=True, pids=[100, 101]),
            Windows(active_pid=101, title="Untitled - Notepad"),
        ) == "matched"

    def test_a_title_that_names_the_app_but_belongs_elsewhere_does_not_match(self):
        """An unrelated window mentioning the application -- a browser tab
        titled "notepad - Google Search" is the obvious one."""
        assert verdict(
            "focus_window", {"application": "notepad"},
            Processes(running=True, pids=[100]),
            Windows(active_pid=999, title="notepad - Google Search"),
        ) != "matched"

    def test_a_window_that_does_not_name_the_app_still_matches_when_it_owns_it(self):
        """The other direction: a document window that never mentions its
        application. Title matching would have called this a failure."""
        assert verdict(
            "focus_window", {"application": "winword"},
            Processes(running=True, pids=[55]),
            Windows(active_pid=55, title="Quarterly Report.docx"),
        ) == "matched"

    def test_an_unobservable_foreground_does_not_match(self):
        assert verdict(
            "focus_window", {"application": "notepad"},
            Processes(running=True, pids=[100]), Windows(active_pid=None),
        ) != "matched"


class TestTheProductionWindowBackend:
    """Defect 2. `WindowManager()` alone is the null backend, which sees
    nothing on a real desktop."""

    def test_the_verifier_builds_a_win32_backed_window_manager(self):
        from master_agent.desktop.execution.win32_backends import Win32WindowBackend
        from master_agent.desktop.gateway import _DesktopStateVerifier

        manager = _DesktopStateVerifier(application="notepad")._window_manager()
        backend = manager._backend

        assert isinstance(backend, Win32WindowBackend), (
            f"window observation uses {type(backend).__name__}; a null "
            f"backend would report no window under every condition"
        )

    def test_an_injected_manager_is_used_unchanged(self):
        """The injection point exists for tests only -- production must not
        be silently observing a stub."""
        from master_agent.desktop.gateway import _DesktopStateVerifier

        stub = Windows(active_pid=1)
        assert _DesktopStateVerifier("app", windows=stub)._window_manager() is stub


class TestWhatIsNotClaimed:

    def test_close_window_is_not_claimed_as_verifiable(self):
        """The payload names an application; execution resolves a handle
        internally. Afterwards, without reading the Action's own report,
        "the intended window closed and another remains" is
        indistinguishable from "the intended window is still open"."""
        assert supports("close_window") is False
        assert verdict(
            "close_window", {"application": "notepad"},
            Processes(running=True, pids=[1]), Windows(active_pid=1),
        ) is None

    @pytest.mark.parametrize("capability", [
        "desktop_click", "desktop_press_key", "desktop_type_text",
        "execute_command", "read_text", "find_target", "desktop_observe",
        "is_running", "open_file",
    ])
    def test_unsupported_capabilities_yield_no_evidence(self, capability):
        assert supports(capability) is False
        assert verdict(
            capability, {"application": "notepad"},
            Processes(running=True, pids=[1]), Windows(active_pid=1),
        ) is None

    def test_exactly_four_capabilities_are_supported(self):
        registered = [
            "launch_application", "close_application", "focus_window",
            "bring_to_front", "close_window", "desktop_observe", "find_target",
            "read_text", "desktop_click", "desktop_type_text",
            "desktop_press_key", "execute_command", "open_file", "open_folder",
            "is_running", "is_installed", "get_version",
            "list_installed_software", "list_running_processes",
        ]
        assert len(registered) == 19
        assert sum(1 for c in registered if supports(c)) == 4


class TestExecutionIsUntouched:

    def test_the_gateway_does_not_override_invoke(self):
        from master_agent.runtime.gateway import PluginGateway

        assert issubclass(DesktopGateway, PluginGateway)
        assert "invoke" not in DesktopGateway.__dict__
