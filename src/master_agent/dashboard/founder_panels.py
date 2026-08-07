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

import textwrap

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
        "Missing": charset.missing,
        "Unavailable": charset.warning,
    }.get(status, charset.unavailable)


#: Indent and label width for the detail lines under an AI decision.
FIELD_INDENT = "      "
FIELD_LABEL = 10
FIELD_WIDTH = WIDTH - len(FIELD_INDENT) - FIELD_LABEL


def _field(label: str, text: str, width: int = FIELD_WIDTH) -> list[str]:
    """A labelled field, wrapped rather than truncated.

    Truncation was the first version, and a live run cut the Broker's
    reason off at *"quality 0.72 clears the qual"* -- losing the number the
    whole panel exists to show. A reason a founder cannot finish reading is
    not an explanation.
    """
    body = textwrap.wrap(text, width=width) if text else []
    if not body:
        return [f"{FIELD_INDENT}{label:<{FIELD_LABEL}}--"]
    head = f"{FIELD_INDENT}{label:<{FIELD_LABEL}}{body[0]}"
    return [head] + [f"{FIELD_INDENT}{'':<{FIELD_LABEL}}{part}" for part in body[1:]]


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


def render_machine(view: FounderView, charset: Charset | None = None) -> list[str]:
    """MB030 Deliverables 4 and 9: Machine Readiness, plus what is
    installed and running. Absent when no Desktop Executive is attached —
    an empty list would read as "you have nothing installed"."""
    cs = _cs(charset)
    machine = view.machine
    if not machine.available:
        return ["MACHINE READINESS", f"  {cs.unavailable} no machine scan yet"]

    lines = [f"MACHINE READINESS  ({machine.installed_count} installed)"]
    for row in machine.readiness:
        glyph = _readiness_glyph(row.status, cs)
        version = f"  {row.detail}" if row.detail else ""
        lines.append(f"  {glyph} {row.label:<12} {row.status}{version}"[:70])
    if machine.running:
        lines.append(f"  Running        {', '.join(machine.running)}"[:70])
    if machine.ai_installed:
        lines.append(f"  AI software    {', '.join(machine.ai_installed)}"[:70])
    if machine.missing_recommended:
        lines.append(
            f"  Not installed  {', '.join(machine.missing_recommended)}"[:70]
        )
    return lines


def _thinking_lines(ai, cs: Charset) -> list[str]:
    """MB033's founder view, in the four lines the brief specifies.

    Printed *above* the decision list, because "what is thinking, and what
    is it costing me" is the question a founder has while it is happening;
    the decision history is what they read afterwards.
    """
    thinking = ai.thinking
    if thinking is None:
        return []

    glyph = cs.ok if thinking.succeeded else cs.warning
    model = f" ({thinking.model})" if thinking.model else ""
    lines = [
        f"  {glyph} Thinking with  {thinking.provider}{model}"[:70],
        f"      Cost           {thinking.cost}",
        f"      Latency        {thinking.latency}",
        f"      Prompt Cache   {thinking.cache}",
        f"      Verified       {thinking.verified or 'not checked'}",
    ]
    # MB038. Shown only when there is one -- a call with no budget says
    # nothing here rather than showing a zero.
    if thinking.budget:
        lines.append(f"      Budget         {thinking.budget}"[:74])
        if thinking.bound_by:
            lines.append(f"      Bound by       {thinking.bound_by}"[:74])
    if thinking.timeout_reason:
        # Which of the three deadlines ended it. "It timed out" was three
        # different failures with three different fixes until MB038.
        lines.append(f"  {cs.warning} Deadline       {thinking.timeout_reason}"[:74])
    if thinking.lifecycle == "abandoned":
        # The founder stopped waiting; the provider may not have stopped
        # working. Worth saying, because the machine can still be busy.
        lines.append(f"  {cs.warning} Abandoned      the provider may still be running")
    if not thinking.succeeded and thinking.error:
        lines.extend(_field("Failed", thinking.error))
    return lines


