"""Panel renderers — pure functions from read model to text.

Every function here takes plain data and returns lines. None of them
touches a live object, which is what makes them testable without a
Runtime and what makes it structurally impossible for a panel to mutate
anything (ADR-0016 Decision 1).

Missing data renders as an explicit marker plus the reason, never as a
plausible-looking zero (MB026 Rule 3).

Glyphs come from a `Charset` so the frame degrades to ASCII on a terminal
that cannot encode box-drawing characters -- see charset.py for why that
is asked of the stream rather than guessed from the platform.
"""
from __future__ import annotations

from datetime import UTC, datetime

from master_agent.dashboard.charset import ASCII, UNICODE, Charset, detect
from master_agent.dashboard.readmodel import (
    ApprovalPanelData,
    AuditPanelData,
    CapabilityPanelData,
    DashboardSnapshot,
    ExecutivePanelData,
    FounderStatePanelData,
    MissionPanelData,
    PanelStatus,
    PersistencePanelData,
    RuntimePanelData,
    SystemHealthPanelData,
)

WIDTH = 62
PROGRESS_BAR_WIDTH = 16
# How many capability names the panel spells out before summarising the
# rest as a count.
REGISTERED_PREVIEW = 8

# Resolved once from the real output stream; overridable per call so tests
# can pin a charset and a launcher can force one.
DEFAULT_CHARSET: Charset = detect()

__all__ = [
    "ASCII",
    "DEFAULT_CHARSET",
    "PROGRESS_BAR_WIDTH",
    "UNICODE",
    "WIDTH",
    "Charset",
    "format_duration",
    "format_timestamp",
    "progress_bar",
    "render_audit",
    "render_capabilities",
    "render_executives",
    "render_founder_state",
    "render_header",
    "render_mission",
    "render_persistence",
    "render_runtime",
    "render_system_health",
    "rule",
    "value",
]


def _cs(charset: Charset | None) -> Charset:
    return charset or DEFAULT_CHARSET


def rule(char: str | None = None, charset: Charset | None = None) -> str:
    return (char or _cs(charset).rule) * WIDTH


def value(raw: object, charset: Charset | None = None) -> str:
    """One place decides how an absent value looks, so no panel can
    accidentally render `None` as the string "None"."""
    if raw is None:
        return _cs(charset).unavailable
    if isinstance(raw, bool):
        return "yes" if raw else "no"
    return str(raw)


def format_duration(seconds: float | None, charset: Charset | None = None) -> str:
    if seconds is None:
        return _cs(charset).unavailable
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    return f"{seconds // 3600}h {(seconds % 3600) // 60}m"


def format_timestamp(when: datetime | None, charset: Charset | None = None) -> str:
    if when is None:
        return _cs(charset).unavailable
    return when.astimezone(UTC).strftime("%H:%M:%S")


def progress_bar(
    progress: float | None,
    width: int = PROGRESS_BAR_WIDTH,
    charset: Charset | None = None,
) -> str:
    """A bar for unknown progress is left empty rather than guessed -- an
    unreadable mission must not look like a mission sitting at 0%."""
    resolved = _cs(charset)
    if progress is None:
        return resolved.bar_empty * width
    clamped = max(0.0, min(1.0, progress))
    filled = round(clamped * width)
    return resolved.bar_full * filled + resolved.bar_empty * (width - filled)


def _unavailable(title: str, status: PanelStatus, charset: Charset | None) -> list[str]:
    return [title, f"  {_cs(charset).unavailable} {status.reason or 'unavailable'}"]


def _wrap_names(names: list[str], indent: int, limit: int) -> list[str]:
    """Pack names onto as few lines as fit the frame width. Bounded, so a
    system with hundreds of capabilities cannot crowd out every other
    panel."""
    lines: list[str] = []
    current = " " * indent
    for name in list(names)[:limit]:
        candidate = f"{current}{name}  "
        if len(candidate.rstrip()) > WIDTH:
            lines.append(current.rstrip())
            current = " " * indent + name + "  "
        else:
            current = candidate
    if current.strip():
        lines.append(current.rstrip())
    return lines


