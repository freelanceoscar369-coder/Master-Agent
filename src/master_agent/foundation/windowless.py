"""Run a helper process without flashing a console window at the founder.

Kalpavriksha probes the machine constantly -- which applications are
installed, which are running, what the desktop looks like. Every one of
those probes is `subprocess.run(..., capture_output=True)`, and on Windows
each spawn of a console executable creates a console window. It exists for
milliseconds and is drawn anyway, so a founder sitting in front of a
"local, quiet" application sees black rectangles blink across their screen
while nothing they asked for is happening.

`CREATE_NO_WINDOW` is the Windows flag for exactly this: the process runs,
its stdout is still captured, and no console is allocated.

## What this deliberately does not cover

**Launching an application the founder asked for.** `DesktopProbe.start()`
opens VS Code because a founder said "open VS Code", and hiding that would
be hiding the thing they requested. This constant is for processes the
founder never asked to see -- the ones whose output Kalpavriksha reads
itself. The distinction is `capture_output`: if the parent reads the
result, the founder does not need the window.

Zero on non-Windows, where the flag does not exist and no console is
created in the first place.
"""
from __future__ import annotations

import subprocess
import sys

#: Passed as `creationflags=` to a probe spawn. `0` everywhere but
#: Windows, so call sites need no platform branch of their own.
NO_WINDOW: int = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
