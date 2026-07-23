# Vision

Status: Frozen (2026-07-23) — Miracle 003.5, Foundation Freeze

`WHY.md` tells the origin story — the specific problem that made this
project worth starting, and the two-part bet the architecture makes.
This document is the structured, longer-range complement to it: mission,
vision, values, and long-term goals, named as four distinct things on
purpose, because conflating them is one of the most common ways a
project's principles quietly erode over time. Read `WHY.md` first for
the "why now"; read this for the "why, always, and toward what."

## Mission, vision, values — and why they're not the same thing

- **Mission** is what we do, today, concretely. It answers "what is this
  project's job." It's a sentence, not a paragraph, and it doesn't
  change often.
- **Vision** is the world we're trying to bring about if the mission
  succeeds completely. It's a description of a future state, not a list
  of features — it should still be true even if every specific technical
  choice in `ARCHITECTURE.md` gets replaced.
- **Values** are the standards we hold ourselves to while pursuing the
  mission, independent of whether they're the fastest path to the
  vision. `MANIFESTO.md` states these; `ENGINEERING_PRINCIPLES.md` and
  `PRODUCT_PRINCIPLES.md` are what the values imply once you have to
  actually write code or design a screen.
- **Long-term goals** are checkpoints — falsifiable, dated, or at least
  orderable claims about what should be true at some point in the
  future. They're allowed to be wrong and get revised; the vision they
  serve is not.

Keeping these four separate matters because they fail differently. A
mission goes stale when the market changes. A vision goes wrong when the
premise it's built on turns out false. Values get compromised under
deadline pressure — that's the failure mode this project has to guard
against hardest, given the Founder Edition deadline (`docs/TIMELINE_RISK.md`).
Long-term goals just get missed, which is fine, as long as missing one
doesn't get quietly reinterpreted as "the vision was wrong."

## Mission

Turn a stated human intention into a verified, completed outcome —
without the human doing the coordination work of deciding which tool,
managing context between tools, or checking whether it actually worked.
This is the Kalpavriksha Principle (`ARCHITECTURE.md` §1): Intent → Plan
→ Delegate → Execute → Verify → Learn → Report, as one system, not as
seven manual steps a human currently performs by switching between a
chat window, a terminal, a file explorer, and their own memory.

## Who it serves

**Today, concretely: one founder**, building this system for their own
daily use first (`PRODUCT_PRINCIPLES.md`'s "build for one founder first,
scale for millions later" isn't a slogan — it's why there's no plugin
marketplace, no multi-user support, and no cloud sync in the codebase
yet, even though all three are easy to imagine wanting eventually).

**Eventually: anyone who currently acts as their own AI orchestrator** —
manually deciding which model or tool handles which task, manually
carrying context between them, manually verifying results. That's a
wide population precisely because it's not a specialized skill; it's
overhead every serious AI user currently pays, regardless of their
domain. Master Agent's bet is that this overhead is a product problem
worth solving generally, not a footnote to solve per-user.

## What problems it solves

1. **Coordination is manual and invisible.** Nothing tracks "I asked
   for X, here's what actually happened, here's proof it worked" across
   a sequence of AI-assisted actions today — the human is the only
   system component holding that thread together, and they lose it
   constantly.
2. **Trust requires either blind faith or constant supervision.** Most
   AI tools are either fully autonomous (worrying, for anything
   consequential) or require the human to review every single step
   (exhausting, defeats the point). The Permission System exists because
   there's a real, addressable middle: cheap read-only actions run
   freely, consequential actions need one clear approval, and nothing
   silently escalates from one to the other.
3. **"Which AI tool" is a burden that grows, not shrinks.** No single
   model or provider stays best forever. A human re-learning "which tool
   for which job" every few months is a tax the Model Router is built to
   eliminate — see `ARCHITECTURE.md` §5.

## What success looks like in five years

Not "Master Agent supports N integrations" or "Master Agent has M
users" — those are lagging indicators of something else going right, not
the thing itself. Success, five years out, looks like:

- **A person states an intention in plain language — voice or text —
  and the coordination work disappears from their attention entirely.**
  They think about outcomes, not tools. The system quietly picks models,
  sequences steps, asks for approval only when it should, and reports
  back in terms of what actually happened, not what was attempted.
- **Trust is earned through a visible, consistent track record, not
  through blind delegation.** Every mission's plan, approval, and
  verified outcome is inspectable after the fact (Local Memory's job,
  once built) — the system's reliability is demonstrable, not just
  claimed.
- **The architecture from `ARCHITECTURE.md` has been extended, not
  rewritten.** New capabilities (voice, memory, new model providers, new
  local actions) arrived as new plugins and new Actions behind the
  existing contracts — `Plugin`, `Action`, the Permission System's grant
  model — because those contracts were designed to be extended rather
  than outgrown. If a five-years-later engineer has to explain "we had
  to rip out the core to add X," that's the vision failing, regardless
  of how successful the product otherwise became.
- **It still works completely offline, on one machine, for one person**
  — because "local-first, cloud-enhanced" was a permanent constraint,
  not a v0.1 simplification that got quietly dropped once cloud
  infrastructure was easier to reach for.

If any one of these stops being true, that's a more urgent finding than
any roadmap slip — the same standard `WHY.md` already sets for its own
premise.
