# Mission Brief 033 — Ollama Provider Plugin & Intelligent Token Economy

Status: **Shipped** — 2026-07-30

**No new ADR.** Nothing architectural was decided here: ADR-0017 already
split deciding from executing, and this builds the executing half.

## Objective

MB032 made the Broker the single authority on *which* AI. Nobody answered.
This brief is the first real execution path, and the beginning of the
discipline that keeps every future one cheap.

```
Task -> Broker -> Ollama Provider Plugin -> Ollama -> Structured Response
                                                   -> Decision Ledger
```

Proved live on the founder's machine, not just in tests:

```
  Thinking with  ollama.local (gemma4:latest)
  Cost           Free
  Latency        22.8 s
  Prompt Cache   MISS

Blue
```

## 1. What changed, and what did not

**Zero frozen files were modified.** `runtime/`, `mission_control/`,
`persistence/`, `executor/`, `verification/`, `plugins/` and `broker/` are
untouched, and the `git diff` guard proves it. MB032 needed one ratified
exception; this brief needed none.

New code is one new package (`providers/`) plus additive modules in
`ai_infrastructure/`. `config.py`, `launcher/` and `dashboard/` gained
fields and a panel section.

**One reading worth stating.** The brief's constraints list says *do not
modify the Dashboard*, and its Dashboard section says *add Current AI
Provider, Last Provider, Latency, Estimated Cost, Prompt Cache Hit/Miss*.
I read the first as "do not redesign" — which is also what that section
says in its own words — and made the additions inside the existing MB032
panel, changing no layer boundary and no existing row. If that reading is
wrong, the Dashboard changes are the separable part of this commit.

### The provider does not become an Executive

`OllamaProvider` is registered in a **second `PluginRegistry`**, held by
the launcher for model providers only. That is not tidiness: ADR-0017
Decision 8 rules that an *AI Capability* (`reasoning`) is not a
Constitution *Capability* (`Filesystem.CreateFolder`), so a provider is
not a dispatchable Executive. Putting one in the Executive registry would
have added it to Mission Control's registry, the Runtime's gateway map and
the Dashboard's Executive list — three of the subsystems this brief must
not touch. Same class, different instance, and four tests hold the line.

## 2. Why the provider lives outside `ai_infrastructure/`

MB032's purity tests assert that the AI Infrastructure layer imports no
`subprocess`, `socket`, `http`, `httpx`, `requests` or `urllib`. An Ollama
provider needs HTTP. Rather than weaken the test, the network went into a
package of its own:

```
    Broker decides    ai_infrastructure invokes    providers/ execute
    (never executes)  (never decides)              (never decide)
```

`ai_infrastructure/execution.py` imports exactly one module from
`providers/` — `response.py`, which is pure dataclasses — so it can record
an execution without acquiring the ability to perform one.
`providers/__init__.py` therefore re-exports **nothing**, and a test
asserts it has no imports at all: a convenience `__init__` would quietly
delete that property.

Inside `providers/`, `transport.py` is the only module that touches the
network — the same one-door discipline `desktop/probe.py` has for
subprocess and `store.py` has for the filesystem. A parameterised test
checks every other module for a network import.

`urllib`, not `httpx`, deliberately: the first production AI execution
path adds **no new dependency**, and one POST plus one GET does not earn
one. `httpx` is already a project dependency and drops in behind the same
`Transport` protocol when streaming is worth having.

## 3. Rule by rule

**Rule 1 — never use an expensive provider if a cheaper one clears the
floor.** Already the Broker's, unchanged. What this brief adds is the
proof that execution follows the decision: a test registers the expensive
provider *and* the cheap one, runs a prompt, and asserts the expensive
one's transport was never touched.

**Rule 2 — never re-solve a solved problem.** `PromptCache` is defined as
the brief specifies — `lookup`, `store`, `invalidate` — and ships wired to
`NullPromptCache`, which always misses. Two rules are written down before
anything caches:

