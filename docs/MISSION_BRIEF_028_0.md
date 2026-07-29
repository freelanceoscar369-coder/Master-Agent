# Mission Brief 028.0 — Runtime Permission Boundary (Safety Fix)

Status: **SHIPPED** — 2026-07-29

Ran in two halves, as MB028.0's own Architecture Rules require:

1. **Design, then stop.** Deliverables 1, 2, and 10 were produced and the
   work halted at `docs/adr/0019-runtime-approval-boundary.md`, because
   the fix needs two frozen packages changed: *"If any frozen component
   must change: stop, produce ADR, explain why, wait for ratification. No
   silent architectural drift."* No frozen file was touched.
2. **Ratified, then implemented.** The founder ratified ADR-0019 on
   2026-07-29. Deliverables 3–9 followed, exactly as specified.

**Constitution Rule 5 is now mechanically true on both execution paths.**

| # | Deliverable | Status |
|---|---|---|
| 1 | Trace the complete execution path | ✅ §1 |
| 2 | Design the correct approval boundary | ✅ §2, ADR-0019 |
| 3 | All Runtime execution passes through it | ✅ `_handle_task()`, one funnel, AST-asserted |
| 4 | IRREVERSIBLE always requires approval | ✅ §3 — a classification, not a list |
| 5 | Demonstrate the path cannot bypass | ✅ §6 |
| 6 | Unapproved irreversible task is denied | ✅ §7, live |
| 7 | Approved task executes, audit holds evidence | ✅ §7, live |
| 8 | Evidence survives restart | ✅ §7, live |
| 9 | Replay never re-executes | ✅ §7, live |
| 10 | Sequence diagram with the approval point marked | ✅ §5 |

---

## 1. Deliverable 1 — The complete trace

### 1.1 The two paths

```
PATH A — the Orchestrator path (MB001-005). Gated.

  Intent -> MissionPlan(Step) -> Orchestrator.execute_step()
                                      |
                                      | orchestrator.py:39  resolve plugin + risk_tier
                                      | orchestrator.py:42  permissions.check(
                                      |                        plugin_name,
                            GATE A -->|                        capability,
                                      |                        risk_tier)      <-- RAISES
                                      v
                                 plugin.invoke()
                                      |
                                      | filesystem_plugin.py:170
                                      | permissions.grant(executor.name, capability, ONCE)
                                      |   ^ ADR-0005 relay: carries GATE A's decision down
                                      v
                                 executor.execute()
                                      |
                            GATE B -->| executor.py:104  permissions.check(
                                      |                    executor.name, action.name, tier)
                                      |   ^ satisfied by the relay above
                                      v
                                 action.run() -> filesystem


PATH B — the Runtime path (MB023/MB024). UNGATED.

  Objective -> MissionControl.submit_objective()
                    |
                    | dispatcher: dependency order, readiness, assignment
                    v
            RuntimeEngine._cycle_once()
                    |
                    v
            RuntimeEngine._handle_task()          <== THE ONLY FUNNEL
                    |
                    | engine.py:256  gateway = self._gateways[task.assigned_executive]
                    | engine.py:274  local_capability = mc.capabilities.get(...).capability
                    |
                    |  *** NO GATE. The Orchestrator is not on this path. ***
                    |
                    v
            _execute_with_retry() -> engine.py:320  gateway.invoke(local_capability, payload)
                    |
                    v
            PluginGateway.invoke()  -> gateway.py:100  plugin.invoke(capability, payload)
                    |
                    v
            FilesystemPlugin.invoke()
                    |
                    | filesystem_plugin.py:170
                    | permissions.grant(executor.name, capability, ONCE)
                    |   ^ relays a decision THAT WAS NEVER MADE
                    v
            executor.execute()
                    |
          GATE B -->| executor.py:104  check(executor.name, action.name, tier)
                    |   ^ passes: the line above just granted this exact key
                    v
            action.run() -> filesystem   *** irreversible work, zero approvals ***
```

### 1.2 Where the boundary disappears, precisely

**Between `engine.py:274` and `engine.py:320`.** That span is where Path A
has Gate A and Path B has nothing.

Gate B is not a second boundary and never was. `executor.py:104` checks a
key that `filesystem_plugin.py:170` unconditionally grants on the line
before — by design, per ADR-0005, because Gate B's job is to *receive* a
relayed decision, not to make one. Remove Gate A and Gate B is
self-satisfying.

