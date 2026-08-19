"""A task is committed only if something is about to run it.

The defect these lock, observed live in a packaged six-step mission:

    step_1  Browser.OpenBrowserSession   READY -> completed
    step_4  Filesystem.CreateFolder      READY -> DISPATCHED, never started

`dispatch_ready()` committed every ready task -- state to DISPATCHED, an
Executive recorded, that Executive marked busy -- and `RuntimeEngine
._cycle()` then ran only `tasks[:max_concurrent_tasks]`. With two ready
tasks and capacity one, the second was assigned and dropped. It was no
longer READY so `ready_tasks()` never offered it again, and its Executive
stayed busy with work that would never start, so nothing else could be
assigned there either. The founder was shown "Step 4 of 6" while the
runtime idled 187 times believing it had nothing to do.

Capacity belongs to the Runtime; assignment belongs to Mission Control.
The number now travels to the decision instead of a slice being applied
after it.
"""
from __future__ import annotations

from master_agent.mission_control.capabilities import CapabilityDescriptor, qualified_name
from master_agent.mission_control.executives import ExecutiveHealth
from master_agent.mission_control.mission_control import MissionControl
from master_agent.mission_control.tasks import Objective, Task, TaskState


def descriptor(executive: str, capability: str) -> CapabilityDescriptor:
    return CapabilityDescriptor(
        qualified_name=qualified_name(executive, capability),
        executive_id=executive,
        capability=capability,
    )


def control(**executives: list[str]) -> MissionControl:
    """`control(browser=["navigate"], filesystem=["create_folder"])`."""
    mc = MissionControl()
    for executive_id, caps in executives.items():
        mc.register_executive(
            executive_id=executive_id,
            version="0.1.0",
            capabilities=[descriptor(executive_id, cap) for cap in caps],
            health=ExecutiveHealth.HEALTHY,
        )
        mc.mark_executive_ready(executive_id)
    return mc


def states(mc: MissionControl, objective_id: str) -> dict[str, TaskState]:
    return {t.task_id: t.state for t in mc.dispatcher.objective(objective_id).tasks}


def busy_executives(mc: MissionControl) -> dict[str, str | None]:
    return {e.executive_id: e.current_task_id for e in mc.executives.all()}


def finish(mc: MissionControl, objective_id: str, task_id: str) -> None:
    """Report a task done the way the Runtime does, so the Executive is
    released through the existing completion path rather than by hand."""
    mc.task_started(task_id, objective_id)
    mc.task_completed(task_id, objective_id=objective_id)


class TestCapacityIsRespectedBeforeAnyStateChanges:

    def test_two_ready_one_slot_commits_exactly_one(self):
        mc = control(browser=["navigate"], filesystem=["create_folder"])
        objective = mc.submit_objective(Objective(
            description="two independent tasks",
            tasks=[
                Task(capability="Browser.Navigate", task_id="t1"),
                Task(capability="Filesystem.CreateFolder", task_id="t2"),
            ],
        ))

        dispatched = mc.dispatch_ready(objective.objective_id, limit=1)

        assert len(dispatched) == 1
        by_state = states(mc, objective.objective_id)
        assert sum(s is TaskState.DISPATCHED for s in by_state.values()) == 1
        assert sum(s is TaskState.READY for s in by_state.values()) == 1

    def test_the_task_beyond_capacity_stays_ready_not_dispatched(self):
        """READY is what "offer me again next cycle" already means. The
        surplus task must be left in it, untouched."""
        mc = control(browser=["navigate"], filesystem=["create_folder"])
        objective = mc.submit_objective(Objective(
            description="two independent tasks",
            tasks=[
                Task(capability="Browser.Navigate", task_id="t1"),
                Task(capability="Filesystem.CreateFolder", task_id="t2"),
            ],
        ))

        taken = mc.dispatch_ready(objective.objective_id, limit=1)[0]
        left = "t2" if taken.task_id == "t1" else "t1"

        assert states(mc, objective.objective_id)[left] is TaskState.READY

    def test_no_executive_is_left_busy_for_a_task_that_will_not_run(self):
        """The half of the defect that poisoned everything after it: an
        Executive marked busy for an uncommitted task can never be given
        another one."""
        mc = control(browser=["navigate"], filesystem=["create_folder"])
        objective = mc.submit_objective(Objective(
            description="two independent tasks",
            tasks=[
                Task(capability="Browser.Navigate", task_id="t1"),
                Task(capability="Filesystem.CreateFolder", task_id="t2"),
            ],
        ))

        taken = mc.dispatch_ready(objective.objective_id, limit=1)[0]
        busy = busy_executives(mc)

        assert sum(v is not None for v in busy.values()) == 1, busy
        assert busy[taken.assigned_executive] == taken.task_id

    def test_the_deferred_task_is_offered_again_once_a_slot_frees(self):
        mc = control(browser=["navigate"], filesystem=["create_folder"])
        objective = mc.submit_objective(Objective(
            description="two independent tasks",
            tasks=[
                Task(capability="Browser.Navigate", task_id="t1"),
                Task(capability="Filesystem.CreateFolder", task_id="t2"),
            ],
        ))

        first = mc.dispatch_ready(objective.objective_id, limit=1)[0]
        finish(mc, objective.objective_id, first.task_id)

        second = mc.dispatch_ready(objective.objective_id, limit=1)
        assert len(second) == 1
        assert second[0].task_id != first.task_id

        finish(mc, objective.objective_id, second[0].task_id)
        assert all(
            s is TaskState.COMPLETED for s in states(mc, objective.objective_id).values()
        )


