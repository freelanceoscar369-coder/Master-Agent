"""Rendering the Founder view as text (Mission Brief 029).

Pure functions of a `FounderView`, exactly as `panels.py` is a pure
function of a `DashboardSnapshot`. Swapping this module for HTML, a
desktop widget set, or a phone layout is the whole of Deliverable 10 —
nothing above it changes.

Every glyph comes from the `Charset`, chosen by asking the output stream
what it can encode. MB029's mock uses check marks and block bars; a
cp1252 Windows console cannot encode either, and MB026 already learned
what happens then.
"""
from __future__ import annotations

from master_agent.dashboard.charset import Charset, detect
from master_agent.dashboard.founder import (
    NEEDS_ATTENTION,
    WAITING_ON_YOU,
    WORKING,
    FounderView,
)
from master_agent.dashboard.roadmap import MISSING, PLANNED, READY

WIDTH = 62
BAR_WIDTH = 12


def _cs(charset: Charset | None) -> Charset:
    return charset if charset is not None else detect()


def _bar(fraction: float | None, charset: Charset, width: int = BAR_WIDTH) -> str:
    if fraction is None:
        return charset.unavailable * width
    filled = max(0, min(width, round(fraction * width)))
    return charset.bar_full * filled + charset.bar_empty * (width - filled)


def _status_glyph(status: str, charset: Charset) -> str:
    return {
        WORKING: charset.healthy,
        WAITING_ON_YOU: charset.pending,
        NEEDS_ATTENTION: charset.warning,
    }.get(status, charset.unavailable)


def _readiness_glyph(status: str, charset: Charset) -> str:
    return {
        READY: charset.ok,
        MISSING: charset.missing,
        PLANNED: charset.unavailable,
    }.get(status, charset.unavailable)


def _duration(seconds: float | None) -> str:
    if seconds is None:
        return "unknown"
    if seconds < 90:
        return f"{round(seconds)}s"
    if seconds < 5400:
        return f"{round(seconds / 60)}m"
    return f"{seconds / 3600:.1f}h"


def render_banner(charset: Charset | None = None) -> list[str]:
    line = "=" * WIDTH
    return [line, "KALPAVRIKSHA".center(WIDTH), line]


def render_status(view: FounderView, charset: Charset | None = None) -> list[str]:
    """Deliverable 3: one human answer, and the reason for it."""
    cs = _cs(charset)
    lines = ["STATUS", f"  {_status_glyph(view.status, cs)} {view.status}"]
    if view.status_reason:
        lines.append(f"    {view.status_reason}")
    return lines


def render_mission(view: FounderView, charset: Charset | None = None) -> list[str]:
    """Deliverable 4. Absent fields say so rather than showing zero."""
    cs = _cs(charset)
    mission = view.mission
    if mission.name is None:
        return ["CURRENT MISSION", "  nothing in flight"]

    percent = (
        f"{round(mission.progress * 100)}%" if mission.progress is not None else "--"
    )
    lines = [
        "CURRENT MISSION",
        f"  {mission.name}",
        f"  {_bar(mission.progress, cs)}  {percent}",
        f"  Current step     {mission.current_step or 'none'}",
        f"  Steps remaining  {mission.steps_remaining if mission.steps_remaining is not None else 'unknown'}",
        f"  Estimated time   {_duration(mission.estimated_seconds)}",
    ]
    confidence = mission.confidence or "not measured"
    lines.append(f"  Confidence       {confidence}")
    if mission.confidence_basis:
        lines.append(f"                   ({mission.confidence_basis})")
    return lines


def render_work(view: FounderView, charset: Charset | None = None) -> list[str]:
    """Deliverable 1's "Today's Work"."""
    cs = _cs(charset)
    work = view.work
    lines = [
        "TODAY'S WORK",
        f"  {cs.ok} {work.completed} completed",
        f"  {cs.running} {work.running} running",
    ]
    if work.awaiting_approval:
        lines.append(f"  {cs.pending} {work.awaiting_approval} waiting approval")
    if work.failed:
        lines.append(f"  {cs.warning} {work.failed} failed")
    return lines