1. *It never invents an answer.* Exact match on a digest over capability,
   provider, model and prompt. Semantic similarity is out of scope: "close
   enough" is a judgement and judgements belong to the Broker.
2. *It only stores verified work.* Rule 2 says *reuse previous verified
   results*, and **nothing verifies generated text yet** — ADR-0011
   defines the Verification Subsystem; nothing in it judges prose. So the
   executor stores nothing unless a caller states the result was checked,
   the cache stays empty in this build on purpose, and the hit counter
   honestly reads zero.

*A judgement call, flagged rather than buried:* the brief says "interface
only". I also shipped `ExactPromptCache`, unwired, as the reference
implementation — because an interface with no implementation is usually
wrong, and because the executor's hit path needs something real to be
tested against. It is exact-match only and it is not semantic caching. One
config flag turns it on.

**Rule 3 — record every execution.** `ExecutionRecord` carries latency,
prompt and completion tokens, cost, outcome, the *declared* quality and
its basis, retry count, cache state, locality, model, error and timestamp.
It annotates the decision that chose the provider rather than appending a
second entry: a decision and its execution are two moments in the life of
one task, and two entries would read as the Broker deciding twice. The
`DecisionRecord` underneath is never rewritten, so a decision stays
replayable however its execution went.

**Rule 4 — the provider never decides.** Asserted by AST rather than
trusted: no function in `providers/` may be named `select`, `rank`,
`score`, `choose`, `prefer` or `fallback`; none may be `install`,
`download`, `benchmark` or `upgrade`; and nothing in the package may
import the Broker, the wiring layer, Mission Control or the Runtime.

Retries are transport-only, and one is deliberately absent: **a timeout is
never retried.** A timeout means the model is slower than the time
allowed, and asking again turns a 120-second wait into a 240-second one
for the same answer. A refused *connection* is retried once, because a
refused socket is sometimes a daemon still starting.

**Rule 5 — never silently fall back.** Every failure is a returned
`ProviderResult`, never an exception and never a substitution. Five named
outcomes, each one a different thing for the founder to do:

| Outcome | What it means | Proved live |
|---|---|---|
| `unavailable` | nothing is listening | `[WinError 10061] ... (is Ollama running at http://127.0.0.1:59999?)` |
| `rejected` | it is there and said no | `HTTP 404: model 'definitely-not-installed' not found`, with `installed: ['gemma4:latest']` |
| `timed_out` | listening, too slow | tested |
| `malformed_response` | not the shape it promised | tested |
| `succeeded` | an answer | `Blue` |

The cost of that rule, stated because it is real: when the chosen provider
is down, this returns a failure rather than asking the Broker for a second
opinion — even though that would make the system *look* more robust. It
would also make the stored `DecisionRecord` a lie about what ran, and
every future benchmark, cost total and policy proposal reads those
records. Re-asking after a failure belongs to a caller holding the ranked
runners-up the Broker already returned, making a **new** decision with its
own record.

## 4. The Token Economy, and the number it refuses to invent

> Do NOT estimate imaginary savings. Only count executions that actually
> occurred.

There is no counterfactual anywhere in `economy.py`. In particular,
`money_saved` is **not** "what the frontier model would have cost". That
number is unfalsifiable, always flattering, and would grow fastest on the
days Kalpavriksha did the least. It is the recorded cost of executions
that genuinely happened once and were then reused from cache instead of
repeated — and `avoided_cloud_executions` counts those reuses.

Which means every economy figure is **zero in this build**, and that is
the correct answer. The panel says why rather than leaving a founder to
infer it from a row of zeroes:

```
  TOKEN ECONOMY
      Ran locally    1
      Ran in cloud   0  (free)
      Cache          0 hit / 1 miss
      Avoided        0 cloud call(s), saving nothing yet
      Basis     nothing is cached: the Prompt Cache ships
                empty because no verifier exists for generated
                text, so no execution has been avoided yet
```

Three states are distinguished, because a row of zeroes is otherwise
ambiguous: *nothing has run*, *nothing was reused*, and *this is real*.
Totals are recomputed from the ledger on every read rather than kept as a
counter — a counter and a ledger eventually disagree, and the counter is
the one on the screen.

