# Gemini Reasoning Provider — Build 2

Status: implemented and unit/integration-tested against a scripted
transport. Real-API validation is BLOCKED on a missing credential in
this environment (see below) — not committed to disk in code, and not
present as an environment variable here.

Founder decision (governing this build, not revisited): provider search
closed, Gemini API selected as the first genuinely programmatic reasoning
provider. Ollama stays disabled (RAM constraint). No paid fallback.

---

## Provider Architecture

Reused, unmodified: `AiCapabilityService`, `CapabilityBroker`,
`ProviderSource`, `PromptExecutor`, `Planner`, `PluginRegistry`,
`DecisionLedger`, the `ProviderDescriptor`/`ProviderSpec` schema, and the
`TaskProfile.exclude_providers` selection mechanism already proven for
`claude-desktop` in the prior reasoning-layer discovery session.

New, matching `providers/ollama.py`'s exact contract shape:

```
Task (capability="reasoning")
  → CapabilityBroker.select() — unchanged, policy-driven
  → winner = "gemini.api" (once Ollama is excluded / not competing)
  → PromptExecutor._locate() → PluginRegistry.get("gemini.api")
  → GeminiProvider.complete(prompt, context, budget, cancellation)
  → REST POST to generativelanguage.googleapis.com (no SDK dependency —
    same "urllib is enough for one POST" judgment ollama.py already made)
  → ProviderResult → Planner validates the JSON plan document
```

No new Broker, no new Router, no new Planner, no new selection path. The
provider only ever returns text; it never plans outside the Planner,
never touches the browser or desktop, never creates a Mission, never
bypasses Permissions.

## Files Changed

| File | Change |
|---|---|
| `src/master_agent/providers/gemini.py` (new) | `GeminiProvider(ModelProvider)` — manifest, availability, complete, generate. Mirrors `ollama.py` line for line in shape. |
| `src/master_agent/config.py` | New `GeminiConfig` dataclass (`enabled`, `api_key`, `model`, `base_url`, `timeout_seconds`); wired into `MasterAgentConfig`; `load_config()` reads `GEMINI_API_KEY` from the environment — the one place this module touches `os.environ`. |
| `src/master_agent/ai_infrastructure/catalog.py` | New `ProviderSpec(provider_id="gemini.api", ...)` entry — `needs_credentials=True`, `cost_per_call=0.0`, `capabilities={reasoning, reasoning.planning, coding}`, `locality=cloud`. |
| `src/master_agent/launcher/boot.py` | Registers `GeminiProvider` beside `OllamaProvider`, gated by `config.gemini.enabled`; boot-report detail string extended to name every registered provider's model/address rather than assuming exactly one. |
| `tests/test_ollama_provider.py` | One test's accepted-marker list extended (`"Gemini API Provider"`) — the same pattern already used when MB038 added `budget.py`; the test's own intent (every provider module states its identity) is unchanged. |
| `tests/test_provider_execution.py` | One test's config fixture updated to also disable Gemini, since "no provider enabled" now requires disabling two independently-configurable providers, not one; one test needed no change once the boot-report detail string was fixed to name Ollama's model/address again. |
| `tests/test_gemini_provider.py` (new) | 19 unit tests against a scripted transport. |
| `tests/test_gemini_broker_integration.py` (new) | 8 tests: catalog discovery, capability declaration, eligibility gating, Ollama-exclusion Broker selection, and two full Planner→Broker→Gemini→plan / Planner→Broker→Gemini→refusal tests. |

No other file touched. `FixedBottleServer`, `debug_log`, the pre-existing
`boot.py` step-order issue, Founder Edition, and the removed
`_try_action()`/`_handle_local_query()` were not revisited.

## Configuration Required

**Environment variable: `GEMINI_API_KEY`** — not currently set in this
environment (`False` on inspection; no secret was written to disk or
committed). Once set, `load_config()` populates
`GeminiConfig.api_key` automatically; no code change needed to activate
it.

Two additional, deliberate founder-facing switches, both already correct
by default and requiring an explicit founder act to turn on for real use:

- `BrokerConfig.enabled_cloud_providers` must include `"gemini.api"`
  before the Broker will report it *available* (unchanged existing
  mechanism — "absence of a key is a fact, not a reason to try anyway").
- `GeminiConfig.model` defaults to `gemini-2.0-flash` — free-tier-eligible
  as of this writing; override in one place if the founder's tier or
  Google's offering changes.

## Model

`gemini-2.0-flash`, documented in both `providers/gemini.py`'s
`DEFAULT_MODEL` constant and `config.py`'s `GeminiConfig.model` docstring.
A configuration value, never a hardcoded assumption baked into logic —
the same discipline `OllamaConfig.model` already states.

## Broker Registration

