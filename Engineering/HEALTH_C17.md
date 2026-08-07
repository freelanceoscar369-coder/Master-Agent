# Health Report — Sprint 1, Component 17: The Kernel API

**Type:** Implementation health report. Working-directory evidence only.
**Date:** 2026-08-06
**Status:** Complete. **Not committed, not tagged, no Rule 001.**
**Built on:** `kalpavriksha-s1-c15.0` — commit `c565244`, with C16 present and untracked.
**Ground:** Kernel Specification · ADR-0022 · ADR-0023 · Roadmap v2 (+ Amendments 001–003) · VEDA 01–04.

**Constraints honoured:** C1–C16 consumed as shipped · Foundation not
modified · Kernel behaviour not modified · no GREEN component reopened ·
no new runtime dependency · no speculative architecture · C18 not begun ·
desktop UI not wired.

---

## 1 · A numbering divergence, stated first

Roadmap §2 assigns **C17 to the Objective Engine**, and records it
**BLOCKED** on the `Objective`/`Mission` ADR (§5 R1). This brief assigns
C17 to the Kernel API (Transport Layer).

**Built: the brief.** Recorded here so the roadmap and the tags do not
silently disagree, and so a reader in a year can tell which C17 a
verification report refers to. The Objective Engine is untouched and
remains blocked.

This is the second such divergence — C16 was briefed as the Execution
Coordinator against a roadmap entry naming Execution Path Unification.
Both are recorded; neither is resolved here. **Recorded as R54.**

---

## 2 · What was built

| File | | |
|---|---|---|
| `src/master_agent/api/kernel_api.py` | new | 338 lines, **61 AST statements** |
| `src/master_agent/api/__init__.py` | new | five exported names |
| `tests/test_kernel_api.py` | new | **52 tests** |

```
KernelApi(kernel)
    authorize(request)           -> ApiResponse
    attempt(warrant_id)          -> ApiResponse
    settle(warrant_id, outcome)  -> ApiResponse
    invalidate(scope, reason)    -> ApiResponse
    status()                     -> ApiResponse

ApiResponse = operation · kind · payload          (frozen)
Operation   = authorize | attempt | settle | invalidate | status
ResultKind  = ok | refused | error
```

**One collaborator, no state.** `__slots__ == {"_kernel"}`. The whole of
the transport is one method and one function; everything else is
delegation.

---

## 3 · The mapping, which is the component

| What the Kernel produced | Kind | Payload |
|---|---|---|
| `Warrant` | `OK` | `Warrant.as_dict()` — C4's own |
| `AttemptToken` | `OK` | `AttemptToken.as_dict()` — C10's own |
| `Receipt` | `OK` | `Receipt.as_dict()` — C5's own |
| `int` (invalidate) | `OK` | `{"count": n}` — §3.5's own word |
| override + outstanding | `OK` | `OverrideSwitch.as_dict()` and the count |
| `KernelRefusal` | `REFUSED` | `KernelRefusal.as_dict()` — C8's own, all seven keys |
| any `Exception` | `ERROR` | `{"type": <class name>, "message": str(exc)}` |

**Nothing is renamed, reordered, flattened, enriched or summarised.** A
test compares the `authorize` payload byte-for-byte against a warrant
minted directly by a second Kernel; another asserts the refusal payload's
key set is exactly C8's seven.

### 3.1 Three kinds, not seven

The operation already says what was asked. The kind says only whether the
Kernel **answered, refused, or raised** — and §7.5 requires the first two
to stay apart:

> *"Refusals are data, not exceptions… the founder is reading a stack
> trace from a provider SDK instead of a sentence about their own
> machine."*

A refusal is a decision the Kernel made and must record. An error is not.
Collapsing them would lose exactly the distinction C8 exists to hold.

Two operations demonstrate the split from opposite sides, and both are
tested: a ledger failure **at attempt** is a `KernelRefusal` and arrives
`REFUSED`; a ledger failure **at settlement** is a raise and arrives
`ERROR`. §3.5 gives settlement no refusal channel, so `settle()` produces
`OK` or `ERROR` and never `REFUSED` — asserted.

### 3.2 Exceptions keep their own names

`AttemptNotAuthorized`, `NothingToSettle`, `LedgerUnavailable`,
`InvalidReceipt`, `InvalidOverride` each cross as **their own class
name**. Nothing is grouped into a transport error taxonomy: a boundary
that renamed them would invent a vocabulary parallel to the one C8 already
closed, and a caller could no longer tell a storage failure from a
constitutional one.

`BaseException` is deliberately not caught — a `KeyboardInterrupt` is not
a response, and a test proves it crosses untouched.

---

## 4 · Four decisions worth naming

