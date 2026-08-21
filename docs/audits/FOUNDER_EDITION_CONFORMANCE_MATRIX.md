# Founder Edition — Canonical Conformance Matrix

Built 2026-08-21 at baseline `1743a53b` / handoff commit `c56b9d1`.

**Method.** Every row below was reconciled against **current source**, not against
audit documents. Where an older document (`GAP_REGISTER`, `ROADMAP`, an audit, or a
Proposed ADR) claims something is missing and source proves otherwise, the document
is recorded as stale and the source wins — per the convergence brief §2 authority
order and Constitution §20 Rule 8 (observed reality wins).

**Authority reminder recorded during the read:** ADR-0001–0022 are Accepted/ratified.
**ADR-0023, ADR-0024 and ADR-0025 are PROPOSED** and are therefore design evidence
only, never binding contracts.

---

## The canonical production path, as actually wired

Traced through source, not documentation:

```
Founder types/speaks
  → desktop_shell.DesktopShellApi.send_message()          founder_edition/desktop_shell.py:375
  → app.communication.handle(request)                      communication/engine.py
  → ConversationEngine + IntentClassifier                  conversation_engine/intent.py
       ├── recognised  → answer, done
       └── routed is None ("I don't recognise this")
  → submit_objective(text)                                 injected by the composition root
  → kalpavriksha_desktop._submit_objective()               kalpavriksha_desktop.py:709
  → mission_service.intent_layer.parse() / .clarify()      brain/intent.py
  → mission_service.start(intent)                          missions/service.py
  → mission_control.submit_objective()                     mission_control/mission_control.py:167
  → RuntimeEngine.run_once()                               runtime/
  → Executive / Worker                                     desktop/, executor/, plugins/
  → Verification (gateway .verify())                       verification/
  → Evidence → Mission State / Memory
  → Reporter.report_plan_record_outcome()                  brain/reporter.py
  → back through send_message()'s return dict → Founder
```

**The composition root is `kalpavriksha_desktop.py` (1289 lines, tracked, repo
root)** — not anything under `src/master_agent/founder_edition/`. `create_window()`
has no caller inside `src/`; the only caller is this file. Any future session
looking for "where Founder Edition is assembled" should start there.

---

## Matrix

