# Health Report — Sprint 1, Component 30: Founder Edition Assembly

**Type:** Implementation health report. Working-directory evidence only.
**Date:** 2026-08-07
**Status:** Complete. **Not committed, not tagged, no Rule 001.**
**Ground:** C1–C29. No Sprint 2, no Mission OS, no Consumer Edition, no Kernel redesign — none touched.

**This is an assembly, and the evidence for that claim is that C24's own
test suite still passes unchanged.** `tests/test_founder_edition_boot.py`
(61 tests) was not edited, and every one of its assertions — including
*"one send, one entry — never two"*, *"no synthetic greeting"*, and its
AST boundary guards — still holds against the extended package.

---

## 1 · What was assembled

```
   boot_founder_edition(founder_name="Onkar")
        │
        ├─ 1  runtime                  C23  the door opens, unwired
        ├─ 2  presence                 C19  attests over what is registered
        ├─ 3  environment_intelligence C22  one scan → intelligence AND inventory
        ├─ 4  conversation             L1   one ConversationMemory
        ├─ 5  connect_founder_runtime  C23  the four, assembled
        │
        ├─ 6  founder_identity         C29  FounderIdentity + FounderSession
        ├─ 7  desktop_executive        C25  knowledge → C26 executor over it
        ├─ 8  desktop_perception       C27  one DesktopObserver
        ├─ 9  desktop_operator         C28  handed the executor and observer above
        ├─ 10 dashboard                C30  eight sections, composed
        │
        ├─ 11 render_founder_surface   C20/C21 — TypeScript, out of scope (unchanged)
        └─ 12 ready
```

**Twelve steps. C24's seven are unchanged and in their original
positions; C30 inserts five after `connect_founder_runtime`.**

| File | Role | New? |
|---|---|---|
| `founder_edition/boot.py` | Extended: five steps, `founder_name`, retained inventory, `say()`, `dashboard()` | edited |
| `founder_edition/desktop_layer.py` | `DesktopLayer` — one each of C25/C26/C27/C28 | new |
| `founder_edition/dashboard.py` | `founder_dashboard()` — eight sections, nothing derived | new |
| `founder_edition/__init__.py` | Exports | edited |
| `tests/test_founder_edition_assembly.py` | 67 tests | new |

**282 statements. 100% coverage (C24 + C30 suites). Ruff clean.**

---

## 2 · The founder experience, run against this machine

```
  Founder: Good morning Somesh
  Somesh : Good morning. I'm awake. Everything is ready.
  Founder: Continue
  Somesh : Continuing.
  Founder: open my inbox
  Somesh : (no reply — see §6.2)

  conversation roles:  user · system · user · system · user
```

Boot on the real machine reported `ok` for all eleven runnable steps
(19 applications scanned, 19 operation profiles available, 3 of 3
runtime sources wired, 8 dashboard sections composed), `out_of_scope`
for `render_founder_surface`, and `ready`. No manual initialization: one
call, no arguments required.

---

## 3 · "No duplicated initialization / state / Runtime" — the three tests
that mattered most

These are the brief's own tests, and each one found something real.

### 3.1 The machine is scanned exactly once

C24 called `discover()`, derived `EnvironmentIntelligence` from the
inventory, and let the inventory fall out of scope. C27's
`DesktopObserver.observe()` needs a `MachineInventory` to attribute a
window's process to an application — so the obvious wiring would have
scanned a second time. **It does not.** `boot.py` now retains the
inventory step 3 already produced and hands it to `DesktopLayer`.
`test_the_machine_is_scanned_exactly_once` counts `discover()` calls
through a monkeypatched name and asserts `== 1`.

This is not only about waste: two scans are two readings of a machine
that may have changed in between, and the founder's dashboard would then
describe an environment the intelligence layer never saw.

### 3.2 There is one executor and one observer, not two of each

`DesktopOperator()` **constructs its own `DesktopExecutor` and
`DesktopObserver` when handed neither** (`desktop_operator/operator.py`
lines 88–89). A composition that built an executor, built an observer,
and then built an operator would silently own two of each — and C27's
`DesktopObservationHistory` is *stateful*, so the dashboard would read
one history while the Operator's own Verify step wrote into another.

