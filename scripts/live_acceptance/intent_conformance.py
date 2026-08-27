"""LIVE ACCEPTANCE — can Kalpavriksha hold the conversation?

    python scripts/live_acceptance/intent_conformance.py

Not a pytest test. It drives the **production** composition: the real
`IntentLayer`, with the real location vocabulary the composition root
builds (including the founder's D: drive), the real reasoning ladder, and
— for the cases that finish — a real folder on the founder's Desktop,
verified by reading the disk.

## What it is for

The unit battery proves the mechanism against a stubbed reasoner. This
proves the thing that actually ships, because the two can differ in
exactly the ways that matter: a vocabulary assembled at runtime, a
provider ladder that may be exhausted, a layer wired up differently in
the composition root than in a fixture.

## How a case is written

The test supplies the founder's *replies* and nothing else. It never
supplies the questions — whatever the layer decides to ask is what gets
answered. A conversation that converges here converged on its own.

Phrasings below are test DATA. They are evidence that a semantic class
works; none of them appears in `src/`, and none of them may become a
production table.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src"))

os.environ.setdefault("KALPAVRIKSHA_DISABLE_MIC", "1")

import kalpavriksha_desktop as kd  # noqa: E402

DESKTOP = Path(os.path.expanduser("~")) / "Desktop"
STAMP = time.strftime("%H%M%S")


def banner(text: str) -> None:
    print("\n" + "=" * 72, flush=True)
    print(text, flush=True)
    print("=" * 72, flush=True)


class Conversation:
    """One founder conversation, against the production Intent Layer."""

    def __init__(self, layer) -> None:
        self._layer = layer
        self.asked: list[str] = []
        self.reasoned = 0

    def run(self, opening: str, replies: list[str]):
        """Returns (payload, still_asking, evidence)."""
        result = self._layer.parse(opening)
        known: dict[str, str] = {}
        for reply in replies:
            if not result.needs_clarification:
                break
            self.asked.append(result.clarification.question)
            result = self._layer.clarify(
                opening, reply, result.clarification, supplied=known
            )
            known = dict(getattr(result, "resolved", None) or known)
        if result.intent is None:
            question = (
                result.clarification.question if result.needs_clarification else ""
            )
            return None, question, {}
        evidence = dict(result.intent.context.get("field_evidence") or {})
        self.reasoned += sum(
            1 for found in evidence.values() if found.get("source") == "reasoned"
        )
        # Payload AND context. Different Intent families put their
        # resolved fields in different places -- `CreateFolder` in the
        # payload, `ListDirectory` in the context -- and a check that
        # only reads one of them silently passes on the other, which is
        # what an earlier version of this runner did.
        settled = {**dict(result.intent.context or {}),
                   **dict(result.intent.payload or {})}
        settled.pop("field_evidence", None)
        settled.pop("clarified", None)
        settled.pop("raw_input", None)
        return settled, "", evidence


class Case:
    def __init__(self, name: str, opening: str, replies: list[str]) -> None:
        self.name = name
        self.opening = opening
        self.replies = replies
        self.checks: list[tuple[bool, str]] = []
        self.notes: dict[str, object] = {}

    def check(self, passed: bool, description: str) -> None:
        self.checks.append((bool(passed), description))

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(ok for ok, _ in self.checks)

    def report(self) -> None:
        print(f"\n  {'PASS' if self.passed else 'FAIL'}  {self.name}", flush=True)
        print(f"        founder: {self.opening!r} "
              f"then {' | '.join(repr(r) for r in self.replies)}", flush=True)
        for key, value in self.notes.items():
            print(f"        {key}: {value}", flush=True)
        for ok, description in self.checks:
            print(f"        [{'PASS' if ok else 'FAIL'}] {description}", flush=True)


def main() -> int:
    banner("PRODUCTION COMPOSITION")
    pipeline = kd._build_mission_pipeline()
    if pipeline is None:
        print("NO PIPELINE.", flush=True)
        return 2
    mission_service = pipeline[0]
    layer = mission_service.intent_layer
    vocabulary = getattr(layer, "_vocabularies", {})
    print(f"  intent layer   : {type(layer).__module__}.{type(layer).__name__}",
          flush=True)
    print(f"  from           : {sys.modules[type(layer).__module__].__file__}",
          flush=True)
    print(f"  vocabulary     : {vocabulary}", flush=True)
    print(f"  reasoner wired : {getattr(layer, '_reasoner', None) is not None}",
          flush=True)

    places = tuple(vocabulary.get("location") or ())
    if not places:
        print("  the production layer was given no location vocabulary", flush=True)
        return 2

    cases: list[Case] = []

    # ---- the classes from the brief's own acceptance list -----------
    def conversation(case: Case):
        talk = Conversation(layer)
        payload, still_asking, evidence = talk.run(case.opening, case.replies)
        case.notes["asked"] = talk.asked
        case.notes["payload"] = payload or f"(still asking: {still_asking})"
        if evidence:
            case.notes["evidence"] = {
                name: f"{found['value']} [{found['source']}]"
                + (f" replaced {found['replaced']}" if found.get("replaced") else "")
                for name, found in evidence.items()
            }
        return payload, still_asking

    # DIRECT
    direct = Case("DIRECT — one complete sentence",
                  f"Create a folder called KVIntent_{STAMP}_A on the Desktop", [])
    payload, _ = conversation(direct)
    direct.check(bool(payload), "resolved without asking anything")
    direct.check((payload or {}).get("name") == f"KVIntent_{STAMP}_A",
                 "the name is theirs")
    direct.check(str((payload or {}).get("location", "")).lower() == "desktop",
                 "the place is theirs")
    cases.append(direct)

    # MULTI-TURN, answered in ordinary language
    staged = Case("MULTI-TURN — a name, then a place said naturally",
                  "create a folder",
                  [f"KVIntent_{STAMP}_B", "put it on my desktop please"])
    payload, still = conversation(staged)
    staged.check(bool(payload), f"the conversation converged ({still})")
    staged.check((payload or {}).get("name") == f"KVIntent_{STAMP}_B",
                 "the name survived")
    staged.check(str((payload or {}).get("location", "")).lower() == "desktop",
                 "the place was understood")
    cases.append(staged)

    # MULTI-FIELD in one reply
    both = Case("MULTI-FIELD — one reply settles two fields",
                "create a folder",
                [f"call it KVIntent_{STAMP}_C and put it in Documents"])
    payload, still = conversation(both)
    both.check(bool(payload), f"the conversation converged ({still})")
    both.check((payload or {}).get("name") == f"KVIntent_{STAMP}_C",
               "the name was read")
    both.check(str((payload or {}).get("location", "")).lower() == "documents",
               "the place was read from the same sentence")
    cases.append(both)

    # CORRECTION
    fixed = Case("CORRECTION — the founder changes their mind",
                 "create a folder",
                 [f"KVIntent_{STAMP}_D", "Desktop", "actually use Documents instead"])
    talk = Conversation(layer)
    result = layer.parse(fixed.opening)
    known: dict[str, str] = {}
    for reply in fixed.replies:
        question = result.clarification if result.needs_clarification else question
        result = layer.clarify(fixed.opening, reply, question, supplied=known)
        known = dict(getattr(result, "resolved", None) or known)
    payload = dict(result.intent.payload or {}) if result.intent else None
    fixed.notes["payload"] = payload
    fixed.notes["evidence"] = (
        (result.intent.context.get("field_evidence") if result.intent else None) or {}
    )
    fixed.check(payload is not None, "the conversation converged")
    if payload:
        fixed.check(str(payload.get("location", "")).lower() == "documents",
                    "the corrected place replaced the stale one")
        fixed.check(payload.get("name") == f"KVIntent_{STAMP}_D",
                    "the name was not disturbed by the correction")
    cases.append(fixed)

    # AMBIGUOUS — must not guess
    vague = Case("AMBIGUOUS — a referent with nothing to refer to",
                 "create a folder", [f"KVIntent_{STAMP}_E", "put it there"])
    payload, still = conversation(vague)
    vague.check(payload is None, "nothing was invented")
    vague.check(bool(still), "the founder was asked instead")
    cases.append(vague)

    # INVALID — somewhere the machine cannot reach
    nowhere = Case("INVALID — a place this machine does not have",
                   "create a folder", [f"KVIntent_{STAMP}_F", "on the moon"])
    payload, still = conversation(nowhere)
    nowhere.check(payload is None, "an unreachable place did not become a location")
    nowhere.check(bool(still), "the founder was asked instead")
    cases.append(nowhere)

    # CONTEXT — the same word, two questions
    context = Case("CONTEXT — a place-word used as a NAME",
                   "create a folder", ["Desktop", "in Documents"])
    payload, still = conversation(context)
    context.check(bool(payload), f"the conversation converged ({still})")
    context.check((payload or {}).get("name") == "Desktop",
                  "the word answering 'what is it called' is the name")
    context.check(str((payload or {}).get("location", "")).lower() == "documents",
                  "and the place came from the reply that named a place")
    cases.append(context)

    # ---- other Intent families, same mechanism ---------------------
    listing = Case("ANOTHER FAMILY — list files, place said naturally",
                   "list files", ["in my Downloads please"])
    payload, still = conversation(listing)
    listing.check(bool(payload), f"the conversation converged ({still})")
    listing.check(str((payload or {}).get("location", "")).lower() == "downloads",
                  "the shared vocabulary resolved it")
    cases.append(listing)

    project = Case("ANOTHER FAMILY — a project name is read, not re-asked",
                   "create a project", ["Atlas"])
    payload, still = conversation(project)
    project.check(bool(payload), f"the conversation converged ({still})")
    project.check((payload or {}).get("project_name") == "Atlas",
                  "the name the founder gave was read, not asked for again")
    cases.append(project)

    banner("INTENT CONFORMANCE")
    for case in cases:
        case.report()

    # ---- does it actually happen on disk ---------------------------
    banner("REAL OUTCOME — the staged conversation, executed")
    executed = Case("EXECUTED — multi-turn folder, verified on disk",
                    "create a folder",
                    [f"KVIntent_{STAMP}_G", "on my desktop"])
    (service, runtime, control, status, _runner,
     _mode, _interactions, _approve) = pipeline
    result = service.intent_layer.parse(executed.opening)
    known = {}
    for reply in executed.replies:
        question = result.clarification
        result = service.intent_layer.clarify(
            executed.opening, reply, question, supplied=known
        )
        known = dict(getattr(result, "resolved", None) or known)
    executed.notes["payload"] = dict(result.intent.payload or {}) if result.intent else None
    if result.intent is None:
        executed.check(False, "the conversation never resolved, so nothing ran")
    else:
        outcome = service.start(result.intent)
        if outcome.accepted:
            deadline = time.monotonic() + 60
            record = control.dispatcher.objective(outcome.objective_id)
            while time.monotonic() < deadline and not (
                record.is_complete or record.has_failure
            ):
                runtime.run_once()
                record = control.dispatcher.objective(outcome.objective_id)
                time.sleep(0.1)
            executed.notes["evidence"] = [
                (task.capability, (task.evidence or {}).get("verdict") or "none")
                for task in record.tasks
            ]
        else:
            executed.check(False, f"the mission was refused: {outcome.refusal}")
        target = DESKTOP / f"KVIntent_{STAMP}_G"
        executed.check(target.is_dir(), f"the folder is on disk: {target}")
    executed.report()
    cases.append(executed)

    banner("SUMMARY")
    for case in cases:
        print(f"  {'PASS' if case.passed else 'FAIL'}  {case.name}", flush=True)
    everything = all(case.passed for case in cases)
    banner(f"INTENT CONFORMANCE: {'PASS' if everything else 'FAIL'}")
    return 0 if everything else 1


if __name__ == "__main__":
    raise SystemExit(main())
