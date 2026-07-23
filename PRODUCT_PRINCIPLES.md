# Product Principles

The founding engineering principles, stated once here as the canonical
list — other docs (`ARCHITECTURE.md`, `MANIFESTO.md`) reference these
rather than restating them, so this file is the source of truth if they
ever seem to drift.

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
