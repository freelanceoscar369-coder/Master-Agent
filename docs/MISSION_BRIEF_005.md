# Mission Brief 005 — Expand Kalpavriksh's Local Execution Capabilities

Status: Implemented (2026-07-23)

## Objective

Turn the Filesystem Plugin from three capabilities into a real toolbox,
without building a Planner, Voice, Model Routing, or introducing AI, and
without any shortcut around the existing architecture: Conversation →
Mission → Permission → Executor → Action → Filesystem, for every one of
the new capabilities, exactly as it already worked for
`create_folder`/`write_file`/`workspace_bootstrap`.

## Design first: FILESYSTEM_CAPABILITIES.md

Written before any code, per the brief's explicit gate. Covers: why each
capability is its own `Action` rather than one operation-switching
`FileManagerAction` (§1); why each Action stays atomic — e.g.
`RenameFileAction` refuses to change directory, `DeleteFileAction` refuses
a directory target (§2); why composition (the `WorkspaceBootstrapAction`
model) is preferred over building speculative new composites this Miracle
didn't need (§3); why adding capability #12 or #200 costs one new file,
never a change to `FilesystemPlugin`'s registration logic (§4); the full
permission-category/risk-tier table for all fourteen capabilities (§5);
security — path traversal, invalid paths, overwrite behavior, dangerous
destinations (§6); what's still not solved, named honestly — no composite
rollback, no special handling for large recursive deletes,
`SearchFilesAction`'s 200-match cap (§7); and the Scalability Question
applied to this Miracle's own design before implementation started (§8).

## What was built

### Eleven new primitive Actions (`executor/actions/`)

**Read (`RiskTier.READ_ONLY` / `PermissionCategory.READ`, no approval
required — ever, per `PermissionSystem.check()`'s pre-existing
short-circuit):** `ReadFileAction`, `ListDirectoryAction`,
`SearchFilesAction`, `FileExistsAction`, `DirectoryExistsAction`.

**Write/Modify (`RiskTier.REVERSIBLE_WRITE`):** `AppendFileAction`
(`PermissionCategory.WRITE`); `RenameFileAction`, `CopyFileAction`,
`MoveFileAction` (`PermissionCategory.MODIFY`).

**Destructive (`RiskTier.IRREVERSIBLE` / `PermissionCategory.DELETE`):**
`DeleteFileAction`, `DeleteFolderAction` — and, per the brief's "MUST
require higher permission levels," these are the first capabilities in
the codebase that a standing `ALWAYS_FOR_CAPABILITY` grant *cannot*
pre-approve; see the Permission Model section below and ADR-0009.

