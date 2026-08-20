"""Kalpavriksha — the Founder Desktop Application entry point.

This is the file `packaging/kalpavriksha.spec` builds into the shipped
executable. A founder never runs this directly — they double-click the
installed app, which double-clicks this. It opens one native window
(via `master_agent.founder_edition.desktop_shell`) and nothing else: no
terminal, no console window, no developer tooling.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys


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

    Returns `None` when no reasoning provider is configured — Founder
    Edition then degrades to conversation-only, the same "construct
    regardless, absence is a fact" posture the rest of this project
    already takes with credentials (`GeminiConfig.api_key`).
    """
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return None

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
    from master_agent.runtime.gateway import PluginGateway
    from master_agent.runtime.approval import PermissionSystemGate
    from master_agent.ai_infrastructure.catalog import CLOUD, DESKTOP, PROVIDER_CATALOG
    from master_agent.ai_infrastructure.profiles import ProviderSource
    from master_agent.ai_infrastructure.service import AiCapabilityService
    from master_agent.ai_infrastructure.execution import PromptExecutor
    from master_agent.ai_infrastructure.ledger import DecisionLedger
    from master_agent.ai_infrastructure.tiered_runner import TieredPromptRunner
    from master_agent.broker.broker import CapabilityBroker
    from master_agent.broker.policy import get_policy
    from master_agent.providers.gemini import GeminiProvider
    from master_agent.providers.desktop_app import build_desktop_providers
    from master_agent.providers.browser_free_ai import (
        BrowserFreeAiReasoningProvider,
        BROWSER_FREE_AI_SPEC,
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
    browser_plugin = BrowserPlugin(
        executor,
        BrowserSessionManager(default_headless=False, default_channel="chrome"),
    )
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
    # unchanged. It adds canonical Evidence for the five capabilities with
    # a read-only postcondition (launch/close application, focus,
    # bring-to-front, close window) and returns None for the rest, which
    # is what the old gateway did for all of them.
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
    providers_source = ProviderSource(
        inventory_provider=lambda: desktop_plugin._context.cached,
        # `PROVIDER_CATALOG + (BROWSER_FREE_AI_SPEC,)`, not the bare
        # catalogue: `BROWSER_FREE_AI_SPEC` is deliberately excluded from
        # the shared, global `PROVIDER_CATALOG` (see that module's own
        # note) so it only ever exists for a composition root that
        # actually registers the provider — this one.
        specs=PROVIDER_CATALOG + (BROWSER_FREE_AI_SPEC,),
        enabled_cloud_providers=("gemini.api",),
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
    provider_registry = PluginRegistry()
    provider_registry.register(GeminiProvider(api_key=api_key))
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
    # Tier 3 — the final, last-resort fallback.
    provider_registry.register(BrowserFreeAiReasoningProvider())
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

    tiered_runner = TieredPromptRunner(
        prompt_executor,
        gemini_provider_ids=frozenset({"gemini.api"}),
        desktop_provider_ids=frozenset() if _gemini_only else frozenset(
            spec.provider_id for spec in PROVIDER_CATALOG if spec.locality == DESKTOP
        ),
        browser_provider_ids=frozenset() if _gemini_only else frozenset({BROWSER_FREE_AI_ID}),
        desktop_context=desktop_plugin._context,
        # The Broker sees every spec in `providers_source`'s own `specs`
        # tuple (`PROVIDER_CATALOG + (BROWSER_FREE_AI_SPEC,)` — Ollama,
        # LM Studio, OpenAI, OpenRouter included), not just the three
        # tiers above. Without this, any of those could win a tier's
        # scoped Broker call by ranking (Ollama notably — this codebase's
        # own repeated "never enable/query Ollama" constraint) purely
        # because nothing had told this ladder they existed to exclude.
        all_known_provider_ids=frozenset(
            spec.provider_id for spec in PROVIDER_CATALOG
        ) | {BROWSER_FREE_AI_ID},
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
    persistence.start_recording()
    plan_history = PlanHistory(store=JsonFilePlanStore(state_dir / HISTORY_FILENAME))
    plan_history.attach_to(mission_control)

    mission_service = MissionService(
        planner=planner, mission_control=mission_control,
        intent_layer=IntentLayer(), reporter=Reporter(),
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
    def _set_mode(mode: str) -> None:
        mode_cell["mode"] = _normalise_mode(mode)

    return (mission_service, runtime, mission_control, status, tiered_runner,
            _set_mode, interactions)


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
    pending = status.pending_clarification

    status.begin(text, timeout_seconds=timeout_seconds)

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
    # A question was asked last turn, so this message is its answer.
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
    # to be work -- can land on an open question. STATED LIMIT: an
    # unrelated escalated request typed while a question is open ("what's
    # the weather today?") is taken as the answer, because nothing in
    # this architecture can tell an odd folder name from a change of
    # subject without guessing, and guessing is what the standing rule
    # forbids. Deterministic and documented, per ADR-0024's discipline of
    # stating a boundary rather than papering over it.
    if pending is not None:
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
        resolved: dict[str, str] = dict(getattr(pending, "supplied", {}) or {}) if pending else {}
        if pending is not None and pending.key:
            resolved[pending.key] = text
        status.pending_clarification = PendingClarification(
            question=question.question,
            key=question.key,
            objective=objective,
            options=tuple(question.options),
            required=question.required,
            supplied=resolved,
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
    deadline = _time.monotonic() + timeout_seconds
    objective = mission_control.dispatcher.objective(objective_id)
    while _time.monotonic() < deadline and not (objective.is_complete or objective.has_failure):
        runtime.run_once()
        objective = mission_control.dispatcher.objective(objective_id)
        # Waiting on the founder is a terminal state for THIS call. The
        # work has run and been verified; nothing further will happen
        # until a human answers, so spinning to the deadline only delays
        # telling them so -- and, before this, ended in "that's taking
        # longer than expected" about a mission that had already finished.
        if status.requires_founder_completion or status.status in (
            AWAITING_APPROVAL, AWAITING_FOUNDER_COMPLETION
        ):
            break
        if not (objective.is_complete or objective.has_failure):
            _time.sleep(0.2)

    state = mission_control.founder_state(objective_id)
    if state.errors:
        # Same hygiene as the refusal branch above: the founder gets a
        # sentence, the full executive/Playwright/gateway diagnostic stays
        # in the log and on `status.errors` where a developer will look.
        joined = "; ".join(state.errors)
        logging.warning("objective failed: %s", joined)
        status.message = _founder_failure_sentence(joined)
        return _founder_reply(status, status.message)
    if state.progress >= 1.0:
        # `state.result` is still recorded -- other consumers legitimately
        # want the last Task result -- but it is no longer what the founder
        # is told the MISSION did.
        status.result = state.result
        status.message = _mission_report(mission_service, status.objective_id) or (
            "The work finished, but I can't reconstruct a verified mission summary."
        )
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
    return "That didn't complete. I've kept the details for review."


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


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format='[%(levelname)s] %(name)s: %(message)s')
    parser = argparse.ArgumentParser(prog='kalpavriksha', description='Kalpavriksha Founder Edition')
    parser.add_argument("--founder-name", default=None)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args(argv)

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
         set_mode, interactions) = pipeline
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
        # The founder's decision on an open approval. Mission Control's
        # own approve/reject -- this composition root decides nothing
        # about whether the decision is allowed, it only carries it.
        def decide_approval(approval_id, approved, note=""):
            """Carry the founder's decision to Mission Control -- and, on
            approval, into the grant ledger that the permission boundary
            actually reads.

            Both steps are required, and the second is not a workaround.
            `ApprovalQueue.find_open` is scoped to *undecided* requests by
            design ("an approved one does not silently authorise a
            repeat"), so an answered approval does not by itself let the
            held task through -- the next boundary check would open a
            fresh question and the task would wait forever. `GrantScope
            .ONCE` is the existing mechanism for exactly this: it
            authorises this one execution and is consumed by it, which
            preserves the no-silent-repeat property the queue is
            protecting.
            """
            if approved:
                approval = mission_control.approvals.get(approval_id)
                if approval is not None:
                    permissions.grant(
                        approval.executive_id, approval.local_capability,
                        GrantScope.ONCE,
                    )
                return mission_control.approve(approval_id, "founder", note).as_dict()
            return mission_control.reject(approval_id, "founder", note).as_dict()
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


if __name__ == "__main__":
    raise SystemExit(main())
