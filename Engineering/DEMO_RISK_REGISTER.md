# Demo Risk Register — Founder Edition, 12 Aug 2026

**Type:** Risk register. Engineering risks only. **No code, no commits, no tags, nothing fixed.**
**Date:** 2026-08-05
**Horizon:** 7 days
**Baseline:** C1–C8 GREEN at `kalpavriksha-s1-c8.0`. Thirteen of twenty-one components remain.

> **What the demo must prove.** Not that an assistant responds — that *Kalpavriksha autonomously executes a real objective under constitutional governance.* Every risk below is scored against that sentence. A risk that would leave a working demo which does not prove it is scored as high-impact, not low.

---

## 0 · Summary

| # | Risk | P | Impact | Owner | Resolve by |
|---|---|---|---|---|---|
| **D1** | `Objective`/`Mission` ADR unratified — blocks C11, C15, C17 | **High** | **Fatal** | **Founder** | **Immediately** |
| **D2** | Thirteen components in 7 days at measured velocity | **High** | **Fatal** | Engineering + Founder | Scope call by **7 Aug** |
| **D3** | C13 Receipt Ledger — first stateful component, on every action's critical path | Medium | **Fatal** | Engineering | C13 |
| **D4** | C16 collides with 148 uncommitted working-tree entries (R3) | **High** | Severe | Engineering | **Before C16** |
| **D5** | Test-estimate calibration is 2–3× low | **High** | Severe | Engineering | Re-plan by **7 Aug** |
| **D6** | 21 Safety-Critical Ruff findings enter the demo path with C16 | Medium | Severe | Engineering | Before R3 is committed |
| **D7** | Frozen specifications and all verification evidence are untracked | Medium | Severe | **Founder** | **Immediately** |
| **D8** | C12's classification audit (~30 capabilities) is easy to underestimate | Medium | Moderate | Engineering | C12 |
| **D9** | N1 — `intentId` exists in no field name; lands on C13 | Medium | Moderate | **Founder** (ADR) | C13 |
| **D10** | C15 exceeds its 600-line ceiling | Medium | Moderate | Engineering | C15 |
| **D11** | Ruff rule set unpinned — the gate is not reproducible | Medium | Low | Engineering | Post-demo |
| **D12** | C19 has no domain-health reporter to attest over | **High** | Low | Engineering | C19 |

**Two risks are Fatal-and-High: D1 and D2. Both need a founder decision, and both need it this week.**

---

## 1 · D1 · The `Objective`/`Mission` ADR is unratified

| | |
|---|---|
| **Probability** | **High** — open since the Implementation Blueprint; no ratification scheduled |
| **Impact** | **Fatal** — blocks C11, C15, C17. C15 *is* the Kernel |
| **Owner** | **Founder.** Not an engineering question |
| **Resolve by** | **Immediately.** It is already the binding constraint |

**Why it is fatal rather than severe.** Amendment M6 established that extracting C11 does *not* route around the ADR — C11 carries `ObjectiveState`, the ADR governs that vocabulary, and C15 depends on C11. Under option (c), the sprint stops after seven components and **the Kernel never ships.** A demo without the Kernel cannot prove constitutional governance; it can only show an assistant doing things.

**Mitigation.** Option (a): ratify. One ADR unblocks three components. Precedent exists — ADR-0014 resolved an identical collision with a synonym rather than a rename. Objective Engine Spec §13.1 already carries the recommendation and the two additive states Conflict B needs.

**Fallback if it stays open past 7 Aug.** Option (b) — narrow C11 to a mintability indicator answering only K1's two questions. Amendment M6 rates this *"a design decision beyond the roadmap"* requiring its own validation pass, so it costs a day and carries risk (a) does not.

**Escalation:** this risk has been recorded in five documents across the project and has not moved. **Recording it a sixth time is not mitigation.**

---

## 2 · D2 · Thirteen components in seven days

| | |
|---|---|
| **Probability** | **High** |
| **Impact** | **Fatal** |
| **Owner** | Engineering + **Founder** (scope) |
| **Resolve by** | Scope decision by **7 Aug** |