**Foundation values in, dictionaries out.** `authorize()` takes an
`ExecutionRequest` and `settle()` takes an `ExecutionOutcome` — never a
dictionary to be assembled here. ADR-0022 D2 makes the caller *"a courier,
not an author"* for the reversibility class, and **a boundary that built
the request from wire fields would become that author.** The door this
component closes is the one onto `master_agent.kernel`; Foundation is
shared vocabulary and stays shared.

**`status()` projects exactly two facts, and derives nothing.** §3.3 gives
the Kernel two pieces of state and it already exposes both as read-only
properties. §7.5 is why these two and no others: *"autonomy is suspended;
1,000 actions are waiting"* needs a switch and a count. Roadmap §2 C21
refuses *"no objective count, no progress bar, no badge"* — what a surface
may **say** about these numbers is C20's and C21's question, and this
component answers none of it. Tests assert both values equal the Kernel's
own properties and that reading them changes nothing.

**`ExecutionCoordinator.run()` is not exposed.** C16 is available and
deliberately unwired: §3.5 fixes the surface at four operations and the
brief permits *"no additional public behaviour."* A fifth operation on
this boundary would be a second way to execute, which is precisely what
one door exists to prevent. A caller wanting the composed sequence
constructs a Coordinator over the same Kernel. Asserted — the module does
not import `coordinator`, and no surface name contains `run`.

**No transport machinery.** No web framework, no server, no socket, no
thread, no queue, no background worker, no retry, no buffering. The
transport is a function call. §11.3's *"no buffering"* is a Kernel rule,
and a transport that buffered on its behalf would defeat it from one layer
up. Asserted against the import list by name.

---

## 5 · Determinism

**No `uuid4()`, no clock, no request id, no correlation of its own.** A
response is a pure function of the operation and what the Kernel returned.

| Property | Asserted by |
|---|---|
| Two APIs over two identically-seeded Kernels answer identically | `authorize` and `status` compared for equality |
| Identical refusals are identical responses | §7.5's *"a thousand refusals are one state"* holds only if they are equal |
| The response carries no id and no timestamp | Key set is exactly `{operation, kind, payload}` |
| No ambient randomness or timing | Checked against **executable identifiers**, not prose — `uuid`, `random`, `monotonic`, `perf_counter` |
| No clock is read | No clock import; no ambient-time call in the AST |
| Every response serialises | All five operations round-tripped through `json` |

The determinism check reads the AST rather than the source text, because
this module's own docstring names the things it does not do — a
text-matching guard would have failed on its own explanation.

---

## 6 · Isolation — the reason the component exists

| Guard | Result |
|---|---|
| Depends only on `master_agent.foundation.*` and `master_agent.kernel` | ✅ |
| Imports no surface (`ui`, `desktop`, `dashboard`, `cli`, `launcher`, `voice`) | ✅ — a door that knew who was on the other side would not be a door |
| Imports no runtime dependency (17 names checked, incl. every web framework) | ✅ |
| Performs no Kernel check and no ledger write | ✅ — no `_check_*`, `_verify_attestations`, `is_suspended`, `is_terminal`, `consequence_ceiling`, `exceeds(`, `attempt_budget`, `is_expired`, `record_*` |
| Invents no refusal vocabulary | ✅ — no `RefusalReason`, `KernelCheck` or `RefusalFamily` in source |
| No surface imports the Kernel | ✅ — `ui/`, `desktop/`, `dashboard/`, `voice/` swept |

**On that last row, honestly:** it passes today because no surface
consumes the Kernel yet. It is a **lock-in guard**, not evidence of a
migration — its value begins the moment a surface needs the Kernel, and it
will fail the build rather than let one reach past this door. Stated so
nobody reads a green tick as work already done.

---

## 7 · Test coverage — 52 tests

The Kernel is **real in every test**, never a double, per §14 R2.

| Area | Proves |
|---|---|
| **Authorize path** | Projects the warrant; the payload equals a directly-minted warrant's own `as_dict()`; delegation is visible in the ledger; the signature takes the Foundation value |
| **Attempt path** | Projects the token; §8.6's idempotency key survives and increments; takes an identifier, not a warrant |
| **Settle path** | Projects the receipt and settles the ledger; **never returns `REFUSED`**; §6.3's four outcome names appear nowhere in the transport |
| **Invalidate path** | Projects `{"count": n}`; suspension reaches the Kernel with its reason intact; a suspended Kernel refuses through the boundary and writes nothing; **no confirmation parameter on any of the five operations** |
| **Refusal mapping** | A refusal is data, not an error; the payload is C8's own seven keys; an attestation refusal keeps its attestor; the boundary invents no reason; identical refusals are identical responses |
| **Transport failures** | Unknown warrant, nothing to settle, ledger failure at settlement, ledger failure at attempt (refusal, not error), `partial` (R43/R49), blank override reason; every error keeps its own class name; `BaseException` is not swallowed; an error writes nothing |
| **Status** | Projects the two owned facts; follows the override; derives nothing; takes no argument; changes nothing when called twice |
| **Deterministic responses** | Six properties, §5 above |
| **API isolation** | Six guards, §6 above; the surface is exactly five names; both vocabularies are closed; there is no `execute` and no `run`; one collaborator and no state; two APIs over one Kernel agree; construction refuses a non-Kernel |

