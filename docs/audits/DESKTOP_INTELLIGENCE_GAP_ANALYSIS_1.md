# Desktop Intelligence — Gap Analysis & Proposed Architecture

**Status: design assessment only. No production code in this document
has been written or modified.** Written as the handoff from the
reasoning-layer milestone (`milestone-reasoning-layer`,
`72fcb37`) toward the next phase: evolving Kalpavriksha from "find a UI
element and execute an action" toward "observe → understand → plan →
act → verify → recover."

## Method

Every capability area named in the mission brief was checked against
what the reasoning-layer milestone actually built and proved live, not
assumed. Each is rated:

- **Generic & solid** — proven, reusable, no per-application logic.
- **Generic but heuristic** — reusable and vendor-agnostic in mechanism,
  but still approximation-based, with real, live-found edge cases
  continuing to surface as new applications are exercised.
- **Exists, but declarative/unexecuted** — a real data model exists;
  nothing yet reads and *acts* on it automatically.
- **Missing** — not built.

## Capability map

| Area | State | Where |
|---|---|---|
| Screen/UI observation | **Missing as a first-class primitive** | Screenshots were used constantly this session (`PIL.ImageGrab`) but only in ad-hoc, scratchpad diagnostic scripts — never a Desktop Executive capability. UIA-based observation (below) is real, but pixel-level observation is not. |
| UIA tree inspection | **Generic & solid** | `UiaAutomationBridge._descendants()`, `find()`, `_text_region_candidates()`, `snapshot_text_regions()` — proven across ChatGPT/Kimi/Perplexity, three structurally different UIs, with zero vendor branching. |
| Semantic element identification | **Generic but heuristic** | `find_composer()` (smallest bottom-anchored focusable), `find_main_content()`/`find_new_content()` (size/change/position heuristics). Real, geometry- and content-based signals, not vendor selectors — but each new application has surfaced at least one new edge case (composer-label concatenation, multi-turn response attribution, a bare `"New"` control). The heuristics work; they are not yet exhaustively validated. |
| Application identification | **Generic & solid** | `desktop/inventory.py`/`probe.py`/`catalog.py` — evidence-precedence discovery (Start Menu, registry, MSIX, running-process), proven against 12+ real applications. |
| Application knowledge | **Exists, not yet wired into runtime** | `app_knowledge/` (this milestone) — a real `DOCUMENTED`/`OBSERVED`/`INFERRED` model with safe read-only acquisition. `acquire_knowledge()`'s own output is deliberately *not* auto-merged into anything a provider reads at call time (see that module's own docstring) — a human/report synthesizes it today. No provider consults a profile before acting. |
| Window management | **Generic & solid** | `desktop/execution/window.py::WindowManager` — enumerate/locate/locate_by_process/active/bring_to_front/maximize/minimize/restore/close, all real Win32-backed. |
| Focus verification | **Generic & solid** | `_verify_focus()` (bounded retry + mouse-click fallback), `get_focused_element_in_window()` (new this milestone — cross-window focus-leak guard). |
| Safe clicking | **Generic & solid** | `click()` — InvokePattern first, geometric fallback from the element's own resolved rect, never an invented coordinate. |
| Safe typing | **Generic & solid — the most hardened primitive in the codebase** | `write_text()` — verified clear, verified focus, paste/type routing, containment-based read-back tolerant of composer-specific reflow/chrome. Every one of its guards was added in response to a real, live-found failure. |
| Submission verification | **Generic & solid** | `_submit()`/`_verify_submission()` — Enter first, generic Send-vocabulary fallback, composer-content-change based confirmation. |
| Response verification | **Generic but heuristic, actively improving** | `find_new_content()` — baseline-diff, content-set comparison, prompt-anchored positional floor (two real bugs fixed this milestone alone). Proven twice against ChatGPT's own growing conversation; unproven against Perplexity's distinct response-surface shape. |
| Failure handling | **Generic & solid** | Every layer returns a structured result with an explicit reason (`ISOLATION_UNVERIFIED`, `WRITE_UNVERIFIED`, `SUBMIT_UNVERIFIED`, `RESPONSE_TIMEOUT`, `EMPTY_RESPONSE`, `ExecutionResult(success=False, errors=[...])`) — fail-closed is the rule, not the exception, everywhere audited. |
| Permissions | **Exists, but bypassed by the reasoning-provider path** | `PermissionSystem`/`RiskTier`/`PermissionCategory` govern the Action/Capability/Planner path (`actions_interaction.py`, `plugin.py`). `DesktopAppReasoningProvider.complete()` deliberately composes UIA primitives *directly*, bypassing that dispatch layer entirely (its own module docstring says so, as a reuse decision, not an oversight) — meaning reasoning-provider actions are not currently subject to the same permission-category gating a Planner-issued Action would be. |
| Action planning | **Exists, but declarative/unexecuted** | `desktop/catalog.py::ApplicationOperationProfile` (launch/focus/close/wait_until_ready/health_check/recover, `AutomationStrategy`, `RecoveryApproach`) is real, structured, per-application metadata — but nothing reads it to *decide* what to do next. Every actual sequence in this milestone (`find_named_session → write → submit → verify`) is a fixed pipeline, not a plan assembled from observed state. |
| Recovery | **Exists, but declarative/unexecuted** | `RecoveryApproach.RESTART_APPLICATION` is a field, not a behavior. Every recovery this entire session (closing a polluted Kimi window, retrying a contested launch) was a human/agent judgment call in the moment, never an automatic loop. |
| Screenshots/evidence | **Missing as a first-class primitive** | Same as "screen observation" above — real, valuable, used constantly, entirely ad-hoc. |

