"""The Founder Edition Console — C33's launcher glue, and nothing else.

*"Running `python app.py` (or the existing launcher) should produce a
working Founder Edition."* This module is what `app.py` (repo root) calls.
It is not a sixth Founder Edition component: every fact it knows about
Somesh, the Runtime, or a reply came from `boot_founder_edition()` (C24/
C30) and the `ConversationEngine`/`CommunicationEngine` it already wires
(C31/C32). This module supplies exactly the two things C1–C32 deliberately
left unimplemented and named as a caller's job:

1. **A real `TextOutput`/`TextInput`** — `communication/channels.py`
   provides the interface and refuses to provide a body
   (`tests/test_communication.py::TestNoImplementationLeakage`). Reading
   `input()` and calling `print()` is the smallest possible implementation
   of that contract, the same relationship `desktop.probe.RealSystemProbe`
   already has to `desktop.probe.SystemProbe`.
2. **Terminal formatting** of the dicts `FounderEditionApp.dashboard()`
   and `BootReport.as_dict()` already produce. `dashboard/founder_panels.
   py` cannot be reused for this (see `Engineering/HEALTH_C33.md` §3) —
   it renders a different read model (`dashboard.readmodel.
   DashboardSnapshot`, fed by Mission Control) that this dict is not
   shaped like. What is here is the same class of function as `launcher.
   main.print_boot_report()`: string formatting, not a second dashboard.

## Why voice is absent rather than faked

*"Voice is primary. Text is fallback."* No real speech engine exists
anywhere in this codebase: `master_agent.voice.Speaker`/`Transcriber` both
`raise NotImplementedError`, and C32's own forbidden list bars building
one here (*"No speech recognition... No TTS... No Whisper... No
ElevenLabs"*). Registering a fabricated `VoiceOutput` that printed text
while claiming to speak would misreport what actually happened — exactly
the lie `founder_runtime`'s own `Source.reason` discipline exists to
prevent. So this module boots with **text only**, states that limitation
in the boot report and in the console's own banner, and leaves the
`voice_output` slot honestly `None`. See `Engineering/HEALTH_C33.md` §2
for the full observation and the proposed integration path.

## The `ChannelNotRegistered` recovery

A founder can still type *"switch to voice"* — `CommunicationRouter`
recognises the phrase and flips its mode before this module ever sees the
request, so the very next reply (including the switch's own
acknowledgement) needs a voice channel that was never registered, and
`CommunicationEngine.handle()` raises `ChannelNotRegistered`. This module
catches that one exception, tells the founder honestly, and immediately
routes a synthetic *"switch to text"* through the same engine — a real
recognised phrase, not a fabricated reply — to leave the app usable
rather than stuck. Recorded as Observation 2 in `Engineering/
HEALTH_C33.md` rather than fixed inside `communication/`, which is a
complete, audited-pending component this integration does not reopen.
"""
from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from typing import Any, TextIO

from master_agent.communication import (
    ChannelNotRegistered,
    CommunicationRequest,
    CommunicationResponse,
    Source,
    TextInput,
    TextOutput,
)
from master_agent.founder_edition.boot import (
    DEFAULT_FOUNDER_NAME,
    FounderEditionApp,
    boot_founder_edition,
)

CONVERSATION_ID = "founder-edition-console"

#: Words that end the console loop. A closed set, matched after
#: normalising case and surrounding whitespace — the same discipline
#: `founder_identity`/`communication` already use for every other
#: recognised phrase in this codebase.
_QUIT_WORDS = ("quit", "exit", "bye")

_BANNER = (
    "Kalpavriksha Founder Edition — Desktop Alpha (C33)\n"
    "Text is live. Voice is not wired in this build (no speech engine\n"
    "exists in this codebase — see Engineering/HEALTH_C33.md).\n"
    "Type to talk to Somesh. 'dashboard' redraws the live view, "
    "'quit' exits.\n"
)


class ConsoleTextOutput(TextOutput):
    """Prints `response.display` to a stream. The whole implementation —
    matching the brief's own instruction that a channel is *"only
    routing... not implementation."*

    `stream` defaults to `None` and is resolved to `sys.stdout` inside
    `__init__` rather than in the signature — a default evaluated in the
    signature is bound once, at import time, and would keep printing to
    whatever `sys.stdout` was *then* even after a caller (a test, a
    redirected run) replaces it.
    """

    def __init__(self, stream: TextIO | None = None) -> None:
        self._stream = stream if stream is not None else sys.stdout

    def emit(self, response: CommunicationResponse) -> None:
        print(f"Somesh: {response.display}", file=self._stream)


class ConsoleTextInput(TextInput):
    """Reads one line from a stream and wraps it as a `CommunicationRequest`.

    `datetime.now(UTC)` is read here deliberately: this class sits
    outside every package `communication/`'s and `conversation_engine/`'s
    own AST guards forbid ambient time in (`tests/test_communication.py::
    TestBoundaries::test_no_ambient_clock_is_read` scans `communication/`
    itself, not its callers) — a real channel reading a real clock is
    precisely the boundary those guards exist to let happen *somewhere*.
    """

    def __init__(self, stream: TextIO | None = None) -> None:
        self._stream = stream if stream is not None else sys.stdin

    def receive(self) -> CommunicationRequest:
        """Read lines until one carries real content, or the stream
        closes. `CommunicationRequest` refuses blank content by design
        (C32's own validation) — there is no valid request a bare Enter
        press could produce, so this reads past it rather than
        constructing one that would fail to build."""
        while True:
            line = self._stream.readline()
            if line == "":
                raise EOFError("the input stream closed")
            content = line.rstrip("\n")
            if content.strip():
                return CommunicationRequest(
                    source=Source.TEXT, content=content,
                    timestamp=datetime.now(UTC), conversation_id=CONVERSATION_ID,
                )