---

## 8 · Quality gates

| Gate | Result |
|---|---|
| C17 tests | **52 passed, 0 failed** |
| C17 + C16 + C15 + C9.1 + all foundation suites | **1,456 passed, 1 pre-existing failure** |
| Architecture guards (7 modules) | **243 passed, 1 skipped, 0 failed** |
| Ruff — C17 source and tests | **All checks passed** |
| Line length | 85 source / 82 tests (limit 100) |
| Size | **61 AST statements** — the Kernel it projects is 163 |
| C1–C16 untouched | **0 modified files** in `foundation/`, `ledger/`, `kernel/` or `coordinator/` |

The single failure is
`test_foundation_clock.py::test_only_the_clock_module_reads_the_machines_wall_clock`,
caused by `launcher/boot.py` reading ambient time **in the working copy**.
It is the pre-existing failure recorded at C15.0 and proven absent at that
tag. C17 adds no ambient-time read; adding the package disturbed no guard.

---

## 9 · New findings

### R52 — a Kernel defect reaches the caller as a response, not a crash · **Medium**

`_dispatch` catches `Exception`, which is what makes §7.5's *"refusals are
data, not exceptions"* extend to the exceptions the Kernel legitimately
raises. The same catch will absorb a genuine defect inside the Kernel and
present it as an `ERROR` response.

**Deliberate, and the trade a boundary makes.** Mitigated by carrying the
exception's own class name verbatim — nothing is anonymised, and a caller
can tell `InvalidReceipt` from `LedgerUnavailable` without a traceback.
`BaseException` is excluded so an interrupt still crosses.

The residual is that an unexpected `TypeError` inside the Kernel looks, at
this boundary, like an ordinary error response. Recorded rather than
mitigated further: distinguishing "expected Kernel exception" from
"defect" would require this module to hold a list of the Kernel's
exception types, which is a second vocabulary and a second thing to keep
in step.

### R53 — the inbound direction has no wire representation · **Medium**

The transport is **in-process**. Outbound is fully JSON-ready — every
response serialises, asserted for all five operations. Inbound is not:
`authorize()` takes an `ExecutionRequest` and `settle()` takes an
`ExecutionOutcome`, both Foundation values.

**A surface in a separate process therefore cannot yet call this API.** It
would need a deserialiser for `ExecutionRequest`, `Attestation` and
`Consequence`, none of which exists — and building one **here** would make
this boundary the author of `reversibility_class`, which ADR-0022 D2
forbids.

Stated as a scope limit rather than a defect: the brief asked for a
transport and forbade new runtime dependencies, and an in-process boundary
is what those two constraints leave. Whoever needs an out-of-process
surface needs a decision about **where** a request is assembled — a
courier question, not a transport one.

### R54 — the roadmap and the briefs disagree on component numbers · **Low**

Roadmap §2 assigns C16 to Execution Path Unification and C17 to the
Objective Engine. The briefs assigned C16 to the Execution Coordinator and
C17 to the Kernel API. Both roadmap entries remain unbuilt — Execution
Path Unification is R51, and the Objective Engine remains BLOCKED on §5
R1.

Recorded so a future verification report is unambiguous about which
component a tag certifies. Not resolved here: renumbering is a roadmap
decision.

---

## 10 · Carried, untouched

R34 · R37 · R38 · R39 · R40 · R41 · R43 · R44 · R45 · R46 · R47 · R48 ·
R49 · R50 · R51 — unchanged and not solved. R43/R49 is reached at this
boundary and reported as an `ERROR` response naming `InvalidReceipt`;
the underlying gap is untouched.

---

## 11 · Preservation

C1–C16 untouched — zero modified files in `foundation/`, `ledger/`,
`kernel/` or `coordinator/`. The Kernel is consumed exactly as shipped,
through its public surface only: `authorize`, `attempt`, `settle`,
`invalidate`, `override`, `outstanding_count`.

No specification, roadmap, amendment or ADR modified. **No new ADR, no new
constitutional vocabulary, no new runtime dependency, no speculative API,
no business logic.** The desktop UI is not wired. C18 not begun. No
commit, no tag, no Rule 001.

**STOP.** Awaiting Hermes audit.
