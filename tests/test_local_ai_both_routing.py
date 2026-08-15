"""LOCAL / AI MODE / BOTH, and the end of pointless reasoning.

A founder typed *"create a folder called KalpavrikshaLiveTest3 in
Documents"*. `Filesystem.CreateFolder(name, location?)` was registered and
entirely sufficient. The Planner sent a planning prompt to its reasoning
ladder anyway, which -- Gemini being out of quota -- fell through every
tier in turn: Gemini, then each installed desktop AI application, then a
browser search. Windows opened across the founder's screen. Nothing about
creating a folder needed a model.

**Capability availability and reasoning necessity are different
questions.** These tests hold that separation in place.

The runner used throughout is `ExplodingRunner`, which raises the moment
it is touched. "No provider was contacted" is therefore not an assertion
about a counter that someone has to remember to check -- a contacted
provider fails the test by construction.
"""
from __future__ import annotations

import pytest

from master_agent.brain.intent import IntentLayer
from master_agent.capabilities.extraction import contracts_from_actions
from master_agent.capabilities.index import build_index
from master_agent.executor.executor import LocalExecutor
from master_agent.mission_control.capabilities import qualified_name
from master_agent.permissions.permission_system import PermissionSystem
from master_agent.planner.direct import direct_plan, find_option
from master_agent.planner.modes import (
    AI_MODE,
    BOTH,
    DEFAULT_MODE,
    LOCAL,
    MODES,
    normalise,
    resolve_mode,
)
from master_agent.planner.plan import LOCAL_ONLY, Intent
from master_agent.planner.planner import Planner
from master_agent.plugins.filesystem_plugin import FilesystemPlugin


class ProviderContacted(AssertionError):
    """Raised when a reasoning provider is reached. Failing loudly beats
    counting calls nobody asserts on."""


class ExplodingRunner:
    def run(self, *args, **kwargs):
        raise ProviderContacted(
            "a reasoning provider was contacted for an objective the "
            "registered capabilities already settle"
        )


class _Unavailable:
    """What the ladder returns when every tier is exhausted -- the shape
    `Planner._rejected()` reads, not an exception."""

    ok = False
    refused = False
    reason = "every tier was exhausted"
    text = ""
    evidence = None
    entry_id = None
    provider_id = None


class CountingRunner:
    """For the cases where a provider *should* be reached."""

    def __init__(self) -> None:
        self.calls = 0

    def run(self, *args, **kwargs):
        self.calls += 1
        return _Unavailable()


@pytest.fixture(scope="module")
def catalogue():
    plugin = FilesystemPlugin(LocalExecutor(PermissionSystem()))
    contracts = contracts_from_actions(
        plugin._actions, plugin.manifest.name, qualified_name
    )
    return build_index(contracts, loader={c.canonical_id: c for c in contracts}.get)


def intent_for(text: str) -> Intent:
    result = IntentLayer().parse(text)
    assert result.intent is not None, f"{text!r} needs clarification, not planning"
    return result.intent


# =========================================================================
# The defect
# =========================================================================


class TestNoReasoningForADeterministicObjective:

    @pytest.mark.parametrize("mode", [BOTH, LOCAL])
    @pytest.mark.parametrize("text", [
        "Create a folder called KalpavrikshaLiveTest3 in Documents",
        "Create a folder called Research on my Desktop",
        "Create a folder called Notes",
    ])
    def test_no_provider_is_contacted(self, catalogue, mode, text):
        planner = Planner(runner=ExplodingRunner(), catalogue=catalogue, mode=mode)
        outcome = planner.plan(intent_for(text))
        assert outcome.plan is not None, f"{text!r} produced no local plan"

    def test_the_plan_names_the_registered_capability_and_its_arguments(self, catalogue):
        planner = Planner(runner=ExplodingRunner(), catalogue=catalogue, mode=BOTH)
        plan = planner.plan(
            intent_for("Create a folder called KalpavrikshaLiveTest3 in Documents")
        ).plan

        assert len(plan.steps) == 1
        step = plan.steps[0]
        assert step.capability == "Filesystem.CreateFolder"
        assert step.payload == {
            "name": "KalpavrikshaLiveTest3", "location": "Documents",
        }

    def test_the_step_states_what_success_looks_like(self, catalogue):
        """`objective_from_plan()` rejects a step with no expectation, and
        Verification would have nothing to compare against."""
        planner = Planner(runner=ExplodingRunner(), catalogue=catalogue, mode=BOTH)
        step = planner.plan(intent_for("Create a folder called Research")).plan.steps[0]
        assert step.expected_outcome is not None

    def test_an_unstated_location_is_still_not_invented(self, catalogue):
        planner = Planner(runner=ExplodingRunner(), catalogue=catalogue, mode=BOTH)
        step = planner.plan(intent_for("Create a folder called Research")).plan.steps[0]
        assert "location" not in step.payload
        assert "Desktop" not in str(step.payload)


# =========================================================================
# The three modes
# =========================================================================


