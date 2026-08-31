"""Every registered Executive can actually be reached by the Runtime.

## The defect this file exists for

`Document.ExtractText`, `Document.WriteDocument` and `Reasoning.Transform`
were registered in Mission Control, visible to the Planner, and granted
permissions — and had **no gateway**. The Runtime does not fall back when
one is missing; `runtime/engine.py` fails the task outright:

    no gateway registered for executive 'document' (task step_1)

So a founder could ask for a document, the Planner could plan it, the
permission boundary could approve it, and the work could not run. The
Document Executive itself was fine the whole time — the first thing it did
once wired was write a valid 35 KB `.docx`.

Nothing caught it because every existing test either used a fake runtime
or exercised the three executives that *did* have gateways. The count of
registered capabilities was asserted in several places; the count of
*reachable* ones was asserted nowhere.

## Why this is a general guard, not two assertions

Registering a capability and registering a gateway are separate lines in
the composition root, and nothing ties them together. A sixth Executive
added next month would repeat this exactly. So the test asks the running
system for both sets and compares them, rather than naming the executives
it happens to know about today.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import kalpavriksha_desktop as kd  # noqa: E402


@pytest.fixture(scope="module")
def pipeline(tmp_path_factory):
    os.environ.setdefault("GEMINI_API_KEY", "fake-key-for-construction-test")
    built = kd._build_mission_pipeline()
    if built is None:
        pytest.skip("no reasoning provider configured; pipeline not built")
    return built


def _executives_with_capabilities(mission_control) -> set[str]:
    return {str(c.executive_id) for c in mission_control.capabilities.all()}


class TestNoCapabilityIsRegisteredWithoutAWayToRunIt:

    def test_every_executive_holding_capabilities_has_a_gateway(self, pipeline):
        """The general form. A capability the Planner can name and the
        Runtime cannot reach is worse than an absent one: it gets planned,
        approved, and then fails."""
        _service, runtime, mission_control, *_rest = pipeline

        registered = _executives_with_capabilities(mission_control)
        reachable = set(runtime._gateways)

        unreachable = sorted(registered - reachable)

        assert unreachable == [], (
            "these executives have registered capabilities the Runtime "
            "cannot reach — the Planner can name them and every task will "
            "fail with 'no gateway registered': " + ", ".join(unreachable)
        )

    def test_the_two_that_were_missing_are_specifically_present(self, pipeline):
        """Named as well as generalised, so the regression is legible in a
        failure message rather than only in a diff."""
        _service, runtime, *_rest = pipeline

        assert "document" in runtime._gateways
        assert "reasoning" in runtime._gateways

    def test_document_writes_use_the_verifying_gateway(self, pipeline):
        from master_agent.plugins.document_gateway import DocumentGateway

        _service, runtime, *_rest = pipeline

        assert isinstance(runtime._gateways["document"], DocumentGateway)

    def test_no_gateway_is_registered_for_an_executive_with_no_capabilities(self, pipeline):
        """The other direction. A gateway for an executive that registers
        nothing is dead wiring — harmless, but it means the composition
        and the registry disagree about what exists."""
        _service, runtime, mission_control, *_rest = pipeline

        registered = _executives_with_capabilities(mission_control)
        orphans = sorted(set(runtime._gateways) - registered)

        assert orphans == [], f"gateways with no registered capabilities: {orphans}"


class TestTheDesktopVerificationSurfaceIsNotOverclaimed:
    """§8 of the wiring brief: re-establish `supports()` dynamically and do
    not turn the rest into "verification gaps"."""

    def test_exactly_the_capabilities_with_a_read_only_postcondition_verify(self, pipeline):
        from master_agent.desktop import gateway as desktop_gateway

        _service, _runtime, mission_control, *_rest = pipeline
        desktop = [
            c.qualified_name for c in mission_control.capabilities.all()
            if str(c.executive_id) == "desktop"
        ]

        verifiable = sorted(c for c in desktop if desktop_gateway.supports(c))

        assert verifiable == [
            "Desktop.BringToFront",
            "Desktop.CloseApplication",
            "Desktop.FocusWindow",
            "Desktop.LaunchApplication",
        ]

    def test_a_click_is_not_claimed_to_be_verifiable(self, pipeline):
        """The brief's own example. `click(x, y)` has no universal
        postcondition — whether it worked is a question about the Step's
        intended observable outcome, not about the mouse. Saying so is the
        truthful answer; manufacturing Evidence would not be."""
        from master_agent.desktop import gateway as desktop_gateway

        assert desktop_gateway.supports("Desktop.DesktopClick") is False
        assert desktop_gateway.supports("Desktop.DesktopTypeText") is False
