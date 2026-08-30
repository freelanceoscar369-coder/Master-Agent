# Codex demo-convergence holdout

This is the frozen adversarial holdout for the 30 August 2026 demo-convergence
mission. `cases.json` was written before the current-source run and before any
production repair in this mission.

Rules:

- The Founder wording in `cases.json` is immutable for this convergence run.
- A runner may substitute only tokens explicitly listed in `variables` (unique
  test names, a loopback fixture URL, and a fixture-generated value).
- Expected outcomes may be clarified by adding evidence to the convergence
  ledger, but a case may not be weakened, deleted, or rewritten after it fails.
- An action result is not a pass. The runner must inspect fresh external state,
  mission Evidence, Founder-facing reporting, and outcome conformance.
- Pre-existing-artifact cases require a precondition observation and proof that
  the requested target—not a similar target—was affected.
- Cases that require a provider must record eligible and rejected candidates,
  the winner, requester, economic/locality reason, and any fallback.
- No case may use Ollama, authenticated Founder browser state, paid capacity
  without the existing approval path, or consequential external actions.

The holdout is intentionally separate from the rehearsed golden paths and from
unit-test phrases. Repair validation may add focused tests, but production code
must not contain these sentences as a phrase table.
