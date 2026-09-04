# KALPAVRIKSHA_FREE_CRITIC_RESEARCH.md

## Executive conclusion
Kalpavriksha can obtain strong criticism at zero incremental paid-token cost by leveraging deterministic verification and conformance checks, augmented by genuinely free local models (e.g., Ollama, LM Studio) when available and adequate for the critique depth required. The existing Broker and verification infrastructure already provides the necessary hooks; no new architecture component is required. The critic should be treated as a constrained extension of the existing reasoning pipeline, with economic enforcement via the Broker's policy layer.

## Founder zero-cost requirement
The Founder mandates that any runtime critic must incur **zero incremental paid-token cost**. This means:
- No automatic fallback to paid APIs.
- No hidden metered usage.
- Free-tier usage must be independently verifiable and quota-observable.
- If no adequate free resource is available, the system must fall back to deterministic checks only and report critique as unavailable.

## Current Kalpavriksha critic-like capabilities
### Deterministic / local zero cost (F0)
- Requirement coverage analysis (brain/conformance.py)
- Evidence sufficiency and freshness (verification/evidence.py)
- Contradiction detection via competing evidence (verification/evaluator.py)
- Schema validation of Observation vs ExpectedOutcome
- Duplicate strategy detection (planned but not yet implemented)
- Verification/Verdict pipeline (already in place)

### Genuinely free model access (F1)
- **Ollama** (`ollama.local`): Local runtime; no per-token cost if already running. Requires local installation and model pull; privacy-preserving; automation via OpenAI-compatible endpoint. Quota: limited by local hardware. Freshness: model dependent.
- **LM Studio** (`lm-studio.local`): Similar to Ollama; local private runtime.
- **Browser/free AI** (`browser.free-ai`): Placeholder; not yet wired as a provider in PROVIDER_CATALOG but present in codebase (`providers/browser_free_ai.py`). Would be zero marginal cost if the Founder already has a web AI service unlocked.

### Zero-marginal-cost existing access (F2)
- **ChatGPT Desktop** (if installed and authenticated): Already paid subscription; additional use does not incur per-token cost. However, automation may violate terms; privacy considerations.
- **Kimi Desktop**, **Perplexity Desktop**: Same as above.

### Free-tier API (F3)
- **Gemini API** (`gemini.api`): Free tier exists but requires API key; quota must be monitored; risk of paid overflow if not gated.
- **OpenRouter** (`openrouter.api`): Offers free models; rate limits apply; requires API key; paid overflow possible.

### Promotional credit (F4)
- Not suitable for runtime critic.

## Current provider audit
From `src/master_agent/ai_infrastructure/catalog.py` (PROVIDER_CATALOG):
| Provider ID | Label | Cost per call | Locality | Privacy | Capabilities | Configured? | Executable? | Available? | Free right now? |
|-------------|-------|---------------|----------|---------|--------------|-------------|-------------|------------|-----------------|
| claude-desktop | Claude Desktop | 0.0 | desktop | third_party | reasoning, planning, coding | No (requires subscription) | No (unless installed) | No (unless installed & healthy) | No (not free to run; marginal cost zero but requires paid subscription) |
| lm-studio.local | LM Studio | 0.0 | local | private | reasoning, coding | No (requires local setup) | Yes (if installed) | Depends on local health | Yes (if running) |
| ollama.local | Ollama | 0.0 | local | private | reasoning, coding | No (requires local setup) | Yes (if installed) | Depends on local health | Yes (if running) |
| gemini.api | Gemini API | 0.0 | cloud | third_party | reasoning, planning, coding | Yes (if GEMINI_API_KEY set) | Yes (API reachable) | Yes (if quota remains) | Conditional (free tier) |
| openrouter.api | OpenRouter | 0.005 | cloud | third_party | reasoning, coding | Yes (if OPENROUTER_API_KEY set) | Yes | Yes (if quota remains) | Conditional (free tier) |
| chatgpt-desktop | ChatGPT Desktop | 0.0 | desktop | third_party | reasoning, planning, coding | No (requires subscription) | No (unless installed) | No (unless installed & healthy) | No (requires paid subscription) |
| kimi-desktop | Kimi Desktop | 0.0 | desktop | third_party | reasoning | No | No | No | No |
| perplexity-desktop | Perplexity Desktop | 0.0 | desktop | third_party | reasoning | No | No | No | No |
| browser.free-ai | Browser Free AI | 0.0 | ? | ? | reasoning | No (not in catalog) | ? | ? | ? |

