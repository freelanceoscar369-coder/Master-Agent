# Master Agent — Founder Vault

An Obsidian vault for founder-facing thinking: journal, research, meeting
notes, roadmap scratch space — everything too unstructured or in-flux for
the versioned docs at the repo root.

Open this folder directly as a vault in Obsidian (`File → Open folder as
vault`). No plugins or special config are assumed; Obsidian will create
its own `.obsidian/` settings folder on first open — that folder is
machine/preference-specific and is gitignored (see the repo's
`.gitignore`) so your Obsidian settings don't collide with anyone else's
if this is ever shared.

## Relationship to the versioned docs

This vault is for thinking *in progress*. The repo-root docs
(`PROJECT_BRAIN.md`, `ROADMAP.md`, `DECISIONS.md`, `ARCHITECTURE.md`,
`docs/adr/`) are the settled, versioned record. When something in here
becomes a real decision or a shipped feature, reflect it back into the
appropriate root doc — don't let the vault become a second, conflicting
source of truth. Several folders below say explicitly which root doc they
feed.

## Folders

- `00 Inbox` — unsorted capture, triage weekly
- `01 Vision` — long-term direction (working version of `WHY.md`)
- `02 Product` — feature specs, user flows, in-flux product decisions
- `03 Architecture` — exploration that hasn't (or won't) reach `ARCHITECTURE.md`
- `04 Decisions` — reasoning behind entries in `DECISIONS.md`
- `05 Research` — competitive/technical research and spikes
- `06 Founder Journal` — dated, personal, unstructured
- `07 Weekly Reviews` — one structured retro per week
- `08 Meetings` — one note per meeting, dated
- `09 Parking Lot` — good ideas, deliberately deferred
- `10 Roadmap` — scratch space behind `ROADMAP.md`
- `11 Releases` — human-readable release notes (artifacts live in `releases/`)
- `12 Ideas` — raw capture, pre-triage
- `13 Users` — feedback, interviews, personas
- `14 AI Prompts` — founder-facing prompt notes (engine prompts live in `prompts/`)
- `15 Plugins` — plugin ideas before they're real code
