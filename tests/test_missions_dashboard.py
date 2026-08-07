"""Mission Brief 037 — what the founder sees while a plan runs.

The brief asks the Dashboard to show: Current Mission, Current Step,
Completed, Remaining, Waiting on dependency, Failed verification. And it
forbids one thing outright: *never display internal LLM reasoning.*

Both halves are asserted here — what must appear, and what must not.
"""
from __future__ import annotations

from datetime import UTC, datetime

from master_agent.dashboard.charset import ASCII
from master_agent.dashboard.founder import as_dict, build_founder_view
from master_agent.dashboard.founder_panels import (
    MAX_PLAN_ROWS,
    render_founder_frame,
    render_plan,
)
from master_agent.dashboard.readmodel import DashboardSnapshot
from master_agent.dashboard.sources import DashboardSources
from tests.missions_test_support import pipeline, plan_text, step
from tests.planner_test_support import CREATE, WRITE, success

WHEN = datetime(2026, 7, 31, 9, 0, tzinfo=UTC)

TWO_STEPS = plan_text(
    step("make_folder", CREATE.name, {"name": "demo"}),
    step("write_readme", WRITE.name, {"path": "demo/README.md"},
         depends_on=["make_folder"],
         success_doc=success("a README exists", must_contain=["README"])),
)


def viewed(system):
    """The founder view, through the real source layer."""
    sources = DashboardSources(
        mission_control=system.mission_control,
        plan_provider=lambda: system.history,
        clock=lambda: WHEN,
    )
    return build_founder_view(sources.collect())


def running_plan(tmp_path):
    system = pipeline(TWO_STEPS, tmp_path=tmp_path)
    outcome = system.start("Set up a demo project")
    return system, outcome.objective_id


# =========================================================================
# What it must show
# =========================================================================


def test_before_anything_is_planned_the_panel_says_so(tmp_path):
    system = pipeline(TWO_STEPS, tmp_path=tmp_path)

    view = viewed(system)

    assert view.plan.available is False
    assert "nothing planned" in view.plan.reason
    assert "nothing planned" in "\n".join(render_plan(view, ASCII))


def test_a_dashboard_with_no_planner_attached_says_that_instead():
    sources = DashboardSources(clock=lambda: WHEN)

    view = build_founder_view(sources.collect())

    assert view.plan.available is False
    assert "no planner attached" in view.plan.reason


def test_the_current_mission_is_the_founders_own_words(tmp_path):
    system, _plan_id = running_plan(tmp_path)

    view = viewed(system)

    assert view.plan.available
    assert view.plan.objective == "Set up a demo project"


def test_the_current_step_its_capability_and_its_expectation_are_shown(tmp_path):
    system, _plan_id = running_plan(tmp_path)

    view = viewed(system)

    assert view.plan.current_step == "make_folder"
    assert view.plan.current_capability == CREATE.name
    assert view.plan.current_expectation


def test_completed_and_remaining_are_counted(tmp_path):
    system, plan_id = running_plan(tmp_path)
    system.mission_control.verification_completed(
        "make_folder", verdict="matched", evidence_id="ev-1", objective_id=plan_id
    )
    system.mission_control.task_completed("make_folder", objective_id=plan_id)

    view = viewed(system)

    assert view.plan.completed == 1
    assert view.plan.remaining == 1
    assert view.plan.progress == 0.5


def test_a_step_waiting_on_a_dependency_says_which_one(tmp_path):
    """MB029's rule that a founder-facing state carries its reason,
    applied to the state that is otherwise indistinguishable from being
    stuck."""
    system, _plan_id = running_plan(tmp_path)

    view = viewed(system)

    assert view.plan.blocked == 1
    waiting = next(s for s in view.plan.steps if s.step_id == "write_readme")
    assert waiting.state == "waiting on make_folder"


def test_a_failed_verification_is_shown_as_a_failure_with_its_verdict(tmp_path):
    system, plan_id = running_plan(tmp_path)
    system.mission_control.verification_completed(
        "make_folder", verdict="not_matched", evidence_id="ev-1", objective_id=plan_id
    )
    system.mission_control.task_failed(
        "make_folder", "verification verdict was 'not_matched'", objective_id=plan_id
    )

    view = viewed(system)

    assert view.plan.failed == 1
    failed = next(s for s in view.plan.steps if s.step_id == "make_folder")
    assert failed.state == "failed"
    assert "verification verdict" in failed.detail


def test_a_step_that_completed_without_matching_is_flagged_not_ticked(tmp_path):
    """A completed step with a non-matching verdict must never render as a
    success."""
    system, plan_id = running_plan(tmp_path)
    system.mission_control.verification_completed(
        "make_folder", verdict="partially_matched", evidence_id="ev-1", objective_id=plan_id
    )
    system.mission_control.task_completed("make_folder", objective_id=plan_id)

    view = viewed(system)

    assert view.plan.unverified == 1
    done = next(s for s in view.plan.steps if s.step_id == "make_folder")
    assert done.detail == "verification: partially matched"
    assert "not verified" in "\n".join(render_plan(view, ASCII))


def test_a_step_waiting_on_a_failed_step_says_it_will_not_run(tmp_path):
    """Found by running MB037 live. "Waiting on step_1" is true and
    misleading once step_1 has failed -- a founder reading it would keep
    waiting for something that will never happen."""
    system, plan_id = running_plan(tmp_path)
    system.mission_control.task_failed(
        "make_folder", "missing required parameter: name", objective_id=plan_id
    )

    view = viewed(system)

    dependent = next(s for s in view.plan.steps if s.step_id == "write_readme")
    assert dependent.state == "will not run - make_folder failed"
    assert "will not run" in "\n".join(render_plan(view, ASCII))


