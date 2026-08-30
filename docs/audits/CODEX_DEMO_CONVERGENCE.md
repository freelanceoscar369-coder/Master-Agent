# CODEX demo convergence ledger

**Mission opened:** 30 August 2026  
**Mode:** engineering convergence with evidence; not an architectural redesign  
**Working branch:** `codex/demo-convergence`  
**Starting source:** `6349eb169239c489b54e9832767c41046aafed53`
(`origin/main` when the branch was cut)  
**Repository:** `D:\MasterAgent`

This ledger is append-only for the duration of the convergence mission. Claims
below distinguish source, package, product surface, environment, and evaluator
evidence. Pre-existing untracked files are Founder-owned and are not part of
this work.

## Gate 0 — independently established starting truth

- The checkout initially named `main` at
  `60dbaa0147b81bc8fae10e684d0fd7e2b4fe84dc`; live `origin/main` was
  `6349eb169239c489b54e9832767c41046aafed53`, 59 commits ahead.
- The convergence branch was cut directly from live `origin/main`; no merge of
  the stale local branch was used.
- The only local packaged executable found at the start was
  `D:\MasterAgent\dist\Kalpavriksha\Kalpavriksha.exe`, timestamp
  26 August 2026 13:50, size 36,901,260 bytes, SHA-256
  `49B8480F4714D4749C2CBD821F946AC51FB2B776BDF1B7A5AE608CD2A8A7A336`.
- That executable self-checked `OK`, identified itself as packaged, advertised
  46 capabilities, reported Browser/Desktop/Document/Filesystem/Reasoning
  executives reachable, and showed no Ollama construction or candidacy.
- Current repository evidence describes a later 48-capability package built
  from `9234319` with a different hash. That artefact is not present locally.
  Therefore the executable above does **not** establish current-source product
  readiness and must not be treated as the release candidate.
- Ollama processes exist in the host environment. Founder Edition's self-check
  reported Ollama neither constructed nor eligible. This mission will not
  enable or select Ollama.

## First adversarial failure — observed product behaviour

Package under test: the stale 46-capability executable identified above. State
was isolated under a test-specific directory and microphone input disabled.

Founder said:

> make a folder called KVST_A1_0830 on my desktop

The product asked:

> What should the folder be called?

The Founder replied:

> Call it KVST_A1_0830 and put it on the Desktop.

Fresh state records establish:

1. `founder_interactions.jsonl` retained the opening, question, and reply.
2. `events.jsonl` recorded `mission_understanding_started` and
   `mission_planning_started` with the clarification reply alone as the
   objective, rather than the original Founder objective plus accumulated
   evidence.
3. The Broker ledger ranked `chatgpt-desktop` first while the same package's
   self-check had reported the desktop reasoning tier unavailable. This is a
   separate routing-truth question; it is not yet established as the cause of
   the semantic failure.
4. No terminal completion was observed before the interactive run was stopped.
   There is therefore no proved false-completion result from this reproduction.

**First incorrect boundary in that package:** Intent parsing failed to extract
two explicitly supplied CreateFolder fields. The next boundary also failed:
the clarification round trip promoted the answer into a replacement objective
instead of preserving the original objective and accumulated evidence.

**Current-source status:** unadjudicated at ledger creation. The present source
contains later Intent/clarification/correspondence changes. The exact sentence
must be traced through the current semantic spine before any repair is made.

## Frozen independent holdout

The 28 objectives in
`scripts/live_acceptance/codex_holdout/cases.json` were frozen before the
current-source run and before any production repair. They are not the three
rehearsed golden paths. They cover:

- equivalent wording, punctuation, capitalization, and courtesy;
- multi-turn and multi-field clarification, nested destination, and ambiguity;
- wrong-parser pressure and compound objectives;
- local multi-step execution and reasoning-to-action Evidence binding;
- browser state, redirect, missing selector, cross-step runtime Evidence, and
  unreachable-page failure;
- pre-existing artefact, wrong-path, and partial-content false-completion traps;
- grounded system questions, follow-up semantics, Broker/provider truth,
  sensitivity, recovery, and same-session continuity.

No production phrase table may be derived from this holdout. Token substitution
is limited to disposable names and controlled fixture values documented beside
the cases.

## Active defects and gates

| ID | Severity | Boundary | Current evidence | Gate |
|---|---|---|---|---|
| CDX-001 | P0 candidate | Intent / clarification round trip in stale package | Explicit fields re-asked; reply became planning objective | Reproduce or falsify on current source |
| CDX-002 | P0 candidate | Release/package identity | Only local package predates current source and advertises 46 rather than 48 capabilities | Build and identify a fresh package after source gates pass |
| CDX-003 | P1 investigation | Broker availability truth | Stale package ranked a desktop provider that self-check called unavailable | Trace current eligibility and runtime availability evidence |
| CDX-004 | Known P1 | Browser lifecycle after failure | Existing repository evidence records a failed-mission session leak | Adversarially reproduce; repair only at lifecycle owner if current |
| CDX-005 | Known P1/P0 candidate | Verification absence handling | Existing repository evidence records an absent-Evidence fall-open path | Test false-completion family before release decision |

## Next evidence action

Drive the exact failed sentence and semantic variants through the current
production `IntentLayer`, record parsed fields, clarification state, semantic
requirements and planner admission, then run focused current tests. Only a
failure in current source authorizes a production repair.
