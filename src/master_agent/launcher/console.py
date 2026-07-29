"""The Founder Console (Mission Brief 028.1).

One terminal that both shows the Dashboard and takes founder decisions.

**Why this is not in `dashboard/`.** ADR-0016 makes the Dashboard
read-only *structurally*: panels receive a frozen snapshot and return
strings, so a panel physically cannot mutate what it observes. Putting
command handling there would give the Dashboard a live Mission Control
and undo that property. So the split is:

    dashboard/   renders the queue          (pure, read-only, unchanged)
    console.py   reads keys, calls Mission Control  (composition root)

The Approval panel prints `[A]pprove N` because that is what the founder
should type -- the panel has no way to act on it. The console does the
acting, through Mission Control's published contract, which is the same
door any other caller uses. ADR-0016 is preserved intact; see ADR-0020.

**Why one render loop, not two writers.** A background render thread and
a blocking `input()` fight over the terminal: the frame redraws over
whatever is half-typed. Instead there is exactly one writer -- this loop
-- which polls for keystrokes between frames and echoes the command line
as part of the frame it draws. That is also why the panel's hints are
single letters: `A`/`R`/`D` are what a poll-driven console can offer
without a full TUI library.
"""
from __future__ import annotations

import sys
import time
from typing import Any, Self

PROMPT = "  > "
HELP = (
    "  commands: approve N | reject N | defer N | approve all | help | quit"
)


class NullKeyReader:
    """No interactive terminal (a pipe, a test, a CI run). Polls nothing,
    so the console renders and never blocks -- which is exactly what a
    non-interactive run should do."""

    interactive = False

    def poll(self) -> str | None:
        return None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_exc: object) -> None:
        return None


class WindowsKeyReader:
    interactive = True

    def __init__(self) -> None:
        import msvcrt

        self._msvcrt = msvcrt

    def poll(self) -> str | None:
        if not self._msvcrt.kbhit():
            return None
        char = self._msvcrt.getwch()
        # Arrow keys and function keys arrive as a two-character prefix;
        # swallow the second half rather than treating it as input.
        if char in ("\x00", "\xe0"):
            self._msvcrt.getwch()
            return None
        return char

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_exc: object) -> None:
        return None


class PosixKeyReader:
    interactive = True

    def __init__(self) -> None:
        import termios
        import tty

        self._termios = termios
        self._tty = tty
        self._fd = sys.stdin.fileno()
        self._saved: Any = None

    def __enter__(self) -> Self:
        self._saved = self._termios.tcgetattr(self._fd)
        self._tty.setcbreak(self._fd)
        return self

    def __exit__(self, *_exc: object) -> None:
        if self._saved is not None:
            self._termios.tcsetattr(self._fd, self._termios.TCSADRAIN, self._saved)

    def poll(self) -> str | None:
        import select

        ready, _, _ = select.select([sys.stdin], [], [], 0)
        if not ready:
            return None
        return sys.stdin.read(1)


def key_reader() -> Any:
    """The right reader for this terminal, or a null one if there isn't a
    terminal. Chosen by asking the stream, not by guessing the platform --
    the same discipline MB026 used for charset selection, and the reason
    `kalpavriksha | tee log.txt` does not crash."""
    if not sys.stdin.isatty():
        return NullKeyReader()
    try:
        if sys.platform == "win32":
            return WindowsKeyReader()
        return PosixKeyReader()
    except Exception:  # noqa: BLE001 - no raw input available is not fatal
        return NullKeyReader()


