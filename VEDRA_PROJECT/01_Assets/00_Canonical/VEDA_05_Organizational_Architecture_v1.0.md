# VEDA 05 — Organizational Architecture

**The internal structure through which an Objective becomes a completed outcome.**

| | |
|---|---|
| **Version** | 1.0 |
| **Status** | Architecture — proposed. Requires founder ratification before any section becomes FROZEN. |
| **Date** | 2026-08-05 |
| **Type** | Architecture only. No code, no implementation, no edits to frozen documents. |
| **Depends on** | VEDA 01 (Experience), VEDA 02 (Design Constitution), VEDA 03 (Founder Dashboard), VEDA 04 (Architecture Requirements), KALPAVRIKSHA_VISION_V2 §§3–6, §8, §10, §12, §15–17 |
| **Supersedes** | Nothing. Extends VEDA 04 Layer C and the Constitution §3–§4 boundary. |

---

## 0 · Reading note, assumptions, and two findings that change the answer

### 0.1 What this document is

The Objective Engine currently turns one stated intention into a flat list of capability calls and dispatches them. This document replaces that with an organizational structure: a small number of standing departments, each holding a distinct standard of correctness, through which every objective flows.

It is written to be permanent. Where I am confident, I state an invariant. Where the design has a seam, I name the seam rather than writing smoothly over it. Where the brief's proposed hierarchy is wrong, I say so and replace it — that was the instruction, and it is warranted twice below.

### 0.2 Assumptions, stated so they can be corrected

1. **Vedra is the persona and the single voice; Kalpavriksha is the platform.** The chain `User → Vedra → Objective Engine` reads as: the founder speaks to Vedra, Vedra is the only thing that speaks back, and the Objective Engine is machinery the founder never addresses directly. This document depends on that reading, and §3.4 turns it into a hard structural rule.
2. **"Objective Engine" is the product name for what the repository currently implements as `TaskDispatcher` + `Objective`** (`src/master_agent/mission_control/`). No component in the codebase carries the name. Every claim below about current behaviour is drawn from that code, not from the name.
3. **The Constitution's three-layer separation (Brain / Shared Infrastructure / Operator) is not replaced by this document.** Departments live *inside* the Brain's planning authority and *drive* the Operator; they are not a fourth layer. §3.3 makes this precise, because getting it wrong would create a second execution path, and VEDA 04 R1 correctly calls that the most dangerous mistake available.

### 0.3 Finding one — the proposed hierarchy is not a hierarchy

The brief proposes:

```
User → Vedra → Objective Engine → Department Heads → Mission Managers
     → Skills → Tools → Execution → Quality Review → Learning
```

This conflates two orthogonal things: a **chain of authority** (who is permitted to decide what) and a **sequence of events** (what happens in what order). The first five terms are authority. The last three are not — Execution is what a Tool *does*, and Quality Review and Learning are not subordinate to Tools; they are obligations that attach to every level simultaneously.

Read literally, the diagram instructs us to build a nine-hop call stack. That would make the system slower, more serialized, and more fragile than what exists today, and it would move the bottleneck from the Objective Engine down one level to the Department Heads without removing it. **Adding a layer beneath a bottleneck does not remove the bottleneck. It moves it and adds latency.**

The corrected model, developed in §3, is:

> **A shallow spine of three decision authorities, standing beside a wide field of horizontal services that any level may call directly.**

The Objective Engine stops being a bottleneck not because something now sits below it, but because five responsibilities that currently pass *through* it — escalation delivery, receipts, evidence, provider selection, learning — are moved *out of the vertical path entirely*.

### 0.4 Finding two — three terminology collisions exist in the repository today

The Constitution's §17 Terminology Freeze states that every term has exactly one meaning and that no frozen term may acquire a third synonym. Three terms in the brief collide with terms already in use:

| Brief's term | Already means | Consequence | Resolution |
|---|---|---|---|
| **Mission Manager** | `MissionManager`, the Shared Infrastructure component that owns Mission state (§5.3, §16) | Two meanings for one name — a direct freeze violation | Rename the new role **Mission Lead**. §2.5. |
| **Skill** | Nothing frozen — but sits one millimetre from **Capability**, which is frozen | Risk of becoming a synonym for Capability, which §17 forbids | Skill is redefined as a *judgment wrapper over Capabilities*, never itself dispatchable. §7.1. |
| **Objective** | `Objective` (`mission_control/tasks.py`) *and* **Mission** (frozen §17: "one complete Intent-to-Outcome unit of work") | Two names for one concept, already live in shipped code | Requires a ratified reconciliation. §10 R7 states the options; this document does not resolve a frozen term unilaterally. |

These are not pedantry. §16 exists because a component with two homes eventually has two states, and two states that disagree about authorization is the failure mode the entire Trust Spine exists to prevent.

---

## 1 · Executive Summary

### 1.1 The central finding

VEDA 04 established that this system's primary object is **a decision, not a task**. That finding governs this document too, and it changes what a department is for.

In a human company, departments exist for two reasons that do not apply here: careers specialize, and one manager can only supervise a handful of people. Neither is a real constraint for Kalpavriksha. Importing the org chart because Apple has one would be cargo cult architecture.

There are two real constraints, and both are severe:

**Constraint A — cognitive load on the planner.** At 500 skills, no single planner can hold the full capability surface in working context and still plan well. This is the actual bottleneck. It is not throughput; the dispatcher can already fan out. It is *the width of the thing one reasoner must understand to produce a good plan.* Departments solve this by making planning hierarchical: the Objective Engine plans over ~7 department-level outcomes; each department plans over ~40–80 skills it actually owns.

**Constraint B — no single authority can define "good" across crafts.** A component competent to judge whether a colour grade is right is not thereby competent to judge whether a database migration is reversible. A single quality authority across 500 skills is either shallow everywhere or a permanent queue.

So the honest justification for departments is not organizational aesthetics. It is this:

> **A department is a bounded standard of correctness, paired with a bounded planning surface. It exists so that both "what should we do next" and "is this good enough" can be answered competently and locally.**

Everything in this document follows from that sentence.

### 1.2 What is recommended

**Seven departments**, each passing a four-part admission test (§2.1):

Research · Creative · Production · Engineering · Operations · Finance · Correspondence

**Three central functions that are deliberately *not* departments**: Narration (Vedra's single voice), Verification (the Constitution's §10 subsystem), and Assurance (a thin process auditor that never judges craft).

**A Mission Lead role that is instantiated lazily**, not a permanent layer — present only when a department's contribution to an objective spans multiple skills or crosses a departmental seam. Single-skill contributions go Head → Skill with no intermediary. §2.5.

**Quality is hybrid, and the split is precise**: craft judgment is distributed to departments; outcome verification is central and mechanically independent of execution; process assurance is central and thin. Completion requires a NASA-style go/no-go poll in which the Objective Engine can *count* votes but cannot *cast* one. §4.3.

**Departments never call tools, never select providers, never speak to the founder, and never own state.** These four prohibitions are what keep the structure from becoming seven silos.

### 1.3 What is rejected, and why it matters

Four candidates from the brief's example list are rejected. Each rejection is load-bearing:

- **Quality Assurance as a department** — a central QA department cannot articulate a coherent standard of correctness spanning colour grading, Python, and vendor reconciliation. Toyota's answer is right: quality is built at the station, not inspected at the end. §4.3.
- **Knowledge as a department** — it is already Shared Infrastructure (§5.4, §9). Making it a department would give one component two homes and violate §16.
- **Automation as a department** — automation is not a standard of correctness; it is a technique. What "Automation" would own is the Standing Rule Engine (VEDA 04 C1), which is cross-cutting and belongs to the boundary, not to a craft. This is the most seductive wrong answer on the list because it sounds like it does something.
- **Communication as a single department** — the brief's list conflates two things that must never share an owner: *inbound narration to the founder* (which must have exactly one voice and is not a department at all) and *outbound correspondence to third parties* (which is real work with the highest social irreversibility in the system, and does deserve a department). §2.4.

### 1.4 The three inheritances

The brief asks for Apple, Toyota, and NASA. Each contributes one thing, and only one:

- **Apple → functional, not divisional.** Departments are organized by craft, not by product line or customer. There is no "Vedra Video Department." One taste authority per craft, company-wide. This is why the roster is seven and not seventeen.
- **Toyota → jidoka and the andon cord.** Quality is built in at the station by whoever does the work, and *any* participant can halt the line without permission and without penalty when they detect that the wrong thing is being built. §4.3, §9.5.
- **NASA → CAPCOM, flight rules, and the go/no-go poll.** One voice to the crew (§3.4). Decisions made in advance, in calm, rather than in the moment (§8.3, the Reversibility Registry as flight rules). And completion by unanimous poll, where the Flight Director declares but does not vote in place of a console (§4.3).

---

## 2 · Department Map

### 2.1 The admission test

A candidate becomes a department only if it passes all four. This test is the document's most important single artifact, because it is what prevents the roster from growing to thirty over ten years.

**T1 · Irreducible standard of correctness.** It can say "this is not good enough" for a reason no other department can articulate. If another department could sign off its work without loss, it is not a department.

**T2 · Distinct failure mode and reversibility profile.** Its characteristic failure is unlike the others', and it sits at a different point on the reversible/irreversible axis.

**T3 · Distinct consequence vocabulary.** The four mandatory fields of a judgment request (VEDA 04 B1: what changes · what it costs · what happens if you do nothing · whether it can be undone) come out shaped differently for this department than for any other.

**T4 · Bounded, non-overlapping planning surface.** The skills it would own form a coherent set that a single reasoner can hold, and no skill in it is better owned elsewhere.

**The merge rule.** Two departments merge when either can sign off the other's work without loss of judgment. Departments are not preserved for sentimental or historical reasons.

**The amendment rule.** Adding, removing, or merging a department is a constitutional amendment requiring an ADR and founder ratification — never a configuration change. Without this, the roster grows monotonically, because every unowned skill creates local pressure for a new home.

### 2.2 The seven

| # | Department | One-sentence mission | Owns the question |
|---|---|---|---|
| 1 | **Research** | Establish what is true, with its sources attached. | *Is this actually so, and how do we know?* |
| 2 | **Creative** | Decide what should be said or made, and why it is the right thing. | *Is this the right thing to make?* |
| 3 | **Production** | Turn approved intent into finished artifacts. | *Is the artifact faithful to the brief and technically sound?* |
| 4 | **Engineering** | Build and change software. | *Is it correct, tested, reviewable, and maintainable?* |
| 5 | **Operations** | Keep the real world and the machines in the intended state. | *Is the world as we believe it to be, and is it healthy?* |
| 6 | **Finance** | Authorize and record every external commitment. | *Should we be bound by this, and can we afford it?* |
| 7 | **Correspondence** | Carry the company's word to people outside it. | *Is this the right thing to send to this person, now?* |

Full charters — mission, responsibilities, inputs, outputs, decision authority, escalation rules — are in §4.2.

### 2.3 Why exactly these, and the near-misses

