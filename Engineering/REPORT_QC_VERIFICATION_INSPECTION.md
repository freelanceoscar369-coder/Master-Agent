# KALPAVRIKSHA — QC / VERIFICATION CLOSED LOOP: INSPECTION & BLOCKING DECISION

**Date:** 2026-08-19 · **HEAD:** `a2930f5` == `origin/main`, ahead 0, behind 0

**Status: STOPPED at a §21 escalation condition — architectural decision required.**
No source was modified. The working tree holds only the 5 pre-existing modified files.

---

## 1. Why this stopped rather than implemented

§18 asked me to inspect first and propose the smallest architecture-consistent sequence.
Inspection found that the first step of that sequence — wiring the Verification that
already exists — **would break the working Simple baseline**, for a reason that requires
an ownership decision the brief reserves to you (§12, §21).

The evidence is in §5 below and is reproducible in one command.

---

## 2. Repository truth

| | |
|---|---|
| LOCAL HEAD | `a2930f5` |
| REMOTE origin/main | `a2930f5` |
| AHEAD / BEHIND | 0 / 0 |
| Worktree | 5 modified tracked, 111 untracked — untouched |

---

## 3. The good news: this architecture already exists and is correct

The principle in §2 and §4 of the brief is **already implemented**, and implemented well.

`verification/verifier.py` — `Verifier.verify()`:

> *"`verify()` never looks at an ExecutionResult, never trusts a Worker's own claim that
> something succeeded — it always re-observes reality fresh … A Worker whose Action has a
> bug that makes it silently no-op will still get an honest NOT_MATCHED Verdict, because
> Verification never asks the Action whether it thinks it worked."*

`Verdict` already carries the three semantics §5 asks for, with no new enum needed:

| Brief's requirement | Existing value |
|---|---|
| requirement satisfied | `MATCHED` |
| requirement violated | `NOT_MATCHED` |
| insufficient evidence | `ERROR` — *"observation itself could not be captured"* |
| (also present) | `PARTIALLY_MATCHED` |

`ExpectedOutcome` + `ObservationCheck` (dot-path, 5 operators) express the requirement;
`Evidence` is the durable record; `evaluate_checks()` computes the verdict.
`FilesystemVerifier`, `BrowserVerifier` and `TextVerifier` all exist.

**Nothing about the core QC concept is missing.**

---

## 4. Root cause of Finding C — Verification is unwired in the Founder Edition

The live Medium run emitted `verification_started` and `verification_completed` for **all
six steps**. Every single one carried:

```json
{"verdict": null, "evidence_id": null, "verifier": "none"}
```

Because `runtime/gateway.py:107` —

```python
def verify(self, capability, payload, expected) -> Evidence | None:
    # The Plugin contract has no verification surface.
    return None
```

— and `kalpavriksha_desktop.py:320-322` registers `PluginGateway` for **browser, desktop
and filesystem alike**.

Meanwhile `launcher/boot.py:573-584` — the other composition root — *does* wire real
verification:

```python
# Wire FilesystemGateway with real verification (same pattern as BrowserGateway in tests)
runtime.register_gateway(plugin.manifest.name, FilesystemGateway(worker, ...))
```

**So the Founder Edition composition root silently lost verification that the CLI
composition root has.** No capability in the packaged app can produce Evidence, and the
mission therefore completes on execution success alone.

### The comment that encodes the false belief

`kalpavriksha_desktop.py:767-770`, on the completion path that says "Done":

> *"The result is spoken from what actually happened, so this cannot claim success for
> work that did not run: `state.result` is the Operator's own evidence, and **Verification
> has already compared it against the Step's expected outcome by the time this event
> fires**."*

It had not. That belief is precisely how Onkar was told "Done —" for an empty folder.

---

## 5. THE BLOCKER — Planner attaches text-shaped checks to every capability

Reproducible:

```
filesystem observation fields : target_exists, target_is_dir, target_path, target_size_bytes,
                                target_name, parent_listing, directory_listing, ...
                                -> has an 'empty' field?  False

ExpectedOutcome the Planner attaches:
   field='empty' operator=equals value=False  ("the answer is not blank")

VERDICT if wired as-is: not_matched
   passed=False  actual=None  error="field 'empty' not present in observation"
```

Both Planner paths — `planner/direct.py:146` and `planner/parsing.py:190` — attach
`SuccessSpec(...).to_expected_outcome()`, which delegates to MB035's `expect()` and
**always** emits the text check `not_empty()` (`field="empty"`). Only `TextVerifier`'s
observation has an `empty` field.

**Consequence:** wiring the existing `FilesystemGateway` into the Founder Edition today
would return `NOT_MATCHED` for a folder that genuinely exists on disk. Every Simple folder
mission — the baseline that currently passes — would begin reporting failure.

This is not a bug in either component. `TextVerifier` + text checks are coherent together;
`FilesystemVerifier` + filesystem observation are coherent together. What was never
reconciled is **who translates a Step's stated expectation into checks appropriate to the
observation shape of the capability that will run it.**

### Why the completion gate cannot ship without this decision

The §6 rule — *no evidence ⇒ fulfilment not established* — is correct and small. But
applied today, when **no** gateway produces Evidence, it would stop Simple folder missions
saying "Done" too. Gating requires Evidence to exist; Evidence requires the verifiers to be
wired; wiring them requires this decision. The three are one knot.

---

## 6. The decision I need from you

**Who owns turning a requirement into checks for a specific capability's observation?**

| Option | Shape | Cost / risk |
|---|---|---|
| **1. Planner emits domain-appropriate checks** | Planner learns each capability's observation fields | Couples the Planner to capability internals; contradicts the spirit of §14 |
| **2. The Gateway/Verifier builds domain checks from the Step's stated expectation** | `FilesystemGateway` already derives the target path from the payload — it would also derive `target_exists` style checks | Smallest change, consistent with existing ownership. The *requirement* stays the founder's/Planner's `description`; only the *mechanism* of checking is domain-local |
| **3. `ExpectedOutcome` gains a domain tag; a resolver picks the check set** | New field on a shared contract | Touches a contract many things depend on |

My recommendation is **Option 2**, on the reading that `ExpectedOutcome.description`
("Folder 'Research' exists at Desktop") is the authoritative requirement, while `checks`
are verification *mechanism*. A verifier supplying checks for its own observation shape
implements the stated requirement rather than redefining founder meaning, so §14 is
preserved. But this is an ownership change to a Verification contract, and §21 says to stop
rather than improvise it.

---

## 7. Implementation Consequence Matrix

