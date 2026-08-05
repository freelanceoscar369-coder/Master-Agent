# Quality Gate Rules

**Status:** Permanent. This is the checklist run before every milestone and every release.
**Established:** 2026-08-05, after Sprint 1 Component 1.
**Relationship to other documents:** `ENGINEERING_PRINCIPLES.md` states how to *write* code. This document states what must be *true* before work is declared done. The two do not overlap and neither supersedes the other.

Rules are numbered permanently. A rule is never renumbered, never reworded to mean something different, and never deleted — if a rule stops applying it is marked superseded, with the reason and the date, so the history of what this project has considered "done" remains readable.

---

## Rule 000

> **Every engineering change must leave the repository more trustworthy than it was before the change.**

Trustworthiness is not the same as feature count, test count, or lines shipped. A change that adds capability while making the pass/fail signal less readable has failed Rule 000, however much it delivers.

The practical test: **after this change, is it easier or harder for the next person to tell whether the system is working?**

---

## Rule 001

> **A milestone is GREEN only if:**
>
> - **Clean checkout**
> - **Tag checkout**
> - **Tests executed**
> - **Architecture guards executed**
> - **Verification report generated**
>
> **The working directory is never considered evidence.**

### Why this rule exists

It was written after a real false green, and the specifics matter more than the principle.

Sprint 1 Component 1 (the Canonical Clock) was verified in the working directory: 28 of 28 passing, reported green, committed, tagged `kalpavriksha-s1-c1`. Run in an isolated checkout of that same tag it was **27 of 28**. The failing test was an architecture guard whose allowlist had been built by scanning the filesystem — which contained roughly 59 uncommitted source files. The list described a state no checkout could reproduce.

**The defect was invisible in exactly the place it was verified, and visible in exactly the place that mattered.**

Three things this establishes, each of which is the reason for a bullet in the rule:

- **A working directory is one person's uncommitted opinion.** It contains work in progress, local experiments, and files git has never seen. It cannot be reproduced by anyone else and it will not be what ships.
- **The tag is the artifact.** Whatever the tag resolves to is what a colleague clones, what CI builds, and what gets deployed. If it has not been run *there*, it has not been run.
- **Architecture guards are not ordinary tests.** In the incident above, every unit test passed at the tag. Only the guard failed — because a guard is the only kind of test that reasons about the *shape* of the repository, and the shape is precisely what differs between a working directory and a checkout.

### How to run it

```bash
# 1 · Clean + tag checkout, isolated from the working directory
git worktree add /tmp/verify <tag>

# 2 · Tests + architecture guards, executed there, against that tree's source
cd /tmp/verify && PYTHONPATH=/tmp/verify/src python -m pytest tests/ -q

# 3 · Record the numbers from THIS run in the verification report

# 4 · Clean up
cd - && git worktree remove /tmp/verify --force
```

`PYTHONPATH` is not optional. Without it an editable install silently imports the *working directory's* source into the checkout's tests, which reproduces the exact failure mode this rule exists to prevent.

### Order of operations for tagging

A tag must never be created before it is proven green, because a tag that has to be moved is not a milestone.

1. Commit
2. Verify the **commit** under Rule 001, in a worktree at its SHA
3. Create the annotated tag **only if green**
4. Re-verify at the tag for the record

### What a verification report must contain

- The tag or SHA verified
- Tests passed / failed / skipped, from the clean checkout
- Architecture guards, named, with their result
- Any failure, with its category: committed code · untracked work · introduced by this change · test assumption

A report that does not distinguish those four categories is not evidence. It is a number.

---

## Using this document

**Before declaring any milestone or release:** work down the rules in order. Every rule must pass. A rule that "mostly passes" has failed.

**When a gate fails:** the milestone is not green. Fix, re-verify from step 1, and do not create the tag until it passes. Never lower a gate to make a milestone fit.

**Adding a rule:** rules are added when a real failure demonstrates a gap — never speculatively. Each new rule states the incident that produced it, because a rule without a story is a rule nobody will defend under deadline pressure.

**Superseding a rule:** mark it superseded with the date and reason. Do not delete it and do not reuse its number.
