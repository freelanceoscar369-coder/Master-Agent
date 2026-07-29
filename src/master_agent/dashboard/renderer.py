"""Frame composition -- the whole rendering contract is one function.

`render_frame(snapshot) -> str`. A future web or desktop front-end
consumes the same DashboardSnapshot and ignores this module entirely; the
read model, not the renderer, is the reusable asset (ADR-0016).
"""
from __future__ import annotations

from master_agent.dashboard.charset import Charset
from master_agent.dashboard.panels import (
    render_approvals,
    render_audit,
    render_capabilities,
    render_executives,
    render_founder_state,
    render_header,
    render_mission,
    render_persistence,
    render_runtime,
    render_system_health,
    rule,
)
from master_agent.dashboard.readmodel import DashboardSnapshot

CLEAR_SCREEN = "\033[2J\033[H"


def render_frame(
    snapshot: DashboardSnapshot,
    audit_limit: int | None = 8,
    include_founder_state: bool = True,
    charset: Charset | None = None,
) -> str:
    """Compose every panel into one frame.

    Panel order is deliberate: what is happening now (runtime, mission)
    before who is doing it (executives, capabilities), before the record
    of it (audit, persistence), before the summary (system health). A
    founder glancing at the top of the screen should see the answer to
    "is it working right now".

    **Pending approvals come first**, above even the Runtime, because
    they are the only thing on the screen the founder must *act* on --
    everything else is something to know. A blocked system whose reason
    for being blocked is eight panels down is a system that looks broken
    (MB028.1).
    """
    sections: list[list[str]] = [
        render_header(snapshot, charset),
        render_approvals(snapshot.approvals, charset),
        render_runtime(snapshot.runtime, charset),
        render_mission(snapshot.mission, charset),
        render_executives(snapshot.executives, charset),
        render_capabilities(snapshot.capabilities, charset),
        render_audit(snapshot.audit, audit_limit, charset),
        render_persistence(snapshot.persistence, charset),
        render_system_health(snapshot.system_health, charset),
    ]
    if include_founder_state:
        sections.append(render_founder_state(snapshot.founder_state, charset))

    lines: list[str] = []
    for index, section in enumerate(sections):
        lines.extend(section)
        if index == 0:
            continue
        lines.append(rule(charset=charset) if index == len(sections) - 1 else rule(".", charset))

    return "\n".join(lines)
