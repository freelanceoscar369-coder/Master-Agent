# UI/UX Asset Inventory — V1 / V2 / VEDA Reconciliation Map

**14 August 2026 · Read-only survey of `VEDRA_PROJECT/01_Assets/UI-UX/`**
**Nothing in the asset area was modified, renamed, deleted, or reorganized.**

Purpose: give HyperAgent (and whoever reconciles V1/V2/VEDA) a complete,
verified map of what exists, what it contains, how the pieces relate, and
where duplicates or superseded artifacts would otherwise cause confusion —
so reconciliation starts from evidence, not from re-discovery.

**Method.** Every zip was listed (never extracted into place); apparent
duplicates were verified byte-for-byte (`diff`/`md5sum`), not assumed from
filenames; every markdown document's actual content was read, not just its
title. File modification timestamps in this asset area are **not reliable**
for dating — most files show `2026-08-14 06:29`, apparently reset by
unrelated tooling that touched the directory, contradicted by content dates
recorded inside the files themselves (used instead, and stated per item
below where it matters).

---

## 0 · The one-paragraph map

Two independent design lineages exist. **Lineage A (V1)** is a one-day
(3 August) HyperAgent output: an Experience Bible + Design Constitution +
four React/Vite prototype apps, richly documented, self-ranked by its own
manifest, but never connected to a real backend. **Lineage B (V2 / VEDA)**
begins 6 August: Product Veda v1.0 (the visual spec that explicitly
supersedes six V1 decisions), followed by a sequence of TypeScript
reference packages (`presence` → `surface` → `founder-edition`) that
HyperAgent built and validated in an isolated workspace with no git and no
access to the shipped app, culminating in two **independently-produced**
attempts to hand that logic to the real `desktop_app/web/` tree UI —
`kalpavriksha-ui-integration-audit.zip` (integrated by Claude; see
§5) and `kalpavriksha-UI-SOURCE-OF-TRUTH.zip` (never integrated; see §6).
**Those two do not know about each other and disagree on method** — that
is the single most important reconciliation item in this inventory.

---

## 1 · Authority hierarchy, as the artifacts themselves declare it

The V1 archive carries its own explicit ranking
(`00_ARCHIVE_MANIFEST.md`, full text in §2). VEDA's own index document
(`11_PRODUCT_VEDA.md`) states its relationship to V1 explicitly:

> "Derived from: the approved UI prototype · the accepted Design
> Constitution and Experience Bible (with the six supersessions above) ·
> C20 Presence · C21 Founder Conversation · the C24 integration."

**On the Experience Bible → VEDA question specifically** (the terminology
note in the request): these are **not** a simple rename. Read side by
side:

- `THE_KALPAVRIKSHA_EXPERIENCE_BIBLE_v1.0.md` (679 lines) is a broad,
  numbered-section constitution — vision, founder psychology, product
  philosophy, and the Interaction/Design/Motion/Voice/Autonomy/Demo
  "constitutions."
- `11_PRODUCT_VEDA.md` (139 lines) is a short **index** into ten separate
  visual-spec files (`00_TOKENS.md` … `09_NOTIFICATION_SYSTEM.md`) plus a
  **recorded table of six explicit supersessions (S1–S6)** against the
  Bible and the Design Constitution — e.g. S2 reverses "the tree recedes"
  to "the tree is primary and permanently full-bleed," which is the exact
  decision `ARCHITECTURE_PRINCIPLES.md`/`HYPER_UI_UX_REVIEW.md` (§4) later
  identifies as the root cause of the founder's "tree over work" complaint.

