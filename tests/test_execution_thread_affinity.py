"""Mission execution runs on one thread, because Playwright demands it.

## The failure

Founder acceptance died on this, verbatim:

    failed to open browser session: cannot switch to a different thread
    (which happens to have exited)

`Browser.OpenBrowserSession` failed 1.3 seconds after planning and the
mission never reached the web. All nine downstream steps stayed pending
and the founder was told "That didn't complete."

Playwright's synchronous API is bound to the thread that started its
driver. `BrowserSessionManager` caches that driver for the life of the
process -- correctly, one driver per manager. The founder surface answers
each message on a different, short-lived HTTP worker thread from the
JS-API server's pool. First mission starts the driver on a thread that
then exits; every later Playwright call raises the sentence above.

## Why the repair is not in the browser code

Marshalling inside `BrowserSessionManager` would not be enough: the
Browser actions hold `Page` objects and call `page.goto(...)` and
`locator(...).click()` directly, and those carry the same affinity. The
manager could hand back a working session the next line still could not
use.

The defect is that execution ran on whichever worker thread arrived. One
stable execution thread fixes the class, not one library.
"""
from __future__ import annotations

import threading

import pytest


class TestTheDefectIsReal:
    """Guard against "fixed" meaning "no longer reproduced by accident".

    This drives the REAL `BrowserSessionManager`, not a stand-in, because
    the whole point is that the affinity belongs to Playwright and not to
    anything we wrote.
    """

    def test_a_dead_creating_thread_breaks_a_cached_driver(self):
        playwright = pytest.importorskip("playwright.sync_api")
        assert playwright is not None

        from master_agent.environment.browser_session import BrowserSessionManager

        manager = BrowserSessionManager(default_headless=True)
        results: dict[str, str] = {}

        def open_on_its_own_thread(key: str, session_id: str) -> None:
            def body() -> None:
                try:
                    manager.open_session(session_id)
                    results[key] = "ok"
                except Exception as exc:  # noqa: BLE001 - the point of the test
                    results[key] = f"{type(exc).__name__}: {exc}"

            thread = threading.Thread(target=body)
            thread.start()
            thread.join()

        try:
            open_on_its_own_thread("first", "s1")
            open_on_its_own_thread("second", "s2")
        finally:
            try:
                manager.close_all()
            except Exception:  # noqa: BLE001 - teardown is best-effort
                pass

        assert results["first"] == "ok"
        assert "different thread" in results["second"], (
            "the affinity defect no longer reproduces on this machine; the "
            "fix below would then be proving nothing"
        )


class TestOneExecutionThread:
    """The repair, tested without a browser: what matters is that every
    Runtime step lands on the SAME thread, whoever calls in."""

    def manager(self):
        import kalpavriksha_desktop as kd

        return kd._ExecutionThread()

    def test_work_submitted_from_many_threads_runs_on_one(self):
        execution = self.manager()
        seen: list[int] = []

        def record() -> None:
            seen.append(threading.get_ident())

        for _ in range(4):
            thread = threading.Thread(target=lambda: execution.run(record))
            thread.start()
            thread.join()

        assert len(seen) == 4
        assert len(set(seen)) == 1, (
            f"work ran on {len(set(seen))} threads; a cached Playwright "
            "driver would break on the second"
        )

    def test_it_is_not_the_calling_thread(self):
        """It has to be its OWN thread. Running on the caller's thread
        would put the driver back on a thread that exits."""
        execution = self.manager()
        where = execution.run(threading.get_ident)
        assert where != threading.get_ident()

    def test_the_same_thread_survives_a_caller_that_has_exited(self):
        """The precise shape of the founder's failure: the thread that
        started the driver is gone by the time the next message
        arrives."""
        execution = self.manager()
        seen: list[int] = []

        first = threading.Thread(
            target=lambda: seen.append(execution.run(threading.get_ident))
        )
        first.start()
        first.join()
        assert not first.is_alive()

        second = threading.Thread(
            target=lambda: seen.append(execution.run(threading.get_ident))
        )
        second.start()
        second.join()

        assert seen[0] == seen[1]

    def test_exceptions_propagate_unchanged(self):
        """Every existing error path -- refusals, failures, the
        founder-facing sentences -- must behave exactly as it did when
        this ran inline. A thread that swallowed errors would turn a
        failure into a silent success."""
        execution = self.manager()

        def boom():
            raise ValueError("the browser could not start")

        with pytest.raises(ValueError, match="could not start"):
            execution.run(boom)

    def test_results_come_back_to_the_caller(self):
        execution = self.manager()
        assert execution.run(lambda: 7 * 6) == 42

    def test_ordering_is_preserved(self):
        """The caller still blocks on the result, so back-pressure and
        ordering are unchanged from running inline."""
        execution = self.manager()
        order: list[int] = []
        for n in range(5):
            execution.run(lambda n=n: order.append(n))
        assert order == [0, 1, 2, 3, 4]


class TestItIsNotASecondOrchestrator:
    def test_it_decides_nothing_and_holds_no_mission_state(self):
        import inspect

        import kalpavriksha_desktop as kd

        source = inspect.getsource(kd._ExecutionThread).lower()
        for forbidden in ("objective", "mission_control", "dispatcher",
                          "plan", "requirement", "status."):
            assert forbidden not in source, forbidden

    def test_the_single_worker_is_the_contract(self):
        """`max_workers=1` is not a tuning choice. A second worker
        reintroduces exactly the defect this exists to remove."""
        import inspect

        import kalpavriksha_desktop as kd

        source = inspect.getsource(kd._ExecutionThread)
        assert "max_workers=1" in source

    def test_the_runtime_is_driven_through_it(self):
        """A repair nothing calls is not a repair."""
        import inspect

        import kalpavriksha_desktop as kd

        source = inspect.getsource(kd._drive_until_settled)
        assert "_EXECUTION.run(runtime.run_once)" in source
        assert "\n        runtime.run_once()" not in source


class TestEveryPlaywrightCallUsesTheOneThread:
    """Including cleanup, which is easy to forget because it looks like
    housekeeping rather than browser work.

    It is browser work. Closing a session drives the same thread-affine
    driver that opened it, and calling it inline corrupted the driver for
    every mission afterwards -- the next `OpenBrowserSession` failed with
    "It looks like you are using Playwright Sync API inside the asyncio
    loop" and every step behind it stayed pending.
    """

    def test_browser_cleanup_goes_through_the_execution_thread(self):
        import inspect

        import kalpavriksha_desktop as kd

        source = inspect.getsource(kd._release_task_browsers)
        assert "_EXECUTION.run(" in source, (
            "session cleanup drives Playwright from whatever thread "
            "finished the mission"
        )
        assert "manager.close_anonymous()" not in source

    def test_cleanup_still_cannot_raise(self):
        import kalpavriksha_desktop as kd

        class Exploding:
            def close_anonymous(self):
                raise RuntimeError("driver is gone")

        original = kd._BROWSER_SESSIONS
        kd._BROWSER_SESSIONS = Exploding()
        try:
            kd._release_task_browsers()
        finally:
            kd._BROWSER_SESSIONS = original