# ---- panels -------------------------------------------------------------


def render_runtime(data: RuntimePanelData, charset: Charset | None = None) -> list[str]:
    if not data.status.available:
        return _unavailable("RUNTIME", data.status, charset)
    return [
        "RUNTIME",
        f"  State             {value(data.state, charset).upper()}",
        f"  Uptime            {format_duration(data.uptime_seconds, charset)}",
        f"  Active Cycle      {value(data.active_cycle, charset)}",
        f"  Queue Length      {value(data.queue_length, charset)}",
        f"  Last Dispatch     {format_timestamp(data.last_dispatch_at, charset)}",
        f"  Last Verification {format_timestamp(data.last_verification_at, charset)}",
    ]


def render_mission(data: MissionPanelData, charset: Charset | None = None) -> list[str]:
    resolved = _cs(charset)
    if not data.status.available:
        return _unavailable("MISSION", data.status, charset)
    if data.objective is None:
        return ["MISSION", f"  {resolved.unavailable} no objective in flight"]

    percent = (
        f"{data.progress * 100:.0f}%" if data.progress is not None else resolved.unavailable
    )
    lines = [
        "MISSION",
        f"  {data.objective}",
        f"  Progress          {progress_bar(data.progress, charset=charset)}  {percent}",
        f"  Status            {value(data.mission_status, charset)}",
        f"  Active Executive  {value(data.active_executive, charset)}",
        f"  Capability        {value(data.active_capability, charset)}",
        f"  ETA               {format_duration(data.eta_seconds, charset)}",
    ]
    if data.errors:
        lines.append(f"  Errors            {len(data.errors)}")
        for error in data.errors[:3]:
            lines.append(f"    {resolved.warning} {error[: WIDTH - 8]}")
    return lines


def render_executives(
    data: ExecutivePanelData, charset: Charset | None = None
) -> list[str]:
    if not data.status.available:
        return _unavailable("EXECUTIVES", data.status, charset)
    if not data.executives:
        return ["EXECUTIVES", f"  {_cs(charset).unavailable} none registered"]

    lines = ["EXECUTIVES", "  NAME             HEALTH     STATUS      VER       CAPS"]
    for row in data.executives:
        lines.append(
            f"  {row.executive_id[:16]:<16} {row.health[:10]:<10} "
            f"{row.state[:11]:<11} {row.version[:9]:<9} {row.capability_count}"
        )
    return lines


def render_capabilities(
    data: CapabilityPanelData, charset: Charset | None = None
) -> list[str]:
    if not data.status.available:
        return _unavailable("CAPABILITIES", data.status, charset)
    lines = [
        "CAPABILITIES",
        f"  Registered        {len(data.registered)}",
    ]
    # Deliverable 5 asks to display the registered capabilities, not just
    # count them -- so name them, wrapped and bounded so a system with two
    # hundred capabilities cannot push every other panel off the screen.
    lines.extend(_wrap_names(data.registered, indent=4, limit=REGISTERED_PREVIEW))
    if len(data.registered) > REGISTERED_PREVIEW:
        remaining = len(data.registered) - REGISTERED_PREVIEW
        lines.append(f"    ... and {remaining} more")
    lines += [
        f"  Pending           {value(data.pending, charset)}",
        f"  Active            {value(data.active, charset)}",
        f"  Completed         {value(data.completed, charset)}",
    ]
    if data.blocked:
        lines.append(f"  Blocked           {data.blocked}")
    if data.failed:
        lines.append(f"  Failed            {data.failed}")
    return lines


def render_audit(
    data: AuditPanelData, limit: int | None = None, charset: Charset | None = None
) -> list[str]:
    resolved = _cs(charset)
    if not data.status.available:
        return _unavailable("AUDIT", data.status, charset)
    if not data.recent:
        return ["AUDIT", f"  {resolved.unavailable} no events recorded yet"]

    rows = data.recent[-limit:] if limit else data.recent
    header = (
        f"AUDIT  ({value(data.total_entries, charset)} events, "
        f"{value(data.failures, charset)} failures)"
    )
    lines = [header]
    for row in rows:
        marker = resolved.warning if row.error else " "
        detail = row.capability or row.task_id or row.source
        lines.append(
            f" {marker}{row.sequence:>5}  {format_timestamp(row.occurred_at, charset)}  "
            f"{row.event_type[:26]:<26} {str(detail)[:14]}"
        )
    return lines