So: **same design-authority lineage, confirmed by VEDA's own provenance
statement — but with a real, named, itemized content change (S1–S6), not
merely a rename.** Where VEDA is silent, the Bible/Constitution still
govern (VEDA's own words: "The Constitution remains authoritative for the
Founder Dashboard's interior surfaces, which this brief explicitly did not
change").

---

## 2 · V1 — the 3 August HyperAgent archive

**`KALPAVRIKSHA_DESIGN_ARCHIVE_v1.zip`** — 150,533 bytes, 28 files,
internal dates 2026-08-03. **This zip carries its own authority table**
(`01_Assets/00_ARCHIVE_MANIFEST.md`, reproduced in ranked order):

| Rank in manifest | File (path inside zip) | Type | Contains | Class | Authority |
|---|---|---|---|---|---|
| 1 | `01_Assets/Experience Bible/THE_KALPAVRIKSHA_EXPERIENCE_BIBLE_v1.0.md` | md, 51,982 B | 13-section product constitution: vision, founder psychology, Interaction/Design/Motion/Voice/Autonomy/Demo law, engineering principles, "the Kalpavriksha Promise." **"Immutable unless the Founder explicitly amends it."** | V1 | **Authoritative** — rank 1 of the whole archive; superseded only where VEDA S1–S6 explicitly say so |
| 2 | `01_Assets/Design Constitution/Kalpavriksha_Design_Language_Constitution_v1.0.md` | md, 40,268 B | 12-section visual language: 70/20/10 translation, colour, lighting, depth, typography, the Tree spec, motion, voice/text sync, AI personality, component language, 10 immutable principles | V1 | Authoritative annex to the Bible; subordinate to it |
| — | `Design Constitution/Grid System/swiss_grid_tokens_dark_inverted.css.txt` | css/txt, 6,501 B | Generated grid tokens: 12-col, 8px baseline, 24px gutter, 48px margin, 1440px max width | V1 | Supporting — generated artifact |
| — | `Design Constitution/Grid System/grid_tokens_generator.py` | py, 10,021 B | Scaffold generator for the above | V1 | Supporting |
| — | `Design Constitution/Grid System/verify_grid.js` | js, 7,699 B | Verification harness — **the manifest itself records this was never run** (package registry unreachable); grid integrity is static-audit-only | V1 | Supporting, **unverified by its own admission** |
| 3 | `Founder Dashboard/Founder_Dashboard_UX_and_Interaction_Spec_v1.md` | md, 28,289 B | Full dashboard UX spec: 5 screens (01–05, with a "04b" variant), core experience flow, motion spec, interaction model, the "Screen 01 v2" rebuild rationale | V1 | Accepted design decision; superseded where the Bible conflicts |
| 3 | `Founder Dashboard/Approval_Queue_at_Volume_Design.md` | md, 4,789 B | Screen 04b: consequence ranking, 3 tiers, standing rules, mute/snooze/delegate, graded undo | V1 | Accepted design decision |
| 3 | `Demo Journey/The_90_Second_Demo_Path.md` | md, 4,605 B | Six-beat demo script, rules of conduct, 3 length variants | V1 | Accepted design decision |
| 4 | `Architecture Reports/MasterAgent_Architectural_Requirements_v1.md` | md, 38,199 B | 22 required capabilities / 5 layers, 7 event flows, API contracts, 5 memory stores, voice requirements, 11 migration risks, 6-phase build order | V1 | Derived requirements — changes if the Bible changes |
| 5 | `Product Philosophy/Kalpavriksha_Product_Philosophy.md` | md, 12,801 B | **Verbatim extract** of Bible §3, §4, §12, §13 | V1 | Convenience copy — "do not edit independently, edit the Bible" |
| 5 | `Vision Documents/Kalpavriksha_Vision.md` | md, 7,786 B | **Verbatim extract** of Bible §1, §2 | V1 | Convenience copy, same rule |
| 6 | `HyperAgent Deliverables/Thread_Working_Notes_and_Plan.md` | md, 5,855 B | Working record: plan, decisions, corrections, from the original design thread | V1 | Process record — illustrative, not normative |
| 6 | `HyperAgent Deliverables/Interactive Prototypes/01_Founder_Dashboard_Concept_v1.html` | html, 67,655 B | Self-contained playable prototype, the original 5 screens ("Wake Kalpavriksha") | V1 | Illustrative — **see §4, this is the file `tree.js`'s own header cites as its tree implementation's source, under a different filename** |
| 6 | `.../02_Approval_Queue_at_Volume_Screen04b.html` | html, 47,459 B | Playable Screen 04b: sweep/commit/60s-undo/rule-proposal | V1 | Illustrative |
| 6 | `.../03_The_First_Screen_v2.html` | html, 41,740 B | Playable "Screen 01 v2" | V1 | Illustrative |
| 6 | `.../04_The_90_Second_Demo_Path.html` | html, 41,109 B | Playable demo timeline | V1 | Illustrative |

**Known gaps the manifest itself records** (not my finding — theirs, kept
verbatim because they still apply): mobile breakpoint undesigned;
multi-principal/delegation undesigned; sound beyond voice undesigned; the
grid-verification harness never executed; the interactive prototypes' voice
is browser-speech-engine demo only, not production synthesis.

---

## 3 · V2 / VEDA — Product Veda v1.0

**`PRODUCT_VEDA_v1.0.zip`** — 87,833 bytes, 12 files, internal dates
2026-08-07. Also present **already extracted**, untouched by this survey,
at `PRODUCT_VEDA_v1.0_extracted/veda/` (identical content, confirmed by
matching file sizes).

| File | Type | Contains | Class | Authority |
|---|---|---|---|---|
| `veda/11_PRODUCT_VEDA.md` | md, 8,741 B | The index (§1 above): reading order, "five sentences that govern everything," the S1–S6 supersession table, testable success criteria, the refusal list, 2 open items for the founder | VEDA | **Authoritative index** — "Claude should never guess. Everything is here." |
| `veda/00_TOKENS.md` | md, 12,685 B | Typography, colour, spacing, radius, duration, easing, elevation, blur, icons, interaction states, motion accessibility — 121 tokens per the review's own count | VEDA | Authoritative — read first per its own build order |
| `veda/01_FOUNDER_SURFACE.md` | md, 11,507 B | Home screen: tree placement, vertical stack, ambient lighting, greeting, mic, text input, 3 breakpoints | VEDA | Authoritative |
| `veda/02_ANIMATION_SYSTEM.md` | md, 35,833 B | Tree geometry, the six tree states, state machine, performance budget, micro-animations. **Cited by name in `desktop_app/web/js/app.js`'s own comments** (already-shipped code) | VEDA | Authoritative — confirmed already governing shipped code |
| `veda/03_VOICE_EXPERIENCE.md` | md, 28,793 B | Mic matrix, listening indicator, waveform, interrupt, mute, noise, voice+text, transcript. **Cited by name in `voice_pipeline.py`'s own comments** (already-shipped code) | VEDA | Authoritative — confirmed already governing shipped code |
| `veda/04_CONVERSATION_DESIGN.md` | md, 34,955 B | Founder/Somesh messages, long replies, tables, charts, code, thinking, scroll, persistence | VEDA | Authoritative |
| `veda/05_DASHBOARD_BEHAVIOUR.md` | md, 15,867 B | Appearance, hiding, overlay, transitions — explicitly "content unchanged" from V1 | VEDA | Authoritative |
| `veda/06_STARTUP_EXPERIENCE.md` | md, 21,245 B | Launch → Splash → Growth → Light → Wake → Greeting → Ready. **Cited by name in `index.html`'s own comments** (already-shipped code) | VEDA | Authoritative — confirmed already governing shipped code |
| `veda/07_DESKTOP_PRESENCE.md` | md, 18,626 B | Taskbar, tray, minimize, restore, focus, application states | VEDA | Authoritative |
| `veda/08_THEME_SYSTEM.md` | md, 16,801 B | Founder Dark / Light / Auto. **Cited by name in `index.html`'s own comments** (already-shipped code) | VEDA | Authoritative — confirmed already governing shipped code |
| `veda/09_NOTIFICATION_SYSTEM.md` | md, 19,716 B | Notifications originating from the tree | VEDA | Authoritative |

**These ten-plus-one files are the closest thing this project has to a
single current design source of truth for the shipped UI**, and (uniquely
among everything in this inventory) five of them are already directly
cited by section number in the comments of code that is actually running.

---

## 4 · The `UX_*.html` screens — a second, revised naming of the V1 prototypes

Four files sit loose at the root of `UI-UX/`, dated 2026-08-03 (same day as
the V1 archive) — **not byte-identical to their §2 zip counterparts**,
matched here by exact `<title>` correlation:

| Standalone file | `<title>` | Zip counterpart (§2) | Size (standalone / zip) | Identical? |
|---|---|---|---|---|
| `UX_01_First_Screen_v2.html` | "The First Screen v2" | `03_The_First_Screen_v2.html` | 45,118 / 41,740 B | **No** — revised |
| `UX_02_Approval_Queue.html` | "Approval Queue at Volume · Screen 04b" | `02_Approval_Queue_at_Volume_Screen04b.html` | 50,837 / 47,459 B | **No** — revised |
| `UX_03_Founder_Dashboard.html` | "Founder Dashboard, Experience Concept v1" | `01_Founder_Dashboard_Concept_v1.html` | 71,033 / 67,655 B | **No** — revised |
| `UX_04_Demo_Path_90sec.html` | "The 90-Second Path" | `04_The_90_Second_Demo_Path.html` | 44,487 / 41,109 B | **No** — revised |

**Numbering warning:** the two naming schemes number differently for the
same screen — zip file `01_Founder_Dashboard...` is `UX_03_...` standalone.
A reader citing "screen 01" must say which scheme.

**`UX_03_Founder_Dashboard.html` is the most load-bearing file in this
entire inventory that isn't a markdown spec:** the shipped, committed
`desktop_app/web/js/tree.js` carries this exact filename in its own header
comment — *"Source: UX_03_Founder_Dashboard.html — THE NEURAL TREE
implementation"* — meaning the canvas tree renderer actually running in
the product today was ported from this specific file, not from V1's zip
copy, not from VEDA. Class: **V1 (implementation source)**. Authority:
**Authoritative-by-adoption** — its provenance in the manifest says
"illustrative," but the shipped codebase disagrees in practice.

---

## 5 · The `surface`/`presence`/`founder-edition` lineage — six zips, one thread

These six zips are **sequential snapshots of the same evolving TypeScript
reference implementation**, each a superset or near-superset of the last.
Verified by diffing shared filenames byte-for-byte, not inferred.

| Zip | Internal date | Package(s) | What's new vs. the previous snapshot | Class |
|---|---|---|---|---|
| `kalpavriksha-C20-presence.zip` **and** `kalpavriksha-C20-presence (1).zip` | 2026-08-06 | `presence/` | Baseline: presence-state derivation logic + tests + `HEALTH_C20.md`. **The two files are byte-for-byte identical** (verified `diff`) | VEDA/impl | Supporting — **exact duplicate pair**, keep one |
| `kalpavriksha-C21-surface.zip` | 2026-08-06 | `surface/` | Adds the React composition: `PresenceHeader`, `MissionStrip`, `ConversationArea`, `Composer`, `FounderActions`, `FounderModeSettings`, `ConversationSurface`, `surface.css`. No prominence logic yet | VEDA/impl | Supporting |
| `kalpavriksha-C24-founder-edition.zip` | 2026-08-06 | `founder-edition/` | Adds `AwaitingRuntime`, `EnvironmentPanel`, `FounderRuntimePanel`, `LiveIndicator`, `FounderDashboard`, ports (`environmentPort`, `founderRuntimePort`) — **no `SystemLine.tsx` yet** | VEDA/impl | Supporting |
| `kalpavriksha-PHASE-1-2.zip` | 2026-08-12 | `surface/` + `founder-edition/` + `docs/audits/PHASE_1_2_IMPLEMENTATION_PLAN.md` | Adds `prominence.ts`/`prominence.css` to `surface/`; adds `SystemLine.tsx` to `founder-edition/` (Phase 2's "collapse two panels into one line" component); `ConversationSurface.tsx` grows 4,431→6,316 B integrating prominence | VEDA/impl | Supporting |
| `kalpavriksha-PHASE-3.zip` | 2026-08-12 | as above + `validation/` | Adds `workState.ts`, `timing.ts`, `WorkRegion.tsx/.css`, `CompletionRequest.tsx/.css`; `ConversationSurface.tsx` grows to 10,482 B; adds `PHASE_1_2_VALIDATION.html`/`PHASE_3_VALIDATION.html` | VEDA/impl | Supporting |
| `kalpavriksha-vocab-verification.zip` | 2026-08-12 15:54 | as PHASE-3 + `vocabularySafety.test.ts` | `workState.ts` grows 8,934→12,640 B — the version carrying the long "two vocabularies coexist" docstring (the `ExecutionPhase` vs `ExecutionStatusName` divergence, later resolved — see §7) | VEDA/impl | Supporting — **superseded, see below** |
| `kalpavriksha-ui-integration-audit.zip` | 2026-08-14 00:21 | vocab-verification's exact content **plus** the full `presence/` package **plus** `docs/audits/UI_INTEGRATION_AUDIT.md` | Verified: every file shared with `vocab-verification.zip` is byte-identical; this zip is a strict superset | VEDA/impl | **This is the final, most complete snapshot of this lineage.** `vocab-verification.zip` is superseded by it — keep the later one |

**`kalpavriksha-desktop-v0.1.zip`** (172,786 B, 2026-08-06 10:1x) and
**`kalpavriksha-C19A.zip`** (202,909 B, 2026-08-06 15:3x–15:4x) are a
**separate, abandoned lineage**: a full React+Vite+TypeScript desktop app
shell (`AppShell`, `NavRail`, `TitleBar`, `StatusBar`, `CommandBar`,
`PresenceSigil`, a mock/HTTP "kernel" abstraction). C19A is v0.1 renamed
`desktop/`→ with `HEALTH_C19A.md`, `docs/ARCHITECTURE.md` added; core
kernel files (`fixtures.ts`, `mockKernel.ts`, etc.) are unchanged in size
between the two. **Neither was ever adopted** — the shipped app is vanilla
HTML/CSS/JS, not this React shell. Class: VEDA/impl. Authority:
**superseded/abandoned** — kept for history only.

**This whole lineage's endpoint, `kalpavriksha-ui-integration-audit.zip`,
is what Claude actually read and integrated** in the mission that produced
`desktop_app/web/js/{prominence,workState,timing}.js` and
`css/{prominence,work-region}.css` (now committed; git tag
`milestone-founder-edition-ui-integration`). The corresponding report,
already committed at `docs/audits/UI_INTEGRATION_PORT_1.md`, **does not
exist inside `VEDRA_PROJECT/`** — it was authored directly in the
production repo and is cross-referenced here for completeness, not part of
this asset-folder inventory.

---

## 6 · `kalpavriksha-UI-SOURCE-OF-TRUTH.zip` — a second, independent port attempt

79,216 bytes, 17 files, internal date **2026-08-14 01:03** — the
newest-dated zip in the whole asset area, and **not part of the §5
lineage** (no `surface/`/`founder-edition/`/`presence/` source trees; a
much smaller, purpose-built bundle).

| File | Type | Contains |
|---|---|---|
| `kv-ui-core/UI_SOURCE_OF_TRUTH.md` | md, 12,844 B | A second porting handoff: reading order, an equivalence-testing claim (6,192 paired cases vs. the TS source, "4 tests, 4 pass"), the same S3.1–S3.8 acceptance criteria as `UI_INTEGRATION_AUDIT.md` covers, an 8-step port order, and — explicitly — the honest limits: *"I have never seen the production UI," "I have never seen `execution_status.py`."* |
| `kv-ui-core/prominence.js` | js, 4,653 B | Vanilla-JS port of `prominence.ts` |
| `kv-ui-core/workState.js` | js, 10,704 B | Vanilla-JS port of `workState.ts` |
| `kv-ui-core/timing.js` | js, 6,074 B | Vanilla-JS port of `timing.ts` |
| `kv-ui-core/statusAdapter.js` | js, 5,120 B | **No equivalent exists in Claude's shipped port.** A dedicated backend-enum → UI-vocabulary adapter, pre-seeded with the 12 canonical spellings, the old hyphenated `ExecutionPhase` variants, and common synonyms (`running`→`executing`, `succeeded`→`completed`, etc.), explicitly designed as "the only file Claude should edit" |
| `kv-ui-core/conformance.html` | html, 53,973 B | Self-checking verification page, in-browser, 63 assertions — **matches** `Conformance self-test — PASS 63 assertions.jpg` (§8) |
| `kv-ui-core/equivalence.test.mjs` | mjs, 5,241 B | Node test asserting the `.js` files match validated TypeScript output over the full case matrix |
| `kv-ui-core/README.md` | md, 1,571 B | Short version of the same handoff |
| `docs/audits/{PHASE_1_2_IMPLEMENTATION_PLAN,HYPER_UI_UX_REVIEW,UI_INTEGRATION_AUDIT}.md` | md | Carried along for reference — identical content to their §5/§9 counterparts |
| `validation/{PHASE_1_2,PHASE_3}_VALIDATION.html` | html | Carried along, identical to §5's copies |

### Why this matters for reconciliation

**Claude's shipped port** (`desktop_app/web/js/{prominence,workState,timing}.js`,
already integrated and committed) and **this bundle's `kv-ui-core/`** are
two **independent** hand-translations of the same validated TypeScript
logic, built without knowledge of each other:

- Claude's port resolved the backend-enum question by reading
  `src/master_agent/missions/execution_status.py` directly and confirmed
  the real spellings match the reference exactly — no adapter layer, the
  values are hardcoded as verified-correct.
- This bundle's `statusAdapter.js` resolves the same question defensively,
  through a configurable mapping table that also tolerates the old
  hyphenated spellings and common synonyms, specifically because "one
  character of drift" once made the Work Region vanish entirely (a real,
  cited prior defect).

