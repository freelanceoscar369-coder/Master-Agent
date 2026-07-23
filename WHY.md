# Why Master Agent Exists

## The problem

Right now, getting an AI to actually finish something means the human
does the orchestration: pick which tool for which task, copy context
between them, remember what happened last time, check whether it actually
worked. The intelligence is distributed across tools; the coordination
work — the part that's tedious and error-prone — is still 100% manual.

Master Agent exists to take over that coordination layer. Not to be
"another chatbot" that answers questions well, but to be the thing that
sits between a stated intention and a completed outcome: planning what
needs to happen, delegating each piece to whichever capability handles it
best, executing, checking the result actually matches what was asked for,
and reporting back — the Kalpavriksha Principle (see `ARCHITECTURE.md`
§1): a human expresses an intention; the system plans, delegates,
executes, verifies, learns, reports.

## Why "orchestration layer," specifically

Two things are true at once, and the architecture is a bet that they stay
true:

1. No single model or tool will be the best choice for everything,
   indefinitely. ChatGPT and a local Hermes model are today's pair; there
   will be a third, a fourth, better and worse at different things.
2. A human doesn't want to be the one deciding, every time, which tool
   that is — and doesn't want to lose control over what happens with
   their filesystem, calendar, or accounts along the way.

Master Agent's job is to resolve (1) automatically — see the Model
Router in `ARCHITECTURE.md` §5 — while never taking (2) away from the
human — see the Permission System, §4.4. Those two constraints, together,
are the actual product. Everything else (voice, memory, a desktop UI) is
in service of making that combination usable day to day.

## Why now / why this founder

Mission Brief 001 exists because the fastest way to find out whether this
premise holds up is to build the smallest real version of it — one
sentence in, one real filesystem write out, with a real approval gate —
and see whether it actually feels like the thing described above, or
whether the architecture is solving a problem that doesn't show up in
practice. It did: the transcript in `docs/MISSION_BRIEF_001.md` is the
first evidence this isn't just a diagram.

## What "success" looks like, longer term

Not "Master Agent can do more things." Success is: the human stops
thinking about *which* tool to use, and starts only thinking about *what*
they want done — with enough trust in the approval gate that they never
feel like they've lost control to get that convenience. If a future
version of this file needs updating because that premise turned out to be
wrong, that's a more important finding than any single feature.
