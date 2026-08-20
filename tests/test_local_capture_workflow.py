"""The dictated local workflow plans without a model.

A founder who writes "open a browser, go to this address, see what the
page says, write that into a file on my Desktop, close the browser" has
not posed a planning problem -- they have dictated the steps. Three live
missions were lost asking a reasoning ladder to rediscover them: Gemini
out of quota, then desktop AI applications that refused or timed out, and
no plan at either end.

These tests hold the two halves that matter: the dictated shape plans
deterministically, and everything else still asks a provider exactly as
before.
"""
from __future__ import annotations

import pytest

from master_agent.capabilities.extraction import contracts_from_actions
from master_agent.capabilities.index import build_index
from master_agent.environment.browser_session import BrowserSessionManager
from master_agent.executor.executor import LocalExecutor
from master_agent.mission_control.capabilities import qualified_name
from master_agent.permissions.permission_system import PermissionSystem
from master_agent.planner.catalogue import catalogue_from_index
from master_agent.planner.direct import direct_plan
from master_agent.planner.modes import LOCAL
from master_agent.planner.plan import Intent
from master_agent.planner.planner import Planner
from master_agent.plugins.browser_plugin import BrowserPlugin
from master_agent.plugins.filesystem_plugin import FilesystemPlugin

OBJECTIVE = (
    "Open a browser and navigate to https://example.com. Observe the page's actual "
    "title and final URL. Create a folder called KV_VISIBLE_MEDIUM_123456 on Desktop. "
    "Inside that folder create a text file called page_info.txt containing the title "
    "and URL you actually observed. Then close the browser."
)


@pytest.fixture
def options():
    """The catalogue the packaged application actually builds."""
    executor = LocalExecutor(PermissionSystem())
    contracts = []
    for plugin in (
        BrowserPlugin(executor, BrowserSessionManager(default_headless=False)),
        FilesystemPlugin(executor),
    ):
        actions = getattr(plugin, "_actions", None)
        if isinstance(actions, dict):
            contracts.extend(
                contracts_from_actions(actions, plugin.manifest.name, qualified_name)
            )
    index = build_index(contracts, loader={c.canonical_id: c for c in contracts}.get)
    return catalogue_from_index(index)


def steps_by_capability(plan):
    return {step.capability: step for step in plan.steps}


class TestTheDictatedWorkflowPlansItself:

    def test_it_produces_the_six_step_plan(self, options):
        plan = direct_plan(Intent(goal=OBJECTIVE), options)
        assert plan is not None, "the dictated workflow still needs a model"
        assert [step.capability for step in plan.steps] == [
            "Browser.OpenBrowserSession",
            "Browser.Navigate",
            "Browser.ObserveBrowser",
            "Filesystem.CreateFolder",
            "Filesystem.WriteFile",
            "Browser.CloseBrowserSession",
        ]

    def test_the_write_carries_no_content_at_planning_time(self, options):
        """Nobody has looked at the page yet, so nothing may claim to know
        what it says. This is the defect the whole binding architecture
        was built for."""
        plan = direct_plan(Intent(goal=OBJECTIVE), options)
        write = steps_by_capability(plan)["Filesystem.WriteFile"]

        assert "content" not in write.payload
        rendered = repr(plan)
        assert "Example Domain" not in rendered, "a page title was predicted"
        assert "https://example.com/" not in rendered, "a final URL was predicted"

    def test_the_content_binds_to_the_observation(self, options):
        plan = direct_plan(Intent(goal=OBJECTIVE), options)
        by_capability = steps_by_capability(plan)
        observe = by_capability["Browser.ObserveBrowser"]
        write = by_capability["Filesystem.WriteFile"]

        segments = write.input_bindings["content"]["concat"]
        refs = [s["from_step"] for s in segments if "from_step" in s]
        assert [r["field"] for r in refs] == ["title", "url"]
        assert {r["step_id"] for r in refs} == {observe.step_id}
        assert observe.step_id in write.depends_on, (
            "a binding may read depends_on but never extend it"
        )

    def test_bindings_are_the_plain_wire_form(self, options):
        """Translation, the event bus and a restart all carry JSON. An
        earlier live mission died on `'dict' object has no attribute
        'ref'` because a parsed object was emitted here instead."""
        import json

        plan = direct_plan(Intent(goal=OBJECTIVE), options)
        write = steps_by_capability(plan)["Filesystem.WriteFile"]
        assert json.loads(json.dumps(write.input_bindings)) == write.input_bindings

    def test_the_browser_is_visible(self, options):
        """The founder said "open a browser" -- something they expect to
        watch happen."""
        plan = direct_plan(Intent(goal=OBJECTIVE), options)
        assert steps_by_capability(plan)["Browser.OpenBrowserSession"].payload[
            "headless"
        ] is False

    def test_every_step_states_an_expectation(self, options):
        """A step with no expectation cannot be verified, and
        `objective_from_plan()` rejects it outright."""
        plan = direct_plan(Intent(goal=OBJECTIVE), options)
        for step in plan.steps:
            assert step.expected_outcome is not None
            assert (step.expected_outcome.description or "").strip()

    def test_step_ids_are_unique_across_missions(self, options):
        """Two missions sharing one step identity is how a completed
        mission's result was once applied to a different mission."""
        first = direct_plan(Intent(goal=OBJECTIVE), options)
        second = direct_plan(Intent(goal=OBJECTIVE), options)
        assert not {s.step_id for s in first.steps} & {s.step_id for s in second.steps}


