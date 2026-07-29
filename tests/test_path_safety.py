"""Cross-platform path safety regression tests (Mission Brief 023.1).

The sandbox boundary must behave identically regardless of which OS the
process happens to run on. Before this Miracle it did not: the guard used
the host's native path flavour, so `/etc/passwd` and `D:config` -- both
root/drive-anchored, neither a safe relative path -- were accepted on
Windows and rejected on POSIX.

Every case below is asserted against the *string*, not against a
host-flavoured Path, so this file makes the same assertions and catches
the same regressions on either platform.
"""
from __future__ import annotations

import pytest

from master_agent.executor.action import is_unsafe_relative_path, to_portable_relative_str
from master_agent.executor.actions.rename_file import RenameFileAction
from master_agent.executor.actions.search_files import SearchFilesAction

# Paths that must be rejected on every platform. Each entry is (path, why).
UNSAFE_PATHS = [
    ("/etc/passwd", "POSIX-absolute -- is_absolute() is False on Windows"),
    ("/", "bare POSIX root"),
    ("//server/share", "POSIX-style network root"),
    ("C:/Windows/system32", "Windows-absolute with forward slashes"),
    ("C:\\Windows\\system32", "Windows-absolute with backslashes"),
    ("D:config", "drive-relative -- is_absolute() is False even on Windows"),
    ("\\\\server\\share", "UNC path"),
    ("\\Windows", "Windows root-relative"),
    ("../escape", "parent traversal, POSIX separator"),
    ("..\\escape", "parent traversal, Windows separator"),
    ("sub/../../escape", "traversal buried mid-path"),
    ("sub\\..\\..\\escape", "traversal buried mid-path, Windows separator"),
    ("..", "bare parent"),
    ("", "empty"),
    ("   ", "whitespace only"),
]

SAFE_PATHS = [
    "Demo",
    "Demo/README.md",
    "Demo\\README.md",
    "a/b/c/d.txt",
    "file.with.dots.txt",
    "spaces in name.txt",
    ".hidden",
    "sub/.hidden",
]


@pytest.mark.parametrize("path,reason", UNSAFE_PATHS, ids=[p for p, _ in UNSAFE_PATHS])
def test_unsafe_paths_are_rejected_on_every_platform(path: str, reason: str):
    assert is_unsafe_relative_path(path) is True, f"should have been rejected ({reason})"


@pytest.mark.parametrize("path", SAFE_PATHS)
def test_ordinary_relative_paths_are_still_accepted(path: str):
    assert is_unsafe_relative_path(path) is False


def test_non_string_input_is_rejected_rather_than_crashing():
    """validate() runs before anything else touches a payload, so a
    malformed type must fail closed, not raise."""
    for value in (None, 123, [], {}, object()):
        assert is_unsafe_relative_path(value) is True  # type: ignore[arg-type]


def test_the_guard_does_not_depend_on_the_host_platform():
    """The regression this Miracle exists to prevent: a boundary that is
    stricter on one OS than another is not a boundary."""
    windows_shaped = ["C:\\Windows", "D:config", "\\\\server\\share", "..\\escape"]
    posix_shaped = ["/etc/passwd", "//server/share", "../escape"]
    for path in windows_shaped + posix_shaped:
        assert is_unsafe_relative_path(path) is True, (
            f"{path!r} must be rejected regardless of which OS is running the check"
        )


# ---- sandbox boundary, exercised through a real Action ------------------


def test_write_file_action_refuses_a_posix_absolute_path_on_any_host(tmp_path):
    from master_agent.executor.actions.write_file import WriteFileAction

    action = WriteFileAction({"desktop": tmp_path})
    errors = action.validate({"path": "/etc/passwd", "content": "x"})
    assert any("unsafe path" in error for error in errors)


def test_write_file_action_refuses_a_drive_relative_path(tmp_path):
    from master_agent.executor.actions.write_file import WriteFileAction

    action = WriteFileAction({"desktop": tmp_path})
    errors = action.validate({"path": "D:config", "content": "x"})
    assert any("unsafe path" in error for error in errors)


