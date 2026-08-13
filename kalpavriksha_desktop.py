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
    for plugin in (browser_plugin, desktop_plugin):
        for descriptor in mission_control.capabilities.for_executive(plugin.manifest.name):
            permissions.grant(
                plugin.manifest.name, descriptor.capability,
                GrantScope.ALWAYS_FOR_CAPABILITY,
            )

    runtime = RuntimeEngine(
        mission_control,
        approval_gate=PermissionSystemGate(permissions, registry),
    )
    runtime.register_gateway(browser_plugin.manifest.name, PluginGateway(browser_plugin))
    runtime.register_gateway(desktop_plugin.manifest.name, PluginGateway(desktop_plugin))

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
    ledger = DecisionLedger(store=None)  # in-memory; this process is the record
    broker = CapabilityBroker(policy=get_policy("prefer_free"), sink=ledger.record)
    intelligence = AiCapabilityService(
        broker=broker, providers=providers_source, ledger=ledger, approvals=None,
    )
    provider_registry = PluginRegistry()
    provider_registry.register(GeminiProvider(api_key=api_key))
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
    tiered_runner = TieredPromptRunner(
        prompt_executor,
        gemini_provider_ids=frozenset({"gemini.api"}),
        desktop_provider_ids=frozenset(
            spec.provider_id for spec in PROVIDER_CATALOG if spec.locality == DESKTOP
        ),
        browser_provider_ids=frozenset({BROWSER_FREE_AI_ID}),
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
    # MB039's richer index, not the plain CapabilityRegistry — the same
    # exact pattern `build_system()` uses, and for the same reason: the
    # simple `catalogue_from(registry)` path carries no `required_args`,
    # so the Planner's prompt never tells Gemini a capability like
    # `Browser.OpenBrowserSession` needs a `session_id` — proven live
    # against the real API, not assumed.
    contracts = []
    for plugin in (browser_plugin, desktop_plugin):
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
    planner = Planner(runner=tiered_runner, catalogue=capability_index)
    mission_service = MissionService(
        planner=planner, mission_control=mission_control,
        intent_layer=IntentLayer(), reporter=Reporter(),
    )

    # Task 2.5 — the Hyper Agent status contract. One ExecutionStatus,
    # subscribed to the same bus every other observer in this composition
    # already reports through; it never decides anything, only records
    # what already happened (see missions/execution_status.py).
    from master_agent.missions.execution_status import ExecutionStatus

    status = ExecutionStatus()
    mission_control.bus.subscribe(status.record, event_type=None)

    return mission_service, runtime, mission_control, status


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
    from master_agent.missions.execution_status import COMPLETED, FAILED

    status.begin(text, timeout_seconds=timeout_seconds)

    # A capability question is not an objective. Asked before anything is
    # planned, because the Planner's only possible answer to "what can you
    # do" is a refusal — its catalogue describes actions, not itself.
    # The question is recognised by the existing Intent Layer
    # (`IntentLayer.is_capability_question`), and answered from the live
    # capability registry, never a hardcoded list.
    intent_layer = getattr(mission_service, "intent_layer", None)
    if intent_layer is not None and intent_layer.is_capability_question(text):
        status.status = COMPLETED
        status.message = _describe_capabilities(mission_control)
        return {"reply": status.message}

    outcome = mission_service.start(text)
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
        return {"reply": status.message}

    objective_id = outcome.objective_id
    deadline = _time.monotonic() + timeout_seconds
    objective = mission_control.dispatcher.objective(objective_id)
    while _time.monotonic() < deadline and not (objective.is_complete or objective.has_failure):
        runtime.run_once()
        objective = mission_control.dispatcher.objective(objective_id)
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
        return {"reply": status.message}
    if state.progress >= 1.0:
        status.result = state.result
        status.message = _describe_result(state.result)
        return {"reply": status.message}
    status.message = "That's taking longer than expected; still working on it."
    return {"reply": status.message}


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


def _describe_capabilities(mission_control) -> str:
    """What this machine can actually do right now, read from the live
    capability registry Mission Control holds.

    Never a hardcoded list: if an Executive is registered or removed, this
    sentence changes with it, because it is generated from the same
    descriptors the Planner itself plans against. Grouped by executive and
    worded plainly — a founder asking "what can you do" wants the shape of
    the answer, not nine qualified capability ids.
    """
    try:
        descriptors = list(mission_control.capabilities.all())
    except Exception:  # noqa: BLE001 — an unreadable registry is an honest absence
        descriptors = []

    if not descriptors:
        return (
            "Right now I can hold a conversation, but I don't have any "
            "action capabilities wired up yet."
        )

    by_executive: dict[str, list[str]] = {}
    for descriptor in descriptors:
        # `capability` is the Executive's own local verb ("open_browser_
        # session"); rendered as words rather than the qualified id, for
        # the same reason `runtime/approval.py::_human_reason` does it —
        # a founder should not have to read snake_case.
        readable = str(descriptor.capability).replace("_", " ").strip()
        by_executive.setdefault(str(descriptor.executive_id), []).append(readable)

    parts = []
    for executive in sorted(by_executive):
        verbs = sorted(set(by_executive[executive]))
        parts.append(f"{executive}: {', '.join(verbs)}")

    return (
        "Right now I can talk with you, and I can act through these: "
        + "; ".join(parts)
        + ". Tell me what you'd like done and I'll plan it out."
    )


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


def _describe_result(result) -> str:
    """The last task's raw output, in one sentence a founder can read —
    never a re-derived judgment about what happened, only the same facts
    Mission Control already recorded, worded plainly. A browser
    observation's own well-known shape (url/title) gets a short sentence;
    anything else falls back to its own string form rather than guessing
    at a summary this function has no authority to invent."""
    if isinstance(result, dict) and "title" in result and "url" in result:
        return f"Done — the page at {result['url']} loaded with title \"{result['title']}\"."
    return str(result) if result else "Done."


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
    if pipeline is not None:
        mission_service, runtime, mission_control, status = pipeline
        submit_objective = lambda text: _submit_objective(  # noqa: E731
            mission_service, runtime, mission_control, status, text
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
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
