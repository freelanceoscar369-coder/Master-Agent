# Conflict Report — C15 Part 2: K1's liveness gate

**Type:** Constitutional conflict. **STOP. No code, no tests, no exports, no commit, no tag.**
**Date:** 2026-08-06
**Verdict:** **BLOCKED.** K1 cannot be implemented until one question is answered: **does a `READY` or `WAITING` objective refuse a mint, and if so, with what reason?**

---

## 1 · The conflict

Two frozen documents state different rules for the same check, and the ratified ADR follows the one the Kernel's own refusal vocabulary cannot express.

### 1.1 Kernel Specification §7.2 K1 — the Kernel's own specification

> **K1 · Objective binding.** `objective_id` present, resolves to an admitted objective in a **non-terminal** state.
> *Refuses:* no objective · unknown objective · objective already completed, failed, or cancelled.

Under this reading, `READY` and `WAITING` are non-terminal and **pass K1**.

### 1.2 Objective Engine Specification §10.2 and §10.3

> *"state change (waiting, resumed) ────────────► **K1 keeps refusing while the objective is not EXECUTING**"*
>
> | `state` | **K1's liveness gate** | **Non-`EXECUTING` ⇒ no mints** |

Under this reading, `READY` and `WAITING` are refused.

### 1.3 ADR-0021 D5 — ratified, and it follows §10.3

> *"`READY` and `WAITING` therefore refuse mints. That is intended."*

**The founder has ratified the stricter reading.**

---

## 2 · Why this blocks implementation rather than being a preference

**C8's `RefusalReason` is frozen at `kalpavriksha-s1-c8.0` and has no member for it.**

The objective-related members are exactly three:

```
OBJECTIVE_MISSING · OBJECTIVE_UNKNOWN · OBJECTIVE_TERMINAL
```

A `READY` objective is not missing, not unknown, and **not terminal**. Refusing it requires a reason that does not exist, and:

- **`OBJECTIVE_TERMINAL` would be a lie** in a permanent record — the objective is alive. §7.5 requires refusals to be recorded, so an inaccurate reason is an inaccurate audit entry, not a cosmetic issue.
- **Adding a member modifies C8**, which is frozen and GREEN at `c8.0`, and the enum is closed by constitutional intent — C8's own tests assert the vocabulary is exactly eleven.
- **Not refusing** contradicts ADR-0021 D5, a founder decision ratified yesterday.

There is no fourth option that does not either falsify a record, modify a frozen component, or contradict a ratified decision.

---

## 3 · A citation error in ADR-0021, and it is mine

**ADR-0021 D5 attributes the liveness gate to *"Kernel Specification §10.3."***

Measured: **Kernel Specification §10.3 is *"The four invariants that make learning safe"*** — a different subject entirely. The liveness-gate text is **Objective Engine Specification §10.2 and §10.3**.

**I wrote that citation and it is wrong.** It matters here because it makes D5 read as though the Kernel's own specification requires the strict gate. It does not — §7.2 K1, the Kernel's own clause, states the *lenient* rule, and the strict rule comes from the Objective Engine's specification of what it expects the Kernel to do.

Correcting the citation does not resolve the conflict. It clarifies that the two documents genuinely disagree rather than one having been misread.

---

## 4 · What is and is not blocked

| | |
|---|---|
| **Blocked** | K1's state validation — the single decision in §5 |
| **Not blocked** | Everything else in this brief: the admission provider port, admission lookup, `AdmissionRecord` integration, override read, outstanding-intent registration. All are implementable the moment the decision lands |

**C15 Part 1 stands.** No shipped component is at risk, C1–C14 remain GREEN, and no defect was found in any of them. R28 and R29 are resolved by the founder decisions in this brief and are **not** the blocker.

---

## 5 · The decision

**Does K1 refuse a non-terminal, non-`EXECUTING` objective?**

### Option A — K1 refuses only on terminal, per Kernel Specification §7.2

`READY` and `WAITING` pass K1. The liveness gate becomes the Objective Engine's responsibility: it publishes `EXECUTING` only when it means it, and the Kernel does not second-guess that.

**Cost: none. Zero code change, zero frozen-component change, and C8's vocabulary already covers it exactly.** Consistent with §1.2 — *"attestation, not reimplementation"* — and with §3.4's test: *does another component already own this question?* The Objective Engine owns the objective's state.

**Requires:** amending ADR-0021 D5 to match, and correcting its citation.

### Option B — K1 refuses on non-`EXECUTING`, per ADR-0021 D5

Requires a new `RefusalReason` — `OBJECTIVE_NOT_EXECUTING` or similar — which **modifies C8**, a frozen GREEN component, and widens a deliberately closed constitutional enum.

**Cost:** a founder decision to reopen C8, a new tag for the amended component, and re-verification of everything downstream of it.

### Option C — narrow the published record

The Objective Engine publishes an `AdmissionRecord` only while `EXECUTING`, so a non-executing objective resolves to nothing and refuses as `OBJECTIVE_UNKNOWN`.

**Rejected on inspection:** *"unknown"* would be false for an objective that exists and is merely waiting, and it would make an audit unable to distinguish a typo from a paused objective. Recorded because it is the tempting shortcut, not because it is viable.

---

## 6 · Recommendation

**Option A.**

Kernel Specification §7.2 is the Kernel's own governing clause and it is unambiguous. Option A costs nothing, changes no frozen component, and matches C8's vocabulary exactly — which is itself evidence, since C8 was built by re-deriving the refusal set from §7.2 and §11.10 and arrived at three objective reasons rather than four.

It also places the question where §3.4's test puts it: the Objective Engine owns what an objective's state means, and a Kernel that refused a `READY` objective would be second-guessing that owner rather than trusting its published record.

**If Option A is taken, ADR-0021 D5 needs one amendment and one citation fix**, and Part 2 proceeds immediately with no other change.

---

## 7 · What was not done

No file was created in `src/`. No test was written. No export was added. No frozen component was modified, no ADR amended, no `RefusalReason` invented. `master_agent/kernel/` contains the same two files it did at the end of Part 1. **Part 3 was not started.**

---

*Conflict report. Verified against Kernel Specification §7.2 and §10.3, Objective Engine Specification §10.2 and §10.3, ADR-0021 D5 and A2, and `foundation/refusal.py` at tag `kalpavriksha-s1-c8.0` on 2026-08-06. All section attributions measured, not recalled.*