class TestModes:

    def test_local_never_reaches_a_provider_even_when_it_cannot_plan(self, catalogue):
        """LOCAL means local capabilities only. An objective they cannot
        satisfy is refused honestly -- not escalated to the thing the
        founder switched off."""
        planner = Planner(runner=ExplodingRunner(), catalogue=catalogue, mode=LOCAL)
        outcome = planner.plan(intent_for("Learn trading"))

        assert outcome.plan is None
        assert outcome.refusal.code == LOCAL_ONLY
        assert outcome.refusal.known_capabilities, (
            "a refusal should name what IS available, MB033-style"
        )

    def test_both_escalates_only_after_local_is_insufficient(self, catalogue):
        runner = CountingRunner()
        planner = Planner(runner=runner, catalogue=catalogue, mode=BOTH)

        planner.plan(intent_for("Create a folder called Research"))
        assert runner.calls == 0, "BOTH reached a provider for a local-solvable goal"

        planner.plan(intent_for("Learn trading"))
        assert runner.calls == 1, "BOTH refused to escalate when local was insufficient"

    def test_ai_mode_goes_to_the_provider_by_the_founders_choice(self, catalogue):
        """A founder who explicitly selects AI MODE is asking for
        reasoning; skipping it because a local shortcut existed would
        override them."""
        runner = CountingRunner()
        planner = Planner(runner=runner, catalogue=catalogue, mode=AI_MODE)
        planner.plan(intent_for("Create a folder called Research"))
        assert runner.calls == 1

    def test_the_mode_is_read_at_plan_time_not_captured_at_boot(self, catalogue):
        """The founder flips the switch mid-session; the Planner is built
        once. A captured value would freeze whatever was set at startup."""
        cell = {"mode": BOTH}
        planner = Planner(
            runner=ExplodingRunner(), catalogue=catalogue, mode=lambda: cell["mode"],
        )
        assert planner.mode() == BOTH
        cell["mode"] = LOCAL
        assert planner.mode() == LOCAL

    def test_an_unwired_switch_behaves_as_both(self, catalogue):
        planner = Planner(runner=ExplodingRunner(), catalogue=catalogue)
        assert planner.mode() == DEFAULT_MODE == BOTH
        assert planner.plan(intent_for("Create a folder called Research")).plan


class TestModeVocabulary:

    @pytest.mark.parametrize("raw,expected", [
        ("local", LOCAL), ("LOCAL", LOCAL), ("  Local  ", LOCAL),
        ("ai_mode", AI_MODE), ("ai_tools", AI_MODE), ("ai", AI_MODE),
        ("both", BOTH), ("", BOTH), ("nonsense", BOTH), (None, BOTH), (7, BOTH),
    ])
    def test_every_spelling_resolves_into_the_closed_vocabulary(self, raw, expected):
        assert normalise(raw) == expected
        assert normalise(raw) in MODES

    def test_an_unreadable_switch_is_both_rather_than_a_crash(self):
        def broken():
            raise RuntimeError("switch is on fire")

        assert resolve_mode(broken) == BOTH


# =========================================================================
# Why the capability is never inferred from argument shape
# =========================================================================


class TestDirectPlanningIsConfirmationNotInference:

    def test_an_intent_naming_nothing_gets_no_direct_plan(self, catalogue):
        from master_agent.planner.catalogue import catalogue_from_index

        options = catalogue_from_index(catalogue)
        assert direct_plan(Intent(goal="do a thing"), options) is None

    def test_an_unregistered_capability_gets_no_direct_plan(self, catalogue):
        from master_agent.planner.catalogue import catalogue_from_index

        options = catalogue_from_index(catalogue)
        intent = Intent(
            goal="x", capability="teleport", payload={"name": "n"},
        )
        assert direct_plan(intent, options) is None

    def test_a_missing_required_argument_gets_no_direct_plan(self, catalogue):
        from master_agent.planner.catalogue import catalogue_from_index

        options = catalogue_from_index(catalogue)
        intent = Intent(goal="x", capability="create_folder", payload={"location": "Desktop"})
        assert direct_plan(intent, options) is None

    def test_an_unpublished_argument_gets_no_direct_plan(self, catalogue):
        from master_agent.planner.catalogue import catalogue_from_index

        options = catalogue_from_index(catalogue)
        intent = Intent(
            goal="x", capability="create_folder",
            payload={"name": "n", "sudo": True},
        )
        assert direct_plan(intent, options) is None

    def test_argument_shape_alone_is_ambiguous_which_is_why_it_is_not_used(self, catalogue):
        """Measured, not asserted from memory: `('path',)` is the required
        signature of six filesystem capabilities, among them ReadFile and
        DeleteFile. Inferring a capability from its arguments could not
        tell reading from deleting, and one of those is irreversible."""
        from master_agent.planner.catalogue import catalogue_from_index

        options = catalogue_from_index(catalogue)
        by_path = [o.name for o in options if tuple(o.required_args) == ("path",)]
        assert len(by_path) > 1
        assert any("Delete" in n for n in by_path)
        assert any("Read" in n for n in by_path)

    def test_names_match_across_the_three_spellings(self, catalogue):
        from master_agent.planner.catalogue import catalogue_from_index

        options = catalogue_from_index(catalogue)
        for spelling in ("create_folder", "CreateFolder", "Filesystem.CreateFolder"):
            found = find_option(spelling, options)
            assert found is not None and found.name == "Filesystem.CreateFolder"


# =========================================================================
# The Planner remains the only planner
# =========================================================================


class TestNoSecondRouter:

    def test_direct_planning_lives_inside_the_planner_package(self):
        import master_agent.planner.direct as direct

        assert direct.__name__.startswith("master_agent.planner.")

    def test_the_composition_root_holds_no_mode_policy(self):
        import inspect

        import kalpavriksha_desktop as kd

        source = inspect.getsource(kd._build_mission_pipeline)
        # The root may STORE the founder's choice; it must not act on it.
        for policy in ("if mode ==", "if mode in", "direct_plan(", "== 'local'"):
            assert policy not in source, (
                f"{policy!r} in the composition root -- the mode decision "
                "belongs to the Planner, not to wiring"
            )
