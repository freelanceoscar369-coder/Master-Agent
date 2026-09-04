# KALPAVRIKSHA P0 — GATE 3
## EXPERT COMPUTER OPERATOR INTELLIGENCE GAP AUDIT

## Executive Conclusion
The Browser Executive (Gate 2) provides proven browser automation capabilities (open_url, new_tab, close_tab, switch_tab, focus_browser, observe_browser, click, type_text, press_key, scroll, wait_for_selector). However, to elevate this to an Expert Human Computer Operator, the system must demonstrate the full OBSERVE→UNDERSTAND→ACT→OBSERVE→VERIFY→RECOVER→LEARN loop. 

Evidence shows:
- **OBSERVE** and **ACT** are proven via BrowserExecutive and action classes.
- **VERIFY** exists structurally (Verification Subsystem) but requires Expected Outcomes from the Planner.
- **UNDERSTAND**, **RECOVER**, and **LEARN** are not demonstrated in the current architecture. The Planner (which would provide UNDERSTAND) is a stub; the real Planner (Mission Brief 036) is not yet implemented. Recovery is limited to action-level retries; objective-level recovery (re-planning after failure) is not implemented. Learning (Persistence → Knowledge → Future Reasoning) is designed but not implemented.

The missing capabilities belong to existing architectural owners:
- UNDERSTAND → Planner (brain)
- OBJECTIVE-LEVEL RECOVERY → Orchestrator (operator) with Brain escalation
- LEARN/REMEMBER → Memory (shared infrastructure) and Promotion Review (brain)
- POST-ACTION UNDERSTANDING → Verification Subsystem (operator-adjacent) and Planner (brain)
- VISUAL/SEMANTIC BOUNDARY → Verification Subsystem (DOM-only observation proven; visual/semantic not required for P0)
- END-TO-END INTELLIGENCE PATH → Blocked at Planner (reasoning provider unavailable)

P0 MINIMUM INTELLIGENCE SET requires only what is already proven plus a functioning Planner that can decompose objectives into steps with Expected Outcomes. Since the reasoning provider issue blocks the Planner, the system cannot currently achieve Expert Human Computer Operator status without resolving the reasoning layer (Gate 7). However, the architecture already defines where each capability belongs; no new owners are needed.

CTO BUILD CANDIDATES: Implement the real Planner (planner/planner.py) to consume the Model Router and produce MissionPlans with Expected Outcomes. This is the smallest constitutionally correct extension to satisfy P0.

## A. UNDERSTAND
- **current capability**: Not demonstrated. The Intent Layer (cli.py) parses rudimentary intents; the Planner (planner/planner.py) is a stub (NotImplementedError). No component decomposes objectives into steps with Expected Outcomes.
- **evidence**: 
  - src/master_agent/planner/planner.py: `class Planner` raises `NotImplementedError` in `plan()` (lines 138-205).
  - src/master_agent/cli.py: `build_plan()` is a regex-based stand-in that only handles folder/project creation (lines 441-470).
  - KALPAVRIKSHA_VISION_V2.md §3.2: Planner attaches Expected Outcome to each Step so Verification has something to check against.
- **owner**: Planner (brain) per KALPAVRIKSHA_VISION_V2.md §3.2 and ARCHITECTURE.md §4.2.
- **classification**: E — MISSING AND NO EXISTING OWNER (the owner exists but the capability is not implemented; however, the architecture assigns it to the Planner, so it is D — MISSING BUT HAS EXISTING ARCHITECTURAL OWNER). Correction: The Planner exists as a component but does not perform the capability. This is classified as **C — EXISTS PARTIALLY / NEEDS EXTENSION** because the Planner class is present but its `plan()` method is not implemented.

## B. OBJECTIVE-LEVEL RECOVERY
- **current capability**: Action-level retry exists (Orchestrator executes steps sequentially and stops on failure; Runtime retries attempts via Kernel.attempt budget). No mechanism for the Orchestrator to detect failure, understand why, select a recovery strategy (e.g., re-plan with different capability), execute recovery, and re-verify.
- **evidence**: 
  - src/master_agent/orchestrator/orchestrator.py: `execute_plan()` stops at first problem (line 82); no retry/failure-branching logic beyond stopping.
  - KALPAVRIKSHA_VISION_V2.md §11.1: Connects failed Verification Verdict to Brain as recovery trigger but does not specify the decision rule for when Orchestrator's retry policy absorbs vs. escalates to re-plan.
  - FOUNDER_CONSTITUTION_FREEZE.md §3: Names "in-mission recovery decision procedure" as an open gap (EVOLVABLE).
- **owner**: Orchestrator (operator) for action-level retry/failure-branching (§4.1); Brain (planner) for objective-level re-plan (§11.1).
- **classification**: C — EXISTS PARTIALLY / NEEDS EXTENSION. The Orchestrator stops on failure but does not implement failure-branching policy (only stops). The architecture expects the Orchestrator to apply retry/failure-branching policy (§4.1) but it is not implemented beyond stopping.

