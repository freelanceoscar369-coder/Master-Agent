"""Every mouse primitive is either reachable or deliberately internal.

A capability that exists and cannot be called is indistinguishable from a
missing one at the moment somebody needs it, so this file accounts for all
of them: click (with button and count), drag and scroll are public;
`move()` is internal, and says so here rather than in someone's memory.
"""
from __future__ import annotations

from master_agent.desktop.actions import DesktopContext
from master_agent.desktop.actions_interaction import (
    DESKTOP_INTERACTION_ACTION_CLASSES,
    ClickControlAction,
    DragPointerAction,
    ScrollPointerAction,
)
from master_agent.desktop.execution.mouse import MouseController
from master_agent.executor.action import ExecutionResult


class Recorder:
    """A mouse that records instead of moving one."""

    def __init__(self):
        self.calls = []

    def click(self, x, y, button="left"):
        self.calls.append(("click", x, y, button))
        return ExecutionResult(success=True, output={"x": x, "y": y, "button": button})

    def multi_click(self, x, y, count, button="left"):
        self.calls.append(("multi_click", x, y, count, button))
        return ExecutionResult(success=True,
                               output={"x": x, "y": y, "button": button, "count": count})

    def drag(self, x1, y1, x2, y2):
        self.calls.append(("drag", x1, y1, x2, y2))
        return ExecutionResult(success=True, output={"from": (x1, y1), "to": (x2, y2)})

    def scroll(self, x, y, amount):
        self.calls.append(("scroll", x, y, amount))
        return ExecutionResult(success=True, output={"x": x, "y": y, "amount": amount})


def _wired(action_cls, monkeypatch, recorder):
    """The real Action with its window checks satisfied and its mouse faked."""
    action = action_cls(DesktopContext())
    window = {"handle": 1, "title": "t", "process_id": 2,
              "is_visible": True, "is_minimized": False, "is_maximized": False}
    monkeypatch.setattr(type(action), "_resolve_window",
                        lambda self, app: ExecutionResult(True, output={"window": window}))
    monkeypatch.setattr(type(action), "_focus_and_confirm",
                        lambda self, w: ExecutionResult(True, output={"window": window}))
    monkeypatch.setattr("master_agent.desktop.actions_interaction._executor",
                        lambda ctx: type("E", (), {"mouse": recorder})())
    return action


# ---- click: one capability, five gestures -------------------------------


def test_default_click_is_one_left_click(monkeypatch):
    recorder = Recorder()
    action = _wired(ClickControlAction, monkeypatch, recorder)
    assert action.run({"application": "chrome", "x": 10, "y": 20}).success
    assert recorder.calls == [("click", 10, 20, "left")]


def test_two_clicks_use_the_generic_repeated_primitive(monkeypatch):
    recorder = Recorder()
    action = _wired(ClickControlAction, monkeypatch, recorder)
    action.run({"application": "chrome", "x": 1, "y": 2, "click_count": 2})
    assert recorder.calls == [("multi_click", 1, 2, 2, "left")]


def test_three_clicks_use_the_same_primitive(monkeypatch):
    recorder = Recorder()
    action = _wired(ClickControlAction, monkeypatch, recorder)
    action.run({"application": "chrome", "x": 1, "y": 2, "click_count": 3})
    assert recorder.calls == [("multi_click", 1, 2, 3, "left")]


def test_right_click_is_the_same_capability_with_a_button(monkeypatch):
    recorder = Recorder()
    action = _wired(ClickControlAction, monkeypatch, recorder)
    action.run({"application": "chrome", "x": 5, "y": 6, "button": "right"})
    assert recorder.calls == [("click", 5, 6, "right")]


def test_an_unknown_button_is_refused_before_anything_moves():
    errors = ClickControlAction(DesktopContext()).validate(
        {"application": "chrome", "x": 1, "y": 1, "button": "purple"}
    )
    assert errors and "button" in errors[0]


def test_a_non_positive_click_count_is_refused():
    action = ClickControlAction(DesktopContext())
    for bad in (0, -1, True, 1.5, "3"):
        errors = action.validate({"application": "chrome", "x": 1, "y": 1,
                                  "click_count": bad})
        assert errors, f"click_count={bad!r} should be refused"


# ---- drag and scroll: previously built and unreachable ------------------


def test_drag_is_reachable_and_reaches_the_existing_primitive(monkeypatch):
    recorder = Recorder()
    action = _wired(DragPointerAction, monkeypatch, recorder)
    assert action.run({"application": "chrome", "x1": 1, "y1": 2,
                       "x2": 3, "y2": 4}).success
    assert recorder.calls == [("drag", 1, 2, 3, 4)]


def test_scroll_is_reachable_and_reaches_the_existing_primitive(monkeypatch):
    recorder = Recorder()
    action = _wired(ScrollPointerAction, monkeypatch, recorder)
    assert action.run({"application": "chrome", "x": 1, "y": 2, "amount": -3}).success
    assert recorder.calls == [("scroll", 1, 2, -3)]


def test_drag_and_scroll_refuse_non_numeric_coordinates():
    context = DesktopContext()
    assert DragPointerAction(context).validate(
        {"application": "chrome", "x1": "a", "y1": 2, "x2": 3, "y2": 4})
    assert ScrollPointerAction(context).validate(
        {"application": "chrome", "x": 1, "y": 2, "amount": "lots"})


# ---- the whole roster is accounted for ----------------------------------


def test_every_mouse_gesture_is_public_or_deliberately_internal():
    """`move()` is the one primitive with no capability, on purpose.

    Nothing in the current interaction semantics needs a bare pointer move:
    click, drag and scroll each position the pointer themselves, and
    `write_text`'s focus fallback uses it internally. Exposing it would add
    a capability whose only use is to leave the pointer somewhere.
    """
    public = {c.name for c in DESKTOP_INTERACTION_ACTION_CLASSES}
    assert {"desktop_click", "desktop_drag", "desktop_scroll"} <= public

    gestures = {name for name in vars(MouseController)
                if not name.startswith("_")}
    assert gestures == {"move", "click", "double_click", "multi_click",
                        "right_click", "drag", "scroll"}, (
        "a new mouse primitive appeared; account for it here as public or "
        "deliberately internal"
    )


def test_the_planner_sees_the_optional_click_arguments():
    from master_agent.capabilities.extraction import contracts_from_actions

    contract = contracts_from_actions(
        {"desktop_click": ClickControlAction(DesktopContext())},
        "desktop",
        lambda executive, local: f"{executive}.{local}",
    )[0]
    fields = {f.name for f in contract.inputs.fields}
    assert {"button", "click_count"} <= fields
    assert contract.inputs.closed is True, "no '(others may exist)' regression"
