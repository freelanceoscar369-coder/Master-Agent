"""Founder Edition Boot Sequence — C24.
```
   Boot
     │
     ▼
   Initialize Runtime            ← the door opens, unwired
     │
     ▼
   Initialize Presence           ← C19 attests whatever is registered (nothing, today)
     │
     ▼
   Initialize Environment Intelligence   ← the Desktop scan, then C22's derivation
     │
     ▼
   Initialize Conversation       ← a fresh Layer 1 ConversationMemory
     │
     ▼
   Connect Founder Runtime       ← C23's FounderRuntime, constructed from the four above
     │
     ▼
   Render Founder Surface        ← out of scope: HyperAgent's TypeScript, not this repo
     │
     ▼
   Ready
```
Seven steps, in the brief's own order, each one a `BootStep` a founder can
read. **This module composes; it derives nothing.** Every value it hands to
`FounderRuntime` was produced by a component that already existed:
`desktop.inventory.discover` scans, `environment_intelligence.derive_intelligence`
interprets, `vigilance.VigilanceAttestation` attests, `memory.conversation.
ConversationMemory` remembers. C24 adds no new inference and no new derivation
— its whole job is the order these run in and what each does when the one
before it could not.
## Why "Initialize Presence" runs before "Initialize Environment Intelligence"
The brief's own ordering, and it is followed literally rather than
reordered for convenience. The temptation was to seed a vigilance domain
from the environment scan's own success — "was the machine scan able to
run" — folded into presence as a fact about presence. That was rejected:
**A vigilance domain is a founder's own concern, not a boot-time side
effect.** VEDA 04 §7 makes per-domain health *"a first-class product
concept surfaced in the founder's own language"* — inbox, calendar,
billing, the things a founder decided matter. The environment scan is not
one of those; it is infrastructure this boot sequence depends on, not
something a founder asked to be watched. Inventing a domain to make
`Coverage.complete` look better than it is would be exactly the
duplication-and-decoration C23's own R80 finding warned against, wearing a
different name.
So **Initialize Presence attests over whatever `DomainRegistry` it is
given — empty, at this milestone, because no connector has registered
anything yet — and reports the honest answer.** `Coverage.complete` is
`False`, VEDA 04 D7's gap says why, and C23's `presence_feed()` already
refuses to feed an empty coverage into the Presence Layer rather than
letting it manufacture calm from nothing (`Engineering/HEALTH_C23.md` §5,
finding R80). Nothing here changes that; this module is the first caller
to actually exercise it against a boot sequence's real ordering, and it
holds.
The ordering the brief gives is therefore not incidental: Presence *can*
be initialized before Environment Intelligence, precisely because it does
not depend on it.
## Why "Render Founder Surface" is not implemented here
That step is HyperAgent's TypeScript artifact (C21, the Founder Surface;
C20, the Presence Layer it renders through) and is not part of this Python
repository. This boot sequence stops at **Connect Founder Runtime**,
which is the boundary Founder Runtime Wiring (C23) already defined: a
JSON-serialisable envelope, produced by `FounderRuntime.handle()`, ready
for whatever transport eventually carries it to the surface. Reporting
`render_founder_surface` as a boot failure would misstate whose component
is missing; reporting it `ok` would claim work nobody did here. It is
recorded as its own status, `OUT_OF_SCOPE`, so a reader of the boot report
sees the boundary rather than a lie in either direction.
## Determinism, and where it ends
`boot_founder_edition()` accepts an injectable `probe` and `clock`, the
same seam `desktop/` and `vigilance/` already use for their own tests —
this module invents no new testing convention. **The one real
non-determinism it has is the machine itself**: two boots on two different
machines see two different environments, honestly. Nothing here reads a
clock beyond what `discover()` and `VigilanceAttestation.attest()` already
read as part of their own contracts.
## What it never does
No capability is invoked, no plugin is loaded, no provider is called, no
Kernel operation is reachable, no browser is opened. In C23's own
vocabulary: `authorize` is unreachable (no Kernel is held), nothing here
`execute`s a capability, and `CalmState`/`VigilanceState` are never
constructed — those are C20's own derived types, produced from the feed
this module hands it, never duplicated here. `tests/
test_founder_edition_boot.py` enforces every one of these by AST, the same
way C23's own suite does, over this package specifically.
"""
from __future__ import annotations
from dataclasses import dataclass
from collections.abc import Callable, Sequence
from typing import Any
from master_agent.communication import CommunicationEngine, TextOutput, VoiceOutput
from master_agent.conversation_engine import ConversationEngine
from master_agent.desktop.execution.executor import DesktopExecutor
from master_agent.desktop.inventory import MachineInventory, discover
from master_agent.desktop.operations import DesktopExecutiveV2
from master_agent.desktop.perception import DesktopObserver
from master_agent.desktop.probe import RealSystemProbe, SystemProbe
from master_agent.desktop_operator import DesktopOperator
from master_agent.environment_intelligence import (
    EnvironmentIntelligence,
    derive_intelligence,
)
from master_agent.foundation.clock import Clock, SystemClock
from master_agent.founder_edition.dashboard import founder_dashboard
from master_agent.founder_edition.desktop_layer import DesktopLayer
from master_agent.founder_identity import (
    FounderIdentity,
    FounderSession,
    continuity_reply,
    founder_context,
    greet,
    is_continuation_request,
    is_greeting,
)
from master_agent.founder_runtime import FounderRuntime
from master_agent.memory.conversation import ConversationMemory
from master_agent.vigilance import Coverage, DomainRegistry, VigilanceAttestation
#: The step succeeded and produced what it promised.
OK = "ok"
#: The step could not run, and the reason is carried rather than swallowed.
#: `desktop/` and `launcher/boot.py` already use this word for exactly this
#: meaning; a synonym here would cost a reader nothing but a lookup.
UNAVAILABLE = "unavailable"
#: The step belongs to a component outside this repository (HyperAgent's
#: TypeScript). Not a failure of this boot sequence — a stated boundary.
OUT_OF_SCOPE = "out_of_scope"
#: Every step, in dependency order. Held as data so a test can assert the
#: report never has a different shape.
#:
#: **C24's seven are unchanged and stay in their original positions.**
#: C30's five are inserted after `connect_founder_runtime`, because every
#: one of them needs the connected runtime, the scanned inventory, or the
#: session memory that the steps before it produced. The C30 brief draws
#: its chain as `… Dashboard → Desktop Executive → Desktop Operator →
#: Desktop Perception`; that is a **layering** diagram — who sits on top of
#: whom — and it cannot be a boot order, because C28's Operator is
#: constructed *from* C26's executor and C27's observer and therefore
#: cannot precede them. Boot follows the dependencies and says so, the
#: same way C24's own docstring argues its presence-before-environment
#: **C30 inserts desktop layer before connect_founder_runtime**, because the
#: FounderRuntime now requires the desktop layer to be wired for application
#: execution. The desktop layer depends on the inventory from step 3, so it
#: goes immediately after environment_intelligence.
#:
#: **C33 inserts two more, immediately after `founder_identity`.**
#: `conversation_engine` (C31) needs only the runtime, the identity, and
#: the session `founder_identity` just produced; `communication` (C32)
#: needs only that engine plus the conversation memory. Neither depends
#: on the desktop layer at all, so they are placed by the same rule as
#: everything else on this list — as early as their own dependencies
#: allow, not where the brief's own UX diagram happens to draw an arrow.
STEP_NAMES: tuple[str, ...] = (
    "runtime",
    "presence",
    "environment_intelligence",
    "desktop_executive",
    "desktop_perception",
    "desktop_operator",
    "connect_founder_runtime",
    "conversation",
    "founder_identity",
    "conversation_engine",
    "communication",
    "dashboard",
    "render_founder_surface",
    "ready",
)
#: The speaker recorded for anything Somesh says. Deliberately **not**
#: `"assistant"`: C23's conversation projection maps every speaker that is
#: not `"user"` to the role `"system"`, and its own suite asserts an
#: `assistant` row is unreachable by construction. C30 records Somesh's
#: acknowledgements through that same door rather than beside it, so the
#: guarantee holds one layer up without being restated.
SOMESH = "somesh"
#: The founder's name when none was given. Generic on purpose — a boot
#: sequence that guessed at a real name would be inventing the one fact
#: C29 says Somesh must already know rather than ask for.
#: The founder this edition is built for. A founder decision, not a
#: placeholder: Onkar is the founder, Somesh is the chief of staff he
#: delegates to (`FounderIdentity.assistant_name`), and Kalpavriksha is
#: the system Somesh operates. Overridable by `--founder-name` or
#: `KALPAVRIKSHA_FOUNDER_NAME` for anyone else running this build.
DEFAULT_FOUNDER_NAME = "Onkar"
_NO_DOMAINS_WATCHED = (
    "no domain has been registered yet; vigilance has nothing to attest "
    "over until a founder connects a domain"
)
_RENDER_SURFACE_REASON = (
    "the Founder Surface is HyperAgent's TypeScript artifact (C21), "
    "rendered through the Presence Layer (C20); neither is part of this "
    "Python repository, and this boot sequence stops at Connect Founder "
    "Runtime"
)
@dataclass(frozen=True)
class BootStep:
    """One line of the boot report. Frozen — a record of what already
    happened should not be editable by whoever reads it."""
    name: str
    status: str
    detail: str = ""
    @property
    def ok(self) -> bool:
        return self.status == OK
    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "status": self.status, "detail": self.detail}
