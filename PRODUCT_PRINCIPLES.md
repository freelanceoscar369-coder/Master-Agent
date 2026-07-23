# Product Principles

Status: Frozen (2026-07-23) — Miracle 003.5, Foundation Freeze

Two things live in this file, kept distinct:

1. **Product philosophy** — how the product should *feel*, independent
   of implementation. This is the newer section below and the one to
   read first; it's what a design or UX decision should be checked
   against.
2. **The founding engineering principles list** — kept here as the
   canonical, concise reference other docs (`ARCHITECTURE.md`,
   `MANIFESTO.md`, `PROJECT_BRAIN.md`) already point to, so their
   cross-references don't break. `ENGINEERING_PRINCIPLES.md` is now the
   fuller treatment of the same list — each principle there is backed by
   the real bug, ADR, or decision that produced it. Read this file's
   list for the "what," that one for the "why, with evidence."

## Product philosophy

What the product should feel like using, stated as a short list of
commitments — not features, not a roadmap.

- **Results over prompts.** The user states an outcome; they should
  never have to think in terms of "the right prompt" to get it. This is
  "Intent over prompts" (below) read from the user's side of the screen
  rather than the engineer's — the Intent Layer's whole job is absorbing
  that translation so the user doesn't have to.
- **One conversation.** A mission doesn't require the user to context-
  switch between a chat window, a terminal, and a file explorer to see
  what happened. Everything from "here's what I want" to "here's proof
  it's done" happens in one continuous exchange — Mission Brief 001's
  transcript through Mission Brief 003.1's is the same conversational
  surface, extended, never replaced by a second interface.
- **One workspace.** The user has one place their intentions turn into
  outcomes, not a different tool per capability. `workspace_bootstrap`
  (Miracle 003) exists specifically so "set up a new project" is one
  request, not a folder here, a README there, a `.gitignore` remembered
  separately.
- **One assistant.** Multiple models and providers may work underneath
  (the Model Router, `ARCHITECTURE.md` §5), but the user relates to one
  consistent assistant, not a router they have to reason about. If a
  user ever needs to know *which* model handled their request to trust
  the result, the abstraction has leaked.
- **Privacy first.** Sensitive context defaults to staying local (the
  Model Router's routing policy, `ARCHITECTURE.md` §5) — the user should
  never have to remember to ask for privacy; they should have to
  deliberately opt out of it.
- **Local-first.** The product works fully offline. Not "works offline
  in a degraded mode" — every capability shipped so far
  (`create_folder`, `write_file`, `workspace_bootstrap`) has zero network
  dependency, by construction, not as a fallback path.
- **Permission before action.** Every consequential action gets exactly
  one clear, specific approval request — never a generic "allow this
  action?" dialog, never silent execution, never repeated nagging for
  things already approved within the same mission. See
  `ENGINEERING_PRINCIPLES.md` #2 and #5 for how this is kept true as the
  system grows more capable.
- **Trust through transparency.** The user can always see what was
  planned, what was approved, and what actually happened — a mission's
  plan is shown before approval, its outcome is reported honestly
  (including failures — `"Something went wrong: {error}"` is a real
  message, not swallowed), and nothing is marked "done" without a
  verification step (`MANIFESTO.md`'s "outcomes, not outputs"). Trust is
  built from a visible track record, not from asking the user to have
  faith.

## Founding engineering principles

- **Intent over prompts.** Capture a structured `Intent` (goal,
  constraints, context, success criteria) — not a raw prompt string
  handed straight to a model. See `planner/planner.py`'s `Intent`
  dataclass and `ARCHITECTURE.md` §4.1.
- **Outcome over output.** A Mission isn't done because a model produced
  plausible text; it's done because a Verifier confirmed the real-world
  state matches what was asked for. See the `verifying` state in the
  Mission state machine.
- **Everything is a plugin.** Model providers, capabilities, voice
  adapters — all behind one `Plugin` contract and the registry. See
  `docs/adr/0003-plugin-first-boundary.md`.
- **Human approval before important actions.** No plugin executes
  anything above `read_only` risk without a Permission System grant. See
  `permissions/permission_system.py` and Mission Brief 001's approval
  prompt, which is the first real instance of this principle actually
  gating something.
- **Local-first architecture.** The system must be fully functional
  offline against a local model and local memory.
- **Cloud enhancement when beneficial.** Cloud providers (ChatGPT) are an
  opt-in the Model Router reaches for, never a hard dependency. See
  `docs/adr/0002-hermes-local-llm.md` and `ARCHITECTURE.md` §5.
- **Replaceable modules.** Every module is swappable behind its interface
  without touching the others — this is what makes "build for one founder
  first, scale for millions later" possible without a rewrite.
- **Maintainable code over clever code.** Mission Brief 001's own
  retrospective (`docs/MISSION_BRIEF_001.md`) is evidence this matters in
  practice: the two bugs it found were in code that looked "done" but
  hadn't been exercised end to end. Prefer code a stranger can verify over
  code that's merely compact.
- **Build for one founder first, scale for millions later.** Don't add
  infrastructure (a plugin marketplace, multi-device sync, a message
  queue) before there's a concrete reason a single founder's workflow
  needs it. `docs/adr/0004-local-first-memory.md` is a direct application
  of this — no sync layer until it's actually needed.

## From the Manifesto (product-facing, not just engineering)

- Every feature must save time.
- Every interaction must reduce confusion.
- Every mission should move the user closer to success.

See `MANIFESTO.md` for the full text and how it maps onto the
architecture, including a named tension between "reduce confusion" and
"require approval" that the Permission System's UX has to resolve, not
avoid.
