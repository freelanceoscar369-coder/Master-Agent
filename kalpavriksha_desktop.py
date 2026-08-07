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
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