@dataclass(frozen=True)
class BootReport:
    """Every step, in the order the brief names them. Immutable, like
    every other record-of-a-past-moment in this project."""
    steps: tuple[BootStep, ...] = ()
    def step(self, name: str) -> BootStep | None:
        for candidate in self.steps:
            if candidate.name == name:
                return candidate
        return None
    @property
    def needs_attention(self) -> tuple[BootStep, ...]:
        """Every step a founder should actually read about.
        `OUT_OF_SCOPE` is deliberately excluded: it is not something to
        fix, it is a boundary this boot sequence draws on purpose.
        """
        return tuple(s for s in self.steps if s.status == UNAVAILABLE)
    def as_dict(self) -> dict[str, Any]:
        return {"steps": [s.as_dict() for s in self.steps]}
class FounderEditionApp:
    """What Boot produced. Holds a `FounderRuntime` and the one thing it
    does not expose publicly — the live `ConversationMemory` — so a
    founder message can reach it without reopening the runtime.
    A plain container after construction: every read delegates to
    `FounderRuntime`, and the one write (`send`) delegates to
    `ConversationMemory.record`, which already existed. No method here
    performs a derivation `FounderRuntime`, C19, C20 or C22 does not
    already perform.
    """
    __slots__ = (
        "_clock",
        "_communication",
        "_conversation",
        "_conversation_engine",
        "_desktop",
        "_identity",
        "_report",
        "_runtime",
        "_session",
    )
    def __init__(
        self,
        *,
        runtime: FounderRuntime,
        conversation: ConversationMemory,
        report: BootReport,
        identity: FounderIdentity | None = None,
        session: FounderSession | None = None,
        desktop: DesktopLayer | None = None,
        clock: Clock | None = None,
        conversation_engine: ConversationEngine | None = None,
        communication: CommunicationEngine | None = None,
    ) -> None:
        if not isinstance(runtime, FounderRuntime):
            raise TypeError("runtime must be the FounderRuntime this boot connected")
        if not isinstance(conversation, ConversationMemory):
            raise TypeError("conversation must be the ConversationMemory this boot created")
        if not isinstance(report, BootReport):
            raise TypeError("report must be the BootReport this boot produced")
        if identity is not None and not isinstance(identity, FounderIdentity):
            raise TypeError("identity must be the FounderIdentity this boot built")
        if session is not None and not isinstance(session, FounderSession):
            raise TypeError("session must be the FounderSession this boot built")
        if desktop is not None and not isinstance(desktop, DesktopLayer):
            raise TypeError("desktop must be the DesktopLayer this boot built")
        if conversation_engine is not None and not isinstance(
            conversation_engine, ConversationEngine
        ):
            raise TypeError(
                "conversation_engine must be the ConversationEngine this boot built"
            )
        if communication is not None and not isinstance(communication, CommunicationEngine):
            raise TypeError(
                "communication must be the CommunicationEngine this boot built"
            )
        self._runtime = runtime
        self._conversation = conversation
        self._report = report
        self._identity = identity
        self._session = session
        self._desktop = desktop
        self._clock = clock or SystemClock()
        self._conversation_engine = conversation_engine
        self._communication = communication
    @property
    def report(self) -> BootReport:
        return self._report
    @property
    def runtime(self) -> FounderRuntime:
        return self._runtime
    @property
    def identity(self) -> FounderIdentity | None:
        """C29's `FounderIdentity`. `None` only when this app was built
        the C24 way, with the three arguments that predate C30."""
        return self._identity
    @property
    def session(self) -> FounderSession | None:
        """C29's `FounderSession`, over **this app's own**
        `ConversationMemory` — never a second one. See `_wire_identity`."""
        return self._session
    @property
    def desktop(self) -> DesktopLayer | None:
        """C25–C28, composed once. `None` when the desktop layer could
        not be wired; the rest of the application still runs."""
        return self._desktop
    @property
    def conversation(self) -> ConversationMemory:
        """The one `ConversationMemory` this application holds. Every
        other view of a founder's speech — `session`, `runtime.
        conversation()`, `conversation_engine`, `communication` — is a
        lens on this same object, never a second history. Exposed
        publicly so an integration layer (C33) can wire further
        components against it without this class having to know what
        they are."""
        return self._conversation
    @property
    def conversation_engine(self) -> ConversationEngine | None:
        """C31's `ConversationEngine`. `None` when Founder Identity did
        not complete — there is no founder for it to answer on behalf
        of."""
        return self._conversation_engine
    @property
    def communication(self) -> CommunicationEngine | None:
        """C32's `CommunicationEngine`. Holds whatever channels this
        boot was given (`boot_founder_edition(voice_output=...,
        text_output=...)`) — `None` of either is a supported, honest
        state: a caller that registers no channel gets `handle()`'s own
        `ChannelNotRegistered` the moment a mode needs one, never a
        silent no-op."""
        return self._communication
    @property
    def ready(self) -> bool:
        """True once Connect Founder Runtime succeeded.
        Independent of `render_founder_surface`, which this process
        cannot perform and does not need to in order for the data this
        surface will render to be correct and live.
        """
        connected = self._report.step("connect_founder_runtime")
        return connected is not None and connected.ok
    def snapshot(self) -> dict[str, Any]:
        """Every section at once. `FounderRuntime`'s own method — nothing
        added, nothing renamed."""
        return self._runtime.snapshot()
    def handle(self, envelope: dict[str, Any]) -> dict[str, Any]:
        """The one door out, unchanged from C23."""
        return self._runtime.handle(envelope)
    def send(self, text: str) -> dict[str, Any]:
        """A founder message, reaching the runtime.
        Records exactly one `user` turn — nothing is executed, no
        provider is called, and no reply is composed. The return value is
        the runtime's own `conversation` section immediately afterward,
        so a caller can watch the sent text arrive without a second
        round trip.
        This is C24's whole answer to *"prove the conversation pipeline
        works end-to-end"*: text goes in, the same text comes back out of
        the runtime's own projection, and nothing else happens.
        """
        if not isinstance(text, str):
            raise TypeError("send() takes the founder's text as a string")
        self._conversation.record("user", text)
        return self._runtime.conversation() or {"entries": []}
    # ---- C30: the founder actually talks to Somesh ----------------------
    def say(self, text: str) -> dict[str, Any]:
        """The founder speaks; Somesh answers if C29 has an answer.
        `send()` above is left exactly as C24 built it — it records the
        founder's turn and composes nothing, and its own tests assert
        *"one send, one entry — never two."* That guarantee is worth
        keeping, so C30 adds a door rather than changing that one.
        What this method may reply with is **entirely C29's**, and the
        two cases it recognises are the two the C29 brief names:
        | Founder says | Somesh answers with |
        |---|---|
        | *"Good morning Somesh"* | `greet()` — C29 |
        | *"Continue"* | `continuity_reply()` — C29 |
        | anything else | nothing, and `reply` is `None` |
        **The third row is not an omission.** Composing prose for
        open-ended founder speech would be a conversational engine, and
        this brief is composition only (*"No new Identity"*). Nothing in
        C1–C29 builds one, so nothing here pretends to. The founder's
        turn is still recorded and still reaches the runtime, which is
        exactly what `send()` already promised.
        Somesh's own turn is recorded under the speaker `SOMESH`, which
        C23's projection maps to the role `system` — never `assistant`.
        """
        if not isinstance(text, str):
            raise TypeError("say() takes the founder's text as a string")
        self._conversation.record("user", text)
        reply = self._compose_reply(text)
        if reply is not None:
            self._conversation.record(SOMESH, reply)
        return {
            "reply": reply,
            "conversation": self._runtime.conversation() or {"entries": []},
        }
    def _compose_reply(self, text: str) -> str | None:
        """Dispatch to C29, or to nothing at all. Composes no prose of
        its own — every string this can return was written by C29."""
        if self._identity is None or self._session is None:
            return None
        if is_continuation_request(text):
            return continuity_reply(self._session)
        if is_greeting(text):
            return greet(self._identity, founder_context(self._runtime, self._clock.now()))
        return None
    def dashboard(self) -> dict[str, Any]:
        """Every founder-facing section at once, freshly read.
        Live rather than cached: `presence`, `environment`, `conversation`
        and the desktop observation are read at call time, which is what
        makes *"Dashboard updates. Environment updates. Presence updates.
        Desktop readiness updates."* true of the same object across two
        calls rather than only at boot.
        """
        if self._identity is None or self._session is None:
            raise RuntimeError(
                "this application was built without a FounderIdentity; there "
                "is no founder for a dashboard to be about"
            )
        return founder_dashboard(
            runtime=self._runtime,
            identity=self._identity,
            session=self._session,
            boot=self._report.as_dict(),
            desktop=self._desktop,
            moment=self._clock.now(),
        )
