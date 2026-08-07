"""The capability index (Mission Brief 039 Stage A2).

Two tiers, for one reason: a planning prompt carries the whole catalogue,
and MB038 measured what that costs — 1 095 prompt tokens and 78 s of
prefill for twenty-six capabilities. Putting every field of every full
contract into that prompt would multiply the number that already dominates
planning latency.

```
  IndexEntry     always loaded, one line each, goes in the prompt
  Contract       loaded on demand, for the one capability being checked
```

So the index carries what the Planner needs to *choose* and to *fill in
arguments*, and the full contract is fetched only when something asks a
question the summary cannot answer.

**Immutable once built.** Entries are a frozen mapping and the loader is
consulted at most once per capability. A registry that could change
underneath a plan would make the plan's premises unreproducible, and
MB032's replay guarantee depends on the opposite.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from master_agent.capabilities.contract import UNKNOWN, CapabilityContract


@dataclass(frozen=True)
class IndexEntry:
    """One line of the always-loaded index.

    Small on purpose. Everything here is something a Planner needs before
    it can write a step; everything else waits for the full contract.
    """

    canonical_id: str
    domain: str
    summary: str = ""
    risk_tier: str = UNKNOWN
    #: The arguments a call **must** carry. The single field that fixes
    #: MB036 Finding 4: without it the Planner was guessing names out of
    #: an English sentence.
    required_args: tuple[str, ...] = ()
    #: False when optional arguments exist that nobody has published, so a
    #: caller knows the list above is a floor rather than the whole story.
    args_complete: bool = False
    approval_required: bool = False
    side_effect: str = UNKNOWN

    @property
    def signature(self) -> str:
        """`Filesystem.CreateFolder(name)` — the one line a prompt needs."""
        args = ", ".join(self.required_args)
        tail = ", ..." if not self.args_complete and self.required_args else ""
        if not self.required_args:
            tail = "..." if not self.args_complete else ""
        return f"{self.canonical_id}({args}{tail})"

    def as_dict(self) -> dict[str, Any]:
        return {
            "canonical_id": self.canonical_id,
            "domain": self.domain,
            "summary": self.summary,
            "risk_tier": self.risk_tier,
            "required_args": list(self.required_args),
            "args_complete": self.args_complete,
            "approval_required": self.approval_required,
            "side_effect": self.side_effect,
        }


def entry_for(contract: CapabilityContract) -> IndexEntry:
    """Project a full contract down to its index line."""
    return IndexEntry(
        canonical_id=contract.canonical_id,
        domain=contract.domain,
        summary=contract.summary,
        risk_tier=contract.permissions.risk_tier,
        required_args=contract.inputs.required_names if contract.inputs.known else (),
        # A schema is only "complete" when it is both known *and* closed:
        # known-but-open means the required names are published and the
        # optional ones are not.
        args_complete=contract.inputs.known and contract.inputs.closed,
        approval_required=contract.permissions.approval_required,
        side_effect=contract.side_effect,
    )


@dataclass
class CapabilityIndex:
    """Every capability's summary, and its full contract on request.

    `loader` is a callable `canonical_id -> CapabilityContract | None`,
    consulted lazily and **memoised**, so a contract is built at most once
    and two reads of the same capability cannot disagree.

    Mutable as an object only because the memo cache fills; the *index*
    itself — which capabilities exist and what their entries say — is
    fixed at construction.
    """

    entries: tuple[IndexEntry, ...] = ()
    loader: Any = None
    _by_id: dict[str, IndexEntry] = field(default_factory=dict, init=False, repr=False)
    _contracts: dict[str, CapabilityContract] = field(
        default_factory=dict, init=False, repr=False
    )
    _missing: set[str] = field(default_factory=set, init=False, repr=False)

    def __post_init__(self) -> None:
        self._by_id = {entry.canonical_id: entry for entry in self.entries}

    # ---- the always-loaded tier ------------------------------------------

    def __len__(self) -> int:
        return len(self.entries)

    def __contains__(self, canonical_id: str) -> bool:
        return canonical_id in self._by_id

    def names(self) -> tuple[str, ...]:
        return tuple(entry.canonical_id for entry in self.entries)

    def entry(self, canonical_id: str) -> IndexEntry | None:
        return self._by_id.get(canonical_id)

    def in_domain(self, domain: str) -> tuple[IndexEntry, ...]:
        return tuple(entry for entry in self.entries if entry.domain == domain)

    def domains(self) -> tuple[str, ...]:
        return tuple(sorted({entry.domain for entry in self.entries}))

    def search(self, text: str) -> tuple[IndexEntry, ...]:
        """Substring match over id and summary, case-insensitive.

        Deliberately dumb. MB034 chose exact matching over stemming for
        its memory search because a founder can see why a plain match
        missed and cannot see why a clever one did; the same argument
        applies here.
        """
        needle = text.strip().lower()
        if not needle:
            return ()
        return tuple(
            entry
            for entry in self.entries
            if needle in entry.canonical_id.lower() or needle in entry.summary.lower()
        )

    # ---- the lazy tier ---------------------------------------------------

    def contract(self, canonical_id: str) -> CapabilityContract | None:
        """The full contract, loaded on first ask and remembered.

        `None` for a capability the index does not hold, or one whose
        loader produced nothing — absence reported rather than an empty
        contract, which would read as "takes no arguments".
        """
        if canonical_id in self._contracts:
            return self._contracts[canonical_id]
        if canonical_id in self._missing or canonical_id not in self._by_id:
            return None
        if self.loader is None:
            self._missing.add(canonical_id)
            return None

        loaded = self.loader(canonical_id)
        if loaded is None:
            self._missing.add(canonical_id)
            return None
        self._contracts[canonical_id] = loaded
        return loaded

    @property
    def loaded(self) -> tuple[str, ...]:
        """Which full contracts have actually been fetched. Exposed so the
        lazy tier's laziness is observable rather than assumed."""
        return tuple(sorted(self._contracts))

    # ---- reporting -------------------------------------------------------

    def unspecified(self) -> tuple[str, ...]:
        """Capabilities whose index entry publishes no required arguments
        and no completeness — the honest work list."""
        return tuple(
            entry.canonical_id
            for entry in self.entries
            if not entry.required_args and not entry.args_complete
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "count": len(self.entries),
            "domains": list(self.domains()),
            "entries": [entry.as_dict() for entry in self.entries],
        }


def build_index(contracts: tuple[CapabilityContract, ...] | list[CapabilityContract],
                loader: Any = None) -> CapabilityIndex:
    """Build the index once, at startup, from contracts already derived.

    Sorted by canonical id, always: the index goes into a planning prompt,
    and a prompt whose text depends on registration order would make the
    same objective produce a different plan on a different boot. The same
    determinism `catalogue_from()` established in MB036.
    """
    ordered = sorted(contracts, key=lambda contract: contract.canonical_id)
    return CapabilityIndex(
        entries=tuple(entry_for(contract) for contract in ordered),
        loader=loader,
    )
