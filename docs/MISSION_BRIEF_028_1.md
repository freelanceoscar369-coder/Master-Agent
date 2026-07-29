# Mission Brief 028.1 — Founder Approval Workflow

Status: **Shipped** — 2026-07-29

Decision record: `docs/adr/0020-founder-approval-workflow.md`
(**Accepted; its frozen-component changes are Proposed, awaiting
ratification** — see §9.)

## Objective

MB028.0 made Kalpavriksha safe. It did not make it usable: the boundary
blocked irreversible work and there was no way to say yes. This turns
approval from an architectural concept into a founder workflow — see,
inspect, approve, reject, defer, without leaving the Dashboard.

| # | Deliverable | Where |
|---|---|---|
| 1 | Founder Approval Queue | `mission_control/approvals.py`, §2 |
| 2 | Dashboard Approval panel | `dashboard/panels.py::render_approvals`, §3 |
| 3 | Founder commands | `launcher/console.py`, §4 |
| 4 | Approval Ledger | `ApprovalRecord`, §5 |
| 5 | Deferred queue survives restart | `persistence/service.py`, §5 |
| 6 | Rejected work fails gracefully | §6 |
| 7 | Approval timeout | §6 |
| 8 | Multiple pending approvals | §7 |
| 9 | Live dashboard refresh | §3 |
| 10 | Sequence diagram | §8 |

## 1. The change in one line

> **An unanswered request is no longer a refusal.** MB028.0 failed the
> task; MB028.1 asks the founder and the task waits.

`ApprovalPending` is deliberately not a subclass of `ApprovalDenied`.
Conflating them is how "the founder was asleep" becomes "the mission
failed", and Deliverables 6 and 7 exist precisely to keep those apart.

## 2. The queue (Deliverable 1)

`ApprovalQueue` sits in Mission Control beside the two human-gated queues
MB023 already built. Every entry carries all ten fields the brief names:
approval id, objective, mission (task), executive, capability, risk tier,
reason, estimated impact, timestamp, requesting component.

Two properties worth reading:

- **Idempotent by (task, capability).** The Runtime re-checks the
  boundary every cycle while a task waits. Without this, a five-second
  wait produces hundreds of identical entries and hundreds of events. The
  founder is asked once and answers once — asserted by
  `test_the_founder_is_asked_once_however_many_cycles_pass`.
- **`find_open` is scoped to *undecided* entries.** A rejected delete does
  not silently authorise the next delete, and an approved one does not
  silently authorise a repeat — the same rule ADR-0009 applies to `ONCE`
  grants.

It is **not a second permission system.** The queue holds questions; the
Permission System holds authority. Approving issues a `ONCE` grant there.
ADR-0019's boundary stays singular, as MB028.1's Architecture Rules
require.

## 3. The panel (Deliverables 2, 9)

```
PENDING APPROVALS (1)
  [1] Filesystem.DeleteFolder
      Executive : filesystem
      Reason    : Delete Folder
      Risk      : IRREVERSIBLE
      Impact    : Deletes 14 files
      Requested : 18:00
  [A]pprove N   [R]eject N   [D]efer N   approve all
```

Rendered **above the Runtime panel** — it is the only thing on the screen
the founder must *act* on; everything else is something to know. A
blocked system whose reason for being blocked is eight panels down looks
broken.

Updates live off the Event Bus with no restart and no manual refresh: a
new request publishes `APPROVAL_REQUESTED`, which marks the view dirty
like any other event (Deliverable 9).

**ADR-0016 is untouched.** The panel is a pure function of a frozen
snapshot and has no way to act on the hints it prints. See §4.

## 4. The console (Deliverable 3)

```
approve 1     reject 1     defer 1     approve all     help     quit
a 1           r 1          d 1
```

No flags. `--approve` is gone: approving a capability *class* in advance
is the wrong shape — a founder should decide a specific request, seeing
its impact, at the moment it is asked.

**Why the console is in `launcher/`, not `dashboard/`.** ADR-0016 makes
read-only structural: panels hold a frozen snapshot and cannot mutate
what they observe. Giving `FounderDashboard` a live Mission Control would
undo that. So the Dashboard renders and the Console — in the composition
root, which is permitted to know every layer — acts through Mission
Control's published contract.

**One writer to the terminal.** A background render thread plus a
blocking `input()` fight over stdout. Instead the console polls for
keystrokes between frames and echoes the command line as part of the
frame it draws. The reader is chosen by asking the stream
(`sys.stdin.isatty()`), not by guessing the platform, so
`kalpavriksha | tee log.txt` renders and never blocks — the same
discipline MB026 used for charset selection.

Every command is total: a typo at 22:13 returns a message, never an
exception, and never decides anything
(`test_a_bad_command_is_a_message_not_a_crash`).

## 5. Ledger and restart (Deliverables 4, 5)

`ApprovalRecord` is a frozen dataclass in an append-only list, carrying
founder, decision, timestamp, approval id, capability, and mission.
`ledger()` returns copies — evidence you can reach in and edit is not
evidence.

The queue is snapshotted, so **deferred approvals reappear exactly as
they were** after a restart, note included. And ADR-0019's rule extends
to it:

> A restored **approved** entry is a *record*, never a grant.

The grant it produced lived in the Permission System, which is
deliberately not persisted. Resubmitting the same work after a restart
asks again — demonstrated live in §8, asserted by
`test_restart_restores_evidence_but_not_authority`.

## 6. Rejection and expiry (Deliverables 6, 7)

**Rejected** work fails gracefully: the task is reported failed to Mission
Control, Founder State updates, `APPROVAL_DENIED` lands in the audit, and
it is **never retried** — retrying a refusal is asking the same question
and hoping for a different answer. Nothing disappears silently.

