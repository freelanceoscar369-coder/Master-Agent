"""The six data contracts C22 produces. Declarations only — no derivation.

Every type here is frozen and JSON-projectable, for the same reason every
value in `foundation/` is: these describe a moment that has passed, and a
snapshot a consumer can edit is not a snapshot.

**Nothing in this file reads a machine.** The derivations live in
`derive.py`; this file is the shape of what they return.

## The vocabulary is this layer's own

No name here is borrowed from the Kernel. `Warrant`, `Attestation`,
`Receipt`, `RefusalReason` and the rest belong to C1–C15 and mean
something exact; nothing in an environment reading is any of them. The one
word that could collide — `Coverage`, which C19 owns for vigilance — is
deliberately not used.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from master_agent.environment_intelligence.evidence import (
    Availability,
    Inference,
)


class ToolState(str, Enum):
    """What the inventory says about one application. Closed.

    Mirrors the scanner's own three-way answer rather than inventing a
    fourth: `desktop/inventory.py` reports installed, missing, or present
    but unusable, and this layer does not re-decide any of them.
    """

    #: Installed and the scanner could use it.
    USABLE = "usable"

    #: Installed, and the scanner found it broken or unreadable.
    UNUSABLE = "unusable"

    #: Not found on PATH or at any known install path.
    ABSENT = "absent"

    #: The catalog has no entry, so the scanner never looked.
    UNCATALOGUED = "uncatalogued"


@dataclass(frozen=True)
class ToolObservation:
    """One application, as read from the inventory. Facts only.

    `running` is process-list evidence and nothing more. **No window title
    is ever read** — a browser's window title is the page the founder is
    on, and reading it would be inspecting browsing.
    """

    key: str
    label: str
    state: ToolState
    running: bool
    version: str | None = None

    @property
    def installed(self) -> bool:
        return self.state in (ToolState.USABLE, ToolState.UNUSABLE)

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "state": self.state.value,
            "running": self.running,
            "version": self.version,
        }


# ─────────────────────────── 1 · browsers ──────────────────────────────


@dataclass(frozen=True)
class BrowserProfile:
    """What is known about the founder's browsers.

    Three of the brief's four questions are answerable from a machine
    inventory; one is not, and says so rather than guessing. See
    `derive.py` for which and why.
    """

    browsers: tuple[ToolObservation, ...] = ()

    #: Which browser the evidence points to. `UNKNOWN` when several are
    #: installed and nothing distinguishes them.
    preferred: Inference | None = None

    #: The OS default handler. Requires a registry or xdg lookup the
    #: scanner does not perform, so this is `UNKNOWN` by construction.
    default: Inference | None = None

    #: Running now, from the process list. Never from history or titles.
    active: Inference | None = None

    def installed(self) -> tuple[ToolObservation, ...]:
        return tuple(b for b in self.browsers if b.installed)

    def as_dict(self) -> dict[str, Any]:
        return {
            "browsers": [b.as_dict() for b in self.browsers],
            "preferred": None if self.preferred is None else self.preferred.as_dict(),
            "default": None if self.default is None else self.default.as_dict(),
            "active": None if self.active is None else self.active.as_dict(),
        }


# ─────────────────────────── 2 · AI ecosystem ──────────────────────────


@dataclass(frozen=True)
class WebAIAccess:
    """Whether a web-based AI service is reachable, and nothing else.

    **The three-value vocabulary is the whole contract.** No account, no
    session token, no cookie contents, no conversation, no history. The
    brief permits `available | unknown | unavailable` and this type cannot
    express anything more even if a future caller wanted it to.
    """

    service: str
    availability: Availability
    inference: Inference

    def as_dict(self) -> dict[str, Any]:
        return {
            "service": self.service,
            "availability": self.availability.value,
            "inference": self.inference.as_dict(),
        }


@dataclass(frozen=True)
class AIToolProfile:
    """The AI ecosystem: what is on the machine, and what is reachable."""

    #: Locally installed AI applications, from the inventory.
    tools: tuple[ToolObservation, ...] = ()

    #: Which the evidence points to. `UNKNOWN` when several run at once.
    preferred: Inference | None = None

    #: Web services, each `available | unknown | unavailable`.
    web_access: tuple[WebAIAccess, ...] = ()

    def local(self) -> tuple[ToolObservation, ...]:
        return tuple(t for t in self.tools if t.installed)

    def running(self) -> tuple[ToolObservation, ...]:
        return tuple(t for t in self.tools if t.running)

    def as_dict(self) -> dict[str, Any]:
        return {
            "tools": [t.as_dict() for t in self.tools],
            "preferred": None if self.preferred is None else self.preferred.as_dict(),
            "web_access": [w.as_dict() for w in self.web_access],
        }


# ─────────────────────────── 3 · capability graph ──────────────────────


@dataclass(frozen=True)
class CapabilityNode:
    """One thing the environment can do, or one thing that provides it."""

    key: str
    label: str
    #: What put this node in the graph.
    inference: Inference

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "inference": self.inference.as_dict(),
        }


@dataclass(frozen=True)
class CapabilityEdge:
    """`source` enables `target`, because of `inference`.

    **Only evidenced edges exist.** The brief's illustrative chain —
    Claude Desktop → MCP → Filesystem → Trading Repository — is built only
    as far as the inventory supports it, and stops where the evidence
    stops. An edge nobody can justify is not drawn.
    """

    source: str
    target: str
    inference: Inference

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "inference": self.inference.as_dict(),
        }


@dataclass(frozen=True)
class CapabilityGraph:
    """What this environment can do, and why it can do it."""

    nodes: tuple[CapabilityNode, ...] = ()
    edges: tuple[CapabilityEdge, ...] = ()

    def node(self, key: str) -> CapabilityNode | None:
        for candidate in self.nodes:
            if candidate.key == key:
                return candidate
        return None

    def edges_from(self, key: str) -> tuple[CapabilityEdge, ...]:
        return tuple(e for e in self.edges if e.source == key)

    def reaches(self, source: str, target: str) -> bool:
        """Whether a chain of evidenced edges connects the two.

        Breadth-first over the edges that exist. Returns `False` rather
        than assuming a link the evidence does not draw.
        """
        seen: set[str] = set()
        frontier = [source]
        while frontier:
            current = frontier.pop()
            if current == target:
                return True
            if current in seen:
                continue
            seen.add(current)
            frontier.extend(e.target for e in self.edges_from(current))
        return False

    def as_dict(self) -> dict[str, Any]:
        return {
            "nodes": [n.as_dict() for n in self.nodes],
            "edges": [e.as_dict() for e in self.edges],
        }


# ─────────────────────────── 4 · user profile ──────────────────────────


class ProfileKind(str, Enum):
    """The brief's six, closed."""

    DEVELOPER = "developer"
    CREATOR = "creator"
    OFFICE_USER = "office_user"
    TRADER = "trader"
    RESEARCH_USER = "research_user"
    MIXED = "mixed"