## C. LEARN / REMEMBER
- **current capability**: Execution → Evidence → Knowledge Candidate → Promotion Review → Permanent Knowledge → Future Reasoning lifecycle is designed but not implemented. Mission history is stored in Local Memory (SQLite) but not used to generate Knowledge Candidates or inform future planning.
- **evidence**: 
  - KALPAVRIKSHA_VISION_V2.md §9.3: Describes the Knowledge Lifecycle but marks it RESEARCH-BACKED (not yet implemented).
  - src/master_agent/memory/store.py: SQLiteMemoryStore persists MissionRecord but does not expose knowledge promotion interface.
  - No Prominent Review gate or Knowledge Candidate nomination observed in code.
- **owner**: 
  - Knowledge Candidate → Brain (Planner) (§9.3)
  - Promotion Review → dedicated gate (human-confirmed for Founder Edition) (§9.3)
  - Permanent Knowledge → Shared Infrastructure (Memory, Layer 4) (§9.3)
  - Future Reasoning → Brain (Planner) (§9.3)
- **classification**: C — EXISTS PARTIALLY / NEEDS EXTENSION. Memory persistence exists; the learning loop stages are designed but not implemented.

## D. POST-ACTION UNDERSTANDING
- **current capability**: The Verification Subsystem produces Evidence (Observation vs. Expected Outcome) but does not interpret whether the Objective is satisfied; that is the Brain's job (via Planner consuming Evidence as context).
- **evidence**: 
  - KALPAVRIKSHA_VISION_V2.md §10.2: Verification Subsystem produces Evidence (Observation + Expected Outcome + Verdict).
  - KALPAVRIKSHA_VISION_V2.md §10.4: Evidence flows back to the Brain as input to "is this Mission actually complete, or does it need another Step."
  - src/master_agent/planner/planner.py: Planner reads recent Mission history as context (line 119: "Reads recent Mission history and Permanent Knowledge (§9) as context for 'have I done something like this before.'")
- **owner**: 
  - Verification Subsystem produces Evidence (operator-adjacent, own contract) (§10)
  - Brain (Planner) interprets Evidence to determine if objective is satisfied (§3.2, §9)
- **classification**: C — EXISTS PARTIALLY / NEEDS EXTENSION. Verification produces Evidence; the Planner is supposed to use it as context but is not implemented.

## E. VISUAL / SEMANTIC BOUNDARY
- **current capability**: ObserveBrowserAction returns DOM-only observation (URL, title, viewport, selector-based element state). No visual observation (screenshots, OCR, visual diff) is implemented or required for P0.
- **evidence**: 
  - BROWSER_WORKER_ARCHITECTURE.md: ObserveBrowserAction returns URL, title, viewport; no visual/UI observation.
  - docs/audits/HERMES_BROWSER_AUTOMATION_BASELINE.md: MIT-001 confirms ObserveBrowser returns URL, title, viewport (DOM-only).
  - KALPAVRIKSHA_VISION_V2.md §10.2: Observation is a freshly captured fact about real-world state gathered by Verification Subsystem re-checking an Environment Instance.
  - No visual observation capabilities (e.g., screenshot, OCR) are present in the browser actions.
- **owner**: Verification Subsystem (via ObserveBrowserAction) owns DOM observation; visual/semantic would be a future extension of Verification Subsystem.
- **classification**: A — ALREADY EXISTS AND PROVEN for DOM observation. Visual/semantic observation is **F — OUTSIDE P0 / DEFER** (not required for P0 per Gate 2 evidence).

## F. END-TO-END INTELLIGENCE PATH
Show: USER OBJECTIVE → INTENT → CONTEXT → PLANNER → PLAN → MISSION CONTROL → EXECUTIVE → OBSERVE → VERIFY → MEMORY