Notes:
- `cliude-desktop` and `chatgpt-desktop` are zero marginal cost *only* if the Founder already has a paid subscription; they are not *free* in the sense of no economic burden.
- `ollama.local` and `lm-studio.local` are genuinely free (F1) if locally installed and healthy.
- `gemini.api` and `openrouter.api` are free‑tier APIs (F3) and require quota monitoring.
- No provider is currently marked as `executable` in the broker registry unless explicitly wired (e.g., via `provider_registry` in `kalpavriksha_desktop.py`).

## External free critic research
### Verified zero‑cost resources (as of 2026-08-30)
- **Ollama**: Local LLM server; models like `llama3.1`, `mistral`, `gemma2`; completely free; OpenAI‑compatible API; privacy‑preserving; rate limited by hardware.
- **LM Studio**: Local GUI/server for LLMs; free to download and run; supports OpenAI‑compatible API; privacy‑preserving.
- **Gemini API (free tier)**: 60 requests/minute; requires API key; Google’s free usage limits subject to change.
- **OpenRouter**: Offers free access to models like `mistral-7b-instruct`, `llama3-8b`; rate limits apply; requires API key.
- **Hugging Face Inference API**: Free tier available for many models; rate limited; requires API key; some models have commercial restrictions.
- **Groq**: Free tier not currently available (as of 2026‑08); mostly paid.
- **Cerebras**: No free tier.
- **Cloudflare Workers AI**: Free tier with limits; requires account.
- **NVIDIA AI Foundation**: No free public API.

### Privacy & automation
- Ollama/LM Studio: Data never leaves machine; automation via HTTP POST; safe for sensitive Founder data.
- Gemini/OpenRouter/HF: Data sent to provider; review terms; not suitable for highly sensitive Founder prompts unless explicitly cleared.
- Browser/free‑ai: Depends on the specific service; if it is a web AI chat (e.g., Bing Chat), automation may be restricted and data may be logged.

## Quality / adequacy comparison
### Adequate for C1 light critique (deterministic + free model for obvious omissions/contradictions)
- **Ollama/LM Studio** with small models (e.g., `phi3`, `gemma2:2b`) – sufficient for checking requirement coverage, detecting contradictions in short text, judging answer relevance.
- Deterministic checks alone (F0) often suffice for C1.

### Adequate for C2 strong critique (complex reasoning, multiple requirements)
- **Ollama/LM Studio** with larger models (e.g., `llama3.1:8b`, `mistral`) – capable of lightweight research synthesis, spotting missing implications, evaluating recovery strategies.
- **Gemini API** (free tier) – if quota allows and privacy acceptable.

### Adequate for C3 independent critique (different provider/challenges generator)
- Only possible if two genuinely free local models differ (e.g., Ollama vs LM Studio) – rare; usually same backend.
- Free‑tier APIs from different providers (e.g., Gemini vs OpenRouter) could serve but cost‑class F3 and require quota monitoring.

### Not adequate
- Any provider that incurs per‑token cost or risks paid fallback.
- Deterministic-only for tasks requiring deep synthesis.

## Free‑status observability matrix
| Provider | Free state observable? | How |
|----------|-----------------------|-----|
| Ollama/localhost | YES | `GET http://localhost:11434/api/tags` returns list of models; health endpoint. |
| LM Studio | YES | Local API health check. |
| Gemini API | PARTIALLY | Requires calling `https://generativelanguage.googleapis.com/v1beta/models?key=`; quota info not directly exposed; must rely on headers (`X-RateLimit-Remaining`) if present. |
| OpenRouter | PARTIALLY | `https://openrouter.ai/api/v1/auth/key` returns rate limit info; requires API key. |
| Hugging Face | PARTIALLY | API returns `X-RateLimit-Remaining` header for some endpoints. |
| Browser/free‑ai | UNKNOWN | Not implemented. |

## Privacy assessment
- **Safe for sensitive Founder data**: Ollama, LM Studio (local only).
- **Conditionally safe**: Gemini, OpenRouter, Hugging Face – only if Founder has explicitly consented to data export and the provider’s terms permit founder‑level usage.
- **Unsafe**: Any service that retains prompts for training without opt‑out.

## Proposed critic responsibility
The critic should:
1. Receive a `CritiqueRequest` (structured) containing:
   - `plan_or_reasoning`: text or structured plan.
   - `requirements`: list of requirement IDs and descriptions.
   - `evidence`: list of evidence IDs to consider.
   - `context`: mission‑level constraints (privacy, sensitivity).