@dataclass(frozen=True)
class UserProfile:
    """What kind of environment this is.

    The brief's rule is a hard one: *"Never infer from a single
    application alone."* `derive.py` enforces it by requiring at least two
    distinct applications before any kind is named, and the inference
    carries both.
    """

    kind: Inference

    #: Every profile the evidence partially supports, strongest first.
    considered: tuple[Inference, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.as_dict(),
            "considered": [c.as_dict() for c in self.considered],
        }


# ─────────────────────────── 5 · preferences ───────────────────────────


@dataclass(frozen=True)
class PreferenceModel:
    """What the founder appears to prefer, and why.

    Four preferences, each an `Inference`, each carrying confidence,
    reason and evidence. Determined without asking, and explainable — the
    brief requires both halves.
    """

    editor: Inference
    browser: Inference
    ai: Inference
    terminal: Inference

    def as_dict(self) -> dict[str, Any]:
        return {
            "editor": self.editor.as_dict(),
            "browser": self.browser.as_dict(),
            "ai": self.ai.as_dict(),
            "terminal": self.terminal.as_dict(),
        }


# ─────────────────────────── 6 · summary ───────────────────────────────


@dataclass(frozen=True)
class EnvironmentSummary:
    """Structured observations, and the readiness signals C20 can read.

    **Observations, never recommendations.** `desktop/inventory.py` draws
    this line already — *"'Ollama not installed.' is a fact. 'Install
    Ollama.' is advice"* — and this layer holds it. Nothing here suggests,
    advises, ranks or urges.
    """

    #: One fact per line. No advice, no adjectives, no AI-authored prose.
    observations: tuple[str, ...] = ()

    #: The three signals the C22 brief names for C20 Presence.
    environment_ready: Inference | None = None
    ai_available: Inference | None = None
    developer_environment_healthy: Inference | None = None

    def as_dict(self) -> dict[str, Any]:
        def maybe(value: Inference | None) -> dict[str, Any] | None:
            return None if value is None else value.as_dict()

        return {
            "observations": list(self.observations),
            "environment_ready": maybe(self.environment_ready),
            "ai_available": maybe(self.ai_available),
            "developer_environment_healthy": maybe(
                self.developer_environment_healthy
            ),
        }