**Creative and Production are separate, and that seam is deliberate.** Creative owns *message and intent*; Production owns *fidelity of realization*. Different standards of done: "is this the right script" versus "is this rendered at the right specification with synchronized audio." Different failure modes: a technically flawless video of the wrong argument, versus the right argument at the wrong aspect ratio. The brief's own conflict scenario — Creative changes the script after Media has animated — lives exactly on this seam, which is evidence that the seam is real and worth naming rather than dissolving. §9 handles it.

**Engineering and Operations are separate.** Engineering changes the artifact; Operations changes the running world. "Is this code correct and maintainable" and "is production healthy and is the deploy reversible" are different questions with different reversibility profiles — a bad commit is reversible in seconds, a bad migration frequently is not.

**Research is a department, not part of Shared Infrastructure.** Research *produces* sourced belief; Memory *stores* it (§5.4). The same relationship Operations has with Evidence. Research qualifies under T1 because "is this claim adequately sourced" is a judgment only it can make, and it has a mechanical spine in the Evidence Graph (VEDA 04 B5).

**Finance is a department with an unusual shape: a cross-cutting veto.** Money touches every other department's work, which raises a fair objection — is it a department, or a constraint? It is a department, because "is this within the envelope, is this vendor legitimate, what does this do to runway" is an irreducible standard (T1) with the system's highest irreversibility exposure (T2). But its authority reaches sideways: it may veto any other department's committing action. NASA's precedent is exact — the console that can call an abort is not thereby the Flight Director.

**Correspondence is the department the brief's list was missing.** Sending an email to a vendor, replying to a customer, posting publicly: real work, its own standard ("does this contradict what we told them in March?"), and social irreversibility that no compensating action reverses. An apology is not an undo.

### 2.4 Rejected candidates

| Candidate | Fails | Where it actually lives |
|---|---|---|
| **Quality Assurance** | T1 — no coherent standard across crafts; T4 — its surface is every surface | Split three ways: craft judgment → departments; outcome verification → Verification Subsystem (§10); process audit → Assurance function. §4.3. |
| **Knowledge** | Already Shared Infrastructure (§5.4, §9); a second home violates §16 | Memory + Knowledge Lifecycle. Departments *nominate* Knowledge Candidates; the Promotion Review promotes. |
| **Automation** | T1 — a technique, not a standard of correctness | Standing Rule Engine (VEDA 04 C1) + Rule Proposal Miner (C3). Cross-cutting, owned by the boundary. |
| **Communication** | Conflates two incompatible things | Inbound → **Narration**, a central function with exactly one voice, not a department. Outbound → **Correspondence** department. |
| **Media** | Merges cleanly into Production under T1 | Production. |
| **Legal / Compliance** | T4 today — insufficient distinct surface at current scale | Folded into Finance's commitment standard. **Promotion trigger:** the first objective whose blocking judgment is a legal question rather than a spend question. |
| **People / HR** | T1, T4 — no distinct surface with one founder | Not created. **Promotion trigger:** the first non-founder principal with standing approval authority (VEDA 04 C6 Delegation). |
| **Strategy** | T1 — this is the founder's judgment, by constitutional definition | Nowhere. §3 of the Experience Bible is explicit: humans provide judgment. A Strategy department is the system deciding what the company should want, which VEDA 01 §10 Ethics 1 forbids. |

The last row deserves emphasis. **There is no department for deciding what the company should be doing.** That is not an omission; it is the product.

### 2.5 The Mission Lead layer — should it exist?

**Recommendation: yes, but as a lazily-instantiated role, not a standing layer, and not under the name "Mission Manager."**

**Why it must exist.** Without it, a Department Head is simultaneously the standards authority for its craft *and* the project manager for every concurrent objective touching that craft. That is the department-level reproduction of the exact bottleneck we are removing from the Objective Engine. At a hundred concurrent objectives, seven Heads would serialize on coordination work that has nothing to do with judgment. Separating *standing authority over a craft* from *temporary ownership of one objective's outcome inside that craft* is the whole reason the role earns its place.

**Why it must be lazy.** A permanent layer would impose an extra hop on every objective, including "read me that file." Latency compounds against VEDA 04's §7 budgets, and the honest-latency constraint means we cannot hide it.

**Instantiation rule.** A Mission Lead is created for a department's contribution to an objective if and only if that contribution (a) invokes more than one skill, **or** (b) has a dependency on, or a dependent in, another department. Otherwise the Head assigns the skill directly and remains accountable.

| Aspect | Definition |
|---|---|
| **Responsibilities** | Owns one department's contribution to one objective end to end: sequencing its skills, holding its budget, tracking its dependencies in and out, assembling its evidence, and presenting it for its Head's sign-off. |
| **Lifecycle** | Created at department contract acceptance → active through execution → dissolved at sign-off or at objective abandonment. Its record persists permanently; it is the accountable name on every receipt its work produced. |
| **Ownership** | Owned by its department. Accountable to the objective contract held by the Objective Engine. Never accountable to another department. |
| **Authority** | Sequencing, retry within budget, and skill selection within its department's owned set. **No sign-off authority** — the Head signs, never the Lead. **No spend authority** beyond the contract envelope. **No authority over any irreversible action, ever.** |
| **Prohibitions** | Never speaks to the founder. Never negotiates directly with another department's Lead on scope — cross-department scope changes are amendments (§9.3). Never selects a Provider. |

The Head-signs-not-the-Lead rule is a separation of duty and it is not negotiable: the party that produced the work is never the sole party that certifies it.

---

## 3 · Hierarchy Diagram

### 3.1 The corrected model

```
                              ┌─────────────────────────────────────┐
                              │             FOUNDER                  │
                              │   judgment · authority · override    │
                              └───────────────┬──────────────────────┘
                                              │  one channel, both ways
                              ┌───────────────┴──────────────────────┐
                              │              VEDRA                    │
                              │   the single voice · the interface    │
                              │  (Narration + Voice Charter + Brief)  │
                              └───────────────┬──────────────────────┘
                                              │
   ══════════════════════════════════════════════════════════════════════════════
    THE SPINE — three decision authorities         THE FIELD — horizontal services
   ══════════════════════════════════════════════════════════════════════════════
                                              │
                              ┌───────────────┴──────────────┐        ┌──────────────────┐
              AUTHORITY 1 →   │      OBJECTIVE ENGINE         │◄──────►│   JUDGMENT        │
                              │  admits · decomposes · holds  │        │  consequence ·    │
                              │  the contract · declares done │        │  ranking · router │
                              │  ── decides SCOPE ──          │        │  silence defaults │
                              └───────────────┬──────────────┘        └──────────────────┘
                                              │                                ▲
              ┌────────┬────────┬─────────────┼────────┬────────┬────────┐     │
              ▼        ▼        ▼             ▼        ▼        ▼        ▼     │
           ┌──────┐┌──────┐┌──────────┐┌──────────┐┌──────┐┌───────┐┌────────┐│
AUTHORITY  │RESEA-││CREAT-││PRODUCTION││ENGINEER- ││OPERA-││FINANCE││CORRESP-││
    2  →   │ RCH  ││ IVE  ││          ││   ING    ││TIONS ││       ││ ONDENCE││
           │ HEAD ││ HEAD ││   HEAD   ││   HEAD   ││ HEAD ││ HEAD  ││  HEAD  ││
           └───┬──┘└───┬──┘└─────┬────┘└─────┬────┘└───┬──┘└───┬───┘└────┬───┘│
               │       │         │           │         │       │         │    │
               │   ── each Head decides CRAFT, and signs off its own work ──   │
               │       │         │           │         │       │         │    │
               ▼       ▼         ▼           ▼         ▼       ▼         ▼    │
           ┌────────────────────────────────────────────────────────────────┐ │
           │  MISSION LEADS  (instantiated only when a contribution spans    │ │
           │  multiple skills or crosses a departmental seam — §2.5)         │ │
           │  ── decides SEQUENCE, never scope, never sign-off ──            │ │
           └───────────────────────────┬────────────────────────────────────┘ │
                                       │                                       │
           ┌───────────────────────────┴────────────────────────────────────┐ │
           │  SKILLS  ── owned by exactly one department (§7)                │ │
           │  a named composition of Capabilities + its standard of use      │ │
           └───────────────────────────┬────────────────────────────────────┘ │
                                       │                                       │
   ─────────────────────────────────────────────────────────────────────────── │
    Below this line is the Constitution's Operator. Nothing above it executes.  │
   ─────────────────────────────────────────────────────────────────────────── │
                                       │                                       │
           ┌───────────────────────────┴────────────────────────────────────┐ │
           │  CAPABILITIES → WORKERS → ACTIONS → ENVIRONMENT                 │ │
           │  the one and only execution path (Constitution §4, §12)         │ │
           └───────────────────────────┬────────────────────────────────────┘ │
                                       │                                       │
                                       ▼                                       │
   ══════════════════════════════════════════════════════════════════════════════
    HORIZONTAL SERVICES — every level calls these directly, never through the spine
   ══════════════════════════════════════════════════════════════════════════════
     ┌────────────┐ ┌────────────┐ ┌───────────┐ ┌──────────┐ ┌──────────────┐
     │ TRUST SPINE│ │VERIFICATION│ │ ASSURANCE │ │ BROKER   │ │  LEARNING    │
     │ receipts · │ │ observes · │ │ audits    │ │ decides  │ │ L1 skill     │
     │ reversibi- │ │ produces   │ │ process,  │ │ which    │ │ L2 provider  │
     │ lity ·     │ │ Evidence · │ │ never     │ │ Provider │ │ L3 boundary  │
     │ override   │ │ independent│ │ craft     │ │ serves   │ │ none enact   │
     └────────────┘ └────────────┘ └───────────┘ └──────────┘ └──────────────┘
     ┌────────────────────────────────────────────────────────────────────────┐
     │ SHARED INFRASTRUCTURE (Constitution §5) — Capability Registry ·         │
     │ Permission System · Mission State · Memory · Configuration · Telemetry  │
     └────────────────────────────────────────────────────────────────────────┘
```

### 3.2 How the brief's nine terms map onto this

| Brief's term | Where it went | Why |
|---|---|---|
| Vedra | Kept, elevated | It is the interface, not a router. All narration; no work. |
| Objective Engine | Kept, narrowed | Now holds contracts and scope only. Five responsibilities moved out. |
| Department Heads | Kept as Authority 2 | The craft standard. |
| Mission Managers | Renamed **Mission Lead**, made lazy | Name collision (§0.4); a permanent layer would add latency for no gain. |
| Skills | Kept, redefined | Now a judgment wrapper over Capabilities, never dispatchable itself (§7.1). |
| Tools | Kept, but unowned | Tools are Capabilities and Providers in Shared Infrastructure. No department owns one (§8). |
| Execution | **Removed as a level** | Execution is what a Capability does. It is a verb, not a layer — and the Constitution already owns the single execution path. |
| Quality Review | **Removed as a level, redistributed** | Made a horizontal obligation attaching at every level, plus a completion gate. §4.3. |
| Learning | **Removed as a level, split three ways** | Three loops with three owners and three cadences. §5.6. |

