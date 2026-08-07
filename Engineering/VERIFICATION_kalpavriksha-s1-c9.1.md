# Verification Report — `kalpavriksha-s1-c9.1`

**Gate applied:** Quality Gate Rule 001 · **Verdict: GREEN** · **Date:** 2026-08-06

| | |
|---|---|
| Tag | `kalpavriksha-s1-c9.1` (annotated) |
| Commit | `e224fd8` |
| Milestone | Sprint 1, Component 9.1 — Execution Request, reopened |
| Supersedes | `kalpavriksha-s1-c9.0` → `6bc53d4` |
| Implements | **ADR-0022** and **ADR-0023 D2**, both ratified |

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

| | At commit `e224fd8` | At tag |
|---|---|---|
| Full suite | **2,479 passed · 0 failed · 1 skipped** | **2,479 passed · 0 failed · 1 skipped** |
| Architecture guards (6 modules) | 215 passed · 1 skipped · 0 failed | 215 passed · 1 skipped · 0 failed |

**Identical.** Reconciliation: 2,462 at `c13.0` + **17** added by C9.1 = **2,479**. Exact. C9's own suite: 102 → **119**.

## 3 · Ruff

C9.1's two files clean. Repo-wide **21 findings, identical to `c13.0`** — the pre-Sprint-1 baseline. **Zero introduced.**

## 4 · What changed

```
src/master_agent/foundation/execution_request.py   +68 / -…
tests/test_foundation_execution_request.py         +100 / -…
```

**151 insertions, 17 deletions, two files.** `git diff --stat kalpavriksha-s1-c13.0 kalpavriksha-s1-c9.1` limited to `src/` and `tests/` shows **exactly these two files** — every other component is byte-identical, including C4, C7, C8, C10, C11, C12, C13 and C14.

`foundation/__init__.py` is unchanged: the two fields are not new exported symbols.

## 5 · The two fields

| Field | Type | Source of truth |
|---|---|---|
| `reversibility_class` | `ReversibilityClass` | **Reversibility Registry** (§4.3's owner), via `classify()` alongside the A2 attestation |
| `expected_effect` | `str` | **Planner**, via Constitution §17's `Step` and its Expected Outcome |

Both **required, no defaults**. A defaulted class would be the guess VEDA 04 A2 forbids; a blank effect is a step whose completion cannot be checked, which Objective Engine Spec V2 refuses.

Placed after `action_class`, before `consequence`. All existing callers use keyword arguments, so **measured positional breakage is zero**.

## 6 · Three superseded guards, and their reasoning preserved

ADR-0022 §5.2. Each is changed rather than deleted, and each keeps the record of what it used to assert:

| Guard | Change |
|---|---|
| `test_it_has_no_dependency_on_the_warrant_type` | → **`test_it_carries_no_warrant`**. It formerly asserted no import from `warrant` at all, *"which the Reversibility Registry attests (A2) rather than the caller asserting."* Now: the **vocabulary** is imported; the `Warrant` **type** still is not, asserted by imported-name |
| `test_it_depends_only_on_components_seven_and_six` | → **four, six and seven**. C4 joined the dependency set |
| `test_it_holds_no_field_the_kernel_owns` | `reversibility_class` and `expected_effect` removed from the list. **The other fourteen names stay** |

**This is the honest cost of ADR-0022**, recorded rather than quietly edited: C9 was built to stop the caller asserting its own reversibility class, and this milestone permits exactly that — with ADR-0022 D2 as the discipline and **R34** as the residual.

## 7 · R34 remains open, and is marked in source

The A2 attestation does **not** bind to the carried `reversibility_class`. A caller can present a genuine, fresh, correctly attributed A2 attestation together with a different class, and nothing detects it. The dangerous direction is understatement.

**Two `TODO(ADR-0022)` markers** are in the Kernel and one in C9's module docstring, naming R34 and ADR-0023 D5's close — `A2.subject = sha256(payload_digest + "\x1f" + reversibility_class.value)`. Until that ships, **the carried class is trusted**, per the founder's instruction.

## 8 · Tag history

**`c10.0` through `c14.0` are not re-cut and remain valid.** They contain the earlier `ExecutionRequest` and were verified against it; history is linear and nothing was rewritten. `c9.0` remains in place as the record of what it superseded.

## 9 · Working-directory note

C15 Parts 1–4 are untracked and therefore absent from this tag. Their test fixtures were updated in the working directory to supply the two new fields — **fixtures only, no Kernel source touched** — and all 188 C15 tests plus C9's 119 pass locally, 307 together.

---

*Generated in clean checkouts of commit `e224fd8` and tag `kalpavriksha-s1-c9.1`, per Quality Gate Rule 001. All temporary worktrees removed.*