**Measured velocity.** Eight components across the Sprint 1 track, all value objects. C7 and C8 each took one focused session. **Remaining work is not comparable:** C13 is the first stateful component, C15 is the largest, C16 modifies six shipped files, C17 is blocked, and C12 carries a multi-day audit the roadmap explicitly says *"does not shrink."*

Roadmap estimate for the remainder: **~3,080 source lines, ~730 tests** — and §6 shows the test figure is 2–3× low.

**Mitigation — the roadmap already provides it.** §5 R10: *"The order is dependency-correct, so scope can be cut from the tail (C19–C21) without invalidating anything before it."*

**Recommended minimum demo spine**, in dependency order:

```
C9 → C10 → C12 → C13 → C14 → [C11] → C15 → C16 → C17 → C21
```

**C18 Learning Subscriber and C19 Vigilance can be cut.** C18 is provably optional — Kernel Spec §10.3: *"zero subscribers is a valid, fully functional configuration."* C19 has nothing to attest over (D12). **C20 Voice Charter cannot be cut** if anything is said to the founder — VEDA 04 D2/R4, and C21 produces the first utterance.

**The honest framing for the founder:** the choice is not *"can all thirteen ship?"* It is *"which ten prove the sentence?"* That call is worth more than any engineering speed-up available in seven days.

---

## 3 · D3 · C13 Receipt Ledger — the first stateful component

| | |
|---|---|
| **Probability** | Medium |
| **Impact** | **Fatal** — nothing executes without it |
| **Owner** | Engineering |
| **Resolve by** | C13 |

Kernel Spec §7.2 K3 and VEDA 04 A1: *"if the intent write fails, the action does not occur. No exceptions, no buffering, no fire-and-forget."* The write is on the critical path of **every** action, and *"no buffering"* forecloses the obvious mitigation for a slow write.

Every component before it has been an immutable value object with no state to corrupt. C13 is the first thing that persists, the first that can fail in a way that must abort an action, and the first requiring crash-safety and restart-ordering tests.

**Mitigation.** Measure write latency from the first slice run. **Never make the write async** — Roadmap R4: that is the one change that would void A1. Budget for the roadmap's ~65 tests to be low, consistent with §6's calibration.

**Carries D9.** C13 is also where N1 lands.

---

## 4 · D4 · C16 collides with 148 uncommitted working-tree entries

| | |
|---|---|
| **Probability** | **High** |
| **Impact** | Severe |
| **Owner** | Engineering |
| **Resolve by** | **Before C16 begins** |

`git status` reports **148 entries** — modifications to `orchestrator/`, `executor/`, `runtime/`, `broker/`, `planner/`, `plugins/`, plus ~60 untracked source files and 25 untracked test files. C16 modifies six of the same files.

The Baseline Assessment rated this ~70%, *"concentrated entirely in this one component."*

**Visible symptom today:** 49 test failures in the working directory that do not exist at any tag, and 143 Ruff findings likewise.

**Mitigation.** Commit MB032–039 **before C16 starts** — Roadmap R3: *"The window closes when C16 begins."* Two prerequisites first, or the commit imports fresh debt into history:

- **R7** — `launcher/boot.py` reads ambient time twice. Must take an injected `Clock` or join `LEGACY_AMBIENT_TIME`.
- **D6** — the 21 Safety-Critical Ruff findings below.

---

## 5 · D5 · Test-estimate calibration is 2–3× low

| | |
|---|---|
| **Probability** | **High** |
| **Impact** | Severe |
| **Owner** | Engineering |
| **Resolve by** | Re-plan by **7 Aug** |

Measured: C7 estimated ~50 tests, delivered **66** (1.3×). C8 estimated ~35, delivered **108** (3.1×).

Both overruns have one cause — enforcing invariants at construction with exhaustive parametrized coverage rather than checking them downstream. **That is the house pattern and it is why the milestones are trustworthy.** It is also not what the roadmap's estimates were calibrated against.

Applying a 2× factor to the remaining ~730 tests gives **~1,460**, against a 7-day horizon.

**Mitigation.** Treat remaining test estimates as lower bounds; re-plan D2's scope with the corrected figure. **Do not reduce test rigour to hit the date** — Rule 000, and the rigour is what the demo is meant to prove.