### 3.3 The Constitutional placement — where the spine sits in the frozen three-layer model

This is the question most likely to be got wrong, so it is stated flatly:

| New component | Constitutional layer | Why |
|---|---|---|
| Vedra / Narration | **Brain** (§3.4 Reporter, expanded) | Deciding how to explain is Brain-shaped judgment. |
| Objective Engine | **Brain** (§3.2 Planner, hierarchical) | It plans; it does not execute. |
| Department Head | **Brain** | It plans within a craft and judges quality. It reasons; it never touches an Environment. |
| Mission Lead | **Brain** | Sequencing is planning. |
| Skill | **Brain-side definition, Operator-side execution** | The *standard* is Brain. The Capabilities it composes execute through the Operator, unchanged. |
| Capability / Worker / Action | **Operator** (§4, §12) | Untouched by this document. |
| Verification | **Operator-adjacent, own contract** (§10) | Untouched. |
| Assurance | **Shared Infrastructure** | It reads receipts and Evidence; it produces neither. |
| Judgment services | **Shared Infrastructure** | Both Brain-side departments and the Operator's failures raise judgment requests; both need the same answer. Same reasoning as §5.2 and §5.7. |

**Invariant.** No department, Head, Lead, or Skill acquires Environment access, holds a Permission grant, or creates an execution path. The Operator's Worker Runtime remains the single door. **A department that could execute would be a second execution path, and VEDA 04 R1 correctly rates that critical: holes in an audit spine are worse than no spine, because they manufacture false confidence.**

### 3.4 The CAPCOM rule

> **Exactly one component speaks to the founder. It is Vedra. No department, Head, Lead, Skill, or Worker has any channel to the founder, in any medium, under any condition — including failure, including urgency, including its own error.**

This is not a presentation preference. In Mission Control, telemetry from a dozen consoles converges on one person who talks to the crew, because a crew hearing twelve voices under load cannot act. Kalpavriksha's version of that load is the founder's resident model of the company (VEDA 01 §2), which degrades on interruption. Seven departments with direct access would reproduce, precisely, the notification storm that VEDA 01 §5 abolishes.

**Structural enforcement, not policy:** departments have no reference to any narration or surfacing interface. They can only *raise a judgment request*, which enters the Judgment service, is ranked against all other open requests, and reaches the founder — if at all — as one line composed by Vedra in one voice. A department cannot make itself louder by being more insistent, because it has no volume control to reach for.

**The corollary that costs something:** a Department Head cannot warn the founder directly even when it believes the objective is going badly. It must raise a judgment request or pull the andon cord (§9.5). This is the correct trade. A department that can bypass ranking when it feels strongly is a department that will feel strongly.

### 3.5 Why the Objective Engine is now structurally incapable of being the bottleneck

Five responsibilities are removed from the vertical path. Each removal is what makes the claim true rather than aspirational:

1. **It does not deliver escalations.** Departments publish judgment requests to the Judgment service directly. The Engine is not in that path and cannot delay it.
2. **It does not write or hold receipts.** Every actor writes its own intent record to the Trust Spine before acting (VEDA 04 A1). The Engine writes only receipts for its own decisions.
3. **It does not collect evidence.** Verification writes Evidence to Memory; departments and the Engine both read it. No aggregation hop.
4. **It does not choose providers.** The AI Capability Broker decides, for every actor, including the Engine itself (§5.7 — "No other component may decide").
5. **It does not learn.** The three learning loops each have their own owner and cadence (§5.6).

What remains in the Engine is small, and small deliberately: **admit, decompose into department contracts, hold the contract, arbitrate scope, count the completion poll, declare done.** It touches an objective a handful of times over its life, never per task, never per tool call, never per utterance.

---

## 4 · Responsibility Matrix

### 4.1 Decision rights — who decides what

The row that matters most is the last one.

| Decision | Founder | Vedra | Objective Engine | Dept Head | Mission Lead | Skill |
|---|---|---|---|---|---|---|
| What the company should want | **Decides** | — | — | — | — | — |
| Whether to accept an objective | **Decides** | Presents | Recommends | — | — | — |
| The objective's acceptance criteria | **Approves** | Presents | Proposes | Consulted | — | — |
| Which departments participate | — | — | **Decides** | — | — | — |
| Objective budget and deadline | **Approves** | Presents | Proposes | Consulted | — | — |
| Reallocating budget between departments | — | — | **Decides** (within envelope) | Requests | — | — |
| Which skills a department uses | — | — | — | **Decides** | Selects within set | — |
| Execution order within a department | — | — | — | Sets policy | **Decides** | — |
| Retry within budget | — | — | — | — | **Decides** | — |
| Which Provider serves a call | — | — | — | — | — | Asks Broker; **Broker decides** |
| Craft sign-off on a deliverable | — | — | Counts | **Decides** | Presents | — |
| Whether Evidence matches Expected Outcome | — | — | Counts | — | — | — · **Verification decides** |
| Whether process was complete | — | — | Counts | — | — | — · **Assurance decides** |
| Declaring an objective complete | Informed | Narrates | **Declares** (on unanimous go) | Votes | — | — |
| Halting an objective (andon) | **May** | — | **May** | **May** | **May** | **May** |
| Suspending all autonomy (override) | **Decides, alone** | — | — | — | — | — |
| **Any irreversible action** | **Decides, always, contemporaneously** | — | **Never** | **Never** | **Never** | **Never** |

That last row is VEDA 01 §10 Ethics 3, made structural: *no rule, however broad, ever grants irreversible authority.* No level of this hierarchy — including the Objective Engine — can authorize an irreversible action. The hierarchy delegates work and craft judgment. It never delegates irreversibility.

### 4.2 Department charters

---

#### 4.2.1 · RESEARCH

**Mission.** Establish what is true, with sources attached, so that every other department builds on fact rather than on plausible text.

**Responsibilities.** Gather and read sources. Distinguish *verified*, *reported*, and *inferred*, and never let the distinction dissolve in a summary. Maintain the Evidence Graph binding for every claim it emits. Detect and surface contradiction with previously held facts rather than silently overwriting them. Report staleness: distinguish *I don't know* from *I haven't checked* (VEDA 01 §8).

**Inputs.** A question with a decision attached to it. A freshness requirement. A budget.

**Outputs.** A **Finding**: a claim set where every claim carries its sources, its confidence level in coarse steps, what would raise that confidence, and its as-of timestamp. Never a number without a source.

**Decision authority.** Sufficiency of sourcing. Whether a claim may be stated as fact. Whether to declare a question unanswerable within budget — and it is expected to use this rather than produce a confident guess.

**Escalation rules.** → **Founder (E3)** when sources materially contradict each other on a decision-relevant point and no methodological ground chooses between them. This is a judgment, not a research failure. → **Objective Engine (E2)** when the answer requires spend beyond envelope. → **Andon (E4)** when it discovers a premise of the objective is false. *Research is the department most likely to pull the cord, and that is correct.*

**Characteristic failure.** A well-written, well-cited, wrong synthesis. Mitigated by contradiction surfacing and by the invariant that an unsourced claim is not renderable (VEDA 04 B5).

---

#### 4.2.2 · CREATIVE

**Mission.** Decide what should be said or made, and be able to defend why it is the right thing rather than a competent thing.

**Responsibilities.** Own the brief, the argument, the narrative, the copy, and the brand's voice in outbound artifacts. Own the concept before anything is produced. Own the standard of taste. Reject work that meets specification but misses intent.

**Inputs.** The objective's purpose and audience. Findings from Research. Brand and design constitution (VEDA 02). Prior creative decisions and their outcomes.

**Outputs.** An **Approved Brief** — versioned, immutable once issued, hash-addressable — containing the argument, the audience, the constraints, the success criteria, and the explicit non-goals. Downstream departments consume the version, never "the brief."

**Decision authority.** Message, argument, structure, tone, and taste. Absolute within its craft: no other department, and not the Objective Engine, may overrule a Creative rejection on craft grounds. Apple's single-taste-authority principle, applied honestly.

**Escalation rules.** → **Founder (E3)** when the right creative answer conflicts with a stated founder constraint, or when the work makes a claim about the company the founder has not made. → **Peer (E1)** when Production reports a brief is unrealizable within budget. → **Amendment (§9.3)** when it wishes to change an already-issued brief version — **it may never mutate an issued version**, because downstream work is bound to the hash.

**Characteristic failure.** Late-arriving taste. Addressed structurally, not culturally, in §9.

---

#### 4.2.3 · PRODUCTION

**Mission.** Turn approved intent into finished artifacts that are faithful to the brief and technically sound.

**Responsibilities.** Video, audio, image, document, deck, and their assembly. Technical specification — resolution, duration, format, colour, loudness, accessibility. Asset management and provenance: knowing which source produced which frame. Rendering, encoding, and the reproducibility of both.

**Inputs.** An Approved Brief at a named version. Assets and their licences. Technical specification. Budget and deadline.

**Outputs.** A **Deliverable**: the artifact, its specification conformance report, its complete asset provenance, and the brief version hash it was built against. That last field is what makes staleness mechanically detectable (§9.2).

**Decision authority.** Technique, tooling, production sequence, and technical acceptability. It may reject a brief as unrealizable within budget, with a stated alternative — a rejection without an alternative is escalated, not asserted.

**Escalation rules.** → **Peer (E1)** to Creative on realizability. → **Objective Engine (E2)** when rework from an upstream amendment exceeds its remaining envelope. → **Founder (E3)** for any licence or rights question with cost or exposure attached — this routes through Finance for the commitment, and Production does not resolve rights questions itself.

**Characteristic failure.** Perfect execution of a stale brief. This is the single most expensive failure in the system and §9 exists primarily to prevent it.

---

#### 4.2.4 · ENGINEERING

**Mission.** Build and change software that is correct, tested, reviewable, and maintainable by someone who was not present when it was written.

**Responsibilities.** Code, tests, review, refactoring, dependency and version control, technical documentation, and architectural consistency with the Constitution. Owns the judgment of when a change is too large to review safely.

**Inputs.** A specification with acceptance criteria. The existing codebase and its constraints. Findings where a technical fact is in question.

**Outputs.** A **Change**: the diff, its tests, its review record, its rollback procedure, and its declared reversibility class. **A change without a stated rollback procedure is not a valid output** — this is the department-level expression of Reversibility Registry fail-closed behaviour (VEDA 04 A2).

**Decision authority.** Implementation approach, decomposition, technical debt trade-offs within budget, and refusal of a change that cannot be made safely. Full authority to say a specification is technically incoherent.

**Escalation rules.** → **Objective Engine (E2)** when correct implementation exceeds the envelope. → **Founder (E3)** for any irreversible schema or data migration, always, with no exception and no standing rule — and for architectural decisions that constrain future options (these become ADRs). → **Andon (E4)** on discovering the change would break a constitutional invariant.

**Characteristic failure.** A change that passes its tests and violates an invariant no test encodes. Mitigated by Assurance's structural audit and by Verification's independence from the executing path.

