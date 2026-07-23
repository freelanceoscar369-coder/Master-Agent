# plugins/

External / installed plugins.

This is NOT the same as src/master_agent/plugins/ — that package holds
the built-in Plugin contract, registry, and core plugins (filesystem,
model providers) that ship with the engine and are covered by tests.

This top-level plugins/ is where a *future* plugin-distribution mechanism
(see ARCHITECTURE.md §6 and ADR-0003's open question about third-party
plugins) would drop externally-installed plugin packages at runtime,
without touching source code. Empty for now — Founder Edition has no
plugin marketplace/installer yet.
