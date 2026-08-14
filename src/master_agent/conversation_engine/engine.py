"""`ConversationEngine` — the one public door into C31. Answers only.

```
   founder speech
        │
        ▼
   ConversationEngine.reply()
        │  moment, optional DesktopStatus — both handed in, never read ambient
        ▼
   ResponsePipeline.handle()
        │  classify → assemble → compose → record
        ▼
   ConversationTurn (intent, reply, context)
```

Everything this class does was already built by the four collaborators it
holds — it adds no wording, no derivation, and no branch that is not
already `ResponsePipeline`'s own. Its entire reason to exist is to be the
one name a caller (a future `founder_edition` wiring step, most likely)
needs to import.

## The five prohibitions, structural rather than promised

*"Conversation Engine MUST NOT execute desktop actions, launch
applications, create missions, plan work, [or] mutate Founder Runtime."*
Every one of these is a fact about this package's import graph, checked
by `tests/test_conversation_engine.py` via AST across every module in
`conversation_engine/`, not merely a rule this docstring states:

| Forbidden | Why it cannot happen |
|---|---|
| Execute desktop actions | No `desktop.execution`, `desktop_operator`, or `desktop.perception` import anywhere in this package |
| Launch applications | Same guard — no module that could open a process is reachable |
| Create missions | No `mission_manager`, `mission_control`, or `missions` import |
| Plan work | No `planner`, `brain`, or `orchestrator` import |
| Mutate Founder Runtime | `FounderRuntime` is read through its own three projections (`environment()`, `conversation()`, `presence()`) only — no `handle()`, no setter, and this package holds no Kernel through which a mutation could travel anyway |

`FounderRuntime.handle()` is deliberately never called here: it is the one
door that could, in principle, be extended with a mutating operation in
the future, and this engine reaches only the read-only methods a `Source`
already reports present.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime

from master_agent.conversation_engine.composer import ResponseComposer
from master_agent.conversation_engine.context import DesktopStatus
from master_agent.conversation_engine.pipeline import ConversationTurn, ResponsePipeline
from master_agent.founder_identity import FounderIdentity, FounderSession
from master_agent.founder_runtime import FounderRuntime
from master_agent.memory.conversation import ConversationMemory


class ConversationEngine:
    """One `ResponsePipeline`, held. `reply()` is the whole public
    surface a caller needs — `inspect.signature` is checked directly by
    a test, the same way C28's `DesktopOperator.execute()` boundary is."""

    __slots__ = ("_pipeline",)

    def __init__(
        self,
        *,
        runtime: FounderRuntime,
        identity: FounderIdentity,
        session: FounderSession,
        conversation: ConversationMemory,
        capability_domains: Callable[[], Sequence[str]] | None = None,
    ) -> None:
        # `capability_domains` is carried, not consulted, here -- it
        # belongs to the composer, which is the only thing that turns it
        # into a sentence. Passed through so the composition root can
        # supply the live executive registry without this engine (or the
        # pipeline) ever reaching into the Operator side itself.
        self._pipeline = ResponsePipeline(
            runtime=runtime,
            identity=identity,
            session=session,
            conversation=conversation,
            composer=ResponseComposer(capability_domains=capability_domains),
        )

    def reply(
        self,
        text: str,
        *,
        moment: datetime,
        desktop: DesktopStatus | None = None,
    ) -> ConversationTurn:
        """The founder speaks; Somesh answers if C31 recognises the
        shape of what was said. `moment` and `desktop` are parameters,
        never read from an ambient source — the same clock-injection
        discipline every founder-facing time in this codebase already
        follows."""
        return self._pipeline.handle(text, moment=moment, desktop=desktop)
