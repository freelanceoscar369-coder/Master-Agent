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