---

## 6 · D6 · 21 Safety-Critical Ruff findings enter the demo path with C16

| | |
|---|---|
| **Probability** | Medium |
| **Impact** | Severe |
| **Owner** | Engineering |
| **Resolve by** | Before R3 is committed |

Untracked MB032–039 code carries **14 `BLE001`** blind `except Exception`, **7 `S110`** `try`/`except`/`pass`, and **10 `PLW1510`** `subprocess.run` without `check`.

**Why these are constitutional and not stylistic:**

- A blind catch can swallow the failure a fail-closed check depends on. Kernel Spec §11 requires **eight of nine** conditions to fail closed.
- `try`/`except`/`pass` discards the failure with no record. §7.5: *"a silently refused action is indistinguishable from one never attempted."*
- An unchecked `subprocess.run` means **a failed action reads as a succeeded one** — a false Receipt, which is the one thing the ledger exists to make impossible.

**They do not block the demo today**, because the demo path runs through `foundation/` and the Kernel. **C16 Execution Path Unification routes execution through this code**, and on that day they are on the path.

**Mitigation.** Triage the 21 before R3 is committed — inventory in `RUFF_DEBT_REGISTER.md` §3.1, with file and line. Ten `PLW1510` are the priority: an unchecked exit code is a wrong receipt, not a wrong style.

**Do not run `ruff check --fix` repo-wide.** §6.1 of the register, and the C5 precedent.

---

## 7 · D7 · Frozen specifications and all verification evidence are untracked

| | |
|---|---|
| **Probability** | Medium |
| **Impact** | Severe |
| **Owner** | **Founder** (policy) |
| **Resolve by** | **Immediately** — it is one commit |

The Kernel Specification, Objective Engine Specification, First Founder Journey Specification, Roadmap v2, Amendment 001, all five VEDAs, and **all seven verification reports for eight GREEN milestones** exist in no commit.

**Three consequences:**

- **Rule 002 is unexecutable from a clone.** Grounding requires documents the repository does not contain.
- **A clone contains no proof that any milestone was verified**, though Rule 001 makes the report a GREEN criterion.
- `git clean -fdx` would destroy the roadmap, the amendment, all five VEDAs, the Kernel Specification, and every verification report. **There is no second copy.**

**Demo-specific impact.** If the demo is shown from a fresh clone or another machine, the constitutional documents the product is *about* are absent — and if a single file is lost this week, the reconstruction cost lands inside the 7-day window.

**Mitigation.** `ENGINEERING_DOCUMENT_POLICY.md` §4 proposes the split and §4.4 the backlog. **Commit the frozen specifications first** — it is one commit and it removes the Critical half immediately.

---

## 8 · D8 · C12's classification audit

| | |
|---|---|
| **Probability** | Medium · **Impact** Moderate · **Owner** Engineering · **Resolve by** C12 |

~30 shipped capabilities each need a reversibility class **and a working compensating action**. VEDA 04 R2 rates it high severity and *"easy to underestimate"*; the roadmap says it is *"the expensive half and it does not shrink"* — days, not hours.

A2 fails closed with no default classification, so **an unclassified capability cannot execute**. An incomplete audit is not a degraded demo; it is a demo where the chosen action refuses.

**Mitigation.** Classify only the capabilities the demo path uses, and let the rest fail closed — that is A2 working as designed, not a shortcut. Do it at 30, not 300.

---

## 9 · D9 · N1 — `intentId` exists in no field name

| | |
|---|---|
| **Probability** | Medium · **Impact** Moderate · **Owner** **Founder** (ADR) · **Resolve by** C13 |

Objective Engine Spec §13.1's ratified amendment says the Kernel's token is renamed `Warrant` but *"the field it carries stays `intent_id`, preserving VEDA 04 A1's `intentId` verbatim."* Shipped C4 names it `warrant_id`, with a documented reason. **`intentId` is now in no field name anywhere.**

C13 implements `recordIntent → intentId`. Without a decision it will either contradict VEDA 04 A1 or introduce `intent_id` beside `warrant_id` — the third synonym §17's Worker/Executive row forbids.