`DesktopLayer` requires all four at construction and constructs none of
them itself, so there is exactly one construction site per component and
it is the boot sequence. Proven directly:

```python
assert desktop.operator._executor is desktop.executor
assert desktop.operator._observer is desktop.observer
assert desktop.executor._executive is desktop.executive
```

### 3.3 There is one Runtime and one ConversationMemory

`FounderSession` (C29) holds a *reference* to the app's own
`ConversationMemory` — `__slots__ = ("_conversation",)`, no copy. So a
turn recorded through `say()` is visible to the session, to C23's
projection, and to the dashboard at the same instant, and
`test_there_is_one_conversation_memory_and_the_session_reads_it` asserts
all three see it.

---

## 4 · Somesh speaks, and `assistant` is still unreachable

C23's standing guarantee is that its conversation projection **cannot
emit an `assistant` role** — its own suite asserts this across every
speaker string. C30 records Somesh's replies under the speaker `SOMESH`
(`"somesh"`), which that projection maps to `system` exactly as it maps
every non-`user` speaker. The guarantee therefore holds one layer up
**without being restated or weakened**, and
`test_somesh_turns_are_never_the_assistant_role` asserts the rendered
role set is exactly `{"user", "system"}`.

**C24's `send()` was not touched.** It still records one turn and
composes nothing, and its own tests still assert that. C30 added `say()`
beside it rather than changing it, because *"typing reaches the runtime
with no invented response"* is a guarantee worth being able to keep
testing.

---

## 5 · Two interpretation decisions, stated rather than buried

### 5.1 Which "Dashboard" this is

`master_agent/dashboard/` (MB026, MB029) already exists — but it is a
**different surface at a different altitude**: it renders the Runtime
Engine, Mission Control, approvals, the audit spine, persistence and the
broker, and `DashboardSources` reads those subsystems' own contracts.
Wiring it into this assembly would reach straight into Mission Control,
which this brief forbids in as many words (*"No Mission OS"*) and which
C29 forbids Somesh from touching at all.

So the dashboard C30 assembles is the **founder-facing** one: the eight
sections a Founder Surface (C21) renders through the Presence Layer
(C20). Every section is some other component's own `as_dict()`,
unchanged — `founder_dashboard()` has no branch that reshapes a value, no
key it renames, and no number it computes.
`test_no_mission_os_surface_is_reachable` enforces the boundary by AST
across the whole package.

### 5.2 Boot order is dependency order, not the brief's layering order

The brief draws `… Dashboard → Desktop Executive → Desktop Operator →
Desktop Perception`. That is a **layering** diagram — who sits on top of
whom — and it cannot be a boot order, because C28's Operator is
constructed *from* C26's executor and C27's observer and so cannot
precede them. Boot runs executive → perception → operator and
`STEP_NAMES` carries the argument at the point a reader would ask, the
same way C24's own docstring argues its presence-before-environment
ordering.

---

## 6 · Known limitations

1. **The Operator is wired and idle.** Nothing in C1–C29 turns founder
   speech into a `DesktopTask` — producing one would be planning, which
   C29 states Somesh never does and which this brief places outside its
   scope. So `DesktopOperator` is constructed, holds the one executor and
   the one observer, and is reachable as `app.desktop.operator` — and
   **no founder-facing door hands it a mission.**
   `test_no_founder_facing_door_starts_desktop_work` asserts
   `FounderEditionApp` exposes no `execute`/`run`/`act`/`dispatch`
   method. This is consistent with C23's own *"nothing the founder does
   on this surface can start work"*, but it does mean the desktop
   execution path is assembled and unexercised end-to-end.
2. **Open-ended founder speech gets no reply.** `say()` dispatches to
   C29's `greet()` and `continuity_reply()` and to nothing else.
   Composing prose for arbitrary speech would be a conversational engine;
   this brief is composition only (*"No new Identity"*), and nothing in
   C1–C29 builds one. The founder's turn is still recorded and still
   reaches the runtime. **The brief's own named experience — greeting and
   "Continue" — is fully met; general conversation is not, and is not
   claimed to be.**