| Concept (brief §) | Classification | Note |
|---|---|---|
| Verification independent of execution success (§4) | **ALREADY EXISTS** | `Verifier.verify()` re-observes; never reads `ExecutionResult` |
| Verdict incl. insufficient-evidence (§5) | **ALREADY EXISTS** | `MATCHED` / `NOT_MATCHED` / `PARTIALLY_MATCHED` / `ERROR` |
| Requirement contract (§3A) | **ALREADY EXISTS** | `ExpectedOutcome` + `ObservationCheck`; `Intent.success_criteria` upstream |
| Evidence contract (§3C) | **ALREADY EXISTS** | `Evidence`, with `evidence_id`, observation, check results |
| Per-capability verifiers | **ALREADY EXISTS** | `FilesystemVerifier`, `BrowserVerifier`, `TextVerifier` |
| Verifying gateway | **EXISTS BUT UNWIRED** | `FilesystemGateway` wired in `launcher/boot.py`, **not** in the Founder Edition |
| Production BrowserGateway | **GENUINELY MISSING** | `BrowserGateway` exists only as a test double in `tests/runtime_test_support.py` |
| Founder Edition verification wiring | **REQUIRES REPAIR** | `PluginGateway.verify()` returns `None` for every capability |
| Requirement→check translation per domain | **BLOCKED / ARCHITECTURAL DECISION REQUIRED** | §5 above — the knot |
| Completion gated on established conformance (§2, §11) | **REQUIRES MINIMAL EXTENSION** | Small once Evidence exists; blocked until then |
| Fail-closed on missing evidence (§6) | **REQUIRES MINIMAL EXTENSION** | `Verdict.ERROR` already means this; nothing consumes it |
| QC judges, does not repair (§7) | **ALREADY EXISTS** | Verifier returns Evidence; it corrects nothing |
| Observation result retention (§13) | **GENUINELY MISSING** | `step_3` completed with no result field of any kind |
| Cross-step reference/resolution (§13) | **GENUINELY MISSING** | `Step.payload` fixed at plan time |
| Dependency invalidation (§9) | **EXISTS BUT UNWIRED** | `depends_on` expresses order; nothing invalidates downstream on QC failure |
| Selective recovery boundary (§8) | **GENUINELY MISSING** | — |
| Progress-sensitive loop protection (§10) | **PARTIALLY EXISTS** | `max_attempts` / retry exists in `RuntimeEngine`; no no-new-information detection |
| Path semantics (§12) | **REQUIRES REPAIR — decision needed** | `location`+`path` double-applied; see §8 |
| Reporter communicates authoritative result (§11) | **REQUIRES REPAIR** | Currently infers success from step success |
| New `QCEngine` / `QualityManager` | **NOT NEEDED** | Everything maps onto existing contracts |

---

## 8. Second decision — path semantics (§12)

Confirmed deterministic and long-standing:

| step | payload | resolved |
|---|---|---|
| `Filesystem.CreateFolder` | `{"name": "KV_…", "location": "Desktop"}` | `…\Desktop\KV_…` |
| `Filesystem.WriteFile` | `{"path": "Desktop/KV_…/page_info.txt"}` | `…\Desktop\**Desktop**\KV_…\page_info.txt` |

`location` names a base; `path` is resolved **relative to that base**; the plan supplied
`Desktop/…` for both, so `Desktop` was applied twice.

`C:\Users\DELL\Desktop\Desktop\` **pre-existed from 2026-07-31**, already holding
`demo_api` and `Research on my Desktop` — this has been depositing stray files for weeks.

§12 requires one authoritative semantic (`location` + `relative_path`, **or**
`absolute_path`) and forbids implementing both. That is your choice to make; I have not
guessed it.

---

## 9. Proposed sequence, once the two decisions are made

1. **Decision 6** → give verifiers domain-appropriate checks. Prove Simple folder missions
   verify `MATCHED` against real disk state.
2. Wire the verifying gateway into the Founder Edition; add a production `BrowserGateway`.
   Evidence now exists.
3. **Gate completion on established conformance**; missing Evidence ⇒ not established.
   Expected first live result: the Medium objective correctly does **not** say Done — the
   §16 outcome.
4. **Decision 8** → one path semantic; the file lands in the requested folder.
5. Retain capability results (§13) — required before any cross-step reference can exist.
6. Cross-step consumption, so contents come from the observation rather than a prediction.
7. Recovery from the minimum invalidated dependency (§8, §9).
8. Progress-sensitive loop protection (§10).

Steps 1–3 are one shippable slice and deliver the constitutional fix: Kalpavriksha stops
claiming fulfilment it has not established.

---

## 10. What I did not do, deliberately

- No source modified — the knot in §5 means any wiring I shipped alone would regress the
  Simple baseline.
- No `QCEngine`/`QualityManager` — not needed; existing contracts cover it.
- No Reporter patch — §11 forbids treating the symptom.
- No path-semantic guess — §12 reserves that choice.
- No live packaged acceptance run — there is nothing new to accept yet, and §15's visible
  acceptance is meaningful only against an implemented change.

---

## Final checkpoint

```
LOCAL HEAD:         a2930f5
REMOTE origin/main: a2930f5
GITHUB SYNC:        YES
AHEAD:              0
BEHIND:             0
WORKTREE PROTECTED: YES
```
