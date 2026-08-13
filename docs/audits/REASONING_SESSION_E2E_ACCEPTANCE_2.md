# Clean Live E2E Acceptance After Restart — Report

**Final decision: FAIL on both applications.** The architecture is
**not** declared complete. No production code was changed. Both blockers
are demonstrably environment/application-state issues, not generic code
defects — evidenced below, not asserted.

## Summary

The machine was restarted before this mission began. Both ChatGPT Desktop
and Kimi Desktop were confirmed **not running** at the start (process
list checked directly — neither appeared). Both were freshly launched by
the real, unmodified production path
(`DesktopAppReasoningProvider.complete()` → `_launch_or_focus()`) for the
first time this mission, with no manual intervention.

Both applications, once launched, were found to be carrying **exactly
the same stale, unsent composer draft content that existed before the
restart** — proving the blocking pollution is not session-local (cleared
by restarting the machine or the app) but is persisted to disk by each
application itself (Electron's own local-storage/IndexedDB draft
persistence), independent of process or OS lifecycle. Two live attempts
per application were made (a first cold-launch attempt, then one retry
once each app had had time to fully render) — no more, per the mission's
own explicit anti-looping instruction.

## ChatGPT Desktop — result: FAIL

**Attempt 1** (immediately after cold launch, `elapsed=37.8s` including
the launch itself): `ISOLATION_UNVERIFIED: no generic 'start a new
conversation' control was found`. A read-only check immediately after
confirmed the real cause was **not** a code defect: the window's own UIA
tree, inspected directly, showed `'Switch mode, current mode: ChatGPT'`
(the app was correctly in ChatGPT/Chat mode, not Codex) and a genuine
`'New chat'` control did exist in the tree — the failure was a cold-launch
rendering-timing race, not a missing/broken mechanism.

**Attempt 2** (same, now-warm window, `elapsed=10.7s`): advanced past
control discovery — a `"New chat"` control was found and invoked — but
failed the freshness confirmation: `ISOLATION_UNVERIFIED: the surface
still shows 5961 characters of content after requesting a new session`.

**Root cause, confirmed by direct read-only inspection, not guessed**:
`find_main_content()` (and separately, `find_composer()`, which raised
`UiaTargetNotFound` entirely) both resolve to the same real UI element —
accessible name **`"Message ChatGPT"`**, the composer itself — currently
holding **6,075 characters** of stale draft text. That text is the exact
`"You are the Planner for an autonomous system..."` planning prompt from
the very first live-testing mission in this session's history, still
sitting there, unsent, verbatim. This composer's bounding rectangle is
`(469, 345)`–`(1070, 1626)` — **1,281px tall against a 1,626px-tall
window, roughly 79% of the window's height** — a composer that has grown
far beyond any reasonable "empty or lightly-drafted" shape because of
this much accumulated, never-cleared text.

This is the same *class* of issue an earlier mission found and partially
addressed for Claude Desktop (a composer that grows to accommodate real
content defeats a pure height-based "is this the composer" heuristic),
already widened once (`_COMPOSER_MAX_HEIGHT_FRACTION`: 0.30 → 0.40). This
instance is roughly double even that widened bound. **Widening the
threshold further was deliberately not done**: the composer's size here
is not a property of real founder usage, a real conversation, or the
application's own normal behavior — it is a direct artifact of this
specific development machine having had thousands of characters of test
prompts typed into this exact application across four prior missions
this session, none of which were ever actually sent, all of which
persisted to disk and survived both an application restart and a full
machine restart. Chasing this with an ever-larger magic-number threshold
would be tuning the Universal Desktop Executive to accommodate one
machine's accumulated test debris, not fixing a generic defect a real
founder would ever encounter on a normally-used machine.

## Kimi Desktop — result: FAIL

**Attempt 1** (immediately after cold launch, `elapsed=9.2s`):
`ISOLATION_UNVERIFIED: no generic 'start a new conversation' control was
found` — the identical cold-launch rendering-timing signature observed
for ChatGPT Desktop's first attempt.

**Attempt 2** (same, now-warm window, `elapsed=9.8s`): `ISOLATION_UNVERIFIED:
the composer still shows 92 characters of drafted content after
requesting a new session — not confirmed fresh`.