2. Return a `CritiqueResult` (see below) with:
   - `status`: `ACCEPT`, `REVISE`, `NEED_MORE_EVIDENCE`, `ESCALATE`.
   - `issues`: list of `{requirement_id, issue_type, severity, evidence_ids, explanation, correction_owner}`.
   - `unsupported_claims`, `contradictions`, `missing_requirements`, `missing_evidence`, `revision_required`.
   - `confidence`: float 0.0‑1.0.
   - `critic_provider`, `critic_model`, `cost_class`, `incremental_cost` (must be 0.0), `free_status_evidence`, `free_status_verified_at`.
3. The Brain (or Planner) validates the result; the existing owner (Planner, Verifier, Conformance) performs correction.
4. Critic never owns truth; Evidence and Conformance override critic judgments.

## Existing Brain extension
No new component required. Extend:
- `brain/conformance.py` to optionally call a critic after deterministic checks.
- `brain/reporter.py` to surface critic findings in reports.
- Use the existing `ModelRouter` / `Broker` to select a zero‑cost critic provider, constrained by a policy that forbids incremental cost.

## Broker zero‑cost constraint
The existing `SelectionPolicy` can express a hard floor on `cost_per_call`. To enforce zero incremental cost:
- Create a policy (e.g., `ZERO_COST`) with `hard_floor = 0.0` and `allow_paid = False`.
- The Broker will then filter out any provider with `cost_per_call > 0.0` (i.e., any metered API).
- For free‑tier APIs (`cost_per_call == 0.0` but with quota risk), additional runtime guardrails are needed (see below).

## Critic depth policy
- **C0 (deterministic only)**: Used for simple filesystem ops, verified browser actions, obvious transformations.
- **C1 (light free critic)**: Employ when deterministic checks pass but the Founder would benefit from a quick sanity check (e.g., “did you miss any obvious requirement?”). Use smallest adequate local model.
- **C2 (strong free critic)**: Employ for complex reasoning, research synthesis, recovery decisions. Use best available free local model or monitored free‑tier API.
- **C3 (independent free critic)**: Employ when consequence justifies cross‑provider challenge and two zero‑cost providers are available.
- **C4 (adversarial free critique)**: Only if abundant free capacity exists; ask critic to falsify a claim.

## Independent‑model policy
- Prefer cross‑provider critic only if both are zero‑cost and adequately capable.
- If only one zero‑cost provider is available, use it (same‑provider critic) rather than falling back to paid.
- Never sacrifice the zero‑cost guarantee for independence.

## Fail‑closed economics policy
The critic selection logic must:
- **Never** automatically fall back to a paid provider.
- If the selected free critic signals that its next call may become paid (e.g., quota exhausted), treat as unavailable and reselect among remaining zero‑cost resources.
- If no zero‑cost critic is available, return `critique unavailable` and continue with deterministic checks only.
- Log the reason (quota exhausted, cost status unknown, etc.) for audit.

## CritiqueResult contract
```json
{
  "status": "ACCEPT|REVISE|NEED_MORE_EVIDENCE|ESCALATE",
  "issues": [
    {
      "requirement_id": "string",
      "issue_type": "OMISSION|CONTRADICTION|UNSUPPORTED|WEAK_STRATEGY|...",
      "severity": "LOW|MEDIUM|HIGH",
      "evidence_ids": ["string", ...],
      "explanation": "string",
      "correction_owner": "PLANNER|VERIFIER|CONFORMANCE|EXECUTIVE"
    }
  ],
  "unsupported_claims": ["string", ...],
  "contradictions": ["string", ...],
  "missing_requirements": ["string", ...],
  "missing_evidence": ["string", ...],
  "revision_required": ["string", ...],
  "confidence": 0.0,
  "critic_provider": "string",
  "critic_model": "string",
  "cost_class": "F0|F1|F2|F3",
  "incremental_cost": 0.0,
  "free_status_evidence": "string", // e.g., "ollama health check OK"
  "free_status_verified_at": "ISO timestamp"
}
```

## Anti‑loop rules
- Maximum **one** model‑based critique/revision cycle per mission step.
- If the same criticism is produced with the same evidence and no substantive change in the plan after revision, **STOP** and escalate to `NEED_MORE_EVIDENCE` or `ESCALATE` as appropriate.
- Free does not mean unlimited; latency and system capacity still apply.

## Runtime vs development critic
- **Development critic**: May use promotional credits, higher‑quota free tiers, or even paid models for regression grading and adversarial evaluation (not bound by zero‑cost runtime rule).
- **Runtime critic**: Strictly zero incremental paid‑token cost, as defined above.

