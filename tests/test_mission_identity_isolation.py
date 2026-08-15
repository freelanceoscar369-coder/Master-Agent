"""Two missions must never share one identity.

The founder reported that completed work appeared to block new work: the
first folder mission finished instantly, and every one after it span the
founder surface's full 45-second timeout and reported *"that's taking
longer than expected"* -- about a folder already sitting on disk.

It was not backpressure from the dashboard, and not the founder failing
to acknowledge anything. `direct_plan()` minted `step_id` as
`f"{capability}-1"`, which is unique inside a one-step plan and
**identical for every folder mission ever planned**.
`RuntimeEngine._objective_of()` resolves a task's objective by scanning
every objective for a matching `task_id` and returning the first hit, so
mission B's completion was applied to mission A's objective. B's
objective never completed, `OBJECTIVE_COMPLETED` never fired, no
completion question was asked, and the surface waited for a terminal
state that could not arrive.

Three missions, three identities, three completions.
"""
from __future__ import annotations

import pytest

from master_agent.brain.intent import IntentLayer
from master_agent.capabilities.extraction import contracts_from_actions
from master_agent.capabilities.index import build_index
from master_agent.executor.executor import LocalExecutor
from master_agent.mission_control.capabilities import qualified_name
from master_agent.permissions.permission_system import PermissionSystem
from master_agent.planner.catalogue import catalogue_from_index
from master_agent.planner.direct import direct_plan
from master_agent.plugins.filesystem_plugin import FilesystemPlugin


@pytest.fixture(scope="module")
def options():
    plugin = FilesystemPlugin(LocalExecutor(PermissionSystem()))
    contracts = contracts_from_actions(
        plugin._actions, plugin.manifest.name, qualified_name
    )
    index = build_index(contracts, loader={c.canonical_id: c for c in contracts}.get)
    return catalogue_from_index(index)


def plan_for(text: str, options):
    intent = IntentLayer().parse(text).intent
    assert intent is not None
    plan = direct_plan(intent, options)
    assert plan is not None, f"{text!r} produced no deterministic plan"
    return plan


class TestStepIdentityIsUnique:

    def test_two_missions_of_the_same_shape_get_different_step_ids(self, options):
        a = plan_for("Create a folder called Alpha in Documents", options)
        b = plan_for("Create a folder called Beta in Documents", options)
        assert a.steps[0].step_id != b.steps[0].step_id

    def test_even_two_identical_requests_get_different_step_ids(self, options):
        """The same sentence twice is still two missions. Identity comes
        from the mission, never from what it happens to be about."""
        a = plan_for("Create a folder called Same in Documents", options)
        b = plan_for("Create a folder called Same in Documents", options)
        assert a.steps[0].step_id != b.steps[0].step_id

    def test_many_missions_stay_distinct(self, options):
        ids = {
            plan_for(f"Create a folder called N{i} in Documents", options).steps[0].step_id
            for i in range(25)
        }
        assert len(ids) == 25

    def test_the_id_still_names_the_capability(self, options):
        """Readable in a log and in the founder's own mission record --
        uniqueness must not cost legibility."""
        step = plan_for("Create a folder called Alpha in Documents", options).steps[0]
        assert step.step_id.startswith("Filesystem.CreateFolder-")
        assert step.step_id != "Filesystem.CreateFolder-1"


class TestObjectiveResolutionCannotCollide:

    def test_a_task_id_resolves_to_exactly_one_objective(self, options):
        """`_objective_of()` returns the FIRST objective holding a matching
        task id. That is only correct while ids are unique -- this asserts
        the property it silently depends on."""
        plans = [
            plan_for(f"Create a folder called C{i} in Documents", options)
            for i in range(5)
        ]
        all_ids = [step.step_id for plan in plans for step in plan.steps]
        assert len(all_ids) == len(set(all_ids)), (
            "two missions share a task id, so a completion reported for one "
            "would be applied to the other"
        )
