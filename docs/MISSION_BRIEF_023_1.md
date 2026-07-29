# Mission Brief 023.1 — Cross-Platform Path Safety

Status: Shipped — 2026-07-26

Parallel maintenance brief raised alongside Mission Brief 023, and
deliberately kept out of it: the nervous system was the mission, this is
tracked-and-completed work that must not distract from it. Shipped as its
own commit, after MB023 was committed and sealed.

## Objective

Fix Windows/POSIX path normalization, harden `is_unsafe_relative_path()`,
add regression tests, and verify sandbox boundary behavior.

## What was actually wrong

Three genuine cross-platform defects, not five cosmetic test failures.
Each had been visible as a failing test since before Mission Brief 022,
consistently reported as pre-existing rather than quietly ignored.

**1. The sandbox guard was weaker on Windows than on POSIX.**
`is_unsafe_relative_path()` used `Path(...)` — whichever flavour the
*host* happens to be — and rejected on `is_absolute()`. On Windows:

```
PureWindowsPath("/etc/passwd").is_absolute()  ->  False
PureWindowsPath("D:config").is_absolute()     ->  False
```

Both are root- or drive-anchored and neither is a safe relative path, but
the old check accepted them on Windows. Separator handling had the mirror
problem on POSIX: `PurePosixPath("..\\escape").parts` is one opaque
segment, so a backslash traversal was invisible there.

This is the substantive finding of this brief: **a sandbox boundary that
depends on which OS you happen to run is not a boundary.** The fix checks
the string against *both* path flavours and rejects on `anchor` (which
catches drive- and root-relative forms) rather than only `is_absolute()`.

**2. `overwrite: true` meant two different things on two platforms.**
`Path.rename()` raises on Windows when the destination exists, but
silently replaces on POSIX. `RenameFileAction` used it, so an explicitly
requested overwrite worked on one platform and failed on the other.
Replaced with `Path.replace()`, the atomic overwrite on both. The
overwrite *guard* is unchanged — only the allowed case was made
consistent.

**3. Search results leaked the host's native separator into persisted
history.** `SearchFilesAction` returned `sub\b.pdf` on Windows and
`sub/b.pdf` on POSIX. That output travels into an `ExecutionResult`, then
a persisted `MissionRecord`, and eventually Evidence a future Planner
reads — so the same mission recorded on two machines would not compare
equal. Added `to_portable_relative_str()`, which renders forward slashes
everywhere (and remains valid input back into `Path()` on Windows).

## Sandbox boundary verification — and one thing it revealed

The brief asked to *verify* sandbox boundary behavior, not just fix the
guard. Doing so surfaced a limit worth stating plainly:

**`run()` is not a second boundary.** It trusts that `validate()` already
passed — which the `Action` contract states explicitly, and which
`LocalExecutor.execute()` always honors. So on every supported path a
traversal payload is refused before touching the filesystem
(`test_traversal_is_refused_through_the_real_executor_path` asserts this
end to end through the real Executor). But calling `Action.run()`
directly, bypassing the Executor, is a caller contract violation that the
action does not re-check.

That is current, deliberate behaviour, and it is now pinned by a test
(`test_run_alone_is_not_a_second_boundary_and_this_is_known`) that fails
if defence-in-depth is ever added — forcing the change to be acknowledged
rather than landing silently. Adding containment checking inside `run()`
across all fourteen filesystem actions would be genuine defence in depth
and is a reasonable future Miracle; it was **not** done here, because this
brief was explicitly scoped as secondary maintenance and a fourteen-file
change is exactly the distraction it was told not to become. Named here
rather than hidden.

## Files changed

- `src/master_agent/executor/action.py` — hardened
  `is_unsafe_relative_path()`, added `to_portable_relative_str()`
- `src/master_agent/executor/actions/rename_file.py` — `replace()` over
  `rename()`
- `src/master_agent/executor/actions/search_files.py` — portable output
- `tests/test_path_safety.py` — new, 34 tests

No other file was touched. Mission Control (MB023) is untouched by this
brief, and vice versa.

## Testing

**34 new tests; 500 passing overall, 0 failing.** This is the first fully
green run of the suite in this session: the 5 pre-existing failures
(`test_cli_session.py` ×2, `test_modify_actions.py`,
`test_read_actions.py`, `test_write_file_action.py`) are fixed by the
three source changes above, not by adjusting their assertions — every one
of those tests still asserts exactly what it asserted before.

The new tests are written against *strings*, never host-flavoured `Path`
objects, so they make the same assertions and catch the same regressions
on Windows and POSIX alike. Fifteen unsafe shapes (POSIX-absolute, bare
root, UNC, drive-relative, Windows-absolute in both separator styles,
traversal in both separator styles, buried traversal, empty, whitespace)
and eight safe ones are covered explicitly.

`ruff check` on every changed file: All checks passed. (Two pre-existing
`UP017` findings remain in `executor/executor.py`, which this brief did
not modify.)

## Known limitations

- **`run()` has no containment check of its own** — see the verification
  section above. Deliberate, tested, and named.
- **Reserved Windows device names** (`CON`, `NUL`, `COM1`, …) are not
  rejected. They are not path-traversal — they cannot escape the sandbox
  root — but they can produce surprising I/O on Windows. Out of scope
  here; worth a look if a future capability accepts user-supplied
  filenames from an untrusted source.
- **Case-insensitivity and symlink resolution** are not addressed. Neither
  affects the traversal guard, since every path is joined onto a
  configured root; both would matter for a stricter containment model.