3. **The greeting does not mention desktop readiness.** The brief's
   example reads *"Good morning. Claude Desktop is ready. Environment
   looks healthy."* C29's `greet()` composes from `FounderContext`, which
   carries environment/conversation/presence readiness and **no desktop
   field**. Adding one means editing C29 — identity work, not
   composition, and C29 is itself awaiting Hermes audit. Desktop
   readiness *is* carried, in the dashboard's own `desktop` section.
   Recorded, not redesigned.
4. **`_abort()` can itself fail if `ConversationMemory` is permanently
   broken.** C24's abort path builds a replacement `ConversationMemory`
   for the unwired app it returns; if that class is the thing that
   failed, the abort raises rather than returning a readable report.
   C24's own suite does not catch this because its `_raise_once` helper
   fails only the first construction. **Pre-existing C24 behaviour,
   surfaced by a C30 test and then tested at C24's own intermittent-
   failure model rather than repaired** — repairing it is not
   composition. Recorded here for the Founder to decide.
5. **`DesktopLayer.readiness()` watches applications that are installed
   *and* running.** That is a fact the inventory already published, not a
   curated watch-list — a chosen list would be this layer deciding what
   matters to a founder. The consequence is that an application the
   founder cares about but has not launched is not observed.
6. **No test drives a real desktop mutation.** `StubObserver` makes
   readiness assertions deterministic; the live smoke run in §2 exercised
   real perception read-only. C27's and C28's own health reports already
   name their real backends' mutating paths as unverified live; this
   assembly inherits that boundary rather than resolving it.
7. **`render_founder_surface` remains `out_of_scope`.** C20's Presence
   Layer and C21's Founder Surface are HyperAgent's TypeScript and are
   not in this repository. C30 assembles the **data** those surfaces
   consume; it does not render them. C24 already drew this boundary and
   C30 does not move it.

---

## 7 · Test evidence

```
python -m pytest tests/test_founder_edition_assembly.py -q
  67 passed

python -m pytest tests/test_founder_edition_assembly.py \
                tests/test_founder_edition_boot.py \
                --cov=master_agent.founder_edition
  __init__.py         5 stmts   0 miss  100%
  boot.py           206 stmts   0 miss  100%
  dashboard.py       19 stmts   0 miss  100%
  desktop_layer.py   52 stmts   0 miss  100%
  TOTAL             282 stmts   0 miss  100%
  128 passed

python -m ruff check src/master_agent/founder_edition/ \
                     tests/test_founder_edition_assembly.py
  All checks passed!
```

**The guards were proven able to fail.** A throwaway module containing
`from master_agent.dashboard.readmodel import DashboardSnapshot`,
`from master_agent.planner import planner`, and redeclarations of
`FounderRuntime` and `DesktopOperator` was added to the package and the
boundary suite re-run:

```
FAILED TestOnlyComposition::test_no_component_is_redeclared_here[FounderRuntime]
FAILED TestOnlyComposition::test_no_component_is_redeclared_here[DesktopOperator]
FAILED TestOnlyComposition::test_no_mission_os_surface_is_reachable
3 failed, 11 passed
```

The file was deleted and the suite returned to 14 passing.

**Regression evidence:** C24's `tests/test_founder_edition_boot.py` (61
tests), C29's `tests/test_founder_identity.py` (44), and C23's
`tests/test_founder_runtime.py` (83) all pass unedited against the
extended package — **255 together with C30's own 67.**

---

## 8 · Frozen components and prior deliverables

```
git status --porcelain -- foundation kernel ledger coordinator runtime_bridge api
→ (empty)

git status --porcelain -- desktop desktop_operator founder_runtime founder_identity
                          environment_intelligence vigilance
→ (only the untracked C22/C25–C29 directories themselves;
   no tracked file modified)

git status --porcelain -- founder_edition
→ ?? src/master_agent/founder_edition/     (C24's own untracked working-tree work)
```

**Every frozen authority surface is byte-identical, and every C22–C29
deliverable this assembly consumes is untouched.** The only source
package C30 edited is `founder_edition/`, which is C24's own uncommitted
working-tree component and is the composition root this brief asked to
extend.

---

*End of report. Working-directory evidence only. No commits, no tags, no
Rule 001 milestone declared. Stop. Waiting for Hermes audit.*
