"""Regression coverage for two real bugs found only by live-exercising
`Win32ClipboardBackend` against the actual system clipboard this session —
`test_desktop_execution.py`'s own fakes-only suite cannot catch either,
since both are specific to the real Win32 marshaling layer:

1. `GetClipboardData`/`GlobalLock`/`GlobalAlloc` return real 64-bit
   pointers on x64 Windows; without an explicit `restype`, ctypes
   truncates them to 32 bits, and the first real read crashed with an
   access-violation `OSError`.
2. The Clipboard History / Cloud Clipboard exclusion marker
   (`ExcludeClipboardContentFromMonitorProcessing`) was silently never
   set: `GlobalAlloc(GMEM_MOVEABLE, 0)` returns NULL on this platform, so
   the `if marker:` guard skipped `SetClipboardData` for the exclusion
   format every time.

These touch the real system clipboard (read/write/marker-presence only —
no keyboard, mouse, or window state), a deliberate, narrow exception to
`test_desktop_execution.py`'s own fakes-only scoping, kept in its own file
for that reason.
"""
from __future__ import annotations

from master_agent.desktop.execution.win32_backends import (
    CF_UNICODETEXT,
    CFSTR_EXCLUDE_FROM_MONITOR,
    Win32ClipboardBackend,
    user32,
)


class TestWin32ClipboardBackendLive:
    def test_write_then_read_round_trips_without_crashing(self):
        """Regression for the 64-bit pointer truncation bug: the original
        `restype`-less declarations crashed with an access-violation
        `OSError` on the very first real read."""
        backend = Win32ClipboardBackend()
        text = "win32 clipboard regression check " * 20  # long enough to exercise real allocation

        backend.write(text)
        result = backend.read()

        assert result == text

    def test_write_sets_the_clipboard_history_exclusion_marker(self):
        """Regression for the `GlobalAlloc(..., 0)` bug: the exclusion
        format must actually be present on the clipboard after `write()`,
        not merely attempted."""
        backend = Win32ClipboardBackend()
        backend.write("clipboard history exclusion regression check")

        exclude_format = user32.RegisterClipboardFormatW(CFSTR_EXCLUDE_FROM_MONITOR)
        assert user32.OpenClipboard(0)
        try:
            assert user32.IsClipboardFormatAvailable(exclude_format)
            assert user32.IsClipboardFormatAvailable(CF_UNICODETEXT)
        finally:
            user32.CloseClipboard()
