"""LOCAL / AI MODE / BOTH — the founder's operating mode.

The three modes are not new. They are the founder's own vocabulary, and
they already exist as three buttons on the founder surface
(`desktop_app/web/index.html`, `data-mode="local|ai_mode|both"`) wired to
a `set_mode` bridge call. What went missing is the other end: the shell
method those buttons call was dropped from
`src/master_agent/founder_edition/desktop_shell.py` while surviving in
the stale `build/lib/` copy, and the page swallows the failure
(`Bridge.call('set_mode', mode).catch(() => null)`). So the buttons have
been inert, every session running as BOTH by default and BOTH itself
never meaning anything.

## What they mean

| Mode | Meaning |
|---|---|
| `LOCAL` | Local capabilities only. No reasoning provider is contacted, for any reason. |
| `AI_MODE` | The founder is asking for reasoning. Go to the Model Router. |
| `BOTH` | **Local-first.** Deterministic when the registered capabilities already settle it; reasoning only when they do not. |

BOTH has never meant "local *and* every AI provider". It means: can the
local capabilities solve this completely and safely? Yes → local. No →
reasoning.

## Where the decision is made, and why not where it used to be

The historical implementation made this decision in the composition root,
by matching prose (`text.startswith("open ")` in `_try_action`) before
the Brain was consulted at all. That is the exact shape ADR-0024 and the
capability-question fix removed: a routing decision in the wrong layer,
keyed on substrings, invisible to the Intent Layer that owns meaning.

It lives in the Planner instead, because the question BOTH asks — *can
the registered capabilities achieve this without reasoning?* — is the
Planner's own question, and the Planner is already the only component
allowed to answer it.
"""
from __future__ import annotations

from typing import Any

LOCAL = "local"
AI_MODE = "ai_mode"
BOTH = "both"

#: Closed, like every other vocabulary in this codebase. `ai_tools` is
#: accepted as an alias because the historical shell accepted it and the
#: founder surface may still send it.
MODES = (LOCAL, AI_MODE, BOTH)
_ALIASES = {"ai_tools": AI_MODE, "ai": AI_MODE, "local_only": LOCAL}

#: What applies when nobody has chosen. The founder surface itself sets
#: BOTH at boot; this matches so a missing switch behaves identically to
#: an untouched one.
DEFAULT_MODE = BOTH


def normalise(mode: Any) -> str:
    """Any founder-supplied spelling to one of `MODES`.

    Unknown values fall back to `DEFAULT_MODE` rather than raising: a
    surface sending an unrecognised string is a bug worth fixing, but it
    must not stop a founder getting work done, and BOTH is the mode that
    can still do everything.
    """
    if not isinstance(mode, str):
        return DEFAULT_MODE
    lowered = mode.strip().lower()
    lowered = _ALIASES.get(lowered, lowered)
    return lowered if lowered in MODES else DEFAULT_MODE


def resolve_mode(mode: Any) -> str:
    """Read a mode that may be a string, a callable, or absent.

    Callable because the founder flips the switch mid-session while the
    Planner is built once at boot: holding the value would freeze whatever
    was set the moment the process started.
    """
    if callable(mode):
        try:
            mode = mode()
        except Exception:  # noqa: BLE001 — an unreadable switch is BOTH, not a crash
            return DEFAULT_MODE
    return normalise(mode)