Both approaches are reasonable; they were never compared against each
other. **This bundle was never copied into `desktop_app/web/` — it exists
only in this zip.** Whether Claude's simpler, verified-exact mapping is
sufficient, or whether `statusAdapter.js`'s extra tolerance is worth
adopting, is the reconciliation decision this inventory surfaces rather
than resolves.

Class: VEDA/impl (a second implementation attempt). Authority: **supporting
evidence, not integrated** — its own title notwithstanding.

---

## 7 · `ARCHITECTURE_PRINCIPLES.md` — a duplicate of the HyperAgent review, under a different name

30,022 bytes, loose at the root of `UI-UX/`. **Verified byte-for-byte
identical** (`diff --strip-trailing-cr`, differs only in CRLF vs. LF line
endings) to `docs/audits/HYPER_UI_UX_REVIEW.md` as it appears inside
`kalpavriksha-ui-integration-audit.zip`, `kalpavriksha-vocab-verification.zip`,
and `kalpavriksha-UI-SOURCE-OF-TRUTH.zip` — **and to the already-committed**
`docs/audits/HYPER_UI_UX_REVIEW.md` in the production repo.

Content: the full HyperAgent UX review (7–12 August 2026) — the founder's
"tree over work"/"bulky" complaints traced to Product Veda §S2, the P1–P7
problem ranking, the Earlier-vs-Current comparison table, the conditional
five-condition information hierarchy, the Task-State/Timing/Founder-
Completion experience specs, the UX verdict **"C — hierarchy lost,
targeted redesign required,"** and the Top 5 Changes that became the
`UI_INTEGRATION_AUDIT.md` port manifest's own agreed-fix list.

