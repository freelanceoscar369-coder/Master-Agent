# Filesystem Capabilities

Status: Added 2026-07-23 — Miracle 005, Local Executor Expansion

Design document for turning the Filesystem Plugin from "one folder, one
file, one composite" into a real toolbox of local filesystem operations —
required before any of this Miracle's code was written, per its explicit
design-first gate. `ARCHITECTURE.md` §4.7 has the short summary; this
file is the detail, in the same relationship `MEMORY_ARCHITECTURE.md` has
to §4.8.

## 1. Why capabilities are individual Actions

Every filesystem operation Master Agent can perform — read a file, list a
directory, rename something, delete something — is its own `Action`
class: its own `name`, its own `validate()`, its own `run()`, registered
individually on the `LocalExecutor`. Not one `FileManagerAction` with an
`operation` parameter switching between `"read"`/`"write"`/`"delete"`/etc.

This isn't a style preference. A single `FileManagerAction` would mean:
one `risk_tier` for every operation it handles (so reading a file and
deleting a folder would need the same permission gate — wrong, deleting
needs to be strictly harder to approve than reading), one `validate()`
with a branch per operation (the exact "long if/else chain" this
Miracle's brief explicitly warns against, just moved from
`FilesystemPlugin` into the Action instead), and one class that every
future filesystem capability has to be squeezed into or that has to grow
a new branch. Individual Actions mean each operation's risk tier,
validation, and behavior is declared once, in one small file, and adding
capability #50 means writing a new file, not editing an existing one to
add a 50th branch.

## 2. Why Actions remain atomic

Every Action in this Miracle does exactly one filesystem operation:
`ReadFileAction` reads, it does not also check existence first and branch
on the result: `DeleteFileAction` deletes a file and refuses to touch a
directory (`DeleteFolderAction` is the one that handles directories) —
it does not try to be clever about "delete this path, whatever it turns
out to be." `RenameFileAction` only renames within the same directory; it
does not also move across directories (`MoveFileAction` does that).

Atomicity here means "one Action, one clearly-scoped effect," not
database-transaction atomicity (see §7 for where composites still don't
get rollback). The payoff: each Action's `validate()`/`run()` stays small
enough to read completely in one sitting, each Action's risk tier is
unambiguous (a rename is reversible; there's no version of `RenameFileAction`
that's secretly sometimes a delete), and each Action can be tested,
reused, and reasoned about independently. An Action that tries to do two
things is really two Actions wearing one name — split it before it ships,
not after it's grown a third thing.

## 3. Why composition is preferred over large Actions

`WorkspaceBootstrapAction` (Mission Brief 003) is still the model: a
composite Action that orchestrates primitive Actions *through the real
`LocalExecutor.execute()` path* — never by calling another Action's
`run()` directly — so every sub-step stays independently validated,
permission-gated, and logged (`docs/adr/0006-composite-action-relay.md`).
This Miracle adds eleven new primitives specifically so future composites
have more to build from without inventing new business logic: an
"archive and clear a folder" composite could be built entirely from
`CopyFileAction` + `DeleteFolderAction`, once one is actually needed — not
built speculatively now, since nothing in this Miracle's brief asks for
it (see §9 — no new composite ships in this Miracle, on purpose).

The alternative — one large `Action` that does "bootstrap a project, but
also handle deletion, but also handle renames" — fails the moment a
mission needs a *different* combination of the same primitives. Small
primitives compose into arbitrarily many future combinations; a large
Action only ever does the combination it was written for.

## 4. Future capability growth

Filesystem capabilities alone are not the ceiling — `ARCHITECTURE.md`'s
original list also names shell commands, git operations, VS Code
operations, Obsidian operations, each a candidate for its own plugin
built the same way this one is. What this Miracle's design commits to,
so that growth doesn't require a rewrite:

- **Adding action #12 (or #200) never means editing an existing Action.**
  Each is its own file, its own class, registered once.
- **Adding action #12 never means editing `PermissionSystem`.** Every new
  Action declares a `risk_tier` from the three that already exist
  (`READ_ONLY`/`REVERSIBLE_WRITE`/`IRREVERSIBLE`) and a `permission_category`
  from the five that already exist (§6) — both closed, pre-existing
  vocabularies, not something each new Action invents its own value for.
- **Adding action #12 never means editing `FilesystemPlugin`'s dispatch
  logic.** §5 covers this — registration is a loop over a declared list of
  Action classes, and `invoke()` resolves whatever's registered instead of
  checking a hand-maintained allow-list.
- **A capability category this plugin doesn't own yet** (running a shell
  command, a git operation) is a new plugin over a new Executor-registered
  Action family, following the exact same shape — not a reason to grow
  `FilesystemPlugin` itself into something it isn't. "Filesystem" stays
  the boundary of what this plugin knows about.

