"""Mission Brief 037 — the founder types a sentence and a mission starts.

Deliverable 6: a founder command automatically becomes
`Objective -> Planner -> Execution`. The console owns none of that — it
turns one line into one `MissionService.start()` call and reports the
answer.
"""
from __future__ import annotations

from typing import Any

import pytest

from master_agent.dashboard.app import build_dashboard
from master_agent.launcher.console import FounderConsole
from tests.missions_test_support import pipeline, plan_text, step
from tests.planner_test_support import CREATE, WRITE, refused, success

TWO_STEPS = plan_text(
    step("make_folder", CREATE.name, {"name": "demo"}),
    step("write_readme", WRITE.name, {"path": "demo/README.md"},
         depends_on=["make_folder"],
         success_doc=success("a README exists", must_contain=["README"])),
)


def console_over(system) -> FounderConsole:
    return FounderConsole(
        dashboard=build_dashboard(
            mission_control=system.mission_control,
            plan_provider=lambda: system.history,
        ),
        mission_control=system.mission_control,
        memory=system.memory,
        missions=system.missions,
        writer=lambda _text: None,
    )


def wired(tmp_path, *replies):
    system = pipeline(*(replies or (TWO_STEPS,)), tmp_path=tmp_path)
    return system, console_over(system)


# =========================================================================
# An unrecognised line is an objective
# =========================================================================


def test_a_sentence_becomes_a_planned_mission(tmp_path):
    system, console = wired(tmp_path)

    reply = console.execute("Set up a demo project")

    assert "planned 2 step(s)" in reply
    assert len(system.mission_control.dispatcher.objectives()) == 1


def test_the_objective_reaches_the_planner_exactly_as_typed(tmp_path):
    """Not lower-cased. The console lower-cases to match its own verbs;
    an objective is prose and must arrive as the founder wrote it."""
    system, console = wired(tmp_path)

    console.execute("Set up a Demo Project for ACME")

    # The IntentLayer parses the input and creates an Intent with goal/constraints/context
    # The prompt should contain the parsed intent's goal and constraints
    assert "Create demo project 'ACME'" in system.runner.prompt
    assert "Project type: demo" in system.runner.prompt
    assert "ACME" in system.runner.prompt


def test_the_reply_names_the_mission_so_it_can_be_found_again(tmp_path):
    system, console = wired(tmp_path)

    reply = console.execute("Set up a demo project")

    objective_id = system.mission_control.dispatcher.objectives()[0].objective_id
    assert objective_id[:8] in reply


def test_a_refused_objective_reports_the_reason_and_starts_nothing(tmp_path):
    system, console = wired(tmp_path, refused("no provider clears the floor"))

    reply = console.execute("Set up a demo project")

    assert "no provider clears the floor" in reply
    assert system.mission_control.dispatcher.objectives() == []


def test_the_console_executes_nothing_itself(tmp_path):
    """It submits. The Runtime pulls. A console that executed would be a
    second execution path."""
    from master_agent.mission_control.tasks import TaskState

    system, console = wired(tmp_path)

    console.execute("Set up a demo project")

    tasks = system.mission_control.dispatcher.objectives()[0].tasks
    assert all(task.state in (TaskState.READY, TaskState.CREATED) for task in tasks)


# =========================================================================
# The existing verbs still win
# =========================================================================


@pytest.mark.parametrize(
    "command", ["help", "?", "quit", "exit", "q", "v", "view", "f", "founder"]
)
def test_a_console_verb_is_never_mistaken_for_an_objective(tmp_path, command):
    system, console = wired(tmp_path)

    console.execute(command)

    assert system.runner.calls == [], f"'{command}' was planned"


def test_approve_still_approves_rather_than_planning(tmp_path):
    system, console = wired(tmp_path)

    reply = console.execute("approve 1")

    assert "no pending approval" in reply
    assert system.runner.calls == []


def test_remember_still_remembers_rather_than_planning(tmp_path):
    system, console = wired(tmp_path)

    console.execute('remember "Always prefer local models"')

    assert system.runner.calls == []
    assert any("local models" in r.full_text for r in system.memory.all())


def test_memory_still_recalls_rather_than_planning(tmp_path):
    system, console = wired(tmp_path)

    console.execute("memory local")

    assert system.runner.calls == []


def test_an_empty_line_does_nothing_at_all(tmp_path):
    system, console = wired(tmp_path)

    assert console.execute("   ") == ""
    assert system.runner.calls == []


def test_the_help_text_says_what_an_unrecognised_line_will_do(tmp_path):
    """A founder about to spend minutes of local inference by typo
    deserves to have been told."""
    _system, console = wired(tmp_path)

    assert "treated as an objective" in console.execute("help")


# =========================================================================
# Without a Planner
# =========================================================================


def test_with_no_planner_wired_the_console_says_so(tmp_path):
    system = pipeline(TWO_STEPS, tmp_path=tmp_path)
    console = console_over(system)
    console._missions = None

    reply = console.execute("Set up a demo project")

    assert "no planner is wired" in reply


def test_a_planner_that_raises_is_a_message_not_a_crash(tmp_path):
    """A console must survive anything. It is what the founder uses to
    stop something irreversible."""

    class Exploding:
        def start(self, _objective: str) -> Any:
            raise RuntimeError("the daemon died mid-plan")

    system = pipeline(TWO_STEPS, tmp_path=tmp_path)
    console = console_over(system)
    console._missions = Exploding()

    reply = console.execute("Set up a demo project")

    assert "could not plan that" in reply
    assert "the daemon died mid-plan" in reply


# =========================================================================
# replay
# =========================================================================


def test_replay_reads_back_the_last_mission(tmp_path):
    system, console = wired(tmp_path)
    console.execute("Set up a demo project")
    plan_id = system.mission_control.dispatcher.objectives()[0].objective_id
    system.mission_control.verification_completed(
        "make_folder", verdict="matched", evidence_id="ev-1", objective_id=plan_id
    )
    system.mission_control.task_completed("make_folder", objective_id=plan_id)

    reply = console.execute("replay")

    assert "Set up a demo project" in reply
    assert "make_folder" in reply
    assert "matched" in reply
    assert "has not finished" in reply


def test_replay_contacts_no_provider(tmp_path):
    system, console = wired(tmp_path)
    console.execute("Set up a demo project")
    calls = len(system.runner.calls)

    console.execute("replay")

    assert len(system.runner.calls) == calls


def test_replay_before_anything_is_planned_says_so(tmp_path):
    _system, console = wired(tmp_path)

    assert "nothing has been planned yet" in console.execute("replay")


def test_replay_of_an_unknown_mission_says_so(tmp_path):
    _system, console = wired(tmp_path)

    assert "no mission nope" in console.execute("replay nope")


def test_replay_names_a_step_that_was_never_checked(tmp_path):
    _system, console = wired(tmp_path)
    console.execute("Set up a demo project")

    reply = console.execute("replay")

    assert "not checked" in reply


def test_replay_with_no_history_being_kept_says_so(tmp_path):
    console = console_over(pipeline(TWO_STEPS, tmp_path=tmp_path, with_history=False))

    assert "no mission history" in console.execute("replay")
