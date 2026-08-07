# Sprint 1 — Current Status

**Type:** Current state of shipped work. Point-in-time, and superseded by the next one.
**Date:** 2026-08-06
**HEAD:** `01497c3` · **Latest tag:** `kalpavriksha-s1-c18.0`
**Measured, not recalled:** every row below was read from `git`, from a verification report, or from a suite executed at a tag.

> This does **not** amend `SPRING_1_IMPLEMENTATION_ROADMAP_v2.md` or any of
> its amendments, and it does not supersede
> `ROADMAP_CONSISTENCY_STATUS.md`, which is a dated audit against `c8.0`.
> It records what is shipped, as of today.

---

## 1 · Shipped and verified

| # | Component | Tag | Commit | Tests |
|---|---|---|---|---|
| C1 | Canonical Clock | `kalpavriksha-s1-c1.1` | — | — |
| C2 · C3 | Principal · Warrant | `kalpavriksha-s1-c2.0` · `c3.0` | — | — |
| C4 | Warrant | `kalpavriksha-s1-c4.0` | — | — |
| C5 · C6 | Receipt · Consequence | `kalpavriksha-s1-c5.0` | — | — |
| C7 | Attestation | `kalpavriksha-s1-c7.0` | — | 66 |
| C8 | Kernel Refusal | `kalpavriksha-s1-c8.0` | `ac5e399` | 108 |
| C9 | Execution Request | `kalpavriksha-s1-c9.0` | `6bc53d4` | 102 |
| C10 | Attempt Token | `kalpavriksha-s1-c10.0` | `36d14f7` | — |
| C11 | Admission Record | `kalpavriksha-s1-c11.0` | `2e7ba68` | — |
| C12 | Reversibility Registry | `kalpavriksha-s1-c12.0` | `1bb6150` | — |
| C13 | Receipt Ledger | `kalpavriksha-s1-c13.0` | `9f9f21d` | — |
| C14 | Override | `kalpavriksha-s1-c14.0` | `7b74df7` | — |
| **C9.1** | Execution Request, reopened (ADR-0022 · ADR-0023 D2) | `kalpavriksha-s1-c9.1` | `e224fd8` | 119 |
| **C15** | **Constitutional Kernel** | `kalpavriksha-s1-c15.0` | `c565244` | **417** |
| **C16** | **Execution Coordinator** | ↓ | `cb18e9d` | **56** |
| **C17** | **Kernel API** | ↓ | `cecd972` | **52** |
| **C18** | **Runtime Integration Layer** | `kalpavriksha-s1-c18.0` | `01497c3` | **81** |

**Full suite at `kalpavriksha-s1-c18.0`: 3,085 passed · 0 failed · 1 skipped.**
Architecture guards: 215 passed · 1 skipped. Ruff repo-wide: 21, the
pre-Sprint-1 baseline, unchanged since `c8.0`.

C16, C17 and C18 share one tag because C18 imports the other two; a tag
naming C18 alone could not be checked out. See
`VERIFICATION_kalpavriksha-s1-c18.0.md` §7.

---

## 2 · The path a surface now takes to the Kernel

```
   Desktop UI · CLI · future services
        │
        ▼
   C18  Runtime Integration Layer     124 statements
        │      transport · serialization · wiring
        ▼
   C17  Kernel API                     64 statements
        │      the single integration boundary
        ▼
   C16  Execution Coordinator          73 statements
        │      §6.1's sequence, composed once
        ▼
   C15  Constitutional Kernel         163 statements
        │      3 checks · 8 attestations · 4 operations
        ▼
   C13  Receipt Ledger
```

**Every layer holds one collaborator and no state**, and each asserts its
own dependency set by test. The Kernel's §14 R9 budget is 600 statements;
it uses 163.

---

## 3 · Roadmap numbering divergence — R54

The briefs and the roadmap assign three numbers differently. **Recorded so
a verification report is never ambiguous about which component a tag
certifies.** Not resolved here; renumbering is a roadmap decision.

| # | Roadmap §2 says | Built and tagged | Roadmap entry's status |
|---|---|---|---|
| **C16** | Execution Path Unification | **Execution Coordinator** | Not built — **R51** |
| **C17** | Objective Engine | **Kernel API** | Not built — **BLOCKED** on the `Objective`/`Mission` ADR |
| **C18** | Learning Subscriber | **Runtime Integration Layer** | Not built |

---

## 4 · Roadmap components still unbuilt

| # | Component | Status |
|---|---|---|
| Execution Path Unification | 15 entry points still reach tools without a `warrant_id` | **R51 — the largest open item** |
| Objective Engine | **BLOCKED** on the `Objective`/`Mission` ADR, the longest-standing open item | Unchanged |
| Learning Subscriber | Publication is not built; the Kernel emits no events | **R45** |
| Vigilance Attestation · Voice Charter Validator · Dashboard State | Not begun | — |

---

## 5 · Open risk register

None is a Rule 001 gate. Each is documented, fails closed, and is covered
by a test asserting the gap so it cannot close unnoticed.

| # | Summary | Severity | Owner of the decision |
|---|---|---|---|
| **R34** | The A2 attestation does not bind to the carried class | High | ADR-0023 D5 specifies the close |
| **R51** | The execution path is not unified | High | A brief permitting `runtime/`, `executor/`, `orchestrator/` changes |
| **R46** | Invalidation cannot record itself — §4.5 requires all six terminal states be recorded | High | A fourth `RecordKind`, or a widened outcome vocabulary (C13 / C5) |
| **R39 · R40** | No `RefusalReason` for an envelope breach, or for `attempt()`'s four conditions | Medium | One decision about C8 closes both |
| **R43 · R49** | `partial` cannot be settled — one of §6.3's four kinds is unreachable | Medium | `settle()`'s ratified signature |
| **R41** | The payload digest is not checked at `attempt()` | Medium | §3.5 fixes the signature |
| **R47** | A suspended Kernel cannot be resumed | Medium | §3.5's surface |
| **R52** | A Kernel defect reaches a caller as an `ERROR` response | Medium | Accepted trade at the boundary |
| **R55** | The composed sequence is in-process only | Medium | What a remote executor is — Sprint 2 |
| **R57** | No inbound timeout or envelope size limit | Medium | Sprint 2, with an HTTP transport |
| **R31 · R37 · R38 · R44 · R45 · R48 · R50 · R54 · R56 · R58** | Freshness window · omitted grant validity · `read_only = 5` · receipts carry no detail · nothing is published · an objective named `all` · exception text has no home · numbering · unvalidated echo · no metrics | Low | — |

**R29 · R32 · R34(partial) · R42 · R53 are CLOSED.** R53 was closed by C18
without modifying C17.

---

## 6 · Process observations

**`Engineering/AUDIT_C16.md` is absent.** `AUDIT_C17.md` and
`AUDIT_C18.md` are on file. An audit is not a Rule 001 gate, and Hermes's
C18 audit independently verified C16 as unmodified and exercised it
through `Runtime.execute()`. Whether a retrospective C16 audit is wanted
is a founder decision.

**Forty-nine working-directory test failures persist**, across five files,
unchanged since before C16 and absent from every tag. All are *untracked
work* under Rule 001's categories — three files exist at no tag, and two
fail only against locally modified copies. They are outside Sprint 1's
component track and no brief has covered them.

---

*Measured at `kalpavriksha-s1-c18.0` on 2026-08-06. Every tag figure comes
from a verification report generated in a clean, isolated checkout; no
number here is taken from the working directory.*
