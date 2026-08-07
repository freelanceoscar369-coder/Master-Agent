"""Provider execution — the one layer in Kalpavriksha that talks to an AI
(Mission Brief 033).

```
    Broker decides  ->  ai_infrastructure invokes  ->  providers/ execute
    (never executes)    (never decides)               (never decide)
```

**This package re-exports nothing, on purpose.** Importing
`master_agent.providers` must not pull in a network client, so a caller
imports the submodule it actually needs:

    from master_agent.providers.response import ProviderResult   # pure data
    from master_agent.providers.ollama import OllamaProvider     # touches HTTP

That distinction is what lets the AI Infrastructure layer record an
execution without acquiring the ability to perform one — it imports
`response` and nothing else, which a test asserts. A convenience
`__init__` that imported everything would quietly delete that property.

**Not to be confused with `plugins/providers/`**, which holds two
scaffolding stubs from MB001 that raise `NotImplementedError` and predate
the Broker entirely. They live in a package frozen since MB025 and were
left untouched; this is where a provider that actually runs lives.
"""