def test_a_step_waiting_on_one_that_is_merely_unfinished_still_says_waiting(tmp_path):
    """The distinction only exists because both states are real."""
    system, _plan_id = running_plan(tmp_path)

    dependent = next(s for s in viewed(system).plan.steps if s.step_id == "write_readme")

    assert dependent.state == "waiting on make_folder"


def test_the_panel_names_who_planned_it(tmp_path):
    system, _plan_id = running_plan(tmp_path)

    assert "alpha-local" in "\n".join(render_plan(viewed(system), ASCII))


def test_the_panel_renders_every_step(tmp_path):
    system, _plan_id = running_plan(tmp_path)

    rendered = "\n".join(render_plan(viewed(system), ASCII))

    assert "make_folder" in rendered
    assert "write_readme" in rendered


def test_a_long_plan_says_what_it_is_not_showing(tmp_path):
    """No silent truncation: a list that quietly stops reads as a shorter
    plan."""
    many = plan_text(*[step(f"s{index}", CREATE.name) for index in range(MAX_PLAN_ROWS + 4)])
    system = pipeline(many, tmp_path=tmp_path)
    system.start("A long one")

    rendered = "\n".join(render_plan(viewed(system), ASCII))

    assert "and 4 more step(s)" in rendered


# =========================================================================
# What it must never show
# =========================================================================


def test_the_founder_page_never_shows_the_prompt_or_the_reply(tmp_path):
    """The brief forbids internal LLM reasoning on this page. The read
    model has nowhere to put it, which is the cheapest way to keep that
    true as the panel grows."""
    system, _plan_id = running_plan(tmp_path)

    view = viewed(system)
    frame = render_founder_frame(view, ASCII)

    assert "You are the Planner" not in frame
    assert "Capabilities available" not in frame
    assert not hasattr(view.plan, "prompt")
    assert not hasattr(view.plan, "raw")
    assert not hasattr(view.plan, "reasoning")


def test_the_plan_panel_data_has_no_field_for_a_reply(tmp_path):
    system, _plan_id = running_plan(tmp_path)
    sources = DashboardSources(
        mission_control=system.mission_control,
        plan_provider=lambda: system.history,
        clock=lambda: WHEN,
    )

    fields = set(sources.collect().plan.__dataclass_fields__)

    assert not fields & {"prompt", "raw", "reply", "reasoning", "thinking"}


# =========================================================================
# The frame as a whole
# =========================================================================


def test_the_frame_stays_within_its_sixty_lines_with_a_plan_running(tmp_path):
    system, _plan_id = running_plan(tmp_path)

    frame = render_founder_frame(viewed(system), ASCII)

    assert len(frame.splitlines()) <= 60


def test_the_frame_stays_within_sixty_lines_with_a_long_plan(tmp_path):
    many = plan_text(*[step(f"s{index}", CREATE.name) for index in range(30)])
    system = pipeline(many, tmp_path=tmp_path)
    system.start("A long one")

    frame = render_founder_frame(viewed(system), ASCII)

    assert len(frame.splitlines()) <= 60


def test_the_plan_replaces_the_older_mission_summary_rather_than_repeating_it(tmp_path):
    """Both answer "what is it doing". Showing both would say it twice and
    push the page past its line budget."""
    system, _plan_id = running_plan(tmp_path)

    frame = render_founder_frame(viewed(system), ASCII)

    assert frame.count("CURRENT MISSION") == 1
    assert "MISSION\n" not in frame.replace("CURRENT MISSION", "")


def test_with_no_plan_the_older_mission_summary_still_shows(tmp_path):
    """The launcher's own machine scan is an objective nobody planned. It
    must not become invisible."""
    system = pipeline(TWO_STEPS, tmp_path=tmp_path)

    frame = render_founder_frame(viewed(system), ASCII)

    assert "MISSION" in frame


def test_the_view_serialises_for_a_front_end_that_imports_none_of_this(tmp_path):
    import json

    system, _plan_id = running_plan(tmp_path)

    document = as_dict(viewed(system))

    json.dumps(document)
    assert document["plan"]["objective"] == "Set up a demo project"
    assert document["plan"]["current_step"] == "make_folder"
    assert [s["step_id"] for s in document["plan"]["steps"]] == [
        "make_folder",
        "write_readme",
    ]


def test_a_plan_provider_that_raises_becomes_absent_data_with_a_reason():
    """ADR-0016 Decision 2: a failed read is absent data, never an
    exception that blanks the view."""

    def broken():
        raise RuntimeError("history is gone")

    sources = DashboardSources(plan_provider=broken, clock=lambda: WHEN)

    view = build_founder_view(sources.collect())

    assert view.plan.available is False
    assert "history is gone" in view.plan.reason


def test_a_plan_provider_returning_nothing_is_reported_honestly():
    sources = DashboardSources(plan_provider=lambda: None, clock=lambda: WHEN)

    assert "no plan history" in build_founder_view(sources.collect()).plan.reason


def test_the_history_count_is_reported_even_before_the_first_plan(tmp_path):
    system = pipeline(TWO_STEPS, tmp_path=tmp_path)
    sources = DashboardSources(plan_provider=lambda: system.history, clock=lambda: WHEN)

    assert sources.collect().plan.history_count == 0


def test_a_default_snapshot_reports_no_plan_rather_than_an_empty_one():
    """`0/0 steps` for a mission nobody started is `0` standing in for
    "unknown", which ADR-0016 exists to prevent."""
    snapshot = DashboardSnapshot(captured_at=WHEN)

    assert snapshot.plan.status.available is False
    assert build_founder_view(snapshot).plan.available is False
