"""Elite Desktop Executive — execution substrate (C26).

```
   DesktopExecutor.execute() / .focus() / .type() / .click() / .wait() / .close()
              │  every call checked against a C25 profile first
              ▼
   WindowManager · KeyboardController · MouseController · ClipboardExecutive
   ProcessExecutive (extends desktop/actions.py)  ·  BrowserExecutive (extends the Browser Worker)
              │
              ▼
   Win32*Backend (ctypes)  ·  BrowserSessionManager (Playwright)  ·  existing SystemProbe
```

**Execution, not intelligence.** This package performs exactly what it is
asked — launch, focus, type, click, wait, close — and decides nothing
about *what* to do or *which* application to use; those questions belong
to `desktop.operations` (C25) and to Kalpavriksha, neither of which is
built or extended here. No OCR, no vision, no image recognition, no
install/uninstall, no privilege elevation, no registry, no password or
conversation inspection — see `permissions.py` for the brief's own two
lists, reproduced as data a test checks mechanically.

**Read before trusting the real backend:** `win32_backends.py`'s own
module docstring, and `Engineering/HEALTH_C26.md` §11, both state plainly
that live keyboard/mouse/window-close execution was not exercised against
a real desktop in the session that built this package — only window
enumeration (read-only) was.
"""
from __future__ import annotations

from master_agent.desktop.execution.backends import (
    BackendUnavailable,
    ClipboardBackend,
    KeyboardBackend,
    MouseBackend,
    NullClipboardBackend,
    NullKeyboardBackend,
    NullMouseBackend,
    NullWindowBackend,
    WindowBackend,
    WindowInfo,
)
from master_agent.desktop.execution.browser import BrowserExecutive, BrowserUnavailable
from master_agent.desktop.execution.clipboard import ClipboardExecutive
from master_agent.desktop.execution.executor import DesktopExecutor
from master_agent.desktop.execution.keyboard import KeyboardController
from master_agent.desktop.execution.mouse import MouseController
from master_agent.desktop.execution.permissions import (
    FORBIDDEN_METHOD_NAMES,
    FORBIDDEN_OPERATIONS,
    PERMITTED_OPERATIONS,
)
from master_agent.desktop.execution.process import ProcessExecutive
from master_agent.desktop.execution.window import WindowManager

__all__ = [
    "FORBIDDEN_METHOD_NAMES",
    "FORBIDDEN_OPERATIONS",
    "PERMITTED_OPERATIONS",
    "BackendUnavailable",
    "BrowserExecutive",
    "BrowserUnavailable",
    "ClipboardBackend",
    "ClipboardExecutive",
    "DesktopExecutor",
    "KeyboardBackend",
    "KeyboardController",
    "MouseBackend",
    "MouseController",
    "NullClipboardBackend",
    "NullKeyboardBackend",
    "NullMouseBackend",
    "NullWindowBackend",
    "ProcessExecutive",
    "WindowBackend",
    "WindowInfo",
    "WindowManager",
]