---

#### 4.2.5 · OPERATIONS

**Mission.** Keep the real world and the machines in the state the founder believes they are in, and know immediately when they are not.

**Responsibilities.** Deployment, scheduling, environment and session health, monitoring, backups, file and workspace organization, third-party account state, and **per-domain freshness reporting**. Owns the runbook for every recurring operation.

**Inputs.** A Change ready to deploy, or a world-state intent. Health signals from every monitored domain. Maintenance windows and blackout periods.

**Outputs.** A **World-State Report**: what is running, at what version, since when, checked when, healthy or not — and, critically, **an explicit list of what it could not check.** This output feeds the Vigilance Attestation (VEDA 04 D7) and is therefore load-bearing for the product's most valuable sentence.

**Decision authority.** Deploy timing within the window. Rollback — **immediate, unilateral, no approval required, at any hour.** Resource allocation within budget. Declaring a domain unhealthy.

**Escalation rules.** → **Founder (E3)** before any irreversible operation: data deletion, account closure, DNS or billing change, anything with no compensating action. → **Andon (E4)** on any integrity threat, immediately, with a receipt written and no permission sought. → **Immediate (bypasses ranking)** — a Vigilance gap. **When Operations reports it could not check a domain, that report may not sit in a ranked queue.** It changes what Vedra is permitted to say at the next greeting, and a lie by omission there is, per VEDA 04 R6, the failure most likely to end the relationship permanently.

**Characteristic failure.** Silent partial coverage — a connector that fails quietly. This is why "what I could not check" is a mandatory output field rather than an error log.

---

#### 4.2.6 · FINANCE

**Mission.** Authorize, bound, and record every commitment that binds the company externally, so that no obligation is ever created that the founder did not knowingly accept.

**Responsibilities.** Spend authorization against standing rules and their cumulative limits. Vendor legitimacy. Contract and subscription obligations, including their renewal dates and their exit terms. Runway impact. Reconciliation of the spend ledger against the receipt ledger — continuously, not periodically (VEDA 04 R3).

**Inputs.** A proposed commitment with its terms. The standing rule set and current cumulative consumption. Budget envelopes and runway model.

**Outputs.** An **Authorization** or a **Refusal**, each with its reasoning; a ledger entry reconciled against receipts; and a runway delta. Every authorization names the rule it fired under, or names its absence.

**Decision authority.** **Veto over any committing action by any department** — this is the cross-cutting authority, and it is one-directional: Finance can stop a commitment, never compel one. Authorization within an active standing rule's per-instance *and* cumulative limits. Refusal on vendor legitimacy grounds.

**Escalation rules.** → **Founder (E3)** for every new vendor, every commitment above rule limits, every cumulative-cap breach (citing the cap explicitly), and **every irreversible payment without exception.** → **Immediate** on any suspected fraud or anomaly, bypassing ranking. → **Refusal is never silent**: a refused commitment is narrated in the next brief even when nothing was lost, because a partner that quietly declines things on your behalf is deciding for you.

**Characteristic failure.** Death by a thousand authorized cuts — many small approved spends summing past a threshold no single one crossed. This is exactly why VEDA 01 §10 makes a cumulative limit mandatory and why a per-instance cap alone renders a rule malformed at definition time.

---

#### 4.2.7 · CORRESPONDENCE

**Mission.** Carry the company's word to people outside it, consistently with everything the company has already said to them.

**Responsibilities.** Outbound email, replies, scheduling communications, public posts, and vendor and customer communication. Owns the **relationship record**: what we have told each party, when, and what we committed to. Owns channel, timing, and register for each relationship.

**Inputs.** An intent to communicate. The relationship history. Creative's voice standard for anything public-facing. Finance's authorization for anything that commits.

**Outputs.** A **Dispatch Record**: recipient, channel, content, the authorization it went out under, and the relationship-history delta. Nothing leaves without one.

**Decision authority.** Channel, timing, register, and recipient selection. **Refusal** — it may decline to send something that contradicts a prior statement to the same party, and this refusal is treated as a finding, not an obstruction.

**Escalation rules.** → **Founder (E3)** for **every first contact with a new party**, every public post, every message containing a commitment or a number, and every reply to a message the founder has read. **No standing rule may authorize an unreviewed first contact**, because a first impression has no compensating action. → **Peer (E1)** to Creative on voice, to Finance on anything committing.

**Characteristic failure.** Contradicting a prior statement to the same party. The relationship record exists specifically to make this mechanically detectable rather than remembered.

**A note on reversibility.** Correspondence holds the system's largest gap between *technically undoable* and *actually undone*. A recall, a correction, an apology — none of these restore the prior state. **Correspondence classifies every send as irreversible regardless of platform features**, and the Reversibility Registry must not be permitted a "reversible-until-T" entry for outbound human contact. This is a deliberate pessimism, per VEDA 04 R2: classify pessimistically, upgrade only on evidence of a working compensating action, and there is no such action here.

---

### 4.3 Quality ownership and sign-off

**The question:** should QA be central, distributed, or hybrid?

**Recommendation: hybrid, split along a specific line — craft judgment distributed, mechanism central, process audit central and thin.** The defence follows.

#### Why not central

A central QA department must judge colour grading, Python correctness, vendor legitimacy, and whether an email contradicts something said in March. There is no reasoner competent in all four, so a central QA is either shallow in every domain or a permanent serialized queue in front of every completion — the bottleneck reintroduced one layer down, with the added property that it is now the *last* layer, where fixes are most expensive.

It also fails T1: it has no standard of correctness of its own. It would be borrowing each department's standard while holding the authority to apply it, which is the worst available arrangement — accountability without competence.

Toyota settled this in the 1950s and the finding has not weakened: **inspection at the end finds defects late and teaches the station nothing.** Jidoka builds quality at the station, because the station is the only place that knows what good looks like while the work is still cheap to change.

#### Why not fully distributed

Fully distributed means the party that produced the work is the sole party that certifies it. That fails separation of duty, and it makes VEDA 01 §10 Ethics 2 — never withhold information to preserve confidence in yourself — a matter of good intentions rather than structure.

It also leaves nobody accountable for the *composition*. Seven perfect departmental outputs can compose into a wrong objective: a technically flawless video making a claim Research never verified, delivered on time and on budget, with every department correct in isolation.

#### The hybrid, precisely

Quality has three separable components. They have different owners because they are different questions.

| Component | Question | Owner | Nature |
|---|---|---|---|
| **Craft quality** | Is this good work of its kind? | **The owning Department Head, distributed** | Judgment. Irreducible. Built at the station. |
| **Outcome verification** | Does the real world match the Expected Outcome? | **Verification Subsystem, central** | Mechanical. Structurally independent of execution (Constitution §10.3). |
| **Process assurance** | Was it done properly, and can we prove it? | **Assurance function, central and thin** | Audit. Never judges craft. |

**Assurance's scope is deliberately narrow, and it never touches craft.** It checks only: did every action write its intent receipt before executing; did every task name an Expected Outcome; is Evidence attached and bound to the claim; did a Head other than the producing Lead sign off; are all consumed brief and artifact versions current rather than stale; is every consumed Capability classified in the Reversibility Registry. **Assurance can fail an objective for a missing receipt. It can never fail one for an ugly video.** That boundary is what keeps it thin enough to be fast and honest enough to be trusted.

#### Who signs off before completion — the go/no-go poll

Completion requires a unanimous poll. NASA's structure, adopted directly:

```
        Objective Engine calls the poll
                    │
    ┌───────────┬───┴────┬───────────┬──────────────┐
    ▼           ▼        ▼           ▼              ▼
 Research    Creative  Production  ... each        Verification
   Head        Head       Head     contributing      (Evidence
    │           │          │       Head              matched?)
    └───────────┴──────────┴──────────┬──────────────┘
                                      │              Assurance
                    GO / NO-GO        │              (process
                                      ▼               complete?)
                         Any single NO-GO blocks completion.
                         The Engine declares. It does not vote.
```

**Invariants:**
- **A department votes only on its own contribution.** No department votes on another's craft.
- **The Objective Engine cannot manufacture a GO.** It counts. If a Head is unavailable or times out, the objective does not complete — it escalates as a stalled poll. Absence is never assent.
- **A NO-GO must state its remedy or its impossibility.** A bare refusal is escalated as a conflict (§9), not accepted as a verdict.
- **The founder does not sign off on deliverables.** The founder approves the *acceptance criteria at admission* and receives the completion receipt. Requiring per-artifact founder sign-off would rebuild the approval treadmill the product exists to abolish, and would put the position of the line — the actual product metric — in permanent reverse.

---

## 5 · Objective Lifecycle

### 5.1 The eight phases

```
  ADMISSION → DECOMPOSITION → CONTRACTING → EXECUTION → INTEGRATION
                                                            │
                                      COMPLETION POLL ◄─────┘
                                             │
                                      DELIVERY → LEARNING
```

Only Admission and Delivery touch the founder in the normal case. Everything between is silent unless something crosses an escalation trigger — VEDA 01's silent guardian, expressed as a control-flow property rather than as a promise.

### 5.2 Phase definitions

**1 · Admission.** The Objective Engine receives a stated intention from Vedra. It establishes: what "done" means in checkable terms, the budget, the deadline, the reversibility class of the objective as a whole, and the departments likely to participate. It then does the thing that most determines whether the rest goes well — **it refuses the objective if "done" cannot be stated checkably.** An objective admitted with a vague completion criterion produces a completion poll nobody can vote in.

The founder approves the acceptance criteria and the envelope. This is the **one approval per objective** (Constitution §15.3), and everything downstream relays that grant rather than re-asking.

**2 · Decomposition.** The Engine decomposes into **department-level outcomes**, never into tasks. It reasons over seven outcomes, not five hundred skills — this is Constraint A resolved. Each outcome names a department, a deliverable, an acceptance criterion, a budget slice, a deadline, and its dependencies on other departments' outcomes.

**Invariant:** the Objective Engine never names a skill or a capability. If it does, it has taken a craft decision it is not competent to take, and it has re-acquired the surface it was supposed to shed.

**3 · Contracting.** Each department receives its outcome and either accepts, accepts-with-conditions, or refuses with a stated alternative. A department that accepts is bound to its acceptance criterion and its envelope. Departments with no dependency between them contract in parallel; there is no ordering requirement here.

Contract acceptance creates a Mission Lead if §2.5's condition is met.

**4 · Execution.** Departments work concurrently, gated only by declared dependencies. Within a department: the Lead sequences skills, skills compose Capabilities, Capabilities run through the Operator's single execution path, every action writes its receipt intent first, and Verification observes independently.

**Nothing in this phase routes through the Objective Engine.** It is not notified per task. It receives events; it does not mediate them.

**5 · Integration.** Where one department's output feeds another's input, the handoff is a versioned, hash-addressed Commitment (§9.1). The consuming department records the version it consumed. This record is what makes staleness mechanical rather than diplomatic.

**6 · Completion poll.** §4.3.

