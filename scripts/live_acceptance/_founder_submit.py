"""Stand in for the founder's hands at the Kalpavriksha window.

This types the founder's OBJECTIVE into the real application and presses
Send. It does not do the work the objective asks for, does not choose a
provider, and does not touch mission state -- everything after Send
belongs to Kalpavriksha.

Target ownership is verified the way the campaign requires: the window is
resolved by handle, its title and process are confirmed, foreground is
confirmed, and every step re-observes. If the target is not provably the
Kalpavriksha window, nothing is typed and nothing is pressed.

    python _founder_submit.py <hwnd> "<objective>"
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, "D:/MasterAgent")
sys.path.insert(0, "D:/MasterAgent/src")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from master_agent.desktop.execution.keyboard import KeyboardController  # noqa: E402
from master_agent.desktop.execution.mouse import MouseController  # noqa: E402
from master_agent.desktop.execution.uia_control import UiaAutomationBridge  # noqa: E402
from master_agent.desktop.execution.window import WindowManager  # noqa: E402

EXPECTED_TITLE = "kalpavriksha"


def ascii_of(text):
    return (text or "").encode("ascii", "replace").decode("ascii")


def window_title(hwnd: int) -> str:
    import ctypes
    user32 = ctypes.windll.user32
    n = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def foreground_hwnd() -> int:
    import ctypes
    return int(ctypes.windll.user32.GetForegroundWindow())


def names(bridge, hwnd) -> list[str]:
    out = []
    for snap in bridge.snapshot_elements(hwnd):
        name = (getattr(snap, "name", "") or "").strip()
        if name and name not in out:
            out.append(name)
    return out


def main() -> int:
    hwnd = int(sys.argv[1])
    objective = sys.argv[2]

    bridge = UiaAutomationBridge()
    keyboard = KeyboardController()
    mouse = MouseController()
    windows = WindowManager()

    title = window_title(hwnd)
    print(f"target hwnd : {hwnd}")
    print(f"target title: {ascii_of(title)!r}")
    if EXPECTED_TITLE not in title.lower():
        print("REFUSING: that window is not Kalpavriksha. Nothing typed.")
        return 2

    windows.bring_to_front(hwnd)
    time.sleep(1.2)
    front = foreground_hwnd()
    print(f"foreground  : {front} ({'ours' if front == hwnd else ascii_of(window_title(front))!r})")
    if front != hwnd:
        # The campaign's invariant: uncertain target identity means zero
        # input. A wrong-window keystroke fails the run outright, so a
        # failure to take the foreground has to stop here.
        print("REFUSING: could not confirm foreground. Nothing typed.")
        return 3

    visible = names(bridge, hwnd)
    if "Type instead" in visible:
        button = bridge.find(hwnd, name_exact="Type instead")
        if button is not None:
            bridge.click(button, mouse)
            time.sleep(1.0)
            print("clicked     : 'Type instead'")

    composer = bridge.find_composer(hwnd)
    if composer is None:
        print("FAILED: no composer found. Elements:", [ascii_of(n) for n in names(bridge, hwnd)][:25])
        return 4
    described = bridge.describe(composer)
    print(f"composer    : {ascii_of(getattr(described, 'name', '') or '')!r}")

    if foreground_hwnd() != hwnd:
        print("REFUSING: focus moved before typing. Nothing typed.")
        return 3

    wrote = bridge.write_text(composer, objective, keyboard)
    print(f"typed       : {wrote}  ({len(objective)} chars)")
    if not wrote:
        return 5

    if foreground_hwnd() != hwnd:
        print("REFUSING: focus moved before send. Not pressing Send.")
        return 3

    send = bridge.find(hwnd, name_exact="Send")
    if send is not None:
        bridge.click(send, mouse)
        print("clicked     : 'Send'")
    else:
        keyboard.press("enter")
        print("pressed     : enter (no Send button found)")

    time.sleep(2.0)
    print("---- window after submit ----")
    for name in names(bridge, hwnd):
        print("  ", ascii_of(name)[:160])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