# ─────────────────────────── the root ──────────────────────────────────


#: The six sections a reading is divided into. Named so that comparing two
#: readings reports *which* understanding changed rather than "something
#: did" — see `EnvironmentIntelligence.changes_from`.
SECTIONS: tuple[str, ...] = (
    "browsers",
    "ai",
    "graph",
    "profile",
    "preferences",
    "summary",
)


@dataclass(frozen=True)
class EnvironmentIntelligence:
    """Everything C22 derives, in one immutable value.

    Produced by `derive_intelligence()` from a `MachineInventory` the
    Desktop Executive already captured. This layer performs no scan, holds
    no probe, and cannot reach the machine.

    ## Designed to be refreshed, without refreshing itself

    This is a **reading**, not a live view: it describes the machine as of
    `captured_at` and never changes afterwards. A later understanding is a
    *new* reading derived from a *new* inventory, and the two coexist.

    Three properties make continuous refresh possible later, and all three
    are structural rather than behavioural:

    **Immutable and self-dated.** Two readings can be held at once and
    told apart, and a consumer holding an older one cannot have it change
    underneath them.

    **Derived by a pure function.** Refreshing is calling
    `derive_intelligence()` again — no state to reset, no cache to
    invalidate, no warm-up.

    **Comparable.** `is_newer_than` and `changes_from` let a caller act on
    *what changed* rather than re-reading everything.

    **No refresh is implemented here, deliberately.** There is no
    scheduler, no timer, no polling loop, no cache and no subscription —
    those would be behaviour, and this layer has none. Whoever owns the
    cadence owns the loop; this only makes the loop cheap to write.

    The same shape the Presence Layer already expects: it consumes
    snapshots it did not produce and cannot reach back into.
    """

    browsers: BrowserProfile
    ai: AIToolProfile
    graph: CapabilityGraph
    profile: UserProfile
    preferences: PreferenceModel
    summary: EnvironmentSummary

    #: The moment the underlying inventory was captured — carried from it,
    #: never read from a clock here.
    captured_at: datetime | None = None

    #: Applications the brief names that the catalog has no entry for, so
    #: the scanner never looked. Surfaced rather than silently absent.
    uncatalogued: tuple[str, ...] = field(default_factory=tuple)

    # ---- the refresh seam · comparison only, never a loop --------------

    def is_newer_than(self, other: EnvironmentIntelligence) -> bool:
        """Whether this reading describes a later moment than `other`.

        Compares the two `captured_at` values — **the inventory's own
        moments, not a clock read here.** A reading whose inventory
        carried no timestamp is never newer than anything, because
        "unknown when" cannot be ordered against "known when".

        This exists so a future refresh loop can discard a late-arriving
        stale reading without inventing an ordering of its own.
        """
        if self.captured_at is None or other.captured_at is None:
            return False
        return self.captured_at > other.captured_at

    def changes_from(
        self, previous: EnvironmentIntelligence
    ) -> tuple[str, ...]:
        """Which of the six sections differ from an earlier reading.

        Returns section names in `SECTIONS` order, so a caller can act on
        *what* the machine now means differently rather than diffing two
        projections by hand. An empty tuple means the understanding is
        unchanged even if the moment is not.

        Pure comparison. It notifies nobody, schedules nothing and mutates
        neither reading — the refresh cadence belongs to the caller.
        """
        return tuple(
            name
            for name in SECTIONS
            if getattr(self, name) != getattr(previous, name)
        )

    def as_dict(self) -> dict[str, Any]:
        """Deterministic, JSON-ready. Fixed key order.

        This projection is the data contract C20 Presence consumes. It
        carries no prose beyond `summary.observations`, which are facts.
        """
        return {
            "browsers": self.browsers.as_dict(),
            "ai": self.ai.as_dict(),
            "graph": self.graph.as_dict(),
            "profile": self.profile.as_dict(),
            "preferences": self.preferences.as_dict(),
            "summary": self.summary.as_dict(),
            "captured_at": (
                None if self.captured_at is None else self.captured_at.isoformat()
            ),
            "uncatalogued": list(self.uncatalogued),
        }