**7 · Delivery.** The Objective Engine declares completion. Vedra narrates it — headline first, the work collapsed to one line and a receipt (VEDA 04 D6). The founder sees an outcome, not a project history, unless they ask.

**8 · Learning.** §5.6. Three loops, three owners, none of which self-enact.

### 5.3 Worked example — *"Prepare a 5-minute Vedra product video."*

Timings are illustrative of shape, not of performance.

```
T+0   FOUNDER  "Prepare a 5-minute Vedra product video."
         │
      VEDRA    Receives. Does not plan. Passes structured intent to the Engine.
         │
T+2s  OBJECTIVE ENGINE — ADMISSION
         │  Asks itself: what is "done"? Not "a video exists" — that is not
         │  checkable against intent. Proposes: a 5:00 ±0:15 artifact at
         │  1080p/H.264, making the three claims in the positioning document,
         │  every factual claim sourced, brand-conformant per VEDA 02,
         │  delivered to the exports folder.
         │  Reversibility: the artifact is reversible; publication would not
         │  be — so publication is explicitly OUT of this objective's scope.
         │  Budget: 8 provider-hours, ₹X external assets. Deadline: 5 days.
         │
      VEDRA    Presents criteria + envelope in one screen. One decision.
      FOUNDER  Approves.  ◄── the only approval in the normal path
         │
T+1m  DECOMPOSITION — five department outcomes, not fifty tasks
         │
         ├─ RESEARCH      → verified claim set with sources        (no deps)
         ├─ CREATIVE      → approved brief + script                (needs Research)
         ├─ PRODUCTION    → rendered artifact to spec              (needs Creative)
         ├─ OPERATIONS    → assets staged, workspace, delivery     (no deps)
         └─ FINANCE       → asset licence authorization            (needs Production spec)
         │
         │  Note what is absent: Correspondence and Engineering are not
         │  contracted, because nothing leaves the company and no code changes.
         │  A department not needed is not consulted. This is why the roster
         │  being seven costs nothing on a three-department objective.
         │
T+2m  CONTRACTING
         │  Research accepts.  Operations accepts.
         │  Creative accepts-with-condition: "script cannot be final before
         │     the claim set is; my clock starts at Research handoff."
         │  Production accepts-with-condition: "5:00 at this scope needs a
         │     locked script; I will not start animation on a draft."
         │       ◄── Production has just pre-empted the §9 conflict, correctly,
         │           at contracting time when it is free.
         │  Finance defers: no commitment exists yet to authorize.
         │
T+2m  EXECUTION begins — Research and Operations run concurrently
         │
      RESEARCH (Mission Lead created: 3 skills)
         │  Skills: Source Gathering · Claim Verification · Contradiction Check
         │  Each skill asks the BROKER which Provider serves it. Research does
         │  not choose a model. Each Capability writes receipt intent first.
         │  ► Finding: claim 2 ("40% faster") traces to an internal benchmark
         │    that is 9 months old and was run on different hardware.
         │  ► Research does not quietly drop it, and does not quietly keep it.
         │    It raises E3: novel + affects a public-facing claim.
         │
T+40m JUDGMENT REQUEST reaches the queue — not the Engine
         │  Consequence quartet, mandatory, or the request cannot be emitted:
         │    what changes  — the video makes a performance claim
         │    what it costs — 2h to re-benchmark, or 0 to drop the claim
         │    if you do nothing — DEFAULT: the claim is dropped, at T+4h
         │    reversible?    — yes, until render
         │  Ranked against everything else open. Vedra surfaces one line.
      FOUNDER  "Drop it."
         │  Silence timer cancelled. Receipt written. Provenance stored.
         │  Fed to the Rule Proposal Miner — a pattern may be forming here.
         │
T+45m CREATIVE  Mission Lead created (script + structure + copy)
         │  Consumes Finding v1 (hash 7c3a…). Issues APPROVED BRIEF v1, hash 9f21…
         │  Brief is immutable. Production is notified of a version, not a file.
         │
T+3h  PRODUCTION  Mission Lead created (storyboard · animate · voice · edit · grade)
         │  Records: built against brief 9f21…
         │  ► Needs a licensed music track. Raises a commitment.
         │
      FINANCE  Evaluates. New vendor → no standing rule can cover it.
         │  E3 to founder. Approved. Ledger entry, reconciled against receipt.
         │
T+2d  ══ THE CONFLICT ══  Creative wants a stronger opening line. See §9.4.
         │
T+4d  INTEGRATION  Production delivers, recording brief version 9f21… — which
         │  is now current again after the amendment resolved. Not stale.
         │  Operations stages the artifact and reports the workspace state.
         │
T+4d  COMPLETION POLL
         │  Research      GO   — claims sourced, dropped claim recorded
         │  Creative      GO   — brief realized, voice conformant
         │  Production    GO   — 4:58, spec conformant, provenance complete
         │  Operations    GO   — delivered, checksummed, backed up
         │  Finance       GO   — one commitment, authorized, reconciled
         │  Verification  GO   — Observation matches Expected Outcome
         │  Assurance     GO   — receipts complete, no stale versions consumed,
         │                       every sign-off by a Head, not a Lead
         │  ► Unanimous. The Engine declares. It cast no vote.
         │
T+4d  DELIVERY
      VEDRA  "The product video is done — four fifty-eight, in exports.
              I dropped the speed claim; the benchmark behind it was nine
              months old on different hardware. One licence, ₹X, on file."
         │  Headline first. Work collapsed to one line and a receipt.
         │
T+4d  LEARNING — three loops, three owners, none self-enacting
         L1  Production: this render pipeline at this spec, 2.1× estimate.
             Skill's estimator updated. Department-owned.
         L2  Broker: provider P outperformed on `vision.ocr` for storyboards.
             Benchmark store updated. Shared.
         L3  Boundary: this is the third stale-internal-benchmark drop in
             two months. Miner proposes a rule — "flag any claim resting on
             a benchmark older than 6 months" — with evidence, including the
             one counter-example where the founder kept the claim.
             ► PROPOSED. NOT ENACTED. Eng. Law V.
```

### 5.4 What the founder actually experienced

Two touches. One approval at admission, one judgment mid-flight, one narrated outcome. Five departments, four Mission Leads, roughly thirty skill invocations, and a cross-department conflict resolved without them.

That ratio is the product. It is also the metric: not tasks completed, but *judgments required per objective*, trending down.

### 5.5 Where the Objective Engine actually appeared

Four times: admission, decomposition, one scope arbitration (§9.4), and counting the poll. Zero times per task, per tool call, or per utterance. **On a hundred concurrent objectives, that is four hundred touches over days, not four hundred thousand.**

### 5.6 Learning — three loops, not one layer

The brief places Learning at the bottom of the chain. It is not one thing, and it does not sit anywhere in particular. It is three loops with different owners, different cadences, and different evidence:

| Loop | Learns | Owner | Cadence | Enacts? |
|---|---|---|---|---|
| **L1 · Skill** | What works within one craft — estimates, technique, failure patterns | The owning department | Per objective | Yes, within the skill's own definition. Never across departments. |
| **L2 · Provider** | Which Provider serves which AI Capability well, at what cost | AI Capability Broker (§5.7, ADR-0018) | Continuous | Yes, within the Broker's already-ratified decision authority. |
| **L3 · Boundary** | Which decisions the founder makes consistently enough to delegate | Rule Proposal Miner (VEDA 04 C3) | Continuous, surfaced on evidence | **Never.** Proposes only. Eng. Law V. |

**The invariant that matters:** L1 and L2 improve *how well the system does what it is already permitted to do.* Only L3 touches *what it is permitted to do*, and L3 cannot enact. **No department may move the line by getting good at its job.** Competence is never converted into authority automatically — that conversion is a founder act, always, and it is the mechanism VEDA 01 §10 calls "autonomy is lent, never earned in a way that makes it permanent."

---

## 6 · Escalation Model

### 6.1 The governing principle

> **Escalation is routed by the class of the decision, never by the seniority of whoever noticed it.**

This is the central anti-pattern of human organizations and it must not be inherited. In a company, a problem travels up until it meets someone senior enough to decide, which means the route depends on who happened to find it. Here, the route is a property of the decision itself: an irreversible action escalates to the founder whether a Skill, a Lead, a Head, or the Objective Engine encountered it, and no amount of departmental seniority substitutes.

### 6.2 The five tiers

| Tier | Name | Trigger | Who decides | Receipt | Founder sees it |
|---|---|---|---|---|---|
| **E0** | **Auto** | Within department envelope · reversible · classified · covered by an active rule with cumulative headroom | The department | Intent + outcome | Collapsed into the brief's summary line |
| **E1** | **Peer** | Cross-department, within both envelopes, no scope change | The two Heads, jointly | Both Heads named | One line in the brief |
| **E2** | **Contract** | Scope, budget, deadline, or dependency change within the objective's approved envelope | Objective Engine | Engine + affected Heads | One line in the brief |
| **E3** | **Judgment** | **Novel · Irreversible · Excluded by rule** — VEDA 04 B3's three triggers, unchanged and not extended | **The founder** | Full quartet + provenance | Ranked judgment request, one at a time |
| **E4** | **Halt** | Wrong thing being built · integrity threat · false premise · constitutional violation | **Anyone.** No permission. No penalty. | Halt receipt naming the puller | Immediately, outside ranking |

**E3's triggers are copied deliberately, not re-derived.** They are already the Escalation Router's classification (VEDA 04 B3). Introducing a departmental escalation vocabulary alongside them would create two answers to "why did this reach me," and the founder would have to learn both.

### 6.3 Hard invariants

1. **Irreversible never batches.** No E0, E1, or E2 path can carry an irreversible action, regardless of value, volume, or how routine it has become. VEDA 04 B3's invariant, restated because the department layer is exactly where it would erode.
2. **Every open request carries a default and a firing time.** No exception for department-raised requests. An item that can sit indefinitely is a defect (VEDA 04 B4).
3. **Defaults are re-verified before firing.** Facts move during an objective. A default computed at T+40m and fired at T+4h is re-checked against current state, and re-escalates if it has changed. Firing a stale default is a trust-ending event.
4. **No department has a fast lane.** Departments cannot mark their own requests urgent. Ranking is central, explainable, and not for sale. The two exceptions are structural rather than discretionary: a **Vigilance gap** from Operations (it changes what Vedra may say, so it precedes the greeting) and a **suspected-fraud signal** from Finance. Neither is a priority flag a department can set at will; both are specific conditions with specific handlers.
5. **A department may not escalate to avoid deciding.** An E3 raised on a matter within a Head's own craft authority is returned by the Judgment service, not forwarded. Otherwise the founder becomes the fallback for departmental indecision, which is the treadmill rebuilt through the back door.
6. **Escalation never bypasses Vedra.** Every tier's founder-facing output is composed by the single voice. §3.4.

### 6.4 The andon cord

Any participant — Skill, Lead, Head, Engine, or founder — may halt an objective at any moment, without permission, without a confirmation dialogue, and without penalty.

