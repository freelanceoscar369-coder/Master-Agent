"""Cumulative Cost Model (Mission Brief 031 Deliverable 7).

Tracks spend over time, enforces budget caps. Per-request cost model already
exists in ProviderProfile.cost and TaskProfile.max_cost; this adds cumulative
spend tracking, periodic budget enforcement, and spend forecasting.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from master_agent.broker.decision import BrokerDecision


class BudgetPeriod(str, Enum):
    """Budget period for caps."""

    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    TOTAL = "total"  # Lifetime


@dataclass(frozen=True)
class BudgetCap:
    """A budget cap for a period."""

    period: BudgetPeriod
    max_spend: float  # In the budget's currency
    currency: str = "USD"

    # Optional: scope to specific providers/capabilities
    provider_id: str | None = None
    ai_capability: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "period": self.period.value,
            "max_spend": self.max_spend,
            "currency": self.currency,
            "provider_id": self.provider_id,
            "ai_capability": self.ai_capability,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BudgetCap:
        return cls(
            period=BudgetPeriod(data["period"]),
            max_spend=data["max_spend"],
            currency=data.get("currency", "USD"),
            provider_id=data.get("provider_id"),
            ai_capability=data.get("ai_capability"),
        )


@dataclass(frozen=True)
class SpendEntry:
    """One recorded spend event."""

    decision_id: str
    provider_id: str
    ai_capability: str
    task_class: str
    cost: float
    currency: str = "USD"
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    task_id: str = ""
    objective_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "provider_id": self.provider_id,
            "ai_capability": self.ai_capability,
            "task_class": self.task_class,
            "cost": self.cost,
            "currency": self.currency,
            "timestamp": self.timestamp.isoformat(),
            "task_id": self.task_id,
            "objective_id": self.objective_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SpendEntry:
        return cls(
            decision_id=data["decision_id"],
            provider_id=data["provider_id"],
            ai_capability=data["ai_capability"],
            task_class=data["task_class"],
            cost=data["cost"],
            currency=data.get("currency", "USD"),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            task_id=data.get("task_id", ""),
            objective_id=data.get("objective_id"),
        )


@dataclass(frozen=True)
class BudgetStatus:
    """Current status of a budget cap."""

    cap: BudgetCap
    spent: float
    remaining: float
    period_start: datetime
    period_end: datetime
    is_exceeded: bool
    utilization_pct: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "cap": self.cap.as_dict(),
            "spent": self.spent,
            "remaining": self.remaining,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "is_exceeded": self.is_exceeded,
            "utilization_pct": self.utilization_pct,
        }


@dataclass(frozen=True)
class CostModelConfig:
    """Configuration for the cost model."""

    currency: str = "USD"
    default_daily_cap: float | None = None
    default_monthly_cap: float | None = None
    default_total_cap: float | None = None
    warning_threshold_pct: float = 0.8  # Warn at 80%
    critical_threshold_pct: float = 0.95  # Critical at 95%


class CostModel:
    """Tracks cumulative spend and enforces budget caps.

    Budget caps that merely warn are not caps (ADR-0017 §19.4). When a cap
    is exceeded, paid tiers are filtered out entirely by the Broker.
    """

    def __init__(
        self,
        config: CostModelConfig | None = None,
        sink: Any = None,
    ) -> None:
        self._config = config or CostModelConfig()
        self._sink = sink
        self._spend: list[SpendEntry] = []
        self._caps: list[BudgetCap] = []
        self._audit_log: list[dict[str, Any]] = []

        # Initialize default caps
        if self._config.default_daily_cap is not None:
            self._caps.append(BudgetCap(
                period=BudgetPeriod.DAILY,
                max_spend=self._config.default_daily_cap,
                currency=self._config.currency,
            ))
        if self._config.default_monthly_cap is not None:
            self._caps.append(BudgetCap(
                period=BudgetPeriod.MONTHLY,
                max_spend=self._config.default_monthly_cap,
                currency=self._config.currency,
            ))
        if self._config.default_total_cap is not None:
            self._caps.append(BudgetCap(
                period=BudgetPeriod.TOTAL,
                max_spend=self._config.default_total_cap,
                currency=self._config.currency,
            ))

    def record_spend(
        self,
        decision: BrokerDecision,
        actual_cost: float | None = None,
        task_id: str = "",
        objective_id: str | None = None,
    ) -> SpendEntry:
        """Record a spend event from a Broker decision."""
        cost = actual_cost if actual_cost is not None else decision.cost_estimate

        # Estimate cost from winner if not provided
        if cost == 0 and decision.winner:
            # This would need provider registry lookup - for now use 0
            pass

        entry = SpendEntry(
            decision_id=decision.task.task_id,
            provider_id=decision.winner or "unknown",
            ai_capability=decision.task.capability,
            task_class=self._infer_task_class(decision.task),
            cost=cost,
            currency=self._config.currency,
            task_id=task_id,
            objective_id=objective_id,
        )

        self._spend.append(entry)
        self._audit("spend_recorded", entry)
        return entry

    def _infer_task_class(self, task) -> str:
        if task.sensitivity == "sensitive":
            return "sensitive"
        if task.offline:
            return "offline"
        if task.required_context_tokens and task.required_context_tokens > 8000:
            return "long_context"
        return "general"

    def get_spend(
        self,
        period: BudgetPeriod | None = None,
        provider_id: str | None = None,
        ai_capability: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> tuple[SpendEntry, ...]:
        """Get spend entries matching filters."""
        results = []

        for entry in self._spend:
            if period and not self._in_period(entry.timestamp, period):
                continue
            if provider_id and entry.provider_id != provider_id:
                continue
            if ai_capability and entry.ai_capability != ai_capability:
                continue
            if since and entry.timestamp < since:
                continue
            if until and entry.timestamp > until:
                continue
            results.append(entry)

        return tuple(results)

    def _in_period(self, timestamp: datetime, period: BudgetPeriod) -> bool:
        now = datetime.now(UTC)
        if period == BudgetPeriod.HOURLY:
            return timestamp >= now.replace(minute=0, second=0, microsecond=0)
        elif period == BudgetPeriod.DAILY:
            return timestamp >= now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == BudgetPeriod.WEEKLY:
            # Week starts Monday
            days_since_monday = now.weekday()
            week_start = now - timedelta(days=days_since_monday)
            return timestamp >= week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == BudgetPeriod.MONTHLY:
            return timestamp >= now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        elif period == BudgetPeriod.TOTAL:
            return True
        return False

    def _period_bounds(self, period: BudgetPeriod) -> tuple[datetime, datetime]:
        """Get (start, end) of current period."""
        now = datetime.now(UTC)
        if period == BudgetPeriod.HOURLY:
            start = now.replace(minute=0, second=0, microsecond=0)
            end = start + timedelta(hours=1)
        elif period == BudgetPeriod.DAILY:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
        elif period == BudgetPeriod.WEEKLY:
            days_since_monday = now.weekday()
            start = (now - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(weeks=1)
        elif period == BudgetPeriod.MONTHLY:
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if start.month == 12:
                end = start.replace(year=start.year + 1, month=1)
            else:
                end = start.replace(month=start.month + 1)
        elif period == BudgetPeriod.TOTAL:
            start = datetime.min.replace(tzinfo=UTC)
            end = datetime.max.replace(tzinfo=UTC)
        else:
            start = now
            end = now
        return start, end

    def get_budget_status(self, cap: BudgetCap) -> BudgetStatus:
        """Get current status of a budget cap."""
        start, end = self._period_bounds(cap.period)
        entries = self.get_spend(
            period=cap.period,
            provider_id=cap.provider_id,
            ai_capability=cap.ai_capability,
        )
        spent = sum(e.cost for e in entries)
        remaining = max(0.0, cap.max_spend - spent)
        is_exceeded = spent >= cap.max_spend
        utilization_pct = (spent / cap.max_spend * 100) if cap.max_spend > 0 else 0.0

        return BudgetStatus(
            cap=cap,
            spent=spent,
            remaining=remaining,
            period_start=start,
            period_end=end,
            is_exceeded=is_exceeded,
            utilization_pct=utilization_pct,
        )

    def all_budget_statuses(self) -> tuple[BudgetStatus, ...]:
        """Status of all budget caps."""
        return tuple(self.get_budget_status(cap) for cap in self._caps)

    def is_budget_exceeded(
        self,
        provider_id: str | None = None,
        ai_capability: str | None = None,
    ) -> bool:
        """Check if any relevant budget cap is exceeded."""
        for cap in self._caps:
            if cap.provider_id and cap.provider_id != provider_id:
                continue
            if cap.ai_capability and cap.ai_capability != ai_capability:
                continue
            status = self.get_budget_status(cap)
            if status.is_exceeded:
                return True
        return False

    def get_effective_max_cost(
        self,
        provider_id: str | None = None,
        ai_capability: str | None = None,
    ) -> float | None:
        """Get the effective max_cost for a provider/capability based on budgets.

        Returns the lowest remaining budget across all matching caps,
        or None if no caps apply.
        """
        min_remaining = None

        for cap in self._caps:
            if cap.provider_id and cap.provider_id != provider_id:
                continue
            if cap.ai_capability and cap.ai_capability != ai_capability:
                continue
            status = self.get_budget_status(cap)
            if min_remaining is None or status.remaining < min_remaining:
                min_remaining = status.remaining

        return min_remaining

    def add_cap(self, cap: BudgetCap) -> None:
        """Add a budget cap."""
        self._caps.append(cap)
        self._audit("cap_added", cap)

    def remove_cap(self, cap: BudgetCap) -> bool:
        """Remove a budget cap."""
        for i, existing in enumerate(self._caps):
            if (
                existing.period == cap.period
                and existing.max_spend == cap.max_spend
                and existing.currency == cap.currency
                and existing.provider_id == cap.provider_id
                and existing.ai_capability == cap.ai_capability
            ):
                self._caps.pop(i)
                self._audit("cap_removed", cap)
                return True
        return False

    def total_spend(self, since: datetime | None = None) -> float:
        """Total spend, optionally since a date."""
        entries = self.get_spend(since=since)
        return sum(e.cost for e in entries)

    def forecast_spend(
        self,
        horizon: BudgetPeriod = BudgetPeriod.MONTHLY,
        provider_id: str | None = None,
        ai_capability: str | None = None,
    ) -> float:
        """Simple linear forecast based on recent spend rate."""
        # Get daily spend rate over last 7 days
        week_ago = datetime.now(UTC) - timedelta(days=7)
        recent = self.get_spend(
            provider_id=provider_id,
            ai_capability=ai_capability,
            since=week_ago,
        )
        if not recent:
            return 0.0

        daily_rate = sum(e.cost for e in recent) / 7.0

        if horizon == BudgetPeriod.DAILY:
            return daily_rate
        elif horizon == BudgetPeriod.WEEKLY:
            return daily_rate * 7
        elif horizon == BudgetPeriod.MONTHLY:
            return daily_rate * 30
        elif horizon == BudgetPeriod.TOTAL:
            return sum(e.cost for e in self._spend) + daily_rate * 30
        return daily_rate

    def audit_log(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._audit_log)

    def _audit(self, event_type: str, data: Any, previous: Any = None) -> None:
        event = {
            "event_type": event_type,
            "timestamp": datetime.now(UTC).isoformat(),
            "data": data.as_dict() if hasattr(data, "as_dict") else str(data),
            "previous": previous.as_dict() if previous and hasattr(previous, "as_dict") else None,
        }
        self._audit_log.append(event)
        if self._sink is not None:
            try:
                self._sink(event)
            except Exception:
                pass


# Convenience for Broker integration
def check_budget_for_decision(
    cost_model: CostModel,
    decision: BrokerDecision,
) -> tuple[bool, list[BudgetStatus]]:
    """Check if a decision's selection would exceed any budget.

    Returns (allowed, exceeded_statuses). If not allowed, the Broker should
    filter out the selected provider.
    """
    if not decision.winner:
        return True, []

    provider_id = decision.winner
    ai_capability = decision.task.capability

    exceeded = []
    for cap in cost_model._caps:
        if cap.provider_id and cap.provider_id != provider_id:
            continue
        if cap.ai_capability and cap.ai_capability != ai_capability:
            continue
        status = cost_model.get_budget_status(cap)
        if status.is_exceeded:
            exceeded.append(status)

    return len(exceeded) == 0, exceeded