| # | Responsibility | Canonical owner | Canonical source | Current source | Classification |
|---|---|---|---|---|---|
| 1 | Founder Surface → Conversation | Brain-adjacent surface | Vision §3, §13 | `founder_edition/desktop_shell.py`, `kalpavriksha_desktop.py` | **COMPLIANT_AND_WIRED** |
| 2 | Conversational answer layer | Brain | Vision §3.1 | `conversation_engine/` | **COMPLIANT_AND_WIRED** |
| 3 | **Utterance-role understanding** | **Brain / Intent Layer** | **Brief §11, §12; Vision §3.1** | `brain/utterance.py`, consulted via `IntentLayer.decide_role()` | **WAS SPECIFIED_BUT_MISSING — now COMPLIANT_AND_WIRED** (Slice 1). All six §12 regressions live-proven |
| 4 | Intent Layer semantic understanding | Brain | Vision §3.1; ADR-0024 D7 | `IntentLayer(reasoner=...)` — the Model Router door, opened for one undecidable shape | **WAS DRIFT — now COMPLIANT_AND_WIRED** (Slice 4). Structure still settles the ordinary path at no cost |
| 5 | Clarification round trip | Brain | Vision §3.1; ADR-0024 Gap 1 | `brain/intent.py::clarify` + `kalpavriksha_desktop.py:787` | **COMPLIANT_AND_WIRED** (ADR-0024 Gap 1 is **STALE**) |
| 6 | Intent → Planner admission | Brain | ADR-0024 D1 (proposed) | `kalpavriksha_desktop.py:751-851` | **COMPLIANT_AND_WIRED** |
| 7 | Planner → MissionPlan | Brain | Vision §3.2 | `planner/planner.py` | **COMPLIANT_AND_WIRED** |
| 8 | Model Router = Brain's single reasoning door | Brain | Vision §3.3; ADR-0024 D7 | `plugins/model_router.py`, consumed by `planner/planner.py:73` | **COMPLIANT_AND_WIRED** |
| 9 | Broker is the single provider selector | Shared Infra | Vision §5.7; ADR-0017 | `broker/broker.py` — only `select/_decide/_reject/_record/replay` | **COMPLIANT_AND_WIRED** |
| 10 | Broker never discovers / executes / retries / approves | Shared Infra | Vision §5.7, §5.8 | `broker/` — no execution, no probing, no retry | **COMPLIANT_AND_WIRED** |
| 11 | ADR-0017 tier ladder preserved | Shared Infra | ADR-0017 (ratified) | `broker/policy.py` locality ordering | **COMPLIANT_AND_WIRED** |
| 12 | Duck.ai excluded from Founder Edition | Founder decision | Brief §3 | `kalpavriksha_desktop.py:483-491` — `browser_free_ai` never registered | **COMPLIANT_AND_WIRED** |
| 13 | Retry owned by its canonical layer | Provider | Brief §9; MB033 Rule 4 | `providers/gemini.py`, committed with 18 tests | **WAS BUILT_BUT_UNWIRED — now COMPLIANT_AND_WIRED** (Slice 2). Retry stays in the provider; the Broker still retries nothing |
| 14 | Mission Control lifecycle | Shared Infra | Vision §5.3; ADR-0021 | `mission_control/` | **COMPLIANT_AND_WIRED** |
| 15 | Runtime → Executive/Worker | Operator | Vision §4.1, §12 | `runtime/`, `executor/`, `desktop/` | **COMPLIANT_AND_WIRED** |
| 16 | Verification structurally independent | Operator-adjacent | Vision §10; ADR-0011 | `verification/`, gateway `.verify()` | **COMPLIANT_AND_WIRED** |
| 17 | Evidence → Memory | Shared Infra | Vision §5.4, §9.2 | `memory/`, `persistence/` | **COMPLIANT_AND_WIRED** |
| 18 | Reporter | Brain | Vision §3.4, §16 | `brain/reporter.py` (566 lines), wired at `kalpavriksha_desktop.py:621,691` | **COMPLIANT_AND_WIRED** (Vision §3.4 "not yet built" is **STALE**) |
| 19 | Permission / approval | Shared Infra | Vision §5.2, §15; ADR-0019, ADR-0020 | `permissions/`, `mission_control/approvals.py` | **COMPLIANT_AND_WIRED** — **live-proven** (Acceptance D), after Rows 26/27 were fixed |
| 20 | Founder checkpoint distinct from permission | Shared Infra | Brief §14; ADR-0020 | `runtime/engine.py` `FOUNDER_CHECKPOINT`, `confirm_completion` bridge | **COMPLIANT_AND_WIRED** — **live-proven** (Acceptance C mechanism): `kind='founder_checkpoint'`, and Stop performs no mutation |
| 21a | Persistence — **recording** | Shared Infra | Vision §11.2; ADR-0015 | `PersistenceService` + `PlanHistory`, wired at `kalpavriksha_desktop.py:614` | **COMPLIANT_AND_WIRED** — live-proven |
| 21b | Persistence — **resume after restart** | Shared Infra | Vision §11.1; ADR-0015 | `persistence/recovery.py::recover()` built; called by `launcher/boot.py:380` **only** | **BUILT_BUT_UNWIRED** — deliberate, see below |
| 22 | Founder interaction audit trail | Shared Infra | ADR-0025 (**PROPOSED**) | `_audit()` in `desktop_shell.py` | **COMPLIANT_AND_WIRED** — note it implements a *Proposed* ADR |
| 23 | Multi-Operator concurrency | — | Vision §8.5 | not built | **DELIBERATELY_FUTURE** |
| 24 | Knowledge promotion review | Brain + gate | Vision §9.3–9.5 | `mission_control/knowledge_queue.py` partial | **DELIBERATELY_FUTURE** for this mission |
| 25 | Stateful Environment Sessions | Operator | Vision §8.3, Freeze §3 item 2 | one-shot Action contract | **DELIBERATELY_FUTURE** |
| 26 | Founder approval reaches the grant ledger | Shared Infra | Vision §5.2, §15.1 | `decide_approval` in `kalpavriksha_desktop.py` | **WAS BROKEN — now COMPLIANT_AND_WIRED** (Slice 5) |
| 27 | Approval resumes the work it authorised | Operator | Vision §15.1 | `_drive_until_settled` + `decide_approval` | **WAS BROKEN — now COMPLIANT_AND_WIRED** (Slice 6) |
| 28 | Founder Surface does not reach the Mission OS | Brain-adjacent | `TestOnlyComposition` guard | `desktop_shell.py` imported `planner.modes` | **WAS DRIFT — now COMPLIANT_AND_WIRED** |
| 29 | Founder Surface holds no environment door | Brain-adjacent | `TestNothingExecutesOrCallsAI` guard | vendored server moved to the composition root; `create_window(server=...)` | **WAS DRIFT — now COMPLIANT_AND_WIRED.** `socket`/`bottle`/`wsgiref` gone from the package; the only `os` left is Row 30's untracked file, proven by parking it |
| 30 | No second provider path | Shared Infra | Vision §5.7; ADR-0024 D7 | **untracked** `founder_edition/ai_client.py` — direct OpenRouter over `urllib` | **IMPLEMENTATION_DRIFT — open, founder's call** |
| 31 | Declared boot order matches actual boot | Brain-adjacent | `boot.py` own contract | `STEP_NAMES` contradicted the sequence | **WAS DRIFT — now COMPLIANT_AND_WIRED** |

