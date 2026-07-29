"""`kalpavriksha` - the founder command (Mission Brief 027.5).

Recovers state, wires every shipped subsystem, starts the Runtime, and
hands the terminal to the Founder Dashboard. Ctrl-C stops the Runtime,
stops the Dashboard, and writes a final snapshot, so the next launch
resumes from a system at rest rather than replaying an interrupted one.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from master_agent.launcher.boot import KalpavrikshaSystem, build_system
from master_agent.launcher.console import FounderConsole
from master_agent.mission_control.tasks import Objective, Task
from master_agent.runtime.config import RuntimeConfig

# A deliberately small, clearly-labelled objective, used only by --demo.
# It exists because there is no way for a founder to state an objective in
# their own words yet: `Objective` requires an explicit Task list naming
# capabilities and payloads, and the component that would turn a sentence
# into that list is the real Planner (`ROADMAP.md`, Planned item 1). Until
# it exists, this is the only way to watch the loop actually run.
DEMO_FOLDER = "Kalpavriksha Demo"
# --demo needs create_folder and write_file. It grants nothing: MB028.1
# routes every approval through the Founder Console, so the demo objective
# appears in the Approval panel and waits for you like anything else.


def demo_objective() -> Objective:
    return Objective(
        description="Demonstration: create a folder and write a file into it",
        tasks=[
            Task(
                capability="Filesystem.CreateFolder",
                payload={"name": DEMO_FOLDER},
                task_id="demo-1",
            ),
            Task(
                capability="Filesystem.WriteFile",
                payload={
                    "path": f"{DEMO_FOLDER}/hello.txt",
                    "content": "Kalpavriksha was here.\n",
                },
                task_id="demo-2",
                depends_on=["demo-1"],
            ),
        ],
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kalpavriksha",
        description="Launch Kalpavriksha: recover, wire, run, and watch.",
    )
    parser.add_argument(
        "--state-dir",
        type=Path,
        default=None,
        help="Where snapshots and the event log live (default: ~/.master_agent/state)",
    )
    parser.add_argument(
        "--approval-timeout",
        type=float,
        default=None,
        help=(
            "Seconds before an unanswered approval expires (default: never). "
            "An expired request fails its task safely; waiting forever is the "
            "safer default, because a request that vanishes overnight is "
            "worse than one still on the screen in the morning."
        ),
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help=(
            "Submit one demonstration objective (create a folder, write a "
            "file) so the loop has work to do. It grants nothing - the "
            "tasks appear in the Approval panel and wait for you."
        ),
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=1.0,
        help="Seconds the Runtime rests between empty cycles (default: 1.0)",
    )
    parser.add_argument(
        "--refresh-interval",
        type=float,
        default=1.0,
        help="Seconds between Dashboard redraws (default: 1.0)",
    )
    parser.add_argument(
        "--boot-only",
        action="store_true",
        help="Print the boot report and exit without starting anything.",
    )
    return parser


def print_boot_report(system: KalpavrikshaSystem) -> None:
    # ASCII only in this module's own output. MB026 found that a cp1252
    # Windows console cannot encode the punctuation this project writes
    # everywhere else; the Dashboard solved it by asking the stream what
    # it can encode. The launcher prints twelve lines, so the proportionate
    # fix is to write nothing that needs encoding.
    print("\nKalpavriksha - boot report\n")
    for line in system.report.as_lines():
        print(f"  {line}")
    if system.report.needs_attention:
        print("\n  Read the lines above that are not [OK]. None of them is a crash;")
        print("  each is something this build genuinely cannot do, said out loud.")
    print()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    system = build_system(
        state_dir=args.state_dir,
        runtime_config=RuntimeConfig(poll_interval_seconds=args.poll_interval),
        approval_timeout_seconds=args.approval_timeout,
        dashboard_kwargs={"refresh_interval_seconds": args.refresh_interval},
    )
    print_boot_report(system)

    if args.boot_only:
        return 0

    if args.demo:
        objective = system.mission_control.submit_objective(demo_objective())
        print(f"  Submitted demonstration objective {objective.objective_id}\n")

    system.start()
    console = FounderConsole(
        system.dashboard,
        system.mission_control,
        refresh_seconds=args.refresh_interval,
    )
    try:
        console.run()
    except KeyboardInterrupt:
        print("\nStopping - saving state.")
    finally:
        problems = system.stop()
        for problem in problems:
            print(f"  shutdown problem: {problem}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
