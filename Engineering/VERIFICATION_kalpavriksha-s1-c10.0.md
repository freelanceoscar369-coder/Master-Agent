# Verification Report — `kalpavriksha-s1-c10.0`

**Gate applied:** Quality Gate Rule 001 · **Verdict: GREEN** · **Date:** 2026-08-05

| | |
|---|---|
| Tag | `kalpavriksha-s1-c10.0` (annotated) |
| Commit | `36d14f7` |
| Milestone | Sprint 1, Component 10 — Attempt Token |
| Previous | `kalpavriksha-s1-c9.0` → `6bc53d4`, unchanged |

---

## 1 · Rule 001 criteria

| Criterion | Result |
|---|---|
| Clean checkout, `git status` empty | ✅ |
| **Commit verified before the tag existed** | ✅ |
| **Tag verified afterwards, second independent worktree** | ✅ |
| PYTHONPATH pinned; source isolation asserted | ✅ |
| Full suite + architecture guards against the tag | ✅ |
| Verification report generated | ✅ this document |

## 2 · Test reconciliation

| | At commit `36d14f7` | At tag |
|---|---|---|
| Full suite | **2,133 passed · 0 failed · 1 skipped** | **2,133 passed · 0 failed · 1 skipped** |
| Architecture guards | 215 passed · 1 skipped · 0 failed | 215 passed · 1 skipped · 0 failed |

**Identical.** Reconciliation: 2,068 at `c9.0` + **65** = **2,133**. Exact.

## 3 · Ruff

C10's files clean. Repo-wide **21 findings, identical to `c9.0`**. Zero introduced.

## 4 · What changed

```
src/master_agent/foundation/attempt_token.py   new, 173 lines (28 statements)
src/master_agent/foundation/__init__.py        exports only, +8
tests/test_foundation_attempt_token.py         new, 394 lines
```

**575 insertions, 0 deletions, three files.**

## 5 · Components 1–9 unchanged

Byte-identical, verified by diff against `c9.0` limited to prior modules.

## 6 · Decisions carried

**Amendment 001 M4** applied over the roadmap: C10 depends on **nothing** — not the Warrant, not even the Clock. §3.5's operation takes an id, and the declared API is a string, an int and a timestamp. A guard asserts the module imports nothing from `master_agent` at all.

`idempotency_key` is §8.6's `(warrant_id, attempt_seq)`, with `opened_at` deliberately excluded — one attempt retried by a Worker is still one attempt.

`attempt_seq` rejects `bool`: `isinstance(True, int)` is `True`, so without the explicit check `True` would construct a valid-looking first attempt.

**Carries no budget and no retry policy.** §8.5 sets the budget at mint *"never by the retry loop"*, and §8.4 — the most important clause in §8 — belongs to the Kernel and the Reversibility Registry, never to the thing being retried.

## 7 · Risk recorded

**R17** — `attempt_seq` monotonicity is unenforceable in a pure value; the Kernel owns sequencing via `attempt()`. C15's brief must state it.

---

*Generated in clean checkouts of commit `36d14f7` and tag `kalpavriksha-s1-c10.0`. All temporary worktrees removed.*
