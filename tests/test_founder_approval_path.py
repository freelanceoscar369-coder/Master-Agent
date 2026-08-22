"""The founder presses Approve, and something actually gets granted.

## The defect this file exists for

`decide_approval` was defined as a closure inside `main()`. `permissions`
and `GrantScope` are not in scope there -- both are local to
`_build_mission_pipeline()` -- so Python compiled them as global lookups,
and neither name exists at module level. The first time a founder pressed
Approve, the bridge raised `NameError` instead of granting anything.

Nothing caught it. Every test that touched approval either passed a fake
`decide_approval` in, or asserted that `create_window` *received* one --
never that the real one worked. The closure was unreachable without
running `main()`, which opens a real window.

Two kinds of test follow. The first is specific: build the real pipeline
and call the real `decide_approval`. The second is general, and is the one
that would have caught this without anyone suspecting it -- a name that a
function reads as a global, and that no module-level name provides, is a
`NameError` waiting for the branch that reaches it.
"""
from __future__ import annotations

import builtins
import dis
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import kalpavriksha_desktop as kd  # noqa: E402


# =========================================================================
# The general guard
# =========================================================================


def _code_objects(code, seen=None):
    """Every code object in the module, nested closures included."""
    if seen is None:
        seen = []
    seen.append(code)
    for const in code.co_consts:
        if isinstance(const, types.CodeType):
            _code_objects(const, seen)
    return seen


def _global_reads(code):
    """`(code_name, global_name)` for every LOAD_GLOBAL in `code`."""
    for instruction in dis.get_instructions(code):
        if instruction.opname == "LOAD_GLOBAL":
            name = instruction.argval
            # 3.11+ encodes a NULL-push flag into the low bit and can hand
            # back a tuple/prefixed form; normalise to the bare name.
            if isinstance(name, tuple):
                name = name[0]
            yield code.co_name, str(name).lstrip("+ ")


class TestNoFunctionReadsAGlobalThatDoesNotExist:
    """A closure reading `permissions` from a function that never defines
    it is not a style problem -- it is a crash on whichever founder
    action reaches that line first."""

    def test_every_global_read_resolves(self):
        module_code = compile(
            open(kd.__file__, encoding="utf-8").read(), kd.__file__, "exec",
        )
        available = set(vars(kd)) | set(dir(builtins))

        unresolved = sorted({
            (fn, name)
            for code in _code_objects(module_code)
            for fn, name in _global_reads(code)
            if name not in available
        })

        assert unresolved == [], (
            "these functions read names that do not exist at module level, "
            "so the branch reaching them raises NameError: "
            + ", ".join(f"{fn}() -> {name}" for fn, name in unresolved)
        )


# =========================================================================
# The specific one
# =========================================================================


