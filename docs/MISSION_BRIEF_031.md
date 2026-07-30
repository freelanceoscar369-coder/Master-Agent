# Mission Brief 031 — AI Capability Broker (Core Decision Engine)

Status: **Shipped** — 2026-07-30

Implements ADR-0017, ADR-0018, and Constitution Amendment 2 §5.7.
**No new ADR** — nothing architectural changed; see §1.

## Objective

The decision engine, and only the decision engine. *Given these provider
profiles and this task, which provider should be used?* — answered
deterministically, auditably, and without ever contacting a model.

## 1. Nothing existing was touched

```
$ git diff --name-only v0.12.0-miracle-030 -- \
    src/master_agent/runtime src/master_agent/mission_control \
    src/master_agent/persistence src/master_agent/executor \
    src/master_agent/plugins src/master_agent/verification \
    src/master_agent/dashboard src/master_agent/desktop
(empty)
```

Everything is a new `broker/` package. It is not yet wired to anything —
deliberately: MB031 is the engine, and wiring it into the Runtime's Model
Router path is a separate brief with its own risk.

## 2. The forbidden list, enforced rather than promised

MB031's "Absolutely Forbidden" section is checked by tests, not trusted:

| Rule | How it is held |
|---|---|
| No provider execution | An AST test asserts the package imports none of `subprocess`, `socket`, `http`, `httpx`, `requests`, `urllib`, `openai`, `anthropic` |
| No provider names | A parameterised test greps every file for seven vendor names and fails on any hit |
| No execution surface | A test asserts no `def invoke`, `def execute`, `def launch`, `def download`, or `def install` exists |
| No discovery | The package has no filesystem access; profiles arrive as arguments |
| Kernel service, no dependencies | An AST test asserts the only `master_agent` imports are `master_agent.broker` |

The last one matters most. A kernel service consulted from everywhere must
depend on nothing, or it drags its dependencies into every caller
(ADR-0017). The Broker imports nothing from Mission Control, the Runtime,
persistence, or the Dashboard — recording goes through an injected
callable, the same outbound-port move MB025 used for `CheckpointSink`.

## 3. The algorithm

```
filter (hard constraints) -> quality floor -> rank by policy -> take the first
                                                             -> or refuse
```

Deliverable 8 is the load-bearing step, stated exactly as the brief does:
**the lowest-cost provider that satisfies the minimum required quality.**
If none satisfy the floor, `NO_PROVIDER_AVAILABLE`. Never a guess.

Filters are absolute — nothing in ranking can revive a filtered provider,
and no policy can override a task's constraints. Twelve rejection reasons
exist, each a sentence a founder can act on: `does not offer this
capability`, `sensitive work may not go to a third party`, `needs founder
approval, which has not been given`, and so on.

## 4. The scoring tension, resolved — and the bug it caught

MB031 Deliverable 3 asks for scoring. **ADR-0017 Decision 3 explicitly
rejected a blended score** as unauditable: *"a single blended number
cannot be audited — 'why didn't it use the local one?' has no answer
beyond 'the weights said so'."*

Both hold, because scoring **ranks within** the frozen filter-then-floor
structure rather than replacing it, and every component is recorded
separately on each candidate.

**Then the first draft proved the ADR right by breaking.** It had a
`BY_BALANCED` ranking key — quality divided by cost — and a smoke run
against four invented providers picked the *paid cloud* provider at
quality 0.95 over a *free local* one at 0.82, both clearing a 0.70 floor.
At realistic per-call costs the denominator barely moves, so "balanced"
silently degenerated into "best quality" and overrode Deliverable 8's
central rule.

The blended key was deleted. What distinguishes the policies is now the
**floor**, not a hidden weighting: `balanced` sets a higher bar than
`lowest_cost` and then takes the cheapest thing that clears it. That is a
sentence a founder can check against the record — which was ADR-0017's
whole point.

## 5. Determinism and replay (Deliverables 4, 6)

> Same task + same providers + same policy ⇒ the same decision, always.

Providers are sorted before anything reads them; ties break
lexicographically on `provider_id`; nothing consults a clock except to
stamp `decided_at`, which is excluded from the digest. `inputs_digest` is
a SHA-256 over the task, the policy, and the id-sorted providers — so the
same set in a different order fingerprints identically, because the
caller's list order is not an input to anything.

`replay()` uses the policy and providers **stored on the record**, never
the Broker's current ones. Replaying against today's providers would not
be reproducing history; it would be making a new decision and calling it
history. Replay also does not append to the ledger — replaying history
must not change it.

`replay_matches()` compares outcome, winner, floor, digest, **and the full
ranking** — not just the winner. Two policies can agree on first place and
disagree on everything after it.

## 6. Policy versioning (ADR-0018)

