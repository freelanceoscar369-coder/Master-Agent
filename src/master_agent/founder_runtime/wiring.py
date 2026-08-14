"""The Founder Runtime — composition, projection, and one door out.

```
   C22 Environment Intelligence      C19 Vigilance      Conversation Memory
              │                            │                     │
              └──────────────┬─────────────┴──────────┬──────────┘
                             ▼                        ▼
                    C23 Founder Runtime  ←  composition · projection
                             │
                             ▼   one envelope, JSON only
                    C20 Presence Layer  →  PresenceSnapshot
                             │
                             ▼
                    C21 Founder Surface
```

## What it is

> **A composition root with a door.** It holds what it was handed, projects
> what those things already publish, and answers questions about the result.
> It derives nothing, decides nothing, and reaches nothing.

Every rule below is structural rather than promised, and each has a test:

| Never | Prevented by |
|---|---|
| Execute anything | It holds no executor, no gateway, no plugin and no action |
| Authorize anything | It holds no Kernel; `authorize`/`attempt`/`settle` are unreachable |
| Call a model | It imports no provider, no broker and no router |
| Invent a response | The conversation projection cannot emit an `assistant` role |
| Derive presence | It emits observations; the snapshot is C20's and stays C20's |
| Re-derive the environment | `environment` is C22's own `as_dict()`, unchanged |
| Mutate anything it was given | It calls no setter and returns only new dicts |

## Why it does not hold the Kernel

C18's Runtime Bridge is the door to **authority** — `authorize`, `attempt`,
`settle`, `invalidate`, `status`. This door is the door to **observation**,
and the two are kept apart deliberately: a surface that holds a Kernel
reference can authorize, whatever its docstring says, and one that holds
none cannot. So the founder runtime imports no frozen package, and a test
walks its imports to keep that true.

The consequence is stated rather than hidden: **nothing the founder does on
this surface can start work.** Sending a message, approving a request and
cancelling an execution all travel the Runtime Bridge, and none of them is
reachable here. `sources()` says so in as many words, so a surface can
report its own connectivity truthfully instead of inferring it from a call
that quietly did nothing.

## The wire shape is C18's, not a new one

```
   in    {"operation": "snapshot"}
   out   {"operation": "snapshot", "kind": "ok", "payload": {…}}
   out   {"operation": "snapshot", "kind": "error", "payload": {"type", "message"}}
```

Same three keys, same convention that an error carries **its own class
name** rather than a transport taxonomy. The operation set is this door's
own and is closed — the two enums are separate because sharing one would
mean a founder envelope could name `authorize`, and the whole point of the
split is that it cannot.

**No status code, no envelope version, no request id, no timestamp** —
C18's reason holds here unchanged: a wire field nobody reads is a field
somebody will eventually depend on.

## Absence

Every section this runtime was not given arrives as `null`, and `sources`
says which, and why, in the words of whichever component was missing. This
follows the discipline MB032 established for the same class of problem:
*"nothing has scanned yet"* is reported as absence rather than assumed
present. A surface can render the difference; it cannot render a guess.

## Determinism

No clock, no `uuid4()`, no randomness, no thread, no timer, no queue, no
cache and no I/O. Two calls with the same inputs return equal dictionaries,
which is what lets the whole envelope be asserted byte-for-byte in a test.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any

from master_agent.environment_intelligence import EnvironmentIntelligence
from master_agent.founder_runtime.presence_feed import PresenceFeed, presence_feed
from master_agent.founder_runtime.projection import (
    conversation_projection,
    environment_projection,
)
from master_agent.memory.conversation import ConversationMemory
from master_agent.vigilance import Coverage, DomainRegistry

#: The envelope key naming which operation is asked for. C18's word.
OPERATION = "operation"

#: The envelope key carrying arguments. Present for shape compatibility with
#: C18; every operation here is nullary, so a non-empty map is refused
#: rather than ignored — a caller passing one expects something this door
#: does not do.
ARGUMENTS = "arguments"


class FounderOperation(str, Enum):
    """What this door answers. Closed, and deliberately not C17's enum.

    Sharing `Operation` would let a founder envelope name `authorize`.
    These five are observation only, and there is no sixth that executes.
    """

    #: Everything below, in one round trip. What a surface actually wants.
    SNAPSHOT = "snapshot"

    #: C22's projection alone.
    ENVIRONMENT = "environment"

    #: The observation feed C20 folds in, plus C19's coverage verbatim.
    PRESENCE = "presence"

    #: Session turns in the surface's row shape.
    CONVERSATION = "conversation"

    #: What is wired, what is not, and why. Never fails.
    STATUS = "status"


class ResultKind(str, Enum):
    """Two outcomes. C17's convention, and its vocabulary is not imported.

    There is no `refused` here on purpose: refusal is a constitutional
    answer the Kernel gives, and an observation door that could produce
    one would be claiming an authority it does not have.
    """

    OK = "ok"
    ERROR = "error"


class InvalidFounderEnvelope(ValueError):
    """The envelope was malformed. Not a refusal, and never recorded as one.

    C9's distinction, followed rather than restated: *"a request that is
    merely malformed is not a constitutional refusal and must not become
    one."* Nothing here reaches a ledger in any case — this door has none.
    """


@dataclass(frozen=True)
class Source:
    """One thing this runtime either was given or was not, and why.

    The reason is carried from whichever component is missing, or states
    a structural fact about this surface. It is never composed prose
    about how the founder should feel about the gap.
    """

    name: str
    present: bool
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "present": self.present,
            "reason": self.reason,
        }


#: Stated once, because it is the most important thing this surface reports
#: about itself: observation and authority are different doors.
AUTHORITY_UNREACHABLE = (
    "authority travels the Runtime Bridge and is not reachable from this "
    "surface by construction; nothing sent here can start, approve or "
    "cancel work"
)

_NO_INTELLIGENCE = (
    "no machine inventory has been derived, so nothing is known about this "
    "environment yet"
)
_NO_COVERAGE = (
    "no coverage has been attested, so what is watched is unknown"
)
_NO_CONVERSATION = "no conversation memory is wired to this surface"


class FounderRuntime:
    """Holds four things it was handed, and hands on what they publish.

    Every constructor argument is optional and absent is a first-class
    state: a founder surface has to be able to open before an inventory
    has been scanned, and it has to be able to say so.
    """

    __slots__ = ("_conversation", "_coverage", "_intelligence", "_registry", "_desktop")

    def __init__(
        self,
        *,
        intelligence: EnvironmentIntelligence | None = None,
        coverage: Coverage | None = None,
        registry: DomainRegistry | None = None,
        conversation: ConversationMemory | None = None,
        desktop: DesktopLayer | None = None,
    ) -> None:
        if intelligence is not None and not isinstance(
            intelligence, EnvironmentIntelligence
        ):
            raise TypeError(
                "intelligence must be the EnvironmentIntelligence that "
                "derive_intelligence() returned, or be omitted"
            )
        if coverage is not None and not isinstance(coverage, Coverage):
            raise TypeError(
                "coverage must be the Coverage that attest() returned, or "
                "be omitted"
            )
        if registry is not None and not isinstance(registry, DomainRegistry):
            raise TypeError("registry must be a DomainRegistry, or omitted")
        if conversation is not None and not isinstance(
            conversation, ConversationMemory
        ):
            raise TypeError(
                "conversation must be a ConversationMemory, or be omitted"
            )
        if desktop is not None:
            # Imported here, not at module scope, and this placement is
            # load-bearing rather than stylistic. `master_agent
            # .founder_edition`'s package __init__ imports `boot`, which
            # imports `master_agent.communication`, which reaches
            # conversation_engine -> founder_runtime -> back to this
            # module. At module scope that closes a genuine import cycle:
            # importing `master_agent.communication` first (as the test
            # suite does) fails with "cannot import name
            # CommunicationEngine from partially initialized module" and
            # takes collection of the whole suite down with it. By the
            # time any caller has a DesktopLayer instance to pass here,
            # founder_edition is fully imported, so a local import is
            # both safe and cheap (sys.modules hit).
            from master_agent.founder_edition.desktop_layer import DesktopLayer

            if not isinstance(desktop, DesktopLayer):
                raise TypeError("desktop must be a DesktopLayer, or be omitted")

        self._intelligence = intelligence
        self._coverage = coverage
        self._registry = registry
        self._conversation = conversation
        self._desktop = desktop

    # ---- what is wired ---------------------------------------------------

    def sources(self) -> tuple[Source, ...]:
        """What this runtime has, what it has not, and why. Fixed order.

        The fourth entry is not a dependency: it is the standing fact
        that this door cannot reach authority, reported every time so a
        surface never has to infer it from a call that did nothing.
        """
        return (
            Source(
                name="environment_intelligence",
                present=self._intelligence is not None,
                reason=(
                    "derived from the Desktop Executive's machine inventory"
                    if self._intelligence is not None
                    else _NO_INTELLIGENCE
                ),
            ),
            Source(
                name="vigilance",
                present=self._coverage is not None,
                reason=(
                    "attested coverage is available"
                    if self._coverage is not None
                    else _NO_COVERAGE
                ),
            ),
            Source(
                name="conversation",
                present=self._conversation is not None,
                reason=(
                    "the session's turn history is available"
                    if self._conversation is not None
                    else _NO_CONVERSATION
                ),
            ),
            Source(
                name="desktop",
                present=self._desktop is not None,
                reason=(
                    "desktop layer wired with executor and observer"
                    if self._desktop is not None
                    else "desktop layer not constructed"
                ),
            ),
            Source(
                name="kernel_authority",
                present=False,
                reason=AUTHORITY_UNREACHABLE,
            ),
        )

    # ---- the sections ----------------------------------------------------

    def environment(self) -> dict[str, Any] | None:
        """C22's projection, or `None` when nothing has been derived."""
        if self._intelligence is None:
            return None
        return environment_projection(self._intelligence)

    def presence(self) -> dict[str, Any]:
        """The C20 feed, and C19's coverage answer beside it.

        Both, not either. The feed is what the Presence Layer folds in;
        the coverage is C19's authoritative `complete`, carried verbatim
        so a surface never has to take a re-derivation's word for whether
        *"Nothing needs you."* may be said.
        """
        if self._coverage is None:
            feed = PresenceFeed(absent_reason=_NO_COVERAGE)
            return {"feed": feed.as_dict(), "coverage": None}
        feed = presence_feed(self._coverage, self._registry)
        return {"feed": feed.as_dict(), "coverage": self._coverage.as_dict()}

    def conversation(self) -> dict[str, Any] | None:
        """Session turns, or `None` when no memory is wired."""
        if self._conversation is None:
            return None
        return conversation_projection(self._conversation)

    def status(self) -> dict[str, Any]:
        """What is wired. The one operation that cannot report absence."""
        return {"sources": [source.as_dict() for source in self.sources()]}

    def snapshot(self) -> dict[str, Any]:
        """Every section at once, with fixed key order.

        One round trip, because a surface that has to make four calls to
        draw one screen will eventually draw three of them from one
        moment and one from another.
        """
        return {
            "environment": self.environment(),
            "presence": self.presence(),
            "conversation": self.conversation(),
            "sources": [source.as_dict() for source in self.sources()],
        }

    # ---- the door --------------------------------------------------------

    def handle(self, envelope: Mapping[str, Any]) -> dict[str, Any]:
        """Read one envelope, answer with one envelope.

        The only method that reads a wire shape. Every branch below is
        selected by the operation name and by nothing else.
        """
        raw = envelope.get(OPERATION) if isinstance(envelope, Mapping) else None
        try:
            operation = _operation_of(envelope)
            _refuse_arguments(envelope)
            payload = self._payload(operation)
        except Exception as exc:  # noqa: BLE001 — see the module docstring
            return {
                OPERATION: raw,
                "kind": ResultKind.ERROR.value,
                "payload": {
                    "type": type(exc).__name__,
                    "message": str(exc),
                },
            }
        return {
            OPERATION: operation.value,
            "kind": ResultKind.OK.value,
            "payload": payload,
        }

    def _payload(self, operation: FounderOperation) -> Any:
        """One line per operation, and no line between them."""
        if operation is FounderOperation.SNAPSHOT:
            return self.snapshot()
        if operation is FounderOperation.ENVIRONMENT:
            return self.environment()
        if operation is FounderOperation.PRESENCE:
            return self.presence()
        if operation is FounderOperation.CONVERSATION:
            return self.conversation()
        return self.status()


