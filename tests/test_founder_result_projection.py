"""No implementation object reaches Onkar's screen.

The first AI-planned mission showed him `[object Object]` in the
work-state area while the conversation below it read correctly. Two
independent leak paths existed for one defect; `2ef7874` closed the
conversation one, and this closes the other:

    kalpavriksha_desktop.py   status.result = state.result   (raw object)
    execution_status.py       "result": self.result          (verbatim)
    app.js                    summary.textContent = exec.result || ...

Assigning an object to `textContent` is what JavaScript renders as
`[object Object]`.

The canonical value is deliberately NOT changed -- an internal consumer
that needs the real structure still has it. Only the founder-facing
transport is projected, and it projects a structure to `None` rather than
to prose: this layer has no idea what a capability's payload means, and
inventing a sentence for it would be reporting authority it does not
hold. `None` makes the surface fall through to `message`, which the
mission-level path has already composed truthfully.
"""
from __future__ import annotations

import pytest

from master_agent.missions.execution_status import ExecutionStatus, _founder_safe

CLEANUP = {"session_id": "research_session", "closed": True}


class TestNoRawStructureCrossesTheTransport:

    @pytest.mark.parametrize("raw", [
        CLEANUP, {"ok": True}, [1, 2], ("a",), {"x"}, b"bytes", bytearray(b"b"),
    ])
    def test_a_structure_is_projected_away(self, raw):
        assert _founder_safe(raw) is None

    def test_the_exact_observed_value_cannot_render(self):
        status = ExecutionStatus()
        status.result = CLEANUP
        status.message = "Done — the page loaded."
        published = status.as_dict()

        assert published["result"] is None
        for marker in ("session_id", "closed", "{", "}"):
            assert marker not in str(published["result"])

    def test_the_surface_falls_through_to_the_mission_sentence(self):
        """`exec.result || exec.message` -- a null result is what lets the
        already-correct mission-level sentence through."""
        status = ExecutionStatus()
        status.result = CLEANUP
        status.message = "Done — the page at https://example.com loaded."
        published = status.as_dict()
        rendered = published["result"] or published["message"]
        assert rendered.startswith("Done — the page")


class TestUsefulValuesAreUntouched:

    def test_a_path_string_passes_through(self):
        status = ExecutionStatus()
        status.result = r"C:\Users\DELL\Desktop\KVResultTest"
        assert status.as_dict()["result"] == r"C:\Users\DELL\Desktop\KVResultTest"

    @pytest.mark.parametrize("value", ["done", 42, 3.5, True, None])
    def test_scalars_pass_through(self, value):
        assert _founder_safe(value) == value


class TestTheCanonicalValueIsNotMutated:
    """Requirement A: internal structured data survives; only the
    projection changes."""

    def test_the_object_is_still_there_after_publishing(self):
        status = ExecutionStatus()
        status.result = CLEANUP
        status.as_dict()
        assert status.result == CLEANUP
        assert status.result is CLEANUP

    def test_the_projection_invents_no_prose(self):
        """A structure becomes absence, never a made-up summary -- this
        layer does not know what any payload means."""
        assert _founder_safe(CLEANUP) is None
        assert not isinstance(_founder_safe(CLEANUP), str)


class TestSendBackIsNotAnUnexplainedDeadControl:
    """It is deliberately unwired -- `confirm_completion()` is the only
    completion-namespace handler -- but it must say so where Onkar can
    read it, not only in a hover title."""

    def test_the_label_states_its_unavailability(self):
        import pathlib

        source = (pathlib.Path(__file__).resolve().parent.parent
                  / "desktop_app" / "web" / "js" / "app.js").read_text(encoding="utf-8")
        assert "Send back (not available yet)" in source
        assert "secondary.disabled = true" in source

    def test_it_is_still_not_wired_to_a_backend_action(self):
        """Guards against someone 'fixing' the dead button by pointing it
        at the approval namespace, which is a different subsystem."""
        import pathlib

        source = (pathlib.Path(__file__).resolve().parent.parent
                  / "desktop_app" / "web" / "js" / "app.js").read_text(encoding="utf-8")
        block = source.split("secondary.textContent")[1][:600]
        for wrong in ("decide_approval", "reject(", "defer("):
            assert wrong not in block