Class: VEDA (review/reference). Authority: **Authoritative** — this is the
review that produced the whole Phase 1–3 lineage in §5; keep one copy,
the filename `ARCHITECTURE_PRINCIPLES.md` is misleading (it is a UX review,
not an architecture document) and worth renaming if this asset folder is
ever cleaned up.

---

## 8 · Screenshots

Six JPGs, loose at the root of `UI-UX/`. Filenames are self-describing;
correlated here against the artifact each one is evidence for.

| File | Size | Evidence for |
|---|---|---|
| `Conformance self-test _ PASS_ 63 assertions.jpg` | 96,222 B | `kv-ui-core/conformance.html` (§6) / `bundled-twin-html.html` (§9) — the 63-assertion self-test passing |
| `Phase 1_2 validation _ harness top.jpg` | 124,081 B | The Phase 1+2 validation harness (§5/§9), top-of-page view |
| `Before - After _ active work state.jpg` | 124,091 B | Prominence before/after comparison, an active-work screenshot |
| `Six states _ prominence by backend state.jpg` | 124,010 B | The six-state prominence table (§1's derivation logic) rendered live |
| `Phase 3 _ Work Region across the state machine.jpg` **and** `... (1).jpg` | 82,280 B each | Work Region across states — **the two files are byte-identical duplicates** (verified `md5sum`) |
| `Phase 3 _ before-after and founder completion.jpg` | 82,280 B | Founder Completion flow, before/after |

Class: VEDA (visual evidence). Authority: supporting — these are what the
review/handoff documents cite as their own "verified live" proof; no
markdown file embeds them directly, they are referenced by description.

---

## 9 · Validation HTML harnesses and their duplicates

| File | Size | Byte-identical to | Class |
|---|---|---|---|
| `phase-1-2-validation-html.html` | 74,568 B | `validation/PHASE_1_2_VALIDATION.html` inside §5/§6 zips — **confirmed identical** | Supporting — true duplicate, keep one |
| `phase-3-validation-html.html` | 68,535 B | `validation/PHASE_3_VALIDATION.html` inside §5/§6 zips — **confirmed identical** | Supporting — true duplicate, keep one |
| `kalpavriksha-phase-1-2-visual-validation.html` **and** `... (1).html` | 78,018 B each | Each other (**confirmed identical duplicate pair**); **not** identical to `phase-1-2-validation-html.html` above despite the same `<title>` — a separate revision, not further diffed | Supporting — internal duplicate pair; distinct from the file above |
| `bundled-twin-html.html` | 82,017 B | **Not** identical to `kv-ui-core/conformance.html` (§6) despite the same `<title>`, "Kalpavriksha — UI Core Conformance" — a related but separately-saved revision | Supporting — related, not a duplicate |

---

## 10 · The "previously discussed 8–9 page dashboard" — not found

Searched every markdown file and every zip's text content in this asset
area for "8-9 page," "8–9 page," "eight-page," "nine-page," and similar
phrasing. **No match anywhere.** The closest artifact by subject is the
V1 Founder Dashboard concept (§2, §4), which specifies **5 screens**
(01–05, with a "04b" variant) — not 8–9. If an 8–9-page dashboard was
discussed, the record of that conversation is not present in this asset
folder; it may exist only in a chat thread outside these files. Flagging
this as an honest gap rather than guessing which document was meant.

---

## 11 · Consolidated duplicates / superseded list

| Item | Verdict | Action for whoever cleans this up |
|---|---|---|
| `kalpavriksha-C20-presence.zip` vs `kalpavriksha-C20-presence (1).zip` | Byte-identical | Delete one |
| `Phase 3 _ Work Region across the state machine.jpg` vs `... (1).jpg` | Byte-identical | Delete one |
| `kalpavriksha-phase-1-2-visual-validation.html` vs `... (1).html` | Byte-identical | Delete one |
| `kalpavriksha-vocab-verification.zip` | Strict subset of `kalpavriksha-ui-integration-audit.zip` | Superseded — keep the later zip only |
| `kalpavriksha-desktop-v0.1.zip` / `kalpavriksha-C19A.zip` | Abandoned React/Vite lineage, never adopted by the shipped app | Superseded by the actual vanilla-JS `desktop_app/web/` — historical only |
| `ARCHITECTURE_PRINCIPLES.md` | Byte-identical content to `HYPER_UI_UX_REVIEW.md` (already committed in the repo) | Redundant copy in the asset folder; misleading filename |
| `kalpavriksha-UI-SOURCE-OF-TRUTH.zip` (`kv-ui-core/`) | **Not** superseded — an independent, never-integrated alternative to the port Claude already shipped | Needs an explicit reconciliation decision (§6), not a deletion |

---

## 12 · Cross-reference — where the shipped port and its report actually live

Not inside `VEDRA_PROJECT/`; recorded here because the request named them:

- `docs/audits/UI_INTEGRATION_AUDIT.md` — committed in the production repo
  (copied there from `kalpavriksha-ui-integration-audit.zip`, §5).
- `docs/audits/UI_INTEGRATION_PORT_1.md` — committed in the production
  repo; Claude's own completion report for the port that shipped
  `desktop_app/web/js/{prominence,workState,timing}.js` and
  `css/{prominence,work-region}.css`. Tag: `milestone-founder-edition-ui-integration`.
- `docs/audits/HYPER_UI_UX_REVIEW.md` and
  `docs/audits/PHASE_1_2_IMPLEMENTATION_PLAN.md` — also already committed,
  copied from the same zip.

These four are the only documents in this whole inventory that are
simultaneously (a) inside the production git repository, (b) covered by
Engineering Rule 001 clean-checkout verification, and (c) describing code
that is actually running. Everything else in this report is reference
material sitting in `VEDRA_PROJECT/01_Assets/UI-UX/`, not yet — or no
longer — connected to the shipped product.
