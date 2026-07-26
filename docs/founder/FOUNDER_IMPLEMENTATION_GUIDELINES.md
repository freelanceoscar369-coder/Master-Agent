Founder Implementation Guidelines
Permanent Implementation Rules for Kalpavriksha

Version 1.0
Changelog:
- 2026-07-26: Initial version

Section 1 — Purpose
Explain that this document exists because the Founder discovered repeated mistakes during Mission Briefs 001–022.
Future AI systems must follow these principles automatically rather than depending on prompt wording.
These are permanent implementation rules.

Section 2 — Never Build Before Research
Every significant subsystem must first undergo research.
Research should identify:
existing industry solutions
architectural patterns
strengths
weaknesses
failure modes
Never reinvent something already solved well.

Section 3 — Borrow Everything Except Differentiation
Always prefer wrapping proven technology instead of rebuilding it.
Examples:
Wrap Playwright.
Wrap accessibility APIs.
Wrap LangGraph.
Wrap browser engines.
Wrap operating-system APIs.
Never rebuild mature infrastructure.
Only build what makes Kalpavriksha unique.

Section 4 — Build Only Competitive Advantage
Only implement components that competitors do not already provide.
Everything else should be adapters around proven software.

Section 5 — Brain and Body Must Never Merge
Planning belongs only to the Executive Brain.
Execution belongs only to the Universal Executive Operator.
Workers never plan.
Brains never execute.
This separation is permanent.

Section 6 — Never Learn Products
Never teach the system:
Windows
Chrome
VS Code
SAP
ChatGPT
Claude
Gmail
etc.
Teach environments.
Teach behaviors.
Teach capabilities.
Teach observations.
Teach constraints.
Teach verification.
Teach recovery.
Products are temporary.
Behaviors are permanent.

Section 7 — Reality Always Wins
Documentation is not truth.
Execution is truth.
Observation is truth.
Verification is truth.
Logs are truth.
The running environment always overrides documentation.

Section 8 — Independent Verification
Execution must never verify itself.
Verification must always be structurally independent.
Never ask the executor if it succeeded.
Always prove success.

Section 9 — Recovery Is First-Class
Recovery is not retry.
Recovery is a dedicated subsystem.
Every Worker must support:
interruption handling
unexpected UI
missing controls
crashes
retries
escalation

Section 10 — Evidence Before Knowledge
Nothing becomes permanent knowledge after one observation.
Evidence accumulates.
Evidence is reviewed.
Knowledge is promoted only after sufficient confidence.

Section 11 — Human Approval
Irreversible actions always require Founder approval.
Never bypass this rule.

Section 12 — Two Examples Before Generalization
Never build abstractions from one implementation.
Implement twice.
Generalize afterwards.

Section 13 — Honest Technical Debt
Never hide limitations.
Never pretend something exists.
Every unfinished subsystem must be explicitly marked.

Section 14 — Scalability Question
Before implementing anything ask:
Will this still work with
100 Workers
1000 plugins
100 environments
distributed VPS execution
multiple operator instances
If not, redesign before coding.

Section 15 — Research Before Decisions
Every major architectural decision should document:
What alternatives existed
Why they were rejected
Why the chosen solution won

Section 16 — Cost Discipline
Claude tokens are expensive.
Research should be performed with lower-cost models whenever possible.
Use Gemini, Hermes, ChatGPT, web research, documentation, and existing knowledge before consuming Claude implementation budget.
Reserve Claude primarily for:
architecture
implementation
audits
difficult reasoning

Section 17 — Local First
Prefer local execution whenever practical.
Cloud services should enhance Kalpavriksha, not become mandatory dependencies.

Section 18 — Build Production Systems
Never build prototypes.
Never build demos.
Never build mock architecture.
Every implementation should be production quality unless explicitly marked experimental.

Section 19 — Continuous Learning
Whenever a new important lesson is discovered:
Update this document.
Do not rely on remembering it in future prompts.
This document is expected to evolve throughout the lifetime of Kalpavriksha.

Section 20 — Mandatory Reading
Every future Mission Brief must begin by reading:
Founder Constitution Freeze
Founder Implementation Guidelines
PROJECT_BRAIN.md
If any Mission Brief conflicts with these documents,
the Constitution wins,
then Founder Implementation Guidelines,
then PROJECT_BRAIN,
then Mission Brief.

This document exists so Kalpavriksha improves not only by writing better code, but by becoming better at building itself.