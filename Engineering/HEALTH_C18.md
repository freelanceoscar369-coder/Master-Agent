# Health Report — Sprint 1, Component 18: Runtime Integration Layer

**Type:** Implementation health report. Working-directory evidence only.
**Date:** 2026-08-06
**Status:** Complete. **Not committed, not tagged, not merged, not pushed. No Rule 001.**
**Built on:** `kalpavriksha-s1-c15.0` — commit `c565244`, with C16 and C17 present and untracked.
**Ground:** Kernel Specification · ADR-0022 · ADR-0023 · Roadmap v2 (+ Amendments 001–003) · VEDA 01–04.

---

## 1 · What was built

| File | | |
|---|---|---|
| `src/master_agent/runtime_bridge/codec.py` | new | 311 lines, **58 AST statements** |
| `src/master_agent/runtime_bridge/runtime.py` | new | 284 lines, **62 AST statements** |
| `src/master_agent/runtime_bridge/__init__.py` | new | ten exported names |
| `tests/test_runtime_bridge.py` | new | **81 tests** |

**124 statements of implementation.** The Kernel it bridges to is 163.

```
Runtime(kernel)
    handle(envelope) -> dict          the transport door
    execute(request, work) -> Execution   the in-process door

codec: encode_request / decode_request / encode_outcome / decode_outcome
```

**Package name.** `master_agent/runtime_bridge/`, deliberately **not**
inside `master_agent/runtime/` — that package is the shipped Runtime
Engine (MB024), and importing through its `__init__` would give this layer
a dependency the brief forbids. A test asserts the package is never
reached.

---

## 2 · R53 — resolved, and where the resolution had to live

### 2.1 What R53 was

C17 recorded it: the Kernel API's outbound direction is fully JSON-ready,
and its **inbound direction is not**. `authorize()` takes an
`ExecutionRequest`, so a surface in another process could not call it —
and building a decoder *inside the Kernel API* would make that boundary
the author of `reversibility_class`, which ADR-0022 D2 forbids.

### 2.2 The resolution

**The decoder belongs to the Runtime, because the Runtime is the caller.**

ADR-0022 D2 names the role:

> *"Both the value and the attestation come from **C12, the owner §4.3
> names**. **The caller is a courier, not an author.**"*

The Runtime is the component standing between a surface and the Kernel
API. Assembling a request from what a surface sent is precisely what a
courier does — it carries a value it did not decide. The Kernel API is
**not** the caller; it is the Kernel's own projection, one layer below,
and a decoder there would put request construction inside the authority's
own boundary.

```
   surface ──(wire)──► Runtime.decode_request ──► ExecutionRequest
                          ▲ courier                      │
                          │                              ▼
                    C12 gave the class            KernelApi.authorize
                    to the surface, per D2               │
                                                         ▼
                                                      Kernel
```

**Nothing in this layer originates a `reversibility_class`.** It arrives
on the wire from a surface that obtained it from C12. The codec adds
**zero**: no default, no inference, no fallback. A payload without the
field does not decode — ADR-0022 D1's *"required, with no default: a
default would be a guessed class"* holds across the boundary, asserted
per-field for all eight required fields.

**C17 is unmodified.** The resolution cost the Kernel API nothing.

### 2.3 The line C9 draws, kept visible on the wire

> *"A request that is merely **malformed** is not a constitutional refusal
> and must not become one, or the ledger fills with records of callers
> getting the shape wrong."*

| Failure | Raises | On the wire |
|---|---|---|
| A key is missing, or a value is outside a closed vocabulary | `InvalidEnvelope` | `type: "InvalidEnvelope"` |
| A blank capability, a stale attestation, a null consequence | the value's own error | `type: "InvalidExecutionRequest"` |

The lookups and enum conversions happen inside one guarded step; the
Foundation value is constructed **outside** it. **No constitutional error
is ever wrapped, renamed, or hidden behind a transport one** — asserted
directly, including that `InvalidEnvelope` is not in the raised type's
ancestry.

### 2.4 What survives the round trip