def boot_founder_edition(
    *,
    probe: SystemProbe | None = None,
    clock: Clock | None = None,
    founder_name: str = DEFAULT_FOUNDER_NAME,
    voice_output: VoiceOutput | None = None,
    text_output: TextOutput | None = None,
    capability_domains: Callable[[], Sequence[str]] | None = None,
) -> FounderEditionApp:
    """Run every step and return what they built.
    `probe` and `clock` are the same injection seam `desktop/` and
    `vigilance/` already expose for their own tests; this function adds no
    new one. Omitted, they default to the real machine and the real
    clock — precisely what a founder's actual launch uses.
    `founder_name` is C30's one new argument, and it is the only fact this
    whole assembly cannot derive from the machine: C29 requires a founder
    name and refuses an empty one, and no component in C1–C29 publishes a
    real person's name. Omitted, it is the generic `"Founder"`.
    `voice_output`/`text_output` are C33's own two — the concrete channel
    objects (C32's `VoiceOutput`/`TextOutput`) a real launcher supplies.
    This function builds no channel of its own: C32's own boundary is
    that `communication/` never constructs an implementation, and
    inventing one here, in the composition root, would be the same
    violation one layer up. Both default to `None`, which is
    `CommunicationEngine`'s own supported "wired and idle" state — a mode
    that later needs a channel nobody registered fails loudly
    (`ChannelNotRegistered`) rather than silently.
    """
    steps: list[BootStep] = []
    # Desktop layer components (built in steps 4,5,6)
    # ── 1 · Initialize Runtime ──────────────────────────────────────────
    # The door opens unwired, before anything it might hold is ready.
    # `FounderRuntime()` with no arguments is already C23's own supported
    # state — "an unwired runtime still opens" — so this step can only
    # fail if the class itself cannot be constructed, which would mean
    # the founder_runtime package failed to import.
    try:
        FounderRuntime()
        steps.append(BootStep("runtime", OK, "the founder runtime door is open"))
    except Exception as exc:  # noqa: BLE001 — a boot step reports, never crashes
        steps.append(BootStep("runtime", UNAVAILABLE, str(exc)))
        return _abort(steps)
    # ── 2 · Initialize Presence ──────────────────────────────────────────
    # Attests over whatever is registered — nothing, at this milestone.
    # See the module docstring for why this does not seed a domain from
    # the environment scan that has not run yet.
    registry = DomainRegistry()
    resolved_clock = clock or SystemClock()
    try:
        coverage: Coverage | None = VigilanceAttestation(
            registry, resolved_clock
        ).attest()
        detail = (
            "attested; complete"
            if coverage.complete
            else f"attested; incomplete — {_NO_DOMAINS_WATCHED}"
        )
        steps.append(BootStep("presence", OK, detail))
    except Exception as exc:  # noqa: BLE001
        coverage = None
        steps.append(BootStep("presence", UNAVAILABLE, str(exc)))
    # ── 3 · Initialize Environment Intelligence ─────────────────────────
    # The one step that actually touches the machine — through the
    # Desktop Executive's own scanner, never a second one.
    resolved_probe = probe or RealSystemProbe()
    intelligence: EnvironmentIntelligence | None = None
    # C30 keeps the inventory this step already produced. C24 derived
    # intelligence from it and let it fall out of scope; the desktop layer
    # below needs the same scan, and scanning a second time would be
    # exactly the duplicated initialization this brief forbids — as well
    # as a second reading of a machine that may have changed in between.
    inventory: MachineInventory | None = None
    try:
        # `discover()`'s own `clock` parameter is a zero-arg callable,
        # not the `Clock` protocol `VigilanceAttestation` takes — passed
        # through so the same injected clock stamps both, and two boots
        # against the same fake machine agree byte-for-byte.
        inventory = discover(resolved_probe, clock=resolved_clock.now)
        intelligence = derive_intelligence(inventory)
        steps.append(
            BootStep(
                "environment_intelligence",
                OK,
                f"{len(inventory.applications)} applications scanned",
            )
        )
    except Exception as exc:  # noqa: BLE001
        steps.append(BootStep("environment_intelligence", UNAVAILABLE, str(exc)))
    # ── 9 · Desktop Executive ────────────────────────────────────────────
    # C25's authored knowledge, and the C26 door built over it. One
    # `DesktopExecutiveV2` serves both: `DesktopExecutor()` would build its
    # own if handed none, and two knowledge bases in one process is the
    # duplication this step exists to prevent.
    executive: DesktopExecutiveV2 | None = None
    executor: DesktopExecutor | None = None
    try:
        executive = DesktopExecutiveV2()
        executor = DesktopExecutor(desktop_executive=executive)
        steps.append(
            BootStep(
                "desktop_executive",
                OK,
                f"{len(executive.knowledge_base.profiled_keys())} application "
                "profiles available",
            )
        )
    except Exception as exc:  # noqa: BLE001
        steps.append(BootStep("desktop_executive", UNAVAILABLE, str(exc)))
    # ── 10 · Desktop Perception ──────────────────────────────────────────
    # C27. Built before the Operator because the Operator is built *from*
    # it — see STEP_NAMES for why this is dependency order rather than the
    # brief's layering order.
    observer: DesktopObserver | None = None
    try:
        observer = DesktopObserver()
        steps.append(BootStep("desktop_perception", OK, "the desktop can be observed"))
    except Exception as exc:  # noqa: BLE001
        steps.append(BootStep("desktop_perception", UNAVAILABLE, str(exc)))
    # ── 11 · Desktop Operator ────────────────────────────────────────────
    # C28, handed the executor and observer built above rather than
    # constructing its own. Wired and idle: nothing in C1–C29 turns founder
    # speech into a DesktopTask, so no door here hands it one.
    desktop: DesktopLayer | None = None
    if executive is not None and executor is not None and observer is not None:
        try:
            desktop = DesktopLayer(
                executive=executive,
                executor=executor,
                observer=observer,
                operator=DesktopOperator(executor, observer),
                inventory=inventory,
            )
            steps.append(
                BootStep(
                    "desktop_operator",
                    OK,
                    "one executor and one observer, shared with perception",
                )
            )
        except Exception as exc:  # noqa: BLE001
            steps.append(BootStep("desktop_operator", UNAVAILABLE, str(exc)))
    else:
        steps.append(
            BootStep(
                "desktop_operator",
                UNAVAILABLE,
                "the executor or the observer could not be built, and an "
                "operator without both would have to construct its own",
            )
        )
    # ── 4 · Initialize Conversation ──────────────────────────────────────
    # Layer 1 is in-process and never persisted, by its own docstring —
    # a fresh instance per boot is the correct lifetime, not a shortcut.
    try:
        conversation = ConversationMemory()
        steps.append(BootStep("conversation", OK, "session memory ready"))
    except Exception as exc:  # noqa: BLE001
        steps.append(BootStep("conversation", UNAVAILABLE, str(exc)))
        return _abort(steps)
    # ── 5 · Connect Founder Runtime ──────────────────────────────────────
    # Every prior step's output, handed to C23's own constructor. This is
    # the only place any of the four are assembled together.
    try:
        runtime = FounderRuntime(
            intelligence=intelligence,
            coverage=coverage,
            registry=registry if coverage is not None else None,
            conversation=conversation,
            desktop=desktop,  # C30 desktop layer
        )
        present = sum(1 for s in runtime.sources() if s.present)
        steps.append(
            BootStep(
                "connect_founder_runtime",
                OK,
                f"{present} of {len(runtime.sources()) - 1} sources wired",
            )
        )
    except Exception as exc:  # noqa: BLE001
        steps.append(BootStep("connect_founder_runtime", UNAVAILABLE, str(exc)))
        return _abort(steps, conversation=conversation)
    # ── 6 · Founder Identity ─────────────────────────────────────────────
    # C29, constructed over **this boot's own** ConversationMemory. The
    # session is a lens on that one memory, never a second history — which
    # is what makes "no duplicated state" true rather than intended.
    identity: FounderIdentity | None = None
    session: FounderSession | None = None
    try:
        identity = FounderIdentity(founder_name=founder_name)
        session = FounderSession(conversation)
        steps.append(
            BootStep(
                "founder_identity",
                OK,
                f"{identity.assistant_name} is awake for {identity.founder_name}",
            )
        )
    except Exception as exc:  # noqa: BLE001
        steps.append(BootStep("founder_identity", UNAVAILABLE, str(exc)))
    # ── 7 · Conversation Engine ──────────────────────────────────────────
    # C31, constructed over the same runtime, identity, session and
    # conversation every step above already produced. Nothing here
    # composes a sentence — every reply this engine will ever return was
    # already written by conversation_engine/composer.py.
    conv_engine: ConversationEngine | None = None
    try:
        if identity is None or session is None:
            raise RuntimeError(
                "founder identity did not complete; there is no founder for "
                "the conversation engine to answer on behalf of"
            )
        # `capability_domains` is how the Brain learns which domains it
        # can act in without ever reading the Operator's capability
        # registry itself. The composition root supplies it (it owns
        # Mission Control); absent, the composer answers honestly that it
        # cannot act rather than inventing a capability.
        conv_engine = ConversationEngine(
            runtime=runtime, identity=identity, session=session,
            conversation=conversation, capability_domains=capability_domains,
        )
        steps.append(
            BootStep(
                "conversation_engine", OK,
                "Somesh can answer greetings, continuations and status/"
                "activity/priority/build speech",
            )
        )
    except Exception as exc:  # noqa: BLE001
        steps.append(BootStep("conversation_engine", UNAVAILABLE, str(exc)))
    # ── 8 · Communication Layer ──────────────────────────────────────────
    # C32, holding whatever channels this boot was handed. Registers
    # nothing itself — see this function's own docstring for why a
    # channel implementation is a launcher's job, never this one's.
    communication: CommunicationEngine | None = None
    try:
        if conv_engine is None:
            raise RuntimeError(
                "the conversation engine did not complete; there is nothing "
                "for the communication layer to route to"
            )
        communication = CommunicationEngine(
            conversation_engine=conv_engine, conversation=conversation,
            voice_output=voice_output, text_output=text_output,
        )
        registered = [
            name for name, channel in
            (("voice", voice_output), ("text", text_output))
            if channel is not None
        ]
        steps.append(
            BootStep(
                "communication", OK,
                f"channels registered: {', '.join(registered) or 'none'}",
            )
        )
    except Exception as exc:  # noqa: BLE001
        steps.append(BootStep("communication", UNAVAILABLE, str(exc)))
    # ── 12 · Dashboard ───────────────────────────────────────────────────
    # Composed, not cached. This step proves the sections can be assembled
    # at all; every later read goes back to the live components.
    try:
        if identity is None or session is None:
            raise RuntimeError(
                "the founder identity step did not complete, so there is no "
                "founder for a dashboard to be about"
            )
        drawn = founder_dashboard(
            runtime=runtime,
            identity=identity,
            session=session,
            boot=BootReport(steps=tuple(steps)).as_dict(),
            desktop=desktop,
            moment=resolved_clock.now(),
        )
        steps.append(
            BootStep("dashboard", OK, f"{len(drawn)} sections composed")
        )
    except Exception as exc:  # noqa: BLE001
        steps.append(BootStep("dashboard", UNAVAILABLE, str(exc)))
    # ── 13 · Render Founder Surface ──────────────────────────────────────
    steps.append(
        BootStep("render_founder_surface", OUT_OF_SCOPE, _RENDER_SURFACE_REASON)
    )
    # ── 14 · Ready ────────────────────────────────────────────────────────
    # Looked up by name rather than by position: C30 inserted five steps
    # between connect and render, and a positional read would have gone on
    # working while silently reporting a different step's outcome.
    connected = next(
        (s for s in steps if s.name == "connect_founder_runtime"), None
    )
    if connected is not None and connected.ok:
        steps.append(BootStep("ready", OK, "the founder runtime is connected and live"))
    else:  # pragma: no cover — connect() already returned above on failure
        steps.append(BootStep("ready", UNAVAILABLE, "connect_founder_runtime did not succeed"))
    return FounderEditionApp(
        runtime=runtime,
        conversation=conversation,
        report=BootReport(steps=tuple(steps)),
        identity=identity,
        session=session,
        desktop=desktop,
        clock=resolved_clock,
        conversation_engine=conv_engine,
        communication=communication,
    )
