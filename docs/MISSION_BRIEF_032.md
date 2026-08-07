# Mission Brief 032 — Wiring the AI Capability Broker into Kalpavriksha

Status: **Shipped** — 2026-07-30

Implements ADR-0017 and ADR-0018 as ratified. **No new ADR** — nothing
architectural was decided here; MB027 decided it, the founder ratified it
as Constitution Amendment 2, and this brief connects it.

## Objective

MB031 shipped a complete, fully-tested decision engine that nothing
called. This brief makes it the only thing in Kalpavriksha that answers
*"which AI?"*.

```
Task -> Broker -> DecisionRecord -> Approval (if required) -> Execution
```

## 1. What actually changed, and what did not

**One frozen file was modified**, and it was named in advance by a
ratified ADR:

| File | Permitted by |
|---|---|
| `plugins/model_router.py` | ADR-0017 Consequences + Constitution Amendment 2 §3.3 |

Amendment 2's §3.3 row says it outright: *the Model Router resolves which
Reasoning Provider by consulting the Broker, rather than implementing its
own ranking.* ADR-0017's Consequences named this file as "a documented
contradiction" and named its migration as a future brief. This is that
brief, and the exception is recorded where every other one is — in
`tests/test_dashboard_architecture.py`'s `RATIFIED_EXCEPTIONS`, the list
that *is* the amendment record.

**Nothing else frozen moved.** `runtime/`, `mission_control/`,
`persistence/`, `executor/`, `verification/` and `broker/` are untouched;
the guard test proves it. Notably:

- **The Broker package was not edited at all.** MB031's invariant — a
  kernel service that imports nothing — is re-asserted from the other
  side: MB032 wired it up without reaching back into it.
- **No new event type, no new approval path, no new snapshot key.** Paid
  selections ride MB028.1's Approval Queue through its published
  contract, so they publish the `APPROVAL_REQUESTED`/`APPROVAL_REQUIRED`
  events a founder's console already watches for. This is ADR-0018
  Decision 3's rule ("two existing queues, two existing gates, zero new
  approval paths") applied to the wiring rather than to the learning loop.

New code lives in one new package, `ai_infrastructure/`, plus additive
changes to `dashboard/` (not a frozen package — MB029 and MB030 both
changed it), `launcher/boot.py` (the composition root), and `config.py`.

## 2. The seam, and why it needed a package of its own

The Broker is deliberately unable to fetch its own inputs or act on its
own outputs. Something has to supply and consume:

```
    Desktop Executive inventory ─┐
    founder configuration ───────┤
                                 ├─> ProviderSource ─> profiles ─┐
                                                                 v
                              ModelRouter ─ request ───────> CapabilityBroker
                                                                 │
                                    DecisionLedger <── record ───┤
                                                                 v
                              Approval Queue <── paid? ── ProviderApprovalGate
                                                                 │
                                                            Selection
```

`ai_infrastructure/` is **not** the AI Infrastructure Executive (ADR-0018
Decision 2). It performs no discovery, no probing, no benchmarking and no
installation — it *reads* the scan the Desktop Executive already
published, exactly as the Dashboard does, so Environment access still has
one door (Constitution Rule 4).

And it holds **no ranking**. ADR-0018's Consequences name a ranking
function growing outside the Broker as the single failure mode that would
invalidate the design, so the test suite parses the package for it: the
only `sorted(key=...)` in it sorts by `provider_id`, which is canonical
ordering for a record and the opposite of a preference.

## 3. Deliverable by deliverable

**1. Provider routing replaced.** The four branches are gone:

```python
if not ctx.is_online:             return self._provider("hermes")
if ctx.is_sensitive:              return self._provider("hermes")
if ctx.requires_strong_reasoning: return self._provider("chatgpt")
return self._provider(self._default_provider)   # "hermes"
```

They became four *facts about the request* — `offline`, `sensitive`,
`requires_strong_reasoning`, `preferred_provider` — that the Broker turns
into a decision with a record behind it. `ModelRouterConfig.default_provider`
went with them: a default provider sitting in configuration is the same
hardcoded ladder in a different file.

The most interesting translation is the third. *"I need this done well"*
is a statement about **quality**, so it becomes a quality floor
(`BrokerConfig.strong_reasoning_min_quality`). Turning it into a product
name was the bug.

**2. Broker initialisation at startup.** Boot step 8 now constructs the
Broker, the ledger (restored from disk), the profile source and the
approval gate, and reports what it built:

```
[OK  ] AI Capability Broker  (policy balanced/1; 1/5 provider(s) available,
                              0 past decision(s) restored)
```

It sits after Executives (the estate is read from one of them) and before
the Dashboard (which displays its decisions).

**3. Profiles from the Desktop Executive.** `ProviderSource` reads the
same `cached_inventory` the Dashboard reads and rebuilds the estate on
every request, so a provider that was absent at boot and is present now is
selectable now. Three availability rules, each reporting a fact:

