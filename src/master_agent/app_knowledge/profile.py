"""App Knowledge Profile — a reusable, inspectable record of how one
desktop application's interface actually works, built *before* any live
automation targets it.

**What this is.** A generic, vendor-neutral data model. Every field it
carries is data, not code — no `if app_id == "chatgpt-desktop"` branch
lives here or anywhere this module is consumed. The whole point is to
stop *re-deriving* the same facts about the same application, live, over
and over across missions — this session's own history is the evidence:
"Chat" vs "Work"/"Codex" tabs, a composer's own placeholder text baked
into its accessibility tree, stale unsent drafts surviving a restart,
inactive tabs staying mounted-but-hidden — each was discovered live, more
than once, before being written down anywhere reusable. This package is
where that goes from now on.

**What this is not.** Not a replacement for generic UI discovery. A
profile *informs* — narrows the search, sets expectations, flags known
traps — the same `find()`/`find_composer()`/`click()`/`write_text()`
primitives in `desktop/execution/uia_control.py` still do the actual
work, at runtime, against whatever the application's real, current state
turns out to be. A profile that turns out to be wrong is a reason to
correct the profile, never a reason to trust it over what the live UI
tree actually shows.

**Knowledge types, never conflated.** Every `Fact` is exactly one of:

- `DOCUMENTED` — read from an official source (help docs, README,
  in-app About/Help) and cited by `source`.
- `OBSERVED` — confirmed by safe, read-only inspection of the real,
  running application; `source` names how (e.g. "live UIA read,
  2026-08-13").
- `INFERRED` — a reasoned guess, not yet confirmed either way; `source`
  explains the reasoning. Must never be presented or consumed as if it
  were `OBSERVED` or `DOCUMENTED`.
- `UNKNOWN` — genuinely not yet investigated, or investigated and
  inconclusive. A profile is allowed — expected — to carry these
  honestly rather than guess.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class KnowledgeType(Enum):
    DOCUMENTED = "documented"
    OBSERVED = "observed"
    INFERRED = "inferred"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Fact:
    """One answered (or honestly unanswered) question about an
    application. `source` is never optional: a `DOCUMENTED` fact without
    a citation is indistinguishable from a guess, an `OBSERVED` fact
    without a description of *how* it was observed cannot be
    re-verified, and even an `UNKNOWN` fact should say what was tried."""

    value: object
    knowledge_type: KnowledgeType
    source: str
    note: str = ""

    def __post_init__(self) -> None:
        if not self.source.strip():
            raise ValueError("a Fact must always carry a non-empty source")

    @property
    def is_confirmed(self) -> bool:
        """`True` only for `DOCUMENTED`/`OBSERVED` — the two knowledge
        types safe to act on directly. `INFERRED` and `UNKNOWN` are
        never confirmed, by construction; a caller deciding whether it
        can *trust* a fact should check this, not merely check that a
        `Fact` object exists."""
        return self.knowledge_type in (KnowledgeType.DOCUMENTED, KnowledgeType.OBSERVED)


def unknown(note: str = "not yet investigated") -> Fact:
    """The honest default for a field nobody has looked at yet —
    profiles are built incrementally, and an unexamined question should
    read as `UNKNOWN`, never be silently omitted or guessed at."""
    return Fact(value=None, knowledge_type=KnowledgeType.UNKNOWN, source=note)


@dataclass(frozen=True)
class AppKnowledgeProfile:
    """One application's knowledge profile. Field names mirror the
    mission's own question list verbatim, so a reader can check "did we
    answer every question we were asked" by eye. `provider_id` is the
    join back to `ai_infrastructure.catalog.PROVIDER_CATALOG` — the same
    join key every other per-application record in this codebase already
    uses, not a second identity scheme."""

    provider_id: str
    label: str
    last_reviewed: str  # a plain date string the profile's author sets by hand

    chat_interface: Fact = field(default_factory=unknown)
    other_modes: Fact = field(default_factory=unknown)
    new_session_creation: Fact = field(default_factory=unknown)
    can_rename_chat: Fact = field(default_factory=unknown)
    dedicated_session_strategy: Fact = field(default_factory=unknown)
    composer_exposure: Fact = field(default_factory=unknown)
    send_representation: Fact = field(default_factory=unknown)
    enter_submits: Fact = field(default_factory=unknown)
    response_exposure: Fact = field(default_factory=unknown)
    persists_unsent_drafts: Fact = field(default_factory=unknown)
    inactive_tabs_in_uia_tree: Fact = field(default_factory=unknown)
    visibility_distinguishing_properties: Fact = field(default_factory=unknown)
    loading_reconnection_states: Fact = field(default_factory=unknown)
    safe_active_session_indicator: Fact = field(default_factory=unknown)

    def all_facts(self) -> dict[str, Fact]:
        """Every named question, mapped to its current answer — the
        mechanism `merge_observations()` and the audit report both use
        to walk the whole profile generically, without hand-listing
        fields a second time."""
        return {
            "chat_interface": self.chat_interface,
            "other_modes": self.other_modes,
            "new_session_creation": self.new_session_creation,
            "can_rename_chat": self.can_rename_chat,
            "dedicated_session_strategy": self.dedicated_session_strategy,
            "composer_exposure": self.composer_exposure,
            "send_representation": self.send_representation,
            "enter_submits": self.enter_submits,
            "response_exposure": self.response_exposure,
            "persists_unsent_drafts": self.persists_unsent_drafts,
            "inactive_tabs_in_uia_tree": self.inactive_tabs_in_uia_tree,
            "visibility_distinguishing_properties": self.visibility_distinguishing_properties,
            "loading_reconnection_states": self.loading_reconnection_states,
            "safe_active_session_indicator": self.safe_active_session_indicator,
        }

    def unresolved_questions(self) -> list[str]:
        """Field names still `UNKNOWN` — the audit report's own "what
        remains unknown" section is this, not a hand-maintained list."""
        return [name for name, fact in self.all_facts().items()
                if fact.knowledge_type is KnowledgeType.UNKNOWN]

    def merge_observations(self, observed: dict[str, Fact]) -> "AppKnowledgeProfile":
        """Return a new profile with the given fields replaced by freshly
        `OBSERVED` (or re-confirmed) facts — immutable, like every other
        `@dataclass(frozen=True)` record in this codebase; acquisition
        never mutates a profile in place. Only fields actually named in
        `observed` change; everything else (including prior `DOCUMENTED`
        knowledge) is preserved untouched. A caller passing a fact whose
        `knowledge_type` is not `OBSERVED` is a caller misusing this
        method — acquisition results are observations, by definition."""
        for field_name, fact in observed.items():
            if field_name not in self.all_facts():
                raise ValueError(f"{field_name!r} is not a known profile field")
            if fact.knowledge_type is not KnowledgeType.OBSERVED:
                raise ValueError(
                    f"merge_observations() only accepts OBSERVED facts, "
                    f"got {fact.knowledge_type} for {field_name!r}"
                )
        import dataclasses
        return dataclasses.replace(self, **observed)
