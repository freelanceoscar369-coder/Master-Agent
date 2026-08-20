"""When no plan could be built, Somesh must not promise work.

The live CV mission produced this, over a mission with no plan, no tasks
and nothing waiting on an answer:

    "I am taking full responsibility for evaluating all your resume
     files... Shall I start cataloging those files now?"

recorded with `status=completed`. Nothing was cataloguing anything, and
there was no resumable work behind the question.

Two separate untruths. The turn asked `brain/advisory.py::advise()` what
to say about the request -- and an unconstrained reasoner asked that
question proposes a next action, because that is what the question
invites. Then it recorded the outcome as COMPLETED, which is how a
failure came to look like an acknowledgement.

The invariant: **Somesh may claim work is starting, underway or
continuing only when a real executable Mission exists.** These tests hold
the branch to it -- and, just as importantly, hold the *normal* path to
starting ordinary work without asking anyone's permission.

They do not police prose for words like "I'll" or "start". A blacklist
would treat the symptom; the branch itself has to know that `NO_STEPS`
carries no authority to promise anything.
"""
from __future__ import annotations

import ast
import inspect
import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
COMPOSITION = REPO / "kalpavriksha_desktop.py"


def _no_steps_branch() -> str:
    """The source of the branch under test, located structurally.

    Found by walking to the `if` whose test names `NO_STEPS` rather than
    by line number, so this keeps pointing at the right code when the file
    around it moves.
    """
    tree = ast.parse(COMPOSITION.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.If) and "NO_STEPS" in ast.unparse(node.test):
            return ast.unparse(node)
    raise AssertionError("no NO_STEPS branch found in the composition root")


@pytest.fixture(scope="module")
def branch():
    return _no_steps_branch()


class TestNoPlanIsNotWork:

    def test_it_starts_nothing(self, branch):
        """A branch that reached the runtime would be starting work that
        has no plan behind it."""
        for starting in ("runtime.", "dispatch", "submit_objective",
                         "mission_control.", "execute("):
            assert starting not in branch, (
                f"the no-plan branch reaches {starting!r}"
            )

    def test_it_is_not_reported_as_completed(self, branch):
        assert "status.status = COMPLETED" not in branch
        assert "status.status = FAILED" in branch

    def test_it_does_not_become_an_approval_request(self, branch):
        """No action is waiting for a yes, so nothing may say one is."""
        assert "AWAITING_APPROVAL" not in branch

    def test_a_missing_capability_is_not_a_clarification(self, branch):
        """Clarification is for a fact only the founder holds. "No plan
        could be built" is a statement about the machine."""
        assert "AWAITING_CLARIFICATION" not in branch
        assert "PendingClarification" not in branch
        assert "clarification_question" not in branch

    def test_it_no_longer_asks_an_unconstrained_reasoner_what_to_say(self, branch):
        """The root cause. `advise()` was asked what to say about the
        founder's request and answered with a plan of action."""
        assert "advise" not in branch
        assert "reasoning_runner" not in branch

    def test_the_sentence_comes_from_the_planners_own_refusal(self, branch):
        assert "_founder_no_plan_sentence(refusal)" in branch


class TestWhatTheFounderIsTold:
    """The composed sentence itself, from the real function."""

    @pytest.fixture
    def sentence(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "_kv_composition", COMPOSITION
        )
        module = importlib.util.module_from_spec(spec)
        # The module runs plenty at import; only the pure composer is
        # needed, so it is lifted out by source rather than executed.
        source = COMPOSITION.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and \
                    node.name == "_founder_no_plan_sentence":
                namespace: dict = {}
                exec(compile(ast.Module([node], []), "<composer>", "exec"),
                     namespace)
                return namespace["_founder_no_plan_sentence"]
        raise AssertionError("_founder_no_plan_sentence not found")

    class Refusal:
        code = "no_steps"
        reason = "no plan: the available capabilities cannot achieve this objective"
        detail = "The provider was given the full catalogue and returned no steps."
        known_capabilities = ("Filesystem.ReadFile", "Browser.Navigate")

    def test_it_says_the_request_was_understood(self, sentence):
        """Not planable is not not-understood -- the distinction the
        original branch was right to care about."""
        text = sentence(self.Refusal()).lower()
        assert "understood" in text

    def test_it_says_no_plan_could_be_built(self, sentence):
        text = sentence(self.Refusal()).lower()
        assert "plan" in text
        assert "couldn't" in text or "could not" in text

    def test_it_states_that_nothing_started(self, sentence):
        text = sentence(self.Refusal()).lower()
        assert "nothing has been started" in text

    def test_it_does_not_leak_developer_prose(self, sentence):
        """`reason` reads as a rejection of the founder and belongs on
        `errors`, not in the sentence."""
        assert self.Refusal.reason not in sentence(self.Refusal())

    def test_capabilities_are_counted_never_listed(self, sentence):
        text = sentence(self.Refusal())
        assert "2" in text
        assert "Filesystem.ReadFile" not in text

    def test_it_works_without_optional_refusal_fields(self, sentence):
        class Bare:
            code = "no_steps"

        assert sentence(Bare()).strip()