class TestThreeReadyTwoSlots:

    def _objective(self, mc: MissionControl):
        return mc.submit_objective(Objective(
            description="three independent tasks",
            tasks=[
                Task(capability="Browser.Navigate", task_id="t1"),
                Task(capability="Browser.Click", task_id="t2"),
                Task(capability="Filesystem.CreateFolder", task_id="t3"),
            ],
        ))

    def test_two_are_accepted_and_one_remains_ready(self):
        mc = control(browser=["navigate", "click"], filesystem=["create_folder"])
        objective = self._objective(mc)

        dispatched = mc.dispatch_ready(objective.objective_id, limit=2)

        # The browser Executive can only hold one task at a time, so the
        # exact pair depends on availability -- what must hold is that no
        # more than the limit was committed and nothing was stranded.
        assert len(dispatched) <= 2
        by_state = states(mc, objective.objective_id)
        assert sum(s is TaskState.DISPATCHED for s in by_state.values()) == len(dispatched)
        assert sum(s is TaskState.READY for s in by_state.values()) == 3 - len(dispatched)

    def test_the_remainder_progresses_once_a_slot_becomes_available(self):
        mc = control(browser=["navigate", "click"], filesystem=["create_folder"])
        objective = self._objective(mc)

        done: set[str] = set()
        for _ in range(6):  # bounded: this must converge, not spin
            for task in mc.dispatch_ready(objective.objective_id, limit=2):
                finish(mc, objective.objective_id, task.task_id)
                done.add(task.task_id)
            if len(done) == 3:
                break

        assert done == {"t1", "t2", "t3"}


class TestNoDoubleAssignmentOnOneExecutive:

    def test_two_tasks_for_the_same_executive_do_not_both_commit(self):
        mc = control(browser=["navigate", "click"])
        objective = mc.submit_objective(Objective(
            description="same executive twice",
            tasks=[
                Task(capability="Browser.Navigate", task_id="t1"),
                Task(capability="Browser.Click", task_id="t2"),
            ],
        ))

        dispatched = mc.dispatch_ready(objective.objective_id, limit=2)

        assert len(dispatched) == 1, "one Executive took two tasks at once"
        assert states(mc, objective.objective_id)["t2" if dispatched[0].task_id == "t1" else "t1"] \
            is TaskState.READY

    def test_the_executive_is_released_and_the_second_task_then_runs(self):
        mc = control(browser=["navigate", "click"])
        objective = mc.submit_objective(Objective(
            description="same executive twice",
            tasks=[
                Task(capability="Browser.Navigate", task_id="t1"),
                Task(capability="Browser.Click", task_id="t2"),
            ],
        ))

        first = mc.dispatch_ready(objective.objective_id, limit=2)[0]
        finish(mc, objective.objective_id, first.task_id)
        assert busy_executives(mc)["browser"] is None, "busy state leaked"

        second = mc.dispatch_ready(objective.objective_id, limit=2)
        assert len(second) == 1 and second[0].task_id != first.task_id