**Expiry** is a decision made by the system rather than the founder, so it
writes to the ledger with `decided_by: "system"` — a ledger recording
only human decisions would leave an unexplained failure.

**Timeout defaults to disabled** (`--approval-timeout` to enable). A
request that vanishes overnight is worse than one still on the screen in
the morning, and "safe" here means *not executing*, which waiting already
achieves. Expiry is evaluated when the boundary is consulted, not on a
timer — the Runtime already re-checks every cycle, so a separate clock
would be a second thing to keep honest.

## 7. Multiple pending (Deliverable 8)

The queue holds any number, ordered oldest-first with deferred entries
sorted below pending ones, and the founder decides in any order —
`approve 3` before `reject 1` is fine, and indexes resolve against the
queue as it stood when the command was typed, which is how a founder
reads the panel.

**Named limitation:** a task held at the boundary keeps its Executive
assigned, so with a single Filesystem Executive, requests arrive one at a
time in practice even though the queue supports many. It resolves itself
when a second Executive exists; nothing in the queue changes.

## 8. Sequence (Deliverable 10) and live demonstration

```
Founder      Console      Dashboard    MissionControl   ApprovalQueue   Runtime   Gateway  Executive
   |            |             |               |               |            |         |        |
   |            |             |               |<-- ready task -------------|         |        |
   |            |             |               |               |    _handle_task()    |        |
   |            |             |               |               |            |         |        |
   |            |             |               |     ###### APPROVAL BOUNDARY (ADR-0019) #####
   |            |             |               |<-- gate.check() -----------|         |        |
   |            |             |               |--- no grant -> request ---->|        |        |
   |            |             |               |<-- PendingApproval ---------|        |        |
   |            |             |               |-- APPROVAL_REQUESTED (bus) -|        |        |
   |            |             |<-- dirty -----|               |            |         |        |
   |<-- panel renders the queue --------------|               |  TASK WAITS. NOTHING RUNS.
   |            |             |               |               |            |         |        |
   |-- "approve 1" ---------->|               |               |            |         |        |
   |            |-- approve(id, founder) ---->|               |            |         |        |
   |            |             |               |-- decide ---->|            |         |        |
   |            |             |               |<- ApprovalRecord (ledger) -|         |        |
   |            |             |               |-- APPROVAL_GRANTED (bus, audit, event log)    |
   |            |             |<-- dirty -----|               |            |         |        |
   |            |             |               |               |            |         |        |
   |            |             |     next cycle: _resume_awaiting() re-offers the held task    |
   |            |             |               |<-- gate.check() -----------|         |        |
   |            |             |               |-- grant ONCE -> Permission System -->|        |
   |            |             |               |               |            |-- invoke -->|   |
   |            |             |               |               |            |         |-- run ->
   |            |             |               |<-- task_completed ---------|         |        |
   |<-- panel shows (0); mission completes ---|               |            |         |        |
```

Run live against a real filesystem, all eight steps the brief names:

```
1-2. Irreversible task submitted; Runtime asks; Dashboard shows it
     PENDING APPROVALS (1)
       [1] Filesystem.DeleteFolder
           Risk      : IRREVERSIBLE
           Impact    : Deletes 14 files
     folder still there: True   task: dispatched
3.   Founder approves from the console
     > approved [1] Filesystem.DeleteFolder
4-5. Runtime resumes; task completes
     task: completed   folder gone: True
     PENDING APPROVALS (0)  nothing is waiting on you
6-7. Restart. Audit proves the approval existed
     ledger: approved by onkar at 18:00:21 for Filesystem.DeleteFolder
8.   The approval is no longer active
     open approvals after restart: 0
     same work resubmitted -> asks again: 1 pending, folder intact: True
```

## 9. Verification

**33 new tests, 1051 passing, 1 skipped, zero regressions** (1015 before).
Ruff clean across every file this brief touched.

The eight proofs the brief requires, each with a test: approval appears in
the dashboard; reject works; defer works; timeout works; restart restores
deferred approvals; approval evidence is immutable; multiple approvals
supported; replay restores evidence but not authority.

**One real bug found by a failing test.** The first implementation
approved correctly, published correctly, and left the task at
`DISPATCHED` forever: a held task is dispatched as far as Mission Control
is concerned, so it never returns through `_dispatch()`. The Runtime now
keeps `_awaiting_approval` and re-offers those tasks first each cycle.

**Frozen components changed — ADR-0020 is Proposed.** MB028.1 lists
"updated ADR (if needed)" as a deliverable rather than a gate and its
Definition of Done is a working workflow, so this shipped on MB025's
precedent rather than stopping. Every change is additive and isolated:
reverting them removes the workflow and restores MB028.0's behaviour
exactly. The ratified-exceptions guard names each path against its ADR.

## 10. Technical Debt and Known Limitations (Rule 10)

1. **ADR-0020's frozen changes are unratified.** A founder decision.
2. **One Executive serialises approvals** (§7). Resolves itself when a
   second Executive exists.
3. **`estimate_impact` is best-effort.** It reports `unknown` rather than
   guessing, because a founder approves *against* that number — but it
   only understands filesystem payloads today, so a future Executive's
   requests will show `unknown` until it learns their shape.
4. **No approval history view.** The ledger is durable and queryable but
   nothing renders it; the founder sees pending work, not past decisions.
5. **Console editing is minimal** — printable characters, backspace,
   Enter. No history, no completion, no cursor movement.
6. **A rejected task cannot be re-offered.** Rejection is final for that
   task; resubmitting the objective is the way to ask again. That is
   deliberate, but a founder who rejects by mistake currently has no undo
   short of resubmitting.
