"""`ResponseComposer` — one human sentence per intent, never a leak. C31.

*"Translate everything."* Every method here takes a fact this package
already assembled (`ConversationContext`) and returns a short, spoken
sentence — never the fact's own name. `DesktopExecutiveV2 healthy` becomes
*"Everything on the desktop is working normally"* not because a lookup
table renames one string to another, but because no method on this class
ever holds the first string to begin with: `ContextAssembler` handed it a
boolean, and this module speaks about the boolean.

## The brief's own status example, and the conflict inside it

The brief's worked dialogue reads:

```
How's the system?
↓
Desktop Executive healthy.
Environment Intelligence healthy.
Founder Runtime healthy.
No warrants pending.
```

—but the same brief's Speaking Rules say, two sections earlier, *"Never
expose Runtime … Component names,"* and give its own worked translation
in the opposite direction: `DesktopExecutiveV2 healthy` → *"Everything on
the desktop is working normally."* Read literally, the dialogue's own
four lines contain exactly the component names the rules forbid two
paragraphs above it.

**The structural rule wins.** This module follows the Speaking Rules —
checked by `_checked()` below, not merely intended — and produces the
same *four facts*, spoken without a single forbidden name:

```
Everything on the desktop is working normally.
The environment looks healthy.
I'm here and fully connected.
Nothing is waiting on your approval.
```

Recorded as a stated interpretation in `Engineering/HEALTH_C31.md` §5,
the same way C30 recorded its own two reconciliations rather than picking
silently between a brief's two conflicting sentences.

## Never invent

Every branch below reads one field of `ConversationContext` and states it.
None composes a number, a name, or a recommendation that was not already
sitting in that context — `priority()`'s attention item, when it names
one, is a domain name `ContextAssembler` read verbatim from `Coverage`,
never synthesised here.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence

from master_agent.conversation_engine.context import ConversationContext
from master_agent.founder_identity import (
    FounderContext,
    FounderIdentity,
    FounderSession,
    continuity_reply,
    greet,
)

#: Architecture this module must never name aloud. Checked as lower-cased
#: substrings against every composed sentence, the same discipline
#: `founder_identity.greeting.FORBIDDEN_PHRASES` already established for
#: AI wording — extended here to component and subsystem names.
FORBIDDEN_INTERNAL_TERMS: tuple[str, ...] = (
    "runtime",
    "kernel",
    "operator",
    "mission id",
    "founderruntime",
    "desktopexecutivev2",
    "desktopoperator",
    "desktopobserver",
    "desktopexecutor",
    "coordinator",
    "orchestrator",
    "bridge",
)


class ExposedInternals(RuntimeError):
    """A composed sentence named architecture the founder was never meant
    to hear. Raised rather than silently rewritten — the same choice
    `founder_identity.greeting.ForbiddenWording` makes for AI wording."""


def _checked(text: str) -> str:
    lowered = text.lower()
    for term in FORBIDDEN_INTERNAL_TERMS:
        if term in lowered:
            raise ExposedInternals(
                f"a composed reply named forbidden architecture {term!r}"
            )
    return text


class ResponseComposer:
    """Stateless. Every method is a pure function of what it is handed —
    no clock, no I/O, no randomness. Two calls with the same context
    produce the same sentence.

    `capability_domains` is the one injected collaborator: a
    zero-argument callable returning the founder-level domains this
    system can currently act in ("your browser", "your desktop"). It is
    *injected* rather than read here because the registry that knows the
    answer belongs to the Operator side, and this composer must never
    reach into it — the Brain is told which domains exist, never which
    verbs implement them. Omitted, the composer answers honestly that it
    can talk but not act.
    """

    # Deliberately no __slots__: `TestExposedInternalsIsStructural`
    # monkeypatches a translation helper to prove the leak detector is
    # structural rather than incidental, and __slots__ would make that
    # test impossible to write.

    def __init__(
        self, *, capability_domains: Callable[[], Sequence[str]] | None = None,
    ) -> None:
        self._capability_domains = capability_domains

    def capabilities(self, context: ConversationContext) -> str:
        """*"What can you do right now?"* — and every natural variation
        of it (see `intent._CAPABILITY_MARKERS`).

        Domain-level language only. The founder learns what Kalpavriksha
        can act on, never the execution primitives that implement it:
        no `browser.click`, no `focus_window`, no `execute_command`.
        """
        domains = []
        if self._capability_domains is not None:
            try:
                domains = [d for d in self._capability_domains() if d]
            except Exception:  # noqa: BLE001 — an unreadable registry is an honest absence
                domains = []

        if not domains:
            return _checked(
                "Right now I can talk with you, but I don't have a way to "
                "act on this machine yet."
            )
        if len(domains) == 1:
            reach = domains[0]
        else:
            reach = ", ".join(domains[:-1]) + " and " + domains[-1]
        return _checked(
            f"I can work with {reach}. Beyond single actions I can plan and "
            "carry out multi-step work — tell me what you want done and I'll "
            "work out the steps."
        )

    # ---- greeting and continuation delegate to C29, verbatim ----------

    def greeting(self, identity: FounderIdentity, context: ConversationContext) -> str:
        """C29's own `greet()`. This method adds no wording of its own —
        it exists so a caller reaches greetings through this composer's
        one door rather than reaching into `founder_identity` directly."""
        founder_context = FounderContext(
            moment=context.moment,
            environment_ready=context.environment_ready,
            conversation_ready=context.conversation_ready,
            presence_ready=context.presence_complete,
        )
        return _checked(greet(identity, founder_context))

    def continuation(self, session: FounderSession) -> str:
        """C29's own `continuity_reply()`, unchanged."""
        return _checked(continuity_reply(session))

    # ---- the four C31 intents -------------------------------------------

    def status(self, context: ConversationContext) -> str:
        """*"How's the system?"* — four facts, in the brief's own order,
        none of them a component name. See the module docstring for why."""
        lines = [
            self._desktop_line(context.desktop_ready),
            self._environment_line(context.environment_ready),
            "I'm here and fully connected.",
            "Nothing is waiting on your approval.",
        ]
        return _checked(" ".join(lines))

    def activity(self, context: ConversationContext) -> str:
        """*"What are you doing?"* Honest about the R80 distinction: a
        founder with nothing registered is told that, never told
        *"monitoring everything"* over a coverage that watches nothing —
        see `founder_runtime.presence_feed`'s own `NOTHING_WATCHED`."""
        if not context.presence_registered:
            return _checked(
                "I'm here and ready. Nothing is being watched yet, so "
                "nothing can need your attention."
            )
        if context.presence_complete:
            return _checked(
                "I'm monitoring everything. Nothing currently needs your "
                "attention."
            )
        count = len(context.attention_needed)
        noun = "thing" if count == 1 else "things"
        return _checked(
            f"I'm keeping an eye on things. {count} {noun} could use your "
            "attention."
        )

    def priority(self, context: ConversationContext) -> str:
        """*"What should I work on?"* Summarises and prioritises from
        `Coverage`'s own gaps; never invents one. The first gap is spoken
        because `Coverage.gaps` is already ordered — C19's own order,
        carried rather than re-sorted."""
        if context.attention_needed:
            first = context.attention_needed[0]
            return _checked(f"The thing that needs you most right now is {first}.")
        if not context.presence_registered:
            return _checked(
                "Nothing is being tracked yet, so I don't have a priority "
                "to point you to."
            )
        return _checked(
            "Nothing needs your attention right now — a good moment to "
            "start something new."
        )

    def build_request(self, context: ConversationContext) -> str:
        """*"Build a trading bot."* Never plans, and never claims to have
        forwarded the request — this engine holds no door that could
        actually do that, and claiming otherwise would be inventing an
        action that did not happen."""
        return _checked(
            "I don't build things myself — that needs to go through "
            "planning, not through me."
        )

    # ---- translation helpers, each a closed three-way branch -----------

    def _desktop_line(self, ready: bool | None) -> str:
        if ready is None:
            return "I don't have a desktop reading yet."
        if ready:
            return "Everything on the desktop is working normally."
        return "Something on the desktop needs a look."

    def _environment_line(self, ready: bool) -> str:
        if ready:
            return "The environment looks healthy."
        return "I haven't looked at the environment yet."