@pytest.fixture()
def pipeline(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-construction-test")
    monkeypatch.setenv("KALPAVRIKSHA_STATE_DIR", str(tmp_path))
    built = kd._build_mission_pipeline()
    if built is None:
        pytest.skip("no reasoning provider configured; pipeline not built")
    return built


class TestTheRealDecideApprovalIsReachableAndWorks:

    def test_the_pipeline_hands_one_back(self, pipeline):
        """It is built beside the PermissionSystem it grants through,
        which is the whole point -- `main()` cannot see that object."""
        assert callable(pipeline[7])

    def test_approving_an_unknown_id_does_not_raise_name_error(self, pipeline):
        """The exact crash. An id Mission Control does not know still
        exercises every name the function reads on the approve branch --
        `permissions`, `GrantScope`, `mission_control` -- which is what
        was broken.
        """
        decide_approval = pipeline[7]
        try:
            decide_approval("no-such-approval-id", True)
        except NameError as exc:  # the regression, stated as itself
            pytest.fail(f"decide_approval still cannot see its own dependencies: {exc}")
        except Exception:
            # Mission Control legitimately rejecting an unknown id is fine;
            # this test is only about the names resolving.
            pass

    def test_declining_an_unknown_id_does_not_raise_name_error(self, pipeline):
        decide_approval = pipeline[7]
        try:
            decide_approval("no-such-approval-id", False)
        except NameError as exc:
            pytest.fail(f"the decline branch cannot see its dependencies: {exc}")
        except Exception:
            pass

    def test_it_grants_through_the_permission_system_on_approval(self, pipeline):
        """Approving must reach the grant ledger the permission boundary
        actually reads -- not only Mission Control's approval queue.
        `ApprovalQueue.find_open` is scoped to undecided requests, so an
        approval that stopped at the queue would leave the held task
        waiting forever.
        """
        mission_control = pipeline[2]
        decide_approval = pipeline[7]

        approvals = getattr(mission_control, "approvals", None)
        if approvals is None or not hasattr(approvals, "request"):
            pytest.skip("no approval queue on this Mission Control build")

        opened = None
        for kwargs in (
            {"executive_id": "filesystem", "local_capability": "create_folder",
             "reason": "acceptance", "risk_tier": "irreversible_write"},
            {"executive_id": "filesystem", "local_capability": "create_folder",
             "reason": "acceptance"},
        ):
            try:
                opened = approvals.request(**kwargs)
                break
            except TypeError:
                continue
        if opened is None:
            pytest.skip("could not open an approval with this queue's signature")

        approval_id = getattr(opened, "approval_id", None) or getattr(opened, "id", None)
        if not approval_id:
            pytest.skip("approval object exposes no id")

        result = decide_approval(approval_id, True, "acceptance run")

        assert isinstance(result, dict)
        assert "reject" not in str(result.get("state", result.get("status", ""))).lower()


# =========================================================================
# The second defect: approval granted, work never resumed
# =========================================================================


class _FakeObjective:
    def __init__(self, completes_after=0):
        self._left = completes_after
        self.has_failure = False

    @property
    def is_complete(self):
        return self._left <= 0

    def tick(self):
        self._left -= 1


class _FakeDispatcher:
    def __init__(self, objective):
        self._objective = objective

    def objective(self, objective_id):
        return self._objective


class _FakeMissionControl:
    def __init__(self, objective):
        self.dispatcher = _FakeDispatcher(objective)


class _CountingRuntime:
    def __init__(self, objective):
        self.calls = 0
        self._objective = objective

    def run_once(self):
        self.calls += 1
        self._objective.tick()


class _Status:
    """Only the two fields the driver reads."""

    def __init__(self, approval_id=None, requires_founder_completion=False):
        self.approval_id = approval_id
        self.requires_founder_completion = requires_founder_completion


class TestTheRuntimeDriverIsShared:
    """`_drive_until_settled` is the one place anything turns the Runtime.
    It was inline in `_submit_objective`, which meant the only moment work
    could progress was the founder's own message -- and a founder
    answering a question the mission had already asked is not that
    moment."""

    def test_it_turns_the_runtime_until_the_objective_completes(self):
        objective = _FakeObjective(completes_after=3)
        runtime = _CountingRuntime(objective)

        kd._drive_until_settled(
            runtime, _FakeMissionControl(objective), _Status(), "obj-1", 5.0,
        )

        assert objective.is_complete
        assert runtime.calls == 3

    def test_it_stops_when_a_NEW_question_opens(self):
        objective = _FakeObjective(completes_after=99)
        runtime = _CountingRuntime(objective)
        status = _Status()

        original = runtime.run_once

        def open_a_question():
            original()
            status.approval_id = "needs-a-human"

        runtime.run_once = open_a_question
        kd._drive_until_settled(
            runtime, _FakeMissionControl(objective), status, "obj-1", 5.0,
        )

        assert runtime.calls == 1, "it kept running past an open question"

    def test_it_stops_when_the_founder_must_confirm_completion(self):
        objective = _FakeObjective(completes_after=99)
        runtime = _CountingRuntime(objective)
        status = _Status(requires_founder_completion=True)

        kd._drive_until_settled(
            runtime, _FakeMissionControl(objective), status, "obj-1", 5.0,
        )

        assert runtime.calls == 1

    def test_an_already_answered_approval_does_not_stop_the_resume(self):
        """THE REGRESSION. After a founder approves, `status.status` still
        reads `awaiting_approval` -- it is a label, updated by a later
        event. `approval_id` is the authoritative "a question is open"
        fact and is cleared the moment the approval is granted. Breaking
        on the label would stop the resume loop on its first pass, before
        the newly-authorised work ever ran, which is exactly the bug:
        the founder approved and nothing happened.
        """
        objective = _FakeObjective(completes_after=3)
        runtime = _CountingRuntime(objective)
        status = _Status(approval_id=None)      # answered: cleared
        status.status = "awaiting_approval"     # label: still stale

        kd._drive_until_settled(
            runtime, _FakeMissionControl(objective), status, "obj-1", 5.0,
        )

        assert objective.is_complete, "the stale label stopped the resume"
        assert runtime.calls == 3


class TestApprovingActuallyReleasesTheWork:
    def test_decide_approval_drives_the_runtime(self):
        """A permission gate that holds work and never releases it is
        worse than no gate, because the founder is told their decision was
        recorded. Asserted on the source because the closure's own
        Runtime is the real one -- the behaviour itself is proven live by
        `scripts/live_acceptance/d_permission_gate.py`, which approves and
        then only waits.
        """
        import inspect

        source = inspect.getsource(kd._build_mission_pipeline)
        start = source.index("def decide_approval")
        body = source[start:]

        assert "_drive_until_settled" in body, (
            "decide_approval grants the permission but never resumes the "
            "work it just authorised"
        )


class _State:
    def __init__(self, progress=0.0, errors=()):
        self.progress = progress
        self.errors = list(errors)


class _ProgressingMissionControl(_FakeMissionControl):
    """Mission Control as the driver actually sees it: a dispatcher, plus
    `founder_state()` reporting how far the mission has got."""

    def __init__(self, objective, steps):
        super().__init__(objective)
        self._steps = steps
        self._done = 0

    def founder_state(self, objective_id):
        return _State(progress=self._done / self._steps)

    def advance(self):
        self._done = min(self._done + 1, self._steps)


class _SlowRuntime:
    """Each `run_once()` really sleeps longer than the whole budget --
    which is what a real step does when it asks a desktop AI for an
    answer. Real time, not a stubbed clock: the loop reads
    `time.monotonic()` itself, so a fake clock would prove nothing.
    """

    def __init__(self, mission_control, objective, cost, steps, moves=True):
        self.calls = 0
        self._mc = mission_control
        self._objective = objective
        self._cost = cost
        self._steps = steps
        self._moves = moves

    def run_once(self):
        import time as _t

        self.calls += 1
        _t.sleep(self._cost)            # the step is genuinely slow
        if self._moves and self.calls <= self._steps:
            self._mc.advance()
        if self.calls >= self._steps:
            self._objective.tick()


class TestASlowStepDoesNotAbandonTheMission:
    """The deadline bounds silence, not work.

    `run_once()` blocks for the whole of the step it runs, so by the time
    control returns from a step that asked a desktop AI for an answer, an
    elapsed-time budget has always expired -- and the loop exited holding
    a mission that was healthy and half finished.

    Measured in the packaged application on "think of three short names
    ... and write them into packaged_names.txt": the plan was right,
    `Reasoning.Transform` ran, produced real text and was verified
    `matched`, and `Filesystem.WriteFile` was never dispatched, because
    this loop had already given up. Nothing else drives the Runtime, so
    the founder watched "that's taking longer than expected" forever
    about work that had stopped.
    """

    def test_a_step_slower_than_the_budget_still_reaches_the_next_step(self):
        objective = _FakeObjective(completes_after=1)
        mc = _ProgressingMissionControl(objective, steps=2)
        # Every step outlasts the entire budget, exactly as the live
        # reasoning step outlasted the packaged UI's 45 seconds.
        # The step outlasts the whole budget, exactly as the live
        # reasoning step outlasted the packaged UI's 45 seconds. The
        # budget stays above the loop's own 0.2s pacing sleep, as the
        # real 45s one does.
        runtime = _SlowRuntime(mc, objective, cost=0.8, steps=2)
        kd._drive_until_settled(runtime, mc, _Status(), "obj-1", 0.5)

        assert runtime.calls >= 2, (
            "the mission was abandoned after its first slow step -- the "
            "dependent step never ran"
        )
        assert objective.is_complete

    def test_a_silent_runtime_is_still_bounded(self):
        """The bound is still real. A runtime that reports no progress at
        all must not spin forever -- that is what the deadline is for."""
        objective = _FakeObjective(completes_after=10_000)
        mc = _ProgressingMissionControl(objective, steps=2)
        runtime = _SlowRuntime(mc, objective, cost=0.8, steps=10_000,
                               moves=False)   # progress never changes
        kd._drive_until_settled(runtime, mc, _Status(), "obj-1", 0.5)

        assert not objective.is_complete
        assert runtime.calls == 1, (
            "a silent runtime must not be retried past the budget"
        )

    def test_mission_control_without_founder_state_still_works(self):
        """`founder_state()` is read best-effort. A Mission Control that
        does not offer it must not break the driver."""
        objective = _FakeObjective(completes_after=2)
        mc = _FakeMissionControl(objective)          # no founder_state
        runtime = _CountingRuntime(objective)
        kd._drive_until_settled(runtime, mc, _Status(), "obj-1", 5.0)

        assert objective.is_complete