def test_create_folder_action_refuses_traversal_in_either_separator(tmp_path):
    from master_agent.executor.actions.create_folder import CreateFolderAction

    action = CreateFolderAction({"desktop": tmp_path})
    for name in ("../escape", "..\\escape"):
        assert action.validate({"name": name}), f"{name!r} should have been refused"


def test_traversal_is_refused_through_the_real_executor_path(tmp_path):
    """The sandbox boundary as it actually exists: LocalExecutor.execute()
    always calls validate() before run() (the Action contract), so a
    traversal payload never reaches the filesystem on any supported path.
    This asserts the guarantee end to end rather than through validate()
    alone."""
    from master_agent.executor.actions.write_file import WriteFileAction
    from master_agent.executor.executor import LocalExecutor
    from master_agent.permissions.permission_system import GrantScope, PermissionSystem

    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    permissions = PermissionSystem()
    executor = LocalExecutor(permissions)
    executor.register(WriteFileAction({"desktop": sandbox}))
    permissions.grant(executor.name, "write_file", GrantScope.ONCE)

    result = executor.execute("write_file", {"path": "../outside.txt", "content": "nope"})

    assert not result.success
    assert any("unsafe path" in error for error in result.errors)
    assert not (tmp_path / "outside.txt").exists()


def test_run_alone_is_not_a_second_boundary_and_this_is_known(tmp_path):
    """Documents a real limit found while verifying the sandbox for
    Mission Brief 023.1, rather than leaving it as an unstated assumption:
    `run()` trusts that `validate()` already passed (the Action contract
    says so explicitly), so calling `run()` directly -- bypassing the
    Executor -- is a contract violation by the caller, not a boundary the
    action re-checks.

    Asserted here as current, deliberate behaviour so that if a future
    Miracle adds containment checking inside `run()` (defence in depth),
    this test fails and forces the change to be acknowledged rather than
    landing silently. See docs/MISSION_BRIEF_023_1.md."""
    from master_agent.executor.actions.write_file import WriteFileAction

    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    action = WriteFileAction({"desktop": sandbox})

    result = action.run({"path": "../outside.txt", "content": "written"})

    assert result.success, (
        "run() currently trusts validate(); if this now fails, defence-in-depth "
        "was added -- update this test and MISSION_BRIEF_023_1.md together"
    )
    (tmp_path / "outside.txt").unlink(missing_ok=True)


# ---- portable output ----------------------------------------------------


def test_search_results_use_forward_slashes_on_every_platform(tmp_path):
    """Search output is persisted into mission history; native separators
    would make the same mission compare unequal across machines."""
    (tmp_path / "sub").mkdir()
    (tmp_path / "a.pdf").write_text("")
    (tmp_path / "sub" / "b.pdf").write_text("")

    action = SearchFilesAction({"desktop": tmp_path})
    result = action.run({"pattern": "*.pdf"})

    assert result.success
    assert sorted(result.output["matches"]) == ["a.pdf", "sub/b.pdf"]
    assert all("\\" not in match for match in result.output["matches"])


def test_to_portable_relative_str_is_platform_independent(tmp_path):
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    target = nested / "c.txt"
    target.write_text("")
    assert to_portable_relative_str(target, tmp_path) == "a/b/c.txt"


# ---- overwrite semantics ------------------------------------------------


def test_rename_with_overwrite_replaces_the_destination_on_every_platform(tmp_path):
    """Path.rename() raises on Windows when the destination exists but
    silently replaces on POSIX -- which made `overwrite: true` mean two
    different things. Path.replace() is the atomic overwrite on both."""
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.txt").write_text("b")
    action = RenameFileAction({"desktop": tmp_path})

    result = action.run({"path": "a.txt", "new_name": "b.txt", "overwrite": True})

    assert result.success, result.errors
    assert (tmp_path / "b.txt").read_text() == "a"
    assert not (tmp_path / "a.txt").exists()


def test_rename_without_overwrite_still_refuses_to_clobber(tmp_path):
    """The overwrite *guard* is unchanged -- only the allowed case was
    made consistent across platforms."""
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.txt").write_text("b")
    action = RenameFileAction({"desktop": tmp_path})

    result = action.run({"path": "a.txt", "new_name": "b.txt"})

    assert not result.success
    assert (tmp_path / "b.txt").read_text() == "b"
    assert (tmp_path / "a.txt").exists()