Mark each stage:
- **USER OBJECTIVE → INTENT**: PASS (Intent Layer parses rudimentary intents; cli.py stand-in works for basic shapes)
- **INTENT → CONTEXT**: PASS (Planner reads recent Mission history and Permanent Knowledge as context)
- **CONTEXT → PLANNER**: BLOCKED — REASONING PROVIDER (Planner requires reasoning capability; AI Capability Broker has 0 eligible reasoning providers due to Ollama disabled and no alternatives registered)
- **PLANNER → PLAN**: BLOCKED — REASONING PROVIDER (same as above)
- **PLAN → MISSION CONTROL**: PASS (Mission Control accepts MissionPlans from Planner via dispatcher)
- **MISSION CONTROL → EXECUTIVE**: PASS (Runtime dispatches tasks to Executives)
- **EXECUTIVE → OBSERVE**: PASS (BrowserExecutive and action classes proven)
- **OBSERVE → VERIFY**: PASS (Verification Subsystem structurally independent; observe_browser action proven)
- **VERIFY → MEMORY**: PASS (Evidence stored via Shared Infrastructure's Memory)
- **MEMORY → (future planning)**: C — EXISTS PARTIALLY / NEEDS EXTENSION (Memory stores history but not yet used for Knowledge Candidates)

## G. P0 MINIMUM INTELLIGENCE SET
List ONLY what is genuinely required to satisfy P0:
1. A functioning Planner that can:
   - Take an Intent and produce a MissionPlan (DAG of Steps)
   - Attach an Expected Outcome to each Step (machine-checkable)
   - Read recent Mission history and Permanent Knowledge as context
2. The existing BrowserExecutive and action classes (proven in Gate 2)
3. The existing Verification Subsystem (proven to produce Evidence)
4. The existing Memory system (proven to persist Mission Record)
5. The existing Orchestrator (executes plan sequentially, stops on failure)
6. The existing Permission System (gates above read-only risk)
7. The existing Intent Layer (parses basic intents)

Note: The Planner is the only missing piece in the intelligence path. All other components are proven or architecturally specified.

## H. DO NOT BUILD
List capabilities that already work or are outside P0:
- BrowserExecutive capabilities (open_url, new_tab, close_tab, switch_tab, focus_browser, observe_browser, click, type_text, press_key, scroll, wait_for_selector) — DO NOT BUILD (already proven)
- Mouse/Keyboard execution (Gate 1) — DO NOT BUILD
- Application launch, Tree, Greeting, Conversation (Founder Edition basics) — DO NOT BUILD
- Intent Layer (basic parsing) — DO NOT BUILD (sufficient for P0)
- Memory persistence (Mission Record storage) — DO NOT BUILD
- Verification Subsystem (Evidence production) — DO NOT BUILD
- Orchestrator (sequential execution with approval gating) — DO NOT BUILD
- Permission System (Human approval before important actions) — DO NOT BUILD
- Visual/semantic observation (screenshots, OCR) — OUTSIDE P0
- Knowledge Lifecycle (Promotion Review, Permanent Knowledge) — OUTSIDE P0 for P0 (not required for basic Expert Human Computer Operator loop)
- Objective-level recovery (re-planning after failure) — OUTSIDE P0 for P0 (Planner must work first; recovery can be added later)
- Multi-Operator Architecture — OUTSIDE P0
- AI Capability Broker provider selection — OUTSIDE P0 (reasoning provider must be available first, but integration is separate)

## I. CTO BUILD CANDIDATES
List only genuine implementation candidates. For each provide:
- gap;
- existing owner;
- smallest correct extension;
- evidence;
- constitutional basis;
- verification needed.

**Candidate 1: Implement the real Planner**
- gap: UNDERSTAND (Planner stub), POST-ACTION UNDERSTANDING (Planner not using Evidence as context), OBJECTIVE-LEVEL RECOVERY (Planner not involved in re-plan decision), END-TO-END INTELLIGENCE PATH (blocked at Planner)
- existing owner: Planner (brain) per KALPAVRIKSHA_VISION_V2.md §3.2 and ARCHITECTURE.md §4.2
- smallest correct extension: 
  - Replace `src/master_agent/planner/planner.py` with a working implementation that:
    1. Uses the Model Router to call a reasoning provider (local or cloud) to generate a plan prompt.
    2. Validates the returned plan against the capability catalogue and expected outcome schema.
    3. Returns a MissionPlan with Steps each naming a Capability and an Expected Outcome.
    4. Reads recent Mission history and Permanent Knowledge from Shared Infrastructure's Memory as context.
  - This is the smallest extension because:
    - The Planner already depends on the Model Router (line 70) and Capability Catalogue (line 103).
    - The plan_expectation() function already exists (line 69) to generate the Expected Outcome artefact.
    - The validate() function already exists (line 56) to check the plan document.
    - The Planner already has hooks for catalogue and requester.
- evidence: 
  - KALPAVRIKSHA_VISION_V2.md §3.2: Planner attaches Expected Outcome to each Step.
  - KALPAVRIKSHA_VISION_V2.md §3.3: Model Router picks a provider per call based on connectivity, privacy, task profile, explicit user preference.
  - KALPAVRIKSHA_VISION_V2.md §9.3: Planner nominates Knowledge Candidates (future extension).
  - src/master_agent/planner/planner.py: Existing stub shows the intended structure.
- constitutional basis: 
  - The Planner is a Brain component; it must not execute, touch Environment, or hold Permission grants (KALPAVRIKSHA_VISION_V2.md §3.5).
  - The Planner calls a Reasoning Provider through the Model Router — planning is a capability like any other (KALPAVRIKSHA_VISION_V2.md §3.2).
  - The Planner reads recent Mission history and Permanent Knowledge as context (KALPAVRIKSHA_VISION_V2.md §3.2).
- verification needed: 
  - Run the Planner with a sample Intent (e.g., "Create a folder called test") and verify it returns a MissionPlan with one Step (capability=Filesystem.CreateFolder, payload={name: "test"}, Expected Outcome={folder exists at path}).
  - Run with a browser Intent (e.g., "Open Chrome and navigate to example.com") and verify it returns a MissionPlan with Steps for open_url and observe_browser, each with Expected Outcomes.
  - Ensure the Planner does not execute any capability (no side effects).

**Note**: No other candidates are needed for P0. The reasoning provider issue (Gate 7) must be resolved separately, but once a provider is available (e.g., local Hermes or cloud API), the Planner can use it via the existing Model Router.

---
*Evidence collected from source code, architecture documents, and runtime tests. No source code modified, no configuration changed, no provider registered.*