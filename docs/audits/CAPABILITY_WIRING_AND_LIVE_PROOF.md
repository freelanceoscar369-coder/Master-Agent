# Existing Capability Wiring & Live-Proof Sweep

Built 2026-08-21, on top of the completed convergence mission
(`docs/CONVERGENCE_HANDOFF.md`, baseline `1743a53` → `ad3b492`).

**Method.** Every row below was discovered by asking the **running production
composition** — `kalpavriksha_desktop._build_mission_pipeline()` — not by reading
documents and not by taking counts from a brief. Where a claim could be *executed*
rather than inspected, it was executed.

---

## A · Git truth

| Field | Value |
|---|---|
| Branch | `main` |
| HEAD at sweep start | `ad3b492068a2a8ad10e064f4a4936fa6d1573a5a` |
| Remote | equal — 0 ahead, 0 behind |
| Tracked tree | clean (staged: none, unstaged: none) |
| Untracked | 113 paths, all pre-existing, none deleted |
| Preceding convergence baseline | `1743a53b585036cc872a409c2820bedf8cc4f316` (45 commits) |

---

## B · Registered Executive / capability surface — from the live registry

**5 Executives, 46 capabilities, all 46 Planner-visible.**

| Executive | Capabilities | Read-only | Reversible | Irreversible |
|---|---|---|---|---|
| `browser` | 10 | 3 | 7 | 0 |
| `desktop` | 19 | 8 | 9 | 2 |
| `filesystem` | 14 | 5 | 7 | 2 |
| `document` | 2 | 1 | 1 | 0 |
| `reasoning` | 1 | 1 | 0 | 0 |

---

## C · Production wiring matrix

The governing question was not "does it exist" but **"can the Runtime reach it"**.

| Executive | Gateway registered | Runtime-reachable | Verdict |
|---|---|---|---|
| `browser` | `BrowserGateway` | YES | **FULLY_WIRED_AND_LIVE_PROVEN** |
| `filesystem` | `FilesystemGateway` | YES | **FULLY_WIRED_AND_LIVE_PROVEN** |
| `desktop` | `DesktopGateway` | YES | **FULLY_WIRED_AND_LIVE_PROVEN** |
| `document` | **was NONE → now `PluginGateway`** | **was NO → now YES** | **WIRING DEFECT — FIXED; live execution proven, no Evidence** |
| `reasoning` | **was NONE → now `PluginGateway`** | **was NO → now YES** | **WIRING DEFECT — FIXED; live execution proven, no Evidence** |

### The defect, stated exactly

`Document.ExtractText`, `Document.WriteDocument` and `Reasoning.Transform` were
**registered, Planner-visible, and permission-granted — with no gateway.** The
Runtime does not fall back when one is missing (`runtime/engine.py:373`); it fails
the task:

```
no gateway registered for executive 'document' (task step_1)
no gateway registered for executive 'reasoning' (task step_1)
```

**Proven by execution, not inference** — each capability was planned and run, and
the task observed to fail. Fixed by registering the same generic `PluginGateway`
that Browser and Filesystem used before they earned verifying gateways of their
own, and that Desktop's non-verifiable capabilities still take.

Guarded generally by `tests/test_every_executive_is_reachable.py`, which asks the
running system for both sets and compares them — because registering a capability
and registering a gateway are separate lines that nothing ties together. **It fails
on the pre-fix commit by name.**

---

## D · Verification / observation coverage

Re-established **dynamically** from `desktop/gateway.py::supports()`, per the
brief's instruction not to overclaim.