## 5. Permission strategy

Two axes, kept deliberately separate because they answer different
questions:

- **`RiskTier`** (`plugins/base.py`, unchanged enum: `READ_ONLY` /
  `REVERSIBLE_WRITE` / `IRREVERSIBLE`) answers "does this need a human
  approval before it runs, and can it be undone." This is the axis
  `PermissionSystem.check()` actually gates on — mechanism, not label.
- **`PermissionCategory`** (`plugins/base.py`, new, alongside `RiskTier`:
  `READ` / `WRITE` / `MODIFY` / `DELETE` / `SYSTEM`) answers "what kind of
  thing is this, in terms a human approving it would recognize." It's a
  classification attached to every `Action` and mirrored onto its
  `CapabilityManifest` entry, used today to make approval prompts and
  Memory records say "this is a Delete" rather than a generic "this will
  modify your filesystem" for every write-shaped action alike.
  `SYSTEM` has no Action using it yet (no shell/process capability exists
  in this Miracle) — it's reserved the same way Memory's Layers 4-6 are
  reserved: the vocabulary exists ahead of the capability that will need
  it, so that capability doesn't have to invent it later.

Every new Action maps onto both axes:

| Category | Risk tier | Actions |
|---|---|---|
| Read | `READ_ONLY` | `ReadFileAction`, `ListDirectoryAction`, `SearchFilesAction`, `FileExistsAction`, `DirectoryExistsAction` |
| Write | `REVERSIBLE_WRITE` | `WriteFileAction` (existing), `AppendFileAction` |
| Modify | `REVERSIBLE_WRITE` | `RenameFileAction`, `CopyFileAction`, `MoveFileAction` |
| Delete | `IRREVERSIBLE` | `DeleteFileAction`, `DeleteFolderAction` |

Read actions never prompt for approval at all — `PermissionSystem.check()`
already short-circuits `READ_ONLY` unconditionally, unchanged by this
Miracle. Rename/Copy/Move are `REVERSIBLE_WRITE`, the same tier
`create_folder`/`write_file` already use — they can be undone (move it
back, delete the copy, rename it back), so the existing grant machinery
(`ONCE`/`THIS_SESSION`/`ALWAYS_FOR_CAPABILITY`) applies to them exactly as
it does today.

**"Destructive Actions MUST require higher permission levels" — the real
mechanism, not just a label.** `PermissionSystem.check()` gains one new
rule: an `ALWAYS_FOR_CAPABILITY` grant never satisfies a check for an
`IRREVERSIBLE`-tier action — only `ONCE` or `THIS_SESSION` can. Nothing
in this codebase currently offers a human the option to grant
`ALWAYS_FOR_CAPABILITY` (every live approval flow in `cli.py` only ever
grants `ONCE`), so this rule is defensive today — but it's real
enforcement inside `PermissionSystem` itself, not a convention callers
have to remember, so a future "remember my choice" UI checkbox literally
cannot create a standing blanket approval for `delete_file`/`delete_folder`
no matter how it's wired. This is the same shape as the existing
`READ_ONLY` short-circuit: one small, permanent rule inside `check()`,
not a policy scattered across call sites. Full reasoning and options
considered: `docs/adr/0009-permission-category-and-irreversible-grant-rule.md`.

## 6. Security

Every new Action validates the same four things the brief requires,
using machinery that already exists rather than inventing new checks per
Action:

- **Path traversal.** Every path-shaped parameter (`path`, `new_name`,
  `destination`, search `pattern`) is checked with the existing
  `is_unsafe_relative_path()` (`executor/action.py`, unchanged, reused —
  not reimplemented) — rejects absolute paths and any `..` segment.
