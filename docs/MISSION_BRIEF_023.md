# Mission Brief 023 — Mission Control & Self-Development Infrastructure

Status: Shipped — 2026-07-26

## Objective

Build the nervous system: the runtime coordination layer that lets
Kalpavriksha observe, schedule, verify, audit, and eventually improve
itself. Not a dashboard — the switchboard everything else plugs into.

## Design-first, per Rule 1

`MISSION_CONTROL_ARCHITECTURE.md` was written before any code, including
the Scalability Question (its §12) and the two design decisions that had
to be settled up front (terminology, and the knowledge-promotion gate).

## The ten deliverables

| # | Deliverable | Implementation |
|---|---|---|
| 1 | Universal Event Bus | `mission_control/events.py` — `EventType` (all ten brief-named types + the transitions the lifecycle requires), frozen `Event`, `EventBus` |
| 2 | Capability Registry | `mission_control/capabilities.py` — descriptors keyed by deterministic qualified names |
| 3 | Executive Registry | `mission_control/executives.py` — all seven brief-required fields |
| 4 | Worker Lifecycle | `mission_control/lifecycle.py` — the nine states + a legal-transition table |
| 5 | Task Dispatcher | `mission_control/tasks.py`, `dispatcher.py` — objectives, dependencies, readiness, assignment |
| 6 | Self-Development Queue | `mission_control/self_development.py` — the five brief-named categories |
| 7 | Knowledge Acquisition Queue | `mission_control/knowledge_queue.py` — the seven-stage pipeline with a human-gated promotion boundary |
| 8 | Audit Stream | `mission_control/audit.py` — immutable, append-only |
| 9 | Founder Dashboard (backend only) | `mission_control/founder_state.py` — exactly the ten named fields, no UI |
| 10 | Communication Contract | `mission_control/reporting.py` — one `Event` schema, one `report()` method, no free-text channel |

Tied together by `mission_control/mission_control.py` (the facade) and
`mission_control/adapters.py` (registration without modifying anything).

## The three decisions worth reading

**1. "Executive" vs the Constitution's "Worker."** MB023 introduces
*Executive*; the frozen Constitution §17 already defines *Worker* for the
identical role, and MB022 shipped `BrowserWorker`. Two live names for one
concept is exactly the drift §17 exists to prevent. Rather than silently
renaming the founder's deliverables (wrong — the brief is the spec) or
renaming shipped tagged code (wrong — violates Rule 2), the two are
declared synonymous with `Worker` canonical, recorded in §17, and the
Constitution + freeze record were amended together as the freeze process
requires. This is the first amendment made under that process, and it
demonstrates the process works. Full reasoning: ADR-0014.

**2. The knowledge-promotion gate is enforced in code, not prose.**
Constitution ADR-0012 makes Promotion Review human-gated. So advancing a
knowledge request from `VERIFICATION` into `KNOWLEDGE_STORAGE` requires an
explicit `human_approved=True`; without it it raises
`PromotionRequiresHumanApproval`, and the refusal is itself published as
an `APPROVAL_REQUIRED` event so an attempted auto-promotion is auditable
rather than silent. Mission Control can drive the whole pipeline
autonomously right up to that gate and never past it — the one place it
deliberately refuses to be fully automatic.

**3. "Mission Control never performs work" is a test, not a claim.**
`tests/test_mission_control_architecture.py` parses every module's imports
and fails if any of them pulls in Playwright, `subprocess`, `shutil`, a
network library, the `LocalExecutor`, or any concrete plugin. It also
asserts the facade exposes no `execute`/`invoke`/`run` surface, that
registries hold descriptions rather than live objects, and that Mission
Control never defines a second `Evidence` type. The architectural rule
breaks loudly the moment someone crosses it.

## Zero modification to existing Executives

The brief's hardest acceptance criterion. Satisfied by an adapter that
*reads* a plugin's long-standing `manifest`, not by an interface every
plugin must grow. The integration tests deliberately use the **real,
untouched** `FilesystemPlugin` (14 capabilities) and `BrowserPlugin`
(9 capabilities) rather than fakes — a fake shaped for the adapter would
not prove the claim. Neither file was modified by this Mission Brief;
`git diff` over `src/master_agent/plugins/filesystem_plugin.py` and
`browser_plugin.py` is empty.

## A real bug the tests caught

