# Open findings — recorded, not chased

Two behaviours were observed during the semantic strike that are real and
are **not** in scope tonight. They are written down here so they survive
the session, and deliberately left unfixed so that a semantic acceptance
is not diluted into a general bug hunt.

Neither is a fuzzy-matching problem, and neither is to be answered with a
regex.

---

## FINDING 1 — Browser policy: a 5s Navigate timeout is a policy, not a failure

**Observed:** navigating to Steam timed out after 5 seconds and the
mission reported failure.

**Why this is a policy finding.** 5 seconds is a *fixed budget applied to
every destination*. It is the right budget for a local page and the wrong
one for a heavy commercial site on a cold connection; the site did not
misbehave and the worker did not malfunction. What is missing is a
decision about what the timeout *means* — who owns it, whether it varies
by destination class, and whether exceeding it should fail the mission or
report a slow load with the page still arriving.

**Why not to "fix" it now.** Raising the number would make the symptom go
away and leave the policy question unanswered, which is how a constant
becomes load-bearing without anyone choosing it. This belongs with MB022
(Browser Worker) as a deliberate contract, not as a tuned literal.

**Not:** a retry loop, a longer default picked to pass a demo.

---

## FINDING 2 — Language robustness: `ctreate` is a typo, and typos are input

**Observed:** `ctreate a folder` was not recognised.

**Why this is a robustness finding.** The founder typed a real word
wrong. The system's job is to understand what a person meant, and a
transposed pair of letters is one of the most ordinary things a person
does. That is a genuine gap in understanding, sitting in the same family
as everything else this strike was about.

**Why not to "fix" it now, and especially not tonight.** The obvious
patch is fuzzy matching on capability trigger phrases, and that is the
approach the founder has already rejected once, correctly. Edit-distance
matching against a pattern table makes the parser *more* willing to claim
a sentence it does not understand — the exact direction that produced
`D:\Rudra` — and it fails in the unsafe direction: silently confident.

A typo is a reason to be **less** certain, not more. Whatever answers
this must route uncertainty toward a question, not toward a nearest
match, and that design belongs beside the intent work rather than bolted
onto the pattern list at the end of a session.

**Not:** `difflib` over `self._patterns`, a spelling-correction pass, a
synonym table.

---

## Status

Both are recorded as findings against the current build. Neither blocks
the semantic acceptance, because neither is what the acceptance is
asking about: one folder, understood correctly, verified independently,
and reported honestly.
