"""Kalpavriksha — the Founder Desktop Application entry point.

This is the file `packaging/kalpavriksha.spec` builds into the shipped
executable. A founder never runs this directly — they double-click the
installed app, which double-clicks this. It opens one native window
(via `master_agent.founder_edition.desktop_shell`) and nothing else: no
terminal, no console window, no developer tooling.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re as _re
import random
import socket
import sys
import threading
import uuid
from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIServer, WSGIRequestHandler, make_server

import bottle
from bottle import Bottle, static_file


# ── The vendored pywebview server ────────────────────────────────────────
#
# Moved here from `founder_edition/desktop_shell.py`. It has to open a
# socket and read filesystem paths to serve the page, and that package is
# architecture-guarded against both -- `tests/test_founder_edition_boot.py
# ::TestNothingExecutesOrCallsAI` names `socket` as one of the three
# things the guard exists to keep out, and it was failing on exactly this
# code. The composition root is the layer allowed to own the environment,
# which is the same rule already applied to `record_interaction`, to the
# mode vocabulary, and to machine scanning.
#
# Not rewritten, only relocated: same classes, same behaviour, injected
# into `create_window(server=...)` instead of imported by it.

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



def _bundled_dir(*parts: str) -> str:
    """Where a bundled data directory lives, in both a source checkout
    and a PyInstaller-frozen build. PyInstaller unpacks bundled data next
    to `sys._MEIPASS`; a source run resolves it relative to this file."""
    base = getattr(sys, "_MEIPASS", None)
    if base is not None:
        return os.path.join(base, *parts)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "desktop_app", *parts)


def _voice_model_path() -> str | None:
    path = os.path.join(_bundled_dir("voice_models"), "en_US-lessac-medium.onnx")
    return path if os.path.isfile(path) else None


def _whisper_model_path() -> str:
    """The bundled faster-whisper model directory, if present, else the
    bare model-size string — which makes faster-whisper fall back to
    downloading it from Hugging Face on first run. The bundled directory
    is always present in a shipped build (see `packaging/kalpavriksha.spec`);
    the fallback only matters for a source checkout that hasn't run the
    download step yet.

    Returns a raw string path (r'...') that faster_whisper accepts with
    local_files_only=True, or the model size string as fallback.
    """
    path = os.path.join(_bundled_dir("voice_models"), "whisper-base.en")
    if os.path.isdir(path):
        # Return as raw string path for faster_whisper compatibility
        return os.path.normpath(path)
    return "base.en"


def _windows_microphone_allowed() -> bool:
    """Windows' own microphone privacy consent, read from the registry
    consent store `CapabilityAccessManager` keeps for every capability.
    Two toggles gate an unpackaged desktop app like this one: the master
    *"Microphone access"* switch, and the *"Let desktop apps access your
    microphone"* switch under its `NonPackaged` subkey. An unpackaged
    win32 exe never gets a per-app entry of its own there — Windows only
    logs usage timestamps under it (`LastUsedTimeStart`/`Stop`), not a
    decision — so both blanket toggles are what actually gate this
    process. Denied only if either explicitly reads `"Deny"`; a missing
    key (older Windows, or a key Windows has not created yet) is treated
    as allowed — this checker's job is to catch a real block, not to
    invent one from an absence it cannot interpret.

    This function — not `master_agent.founder_edition.voice_pipeline`,
    which is guarded against importing `os`/`winreg` directly — is where
    it lives; it is injected into `create_window()` as
    `mic_permission_checker`."""
    import winreg

    base = r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone"
    for subpath in (base, base + r"\NonPackaged"):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, subpath) as key:
                value, _ = winreg.QueryValueEx(key, "Value")
        except OSError:
            continue  # key absent — cannot determine, does not mean denied
        if value == "Deny":
            return False
    return True


def _open_microphone_settings() -> None:
    """`ms-settings:privacy-microphone` is the Windows Settings deep-link
    for the toggles `_windows_microphone_allowed` reads; `os.startfile`
    is the standard way an unpackaged Windows exe invokes a URI-scheme
    handler. Injected into `create_window()` as `open_settings` for the
    same reason as the permission checker above."""
    os.startfile("ms-settings:privacy-microphone")  # noqa: S606


def _default_input_device_name() -> str | None:
    """C34.4 — the OS's actual, live current default microphone, read
    directly through WASAPI (`IMMDeviceEnumerator.GetDefaultAudioEndpoint`,
    via `pycaw`), not through `sounddevice`/PortAudio's own device-list
    query. `Engineering/HEALTH_C34_3.md` §3 found — with a real Bluetooth
    headset, a real OS-level device switch, and a controlled same-process-
    vs-fresh-process comparison — that PortAudio caches its device table
    at library initialization and never refreshes it for the life of the
    process: `sounddevice.query_devices()` keeps reporting whichever
    device was default when the app launched, even minutes after the
    founder has switched to a different one in Windows. This function is
    the fix for detection specifically (injected into `VoicePipeline` as
    `input_device_resolver`) — `voice_pipeline.py` itself is unchanged
    architecturally; it just gets told the truth instead of asking
    PortAudio, which cannot tell it.

    Returns `None` on any failure (no default device, COM error, `pycaw`
    unavailable) so the caller can fall back to the pre-C34.4 behavior
    rather than block."""
    try:
        from pycaw.pycaw import AudioUtilities
        return AudioUtilities.CreateDevice(AudioUtilities.GetMicrophone()).FriendlyName
    except Exception:  # noqa: BLE001 — an unreadable live device source must not block a working mic
        return None


def _default_output_device_name() -> str | None:
    """Same as `_default_input_device_name`, for the OS's current default
    speaker/headphones — the counterpart that makes TTS playback follow
    Windows' actual default output instead of whatever PortAudio cached
    at startup."""
    try:
        from pycaw.pycaw import AudioUtilities
        return AudioUtilities.GetSpeakers().FriendlyName
    except Exception:  # noqa: BLE001 — same reasoning as above
        return None


def _app_state_dir():
    """Where this application keeps its durable state.

    The same convention `desktop/intelligence/screenshot.py` already uses
    for its evidence directory -- `%LOCALAPPDATA%/Kalpavriksha/<subdir>`
    -- so a packaged run and a source run resolve the SAME logical store,
    and nothing is ever written into the repository, `build/` or `dist/`.
    """
    import os as _os
    from pathlib import Path as _Path

    # An automated validation session must not write into the founder's
    # own history. A packaged FMEA run shared this directory with the live
    # session, so test interactions, missions and broker decisions landed
    # in the same stores as real ones.
    #
    # `KALPAVRIKSHA_STATE_DIR` names a disposable root for that case. It is
    # an override, not a second architecture: unset -- which is every
    # founder run -- resolves exactly as before.
    override = _os.environ.get("KALPAVRIKSHA_STATE_DIR")
    if override:
        state = _Path(override)
        state.mkdir(parents=True, exist_ok=True)
        return state

    root = _Path(_os.environ.get("LOCALAPPDATA") or _Path.home()) / "Kalpavriksha"
    state = root / "state"
    state.mkdir(parents=True, exist_ok=True)
    return state


#: Founder Edition's one browser identity. The *id* is generic on purpose
#: -- nothing branches on it, and a second deployment naming its identity
#: something else changes this line and nothing more. The founder's actual
#: name is the label beside it, which is deployment configuration and is
#: never architectural: it appears in a question put to the founder and
#: nowhere else.
FOUNDER_BROWSER_IDENTITY = "founder"
FOUNDER_BROWSER_IDENTITIES = {FOUNDER_BROWSER_IDENTITY: "Onkar"}

#: The one founder-interaction port for this application.
#:
#: A composition-root singleton because of an ordering fact: the reasoning
#: stack is assembled before a window exists, so the provider must be
#: handed the port it will ask through long before anything can answer.
#: The shell attaches a real implementation once it has a surface; until
#: it does, an unanswerable question cancels rather than being guessed at.
_FOUNDER_INTERACTION = None


def founder_interaction():
    """The application's `FounderInteraction`, created on first use."""
    global _FOUNDER_INTERACTION
    if _FOUNDER_INTERACTION is None:
        from master_agent.founder_interaction import (
            DeferredFounderInteraction,
        )

        _FOUNDER_INTERACTION = DeferredFounderInteraction()
    return _FOUNDER_INTERACTION


def _browser_identity_store():
    """Where this application keeps its browser identities.

    A sibling of `state/` under the same `%LOCALAPPDATA%/Kalpavriksha`
    root `_app_state_dir()` already owns, and deliberately *not* inside
    it: `state/` is what PersistenceService snapshots and what a recovery
    may legitimately discard, and browser authentication material must
    survive neither of those decisions being applied to it. It is not in
    the repository, not in a fixture, not in the provider registry
    snapshot and not in mission history.

    It is emphatically not the founder's own Chrome profile
    (`%LOCALAPPDATA%/Google/Chrome/User Data`). This directory starts
    empty and holds only what a sign-in performed inside Kalpavriksha's
    own window put there.
    """
    import os as _os
    from pathlib import Path as _Path

    from master_agent.environment.browser_identity import (
        IDENTITIES_DIRNAME,
        BrowserIdentityStore,
    )

    override = _os.environ.get("KALPAVRIKSHA_STATE_DIR")
    # A disposable validation run gets disposable identities too, for the
    # same reason it gets a disposable state directory: an automated
    # session must not sign in as, or sign out, the founder.
    root = (
        _Path(override).parent
        if override
        else _Path(_os.environ.get("LOCALAPPDATA") or _Path.home()) / "Kalpavriksha"
    )
    return BrowserIdentityStore(
        root / IDENTITIES_DIRNAME, known=dict(FOUNDER_BROWSER_IDENTITIES)
    )



def _current_system_facts(capability_index, runner, history) -> dict:
    """What is true about this installation, right now.

    Assembled from the registries that already own these answers. The
    Brain may not read the environment and does not: it is handed facts
    that Shared Infrastructure already holds, which is why no mission is
    needed to answer "what can you do?".

    ## The distinction that matters

    KNOWN is not EXECUTABLE. A provider can be registered, configured and
    completely unusable -- no binary installed, no credential, an
    application that is not running. Telling a founder they can use it
    would be a promise this machine cannot keep, so every provider is
    reported with all four facts rather than as a name on a list.

    Every failure here is swallowed to an omission rather than an
    exception: a founder asking a question must not be shown a crash
    because one registry was mid-write. What cannot be read is left out,
    and the answer says what it does not know.
    """
    facts: dict[str, str] = {}

    try:
        by_domain: dict[str, list[str]] = {}
        for entry in capability_index.entries:
            by_domain.setdefault(entry.domain, []).append(entry.canonical_id)
        facts["What this system can do right now"] = "\n".join(
            f"  {domain}: {', '.join(sorted(names))}"
            for domain, names in sorted(by_domain.items())
        )
    except Exception:  # noqa: BLE001 -- an unreadable registry is an omission
        logging.exception("could not read the capability index for grounding")

    try:
        # The SAME four facts the packaged self-check prints, read from
        # the same places. One derivation, so what a founder is told and
        # what an operator sees cannot disagree.
        executor = runner._executor
        executable_ids = {p.provider_id for p in executor._providers.all_plugins()}
        configured_ids = set(_configured_cloud_providers())
        source = executor._service.providers
        profiles = {p.provider_id: p for p in source.profiles()}
        registry = source.registry

        rows = []
        for record in sorted(registry.all() if registry else (),
                             key=lambda d: d.provider_id):
            pid = record.provider_id
            profile = profiles.get(pid)
            rows.append(
                f"  {pid}: known=yes"
                f" configured={'yes' if pid in configured_ids else 'n/a'}"
                f" executable={'yes' if pid in executable_ids else 'no'}"
                f" available={'yes' if profile and profile.available else 'no'}"
            )
        if rows:
            facts["Reasoning providers (known is not the same as usable)"] = (
                chr(10).join(rows)
            )
    except Exception:  # noqa: BLE001
        logging.exception("could not read the provider registry for grounding")

    try:
        record = history.latest() if hasattr(history, "latest") else None
        if record is not None:
            facts["The most recent mission"] = _mission_facts(record)
    except Exception:  # noqa: BLE001
        logging.exception("could not read plan history for grounding")

    return facts


def _mission_facts(record) -> str:
    """The last mission, as recorded -- including whether it satisfied
    what was asked, which is the question a founder actually means."""
    from master_agent.brain.conformance import assess

    lines = [f"  objective: {getattr(record, 'objective', '')}"]
    requirements = tuple(getattr(record, "requirements", ()) or ())
    for requirement in requirements:
        lines.append(
            f"    required: {requirement.get('description', '')}"
            f" [{requirement.get('kind', '')}]"
        )
    for step in getattr(record, "steps", ()) or ():
        covers = ", ".join(getattr(step, "covers", ()) or ()) or "-"
        lines.append(
            f"    step {getattr(step, 'capability', '?')}"
            f" verdict={getattr(step, 'verdict', '') or 'none'} covers={covers}"
        )
        reason = getattr(step, "selection_reason", "")
        if reason:
            lines.append(f"      chosen because: {reason}")
    if requirements:
        # The Brain's own conformance state, computed from what was
        # recorded. Never a Verification verdict -- see ADR-0026.
        # Stored rows read directly -- `assess` takes either shape.
        conformance = assess(requirements, getattr(record, "steps", ()) or ())
        lines.append(f"    did it satisfy the request: {conformance.state}")
        lines.append(f"      because: {conformance.reason}")
    return "\n".join(lines)



def _answers_a_question(record) -> bool:
    """Was this mission itself a founder QUESTION rather than work?

    A question that reasoning had to answer becomes a mission like any
    other, and then becomes "the last mission". Asked *"did the last
    mission satisfy what I asked for?"*, a founder means the last thing
    they asked FOR -- not the last thing they asked ABOUT.
    """
    from master_agent.brain.intent import QUESTION_REQUIREMENT

    requirements = list(getattr(record, "requirements", ()) or ())
    if requirements:
        return all(
            str(r.get("description", "")).startswith(QUESTION_REQUIREMENT)
            for r in requirements
        )

    # No semantic trace -- a record written before requirements existed,
    # and this founder's history holds a hundred of them. Fall back to
    # what the SHAPE says: a mission that is one `Reasoning.Transform`
    # and nothing else changed nothing in the world. It produced text,
    # which is what answering a question looks like. Real generate-then-
    # write work has a second step that hands the text over.
    steps = list(getattr(record, "steps", ()) or ())
    return len(steps) == 1 and str(
        getattr(steps[0], "capability", "")
    ).endswith("Reasoning.Transform")


def _latest_commissioned(history, usable):
    """The most recent mission the founder asked FOR that can answer this.

    Two filters, and both are needed against a real history. A mission
    that was itself a QUESTION is not what "the last mission" means. And
    a record from before the semantic trace existed carries no
    requirements and no recorded rationale, so it cannot answer either --
    this founder's history holds a hundred of them, and picking one would
    produce silence dressed as an answer.

    `None` when nothing qualifies, and the caller says so plainly rather
    than reaching for a provider to fill the gap.
    """
    try:
        records = list(history.all())
    except Exception:  # noqa: BLE001 -- an unreadable history is an omission
        logging.exception("could not read plan history")
        return None
    for record in reversed(records):
        if not _answers_a_question(record) and usable(record):
            return record
    return None


def _grounded_answer(mission_service, question: str, objective_id) -> str:
    """A question about this system, answered from this system's records.

    Returns `""` when the records do not answer it, and the caller falls
    through to the ordinary path.

    ## Why this comes first

    Asked *"What can you do right now?"*, the surface previously built a
    `Reasoning.Transform` mission with the last mission's contents
    attached as grounding. That action defaults to `sensitive=True` --
    correctly, because its context is normally private founder material
    -- so the Broker looked for a PRIVATE-locality provider, found none
    running, and the question failed outright.

    Every layer was right. The mistake was upstream of all of them: none
    of these questions needed a provider. What this machine can do, which
    providers are usable, why a capability was chosen, whether the last
    mission satisfied the request -- all four are already recorded, and
    reading a record is not reasoning.

    Answering here removes three failure modes at once: the sensitivity
    block, the latency, and the chance of a model inventing a reason that
    sounds right.
    """
    from master_agent.brain import self_query

    # Everything comes from the one service the surface already holds.
    # `_submit_objective` is not handed the pipeline's locals, and
    # threading three more parameters through it to reach facts the
    # service already owns would be plumbing for its own sake.
    history = getattr(mission_service, "history", None)
    planner = getattr(mission_service, "planner", None)
    capability_index = getattr(planner, "_catalogue", None)
    runner = getattr(planner, "_runner", None)
    if history is None or capability_index is None:
        return ""

    try:
        subject = mission_service.intent_layer.question_subject(question)
    except Exception:  # noqa: BLE001 -- classification is a shortcut, not a gate
        logging.exception("could not classify the founder's question")
        return ""
    if subject == self_query.OTHER:
        return ""

    record = None
    conformance = None
    if subject in (self_query.PLAN_RATIONALE, self_query.OUTCOME):
        # What this subject needs the record to actually carry.
        usable = (
            (lambda r: bool(getattr(r, "requirements", ()) or ()))
            if subject == self_query.OUTCOME
            else (lambda r: any(
                getattr(s, "selection_reason", "") for s in getattr(r, "steps", ()) or ()
            ))
        )
        try:
            record = history.get(objective_id) if objective_id else None
            if record is None or _answers_a_question(record) or not usable(record):
                record = _latest_commissioned(history, usable)
        except Exception:  # noqa: BLE001
            logging.exception("could not read plan history for a founder question")
            return ""
        if record is None:
            # Nothing recorded can answer this. The ordinary path takes
            # it from here rather than this inventing correspondence.
            return ""
        if subject == self_query.OUTCOME:
            from master_agent.brain.conformance import assess

            conformance = assess(
                tuple(getattr(record, "requirements", ()) or ()),
                getattr(record, "steps", ()) or (),
            )

    capabilities = providers = ()
    if subject == self_query.CAPABILITIES:
        capabilities = getattr(capability_index, "entries", ()) or ()
    if subject == self_query.PROVIDERS:
        try:
            providers = runner._executor._service.providers.profiles()
        except Exception:  # noqa: BLE001
            logging.exception("could not read provider profiles for a founder question")
            return ""

    return self_query.answer(
        subject, capabilities=capabilities, providers=providers,
        record=record, conformance=conformance,
    )


