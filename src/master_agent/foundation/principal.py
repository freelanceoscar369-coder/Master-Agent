"""Principal — who a thing is done *for*.

VEDA 04 defines this term and this module does not extend it:

- **M5 · Relational** — *"principals — the founder, delegates, their
  authorities and their own decision histories."*
- **R10** — *"The Bible assumes one founder. Delegation (C6) introduces a
  second principal, and if the data model assumes singularity, retrofitting
  will be expensive. Mitigation: model the principal as an entity now, even
  while only one exists."*
- **§2 Auth/identity** — *"Must represent delegates (CFO, Head of Eng) as
  approval principals, not merely as users."*

**A Principal is always a human authority.** The founder, or a delegate the
founder has named. There is no third kind, and in particular Kalpavriksha
is never a Principal.

## Why that last sentence is load-bearing

VEDA 01 §10: *"Every capability Kalpavriksha holds was granted, is visible,
and can be withdrawn instantly. Autonomy is lent, never earned in a way
that makes it permanent."*

If the system could be its own Principal it would hold authority nobody
granted and nobody can withdraw. Every receipt would name Kalpavriksha as
the actor, and the ledger would stop answering *"who authorized this?"* —
which is the only question it exists to answer. The execution log already
records which program ran.

So the Kernel's A5 attestation — *"Who is acting, and on whose authority?"*
— resolves to a founder or a delegate, always, or it refuses.

**A `system` kind was sketched in `SPRING_1_IMPLEMENTATION_PLAN.md` §5 C2
and is deliberately not implemented here.** It has no basis in VEDA 04 and
it is the same error in miniature: a non-human principal is Kalpavriksha
holding authority under another name.

## What this module is not

It is not identity for *runtime* — that is `ExecutionContext`, which
references a Principal and owns no authority of its own. It is not a
permission: the Permission System decides what a Principal may do. This
module only says who exists and what kind of authority they are.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PrincipalKind(str, Enum):
    """The two kinds VEDA 04 names. There is no third.

    Adding one is a constitutional amendment, not a code change — the set
    is closed for the same reason the workload vocabulary in MB038 is
    closed: an open enum is where a `system` principal quietly reappears.
    """

    FOUNDER = "founder"
    DELEGATE = "delegate"


class UnknownPrincipal(LookupError):
    """Raised when an id does not resolve.

    Fails closed by design, matching the Reversibility Registry's
    `classify()`. The Kernel's A5 attestation must refuse when no principal
    resolves; a registry that returned `None` would put that decision in
    every caller, and one caller eventually forgets.
    """


class InvalidPrincipalRegistry(ValueError):
    """Raised at construction for a registry that could not be correct.

    At construction rather than at first lookup: a registry with two
    founders or a duplicate id is a configuration error, and discovering it
    the first time someone approves something is the worst available
    moment.
    """


@dataclass(frozen=True)
class Principal:
    """One human authority.

    Immutable. A Principal's identity never changes — a founder who changes
    their display name is the same authority, and rewriting the record
    would silently restate who authorized every past action.
    """

    principal_id: str
    display_name: str
    kind: PrincipalKind

    def __post_init__(self) -> None:
        if not self.principal_id.strip():
            raise ValueError("principal_id must be a non-empty identifier")
        if not self.display_name.strip():
            raise ValueError(
                "display_name must be non-empty; a receipt naming an "
                "unnamed authority is not answerable"
            )

    @property
    def is_founder(self) -> bool:
        return self.kind is PrincipalKind.FOUNDER


class PrincipalRegistry:
    """Who exists. Nothing more.

    Holds no authority, grants nothing, and decides nothing — it answers
    *"is this a real principal, and which one?"* so the Kernel's A5
    attestation has something to resolve against.

    **Exactly one founder, always.** VEDA 01 §10 makes the founder's
    authority absolute and unconditional; two of them is not a richer model
    but an ambiguous one. Delegates are added alongside, which is the shape
    R10 asked for — a second principal costs a row, not a migration.
    """

    def __init__(self, founder: Principal, delegates: tuple[Principal, ...] = ()) -> None:
        if founder.kind is not PrincipalKind.FOUNDER:
            raise InvalidPrincipalRegistry(
                f"the founder principal must be of kind FOUNDER, got {founder.kind.value!r}"
            )

        for delegate in delegates:
            if delegate.kind is not PrincipalKind.DELEGATE:
                raise InvalidPrincipalRegistry(
                    f"{delegate.principal_id!r} is registered as a delegate but "
                    f"declares kind {delegate.kind.value!r}; there is exactly one founder"
                )

        everyone = (founder, *delegates)
        ids = [principal.principal_id for principal in everyone]
        duplicates = sorted({pid for pid in ids if ids.count(pid) > 1})
        if duplicates:
            raise InvalidPrincipalRegistry(f"duplicate principal ids: {duplicates}")

        self._founder = founder
        self._by_id: dict[str, Principal] = {p.principal_id: p for p in everyone}

    def founder(self) -> Principal:
        """The founder. Always present, by construction."""
        return self._founder

    def resolve(self, principal_id: str) -> Principal:
        """Look one up, or refuse.

        Raises rather than returning `None` so that a caller cannot proceed
        with an unresolved authority by forgetting a check.
        """
        try:
            return self._by_id[principal_id]
        except KeyError:
            raise UnknownPrincipal(
                f"no principal with id {principal_id!r}; "
                f"known principals: {sorted(self._by_id)}"
            ) from None

    def is_registered(self, principal_id: str) -> bool:
        """A non-raising check, for callers deciding whether to ask."""
        return principal_id in self._by_id

    def all_principals(self) -> tuple[Principal, ...]:
        """Founder first, then delegates in registration order."""
        return tuple(self._by_id.values())
