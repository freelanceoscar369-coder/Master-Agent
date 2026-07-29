# Mission Brief 029 — Founder Dashboard V2 (Founder Experience)

Status: **Shipped** — 2026-07-29

Pure UX. **No ADR**, because no architecture changed — see §1.

## Objective

The dashboard was technically correct and cognitively expensive. It showed
what the system *is*; a founder needs to know what it is *doing*, whether
it needs them, and what to do next.

## 1. The rule, verified rather than asserted

MB029 forbids changes to the Runtime, Mission Control, Persistence, and
the Approval Queue.

```
$ git diff --name-only v0.10.4-miracle-028-1 -- \
    src/master_agent/runtime src/master_agent/mission_control \
    src/master_agent/persistence
(empty)
```

Everything MB029 touched is in `dashboard/` and `launcher/`: three new
modules, two edited, and the console. The Dashboard stays read-only; the
Console stays the only thing that acts. **No ADR was needed and none was
written** — the brief's own condition.

## 2. The layering, which is also Deliverable 10

```
contracts → sources.py → DashboardSnapshot → founder.py → FounderView → renderer
            (reads)      (read model)        (derive)     (view model)   (any UI)
```

ADR-0016 gave this project a read model. MB029 adds the layer above it: a
**view model** — what a founder should be *shown*, as plain data, with no
notion of a terminal anywhere in it.

That is the whole of "make it trivial to swap Console → Web → Desktop →
Mobile without changing Mission Control". A web front-end imports
`build_founder_view` and `as_dict`, writes its own rendering, and touches
nothing else. `founder_panels.py` is one renderer, not the interface.

Everything in `founder.py` is a **pure function of the snapshot**, so the
same snapshot renders identically in a browser and a terminal — asserted
by `test_the_view_is_a_pure_function_of_the_snapshot`.

## 3. Two pages, one snapshot

| Page | Shows | Default |
|---|---|---|
| **Founder** | status, decisions, mission, work, executives, self-development, recommendations | yes |
| **Technical** | MB026's nine engineering panels, **unchanged** | `[V]` |

MB029 *moves* engineering detail; it does not delete it. Snapshot
versions, event-log sizes, audit counts, cycle numbers, and queue lengths
are all still there, one keystroke away.

The founder page is default because a founder who must switch pages to
find out whether the system needs them has been shown the wrong thing.

## 4. Where the numbers come from

This is the part worth reading, because three deliverables asked for
things that are not measured, and inventing them would have been exactly
the fabrication ADR-0016 forbids.

| Asked for | What it does |
|---|---|
| **Confidence** (D4) | A *reading of the verification record*, with the basis stated: `High` (verified steps, no failures), `Low` (failures present), `Unverified` (completed but no evidence), or **absent** when nothing has completed. Never a prediction. |
| **Self-development bars** (D6) | **Transcribed from `ROADMAP.md` and `MIRACLE_LEDGER.md`**, in `dashboard/roadmap.py`, where every phase records what its number is a reading of. Declared, never computed — a bar derived from a heuristic would look like measurement. |
| **Recommendations** (D8) | Roadmap items, *filtered by live state* — a recommendation for an Executive that already exists is noise a founder learns to scroll past. |
| **Executive readiness** (D5) | The roadmap says what should exist; the registry says what does. `Ready` is never a claim the roadmap file makes. |
| **Time saved** (D9) | **Reported as not measured.** Nothing in Kalpavriksha records what a task would have cost a human. A founder would read an invented figure as fact. |

`Missing` and `Planned` are deliberately different words: one means
something is wrong, the other means something is unfinished.

## 5. Status, in one human sentence (D3)

`Working normally` / `Waiting on you` / `Needs attention`, each with a
reason and no subsystem names.

Order matters: **waiting-on-you outranks needs-attention**, because a
founder being asked something should be told *that* first. The system is
not broken, it is blocked on them, and those feel very different at 22:13.

## 6. What it looks like