| | Capabilities |
|---|---|
| **CAN VERIFY** (generic read-only postcondition) | `Desktop.LaunchApplication`, `Desktop.CloseApplication`, `Desktop.FocusWindow`, `Desktop.BringToFront` — **four**; plus Filesystem's disk re-observation and Browser's DOM/URL observation |
| **CANNOT GENERICALLY VERIFY — and this is not a defect** | `Desktop.DesktopClick`, `DesktopTypeText`, `DesktopPressKey`, `CloseWindow`, `ExecuteCommand`, `OpenFile`, `OpenFolder`, and the read-only query capabilities |
| **NO EVIDENCE PRODUCED** | `Document.*`, `Reasoning.Transform` — they run through the generic `PluginGateway`, whose `verify()` returns `None`. **Live execution is proven; canonical Verification Evidence is not produced.** Stated as a fact about the current wiring, not as a judgement that verification is unnecessary — whether either deserves a verifier is a separate adjudication and is explicitly not decided here |
| **NOT WIRED** | none remaining |

**A comment was overclaiming and is corrected.** `kalpavriksha_desktop.py` said the
Desktop gateway adds Evidence for *five* capabilities "(launch/close application,
focus, bring-to-front, **close window**)". `supports()` disagrees and is the
authority: `CloseWindow` is **not** generically verifiable, because a closed window
leaves a running process that may still own others — a verdict from process presence
would be right by accident for single-window applications and silently wrong
otherwise. The comment overclaimed by one; the code never did.

`Desktop.DesktopClick` is the brief's own example and the reasoning holds: a click
has no universal postcondition. Whether it worked is a question about the Step's
intended observable outcome, not about the mouse. Saying so is the truthful answer.

---

## E · Live Founder proof matrix

| Executive | Capability exercised | Real external effect | Evidence | Verdict |
|---|---|---|---|---|
| `browser` | OpenSession → Navigate → ObserveBrowser → Close | real visible Chrome reached `https://example.com/` | 6 steps `verdict=matched`; observed title + **trailing-slash** final URL the objective never contained | **LIVE_PROVEN** (golden mission) |
| `filesystem` | CreateFolder, WriteFile, DeleteFile | real folder + file on Desktop; real deletion | disk re-observed after the mission claimed done | **LIVE_PROVEN** |
| `desktop` | ListRunningProcesses, IsInstalled, IsRunning, ListInstalledSoftware | **298 real processes**; Chrome detected installed, not running; real software inventory | task `COMPLETED`, real machine data returned | **LIVE_PROVEN** (this sweep) |
| `document` | `Document.WriteDocument` | **valid 35 KB `.docx` written to disk** (verified as a real zip container) | task `COMPLETED` — **no canonical Evidence**, `PluginGateway.verify()` returns `None` | **LIVE EXECUTION PROVEN** (this sweep, after the fix) |
| `reasoning` | `Reasoning.Transform` | real model answered through Model Router → Broker → provider | `{'text': 'acknowledged'}`, task `COMPLETED` — **no canonical Evidence** | **LIVE EXECUTION PROVEN** (this sweep, after the fix) |

Not re-run: Browser and Filesystem were already proven by the preceding mission and
were **cited rather than repeated**, per the instruction not to spend live calls on
success that is already recorded.

---

## F · Wiring defects found and fixed

**One, and it was the whole point of the sweep:** Document and Reasoning registered
without gateways (§C). Seam only — no redesign, no new Executive, no new gateway
class.

**Uncomfortable and worth stating:** one hour before this was found, the preceding
mission added `document` and `reasoning` to the founder-facing capability answer. So
Kalpavriksha had begun *telling the founder* it could work with documents and reason
about text, while both would have failed. **The answer was right and the wiring was
not** — which is exactly the direction this brief predicted the truth would lie.

---

## G · Existing capabilities previously mistaken for gaps

Recorded so no future session rebuilds them.

| Previously believed | Actual truth |
|---|---|
| Desktop verification absent | `DesktopGateway` produces canonical Evidence for four capabilities; the substrate (executor, perception, window/process/UIA) is built and wired |
| Reasoning unreachable / provider defect | Reachable and working. Its earlier refusal was the **privacy boundary**: `Reasoning.Transform` defaults `sensitive=True` deliberately, and with no PRIVATE provider on this machine, sensitive work correctly requires approval instead of being posted to a cloud |
| Ollama "unwired" | **DELIBERATELY_UNAVAILABLE** — 16 GB RAM constraint. Not constructed, registered, probed, ranked, or prompted |
| `Reporter` not built | 566 lines, wired |
| `IntentLayer.clarify()` has no caller | Called by the composition root |
| Persistence recovery missing | `recover()` fully built; deliberately not wired into Founder Edition |