**PASS.** `gemini.api` is discovered in `PROVIDER_CATALOG`
(`test_gemini_is_discovered_in_the_provider_catalog`), declares
`reasoning` (`test_gemini_declares_reasoning`), is correctly reported
unavailable until the founder enables it
(`test_gemini_is_unavailable_until_the_founder_enables_it`) and available
once they do (`test_gemini_is_eligible_once_the_founder_enables_it`).

## Ollama Exclusion

**PASS.** `test_broker_selects_gemini_when_ollama_is_excluded` proves the
Broker selects `gemini.api` when `ollama.local` is excluded via the
existing `TaskProfile.exclude_providers` field.
`test_ollama_exclusion_is_respected_even_when_gemini_is_not_configured`
proves the exclusion holds even when Gemini itself is not yet configured
— excluding Ollama never silently falls back to Ollama anyway. Ollama was
never enabled, started, or registered for execution anywhere in this
build.

## Paid Fallback

**DISABLED.** Nothing in `GeminiProvider`, the Broker wiring, or the
catalog entry falls back to a different provider on failure — a refusal
is returned as data (`ProviderResult`/`PlanRefusal`), exactly matching
MB033 Rule 5 (never silently substitute). `openai.api`/`openrouter.api`
remain untouched, unregistered, and absent from
`enabled_cloud_providers` by default.

## Error Handling

| Case | Outcome | Evidence |
|---|---|---|
| Missing API key | `UNAVAILABLE`, no network call attempted | `test_missing_api_key_is_reported_as_unavailable_without_a_network_call` |
| Authentication failure (401) | `REJECTED`, API's own message surfaced | `test_authentication_failure_is_rejected_with_the_api_message` |
| Rate limit / quota exhaustion (429) | `REJECTED`, API's own message surfaced, no fallback | `test_rate_limit_is_reported_as_rejected_with_the_reason`, `test_quota_exhaustion_never_falls_back_to_a_different_provider` |
| Network unreachable | `UNAVAILABLE` | `test_an_unreachable_endpoint_is_reported_as_unavailable` |
| Timeout | `TIMED_OUT` | `test_a_timeout_is_reported_as_timed_out` |
| Non-JSON body | `MALFORMED` | `test_a_non_json_body_is_malformed` |
| Empty/no candidates | `MALFORMED` (never a silent empty success) | `test_json_with_no_candidates_is_malformed`, `test_a_result_with_no_readable_text_is_malformed_not_a_silent_empty_success` |

All outcomes reuse the existing `providers/response.py` vocabulary
(`UNAVAILABLE`, `REJECTED`, `TIMED_OUT`, `MALFORMED`) — no second error
taxonomy was introduced.

## Test Results

```
tests/test_gemini_provider.py .................... 19 passed
tests/test_gemini_broker_integration.py ........ 8 passed
```

Full regression (`test_ollama_provider.py`, `test_provider_execution.py`,
`test_provider_registry.py`, `test_launcher.py`, plus the two new files):
**340 passed, 2 failed.** Both remaining failures
(`test_the_whole_definition_of_done_holds_end_to_end`,
`test_an_execution_survives_a_restart`) trace to the same pre-existing,
out-of-scope cause: `AttributeError: 'InstalledProbe' object has no
attribute 'get_store_apps'`, from `desktop/inventory.py`'s uncommitted
"store-app" modification (confirmed absent from `git show HEAD` — present
only in this session's already-known, already-flagged, out-of-scope
working-tree state, unrelated to anything in this build). Not touched,
per this mission's explicit instruction.

## Real Runtime Validation

**BLOCKED.** No `GEMINI_API_KEY` is set in this environment. Per this
mission's own instruction (§4), no secret was invented, requested
insecurely, or worked around. The full chain up to the network boundary
is proven with a scripted transport
(`test_planner_produces_a_plan_when_gemini_answers_with_a_valid_plan_document`
— a realistic Gemini response body, parsed by the real `GeminiProvider`,
selected by the real `CapabilityBroker`, validated by the real
`Planner`). Once `GEMINI_API_KEY` is set in the environment, the same
harness this build's integration tests use can be pointed at a real
`UrllibTransport()` (the default) instead of `FakeTransport` to complete
this step — no code change required.

## Cost / Free-Tier Assumption

`cost_per_call=0.0` in the catalog, matching the Founder's stated
selection reason (a free tier suitable for initial reasoning). No paid
API call was made or is reachable through any path this build adds. If
the free tier is exhausted, Gemini returns HTTP 429, which
`GeminiProvider` reports as a clean `REJECTED` refusal — visible to the
founder, never silently absorbed or retried into a charge.

## Future-Provider Compatibility

Confirmed by construction, not merely claimed: adding a next provider
(OpenRouter, Groq, Qwen, Mistral, DeepSeek) requires exactly what adding
Gemini required — one `ProviderSpec` entry, one small adapter matching
`ModelProvider`'s contract, one registration block in `launcher/boot.py`
gated by its own config flag. Zero changes to the Broker, the Planner, the
Capability Registry, or Mission Control for this build; the same would
hold for the next one.
