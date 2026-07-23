# Start Here

Setting up Master Agent on a new machine (or recovering it after this one
died). Read `PROJECT_BRAIN.md` first for orientation, then come back here
to actually get running.

## 1. Prerequisites

- Python 3.11+
- Git
- (Optional, for later mission briefs) [Ollama](https://ollama.com) if
  you're running the local Hermes model — not required for what's
  implemented today.
- (Optional) [Obsidian](https://obsidian.md) to open the `obsidian/`
  founder vault as intended.

## 2. Get the code

If you already have a `.git` history (this bootstrap created one):

```
git clone <wherever you pushed this> D:\MasterAgent
cd D:\MasterAgent
```

If you're working from a delivered zip instead (no remote yet — see
"Known gap" below): unzip it so its contents land directly at
`D:\MasterAgent` (i.e. `D:\MasterAgent\ARCHITECTURE.md` should exist, not
`D:\MasterAgent\MasterAgent\ARCHITECTURE.md` — double-check the zip
didn't nest an extra folder level on extraction).

## 3. Install and verify

```
cd D:\MasterAgent
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
pytest                          # expect: 93 passed (see MIRACLE_LEDGER.md for the current count)
ruff check src tests            # expect: All checks passed
```

If both of those pass, the codebase is healthy on this machine.

## 4. Try the working demo

```
python -m master_agent.cli
```

Then type `Master Agent`, then `Create a folder called Demo on my
Desktop.`, then `Yes`. A real folder should appear on your Desktop. See
`docs/MISSION_BRIEF_001.md` for the full transcript and what's actually
real versus stubbed underneath it.

Or try the newer mission: type `Master Agent`, then `Create a Python
project called Demo.`, then `Yes` — a real project folder (README,
`.gitignore`, `requirements.txt`, `src/`, `tests/`, `docs/`, `config/`,
`main.py`) appears on your Desktop. See `docs/MISSION_BRIEF_003_1.md`
for the full transcript.

## 5. Layout, at a glance

```
D:\MasterAgent\
├── src/master_agent/   # the engine (see ARCHITECTURE.md for module map)
├── docs/                # ADRs, mission brief writeups, timeline risk
├── tests/                # 23 tests, run with pytest
├── plugins/              # external/installed plugins (empty — no marketplace yet)
├── models/                # local model weights (e.g. Hermes via Ollama) — gitignored
├── memory/                # runtime DB for local memory — gitignored
├── logs/, backups/, workspace/, releases/, config/   # runtime folders — gitignored
├── scripts/               # dev/ops scripts, not part of the shipped package
├── prompts/                # versioned prompt templates the engine uses
├── obsidian/               # founder vault — open as an Obsidian vault
├── PROJECT_BRAIN.md         # orientation index — read this first
├── ARCHITECTURE.md, ARCHITECTURE_PRINCIPLES.md, DECISIONS.md, docs/adr/  # system design + why
├── VISION.md, MANIFESTO.md, WHY.md   # mission/vision/values
├── ENGINEERING_PRINCIPLES.md, PRODUCT_PRINCIPLES.md   # how we build, how it should feel
├── FOUNDER_PLAYBOOK.md       # how a Miracle gets built, reviewed, shipped
├── MIRACLE_LEDGER.md         # dated history: every shipped Miracle, tag, commit, test count
├── ROADMAP.md               # what's next
└── FOUNDER_CONTEXT.md        # known constraints, target date, TBDs
```

## 6. Known gap as of this bootstrap (2026-07-23)

This repository was assembled and verified inside a Claude cloud session,
**not on `D:\MasterAgent` itself** — the session had no live connection to
this machine when it was built (the Claude desktop app's device bridge
wasn't open). Everything above was built, tested, committed, and tagged
in that cloud workspace, then delivered as a zip. If you're reading this
file from inside that zip, you're at the "step 2" point above — the
`.git` history is real and already inside the zip, so `git log` should
work immediately after extraction; there's no separate clone step needed.

Next time a Claude session has the desktop app connected, it can verify
this placement directly and skip the manual zip/unzip step entirely —
worth doing once, to confirm this file's instructions actually match
reality on this specific machine.

## 7. If something's inconsistent

Check `DECISIONS.md`'s dated entries for the most recent bootstrap/health
-check notes before assuming a gap is new — it may already be a known,
flagged issue with a reason attached.
