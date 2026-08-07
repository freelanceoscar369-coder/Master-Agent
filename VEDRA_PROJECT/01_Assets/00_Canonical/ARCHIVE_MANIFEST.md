# KALPAVRIKSHA — CANONICAL DESIGN ARCHIVE

**Project:** Kalpavriksha / VEDRA
**Archive created:** 3 August 2026
**Intended location:** `D:\MasterAgent\VEDRA_PROJECT\01_Assets`
**Source:** Hyperagent thread `cmsd4sfuk0aaa07ad0im7crlm`

---

## Canonical hierarchy — read this first

These documents are **not equal in authority.** When two disagree, the higher one governs.

| Rank | Document | Status |
|---|---|---|
| **1** | `Experience Bible/THE_KALPAVRIKSHA_EXPERIENCE_BIBLE_v1.0.md` | **Immutable.** Amendable only by explicit act of the Founder, under the process in its final section. |
| **2** | `Design Constitution/Kalpavriksha_Design_Language_Constitution_v1.0.md` | Subordinate annex to the Bible. Holds the *values* the Bible's laws are expressed in. Craft may be refined; belief may not. |
| **3** | `Founder Dashboard/` · `Demo Journey/` | Accepted design decisions. Superseded by the Bible where they conflict. |
| **4** | `Architecture Reports/` | Derived requirements. Changes when the Bible changes, never the reverse. |
| **5** | `Vision Documents/` · `Product Philosophy/` | **Extracts, not originals.** Verbatim excerpts from the Bible for convenience. Do not edit independently — edit the Bible. |
| **6** | `HyperAgent Deliverables/` | Working prototypes and process record. Illustrative, not normative. |

---

## Contents

### Experience Bible
`THE_KALPAVRIKSHA_EXPERIENCE_BIBLE_v1.0.md` — 14 sections. The operating philosophy: vision, founder psychology, product philosophy, the emotional arc, and the Interaction, Design, Motion, Voice, Autonomy and Demo Constitutions, plus engineering principles and the Kalpavriksha Promise.

### Design Constitution
`Kalpavriksha_Design_Language_Constitution_v1.0.md` — 12 sections. The complete visual language: the 70/20/10 translation, colour, lighting, depth, typography, the Tree specification, motion language, voice/text synchronisation, AI personality, component language, the premium interaction gate, the ten immutable principles and governance.

`Grid System/` — the structural substrate all screens are built on.
- `swiss_grid_tokens_dark_inverted.css.txt` — generated grid tokens (12 columns · 8px baseline · 24px leading · 24px gutter · 48px margin · 1440px max width), dark-inverted from the Swiss editorial canon
- `grid_tokens_generator.py` — scaffold generator
- `verify_grid.js` — verification harness (column adherence, overlay match, baseline lock, optical ink alignment)

### Founder Dashboard
`Founder_Dashboard_UX_and_Interaction_Spec_v1.md` — the full UX spec including the v1 concept, the five original screens, the challenges made to the original brief, the resolved approval-queue decision, and the Screen 01 v2 rebuild.
`Approval_Queue_at_Volume_Design.md` — the queue at volume: consequence ranking, three tiers, standing rules proposed from behaviour, mute/snooze/delegate, graded undo windows, autonomy ratio.

### Demo Journey
`The_90_Second_Demo_Path.md` — six beats, the six rules of conduct, what is cut and why, and three length variants off one spine.

### Product Philosophy
`Kalpavriksha_Product_Philosophy.md` — Bible §3, §4, §12, §13 (extract).

### Vision Documents
`Kalpavriksha_Vision.md` — Bible §1, §2 (extract).

### Architecture Reports
`MasterAgent_Architectural_Requirements_v1.md` — 22 required capabilities across five layers, affected modules, seven event flows, logical API contracts, five memory stores, voice requirements, runtime implications, eleven migration risks, six-phase implementation order.

### HyperAgent Deliverables
`Thread_Working_Notes_and_Plan.md` — the working record: plan, decisions, corrections.
`Interactive Prototypes/` — four self-contained HTML files. **Open directly in a browser; no build step, no server, no dependencies beyond web fonts.** Press `G` in any of them to toggle the grid overlay.
- `01_Founder_Dashboard_Concept_v1.html` — the original five screens. Click "Wake Kalpavriksha."
- `02_Approval_Queue_at_Volume_Screen04b.html` — select sweep items, commit, catch the 60s undo, accept the rule proposal.
- `03_The_First_Screen_v2.html` — the philosophy applied. Resolve both decisions and watch the screen empty. Demo-state control at lower left.
- `04_The_90_Second_Demo_Path.html` — playable timeline. Press Play and rehearse against the clock.

---

## Known gaps, recorded deliberately

Not oversights — decisions held open.

1. **Mobile.** Below ~1080px the composition breaks. A phone-sized Kalpavriksha is probably only the approval flow and the silent state, which is a separate design programme.
2. **Multi-principal.** Everything assumes one founder. Delegation introduces a second principal; the Bible flags it, the architecture report recommends modelling the principal as an entity now.
3. **Sound.** None beyond voice. Under Principle X it could only ever be ambience, never notification.
4. **Grid verification not executed.** The Puppeteer harness in `Grid System/` was never run — the package registry was unreachable from the build environment. Grid integrity was confirmed by static audit only (column placements on valid lines, zero off-baseline vertical spacing). **Run the harness before treating the prototypes as pixel-authoritative.**
5. **Interactive prototype voice** uses the browser speech engine for demonstration only. Production requires real synthesis with programmable prosody — see the Voice Requirements section of the architecture report.

---

## Provenance

All content in this archive was produced in a single working session on 3 August 2026, in sequence: dashboard concept → approval queue at volume → first screen rebuild → demo path → design language → Experience Bible → architecture requirements. Each artefact was accepted by the Founder before the next was begun.

Sample data throughout (mission IDs, rupee figures, vendor names, the founder name Onkar) is illustrative. No real company data is present in this archive.