def _abort(
    steps: list[BootStep], *, conversation: ConversationMemory | None = None
) -> FounderEditionApp:
    """A step that could not be recovered from. The runtime still opens
    unwired — C23's own supported state — so a founder sees *why* rather
    than a crash."""
    steps.append(
        BootStep(
            "connect_founder_runtime",
            UNAVAILABLE,
            "a preceding step failed; connecting would wire in a state "
            "this boot sequence cannot vouch for",
        )
    )
    # Every C30/C33 step, reported unavailable for the same stated reason.
    # Silence would be worse than a repeated sentence: a report that
    # simply omitted the identity, engine, communication, desktop and
    # dashboard steps would read as though they had never been part of
    # this boot sequence.
    for name in (
        "founder_identity",
        "conversation_engine",
        "communication",
        "desktop_executive",
        "desktop_perception",
        "desktop_operator",
        "dashboard",
    ):
        steps.append(
            BootStep(
                name,
                UNAVAILABLE,
                "a preceding step failed; this layer was never reached",
            )
        )
    steps.append(
        BootStep("render_founder_surface", OUT_OF_SCOPE, _RENDER_SURFACE_REASON)
    )
    steps.append(BootStep("ready", UNAVAILABLE, "boot did not complete"))
    return FounderEditionApp(
        runtime=FounderRuntime(),
        conversation=conversation or ConversationMemory(),
        report=BootReport(steps=tuple(steps)),
    )
