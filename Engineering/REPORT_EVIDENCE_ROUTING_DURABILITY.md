# KALPAVRIKSHA — CANONICAL EVIDENCE ROUTING & DURABILITY REPORT

**Date:** 2026-08-19 · **Base:** `ccbb143` == `origin/main`, ahead 0, behind 0

**Yes — a fresh process now recovers the exact Evidence Verification produced.**

---

## 1. Git Truth

`HEAD == origin/main == ccbb143`, ahead 0, behind 0, nothing staged. Protected worktree
(5 modified, 111 untracked) untouched. No reset, no clean.

---

## 2. The boundary Evidence used to fall off

Verification produced a full record; the transport carried two fields of it:

```python
payload = {"verdict": verdict, "evidence_id": evidence_id}
```

`PlanHistory` stored the same two. So after a restart nothing could answer *what was
observed, when, by which Environment verifier, against which checks, or which of them
failed*. **An `evidence_id` is a correlation key, not evidence.**

---

## 3. Canonical serialization

`Evidence.as_dict()` / `Evidence.from_dict()` on the canonical
`verification.evidence.Evidence`, with matching pairs on `ObservationCheck`,
`ExpectedOutcome` and `CheckResult`. **One** serializer, because the alternative is three
that drift. No `EvidenceV2`, no second store.

Every field survives: `evidence_id`, `worker`, `environment`, `captured_at`,
`expected.description`, every `ObservationCheck`, `observation`, `verdict`, every
`CheckResult`, `errors`.

`captured_at` renders ISO-8601 and is read back with `fromisoformat` — never replaced.
`from_dict` reconstructs only: the Verdict is **read**, never re-derived from
`check_results`, because Verification is the only thing permitted to decide one.

The projection is JSON-plain — asserted by round-tripping through `json.dumps`/`loads`
and by checking that no nested value is a `datetime`, `Enum` or dataclass.

---

## 4. Runtime → Mission Control

`_verify()` already held the authoritative object; it now forwards
`evidence=evidence.as_dict()` alongside verdict and id. The Runtime does not read
`worker`, `environment`, `observation` or the checks — it stays domain-agnostic and
transports an opaque canonical projection. It simply stops being where Evidence is
discarded.

---

## 5. `VERIFICATION_COMPLETED` contract

```json
{
  "verdict": "matched",
  "evidence_id": "ev-browser-1",
  "evidence": { "...the canonical record..." }
}
```

Nested, not flattened: `verdict` and `evidence_id` stay top-level for compatibility and
searchability. **Additive** — `evidence` is optional, and callers passing only the old two
keep working with no `evidence` key. Mission Control does not read, validate or modify it.

---

## 6. PlanHistory retention

`StepRecord.evidence: dict | None`, stored from the actual event, carried through
`as_dict`/`from_dict`. Nothing is filled in when an event carries none.

---

## 7. Event-log persistence

Reused as-is. `PersistenceService` already subscribes to all events, projects them with
`event_to_dict()` and appends to durable storage — and the payload is JSON-plain, so it
persists without any change to the persistence layer.

---

## 8. Fresh-process reconstruction — the acceptance gate

Process A writes the event; **a genuinely separate interpreter** (`subprocess`, disk only,
no providers, no Environment re-execution) locates the step and rebuilds the record.
Asserted equal on `evidence_id`, `worker`, `environment`, `captured_at`, expected
description, checks, observation, verdict, check results and errors.

---

## 9. Historical backward compatibility

A record written before this commit — verdict and id, no `evidence` key — loads
successfully, keeps both, and reports `evidence is None`. That is the truth about it.
Nothing is synthesised from the id.

---

## 10. Fabricated Evidence removed

`launcher/boot.py` rebuilt an `Evidence` per step from an id and a verdict, filling in:

```python
worker="filesystem"                  # for EVERY step, whatever the domain
environment="filesystem_environment"
captured_at=datetime.now(UTC)        # report time, not observation time
observation={}
check_results=[]
```

A Browser step came back claiming a filesystem worker; an observation made earlier
acquired the timestamp of the moment the report was generated.

Both callbacks **discarded** the `Report` they built, and `report_mission_outcome()` is
pure — it persists nothing. So this was dead code whose only effect was to make
fabrication look supported. **64 lines removed**, with a comment recording what was there
and why it went. An AST test now asserts `boot.py` constructs no `Evidence` at all: only
Verification may produce it.

