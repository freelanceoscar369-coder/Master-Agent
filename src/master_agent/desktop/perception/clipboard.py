"""C27 · Clipboard Status — read-only, over C26's `ClipboardExecutive`.

`DesktopState` needs to know *whether the clipboard holds something*, not
what — reporting the actual text would make every `DesktopState` a
capture of whatever a founder last copied, which is exactly the kind of
private content this brief's Browser Observer is told to stay out of,
applied here to the clipboard instead. Only `ClipboardExecutive.read()`
(C26) is ever called; `write()`/`clear()` never appear."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from master_agent.desktop.execution.clipboard import ClipboardExecutive
from master_agent.desktop.perception.evidence import (
    Confidence,
    Observation,
    unknown_observation,
)

SOURCE = "ClipboardExecutive.read()"


@dataclass(frozen=True)
class ClipboardStatus:
    has_content: Observation
    """`.value` is `bool` — never the clipboard's actual text."""

    length: Observation
    """`.value` is `int | None` — the character count, a size fact, not
    the content itself."""

    timestamp: datetime

    def as_dict(self) -> dict[str, Any]:
        return {
            "has_content": self.has_content.as_dict(),
            "length": self.length.as_dict(),
            "timestamp": self.timestamp.isoformat(),
        }


class ClipboardObserver:
    __slots__ = ("_clipboard",)

    def __init__(self, clipboard: ClipboardExecutive | None = None) -> None:
        self._clipboard = clipboard or ClipboardExecutive()

    def observe(self, timestamp: datetime) -> ClipboardStatus:
        result = self._clipboard.read()
        if not result.success:
            failed = unknown_observation(
                reason="; ".join(result.errors) or "clipboard read failed",
                source=SOURCE, timestamp=timestamp,
            )
            return ClipboardStatus(has_content=failed, length=failed, timestamp=timestamp)

        text = result.output["text"]
        has_content = Observation(
            value=text is not None, confidence=Confidence.OBSERVED,
            reason="clipboard holds text" if text is not None else "clipboard is empty",
            source=SOURCE, timestamp=timestamp,
        )
        length_value = len(text) if text is not None else 0
        length = Observation(
            value=length_value, confidence=Confidence.OBSERVED,
            reason=(
                f"{length_value} character(s) on the clipboard" if text is not None
                else "clipboard is empty"
            ),
            source=SOURCE, timestamp=timestamp,
        )
        return ClipboardStatus(has_content=has_content, length=length, timestamp=timestamp)