def _build_mission_pipeline():
    """The minimal Planner -> Broker -> Gemini -> MissionPlan -> Mission
    Control -> Browser Executive assembly Founder Edition needs for one
    capability: turning a founder's objective into a real, verified
    browser mission.

    Not a reuse of `master_agent.launcher.boot.build_system()` — that
    assembly also wires Dashboard, Persistence, Recovery and Filesystem,
    none of which this surface needs, and `master_agent.launcher` stays
    out of the Founder Edition build on purpose (`packaging/kalpavriksha.spec`).
    Every class used here is the same one `build_system()` itself uses;
    this is a smaller composition of the same existing parts, not a
    second architecture.

    This function — not `master_agent.founder_edition` — is where it
    lives: that package is architecture-guarded against importing any of
    these modules directly
    (`tests/test_founder_edition_boot.py::TestNothingExecutesOrCallsAI`).
    `desktop_shell.py` only ever receives the one callable this produces.

    Constructed whenever at least one reasoning route exists, which — now
    that the web rung is wired — is always.

    This used to read `if not api_key: return None`, so an absent Gemini
    API key meant no mission pipeline at all: no Planner, no Executives,
    conversation only. That was true when Gemini was the only rung. It is
    not true now. **No Gemini API key is not the same fact as no reasoning
    capability**, and the desktop AI applications and the browser rung
    need no key of ours at all.

    Credential handling itself is unchanged: `GeminiProvider` already
    reports a missing key as an ordinary provider failure
    (`NO_API_KEY`, and without making a network call), so the ladder
    simply skips that rung and walks on. Only the composition's
    assumption is repaired here.
    """
    api_key = os.environ.get("GEMINI_API_KEY", "")

    # Playwright's own PyInstaller/Nuitka detection
    # (`playwright/_impl/_transport.py::PipeTransport.connect`) defaults
    # PLAYWRIGHT_BROWSERS_PATH to "0" the moment `sys.frozen` is true,
    # putting the driver's browser search inside its own bundled
    # `driver/package/.local-browsers` instead of the machine-wide cache —
    # on the assumption a frozen build ships its own browsers. This one
    # deliberately does not (`packaging/kalpavriksha.spec`'s own comment):
    # Browser Executive is meant to use whatever Chromium a founder already
    # has cached at `%LOCALAPPDATA%\ms-playwright`, the same cache every
    # other Playwright process on the machine shares. `setdefault` only
    # fires when the key is absent, so pre-populating it here with the same
    # path Playwright itself would compute on a non-frozen run makes that
    # override a no-op instead of redirecting the search.
    os.environ.setdefault(
        "PLAYWRIGHT_BROWSERS_PATH",
        os.path.join(
            os.environ.get("LOCALAPPDATA")
            or os.path.join(os.path.expanduser("~"), "AppData", "Local"),
            "ms-playwright",
        ),
    )

    from master_agent.permissions.permission_system import GrantScope, PermissionSystem
    from master_agent.executor.executor import LocalExecutor
    from master_agent.plugins.registry import PluginRegistry
    from master_agent.plugins.browser_plugin import BrowserPlugin
    from master_agent.plugins.filesystem_plugin import FilesystemPlugin
    from master_agent.desktop.plugin import DesktopPlugin
    from master_agent.environment.browser_session import BrowserSessionManager
    from master_agent.mission_control.mission_control import MissionControl
    from master_agent.mission_control.adapters import discover_executives
    from master_agent.runtime.engine import RuntimeEngine
    from master_agent.plugins.reasoning_gateway import ReasoningGateway
    from master_agent.runtime.gateway import PluginGateway
    from master_agent.runtime.approval import PermissionSystemGate
    from master_agent.ai_infrastructure.catalog import CLOUD, DESKTOP, PROVIDER_CATALOG
    from master_agent.ai_infrastructure.profiles import (
        ProviderSource, bootstrap_registry, descriptor_for,
    )
    from master_agent.broker.registry import ProviderRegistry
    from master_agent.providers.openrouter import (
        CREDENTIAL_ENV as _OPENROUTER_ENV,
        OpenRouterProvider,
    )
    from master_agent.providers.openrouter import (
        OPENROUTER_PROVIDER_ID as _OPENROUTER_ID,
    )
    import os as _os
    from master_agent.ai_infrastructure.service import AiCapabilityService
    from master_agent.ai_infrastructure.execution import PromptExecutor
    from master_agent.ai_infrastructure.ledger import DecisionLedger
    from master_agent.ai_infrastructure.tiered_runner import TieredPromptRunner
    from master_agent.broker.broker import CapabilityBroker
    from master_agent.broker.policy import get_policy
    from master_agent.providers.gemini import GeminiProvider
    from master_agent.providers.desktop_app import build_desktop_providers
    from master_agent.providers.browser_free_ai import (
        BROWSER_FREE_AI_SPEC,
        FOUNDER_EDITION_SITES,
        BrowserFreeAiReasoningProvider,
        PROVIDER_ID as BROWSER_FREE_AI_ID,
    )
    from master_agent.brain import IntentLayer, Reporter
    from master_agent.planner.planner import Planner
    from master_agent.missions.service import MissionService
    from master_agent.capabilities.extraction import contracts_from_actions
    from master_agent.capabilities.index import build_index
    from master_agent.mission_control.capabilities import qualified_name
    from master_agent.plugins.document_plugin import DocumentPlugin
    from master_agent.plugins.reasoning_plugin import ReasoningPlugin
    from pathlib import Path as _Path

    permissions = PermissionSystem()
    executor = LocalExecutor(permissions)
    registry = PluginRegistry()
    # Founder-visible defaults. Everywhere else in this codebase a browser
    # session is a headless mechanism for getting an answer; here a founder
    # is sitting in front of the machine, and "open Chrome" means the
    # Chrome they can see. `channel="chrome"` is Playwright's own
    # first-class way to drive the *installed* Google Chrome rather than
    # the bundled build (`environment/browser_session.py::_launch`), so
    # this is still exactly one session — one that Playwright continues to
    # observe and verify through the same Browser Worker as before.
    #
    # Defaults, not overrides: an explicit `headless`/`channel` in a plan
    # still wins, so the Planner can ask for an invisible session when an
    # objective genuinely does not want a window.
    browser_identities = _browser_identity_store()
    global _BROWSER_SESSIONS
    _BROWSER_SESSIONS = BrowserSessionManager(
            default_headless=False,
            default_channel="chrome",
            # Declared, not defaulted: a session stays anonymous unless an
            # Action names an identity, so registering the store here adds
            # the *ability* to be the founder without making anything
            # silently become them.
            identities=browser_identities,
    )
    browser_plugin = BrowserPlugin(executor, _BROWSER_SESSIONS)
    registry.register(browser_plugin)

    # Desktop Executive Foundation 1.0: the Desktop Executive
    # (`desktop/plugin.py`) has existed as real, working code since MB030,
    # but was never registered here — every capability it exposes
    # (`launch_application`, `type_text`, `read_text`, ...) was reachable
    # only by importing `DesktopPlugin` directly in a script, never by a
    # founder's objective going through the Planner. This is that
    # registration, mirroring `BrowserPlugin`'s own composition exactly —
    # same registry, same discovery, same permission/gateway wiring — so
    # the Desktop Executive becomes a second real Executive, not a second
    # architecture.
    desktop_plugin = DesktopPlugin(executor)
    registry.register(desktop_plugin)

    # Filesystem Executive. `CreateFolderAction` and its siblings have
    # existed for a long time, but Founder Edition never registered the
    # plugin that exposes them -- so the Planner could not see a typed
    # `create_folder` capability at all and satisfied "create a folder"
    # with `desktop.execute_command`, a raw shell string. That fallback
    # is wrong twice over: it skips the action's own parameter contract
    # (`required_parameters = ["name"]`, which is what makes a missing
    # name a CLARIFICATION rather than a guess), and it reclassifies a
    # REVERSIBLE_WRITE operation as IRREVERSIBLE, which forced a founder
    # approval the real policy never asked for.
    # Named roots. The three defaults plus the founder's D: drive, which
    # is where their own documents actually live -- without a name for it
    # no capability can reach them, and a mission about a file on D: could
    # only fail. Deliberately recorded as a real widening: EVERY filesystem
    # capability resolves against this table, deletion included, so this
    # line grants read AND write reach across that drive.
    from master_agent.executor.action import default_locations as _default_locations

    _locations = dict(_default_locations())
    _d_drive = _Path("D:/")
    if _d_drive.exists():
        _locations["d_drive"] = _d_drive

    filesystem_plugin = FilesystemPlugin(executor, _locations)
    registry.register(filesystem_plugin)

    # The Document Executive: formats, where Filesystem handles bytes.
    # `Filesystem.ReadFile` is honest that it reads text files only, which
    # made every PDF and Word document on the machine unreachable.
    document_plugin = DocumentPlugin(executor, _locations)
    registry.register(document_plugin)

    # The Reasoning Executive. Registered here with the others so it is a
    # real Executive in the catalogue; its runner is bound further down,
    # once the ladder it delegates to exists. Until this, judgement was
    # something the Planner could do *about* a mission and nothing could
    # do *inside* one.
    reasoning_plugin = ReasoningPlugin(executor)
    registry.register(reasoning_plugin)

    mission_control = MissionControl()
    discover_executives(mission_control, registry)

    # Rule 5 stays exactly as strict: this pre-grants only each Executive's
    # own reversible actions (REVERSIBLE_WRITE, never IRREVERSIBLE — an
    # ALWAYS_FOR_CAPABILITY grant cannot satisfy that tier regardless of
    # what's granted here, per PermissionSystem.check()). Not a new
    # approval UI (Section 13 forbids building one) — the same "the
    # calling context already authorised this" relay `DesktopPlugin
    # .invoke()` already performs per-call, done once here for every
    # Executive this composition root wires, because reversible automation
    # is what Gate 2 already proved safe and founder-approved. A capability
    # at IRREVERSIBLE tier (e.g. Desktop's `close_window`) is untouched by
    # this loop and still requires a real decision.
    # `document_plugin` and `reasoning_plugin` belong here for exactly
    # the same reason as the other three, and were missing: their
    # reversible actions would have stopped for a founder decision
    # that Rule 5 already settles, while `Filesystem.WriteFile` --
    # the identical tier -- ran straight through.
    for plugin in (browser_plugin, desktop_plugin, filesystem_plugin,
                   document_plugin, reasoning_plugin):
        for descriptor in mission_control.capabilities.for_executive(plugin.manifest.name):
            permissions.grant(
                plugin.manifest.name, descriptor.capability,
                GrantScope.ALWAYS_FOR_CAPABILITY,
            )

    runtime = RuntimeEngine(
        mission_control,
        # `approvals=mission_control` is what turns "no standing grant"
        # into a question for the founder instead of a failed task. See
        # PermissionSystemGate._ask_founder.
        approval_gate=PermissionSystemGate(permissions, registry, approvals=mission_control),
    )
    # Gateways. `PluginGateway.verify()` returns None unconditionally --
    # "the Plugin contract has no verification surface" -- so registering
    # it for Browser and Filesystem meant no step in the packaged app
    # could ever produce Evidence. A live six-step mission verified
    # nothing, completed on execution success alone, and Onkar was told
    # "Done" for a folder that was empty.
    #
    # `launcher/boot.py` had already wired the verifying FilesystemGateway;
    # this composition root had simply never been given the same treatment,
    # and no production BrowserGateway existed outside test support at all.
    #
    # The composition root is allowed to know which concrete gateway
    # belongs to which concrete Executive. The Runtime is not, which is why
    # these imports are here and not in `runtime/`.
    from master_agent.environment.browser_session import (  # noqa: PLC0415
        BrowserSessionManager as _Sessions,
    )
    from master_agent.plugins.browser_gateway import BrowserGateway  # noqa: PLC0415
    from master_agent.plugins.browser_worker import BrowserWorker  # noqa: PLC0415
    from master_agent.plugins.filesystem_gateway import FilesystemGateway  # noqa: PLC0415
    from master_agent.plugins.filesystem_worker import FilesystemWorker  # noqa: PLC0415

    # The SAME session manager the plugin drives. A second one would open a
    # second browser, and verification would then observe a window nobody
    # navigated.
    browser_sessions = getattr(browser_plugin, "_sessions", None)
    if browser_sessions is None:
        browser_sessions = _Sessions(default_headless=False, default_channel="chrome")

    # The SAME location map the actions resolve against, so verification
    # looks where execution wrote.
    _fs_locations = None
    for _action in (getattr(filesystem_plugin, "_actions", {}) or {}).values():
        if hasattr(_action, "_locations"):
            _fs_locations = _action._locations
            break

    runtime.register_gateway(
        browser_plugin.manifest.name,
        BrowserGateway(
            BrowserWorker(executor, browser_sessions),
            permissions,
            executor.name,
        ),
    )
    # Desktop: `DesktopGateway` subclasses `PluginGateway` and overrides
    # only `verify()`, so `invoke()` is inherited verbatim and the Desktop
    # execution path -- DesktopPlugin -> registered Action ->
    # DesktopExecutor / DesktopExecutiveV2 -> Process/Window/UIA -- is
    # unchanged. It adds canonical Evidence for the FOUR capabilities with
    # a read-only postcondition -- LaunchApplication, CloseApplication,
    # FocusWindow, BringToFront -- and returns None for the rest, which is
    # what the old gateway did for all of them.
    #
    # This said "five ... (launch/close application, focus, bring-to-front,
    # close window)". `gateway.supports()` disagrees, and it is the
    # authority: CloseWindow is NOT generically verifiable, because a
    # closed window leaves a running process that still owns other windows,
    # and a verdict from process presence would be right by accident for
    # single-window applications and silently wrong otherwise. The comment
    # overclaimed by one; the code never did.
    from master_agent.desktop.gateway import DesktopGateway  # noqa: PLC0415

    runtime.register_gateway(desktop_plugin.manifest.name, DesktopGateway(desktop_plugin))
    runtime.register_gateway(
        filesystem_plugin.manifest.name,
        FilesystemGateway(
            FilesystemWorker(executor, locations=_fs_locations),
            permissions,
            executor.name,
        ),
    )

    # Document and Reasoning had NO gateway at all, and the Runtime does
    # not fall back when one is missing -- `engine.py` fails the task with
    # "no gateway registered for executive '<id>'". So all three of
    # `Document.ExtractText`, `Document.WriteDocument` and
    # `Reasoning.Transform` were registered, Planner-visible and
    # permission-granted, and could not run. Proven by planning each one
    # and watching the task fail, not inferred from the code path.
    #
    # `PluginGateway` is the same generic seam Browser and Filesystem used
    # before they earned verifying gateways of their own, and the one
    # Desktop's non-verifiable capabilities still take. It executes and
    # returns no Evidence, which is the truthful shape for Document: a
    # written document has no generic read-only postcondition this layer
    # could re-observe, and inventing one would be manufacturing Evidence.
    runtime.register_gateway(
        document_plugin.manifest.name, PluginGateway(document_plugin),
    )

    # Reasoning is different, and the difference was measured rather than
    # reasoned about. Registered through the generic gateway it executed
    # correctly and produced real text, and then every binding out of it
    # failed: `input_resolution` resolves a produced value only from
    # canonical Evidence with a matched verdict, and `PluginGateway`
    # returns None by contract. So an objective as ordinary as "think of
    # three names and write them into a file" could not run -- not for
    # want of a capability, but because the Executive that produces text
    # and the Verifier that measures text were never joined.
    #
    # `ReasoningGateway` is that join, in the shape `PluginGateway`'s own
    # docstring prescribes and `FilesystemGateway` already follows. It
    # adds no capability and no second verifier: it hands the text to
    # MB035's `TextVerifier`, which re-derives its observation from the
    # artefact by deterministic measurement and never asks the provider
    # what it thought of its own answer.
    runtime.register_gateway(
        reasoning_plugin.manifest.name, ReasoningGateway(reasoning_plugin),
    )

    # No Ollama: matches every prior Gemini mission this build carries.
    # `enabled_cloud_providers` names Gemini only; no plugin for any
    # other cloud provider is ever registered below.
    #
    # Corrected Fallback Ladder (Gemini API -> installed desktop AI ->
    # Browser free AI): `inventory_provider` now reads
    # `desktop_plugin._context.cached` — the exact "same zero-argument
    # callable the Dashboard is given" shape `ai_infrastructure/
    # profiles.py`'s own docstring already asks for. `.cached` (not
    # `.inventory()`) is deliberate: it never triggers a scan on its own,
    # so building `providers_source` here costs nothing and launches
    # nothing — the deep scan a desktop-tier decision actually needs is
    # triggered lazily, only by `TieredPromptRunner`, only once Gemini
    # has already failed (see `tiered_runner.py`'s own docstring).
    # ---- the canonical provider record ---------------------------------
    #
    # ONE registry, and it is administrative only: it holds descriptors,
    # never live provider objects. The executable ones live in the plugin
    # registry the PromptExecutor uses, below, and the two are named apart
    # here so the code cannot confuse them.
    #
    # Order matters. RESTORE first, then bootstrap: a persisted record
    # whose provenance is DISCOVERED or SELF_REGISTERED outranks a
    # declaration, and `bootstrap_registry()` protects it -- but only if
    # it is already present when the import runs.
    canonical_providers = ProviderRegistry()
    _restore_canonical_providers(canonical_providers, _app_state_dir())
    bootstrap_registry(canonical_providers)
    # `BROWSER_FREE_AI_SPEC` is deliberately absent from the shared global
    # catalogue (see that module's own note) so it exists only for a
    # composition root that actually registers the provider. This is that
    # root, so it is imported into the SAME canonical registry rather than
    # appended to a second list of specs -- which is what kept the
    # catalogue a parallel authority.
    canonical_providers.register(descriptor_for(BROWSER_FREE_AI_SPEC))

    providers_source = ProviderSource(
        inventory_provider=lambda: desktop_plugin._context.cached,
        registry=canonical_providers,
        enabled_cloud_providers=_configured_cloud_providers(),
        # Read at call time, never captured: a provider is executable
        # because an implementation is registered NOW, not because a
        # descriptor survived a restart saying it once was.
        executable_provider_ids=lambda: frozenset(
            p.provider_id for p in provider_registry.all_plugins()
        ),
    )
    # The Broker already records a full DecisionEntry for every reasoning
    # request -- which providers were eligible, their rank, which was
    # chosen, on what policy, and what happened when it ran. That was
    # constructed with `store=None`, so the whole provider-attempt trail
    # evaporated with the process, exactly as the mission audit did before
    # cbf5b2a. `JsonFileDecisionStore` already exists and `launcher/boot
    # .py` already uses it; only this composition was passing null.
    #
    # No routing behaviour changes: the ledger is a sink the Broker writes
    # through, and giving it somewhere to write cannot alter what it
    # decided.
    from master_agent.ai_infrastructure.ledger import LEDGER_FILENAME, JsonFileDecisionStore

    ledger = DecisionLedger(store=JsonFileDecisionStore(_app_state_dir() / LEDGER_FILENAME))
    broker = CapabilityBroker(policy=get_policy("prefer_free"), sink=ledger.record)
    intelligence = AiCapabilityService(
        broker=broker, providers=providers_source, ledger=ledger, approvals=None,
    )
    # The EXECUTABLE registry. Live provider objects, and nothing
    # administrative: `canonical_providers` above is the metadata
    # authority and never holds one of these. Named apart deliberately --
    # the two were easy to confuse and mean opposite things.
    provider_registry = PluginRegistry()
    provider_registry.register(GeminiProvider(api_key=api_key))

    # OpenRouter becomes EXECUTABLE only when this deployment has a
    # credential for it. A descriptor in the canonical registry is not a
    # reason to construct one: known is not configured, and configured is
    # not executable. Constructing it performs no network call and reads
    # no credential, so this costs nothing when it is not used.
    #
    # The model slug is deployment configuration, passed in here. The
    # provider revalidates it against OpenRouter's own current metadata on
    # every call and refuses if it is no longer free or no longer text --
    # this is not a claim that it is free forever.
    if _os.environ.get(_OPENROUTER_ENV):
        _openrouter = OpenRouterProvider(model=OPENROUTER_CONFIGURED_MODEL)
        provider_registry.register(_openrouter)
        # The catalogue declares this provider at 0.005 a call -- "metered
        # aggregator; every call spends money" -- which is true of
        # OpenRouter in general and false of the specific model THIS
        # deployment addresses. Left as declared, the free policy ruled it
        # ineligible, which was the right answer to the wrong question.
        #
        # An earlier version corrected the record the moment a credential
        # was present, stamping `economic_verified_at = now`. That was a
        # provenance defect and worth naming: a credential proves this
        # deployment is CONFIGURED, and proves nothing whatsoever about
        # what the model costs today. The Broker was being handed a
        # zero-cost claim carrying a fresh verification timestamp for an
        # observation that had never been made.
        #
        # So the price is READ before it is claimed. Two separate facts
        # now, deliberately kept apart:
        #
        #   static, deployment configuration -- which model we address
        #   dynamic, observed at time T     -- what it currently costs
        #
        # No reading, an unreachable endpoint, an unlisted model or a
        # priced one all land the same way: economics UNKNOWN, cost left
        # at the declared metered rate, and therefore not eligible under a
        # free policy. Never an optimistic zero.
        _declared = canonical_providers.get(_OPENROUTER_ID)
        if _declared is not None:
            canonical_providers.register(_with_observed_economics(
                _declared,
                _observe_openrouter_economics(_openrouter),
                OPENROUTER_CONFIGURED_MODEL,
            ))
    # NO OLLAMA ON THIS MACHINE. A founder decision, not a technical one:
    # this laptop has 16 GB and the smaller of the two installed models
    # occupies 9 GB resident, which is the founder's working memory rather
    # than spare capacity.
    #
    # `providers/ollama.py` is untouched and still a perfectly good generic
    # provider; it is simply not registered here, so Founder Edition never
    # constructs it, never probes the daemon, never loads a model and never
    # sends it a prompt. `ollama.local` remains in `PROVIDER_CATALOG`, and
    # `all_known_provider_ids` below therefore excludes it from every tier
    # attempt -- so it cannot be selected even by a Broker ranking it
    # highest. `test_founder_edition_no_ollama.py` fails if this comes back.
    # Tier 2 — one provider per `locality == DESKTOP` entry already
    # declared in `PROVIDER_CATALOG` (Claude/ChatGPT/Perplexity/Kimi
    # today; a fifth application is a catalogue entry, never a new
    # branch here). Construction is free of any launch/scan — see
    # `providers/desktop_app.py`'s own module docstring.
    for desktop_provider in build_desktop_providers(desktop_plugin._context):
        provider_registry.register(desktop_provider)
    # NO DUCK.AI IN FOUNDER EDITION -- unchanged, and now enforced by
    # configuration rather than by leaving the whole rung empty.
    #
    # The web rung used to be empty here, which meant an exhausted Gemini
    # API quota could end a founder's request outright once the desktop
    # tier was also unavailable. ADR-0017's ladder already has this rung
    # and this provider already knows how to drive a real visible browser,
    # so the gap was wiring, not capability.
    #
    # `sites=FOUNDER_EDITION_SITES` is the whole of the founder decision:
    # Gemini web only. Enabling the provider without it would have quietly
    # switched Duck.ai back on as the fall-through, which is precisely
    # what the decision forbids. `providers/browser_free_ai.py` stays
    # generic -- its default list is unchanged and another deployment may
    # still use it -- and there is no second provider class.
    #
    # `identity_id` is the second half of the founder decision, and the
    # repair to the defect that opened this mission: Chrome being installed
    # and visible was never the same thing as the founder being signed in.
    # The provider used to open an ordinary isolated context -- no cookies,
    # no storage -- so Gemini showed "Sign in" to a founder whose own
    # Chrome was signed in, and the provider read that wall as terminal.
    # Naming an identity gives the session a persistent profile of its
    # own, so a sign-in done once survives every later restart.
    #
    # The session manager is shared with the Browser Executive rather than
    # constructed privately: two managers would mean two Chromes, and
    # verification would then observe a window nobody typed into.
    # Founder Edition's trusted web-AI lane. Registered as its OWN
    # provider, never as a fallback hidden inside the Playwright one:
    # Google refuses to sign in inside an automation-controlled browser,
    # so `browser.free-ai` fails truthfully there, and whether to try this
    # instead is the Broker's decision to make and to record. A provider
    # that silently switched execution paths would be a provider deciding.
    #
    # The descriptor is built here rather than in the provider module
    # because a `ProviderSpec` comes from `ai_infrastructure`, which MB033
    # Rule 4 forbids a provider from importing at all.
    from master_agent.ai_infrastructure.catalog import (
        CLOUD as _CLOUD,
        DECLARED as _DECLARED,
        REASONING as _REASONING,
        THIRD_PARTY as _THIRD_PARTY,
        ProviderSpec as _ProviderSpec,
    )
    from master_agent.desktop.trusted_browser_adapter import DesktopTrustedBrowser
    from master_agent.providers.trusted_web_ai import (
        GEMINI_WEB,
        TRUSTED_WEB_PROVIDER_ID,
        TrustedWebAiProvider,
    )

    trusted_web_spec = _ProviderSpec(
        provider_id=TRUSTED_WEB_PROVIDER_ID,
        label="Web AI in the founder's own browser",
        capabilities=frozenset({_REASONING}),
        locality=_CLOUD,
        privacy=_THIRD_PARTY,
        declared_quality=0.72,
        cost_per_call=0.0,
        latency_ms=12000.0,
        needs_credentials=False,
        basis=_DECLARED,
        # States the requirement and deliberately no verdict: whether a
        # usable authenticated page exists is a fact about this minute,
        # which a record written last week cannot hold.
        notes=(
            "drives the founder's ordinary installed browser through the Desktop "
            "Executive; uses the session they are already signed into; requires a "
            "usable authenticated page, verified at use"
        ),
    )
    canonical_providers.register(descriptor_for(trusted_web_spec))
    provider_registry.register(
        TrustedWebAiProvider(
            browser=DesktopTrustedBrowser(desktop_plugin._context),
            site=GEMINI_WEB,
            interaction=founder_interaction(),
        ),
    )
    # KNOWN but deliberately NOT CONFIGURED for Founder Edition.
    #
    # The descriptor above keeps it administratively known, because the
    # provider and the whole Browser Worker behind it remain valid for
    # generic deployments. What Founder Edition does not do is register an
    # executable implementation, so `executable_provider_ids` omits it and
    # the Broker reports it unavailable rather than selecting something
    # that cannot authenticate. Founder policy: an AI website used as a
    # reasoning provider is driven in the founder's own browser.
    #
    # Nothing is deleted. A deployment that wants the automated lane
    # registers this provider itself.
    _FOUNDER_EDITION_REGISTERS_PLAYWRIGHT_WEB_AI = False
    if _FOUNDER_EDITION_REGISTERS_PLAYWRIGHT_WEB_AI:
        provider_registry.register(
            BrowserFreeAiReasoningProvider(
                sites=FOUNDER_EDITION_SITES,
                identity_id=FOUNDER_BROWSER_IDENTITY,
                sessions=getattr(browser_plugin, "_sessions", None),
                identities=browser_identities,
                interaction=founder_interaction(),
            ),
        )
    prompt_executor = PromptExecutor(
        service=intelligence, providers=provider_registry, ledger=ledger,
    )
    # FMEA reasoning scope. Dormant unless explicitly switched on: with the
    # variable unset this evaluates to the full ladder that has always been
    # here, so a normal Founder launch keeps Gemini -> Desktop -> Browser
    # byte for byte.
    #
    # It exists because an FMEA harness must be able to fail fast on its
    # own test provider. When Gemini returned 429 mid-run, the ladder did
    # exactly what the product should do -- fell through to the desktop AI
    # applications -- and launched twenty-three ChatGPT/Kimi/Perplexity
    # processes on the founder's machine before anything could stop it.
    # That is correct product behaviour and unacceptable test behaviour.
    #
    # The alternative was a pre-flight probe, and that does not work: a
    # small probe succeeds where a planning-sized request gets 429, and a
    # planning-sized probe consumes the very quota it is trying to predict.
    # Scoping the tiers is the only honest answer -- the harness refuses to
    # fall through rather than trying to guess whether it would need to.
    _fmea_reasoning = (os.environ.get("KALPAVRIKSHA_FMEA_REASONING_TIER") or "").strip().lower()
    _gemini_only = _fmea_reasoning == "gemini"
    # `web` isolates the trusted browser rung the same way `gemini` already
    # isolates the API rung, and for the same reason: a validation harness
    # must be able to prove ONE rung executes without the run silently
    # falling through to whichever provider happens to be healthy on the
    # founder's machine that minute. A harness that has to hope the higher
    # rungs fail is not evidence.
    #
    # This is VALIDATION CONFIGURATION, never product policy. Unset -- which
    # is every founder launch -- leaves the complete configured ladder
    # untouched, and an unrecognised value is treated exactly as unset,
    # which is the existing contract's own behaviour and is deliberately
    # not changed here. Nothing about Broker policy, provider ranking or
    # the normal web rung moves.
    _web_only = _fmea_reasoning == "web"

    tiered_runner = TieredPromptRunner(
        prompt_executor,
        # The free-cloud-API rung. Membership follows what this
        # deployment actually CONFIGURED, so a credentialled service joins
        # by having a credential rather than by being named in a branch
        # here -- the same known-is-not-configured rule the candidate
        # boundary already enforces.
        gemini_provider_ids=frozenset() if _web_only else frozenset(
            _configured_cloud_providers()
        ),
        desktop_provider_ids=frozenset() if (_gemini_only or _web_only) else frozenset(
            spec.provider_id for spec in PROVIDER_CATALOG if spec.locality == DESKTOP
        ),
        # The web rung, now filled. Reached only after Gemini API and the
        # desktop AI applications have both been tried and failed, which
        # is ADR-0017's order and not a special case for 429 -- there is
        # deliberately no `if status == 429` anywhere near this.
        # Founder Edition's web rung is the TRUSTED browser lane: the
        # founder's own signed-in browser, driven through the Desktop
        # Executive. Not the Playwright one -- Google refuses to sign in
        # inside an automation-controlled browser ("this browser or app may
        # not be secure"), so `browser.free-ai` cannot authenticate a
        # Google account at all and would occupy this rung without being
        # able to serve it.
        browser_provider_ids=frozenset({TRUSTED_WEB_PROVIDER_ID}),
        desktop_context=desktop_plugin._context,
        # The Broker sees every spec in `providers_source`'s own `specs`
        # tuple (`PROVIDER_CATALOG + (BROWSER_FREE_AI_SPEC,)` — Ollama,
        # LM Studio, OpenAI, OpenRouter included), not just the three
        # tiers above. Without this, any of those could win a tier's
        # scoped Broker call by ranking (Ollama notably — this codebase's
        # own repeated "never enable/query Ollama" constraint) purely
        # because nothing had told this ladder they existed to exclude.
        # DERIVED from the canonical registry rather than hand-listed, and
        # that is the whole repair. This was `PROVIDER_CATALOG` plus one
        # named id, so a provider registered here but absent from the
        # global catalogue -- which is exactly what `trusted-founder-web`
        # is -- was visible to the Broker through `providers_source` while
        # being invisible to this ladder's exclusion set. A provider the
        # ladder does not know exists cannot be excluded from an upper
        # rung's scoped Broker call, so it could win a tier it was never
        # placed in.
        #
        # The canonical registry is the administrative owner of "which
        # providers exist". Deriving from it means the next provider to be
        # registered is scoped correctly without anyone remembering to
        # edit this line. `test_founder_edition_provider_universe.py` pins
        # the invariant: everything the Broker can see is something this
        # ladder knows about.
        all_known_provider_ids=frozenset(
            descriptor.provider_id for descriptor in canonical_providers.all()
        ),
    )
    # The Reasoning Executive delegates to this same ladder -- one
    # routing stack for planning and for mid-mission judgement alike.
    reasoning_plugin.bind_runner(tiered_runner)
    # MB039's richer index, not the plain CapabilityRegistry — the same
    # exact pattern `build_system()` uses, and for the same reason: the
    # simple `catalogue_from(registry)` path carries no `required_args`,
    # so the Planner's prompt never tells Gemini a capability like
    # `Browser.OpenBrowserSession` needs a `session_id` — proven live
    # against the real API, not assumed.
    contracts = []
    # Every Executive this root registers, not a subset. Omitting the
    # two new ones left the Planner unable to SEE reading a document
    # or reasoning over one -- so it answered the founder's CV
    # objective with `NO_STEPS`, correctly, about a machine that
    # could in fact do the work. It reported checking 43 things; the
    # three it was never shown were the three the objective needed.
    for plugin in (browser_plugin, desktop_plugin, filesystem_plugin,
                   document_plugin, reasoning_plugin):
        actions = getattr(plugin, "_actions", None)
        if isinstance(actions, dict):
            contracts.extend(
                contracts_from_actions(actions, plugin.manifest.name, qualified_name)
            )
    capability_index = build_index(
        contracts, loader={c.canonical_id: c for c in contracts}.get
    )
    # `runner=tiered_runner`, not the bare `prompt_executor` — Planner's
    # own code needs no change to gain the fallback ladder: both objects
    # expose the identical `run(prompt, request, **kwargs)` surface
    # (`tiered_runner.py`'s own docstring cites the exact interface this
    # session's own research confirmed `Planner` requires).
    # The founder's LOCAL / AI MODE / BOTH switch. One mutable cell shared
    # between the surface (which sets it) and the Planner (which reads it
    # at plan time) -- the founder flips it mid-session and the Planner is
    # built once at boot, so a captured value would freeze the choice made
    # at startup. The root stores; it decides nothing.
    from master_agent.planner.modes import DEFAULT_MODE, normalise as _normalise_mode

    mode_cell = {"mode": DEFAULT_MODE}
    planner = Planner(
        runner=tiered_runner, catalogue=capability_index,
        mode=lambda: mode_cell["mode"],
    )
    # ---- durable audit history ---------------------------------------
    #
    # The founder's last real session could not be audited after the
    # process exited, because this composition persisted nothing: no
    # event log, no plan history, no snapshot. The architecture for all
    # three already existed and was simply never constructed here --
    # `launcher/boot.py` has wired exactly this since MB025/MB037.
    #
    # `PersistenceService` appends every bus event to a durable log
    # (PERSISTENCE_ARCHITECTURE.md §3: "the event log, appended as events
    # happen -- audit history, replay") and `PlanHistory` records one row
    # per mission with an entry per step. Both are subscribers: they
    # observe the bus and drive nothing, so adding them cannot change
    # what Kalpavriksha does -- only what survives it.
    #
    # Deliberately NOT restored into the runtime. This mission is about
    # being able to reconstruct what happened, not about resuming
    # interrupted missions after a restart; recovery semantics are their
    # own decision and `restore_into()` is left uncalled.
    from master_agent.missions.history import (
        HISTORY_FILENAME, JsonFilePlanStore, PlanHistory,
    )
    from master_agent.persistence.service import PersistenceService
    from master_agent.persistence.store import JsonFileStateStore

    state_dir = _app_state_dir()
    # ADR-0025. Written by the surface, read by an investigator, and by
    # nothing in the Brain, Planner or Runtime -- that boundary is what
    # keeps a transcript from becoming a memory system.
    from master_agent.audit import FILENAME as _INTERACTIONS, InteractionLog, JsonlInteractionStore

    interactions = InteractionLog(JsonlInteractionStore(state_dir / _INTERACTIONS))
    persistence = PersistenceService(JsonFileStateStore(state_dir), mission_control)
    # The canonical provider record travels in the same snapshot as
    # everything else. Attached once here so no later save can quietly
    # omit it -- proving `build_snapshot(registry=...)` in isolation while
    # the composition never passes one is how a component ends up built
    # and unused.
    persistence.attach_provider_registry(canonical_providers)
    persistence.start_recording()
    # ...and something has to actually WRITE one. Attaching the registry
    # guaranteed the provider slice would be in every snapshot this
    # composition saved; it saved none. `launcher/boot.py` has passed
    # `checkpoint_sink=persistence` to its RuntimeEngine since MB025 and
    # this root never did, so the restore path above was reading a file
    # the application itself never produced -- a persistence layer that
    # was correct in every part and inert as a whole.
    #
    # The Runtime checkpoints at the end of every cycle and once more on a
    # graceful stop, and `save_checkpoint()` rewrites the whole snapshot
    # when a MissionControl is attached, so runtime counters, mission
    # state and the canonical provider record always describe the same
    # moment rather than three different ones.
    runtime.attach_checkpoint_sink(persistence)
    plan_history = PlanHistory(store=JsonFilePlanStore(state_dir / HISTORY_FILENAME))
    plan_history.attach_to(mission_control)

    mission_service = MissionService(
        planner=planner, mission_control=mission_control,
        # The SAME runner the Planner was given, not a second path to a
        # provider: understanding what a founder's sentence is doing is
        # something the Brain reasons about, and VISION_V2 §3.3 gives the
        # Brain exactly one door for that. Consulted for one narrow
        # decision only -- see `IntentLayer.decide_role` -- so the
        # ordinary answer still costs nothing.
        intent_layer=IntentLayer(
            reasoner=tiered_runner,
            # This machine's own current facts, for a founder question
            # about this machine. Read at ASK time, never captured now:
            # a provider's availability changes during a session, and an
            # answer built from a snapshot taken at boot would be stale
            # in exactly the way that misleads.
            grounding=lambda: _current_system_facts(
                capability_index, tiered_runner, plan_history
            ),
            # The places a filesystem capability can actually reach --
            # the SAME table the plugin was built with, including the
            # founder's D: drive. Handed over rather than re-derived: a
            # second copy is a copy that drifts, and the Intent Layer's
            # job is mapping the founder's meaning onto values the
            # machine can act on.
            vocabularies={"location": tuple(sorted(_locations))},
        ),
        reporter=Reporter(),
        history=plan_history,
    )

    # Task 2.5 — the Hyper Agent status contract. One ExecutionStatus,
    # subscribed to the same bus every other observer in this composition
    # already reports through; it never decides anything, only records
    # what already happened (see missions/execution_status.py).
    from master_agent.missions.execution_status import ExecutionStatus

    status = ExecutionStatus()
    mission_control.bus.subscribe(status.record, event_type=None)


    # `tiered_runner` is returned as well as given to the Planner: it is
    # the Brain's one door to reasoning (VISION_V2 §3.3), and planning is
    # only one of the things the Brain reasons about. Returning the same
    # instance is what keeps `brain/advisory.py` from needing a provider
    # path of its own -- one ladder, one Broker, one decision trail.
    def _set_mode(mode: str) -> str:
        """Normalise and store, and RETURN what was resolved.

        The surface used to import `planner.modes` and normalise its own
        copy -- putting the founder-facing package inside the Planner's
        namespace to read two constants, which
        `TestOnlyComposition::test_no_mission_os_surface_is_reachable`
        forbids. The vocabulary lives here, so the answer travels back
        the same way every other fact does.
        """
        resolved = _normalise_mode(mode)
        mode_cell["mode"] = resolved
        return resolved

    def decide_approval(approval_id, approved, note=""):
        """Carry the founder's decision to Mission Control -- and, on
        approval, into the grant ledger that the permission boundary
        actually reads.

        Both steps are required, and the second is not a workaround.
        `ApprovalQueue.find_open` is scoped to *undecided* requests by
        design ("an approved one does not silently authorise a repeat"),
        so an answered approval does not by itself let the held task
        through -- the next boundary check would open a fresh question and
        the task would wait forever. `GrantScope.ONCE` is the existing
        mechanism for exactly this: it authorises this one execution and
        is consumed by it, which preserves the no-silent-repeat property
        the queue is protecting.

        ## Why this lives here and not in `main()`

        It used to be defined inside `main()`, where `permissions` and
        `GrantScope` are not in scope -- both are local to THIS function.
        Python compiled them as global lookups, and neither name exists at
        module level, so the first time a founder pressed Approve the
        bridge raised `NameError` instead of granting anything. Nothing
        caught it because the closure was unreachable without running
        `main()`, which opens a real window.

        Defined here, next to the `PermissionSystem` it needs, it is in
        the same place and the same shape as `_set_mode` above, and
        `tests/test_founder_approval_path.py` can call it directly.
        """
        if not approved:
            return mission_control.reject(approval_id, "founder", note).as_dict()

        approval = mission_control.approvals.get(approval_id)
        if approval is not None:
            permissions.grant(
                approval.executive_id, approval.local_capability,
                GrantScope.ONCE,
            )
        decision = mission_control.approve(approval_id, "founder", note).as_dict()

        # AND THEN THE WORK ACTUALLY RUNS.
        #
        # Without this the founder pressed Approve, the grant was
        # recorded, the approval was marked approved -- and nothing ever
        # happened. `_submit_objective` is the only other thing that turns
        # the Runtime, and it returned long before the founder decided, so
        # the authorised task sat at `awaiting_approval` forever. Proven
        # live: approve, then wait ten seconds with nobody turning the
        # crank, and the file the founder had just authorised deleting was
        # still there.
        #
        # A permission gate that holds work and never releases it is worse
        # than no gate, because the founder is told their decision was
        # recorded. This is the release.
        objective_id = getattr(status, "objective_id", None)
        if objective_id:
            _drive_until_settled(runtime, mission_control, status,
                                 objective_id, 180.0)
            # What the founder is told next time the surface asks. The
            # branches mirror `_submit_objective`'s own tail and reuse the
            # same Reporter and the same sentence composers -- this root
            # still writes no founder prose of its own.
            state = mission_control.founder_state(objective_id)
            if state.errors:
                logging.warning("objective failed after approval: %s",
                                "; ".join(state.errors))
                status.message = _founder_failure_sentence("; ".join(state.errors))
            elif state.progress >= 1.0:
                status.result = state.result
                status.message = _mission_report(mission_service, objective_id) or (
                    "The work finished, but I can't reconstruct a verified "
                    "mission summary."
                )
        return decision

    return (mission_service, runtime, mission_control, status, tiered_runner,
            _set_mode, interactions, decide_approval)


