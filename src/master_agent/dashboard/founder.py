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

#: The approval state that means "chosen, but not yet allowed to run".
#: A plain string rather than an import: the view model reads a frozen
#: snapshot and must not acquire a dependency on the component that
#: produced it (ADR-0016), which a test asserts.
WAITING_APPROVAL = "pending"


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
class MachineView:
    """MB030 Deliverables 4 and 9, as founder-facing data."""

    readiness: list[ExecutiveReadiness] = field(default_factory=list)
    installed_count: int = 0
    running: list[str] = field(default_factory=list)
    missing_recommended: list[str] = field(default_factory=list)
    ai_installed: list[str] = field(default_factory=list)
    available: bool = False


@dataclass(frozen=True)
class AiDecisionView:
    """MB032 Deliverable 9: which provider, why, what it costs, how good it
    is claimed to be. Four things, in that order, because that is the order
    a founder asks them in."""

    provider: str
    why: str
    cost: str
    quality: str
    capability: str
    approval: str
    at: str = ""
    #: False for a refusal. Carried rather than inferred from `provider`,
    #: because a renderer testing for the string "none" would be one
    #: unlucky provider id away from showing a refusal as a success --
    #: which is exactly what the first live run of this panel did.
    selected: bool = True
    #: True while the founder has not answered. A provider *was* chosen,
    #: so this is not a refusal -- but it has not run and must not be
    #: drawn with the same glyph as one that has.
    waiting: bool = False


@dataclass(frozen=True)
class ThinkingView:
    """MB033's founder view, exactly as the brief words it: what is
    thinking, what it cost, how long it took, and whether the answer came
    out of the cache. Four lines, no more."""

    provider: str
    cost: str
    latency: str
    cache: str
    succeeded: bool = True
    model: str = ""
    error: str = ""
    # ---- MB038 -----------------------------------------------------------
    # Empty means the call carried no budget, which is the truth about a
    # pre-MB038 or unbudgeted call rather than a zero.
    budget: str = ""
    bound_by: str = ""
    timeout_reason: str = ""
    lifecycle: str = ""
    #: MB035: whether the answer was checked, and against what verdict.
    verified: str = ""


@dataclass(frozen=True)
class EconomyView:
    """What the founder's quota has actually gone on (MB033).

    `basis` is carried because every number here can legitimately be zero,
    and a row of zeroes without a reason is indistinguishable from a
    broken counter.
    """

    local_executions: int = 0
    cloud_executions: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    avoided_cloud_executions: int = 0
    money_saved: float = 0.0
    total_spend: float = 0.0
    failed_executions: int = 0
    basis: str = ""

    @property
    def total_executions(self) -> int:
        return self.local_executions + self.cloud_executions


@dataclass(frozen=True)
class IntelligenceView:
    """The AI Capability Broker, as the founder page shows it.

    `available=False` with a reason is a normal state -- a build with no
    Broker wired says so, rather than showing an empty list that reads as
    "it has never chosen anything".
    """

    available: bool = False
    reason: str = ""
    policy: str | None = None
    providers_available: int | None = None
    providers_total: int | None = None
    scanned: bool = False
    total_decisions: int | None = None
    awaiting_approval: int | None = None
    decisions: list[AiDecisionView] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    #: None until something has actually run. A founder page that showed
    #: "Thinking with: none" before anything had been asked would be
    #: answering a question nobody asked.
    thinking: ThinkingView | None = None
    economy: EconomyView = field(default_factory=EconomyView)


@dataclass(frozen=True)
class MemoryView:
    """MB034's MEMORY section: what Kalpavriksha knows, five lines of it.

    `available=False` with a reason is a normal state — a build with no
    memory wired says so rather than showing a zero that reads as "you
    have told me nothing".
    """

    available: bool = False
    reason: str = ""
    total: int = 0
    critical: int = 0
    recent: list[str] = field(default_factory=list)
    top_tags: list[str] = field(default_factory=list)
    last_written: str = ""
    problems: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PlanStepView:
    """One step of the current mission, as the founder reads it."""

    step_id: str
    capability: str
    state: str
    detail: str = ""
    priority: str = "normal"