| Spec | Available when |
|---|---|
| inventory-backed, scan present | the scan says installed **and** healthy |
| inventory-backed, no scan yet | **no** — "not scanned" is not "installed" |
| credentialled service | the founder enabled it in configuration |

The middle row is ADR-0016's discipline applied to provider selection. A
launcher that assumed local providers were present until proven otherwise
would select one and fail at call time — which is exactly the "fail later"
Deliverable 4 exists to stop.

**4. Structured refusal.** `AiCapabilityService.decide()` returns a
`SelectionOutcome`; a refusal is data, not an exception, and carries the
reason, the policy version, and every provider considered with why it was
rejected. `select()` raises for callers whose signature has no room for a
refusal (`select_provider()` must return a provider or not return), and
the three refusal kinds raise three different types, because a caller
catching "waiting on the founder" is asking a different question from one
catching "nothing is installed".

**5. Paid selections reach the Approval Queue before execution.** The rule
is two lines:

```python
if not is_free(profile.cost):                     -> ask
if sensitive and profile.privacy != PRIVATE:      -> ask
```

The second is ADR-0017 Decision 7's deliberate addition: a *free* cloud
model is still a third party receiving the founder's data. Both are
classified `IRREVERSIBLE` — spent money cannot be unspent, sent data
cannot be unsent — which inherits ADR-0009's shipped guarantee that no
`ALWAYS_FOR_CAPABILITY` grant can ever satisfy them. A standing "yes, use
paid AI" can never authorise the next call.

**6. Free providers run immediately.** Free, private, policy permits →
`approval_state=not_required` and the selection is executable with nobody
interrupted.

**7. A `DecisionRecord` with every AI task.** The `DecisionLedger` is
wired as the Broker's `sink` — the outbound port MB031 built for exactly
this — so every decision is recorded before any caller can act on it,
including refusals and including decisions made by callers other than the
service. It persists to `broker_decisions.json` in the state directory,
written atomically.

**8. Replay uses the stored record.** `ledger.replay(id)` builds a
throwaway engine on the **record's own** policy and providers, with the
clock pinned to the original timestamp and no sink, so replaying history
cannot change it. Proven across the case that matters: decide under
`balanced`, restart the process with the founder now on `best_quality`,
and the stored decision still replays to the same winner and the same
digest.

**9. The Dashboard shows live decisions.** A new founder panel:

```
AI DECISIONS  (policy balanced/1, 1/5 provider(s) available)
  + ollama.local  (reasoning)
      Why       ranked first of 1 eligible by cost, quality,
                latency; quality 0.72 clears the floor 0.60
      Cost      free
      Quality   fair (0.72, declared)
      Approval  not required
```

Selected provider, why, cost tier, quality tier — the four Deliverable 9
asks for. Every value is resolved in `ai_infrastructure` and transcribed
by the renderer: a panel that decided for itself what "expensive" means
would be a second opinion about cost in the layer least able to defend it
(ADR-0016). The report is *handed in* by the launcher exactly as the
machine inventory is, so looking at the screen can no more cause a
decision than it can cause a scan.

**10. Fail closed.** A Model Router with no selector refuses every
request. Not "falls back to the local one" — a fallback *is* a provider
decision, and making one when the decision-maker is missing is the
hardcoding this brief deleted. If the Broker cannot be constructed at all,
the boot step reports `unavailable` with the reason and the router is left
without a selector, so the failure is loud at launch and again at every
request.

**11. Obsolete code removed.** The four branches, `_default_provider`, and
`ModelRouterConfig.default_provider`. Asserted by AST: no argument, name,
or attribute called `default_provider` survives in `model_router.py`, and
a parameterised grep over eight vendor names finds none in it.

**12. Roadmap and living memory updated.** `ROADMAP.md`,
`MIRACLE_LEDGER.md`, `PROJECT_BRAIN.md`, and this file.

## 4. Where a product name is allowed to appear

Exactly one file: `ai_infrastructure/catalog.py`. It is the inventory
seam, and it is the same containment `desktop/catalog.py` already has —
adding a provider is one entry and nothing else changes. A parameterised
test greps every other module in the package for eight vendor names.

**Every number in that catalogue is declared and none is measured.**
`ProviderProfile` separates `quality` (what a provider claims) from
`benchmark` (what this system measured), and measurement wins where both
exist (ADR-0017 Decision 5). No benchmark store exists, so every profile
this build produces carries `benchmark=None`, every spec states its
`basis`, and the Dashboard labels the tier `declared` rather than letting
it read as a measurement.

## 5. Verification

**397 new tests, 1945 passing, 1 skipped, zero regressions** (1547
before). **100% statement coverage** of the new package and the rewritten
Model Router:

