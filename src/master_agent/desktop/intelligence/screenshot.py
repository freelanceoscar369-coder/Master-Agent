"""Desktop Intelligence · the first-class screenshot/evidence capability
the gap analysis found missing: `PIL.ImageGrab` was used constantly, this
codebase's own prior missions, but only in ad-hoc, throwaway diagnostic
scripts — never a real Desktop Executive primitive with a stable
interface, a safe-failure contract, and a typed result. This module is
that promotion, nothing more.

**Read-only, structurally.** `ScreenshotBackend` has exactly one method,
and it takes a bounding rectangle and returns raw pixel bytes — there is
no way to reach a click, a keystroke, or any other mutation through this
module's own interface, the same "the parameter simply does not exist"
guarantee `app_knowledge/acquisition.py` already holds for its own
read-only surface.

**Safe failure is the point.** A screenshot is corroborating evidence, not
a required fact — Pillow not being installed, a window that has since
closed, or a permissions failure must never raise past this module into a
caller that only wanted the rest of a `DesktopObservation`. Every capture
attempt, success or failure, becomes a `ScreenshotEvidence` value; nothing
here raises for an *ordinary* capture failure.
"""
from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Protocol

from master_agent.desktop.intelligence.models import ScreenshotEvidence

SOURCE = "ScreenshotCapture"


class ScreenshotUnavailable(RuntimeError):
    """This backend cannot capture anything right now — Pillow not
    installed, the platform grab call failed, or the target rectangle is
    degenerate. Callers of `capture_screenshot()` never see this
    exception directly; it is caught and turned into a
    `ScreenshotEvidence(captured=False, ...)`."""


@dataclass(frozen=True)
class _RawImage:
    """The minimal shape this module needs back from a backend — width,
    height, and a `save(path)` callable — so `screenshot.py` never
    imports Pillow types directly outside `Win32ScreenshotBackend` itself,
    the same boundary `execution/win32_backends.py`'s own module docstring
    already draws around its one platform-specific dependency."""

    width: int
    height: int
    save: Callable[[str], None]


class ScreenshotBackend(Protocol):
    def capture(self, bounds: tuple[int, int, int, int]) -> _RawImage: ...


class NullScreenshotBackend:
    """Reports honestly that it cannot capture anything — never
    fabricates a blank image. The default for any environment that has
    not explicitly wired a real backend in."""

    def capture(self, bounds: tuple[int, int, int, int]) -> _RawImage:
        raise ScreenshotUnavailable("no screenshot backend is configured")


class Win32ScreenshotBackend:
    """`PIL.ImageGrab.grab(bbox=...)` — the exact mechanism this
    codebase's own prior missions already used ad hoc (see this module's
    own docstring), now behind a stable, typed, read-only interface.
    Pillow is imported lazily, at construction, so a machine without it
    installed fails once, clearly, at the point a caller opted into
    screenshots — not at import time for every consumer of this package,
    most of whom never touch this class at all."""

    def __init__(self) -> None:
        try:
            from PIL import ImageGrab
        except ImportError as exc:  # pragma: no cover — exercised only when Pillow is absent
            raise ScreenshotUnavailable(f"Pillow (PIL.ImageGrab) is not installed: {exc}") from exc
        self._grab = ImageGrab

    def capture(self, bounds: tuple[int, int, int, int]) -> _RawImage:
        left, top, right, bottom = bounds
        if right <= left or bottom <= top:
            raise ScreenshotUnavailable(f"degenerate capture bounds {bounds!r}")
        try:
            image = self._grab.grab(bbox=(left, top, right, bottom))
        except Exception as exc:  # noqa: BLE001 — any platform grab failure is a safe, reported failure
            raise ScreenshotUnavailable(f"ImageGrab.grab() failed for bounds {bounds!r}: {exc}") from exc
        return _RawImage(width=image.width, height=image.height, save=image.save)


def capture_screenshot(
    backend: ScreenshotBackend,
    *,
    window_handle: int,
    application: str,
    bounds: tuple[int, int, int, int],
    dest_dir: Path,
    now: datetime,
) -> ScreenshotEvidence:
    """Capture one screenshot of `bounds` and write it under `dest_dir`,
    returning a `ScreenshotEvidence` describing what happened either way.
    Never raises: `ScreenshotUnavailable` (missing backend, closed
    window, degenerate bounds) and any unexpected filesystem error while
    writing the file are both caught here and turned into
    `captured=False` with a human-readable `reason` — the same
    "structured failure, not an exception the caller must catch"
    contract every other Desktop Executive primitive already holds."""
    try:
        image = backend.capture(bounds)
    except ScreenshotUnavailable as exc:
        return ScreenshotEvidence(
            captured=False, path=None, width=None, height=None,
            window_handle=window_handle, application=application,
            reason=str(exc), source=SOURCE, timestamp=now,
        )

    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{application or 'window'}-{window_handle}-{int(time.time())}-{uuid.uuid4().hex[:8]}.png"
        path = dest_dir / filename
        image.save(str(path))
    except OSError as exc:
        return ScreenshotEvidence(
            captured=False, path=None, width=image.width, height=image.height,
            window_handle=window_handle, application=application,
            reason=f"screenshot was captured but could not be written to disk: {exc}",
            source=SOURCE, timestamp=now,
        )

    return ScreenshotEvidence(
        captured=True, path=str(path), width=image.width, height=image.height,
        window_handle=window_handle, application=application,
        reason="captured successfully", source=SOURCE, timestamp=now,
    )


def default_evidence_dir() -> Path:
    """Where a caller that does not care to choose its own location
    should write evidence screenshots — mirrors
    `uia_control.py`'s own `_GEN_DIR` convention (a writable,
    per-founder-account cache location, never the package's own install
    directory, which a normal install has no guarantee of write access
    to)."""
    return Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "Kalpavriksha" / "desktop_intelligence_evidence"
