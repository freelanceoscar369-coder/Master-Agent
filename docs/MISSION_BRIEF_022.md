# Mission Brief 022 — Universal Executive Operator: Browser Worker

Status: Shipped — 2026-07-26

## Objective

Implement the Browser Worker exactly as defined by the Founder Constitution
(`docs/architecture/KALPAVRIKSHA_VISION_V2.md`), as the first implementation
Mission Brief built against it since its freeze (Mission Brief 021, Revision
3). Not a browser-automation project — a proof that the Universal Executive
Operator architecture (Worker Contract, Observation, Verification, Evidence,
Audit) works in a real Environment, wrapping Playwright rather than
reinventing it.

## Design-first, per Rule 1

`BROWSER_WORKER_ARCHITECTURE.md` was written and reasoned through — including
answering the Scalability Question (its §12) — before any of this Mission
Brief's code was written, per the Constitution's own Rule 1. It resolves the
one Constitution item this Mission Brief's brief flagged as still open
(`docs/architecture/FOUNDER_CONSTITUTION_FREEZE.md` §3: "stateful Environment
Sessions inside the Worker/Action contract") by introducing an **Environment
Session Manager** without changing the existing `Action` contract itself.

## What was built

**Generic, reusable layer** (zero Playwright/browser vocabulary, mechanically
verified — `tests/test_browser_constitution_compliance.py`):

- `src/master_agent/verification/evidence.py` — `Verdict`, `ObservationCheck`,
  `CheckResult`, `ExpectedOutcome`, `Evidence`
- `src/master_agent/verification/evaluator.py` — `get_field`,
  `evaluate_check`, `evaluate_checks` (pure functions, no I/O)
- `src/master_agent/verification/verifier.py` — `Verifier` ABC; concrete
  subclasses implement one method, everything else is shared
- `src/master_agent/verification/audit.py` — `AuditRecord`, `AuditLog`

**Browser-specific layer:**

- `src/master_agent/environment/browser_session.py` — `BrowserSession`,
  `BrowserSessionManager` (one shared Playwright driver + Browser process per
  manager, multiplexed across sessions as separate `BrowserContext`s — see
  "What changed after the first live run" below)
- `src/master_agent/plugins/browser_observation.py` — `BrowserElement`,
  `BrowserObservation`, `normalize_observation()`
- `src/master_agent/plugins/browser_verifier.py` — `BrowserVerifier(Verifier)`
- `src/master_agent/plugins/browser_plugin.py` — `BrowserPlugin`, mirroring
  `filesystem_plugin.py`'s shape exactly
- `src/master_agent/plugins/browser_worker.py` — `BrowserWorker`, the Worker
  Lifecycle facade (Execute → Verify → Audit)
- `src/master_agent/executor/actions/browser/` — nine `Action` subclasses:
  `open_session`, `close_session`, `navigate`, `click`, `type_text`,
  `press_key`, `scroll`, `wait_for_selector`, `observe`

**Dependency:** `playwright>=1.55` added as the `browser` optional extra in
`pyproject.toml` (`pip install -e ".[browser]"`, then a one-time
`playwright install` for browser binaries — matching `START_HERE.md`'s
existing pattern for optional extras like `voice`).

## What changed after the first live run

The design doc's first version of `BrowserSessionManager` gave each
`BrowserSession` its own independent Playwright driver process. Running the
actual test suite (not just a hand-written smoke script) surfaced a real bug
immediately: Playwright's sync API refuses to run a second independent driver
in the same thread while a first is still active ("It looks like you are
using Playwright Sync API inside the asyncio loop"), which only reproduces
once genuinely concurrent sessions are exercised — exactly why `FOUNDER_
PLAYBOOK.md`'s testing process treats end-to-end tests as the primary review
mechanism, not code review of code that "looked done." Fixed by having
`BrowserSessionManager` own one shared Playwright driver and Browser process,
lazily started on the first `open_session()` call and stopped when the last
session closes, with each session becoming one `BrowserContext` (Playwright's
own isolation boundary) rather than one full driver. `BROWSER_WORKER_
ARCHITECTURE.md` and this Mission Brief both reflect the corrected design;
this is a real bug found and fixed during this Miracle, per this project's
own "regression is checked, not assumed" discipline, not a hidden rewrite.

## What a completeness recheck caught, before this Miracle was called done

A deliberate re-read of this brief against what had actually shipped found
a real gap: the brief's **Observation** section names six sources — current
page, DOM state, accessibility tree (where applicable), viewport, visible
elements, and available actions — and the first implementation covered only
four. The accessibility tree and available actions had been skipped
silently, not as a documented scope decision. "Where applicable" did not
excuse it: Playwright exposes an ARIA snapshot API that works fine here, so
the accessibility tree *is* applicable.

Both were then implemented properly (`BROWSER_WORKER_ARCHITECTURE.md` §7):
`accessibility_tree` (the page's ARIA snapshot — generic role/name
vocabulary, never markup) and `available_actions` (the page's live
interactive affordances: role, accessible name, tag, enabled state). Both
are opt-in per call and individually capped with an explicit `*_truncated`
flag, because both are unbounded in page size while Verification
re-observes on every verified step — the reasoning is recorded in §7 rather
than left as an unexplained default.

One conceptual trap worth naming, since a future Worker author will hit the
same one: "available actions" could plausibly mean *what the Worker can do*
(its capability manifest) or *what the page currently affords*. The former
is a Capability Registry concern (`KALPAVRIKSHA_VISION_V2.md` §5.1), not an
Observation one — reading it inside the Observation layer would have put a
Registry lookup where a fresh Environment reading belongs. This
implementation observes the page's affordances, which is the reading that
matches "the Worker must observe browser state."

## Constitution compliance — mechanically verified, not just claimed

`tests/test_browser_constitution_compliance.py` scans every Browser Worker
source file, the architecture doc, and every Browser Worker test file for
the Mission Brief's forbidden product names (word-boundary matching, so the
approved Constitution term "Knowledge" is never a false positive), and
separately confirms the generic `verification/` package and the Plugin/
Verifier/Worker facade files never import Playwright at all. Both checks
pass today and will fail loudly the moment either claim stops being true —
this is a standing regression test for this Mission Brief's own central
promise, not a one-time audit.

## Testing

**125 new tests; 354 passing overall** (229 pre-Mission-Brief-022 baseline
+ 125 new), covering every category the brief asked for:

| Category | File(s) |
|---|---|
| Unit | `test_verification.py`, `test_browser_session.py`, `test_browser_observation.py`, `test_browser_actions.py` |
| Integration | `test_browser_worker.py`, `test_browser_worker_lifecycle.py` |
| Architecture / Constitution Compliance | `test_browser_constitution_compliance.py` |
| Worker Contract | `test_browser_worker_contract.py` |
| Verification | `test_verification.py` (evaluator + Verifier ABC), `test_browser_worker.py` (execution/verification independence) |
| Evidence | `test_verification.py` (Evidence shape, JSON-plainness), `test_browser_worker_lifecycle.py` (Evidence tied to Audit) |
| Audit | `test_browser_worker.py` (`AuditRecord` fields, never-lost history) |
| Regression | full existing suite, re-run unchanged |

`ruff check` on every new/changed file: **All checks passed.** (Pre-existing
lint debt in files this Mission Brief did not touch — `mission.py`,
`permission_system.py`, `executor.py`, `cli.py`, `filesystem_plugin.py`,
`conversation.py`, and several existing test files — was left alone, per
"do not modify unless absolutely necessary"; it predates this Mission Brief
and wasn't part of what was asked.)

**Pre-existing, unrelated failures (unchanged from before this Mission
Brief, confirmed by running the full suite before writing any code):** 5
tests in `test_cli_session.py`/`test_modify_actions.py`/`test_read_actions.py`/
`test_write_file_action.py` fail on this Windows machine due to POSIX
path-separator/absolute-path assumptions (e.g. `Path("/etc/passwd").is_absolute()`
is `False` on Windows) — flagged for a separate, out-of-scope fix, not
touched here.

## Implementation Boundaries Honored

Per the brief's explicit list, none of the following were implemented:
Knowledge Promotion/Learning, Memory, the real Planner, Mission Manager
wiring, Executive Brain, reasoning, intelligence-based retries, adaptive
recovery, or site-specific optimizations. `BrowserWorker`'s public surface
is exactly `run_step()` and `audit_log` — mechanically verified in
`test_browser_constitution_compliance.py`. Protected APIs (`Orchestrator`,
`Planner`, `Step`, `PermissionSystem`, `Mission Manager`, `Model Router`)
were not modified; `BrowserPlugin` integrates with the existing Orchestrator/
PluginRegistry/PermissionSystem exactly the way `FilesystemPlugin` already
does, at zero risk to the 229-test baseline.

## Technical debt / deliberately open items (named, not hidden)

- **No generic `EnvironmentSessionManager` base class yet.**
  `BrowserSessionManager`'s four-method shape (open/get/close/list) is
  written to be copied by a second stateful Worker (Terminal, Desktop,
  Robot); extracting a shared base is deferred until that second example
  exists, per this project's established "one example doesn't justify the
  abstraction yet" judgment (ADR-0005/0006's precedent).
- **Orchestrator does not automatically trigger Verification for a Step.**
  `KALPAVRIKSHA_VISION_V2.md` §4.1 describes this as an eventual Operator
  responsibility; this Mission Brief deliberately did not touch `Orchestrator`
  (a Protected API) to add it, since one Worker's existence isn't a strong
  enough signal to generalize a cross-cutting change from. `BrowserWorker`
  demonstrates the complete lifecycle standalone in the meantime.
- **`ObservationCheck` supports five operators, not a general expression
  language** (equals/contains/not_contains/exists/matches_regex) —
  sufficient for this Mission Brief, easy to extend, deliberately not
  over-built ahead of a demonstrated need.
- **No multi-engine configuration surface.** Which Playwright-driven engine
  launches is not exposed anywhere in the Worker Contract — see
  `BROWSER_WORKER_ARCHITECTURE.md` §5 for why this was the safer, simpler
  choice for this Mission Brief specifically (it also sidesteps a genuine
  product-naming gray area in Playwright's own API).

## Final Founder Review

1. **Is Browser Worker completely subordinate to Executive Brain?** Yes —
   `BrowserWorker.run_step()` takes capability, payload, and Expected Outcome
   entirely from its caller and decides nothing; it does not self-grant
   permission, so it cannot even execute without an approval obtained
   upstream (`test_run_step_requires_a_real_grant_and_does_not_self_approve`).
2. **Does Browser Worker remain environment-aware but product-agnostic?**
   Yes — mechanically verified across 21 files (source, architecture doc,
   tests) with zero forbidden product names found.
3. **Can Desktop Worker be built using exactly the same Worker Contract?**
   Yes — every Browser Action is a plain, unmodified `Action` subclass
   (`test_browser_worker_contract.py`), registered on the same `LocalExecutor`
   class Filesystem uses, with no new contract invented.
4. **Can Terminal Worker reuse this architecture?** Yes, same reasoning as
   #3, plus the entire `verification/` package is provably Playwright-free
   and directly reusable.
5. **Was Playwright wrapped rather than reinvented?** Yes — all nine Actions
   are thin wrappers over one Playwright call each; no selector engine, DOM
   handling, or browser lifecycle logic was reimplemented.
6. **Is Verification structurally independent?** Yes, demonstrated
   concretely: `test_execution_success_does_not_imply_verification_success`
   shows a `click` succeeding while Verification independently reports
   `NOT_MATCHED`, because `Verifier.verify()`'s signature has no
   `ExecutionResult` parameter to read even accidentally.
7. **Is Evidence produced independently of execution?** Yes — same
   mechanism as #6; `BrowserVerifier` always re-observes the live page fresh.
8. **Has any browser-specific knowledge leaked into the architecture?** No,
   beyond the one unavoidable, quarantined Playwright engine-launch call
   confined to a single private function never exposed on any public
   contract.
9. **Would replacing Playwright with another browser engine require only a
   Worker implementation change and not a constitutional change?** Yes —
   concretely, at most `environment/browser_session.py` and
   `plugins/browser_observation.py` (the only two files that import
   Playwright) plus the nine Actions' error-mapping; nothing in
   `verification/`, `Action`, `LocalExecutor`, `PermissionSystem`,
   `Orchestrator`, or the Constitution itself would change.
10. **Can this Worker serve as the canonical implementation for every
    future Worker?** Yes, with one honest, deliberate caveat: the reusable
    parts (Action contract, Plugin adapter, Verifier ABC, Evidence/evaluator,
    Audit) are proven reusable by construction; the Environment Session
    Manager pattern is proven copyable in shape but not yet extracted into a
    shared base class, by design, pending a second stateful Worker (see
    Technical Debt above).

**All ten answers are YES**, the tenth with a named, deliberate scope
decision rather than a gap. Mission Brief 022 is complete.

## Recommendation for the next Mission Brief

Per `docs/architecture/FOUNDER_CONSTITUTION_FREEZE.md`'s Final Founder
Review, the real Planner remains `ROADMAP.md`'s next unblocked item and is
now better-informed by this Miracle: the real Planner should attach an
`ExpectedOutcome` to every `Step` it emits (`KALPAVRIKSHA_VISION_V2.md`
§3.2), not just a human-readable success criterion, now that a concrete
consumer (`Verifier.verify()`) exists for it. Alternatively, if the founder
wants a second Worker next instead, a Terminal Worker is the natural choice
to test whether `BrowserSessionManager`'s shape genuinely generalizes to a
second stateful Environment — the second example this Mission Brief's
architecture doc says is needed before extracting a shared
`EnvironmentSessionManager` base.
