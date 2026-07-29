# Browser Worker Architecture

Status: Added 2026-07-26 — Mission Brief 022, Browser Worker (first implementation
against the frozen Founder Constitution)

Design document required before any of this Miracle's code was written, per
`docs/architecture/KALPAVRIKSHA_VISION_V2.md` Rule 1 ("Design Before Code,
Answering the Scalability Question"). `docs/architecture/KALPAVRIKSHA_VISION_V2.md`
§10 (Verification), §12 (Worker and Plugin Runtime), and §8 (Multi-Operator
Architecture) are the constitutional authority this design implements against;
this file is the detail, in the same relationship `FILESYSTEM_CAPABILITIES.md`
has to `ARCHITECTURE.md` §4.7.

## 1. What this Mission Brief actually proves

Not browser automation — Playwright already solves that. This Mission Brief
proves the **Universal Executive Operator architecture** by implementing its
first real Worker against a real Environment. Every decision below is made
so that a future Desktop Worker, Terminal Worker, REST Worker, or MCP Worker
can copy this file's shape and change only what's genuinely browser-specific
(the four files listed in §9 that import `playwright` at all).

## 2. The one open Constitution question this Mission Brief must resolve

`docs/architecture/FOUNDER_CONSTITUTION_FREEZE.md` §3 named a deliberately
open item: "stateful Environment Sessions inside the Worker/Action contract
— today's Action contract is one-shot (`validate()` → `run()`); Browser,
Terminal, and Robotics capabilities will eventually need a capability that
holds a live handle across multiple `Step`s in one Mission." Browser Worker
is exactly that future capability arriving. This design resolves it (§4)
without touching the existing `Action` contract itself — every Browser
Action still implements the same six-member `Action` ABC
(`executor/action.py`) unchanged; what's new is that some Browser Actions
additionally take a `session_id` parameter naming which already-open
Environment Session to act against, resolved through a new
**Environment Session Manager**, not through the Action contract growing a
new method.

## 3. Layer map (Constitution → this Mission Brief)

| Constitution concept | This Mission Brief's implementation |
|---|---|
| Worker (`KALPAVRIKSHA_VISION_V2.md` §12) | The 9 Browser Actions (§6) + `BrowserPlugin` |
| Environment Session (§8.3) | `BrowserSession` / `BrowserSessionManager` (`environment/browser_session.py`) |
| Observation (§10.2, §17) | `BrowserObservation` / `normalize_observation()` (`plugins/browser_observation.py`) |
| Verification (§10) | `Verifier` ABC (`verification/verifier.py`, generic) + `BrowserVerifier` (`plugins/browser_verifier.py`, ~10 lines) |
| Evidence (§9.2, §17) | `Evidence` / `ExpectedOutcome` / `ObservationCheck` / `Verdict` (`verification/evidence.py`, generic) |
| Audit (§5.6) | `AuditRecord` / `AuditLog` (`verification/audit.py`, generic) |
| Worker lifecycle facade | `BrowserWorker` (`plugins/browser_worker.py`) — sequences execute → verify → audit, decides nothing |

The **generic** layer (`verification/`) contains zero Playwright imports and
zero browser vocabulary — it is written to be the Desktop/Terminal/REST
Worker's verification layer too, not just Browser's. This is the concrete
answer to Founder Review question 10 ("can this Worker serve as the
canonical implementation for every future Worker") — the canonical part is
factored out into its own package precisely so the answer is "yes" by
construction, not by promise.

## 4. Environment Session design

```
BrowserSessionManager  (one per Operator Instance, per KALPAVRIKSHA_VISION_V2.md §8.2)
    session_id -> BrowserSession
                      BrowserSession owns: one Playwright instance,
                      one Browser, one BrowserContext, one Page.
                      Never exposed outside plugins/browser_*.py and
                      environment/browser_session.py.
```

- `BrowserSessionManager.open_session(session_id) -> BrowserSessionHandle`
  starts Playwright, launches a browser, opens a context and a page, and
  registers it under `session_id`. Deliberately **not** Shared
  Infrastructure (`KALPAVRIKSHA_VISION_V2.md` §5.7) — a live browser handle
  belongs to the Operator Instance that opened it, exactly as the
  Constitution requires, so a second Operator Instance can never reach
  into a session it didn't open.
- `.get(session_id) -> BrowserSession` looks up a live session; a missing
  or already-closed session is a structured mechanical error
  (§8's Error Handling), never an exception that escapes to the caller.
- `.close_session(session_id)` tears down the page, context, browser, and
  Playwright instance, in that order, swallowing teardown errors into a
  warnings list rather than raising (closing must never fail loudly —
  a session the caller believes is gone should never leave the process
  in a worse state than before `close` was called).
- Every Browser Action that needs an open page (`navigate`, `click`,
  `type_text`, `press_key`, `scroll`, `wait_for_selector`, `observe`) takes
  `session_id` in its payload and resolves it through the injected
  `BrowserSessionManager` — the Action itself never stores session state
  between calls, keeping it consistent with every other `Action`
  (stateless, constructed once, safe to call `run()` on repeatedly).

**Why not build a generic `EnvironmentSessionManager[T]` base class now.**
One concrete example (Browser) doesn't justify the abstraction yet — this
is the same judgment call ADR-0005/0006 made about the Plugin→Executor
relay pattern ("one working example doesn't justify the abstraction yet").
`BrowserSessionManager`'s four-method shape (open/get/close/list) is written
so that a second stateful Worker (Terminal, holding a shell process instead
of a page) can copy the *shape* directly; extracting a shared base is the
right call the moment that second example exists, not before.

## 5. Product independence, and the one unavoidable gray area

Every Browser Worker file is free of specific product names — none of the
forbidden names this Mission Brief lists appear in any module, test, or
this document. The one place this needed a deliberate decision:
Playwright's own launcher API is namespaced by engine, and at least one of
its three built-in engine identifiers is spelled identically to a consumer
browser product's name — a genuine gray area. Resolution: **the
Environment Session contract does not expose engine choice at all.**
`BrowserSession` takes only
`headless: bool`; which Playwright launcher it calls internally is a single
private function, `_launch(playwright_instance)`, in `environment/
browser_session.py` — the only line in the entire Browser Worker that names
a specific engine. Swapping it for a different one (or, per Founder Review
question 9, swapping Playwright itself for a different browser-automation
library entirely) touches exactly that one function; nothing in the Action
contract, the Plugin manifest, the Verifier, or any test changes shape.

## 6. Action roster (the Worker Contract's concrete instances)

Nine atomic Actions, each one Playwright operation, matching
`FILESYSTEM_CAPABILITIES.md` §2's "one Action, one clearly-scoped effect"
discipline — no `BrowserAction` god-class with an `operation` switch:

| Action | Capability name | Risk tier | Category | Wraps |
|---|---|---|---|---|
| `OpenBrowserSessionAction` | `open_browser_session` | `REVERSIBLE_WRITE` | `SYSTEM` | Playwright launch + new_context + new_page |
| `CloseBrowserSessionAction` | `close_browser_session` | `REVERSIBLE_WRITE` | `SYSTEM` | Playwright context/browser teardown |
| `NavigateAction` | `navigate` | `REVERSIBLE_WRITE` | `MODIFY` | `page.goto()` |
| `ClickAction` | `click` | `REVERSIBLE_WRITE` | `MODIFY` | `page.locator(selector).click()` |
| `TypeTextAction` | `type_text` | `REVERSIBLE_WRITE` | `WRITE` | `page.locator(selector).fill()` |
| `PressKeyAction` | `press_key` | `REVERSIBLE_WRITE` | `MODIFY` | `page.keyboard.press()` / locator `.press()` |
| `ScrollAction` | `scroll` | `REVERSIBLE_WRITE` | `MODIFY` | `page.locator(selector).scroll_into_view_if_needed()` / `mouse.wheel()` |
| `WaitForSelectorAction` | `wait_for_selector` | `READ_ONLY` | `READ` | `page.locator(selector).wait_for()` |
| `ObserveBrowserAction` | `observe_browser` | `READ_ONLY` | `READ` | `normalize_observation()` (below) |

`open_browser_session`/`close_browser_session` are classified `SYSTEM`
category — the first real use of the `PermissionCategory.SYSTEM` value
ADR-0009 reserved "for a future non-file capability (e.g. run a shell
command)"; launching a local process is exactly that. None of the nine
are `IRREVERSIBLE` — every effect a browser session can have is undone by
closing the session; this mirrors the filesystem Actions' own honest
tiering discipline (§5 of `FILESYSTEM_CAPABILITIES.md`), not a default.

**Deliberately not built:** hover, drag-and-drop, file upload, multi-tab
management, network interception. Playwright already has all of these;
adding the Worker-Contract wrapper for any one of them is a single new
`Action` file whenever a concrete need exists (per §4's "adding capability
#N costs one new file" rule) — building them speculatively now, with no
demonstrated need, is exactly the premature complexity `ENGINEERING_
PRINCIPLES.md` #10 warns against.

## 7. Observation and Normalization

`normalize_observation(page, selectors=None, include_accessibility_tree=False,
include_available_actions=False) -> BrowserObservation`
(`plugins/browser_observation.py`) is the **only** function, besides the
Actions themselves, that touches a Playwright `Page`.
`ObserveBrowserAction.run()` and `BrowserVerifier.capture_observation_dict()`
both call this one function — no duplicated "how do we read the page" logic
(`ENGINEERING_PRINCIPLES.md` #7). `BrowserObservation.as_dict()` is the
generic, Playwright-free view that crosses into `verification/`'s Evidence
machinery; nothing past this boundary ever sees a Playwright type.

**Five facets, covering every observation source this Mission Brief named:**

| Facet | Source | Always on? |
|---|---|---|
| Current page | `page.url`, `page.title()` | Yes |
| Viewport | `page.viewport_size` | Yes |
| DOM state / visible elements | one best-effort `BrowserElement` per caller-supplied selector (visibility, text, tag name) | Yes (for the selectors asked about) |
| Accessibility tree | the page's ARIA snapshot, as generic role/name vocabulary | Opt-in |
| Available actions | the page's live interactive affordances (role, accessible name, tag, enabled state) | Opt-in |

**Why the last two are opt-in rather than always-on.** Both are unbounded
in the size of the *page*, whereas the first three are bounded by what the
caller actually asked about. Verification re-observes on **every** verified
step (§8), so capturing them unconditionally would tax every Mission — and
inflate every Evidence record, including any a future Miracle persists into
Memory — with data most steps never check against. Callers opt in per call
(`ObserveBrowserAction`'s payload, `BrowserWorker.run_step`'s
`verify_accessibility_tree`/`verify_available_actions`), and both are
capped (`MAX_ACCESSIBILITY_TREE_CHARS`, `MAX_AVAILABLE_ACTIONS`) with an
explicit `*_truncated` flag rather than silently cut — a silently truncated
observation would make Evidence quietly wrong, which is exactly what §9's
Evidence Hierarchy exists to prevent.

**"Available actions" means the page's affordances, not the Worker's
capabilities.** What the *Worker* can do is its capability manifest — a
Capability Registry concern (`KALPAVRIKSHA_VISION_V2.md` §5.1), not an
Observation one. What the *page* currently affords (an enabled button, a
link, an editable field) is a genuine, freshly-observed fact about
Environment state, and is what this facet reports. Conflating the two would
have put a Registry lookup inside the Observation layer for no reason.

Every facet degrades honestly: a selector that matches nothing, an ARIA
snapshot that can't be captured, an affordance scan that errors — each
yields "absent" rather than raising, because Observation must never crash a
Verification pass just because the page doesn't currently have what was
expected. That absence *is* the observation.

## 8. Verification, Evidence, and why Execution never implies success

`Verifier.verify(expected: ExpectedOutcome) -> Evidence` (`verification/
verifier.py`) is a **concrete** method on an abstract base: it calls the
subclass's one abstract method, `capture_observation_dict()`, evaluates
`expected.checks` against the resulting dict via `evaluate_checks()`
(`verification/evaluator.py`, pure function, no I/O), and returns an
`Evidence` record. `BrowserVerifier` implements only
`capture_observation_dict()` — everything else (building the `Evidence`
object, computing the `Verdict`, handling an observation that fails to
capture at all) is shared, generic code any future Verifier reuses
unchanged.

Crucially, `Verifier.verify()` never reads an `ExecutionResult`. It always
re-observes reality fresh. This is what makes Verification structurally
independent (ADR-0011), not just nominally distinct: an Action can return
`success=True` (Playwright's `click()` didn't raise) while Verification
independently returns `Verdict.NOT_MATCHED` (the click didn't produce the
expected page state) — and the Worker Lifecycle (§9) treats the Verdict,
never the Execution Result, as the source of truth for whether the step
actually worked.

`ObservationCheck` supports four operators for this Mission Brief:
`equals`, `contains`, `not_contains`, `matches_regex`, plus `exists` (does
the field appear in the observation at all). This is deliberately a flat,
small vocabulary — not a general expression language — because nothing in
this Mission Brief's scope needs more, and a bigger DSL is easy to add
later (one more `elif` in `evaluate_check()`) but hard to remove once
consumers depend on it.

## 9. What never imports `playwright`

`environment/browser_session.py` and `plugins/browser_observation.py` are
where Playwright is actually driven — the nine files under
`executor/actions/browser/` call into those two, and some (not all) also
reference Playwright's own exception types directly for error mapping.
This is where any future non-browser Worker's equivalent code would differ
entirely. `verification/*` (the generic layer), `plugins/browser_verifier.py`
(imports only the generic `Verifier` base and calls `normalize_observation`),
`plugins/browser_worker.py`, and `plugins/browser_plugin.py` do not import
Playwright at all — this is mechanically checkable (and is: see
`tests/test_browser_constitution_compliance.py`), not just an intention
stated in prose.

## 10. Worker Lifecycle facade — what `BrowserWorker` is and is not

`BrowserWorker.run_step(capability, payload, requested_by, expected_outcome=None)`
sequences exactly three mechanical steps and returns a `BrowserStepReport`
bundling all three outputs:

1. **Execute** — `LocalExecutor.execute(capability, payload)` (the existing,
   unmodified Executor — Browser Actions register on it exactly the way
   Filesystem Actions do; no new Executor variant was built, because none
   was needed).
2. **Verify** — if `expected_outcome` is given, `BrowserVerifier.verify(...)`
   against the session named in `payload["session_id"]`.
3. **Audit** — an `AuditRecord` capturing `requested_by`, worker name,
   environment name, the action name, start/end time, the Execution
   Result's success flag, the Verification Verdict (if any), the Evidence's
   id (if any), and any errors from either step — appended to an
   `AuditLog` that is never truncated or overwritten (§8's "never lose
   execution history").

`BrowserWorker` performs **no reasoning**: it does not choose which
capability to run, does not retry on failure, does not decide whether a
`NOT_MATCHED` Verdict should trigger a re-plan, and does not touch Memory
or Knowledge. Those are Brain/Recovery responsibilities
(`KALPAVRIKSHA_VISION_V2.md` §3, §11) this Mission Brief explicitly must
not implement. `docs/MISSION_BRIEF_022.md` §"Implementation Boundaries
Honored" lists exactly what was left undone and why.

## 11. Where Orchestrator integration deliberately stops, this Mission Brief

`docs/architecture/KALPAVRIKSHA_VISION_V2.md` §4.1 describes the Orchestrator
triggering Verification as part of its normal step-walking. This Mission
Brief does **not** modify `Orchestrator`, `Step`, or `Planner` — all three
are Protected APIs per this brief's own instruction, and one Worker's
existence isn't a strong enough signal to generalize a cross-cutting
Orchestrator change from (the same "two examples before extraction"
judgment as §4 above, one layer up). Two integration surfaces exist
side by side instead:

- **`BrowserPlugin`** (`plugins/browser_plugin.py`) — a thin `Plugin`
  adapter, structurally identical to `FilesystemPlugin`, so a `Step`
  naming a browser capability resolves and executes through the existing,
  completely unmodified `Orchestrator`/`PluginRegistry`/`PermissionSystem`
  path. This proves Capability Registry integration works for a second,
  unrelated capability family, at zero risk to the 229 existing tests.
- **`BrowserWorker`** — the Constitution-complete facade (§10), called
  directly by this Mission Brief's demonstration and by
  `test_browser_worker_lifecycle.py`, standing in for what a future
  Brain/Orchestrator integration would call once a second Verifier-backed
  Worker justifies wiring Verification generically into `Orchestrator`
  itself.

Both paths execute through the identical `LocalExecutor` + the identical
nine `Action` classes — there are not two implementations of browser
execution, only two callers of the same one.

**`BrowserWorker` deliberately does not self-grant permission.**
`BrowserPlugin.invoke()` safely relays a `ONCE` grant to the Executor's key
(the existing ADR-0005 pattern) because it is only ever reachable *after*
the Orchestrator's own check on a different grant key already passed —
the relay is safe precisely because a real gate already ran upstream.
`BrowserWorker.run_step()` has no such upstream gate in this Mission
Brief's scope: it calls `LocalExecutor.execute()` directly. Auto-granting
there would silently reintroduce exactly the bypass ADR-0005 exists to
prevent — a caller could invoke `run_step()` repeatedly with no real human
approval ever having happened. So `run_step()` does not touch
`permissions.grant()` at all; a caller (this Mission Brief's demonstration
and lifecycle test, standing in for an approved Mission) is responsible
for granting the Executor's key before calling it, and an ungranted call
correctly propagates `ApprovalRequired` uncaught, exactly as
`executor/executor.py`'s own docstring requires of every direct caller.
This is verified directly in `tests/test_browser_worker.py`.

## 12. The Scalability Question (Rule 1)

Would this design still be right at a million Missions, thousands of
Workers, hundreds of Environment Instances, years of history, many
Operator Instances?

- **Adding Browser Action #10 (or #50)** costs one new file under
  `executor/actions/browser/`, registered in one tuple in
  `browser_plugin.py` — no edit to `LocalExecutor`, `PermissionSystem`, or
  `BrowserSessionManager`. Identical guarantee to Filesystem's (proven at
  14 capabilities, `FILESYSTEM_CAPABILITIES.md` §8).
- **Adding Desktop/Terminal/REST/MCP Workers** reuses `verification/`
  unchanged (it has no browser vocabulary to outgrow) and copies
  `BrowserSessionManager`'s shape for whatever "session" means in that
  Environment — no change to `Action`, `Plugin`, `LocalExecutor`, or
  `PermissionSystem` contracts.
- **Many simultaneous browser sessions**: `BrowserSessionManager` is
  already keyed by `session_id`, not a singleton — opening ten sessions in
  one Operator Instance costs ten dict entries, not a redesign. Many
  simultaneous **Operator Instances** each running their own
  `BrowserSessionManager` is exactly the shape `KALPAVRIKSHA_VISION_V2.md`
  §8 describes; nothing here assumes a single global browser process.
- **Where this Mission Brief deliberately did not solve something ahead of
  need**: no generic `EnvironmentSessionManager` base (§4), no
  Orchestrator-level automatic Verification dispatch (§11), no expression
  language for `ObservationCheck` beyond five operators (§8), no
  multi-engine configuration surface (§5). Each is named, not hidden, and
  each becomes the right thing to build the moment a second concrete
  example demands it — not before.