---

## 11–12. Identity, observation, checks, results

| guarded | proof |
|---|---|
| Browser identity | `worker == "browser"`, `environment == "browser_environment"`, explicitly `!= "filesystem"` |
| Filesystem identity | round-trips unchanged |
| Observation | `{"url": "https://example.com/", "title": "Example Domain"}` exact after restart |
| Expected checks | `field=url_normalised, operator=equals, value=https://example.com` survive |
| Check results | both `passed=True` and `passed=False` cases, with `actual_value`; never derived from the verdict |
| ERROR evidence | `Verdict.ERROR` stays ERROR, message preserved — not downgraded to NOT_MATCHED or None |

---

## 13. Mutation proof

| mutation | tests failed |
|---|---|
| A — drop `observation` from the projection | **5** |
| B — force `worker` to `"filesystem"` (the launcher defect) | **5** |
| C — `captured_at = datetime.now()` on reconstruction | **5** |

All restored; 19/19 pass. The suite validates value flow, not class existence.

---

## 14. Regression delta

Named failure sets against `ccbb143` across verification, mission_control, missions
history, persistence (service/restart/serialization/replay/schema), runtime, the three
domain verification suites and gateway wiring:

| | |
|---|---|
| Baseline | 12 |
| After | 12 |
| **Introduced** | **0** |

One process note: an earlier run of this comparison reported "0 failures" because the file
list contained a suite that does not exist (`tests/test_persistence.py`) and pytest aborted
before running anything. Caught and corrected before it was used as evidence — a clean
number from a run that never happened is worse than a failure.

---

## 15. Wiring truth after repair

| | |
|---|---|
| Verification → canonical Evidence | **BUILT + WIRED** |
| Evidence → Mission event | **WIRED** |
| Evidence → PlanHistory | **WIRED** |
| Evidence → durable Persistence | **WIRED** |
| Evidence → fresh-process reconstruction | **WIRED** |
| Evidence → Reporter | **NOT YET WIRED** |

---

## 16–17. Deferred, deliberately

**Reporter** untouched — `brain/reporter.py`, `_describe_result()` and the Founder Surface
wording are unmodified. Reporter wiring cannot be validated until exact Evidence reaches
it; now it can, and that is the next mission.

**Global fail-closed** unchanged. Many integrated capabilities still lack generic
verification contracts, and breaking them to finish this mission would be the wrong trade.

**Execution architecture** unchanged — no new Worker, Gateway, Executor or Verifier.
**Cross-step provenance** untouched; it genuinely does not exist yet.

---

## Verdicts

| | |
|---|---|
| CANONICAL EVIDENCE SERIALIZABLE | **READY** |
| FULL EVIDENCE REACHES MISSION CONTROL | **READY** |
| FULL EVIDENCE REACHES PLAN HISTORY | **READY** |
| FULL EVIDENCE PERSISTS TO DISK | **READY** |
| FRESH PROCESS RECONSTRUCTS EXACT EVIDENCE | **READY** |
| ORIGINAL CAPTURE TIME PRESERVED | **READY** |
| WORKER / ENVIRONMENT IDENTITY PRESERVED | **READY** |
| OBSERVATION PRESERVED | **READY** |
| EXPECTED CHECKS PRESERVED | **READY** |
| CHECK RESULTS PRESERVED | **READY** |
| NO FABRICATED EVIDENCE | **READY** |
| OLD HISTORY STILL LOADS | **READY** |
| REPORTER WIRING TOUCHED | **NO** |
| GLOBAL FAIL-CLOSED ENABLED | **NO** |
| EXECUTION ARCHITECTURE CHANGED | **NO** |
| INTRODUCED TEST FAILURES | **0** |

---

## The question

> *Can a fresh Kalpavriksha process now recover the exact Evidence that Verification
> actually produced, rather than only knowing an evidence ID and a Verdict?*

**Yes.** A separate interpreter reading only the event log rebuilds the record with its
original capture time, its true worker and environment, the full observation, the checks it
was measured against, each check's result and actual value, its verdict and its errors.

What it cannot do — and must not — is invent any of that when a record predates this
change. Those load with `evidence = None`, which is the truthful answer.
