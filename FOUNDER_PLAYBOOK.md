# Founder Playbook

Status: Frozen (2026-07-23) — Miracle 003.5, Foundation Freeze

How development actually happens on this project — not aspirational
process, the process every Miracle from 001 through 003.5 has already
followed. A future contributor (human or AI) should be able to pick up a
new Miracle brief and know exactly what's expected, end to end, from
this document alone.

## The Miracle workflow

A "Miracle" (also called a Mission Brief) is the unit of work on this
project — always scoped narrower than "implement everything," always
delivered as a complete, tested, documented, committed increment. The
shape, every time:

1. **A brief arrives** stating an objective, explicit exclusions ("out
   of scope"), and often an architecture constraint (e.g. "do not bypass
   the Executor"). If the brief is ambiguous about scope, narrow rather
   than widen — every Miracle so far has stayed deliberately smaller than
   its brief could have been read to allow.
2. **Design before code, for anything with a real decision to make.**
   When two parts of the system need to interact in a way that isn't
   obvious (Miracle 002's permission double-check, Miracle 003's
   composite-relay problem), that gets reasoned through and written down
   *before* implementation — as an ADR if it's a real architectural
   choice with rejected alternatives worth recording (`docs/adr/`), or
   inline in the Mission Brief doc if it's smaller. Not after, as
   retroactive justification.
3. **Implement**, honoring `ENGINEERING_PRINCIPLES.md` and
   `ARCHITECTURE_PRINCIPLES.md` throughout — not as a final review pass,
   as the thing guiding each decision while writing the code.
4. **Test.** See Testing Process below — this is not a separate phase
   tacked on at the end, tests are written alongside the feature they
   cover.
5. **Verify manually, at least once, against the real stack.** Every
   Miracle that touches conversational behavior includes a live
   transcript run against a real (sandboxed) filesystem, not just unit
   tests — Miracle 001's transcript, Miracle 003's live `invoke()` trace,
   Miracle 003.1's two live conversations are the pattern. Automated
   tests prove behavior is correct; a manual run proves the demo actually
   works, which is a different and equally necessary claim.
6. **Document.** See Documentation Workflow below.
7. **Commit, tag, package, deliver.** See Git Workflow and Release
   Workflow below.
8. **Report against the brief's deliverable checklist, honestly.** Every
   Miracle's final message answers exactly what was asked for — including
   naming technical debt introduced, stubs still remaining, and an
   honest recommendation for what the next Miracle should be. A Miracle
   is not "done" quietly; it's reported.

## Review process

There is no separate human reviewer in this project's current process —
review is built into the workflow itself, in three specific ways that
have already caught real problems:

- **End-to-end tests are the primary review mechanism.** Miracle 001's
  two bugs and Miracle 003.1's `execution_time_seconds` bug were both
  found this way, not by inspection. If a change can't be exercised
  end-to-end, that's a signal to add the test that would exercise it,
  not to skip review.
- **Regression is checked, not assumed, every time.** Every Miracle runs
  the *complete* suite (not just its own new tests) before being called
  done, and every Mission Brief doc reports the full pass count, not
  just "tests pass." A prior Miracle's tests failing is a blocking
  problem for the current one, full stop.
- **Design decisions with rejected alternatives get written down.** An
  ADR's "Options considered" section is itself a review artifact — it
  makes the reasoning checkable by someone who wasn't in the room (or
  session) when the decision was made. If you can't articulate why the
  obvious alternative was rejected, the decision isn't ready.

## Testing process

- **New business logic gets direct unit tests** against the class/
  function itself, no Executor/Orchestrator/CLI involved —
  `test_create_folder_action.py`, `test_write_file_action.py` are the
  pattern.
- **New integration points get end-to-end tests through the real
  stack**, never mocks for the modules under test — `test_cli_session.py`
  wires a real `PermissionSystem`, real `LocalExecutor`, real
  `Orchestrator`; only the filesystem *location* is sandboxed to
  `tmp_path`.
- **Both the happy path and the refusal paths are tested**: permission
  denied, invalid input, partial failure. A feature isn't tested until
  its failure modes are, not just its success case — see
  `test_workspace_bootstrap_action.py`'s partial-failure-no-rollback test
  as the reference example.
- **Regression tests are never modified to make a new Miracle pass.** If
  a change breaks an existing test, the change is wrong or the test's
  premise has genuinely changed and that's worth its own explanation —
  it isn't fixed by loosening the assertion.
