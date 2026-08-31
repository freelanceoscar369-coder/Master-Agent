# Computer-Use Intelligence Benchmark: ChatGPT Project Reorganization

Date: 2026-08-31

## Founder objective

Reorganize the Founder-authenticated `Kalpavriksh` ChatGPT Project into eight
working conversations: one preserved historical Research Command Center and
seven scoped department conversations. Use the prepared Library state, avoid
duplicating the complete historical Research conversation, and leave unrelated
Founder content unchanged.

## Previous failed attempt reconstructed

- Original intent: preserve the existing Research conversation as the command
  center and create seven department conversations inside `Kalpavriksh`.
- Attempted route: a remote browser session plus Google OAuth, after loading the
  prepared Personal Context/Library materials.
- First failed boundary: the Google OAuth redirect returned `502 Bad Gateway` in
  the remote browser, so the authenticated project could not be reached.
- Previous external effect: none. The failed conversation explicitly reported
  that no chats were created or modified.

## Successful authenticated route

- Environment: the already-running Founder-owned Comet window titled
  `ChatGPT - Kalpavriksh - Comet`.
- Mechanism: legitimate Windows computer control against that exact returned
  Comet window.
- Playwright: not used.
- Credentials/cookies/profile data: not read, copied, exported, or changed.

## Observed starting state

- The project already contained ten historical/other conversations.
- `Research department` was the current historical Research/command-center
  conversation.
- None of the seven required department conversations existed.
- Project Sources was empty.
- Library path `Kalpavriksh/Research Department` contained folders `01` through
  `07`; the inspected `01` folder contained `README.md` and
  `DEPARTMENT_STATE.md`. The root also exposed the shared cross-department
  communication material.

## Interaction trace

1. Selected the single returned Comet window and observed the project before
   changing it.
2. Opened `Reorganize Kalpavriksh Chats` and recovered the previous attempt's
   prompt, actions, and terminal OAuth/502 boundary.
3. Inspected Project Sources and the prepared Library hierarchy.
4. Preserved and renamed `Research department` to
   `00 Research Command Center`.
5. Created only the seven missing department conversations, each with a scoped
   prompt directing it to its own Library folder's `README.md` and
   `DEPARTMENT_STATE.md`, plus `CROSS_DEPARTMENT_COMMUNICATION.md` for handoffs.
6. Renamed every created conversation to the exact required title.
7. Reopened every department conversation. Each response demonstrated use of
   its own department state and the shared communication protocol, and stated
   that it would retain singular departmental ownership.
8. Left all nine other historical/other project conversations unchanged.

## Verified final working set

- `00 Research Command Center`
- `01 Product & Architecture Intelligence`
- `02 Market & Competition Intelligence`
- `03 Investment & Fundraising`
- `04 Infrastructure, Credits & Partnerships`
- `05 Product Evidence & Metrics`
- `06 External Alpha & User Validation`
- `07 Product Positioning & Go-To-Market`

## Outcome facts

- Working conversation count: 8.
- Total project conversation count: 17 (the working set plus nine untouched
  historical/other conversations).
- Department conversations created: 7.
- Conversations renamed: 8 (the preserved command center plus seven
  departments).
- Duplicate department conversations: 0 observed.
- Full historical Research conversation duplicated: no.
- Unrelated Founder data modified: no observed modification.
- Founder intervention: 0 during the successful run.
- False completion: no; titles, project membership, and initialized responses
  were independently reopened and observed.

## Computer-use intelligence lessons

- Authenticated-environment selection was the decisive strategy change: the
  failed remote OAuth route was not retried; the existing trusted Comet session
  was selected from live windows.
- Fresh UI state outranked cached labels. Automatic ChatGPT titles were allowed
  to settle, then were normalized through the live row controls.
- Existing resources were inventoried before creation, preventing duplicate
  command centers or departments.
- Verification inspected resulting conversation content, not just successful
  click/send returns.
- A momentary user-input interlock invalidated the pending click; the window was
  reobserved before continuing, with no blind retry against stale coordinates.
