"""FounderChoice — one bounded question put to the founder, and their one
answer.

**Why it is not inside `mission_control/`.** That was the first home, and
the provider guard rejected it, correctly. MB033 Rule 4 says a provider
executes and never decides, and enforces it structurally: a provider may
not import `master_agent.mission_control`, `broker`, `ai_infrastructure`
or `runtime`, because a provider that can see the layer that decides will
eventually consult it. The thing that needs to ask the founder which
account to use is a provider. So the port lives outside all of them --
it is a contract with no dependencies, which is what lets both a provider
and a shell hold it without either acquiring the other's layer.

**Why this is not the Approval Queue.** `mission_control/approvals.py`
already asks the founder things, and it was the first candidate. It
answers a *yes/no about authority*: may this capability run, is this
risk accepted, and answering yes can mint a real Permission System grant.
"Which of these three Google accounts?" is neither a yes nor a permission
-- it is a choice between options only the founder can disambiguate, and
forcing it through approve/reject would either lose the options or turn
the queue into a two-shaped thing. So this is a sibling of that queue, not
a replacement for it, and a deployment wires whichever the question needs.

**Why it is not a workflow engine.** Exactly one round trip: a request
carrying options, and a response naming one of them or cancelling. No
follow-ups, no state machine, no persistence. If a future question needs
more, that is a new mechanism with its own justification, not a field
added here.

**Why it is a port.** The thing that needs to ask -- a reasoning provider
driving a browser -- must not know a desktop window exists. It holds a
`FounderInteraction` and calls `ask_choice`; whether that reaches a
pywebview shell, a terminal, or a test double is the composition root's
business. A provider importing a UI class would make the provider
unusable in every other deployment and untestable in all of them.

Generic on purpose, and already the shape the next few questions need:
choose an account, choose a workspace, choose a project, choose between
two ambiguous external identities.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

#: What `FounderChoiceResponse.option_id` holds when the founder declined
#: to choose. Distinct from any real option id, and distinct from a
#: timeout: cancelling is an answer, and the work stops because the
#: founder said so.
CANCELLED = ""


@dataclass(frozen=True)
class ChoiceOption:
    """One thing the founder may pick.

    `option_id` is what the asker gets back and is its own business --
    typically an index or a selector it can act on. `label` is what the
    founder reads, and is the only part that should ever carry a name, an
    address or anything else observed from a page.
    """

    option_id: str
    label: str
    #: Optional one-line clarifier, e.g. what will happen if this is
    #: picked. Never a place for anything sensitive.
    detail: str = ""


@dataclass(frozen=True)
class FounderChoiceRequest:
    """The question, its options, and why it is being asked."""

    question: str
    options: tuple[ChoiceOption, ...] = field(default_factory=tuple)
    #: One sentence of context, shown with the question.
    context: str = ""
    #: Who is asking, for the founder's benefit and for an audit line.
    asked_by: str = "kalpavriksha"
    #: How long the asker is prepared to wait. `None` means it will wait
    #: as long as the interaction implementation is prepared to.
    timeout_seconds: float | None = None


@dataclass(frozen=True)
class FounderChoiceResponse:
    """Exactly one of: a chosen option, or a cancellation."""

    option_id: str = CANCELLED
    cancelled: bool = True

    @classmethod
    def chose(cls, option_id: str) -> FounderChoiceResponse:
        return cls(option_id=option_id, cancelled=False)

    @classmethod
    def cancel(cls) -> FounderChoiceResponse:
        return cls()


@runtime_checkable
class FounderInteraction(Protocol):
    """The port. Two methods, because a founder-facing path needs to both
    ask and tell.

    `notify` exists so a caller can say "your attention is needed" without
    inventing a question that has no options -- the Google password/MFA
    case, where Kalpavriksha has nothing to offer and nothing to ask, only
    something to report before it goes back to waiting.
    """

    #: Whether this implementation can actually put a question to a
    #: founder right now. A port that cannot ask is not the same thing as
    #: a founder who said no, and a caller that cannot tell them apart
    #: will eventually report one as the other -- see
    #: `DeferredFounderInteraction`, where exactly that was reachable.
    can_ask: bool

    def ask_choice(self, request: FounderChoiceRequest) -> FounderChoiceResponse:
        ...

    def notify(self, message: str) -> None:
        ...


class DeferredFounderInteraction:
    """A port that exists before anything can answer through it.

    A composition root assembles the reasoning stack long before there is
    a window to ask a question in -- the provider has to be constructed
    with *something*, and constructing it with `None` would mean the
    ability to ask could never be added later without rebuilding the
    provider. This is that something: an empty holder the shell attaches
    a real implementation to once it has a surface.

    Unattached, it reports `can_ask = False` and cancels. Both halves
    matter. Cancelling is what stops a question nobody can answer from
    being answered on the founder's behalf -- returning a default option
    would be exactly the guess the account-choice rule forbids. But
    cancelling *alone* was a bug: the caller then told the founder they
    had cancelled a choice they were never offered, which is a lie about
    the founder's own actions. `can_ask` is how a caller tells "nobody
    asked you" apart from "you said no", so it can say the true thing.
    """

    def __init__(self, delegate: FounderInteraction | None = None) -> None:
        self._delegate = delegate

    @property
    def attached(self) -> bool:
        return self._delegate is not None

    @property
    def can_ask(self) -> bool:
        """False until a surface is attached, and thereafter whatever that
        surface says about itself."""
        if self._delegate is None:
            return False
        return bool(getattr(self._delegate, "can_ask", True))

    def attach(self, delegate: FounderInteraction) -> None:
        self._delegate = delegate

    def ask_choice(self, request: FounderChoiceRequest) -> FounderChoiceResponse:
        if self._delegate is None:
            return FounderChoiceResponse.cancel()
        return self._delegate.ask_choice(request)

    def notify(self, message: str) -> None:
        if self._delegate is None:
            return
        self._delegate.notify(message)