**Root cause, confirmed directly**: 92 characters is not a new, unrelated
number — it is the exact same figure, and the exact same content
(`"[Kalpavriksha Reasoning — Kimi Desktop test]Reply with exactly:
KALPAVRIKSHA_KIMI_DESKTOP_OK"`), documented as present in this same
composer at the end of the immediately-prior mission, *before* the
machine was restarted for this one. The full machine restart did not
clear it. This is the same mechanism as ChatGPT Desktop's, at a much
smaller scale: Kimi Desktop persists unsent composer drafts to disk, and
they survive both process and OS restarts.

## Is this a generic code defect or an environment/application-state issue?

**Environment/application-state issue, on direct evidence, not
assertion**:

- Both failures reproduce the *exact same content*, byte-for-byte, that
  was present *before* a full machine restart — content a restart cannot
  have regenerated. The only explanation consistent with that is
  persistence external to the running process (disk-backed local
  storage), which is normal, documented Electron/Chromium behavior for
  unsent draft text in a `contenteditable` field, not a bug in either
  application or in Kalpavriksha's own code.
- `ReasoningSessionManager.establish()`'s own new-session mechanism
  (Chat-section navigation, generic new-session control discovery,
  composer-based freshness confirmation) worked correctly in every
  attempt: it found the right mode, found and invoked the right control,
  and correctly, honestly refused once it could not confirm the result
  was actually fresh — precisely the fail-closed behavior this
  architecture exists to guarantee. Neither failure involved writing a
  prompt, pressing Enter, or invoking a Send control; both stopped at
  the isolation check, exactly as designed.
- The one candidate "generic fix" considered — widening
  `find_composer()`'s height-fraction ceiling further — was evaluated and
  rejected: the composer's current size (≈79% of window height) is a
  direct function of *how much accumulated test text this one
  installation has had typed into it*, not a property any generic
  threshold should be tuned around. A founder's real, normally-used
  installation would never accumulate a draft this large through actual
  use.

## Production changes this mission

**None.** Per the mission's own explicit preference ("zero production
changes" unless "a clean, reproducible, generic failure is discovered")
and its own stop condition ("do not modify the Universal Desktop
Executive unless the evidence proves the failure belongs there") — the
evidence above proves the opposite: both failures belong to accumulated,
machine-specific application state, not to a defect in the Executive, the
session manager, or the reasoning-provider layer.

## Tests

No new tests were added — no code changed. The full deterministic suite
from the immediately-prior mission remains valid and was not re-run in
full for this mission (no changes to invalidate it); its last confirmed
state was 851 passed, 4 failed (all four pre-existing and previously
documented by name in two prior missions' own reports).

## Architectural rules — confirmed intact

- No coding-agent session was used, reused, or typed into in any attempt
  — every attempt stopped at the isolation check before any write.
- ChatGPT Desktop's window was confirmed, by direct inspection, to be in
  `"ChatGPT"` mode, not `"Codex"` mode, at the time of the failure — the
  correct surface was selected; the failure is unrelated to mode
  selection.
- No app-specific selector, coordinate, or branch was added or
  considered.
- No clipboard-history mechanism was touched or investigated.
- The machine was not force-restarted or force-killed by this mission —
  it was already restarted before this mission began, per the mission
  brief's own premise.

## Final acceptance gate: FAIL

Neither application achieved the full required chain (discover → Chat →
new isolated session → empty composer → write → verified prompt → submit
→ verified submission → real response → verified response). Both stopped
at "new isolated session → empty composer" — the isolation-verification
step correctly refused to proceed past accumulated, disk-persisted draft
pollution in both cases.

**The reasoning-provider integration is not frozen.** Per the mission's
own instruction ("if either FAILS: do not declare the architecture
complete... return with evidence before changing anything"), this report
is that return with evidence — no further code changes were made in
pursuit of a live PASS this mission.

## Recommended next step

This blocker is external to anything this session can safely resolve on
its own: a genuinely clean live test of this specific mechanism requires
either the founder's own action (manually starting a new chat and
clearing the stuck draft through each application's own UI — a
seconds-long, low-risk action this session is not positioned to take
unilaterally without risking a real founder's own data) or a machine/user
profile where these two specific applications have never had automated
test content typed into them. Repeating this exact live-acceptance
mission a further time against these same two installations would not
produce new information — it would reproduce this same, now
twice-confirmed, disk-persisted state a third time.

Not committed, per instruction.