Proven, not assumed: every `ReversibilityClass`, every `ActionClass`,
every `ExecutionOutcome`, every attestation with its attestor and
timestamp, `target_ref` present and absent, §14.1's marker as *itself*,
and a **real quartet** whose `Decimal("12.50")` returns as a `Decimal`
rather than a float — C6 renders the amount as a string precisely so that
crossing JSON loses no precision, and the decoder reads it back through
`Decimal`.

---

## 3 · Constitutional compliance

| Requirement | Held by |
|---|---|
| §3.5's four operations, and no fifth | `Operation` is C17's, unextended; `execute` is not a wire operation and is refused as one |
| §4.5's lifecycle crosses end to end | authorize → attempt → settle through dictionaries only, ledger reads back `IntentRecord · AttemptRecord · Receipt` |
| §6.1 — the caller executes | `work` is a callable and stays in-process; a remote surface takes a token and executes on its own side |
| §6.3 — settlement is mandatory | `execute()` delegates wholly to C16, which guarantees it |
| §7.5 — refusals are data | A refusal crosses as `kind: "refused"` carrying C8's own seven keys; identical refusals are identical envelopes |
| §8.4 — never retry an irreversible action | The bridge adds no loop; C16's rule is exercised through it |
| §11.3 — fail closed, no buffering | A ledger failure crosses as an error and nothing is retried, queued or softened |
| §11.8 — no confirmation parameter | Asserted across both doors and against the package source |
| §14 R2 — determinism | No clock, no `uuid4()`, no id, no timestamp; two Runtimes over two Kernels answer identically |
| ADR-0022 D2 — courier, not author | §2.2 |
| ADR-0023 — the two carried fields | Both required on the wire; neither defaulted |

**No constitutional behaviour is mocked in any test.** Every one runs a
real Kernel over a real ledger. The only doubles are the admission
provider the Kernel's own suite already ships and a piece of work that
answers what it was told to.

---

## 4 · Ownership

### 4.1 Serialization ownership — **the Runtime**

The codec is the only place in the system that turns a wire payload into a
Foundation value. It follows the precedent `ledger/receipt_ledger.py`
already set: **Foundation writes projections; consumers read them.** No
`from_dict` was added to any frozen value, and `foundation/` is untouched.

Encoding is the value's **own** `as_dict()`, returned unaltered — the
encoder exists so the boundary has a named pair and so a round-trip test
means something, not because there is a second shape.

**The codec validates nothing.** Every Foundation value validates at
construction, and a decoder that checked the same things would be
duplicated validation that drifts. Asserted: `strip()`,
`canonical_attestor`, `is_stale`, `exceeds(` and `is_intelligence_only`
appear nowhere in it.

### 4.2 Transport ownership — **the Runtime**

One envelope in, one envelope out, three keys each way:

```
   in    {"operation": "authorize", "arguments": {"request": {…}}}
   out   {"operation": "authorize", "kind": "ok", "payload": {…}}
```

`kind` and `operation` are C17's vocabularies, **neither extended**. The
arguments map uses the Kernel API's own parameter names, so there is no
translation table to drift.

**No wire field was added** — no status code, no envelope version, no
request id, no timestamp. A field nobody reads is a field somebody will
eventually depend on. Asserted key-for-key, including that an `authorize`
payload is exactly C4's twelve.

Every answer has the same three keys **whatever happened** — success,
refusal, unknown operation, empty envelope — so a caller parses once.

### 4.3 Lifecycle ownership — **composition only**

Given one Kernel, the Runtime constructs the Kernel API and the Execution
Coordinator over it and holds them for its own life. It **creates no
Kernel**, opens no resource, starts nothing and stops nothing — there is
no `start()`, no `close()`, and no state to leak. `__slots__` is
`{"_api", "_coordinator"}`.

The lifecycle that matters is §4.5's, and that one belongs to the Kernel.
The Runtime carries it across the boundary and owns none of it.

---

## 5 · Hidden dependency audit

Every import in the package, checked by AST across all three modules:

| Class | Result |
|---|---|
| Internal | `master_agent.foundation.*`, `master_agent.kernel`, `master_agent.coordinator`, `master_agent.api`, `master_agent.runtime_bridge` — **C1–C17 only** |
| `master_agent.runtime` (MB024's engine) | **Not reached** — asserted by name |
| Any surface (`ui`, `desktop`, `dashboard`, `cli`, `launcher`, `voice`) | **None** |
| Any other subsystem (`orchestrator`, `executor`, `planner`, `missions`, `mission_control`, `broker`, `ai_infrastructure`, `permissions`, `plugins`, `providers`, `verification`, `memory`) | **None** |
| Ledger | **None** — the bridge writes to no store |
| Clock | **None** — no second timeline |
| Runtime dependency | **None.** 18 names checked, including `http`, `socket`, `threading`, `asyncio`, `multiprocessing`, `concurrent`, `queue`, `subprocess`, `flask`, `fastapi`, `starlette`, `uvicorn`, `requests`, `aiohttp`, `pydantic`, `websockets`, `grpc` |
| Ambient randomness or timing | **None** — `uuid`, `random`, `monotonic`, `perf_counter` checked against **executable identifiers**, not source text |

**No HTTP server was built.** The Roadmap requires none in Sprint 1, and
the transport is a function call over a mapping — a test round-trips an
envelope through nothing but `json` and a dict, and another proves any
`Mapping` works, including a read-only `MappingProxyType`.

---

## 6 · Green component audit

| Component | Status |
|---|---|
| **Foundation** (C1–C14) | **Unmodified** — `git status` clean for `src/master_agent/foundation/` |
| **Ledger** (C13) | **Unmodified** |
| **Kernel** (C15) | **Unmodified** |
| **Coordinator** (C16) | **Unmodified** |
| **Kernel API** (C17) | **Unmodified** — R53 was resolved without touching it |
| `master_agent/runtime/` (MB024) | **Unmodified and not imported** |
| Architecture guards | **243 passed, 1 skipped, 0 failed** — adding the package disturbed none |

Behavioural non-duplication is asserted against **executable identifiers**
rather than source text, because these modules' own docstrings name the
things they do not do:

- **Creates no Kernel state** — `Warrant`, `AttemptToken`, `Receipt`, `IntentRecord`, `AttemptRecord`, `KernelRefusal` appear in no expression.
- **Duplicates no authorization** — `_check_objective_binding`, `_check_override_state`, `_verify_attestations`, `is_suspended`, `is_terminal`, `consequence_ceiling`, `attempt_budget`, `is_expired`, `RefusalReason`, `KernelCheck`: none present.
- **Duplicates no settlement** — no `ExecutionOutcome` member is ever named; no `record_*` call exists.
- **Duplicates no execution logic** — `execute()`'s body is **one statement**, a `return` of the Coordinator's `run`, asserted by AST.
- **Never bypasses the Kernel API** — every call in `_invoke` is on `self._api`, asserted by AST.

---

## 7 · Test coverage — 81 tests

| Area | Proves |
|---|---|
| **Serialization correctness** | Encoding is the value's own projection; a request survives the round trip, and survives JSON; a real quartet survives with its `Decimal` intact; §14.1's marker survives as itself; every attestation keeps its attestor and timestamp; optional fields survive presence and absence; all four outcomes, all four reversibility classes, both action classes |
| **Deserialization correctness** | Eight required fields each fail closed when absent; a word outside a closed vocabulary does not decode; a malformed **request** raises the value's own error and is never relabelled; a null consequence and a partial quartet do not decode; a non-mapping does not decode; the decoder validates nothing itself; a stale attestation decodes and is then refused **by the Kernel**, end to end |
| **Runtime request handling** | Authorize crosses; the whole §4.5 lifecycle crosses; invalidate crosses and suspends; status crosses with no arguments; the arguments use the API's own parameter names |
| **Runtime response handling** | A refusal crosses as a refusal with C8's own seven keys; every answer has the same three keys whatever happened; no wire field is added; every answer serialises |
| **Exception propagation** | Unknown operation echoes itself; missing operation; missing argument; **a malformed envelope and a malformed request are told apart on the wire**; Kernel exceptions keep their class names; a ledger failure crosses as an error and settles nothing; an unknown outcome word; `BaseException` is not swallowed; an error writes nothing |
| **Coordinator interaction** | `execute()` runs the composed sequence and the ledger shows all three records; honours §8.5's budget; honours §8.4's irreversible rule; is a pure one-statement delegation; is **not** reachable over the transport; a refused execution never reaches the work |
| **Kernel interaction** | The five non-duplication guards of §6; holds no Kernel of its own; two Runtimes over one Kernel agree; construction refuses a non-Kernel |
| **Deterministic execution** | Two Runtimes over two Kernels answer identically; identical refusals are identical envelopes; encoding is stable; no clock; no ambient randomness |
| **Transport independence** | No runtime dependency (18 names); C1–C17 only; MB024's engine not reached; no surface imported; any `Mapping` works; `json` and a dict suffice; the surface is two doors; no confirmation parameter anywhere |

---

## 8 · Quality gates

| Gate | Result |
|---|---|
| C18 tests | **81 passed, 0 failed** |
| C18 + C17 + C16 + C15 + C9.1 + all foundation suites | **1,537 passed, 1 pre-existing failure** |
| Architecture guards (7 modules) | **243 passed, 1 skipped, 0 failed** |
| Ruff — C18 source and tests | **All checks passed** |
| Line length | 123 source (docstring table) / 83 tests — limit 100 for code, and Ruff is clean |
| Size | **124 AST statements** across three modules |
| C1–C17 untouched | **0 modified files** |

The single failure is
`test_foundation_clock.py::test_only_the_clock_module_reads_the_machines_wall_clock`,
caused by `launcher/boot.py` reading ambient time **in the working copy**.
It is the pre-existing failure recorded at C15.0 and proven absent at that
tag. C18 adds no ambient-time read.

---

## 9 · New findings

### R55 — the composed sequence is in-process only · **Medium**

`execute(request, work)` takes a callable, and a callable has no wire
representation. So §6.1's composed sequence — the one that guarantees
§6.3's mandatory settlement — is reachable from an in-process caller and
**not** from a remote surface.

A remote surface must therefore run the sequence itself: authorize,
attempt, execute on its own side, settle. Every step is available over the
transport, and the lifecycle test proves the round trip works. **But the
guarantee C16 exists to provide does not cross the wire** — a remote
caller that forgets to settle produces exactly the unsettled intent §4.4
calls *"a first-class defect."*

Stated as a scope limit rather than a defect: inventing a wire
representation for arbitrary work would be the speculative API the brief
forbids, and it is not obvious that one should exist. Closing it needs a
decision about what a remote executor is, which is a Sprint 2 question.

### R56 — an unknown operation echoes an unvalidated string · **Low**

When an envelope names an operation this system does not have, the error
envelope echoes the caller's own string back in the `operation` key. It is
**not** coerced into an `Operation` — that enum is closed, and giving a
foreign word one of its names would be worse.

The consequence is that one field of one error response is caller-supplied
text. It is never interpreted, never stored, and never reaches the ledger;
the Kernel is not called at all on that path. Recorded because a surface
that renders it must treat it as untrusted input, which is C20's and
C21's concern rather than this layer's.

---

## 10 · Carried, untouched

R34 · R37 · R38 · R39 · R40 · R41 · R43 · R44 · R45 · R46 · R47 · R48 ·
R49 · R50 · R51 · R52 · R54 — unchanged and not solved.

**R53 is CLOSED** by §2.

---

## 11 · Preservation

C1–C17 untouched — zero modified files in `foundation/`, `ledger/`,
`kernel/`, `coordinator/`, `api/` or `runtime/`. Every one is consumed
through its public surface only.

No specification, roadmap, amendment or ADR modified. **No new ADR, no new
constitutional vocabulary, no new runtime dependency, no HTTP server, no
speculative API, no UI wiring, no desktop change.** No Objective Engine
and no Mission Engine. C19 not begun.

**No commit, no tag, no merge, no push, no Rule 001.**

**STOP.** Awaiting Hermes audit.