- **Invalid paths.** Empty/whitespace-only names, non-string content
  where a string is required, and structurally malformed payloads
  (e.g. `folders`/`files` not being lists — pattern already established
  by `WorkspaceBootstrapAction`) are all rejected in `validate()`, before
  the filesystem or the Permission System is ever touched — the existing
  contract (`Action.validate()` "must never touch the filesystem or
  perform side effects").
- **Overwrite behaviour.** `RenameFileAction`/`CopyFileAction`/`MoveFileAction`
  refuse to clobber an existing destination by default — the operation
  fails with a structured error rather than silently replacing something —
  unless the payload explicitly sets `"overwrite": true`. This is new
  relative to `WriteFileAction`/`CreateFolderAction`, which have their own
  older, narrower idempotency (identical content = no-op; a folder that's
  already a folder = no-op) that predates this Miracle and isn't changed
  by it. Overwrite protection matters specifically for Rename/Copy/Move
  because clobbering a destination there discards a *different* file
  entirely, not just re-writes the same one.
- **Dangerous destinations.** Every location this plugin can touch comes
  from a small, developer-configured `locations: dict[str, Path]` map
  (`{"desktop": ..., "downloads": ..., "documents": ...}` by default,
  same injection pattern every existing Action already uses). Combined
  with the traversal check above, there is no payload shape that can name
  a path outside one of these roots — "dangerous destination" isn't a
  separate blocklist to maintain, it's a consequence of the sandboxing
  model already in place. `DeleteFolderAction` additionally refuses an
  empty or `"."` path, so "delete X" can never resolve to "delete an
  entire location root" even though the traversal check alone already
  makes escaping a root impossible.

## 7. What's still not solved (named honestly, not hidden)

- **No transactional rollback for composites**, unchanged from Mission
  Brief 003 — a composite that fails partway through leaves whatever
  completed, completed. Still deliberate, still flagged.
- **Deep recursive operations aren't specially protected beyond what
  `shutil.rmtree`/`shutil.copy2`/`shutil.move` already do.** Deleting a
  very large folder tree is still one `IRREVERSIBLE` action, same as
  deleting a small one — no separate "this is a big deletion, extra
  confirmation" tier exists. Worth a future Miracle if it becomes a real
  problem; not solved speculatively here.
- **`SearchFilesAction` caps results at 200 matches** and reports whether
  it was capped — chosen over an unbounded scan so a broad pattern over a
  large tree can't hang the CLI. Named as a real limit, not silently
  truncated.

## 8. The scalability question, applied to this design

Before finalizing: would this design still be right at a million
missions, thousands of plugins, hundreds of capabilities, years of
accumulated history?

- **Adding capability #201 through #300** costs one new file each — no
  existing file (`FilesystemPlugin`, `PermissionSystem`, `LocalExecutor`)
  needs to change. That's the whole point of §1 and §4.
- **`PermissionCategory`/`RiskTier` stay two small closed enums**, not a
  growing list — every new capability picks from what already exists.
  If a genuinely new risk shape shows up later (network access, for
  instance), that's a deliberate addition to `RiskTier`, made once, not a
  per-capability decision.
- **`FilesystemPlugin`'s registration loop (§5 of this doc,
  implementation in `plugins/filesystem_plugin.py`) is O(1) code for
  O(n) Actions** — the loop body doesn't get longer as more Actions are
  added, only the declared list does.
- **`PermissionSystem.check()`'s grant lookup remains a scan over
  distinct `(plugin, capability)` grants**, not over mission volume —
  unchanged from `MEMORY_ARCHITECTURE.md`'s scale review of the same
  question; still bounded by how many capabilities are actively
  in-session-approved, not by how many missions have ever run.
- **Where this Miracle deliberately did NOT try to solve something
  ahead of need**: no capability discovery/marketplace mechanism (still
  ADR-0004's accepted Founder Edition tradeoff), no generic
  operation-batching/transaction layer across composites (§7), no
  configurable-at-runtime location roots (still a constructor-injected
  dict — real runtime-configurable roots are a UI/config concern for
  whenever a Desktop UI exists, not a filesystem-capability concern).
  Building any of these now, without a demonstrated need, is exactly the
  premature complexity this question exists to catch.

## 9. Conversation reachability

Not every capability built this Miracle has a conversational phrasing —
that's a deliberate scope decision, not an oversight. `cli.py`'s intent
parser (`docs/MISSION_BRIEF_005.md`) reaches nine of the fourteen
capabilities: `read_file`, `list_directory`, `search_files`,
`rename_file`, `copy_file`, `move_file` (added for symmetry with copy,
not explicitly requested), `delete_file`, `delete_folder`, plus the
pre-existing `create_folder`/`workspace_bootstrap`. `file_exists`,
`directory_exists`, and `append_file` are real, independently tested
Actions (`tests/test_read_actions.py`, `tests/test_write_actions.py`)
with no `cli.py` phrasing yet — the brief's conversation examples didn't
call for them, and per §1's whole argument, adding one is a small,
additive change (one more Action-shaped file already exists; only a
regex/builder pair needs adding to `cli.py`'s `_INTENT_PATTERNS`) whenever
there's a concrete need, not a redesign.

Every one of the nine reachable capabilities is represented in
conversation by a single generic `ParsedActionIntent` dataclass rather
than nine hand-written ones — the same "avoid long if/else chains, design
for many" principle this document applies to `FilesystemPlugin`'s own
registration (§4) applied one layer up, to intent parsing itself.