def _economy_lines(ai, cs: Charset) -> list[str]:
    """The token economy, as counts. Every one of these can legitimately
    be zero, so the basis is printed with them -- a row of zeroes with no
    reason is indistinguishable from a broken counter."""
    economy = ai.economy
    if economy.total_executions == 0 and economy.failed_executions == 0:
        return []

    saved = f"{economy.money_saved:.4f}" if economy.money_saved else "nothing yet"
    spent = (
        f"  (spent {economy.total_spend:.4f})" if economy.total_spend else "  (free)"
    )
    cache = f"{economy.cache_hits} hit / {economy.cache_misses} miss"
    avoided = (
        f"{economy.avoided_cloud_executions} cloud call(s), saving {saved}"
    )
    # The header is not decoration. Without it these sit at the same
    # indent as the last decision's fields and read as belonging to it --
    # found by reading a live frame, which is also how MB032's two panel
    # defects turned up.
    lines = [
        "  TOKEN ECONOMY",
        f"      Ran locally    {economy.local_executions}",
        f"      Ran in cloud   {economy.cloud_executions}{spent}",
        f"      Cache          {cache}",
        f"      Avoided        {avoided}",
    ]
    if economy.failed_executions:
        lines.append(f"  {cs.warning} {economy.failed_executions} execution(s) failed")
    lines.extend(_field("Basis", economy.basis))
    return lines


def render_intelligence(view: FounderView, charset: Charset | None = None) -> list[str]:
    """MB032 Deliverable 9: which provider, why, what it cost, how good it
    is claimed to be.

    Always visible, like the Decisions panel and for the same reason: a
    panel that disappears when there is nothing to show trains a founder to
    stop looking for it -- and "nothing has been chosen yet" is exactly the
    state they would want to notice.
    """
    cs = _cs(charset)
    ai = view.intelligence
    if not ai.available:
        return ["AI DECISIONS", f"  {cs.unavailable} {ai.reason or 'no broker attached'}"]

    ready = (
        f"{ai.providers_available}/{ai.providers_total} provider(s) available"
        if ai.providers_total is not None
        else "provider estate unknown"
    )
    lines = [f"AI DECISIONS  (policy {ai.policy or 'unknown'}, {ready})"]
    lines.extend(_thinking_lines(ai, cs))
    if not ai.scanned:
        lines.append(f"  {cs.unavailable} no machine scan yet, so local providers read as absent")
    if ai.awaiting_approval:
        lines.append(f"  {cs.pending} {ai.awaiting_approval} waiting on your approval")

    if not ai.decisions:
        lines.append(f"  {cs.unavailable} nothing has asked for AI yet")
        return lines

    for decision in ai.decisions:
        if not decision.selected:
            # A refusal is not a success with blanks in it. The first live
            # run of this panel rendered one with a tick beside it and
            # "Approval  not required" underneath, which reads as "we chose
            # nothing and that was fine".
            lines.append(f"  {cs.warning} no provider for {decision.capability}"[:70])
            lines.extend(_field("Why", decision.why))
            continue
        # A chosen-but-unapproved provider has not run. Drawing it with the
        # same tick as one that has is the same class of dishonesty as
        # drawing a refusal that way -- found the same way, by reading a
        # live frame.
        glyph = cs.pending if decision.waiting else cs.ok
        lines.append(f"  {glyph} {decision.provider}  ({decision.capability})"[:70])
        lines.extend(_field("Why", decision.why))
        lines.extend(_field("Cost", decision.cost))
        lines.extend(_field("Quality", decision.quality))
        lines.extend(_field("Approval", decision.approval))
    lines.extend(_economy_lines(ai, cs))
    for problem in ai.problems:
        lines.append(f"  {cs.warning} recording problem: {problem}"[:70])
    return lines


def render_memory(view: FounderView, charset: Charset | None = None) -> list[str]:
    """MB034's MEMORY section: five lines, no scrolling.

    Always visible, for the reason the Decisions and AI panels are: a
    section that vanishes when empty teaches a founder to stop looking for
    it — and "you have not told me anything yet" is precisely the state
    they would want to notice.
    """
    cs = _cs(charset)
    memory = view.memory
    if not memory.available:
        return ["MEMORY", f"  {cs.unavailable} {memory.reason or 'not attached'}"]

    lines = [
        "MEMORY",
        f"  Total knowledge  {memory.total}",
        f"  Critical facts   {memory.critical}",
    ]
    if memory.recent:
        lines.append("  Recent learnings")
        for title in memory.recent:
            lines.append(f"      {cs.sub_rule} {title}"[:74])
    else:
        lines.append(f"  Recent learnings {cs.unavailable} nothing remembered yet")
    lines.append(f"  Top tags         {', '.join(memory.top_tags) or '--'}"[:74])
    lines.append(f"  Last written     {memory.last_written or '--'}"[:74])
    for problem in memory.problems:
        lines.append(f"  {cs.warning} {problem}"[:74])
    return lines