- **Every Miracle reports:** the exact `pytest` pass count, and `ruff
  check .` output, verbatim, in its deliverable. Not "tests pass" as
  prose — the actual numbers, so they're independently checkable later
  against `MIRACLE_LEDGER.md`.

## Git workflow

- **One commit per Miracle**, with a message that states what shipped
  and, briefly, why the non-obvious decisions were made the way they
  were — the commit messages for Miracles 002/003/003.1 are the
  reference: what changed, the key design decision and which ADR
  documents it, test/ruff results, technical debt introduced.
- **One annotated tag per Miracle**, following
  `vMAJOR.MINOR.PATCH-miracle-NNN[-N]` — `v0.1.0-miracle-001`,
  `v0.2.0-miracle-002`, `v0.3.0-miracle-003`, `v0.3.1-miracle-003-1`.
  Minor version bumps for a new capability; patch-equivalent suffixes
  (`-003-1`) for a Miracle that connects/extends an existing one rather
  than adding a new one. A documentation-only Miracle (like 003.5) still
  gets its own tag — see `MIRACLE_LEDGER.md`.
- **Never amend a previous Miracle's commit.** Fix forward, in a new
  commit, even for something small — the Miracle Ledger's history has to
  stay literally accurate to what shipped when.
- **Build artifacts never get committed.** `.venv/`, `__pycache__/`,
  `.pytest_cache/`, `.ruff_cache/`, `*.egg-info/` are cleaned before every
  package/delivery step — verified with `git status --short` showing
  clean before zipping, every time.

## Release workflow

Until `D:\MasterAgent` is a confirmed, reachable location (still
unverified as of this writing — see `FOUNDER_CONTEXT.md` and every
Mission Brief's closing caveat), "release" means:

1. Full suite green, ruff clean — verified fresh in this delivery, not
   assumed from an earlier run in the same session.
2. Commit + annotated tag in the staging git repository.
3. Clean build artifacts, then package the whole repository (including
   `.git/`, so history travels with the zip) as `MasterAgent_scaffold.zip`.
4. Deliver the zip directly to the founder — never just a description of
   what changed.
5. Persist the updated canonical docs (`PROJECT_BRAIN.md`,
   `ARCHITECTURE.md`, the relevant Mission Brief doc, `DECISIONS.md`) to
   the Claude Project, so they're visible across sessions without
   depending on the zip being unpacked.
6. State plainly, every time, what's still unverified: this workflow
   produces a staging copy in a cloud session, not a confirmed write to
   the founder's actual machine. That gap gets named explicitly, not
   glossed over — the project's standing instruction on this point is
   non-negotiable.

## Documentation workflow

- **Code changes and their documentation ship in the same Miracle**, not
  as separate follow-up work. `ARCHITECTURE.md` is updated in the same
  commit as the module it describes, every time.
- **Every Miracle gets its own `docs/MISSION_BRIEF_NNN.md`** — objective,
  architecture summary, files changed, tests added, test results, ruff
  results, live verification, technical debt introduced, remaining
  stubs, and a recommendation for the next Miracle. This is the durable
  record; the chat-facing deliverable message is a summary of it, not
  the other way around.
- **A real design decision gets an ADR** (`docs/adr/NNNN-slug.md`) —
  context, options considered (including why the obvious-but-wrong ones
  were rejected), decision, consequences (including debt the decision
  knowingly introduces). `DECISIONS.md` gets a short cross-referencing
  entry pointing to it; the ADR is where the actual reasoning lives.
- **Status lines, not silent drift.** Every canonical doc
  (`PROJECT_BRAIN.md`, `ROADMAP.md`, `README.md`, the six documents this
  Miracle created or updated) gets its "as of" status updated in the same
  Miracle that changes what it describes — a doc that quietly stops
  matching reality is worse than no doc, because it's actively
  misleading rather than just absent.
- **Never delete a doc to fix drift; update it, and say what changed.**
  If a document's structure needs to change to stay useful (as
  `PRODUCT_PRINCIPLES.md`'s did this Miracle, gaining a Product
  Philosophy section), the change is additive and explained, not a
  silent rewrite — this document set is meant to be readable by someone
  who only has last month's copy of one file.

## How this playbook itself gets updated

This document describes the process as it has actually been practiced,
not an ideal to grow into — so it should be revised the moment the real
process changes (a new required step, a workflow that stopped applying),
in the same Miracle that changes it, following its own Documentation
Workflow section above.
