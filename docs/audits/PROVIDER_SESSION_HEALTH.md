# Provider session health — the Kimi saturation P0

**Date:** 29 August 2026
**Branch:** `claude/brain-wisdom`
**Owner extended:** `src/master_agent/providers/reasoning_session.py`
**Status:** mechanism in and unit-proven; two live checks NOT YET provable
on this estate, stated below rather than assumed.

---

## 1. The founder's observation

Kimi Desktop was displaying

```
Your conversation with Kimi is getting too long.
Try starting a new session.
```

while Kalpavriksha kept sending reasoning requests into that same
conversation.

## 2. What it actually was

Not model answer content. Not a Planner failure, a deliberation failure,
or a mission-recovery failure.

```
PROVIDER HEALTH          is Kimi installed, launchable, answering
PROVIDER SESSION HEALTH  is THIS conversation still fit to use
```

Only the second was wrong. That distinction is load-bearing: it is why
nothing in this change excludes Kimi as a provider, and why a spent
conversation is retired rather than the application being downgraded.

The consequence was worse than a bad answer. Fixtures D, D2 and E were
failing, and the failures were being read as **intelligence variance** —
evidence about the Brain — when the transport underneath them was
returning nothing usable.

## 3. Why the existing owner was extended and no new one built

`ReasoningSessionManager` already knew which conversation is active, how
to create one, how to find the existing named one, and how to read the
composer. Every question session health asks was already its business.
It gained methods; there is no second Kimi session manager, no provider
health registry, and no new automation layer.

| Question | Answered by |
|---|---|
| is this conversation spent? | `ReasoningSessionManager.inspect_session()` |
| must it not be used again? | `ReasoningSessionManager.retire()` |
| open one, or replace one? | `ReasoningSessionManager.establish()` |
| exclude this provider for this attempt? | `TieredPromptRunner` (unchanged) |

## 4. The rules that hold

**Pre-flight before every request.** `establish()` gets a conversation and
then asks whether it is fit to use, before a character is written.

**A saturated conversation is never written into.** It is retired, and a
replacement is established.

**Exactly one governed rotation.** If the replacement cannot be proven
healthy either, the provider fails closed for this attempt and the ladder
asks the next one. Nothing clicks "New chat" in a loop.

**A rotation does not rename its replacement.** The retired conversation
may still hold `Kalpavriksha Reasoning`; giving the replacement the same
name would make `find_named_session()`'s exact match ambiguous — the one
failure that rule exists to prevent. The marker in the first message
still identifies it, the strategy `app_knowledge.catalog` already records
for these applications.

**Retirement is in-process, and self-correcting across processes.** A
later process finds the same saturated conversation once, observes the
same warning, and rotates again. One wasted click, and no need to teach
this manager to rename or delete conversations in the founder's window.

**A valid answer survives the warning.** The warning can be caused by the
very turn that just succeeded. The answer stands; the conversation is
retired so the NEXT call rotates.

**An unreadable window claims nothing.** `observed=False` is not ill
health. The write/submit/read path verifies each of its own steps.

**A stale attachment blocks the send on its own.** A clean text composer
is not an isolated session — the founder saw a previous prompt survive as
an attachment. Only *removal* controls count as evidence, because an
"Attach file" button exists permanently and a "Remove attachment" control
exists only when there is something to remove.

**Two length constraints, never conflated.**

```
SESSION TOO LONG       ->  rotate the conversation
THIS PROMPT TOO LONG   ->  provider failure, ladder falls through
```

`ProviderSpec.max_prompt_chars` (kimi-desktop: 4000, from the founder's
own live observation) is checked *before* discovery, launch or focus.
Nothing truncates. A shortened prompt is a different question answered
confidently, which is worse than no answer — `tests/test_provider_session_saturation.py`
asserts against the executable source that no slice of a prompt is taken
anywhere on the send path.

## 5. What the live run found that was not asked for

Asked to reply with one nonce token, Kimi returned `SUCCEEDED` carrying:

```
Copy
Share
Create or select a file to start
Your chats will appear here
Update
Instant
High
AI-generated, for reference only
```

Not our prompt handed back, so the echo guard did not fire. Not a service
notice, so that guard did not fire. Eight lines of a window describing
itself, propagating as a reasoning result.

