# UI Integration Audit
**14 August 2026 · Kalpavriksha Founder Edition UI**

Required by the mission's acceptance criteria: *"A concise audit/report records
exactly what changed and what was visually verified."*

---

## 1 · Verdict

**No code was changed in this mission, and none should have been.**

Every UI fix agreed in the prior review is **already implemented and verified**.
What is *not* done is **porting them into the shipped application** — and the
shipped application is not in this workspace.

This is a **handoff gap, not an implementation gap.**

---

## 2 · Preconditions verified before touching anything

| Mission instruction | Precondition | Present |
|---|---|---|
| "Read the existing Kalpavriksha UI implementation" | shipped app source | ❌ no `webview`, `WebView`, `ipcRenderer` or `treeRenderer` anywhere |
| "Inspect the current UI… including running it" | runnable app | ❌ absent |
| "Review the previous UI discussion/history **in the repository**" | a git repository | ❌ `fatal: not a git repository` |
| "Preserve `milestone-reasoning-layer`" | that tag/branch | ❌ not found |
| "Preserve `milestone-desktop-intelligence-observe`" | that tag/branch | ❌ not found |
| "Do not modify the reasoning-layer or Desktop Intelligence architecture" | that source | ❌ absent — trivially preserved, nothing to modify |
| "commit and tag following Engineering Rule 001" | the rule, and a repo | ❌ rule not documented anywhere; no repo |

**Nothing was uploaded this turn.**

Consequence: **I cannot commit, cannot tag, and did not fabricate either.** The
two named milestones are preserved by the only honest means available — nothing
in this workspace touches them, because they are not in it.

---

## 3 · The agreed UI fixes — status

Taken from `HYPER_UI_UX_REVIEW.md` (verdict **C**, Top 5 changes) and the
approved Phase 1/2/3 scope. Not re-derived, not reinterpreted.

| # | Agreed fix | Implemented in | Status |
|---|---|---|---|
| 1 | Tree prominence inversely proportional to work in flight | `surface/src/presentation/prominence.ts` | ✅ |
| 1b | Portable prominence contract (data attribute + 5 CSS vars) | `surface/src/styles/prominence.css` | ✅ |
| 2 | Remove the four disabled founder-action buttons | `ConversationSurface.tsx` — 0 renders | ✅ |
| 2 | Remove the mission-strip band | `ConversationSurface.tsx` — 0 renders | ✅ |
| 2 | Collapse two "Awaiting runtime" panels into one system line | `founder-edition/src/components/SystemLine.tsx` | ✅ |
| 2 | Debord the rail | `founderEdition.css` | ✅ |
| 3 | Work Region — one sentence answering "what is it doing?" | `surface/src/components/WorkRegion.tsx` | ✅ |
| 3 | State translation, `message` over `status` | `surface/src/presentation/workState.ts` | ✅ |
| 3 | Timing honesty (10s gate · discrete steps · no countdown) | `surface/src/presentation/timing.ts` | ✅ |
| 3 | Founder completion — five elements, evidence collapsed, undo | `surface/src/components/CompletionRequest.tsx` | ✅ |
| — | Vocabulary fail-safe (mismatch never hides the work) | `workState.ts` | ✅ |

**Zero agreed fixes remain unimplemented.** Nothing was added in this mission,
because adding anything would have been the scope broadening the mission
forbids.

---

## 4 · Regression run — this mission, on the real packages

```
surface          250 pass / 0 fail     BOUNDED
presence         183 pass / 0 fail     CONTAINED
founder-edition   52 pass / 0 fail     COMPOSED
                 ───────────────────
                 485 pass / 0 fail
```

Phase 2 removals confirmed still in effect: `FounderActions` 0 renders ·
`MissionStrip` 0 renders · environment/runtime panels 0 renders.

**No regressions. No existing test modified. No existing functionality altered.**

---

## 5 · Visual verification — what was actually seen in a browser

Both harnesses were published and loaded in a real Chromium session; values
below were **computed live in the page**, not asserted from source.