Three small helpers were added to `executor/action.py` and shared across
these (rather than duplicated per-Action, per
`FILESYSTEM_CAPABILITIES.md`'s "never duplicate business logic"):
`default_locations()` (desktop/downloads/documents — consolidates a dict
literal that was previously copy-pasted in every Action's constructor),
`resolve_into_or_as()` (Copy/Move's "into a folder, keeping the filename"
vs. "as a new literal path" resolution — used identically by both),
`resolve_overwrite_error()` (the shared no-clobber-unless-`overwrite:true`
check used by Rename/Copy/Move).

### Permission Model: `PermissionCategory` + a new IRREVERSIBLE rule

Full reasoning: ADR-0009. Summary: `PermissionCategory`
(`READ`/`WRITE`/`MODIFY`/`DELETE`/`SYSTEM`) is a new, purely descriptive
axis alongside the pre-existing `RiskTier` — it answers "what kind of
thing is this" for a human or future UI, and is never consulted by the
actual gating mechanism. `RiskTier` still drives everything
`PermissionSystem.check()` does, plus one new rule: an
`ALWAYS_FOR_CAPABILITY` grant can never satisfy a check for an
`IRREVERSIBLE`-tier capability, no matter how it was created. Destructive
actions genuinely require a fresh decision every time — not just a label
saying they should.

### Plugin registration: declarative, not an if/else chain

`FilesystemPlugin` was rewritten around a single tuple,
`_PRIMITIVE_ACTION_CLASSES`, and a registration loop — adding capability
#15 (or #200) means adding one class to that tuple, never editing
`FilesystemPlugin.__init__`, `.manifest`, or `.invoke()`. Composite
Actions (currently just `WorkspaceBootstrapAction`, which needs the
executor itself injected) are registered separately, by design — primitives
are meant to scale into the hundreds; composites are meant to stay few and
deliberate (`FILESYSTEM_CAPABILITIES.md` §4-5).

### Conversation: cli.py's Intent Parser generalized

Rather than one `ParsedXIntent` dataclass per new capability, a single
generic `ParsedActionIntent` (capability name + payload + title/location/
warning display strings) represents all nine new capabilities reachable
from conversation. Intent parsing itself moved from a growing if/elif
chain to a table (`_INTENT_PATTERNS`) of `(regex, builder)` pairs — the
same "avoid long if/else chains, design for many" principle
`FilesystemPlugin`'s own registration follows. All six of the brief's
conversation examples work end to end, plus "Move" (added for symmetry
with "Copy," not explicitly requested):

- "Read README.md" — executes immediately, no approval (READ_ONLY).
- "List files inside Downloads" — executes immediately, no approval.
- "Search for *.pdf" — executes immediately, no approval.
- "Rename notes.txt to notes_old.txt" — approval required, then renames.
- "Copy config.json to backup folder" — approval required, then copies
  (into the folder, keeping the filename).
- "Move temp.txt to archive folder" — approval required, then moves.
- "Delete temp folder" / "Delete notes.txt" — approval required
  (sharper "cannot be undone" wording), disambiguated from each other by
  a trailing " folder" keyword, checked in plain Python rather than a
  second regex, per "prefer simplicity over cleverness."

`file_exists`/`directory_exists`/`append_file` are real, tested
capabilities with no conversational phrasing yet — not required by the
brief's examples, and the toolbox is intentionally allowed to be bigger
than any one conversation needs to reach on day one.

`_extract_artifacts()`/`_record_title()` were generalized to handle the
new capabilities' output shapes for Memory persistence — Read/List/Search
persist with no artifacts (nothing created, modified, or removed);
Rename/Copy/Move persist a `{"type": "file", "path": ...}` artifact;
Delete persists `{"type": "deleted_file"/"deleted_folder", "path": ...}`
— new type strings, no `MissionRecord` schema change needed
(`artifacts` has been a generic list since ADR-0008).

## Security

Every new Action validates path traversal (`is_unsafe_relative_path()` —
rejects absolute paths and `..` segments — reused unchanged from Mission
Brief 002), invalid/missing paths, and unknown locations, exactly like
the two pre-existing Actions. `RenameFileAction`/`CopyFileAction`/
`MoveFileAction` refuse to silently overwrite an existing destination
unless the caller explicitly opts in with `overwrite: true`.
`DeleteFolderAction` refuses an empty or `"."` path (so "delete X" can
never resolve to deleting an entire location root) and carries a
defense-in-depth check that the resolved target is actually inside its
configured location base, even though `validate()` already makes that
structurally guaranteed. Nothing added this Miracle allows execution
outside the configured `locations` roots — see
`FILESYSTEM_CAPABILITIES.md` §6 for the full accounting.

## The Scalability Question, applied

Answered explicitly in `FILESYSTEM_CAPABILITIES.md` §8 before
implementation started: adding a capability costs one new file (O(1) per
capability, not a growing edit to shared code); `PermissionCategory` and
`RiskTier` stay two small, closed enums, not an open-ended taxonomy;
`FilesystemPlugin`'s registration loop is O(1) code regardless of how
many Actions are in the tuple. Deliberately *not* solved without a
demonstrated need: a capability marketplace, a transaction/rollback layer
for composites, or runtime-configurable location roots.

## Files changed

- `FILESYSTEM_CAPABILITIES.md` (new) — full design doc, written first.
- `src/master_agent/plugins/base.py` — `PermissionCategory` enum added;
  `CapabilityManifest.permission_category` field added.
- `src/master_agent/permissions/permission_system.py` — re-exports
  `PermissionCategory`; `check()` gained the IRREVERSIBLE/
  ALWAYS_FOR_CAPABILITY rule (ADR-0009).
- `src/master_agent/executor/action.py` — `permission_category` added to
  the `Action` ABC; `default_locations()`, `resolve_into_or_as()`,
  `resolve_overwrite_error()` added.
- `src/master_agent/executor/actions/create_folder.py`,
  `write_file.py`, `workspace_bootstrap.py` — updated to declare
  `permission_category` and use `default_locations()`.
- `src/master_agent/executor/actions/{read_file,list_directory,
  search_files,file_exists,directory_exists,append_file,rename_file,
  copy_file,move_file,delete_file,delete_folder}.py` (all new) — the
  eleven new primitives.
- `src/master_agent/plugins/filesystem_plugin.py` — rewritten for
  declarative registration; now exposes all fourteen capabilities.
- `src/master_agent/cli.py` — `ParsedActionIntent` (new, generic);
  eight new intent regexes; `_INTENT_PATTERNS` table-driven dispatch
  replacing the if/elif chain; `build_plan()`, `_record_title()`,
  `_extract_artifacts()`, `_approval_message()`, `_finish()` all
  generalized to handle `ParsedActionIntent`; per-capability completion-
  message builders (`_ACTION_COMPLETION_BUILDERS`).
- `docs/adr/0009-permission-category-and-irreversible-grant-rule.md`
  (new).
- `ARCHITECTURE.md`, `PROJECT_BRAIN.md`, `ROADMAP.md`, `DECISIONS.md` —
  updated (see each file's own diff for specifics).
- New test files: `tests/test_read_actions.py`,
  `tests/test_write_actions.py`, `tests/test_modify_actions.py`,
  `tests/test_delete_actions.py`, `tests/test_permission_system.py`
  (first dedicated `PermissionSystem` test module).
- `tests/test_filesystem_plugin.py` — manifest tests updated for
  fourteen capabilities; one unsupported-capability test's example
  capability changed (`delete_folder` is now real).
- `tests/test_cli_session.py` — new Mission Brief 005 section: parse_intent
  coverage for all new shapes, full-session tests for all six
  conversation examples plus Move, permission-denied paths for both
  delete capabilities, overwrite-refusal-through-conversation, and
  Memory-persistence assertions for the new artifact types.

## Tests

108 new tests across six new/updated test files (read/write/modify/
delete action units, permission system, filesystem plugin manifest, CLI
integration) — **234 passed** (up from 126 before this Miracle; zero
regressions across the full suite, including everything every prior
Miracle added).

## Test results

```
234 passed in 0.56s
```

## Ruff results

```
All checks passed!
```

## Live verification

Ran a real `MasterAgentSession` (sandboxed to a `tmp_path` desktop +
downloads pair, real `Orchestrator`/`PermissionSystem`/`LocalExecutor`,
no mocks) through all six of the brief's conversation examples plus
Move, in one live Python process:

- "Read README.md" → returned file content in one turn, no approval
  prompt.
- "List files inside Downloads" → returned folders/files split, no
  approval prompt.
- "Search for *.pdf" → returned matches, no approval prompt (0 matches
  when searching Desktop with the *.pdf file living in Downloads —
  confirms the default-location resolution is real, not a stub).
- "Rename notes.txt to notes_old.txt" → prompted for approval, then
  renamed on "Yes"; file existed under its new name.
- "Copy config.json to backup folder" → prompted for approval, then
  copied into the folder on "Yes"; source file untouched.
- "Delete temp folder" → prompted with the sharper "cannot be undone"
  wording, then deleted the whole subtree on "Yes".
- "What was my last mission?" / "Show me recent missions" → correctly
  reflected every one of the above, newest first.

## Remaining limitations

- `file_exists`/`directory_exists`/`append_file` have no conversational
  phrasing yet — real, tested capabilities, just not reachable from
  `cli.py` today. Adding phrasings for them is a small, additive future
  step (one more `_INTENT_PATTERNS` entry each), not a redesign.
- No composite rollback for multi-step failures — unchanged limitation
  from Mission Brief 003/ADR-0006, not something this Miracle's new
  primitives introduce or fix (none of the eleven new Actions are
  composites).
- `SearchFilesAction` caps results at 200 matches and reports
  `truncated: true` rather than paginating — a deliberate, named
  simplification (`FILESYSTEM_CAPABILITIES.md` §7), not a hidden one.
- `LocalExecutor._log` remains an unbounded in-memory list — flagged in
  Mission Brief 004.1, still not fixed (still out of scope for this
  Miracle; still on `ROADMAP.md`).
- `cli.py`'s intent parser is still a rule-based stand-in for the real
  Planner, unchanged in kind by this Miracle — it now recognizes more
  shapes, but the fundamental gap (no model call, no clarification loop
  for ambiguous phrasing) is exactly what Miracle 006 is expected to
  close.
- The standing `D:\MasterAgent` gap: no session in this project's history
  has had the Claude desktop device bridge connected, so none of this
  Miracle's work has been verified or written to the founder's actual
  local machine — only to this session's cloud staging copy, packaged
  and delivered as a zip. See `START_HERE.md` for the transfer steps this
  still requires.

## Recommendation for Miracle 006

The toolbox is now real and reachable from conversation — the next
highest-leverage step is the real Planner (unchanged recommendation from
Mission Brief 004.1, now with more surface area to prove itself against:
fourteen capabilities and nine distinct conversational shapes instead of
three and two). A model-driven Planner replacing `parse_intent()`/
`build_plan()` would also be the natural point to finally handle phrasing
`cli.py`'s regexes can't — ambiguous requests, capabilities without a
wired phrasing yet (`file_exists`, `append_file`, ...), and multi-step
requests spanning more than one capability in a single sentence. Worth
verifying against the full `test_cli_session.py` suite (now 100+
assertions deep) before intent recognition changes shape again — that
suite is the regression contract this next Miracle must not break.
