# Mission Brief 035 — Verifying Generated Text

Status: **Shipped** — 2026-07-30

**No new ADR.** ADR-0011 froze the Verification Subsystem; this is its
second concrete Verifier, and no frozen component changed.

## Objective

MB033 shipped a Prompt Cache that never hit. MB034 shipped a Prompt
Library with no automatic writer. Both were blocked on the same missing
sentence: *Kalpavriksha can tell whether a generated answer was any
good.*

Proved live against `gemma4:latest`:

```
1. AN ANSWER THAT MEETS WHAT WAS ASKED FOR
   answer  : 'Blue'
   verdict : matched   verified=True   cache=miss
      [PASS] the answer is not blank
      [PASS] mentions 'blue'
      [PASS] at least 1 word(s)

2. THE SAME QUESTION AGAIN — reused, no provider call
   cache=hit   economy: 1 hit(s)

3. THE SAME QUESTION, A DIFFERENT EXPECTATION
   verdict : partially_matched   verified=False
```

## 1. What changed, and what did not

**Zero frozen files modified.** The guard shows the same seven files
MB032 accounted for; MB035 added none.

`verification/` is itself frozen, so the new Verifier lives **outside**
it — `ai_infrastructure/text_verifier.py` — importing the published
contracts and implementing the one abstract method. That is what a
Worker's Verifier is supposed to do anyway, and `BrowserVerifier` already
proved the shape generalises. Nothing in `verification/` was touched, and
a test asserts the package still contains exactly its five original
files.

Changed, all additively: `ai_infrastructure/execution.py` (verify, record
the verdict, hand a checked prompt to memory),
`ai_infrastructure/ledger.py` (two fields), `memory/memory_service.py`
(one writer), `config.py`, `dashboard/` (one line), `launcher/boot.py`
(wire the sink).

## 2. The one interpretation this brief had to make

`Verifier.capture_observation_dict()` says: *re-observe current real-world
state fresh; never return a cached value from a prior Execution.* For a
browser that means reading the page again. For generated text there is no
page — **the answer is the artefact**.

The reading taken, stated in the module docstring so a future reader finds
the reasoning rather than inferring it: re-derive the observation from the
artefact by deterministic measurement, every time, and never consult
anybody's *opinion* of it. So the observation is length, word count,
whether it parses as JSON, what it contains — facts a second reader could
recompute — and the provider is never asked whether it thinks it did well.
A test asserts no field named `success`, `confidence` or `score` exists.

**No model judges another model.** Asking an LLM whether an LLM's answer
was good needs an LLM to judge *that*; ADR-0017 refused to start that
recursion for provider selection and MB034 refused it for memory. A
verdict here is arithmetic over an `ExpectedOutcome` stated *before* the
answer arrived, which is also the only kind of verdict that is
falsifiable.

**No new operators.** The five in the frozen evaluator express everything
here. `at_least_words` is a regex rather than a sixth operator, because
adding one would mean editing a frozen file to save writing a line.

## 3. What a verdict changes

**The cache stores on evidence, not on a promise.** MB033's `verified`
flag was a caller asserting the answer was fine. When an `ExpectedOutcome`
is supplied the verdict decides and the flag is ignored — evidence beats
assertion, which is exactly why ADR-0011 keeps Verification structurally
independent of Execution. `PARTIALLY_MATCHED` is deliberately not enough:
half of what was asked for is not what was asked for, and a cache that
remembered it would serve the same half answer forever.

**The cache ships on.** MB033 defaulted it off because nothing could
verify prose, so it could only ever have stored unchecked output. That
reason is gone. A request that asks for nothing specific still stores
nothing, so turning it on makes reuse *reachable* without making anything
unverified cacheable.

**MB034's Prompt Library has a writer.** A checked prompt goes to the
Prompt Library when it matched and the Failure Library when it did not,
carrying the provider, the verdict, what was asked for, and the evidence
id. It arrives through an **outbound port** rather than an import:
`ai_infrastructure` stays free of `memory/`, and `memory/` is already
forbidden from reaching back (MB034 asserts it).

**The founder sees the verdict.** One line on the AI panel, and
`not checked` is rendered rather than a blank — "not checked" and
"checked and failed" are different facts.

## 4. Verification

**153 new tests, 2763 passing, 1 skipped, zero regressions** (2610
before). **100% statement coverage** of both changed modules:

```
src/master_agent/ai_infrastructure/text_verifier.py    73 stmts  100%
src/master_agent/ai_infrastructure/execution.py       121 stmts  100%
```

Smaller than MB031–034 because the brief is smaller: one Verifier and its
consequences, composed onto contracts that already existed. There was no
new architecture to test.

## 5. Two defects, both found by running it

1. **"At least 1 word" passed on a blank answer.** The regex ended in
   `\S*`, which matches the empty string. That is precisely the silent
   pass this whole subsystem exists to prevent, in the first check written
   against it. The final quantifier is now `\S+`, and a test asserts a
   word-count check never passes on nothing.
2. **A cache hit ignored what the *new* caller asked for.** Found by a
   live run that asked one prompt with two different expectations: the
   answer stored under the first was served for the second, marked "not
   checked". A stored answer was verified against *the expectation it was
   stored under*, and serving it to somebody asking for something else is
   how "everything reused was verified" quietly stops being true. A hit is
   now re-checked against the current expectation — arithmetic, where
   calling the provider again is seconds — and falls through to a real
   call if it no longer qualifies.

A third, in the same family as MB034's: the evidence id in a memory's
`full_text` made every repeat of the same prompt a **new** record, because
the digest is taken over that field. Two runs produce two Evidence records
and one lesson. The stable sentence stays in `full_text` and the traceable
id moved to `summary`, so duplicate suppression works and the claim is
still traceable.

## 6. Debt and known limitations (Rule 10)

1. **Somebody has to state an expectation.** Nothing infers one, and
   nothing should — a check invented after the answer arrived is a
   rationalisation, not a verification. So the cache and the Prompt
   Library fill only for callers that say what they want. The real Planner
   (`ROADMAP.md`) is the component that would attach one to every step, as
   Constitution §3.2 already expects.
2. **Checks are structural, not semantic.** `contains`, `matches`, JSON
   shape, word count. They catch a blank answer, a refusal, a truncation,
   a wrong format — not an answer that is fluent, well-formed and wrong.
   ADR-0017 Decision 5 already named that gap for benchmarking; nothing
   here closes it, and no deterministic check can.
3. **The observation is capped at 100,000 characters** and says so when it
   truncates, because truncating the thing under test would make a check
   pass or fail on where the cut fell.
4. **A cache hit is re-verified but not re-recorded as new evidence for
   the store.** The stored entry keeps the verification it was stored
   with; the fresh check produces its own Evidence for this call's record.
   That is correct but means two evidence ids exist for one cached string.
5. **`Success Library` still has no writer from this path.** MB034 writes
   it from Mission Control's `verification_completed` event, and a prompt
   executed outside a mission has no such event. Publishing one would mean
   editing a frozen file for reporting rather than for a guarantee — the
   same call MB032 made about Broker decisions in the Audit Stream.
