"""Layers 4-6 — reserved and future memory layers. Interfaces only.

Per Miracle 004's brief: "The implementation should only build Layers
1-3. Layers 4-6 remain interfaces or placeholders." Nothing in this file
is instantiated or wired into MasterAgentSession, the Memory facade, or
any other live code path — these exist so the eventual real
implementations have an agreed shape to grow into, without Layer 3's
schema or the Memory facade needing to change when they arrive. See
MEMORY_ARCHITECTURE.md §12 for how each is expected to evolve.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class KnowledgeMemory(ABC):
    """Layer 4 (Reserved) — durable facts/documents distinct from mission
    history (e.g. a learned founder preference stated in conversation
    rather than set via Memory.remember_preference, or an ingested
    document). Not mission-shaped, so it doesn't belong in Layer 3's
    schema. Not implemented in this Miracle."""

    @abstractmethod
    def remember_fact(self, topic: str, fact: str, source: str | None = None) -> None:
        ...

    @abstractmethod
    def recall_facts(self, topic: str) -> list[str]:
        ...


class VectorMemory(ABC):
    """Layer 5 (Future) — semantic recall over mission/knowledge history
    via local embeddings. ADR-0004 already anticipated this ("a local
    embedding index for semantic recall"). Deliberately absent from
    Layer 3's SQLite schema — adding it later means a new component that
    reads Layer 3's history and indexes it, not a Layer-3 migration."""

    @abstractmethod
    def index(self, record_id: str, text: str, metadata: dict[str, Any] | None = None) -> None:
        ...

    @abstractmethod
    def search(self, query: str, top_k: int = 5) -> list[str]:
        ...


class CloudSyncMemory(ABC):
    """Layer 6 (Optional future) — multi-device sync, explicitly opt-in
    and off by default (see PRODUCT_PRINCIPLES.md's privacy-first
    principle and ADR-0004's "arrive as an optional plugin, not a
    rewrite"). No implementation, no network calls, anywhere in this
    codebase today."""

    @abstractmethod
    def push(self, since: Any = None) -> None:
        ...

    @abstractmethod
    def pull(self) -> None:
        ...
