"""Desktop Intelligence · Part E — App Knowledge as a consulted *input*,
never an executor.

`AppKnowledgeProfile` is keyed by `provider_id`
(`ai_infrastructure.catalog.PROVIDER_CATALOG`); the Desktop Executive's own
application identity (`desktop/catalog.py::ApplicationSpec.key`, what
`observe_desktop(application=...)` actually receives) is a different join
key. `ProviderSpec.inventory_key` is the existing, already-declared bridge
between the two (the same join `providers/desktop_app.py::
_resolve_app_record()` already relies on) — this module reuses it rather
than inventing a second mapping.

**Consulted, never executed.** This module's only exported function
returns data (`AppKnowledgeProfile | None`); nothing in this package calls
any Desktop Executive action, ever. That is the whole of Part E's "App
Knowledge informs understanding; it does not control the machine" rule,
enforced simply by this module never importing anything from
`desktop/execution/` or `desktop/actions*.py` at all.
"""
from __future__ import annotations

from master_agent.ai_infrastructure.catalog import PROVIDER_CATALOG
from master_agent.app_knowledge.catalog import APP_KNOWLEDGE_CATALOG
from master_agent.app_knowledge.profile import AppKnowledgeProfile


def resolve_app_knowledge(application_key: str) -> AppKnowledgeProfile | None:
    """`application_key` is a `desktop/catalog.py` application key (e.g.
    `"chatgpt_desktop"`) — the same identity `observe_desktop()`'s own
    `application` parameter already carries. Returns `None` when no
    provider declares this `inventory_key`, or when a provider does but no
    `AppKnowledgeProfile` has been written for it yet — both are honest,
    ordinary outcomes (most catalogued applications have no profile at
    all), never an error."""
    for spec in PROVIDER_CATALOG:
        if spec.inventory_key == application_key:
            return APP_KNOWLEDGE_CATALOG.get(spec.provider_id)
    return None