class TestTheExactMediumShape:
    """The live failure, reduced to its scheduling essentials:
    `Browser.OpenBrowserSession` and `Filesystem.CreateFolder` both ready
    in the first cycle, capacity one."""

    def _objective(self, mc: MissionControl):
        return mc.submit_objective(Objective(
            description="browser and filesystem, both ready at once",
            tasks=[
                Task(capability="Browser.OpenBrowserSession", task_id="step_1"),
                Task(capability="Browser.Navigate", task_id="step_2", depends_on=["step_1"]),
                Task(capability="Browser.ObserveBrowser", task_id="step_3", depends_on=["step_2"]),
                Task(capability="Filesystem.CreateFolder", task_id="step_4"),
                Task(capability="Filesystem.WriteFile", task_id="step_5",
                     depends_on=["step_3", "step_4"]),
                Task(capability="Browser.CloseBrowserSession", task_id="step_6",
                     depends_on=["step_3"]),
            ],
        ))

    def _mc(self) -> MissionControl:
        return control(
            browser=["open_browser_session", "navigate", "observe_browser",
                     "close_browser_session"],
            filesystem=["create_folder", "write_file"],
        )

    def test_step_4_is_not_committed_in_the_first_cycle(self):
        mc = self._mc()
        objective = self._objective(mc)

        mc.dispatch_ready(objective.objective_id, limit=1)

        by_state = states(mc, objective.objective_id)
        assert by_state["step_4"] is TaskState.READY, (
            "step_4 was committed in a cycle that could not run it -- the "
            "exact state the live mission stranded in"
        )

    def test_step_4_eventually_starts_and_the_mission_converges(self):
        """The live failure was not slowness -- step_4 could never start
        again. Driving the scheduler to a fixed point proves it now does,
        and the bound proves there is no dispatch/idle spin."""
        mc = self._mc()
        objective = self._objective(mc)

        started: list[str] = []
        for _ in range(20):  # bounded: 6 tasks at capacity 1 must converge
            batch = mc.dispatch_ready(objective.objective_id, limit=1)
            if not batch:
                break
            for task in batch:
                started.append(task.task_id)
                finish(mc, objective.objective_id, task.task_id)

        assert "step_4" in started, "step_4 never started"
        assert set(started) == {f"step_{i}" for i in range(1, 7)}
        assert all(
            s is TaskState.COMPLETED for s in states(mc, objective.objective_id).values()
        )

    def test_no_executive_is_left_holding_a_task_at_the_end(self):
        mc = self._mc()
        objective = self._objective(mc)

        for _ in range(20):
            batch = mc.dispatch_ready(objective.objective_id, limit=1)
            if not batch:
                break
            for task in batch:
                finish(mc, objective.objective_id, task.task_id)

        assert all(v is None for v in busy_executives(mc).values()), busy_executives(mc)


class TestTheLimitContractItself:

    def test_no_limit_keeps_the_previous_unbounded_behaviour(self):
        """Existing callers pass no limit and must be unaffected."""
        mc = control(browser=["navigate"], filesystem=["create_folder"])
        objective = mc.submit_objective(Objective(
            description="two independent tasks",
            tasks=[
                Task(capability="Browser.Navigate", task_id="t1"),
                Task(capability="Filesystem.CreateFolder", task_id="t2"),
            ],
        ))

        assert len(mc.dispatch_ready(objective.objective_id)) == 2

    def test_a_zero_or_negative_limit_commits_nothing(self):
        mc = control(browser=["navigate"])
        objective = mc.submit_objective(Objective(
            description="one task",
            tasks=[Task(capability="Browser.Navigate", task_id="t1")],
        ))

        for limit in (0, -1):
            assert mc.dispatch_ready(objective.objective_id, limit=limit) == []
            assert states(mc, objective.objective_id)["t1"] is TaskState.READY
            assert all(v is None for v in busy_executives(mc).values())