def format_boot_report(app: FounderEditionApp) -> str:
    """One line per step, ASCII only — `launcher.main.print_boot_report`'s
    own reason: a cp1252 Windows console cannot encode this project's
    usual punctuation, and a boot report is not the place to find that
    out."""
    lines = ["Kalpavriksha Founder Edition -- boot report", ""]
    for step in app.report.steps:
        lines.append(f"  [{step.status:^12}] {step.name:<20} {step.detail}")
    if app.report.needs_attention:
        lines.append("")
        lines.append("  Steps above marked 'unavailable' are honest gaps, not crashes.")
    return "\n".join(lines)


def format_dashboard(dashboard: dict[str, Any]) -> str:
    """Every section `FounderEditionApp.dashboard()` produces, as plain
    text. Formatting only — every value printed here was already computed
    by C23/C29/C30; nothing here derives a fact of its own."""
    identity = dashboard["identity"]
    session = dashboard["session"]
    presence = dashboard["presence"]
    coverage = presence.get("coverage")
    desktop = dashboard["desktop"]

    lines = [
        "-" * 60,
        (
            f" {identity['assistant_name']}, for {identity['founder_name']}"
            f" ({identity['edition']})"
        ),
        "-" * 60,
        f" Session      active={session['active']}"
        + (
            f", last said: {session['last_founder_utterance']!r}"
            if session["last_founder_utterance"] is not None
            else ""
        ),
        f" Environment  {'known' if dashboard['environment'] is not None else 'not scanned yet'}",
    ]

    if coverage is None:
        lines.append(" Presence     no vigilance domain registered")
    else:
        lines.append(
            f" Presence     complete={coverage['complete']}, "
            f"gaps={len(coverage['gaps'])}"
        )

    entries = dashboard["conversation"]["entries"] if dashboard["conversation"] else []
    lines.append(f" Conversation {len(entries)} turn(s)")

    if desktop is None:
        lines.append(" Desktop      not wired")
    else:
        wired = ", ".join(layer["name"] for layer in desktop["layers"] if layer["wired"])
        lines.append(f" Desktop      {wired}")

    sources = ", ".join(
        f"{s['name']}={'yes' if s['present'] else 'no'}" for s in dashboard["sources"]
    )
    lines.append(f" Sources      {sources}")
    lines.append("-" * 60)
    return "\n".join(lines)


def process_line(app: FounderEditionApp, text: str, *, out: TextIO = sys.stdout) -> bool:
    """One founder line, handled through C31/C32 alone. Returns `False`
    when the console should stop.

    No branch here composes a reply — recognised speech is answered by
    `app.communication.handle()`, unrecognised speech gets the console's
    own honest note (never attributed to Somesh), and `dashboard`/quit are
    console commands, not conversation.
    """
    stripped = text.strip()
    lowered = stripped.lower()

    if lowered in _QUIT_WORDS:
        return False

    if lowered == "dashboard":
        print(format_dashboard(app.dashboard()), file=out)
        return True

    if not stripped:
        return True

    request = CommunicationRequest(
        source=Source.TEXT, content=text, timestamp=datetime.now(UTC),
        conversation_id=CONVERSATION_ID,
    )

    try:
        routed = app.communication.handle(request)
    except ChannelNotRegistered as exc:
        print(f"[console] {exc} -- switching back to text.", file=out)
        recovery = CommunicationRequest(
            source=Source.TEXT, content="switch to text",
            timestamp=datetime.now(UTC), conversation_id=CONVERSATION_ID,
        )
        app.communication.handle(recovery)
        return True

    if routed is None:
        print(
            "[console] no recognised response -- try a greeting, "
            "'Continue', 'How's the system?', 'What are you doing?', "
            "'What should I work on?', or a build request.",
            file=out,
        )

    print(format_dashboard(app.dashboard()), file=out)
    return True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kalpavriksha-founder-edition",
        description="Launch Kalpavriksha Founder Edition (Desktop Alpha, C33).",
    )
    parser.add_argument(
        "--founder-name", default=DEFAULT_FOUNDER_NAME,
        help="How Somesh should address you (default: %(default)r).",
    )
    return parser


def run_repl(app: FounderEditionApp, *, input_stream: TextIO = sys.stdin,
             output_stream: TextIO = sys.stdout) -> None:
    print(_BANNER, file=output_stream)
    print(format_dashboard(app.dashboard()), file=output_stream)
    console_input = ConsoleTextInput(input_stream)
    while True:
        print("You: ", end="", file=output_stream, flush=True)
        try:
            request = console_input.receive()
        except EOFError:
            print(file=output_stream)
            break
        if not process_line(app, request.content, out=output_stream):
            break
    print("Stopping -- the founder runtime is a fresh session next launch.",
          file=output_stream)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    app = boot_founder_edition(
        founder_name=args.founder_name, text_output=ConsoleTextOutput(),
    )
    print(format_boot_report(app))

    if not app.ready:
        print("\nBoot did not complete; Founder Edition cannot start.")
        return 1
    if app.communication is None:
        print("\nThe communication layer did not wire up; see the boot report above.")
        return 1

    try:
        run_repl(app)
    except KeyboardInterrupt:
        print("\nStopping.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