Every policy carries a version, and `policy_version` (`balanced/1`) lands
on every record. Switching policy leaves past decisions readable under the
rules they were actually made under — which is exactly what makes
ADR-0018's learning loop safe to add later: learning produces `balanced/2`
as a discrete artifact, and `balanced/1` decisions keep replaying against
`balanced/1`.

A policy also has a `hard_floor` a task cannot lower it past. A task may
raise the bar; nothing may lower it below the policy's minimum — the guard
against ADR-0018's cost-quality death spiral, where "just this once"
becomes the default.

## 7. Eight founder policies (Deliverable 7)

`balanced` (default), `lowest_cost`, `best_quality`, `prefer_local`,
`prefer_free`, `offline_only`, `cloud_allowed`, `privacy_first`.

Each is data: a name, a version, a ranking order, a default floor, a hard
floor, and three switches (`allow_cloud`, `allow_paid`,
`require_private_for_sensitive`). Adding one is a `SelectionPolicy`
literal; the engine reading them is fixed.

Sensitive work never goes to a third party unless a policy says so **by
name** — configurable, but never silently.

## 8. Verification

**180 unit + integration tests, 100% statement coverage of `broker/`,
1543 passing overall, 1 skipped, zero regressions** (1367 before). Ruff
clean.

```
src/master_agent/broker/__init__.py     5 stmts   100%
src/master_agent/broker/broker.py     102 stmts   100%
src/master_agent/broker/decision.py    80 stmts   100%
src/master_agent/broker/policy.py      72 stmts   100%
src/master_agent/broker/profiles.py    60 stmts   100%
TOTAL                                 319 stmts   100%
```

The integration suite runs a **ten-task workload** across a
seven-provider invented estate — including one provider that needs
approval and one that is down — under all eight policies, then serialises
the whole history to JSON, reads it back, and replays every decision. Plus
a **golden-answer regression table** for the default policy, so a future
change to filtering or ranking has to state itself rather than drift.

Two invariants worth naming, both asserted across the whole workload
rather than in one case: a provider needing approval is **never** chosen,
and sensitive work **never** leaves the machine.

## 9. Unexpected findings

1. **The blended score broke Deliverable 8** (§4). Found by running the
   engine once against realistic numbers, not by review. This is the
   second time in this project that implementing the thing an ADR warned
   against immediately demonstrated the failure mode the ADR predicted.
2. **Two of my golden answers were wrong, and the engine was right.** I
   guessed `w2` and `w8` would go to paid providers; the free local model
   measured 0.79 and cleared both floors at zero cost. The table now
   records the reasoning per row so a reader can check it rather than
   trust it.
3. **Two test expectations were also wrong for the same reason** — both
   local providers in the unit fixture are free, so cost ties and quality
   correctly breaks the tie. That is a genuine property, now asserted
   explicitly (`test_quality_breaks_a_cost_tie`).
4. **MB031's names differ from ADR-0017's.** The brief says
   `ProviderProfile` / `TaskProfile` / `SelectionPolicy` / `DecisionRecord`;
   ADR-0017 wrote `ProviderDescriptor` / `CapabilityRequest` /
   `BrokerDecision`. I followed **MB031**, since it is the implementation
   brief, and `BrokerDecision` is common to both. Flagged rather than
   silently reconciled: a future reader comparing the two documents should
   know they name the same shapes.
5. **`benchmark_confidence` is stored and never read.** ADR-0017's cold-
   start penalty needs it, and that belongs to the learning loop
   (ADR-0018), not here. Carried on the profile so the field exists when
   that brief arrives — named in the debt list rather than left as a
   surprise.

## 10. Technical Debt and Known Limitations (Rule 10)

1. **The Broker is not wired to anything.** Nothing calls it yet. Retiring
   `ModelRouter.select_provider()`'s hardcoded `"hermes"`/`"chatgpt"`
   branches is the next brief, and it is where the real integration risk
   lives.
2. **No cost ledger, no benchmark store, no recommendation engine.**
   ADR-0017 froze all three; MB031 implemented only the decision engine,
   as instructed. `ProviderProfile.benchmark` is an input here, not
   something the Broker maintains.
3. **`benchmark_confidence` is unused** (§9.5).
4. **No approval integration.** A provider with `requires_approval=True`
   is simply never selected. Routing that into MB028.1's Approval Queue —
   so a founder can say yes to a paid provider — is a separate brief.
5. **Cost is a bare number** with no currency and no units. Fine while one
   caller populates every profile consistently; a real cost model
   (ADR-0017 §9) needs `CostComponent`s.
6. **No decision caching**, deliberately. ADR-0017 explains why: a cached
   decision must be invalidated by four independent sources, and a stale
   hit spends money a budget filter would have refused. Determinism means
   it can be added safely later.
7. **Latency is a single number**, not a percentile. ADR-0017's design
   wants p50 and p95.
