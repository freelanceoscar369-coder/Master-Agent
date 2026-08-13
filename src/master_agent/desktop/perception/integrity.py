"""Desktop Executive Foundation 1.0 — the integrity/UIPI boundary.

*"Determine whether Kalpavriksha is lower than target; whether target is
elevated/admin."* Windows enforces this itself (User Interface Privilege
Isolation: a lower-integrity process's window messages are silently
dropped by a higher-integrity one — `SendInput`/`PostMessageW` land on an
elevated window and nothing happens, with no error raised anywhere). This
module's whole job is turning that silent drop into a fact reported
*before* an action is attempted, not a mystery after one fails for no
visible reason.

**Read-only, like `win32_probe.py` beside it.** No token is adjusted, no
privilege is enabled, no elevation is requested or bypassed — the two
Win32 calls here (`OpenProcessToken`, `GetTokenInformation`) only ever
read what a process already has. `ctypes` only, no `pywin32`, the same
isolation `execution/win32_backends.py`'s own module docstring explains
(a platform-detection failure here fails one import, never the
package's).
"""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from dataclasses import dataclass
from typing import Protocol

#: Windows' own four-level scale (there are more SIDs than this in
#: principle; these are the ones a desktop process actually reports).
UNKNOWN = "unknown"
LOW = "low"
MEDIUM = "medium"
HIGH = "high"
SYSTEM = "system"

_LEVEL_BY_RID = {
    0x1000: LOW,
    0x2000: MEDIUM,
    0x3000: HIGH,
    0x4000: SYSTEM,
}

#: Ordering for "is target higher than me" — a plain rank, not a claim
#: about what a level can do beyond what Windows itself already enforces.
_RANK = {UNKNOWN: -1, LOW: 0, MEDIUM: 1, HIGH: 2, SYSTEM: 3}


class IntegrityUnavailable(RuntimeError):
    """This probe cannot run here — wrong platform, or the process
    handle/token could not be opened. Never raised for an ordinary
    "integrity level determined" result, including `UNKNOWN`, which is a
    valid answer when Windows itself would not say."""


@dataclass(frozen=True)
class IntegrityInfo:
    level: str
    is_elevated: bool


class IntegrityBackend(Protocol):
    def integrity_of_process(self, pid: int) -> IntegrityInfo: ...

    def integrity_of_self(self) -> IntegrityInfo: ...


class NullIntegrityBackend:
    """Reports honestly that it cannot say — never guesses a level."""

    def integrity_of_process(self, pid: int) -> IntegrityInfo:
        raise IntegrityUnavailable("no integrity backend is configured")

    def integrity_of_self(self) -> IntegrityInfo:
        raise IntegrityUnavailable("no integrity backend is configured")