---

## Rows that are not COMPLIANT_AND_WIRED — detail

### Row 3 — Utterance-role understanding · SPECIFIED_BUT_MISSING

- **Responsibility:** decide what *role* the Founder's utterance plays relative to
  conversational state — `NEW_OBJECTIVE`, `ANSWER_TO_CLARIFICATION`, `FOLLOW_UP`,
  `CONTINUATION`, `CANCEL_OR_STOP`, `MODIFY_OR_REDIRECT`, `ORDINARY_CONVERSATION`.
- **Canonical owner:** Brain / Intent Layer (Vision §3.1 — "owns follow-up
  clarification"; the decision is about Founder *meaning*, so it is Brain-side).
- **Canonical source:** convergence brief §11 (the CRITICAL INVARIANT) and §12
  (the exact regressions). Vision §3.1.
- **Current source:** **the concept does not exist** — `NEW_OBJECTIVE`,
  `ANSWER_TO_CLARIFICATION`, `FOLLOW_UP`, `CANCEL_OR_STOP`, `MODIFY_OR_REDIRECT`
  and `utterance_role` return **zero matches** across all of `src/`, `tests/` and
  `docs/adr/`. `IntentLayer._with_roles` is unrelated — it stamps
  *actor/beneficiary* agency (ADR-0024 D5), not utterance role.
- **Exact discrepancy:** `kalpavriksha_desktop.py:786` reads
  `if pending is not None:` and unconditionally routes the utterance into
  `intent_layer.clarify()`. The source comment states the assumption in as many
  words — *"A question was asked last turn, so this message is its answer"* — and
  the STATED LIMIT at lines 779–785 concedes that an unrelated request typed while
  a question is open is taken as the answer. That is precisely the invariant the
  brief §11 forbids: **a pending clarification is context, and does not own the
  next utterance.**
- **Smallest canonical convergence action:** introduce an utterance-role decision
  in the Brain's Intent Layer, consulted by the composition root *before* the
  `pending is not None` branch. The composition root keeps deciding nothing — it
  asks the Brain and obeys.
- **Dependencies:** none. This is the earliest blocker in the loop; every §12
  regression and the whole of Live Acceptance A depend on it.
- **Would frozen architecture need modifying?** No. Vision §3.1 already assigns
  clarification ownership to the Intent Layer. This adds a method to an existing
  Brain component.
- **Founder decision required?** No.

### Row 4 — Intent Layer semantic understanding · IMPLEMENTATION_DRIFT

- **Current source:** `brain/intent.py` is 903 lines of ordered substring patterns
  and twelve hand-written parsers. Its own docstring says *"Never calls a model
  directly."* `_CAPABILITY_QUESTION_PATTERNS` is a 14-entry phrase list; the
  `_patterns` table is 17 ordered substrings where first match wins.
- **Exact discrepancy vs. brief §11:** *"Do NOT solve natural language
  understanding by continuously adding more phrases and regexes."* The layer has no
  reasoning door at all, so every new phrasing is a new literal.
- **Note — this is drift, not absence.** The regex layer works for the shapes it
  covers and must not be deleted. ADR-0024 D3's generic-fallback rule is honoured:
  unmatched-but-clear input travels on rather than becoming an interrogation.
- **Smallest canonical convergence action:** give the Intent Layer a reasoning
  door **through the Model Router** (ADR-0024 D7 — normative: *every* Brain
  reasoning call goes through the Model Router, not just the Planner's), used where
  structure genuinely cannot decide. Deterministic parsing stays in front of it.
- **Dependencies:** Row 3 (the role decision is the first thing worth reasoning
  about, and it is where a wrong answer currently hurts the Founder most).
- **Would frozen architecture need modifying?** No — Vision §3.3 and ADR-0024 D7
  already require exactly this door.
- **Founder decision required?** No.

### Row 21b — Resume after restart · BUILT_BUT_UNWIRED (corrected 2026-08-21 16:10)

**This row was wrong in the first version of this matrix**, which recorded a single
"Persistence / recovery — COMPLIANT_AND_WIRED" row. Two different things travel
under that word and Founder Edition wires exactly one. Corrected here rather than
quietly amended, because getting it wrong is the same class of error this matrix
exists to catch.

The composition root states the boundary itself, at the line that would have
called it:

> `# Deliberately NOT restored into the runtime. This mission is about being able`
> `# to reconstruct what happened, not about resuming interrupted missions after a`
> `# restart; recovery semantics are their own decision and restore_into() is left`
> `# uncalled.`

Verified by AST rather than by grep — the root *mentions* `restore_into()` in the
comment explaining why it does not call it, so a text search finds the explanation
and concludes the opposite. No `Call` node for `restore_into` or `recover` exists
in `kalpavriksha_desktop.py`.

`recover()` is fully built (`persistence/recovery.py`, with `RecoveryReport`,
quarantine of interrupted tasks, snapshot-vs-replay) and **is** wired by
`launcher/boot.py:380` — but `master_agent.launcher` is deliberately excluded from
the Founder Edition build (`packaging/kalpavriksha.spec`).

**Convergence action: none, and deliberately so.** This is a scope decision the
source records explicitly, not drift. Wiring `recover()` into Founder Edition
would be building something the founder has not asked for, against §20. It is
listed under DELIBERATELY_FUTURE below.

### Row 13 — Provider retry · BUILT_BUT_UNWIRED

Inherited uncommitted work (handoff T2). Coherent and correctly placed in the
provider — which is retry's canonical owner, and specifically **not** the Broker
(Vision §5.7 — the Broker "retries nothing"). Non-regressive (30 provider tests
pass). **Has no test for the behaviour it adds.** Convergence action: write the
retry-policy test using the `sleep` seam its author already provided, then commit.

---

## Stale documents identified during this read

Recorded so a future session does not rebuild working components:

1. **ADR-0024 Gap 1** — "`IntentLayer.clarify()` has zero production callers."
   **Stale.** `kalpavriksha_desktop.py:787` calls it, passing `question`, `key`,
   `options`, `required` and `supplied`. The round trip closes.
2. **Vision §3.4 / §16** — "Reporter … not yet built."
   **Stale.** `brain/reporter.py` is 566 lines and wired into the Founder path.
3. **Vision §3.1** — "the real Intent Layer is a stub pending the real Planner."
   **Stale.** The Planner is real and the Intent Layer is substantial (if regex-bound).
4. **Test-layer staleness** — four inherited test files lag committed source; e.g.
   `test_no_automation_capability_exists` forbids a `click` capability that source
   now deliberately ships (`desktop_click`, `desktop_type_text`, `desktop_press_key`),
   and `test_bringing_to_front_reports_that_it_is_not_built` expects a stub where
   source now really implements it. **The Desktop Executive is further along than
   both its tests and the audit documents claim.**

---

## Dependency order for convergence

1. **Row 3 — utterance roles.** Earliest blocker; gates every §12 regression and
   Live Acceptance A. **First implementation slice.**
2. **Row 4 — Intent reasoning door**, reusing the Model Router seam Row 3 establishes.
3. **Row 13 — provider retry test**, then commit the inherited provider work.
4. Inherited test-file corrections (handoff T1), then commit.
5. Live Acceptance B–F against the converged loop.

---

## Founder decisions required

Two, both recorded rather than guessed. Neither blocks the canonical loop.

1. **FD1 — what status follows a founder's Stop?** Observed live: a declined
   checkpoint correctly performs no mutation and leaves `status.status ==
   awaiting_approval`, so the surface reads as waiting on someone who has already
   answered. There is no truthful state to move it to — `FAILED` is untrue,
   `COMPLETED` is untrue, `SUPERSEDED` implies a replacement. **This is precisely
   ADR-0021 Open Item O1**, which already records that the ratified vocabulary has
   no `CANCELLED` and that the choice is the founder's. Inventing a seventh state
   here would pre-empt it.
2. **FD2 — delete the untracked `founder_edition/ai_client.py`?** Row 30. It is a
   direct, unbrokered, paid provider path with zero callers. Recommended for
   deletion; untracked means git holds no copy, so it is not removed unilaterally.

**No canonical *conflict* was found.** Both are open questions the architecture
already anticipated, not contradictions between canonical sources. Everything else
in this matrix is implementable inside frozen architecture without amending the
Constitution.

---

## What this session changed

Recorded so a later reader can tell findings from repairs.

**Real founder-facing defects found and fixed** (none were caught by the existing
suite, all three found by attempting live acceptance):

1. **The founder could not approve anything.** `decide_approval` read `permissions`
   and `GrantScope` as globals that do not exist — `NameError` on the first
   Approve. Rows 26.
2. **Approval never resumed the work.** Nothing drove the Runtime after the founder
   decided, so an authorised task waited forever. Row 27.
3. **A pending clarification owned the founder's next utterance.** "nothing thanks"
   became a filename. Row 3.

**Drift closed:** Rows 28 (surface reaching into the Planner) and 31 (declared boot
order contradicting the sequence).

**Drift found and left open, with the fix written down:** Rows 29 and 30.

**Stale claims corrected in this matrix itself:** Row 21 (recording ≠ recovery) —
see Row 21b. Getting that wrong is the same class of error this matrix exists to
catch and does not get a pass for being ours.