@dataclass(frozen=True)
class PlanView:
    """MB037's CURRENT MISSION section.

    Everything here is transcribed from the plan record. There is
    deliberately no field for the prompt, the reply, or a provider's
    reasoning: the brief forbids showing internal LLM reasoning, and a
    view model with nowhere to put it cannot leak it by accident later.
    """

    available: bool = False
    reason: str = ""
    objective: str = ""
    state: str = ""
    current_step: str = ""
    current_capability: str = ""
    current_expectation: str = ""
    steps: list[PlanStepView] = field(default_factory=list)
    completed: int = 0
    remaining: int = 0
    blocked: int = 0
    failed: int = 0
    unverified: int = 0
    progress: float = 0.0
    planned_by: str | None = None
    history_count: int = 0


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
    machine: MachineView = field(default_factory=MachineView)
    intelligence: IntelligenceView = field(default_factory=IntelligenceView)
    memory: MemoryView = field(default_factory=MemoryView)
    plan: PlanView = field(default_factory=PlanView)

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
        machine=_machine(snapshot),
        intelligence=_intelligence(snapshot),
        memory=_memory(snapshot),
        plan=_plan(snapshot),
    )


#: How a step's state reads on the founder page. `waiting` is its own
#: word because being blocked behind a dependency is not the same as not
#: having started -- the distinction MB029 insisted on for the mission
#: status, applied one level down.
_STEP_WORDS = {
    "pending": "not started",
    "running": "running now",
    "completed": "done",
    "failed": "failed",
}


def _plan(snapshot: DashboardSnapshot) -> PlanView:
    """MB037 section. Transcribed from the plan record -- the classifying
    happened where the record lives."""
    plan = snapshot.plan
    if not plan.status.available:
        return PlanView(available=False, reason=plan.status.reason or "no plan")

    steps = []
    for row in plan.steps:
        if row.unreachable:
            # Not "waiting": what it waits for has already failed, and
            # telling a founder to wait for it would be false.
            word = "will not run - " + ", ".join(row.blocked_by) + " failed"
        elif row.blocked_by:
            word = "waiting on " + ", ".join(row.blocked_by)
        else:
            word = _STEP_WORDS.get(row.state, row.state)
        detail = row.errors[0] if row.errors else ""
        if row.state == "completed" and row.verdict and row.verdict != "matched":
            # A step that finished but did not verify is not a success,
            # and the founder page says so rather than showing a tick.
            detail = f"verification: {row.verdict.replace('_', ' ')}"
        steps.append(
            PlanStepView(
                step_id=row.step_id,
                capability=row.capability,
                state=word,
                detail=detail,
                priority=row.priority,
            )
        )

    current = plan.current
    return PlanView(
        available=True,
        objective=plan.objective,
        state=plan.state,
        current_step=current.step_id if current else "",
        current_capability=current.capability if current else "",
        current_expectation=current.expectation if current else "",
        steps=steps,
        completed=plan.completed,
        remaining=plan.remaining,
        blocked=plan.blocked,
        failed=plan.failed,
        unverified=plan.unverified,
        progress=plan.progress,
        planned_by=plan.planned_by,
        history_count=plan.history_count,
    )


def _memory(snapshot: DashboardSnapshot) -> MemoryView:
    """MB034 Dashboard section. Transcribed from the panel data — the
    counting happened where the records live."""
    memory = snapshot.memory
    if not memory.status.available:
        return MemoryView(
            available=False, reason=memory.status.reason or "not attached"
        )
    last = memory.last_written
    return MemoryView(
        available=True,
        total=memory.total or 0,
        critical=memory.critical or 0,
        recent=[row.title for row in memory.recent],
        top_tags=[f"{tag} ({count})" for tag, count in memory.top_tags],
        last_written=f"{last.title}  ({last.written_at})" if last else "",
        problems=list(memory.problems),
    )


def _intelligence(snapshot: DashboardSnapshot) -> IntelligenceView:
    """MB032 Deliverable 9. Every value is transcribed from the panel data
    -- the tiers were resolved where the numbers live (`ai_infrastructure`),
    and this layer restates them rather than re-deriving them."""
    broker = snapshot.broker
    if not broker.status.available:
        return IntelligenceView(
            available=False, reason=broker.status.reason or "not attached"
        )

    return IntelligenceView(
        available=True,
        policy=broker.policy_version,
        providers_available=broker.providers_available,
        providers_total=broker.providers_total,
        scanned=broker.scanned,
        total_decisions=broker.total_decisions,
        awaiting_approval=broker.awaiting_approval,
        decisions=[
            AiDecisionView(
                provider=row.provider_id or "no provider available",
                why=row.reason,
                cost=row.cost_detail,
                quality=row.quality_detail,
                capability=row.capability,
                approval=row.approval_state.replace("_", " "),
                at=row.decided_at,
                selected=row.provider_id is not None,
                waiting=row.approval_state == WAITING_APPROVAL,
            )
            for row in broker.decisions
        ],
        problems=list(broker.recording_failures),
        thinking=_thinking(broker.last_execution),
        economy=EconomyView(
            local_executions=broker.economy.local_executions,
            cloud_executions=broker.economy.cloud_executions,
            cache_hits=broker.economy.cache_hits,
            cache_misses=broker.economy.cache_misses,
            avoided_cloud_executions=broker.economy.avoided_cloud_executions,
            money_saved=broker.economy.money_saved,
            total_spend=broker.economy.total_spend,
            failed_executions=broker.economy.failed_executions,
            basis=broker.economy.basis,
        ),
    )