This exact knowledge already existed — in
`scripts/live_acceptance/p0_3_complete_response.py`, where a hand-written
judge rejected the same eight lines. **A guard that lives only in an
acceptance script protects the acceptance run and nothing else.** It now
lives in `desktop_app.py` beside the guards that refuse the other fake
successes, and the script imports it. One owner.

Session state now also travels on failure results. The first live run
could not say whether a fresh conversation had been created, because the
run ended in a provider failure and the failure carried nothing about the
session — a diagnosis is most needed exactly when something went wrong.

## 6. Live acceptance — `scripts/live_acceptance/kimi_session_health.py`

Against the real installed Kimi Desktop, this estate, 29 Aug 2026:

```
KIMI SATURATION WARNING DETECTED             NOT YET
REPLACEMENT CONVERSATION CREATED             PASS
REPLACEMENT OBSERVED CLEAN                   PASS
OLD SESSION RETIRED                          PASS
NEW SESSION CREATED                          NOT YET
NEW SESSION CLEAN                            PASS
STALE ATTACHMENT ABSENT                      PASS
SHORT PROMPT CURRENT-TURN OWNERSHIP          NOT YET
TWO-TURN ISOLATION                           NOT YET
SATURATED SESSION MARKED NON-REUSABLE        NOT YET
4000-CHAR CURRENT-PROMPT LIMIT               PASS
SATURATED SESSION REUSED                     NO
```

Zero FAIL. Each `NOT YET` is a question this estate could not put, not a
verdict:

- **SATURATION WARNING / SESSION MARKED NON-REUSABLE** — no conversation
  in Kimi is currently saturated. Detection is proven against the
  founder's verbatim two-line text in
  `tests/test_provider_session_saturation.py`, including that the advice
  half alone ("Try starting a new session") is *not* a warning, since
  that is what the New-chat button says.
- **NEW SESSION CREATED** — the conversation as found was healthy and was
  correctly reused. Demanding a rotation here would report the right
  behaviour as a failure.
- **SHORT PROMPT OWNERSHIP / TWO-TURN ISOLATION** — Kimi is currently
  returning `High demand. Switched to K2.6 Instant for speed. Upgrade to
  use K2.6 Thinking.` to every request. That is a genuine service notice,
  correctly classified `UNAVAILABLE`, and the ladder falls through. A
  provider that never answered says nothing about whether its session was
  isolated, so recording those as FAIL would be reporting a question
  nobody got to ask.

The half of a rotation that touches the real application — creating a
replacement conversation and observing it clean through the real UIA
path — is run on its own rather than left as an untested branch, and
passes live.

`session_reused: True` in the live run is itself worth recording: a
`Kalpavriksha Reasoning` conversation **was** found and reused in Kimi,
which is precisely how the founder's saturated conversation accumulated.
The mechanism the founder observed is real and reproducible in principle;
it simply is not saturated today.

## 7. Fixture variance, re-judged on a clean estate

Per the brief, D/D2/E were not re-judged until transport health was
established. On the re-run:

```
D  two independent sources, neither sufficient alone   PASS
E  a failed source does not end the objective          PASS
F  provider fallback on a service notice               PASS
G  privacy asymmetry                                   PASS
I  unanswerable research stops truthfully              PASS
```

D2 exposed two further defects, both unrelated to Kimi and recorded in
`docs/audits/BRAIN_WISDOM_CONVERGENCE.md`: the Planner was being handed
`still unresolved: crit_2` — an internal identifier — and asked to go and
settle it; and a page's links never became Evidence, so a mission holding
the answer's address could only re-read the page it had already read.
With both closed:

```
D2  more_research is consumed, and acquires what is missing   PASS

DIVERSIFIED BATTERY: PASS
```

A third defect surfaced during that work and belongs here, because it is
the same class as everything else on this page — a step that was allowed
to fail loudly when its own contract said it should fail quietly.
`SetFocus()` on an inline rename field that had already closed raised
`_ctypes.COMError` out of `_rename_current_session`, whose docstring
promises "never raises", and killed the mission. Losing a rename costs
reuse on a future call; losing the mission costs the founder the work.