**What a halt does:** stops new work on *that objective*, preserves all state, writes a receipt naming who pulled and why, and raises an E3 with the halt already in effect. **What it does not do:** stop the system. The founder's override (VEDA 04 A3) does that, and it belongs to the founder alone.

**Why it must be free.** Toyota's finding is that a cord anyone hesitates to pull is a cord that does not exist. If pulling one counts against a department in any metric anywhere, it will stop being pulled, and the system will finish building wrong things efficiently. **A halt is therefore never an input to any quality or performance measure of the department that pulled it.** If a future metric would make halting look bad, the metric is wrong.

---

## 7 · Skill Ownership Model

### 7.1 What a Skill is — and the collision it must not create

The Constitution freezes **Capability** as "the named unit of what can be done that a Step references, resolved to a Worker at execution time." §17 forbids a frozen term acquiring a third synonym. "Skill" is one careless sentence away from becoming exactly that.

> **A Skill is a named, department-owned composition of one or more Capabilities, together with the standard of correctness for their use. A Skill knows *when* to act and *how well* the result must be. A Capability knows *what runs*. A Skill is never itself dispatchable.**

The distinction is enforceable, not merely stated:

| | Capability | Skill |
|---|---|---|
| Layer | Operator (§4, §12) | Brain-side judgment |
| Nature | Atomic and executable | Compositional and judgmental |
| Owner | Registered by a Worker | Exactly one department |
| Names | `Filesystem.ReadFile` — `PascalCase.PascalCase` | `Claim Verification` — prose |
| Dispatchable | Yes | **No** — it expands to Capability calls |
| Contains | Parameters, risk tier, permission category | Composition, standard of done, escalation triggers, estimator |

**Invariant:** a Skill that composes exactly one Capability and adds no standard of correctness is not a Skill. It is a Capability with a nickname, and it must be deleted. This rule is what prevents 500 Capabilities from silently becoming 500 redundant Skills.

### 7.2 The ownership rules

**Rule 1 — Exactly one owner.** Every Skill belongs to exactly one department. No shared ownership, no matrix, no committee. This mirrors §16's discipline: a component with two homes eventually has two definitions of done.

**Rule 2 — Ownership follows the standard of correctness, never the tool.** Creative and Engineering both use a reasoning Provider; that does not make the Provider anyone's property, and it does not co-locate their skills. What determines the owner is *whose judgment decides the output is good.*

**Rule 3 — The contested-skill heuristic.** When two departments both claim a skill, ask: **when this output is wrong, whose reputation is damaged?** That department owns it. This resolves nearly every real case, and it resolves them correctly, because reputation tracks accountability.

**Rule 4 — Borrowing is explicit and carries the owner's standard.** A department may invoke another's Skill through a stated contract. The owner's standard of correctness travels with it. Engineering borrowing Creative's `Write Copy` for a README gets Creative's voice standard applied — it does not get a lower bar because the context is technical.

**Rule 5 — Owner defines, borrowers request.** Only the owner may change a Skill's definition, standard, or composition. A borrower with a need files a request, never a fork. Forking a skill to escape its standard is the single most likely way this model rots, and it must be treated as a defect, not a workaround.

**Rule 6 — No unowned skills.** A Capability set with no owning department is not invocable. Fails closed, in the same spirit as the Reversibility Registry (VEDA 04 A2). An orphan skill is a skill nobody will judge.

### 7.3 Ownership at a glance

| Skill (illustrative) | Department | Because |
|---|---|---|
| Source Gathering, Claim Verification, Contradiction Check, Freshness Audit | **Research** | Wrong ⇒ we believed something false |
| Script Writing, Copywriting, Concept Development, Brand Voice Review | **Creative** | Wrong ⇒ we said the wrong thing |
| Video Editing, Animation, Colour Grading, Voice Synthesis, Deck Assembly, Document Layout | **Production** | Wrong ⇒ the artifact is defective |
| Code Authoring, Test Writing, Code Review, Refactoring, Git Operations, Dependency Management | **Engineering** | Wrong ⇒ the software is broken |
| Deployment, Backup, Monitoring, File Organization, Scheduling, Environment Provisioning, Health Probing | **Operations** | Wrong ⇒ the world is not as believed |
| Spend Authorization, Vendor Assessment, Contract Review, Runway Modelling, Ledger Reconciliation | **Finance** | Wrong ⇒ we are bound to something we should not be |
| Email Composition, Reply Drafting, Relationship History Check, Publication | **Correspondence** | Wrong ⇒ we damaged a relationship |

**Two deliberately instructive placements:**

*Git Operations → Engineering, not Operations.* Version control is a property of the codebase, and the standard for a good commit — atomic, reviewable, revertible — is Engineering's. But **deploying** what git contains is Operations'. The seam is between the artifact and the running world, and it is the same seam that separates the two departments everywhere else.

*Publication → Correspondence, not Production or Creative.* Production makes the artifact; Creative approves the message; **Correspondence decides it leaves the building.** Publication is irreversible outbound contact, and it belongs with the department that holds the relationship record and treats every send as irreversible. If publication lived with Production, the party most invested in the artifact existing would be the party deciding it goes out.

### 7.4 Where the registry lives — and why not a new one

**Do not build a Skill Registry.** Constitution §5.1 establishes one Capability Registry with two indices, because one registry means one answer regardless of who asks. A parallel Skill Registry would be a second catalogue of what the system can do, and the two would drift.

**Add a third index to the existing registry: `Capability → owning department`.** Skill definitions are records in the same registry, marked non-dispatchable. One catalogue, three indices, one answer.

---

## 8 · Tool Ownership Model

### 8.1 The rule, and the four prohibitions behind it

> **Departments never call tools. Skills compose Capabilities. Capabilities are executed by Workers through the Operator. Tools are owned by nobody.**

```
   Department  ──owns──►  Skill  ──composes──►  Capability
       │                    │                       │
   defines the        declares an AI          registered by a
   standard of        Capability NEED         Worker, classified
   correctness        (never a Provider)      for reversibility
                            │                       │
                            ▼                       ▼
                    ┌──────────────┐        ┌────────────────┐
                    │ AI CAPABILITY│        │   OPERATOR      │
                    │   BROKER     │        │ Worker Runtime  │
                    │ DECIDES which│        │ Environment     │
                    │  Provider    │        │ Session         │
                    └──────────────┘        └────────────────┘
```

**Prohibition 1 — no department may select a Provider.** Constitution §5.7 is categorical: every component needing AI asks the Broker which Provider, and **no other component may decide.** A department choosing its own model would fragment the Broker's singular spend ledger, its benchmark store, and its approval policy across seven owners — the exact fragmentation §5.2 and §5.7 exist to prevent.

Skills therefore declare an **AI Capability need** (`reasoning`, `vision.ocr`, `speech.transcribe` — lowercase.dotted, per §17) and never a Provider name. This is mechanically checkable: a department-side artifact containing a `PascalCase.PascalCase` Provider name or a model identifier is a boundary violation detectable by lint.

**Prohibition 2 — no department may introduce a tool.** New Capabilities arrive only through the Worker Runtime, only registered, and only classified in the Reversibility Registry. Unclassified means non-executable, fails closed (VEDA 04 A2). A department that could add a tool could add an unclassified one under deadline pressure, which is precisely how the registry stops being trustworthy.

**Prohibition 3 — no department holds a Permission grant.** Grants live in the Permission System (§5.2), single and Mission-wide, so one approval satisfies every department in an objective without any of them holding it. Relay, never re-issue (ADR-0005/0006).

**Prohibition 4 — no department touches an Environment.** Environment Sessions belong to the Operator Instance that opened them (§5.8). A department reaching a live session would be reaching into another component's connection.

### 8.2 What departments do own about tools

Not the tools. Three things about their use:

1. **Composition** — which Capabilities, in what order, form a Skill.
2. **Standard** — what "correctly used" means for their craft.
3. **Constraint declaration** — privacy sensitivity, quality floor, latency tolerance, cost ceiling. These are *inputs to the Broker's hard-constraint filter*, not selections. A department saying "this must stay local" is stating a constraint; the Broker still chooses which local Provider.

Constitution §3.3's four routing criteria are unchanged, and criterion 4 — explicit user preference always wins — is honoured among candidates surviving the Broker's filter, exactly as Amendment 2 states.

### 8.3 Reversibility composes pessimistically

A gap worth naming, because it is invisible at the single-action level:

**An objective's reversibility class is the worst class among its constituent actions, not the average and not the modal.** Rendering a video is reversible. Publishing it is not. An objective containing both is irreversible, and it may not be authorized by any standing rule at any tier.

Stronger still: **actions individually reversible can compose into an irreversible outcome.** Publishing an artifact containing an unverified claim is, mechanically, a reversible file operation and a reversible upload. The composed consequence — a false public statement — has no compensating action. **The Reversibility Registry must therefore be consulted at the objective level and at the handoff level, not only per action.** Classification is a property of consequence, not of file operations, and this is where a department architecture is most likely to lose sight of that.

---

## 9 · Conflict Resolution

### 9.1 Handoffs are Commitments, not messages

The single design decision that makes conflict tractable:

> **Every inter-department handoff is a versioned, immutable, hash-addressed Commitment. The consuming department records the exact version it consumed.**

Production never animates "the script." It animates **brief v1, hash 9f21…**, and its Deliverable records that hash. Once issued, a version is never mutated — not for a typo, not for a small improvement, not under deadline pressure. Improvements are new versions.

**This converts every downstream-invalidation question from a conversation into a lookup.** Who is affected by a change to brief v1 is not something anyone has to remember, ask about, or discover during the completion poll.

### 9.2 Staleness is mechanical and fails closed

When a Commitment is superseded, every artifact recording the prior hash is marked **stale**, automatically, transitively through the dependency graph.

**Invariant:** a stale artifact cannot be delivered, cannot pass the completion poll, and cannot be consumed by a further handoff. This is Assurance's check, and it is why Assurance can fail an objective on a version mismatch without knowing anything about video.

Fail-closed, in the spirit of VEDA 04 A2. **Staleness is never a warning.** A warning is something a system under deadline pressure learns to route around, and the failure it prevents — perfect execution of a superseded brief — is the most expensive one available.

### 9.3 An amendment is a decision, not a task

When Creative wants to change an issued brief, it does not edit anything and does not message Production. It files an **Amendment Request** against the objective.

The Objective Engine — the only holder of the objective contract, therefore the only party with standing — computes the **impact**, but does not decide the trade-off:

| Quartet field | Computed how |
|---|---|
| What changes | Traverse the dependency graph from the superseded hash. Enumerate every stale artifact. |
| What it costs | Sum the affected departments' re-execution estimates and any new commitment. |
| What happens if you do nothing | The current version ships. State plainly what that means in the founder's terms. |
| Can it be undone | Yes until the objective's first irreversible action. After that, no. |

**The reconciliation owner is the Objective Engine. The decision owner depends on the impact.** Those are two different roles and conflating them is how a coordinator quietly becomes a censor.

### 9.4 The authority ladder — worked, using the brief's own scenario