class Win32IntegrityBackend:
    """`OpenProcessToken` + `GetTokenInformation(TokenIntegrityLevel)` —
    the documented mechanism for reading a process's own integrity SID.
    Elevation (`is_elevated`) is read the same way, via
    `TokenElevation`."""

    _TOKEN_QUERY = 0x0008
    _TOKEN_INTEGRITY_LEVEL = 25
    _TOKEN_ELEVATION = 20
    _PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise IntegrityUnavailable(
                "the Win32 integrity backend is only available on Windows"
            )
        self._advapi32 = ctypes.windll.advapi32
        self._kernel32 = ctypes.windll.kernel32
        # ctypes' default `restype` is a 32-bit `c_int` — silently
        # truncating/misinterpreting a 64-bit `HANDLE` (`GetCurrentProcess`
        # returns the pseudo-handle -1, i.e. all bits set). Every function
        # here that returns or takes a HANDLE/DWORD needs its real type
        # declared explicitly; a wrong default is not a load-time error,
        # it is a call that "succeeds" against garbage.
        self._kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        self._kernel32.OpenProcess.restype = wintypes.HANDLE
        self._kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self._kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        self._advapi32.OpenProcessToken.argtypes = [
            wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE),
        ]
        self._advapi32.GetTokenInformation.argtypes = [
            wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
        ]

    def integrity_of_self(self) -> IntegrityInfo:
        return self._integrity_of_handle(self._kernel32.GetCurrentProcess())

    def integrity_of_process(self, pid: int) -> IntegrityInfo:
        handle = self._kernel32.OpenProcess(
            self._PROCESS_QUERY_LIMITED_INFORMATION, False, pid
        )
        if not handle:
            raise IntegrityUnavailable(
                f"could not open process {pid} (access denied, or it has exited)"
            )
        try:
            return self._integrity_of_handle(handle)
        finally:
            self._kernel32.CloseHandle(handle)

    def _integrity_of_handle(self, process_handle: int) -> IntegrityInfo:
        token = wintypes.HANDLE()
        if not self._advapi32.OpenProcessToken(
            process_handle, self._TOKEN_QUERY, ctypes.byref(token)
        ):
            raise IntegrityUnavailable("could not open the process token")
        try:
            level = self._read_integrity_level(token)
            elevated = self._read_elevation(token)
            return IntegrityInfo(level=level, is_elevated=elevated)
        finally:
            self._kernel32.CloseHandle(token)

    def _read_integrity_level(self, token: wintypes.HANDLE) -> str:
        size = wintypes.DWORD(0)
        # First call establishes the required buffer size (documented
        # `GetTokenInformation` two-call pattern) — the initial failure is
        # expected, not an error.
        self._advapi32.GetTokenInformation(token, self._TOKEN_INTEGRITY_LEVEL, None, 0, ctypes.byref(size))
        if size.value == 0:
            return UNKNOWN
        buffer = ctypes.create_string_buffer(size.value)
        if not self._advapi32.GetTokenInformation(
            token, self._TOKEN_INTEGRITY_LEVEL, buffer, size.value, ctypes.byref(size)
        ):
            return UNKNOWN
        # TOKEN_MANDATORY_LABEL: one SID pointer at the head of the buffer.
        sid_ptr = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_void_p))[0]
        if not sid_ptr:
            return UNKNOWN
        rid_count = ctypes.cast(
            sid_ptr + 1, ctypes.POINTER(ctypes.c_ubyte)
        )[0]
        if rid_count == 0:
            return UNKNOWN
        # The integrity RID is the last sub-authority in the SID.
        rid_ptr = ctypes.cast(
            sid_ptr + 8 + 4 * (rid_count - 1), ctypes.POINTER(wintypes.DWORD)
        )
        rid = rid_ptr[0] & 0xFFFFF000
        return _LEVEL_BY_RID.get(rid, UNKNOWN)

    def _read_elevation(self, token: wintypes.HANDLE) -> bool:
        elevation = wintypes.DWORD(0)
        size = wintypes.DWORD(ctypes.sizeof(elevation))
        ok = self._advapi32.GetTokenInformation(
            token, self._TOKEN_ELEVATION, ctypes.byref(elevation),
            size, ctypes.byref(size),
        )
        return bool(ok) and bool(elevation.value)


#: Structured conditions `IntegrityGuard.check()` can return — the same
#: "carried fact, never an exception the caller has to guess the shape
#: of" discipline every other module in this package uses.
PERMISSION_BOUNDARY = "permission_boundary"
ELEVATION_REQUIRED = "elevation_required"
INACCESSIBLE_TARGET = "inaccessible_target"
CLEAR = "clear"


@dataclass(frozen=True)
class IntegrityCheck:
    condition: str
    detail: str
    self_level: str = UNKNOWN
    target_level: str = UNKNOWN

    @property
    def blocked(self) -> bool:
        return self.condition != CLEAR


class IntegrityGuard:
    """Detects a UIPI boundary before an action crosses it. Never grants
    elevation, never bypasses UAC, never touches a secure desktop —
    reports the boundary and stops; the existing Permission System is
    where a founder-visible approval, if any is even possible, would come
    from (this module does not call it, and does not need to: an
    elevated target is inaccessible to this process regardless of any
    approval, because UIPI is enforced by Windows itself, not by
    Kalpavriksha)."""

    def __init__(self, backend: IntegrityBackend | None = None) -> None:
        self._backend = backend or NullIntegrityBackend()

    def check(self, target_pid: int) -> IntegrityCheck:
        try:
            mine = self._backend.integrity_of_self()
        except IntegrityUnavailable as exc:
            return IntegrityCheck(INACCESSIBLE_TARGET, f"cannot determine own integrity level: {exc}")

        try:
            theirs = self._backend.integrity_of_process(target_pid)
        except IntegrityUnavailable as exc:
            return IntegrityCheck(
                INACCESSIBLE_TARGET,
                f"cannot determine target process {target_pid}'s integrity level: {exc}",
                self_level=mine.level,
            )

        if theirs.is_elevated and not mine.is_elevated:
            return IntegrityCheck(
                ELEVATION_REQUIRED,
                (
                    f"process {target_pid} is running elevated; this process is "
                    "not, and Windows (UIPI) will silently drop input sent to it"
                ),
                self_level=mine.level, target_level=theirs.level,
            )

        if _RANK.get(theirs.level, -1) > _RANK.get(mine.level, -1):
            return IntegrityCheck(
                PERMISSION_BOUNDARY,
                (
                    f"process {target_pid} runs at a higher integrity level "
                    f"({theirs.level}) than this process ({mine.level})"
                ),
                self_level=mine.level, target_level=theirs.level,
            )

        return IntegrityCheck(CLEAR, "no integrity boundary detected", mine.level, theirs.level)