def _thinking(row: Any) -> ThinkingView | None:
    """MB033's four lines. `cache` is upper-cased because HIT and MISS are
    the two words the brief puts on the founder's screen, and they are
    read at a glance rather than parsed."""
    if row is None:
        return None
    return ThinkingView(
        provider=row.provider_id,
        cost=row.cost,
        latency=row.latency,
        cache=row.cache.replace("_", " ").upper(),
        succeeded=row.succeeded,
        model=row.model,
        error=row.error,
        verified=row.verified,
        budget=row.budget,
        bound_by=row.bound_by.replace("_", " "),
        timeout_reason=row.timeout_reason.replace("_", " "),
        lifecycle=row.lifecycle,
    )


def _machine(snapshot: DashboardSnapshot) -> MachineView:
    """Deliverable 9's Machine Readiness. `Ready` / `Missing` /
    `Unavailable` come straight from what the Desktop Executive observed
    -- the Dashboard classifies nothing and decides nothing."""
    machine = snapshot.machine
    if not machine.status.available:
        return MachineView(available=False)

    readiness = [
        ExecutiveReadiness(
            label=row.label,
            status=READY if row.status == "installed" else row.status.title(),
            detail=row.version or row.detail,
        )
        for row in machine.readiness
    ]
    return MachineView(
        readiness=readiness,
        installed_count=len(machine.installed),
        running=list(machine.running),
        missing_recommended=list(machine.missing_recommended),
        ai_installed=list(machine.ai_installed),
        available=True,
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
        "plan": {
            "available": view.plan.available,
            "reason": view.plan.reason,
            "objective": view.plan.objective,
            "state": view.plan.state,
            "current_step": view.plan.current_step,
            "current_capability": view.plan.current_capability,
            "current_expectation": view.plan.current_expectation,
            "completed": view.plan.completed,
            "remaining": view.plan.remaining,
            "blocked": view.plan.blocked,
            "failed": view.plan.failed,
            "unverified": view.plan.unverified,
            "progress": view.plan.progress,
            "planned_by": view.plan.planned_by,
            "history_count": view.plan.history_count,
            "steps": [
                {
                    "step_id": s.step_id,
                    "capability": s.capability,
                    "state": s.state,
                    "detail": s.detail,
                    "priority": s.priority,
                }
                for s in view.plan.steps
            ],
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
        "intelligence": {
            "available": view.intelligence.available,
            "reason": view.intelligence.reason,
            "policy": view.intelligence.policy,
            "providers_available": view.intelligence.providers_available,
            "providers_total": view.intelligence.providers_total,
            "total_decisions": view.intelligence.total_decisions,
            "awaiting_approval": view.intelligence.awaiting_approval,
            "decisions": [
                {
                    "provider": d.provider,
                    "why": d.why,
                    "cost": d.cost,
                    "quality": d.quality,
                    "capability": d.capability,
                    "approval": d.approval,
                    "at": d.at,
                }
                for d in view.intelligence.decisions
            ],
            "thinking": (
                {
                    "provider": view.intelligence.thinking.provider,
                    "cost": view.intelligence.thinking.cost,
                    "latency": view.intelligence.thinking.latency,
                    "cache": view.intelligence.thinking.cache,
                    "verified": view.intelligence.thinking.verified,
                    "succeeded": view.intelligence.thinking.succeeded,
                    "model": view.intelligence.thinking.model,
                }
                if view.intelligence.thinking is not None
                else None
            ),
            "economy": {
                "local_executions": view.intelligence.economy.local_executions,
                "cloud_executions": view.intelligence.economy.cloud_executions,
                "cache_hits": view.intelligence.economy.cache_hits,
                "cache_misses": view.intelligence.economy.cache_misses,
                "avoided_cloud_executions": (
                    view.intelligence.economy.avoided_cloud_executions
                ),
                "money_saved": view.intelligence.economy.money_saved,
                "total_spend": view.intelligence.economy.total_spend,
                "failed_executions": view.intelligence.economy.failed_executions,
                "basis": view.intelligence.economy.basis,
            },
        },
        "memory": {
            "available": view.memory.available,
            "reason": view.memory.reason,
            "total": view.memory.total,
            "critical": view.memory.critical,
            "recent": list(view.memory.recent),
            "top_tags": list(view.memory.top_tags),
            "last_written": view.memory.last_written,
        },
    }