---

## H · Founder decisions still required

1. **FD1** — what status follows a founder's **Stop**? (ADR-0021 Open Item O1; no
   `CANCELLED` exists and none of the three terminal states is truthful.)
2. **FD2** — delete the untracked `founder_edition/ai_client.py`? Unbrokered, paid,
   zero callers. Recommended: delete.
3. **FD3** — the ladder tier named `TIER_GEMINI` should be `free cloud` per
   ADR-0017's rungs. Mechanical rename; touches the reasoning ladder.
4. **FD4** — frozen components under `executor/` modified without a ratified ADR,
   reported independently by two guards.

---

## I · External blockers

### Live Acceptance C — attempted once at `da9f8f9`, NOT EXECUTED

Per the closing brief: attempt once, record the exact response, do not implement
around an external quota. Both runs refused at the Planner, so **the checkpoint was
never reached**.

```
HTTP 429: You exceeded your current quota ...
* Quota exceeded for metric:
  generativelanguage.googleapis.com/generate_content_free_tier_requests,
  limit: 20, model: gemini-3.6-flash
Please retry in 33.322775703s.   (CONTINUE run)
Please retry in 30.669689260s.   (STOP run)
```

**The script printed two PASS lines that must not be read as evidence.**
*"nothing was written while waiting"* and *"Stop did not execute the mutation"* are
**vacuous here** — no plan existed, so no mutation was ever held and none could have
escaped. They are true statements about an acceptance that did not run, not
observations of checkpoint behaviour.

**Correct verdict: `EXTERNAL BLOCKER — LIVE ACCEPTANCE C NOT EXECUTED`.** Not FAIL:
nothing about the checkpoint was disproven. Its mechanism remains proven without
quota by `c2_checkpoint_mechanism.py` (Continue writes the previewed payload; Stop
performs no mutation).

The script cleaned up its own disposable folders; both were removed by it.


**Gemini free tier — 20 requests/day.** Refined this sweep: **small requests still
succeed while planning-sized ones do not.** `Reasoning.Transform` completed; the
Planner's own call returned 429 twice, ~75 s apart. This confirms the composition
root's own recorded reasoning — *"a small probe succeeds where a planning-sized
request gets 429, and a planning-sized probe consumes the very quota it is trying to
predict."*

Consequence: **Live Acceptance C end-to-end (the Planner marking a checkpoint from
the founder's own sentence) remains the one unproven item.** Its mechanism is proven
without quota by `c2_checkpoint_mechanism.py`.

---

## J · Genuinely missing capabilities

**None proven.** Every apparent gap examined in this sweep resolved to one of:
already built, already wired, wired-but-unreachable (fixed), deliberately excluded,
or blocked by an external quota.

`GENUINELY_MISSING` remains empty, which is the correct outcome of a sweep whose
whole purpose was to stop treating unproven things as absent.

---

## K · Exactly one next mission

**NO NEW IMPLEMENTATION BRIEF — EXISTING CAPABILITY PROOF NOT COMPLETE.**

One item of proof is outstanding and it is blocked externally, not architecturally:
Live Acceptance C end-to-end, which needs Planner-sized Gemini quota. Until that is
run, the honest position is that Kalpavriksha's existing capability surface is
proven everywhere it can currently be proven — and nothing has been shown to be
missing.

The next session's first action is to re-run
`scripts/live_acceptance/c_founder_checkpoint.py` once quota allows. If it passes,
every Executive family and every §30 acceptance is live-proven, and only then does
choosing something new to build become an evidence-backed question.
