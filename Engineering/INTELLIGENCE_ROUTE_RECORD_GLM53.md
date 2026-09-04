# Free Intelligence Stack — route record: GLM-5.3-Flash

Recorded 2026-09-04. **Route-specific**, never flattened to a model verdict.
This model must NOT be stored as `GLM-5.3-Flash = PAID`, nor as permanently free.

```
intelligence: GLM-5.3-Flash

routes:

  ollama-cloud:
    availability:  available (model listed, Ollama 0.33.3, direct API 11434)
    identity:      glm5_next, 321,323,031,390 params, FP8, ctx 1,048,576
    economics:     PAID_NOT_ENTITLED
    evidence:      live /api/generate -> "requires a subscription or extra usage"

  ROUTE A - cline-harness -> ollama -> glm-5.3-flash:cloud   [FOUNDER SCREENSHOT ROUTE]
    reproduced:    TRUE, 2026-09-04. Not inferred -- run through the Cline
                   harness itself with BOTH provider and model pinned.
    config proof:  extension globalState still holds
                   planModeApiProvider/actModeApiProvider = "ollama",
                   plan/actModeOllamaModelId = "glm-5.3-flash:cloud", mode "act"
                   -- matching the screenshot's `ollama:glm-5.3-flash:cl...`
    live result:   finishReason=error, durationMs=507, totalCost=0
                   "this model requires a subscription or extra usage,
                    upgrade for access at https://ollama.com/upgrade"
    economics:     PAID_NOT_ENTITLED
    NOTE:          this is Route A only. It says NOTHING about the
                   Cline-native free promotion, which is a different route.

  openrouter:
    model_id:      z-ai/glm-5.3-flash
    economics:     PRICED (0.075 in / 0.25 out, per Cline stored model info)

  ROUTE B - cline-native FREE   [LIVE PROVEN 2026-09-04, TUI]
    session:       rotated via device OAuth (`cline auth cline`), "You are now
                   logged in to cline"; Chrome showed "Device connected"
    picker:        Provider "Cline Usage-Billing" -> category "Free" contains
                   DeepSeek V4 Flash / GLM-5.3-Flash / LongCat 2.0 / Laguna S 2.1
    display name:  GLM-5.3-Flash
    internal id:   glm-5.3-flash  (bare, as persisted by the TUI selection)
    live proof:    prompt -> "KALPAVRIKSHA_GLM53_CLINE_FREE_OK" returned verbatim
                   5,211 tokens, status bar "$0.00", no payment prompt,
                   auto-approve DISABLED, no tools used
    economics:     FREE (promotional/limited - client carries daily-limit and
                   promotion-ended states, so expiry uncertainty is RETAINED)
    ==> GLM53_CLINE_NATIVE_FREE_LIVE_PROVEN = TRUE

  ROUTE B-headless - SAME model, headless CLI   [BLOCKED]
    the CLI resolves the persisted free selection to `free/glm-5.3-flash`
    and the gateway answers 404:
      "failed to generate stream from Vercel: failed to invoke model
       'free/glm-5.3-flash' with streaming: request failed with status 404"
    explicit --model cline-free/glm-5.3-flash -> "model not found"
    explicit --model glm-5.3-flash            -> "invalid model format.
                                                  Expected format: modelType/model"
    So the free entitlement is reachable INTERACTIVELY but not through the
    headless surface in cline 3.0.61. All failures cost 0.
    ==> GLM53_CLINE_HEADLESS_FREE_PROVEN = FALSE (surface gap, not our config)

  cline-native:
    public_claim:  FREE (Founder cites Cline announcement, 26-27 Aug 2026, "Ox Alpha")
    model_id:      zai/glm-5.3-flash  (resolves under --provider cline)
    catalogue:     PRICED 0.15 in / 0.5 out, ctx 1,000,000
    free_namespace: cline-free/ EXISTS but contains only
                    cline-free/kat-coder-pro, cline-free/longcat-2.0
    live_state:    UNVERIFIED - account-scoped check not performed
    free_type:     UNDETERMINED (promotional vs limited)

  cline-cli:
    programmatic:  TRUE - cline 3.0.61, headless --json works WITHOUT a TTY
    blocker:       interactive surfaces (config, auth, /models) REQUIRE a TTY
    economics:     UNVERIFIED
    hazard:        DEFAULT MODEL IS PAID -- anthropic/claude-fable-5.1
                   at input 10 / output 50 under provider `cline`.
                   Any probe MUST pin --model or it spends real money.

  cline-api:
    endpoint:      https://api.cline.bot/api/v1/models (HTTP 200, 427 models)
    model_visible: TRUE (z-ai/glm-5.3-flash, :batch, z-ai/glm-5.3)
    free_entitlement: UNVERIFIED - endpoint exposes no pricing field at all

  cline-sdk (@cline/llms 0.0.82):
    every glm-5.3-flash record PRICED (0.165/0.55, 0.113/0.394, 0.201/0.5, 0.07/0.22)
    zero zero-cost glm-5.3 entries
```

## Confirmed free GLM in the current client

`coding-glm-5.1-free` — "Coding GLM 5.1 (free)", `family:"glm-free"`,
`pricing:{input:0,output:0,cacheRead:0,cacheWrite:0}`. That is **5.1, not 5.3**.

## Why this is not classified "promotion ended"

Per the Founder's own gate, four of five preconditions are met — CLI is current
(3.0.61, installed today), catalogue is fresh (same install), provider was
explicitly `cline`, and the model id resolves. The fifth is **not** met: the
account is not authenticated, and the free category is account-scoped, so a
server-side promotional entry would not appear in the bundled catalogue.

Correct classification:

```
CURRENT_CLIENT_CATALOGUE_LACKS_FREE_GLM53   (pending authenticated /models)
```

NOT `GLM-5.3-FLASH_PAID`. NOT `promotion ended`.

## Caution carried forward

A catalogue price of `0` does not prove entitlement. Ollama Cloud's own default
is a zero-priced bare id in the extension bundle, and its live API still
demanded payment. Only a live authenticated call settles economics.