```
==============================================================
                         KALPAVRIKSHA
==============================================================

STATUS
  ! Needs attention
    Browser Executive missing

FOUNDER DECISIONS
  + none pending

CURRENT MISSION
  nothing in flight

TODAY'S WORK
  + 0 completed
  ~ 0 running

EXECUTIVES
  + Filesystem   Ready
  x Browser      Missing
  - Desktop      Planned
  - AI Broker    Planned
  - Reasoning    Planned

SELF DEVELOPMENT
  Architecture    ########.. 80%
  Implementation  ######.... 60%
  Testing         ########## 100%
  Documentation   ########.. 80%

RECOMMENDATIONS
  1. Implement the AI Capability Broker
  2. Build the real Planner (replace cli.py's regex stand-in)
  3. Build the Desktop Executive
  4. Ratify or reject ADR-0015 and ADR-0020

NEXT RECOMMENDED STEP
  Implement the AI Capability Broker
==============================================================
```

Captured from a real `kalpavriksha` run on a cp1252 Windows console —
which is why the glyphs are `+ x - #` rather than `✓ ✗ — █`. The charset
is chosen by **asking the stream what it can encode**, so a UTF-8
terminal gets the nicer set. MB026 learned this the hard way and MB027.5
re-learned it; MB029's mock-up uses check marks and block bars, so it
would have happened a third time.

`Browser: Missing` is honest, not a bug: the launcher wires only the
Filesystem Executive, because MB024's browser gateway still lives in test
support (a standing roadmap item). The dashboard is the first thing that
says so out loud.

## 7. Console additions

`[V]` toggles pages. `y N` / `n N` approve and reject, matching the
`[Y]/[N]` the panel prints — MB028.1's `approve N` / `reject N` still
work, because a founder should not have to remember which screen they
are on.

## 8. Daily summary at shutdown (D9)

Captured **before** `stop()`, so it describes the day rather than the
moment after it ended:

```
  Tasks completed    31
  Failures           1
  Recovered          1
  Decisions made     3
  Ran for            2.0h

  Learning           Architecture 80%, Implementation 60%, Testing 100%, ...
  Time saved         not measured - Kalpavriksha records what it did, not
                     what it would have cost you

  TOMORROW
  Implement the AI Capability Broker
```

## 9. Verification

**76 new tests** (the brief asked for 40), **1138 passing, 1 skipped, zero
regressions** (1051 before). Ruff clean across every file touched.

Beyond the brief's list, three worth naming:

- **Zero engineering leakage** is a parameterised test over thirteen
  banned terms — `snapshot version`, `event log size`, `audit entries`,
  `active cycle`, `queue length`, `objective_id`, and so on — plus one
  asserting no raw identifier appears.
- **Panel ordering** is asserted by string position, so a future edit
  that pushes decisions below the mission fails.
- **Frame length ≤ 60 lines.** Five seconds is a length claim as much as
  a content one; past one terminal, a founder scrolls, which is where the
  old dashboard lost them.

Three MB028.1 tests were updated rather than deleted: they asserted the
technical page's approval panel, which still exists — they now check both
pages.

## 10. Technical Debt and Known Limitations (Rule 10)

1. **The roadmap tables are transcriptions and will drift.** Every entry
   names its source, and a test asserts each phase states its basis — but
   nothing checks them against `ROADMAP.md`, because parsing prose into
   percentages would be inventing the number again. They need updating
   when the roadmap moves.
2. **"Today's Work" is since-launch, not since-midnight.** The counts come
   from the current objective set; there is no daily boundary, because
   nothing persists one.
3. **Confidence is coarse** — three buckets from the verification record.
   It is honest about its basis, but it is not a probability.
4. **No approval history on the founder page.** The ledger is durable;
   nothing renders it (carried from MB028.1).
5. **The technical page is unchanged, including its known costs** — the
   O(log) event-count read ADR-0016 named is still there.
6. **`render_founder_frame` takes a `footer` parameter the console does
   not use**, since the console composes its own prompt. Harmless, but it
   is a seam with one caller and no second use yet.
