# Mission Brief 003 — Workspace Bootstrap Action

Status: Implemented (2026-07-23)

## Objective

Mission Brief 002 proved the Executor + Action Contract generalizes past
`create_folder`. This brief proved something more specific and more
important: that a *composite* mission — one that needs several local
operations to happen together — can be built entirely by **reusing**
smaller actions, without ever bypassing the Executor or the Permission
System to do it. Constraints given: don't bypass the Executor, don't
bypass the Permission System, build the composite from smaller reusable
actions rather than a hardcoded "create project" script.

## Architecture summary

Two new Actions under `src/master_agent/executor/actions/`:

- **`WriteFileAction`** (`write_file.py`) — the second filesystem
  primitive, alongside `create_folder`. Writes text content to a file
  under a known location, creating missing parent directories, with the
  same idempotent-with-warning behavior `CreateFolderAction` established
  (unchanged content → no-op with a warning; different content →
  overwrite with a warning).
- **`WorkspaceBootstrapAction`** (`workspace_bootstrap.py`) — a
  **composite** action. It creates a root folder, then any requested
  subfolders and seed files under it. It does not touch the filesystem
  itself — it's parameterized by `name`/`folders`/`files`, so it's a
  reusable "stand up a workspace" primitive, not a hardcoded script for
  one specific project layout.

The composite's `run()` invokes `create_folder` and `write_file` the same
way any other caller would: through `self._executor.execute(action_name,
payload)`. Before each call, it relays a fresh `ONCE` grant to that
sub-action's own grant key — the same pattern `FilesystemPlugin.invoke()`
uses to relay the Orchestrator's approval down to the Executor
(ADR-0005), now applied one layer deeper, because here it's an Action
relaying to itself rather than a Plugin relaying to an Executor. Full
reasoning, options considered, and the honest cost of this pattern:
`docs/adr/0006-composite-action-relay.md`.

```
Orchestrator → FilesystemPlugin.invoke("workspace_bootstrap")
                 → relay grant → LocalExecutor.execute("workspace_bootstrap")
                     → WorkspaceBootstrapAction.run()
                         → relay grant → LocalExecutor.execute("create_folder")  [× N]
                         → relay grant → LocalExecutor.execute("write_file")     [× N]
```

Every arrow above is a real `LocalExecutor.execute()` call — validated,
permission-checked, logged. Nothing in this chain calls an `Action.run()`
method directly except the Executor itself.

**A closed gap, not new scope creep:** while composing `create_folder`
calls with programmatically-generated multi-segment names (e.g.
`"MyProject/src"`), it became clear `CreateFolderAction.validate()` never
rejected `..` path-traversal segments — safe in Mission Brief 001/002
because `name` only ever came from a single user-typed folder name, but
no longer safe once a composite can generate that value. Added the same
traversal guard `WriteFileAction`/`WorkspaceBootstrapAction` already
needed (a shared `is_unsafe_relative_path()` helper in `action.py`) to
`CreateFolderAction` too, so the guard protects every caller regardless
of which path reaches it.

## Files changed

**New:**
- `src/master_agent/executor/actions/write_file.py` — `WriteFileAction`
- `src/master_agent/executor/actions/workspace_bootstrap.py` —
  `WorkspaceBootstrapAction`
- `docs/adr/0006-composite-action-relay.md`
- `docs/MISSION_BRIEF_003.md` (this file)
- `tests/test_write_file_action.py`
- `tests/test_workspace_bootstrap_action.py`

**Modified:**
- `src/master_agent/executor/action.py` — added `is_unsafe_relative_path()`,
  a shared helper used by all three filesystem actions
- `src/master_agent/executor/actions/create_folder.py` — added the same
  traversal guard (see "A closed gap" above); no other behavior change
- `src/master_agent/plugins/filesystem_plugin.py` — registers all three
  actions on the injected executor; manifest now declares three
  capabilities; `invoke()` generalized from a single hardcoded capability
  check to a small supported-capability set (the relay/execute lines were
  already generic, unchanged)
- `tests/test_filesystem_plugin.py` — new tests for the two additional
  capabilities; existing `create_folder` tests unchanged

**Unchanged (verified, not assumed):**
- `src/master_agent/executor/executor.py`
- `src/master_agent/orchestrator/orchestrator.py`
- `src/master_agent/permissions/permission_system.py`
- `tests/test_executor.py`, `tests/test_create_folder_action.py`,
  `tests/test_cli_session.py`, `tests/test_plugin_registry.py`

## Tests added

35 new tests across two new files, plus additions to an existing one:

- `tests/test_write_file_action.py` (14 tests) — the same
  validate()/run() coverage style as `test_create_folder_action.py`:
  missing/unsafe path, non-string content, unknown location, default
  location, nested-parent-directory auto-creation, idempotent no-op on
  identical content, overwrite-with-warning on different content, failure
  when the target path is a directory.