def render_persistence(
    data: PersistencePanelData, charset: Charset | None = None
) -> list[str]:
    if not data.status.available:
        return _unavailable("PERSISTENCE", data.status, charset)
    recovery = value(data.recovery_status, charset)
    if data.recovery_source:
        recovery += f" ({data.recovery_source})"
    return [
        "PERSISTENCE",
        f"  Last Checkpoint   {format_timestamp(data.last_checkpoint_at, charset)}",
        f"  Snapshot Version  {value(data.snapshot_schema_version, charset)}",
        f"  Event Log Size    {value(data.event_log_size, charset)}",
        f"  Recovery          {recovery}",
    ]


def render_system_health(
    data: SystemHealthPanelData, charset: Charset | None = None
) -> list[str]:
    if not data.status.available:
        return _unavailable("SYSTEM HEALTH", data.status, charset)
    return [
        "SYSTEM HEALTH",
        f"  Executives Online {value(data.executives_online, charset)}",
        f"  Runtime           {value(data.runtime_health, charset)}",
        f"  Queue             {value(data.queue_health, charset)}",
        f"  Audit             {value(data.audit_health, charset)}",
        f"  Persistence       {value(data.persistence_health, charset)}",
    ]


def render_approvals(
    data: ApprovalPanelData, charset: Charset | None = None
) -> list[str]:
    """The Approval panel (MB028.1 Deliverable 2).

    Pure, like every other panel: it takes plain data and returns strings.
    The `[A]/[R]/[D]` hints tell the founder what to type -- the panel
    itself has no way to act on them, which is what keeps the Dashboard
    read-only (ADR-0016) while the workflow becomes interactive."""
    if not data.status.available:
        return _unavailable("PENDING APPROVALS", data.status, charset)

    if not data.approvals:
        return ["PENDING APPROVALS (0)", "  nothing is waiting on you"]

    lines = [f"PENDING APPROVALS ({data.count})"]
    for row in data.approvals:
        deferred = "  [deferred]" if row.state == "deferred" else ""
        lines.append(f"  [{row.index}] {row.capability}{deferred}")
        lines.append(f"      Executive : {row.executive_id}")
        lines.append(f"      Reason    : {row.reason}")
        lines.append(f"      Risk      : {row.risk_tier.upper()}")
        lines.append(f"      Impact    : {row.impact}")
        lines.append(f"      Requested : {row.requested_at}")
    lines.append("  [A]pprove N   [R]eject N   [D]efer N   approve all")
    return lines


def render_founder_state(
    data: FounderStatePanelData, charset: Charset | None = None
) -> list[str]:
    """Renders the published Founder State verbatim. MB026: "display the
    published Founder State exactly as exposed. Do not derive values
    independently" -- so this iterates whatever keys are published rather
    than naming them, and a future field appears with no change here."""
    if not data.status.available:
        return _unavailable("FOUNDER STATE", data.status, charset)
    if not data.state:
        return ["FOUNDER STATE", f"  {_cs(charset).unavailable} not published"]

    lines = ["FOUNDER STATE"]
    for key, raw in data.state.items():
        rendered = value(raw, charset)
        if len(rendered) > 38:
            rendered = rendered[:35] + "..."
        lines.append(f"  {key:<22} {rendered}")
    return lines


def render_header(
    snapshot: DashboardSnapshot, charset: Charset | None = None
) -> list[str]:
    return [
        rule(charset=charset),
        "KALPAVRIKSHA - FOUNDER EDITION".center(WIDTH),
        f"as of {format_timestamp(snapshot.captured_at, charset)} UTC".center(WIDTH),
        rule(charset=charset),
    ]