`test_a_ready_task_with_no_available_provider_stays_ready_not_failed`
failed on first run, and it was not a test bug: the dispatcher was
assigning a *second* task to an Executive that already held one.
`ExecutiveRecord.is_available` checked state and health but not
`current_task_id`, and since Mission Control assigns without transitioning
the Executive to RUNNING (it cannot know when the Worker actually starts —
that is the Worker's own report), the state alone still read `READY`
immediately after an assignment. Fixed by making `current_task_id is None`
part of availability, with the reasoning recorded at the property.

## Testing

**107 new tests; 461 passing overall** (354 pre-MB023 baseline + 107).

| File | Covers |
|---|---|
| `test_mission_control_events.py` | Event schema, bus delivery, subscriber isolation, Communication Contract (#10) |
| `test_mission_control_lifecycle.py` | All nine states, legal/illegal transitions |
| `test_mission_control_registries.py` | Qualified names, both registries, availability rules |
| `test_mission_control_dispatcher.py` | Objectives, cycles, dependencies, blocking, dispatch, event sequence |
| `test_mission_control_queues.py` | Both queues, and the promotion gate |
| `test_mission_control_audit.py` | Immutability, sequencing, failure retrieval |
| `test_mission_control_architecture.py` | "Never performs work", mechanically |
| `test_mission_control_integration.py` | The seven acceptance criteria, against real unmodified plugins |

`ruff check` on every new file: All checks passed.

**Pre-existing, unrelated failures (unchanged, 5):** the Windows
path-separator issues tracked as MB023.1 — see below.

## Acceptance criteria

All seven, each with a covering test:

- [x] Register Executives — `test_the_real_unmodified_filesystem_plugin_registers_as_an_executive`
- [x] Register Capabilities — `test_registration_derives_qualified_names_from_the_plugins_own_manifest`
- [x] Dispatch Tasks — `test_dispatch_assigns_a_provider_and_marks_the_executive_busy`
- [x] Receive Events — `test_executive_reporter_stamps_identity_and_publishes_the_single_schema`
- [x] Maintain Audit Stream — `test_audit_stream_records_every_published_event`
- [x] Maintain Self-Development Queue — `test_items_move_through_their_state_machine`
- [x] Expose Founder State — `test_founder_state_exposes_exactly_the_ten_brief_named_fields`
- [x] …without modifying existing Executives — `test_the_real_unmodified_browser_plugin_registers_the_same_way`

## Out of scope, honored

No Desktop, Filesystem, Git, Research, or Knowledge Executive was built.
Only the interfaces they plug into exist —
`test_an_executive_that_is_not_a_plugin_registers_through_the_primitive`
and `test_registering_a_new_executive_requires_no_mission_control_change`
demonstrate that a future Executive needs no Mission Control change.

## Technical debt / known limitations (named, not hidden)

- **The Event Bus is synchronous and in-process.** Correct for one founder
  on one machine; wrong for multi-process. Isolated behind a small
  interface so it can be replaced without touching anything above it.
- **The Audit Stream is an unbounded in-memory list.** Same class of
  problem as `LocalExecutor._log` (`MEMORY_ARCHITECTURE.md` §11), and
  deliberately *not* solved differently here so there is one answer when
  it is addressed, not three.
- **No persistence.** Mission Control state does not survive a restart.
  The correct seam already exists — a persistence layer subscribes to the
  bus — but wiring it to Memory is a separate decision, not something to
  assume.
- **Readiness is recomputed O(tasks) per call** rather than incrementally.
  Fine at Founder Edition scale, wrong for very large objectives.
- **No priority scheduling beyond dependency order**, no retry policy
  (strategic recovery is the Brain's, per Constitution §11), no
  distributed dispatch (§8.5 leaves concurrency EVOLVABLE).

## MB023.1 — Cross-Platform Path Safety

Tracked separately in `ROADMAP.md` as the brief instructed, and completed
as its own commit so it did not distract from the nervous system. See
`docs/MISSION_BRIEF_023_1.md`.

## Recommendation for the next Mission Brief

Mission Control is now the coordination layer, but nothing yet *drives* it
end to end: today a caller must pull ready tasks and invoke them itself.
The natural next Miracle is the loop that closes — an Operator-side runner
that takes `dispatch_ready()`, invokes each task through the Mission Brief
022 Worker machinery, feeds the Verification Verdict back via
`task_completed(evidence_id=...)`, and drives a real multi-step objective
to completion with no hand-holding. That would make the Kalpavriksha Loop
(`Intent → Plan → Delegate → Execute → Verify → Learn → Report`) genuinely
continuous for the first time, and it needs no Constitution change.
