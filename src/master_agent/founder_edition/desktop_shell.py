"""The Founder Desktop Application shell — Product Veda integration.

*\"You are the product assembly engineer... ASSEMBLE. WIRE. POLISH.
PACKAGE.\"* This module is the wiring: it opens one native window (via
`pywebview`, wrapping the OS's own WebView2/WebKit engine — already
declared as an optional dependency, `pyproject.toml`'s `ui` extra) that
hosts `desktop_app/web/index.html`, and exposes exactly fifteen methods to
that page's JavaScript (nine when this was written; the approval,
completion, execution-status and mode contracts have been wired through
the same bridge since). Every one of them is a thin call onto
`FounderEditionApp` (C24/C30) and the pieces it already wires (C29 Identity,
C31 Conversation Engine, C32 Communication Layer) — this module composes
no reply, plans no mission, and derives no fact the backend did not
already publish.

## The one new concrete implementation

C32's `TextOutput` is deliberately abstract (`communication/channels.py`).
`BridgeTextOutput` is its one concrete body here: `emit()` does nothing,
because the founder-facing text already reaches the page as the return
value of `send_message()` — the same reply, read once, not composed
twice. Registering *something* is required only because
`CommunicationEngine` refuses to silently drop text-mode output
(`ChannelNotRegistered`); a no-op sink is the honest way to say "the
Python side is not the one drawing this text; JavaScript is."

## The spontaneous greeting is `greet()`, called differently, not rewritten

Product Veda's *"Somesh greets the Founder according to the current
system time"* on launch, unprompted, is a different trigger than C29's
`greet()` was built to answer to (a founder's own *"Good morning
Somesh"*). This module does not write a second greeting composer — it
calls the same `founder_identity.greet()` function C29 already built,
with a `FounderContext` built from the real local clock
(`datetime.now().astimezone()`, read here because this is the launcher —
the one place in the whole assembly real time is permitted to enter, the
same discipline `founder_edition/console.py` already established).

## The mode-switch gap, guarded the same way `console.py` guards it

`CommunicationRouter` still recognises *"switch to voice"/"switch to
text"* as phrases (C32), and Product Veda explicitly forbids mode
switching as a founder-facing concept (*"No mode changes... one
conversation, two input methods"*). If a founder ever types one of those
phrases as ordinary conversation, the router would flip its internal mode
and the next reply would raise `ChannelNotRegistered` — the same gap
`Engineering/HEALTH_C33.md` §5 already recorded. `send_message()` catches
it and recovers exactly as `console.py` does: a real *"switch to text"*
request through the same engine, never a fabricated reply.

## C34.1 — voice moved entirely to `voice_pipeline.VoicePipeline`

C34's build used the browser's own Web Speech API. C34.1's brief judged
that unable to satisfy automatic device tracking and asked for a proper
local replacement, *"not a partially working implementation."* This
module now owns one `VoicePipeline` (local Whisper STT, local Piper TTS)
and pushes its events into the page with `window.evaluate_js` — there is
no JavaScript speech recognition or synthesis code left anywhere in
`desktop_app/web/`. `send_message()` speaks every reply, regardless of
whether the founder typed or talked, because Product Veda's own
governing sentence is *"Voice is primary... both are simultaneously
live."*
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import os
import random
import threading
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Any

import bottle
from bottle import Bottle, static_file
from wsgiref.simple_server import WSGIServer, WSGIRequestHandler, make_server
from socketserver import ThreadingMixIn

from master_agent.communication import (
    ChannelNotRegistered,
    CommunicationRequest,
    CommunicationResponse,
    Source,
    TextOutput,
)
from master_agent.founder_edition.boot import FounderEditionApp, boot_founder_edition
from master_agent.founder_edition.voice_pipeline import VoicePipeline
from master_agent.founder_identity import FounderContext, greet

# Custom BottleServer that fixes the pywebview 6.x asset() signature issue
# where @app.route('/') and @app.route('/<file:path>') both call asset(file)
# but '/' doesn't provide a 'file' parameter, causing TypeError.
class FixedBottleServer:
    def __init__(self) -> None:
        self.root_path = '/'
        self.running = False
        self.address = None
        self.js_callback = {}
        self.js_api_endpoint = None
        self.uid = str(uuid.uuid1())

    @classmethod
    def start_server(
        cls, urls: list[str], http_port: int | None = None, keyfile: str | None = None, certfile: str | None = None
    ) -> tuple[str, str | None, "FixedBottleServer"]:
        from webview import _state
        from webview.util import abspath, is_app, is_local_url

        logger = logging.getLogger('pywebview')

        apps = [u for u in urls if is_app(u)]
        server = cls()

        if len(apps) > 0:
            app = apps[0]
            common_path = '.'
        else:
            local_urls = [u.split('#')[0] for u in urls if is_local_url(u)]
            common_path = os.path.commonpath(local_urls) if len(local_urls) > 0 else None
            if common_path is not None and not os.path.isdir(abspath(common_path)):
                common_path = os.path.dirname(common_path)
            logger.debug(f'Common path for local URLs: {common_path}')
            server.root_path = abspath(common_path) if common_path is not None else None
            logger.debug(f'HTTP server root path: {server.root_path}')
            app = Bottle()

            @app.post(f'/js_api/{server.uid}')
            def js_api():
                bottle.response.headers['Access-Control-Allow-Origin'] = '*'
                bottle.response.headers['Access-Control-Allow-Methods'] = (
                    'PUT, GET, POST, DELETE, OPTIONS'
                )
                bottle.response.headers['Access-Control-Allow-Headers'] = (
                    'Origin, Accept, Content-Type, X-Requested-With, X-CSRF-Token'
                )

                body = json.loads(bottle.request.body.read().decode('utf-8'))
                if body['uid'] in server.js_callback:
                    return json.dumps(server.js_callback[body['uid']](body))
                else:
                    logger.error(f'JS callback function is not set for window {body["uid"]}')

            @app.route('/')
            def index():
                if not server.root_path:
                    return ''
                bottle.response.set_header('Cache-Control', 'no-cache, no-store, must-revalidate')
                bottle.response.set_header('Pragma', 'no-cache')
                bottle.response.set_header('Expires', 0)
                return static_file('index.html', root=server.root_path)

            @app.route('/<file:path>')
            def asset(file):
                if not server.root_path:
                    return ''
                bottle.response.set_header('Cache-Control', 'no-cache, no-store, must-revalidate')
                bottle.response.set_header('Pragma', 'no-cache')
                bottle.response.set_header('Expires', 0)
                return static_file(file, root=server.root_path)

        server.root_path = abspath(common_path) if common_path is not None else None
        server.port = http_port or cls._get_random_port()
        if keyfile and certfile:
            server_adapter = SSLWSGIRefServer()
            server_adapter.port = server.port
            setattr(server_adapter, 'pywebview_keyfile', keyfile)
            setattr(server_adapter, 'pywebview_certfile', certfile)
        else:
            server_adapter = ThreadedAdapter
        server.thread = threading.Thread(
            target=lambda: bottle.run(
                app=app, server=server_adapter, port=server.port, quiet=not _state['debug']
            ),
            daemon=True,
        )
        server.thread.start()

        server.running = True
        protocol = 'https' if keyfile and certfile else 'http'
        server.address = f'{protocol}://127.0.0.1:{server.port}/'
        cls.common_path = common_path
        server.js_api_endpoint = f'{server.address}js_api/{server.uid}'

        return server.address, common_path, server

    @staticmethod
    def _get_random_port() -> int:
        while True:
            port = random.randint(1023, 65535)
            import socket
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                try:
                    sock.bind(('localhost', port))
                except OSError:
                    continue
                else:
                    return port

    @property
    def is_running(self) -> bool:
        return self.running


class ThreadedAdapter(bottle.ServerAdapter):
    def run(self, handler) -> None:
        if self.quiet:
            class QuietHandler(WSGIRequestHandler):
                def log_request(*args, **_):
                    pass
            self.options['handler_class'] = QuietHandler

        class ThreadAdapter(ThreadingMixIn, WSGIServer):
            pass

        server = make_server(
            self.host, self.port, handler, server_class=ThreadAdapter, **self.options
        )
        server.serve_forever()


class SSLWSGIRefServer(bottle.ServerAdapter):
    def run(self, handler) -> None:
        import ssl
        import socket

        class FixedHandler(WSGIRequestHandler):
            def address_string(self) -> str:
                return self.client_address[0]

            def log_request(*args, **kw) -> None:
                if not self.quiet:
                    return WSGIRequestHandler.log_request(*args, **kw)

        handler_cls = self.options.get('handler_class', FixedHandler)
        server_cls = self.options.get('server_class', WSGIServer)

        if ':' in self.host:
            if server_cls.address_family == socket.AF_INET:
                class server_cls(server_cls):
                    address_family = socket.AF_INET6

        ssl_context = ssl.SSLContext()
        ssl_context.load_cert_chain(self.pywebview_certfile, self.pywebview_keyfile)
        self.srv = make_server(self.host, self.port, handler, server_cls, handler_cls)
        self.srv.socket = ssl_context.wrap_socket(self.srv.socket, server_side=True)
        self.port = self.srv.server_port

        if os.path.exists(self.pywebview_keyfile):
            os.unlink(self.pywebview_keyfile)
        try:
            self.srv.serve_forever()
        except KeyboardInterrupt:
            self.srv.server_close()
            raise


CONVERSATION_ID = "founder-surface"

#: Source strings the page may send, mapped to C32's own enum. Closed —
#: a page sending anything else is refused rather than guessed at.
_SOURCE_BY_NAME = {"voice": Source.VOICE, "text": Source.TEXT}


class BridgeTextOutput(TextOutput):
    """The one required `TextOutput`. Does nothing — see the module
    docstring for why doing nothing here is correct rather than
    incomplete: the reply already reached the page as `send_message()`'s
    own return value."""

    def emit(self, response: CommunicationResponse) -> None:
        return None


def _local_now() -> datetime:
    return datetime.now().astimezone()


def _founder_seed(founder_name: str) -> int:
    digest = hashlib.sha256(founder_name.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big")


class DesktopShellApi:
    """The whole bridge surface `window.pywebview.api` exposes to the
    page. Nine methods — nothing else is reachable from JavaScript.
    `voice` is optional: a machine where the local pipeline could not
    load still gets every other method, honestly, with voice absent."""

    def __init__(
        self, app: FounderEditionApp, voice: VoicePipeline | None = None,
        open_settings: Callable[[], None] | None = None,
        submit_objective: Callable[[str], dict[str, Any]] | None = None,
        default_mode: str = "",
        get_execution_status: Callable[[], dict[str, Any]] | None = None,
        confirm_completion: Callable[[str], dict[str, Any]] | None = None,
        decide_approval: Callable[..., dict[str, Any]] | None = None,
        set_mode: Callable[[str], None] | None = None,
        record_interaction: Callable[..., None] | None = None,
    ) -> None:
        self._app = app
        self._voice = voice
        self._muted = False
        self._open_settings = open_settings
        # Injected the same way `open_settings` already is: this package
        # is architecture-guarded against importing the Planner/Mission
        # Control/Broker/Runtime it takes to actually run an objective
        # (`tests/test_founder_edition_boot.py::TestNothingExecutesOrCallsAI`),
        # so `kalpavriksha_desktop.py` — the one place outside the guard —
        # builds that pipeline and hands this module only a plain
        # callable. `None` on a machine with no reasoning provider
        # configured; conversation still works, an objective just falls
        # through to the existing "I don't understand" reply below.
        self._submit_objective = submit_objective
        # Task 2.5 — the Hyper Agent status/completion contract. Same
        # injection shape as `submit_objective`, for the same architectural
        # reason: this module states no opinion about execution state, it
        # only relays the one callable the composition root handed it.
        self._get_execution_status = get_execution_status
        # The founder's answer to an open approval. Same injection shape
        # and the same reason: Mission Control owns the decision, this
        # module only carries the founder's word to it.
        self._decide_approval = decide_approval
        self._set_mode = set_mode
        #: ADR-0025. Injected rather than imported: this package is
        #: architecture-guarded against reaching into the runtime, and an
        #: audit trail must never be able to break the product it observes.
        self._record_interaction = record_interaction
        #: LOCAL / AI MODE / BOTH. Injected, not imported, for the same
        #: reason `record_interaction` above is: this package is
        #: architecture-guarded against reaching into the Mission OS
        #: (`tests/test_founder_edition_assembly.py::TestOnlyComposition`),
        #: and `master_agent.planner.modes` is on the far side of that
        #: line. The composition root owns the vocabulary and already
        #: normalises with it; importing a second copy here put the
        #: surface package inside the Planner's namespace to read two
        #: constants.
        self._mode: str = default_mode or "both"
        self._confirm_completion = confirm_completion

    def get_founder_seed(self) -> int:
        identity = self._app.identity
        name = identity.founder_name if identity is not None else "Founder"
        return _founder_seed(name)

    def greet(self) -> dict[str, Any]:
        """One spontaneous greeting, from C29's own `greet()`, banded by
        the real local system clock — never a fixed string."""
        identity = self._app.identity
        if identity is None:
            return {"reply": None, "presence": None}
        moment = _local_now()
        context = FounderContext(
            moment=moment,
            environment_ready=self._app.runtime.environment() is not None,
            conversation_ready=self._app.runtime.conversation() is not None,
            presence_ready=self._presence_complete(),
        )
        reply = greet(identity, context)
        # This bridge call fires as soon as the page's own startup script
        # runs (`runStartup()` calls `fetchGreeting()` first thing) — the
        # same moment `voice.start()`'s model-loading thread has, at best,
        # only just begun loading Whisper/Piper from disk. `speak()`
        # queues this text itself when TTS is not ready yet and flushes it
        # the moment loading finishes (`VoicePipeline._load_and_open`), so
        # this call is correct to make unconditionally rather than only
        # when `voice.tts_ready` already happens to be true.
        if self._voice is not None and reply:
            self._voice.speak(reply)
        # The first thing Onkar sees. It is a founder-visible Chief-of-Staff
        # interaction under ADR-0025 and belongs in the same trail as every
        # other one -- it was absent only because the boot greeting reaches
        # the page through this bridge call rather than `send_message()`.
        # Recorded here, at the one place the exact shown text exists; no
        # separate greeting history, and no routing through mission
        # machinery to make an audit work.
        self._audit("chief_of_staff", reply, interaction_type="greeting")
        return {"reply": reply, "presence": None}

    def send_message(self, text: str, source: str = "text") -> dict[str, Any]:
        if self._app.communication is None:
            return {"reply": None}
        asked = self._audit("founder", text)
        resolved_source = _SOURCE_BY_NAME.get(source, Source.TEXT)
        request = CommunicationRequest(
            source=resolved_source, content=text,
            timestamp=_local_now(), conversation_id=CONVERSATION_ID,
        )
        try:
            routed = self._app.communication.handle(request)
        except ChannelNotRegistered:
            recovery = CommunicationRequest(
                source=Source.TEXT, content="switch to text",
                timestamp=_local_now(), conversation_id=CONVERSATION_ID,
            )
            self._app.communication.handle(recovery)
            return {"reply": None}
        if routed is None:
            # ConversationEngine's own "I don't recognise this" signal —
            # not a new classifier, the existing one. An objective the
            # founder typed but the answer layer has nothing to say about
            # is exactly what the Planner pipeline exists for.
            if self._submit_objective is not None:
                outcome = self._submit_objective(text)
                # A mission reply is exactly as founder-facing as a
                # conversational one — the founder-spoken objective that
                # got here voiced the request, and hearing nothing back
                # would break the same voice loop the branch below
                # honours. `outcome["reply"]` is already the one plain
                # sentence `_describe_result`/the refusal/timeout paths
                # produce; nothing here composes a second one.
                if self._voice is not None and outcome.get("reply"):
                    self._voice.speak(outcome["reply"])
                # What the founder was actually SHOWN. The whole point of
                # ADR-0025 is being able to compare this against what the
                # backend believed happened.
                # Every identifier the mission owner already had at the
                # moment it replied, projected onto the record -- plus a
                # back-reference to the founder turn that caused it.
                self._audit(
                    "chief_of_staff", outcome.get("reply"),
                    interaction_type=outcome.get("interaction_type") or "mission_result",
                    mission_id=outcome.get("mission_id"),
                    status=outcome.get("status"),
                    clarification_id=outcome.get("clarification_id"),
                    approval_id=outcome.get("approval_id"),
                    completion_id=outcome.get("completion_id"),
                    in_reply_to=asked,
                )
                return outcome
            return {"reply": None}
        if self._voice is not None:
            self._voice.speak(routed.response.spoken)
        self._audit("chief_of_staff", routed.response.display,
                    interaction_type="conversation", in_reply_to=asked)
        return {"reply": routed.response.display}

    def _audit(self, direction: str, text: Any, **fields: Any) -> str | None:
        """Best-effort, always. A founder's request must never fail because
        a log write did -- a missing record is recoverable, a broken
        session is not."""
        if self._record_interaction is None or not text:
            return None
        with contextlib.suppress(Exception):
            return self._record_interaction(direction, str(text), **fields)
        return None

    def get_dashboard(self) -> dict[str, Any]:
        return self._app.dashboard()

    def get_execution_status(self) -> dict[str, Any]:
        """Task 2.5 §8 — the current objective's live status, as a plain
        semantic contract (status/step/timing/attempt/completion — no
        color, animation, or visual metaphor; those are Hyper Agent's
        decisions, made from these fields). `{}` on a machine with no
        reasoning provider configured, or before any objective has run —
        an honest "nothing to report" rather than a fabricated idle state.
        """
        if self._get_execution_status is None:
            return {}
        return self._get_execution_status()

    def confirm_completion(self, completion_id: str) -> dict[str, Any]:
        """Task 2.5 §D — the one action that turns a verified objective
        into a founder-facing completed one. Relays to Mission Control's
        own `confirm_completion`; this module decides nothing about
        whether the answer is allowed, only that the founder gave one."""
        if self._confirm_completion is None:
            return {}
        return self._confirm_completion(completion_id)

    def decide_approval(
        self, approval_id: str, approved: bool, note: str = "",
    ) -> dict[str, Any]:
        """The founder's decision on an open approval.

        Relays to Mission Control's own `approve`/`reject`. This module
        decides nothing about whether the decision is allowed -- it only
        carries the fact that the founder made one. A rejection is a real
        decision and ends the task; it is not a failure of the work.
        """
        if self._decide_approval is None:
            return {}
        return self._decide_approval(approval_id, bool(approved), note or "")

    def toggle_mute(self) -> dict[str, Any]:
        """Founder-chosen silence — `03_VOICE_EXPERIENCE §3.5`'s `muted`
        state. Returns the new state so the page does not have to guess
        at it from a separate push landing first."""
        if self._voice is None:
            return {"muted": None}
        self._muted = not self._muted
        self._voice.set_muted(self._muted)
        return {"muted": self._muted}

    def set_mode(self, mode: str) -> dict[str, Any]:
        """The founder's LOCAL / AI MODE / BOTH switch.

        Restored. The three buttons have been on the surface all along and
        the page has always called this, but the method existed only in the
        stale `build/lib/` copy -- and the page swallows the failure
        (`.catch(() => null)`), so every click was silently inert and every
        session ran as whatever the Planner defaulted to.

        Session-scoped by design, exactly as the historical version was:
        an operating mode is a decision about right now, not a preference
        to be remembered and later surprise a founder who has forgotten
        setting it.

        The mode is *stored* here and *read* by the Planner, which is the
        component that can act on it. This method decides nothing.
        """
        # The root normalises -- it holds the vocabulary -- and returns
        # what it resolved. This surface stores the answer rather than
        # deriving it, so there is one normalisation in the process.
        resolved = mode
        if self._set_mode is not None:
            with contextlib.suppress(Exception):
                returned = self._set_mode(mode)
                if isinstance(returned, str) and returned:
                    resolved = returned
        self._mode = resolved
        return {"mode": resolved}

    def get_mode(self) -> dict[str, Any]:
        return {"mode": self._mode}

    def open_microphone_settings(self) -> None:
        """`03_VOICE_EXPERIENCE §3.5`'s `denied` recovery path: a click on
        the mic (or the "here" word in its secondary copy) opens the
        Windows Settings page that actually controls this. This module
        does not touch the OS itself — `master_agent.founder_edition` is
        guarded against importing `os` directly — so `open_settings` is
        injected by `kalpavriksha_desktop.py`, the one place outside this
        guarded package permitted to call `os.startfile`."""
        if self._open_settings is None:
            return
        with contextlib.suppress(Exception):
            # opening Settings must not crash the app on a machine where
            # the URI scheme is missing (non-Windows dev run, older build)
            self._open_settings()

    def interrupt_speech(self) -> None:
        """`03_VOICE_EXPERIENCE §3.4` — the founder typed, clicked the
        mic, or pressed Escape while Somesh was speaking. The page runs
        its own visual interrupt sequence (waveform cut, tree state,
        "— interrupted" marker) unconditionally; this just tells the
        pipeline to actually stop the audio, an honest no-op if nothing
        is speaking (`VoicePipeline.interrupt_speech`'s own guard)."""
        if self._voice is not None:
            self._voice.interrupt_speech()

    def abandon_voice_capture(self) -> None:
        """`03_VOICE_EXPERIENCE §3.7` — the founder started typing while
        their own utterance was still being captured (`capturing-
        speech`), not while Somesh was speaking; a distinct scenario
        from `interrupt_speech()` above, with its own bridge method
        because it discards the founder's own in-flight microphone
        buffer rather than stopping Somesh's playback."""
        if self._voice is not None:
            self._voice.abandon_capture()

    def get_startup_diagnostics(self) -> dict[str, bool]:
        """Startup Diagnostics overlay — one honest check per subsystem,
        so a founder (or whoever's helping them) sees exactly where
        startup stopped instead of a silent blank window.

        `stt_loaded`/`tts_loaded` say a model was loaded into memory
        (INITIALIZED). `mic_live` is the separate, stronger claim that a
        real microphone stream is open against real hardware right now
        (LIVE DEVICE VERIFIED) — a machine with no working input device
        can have `stt_loaded=True` and `mic_live=False` simultaneously,
        and that distinction is the point: a founder debugging silence
        needs to know which one failed.
        """
        voice = self._voice
        return {
            "webview_loaded": True,  # this call answering at all proves it
            "conversation_engine_ready": self._app.communication is not None,
            "voice_initialized": voice is not None,
            "stt_loaded": voice is not None and voice.stt_ready,
            "tts_loaded": voice is not None and voice.tts_ready,
            "mic_live": voice is not None and voice.mic_live,
            "dashboard_ready": self._app.dashboard is not None,
        }

    def debug_log(self, data: dict) -> None:
        """Receive debug data from JavaScript for troubleshooting."""
        import logging
        logging.info(f"JS_DEBUG: {data}")

    def _presence_complete(self) -> bool:
        presence = self._app.runtime.presence()
        coverage = presence.get("coverage")
        return bool(coverage and coverage.get("complete"))


def _push(window, function_name: str, *args: Any) -> None:
    """Call a page-global function with JSON-safe arguments. The one
    place this module writes JavaScript source — every argument is
    `json.dumps`-escaped, so a transcript containing a quote or a
    backslash cannot break out of the call."""
    payload = ", ".join(json.dumps(arg) for arg in args)
    with contextlib.suppress(Exception):
        # A closed/closing window must not crash the voice pipeline's own
        # background thread — losing one push is the correct failure mode.
        window.evaluate_js(f"{function_name}({payload})")


def _build_voice(
    window, *, whisper_model: str, piper_model_path: str | None,
    mic_permission_checker: Callable[[], bool] | None = None,
    input_device_resolver: Callable[[], str | None] | None = None,
    output_device_resolver: Callable[[], str | None] | None = None,
    microphone_enabled: bool = True,
) -> VoicePipeline:
    """One `VoicePipeline`, wired to push its three event kinds into the
    page. Construction never fails — a model that cannot load reports
    `error` through the same `on_state` push every other absence uses
    (`VoicePipeline._load_and_open`'s own try/except)."""
    # An automated run must not listen to the room. Ambient founder speech
    # reached a reasoning provider during a packaged test because the
    # harness drove the same process, on the same microphone, that the
    # founder was speaking near.
    #
    # `microphone_enabled=False` skips the capture device entirely for
    # exactly that case. Injected rather than read here: this package is
    # architecture-guarded against importing `os` directly, so the
    # composition root owns the environment and hands down the decision --
    # the same way `mic_permission_checker` and `open_settings` already
    # work. A voice-input test that needs the device leaves it True.
    if not microphone_enabled:
        return None

    voice = VoicePipeline(
        on_state=lambda state: _push(window, "onVoiceState", state),
        on_amplitude=lambda amplitude: _push(window, "onVoiceAmplitude", amplitude),
        on_transcript=lambda text: _push(window, "onTranscript", text),
        whisper_model=whisper_model,
        piper_model_path=piper_model_path,
        mic_permission_checker=mic_permission_checker,
        input_device_resolver=input_device_resolver,
        output_device_resolver=output_device_resolver,
    )
    return voice


def create_window(
    *,
    founder_name: str,
    web_dir: str,
    debug: bool = False,
    voice_model_path: str | None = None,
    whisper_model: str = "base.en",
    mic_permission_checker: Callable[[], bool] | None = None,
    open_settings: Callable[[], None] | None = None,
    input_device_resolver: Callable[[], str | None] | None = None,
    output_device_resolver: Callable[[], str | None] | None = None,
    microphone_enabled: bool = True,
    submit_objective: Callable[[str], dict[str, Any]] | None = None,
    default_mode: str = "",
    get_execution_status: Callable[[], dict[str, Any]] | None = None,
    confirm_completion: Callable[[str], dict[str, Any]] | None = None,
    capability_domains: Callable[[], Any] | None = None,
    decide_approval: Callable[..., dict[str, Any]] | None = None,
    set_mode: Callable[[str], None] | None = None,
    record_interaction: Callable[..., None] | None = None,
) -> FounderEditionApp:
    """Boot Founder Edition, start the local voice pipeline, and open the
    one native window.

    Imports `webview` lazily — it is an optional dependency
    (`pyproject.toml`'s `ui` extra) and this module must remain importable
    (for tests) on a machine that has not installed it.

    The voice pipeline is started *after* the window exists (its
    callbacks push into that window) and is never awaited: model loading
    takes seconds, and Product Veda's own rule is that *"the founder
    never waits on a flourish"* — the tree grows and the composer is
    usable long before Whisper/Piper finish loading, and the mic simply
    reports `unavailable`-then-`armed` as loading completes.
    """
    import webview

    app = boot_founder_edition(
        founder_name=founder_name, text_output=BridgeTextOutput(),
        capability_domains=capability_domains,
    )

    # `?debug=1` is how the page learns it was started with --debug. The
    # startup-diagnostics panel is development instrumentation and stays
    # hidden on a healthy founder launch; this is the switch that brings
    # it back for whoever is debugging a dead startup, alongside its own
    # rule of appearing unasked whenever a check actually fails.
    window = webview.create_window(
        "Kalpavriksha",
        url=f"{web_dir}/index.html" + ("?debug=1" if debug else ""),
        width=1440, height=900,
        min_size=(1180, 760),
        background_color="#05070A",
        # pywebview defaults `text_select` to False and, when it is False,
        # injects `body { user-select: none; cursor: default }` into the
        # document at runtime. The founder could not select or copy a word
        # Somesh had said -- proven in the packaged application with a real
        # mouse drag and a real Ctrl+C, not from reading CSS.
        #
        # Our own stylesheet already granted `user-select: text` on the
        # conversation and out-specifies that injected rule, which is
        # exactly why the CSS looked correct while the behaviour was not.
        # This is the switch that actually governs it.
        text_select=True,
    )

    voice = _build_voice(
        window, whisper_model=whisper_model, piper_model_path=voice_model_path,
        mic_permission_checker=mic_permission_checker,
        input_device_resolver=input_device_resolver,
        output_device_resolver=output_device_resolver,
        microphone_enabled=microphone_enabled,
    )
    api = DesktopShellApi(
        app, voice=voice, open_settings=open_settings,
        submit_objective=submit_objective,
        default_mode=default_mode,
        get_execution_status=get_execution_status,
        confirm_completion=confirm_completion,
        decide_approval=decide_approval,
        set_mode=set_mode,
        record_interaction=record_interaction,
    )
    window.expose(api.get_founder_seed, api.greet, api.send_message,
                  api.get_dashboard, api.toggle_mute,
                  api.open_microphone_settings,
                  api.interrupt_speech, api.abandon_voice_capture, api.get_startup_diagnostics,
                  api.debug_log, api.get_execution_status, api.confirm_completion,
                  api.decide_approval, api.set_mode, api.get_mode)

    # `voice` is None when the composition root disables the microphone
    # for this session. `DesktopShellApi` already guards every use site
    # -- it was written to run without a pipeline -- but these two
    # lifecycle bindings were not, and `+= voice.stop` raised at
    # composition time before any window was shown.
    #
    # The environment variable that drives this is deliberately NOT named
    # here: an architecture test asserts this package never reads the
    # environment, and it matches on source text, so even naming the
    # variable in a comment trips it. The flag arrives as an argument.
    #
    # This is the failure the flag existed to prevent being papered over:
    # while the flag was silently dropped, a real pipeline was always
    # built and this path never ran, so nothing here was ever exercised.
    if voice is not None:
        def _on_shown():
            try:
                voice.start()
            except Exception as e:
                logging.error(f"Failed to start voice pipeline: {e}")

        window.events.shown += _on_shown
        window.events.closing += voice.stop
    else:
        logging.info("voice pipeline not built: microphone disabled for this session")

    # Use FixedBottleServer to avoid pywebview 6.x asset() signature bug
    webview.start(debug=debug, server=FixedBottleServer)
    return app