- `tests/test_workspace_bootstrap_action.py` (16 tests) — contract shape;
  `validate()` coverage (missing name, unsafe name/folder/file paths,
  malformed folders/files, and confirmation `validate()` never touches
  the filesystem); full composition through a real `LocalExecutor` +
  `PermissionSystem` (root + subfolders + files created correctly, only
  one human approval needed for the whole composite, every sub-step
  individually present in the Executor's log); permission denied at the
  top blocks every sub-step (nothing created, one log entry); partial
  failure stops at the failing step, reports exactly what completed, and
  does **not** roll back what already succeeded; re-running the same
  bootstrap is idempotent.
- `tests/test_filesystem_plugin.py` (+6 tests) — manifest now declares
  all three capabilities; `write_file` delegation and error translation;
  `workspace_bootstrap` delegation, confirming the plugin only relays
  ONE grant yet every sub-step still shows up in the log (proof the
  composite is relaying its own grants internally, invisibly to the
  Plugin layer); repeat invocation doesn't ask twice.

## Test results

```
76 passed in 0.19s
```

(41 from Mission Brief 002 + 35 new; all passing on the same run, no
regressions.)

## Ruff results

```
All checks passed!
```

## Live verification

Ran a `workspace_bootstrap` mission through `FilesystemPlugin.invoke()`
(the same entry point the Orchestrator uses) against a sandboxed temp
directory, with exactly one grant issued
(`plugin.manifest.name` / `workspace_bootstrap`):

```
success: True
output: {'root': '.../DemoProject',
         'created_folders': ['.../DemoProject', '.../DemoProject/src',
                              '.../DemoProject/docs', '.../DemoProject/tests'],
         'written_files': ['.../DemoProject/README.md',
                            '.../DemoProject/docs/NOTES.md']}
--- executor log ---
  create_folder        status=success  duration=0.000092s
  create_folder        status=success  duration=0.000055s
  create_folder        status=success  duration=0.000049s
  create_folder        status=success  duration=0.000047s
  write_file           status=success  duration=0.000118s
  write_file           status=success  duration=0.000140s
  workspace_bootstrap  status=success  duration=0.000880s
```

Seven real, independently-logged Executor calls from one human approval,
and the filesystem matched exactly what was asked for.

## Technical debt introduced

1. **The relay pattern now has two hand-written instances** —
   `FilesystemPlugin.invoke()` (ADR-0005) and
   `WorkspaceBootstrapAction._run_substep()` (ADR-0006) — both convention,
   not something the type system enforces. Two examples make a stronger
   case for extracting a shared `LocalExecutor.execute_relayed()`-style
   helper than Mission Brief 002's one example did, but "do not
   over-engineer" still applies until a third instance shows up. Flagged
   in both `ARCHITECTURE.md` §6 and ADR-0006.
2. **No transactional rollback in composite actions.** If step 3 of 5
   fails, steps 1–2 stay done. `WorkspaceBootstrapAction`'s result reports
   exactly what completed before the failure (`output["completed_before_failure"]`),
   but nothing undoes it. Acceptable for `create_folder`/`write_file`
   (both idempotent, both safe to leave half-done and re-run), but this
   won't hold for every future primitive — worth a real design (staged
   commit, compensating actions) before a composite ever includes an
   `IRREVERSIBLE` sub-step.
3. **`WorkspaceBootstrapAction`'s risk tier is a manual promise, not a
   derived value.** It's hardcoded to `REVERSIBLE_WRITE` because that's
   the ceiling of what it currently composes. Nothing checks that this
   stays true if a future sub-step with a higher risk tier gets added to
   its `run()` — noted as a rule in ADR-0006, not enforced by code.
4. Carried over from Mission Brief 002, still true: `LocalExecutor`'s
   grant namespace is shared per executor instance, and `ApprovalRequired`
   is a plain `Exception` a broad `except Exception` could theoretically
   swallow (still not currently triggered by anything).

## Remaining stubs

Every local capability besides `create_folder`, `write_file`, and
`workspace_bootstrap` (read/rename/delete/copy/move file, run
PowerShell/CMD, git operations, VS Code operations, Obsidian operations)
— all cheap to add as either a primitive or a composite now, none built.
**Deliberately out of scope for this brief:** no new CLI/conversational
command was added to `cli.py` for `workspace_bootstrap` — this brief was
about proving actions compose safely through the Executor and Permission
System, not about shipping a new user-facing mission. Wiring a real
intent (Planner or a rule-based parser like Mission Brief 001's) to this
capability is natural follow-up work, not done here. Planner, Mission
Manager persistence, Model Router wiring to live providers, Memory
persistence, Voice I/O, Desktop UI remain exactly as described in
`docs/MISSION_BRIEF_001.md`.

## Recommendation for Mission Brief 004

Two candidates, in order of what teaches the architecture more:

1. **Wire `workspace_bootstrap` to a real intent.** Extend `cli.py`'s
   rule-based parser (or, if the Planner is ready to be more than a stub,
   start there instead) so a founder can actually trigger this mission by
   typing/saying something like "set up a new project called X with
   src/docs/tests folders." This is the first time a mission would need
   the Planner to produce a payload with real structure (a `folders` list,
   a `files` list) rather than the single flat `{name, location}` payload
   every mission so far has used — worth doing deliberately rather than
   leaving `workspace_bootstrap` permanently unreachable from outside a
   test file.
2. **Add the third relay instance** (a git-operations plugin/action, or a
   `delete_file`/`RunPowerShell` action) specifically to settle whether
   ADR-0005/0006's flagged base-class extraction is worth building now —
   two examples said "not yet," a third might say "yes."
