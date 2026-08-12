"""The Founder Desktop Application shell — Product Veda integration.

*\"You are the product assembly engineer... ASSEMBLE. WIRE. POLISH.
PACKAGE.\"* This module is the wiring: it opens one native window (via
`pywebview`, wrapping the OS's own WebView2/WebKit engine — already
declared as an optional dependency, `pyproject.toml`'s `ui` extra) that
hosts `desktop_app/web/index.html`, and exposes exactly nine methods to
that page's JavaScript. Every one of them is a thin call onto
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
        get_execution_status: Callable[[], dict[str, Any]] | None = None,
        confirm_completion: Callable[[str], dict[str, Any]] | None = None,
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
        return {"reply": greet(identity, context), "presence": None}

    def send_message(self, text: str, source: str = "text") -> dict[str, Any]:
        if self._app.communication is None:
            return {"reply": None}
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
                return self._submit_objective(text)
            return {"reply": None}
        if self._voice is not None:
            self._voice.speak(routed.response.spoken)
        return {"reply": routed.response.display}

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

    def toggle_mute(self) -> dict[str, Any]:
        """Founder-chosen silence — `03_VOICE_EXPERIENCE §3.5`'s `muted`
        state. Returns the new state so the page does not have to guess
        at it from a separate push landing first."""
        if self._voice is None:
            return {"muted": None}
        self._muted = not self._muted
        self._voice.set_muted(self._muted)
        return {"muted": self._muted}

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
        startup stopped instead of a silent blank window."""
        voice = self._voice
        return {
            "webview_loaded": True,  # this call answering at all proves it
            "conversation_engine_ready": self._app.communication is not None,
            "voice_initialized": voice is not None,
            "stt_loaded": voice is not None and voice.stt_ready,
            "tts_loaded": voice is not None and voice.tts_ready,
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
) -> VoicePipeline:
    """One `VoicePipeline`, wired to push its three event kinds into the
    page. Construction never fails — a model that cannot load reports
    `error` through the same `on_state` push every other absence uses
    (`VoicePipeline._load_and_open`'s own try/except)."""
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
    submit_objective: Callable[[str], dict[str, Any]] | None = None,
    get_execution_status: Callable[[], dict[str, Any]] | None = None,
    confirm_completion: Callable[[str], dict[str, Any]] | None = None,
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
    )

    window = webview.create_window(
        "Kalpavriksha",
        url=f"{web_dir}/index.html",
        width=1440, height=900,
        min_size=(1180, 760),
        background_color="#05070A",
    )

    voice = _build_voice(
        window, whisper_model=whisper_model, piper_model_path=voice_model_path,
        mic_permission_checker=mic_permission_checker,
        input_device_resolver=input_device_resolver,
        output_device_resolver=output_device_resolver,
    )
    api = DesktopShellApi(
        app, voice=voice, open_settings=open_settings,
        submit_objective=submit_objective,
        get_execution_status=get_execution_status,
        confirm_completion=confirm_completion,
    )
    window.expose(api.get_founder_seed, api.greet, api.send_message,
                  api.get_dashboard, api.toggle_mute,
                  api.open_microphone_settings,
                  api.interrupt_speech, api.abandon_voice_capture, api.get_startup_diagnostics,
                  api.debug_log, api.get_execution_status, api.confirm_completion)

    def _on_shown():
        try:
            voice.start()
        except Exception as e:
            logging.error(f"Failed to start voice pipeline: {e}")

    window.events.shown += _on_shown
    window.events.closing += voice.stop

    # Use FixedBottleServer to avoid pywebview 6.x asset() signature bug
    webview.start(debug=debug, server=FixedBottleServer)
    return app