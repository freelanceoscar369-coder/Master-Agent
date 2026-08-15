"""Background work must stay in the background.

Kalpavriksha probes the machine constantly -- installed applications,
running processes, desktop state. Every probe was
`subprocess.run(..., capture_output=True)` with no creation flags, and on
Windows each spawn of a console executable allocates a console window. It
lives for milliseconds and is drawn anyway, so a founder watching a
"quiet, local" application sees black rectangles blink across the screen
while nothing they asked for is happening.

The rule is not "hide everything". It is:

    if the parent reads the output, the founder does not need the window

which is why `DesktopProbe.start()` -- the call that opens VS Code
because a founder said "open VS Code" -- is deliberately excluded. Hiding
that would hide the thing they asked for.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

SRC = pathlib.Path(__file__).resolve().parent.parent / "src" / "master_agent"

#: Every module that spawns a helper process whose output it reads.
PROBE_MODULES = [
    "desktop/probe.py",
    "ai_infrastructure/executive/probes.py",
    "ai_infrastructure/executive/actions.py",
]


def spawns(path: pathlib.Path):
    """Every `subprocess.run(...)` call in a module, with its keywords."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (isinstance(func, ast.Attribute) and func.attr == "run"
                and isinstance(func.value, ast.Name) and func.value.id == "subprocess"):
            yield node, {k.arg for k in node.keywords if k.arg}


@pytest.mark.parametrize("relative", PROBE_MODULES)
def test_every_output_capturing_spawn_is_windowless(relative):
    path = SRC / relative
    assert path.is_file(), relative
    offenders = [
        node.lineno for node, kwargs in spawns(path)
        if "capture_output" in kwargs and "creationflags" not in kwargs
    ]
    assert not offenders, (
        f"{relative} spawns a console-allocating process whose output it "
        f"reads itself, at line(s) {offenders} -- the founder sees a "
        "console flash for work they never asked to watch"
    )


def test_a_founder_requested_launch_is_not_hidden():
    """`start()` opens what the founder asked for. It must NOT carry the
    flag -- this test fails if a future sweep hides it along with the
    probes."""
    source = (SRC / "desktop" / "probe.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    # Three functions are named `start` here: a Protocol stub, the real
    # launcher, and a null probe. The one under test is the one that
    # actually spawns.
    segments = [
        ast.get_source_segment(source, n) or ""
        for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "start"
    ]
    start = next(seg for seg in segments if "Popen(" in seg)
    assert "creationflags" not in start, (
        "a founder-requested application launch was made windowless -- "
        "the founder asked to see that application"
    )


def test_the_flag_is_a_no_op_off_windows():
    from master_agent.foundation.windowless import NO_WINDOW

    assert isinstance(NO_WINDOW, int)