| Verified | Evidence |
|---|---|
| Bordered regions, before → after | **9 → 3** |
| Tree share of frame, before → after | **100% → 30%** |
| Six states derive correct prominence | idle `ambient` · active `reduced` · retry `reduced` · awaiting `minimum` · completed `reduced` · failed `minimum` |
| Asymmetric transition (yields fast, returns slow) | 600ms receding / 1400ms returning, observable in the interactive frame |
| Timing honesty — 12 checks | all **PASS**: 9,999ms silent / 10,000ms shows · 2 steps no bar / 3 steps bar · attempt 1 silent / attempt 2 shows · no `%`, no `remaining`, no `ETA`, no countdown |
| Idle renders nothing from the Work Region | `visible:false` — no wrapper, no reserved height |
| Founder completion flow | evidence collapsed by default; Mark complete → 60s undo → restore |

Screenshots retained in the thread: harness top · before/after · six states ·
Work Region state stack · completion flow.

**Not visually verified:** the shipped application, because it is not here. The
four `.tsx` components have never mounted — React is not installable in this
environment. Their *logic* is fully tested and the *visual contract* is
exercised in a browser; the React wiring between them is verified by inspection
only. This is unchanged from Phase 3 and is stated again rather than quietly
dropped.

---

## 6 · What actually blocks completion

Two items. Both are missing artifacts, not open decisions.

**BLOCKER-A · The shipped application is not in this workspace.**
Without it I cannot read it, run it, port into it, or visually validate it.
Every fix above is expressed to be portable — prominence is one data attribute
plus five CSS variables; the four rule modules are pure TypeScript with no React
dependency — but somebody has to apply them to the real tree renderer.

**BLOCKER-B · There is no repository.**
No git, no history to review, no tags to preserve, and Engineering Rule 001 is
not documented anywhere in this workspace. Committing and tagging is therefore
impossible, and inventing a rule I have not read would be worse than not tagging.

---

## 7 · Port manifest — the smallest clean change set

For whoever holds the shipped app. Ordered; each step is independent and
individually shippable.

| Step | Copy / apply | Into | Effort |
|---|---|---|---|
| 1 | `prominence.ts` + `prominence.css` | anywhere importable by the shell | copy, no edits |
| 2 | Set `data-prominence` + the 5 CSS vars on the tree's container from `deriveProminence(execution)` | the app root or tree wrapper | ~10 lines |
| 3 | Delete the four disabled action buttons from the home composition | shipped home screen | deletion only |
| 4 | Delete the mission-strip band; fold its content into a single bottom system line | shipped home screen | deletion + 1 row |
| 5 | Collapse the two "Awaiting runtime" panels to two segments in that system line | shipped rail | deletion + 2 segments |
| 6 | `workState.ts` + `timing.ts` | anywhere importable | copy, no edits |
| 7 | Render one work line from `presentWork()`; render nothing when `visible:false` | shipped home screen | new, ~40 lines |
| 8 | Render `CompletionRequest` on `AWAITING_FOUNDER_COMPLETION` | shipped home screen | new, ~80 lines |

**Steps 1–5 require no new UI and no backend contract.** They are the ones that
answer the founder's two original complaints, and they can land first.

**One thing to confirm before step 6:** the authoritative `ExecutionStatus.status`
enum spellings. Two vocabularies currently coexist — `ExecutionPhase` (C19A/C20,
hyphenated, 9 values) and `ExecutionStatusName` (Phase 3, underscored, 12
values), sharing only `idle` and `failed`. A fail-safe is in place so a mismatch
degrades to *showing the message* rather than *showing nothing*, but the real
enum should replace the guess. One-line change in `prominence.ts`.

---

## 8 · Scope discipline

Not started, per the mission's explicit exclusions: Hermes · Groq · Gemini ·
Perplexity · video generation · any new capability. No backend, runtime, kernel,
reasoning-layer or Desktop Intelligence file was read or written — none exist
here to read or write.

**Files changed by this mission: one — this audit.**