def render_decisions(view: FounderView, charset: Charset | None = None) -> list[str]:
    """Deliverable 7 — always visible, including when there is nothing to
    decide. A panel that disappears when empty trains a founder to stop
    looking for it."""
    cs = _cs(charset)
    if not view.decisions:
        return ["FOUNDER DECISIONS", f"  {cs.ok} none pending"]

    lines = [f"FOUNDER DECISIONS ({len(view.decisions)})"]
    for decision in view.decisions:
        lines.append(f"  [{decision.index}] {decision.title}")
        lines.append(f"      Impact  {decision.impact}")
        lines.append(f"      Risk    {decision.risk_tier.upper()}")
        lines.append(f"      Asked   {decision.requested_at}  by {decision.executive}")
    lines.append("  [Y]es N   [N]o N   [D]efer N   approve all")
    return lines


def render_readiness(view: FounderView, charset: Charset | None = None) -> list[str]:
    """Deliverable 5: which Executives exist, not how many capabilities."""
    cs = _cs(charset)
    lines = ["EXECUTIVES"]
    for executive in view.executives:
        glyph = _readiness_glyph(executive.status, cs)
        lines.append(f"  {glyph} {executive.label:<12} {executive.status}")
    return lines


def render_self_development(
    view: FounderView, charset: Charset | None = None
) -> list[str]:
    """Deliverable 6. Read from the roadmap, not computed — see
    `roadmap.py` for why, and for what each number is a reading of."""
    cs = _cs(charset)
    lines = ["SELF DEVELOPMENT"]
    for phase in view.phases:
        lines.append(
            f"  {phase.label:<15} {_bar(phase.fraction, cs, 10)} "
            f"{round(phase.fraction * 100)}%"
        )
    return lines


def render_recommendations(
    view: FounderView,
    charset: Charset | None = None,
) -> list[str]:
    """Deliverable 8. `charset` is unused but kept for signature parity
    with every sibling renderer -- a caller composing panels should not
    have to remember which ones need glyphs."""
    del charset
    lines = ["RECOMMENDATIONS"]
    if not view.recommendations:
        return lines + ["  nothing needed"]
    for position, text in enumerate(view.recommendations, start=1):
        lines.append(f"  {position}. {text}")
    return lines


def render_next_step(
    view: FounderView,
    charset: Charset | None = None,
) -> list[str]:
    del charset  # signature parity -- see render_recommendations
    return ["NEXT RECOMMENDED STEP", f"  {view.next_step}"]


def render_founder_frame(
    view: FounderView,
    charset: Charset | None = None,
    footer: str = "",
) -> str:
    """The whole founder page.

    Order is the answer to the three questions, in the order a founder
    asks them: *is it OK* (status), *does it need me* (decisions), *what
    is it doing* (mission, work), *what does it have* (executives), *how
    far along* (self development), *what next* (recommendations).

    Decisions sit second, above the mission, because a system blocked on
    the founder is not doing anything else — and a founder scrolling past
    their own blocked decision to read a progress bar is the exact failure
    this brief exists to fix.
    """
    cs = _cs(charset)
    sections = [
        render_status(view, cs),
        render_decisions(view, cs),
        render_mission(view, cs),
        render_work(view, cs),
        render_readiness(view, cs),
        render_self_development(view, cs),
        render_recommendations(view, cs),
        render_next_step(view, cs),
    ]

    lines = list(render_banner(cs))
    for section in sections:
        lines.append("")
        lines.extend(section)
    lines.append("")
    lines.append("=" * WIDTH)
    if footer:
        lines.append(footer)
    return "\n".join(lines)


def render_daily_summary(summary, charset: Charset | None = None) -> str:
    """Deliverable 9, printed at shutdown."""
    del charset  # plain ASCII: this prints after the frame is gone
    lines = [
        "",
        "=" * WIDTH,
        "TODAY'S SUMMARY".center(WIDTH),
        "=" * WIDTH,
        "",
        f"  Tasks completed    {summary.completed}",
        f"  Failures           {summary.failed}",
        f"  Recovered          {summary.recovered}",
        f"  Decisions made     {summary.approvals_decided}",
        f"  Ran for            {_duration(summary.uptime_seconds)}",
        "",
        f"  Learning           {summary.learning}",
        f"  Time saved         {summary.time_saved_note}",
        "",
        "  TOMORROW",
        f"  {summary.tomorrow}",
        "",
        "=" * WIDTH,
    ]
    return "\n".join(lines)