*Creative wants to change the script after Production has animated.*

```
  A1 · WITHIN BOTH ENVELOPES  (rework fits Production's remaining budget,
       no deadline risk, no new commitment)
       → E1. The two Heads settle it. Production's Head has the deciding
         voice on feasibility; Creative's on whether the change is worth
         making at all. Receipt written naming both. One line in the brief.
       → Founder is informed, not consulted.

  A2 · EXCEEDS AN ENVELOPE, WITHIN THE OBJECTIVE
       → E2. The Objective Engine reallocates from the objective's reserve
         or from another department's unspent slice. It decides this because
         it holds the contract and the budget — that IS its authority.
       → Founder informed.

  A3 · EXCEEDS THE OBJECTIVE, OR CROSSES AN IRREVERSIBILITY LINE
       (needs more money, misses the deadline, or the old version has
        already been published)
       → E3. Founder judgment, with the full quartet and a silence default.
       → No department and no Engine may absorb this quietly. Absorbing it
         is deciding on the founder's behalf, and it is the failure mode
         VEDA 01 §10 Ethics 4 names — optimising for its own smooth running.

  A4 · THE TWO HEADS DISAGREE ON CRAFT
       ("this change is essential" vs "this change is not worth the rework")
       → The Objective Engine does NOT break the tie. It escalates.
       → Reason, stated plainly: a craft dispute settled by a non-craft
         authority is how quality dies in every organization that has ever
         tried it. The Engine has no standard of correctness for video or
         for argument. Arbitrating between two competent authorities on a
         question it cannot evaluate is not neutrality — it is a coin flip
         wearing a suit.
       → What the Engine DOES do: compute the impact, state both positions
         in their own terms, and hand the founder a decision rather than a
         dispute. That is the one thing it is uniquely able to do.

  A5 · THE CHANGE MEANS THE OBJECTIVE WAS MISCONCEIVED
       → E4. Andon. Halt, preserve, receipt, escalate with the halt in
         effect. Better to stop at 80% than to deliver the wrong video.
```

**In the §5.3 timeline, T+2d was A1**: the rework fit Production's remaining budget, both Heads agreed, a receipt was written, brief v2 was issued, v1's derivatives went stale, Production rebuilt against v2, and the founder read one line about it in the next brief. Total founder involvement: reading one sentence, after the fact.

### 9.5 Prevention beats resolution — three structural preventions

Conflict resolution machinery that is *invoked often* is a design failure, not a feature. Three mechanisms reduce the frequency:

1. **Contract-time pre-emption.** In §5.3, Production accepted with the condition "I will not start animation on a draft." That condition was free at T+2m and would have cost two days at T+2d. **A department is expected to state its stability requirements at contracting**, and a department that habitually does not is generating avoidable conflict.
2. **Explicit lock points.** Each Commitment declares when it locks. After the lock, changes are amendments with computed impact. Before it, they are free. Making the transition visible and dated stops "one more small change" from being a permanently available option.
3. **The andon cord, used early.** Halting at 20% costs a fifth of halting at 80%. This only holds if pulling is genuinely free (§6.4) — which is why the no-penalty rule is load-bearing rather than decorative.

---

## 10 · Risks

Ordered by severity. Each names its mitigation and, where the mitigation is imperfect, says so.

**R1 · The hierarchy becomes latency.** *Severity: high.* Seven levels between intent and action is seven serialization points, and VEDA 04's latency budgets have no slack. A "read me that file" objective routed through admission, decomposition, contracting, a Lead, and a poll is a product that feels slow at the exact moments where speed signals competence.
*Mitigation:* lazy Mission Leads (§2.5); direct Head→Skill for single-skill contributions; a **fast path for single-department, read-only, single-skill objectives that skips decomposition, contracting, and the poll entirely.** *Honest residual:* the fast path is a second control path, and second paths are where invariants get skipped. It must be built as a *shorter walk through the same gates*, never as a bypass — and Assurance must audit fast-path objectives at the same rate as the rest, not at a reduced one.

**R2 · Departments accumulate private state.** *Severity: high.* The classic org failure, and here it would be a constitutional violation: multiple Operator Instances disagreeing about approvals is exactly what §5.2 and §5.3 exist to prevent.
*Mitigation:* **departments are policy, not storage.** A department owns definitions and standards; it owns no state. Every fact it uses lives in Shared Infrastructure. A department-scoped store is a build-breaking defect, not a code review comment.

**R3 · Department Heads become shadow planners.** *Severity: high.* A Head with planning authority over its craft will, under pressure, start planning slightly outside it — adding a step "while we're here," reinterpreting an acceptance criterion generously. Scope creep, at seven sites simultaneously.
*Mitigation:* contracts are outcome-bounded with a budget; exceeding either requires an amendment with computed impact. The Engine never names skills (so it cannot micromanage), and Heads never change acceptance criteria (so they cannot self-authorize). Assurance audits delivered-versus-contracted scope.

**R4 · Organizational metaphor imports organizational pathology.** *Severity: high, cultural, permanent.* The metaphor is a genuine asset and a genuine hazard. Human departments grow, defend budgets, resist merging, and treat headcount as status. There is no reason the failure modes should not translate along with the useful parts.
*Mitigation:* the admission test (§2.1) written down; the merge rule made explicit; department changes requiring founder ratification; and an explicit prohibition on **department count, skill count, or task throughput** appearing in any success metric. *Honest residual:* this is a discipline, not a mechanism, and disciplines erode. The single best defence is that the roster's size is itself reviewable at the annual dependency audit.

**R5 · Seven voices.** *Severity: high.* Every department will, sooner or later, have something it believes the founder must know now. Each case will be individually reasonable. Collectively they rebuild the notification storm the product exists to abolish.
*Mitigation:* the CAPCOM rule enforced structurally, not by policy — departments hold no reference to any surfacing interface (§3.4). They can raise a request; they cannot raise their voice. The two structural exceptions (Vigilance gap, fraud signal) are specific conditions with specific handlers, not priority flags anyone can set.

**R6 · Distributed quality becomes optional quality.** *Severity: high.* If each department judges its own craft, a department under deadline pressure grades itself generously — and the pressure arrives at all seven simultaneously, because they share a deadline.
*Mitigation:* the poll fails closed and absence is never assent (§4.3); Verification is mechanically independent of the executing path (§10.3); Assurance audits that sign-offs came from a Head and not the producing Lead; and the Self-Audit (VEDA 04 C5) covers department sign-offs, meaning the system surfaces its own generous grading before anyone finds it.

**R7 · Terminology collision with shipped code.** *Severity: high, and immediate.* `Objective` and `Mission` both exist and both mean "one complete intent-to-outcome unit." `Mission` is frozen (§17); `Objective` is live in `mission_control/tasks.py`. This document adds Department, Skill, and Mission Lead on top of that ambiguity.
*Mitigation:* §0.4's resolutions for Skill and Mission Lead can be adopted directly. The Objective/Mission collision **cannot be resolved by this document** — §17 is frozen and amendment requires an ADR plus founder ratification. Two options:
  - **(a)** `Objective` becomes the founder-facing name and `Mission` is retired as a duplicate. Cleanest conceptually; touches a frozen term and a large amount of shipped code.
  - **(b)** `Objective` is declared the founder-facing synonym of the frozen `Mission`, with `Mission` remaining canonical in the state machine — precedent: Amendment 1's treatment of Executive/Worker, which is an exact structural parallel.
  **Recommendation: (b).** It follows established precedent, needs no code renaming, and §17 already demonstrates the pattern for exactly this situation. Requires an ADR.

**R8 · Composed irreversibility.** *Severity: high, and easy to miss.* Every action reversible, the composition not. The publish-an-unverified-claim case in §8.3.
*Mitigation:* reversibility evaluated at objective and handoff level, not only per action; objective class is the worst of its parts; Correspondence classifies all outbound contact as irreversible regardless of platform undo features. *Honest residual:* this requires the Reversibility Registry to reason about *consequence*, not just operation, and VEDA 04 A2 does not currently specify that. **This is a genuine extension request against a Layer A component and should be raised as one.**

**R9 · The completion poll deadlocks.** *Severity: medium.* Seven votes, any one blocking, a department that cannot decide, and an objective that never finishes and never fails.
*Mitigation:* every poll carries a deadline and a **declared default on silence** — the same B4 machinery as every other open request, which here defaults to **no-go**, never to go. A stalled poll escalates as E3 with the specific non-voting department named. **The default must be no-go**; a poll that completes on timeout is not a poll.

**R10 · The fast path becomes the normal path.** *Severity: medium, insidious.* R1's mitigation, misused. If the fast path is faster and simpler, pressure accumulates to widen its eligibility until most objectives qualify and the department structure is ceremonial.
*Mitigation:* fast-path eligibility is a fixed predicate — single department, single skill, read-only, no commitment — that is not configurable at runtime; widening it requires ratification. Assurance reports the fast-path ratio in the brief, so drift is visible rather than gradual.

**R11 · Learning attributed to the wrong loop.** *Severity: medium.* If L1 (skill improvement) can quietly widen what a department does without asking, the line moves without a founder act — which is the constitutional failure this whole architecture exists to prevent.
*Mitigation:* L1's write scope is confined to a Skill's own composition and estimates; anything touching authority routes to L3, which cannot enact. Enforceable by inspecting what each loop is permitted to write.

**R12 · Measuring the wrong thing.** *Severity: low technically, terminal culturally.* VEDA 01 §12's warning, in departmental form: departments completed, tasks dispatched, skills invoked, throughput per department — all conventional, all measuring the inverse of success.
*Mitigation:* the primary metric remains **the position of the line**. The departmental metric is **judgments required per objective, trending down.** Both belong in code review, not only design review.

---

## 11 · Future Scalability

### 11.1 500+ skills

The binding constraint is planning context, not dispatch throughput. The arithmetic:

| | Flat (today) | Departmental |
|---|---|---|
| Skills one reasoner must hold to plan | 500 | **7** (Engine) or **~70** (Head) |
| Growth in that number as skills → 1000 | Linear | **Constant** for the Engine; linear within one department only |
| Adding a skill | Widens the one planner's surface | Widens exactly one department's |
| Adding a department | n/a | Widens the Engine's surface by one, requires ratification |

The Engine's surface is bounded by the roster, and the roster is bounded by a ratification requirement. That is why §2.1's admission test is the load-bearing part of this document: it is the only thing standing between hierarchical planning and a flat planner wearing a hierarchy's clothes.

**At 1000 skills**, a department exceeding roughly 100 skills should split — but only by the same test. "Production is large" is not a reason. "Production contains two irreducibly different standards of correctness" is.

### 11.2 Hundreds of concurrent objectives

Contention points, and why each is bounded:

| Point | Touches per objective | At 100 concurrent |
|---|---|---|
| Objective Engine | ~4 (§5.5) | ~400 over days. Not a bottleneck. |
| Department Head | 1 contract + 1 sign-off, plus escalations | 200 + escalations, spread over 7 Heads |
| Mission Lead | Per skill, but **one Lead per department per objective** | Horizontally instantiated; unbounded |
| Judgment queue | Per escalation | **The real constraint — see below** |
| Founder | Judgments only | **The only genuinely scarce resource in the system** |

