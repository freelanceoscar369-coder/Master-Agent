"""Production must not know what the demo happens to be about.

Two objectives carried this work: a game search, and a set of community
repair workshops. Both were chosen so the system would be exercised, not
so it would be taught. A capability that recognises "Ashcombe" only ever
works for Ashcombe.

The check reads EXECUTABLE CODE, not comments. Every module here
discusses the demo at length in its docstrings and its history, and
should — recording why a decision was made is the opposite of encoding
one. What must never appear is a branch, a constant or a string that a
mission's subject can reach at run time.
"""
from __future__ import annotations

import importlib
import inspect
import io
import re
import tokenize

import pytest

#: Words from the two demo objectives and their controlled fixtures.
DEMO_VOCABULARY = [
    # the repair-workshop centrepiece
    "ashcombe", "brindle", "calder", "repair workshop", "workshops",
    "laptops", "saturday", "weekend-archive",
    # the reading rooms
    "halden", "brackwell", "coleport", "reading room", "step-free",
    # the game objective
    "steam", "rpg", "action rpg", "demo download",
    # H
    "barcelona", "madrid", "hamburg", "metro",
]

#: Every module that decides anything about a mission's subject.
DECIDING_MODULES = [
    "master_agent.brain.deliberation",
    "master_agent.brain.conformance",
    "master_agent.brain.intent",
    "master_agent.planner.planner",
    "master_agent.planner.prompting",
    "master_agent.planner.direct",
    "master_agent.planner.task_playbook",
    "master_agent.missions.service",
    "master_agent.runtime.sensitivity",
    "master_agent.runtime.input_resolution",
    "master_agent.plugins.browser_observation",
    "master_agent.executor.actions.browser.read_page_text",
    "master_agent.executor.actions.reasoning.transform",
    "master_agent.providers.desktop_app",
    "master_agent.providers.reasoning_session",
]


def executable_code(module) -> str:
    """The source with comments and string literals removed.

    Docstrings are where this codebase keeps its reasoning, and the
    reasoning is FULL of the demo — deliberately. Only what runs counts
    as knowledge the product has.
    """
    kept: list[str] = []
    for token in tokenize.generate_tokens(
        io.StringIO(inspect.getsource(module)).readline
    ):
        if token.type not in (tokenize.COMMENT, tokenize.STRING):
            kept.append(token.string)
    return " ".join(kept).lower()


@pytest.mark.parametrize("name", DECIDING_MODULES)
def test_no_module_knows_what_the_demo_is_about(name):
    module = importlib.import_module(name)
    code = executable_code(module)

    named = [
        word for word in DEMO_VOCABULARY
        if re.search(rf"(?<![a-z]){re.escape(word)}(?![a-z])", code)
    ]

    assert named == [], f"{name} names {named} in executable code"


def test_the_check_can_actually_fail():
    """A guard that cannot fail is decoration. This proves the reader
    sees code, and equally that it ignores prose."""
    module = type("M", (), {})()

    source = 'x = 1\n# ashcombe in a comment\ny = "ashcombe in a string"\n'
    kept = " ".join(
        token.string
        for token in tokenize.generate_tokens(io.StringIO(source).readline)
        if token.type not in (tokenize.COMMENT, tokenize.STRING)
    ).lower()
    assert "ashcombe" not in kept

    source = "ashcombe = 1\n"
    kept = " ".join(
        token.string
        for token in tokenize.generate_tokens(io.StringIO(source).readline)
        if token.type not in (tokenize.COMMENT, tokenize.STRING)
    ).lower()
    assert "ashcombe" in kept
    del module


def test_the_fixtures_are_the_only_place_the_subjects_live():
    """Where the demo vocabulary IS allowed: the acceptance scripts that
    stage controlled reality, and the tests that assert against it."""
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[1]
    offenders = []
    for path in (root / "src").rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="replace").lower()
        for word in ("ashcombe", "brindle", "calder", "halden"):
            if word in text:
                offenders.append(f"{path.relative_to(root)}: {word}")
    assert offenders == [], offenders