MB023.1 came closest to naming this: *"`run()` is not a second boundary."*
It is the same observation, one layer up.

### 1.3 Why no single component is at fault

Each behaves exactly as specified:

- **ADR-0005's relay** is correct *given* an outer approval.
- **MB024's `ExecutiveGateway`** is correct *given* something gates it —
  and MB024's brief was about the loop, not about permissions.
- **MB023's dispatcher** never claimed to gate anything.
- **MIT-001** certified that Mission Control can orchestrate the Browser
  Executive without modifying it. It did not ask whether the path it
  certified was gated, so it did not find this.

The defect is structural: MB024 introduced a **second execution path**,
and the boundary lived in a component (`Orchestrator`) that the new path
does not use. Nothing in the architecture forced the new path to carry it,
because nothing said "there is exactly one place execution may begin."

### 1.4 Verified, not inferred

MB027.5 shipped `test_the_runtime_path_is_ungated`, which built the
launcher's own wiring, invoked `delete_folder` through a bare
`PluginGateway` with no approval anywhere, and asserted the directory was
gone. It passed. It was written to fail once the gap closed — and it did,
so it is now `test_the_runtime_path_is_no_longer_ungated`, asserting the
folder **survives**. A characterisation test that flips into a regression
test is the cheapest possible proof that a defect is actually fixed rather
than merely believed to be.

---

## 2. Deliverable 2 — The design

Full reasoning and rejected alternatives: **ADR-0019**. In brief:

> **One `ApprovalGate`, defined inside `runtime/`, consulted once by
> `RuntimeEngine._handle_task()` before any gateway is touched, failing
> closed when absent.**

- **One source of truth.** `_handle_task` is the only funnel: both gateway
  call sites descend from it, and every task of every objective for every
  Executive passes through it. The gate delegates to Shared
  Infrastructure's Permission System — the same single ledger the
  Orchestrator uses. No second ledger, no duplicated check.
- **The Runtime gains no new dependency.** The protocol lives in
  `runtime/approval.py`, exactly as MB025 put `CheckpointSink` inside
  `runtime/` so the Runtime acquired no storage dependency. The
  composition root supplies the real implementation.
- **Fail closed, totally.** A Runtime with no gate refuses *everything*.
  The ADR proposed "everything above `READ_ONLY`", which turned out not to
  be implementable: the Runtime cannot know a capability's risk tier
  (resolving it is the gate's job, precisely so the Runtime stays ignorant
  of Executives), so with no gate it cannot evaluate the exception it
  would be making. Stricter than proposed, never weaker — and the only
  version that is genuinely fail-closed rather than
  fail-closed-if-we-can-work-out-what-to-close. The `READ_ONLY` exemption
  lives in the gate, where the tier is known.

