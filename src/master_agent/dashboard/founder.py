"""The Founder view model (Mission Brief 029).

The engineering Dashboard is technically correct and cognitively
expensive. This layer answers the only three questions a founder actually
has:

    What is Kalpavriksha doing?   Does it need me?   What should happen next?

**This module is Deliverable 10.** `DashboardSnapshot` is the read model
(what the system published); `FounderView` is the *view* model (what a
founder should be shown). A web dashboard, a desktop app, or a phone
consumes `FounderView` and writes its own renderer — Mission Control is
never touched, because nothing above this line knows what a terminal is.

```
contracts -> sources.py -> DashboardSnapshot -> founder.py -> FounderView -> any renderer
             (reads)       (read model)         (this)        (view model)
```

Everything here is a **pure function of the snapshot** plus the roadmap
tables. No I/O, no live objects, no clock of its own — so a view is
reproducible from a snapshot, which is what makes a web front-end able to
render exactly what the console rendered.

**Nothing here invents a number.** Where a value is not measured, the
field is `None` and the renderer says so. MB029 asks for "Confidence" and
"Time Saved"; neither exists as data, so both are derived honestly from
what does exist or reported as unmeasured (see `_confidence` and
`DailySummary.time_saved_note`).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from master_agent.dashboard.readmodel import DashboardSnapshot
from master_agent.dashboard.roadmap import (
    EXPECTED_EXECUTIVES,
    MISSING,
    NOTHING_NEEDED,
    PLANNED,
    READY,
    RECOMMENDATIONS,
    SELF_DEVELOPMENT_PHASES,
)

WORKING = "Working normally"
NEEDS_ATTENTION = "Needs attention"
WAITING_ON_YOU = "Waiting on you"


@dataclass(frozen=True)
class ExecutiveReadiness:
    label: str
    status: str
    detail: str = ""

    @property
    def is_ready(self) -> bool:
        return self.status == READY


@dataclass(frozen=True)
class PhaseProgress:
    label: str
    fraction: float
    basis: str


@dataclass(frozen=True)
class WorkTally:
    """Deliverable 1's "Today's Work". Named `tally` rather than `stats`
    because these are counts of things that happened, not measurements."""

    completed: int = 0
    running: int = 0
    awaiting_approval: int = 0
    failed: int = 0


@dataclass(frozen=True)
class MissionView:
    """Deliverable 4. Every field optional: a system with no mission is a
    normal state, not a missing panel."""

    name: str | None = None
    current_step: str | None = None
    steps_remaining: int | None = None
    progress: float | None = None
    estimated_seconds: float | None = None
    confidence: str | None = None
    confidence_basis: str = ""


@dataclass(frozen=True)
class DecisionView:
    """Deliverable 7. One thing the founder must answer."""

    index: int
    title: str
    impact: str
    risk_tier: str
    requested_at: str
    executive: str


@dataclass(frozen=True)
class FounderView:
    """Everything the founder page shows, as plain data."""

    status: str = WORKING
    status_reason: str = ""
    mission: MissionView = field(default_factory=MissionView)
    work: WorkTally = field(default_factory=WorkTally)
    executives: list[ExecutiveReadiness] = field(default_factory=list)
    decisions: list[DecisionView] = field(default_factory=list)
    phases: list[PhaseProgress] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    next_step: str = ""

    @property
    def needs_founder(self) -> bool:
        return bool(self.decisions)


def build_founder_view(snapshot: DashboardSnapshot) -> FounderView:
    """One pure function, snapshot in, view out."""
    executives = _executives(snapshot)
    decisions = _decisions(snapshot)
    recommendations = _recommendations(executives)
    status, reason = _status(snapshot, executives, decisions)

    return FounderView(
        status=status,
        status_reason=reason,
        mission=_mission(snapshot),
        work=_work(snapshot),
        executives=executives,
        decisions=decisions,
        phases=[
            PhaseProgress(p.label, p.fraction, p.basis)
            for p in SELF_DEVELOPMENT_PHASES
        ],
        recommendations=recommendations,
        next_step=recommendations[0] if recommendations else NOTHING_NEEDED,
    )


# ---- derivations --------------------------------------------------------


def _executives(snapshot: DashboardSnapshot) -> list[ExecutiveReadiness]:
    """Deliverable 5. Readiness is checked against what is *registered* —
    the roadmap says what should exist, live state says what does."""
    registered = {
        row.executive_id: row for row in (snapshot.executives.executives or [])
    }
    readiness = []
    for expected in EXPECTED_EXECUTIVES:
        row = registered.get(expected.executive_id)
        if row is not None:
            detail = "" if row.health == "healthy" else f"health: {row.health}"
            readiness.append(ExecutiveReadiness(expected.label, READY, detail))
        elif expected.planned:
            readiness.append(
                ExecutiveReadiness(expected.label, PLANNED, expected.source)
            )
        else:
            readiness.append(
                ExecutiveReadiness(expected.label, MISSING, expected.source)
            )
    return readiness


def _decisions(snapshot: DashboardSnapshot) -> list[DecisionView]:
    return [
        DecisionView(
            index=row.index,
            title=row.reason or row.capability,
            impact=row.impact,
            risk_tier=row.risk_tier,
            requested_at=row.requested_at,
            executive=row.executive_id,
        )
        for row in (snapshot.approvals.approvals or [])
    ]


def _work(snapshot: DashboardSnapshot) -> WorkTally:
    capabilities = snapshot.capabilities
    return WorkTally(
        completed=capabilities.completed or 0,
        running=capabilities.active or 0,
        awaiting_approval=snapshot.approvals.count,
        failed=capabilities.failed or 0,
    )


def _mission(snapshot: DashboardSnapshot) -> MissionView:
    mission = snapshot.mission
    if not mission.status.available or not mission.objective:
        return MissionView()

    remaining = None
    capabilities = snapshot.capabilities
    if capabilities.pending is not None and capabilities.active is not None:
        remaining = capabilities.pending + capabilities.active

    confidence, basis = _confidence(snapshot)
    return MissionView(
        name=mission.objective,
        current_step=mission.active_capability,
        steps_remaining=remaining,
        progress=mission.progress,
        estimated_seconds=mission.eta_seconds,
        confidence=confidence,
        confidence_basis=basis,
    )


def _confidence(snapshot: DashboardSnapshot) -> tuple[str | None, str]:
    """MB029 asks for "Confidence". No such metric exists, and inventing
    one would be exactly the fabrication ADR-0016 forbids — a founder
    would read it as a prediction.

    So confidence is reported as a *reading of the verification record*,
    with the basis stated, and as `None` when there is nothing to read.
    Verified steps are the only evidence this system has that things are
    actually working (ADR-0011).
    """
    failed = snapshot.capabilities.failed or 0
    completed = snapshot.capabilities.completed or 0
    evidence = snapshot.mission.evidence_count or 0

    if completed == 0:
        return None, "nothing has completed yet"
    if failed:
        return (
            "Low",
            f"{failed} failed step(s) against {completed} completed",
        )
    if evidence:
        return "High", f"{evidence} verified step(s), no failures"
    return "Unverified", f"{completed} completed, but no verification evidence"


def _recommendations(executives: list[ExecutiveReadiness]) -> list[str]:
    """Deliverable 8. Roadmap items, filtered by what is genuinely absent
    — recommending something already built is noise a founder learns to
    scroll past."""
    ready = {e.label for e in executives if e.is_ready}
    label_of = {
        expected.executive_id: expected.label for expected in EXPECTED_EXECUTIVES
    }
    out = []
    for recommendation in RECOMMENDATIONS:
        gate = recommendation.requires_missing
        if gate is not None and label_of.get(gate) in ready:
            continue
        out.append(recommendation.text)
    return out


def _status(
    snapshot: DashboardSnapshot,
    executives: list[ExecutiveReadiness],
    decisions: list[DecisionView],
) -> tuple[str, str]:
    """Deliverable 3: one human answer, with a reason.

    Order matters. "Waiting on you" outranks "needs attention" because a
    founder who is being asked something should be told *that* first —
    the system is not broken, it is blocked on them, and those feel very
    different at 22:13.
    """
    if decisions:
        count = len(decisions)
        plural = "s" if count > 1 else ""
        return WAITING_ON_YOU, f"{count} decision{plural} waiting for you"

    if snapshot.capabilities.failed:
        return NEEDS_ATTENTION, f"{snapshot.capabilities.failed} failed step(s)"

    missing = [e.label for e in executives if e.status == MISSING]
    if missing:
        return NEEDS_ATTENTION, f"{', '.join(missing)} Executive missing"

    if snapshot.runtime.status.available and snapshot.runtime.state == "error":
        return NEEDS_ATTENTION, "the runtime reported an error"

    return WORKING, ""


# ---- daily summary (Deliverable 9) --------------------------------------


@dataclass(frozen=True)
class DailySummary:
    """Printed at shutdown. Same discipline as the rest: what is measured
    is reported, what is not is named."""

    completed: int = 0
    failed: int = 0
    recovered: int = 0
    approvals_decided: int = 0
    learning: str = ""
    tomorrow: str = ""
    uptime_seconds: float | None = None
    #: MB029 asks for "Time Saved". Nothing in Kalpavriksha measures what
    #: a task would have cost a human, so there is no honest number to
    #: report and this states that rather than inventing one.
    time_saved_note: str = (
        "not measured - Kalpavriksha records what it did, not what it "
        "would have cost you"
    )


def build_daily_summary(
    snapshot: DashboardSnapshot,
    approvals_decided: int = 0,
    recovered: int = 0,
) -> DailySummary:
    view = build_founder_view(snapshot)
    phases = ", ".join(
        f"{p.label} {round(p.fraction * 100)}%" for p in view.phases
    )
    return DailySummary(
        completed=view.work.completed,
        failed=view.work.failed,
        recovered=recovered,
        approvals_decided=approvals_decided,
        learning=phases,
        tomorrow=view.next_step,
        uptime_seconds=snapshot.runtime.uptime_seconds,
    )


def as_dict(view: FounderView) -> dict[str, Any]:
    """A JSON-shaped view, for the front-ends Deliverable 10 anticipates.
    Deliberately here rather than on the dataclass: a view model should
    not have to know that JSON exists, and a second serialisation (say,
    protobuf for a phone) is another function, not another method."""
    return {
        "status": view.status,
        "status_reason": view.status_reason,
        "needs_founder": view.needs_founder,
        "mission": {
            "name": view.mission.name,
            "current_step": view.mission.current_step,
            "steps_remaining": view.mission.steps_remaining,
            "progress": view.mission.progress,
            "estimated_seconds": view.mission.estimated_seconds,
            "confidence": view.mission.confidence,
            "confidence_basis": view.mission.confidence_basis,
        },
        "work": {
            "completed": view.work.completed,
            "running": view.work.running,
            "awaiting_approval": view.work.awaiting_approval,
            "failed": view.work.failed,
        },
        "executives": [
            {"label": e.label, "status": e.status, "detail": e.detail}
            for e in view.executives
        ],
        "decisions": [
            {
                "index": d.index,
                "title": d.title,
                "impact": d.impact,
                "risk_tier": d.risk_tier,
                "requested_at": d.requested_at,
                "executive": d.executive,
            }
            for d in view.decisions
        ],
        "phases": [
            {"label": p.label, "fraction": p.fraction, "basis": p.basis}
            for p in view.phases
        ],
        "recommendations": list(view.recommendations),
        "next_step": view.next_step,
    }
