"""Glyph sets, and why there are two.

The first smoke run of MB026 crashed with `UnicodeEncodeError` on a
Windows console: the default code page (cp1252) cannot encode the
box-drawing and block characters the frame is built from. A dashboard
that cannot render on the founder's own terminal is not a dashboard.

So rendering is parameterised by a `Charset`, and the default is chosen by
*asking the output stream what it can encode* rather than guessing from
the platform name -- a Windows terminal running UTF-8 gets the nice
glyphs, and a cp1252 one gets readable ASCII instead of a traceback.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Charset:
    rule: str
    sub_rule: str
    bar_full: str
    bar_empty: str
    unavailable: str
    warning: str
    # MB029 founder glyphs. Same rule as the rest: chosen by asking the
    # stream, never by guessing -- the brief's mock uses check marks and
    # block bars a cp1252 console cannot encode.
    ok: str = "+"
    missing: str = "x"
    running: str = "~"
    pending: str = "!"
    healthy: str = "*"


UNICODE = Charset(
    rule="─",
    sub_rule="·",
    bar_full="█",
    bar_empty="░",
    unavailable="—",
    warning="!",
    ok="✓",
    missing="✗",
    running="⏳",
    pending="⚠",
    healthy="●",
)

ASCII = Charset(
    rule="-",
    sub_rule=".",
    bar_full="#",
    bar_empty=".",
    unavailable="-",
    warning="!",
)


def stream_supports(charset: Charset, stream: Any = None) -> bool:
    """Can this stream actually encode these glyphs? Asked, not assumed."""
    stream = stream if stream is not None else sys.stdout
    encoding = getattr(stream, "encoding", None) or "ascii"
    probe = (
        charset.rule
        + charset.bar_full
        + charset.bar_empty
        + charset.unavailable
        + charset.ok
        + charset.missing
        + charset.running
        + charset.pending
        + charset.healthy
    )
    try:
        probe.encode(encoding)
    except (UnicodeEncodeError, LookupError):
        return False
    return True


def detect(stream: Any = None) -> Charset:
    return UNICODE if stream_supports(UNICODE, stream) else ASCII