class _ExecutionThread:
    """One long-lived thread that every Runtime step runs on.

    ## The failure this exists for

    Founder acceptance died here, verbatim:

        failed to open browser session: cannot switch to a different
        thread (which happens to have exited)

    Playwright's synchronous API is bound to the thread that started its
    driver, and `BrowserSessionManager` caches that driver for the life
    of the process -- correctly, because one driver per manager is the
    Constitution's Environment Session Manager rule. The founder surface
    answers each message on a **different, short-lived HTTP worker
    thread** from the JS-API server's pool. So the first mission started
    the driver on a thread that then exited, and the next Playwright call
    from any later thread hit exactly the error above.

    Reproduced directly against the real manager before this was written:
    open a session on a thread, let that thread exit, open another from a
    second thread, and the second raises that sentence.

    ## Why the fix is here and not in the browser code

    Marshalling inside `BrowserSessionManager` would not be enough. The
    Browser actions hold `Page` objects and call `page.goto(...)`,
    `locator(...).click()` and the rest directly, and those objects carry
    the same thread affinity -- so the manager could hand back a working
    session that the very next line still could not use.

    The defect is not that Playwright is fussy. It is that mission
    execution ran on whichever HTTP worker happened to arrive. A Runtime
    step may hold any thread-affine resource; giving execution one stable
    thread fixes the whole class rather than one library.

    Not a scheduler and not a second orchestration authority: it decides
    nothing, holds no mission state, and runs exactly what
    `_drive_until_settled` already ran, in the order it already ran it.
    The caller still blocks on the result, so ordering and back-pressure
    are unchanged.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pool = None

    def run(self, call):
        """Run `call` on the execution thread and return its result.

        Exceptions propagate to the caller unchanged, so every existing
        error path -- refusals, failures, the founder-facing sentences --
        behaves exactly as it did when this ran inline.
        """
        from concurrent.futures import ThreadPoolExecutor

        with self._lock:
            if self._pool is None:
                # `max_workers=1` IS the contract here, not a tuning
                # choice: a second worker would reintroduce the exact
                # defect this class exists to remove.
                self._pool = ThreadPoolExecutor(
                    max_workers=1, thread_name_prefix="kalpavriksha-exec"
                )
            pool = self._pool
        return pool.submit(call).result()


#: How many extra acquisition cycles one mission may spend.
#:
#: A system that can decide "research more" becomes an infinite
#: researcher without a number here. Small on purpose: the founder waits
#: through every cycle, and `no_useful_progress` stops it earlier than
#: this whenever a cycle establishes nothing.
_RESEARCH_BUDGET = 2


#: The ordinary Browser lane's session manager, held by the composition
#: root that built it so a mission which ends without running its planned
#: `CloseBrowserSession` can still have its environment released.
#:
#: `None` until the pipeline is built, and nothing here assumes it is not.
_BROWSER_SESSIONS = None


def _release_task_browsers() -> None:
    """Let go of task-owned browser sessions after a mission ends.

    A mission that failed before its planned `CloseBrowserSession` left
    session `'main'` open; the next attempt planned its own
    `OpenBrowserSession('main')` and died on `session already open`. One
    attempt's leftovers made the next one impossible, which is what took
    autonomous recovery off the table.

    Anonymous sessions only -- the founder's signed-in browser is theirs
    and is never touched. Best-effort and silent: releasing an
    environment is housekeeping, and a warning about it does not belong
    in a founder's reply.
    """
    manager = _BROWSER_SESSIONS
    if manager is None:
        return
    try:
        # ON THE EXECUTION THREAD, like every other Playwright call.
        #
        # Closing a session drives the same thread-affine driver that
        # opened it, so doing it from whichever thread happened to reach
        # the end of a mission corrupts the driver for every mission
        # after it. Measured immediately after this cleanup was added and
        # called inline: the next `OpenBrowserSession` failed with "It
        # looks like you are using Playwright Sync API inside the asyncio
        # loop", and every step behind it stayed pending.
        #
        # The invariant was already established and this call broke it.
        released = _EXECUTION.run(manager.close_anonymous)
    except Exception:  # noqa: BLE001 -- cleanup never becomes the failure
        logging.exception("browser session cleanup failed")
        return
    if released:
        logging.info("released task-owned browser sessions: %s",
                     ", ".join(sorted(released)))


#: Process-wide, because the thread affinity being protected is
#: process-wide: one Playwright driver, one browser, one execution
#: thread. A per-mission thread would put the second mission back on a
#: different thread from the driver the first one started.
_EXECUTION = _ExecutionThread()


def _observations_from(mission_control, objective_ids):
    """Canonical Evidence, read as things that were actually seen.

    Only Evidence carries an `evidence_id`, and only steps that produced
    Evidence appear here -- so a claim can later be traced to an
    independent observation rather than to a model's memory of one. A
    step that ran and observed nothing contributes nothing, which is the
    correct amount.
    """
    from master_agent.brain.deliberation import (
        CORROBORATION, DISCOVERY, PRIMARY, Observation,
    )

    if isinstance(objective_ids, str):
        objective_ids = (objective_ids,)

    found = []
    tasks = []
    for one in objective_ids:
        try:
            tasks.extend(mission_control.dispatcher.objective(one).tasks)
        except Exception:  # noqa: BLE001 -- an unreadable record observes nothing
            continue
    for task in tasks:
        evidence = getattr(task, "evidence", None) or {}
        if not isinstance(evidence, dict):
            continue
        evidence_id = str(evidence.get("evidence_id") or "").strip()
        if not evidence_id:
            continue
        observed = evidence.get("observation")
        if not isinstance(observed, dict):
            continue
        text = ""
        for key in ("text", "page_text", "content", "accessibility_tree"):
            value = observed.get(key)
            if isinstance(value, str) and value.strip():
                text = value
                break
        if not text:
            continue
        url = str(observed.get("url") or "")
        # Source class from what was observed, never from a hostname
        # table. A page served by the party a claim is ABOUT is primary
        # for that claim; a search or listing page is where candidates
        # are FOUND, not where they are established.
        lowered = url.lower()
        if any(mark in lowered for mark in ("/search", "?q=", "&q=", "/browse")):
            source_class = DISCOVERY
        elif url:
            source_class = PRIMARY
        else:
            source_class = CORROBORATION
        found.append(Observation(
            evidence_id=evidence_id, text=text,
            source_class=source_class, url=url,
        ))
    return tuple(found)


def _decide(mission_service, mission_control, intent, objective_ids):
    """Perform the decision this mission was framed for, or return None.

    The frame was written at admission, before any evidence existed. This
    is the other end of it: the same criteria, now answered against what
    was actually observed.

    `objective_ids` is EVERY attempt this objective made, not the last
    one. A replan starts a new mission record, and reading only the
    newest one threw away everything the earlier attempts established --
    so a mission that read the directory on its first pass and the
    opening hours on its third could never decide anything, because no
    single record ever held both. It reported "mandatory criteria remain
    unestablished" while holding, between them, every fact it needed.

    That is the direct opposite of the rule recovery is built on: a
    second attempt must PRESERVE verified work, and Evidence is what
    verified work IS.

    `None` whenever there is nothing to decide -- no frame, or nothing
    seen. Most missions are that, and they pay nothing for this.
    """
    frame_row = (getattr(intent, "context", None) or {}).get("decision_frame")
    if not isinstance(frame_row, dict):
        return None
    observations = _observations_from(mission_control, objective_ids)
    if not observations:
        return None

    from master_agent.brain.deliberation import Criterion, DecisionFrame, deliberate

    frame = DecisionFrame(
        objective=str(frame_row.get("objective") or ""),
        requirement_ids=tuple(frame_row.get("requirement_ids") or ()),
        decision_type=str(frame_row.get("decision_type") or ""),
        mandatory=tuple(
            Criterion(
                criterion_id=str(row.get("criterion_id") or ""),
                description=str(row.get("description") or ""),
                requirement_id=str(row.get("requirement_id") or ""),
                mandatory=bool(row.get("mandatory", True)),
            )
            for row in (frame_row.get("mandatory") or [])
        ),
    )
    try:
        return deliberate(
            frame, observations,
            getattr(mission_service.intent_layer, "_reasoner", None),
        )
    except Exception:  # noqa: BLE001 -- an undecided mission still reports
        logging.exception("deliberation failed")
        return None


def _plain(claims) -> str:
    """Claims as a founder can read them.

    An internal claim carries its candidate id, criterion id and the
    Evidence UUIDs behind it -- all necessary, none of it English. The
    first real deliberation put four UUIDs into the founder's reply
    twice over. Provenance belongs in the record, which keeps it; the
    sentence gets the part a person can act on.
    """
    names = []
    for claim in claims:
        text = str(claim)
        if ": " in text:
            text = text.split(": ", 1)[1]
        for separator in (". Evidence:", " Evidence:"):
            if separator in text:
                text = text.split(separator, 1)[0]
        text = text.strip()
        if text and text not in names:
            names.append(text)
    return "; ".join(names) if names else "something it could not name"


def _unvisited_links(mission_control, objective_ids) -> list[dict]:
    """Somewhere a page already read says you can go, that nobody went.

    The missing half of a research system that can decide it needs more
    evidence. Naming the unresolved criterion tells the Planner WHAT to
    settle; this tells it WHERE it may be settled -- and both come out of
    canonical Evidence, so neither is a model inventing a destination.

    Concretely, this is what a mission looked like without it: read a
    directory page, decide "nobody has established the Sunday hours",
    replan, and re-read the same directory page, twice, because the page
    TEXT keeps the words "Sunday opening hours" and loses the address
    behind them.
    """
    if isinstance(objective_ids, str):
        objective_ids = (objective_ids,)

    tasks = []
    for one in objective_ids:
        try:
            tasks.extend(getattr(
                mission_control.dispatcher.objective(one), "tasks", ()) or ())
        except Exception:  # noqa: BLE001 -- an unreadable record points nowhere
            continue

    visited: set[str] = set()
    offered: dict[str, str] = {}
    for task in tasks:
        evidence = getattr(task, "evidence", None) or {}
        observed = evidence.get("observation") if isinstance(evidence, dict) else None
        if not isinstance(observed, dict):
            continue
        for key in ("url", "url_normalised"):
            been = str(observed.get(key) or "").strip()
            if been:
                visited.add(been.rstrip("/"))
        for link in observed.get("links") or ():
            if not isinstance(link, dict):
                continue
            url = str(link.get("url") or "").strip()
            if url and url not in offered:
                offered[url] = str(link.get("text") or "").strip()

    return [
        {"text": text, "url": url}
        for url, text in offered.items()
        if url.rstrip("/") not in visited
    ]


def _evidence_question(result, unvisited: list[dict] | None = None) -> dict | None:
    """What is still missing, said precisely enough to go and get.

    `None` when there is nothing to ask for. Otherwise the unresolved
    criteria and the candidates they belong to -- because "search more"
    is not a question anybody can act on, and the difference between
    that and "establish whether these three are open on Sunday" is the
    difference between another broad sweep and one targeted look.

    Nothing domain-specific: criteria and candidate names come from the
    frame the Brain already built out of the founder's own requirements.
    """
    if result is None or not result.more_research:
        return None
    # By what it ASKS, never by its id. The Planner was being handed
    # "still unresolved: crit_2" and asked to go and settle it.
    asks = dict(result.criteria or {})
    missing: dict[str, list[str]] = {}
    for rejected in result.rejected:
        for criterion in rejected.unverified:
            question = asks.get(criterion, criterion)
            missing.setdefault(question, [])
            if rejected.summary not in missing[question]:
                missing[question].append(rejected.summary)

    # Nothing was extracted at all -- no shortlist and nothing rejected.
    #
    # That is not "nothing to ask for", it is the widest possible
    # question: the first source established none of the criteria, so
    # every one of them is still open. Returning None here was why a
    # mission that read one page, learned nothing usable and knew it
    # stopped after a single cycle -- it had decided more research was
    # needed and then had nothing to say about what.
    if not missing and not result.shortlist and not result.rejected:
        missing = {question: [] for question in asks.values()}
    if not missing:
        return None
    return {
        "unresolved_criteria": sorted(missing),
        "candidates": {k: v[:8] for k, v in missing.items()},
        "already_established": [
            candidate.summary for candidate in result.shortlist
        ],
        # Where to look, alongside what to look for. Both from Evidence.
        "unvisited": (unvisited or [])[:12],
    }


def _decision_sentence(result) -> str:
    """What the decision means, for a founder, in their terms.

    Conclusions and the evidence behind them. Never the extraction
    prompt, never a transcript, never internal scores -- a reviewable
    answer is not a reasoning trace.
    """
    from master_agent.brain.deliberation import CONTESTED, DECIDED

    if result is None:
        return ""
    if result.state == DECIDED and result.shortlist:
        lines = [f"{len(result.shortlist)} of what I found meets everything you asked for:"]
        for candidate in result.shortlist:
            lines.append(f"  - {candidate.summary}")
        if result.rejected:
            lines.append(
                f"I ruled out {len(result.rejected)}: "
                + "; ".join(
                    f"{r.summary} ({r.reason})" for r in result.rejected[:3]
                )
            )
        return "\n".join(lines)
    if result.state == CONTESTED:
        return (
            "Sources disagree about "
            + _plain(result.unresolved[:3])
            + ", and nothing authoritative settles it, so I am not going "
            "to pick for you."
        )
    # Nothing cleared the bar. Saying so is the useful answer -- an empty
    # list presented as a result is how a founder ends up with nothing
    # and the impression of something.
    rejected = (
        f" I looked at {len(result.rejected)} and could not confirm all of "
        "what you asked for any of them."
        if result.rejected else ""
    )
    return (
        f"I could not confirm anything that meets all of it.{rejected} "
        f"{result.rationale}"
    ).strip()


def no_useful_progress(before, after) -> bool:
    """Re-exported so the mission loop reads as one thought.

    The rule itself lives in the Brain, which owns what progress means;
    this is the name the surface calls it by.
    """
    from master_agent.brain.deliberation import (
        no_useful_progress as _no_useful_progress,
    )

    return _no_useful_progress(before, after)


def _mission_progress(mission_control, intent, objective_id):
    """Where this mission stands, from the records that already hold it."""
    from master_agent.brain.deliberation import progress_of

    try:
        objective = mission_control.dispatcher.objective(objective_id)
    except Exception:  # noqa: BLE001 -- an unreadable record stands nowhere
        return None
    return progress_of(
        str(getattr(intent, "goal", "") or ""),
        tuple(getattr(intent, "requirements", ()) or ()),
        # Read defensively: this is now consulted on EVERY mission, not
        # only on the replan path, and the surface tests drive the bridge
        # with the smallest record that makes their own point -- rightly.
        getattr(objective, "tasks", ()) or (),
    )


def _recovery_decision(mission_control, intent, objective_id, attempts_used):
    """Ask the Brain what a failed mission's failure MEANS.

    The surface does not decide this and must not. It observes that a
    mission stopped, hands the Brain the facts, and relays the answer to
    the lifecycle authority that already exists. `MissionDispatcher`'s
    own comment says auto-retry "would be a strategic recovery decision,
    which belongs to the Brain"; this is the call it was waiting for.

    Returns `None` when there is nothing to decide.
    """
    from master_agent.brain.conformance import SATISFIED, assess
    from master_agent.brain.deliberation import recovery_for

    requirements = tuple(getattr(intent, "requirements", ()) or ())
    if not requirements:
        return None
    try:
        objective = mission_control.dispatcher.objective(objective_id)
        outcome = assess(requirements, objective.tasks)
    except Exception:  # noqa: BLE001 -- an unreadable record decides nothing
        return None

    satisfied = tuple(
        row.requirement_id for row in outcome.requirements
        if row.state == SATISFIED
    )
    unmet = tuple(
        row.requirement_id for row in outcome.requirements
        if row.state != SATISFIED
    )
    # Partial success no longer stops recovery.
    #
    # This used to return `None` whenever anything was satisfied, because
    # replanning from scratch would re-run work reality had already
    # confirmed -- and for a capability with an external effect that is
    # not a wasted step, it is a second real change to the founder's
    # machine. The Planner now receives the satisfied requirement ids and
    # is told plainly not to redo them, so the reason for the guard is
    # gone and keeping it would abandon missions that are most of the way
    # there.
    return recovery_for(
        unmet_requirements=unmet,
        alternatives_available=True,
        attempts_used=attempts_used,
    )


def _drive_until_settled(runtime, mission_control, status, objective_id,
                         timeout_seconds: float) -> None:
    """Turn the Runtime until this objective settles or waits on a human.

    The ONE place anything drives `run_once()`. It was inline in
    `_submit_objective`, which meant the only moment work could progress
    was the founder's own message -- and a founder answering a question
    the mission had already asked was not that moment. See
    `decide_approval` for what that cost.

    Not a scheduler and not a second orchestration authority: the same
    bounded loop as before, in a function, so that both callers share one
    implementation rather than growing two that drift.

    ## Why the break reads `approval_id` rather than the status string

    `status.approval_id` is the authoritative "a question is open" fact --
    its own docstring says `None` whenever nothing is pending, and
    `APPROVAL_GRANTED`/`APPROVAL_DENIED` clear it. `status.status` is a
    label that still reads `awaiting_approval` immediately after a founder
    has answered, so breaking on it would stop the resume loop on its
    first pass, before the newly-granted work ever ran. Same behaviour on
    the original path, where both are set together.
    """
    import time as _time

    def _progress_mark():
        """What "this mission moved" looks like from outside.

        Read from Mission Control rather than counted here: this function
        observes progress, it does not define it.
        """
        try:
            state = mission_control.founder_state(objective_id)
            return (state.progress, tuple(state.errors or ()))
        except Exception:  # noqa: BLE001 - a mark is best-effort, never fatal
            return None

    deadline = _time.monotonic() + timeout_seconds
    mark = _progress_mark()
    objective = mission_control.dispatcher.objective(objective_id)
    # A failed step is not a finished mission.
    #
    # This read `objective.has_failure`, so the first failure stopped the
    # loop -- abandoning every step that could still run. On the founder's
    # research objective that meant one site refusing us ended a mission
    # with two more sources sitting READY and never dispatched.
    #
    # `has_runnable_work` is Mission Control's own fact, the same one it
    # computes before declaring an objective failed, so the loop now stops
    # exactly when the lifecycle authority says there is nothing left.
    while _time.monotonic() < deadline and not (
        objective.is_complete
        or (objective.has_failure and not objective.has_runnable_work)
    ):
        # On the one execution thread, always. See `_ExecutionThread`.
        _EXECUTION.run(runtime.run_once)
        objective = mission_control.dispatcher.objective(objective_id)

        # **The deadline bounds silence, not work.**
        #
        # `run_once()` blocks for the whole of the step it runs, and a step
        # that asks a desktop AI for an answer legitimately takes minutes.
        # So the elapsed clock had always expired by the time control came
        # back -- and the loop exited holding a mission that was perfectly
        # healthy and half finished.
        #
        # Measured in the packaged application, on "think of three short
        # names ... and write them into packaged_names.txt": the plan was
        # right, `Reasoning.Transform` ran, produced real text and was
        # verified `matched` -- and `Filesystem.WriteFile` was never
        # dispatched, because this loop had already given up. Nothing else
        # drives the Runtime, so the mission stayed abandoned, and the
        # founder watched "that's taking longer than expected" forever
        # about work that had stopped.
        #
        # A mission that just moved is not a mission that is stuck. Every
        # observable step forward returns the full budget; the bound is
        # still real, and still stops a genuinely hung provider, but it now
        # measures how long the mission has been SILENT rather than how
        # long it has been running.
        moved = _progress_mark()
        if moved != mark:
            mark = moved
            deadline = _time.monotonic() + timeout_seconds
        # Waiting on the founder is a terminal state for THIS call. The
        # work has run and been verified; nothing further will happen
        # until a human answers, so spinning to the deadline only delays
        # telling them so -- and, before this, ended in "that's taking
        # longer than expected" about a mission that had already finished.
        if status.requires_founder_completion or status.approval_id:
            break
        if not (objective.is_complete or objective.has_failure):
            _time.sleep(0.2)


def _founder_reply(status, reply: str, *, interaction_type: str = "") -> dict:
    """The reply, plus the identifiers the audit needs to join it.

    Every return from `_submit_objective()` used to be `{"reply": text}`,
    and the first packaged FMEA measured the consequence: mission_id 0/8,
    status 0/8, clarification_id 0/8 on the interaction audit. The fields
    existed and were designed; the transport simply dropped them, so an
    investigator could only join a founder turn to its mission by
    timestamp proximity -- which stops being reliable the moment two
    missions overlap.

    Nothing here owns anything. `ExecutionStatus` is the mission owner and
    already holds every one of these at the moment of return; this
    projects them onto the wire (ADR-0025: the audit records mission
    identity, it never becomes the source of it).
    """
    pending = getattr(status, "pending_clarification", None)
    return {
        "reply": reply,
        "mission_id": getattr(status, "objective_id", None),
        "status": getattr(status, "status", None),
        "clarification_id": getattr(pending, "clarification_id", None),
        "approval_id": getattr(status, "approval_id", None),
        "completion_id": getattr(status, "completion_id", None),
        "interaction_type": interaction_type or None,
    }


def _mission_report(mission_service, objective_id: str | None) -> str:
    """What the Brain's Reporter says about this mission, or "".

    Terminal Founder messages used to be composed from `state.result` --
    the most recently completed Task's output. That is a truthful thing to
    call "the last task result" and an untruthful thing to call "the
    mission outcome": a three-step browser mission ending in a cleanup
    step reported `{"closed": true}` as though closing the browser were
    what Onkar had asked for.

    The authoritative record is the `PlanRecord` the Runtime wrote, with
    the exact Evidence Verification produced now durable on each step. This
    asks the already-wired Reporter to explain that, and returns "" when it
    genuinely cannot -- the caller then says so plainly rather than
    substituting a task output.
    """
    reporter = getattr(mission_service, "reporter", None)
    history = getattr(mission_service, "history", None)
    if reporter is None or history is None or not objective_id:
        return ""
    try:
        record = history.get(objective_id)
    except Exception:  # noqa: BLE001 -- reporting must not break a mission
        logging.exception("could not read mission history for %s", objective_id)
        return ""
    if record is None:
        return ""
    try:
        return reporter.report_plan_record_outcome(record).body
    except Exception:  # noqa: BLE001
        logging.exception("reporter failed for %s", objective_id)
        return ""


def _submit_objective(mission_service, runtime, mission_control, status, text: str,
                       timeout_seconds: float = 45.0) -> dict:
    """One founder objective, run to a terminal state, and a plain reply
    dict — `desktop_shell.py` never sees a `MissionOutcome`/`FounderState`,
    only a dict shaped exactly like `send_message()`'s own return value.

    Drives the existing `RuntimeEngine.run_once()` in a bounded loop — the
    same call `run_forever()` itself makes, just capped so one synchronous
    pywebview bridge call can return a real result instead of a background
    daemon. Not a new orchestration authority: nothing here decides
    anything `MissionService`/`RuntimeEngine`/`CapabilityBroker` did not
    already decide.
    """
    import time as _time
    from master_agent.brain.intent import ClarificationQuestion
    from master_agent.brain.utterance import UtteranceRole
    from master_agent.missions.execution_status import (
        AWAITING_APPROVAL,
        AWAITING_CLARIFICATION,
        AWAITING_FOUNDER_COMPLETION,
        COMPLETED,
        FAILED,
        PendingClarification,
    )
    from master_agent.planner import NO_STEPS

    # Read the open question BEFORE `begin()` clears it: the founder's
    # answer arrives as the next message, so the turn that resolves a
    # clarification is the same turn that would otherwise reset it.
    #: Set by the informational-question branch below, when the founder
    #: asked something rather than ordered something. `None` everywhere
    #: else, so the ordinary clarify/parse fork is untouched.
    intent_result = None
    pending = status.pending_clarification
    # The mission this founder turn FOLLOWS, for the same reason -- a
    # question about what just happened is answered from the record of
    # what just happened, and `begin()` is about to clear the pointer.
    previous_objective_id = getattr(status, "objective_id", None)

    # What ROLE this utterance plays. Asked of the Brain, and asked BEFORE
    # anything is done with the utterance -- this root still decides
    # nothing, it just no longer assumes.
    #
    # The assumption it replaces was written here in as many words: "a
    # question was asked last turn, so this message is its answer." A
    # pending clarification is CONTEXT -- it says a question is open. It
    # does not own whatever the founder says next, which is why
    # `awaiting_answer` is passed as one input among several rather than
    # used as the branch it used to be.
    # `mission_service`'s OWN Intent Layer, the same instance that parses
    # and clarifies below -- there is one Intent Layer in this process,
    # not a second one wired up here.
    role = mission_service.intent_layer.decide_role(
        text,
        awaiting_answer=pending is not None,
        options=tuple(pending.options) if pending is not None else (),
        question=pending.question if pending is not None else "",
        objective=pending.objective if pending is not None else "",
        objective_id=getattr(status, "objective_id", None),
        # Whether there is anything to follow up ON. A question about the
        # past needs a past; without one, an interrogative is a question
        # to ANSWER, not a report to fetch. The surface holds this fact --
        # the Brain sees one sentence, not the conversation.
        has_referent=previous_objective_id is not None,
    )

    status.begin(text, timeout_seconds=timeout_seconds)

    if role is UtteranceRole.CANCEL_OR_STOP:
        # Nothing failed and nothing completed, so neither terminal status
        # is truthful -- and there is no Objective to terminate either:
        # clarification happens BEFORE `mission_service.start()`, so a
        # question abandoned here never became a mission. `begin()` has
        # already cleared the pending question; the honest record of this
        # turn is that no mission ran, which is exactly `status = None`.
        #
        # (ADR-0021 Open Item O1 asks the founder whether the Objective
        # vocabulary needs a seventh `CANCELLED` state. It is not needed
        # here and this deliberately does not pre-empt that decision --
        # nothing in this branch creates an Objective to put in one.)
        if pending is not None:
            reply = (
                f"Alright, I've dropped that. Nothing is waiting on you.\n\n"
                f"(I was asking about: {pending.objective})"
            )
        else:
            reply = "Nothing was waiting, so there's nothing to stop."
        status.message = reply
        return _founder_reply(status, reply, interaction_type="cancelled")

    if role is UtteranceRole.FOLLOW_UP:
        # A question, not an instruction and not field data. Two shapes,
        # and neither may consume the open question as an answer.
        if pending is not None:
            # They asked about the question itself. Answer that, and put
            # the question back exactly as it was -- `begin()` cleared it
            # a moment ago, and losing it here would abandon the founder's
            # own request because they asked us why we were asking.
            status.status = AWAITING_CLARIFICATION
            status.objective = pending.objective
            status.pending_clarification = pending
            reply = (
                f"Because I can't start \"{pending.objective}\" until I know "
                f"one more thing.\n\n{pending.question}"
            )
            status.message = reply
            return _founder_reply(status, reply,
                                  interaction_type="clarification_question")
        # A question about what just happened. The Reporter is the layer
        # that explains a mission from its record and Evidence, so it
        # answers here rather than this surface composing a second account
        # -- and when there is no record it says so plainly instead of
        # inventing mission work out of a question.
        # A question about the last mission may be answerable from what
        # was RECORDED -- why a capability was chosen, whether the work
        # satisfied the request. Those are projections of the plan and
        # its Evidence, and reading them needs no provider and cannot
        # invent a reason after the fact.
        grounded = _grounded_answer(
            mission_service, text, previous_objective_id
        )
        told = grounded or _mission_report(mission_service, previous_objective_id)
        reply = told or "Nothing has run yet, so there's nothing to report on."
        status.message = reply
        return _founder_reply(status, reply, interaction_type="follow_up")

    if role is UtteranceRole.INFORMATIONAL_QUESTION and pending is None:
        # A question with nothing behind it. It used to be answered from
        # the mission record -- "Nothing has run yet, so there's nothing
        # to report on" -- which is a true sentence about the wrong
        # question, delivered in three milliseconds without reaching a
        # Planner, a Broker or any reasoning at all.
        #
        # Thinking is work. `Reasoning.Transform` is the capability for
        # it, so this becomes an ordinary objective naming that
        # capability, planned deterministically, executed by the Reasoning
        # Executive, and verified by `TextVerifier` like any other
        # generated text. Nothing new is built and nothing is bypassed:
        # this line chooses which Intent to ask for, and every layer below
        # behaves exactly as it always has.
        #
        # `pending is None` because a question asked while a clarification
        # is open is a question ABOUT that clarification -- the branch
        # above already answers it, and that referent is real.
        grounded = _grounded_answer(
            mission_service, text, previous_objective_id
        )
        if grounded:
            # Answered from what this machine already knows. No mission is
            # created to read facts Shared Infrastructure already holds.
            status.status = COMPLETED
            status.message = grounded
            return _founder_reply(
                status, grounded, interaction_type="follow_up"
            )
        intent_result = mission_service.intent_layer.answer_question(text)
    elif role is UtteranceRole.MODIFY_OR_REDIRECT and pending is not None:
        # The founder changed what they want while a question was open.
        # The old question yields -- `begin()` already cleared it -- and
        # the new sentence is parsed as what it is, a fresh objective,
        # rather than being fed to `clarify()` as the answer to a question
        # about something else. Falling through with `pending` dropped is
        # exactly that.
        logging.info(
            "founder redirected while a clarification was open; abandoning %r",
            pending.objective,
        )
        pending = None

    # NOTE: the capability-question shortcut that used to sit here is
    # gone. It was a phrase list consulted by this composition root
    # *before* the Conversation Engine was ever asked, which put the
    # routing decision in the wrong layer and matched by contiguous
    # substring -- so "what are your capabilities" was recognised while
    # "what are your *current* capabilities" fell through to the Planner,
    # which cannot plan a question and refused it. Capability inquiries
    # are now `Intent.CAPABILITY_QUERY` in the Conversation Engine's own
    # taxonomy and never reach this function at all.

    # ADR-0024 Decision 1 -- the admission boundary. Understanding happens
    # BEFORE a mission exists, not inside it.
    #
    # This used to read `mission_service.start(text)`, which parsed intent
    # *inside* the mission: an under-specified request became a mission,
    # was refused, and the question came back wrapped in a `PlanRefusal`
    # for this function to unwrap -- a question travelling as a planning
    # failure, which is exactly the collapse ADR-0024 Decision 10 forbids.
    # ADR-0024 §10 requires that a clarification-required Intent reach
    # neither MissionService nor the Planner. Asking first is how.
    #
    # This root still decides nothing. `IntentLayer` decides whether the
    # request is understood, and it is `mission_service`'s OWN instance --
    # there is one Intent Layer in this process, not a second one wired
    # up here.
    # A question was asked last turn AND the Brain read this message as its
    # answer -- both, now, where this used to assume the second from the
    # first.
    #
    # The founder's words are clarification DATA, not a new objective:
    # "Research" is not a mission, it is the name of the folder they
    # already asked for. `clarify()` re-parses their ORIGINAL sentence
    # with the answer supplied against the question's own `key`, so
    # everything they already said survives and only the missing field
    # comes from the answer.
    #
    # Which messages can be an answer is decided upstream and is not a
    # judgement made here: the Conversation Engine runs first, so a
    # greeting or a capability question is HANDLED and never reaches this
    # function at all. Only input the engine escalates -- input it takes
    # to be work -- can land on an open question, and `role_of()` above
    # has already separated an answer from a refusal, a question back, and
    # a change of subject.
    #
    # STATED LIMIT (narrowed, not removed): a value genuinely
    # indistinguishable from a refusal -- a folder the founder really
    # wants called `nothing` -- is still read as a refusal when the open
    # question offered no `options`. That is the residual case; it is
    # asserted in `tests/test_utterance_role.py` rather than left to be
    # rediscovered, and populating `options` removes it wherever a
    # producer can enumerate the choices.
    if intent_result is not None:
        # Already decided above: the founder asked a question and the
        # Intent Layer built the Intent that answers it.
        pass
    elif pending is not None:
        intent_result = mission_service.intent_layer.clarify(
            pending.objective,
            text,
            ClarificationQuestion(
                question=pending.question,
                key=pending.key,
                options=tuple(pending.options),
                required=pending.required,
            ),
            # What the founder resolved in EARLIER rounds. Without it a
            # second question silently discards the first answer: "Create
            # a folder" re-parsed with only `{"location": "Desktop"}` has
            # no name in it, so the founder would be asked for the name
            # they had already given.
            supplied=dict(getattr(pending, "supplied", {}) or {}),
            # The founder's own words for what earlier turns settled.
            # Carried for the same reason the values are: a requirement
            # built from a value with no evidence behind it can only
            # compare the interpretation with itself.
            evidence=dict(getattr(pending, "evidence", {}) or {}),
        )
        # The objective under way is still the founder's ORIGINAL request.
        # Reporting the answer as the objective would lose what they asked
        # for and leave "Research" standing where "Create a folder" should.
        status.objective = pending.objective
    else:
        intent_result = mission_service.intent_layer.parse(text)

    if intent_result.needs_clarification:
        # Clarification is not refusal, and it is not failure. The founder
        # is asked, verbatim, so they can answer and the request proceeds.
        #
        # The objective is NOT completed here. It used to be marked
        # COMPLETED the moment the question was successfully displayed,
        # which told the founder their request had finished when it had
        # not started -- and left nothing pending, so their answer arrived
        # as a brand-new mission. It stays AWAITING_CLARIFICATION, with
        # everything needed to resume it, until they answer.
        question = intent_result.clarification
        objective = pending.objective if pending is not None else text
        status.status = AWAITING_CLARIFICATION
        status.objective = objective
        status.message = question.question
        # Carry every answer so far, plus the one just given, into the
        # next question. This is the same logical Intent being resolved
        # field by field -- the objective and the clarification thread are
        # unchanged -- not a new objective built out of replies.
        # What the Intent Layer actually UNDERSTOOD, carried forward --
        # not what the founder typed.
        #
        # This used to read `resolved[pending.key] = text`, which threw
        # the understanding away between turns: `clarify()` could resolve
        # "on my desktop" to `desktop`, and the next round was handed the
        # sentence again. Canonical values in, canonical values out.
        resolved: dict[str, str] = dict(getattr(pending, "supplied", {}) or {}) if pending else {}
        resolved.update(getattr(intent_result, "resolved", None) or {})
        if pending is not None and pending.key and pending.key not in resolved:
            resolved[pending.key] = text
        spoken: dict[str, Any] = dict(getattr(pending, "evidence", {}) or {}) if pending else {}
        spoken.update(getattr(intent_result, "evidence", None) or {})
        status.pending_clarification = PendingClarification(
            question=question.question,
            key=question.key,
            objective=objective,
            options=tuple(question.options),
            required=question.required,
            supplied=resolved,
            evidence=spoken,
        )
        return _founder_reply(status, question.question,
                              interaction_type="clarification_question")

    if intent_result.intent is None:
        status.status = FAILED
        status.message = _founder_refusal_sentence("the intent layer produced no intent")
        return _founder_reply(status, status.message)

    # A canonical, already-understood Intent -- goal, constraints, context,
    # success criteria, and the agency the founder expressed. MissionService
    # admits it without reinterpreting a word of it.
    outcome = mission_service.start(intent_result.intent)
    # What the founder chose, and what the mission actually needed. Read
    # from the outcome rather than re-derived: the Planner decided it.
    status.selected_mode = getattr(outcome, "selected_mode", "") or ""
    status.effective_mode = getattr(outcome, "effective_mode", "") or ""
    status.mode_reason = getattr(outcome, "mode_reason", "") or ""
    refusal = outcome.refusal

    # Not executable is not not-understood. `NO_STEPS` is the Planner's
    # own verdict, under `prompting.py` rule 6, that a provider looked at
    # the whole capability catalogue and honestly reported that nothing
    # in it achieves this goal. The goal was parsed, resolved and planned
    # against; what is missing is a plan.
    #
    # This used to ask `brain/advisory.py::advise()` what to say and then
    # record the turn as COMPLETED. Both halves were wrong, and the live
    # CV mission showed exactly how wrong: the founder was told "I am
    # taking full responsibility for evaluating all your resume files...
    # Shall I start cataloging those files now?" over a mission that had
    # no plan, no tasks, and nothing waiting on an answer. Nothing was
    # cataloguing anything, and there was no resumable work behind the
    # question.
    #
    # An unconstrained reasoner asked "what should I say about this
    # request?" will propose a next action, because that is what the
    # question invites. It cannot promise otherwise, so it is not asked.
    # The sentence is composed from what the Planner actually reported.
    #
    # `FAILED` rather than `COMPLETED`: this attempt did not succeed and
    # nothing is pending. Not `AWAITING_APPROVAL` -- no action is waiting
    # for a yes; not `AWAITING_CLARIFICATION` -- clarification is for a
    # fact only the founder holds, and "no plan could be built" is not a
    # missing fact about the founder. `FAILED` is already what the
    # refusal path immediately below uses, and it is terminal, which is
    # the honest shape of this outcome.
    if refusal is not None and getattr(refusal, "code", None) == NO_STEPS:
        logging.warning("objective not planable: %s", getattr(refusal, "reason", ""))
        status.status = FAILED
        status.message = _founder_no_plan_sentence(refusal)
        status.errors.append(getattr(refusal, "reason", "") or NO_STEPS)
        return _founder_reply(
            status, status.message, interaction_type="mission_result",
        )

    if not outcome.accepted:
        reason = (
            outcome.refusal.reason if outcome.refusal is not None
            else "; ".join(outcome.reasons) or "the plan could not be accepted"
        )
        # A refusal never becomes an Objective, so no Task/Event trail
        # exists for `status` to derive this from — the one fact this
        # function reports onto `status` directly rather than through the
        # bus, because there is no Task 2.5 event that would ever say it.
        status.status = FAILED
        # `reason` is the developer-facing diagnostic and stays intact on
        # `status.errors` (and in the Planner's own refusal object, and in
        # whatever Memory already recorded). Only the sentence the founder
        # reads is rewritten — a founder should never be shown "HTTP 503"
        # or a provider's internal prose.
        logging.warning("objective refused: %s", reason)
        status.message = _founder_refusal_sentence(reason)
        status.errors.append(reason)
        return _founder_reply(status, status.message)

    objective_id = outcome.objective_id
    # Every mission record this one objective produced. A replan makes a
    # new record; what the previous one established is still the
    # founder's, and still true.
    attempts_made = [objective_id]
    _drive_until_settled(runtime, mission_control, status, objective_id,
                         timeout_seconds)

    # A method that failed is not an objective that failed.
    #
    # The founder was told "That didn't complete." about a mission whose
    # very first step could not open a browser -- nine planned steps,
    # naming several different sources, never ran. Mission Control was
    # right to stop; nothing was there to decide what the stop MEANT.
    #
    # The surface does not decide it here either. It asks the Brain and
    # relays the answer to the admission boundary that already exists,
    # bounded by the Brain's own budget.
    attempts = 0
    while True:
        state = mission_control.founder_state(objective_id)

        # What the mission has actually established, judged before
        # deciding whether to go round again. Both diagnoses below need
        # it, and it is the same judgement the founder is shown.
        decided = _decide(
            mission_service, mission_control, intent_result.intent, attempts_made
        )
        # WHAT THE MISSION HAS ACTUALLY ACHIEVED, and it is the thing
        # that decides whether more research is even a coherent idea.
        #
        # More research exists to close a requirement nobody has closed.
        # If every requirement is satisfied, there is nothing to close,
        # and asking for more is not diligence -- it is a mission that
        # cannot tell it has finished.
        #
        # Measured, and it was a real regression of mine. "Think of three
        # names and write them into a file" ran THREE TIMES:
        #
        #   attempt 1 (insufficient evidence):
        #       satisfied=['req_1','req_2','req_3','req_4'] unresolved=[]
        #
        # Every requirement satisfied, nothing unresolved, nothing
        # failed -- and it replanned twice anyway, because a deliberation
        # over an objective that poses no decision extracted no
        # candidates, and "no candidates" is read as "every criterion is
        # still open". Each pass generated different names and rewrote
        # the founder's file, so what the founder was told had been
        # verified was the FIRST run's text and what sat on their disk
        # was the THIRD's.
        standing = _mission_progress(
            mission_control, intent_result.intent, objective_id
        )
        needed = (
            _evidence_question(decided, _unvisited_links(mission_control, attempts_made))
            if decided is not None
            and decided.more_research
            and standing is not None
            and standing.unresolved
            else None
        )

        # TWO DIAGNOSES, and they are not the same thing.
        #
        # A failed step means the METHOD did not work. Insufficient
        # evidence means every step worked and the answer still is not
        # supported -- fixture D's first cycle exactly: one source read
        # cleanly, Evidence valid, no execution failure anywhere, and a
        # criterion nobody could establish from it.
        #
        # Both may replan. Recording them as the same would tell a
        # founder their mission failed when nothing failed, and would
        # send the Planner looking for a broken route that does not
        # exist.
        if state.errors:
            decision = _recovery_decision(
                mission_control, intent_result.intent, objective_id, attempts
            )
            if decision is None or not decision.should_replan:
                if decision is not None:
                    logging.info(
                        "recovery declined (%s): %s",
                        decision.failure_class, decision.reason,
                    )
                break
            status.recovery = decision.as_dict()
            reason = f"recovery ({decision.failure_class})"
        elif needed is not None and attempts < _RESEARCH_BUDGET:
            # Execution succeeded. The objective did not.
            logging.info(
                "insufficient evidence; unresolved criteria: %s",
                needed["unresolved_criteria"],
            )
            reason = "insufficient evidence"
        else:
            break

        attempts += 1

        # What the first attempt learned, carried into the second.
        #
        # An earlier version re-submitted the SAME intent and made things
        # worse: the new plan opened a browser session the failed attempt
        # still held, and the mission died on `session already open`. The
        # rule `recovery_for` states -- a new attempt must differ
        # materially in source, method, capability, environment, evidence
        # question or strategy -- was being relayed and then violated.
        #
        # What differs now is knowledge, not identity. Same Intent, same
        # requirement ids, same founder evidence; the Planner is
        # additionally told which routes were already tried and which
        # requirements are already satisfied, so it can plan around both.
        # The environment is released first, so the second attempt does
        # not inherit the first one's leftovers.
        before = _mission_progress(
            mission_control, intent_result.intent, objective_id
        )
        if before is None:
            break
        logging.info(
            "attempt %s (%s): satisfied=%s unresolved=%s failed=%s",
            attempts, reason, list(before.satisfied),
            list(before.unresolved), list(before.failed_routes),
        )
        _release_task_browsers()
        intent_result.intent.context["recovery"] = before.as_dict()
        if needed is not None:
            # What to go and find, rather than "look again".
            intent_result.intent.context["evidence_needed"] = needed
        else:
            intent_result.intent.context.pop("evidence_needed", None)

        retried = mission_service.start(intent_result.intent)
        if not retried.accepted:
            break
        objective_id = retried.objective_id
        attempts_made.append(objective_id)
        _drive_until_settled(runtime, mission_control, status, objective_id,
                             timeout_seconds)

        # Did that change anything that matters?
        after = _mission_progress(
            mission_control, intent_result.intent, objective_id
        )
        if after is None:
            break
        if no_useful_progress(before, after):
            # Same requirement standing, no new Evidence, no route
            # eliminated. Going round again here would be a loop wearing
            # the costume of persistence, and the founder would wait
            # through every lap of it.
            logging.info(
                "no useful progress on attempt %s; changing nothing further",
                attempts,
            )
            break

    state = mission_control.founder_state(objective_id)

    # The mission is over one way or another. Whatever it opened and did
    # not close is nobody's now.
    _release_task_browsers()

    # The decision this mission was framed for, before the branch below.
    #
    # It used to run only on the success path, which threw away the most
    # useful half of a research mission: one that reached three sources,
    # learned something real from two of them and then failed a fourth
    # step told the founder "That didn't complete" and nothing else. What
    # was actually established is still true, and still theirs.
    decided = _decide(
        mission_service, mission_control, intent_result.intent, attempts_made
    )
    if decided is not None:
        status.deliberation = decided.as_dict()
        logging.info(
            "deliberation: %s (%s shortlisted, %s rejected)",
            decided.state, len(decided.shortlist), len(decided.rejected),
        )
    # A DECISION IS ONLY NEWS WHEN THE OBJECTIVE POSED ONE.
    #
    # "Think of three names and write them into a file" poses no
    # decision: it names what it wants and every requirement was
    # satisfied. A deliberation still ran over its Evidence, found
    # nothing it recognised as a candidate, and the founder was told
    #
    #     I could not confirm anything that meets all of it.
    #
    # about work that had entirely succeeded. An empty shortlist over a
    # mission with nothing unresolved is not a finding -- it is the Brain
    # answering a question nobody asked, and repeating it to the founder
    # is how a working product sounds broken.
    #
    # A research mission that genuinely found nothing still says so:
    # there, a requirement IS unresolved, which is exactly the
    # difference.
    final_standing = _mission_progress(
        mission_control, intent_result.intent, objective_id
    )
    decision_text = (
        ""
        if (
            decided is not None
            and not decided.shortlist
            and final_standing is not None
            and not final_standing.unresolved
        )
        else _decision_sentence(decided)
    )

    if state.errors:
        # Same hygiene as the refusal branch above: the founder gets a
        # sentence, the full executive/Playwright/gateway diagnostic stays
        # in the log and on `status.errors` where a developer will look.
        joined = "; ".join(state.errors)
        logging.warning("objective failed: %s", joined)
        status.message = _founder_failure_sentence(joined)
        if decision_text:
            # What the mission DID establish, before what stopped it.
            # A founder who asked for research and got two verified
            # answers out of four is owed the two.
            #
            # And when the question was actually ANSWERED, "that didn't
            # complete" is not the truth about it. The demo centrepiece
            # ended with a decided shortlist -- every criterion cleared
            # against Evidence, two candidates rejected with reasons --
            # and then told the founder the work did not complete,
            # because a route it had already recovered from had failed
            # earlier in the mission. Both halves are facts; only one of
            # them is the outcome. Saying the objective failed when it
            # was answered is as untrue as the reverse, and the reverse
            # is what this whole system is built against.
            answered = decided is not None and bool(decided.shortlist)
            status.message = f"{decision_text}\n\n" + (
                "Some of what I tried along the way didn't work, and I've "
                "kept the details."
                if answered else status.message
            )
        return _founder_reply(status, status.message)
    if state.progress >= 1.0:
        # `state.result` is still recorded -- other consumers legitimately
        # want the last Task result -- but it is no longer what the founder
        # is told the MISSION did.
        status.result = state.result
        report = _mission_report(mission_service, status.objective_id) or (
            "The work finished, but I can't reconstruct a verified mission summary."
        )
        # If the founder ASKED for a value, tell them the value. The
        # verification summary follows it rather than replacing it.
        #
        # This is the last joint in the chain and the one that used to
        # drop the answer on the floor: a browser workflow that observed
        # `#state` as `accepted`, verified it against a fresh
        # observation, and then told the founder "Work finished. 4 of 6
        # steps were independently verified." True, and not what they
        # asked. `state.answer` is present only when a Step named the
        # field and Verification actually observed it, so this cannot
        # invent an answer for a mission that produced none -- and it is
        # a deterministic projection of canonical Evidence, never
        # something composed.
        answer = getattr(state, "answer", None)

        status.message = (
            _ANSWER_THEN_SUMMARY.format(answer=answer, report=report)
            if answer is not None
            else report
        )
        if decision_text:
            status.message = f"{decision_text}\n\n{status.message}"
        return _founder_reply(status, status.message)
    # Waiting on the founder is not slowness. `AWAITING_APPROVAL` means
    # the plan is ready and held at the permission boundary until a human
    # decides -- saying "taking longer than expected" would describe the
    # system as struggling when it is in fact waiting for its founder.
    if status.status == AWAITING_APPROVAL:
        status.message = "This needs your approval before I go ahead."
        return _founder_reply(status, status.message)
    # Finished, verified, and held for the founder's confirmation. This had
    # no branch, so it fell to the sentence below and told a founder whose
    # folder already existed on disk that the system was struggling. A
    # mission waiting on a human is not a slow mission -- the same
    # distinction the approval branch above already draws.
    #
    # The Reporter says what happened; this surface says what the founder
    # is being asked to do next. That split is why the prompt is appended
    # here rather than moved into the Brain.
    #
    # The comment that used to sit here claimed "Verification has already
    # compared it against the Step's expected outcome by the time this
    # event fires". It had not -- every gateway returned no Evidence at
    # all -- and that belief is how Onkar was told "Done" for an empty
    # folder. The sentence now comes from the mission record and the
    # Evidence that actually exists, including when that Evidence is
    # missing.
    if status.requires_founder_completion or status.status == AWAITING_FOUNDER_COMPLETION:
        done = _mission_report(mission_service, status.objective_id)
        status.message = (
            f"{done} Ready for your review." if done
            else "The work finished, but I can't reconstruct a verified "
                 "mission summary. Ready for your review."
        )
        return _founder_reply(status, status.message)
    status.message = "That's taking longer than expected; still working on it."
    return _founder_reply(status, status.message)


#: Founder-facing sentences for the refusal kinds a founder can actually
#: act on. Matched against the *developer* diagnostic, which stays intact
#: everywhere else — this is presentation, not a second classification of
#: what went wrong (the Planner/Broker already decided that).
_BUSY_MARKERS = (
    "http 503", "http 429", "http 500", "http 502", "http 504",
    "high demand", "overloaded", "rate limit", "quota", "resource exhausted",
    "unavailable", "temporarily",
)
_OFFLINE_MARKERS = (
    "could not reach", "connection", "getaddrinfo", "network is unreachable",
    "name or service not known", "no route to host",
)
_TIMEOUT_MARKERS = ("no answer within", "timed out", "timeout")
_NO_KEY_MARKERS = ("no gemini_api_key", "api key not valid", "http 401", "http 403")


def _founder_no_plan_sentence(refusal) -> str:
    """What the founder is told when no executable plan could be built.

    Deterministic, and composed only from what the Planner reported --
    which is the point. The alternative, asking a reasoner what to say
    about the request, produced an operational commitment ("I am going to
    catalog your local resume files... Shall I start?") over a mission
    that had no plan and nothing waiting to run.

    So this states the two facts that are true and stops: the request was
    understood, and no plan could be built for it. It never says work is
    starting, queued, or awaiting a yes, because none of those is the
    case.

    `detail` is surfaced only when the Planner supplied something a
    founder can act on. `reason` stays out of the sentence entirely and
    remains on `ExecutionStatus.errors` for whoever is debugging -- it is
    developer prose ("no plan: the available capabilities cannot achieve
    this objective") and reads as a rejection of the founder rather than a
    statement about the machine.
    """
    sentence = (
        "I understood what you asked for, but I couldn't put together an "
        "executable plan for it with the capabilities I have right now. "
        "Nothing has been started."
    )
    known = tuple(getattr(refusal, "known_capabilities", ()) or ())
    if known:
        # Only ever a count. Naming twenty-seven capability identifiers at
        # a founder is the same overreach as showing them a stack trace.
        sentence += f" I checked all {len(known)} of the things I can do."
    return sentence


def _founder_refusal_sentence(reason: str) -> str:
    """One clean sentence for the founder, from the developer diagnostic.

    Never returns the raw text: a founder reading "HTTP 503: This model is
    currently experiencing high demand" learns nothing they can act on and
    everything about our plumbing. The full `reason` is logged and kept on
    `ExecutionStatus.errors` for whoever is debugging.
    """
    lowered = (reason or "").lower()
    if any(marker in lowered for marker in _NO_KEY_MARKERS):
        return (
            "I can't reach my reasoning service — its access key looks "
            "missing or invalid."
        )
    if any(marker in lowered for marker in _TIMEOUT_MARKERS):
        return "My reasoning service took too long to answer. Please try again."
    if any(marker in lowered for marker in _BUSY_MARKERS):
        return (
            "My reasoning service is temporarily busy. Please try again in "
            "a moment."
        )
    if any(marker in lowered for marker in _OFFLINE_MARKERS):
        return "I can't reach my reasoning service right now — please check the connection."
    if "nothing is registered" in lowered:
        return "I don't have any capabilities wired up to do that yet."
    if "cannot achieve this objective" in lowered or "not executable" in lowered:
        return "I can't do that with what I'm currently able to do."
    # Anything unrecognised: still never the raw text.
    return "I couldn't plan that just now. Please try again."


#: Founder-level domains, keyed by the executive that provides them. This
#: is the translation layer between the Operator's registry and what the
#: founder is actually told: the *keys* are checked against live
#: registrations (so this never claims a capability that is not wired),
#: while the *values* deliberately name no execution primitive. Adding an
#: executive without adding it here degrades honestly — see
#: `_describe_capabilities`'s handling of unknown executives.
#: Noun phrases, not sentences: the composer says "I can work with
#: {domains}", so each value has to slot into that grammatically.
#: A founder-facing sentence per registered executive.
#:
#: `filesystem` was missing, and the omission was silent: `_capability_
#: domains()` filters the live registry through this table, so an
#: executive with no entry simply does not exist as far as the founder is
#: concerned. Asked "tell me what capabilities you currently have",
#: Kalpavriksha answered browser and desktop and never mentioned files or
#: folders -- while fourteen `Filesystem.*` capabilities were registered,
#: including the one thing it does deterministically, every time, with no
#: provider involved at all.
#:
#: An incomplete self-report is an untrue one. `test_capability_self_
#: knowledge.py` now asserts every registered executive has an entry
#: here, so the next one to be registered cannot vanish the same way.
_EXECUTIVE_DOMAINS: dict[str, str] = {
    "browser": "your browser — opening pages, reading what is there, and acting on them",
    "desktop": "your desktop — opening your applications, reading what is on screen, and operating them",
    "filesystem": "your files and folders — creating, reading, renaming, moving and organising them",
    # `document` and `reasoning` are registered executives the founder was
    # never told about: the map omitted them, so asking "what can you do"
    # answered with three domains while five were wired.
    #
    # Omission is the right default -- the docstring below is explicit that
    # inventing words for an executive is worse than leaving it out -- but
    # these two have plain, truthful domains rather than missing ones.
    # `Document.ExtractText`/`WriteDocument` and `Reasoning.Transform` are
    # what each actually registers, described here at founder level rather
    # than by their verbs.
    "document": "documents — reading what is inside a PDF or Word file, and writing new ones",
    "reasoning": "thinking a piece of work through — reading something and turning it into what you asked for",
}


def _capability_domains(mission_control) -> list[str]:
    """The founder-level DOMAINS this machine can act in, read from the
    live capability registry Mission Control holds.

    This is the Brain/Operator translation boundary. It returns domains
    rather than a finished sentence on purpose: composing the founder's
    words belongs to the Conversation Engine
    (`ResponseComposer.capabilities`), while knowing which executives are
    registered belongs to Mission Control. This function is the only one
    that sees both, and it is *injected* into the engine as
    `capability_domains`, so the Brain never reaches into the Operator
    side itself.

    It replaces `_describe_capabilities`, which rendered every capability
    *verb* in the registry -- "browser.click, navigate, press key, type
    text, execute command, find target, focus window, launch
    application, ..." -- directly into the founder's answer. That was the
    Operator's execution vocabulary reaching the Founder Surface
    unmediated, which the Brain/Operator separation exists to prevent.

    Still not hardcoded: registering or removing an executive changes the
    result, because the registry is read at call time. An executive with
    no founder-facing description is omitted rather than described --
    inventing words for it would be worse than leaving it out.
    """
    try:
        descriptors = list(mission_control.capabilities.all())
    except Exception:  # noqa: BLE001 — an unreadable registry is an honest absence
        return []
    executives = sorted({str(d.executive_id) for d in descriptors})
    return [_EXECUTIVE_DOMAINS[e] for e in executives if e in _EXECUTIVE_DOMAINS]


#: A capability reporting a place it does not know, and the places it
#: does. Matched rather than reproduced -- see `_founder_failure_sentence`.
_UNKNOWN_PLACE = _re.compile(r"unknown location '([^']*)'[^(]*\(known:\s*([^)]*)\)")


def _founder_failure_sentence(errors: str) -> str:
    """The execution-side counterpart to `_founder_refusal_sentence` — a
    task that was planned, ran, and did not finish. Same rule: the founder
    reads a sentence, never a stack trace, a Playwright call log, or a
    filesystem path."""
    lowered = (errors or "").lower()
    if "executable doesn't exist" in lowered or "playwright install" in lowered:
        return "I couldn't start the browser on this machine."
    if "approval" in lowered:
        return "I stopped because that needs your approval first."
    if any(marker in lowered for marker in _TIMEOUT_MARKERS):
        return "That took too long to finish, so I stopped."
    if any(marker in lowered for marker in _BUSY_MARKERS):
        return "A service I needed was temporarily busy, so that didn't finish."

    # A place the machine does not recognise. The founder can fix this in
    # one word, and only if they are told which words work -- so the
    # capability's own list is repeated back rather than swallowed.
    #
    # Read out of the error rather than written here on purpose. A second
    # copy of "Desktop, Documents, Downloads" in the surface is a
    # vocabulary that drifts from the one that actually decides, and the
    # founder would eventually be offered a place that no longer exists.
    place = _UNKNOWN_PLACE.search(errors or "")
    if place:
        known = ", ".join(
            word.strip().replace("_", " ") for word in place.group(2).split(",")
        )
        return (
            f"I don't know where \"{place.group(1)}\" is. "
            f"I can use: {known}."
        )

    return "That didn't complete. I've kept the details for review."


#: The answer the founder asked for, then how far it was verified.
#:
#: Two facts, in the order a founder wants them: what the machine found,
#: and how much of the work stands on independent observation. Neither
#: replaces the other -- an answer with no verification summary hides how
#: it was established, and a verification summary with no answer is what
#: this codebase shipped, and it left "tell me the text shown by #state"
#: answered with "4 of 6 steps were independently verified".
_ANSWER_THEN_SUMMARY = """{answer}

{report}"""


def _describe_result(result, objective: str = "") -> str:
    """One sentence a founder can read about the MISSION -- never a raw
    implementation step.

    This is handed `FounderState.result`, which is `_last_result()`: the
    output of the LAST task. For a one-step mission that is the mission's
    own result and reads correctly -- a folder mission's last output is
    the path, which is exactly what Onkar wanted to know. Every packaged
    mission until the first AI-planned one was single-step, so the
    conflation never showed.

    The first five-step plan ended in `Browser.CloseBrowserSession`, and
    Onkar was shown its raw output -- rendered by the page as
    `[object Object]` -- for a mission that had genuinely researched the
    printing press and written the file. The work succeeded; the sentence
    describing it came from the cleanup step.

    A step's output is not a mission result. So a structure that is
    plainly implementation detail is no longer stringified at the founder:
    the mission is described by what Onkar asked for, which is the one
    thing about it that is certainly true. A plain string is still spoken
    as-is, because that is the single-step case where the step output IS
    the mission's answer.

    Deliberately still no invention. This function has no authority to
    summarise, and does not acquire it here -- it only stops repeating
    something meaningless. Naming the artifact a multi-step mission
    produced needs evidence the surface is not currently given; that is a
    follow-up, not a place to guess.
    """
    if isinstance(result, dict) and "title" in result and "url" in result:
        return f"Done — the page at {result['url']} loaded with title \"{result['title']}\"."
    if isinstance(result, (dict, list, tuple, set, bytes)):
        return f"Done — {objective}." if objective else "Done."
    text = str(result).strip() if result is not None else ""
    if not text:
        return f"Done — {objective}." if objective else "Done."
    return text


def _self_check() -> int:
    """What this build actually assembled — printed, then exit.

    A packaged application can differ from its source in exactly the ways
    that matter here: a module the bundler did not collect, an asset path
    that only resolves in a checkout, an environment the frozen process
    does not inherit. "It launched" does not answer any of those, and the
    Founder Surface is a native window, so there is nowhere for an
    operator to read the answer from outside.

    So the build reports on itself. This constructs the real production
    composition — the same `_build_mission_pipeline()` a launch uses — and
    prints what came back. Nothing is mocked and nothing is inferred from
    the source tree; if a capability is missing from the package it is
    missing from this output too.

    No window opens, no application is launched, no machine scan runs and
    no prompt is sent anywhere.

    **One network read does happen**, and saying otherwise would be the
    kind of comfortable inaccuracy this whole output exists to avoid: when
    a gateway credential is configured, the composition asks that gateway
    what the configured model currently costs, because the Broker ranks on
    economics and a price nobody has read is not evidence. It is one
    unauthenticated GET for public metadata, it carries no prompt, and a
    failure is not fatal -- see `_observe_openrouter_economics`.
    """
    import sys

    frozen = getattr(sys, "frozen", False)
    print(f"Kalpavriksha Founder Edition — self check")
    print(f"  packaged: {bool(frozen)}")
    print(f"  running from: {_bundled_dir('web')}")

    pipeline = _build_mission_pipeline()
    if pipeline is None:
        print("  FAIL: no mission pipeline was assembled")
        return 1

    (mission_service, runtime, mission_control, _status, runner,
     _set_mode, _interactions, decide_approval) = pipeline

    capabilities = list(mission_control.capabilities.all())
    executives = sorted({str(c.executive_id) for c in capabilities})
    reachable = sorted(runtime._gateways)
    unreachable = sorted(set(executives) - set(reachable))

    print(f"  capabilities registered: {len(capabilities)}")
    print(f"  executives:              {', '.join(executives)}")
    print(f"  runtime-reachable:       {', '.join(reachable)}")

    tiers = getattr(runner, "_tiers", ())
    for name, ids in tiers:
        print(f"  reasoning tier {name:<9} {', '.join(sorted(ids)) or '(empty)'}")

    print(f"  approval wired:          {callable(decide_approval)}")

    # ---- what this build knows, what it can call, and on what evidence --
    #
    # A tier list says which ids the ladder would try. It does not say
    # whether an id is merely KNOWN, whether this deployment CONFIGURED
    # it, whether anything is actually EXECUTABLE behind it, or what the
    # economic claim attached to it is standing on -- and those four
    # became different questions in U1. A packaged build is exactly where
    # they cannot be answered by reading the source, so they are printed.
    print("  provider facts:")
    executor = runner._executor
    executable_ids = {p.provider_id for p in executor._providers.all_plugins()}
    configured_ids = set(_configured_cloud_providers())
    source = executor._service.providers
    profiles = {p.provider_id: p for p in source.profiles()}
    registry = source.registry

    for record in sorted(registry.all() if registry else (),
                         key=lambda d: d.provider_id):
        pid = record.provider_id
        profile = profiles.get(pid)
        verified = record.economic_verified_at
        economics = (
            f"{record.economic_class.value} @ {record.cost_per_call:g}"
            + (f", read {verified.isoformat(timespec='seconds')}"
               if verified else ", NOT currently verified")
        )
        print(
            f"    {pid:<22} known=yes"
            f" configured={'yes' if pid in configured_ids else 'n/a'}"
            f" executable={'yes' if pid in executable_ids else 'no'}"
            f" available={'yes' if profile and profile.available else 'no'}"
        )
        print(f"    {'':<22} economics: {economics}")

    # No Ollama, stated as an observation rather than a promise: if it
    # were ever constructed it would be in the executable set.
    print(f"  no-ollama:               constructed="
          f"{'yes' if 'ollama.local' in executable_ids else 'no'}"
          f", candidate="
          f"{'yes' if 'ollama.local' in set(getattr(runner, '_configured_ids', ())) else 'no'}")

    # Deterministic planning, proven rather than assumed: a fully dictated
    # objective must compile without any provider being reachable.
    from master_agent.planner.direct import direct_plan
    from master_agent.planner.plan import Intent

    dictated = (
        "Create a folder called KV_SelfCheck on the Desktop. Then show me the "
        "text before you write it into notes.txt inside that folder. The text "
        "should be: self check."
    )
    # The Planner's own view of the catalogue, via its own accessor --
    # never a second derivation of what capabilities exist.
    plan = direct_plan(Intent(goal=dictated), mission_service.planner.options())
    steps = [s.capability for s in plan.steps] if plan is not None else []
    checkpoint = bool(plan and any(s.founder_checkpoint for s in plan.steps))
    print(f"  deterministic planning:  {' -> '.join(steps) or 'FAILED'}")
    print(f"  founder checkpoint:      {checkpoint}")

    problems = []
    if unreachable:
        problems.append(f"executives with no gateway: {', '.join(unreachable)}")
    if len(steps) != 2:
        problems.append("a fully dictated objective did not compile locally")
    if not checkpoint:
        problems.append("the founder's checkpoint was not compiled")
    if not callable(decide_approval):
        problems.append("approval is not wired")

    if problems:
        print("  RESULT: FAIL")
        for problem in problems:
            print(f"    - {problem}")
        return 1
    print("  RESULT: OK")
    return 0


def _default_mode() -> str:
    """LOCAL / AI MODE / BOTH's default, read from the one module that
    owns the vocabulary.

    A function rather than a module-level constant because every import
    in this composition root is deliberately lazy, and a bare
    `DEFAULT_MODE` in `main()` would be read as a global that
    `_build_mission_pipeline`'s own local import never provides -- the
    exact NameError shape `tests/test_founder_approval_path.py` exists to
    catch, which is how this was caught.
    """
    from master_agent.planner.modes import DEFAULT_MODE

    return DEFAULT_MODE


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format='[%(levelname)s] %(name)s: %(message)s')
    parser = argparse.ArgumentParser(prog='kalpavriksha', description='Kalpavriksha Founder Edition')
    parser.add_argument("--founder-name", default=None)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument(
        "--self-check", action="store_true",
        help="Report what this build actually assembled, then exit without "
             "opening a window.",
    )
    args = parser.parse_args(argv)

    # `--debug` opened the WebView's developer tools and did nothing to
    # the log level, so everything the page reports through
    # `DesktopShellApi.debug_log()` -- which logs at INFO -- was discarded
    # by the WARNING default above. Debugging a founder-reported UI defect
    # meant the one channel built for exactly that was silent in the one
    # mode meant to expose it.
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.self_check:
        return _self_check()

    from master_agent.founder_edition.boot import DEFAULT_FOUNDER_NAME
    from master_agent.founder_edition.desktop_shell import create_window

    pipeline = _build_mission_pipeline()
    submit_objective = None
    get_execution_status = None
    confirm_completion = None
    capability_domains = None
    interactions = None
    decide_approval = None
    if pipeline is not None:
        (mission_service, runtime, mission_control, status, _reasoning_runner,
         set_mode, interactions, decide_approval) = pipeline
        submit_objective = lambda text: _submit_objective(  # noqa: E731
            mission_service, runtime, mission_control, status, text,
        )
        # Task 2.5 §8 — the Hyper Agent contract. Read-only: this returns
        # the same `status` object's own `as_dict()`, never a copy that
        # could drift from what actually happened.
        get_execution_status = lambda: status.as_dict()  # noqa: E731
        # Task 2.5 §D — the one action a founder takes to turn a verified
        # objective into a founder-facing completed one. Reuses Mission
        # Control's own `confirm_completion` (mission_control.py); this
        # composition root decides nothing about when that is allowed.
        confirm_completion = lambda completion_id: (  # noqa: E731
            mission_control.confirm_completion(completion_id).as_dict()
        )
        # The Brain's window onto what this machine can actually act on.
        # It hands over founder-level DOMAINS derived from the same live
        # registry the Planner plans against -- never the Operator's own
        # capability verbs, which is the leak `_capability_domains`
        # used to be. Read at call time, so registering or removing an
        # executive changes the answer with no restart.
        capability_domains = lambda: _capability_domains(mission_control)  # noqa: E731

    founder_name = args.founder_name or os.environ.get("KALPAVRIKSHA_FOUNDER_NAME") or DEFAULT_FOUNDER_NAME
    create_window(
        founder_name=founder_name, web_dir=_bundled_dir("web"), debug=args.debug,
        voice_model_path=_voice_model_path(),
        whisper_model=_whisper_model_path(),
        mic_permission_checker=_windows_microphone_allowed,
        open_settings=_open_microphone_settings,
        input_device_resolver=_default_input_device_name,
        output_device_resolver=_default_output_device_name,
        submit_objective=submit_objective,
        get_execution_status=get_execution_status,
        confirm_completion=confirm_completion,
        capability_domains=capability_domains,
        decide_approval=decide_approval,
        set_mode=set_mode,
        default_mode=_default_mode(),
        # See the module-level comment on FixedBottleServer.
        server=FixedBottleServer,
        # The composition root owns the environment; `founder_edition` is
        # guarded against reading it. An automated validation run sets
        # KALPAVRIKSHA_DISABLE_MIC so the harness cannot listen to the
        # room -- unset, which is every founder run, leaves voice intact.
        microphone_enabled=not os.environ.get("KALPAVRIKSHA_DISABLE_MIC"),
        record_interaction=(
            lambda direction, text, **f: getattr(
                interactions.record(direction, text, **f), "interaction_id", None
            )
        ) if interactions is not None else None,
    )
    return 0


def _configured_cloud_providers() -> tuple[str, ...]:
    """Which credentialled services this deployment has actually
    configured, decided from the environment at construction time.

    Generic, and deliberately not a list of names in a branch: a service
    is configured when its credential is present, and that is the same
    question for every one of them. `known != configured` is what this
    function is for -- a descriptor in the canonical registry does not put
    a provider here.
    """
    import os

    from master_agent.providers.openrouter import (
        CREDENTIAL_ENV as OPENROUTER_ENV,
        OPENROUTER_PROVIDER_ID,
    )

    configured: list[str] = []
    if os.environ.get("GEMINI_API_KEY"):
        configured.append("gemini.api")
    if os.environ.get(OPENROUTER_ENV):
        configured.append(OPENROUTER_PROVIDER_ID)
    return tuple(configured)


def _restore_canonical_providers(registry, state_dir) -> tuple[str, ...]:
    """Put last run's canonical descriptors back, before the catalogue is
    imported over the top of them.

    Order is the point. `bootstrap_registry()` refuses to overwrite a
    record whose provenance outranks a declaration -- but it can only
    refuse what is already there, so a DISCOVERED record has to be
    restored FIRST or the declared import silently wins.

    Reads the same snapshot the rest of the system uses, **through the
    same verified loader**. `PersistenceService.load()` already does
    `load_snapshot()` -> `envelope.verify()` -> `migrate()`, and an
    earlier version of this function open-coded two of those three and
    skipped the checksum -- a second loader, weaker than the first, in the
    one place a founder would never look.

    A MISSING snapshot is a legitimate first run and returns nothing.
    A CORRUPT, TAMPERED or UNREADABLE one is a different condition
    entirely, and it is raised, not logged and swallowed: this package's
    whole discipline is that refusing to start beats starting on a lie.
    """
    from master_agent.persistence.service import PersistenceService, restore_providers
    from master_agent.persistence.store import JsonFileStateStore

    envelope = PersistenceService(JsonFileStateStore(state_dir)).load()
    if envelope is None:
        return ()
    return restore_providers(envelope, registry)


#: The OpenRouter model this deployment addresses, as configuration.
#:
#: Live-proven zero-cost and text-only on 2026-08-26, which is a fact
#: about that moment and not a promise. `OpenRouterProvider` revalidates
#: it against OpenRouter's own metadata before every call and refuses if
#: the price or the modality has changed -- this constant says WHICH model
#: this deployment uses, never that it is permanently free.
#:
#: Choosing among models belongs to a later tranche. Until then the choice
#: is written down here where a founder can see and change it, rather than
#: ranked inside a provider adapter.
OPENROUTER_CONFIGURED_MODEL = "minimax/minimax-m3:free"


def _observe_openrouter_economics(provider) -> dict | None:
    """Read what the configured model costs RIGHT NOW, or return None.

    This is the selection-time price check, and it exists because the
    Broker ranks on economics before anything is executed. Without it the
    only price gate was inside the provider, which is the correct place
    for the *execution-time* gate and far too late to keep a ranking
    honest: the Broker would already have preferred a "free" provider on a
    claim nobody had checked.

    `resolve_model()` is reused rather than reimplemented -- it is already
    the thing that asks OpenRouter's own `/api/v1/models` for the
    configured slug and returns it only when both published prices are
    exactly zero and it still emits text only. Calling it here costs one
    unauthenticated GET, warms the same short-lived cache the execution
    path reads, and needs no second notion of what "free" means.

    Returns the evidence -- which model, both prices, and the moment the
    reading was taken -- or None for every way the reading can fail to
    establish zero cost. None is not an error: it is the absence of
    evidence, and the caller must treat it as such rather than as a zero.
    """
    from datetime import UTC, datetime

    try:
        model = provider.resolve_model()
    except Exception as exc:  # noqa: BLE001 - an unreachable gateway is not fatal
        logging.warning("OpenRouter price not observed: %s", exc)
        return None
    observed_at = datetime.now(UTC)
    if model is None:
        return None

    pricing = model.get("pricing") or {}
    try:
        prompt_price = float(pricing.get("prompt", 1))
        completion_price = float(pricing.get("completion", 1))
    except (TypeError, ValueError):
        return None
    if prompt_price != 0.0 or completion_price != 0.0:
        return None

    return {
        "model": str(model.get("id", "")),
        "prompt_price": prompt_price,
        "completion_price": completion_price,
        "observed_at": observed_at,
        "source": "openrouter /api/v1/models",
    }


def _with_observed_economics(descriptor, observation, configured_model: str):
    """The canonical record, with its economics set from an observation
    rather than from a hope.

    Pure and separated from the reading above so the rule can be tested
    without a network: evidence in, descriptor out.

    With evidence, the record says free, and says why: which model, which
    endpoint, and the timestamp of the actual retrieval. Without it, the
    record says UNKNOWN and keeps the declared metered cost -- so a stale
    "free" that arrived from a persisted snapshot cannot quietly become
    today's truth, which is the failure mode this whole function exists
    to close.
    """
    import dataclasses

    from master_agent.broker.registry import EconomicClass

    if observation is None:
        return dataclasses.replace(
            descriptor,
            # Deliberately NOT zero. `ProviderProfile.is_free` is
            # `cost <= 0`, so a cost of zero here would make the Broker
            # treat an unverified provider as free on no evidence at all.
            cost_per_call=max(descriptor.cost_per_call, _OPENROUTER_METERED_COST),
            is_free=False,
            economic_class=EconomicClass.UNKNOWN,
            economic_source=(
                f"deployment configures {configured_model!r}; its current "
                "price could NOT be read from OpenRouter, so no zero-cost "
                "claim is made and the declared metered rate stands"
            ),
            economic_verified_at=None,
            notes=f"gateway, addressing {configured_model} only",
        )

    return dataclasses.replace(
        descriptor,
        cost_per_call=0.0,
        is_free=True,
        economic_class=EconomicClass.RECURRING_FREE,
        economic_source=(
            f"{observation['source']}: {observation['model']} priced at "
            f"prompt {observation['prompt_price']:g} / completion "
            f"{observation['completion_price']:g}, read at "
            f"{observation['observed_at'].isoformat()}; revalidated again "
            "before every call"
        ),
        economic_verified_at=observation["observed_at"],
        notes=f"gateway, addressing {configured_model} only",
    )


#: What `PROVIDER_CATALOG` declares an OpenRouter call costs in general.
#: The floor an unverified record falls back to, so "we could not read the
#: price" can never be mistaken for "the price is zero".
_OPENROUTER_METERED_COST = 0.005


# The executable entry point, and it belongs HERE -- at the true end of
# the module, after every helper and constant it can reach.
#
# It used to sit above `_configured_cloud_providers`,
# `_restore_canonical_providers` and `OPENROUTER_CONFIGURED_MODEL`. On an
# `import`, that is harmless: the whole module executes before anything
# calls `main()`. Run as a script -- which is exactly what the packaged
# Founder Edition does -- the guard fires the moment the interpreter
# reaches it, `main()` calls `_build_mission_pipeline()`, and the names
# below it do not exist yet. A packaging change alone could have surfaced
# that as a NameError on launch.
if __name__ == "__main__":
    raise SystemExit(main())