## What this adds up to

The **primitives** (act + verify: click, type, submit, focus, window
management, response discovery) are generic, hardened, and proven across
three structurally different real applications. This is a genuinely
solid foundation — the reasoning-layer milestone's own repeated finding
was never "the primitive is wrong," it was "a new application exposed an
edge case the primitive's existing heuristic didn't yet cover," and each
one was closed with a structural, generic fix, not a vendor branch.

What does **not** yet exist is the layer above them: something that
looks at an observation, classifies it semantically (not just
geometrically), consults what is already known about the application,
decides what to do next, and — if something goes wrong — recovers
without a person or a fixed pipeline deciding for it. Today, "planning"
is a single hardcoded sequence per capability; "observation" stops at
the UIA tree; "recovery" is a label nobody reads.

## Proposed architecture for the next mission

A **Desktop Intelligence** layer, sitting above `uia_control.py`'s raw
primitives and *composing* them — not replacing them, and not adding a
second automation framework, the same discipline every layer in this
milestone already held itself to.

1. **Observe** — `DesktopObservation`: one structured snapshot combining
   a UIA scan (existing) with, newly, a first-class screenshot
   capability (`capture_evidence()` — promote what every mission this
   session already did ad-hoc into a real Desktop Executive primitive).
2. **Understand** — semantic classification of what `Observe` found
   (composer / response / navigation chrome / loading state), informed
   by an application's own `AppKnowledgeProfile` where one exists — this
   is where the App Knowledge layer stops being a passive report and
   starts being consulted at call time.
3. **Plan** — a small, generic step-sequencer that reads
   `ApplicationOperationProfile` and the current `DesktopObservation` to
   choose the next primitive, instead of one fixed pipeline per
   capability — the same shape `ReasoningSessionManager.establish()`
   already has in miniature (find-or-create), generalized into a
   reusable concept.
4. **Act** — unchanged: `click()`/`write_text()`/window management,
   already solid.
5. **Verify** — unchanged: the existing verified-write/submit/response
   primitives, continuing to harden per new application encountered.
6. **Recover** — a real executor for `RecoveryApproach`: when a bounded
   verification failure is confirmed, actually perform the declared
   recovery (e.g., close-and-relaunch) instead of stopping at "reported
   as unavailable."

**Permissions** should be reconciled in the same mission or the one
immediately after: either the reasoning-provider path starts routing
through `PermissionSystem`, or the deliberate reuse decision that
bypasses it is re-examined and re-justified now that a second, adjacent
Desktop Intelligence layer is being built on the same primitives.

## Explicit non-goals (for whoever picks this up)

- Not a rewrite of `uia_control.py` — every primitive audited above is
  sound; Desktop Intelligence composes them, the same way
  `reasoning_session.py` and `desktop_app.py` already do.
- Not vision/OCR by default — screenshots as *evidence* (for a human, or
  for a future model with vision) are a clear, proven need; screenshots
  as the *primary* discovery mechanism would be a regression from UIA's
  own generic, resolution-independent semantics.
- Not a new permission model — reconciling with the existing
  `PermissionSystem` is in scope; inventing a second one is not.

## Recommended next mission scope

One bounded mission: implement `capture_evidence()` as a real Desktop
Executive primitive, define `DesktopObservation` and the semantic
classification step (Observe + Understand), and wire
`AppKnowledgeProfile` into it as a consulted input — deliberately
stopping short of Plan/Recover until Observe/Understand has its own
live evidence across at least two of the three proven applications.
Planning and recovery are real, valuable, and explicitly the mission
after that, not this one — the same "one clean layer per mission, proven
live before the next is trusted" discipline this whole reasoning-layer
milestone was built with.