```
src/master_agent/ai_infrastructure/__init__.py     8 stmts   100%
src/master_agent/ai_infrastructure/approval.py    78 stmts   100%
src/master_agent/ai_infrastructure/catalog.py     36 stmts   100%
src/master_agent/ai_infrastructure/ledger.py     195 stmts   100%
src/master_agent/ai_infrastructure/profiles.py    54 stmts   100%
src/master_agent/ai_infrastructure/refusal.py     40 stmts   100%
src/master_agent/ai_infrastructure/service.py    139 stmts   100%
src/master_agent/ai_infrastructure/tiers.py       53 stmts   100%
src/master_agent/plugins/model_router.py          73 stmts   100%
TOTAL                                            676 stmts   100%
```

Proven, each as its own test rather than as a claim here: deterministic
replay (including across a restart, and against a policy the founder has
since changed); the paid approval workflow end to end, with the provider
itself proving it was never called before the founder answered; the free
provider workflow with nothing asked; and the Dashboard showing decisions
the launcher's own Broker made.

**Live run against the founder's actual machine.** Ollama is installed on
it, so the Broker picks it for plain reasoning — free, local, no approval
— keeps sensitive work on it, and refuses strong reasoning with:

> 5 provider(s) considered; none met the quality floor of 0.80 (best was
> ollama.local at 0.72)

which is a refusal a founder can act on: install something better, lower
the bar, or enable a cloud provider.

## 6. Two real defects, both found by running it

Neither was found by review, and both were in the panel rather than the
engine — which is where the risk actually was, since the engine shipped
tested in MB031.

1. **A refusal rendered as a success.** The first live run drew
   `+ none (reasoning)` with a green tick and `Approval  not required`
   underneath. That reads as *"we chose nothing and that was fine"*. The
   view model now carries `selected` explicitly (rather than the renderer
   testing for the string `"none"`, which would be one unlucky provider id
   away from the same bug), and a refusal renders with a warning glyph and
   no cost/quality/approval lines at all.
2. **The reason was truncated mid-number.** *"quality 0.72 clears the
   qual"* — the panel cut off the one sentence it exists to show. Labelled
   fields now wrap instead of truncating.

## 7. Design decisions worth stating

- **An override is a constraint, not a bypass.** `preferred_provider`
  survives, but it is expressed to the Broker as *"exclude every other
  provider"* — so it still produces a real decision with a real record,
  the excluded providers appear on that record with a reason, and an
  override naming something unavailable is refused rather than used
  because somebody asked nicely. Nothing is selected without a
  `DecisionRecord`.
- **The service records defensively even though the sink is wired.**
  Deliverable 7 says *every* AI task has a stored record; a service that
  quietly skipped one when its sink was mis-wired would break replay in
  the least visible way possible. The reconciliation is an identity match
  on the decision object, so it can never double-record.
- **Approval state annotates the decision rather than appending a second
  one.** "The founder was asked" and "the founder answered" are two
  moments in the life of one decision; two entries would read as the
  Broker deciding twice. The `DecisionRecord` itself is never rewritten.
- **A Broker failure does not stop the boot.** The Runtime, the Dashboard
  and the approval boundary are not the Broker's dependents. A system that
  cannot choose an AI can still do filesystem work, and it should say
  which half is broken rather than refusing to start.

## 8. Technical debt and known limitations (Rule 10)

1. **No provider actually generates text.** Both shipped `ModelProvider`
   plugins are documented stubs, and the launcher deliberately registers
   neither — registering a provider whose `generate()` raises would put a
   fictional Executive in the founder's Dashboard. The Broker chooses; the
   thing that runs the choice is a separate piece of work. `ModelRouter`
   raises `ProviderNotWired` with the chosen id, which is the honest
   answer.
2. **Declared quality numbers are first guesses** (§4). They will be wrong
   in ways only a benchmark store can fix (ADR-0017 §10, ADR-0018).
3. **A provider is a runtime, not a model.** Which checkpoint a local
   runtime is serving is invisible here; per-model profiles need the
   benchmark store to tell two of them apart.
4. **The ledger grows without bound** and is rewritten whole on each
   decision. This is the same unbounded-growth item already on
   `ROADMAP.md` for the persisted event log, and it should be solved once
   for both.
5. **Broker decisions are not in the Audit Stream.** They are durable,
   replayable, and visible on the Dashboard, but adding a
   `BROKER_DECISION` event type would mean editing a frozen file
   (`mission_control/events.py`) for reporting rather than for a
   guarantee. Deliberately deferred to a brief that can weigh that
   properly.
6. **"One approval per mission" (§15.3) is not implemented** for
   providers: approval is scoped to one task and consumed once. That is
   the safer default and matches MB028.1's semantics exactly, but a
   founder running a fifty-step paid mission would be asked fifty times.
7. **No cost ledger.** Nothing accumulates what has been spent, so no
   budget can be enforced yet (ADR-0017 §9). `cost` remains a bare number
   with no currency (MB031 debt item 5, unchanged).
8. **Exploration is not implemented** (ADR-0018 Decision 7). A provider
   ranked low is never selected and so never generates the samples that
   would let it climb — which does not matter until there is a benchmark
   store for it to climb in.
