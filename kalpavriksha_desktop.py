"""Kalpavriksha — the Founder Desktop Application entry point.

This is the file `packaging/kalpavriksha.spec` builds into the shipped
executable. A founder never runs this directly — they double-click the
installed app, which double-clicks this. It opens one native window
(via `master_agent.founder_edition.desktop_shell`) and nothing else: no
terminal, no console window, no developer tooling.
"""
from __future__ import annotations

import argparse
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
    download step yet."""
    path = os.path.join(_bundled_dir("voice_models"), "whisper-base.en")
    return path if os.path.isdir(path) else "base.en"


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kalpavriksha", description="Kalpavriksha Founder Edition")
    parser.add_argument("--founder-name", default=None)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args(argv)

    from master_agent.founder_edition.boot import DEFAULT_FOUNDER_NAME
    from master_agent.founder_edition.desktop_shell import create_window

    founder_name = args.founder_name or os.environ.get("KALPAVRIKSHA_FOUNDER_NAME") or DEFAULT_FOUNDER_NAME
    create_window(
        founder_name=founder_name, web_dir=_bundled_dir("web"), debug=args.debug,
        voice_model_path=_voice_model_path(),
        whisper_model=_whisper_model_path(),
        mic_permission_checker=_windows_microphone_allowed,
        open_settings=_open_microphone_settings,
        input_device_resolver=_default_input_device_name,
        output_device_resolver=_default_output_device_name,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
