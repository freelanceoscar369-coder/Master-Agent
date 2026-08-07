"""MB038 Step 13 — timeout evidence, made observable.

Reporting only. Nothing here changes what executes: every test builds a
snapshot from a record that already exists and asserts what a founder
would read.
"""
from __future__ import annotations

from master_agent.ai_infrastructure.admission import OCCUPIED
from master_agent.ai_infrastructure.ledger import ABANDONED, REFUSED, ExecutionRecord
from master_agent.dashboard.charset import ASCII
from master_agent.dashboard.founder import build_founder_view
from master_agent.dashboard.founder_panels import render_intelligence
from master_agent.dashboard.readmodel import (
    BrokerPanelData,
    DashboardSnapshot,
    ExecutionRow,
)
from master_agent.dashboard.sources import _budget_line, _execution_row
from master_agent.providers.response import CANCELLED, TIMED_OUT_TTFT

BUDGET = {
    "total_ms": 300_000.0,
    "ttft_ms": 200_000.0,
    "itl_ms": 5_000.0,
    "enforce_itl": True,
    "derivation": {"request_class": "planning", "total_bound_by": "class_ceiling"},
}


class Entry:
    def __init__(self, execution):
        self.execution = execution


def row_for(**fields) -> ExecutionRow:
    defaults = {
        "provider_id": "ollama.local",
        "outcome": "succeeded",
        "latency_ms": 1200.0,
        "cost": 0.0,
    }
    defaults.update(fields)
    return _execution_row(Entry(ExecutionRecord(**defaults)))


def view_for(row: ExecutionRow | None):
    snapshot = DashboardSnapshot(
        captured_at=None,  # type: ignore[arg-type]
        broker=BrokerPanelData(last_execution=row),
    )
    return build_founder_view(snapshot)


# ---- the read model ------------------------------------------------------


def test_a_budgeted_execution_reports_its_three_deadlines():
    row = row_for(budget=BUDGET)

    assert row.budget == "300s total / 200s first token / 5s stall"
    assert row.bound_by == "class_ceiling"


def test_an_unbudgeted_execution_reports_nothing_rather_than_zero():
    """A pre-MB038 call had no budget. Showing `0s total` would be a
    fabricated fact about it."""
    row = row_for()

    assert row.budget == ""
    assert row.bound_by == ""
    assert row.timeout_reason == ""


def test_a_timeout_reports_which_deadline_ended_it():
    row = row_for(outcome=TIMED_OUT_TTFT, timeout={"reason": TIMED_OUT_TTFT})

    assert row.timeout_reason == TIMED_OUT_TTFT


def test_an_admission_refusal_is_visible():
    row = row_for(outcome="not_admitted", admission=OCCUPIED, lifecycle=REFUSED)

    assert row.admission == OCCUPIED
    assert row.lifecycle == REFUSED


def test_the_budget_line_is_absent_for_an_empty_budget():
    assert _budget_line(None) == ""
    assert _budget_line({}) == ""


def test_a_partial_budget_does_not_crash_the_panel():
    """A record from a future or older shape must render, not explode."""
    assert _budget_line({"total_ms": 1000.0}) == "1s total / 0s first token / 0s stall"


# ---- the view model ------------------------------------------------------


def test_the_founder_view_carries_the_budget_through():
    view = view_for(row_for(budget=BUDGET))

    assert view.intelligence.thinking.budget.startswith("300s total")
    assert view.intelligence.thinking.bound_by == "class ceiling"


def test_the_view_words_a_timeout_reason_for_a_human():
    view = view_for(row_for(outcome=TIMED_OUT_TTFT, timeout={"reason": TIMED_OUT_TTFT}))

    assert view.intelligence.thinking.timeout_reason == "timed out ttft"


def test_an_abandoned_call_is_carried_to_the_view():
    view = view_for(row_for(outcome=CANCELLED, lifecycle=ABANDONED))

    assert view.intelligence.thinking.lifecycle == ABANDONED


# ---- the panel -----------------------------------------------------------


def rendered(row) -> str:
    return "\n".join(render_intelligence(view_for(row), ASCII))


def test_the_panel_shows_the_budget_and_what_bound_it():
    text = rendered(row_for(budget=BUDGET))

    assert "Budget" in text
    assert "300s total" in text
    assert "Bound by" in text


def test_the_panel_says_nothing_about_a_budget_that_did_not_exist():
    text = rendered(row_for())

    assert "Budget" not in text
    assert "Bound by" not in text


def test_the_panel_names_the_deadline_that_ended_a_call():
    """"It timed out" was three different failures with three different
    fixes until MB038."""
    text = rendered(
        row_for(outcome=TIMED_OUT_TTFT, timeout={"reason": TIMED_OUT_TTFT}, budget=BUDGET)
    )

    assert "Deadline" in text
    assert "timed out ttft" in text


def test_the_panel_warns_that_an_abandoned_provider_may_still_be_running():
    """The founder stopped waiting. The machine may not have."""
    text = rendered(row_for(outcome=CANCELLED, lifecycle=ABANDONED))

    assert "Abandoned" in text
    assert "may still be running" in text


def test_a_completed_call_carries_no_abandonment_warning():
    text = rendered(row_for(budget=BUDGET))

    assert "Abandoned" not in text


def test_the_panel_still_renders_when_nothing_has_run():
    assert render_intelligence(view_for(None), ASCII)


def test_reporting_reads_and_never_computes():
    """The row is a transcription. Every MB038 field on it must appear
    verbatim in the record it came from."""
    record = ExecutionRecord(
        provider_id="p",
        outcome="succeeded",
        budget=BUDGET,
        admission="admitted",
        lifecycle="completed",
    )

    row = _execution_row(Entry(record))

    assert row.admission == record.admission
    assert row.lifecycle == record.lifecycle
    assert row.bound_by == record.budget["derivation"]["total_bound_by"]