class TestOrdinaryWorkStillRunsItself:
    """The approval policy is unchanged, and this correction must not have
    made Kalpavriksha timid about normal work."""

    def test_read_only_work_needs_no_approval(self):
        from master_agent.permissions.permission_system import PermissionSystem
        from master_agent.plugins.base import RiskTier

        PermissionSystem().check("document", "extract_text", RiskTier.READ_ONLY)

    def test_the_gate_lets_read_only_work_straight_through(self):
        """The founder-facing boundary, not the executor's own relay
        check: READ_ONLY is outside the boundary entirely."""
        import inspect

        from master_agent.runtime.approval import PermissionSystemGate

        import ast
        import textwrap

        source = textwrap.dedent(inspect.getsource(PermissionSystemGate.check))
        tree = ast.parse(source)
        guard = next(
            node for node in ast.walk(tree)
            if isinstance(node, ast.If) and "READ_ONLY" in ast.unparse(node.test)
        )
        # Parsed rather than string-matched: the block is mostly comment,
        # and a window over the raw text would only be measuring how much
        # was written about it.
        assert isinstance(guard.body[-1], ast.Return)
        assert guard.body[-1].value is None, "read-only work is not 'approved'"

    def test_this_commit_changed_no_tier_policy(self):
        """The correction is confined to the no-plan sentence. Whatever the
        gate decides per tier, it decides exactly as it did before.

        Recorded plainly because there IS a discrepancy worth the founder's
        attention, and it is not this commit's to resolve: the stated
        Founder Edition policy is that a REVERSIBLE_WRITE runs
        automatically, and `PermissionSystemGate.check()` currently sends
        every tier above READ_ONLY to `_ask_founder`. So writing a revised
        copy of a document does ask today. This test asserts only that the
        behaviour is untouched here.
        """
        import inspect

        from master_agent.runtime.approval import PermissionSystemGate

        source = inspect.getsource(PermissionSystemGate.check)
        # One short-circuit, one escalation path -- the shape it had.
        assert source.count("if tier_value ==") == 1
        assert "_ask_founder" in source

    def test_an_irreversible_action_still_asks(self):
        """The boundary that does exist, unchanged."""
        from master_agent.permissions.permission_system import (
            ApprovalRequired,
            PermissionSystem,
        )
        from master_agent.plugins.base import RiskTier

        with pytest.raises(ApprovalRequired):
            PermissionSystem().check(
                "filesystem", "delete_folder", RiskTier.IRREVERSIBLE
            )

    def test_a_standing_grant_never_satisfies_an_irreversible_check(self):
        from master_agent.permissions.permission_system import (
            ApprovalRequired,
            GrantScope,
            PermissionSystem,
        )
        from master_agent.plugins.base import RiskTier

        permissions = PermissionSystem()
        permissions.grant(
            "filesystem", "delete_folder", GrantScope.ALWAYS_FOR_CAPABILITY
        )
        with pytest.raises(ApprovalRequired):
            permissions.check(
                "filesystem", "delete_folder", RiskTier.IRREVERSIBLE
            )

    def test_a_planned_mission_is_not_routed_through_the_no_plan_branch(self):
        """The normal path: a plan exists, so the branch is skipped and the
        mission proceeds on its own."""
        branch = _no_steps_branch()
        tree = ast.parse(f"if x:\n    pass\n")
        # The guard requires BOTH a refusal object and the NO_STEPS code,
        # so an accepted plan (refusal is None) cannot enter it.
        assert "refusal is not None" in branch
        assert "NO_STEPS" in branch


class TestTheRepairIsNotAPhraseFilter:
    """§: do not solve this by scanning generated prose."""

    def test_no_word_blacklist_was_introduced(self):
        source = COMPOSITION.read_text(encoding="utf-8")
        tree = ast.parse(source)
        code = "\n".join(
            ast.unparse(node) for node in tree.body
            if not isinstance(node, ast.Expr)
        )
        for symptom_scan in ("\"shall i\"", "'shall i'", "\"i'll\"",
                             "banned_phrases", "forbidden_words"):
            assert symptom_scan not in code.lower(), (
                f"a prose blacklist was introduced: {symptom_scan}"
            )

    def test_the_advisory_module_still_exists(self):
        """Removed from this branch, not deleted -- it remains available
        for callers that genuinely want an opinion."""
        from master_agent.brain.advisory import advise  # noqa: F401

        assert callable(advise)


class TestEveryExecutiveReachesThePlanner:
    """The omission that made a capable machine refuse.

    `Document` and `Reasoning` were registered with Mission Control and
    left out of the two loops that matter: the one building the Planner's
    capability catalogue, and the one pre-granting each Executive's
    reversible actions. So the Planner could not see reading a document or
    reasoning over one, and answered the founder's objective with
    `NO_STEPS` -- correctly, about a machine that could do the work. It
    reported checking 43 capabilities; the three it was never shown were
    the three the objective needed.

    Read structurally: a future Executive added to the registry and
    forgotten here fails these rather than a founder finding out.
    """

    @staticmethod
    def _plugin_tuples() -> list[set[str]]:
        """Every `for plugin in (...)` fan-out in the composition root."""
        tree = ast.parse(COMPOSITION.read_text(encoding="utf-8"))
        found = []
        for node in ast.walk(tree):
            if isinstance(node, ast.For) and isinstance(node.iter, ast.Tuple):
                names = {
                    element.id for element in node.iter.elts
                    if isinstance(element, ast.Name)
                }
                if any(name.endswith("_plugin") for name in names):
                    found.append(names)
        return found

    def test_the_registered_executives_are_the_ones_wired(self):
        source = COMPOSITION.read_text(encoding="utf-8")
        registered = {
            line.split("registry.register(")[1].split(")")[0].strip()
            for line in source.splitlines()
            if "registry.register(" in line and "provider_registry" not in line
        }
        registered = {name for name in registered if name.endswith("_plugin")}
        assert registered, "no plugin registrations found"

        for names in self._plugin_tuples():
            missing = registered - names
            assert not missing, (
                f"registered but left out of a composition loop: {sorted(missing)}"
            )

    def test_document_and_reasoning_are_in_every_loop(self):
        """Named explicitly: these two are the ones that were missed, and
        the objective that exposed it needs all three of their
        capabilities."""
        for names in self._plugin_tuples():
            assert "document_plugin" in names
            assert "reasoning_plugin" in names
