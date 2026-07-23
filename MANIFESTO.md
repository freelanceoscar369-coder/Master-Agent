# Master Agent Manifesto

We believe technology should reduce complexity, not create it.
We believe people should express intentions instead of managing software.
We believe AI should work together so humans can focus on creating value.

Our mission is to empower every individual by transforming intention into
intelligent execution.

We optimize for outcomes, not outputs.
We optimize for people, not technology.

Every feature must save time.
Every interaction must reduce confusion.
Every mission should move the user closer to success.

---

## How this maps to the architecture

These aren't just values — they're testable constraints on the design in
`ARCHITECTURE.md`. Cross-references so future work can be checked against
them directly:

- **"AI should work together"** → the Model Router + Plugin contract
  (`docs/adr/0003-plugin-first-boundary.md`) exist specifically so
  multiple models/capabilities cooperate behind one interface rather than
  the user manually switching between ChatGPT, Hermes, and other tools
  themselves.
- **"Outcomes, not outputs"** → this is why the Mission state machine has
  a `verifying` state before `completed` (`ARCHITECTURE.md` §4.3). A
  model producing a plausible-looking response is not the same as the
  Verifier confirming the real-world state matches the Intent's success
  criteria. Nothing should be able to mark a mission complete without
  going through Verify.
- **"Every mission should move the user closer to success"** → argues
  against ever letting a mission end in an ambiguous or silent state.
  `failed` and `cancelled` need to report *why*, not just stop — the
  Reporter step isn't optional cleanup, it's part of the definition of
  done.

## A tension worth naming, not hiding

"Every interaction must reduce confusion" and "human approval before
important actions" (a founding engineering principle) pull against each
other by default — an approval prompt is an interruption, and a poorly
designed one is exactly the kind of confusion the manifesto rules out.

This isn't a reason to weaken the Permission System. It's a design
requirement on it: an approval request must be a single, clear,
voice-summarizable question with an obvious safe default — never a
generic "allow this action?" dialog. Mission Brief 001's approval prompt
("Action / Location / This action will modify your filesystem / Approve?
(Yes/No)") is the first working instance of that requirement — it's a
pattern to preserve, not something to improve away for the sake of
brevity.

*(This file mirrors the copy saved to the Claude Project. If they ever
diverge, the Project copy has commentary added after later conversations —
treat this file as the source of record for the repo itself.)*