**Mitigation.** An ADR recording the synonym, following ADR-0014's precedent. **Do not rename C4** — it is frozen, documented, and GREEN. Detail in `ROADMAP_CONSISTENCY_STATUS.md` §2.2.

---

## 10 · D10 · C15 exceeds its 600-line ceiling

| | |
|---|---|
| **Probability** | Medium · **Impact** Moderate · **Owner** Engineering · **Resolve by** C15 |

Kernel Spec §14 R9 sets 600 lines: *"if the Kernel exceeds roughly 600 lines, something in it belongs somewhere else."* Estimated at ~400.

**Measured evidence the ceiling is tighter than it looks:** C8's `refusal.py` is 379 total lines for 107 executable. At that documentation density a 400-line Kernel is ~1,100 total. **The ceiling must be read as executable lines**, or it is breached on the first draft by comments.

Every §3.4 exclusion will be proposed as an inclusion under time pressure — and D2 guarantees time pressure.

**Mitigation.** Treat the ceiling as a review gate on executable lines. *Attestation, never reimplementation.* C8's `_PERMITTED_CHECKS` already removes one table the Kernel would otherwise carry, and C7's `canonical_attestor` removes another.

---

## 11 · D11 · The Ruff rule set is unpinned

| | |
|---|---|
| **Probability** | Medium · **Impact** Low · **Owner** Engineering · **Resolve by** Post-demo |

`ruff>=0.5` with no `select`. The gate is whatever version is installed; two machines can disagree about the same commit. Does not affect the demo, but it means "Ruff clean" is not a reproducible claim — and `RULE001_CLARIFICATION.md` D3 proposes making lint a Rule 001 criterion, which **requires this fixed first**.

**Mitigation.** Pin an exact version and an explicit `select` reproducing today's 21 findings, so pinning changes nothing on the day it lands.

---

## 12 · D12 · C19 has nothing to attest over

| | |
|---|---|
| **Probability** | **High** — certain unless a connector ships · **Impact** Low · **Owner** Engineering · **Resolve by** C19 |

VEDA 04 D7 requires *"a coverage check across every monitored domain,"* and §2 requires connectors to report freshness and health. **No component reports domain health today.** C19 is buildable but attests over a hand-registered set.

**Mitigation.** Amendment M9's scope: register exactly one domain — the receipts folder — per the First Founder Journey slice, and say so in the brief rather than implying a connector integration that is not in Sprint 1.

**Or cut it.** C19 is one of the two components D2 identifies as cuttable. If the demo does not speak the calm state, C19 buys nothing — and if it *does*, C19 is mandatory, because VEDA 04 §9 names shipping the reassurance before the proof as the most tempting sequencing error. **That is a founder call about the demo script, not an engineering call.**

---

## 13 · Risks explicitly excluded

| Not included | Why |
|---|---|
| Product, design, narrative and founder-experience risk | Brief scope: engineering only |
| Model or provider availability | Broker already returns a structured `BrokerRefusal` and never falls back (§11.6) |
| The 49 working-directory test failures | Symptom of D4, not an independent risk. Zero at every tag |
| The 21 Tier A Ruff findings | 19 Cosmetic, 2 Maintainability, all pre-Sprint 1. Neither blocks the demo nor Rule 001 |
| Regression in C1–C8 | Byte-identity proven by blob SHA-1 at every tag; guards enforce it |

---

## 14 · The one-paragraph version

**Two risks decide the demo, and both are founder decisions rather than engineering problems.** D1 — ratifying the `Objective`/`Mission` ADR — is the difference between a Kernel and no Kernel, and it has been open since the Implementation Blueprint. D2 — cutting scope to a defensible spine — is the difference between ten finished components and thirteen unfinished ones. Everything else on this register is manageable inside seven days by engineering alone. **Neither of those two is.**

---

## 15 · What was not done

No risk was mitigated here. No code, no configuration, no commits, no tags. This register is an inventory; every item awaits an owner's decision.

---

*Risk register compiled against the roadmap, Amendment 001, the Constitutional Kernel Specification, VEDA 04, the four companion documents produced under this brief, and measured working-directory state on 2026-08-05.*