class TestItIsNotKeyedOnTheSite:

    def test_a_different_address_plans_identically(self, options):
        """Matching a host would make this a rehearsal, not a capability."""
        other = OBJECTIVE.replace("https://example.com", "https://www.iana.org/help/example-domains")
        plan = direct_plan(Intent(goal=other), options)

        assert plan is not None
        navigate = steps_by_capability(plan)["Browser.Navigate"]
        assert navigate.payload["url"] == "https://www.iana.org/help/example-domains"

    def test_the_founders_own_names_are_used(self, options):
        other = (
            OBJECTIVE.replace("KV_VISIBLE_MEDIUM_123456", "QuarterlyNotes")
            .replace("page_info.txt", "summary.txt")
            .replace("on Desktop", "in Documents")
        )
        plan = direct_plan(Intent(goal=other), options)
        by_capability = steps_by_capability(plan)

        assert by_capability["Filesystem.CreateFolder"].payload == {
            "name": "QuarterlyNotes",
            "location": "Documents",
        }
        assert by_capability["Filesystem.WriteFile"].payload["path"] == (
            "QuarterlyNotes/summary.txt"
        )


class TestAnythingElseStillAsksAProvider:

    @pytest.mark.parametrize("missing", [
        "Open a browser and navigate to https://example.com. Then close the browser.",
        "Create a folder called Notes on Desktop and a file called a.txt in it.",
        "Research our competitors and write a summary to my Desktop.",
    ])
    def test_an_undictated_objective_gets_no_direct_plan(self, missing, options):
        assert direct_plan(Intent(goal=missing), options) is None


class TestLocalModeNeedsNoProvider:

    def test_local_mode_plans_without_calling_a_runner(self, options):
        """The load-bearing one. In LOCAL mode this must produce the plan
        rather than refuse with LOCAL_ONLY, and must reach no provider."""
        calls = []

        class Runner:
            def run(self, *args, **kwargs):
                calls.append(args)
                raise AssertionError("a reasoning provider was called")

        executor = LocalExecutor(PermissionSystem())
        contracts = []
        for plugin in (
            BrowserPlugin(executor, BrowserSessionManager(default_headless=False)),
            FilesystemPlugin(executor),
        ):
            actions = getattr(plugin, "_actions", None)
            if isinstance(actions, dict):
                contracts.extend(
                    contracts_from_actions(actions, plugin.manifest.name, qualified_name)
                )
        index = build_index(contracts, loader={c.canonical_id: c for c in contracts}.get)

        planner = Planner(runner=Runner(), catalogue=index, mode=lambda: LOCAL)
        outcome = planner.plan(Intent(goal=OBJECTIVE))

        assert outcome.refusal is None, getattr(outcome.refusal, "code", None)
        assert outcome.plan is not None
        assert len(outcome.plan.steps) == 6
        assert calls == [], "LOCAL mode reached a provider"


class TestTheOneStepPathIsUntouched:

    def test_a_named_capability_still_plans_as_one_step(self, options):
        """The existing deterministic seam must keep working exactly as it
        did -- this extension adds a shape, it does not replace one."""
        intent = Intent(goal="create a folder called Reports on Desktop")
        intent.capability = "create_folder"
        intent.payload = {"name": "Reports", "location": "Desktop"}

        plan = direct_plan(intent, options)
        assert plan is not None
        assert len(plan.steps) == 1
        assert plan.steps[0].capability == "Filesystem.CreateFolder"
        assert plan.steps[0].payload == {"name": "Reports", "location": "Desktop"}