#: How many step rows the founder page shows before summarising the rest.
#: Five, because the page is allowed sixty lines and this panel also
#: carries the objective, the progress bar, the current step, what it
#: expects, and who planned it. Measured against a thirty-step plan.
MAX_PLAN_ROWS = 5


def render_plan(view: FounderView, charset: Charset | None = None) -> list[str]:
    """MB037's CURRENT MISSION section.

    Always visible, like every other founder panel, and for the same
    reason: "nothing planned yet" is a state worth noticing.

    It shows what was planned and what became of it. It never shows the
    prompt, the reply, or a provider's reasoning -- the brief forbids
    that, and `PlanView` has no field to hold it.
    """
    cs = _cs(charset)
    plan = view.plan
    if not plan.available:
        return ["CURRENT MISSION", f"  {cs.unavailable} {plan.reason or 'nothing planned'}"]

    lines = [
        "CURRENT MISSION",
        f"  Objective        {plan.objective}"[:74],
        (
            f"  Progress         {_bar(plan.progress, cs)} "
            f"{plan.completed}/{plan.completed + plan.remaining} steps"
        ),
    ]
    if plan.current_step:
        lines.append(f"  Now              {plan.current_step} - {plan.current_capability}"[:74])
        if plan.current_expectation:
            lines.append(f"  Expecting        {plan.current_expectation}"[:74])
    else:
        lines.append(f"  Now              {cs.unavailable} nothing running")

    # Capped: this page is allowed sixty lines, and a twenty-step plan
    # would eat all of them. What is dropped is *said*, never silently
    # truncated -- a list that quietly stops reads as a shorter plan.
    for step in plan.steps[:MAX_PLAN_ROWS]:
        glyph = cs.ok if step.state == "done" else cs.sub_rule
        if step.state == "failed":
            glyph = cs.warning
        row = f"      {glyph} {step.step_id} - {step.state}"
        if step.detail:
            row += f" ({step.detail})"
        lines.append(row[:74])
    hidden = len(plan.steps) - MAX_PLAN_ROWS
    if hidden > 0:
        lines.append(f"      {cs.sub_rule} and {hidden} more step(s)")

    if plan.failed:
        lines.append(f"  {cs.warning} {plan.failed} step(s) failed")
    if plan.unverified:
        # MB035's distinction, surfaced: a step that ran and was not
        # verified is not a step that succeeded.
        lines.append(f"  {cs.warning} {plan.unverified} completed step(s) not verified")
    if plan.planned_by:
        lines.append(f"  Planned by       {plan.planned_by}"[:74])
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
    is it doing* (mission, work), *what does it have* (executives, machine,
    intelligence), *how far along* (self development), *what next*
    (recommendations).

    AI decisions sit with the machine rather than near the top: which
    provider was chosen is a question about what the system *has*, and a
    founder only asks it once they already know whether anything is wrong.

    Decisions sit second, above the mission, because a system blocked on
    the founder is not doing anything else — and a founder scrolling past
    their own blocked decision to read a progress bar is the exact failure
    this brief exists to fix.
    """
    cs = _cs(charset)
    sections = [
        render_status(view, cs),
        render_decisions(view, cs),
        # MB037: one slot, best available answer. The plan panel and the
        # MB029 mission panel answer the same founder question -- "what is
        # it doing" -- and showing both would say it twice and push the
        # frame past the sixty lines this page is allowed. When the
        # Planner produced a plan the step-level answer is strictly
        # better; when it did not (the launcher's own machine scan, say)
        # the summary is all there is, and it still shows.
        render_plan(view, cs) if view.plan.available else render_mission(view, cs),
        render_work(view, cs),
        render_readiness(view, cs),
        render_machine(view, cs),
        render_intelligence(view, cs),
        render_memory(view, cs),
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