Rejected: checking inside `PluginGateway` (duplicated per gateway),
routing the Runtime through the `Orchestrator` (merges two execution
models to fix a boundary), and wrapping gateways in the launcher (works,
requires no frozen change, and is exactly the "convention, not
architecture" the Definition of Done rejects).

---

## 3. Deliverable 4 — What always requires approval

The rule is **not** a capability list. A list is a thing to forget to
update; the classification already exists and already travels with the
capability:

> **Every capability declaring `RiskTier.IRREVERSIBLE` requires a fresh
> founder decision, regardless of caller, path, or Executive.**

ADR-0009 already guarantees the half that matters most, mechanically and
in shipped code: an `ALWAYS_FOR_CAPABILITY` grant **can never** satisfy an
`IRREVERSIBLE` check. So no standing approval — however broad, however
convenient — ever authorises destruction. That property is inherited, not
rebuilt.

MB028.0's named capabilities map onto it:

| MB028.0 names | Today | Classification |
|---|---|---|
| Delete Folder | `delete_folder` | `IRREVERSIBLE` ✅ shipped |
| Delete File | `delete_file` | `IRREVERSIBLE` ✅ shipped |
| Install Software | `AiInfrastructure.InstallProvider` | `IRREVERSIBLE` — contract frozen MB027, unimplemented |
| Remove Software | `AiInfrastructure.RemoveProvider` | `IRREVERSIBLE` — as above |
| Upgrade Provider | `AiInfrastructure.UpgradeProvider` | `IRREVERSIBLE` — as above |
| Execute External Program | — | **Does not exist yet.** `PermissionCategory.SYSTEM` is reserved for it (MB005) |
| Registry edits | — | Does not exist yet |
| System configuration changes | — | Does not exist yet |

Five of the eight are not built. The design point is that they need no
special handling when they arrive: they declare `IRREVERSIBLE` in their
manifest and the gate covers them on the day they register. **A capability
list in the Runtime would be the wrong answer** — it would make the
Runtime know what Executives exist, which MB024's Rule 2 forbids and an
import-parsing test already enforces.

---

## 4. Deliverables 8 & 9 — Evidence survives; authority does not

These two pull against each other, and the resolution is the whole of
both:

> **A replayed `APPROVAL_GRANTED` event restores the *record* that an
> approval happened. It must never restore a usable grant.**

- **Evidence is durable.** `APPROVAL_GRANTED` / `APPROVAL_DENIED` events
  carry `capability`, `risk_tier`, `executive_id`, `task_id`,
  `decided_by`, `decided_at`, `scope`. They land in the event log and the
  immutable Audit Stream, so after a kill and recover the audit still
  answers *approval existed / who / when / which capability* —
  Deliverable 8, in full. `decided_by` is required, not optional:
  "approval existed" is a weaker claim than "the founder approved," and
  the deliverable asks for the second.
- **Authority is not durable, on purpose.** The grant ledger is in-memory
  and stays that way. If replay rehydrated grants, every restart would
  silently re-arm every approval ever given — an authority ledger growing
  monotonically, reconstructed from history the founder cannot see. The
  correct posture after a restart is: *the audit remembers that you
  approved; the system still asks again.*
- **Replay executes nothing.** `persistence/replay.py` reconstructs
  Mission Control state and never invokes a gateway. That is true today by
  construction and untested; the ratified work adds the test that pins it,
  because a property nothing asserts is a property that will eventually
  stop being true.

This is ADR-0009's discipline in restart form. A `ONCE` grant is consumed
on use; an `ALWAYS_FOR_CAPABILITY` grant never satisfies `IRREVERSIBLE`;
replay restores evidence and not grants. All three say one thing:
**destructive authority does not accumulate.**

---

## 5. Deliverable 10 — Sequence diagram, approval point marked

```
Founder      PermissionSystem   MissionControl    Runtime      ApprovalGate    Gateway    Executive   Executor
   |                |                 |              |              |             |           |          |
   |--- submit objective ------------>|              |              |             |           |          |
   |                |                 |-- OBJECTIVE_SUBMITTED (event bus) ------------------------------>|
   |                |                 |              |              |             |           |          |
   |                |                 |<- next ready task -----------|            |           |          |
   |                |                 |-- Task ------->|             |            |           |          |
   |                |                 |              |              |             |           |          |
   |                |                 |          _handle_task()      |            |           |          |
   |                |                 |              |              |             |           |          |
   |                |                 |              |-- resolve gateway + local capability   |          |
   |                |                 |              |              |             |           |          |
   |  ############################  THE APPROVAL POINT  ##############################        |          |
   |                |                 |              |-- check(req)->|             |           |          |
   |                |                 |              |              |-- check(plugin,          |          |
   |                |<-------------------------------------------------  capability, tier) --->|          |
   |                |                 |              |              |             |           |          |
   |   [ no grant ] |                 |              |              |             |           |          |
   |                |-- ApprovalRequired ------------>|              |             |           |          |
   |<-- APPROVAL_REQUIRED (event, dashboard) ---------|              |             |           |          |
   |                |                 |              |  TASK FAILS. NOTHING RUNS. |           |          |
   |                |                 |              |              |             |           |          |
   |--- approve(capability, scope) -->|              |              |             |           |          |
   |                |-- APPROVAL_GRANTED (event -> audit -> event log) ---------->|           |          |
   |                |                 |              |              |             |           |          |
   |   [ granted ]  |                 |              |-- check(req)->|             |           |          |
   |                |<------------------------------------------------- check() --|           |          |
   |                |--- ok --------------------------------------------->|        |           |          |
   |                |                 |              |              |             |           |          |
   |  ##################################################################################      |          |
   |                |                 |              |                            |           |          |
   |                |                 |              |-- invoke(local_capability, payload) -->|          |
   |                |                 |              |              |             |-- invoke ->|          |
   |                |                 |              |              |             |           |-- relay -+
   |                |                 |              |              |             |           |   (ADR-0005)
   |                |                 |              |              |             |           |-- execute >
   |                |                 |              |              |             |           |          |-- GATE B
   |                |                 |              |              |             |           |          |   check()
   |                |                 |              |              |             |           |          |-- run()
   |                |                 |              |<------------ result -------------------|          |
   |                |                 |<- task_completed / TASK_COMPLETED (event) |            |          |
   |<-- dashboard reflects completion, audit holds the approval evidence ---------|            |          |
```

Two things the diagram is drawn to make unmissable:

1. **The approval point is on the Runtime's side of the gateway**, not
   inside it. Every gateway implementation — Filesystem today, Browser and
   Terminal later — is behind the same gate, and no gateway can be
   registered that skips it.
2. **Gate B still exists and still receives the ADR-0005 relay.** It is
   not removed and not duplicated. It goes back to doing the job it was
   designed for: carrying a decision that has now genuinely been made on
   both paths.

---

## 6. Deliverable 5 — the path cannot bypass, proven mechanically

Behavioural tests prove the boundary *works*. These prove it cannot be
*routed around*, which is the actual Definition of Done:

| Test | Proves |
|---|---|
| `test_the_runtime_reaches_a_gateway_from_exactly_one_place` | AST-walks all of `runtime/` and asserts exactly **one** `gateway.invoke(...)` site. A second one is an alternate execution path, and this fails. |
| `test_the_approval_check_precedes_the_only_dispatch_path` | AST-asserts `_require_approval` is called at a lower line number than `_execute_with_retry` inside `_handle_task`. A reordering that put execution first would still pass every behavioural test that happens to grant approval — so ordering is asserted on the source, not the behaviour. |
| `test_the_runtime_imports_no_permission_system` | `runtime/` still depends on no Shared Infrastructure module; the boundary is a protocol defined inside it. |
| `test_a_runtime_with_no_gate_executes_nothing` | Fail-closed, with a grant present — proving the gate, not the grant, is what authorises. |
| `test_every_irreversible_capability_is_covered_without_naming_one` | Deliverable 4 as a classification: iterates every `IRREVERSIBLE` capability in the manifest, so a capability added tomorrow is covered without touching the Runtime. |

## 7. Live verification (Deliverables 6–9)

Run against a real filesystem in a sandbox, not a fixture:

```
D6: irreversible task, NO approval
  task state      : failed
  error           : approval denied: founder approval required
  folder survives : True
  APPROVAL_DENIED : 1 event(s)

D7: founder approves, same task repeats
  task state      : completed
  folder deleted  : True
  APPROVAL_GRANTED: 1 event(s)
    who    : onkar
    what   : Filesystem.DeleteFolder
    when   : 2026-07-29T17:13:12.905429+00:00

D8/D9: restart -- replay history into a fresh Mission Control
  evidence survived : 1 APPROVAL_GRANTED event(s)
    who/what/when   : onkar / Filesystem.DeleteFolder / 2026-07-29T17:13:12Z
  replay executed?  : folder still present = True
  authority re-armed? task state = failed, folder = True
```

The last line is the one to read twice. After a restart the audit proves
the approval happened — and the same task, resubmitted, is **refused
again**. Evidence survived; authority did not.

## 8. Churn, and what it measured

Every test that drives the Runtime through a gateway now has to say
whether the founder approved: `tests/dashboard_test_support.py`, MB024's
suite (5 sites), MB025's restart suite, MB027.5's launcher suite. That
churn was predicted in the ADR and is not incidental — **it is a direct
count of how many places were relying on the missing boundary.** Before
MB028.0, none of those tests could have told you whether approval had
happened, because nothing asked.

`tests/approval_test_support.py` holds `ApprovingGate` / `RefusingGate`.
Deliberately *not* shipped in `runtime/`: an "allow everything" gate in
production code is a footgun that eventually gets wired by accident, which
is the exact class of mistake this brief exists to make impossible.

## 9. What is still NOT done

- **There is still no approval UI.** `kalpavriksha --approve <capability>`
  grants for the session, and the Dashboard's `waiting_approval` field
  already exists — but a founder cannot yet answer a pending request
  interactively. With the boundary in place, the honest behaviour is that
  irreversible tasks stop and are reported, which is strictly safer than
  before. The interface is a founder UX decision and belongs in its own
  brief.
- **`ApprovalRequest` carries no evidence of *why* a task wants a
  capability.** A founder approving `delete_folder` sees the capability
  and the task, not the reasoning — that arrives with the real Planner.
- **The Orchestrator path is unchanged**, and now genuinely redundant with
  the Runtime path for permission purposes. Consolidating them is not this
  brief's business and would be a much larger change (ADR-0019, rejected
  option 2).