**The scarce resource is the founder's attention, and it always will be.** This changes what "scaling" means here. Every other layer scales by instantiation. The founder does not. Therefore:

- **Admission control, not queueing.** Departments publish capacity; the Engine admits against it. Toyota's heijunka — level loading — rather than an unbounded intake. An objective that cannot be resourced is refused at admission with a stated reason, not accepted and starved. *A queue that only grows is a promise the system cannot keep.*
- **WIP limits per department**, declared and visible. A department at capacity blocks admission rather than degrading quality silently.
- **The only real scaling mechanism for the founder is L3** — moving the line so fewer decisions require them. **Scaling this system means needing the founder less, not routing to them faster.** Every other product would answer this question with throughput; this one cannot.

### 11.3 Multi-agent collaboration

The Constitution deliberately leaves §8 (Multi-Operator) RESEARCH-BACKED and instructs that a distributed system not be designed. This document honours that and states only the shape it must not block.

**A department is the natural federation boundary**, for three reasons that already hold:

1. It has a **contract-shaped interface** — outcome in, deliverable plus evidence out, with a budget and an acceptance criterion. That is already a remote-capable boundary.
2. It **owns no state.** Everything it uses is in Shared Infrastructure. A remote department would need no state migration.
3. It **holds no permission grants and touches no Environment.** A remote department is therefore not a new trust surface — it is a reasoner producing plans that execute through the same single Operator path, under the same single Permission System.

Three future shapes this admits without redesign:

- **Remote department.** A specialist agent admitted as, say, the Legal department, contracting exactly as a local Head does.
- **Skill provider.** A third-party agent registered as a Skill inside an existing department, subject to that department's standard of correctness and sign-off. **The owning Head still signs.** This is the safest shape and should be the default for anything external.
- **Peer Objective Engine.** Another Kalpavriksha instance, another founder, contracting across a boundary. **Deliberately not designed here.** It raises questions — whose Permission System, whose ledger, whose line — that must be answered before any code, not discovered during it.

**The invariant that must survive all three:** a federated participant is a **reasoner**, never an **executor**. It may propose, plan, and judge within its craft. It may not acquire Environment access, hold a permission grant, or create an execution path. The moment a remote agent can execute, the audit spine has a hole in it that nothing above can detect, and VEDA 04 R1 rates that critical for exactly this reason.

### 11.4 The ten-year test

Four properties that determine whether this document is still useful in 2036:

1. **The roster is bounded by a test, not a list.** New crafts appear; the admission test evaluates them. Nothing here needs rewriting when video generation is replaced by something unnamed.
2. **Skills are versioned and owned; tools are neither owned nor named.** Every Provider in use today will be gone. Not one department definition mentions one.
3. **Authority is separated from competence.** L1 and L2 make the system better at what it may do; only L3 touches what it may do, and L3 cannot enact. **Ten years of compounding competence cannot silently become ten years of accumulated authority.**
4. **The founder's role does not scale with the system's size.** Two touches on a five-department objective. That ratio must hold at fifty departments, or the architecture has failed regardless of how elegant it looks.

---

## 12 · Final Recommendation

### 12.1 Adopt

1. **Seven departments** — Research, Creative, Production, Engineering, Operations, Finance, Correspondence — governed by the §2.1 admission test, changeable only by ratified amendment.
2. **Three central functions that are not departments** — Narration (Vedra, the single voice), Verification (Constitution §10, unchanged), Assurance (thin, process-only, never craft).
3. **Mission Lead**, lazily instantiated per §2.5, never named "Mission Manager."
4. **The shallow spine plus horizontal services model** of §3, replacing the brief's nine-level chain. Execution, Quality Review, and Learning are removed as levels and redistributed.
5. **Hybrid quality** with the three-way split of §4.3, and a unanimous go/no-go poll in which the Objective Engine counts but does not vote.
6. **Skill as a judgment wrapper**, never dispatchable, one owner each, registered as a third index on the existing Capability Registry — **not a new registry**.
7. **The four tool prohibitions** of §8.1: no department selects a Provider, introduces a tool, holds a grant, or touches an Environment.
8. **Commitment-based handoffs** with mechanical, fail-closed staleness (§9.1–9.2), and amendments treated as decisions with computed impact.
9. **Five escalation tiers** routed by decision class, reusing VEDA 04 B3's three triggers unchanged, with a free and unpenalized andon cord.

### 12.2 Reject

- QA, Knowledge, Automation, and Communication as departments (§2.4), each for a stated reason.
- Any department for deciding what the company should want. That is the founder's, by constitutional definition, and a system that acquires it has become something else.
- A permanent Mission Manager layer.
- A separate Skill Registry.
- Any per-artifact founder sign-off.

### 12.3 What this document does not settle

Stated plainly, because a specification that hides its gaps is worse than one that names them.

1. **The Objective/Mission collision (R7)** — requires an ADR and ratification. Recommendation (b) given; the decision is not mine.
2. **Consequence-level reversibility (R8)** — an extension request against VEDA 04 A2. The Registry currently classifies operations; composed irreversibility requires it to classify consequences. This should be raised as a Layer A amendment.
3. **The fast path's exact predicate (R1, R10)** — the shape is fixed (single department, single skill, read-only, no commitment); the precise boundary needs one design pass and a stated non-configurability guarantee.
4. **Department capacity and WIP limit calibration (§11.2)** — requires production data. Do not guess numbers into this document.
5. **Peer Objective Engine federation (§11.3)** — deliberately not designed, per the Constitution's standing instruction. The questions it raises are named so they are not discovered late.

### 12.4 Adoption sequence

The ordering is not preference. Each step makes the next one safe, and the sequencing rule inherited from VEDA 04 §9 governs throughout: **never ship autonomy before accountability.**

| Step | What | Gate to proceed |
|---|---|---|
| **0** | Ratify terminology: Mission Lead, Skill-as-wrapper, and the Objective/Mission resolution | No document or module uses a colliding term |
| **1** | Assign every existing Capability to an owning department; add the third registry index | **No unowned Capability is invocable.** Fails closed. |
| **2** | Stand up Department Heads as sign-off authorities only, over today's flat dispatch | Every completed objective carries a Head's signature; the poll runs even though nothing routes departmentally yet |
| **3** | Hierarchical decomposition: the Engine emits department outcomes, not tasks | **The Engine never names a skill.** Verified by test, not by review. |
| **4** | Commitment-based handoffs with versioning and mechanical staleness | A stale artifact cannot pass the poll |
| **5** | Mission Leads, lazily; the fast path, with its predicate fixed | Fast-path ratio reported in the brief |
| **6** | Assurance function | Fails an objective on a missing receipt; cannot fail one on craft |
| **7** | The three learning loops, with write scopes enforced | **L3 proposes and cannot enact.** Verified by test. |

**Step 2 before step 3 is the important ordering.** Sign-off authority is accountability; hierarchical decomposition is delegated planning authority. Shipping the delegation first would give departments planning power in a release where nobody yet signs for the result — autonomy before accountability, precisely.

### 12.5 VEDA compliance

Each principle, the structural mechanism that serves it, and — where one exists — the tension this architecture creates against it. The tensions are listed because an architecture that claims to serve every principle without cost is not being examined honestly.

| Principle | Mechanism | Tension, and how it is held |
|---|---|---|
| **Protect the user's judgment** | No Strategy department (§2.4). Irreversibility never delegated, at any tier (§4.1). L3 proposes and cannot enact (§5.6). Amendments return decisions, not disputes (§9.4). | **Seven competent departments make deference easy.** Mitigated by returning reasoning rather than conclusions, and by the annual dependency audit reviewing the roster itself. |
| **User-centric** | Two founder touches per objective (§5.4). One approval at admission, relayed downward (§5.2). No per-artifact sign-off (§4.3). Admission control rather than unbounded queueing (§11.2). | None material. |
| **Silent guardian** | Six of eight lifecycle phases are silent by construction (§5.1). E0–E2 resolve without the founder. Departments hold no surfacing channel (§3.4). | **Silence can conceal.** Held by: refusals narrated even when nothing was lost (§4.2.6); halts always surfaced; Vigilance gaps bypassing ranking (§4.2.5). |
| **Transparency** | Every actor writes intent before acting. Receipts name Head, Lead, and Skill. Handoffs are hash-addressed. Assurance audits process. Ranking justifies itself. | **Hierarchy adds distance between the founder and the actor.** Held by receipts naming the specific Lead and Skill — depth is recorded, never summarized away — and by department branches appearing in the tree topology. |
| **Authorization first** | Four tool prohibitions (§8.1). Departments hold no grants. Unowned skills non-invocable. Unclassified Capabilities non-executable. Reversibility composes pessimistically (§8.3). | None material. R8 names a real gap in the underlying Registry; it is an extension request, not an exemption. |
| **Objective completion** | "Done" must be checkable or the objective is refused at admission (§5.2). Unanimous poll, failing closed, absence never assent (§4.3). Verification independent of execution. Stale artifacts undeliverable. | **A unanimous poll can deadlock.** Held by R9: every poll carries a deadline whose default is **no-go**, never go. |
| **Constitution above convenience** | Department changes require ratification (§2.1). Fast path is non-configurable (R10). Andon cord carries no penalty (§6.4). No department may fork a skill to escape its standard (§7.2 Rule 5). Terminology collisions named rather than absorbed (§0.4). | This principle *is* the tension, permanently. Every mechanism above costs something on a deadline. That is what makes them constitutional rather than default. |

### 12.6 Closing

The brief asked for an architecture worthy of ten years. The test of that is not whether the structure is elegant today; it is whether it still constrains the right things after a decade of pressure it was not designed for.

Two properties are what this document is actually betting on.

**The roster is governed by a test rather than a list.** Crafts will appear that have no name in 2026. The admission test evaluates them without the roster needing to be rewritten, and the ratification requirement means the roster cannot grow quietly.

**Competence and authority are separated by structure, not by intention.** The system will become dramatically better at what it does. L1 and L2 make sure of that. Neither can widen what it is permitted to do. Only L3 touches the line, and L3 cannot enact — so ten years of compounding capability cannot become ten years of accumulated authority through any path except a founder deliberately granting it, one rule at a time, each with a cumulative cap and an expiry date.

That is the whole architecture, and it is the reason for every prohibition in it:

> **The departments exist so the system can become excellent. The prohibitions exist so that becoming excellent never becomes a reason to ask permission less often.**

---

*Prepared as a permanent VEDA Project document. Architecture only — no code, no implementation, no edits to frozen documents. Every claim about current system behaviour is drawn from `src/master_agent/mission_control/`, `KALPAVRIKSHA_VISION_V2` as summarized in `knowledge/architecture/02_constitution.md`, and VEDA 01–04. Where this document proposes a change to a frozen term or a Layer A component, it says so and requests ratification rather than assuming it.*