## Acceptance battery (conceptual)
Tests proving:
- **ECONOMIC**: Zero‑cost resource selected; paid resource excluded even if higher quality; free quota exhaustion does not trigger paid fallback; unknown economics does not trigger paid fallback.
- **QUALITY**: Critic catches omitted requirement, unsupported claim, contradictory evidence, insufficient research, answer to nearby question, weak recovery strategy, repeated failed method, overconfident conclusion.
- **NEGATIVE**: Critic does not interfere with simple correct folder creation, deterministic verified task, fully supported answer, operation already rejected by deterministic constraint.
- **PRIVACY**: Sensitive request never goes to an ineligible free third‑party critic.

## Architecture impact
- **Does zero‑cost Critic require a new component?** No. Existing `ModelRouter`, `Broker`, `Verification`, and `Conformance` can be extended.
- **Likely files to touch**:
  - `src/master_agent/brain/conformance.py` – add critic hook after deterministic checks.
  - `src/master_agent/brain/reporter.py` – include critic findings in reports.
  - `src/master_agent/broker/policy.py` – add a `ZERO_COST` policy (or reuse `hard_floor=0.0, allow_paid=False`).
  - `src/master_agent/plugins/model_router.py` – ensure it can be constrained by a zero‑cost policy when called for critic.
  - `src/master_agent/verification/evaluator.py` – no change.
  - `src/master_agent/ai_infrastructure/catalog.py` – no change.
- **Broker changes**: None if we reuse existing policy mechanism; otherwise add a named policy.
- **Provider metadata extensions**: None needed; `cost_per_call` already expresses marginal cost.
- **Persistence/freshness requirements**: None for local models; for free‑tier APIs, require runtime quota check (could be a thin wrapper around the Model Router).
- **Privacy consequences**: Must ensure that the critic selection respects the sensitivity of the input; route sensitive prompts only to local critics (Ollama/LM Studio).
- **Domino‑effect risk**: Low; changes are confined to Brain and Broker policy selection.

## What NOT to build
- ❌ CriticEngine / CriticAgent / CriticBroker / CriticRegistry.
- ❌ Another reasoning provider abstraction (the critic is a usage of existing providers, not a new kind).
- ❌ Always‑on multi‑agent debate.
- ❌ Paid fallback ladder.
- ❌ Permanent promotional‑credit dependency.
- ❌ Separate critic memory store.
- ❌ Critic owning Verification or Conformance.
- ❌ Critic changing Founder requirements.

## Minimum implementation sequence
1. Add a `ZERO_COST` policy (or confirm that `hard_floor=0.0, allow_paid=False` suffices) to `broker/policy.py`.
2. Extend `brain/conformance.py` to:
   - Run deterministic checks (requirement coverage, evidence support, contradiction detection).
   - If configured and a zero‑cost critic is desired (based on mission complexity or Founder preference), invoke the Model Router with the `ZERO_COST` policy to obtain a critic provider.
   - If a provider is obtained, call it with a structured prompt asking for critique (format to be defined).
   - Parse the response into a `CritiqueResult`.
   - Merge critic findings with deterministic results; let the existing owner (Planner/Verifier/Conformance) perform corrections.
3. Extend `brain/reporter.py` to include `critic_findings` in the report metadata when present.
4. Add unit tests to verify that:
   - No paid provider is ever selected when the zero‑cost policy is active.
   - Deterministic checks work unaided.
   - Critic is bypassed when no zero‑cost resource is available.

## SEALED_FREE_CRITIC_HOLDOUT
(Not written into repository; kept separate for engineering validation.)
20 fresh evaluation cases covering:
- Missed requirement.
- Plausible unsupported statement.
- Contradictory evidence.
- Incomplete research.
- Causal overreach.
- Stale source.
- Strong but misleading answer.
- Recovery loop.
- Partial success.
- Simple correct cases where critic must stay silent.

## Recommended Kalpavriksha implementation
> **Critic = Deterministic checks first → if beneficial and zero‑cost resource available → query local Ollama/LM Studio (or monitored free‑tier API) with structured prompt → return structured CritiqueResult → Brain validates → existing owner corrects.**

### Best zero‑cost runtime critic: **Ollama** (locally installed, healthy model)
### Best zero‑cost independent critic: **Ollama vs LM Studio** (if both available and differ)
### Best zero‑cost development judge: **Gemini API free tier** (if quota allows and privacy cleared for non‑sensitive work)
### Best deterministic critic functions: **Requirement coverage analysis, Evidence sufficiency check, Contradiction detection via competing evidence**

### Paid‑token critic required: **NO**
### New architecture component required: **NO**

## Final principle
> Optimize for the strongest adequate criticism obtainable at zero incremental monetary cost, governed by existing Kalpavriksha intelligence, Evidence, privacy and authority. If no free model is adequate, do not spend; use deterministic quality controls and continue truthfully.