"""The complete Universal Executive Operator lifecycle, demonstrated
end-to-end -- this is Mission Brief 022's required live verification, not
just another unit test. See BROWSER_WORKER_ARCHITECTURE.md §1, §11 and
docs/MISSION_BRIEF_022.md's Success Criteria section.

Two integration surfaces are both exercised, because this Mission Brief
deliberately built two (see BROWSER_WORKER_ARCHITECTURE.md §11):

1. A hand-built Step (standing in for a real Planner, exactly the way
   Mission Brief 001 hand-built a plan before a real Planner existed)
   resolved and executed through the real, completely unmodified
   Orchestrator + PluginRegistry + PermissionSystem -- proving Capability
   Registry integration works for a second, unrelated capability family.
2. BrowserWorker, called directly, carrying that same execution through
   Verification and Audit and back to a stand-in for the Executive Brain
   -- proving the complete Execute -> Verify -> Evidence -> Brain loop
   ADR-0011 defines.

Both paths execute through the identical LocalExecutor and the identical
nine Actions -- there are not two implementations of browser execution,
only two callers of the same one.
"""
from __future__ import annotations

from master_agent.executor.executor import LocalExecutor
from master_agent.orchestrator.orchestrator import Orchestrator
from master_agent.permissions.permission_system import GrantScope, PermissionSystem
from master_agent.planner.planner import Step
from master_agent.plugins.browser_plugin import BrowserPlugin
from master_agent.plugins.browser_worker import BrowserWorker
from master_agent.plugins.registry import PluginRegistry
from master_agent.verification.evidence import ExpectedOutcome, ObservationCheck, Verdict

SAMPLE_HTML = """
<html><head><title>Lifecycle Demo Page</title></head>
<body><h1 id="heading">Ready</h1><button id="go">Go</button></body></html>
"""


def test_full_lifecycle_through_the_real_orchestrator_and_plugin_registry():
    """Founder Request -> Executive Brain (hand-built Step) -> Shared
    Infrastructure (PermissionSystem, Capability Registry) -> Universal
    Executive Operator (Orchestrator) -> Browser Worker -> Playwright ->
    Browser."""
    permissions = PermissionSystem()
    executor = LocalExecutor(permissions)
    from master_agent.environment.browser_session import BrowserSessionManager

    sessions = BrowserSessionManager()
    plugin = BrowserPlugin(executor, sessions)

    registry = PluginRegistry()
    registry.register(plugin)
    orchestrator = Orchestrator(registry, permissions)

    try:
        # A human approves this Mission's one step once -- the Orchestrator's
        # own grant key, (plugin_name, capability), unrelated to the
        # Executor's own key that BrowserPlugin.invoke() relays to.
        permissions.grant("browser", "open_browser_session", GrantScope.ONCE)

        step = Step(step_id="open-1", capability="open_browser_session", payload={"session_id": "lifecycle"})
        step_result = orchestrator.execute_step(step)

        assert step_result.blocked_on_approval is False
        assert step_result.result.success is True
        assert sessions.get("lifecycle").is_open
    finally:
        sessions.close_all()


def test_full_lifecycle_through_browser_worker_including_verification_and_evidence():
    """Founder Request -> Executive Brain (ExpectedOutcome attached to the
    Step, per KALPAVRIKSHA_VISION_V2.md §3.2) -> Browser Worker -> Playwright
    -> Browser -> Verifier -> Evidence -> Executive Brain (the returned
    BrowserStepReport, which is what a real Brain integration would consume
    next)."""
    from master_agent.environment.browser_session import BrowserSessionManager

    permissions = PermissionSystem()
    executor = LocalExecutor(permissions)
    sessions = BrowserSessionManager()
    BrowserPlugin(executor, sessions)
    worker = BrowserWorker(executor, sessions)

    def approve(capability: str) -> None:
        # Stands in for a human approving each step of this Mission --
        # relayed to the Executor's own grant key, exactly as
        # BrowserPlugin.invoke() would do it, since BrowserWorker itself
        # deliberately never self-grants (BROWSER_WORKER_ARCHITECTURE.md §11).
        permissions.grant(executor.name, capability, GrantScope.ONCE)

    try:
        approve("open_browser_session")
        opened = worker.run_step(
            "open_browser_session", {"session_id": "lifecycle"}, requested_by="founder"
        )
        assert opened.execution.success

        sessions.get("lifecycle").page.set_content(SAMPLE_HTML)

        approve("click")
        clicked = worker.run_step(
            "click",
            {"session_id": "lifecycle", "selector": "#go"},
            requested_by="founder",
            expected_outcome=ExpectedOutcome(
                description="the page heading still reads Ready after clicking Go",
                checks=[ObservationCheck(field="elements.0.text", operator="equals", value="Ready")],
            ),
            verify_selectors=["#heading"],
        )

        # Execution succeeded (the click ran) -- but Mission success is
        # decided by Evidence, not by that success flag (ADR-0011).
        assert clicked.execution.success is True
        assert clicked.evidence is not None
        assert clicked.evidence.verdict == Verdict.MATCHED
        assert clicked.evidence.worker == "browser"
        assert clicked.evidence.environment == "browser_environment"

        # Audit ties requester, worker, verdict, and evidence together --
        # nothing about this Mission's history is lost.
        assert clicked.audit.requested_by == "founder"
        assert clicked.audit.verification_verdict == Verdict.MATCHED
        assert clicked.audit.evidence_id == clicked.evidence.evidence_id

        approve("close_browser_session")
        closed = worker.run_step(
            "close_browser_session", {"session_id": "lifecycle"}, requested_by="founder"
        )
        assert closed.execution.success

        # The complete, ordered history of this Mission, exactly as it
        # happened -- proving "never lose execution history."
        assert [r.action_name for r in worker.audit_log.records] == [
            "open_browser_session",
            "click",
            "close_browser_session",
        ]
    finally:
        sessions.close_all()