# ---- envelope reading ---------------------------------------------------


def _operation_of(envelope: Any) -> FounderOperation:
    if not isinstance(envelope, Mapping):
        raise InvalidFounderEnvelope(
            f"an envelope is a mapping naming {OPERATION!r}; got "
            f"{type(envelope).__name__}"
        )
    if OPERATION not in envelope:
        raise InvalidFounderEnvelope(f"the envelope names no {OPERATION!r}")

    value = envelope[OPERATION]
    try:
        return FounderOperation(value)
    except (ValueError, KeyError) as exc:
        allowed = ", ".join(
            sorted(member.value for member in FounderOperation)
        )
        raise InvalidFounderEnvelope(
            f"operation must be one of: {allowed}; got {value!r}"
        ) from exc


def _refuse_arguments(envelope: Mapping[str, Any]) -> None:
    """Every operation here is nullary, so arguments are refused.

    Not ignored. A caller passing arguments is asking for something
    parameterised — a mission, a filter, a page — and this door has none
    of those. Silently dropping them would answer a different question
    than the one asked.
    """
    arguments = envelope.get(ARGUMENTS)
    if arguments in (None, {}):
        return
    if not isinstance(arguments, Mapping):
        raise InvalidFounderEnvelope(
            f"{ARGUMENTS!r} must be a mapping when present"
        )
    named = ", ".join(sorted(str(key) for key in arguments))
    raise InvalidFounderEnvelope(
        f"every founder operation is nullary; got arguments: {named}"
    )