## 5. Verification

**350 new tests, 2295 passing, 1 skipped, zero regressions** (1945
before). **100% statement coverage** of both new packages and everything
they touch:

```
src/master_agent/ai_infrastructure/*            907 stmts  100%
src/master_agent/providers/ollama.py            114 stmts  100%
src/master_agent/providers/response.py           58 stmts  100%
src/master_agent/providers/transport.py          50 stmts  100%
src/master_agent/plugins/model_router.py         73 stmts  100%
TOTAL                                          1202 stmts  100%
```

Every test in the brief's list has one: successful execution, timeout,
malformed response, provider unavailable, ledger recording, the cache
interface, a cache miss, dashboard reporting, Broker integration, replay
consistency, no routing inside the provider, and no subprocess or network
import outside the approved location.

The unit suite runs against a scripted transport. That is not a
compromise: what is under test is *what this provider does with what the
daemon says*, and a test needing a live model would test the model
instead — slowly, and differently on every machine. The live proof is §1
and §3 above, run against Ollama 0.32.5 serving `gemma4:latest`.

## 6. Three defects, and how each was found

1. **A latent `NameError` in the Dashboard, found by the linter.**
   `sources.py` used the "not measured" marker without importing it, so
   the first execution with an unrecorded latency would have crashed while
   rendering the founder page. Every execution in the suite happened to
   have both a latency and a cost — which is exactly how a hole like that
   stays open. Fixed, and pinned by a test that records an execution with
   neither.
2. **The economy totals read as part of the last decision**, because they
   sat at the same indent as its fields. Found by reading a live frame,
   which is also how MB032's two panel defects turned up. A `TOKEN
   ECONOMY` header fixes it, and a test asserts the header is there.
3. **An MB032 test passed on a substring.** Its "no execution surface"
   check grepped for `def execute` and matched `def executed`, a
   read-only property. Rewritten to walk the AST for exact function
   names — the same false positive MB032 itself hit with `find_open`, now
   fixed in both places. The rule was also *refined* rather than relaxed:
   this layer may now invoke a provider it was handed, and still may not
   contain transport of its own.

## 7. Debt and known limitations (Rule 10)

1. **The cache never hits**, because nothing verifies generated text. The
   interface, the wiring, the metric and the panel are all real; the
   missing piece is a verifier, and it is the single highest-value thing a
   future brief could add to the token economy.
2. **`hermes3` is the default model and it is not installed here.** ADR-0002
   chose it; the founder's machine has `gemma4:latest`. Out of the box the
   default therefore produces the `rejected` result in §3 — accurate, and
   still a papercut. Changing the default without measuring anything would
   just move the papercut.
3. **A provider is a runtime, not a model.** Which checkpoint Ollama is
   serving is configuration, not a profile, so the Broker cannot choose
   between two local models. Per-model profiles need the benchmark store.
4. **Quality is still declared, never measured.** `quality_declared` is
   recorded on every execution specifically so a benchmark store can
   compare the claim against what was delivered — but nothing measures yet
   (MB032 debt item 2, unchanged).
5. **No streaming.** One request, one answer, one timeout. A 22-second
   local generation shows nothing until it finishes, which is a poor
   experience and needs `httpx` and a Dashboard that can render partials.
6. **No cost ledger and no budget.** MB032's debt, unchanged: cost is
   recorded per execution and totalled, but nothing enforces a ceiling.
7. **`plugins/providers/` still holds two stubs** (`hermes_provider.py`,
   `chatgpt_provider.py`) that raise `NotImplementedError` and are now
   superseded. They live in a package frozen since MB025 and were left
   untouched rather than spending an exception on a deletion.
8. **`--ask` runs a machine scan first** when none has run, because a
   provider the machine has never been scanned for correctly reads as
   absent. That costs a few seconds on the first ask of a fresh state
   directory. The normal launch path scans on its first Runtime cycle
   anyway.