class FounderConsole:
    """Renders the Dashboard and executes founder decisions against
    Mission Control. Owns no policy: every command is a call to a
    published Mission Control method."""

    def __init__(
        self,
        dashboard: Any,
        mission_control: Any,
        founder: str = "founder",
        refresh_seconds: float = 1.0,
        reader: Any = None,
        writer: Any = None,
        sleep: Any = None,
    ) -> None:
        self._dashboard = dashboard
        self._mc = mission_control
        self._founder = founder
        self._refresh = refresh_seconds
        self._reader = reader
        self._write = writer or (lambda text: print(text, end="", flush=True))
        self._sleep = sleep or time.sleep
        self._buffer = ""
        self._message = ""
        self._stopped = False

    # ---- commands -----------------------------------------------------

    def execute(self, line: str) -> str:
        """Run one founder command and return the message to display.

        Never raises: a typo at 22:13 must not take down the console the
        founder is using to stop something irreversible.
        """
        command = line.strip().lower()
        if not command:
            return ""
        if command in ("quit", "exit", "q"):
            self._stopped = True
            return "stopping"
        if command in ("help", "?"):
            return HELP.strip()

        parts = command.split()
        verb, args = parts[0], parts[1:]
        actions = {
            "approve": self._mc.approve,
            "a": self._mc.approve,
            "reject": self._mc.reject,
            "r": self._mc.reject,
            "defer": self._mc.defer,
            "d": self._mc.defer,
        }
        action = actions.get(verb)
        if action is None:
            return f"unknown command '{verb}' - type help"
        if not args:
            return f"{verb} which? e.g. '{verb} 1'"

        if args[0] == "all":
            return self._apply_all(verb, action)
        return self._apply_one(verb, action, args[0])

    def _apply_one(self, verb: str, action: Any, token: str) -> str:
        try:
            index = int(token)
        except ValueError:
            return f"'{token}' is not an approval number"
        try:
            approval = self._mc.approvals.by_index(index)
        except Exception as exc:  # noqa: BLE001 - a bad number is a message
            return str(exc)
        try:
            action(approval.approval_id, self._founder)
        except Exception as exc:  # noqa: BLE001
            return f"could not {verb}: {exc}"
        return f"{verb}d [{index}] {approval.capability}"

    def _apply_all(self, verb: str, action: Any) -> str:
        """`approve all` resolves against a *snapshot* of the queue taken
        before the first decision, because deciding changes what is open
        and iterating a shifting list would skip entries."""
        targets = list(self._mc.approvals.open())
        if not targets:
            return "nothing pending"
        failures = 0
        for approval in targets:
            try:
                action(approval.approval_id, self._founder)
            except Exception:  # noqa: BLE001 - keep going; report the count
                failures += 1
        done = len(targets) - failures
        suffix = f", {failures} failed" if failures else ""
        return f"{verb}d {done} approval(s){suffix}"

    # ---- loop ---------------------------------------------------------

    def render_once(self) -> str:
        frame = self._dashboard.render()
        pending = self._mc.approvals.open()
        footer = [""]
        if self._message:
            footer.append(f"  {self._message}")
        if pending:
            footer.append(HELP)
        footer.append(f"{PROMPT}{self._buffer}")
        text = frame + "\n" + "\n".join(footer)
        self._write("\033[2J\033[H" + text)
        return text

    def feed(self, char: str) -> None:
        """One keystroke. Enter runs the buffer; backspace edits it."""
        if char in ("\r", "\n"):
            self._message = self.execute(self._buffer)
            self._buffer = ""
            return
        if char in ("\x7f", "\b"):
            self._buffer = self._buffer[:-1]
            return
        if char == "\x03":  # Ctrl-C
            self._stopped = True
            return
        if char.isprintable():
            self._buffer += char

    @property
    def stopped(self) -> bool:
        return self._stopped

    def run(self, max_frames: int | None = None) -> None:
        reader = self._reader if self._reader is not None else key_reader()
        frames = 0
        with reader:
            while not self._stopped:
                if max_frames is not None and frames >= max_frames:
                    break
                self.render_once()
                frames += 1
                if not getattr(reader, "interactive", False):
                    # No terminal: render on the interval and never poll.
                    self._sleep(self._refresh)
                    continue
                # Poll for the whole refresh window in small slices, so a
                # keystroke is echoed immediately rather than up to a
                # second later -- which is what makes typing feel like
                # typing rather than like a form submission.
                deadline = self._refresh
                while deadline > 0 and not self._stopped:
                    char = reader.poll()
                    if char is not None:
                        self.feed(char)
                        break
                    self._sleep(0.05)
                    deadline -= 0.05
